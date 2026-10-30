"""Forward semantic correction: MK9 green CE79.3, blue retention65.

Never rewrite old extraction, v7/3g, frozen inputs or model results. The new
canonical release materializes already-selected views to enforce local FKs.
"""
from pathlib import Path
import hashlib,json,sqlite3,sys,copy,shutil
import numpy as np
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
BASE=ROOT/'保持率达标研究_v3_主线与近优组合_20261030';P11=BASE/'第十一轮_双电极原文曲线补充';OUT=P11/'batch5_指标纠错_20261031';CAN=ROOT/'全量文献训练数据接入_v7r1_循环指标纠错_20261031';EID='v25:Mango_MK9_2E_C100000'
def read(p):return json.loads(Path(p).read_text('utf8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(x):return json.dumps(x,ensure_ascii=False,allow_nan=False)
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n','utf8')

def extract():
    assert not(OUT/'MK9_blue_corrected_candidate.json').exists()
    old=next(q for q in read(P11/'batch4_20261031/curve_dataset_v3g.json')if q['endpoint_id']==EID);q=copy.deepcopy(old);image=Image.open(ROOT/old['figure_path']).convert('RGB');image.crop((0,0,380,265)).save(OUT/'MK9_axis_evidence.png');a=np.array(image).astype(float);r,g,b=[a[:,:,j]for j in range(3)];mask=(b-r>35)&(b-g>20)&(b>100);mask[:33]=False;mask[128:]=False;mask[:,:70]=False;mask[:,320:]=False;mass=mask.sum(0)
    cand=[x for x in range(72,318)if mass[x]>=5 and mass[x]==max(mass[x-2:x+3])];xs=[]
    for x in sorted(cand,key=lambda x:(-mass[x],x)):
        if all(abs(x-v)>=8 for v in xs):xs.append(x)
    points=[]
    for x in sorted(xs):
        ys=np.flatnonzero(mask[:,x]);y=float((ys.min()+ys.max())/2);n=(x-76)*100000/238;v=(237-y)*100/195;bound=300/195
        points.append(dict(marker_index=len(points),x_px=float(x),y_px=y,cycle_coordinate=n,cycle_lower=max(0,n-300000/238),cycle_upper=n+300000/238,retention_pct=v,reading_interval_pp=[v-bound,v+bound],reading_bound_pp=bound,source_pixels=dict(column_y=ys.tolist()),sampling_mode='actual_blue_capacitance_retention_glyph_centre_not_green_CE'))
    assert len(points)>=15 and points[-1]['cycle_coordinate']>=97000
    q.update(curve_id='metric_v3h:'+EID,author_retention_pct=65.,co_reported_coulombic_efficiency_pct=79.3,points=points,calibration=dict(x0=76.,xN=314.,N=100000,y0=237.,y100=42.,pixel_bound=3,metric='right_blue_capacitance_retention_percent'),endpoint_consistent_with_graph_bound=points[-1]['reading_interval_pp'][0]-.1<=65<=points[-1]['reading_interval_pp'][1]+.1,training_eligible_pending_visual_review=True,first_plotted_reference=None)
    assert q['endpoint_consistent_with_graph_bound'];q['window_availability']=[dict(fraction=f,point_count=sum(p['cycle_upper']<=f*100000 for p in points),marker_indices=[p['marker_index']for p in points if p['cycle_upper']<=f*100000])for f in[.1,.2]]
    q['visual_review']=dict(status='corrected_metric_role_from_primary_axes_and_body',supersedes_curve_id=old['curve_id'],reason='Original Fig10a leftgreenCE79.3 andrightbluecapacitanceretention65;body explicitly calls79.3 CE. Old classifier anddigitizer reversedroles. No numericvalue selected bymodelperformance.',old_wrong_target=79.3,corrected_target=65.,old_metric_role='misclassified_coulombic_efficiency',first_or_baseline_cycle_index_not_invented=True)
    q['provenance']='Original published Fig10a right blue capacitance-retention curve and printed65% annotation, with body corroboratinggreen79.3 isCE. Same source/physicaltest,not anewexperiment.'
    q['conditions']=dict(q['conditions'],metric_kind='capacitance_retention',metric_axis_evidence='Fig10a rightblueaxis, not leftgreenCE')
    write(OUT/'MK9_blue_corrected_candidate.json',q);write(OUT/'curve_dataset_v3h.json',read(P11/'batch4_20261031/curve_dataset_v3g.json')+[q]);write(OUT/'metric_supersession.json',dict(endpoint_id=EID,previous_curve_id=old['curve_id'],replacement_curve_id=q['curve_id'],previous_processed_target=79.3,corrected_capacitance_retention_pct=65.,co_reported_CE_pct=79.3,reason='scientific_metric_axis_correction_not_performance_selection',old_raw_object_retained_exactly=True))
    overlay=image.copy();draw=ImageDraw.Draw(overlay)
    for p in points:draw.rectangle((p['x_px']-1,p['y_px']-1,p['x_px']+1,p['y_px']+1),outline='orange')
    overlay.save(OUT/'MK9_blue_overlay.png');print('Correct bluecurve',len(points),'last',points[-1]['retention_pct'],'windows',[w['point_count']for w in q['window_availability']])

def canonical():
    assert not CAN.exists(),'Never overwrite a canonical release';CAN.mkdir()
    from data.training_latest import open_training_datasets
    ptr=read(ROOT/'data/current_training_latest.json');assert ptr['version']=='training_latest_v7_YZPC_Kochia';parent=ROOT/ptr['directory']/ptr['database_file'];assert sha(parent)==ptr['sha256'];meta={};schema=[]
    with sqlite3.connect(parent.as_uri()+'?mode=ro',uri=True)as c:
        meta={k:json.loads(v)for k,v in c.execute('SELECT key,value_json FROM metadata')};schema=[sql for name,sql in c.execute("SELECT name,sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
    db=CAN/'training_metric_correction_v7r1.sqlite';dest=sqlite3.connect(db)
    for sql in schema:dest.execute(sql)
    before_counts={};changes=[]
    evidence=read(OUT/'correction_review.json')['evidence'];annotation=dict(correction_id='MK9_metric_axis_20261031',old_processed_retention_pct=79.3,selected_capacitance_retention_pct=65.,co_reported_coulombic_efficiency_pct=79.3,evidence=evidence,reason='Explicit originalaxes/arrows andbodyCE text; authorreportednumbers preserved incorrect roles,notadjustedforR2.')
    with open_training_datasets()as source:
        for table in meta['append_only_union_tables']:
            cols=[r['name']for r in source.connection.execute('PRAGMA main.table_info('+table+')')];rows=source.connection.execute('SELECT *FROM '+table).fetchall();before_counts[table]=len(rows)
            if rows:dest.executemany('INSERT INTO '+table+'('+','.join(cols)+')VALUES('+','.join('?'for _ in cols)+')',[tuple(r)for r in rows])
        def replace(table,keyfields,key,old,after):
            aftertext=dump(after);changeid='MK9_metric:'+table+':'+hashlib.sha256(dump(key).encode()).hexdigest()[:14];change=dict(change_id=changeid,table=table,key=key,before_sha256=hashlib.sha256(old.encode()).hexdigest(),after_sha256=hashlib.sha256(aftertext.encode()).hexdigest(),before=json.loads(old),after=after,reason=annotation['reason'],evidence=evidence)
            dest.execute('UPDATE '+table+' SET record_json=?WHERE '+' AND '.join(k+'=?'for k in keyfields),(aftertext,*key));dest.execute('INSERT INTO overlay_changes VALUES(?,?)',(changeid,dump(change)));changes.append(change)
        old=source.connection.execute('SELECT record_json FROM cycle_records WHERE endpoint_id=?',(EID,)).fetchone()[0];r=json.loads(old);assert r['retention_pct']==79.3;r.update(retention_pct=65.,co_reported_coulombic_efficiency_pct=79.3,metric_correction=annotation);replace('cycle_records',['endpoint_id'],[EID],old,r)
        rows=source.connection.execute('SELECT *FROM inputs WHERE row_id=?',(EID,)).fetchall();assert len(rows)==4
        for row in rows:
            old=row['record_json'];r=json.loads(old);assert r['target']==79.3;r.update(target=65.,co_reported_coulombic_efficiency_pct=79.3,metric_correction=annotation);replace('inputs',['task','row_id'],[row['task'],EID],old,r)
        row=source.connection.execute("SELECT candidate_id,record_json FROM candidates WHERE candidate_id='LP13_Mango_MK9_2E_C100000'").fetchone();r=json.loads(row['record_json']);r['record'].update(retention_pct=65.,co_reported_coulombic_efficiency_pct=79.3,locator='Fig10a right blue capacitance-retention65%; leftgreenCE79.3 andbody corroborate CE; semantic correction20261031');r['record']['metric_correction']=annotation;replace('candidates',['candidate_id'],[row['candidate_id']],row['record_json'],r)
    dest.execute('CREATE TABLE metric_corrections(correction_id TEXT PRIMARY KEY,record_json TEXT NOT NULL)');dest.execute('INSERT INTO metric_corrections VALUES(?,?)',(annotation['correction_id'],dump(annotation)))
    oldchain=[dict(path=parent.relative_to(ROOT).as_posix(),sha256=sha(parent))]+meta['readonly_parent_chain'];meta['readonly_parent_chain']=[];meta['append_only_union_tables']=meta['append_only_union_tables']+['metric_corrections'];meta['materialized_from_pinned_selected_views']=oldchain;meta['summary']=dict(meta['summary'],metric_semantic_corrections=1,current_retention_target_MK9_pct=65.,co_reported_MK9_CE_pct=79.3,metric_correction_new_model_fits=0);meta['semantic_correction_note']='Original v7/parent payloads remain untouched. This new release materializes current selected views and changes6 processed JSONrecords with explicit before/after receipts. Numeric sourcefacts are preserved; metric names and selected cycle target corrected.'
    dest.execute('DELETE FROM metadata');dest.executemany('INSERT INTO metadata VALUES(?,?)',[(k,dump(v))for k,v in meta.items()]);dest.commit();assert dest.execute('PRAGMA integrity_check').fetchone()[0]=='ok';assert not dest.execute('PRAGMA foreign_key_check').fetchall();dest.close();shutil.copyfile(parent.parent/'source_family_rules.json',CAN/'source_family_rules.json')
    write(CAN/'metric_correction_changes.json',changes);write(CAN/'materialization_receipt.json',dict(origin_chain=oldchain,selected_view_counts_before=before_counts,processed_rows_changed=6,new_source_facts=0,originals_retained=True,new_model_fits=0,sqlite_sha256=sha(db)))
    print('Canonical v7r1 materialized;6 processed rows corrected,physicalFKs passed;oldv7 unchanged.')

def verify():
    from data.training_latest import open_training_datasets
    checks=[]
    def ck(s,ok):
        if not ok:raise AssertionError(s)
        checks.append(s)
    q=read(OUT/'MK9_blue_corrected_candidate.json');old=read(P11/'batch4_20261031/curve_dataset_v3g.json');new=read(OUT/'curve_dataset_v3h.json');ck('old70_objects_retained',len(old)==70 and new[:-1]==old);a=np.array(Image.open(ROOT/q['figure_path']).convert('RGB')).astype(float)
    import xml.etree.ElementTree as ET
    review=read(OUT/'correction_review.json')
    for e in review['evidence']:ck('primary_evidence_hash:'+e['path'],sha(ROOT/e['path'])==e['sha256'])
    xml=next(ROOT/e['path']for e in review['evidence']if e['path'].endswith('.xml'));paragraphs=[' '.join(e.itertext())for e in ET.parse(xml).findall('.//p')];ck('body_calls79point3_CE',any('79.3'in t and'coulombic efficiency'in t for t in paragraphs))
    for p in q['points']:
        x=int(p['x_px']);ys=p['source_pixels']['column_y'];rgb=a[ys,x];ck('blue_not_green:'+str(x),(rgb[:,2]-rgb[:,0]>35).all()and(rgb[:,2]-rgb[:,1]>20).all());ck('direct_rightaxis_reading:'+str(x),math_close(p['retention_pct'],(237-p['y_px'])*100/195));ck('fixed3px:'+str(x),math_close(p['reading_bound_pp'],300/195))
    db=CAN/'training_metric_correction_v7r1.sqlite';changes=read(CAN/'metric_correction_changes.json');receipt=read(CAN/'materialization_receipt.json');keys={(r['table'],tuple(r['key']))for r in changes};ck('exact6_change_receipts',len(keys)==6)
    # Pin the historical input explicitly. The rolling latest pointer now names
    # the corrected release, so it must never serve as its own old comparator.
    previous=receipt['origin_chain'][0]
    with open_training_datasets(ROOT/previous['path'],previous['sha256'])as prior,open_training_datasets(db,sha(db))as current:
        for table,n in receipt['selected_view_counts_before'].items():
            oldrows=[dict(r)for r in prior.connection.execute('SELECT *FROM '+table)];newrows=[dict(r)for r in current.connection.execute('SELECT *FROM '+table)];ck('count:'+table,len(oldrows)==len(newrows)==n if table!='overlay_changes'else len(newrows)==n+6)
            if table=='overlay_changes':
                prior_receipts={r['change_id']:r for r in oldrows};current_receipts={r['change_id']:r for r in newrows};ck('all_old_change_chain_receipts_preserved',all(current_receipts[k]==v for k,v in prior_receipts.items()));continue
            pk=[r['name']for r in current.connection.execute('PRAGMA main.table_info('+table+')')if r['pk']];pk=pk or list(oldrows[0])if oldrows else pk
            if not oldrows:continue
            before={tuple(r[k]for k in pk):r for r in oldrows};after={tuple(r[k]for k in pk):r for r in newrows};ck('keys:'+table,before.keys()==after.keys())
            for k,v in before.items():
                if (table,k)in keys:
                    change=next(c for c in changes if c['table']==table and tuple(c['key'])==k);ck('receipt_before:'+table+str(k),hashlib.sha256(v['record_json'].encode()).hexdigest()==change['before_sha256']);ck('receipt_after:'+table+str(k),hashlib.sha256(after[k]['record_json'].encode()).hexdigest()==change['after_sha256'])
                else:ck('unchanged:'+table+str(k),v==after[k])
        rows=current.connection.execute('SELECT record_json FROM inputs WHERE row_id=?',(EID,)).fetchall();ck('four_latest_inputs65',len(rows)==4 and all(json.loads(r[0])['target']==65 for r in rows));ck('latest_cycle65',json.loads(current.connection.execute('SELECT record_json FROM cycle_records WHERE endpoint_id=?',(EID,)).fetchone()[0])['retention_pct']==65)
        ck('original_v7_still79point3',json.loads(prior.connection.execute('SELECT record_json FROM cycle_records WHERE endpoint_id=?',(EID,)).fetchone()[0])['retention_pct']==79.3)
    with sqlite3.connect((OUT/'cycling_research_v3h.sqlite').as_uri()+'?mode=ro',uri=True)as c:
        ck('research_integrity',c.execute('pragma integrity_check').fetchone()[0]=='ok');ck('research_FKs',not c.execute('pragma foreign_key_check').fetchall());ck('old_green_curve_inactive',c.execute('SELECT approved FROM curves WHERE curve_id=?',('marker_v2:'+EID,)).fetchone()[0]==0)
        for f in[.1,.2]:
            got=c.execute('SELECT target_retention_pct FROM training_windows WHERE endpoint_id=? AND fraction=?',(EID,f)).fetchall();expected=sum(p['cycle_upper']<=f*100000 for p in q['points'])>=3;ck('current_blue_view:'+str(f),len(got)==int(expected)and all(r[0]==65 for r in got))
        ck('no_active_duplicate_endpoint',not c.execute('SELECT endpoint_id,count(*)FROM curves WHERE approved=1 GROUP BY endpoint_id HAVING count(*)>1').fetchall());ck('old_wrong_raw_json_retained',json.loads(c.execute('SELECT raw_json FROM curves WHERE curve_id=?',('marker_v2:'+EID,)).fetchone()[0])==next(r for r in old if r['endpoint_id']==EID))
    for p in receipt['origin_chain']:ck('origin_hash:'+p['path'],sha(ROOT/p['path'])==p['sha256'])
    result=dict(status='passed',checks=len(checks),processed_current_rows_changed=6,canonical_sqlite_sha256=sha(db),research_sqlite_sha256=sha(OUT/'cycling_research_v3h.sqlite'),wrong_green_curve_superseded=True,correct_blue_target_pct=65.,CE_retained_pct=79.3,old70_curve_objects_preserved=True,original_v7_and_chain_unchanged=True,new_model_fits=0,new_formal_endpoint_admissions=0,check_names=checks);write(OUT/'independent_verification.json',result);print(dump({k:v for k,v in result.items()if k!='check_names'}))
def math_close(a,b):return abs(a-b)<=1e-9
if __name__=='__main__':globals()[sys.argv[1]]()
