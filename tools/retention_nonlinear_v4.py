"""Signed nonlinear continuation using only the six approved early summaries."""
from pathlib import Path
import argparse,collections,gzip,hashlib,json,math,sys,time,warnings
import numpy as np
from sklearn.linear_model import Ridge,HuberRegressor
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import DotProduct,Matern
from sklearn.neural_network import MLPRegressor
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.run_small_sample_routes import Encoder,weights,metrics
from tools.retention_v3_optimizer import now
BASE=ROOT/'保持率达标研究_v3_主线与近优组合_20261030';OLD=BASE/'第三轮_扩充来源验证';OUT=BASE/'第六轮_非线性延拓与稳健学习'
NEAR=['RF_early','GPR_early','XGB_early','RF_static']
def read(p):return json.loads(Path(p).read_text('utf8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,x):Path(p).write_bytes((json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode('utf8'))
def new_configs():
 cfg=[]
 for kind in['Ridge_signed','Huber_signed']:
  for p in[.25,.5,1.]:cfg.append(dict(id=kind+'_p'+str(p),family=kind,kind=kind,power=p,target='delta',parameters=dict(alpha=1.)if kind=='Ridge_signed'else dict(epsilon=1.35,alpha=.1,max_iter=500,tol=1e-5)))
 for alpha in[.01,.1,1.]:cfg.append(dict(id='GPR_linear_kernel_a'+str(alpha),family='GPR_linear_kernel',kind='GPR_linear_kernel',power=.5,target='delta',parameters=dict(alpha=alpha,length_scale=2.,nu=1.5,sigma_0=1.)))
 for hidden in[[4],[8],[8,4]]:cfg.append(dict(id='BP_signed_h'+'_'.join(map(str,hidden)),family='BP_signed',kind='BP_signed',power=.5,target='delta',parameters=dict(hidden_layer_sizes=hidden,alpha=10.,solver='lbfgs',max_iter=500,tol=1e-5,random_state=20261029)))
 assert len(cfg)==12;return cfg
def view(r,c):
 f=r['features'];N=f['target_cycle_count'];obs=f['early_observed_cycle_count'];assert 0<obs<N;h=N/obs;factor=h**c['power']-1;last=f['last_early_retention_pct'];level=last-100;drift=f['early_retention_slope_per_1000_cycles']*obs/1000;mean_gap=f['early_mean_retention_pct']-last
 # Split signs in explanatory variables, never clip a target/prediction to100.
 v=dict(early_level_change_pp=level,mean_minus_last_pp=mean_gap,early_range_pp=f['early_retention_range_pp'],early_local_drift_pp=drift,observed_fraction=obs/N,target_cycle_count=N,horizon_log=math.log(h),positive_level_extension_pp=max(0,level)*factor,negative_level_extension_pp=min(0,level)*factor,positive_drift_extension_pp=max(0,drift)*factor,negative_drift_extension_pp=min(0,drift)*factor,mean_gap_extension_pp=mean_gap*factor)
 return dict(r,features=v)
def estimator(c):
 p=c['parameters'];k=c['kind']
 if k=='Ridge_signed':return Ridge(**p)
 if k=='Huber_signed':return HuberRegressor(**p)
 if k=='GPR_linear_kernel':return GaussianProcessRegressor(kernel=DotProduct(sigma_0=p['sigma_0'],sigma_0_bounds='fixed')+Matern(length_scale=p['length_scale'],nu=p['nu']),alpha=p['alpha'],optimizer=None,normalize_y=False)
 if k=='BP_signed':return MLPRegressor(**p)
 raise ValueError(k)
def prepare():
 assert not OUT.exists(),'Never overwrite a frozen study';OUT.mkdir();(OUT/'input_snapshot.json').write_bytes((OLD/'input_snapshot.json').read_bytes());controls=read(OLD/'candidate_configurations.json');new=new_configs();write(OUT/'candidate_configurations.json',dict(reused_controls=controls,new=new))
 protected=read(OLD/'source_protection.json')
 for folder in[OLD,BASE/'第四轮_选模稳定性复核']:
  for f in folder.rglob('*'):
   if f.is_file():protected[f.relative_to(ROOT).as_posix()]=sha(f)
 for p in ['tools/run_small_sample_routes.py','tools/retention_v3_optimizer.py']:
  assert sha(ROOT/p)==protected[p]
 write(OUT/'source_protection.json',protected);prior=read(OLD/'training_plan.json');plan=dict(frozen_at=now(),runner_sha256=sha(Path(__file__)),input_sha256=sha(OUT/'input_snapshot.json'),candidate_sha256=sha(OUT/'candidate_configurations.json'),source_protection_sha256=sha(OUT/'source_protection.json'),splits=prior['splits'],counts=prior['counts'],primary='oneSE_family_mean',secondary=['nested_selected','nested_family::all12','near4_equal'],new_candidates=12,reused_controls=16,new_estimator_fits=2580,reused_estimator_predictions=3440,new_weight_fits=0,all_candidate_equivalent_count=28,criteria=prior['criteria'],hypotheses=['Positive and negative early trend may continue differently; finite power .25/.5/1 changes only algebra of approved summaries.','RobustHuber loss may reduce sensitivity to training errors without deleting any source.','DotProduct+Matern GPR permits a linear trend component alongside local covariance, without changing raw inputs.','Small regularized BP is retained as a distinct nonlinear candidate.','One-standard-error family mean reduces unstable single-winner selection; eligibility uses inner-source errors only.'],input_boundary='Exactly original approved six early summaries; optional static fields appear only in reused controls. No new measurements, no added later points, no window/minimum3/scope changes. All targets remain author values; >100 retained.',data_note='Same already-exposed development sources as phase3, not an independent confirmatory test. Fifth-round candidate sources are excluded entirely.',reuse='Same input bytes and exactly same source/fold splits. Old fit predictions are reused by config/source/fold key; no duplicate fitting or false fit inflation. All new inner and outer predictions saved.',weighting='All new estimators exceptGPR receive source weights; local sklearn1.7.2 MLP.fit supports sample_weight (verified signature). GPR target scaling/evaluation source-weighted, library fit unweighted. Older MLP notes reflect old code, not a permanent API restriction.',stop='Exactly2580 new fits. No added candidate/rule after outer results. Failures/warnings/negative predictions retained and fail gates as appropriate.',references=['https://scikit-learn.org/1.7/modules/generated/sklearn.gaussian_process.kernels.DotProduct.html','https://scikit-learn.org/1.7/modules/generated/sklearn.linear_model.HuberRegressor.html','https://scikit-learn.org/1.7/modules/generated/sklearn.neural_network.MLPRegressor.html'],goal_status='active')
 assert sum(v['sources']for v in plan['counts'].values())*5*12==2580
 write(OUT/'training_plan.json',plan);write(OUT/'progress.json',dict(status='frozen_ready',new_fits=0,planned_fits=2580));print('Frozen12 new candidates, reuse16 controls;2580 new fits')
def run():
 plan=read(OUT/'training_plan.json');assert sha(Path(__file__))==plan['runner_sha256'];assert sha(OUT/'input_snapshot.json')==plan['input_sha256'];assert sha(OUT/'candidate_configurations.json')==plan['candidate_sha256'];assert not(OUT/'fit_events.jsonl').exists(),'Never restart a started study'
 for p,h in read(OUT/'source_protection.json').items():assert sha(ROOT/p)==h,p
 data=read(OUT/'input_snapshot.json');configs=read(OUT/'candidate_configurations.json');allcfg=configs['reused_controls']+configs['new'];archive={};n=0;start=time.monotonic();failed=[]
 with gzip.open(OLD/'fit_predictions.jsonl.gz','rt',encoding='utf8')as f:
  for line in f:
   q=json.loads(line);key=(q['route'],q['outer_source'],q['config_id'],q['role'],q['inner_fold']);assert key not in archive;archive[key]=q['predictions']
 def fit(route,outer,c,role,fold,tr,te):
  nonlocal n
  event=dict(fit_index=n+1,route=route,outer_source=outer,config_id=c['id'],role=role,inner_fold=fold,train_sources=sorted({r['source_family']for r in tr}),test_sources=sorted({r['source_family']for r in te}),train_row_ids=[r['row_id']for r in tr],test_row_ids=[r['row_id']for r in te]);assert outer not in event['train_sources'];assert not set(event['train_sources'])&set(event['test_sources'])
  try:
   en=Encoder().fit([view(r,c)for r in tr]);x=en.transform([view(r,c)for r in tr]);xt=en.transform([view(r,c)for r in te]);w=weights(tr);y=np.array([r['target']-r['last_early']for r in tr]);mu=float(np.average(y,weights=w));scale=float(np.sqrt(np.average((y-mu)**2,weights=w)))or 1.;model=estimator(c)
   with warnings.catch_warnings(record=True)as caught:
    warnings.simplefilter('always')
    if c['kind']=='GPR_linear_kernel':model.fit(x,(y-mu)/scale)
    else:model.fit(x,(y-mu)/scale,sample_weight=w*len(tr))
    out=model.predict(xt)*scale+mu
   pp=[dict(route=route,model=c['id'],row_id=r['row_id'],source_family=r['source_family'],material_key=r['material_key'],curve_id=r['curve_id'],sample_name=r['sample_name'],observed=r['target'],predicted=float(z+r['last_early']),fit_index=event['fit_index'])for r,z in zip(te,out)];assert all(math.isfinite(p['predicted'])for p in pp);event.update(status='complete',encoder=en.schema,target_center=mu,target_scale=scale,warnings=[str(q.message)for q in caught])
  except Exception as ex:pp=[];event.update(status='failed',error=repr(ex));failed.append(event.copy())
  n+=1;assert n<=2580
  with(OUT/'fit_events.jsonl').open('a',encoding='utf8')as f:f.write(json.dumps(event,ensure_ascii=False,allow_nan=False)+'\n')
  with gzip.open(OUT/'fit_predictions.jsonl.gz','at',encoding='utf8')as f:f.write(json.dumps(dict(fit_index=event['fit_index'],route=route,outer_source=outer,config_id=c['id'],role=role,inner_fold=fold,predictions=pp),ensure_ascii=False,allow_nan=False)+'\n')
  archive[(route,outer,c['id'],role,fold)]=pp
  if n%60==0 or n==1:
   elapsed=round(time.monotonic()-start,1);write(OUT/'progress.json',dict(status='running',new_fits=n,planned_fits=2580,elapsed_seconds=elapsed,failures=len(failed),route=route));print(f'{n}/2580 {route} {elapsed}s',flush=True)
 pred=[];selection=[]
 for route,rows in data.items():
  for s in plan['splits'][route]:
   outer=s['outer_source'];tr=[r for r in rows if r['source_family']!=outer];te=[r for r in rows if r['source_family']==outer]
   for c in configs['new']:
    for fold,held in enumerate(s['inner_held_sources']):fit(route,outer,c,'inner',fold,[r for r in tr if r['source_family']not in held],[r for r in tr if r['source_family']in held])
    fit(route,outer,c,'outer',None,tr,te)
   scores=[];inner={};final={}
   for c in allcfg:
    pp=[p for k in range(4)for p in archive[(route,outer,c['id'],'inner',k)]];fo=archive[(route,outer,c['id'],'outer',None)];final[c['id']]=fo
    pred.extend(dict(p,model='fixed::'+c['id'])for p in fo)
    if len(pp)!=len(tr)or len(fo)!=len(te):continue
    mm=metrics(pp);scores.append(dict(config_id=c['id'],family=c['family'],mae=mm['mae'],rmse=mm['rmse']));inner[c['id']]=mm
   rank=lambda q:(q['mae'],q['rmse'],q['config_id']);win=min(scores,key=rank);fam={f:min([q for q in scores if q['family']==f],key=rank)for f in sorted({q['family']for q in scores})};stats=inner[win['config_id']]['per_source'];se=float(np.std([r['mae']for r in stats],ddof=1)/math.sqrt(len(stats)));eligible=[f for f in fam if fam[f]['mae']<=win['mae']+se+1e-12];assert eligible
   selection.append(dict(route=route,outer_source=outer,inner_scores=scores,overall_selected=win,family_selected=fam,oneSE=se,oneSE_eligible_families=eligible))
   for method,v in dict(nested_selected=win,**{'nested_family::'+f:v for f,v in fam.items()}).items():pred.extend(dict(p,model=method,selected_config=v['config_id'])for p in final[v['config_id']])
   fp={k:{p['row_id']:p for p in pp}for k,pp in final.items()}
   for r in te:
    for method,families in [('oneSE_family_mean',eligible),('family_all_equal',sorted(fam)),('near4_equal',NEAR)]:
     z=float(np.mean([fp[fam[f]['config_id']][r['row_id']]['predicted']for f in families]));pred.append(dict(route=route,model=method,row_id=r['row_id'],source_family=r['source_family'],material_key=r['material_key'],curve_id=r['curve_id'],sample_name=r['sample_name'],observed=r['target'],predicted=z))
 # Reuse old baseline predictions, whose training folds and target values are unchanged.
 pred.extend(p for p in read(OLD/'heldout_predictions.json')if p['model']in['training_mean','early_persistence','early_linear'])
 assert n==2580;write(OUT/'heldout_predictions.json',pred);write(OUT/'nested_selection.json',selection);write(OUT/'fit_failures.json',failed);group=collections.defaultdict(list)
 for p in pred:group[(p['route'],p['model'])].append(p)
 summaries=[]
 for(route,method),pp in sorted(group.items()):
  m=metrics(pp,bootstrap=method==plan['primary']);m.update(route=route,model=method);m['checks']=dict(r2=m['r2']>.95,mae=m['mae']<=2,rmse=m['rmse']<=3,mape=m['mape_pct']<=5,p90_ape=m['p90_ape_pct']<=10,p90_abs=m['p90_absolute_error']<=5,source_tail=m['source_p90_mae']<=5,coverage=len(pp)==len(data[route]),positive=all(p['predicted']>0 for p in pp))
  for b in['training_mean','early_persistence','early_linear']:
   z=1-m['mae']/metrics(group[(route,b)])['mae'];m['mae_reduction_vs_'+b]=z;m['checks']['beat_'+b]=z>=.2
  m['numeric_pass']=all(m['checks'].values());m['reliable_model_accepted']=False;summaries.append(m)
 for p,h in read(OUT/'source_protection.json').items():assert sha(ROOT/p)==h,p
 write(OUT/'results.json',dict(status='complete',new_estimator_fits=n,reused_estimator_prediction_fits=3440,new_weight_fits=0,failed_fits=len(failed),metrics=summaries,numeric_pass_count=sum(m['numeric_pass']for m in summaries),new_external_sources=0,goal_achieved=False,completed_at=now()));write(OUT/'progress.json',dict(status='complete',new_fits=n,planned_fits=2580,elapsed_seconds=round(time.monotonic()-start,1),goal_status='active'))
 for m in summaries:
  if m['route']=='B_3E_early20'and not m['model'].startswith('fixed::'):print(m['model'],round(m['r2'],4),round(m['mae'],4),round(m['rmse'],4),flush=True)
if __name__=='__main__':
 pa=argparse.ArgumentParser();pa.add_argument('action',choices=['prepare','run']);a=pa.parse_args();prepare()if a.action=='prepare'else run()
