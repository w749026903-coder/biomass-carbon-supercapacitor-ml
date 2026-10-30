"""Read geometric centres of glossy black markers; exclude blue efficiency and frame."""
from pathlib import Path
import hashlib,json
import numpy as np
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'保持率达标研究_v3_主线与近优组合_20261030/第十一轮_双电极原文曲线补充'
def read(p):return json.loads(Path(p).read_text('utf8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,x):Path(p).write_bytes((json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode('utf8'))
def main():
 assert not(OUT/'hpcs_curve_candidate.json').exists(),'Do not overwrite evidence'
 image=Image.open(OUT/'HPCS_Fig6g_panel.png').convert('RGB');a=np.array(image).astype(float);gray=(a.max(2)-a.min(2)<8)&(a.mean(2)>110)&(a.mean(2)<220);gray[:55]=False;gray[245:]=False;gray[:,:200]=False;gray[:,1888:]=False;dark=(a.max(2)-a.min(2)<8)&(a.max(2)<100);seen=np.zeros(gray.shape,dtype=bool);loc=[]
 for y,x in zip(*np.where(gray)):
  if seen[y,x]:continue
  stack=[(y,x)];seen[y,x]=True;pixels=[]
  while stack:
   yy,xx=stack.pop();pixels.append((yy,xx))
   for dy,dx in[(1,0),(-1,0),(0,1),(0,-1)]:
    ny,nx=yy+dy,xx+dx
    if 0<=ny<gray.shape[0]and 0<=nx<gray.shape[1]and gray[ny,nx]and not seen[ny,nx]:seen[ny,nx]=True;stack.append((ny,nx))
  if len(pixels)<12:continue
  yy,xx=np.array(pixels).T;w=xx.max()-xx.min()+1;h=yy.max()-yy.min()+1
  if 4<=w<=15 and 4<=h<=15 and .6<=w/h<=1.6:loc.append(dict(x=float(xx.mean()),y=float(yy.mean()),pixels=len(pixels)))
 loc.sort(key=lambda p:p['x']);points=[];held=[];cal=dict(x0=182.,x5000=1894.,y0=572.5,y100=79.5,pixel_bound=3,excluded_frame_x_min=1887)
 write(OUT/'hpcs_extraction_plan.json',dict(figure='Fig6g',pdf_page=8,calibration=cal,segmentation='Grey highlight components locate actual glossy black glyphs; highlight is not the geometric marker centre. Lower-arc circle fit from actual dark pixels, using x=round(gx)-8..round(gx)+12; remove frame x>=1887. No blue efficiency, joining-line densification or fabricated early markers.',marker_qc='>=12 lower contour columns,circle radius10..18px,max radial residual<=1.5px. Bounds remain3px. Reject unresolved glyphs, preserve QC log. Early window>=3 actual markers unchanged.',target='Original author73% after5000,source initial baseline cycle indexunknown. Do not scale figure to73.',contrast='White/grey highlights are offset upward and cannot be used as retention coordinates. Blue curve is coulombic efficiency.'))
 for spot in loc:
  gx,gy=round(spot['x']),round(spot['y']);arc=[]
  for x in range(gx-8,min(gx+13,1887)):
   yy=np.flatnonzero(dark[gy-5:gy+28,x])+gy-5
   if len(yy):arc.append((x,int(yy.max())))
  if len(arc)<12:held.append(dict(locator=spot,reason='insufficient_lower_contour'));continue
  x,y=np.array(arc,dtype=float).T;xx=x-gx;yy=y-gy;coef=np.linalg.lstsq(np.column_stack([2*xx,2*yy,np.ones(len(x))]),xx*xx+yy*yy,rcond=None)[0];cx,cy=coef[:2];radius=float(np.sqrt(coef[2]+cx*cx+cy*cy));res=float(max(abs(np.sqrt((xx-cx)**2+(yy-cy)**2)-radius)));px=float(gx+cx);py=float(gy+cy)
  if not(10<=radius<=18 and res<=1.5):held.append(dict(locator=spot,radius=radius,max_radial_residual=res,reason='geometric_glyph_fit_not_resolved'));continue
  n=(px-cal['x0'])*5000/(cal['x5000']-cal['x0']);value=100*(cal['y0']-py)/(cal['y0']-cal['y100']);bound=300/(cal['y0']-cal['y100']);dx=3*5000/(cal['x5000']-cal['x0']);points.append(dict(marker_index=len(points),x_px=px,y_px=py,cycle_coordinate=n,cycle_lower=max(0,n-dx),cycle_upper=n+dx,retention_pct=value,reading_interval_pp=[value-bound,value+bound],reading_bound_pp=bound,highlight_locator=spot,glyph_radius_px=radius,glyph_max_radial_residual_px=res,lower_contour_pixels=arc,sampling_mode='actual_glossy_black_marker_geometric_lower_arc_circle_centre'))
 assert len(points)>=40 and points[-1]['cycle_coordinate']>=.97*5000
 baseline=next(r for r in read(ROOT/'保持率双路线预研_v2_20261029/baseline_inputs.json')['2E']if r['row_id']=='legacy:R091_CY01');receipt=read(OUT/'HPCS_figure_receipt.json');windows=[]
 for fraction in[.1,.2]:
  ps=[p for p in points if p['cycle_upper']<=fraction*5000];windows.append(dict(fraction=fraction,early_markers=len(ps),eligible_by_point_count=len(ps)>=3,marker_indices=[p['marker_index']for p in ps]))
 q=dict(curve_id='local_curve_v3d:legacy:R091_CY01',endpoint_id=baseline['row_id'],sample_name=baseline['sample_name'],source_family=baseline['source_family'],system='2E',target_cycle_count=5000,author_retention_pct=baseline['target'],features={k:baseline['features'][k]for k in['cycle_count','reported_current_A_g','electrolyte','concentration_mol_L','cycle_voltage_lower_V','cycle_voltage_upper_V','BET_m2_g']},conditions=baseline['conditions'],figure_path=(OUT/'HPCS_Fig6g_panel.png').relative_to(ROOT).as_posix(),figure_sha256=sha(OUT/'HPCS_Fig6g_panel.png'),original_pdf_path=receipt['source_path'],original_pdf_sha256=receipt['source_sha256'],panel_provenance=dict(pdf_page=8,figure='Fig6g',embedded_image='HPCS_PDFp8_Im0.png',crop_rect=[0,1170,2032,1857]),calibration=cal,points=points,first_plotted_reference=None,window_availability=windows,endpoint_consistent_with_graph_bound=points[-1]['reading_interval_pp'][0]-.1<=73<=points[-1]['reading_interval_pp'][1]+.1,training_eligible_pending_visual_review=False,genuinely_new_external_source=False,new_formal_cycle_admission=False,old_endpoint_label_changed=False)
 write(OUT/'hpcs_curve_candidate.json',q);write(OUT/'hpcs_marker_qc.json',dict(locators=len(loc),accepted_markers=len(points),held=held,highlight_not_geometric_centre=True));overlay=image.copy();draw=ImageDraw.Draw(overlay)
 for p in points:draw.rectangle((p['x_px']-2,p['y_px']-2,p['x_px']+2,p['y_px']+2),outline='orange')
 for fraction,color in[(.1,'green'),(.2,'purple')]:x=cal['x0']+fraction*(cal['x5000']-cal['x0']);draw.line((x,45,x,250),fill=color,width=2)
 overlay.save(OUT/'hpcs_curve_overlay.png');print('Markers',len(points),'held',len(held),'windows',windows,'last',points[-1]['retention_pct'],'consistent',q['endpoint_consistent_with_graph_bound'])
if __name__=='__main__':main()
