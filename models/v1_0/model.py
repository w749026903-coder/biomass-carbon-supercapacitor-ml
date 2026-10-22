"""Serializable small-data regression, with training-only scientific feature encoding."""
from __future__ import annotations

from collections import Counter
import math
import numpy as np

CORE = ['cycle_count', 'reported_current_A_g', 'electrolyte', 'concentration_mol_L',
        'cycle_voltage_lower_V', 'cycle_voltage_upper_V', 'BET_m2_g', 'reference_electrode']
CATEGORICAL = {'electrolyte', 'reference_electrode'}
MATERIAL = ['total_pore_volume_cm3_g', 'micropore_volume_cm3_g', 'mesopore_volume_cm3_g',
            'average_pore_diameter_nm', 'micropore_surface_area_m2_g', 'external_surface_area_m2_g',
            'Raman_ID_IG', 'XRD_d002_nm', 'N_at_pct', 'O_at_pct', 'bulk_N_wt_pct', 'bulk_O_wt_pct',
            'mass_loading_mg_cm2', 'activation_temperature_C', 'activation_duration_h', 'heating_rate_C_min',
            'material_density_g_cm3', 'carbonization_temperature_C', 'carbonization_duration_h',
            'carbonization_heating_rate_C_min', 'precarbonization_temperature_C', 'precarbonization_duration_h',
            'precarbonization_heating_rate_C_min', 'hydrothermal_temperature_C', 'hydrothermal_duration_h',
            'microwave_power_W_v14', 'post_treatment_temperature_C', 'post_treatment_duration_h',
            'post_treatment_heating_rate_C_min', 'pretreatment_temperature_C', 'pretreatment_duration_h',
            'pretreatment_heating_rate_C_min']
LOG_FIELDS = {'cycle_count', 'reported_current_A_g', 'BET_m2_g', 'mass_loading_mg_cm2',
              'total_pore_volume_cm3_g', 'micropore_volume_cm3_g', 'mesopore_volume_cm3_g',
              'average_pore_diameter_nm', 'micropore_surface_area_m2_g', 'external_surface_area_m2_g'}


def weights(records):
    counts = Counter(r['source_group'] for r in records)
    return np.array([1 / counts[r['source_group']] for r in records], dtype=float)


def metrics(records, predictions):
    y = np.array([r['retention_pct'] for r in records], dtype=float)
    p = np.asarray(predictions, dtype=float)
    w = weights(records)
    mse = float(np.average((p - y) ** 2, weights=w))
    var = float(np.average((y - np.average(y, weights=w)) ** 2, weights=w))
    return {'mae': float(np.average(abs(p - y), weights=w)), 'rmse': math.sqrt(mse),
            'r2': 1 - mse / var if len(y) > 1 and var > 0 else None}


class Encoder:
    def __init__(self, spec, minimum_material_sources=5):
        self.spec = dict(spec)
        self.minimum_material_sources = minimum_material_sources

    def fit(self, records):
        legacy = self.spec.get('legacy', False)
        fields = [f for f in CORE if self.spec['current'] or f != 'reported_current_A_g']
        if self.spec['block'] == 'material':
            fields += MATERIAL
        self.schema = []
        for f in fields:
            if f in CATEGORICAL:
                vocabulary = sorted({r[f] for r in records if r.get(f) is not None})
                self.schema.append({'field': f, 'kind': 'categorical', 'vocabulary': vocabulary})
                continue
            observed = [r for r in records if r.get(f) is not None]
            support = len({r['source_group'] for r in observed})
            enabled = bool(observed) and (f in CORE or support >= self.minimum_material_sources)
            item = {'field': f, 'kind': 'numeric', 'enabled': enabled, 'source_support': support,
                    'transform': 'log1p' if f in LOG_FIELDS and not legacy else 'raw',
                    'missing_indicator': f not in CORE}
            if enabled:
                values = np.array([self._value(r[f], item) for r in observed])
                w = np.ones(len(observed)) if legacy else weights(observed)
                mean = float(np.average(values, weights=w))
                scale = math.sqrt(float(np.average((values - mean) ** 2, weights=w))) or 1.
                item.update(mean=mean, scale=scale, minimum=min(r[f] for r in observed),
                            maximum=max(r[f] for r in observed))
            self.schema.append(item)
        self.training_sources = sorted({r['source_group'] for r in records})
        return self

    @staticmethod
    def _value(value, item):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError('Finite numeric feature required: ' + item['field'])
        if item['transform'] == 'log1p':
            if value < 0:
                raise ValueError('Negative value for a nonnegative feature: ' + item['field'])
            return math.log1p(value)
        return float(value)

    def transform(self, records):
        output = []
        for r in records:
            row = []
            for item in self.schema:
                f = item['field']
                value = r.get(f)
                if item['kind'] == 'categorical':
                    row += [float(value == c) for c in item['vocabulary']]
                    row += [float(value not in item['vocabulary'])]
                elif item['enabled']:
                    row.append(0. if value is None else (self._value(value, item) - item['mean']) / item['scale'])
                    if item['missing_indicator']:
                        row.append(float(value is None))
            if not row or not all(math.isfinite(x) for x in row):
                raise ValueError('Invalid encoded matrix.')
            output.append(row)
        return np.asarray(output, dtype=float)

    def warnings(self, record):
        alerts = []
        for item in self.schema:
            f, v = item['field'], record.get(item['field'])
            if item['kind'] == 'categorical':
                if v not in item['vocabulary']:
                    alerts.append('unseen_category:' + f + '=' + str(v))
            elif item['enabled']:
                if v is None:
                    alerts.append('missing:' + f)
                elif v < item['minimum'] or v > item['maximum']:
                    alerts.append('outside_training_range:' + f)
        return alerts


