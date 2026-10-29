"""Pre-fit visual review and a forward-only callable curve store."""
from pathlib import Path
import collections,hashlib,json,sqlite3,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.build_retention_curve_store_v3 import main as build
import tools.build_retention_curve_store_v3 as store
P=ROOT/'保持率达标研究_v3_主线与近优组合_20261030/第二轮_证据与曲线扩充'
def read(p):return json.loads(Path(p).read_text('utf8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,x):Path(p).write_bytes((json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode('utf8'))
def main():
 assert not(P/'batch2_reviewed.json').exists(),'Review already frozen'
 curves=read(P/'batch2_digitization_review_v3/candidates.json');checks=0
 original=read(ROOT/'保持率双路线预研_v2_20261029/baseline_inputs.json')['3E'];byid={r['row_id']:r for r in original}
 notes={
 'CMC':'Printed96.7% excluded from ROI. Lower red curve is a dense experimental trace; retain sampled actual trace columns as approximate graph readings, not raw measurement count. Upper pale CE excluded.',
 'AUACW':'Green retention uses left axis; orange CE excluded. Final partly occluded marker has85 real green pixels in fixed ROI968,145,986,166, centroid970,158. Endpoint QC now supported by actual fragment. No early feature/author-label rescaling.',
 'NCHU20':'Upper orange/red trace follows the NCHU20 legend and91.08% text. NCHU0 dark lower trace and following CO2 adsorption experiment excluded; overlapped initial region not asserted as visible separate data.',
 'OPBNP':'Dense individual Fig6f selected. Sparse Fig6g same experiment not duplicated.',
 'ALPC-800':'Fig8c three-electrode two electrolytes10A/g/2000cycles, not ORR Fig7 or two-electrode Fig8f. Same DOI group for both.',
 'SS-300':'Green series on right Percent axis; pink series/left C not used.',
 'CCL-K2CO3-1-700':'True activation growth above100% preserved.',
 }
 for q in curves:
  assert q['author_retention_pct']==byid[q['endpoint_id']]['target'];assert q['features']==byid[q['endpoint_id']]['features'];checks+=2
  assert sha(ROOT/q['figure_path'])==q['figure_sha256'];checks+=1
  reason=[]
  if q['manual_hold']:reason.append(q['manual_hold'])
  if not q['endpoint_consistent_with_graph_bound']:reason.append('Author endpoint and graph reading differ beyond fixed reading bound; preserve both and freeze B input, not author target.')
  if not any(w['eligible_by_point_count']for w in q['window_availability']):reason.append('Fewer than3 visible actual markers within the approved early windows. No sparse connecting-line densification. Pending optional2-point contract discussion does not grant admission.')
  q['training_eligible_pending_visual_review']=not reason
  q['visual_review']={'status':'accepted_for_approved_windows'if not reason else'hold','notes':notes.get(q['sample_name'],'Visual original/panel/overlay review confirms plotted series, axis, actual markers/dense trace and endpoint reading.'),'hold_reasons':reason,'before_phase2_fits':True,'author_label_changed':False,'minimum_early_points':3,'independent_external_validation':False}
  for w in q['window_availability']:
   ps=[p for p in q['points']if p['cycle_upper']<=w['fraction']*q['target_cycle_count']];assert len(ps)==w['early_markers'];checks+=1
   assert all(p['retention_pct']>0 and p['cycle_coordinate']<=p['cycle_upper']for p in ps);checks+=1
 write(P/'batch2_reviewed.json',curves)
 old=read(P/'curve_dataset_v3_incremental.json');assert not{q['endpoint_id']for q in old}&{q['endpoint_id']for q in curves}
 combined=old+curves;write(P/'curve_dataset_v3b.json',combined)
 queue=read(P/'existing_pdf_queue.json');status=[]
 for item in queue['items']:
  matched=[q for q in combined if q['source_family']==item['identity']]
  assert matched,item['identity'];status.append(dict(source_family=item['identity'],review_status='all_target_curves_reviewed',curves=[dict(endpoint_id=q['endpoint_id'],approved=q['training_eligible_pending_visual_review'],windows=q['window_availability'],review=q.get('visual_review'))for q in matched]))
 assert len(status)==20
 write(P/'existing_pdf_queue_reviewed.json',dict(original_queue_sha256=sha(P/'existing_pdf_queue.json'),all20_sources_reviewed=True,phase2_fits_before_review=0,items=status))
 # Forward store builder is a separately saved version, never mutate/run original builder.
 src=(ROOT/'tools/build_retention_curve_store_v3.py').read_text('utf8')
 src=src.replace('cycling_research_v3.sqlite','cycling_research_v3b.sqlite').replace('curve_dataset_v3_incremental.json','curve_dataset_v3b.json').replace('training_windows.json','training_windows_v3b.json').replace('store_verification.json','store_verification_v3b.json').replace("assert counts['training_B_3E_early20']==(16,11)and counts['training_B_3E_early10']==(10,9)","assert counts['training_B_3E_early20']==(30,24)and counts['training_B_3E_early10']==(20,19)").replace('new_early_curves=3','new_early_curves=17')
 dest=ROOT/'tools/build_retention_curve_store_v3b.py';assert not dest.exists();dest.write_bytes(src.encode('utf8'))
 write(P/'batch2_review_verification.json',dict(status='reviewed_before_fits',checks=checks,curves_reviewed=len(curves),sources_reviewed=len({q['source_family']for q in curves}),accepted=sum(q['training_eligible_pending_visual_review']for q in curves),held=sum(not q['training_eligible_pending_visual_review']for q in curves),all_queue_sources_reviewed=20,author_labels_changed=0,new_external_sources=0,source_data_snapshot_sha256=sha(P/'curve_dataset_v3b.json'),raw_candidates_preserved=True,minimum3_unchanged=True,pending2point_contract_not_used=True))
 print(json.dumps(read(P/'batch2_review_verification.json'),ensure_ascii=False,indent=2))
if __name__=='__main__':main()
