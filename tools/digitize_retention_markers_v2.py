"""Sample inspected original markers, not synthetic trajectories; preserve bounds."""
from pathlib import Path
import collections, hashlib, json, math
import numpy as np
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'保持率双路线预研_v2_20261029'
P='同体系文献补充_第二批_20261017/定向扩搜40至60篇_20261017/sources/'
def read(p):return json.loads(Path(p).read_text('utf8'))
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n','utf8')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def color_mask(a,color):
 r,g,b=(a[:,:,i].astype(float)for i in range(3))
 if color=='red':return(r>130)&(r>1.35*g)&(r>1.35*b)
 if color=='blue':return(b>110)&(b>1.5*r)&(b>1.2*g)
 if color in ['magenta','purple']:return(r>75)&(b>75)&(g<.65*np.minimum(r,b))
 if color=='green':return(g>65)&(g>1.25*r)&(g>1.25*b)
 if color=='orange':return(r>150)&(g>70)&(g<.88*r)&(b<.85*g)
 if color=='black':return(np.max(a,axis=2)-np.min(a,axis=2)<40)&(np.max(a,axis=2)<130)
 raise ValueError(color)
def specs():
 s=[]
 def add(id,path,roi,x0,xend,yticks,color,**kwargs):s.append(dict(endpoint_id=id,path=path,roi=roi,x0=x0,xend=xend,yticks=yticks,color=color,height=3,prominence=.6,distance=5,pixel_bound=3,**kwargs))
 wood='文献全量利用复核_20261028/批次26_木粉炭化系列与锰复合全样品/evidence/gr10.jpg'
 add('candidate:TE037',wood,[53,40,291,125],49,288,[[22,100],[215,50]],'blue')
 add('candidate:TE038',wood,[53,35,291,190],49,288,[[22,100],[215,50]],'magenta')
 pine='三电极端点扩充_20261018/new_sources/PMC10056672/assets/micromachines-14-00572-g008.jpg'
 add('candidate:TE033',pine,[97,25,721,105],92,720,[[22,100],[517,60]],'black',distance_override=12)
 add('candidate:TE034',pine,[94,14,721,62],92,720,[[22,100],[517,60]],'red',distance_override=12)
 add('candidate:TE020',P+'OA059/figures/nanomaterials-13-01654-g007.jpg',[57,29,369,65],57,366,[[36,100],[252,40]],'blue')
 add('candidate:TE052','三电极端点扩充_20261018/new_sources/PMC12158216/assets/polymers-17-01544-g007.jpg',[104,87,667,151],102,665,[[96,100],[475,50]],'red',distance_override=7)
 add('candidate:TE035','三电极端点扩充_20261018/new_sources/PMC10759806/assets/d3ra07014j-f7.jpg',[59,44,340,78],56,338,[[61,100],[214,40]],'red',distance_override=7)
 q=P+'OA004/figures/ao3c04692_0008.jpg'
 for id,color,band in [('candidate:V05:008','black',[198,214]),('candidate:V05:009','red',[126,146]),('candidate:V05:010','blue',[34,56]),('candidate:V05:011','magenta',[132,153])]:
  add(id,q,[54,band[0],359,band[1]],50,357,None,color,absolute_zero_y=229,reference_roi=[51,band[0],55,band[1]])
 q2=P+'OA004/figures/ao3c04692_0011.jpg'
 add('candidate:V05:012',q2,[81,40,324,62],83,322,[[44,100],[224,0]],'black',distance_override=6)
 add('candidate:V05:013',q2,[77,305,322,328],79,319,[[309,100],[491,0]],'black',distance_override=6)
 add('candidate:V05:014',P+'OA011/figures/d5ra01262g-f8.jpg',[432,645,678,670],430,675,[[617,120],[855,0]],'red')
 add('legacy:SRC124_CY01','三电极端点扩充_20261018/new_sources/PMC12794195/assets/d5ra08165c-f5.jpg',[291,432,482,457],289,480,None,'black',absolute_zero_y=582,reference_roi=[291,435,295,447],distance_override=4)
 add('v25:Mango_MK9_2E_C100000',P+'OA015/figures/d5ra02129d-f10.jpg',[76,32,317,92],76,314,[[42,100],[237,0]],'green',distance_override=8)
 add('v23:NTAC_2E_C10000','文献全量利用复核_20261026/批次11_青豌豆皮水葫芦红茶与Tondolo/evidence/d6ra02137a-f8.jpg',[430,285,678,307],430,676,[[290,100],[475,0]],'orange')
 add('candidate:V05:019',P+'OA048/figures/nanomaterials-14-00686-g009.jpg',[446,267,772,295],445,770,None,'green',absolute_zero_y=464,reference_roi=[446,275,452,291])
 add('candidate:TE009',P+'OA007/figures/molecules-28-06543-g006.jpg',[413,334,666,367],410,666,[[328,100],[519,0]],'black',distance_override=4)
 add('candidate:V05:018',P+'OA043/figures/nanomaterials-13-02431-g006.jpg',[100,43,659,67],94,659,[[37,100],[319,0]],'red',distance_override=7)
 add('v25:Leather_ANSC8_3E_C10000','文献全量利用复核_20261026/批次13_芒果核皮革糠醛渣与界面参考/evidence/d6ra04144b-f5.jpg',[427,603,679,617],425,675,[[610,100],[795,0]],'purple',distance_override=6)
 add('candidate:TE007',P+'OA001/figures/molecules-31-02329-g004.jpg',[407,314,661,337],404,660,[[321,100],[470,0]],'red',distance_override=6)
 return s
