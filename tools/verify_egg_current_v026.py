"""Verify existing-endpoint correction, old masks, source quarantine and fixed goal."""
from pathlib import Path
from contextlib import closing,redirect_stdout
from unittest.mock import patch
import collections,importlib.util,io,json,math,sqlite3,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tools'))
from release_egg_current_v026 import OUT,DB,PARENT,PSHA,KEY,DOI,PROFILES,SOURCE,SSHA,sha,write
def module(path,name):
    if name not in sys.modules:
        s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m)
    return sys.modules[name]
def verify(prepare=False):
    if prepare:assert not(OUT/'merge_manifest.json').exists()
    checks=[]
    def ck(n,b):assert b,n;checks.append(n)
    snapshot=json.loads((OUT/'source_review.json').read_text('utf8'));new=module(OUT/'ml_data.py','_verify_cycle026');parent=module(PARENT/'ml_data.py','_verify_cycle025_for026')
    ck('v025_SHA',sha(PARENT/'cycling_v0_25.sqlite')==PSHA);ck('unchanged_main_XML',sha(SOURCE)==SSHA)
    for r in json.loads((OUT/'protected_inputs.json').read_text('utf8')):ck('original:'+r['path'],sha(ROOT/r['path'])==r['sha256'])
    with closing(sqlite3.connect(DB))as c:
        ck('integrity',c.execute('pragma integrity_check').fetchall()==[('ok',)]);ck('foreign_keys',not c.execute('pragma foreign_key_check').fetchall());ck('one_existing_endpoint_delta',c.execute('select endpoint_id from reviewed_endpoints_v26').fetchall()==[(KEY,)]);ck('eleven_changed_fields',c.execute('select count(*)from changes_v26').fetchone()[0]==11)
    with new.Database()as d,parent.Database(PARENT/'cycling_v0_25.sqlite')as old:
        a=d.fetch('all_review').rows;b=old.fetch('all_review').rows;ck('286observations185groups',len(a)==len(b)==286 and len({r['source_group']for r in a})==185);ck('no_insert_or_delete_endpoint',{r['endpoint_id']for r in a}=={r['endpoint_id']for r in b})
        aa={r['endpoint_id']:r for r in a};bb={r['endpoint_id']:r for r in b}
        for key in bb:
            if key!=KEY:ck('unchanged_other_endpoint:'+key,aa[key]==bb[key])
        row=d.by_endpoint(KEY);ck('exact_source_snapshot',row==snapshot['after']);ck('explicit_current10',row['reported_current_A_g']==10 and snapshot['before']['reported_current_A_g']is None);ck('retention_and_othercore_unchanged',all(row[k]==snapshot['before'][k]for k in ['retention_pct','cycle_count','cycle_voltage_lower_V','cycle_voltage_upper_V','BET_m2_g','reference_electrode','electrolyte','source_group','material_id','test_id','curve_group','source_year','baseline_cycle','baseline_reference']))
        ck('canonical_current_unknown_and_optional_N_O_masks',row['canonical_current_A_g']is None and row['N_at_pct']is None and row['O_at_pct']is None)
        ck('no_historical_profile_backdate',all(row[k]==snapshot['before'][k]for k in ['admission_profiles_v13','admission_profiles_v17','review_disposition_v12','review_disposition_v15']))
        counts={};core={}
        expected={'reported_3e':(45,33),'reported_3e_residue_sensitivity':(46,34),'reported_3e_sensitivity':(54,40),'reported_3e_all_years':(49,36),'reported_2e':(31,25),'reported_2e_residue':(33,26),'reported_2e_approx':(35,28),'reported_2e_all_years':(33,27)}
        for profile,(n,g)in expected.items():
            ds=d.fetch(profile);os=old.fetch(profile);m=ds.feature_matrix();om=os.feature_matrix();counts[profile]=dict(rows=len(ds.rows),source_families=len(set(m['groups'])));ck('cohort:'+profile,len(ds.rows)==n and len(set(m['groups']))==g)
            index={r['endpoint_id']:i for i,r in enumerate(ds.rows)}
            for i,r in enumerate(os.rows):
                j=index[r['endpoint_id']];ck('old_matrix_Xy:'+profile+r['endpoint_id'],m['X'][j]==om['X'][i]and m['y'][j]==om['y'][i])
                for k in ['label_relations','label_evidence_kind','label_reading_bound_pp','baseline_references']:
                    if k in om:ck('old_label_metadata:'+k+profile+r['endpoint_id'],m[k][j]==om[k][i])
            for family in set(m['groups']):ck('source_weight:'+profile+family,math.isclose(sum(w for w,g0 in zip(m['sample_weight'],m['groups'])if g0==family),1))
            ck('matrix_not_training:'+profile,not m['training_authorized'])
            if '2e'in profile:ck('2E_API_matrix_unchanged:'+profile,ds.rows==os.rows and m==om)
            core[profile]=dict(rows=len(m['y']),features=m['feature_names'],missing_core_values=sum(v is None for rr in m['X']for v in rr),model_fits=0)
        ck('yearfilter_current_removed',not any(r['endpoint_id']==KEY for r in d.fetch('reported_3e',year_max=2022).rows))
        ck('37pending23sources',len(d.reviewed_pending_batch())==37 and len({r['source_group']for r in d.reviewed_pending_batch()})==23)
        ck('fixed41auditnotshrunk',len(d.reviewed_pending_batch(True))==len(old.reviewed_pending_batch(True))==41)
        oldpending={r['endpoint_id']:r for r in old.reviewed_pending_batch()};newpending={r['endpoint_id']:r for r in d.reviewed_pending_batch()};ck('only_TE009_closed',set(oldpending)-set(newpending)=={KEY})
        for key,r in newpending.items():ck('other_pending_exact:'+key,r==oldpending[key])
        ck('15freeze_and_Cycas4_unchanged',d.feature_conflicts_v24()==old.feature_conflicts_v24()and len(d.feature_conflicts_v24())==4)
        ck('retention_above100notclipped',max(r['retention_pct']for r in a if isinstance(r.get('retention_pct'),(int,float)))>100)
        ck('current_review_no_open_core_issues',d.holds(KEY)['open_issues']==[]and d.holds(KEY)['previous_review']==snapshot['previous_pending_review'])
        ev=d.evidence(KEY,'reported_current_A_g');ck('currentproof_not_oldunlocated',any(r.get('review_version')=='v0.26'and r.get('value')==10 and r['currently_selected']==1 for r in ev)and all(r.get('currently_selected')==0 for r in ev if r.get('review_version')!='v0.26'))
        ck('eleven_changes_keep_before',len(d.field_changes(KEY))==11 and any(r['field_name']=='reported_current_A_g'and r['before']is None and r['after']==10 for r in d.field_changes(KEY)))
    addendum_path=ROOT/'文献全量利用复核_20261027/批次19_木质素纳米纤维蛋米与烟草系列/verification_order_addendum.json'
    addendum=json.loads(addendum_path.read_text('utf8'))
    for k in ['companion','chain_companion','historical_goal_at_v18']:
        record=addendum[k];ck('historical_companion_SHA:'+k,sha(ROOT/record['path'])==record['sha256'])
    # Pin immutable historical API for historical checks; current release tested above.
    def pinned(*a,**kw):return parent.Database(PARENT/'cycling_v0_25.sqlite')
    with patch('data.cycling_db.open_database',pinned),redirect_stdout(io.StringIO()):
        from verify_lignin_egg_tobacco_chain_v19_stable import run
        run()
    ck('historical_literature_and_source_chain',True)
    from data.literature_v19 import open_literature_database
    ldb=ROOT/'文献全量利用复核_20261027/批次19_木质素纳米纤维蛋米与烟草系列/literature_material_pool_v19.sqlite'
    with open_literature_database(ldb,snapshot['literature_v19_sha256'])as lit,new.Database()as d:
        held='doi:'+DOI
        payload=[dict(kind='capacitance',group=r['source_group'])for r in lit.capacitances()if r['doi']==DOI]+[dict(kind='material_fact',group='doi:'+r['doi'])for r in lit.facts(doi=DOI)]+[dict(kind='cycle',group=r['source_group'])for r in d.fetch('all_review').rows if r['source_group']==held]
        for r in payload:ck('same_DOI_quarantine:'+r['kind']+str(len(checks)),lit.is_quarantined_source(r['group'],[held]))
        ck('no_other_family_masquerade',all(lit.isolation_group(r['group'])==held for r in payload))
    report=dict(status='passed',check_count=len(checks),checks=sorted(checks),database_sha256=sha(DB),parent_sha256=PSHA,ordinary_3e=counts['reported_3e'],all_years_3e=counts['reported_3e_all_years'],fixed_original_records=39,scientifically_resolved_original=2,pending_original=37,pending_source_groups=23,corrected_existing_endpoint=KEY,new_endpoints=0,new_admissions=1,model_fits=0,scientific_goal_complete=False)
    for name,value in [('verification',report),('model_inputs_preflight',core),('cohort_counts',counts)]:
        if prepare:write(OUT/(name+'.json'),value)
        else:assert json.loads((OUT/(name+'.json')).read_text('utf8'))==value,name
    if not prepare and(OUT/'merge_manifest.json').exists():
        for r in json.loads((OUT/'merge_manifest.json').read_text('utf8'))['outputs']:assert sha(ROOT/r['path'])==r['sha256'],r['path']
    print(json.dumps({k:v for k,v in report.items()if k!='checks'},ensure_ascii=False))
