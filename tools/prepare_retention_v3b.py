"""Freeze expanded data and candidate shortlist using only historical inner scores."""
from pathlib import Path
import collections,hashlib,json,sqlite3,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.run_retention_v3b import BASE,RUN,read,write,sha,now
P=BASE/'第二轮_证据与曲线扩充'
def main():
 assert not RUN.exists(),'Never overwrite a research phase';RUN.mkdir()
 db=sqlite3.connect((P/'cycling_research_v3b.sqlite').as_uri()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
 curves={q['curve_id']:q for q in read(P/'curve_dataset_v3b.json')};data={}
 for route in['B_3E_early20','B_3E_early10']:
  data[route]=[]
  for rr in db.execute('SELECT * FROM training_'+route+' ORDER BY source_family,curve_id'):
   r=dict(rr);q=curves[r['curve_id']];ps=[p for p in q['points']if p['marker_index']in json.loads(r['point_indices_json'])];N=r['target_cycle_count'];obs=r['early_observed_cycle_count'];last=r['last_early_retention_pct'];slope=r['early_retention_slope_per_1000_cycles']
   data[route].append(dict(row_id=r['endpoint_id']+'::early'+str(int(100*r['fraction'])),endpoint_id=r['endpoint_id'],source_family=r['source_family'],curve_id=r['curve_id'],material_key=r['source_family']+'::'+r['sample_name'],sample_name=r['sample_name'],system='3E',target=r['target_retention_pct'],features={k:r[k]for k in['last_early_retention_pct','early_mean_retention_pct','early_retention_slope_per_1000_cycles','early_retention_range_pp','early_observed_cycle_count','target_cycle_count']},static_features=json.loads(r['static_features_json']),last_early=last,linear_forecast=last+slope*(N-obs)/1000,fraction=r['fraction'],point_indices=json.loads(r['point_indices_json']),early_points=ps,reading_bound_pp=r['maximum_reading_bound_pp']))
 db.close();write(RUN/'input_snapshot.json',data)
 prior=read(BASE/'第一轮_参数与表达/nested_selection.json');candidate=read(BASE/'第一轮_参数与表达/candidate_configurations.json')['B'];scores=collections.defaultdict(list)
 for s in prior:
  if s['cohort']=='B_3E_early20':
   for v in s['inner_scores']:scores[v['config_id']].append(v['mae'])
 selected=[];ranks={}
 for family in sorted({c['family']for c in candidate}):
  rank=sorted([c for c in candidate if c['family']==family],key=lambda c:(sum(scores[c['id']])/len(scores[c['id']]),c['id']));selected+=rank[:2];ranks[family]=[dict(id=c['id'],historical_mean_inner_mae=sum(scores[c['id']])/len(scores[c['id']]))for c in rank]
 assert len(selected)==16;write(RUN/'candidate_configurations.json',selected);write(RUN/'candidate_shortlist_basis.json',dict(method='Best2 per each of8 families ranked only by phase1 inner-MAE aggregate. New expanded cohort outer results not seen. This still reuses development sources, not external validation.',phase1_selection_sha256=sha(BASE/'第一轮_参数与表达/nested_selection.json'),ranking=ranks))
 splits={};counts={}
 for route,rows in data.items():
  sources=sorted({r['source_family']for r in rows});counts[route]=dict(rows=len(rows),sources=len(sources));splits[route]=[]
  for outer in sources:
   others=sorted([s for s in sources if s!=outer],key=lambda s:hashlib.sha256(s.encode('utf8')).hexdigest());folds=[others[i::4]for i in range(4)];assert all(folds);splits[route].append(dict(outer_source=outer,inner_held_sources=folds))
 protected=read(BASE/'第一轮_参数与表达/source_protection.json')
 for folder in[BASE/'第一轮_参数与表达',P]:
  for f in folder.rglob('*'):
   if f.is_file():protected[f.relative_to(ROOT).as_posix()]=sha(f)
 for p in['tools/retention_v3_optimizer.py','tools/run_small_sample_routes.py','tools/prepare_small_sample_routes.py']:
  assert sha(ROOT/p)==protected[p]
 write(RUN/'source_protection.json',protected)
 plan=dict(frozen_at=now(),runner_sha256=sha(ROOT/'tools/run_retention_v3b.py'),preparer_sha256=sha(Path(__file__)),input_sha256=sha(RUN/'input_snapshot.json'),candidate_sha256=sha(RUN/'candidate_configurations.json'),source_protection_sha256=sha(RUN/'source_protection.json'),sqlite_sha256=sha(P/'cycling_research_v3b.sqlite'),counts=counts,splits=splits,planned_estimator_fits=sum(v['sources']for v in counts.values())*5*16,planned_ensemble_fits=sum(v['sources']for v in counts.values()),primary='nested_selected',selection='Outer leave-one-whole-source-out; inside each training set4 whole-source folds hashed by source identity, no label-based assignment. Rank by source-weighted inner MAE then RMSE and candidateID. Every inner and outer fit prediction saved. Family winners and equal/inner convex RF/GPR/XGB/RF-static mixture reported alongside primary.',baseline=['training_mean','early_persistence','early_linear'],criteria=read(BASE/'research_goal.json')['criteria'],protected_output='specifiedN capacitance retention',minimum_early_points=3,shortlist_candidates=16,phase1_reused_development_sources=True,untouched_external_sources=0,A_and_2E='Retain complete previous results unchanged; no new eligible2E curves orA labels in this batch. No false new benchmark.',target_transformation='Frozen delta/log ratios from historical shortlist; never change true author labels; no upper100% clipping.',stop='Exactly3440 estimator fits and43 inner ensemble-weight fits; no added candidates after outer scores.',methods='Same verified installed estimators as frozen phase1; GPR fit lacks sample-weight argument; target scaling/selection/evaluation use source weights. Train-only preprocessing.',high_accuracy_goal_status='active')
 assert plan['planned_estimator_fits']==3440 and plan['planned_ensemble_fits']==43
 write(RUN/'training_plan.json',plan);write(RUN/'progress.json',dict(status='frozen_ready',fits=0,planned_fits=3440));print(json.dumps(dict(counts=counts,candidates=16,fits=3440,ensemble_fits=43,protected_files=len(protected)),ensure_ascii=False,indent=2))
if __name__=='__main__':main()
