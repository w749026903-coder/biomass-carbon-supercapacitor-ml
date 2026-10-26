"""Independent delta, scientific-boundary, history and model-input verification."""
import json,math,sqlite3,sys
from contextlib import closing
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tools'))
from release_mango_leather_cycles_v025 import OUT,DB,PARENT,PSHA,LIT,LDB,MA,LE,JOBS,PROFILES,sha,write,ro,load


def verify(prepare=False):
    from data.literature_v13 import open_literature_database
    checks=[]
    def ck(name,passed):
        if not passed:raise AssertionError(name)
        checks.append(name)
    digest=sha(DB)
    for p in json.loads((OUT/'protected_inputs.json').read_text('utf8')):ck('protected:'+p['path'],sha(ROOT/p['path'])==p['sha256'])
    for folder in [PARENT,LIT]:
        for p in json.loads((folder/'merge_manifest.json').read_text('utf8'))['outputs']:ck('payload:'+p['path'],sha(ROOT/p['path'])==p['sha256'])
    with closing(ro(DB))as c:
        c.row_factory=sqlite3.Row;ck('integrity',c.execute('pragma integrity_check').fetchone()[0]=='ok');ck('foreignkeys',not c.execute('pragma foreign_key_check').fetchall());ck('two_new_endpoints',c.execute('select count(*)from reviewed_endpoints_v25').fetchone()[0]==2)
        for r in c.execute('select *from evidence_v25'):ck('evidence_hash:'+r['evidence_id'],sha(ROOT/r['path'])==r['sha256'])
        ck('7_report_decisions',c.execute('select count(*)from report_decisions_v25').fetchone()[0]==7)
    child=load(OUT,'_v025_scientific_verify');parent=load(PARENT,'_v024_pinned_mango_leather');matrices={};counts={}
    with child.Database()as new,parent.Database()as old,open_literature_database(LDB,sha(LDB))as lit:
        before={r['endpoint_id']:r for r in old.fetch('all_review').rows};after={r['endpoint_id']:r for r in new.fetch('all_review').rows}
        ck('286_observations',len(after)==286);ck('185_raw_groups',len({r['source_group']for r in after.values()})==185);ck('only_two_new_IDs',set(after)-set(before)=={job[1]for job in JOBS})
        for key,row in before.items():ck('old_row_exact:'+key,after[key]==row)
        expected={'reported_3e':(44,32),'reported_3e_residue_sensitivity':(45,33),'reported_3e_sensitivity':(53,39),'reported_2e':(31,25),'reported_2e_residue':(33,26),'reported_2e_approx':(35,28),'reported_3e_all_years':(48,35),'reported_2e_all_years':(33,27)}
        for profile,want in expected.items():
            ds=new.fetch(profile);m=ds.feature_matrix();matrices[profile]=m;counts[profile]=dict(rows=len(ds.rows),source_families=len(set(m['groups'])));ck('counts:'+profile,(len(ds.rows),len(set(m['groups'])))==want)
            oldds=old.fetch(profile);oldids={r['endpoint_id']for r in oldds.rows};add={key for cid,key,doi,s in JOBS if profile in PROFILES['2E_symmetric'if doi==MA else'3E']};ck('exact_membership:'+profile,{r['endpoint_id']for r in ds.rows}==oldids|add)
            om=oldds.feature_matrix();position={r['endpoint_id']:i for i,r in enumerate(ds.rows)}
            for i,r in enumerate(oldds.rows):
                j=position[r['endpoint_id']];ck('old_X_y_group_weight:'+profile+r['endpoint_id'],all(m[f][j]==om[f][i]for f in ['X','y','groups','sample_weight']))
            for group in set(m['groups']):ck('family_weight:'+profile+group,abs(sum(w for g,w in zip(m['groups'],m['sample_weight'])if g==group)-1)<1e-12)
            for i,fold in enumerate(ds.source_folds(len(set(m['groups'])))):ck('fold:'+profile+str(i),not{m['groups'][j]for j in fold['train']}&{m['groups'][j]for j in fold['test']})
            mm=new.method_specific_material_matrix(profile);ck('no_imputation_or_fit:'+profile,mm['estimators_fitted']==0 and not mm['imputed']and all(mask==(v is None)for row,masks in zip(mm['X'],mm['missing_mask'])for v,mask in zip(row,masks)))
            ck('no_ID_or_response_X:'+profile,not{'endpoint_id','source_group','source_family_group_v23','retention_pct','coulombic_efficiency_pct','capacitance_F_g','EIS_Rs'}&set(mm['feature_names']))
        candidates={r['candidate_id']:r for r in lit.tests()};links={r['candidate_id']:r for r in new.literature_links()}
        for cid,key,doi,sample in JOBS:
            row=new.by_endpoint(key);raw=candidates[cid]['record'];ck('candidate_crosslink:'+key,links[cid]['endpoint_id']==key and links[cid]['literature_database_sha256']==sha(LDB)and row['literature_material_key']==candidates[cid]['material_key'])
            for f in ['retention_pct','cycle_count','reported_current_A_g','cycle_voltage_lower_V','cycle_voltage_upper_V','electrolyte','concentration_mol_L','reference_electrode','system','method','baseline_reference']:ck('candidate_value:'+key+f,row[f]==raw[f])
            ck('unknown_mass_and_baseline_preserved:'+key,row['current_mass_basis']is None and row['canonical_current_A_g']is None and row['baseline_cycle']is None)
            ck('actual_own_label_proof:'+key,any(e['selected']and e['value']==row['retention_pct']and e['path'].endswith('.jpg')for e in new.evidence(key,'retention_pct')))
            ck('review_version_not_backdated:'+key,new.holds(key)['review_version']=='v0.25'and'admission_profiles_v13'not in row)
            ck('new_material_system:'+key,all(json.loads(r['applies_to_systems_json'])==[row['system']]for r in new.material_properties(row['material_id'])if r.get('review_version')=='v0.25'))
            for change in new.field_changes(key):ck('new_row_change:'+key+change['field_name'],change['before']is None and change['after']==row[change['field_name']]and change['operation']=='insert_new_reviewed_endpoint')
            for p in PROFILES[row['system']]:
                ds=new.fetch(p);one=next(r for r in ds.rows if r['endpoint_id']==key)
                for f,v in [('reported_current_A_g',None),('BET_m2_g',0),('method','CV'),('retention_pct',float('nan')),('cycle_voltage_upper_V',-1),('baseline_reference',None),('admission_profiles_v25',[])]:
                    bad=dict(one);bad[f]=v
                    try:child.Dataset(p,[bad],list(ds.features)).feature_matrix()
                    except child.DataNotReady:ck('reject:'+key+p+f,True)
                    else:raise AssertionError('Invalid new purpose accepted:'+p+f)
                growth=dict(one,retention_pct=101.7);ck('positive_growth_not_probability_clipped:'+key+p,child.Dataset(p,[growth],list(ds.features)).feature_matrix()['y']==[101.7])
        mango=new.by_endpoint(JOBS[0][1]);leather=new.by_endpoint(JOBS[1][1])
        ck('Mango_own_2E_core',(mango['retention_pct'],mango['cycle_count'],mango['reported_current_A_g'],mango['cycle_voltage_lower_V'],mango['cycle_voltage_upper_V'],mango['concentration_mol_L'])==(79.3,100000,2,0,1.2,3))
        ck('Mango_BET_working_and_abstract_retained',mango['BET_m2_g']==1348.5 and{e['value']for e in new.evidence(JOBS[0][1],'BET_m2_g')}=={1348.5,1348.9})
        ck('Mango_device_mass_not_3E',mango['active_mass_mg_v14']==5 and mango['mass_loading_mg_cm2']is None)
        ck('Mango_thermal_no_activation_guess',mango['carbonization_temperature_C']==900 and mango['carbonization_duration_h']is None and mango['carbonization_heating_rate_C_min']==10 and mango['activation_temperature_C']is None)
        ck('Mango_XRD_unit_conversion',mango['XRD_d002_nm']==.35 and 'approximate'in mango['XRD_d002_nm_status'])
        ck('Mango_CE_kept_as_response',[(e['value'],e['selected'])for e in new.evidence(JOBS[0][1],'coulombic_efficiency_pct')]==[(79.3,0),(65,1)])
        ck('Leather_own_3E_core',(leather['retention_pct'],leather['cycle_count'],leather['reported_current_A_g'],leather['cycle_voltage_lower_V'],leather['cycle_voltage_upper_V'],leather['reference_electrode'])==(99.2,10000,10,0,.5,'Ag/AgCl_saturated_KCl'))
        ck('Leather_current_dissent_retained',any(e['value']==1 and not e['selected']for e in new.evidence(JOBS[1][1],'reported_current_A_g')))
        ck('Leather_BET_precision_retained',leather['BET_m2_g']==2214.5 and{e['value']for e in new.evidence(JOBS[1][1],'BET_m2_g')}=={2214.5,2215})
        ck('Leather_basis_unreported',leather['XPS_N_reported_pct']==31.12 and leather['XPS_O_reported_pct']==8.91 and leather['XPS_percentage_basis']=='unreported'and leather['N_at_pct']is None and leather['O_at_pct']is None)
        mm=new.method_specific_material_matrix('reported_3e');i=mm['endpoint_ids'].index(JOBS[1][1])
        for f in ['XPS_N_atomic_pct_v15','XPS_N_weight_pct_v15','XPS_O_atomic_pct_v15','XPS_O_weight_pct_v15']:ck('Leather_method_mask:'+f,mm['X'][i][mm['feature_names'].index(f)]is None)
        ck('Leather_stages_not_summed',leather['precarbonization_temperature_C']==400 and leather['precarbonization_duration_h']==1 and leather['activation_temperature_C']==800 and leather['activation_duration_h']==1 and leather['heating_rate_C_min']is None and leather['active_mass_mg_v14']is None)
        ck('fixed38_exact',new.reviewed_pending_batch()==old.reviewed_pending_batch()and len(new.reviewed_pending_batch())==38)
        ck('15_old_freezes',sum(r.get('review_version')=='v0.21'for r in new.field_changes(include_history=True))==15)
        ck('Cycas4_alias_masks_exact',new.feature_conflicts_v24()==old.feature_conflicts_v24())
        ck('101point7_original_not_clipped',new.by_endpoint('v22:NFACc_2E_C10000')['retention_pct']==101.7)
        ck('families_unchanged',new.source_family_rules()==old.source_family_rules());ck('old_links_plus2',len(new.literature_links())==len(old.literature_links())+2)
        ck('year_filter_does_not_promote',all(r['source_year']<=2025 for r in new.fetch('reported_2e',year_max=2025).rows)and JOBS[1][1]not in{r['endpoint_id']for r in new.fetch('reported_3e',year_max=2025).rows})
        ck('commercial3_candidates_stay_pending',not any(r['candidate_id'].startswith('LP13_Interface')for r in new.literature_links()))
    ck('readonly_hash',sha(DB)==digest)
    report=dict(status='passed',database_sha256=digest,check_count=len(checks),checks=sorted(checks),observations=286,raw_source_groups=185,profiles=counts,new_endpoints=2,new_materials=2,promoted_existing_endpoints=0,new_purpose_admissions=2,new_source_families=2,original_fixed_resolved=1,original_fixed_pending=38,legacy_feature_cells_frozen=15,cycle_v24_conflict_aliases=4,model_fits=0,full_goal_complete=False)
    if prepare:
        assert not(OUT/'merge_manifest.json').exists();write(OUT/'verification.json',report);write(OUT/'summary.json',{k:v for k,v in report.items()if k!='checks'});write(OUT/'model_inputs_preflight.json',matrices)
    else:
        assert json.loads((OUT/'verification.json').read_text('utf8'))==report;assert json.loads((OUT/'model_inputs_preflight.json').read_text('utf8'))==matrices
        if(OUT/'merge_manifest.json').exists():
            for p in json.loads((OUT/'merge_manifest.json').read_text('utf8'))['outputs']:assert sha(ROOT/p['path'])==p['sha256']
    print(json.dumps({k:v for k,v in report.items()if k!='checks'},ensure_ascii=False))


