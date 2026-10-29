"""Independent arithmetic, memberships and protected-file verification; no estimators."""
from pathlib import Path
import collections, hashlib, json, math
import numpy as np
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'小样本方向预研_20261029';RUN=BASE/'保持率固定输入输出'
def read(p):return json.loads(Path(p).read_text('utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 count=0
 def check(v,msg):
  nonlocal count
  count+=1
  if not v:raise AssertionError(msg)
 p=read(RUN/'training_plan.json');r=read(RUN/'results.json');input=read(RUN/'input_snapshot.json');rows={x['row_id']:x for x in input['rows']};original={x['row_id']:x for x in read(BASE/'input_snapshot.json')['retention']}
 check(sha(BASE/'input_snapshot.json')==p['source_snapshot_sha256'],'input SHA')
 check(sha(ROOT/'tools/run_fixed_io_retention_routes.py')==p['runner_sha256'],'runner frozen')
 check(sha(ROOT/'tools/run_small_sample_routes.py')==p['engine_sha256'],'engine frozen')
 check(sha(ROOT/'docs/RETENTION_DIRECTION_GOAL.json')==p['goal_sha256'],'goal contract frozen')
 for path,h in read(BASE/'source_protection.json').items():check(sha(ROOT/path)==h,'source '+path)
 for rid,x in rows.items():
  check(set(x['features'])==set(p['fixed_inputs']),'exact8 '+rid)
  check(x['target']==original[rid]['target'],'unchanged retention '+rid)
  for k,v in x['features'].items():check(v==original[rid]['features'][k],'original input '+rid+k)
 events=[json.loads(x)for x in(RUN/'fit_events.jsonl').read_text('utf8').splitlines()]
 check(len(events)==p['planned_fits']==r['actual_fits'],'fit count')
 for e in events:
  train=set(e['train_row_ids']);test=set(e['test_row_ids']);check(not train&test,'row exclusion')
  if e['route']=='R5_known_family':
   check(not{rows[x]['material_key']for x in train}&{rows[x]['material_key']for x in test},'material exclusion')
  else:check(not set(e['train_sources'])&set(e['test_sources']),'source exclusion')
  check(set(e['test_sources'])=={rows[x]['source_family']for x in test},'actual test sources')
  for s in e.get('encoder',[]):check(s['field']in p['fixed_inputs'],'encoder whitelist')
 preds=read(RUN/'heldout_predictions.json');groups=collections.defaultdict(list)
 for a in preds:
  check(a['observed']==rows[a['row_id']]['target'],'original target in predictions')
  check(a['source_family']==rows[a['row_id']]['source_family'],'prediction source')
  check(not a['calibration_row_ids'],'no measured test retention input')
  groups[(a['route'],a['model'])].append(a)
 for s in r['metrics']:
  a=groups[(s['route'],s['model'])];units=collections.defaultdict(lambda:collections.Counter())
  for x in a:units[x['source_family']][x['material_key']]+=1
  w=np.array([1/len(units)/len(units[x['source_family']])/units[x['source_family']][x['material_key']]for x in a]);y=np.array([x['observed']for x in a]);yh=np.array([x['predicted']for x in a]);err=yh-y
  mse=np.sum(w*err**2)/sum(w);variance=np.sum(w*(y-np.average(y,weights=w))**2)/sum(w)
  computed=dict(mae=float(np.sum(w*abs(err))/sum(w)),rmse=float(math.sqrt(mse)),r2=float(1-mse/variance))
  for k,v in computed.items():check(math.isclose(v,s[k],rel_tol=1e-10,abs_tol=1e-9),'independent '+k)
  check(s['rmse']+1e-9>=s['mae'],'RMSE>=MAE')
  check(not s['final_acceptance'],'no prospective assertion')
  if s['numerical_pass']:check(s['r2']>.95 and s['mae']<=2 and s['rmse']<=3,'all gates')
  if s['rows']!=len(groups[(s['route'],'training_mean')]):check(not s['numerical_pass'],'failure coverage cannot pass')
 initial=read(BASE/'results.json');initial_plan=read(BASE/'training_plan.json')
 check(sha(BASE/'input_snapshot.json')==initial_plan['input_sha256'],'initial plan unchanged')
 check(initial['actual_fits']==initial['planned_fits']==986,'initial pass count preserved')
 receipt=dict(status='passed',checks=count,estimator_fits_during_verification=0,retention_fit_attempts=len(events),retention_fit_failures=len(r['failures']),off_target_previous_attempts=986,all_numeric_pass_count=sum(x['numerical_pass']for x in r['metrics']),fixed_inputs=p['fixed_inputs'],fixed_output=p['fixed_output'],prospective_generalization_confirmed=False,source_protected_files=63)
 (RUN/'independent_verification.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n','utf8');print(json.dumps(receipt,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
