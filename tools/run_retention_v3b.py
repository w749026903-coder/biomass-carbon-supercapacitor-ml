"""Expanded existing-source experiment with every inner prediction retained."""
from pathlib import Path
import collections,gzip,hashlib,json,math,sys,time,warnings
import numpy as np
from scipy.optimize import minimize
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.retention_v3_optimizer import features,encode_target,decode_target,estimator,now
from tools.run_small_sample_routes import Encoder,weights,metrics
BASE=ROOT/'保持率达标研究_v3_主线与近优组合_20261030'
RUN=BASE/'第三轮_扩充来源验证'
NEAR=['RF_early','GPR_early','XGB_early','RF_static']
def read(p):return json.loads(Path(p).read_text('utf8'))
def write(p,x):Path(p).write_bytes((json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode('utf8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def row_prediction(route,method,r,p,**extra):
 return dict(route=route,model=method,row_id=r['row_id'],source_family=r['source_family'],material_key=r['material_key'],curve_id=r['curve_id'],sample_name=r['sample_name'],observed=r['target'],predicted=float(p),**extra)
class Experiment:
 def __init__(self,plan):self.plan=plan;self.fits=0;self.start=time.monotonic();self.pred=[];self.selection=[];self.failed=[];self.ensemble_fits=0
 def fit(self,route,c,train,test,outer,role,innerfold=None):
  event=dict(fit_index=self.fits+1,route=route,config_id=c['id'],role=role,outer_source=outer,inner_fold=innerfold,train_sources=sorted({r['source_family']for r in train}),test_sources=sorted({r['source_family']for r in test}),train_row_ids=[r['row_id']for r in train],test_row_ids=[r['row_id']for r in test])
  assert outer not in event['train_sources']
  assert not set(event['train_sources'])&set(event['test_sources'])
  assert not {r['curve_id']for r in train}&{r['curve_id']for r in test}
  if role=='inner':assert outer not in event['test_sources']
  try:
   enc=Encoder().fit([features(r,c)for r in train]);x=enc.transform([features(r,c)for r in train]);xt=enc.transform([features(r,c)for r in test]);w=weights(train);y=np.array([encode_target(r,c)for r in train]);center=float(np.average(y,weights=w));scale=float(np.sqrt(np.average((y-center)**2,weights=w)))or 1.;model=estimator(c)
   with warnings.catch_warnings(record=True)as caught:
    warnings.simplefilter('always')
    if c['kind']=='GPR':model.fit(x,(y-center)/scale)
    else:model.fit(x,(y-center)/scale,sample_weight=w*len(train))
    out=model.predict(xt)*scale+center
   result=[row_prediction(route,c['id'],r,decode_target(z,r,c),fit_index=event['fit_index'])for r,z in zip(test,out)];assert all(math.isfinite(r['predicted'])for r in result)
   event.update(status='complete',encoder=enc.schema,target_center=center,target_scale=scale,warnings=[str(w.message)for w in caught])
  except Exception as e:
   result=[];event.update(status='failed',error=repr(e));self.failed.append(event.copy())
  self.fits+=1;assert self.fits<=self.plan['planned_estimator_fits']
  with(RUN/'fit_events.jsonl').open('a',encoding='utf8')as f:f.write(json.dumps(event,ensure_ascii=False,allow_nan=False)+'\n')
  with gzip.open(RUN/'fit_predictions.jsonl.gz','at',encoding='utf8')as f:
   f.write(json.dumps(dict(fit_index=event['fit_index'],route=route,config_id=c['id'],outer_source=outer,role=role,inner_fold=innerfold,predictions=result),ensure_ascii=False,allow_nan=False)+'\n')
  if self.fits%40==0 or self.fits==1:
   elapsed=round(time.monotonic()-self.start,1);write(RUN/'progress.json',dict(status='running',fits=self.fits,planned_fits=self.plan['planned_estimator_fits'],elapsed_seconds=elapsed,failures=len(self.failed),route=route,outer_source=outer));print(f'{self.fits}/{self.plan["planned_estimator_fits"]} {route} {elapsed}s',flush=True)
  return result
 def run(self,route,rows,configs):
  for split in self.plan['splits'][route]:
   outer=split['outer_source'];train=[r for r in rows if r['source_family']!=outer];test=[r for r in rows if r['source_family']==outer];inner={};final={};scores=[]
   for c in configs:
    a=[]
    for k,held in enumerate(split['inner_held_sources']):
     tr=[r for r in train if r['source_family']not in held];va=[r for r in train if r['source_family']in held];a.extend(self.fit(route,c,tr,va,outer,'inner',k))
    final[c['id']]=self.fit(route,c,train,test,outer,'outer')
    for p in final[c['id']]:self.pred.append(dict(p,model='fixed::'+c['id']))
    if len(a)!=len(train)or len(final[c['id']])!=len(test):continue
    assert len({r['row_id']for r in a})==len(train)
    m=metrics(a);scores.append(dict(config_id=c['id'],family=c['family'],mae=m['mae'],rmse=m['rmse']));inner[c['id']]={r['row_id']:r['predicted']for r in a}
   assert scores,'No complete candidate'
   rank=lambda v:(v['mae'],v['rmse'],v['config_id']);selected={f:min([s for s in scores if s['family']==f],key=rank)for f in sorted({c['family']for c in configs})};win=min(scores,key=rank)
   for method,s in dict(nested_selected=win,**{'nested_family::'+f:v for f,v in selected.items()}).items():
    self.pred.extend(dict(p,model=method,selected_config=s['config_id'])for p in final[s['config_id']])
   matrix=np.array([[inner[selected[f]['config_id']][r['row_id']]for f in NEAR]for r in train]);y=np.array([r['target']for r in train]);w=weights(train);unif=np.ones(4)/4
   opt=minimize(lambda z:float(np.average((matrix@z-y)**2,weights=w)+np.sum((z-unif)**2)),unif,method='SLSQP',bounds=[(0,1)]*4,constraints=[dict(type='eq',fun=lambda z:float(sum(z)-1))],options=dict(maxiter=300,ftol=1e-10));self.ensemble_fits+=1;z=opt.x if opt.success else unif
   assert abs(sum(z)-1)<1e-6 and min(z)>-1e-8
   fp={k:{r['row_id']:r['predicted']for r in v}for k,v in final.items()}
   mean=float(np.average([r['target']for r in train],weights=weights(train)))
   for r in test:
    values=np.array([fp[selected[f]['config_id']][r['row_id']]for f in NEAR]);self.pred.extend([row_prediction(route,'near4_equal',r,values.mean()),row_prediction(route,'near4_inner_convex',r,values@z),row_prediction(route,'training_mean',r,mean),row_prediction(route,'early_persistence',r,r['last_early']),row_prediction(route,'early_linear',r,r['linear_forecast'])])
   self.selection.append(dict(route=route,outer_source=outer,inner_scores=scores,family_selected=selected,overall_selected=win,inner_row_ids=[r['row_id']for r in train],ensemble_weights=z.tolist(),ensemble_status=str(opt.message)))
def main():
 plan=read(RUN/'training_plan.json');assert not(RUN/'fit_events.jsonl').exists(),'Do not restart a started phase'
 assert sha(Path(__file__))==plan['runner_sha256']and sha(RUN/'input_snapshot.json')==plan['input_sha256']and sha(RUN/'candidate_configurations.json')==plan['candidate_sha256']
 for p,h in read(RUN/'source_protection.json').items():assert sha(ROOT/p)==h,p
 data=read(RUN/'input_snapshot.json');cfg=read(RUN/'candidate_configurations.json');exp=Experiment(plan)
 for route,rows in data.items():exp.run(route,rows,cfg)
 assert exp.fits==plan['planned_estimator_fits']and exp.ensemble_fits==plan['planned_ensemble_fits']
 write(RUN/'heldout_predictions.json',exp.pred);write(RUN/'nested_selection.json',exp.selection);write(RUN/'fit_failures.json',exp.failed)
 grouped=collections.defaultdict(list)
 for p in exp.pred:grouped[(p['route'],p['model'])].append(p)
 result=[]
 for(route,method),a in sorted(grouped.items()):
  m=metrics(a,bootstrap=not method.startswith('fixed::'));m.update(route=route,model=method)
  m['checks']=dict(r2=m['r2']is not None and m['r2']>.95,mae=m['mae']<=2,rmse=m['rmse']<=3,mape=m['mape_pct']<=5,p90_ape=m['p90_ape_pct']<=10,p90_abs=m['p90_absolute_error']<=5,source_tail=m['source_p90_mae']<=5,complete_coverage=len(a)==len(data[route]),positive=all(p['predicted']>0 for p in a))
  for base in['training_mean','early_persistence','early_linear']:
   bm=metrics(grouped[(route,base)]);improvement=1-m['mae']/bm['mae'];m['mae_reduction_vs_'+base]=improvement;m['checks']['beat_'+base]=improvement>=.2
  m['numeric_pass']=all(m['checks'].values());m['reliable_model_accepted']=False;m['untouched_external_test']=False;result.append(m)
 for p,h in read(RUN/'source_protection.json').items():assert sha(ROOT/p)==h,p
 write(RUN/'results.json',dict(status='complete',estimator_fits=exp.fits,ensemble_weight_fits=exp.ensemble_fits,failed_estimator_fits=len(exp.failed),metrics=result,goal_achieved=False,new_external_sources=0,exploratory_reused_sources=True,inner_predictions_saved=True,completed_at=now()))
 write(RUN/'progress.json',dict(status='complete',fits=exp.fits,planned_fits=exp.fits,ensemble_weight_fits=exp.ensemble_fits,elapsed_seconds=round(time.monotonic()-exp.start,1),research_goal_status='active'))
 for m in result:
  if m['route']=='B_3E_early20'and not m['model'].startswith('fixed::'):print(m['model'],round(m['r2'],4),round(m['mae'],4),round(m['rmse'],4),'numeric_pass',m['numeric_pass'],flush=True)
if __name__=='__main__':main()
