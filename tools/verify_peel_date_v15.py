"""Read-only numerical, provenance, stage, source isolation and parent-chain checks."""
from pathlib import Path
from contextlib import closing,redirect_stdout
import collections,csv,io,json,math,sqlite3,sys,zipfile
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tools'))
from extract_peel_date_v15 import OUT,DB,PARENT,PSHA,PE,DA,PE_DIR,PATHS,NAMES,sha,write,ro,number
from data.literature_v15 import open_literature_database

def inspect(prepare=False):
    digest=sha(DB);checks=[]
    def ck(name,yes):assert yes,name;checks.append(name)
    ck('parent_SHA',sha(PARENT)==PSHA)
    spec=json.loads((OUT/'curation_spec.json').read_text('utf8'));protected=json.loads((OUT/'protected_inputs.json').read_text('utf8'))['files']
    for p in protected:ck('protected:'+p['path'],sha(ROOT/p['path'])==p['sha256']and(ROOT/p['path']).stat().st_size==p['bytes'])
    for p in json.loads((PARENT.parent/'merge_manifest.json').read_text('utf8'))['outputs']:ck('parent_manifest:'+p['path'],sha(ROOT/p['path'])==p['sha256'])
    with zipfile.ZipFile(OUT/'evidence/DatePalm_original_assets.zip')as z:
        ck('six_original_date_images',len([n for n in z.namelist()if n.endswith('.jpg')])==6)
        for n in z.namelist():
            if n.endswith('.jpg'):ck('date_archive_exact:'+n,(OUT/'evidence'/n).read_bytes()==z.read(n))
    with zipfile.ZipFile(PE_DIR/'supplementary_package.zip')as z:
        for n in range(1,10):
            name='nanomaterials-14-00836-g'+str(n).zfill(3)+'.jpg';members=[x for x in z.namelist()if x.rsplit('/',1)[-1]==name];ck('peel_original_image:'+name,len(members)==1 and z.read(members[0])==(PE_DIR/'figures'/name).read_bytes())
        si=[x for x in z.namelist()if x.endswith('-s001.zip')];ck('peel_original_SI_package',len(si)==1)
        with zipfile.ZipFile(io.BytesIO(z.read(si[0])))as inner:
            names=[n for n in inner.namelist()if n.endswith('.pdf')];ck('SI_exact_archive_member',len(names)==1 and inner.read(names[0])==(PE_DIR/'nanomaterials-2978200-supplementary.pdf').read_bytes())
    with closing(ro(PARENT))as old,closing(ro(DB))as c:
        old.row_factory=c.row_factory=sqlite3.Row
        ck('sqlite_integrity',[r[0]for r in c.execute('pragma integrity_check')]==['ok']);ck('foreign_keys',not c.execute('pragma foreign_key_check').fetchall())
        rawids={t['raw_table_id']for t in spec['tables']}
        for t in [r[0]for r in old.execute("select name from sqlite_master where type='table' and name not like 'sqlite_%'")]:
            before={tuple(r)for r in old.execute('select *from "'+t+'"')};after={tuple(r)for r in c.execute('select *from "'+t+'"')}
            if t=='raw_table_queue':
                olds={r['table_id']:dict(r)for r in old.execute('select *from raw_table_queue')};news={r['table_id']:dict(r)for r in c.execute('select *from raw_table_queue')};ck('raw_queue_same959ids',set(olds)==set(news)and len(news)==959)
                for k,r in olds.items():
                    expected=dict(r)
                    if k in rawids:expected['review_state']='v15_declared_own_scope_methods_and_disputes_retained'
                    ck('raw_queue_exact_scope:'+k,news[k]==expected and news[k]['training_eligible']==0)
            else:ck('all_parent_rows_retained:'+t,before<=after)
        def count(t,where=''):return c.execute('select count(*)from '+t+(' where '+where if where else'')).fetchone()[0]
        for t,delta in [('reviewed_sources',2),('materials',14),('material_facts',156),('capacitance_observations',24),('outcome_observations_v3',38),('synthesis_stages_v3',12),('test_candidates',2),('scientific_issues',12),('reviewed_tables',21),('extraction_units_v3',21),('auxiliary_gcd_reviews_v3',20)]:ck('exact_delta:'+t,count(t)-old.execute('select count(*)from '+t).fetchone()[0]==delta)
        ck('numeric_facts2447',count('material_facts','value is not null')==2447);ck('allfacts2539',count('material_facts')==2539)
        for kind,table,keyname in [('fact','material_facts','fact_id'),('capacitance','capacitance_observations','observation_id'),('response','outcome_observations_v3','outcome_id')]:
            for receipt in c.execute('select *from cell_extractions_v15 where kind=?',(kind,)):
                raw=json.loads(c.execute('select cells_json from transcribed_rows where table_key=?and row_ordinal=?',(receipt['table_key'],receipt['row_ordinal'])).fetchone()[0])[receipt['column_ordinal']];r=c.execute('select *from '+table+' where '+keyname+'=?',(receipt['record_id'],)).fetchone();record=json.loads(r['record_json'])if kind=='response'else dict(r)
                ck('source_cell:'+kind+receipt['record_id'],record['value']==number(raw)and record['raw_value']==raw)
                if kind!='response':ck('cell_position:'+kind+receipt['record_id'],r['table_key']==receipt['table_key']and r['row_ordinal']==receipt['row_ordinal']and r['column_ordinal']==receipt['column_ordinal'])
        rawleft=count('raw_table_queue',"review_state='automatic_candidate_unreviewed'");ck('810_untouched',rawleft==810)
    with open_literature_database(DB,digest)as db:
        from data.literature_v14 import open_literature_database as open_old
        with open_old(PARENT,PSHA)as old:
            for p,expected in [('3e',176),('2e_device',5),('native_mineral_3e',5),('2e_author_factor2',6)]:
                newrows=db.auxiliary_feature_rows(p);ck('auxiliary_count:'+p,len(newrows)==expected);ck('old_auxiliary_exact:'+p,[r for r in newrows if r['doi']not in [PE,DA]]==old.auxiliary_feature_rows(p))
            for mode,n in [('author_exact',4),('point_mixed',46),('interval_mixed',48),('figure_only',46)]:ck('furfural_mode_unchanged:'+mode,db.furfural_rate_matrix(mode)==old.furfural_rate_matrix(mode)and len(db.furfural_rate_inputs(mode))==n)
            from data.literature_v12 import TARGETS12
            for t in TARGETS12:ck('v12_target_unchanged:'+t,db.batch12_inputs(t)==old.batch12_inputs(t))
            ck('old_residue_reference_wetting_unchanged',db.template_residue_matrix()==old.template_residue_matrix()and db.interface_reference_reports()==old.interface_reference_reports()and db.wettability_series_v13()==old.wettability_series_v13())
            ck('v13_named_scope55_unchanged',db.report_groups_v13()==old.report_groups_v13()and len(db.report_groups_v13())==55)
        caps=[r for r in db.capacitances()if r['doi']in [PE,DA]];fresh=[r for r in db.auxiliary_gcd('3e')if r['doi']in [PE,DA]];ck('24reports22conditions20fresh',len(caps)==24 and len({r['conditions']['physical_test_group']for r in caps})==22 and len(fresh)==20)
        ck('no_SI_repeat_or_postcycle_in_fresh',all(r['conditions']['target_stage']=='fresh_reported_GCD_rate_test'and r['conditions'].get('report_kind')!='repeat_SI_same_test'for r in fresh))
        ck('P35_16_rate_values',[r['value']for r in sorted((r for r in fresh if r['sample_name']=='PAC-700'),key=lambda r:r['current_A_g'])]==[211,201.4,188,182.2,177.3,173,169.5,165.5]and[r['value']for r in sorted((r for r in fresh if r['sample_name']=='SAC-600'),key=lambda r:r['current_A_g'])]==[219.7,196,187,180.4,175,170,165.2,161])
        ck('working_AgAgCl_dissent_retained',all(r['conditions']['reference_electrode']=='Ag/AgCl'and'SCE'in r['conditions']['reference_electrode_dissent']for r in fresh if r['doi']==DA))
        components=[r['record']for r in db.batch15_components()];ck('32components_distinct_scales',len(components)==32 and sum(r['absolute_at_pct']is not None for r in components)==26 and sum(r['relative_envelope_pct']is not None for r in components)==6)
        audit=[]
        for s in ['PAC-700','SAC-600']:
            features=db.canonical_material_features_v13(PE,s)['values']
            for element,total in [('C',80.84 if s=='PAC-700'else 78.66),('N',3.5 if s=='PAC-700'else 4.62),('S',.61 if s=='PAC-700'else .59),('O',15.05 if s=='PAC-700'else 16.13)]:
                selected=[r for r in components if r['sample']==s and r['name'].startswith(element+'-')];summed=sum(r['absolute_at_pct']for r in selected);ck('element_total_not_component_normalized:'+s+element,features['XPS_'+element+'_at_pct']==total);audit.append(dict(sample=s,element=element,reported_total_at_pct=total,reported_component_sum_at_pct=round(summed,6),difference=round(summed-total,6),normalized=False))
            ck('four_zero_component_disputes:'+s,all('XPS_component_'+name+'_at_pct'not in features for name in ['S_II','S_IV']))
        ck('PAC_C_sum_dissent_009',audit[0]['difference']==.09)
        for s in NAMES[DA]:
            features=db.canonical_material_features_v13(DA,s)['values'];ck('near_one_Raman_not_numeric:'+s,'Raman_ID_IG'not in features)
            ck('DFT_DA_separate:'+s,'total_pore_volume_cm3_g'not in features and features['DA_micropore_volume_cm3_g']>features['DFT_pore_volume_cm3_g'])
            ck('coating_not_active_mass:'+s,'active_mass_loading_mg_cm2'not in features and features['electrode_coating_mass_loading_mg_cm2']in [1.4,1.8])
        mat=db.batch15_matrix();ck('20inputs_two_families',len(mat['y'])==20 and mat['source_families']==2)
        ck('source_weight_balance',all(math.isclose(sum(w for w,g in zip(mat['sample_weight'],mat['groups'])if g==family),1)for family in set(mat['groups'])))
        ck('no_imputation_or_fit',not mat['imputed']and mat['estimators_fitted']==0 and all(m==(v is None)for row,mask in zip(mat['X'],mat['missing_mask'])for v,m in zip(row,mask)))
        for i,g in enumerate(mat['groups']):
            values=dict(zip(mat['feature_names'],mat['X'][i]))
            if g=='doi:'+DA:ck('Date_unknown_process_and_pore_masks:'+str(i),values['carbonization_temperature_C']is None and values['total_pore_volume_cm3_g']is None and values['Raman_ID_IG']is None)
        candidates=[r['record']for r in db.tests()if r['candidate_id'].startswith('LP15_')];ck('two_cycle_candidates_window_unknown',len(candidates)==2 and all(r['system']=='2E_symmetric'and r['cycle_voltage_lower_V']is None and not r['purpose_reviewed_candidate_ready']for r in candidates))
        links=db.batch15_cycle_identity_links();ck('PAC_existing_endpoint_not_counted_twice',len(links)==1 and links[0]['record']['existing_endpoint_id']=='candidate:V05:034'and not links[0]['record']['formal_admission_changed'])
        ck('16_figure_scopes_and8collective_annotations',len(db.batch15_figures())==16 and len(db.batch15_annotations())==8)
        ck('source_partial_not_full',len(db.batch15_sources())==2 and all(not r['record']['full_source_review_complete']for r in db.batch15_sources()))
        ck('source_quarantine_all_records',all(db.is_quarantined_source('doi:'+doi,[doi])for doi in [PE,DA])and not db.is_quarantined_source(PE,[DA]))
        if prepare:
            assert not(OUT/'merge_manifest.json').exists()
            with(OUT/'fresh_gcd_inputs_v15.csv').open('w',encoding='utf-8-sig',newline='')as f:
                fields=['observation_id','doi','sample_name','source_family','physical_test_group','reported_current_A_g','target_F_g','target_kind','source_balanced_weight','source_path','source_sha256'];writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
                for r,weight in zip([next(r for r in fresh if r['observation_id']==oid)for oid in mat['observation_ids']],mat['sample_weight']):writer.writerow(dict(observation_id=r['observation_id'],doi=r['doi'],sample_name=r['sample_name'],source_family=db.isolation_group(r['source_group']),physical_test_group=r['conditions']['physical_test_group'],reported_current_A_g=r['current_A_g'],target_F_g=r['value'],target_kind=r['status'],source_balanced_weight=weight,source_path=r['source_path'],source_sha256=r['source_sha256']))
        with(OUT/'fresh_gcd_inputs_v15.csv').open(encoding='utf-8-sig',newline='')as f:export=list(csv.DictReader(f))
        ck('CSV20source_group_targets',len(export)==20 and{r['observation_id']for r in export}==set(mat['observation_ids'])and all(float(r['target_F_g'])==next(v for oid,v in zip(mat['observation_ids'],mat['y'])if oid==r['observation_id'])for r in export))
    ck('read_only_hash',sha(DB)==digest)
    summary=json.loads((PARENT.parent/'summary.json').read_text('utf8'))
    for k in list(summary):
        if k.startswith('new_')and isinstance(summary[k],int):summary[k]=0
    summary.update(cumulative_reviewed_source_publications=39,cumulative_materials=225,cumulative_selected_material_cells=2539,cumulative_numeric_material_facts=2447,unreported_material_cells=92,new_materials=14,new_numeric_material_facts=154,reviewed_table_units=176,reviewed_evidence_units=349,raw_candidates_touched=149,raw_candidates_untouched=810,capacitance_records=856,numeric_capacitance_values=852,cycling_candidates=71,scientific_issues=156,synthesis_materials=188,response_outcomes=2566,new_source_response_records=38,new_response_records=38,new_capacitance_reports=24,new_own_main_tables=3,new_own_SI_tables=1,auxiliary_aqueous_3e_GCD_rows=176,auxiliary_purpose_reviewed_input_rows=192,auxiliary_independent_DOI_groups=19,auxiliary_ordinary_3e_DOI_groups=18,actual_distinct_reviewed_table_keys=335,extraction_units_v3_count=318,new_XPS_component_records=32,new_collective_annotations=8,new_cycle_candidates=2,new_training_admissions=0,formal_cycling_admissions=0,model_fits=0,scope_note='Two additional primary sources: all own main tables/selected prose/SI and all16figure scopes;20new own3E inputs,2device candidates lack physical cyclingwindow; sourcefullreview incomplete')
    report=dict(status='passed',database_sha256=digest,check_count=len(checks),checks=checks,new_materials=14,new_facts=156,new_numeric_facts=154,new_capacitance_reports=24,new_fresh_3e_inputs=20,new_DOI_groups=2,formal_cycling_admissions=0,model_fits=0,scientific_goal_complete=False)
    for name,value in [('verification',report),('summary',summary),('model_inputs_preflight',mat),('XPS_component_sum_audit',audit)]:
        if prepare:write(OUT/(name+'.json'),value)
        else:assert json.loads((OUT/(name+'.json')).read_text('utf8'))==value,name
    if not prepare and(OUT/'merge_manifest.json').exists():
        for p in json.loads((OUT/'merge_manifest.json').read_text('utf8'))['outputs']:assert sha(ROOT/p['path'])==p['sha256']
    print(json.dumps({k:v for k,v in report.items()if k!='checks'},ensure_ascii=False))

