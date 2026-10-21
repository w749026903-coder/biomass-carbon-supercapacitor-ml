"""Model-free, training-fold-only encoding of sparse v0.11 material inputs."""
import collections
import math


def prepare_material_fold(matrix, split, minimum_material_sources=2):
    """Source-balanced means/scales, explicit missing flags, training vocabulary only.

    A sparse extra numeric predictor needs two observed training-source groups;
    otherwise its encoded channel is disabled for both train and held-out rows.
    The raw scientific matrix is never modified. No estimator is fitted.
    """
    train = list(split['train']); test = list(split['test'])
    excluded = list(split.get('outer_holdout', [])); n = len(matrix['X'])
    if not train or not test or set(train) & set(test) or (set(train) | set(test)) & set(excluded) or set(train) | set(test) | set(excluded) != set(range(n)):
        raise ValueError('Nonempty disjoint train/test/outer partition required.')
    groups = matrix['groups']
    tg = {groups[i] for i in train}; vg = {groups[i] for i in test}
    if tg & vg or {groups[i] for i in excluded} & (tg | vg):
        raise ValueError('Source-group leakage rejected.')
    forbidden = {'endpoint_id', 'identity_key', 'source_group', 'sample_name', 'retention_pct', 'material_id', 'material_key_v11', 'post_cycle_XPS', 'post_cycle_EIS', 'final_capacitance'}
    if set(matrix['feature_names']) & forbidden:
        raise ValueError('Forbidden predictor.')
    categorical = set(matrix['categorical_features'])
    schema = []; columns = []
    core = {'cycle_count', 'reported_current_A_g', 'electrolyte', 'concentration_mol_L', 'cycle_voltage_lower_V', 'cycle_voltage_upper_V', 'BET_m2_g', 'reference_electrode'}
    for j, field in enumerate(matrix['feature_names']):
        observed = [(i, matrix['X'][i][j]) for i in train if matrix['X'][i][j] is not None]
        if field in categorical:
            vocabulary = sorted({v for _, v in observed})
            schema.append({'field': field, 'index': j, 'kind': 'categorical', 'vocabulary': vocabulary})
            columns.extend([field + '=' + v for v in vocabulary] + [field + '=<MISSING>', field + '=<UNKNOWN>'])
            continue
        source_counts = collections.Counter(groups[i] for i, _ in observed)
        enabled = bool(observed) and (field in core or len(source_counts) >= minimum_material_sources)
        if enabled:
            total_weight = sum(1 / source_counts[groups[i]] for i, _ in observed)
            mean = sum(v / source_counts[groups[i]] for i, v in observed) / total_weight
            scale = math.sqrt(sum((v - mean) ** 2 / source_counts[groups[i]] for i, v in observed) / total_weight) or 1.0
        else:
            mean = 0.0; scale = 1.0
        schema.append({'field': field, 'index': j, 'kind': 'numeric', 'enabled': enabled,
                       'observed_training_sources': len(source_counts), 'training_source_balanced_mean': mean,
                       'training_source_balanced_scale': scale, 'minimum_material_sources': minimum_material_sources})
        columns.extend([field, field + '::<MISSING>'])

    def encode(ids):
        result = []
        for i in ids:
            values = []
            for spec in schema:
                v = matrix['X'][i][spec['index']]
                if spec['kind'] == 'categorical':
                    values.extend([float(v == c) for c in spec['vocabulary']] + [float(v is None), float(v is not None and v not in spec['vocabulary'])])
                elif not spec['enabled']:
                    values.extend([0.0, 1.0])
                else:
                    values.extend([0.0 if v is None else (v - spec['training_source_balanced_mean']) / spec['training_source_balanced_scale'], float(v is None)])
            if any(not math.isfinite(v) for v in values):
                raise ValueError('Nonfinite encoded matrix.')
            result.append(values)
        return result

    def weights(ids):
        counts = collections.Counter(groups[i] for i in ids)
        return [1 / counts[groups[i]] for i in ids]

    return {'X_train': encode(train), 'X_validation': encode(test),
            'y_train': [matrix['y'][i] for i in train], 'y_validation': [matrix['y'][i] for i in test],
            'train_indices': train, 'validation_indices': test, 'outer_holdout_indices': excluded,
            'train_source_weights': weights(train), 'validation_source_weights': weights(test),
            'feature_names': columns, 'training_only_schema': schema, 'estimators_fitted': 0,
            'training_source_groups': sorted(tg), 'validation_source_groups': sorted(vg)}
