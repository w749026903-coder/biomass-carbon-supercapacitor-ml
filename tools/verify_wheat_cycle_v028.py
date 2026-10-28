"""Read-only endpoint admission, immutable history, negative-case and cross-task checks."""
from pathlib import Path
from contextlib import closing
import csv,io,json,math,sqlite3,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tools'))
from release_wheat_cycle_v028 import OUT,DB,PARENT,PSHA,LIT,LDB,LSHA,SOURCE,SSHA,FIG,DOI,KEY,CID,PROFILE,sha,write,load
EXPECTED={'reported_3e':(45,33),'reported_3e_residue_sensitivity':(46,34),'reported_3e_sensitivity':(54,40),'reported_3e_all_years':(49,36),'reported_2e':(31,25),'reported_2e_residue':(36,27),'reported_2e_approx':(38,29),'reported_2e_all_years':(34,28)}

def verify(prepare=False):
    if prepare:assert not(OUT/'merge_manifest.json').exists()
    checks=[]
    def ck(name,ok):assert ok,name;checks.append(name)
    ck('parent_sha',sha(PARENT/'cycling_v0_27.sqlite')==PSHA);ck('literal_source_sha',sha(SOURCE)==SSHA);ck('literature_sha',sha(LDB)==LSHA)
    for r in json.loads((OUT/'protected_inputs.json').read_text('utf8')):ck('protected:'+r['path'],sha(ROOT/r['path'])==r['sha256'])
    for folder in [PARENT,LIT]:
        for r in json.loads((folder/'merge_manifest.json').read_text('utf8'))['outputs']:ck('old_manifest:'+r['path'],sha(ROOT/r['path'])==r['sha256'])
    snap=json.loads((OUT/'source_review.json').read_text('utf8'));identity=json.loads((OUT/'identity_review.json').read_text('utf8'))
    with closing(sqlite3.connect(DB.as_uri()+'?mode=ro',uri=True))as c:
        c.row_factory=sqlite3.Row;ck('integrity',[r[0]for r in c.execute('pragma integrity_check')]==['ok']);ck('foreign_keys',not c.execute('pragma foreign_key_check').fetchall());ck('one_endpoint_one_purpose',len(c.execute('select *from reviewed_endpoints_v28').fetchall())==1 and list(map(tuple,c.execute('select *from profile_membership_v28')))==[(KEY,PROFILE)])
        for ev in c.execute('select *from evidence_v28'):ck('evidence_sha:'+ev['evidence_id'],sha(ROOT/ev['path'])==ev['sha256'])
        changes=list(c.execute('select *from changes_v28'));ck('full_field_creation_history',len(changes)==len(snap['row']))
        for r in changes:ck('new_not_rewrite:'+r['field_name'],r['operation']=='insert_new_endpoint_field'and r['before_json']=='null'and json.loads(r['after_json'])==snap['row'][r['field_name']])
    child=load(OUT,'_v028_verify');parent=load(PARENT,'_v027_verify_v028');cohorts={};export=None
    with child.Database()as d,parent.Database()as old:
        aa={r['endpoint_id']:r for r in d.fetch('all_review').rows};bb={r['endpoint_id']:r for r in old.fetch('all_review').rows};ck('287_and_186_rawgroups',len(aa)==287 and len({r['source_group']for r in aa.values()})==186);ck('only_one_new_ID',set(aa)-set(bb)=={KEY}and set(bb)<=set(aa))
        for key,r in bb.items():ck('all_old_observations_exact:'+key,aa[key]==r)
        row=d.by_endpoint(KEY);ck('new_snapshot_matches',row==snap['row']);ck('own_cycle_exact',row['retention_pct']==98.59 and row['cycle_count']==30000 and row['reported_current_A_g']==5 and row['source_year']==2022 and row['system']=='2E_symmetric');ck('unknown_physics_and_index',row['canonical_current_A_g']is None and row['baseline_cycle']is None and row['current_mass_basis']=='author_reported_unknown_not_inferred'and not row['mass_basis_checked'])
        ck('no_fresh_capacity_as_reference',row['baseline_reference']=='author_initial_capacitance_exact_reference_cycle_unknown'and row['label_reading_bound_pp']is None);ck('own_final_BET_not_prechar',row['BET_m2_g']==2721 and row['BET_m2_g']!=524);ck('atomic_not_weight_and_no_Nzero',row['O_at_pct']==row['XPS_O_reported_pct']==10.66 and row['XPS_percentage_basis']=='atomic_explicit'and row['N_at_pct']is None)
        for profile,(n,g)in EXPECTED.items():
            ds=d.fetch(profile);os=old.fetch(profile);m=ds.feature_matrix();om=os.feature_matrix();index={r['endpoint_id']:i for i,r in enumerate(ds.rows)};ck('cohort:'+profile,len(ds.rows)==n and len(set(m['groups']))==g);cohorts[profile]=dict(rows=n,source_families=g,model_fits=0)
            for i,r in enumerate(os.rows):
                j=index[r['endpoint_id']];ck('old_X_y_weight:'+profile+r['endpoint_id'],m['X'][j]==om['X'][i]and m['y'][j]==om['y'][i]and m['sample_weight'][j]==om['sample_weight'][i])
            if profile!=PROFILE:ck('other_profile_exact:'+profile,ds.rows==os.rows and m==om)
            else:
                ck('just_one_all_years_addition',set(index)-{r['endpoint_id']for r in os.rows}=={KEY});i=index[KEY];export=dict(endpoint_id=KEY,**{f:row[f]for f in ds.features},retention_pct=row['retention_pct'],source_family=m['groups'][i],source_weight=m['sample_weight'][i]);ck('new_weight_one',m['sample_weight'][i]==1 and m['groups'][i]=='doi:'+DOI)
            for family in sorted(set(m['groups'])):ck('weights:'+profile+family,math.isclose(sum(w for w,g0 in zip(m['sample_weight'],m['groups'])if g0==family),1))
            ck('core_no_missing_or_fit:'+profile,not any(v is None for x in m['X']for v in x)and not m['training_authorized'])
        ck('strict_physical_not_admitted',KEY not in{r['endpoint_id']for r in d.fetch('strict_2e').rows});ck('legacy_year_gate_kept',KEY not in{r['endpoint_id']for r in d.fetch('reported_2e').rows});ck('filter_excludes_2022',KEY not in{r['endpoint_id']for r in d.fetch(PROFILE,year_min=2023).rows});ck('filter_includes_2022',KEY in{r['endpoint_id']for r in d.fetch(PROFILE,year_min=2022,year_max=2022).rows})
        ck('fixed_original37_and_history41_exact',d.reviewed_pending_batch()==old.reviewed_pending_batch()and d.reviewed_pending_batch(True)==old.reviewed_pending_batch(True)and len(d.reviewed_pending_batch())==37 and len(d.reviewed_pending_batch(True))==41);ck('Cycas4_masks_exact',d.feature_conflicts_v24()==old.feature_conflicts_v24());ck('old_real_above100_kept',d.by_endpoint('v22:NFACc_2E_C10000')['retention_pct']==101.7);ck('linked_candidate_not_duplicate',len(d.literature_links())==len(old.literature_links())+1 and next(r for r in d.literature_links()if r['candidate_id']==CID)['endpoint_id']==KEY)
        ck('baseline_no_cycle1_invention',all(e['value']!=1 for e in d.evidence(KEY,'baseline_cycle')));ck('actual_device_window_receipt',all(e['path'].endswith('nanomaterials-12-03804-g008.jpg')and'3E' in e['note']for f in ['cycle_voltage_lower_V','cycle_voltage_upper_V']for e in d.evidence(KEY,f)))
        features=d.fetch(PROFILE).features
        for label,update in [('noBET',{'BET_m2_g':None}),('zeroBET',{'BET_m2_g':0}),('noReference',{'baseline_reference':None}),('emptyMembership',{'admission_profiles_v28':[]}),('wrongYear',{'source_year':2026}),('boolYear',{'source_year':True}),('badWindow',{'cycle_voltage_upper_V':0}),('wrongMethod',{'method':'CV'}),('wrongSystem',{'system':'3E'}),('noCurrent',{'reported_current_A_g':None}),('negativeTarget',{'retention_pct':-1}),('NaNtarget',{'retention_pct':float('nan')}),('wrongMetric',{'metric_kind':'coulombic_efficiency'}),('wrongMaterial',{'material_scope_v28':'MnO2_composite'})]:
            try:child.Dataset(PROFILE,[dict(row,**update)],list(features)).feature_matrix()
            except child.DataNotReady:ck('reject:'+label,True)
            else:raise AssertionError('Invalid new record accepted:'+label)
        try:child.Dataset('reported_2e',[row],list(features)).feature_matrix()
        except child.DataNotReady:ck('reject_2022_in_legacy_profile',True)
        else:raise AssertionError('2022 entered original main purpose')
        material=d.method_specific_material_matrix(PROFILE);i=material['endpoint_ids'].index(KEY);ck('XPS_Oatomic10p66_only',material['X'][i][material['feature_names'].index('XPS_O_atomic_pct_v15')]==10.66 and material['X'][i][material['feature_names'].index('XPS_O_weight_pct_v15')]is None and material['X'][i][material['feature_names'].index('XPS_N_atomic_pct_v15')]is None)
    from data.literature_v25 import open_literature_database,PURPOSES25
    with open_literature_database(LDB,LSHA)as lit:
        caps=lit.capacitances(DOI);curves=lit.sampled_curves(DOI);rows=[r for p in PURPOSES25 for r in lit.batch25_rate_inputs('point_mixed',p)];ck('all_own_aux_and_cycles_same_family',len(caps)==29 and len(curves)==20 and len(rows)==20 and all(lit.is_quarantined_source(r['source_group'],['doi:'+DOI])for r in caps+rows));ck('reported_capacity_does_not_change_cyclelabel',all(r['cyclic_retention_training_admitted']is False for r in rows));ck('old_candidate_literal_window_kept_unknown',next(r for r in lit.tests()if r['candidate_id']==CID)['record']['voltage_upper_V']is None)
    ck('identity_uncertainty_retained',identity['direct_DOI_matches']==[] and len(identity['unresolved_parent_endpoint_ids'])==6 and identity['whole_DOI_task_isolation'])
    report=dict(status='passed',database_sha256=sha(DB),parent_sha256=PSHA,literature_sha256=LSHA,check_count=len(checks),checks=sorted(checks),profiles=cohorts,observations=287,raw_source_groups=186,new_endpoints=1,new_source_families=1,new_admissions=1,admitted_profiles=[PROFILE],original_resolved=2,original_pending=37,original_pending_sources=23,model_fits=0,scientific_goal_complete=False,cross_task_holdout=dict(doi=DOI,capacitance_reports=29,graph_captures=20,nominal_rate_conditions=20,all_tasks_one_family=True))
    report.update(new_purpose_admissions=1,ordinary_main_new_admissions=0,residue_only_new_admissions=0,cross_year_only_new_admissions=1,promoted_existing_endpoints=0)
    preflight=dict(status='passed',profile=PROFILE,rows=34,source_families=28,new_row=export,missing_required_values=0,model_fits=0,training_authorized=False,note='Input readiness only; no generalization or adequacy claim. 2022 test excluded from2023..2026main, unknown physicalcurrent retained.')
    for name,value in [('verification',report),('summary',{k:v for k,v in report.items()if k!='checks'}),('model_inputs_preflight',preflight)]:
        if prepare:write(OUT/(name+'.json'),value)
        else:assert json.loads((OUT/(name+'.json')).read_text('utf8'))==value,name
    b=io.StringIO(newline='');w=csv.DictWriter(b,fieldnames=list(export),lineterminator='\n');w.writeheader();w.writerow(export);p=OUT/'new_all_years_2e_training_input.csv'
    if prepare:p.write_text(b.getvalue(),encoding='utf-8-sig',newline='')
    else:assert p.read_text('utf-8-sig')==b.getvalue()
    if(OUT/'merge_manifest.json').exists():
        for r in json.loads((OUT/'merge_manifest.json').read_text('utf8'))['outputs']:assert sha(ROOT/r['path'])==r['sha256'],r['path']
    print(json.dumps({k:v for k,v in report.items()if k!='checks'},ensure_ascii=False))

def seal():
    assert not(OUT/'merge_manifest.json').exists();verify(False);paths=[p for p in OUT.rglob('*')if p.is_file()]+[ROOT/'tools/release_wheat_cycle_v028.py',Path(__file__).resolve()]
    write(OUT/'merge_manifest.json',dict(version='cycling_v0.28',parent_sha256=PSHA,outputs=[dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p),bytes=p.stat().st_size)for p in sorted(paths)],new_endpoints=1,new_admissions=1,model_fits=0,scientific_goal_complete=False))
    write(ROOT/'data/current_database.json',dict(version='cycling_v0.28',version_directory=OUT.name,database_file=DB.name,sha256=sha(DB),parent_database_file=(PARENT/'cycling_v0_27.sqlite').relative_to(ROOT).as_posix(),default_profile='reported_3e',stage='one_wheat_2022_existing_all_years_2e_purpose',ready_for_training_inputs=True,research_training_authorized=False,all_records_admitted=False))
if __name__=='__main__':
    action=sys.argv[1]if len(sys.argv)==2 else''
    if action=='prepare':verify(True)
    elif action=='verify':verify(False)
    elif action=='seal':seal()
    else:raise SystemExit('prepare/seal once before release; verify readonly')
