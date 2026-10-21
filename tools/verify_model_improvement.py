"""Independent audit of inner selections and untouched outer-source predictions; no fits."""
from pathlib import Path
import collections
import hashlib
import json
import math
import sqlite3
import statistics
import sys
import numpy as np
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from data.cycling_db import open_database
from train_initial_baselines import read, write, sha

OUT = ROOT / '模型诊断与改进_20261021'


def verify():
    checks = []

    def check(name, ok):
        if not ok:
            raise AssertionError(name)
        checks.append(name)

    plan, result = read(OUT / 'training_plan.json'), read(OUT / 'results.json')
    pred, progress = read(OUT / 'predictions.json'), read(OUT / 'progress.json')
    specs = {s['id']: s for s in plan['candidates']}
    check('plan_frozen', sha(OUT / 'training_plan.json') == result['plan_sha256'])
    check('bounded_candidates', len(specs) == 23 and plan['authorization']['authorized'])
    check('completed_2714_tasks', progress['completed'] == progress['total'] == 2714 and progress['status'] == 'complete')
    check('true_event_counts', [e['completed'] for e in progress['events']] == list(range(1, 2715)))
    check('event_time_monotonic', all(a['seconds'] <= b['seconds'] for a, b in zip(progress['events'], progress['events'][1:])))
    check('no_clipping_or_row_removal', result['all_original_sources_kept'])
    with open_database() as db:
        ds = db.fetch()
        check('stable_dataset', ds.fingerprint() == result['dataset_fingerprint'] == plan['dataset_fingerprint'])
    rows = ds.rows
    by_id = {r['endpoint_id']: r for r in rows}
    c = sqlite3.connect((OUT / 'evaluation.sqlite').as_uri() + '?mode=ro', uri=True)
    c.row_factory = sqlite3.Row
    check('sqlite_integrity', c.execute('pragma integrity_check').fetchone()[0] == 'ok')
    check('sqlite_foreign_keys', not c.execute('pragma foreign_key_check').fetchall())
    check('inner_fit_tasks', c.execute('select count(*) from inner_fit_audit').fetchone()[0] == 2645)
    check('inner_prediction_count', c.execute('select count(*) from inner_predictions').fetchone()[0] == 15686)
    expected_fits = 0
    warning_count = 0
    for outer_no, outer in enumerate(ds.source_folds(23), 1):
        decision = json.loads(c.execute('select decision_json from selections where outer_fold=?', (outer_no,)).fetchone()[0])
        check('outer_plan:' + str(outer_no), outer['train'] == decision['outer_train_indices'] and outer['test'] == decision['outer_test_indices'])
        validated = []
        for split_row in c.execute('select * from split_audit where outer_fold=? order by inner_fold', (outer_no,)):
            split = json.loads(split_row['split_json'])
            tr, va = split['train'], split['test']
            check('inner_partition:' + str(outer_no) + ':' + str(split_row['inner_fold']),
                  set(tr) | set(va) == set(outer['train']) and not set(tr) & set(va)
                  and not (set(tr) | set(va)) & set(outer['test'])
                  and {rows[i]['source_group'] for i in tr}.isdisjoint({rows[i]['source_group'] for i in va}))
            validated.extend(va)
            for prep in c.execute('select * from preprocessing where outer_fold=? and inner_fold=?', (outer_no, split_row['inner_fold'])):
                schema = json.loads(prep['schema_json'])
                source_values = collections.defaultdict(list)
                for s in schema:
                    if s['kind'] == 'categorical':
                        check('category_vocabulary:' + str((outer_no, split_row['inner_fold'], prep['transform_key'], s['field'])),
                              s['vocabulary'] == sorted({rows[i][s['field']] for i in tr}))
                    else:
                        grouped = collections.defaultdict(list)
                        for i in tr:
                            value = rows[i][s['field']]
                            grouped[rows[i]['source_group']].append(math.log10(value) if s['log10'] else value)
                        mean = statistics.fmean(statistics.fmean(v) for v in grouped.values())
                        variance = statistics.fmean(statistics.fmean((x - mean) ** 2 for x in v) for v in grouped.values())
                        scale = math.sqrt(variance) or 1.
                        check('source_equal_scaler:' + str((outer_no, split_row['inner_fold'], prep['transform_key'], s['field'])),
                              abs(mean - s['mean']) < 1e-8 and abs(scale - s['scale']) < 1e-8)
        check('all_inner_training_records_held_once:' + str(outer_no), sorted(validated) == sorted(outer['train']))
        rescored = []
        for cid in specs:
            inner = list(c.execute('select * from inner_predictions where outer_fold=? and candidate=?', (outer_no, cid)))
            check('inner_predictions_use_training_only:' + str(outer_no) + ':' + cid,
                  {r['endpoint_id'] for r in inner} == {rows[i]['endpoint_id'] for i in outer['train']}
                  and all(r['observed'] == by_id[r['endpoint_id']]['retention_pct'] for r in inner))
            grouped = collections.defaultdict(list)
            for r in inner:
                grouped[r['source_group']].append(abs(r['observed'] - r['predicted']))
            errors = {g: statistics.fmean(v) for g, v in grouped.items()}
            score = statistics.fmean(errors.values())
            se = statistics.stdev(errors.values()) / math.sqrt(len(errors))
            saved = next(s for s in decision['scores'] if s['candidate'] == cid)
            check('inner_source_MAE:' + str(outer_no) + ':' + cid, abs(score - saved['mae']) < 1e-10 and abs(se - saved['source_error_se']) < 1e-10)
            rescored.append({'candidate': cid, 'mae': score, 'se': se})
        ranked = sorted(rescored, key=lambda x: (x['mae'], specs[x['candidate']]['complexity'], x['candidate']))
        cutoff = ranked[0]['mae'] + ranked[0]['se']
        simple = min([r for r in ranked if r['mae'] <= cutoff], key=lambda x: (specs[x['candidate']]['complexity'], x['mae'], x['candidate']))
        linear = next(r for r in ranked if specs[r['candidate']]['kind'] in ['mean', 'median', 'ridge'])
        chosen = {'nested_min': ranked[0]['candidate'], 'nested_1se': simple['candidate'], 'nested_linear': linear['candidate']}
        check('independent_selection_rules:' + str(outer_no), chosen == decision['chosen'])
        check('only_selected_outer_fits:' + str(outer_no), {r['candidate'] for r in c.execute('select candidate from outer_fit_audit where outer_fold=?', (outer_no,))} == set(chosen.values()))
        for policy, cid in chosen.items():
            own = [r for r in pred if r['variant'] == policy and r['fold'] == outer_no]
            check('outer_test_ids:' + str(outer_no) + ':' + policy,
                  {r['endpoint_id'] for r in own} == {rows[i]['endpoint_id'] for i in outer['test']}
                  and all(r['candidate'] == cid and r['observed'] == by_id[r['endpoint_id']]['retention_pct'] for r in own))
    for table in ['inner_fit_audit', 'outer_fit_audit']:
        for r in c.execute('select fit_json from ' + table):
            audit = json.loads(r[0])
            expected_fits += int(audit['estimator_fitted'])
            warning_count += len(audit['warnings'])
    check('true_fit_counter', result['actual_estimator_fits'] == expected_fits == 2451)
    check('warnings_complete', result['warning_count'] == warning_count == len(progress['warnings']))
    old = read(ROOT / plan['prior_run'] / 'predictions.json')
    old_map = {(r['variant'], r['endpoint_id']): r for r in old}
    for variant in {r['variant'] for r in pred}:
        own = [r for r in pred if r['variant'] == variant]
        check('one_prediction_per_record:' + variant, len(own) == 31 and len({r['endpoint_id'] for r in own}) == 31)
        w = [1 / sum(x['source_group'] == r['source_group'] for x in own) for r in own]
        y, p = [r['observed'] for r in own], [r['predicted'] for r in own]
        m = next(x for x in result['metrics'] if x['variant'] == variant)
        check('independent_outer_metrics:' + variant, abs(m['mae'] - mean_absolute_error(y, p, sample_weight=w)) < 1e-10
              and abs(m['rmse'] - math.sqrt(mean_squared_error(y, p, sample_weight=w))) < 1e-10
              and abs(m['r2'] - r2_score(y, p, sample_weight=w)) < 1e-10)
        if variant in ['mean/full', 'previous_mlp_full', 'previous_mlp_no_current']:
            old_name = {'previous_mlp_full': 'MLP/full', 'previous_mlp_no_current': 'MLP/no_current'}.get(variant, variant)
            check('previous_predictions_preserved:' + variant, all(r['predicted'] == old_map[old_name, r['endpoint_id']]['predicted'] for r in own))
    for item in read(ROOT / plan['prior_run'] / 'run_manifest.json')['outputs']:
        check('previous_experiment_payload:' + item['path'], sha(ROOT / item['path']) == item['sha256'])
    pointer = read(ROOT / 'data/current_database.json')
    check('database_pointer_unchanged', pointer == plan['data_pointer'])
    for item in read(ROOT / pointer['version_directory'] / 'merge_manifest.json')['outputs']:
        check('sealed_data_payload:' + item['path'], sha(ROOT / item['path']) == item['sha256'])
    check('not_misrepresented_external_test', result['fresh_external_test'] is False)
    c.close()
    return {'passed': True, 'check_count': len(checks), 'inner_prediction_rows': 15686,
            'inner_tasks': 2645, 'outer_prediction_tasks': 69, 'actual_estimator_fits': expected_fits,
            'old_experiment_and_data_unchanged': True, 'independent_selection_and_metrics_verified': True, 'checks': checks}


if __name__ == '__main__':
    report = verify()
    write(OUT / 'verification.json', report)
    print(json.dumps({k: v for k, v in report.items() if k != 'checks'}, ensure_ascii=False, indent=2))
