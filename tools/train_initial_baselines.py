"""Authorized, fixed-parameter source-grouped baseline experiment; no model publication."""
from pathlib import Path
import argparse
import collections
import datetime
import hashlib
import importlib.metadata
import json
import math
import statistics
import sys
import time
import traceback
import warnings

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from data.cycling_db import open_database
from tools.training_input_quality import assess, prepare_source_fold


def read(p):
    return json.loads(p.read_text('utf-8'))


def write(p, value):
    tmp = p.with_suffix(p.suffix + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', 'utf-8')
    # A Windows HTTP reader may briefly hold the destination without delete sharing.
    # Retry only the atomic commit, not a completed fit or a partial JSON write.
    for attempt in range(30):
        try:
            tmp.replace(p)
            break
        except PermissionError:
            if attempt == 29:
                raise
            time.sleep(0.03)


def sha(p):
    with p.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def now():
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(timespec='seconds')


def weighted_metrics(y, p, w):
    import numpy as np
    y, p, w = map(lambda x: np.asarray(x, dtype=float), (y, p, w))
    error = p - y
    mse = float(np.average(error ** 2, weights=w))
    variance = float(np.average((y - np.average(y, weights=w)) ** 2, weights=w))
    return {'mae': float(np.average(np.abs(error), weights=w)), 'rmse': math.sqrt(mse),
            'r2': 1 - mse / variance if len(y) >= 2 and variance > 0 else None}


def summarize(predictions, audits):
    import numpy as np
    baseline = {r['endpoint_id']: r for r in predictions if r['variant'] == 'mean/full'}
    output = []
    for variant in dict.fromkeys(r['variant'] for r in predictions):
        rows = [r for r in predictions if r['variant'] == variant]
        weights = [1 / sum(x['source_group'] == r['source_group'] for x in rows) for r in rows]
        metrics = weighted_metrics([r['observed'] for r in rows], [r['predicted'] for r in rows], weights)
        grouped = collections.defaultdict(list)
        for r in rows:
            grouped[r['source_group']].append(r)
        group_errors = [statistics.fmean(abs(r['predicted'] - r['observed']) for r in rs) for rs in grouped.values()]
        rng = np.random.default_rng(20261021)
        indexes = rng.integers(0, len(group_errors), (2000, len(group_errors)))
        boot = np.asarray(group_errors)[indexes].mean(axis=1)
        lo, hi = map(float, np.quantile(boot, [0.025, 0.975]))
        diffs = [statistics.fmean(abs(r['predicted'] - r['observed']) -
                 abs(baseline[r['endpoint_id']]['predicted'] - r['observed']) for r in rs) for rs in grouped.values()]
        dboot = np.asarray(diffs)[indexes].mean(axis=1)
        dlo, dhi = map(float, np.quantile(dboot, [0.025, 0.975]))
        own_audit = [a for a in audits if a['variant'] == variant]
        output.append({'variant': variant, **metrics, 'mae_ci_low': lo, 'mae_ci_high': hi,
                       'delta_mae_vs_mean': statistics.fmean(diffs), 'delta_ci_low': dlo, 'delta_ci_high': dhi,
                       'train_mae': statistics.fmean(a['train_metrics']['mae'] for a in own_audit),
                       'folds': len(own_audit), 'rows': len(rows), 'source_groups': len(grouped),
                       'warning_folds': sum(bool(a['warnings']) for a in own_audit),
                       'training_seconds': sum(a['fit_seconds'] for a in own_audit),
                       'ci_method': '95% descriptive source-group bootstrap, 2000 resamples; no refitting'})
    return output


def run(folder, resume=False):
    import numpy as np
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.neural_network import MLPRegressor
    from xgboost import XGBRegressor
    from threadpoolctl import threadpool_limits

    folder = folder.resolve()
    if ROOT not in folder.parents or (folder / 'results.json').exists():
        raise ValueError('Use a new authorized run folder inside this project; never overwrite completed experiments.')
    plan = read(folder / 'training_plan.json')
    if not plan['authorization']['authorized'] or plan['profile'] != 'reported_3e' or plan['hyperparameter_search']:
        raise ValueError('Explicit bounded initial-run authorization required.')
    if read(ROOT / 'data/current_database.json') != plan['database_pointer']:
        raise ValueError('Dataset pointer changed after the plan was frozen.')
    plan_hash = sha(folder / 'training_plan.json')
    with open_database() as db:
        ds = db.fetch(plan['profile'])
        if ds.fingerprint() != plan['dataset_fingerprint']:
            raise ValueError('Dataset fingerprint changed.')
        quality = assess(ds)
    snapshot = read(folder / 'data_snapshot.json')
    if ds.rows != snapshot['rows'] or ds.feature_matrix() != snapshot['matrix']:
        raise ValueError('Snapshot does not match the immutable database.')
    folds = ds.source_folds(plan['source_groups'])
    if snapshot['source_folds'] != folds:
        raise ValueError('Source fold plan changed.')
    saved = read(folder / 'progress.json') if resume else None
    if saved and saved['status'] not in ['failed', 'interrupted']:
        raise ValueError('Only a failed/interrupted attempt can be resumed.')
    elapsed_before = saved['elapsed_seconds'] if saved else 0
    start = time.monotonic()
    state = {'run_id': plan['run_id'], 'status': 'running', 'completed': 0,
             'total': len(folds) * len(plan['variants']), 'percent': 0, 'active': None,
             'elapsed_seconds': 0, 'started_at': now(), 'updated_at': now(),
             'events': [], 'models': [], 'metrics': [], 'predictions': [], 'warnings': []}
    audits, predictions = [], []
    if saved:
        audits = read(folder / 'partial_fold_audit.json')
        predictions = saved['predictions']
        if saved['completed'] != len(audits) or len(saved['events']) != len(audits):
            raise ValueError('Resume checkpoint does not reconcile.')
        failure_record = folder / 'attempt_01_failure.json'
        if not failure_record.exists():
            write(failure_record, {'status': saved['status'], 'error': saved.get('error'),
                  'completed': saved['completed'], 'elapsed_seconds': elapsed_before,
                  'plan_sha256': plan_hash, 'recovery': 'Bounded atomic-write retry; retain all154 completed folds; fit only remaining7.'})
        state = saved
        state.update(status='running', active=None, resumed_at=now())
        state.pop('error', None)
    state['plan_sha256'] = plan_hash
    completed_keys = {(a['variant'], a['fold']) for a in audits}

    def update():
        state['elapsed_seconds'] = round(elapsed_before + time.monotonic() - start, 3)
        state['updated_at'] = now()
        state['percent'] = 100 * state['completed'] / state['total']
        state['predictions'] = predictions
        write(folder / 'progress.json', state)

    versions = {n: importlib.metadata.version(n) for n in
                ['numpy', 'scipy', 'scikit-learn', 'xgboost', 'joblib', 'threadpoolctl']}
    write(folder / 'runtime.json', {'python': sys.version, 'versions': versions,
          'runtime': plan['runtime'], 'process_threads': 1, 'shared_runtime_modified': False})
    try:
        update()
        for spec in plan['variants']:
            model, features = spec['model'], spec['features']
            variant = model + '/' + features
            model_state = next((m for m in state['models'] if m['variant'] == variant), None)
            if model_state is None:
                model_state = {'variant': variant, 'completed': 0, 'total': len(folds), 'status': 'running'}
                state['models'].append(model_state)
            for n, split in enumerate(folds):
                if (variant, n + 1) in completed_keys:
                    continue
                state['active'] = {'variant': variant, 'fold': n + 1, 'total_folds': len(folds)}
                update()
                prepared = prepare_source_fold(ds, split, drop_reported_current=features == 'no_current')
                train, test = split['train'], split['test']
                X, V = np.asarray(prepared['X_train']), np.asarray(prepared['X_validation'])
                y = np.asarray(prepared['y_train'], dtype=float)
                weight = np.asarray(prepared['train_source_weights'], dtype=float)
                weight = weight / weight.mean()
                center, scale = 0., 1.
                if model == 'MLP':
                    center = float(np.average(y, weights=weight))
                    scale = math.sqrt(float(np.average((y - center) ** 2, weights=weight))) or 1.
                tick = time.monotonic()
                with warnings.catch_warnings(record=True) as caught, threadpool_limits(limits=1):
                    warnings.simplefilter('always')
                    if model == 'mean':
                        p = np.full(len(test), np.average(y, weights=weight))
                        train_pred = np.full(len(train), np.average(y, weights=weight))
                        estimator = None
                    else:
                        params = dict(plan['model_parameters'][model])
                        if model == 'MLP':
                            params['hidden_layer_sizes'] = tuple(params['hidden_layer_sizes'])
                        estimator = {'RF': RandomForestRegressor, 'XGBoost': XGBRegressor, 'MLP': MLPRegressor}[model](**params)
                        estimator.fit(X, (y - center) / scale, sample_weight=weight)
                        p = estimator.predict(V) * scale + center
                        train_pred = estimator.predict(X) * scale + center
                fit_seconds = time.monotonic() - tick
                if not np.isfinite(p).all():
                    raise ValueError('Non-finite prediction; do not silently omit failed folds.')
                messages = [{'category': type(w.message).__name__, 'message': str(w.message)} for w in caught]
                heldout_groups = sorted({ds.rows[i]['source_group'] for i in test})
                unknowns = {s['field']: sorted({ds.rows[i][s['field']] for i in test} - set(s['vocabulary']))
                            for s in prepared['training_only_schema'] if s['kind'] == 'categorical'}
                audit = {'variant': variant, 'fold': n + 1,
                         'train_endpoint_ids': [ds.rows[i]['endpoint_id'] for i in train],
                         'test_endpoint_ids': [ds.rows[i]['endpoint_id'] for i in test],
                         'training_source_groups': prepared['training_source_groups'], 'heldout_source_groups': heldout_groups,
                         'training_only_schema': prepared['training_only_schema'], 'feature_names': prepared['feature_names'],
                         'train_fit_weights': weight.tolist(), 'target_center': center, 'target_scale': scale,
                         'unknown_heldout_categories': unknowns,
                         'train_metrics': weighted_metrics(y, train_pred, prepared['train_source_weights']),
                         'heldout_mae': float(np.mean(np.abs(p - prepared['y_validation']))),
                         'warnings': messages, 'fit_seconds': fit_seconds,
                         'estimator_fitted': model != 'mean', 'iterations': int(getattr(estimator, 'n_iter_', 0))}
                audits.append(audit)
                for i, predicted in zip(test, p):
                    r = ds.rows[i]
                    predictions.append({'variant': variant, 'fold': n + 1, 'endpoint_id': r['endpoint_id'],
                        'sample_name': r['sample_name'], 'source_group': r['source_group'], 'observed': r['retention_pct'],
                        'predicted': float(predicted), 'residual': float(predicted) - r['retention_pct'],
                        'electrolyte': r['electrolyte'], 'reference_electrode': r['reference_electrode']})
                state['warnings'] += [{'variant': variant, 'fold': n + 1, **w} for w in messages]
                state['completed'] += 1
                model_state['completed'] += 1
                state['events'].append({'seconds': round(elapsed_before + time.monotonic() - start, 3), 'completed': state['completed'],
                                        'variant': variant, 'fold': n + 1, 'fold_mae': audit['heldout_mae']})
                update()
                print(json.dumps({'completed': state['completed'], 'total': state['total'], **state['active']}, ensure_ascii=False), flush=True)
            model_state['status'] = 'complete'
            state['metrics'] = summarize(predictions, audits)
            update()
        if sha(folder / 'training_plan.json') != plan_hash:
            raise ValueError('Training plan was changed during fitting.')
        result = {'run_id': plan['run_id'], 'complete': True, 'completed_at': now(),
                  'plan_sha256': plan_hash, 'dataset_fingerprint': ds.fingerprint(),
                  'evaluation_tasks': state['completed'], 'actual_estimator_fits': sum(a['estimator_fitted'] for a in audits),
                  'mean_reference_calculations': sum(not a['estimator_fitted'] for a in audits),
                  'metrics': state['metrics'], 'warning_count': len(state['warnings']),
                  'uncertainty': plan['uncertainty'], 'hyperparameter_search': False, 'final_all_data_refit': False,
                  'labels_clipped': False, 'model_binaries_published': False, 'input_quality': quality,
                  'data_preparation_authorization_flag_is_historical': True}
        write(folder / 'fold_audit.json', audits)
        write(folder / 'predictions.json', predictions)
        write(folder / 'results.json', result)
        state.update(status='complete', active=None)
        update()
        return result
    except BaseException as exc:
        state.update(status='interrupted' if isinstance(exc, KeyboardInterrupt) else 'failed',
                     error=type(exc).__name__ + ': ' + str(exc))
        write(folder / 'partial_fold_audit.json', audits)
        update()
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--resume', action='store_true', help='Continue only the uncompleted folds of a reconciled checkpoint.')
    args = parser.parse_args()
    result = run(args.run_dir, resume=args.resume)
    print(json.dumps({'complete': True, 'actual_estimator_fits': result['actual_estimator_fits']}, ensure_ascii=False))