def seal():
    assert not(OUT/'merge_manifest.json').exists();verify(False)
    files=[p for p in OUT.rglob('*')if p.is_file()]+[ROOT/'tools/release_egg_current_v026.py',ROOT/'tools/verify_egg_current_v026.py']
    write(OUT/'merge_manifest.json',dict(version='cycling_v0.26',parent_database_sha256=PSHA,outputs=[dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p),bytes=p.stat().st_size)for p in sorted(files)],new_endpoints=0,new_admissions=1,fixed_original_pending=37,model_fits=0,scientific_goal_complete=False))
    write(ROOT/'data/current_database.json',dict(version='cycling_v0.26',version_directory=OUT.name,database_file=DB.name,sha256=sha(DB),parent_database_file=(PARENT/'cycling_v0_25.sqlite').relative_to(ROOT).as_posix(),default_profile='reported_3e',stage='existing_TE009_original_sentence_current_correction',ready_for_training_inputs=True,research_training_authorized=False,all_records_admitted=False))
if __name__=='__main__':
    if len(sys.argv)!=2 or sys.argv[1]not in ['prepare','verify','seal']:raise SystemExit('prepare/seal once before release; verify readonly')
    if sys.argv[1]=='seal':seal()
    else:verify(sys.argv[1]=='prepare')
