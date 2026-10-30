"""Independent local-figure/store/API checks; never train or rewrite old stores."""
from pathlib import Path
import hashlib,json,math,sqlite3,sys
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
BASE=ROOT/'保持率达标研究_v3_主线与近优组合_20261030';OUT=BASE/'第八轮_原文补证与双电极曲线';OLD=BASE/'第二轮_证据与曲线扩充'
def read(p):return json.loads(Path(p).read_text('utf8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,x):Path(p).write_bytes((json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode('utf8'))
def main():
 checks=0
 def check(ok,msg):
  nonlocal checks
  assert ok,msg;checks+=1
 def close(a,b,msg):check(math.isclose(a,b,rel_tol=1e-9,abs_tol=1e-8),msg)
 check(sha(OLD/'cycling_research_v3b.sqlite')=='3f79549f536831107d93bd0e0b1d6413d651f0c9d2f93e8790df8ee08db36f9e','old3b')
 q=read(OUT/'rppac_curve_reviewed.json');check(sha(ROOT/q['original_pdf_path'])==q['original_pdf_sha256'],'PDF unchanged');check(sha(ROOT/q['figure_path'])==q['figure_sha256'],'panel unchanged')
 receipt=read(OUT/'figure_receipt.json');original=Image.open(ROOT/receipt['output']).convert('RGB');panel=original.crop(q['panel_provenance']['crop_rect']);check(np.array_equal(np.asarray(panel),np.asarray(Image.open(ROOT/q['figure_path']).convert('RGB'))),'exact crop')
 a=np.asarray(panel);cal=q['calibration'];blue=(a[:,:,2].astype(float)>110)&(a[:,:,2]>1.5*a[:,:,0].astype(float))&(a[:,:,2]>1.2*a[:,:,1].astype(float))
 pts=q['points'];check(len(pts)==60,'actual marker count')
 for i,p in enumerate(pts):
  x=p['x_px'];y=p['y_px'];check(p['marker_index']==i,'index');check(i==0 or x-pts[i-1]['x_px']>=15,'one diamond per marker')
  xx=int(x);ys=np.where(blue[52:210,xx-1:xx+2])[0]+52;check(len(ys)>=20,'blue source pixels');close(y,(ys.min()+ys.max())/2,'vertical centre')
  n=(x-cal['x0'])*6000/(cal['x6000']-cal['x0']);r=100*(cal['y0']-y)/(cal['y0']-cal['y100']);b=300/(cal['y0']-cal['y100'])
  close(p['cycle_coordinate'],n,'cycle');close(p['retention_pct'],r,'retention');close(p['reading_bound_pp'],b,'pixel bound');close(p['cycle_upper'],n+3*6000/(cal['x6000']-cal['x0']),'cycle upper')
 check(pts[-1]['reading_interval_pp'][0]<=88<=pts[-1]['reading_interval_pp'][1],'author88 in fixed interval');check(q['conditions']['baseline_cycle_index'] is None,'unknown baseline retained')
 old=read(OLD/'curve_dataset_v3b.json');new=read(OUT/'curve_dataset_v3c.json');check(new[:-1]==old and new[-1]==q,'forward increment only')
 db=sqlite3.connect((OUT/'cycling_research_v3c.sqlite').as_uri()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
 check(db.execute('PRAGMA integrity_check').fetchone()[0]=='ok','integrity');check(not db.execute('PRAGMA foreign_key_check').fetchall(),'foreignkeys')
 for c in new:
  r=db.execute('SELECT * FROM curves WHERE curve_id=?',(c['curve_id'],)).fetchone();check(json.loads(r['raw_json'])==c,'curve bytes projection');check(r['target_retention_pct']==c['author_retention_pct'],'author label')
  for f in[.1,.2]:
   p=[p for p in c['points'] if p['cycle_upper']<=f*c['target_cycle_count']];w=db.execute('SELECT * FROM early_windows WHERE curve_id=? AND fraction=?',(c['curve_id'],f)).fetchone();check(w['point_count']==len(p),'point count');check(json.loads(w['point_indices_json'])==[v['marker_index']for v in p],'window indices')
   if p:
    x=np.array([v['cycle_coordinate']for v in p]);y=np.array([v['retention_pct']for v in p]);close(w['last_early_retention_pct'],y[-1],'last');close(w['early_mean_retention_pct'],y.mean(),'mean');close(w['early_retention_range_pp'],np.ptp(y),'range')
    if len(x)>1:close(w['early_retention_slope_per_1000_cycles'],float(np.linalg.lstsq(np.column_stack([np.ones(len(x)),x-x.mean()]),y,rcond=None)[0][1])*1000,'OLS slope')
 counts={}
 for system in['2E','3E']:
  for f in[.1,.2]:
   view=f'training_B_{system}_early{int(f*100)}';counts[view]=list(db.execute(f'SELECT count(*),count(DISTINCT source_family) FROM {view}').fetchone())
 check(counts=={'training_B_2E_early10':[5,5],'training_B_2E_early20':[7,7],'training_B_3E_early10':[20,19],'training_B_3E_early20':[30,24]},'cohort counts');db.close()
 # Locate the authoritative v7 database through its unchanged routing file.
 routing=read(ROOT/'data/current_training_latest.json');v7=ROOT/routing['directory']/routing['database_file']
 check(sha(v7)==routing['sha256']=='dd933ec815668060a10a1a828e2dcf8460eb862b16f4f9807d47b10a3816a097','canonical v7 preserved')
 write(OUT/'independent_verification_v3c.json',dict(status='passed',checks=checks,sqlite_sha256=sha(OUT/'cycling_research_v3c.sqlite'),counts=counts,original_labels_changed=0,formal_admissions=0,untouched_external_sources=0,visual_review='Actual blue diamond centres reviewed on preserved overlay; no interpolated points.',verifier_sha256=sha(Path(__file__))))
 print('PASS',checks,'local pixel/store checks; old3b and canonicalv7 unchanged')
if __name__=='__main__':main()
