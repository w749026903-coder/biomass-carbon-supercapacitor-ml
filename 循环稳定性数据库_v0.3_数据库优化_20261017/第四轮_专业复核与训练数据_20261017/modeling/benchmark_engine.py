"""Shared nested grouped engine. Synthetic runs never read/write research rows."""
import collections
import copy
import hashlib
import importlib.metadata
import json
import math
import pathlib
import warnings
from prepare_dataset import ROOT, CONTRACT, validate_rows

def source_disjoint(train_rows, test_rows):
    for key in ['study_group','paper_id','material_id','cycle_test_id']:
        if {r[key] for r in train_rows} & {r[key] for r in test_rows}:
            raise ValueError('Train/test leakage: '+key)

def load_spaces(config):
    specs = json.loads((ROOT/'modeling'/config['tuning']['search_space']).read_text(encoding='utf-8'))
    specs['mlp']['grid']['hidden_layer_sizes'] = config['mlp_policy']['small_networks']
    specs['mlp']['default']['hidden_layer_sizes'] = config['mlp_policy']['small_networks'][0]
    specs['mlp']['base'].update(solver=config['mlp_policy']['solver'],early_stopping=config['mlp_policy']['early_stopping'])
    if specs['mlp']['base']['early_stopping']:
        raise ValueError('Random internal MLP validation is forbidden')
    return specs

def validate_config(config):
    for v in [config['split']['folds_up_to'],config['tuning']['inner_group_folds_up_to']]:
        if type(v) is not int or v < 2:
            raise ValueError('Group fold caps must be integers >= 2')
    for v in [config['tuning']['candidate_budget_per_model'],*config['tuning'].get('budget_by_model',{}).values()]:
        if type(v) is not int or v < 1:
            raise ValueError('Candidate budget must be a positive integer')
    if type(config['split']['random_state']) is not int or type(config['split']['shuffle']) is not bool:
        raise ValueError('Invalid split configuration')
    if config['tuning']['selection_metric'] != 'study_macro_MAE_percentage_points':
        raise ValueError('Unsupported tuning metric')
    if config['split']['method'] != 'GroupKFold':
        raise ValueError('Unsupported splitter')
    specs = load_spaces(config)
    if not config['models'] or len(set(config['models'])) != len(config['models']) or set(config['models'])-set(specs):
        raise ValueError('Unknown, empty, or duplicate model selection')
    for nums in config['feature_sets'].values():
        if set(nums+config['categorical_features']) & set(config['forbidden_features']):
            raise ValueError('Forbidden feature')
    return specs

def candidates_for(name, cfg, specs):
    from sklearn.model_selection import ParameterSampler
    grid = specs[name]['grid']
    if not grid:
        return [{}]
    budget = cfg['tuning'].get('budget_by_model',{}).get(name,cfg['tuning']['candidate_budget_per_model'])
    if budget == 1:
        return [copy.deepcopy(specs[name]['default'])]
    return list(ParameterSampler(grid,n_iter=min(budget,math.prod(len(v) for v in grid.values())),random_state=cfg['split']['random_state']))

def weights_for(groups):
    import numpy as np
    counts = collections.Counter(groups)
    weights = np.array([1/counts[s] for s in groups])
    return weights * len(groups)/weights.sum()

def splitter(n_groups, cap, cfg, seed_offset=0):
    from sklearn.model_selection import GroupKFold
    return GroupKFold(n_splits=min(cap,n_groups),shuffle=cfg['split']['shuffle'],
                      random_state=cfg['split']['random_state']+seed_offset if cfg['split']['shuffle'] else None)

