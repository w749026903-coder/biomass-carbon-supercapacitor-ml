"""Small-sample retention models with auditable, training-only feature encoding."""
from collections import Counter
import math
import numpy as np

CORE = ['cycle_count', 'reported_current_A_g', 'electrolyte', 'concentration_mol_L',
        'cycle_voltage_lower_V', 'cycle_voltage_upper_V', 'BET_m2_g', 'reference_electrode']
CATEGORIES = {'electrolyte', 'reference_electrode', 'XPS_percentage_basis',
              'activation_primary_chemistry', 'activation_stage_status', 'precursor_origin_class'}
LOG_FIELDS = {'cycle_count', 'reported_current_A_g', 'BET_m2_g', 'mass_loading_mg_cm2',
              'total_pore_volume_cm3_g', 'micropore_volume_cm3_g', 'mesopore_volume_cm3_g',
              'average_pore_diameter_nm', 'micropore_surface_area_m2_g', 'external_surface_area_m2_g'}

def weights(rows):
    counts = Counter(r['source_group'] for r in rows)
    return np.array([1. / counts[r['source_group']] for r in rows])

def weighted_median(values, w):
    order = np.argsort(values, kind='stable')
    v, w = np.asarray(values)[order], np.asarray(w)[order]
    return float(v[np.searchsorted(np.cumsum(w), w.sum() / 2, side='left')])

def metrics(rows, predictions):
    y = np.array([r['retention_pct'] for r in rows]); p = np.asarray(predictions); w = weights(rows)
    mse = float(np.average((p-y)**2, weights=w)); var = float(np.average((y-np.average(y, weights=w))**2, weights=w))
    return dict(mae=float(np.average(abs(p-y), weights=w)), rmse=math.sqrt(mse), r2=1-mse/var if var else None)

class Encoder:
    def __init__(self, specification, features):
        self.spec, self.features = dict(specification), list(features)

    @staticmethod
    def value(v, field):
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
            raise ValueError('Finite numeric input required: '+field)
        if field in LOG_FIELDS:
            if v < 0: raise ValueError('Negative nonnegative feature: '+field)
            return math.log1p(v)
        return float(v)

    def fit(self, rows):
        fields = CORE if self.spec['block']=='core' else self.features
        fields = [f for f in fields if self.spec['current'] or f!='reported_current_A_g']
        self.schema = []; self.training_sources = sorted({r['source_group'] for r in rows})
        for f in fields:
            observed = [r for r in rows if r.get(f) is not None]
            support = len({r['source_group'] for r in observed})
            if f in CATEGORIES:
                levels = sorted({r[f] for r in observed})
                counts = {v:len({r['source_group'] for r in observed if r[f]==v}) for v in levels}
                vocabulary = [v for v in levels if counts[v]>=3]
                self.schema.append(dict(field=f, kind='categorical', vocabulary=vocabulary, source_support=counts,
                                        unknown_policy='one explicit unknown-or-rare column'))
            else:
                enabled = support >= (1 if f in CORE else 5)
                item = dict(field=f,kind='numeric',enabled=enabled,source_support=support,
                            transform='log1p' if f in LOG_FIELDS else 'raw',missing_indicator=f not in CORE)
                if enabled:
                    values = np.array([self.value(r[f],f) for r in observed]); w = weights(observed)
                    center = float(np.average(values,weights=w)); scale = math.sqrt(float(np.average((values-center)**2,weights=w))) or 1.
                    item.update(impute=weighted_median(values,w), center=center, scale=scale,
                                minimum=min(r[f] for r in observed),maximum=max(r[f] for r in observed))
                self.schema.append(item)
        return self

    def transform(self, rows):
        result = []
        for r in rows:
            out = []
            for item in self.schema:
                f = item['field']; v = r.get(f)
                if item['kind']=='categorical':
                    out.extend(float(v==k) for k in item['vocabulary']); out.append(float(v not in item['vocabulary']))
                elif item['enabled']:
                    number = item['impute'] if v is None else self.value(v,f)
                    out.append((number-item['center'])/item['scale'])
                    if item['missing_indicator']: out.append(float(v is None))
            assert out and all(math.isfinite(x) for x in out)
            result.append(out)
        return np.asarray(result)

    def warnings(self, r):
        out=[]
        for item in self.schema:
            f=item['field']; v=r.get(f)
            if item['kind']=='categorical' and v not in item['vocabulary']:out.append('unknown_or_rare:'+f)
            elif item['kind']=='numeric' and item['enabled']:
                if v is None:out.append('missing:'+f)
                elif v<item['minimum'] or v>item['maximum']:out.append('outside_training_range:'+f)
        return out

class RetentionModel:
    def __init__(self, specification, features):
        self.spec, self.features = dict(specification), list(features)

    def fit(self, rows):
        from sklearn.linear_model import Ridge
        from sklearn.kernel_ridge import KernelRidge
        from sklearn.ensemble import ExtraTreesRegressor
        from sklearn.metrics.pairwise import euclidean_distances
        self.encoder=Encoder(self.spec,self.features).fit(rows); X=self.encoder.transform(rows)
        y=np.asarray([r['retention_pct'] for r in rows]); assert np.all(y>0)
        w=weights(rows); z=np.log(y/100.)
        self.center=float(np.average(z,weights=w)); self.scale=math.sqrt(float(np.average((z-self.center)**2,weights=w))) or 1.
        self.training_sources=sorted({r['source_group'] for r in rows}); self.training_endpoint_ids=[r['endpoint_id'] for r in rows]
        kind=self.spec['kind']
        if kind=='ridge':self.estimator=Ridge(alpha=self.spec['alpha'],solver='svd')
        elif kind=='krr':
            dist=euclidean_distances(X,X,squared=True); cross=np.array([[a['source_group']!=b['source_group'] for b in rows] for a in rows])
            mask=cross & (dist>1e-12); pair_w=(w[:,None]*w[None,:])[mask]
            self.kernel_gamma=1/weighted_median(dist[mask],pair_w)
            self.estimator=KernelRidge(alpha=self.spec['alpha'],kernel='rbf',gamma=self.kernel_gamma)
        elif kind=='extra_trees':
            self.estimator=ExtraTreesRegressor(n_estimators=200,max_depth=3,min_samples_leaf=3,max_features=.7,random_state=20261028,n_jobs=1)
        else:raise ValueError('Unplanned estimator')
        self.estimator.fit(X,(z-self.center)/self.scale,sample_weight=w)
        return self

    def predict(self, rows):
        p=100*np.exp(self.estimator.predict(self.encoder.transform(rows))*self.scale+self.center)
        if not np.all(np.isfinite(p)) or np.any(p<=0):raise ValueError('Nonfinite or nonpositive prediction')
        return p

    def predict_with_context(self, rows):
        for r in rows:
            if r.get('system','3E')!='3E' or r.get('method','GCD')!='GCD':raise ValueError('Only reviewed 3E GCD purpose')
            if any(r.get(f) is None for f in CORE):raise ValueError('Missing required protocol feature')
            if r['cycle_count']<1000:raise ValueError('Outside >=1000-cycle purpose')
        return [dict(predicted_retention_pct=float(p),predicted_retention_ratio=float(p)/100,
                     above_initial_reference=bool(p>100),warnings=self.encoder.warnings(r),
                     reliable_for_design=False,calibrated_prediction_interval=None)
                for r,p in zip(rows,self.predict(rows))]
