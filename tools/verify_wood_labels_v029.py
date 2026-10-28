"""Read-only verification of old-label preservation, specific-source selection and purpose changes."""
from pathlib import Path
from contextlib import closing
import csv,io,json,math,sqlite3,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tools'))
from release_wood_labels_v029 import OUT,DB,PARENT,PSHA,LIT,LDB,LSHA,SOURCE,SSHA,FIG,GCD,BETFIG,DOI,PROFILES,JOBS,sha,write,load
EXPECTED={'reported_3e':(47,34),'reported_3e_residue_sensitivity':(48,35),'reported_3e_sensitivity':(54,40),'reported_3e_all_years':(51,37),'reported_2e':(31,25),'reported_2e_residue':(36,27),'reported_2e_approx':(38,29),'reported_2e_all_years':(34,28)}

def verify(prepare=False):
    if prepare:assert not(OUT/'merge_manifest.json').exists()
    checks=[]
    def ck(name,ok):assert ok,name;checks.append(name)
    ck('parent_SHA',sha(PARENT/'cycling_v0_28.sqlite')==PSHA);ck('literal_source_SHA',sha(SOURCE)==SSHA);ck('literature_SHA',sha(LDB)==LSHA)
    for r in json.loads((OUT/'protected_inputs.json').read_text('utf8')):ck('protected:'+r['path'],sha(ROOT/r['path'])==r['sha256'])
    for folder in [PARENT,LIT]:
        for r in json.loads((folder/'merge_manifest.json').read_text('utf8'))['outputs']:ck('old_manifest:'+r['path'],sha(ROOT/r['path'])==r['sha256'])
    snap=json.loads((OUT/'source_review.json').read_text('utf8'));records={r['after']['endpoint_id']:r for r in snap['records']};keys=set(records);promoted={'candidate:TE037','candidate:TE038'}
    with closing(sqlite3.connect(DB.as_uri()+'?mode=ro',uri=True))as c:
        c.row_factory=sqlite3.Row;ck('integrity',[r[0]for r in c.execute('pragma integrity_check')]==['ok']);ck('foreign_keys',not c.execute('pragma foreign_key_check').fetchall());ck('3existing_rows_not_new',len(c.execute('select *from reviewed_endpoints_v29').fetchall())==3);ck('8memberships_onlytwoeligible',len(c.execute('select *from profile_membership_v29').fetchall())==8 and{r[0]for r in c.execute('select endpoint_id from profile_membership_v29')}==promoted)
        for r in c.execute('select *from evidence_v29'):ck('evidence_SHA:'+r['evidence_id'],sha(ROOT/r['path'])==r['sha256'])
        for r in c.execute('select *from changes_v29'):
            rec=records[r['endpoint_id']];ck('before_preserved:'+str(r['change_id']),json.loads(r['before_json'])==rec['before'].get(r['field_name']));ck('after_receipt:'+str(r['change_id']),json.loads(r['after_json'])==rec['after'][r['field_name']])
    child=load(OUT,'_v029_verify');parent=load(PARENT,'_v028_verify_v029');cohorts={};exports=[]
    with child.Database()as d,parent.Database()as old:
        aa={r['endpoint_id']:r for r in d.fetch('all_review').rows};bb={r['endpoint_id']:r for r in old.fetch('all_review').rows};ck('same287observationIDs_186rawsources',set(aa)==set(bb)and len(aa)==287 and len({r['source_group']for r in aa.values()})==186)
        for key,r in bb.items():
            if key not in keys:ck('other_observation_exact:'+key,aa[key]==r)
        identities=['endpoint_id','source_group','source_year','sample_name','material_id','material_key_v11','test_id','curve_group','system','method','cycle_count','reported_current_A_g','canonical_current_A_g','BET_m2_g','electrolyte','concentration_mol_L','reference_electrode','cycle_voltage_lower_V','cycle_voltage_upper_V','baseline_cycle','N_at_pct','O_at_pct','Raman_ID_IG']
        for key,sample,previous,selected,bet in JOBS:
            before,after=records[key]['before'],d.by_endpoint(key);ck('source_snapshot:'+key,after==records[key]['after']);ck('identity_conditions_and_BET_kept:'+key,all(after.get(f)==before.get(f)for f in identities));ck('direct_fig_not_complement:'+key,after['retention_pct']==selected and before['retention_pct']==previous and before['retention_relation']=='derived_complement'and after['retention_relation']=='eq');ck('old_selection_explicit:'+key,after['prior_retention_selection_v29']['value']==previous and after['other_retention_claims_v29'][0]['value']==previous)
            ev=d.evidence(key,'retention_pct');ck('selected_actual_figure:'+key,any(e.get('review_version')=='v0.29'and e['currently_selected']==1 and e['value']==selected and e['path']==FIG.relative_to(ROOT).as_posix()for e in ev));ck('body_dissent_unselected:'+key,any(e.get('review_version')=='v0.29'and e['value']==previous and e['currently_selected']==0 and e['path']==SOURCE.relative_to(ROOT).as_posix()for e in ev));ck('old_selection_not_overwritten:'+key,all(e['currently_selected']==0 for e in ev if e.get('review_version')!='v0.29'))
            ck('no_guessed_physics_orbaselinecycle:'+key,after['canonical_current_A_g']is None and after['baseline_cycle']is None and after['baseline_reference']['cycle_index']is None and after['label_reading_bound_pp']is None);ck('own_jointstage_bound:'+key,after['carbonization_temperature_C']==int(sample[-3:])and after['carbonization_duration_h']==3 and after.get('activation_temperature_C')is None and after.get('activation_duration_h')is None and after['preheat_temperature_C_v29']==110 and after['preheat_duration_h_v29']==2)
            ck('no_membership_backdating:'+key,all(after.get(f)==before.get(f)for f in ['admission_profiles_v11','admission_profiles_v12','admission_profiles_v13','admission_profiles_v17','admission_profiles_v22','review_disposition_v15']))
            ck('previous_holds_preserved:'+key,d.holds(key)['previous_holds']==old.holds(key))
        for profile,(n,g)in EXPECTED.items():
            ds=d.fetch(profile);os=old.fetch(profile);m=ds.feature_matrix();om=os.feature_matrix();index={r['endpoint_id']:i for i,r in enumerate(ds.rows)};ck('cohort:'+profile,len(ds.rows)==n and len(set(m['groups']))==g);cohorts[profile]=dict(rows=n,source_families=g,model_fits=0)
            for i,r in enumerate(os.rows):
                j=index[r['endpoint_id']]
                if r['endpoint_id']not in keys:ck('other_old_X_y_weight:'+profile+r['endpoint_id'],m['X'][j]==om['X'][i]and m['y'][j]==om['y'][i]and m['sample_weight'][j]==om['sample_weight'][i])
                else:ck('old_core_X_same_only_ycorrected:'+profile+r['endpoint_id'],m['X'][j]==om['X'][i]and m['y'][j]==records[r['endpoint_id']]['after']['retention_pct']and m['sample_weight'][j]==om['sample_weight'][i])
            added=set(index)-{r['endpoint_id']for r in os.rows};ck('exact_membership_delta:'+profile,added==(promoted if profile in PROFILES and profile!='reported_3e_sensitivity'else set()))
            if profile not in PROFILES:ck('all_2E_profiles_exact:'+profile,ds.rows==os.rows and m==om)
            for g0 in sorted(set(m['groups'])):ck('source_weight:'+profile+g0,math.isclose(sum(w for gg,w in zip(m['groups'],m['sample_weight'])if gg==g0),1))
            ck('no_missing_required_orfit:'+profile,not any(v is None for x in m['X']for v in x)and not m['training_authorized'])
            if profile=='reported_3e':
                for key in sorted(promoted):i=index[key];r=ds.rows[i];ck('halfsourceweight:'+key,m['sample_weight'][i]==.5);exports.append(dict(endpoint_id=key,**{f:r[f]for f in ds.features},retention_pct=r['retention_pct'],source_family=m['groups'][i],source_weight=m['sample_weight'][i]))
        pending={r['endpoint_id']:r for r in d.reviewed_pending_batch()};history={r['endpoint_id']:r for r in d.reviewed_pending_batch(True)};oldpending={r['endpoint_id']:r for r in old.reviewed_pending_batch()};oldhistory={r['endpoint_id']:r for r in old.reviewed_pending_batch(True)};ck('fixed37_and_41IDs_exact',len(pending)==37 and len(history)==41 and set(pending)==set(oldpending)and set(history)==set(oldhistory));ck('AC500onlyBETpending',pending['candidate:TE036']['open_issues']==['own_numeric_BET']and not pending['candidate:TE036']['approved_profiles']and d.by_endpoint('candidate:TE036')['BET_m2_g']is None)
        for key,r in oldhistory.items():
            if key!='candidate:TE036':ck('other_fixedqueue_review_exact:'+key,history[key]==r)
        ck('two_promotions_outside_original41',not promoted&set(history));ck('AC500no_formal_profile',all('candidate:TE036'not in{r['endpoint_id']for r in d.fetch(p).rows}for p in PROFILES));ck('no_strict_physics_admission',not keys&{r['endpoint_id']for r in d.fetch('strict_3e').rows});ck('Cycas4_masks_exact',d.feature_conflicts_v24()==old.feature_conflicts_v24());ck('trueabove100_notclipped',d.by_endpoint('v22:NFACc_2E_C10000')['retention_pct']==101.7);ck('three_oldlinks_notnewexperiments',len(d.literature_links())==len(old.literature_links())+3)
        r=d.by_endpoint('candidate:TE037');features=d.fetch('reported_3e').features
        for name,update in [('noBET',{'BET_m2_g':None}),('noCurrent',{'reported_current_A_g':None}),('noBaseline',{'baseline_reference':None}),('badWindow',{'cycle_voltage_upper_V':-2}),('CV',{'method':'CV'}),('lossComplement',{'retention_relation':'derived_complement'}),('noMembership',{'admission_profiles_v29':[]}),('wrongYear',{'source_year':2022}),('wrongSystem',{'system':'2E_symmetric'}),('wrongMetric',{'metric_kind':'coulombic_efficiency'}),('NaNtarget',{'retention_pct':float('nan')})]:
            try:child.Dataset('reported_3e',[dict(r,**update)],list(features)).feature_matrix()
            except child.DataNotReady:ck('reject:'+name,True)
            else:raise AssertionError('Invalid current record accepted:'+name)
        try:child.Dataset('reported_3e',[d.by_endpoint('candidate:TE036')],list(features)).feature_matrix()
        except child.DataNotReady:ck('reject_pending_AC500',True)
        else:raise AssertionError('AC500missingBETadmitted')
        ck('year_filter',not keys&{r['endpoint_id']for r in d.fetch('reported_3e',year_min=2025).rows})
        preparation=d.reviewed_preparation_rows_v29();ck('two_preparation_exports_one_DOI',len(preparation)==2 and len({r['source_family_group']for r in preparation})==1);ck('pending_preparation_inspection_only',len(d.reviewed_preparation_rows_v29(True))==3 and not next(r for r in d.reviewed_preparation_rows_v29(True)if r['endpoint_id']=='candidate:TE036')['cycling_purpose_eligible'])
        byprep={r['endpoint_id']:r for r in preparation}
        for row in exports:
            key=row['endpoint_id'];p=byprep[key];ck('own_preparation_feature_export:'+key,p['preparation_values']['carbonization_temperature_C']==records[key]['after']['carbonization_temperature_C']and p['preparation_values']['carbonization_duration_h']==3 and p['preparation_values']['preheat_temperature_C']==110 and p['preparation_values']['preheat_duration_h']==2 and p['preparation_values']['wetting_temperature_C']==25 and p['preparation_values']['wetting_duration_h']==24 and p['preparation_values']['carbonization_N2_flow_mL_min']==100);row.update(p['preparation_values'])
            for field,value in p['preparation_values'].items():ck('each_preparation_field_source:'+key+field,any(e['field_name']==p['source_field_map'][field]and e['value']==value and e['currently_selected']==1 and e['path']==SOURCE.relative_to(ROOT).as_posix()and e['sha256']==SSHA for e in p['evidence']))
    from data.literature_v26 import open_literature_database,TARGETS26
    with open_literature_database(LDB,LSHA)as lit:
        caps=lit.capacitances(DOI);rows=[r for t in TARGETS26 for r in lit.batch26_inputs(t)];ck('six_aux_and_all16reports_same_holdout',len(caps)==16 and len(rows)==6 and all(lit.is_quarantined_source(r['source_group'],['doi:'+DOI])for r in caps+rows));ck('8cycles_shareDOI',len(lit.batch26_cycle_claims())==8 and all(r['record']['source_group']=='doi:'+DOI for r in lit.tests()if r['candidate_id'].startswith('LP26:')))
    report=dict(status='passed',database_sha256=sha(DB),parent_sha256=PSHA,literature_sha256=LSHA,check_count=len(checks),checks=sorted(checks),profiles=cohorts,observations=287,raw_source_groups=186,new_endpoints=0,existing_labels_corrected=3,promoted_existing_endpoints=2,new_purpose_admissions=2,ordinary_main_new_admissions=2,residue_only_new_admissions=0,cross_year_only_new_admissions=0,newly_entering_ordinary3e_source_families=1,original_resolved=2,original_pending=37,original_pending_sources=23,model_fits=0,scientific_goal_complete=False)
    preflight=dict(status='passed',new_ordinary3e_rows=exports,preparation_export=dict(eligible_rows=2,including_pending_inspection_rows=3,DOI_families=1,automatically_appended_to_legacy_material_matrix=False,imputed=False),ordinary3e=dict(rows=47,source_families=34),all_years3e=dict(rows=51,source_families=37),sensitivity3e=dict(rows=54,source_families=40,existing_two_labels_corrected=True),missing_required_values=0,one_DOI_all_tasks_heldout_together=True,no_model_fits=True,not_proof_of_accuracy=True)
    for name,value in [('verification',report),('summary',{k:v for k,v in report.items()if k!='checks'}),('model_inputs_preflight',preflight)]:
        if prepare:write(OUT/(name+'.json'),value)
        else:assert json.loads((OUT/(name+'.json')).read_text('utf8'))==value,name
    b=io.StringIO(newline='');w=csv.DictWriter(b,fieldnames=list(exports[0]),lineterminator='\n');w.writeheader();w.writerows(exports);p=OUT/'promoted_ordinary_3e_training_inputs.csv'
    if prepare:p.write_text(b.getvalue(),encoding='utf-8-sig',newline='')
    else:assert p.read_text('utf-8-sig')==b.getvalue()
    if(OUT/'merge_manifest.json').exists():
        for r in json.loads((OUT/'merge_manifest.json').read_text('utf8'))['outputs']:assert sha(ROOT/r['path'])==r['sha256'],r['path']
    print(json.dumps({k:v for k,v in report.items()if k!='checks'},ensure_ascii=False))

