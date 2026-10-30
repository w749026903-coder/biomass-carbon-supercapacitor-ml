"""No-refit independent checks of actual windows, encoders, selection and all gates."""
from pathlib import Path
import collections,gzip,hashlib,json,math,sqlite3,sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import tools.verify_retention_v3b as a
BASE=ROOT/'保持率达标研究_v3_主线与近优组合_20261030';OUT=BASE/'第十二轮_扩充双电极来源验证';OLD=BASE/'第三轮_扩充来源验证';P8=BASE/'第十一轮_双电极原文曲线补充/batch4_20261031'
FIELDS=['first_half_slope_pp','last_half_slope_pp','quadratic_curvature_pp','peak_relative_time_fraction']
SIMPLE=['Ridge_early','RF_early','ExtraTrees_early','GPR_early','XGB_early','RF_static','GPR_static','XGB_static'];NEAR=['RF_early','GPR_early','XGB_early','RF_static']
def read(p):return json.loads(Path(p).read_text('utf8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def mae(rows):return float(sum(a.wts(rows)*np.array([abs(r['observed']-r['predicted'])for r in rows])))
def protected_ok(p,h):
 current=sha(ROOT/p)
 if current==h:return True
 # Only rolling presentation/checkpoint files may change after the fit/audit.
 # Their exact before/after hashes must be declared; scientific inputs never qualify.
 allowed={BASE.name+'/'+name for name in['README.md','research_progress.json','研究进度.html','研究进度预览.png','版式核验.json']}
 receipt=OUT/'post_fit_publication_receipt.json'
 if p not in allowed or not receipt.exists():return False
 q=read(receipt).get('rolling_files',{}).get(p)
 return q is not None and q['frozen_at_fit_sha256']==h and q['published_sha256']==current
def arc(folder):
 out={}
 with gzip.open(folder/'fit_predictions.jsonl.gz','rt',encoding='utf8')as f:
  for line in f:
   q=json.loads(line);k=(q['route'],q['outer_source'],q['config_id'],q['role'],q['inner_fold']);a.check(k not in out,'duplicate fit key');out[k]=q
 return out
def rawfeatures(r,c,view):
 f=r['features']
 if c['feature_view']=='raw':v=dict(f)
 else:
  N=f['target_cycle_count'];obs=f['early_observed_cycle_count'];last=f['last_early_retention_pct'];v=dict(last_early_retention_pct=last,early_mean_minus_last_pp=f['early_mean_retention_pct']-last,early_range_pp=f['early_retention_range_pp'],early_linear_remaining_change_pp=f['early_retention_slope_per_1000_cycles']*(N-obs)/1000,observed_fraction=obs/N,target_cycle_count=N)
 if c['static']:v.update(r['static_features'])
 if view=='shape':v.update(r['shape_features'])
 return v
def main():
 plan=read(OUT/'training_plan.json');a.check(sha(ROOT/'tools/retention_expanded2e_v6.py')==plan['runner_sha256']);a.check(sha(OUT/'input_snapshot.json')==plan['input_sha256']);a.check(sha(OUT/'candidate_configurations.json')==plan['candidate_sha256'])
 protected=read(OUT/'source_protection.json')
 for p,h in protected.items():a.check(protected_ok(p,h),p)
 data=read(OUT/'input_snapshot.json');cfg={c['id']:c for c in read(OUT/'candidate_configurations.json')};olddata={};curves={r['curve_id']:r for r in read(P8/'curve_dataset_v3g.json')}
 for route,rows in data.items():
  a.check(len(rows)==plan['counts'][route]['rows']);a.check(len({r['source_family']for r in rows})==plan['counts'][route]['sources'])
  if route.startswith('B_3E'):a.check([{k:v for k,v in r.items()if k!='shape_features'}for r in rows]==olddata[route],'exact old3E inputs')
  for r in rows:
   q=curves[r['curve_id']];ps=[p for p in q['points']if p['cycle_upper']<=r['fraction']*q['target_cycle_count']];a.check(ps==r['early_points']);a.check(r['target']==q['author_retention_pct']);a.check(r['system']==q['system']);a.check(q['training_eligible_pending_visual_review']);a.check(len(ps)>=3)
   x=np.array([p['cycle_coordinate']for p in ps]);y=np.array([p['retention_pct']for p in ps]);z=(x-min(x))/(max(x)-min(x));l=z<=.5;h=z>.5
   if l.sum()<3 or h.sum()<3:a.check(all(v is None for v in r['shape_features'].values()))
   else:
    def slope(mask):return float(np.linalg.lstsq(np.column_stack([np.ones(mask.sum()),z[mask]-z[mask].mean()]),y[mask],rcond=None)[0][1])
    b=np.linalg.lstsq(np.column_stack([np.ones(len(z)),z,z*z]),y,rcond=None)[0];expected=dict(zip(FIELDS,[slope(l),slope(h),float(2*b[2]),float(z[np.flatnonzero(y==max(y))[0]])]))
    for k,v in expected.items():a.close(r['shape_features'][k],v)
 db=sqlite3.connect((P8/'cycling_research_v3g.sqlite').as_uri()+'?mode=ro',uri=True);a.check(db.execute('PRAGMA integrity_check').fetchone()[0]=='ok');a.check(not db.execute('PRAGMA foreign_key_check').fetchall());db.close()
 archive=arc(OUT);oldarc={};events=[json.loads(line)for line in(OUT/'fit_events.jsonl').read_text('utf8').splitlines()];a.check(len(archive)==6400);a.check(len(events)==6400);a.check([e['fit_index']for e in events]==list(range(1,6401)));a.check(sum(q['reused']for q in archive.values())==0)
 split={(r,s['outer_source']):s for r,ss in plan['splits'].items()for s in ss};byid={r:{q['row_id']:q for q in rows}for r,rows in data.items()};shapeuse=collections.Counter();warn=collections.Counter();newindex={e['fit_index']:e for e in events};inner={};outer={}
 for key,q in archive.items():
  route,held,cid,role,fold=key;view,baseid=cid.split('::',1);c=cfg[baseid];exclude={held};heldinner=set(split[(route,held)]['inner_held_sources'][fold])if role=='inner'else{held}
  if role=='inner':exclude|=heldinner
  train=[r for r in data[route]if r['source_family']not in exclude];test=[r for r in data[route]if r['source_family']in heldinner];pp=q['predictions'];a.check([p['row_id']for p in pp]==[r['row_id']for r in test]);a.check(not{r['source_family']for r in train}&{r['source_family']for r in test});a.check(not{r['curve_id']for r in train}&{r['curve_id']for r in test});a.check(all(p['observed']==byid[route][p['row_id']]['target']and math.isfinite(p['predicted'])for p in pp))
  if q['reused']:
   a.check(view=='six'and route.startswith('B_3E'));prior=oldarc[(route,held,baseid,role,fold)];a.check(pp==prior['predictions']);a.check(q['source_fit_index']==prior['fit_index'])
  else:
   e=newindex[q['fit_index']];a.check((e['route'],e['outer_source'],e['config_id'],e['role'],e['inner_fold'])==key);a.check(e['status']=='complete');a.check(e['train_row_ids']==[r['row_id']for r in train]);a.check(e['test_row_ids']==[r['row_id']for r in test]);a.check(e['train_sources']==sorted({r['source_family']for r in train}));a.check(e['test_sources']==sorted({r['source_family']for r in test}));warn.update(e['warnings'])
   w=a.wts(train);yy=np.array([r['target']-r['last_early']if c['target']=='delta'else math.log(r['target']/r['last_early'])for r in train]);mu=float(sum(w*yy));sd=float(np.sqrt(sum(w*(yy-mu)**2)))or 1.;a.close(mu,e['target_center']);a.close(sd,e['target_scale'])
   fs=[rawfeatures(r,c,view)for r in train];expected=[]
   for k in sorted(set().union(*(v.keys()for v in fs))):
    ids=[i for i,v in enumerate(fs)if v.get(k)is not None]
    if len(ids)<max(2,int(.15*len(train)))or len({train[i]['source_family']for i in ids})<3:continue
    vals=[fs[i][k]for i in ids];schema=next(s for s in e['encoder']if s['field']==k);expected.append(k)
    if all(isinstance(v,str)for v in vals):a.check(schema['kind']=='categorical');a.check(schema['vocab']==sorted(set(vals)))
    else:
     med=float(np.median(vals));log=all(v>=0 for v in vals)and any(s in k.lower()for s in['bet','volume','current','ratio','cycle_count']);z=np.array([v.get(k)if v.get(k)is not None else med for v in fs]);z=np.log1p(z)if log else z;center=float(sum(w*z));scale=float(np.sqrt(sum(w*(z-center)**2)))or 1.;a.check(schema['kind']=='numeric');a.check(schema['log']==log);a.close(schema['median'],med);a.close(schema['center'],center);a.close(schema['scale'],scale)
   a.check([s['field']for s in e['encoder']]==expected);a.check(e['shape_fields_retained']==[k for k in expected if k in FIELDS]);shapeuse[(route,view,role,'retained'if e['shape_fields_retained']else'none')]+=1
  if role=='inner':inner.setdefault((route,held,cid),[]).extend(pp)
  else:outer[(route,held,cid)]={r['row_id']:r['predicted']for r in pp}
 pred=read(OUT/'heldout_predictions.json');predindex={(r['route'],r['model'],r['row_id']):r for r in pred};a.check(len(predindex)==len(pred));group=collections.defaultdict(list)
 for p in pred:group[(p['route'],p['model'])].append(p)
 for sel in read(OUT/'nested_selection.json'):
  route=sel['route'];held=sel['outer_source'];ss=[];stats={}
  for cid in[view+'::'+c for view in['six','shape']for c in cfg]:
   pp=inner[(route,held,cid)];a.check(len(pp)==len({r['row_id']for r in pp}));a.check({r['row_id']for r in pp}=={r['row_id']for r in data[route]if r['source_family']!=held});m=a.score(pp);v,bid=cid.split('::',1);stats[cid]=m;ss.append(dict(config_id=cid,family=cfg[bid]['family'],view=v,mae=m['mae'],rmse=m['rmse']))
   reported=next(v for v in sel['scores']if v['config_id']==cid);a.close(reported['mae'],m['mae']);a.close(reported['rmse'],m['rmse'])
  rank=lambda x:(x['mae'],x['rmse'],x['config_id']);expectedmethods={}
  for view in['six','shape','joint']:
   eligible_scores=[s for s in ss if view=='joint'or s['view']==view];win=min(eligible_scores,key=rank);fams={f:min([s for s in eligible_scores if s['family']==f],key=rank)for f in SIMPLE};pp=inner[(route,held,win['config_id'])];sources=sorted({p['source_family']for p in pp});sm=[mae([p for p in pp if p['source_family']==source])for source in sources];se=float(np.std(sm,ddof=1)/math.sqrt(len(sm)));near=[f for f in SIMPLE if fams[f]['mae']<=win['mae']+se+1e-12];s=sel['views'][view];a.check(s['winner']==win['config_id']);a.close(s['inner_source_mae_standard_error'],se);a.check(s['eligible_oneSE_families']==near)
   expectedmethods[view+'_nested_selected']=[win['config_id']];expectedmethods[view+'_oneSE_family_mean']=[fams[f]['config_id']for f in near];expectedmethods[view+'_near4_equal']=[fams[f]['config_id']for f in NEAR]
   for f,c in fams.items():a.check(s['family_selected'][f]['config_id']==c['config_id']);expectedmethods[view+'_family::'+f]=[c['config_id']]
  a.check(sel['methods']==expectedmethods)
  tr=[r for r in data[route]if r['source_family']!=held];mu=float(sum(a.wts(tr)*np.array([r['target']for r in tr])))
  for r in data[route]:
   if r['source_family']!=held:continue
   rid=r['row_id']
   for method,cids in expectedmethods.items():a.close(predindex[(route,method,rid)]['predicted'],float(np.mean([outer[(route,held,c)][rid]for c in cids])))
   for cid in[view+'::'+c for view in['six','shape']for c in cfg]:a.close(predindex[(route,'fixed::'+cid,rid)]['predicted'],outer[(route,held,cid)][rid])
   for b,v in dict(training_mean=mu,early_persistence=r['last_early'],early_linear=r['linear_forecast']).items():a.close(predindex[(route,b,rid)]['predicted'],v)
 result=read(OUT/'results.json')
 for m in result['metrics']:
  pp=group[(m['route'],m['model'])];s=a.score(pp);a.check(len(pp)==len(data[m['route']]));a.check(len(pp)==len({p['row_id']for p in pp}))
  for k,v in s.items():a.close(m[k],v)
  checks=dict(r2=s['r2']>.95,mae=s['mae']<=2,rmse=s['rmse']<=3,mape=s['mape_pct']<=5,p90_ape=s['p90_ape_pct']<=10,p90_abs=s['p90_absolute_error']<=5,source_tail=s['source_p90_mae']<=5,coverage=True,positive=all(p['predicted']>0 for p in pp))
  for b in plan['baselines']:
   z=1-s['mae']/a.score(group[(m['route'],b)])['mae'];a.close(m['mae_reduction_vs_'+b],z);checks['beat_'+b]=z>=.2
  a.check(m['checks']==checks);a.check(m['numeric_pass']==all(checks.values()));a.check(m['at_least10_sources']==(len({p['source_family']for p in pp})>=10));a.check(not m['reliable_model_accepted']and not m['untouched_external_test'])
 for pair in read(OUT/'paired_comparison.json'):
  route=pair['route'];p=group[(route,'shape_oneSE_family_mean')];b=group[(route,'six_oneSE_family_mean')];sources=sorted({q['source_family']for q in p});diff=np.array([mae([q for q in p if q['source_family']==s])-mae([q for q in b if q['source_family']==s])for s in sources]);a.close(pair['shape_minus_six_MAE_pp'],float(diff.mean()));rng=np.random.default_rng(20261030);ci=np.quantile([rng.choice(diff,len(diff),replace=True).mean()for _ in range(5000)],[.025,.975]);a.check(np.allclose(ci,pair['source_bootstrap95'],rtol=0,atol=1e-10))
 for p,h in protected.items():a.check(protected_ok(p,h),p)
 audit=dict(status='passed',checks=a.CHECKS,protected_sha256_files=len(protected),new_fits=6400,reused_control_fits=0,fit_warnings=dict(warn),shape_schema_usage=[dict(route=k[0],view=k[1],role=k[2],shape_fields=k[3],fits=v)for k,v in sorted(shapeuse.items())],all_rows_preserved=True,author_labels_changed=0,all_inner_predictions_and_selection_recomputed=True,train_only_encoders_independently_recomputed=True,new_untouched_external_sources=0,goal_status='active',limits='No estimator refitting in audit. These are already exposed development sources. No numeric result alone satisfies independent generalization.',verifier_sha256=sha(Path(__file__)))
 (OUT/'independent_verification.json').write_bytes((json.dumps(audit,ensure_ascii=False,indent=2)+'\n').encode('utf8'));print(json.dumps({k:v for k,v in audit.items()if k!='shape_schema_usage'},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
