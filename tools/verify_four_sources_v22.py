"""Source/cell/immutability/purpose/isolation validation; prepare and seal only before release."""
import collections,contextlib,csv,io,json,math,sqlite3,sys,xml.etree.ElementTree as E
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tools'))
from extract_four_sources_v22 import OUT,DB,PARENT,PSHA,KEYS,FO,PI,DI,MN,sha,write,ro,number,xml_grid,clean
from data.literature_v22 import open_literature_database,TARGETS22,FIELDS22
from data.literature_v21 import open_literature_database as old_open
from data.literature_v20 import TARGETS20
EXPECTED=[3,3,3,3,3,3,1,5,3]
def verify(prepare=False):
    if prepare:assert not(OUT/'merge_manifest.json').exists()
    checks=[];digest=sha(DB);spec=json.loads((OUT/'curation_spec.json').read_text('utf8'));docs={d['key']:d for d in spec['documents']}
    def ck(name,ok):assert ok,name;checks.append(name)
    ck('parent_SHA',sha(PARENT)==PSHA)
    for r in json.loads((OUT/'protected_inputs.json').read_text('utf8'))['files']:ck('protected:'+r['path'],sha(ROOT/r['path'])==r['sha256'])
    for r in json.loads((PARENT.parent/'merge_manifest.json').read_text('utf8'))['outputs']:ck('old_manifest:'+r['path'],sha(ROOT/r['path'])==r['sha256'])
    for t in spec['tables']:
        root=E.parse(ROOT/docs[t['document']]['path']).getroot();tt=next(x for x in root.findall('.//table-wrap')if x.get('id')==t['id']);ck('native_table:'+t['doi']+t['id'],xml_grid(tt)==t['grid'])
    for f in spec['figures']:
        r=E.parse(ROOT/docs[KEYS[f['doi']]]['path']).getroot();x=next(x for x in r.findall('.//fig')if x.get('id')==f['xml_id']);ck('printed_figure_identity:'+f['doi']+str(f['figure_number']),clean(x.find('label'))==f['printed_label']and x.find('.//graphic').get('{http://www.w3.org/1999/xlink}href')==f['graphic_href']);ck('figure_original_SHA:'+f['doi']+str(f['figure_number']),all(sha(ROOT/p)==docs[f['document']]['sha256']for p in f['equivalent_local_paths']))
    with contextlib.closing(ro(DB))as c,contextlib.closing(ro(PARENT))as p:
        c.row_factory=p.row_factory=sqlite3.Row;ck('SQLite_integrity',[r[0]for r in c.execute('pragma integrity_check')]==['ok']);ck('foreign_keys',not c.execute('pragma foreign_key_check').fetchall())
        changed=[]
        for name, in p.execute("select name from sqlite_master where type='table'and name not like'sqlite_%'"):
            if name=='raw_table_queue':
                before={r['table_id']:dict(r)for r in p.execute('select *from raw_table_queue')}
                for r in c.execute('select *from raw_table_queue'):
                    a=dict(r);b=before[r['table_id']]
                    if a!=b:changed.append(r['table_id']);ck('queue_only_state:'+r['table_id'],{k:v for k,v in a.items()if k!='review_state'}=={k:v for k,v in b.items()if k!='review_state'})
            else:ck('immutable_old_rows:'+name,{tuple(r)for r in p.execute('select *from "'+name+'"')}<={tuple(r)for r in c.execute('select *from "'+name+'"')})
        ck('only14native_candidates',len(changed)==14 and set(changed)=={t['raw_table_id']for t in spec['tables']})
        for table,n in [('materials',38),('material_facts',238),('capacitance_observations',28),('outcome_observations_v3',66),('synthesis_stages_v3',25),('test_candidates',3),('reviewed_sources',4),('reviewed_tables',28),('scientific_issues',5)]:ck('delta:'+table,c.execute('select count(*)from '+table).fetchone()[0]-p.execute('select count(*)from '+table).fetchone()[0]==n)
        for r in c.execute('select *from cell_extractions_v22'):
            raw=json.loads(c.execute('select cells_json from transcribed_rows where table_key=?and row_ordinal=?',(r['table_key'],r['row_ordinal'])).fetchone()[0])[r['column_ordinal']]
            table,pk={'fact':('material_facts','fact_id'),'capacitance':('capacitance_observations','observation_id'),'response':('outcome_observations_v3','outcome_id')}[r['kind']];v=c.execute('select *from '+table+' where '+pk+'=?',(r['record_id'],)).fetchone();v=json.loads(v['record_json'])if r['kind']=='response'else dict(v)
            ck('literal_cell:'+r['kind']+r['record_id'],v['raw_value']==raw);ck('numeric_cell:'+r['kind']+r['record_id'],v['value']==number(raw))
            if r['kind']=='fact':
                doc=c.execute('select document_key from table_source_links where table_key=?',(r['table_key'],)).fetchone()[0];ck('fact_SHA:'+r['record_id'],v['source_sha256']==docs[doc]['sha256']);ck('numeric_details:'+r['record_id'],json.loads(c.execute('select record_json from numeric_details_v22 where fact_id=?',(r['record_id'],)).fetchone()[0])['value']==v['value'])
        count=lambda t:c.execute('select count(*)from '+t).fetchone()[0]
        totals={k:count(t)for k,t in [('cumulative_reviewed_source_publications','source_scope_decisions'),('cumulative_materials','materials'),('cumulative_selected_material_cells','material_facts'),('actual_distinct_reviewed_table_keys','reviewed_tables'),('extraction_units_v3_count','extraction_units_v3'),('capacitance_records','capacitance_observations'),('cycling_candidates','test_candidates'),('scientific_issues','scientific_issues'),('synthesis_materials','synthesis_stages_v3'),('response_outcomes','outcome_observations_v3')]}
        totals['cumulative_numeric_material_facts']=c.execute('select count(*)from material_facts where value is not null').fetchone()[0];totals['unreported_material_cells']=count('material_facts')-totals['cumulative_numeric_material_facts'];totals['numeric_capacitance_values']=c.execute('select count(*)from capacitance_observations where value is not null').fetchone()[0]
        ck('queue_959_731',count('raw_table_queue')==959 and c.execute("select count(*)from raw_table_queue where review_state='automatic_candidate_unreviewed'").fetchone()[0]==731)
    preflight={};exports=[]
    with open_literature_database(DB,digest)as d,old_open(PARENT,PSHA)as old:
        oldfacts={r['fact_id']:r for r in old.facts()}
        for r in d.facts():
            if r['fact_id']in oldfacts:ck('old_API_fact:'+str(r['fact_id']),r==oldfacts[r['fact_id']])
        for t in TARGETS20:ck('old_v20_matrix:'+t,d.batch20_matrix(t)==old.batch20_matrix(t))
        for p in ['coffee_KOH_author_capacity','rice_mass_ratio_inspection']:
            for mode in ['author_exact','point_mixed','figure_only']:ck('old_v21_rates:'+p+mode,d.batch21_rate_rows(mode,p)==old.batch21_rate_rows(mode,p))
        for profile in ['3e','2e_device','native_mineral_3e','2e_author_factor2']:
            current={r['observation_id']:r for r in d.auxiliary_gcd(profile)}
            for r in old.auxiliary_gcd(profile):ck('old_aux:'+r['observation_id'],r==current[r['observation_id']])
        for t,n in zip(TARGETS22,EXPECTED):
            rows=d.batch22_inputs(t);m=d.batch22_matrix(t);ck('purpose_count:'+t,len(rows)==n==len(m['y']));ck('purpose_masks:'+t,m['missing_mask']==[[v is None for v in xx]for xx in m['X']]);ck('no_fit_imputation:'+t,not m['imputed']and m['estimators_fitted']==0 and not m['training_authorized']);ck('unique_physical_test_within_purpose:'+t,len(set(m['physical_test_groups']))==n)
            for g in sorted(set(m['groups'])):ck('source_weights:'+t+g,math.isclose(sum(w for w,gg in zip(m['sample_weight'],m['groups'])if gg==g),1))
            for r in rows:ck('same_source_quarantine:'+r['observation_id'],d.isolation_group(r['source_group'])==r['source_family_group']and not r['cyclic_retention_training_admitted'])
            preflight[t]=dict(rows=n,source_families=m['source_families'],features=len(FIELDS22),missing_cells=sum(sum(rr)for rr in m['missing_mask']),model_fits=0,cross_source_comparable=all(r['cross_source_comparable']for r in m['categorical_protocol']));exports.append((t,rows,m))
        pine=d.batch22_inputs(TARGETS22[0]);ck('three_ordinary_pine_reports',[(r['sample_name'],r['current_A_g'],r['value'])for r in pine]==[('DRY-1',.1,146),('DRY-1',15,59),('WET-1',15,64)])
        ck('WET247_preserved_excluded',any(r['value']==247 and r['current_A_g']==.1 for r in d.capacitances(PI))and not any(r['value']==247 for r in pine))
        f=d.canonical_material_features_v13(PI,'DRY-1');ck('pine_Vtotal_primary_unit_resolved',f['values']['total_pore_volume_cm3_g']==.637 and'tplot_micropore_volume_raw_m3_g'not in f['values']);ck('within_peak_not_whole_atomic',f['values']['XPS_C1s_CC_envelope_pct']==59.7 and f['values']['XPS_C_at_pct']==96.3)
        f=d.canonical_material_features_v13(DI,'NAPC-650-4');ck('no_EA_inherited_from_other_ratio',not any(k.startswith('elemental_analysis')for k in f['values'])and f['values']['Raman_ID_IG']==.856)
        for s in ['NAPC-650-1','NAPC-650-2']:ck('BET_dispute_masked:'+s,'BET_surface_area_m2_g'not in d.canonical_material_features_v13(DI,s)['values']and len(d.facts(DI,s,'BET_surface_area_m2_g'))==2)
        ck('SAP_and_Mn_not_in_ordinary_GCD',all(r['doi']not in [DI,MN,FO]for r in d.auxiliary_gcd()if r['doi']in KEYS))
        f=d.canonical_material_features_v13(FO,'PAC');ck('raw_ashfree_not_same_measurement',f['values']['BET_surface_area_m2_g']==2813 and f['values']['author_ash_free_recalculated_BET_m2_g']==3125 and'Raman_ID_IG_author_intensity_area_ambiguous'not in f['values']);ck('H2_batch_not_inherited',not any('density'in k for k in f['values']))
        a=d.batch22_matrix(TARGETS22[1]);b=d.batch22_matrix(TARGETS22[2]);ck('raw_ashfree_same_tests',a['physical_test_groups']==b['physical_test_groups']and a['y']!=b['y'])
        ck('organic_window_missing_not_guessed',all(r['conditions']['voltage_upper_V']is None for r in d.batch22_inputs(TARGETS22[3])))
        f=d.canonical_material_features_v13(MN,'C-LS120%-Mn20%');ck('EDX_unknown_basis_not_XPS',not any(k.startswith('XPS')or k.startswith('SEM_EDX')for k in f['values']))
        ck('CV_not_GCD_lifetime',len(d.capacitances(MN,method='CV'))==8 and not d.capacitances(MN,method='GCD')and not any(r['record']['source_group']=='doi:'+MN for r in d.tests()))
        ck('kinetic_exponent_normalized',any(r['record']['raw_value']=='(5.22 ± 2.25) × 106'and r['record']['value']==5220000 for r in d.outcomes('pyrolysis_model_pre_exponential_factor')))
        ck('ordinary192_26',len(d.auxiliary_gcd())==192 and len({r['doi']for r in d.auxiliary_gcd()})==26);ck('expanded361_26',len(d.expanded_graph_3e_matrix()['y'])==361 and d.expanded_graph_3e_matrix()['source_families']==26)
        ck('all_source_scopes_still_partial',totals['cumulative_reviewed_source_publications']==56 and not d.connection.execute('select *from source_scope_decisions where full_source_review_complete=1').fetchall())
        summary=json.loads((PARENT.parent/'summary.json').read_text('utf8'))
        for k in list(summary):
            if k.startswith('new_')and isinstance(summary[k],int):summary[k]=0
            elif k.startswith('new_')and isinstance(summary[k],list):summary[k]=[]
        summary.update(totals);summary.update(new_materials=38,new_material_facts=238,new_numeric_material_facts=235,new_null_material_facts=3,new_capacitance_reports=28,new_response_records=66,new_source_response_records=66,new_cycle_candidates=3,new_source_scopes=4,new_own_main_tables=14,new_mixed_own_foreign_main_tables=3,new_raw_candidates_touched=14,raw_candidates_touched=228,raw_candidates_untouched=731,reviewed_table_units=259,reviewed_evidence_units=510,distinct_database_table_keys=496,database_extraction_units_v3=479,reviewed_evidence_units_definition='510declaredunits;496actualkeys/479extractionunits;259physicaltables. 14mainphysicaltables plus14prose/printedlabelunits. 38stage registrations include prechars, unactivatedcontrols, kineticprecursors and separateH2batches, not38independentfinalmaterials.',auxiliary_aqueous_3e_GCD_rows=192,auxiliary_ordinary_3e_DOI_groups=26,auxiliary_purpose_reviewed_input_rows=208,auxiliary_independent_DOI_groups=27,expanded_3e_with_graph_rows=361,expanded_3e_with_graph_DOI_groups=26,new_3e_purpose_inputs=3,new_separate_purpose_rows=EXPECTED,new_existing_cycle_identity_links=6,new_figure_scope_inspections=25,new_model_fits=0,scope_note='Fourexistingpublications; allmainnativetables/fullbody and25availableoriginalfigurescopes. 235numericmaterialfacts/3null;28capacityreports;27conditionexpressionsin9separatepurposes. WET1.1Ag247disputedexcluded, SAPmixedreference andMnCVkeptseparate, ashfree/rawsameexperiment. No cyclingadmission/fit/fullsourcecompletion. ForestSI/main10figassetsstillunobtained.')
    report=dict(status='passed',database_sha256=digest,parent_sha256=PSHA,checks=checks,check_count=len(checks),new_cycle_admissions=0,new_model_fits=0,scientific_goal_complete=False)
    for name,value in [('summary',summary),('verification',report),('model_inputs_preflight',preflight)]:
        if prepare:write(OUT/(name+'.json'),value)
        else:assert json.loads((OUT/(name+'.json')).read_text('utf8'))==value,name
    for t,rows,m in exports:
        buf=io.StringIO(newline='');w=csv.writer(buf,lineterminator='\n');w.writerow(['observation_id','doi','sample','method','current_A_g','scan_rate_mV_s','capacitance_F_g','source_family_group','source_weight']+FIELDS22)
        for i,r in enumerate(rows):w.writerow([r['observation_id'],r['doi'],r['sample_name'],r['method'],r['current_A_g'],r['scan_rate_mV_s'],r['value'],r['source_family_group'],m['sample_weight'][i]]+m['X'][i])
        path=OUT/('purpose_'+t+'.csv')
        if prepare:path.write_text(buf.getvalue(),encoding='utf-8-sig',newline='')
        else:assert path.read_text(encoding='utf-8-sig')==buf.getvalue()
    if(OUT/'merge_manifest.json').exists():
        for r in json.loads((OUT/'merge_manifest.json').read_text('utf8'))['outputs']:assert sha(ROOT/r['path'])==r['sha256'],r['path']
    print(json.dumps({k:v for k,v in report.items()if k!='checks'},ensure_ascii=False))