class RetentionModel:
    """Keep feature schema, all preprocessing, and estimator together for local reuse."""
    def __init__(self, spec):
        self.spec = dict(spec)

    def fit(self, records):
        from sklearn.linear_model import Ridge
        from sklearn.kernel_ridge import KernelRidge
        from sklearn.ensemble import ExtraTreesRegressor
        from sklearn.neural_network import MLPRegressor
        from sklearn.metrics.pairwise import euclidean_distances

        y = np.array([r['retention_pct'] for r in records], dtype=float)
        w = weights(records)
        self.center = float(np.average(y, weights=w))
        self.scale = math.sqrt(float(np.average((y - self.center) ** 2, weights=w))) or 1.
        self.training_endpoint_ids = [r['endpoint_id'] for r in records]
        self.training_sources = sorted({r['source_group'] for r in records})
        self.training_target_range = [float(y.min()), float(y.max())]
        kind = self.spec['kind']
        self.estimator_fit_count = 0
        if kind in ('mean', 'median'):
            if kind == 'median':
                order = np.argsort(y, kind='stable')
                self.center = float(y[order][np.searchsorted(np.cumsum(w[order]), w.sum() / 2)])
            self.encoder = None
            return self
        self.encoder = Encoder(self.spec).fit(records)
        X = self.encoder.transform(records)
        if kind == 'ridge':
            self.estimator = Ridge(alpha=self.spec['alpha'], solver='svd')
        elif kind == 'krr':
            dist = euclidean_distances(X, X, squared=True)
            cross_source = np.array([[a['source_group'] != b['source_group'] for b in records] for a in records])
            mask = cross_source & (dist > 1e-12)
            values = dist[mask]
            pair_weights = (w[:, None] * w[None, :])[mask]
            order = np.argsort(values, kind='stable')
            median = float(values[order][np.searchsorted(np.cumsum(pair_weights[order]), pair_weights.sum() / 2)])
            self.kernel_gamma = 1 / median
            self.estimator = KernelRidge(alpha=self.spec['alpha'], kernel='rbf', gamma=self.kernel_gamma)
        elif kind == 'extra_trees':
            self.estimator = ExtraTreesRegressor(n_estimators=200, max_depth=4,
                min_samples_leaf=self.spec['leaf'], max_features=.8, random_state=42, n_jobs=1)
        elif kind == 'mlp':
            self.estimator = MLPRegressor(hidden_layer_sizes=(self.spec['hidden'],), activation='tanh',
                solver='lbfgs', alpha=self.spec['alpha'], max_iter=3000 if not self.spec.get('legacy') else 2000,
                max_fun=50000 if not self.spec.get('legacy') else 30000, tol=1e-6,
                early_stopping=False, random_state=42)
        else:
            raise ValueError('Unplanned model family: ' + kind)
        # Original reference retains its exact mean-one fitting weights and row-scaled X.
        fitting_weights = w / w.mean() if self.spec.get('legacy') else w
        self.estimator.fit(X, (y - self.center) / self.scale, sample_weight=fitting_weights)
        self.estimator_fit_count = 1
        return self

    def predict(self, records):
        if self.encoder is None:
            return np.full(len(records), self.center)
        return self.estimator.predict(self.encoder.transform(records)) * self.scale + self.center

    def predict_with_context(self, records):
        for record in records:
            if record.get('system', '3E') != '3E':
                raise ValueError('v1.0 supports three-electrode tests only.')
            for field in CORE:
                if record.get(field) is None:
                    raise ValueError('Required protocol input missing: ' + field)
            if record['cycle_count'] < 1000 or record.get('method', 'GCD') != 'GCD':
                raise ValueError('Outside approved GCD >=1000-cycle purpose.')
        predictions = self.predict(records)
        return [{'retention_pct_prediction': float(prediction),
                 'warnings': self.encoder.warnings(record) if self.encoder else [],
                 'scope': 'reported_protocol_3e_exploratory', 'calibrated_interval': None}
                for record, prediction in zip(records, predictions)]
