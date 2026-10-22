"""Independent read-only checks and source-coverage audit; never fits models."""
from pathlib import Path
import collections,copy,hashlib,importlib.util,json,math,sqlite3,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'tools')]
OUT=ROOT/'循环稳定性数据库_v0.13_冲突复核_20261022'
BATCH=ROOT/'冲突复核与来源充分性_20261022'
PARENT=ROOT/'循环稳定性数据库_v0.12_待补证精细复核_20261022'
from training_input_quality import assess
from material_feature_inputs_v011 import prepare_material_fold
def read(p):return json.loads(p.read_text('utf-8'))
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n','utf-8')
def module(path,name):
    sp=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(sp);sys.modules[name]=m;sp.loader.exec_module(m);return m

def main():
    checks=[]
    def check(label,ok):
        if not ok:raise AssertionError(label)
        checks.append(label)
    manifest=read(PARENT/'merge_manifest.json')
    outputs=manifest['outputs']
    if isinstance(outputs,dict):outputs=[dict(path=p,sha256=h) for p,h in outputs.items()]
    for e in outputs:check('v12_sealed_'+e['path'],sha(ROOT/e['path'])==e['sha256'])
    check('large_native_index_unchanged',sha(ROOT/'全库复检与特征补提取_20261021/full_corpus_search_native.sqlite')==manifest['corpus_sha256'])
    source_hashes=read(BATCH/'protected_sources.json')
    packets=read(ROOT/'待补证原文复核_20261022/original_review_packets.json')
    for p in packets:
        for s in p['sources']:source_hashes[s['path']]=s['sha256']
    for path,h in source_hashes.items():check('original_hash_'+path,sha(ROOT/path)==h)
    for r in read(BATCH/'render_provenance.json'):check('render_hash_'+r['render_path'],sha(ROOT/r['render_path'])==r['render_sha256'])
    with sqlite3.connect((OUT/'cycling_v0_13.sqlite').as_uri()+'?mode=ro',uri=True) as c:
        check('sqlite_integrity',c.execute('pragma integrity_check').fetchone()[0]=='ok')
        check('foreign_keys',not c.execute('pragma foreign_key_check').fetchall())
    parent=module(PARENT/'ml_data.py','_v013_verify_parent');current=module(OUT/'ml_data.py','_v013_verify_current')
    changes=read(BATCH/'field_changes.json');reviews=read(BATCH/'effective_reviews.json')
    changed={(c['endpoint_id'],c['field_name']):c for c in changes}
    cohorts={};feature_counts={};comparison={}
    with parent.Database() as old,current.Database() as db:
        before={r['endpoint_id']:r for r in old.fetch('all_review').rows}
        after={r['endpoint_id']:r for r in db.fetch('all_review').rows}
        check('all_277_observations_preserved',set(before)==set(after) and len(after)==277)
        newly_approved={k for k,r in before.items() if not r.get('admission_profiles_v12') and after[k]['admission_profiles_v13']}
        check('administrative_transitions_limited_to_four_reviewed_AHPC',len(newly_approved)==4 and all('AHPC2026' in k for k in newly_approved))
        for key,r in before.items():
            for f,v in r.items():
                if f=='source_weight':continue
                if key in newly_approved and f in ['eligible','admission_status']:
                    check('explicit_admission_transition_'+key+'_'+f,after[key][f]==(1 if f=='eligible' else 'approved_for_reported_protocol'))
                    continue
                if (key,f) not in changed:check('old_value_'+key+'_'+f,after[key].get(f)==v)
        for c in changes:
            key=c['endpoint_id'];f=c['field_name']
            check('change_before_'+key+'_'+f,before[key].get(f)==c['before'])
            check('change_after_'+key+'_'+f,after[key].get(f)==c['after'])
            check('change_evidence_'+key+'_'+f,bool(c['reason']) and all(f in e['fields'] for e in c['evidence']))
            check('public_evidence_'+key+'_'+f,any(e.get('review_version')=='v0.13' and e.get('field_name')==f for e in db.evidence(key,f)))
        for c in reviews:
            key=c['endpoint_id'];h=db.holds(key)
            check('freeze_history_'+key,h['previous_holds']==old.holds(key)==c['previous_holds'])
            check('current_issues_'+key,h['open_issues']==c['open_issues'])
        main_old={r['endpoint_id'] for r in old.fetch().rows};main_new={r['endpoint_id'] for r in db.fetch().rows}
        added=main_new-main_old
        check('only_four_AHPC_table_rows_added',len(added)==4 and all('AHPC2026' in k for k in added) and main_old<=main_new)
        for key in added:
            r=after[key]
            check('no_baseline_index_invented_'+key,r['baseline_reference']['cycle_index'] is None and r['baseline_cycle'] is None)
            check('old_admission_fields_immutable_'+key,r['admission_profiles_v12']==before[key]['admission_profiles_v12']==[])
        for p in db.contract['profiles']:
            ds=db.fetch(p);was=old.fetch(p);q=assess(ds)
            checks.extend(p+'_'+x for x in q['quality_checks'])
            cohorts[p]=dict(rows=len(ds.rows),source_groups=len({r['source_group'] for r in ds.rows}))
            for r in was.rows:
                selected=next(x for x in ds.rows if x['endpoint_id']==r['endpoint_id'])
                check('old_cohort_target_'+p+'_'+r['endpoint_id'],selected['retention_pct']==r['retention_pct'])
            if p.startswith('reported_2e'):check('two_e_membership_unchanged_'+p,{r['endpoint_id'] for r in was.rows}=={r['endpoint_id'] for r in ds.rows})
            groups={r['source_group'] for r in ds.rows}
            normalized={g.lower().removeprefix('doi:').removeprefix('https://doi.org/') for g in groups}
            check('normalized_DOI_group_not_split_'+p,len(normalized)==len(groups))
        ds=db.fetch();rows=ds.rows;matrix=db.material_matrix();oldmatrix=old.material_matrix()
        features=matrix['feature_names'];extras=[f for f in features if f not in ds.features]
        for f in extras:
            selected=[r for r in rows if r.get(f) is not None]
            feature_counts[f]=dict(rows_nonmissing=len(selected),source_groups_nonmissing=len({r['source_group'] for r in selected}),
                rows_total=len(rows),source_groups_total=len({r['source_group'] for r in rows}))
        optional=sum(x['rows_nonmissing'] for x in feature_counts.values())
        check('no_optional_predictor_loss',all(after[k].get(f)==v for k,r in before.items() for f,v in r.items() if k in main_old and f in extras and v is not None))
        for n,fold in enumerate(matrix['source_folds']):
            out=prepare_material_fold(matrix,fold)
            check('sparse_fold_finite_'+str(n),all(math.isfinite(x) for data in [out['X_train'],out['X_validation']] for r in data for x in r))
        for field,value in [('BET_m2_g',None),('cycle_count',True),('retention_pct',False),('baseline_reference',None),('admission_profiles_v13',[])]:
            bad=copy.deepcopy(ds);bad.rows[0][field]=value
            try:bad.feature_matrix()
            except current.DataNotReady:checks.append('reject_bad_'+field)
            else:raise AssertionError('Bad field accepted: '+field)
        check('SI_native_search',bool(db.search_native('3175.91',doi='10.1016/j.indcrop.2026.123626')))
        check('SI_table_search',bool(db.search_tables('LCC-3',doi='10.1016/j.indcrop.2026.123626')))
        check('old_SI_search_preserved',bool(db.search_native('5.69',doi='10.1016/j.biombioe.2026.109160')))
        check('C4_ratio_not_formal_target',after['legacy:R018_CY01']['retention_pct']==before['legacy:R018_CY01']['retention_pct'] and not after['legacy:R018_CY01']['admission_profiles_v13'])
        check('LCC_and_LCNC_unresolved_not_admitted',all(not after[k]['admission_profiles_v13'] for k in ['incoming:ADD_059_T01','incoming:ADD_059_T02']))
        check('no_LCNC1_BET_borrowed',after['incoming:ADD_059_T02'].get('BET_m2_g') is None)
        check('mesopore_area_not_external_area',after['incoming:ADD_059_T01'].get('external_surface_area_m2_g') is None)
        def coverage(predicate):
            rr=[r for r in rows if predicate(r)]
            return dict(rows=len(rr),source_groups=len({r['source_group'] for r in rr}),
                        endpoint_ids=[r['endpoint_id'] for r in rr])
        group_counts=collections.Counter(r['source_group'] for r in rows)
        categories={f:{v:dict(rows=sum(r[f]==v for r in rows),source_groups=len({r['source_group'] for r in rows if r[f]==v})) for v in sorted({r[f] for r in rows})} for f in ['electrolyte','reference_electrode','cycle_count']}
        pending=[r for r in db.pending_evidence() if r['system']=='3E' and (r['source_year'] is None or 2023<=r['source_year']<=2026)]
        stats=dict(version='v0.13',main_rows=len(rows),main_source_groups=len(group_counts),all_review_observations=len(after),
            all_review_source_groups=len({r['source_group'] for r in after.values()}),all_3e_observations=len(db.fetch('review_3e_all').rows),
            current_purpose_3e_pending_rows=len(pending),all_3e_unadmitted_rows=sum(r['system']=='3E' for r in db.full_review_queue()),
            low_retention_below91=coverage(lambda r:r['retention_pct']<91),low_retention_below85=coverage(lambda r:r['retention_pct']<85),
            long_cycles_ge50000=coverage(lambda r:r['cycle_count']>=50000),above100=coverage(lambda r:r['retention_pct']>100),
            optional_features=len(extras),optional_nonmissing_cells=optional,optional_total_cells=len(rows)*len(extras),
            optional_cell_coverage_pct=100*optional/(len(rows)*len(extras)),optional_feature_coverage=feature_counts,
            source_group_counts=dict(group_counts),maximum_raw_row_share_pct=100*max(group_counts.values())/len(rows),
            source_equal_weight_share_pct=100/len(group_counts),categories=categories,
            model_fits=0,conclusion='Exploratory grouped baseline inputs are ready; reliable broad generalization and large-model scale are not established. Additional independent sources and richer conditions/material predictors remain needed.',
            no_universal_minimum_paper_threshold=True,
            next_priorities=['independent low-retention and long-cycle sources','own before-cycling material composition/porosity/processing and loading','neutral/NaOH and sparse reference categories','new independent source holdout for any new experiment'])
        write(BATCH/'source_coverage.json',stats)
        queue=[dict(endpoint_id=r['endpoint_id'],sample_name=r['sample_name'],source_group=r['source_group'],
            reason=r.get('review_reason_v13',r.get('review_reason_v12')),open_issues=db.holds(r['endpoint_id']).get('open_issues',[])) for r in pending]
        write(BATCH/'current_pending_records.json',queue)
    # Hash originals once more after all API checks.
    for path,h in source_hashes.items():check('final_original_hash_'+path,sha(ROOT/path)==h)
    result=dict(status='passed',checks_count=len(checks),checks=checks,cohorts=cohorts,field_changes=len(changes),reviewed_records=len(reviews),
        parent_database_sha256=sha(PARENT/'cycling_v0_12.sqlite'),database_sha256=sha(OUT/'cycling_v0_13.sqlite'),
        protected_original_files=len(source_hashes),model_fits=0,all_scientific_questions_resolved=False,all_records_admitted=False)
    write(OUT/'verification.json',result)
    print(json.dumps({k:v for k,v in result.items() if k!='checks'},ensure_ascii=False))
    print(json.dumps({k:stats[k] for k in ['low_retention_below91','low_retention_below85','long_cycles_ge50000','optional_nonmissing_cells','optional_total_cells','current_purpose_3e_pending_rows']},ensure_ascii=False))
if __name__=='__main__':main()
