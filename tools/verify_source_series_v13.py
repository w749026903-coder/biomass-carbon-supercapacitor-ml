"""Read-only verification; prepare/seal are explicit one-use release operations."""
from pathlib import Path
from contextlib import closing
import collections,json,sqlite3,sys,xml.etree.ElementTree as E,zipfile
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tools'))
from extract_source_series_v13 import OUT,EV,DB,PARENT,PSHA,MA,LE,FU,RF,NAMES,sha,write,ro,mk,xml_grid,number


def verify(prepare=False):
    from data.literature_v13 import open_literature_database
    from data.literature_v12 import open_literature_database as oldapi,TARGETS12
    checks=[]
    def ck(name,passed):
        if not passed:raise AssertionError(name)
        checks.append(name)
    digest=sha(DB);spec=json.loads((OUT/'curation_spec.json').read_text('utf8'));notes=json.loads((OUT/'source_review_notes.json').read_text('utf8'))
    ck('parent_database_pin',sha(PARENT)==PSHA)
    for r in json.loads((OUT/'protected_inputs.json').read_text('utf8'))['files']:ck('protected:'+r['path'],sha(ROOT/r['path'])==r['sha256'])
    for r in json.loads((PARENT.parent/'merge_manifest.json').read_text('utf8'))['outputs']:ck('parent_payload:'+r['path'],sha(ROOT/r['path'])==r['sha256'])
    for receipt in notes['existing_package_receipts']:
        ck('original_package:'+receipt['label'],sha(ROOT/receipt['package'])==receipt['sha256'])
        with zipfile.ZipFile(ROOT/receipt['package'])as z:
            for name in receipt['selected_members']:ck('original_member:'+name,(EV/name).read_bytes()==z.read(name))
    receipt=json.loads((EV/'Commercial_acquisition.json').read_text('utf8'))
    ck('commercial_package',sha(ROOT/receipt['path'])==receipt['sha256'])
    with zipfile.ZipFile(ROOT/receipt['path'])as z:
        for name in receipt['selected_members']:ck('original_commercial_member:'+name,(EV/name).read_bytes()==z.read(name))
    furzip=ROOT/'文献扩充_大批补齐_20261018/sources/SUP_117/assets/polymers-16-03421-s001.zip'
    with zipfile.ZipFile(furzip)as z:ck('Furfural_exact_SI_member',(EV/'polymers-3313966-supplementary.pdf').read_bytes()==z.read('polymers-3313966-supplementary.pdf'))
    from pypdf import PdfReader
    ck('Leather_SI_5_pages',len(PdfReader(ROOT/notes['leather_SI']['path']).pages)==5)
    ck('Furfural_SI_3_pages',len(PdfReader(EV/'polymers-3313966-supplementary.pdf').pages)==3)
    with closing(ro(DB))as c:
        c.row_factory=sqlite3.Row;ck('integrity',c.execute('pragma integrity_check').fetchone()[0]=='ok');ck('foreign_keys',not c.execute('pragma foreign_key_check').fetchall())
        c.execute('attach database ?as parent',(PARENT.as_uri()+'?mode=ro',))
        for (table,)in c.execute("select name from parent.sqlite_master where type='table'and name not like 'sqlite_%'"):
            if table=='raw_table_queue':continue
            ck('all_parent_rows:'+table,not c.execute('select *from parent.'+table+' except select *from main.'+table).fetchall())
        touched={r['raw_table_id']for r in spec['tables']};ck('15_distinct_original_candidates',len(touched)==15)
        for before in c.execute('select *from parent.raw_table_queue'):
            now=dict(c.execute('select *from raw_table_queue where table_id=?',(before['table_id'],)).fetchone());before=dict(before)
            if before['table_id']in touched:
                ck('previously_untouched:'+before['table_id'],before['review_state']=='automatic_candidate_unreviewed');ck('declared_partial_scope:'+before['table_id'],now['review_state']=='v13_declared_own_scope_reference_and_foreign_rows_separate');now['review_state']=before['review_state']
            ck('raw_queue_original_fields:'+before['table_id'],now==before)
        count=lambda t:c.execute('select count(*)from '+t).fetchone()[0]
        ck('raw959_preserved',count('raw_table_queue')==959);ck('813_untouched',c.execute("select count(*)from raw_table_queue where review_state='automatic_candidate_unreviewed'").fetchone()[0]==813)
        for table in ['material_facts','capacitance_observations','outcome_observations_v3','test_candidates','raw_table_queue']:ck('raw_no_auto_admission:'+table,c.execute('select count(*)from '+table+' where training_eligible!=0 or training_eligible is null').fetchone()[0]==0)
        for t in spec['tables']:
            source=next(s for s in spec['sources']if s['doi']==t['doi']);root=E.parse(ROOT/source['path']).getroot()
            ck('original_table_grid:'+t['doi']+t['id'],xml_grid(next(x for x in root.findall('.//table-wrap')if x.get('id')==t['id']))==t['grid'])
            ck('original_source_DOI:'+t['doi']+t['id'],{x.text.lower()for x in root.findall('./front/article-meta/article-id')if x.get('pub-id-type')=='doi'}=={t['doi']})
        for unit in spec['tables']+spec['units']:
            key=unit['doi']+'#'+unit['id'];rows=[[v['raw']for v in r]for r in unit['grid']]if 'grid'in unit else unit['rows']
            got=[json.loads(r[0])for r in c.execute('select cells_json from transcribed_rows where table_key=? order by row_ordinal',(key,))]
            ck('transcribed_scope:'+key,got==rows)
        for r in c.execute('select *from cell_extractions_v13'):
            raw=json.loads(c.execute('select cells_json from transcribed_rows where table_key=?and row_ordinal=?',(r['table_key'],r['row_ordinal'])).fetchone()[0])[r['column_ordinal']];value=number(raw,r['parse_part'])
            table,idfield={'fact':('material_facts','fact_id'),'capacitance':('capacitance_observations','observation_id'),'response':('outcome_observations_v3','outcome_id')}[r['kind']]
            stored=dict(c.execute('select *from '+table+' where '+idfield+'=?',(r['record_id'],)).fetchone());stored=json.loads(stored['record_json'])if r['kind']=='response'else stored
            ck('cell:'+r['kind']+':'+r['record_id'],stored['raw_value']==raw and stored['value']==value)
        ck('all401_receipts',count('cell_extractions_v13')==211+55+135)
        old=json.loads((PARENT.parent/'summary.json').read_text('utf8'));summary=dict(old)
        numeric=c.execute('select count(*)from material_facts where value is not null').fetchone()[0]
        summary.update(cumulative_reviewed_source_publications=count('reviewed_sources'),cumulative_materials=count('materials'),cumulative_selected_material_cells=count('material_facts'),cumulative_numeric_material_facts=numeric,new_materials=26,new_numeric_material_facts=numeric-old['cumulative_numeric_material_facts'],reviewed_table_units=old['reviewed_table_units']+16,reviewed_evidence_units=old['reviewed_evidence_units']+54,distinct_database_table_keys=count('reviewed_tables'),database_extraction_units_v3=count('extraction_units_v3'),raw_candidates_touched=146,raw_candidates_untouched=813,capacitance_records=count('capacitance_observations'),numeric_capacitance_values=c.execute('select count(*)from capacitance_observations where value is not null').fetchone()[0],cycling_candidates=count('test_candidates'),scientific_issues=count('scientific_issues'),synthesis_materials=count('synthesis_stages_v3'),response_outcomes=count('outcome_observations_v3'),new_source_response_records=135,new_capacitance_reports=55,new_response_records=135,new_own_main_tables=11,new_own_SI_tables=1,new_mixed_comparison_main_tables=4,new_foreign_comparison_main_tables=0,unreported_material_cells=c.execute('select count(*)from material_facts where value is null').fetchone()[0],auxiliary_aqueous_3e_GCD_rows=156,auxiliary_independent_DOI_groups=17,auxiliary_purpose_reviewed_input_rows=172,new_batch13_template_residue_rows=4,new_batch13_reference_reports=24,new_batch13_wetting_reports=9,full_source_review_complete=0,scope_note='Four declared source scopes, including one origin-unverified commercial method reference; 26 registrations include one raw feedstock and nine reference variants. Exact reports, partial figures and complete available SI read; waveforms remain. No formal cycle admission or fit.')
        summary['reviewed_evidence_units_definition']='Historical cumulative declared scope units322; distinct DB table keys308 and extraction_units_v3 291 are separate inventories, not experiments.'
        ck('expected_totals',all(summary[k]==v for k,v in dict(cumulative_materials=211,cumulative_selected_material_cells=2383,cumulative_numeric_material_facts=2293,capacitance_records=784,numeric_capacitance_values=782,unreported_material_cells=90,cycling_candidates=69,response_outcomes=2509,synthesis_materials=176,cumulative_reviewed_source_publications=37).items()))
        ck('no_full_source_completion',c.execute('select sum(full_source_review_complete)from source_scope_decisions').fetchone()[0]==0)
    with open_literature_database(DB,digest)as d,oldapi(PARENT,PSHA)as old:
        for profile in ['3e','2e_device','native_mineral_3e','2e_author_factor2']:
            before=old.auxiliary_feature_rows(profile);ids={r['observation_id']for r in before};after=d.auxiliary_feature_rows(profile);ck('old_aux_exact:'+profile,[r for r in after if r['observation_id']in ids]==before)
        facts=lambda doi,sample,field:d.facts(doi=doi,sample=sample,field=field)
        vals=lambda doi,sample,field:{r['value']for r in facts(doi,sample,field)}
        canonical=lambda doi,s:d.canonical_material_features_v13(doi,s)['values']
        ck('Mango_working_BET_and_dissent',canonical(MA,'MK9')['BET_surface_area_m2_g']==1348.5 and vals(MA,'MK9','BET_surface_area_m2_g')=={1348.5,1348.9})
        ck('Mango_EDS_MK10_only',vals(MA,'MK10','EDS_C_reported_pct')=={84.86}and not facts(MA,'MK9','EDS_C_reported_pct'))
        ck('Mango_mass_mg_not_area',vals(MA,'MK9','active_mass_mg_reported')=={2.61}and not facts(MA,'MK9','mass_loading_mg_cm2'))
        for sample,value in [('A-NSC6',531.71),('A-NSC8',2214.5)]:ck('Leather_precision:'+sample,canonical(LE,sample)['BET_surface_area_m2_g']==value)
        for field in ['BET_surface_area_m2_g','total_pore_volume_cm3_g','average_pore_diameter_reported_nm']:ck('Leather_A7_blank:'+field,vals(LE,'A-NSC7',field)=={None}and field not in canonical(LE,'A-NSC7'))
        ck('Leather_EDS_vs_XPS',vals(LE,'A-NSC8','EDS_N_reported_pct')=={28.59}and vals(LE,'A-NSC8','XPS_N_reported_pct')=={31.12}and not facts(LE,'A-NSC8','XPS_N_at_pct'))
        ck('Furfural_contact_freeze',all('water_contact_angle_time_unspecified_deg'not in canonical(FU,s)and vals(FU,s,'water_contact_angle_time_unspecified_deg')=={8.7,34.2}for s in ['PC900-0','PC900-1']))
        ck('Furfural_final_Zn_not_assumed_pure',canonical(FU,'PC900-1')['ICP_OES_Zn_wt_pct']==1.19 and canonical(FU,'PC900-1')['author_S_wt_pct_method_unspecified']==19.26)
        ck('raw_ad_daf_not_final',vals(FU,'raw_FR','feedstock_C_wt_daf_pct')=={50.16}and not any(f['field_name'].startswith('feedstock_')for f in d.facts(doi=FU,sample='PC900-1')))
        ck('reference_not_biomass_input',len(d.interface_reference_reports())==24 and all(not r['training_input_ready']for r in d.interface_reference_reports()))
        ck('six_reference_variants_no_pore_inheritance',all('BET_surface_area_m2_g'not in canonical(RF,s)for s in NAMES[RF]if s not in ['NEAT_AC','Emim_0.25pct','Bmim_0.5pct']))
        ck('reference_ND_not_zero',len([f for f in d.facts(doi=RF)if 'not_detected'in f['review_status']and f['value']is None])==4)
        ck('wetting_time_series',len(d.wettability_series_v13())==9 and canonical(RF,'Emim_0.25pct')['water_contact_angle_t0s_deg']==45.73 and canonical(RF,'Emim_0.25pct')['water_contact_angle_t6s_deg']==7.8)
        newaux=[r for r in d.auxiliary_gcd('3e')if r['doi']in [MA,LE]]
        ck('nine_selected_not_repeats',len(newaux)==9 and len({(r['doi'],r['sample_name'],r['current_A_g'])for r in newaux})==9)
        ck('author_j_unknown_mass_basis_allowed',all(r['conditions']['current_mass_basis']=='author_reported_unknown_not_inferred'for r in newaux))
        ck('no_unknown_XPS_atom_inferred',all('XPS_N_at_pct'not in r['material_features']for r in newaux))
        allaux=[r for p in ['3e','2e_device','native_mineral_3e','2e_author_factor2']for r in d.auxiliary_gcd(p)]
        ck('aux172_17DOI',len(allaux)==172 and len({r['doi']for r in allaux})==17);ck('ordinary3E156_16DOI',len(d.auxiliary_gcd('3e'))==156 and len({r['doi']for r in d.auxiliary_gcd('3e')})==16)
        residue=d.template_residue_matrix();ck('residue_separate',len(residue['y'])==4 and len(set(residue['groups']))==1 and not residue['independent_source_validation_possible_alone']and abs(sum(residue['sample_weight'])-1)<1e-12)
        ck('residue_masks',all(mask==(value is None)for row,masks in zip(residue['X'],residue['missing_mask'])for value,mask in zip(row,masks)));ck('no_contact_conflict_in_residue_features','water_contact_angle_time_unspecified_deg'not in residue['feature_names'])
        reports=d.report_groups_v13();refs=[r for r in reports if r['reference_only']]
        ck('55_reports_not_independent_tests',len(reports)==55 and len(refs)==24 and len({r['nominal_report_group']for r in refs})==21 and all(r['independent_experiment_count']is None for r in reports))
        ck('report_source_quarantine',all('doi:'+r['doi']in d.quarantine_source_groups([r['source_family_group']])for r in reports))
        candidates={r['candidate_id']:r['record']for r in d.tests()if r['candidate_id'].startswith('LP13_')};m=candidates['LP13_Mango_MK9_2E_C100000'];l=candidates['LP13_Leather_ANSC8_3E_C10000']
        ck('Mango_retention_role_not_CE',m['retention_pct']==79.3 and m['cycle_count']==100000 and m['reported_current_A_g']==2 and m['cycle_voltage_upper_V']==1.2 and m['baseline_cycle']is None)
        ck('Leather_cycle_current_dissent',l['retention_pct']==99.2 and l['reported_current_A_g']==10 and l['competing_table_cycle_current_A_g']==1 and l['competing_table_retention_pct']==99)
        ck('commercial_cycles_stay_pending',all(not r['purpose_reviewed_candidate_ready']and r['cycle_voltage_lower_V']is None and r['cycle_voltage_upper_V']is None for k,r in candidates.items()if 'Interface'in k))
        ck('no_furfural_rate_as_cycling',not any('doi:'+FU==r['record']['source_group']for r in d.tests()))
        for target in TARGETS12:ck('old_v12_target_exact:'+target,d.batch12_inputs(target)==old.batch12_inputs(target)and d.batch12_matrix(target)==old.batch12_matrix(target))
        for name,now,before in [('curves',d.sampled_curves(),old.sampled_curves()),('freezes',d.legacy_feature_conflicts(),old.legacy_feature_conflicts()),('families',d.source_relations(),old.source_relations()),('composite',d.composite_cycle_inputs(),old.composite_cycle_inputs())]:ck('parent_exact:'+name,now==before)
        ck('parent_DES_exact',all(d.des_reported_inputs(t)==old.des_reported_inputs(t)for t in ['retention','capacitance']))
        responses=[json.loads(r[0])for r in d.connection.execute("select record_json from outcome_observations_v3 where table_key like ?",(LE+'#SI_TableS1',))]
        ck('SI_malformed_1_o_not1',len([r for r in responses if r['raw_value']=='1.o'and r['value']is None])==1)
        for s in NAMES[MA]:ck('Mango_duration_unknown:'+s,d.synthesis(doi=MA,sample=s)[0]['stages'][0]['duration_h']is None)
        for s in NAMES[RF]:
            stages=d.synthesis(doi=RF,sample=s)[0]['stages'];ck('reference_solution_binder:'+s,any('solution'in json.dumps(r).lower()for r in stages)and not any(r.get('PVDF_wt_pct')==10 for r in stages))
    ck('read_only_database_hash',sha(DB)==digest)
    audits=[dict(kind='author_rate_ratio',sample='PC900-0.1',reported_pct=80.7,calculated_pct=114.32/141.32*100,action='Preserve author80.7 and reported point values; no cycling endpoint or forced overwrite.'),dict(kind='Mango_BET',working=1348.5,dissent=1348.9,action='Detailed own Table1/body/conclusion working choice; no erratum claim.'),dict(kind='Furfural_contact',prose={'PC900-0':8.7,'PC900-1':34.2},figure={'PC900-0':34.2,'PC900-1':8.7},canonical=None,action='Freeze both canonical contact-angle fields.'),dict(kind='Leather_current',selected_A_g=10,competing_A_g=1,action='Actual own cycle plot/caption and methods/results; retain comparison dissent.')]
    report=dict(status='passed',database_sha256=digest,check_count=len(checks),checks=checks,model_fits=0,formal_cycling_admissions=0,scientific_goal_complete=False)
    for name,value in [('summary',summary),('verification',report),('quantity_audits',audits)]:
        if prepare:assert not(OUT/'merge_manifest.json').exists();write(OUT/(name+'.json'),value)
        else:assert json.loads((OUT/(name+'.json')).read_text('utf8'))==value
    if not prepare and(OUT/'merge_manifest.json').exists():
        for p in json.loads((OUT/'merge_manifest.json').read_text('utf8'))['outputs']:assert sha(ROOT/p['path'])==p['sha256']
    print(json.dumps(dict(status='passed',checks=len(checks),database_sha256=digest,numeric_material_values=summary['cumulative_numeric_material_facts'],raw_untouched=813),ensure_ascii=False))
    return summary


