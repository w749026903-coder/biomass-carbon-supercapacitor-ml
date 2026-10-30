"""Independent pixel, original-source, lineage and SQL early-window audit."""
from pathlib import Path
import hashlib,json,math,sqlite3
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'保持率达标研究_v3_主线与近优组合_20261030';OUT=BASE/'第十一轮_双电极原文曲线补充/batch3_20261031'
def read(p):return json.loads(Path(p).read_text('utf8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n','utf8')

def main():
    checks=[]
    def ck(name,condition):
        if not condition:raise AssertionError(name)
        checks.append(name)
    protection=read(OUT/'source_protection.json')
    for p,h in protection['files'].items():ck('source_unchanged:'+p,sha(p)==h)
    old=read(OUT.parent/'batch2_20261031/curve_dataset_v3e.json');curves=read(OUT/'curve_dataset_v3f.json');new=curves[len(old):]
    ck('old55_exact_objects',curves[:len(old)]==old and len(old)==55)
    ck('new14_candidates',len(new)==14)
    ck('endpoint_deduplication',len({q['endpoint_id'] for q in curves})==len(curves))
    baseline={r['row_id']:r for r in read(ROOT/'保持率双路线预研_v2_20261029/baseline_inputs.json')['2E']}
    rec=read(OUT/'figure_receipts.json');approved=[q for q in new if q['training_eligible_pending_visual_review']]
    ck('12_approved_10_source_families',len(approved)==12 and len({q['source_family']for q in approved})==10)
    positions=sum(len(q['points'])for q in approved);ck('864_correlated_positions_not_experiments',positions==864)
    for q in new:
        row=baseline[q['endpoint_id']];ck('author_label:'+q['endpoint_id'],row['target']==q['author_retention_pct'])
        ck('source_group:'+q['endpoint_id'],row['source_family']==q['source_family'])
        ck('static_conditions:'+q['endpoint_id'],q['features']=={k:row['features'].get(k)for k in q['features']})
        ck('original_hash:'+q['curve_id'],sha(ROOT/q['original_pdf_path'])==q['original_pdf_sha256'])
        ck('no_new_external_or_admission:'+q['curve_id'],not q['genuinely_new_external_source'] and not q['new_formal_cycle_admission'])
        parent=next(r for r in rec if r['output']==q['panel_provenance']['original_image_path'])
        original=Image.open(ROOT/parent['output']).convert('RGB').crop(q['panel_provenance']['crop_rect']);panel=Image.open(ROOT/q['figure_path']).convert('RGB')
        ck('exact_original_crop:'+q['curve_id'],np.array_equal(np.array(original),np.array(panel)) and sha(ROOT/q['figure_path'])==q['figure_sha256'])
        if not q['training_eligible_pending_visual_review']:continue
        a=np.array(panel);cal=q['calibration'];dx=cal['xN']-cal['x0'];dy=cal['y0']-cal['y100'];N=q['target_cycle_count']
        ck('near_endpoint_not_synthetic_exact_N:'+q['curve_id'],q['points'][-1]['cycle_coordinate']>=.97*N)
        ck('near_endpoint_consistent:'+q['curve_id'],q['points'][-1]['reading_interval_pp'][0]-.1<=q['author_retention_pct']<=q['points'][-1]['reading_interval_pp'][1]+.1)
        last=-math.inf
        for i,p in enumerate(q['points']):
            tag=q['endpoint_id']+':'+str(i);x,y=p['x_px'],p['y_px'];ck('ordered_actual_positions:'+tag,x>last);last=x
            ck('axis_affine_reading:'+tag,math.isclose(p['retention_pct'],(cal['y0']-y)*100/dy,abs_tol=1e-10))
            ck('fixed3px_bound:'+tag,math.isclose(p['reading_bound_pp'],300/dy,abs_tol=1e-10) and cal['pixel_bound']==3)
            ck('independent_cycle_bounds:'+tag,math.isclose(p['cycle_coordinate'],(x-cal['x0'])*N/dx,abs_tol=1e-9) and math.isclose(p['cycle_upper'],(x+3-cal['x0'])*N/dx,abs_tol=1e-9))
            ev=p['source_pixels']
            if 'column_y'in ev:
                ys=ev['column_y'];ck('actual_column_pixels:'+tag,bool(ys) and min(ys)<=y<=max(ys) and 0<=int(x)<a.shape[1])
                rgb=a[ys,int(x)].astype(float);label=Path(q['figure_path']).name
                if label.startswith('MF_'):ok=(rgb[:,0]-rgb[:,1]>30).all()and(rgb[:,0]-rgb[:,2]>20).all()
                elif label.startswith(('LYS_','NWJPC_','NDB_')):ok=(rgb[:,1]-rgb[:,0]>8).all()
                elif label.startswith(('PPC_','PC_NaCl_3A_','LAC_')):ok=(rgb[:,0]-rgb[:,1]>30).all()
                else:ok=(rgb[:,2]-rgb[:,0]>30).all()
                ck('correct_trace_colour_not_CE:'+tag,ok)
            elif 'lower_contour_pixels'in ev:
                arc=np.array(ev['lower_contour_pixels'],float);cx,cy=x,y;rr=np.sqrt((arc[:,0]-cx)**2+(arc[:,1]-cy)**2)
                ck('geometric_lower_arc_not_highlight:'+tag,len(arc)>=10 and max(abs(rr-ev['glyph_radius_px']))<=1.50000001)
                rgb=a[arc[:,1].astype(int),arc[:,0].astype(int)].astype(float)
                ck('lower_arc_is_original_green:'+tag,(rgb[:,1]-rgb[:,0]>20).all()and(rgb[:,1]-rgb[:,2]>10).all())
            else:
                px,py=int(round(x)),int(round(y));patch=a[max(0,py-2):py+3,max(0,px-2):px+3].astype(float)
                if ev.get('visually_located_actual_glyph'):ok=(patch[:,:,0]-patch[:,:,1]>30).sum()>=3
                else:ok=(patch.max(2)<130).sum()>=5
                ck('visible_actual_solid_or_star_glyph:'+tag,ok)
        for f in [.1,.2]:
            expected=[p['marker_index'] for p in q['points'] if p['cycle_upper']<=f*N];actual=next(w for w in q['window_availability']if w['fraction']==f)
            ck('strict_early_upper_bound:'+q['curve_id']+str(f),actual['marker_indices']==expected and actual['point_count']==len(expected))
    # Independent labelled tick records from visually read axes, including the
    # truncated SSC axis, separate left/right NDB and AUACW scales.
    ticks={'MF':[(120,26.3),(0,507.5)],'LYS':[(120,14),(0,422)],'NWJPC':[(120,31.4),(0,435)],'PC_NaCl_1A':[(150,76),(0,488.5)],'PC_NaCl_3A':[(150,76),(0,488.5)],'NDB':[(300,38),(0,394)],'DUGPC':[(100,69),(0,380)],'SSC':[(85,666),(100,176)],'AUACW':[(150,40.5),(0,380)],'PPC':[(100,114.5),(0,399)],'PR2':[(120,122),(0,1361)],'LAC':[(100,92.5),(0,616.5)]}
    for q in approved:
        label=Path(q['figure_path']).name.removesuffix('_cycle_panel.png');cal=q['calibration']
        for value,yp in ticks[label]:ck('visible_axis_tick:'+label+str(value),abs((cal['y0']-yp)*100/(cal['y0']-cal['y100'])-value)<=300/(cal['y0']-cal['y100'])+1e-8)
    dest=OUT/'cycling_research_v3f.sqlite'
    c=sqlite3.connect(dest.as_uri()+'?mode=ro',uri=True);c.row_factory=sqlite3.Row
    ck('sqlite_integrity',c.execute('pragma integrity_check').fetchone()[0]=='ok');ck('foreign_keys',not c.execute('pragma foreign_key_check').fetchall())
    expected_counts={('3E',.2):(30,24),('3E',.1):(20,19),('2E',.2):(26,21),('2E',.1):(22,17)}
    for (system,f),expected in expected_counts.items():
        rows=[dict(r)for r in c.execute('SELECT * FROM training_windows WHERE system=? AND fraction=?',(system,f))]
        ck('view_count:'+system+str(f),(len(rows),len({r['source_family']for r in rows}))==expected)
        for r in rows:
            q=next(q for q in curves if q['curve_id']==r['curve_id']);ps=[p for p in q['points']if p['cycle_upper']<=f*q['target_cycle_count']];n=len(ps);xs=[p['cycle_coordinate']for p in ps];ys=[p['retention_pct']for p in ps];xm=sum(xs)/n;ym=sum(ys)/n
            slope=sum((x-xm)*(y-ym)for x,y in zip(xs,ys))/sum((x-xm)**2 for x in xs)*1000
            ck('source_and_approved:'+r['curve_id']+str(f),q['training_eligible_pending_visual_review'] and r['source_family']==q['source_family'] and n>=3)
            ck('SQL_window_indices:'+r['curve_id']+str(f),json.loads(r['point_indices_json'])==[p['marker_index']for p in ps])
            ck('SQL_window_features:'+r['curve_id']+str(f),all(math.isclose(a,b,abs_tol=1e-9)for a,b in[(r['last_early_retention_pct'],ys[-1]),(r['early_mean_retention_pct'],ym),(r['early_retention_slope_per_1000_cycles'],slope),(r['early_retention_range_pp'],max(ys)-min(ys))]))
    for r in c.execute('SELECT curve_id,raw_json FROM curves'):
        ck('raw_original_record:'+r['curve_id'],json.loads(r['raw_json'])==next(q for q in curves if q['curve_id']==r['curve_id']))
    bad={'incoming:ADD_006_T01','legacy:SRC035_CY01','incoming:ADD_064_T01','incoming:ADD_007_T01','incoming:ADD_066_T01'}
    ids={r[0]for r in c.execute('SELECT endpoint_id FROM training_windows')};ck('all5_queue_holds_excluded',not ids&bad)
    ck('SSC_two_point10pct_excluded','legacy:R104_CY01'not in{r[0]for r in c.execute("SELECT endpoint_id FROM training_windows WHERE system='2E' AND fraction=.1")})
    ck('no_author_growth_clipping',sum(q['author_retention_pct']>100 for q in approved)==3)
    c.close()
    for p,h in protection['files'].items():ck('final_protection:'+p,sha(p)==h)
    result=dict(status='passed',checks=len(checks),protected_files=len(protection['files']),old_curve_objects_preserved=len(old),new_candidate_curves=14,new_approved_early_curves=12,new_source_groups=10,approved_positions=positions,positions_are_correlated_curve_readings_not_experiments=True,views={s+str(int(f*100)):list(v)for(s,f),v in expected_counts.items()},canonical_label_changes=0,new_formal_cycle_admissions=0,new_untouched_external_sources=0,new_model_fits=0,sqlite_sha256=sha(dest),all_scientific_questions_resolved=False,remaining_queue_holds=['MMC own firstC(N) reference','BLAC ownC(N) reference conflicts with author','CLK low-resolution earlyglyphs','OPC near-endpoint graph versus body','OPBNP blueglyphs occluded and coordinate extraction unresolved'],limitations=['Near-endpoint reading checks use last visible position >=97% ofN, not synthetic exactN measurements.','Fixed3px reading boxes are not statistical confidence intervals.','Whole source validation and new untouched external testing still required.'],check_names=checks)
    write(OUT/'independent_verification.json',result);print(json.dumps({k:v for k,v in result.items()if k!='check_names'},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
