"""Remaining fixed PDF queue: real markers or dense published traces, not fitted data."""
from pathlib import Path
import hashlib,json,sys
import numpy as np
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.digitize_retention_markers_v2 import color_mask,marker_peaks
BASE=ROOT/'保持率达标研究_v3_主线与近优组合_20261030/第二轮_证据与曲线扩充'
OUT=BASE/'batch2_digitization_review_v3'
def read(p):return json.loads(Path(p).read_text('utf8'))
def write(p,x):Path(p).write_bytes((json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode('utf8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def mask_for(a,color):
 r,g,b=(a[:,:,i].astype(float)for i in range(3))
 if color=='steelblue':return(b>130)&(g>90)&(b>1.2*r)&(b>1.05*g)&(g>1.05*r)
 if color=='teal':return(g>65)&(b>65)&(r<.65*np.minimum(g,b))&(g<1.35*b)&(b<1.35*g)
 if color=='mint_green':return(g>100)&(g>1.2*r)&(g>1.05*b)
 return color_mask(a,color)
def specifications():
 s=[]
 def add(name,doi,sample,roi,x0,xend,yticks,color,mode='markers',**extra):
  row=dict(name=name,identity='doi:'+doi,sample=sample,roi=roi,x0=x0,xend=xend,yticks=yticks,color=color,mode=mode,height=3,prominence=.6,distance=6,pixel_bound=3);row.update(extra);s.append(row)
 add('OAC623','10.1007/s00339-023-07141-8','OAC623',[121,111,531,169],120,524,None,'blue',absolute_zero_y=402,reference_roi=[121,115,129,126])
 add('AMFS','10.1007/s10854-026-18573-2','AMFS-derived activated carbon',[192,110,945,139],167,927,[[124,100],[616,0]],'magenta',distance=30,marker_centroid_radius=13)
 add('NCHU20','10.1016/j.biombioe.2026.109160','NCHU20',[153,82,536,123],140,534,[[83,100],[474,0]],'red','dense_trace',trace_step=4,top_cluster=True,identity_note='Upper red-family curve matches NCHU20 orange/red legend and printed NAC20:91.08%; dark burgundy lower trace is NCHU0. Caption identifies this as electrode cycling, not the following CO2 adsorption panel.')
 add('CCL','10.1016/j.biombioe.2026.109168','CCL-K2CO3-1-700',[90,76,503,116],94,496,[[110,100],[389,0]],'red',distance=6)
 add('PCSKOH','10.1016/j.jaap.2026.107754','P-doped CSKOH',[92,106,759,147],90,750,None,'steelblue',absolute_zero_y=675,reference_roi=[92,108,100,123],distance=35,identity_note='Sparse marked C(N); connecting segments do not create new early observations.')
 add('NPC700','10.1016/j.jenvman.2025.125582','NPC-700-6',[134,53,687,108],130,679,[[83.5,100],[515.5,0]],'orange','dense_trace',trace_step=6,exclude_rects=[[560,94,690,145]])
 add('ABC02','10.1016/j.jenvman.2026.129124','A-BC-0.2',[104,50,596,91],109,587,[[56,100],[441,0]],'red',distance=18,marker_centroid_radius=6,exclude_rects=[[582,90,595,200]])
 add('C600','10.1016/j.jpcs.2023.111318','C/600C',[66,17,619,32],62,620,[[18,100],[467,0]],'red','dense_trace',trace_step=6,identity_note='Red retention series on right axis; black C(N) on left is not used for these percent features.')
 add('AC3','10.1021/acs.energyfuels.4c01398','AC3',[95,120,560,166],92,562,None,'black','dense_trace',trace_step=6,absolute_zero_y=503.75,reference_roi=[94,118,97,153],manual_hold='Initial black C(N) overlaps the vertical axis and falls sharply before the first clearly readable mark; own initial denominator cannot be identified reliably. Do not borrow the separate rate-test bar or infer C0 from final91%.',exclude_rects=[[350,95,570,146]])
 add('EUAC160','10.1021/acsomega.4c11529','EUAC1-60',[152,79,672,164],154,667,[[111,100],[489,0]],'red','dense_trace',trace_step=6)
 add('ALPC800','10.1021/acssusresmgt.3c00028','ALPC-800',[106,70,560,94],110,553,[[82,100],[302,95]],'red',electrolyte='H2SO4',distance=12)
 add('ALPC800','10.1021/acssusresmgt.3c00028','ALPC-800',[106,70,560,94],110,553,[[82,100],[302,95]],'blue',electrolyte='Na2SO4',distance=12)
 add('AUACW','10.1039/d4cp01914h','AUACW',[90,126,1000,171],83,980,[[138.5,100],[365.96,20]],'green',distance=18,marker_centroid_radius=10,exclude_rects=[[780,85,995,134]])
 add('OPBNP','10.1039/d4ta02115k','OPBNP',[88,55,1254,94],82,1254,[[61,100],[311,0]],'blue','dense_trace',trace_step=6,exclude_rects=[[1030,30,1190,64]])
 for sample,color in[('OPB','blue'),('OPNP','magenta'),('OPC','teal')]:add('OPB_series','10.1039/d4ta02115k',sample,[70,48,407,121],67,395,[[55,100],[298,0]],color,distance=22,height=4,prominence=1.2,marker_centroid_radius=6,identity_note='Sparse summary markers: no added points from connecting lines, no assumed initial marker hidden under another series.')
 add('SSC2','10.1039/d4ya00076e','SSC2-0.6',[53,26,309,51],49,307,[[30,100],[225,0]],'green',distance=4)
 add('CMC','10.1039/d6nj00244g','CMC',[80,35,295,47],78,293,[[40,100],[185,0]],'red','dense_trace',trace_step=6,identity_note='Three-electrode Fig4i lower dense filled-red retention trace, not pale upper CE or two-electrode Fig5. Restricted vertical band excludes printed96.7% at y48+. Sampling actual dense trace columns is not raw observation count.')
 add('SS300','10.1088/1361-6528/ace97a','SS-300',[42,53,402,77],44,391,[[60.8333333333,100],[265,0]],'mint_green',distance=5,height=2.5,prominence=.5,marker_centroid_radius=3,identity_note='Green series read on right Percent axis at98.3% annotation; do not normalize left C(F/g) or use pink series.')
 add('RSM','10.3390/molecules28124633','RSM-0.33-550',[77,316,487,340],74,488,[[58.5,0],[333.5,100]],'orange',distance=6,exclude_rects=[[352,250,365,323]],manual_hold='Orange inverted-axis terminal marker is partly occluded at frame; current plot reading is not sufficient to reconcile author96.3%. Preserve original label and hold B input pending better evidence.',identity_note='Orange right retention axis is inverted (0 at top), not red C(F/g).')
 return s
def main():
 assert not OUT.exists(),'Do not overwrite digitization batch'
 OUT.mkdir();(OUT/'overlays').mkdir();spec=specifications();write(OUT/'calibration.json',spec);panels={r['name']:r for r in read(BASE/'batch2_panel_receipt.json')};records=read(ROOT/'保持率双路线预研_v2_20261029/baseline_inputs.json')['3E'];curves=[]
 for s in spec:
  matches=[r for r in records if r['source_family']==s['identity']and r['sample_name']==s['sample']and('electrolyte'not in s or r['features']['electrolyte']==s['electrolyte'])];assert len(matches)==1,(s['name'],s['sample'],len(matches));rec=matches[0];pa=panels[s['name']];path=ROOT/pa['panel_path'];assert sha(path)==pa['panel_sha256'];im=Image.open(path).convert('RGB');a=np.array(im);x1,y1,x2,y2=s['roi'];assert 0<=x1<x2<=im.width and 0<=y1<y2<=im.height
  mask=mask_for(a[y1:y2,x1:x2],s['color'])
  for ex1,ey1,ex2,ey2 in s.get('exclude_rects',[]):mask[max(0,ey1-y1):min(y2-y1,ey2-y1),max(0,ex1-x1):min(x2-x1,ex2-x1)]=False
  positions=list(range(0,mask.shape[1],s.get('trace_step',6)))if s['mode']=='dense_trace'else marker_peaks(mask,s)[0]
  if s['mode']=='dense_trace':
   cols=np.flatnonzero(mask.any(axis=0))
   if len(cols):positions=sorted(set(positions+[int(cols[0]),int(cols[-1])]))
  reference=None
  if s['yticks']is None:
   rx1,ry1,rx2,ry2=s['reference_roi'];m=mask_for(a[ry1:ry2,rx1:rx2],s['color']);yy,xx=np.where(m);assert len(xx)>=2,('No own reference',s['name']);ref_y=float(np.median(yy+ry1));ref_h=s['absolute_zero_y']-ref_y;reference=dict(y_px=ref_y,height_from_zero_px=ref_h,roi=s['reference_roi'],cycle_coordinate_note='Own first readable plotted region; exact true first/conditioning cycle unknown. No endpoint calibration.')
  else:(yp,vp),(yq,vq)=s['yticks'];slope=(vq-vp)/(yq-yp)
  points=[];N=rec['features']['cycle_count'];dx=(s['xend']-s['x0'])/N
  for peak in positions:
   radius=1 if s['mode']=='dense_trace'else s.get('marker_centroid_radius',3);lo=max(0,peak-radius);hi=min(mask.shape[1],peak+radius+1);yy,xx=np.where(mask[:,lo:hi])
   if len(xx)<2:continue
   if s.get('top_cluster'):
    cut=float(np.min(yy))+4;choose=yy<=cut;yy=yy[choose];xx=xx[choose]
   px=float(np.median(xx+lo+x1));py=float(np.median(yy+y1))
   if s['mode']=='markers'and radius>3:
    counts=mask[:,lo:hi].sum(axis=0).astype(float);baseline=float(np.quantile(counts,.2));signal=np.maximum(0,counts-baseline)
    if signal.sum()>0:px=float(np.average(np.arange(lo,hi)+x1,weights=signal))
   n=(px-s['x0'])/dx
   if n<0 or n>N*1.02:continue
   if reference:
    h=s['absolute_zero_y']-py;value=100*h/ref_h;low=100*(h-3)/(ref_h+3);high=100*(h+3)/(ref_h-3)
   else:value=vp+(py-yp)*slope;low=value-3*abs(slope);high=value+3*abs(slope)
   points.append(dict(marker_index=len(points),x_px=px,y_px=py,cycle_coordinate=n,cycle_lower=max(0,n-3/dx),cycle_upper=n+3/dx,retention_pct=value,reading_interval_pp=[low,high],reading_bound_pp=max(value-low,high-value),pixel_count=len(xx),sampling_mode=s['mode']))
  if s['name']=='AUACW':
   ex1,ey1,ex2,ey2=968,145,986,166;em=mask_for(a[ey1:ey2,ex1:ex2],'green');ey,ex=np.where(em);assert len(ex)==85,'Verified terminal fragment changed'
   px=float(np.median(ex+ex1));py=float(np.median(ey+ey1));n=(px-s['x0'])/dx;value=vp+(py-yp)*slope;bound=3*abs(slope)
   assert n>points[-1]['cycle_coordinate']
   points.append(dict(marker_index=len(points),x_px=px,y_px=py,cycle_coordinate=n,cycle_lower=max(0,n-6/dx),cycle_upper=n+6/dx,retention_pct=value,reading_interval_pp=[value-bound,value+bound],reading_bound_pp=bound,pixel_count=len(ex),sampling_mode='visible_edge_fragment',fragment_roi=[ex1,ey1,ex2,ey2],x_reading_bound_px=6,note='Real terminal green marker fragment partly occluded at border; pixelmedian used without forcing exactN or author target. Outside early windows.'))
  assert points,s['name'];last=points[-1];consistent=last['cycle_coordinate']>=.97*N and last['reading_interval_pp'][0]-.1<=rec['target']<=last['reading_interval_pp'][1]+.1;windows=[]
  for f in[.1,.2]:
   ps=[p for p in points if p['cycle_upper']<=f*N];windows.append(dict(fraction=f,early_markers=len(ps),eligible_by_point_count=len(ps)>=3,marker_indices=[p['marker_index']for p in ps],maximum_early_retention_reading_bound_pp=max([p['reading_bound_pp']for p in ps],default=None)))
  q=dict(curve_id='pdf_curve_v3b:'+rec['row_id'],endpoint_id=rec['row_id'],sample_name=rec['sample_name'],source_family=rec['source_family'],system='3E',target_cycle_count=N,author_retention_pct=rec['target'],features=rec['features'],conditions=rec['conditions'],figure_path=pa['panel_path'],figure_sha256=pa['panel_sha256'],panel_provenance=pa,calibration=s,first_plotted_reference=reference,points=points,window_availability=windows,endpoint_consistent_with_graph_bound=consistent,training_eligible_pending_visual_review=False,manual_hold=s.get('manual_hold'),sampling_note='Markers retain actual visible markers only. Dense-trace columns are approximate published curve locations, not an asserted raw measurement count; no interpolated points or independent sample inflation. Sparse connecting lines are never densified.',genuinely_new_external_source=False)
  curves.append(q);overlay=im.copy();draw=ImageDraw.Draw(overlay)
  for p in points:
   x=p['x_px'];y=p['y_px'];draw.rectangle((x-2,y-2,x+2,y+2),outline='cyan')
  for f,c in[(.1,'green'),(.2,'purple')]:x=s['x0']+f*(s['xend']-s['x0']);draw.line((x,max(0,y1-15),x,min(im.height,y2+15)),fill=c,width=1)
  overlay.save(OUT/'overlays'/(rec['row_id'].replace(':','_')+'.png'))
 write(OUT/'candidates.json',curves)
 write(OUT/'revision_receipt.json',dict(previous_candidates_sha256=sha(BASE/'batch2_digitization_review_v2/candidates.json'),previous_calibration_sha256=sha(BASE/'batch2_digitization_review_v2/calibration.json'),revision_reason='Before any phase2 fit: CMC annotation exclusion and actual dense-trace sampling; AUACW independently visible terminal marker fragment, unchanged early features. Previous candidates/calibration and author labels preserved. No result-based filtering or label changes.',new_extractor_sha256=sha(Path(__file__)),phase2_model_fits_before_revision=0))
 for q in curves:print(q['endpoint_id'],q['sample_name'],'points',len(q['points']),'early',[(w['fraction'],w['early_markers'])for w in q['window_availability']],'author',q['author_retention_pct'],'graph',round(q['points'][-1]['retention_pct'],3),'bound',round(q['points'][-1]['reading_bound_pp'],3),'consistent',q['endpoint_consistent_with_graph_bound'],'manual_hold',bool(q['manual_hold']))
if __name__=='__main__':main()
