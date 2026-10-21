"""Immutable previous experiment; all current model choices use inner source folds."""
from pathlib import Path
import collections
import hashlib
import json
import math
import sqlite3
import statistics
import sys
import time
import numpy as np
from threadpoolctl import threadpool_limits

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from data.cycling_db import open_database
from grouped_model_improvement import prepare, fit_predict, inner_splits, select
from train_initial_baselines import write, read, sha, now, weighted_metrics

OUT = ROOT / '模型诊断与改进_20261021'


def summary(predictions):
    result = []
    baseline = {r['endpoint_id']: r for r in predictions if r['variant'] == 'mean/full'}
    old_best = {r['endpoint_id']: r for r in predictions if r['variant'] == 'previous_mlp_no_current'}
    for variant in dict.fromkeys(r['variant'] for r in predictions):
        records = [r for r in predictions if r['variant'] == variant]
        if len(records) != 31:
            continue
        groups = collections.defaultdict(list)
        for r in records:
            groups[r['source_group']].append(r)
        weights = [1 / len(groups[r['source_group']]) for r in records]
        row = {'variant': variant, **weighted_metrics([r['observed'] for r in records],
               [r['predicted'] for r in records], weights)}
        errors = np.asarray([statistics.fmean(abs(r['predicted'] - r['observed']) for r in rs) for rs in groups.values()])
        indexes = np.random.default_rng(20261021).integers(0, len(groups), (2000, len(groups)))
        lo, hi = np.quantile(errors[indexes].mean(axis=1), [.025, .975])
        row.update(mae_ci_low=float(lo), mae_ci_high=float(hi), source_groups=len(groups), rows=len(records))
        for tag, reference in [('mean', baseline), ('previous_mlp_no_current', old_best)]:
            differences = np.asarray([statistics.fmean(abs(r['predicted'] - r['observed']) -
                abs(reference[r['endpoint_id']]['predicted'] - r['observed']) for r in rs) for rs in groups.values()])
            lo, hi = np.quantile(differences[indexes].mean(axis=1), [.025, .975])
            row['delta_vs_' + tag] = {'mae': float(differences.mean()), 'low': float(lo), 'high': float(hi)}
        result.append(row)
    return result


