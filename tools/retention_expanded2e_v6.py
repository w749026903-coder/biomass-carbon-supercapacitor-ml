"""Expanded2E finite validation; P9 source-isolated engine, new frozen cohorts.
No old prediction is reused. All original failures and hard sources are retained.
"""
from pathlib import Path
import collections,gzip,hashlib,json,math,sys,time,warnings
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.retention_shape_v4 import expressed,predicted,Encoder,weights,metrics,encode_target,decode_target,estimator,read,write,sha,now,FIELDS,SIMPLE,NEAR
BASE=ROOT/'保持率达标研究_v3_主线与近优组合_20261030';OUT=BASE/'第十二轮_扩充双电极来源验证'

class Experiment:
 def __init__(self,plan):
  self.plan=plan;self.n=0;self.reused=0;self.pred=[];self.selections=[];self.failed=[];self.start=time.monotonic();self.archive={}
 def fit(self,route,c,view,train,test,outer,role,fold=None):
  key=(route,outer,c['id'],role,fold);reuse=False;cid=view+'::'+c['id']
  if reuse:
   q=self.archive[key];p=q['predictions'];assert {v['row_id']for v in p}=={v['row_id']for v in test};self.reused+=1
   record=dict(q,config_id=cid,view=view,reused=True,source_fit_index=q['fit_index'],fit_index=None)
  else:
   event=dict(fit_index=self.n+1,route=route,config_id=cid,base_config_id=c['id'],view=view,outer_source=outer,role=role,inner_fold=fold,train_sources=sorted({r['source_family']for r in train}),test_sources=sorted({r['source_family']for r in test}),train_row_ids=[r['row_id']for r in train],test_row_ids=[r['row_id']for r in test])
   assert outer not in event['train_sources'] and not set(event['train_sources'])&set(event['test_sources'])
   assert not{r['curve_id']for r in train}&{r['curve_id']for r in test}
   if role=='inner':assert outer not in event['test_sources']
   try:
    a=[expressed(r,c,view)for r in train];b=[expressed(r,c,view)for r in test];enc=Encoder().fit(a);x=enc.transform(a);xt=enc.transform(b);w=weights(train);y=np.array([encode_target(r,c)for r in train]);mu=float(np.average(y,weights=w));sd=float(np.sqrt(np.average((y-mu)**2,weights=w)))or 1.;model=estimator(c)
    with warnings.catch_warnings(record=True)as caught:
     warnings.simplefilter('always')
     if c['kind']=='GPR':model.fit(x,(y-mu)/sd)
     else:model.fit(x,(y-mu)/sd,sample_weight=w*len(train))
     z=model.predict(xt)*sd+mu
    p=[predicted(route,cid,r,decode_target(v,r,c),fit_index=event['fit_index'])for r,v in zip(test,z)];assert all(math.isfinite(v['predicted'])for v in p)
    event.update(status='complete',encoder=enc.schema,target_center=mu,target_scale=sd,shape_fields_retained=[s['field']for s in enc.schema if s['field']in FIELDS],warnings=[str(v.message)for v in caught])
   except Exception as exc:
    p=[];event.update(status='failed',error=repr(exc));self.failed.append(event.copy())
   self.n+=1;assert self.n<=self.plan['planned_new_fits']
   with(OUT/'fit_events.jsonl').open('a',encoding='utf8')as f:f.write(json.dumps(event,ensure_ascii=False,allow_nan=False)+'\n')
   record=dict(fit_index=event['fit_index'],route=route,config_id=cid,view=view,outer_source=outer,role=role,inner_fold=fold,predictions=p,reused=False)
   if self.n%80==0 or self.n==1:
    elapsed=round(time.monotonic()-self.start,1);write(OUT/'progress.json',dict(status='running',new_fits=self.n,planned_new_fits=6400,reused_control_fits=self.reused,failures=len(self.failed),elapsed_seconds=elapsed,route=route,outer_source=outer));print(self.n,'/6400',route,elapsed,'s',flush=True)
  with gzip.open(OUT/'fit_predictions.jsonl.gz','at',encoding='utf8')as f:f.write(json.dumps(record,ensure_ascii=False,allow_nan=False)+'\n')
  return p
 def run_route(self,route,rows,cfg):
  for split in self.plan['splits'][route]:
   outer=split['outer_source'];train=[r for r in rows if r['source_family']!=outer];test=[r for r in rows if r['source_family']==outer];scores=[];inner={};final={}
   for view in['six','shape']:
    for c in cfg:
     cid=view+'::'+c['id'];a=[]
     for k,held in enumerate(split['inner_held_sources']):a.extend(self.fit(route,c,view,[r for r in train if r['source_family']not in held],[r for r in train if r['source_family']in held],outer,'inner',k))
     p=self.fit(route,c,view,train,test,outer,'outer');final[cid]={v['row_id']:v['predicted']for v in p};self.pred.extend(dict(v,model='fixed::'+cid)for v in p)
     if len(a)!=len(train)or len(p)!=len(test):continue
     m=metrics(a);scores.append(dict(config_id=cid,family=c['family'],view=view,mae=m['mae'],rmse=m['rmse']));inner[cid]=a
   rank=lambda v:(v['mae'],v['rmse'],v['config_id']);methods={};details={}
   for view in['six','shape','joint']:
    ss=[s for s in scores if view=='joint'or s['view']==view];assert ss
    families={f:min([s for s in ss if s['family']==f],key=rank)for f in SIMPLE};win=min(ss,key=rank);ms=metrics(inner[win['config_id']]);se=float(np.std([s['mae']for s in ms['per_source']],ddof=1)/math.sqrt(len(ms['per_source'])));eligible=[f for f in SIMPLE if families[f]['mae']<=win['mae']+se+1e-12];assert eligible
    methods[view+'_nested_selected']=[win['config_id']];methods[view+'_oneSE_family_mean']=[families[f]['config_id']for f in eligible];methods[view+'_near4_equal']=[families[f]['config_id']for f in NEAR]
    for family,v in families.items():methods[view+'_family::'+family]=[v['config_id']]
    details[view]=dict(winner=win['config_id'],family_selected=families,inner_source_mae_standard_error=se,eligible_oneSE_families=eligible,selected_oneSE_configs=methods[view+'_oneSE_family_mean'],inner_row_ids=[r['row_id']for r in inner[win['config_id']]])
   self.selections.append(dict(route=route,outer_source=outer,scores=scores,views=details,methods=methods))
   mean=float(np.average([r['target']for r in train],weights=weights(train)))
   for r in test:
    for method,cs in methods.items():self.pred.append(predicted(route,method,r,np.mean([final[c][r['row_id']]for c in cs])))
    for name,z in dict(training_mean=mean,early_persistence=r['last_early'],early_linear=r['linear_forecast']).items():self.pred.append(predicted(route,name,r,z))