def seal():
    assert not(OUT/'merge_manifest.json').exists()
    from verify_mango_leather_chain_v025 import run
    run(False)
    paths=[p for p in OUT.rglob('*')if p.is_file()]+[ROOT/'tools/release_mango_leather_cycles_v025.py',ROOT/'tools/verify_mango_leather_cycles_v025.py',ROOT/'tools/verify_mango_leather_chain_v025.py']
    write(OUT/'merge_manifest.json',dict(version='cycling_v0.25',parent_sha256=PSHA,outputs=[dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p),bytes=p.stat().st_size)for p in sorted(paths)],model_fits=0,scientific_goal_complete=False))
    write(ROOT/'data/current_database.json',dict(version='cycling_v0.25',version_directory=OUT.relative_to(ROOT).as_posix(),database_file=DB.name,sha256=sha(DB),parent_database_file=(PARENT/'cycling_v0_24.sqlite').relative_to(ROOT).as_posix(),default_profile='reported_3e',stage='own_Mango2E_Leather3E_tests_with_source_report_variants_retained',ready_for_training_inputs=True,research_training_authorized=False,all_records_admitted=False))


if __name__=='__main__':
    if len(sys.argv)!=2 or sys.argv[1]not in ['prepare','verify','seal']:raise SystemExit('prepare/seal once; verify read-only')
    if sys.argv[1]=='seal':seal()
    else:verify(sys.argv[1]=='prepare')
