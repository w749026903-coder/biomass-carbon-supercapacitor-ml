"""Local original-figure review, fixed axis calibration and bounded pixel readings.

This one-shot extraction does not fit models or change author endpoint labels.
Sparse joining lines are never densified. Dense original glyph traces are sampled
at actual coloured pixels and remain one correlated curve, not new experiments.
"""
from pathlib import Path
import hashlib, json
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '保持率达标研究_v3_主线与近优组合_20261030/第十一轮_双电极原文曲线补充/batch3_20261031'

def read(p): return json.loads(Path(p).read_text('utf8'))
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p, x): Path(p).write_text(json.dumps(x, ensure_ascii=False, indent=2, allow_nan=False)+'\n', 'utf8')

def components(mask):
    seen = np.zeros(mask.shape, bool); result = []
    for y, x in zip(*np.where(mask)):
        if seen[y,x]: continue
        stack=[(y,x)]; seen[y,x]=True; pixels=[]
        while stack:
            yy,xx=stack.pop();pixels.append((yy,xx))
            for dy,dx in [(1,0),(-1,0),(0,1),(0,-1)]:
                ny,nx=yy+dy,xx+dx
                if 0<=ny<mask.shape[0] and 0<=nx<mask.shape[1] and mask[ny,nx] and not seen[ny,nx]:
                    seen[ny,nx]=True; stack.append((ny,nx))
        if len(pixels)>=4: result.append(np.array(pixels))
    return result

def circle(arc, gx, gy):
    x,y=np.array(arc,float).T; xx=x-gx;yy=y-gy
    co=np.linalg.lstsq(np.column_stack([2*xx,2*yy,np.ones(len(x))]),xx*xx+yy*yy,rcond=None)[0]
    cx,cy=co[:2]; rad=float(np.sqrt(max(0,co[2]+cx*cx+cy*cy)))
    residual=float(max(abs(np.sqrt((xx-cx)**2+(yy-cy)**2)-rad)))
    return float(gx+cx),float(gy+cy),rad,residual

