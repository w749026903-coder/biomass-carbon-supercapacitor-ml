"""Verify saved real grouped evaluation without repeating any fitted model."""
from pathlib import Path
import argparse
import collections
import hashlib
import importlib.util
import json
import math
import statistics
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from data.cycling_db import open_database
from tools.training_input_quality import prepare_source_fold
from tools.train_initial_baselines import write, weighted_metrics, summarize


def read(p):
    return json.loads(p.read_text('utf-8'))


def verify(folder):
    import numpy as np
    from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
    checks = []

    def check(name, value):
        if not value:
            raise AssertionError(name)
        checks.append(name)

    plan = read(folder / 'training_plan.json')
    result = read(folder / 'results.json')
    pred = read(folder / 'predictions.json')
    audit = read(folder / 'fold_audit.json')
    progress = read(folder / 'progress.json')
    check('explicit_user_authorization', plan['authorization']['authorized'] is True)
    check('frozen_plan_hash', hashlib.sha256((folder / 'training_plan.json').read_bytes()).hexdigest() == result['plan_sha256'])
    check('task_fit_counts', len(audit) == 161 and result['actual_estimator_fits'] == 138
          and result['mean_reference_calculations'] == 23)
    check('progress_completion', progress['status'] == 'complete' and progress['completed'] == progress['total'] == 161)
    check('no_duplicated_task', len({(a['variant'], a['fold']) for a in audit}) == 161)
    check('true_progress_events', [e['completed'] for e in progress['events']] == list(range(1, 162))
          and all(a['seconds'] <= b['seconds'] for a, b in zip(progress['events'], progress['events'][1:])))
    check('predictions_complete', len(pred) == 217 and progress['predictions'] == pred)
    check('checkpoint_preserved', audit[:154] == read(folder / 'partial_fold_audit.json'))
    check('recovery_record', read(folder / 'attempt_01_failure.json')['completed'] == 154)
    # Regression for the real Windows read/rename race, without a second training run.
    import tempfile
    with tempfile.TemporaryDirectory(dir=folder) as tmp:
        path = Path(tmp) / 'atomic_probe.json'
        original = Path.replace
        attempts = []

        def intermittent(src, dst):
            attempts.append(1)
            if len(attempts) <= 2:
                raise PermissionError('injected reader sharing conflict')
            return original(src, dst)

        with patch.object(Path, 'replace', intermittent):
            write(path, {'retained': True})
        check('atomic_write_retry', len(attempts) == 3 and read(path) == {'retained': True})
    with open_database() as db:
        ds = db.fetch('reported_3e')
        check('database_snapshot_unchanged', ds.rows == read(folder / 'data_snapshot.json')['rows']
              and ds.fingerprint() == result['dataset_fingerprint'])
        folds = ds.source_folds(23)
        for a in audit:
            key = a['variant'] + ':' + str(a['fold'])
            split = folds[a['fold'] - 1]
            expected = prepare_source_fold(ds, split, a['variant'].endswith('/no_current'))
            check('train_ids:' + key, a['train_endpoint_ids'] == [ds.rows[i]['endpoint_id'] for i in split['train']])
            check('heldout_ids:' + key, a['test_endpoint_ids'] == [ds.rows[i]['endpoint_id'] for i in split['test']])
            check('whole_source_split:' + key, set(a['training_source_groups']).isdisjoint(a['heldout_source_groups']))
            check('fold_only_schema:' + key, a['training_only_schema'] == expected['training_only_schema'])
            w = a['train_fit_weights']
            rowgroups = [ds.rows[i]['source_group'] for i in split['train']]
            totals = [sum(x for x, g in zip(w, rowgroups) if g == group) for group in set(rowgroups)]
            check('equal_source_train_weight:' + key, max(totals) - min(totals) < 1e-10)
            model = a['variant'].split('/')[0]
            check('target_not_in_features:' + key, 'retention_pct' not in a['feature_names'])
            if model == 'MLP':
                y = [ds.rows[i]['retention_pct'] for i in split['train']]
                mean = float(np.average(y, weights=w))
                scale = math.sqrt(float(np.average((np.asarray(y) - mean) ** 2, weights=w))) or 1
                check('training_only_target_scale:' + key, abs(mean - a['target_center']) < 1e-12 and abs(scale - a['target_scale']) < 1e-12)
            if a['variant'].endswith('no_current'):
                check('current_removed:' + key, 'reported_current_A_g' not in a['feature_names'])
        for variant in dict.fromkeys(r['variant'] for r in pred):
            own = [r for r in pred if r['variant'] == variant]
            check('one_OOF_per_record:' + variant, len(own) == 31 and len({r['endpoint_id'] for r in own}) == 31)
            weights = [1 / sum(x['source_group'] == r['source_group'] for x in own) for r in own]
            observed = [r['observed'] for r in own]
            predicted = [r['predicted'] for r in own]
            score = next(r for r in result['metrics'] if r['variant'] == variant)
            check('independent_MAE:' + variant, abs(score['mae'] - mean_absolute_error(observed, predicted, sample_weight=weights)) < 1e-10)
            check('independent_RMSE:' + variant, abs(score['rmse'] - math.sqrt(mean_squared_error(observed, predicted, sample_weight=weights))) < 1e-10)
            check('independent_R2:' + variant, abs(score['r2'] - r2_score(observed, predicted, sample_weight=weights)) < 1e-10)
            check('labels_not_clipped:' + variant, sorted(observed) == sorted(r['retention_pct'] for r in ds.rows))
            if variant == 'mean/full':
                for r in own:
                    a = next(a for a in audit if a['variant'] == variant and a['fold'] == r['fold'])
                    ids = {x: i for i, x in enumerate([row['endpoint_id'] for row in ds.rows])}
                    values = [ds.rows[ids[key]]['retention_pct'] for key in a['train_endpoint_ids']]
                    check('baseline_from_training_only:' + r['endpoint_id'], abs(r['predicted'] - np.average(values, weights=a['train_fit_weights'])) < 1e-10)
        check('bootstrap_reproducible', summarize(pred, audit) == result['metrics'])
        # Verify every immutable scientific payload in v0.10 and the prior parent pointers.
        pointer = read(ROOT / 'data/current_database.json')
        manifest = read(ROOT / pointer['version_directory'] / 'merge_manifest.json')
        for item in manifest['outputs']:
            check('sealed_data_payload:' + item['path'], hashlib.sha256((ROOT / item['path']).read_bytes()).hexdigest() == item['sha256'])
    check('fixed_parameters_and_no_outer_selection', not result['hyperparameter_search'] and not result['final_all_data_refit'])
    check('warnings_reconcile', result['warning_count'] == len(progress['warnings']) == sum(len(a['warnings']) for a in audit))
    return {'all_checks_passed': True, 'check_count': len(checks), 'actual_estimator_fits': 138,
            'evaluation_tasks': 161, 'prediction_rows': 217, 'model_variants': 7, 'source_groups': 23,
            'data_versions_unchanged': True, 'metrics_recomputed_independently': True,
            'resume_without_refitting_completed_tasks': True, 'checks': checks}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run-dir', type=Path, required=True)
    args = p.parse_args()
    report = verify(args.run_dir)
    write(args.run_dir / 'verification.json', report)
    print(json.dumps({k: v for k, v in report.items() if k != 'checks'}, ensure_ascii=False, indent=2))
