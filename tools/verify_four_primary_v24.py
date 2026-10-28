"""Source/role/lineage verification; sealed releases are readonly."""
from pathlib import Path
from contextlib import closing
import collections,csv,io,json,math,sqlite3,sys,xml.etree.ElementTree as E,re
import pdfplumber
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tools'))
from extract_four_primary_v24 import OUT,DB,PARENT,PSHA,CYCLE,CSHA,FR,FW,NS,HP,KEYS,sha,ro,write,number
from extract_palm_kernel_v7 import xml_grid
from extract_source_series_v13 import clean
from data.literature_v24 import open_literature_database,TARGETS24,FIELDS24
from data.literature_v23 import open_literature_database as old_open,TARGETS23
from data.cycling_identity import cycling_endpoints_by_doi

def verify(prepare=False):
    if prepare:assert not(OUT/'merge_manifest.json').exists()
    spec=json.loads((OUT/'curation_spec.json').read_text('utf8'));docs={d['key']:d for d in spec['documents']};checks=[]
    def ck(n,ok):assert ok,n;checks.append(n)
    ck('parent_SHA',sha(PARENT)==PSHA);ck('cycling_SHA',sha(CYCLE)==CSHA)
    for r in json.loads((PARENT.parent/'merge_manifest.json').read_text('utf8'))['outputs']:ck('parent_output:'+r['path'],sha(ROOT/r['path'])==r['sha256'])
    for r in json.loads((OUT/'protected_inputs.json').read_text('utf8'))['files']:ck('protected:'+r['path'],sha(ROOT/r['path'])==r['sha256'])
    for t in spec['tables']:
        r=E.parse(ROOT/docs[t['document']]['path']).getroot();x=next(x for x in r.findall('.//table-wrap')if x.get('id')==t['id']);ck('native_grid:'+t['doi']+t['id'],xml_grid(x)==t['grid'])
    for f in spec['figures']:
        r=E.parse(ROOT/docs[KEYS[f['doi']]]['path']).getroot();x=next(x for x in r.findall('.//fig')if x.get('id')==f['xml_id'])
        ck('figure_identity:'+f['doi']+str(f['figure_number']),clean(x.find('label'))==f['printed_label']and x.find('.//graphic').get('{http://www.w3.org/1999/xlink}href')==f['href'])
        ck('figure_SHA:'+f['doi']+str(f['figure_number']),sha(ROOT/f['path'])==f['sha256']and f['scope_visually_inspected']and not f['full_waveform_extracted'])
    inv=json.loads((OUT/'figure_scope_inventory.json').read_text('utf8'))
    ck('wheat_figures_not_faked',len([x for x in inv if x['doi']==HP])==9 and all(not x['path']and not x['scope_visually_inspected']for x in inv if x['doi']==HP))
    with pdfplumber.open(ROOT/docs['FW24_SI']['path'])as p:
        text=p.pages[1].extract_text();ck('own_SI_last_row_bound',bool(re.search(r'FWCA-4.*1470.*6M KOH.*314\(1\.0 A/g\).*This work',text)))
    with closing(ro(DB))as c,closing(ro(PARENT))as p:
        c.row_factory=p.row_factory=sqlite3.Row;ck('integrity',[r[0]for r in c.execute('pragma integrity_check')]==['ok']);ck('foreign_keys',not c.execute('pragma foreign_key_check').fetchall());changed=[]
        for name, in p.execute("select name from sqlite_master where type='table'and name not like'sqlite_%'"):
            if name=='raw_table_queue':
                before={r['table_id']:dict(r)for r in p.execute('select *from raw_table_queue')}
                for r in c.execute('select *from raw_table_queue'):
                    a=dict(r);b=before[r['table_id']]
                    if a!=b:changed.append(r['table_id']);ck('queue_only_state:'+r['table_id'],{k:v for k,v in a.items()if k!='review_state'}=={k:v for k,v in b.items()if k!='review_state'})
            else:ck('old_rows_unchanged:'+name,{tuple(r)for r in p.execute('select *from "'+name+'"')}<={tuple(r)for r in c.execute('select *from "'+name+'"')})
        ck('only_eight_native_candidates',len(changed)==8 and set(changed)=={t['raw_table_id']for t in spec['tables']})
        for table,key in [('materials','materials'),('material_facts','facts'),('capacitance_observations','caps'),('outcome_observations_v3','responses'),('synthesis_stages_v3','synthesis'),('test_candidates','candidates'),('reviewed_sources','sources'),('scientific_issues','decisions')]:ck('delta:'+table,c.execute('select count(*)from '+table).fetchone()[0]-p.execute('select count(*)from '+table).fetchone()[0]==len(spec[key]))
        ck('26_new_evidence_units',c.execute('select count(*)from reviewed_tables').fetchone()[0]-p.execute('select count(*)from reviewed_tables').fetchone()[0]==26)
        for r in c.execute('select *from cell_extractions_v24'):
            raw=json.loads(c.execute('select cells_json from transcribed_rows where table_key=?and row_ordinal=?',(r['table_key'],r['row_ordinal'])).fetchone()[0])[r['column_ordinal']]
            table,pk={'fact':('material_facts','fact_id'),'capacitance':('capacitance_observations','observation_id'),'response':('outcome_observations_v3','outcome_id')}[r['kind']];v=c.execute('select *from '+table+' where '+pk+'=?',(r['record_id'],)).fetchone();v=json.loads(v['record_json'])if r['kind']=='response'else dict(v)
            ck('raw_cell:'+r['kind']+r['record_id'],raw==v['raw_value']);ck('numeric_cell:'+r['kind']+r['record_id'],number(raw)==v['value'])
            if r['kind']=='fact':
                d=c.execute('select document_key from table_source_links where table_key=?',(r['table_key'],)).fetchone()[0];ck('fact_SHA:'+r['record_id'],v['source_sha256']==docs[d]['sha256'])
        ct=lambda t:c.execute('select count(*)from '+t).fetchone()[0]
        totals={k:ct(t)for k,t in [('cumulative_reviewed_source_publications','source_scope_decisions'),('cumulative_materials','materials'),('cumulative_selected_material_cells','material_facts'),('actual_distinct_reviewed_table_keys','reviewed_tables'),('extraction_units_v3_count','extraction_units_v3'),('capacitance_records','capacitance_observations'),('cycling_candidates','test_candidates'),('scientific_issues','scientific_issues'),('synthesis_materials','synthesis_stages_v3'),('response_outcomes','outcome_observations_v3')]}
        totals['cumulative_numeric_material_facts']=c.execute('select count(*)from material_facts where value is not null').fetchone()[0];totals['unreported_material_cells']=ct('material_facts')-totals['cumulative_numeric_material_facts'];totals['numeric_capacitance_values']=c.execute('select count(*)from capacitance_observations where value is not null').fetchone()[0]
        ck('numeric_and_registration_counts',totals['cumulative_selected_material_cells']==4656 and totals['cumulative_numeric_material_facts']==4459 and totals['cumulative_materials']==447)
        ck('no_source_complete',not c.execute('select *from source_scope_decisions where full_source_review_complete=1').fetchall());ck('959_queue_707_untouched',ct('raw_table_queue')==959 and c.execute("select count(*)from raw_table_queue where review_state='automatic_candidate_unreviewed'").fetchone()[0]==707)
    exports=[];preflight={}
    with open_literature_database(DB,sha(DB))as d,old_open(PARENT,PSHA)as old:
        oldfacts={r['fact_id']:r for r in old.facts()}
        for r in d.facts():
            if r['fact_id']in oldfacts:ck('old_fact_API:'+str(r['fact_id']),r==oldfacts[r['fact_id']])
        for t in TARGETS23:ck('old_v23_matrix:'+t,d.batch23_matrix(t)==old.batch23_matrix(t))
        ck('peer_secondary309_unchanged',d.secondary_inspection_rows()==old.secondary_inspection_rows()and d.peer_metrics()==old.peer_metrics())
        for p in ['3e','2e_device','native_mineral_3e','2e_author_factor2']:
            now={r['observation_id']:r for r in d.auxiliary_gcd(p)}
            for r in old.auxiliary_gcd(p):ck('old_aux:'+r['observation_id'],r==now[r['observation_id']])
        for t,n in zip(TARGETS24,[11,1,4,2]):
            rows=d.batch24_inputs(t);m=d.batch24_matrix(t);ck('purpose_count:'+t,len(rows)==n==len(m['y']));ck('masks:'+t,m['missing_mask']==[[v is None for v in x]for x in m['X']]);ck('unique_tests:'+t,len(set(m['physical_test_groups']))==n)
            ck('no_fit_imputation:'+t,not m['imputed']and m['estimators_fitted']==0 and not m['training_authorized'])
            for g in sorted(set(m['groups'])):ck('source_weights:'+t+g,math.isclose(sum(w for w,gg in zip(m['sample_weight'],m['groups'])if gg==g),1))
            preflight[t]=dict(rows=n,source_families=m['source_families'],features=len(FIELDS24),missing_cells=sum(map(sum,m['missing_mask'])),model_fits=0);exports.append((t,rows,m))
        ck('FR_four_inspection_not_inputs',len(d.batch24_inspection_rows())==4 and not any(r['doi']==FR for r in d.auxiliary_gcd())and all(not r['training_input_ready']and r['concentration_mol_L']is None and r['conditions']['concentration_claims_mol_L']==[1,6]for r in d.batch24_inspection_rows()))
        try:d.batch24_matrix('furfural_concentration_disputed_inspection');refused=False
        except ValueError:refused=True
        ck('FR_matrix_refused',refused)
        f=d.canonical_material_features_v13(FR,'FRPCK-Urea');ck('FR_XPS_basis_and_ratio_masked','XPS_N_reported_pct_basis_unspecified'not in f['values']and'author_mesopore_volume_fraction_pct'not in f['values']and f['values']['XPS_N1s_pyridinic_envelope_pct']==35.99)
        f=d.canonical_material_features_v13(FW,'FWCA-4');ck('FW_units_and_raw_stage',f['values']['total_pore_volume_cm3_g']==.634 and f['values']['HK_micropore_volume_cm3_g']==.4 and 'raw_prose_pore_volume_m3_g'not in f['values']and not any(k.startswith('raw_bulk')or k.startswith('raw_dry')for k in f['values']))
        fw=[r for r in d.batch24_inputs()if r['doi']==FW];ck('FW_detailed_precision_314point4',[(r['current_A_g'],r['value'])for r in fw]==[(.5,322.8),(1,314.4),(20,243)]and all(r['conditions']['reference_electrode']is None for r in fw))
        f=d.canonical_material_features_v13(NS,'NSOC-800');ck('NS_EDS_not_XPS',f['values']['EDS_N_wt_pct']==1.44 and not any(k.startswith('XPS_N_at')for k in f['values']));ck('NS_conflicting_positions_masked',not any(k in f['values']for k in ['Raman_D_position_cm_inv','Raman_G_position_cm_inv','XPS_N1s_component_3_binding_eV']))
        ns=[r for r in d.batch24_inputs()if r['doi']==NS];ck('NS_reference_kept_unresolved',all(r['conditions']['reference_electrode']is None and r['conditions']['reference_claims']==['calomel','Hg/HgO']for r in ns));ck('NS873K_explicit_conversion_not_800C',all(r['matrix_feature_values']['single_stage_temperature_K_as_reported']==873 and math.isclose(r['matrix_feature_values']['single_stage_temperature_C_from_K'],599.85)for r in ns))
        hp=[r for r in d.batch24_inputs()if r['doi']==HP];ck('HPC_not_prechar_BET',{r['sample_name']:r['material_features']['BET_surface_area_m2_g']for r in hp}=={'HPC-700':2721,'HPC-800':2202,'HPC-900':1739});ck('HPC_stage_temperatures',all(r['matrix_feature_values']['activation_temperature_C']==800 and r['matrix_feature_values']['salt_sealed_precarbonization_temperature_C']==int(r['sample_name'][-3:])for r in hp))
        a=d.batch24_matrix(TARGETS24[3]);ck('HPC_2E_factor4_not_device',a['y']==[346,262]and all(x['capacitance_basis']=='4I_dt_over_total_two_electrode_active_m_dV'for x in a['categorical_protocol']));ck('HPC_2E_window_not_inherited',all(r['conditions']['voltage_upper_V']is None for r in d.batch24_inputs(TARGETS24[3])))
        ck('ordinary205_30',len(d.auxiliary_gcd())==205 and len({r['doi']for r in d.auxiliary_gcd()})==30);g=d.expanded_graph_3e_matrix();ck('expanded374_30',len(g['y'])==374 and g['source_families']==30)
        ck('same_paper_all_materials_quarantined',all(d.is_quarantined_source(r['source_group'],[r['doi']])for r in d.capacitances()if r['doi']in KEYS))
        from data.cycling_db import open_database
        with open_database()as cycle:
            allcycles=cycle.fetch('all_review').rows;audit=cycling_endpoints_by_doi(allcycles)
            ck('cycling286_fixed37',len(allcycles)==286 and len(cycle.reviewed_pending_batch())==37 and len(cycle.reviewed_pending_batch(True))==41)
            ck('three_existing_links_correct',[(r['record']['doi'],r['record']['existing_endpoint_id'])for r in d.batch24_cycle_identity_links()]==[(FR,'candidate:TE010'),(FW,'candidate:TE008'),(NS,'candidate:V05:017')])
            for r in d.batch24_cycle_identity_links():ck('old_DOI_bound:'+r['record']['existing_endpoint_id'],any(x['endpoint_id']==r['record']['existing_endpoint_id']for x in audit['by_doi'][r['record']['doi']]))
            candidate_audit=dict(status='candidate_identity_only_not_admission',canonical_DOI_matches={doi:[dict(endpoint_id=x['endpoint_id'],sample=x['sample_name'],system=x['system'])for x in audit['by_doi'].get(doi,[])]for doi in KEYS},unresolved_current_endpoint_ids=audit['unresolved_endpoint_ids'],new_candidates=['LP24:NSOC:2E:C5000','LP24:HPC700:2E:C30000'],new_endpoint_records=0,independence_not_assumed_from_no_DOI_match=True)
        mats={r['material_key']:r for r in d.materials()};payload=[dict(kind='material',group='doi:'+r['doi'])for r in mats.values()]+[dict(kind='fact',group='doi:'+r['doi'])for r in d.facts()]+[dict(kind='capacitance',group=r['source_group'])for r in d.capacitances()]+[dict(kind='cycling',group=r['source_group'])for r in allcycles]+[dict(kind='curve',group=r.get('source_group')or'doi:'+r['doi'])for r in d.sampled_curves()]
        for r in d.tests():payload.append(dict(kind='candidate',group='doi:'+mats[r['material_key']]['doi']))
        for r in d.connection.execute('select material_key from synthesis_stages_v3'):payload.append(dict(kind='synthesis',group='doi:'+mats[r[0]]['doi']))
        for r in d.connection.execute('select o.record_json,m.doi from outcome_observations_v3 o left join materials m using(material_key)'):
            q=json.loads(r[0]);sg='doi:'+r[1]if r[1]else q.get('source_group');assert sg;payload.append(dict(kind='response',group=sg))
        for t,rows,m in exports:payload.extend(dict(kind='v24_input',group=r['source_group'])for r in rows)
        fam={}
        for r in payload:r['family']=d.isolation_group(r['group'])
        for family in sorted({r['family']for r in payload}):
            rr=[r for r in payload if r['family']==family];ck('whole_family_holdout:'+family,all(d.is_quarantined_source(r['group'],[family])for r in rr));fam[family]=dict(sorted(collections.Counter(r['kind']for r in rr).items()))
    summary=json.loads((PARENT.parent/'summary.json').read_text('utf8'))
    for k in list(summary):
        if k.startswith('new_')and isinstance(summary[k],int):summary[k]=0
        elif k.startswith('new_')and isinstance(summary[k],list):summary[k]=[]
    summary.update(totals);summary.update(new_materials=25,new_material_facts=236,new_numeric_material_facts=223,new_null_material_facts=13,new_capacitance_reports=26,new_response_records=43,new_source_response_records=43,new_cycle_candidates=2,new_source_scopes=4,new_own_main_tables=8,new_mixed_own_foreign_main_tables=2,new_own_SI_tables=1,new_raw_candidates_touched=8,raw_candidates_touched=252,raw_candidates_untouched=707,reviewed_table_units=284,reviewed_evidence_units=556,distinct_database_table_keys=542,database_extraction_units_v3=525,reviewed_evidence_units_definition='556declared;542actualkeys/525extractionunits;284physicaltables. Thisbatch8nativephysicaltables+1ownSIcomparisonrowtable and17prose/printedlabelunits. SIhasnooldautomaticcandidate; fixed959queuechangedonly8entries.',auxiliary_aqueous_3e_GCD_rows=205,auxiliary_ordinary_3e_DOI_groups=30,auxiliary_purpose_reviewed_input_rows=221,auxiliary_independent_DOI_groups=31,expanded_3e_with_graph_rows=374,expanded_3e_with_graph_DOI_groups=30,new_3e_purpose_inputs=11,new_separate_purpose_rows=[11,1,4,2],new_existing_cycle_identity_links=3,new_figure_scope_inspections=17,new_model_fits=0,scope_note='Fourprimarysources;236facts/223numeric/13unreported,26capacityreports,18separatepurposeinputsand4furfuralinspectionrows. Source-specific2Enormalizationsseparate; referenceuncertaintyinreported3Ecapacitydoesnotclearstricterlifetimegate. No original37reduction/cyclingadmission/fit/fullsourcecompletion; wheat9figassetsunobtained.')
    report=dict(status='passed',database_sha256=sha(DB),parent_sha256=PSHA,check_count=len(checks),checks=checks,new_cycle_admissions=0,new_model_fits=0,scientific_goal_complete=False)
    chain=dict(status='passed',database_sha256=sha(DB),representation_payloads=len(payload),raw_identifiers=len({r['group']for r in payload}),source_families=len(fam),whole_family_counts=fam,secondary_training_admissions=0,fixed_scope=39,current_pending=37,resolved=2,cycling_observations=286,new_cycling_admissions=0,new_model_fits=0,scientific_goal_complete=False,scope='Repeatedrepresentationsnotindependentexperiments; allsource/material/stage/curve/capacity/response/cyclingandcandidate payloads isolated together, secondarymatrixstillrefused')
    for name,value in [('summary',summary),('verification',report),('model_inputs_preflight',preflight),('chain_verification',chain),('candidate_identity_audit',candidate_audit)]:
        if prepare:write(OUT/(name+'.json'),value)
        else:assert json.loads((OUT/(name+'.json')).read_text('utf8'))==value,name
    for t,rows,m in exports:
        b=io.StringIO(newline='');w=csv.writer(b,lineterminator='\n');w.writerow(['observation_id','doi','sample','C_F_g','current_A_g','source_family','source_weight']+FIELDS24)
        for i,r in enumerate(rows):w.writerow([r['observation_id'],r['doi'],r['sample_name'],r['value'],r['current_A_g'],r['source_family_group'],m['sample_weight'][i]]+m['X'][i])
        p=OUT/('purpose_'+t+'.csv')
        if prepare:p.write_text(b.getvalue(),encoding='utf-8-sig',newline='')
        else:assert p.read_text('utf-8-sig')==b.getvalue()
    if(OUT/'merge_manifest.json').exists():
        for r in json.loads((OUT/'merge_manifest.json').read_text('utf8'))['outputs']:assert sha(ROOT/r['path'])==r['sha256'],r['path']
    print(json.dumps({k:v for k,v in report.items()if k!='checks'}))

