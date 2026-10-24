"""Independent data, provenance, scope and training-input checks for v0.15."""
from pathlib import Path
import collections,copy,csv,hashlib,importlib.util,json,math,sqlite3,sys
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'tools')]
from inspect_existing_sources_v015 import BATCH,SNAPSHOT,read,sha
from material_feature_inputs_v011 import prepare_material_fold
from training_input_quality import assess
PARENT=ROOT/'循环稳定性数据库_v0.14_主集参数精提取_20261022'
OUT=ROOT/'循环稳定性数据库_v0.15_表图与待补证复核_20261024'
def write(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n','utf-8')
def module(p,n):
    s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);sys.modules[n]=m;s.loader.exec_module(m);return m
def main():
    checks=[]
    def check(name,value):
        if not value:raise AssertionError(name)
        checks.append(name)
    # Protect complete latest parent release and both historical training runs.
    manifest_paths=[PARENT/'merge_manifest.json',ROOT/'模型逐项优化_v1.1_20261022/run_manifest.json',ROOT/'模型v1.0_来源留出训练_20261022/run_manifest.json']
    protection={}
    for path in manifest_paths:
        manifest=read(path)
        for section in ['outputs','protected_files','protected_sources']:
            entries=manifest.get(section,[])
            if isinstance(entries,dict):entries=[{'path':p,'sha256':h} for p,h in entries.items()]
            for item in entries:
                if isinstance(item,dict) and 'path' in item and 'sha256' in item:
                    p=Path(item['path']);p=p if p.is_absolute() else ROOT/p
                    check('sealed_'+str(p),p.is_file() and sha(p)==item['sha256']);protection[str(p)]=item['sha256']
    check('immutable_full_text_index',sha(ROOT/'全库复检与特征补提取_20261021/full_corpus_search_native.sqlite')=='f2720c3e417904dad5857a6574cc72d5cf996f9b8716620d69594f11380c658c')
    for p,h in read(BATCH/'protected_sources.json').items():
        f=Path(p);f=f if f.is_absolute() else ROOT/f
        check('original_'+p,sha(f)==h)
    with sqlite3.connect((OUT/'cycling_v0_15.sqlite').as_uri()+'?mode=ro',uri=True) as c:
        check('sqlite_integrity',c.execute('pragma integrity_check').fetchone()[0]=='ok')
        check('foreign_keys',not c.execute('pragma foreign_key_check').fetchall())
    oldapi=module(PARENT/'ml_data.py','_v015_verify_parent');newapi=module(OUT/'ml_data.py','_v015_verify_current')
    changes=read(BATCH/'field_changes.json');lookup={(c['endpoint_id'],c['field_name']):c for c in changes}
    check('unique_change_keys',len(lookup)==len(changes))
    snapshot=read(SNAPSHOT)
    with oldapi.Database() as old,newapi.Database() as db:
        before={r['endpoint_id']:r for r in old.fetch('all_review').rows};after={r['endpoint_id']:r for r in db.fetch('all_review').rows}
        check('all_277_observations_retained',set(before)==set(after) and len(after)==277)
        for key,row in before.items():
            for field,value in row.items():
                if (key,field) in lookup:
                    check('old_value_chain_'+key+field,lookup[(key,field)]['before']==value)
                elif field.endswith('_status') and (key,field.removesuffix('_status')) in lookup:continue
                else:check('unchanged_'+key+'_'+field,after[key].get(field)==value)
            holds=db.holds(key)
            if key in db.reviews_v15:check('freeze_history_'+key,holds['previous_holds']==old.holds(key))
            else:check('unchanged_holds_'+key,holds==old.holds(key))
        corrections=[]
        for c in changes:
            key=c['endpoint_id'];field=c['field_name']
            check('delta_applied_'+key+field,after[key][field]==c['after'] and before[key].get(field)==c['before'])
            check('material_binding_'+key+field,after[key]['material_key_v11']==before[c['reviewed_endpoint']]['material_key_v11'])
            for e in c['evidence']:
                p=Path(e['path']);p=p if p.is_absolute() else ROOT/p
                check('direct_source_'+key+field,field in e['fields'] and sha(p)==e['sha256'])
            check('selected_evidence_'+key+field,any(e.get('review_version')=='v0.15' and e.get('currently_selected')==1 for e in db.evidence(key,field)))
            if c['before'] is not None:corrections.append(c)
        check('only_four_ALPC_method_corrections',len(corrections)==4 and all(after[c['endpoint_id']]['sample_name']=='ALPC-800' and c['field_name'] in ['XPS_N_reported_pct','XPS_O_reported_pct'] for c in corrections))
        cohorts={};readiness={}
        for profile in db.contract['profiles']:
            a=old.fetch(profile);b=db.fetch(profile)
            check('same_membership_'+profile,[r['endpoint_id'] for r in a.rows]==[r['endpoint_id'] for r in b.rows])
            check('same_core_labels_groups_weights_'+profile,a.feature_matrix()==b.feature_matrix())
            readiness[profile]=assess(b)
            check('input_quality_'+profile,readiness[profile]['status']=='ready_for_exploratory_grouped_baseline_inputs')
            cohorts[profile]=dict(records=len(b.rows),source_groups=len({r['source_group'] for r in b.rows}))
        raw=db.material_matrix();method=db.method_specific_material_matrix()
        for i,matrix in enumerate([raw,method]):
            for j,fold in enumerate(matrix['source_folds']):
                a=prepare_material_fold(matrix,fold);check(f'finite_fold_{i}_{j}',all(math.isfinite(x) for k in ['X_train','X_validation'] for r in a[k] for x in r))
                modified=copy.deepcopy(matrix)
                for k in fold['test']:
                    modified['y'][k]=987654321
                    for col,f in enumerate(matrix['feature_names']):modified['X'][k][col]='HELDOUT_ONLY' if f in matrix['categorical_features'] else 987654321
                b=prepare_material_fold(modified,fold)
                check(f'no_holdout_preprocessing_leak_{i}_{j}',a['X_train']==b['X_train'] and a['training_only_schema']==b['training_only_schema'])
        fields=db.contract['model_material_features'];main=db.fetch().rows;oldmain=old.fetch().rows
        coverage={f:dict(before=sum(r.get(f) is not None for r in oldmain),after=sum(r.get(f) is not None for r in main),
            after_sources=len({r['source_group'] for r in main if r.get(f) is not None})) for f in fields}
        prev=sum(v['before'] for v in coverage.values());now=sum(v['after'] for v in coverage.values())
        check('fixed_18_field_denominator',len(fields)==18 and len(main)==42 and prev==299 and now==320)
        byname={r['sample_name']:r for r in main}
        check('ALPC_separate_EDS_XPS',byname['ALPC-800']['XPS_N_reported_pct']==4.64 and byname['ALPC-800']['EDS_N_at_pct_v15']==11.23 and byname['ALPC-800']['N_at_pct']==11.23)
        check('ALPC_conflicting_pores_not_promoted',all(byname['ALPC-800'].get(f) is None for f in ['micropore_volume_cm3_g','micropore_surface_area_m2_g']))
        check('RSM_reciprocal_not_other_sample',byname['RSM-0.33-550']['Raman_ID_IG']==round(1/1.292,6))
        check('AHC_weight_not_atomic',byname['AHC-CL-TU']['XPS_percentage_basis']=='weight_explicit' and byname['AHC-CL-TU'].get('N_at_pct') is None)
        ni=method['feature_names'].index('XPS_N_atomic_pct_v15');nw=method['feature_names'].index('XPS_N_weight_pct_v15')
        for i,key in enumerate(method['endpoint_ids']):
            row=after[key]
            if row['sample_name']=='AHC-CL-TU':check('AHC_projection_weight_only',method['X'][i][ni] is None and method['X'][i][nw]==3.2)
            if row['sample_name']=='ALPC-800':check('ALPC_projection_XPS_only',method['X'][i][ni]==4.64 and method['X'][i][nw] is None)
            if row.get('XPS_percentage_basis')=='not_explicitly_reported':check('unspecified_XPS_withheld_'+key,method['X'][i][ni] is None and method['X'][i][nw] is None)
        check('no_unit_frozen_pore_overwrite',all(byname[s]['total_pore_volume_cm3_g'] is None for s in ['WET-1','DRY-1']))
        check('real_over_100_labels_preserved',[(r['endpoint_id'],r['retention_pct']) for r in oldmain if r['retention_pct']>100]==[(r['endpoint_id'],r['retention_pct']) for r in main if r['retention_pct']>100])
        reviews=db.reviewed_pending_batch(True)
        review_evidence_hashes={}
        for c in reviews:
            check('review_matches_draft_ledger_'+c['endpoint_id'],c==next(x for x in read(BATCH/'reviewed_curation.json')['pending_reviews'] if x['endpoint_id']==c['endpoint_id']))
            for e in c['evidence']:
                p=Path(e['path']);p=p if p.is_absolute() else ROOT/p
                check('pending_evidence_hash_'+c['endpoint_id']+e['locator'],sha(p)==e['sha256'])
                review_evidence_hashes[e['path']]=e['sha256']
        write(BATCH/'review_evidence_hashes.json',review_evidence_hashes)
        check('all_41_individual_dispositions',len(reviews)==41 and {c['endpoint_id'] for c in reviews}=={c['endpoint_id'] for c in snapshot['pending']})
        check('39_still_pending',len(db.reviewed_pending_batch())==39)
        check('two_definite_scope_decisions',{c['endpoint_id'] for c in reviews if c['disposition'].startswith('outside_')}=={'candidate:TE032','legacy:SRC126_CY01'})
        check('no_new_admissions',all(not c['approved_profiles'] for c in reviews))
        check('preprint_BET_recovered_without_label_fabrication',after['incoming:ADD_058_T01']['BET_m2_g']==1018.74 and after['incoming:ADD_058_T01'].get('retention_pct') is None and after['incoming:ADD_073_T01']['BET_m2_g']==2142)
        # Verify rejection of deliberately wrong inputs, not just happy-path matrices.
        for mutation in ['missing_baseline','wrong_system','missing_current']:
            dataset=db.fetch();dataset.rows=copy.deepcopy(dataset.rows)
            if mutation=='missing_baseline':dataset.rows[0]['baseline_reference']=None
            elif mutation=='wrong_system':dataset.rows[0]['system']='2E'
            else:dataset.rows[0]['reported_current_A_g']=None
            try:dataset.feature_matrix()
            except newapi.DataNotReady:check('reject_'+mutation,True)
            else:raise AssertionError('Accepted invalid '+mutation)
        write(OUT/'training_readiness.json',readiness)
        write(OUT/'reported_3e_method_specific_inputs.json',method)
        summary=dict(version='v0.15',cohorts=cohorts,model_fits=0,field_changes=len(changes),fill_changes=len(changes)-len(corrections),correction_changes=len(corrections),
            affected_records=len({c['endpoint_id'] for c in changes}),fixed_main_records=42,fixed_main_sources=30,
            fixed_optional_fields=18,total_cells=756,before_nonmissing=prev,after_nonmissing=now,before_coverage_pct=100*prev/756,after_coverage_pct=100*now/756,
            optional_cell_gain=now-prev,feature_coverage=coverage,pending_original=41,pending_remaining=39,outside_scope_resolved=2,new_admitted_records=0,
            pending_dispositions=dict(collections.Counter(c['disposition'] for c in reviews)),new_independent_sources=0,
            limits=['New features do not establish accuracy improvement.','Past v1.1 model was trained on v0.14, not this evidence layer.','No new publisher-version check, author correction or raw data acquired.'])
        write(BATCH/'coverage_and_dispositions.json',summary)
        with (BATCH/'41条逐项处置.csv').open('w',encoding='utf-8-sig',newline='') as f:
            cols=['endpoint_id','sample_name','source_group','disposition','resolution','open_issues','reason','evidence_files']
            w=csv.DictWriter(f,fieldnames=cols);w.writeheader()
            for c in reviews:w.writerow({k:('; '.join(c[k]) if isinstance(c.get(k),list) else c.get(k,'')) for k in cols if k!='evidence_files'}|{'evidence_files':'; '.join(e['path']+' @ '+e['locator'] for e in c['evidence'])})
        write(BATCH/'remaining_pending_records.json',db.reviewed_pending_batch())
    write(OUT/'verification.json',dict(passed=True,check_count=len(checks),checks=checks,protected_sealed_payloads=len(protection),protected_originals=len(read(BATCH/'protected_sources.json')),protected_pending_evidence_files=len(review_evidence_hashes),model_fits=0))
    print(json.dumps(dict(passed=True,checks=len(checks),coverage=f'{prev}/756 -> {now}/756',pending=39,new_admissions=0,model_fits=0),ensure_ascii=False))
if __name__=='__main__':main()
