"""Verify glossy marker geometry and forward SQLite increment without fitting."""
from pathlib import Path
import hashlib,json,math,sqlite3,sys
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
BASE=ROOT/'保持率达标研究_v3_主线与近优组合_20261030';OUT=BASE/'第十一轮_双电极原文曲线补充';OLD=BASE/'第八轮_原文补证与双电极曲线'
def read(p):return json.loads(Path(p).read_text('utf8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 checks=0
 def ck(x,message=''):
  nonlocal checks
  assert x,message;checks+=1
 def close(a,b):ck(math.isclose(a,b,rel_tol=1e-8,abs_tol=1e-8),(a,b))
 plan=read(OUT/'store_build_plan.json');ck(sha(OLD/'cycling_research_v3c.sqlite')==plan['old_store_sha256']);ck(sha(OLD/'curve_dataset_v3c.json')==plan['old_dataset_sha256']);ck(sha(OUT/'curve_dataset_v3d.json')==plan['new_input_sha256']);q=read(OUT/'hpcs_curve_reviewed.json');receipt=read(OUT/'HPCS_figure_receipt.json');ck(sha(Path(receipt['source_path']))==receipt['source_sha256']);ck(sha(ROOT/q['figure_path'])==q['figure_sha256']);im=Image.open(ROOT/receipt['output']).convert('RGB').crop(q['panel_provenance']['crop_rect']);img=Image.open(ROOT/q['figure_path']).convert('RGB');ck(np.array_equal(np.array(im),np.array(img)));a=np.array(img).astype(float);dark=(a.max(2)-a.min(2)<8)&(a.max(2)<100);cal=q['calibration'];ck(cal['pixel_bound']==3)
 for p in q['points']:
  arc=p['lower_contour_pixels'];gx,gy=round(p['highlight_locator']['x']),round(p['highlight_locator']['y']);ck(len(arc)>=12)
  for x,y in arc:
   ck(x<1887 and dark[y,x]);lower=np.where(dark[gy-5:gy+28,x])[0]+gy-5;ck(y==max(lower))
  x,y=np.array(arc,dtype=float).T;xx=x-gx;yy=y-gy;A=np.column_stack([2*xx,2*yy,np.ones(len(x))]);coef=np.linalg.pinv(A)@(xx*xx+yy*yy);cx,cy=coef[:2];radius=float(np.sqrt(coef[2]+cx*cx+cy*cy));res=float(max(abs(np.sqrt((xx-cx)**2+(yy-cy)**2)-radius)));close(p['x_px'],gx+cx);close(p['y_px'],gy+cy);close(p['glyph_radius_px'],radius);ck(10<=radius<=18 and res<=1.5)
  n=(p['x_px']-182)*5000/(1894-182);r=100*(572.5-p['y_px'])/(572.5-79.5);b=300/(572.5-79.5);close(p['cycle_coordinate'],n);close(p['cycle_upper'],n+3*5000/1712);close(p['retention_pct'],r);close(p['reading_bound_pp'],b)
 ck(q['points'][-1]['reading_interval_pp'][0]<=73<=q['points'][-1]['reading_interval_pp'][1]);ck(len(q['points'])==50);ck(q['author_retention_pct']==73);ck(q['conditions']['baseline_cycle']is None);old=read(OLD/'curve_dataset_v3c.json');new=read(OUT/'curve_dataset_v3d.json');ck(new[:-1]==old and new[-1]==q)
 db=sqlite3.connect((OUT/'cycling_research_v3d.sqlite').as_uri()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row;ck(db.execute('PRAGMA integrity_check').fetchone()[0]=='ok');ck(not db.execute('PRAGMA foreign_key_check').fetchall());counts={}
 for system in['2E','3E']:
  for fraction in[.1,.2]:
   view=f'training_B_{system}_early{int(fraction*100)}';counts[view]=list(db.execute(f'SELECT count(*),count(DISTINCT source_family) FROM {view}').fetchone())
 ck(counts=={'training_B_2E_early10':[5,5],'training_B_2E_early20':[8,8],'training_B_3E_early10':[20,19],'training_B_3E_early20':[30,24]})
 for fraction,n in[(.1,2),(.2,8)]:
  row=db.execute('SELECT * FROM early_windows WHERE curve_id=? AND fraction=?',(q['curve_id'],fraction)).fetchone();ck(row['point_count']==n);ps=[p for p in q['points']if p['cycle_upper']<=fraction*5000];x=np.array([p['cycle_coordinate']for p in ps]);y=np.array([p['retention_pct']for p in ps]);close(row['last_early_retention_pct'],y[-1]);close(row['early_mean_retention_pct'],y.mean());close(row['early_retention_range_pp'],np.ptp(y));slope=np.linalg.lstsq(np.column_stack([np.ones(len(x)),x-x.mean()]),y,rcond=None)[0][1]*1000;close(row['early_retention_slope_per_1000_cycles'],slope)
 for c in old:ck(json.loads(db.execute('SELECT raw_json FROM curves WHERE curve_id=?',(c['curve_id'],)).fetchone()[0])==c)
 db.close();v7=read(ROOT/'data/current_training_latest.json');ck(sha(ROOT/v7['directory']/v7['database_file'])==v7['sha256']=='dd933ec815668060a10a1a828e2dcf8460eb862b16f4f9807d47b10a3816a097')
 result=dict(status='passed',checks=checks,sqlite_sha256=sha(OUT/'cycling_research_v3d.sqlite'),views=counts,actual_new_curves=1,actual_resolved_markers=50,unresolved_glyphs=16,new_training_rows_2E20=1,new_training_rows_2E10=0,new_fits=0,formal_admissions=0,old_source_labels_changed=0,old_v3c_and_v7_preserved=True,limitation='Original author endpoint retained; glossy-marker geometric reading is approximate,fixed3px bound. Earlier occluded markers unresolved;10%two-point window remainsineligible. This is not a new untouched external source.',verifier_sha256=sha(Path(__file__)))
 (OUT/'independent_verification_v3d.json').write_bytes((json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode('utf8'));print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