def seal():
    assert not(OUT/'merge_manifest.json').exists();verify(False)
    h=json.loads((OUT/'historical_v23_verification.json').read_text('utf8'));assert h['status']=='passed'and h['database_sha256']==PSHA
    paths=[p for p in OUT.rglob('*')if p.is_file()]+[ROOT/'data/literature_v24.py',ROOT/'tools/extract_four_primary_v24.py',Path(__file__).resolve()]
    write(OUT/'merge_manifest.json',dict(version='literature_pool_v24',parent_sha256=PSHA,outputs=[dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p),bytes=p.stat().st_size)for p in sorted(paths)],new_cycle_admissions=0,model_fits=0,scientific_goal_complete=False))
    write(ROOT/'data/current_literature.json',dict(version='literature_pool_v24',directory=OUT.relative_to(ROOT).as_posix(),database_file=DB.name,sha256=sha(DB),api_module='data.literature_v24',scope='Fourprimarysources:236facts/223numeric,26capacityreports;18purposeinputs and4disputedinspectionrows. 11reported3EGCDauxnew,3oldcyclelinks/2candidatesonly; original37holdsunchanged, nofit/fullsourcecompletion.'))
if __name__=='__main__':
    mode=sys.argv[1]
    if mode=='prepare':verify(True)
    elif mode=='verify':verify(False)
    elif mode=='seal':seal()
    else:raise SystemExit(mode)
