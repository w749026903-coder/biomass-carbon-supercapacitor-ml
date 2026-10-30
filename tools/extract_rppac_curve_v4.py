"""Local originalPDF hollow-diamond curve; no sparse-line densification."""
from pathlib import Path
import hashlib,json,sys
import numpy as np
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'保持率达标研究_v3_主线与近优组合_20261030/第八轮_原文补证与双电极曲线'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 assert not(OUT/'rppac_curve_candidate.json').exists(),'Do not overwrite extracted evidence'
 image=Image.open(OUT/'RPPAC_Fig8c_panel.png').convert('RGB');a=np.array(image);r,g,b=(a[:,:,i].astype(float)for i in range(3));mask=(b>110)&(b>1.5*r)&(b>1.2*g);mask[:52]=False;mask[210:]=False;mask[:,:250]=False;mask[:,1560:]=False
 top=np.full(image.width,np.nan)
 for x in range(250,1558):
  yy=np.flatnonzero(mask[:,x])
  if len(yy):top[x]=yy.min()
 candidates=[]
 for x in range(252,1556):
  if not np.isfinite(top[x-1:x+2]).all():continue
  if top[x]>top[x-1]or top[x]>top[x+1]:continue
  lo=max(250,x-12);hi=min(1558,x+13)
  if min(np.nanmax(top[lo:x+1]),np.nanmax(top[x:hi]))-top[x]<2:continue
  candidates.append(x)
 selected=[]
 for x in sorted(candidates,key=lambda x:(top[x],x)):
  if all(abs(x-z)>=15 for z in selected):selected.append(x)
 selected.sort();points=[];x0=247.;xN=1549.;y0=900.5;y100=79.5;N=6000;dx=(xN-x0)/N;bound=3/(y0-y100)*100
 for x in selected:
  yy,xx=np.where(mask[:,x-1:x+2]);px=float(x);py=float((yy.min()+yy.max())/2);n=(px-x0)/dx;v=(y0-py)/(y0-y100)*100
  points.append(dict(marker_index=len(points),x_px=px,y_px=py,cycle_coordinate=n,cycle_lower=max(0,n-3/dx),cycle_upper=n+3/dx,retention_pct=v,reading_interval_pp=[v-bound,v+bound],reading_bound_pp=bound,pixel_count=len(xx),sampling_mode='actual_hollow_diamond_centre_top_vertex_and_vertical_extrema'))
 assert len(points)>=40 and points[-1]['cycle_coordinate']>=.97*N
 last=points[-1];consistent=last['reading_interval_pp'][0]-.1<=88<=last['reading_interval_pp'][1]+.1;windows=[]
 for f in[.1,.2]:
  ps=[p for p in points if p['cycle_upper']<=f*N];windows.append(dict(fraction=f,early_markers=len(ps),eligible_by_point_count=len(ps)>=3,marker_indices=[p['marker_index']for p in ps],maximum_early_retention_reading_bound_pp=max([p['reading_bound_pp']for p in ps],default=None)))
 q=dict(curve_id='local_curve_v3c:candidate:V05:002',endpoint_id='candidate:V05:002',sample_name='RPPAC-0.25-850',source_family='doi:10.1002/est2.70547',system='2E',target_cycle_count=N,author_retention_pct=88,author_label_relation='approximately_author_rounded',features=dict(cycle_count=N,reported_current_A_g=10,electrolyte='H2SO4',concentration_mol_L=1,cycle_voltage_lower_V=0,cycle_voltage_upper_V=1,BET_m2_g=553),conditions=dict(configuration='symmetric_two_electrode',protocol_source='PDFp4section2.4; CV0..1V andGCD same window; stabilityGCD6000at10A/g',target_source='PDFp13 andFig8c; initial author reference, exactcycleindex unknown',reported_current_mass_basis='unknown_not_inferred_from_2I_capacitance_formula',baseline_cycle_index=None,not_retention_targets={'energy_density_pct':49,'power_density_pct':141}),figure_path=(OUT/'RPPAC_Fig8c_panel.png').relative_to(ROOT).as_posix(),figure_sha256=sha(OUT/'RPPAC_Fig8c_panel.png'),original_pdf_path='用户补充文献核验_20261018/pdfs/missing_main_received/U019.pdf',original_pdf_sha256=sha(ROOT/'用户补充文献核验_20261018/pdfs/missing_main_received/U019.pdf'),panel_provenance=dict(figure='Fig8c',pdf_page=12,embedded_image='RPPAC_PDFp12_Im0.png',crop_rect=[220,850,1840,1830]),calibration=dict(x0=x0,x6000=xN,y0=y0,y100=y100,pixel_bound=3,colour='blue',method='Actual hollow diamonds via top-vertex local minima, centreY from vertical extrema. Not added connecting-line samples.'),first_plotted_reference=None,points=points,window_availability=windows,endpoint_consistent_with_graph_bound=consistent,training_eligible_pending_visual_review=False,genuinely_new_external_source=False,new_formal_cycle_admission=False,old_endpoint_label_changed=False)
 (OUT/'rppac_curve_candidate.json').write_bytes((json.dumps(q,ensure_ascii=False,indent=2)+'\n').encode('utf8'));overlay=image.copy();d=ImageDraw.Draw(overlay)
 for p in points:d.rectangle((p['x_px']-2,p['y_px']-2,p['x_px']+2,p['y_px']+2),outline='cyan')
 for f,c in[(.1,'green'),(.2,'purple')]:x=x0+f*(xN-x0);d.line((x,45,x,200),fill=c,width=2)
 overlay.save(OUT/'rppac_curve_overlay.png');print('Actual markers',len(points),'last',last,'windows',windows,'endpoint_consistent',consistent)
if __name__=='__main__':main()
