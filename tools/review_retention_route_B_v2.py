"""Record visual QC before fitting; keep the original digitization immutable."""
from pathlib import Path
import hashlib,json,sys
import numpy as np
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.digitize_retention_markers_v2 import color_mask,marker_peaks
OUT=ROOT/'保持率双路线预研_v2_20261029'
def read(p):return json.loads(Path(p).read_text('utf8'))
def write(p,x):Path(p).write_bytes((json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode('utf8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def correct_magenta(q):
 # Visual review found split detections on the same hollow circle. The genuine
 # consecutive marker centres are about9px apart. An8px separation merges the
 # duplicate centres without adding or interpolating any observation.
 s=dict(q['calibration'],distance_override=8);image=Image.open(ROOT/q['figure_path']).convert('RGB');a=np.array(image);x1,y1,x2,y2=s['roi'];mask=color_mask(a[y1:y2,x1:x2],s['color']);peaks,_=marker_peaks(mask,s)
 ref=q['first_plotted_reference'];rh=ref['height_from_zero_px'];n=q['target_cycle_count'];dx=(s['xend']-s['x0'])/n;points=[]
 for peak in peaks:
  lo=max(0,peak-2);hi=min(mask.shape[1],peak+3);yy,xx=np.where(mask[:,lo:hi])
  if len(xx)<3:continue
  px=float(np.median(xx+lo+x1));py=float(np.median(yy+y1));cycle=(px-s['x0'])/dx
  if cycle<0 or cycle>n*1.02:continue
  h=s['absolute_zero_y']-py;v=100*h/rh;low=100*(h-3)/(rh+3);high=100*(h+3)/(rh-3)
  points.append(dict(marker_index=len(points),x_px=px,y_px=py,cycle_coordinate=cycle,cycle_lower=max(0,cycle-3/dx),cycle_upper=cycle+3/dx,retention_pct=v,reading_interval_pp=[low,high],reading_bound_pp=max(v-low,high-v),pixel_count=len(xx)))
 fixed=dict(q,points=points,calibration=s,correction_reason='Pre-fit visual QC: duplicate detections of hollow magenta markers, minimum centre distance5->8px. No target or pixel-axis calibration changed.')
 crop=image.crop((x1-8,y1-8,x2+8,y2+8));draw=ImageDraw.Draw(crop)
 for p in points:
  x=p['x_px']-x1+8;y=p['y_px']-y1+8;draw.rectangle((x-2,y-2,x+2,y+2),outline='cyan')
 for f,c in[(.1,'green'),(.2,'purple')]:
  x=s['x0']+f*(s['xend']-s['x0'])-x1+8;draw.line((x,0,x,crop.height),fill=c)
 crop.resize((crop.width*3,crop.height*3)).save(OUT/'evidence_overlays/candidate_V05_011_reviewed.png')
 return fixed

def main():
 dest=OUT/'reviewed_curve_data.json';assert not dest.exists(),'Never overwrite a reviewed dataset'
 curves=read(OUT/'curve_marker_candidates.json');review=[];accepted=[];excluded=[]
 for q in curves:
  assert sha(ROOT/q['figure_path'])==q['figure_sha256']
  raw_n=len(q['points'])
  if q['endpoint_id']=='candidate:V05:011':q=correct_magenta(q)
  windows=[]
  for f in [.1,.2]:
   pts=[p for p in q['points']if p['cycle_upper']<=f*q['target_cycle_count']]
   windows.append(dict(fraction=f,early_markers=len(pts),eligible_by_point_count=len(pts)>=3,marker_indices=[p['marker_index']for p in pts],maximum_early_retention_reading_bound_pp=max([p['reading_bound_pp']for p in pts],default=None)))
  q=dict(q,window_availability=windows)
  reasons=[]
  if q['endpoint_consistent_with_graph_bound']is not True:reasons.append('Author final retention is outside the graph reading bound; unresolved graph/text disagreement, freeze B only.')
  if not any(w['eligible_by_point_count']for w in windows):reasons.append('Fewer than3 colour-identifiable early observations in both declared windows; overlapping plot symbols are not invented.')
  q['visual_review']=dict(status='exclude_pending_evidence'if reasons else'accepted_for_exploratory_B',reviewer='Codex visual inspection of original plots and cyan-centre overlays before B fits',reasons=reasons,raw_point_count=raw_n,reviewed_point_count=len(q['points']),future_target_not_used_in_normalization=True,precision='Graph-read feature intervals are conservative3px bounds, not instrument measurements or confidence intervals.',curve_sampling='Actual visible plotted marks/trace; adjacent pixels are never independent experiments.')
  q['training_eligible_pending_visual_review']=not reasons
  (excluded if reasons else accepted).append(q['endpoint_id']);review.append(q)
 write(dest,review)
 write(OUT/'curve_review_receipt.json',dict(raw_sha256=sha(OUT/'curve_marker_candidates.json'),reviewed_sha256=sha(dest),review_program_sha256=sha(Path(__file__)),accepted_endpoint_ids=accepted,excluded_endpoint_ids=excluded,old_author_labels_changed=0,old_databases_changed=0,pre_fit=True,not_exhaustive_corpus_extraction=True))
 for system in ['2E','3E']:
  for f in [.1,.2]:
   a=[q for q in review if q['system']==system and q['training_eligible_pending_visual_review']and next(w for w in q['window_availability']if w['fraction']==f)['eligible_by_point_count']]
   print(system,f,'curves',len(a),'sources',len({q['source_family']for q in a}))
 print('Excluded',excluded)
if __name__=='__main__':main()
