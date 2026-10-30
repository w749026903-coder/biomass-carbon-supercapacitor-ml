"""Finite robust-feature/source-regularized comparison on unchanged approved inputs."""
from pathlib import Path
import argparse,collections,gzip,hashlib,json,math,sys,time,warnings
import numpy as np
from sklearn.ensemble import RandomForestRegressor,ExtraTreesRegressor
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import Matern
from sklearn.linear_model import Ridge
from xgboost import XGBRegressor
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.retention_shape_v4 import predicted,expressed,FIELDS,read,write,sha,now,BASE,SIMPLE,NEAR
from tools.run_small_sample_routes import weights,metrics
P9=BASE/'第九轮_同窗口形状对照';OUT=BASE/'第十轮_稳健表达与来源权重'
SEED=20261029
STATIC={'reported_current_A_g','electrolyte','concentration_mol_L','cycle_voltage_lower_V','cycle_voltage_upper_V','BET_m2_g','reference_electrode'}
def configurations():
 out=[]
 for static in[False,True]:
  for view in['six','shape']:
   suffix=('_static'if static else'_early')
   for ell,alpha in[(2.,.1),(8.,.5)]:out.append(dict(id=f'robust_GPR{suffix}_{view}_ell{ell}_a{alpha}',family='GPR'+suffix,kind='GPR',static=static,view=view,length_scale=ell,alpha=alpha))
   for leaf in[1,2]:out.append(dict(id=f'robust_RF{suffix}_{view}_leaf{leaf}',family='RF'+suffix,kind='RF',static=static,view=view,parameters=dict(n_estimators=240,max_depth=4,min_samples_leaf=leaf,max_features=.7)))
   for depth in[1,2]:out.append(dict(id=f'robust_XGB{suffix}_{view}_depth{depth}',family='XGB'+suffix,kind='XGB',static=static,view=view,parameters=dict(n_estimators=240,max_depth=depth,learning_rate=.03,reg_lambda=20.,min_child_weight=1.)))
 for view in['six','shape']:
  for alpha in[10.,100.]:out.append(dict(id=f'robust_Ridge_early_{view}_a{alpha}',family='Ridge_early',kind='Ridge',static=False,view=view,parameters=dict(alpha=alpha)))
  out.append(dict(id=f'robust_ExtraTrees_early_{view}',family='ExtraTrees_early',kind='ExtraTrees',static=False,view=view,parameters=dict(n_estimators=240,max_depth=4,min_samples_leaf=2,max_features=.7)))
  out.append(dict(id=f'robust_RidgeGP_{view}',family='RidgeGP_residual',kind='RidgeGP',static=False,view=view,length_scale=2.,alpha=.5,mean_ridge_alpha=10.))
 assert len(out)==32
 for c in out:c.update(feature_view='continuation',target='delta',shape_multiplier=.25,static_multiplier=.5)
 return out
class RobustEncoder:
 """Train-only median/IQR and smooth asinh compression; no source IDs as predictors."""
 def __init__(self,c):self.c=c
 def fit(self,rows):
  self.schema=[]
  for k in sorted({k for r in rows for k in r['features']}):
   obs=[r for r in rows if r['features'].get(k)is not None]
   if len(obs)<max(2,int(.15*len(rows)))or len({r['source_family']for r in obs})<3:continue
   vals=[r['features'][k]for r in obs];mult=self.c['shape_multiplier']if k in FIELDS else self.c['static_multiplier']if k in STATIC else 1.
   if all(isinstance(v,str)for v in vals):self.schema.append(dict(field=k,kind='categorical',vocab=sorted(set(vals)),multiplier=mult));continue
   assert all(isinstance(v,(float,int))for v in vals);median=float(np.median(vals));log=all(v>=0 for v in vals)and any(s in k.lower()for s in['bet','volume','current','ratio','cycle_count']);z=np.array([r['features'].get(k)if r['features'].get(k)is not None else median for r in rows]);z=np.log1p(z)if log else z;center=float(np.median(z));iqr=float(np.quantile(z,.75)-np.quantile(z,.25));scale=iqr if iqr>1e-9 else(float(np.std(z))or 1.)
   self.schema.append(dict(field=k,kind='numeric',median=median,log=log,center=center,scale=scale,iqr=iqr,multiplier=mult,compression='asinh'))
  assert self.schema;return self
 def transform(self,rows):
  output=[]
  for r in rows:
   a=[]
   for s in self.schema:
    v=r['features'].get(s['field']);mult=s['multiplier']
    if s['kind']=='categorical':a.extend([mult*float(v==k)for k in s['vocab']]+[mult*float(v not in s['vocab'])])
    else:
     miss=v is None;v=s['median']if miss else v;v=math.log1p(v)if s['log']else v;a.extend([mult*math.asinh((v-s['center'])/s['scale']),mult*float(miss)])
   output.append(a)
  return np.array(output,dtype=float)