def chain(prepare=False):
    if prepare:assert not(OUT/'merge_manifest.json').exists()
    from verify_identity_rates_v21 import verify as historical_verify,chain as historical_chain
    with contextlib.redirect_stdout(io.StringIO()):historical_verify(False);historical_chain(False)
    from data.cycling_db import open_database
    payload=[]
    with open_literature_database(DB,sha(DB))as d,open_database()as cycle:
        mats={r['material_key']:r for r in d.materials()}
        def add(kind,rows):
            for r in rows:payload.append(dict(kind=kind,group=r.get('source_group')or'doi:'+r['doi']))
        add('fact',d.facts());add('registration',d.materials());add('capacitance',d.capacitances());add('curve',d.sampled_curves());add('cycling',cycle.fetch('all_review').rows)
        for r in d.tests():payload.append(dict(kind='candidate',group=r['record']['source_group']))
        for r in d.connection.execute('select material_key from synthesis_stages_v3'):payload.append(dict(kind='synthesis',group='doi:'+mats[r[0]]['doi']))
        for r in d.connection.execute('select o.record_json,m.doi from outcome_observations_v3 o left join materials m using(material_key)'):
            rec=json.loads(r[0]);g='doi:'+r[1]if r[1]else rec.get('source_group');assert g;payload.append(dict(kind='response',group=g))
        for t in TARGETS22:add('v22_input',d.batch22_inputs(t))
        for r in d.batch22_cycle_identity_links():payload.append(dict(kind='v22_identity',group='doi:'+r['record']['doi']))
        for r in payload:r['family']=d.isolation_group(r['group'])
        holds={}
        for g in sorted({r['family']for r in payload}):
            test=[r for r in payload if r['family']==g];train=[r for r in payload if r['family']!=g];assert not{r['family']for r in test}&{r['family']for r in train};assert all(d.is_quarantined_source(x,[g])and d.is_quarantined_source(x.removeprefix('doi:'),[g])for x in {r['group']for r in test});holds[g]=dict(sorted(collections.Counter(r['kind']for r in test).items()))
        assert len(cycle.fetch('all_review').rows)==286 and len(cycle.reviewed_pending_batch())==37 and len(cycle.reviewed_pending_batch(True))==41
        goal=json.loads((OUT/'correction_scope_snapshot.json').read_text('utf8'))
        assert goal['fixed_record_count']==39 and goal['scientifically_resolved_in_goal']==2 and goal['current_pending']==37
        assert all(cycle.by_endpoint(x)['eligible']==1 for x in ['candidate:TE033','candidate:TE034'])
        assert cycle.by_endpoint('candidate:TE032')['eligible']==0
        assert not any('B2_004'in str(x)for x in cycle.reviewed_pending_batch(True))
        report=dict(status='passed',database_sha256=sha(DB),payloads=len(payload),raw_identifiers=len({r['group']for r in payload}),source_families=len(holds),full_quarantine_counts=holds,historical_pinned_v21_and_earlier='passed',fixed_scope=39,current_pending=37,resolved=2,cycling_observations=286,new_cycling_admissions=0,new_model_fits=0,scientific_goal_complete=False,payload_definition='Repeated representations andviews, not independent experiments; all sameDOI/material/curve/response/purpose isolated together, oldadditionalviews verifiedinimmutablehistoricchain')
    if prepare:write(OUT/'chain_verification.json',report)
    else:assert json.loads((OUT/'chain_verification.json').read_text('utf8'))==report
    print(json.dumps({k:v for k,v in report.items()if k!='full_quarantine_counts'}))

