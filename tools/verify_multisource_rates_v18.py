"""Verify original pixel evidence, current figure identities and all parent rows."""
from pathlib import Path
from contextlib import closing
import collections,csv,json,math,sqlite3,sys,xml.etree.ElementTree as E
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tools'))
from extract_multisource_rates_v18 import OUT,DB,PARENT,PSHA,IMAGES,AXES,CURRENTS,NPC,RH,MIX,sha,write,ro,capture
from data.literature_v18 import open_literature_database,FIELDS17

def verify(prepare=False):
    if prepare:assert not(OUT/'merge_manifest.json').exists()
    digest=sha(DB);checks=[]
    def ck(n,b):assert b,n;checks.append(n)
    s=json.loads((OUT/'curation_spec.json').read_text('utf8'));recomputed={r['reading_id']:r for r in capture()}
    for r in s['readings']:
        for k,v in recomputed[r['reading_id']].items():ck('pixel:'+r['reading_id']+':'+k,r[k]==v)
        if r['y_value']is None:ck('occlusion_not_guessed:'+r['reading_id'],r['y_lower_bound']is None and r['y_upper_bound']is None and not r['ready_for_point_purpose'])
        else:ck('bounded:'+r['reading_id'],r['y_lower_bound']<=r['y_value']<=r['y_upper_bound'])
    ck('126raw118numeric8unresolved',len(s['readings'])==126 and sum(r['y_value']is not None for r in s['readings'])==118)
    ck('114nominal12duplicates',sum(r['primary_for_nominal_condition']for r in s['readings'])==114)
    for r in json.loads((OUT/'protected_inputs.json').read_text('utf8'))['files']:ck('protected:'+r['path'],sha(ROOT/r['path'])==r['sha256'])
    for r in json.loads((PARENT.parent/'merge_manifest.json').read_text('utf8'))['outputs']:ck('parent_manifest:'+r['path'],sha(ROOT/r['path'])==r['sha256'])
    ck('parent_SHA',sha(PARENT)==PSHA)
    with closing(ro(PARENT))as p,closing(ro(DB))as c:
        p.row_factory=c.row_factory=sqlite3.Row;ck('integrity',[r[0]for r in c.execute('pragma integrity_check')]==['ok']);ck('foreign_keys',not c.execute('pragma foreign_key_check').fetchall())
        mutable={'source_documents','reviewed_tables','table_source_links','transcribed_rows','transcription_origins_v7','extraction_units_v3','curve_samples_v8','capacitance_observations','scientific_issues'}
        for name in [r[0]for r in p.execute("select name from sqlite_master where type='table'and name not like'sqlite_%'")]:
            before={tuple(r)for r in p.execute('select *from "'+name+'"')};after={tuple(r)for r in c.execute('select *from "'+name+'"')};ck('old_rows_exact:'+name,before<=after if name in mutable else before==after)
        for t,n in [('source_documents',3),('reviewed_tables',5),('curve_samples_v8',126),('capacitance_observations',126),('scientific_issues',1)]:ck('delta:'+t,c.execute('select count(*)from '+t).fetchone()[0]-p.execute('select count(*)from '+t).fetchone()[0]==n)
        ck('raw959800unchanged',c.execute('select count(*)from raw_table_queue').fetchone()[0]==959 and c.execute("select count(*)from raw_table_queue where review_state='automatic_candidate_unreviewed'").fetchone()[0]==800)
        ck('4binding_corrections9native_labels',c.execute('select count(*)from source_binding_corrections_v18').fetchone()[0]==4 and c.execute('select count(*)from figure_identity_resolution_v18').fetchone()[0]==9)
        for r in c.execute('select *from figure_identity_resolution_v18'):
            rec=json.loads(r['record_json']);root=E.parse(ROOT/rec['source_XML']).getroot();f=next(f for f in root.findall('.//fig')if f.get('id')==rec['xml_id']);label=''.join(f.find('label').itertext());href=f.find('.//graphic').get('{http://www.w3.org/1999/xlink}href')
            ck('native_label_href:'+r['document_key'],label==r['printed_label']==rec['printed_label']and href==rec['href']and sha(ROOT/rec['path'])==rec['sha256'])
        ck('scheme_not_Figure1',c.execute("select printed_label from figure_identity_resolution_v18 where document_key='Starch17_Fig1'").fetchone()[0]=='Scheme 1')
        for r in c.execute('select a.*,p.record_json from capacitance_observations a join purpose_reviews_v18 p using(observation_id)'):
            rr=json.loads(r['record_json']);ck('db_binding:'+r['observation_id'],r['value']==rr['y_value']and r['current_A_g']==rr['x_value']and r['training_eligible']==0)
            ck('db_missing_status:'+r['observation_id'],('occluded'in r['status'])==(r['value']is None))
    from data.literature_v17 import open_literature_database as oldopen,TARGETS17
    mode_counts={};exports=[]
    with open_literature_database(DB,digest)as d,oldopen(PARENT,PSHA)as old:
        ck('13fact_current_paths_fixed',sum(r.get('current_source_binding_correction_v18',False)for r in d.facts())==13)
        ck('16response_current_paths_fixed',sum('current_provenance_v18'in r for r in d.outcomes())==16)
        oldfacts={r['fact_id']:r for r in old.facts()}
        for r in d.facts():
            if r.get('current_source_binding_correction_v18'):
                ck('corrected_fact_unchanged_value:'+str(r['fact_id']),r['value']==oldfacts[r['fact_id']]['value']and r['raw_value']==oldfacts[r['fact_id']]['raw_value']and r['source_path'].endswith('molecules-29-02532-g003.jpg')and sha(ROOT/r['source_path'])==r['source_sha256'])
                ck('original_bad_binding_kept:'+str(r['fact_id']),r['original_provenance_v17']['source_path'].endswith('g002.jpg'))
            else:ck('other_fact_payload_exact:'+str(r['fact_id']),r==oldfacts[r['fact_id']])
        for target in TARGETS17:ck('v17_matrix_exact:'+target,d.batch17_matrix(target)==old.batch17_matrix(target))
        for p in ['3e','2e_device','native_mineral_3e','2e_author_factor2']:
            a=d.auxiliary_gcd(p);b=old.auxiliary_gcd(p);ck('ordinary_targets_IDs_unchanged:'+p,[(r['observation_id'],r['value'],r['material_features'])for r in a]==[(r['observation_id'],r['value'],r['material_features'])for r in b])
        for mode in ['author_exact','point_mixed','figure_only']:ck('v16_exact:'+mode,d.batch16_rate_matrix(mode)==old.batch16_rate_matrix(mode))
        ck('v15_exact',d.batch15_matrix()==old.batch15_matrix())
        for mode in ['author_exact','point_mixed','interval_mixed','figure_only']:ck('v14_exact:'+mode,d.furfural_rate_matrix(mode)==old.furfural_rate_matrix(mode))
        for purpose,wants in [('ordinary_3e',[3,97,103]),('native_silica_3e',[0,11,11])]:
            for mode,n in zip(['author_exact','point_mixed','figure_only'],wants):
                rows=d.batch18_rate_inputs(mode,purpose);ck('counts:'+purpose+mode,len(rows)==n);mode_counts[purpose+'_'+mode]=dict(rows=n,missing_targets=sum(r['target_value']is None for r in rows),source_families=len({r['source_family_group']for r in rows}))
                if mode=='figure_only'and purpose=='ordinary_3e':
                    try:d.batch18_rate_matrix(mode,purpose)
                    except ValueError:ck('reject_occluded_point_matrix',True)
                    else:raise AssertionError('Occluded point target accepted')
                else:
                    m=d.batch18_rate_matrix(mode,purpose);ck('weights_masks:'+purpose+mode,all(math.isclose(sum(w for g,w in zip(m['groups'],m['sample_weight'])if g==family),1)for family in set(m['groups']))and all((v is None)==mask for x,ms in zip(m['X'],m['missing_mask'])for v,mask in zip(x,ms)))
                    ck('no_fit:'+purpose+mode,not m['training_authorized']and m['estimators_fitted']==0 and not m['imputed'])
                    if mode=='point_mixed':exports.append((purpose,rows,m))
        ck('3anchors_all_visible',len({r['author_exact_observation_id']for r in s['readings']if r['author_exact_observation_id']})==3 and all(r['author_anchor_within_graph_envelope']for r in s['readings']if r['author_exact_observation_id']))
        points=d.batch18_rate_inputs('point_mixed');ck('no_native_residue_in_ordinary',not any(r['sample_name']=='RH-1000'for r in points))
        ck('starch1point5_not2',all(r['current_A_g']in [.5,1,1.5,3,5,10]for r in points if r['doi']==NPC))
        ck('Rice_BET_stays_missing',all(r['matrix_feature_values'].get('BET_surface_area_m2_g')is None for r in points if r['doi']==RH))
        ex=d.expanded_graph_3e_inputs();em=d.expanded_graph_3e_matrix();ck('expanded353_22families',len(ex)==len(em['y'])==353 and len(set(em['groups']))==22)
        previous=old.expanded_graph_3e_inputs();ck('previous259_targets_exact',[(r['observation_id'],r['target_value'])for r in ex[:259]]==[(r['observation_id'],r['target_value'])for r in previous])
        ck('new94_bounded_only',len(ex[259:])==94 and all(r['target_value_kind']=='bounded_original_figure'for r in ex[259:]))
        review=d.batch18_cycle_reviews()[0]['record'];ck('ABPC_config_not_guessed',review['configuration']['selected_system']is None and review['configuration']['selected_cycle_voltage']is None and not review['formal_admission'])
        ck('raw_ABPC_candidate_kept',next(r for r in d.tests()if r['candidate_id']=='LP17_ABPC4')['record']==next(r for r in old.tests()if r['candidate_id']=='LP17_ABPC4')['record'])
        for purpose,rows,m in exports:
            path=OUT/('rate_inputs_v18_'+purpose+'.csv');cols=['observation_id','doi','sample','target_F_g','target_lower_F_g','target_upper_F_g','target_kind','source_family','weight','nominal_report_group','source_path','source_sha256']+FIELDS17
            if prepare:
                with path.open('w',encoding='utf-8-sig',newline='')as stream:
                    w=csv.DictWriter(stream,fieldnames=cols);w.writeheader()
                    for i,r in enumerate(rows):w.writerow(dict(observation_id=r['observation_id'],doi=r['doi'],sample=r['sample_name'],target_F_g=r['target_value'],target_lower_F_g=r['target_lower_bound'],target_upper_F_g=r['target_upper_bound'],target_kind=r['target_value_kind'],source_family=m['groups'][i],weight=m['sample_weight'][i],nominal_report_group=r['nominal_report_group'],source_path=r['source_path'],source_sha256=r['source_sha256'],**dict(zip(FIELDS17,m['X'][i]))))
            with path.open(encoding='utf-8-sig',newline='')as stream:export=list(csv.DictReader(stream))
            ck('CSV:'+purpose,len(export)==len(rows)and all(float(e['target_F_g'])==r['target_value']and all((e[f]=='')==(v is None)for f,v in zip(FIELDS17,m['X'][i]))for i,(e,r)in enumerate(zip(export,rows))))
        summary=json.loads((PARENT.parent/'summary.json').read_text('utf8'))
        for k in list(summary):
            if k.startswith('new_')and isinstance(summary[k],int):summary[k]=0
        summary.update(capacitance_records=1100,numeric_capacitance_values=1088,null_capacitance_cells=12,occluded_capacitance_cells=8,reviewed_evidence_units=398,actual_distinct_reviewed_table_keys=384,distinct_database_table_keys=384,extraction_units_v3_count=367,database_extraction_units_v3=367,reviewed_evidence_units_definition='398declaredunits,384actualtablekeys/367extractionunits;194physicaltables unchanged.5newunits are figure transcriptions.',new_bounded_curve_samples=126,new_numeric_curve_samples=118,new_occluded_curve_samples=8,new_capacitance_reports=126,new_nominal_graph_conditions=114,new_approximate_conditions_beyond_author_points=94,new_separate_native_silica_conditions=11,cumulative_bounded_curve_samples=403,cumulative_numeric_curve_samples=393,cumulative_occluded_curve_samples=8,cumulative_curve_groups=61,curve_sampling_panels=18,scientific_issues=173,expanded_3e_with_graph_rows=353,expanded_3e_with_graph_DOI_groups=22,current_binding_corrections=4,current_corrected_fact_provenance=13,current_corrected_response_provenance=16,scope_note='Three existing sources deepened:126captures/114nominalconditions,118numeric/8occluded captures;97ordinary pointinputs(3oldauthor+94newgraph) and11native-silica separate;4versioned source-binding corrections. No cycleadmission/fullsourcecompletion/fit.')
    ck('readonly_SHA',sha(DB)==digest)
    report=dict(status='passed',database_sha256=digest,check_count=len(checks),checks=sorted(checks),scientific_goal_complete=False,formal_cycling_admissions=0,model_fits=0)
    for name,value in [('summary',summary),('verification',report),('model_inputs_preflight',mode_counts)]:
        if prepare:write(OUT/(name+'.json'),value)
        else:assert json.loads((OUT/(name+'.json')).read_text('utf8'))==value,name
    if not prepare and(OUT/'merge_manifest.json').exists():
        for r in json.loads((OUT/'merge_manifest.json').read_text('utf8'))['outputs']:assert sha(ROOT/r['path'])==r['sha256'],r['path']
    print(json.dumps({k:v for k,v in report.items()if k!='checks'},ensure_ascii=False))

