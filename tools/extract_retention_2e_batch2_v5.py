"""Actual dense traces and sparse glyphs from next four prespecified local sources."""
from pathlib import Path
import hashlib,json,math
import numpy as np
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'保持率达标研究_v3_主线与近优组合_20261030/第十一轮_双电极原文曲线补充/batch2_20261031'
def read(p):return json.loads(Path(p).read_text('utf8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,x):Path(p).write_bytes((json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode('utf8'))
def components(mask):
 seen=np.zeros(mask.shape,dtype=bool);result=[]
 for y,x in zip(*np.where(mask)):
  if seen[y,x]:continue
  stack=[(y,x)];seen[y,x]=True;pixels=[]
  while stack:
   yy,xx=stack.pop();pixels.append((yy,xx))
   for dy,dx in[(1,0),(-1,0),(0,1),(0,-1)]:
    ny,nx=yy+dy,xx+dx
    if 0<=ny<mask.shape[0]and 0<=nx<mask.shape[1]and mask[ny,nx]and not seen[ny,nx]:seen[ny,nx]=True;stack.append((ny,nx))
  if len(pixels)>=9:result.append(pixels)
 return result
def solid_markers(mask):
 eroded=mask.copy()
 for dy in[-1,0,1]:
  for dx in[-1,0,1]:eroded &=np.roll(np.roll(mask,dy,0),dx,1)
 points=[]
 for pixels in components(eroded):
  yy,xx=np.array(pixels).T;w=xx.max()-xx.min()+1;h=yy.max()-yy.min()+1
  if 3<=w<=16 and 3<=h<=16:
   x=float((xx.min()+xx.max())/2);y=float((yy.min()+yy.max())/2);points.append((x,y,dict(eroded_bbox=[int(xx.min()),int(yy.min()),int(xx.max()),int(yy.max())],pixel_count=len(pixels))))
 return sorted(points)
def main():
 assert not(OUT/'extracted_curve_candidates_v2.json').exists(),'Preserve extracted evidence'
 baseline={r['row_id']:r for r in read(ROOT/'保持率双路线预研_v2_20261029/baseline_inputs.json')['2E']};receipts=read(OUT/'figure_receipts.json');oldplan=read(OUT/'review_plan.json');spec=[]
 for label,eid,color in[('PC','incoming:ADD_054_T01','red'),('PC_D','incoming:ADD_054_T02','blue'),('PC_W','incoming:ADD_054_T03','purple')]:spec.append(dict(label=label,eid=eid,file='PC_cycle_panel.png',source_label='PC',mode='dense',color=color,cal=dict(x0=65.5,xN=641.5,y0=856.5,y100=67.5,N=25000),roi=[(24,130),(24,105),(50,85)][['red','blue','purple'].index(color)],crop=[1490,570,2155,1080],figure='Fig7f'))
 spec += [dict(label='BLAC900',eid='incoming:ADD_007_T01',file='BLAC_original.jpg',source_label='BLAC',mode='absolute_C',cal=dict(x0=150.5,xN=944.,y0=690.,y100=15.5,N=5000),roi=[320,368],figure='Fig7d_absolute_C(N)',crop=None),dict(label='ACK',eid='legacy:R111_CY01',file='ACK_cycle_panel.png',source_label='ACK',mode='magenta_rings',cal=dict(x0=101.,xN=503.5,y0=410.,y100=41.5,N=2000),roi=[32,94],figure='Fig5F',crop=[1200,485,1800,930]),dict(label='CE_KOH',eid='incoming:ADD_043_T01',file='CE_KOH_cycle_panel.png',source_label='CE_KOH',mode='solid_circles',cal=dict(x0=51.5,xN=727.5,y0=600.,y100=54.5,N=10000),roi=[31,85],first_visible_partial_marker=[51.5,54.5],figure='Fig6f',crop=[940,1360,1723,2051]),dict(label='CE_acid',eid='incoming:ADD_043_T02',file='CE_acid_cycle_panel.png',source_label='CE_acid',mode='solid_circles',cal=dict(x0=41.5,xN=672.,y0=594.,y100=85.5,N=10000),roi=[69,145],first_visible_partial_marker=[41.5,85.5],figure='Fig8f',crop=[900,1300,1658,1989])]
 write(OUT/'extraction_plan_v2.json',dict(specifications=spec,minimum_points=3,pixel_bound=3,endpoint_tolerance_pp=.1,author_targets_changed=False,source_labels='All7 predetermined endpoints ofnext4sources. Directretention curves/absoluteC(N) distinct. Graph axis andauthors labels preserved; never scale to endpoint. Partial axis marker usedonlywhere visiblypresent and sameglyph geometry. Dense mode samples actual observed coloured glyph/trace pixels,no interpolation or sparse-line densification.',absolute_reference='Own first plotted C(N) point only; propagated numerator/reference3px boxes,not borrowed GCD rate capacitance. If endpoint incompatible remainsheld. Exact author referencecycle unknown.'))
 out=[];qc=[]
 for s in spec:
  image=Image.open(OUT/s['file']).convert('RGB');a=np.array(image).astype(float);r,g,b=(a[:,:,i]for i in range(3));lo,hi=s['roi'];raw=[]
  if s['mode']=='dense':
   if s['color']=='red':mask=(r-g>35)&(r-b>25)&(g>60)&(r>160)&(b<210)
   elif s['color']=='blue':mask=(b-r>30)&(b-g>5)&(g-r>20)
   else:mask=(r-g>10)&(b-g>15)&(r<230)&(g>85)
   mask[:lo]=False;mask[hi:]=False
   for x in sorted(set(list(range(73,638,5))+[max(x for x in range(66,641)if mask[:,x].any())])):
    y=np.flatnonzero(mask[:,x])
    if len(y):raw.append((float(x),float(np.median(y)),dict(pixel_count=len(y),column_y=[int(v)for v in y])))
  elif s['mode']in['absolute_C','solid_circles']:
   mask=a.max(2)<110;mask[:lo]=False;mask[hi:]=False
   xmin,xmax=(140,951)if s['mode']=='absolute_C'else(s['cal']['x0']+7,s['cal']['xN']+8);mask[:,:int(xmin)]=False;mask[:,int(xmax):]=False;raw=solid_markers(mask)
   if s.get('first_visible_partial_marker'):
    x,y=s['first_visible_partial_marker'];raw=[(x,y,dict(partially_axis_occluded=True,source='visible actual firstmarker,not an invented baseline cycle index'))]+[v for v in raw if v[0]>x+12]
  else:
   mask=(r>100)&(r-g>50)&(b-g>35);mask[:lo]=False;mask[hi:]=False;mask[:,:95]=False;mask[:,508:]=False;mass=mask.sum(0);cand=[x for x in range(97,506)if mass[x]>=5 and mass[x]==max(mass[x-2:x+3])];selected=[]
   for x in sorted(cand,key=lambda x:(-mass[x],x)):
    if all(abs(x-j)>=8 for j in selected):selected.append(x)
   for x in sorted(selected):
    yy=np.flatnonzero(mask[:,x]);raw.append((float(x),float((yy.min()+yy.max())/2),dict(pixel_count=len(yy),column_y=[int(v)for v in yy])))
  cal=s['cal'];dy=cal['y0']-cal['y100'];dx=cal['xN']-cal['x0'];bound=300/dy;points=[]
  for x,y,extra in raw:
   n=(x-cal['x0'])*cal['N']/dx;value=(cal['y0']-y)*100/dy
   points.append(dict(marker_index=len(points),x_px=x,y_px=y,cycle_coordinate=n,cycle_lower=max(0,n-3*cal['N']/dx),cycle_upper=n+3*cal['N']/dx,retention_pct=value,reading_interval_pp=[value-bound,value+bound],reading_bound_pp=bound,sampling_mode=s['mode'],source_pixels=extra))
  ref=None
  if s['mode']=='absolute_C'and points:
   C0=points[0]['retention_pct'];ref=dict(value_F_g=C0,reading_bound_F_g=bound,marker_index=0,source='own first plotted C(N); exact author normalization indexunknown')
   for p in points:
    C=p['retention_pct'];rr=100*C/C0;low=100*(C-bound)/(C0+bound);high=100*(C+bound)/(C0-bound)
    p.update(raw_capacitance_F_g=C,raw_capacitance_reading_bound_F_g=bound,retention_pct=rr,reading_interval_pp=[low,high],reading_bound_pp=max(rr-low,high-rr))
   points[0].update(retention_pct=100.,reading_interval_pp=[100.,100.],reading_bound_pp=0.,derived_reference_not_exact_raw_measurement=True)
  assert points and points[-1]['cycle_coordinate']>=.97*cal['N'],s['label']
  row=baseline[s['eid']];parent=next(r for r in receipts if Path(r['output']).stem==s['source_label']+'_original');last=points[-1];consistent=last['reading_interval_pp'][0]-.1<=row['target']<=last['reading_interval_pp'][1]+.1
  windows=[dict(fraction=f,point_count=len([p for p in points if p['cycle_upper']<=f*cal['N']]),marker_indices=[p['marker_index']for p in points if p['cycle_upper']<=f*cal['N']])for f in[.1,.2]]
  q=dict(curve_id='local_curve_v3e:'+s['eid'],endpoint_id=s['eid'],source_family=row['source_family'],sample_name=row['sample_name'],system='2E',target_cycle_count=row['features']['cycle_count'],author_retention_pct=row['target'],features={k:row['features'].get(k)for k in['cycle_count','reported_current_A_g','electrolyte','concentration_mol_L','cycle_voltage_lower_V','cycle_voltage_upper_V','BET_m2_g']},conditions=row['conditions'],figure_path=(OUT/s['file']).relative_to(ROOT).as_posix(),figure_sha256=sha(OUT/s['file']),original_pdf_path=parent['source_path'],original_pdf_sha256=parent['source_sha256'],panel_provenance=dict(pdf_page=parent['pdf_page'],figure=s['figure'],original_image_path=parent['output'],crop_rect=s['crop']),calibration=dict(**cal,pixel_bound=3),points=points,first_plotted_reference=ref,window_availability=windows,endpoint_consistent_with_graph_bound=consistent,training_eligible_pending_visual_review=False,genuinely_new_external_source=False,new_formal_cycle_admission=False,old_endpoint_label_changed=False)
  out.append(q);overlay=image.copy();draw=ImageDraw.Draw(overlay)
  for p in points:draw.rectangle((p['x_px']-1,p['y_px']-1,p['x_px']+1,p['y_px']+1),outline='orange')
  for f,color in[(.1,'green'),(.2,'purple')]:x=cal['x0']+f*dx;draw.line((x,lo,x,hi),fill=color,width=1)
  overlay.save(OUT/(s['label']+'_overlay_v2.png'));qc.append(dict(endpoint_id=s['eid'],points=len(points),last_retention=last['retention_pct'],last_interval=last['reading_interval_pp'],author=row['target'],consistent=consistent,windows=windows));print(s['label'],len(points),'last',round(last['retention_pct'],4),'bound',last['reading_interval_pp'],'author',row['target'],'ok',consistent,'early',[w['point_count']for w in windows])
 write(OUT/'extracted_curve_candidates_v2.json',out);write(OUT/'extraction_qc_v2.json',qc)
if __name__=='__main__':main()