def seal():
    assert not(OUT/'merge_manifest.json').exists();verify(False)
    from verify_source_chain_v13 import run
    run(False)
    paths=[p for p in OUT.rglob('*')if p.is_file()]+[ROOT/'data/literature_v13.py',ROOT/'tools/extract_source_series_v13.py',ROOT/'tools/verify_source_series_v13.py',ROOT/'tools/verify_source_chain_v13.py']
    write(OUT/'merge_manifest.json',dict(version='literature_pool_v13',parent_sha256=PSHA,outputs=[dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p),bytes=p.stat().st_size)for p in sorted(paths)],model_fits=0,formal_cycling_admissions=0,scientific_goal_complete=False))
    write(ROOT/'data/current_literature.json',dict(version='literature_pool_v13',directory=OUT.relative_to(ROOT).as_posix(),database_file=DB.name,sha256=sha(DB),api_module='data.literature_v13',scope='Four partial own-source scopes; ordinary3E, ZnS-residue and origin-unverified method references separated; no fit or formal cycle admission'))


if __name__=='__main__':
    if len(sys.argv)!=2 or sys.argv[1]not in ['prepare','verify','seal']:raise SystemExit('prepare/seal once on unsealed batch; verify read-only')
    if sys.argv[1]=='seal':seal()
    else:verify(sys.argv[1]=='prepare')
