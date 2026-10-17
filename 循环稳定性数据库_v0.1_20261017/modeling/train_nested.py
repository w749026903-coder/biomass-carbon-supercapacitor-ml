"""Future nested grouped benchmark. No fitting occurs on import or default invocation."""
import collections,hashlib,json,math,warnings
from prepare_dataset import ROOT,CONTRACT,load_ready

def source_disjoint(train_rows,test_rows):
 for key in ['study_group','paper_id','material_id','cycle_test_id']:
  if {r[key] for r in train_rows}&{r[key] for r in test_rows}:raise ValueError('Train/test leakage: '+key)

def train(feature_set='plus_BET'):
 rows=load_ready()
 if not rows:raise ValueError('No admitted records. Candidate exports must not bypass record admission.')
 groups=sorted({r['study_group'] for r in rows})
 if len(groups)<2:raise ValueError('Grouped validation needs at least two groups; this is not an adequacy threshold.')
 if feature_set not in ['protocol_only','plus_BET']:raise ValueError('Unknown feature set')
 output=ROOT/('modeling/benchmark_run_'+feature_set)
 if output.exists():raise FileExistsError('Preserve earlier run; select a new run version.')
 import numpy as np
 from sklearn.compose import ColumnTransformer,TransformedTargetRegressor
 from sklearn.dummy import DummyRegressor
 from sklearn.ensemble import RandomForestRegressor
 from sklearn.impute import SimpleImputer
 from sklearn.linear_model import Ridge
 from sklearn.metrics import r2_score
 from sklearn.model_selection import GroupKFold,ParameterSampler
 from sklearn.neural_network import MLPRegressor
 from sklearn.pipeline import Pipeline
 from sklearn.preprocessing import OneHotEncoder,StandardScaler
 from xgboost import XGBRegressor
 num=[k for k in CONTRACT['numeric_features'] if feature_set=='plus_BET' or k!='BET_m2_g'];cat=CONTRACT['categorical_features'];features=num+cat
 assert not set(features)&set(CONTRACT['forbidden_features'])
 X=np.array([[np.nan if r.get(k) is None else r[k] for k in features] for r in rows],dtype=object)
 y=np.array([r['retention_pct'] for r in rows],dtype=float);g=np.array([r['study_group'] for r in rows])
 spaces={'mean_baseline':{},'ridge':{'alpha':[0.1,1.,10.,100.]},
 'random_forest':{'max_depth':[3,5,None],'min_samples_leaf':[1,2,4],'max_features':[0.7,1.0]},
 'xgboost':{'max_depth':[2,3],'n_estimators':[150,300],'learning_rate':[0.03,0.08],'min_child_weight':[2,5],'subsample':[0.7,1.0],'colsample_bytree':[0.7,1.0],'reg_lambda':[1.,10.],'reg_alpha':[0.,0.1]},
 'mlp':{'hidden_layer_sizes':[(8,),(16,),(16,8)],'alpha':[0.001,0.01,0.1,1.]}}
 defaults={'mean_baseline':{},'ridge':{'alpha':1.},'random_forest':{'max_depth':3,'min_samples_leaf':2,'max_features':1.},'xgboost':{'max_depth':2,'n_estimators':150,'learning_rate':0.03,'min_child_weight':5,'reg_lambda':10.},'mlp':{'hidden_layer_sizes':(8,),'alpha':0.1}}
 def make(name,params):
  if name=='mean_baseline':est=DummyRegressor(strategy='mean')
  elif name=='ridge':est=Ridge(**params)
  elif name=='random_forest':est=RandomForestRegressor(n_estimators=300,random_state=20261017,n_jobs=1,**params)
  elif name=='xgboost':est=XGBRegressor(objective='reg:squarederror',tree_method='hist',random_state=20261017,n_jobs=1,**params)
  else:est=MLPRegressor(solver='lbfgs',early_stopping=False,max_iter=2000,random_state=20261017,**params)
  prep=ColumnTransformer([
  ('numeric',Pipeline([('imputer',SimpleImputer(strategy='median',add_indicator=True,keep_empty_features=True)),('scale',StandardScaler())]),list(range(len(num)))),
  ('categorical',OneHotEncoder(handle_unknown='ignore',sparse_output=False),list(range(len(num),len(features))))])
  pipe=Pipeline([('features',prep),('estimator',est)])
  return TransformedTargetRegressor(regressor=pipe,transformer=StandardScaler()) if name=='mlp' else pipe
 warning_log=[]
 def fit_predict(name,params,tr,te):
  source_disjoint([rows[i] for i in tr],[rows[i] for i in te])
  counts=collections.Counter(g[tr]);weights=np.array([1/counts[s] for s in g[tr]]);weights*=len(tr)/weights.sum()
  model=make(name,params)
  with warnings.catch_warnings(record=True) as observed:
   warnings.simplefilter('always');model.fit(X[tr],y[tr],estimator__sample_weight=weights);pred=model.predict(X[te])
  warning_log.extend({'model':name,'category':w.category.__name__,'message':str(w.message)} for w in observed)
  if not np.isfinite(pred).all():raise ValueError('Nonfinite predictions require investigation.')
  return pred
 def macro_mae(indices,pred):
  return float(np.mean([np.mean(np.abs(y[indices][g[indices]==s]-pred[g[indices]==s])) for s in sorted(set(g[indices]))]))
 outer=GroupKFold(n_splits=min(5,len(groups)),shuffle=True,random_state=20261017)
 splits=list(outer.split(X,y,g));results={};predictions=[];assignments=[]
 for fold,(tr,te) in enumerate(splits):
  source_disjoint([rows[i] for i in tr],[rows[i] for i in te])
  assignments.extend({'record_id':rows[i]['record_id'],'outer_test_fold':fold,'study_group':rows[i]['study_group']} for i in te)
 for name in CONTRACT['models']:
  pred=np.empty(len(rows));folds=[]
  budget=min(8,math.prod(len(v) for v in spaces[name].values()))
  candidates=list(ParameterSampler(spaces[name],n_iter=budget,random_state=20261017)) if spaces[name] else [{}]
  for fold,(tr,te) in enumerate(splits):
   tr_groups=sorted(set(g[tr]));selection=[]
   if len(tr_groups)>=2 and len(candidates)>1:
    inner=GroupKFold(n_splits=min(3,len(tr_groups)),shuffle=True,random_state=20261017+fold)
    inner_splits=[(tr[it],tr[iv]) for it,iv in inner.split(X[tr],y[tr],g[tr])]
    for params in candidates:
     ipred={}
     for it,iv in inner_splits:
      for idx,val in zip(iv,fit_predict(name,params,it,iv)):ipred[int(idx)]=float(val)
     idx=np.array(sorted(ipred));score=macro_mae(idx,np.array([ipred[int(i)] for i in idx]))
     selection.append({'parameters':params,'inner_source_macro_MAE_pp':score})
    chosen=min(selection,key=lambda x:x['inner_source_macro_MAE_pp'])['parameters']
   else:chosen=defaults[name]
   pred[te]=fit_predict(name,chosen,tr,te)
   folds.append({'fold':fold,'train_groups':sorted(set(g[tr])),'test_groups':sorted(set(g[te])),'chosen_parameters':chosen,'inner_search':selection,'outer_test_used_for_tuning':False})
  per_source=[]
  for group in groups:
   sel=g==group;err=y[sel]-pred[sel]
   per_source.append({'study_group':group,'rows':int(sel.sum()),'MAE_pp':float(np.abs(err).mean()),'MSE_pp2':float((err**2).mean())})
  results[name]={'study_macro_MAE_pp':sum(r['MAE_pp'] for r in per_source)/len(per_source),'study_balanced_RMSE_pp':math.sqrt(sum(r['MSE_pp2'] for r in per_source)/len(per_source)),'pooled_R2':float(r2_score(y,pred)) if len(y)>1 and np.var(y)>0 else None,'per_source':per_source,'folds':folds}
  predictions.extend({'model':name,'record_id':r['record_id'],'study_group':r['study_group'],'observed':float(y[i]),'out_of_fold_prediction':float(pred[i])} for i,r in enumerate(rows))
 output.mkdir()
 for filename,data in [('metrics.json',results),('predictions.json',predictions),('fold_assignments.json',assignments),('warnings.json',warning_log),('input_fingerprints.json',{'feature_set':feature_set,'features':features,'database_sha256':hashlib.sha256((ROOT/'cycling_v0_1.sqlite').read_bytes()).hexdigest(),'contract_sha256':hashlib.sha256((ROOT/'modeling/model_contract.json').read_bytes()).hexdigest()})]:
  (output/filename).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