def seal():
    assert not(OUT/'merge_manifest.json').exists();verify(False);chain(False)
    paths=[p for p in OUT.rglob('*')if p.is_file()]+[ROOT/'data/literature_v22.py',ROOT/'tools/extract_four_sources_v22.py',Path(__file__).resolve()]
    write(OUT/'merge_manifest.json',dict(version='literature_pool_v22',parent_sha256=PSHA,outputs=[dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p),bytes=p.stat().st_size)for p in sorted(paths)],model_fits=0,new_cycle_admissions=0,scientific_goal_complete=False))
    write(ROOT/'data/current_literature.json',dict(version='literature_pool_v22',directory=OUT.relative_to(ROOT).as_posix(),database_file=DB.name,sha256=sha(DB),api_module='data.literature_v22',scope='Fourexistingpublications;238facts/235numeric,28capacityreports,27separatepurposeexpressions,3neworganiccyclecandidatesand6oldcyclelinks. WET247disputedmasked; SAPandMnCVscopesseparate. No newcyclingadmission/fitting/fullsourcecompletion.'))
if __name__=='__main__':
    mode=sys.argv[1]
    if mode=='prepare':verify(True);chain(True)
    elif mode=='seal':seal()
    elif mode=='verify':verify(False);chain(False)
    else:raise SystemExit('prepare/seal/verify')