def points_from_pixels(s, image):
    a=np.array(image).astype(float);r,g,b=[a[:,:,j] for j in range(3)]
    color=s['color']
    masks={
        'red':(r>150)&(r-g>30)&(r-b>20),
        'green':(g-r>20)&(g-b>10)&(g>65)&(g<205),
        'navy':(b-r>12)&(b-g>2)&(b<220)&(r<180),
        'blue':(b-r>30)&(b-g>20)&(b>100),
        'cyan':(b-r>45)&(g-r>25)&(b>100),
        'teal':(g-r>30)&(g-b>5)&(g<200),
        'olive':(g-r>8)&(r-b>15)&(g<155)&(r<150),
        'magenta':(r-g>50)&(b-g>35)&(r>100),
        'black':a.max(2)<95,
    }
    mask=masks[color].copy();xl,xh,yl,yh=s['roi']
    mask[:yl]=False;mask[yh:]=False;mask[:,:xl]=False;mask[:,xh:]=False
    raw=[];held=[]
    if s['mode']=='dense_original_glyph_trace':
        # Column coordinates reference actual dense printed glyphs. Never used on
        # the sparse SSC series or on a connecting line between isolated markers.
        for x in sorted(set(list(range(xl,xh,s.get('step',8)))+[xh-1])):
            yy=np.flatnonzero(mask[:,x])
            if len(yy): raw.append((float(x),float((yy.min()+yy.max())/2),dict(column_y=yy.tolist())))
    elif s['mode']=='solid_markers':
        eroded=mask.copy()
        for dy in [-1,0,1]:
            for dx in [-1,0,1]:eroded &= np.roll(np.roll(mask,dy,0),dx,1)
        for pixels in components(eroded):
            yy,xx=pixels.T;w=int(xx.max()-xx.min()+1);h=int(yy.max()-yy.min()+1)
            if 3<=w<=22 and 3<=h<=22:
                raw.append((float((xx.min()+xx.max())/2),float((yy.min()+yy.max())/2),dict(eroded_bbox=[int(xx.min()),int(yy.min()),int(xx.max()),int(yy.max())],pixel_count=len(pixels))))
        for x,y in s.get('visible_partial_markers',[]):
            raw.append((x,y,dict(partial_glyph_on_axis=True,reason='Actual visible clipped glyph; no synthetic cycle-zero observation or baseline index asserted.')))
    elif s['mode']=='glossy_green_geometric_centres':
        highlight=(g-r>0)&(g-r<25)&(g-b>0)&(g-b<25)&(r>155)&(r<245)
        highlight[:yl]=False;highlight[yh:]=False;highlight[:,:xl]=False;highlight[:,xh:]=False
        loc=[]
        for pixels in components(highlight):
            yy,xx=pixels.T;w=xx.max()-xx.min()+1;h=yy.max()-yy.min()+1
            if 3<=w<=12 and 3<=h<=12 and len(pixels)>=7:
                loc.append((int(round(xx.mean())),int(round(yy.mean()))))
        for gx,gy in sorted(loc):
            arc=[]
            for x in range(max(xl,gx-6),min(xh,gx+13)):
                yy=np.flatnonzero(mask[max(yl,gy-2):min(yh,gy+28),x])+max(yl,gy-2)
                if len(yy):arc.append((x,int(yy.max())))
            if len(arc)<10:held.append(dict(locator=[gx,gy],reason='insufficient_arc'));continue
            px,py,rad,res=circle(arc,gx,gy)
            if 8<=rad<=17 and res<=1.5:
                raw.append((px,py,dict(highlight_locator=[gx,gy],lower_contour_pixels=arc,glyph_radius_px=rad,glyph_max_radial_residual_px=res)))
            else:held.append(dict(locator=[gx,gy],radius=rad,residual=res,reason='unresolved_geometric_centre'))
    else:
        mass=mask.sum(0);candidate=[]
        for x in range(xl+2,xh-2):
            yy=np.flatnonzero(mask[:,x])
            if len(yy)>=s.get('min_mass',4) and yy.max()-yy.min()<=s.get('max_glyph_height',18) and mass[x]==max(mass[x-2:x+3]):candidate.append(x)
        chosen=[]
        for x in sorted(candidate,key=lambda x:(-mass[x],x)):
            if all(abs(x-v)>=s['min_sep'] for v in chosen):chosen.append(x)
        for x in sorted(chosen):
            yy=np.flatnonzero(mask[:,x])
            raw.append((float(x),float((yy.min()+yy.max())/2),dict(column_y=yy.tolist(),pixel_count=len(yy))))
    raw.sort()
    return raw,held

