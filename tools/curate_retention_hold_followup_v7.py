"""Forward-only MMC own-reference curation and independent ratio audit."""
from pathlib import Path
import json,hashlib,math,sqlite3
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'保持率达标研究_v3_主线与近优组合_20261030';P11=BASE/'第十一轮_双电极原文曲线补充';OUT=P11/'batch4_20261031'
def read(p):return json.loads(Path(p).read_text('utf8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n','utf8')

def curate():
    assert not(OUT/'curve_dataset_v3g.json').exists()
    ptr=read(ROOT/'data/current_retention_research.json');assert ptr['sha256']=='3653231f25c72038a34eb41d6619e7c644a35b9a0e933969915d751173671357'
    files=[ROOT/ptr['database'],P11/'batch3_20261031/curve_dataset_v3f.json',P11/'queue_plan.json',ROOT/'data/current_training_latest.json',ROOT/'全量文献训练数据接入_v7_药渣与地肤主集_20261029/training_extension_v7.sqlite',ROOT/'保持率双路线预研_v2_20261029/baseline_inputs.json',BASE/'research_goal.json',ROOT/'新增文献整理_20261020/originals/ADD_066.pdf',ROOT/'新增文献整理_20261020/originals/ADD_007.pdf',ROOT/'数据质量优化_20261021/additional_sources/ADD_064_1-s2.0-S295015552600025X-mmc1.docx',P11/'MMC_PDFp9_Im10.jpg',P11/'batch2_20261031/BLAC_original.jpg',P11/'batch3_20261031/OPC_original.jpg',P11/'batch3_20261031/OPBNP_original.jp2',BASE/'第十轮_稳健表达与来源权重/results.json',BASE/'第十轮_稳健表达与来源权重/training_plan.json']
    protection={p.relative_to(ROOT).as_posix():sha(p)for p in files}
    for name,h in read(P11/'batch3_20261031/source_protection.json')['files'].items():
        p=Path(name);assert sha(p)==h
        protection[p.relative_to(ROOT).as_posix()if p.is_relative_to(ROOT)else p.as_posix()]=h
    write(OUT/'source_protection.json',dict(files=protection,parent_pointer=ptr,parent_pointer_sha256=sha(ROOT/'data/current_retention_research.json'),parent_scientific_protection_inherited=True))
    q=read(OUT/'MMC_candidate.json');qc=read(OUT/'MMC_reading_qc.json');assert q['endpoint_consistent_with_graph_bound']
    # Original author95.6 is rounded to one decimal. Its rounding interval,
    # not its exact displayed centre, intersects the independently read box.
    box=qc['last_interval'];rounding=qc['author_one_decimal_rounding_interval'];assert max(box[0],rounding[0])<=min(box[1],rounding[1])
    q['training_eligible_pending_visual_review']=True
    q['visual_review']=dict(status='approved_exploratory_early_window_with_reference_precision_limit',reason='Own first actual red cycling C(N) glyph resolved geometrically. Propagated numerator/reference3px box intersects the author95.6% rounding interval, not the displayed95.6 centre itself. Exact author reference index unknown, no borrowing rateC0 or endpoint scaling.',shared_reference_uncertainty=True,author_reference_exact_cycle_unknown=True,author_target_matches_via_rounding_interval_only=True,not_formal_new_endpoint=True)
    parent=read(P11/'batch3_20261031/curve_dataset_v3f.json');assert q['endpoint_id']not in{r['endpoint_id']for r in parent};write(OUT/'curve_dataset_v3g.json',parent+[q])
    follow=dict(MMC='One exploratory Bcurve approved with explicit precision limit. C0 from its own first actual cycling glyph36.553444F/g, bound0.418605F/g. Nearend93.332598%, propagated91.143649..95.572262%; author95.6 roundedinterval95.55..95.65 intersects by0.022262pp. Do not say exact95.6 liesinside the box or that uncertainty is resolved completely.',BLAC='Own first glyph52.335F/g versusnearend51.223F/g unchanged. Ratio97.875354 box96.207865..99.571429 does not overlap author96% evenwith fixed.1pp tolerance. Stillheld, no second/max C0 selected.',CLK='Existing publisher SI DOCX has5 media objects and FigS1..S5:FTIR,NMR,SEM,3E electrochemical/rate/EIS. No clearer own Fig6j cycling duplicate found. Existing mainFig6j still553x470wholeimage, early glyphs unresolved. No upsampled pseudo-evidence.',OPC='Original user-source directory contains only mainPDF and use-note, no extraSI. Labelled100/80 axis and original dense trace rechecked; nearend99.146919 reading box98.578199..99.715640 remains below author100, fixed.1pp does not bridge. Hold.',OPBNP='Lower-envelope geometry-only experiment yielded21 tentative circles but none in approved first10%/20% windows. Overlay review shows partial arcs/annotation errors, so every tentative circle remains unvalidated and no curve admitted. Existing false92.84 is not a scientific fact.',control_C='MMC figure also shows controlC, but no author end-retention label in reviewed cycling paragraph; do not infer an author label or treat curve as another independent source. Retain figure locator for later separately labelled digitized-target review.')
    write(OUT/'five_case_followup.json',dict(status='one_case_research_admitted_four_stillheld',cases=follow,author_label_changes=0,new_formal_endpoint_admissions=0,new_external_sources=0,new_model_fits=0))
    print('MMC curated with rounding-only consistency;four holds retained.')

def verify():
    checks=[]
    def ck(name,ok):
        if not ok:raise AssertionError(name)
        checks.append(name)
    prot=read(OUT/'source_protection.json')
    for p,h in prot['files'].items():ck('protected:'+p,sha(ROOT/p)==h)
    parent=read(P11/'batch3_20261031/curve_dataset_v3f.json');data=read(OUT/'curve_dataset_v3g.json');ck('69_old_objects_preserved',len(parent)==69 and data[:-1]==parent)
    q=data[-1];base=next(r for r in read(ROOT/'保持率双路线预研_v2_20261029/baseline_inputs.json')['2E']if r['row_id']==q['endpoint_id']);ck('original_label_group_and_features',q['author_retention_pct']==base['target']and q['source_family']==base['source_family']and q['features']=={k:base['features'].get(k)for k in q['features']})
    original=Image.open(P11/'MMC_PDFp9_Im10.jpg').convert('RGB').crop((0,560,760,1116));panel=Image.open(ROOT/q['figure_path']).convert('RGB');a=np.array(panel).astype(float);ck('exact_original_crop',np.array_equal(np.array(original),a));ck('source_pdf_hash',sha(ROOT/q['original_pdf_path'])==q['original_pdf_sha256'])
    red=(a[:,:,0]>150)&(a[:,:,0]-a[:,:,1]>65)&(a[:,:,0]-a[:,:,2]>50);cal=q['calibration'];scale=60/(cal['y0']-cal['y60']);bd=3*scale;ref=q['first_plotted_reference'];C0=ref['value_F_g'];first=q['points'][0];ev=first['source_pixels'];arc=np.array(ev['reference_glyph_contour'],float)
    ck('actual_first_contour_pixels',red[arc[:,1].astype(int),arc[:,0].astype(int)].all());radius=ev['glyph_radius_px'];ck('first_glyph_geometry',max(abs(np.hypot(arc[:,0]-first['x_px'],arc[:,1]-first['y_px'])-radius))<=1.5)
    ck('own_C0_not_rate_value',math.isclose(C0,(468-first['y_px'])*60/430,abs_tol=1e-10)and ref['reference_cycle_index_unknown'])
    for i,p in enumerate(q['points']):
        tag=str(i);x,y=p['x_px'],p['y_px'];c=(468-y)*60/430;ck('absoluteC:'+tag,math.isclose(c,p['raw_capacitance_F_g'],abs_tol=1e-10));ck('fixed_pixel_box:'+tag,math.isclose(p['raw_capacitance_reading_bound_F_g'],bd,abs_tol=1e-10))
        if i:
            ys=p['source_pixels']['column_y'];ck('actual_red_pixels:'+tag,red[ys,int(x)].all() and y==(min(ys)+max(ys))/2)
            lo=100*(c-bd)/(C0+bd);hi=100*(c+bd)/(C0-bd);ck('shared_reference_ratio_box:'+tag,all(math.isclose(v,w,abs_tol=1e-10)for v,w in zip([lo,hi],p['reading_interval_pp'])))
        else:ck('algebraic_reference100_not_exact_measurement',p['retention_pct']==100 and p['derived_reference_not_exact_raw_measurement'])
        ck('no_cycle_rounding_or_window_leak:'+tag,math.isclose(p['cycle_upper'],(x+3-158.5)*30000/562,abs_tol=1e-9))
    lo,hi=q['points'][-1]['reading_interval_pp'];ck('rounded_author_overlap_only',hi<95.6 and max(lo,95.55)<=min(hi,95.65));ck('real_early_counts',[w['point_count']for w in q['window_availability']]==[10,24])
    c=sqlite3.connect((OUT/'cycling_research_v3g.sqlite').as_uri()+'?mode=ro',uri=True);ck('integrity',c.execute('pragma integrity_check').fetchone()[0]=='ok');ck('foreign_keys',not c.execute('pragma foreign_key_check').fetchall())
    views={}
    for name,expected in [('training_B_2E_early20',(27,22)),('training_B_2E_early10',(23,18)),('training_B_3E_early20',(30,24)),('training_B_3E_early10',(20,19))]:
        got=c.execute(f'SELECT count(*),count(DISTINCT source_family)FROM {name}').fetchone();ck('view:'+name,got==expected);views[name]=list(got)
    for f,n in[(.1,10),(.2,24)]:
        r=c.execute('SELECT point_count,point_indices_json FROM training_windows WHERE endpoint_id=? AND fraction=?',(q['endpoint_id'],f)).fetchone();ids=[p['marker_index']for p in q['points']if p['cycle_upper']<=f*30000];ck('callable_actual_MMC:'+str(f),r[0]==n and json.loads(r[1])==ids)
    ck('raw_exact_new_curve',json.loads(c.execute('SELECT raw_json FROM curves WHERE curve_id=?',(q['curve_id'],)).fetchone()[0])==q);c.close()
    for p,h in prot['files'].items():ck('final_protection:'+p,sha(ROOT/p)==h)
    result=dict(status='passed',checks=len(checks),protected_files=len(prot['files']),old_curve_objects_preserved=69,new_early_curves=1,new_correlated_positions=138,author_label_changes=0,new_formal_endpoint_admissions=0,new_model_fits=0,new_untouched_external_sources=0,shared_reference_uncertainty_preserved=True,exact_author_target_inside_reading_box=False,author_rounding_interval_intersects_box=True,remaining_holds=4,views=views,sqlite_sha256=sha(OUT/'cycling_research_v3g.sqlite'),check_names=checks)
    write(OUT/'independent_verification.json',result);print(json.dumps({k:v for k,v in result.items()if k!='check_names'},ensure_ascii=False,indent=2))
if __name__=='__main__':
    import sys
    curate()if sys.argv[1]=='curate'else verify()
