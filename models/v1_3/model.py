"""Fixed regularized models; auxiliary predictions never use their query source."""
from collections import Counter
import math
import numpy as np

ALIASES = {'BET_surface_area_m2_g': 'BET_m2_g', 'XPS_C_at_pct': 'XPS_C_atomic_pct_v15',
           'XPS_N_at_pct': 'XPS_N_atomic_pct_v15', 'XPS_O_at_pct': 'XPS_O_atomic_pct_v15'}
FORBIDDEN = ('retention', 'capacitance', 'discharge_time', 'resistance', 'coulombic', 'energy_density', 'power_density')

def canonical(features):
    out = {}; mapping = {}
    for k, v in features.items():
        raw = k.removeprefix('lib__'); name = ALIASES.get(raw, raw)
        if name in out and out[name] is not None and v is not None and out[name] != v:
            name = 'unmerged__' + k
        if name not in out or out[name] is None:
            out[name] = v
        mapping[k] = name
    assert not any(s in k.lower() for k in out for s in FORBIDDEN)
    return out, mapping

def weights(rows):
    totals = Counter()
    for r in rows: totals[r['source_family']] += r.get('quality_weight', 1.)
    return np.array([r.get('quality_weight', 1.) / totals[r['source_family']] for r in rows])

def scores(rows, p):
    w = weights(rows); y = np.array([r['target'] for r in rows]); p = np.asarray(p)
    mse = np.average((y-p)**2, weights=w); var = np.average((y-np.average(y, weights=w))**2, weights=w)
    return dict(mae=float(np.average(abs(y-p), weights=w)), rmse=float(np.sqrt(mse)), r2=float(1-mse/var))

class Encoder:
    def __init__(self, minimum_fraction=.2): self.minimum_fraction = minimum_fraction

    def fit(self, rows):
        self.schema = []; self.fields = sorted({k for r in rows for k in r['features']})
        self.training_sources = sorted({r['source_family'] for r in rows})
        for name in self.fields:
            obs = [r for r in rows if r['features'].get(name) is not None]
            support = len({r['source_family'] for r in obs})
            enabled = support >= 3 and len(obs) / len(rows) >= self.minimum_fraction
            kinds = {isinstance(r['features'][name], str) for r in obs}
            assert len(kinds) <= 1, name
            item = dict(field=name, enabled=enabled, source_support=support, observed_rows=len(obs), kind='categorical' if True in kinds else 'numeric')
            if enabled and item['kind'] == 'categorical':
                vals = sorted({r['features'][name] for r in obs})
                item['vocabulary'] = [v for v in vals if len({r['source_family']for r in obs if r['features'][name]==v})>=3]
            elif enabled:
                vals = np.array([r['features'][name] for r in obs], dtype=float)
                assert np.isfinite(vals).all(), name
                use_log = bool(any(s in name for s in ['volume', 'surface_area', 'BET_', 'cycle_count', 'current_A_g', 'conductivity']) and min(vals) >= 0)
                z = np.log1p(vals) if use_log else vals
                w = weights(obs); center = np.average(z, weights=w); order = np.argsort(z, kind='stable')
                median = z[order][np.searchsorted(np.cumsum(w[order]), w.sum()/2)]
                item.update(log1p=use_log, impute=float(median), center=float(center), scale=float(np.sqrt(np.average((z-center)**2,weights=w))) or 1.)
            self.schema.append(item)
        assert any(x['enabled']for x in self.schema), 'No supported features'
        return self

    def transform(self, rows):
        result = []
        for r in rows:
            row = []
            for item in self.schema:
                if not item['enabled']: continue
                v = r['features'].get(item['field'])
                if item['kind'] == 'categorical':
                    row += [float(v == level) for level in item['vocabulary']] + [float(v not in item['vocabulary'])]
                else:
                    z = item['impute'] if v is None else math.log1p(v) if item['log1p'] else v
                    row += [(z-item['center'])/item['scale'], float(v is None)]
            result.append(row)
        a = np.asarray(result); assert np.isfinite(a).all(); return a

class Regressor:
    def __init__(self, kind='ridge', minimum_fraction=.2): self.kind=kind; self.minimum_fraction=minimum_fraction

    def fit(self, rows):
        from sklearn.linear_model import Ridge
        from sklearn.ensemble import ExtraTreesRegressor
        self.encoder=Encoder(self.minimum_fraction).fit(rows); x=self.encoder.transform(rows)
        self.training_sources=sorted({r['source_family'] for r in rows}); self.training_rows=[r['row_id']for r in rows]
        y=np.array([r['target']for r in rows]); assert min(y)>0
        w=weights(rows); z=np.log(y); self.center=float(np.average(z,weights=w)); self.scale=float(np.sqrt(np.average((z-self.center)**2,weights=w))) or 1.
        self.estimator = Ridge(alpha=100.,solver='svd') if self.kind=='ridge' else ExtraTreesRegressor(n_estimators=160,max_depth=4,min_samples_leaf=3,max_features=.8,random_state=20261029,n_jobs=1)
        self.estimator.fit(x,(z-self.center)/self.scale,sample_weight=w)
        return self

    def predict(self, rows):
        p=np.exp(self.estimator.predict(self.encoder.transform(rows))*self.scale+self.center)
        assert np.isfinite(p).all() and min(p)>0
        return p

class AssistedModel:
    def __init__(self, main, helpers): self.main=main; self.helpers=helpers
    def predict(self, rows):
        enriched=[dict(r,features=dict(r['features'])) for r in rows]
        for name, model in self.helpers.items():
            query=[dict(r,features=dict(r['features'],voltage_lower_V=r['features'].get('cycle_voltage_lower_V'),voltage_upper_V=r['features'].get('cycle_voltage_upper_V')))for r in rows]
            for r,p in zip(enriched,model.predict(query)):r['features']['aux_predicted_'+name]=float(p)
        return self.main.predict(enriched)
