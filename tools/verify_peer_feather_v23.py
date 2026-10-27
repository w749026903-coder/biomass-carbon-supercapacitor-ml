"""Readonly reproduction; prepare/seal are one-use before the release is immutable."""
from pathlib import Path
from contextlib import closing,redirect_stdout
import collections,csv,io,json,math,sqlite3,sys,xml.etree.ElementTree as E
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tools'))
from extract_peer_feather_v23 import OUT,DB,PARENT,PSHA,CYCLE,CSHA,KEYS,FE,ML,ME,SA,sha,ro,write,number
from extract_palm_kernel_v7 import xml_grid
from extract_source_series_v13 import clean
from transcribe_peer_SI_v23 import extract
from data.literature_v23 import open_literature_database,TARGETS23,FIELDS23
from data.literature_v22 import open_literature_database as old_open,TARGETS22

def verify(prepare=False):
    if prepare:assert not (OUT/'merge_manifest.json').exists()
    spec=json.loads((OUT/'curation_spec.json').read_text('utf8'));checks=[];docs={d['key']:d for d in spec['documents']}
    def ck(n,ok):assert ok,n;checks.append(n)
    ck('parent_SHA',sha(PARENT)==PSHA);ck('current_cycling_protected',sha(CYCLE)==CSHA)
    for r in json.loads((PARENT.parent/'merge_manifest.json').read_text('utf8'))['outputs']:ck('parent_manifest:'+r['path'],sha(ROOT/r['path'])==r['sha256'])
    for r in json.loads((OUT/'protected_inputs.json').read_text('utf8'))['files']:ck('protected:'+r['path'],sha(ROOT/r['path'])==r['sha256'])
    for t in spec['tables']:
        if 'grid'in t:
            r=E.parse(ROOT/docs[t['document']]['path']).getroot();x=next(x for x in r.findall('.//table-wrap')if x.get('id')==t['id']);ck('native_XML:'+t['doi']+t['id'],xml_grid(x)==t['grid'])
    peer=json.loads((OUT/'peer_SI_S1_native_transcription.json').read_text('utf8'))
    ck('all166_native_cells_and_page_coordinates_reproduced',json.loads(json.dumps(extract(),ensure_ascii=False))==peer)
    ck('six_missing_pagebreak_rows_recovered',[r['row_number']for r in peer['rows']if r['provenance']['method']=='pagebreak_first_row_native_words']==[20,43,65,85,116,142])
    for f in spec['figures']:
        root=E.parse(ROOT/docs[KEYS[f['doi']]]['path']).getroot();x=next(x for x in root.findall('.//fig')if x.get('id')==f['xml_id'])
        ck('figure_label_href:'+str(f['doi'])+str(f['figure_number']),clean(x.find('label'))==f['printed_label']and x.find('.//graphic').get('{http://www.w3.org/1999/xlink}href')==f['graphic_href'])
        ck('render_SHA:'+str(f['doi'])+str(f['figure_number']),sha(ROOT/f['render_path'])==f['render_sha256'])
    with closing(ro(DB))as c,closing(ro(PARENT))as p:
        c.row_factory=p.row_factory=sqlite3.Row
        ck('SQLite_integrity',[x[0]for x in c.execute('pragma integrity_check')]==['ok']);ck('foreign_keys',not c.execute('pragma foreign_key_check').fetchall());changed=[]
        for name, in p.execute("select name from sqlite_master where type='table'and name not like'sqlite_%'"):
            if name=='raw_table_queue':
                before={r['table_id']:dict(r)for r in p.execute('select *from raw_table_queue')}
                for r in c.execute('select *from raw_table_queue'):
                    a=dict(r);b=before[r['table_id']]
                    if a!=b:changed.append(r['table_id']);ck('queue_only_state:'+r['table_id'],{k:v for k,v in a.items()if k!='review_state'}=={k:v for k,v in b.items()if k!='review_state'})
            else:ck('all_old_rows_preserved:'+name,{tuple(x)for x in p.execute('select *from "'+name+'"')}<={tuple(x)for x in c.execute('select *from "'+name+'"')})
        ck('only16_target_candidates_changed',len(changed)==16 and set(changed)=={t['raw_table_id']for t in spec['tables']})
        for table,n in [('materials',17),('material_facts',147),('capacitance_observations',14),('outcome_observations_v3',22),('synthesis_stages_v3',9),('test_candidates',0),('reviewed_sources',4),('reviewed_tables',20),('scientific_issues',5)]:ck('delta:'+table,c.execute('select count(*)from '+table).fetchone()[0]-p.execute('select count(*)from '+table).fetchone()[0]==n)
        for r in c.execute('select *from cell_extractions_v23'):
            raw=json.loads(c.execute('select cells_json from transcribed_rows where table_key=?and row_ordinal=?',(r['table_key'],r['row_ordinal'])).fetchone()[0])[r['column_ordinal']]
            table,pk={'fact':('material_facts','fact_id'),'capacitance':('capacitance_observations','observation_id'),'response':('outcome_observations_v3','outcome_id')}[r['kind']]
            v=c.execute('select *from '+table+' where '+pk+'=?',(r['record_id'],)).fetchone();v=json.loads(v['record_json'])if r['kind']=='response'else dict(v)
            ck('literal_cell:'+r['kind']+r['record_id'],v['raw_value']==raw);ck('numeric_cell:'+r['kind']+r['record_id'],v['value']==number(raw))
            if r['kind']=='fact':
                doc=c.execute('select document_key from table_source_links where table_key=?',(r['table_key'],)).fetchone()[0];ck('fact_SHA:'+r['record_id'],v['source_sha256']==docs[doc]['sha256'])
        for r in c.execute('select *from secondary_rows_v23'):
            x=json.loads(r['record_json']);cells=json.loads(c.execute('select cells_json from transcribed_rows where table_key=?and row_ordinal=?',(r['table_key'],r['row_ordinal'])).fetchone()[0]);ck('secondary_literal:'+r['row_id'],x['cells']==cells and not r['training_eligible']and not x['primary_protocol_verified'])
        count=lambda t:c.execute('select count(*)from '+t).fetchone()[0]
        totals={k:count(t)for k,t in [('cumulative_reviewed_source_publications','source_scope_decisions'),('cumulative_materials','materials'),('cumulative_selected_material_cells','material_facts'),('actual_distinct_reviewed_table_keys','reviewed_tables'),('extraction_units_v3_count','extraction_units_v3'),('capacitance_records','capacitance_observations'),('cycling_candidates','test_candidates'),('scientific_issues','scientific_issues'),('synthesis_materials','synthesis_stages_v3'),('response_outcomes','outcome_observations_v3')]}
        totals['cumulative_numeric_material_facts']=c.execute('select count(*)from material_facts where value is not null').fetchone()[0];totals['unreported_material_cells']=count('material_facts')-totals['cumulative_numeric_material_facts'];totals['numeric_capacitance_values']=c.execute('select count(*)from capacitance_observations where value is not null').fetchone()[0]
        ck('fixed_queue959_715',count('raw_table_queue')==959 and c.execute("select count(*)from raw_table_queue where review_state='automatic_candidate_unreviewed'").fetchone()[0]==715)
        ck('no_full_source_completion',not c.execute('select *from source_scope_decisions where full_source_review_complete=1').fetchall())
    exports=[];preflight={}
    with open_literature_database(DB,sha(DB))as d,old_open(PARENT,PSHA)as old:
        before={r['fact_id']:r for r in old.facts()}
        for r in d.facts():
            if r['fact_id']in before:ck('old_fact_API:'+str(r['fact_id']),r==before[r['fact_id']])
        for t in TARGETS22:ck('v22_matrix_unchanged:'+t,d.batch22_matrix(t)==old.batch22_matrix(t))
        for profile in ['3e','2e_device','native_mineral_3e','2e_author_factor2']:
            now={r['observation_id']:r for r in d.auxiliary_gcd(profile)}
            for r in old.auxiliary_gcd(profile):ck('old_aux:'+r['observation_id'],r==now[r['observation_id']])
        for t,n in zip(TARGETS23,[2,4,1]):
            rows=d.batch23_inputs(t);m=d.batch23_matrix(t);ck('purpose_count:'+t,len(rows)==n==len(m['y']));ck('mask:'+t,m['missing_mask']==[[v is None for v in x]for x in m['X']]);ck('purpose_unique_tests:'+t,len(set(m['physical_test_groups']))==n)
            ck('no_fit_or_imputation:'+t,not m['imputed']and m['estimators_fitted']==0 and not m['training_authorized'])
            for g in set(m['groups']):ck('source_weights:'+t+g,math.isclose(sum(w for w,gg in zip(m['sample_weight'],m['groups'])if gg==g),1))
            preflight[t]=dict(rows=n,source_families=m['source_families'],features=len(FIELDS23),missing_cells=sum(map(sum,m['missing_mask'])),model_fits=0);exports.append((t,rows,m))
        ck('ordinary_only_two_Cu_free_controls',{(r['sample_name'],r['value'])for r in d.batch23_inputs()}=={('PS-3-0',277.79),('M-3-0',438.49)})
        ck('M325_competing_values_retained',{r['value']for r in d.capacitances(FE,'M-3-25')if r['system']=='3E'}=={581.74,587.14})
        ck('M325_competing_target_not_selected',all(r['sample_name']!='M-3-25'for r in d.batch23_inputs(TARGETS23[1])))
        ck('no_8mg_loading_assumed',all(r['conditions'].get('mass_loading_mg_cm2')is None for r in d.capacitances(FE)))
        f=d.canonical_material_features_v13(FE,'M-3-25');ck('O_proxy_not_XPS_or_measured_O','author_O_by_100_minus_CHN_proxy_pct'in f['values']and not any(k.startswith('XPS')for k in f['values']))
        f=d.canonical_material_features_v13(ML,'HDP-AC');ck('Raman_direction_variants_masked',not any(k.startswith('Raman')for k in f['values'])and f['values']['BET_surface_area_m2_g']==33)
        ck('HDP_485_current_unbound',next(r for r in d.capacitances(ML)if r['value']==485)['current_A_g']is None)
        ck('HDP_not_auxiliary',not any(r['doi']==ML for r in d.auxiliary_gcd()))
        ck('prior_work_family_quarantined',d.isolation_group(ML)==d.isolation_group('10.1002/asia.202400622')and d.is_quarantined_source(ML,['10.1002/asia.202400622']))
        sec=d.secondary_inspection_rows();ck('309_secondary_not_experiments',len(sec)==309 and all(not r['training_input_ready']for r in sec))
        ck('peer_curator_heldout_quarantines166',all(r['quarantined_for_heldout']for r in d.secondary_inspection_rows(ML,[ML])))
        rr=d.secondary_inspection_rows(ML,['10.1016/j.biortech.2015.07.100']);ck('cited_source_heldout_includes_both_duplicates',[r['record']['row_number']for r in rr if r['quarantined_for_heldout']]==[164,89])
        try:d.peer_compilation_matrix();blocked=False
        except ValueError:blocked=True
        ck('peer_matrix_refused',blocked)
        ck('ordinary194_27',len(d.auxiliary_gcd())==194 and len({r['doi']for r in d.auxiliary_gcd()})==27)
        graph=d.expanded_graph_3e_matrix();ck('expanded363_27',len(graph['y'])==363 and graph['source_families']==27)
        ck('two_old_cycle_links_only',{r['record']['existing_endpoint_id']for r in d.batch23_cycle_identity_links()}=={'legacy:SRC126_CY01','legacy:R001_CY01'})
        # Every own representation is held out with its entire source/prior-work family.
        payload=[dict(kind='fact',group='doi:'+r['doi'])for r in d.facts()]+[dict(kind='capacitance',group=r['source_group'])for r in d.capacitances()]+[dict(kind='registration',group='doi:'+r['doi'])for r in d.materials()]
        for t,rows,m in exports:payload.extend(dict(kind='v23_input',group=r['source_group'])for r in rows)
        families={}
        for r in payload:r['family']=d.isolation_group(r['group'])
        for g in sorted({r['family']for r in payload}):
            rr=[r for r in payload if r['family']==g];ck('whole_source_holdout:'+g,all(d.is_quarantined_source(r['group'],[g])for r in rr));families[g]=dict(collections.Counter(r['kind']for r in rr))
    from data.cycling_db import open_database
    with open_database()as cycle:
        ck('cycle286_fixed39_pending37',len(cycle.fetch('all_review').rows)==286 and len(cycle.reviewed_pending_batch())==37 and len(cycle.reviewed_pending_batch(True))==41)
        ck('zero_cycle_change',sha(CYCLE)==CSHA)
    summary=json.loads((PARENT.parent/'summary.json').read_text('utf8'))
    for k in list(summary):
        if k.startswith('new_')and isinstance(summary[k],int):summary[k]=0
        elif k.startswith('new_')and isinstance(summary[k],list):summary[k]=[]
    summary.update(totals);summary.update(new_materials=17,new_material_facts=147,new_numeric_material_facts=147,new_null_material_facts=0,new_capacitance_reports=14,new_response_records=22,new_source_response_records=22,new_source_scopes=4,new_own_main_tables=3,new_mixed_own_foreign_main_tables=1,new_raw_candidates_touched=16,raw_candidates_touched=244,raw_candidates_untouched=715,reviewed_table_units=275,reviewed_evidence_units=530,distinct_database_table_keys=516,database_extraction_units_v3=499,reviewed_evidence_units_definition='530declared;516actualkeys/499extractionunits;275physicaltables. Thisbatch16physicaltablesinclude9review,2MLvariabletables,3ownFeathertables,2SIpeercompilation/metrics. TableS1p2..8isonephysicaltable.',auxiliary_aqueous_3e_GCD_rows=194,auxiliary_ordinary_3e_DOI_groups=27,auxiliary_purpose_reviewed_input_rows=210,auxiliary_independent_DOI_groups=28,expanded_3e_with_graph_rows=363,expanded_3e_with_graph_DOI_groups=27,new_3e_purpose_inputs=2,new_separate_purpose_rows=[2,4,1],new_existing_cycle_identity_links=2,new_figure_scope_inspections=17,new_peer_secondary_rows=166,new_review_secondary_context_rows=143,new_model_fits=0,scope_note='Fourexistingpublications;147ownpretestfacts,14capacityreportswith2unreporteddashes,7purposeinputs(2ordinarycontrols,4Cu3E,1Cu2E). 309secondaryrows are retrievalcontext,notnewqualifiedexperiments. PeerS1duplicates/collisionsretained; priorHDPandM325conflictshold. No cyclingadmission/fit/fullsourcecompletion.')
    report=dict(status='passed',database_sha256=sha(DB),parent_sha256=PSHA,check_count=len(checks),checks=checks,new_cycle_admissions=0,new_model_fits=0,scientific_goal_complete=False)
    chain=dict(status='passed',own_representation_payloads=len(payload),source_families=len(families),family_counts=families,secondary_rows=309,secondary_training_admissions=0,secondary_policy='Eachcitedsource andcurator quarantine checked; no secondary trainingmatrix exists',current_pending=37,fixed_scope=39,resolved=2,new_model_fits=0,scope='Ownrepresentationsnotindependentexperiments; historicalfullchain checkedbyunchangedv027verifier')
    for name,value in [('summary',summary),('verification',report),('model_inputs_preflight',preflight),('chain_verification',chain)]:
        if prepare:write(OUT/(name+'.json'),value)
        else:assert json.loads((OUT/(name+'.json')).read_text('utf8'))==value,name
    for t,rows,m in exports:
        buf=io.StringIO(newline='');w=csv.writer(buf,lineterminator='\n');w.writerow(['observation_id','doi','sample','capacitance_F_g','current_A_g','source_family_group','source_weight']+FIELDS23)
        for i,r in enumerate(rows):w.writerow([r['observation_id'],r['doi'],r['sample_name'],r['value'],r['current_A_g'],r['source_family_group'],m['sample_weight'][i]]+m['X'][i])
        p=OUT/('purpose_'+t+'.csv')
        if prepare:p.write_text(buf.getvalue(),encoding='utf-8-sig',newline='')
        else:assert p.read_text('utf-8-sig')==buf.getvalue()
    if (OUT/'merge_manifest.json').exists():
        for r in json.loads((OUT/'merge_manifest.json').read_text('utf8'))['outputs']:assert sha(ROOT/r['path'])==r['sha256'],r['path']
    print(json.dumps({k:v for k,v in report.items()if k!='checks'}))

