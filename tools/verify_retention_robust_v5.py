"""Source/encoder/selection audit plus closed-form GP/Ridge reproduction; no fits."""
from pathlib import Path
import collections,gzip,hashlib,json,math,sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import tools.verify_retention_v3b as a
from tools.verify_retention_shape_v4 import rawfeatures,mae
BASE=ROOT/'保持率达标研究_v3_主线与近优组合_20261030';P9=BASE/'第九轮_同窗口形状对照';OUT=BASE/'第十轮_稳健表达与来源权重'
FIELDS=['first_half_slope_pp','last_half_slope_pp','quadratic_curvature_pp','peak_relative_time_fraction'];STATIC={'reported_current_A_g','electrolyte','concentration_mol_L','cycle_voltage_lower_V','cycle_voltage_upper_V','BET_m2_g','reference_electrode'}
SIMPLE=['Ridge_early','RF_early','ExtraTrees_early','GPR_early','XGB_early','RF_static','GPR_static','XGB_static','RidgeGP_residual'];NEAR=['RF_early','GPR_early','XGB_early','RF_static']
def read(p):return json.loads(Path(p).read_text('utf8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def protected_ok(p,h):
 if sha(ROOT/p)==h:return True
 # The pipeline reads the immutable P9 input_reference, never this rolling API
 # pointer. A later, independently verified forward-store route is archived
 # with exact before/after hashes; all actual scientific inputs stay protected.
 if p!='data/current_retention_research.json':return False
 receipt=OUT/'post_fit_pointer_change.json'
 if not receipt.exists():return False
 r=read(receipt);return r['old_sha256']==h and sha(ROOT/r['old_snapshot_path'])==h and sha(ROOT/p)==r['new_sha256'] and sha(ROOT/r['new_database_path'])==r['new_database_sha256']
def archive(folder,prefix=''):
 out={}
 with gzip.open(folder/'fit_predictions.jsonl.gz','rt',encoding='utf8')as f:
  for line in f:
   q=json.loads(line);k=(q['route'],q['outer_source'],prefix+q['config_id'],q['role'],q['inner_fold']);a.check(k not in out);out[k]=q
 return out
def transform(rows,schema,c):
 output=[]
 for r in rows:
  fields=rawfeatures(r,c,c['view']);v=[]
  for s in schema:
   x=fields.get(s['field']);mult=s['multiplier']
   if s['kind']=='categorical':v.extend([mult*float(x==k)for k in s['vocab']]+[mult*float(x not in s['vocab'])])
   else:
    missing=x is None;x=s['median']if missing else x;x=math.log1p(x)if s['log']else x;v.extend([mult*math.asinh((x-s['center'])/s['scale']),mult*float(missing)])
  output.append(v)
 return np.array(output)
def ridge(x,y,w,alpha):
 weighted=w*len(w);xm=np.average(x,axis=0,weights=weighted);ym=float(np.average(y,weights=weighted));xc=x-xm;coef=np.linalg.solve((xc.T*weighted)@xc+alpha*np.eye(x.shape[1]),(xc.T*weighted)@(y-ym));intercept=ym-xm@coef;return coef,intercept
def gp(x,xt,y,alpha,ell):
 def kernel(a,b):
  distance=np.sqrt(np.maximum(0,((a[:,None,:]-b[None,:,:])**2).sum(axis=2)))/ell;z=math.sqrt(3)*distance;return(1+z)*np.exp(-z)
 K=kernel(x,x)+np.diag(alpha);dual=np.linalg.solve(K,y);return kernel(xt,x)@dual
def main():
 plan=read(OUT/'training_plan.json');a.check(plan['runner_sha256']==sha(ROOT/'tools/retention_robust_v5.py'));a.check(plan['input_reference']['sha256']==sha(ROOT/plan['input_reference']['path']));a.check(plan['candidate_sha256']==sha(OUT/'candidate_configurations.json'));a.check(plan['method_review_sha256']==sha(OUT/'方法依据与适用边界.md'));protected=read(OUT/'source_protection.json')
 for p,h in protected.items():a.check(protected_ok(p,h),p)
 data=read(ROOT/plan['input_reference']['path']);a.check(data==read(P9/'input_snapshot.json'));cfg={c['id']:c for c in read(OUT/'candidate_configurations.json')};priorbase=read(P9/'candidate_configurations.json');prior={f'prior::{view}::{c["id"]}':dict(c,view=view)for view in['six','shape']for c in priorbase};combinedcfg={**prior,**cfg};newarc=archive(OUT);oldarc=archive(P9,'prior::');arc={**oldarc,**newarc};a.check(len(oldarc)==len(newarc)==8800);a.check(len(arc)==17600)
 events=[json.loads(line)for line in(OUT/'fit_events.jsonl').read_text('utf8').splitlines()];a.check(len(events)==8800);a.check([e['pipeline_fit_index']for e in events]==list(range(1,8801)));a.check(sum(len(e['estimator_stages'])for e in events)==9350);starts=1;reproduced=collections.Counter();warning=collections.Counter();split={(route,s['outer_source']):s for route,ss in plan['splits'].items()for s in ss};inner={};outer={}
 for e in events:
  route=e['route'];outer_source=e['outer_source'];c=cfg[e['config_id']];key=(route,outer_source,e['config_id'],e['role'],e['inner_fold']);q=newarc[key];a.check(q['pipeline_fit_index']==e['pipeline_fit_index']);a.check(e['estimator_fit_index_start']==starts);starts+=len(e['estimator_stages']);a.check(e['status']=='complete');warning.update(e['warnings']);expected_stages=['Ridge_mean','GPR_residual']if c['kind']=='RidgeGP'else[c['kind']];a.check(e['estimator_stages']==expected_stages)
  held={outer_source}if e['role']=='outer'else set(split[(route,outer_source)]['inner_held_sources'][e['inner_fold']]);excluded=held|{outer_source};train=[r for r in data[route]if r['source_family']not in excluded];test=[r for r in data[route]if r['source_family']in held];a.check(e['train_row_ids']==[r['row_id']for r in train]);a.check(e['test_row_ids']==[r['row_id']for r in test]);a.check(e['train_sources']==sorted({r['source_family']for r in train}));a.check(e['test_sources']==sorted({r['source_family']for r in test}));a.check(not set(e['train_sources'])&set(e['test_sources']));a.check(not{r['curve_id']for r in train}&{r['curve_id']for r in test});a.check([p['row_id']for p in q['predictions']]==e['test_row_ids']);a.check(all(p['observed']==r['target']and math.isfinite(p['predicted'])for p,r in zip(q['predictions'],test)))
  w=a.wts(train);y=np.array([r['target']-r['last_early']for r in train]);mu=float(sum(w*y));sd=float(np.sqrt(sum(w*(y-mu)**2)))or 1.;a.close(e['target_center'],mu);a.close(e['target_scale'],sd);y=(y-mu)/sd;ff=[rawfeatures(r,c,c['view'])for r in train];eligible=[]
  for k in sorted(set().union(*(v.keys()for v in ff))):
   ids=[i for i,v in enumerate(ff)if v.get(k)is not None]
   if len(ids)<max(2,int(.15*len(train)))or len({train[i]['source_family']for i in ids})<3:continue
   eligible.append(k);s=next(v for v in e['encoder']if v['field']==k);vals=[ff[i][k]for i in ids];mult=.25 if k in FIELDS else .5 if k in STATIC else 1.;a.close(s['multiplier'],mult)
   if all(isinstance(v,str)for v in vals):a.check(s['kind']=='categorical');a.check(s['vocab']==sorted(set(vals)));continue
   median=float(np.median(vals));log=all(v>=0 for v in vals)and any(v in k.lower()for v in['bet','volume','current','ratio','cycle_count']);z=np.array([f.get(k)if f.get(k)is not None else median for f in ff]);z=np.log1p(z)if log else z;center=float(np.median(z));iqr=float(np.quantile(z,.75)-np.quantile(z,.25));scale=iqr if iqr>1e-9 else(float(np.std(z))or 1.);a.check(s['kind']=='numeric');a.check(s['log']==log);a.close(s['median'],median);a.close(s['center'],center);a.close(s['iqr'],iqr);a.close(s['scale'],scale);a.check(s['compression']=='asinh')
  a.check([v['field']for v in e['encoder']]==eligible)
  # Independent matrix equations reproduce analytic model predictions without
  # calling any estimator's fit or using held labels in the reconstruction.
  if c['kind']in['Ridge','GPR','RidgeGP']:
   x=transform(train,e['encoder'],c);xt=transform(test,e['encoder'],c)
   if c['kind']=='Ridge':coef,intercept=ridge(x,y,w,c['parameters']['alpha']);z=xt@coef+intercept
   else:
    diagonal=c['alpha']/(w*len(train));a.check(np.allclose(e['diagonal_regularization'],diagonal,rtol=0,atol=1e-12))
    if c['kind']=='RidgeGP':
     coef,intercept=ridge(x,y,w,c['mean_ridge_alpha']);a.close(float(intercept),e['ridge_intercept']);a.check(np.allclose(coef,e['ridge_coefficients'],rtol=1e-8,atol=1e-8));residual=y-x@coef-intercept;a.check(np.allclose(residual,e['train_residuals'],rtol=1e-8,atol=1e-8));z=xt@coef+intercept+gp(x,xt,residual,diagonal,c['length_scale'])
    else:z=gp(x,xt,y,diagonal,c['length_scale'])
   for pred,r,v in zip(q['predictions'],test,z):a.close(pred['predicted'],r['last_early']+float(v)*sd+mu)
   reproduced[c['kind']]+=1
 a.check(starts==9351)
 for key,q in arc.items():
  route,outer_source,cid,role,fold=key
  if role=='inner':inner.setdefault((route,outer_source,cid),[]).extend(q['predictions'])
  else:outer[(route,outer_source,cid)]={r['row_id']:r['predicted']for r in q['predictions']}
 pp=read(OUT/'heldout_predictions.json');index={(p['route'],p['model'],p['row_id']):p for p in pp};a.check(len(index)==len(pp));group=collections.defaultdict(list)
 for p in pp:group[(p['route'],p['model'])].append(p)
 for sel in read(OUT/'nested_selection.json'):
  route=sel['route'];outer_source=sel['outer_source'];stats=[]
  for cid,c in combinedcfg.items():
   rows=inner[(route,outer_source,cid)];a.check(len(rows)==len({p['row_id']for p in rows}));a.check({p['row_id']for p in rows}=={r['row_id']for r in data[route]if r['source_family']!=outer_source});m=a.score(rows);stats.append(dict(config_id=cid,family=c['family'],mae=m['mae'],rmse=m['rmse'],new=cid in cfg));saved=next(s for s in sel['inner_scores']if s['config_id']==cid);a.close(saved['mae'],m['mae']);a.close(saved['rmse'],m['rmse'])
  rank=lambda v:(v['mae'],v['rmse'],v['config_id']);win=min(stats,key=rank);families={f:min([s for s in stats if s['family']==f],key=rank)for f in SIMPLE};rows=inner[(route,outer_source,win['config_id'])];sources=sorted({p['source_family']for p in rows});se=float(np.std([mae([p for p in rows if p['source_family']==s])for s in sources],ddof=1)/math.sqrt(len(sources)));eligible=[f for f in SIMPLE if families[f]['mae']<=win['mae']+se+1e-12];a.check(sel['winner']==win['config_id']);a.close(sel['oneSE'],se);a.check(sel['eligible_families']==eligible)
  for f,v in families.items():a.check(sel['family_selected'][f]['config_id']==v['config_id'])
  methods=dict(oneSE_family_mean=[families[f]['config_id']for f in eligible],nested_selected=[win['config_id']],near4_equal=[families[f]['config_id']for f in NEAR],all9_family_equal=[families[f]['config_id']for f in SIMPLE]);methods.update({'nested_family::'+f:[v['config_id']]for f,v in families.items()})
  for label,ss in [('new_only',[s for s in stats if s['new']]),('old_only',[s for s in stats if not s['new']])]:
   winner=min(ss,key=rank);rows=inner[(route,outer_source,winner['config_id'])];sources=sorted({p['source_family']for p in rows});se=float(np.std([mae([p for p in rows if p['source_family']==s])for s in sources],ddof=1)/math.sqrt(len(sources)));fams={f:min([s for s in ss if s['family']==f],key=rank)for f in{v['family']for v in ss}};methods[label+'_oneSE_family_mean']=[v['config_id']for f,v in sorted(fams.items())if v['mae']<=winner['mae']+se+1e-12]
  a.check(sel['methods']==methods)
  train=[r for r in data[route]if r['source_family']!=outer_source];mean=float(sum(a.wts(train)*np.array([r['target']for r in train])))
  for r in data[route]:
   if r['source_family']!=outer_source:continue
   rid=r['row_id']
   for method,cids in methods.items():a.close(index[(route,method,rid)]['predicted'],float(np.mean([outer[(route,outer_source,c)][rid]for c in cids])))
   for cid in combinedcfg:a.close(index[(route,'fixed::'+cid,rid)]['predicted'],outer[(route,outer_source,cid)][rid])
   for b,v in dict(training_mean=mean,early_persistence=r['last_early'],early_linear=r['linear_forecast']).items():a.close(index[(route,b,rid)]['predicted'],v)
 for prior in read(P9/'heldout_predictions.json'):
  if prior['model']in['six_oneSE_family_mean','shape_oneSE_family_mean']:a.close(index[(prior['route'],'P9_'+prior['model'],prior['row_id'])]['predicted'],prior['predicted'])
 result=read(OUT/'results.json')
 for m in result['metrics']:
  rows=group[(m['route'],m['model'])];s=a.score(rows);a.check(len(rows)==len(data[m['route']]));a.check(len(rows)==len({p['row_id']for p in rows}))
  for k,v in s.items():a.close(m[k],v)
  checks=dict(r2=s['r2']>.95,mae=s['mae']<=2,rmse=s['rmse']<=3,mape=s['mape_pct']<=5,p90_ape=s['p90_ape_pct']<=10,p90_abs=s['p90_absolute_error']<=5,source_tail=s['source_p90_mae']<=5,coverage=True,positive=all(p['predicted']>0 for p in rows))
  for b in plan['baselines']:
   diff=1-s['mae']/a.score(group[(m['route'],b)])['mae'];a.close(m['mae_reduction_vs_'+b],diff);checks['beat_'+b]=diff>=.2
  a.check(m['checks']==checks);a.check(m['numeric_pass']==all(checks.values()));a.check(not m['reliable_model_accepted']and not m['untouched_external_test'])
 for p,h in protected.items():a.check(protected_ok(p,h),p)
 audit=dict(status='passed',checks=a.CHECKS,new_pipeline_fits=8800,new_estimator_fits=9350,reused_control_pipeline_fits=8800,protected_sha256_files=len(protected),closed_form_reproduced_pipeline_fits=dict(reproduced),fit_warnings=dict(warning),old_labels_changed=0,all_rows_preserved=True,inner_scores_selection_encoders_recomputed=True,goal_status='active',limits='No model fit during audit. All GP/Ridge/hybrid predictions reconstructed by independent matrix equations; tree estimator weights not archived/rebuilt, but splits/encoders/finite outputs/code SHA/selection/gates audited. Exposed development sources do not establish external generalization.',verifier_sha256=sha(Path(__file__)))
 (OUT/'independent_verification.json').write_bytes((json.dumps(audit,ensure_ascii=False,indent=2)+'\n').encode('utf8'));print(json.dumps(audit,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