def prepare():
 assert not(OUT/'training_plan.json').exists(),'Never overwrite a frozen study'
 assert read(P9/'independent_verification.json')['status']=='passed';OUT.mkdir(exist_ok=True)
 data=read(P9/'input_snapshot.json');configs=configurations();protected={}
 for p,h in read(P9/'source_protection.json').items():
  # Earlier rolling-root snapshots are intentionally superseded. Protect all
  # actual scientific evidence using its already audited current bytes.
  if p.startswith(BASE.name+'/')and len(Path(p).parts)==2:continue
  if p.startswith('docs/')and p not in['docs/knowledge/早期循环辅助保持率与小样本核验_20261029.md']:continue
  protected[p]=sha(ROOT/p)
 for directory in[P9,BASE/'第八轮_原文补证与双电极曲线']:
  for f in directory.rglob('*'):
   if f.is_file():protected[f.relative_to(ROOT).as_posix()]=sha(f)
 for rel in['tools/retention_shape_v4.py','tools/verify_retention_shape_v4.py','tools/retention_v3_optimizer.py','tools/run_small_sample_routes.py',(BASE/'research_goal.json').relative_to(ROOT).as_posix(),(BASE/'checkpoint_04_manifest.json').relative_to(ROOT).as_posix()]:protected[rel]=sha(ROOT/rel)
 reference=dict(path=(P9/'input_snapshot.json').relative_to(ROOT).as_posix(),sha256=sha(P9/'input_snapshot.json'));write(OUT/'input_reference.json',reference);write(OUT/'candidate_configurations.json',configs);write(OUT/'source_protection.json',protected)
 write(OUT/'training_plan.json',dict(frozen_at=now(),runner_sha256=sha(Path(__file__)),input_reference=reference,candidate_sha256=sha(OUT/'candidate_configurations.json'),source_protection_sha256=sha(OUT/'source_protection.json'),counts=read(P9/'training_plan.json')['counts'],splits=read(P9/'training_plan.json')['splits'],new_configurations=32,reused_P9_configurations=32,planned_new_pipeline_fits=8800,planned_additional_ridge_mean_fits=550,planned_new_estimator_fits=9350,planned_reused_control_pipeline_fits=8800,primary='oneSE_family_mean',paired_control='P9_six_oneSE_family_mean',selection='Within each outer training set,rank64 candidates by inner source-weightedMAE,RMSE,ID. Best representative of each9 families. Primary averages family representatives within winnerMAE+SE,SE=sampleSD(per-source innerMAE)/sqrt(G). All8 original families plus RidgeGP retained; old/new/six/shape family winners and joint winner reported; never replace primary using outer scores.',preprocessing='Train-only: same eligibility >=3 sources and15% rows,unweighted median imputation; same original log1p fields; center transformed training median,divideIQR; IQR<=1e-9 falls back to training populationSD or1. Apply smoothasinh. Shape/missing indicators multiplied.25,static/onehot/missing.5,early1. Values/labels never edited or clipped.',GPR_weighting='alpha_i=base_alpha/(source_weight_i*n_train); deliberate source-balanced diagonal regularization,not measured noise variance. FixedMaternnu1.5,optimizerNone. Targetcenter/scale and nonGP sample_weight also source-balanced.',hybrid='Ridge(alpha10) fits standardized delta target ontraining only; MaternGP fits in-sample training residuals with source diagonal regularization. Prediction=sum of mean and residual;2 estimator fits per pipeline. Inner/outer source isolation covers both stages. No copied battery monotonic constraint.',output='specifiedN_capacitance_retention_pct',criteria=read(BASE/'research_goal.json')['criteria'],generalization=read(BASE/'research_goal.json')['generalization'],baselines=['training_mean','early_persistence','early_linear'],new_measurement_inputs=0,new_author_labels=0,new_external_sources=0,scope='Exactly P9 cohorts/rows/author targets/windows; no raw-point new descriptors. Six/shape both remain permitted,2E/3E independent.2point proposal still not applied. A/P6 histories remain.',scientific_status='Exploratory adaptive development round after exposed previous results. Not untouched external confirmation. Robust scaling/source regularization may help but is not presumed successful.',stop='Exactly8800 new pipelinejobs +550 Ridge mean fits=9350 estimators,8800 old pipeline predictions reused. No outcome-driven additions.',goal_status='active'))
 write(OUT/'progress.json',dict(status='frozen_ready',new_pipeline_fits=0,planned_pipeline_fits=8800,new_estimator_fits=0,planned_estimator_fits=9350));print('Frozen32 new +32 reused configs;8800 new pipelines/9350 estimators')