def seal():
    assert not(OUT/'merge_manifest.json').exists();inspect(False)
    from verify_peel_date_chain_v15 import run
    run(False)
    paths=[p for p in OUT.rglob('*')if p.is_file()]+[ROOT/'data/literature_v15.py',ROOT/'tools/extract_peel_date_v15.py',ROOT/'tools/verify_peel_date_v15.py',ROOT/'tools/verify_peel_date_chain_v15.py']
    write(OUT/'merge_manifest.json',dict(version='literature_pool_v15',parent_sha256=PSHA,outputs=[dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p),bytes=p.stat().st_size)for p in sorted(paths)],model_fits=0,formal_cycling_admissions=0,scientific_goal_complete=False))
    write(ROOT/'data/current_literature.json',dict(version='literature_pool_v15',directory=OUT.relative_to(ROOT).as_posix(),database_file=DB.name,sha256=sha(DB),api_module='data.literature_v15',scope='Two primary source series,20new3E inputs,method-qualified composition/pore models; no full-source completion or fit'))

if __name__=='__main__':
    if len(sys.argv)!=2 or sys.argv[1]not in ['prepare','verify','seal']:raise SystemExit('prepare/seal on unsealed batch once; verify read-only')
    if sys.argv[1]=='seal':seal()
    else:inspect(sys.argv[1]=='prepare')