def seal():
    assert not(OUT/'merge_manifest.json').exists();verify(False);paths=[p for p in OUT.rglob('*')if p.is_file()]+[ROOT/'tools/release_wood_labels_v029.py',Path(__file__).resolve()]
    write(OUT/'merge_manifest.json',dict(version='cycling_v0.29',parent_sha256=PSHA,outputs=[dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p),bytes=p.stat().st_size)for p in sorted(paths)],new_endpoints=0,corrected_labels=3,promoted_existing_endpoints=2,model_fits=0,scientific_goal_complete=False))
    write(ROOT/'data/current_database.json',dict(version='cycling_v0.29',version_directory=OUT.name,database_file=DB.name,sha256=sha(DB),parent_database_file=(PARENT/'cycling_v0_28.sqlite').relative_to(ROOT).as_posix(),default_profile='reported_3e',stage='specific_original_graph_labels_over_loss_complements_three_existing_wood_tests',ready_for_training_inputs=True,research_training_authorized=False,all_records_admitted=False))
if __name__=='__main__':
    action=sys.argv[1]if len(sys.argv)==2 else''
    if action=='prepare':verify(True)
    elif action=='verify':verify(False)
    elif action=='seal':seal()
    else:raise SystemExit('prepare/seal once before release; verify readonly')