def specifications():
    # Axis ticks, not author endpoints, define all transformations. SSC's y axis
    # starts at 85%, so y0 is an extrapolated coordinate from the 85/100 ticks.
    return [
      dict(label='MF',eid='incoming:ADD_026_T01',idx=7,parent='MF_LYS_original.jpg',crop=[0,550,700,1134],figure='main Fig7d',mode='ring_glyph_centres',color='red',roi=[103,700,57,133],min_sep=9,cal=[101.5,698,507.5,106.5,5000]),
      dict(label='LYS',eid='incoming:ADD_026_T02',idx=7,parent='LYS_SI_FigS7_original.jpeg',crop=[640,490,1269,1005],figure='publisher SI FigS7d',mode='ring_glyph_centres',color='green',roi=[93,601,42,118],min_sep=8,cal=[91.5,598.5,422,82,5000]),
      dict(label='NWJPC',eid='v20:WJ2026_NWJPC2_SSC_C10000',idx=8,parent='Weigela_gr7.webp',crop=[0,880,1600,1346],figure='main Fig7G; symmetric carbon SC, not Fig9 zinc hybrid',mode='dense_original_glyph_trace',color='olive',roi=[116,1507,91,108],step=10,cal=[115.5,1506.5,435,98.66666666666669,10000]),
      dict(label='OPC',eid='legacy:SRC035_CY01',idx=9,parent='OPC_original.jpg',crop=[0,1270,1120,1988],figure='main Fig8g',mode='dense_original_glyph_trace',color='navy',roi=[205,1060,52,80],step=8,cal=[199.5,1059,590,62.5,10000]),
      dict(label='PC_NaCl_1A',eid='incoming:ADD_019_T01',idx=10,parent='PC_NaCl_original.jpg',crop=[780,580,2129,1160],figure='main Fig7f blue circles, 1A/g',mode='dense_original_glyph_trace',color='blue',roi=[184,1266,88,225],step=9,cal=[182.5,1264.5,488.5,213.5,10000]),
      dict(label='PC_NaCl_3A',eid='incoming:ADD_019_T02',idx=10,parent='PC_NaCl_original.jpg',crop=[780,580,2129,1160],figure='main Fig7f red stars, 3A/g; caption/result supplements methods-only 1A/g statement',mode='ring_glyph_centres',color='red',roi=[184,1266,156,221],min_sep=9,cal=[182.5,1264.5,488.5,213.5,10000]),
      dict(label='NDB',eid='incoming:ADD_010_T01',idx=11,parent='NDB_original.jpg',crop=[0,460,1900,920],figure='main Fig5d left green capacitance retention; not orange CE',mode='dense_original_glyph_trace',color='teal',roi=[107,1834,264,290],step=12,cal=[104,1831.5,394,275.3333333333333,10000]),
      dict(label='DUGPC',eid='legacy:R107_CY01',idx=12,parent='DUGPC_Fig6_original.jpg',crop=[0,450,650,931],figure='main Fig6d left retention scale, not right F/g scale',mode='ring_glyph_centres',color='cyan',roi=[100,567,27,95],min_sep=5,min_mass=4,max_glyph_height=14,cal=[103.5,562,380,69,10000]),
      dict(label='SSC',eid='legacy:R104_CY01',idx=13,parent='SSC_original.jp2',crop=[0,0,1020,810],figure='main Fig10a, 85..105% truncated axis, author endpoint98.4+-0.3%',mode='solid_markers',color='black',roi=[118,842,164,248],visible_partial_markers=[[107,176]],cal=[107,830,3442.666666666667,176,20000]),
      dict(label='AUACW',eid='incoming:ADD_003_T02',idx=14,parent='AUACW_original.jpg',crop=[530,825,1765,1284],figure='main Fig6h left green retention, not orange CE; glossy geometric centres',mode='glossy_green_geometric_centres',color='green',roi=[240,1118,135,220],cal=[232,1123,380,153.66666666666669,10000]),
      dict(label='OPBNP',eid='incoming:ADD_006_T01',idx=15,parent='OPBNP_original.jpg',crop=[0,1000,1139,1528],figure='main Fig4e blue retention, red CE; separate from 3E Fig3f and sodium battery Fig5',mode='dense_original_glyph_trace',color='blue',roi=[120,1026,70,120],step=8,cal=[110.5,1028.5,425,94.58333333333331,10000]),
      dict(label='PPC',eid='candidate:V05:015',idx=16,parent='PPC_original.jpg',crop=[570,900,1116,1377],figure='main Fig7f',mode='ring_glyph_centres',color='magenta',roi=[100,520,103,127],min_sep=8,min_mass=3,cal=[94,516,399,114.5,20000]),
      dict(label='PR2',eid='legacy:R093_CY01',idx=17,parent='PR2_original.jpg',crop=[0,0,2180,1500],figure='main Fig8e, actual black square glyphs',mode='solid_markers',color='black',roi=[386,2057,215,340],cal=[380,2057,1361,328.5,10000]),
      dict(label='LAC',eid='legacy:R103_CY01',idx=18,parent='LAC_page.png',crop=[300,1580,1200,2310],figure='main Fig7c; whole page render preserves strip image placement',mode='ring_glyph_centres',color='red',roi=[200,818,87,124],min_sep=9,min_mass=4,cal=[204.5,810.5,616.5,92.5,10000]),
    ]