def seal():
    assert not(OUT/'merge_manifest.json').exists();verify(False)
    from verify_multisource_chain_v18 import run
    run(False)
    paths=[p for p in OUT.rglob('*')if p.is_file()]+[ROOT/'data/literature_v18.py',ROOT/'tools/extract_multisource_rates_v18.py',ROOT/'tools/verify_multisource_rates_v18.py',ROOT/'tools/verify_multisource_chain_v18.py']
    write(OUT/'merge_manifest.json',dict(version='literature_pool_v18',parent_sha256=PSHA,outputs=[dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p),bytes=p.stat().st_size)for p in sorted(paths)],formal_cycling_admissions=0,model_fits=0,scientific_goal_complete=False))
    write(ROOT/'data/current_literature.json',dict(version='literature_pool_v18',directory=OUT.relative_to(ROOT).as_posix(),database_file=DB.name,sha256=sha(DB),api_module='data.literature_v18',scope='Three-source fivepanel rates:94new ordinary graphical conditions and11native-silica purpose;8occluded rawcaptures retained;4versioned evidence-binding corrections;no cyclingadmission/fullsourcecompletion/fit'))

if __name__=='__main__':
    if len(sys.argv)!=2 or sys.argv[1]not in ['prepare','verify','seal']:raise SystemExit('prepare/seal before release only; verify readonly')
    if sys.argv[1]=='seal':seal()
    else:verify(sys.argv[1]=='prepare')