def seal():
    assert not(OUT/'merge_manifest.json').exists();verify(False)
    historical=json.loads((OUT/'historical_v027_verification.json').read_text('utf8'));assert historical['status']=='passed'
    paths=[p for p in OUT.rglob('*')if p.is_file()]+[ROOT/'data/literature_v23.py',ROOT/'tools/extract_peer_feather_v23.py',ROOT/'tools/transcribe_peer_SI_v23.py',Path(__file__).resolve()]
    write(OUT/'merge_manifest.json',dict(version='literature_pool_v23',parent_sha256=PSHA,outputs=[dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p),bytes=p.stat().st_size)for p in sorted(paths)],model_fits=0,new_cycle_admissions=0,scientific_goal_complete=False))
    write(ROOT/'data/current_literature.json',dict(version='literature_pool_v23',directory=OUT.relative_to(ROOT).as_posix(),database_file=DB.name,sha256=sha(DB),api_module='data.literature_v23',scope='Own147facts/14capacityreports and7qualifiedpurposeinputs;309secondaryretrievalrowsseparate. ZeroCucontrolsordinary;Cucompositeseparate;HDPprioroverlapandM325capacitycompetitionremainheld. No cyclingadmission/fitting/fullsourcecompletion.'))
if __name__=='__main__':
    mode=sys.argv[1]
    if mode=='prepare':verify(True)
    elif mode=='verify':verify(False)
    elif mode=='seal':seal()
    else:raise SystemExit(mode)