def marker_peaks(mask,s):
 counts=mask.sum(axis=0).astype(float);score=np.convolve(counts,[.25,.5,.25],mode='same');distance=s.get('distance_override',s['distance']);candidates=[]
 for i in range(1,len(score)-1):
  if score[i]<s['height']or score[i]<score[i-1]or score[i]<score[i+1]:continue
  left=max(0,i-distance);right=min(len(score),i+distance+1)
  if score[i]-min(np.min(score[left:i+1]),np.min(score[i:right]))<s['prominence']:continue
  candidates.append(i)
 chosen=[]
 for i in sorted(candidates,key=lambda i:(-score[i],i)):
  if all(abs(i-j)>=distance for j in chosen):chosen.append(i)
 return sorted(chosen),counts.tolist()
def main():
 dest=OUT/'curve_marker_candidates.json';assert not dest.exists(),'Do not overwrite reviewed digitization'
 raw=read(OUT/'baseline_inputs.json');records={r['row_id']:(system,r)for system,rs in raw.items()for r in rs};output=[];(OUT/'evidence_overlays').mkdir(exist_ok=True)
 spec=specs();write(OUT/'trace_calibration_spec.json',spec)
 for s in spec:
  system,rec=records[s['endpoint_id']];image=Image.open(ROOT/s['path']).convert('RGB');a=np.array(image);x1,y1,x2,y2=s['roi'];assert x2<=a.shape[1]and y2<=a.shape[0],(s['path'],a.shape,s['roi'])
  mask=color_mask(a[y1:y2,x1:x2],s['color']);peaks,counts=marker_peaks(mask,s);n=rec['features']['cycle_count'];dx=(s['xend']-s['x0'])/n;reference=None
  if s['yticks']is None:
   rx1,ry1,rx2,ry2=s['reference_roi'];rm=color_mask(a[ry1:ry2,rx1:rx2],s['color']);ys,xs=np.where(rm);assert len(xs)>=2,'No own reference marker: '+s['endpoint_id'];refy=float(np.median(ys+ry1));refheight=s['absolute_zero_y']-refy;assert refheight>s['pixel_bound'];reference=dict(y_px=refy,height_from_zero_px=refheight,roi=s['reference_roi'],cycle_coordinate_note='first plotted reference-marker region; true conditioning/first-cycle index not invented')
  else:(yp,vp),(yq,vq)=s['yticks'];slope=(vq-vp)/(yq-yp)
  points=[]
  for peak in peaks:
   lo=max(0,peak-2);hi=min(mask.shape[1],peak+3);yy,xx=np.where(mask[:,lo:hi])
   if len(xx)<3:continue
   px=float(np.median(xx+lo+x1));py=float(np.median(yy+y1));cycle=(px-s['x0'])/dx
   if cycle<0 or cycle>n*1.02:continue
   if reference:
    height=s['absolute_zero_y']-py;value=100*height/refheight;low=100*(height-s['pixel_bound'])/(refheight+s['pixel_bound']);high=100*(height+s['pixel_bound'])/(refheight-s['pixel_bound'])
   else:value=vp+(py-yp)*slope;bound=abs(slope)*s['pixel_bound'];low=value-bound;high=value+bound
   points.append(dict(marker_index=len(points),x_px=px,y_px=py,cycle_coordinate=cycle,cycle_lower=max(0,cycle-s['pixel_bound']/dx),cycle_upper=cycle+s['pixel_bound']/dx,retention_pct=float(value),reading_interval_pp=[float(low),float(high)],reading_bound_pp=float(max(value-low,high-value)),pixel_count=len(xx)))
  cid='marker_v2:'+s['endpoint_id'];last=points[-1]if points else None;consistent=None
  if last and last['cycle_coordinate']>=.97*n:consistent=last['reading_interval_pp'][0]-.1<=rec['target']<=last['reading_interval_pp'][1]+.1
  states=[]
  for fraction in [.1,.2]:
   early=[p for p in points if p['cycle_upper']<=fraction*n]
   states.append(dict(fraction=fraction,early_markers=len(early),eligible_by_point_count=len(early)>=3,marker_indices=[p['marker_index']for p in early],maximum_early_retention_reading_bound_pp=max([p['reading_bound_pp']for p in early],default=None)))
  row=dict(curve_id=cid,endpoint_id=s['endpoint_id'],sample_name=rec['sample_name'],source_family=rec['source_family'],system=system,target_cycle_count=n,author_retention_pct=rec['target'],features=rec['features'],conditions=rec['conditions'],figure_path=s['path'],figure_sha256=sha(ROOT/s['path']),calibration=s,first_plotted_reference=reference,points=points,window_availability=states,endpoint_consistent_with_graph_bound=consistent,training_eligible_pending_visual_review=False,provenance='Existing reviewed endpoint plus actual color-isolated marker-pixel centroids; no interpolation, no simulated values, reading intervals are conservative pixel bounds not confidence intervals.')
  output.append(row)
  crop=image.crop((max(0,x1-8),max(0,y1-8),min(image.width,x2+8),min(image.height,y2+8)));draw=ImageDraw.Draw(crop);ox=max(0,x1-8);oy=max(0,y1-8)
  for p in points:xx=p['x_px']-ox;yy=p['y_px']-oy;draw.rectangle((xx-2,yy-2,xx+2,yy+2),outline='cyan',width=1)
  for fraction,color in[(.1,'green'),(.2,'purple')]:x=s['x0']+fraction*(s['xend']-s['x0'])-ox;draw.line((x,0,x,crop.height),fill=color,width=1)
  crop.save(OUT/'evidence_overlays'/(s['endpoint_id'].replace(':','_')+'.png'))
 write(dest,output)
 print(json.dumps([dict(id=r['endpoint_id'],system=r['system'],markers=len(r['points']),windows=r['window_availability'],last=r['points'][-1]if r['points']else None,gold=r['author_retention_pct'],consistent=r['endpoint_consistent_with_graph_bound'])for r in output],ensure_ascii=False,indent=2))
if __name__=='__main__':main()
