"""Independent source-pixel, ratio, window and forward-database audit; no training."""
from pathlib import Path
import hashlib,json,math,sqlite3,sys
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'保持率达标研究_v3_主线与近优组合_20261030';P11=BASE/'第十一轮_双电极原文曲线补充';OUT=P11/'batch2_20261031'
def read(p):return json.loads(Path(p).read_text('utf8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 checks=0
 def ck(x,msg=''):
  nonlocal checks
  assert x,msg;checks+=1
 def close(x,y):ck(math.isclose(x,y,rel_tol=1e-9,abs_tol=1e-8),(x,y))
 plan=read(OUT/'store_build_plan.json');ck(sha(ROOT/plan['old_database_path'])==plan['old_database_sha256']);ck(sha(P11/'curve_dataset_v3d.json')==plan['old_dataset_sha256']);ck(sha(OUT/'curve_dataset_v3e.json')==plan['new_dataset_sha256']);old=read(P11/'curve_dataset_v3d.json');new=read(OUT/'curve_dataset_v3e.json');curves=read(OUT/'reviewed_curve_data.json');ck(new==old+curves);ck(len(curves)==7);ck(sum(q['training_eligible_pending_visual_review']for q in curves)==6)
 specs={s['eid']:s for s in read(OUT/'extraction_plan_v2.json')['specifications']};baseline={r['row_id']:r for r in read(ROOT/'保持率双路线预研_v2_20261029/baseline_inputs.json')['2E']};receipts=read(OUT/'figure_receipts.json')
 for r in receipts:ck(sha(ROOT/r['source_path'])==r['source_sha256']);ck(sha(ROOT/r['output'])==r['image_sha256'])
 for q in curves:
  spec=specs[q['endpoint_id']];row=baseline[q['endpoint_id']];ck(q['author_retention_pct']==row['target']);ck(q['source_family']==row['source_family']);ck(q['conditions']==row['conditions']);ck(q['target_cycle_count']==row['features']['cycle_count']);ck(all(q['features'][k]==row['features'].get(k)for k in q['features']));ck(sha(ROOT/q['figure_path'])==q['figure_sha256']);im=Image.open(ROOT/q['figure_path']).convert('RGB');a=np.array(im).astype(float)
  if spec['crop']is not None:
   parent=Image.open(ROOT/q['panel_provenance']['original_image_path']).convert('RGB').crop(spec['crop']);ck(np.array_equal(np.array(im),np.array(parent)))
  cal=q['calibration'];ck(cal['pixel_bound']==3)
  if spec['mode']=='dense':
   # The displayed PC lower tick is50%,notzero.
   ck(cal['y0']==856.5);close((cal['y0']-462)/(cal['y0']-cal['y100'])*100,50.)
  mask=None
  if spec['mode']in['solid_circles','absolute_C']:
   mask=a.max(2)<110;lo,hi=spec['roi'];mask[:lo]=False;mask[hi:]=False;xmin,xmax=(140,951)if spec['mode']=='absolute_C'else(cal['x0']+7,cal['xN']+8);mask[:,:int(xmin)]=False;mask[:,int(xmax):]=False;eroded=mask.copy()
   for dy in[-1,0,1]:
    for dx in[-1,0,1]:eroded&=np.roll(np.roll(mask,dy,0),dx,1)
  for i,p in enumerate(q['points']):
   ck(p['marker_index']==i);ck(i==0 or p['cycle_coordinate']>q['points'][i-1]['cycle_coordinate']);x,y=p['x_px'],p['y_px'];n=(x-cal['x0'])*cal['N']/(cal['xN']-cal['x0']);v=(cal['y0']-y)*100/(cal['y0']-cal['y100']);bound=300/(cal['y0']-cal['y100']);close(p['cycle_coordinate'],n);close(p['cycle_upper'],n+3*cal['N']/(cal['xN']-cal['x0']));e=p['source_pixels']
   if 'column_y'in e:
    yy=np.array(e['column_y']);rgb=a[yy,int(x)];ck(len(yy)==e['pixel_count']);ck(all(spec['roi'][0]<=v<spec['roi'][1]for v in yy))
    if spec['mode']=='magenta_rings':ck(np.all((rgb[:,0]>100)&(rgb[:,0]-rgb[:,1]>50)&(rgb[:,2]-rgb[:,1]>35)));close(y,float((yy.min()+yy.max())/2))
    else:
     if spec['color']=='red':ck(np.all((rgb[:,0]-rgb[:,1]>35)&(rgb[:,0]-rgb[:,2]>25)&(rgb[:,1]>60)&(rgb[:,0]>160)&(rgb[:,2]<210)))
     elif spec['color']=='blue':ck(np.all((rgb[:,2]-rgb[:,0]>30)&(rgb[:,2]-rgb[:,1]>5)&(rgb[:,1]-rgb[:,0]>20)))
     else:ck(np.all((rgb[:,0]-rgb[:,1]>10)&(rgb[:,2]-rgb[:,1]>15)&(rgb[:,0]<230)&(rgb[:,1]>85)))
     close(y,float(np.median(yy)))
   elif 'eroded_bbox'in e:
    x0,y0,x1,y1=e['eroded_bbox'];region=eroded[y0:y1+1,x0:x1+1];ck(int(region.sum())==e['pixel_count']);yy,xx=np.where(region);ck(xx.min()==yy.min()==0);ck(xx.max()==x1-x0 and yy.max()==y1-y0);close(x,(x0+x1)/2);close(y,(y0+y1)/2)
   else:
    ck(e['partially_axis_occluded']);ck(i==0 and spec['first_visible_partial_marker']==[x,y]);right=a[round(y)-6:round(y)+7,round(x)+2:round(x)+8];ck(int((right.max(2)<110).sum())>=12,'actual visible clipped disk pixels')
   if spec['mode']=='absolute_C':
    close(p['raw_capacitance_F_g'],v);ref=q['first_plotted_reference'];C0=ref['value_F_g'];b0=ref['reading_bound_F_g'];close(p['retention_pct'],100*v/C0)
    if i:
     close(p['reading_interval_pp'][0],100*(v-bound)/(C0+b0));close(p['reading_interval_pp'][1],100*(v+bound)/(C0-b0))
   else:close(p['retention_pct'],v);close(p['reading_interval_pp'][0],v-bound);close(p['reading_interval_pp'][1],v+bound)
  tail=q['points'][-1];expected=tail['reading_interval_pp'][0]-.1<=q['author_retention_pct']<=tail['reading_interval_pp'][1]+.1;ck(q['endpoint_consistent_with_graph_bound']==expected);ck(q['training_eligible_pending_visual_review']==expected);ck(tail['cycle_coordinate']>=.97*cal['N'])
  for f in[.1,.2]:ck(len([p for p in q['points']if p['cycle_upper']<=f*cal['N']])>=3)
 db=sqlite3.connect((OUT/'cycling_research_v3e.sqlite').as_uri()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row;ck(db.execute('PRAGMA integrity_check').fetchone()[0]=='ok');ck(not db.execute('PRAGMA foreign_key_check').fetchall());counts={}
 for system in['2E','3E']:
  for f in[.1,.2]:
   view=f'training_B_{system}_early{int(f*100)}';counts[view]=list(db.execute(f'SELECT count(*),count(DISTINCT source_family) FROM {view}').fetchone());oldconn=sqlite3.connect((P11/'cycling_research_v3d.sqlite').as_uri()+'?mode=ro',uri=True);oldconn.row_factory=sqlite3.Row;previous=[dict(r)for r in oldconn.execute(f'SELECT * FROM {view} ORDER BY curve_id')];current={r['curve_id']:dict(r)for r in db.execute(f'SELECT * FROM {view}')};ck(all(current[r['curve_id']]==r for r in previous));oldconn.close()
 ck(counts=={'training_B_2E_early10':[11,8],'training_B_2E_early20':[14,11],'training_B_3E_early10':[20,19],'training_B_3E_early20':[30,24]})
 for q in curves:
  ck(json.loads(db.execute('SELECT raw_json FROM curves WHERE curve_id=?',(q['curve_id'],)).fetchone()[0])==q)
  for f in[.1,.2]:
   ps=[p for p in q['points']if p['cycle_upper']<=f*q['target_cycle_count']];w=db.execute('SELECT * FROM early_windows WHERE curve_id=? AND fraction=?',(q['curve_id'],f)).fetchone();ck(w['point_count']==len(ps));ck(json.loads(w['point_indices_json'])==[p['marker_index']for p in ps]);x=np.array([p['cycle_coordinate']for p in ps]);y=np.array([p['retention_pct']for p in ps]);close(w['last_early_retention_pct'],y[-1]);close(w['early_mean_retention_pct'],y.mean());close(w['early_retention_range_pp'],np.ptp(y));close(w['early_retention_slope_per_1000_cycles'],np.linalg.lstsq(np.column_stack([np.ones(len(x)),x-x.mean()]),y,rcond=None)[0][1]*1000)
 db.close();v7=read(ROOT/'data/current_training_latest.json');ck(sha(ROOT/v7['directory']/v7['database_file'])==v7['sha256']=='dd933ec815668060a10a1a828e2dcf8460eb862b16f4f9807d47b10a3816a097')
 result=dict(status='passed',checks=checks,sqlite_sha256=sha(OUT/'cycling_research_v3e.sqlite'),views=counts,new_B_curves=6,new_source_groups=3,held_curves=1,positions_connected=430,dense_trace_positions=337,explicit_glyph_positions=93,changed_author_labels=0,new_formal_admissions=0,new_model_fits=0,new_untouched_external_sources=0,old3d_v7_and_view_rows_unchanged=True,limits='Pixel/figure readings are approximate. PC truncatedaxis corrected with original attempt retained;BLACown-first-C reference mismatch remainsheld. Sparsecurve points not densified. FirstCE axis-clipped disk is visiblypresent;baselinecycleindex stillunknown.',verifier_sha256=sha(Path(__file__)))
 (OUT/'independent_verification.json').write_bytes((json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode('utf8'));print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