def make_model(name, params, numeric_count, feature_count, cfg, specs):
    from sklearn.compose import ColumnTransformer, TransformedTargetRegressor
    from sklearn.dummy import DummyRegressor
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import Ridge
    from sklearn.neural_network import MLPRegressor
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import OneHotEncoder, StandardScaler
    args = {**specs[name]['base'],**params}
    if name in ['random_forest','xgboost','mlp']:
        args['random_state'] = cfg['split']['random_state']
    if name == 'mlp':
        args['hidden_layer_sizes'] = tuple(args['hidden_layer_sizes'])
    classes = {'mean_baseline':DummyRegressor,'ridge':Ridge,'random_forest':RandomForestRegressor,'mlp':MLPRegressor}
    if name == 'xgboost':
        from xgboost import XGBRegressor
        estimator = XGBRegressor(**args)
    else:
        estimator = classes[name](**args)
    prep = ColumnTransformer([
        ('numeric',Pipeline([('imputer',SimpleImputer(strategy='median',add_indicator=True,keep_empty_features=True)),
                            ('scale',StandardScaler())]),list(range(numeric_count))),
        ('categorical',OneHotEncoder(handle_unknown='ignore',sparse_output=False),list(range(numeric_count,feature_count)))])
    pipe = Pipeline([('features',prep),('estimator',estimator)])
    return TransformedTargetRegressor(regressor=pipe,transformer=StandardScaler()) if name == 'mlp' else pipe