def main():
    if (OUT / 'evaluation.sqlite').exists() or (OUT / 'results.json').exists():
        raise FileExistsError('Use a new experiment. Never overwrite a completed or partial diagnostic run.')
    plan = read(OUT / 'training_plan.json')
    if not plan['authorization']['authorized']:
        raise ValueError('This run requires explicit user authorization.')
    plan_hash = sha(OUT / 'training_plan.json')
    with open_database() as db:
        ds = db.fetch()
        if ds.fingerprint() != plan['dataset_fingerprint']:
            raise ValueError('Dataset changed.')
    rows = ds.rows
    prior = ROOT / plan['prior_run']
    protected = read(prior / 'run_manifest.json')['outputs']
    for p in protected:
        if sha(ROOT / p['path']) != p['sha256']:
            raise ValueError('Previous experiment changed: ' + p['path'])
    old_predictions = read(prior / 'predictions.json')
    predictions = []
    for r in old_predictions:
        if r['variant'] in ['mean/full', 'MLP/full', 'MLP/no_current']:
            variant = {'MLP/full': 'previous_mlp_full', 'MLP/no_current': 'previous_mlp_no_current'}.get(r['variant'], r['variant'])
            predictions.append({**r, 'variant': variant, 'prediction_origin': 'verified_previous_fixed_parameter_run'})
    state = read(OUT / 'progress.json')
    state.update(status='running', started_at=now(), predictions=predictions, metrics=summary(predictions),
                 models=[{'variant': v, 'completed': 0, 'total': 23} for v in ['nested_min', 'nested_1se', 'nested_linear']])
    start = time.monotonic()
    last_write = 0
    fitted = 0
    decisions = []

    def progress(force=False):
        nonlocal last_write
        state.update(elapsed_seconds=round(time.monotonic() - start, 3), updated_at=now(),
                     percent=100 * state['completed'] / state['total'], actual_estimator_fits=fitted)
        if force or time.monotonic() - last_write >= .5:
            write(OUT / 'progress.json', state)
            last_write = time.monotonic()

    def task(kind, fold, candidate):
        state['completed'] += 1
        state['events'].append({'seconds': round(time.monotonic() - start, 3), 'completed': state['completed'],
                                'outer_fold': fold, 'phase': kind, 'candidate': candidate})
        progress()

    connection = sqlite3.connect(OUT / 'evaluation.sqlite')
    connection.executescript('''
    CREATE TABLE inner_predictions(outer_fold INTEGER,inner_fold INTEGER,candidate TEXT,endpoint_id TEXT,source_group TEXT,observed REAL,predicted REAL,PRIMARY KEY(outer_fold,candidate,endpoint_id));
    CREATE TABLE inner_fit_audit(outer_fold INTEGER,inner_fold INTEGER,candidate TEXT,fit_json TEXT,PRIMARY KEY(outer_fold,inner_fold,candidate));
    CREATE TABLE split_audit(outer_fold INTEGER,inner_fold INTEGER,split_json TEXT,PRIMARY KEY(outer_fold,inner_fold));
    CREATE TABLE preprocessing(outer_fold INTEGER,inner_fold INTEGER,transform_key TEXT,schema_json TEXT,PRIMARY KEY(outer_fold,inner_fold,transform_key));
    CREATE TABLE selections(outer_fold INTEGER PRIMARY KEY,decision_json TEXT);
    CREATE TABLE outer_fit_audit(outer_fold INTEGER,candidate TEXT,fit_json TEXT,PRIMARY KEY(outer_fold,candidate));
    ''')
    try:
        progress(True)
        with threadpool_limits(limits=1):
            for outer_no, outer in enumerate(ds.source_folds(23), 1):
                state['active'] = {'phase': 'inner_selection', 'fold': outer_no, 'total_folds': 23, 'variant': '内层候选比较'}
                by_candidate = {s['id']: [] for s in plan['candidates']}
                for inner_no, (train, valid) in enumerate(inner_splits(rows, outer['train'], outer['test']), 1):
                    split = {'train': train, 'test': valid, 'outer_holdout': outer['test'],
                             'train_source_groups': sorted({rows[i]['source_group'] for i in train}),
                             'validation_source_groups': sorted({rows[i]['source_group'] for i in valid}),
                             'outer_source_groups': sorted({rows[i]['source_group'] for i in outer['test']})}
                    connection.execute('insert into split_audit values(?,?,?)', (outer_no, inner_no, json.dumps(split)))
                    cache = {}
                    for spec in plan['candidates']:
                        key = spec['transform'] + '/' + str(spec['current'])
                        if key not in cache:
                            cache[key] = prepare(rows, train, valid, spec)
                            connection.execute('insert into preprocessing values(?,?,?,?)',
                                (outer_no, inner_no, key, json.dumps(cache[key]['schema'])))
                        p, audit = fit_predict(cache[key], spec)
                        fitted += int(audit['estimator_fitted'])
                        audit.update(target_center=cache[key]['target_center'], target_scale=cache[key]['target_scale'],
                                     train_weights=cache[key]['weights'].tolist(), transform_key=key)
                        connection.execute('insert into inner_fit_audit values(?,?,?,?)',
                                           (outer_no, inner_no, spec['id'], json.dumps(audit)))
                        for i, estimate in zip(valid, p):
                            record = rows[i]
                            connection.execute('insert into inner_predictions values(?,?,?,?,?,?,?)',
                                (outer_no, inner_no, spec['id'], record['endpoint_id'], record['source_group'], record['retention_pct'], float(estimate)))
                            by_candidate[spec['id']].append((record['source_group'], abs(float(estimate) - record['retention_pct'])))
                        state['warnings'].extend({'variant': spec['id'], 'fold': outer_no, 'inner_fold': inner_no, **w} for w in audit['warnings'])
                        task('inner', outer_no, spec['id'])
                    connection.commit()
                scores = []
                for cid, errors in by_candidate.items():
                    grouped = collections.defaultdict(list)
                    for group, error in errors:
                        grouped[group].append(error)
                    source_errors = {g: statistics.fmean(v) for g, v in grouped.items()}
                    if len(source_errors) != 22:
                        raise ValueError('Inner source coverage incomplete.')
                    scores.append({'candidate': cid, 'mae': statistics.fmean(source_errors.values()),
                                   'source_error_se': statistics.stdev(source_errors.values()) / math.sqrt(len(source_errors)),
                                   'source_errors': source_errors})
                chosen, threshold = select(scores, plan['candidates'])
                decision = {'outer_fold': outer_no, 'outer_train_indices': outer['train'], 'outer_test_indices': outer['test'],
                            'heldout_sources': sorted({rows[i]['source_group'] for i in outer['test']}),
                            'scores': scores, 'chosen': chosen, 'one_se_cutoff': threshold}
                outer_cache = {}
                for policy, cid in chosen.items():
                    state['active'] = {'phase': 'outer_validation', 'fold': outer_no, 'total_folds': 23, 'variant': policy}
                    spec = next(s for s in plan['candidates'] if s['id'] == cid)
                    if cid not in outer_cache:
                        prepared = prepare(rows, outer['train'], outer['test'], spec)
                        estimate, audit = fit_predict(prepared, spec)
                        fitted += int(audit['estimator_fitted'])
                        audit.update(schema=prepared['schema'], target_center=prepared['target_center'], target_scale=prepared['target_scale'],
                                     train_weights=prepared['weights'].tolist())
                        connection.execute('insert into outer_fit_audit values(?,?,?)', (outer_no, cid, json.dumps(audit)))
                        outer_cache[cid] = estimate
                        state['warnings'].extend({'variant': cid, 'fold': outer_no, 'phase': 'outer', **w} for w in audit['warnings'])
                    for i, estimate in zip(outer['test'], outer_cache[cid]):
                        r = rows[i]
                        predictions.append({'variant': policy, 'candidate': cid, 'fold': outer_no, 'endpoint_id': r['endpoint_id'],
                                            'sample_name': r['sample_name'], 'source_group': r['source_group'], 'observed': r['retention_pct'],
                                            'predicted': float(estimate), 'residual': float(estimate) - r['retention_pct'],
                                            'prediction_origin': 'inner_selected_outer_heldout'})
                    next(m for m in state['models'] if m['variant'] == policy)['completed'] += 1
                    task('outer', outer_no, policy)
                decisions.append(decision)
                connection.execute('insert into selections values(?,?)', (outer_no, json.dumps(decision)))
                connection.commit()
                state['metrics'] = summary(predictions)
                progress(True)
                print(json.dumps({'outer_fold_complete': outer_no, 'completed': state['completed'], 'total': state['total'], 'chosen': chosen}), flush=True)
        if sha(OUT / 'training_plan.json') != plan_hash:
            raise ValueError('Plan changed during execution.')
        connection.close()
        write(OUT / 'predictions.json', predictions)
        write(OUT / 'decisions.json', decisions)
        write(OUT / 'results.json', {'complete': True, 'plan_sha256': plan_hash, 'dataset_fingerprint': ds.fingerprint(),
              'actual_estimator_fits': fitted, 'evaluation_tasks': state['completed'], 'metrics': summary(predictions),
              'warning_count': len(state['warnings']), 'fresh_external_test': False, 'all_original_sources_kept': True})
        state.update(status='complete', active=None, metrics=summary(predictions))
        progress(True)
    except BaseException as exc:
        connection.commit()
        connection.close()
        state.update(status='failed', error=type(exc).__name__ + ': ' + str(exc))
        progress(True)
        raise


if __name__ == '__main__':
    main()
