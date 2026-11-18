"""P77: read only the supplied PDFs, keep same-test measurements distinct, lock a diagnostic before reveal."""
import argparse, csv, hashlib, json, re, sys, warnings
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
BASE=next(ROOT.glob('保持率达标研究_v3*'))
OUT=BASE/'第七十七轮_两篇正文与绿茶高BET核查_20261118'
TEA='10.1016/j.sajce.2026.100908'
OIL='10.1016/j.rsurfi.2024.100313'

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def save(name,obj):
    with (OUT/name).open('x',encoding='utf-8',newline='\n') as f:
        json.dump(obj,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
def flat(s): return ' '.join(s.split())
def prep(folder):
    import numpy as np
    import pdfplumber
    from pypdf import PdfReader
    from tools.retention_blind_reserve_v22 import db_matches
    files={OIL:folder/'A new porous carbon derived from waste Pongamia pinnata oil residue as a renewable resource for supercapacitor performance.pdf',TEA:folder/'Activation Agent-Driven Modulation of Green Tea-Derived Nitrogen-Doped Carbons for Energy Storage Applications.pdf'}
    rr={doi:PdfReader(f) for doi,f in files.items()}; expected={OIL:'45e86baa4682c81a1673868e8172c48ee3f0d30269d214fe000e631f16f3bf19',TEA:'c09ff9d2592212945d95d37b27b0ec40c061088bc2b35ae5e695fb7d29351663'}
    for doi,p in files.items(): assert sha(p)==expected[doi] and doi in flat(rr[doi].pages[0].extract_text()).lower()
    hits=db_matches(list(files));assert all(v==0 for pair in hits.values() for v in pair.values())
    OUT.mkdir(exist_ok=True)
    save('source_receipts.json',[dict(doi=d,filename=p.name,page_count=len(rr[d].pages),bytes=p.stat().st_size,sha256=expected[d],prior_database_source_rows=hits[d]) for d,p in files.items()]); facts=[]
    def fact(d,s,field,val,unit,loc,condition='',role='auxiliary_reported'):
        facts.append(dict(doi=d,sample=s,field=field,value=val,unit=unit,locator=loc,condition=condition,role=role))
    with pdfplumber.open(files[TEA]) as pdf:
        mat=pdf.pages[4]; area=mat.crop((0,0,mat.width/2,mat.height)).extract_text();
        for s,bet,pore in re.findall(r'^(GTN8|GKN8|GZN8) (\d+\.\d+) (0\.\d+)\s*$',area,re.M):
            fact(TEA,s,'BET',bet,'m2/g','p5 Table 2');fact(TEA,s,'total_pore_volume',pore,'cm3/g','p5 Table 2')
        p=pdf.pages[6]; t=p.crop((298,0,p.width,p.height)).extract_text(); t=t[t.index('GTN8 1 110.647'):t.index('20 99.527 70 56.447 10.650')+len('20 99.527 70 56.447 10.650')];sample=None
        for line in t.splitlines():
            m=re.fullmatch(r'(?:(GTN8|GKN8|GZN8) )?(1|2|3|5|10|20) ([\d.]+) ([\d.]+) ([\d.]+) ([\d.]+)',line);assert m,line
            s,j,cs,cv,e,power=m.groups();sample=s or sample
            # CV column has no scan rate specified here; never treat its paired GCD current as a CV measurement condition.
            for field,val,unit in [('GCD_specific_capacitance',cs,'F/g'),('CV_specific_capacitance',cv,'F/g'),('reported_energy_density',e,'mWh/g'),('reported_power_density',power,'mW/g')]:
                cond=f'3E;6 M KOH;GCD {j} A/g' if field!='CV_specific_capacitance' else f'3E;6 M KOH;paired with table row {j} A/g;CV scan rate unresolved'
                fact(TEA,sample,field,val,unit,'p7 Table 4',cond)
    with pdfplumber.open(files[OIL]) as pdf:
        t=pdf.pages[7].extract_text();
        for s,vals in re.findall(r'^(PRPC|PRC[5678]) ((?:[\d.]+ ){8}[\d.]+)\s*$',t,re.M):
            for field,val,unit in zip(['BET','micropore_area','mesopore_area','total_pore_volume','micropore_volume','mesopore_volume','micropore_volume_share','mesopore_volume_share','reported_Dg'],vals.split(),['m2/g']*3+['cm3/g']*3+['%','%','nm'],strict=True): fact(OIL,s,field,val,unit,'p8 Table 2')
    text=flat(rr[OIL].pages[10].extract_text());assert '93.01%' in text and '22.52' in text and '20.95' in text and '10 Ag-1' in text
    for j,cs in zip([.4,.8,1,3,5,10],[87.09,80.51,65.55,60.40,56.69,45.82],strict=True):
        assert f'{cs:.2f}' in text;fact(OIL,'PRC8','GCD_specific_capacitance',cs,'F/g','p11 section 3.9 / Fig 10b',f'2E symmetric;aqueous Na2SO4;0–1 V;{j} A/g','separate_device_rate_series')
    for field,val,unit in [('initial_cycle_specific_capacitance',22.52,'F/g'),('later_cycle_specific_capacitance',20.95,'F/g'),('author_terminal_retention_approx',93.01,'%')]:
        fact(OIL,'PRC8',field,val,unit,'p11–12 Fig 10f and cycling paragraph','2E symmetric;Na2SO4;10 A/g;5000 cycles;mass denominator unconfirmed','separate_device_cycling')
    assert len(facts)==132 and len({(f['doi'],f['sample'],f['field'],f['condition']) for f in facts})==132
    with (OUT/'auxiliary_facts.csv').open('x',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(facts[0])); w.writeheader();w.writerows(facts)
    fig=rr[TEA].pages[8].images[0].image.convert('RGB'); assert fig.size==(1250,939)
    early=fig.crop((0,0,365,785));a=np.asarray(early); black=a.max(axis=2)<100
    def yr(x):
        y=np.where(black[445:500,x])[0]+445;return [int(min(y)),int(max(y))]
    # Visible starts of successive descending square lower edges; no grid interpolation or use of distant points. Final square has an exposed right edge.
    low_edges=[181,191,201,212,232]; centers=[]
    for x in low_edges:
        y=float(np.median([yr(i)[1] for i in range(x,x+4)])); assert y>yr(x-2)[1];centers.append((x+7.5,y-7.5))
    centers.append((279-7.5,float(np.mean(yr(275)))))
    y0=yr(173)[0]+7.5
    def cap(y): return 85-(y-22.5)*30/(785-22.5)
    def cycle(x): return (x-168.5)*1000/(1202-168.5)
    points=[dict(cycle=cycle(x),cycle_lower=cycle(x-3),cycle_upper=cycle(x+3),retention_pct=100*cap(y)/cap(y0),sample_center_px=[x,y],capacitance_F_g=cap(y),retention_reading_envelope_pct=[100*cap(y+3)/cap(y0-3),100*cap(y-3)/cap(y0+3)]) for x,y in centers]; assert all(0<p['cycle_lower']<p['cycle_upper']<=200 for p in points)
    save('early_only.json',dict(doi=TEA,sample='GKN8',system='3E',target_cycles=1000,electrolyte='KOH',concentration_mol_L=6,reported_current_A_g=10,reference_electrode='Ag/AgCl',bet_m2_g=1680,bet_source='p5 Table 2',source_figure='p9 Fig 9 black squares; p10 cycling paragraph, not the cross-study comparison row for GZN8',normalization='Same black trace, first partly obscured plotted marker near the origin; no assumption that its experimental index is exactly 0 or 1. Author approximate absolute capacitance is not used as denominator.',pixel_axes={'x_at_0_1000':[168.5,1202],'y_at_85_55':[22.5,785],'legend_square_half_width_px':7.5,'initial_center_y':y0,'pixel_margin_each_axis':3},early_points=points,role='locked independent-paper diagnostic; not counted in strict blind cohort',disclosure='Exact 1000-cycle percentage and right-hand graph were withheld; redacted identity review nevertheless showed qualitative stability and an approximate 67.1 F/g descriptor of the run. These are not model inputs. Do not assert completely unexposed validation.',other_curves={'CKN8':'reference carbon, not mapped to GKN8. p2 Table 1; p9 body.','CZN8':'reference carbon, not mapped to GZN8; commercial carbon noted p9.','GTN8 and GZN8':'no labelled Fig 9 early trace; text/table outcomes not paired with other curves.'},figure_before_lock='only early trace, legend, isolated axes inspected',image_pixel_sha256=hashlib.sha256(np.asarray(early).tobytes()).hexdigest()))

def lock():
    import numpy as np
    from tools.retention_prospective_predict_v75 import checked,predict,committed
    from tools.retention_mild_scope_v64 import outside_reasons
    epath=OUT/'early_only.json';parent=committed(epath);e=json.loads(epath.read_text(encoding='utf8')); pts=e['early_points'];x=np.array([p['cycle'] for p in pts]);y=np.array([p['retention_pct'] for p in pts]);f=dict(last_early_retention_pct=float(y[-1]),early_mean_retention_pct=float(y.mean()),early_retention_slope_per_1000_cycles=float(np.polyfit(x/1000,y,1)[0]),early_retention_range_pp=float(np.ptp(y)),early_observed_cycle_count=float(x[-1]),target_cycle_count=1000)
    row=dict(row_id='P77-GKN8-F9-1000',curve_id='P77-GKN8-F9-1000',source_family='doi:'+TEA,features=f,last_early=float(y[-1]),static_features={k:e[k] for k in ['electrolyte','concentration_mol_L','reported_current_A_g','bet_m2_g']});assert not outside_reasons(row,dict(mol_L_min=2,mol_L_max=6,A_g_min=1,A_g_max=10));_,_,pool,cfg,midplan,mid=checked();
    with warnings.catch_warnings(record=True) as warns:
        output,n=predict(pool,[row],cfg,mid,midplan)
    assert n==2 and len(pool)==23 and output[0]['p64']==output[0]['p67'];save('locked_diagnostic.json',dict(early_commit=parent,early_sha256=sha(epath),frozen_recipes='P64/P67 identical at 1000 cycles',features=f,outputs=output,fits=n,warnings=[str(q.message) for q in warns],fits_on_incoming_cases=0,development_sources=len(set(r['source_family'] for r in pool)),formal_blind_case=False))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['prep','lock']);p.add_argument('--pdf-folder',type=Path);a=p.parse_args();prep(a.pdf_folder) if a.stage=='prep' else lock()
