"""Execute one frozen v1.0 run, with source-safe selection and resumable actual progress."""
from pathlib import Path
from collections import defaultdict
import argparse
import datetime
import hashlib
import importlib.metadata
import json
import math
import sqlite3
import sys
import time
import traceback
import warnings

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from models.v1_0.model import RetentionModel, metrics, weights


def read(path):
    return json.loads(path.read_text('utf-8'))


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def now():
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(timespec='seconds')


def write(path, value):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    for attempt in range(40):
        try:
            temporary.replace(path)
            return
        except PermissionError:
            if attempt == 39:
                raise
            time.sleep(.03)


def job_result(key, stage, spec, records, train, test):
    from threadpoolctl import threadpool_limits
    tr, te = [records[i] for i in train], [records[i] for i in test]
    assert not {r['source_group'] for r in tr} & {r['source_group'] for r in te}
    tick = time.monotonic()
    with warnings.catch_warnings(record=True) as caught, threadpool_limits(limits=1):
        model = RetentionModel(spec).fit(tr)
        prediction = model.predict(te)
    if not all(math.isfinite(p) for p in prediction):
        raise ValueError('Nonfinite model prediction.')
    result = {'key': key, 'stage': stage, 'candidate': spec['id'], 'train_indices': train,
        'test_indices': test, 'train_sources': model.training_sources,
        'test_sources': sorted({r['source_group'] for r in te}),
        'schema': model.encoder.schema if model.encoder else [],
        'target_center': model.center, 'target_scale': model.scale,
        'estimator_fits': model.estimator_fit_count, 'seconds': time.monotonic() - tick,
        'warnings': [str(w.message) for w in caught],
        'predictions': [{'index': i, 'endpoint_id': r['endpoint_id'], 'sample_name': r['sample_name'],
                         'source_group': r['source_group'], 'observed': r['retention_pct'],
                         'predicted': float(p), 'warnings': model.encoder.warnings(r) if model.encoder else []}
                        for i, r, p in zip(test, te, prediction)],
        'kernel_gamma': getattr(model, 'kernel_gamma', None)}
    return result, model


def bootstrap(rows, baseline, seed=20261022):
    import numpy as np
    grouped = defaultdict(list)
    by_endpoint = {r['endpoint_id']: r for r in baseline}
    for row in rows:
        error = abs(row['predicted'] - row['observed'])
        base = by_endpoint[row['endpoint_id']]
        grouped[row['source_group']].append((error, error - abs(base['predicted'] - base['observed'])))
    errors = np.array([np.mean(value, axis=0) for _, value in sorted(grouped.items())])
    sampled = np.random.default_rng(seed).integers(0, len(errors), (5000, len(errors)))
    averages = errors[sampled].mean(axis=1)
    bounds = np.quantile(averages, [.025, .975], axis=0)
    return {'mae_ci_low': float(bounds[0, 0]), 'mae_ci_high': float(bounds[1, 0]),
            'delta_mae': float(errors[:, 1].mean()), 'delta_ci_low': float(bounds[0, 1]),
            'delta_ci_high': float(bounds[1, 1]),
            'method': '5000 paired source-bootstrap resamples; descriptive95%, no refit;7sources only'}


