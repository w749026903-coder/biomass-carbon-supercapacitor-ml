"""Independent split/selection/metric audit of the completed finite phase."""
from pathlib import Path
import collections,hashlib,itertools,json,math
import numpy as np
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'保持率达标研究_v3_主线与近优组合_20261030';RUN=OUT/'第一轮_参数与表达'
def read(p):return json.loads(Path(p).read_text('utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def weights(a):
 u=collections.defaultdict(lambda:collections.Counter())
 for r in a:u[r['source_family']][r.get('curve_id')or r['material_key']]+=1
 return np.array([1/len(u)/len(u[r['source_family']])/u[r['source_family']][r.get('curve_id')or r['material_key']]for r in a])
def values(a):
 w=weights(a);y=np.array([r['observed']for r in a]);p=np.array([r['predicted']for r in a]);e=abs(y-p);mse=np.average(e**2,weights=w);var=np.average((y-np.average(y,weights=w))**2,weights=w)
 return dict(mae=float(np.average(e,weights=w)),rmse=float(np.sqrt(mse)),r2=float(1-mse/var),mape_pct=float(np.average(e/y*100,weights=w)))
def main():
 checks=0
 def check(v,message):
  nonlocal checks
  checks+=1;assert v,message
 def close(a,b,msg):check(math.isclose(a,b,rel_tol=1e-9,abs_tol=1e-8),msg)
 plan=read(RUN/'training_plan.json');data=read(RUN/'input_snapshot.json');config=read(RUN/'candidate_configurations.json');results=read(RUN/'results.json');configs={c['id']:c for a in config.values()for c in a};rows={c:{r['row_id']:r for r in a}for c,a in data.items()}
 for p,h in read(RUN/'source_protection.json').items():check(sha(ROOT/p)==h,'protected '+p)
 for p,key in[(RUN/'input_snapshot.json','input_sha256'),(RUN/'candidate_configurations.json','candidate_sha256'),(RUN/'source_protection.json','source_protection_sha256'),(ROOT/'tools/retention_v3_optimizer.py','runner_sha256')]:check(sha(p)==plan[key],'frozen '+key)
 check(not results['failed_estimator_fits'],'all estimator fits returned finite predictions');events=[json.loads(s)for s in(RUN/'fit_events.jsonl').read_text('utf8').splitlines()];check(len(events)==results['estimator_fits']==plan['planned_estimator_fits']==6324,'finite fits6324')
 keys=set()
 for e in events:
  cohort=e['cohort'];c=configs[e['config_id']];lookup=rows[cohort];train=[lookup[i]for i in e['train_row_ids']];test=[lookup[i]for i in e['test_row_ids']];key=(cohort,e['config_id'],tuple(e['held_sources']));check(key not in keys,'no repeated job');keys.add(key)
  check(not{r['source_family']for r in train}&set(e['held_sources']),'source excluded');check({r['source_family']for r in test}==set(e['held_sources']),'held source actual members');check(not set(e['train_row_ids'])&set(e['test_row_ids']),'row exclusion');check(not{r['material_key']for r in train}&{r['material_key']for r in test},'material exclusion');check(len(train)+len(test)==len(lookup),'every cohort row assigned')
  target=c['target'];y=np.array([r['target']if target=='absolute'else math.log(r['target'])if target=='log_absolute'else r['target']-r['last_early']if target=='delta'else math.log(r['target']/r['last_early'])for r in train]);w=weights(train);center=float(np.average(y,weights=w));scale=float(np.sqrt(np.average((y-center)**2,weights=w)))or 1.;close(center,e['target_center'],'train-only target centre');close(scale,e['target_scale'],'train-only target scale')
 for cohort,a in data.items():
  gs=sorted({r['source_family']for r in a});cs=config['B']if cohort in plan['B_cohorts']else config['A'];splits=list(itertools.combinations(gs,2))+[(s,)for s in gs]if cohort in plan['B_cohorts']else[(s,)for s in gs]
  for c in cs:
   for held in splits:check((cohort,c['id'],tuple(held))in keys,'complete planned job grid')
 selection=read(RUN/'nested_selection.json');check(len(selection)==plan['planned_ensemble_weight_fits']==20,'outer selections20')
 for sel in selection:
  lookup=rows[sel['cohort']];outer=sel['outer_source'];check(all(lookup[i]['source_family']!=outer for i in sel['inner_validation_row_ids']),'no outer labels in selection rows');check(set(sel['excluded_outer_rows'])=={r['row_id']for r in lookup.values()if r['source_family']==outer},'all outer rows excluded')
  rank=lambda s:(s['mae'],s['rmse'],s['config_id']);check(sel['overall_selected']==min(sel['inner_scores'],key=rank),'primary chooses inner score only')
  for fam,s in sel['family_selected'].items():check(s==min([z for z in sel['inner_scores']if z['family']==fam],key=rank),'family inner selection')
  en=sel['ensemble'];check(set(en['uses_only_inner_validation_row_ids'])==set(sel['inner_validation_row_ids']),'combination uses inner cohort');check(abs(sum(en['weights'])-1)<1e-6 and min(en['weights'])>=-1e-8,'convex weights');check(en['status']=='complete','weight optimizer success')
 pred=read(RUN/'heldout_predictions.json');group=collections.defaultdict(list);selmap={(s['cohort'],s['outer_source']):s for s in selection}
 for p in pred:
  r=rows[p['route']][p['row_id']];check(p['observed']==r['target']and p['source_family']==r['source_family'],'original labels and source');check(math.isfinite(p['predicted']),'finite prediction');group[(p['route'],p['model'])].append(p)
  if p['model']=='nested_selected':check(p['selected_config']==selmap[(p['route'],p['source_family'])]['overall_selected']['config_id'],'outer prediction uses inner chosen config')
  if p['model'].startswith('nested_family::'):check(p['selected_config']==selmap[(p['route'],p['source_family'])]['family_selected'][p['model'].split('::')[1]]['config_id'],'family prediction chosen config')
 for s in results['metrics']:
  a=group[(s['route'],s['model'])];m=values(a)
  for k,v in m.items():close(v,s[k],'independent metric '+k)
  check(len(a)==len(rows[s['route']]),'complete prediction coverage');check(len({r['row_id']for r in a})==len(a),'one prediction per endpoint/method');check(not s['reliable_model_accepted']and not s['untouched_external_test'],'no false independent claim')
  if s['numeric_pass']:check(s['r2']>.95 and s['mae']<=2 and s['rmse']<=3 and all(s['checks'].values()),'every numerical gate')
 check(not results['goal_achieved']and not results['new_external_sources'],'goal remains unmet');check(not any(s['numeric_pass']for s in results['metrics']),'zero numeric pass accurately recorded')
 limitation='Pair-exclusion individual predictions were not persisted by this frozen runner. Inner ranking is checked against stored inner score tables and exclusion membership/code; individual inner MAE arithmetic is not independently rederived. Outer metrics are independently recomputed. Future phases should persist inner predictions.'
 receipt=dict(status='passed_with_documented_audit_limit',checks=checks,estimator_fits_during_verification=0,base_estimator_fits=6324,combination_weight_fits=20,protected_hashes=len(read(RUN/'source_protection.json')),all_outer_metrics_recomputed=True,known_source_and_material_exclusion_verified=True,inner_ranking_and_exclusion_membership_verified=True,individual_inner_arithmetic_recomputed=False,audit_limit=limitation,numeric_pass_count=0,high_accuracy_goal_achieved=False,research_goal_status='active')
 (RUN/'independent_verification.json').write_bytes((json.dumps(receipt,ensure_ascii=False,indent=2)+'\n').encode('utf8'));print(json.dumps(receipt,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
