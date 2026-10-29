"""Digitize three inspected original PDF figures; no model or author-label edits."""
from pathlib import Path
import hashlib,json,sys
import numpy as np
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.digitize_retention_markers_v2 import color_mask,marker_peaks
OUT=ROOT/'保持率达标研究_v3_主线与近优组合_20261030/第二轮_证据与曲线扩充'
def read(p):return json.loads(Path(p).read_text('utf8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,x):Path(p).write_bytes((json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode('utf8'))
def main():
 dest=OUT/'new_curve_candidates.json';assert not dest.exists(),'Do not overwrite digitization'
 spec=[dict(name='YZPC3',crop_rect=[1028,721,2055,1442],roi=[180,63,952,108],x0=187,xend=943,yticks=[[72,100],[650,0]],color='blue',height=4,prominence=.8,distance=12,pixel_bound=3),dict(name='KAC5',crop_rect=[834,1340,1669,2010],roi=[229,82,790,151],exclude_rects=[[670,65,810,112]],x0=235,xend=778,yticks=[[91,100],[568,0]],color='red',height=4,prominence=.8,distance=7,pixel_bound=3),dict(name='RMAC800',crop_rect=[730,625,1153,936],roi=[85,65,344,95],x0=90,xend=338,yticks=[[35,120],[259,0]],color='red',height=2,prominence=.5,distance=4,pixel_bound=3)]
 write(OUT/'new_curve_calibration.json',spec);evidence={r['name']:r for r in read(OUT/'new_figure_evidence.json')};curves=[]
 for s in spec:
  ev=evidence[s['name']];assert sha(ROOT/ev['pdf_path'])==ev['pdf_sha256']and sha(ROOT/ev['figure_path'])==ev['figure_sha256'];rec=ev['baseline_records'][0];path=OUT/'evidence'/(s['name']+'_cycle_panel.png');im=Image.open(path).convert('RGB');a=np.array(im);x1,y1,x2,y2=s['roi'];mask=color_mask(a[y1:y2,x1:x2],s['color'])
  for ex1,ey1,ex2,ey2 in s.get('exclude_rects',[]):mask[max(0,ey1-y1):min(y2-y1,ey2-y1),max(0,ex1-x1):min(x2-x1,ex2-x1)]=False
  peaks,_=marker_peaks(mask,s);N=rec['features']['cycle_count'];dx=(s['xend']-s['x0'])/N;(yp,vp),(yq,vq)=s['yticks'];slope=(vq-vp)/(yq-yp);points=[]
  for peak in peaks:
   lo=max(0,peak-2);hi=min(mask.shape[1],peak+3);yy,xx=np.where(mask[:,lo:hi])
   if len(xx)<3:continue
   px=float(np.median(xx+lo+x1));py=float(np.median(yy+y1));n=(px-s['x0'])/dx
   if n<0 or n>N*1.02:continue
   value=vp+(py-yp)*slope;bound=abs(slope)*3;points.append(dict(marker_index=len(points),x_px=px,y_px=py,original_figure_x_px=px+s['crop_rect'][0],original_figure_y_px=py+s['crop_rect'][1],cycle_coordinate=n,cycle_lower=max(0,n-3/dx),cycle_upper=n+3/dx,retention_pct=value,reading_interval_pp=[value-bound,value+bound],reading_bound_pp=bound,pixel_count=len(xx)))
  last=points[-1];consistent=last['cycle_coordinate']>=.97*N and last['reading_interval_pp'][0]-.1<=rec['target']<=last['reading_interval_pp'][1]+.1;windows=[]
  for f in[.1,.2]:
   early=[p for p in points if p['cycle_upper']<=f*N];windows.append(dict(fraction=f,early_markers=len(early),marker_indices=[p['marker_index']for p in early],eligible_by_point_count=len(early)>=3,maximum_early_retention_reading_bound_pp=max([p['reading_bound_pp']for p in early],default=None)))
  q=dict(curve_id='pdf_curve_v3:'+rec['row_id'],endpoint_id=rec['row_id'],sample_name=rec['sample_name'],source_family=rec['source_family'],system='3E',target_cycle_count=N,author_retention_pct=rec['target'],features=rec['features'],conditions=rec['conditions'],figure_path=path.relative_to(ROOT).as_posix(),figure_sha256=sha(path),pdf_provenance=ev,calibration=s,first_plotted_reference=None,points=points,window_availability=windows,endpoint_consistent_with_graph_bound=consistent,training_eligible_pending_visual_review=False,normalization='Explicit author retention axis; no rescaling to author endpoint and no assumed first-cycle baseline.',evidence_purpose='New early-curve input for previously used endpoint/source, not a genuinely new independent test source.')
  curves.append(q);overlay=im.copy();draw=ImageDraw.Draw(overlay)
  for p in points:
   x=p['x_px'];y=p['y_px'];draw.rectangle((x-3,y-3,x+3,y+3),outline='cyan')
  for f,c in[(.1,'green'),(.2,'purple')]:x=s['x0']+f*(s['xend']-s['x0']);draw.line((x,50,x,y2+8),fill=c,width=2)
  overlay.save(OUT/'evidence'/(s['name']+'_cycle_overlay.png'))
 write(dest,curves)
 print(json.dumps([dict(sample=q['sample_name'],markers=len(q['points']),early=[(w['fraction'],w['early_markers'])for w in q['window_availability']],gold=q['author_retention_pct'],graph=q['points'][-1]['retention_pct'],bound=q['points'][-1]['reading_bound_pp'],consistent=q['endpoint_consistent_with_graph_bound'])for q in curves],ensure_ascii=False,indent=2))
if __name__=='__main__':main()