def run(folder, resume=False):
    import joblib
    folder = folder.resolve()
    if ROOT not in folder.parents or (folder / 'results.json').exists():
        raise ValueError('New planned folder required; completed runs cannot be overwritten.')
    plan = read(folder / 'training_plan.json')
    if not plan['authorization']['authorized'] or plan['model_version'] != '1.0':
        raise ValueError('Explicit new v1.0 authorization required.')
    if read(ROOT / 'data/current_database.json') != plan['database_pointer']:
        raise ValueError('Database pointer changed since planning.')
    if sha(folder / 'data_snapshot.json') != plan['snapshot_sha256']:
        raise ValueError('Snapshot was changed.')
    for path, digest in read(folder / 'protected_inputs.json').items():
        if sha(ROOT / path) != digest:
            raise ValueError('Protected input changed: ' + path)
    records = read(folder / 'data_snapshot.json')['records']
    code_paths = ['tools/train_model_v1.py', 'tools/prepare_model_v1.py', 'models/v1_0/model.py']
    seal = {p: sha(ROOT / p) for p in code_paths}
    seal.update(training_plan=sha(folder / 'training_plan.json'), snapshot=sha(folder / 'data_snapshot.json'))
    if (folder / 'frozen_run_hashes.json').exists():
        if not resume or read(folder / 'frozen_run_hashes.json') != seal:
            raise ValueError('Use resume only with the original frozen code, plan and snapshot.')
    else:
        write(folder / 'frozen_run_hashes.json', seal)
    checkpoint = sqlite3.connect(folder / 'evaluation.sqlite')
    checkpoint.execute('CREATE TABLE IF NOT EXISTS jobs(key TEXT PRIMARY KEY, payload TEXT NOT NULL)')
    checkpoint.commit()
    done = {key: json.loads(payload) for key, payload in checkpoint.execute('SELECT key,payload FROM jobs ORDER BY rowid')}
    previous = read(folder / 'progress.json')
    elapsed_before = previous.get('elapsed_seconds', 0) if resume else 0
    started = time.monotonic()
    state = {**previous, 'status': 'running', 'started_at': previous.get('started_at', now()),
             'plan_sha256': seal['training_plan'], 'actual_estimator_fits': sum(j['estimator_fits'] for j in done.values()),
             'completed': len(done), 'total': plan['planned_jobs']}
    specs = {s['id']: s for s in plan['candidates']}
    write(folder / 'environment.json', {'python': sys.version, 'runtime': str(Path(sys.executable).relative_to(ROOT)),
          'versions': {n: importlib.metadata.version(n) for n in ['numpy','scipy','scikit-learn','joblib','threadpoolctl']},
          'shared_dependencies_modified': False, 'threads': 1})

    def update():
        state['elapsed_seconds'] = round(elapsed_before + time.monotonic() - started, 4)
        state['updated_at'] = now()
        state['percent'] = 100 * state['completed'] / state['total']
        write(folder / 'progress.json', state)

    def commit(result):
        checkpoint.execute('INSERT INTO jobs VALUES(?,?)', (result['key'], json.dumps(result, ensure_ascii=False, allow_nan=False)))
        checkpoint.commit()
        done[result['key']] = result
        state['completed'] = len(done)
        state['actual_estimator_fits'] = sum(j['estimator_fits'] for j in done.values())
        state.setdefault('events', []).append({'seconds': round(elapsed_before + time.monotonic() - started, 4),
             'completed': len(done), 'fits': state['actual_estimator_fits']})
        update()

    try:
        update()
        for spec in plan['candidates']:
            for split in plan['development_folds']:
                key = 'cv/' + spec['id'] + '/' + str(split['fold'])
                if key in done:
                    continue
                state['active'] = {'stage': 'development', 'candidate': spec['id'], 'fold': split['fold']}
                result, _ = job_result(key, 'development', spec, records, split['train'], split['test'])
                commit(result)
            predictions = [r for j in done.values() if j['stage'] == 'development' and j['candidate'] == spec['id'] for r in j['predictions']]
            performance = metrics([records[r['index']] for r in predictions], [r['predicted'] for r in predictions])
            row = {'candidate': spec['id'], 'block': spec['block'], 'current': spec['current'],
                   'eligible': spec['eligible_for_selection'], **performance}
            state['candidates'] = [r for r in state.get('candidates', []) if r['candidate'] != spec['id']] + [row]
            update()
        selectable = [r for r in state['candidates'] if r['eligible']]
        best = min(r['mae'] for r in selectable)
        selected_id = next(s['id'] for s in plan['candidates'] if s['eligible_for_selection'] and
                           next(r['mae'] for r in selectable if r['candidate'] == s['id']) <= best + 1e-10)
        selection = {'selected_id': selected_id, 'specification': specs[selected_id],
                     'development_scores': state['candidates'], 'frozen_at': now(),
                     'reserved_results_read_during_selection': False,
                     'plan_sha256': seal['training_plan'], 'rule': plan['selection']}
        selected_path = folder / 'selected.json'
        if selected_path.exists():
            if read(selected_path)['selected_id'] != selected_id:
                raise ValueError('A resumed selection changed.')
        else:
            write(selected_path, selection)
        write(folder / 'development_predictions.json', [r | {'candidate': j['candidate']}
              for j in done.values() if j['stage'] == 'development' for r in j['predictions']])
        state['selected_id'] = selected_id
        # No reserved labels, scores or predictions were used above this boundary.
        reserved_models = {}
        for slot in plan['reserved_evaluation_slots']:
            key = 'reserved/' + slot
            candidate_id = selected_id if slot == 'selected' else slot
            if key in done:
                continue
            state['active'] = {'stage': 'reserved_source_test', 'candidate': candidate_id, 'slot': slot}
            if candidate_id in reserved_models:
                original, fitted = reserved_models[candidate_id]
                result = dict(original, key=key, estimator_fits=0, reused_fit=original['key'])
            else:
                result, fitted = job_result(key, 'reserved_source_test', specs[candidate_id], records,
                    plan['development_indices'], plan['reserved_source_test_indices'])
                reserved_models[candidate_id] = (result, fitted)
            if slot == 'selected':
                joblib.dump(fitted, folder / 'evaluated_development_model.joblib', compress=3)
                write(folder / 'evaluated_model_schema.json', fitted.encoder.schema if fitted.encoder else [])
            commit(result)
        reserved = []
        for slot in plan['reserved_evaluation_slots']:
            reserved.extend(r | {'variant': slot, 'candidate': done['reserved/' + slot]['candidate']}
                            for r in done['reserved/' + slot]['predictions'])
        mean_rows = [r for r in reserved if r['variant'] == 'source_mean']
        legacy_rows = [r for r in reserved if r['variant'] == 'legacy_mlp_noI']
        scores = []
        for slot in plan['reserved_evaluation_slots']:
            rows = [r for r in reserved if r['variant'] == slot]
            scores.append({'variant': slot, 'candidate': done['reserved/' + slot]['candidate'],
                'rows': len(rows), 'sources': len({r['source_group'] for r in rows}),
                **metrics([records[r['index']] for r in rows], [r['predicted'] for r in rows]),
                'vs_mean': bootstrap(rows, mean_rows), 'vs_legacy': bootstrap(rows, legacy_rows)})
        state['metrics'], state['predictions'] = scores, reserved
        update()
        final_key = 'final/all_admitted'
        if final_key not in done:
            from threadpoolctl import threadpool_limits
            state['active'] = {'stage': 'final_all_data_refit', 'candidate': selected_id}
            tick = time.monotonic()
            with warnings.catch_warnings(record=True) as caught, threadpool_limits(limits=1):
                final = RetentionModel(specs[selected_id]).fit(records)
            joblib.dump(final, folder / 'model_v1_0.joblib', compress=3)
            write(folder / 'model_schema.json', final.encoder.schema if final.encoder else [])
            write(folder / 'inference_example.json', [{k: v for k, v in records[plan['reserved_source_test_indices'][0]].items()
                if k in ['system','method'] + plan['feature_encoding']['core'] + plan['feature_encoding']['material']}])
            # Training predictions are kept explicitly separate and carry no validation claim.
            write(folder / 'training_resubstitution.json', {'not_generalization': True,
                'metrics': metrics(records, final.predict(records)),
                'predictions': [{'endpoint_id': r['endpoint_id'], 'observed': r['retention_pct'], 'predicted': float(p)}
                                for r, p in zip(records, final.predict(records))]})
            commit({'key': final_key, 'stage': 'final_all_data_refit', 'candidate': selected_id,
                'train_indices': list(range(len(records))), 'test_indices': [],
                'train_sources': final.training_sources, 'test_sources': [],
                'schema': final.encoder.schema if final.encoder else [], 'predictions': [],
                'warnings': [str(w.message) for w in caught], 'estimator_fits': final.estimator_fit_count,
                'seconds': time.monotonic() - tick})
        write(folder / 'reserved_predictions.json', reserved)
        primary = next(r for r in scores if r['variant'] == 'selected')
        results = {'selected_id': selected_id, 'selection': selection, 'reserved_metrics': scores,
            'development_rows': 35, 'development_sources': 23, 'reserved_rows': 7, 'reserved_sources': 7,
            'all_data_refit_rows': 42, 'all_data_refit_sources': 30,
            'actual_estimator_fits': state['actual_estimator_fits'], 'completed_jobs': len(done),
            'warnings': [{'key': j['key'], 'messages': j['warnings']} for j in done.values() if j['warnings']],
            'beats_reserved_mean': primary['vs_mean']['delta_mae'] < 0,
            'beats_reserved_legacy': primary['vs_legacy']['delta_mae'] < 0,
            'statistically_clear_gain_vs_mean': primary['vs_mean']['delta_ci_high'] < 0,
            'statistically_clear_gain_vs_legacy': primary['vs_legacy']['delta_ci_high'] < 0,
            'status': 'exploratory_only', 'limits': [plan['holdout_limits'],
                '7-source test is small; bootstrap intervals are descriptive and conditional.',
                'The42-row refit has no independent generalization test; scores above evaluate the35-row model.',
                'No calibrated per-sample prediction intervals; no automatic extrapolation approval.']}
        assert len(done) == plan['planned_jobs'] and state['actual_estimator_fits'] <= plan['maximum_estimator_fits']
        state.update(status='complete', active=None)
        update()
        results['elapsed_seconds'] = state['elapsed_seconds']
        write(folder / 'results.json', results)
        print(json.dumps({'selected': selected_id, 'reserved': scores, 'fits': state['actual_estimator_fits'],
                          'warnings': len(results['warnings']), 'seconds': state['elapsed_seconds']}, ensure_ascii=False))
    except Exception:
        state.update(status='failed', error=traceback.format_exc())
        update()
        raise
    finally:
        checkpoint.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--resume', action='store_true')
    args = parser.parse_args()
    run(args.run_dir, args.resume)
