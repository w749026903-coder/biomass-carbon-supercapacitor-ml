"""Independent memberships, arithmetic and hashes; never imports an estimator."""
from pathlib import Path
import collections,hashlib,json,math
import numpy as np
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'保持率双路线预研_v2_20261029'
def read(p):return json.loads(Path(p).read_text('utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,x):Path(p).write_bytes((json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode('utf8'))
def weights(a):
 units=collections.defaultdict(lambda:collections.Counter())
 for r in a:units[r['source_family']][r.get('curve_id')or r.get('material_key')or r['row_id']]+=1
 return np.array([1/len(units)/len(units[r['source_family']])/units[r['source_family']][r.get('curve_id')or r.get('material_key')or r['row_id']]for r in a])
def metrics(a):
 w=weights(a);y=np.array([p['observed']for p in a]);yp=np.array([p['predicted']for p in a]);e=abs(y-yp);v=np.average((y-np.average(y,weights=w))**2,weights=w);m=np.average(e**2,weights=w)
 def quantile(z):
  i=np.argsort(z);return float(z[i][min(len(i)-1,np.searchsorted(np.cumsum(w[i]),.9*w.sum()))])
 source=[np.average(e[[r['source_family']==g for r in a]],weights=w[[r['source_family']==g for r in a]])for g in sorted({r['source_family']for r in a})]
 return dict(mae=float(np.average(e,weights=w)),rmse=float(np.sqrt(m)),r2=float(1-m/v)if v else None,mape_pct=float(np.average(e/y*100,weights=w)),p90_ape_pct=quantile(e/y*100),p90_absolute_error=quantile(e),source_p90_mae=float(np.quantile(source,.9)))
def main():
 checks=[]
 def check(v,msg):
  assert v,msg;checks.append(msg)
 def close(x,y,msg):check(math.isclose(x,y,rel_tol=1e-9,abs_tol=1e-8),msg)
 baseline=read(OUT/'baseline_inputs.json');old={r['row_id']:r for a in baseline.values()for r in a};review=read(OUT/'reviewed_curve_data.json');lookup={r['endpoint_id']:r for r in review}
 receipt=read(OUT/'curve_review_receipt.json');check(sha(OUT/'curve_marker_candidates.json')==receipt['raw_sha256'],'raw review SHA');check(sha(OUT/'reviewed_curve_data.json')==receipt['reviewed_sha256'],'reviewed SHA');check(sha(ROOT/'tools/review_retention_route_B_v2.py')==receipt['review_program_sha256'],'review code SHA')
 for q in review:
  check(q['author_retention_pct']==old[q['endpoint_id']]['target'],'original author label:'+q['endpoint_id']);check(sha(ROOT/q['figure_path'])==q['figure_sha256'],'figure:'+q['endpoint_id'])
  if q['endpoint_id']in receipt['excluded_endpoint_ids']:check(not q['training_eligible_pending_visual_review'],'conflict frozen:'+q['endpoint_id'])
 for paper in read(OUT/'curve_resource_inventory.json')['papers']:
  for src in paper['sources']:
   if src['available']:check(sha(ROOT/src['path'])==src['sha256'],'inventory original:'+src['path'])
 summaries=[]
 for folder,tag,runner in [('A_材料工况直接预测','A','train_retention_route_A_v2.py'),('B_早期实测辅助预测','B','train_retention_route_B_v2.py')]:
  run=OUT/folder;plan=read(run/'training_plan.json');data=read(run/'input_snapshot.json');rows={r['row_id']:r for a in data.values()for r in a};result=read(run/'results.json');events=[json.loads(x)for x in(run/'fit_events.jsonl').read_text('utf8').splitlines()];preds=read(run/'heldout_predictions.json')
  check(sha(run/'input_snapshot.json')==plan['input_sha256'],tag+'input frozen');check(sha(ROOT/'tools'/runner)==(plan['runner_sha256']if tag=='A'else plan['protected_sha256']['tools/'+runner]),tag+'runner frozen')
  if tag=='A':
   for rel,key in [('保持率双路线预研_v2_20261029/baseline_inputs.json','baseline_source_sha256'),('保持率双路线预研_v2_20261029/contract.json','contract_sha256'),('tools/run_small_sample_routes.py','engine_sha256')]:check(sha(ROOT/rel)==plan[key],tag+'protected:'+rel)
   for system,a in data.items():
    for r in a:
     check(set(r['features'])==set(plan['inputs_by_system'][system]),'A input schema:'+r['row_id']);check(r['target']==old[r['row_id']]['target'],'A unchanged label:'+r['row_id'])
     for k,v in r['features'].items():check(v==old[r['row_id']]['features'][k],'A original feature:'+r['row_id']+':'+k)
  else:
   for p,h in plan['protected_sha256'].items():check(sha(ROOT/p)==h,'B protected:'+p)
   for route,a in data.items():
    for r in a:
     q=lookup[r['endpoint_id']];check(q['training_eligible_pending_visual_review'],'B approved:'+r['row_id']);check(q['system']==r['system'],'B electrode:'+r['row_id']);check(r['target']==q['author_retention_pct'],'B original label:'+r['row_id']);check(set(r['features'])==set(plan['input_fields']),'B feature whitelist:'+r['row_id'])
     early=[p for p in q['points']if p['cycle_upper']<=r['fraction']*q['target_cycle_count']];check(len(early)>=3,'B min early observations:'+r['row_id']);check(r['point_indices']==[p['marker_index']for p in early],'B only early markers:'+r['row_id']);check(r['early_points']==early,'B original early points:'+r['row_id'])
     x=np.array([p['cycle_coordinate']for p in early]);y=np.array([p['retention_pct']for p in early]);slope=float(np.polyfit(x,y,1)[0]);vals=dict(last_early_retention_pct=y[-1],early_mean_retention_pct=y.mean(),early_retention_slope_per_1000_cycles=slope*1000,early_retention_range_pp=np.ptp(y),early_observed_cycle_count=x[-1],target_cycle_count=q['target_cycle_count'])
     for k,v in vals.items():close(float(v),r['features'][k],'B independent early feature:'+r['row_id']+':'+k)
     close(r['linear_forecast'],float(y[-1]+slope*(q['target_cycle_count']-x[-1])),'B linear baseline:'+r['row_id'])
     for p in early:
      s=q['calibration'];expected=(p['x_px']-s['x0'])/(s['xend']-s['x0'])*q['target_cycle_count'];close(p['cycle_coordinate'],expected,'B x calibration:'+r['row_id'])
     if q['first_plotted_reference']:
      s=q['calibration'];check(s['reference_roi'][2]+s['pixel_bound']<=s['x0']+r['fraction']*(s['xend']-s['x0']),'B own reference is early:'+r['row_id'])
     check(r['endpoint_id']not in receipt['excluded_endpoint_ids'],'B no frozen curve:'+r['row_id'])
  check(len(events)==plan['planned_fits']==result['fits'],tag+'finite fit count');check(all(e['status']=='complete'for e in events)and not result['failures'],tag+'all fits complete')
  for e in events:
   train=[rows[i]for i in e['train_row_ids']];test=[rows[i]for i in e['test_row_ids']];check(not set(e['train_sources'])&set(e['test_sources']),tag+'source disjoint:'+str(e['fit_index']));check(not{r['row_id']for r in train}&{r['row_id']for r in test},tag+'row disjoint:'+str(e['fit_index']));check(not{r['material_key']for r in train}&{r['material_key']for r in test},tag+'material disjoint:'+str(e['fit_index']));check({r['source_family']for r in train}==set(e['train_sources'])and{r['source_family']for r in test}==set(e['test_sources']),tag+'actual source members:'+str(e['fit_index']))
   if tag=='B':
    route,name=e['route'].split('::');check(all(r['system']==test[0]['system']and r['fraction']==test[0]['fraction']for r in train+test),'B system/window isolation:'+str(e['fit_index']));check(not{r['curve_id']for r in train}&{r['curve_id']for r in test},'B curve disjoint:'+str(e['fit_index']));allowed=set(plan['input_fields'])|(set(plan['optional_static_by_system'][test[0]['system']])if'static'in name else set())
    t=np.array([(r['target']-r['last_early'])/10 for r in train]);w=weights(train);mu=np.average(t,weights=w);sd=float(np.sqrt(np.average((t-mu)**2,weights=w)))or 1.;close(float(mu),e['target_center'],'B train-only target centre:'+str(e['fit_index']));close(sd,e['target_scale'],'B train-only target scale:'+str(e['fit_index']))
   else:allowed=set(plan['inputs_by_system'][e['route'][2:]])
   for field in e['encoder']:
    check(field['field']in allowed,tag+'encoder whitelist:'+str(e['fit_index']))
    values=[r['features'].get(field['field'],r.get('static_features',{}).get(field['field']))for r in train];values=[v for v in values if v is not None]
    if field['kind']=='categorical':check(field['vocab']==sorted(set(values)),tag+'train-only vocabulary:'+str(e['fit_index']))
    else:close(field['median'],float(np.median(values)),tag+'train-only median:'+str(e['fit_index']))
  groups=collections.defaultdict(list)
  for p in preds:
   r=rows[p['row_id']];check(p['observed']==r['target']and p['source_family']==r['source_family'],tag+'prediction label/source');check(math.isfinite(p['predicted']),tag+'finite prediction');groups[(p['route'],p['model'])].append(p)
   if p['model']=='early_persistence':close(p['predicted'],r['last_early'],'persistence original early value')
   if p['model']=='early_linear_extrapolation':close(p['predicted'],r['linear_forecast'],'linear baseline value')
  for s in result['metrics']:
   a=groups[(s['route'],s['model'])];m=metrics(a)
   for k,v in m.items():close(v,s[k],tag+'independent metric:'+s['route']+':'+s['model']+':'+k)
   route_rows=data[s['route']]if tag=='B'else data[s['route'][2:]];check(len(a)==len(route_rows),tag+'complete coverage:'+s['route']+':'+s['model']);check(len({p['row_id']for p in a})==len(a),tag+'no duplicate predictions')
   check(not s['numeric_pass']and not s['final_reliable'],tag+'no false success')
   if tag=='B':
    for name in plan['baselines']:
     base=groups[(s['route'],name)];bm=metrics(base);close(s['mae_reduction_vs_baselines'][name],1-m['mae']/bm['mae'],'B baseline reduction')
    ids={p['endpoint_id']for p in a};check(not ids&set(receipt['excluded_endpoint_ids']),'B conflicts stay excluded')
   if s['model']=='training_mean':
    for p in a:
     train=[r for r in route_rows if r['source_family']!=p['source_family']];close(p['predicted'],float(np.average([r['target']for r in train],weights=weights(train))),tag+'source-held training mean')
  summaries.append(dict(route=tag,fit_attempts=len(events),prediction_records=len(preds),numeric_pass_count=sum(s['numeric_pass']for s in result['metrics']),failed_fits=len(result['failures'])))
 # Preserve the existing science and all older model artefacts.
 protected=read(ROOT/'小样本方向预研_20261029/source_protection.json')
 for p,h in protected.items():check(sha(ROOT/p)==h,'original protected:'+p)
 old_manifest=read(ROOT/'模型v1.3_新数据与辅助学习_20261029/merge_manifest.json')
 for item in old_manifest['outputs']:check(sha(ROOT/item['path'])==item['sha256'],'old v1.3 output:'+item['path'])
 out=dict(status='passed',checks=len(checks),estimator_fits_in_verification=0,routes=summaries,old_protected_hashes=len(protected),old_v13_output_hashes=len(old_manifest['outputs']),original_labels_changed=0,original_databases_changed=0,source_and_material_and_curve_isolation_verified=True,early_cutoff_and_train_only_preprocessing_verified=True,high_accuracy_retention_goal_achieved=False,untouched_external_generalization_confirmed=False,check_names=checks)
 write(OUT/'independent_verification.json',out);print(json.dumps({k:v for k,v in out.items()if k!='check_names'},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