class Experiment:
 def __init__(self,plan):
  self.plan=plan;self.jobs=0;self.estimators=0;self.reused=0;self.failures=[];self.pred=[];self.selection=[];self.start=time.monotonic();self.prior={}
  with gzip.open(P9/'fit_predictions.jsonl.gz','rt',encoding='utf8')as f:
   for line in f:
    q=json.loads(line);k=(q['route'],q['outer_source'],q['config_id'],q['role'],q['inner_fold']);assert k not in self.prior;self.prior[k]=q
 def fit(self,route,c,train,test,outer,role,fold=None):
  event=dict(pipeline_fit_index=self.jobs+1,estimator_fit_index_start=self.estimators+1,route=route,config_id=c['id'],outer_source=outer,role=role,inner_fold=fold,train_sources=sorted({r['source_family']for r in train}),test_sources=sorted({r['source_family']for r in test}),train_row_ids=[r['row_id']for r in train],test_row_ids=[r['row_id']for r in test],estimator_stages=['Ridge_mean','GPR_residual']if c['kind']=='RidgeGP'else[c['kind']])
  assert outer not in event['train_sources']and not set(event['train_sources'])&set(event['test_sources']);assert not{r['curve_id']for r in train}&{r['curve_id']for r in test}
  if role=='inner':assert outer not in event['test_sources']
  try:
   enc=RobustEncoder(c).fit([expressed(r,c,c['view'])for r in train]);x=enc.transform([expressed(r,c,c['view'])for r in train]);xt=enc.transform([expressed(r,c,c['view'])for r in test]);w=weights(train);y=np.array([r['target']-r['last_early']for r in train]);mu=float(np.average(y,weights=w));sd=float(np.sqrt(np.average((y-mu)**2,weights=w)))or 1.;target=(y-mu)/sd;kind=c['kind'];extra={}
   with warnings.catch_warnings(record=True)as caught:
    warnings.simplefilter('always')
    if kind in['GPR','RidgeGP']:
     diag=c['alpha']/(w*len(train));model=GaussianProcessRegressor(kernel=Matern(length_scale=c['length_scale'],nu=1.5),alpha=diag,optimizer=None,normalize_y=False);extra['diagonal_regularization']=diag.tolist()
     if kind=='RidgeGP':
      mean=Ridge(alpha=c['mean_ridge_alpha']);mean.fit(x,target,sample_weight=w*len(train));resid=target-mean.predict(x);model.fit(x,resid);z=mean.predict(xt)+model.predict(xt);extra.update(ridge_intercept=float(mean.intercept_),ridge_coefficients=mean.coef_.tolist(),train_residuals=resid.tolist())
     else:model.fit(x,target);z=model.predict(xt)
    else:
     if kind=='RF':model=RandomForestRegressor(**c['parameters'],random_state=SEED,n_jobs=1)
     elif kind=='ExtraTrees':model=ExtraTreesRegressor(**c['parameters'],random_state=SEED,n_jobs=1)
     elif kind=='Ridge':model=Ridge(**c['parameters'])
     elif kind=='XGB':model=XGBRegressor(**c['parameters'],subsample=1.,colsample_bytree=1.,random_state=SEED,n_jobs=1,objective='reg:squarederror')
     else:raise ValueError(kind)
     model.fit(x,target,sample_weight=w*len(train));z=model.predict(xt)
   p=[predicted(route,c['id'],r,r['last_early']+float(v)*sd+mu,pipeline_fit_index=self.jobs+1)for r,v in zip(test,z)];assert all(math.isfinite(r['predicted'])for r in p);event.update(status='complete',encoder=enc.schema,target_center=mu,target_scale=sd,warnings=[str(v.message)for v in caught],**extra)
  except Exception as exc:p=[];event.update(status='failed',error=repr(exc));self.failures.append(event.copy())
  self.jobs+=1;self.estimators+=len(event['estimator_stages']);assert self.jobs<=8800 and self.estimators<=9350
  with(OUT/'fit_events.jsonl').open('a',encoding='utf8')as f:f.write(json.dumps(event,ensure_ascii=False,allow_nan=False)+'\n')
  record=dict(pipeline_fit_index=self.jobs,route=route,outer_source=outer,config_id=c['id'],role=role,inner_fold=fold,predictions=p)
  with gzip.open(OUT/'fit_predictions.jsonl.gz','at',encoding='utf8')as f:f.write(json.dumps(record,ensure_ascii=False,allow_nan=False)+'\n')
  if self.jobs%100==0 or self.jobs==1:
   elapsed=round(time.monotonic()-self.start,1);write(OUT/'progress.json',dict(status='running',new_pipeline_fits=self.jobs,planned_pipeline_fits=8800,new_estimator_fits=self.estimators,planned_estimator_fits=9350,reused_control_pipeline_fits=self.reused,failed_jobs=len(self.failures),elapsed_seconds=elapsed,route=route,outer_source=outer));print(self.jobs,'/8800',route,elapsed,'s',flush=True)
  return p
 def run_route(self,route,rows,configs,priorcfg):
  for split in self.plan['splits'][route]:
   outer=split['outer_source'];train=[r for r in rows if r['source_family']!=outer];test=[r for r in rows if r['source_family']==outer];scores=[];ins={};final={}
   for c in priorcfg+configs:
    a=[]
    for role,k,held in [('inner',i,hs)for i,hs in enumerate(split['inner_held_sources'])]+[('outer',None,[outer])]:
     if c.get('reused'):
      q=self.prior[(route,outer,c['prior_id'],role,k)];p=q['predictions'];self.reused+=1
     else:
      tr=[r for r in train if role=='outer'or r['source_family']not in held];te=test if role=='outer'else[r for r in train if r['source_family']in held];p=self.fit(route,c,tr,te,outer,role,k)
     if role=='inner':a.extend(p)
     else:final[c['id']]={v['row_id']:v['predicted']for v in p};self.pred.extend(dict(v,model='fixed::'+c['id'])for v in p)
    if len(a)==len(train)and len(final[c['id']])==len(test):
     s=metrics(a);scores.append(dict(config_id=c['id'],family=c['family'],view=c['view'],new=not c.get('reused',False),mae=s['mae'],rmse=s['rmse']));ins[c['id']]=a
   rank=lambda v:(v['mae'],v['rmse'],v['config_id']);win=min(scores,key=rank);families={f:min([s for s in scores if s['family']==f],key=rank)for f in SIMPLE+['RidgeGP_residual']};stat=metrics(ins[win['config_id']]);se=float(np.std([s['mae']for s in stat['per_source']],ddof=1)/math.sqrt(len(stat['per_source'])));eligible=[f for f in SIMPLE+['RidgeGP_residual']if families[f]['mae']<=win['mae']+se+1e-12];assert eligible
   methods=dict(oneSE_family_mean=[families[f]['config_id']for f in eligible],nested_selected=[win['config_id']],near4_equal=[families[f]['config_id']for f in NEAR],all9_family_equal=[families[f]['config_id']for f in families]);methods.update({'nested_family::'+f:[v['config_id']]for f,v in families.items()})
   for subgroup,ss in [('new_only',[s for s in scores if s['new']]),('old_only',[s for s in scores if not s['new']])]:
    ww=min(ss,key=rank);mm=metrics(ins[ww['config_id']]);ee=float(np.std([s['mae']for s in mm['per_source']],ddof=1)/math.sqrt(len(mm['per_source'])));ff={f:min([s for s in ss if s['family']==f],key=rank)for f in{v['family']for v in ss}};methods[subgroup+'_oneSE_family_mean']=[v['config_id']for f,v in sorted(ff.items())if v['mae']<=ww['mae']+ee+1e-12]
   self.selection.append(dict(route=route,outer_source=outer,inner_scores=scores,winner=win['config_id'],family_selected=families,oneSE=se,eligible_families=eligible,methods=methods,inner_row_ids=[r['row_id']for r in ins[win['config_id']]]))
   mean=float(np.average([r['target']for r in train],weights=weights(train)))
   for r in test:
    for method,cids in methods.items():self.pred.append(predicted(route,method,r,np.mean([final[c][r['row_id']]for c in cids])))
    for b,z in dict(training_mean=mean,early_persistence=r['last_early'],early_linear=r['linear_forecast']).items():self.pred.append(predicted(route,b,r,z))