def main():
    assert not (OUT/'extracted_curve_candidates.json').exists(), 'Preserve evidence attempts'
    baseline={r['row_id']:r for r in read(ROOT/'保持率双路线预研_v2_20261029/baseline_inputs.json')['2E']}
    rec=read(OUT/'figure_receipts.json');spec=specifications()
    write(OUT/'extraction_plan.json',dict(specifications=spec,pixel_bound=3,endpoint_tolerance_pp=.1,minimum_actual_early_positions=3,model_fits=0,
        interpretation='All selected remaining endpoints reviewed; CLK low-resolution early glyphs unresolved and held. Actual dense printed traces versus isolated glyphs distinguished. Highlight is not geometric centre. No endpoint-based axis calibration, no interpolation of sparse connecting lines, no new formal endpoint or independent source. Printed errorbars retained as author context, not claimed to be digitization noise.'))
    out=[];qc=[]
    for s in spec:
        parent=next(v for v in rec if Path(v['output']).name==s['parent']);image=Image.open(ROOT/parent['output']).convert('RGB').crop(s['crop']);path=OUT/(s['label']+'_cycle_panel.png');image.save(path)
        raw,held=points_from_pixels(s,image);x0,xN,y0,y100,N=s['cal'];points=[];bd=300/(y0-y100)
        for x,y,ev in raw:
            n=(x-x0)*N/(xN-x0);value=(y0-y)*100/(y0-y100)
            if n < -3*N/(xN-x0): continue
            points.append(dict(marker_index=len(points),x_px=x,y_px=y,cycle_coordinate=n,cycle_lower=max(0,n-3*N/(xN-x0)),cycle_upper=n+3*N/(xN-x0),retention_pct=value,reading_interval_pp=[value-bd,value+bd],reading_bound_pp=bd,sampling_mode=s['mode'],source_pixels=ev))
        row=baseline[s['eid']];last=points[-1]if points else None;consistent=bool(last and last['reading_interval_pp'][0]-.1<=row['target']<=last['reading_interval_pp'][1]+.1)
        windows=[dict(fraction=f,point_count=sum(p['cycle_upper']<=f*N for p in points),marker_indices=[p['marker_index'] for p in points if p['cycle_upper']<=f*N]) for f in [.1,.2]]
        q=dict(curve_id='local_curve_v3f:'+s['eid'],endpoint_id=s['eid'],source_family=row['source_family'],sample_name=row['sample_name'],system='2E',target_cycle_count=N,author_retention_pct=row['target'],features={k:row['features'].get(k)for k in ['cycle_count','reported_current_A_g','electrolyte','concentration_mol_L','cycle_voltage_lower_V','cycle_voltage_upper_V','BET_m2_g']},conditions=row['conditions'],figure_path=path.relative_to(ROOT).as_posix(),figure_sha256=sha(path),original_pdf_path=parent['source_path'],original_pdf_sha256=parent['source_sha256'],panel_provenance=dict(pdf_page=parent['pdf_page'],figure=s['figure'],original_image_path=parent['output'],crop_rect=s['crop'],source_format=parent['method']),calibration=dict(x0=x0,xN=xN,y0=y0,y100=y100,N=N,pixel_bound=3),points=points,first_plotted_reference=None,window_availability=windows,endpoint_consistent_with_graph_bound=consistent,training_eligible_pending_visual_review=False,genuinely_new_external_source=False,new_formal_cycle_admission=False,old_endpoint_label_changed=False)
        out.append(q);overlay=image.copy();d=ImageDraw.Draw(overlay)
        for p in points:d.rectangle((p['x_px']-1,p['y_px']-1,p['x_px']+1,p['y_px']+1),outline='orange')
        for f,c in[(.1,'green'),(.2,'purple')]:x=x0+f*(xN-x0);d.line((x,s['roi'][2],x,s['roi'][3]),fill=c,width=1)
        overlay.save(OUT/(s['label']+'_overlay.png'))
        item=dict(label=s['label'],endpoint_id=s['eid'],positions=len(points),held_glyphs=held,last_visible_cycle=last['cycle_coordinate']if last else None,last_retention=last['retention_pct']if last else None,last_interval=last['reading_interval_pp']if last else None,author=row['target'],consistent=consistent,windows=windows)
        qc.append(item);print(s['label'],len(points),'last',round(last['retention_pct'],5)if last else None,'author',row['target'],'consistent',consistent,'windows',[w['point_count']for w in windows])
    write(OUT/'extracted_curve_candidates.json',out);write(OUT/'extraction_qc.json',qc)

if __name__=='__main__':main()
