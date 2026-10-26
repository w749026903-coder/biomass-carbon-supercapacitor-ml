"""Read-only v17 scientific/lineage checks; prepare/seal only before release."""
from pathlib import Path
from contextlib import closing,redirect_stdout
import collections,csv,io,json,math,re,sqlite3,sys,xml.etree.ElementTree as E
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tools'))
from extract_multisource_tables_v17 import OUT,DB,PARENT,PSHA,EX,NPC,HC,RH,MIX,sha,write,ro,number,norm
from extract_palm_kernel_v7 import xml_grid
from data.literature_v17 import open_literature_database,TARGETS17,FIELDS17

def verify(prepare=False):
    if prepare:assert not(OUT/'merge_manifest.json').exists()
    digest=sha(DB);spec=json.loads((OUT/'curation_spec.json').read_text('utf8'));checks=[]
    def ck(n,b):assert b,n;checks.append(n)
    ck('parent_SHA',sha(PARENT)==PSHA)
    for r in json.loads((OUT/'protected_inputs.json').read_text('utf8'))['files']:ck('protected:'+r['path'],sha(ROOT/r['path'])==r['sha256']and(ROOT/r['path']).stat().st_size==r['bytes'])
    for r in json.loads((PARENT.parent/'merge_manifest.json').read_text('utf8'))['outputs']:ck('parent_manifest:'+r['path'],sha(ROOT/r['path'])==r['sha256'])
    for s in spec['sources']:
        root=E.parse(ROOT/s['path']).getroot();native={t.get('id'):t for t in root.findall('.//table-wrap')}
        for t in [r for r in spec['tables']if r['doi']==s['doi']]:ck('native_exact_grid:'+t['id'],xml_grid(native[t['id']])==t['grid'])
    # Independent PDF text pass against manually inspected rendered tables.
    from pypdf import PdfReader
    pdf=PdfReader(OUT/'evidence/Extrusion17/CSSC-15-0-s001.pdf')
    pages={p:re.sub(r'\s+',' ',pdf.pages[p-1].extract_text().replace('\uf020',' ').replace('\u00a0',' ')).strip()for p in [3,11,23,28,35,36]}
    for uid,page in [('SI_S1',3),('SI_S2',3),('SI_S3',3),('SI_S4',11),('SI_S5',23),('SI_S6',28),('SI_S7',35)]:
        unit=next(r for r in spec['units']if r['id']==uid)
        for i,row in enumerate(unit['rows'],1):ck('SI_PDF_independent_row:'+uid+':'+str(i),' '.join(row)in pages[page])
    with closing(ro(PARENT))as p,closing(ro(DB))as c:
        p.row_factory=c.row_factory=sqlite3.Row;ck('SQLite_integrity',[r[0]for r in c.execute('pragma integrity_check')]==['ok']);ck('foreign_keys',not c.execute('pragma foreign_key_check').fetchall())
        rawids={r['raw_table_id']for r in spec['tables']};ck('ten_main_candidates',len(rawids)==10)
        for name in [r[0]for r in p.execute("select name from sqlite_master where type='table'and name not like'sqlite_%'")]:
            old={tuple(r)for r in p.execute('select *from "'+name+'"')};new={tuple(r)for r in c.execute('select *from "'+name+'"')}
            if name=='raw_table_queue':
                for a in old:
                    b=next(v for v in new if v[0]==a[0]);idx=[r[1]for r in c.execute('pragma table_info(raw_table_queue)')].index('review_state')
                    ck('raw_queue_row:'+str(a[0]),all(v==b[i]for i,v in enumerate(a)if i!=idx)and (b[idx]=='v17_own_cells_methods_stage_and_conflicts_reviewed'if a[0]in rawids else b[idx]==a[idx]))
            else:ck('all_parent_rows_unchanged:'+name,old<=new)
        for table,delta in [('reviewed_sources',5),('materials',64),('material_facts',707),('capacitance_observations',23),('outcome_observations_v3',87),('synthesis_stages_v3',59),('test_candidates',4),('reviewed_tables',40),('source_scope_decisions',5)]:ck('delta:'+table,c.execute('select count(*)from '+table).fetchone()[0]-p.execute('select count(*)from '+table).fetchone()[0]==delta)
        ck('959_candidates800untouched',c.execute('select count(*)from raw_table_queue').fetchone()[0]==959 and c.execute("select count(*)from raw_table_queue where review_state='automatic_candidate_unreviewed'").fetchone()[0]==800)
        for r in c.execute('select *from cell_extractions_v17'):
            raw=json.loads(c.execute('select cells_json from transcribed_rows where table_key=?and row_ordinal=?',(r['table_key'],r['row_ordinal'])).fetchone()[0])[r['column_ordinal']]
            table,idcol={'fact':('material_facts','fact_id'),'capacitance':('capacitance_observations','observation_id'),'response':('outcome_observations_v3','outcome_id')}[r['kind']]
            dbrow=c.execute('select *from '+table+' where '+idcol+'=?',(r['record_id'],)).fetchone();value=json.loads(dbrow['record_json'])if r['kind']=='response'else dict(dbrow)
            ck('cell_raw_value:'+r['kind']+r['record_id'],value['raw_value']==raw and value['value']==number(raw)and dbrow['table_key']==r['table_key'])
            ck('raw_not_auto_training:'+r['kind']+r['record_id'],dbrow['training_eligible']==0)
        ck('no_full_source_complete',c.execute('select sum(full_source_review_complete)from source_scope_decisions').fetchone()[0]==0)
        ck('no_automatic_cycling_admission',all(not json.loads(r[0])['purpose_reviewed_candidate_ready']for r in c.execute("select record_json from test_candidates where candidate_id like'LP17_%'")))
    from data.literature_v16 import open_literature_database as oldopen
    preflight={};exports={}
    with open_literature_database(DB,digest)as d,oldopen(PARENT,PSHA)as old:
        # Existing inputs keep IDs, values, masks and protocol, regardless of new sources.
        for profile in ['3e','2e_device','native_mineral_3e','2e_author_factor2']:
            before=old.auxiliary_gcd(profile);after={r['observation_id']:r for r in d.auxiliary_gcd(profile)}
            ck('legacy_all_aux_payload:'+profile,all(after[r['observation_id']]==r for r in before))
            bef=old.auxiliary_feature_rows(profile);aft={r['observation_id']:r for r in d.auxiliary_feature_rows(profile)};ck('legacy_feature_masks:'+profile,all(aft[r['observation_id']]==r for r in bef))
        ck('ordinary184_22DOI',len(d.auxiliary_gcd('3e'))==184 and len({r['doi']for r in d.auxiliary_gcd('3e')})==22)
        for mode in ['author_exact','point_mixed','figure_only']:ck('v16_modes_exact:'+mode,d.batch16_rate_matrix(mode)==old.batch16_rate_matrix(mode))
        ck('v15_matrix_exact',d.batch15_matrix()==old.batch15_matrix())
        for mode in ['author_exact','point_mixed','interval_mixed','figure_only']:ck('v14_matrix_exact:'+mode,d.furfural_rate_matrix(mode)==old.furfural_rate_matrix(mode))
        from data.literature_v12 import TARGETS12
        for t in TARGETS12:ck('v12_target_exact:'+t,d.batch12_inputs(t)==old.batch12_inputs(t))
        ck('residue_reference_exact',d.template_residue_matrix()==old.template_residue_matrix()and d.interface_reference_reports()==old.interface_reference_reports())
        for target,count in zip(TARGETS17,[8,6,1]):
            rows=d.batch17_inputs(target);m=d.batch17_matrix(target);ck('purpose_count:'+target,len(rows)==len(m['y'])==count)
            ck('unique_nominal_tests:'+target,len(set(m['physical_test_groups']))==len(rows))
            ck('source_weights:'+target,all(math.isclose(sum(w for g,w in zip(m['groups'],m['sample_weight'])if g==f),1)for f in set(m['groups'])))
            ck('missing_masks:'+target,all((v is None)==mask for rr,mm in zip(m['X'],m['missing_mask'])for v,mask in zip(rr,mm)))
            ck('no_fit_impute:'+target,not m['imputed']and not m['training_authorized']and m['estimators_fitted']==0)
            for r in rows:ck('bound_reported_conditions:'+r['observation_id'],r['method']=='GCD'and r['unit']=='F/g'and r['current_A_g']is not None and r['conditions']['current_mass_basis']=='author_reported_unknown_not_inferred'and r['conditions']['target_stage']=='fresh_reported_GCD_rate_test')
            preflight[target]=dict(rows=count,source_families=m['source_families'],missing_cells=sum(sum(mask)for mask in m['missing_mask']),fields=m['feature_names'],imputed=False,model_fits=0)
            exports[target]=(rows,m)
        x=d.canonical_material_features_v13(EX,'LMK-1');ck('LMK_BET_frozen','BET_surface_area_m2_g'not in x['values']and 'BET_surface_area_m2_g'in x['excluded'])
        f=d.facts(doi=EX,sample='LMK-1');ck('LMK_two_values_kept',{r['value']for r in f if r['field_name']=='BET_surface_area_m2_g'}=={2934,3037})
        x=d.canonical_material_features_v13(EX,'LUK-BM');ck('BM_not_extrusion_defaults',all(f not in x['values']for f in ['extrusion_screw_speed_rpm','extrusion_barrel_temperature_C','extrusion_feed_rate_g_min']))
        x=d.canonical_material_features_v13(EX,'LUK-4');ck('Ar_N2_separate',x['values']['BET_surface_area_m2_g']==3326 and x['values']['Ar_BET_surface_area_m2_g']==1955 and x['values']['total_pore_volume_cm3_g']==1.783 and x['values']['Ar_total_pore_volume_cm3_g']==1.121)
        ck('ND_not_zero',all(r['value']is None for r in d.facts(doi=EX)if r['review_status']=='not_detected_limit_unreported'))
        ck('raw_stage_not_final',d.canonical_material_features_v13(EX,'LUK-4 polymer')['values']['XPS_N_at_pct']==13.76 and x['values']['XPS_N_at_pct']==2.76)
        x=d.canonical_material_features_v13(NPC,'NPC-700-2-2');ck('NPC_precise_BET_XPS',x['values']['BET_surface_area_m2_g']==1498.4 and x['values']['XPS_C_at_pct']==87.7 and x['values']['XPS_N_at_pct']==7.37)
        ck('all_ten_Raman',len([r for r in d.facts(doi=NPC)if r['field_name']=='Raman_ID_IG'])==10)
        x=d.canonical_material_features_v13(HC,'AHC-CL-TU');ck('EA_XPS_wt_distinct',x['values']['bulk_EA_N_wt_pct']==3.25 and x['values']['XPS_N_wt_pct']==3.2 and 'XPS_N_at_pct'not in x['values'])
        ck('HC2E_voltage_unknown',all(r['conditions']['voltage_lower_V']is None and r['conditions']['voltage_upper_V']is None for r in d.batch17_inputs(TARGETS17[1])if r['doi']==HC))
        x=d.canonical_material_features_v13(RH,'RHPC-1000');ck('Rice_no_fabricated_BET','BET_surface_area_m2_g'not in x['values']and'surface_area_as_printed_m3_g'not in x['values']and x['values']['total_pore_volume_cm3_g']==.52)
        r=next(r for r in d.batch17_inputs()if r['doi']==RH);ck('Rice_GCD_not_CV',r['value']==78.7 and r['current_A_g']==.5 and r['conditions']['voltage_lower_V']==-.9 and r['conditions']['numeric_SD']is None)
        test=next(r for r in d.tests()if r['candidate_id']=='LP17_Rice_CV');ck('Rice_cycle_method_CV',test['record']['method']=='CV'and test['record']['reported_current_A_g']is None and test['record']['scan_rate_mV_s']==200)
        mix=d.canonical_material_features_v13(MIX,'ABPC-4');ck('MIX_bulk_not_XPS',mix['values']['bulk_EA_N_wt_pct']==2.19 and'XPS_N_at_pct'not in mix['values'])
        test=next(r for r in d.tests()if r['candidate_id']=='LP17_ABPC4');ck('MIX_CE_role_raw_kept',test['record']['retention_pct']==100 and test['record']['retention_relation']=='approx'and test['record']['coulombic_efficiency_pct']==95.08 and test['record']['conflicting_original_retention_claim']==95.08)
        ck('MIX_highj_dissent_excluded',all(not(r['doi']==MIX and r['current_A_g']==30)for r in d.batch17_inputs(TARGETS17[1])))
        ck('HC_existing_endpoint_link',d.batch17_cycle_identity_links()[0]['record']['existing_endpoint_id']=='candidate:TE011')
        ck('new_sources_not_full',len(d.batch17_sources())==5 and all(not r['record']['full_source_review_complete']for r in d.batch17_sources()))
        ck('expanded259_22DOI',len(d.expanded_graph_3e_matrix()['y'])==259 and d.expanded_graph_3e_matrix()['source_families']==22)
        # Direct exports retain every feature, null and raw target. No fill or fit.
        for idx,(target,(rows,m))in enumerate(exports.items(),1):
            file=OUT/('purpose_inputs_v17_'+str(idx)+'.csv');cols=['observation_id','doi','sample','target_name','target_F_g','source_family','source_weight','physical_test_group','source_path','source_sha256','locator']+FIELDS17
            if prepare:
                with file.open('w',encoding='utf-8-sig',newline='')as stream:
                    w=csv.DictWriter(stream,fieldnames=cols);w.writeheader()
                    for i,r in enumerate(rows):w.writerow(dict(observation_id=r['observation_id'],doi=r['doi'],sample=r['sample_name'],target_name=target,target_F_g=r['value'],source_family=m['groups'][i],source_weight=m['sample_weight'][i],physical_test_group=m['physical_test_groups'][i],source_path=r['source_path'],source_sha256=r['source_sha256'],locator=r['locator'],**dict(zip(FIELDS17,m['X'][i]))))
            with file.open(encoding='utf-8-sig',newline='')as stream:out=list(csv.DictReader(stream))
            ck('CSV:'+target,len(out)==len(rows)and all(e['observation_id']==r['observation_id']and float(e['target_F_g'])==r['value']and all((e[f]=='')==(v is None)for f,v in zip(FIELDS17,m['X'][i]))for i,(e,r)in enumerate(zip(out,rows))))
        # Recomputed current counts; inherited historical summary aliases corrected here.
        count=lambda t:d.connection.execute('select count(*)from '+t).fetchone()[0]
        summary=json.loads((PARENT.parent/'summary.json').read_text('utf8'))
        for k in list(summary):
            if k.startswith('new_')and isinstance(summary[k],int):summary[k]=0
        aux=[r for p in ['3e','2e_device','native_mineral_3e','2e_author_factor2']for r in d.auxiliary_gcd(p)]
        numeric=d.connection.execute('select count(*)from material_facts where value is not null').fetchone()[0]
        summary.update(cumulative_reviewed_source_publications=count('source_scope_decisions'),cumulative_materials=count('materials'),cumulative_selected_material_cells=count('material_facts'),cumulative_numeric_material_facts=numeric,unreported_material_cells=count('material_facts')-numeric,new_materials=64,new_numeric_material_facts=631,new_material_facts=707,new_null_material_facts=76,reviewed_table_units=194,reviewed_evidence_units=393,actual_distinct_reviewed_table_keys=count('reviewed_tables'),distinct_database_table_keys=count('reviewed_tables'),extraction_units_v3_count=count('extraction_units_v3'),database_extraction_units_v3=count('extraction_units_v3'),reviewed_evidence_units_definition='393 cumulative declared evidence units;379 actual reviewed table keys/362 extraction_units_v3;194 physical table units. New40units=10native main tables+8SI tables+22bound prose/figure transcriptions. Not393 independent physical tables.',raw_candidates_touched=159,raw_candidates_untouched=800,capacitance_records=count('capacitance_observations'),numeric_capacitance_values=d.connection.execute('select count(*)from capacitance_observations where value is not null').fetchone()[0],cycling_candidates=count('test_candidates'),scientific_issues=count('scientific_issues'),synthesis_materials=count('synthesis_stages_v3'),response_outcomes=count('outcome_observations_v3'),new_source_response_records=87,new_response_records=87,new_capacitance_reports=23,new_own_main_tables=10,new_own_SI_tables=8,new_cycle_candidates=4,new_source_scopes=5,new_collective_annotations=2,new_3e_purpose_inputs=8,new_separate_factor2_inputs=6,new_separate_organic_factor4_inputs=1,auxiliary_aqueous_3e_GCD_rows=184,auxiliary_ordinary_3e_DOI_groups=22,auxiliary_purpose_reviewed_input_rows=len(aux),auxiliary_independent_DOI_groups=len({r['doi']for r in aux}),expanded_3e_with_graph_rows=259,expanded_3e_with_graph_DOI_groups=22,cumulative_numeric_curve_samples=275,new_nominal_graph_conditions=0,new_approximate_conditions_beyond_author_points=0,scope_note='Five own-source scopes,64staged registrations,707facts(631numeric/76null),23capacitance reports and87responses.8newordinary3E inputs plus separate6factor2 and1organicfactor4. No cycling admissions, full-source completion or fitting.')
    ck('readonly_DB_unchanged',sha(DB)==digest)
    report=dict(status='passed',database_sha256=digest,check_count=len(checks),checks=sorted(checks),scientific_goal_complete=False,formal_cycling_admissions=0,model_fits=0)
    for name,value in [('summary',summary),('verification',report),('model_inputs_preflight',preflight)]:
        if prepare:write(OUT/(name+'.json'),value)
        else:assert json.loads((OUT/(name+'.json')).read_text('utf8'))==value,name
    if not prepare and(OUT/'merge_manifest.json').exists():
        for r in json.loads((OUT/'merge_manifest.json').read_text('utf8'))['outputs']:assert sha(ROOT/r['path'])==r['sha256'],r['path']
    print(json.dumps({k:v for k,v in report.items()if k!='checks'},ensure_ascii=False))