def run():
 plan=read(OUT/'training_plan.json');assert not(OUT/'fit_events.jsonl').exists()and not(OUT/'fit_predictions.jsonl.gz').exists(),'Never restart started study';assert plan['runner_sha256']==sha(Path(__file__));assert plan['input_reference']['sha256']==sha(ROOT/plan['input_reference']['path']);assert plan['candidate_sha256']==sha(OUT/'candidate_configurations.json')
 for p,h in read(OUT/'source_protection.json').items():assert sha(ROOT/p)==h,p
 data=read(ROOT/plan['input_reference']['path']);configs=read(OUT/'candidate_configurations.json');base=read(P9/'candidate_configurations.json');old=[dict(c,id='prior::'+view+'::'+c['id'],prior_id=view+'::'+c['id'],view=view,reused=True)for view in['six','shape']for c in base];ex=Experiment(plan)
 for route,rows in data.items():ex.run_route(route,rows,configs,old)
 assert ex.jobs==8800 and ex.estimators==9350 and ex.reused==8800
 write(OUT/'heldout_predictions.json',ex.pred);write(OUT/'nested_selection.json',ex.selection);write(OUT/'fit_failures.json',ex.failures);group=collections.defaultdict(list)
 # Add exact P9 stable controls for paired, unambiguous interpretation.
 for p in read(P9/'heldout_predictions.json'):
  if p['model']in['six_oneSE_family_mean','shape_oneSE_family_mean']:ex.pred.append(dict(p,model='P9_'+p['model']))
 write(OUT/'heldout_predictions.json',ex.pred)
 for p in ex.pred:group[(p['route'],p['model'])].append(p)
 result=[]
 for(route,method),pp in sorted(group.items()):
  m=metrics(pp,bootstrap=method=='oneSE_family_mean');m.update(route=route,model=method);m['checks']=dict(r2=m['r2']>.95,mae=m['mae']<=2,rmse=m['rmse']<=3,mape=m['mape_pct']<=5,p90_ape=m['p90_ape_pct']<=10,p90_abs=m['p90_absolute_error']<=5,source_tail=m['source_p90_mae']<=5,coverage=len(pp)==len(data[route]),positive=all(p['predicted']>0 for p in pp))
  for b in plan['baselines']:
   v=1-m['mae']/metrics(group[(route,b)])['mae'];m['mae_reduction_vs_'+b]=v;m['checks']['beat_'+b]=v>=.2
  m['numeric_pass']=all(m['checks'].values());m['reliable_model_accepted']=False;m['untouched_external_test']=False;result.append(m)
 for p,h in read(OUT/'source_protection.json').items():assert sha(ROOT/p)==h,p
 write(OUT/'results.json',dict(status='complete',new_pipeline_fits=ex.jobs,new_estimator_fits=ex.estimators,reused_control_pipeline_fits=ex.reused,failed_jobs=len(ex.failures),metrics=result,numeric_pass_count=sum(m['numeric_pass']for m in result),goal_achieved=False,new_external_sources=0,completed_at=now()))
 write(OUT/'progress.json',dict(status='complete',new_pipeline_fits=ex.jobs,new_estimator_fits=ex.estimators,reused_control_pipeline_fits=ex.reused,elapsed_seconds=round(time.monotonic()-ex.start,1),goal_status='active'))
 for m in result:
  if m['model']in['oneSE_family_mean','P9_six_oneSE_family_mean','new_only_oneSE_family_mean']:print(m['route'],m['model'],m['r2'],m['mae'],m['rmse'],m['numeric_pass'],flush=True)
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','run']);args=parser.parse_args();prepare()if args.action=='prepare'else run()
