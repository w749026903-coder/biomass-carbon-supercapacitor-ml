"""Approved paired six-summary/shape experiment; finite, source-isolated and archived."""
from pathlib import Path
import argparse,collections,gzip,hashlib,json,math,sys,time,warnings
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.retention_v3_optimizer import features,encode_target,decode_target,estimator,now
from tools.run_small_sample_routes import Encoder,weights,metrics
from data.retention_research import load_windows
from data.retention_shape import FIELDS,shape_summaries
BASE=ROOT/'保持率达标研究_v3_主线与近优组合_20261030';OLD=BASE/'第三轮_扩充来源验证';OUT=BASE/'第九轮_同窗口形状对照'
NEAR=['RF_early','GPR_early','XGB_early','RF_static']
SIMPLE=['Ridge_early','RF_early','ExtraTrees_early','GPR_early','XGB_early','RF_static','GPR_static','XGB_static']
SIX=['last_early_retention_pct','early_mean_retention_pct','early_retention_slope_per_1000_cycles','early_retention_range_pp','early_observed_cycle_count','target_cycle_count']
def read(p):return json.loads(Path(p).read_text('utf8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,x):Path(p).write_bytes((json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode('utf8'))
def expressed(r,c,view):
 a=features(r,c)
 if view=='shape':a=dict(a,features=dict(a['features'],**r['shape_features']))
 return a
def predicted(route,method,r,z,**kw):return dict(route=route,model=method,row_id=r['row_id'],source_family=r['source_family'],material_key=r['material_key'],curve_id=r['curve_id'],sample_name=r['sample_name'],observed=r['target'],predicted=float(z),**kw)
def prepare():
 assert not OUT.exists(),'Never overwrite a planned round'
 auth=read(BASE/'第七轮_同窗口形状表达提案/authorization_20261030.json');assert auth['minimum2_proposal_authorized'] is False
 assert read(BASE/'第八轮_原文补证与双电极曲线/independent_verification_v3c.json')['status']=='passed'
 data={};counts={};old=read(OLD/'input_snapshot.json');splits={};oldsplit=read(OLD/'training_plan.json')['splits']
 for system in['3E','2E']:
  for fraction in[.2,.1]:
   route=f'B_{system}_early{int(fraction*100)}';rows=[]
   for r in load_windows(system,fraction,include_shape=True):
    if system=='3E':
     q=next(q for q in old[route]if q['curve_id']==r['curve_id']);assert q['early_points']==r['early_points'] and q['point_indices']==r['point_indices']
     for k in SIX:assert q['features'][k]==r[k]
     assert q['static_features']==r['static_features'] and q['target']==r['target_retention_pct'];q=dict(q,shape_features=r['shape_features'])
    else:
     q=dict(row_id=r['endpoint_id']+'::early'+str(int(100*fraction)),endpoint_id=r['endpoint_id'],source_family=r['source_family'],curve_id=r['curve_id'],material_key=r['source_family']+'::'+r['sample_name'],sample_name=r['sample_name'],system=system,target=r['target_retention_pct'],features={k:r[k]for k in SIX},static_features=r['static_features'],last_early=r['last_early_retention_pct'],linear_forecast=r['last_early_retention_pct']+r['early_retention_slope_per_1000_cycles']*(r['target_cycle_count']-r['early_observed_cycle_count'])/1000,fraction=fraction,point_indices=r['point_indices'],early_points=r['early_points'],reading_bound_pp=r['maximum_reading_bound_pp'],shape_features=r['shape_features'])
    assert q['shape_features']==shape_summaries(q['early_points']);rows.append(q)
   data[route]=rows;sources=sorted({r['source_family']for r in rows});good=[r for r in rows if r['shape_features'][FIELDS[0]]is not None]
   counts[route]=dict(rows=len(rows),sources=len(sources),shape_computable_rows=len(good),shape_computable_sources=len({r['source_family']for r in good}));splits[route]=[]
   for outer in sources:
    rest=sorted([s for s in sources if s!=outer],key=lambda s:hashlib.sha256(s.encode('utf8')).hexdigest());folds=[rest[k::4]for k in range(4)];assert all(folds)
    splits[route].append(dict(outer_source=outer,inner_held_sources=folds))
   if system=='3E':assert splits[route]==oldsplit[route]
 cfg=read(OLD/'candidate_configurations.json');assert len(cfg)==16
 protected=read(OLD/'source_protection.json')
 for f in BASE.rglob('*'):
  if f.is_file():protected[f.relative_to(ROOT).as_posix()]=sha(f)
 for p in['data/retention_shape.py','data/retention_research.py','data/current_retention_research.json','data/current_training_latest.json','tools/retention_v3_optimizer.py','tools/run_small_sample_routes.py','tools/retention_stability_v4.py']:
  protected[p]=sha(ROOT/p)
 OUT.mkdir();write(OUT/'input_snapshot.json',data);write(OUT/'candidate_configurations.json',cfg);write(OUT/'source_protection.json',protected)
 plan=dict(frozen_at=now(),runner_sha256=sha(Path(__file__)),input_sha256=sha(OUT/'input_snapshot.json'),candidate_sha256=sha(OUT/'candidate_configurations.json'),source_protection_sha256=sha(OUT/'source_protection.json'),counts=counts,splits=splits,shape_authorization_sha256=sha(BASE/'第七轮_同窗口形状表达提案/authorization_20261030.json'),shape_fields=list(FIELDS),views=['six','shape'],candidate_configs_per_view=16,planned_new_fits=5360,planned_reused_control_fits=3440,planned_new_ensemble_weight_fits=0,primary='shape_oneSE_family_mean',paired_control='six_oneSE_family_mean',selection='Matched16 configurations in each view, identical outerLOSO/inner4 hashed source folds. Rank inner source-weightedMAE,RMSE,configID. Per-view oneSE family mean; winnerSE=sampleSD(per-source innerMAE)/sqrt(G). Joint32-view winner/oneSE recorded as secondary only. Never replace primary with highest outer score.',criteria=read(BASE/'research_goal.json')['criteria'],generalization=read(BASE/'research_goal.json')['generalization'],baselines=['training_mean','early_persistence','early_linear'],input_scope='Same10%/20%,minimum3 actual early points. Four approved shape fields only if>=3 actual points in each temporal half. No interpolation, no deleting missing-shape rows. Train-only Encoder drops unsupported fields or imputes median with missing indicators.',cohort_design='3E unchanged exact30/24 and20/19; reuse3440 archived six-control fit predictions. New2E localRPPAC expands7/7 and5/5, requiring both views to fit on the same expanded2E data. Data expansion is not attributed to shape features.',new_fit_breakdown={'3E_shape':3440,'2E20_six_plus_shape':1120,'2E10_six_plus_shape':800},no_failure_dropping='All failures and warnings retained. Any incomplete coverage fails acceptance.',output='specifiedN_capacitance_retention_pct',unchanged_labels=True,untouched_external_sources=0,secondary='Per-family/view results,near4 equal,and joint view selection. Paired-source MAE difference bootstrap. P6 nonlinear/BP histories and A direct route preserved, not rerun for this feature-isolation comparison.',stop='Exactly5360 new estimator fits;3440 prior control fits reused,0 learned ensemble weights. No outcome-driven additions.',goal_status='active')
 assert sum(v['sources']*(1 if r.startswith('B_3E')else 2)*5*16 for r,v in counts.items())==5360
 write(OUT/'training_plan.json',plan);write(OUT/'progress.json',dict(status='frozen_ready',new_fits=0,planned_new_fits=5360,reused_control_fits=3440));print(json.dumps(counts,ensure_ascii=False));print('FROZEN5360 new fits +3440 reused controls')
class Experiment:
 def __init__(self,plan):
  self.plan=plan;self.n=0;self.reused=0;self.pred=[];self.selections=[];self.failed=[];self.start=time.monotonic();self.archive={}
  with gzip.open(OLD/'fit_predictions.jsonl.gz','rt',encoding='utf8')as f:
   for line in f:
    q=json.loads(line);key=(q['route'],q['outer_source'],q['config_id'],q['role'],q['inner_fold']);assert key not in self.archive;self.archive[key]=q
 def fit(self,route,c,view,train,test,outer,role,fold=None):
  key=(route,outer,c['id'],role,fold);reuse=route.startswith('B_3E')and view=='six';cid=view+'::'+c['id']
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
    elapsed=round(time.monotonic()-self.start,1);write(OUT/'progress.json',dict(status='running',new_fits=self.n,planned_new_fits=5360,reused_control_fits=self.reused,failures=len(self.failed),elapsed_seconds=elapsed,route=route,outer_source=outer));print(self.n,'/5360',route,elapsed,'s',flush=True)
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
 plan=read(OUT/'training_plan.json');assert not(OUT/'fit_events.jsonl').exists() and not(OUT/'fit_predictions.jsonl.gz').exists(),'Do not restart a started round'
 assert sha(Path(__file__))==plan['runner_sha256'] and sha(OUT/'input_snapshot.json')==plan['input_sha256'] and sha(OUT/'candidate_configurations.json')==plan['candidate_sha256']
 for p,h in read(OUT/'source_protection.json').items():assert sha(ROOT/p)==h,p
 data=read(OUT/'input_snapshot.json');cfg=read(OUT/'candidate_configurations.json');exp=Experiment(plan)
 for route,rows in data.items():exp.run_route(route,rows,cfg)
 assert exp.n==5360 and exp.reused==3440
 write(OUT/'heldout_predictions.json',exp.pred);write(OUT/'nested_selection.json',exp.selections);write(OUT/'fit_failures.json',exp.failed);grouped=collections.defaultdict(list)
 for p in exp.pred:grouped[(p['route'],p['model'])].append(p)
 result=[]
 for(route,method),a in sorted(grouped.items()):
  m=metrics(a,bootstrap=method in['shape_oneSE_family_mean','six_oneSE_family_mean']);m.update(route=route,model=method);m['checks']=dict(r2=m['r2']is not None and m['r2']>.95,mae=m['mae']<=2,rmse=m['rmse']<=3,mape=m['mape_pct']<=5,p90_ape=m['p90_ape_pct']<=10,p90_abs=m['p90_absolute_error']<=5,source_tail=m['source_p90_mae']<=5,coverage=len(a)==len(data[route]),positive=all(p['predicted']>0 for p in a))
  for base in plan['baselines']:
   z=1-m['mae']/metrics(grouped[(route,base)])['mae'];m['mae_reduction_vs_'+base]=z;m['checks']['beat_'+base]=z>=.2
  m['numeric_pass']=all(m['checks'].values());m['at_least10_sources']=m['sources']>=10;m['untouched_external_test']=False;m['reliable_model_accepted']=False;result.append(m)
 old={(m['route'],m['model']):m for m in read(BASE/'第四轮_选模稳定性复核/results.json')['metrics']}
 for m in result:
  if m['route'].startswith('B_3E')and m['model']=='six_oneSE_family_mean':
   for k in['r2','mae','rmse']:assert abs(m[k]-old[(m['route'],'oneSE_family_mean')][k])<1e-10
 paired=[]
 for route in data:
  a=metrics(grouped[(route,'shape_oneSE_family_mean')])['per_source'];b={s['source']:s['mae']for s in metrics(grouped[(route,'six_oneSE_family_mean')])['per_source']};diff=np.array([s['mae']-b[s['source']]for s in a]);rng=np.random.default_rng(20261030);means=np.array([rng.choice(diff,len(diff),replace=True).mean()for _ in range(5000)])
  paired.append(dict(route=route,shape_minus_six_MAE_pp=float(diff.mean()),source_bootstrap95=np.quantile(means,[.025,.975]).tolist(),sources=len(diff),interpretation='Negative favours shape; exploratory paired development-source estimate, not independent external confirmation.'))
 write(OUT/'paired_comparison.json',paired)
 for p,h in read(OUT/'source_protection.json').items():assert sha(ROOT/p)==h,p
 write(OUT/'results.json',dict(status='complete',new_estimator_fits=exp.n,reused_control_fits=exp.reused,ensemble_weight_fits=0,failed_estimator_fits=len(exp.failed),metrics=result,numeric_pass_count=sum(m['numeric_pass']for m in result),goal_achieved=False,new_external_sources=0,completed_at=now(),primary=plan['primary'],paired_comparison=paired))
 write(OUT/'progress.json',dict(status='complete',new_fits=exp.n,planned_new_fits=5360,reused_control_fits=exp.reused,elapsed_seconds=round(time.monotonic()-exp.start,1),goal_status='active'))
 for m in result:
  if m['model']in['shape_oneSE_family_mean','six_oneSE_family_mean','joint_oneSE_family_mean']:print(m['route'],m['model'],m['r2'],m['mae'],m['rmse'],'numericpass',m['numeric_pass'],flush=True)
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','run']);args=parser.parse_args();prepare()if args.action=='prepare'else run()
