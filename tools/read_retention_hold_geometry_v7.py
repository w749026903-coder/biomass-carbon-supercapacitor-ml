"""Independent image geometry of held curves; no model scores used."""
from pathlib import Path
import json,hashlib
import numpy as np
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'保持率达标研究_v3_主线与近优组合_20261030';P11=BASE/'第十一轮_双电极原文曲线补充';OUT=P11/'batch4_20261031'
def read(p):return json.loads(Path(p).read_text('utf8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n','utf8')
def fit_circle(arc):
    x,y=np.array(arc,float).T;gx=x.mean();gy=y.mean();xx=x-gx;yy=y-gy
    co=np.linalg.lstsq(np.column_stack([2*xx,2*yy,np.ones(len(x))]),xx*xx+yy*yy,rcond=None)[0]
    cx,cy=co[:2];rr=float(np.sqrt(max(0,co[2]+cx*cx+cy*cy)));res=float(max(abs(np.hypot(xx-cx,yy-cy)-rr)))
    return float(cx+gx),float(cy+gy),rr,res

def main():
    assert not(OUT/'MMC_candidate.json').exists(),'Preserve extraction attempts'
    image=Image.open(OUT/'MMC_cycle_panel.png').convert('RGB');a=np.array(image).astype(float);r,g,b=[a[:,:,j]for j in range(3)];red=(r>150)&(r-g>65)&(r-b>50)
    # First red disk is fully visible. Use its upper/left contour, excluding the
    # second disk and connecting tail, rather than choosing a higher rate C0.
    arc=[]
    for y in range(196,214):
        for x in range(156,174):
            if not red[y,x] or not(x<=164 or y<=203):continue
            if any(not red[y+dy,x+dx]for dy,dx in[(1,0),(-1,0),(0,1),(0,-1)]):arc.append((x,y))
    cx,cy,rad,res=fit_circle(arc);assert 4<=rad<=9 and res<=1.5
    cal=dict(x0=158.5,xN=720.5,y0=468.,y60=38.,N=30000,pixel_bound=3)
    scale=60/(cal['y0']-cal['y60']);C0=(cal['y0']-cy)*scale;bound=3*scale
    positions=[(cx,cy,dict(reference_glyph_contour=arc,glyph_radius_px=rad,max_radial_residual_px=res))]
    for x in list(range(176,719,4))+[719]:
        yy=np.flatnonzero(red[205:255,x])+205
        if len(yy):positions.append((float(x),float((yy.min()+yy.max())/2),dict(column_y=yy.tolist())))
    points=[]
    for x,y,ev in positions:
        c=(cal['y0']-y)*scale;value=100*c/C0;lo=100*(c-bound)/(C0+bound);hi=100*(c+bound)/(C0-bound);n=(x-cal['x0'])*30000/(cal['xN']-cal['x0'])
        points.append(dict(marker_index=len(points),x_px=x,y_px=y,cycle_coordinate=n,cycle_lower=max(0,n-3*30000/(cal['xN']-cal['x0'])),cycle_upper=n+3*30000/(cal['xN']-cal['x0']),raw_capacitance_F_g=c,raw_capacitance_reading_bound_F_g=bound,retention_pct=value,reading_interval_pp=[lo,hi],reading_bound_pp=max(value-lo,hi-value),sampling_mode='first_own_glyph_then_dense_original_red_glyph_trace',source_pixels=ev))
    points[0].update(retention_pct=100.,reading_interval_pp=[100.,100.],reading_bound_pp=0.,derived_reference_not_exact_raw_measurement=True)
    row=next(r for r in read(ROOT/'保持率双路线预研_v2_20261029/baseline_inputs.json')['2E']if r['row_id']=='incoming:ADD_066_T01');receipt=read(P11/'MMC_figure_receipt.json');last=points[-1]
    windows=[dict(fraction=f,point_count=sum(p['cycle_upper']<=f*30000 for p in points),marker_indices=[p['marker_index']for p in points if p['cycle_upper']<=f*30000])for f in[.1,.2]]
    q=dict(curve_id='local_curve_v3g:'+row['row_id'],endpoint_id=row['row_id'],source_family=row['source_family'],sample_name=row['sample_name'],system='2E',target_cycle_count=30000,author_retention_pct=row['target'],features={k:row['features'].get(k)for k in['cycle_count','reported_current_A_g','electrolyte','concentration_mol_L','cycle_voltage_lower_V','cycle_voltage_upper_V','BET_m2_g']},conditions=row['conditions'],figure_path=(OUT/'MMC_cycle_panel.png').relative_to(ROOT).as_posix(),figure_sha256=sha(OUT/'MMC_cycle_panel.png'),original_pdf_path=receipt['source_path'],original_pdf_sha256=receipt['source_sha256'],panel_provenance=dict(pdf_page=9,figure='Fig8c absoluteC(N), redMMC, not blackcontrolC',original_image_path=receipt['output'],crop_rect=[0,560,760,1116]),calibration=cal,points=points,first_plotted_reference=dict(value_F_g=C0,reading_bound_F_g=bound,marker_index=0,reference_cycle_coordinate=points[0]['cycle_coordinate'],reference_cycle_index_unknown=True,source='Own first actual plotted cyclingC(N) glyph, not rate capacitance; ratio bound carries shared-reference uncertainty.'),window_availability=windows,endpoint_consistent_with_graph_bound=last['reading_interval_pp'][0]-.1<=row['target']<=last['reading_interval_pp'][1]+.1,training_eligible_pending_visual_review=False,genuinely_new_external_source=False,new_formal_cycle_admission=False,old_endpoint_label_changed=False)
    write(OUT/'MMC_candidate.json',q);write(OUT/'MMC_reading_qc.json',dict(reference_glyph=dict(centre=[cx,cy],radius=rad,residual=res,contour_pixels=arc),C0_F_g=C0,reading_bound_F_g=bound,positions=len(points),last_retention=last['retention_pct'],last_interval=last['reading_interval_pp'],author=row['target'],author_one_decimal_rounding_interval=[row['target']-.05,row['target']+.05],consistent_under_frozen_tolerance=q['endpoint_consistent_with_graph_bound'],windows=windows))
    overlay=image.copy();draw=ImageDraw.Draw(overlay)
    for p in points:draw.rectangle((p['x_px']-1,p['y_px']-1,p['x_px']+1,p['y_px']+1),outline='orange')
    overlay.save(OUT/'MMC_overlay.png');print('MMC',len(points),'reference',C0,'last',last['retention_pct'],'box',last['reading_interval_pp'],'consistent',q['endpoint_consistent_with_graph_bound'],'early',[w['point_count']for w in windows])
    # A separate geometry-only experiment on occluded blue spheres. Candidate
    # circle lower arcs must be concave and well resolved before interpreting y.
    src=P11/'batch3_20261031/OPBNP_cycle_panel.png';im=Image.open(src).convert('RGB');a=np.array(im).astype(float);r,g,b=[a[:,:,j]for j in range(3)];mask=(b-r>45)&(b-g>35)&(b>100)
    profile={x:int(np.flatnonzero(mask[65:120,x])[-1]+65)for x in range(120,1025)if mask[65:120,x].any()};peaks=[]
    for x,y in profile.items():
        neighborhood=[profile[v]for v in range(max(120,x-4),min(1025,x+5))if v in profile]
        if y==max(neighborhood):peaks.append(x)
    chosen=[]
    for x in sorted(peaks,key=lambda x:(-profile[x],x)):
        if all(abs(x-z)>=7 for z in chosen):chosen.append(x)
    accepted=[];held=[]
    for x in sorted(chosen):
        arc=[(j,profile[j])for j in range(x-5,x+6)if j in profile]
        if len(arc)<8:continue
        cx,cy,rad,res=fit_circle(arc)
        if 5<=rad<=12 and res<=1.0 and abs(cx-x)<=3 and profile[x]-cy>=.6*rad:
            accepted.append(dict(x=cx,y=cy,radius=rad,residual=res,arc=arc))
        else:held.append(dict(seed=x,centre=[cx,cy],radius=rad,residual=res))
    write(OUT/'OPBNP_lower_envelope_geometry_attempt.json',dict(status='candidate_only_not_training',source=src.relative_to(ROOT).as_posix(),source_sha256=sha(src),criteria='Actual blue lower boundary, peak separation7px, >=8 actual boundarycolumns; radius5..12/maxresidual1px; no endpoint-value fitting; all tentative until image review.',accepted_geometry=accepted,held=held,author_target_used_for_circle_selection=False))
    overlay=im.copy();draw=ImageDraw.Draw(overlay)
    for p in accepted:draw.ellipse((p['x']-p['radius'],p['y']-p['radius'],p['x']+p['radius'],p['y']+p['radius']),outline='orange',width=1)
    overlay.save(OUT/'OPBNP_lower_envelope_overlay.png');print('OPBNP geometry',len(accepted),'held',len(held),';first/last',accepted[:2],accepted[-2:])
if __name__=='__main__':main()