def run_benchmark(rows, output, feature_set, config=None, synthetic=False):
    import numpy as np
    from sklearn.metrics import r2_score
    cfg = copy.deepcopy(config or CONTRACT)
    if not synthetic and cfg.get('research_training_authorized') is not True:
        raise RuntimeError('Research fitting is disabled in this data-preparation revision')
    specs = validate_config(cfg)
    rows = validate_rows(copy.deepcopy(rows),cfg,require_admission=not synthetic)
    if synthetic and (not rows or any(r.get('_synthetic') is not True for r in rows)):
        raise ValueError('Synthetic checks require explicitly synthetic rows')
    if not rows:
        raise ValueError('No admitted records. Candidate exports cannot bypass record admission.')
    if feature_set not in cfg['feature_sets']:
        raise ValueError('Unknown feature set')
    groups = sorted({r['study_group'] for r in rows})
    if len(groups) < 2:
        raise ValueError('Grouped validation needs two groups; this is not an adequacy threshold')
    output = pathlib.Path(output)
    output.mkdir(parents=True,exist_ok=False)
    def write(name,data):
        (output/name).write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    numeric = cfg['feature_sets'][feature_set]
    features = numeric+cfg['categorical_features']
    X = np.array([[np.nan if r.get(k) is None else r[k] for k in features] for r in rows],dtype=object)
    y = np.array([r['retention_pct'] for r in rows],dtype=float)
    g = np.array([r['study_group'] for r in rows])
    write('run_manifest.json',{'kind':'SYNTHETIC_INTERFACE_CHECK_NOT_RESEARCH' if synthetic else 'research_grouped_validation',
        'completion_file':'completion.json','feature_set':feature_set,'features':features,'config':cfg,'resolved_model_spaces':specs,
        'rows_sha256':hashlib.sha256(json.dumps(rows,sort_keys=True).encode()).hexdigest(),
        'code_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'modeling').glob('*.py')},
        'versions':{k:importlib.metadata.version(k) for k in ['numpy','scipy','scikit-learn','xgboost']}})
    warning_log = []
    fits = []
    def fit_predict(name,params,tr,te,context):
        source_disjoint([rows[i] for i in tr],[rows[i] for i in te])
        model = make_model(name,params,len(numeric),len(features),cfg,specs)
        with warnings.catch_warnings(record=True) as observed:
            warnings.simplefilter('always')
            model.fit(X[tr],y[tr],estimator__sample_weight=weights_for(g[tr]))
            pred = model.predict(X[te])
        warning_log.extend({'model':name,'context':context,'parameters':params,'category':w.category.__name__,'message':str(w.message)} for w in observed)
        fits.append({'model':name,'context':context,'train_groups':sorted(set(g[tr])),'test_groups':sorted(set(g[te]))})
        if not np.isfinite(pred).all():
            raise ValueError('Nonfinite prediction')
        return pred
    def macro_mae(indices,pred):
        return float(np.mean([np.mean(np.abs(y[indices][g[indices]==s]-pred[g[indices]==s])) for s in sorted(set(g[indices]))]))
    try:
        splits = list(splitter(len(groups),cfg['split']['folds_up_to'],cfg).split(X,y,g))
        assignments = []
        for fold,(tr,te) in enumerate(splits):
            source_disjoint([rows[i] for i in tr],[rows[i] for i in te])
            assignments.extend({'record_id':rows[i]['record_id'],'outer_test_fold':fold,'study_group':rows[i]['study_group']} for i in te)
        write('fold_assignments.json',assignments)
        results = {}
        predictions = []
        for name in cfg['models']:
            pred = np.empty(len(rows))
            folds = []
            candidates = candidates_for(name,cfg,specs)
            for fold,(tr,te) in enumerate(splits):
                train_groups = sorted(set(g[tr]))
                selection = []
                if len(train_groups) >= 2 and len(candidates) > 1:
                    inner = splitter(len(train_groups),cfg['tuning']['inner_group_folds_up_to'],cfg,fold)
                    inner_splits = [(tr[it],tr[iv]) for it,iv in inner.split(X[tr],y[tr],g[tr])]
                    for params in candidates:
                        ipred = {}
                        for inner_fold,(it,iv) in enumerate(inner_splits):
                            for idx,val in zip(iv,fit_predict(name,params,it,iv,{'phase':'inner','outer_fold':fold,'inner_fold':inner_fold})):
                                ipred[int(idx)] = float(val)
                        idx = np.array(sorted(ipred))
                        selection.append({'parameters':params,'inner_source_macro_MAE_pp':macro_mae(idx,np.array([ipred[int(i)] for i in idx]))})
                    chosen = min(selection,key=lambda x:x['inner_source_macro_MAE_pp'])['parameters']
                    policy = 'inner_group_search'
                else:
                    chosen = specs[name]['default'] if len(train_groups)<2 else candidates[0]
                    policy = 'predeclared_default_insufficient_inner_groups' if len(train_groups)<2 else 'single_prespecified_candidate'
                pred[te] = fit_predict(name,chosen,tr,te,{'phase':'outer','outer_fold':fold})
                folds.append({'fold':fold,'train_groups':train_groups,'test_groups':sorted(set(g[te])),
                    'chosen_parameters':chosen,'inner_search':selection,'selection_policy':policy,'outer_test_used_for_tuning':False})
            per_source = []
            for group in groups:
                err = y[g==group]-pred[g==group]
                per_source.append({'study_group':group,'rows':int((g==group).sum()),'MAE_pp':float(np.abs(err).mean()),'MSE_pp2':float((err**2).mean())})
            results[name] = {'study_macro_MAE_pp':float(np.mean([r['MAE_pp'] for r in per_source])),
                'study_balanced_RMSE_pp':math.sqrt(float(np.mean([r['MSE_pp2'] for r in per_source]))),
                'pooled_R2':float(r2_score(y,pred)) if len(y)>1 and np.var(y)>0 else None,'per_source':per_source,'folds':folds}
            predictions.extend({'model':name,'record_id':r['record_id'],'study_group':r['study_group'],'observed':float(y[i]),
                                'out_of_fold_prediction':float(pred[i])} for i,r in enumerate(rows))
        write('metrics.json',results)
        write('predictions.json',predictions)
        write('completion.json',{'status':'completed','synthetic':synthetic,'research_training_performed':not synthetic,'fit_calls':len(fits),
             'convergence_warnings':sum(w['category']=='ConvergenceWarning' for w in warning_log)})
        return results
    except Exception as exc:
        write('completion.json',{'status':'failed','synthetic':synthetic,'exception':type(exc).__name__,'message':str(exc),'fit_calls':len(fits)})
        raise
    finally:
        write('warnings.json',warning_log)
        write('fit_group_audit.json',fits)