def seal():
    assert not(OUT/'merge_manifest.json').exists();verify(False)
    from verify_multisource_chain_v17 import run
    run(False)
    paths=[p for p in OUT.rglob('*')if p.is_file()]+[ROOT/'data/literature_v17.py',ROOT/'tools/extract_multisource_tables_v17.py',ROOT/'tools/verify_multisource_tables_v17.py',ROOT/'tools/verify_multisource_chain_v17.py']
    write(OUT/'merge_manifest.json',dict(version='literature_pool_v17',parent_sha256=PSHA,outputs=[dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p),bytes=p.stat().st_size)for p in sorted(paths)],formal_cycling_admissions=0,model_fits=0,scientific_goal_complete=False))
    write(ROOT/'data/current_literature.json',dict(version='literature_pool_v17',directory=OUT.relative_to(ROOT).as_posix(),database_file=DB.name,sha256=sha(DB),api_module='data.literature_v17',scope='Five own-source scopes with allmain tables,8SI tables,64staged materials and15separate-purpose inputs; no full-source completion or cycle admission/fitting'))

if __name__=='__main__':
    if len(sys.argv)!=2 or sys.argv[1]not in ['prepare','verify','seal']:raise SystemExit('prepare/seal before release only; verify is read-only')
    if sys.argv[1]=='seal':seal()
    else:verify(sys.argv[1]=='prepare')
