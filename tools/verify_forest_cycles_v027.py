"""Read-only evidence and old-cohort verification; prepare/seal only before release."""
from contextlib import closing,redirect_stdout
from unittest.mock import patch
import csv,io,json,math,sqlite3,sys,xml.etree.ElementTree as E
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tools'))
from release_forest_cycles_v027 import OUT,DB,PARENT,PSHA,LIT,LSHA,SOURCE,SSHA,FIG,POLICY,DOI,PROFILES,JOBS,sha,write,load,clean
EXPECTED={'reported_3e':(45,33),'reported_3e_residue_sensitivity':(46,34),'reported_3e_sensitivity':(54,40),'reported_3e_all_years':(49,36),'reported_2e':(31,25),'reported_2e_residue':(36,27),'reported_2e_approx':(38,29),'reported_2e_all_years':(33,27)}
def verify(prepare=False):
    if prepare:assert not(OUT/'merge_manifest.json').exists()
    checks=[]
    def ck(name,ok):assert ok,name;checks.append(name)
    ck('parent_SHA',sha(PARENT/'cycling_v0_26.sqlite')==PSHA);ck('own_source_SHA',sha(SOURCE)==SSHA)
    for r in json.loads((OUT/'protected_inputs.json').read_text('utf8'))['files']:ck('protected:'+r['path'],sha(ROOT/r['path'])==r['sha256'])
    for folder in [PARENT,LIT]:
        for r in json.loads((folder/'merge_manifest.json').read_text('utf8'))['outputs']:ck('old_manifest:'+r['path'],sha(ROOT/r['path'])==r['sha256'])
    r=E.parse(SOURCE).getroot();tables={t.get('id'):t for t in r.findall('.//table-wrap')}
    from extract_palm_kernel_v7 import xml_grid
    t1=xml_grid(tables['tab1']);t3=xml_grid(tables['tab3']);snp=json.loads((OUT/'source_review.json').read_text('utf8'));snap={r['after']['endpoint_id']:r for r in snp['records']}
    with closing(sqlite3.connect(DB.as_uri()+'?mode=ro',uri=True))as c:
        c.row_factory=sqlite3.Row;ck('SQLite_integrity',[r[0]for r in c.execute('pragma integrity_check')]==['ok']);ck('foreign_keys',not c.execute('pragma foreign_key_check').fetchall());ck('only3existing_endpoints',len(c.execute('select *from reviewed_endpoints_v27').fetchall())==3);ck('two_profiles_each',len(c.execute('select *from profile_membership_v27').fetchall())==6)
        for ev in c.execute('select *from evidence_v27'):ck('evidence_SHA:'+ev['evidence_id'],sha(ROOT/ev['path'])==ev['sha256'])
        changed=list(c.execute('select *from changes_v27'))
        for q in changed:
            key=q['endpoint_id'];ck('before_kept:'+str(q['change_id']),json.loads(q['before_json'])==snap[key]['before'].get(q['field_name']));ck('after_receipt:'+str(q['change_id']),json.loads(q['after_json'])==snap[key]['after'][q['field_name']])
    new=load(OUT,'verification_forest_v027');parent=load(PARENT,'verification_forest_parent_v026');core={};cohorts={};csv_rows=[]
    with new.Database()as d,parent.Database()as old:
        a=d.fetch('all_review').rows;b=old.fetch('all_review').rows;aa={r['endpoint_id']:r for r in a};bb={r['endpoint_id']:r for r in b};keys={x[0]for x in JOBS}
        ck('286same_observationIDs',len(a)==len(b)==286 and set(aa)==set(bb));ck('185raw_sourcegroups',len({r['source_group']for r in a})==185)
        for key in sorted(bb):
            if key not in keys:ck('other_observation_exact:'+key,aa[key]==bb[key])
        for row,(key,s,ret,bet,tga)in enumerate(JOBS,2):
            before,after=snap[key]['before'],d.by_endpoint(key);ck('source_snapshot:'+key,after==snap[key]['after']);ck('native_BET_retention:'+key,float(t1[row-1][4]['raw'])==after['BET_m2_g']==bet and float(t3[row-1][6]['raw'])==ret==after['retention_pct']);ck('raw_BET_not_ashfree:'+key,after['BET_m2_g']!=float(t1[row-1][5]['raw']))
            same=['endpoint_id','source_group','source_year','material_id','material_key_v11','test_id','curve_group','sample_name','retention_pct','cycle_count','reported_current_A_g','concentration_mol_L','electrolyte','system','method','metric_kind','retention_relation','baseline_cycle','canonical_current_A_g','N_at_pct','O_at_pct']
            ck('same_label_identity_current:'+key,all(after[f]==before[f]for f in same));ck('unknown_physics_and_index_not_guessed:'+key,after['canonical_current_A_g']is None and after['baseline_cycle']is None and after['current_mass_basis']=='author_reported_unknown_not_inferred')
            ck('no_old_membership_backdating:'+key,all(after.get(f)==before.get(f)for f in ['admission_profiles_v11','admission_profiles_v12','admission_profiles_v13','admission_profiles_v17','review_disposition_v12','review_disposition_v15']))
            ck('actual_scope_residue_only:'+key,after['admission_profiles_v27']==PROFILES and after['ordinary_2e_excluded_v27']and after['material_scope_v27']=='biomass_carbon_with_author_reported_ash_AlOH3_impurity');ck('baseline_has_no_exact_index:'+key,json.loads(after['baseline_reference'])['exact_reference_cycle']is None)
            for f in ['BET_m2_g','cycle_voltage_lower_V','cycle_voltage_upper_V','baseline_reference']:
                ev=d.evidence(key,f);ck('new_binding_selected:'+key+f,any(r.get('review_version')=='v0.27'and r['currently_selected']==1 for r in ev)and all(r.get('currently_selected')==0 for r in ev if r.get('review_version')!='v0.27'))
            ck('old_holds_retained:'+key,d.holds(key)['previous_holds']==old.holds(key));ck('no_open_core_issues_in_declared_scope:'+key,d.holds(key)['open_issues']==[])
            ck('not_in_fixed39_or_41:'+key,not any(r['endpoint_id']==key for r in old.reviewed_pending_batch(True)))
        for profile,(n,g)in EXPECTED.items():
            ds=d.fetch(profile);os=old.fetch(profile);m=ds.feature_matrix();om=os.feature_matrix();cohorts[profile]=dict(rows=len(ds.rows),source_families=len(set(m['groups'])));ck('cohort:'+profile,len(ds.rows)==n and len(set(m['groups']))==g)
            index={r['endpoint_id']:i for i,r in enumerate(ds.rows)}
            for i,r in enumerate(os.rows):
                j=index[r['endpoint_id']];ck('old_matrix_Xy:'+profile+r['endpoint_id'],m['X'][j]==om['X'][i]and m['y'][j]==om['y'][i]and m['sample_weight'][j]==om['sample_weight'][i])
                for k in ['label_relations','label_evidence_kind','label_reading_bound_pp','baseline_references']:
                    if k in om:ck('old_metadata:'+k+profile+r['endpoint_id'],m[k][j]==om[k][i])
            for family in sorted(set(m['groups'])):ck('source_weight:'+profile+family,math.isclose(sum(w for w,g0 in zip(m['sample_weight'],m['groups'])if g0==family),1))
            if profile not in PROFILES:ck('other_profile_exact:'+profile,ds.rows==os.rows and m==om)
            else:
                ck('only3added_to_residue:'+profile,{r['endpoint_id']for r in ds.rows}-{r['endpoint_id']for r in os.rows}==keys)
                for key in keys:
                    i=index[key];ck('forest_source_weight1third:'+profile+key,math.isclose(m['sample_weight'][i],1/3))
            ck('no_missing_core_or_fit:'+profile,not any(v is None for row in m['X']for v in row)and not m['training_authorized']);core[profile]=dict(rows=n,features=m['feature_names'],missing_core_values=0,model_fits=0)
            if profile=='reported_2e_residue':csv_rows=[dict(endpoint_id=r['endpoint_id'],**{f:r[f]for f in ds.features},retention_pct=r['retention_pct'],source_group=r['source_group'],source_weight=m['sample_weight'][i])for i,r in enumerate(ds.rows)if r['endpoint_id']in keys]
        strict_ids={r['endpoint_id']for r in d.fetch('strict_2e').rows}
        ck('no_strict_canonical_approval',not keys&strict_ids)
        ck('new_yearfilter_applied',not keys&{r['endpoint_id']for r in d.fetch('reported_2e_residue',year_min=2024).rows})
        ck('fixed37pending_41history_exact',d.reviewed_pending_batch()==old.reviewed_pending_batch()and d.reviewed_pending_batch(True)==old.reviewed_pending_batch(True)and len(d.reviewed_pending_batch())==37 and len(d.reviewed_pending_batch(True))==41)
        ck('Cycas4mask_exact',d.feature_conflicts_v24()==old.feature_conflicts_v24()and len(d.feature_conflicts_v24())==4);ck('above100_not_clipped',max(r['retention_pct']for r in a if isinstance(r.get('retention_pct'),(int,float)))>100)
        row=d.by_endpoint(JOBS[0][0]);features=list(d.fetch(PROFILES[0]).features)
        for name,test in [('missingBET',dict(row,BET_m2_g=None)),('missingbaseline',dict(row,baseline_reference=None)),('no_membership',dict(row,admission_profiles_v27=[])),('invalidwindow',dict(row,cycle_voltage_upper_V=0))]:
            try:new.Dataset(PROFILES[0],[test],features).feature_matrix()
            except new.DataNotReady:ck('reject:'+name,True)
            else:raise AssertionError('Invalid input accepted: '+name)
        try:new.Dataset('reported_2e',[row],features).feature_matrix()
        except new.DataNotReady:ck('ordinary_scope_rejected',True)
        else:raise AssertionError('Residue mixed into ordinary main')
        from data.literature_v22 import open_literature_database
        with open_literature_database(LIT/'literature_material_pool_v22.sqlite',LSHA)as lit:
            payload=[]
            for kind,rows in [('fact',lit.facts(DOI)),('capacitance',lit.capacitances(DOI)),('material',lit.materials(DOI))]:
                for r in rows:payload.append(dict(kind=kind,group=r.get('source_group')or'doi:'+r['doi']))
            payload += [dict(kind='cycling',group=r['source_group'])for r in a if r['source_group']=='doi:'+DOI]
            payload += [dict(kind='candidate',group=r['record']['source_group'])for r in lit.tests()if r['record']['source_group']=='doi:'+DOI]
            for r in payload:ck('entire_Forest_holdout:'+r['kind']+str(len(checks)),lit.is_quarantined_source(r['group'],['doi:'+DOI])and lit.isolation_group(r['group'])=='doi:'+DOI)
    # Historical reports must see their sealed cycling version, not the new default pointer.
    with patch('data.cycling_db.open_database',lambda *a,**k:parent.Database()),redirect_stdout(io.StringIO()):
        from verify_four_sources_v22 import verify as old_lit_verify,chain as old_chain
        old_lit_verify(False);old_chain(False)
    ck('v22_and_earlier_pinned_historical_chain',True)
    report=dict(status='passed',database_sha256=sha(DB),parent_sha256=PSHA,check_count=len(checks),checks=sorted(checks),ordinary_2e=cohorts['reported_2e'],residue_2e=cohorts['reported_2e_residue'],fixed_original_records=39,resolved_original=2,pending_original=37,pending_source_groups=23,new_endpoints=0,promoted_existing_endpoints=3,new_admissions=3,model_fits=0,scientific_goal_complete=False)
    summary=dict(version='cycling_v0.27',new_endpoints=0,new_purpose_admissions=3,promoted_existing_endpoints=3,ordinary_main_new_admissions=0,residue_only_new_admissions=3,new_independent_source_families_in_residue=1,cycling_observations=286,source_groups=185,fixed_original_records=39,resolved_original=2,pending_original=37,pending_source_groups=23,cohorts=cohorts,model_fits=0,all_records_admitted=False,scope='Existingthreeforestwaterendpoints inresidue/approx nestedpurposes, noordinaryorcanonicalapproval')
    for name,value in [('verification',report),('model_inputs_preflight',core),('cohort_counts',cohorts),('summary',summary)]:
        if prepare:write(OUT/(name+'.json'),value)
        else:assert json.loads((OUT/(name+'.json')).read_text('utf8'))==value,name
    buf=io.StringIO(newline='');w=csv.DictWriter(buf,fieldnames=list(csv_rows[0]),lineterminator='\n');w.writeheader();w.writerows(csv_rows)
    if prepare:(OUT/'new_residue_purpose_rows.csv').write_text(buf.getvalue(),encoding='utf-8-sig',newline='')
    else:assert(OUT/'new_residue_purpose_rows.csv').read_text(encoding='utf-8-sig')==buf.getvalue()
    if(OUT/'merge_manifest.json').exists():
        for r in json.loads((OUT/'merge_manifest.json').read_text('utf8'))['outputs']:assert sha(ROOT/r['path'])==r['sha256'],r['path']
    print(json.dumps({k:v for k,v in report.items()if k!='checks'}))
def seal():
    assert not(OUT/'merge_manifest.json').exists();verify(False)
    files=[p for p in OUT.rglob('*')if p.is_file()]+[ROOT/'tools/release_forest_cycles_v027.py',Path(__file__).resolve()]
    write(OUT/'merge_manifest.json',dict(version='cycling_v0.27',parent_database_sha256=PSHA,outputs=[dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p),bytes=p.stat().st_size)for p in sorted(files)],new_endpoints=0,new_admissions=3,residue_only=True,fixed_original_pending=37,model_fits=0,scientific_goal_complete=False))
    write(ROOT/'data/current_database.json',dict(version='cycling_v0.27',version_directory=OUT.name,database_file=DB.name,sha256=sha(DB),parent_database_file=(PARENT/'cycling_v0_26.sqlite').relative_to(ROOT).as_posix(),default_profile='reported_3e',stage='three_existing_forest_residue_only_reviews',ready_for_training_inputs=True,research_training_authorized=False,all_records_admitted=False))
if __name__=='__main__':
    mode=sys.argv[1]
    if mode=='seal':seal()
    elif mode in ['prepare','verify']:verify(mode=='prepare')
    else:raise SystemExit('prepare/verify/seal')
