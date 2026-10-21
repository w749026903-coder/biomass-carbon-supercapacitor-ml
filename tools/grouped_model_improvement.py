"""Fold-local, source-weighted preprocessing and bounded model candidates."""
import collections
import math
import warnings
import numpy as np

CATEGORIES = ('electrolyte', 'reference_electrode')
NUMERIC = ('cycle_count', 'reported_current_A_g', 'concentration_mol_L',
           'cycle_voltage_lower_V', 'cycle_voltage_upper_V', 'BET_m2_g')
LOG_FIELDS = {'cycle_count', 'reported_current_A_g', 'concentration_mol_L', 'BET_m2_g'}


def weights(rows, ids):
    counts = collections.Counter(rows[i]['source_group'] for i in ids)
    w = np.asarray([1 / counts[rows[i]['source_group']] for i in ids], dtype=float)
    return w / w.mean()


def prepare(rows, train, test, spec):
    if not train or not test or len(set(train)) != len(train) or len(set(test)) != len(test) or set(train) & set(test):
        raise ValueError('Nonempty, unique and disjoint row partitions required.')
    if {rows[i]['source_group'] for i in train} & {rows[i]['source_group'] for i in test}:
        raise ValueError('Source leakage.')
    w = weights(rows, train)
    fields = [f for f in NUMERIC if spec['current'] or f != 'reported_current_A_g']
    schema = []
    for field in fields:
        values = np.asarray([rows[i][field] for i in train], dtype=float)
        if not np.isfinite(values).all():
            raise ValueError('Invalid numeric input.')
        use_log = spec['transform'] == 'log' and field in LOG_FIELDS
        if use_log:
            if (values <= 0).any():
                raise ValueError('Positive feature required for declared log transform.')
            values = np.log10(values)
        mean = float(np.average(values, weights=w))
        scale = math.sqrt(float(np.average((values - mean) ** 2, weights=w))) or 1.
        schema.append({'field': field, 'kind': 'numeric', 'log10': use_log, 'mean': mean, 'scale': scale})
    for field in CATEGORIES:
        schema.append({'field': field, 'kind': 'categorical', 'vocabulary': sorted({rows[i][field] for i in train})})

    def encode(ids):
        X = []
        for i in ids:
            encoded = []
            for s in schema:
                v = rows[i][s['field']]
                if s['kind'] == 'numeric':
                    if s['log10']:
                        if not math.isfinite(v) or v <= 0:
                            raise ValueError('Invalid log input.')
                        v = math.log10(v)
                    encoded.append((v - s['mean']) / s['scale'])
                else:
                    encoded.extend(float(v == c) for c in s['vocabulary'])
                    encoded.append(float(v not in s['vocabulary']))
            X.append(encoded)
        X = np.asarray(X, dtype=float)
        if not np.isfinite(X).all():
            raise ValueError('Non-finite prepared matrix.')
        return X

    y = np.asarray([rows[i]['retention_pct'] for i in train], dtype=float)
    center = float(np.average(y, weights=w))
    scale = math.sqrt(float(np.average((y - center) ** 2, weights=w))) or 1.
    return {'X': encode(train), 'V': encode(test), 'y': y, 'weights': w, 'schema': schema,
            'target_center': center, 'target_scale': scale}


def weighted_median(y, w):
    order = np.argsort(y, kind='stable')
    return float(np.asarray(y)[order][np.searchsorted(np.cumsum(np.asarray(w)[order]), sum(w) / 2)])


def fit_predict(prepared, spec):
    import time
    from sklearn.linear_model import Ridge
    from sklearn.kernel_ridge import KernelRidge
    from sklearn.neural_network import MLPRegressor
    from sklearn.ensemble import RandomForestRegressor
    from xgboost import XGBRegressor
    p = prepared
    kind = spec['kind']
    start = time.monotonic()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        if kind in ['mean', 'median']:
            value = float(np.average(p['y'], weights=p['weights'])) if kind == 'mean' else weighted_median(p['y'], p['weights'])
            prediction, training = np.full(len(p['V']), value), np.full(len(p['X']), value)
            model = None
        else:
            params = dict(spec['params'])
            if kind == 'mlp':
                params['hidden_layer_sizes'] = tuple(params['hidden_layer_sizes'])
            if kind == 'krr':
                params['kernel'] = 'rbf'
            model = {'ridge': Ridge, 'krr': KernelRidge, 'mlp': MLPRegressor,
                     'rf': RandomForestRegressor, 'xgb': XGBRegressor}[kind](**params)
            model.fit(p['X'], (p['y'] - p['target_center']) / p['target_scale'], sample_weight=p['weights'])
            prediction = model.predict(p['V']) * p['target_scale'] + p['target_center']
            training = model.predict(p['X']) * p['target_scale'] + p['target_center']
    if not np.isfinite(prediction).all():
        raise ValueError('Non-finite predictions; failed candidates are not silently discarded.')
    return prediction, {'train_mae': float(np.average(np.abs(training - p['y']), weights=p['weights'])),
                        'fit_seconds': time.monotonic() - start, 'estimator_fitted': model is not None,
                        'warnings': [{'category': type(w.message).__name__, 'message': str(w.message)} for w in caught]}


def inner_splits(rows, outer_train, outer_test, seed=42):
    if {rows[i]['source_group'] for i in outer_train} & {rows[i]['source_group'] for i in outer_test}:
        raise ValueError('Outer source leakage.')
    groups = np.asarray(sorted({rows[i]['source_group'] for i in outer_train}))
    rng = np.random.default_rng(seed)
    rng.shuffle(groups)
    splits = []
    for k in range(5):
        held = set(groups[k::5])
        tr = [i for i in outer_train if rows[i]['source_group'] not in held]
        va = [i for i in outer_train if rows[i]['source_group'] in held]
        if set(tr) | set(va) != set(outer_train) or (set(tr) | set(va)) & set(outer_test):
            raise ValueError('Invalid nested partition.')
        splits.append((tr, va))
    return splits


def select(scores, specs):
    by_id = {s['id']: s for s in specs}
    ordered = sorted(scores, key=lambda x: (x['mae'], by_id[x['candidate']]['complexity'], x['candidate']))
    best = ordered[0]
    threshold = best['mae'] + best['source_error_se']
    one_se = sorted([s for s in ordered if s['mae'] <= threshold],
                    key=lambda x: (by_id[x['candidate']]['complexity'], x['mae'], x['candidate']))[0]
    linear = next(s for s in ordered if by_id[s['candidate']]['kind'] in ['mean', 'median', 'ridge'])
    return {'nested_min': best['candidate'], 'nested_1se': one_se['candidate'], 'nested_linear': linear['candidate']}, threshold