def run():
 plan=read(OUT/'training_plan.json');assert set(plan['counts'])=={'B_2E_early20','B_2E_early10'};assert not(OUT/'fit_events.jsonl').exists() and not(OUT/'fit_predictions.jsonl.gz').exists(),'Do not restart a started round'
 assert sha(Path(__file__))==plan['runner_sha256'] and sha(OUT/'input_snapshot.json')==plan['input_sha256'] and sha(OUT/'candidate_configurations.json')==plan['candidate_sha256']
 for p,h in read(OUT/'source_protection.json').items():assert sha(ROOT/p)==h,p
 data=read(OUT/'input_snapshot.json');cfg=read(OUT/'candidate_configurations.json');exp=Experiment(plan)
 for route,rows in data.items():exp.run_route(route,rows,cfg)
 assert exp.n==6400 and exp.reused==0
 write(OUT/'heldout_predictions.json',exp.pred);write(OUT/'nested_selection.json',exp.selections);write(OUT/'fit_failures.json',exp.failed);grouped=collections.defaultdict(list)
 for p in exp.pred:grouped[(p['route'],p['model'])].append(p)
 result=[]
 for(route,method),a in sorted(grouped.items()):
  m=metrics(a,bootstrap=method in['shape_oneSE_family_mean','six_oneSE_family_mean']);m.update(route=route,model=method);m['checks']=dict(r2=m['r2']is not None and m['r2']>.95,mae=m['mae']<=2,rmse=m['rmse']<=3,mape=m['mape_pct']<=5,p90_ape=m['p90_ape_pct']<=10,p90_abs=m['p90_absolute_error']<=5,source_tail=m['source_p90_mae']<=5,coverage=len(a)==len(data[route]),positive=all(p['predicted']>0 for p in a))
  for base in plan['baselines']:
   z=1-m['mae']/metrics(grouped[(route,base)])['mae'];m['mae_reduction_vs_'+base]=z;m['checks']['beat_'+base]=z>=.2
  m['numeric_pass']=all(m['checks'].values());m['at_least10_sources']=m['sources']>=10;m['untouched_external_test']=False;m['reliable_model_accepted']=False;result.append(m)
 paired=[]
 for route in data:
  a=metrics(grouped[(route,'shape_oneSE_family_mean')])['per_source'];b={s['source']:s['mae']for s in metrics(grouped[(route,'six_oneSE_family_mean')])['per_source']};diff=np.array([s['mae']-b[s['source']]for s in a]);rng=np.random.default_rng(20261030);means=np.array([rng.choice(diff,len(diff),replace=True).mean()for _ in range(5000)])
  paired.append(dict(route=route,shape_minus_six_MAE_pp=float(diff.mean()),source_bootstrap95=np.quantile(means,[.025,.975]).tolist(),sources=len(diff),interpretation='Negative favours shape; exploratory paired development-source estimate, not independent external confirmation.'))
 write(OUT/'paired_comparison.json',paired)
 for p,h in read(OUT/'source_protection.json').items():assert sha(ROOT/p)==h,p
 write(OUT/'results.json',dict(status='complete',new_estimator_fits=exp.n,reused_control_fits=exp.reused,ensemble_weight_fits=0,failed_estimator_fits=len(exp.failed),metrics=result,numeric_pass_count=sum(m['numeric_pass']for m in result),goal_achieved=False,new_external_sources=0,completed_at=now(),primary=plan['primary'],paired_comparison=paired))
 write(OUT/'progress.json',dict(status='complete',new_fits=exp.n,planned_new_fits=6400,reused_control_fits=exp.reused,elapsed_seconds=round(time.monotonic()-exp.start,1),goal_status='active'))
 for m in result:
  if m['model']in['shape_oneSE_family_mean','six_oneSE_family_mean','joint_oneSE_family_mean']:print(m['route'],m['model'],m['r2'],m['mae'],m['rmse'],'numericpass',m['numeric_pass'],flush=True)

if __name__=='__main__':run()
