"""Finite nested source validation; cache pair exclusions without test-label reuse."""
from pathlib import Path
import collections,hashlib,itertools,json,math,sys,time,warnings
import numpy as np
from scipy.optimize import minimize
from sklearn.ensemble import RandomForestRegressor,ExtraTreesRegressor
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import Matern
from sklearn.linear_model import Ridge
from xgboost import XGBRegressor
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.run_small_sample_routes import Encoder,weights,metrics
OUT=ROOT/'保持率达标研究_v3_主线与近优组合_20261030'
RUN=OUT/'第一轮_参数与表达'
SEED=20261029
def read(p):return json.loads(Path(p).read_text('utf-8-sig'))
def write(p,x):Path(p).write_bytes((json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode('utf8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def now():
 from datetime import datetime,timezone,timedelta
 return datetime.now(timezone(timedelta(hours=8))).isoformat()

def configurations():
 rf=[dict(n_estimators=160,max_depth=6,min_samples_leaf=2,max_features=1.),dict(n_estimators=240,max_depth=None,min_samples_leaf=1,max_features=1.),dict(n_estimators=240,max_depth=3,min_samples_leaf=1,max_features=.7)]
 gp=[dict(length_scale=2.,alpha=.04,nu=1.5),dict(length_scale=.7,alpha=.01,nu=1.5),dict(length_scale=4.,alpha=.1,nu=2.5)]
 xgb=[dict(n_estimators=160,max_depth=2,learning_rate=.04,reg_lambda=5.,min_child_weight=1.),dict(n_estimators=256,max_depth=1,learning_rate=.03,reg_lambda=10.,min_child_weight=1.),dict(n_estimators=256,max_depth=2,learning_rate=.04,reg_lambda=1.,min_child_weight=.1)]
 et=[dict(n_estimators=160,max_depth=6,min_samples_leaf=1,max_features=1.),dict(n_estimators=240,max_depth=None,min_samples_leaf=1,max_features=1.),dict(n_estimators=240,max_depth=3,min_samples_leaf=2,max_features=.7)]
 families=[('RF_early','RF',rf,False),('RF_static','RF',rf,True),('GPR_early','GPR',gp,False),('GPR_static','GPR',gp,True),('XGB_early','XGB',xgb,False),('XGB_static','XGB',xgb,True),('Ridge_early','Ridge',[dict(alpha=v)for v in[.1,1.,10.]],False),('ExtraTrees_early','ExtraTrees',et,False)]
 configs=[]
 for family,kind,params,static in families:
  for k,p in enumerate(params):
   for view in(['raw']if static or kind=='ExtraTrees'else['raw','continuation']):
    for target in['delta','log_ratio']:
     configs.append(dict(id=f'{family}_p{k}_{view}_{target}',family=family,kind=kind,parameters=p,feature_view=view,static=static,target=target))
 assert len(configs)==72
 direct=[]
 for kind,params in[('RF',rf[:2]),('GPR',gp[:2]),('XGB',xgb[:2])]:
  for k,p in enumerate(params):
   for target in['absolute','log_absolute']:direct.append(dict(id=f'A_{kind}_p{k}_{target}',family='A_'+kind,kind=kind,parameters=p,feature_view='direct',static=False,target=target))
 assert len(direct)==12
 return configs,direct

def features(r,c):
 f=r['features']
 if c['feature_view']in['raw','direct']:v=dict(f)
 else:
  n=f['target_cycle_count'];obs=f['early_observed_cycle_count'];v=dict(last_early_retention_pct=f['last_early_retention_pct'],early_mean_minus_last_pp=f['early_mean_retention_pct']-f['last_early_retention_pct'],early_range_pp=f['early_retention_range_pp'],early_linear_remaining_change_pp=f['early_retention_slope_per_1000_cycles']*(n-obs)/1000,observed_fraction=obs/n,target_cycle_count=n)
 if c['static']:v.update(r['static_features'])
 return dict(r,features=v)
def encode_target(r,c):
 y=r['target'];t=c['target']
 if t=='absolute':return y
 if t=='log_absolute':return math.log(y)
 if t=='delta':return y-r['last_early']
 if t=='log_ratio':return math.log(y/r['last_early'])
 raise ValueError(t)
def decode_target(v,r,c):
 t=c['target']
 if t=='absolute':return float(v)
 if t=='log_absolute':return math.exp(float(v))
 if t=='delta':return r['last_early']+float(v)
 if t=='log_ratio':return r['last_early']*math.exp(float(v))
 raise ValueError(t)
def estimator(c):
 p=c['parameters'];kind=c['kind']
 if kind=='RF':return RandomForestRegressor(**p,random_state=SEED,n_jobs=1)
 if kind=='ExtraTrees':return ExtraTreesRegressor(**p,random_state=SEED,n_jobs=1)
 if kind=='GPR':return GaussianProcessRegressor(kernel=Matern(length_scale=p['length_scale'],nu=p['nu']),alpha=p['alpha'],optimizer=None,normalize_y=False)
 if kind=='Ridge':return Ridge(**p)
 if kind=='XGB':return XGBRegressor(**p,subsample=1.,colsample_bytree=1.,random_state=SEED,n_jobs=1,objective='reg:squarederror')
 raise ValueError(kind)

class Runner:
 def __init__(self,plan):
  self.plan=plan;self.start=time.monotonic();self.n=0;self.failures=[];self.pred=[];self.selection=[];self.cache={};self.ensemble_fits=0
 def fit(self,cohort,c,rows,held):
  held=tuple(sorted(held));key=(cohort,c['id'],held)
  assert key not in self.cache,'Duplicate estimator job'
  train=[r for r in rows if r['source_family']not in held];test=[r for r in rows if r['source_family']in held];event=dict(cohort=cohort,config_id=c['id'],held_sources=list(held),train_row_ids=[r['row_id']for r in train],test_row_ids=[r['row_id']for r in test],train_sources=sorted({r['source_family']for r in train}),fit_index=self.n+1)
  assert not set(event['train_sources'])&set(held)
  assert not{r['curve_id']for r in train if r.get('curve_id')}&{r['curve_id']for r in test if r.get('curve_id')}
  try:
   tr=[features(r,c)for r in train];te=[features(r,c)for r in test];enc=Encoder().fit(tr);x=enc.transform(tr);xt=enc.transform(te);w=weights(train);y=np.array([encode_target(r,c)for r in train]);center=float(np.average(y,weights=w));scale=float(np.sqrt(np.average((y-center)**2,weights=w)))or 1.;model=estimator(c)
   with warnings.catch_warnings(record=True)as caught:
    warnings.simplefilter('always')
    if c['kind']=='GPR':model.fit(x,(y-center)/scale)
    else:model.fit(x,(y-center)/scale,sample_weight=w*len(train))
    output=model.predict(xt)*scale+center
   preds={r['row_id']:decode_target(z,r,c)for z,r in zip(output,test)}
   assert all(math.isfinite(v)for v in preds.values())
   event.update(status='complete',encoder=enc.schema,target_center=center,target_scale=scale,warnings=[str(q.message)for q in caught])
  except Exception as e:
   preds={};event.update(status='failed',error=repr(e));self.failures.append(dict(event))
  self.cache[key]=preds;self.n+=1
  assert self.n<=self.plan['planned_estimator_fits']
  with(RUN/'fit_events.jsonl').open('a',encoding='utf8')as f:f.write(json.dumps(event,ensure_ascii=False,allow_nan=False)+'\n')
  if self.n%25==0 or self.n==1:
   elapsed=round(time.monotonic()-self.start,1);write(RUN/'progress.json',dict(status='running',fits=self.n,planned_fits=self.plan['planned_estimator_fits'],elapsed_seconds=elapsed,cohort=cohort,config=c['id'],failures=len(self.failures)));print(f"{self.n}/{self.plan['planned_estimator_fits']} {cohort} {c['id']} {elapsed}s",flush=True)
 def prediction(self,cohort,method,row,pred,**extra):
  self.pred.append(dict(route=cohort,model=method,row_id=row['row_id'],source_family=row['source_family'],material_key=row['material_key'],curve_id=row.get('curve_id'),sample_name=row['sample_name'],observed=row['target'],predicted=float(pred),**extra))
 def nested(self,cohort,rows,configs):
  sources=sorted({r['source_family']for r in rows});families=sorted({c['family']for c in configs});near=['RF_early','GPR_early','XGB_early','RF_static']
  for c in configs:
   for held in itertools.chain(itertools.combinations(sources,2),[(s,)for s in sources]):self.fit(cohort,c,rows,held)
   for source in sources:
    pred=self.cache[(cohort,c['id'],(source,))]
    for r in rows:
     if r['source_family']==source and r['row_id']in pred:self.prediction(cohort,'fixed::'+c['id'],r,pred[r['row_id']])
  for outer in sources:
   train=[r for r in rows if r['source_family']!=outer];test=[r for r in rows if r['source_family']==outer];scores=[];inner_by_id={}
   for c in configs:
    inner=[]
    for r in train:
     held=tuple(sorted([outer,r['source_family']]));p=self.cache[(cohort,c['id'],held)]
     if r['row_id']in p:inner.append(dict(route=cohort,model=c['id'],row_id=r['row_id'],source_family=r['source_family'],material_key=r['material_key'],curve_id=r['curve_id'],observed=r['target'],predicted=p[r['row_id']]))
    if len(inner)!=len(train):continue
    m=metrics(inner);scores.append(dict(config_id=c['id'],family=c['family'],mae=m['mae'],rmse=m['rmse']));inner_by_id[c['id']]={r['row_id']:r['predicted']for r in inner}
   assert scores,'No complete inner candidate'
   rank=lambda s:(s['mae'],s['rmse'],s['config_id']);selected={fam:min([s for s in scores if s['family']==fam],key=rank)for fam in families if any(s['family']==fam for s in scores)}
   winner=min(scores,key=rank);record=dict(cohort=cohort,outer_source=outer,inner_validation_row_ids=[r['row_id']for r in train],excluded_outer_rows=[r['row_id']for r in test],inner_scores=scores,family_selected=selected,overall_selected=winner)
   methods={'nested_selected':winner,**{'nested_family::'+k:v for k,v in selected.items()}}
   for method,s in methods.items():
    pred=self.cache[(cohort,s['config_id'],(outer,))]
    for r in test:self.prediction(cohort,method,r,pred[r['row_id']],selected_config=s['config_id'])
   if all(fam in selected for fam in near):
    matrix=np.array([[inner_by_id[selected[f]['config_id']][r['row_id']]for f in near]for r in train]);y=np.array([r['target']for r in train]);w=weights(train);uniform=np.ones(len(near))/len(near)
    result=minimize(lambda z:float(np.average((matrix@z-y)**2,weights=w)+np.sum((z-uniform)**2)),uniform,method='SLSQP',bounds=[(0,1)]*len(near),constraints=[dict(type='eq',fun=lambda z:float(sum(z)-1))],options=dict(maxiter=300,ftol=1e-10))
    self.ensemble_fits+=1;z=result.x if result.success else uniform;assert abs(sum(z)-1)<1e-6 and min(z)>-1e-8
    record['ensemble']=dict(families=near,weights=z.tolist(),status='complete'if result.success else'failed_fallback_equal',message=str(result.message),uses_only_inner_validation_row_ids=[r['row_id']for r in train])
    for r in test:
     out=np.array([self.cache[(cohort,selected[f]['config_id'],(outer,))][r['row_id']]for f in near]);self.prediction(cohort,'near4_equal',r,float(out.mean()));self.prediction(cohort,'near4_inner_convex',r,float(out@z))
   self.selection.append(record)
   mean=float(np.average([r['target']for r in train],weights=weights(train)))
   for r in test:
    self.prediction(cohort,'training_mean',r,mean);self.prediction(cohort,'early_persistence',r,r['last_early']);self.prediction(cohort,'early_linear',r,r['linear_forecast'])
  # Cached pair predictions are not independent benchmark rows; keep them only
  # as selection evidence and do not inflate sample count in results.
  for k in list(self.cache):
   if k[0]==cohort:del self.cache[k]
 def direct(self,cohort,rows,configs):
  for c in configs:
   for source in sorted({r['source_family']for r in rows}):
    self.fit(cohort,c,rows,[source]);pred=self.cache[(cohort,c['id'],(source,))]
    for r in rows:
     if r['source_family']==source and r['row_id']in pred:self.prediction(cohort,'fixed::'+c['id'],r,pred[r['row_id']])
  for source in sorted({r['source_family']for r in rows}):
   tr=[r for r in rows if r['source_family']!=source];mean=float(np.average([r['target']for r in tr],weights=weights(tr)))
   for r in rows:
    if r['source_family']==source:self.prediction(cohort,'training_mean',r,mean)

def main():
 plan=read(RUN/'training_plan.json');data=read(RUN/'input_snapshot.json');config=read(RUN/'candidate_configurations.json')
 assert not(RUN/'fit_events.jsonl').exists(),'Do not restart a started pass'
 assert sha(RUN/'input_snapshot.json')==plan['input_sha256']and sha(Path(__file__))==plan['runner_sha256']
 for p,h in read(RUN/'source_protection.json').items():assert sha(ROOT/p)==h,p
 runner=Runner(plan)
 for cohort in plan['B_cohorts']:runner.nested(cohort,data[cohort],config['B'])
 for cohort in plan['A_cohorts']:runner.direct(cohort,data[cohort],config['A'])
 assert runner.n==plan['planned_estimator_fits'];assert runner.ensemble_fits==plan['planned_ensemble_weight_fits']
 write(RUN/'heldout_predictions.json',runner.pred);write(RUN/'nested_selection.json',runner.selection);write(RUN/'fit_failures.json',runner.failures)
 grouped=collections.defaultdict(list)
 for r in runner.pred:grouped[(r['route'],r['model'])].append(r)
 result=[]
 for (cohort,method),a in sorted(grouped.items()):
  s=metrics(a,bootstrap=not method.startswith('fixed::'));base=metrics(grouped[(cohort,'training_mean')]);s.update(route=cohort,model=method,coverage=len(a)==len(data[cohort]),mae_reduction_vs_mean=1-s['mae']/base['mae'])
  s['checks']=dict(r2=s['r2']is not None and s['r2']>.95,mae=s['mae']<=2,rmse=s['rmse']<=3,mape=s['mape_pct']<=5,p90_ape=s['p90_ape_pct']<=10,p90_abs=s['p90_absolute_error']<=5,source_tail=s['source_p90_mae']<=5,baseline=s['mae_reduction_vs_mean']>=.2,coverage=s['coverage'],positive=all(p['predicted']>0 for p in a))
  if cohort.startswith('B_'):
   persist=metrics(grouped[(cohort,'early_persistence')]);s['mae_reduction_vs_persistence']=1-s['mae']/persist['mae'];s['checks']['persistence']=s['mae_reduction_vs_persistence']>=.2
   linear=metrics(grouped[(cohort,'early_linear')]);s['mae_reduction_vs_linear']=1-s['mae']/linear['mae'];s['checks']['linear_baseline']=s['mae_reduction_vs_linear']>=.2
  s['numeric_pass']=all(s['checks'].values());s['reliable_model_accepted']=False;s['untouched_external_test']=False;s['posthoc_fixed_candidate_score']=method.startswith('fixed::');result.append(s)
 for p,h in read(RUN/'source_protection.json').items():assert sha(ROOT/p)==h,p
 write(RUN/'results.json',dict(status='complete',estimator_fits=runner.n,ensemble_weight_fits=runner.ensemble_fits,failed_estimator_fits=len(runner.failures),metrics=result,goal_achieved=False,new_external_sources=0,not_an_untouched_confirmatory_test=True,completed_at=now()))
 write(RUN/'progress.json',dict(status='complete',fits=runner.n,planned_fits=runner.n,ensemble_weight_fits=runner.ensemble_fits,elapsed_seconds=round(time.monotonic()-runner.start,1),research_goal_status='active'))
 for s in result:
  if not s['model'].startswith('fixed::')and s['route']=='B_3E_early20':print(s['model'],round(s['r2'],4),round(s['mae'],4),round(s['rmse'],4),'numeric_pass',s['numeric_pass'])
if __name__=='__main__':main()
