"""Independent read-only scientific/data/API verification; no fits or repairs."""
from pathlib import Path
import collections, hashlib, importlib.util, json, math, sqlite3, sys

ROOT=Path(__file__).resolve().parents[1]
BATCH=ROOT/'全库复检与特征补提取_20261021'
RELEASE=ROOT/'循环稳定性数据库_v0.11_全库复检与材料特征_20261021'
sys.path.insert(0,str(ROOT))
from material_feature_inputs_v011 import prepare_material_fold


def sha(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def read(path):return json.loads(path.read_text('utf-8'))


def main():
    checks=[]
    def check(name,ok):
        if not ok:raise AssertionError(name)
        checks.append(name)
    spec=importlib.util.spec_from_file_location('_verify_v011_api',RELEASE/'ml_data.py')
    api=importlib.util.module_from_spec(spec);sys.modules[spec.name]=api;spec.loader.exec_module(api)
    with api.Database() as db,api.base.Database() as parent:
        before={r['endpoint_id']:r for r in parent.fetch().rows};after={r['endpoint_id']:r for r in db.fetch().rows}
        check('3E33records25groups',len(after)==33 and len({r['source_group'] for r in after.values()})==25)
        check('only_two_new_3E_admissions',set(after)-set(before)=={'legacy:R087_CY01','legacy:R013_CY01'})
        for key,row in before.items():
            check('old_core_and_label_preserved:'+key,all(after[key].get(f)==row.get(f) for f in db.contract['core_features']+['retention_pct','retention_relation','source_group','source_year','system','method']))
        old_review={r['endpoint_id']:r for r in parent.fetch('all_review').rows}
        review={r['endpoint_id']:r for r in db.fetch('all_review').rows}
        check('all_old_observations_retained',set(old_review)<=set(review) and len(review)==277)
        new_candidates=set(review)-set(old_review)
        check('four_new_samples_still_candidates',len(new_candidates)==4 and all(not review[k]['eligible'] and not review[k]['admission_profiles_v11'] for k in new_candidates))
        for key,row in old_review.items():
            for f,value in row.items():
                if f=='source_weight' or value is None or not isinstance(value,(int,float)) or isinstance(value,bool):continue
                check('old_nonnull_numeric_preserved:'+key+':'+f,review[key].get(f)==value)
        groups=collections.defaultdict(list)
        for r in after.values():groups[r['source_group']].append(r)
        check('source_equal_weights',all(abs(sum(r['source_weight'] for r in values)-1)<1e-12 for values in groups.values()))
        identity_groups=collections.defaultdict(set)
        for r in after.values():identity_groups[r['identity_key']].add(r['source_group'])
        check('no_DOI_split_across_groups',all(len(x)==1 for x in identity_groups.values()))
        check('low_retention_three_independent_sources',len({r['source_group'] for r in after.values() if r['retention_pct']<91})==3)
        check('OAC85_5_1000cycles',after['legacy:R087_CY01']['retention_pct']==85.5 and after['legacy:R087_CY01']['cycle_count']==1000)
        check('EUAC89_9_10000cycles',after['legacy:R013_CY01']['retention_pct']==89.9 and after['legacy:R013_CY01']['cycle_count']==10000)
        check('unknown_physical_current_not_filled',all(after[k].get('canonical_current_A_g') is None and after[k].get('baseline_cycle') is None for k in ['legacy:R087_CY01','legacy:R013_CY01']))
        check('old_holds_visible_for_new_approvals',all(db.holds(k)['previous_holds']==parent.holds(k) for k in ['legacy:R087_CY01','legacy:R013_CY01']))
        by_sample={r['sample_name']:r for r in after.values()}
        check('OPBNP_not_falsely_atomic_N',by_sample['OPBNP']['XPS_N_reported_pct']==3.28 and by_sample['OPBNP'].get('N_at_pct') is None)
        check('EUAC_XPS_not_falsely_atomic_O',by_sample['EUAC1-60']['XPS_O_reported_pct']==15.39 and by_sample['EUAC1-60'].get('O_at_pct') is None)
        check('AMFS_radius_not_diameter',by_sample['AMFS-derived activated carbon']['average_pore_radius_nm']==1.82 and by_sample['AMFS-derived activated carbon'].get('average_pore_diameter_nm') is None)
        check('Raman_reciprocal_direction_retained',by_sample['SNPB-800-4']['Raman_IG_ID']==1.162 and math.isclose(by_sample['SNPB-800-4']['Raman_ID_IG'],1/1.162,rel_tol=1e-6))
        check('CA_AA_conflicting_Raman_not_selected',by_sample['CA-AA'].get('Raman_ID_IG') is None)
        check('YZPC_conflicting_micropore_volume_not_selected',by_sample['YZPC-3'].get('micropore_volume_cm3_g') is None)
        check('WET_DRY_raw_unit_freezes_retained',all(by_sample[n].get('micropore_volume_cm3_g') is None and by_sample[n].get('raw_total_pore_volume_m3_g') is not None for n in ['WET-1','DRY-1']))
        check('ABC_weight_not_atomic',by_sample['A-BC-0.2']['bulk_N_wt_pct']==2.77 and by_sample['A-BC-0.2'].get('N_at_pct') is None)
        check('ALPC_two_protocols_one_material',len({r['material_key_v11'] for r in after.values() if r['sample_name']=='ALPC-800'})==1)
        check('all_training_rows_have_material_key',all(r.get('material_key_v11') for r in after.values()))
        incoming={r['endpoint_id']:r for r in db.incoming_tests()}
        check('incoming_view_has_current_material_fields',incoming['incoming:ADD_039_T01']['N_at_pct']==after['incoming:ADD_039_T01']['N_at_pct']==1.89)
        check('incoming_review_view_consistent',len(db.fetch('incoming_review').rows)==len(incoming)==82)
        check('endpoint_lookup_current_review',db.by_endpoint('legacy:R087_CY01')['eligible']==1 and db.by_endpoint('missing') is None)
        alias=db.conn.execute('select namespace,alias from endpoint_aliases where endpoint_id=? limit 1',('legacy:R087_CY01',)).fetchone()
        check('legacy_alias_current_admission',alias is not None and db.by_alias(alias[0],alias[1])['eligible']==1)
        for profile in ['reported_2e','reported_2e_residue','reported_2e_approx']:
            check('2E_membership_preserved:'+profile,{r['endpoint_id'] for r in db.fetch(profile).rows}=={r['endpoint_id'] for r in parent.fetch(profile).rows})
        for key,row in review.items():
            if row['system'].startswith('2E') and key in old_review:
                check('no_3E_loading_borrowed:'+key,row.get('mass_loading_mg_cm2')==old_review[key].get('mass_loading_mg_cm2'))
        try:db.fetch('all_review').feature_matrix()
        except api.DataNotReady:checks.append('review_pool_cannot_be_training_matrix')
        else:raise AssertionError('Unadmitted pool exported')
        matrix=db.material_matrix()
        atomic=db.material_matrix(extra_features=['N_at_pct','O_at_pct'])
        opb_index=atomic['endpoint_ids'].index('candidate:TE021')
        check('strict_atomic_matrix_keeps_unspecified_unknown',atomic['X'][opb_index][atomic['feature_names'].index('N_at_pct')] is None)
        check('sparse_raw_matrix_not_imputed',not matrix['imputed'] and any(any(mask) for mask in matrix['missing_mask']))
        for k,fold in enumerate(matrix['source_folds']):
            prepared=prepare_material_fold(matrix,fold)
            check('finite_group_fold:'+str(k),all(math.isfinite(v) for values in prepared['X_train']+prepared['X_validation'] for v in values))
            check('fold_source_separation:'+str(k),not(set(prepared['training_source_groups'])&set(prepared['validation_source_groups'])))
        multi=next(v for v in groups.values() if len(v)>1)
        held=next(i for i,r in enumerate(db.fetch().rows) if r['endpoint_id']==multi[0]['endpoint_id'])
        try:prepare_material_fold(matrix,{'test':[held],'train':[i for i in range(len(matrix['X'])) if i!=held]})
        except ValueError:checks.append('within_source_split_rejected')
        else:raise AssertionError('Leaking split accepted')
        check('full_native_search_PDF',bool(db.search_native('NCHU20',doi='10.1016/j.biombioe.2026.109160')))
        check('full_native_search_XML',bool(db.search_native('QSC',doi='10.1021/acsomega.3c04692')))
        word_matches=db.search_native('lignin',doi='10.1016/j.greenca.2025.12.003',limit=100)
        check('full_native_search_new_SI_Word',any(r['format']=='docx' for r in word_matches))
        check('raw_table_search_units_status',all(r['training_eligible']==0 for r in db.search_tables('QSC',doi='10.1021/acsomega.3c04692')) and bool(db.search_tables('QSC',doi='10.1021/acsomega.3c04692')))
        for endpoint,field in [('legacy:R013_CY01','mass_loading_mg_cm2'),('candidate:TE021','Raman_ID_IG')]:
            check('material_evidence_available:'+endpoint,any(e.get('review_version')=='v0.11' and e.get('sha256') for e in db.evidence(endpoint,field)))
        for filename in ['cycling_v0_11.sqlite',db.contract['corpus_search_database']]:
            path=RELEASE/filename if filename.endswith('cycling_v0_11.sqlite') else ROOT/filename
            with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as c:
                check('sqlite_integrity:'+path.name,c.execute('pragma integrity_check').fetchone()[0]=='ok')
                check('sqlite_foreign_keys:'+path.name,not c.execute('pragma foreign_key_check').fetchall())
        check('parent_sha_unchanged',sha(api.PARENT/'cycling_v0_10.sqlite')==db.contract['parent_database_sha256'])
        check('corpus_fingerprint',sha(ROOT/db.contract['corpus_search_database'])==db.contract['corpus_search_database_sha256'])
        with sqlite3.connect((ROOT/db.contract['corpus_search_database']).as_uri()+'?mode=ro',uri=True) as source_index:
            for fingerprint,path in source_index.execute('select sha256,path from sources'):
                check('project_or_catalog_original:'+str(path),bool(path) and Path(path).is_file() and sha(Path(path))==fingerprint)
        fields=sorted({p['field_name'] for p in db.material_properties()})
        coverage={f:{'before_training_records':sum(r.get(f) is not None for r in before.values()),'after_training_records':sum(r.get(f) is not None for r in after.values()),'after_source_groups':len({r['source_group'] for r in after.values() if r.get(f) is not None})} for f in fields}
        training_new_cells=sum(r.get(f) is not None and (k not in before or before[k].get(f) is None) for k,r in after.items() for f in fields)
    # Byte-level protection of prior scientific payloads. Public indices evolve.
    mutable={'data/current_database.json','README.md','AGENTS.md','docs/CURRENT_STATE.md','docs/PROGRESS.md','docs/WORKSPACE_MEMORY.md','docs/KNOWLEDGE_BASE.md'}
    prior=[];mutable_changes=[]
    for manifest in ['初步模型训练_20261021/run_manifest.json','模型诊断与改进_20261021/run_manifest.json','循环稳定性数据库_v0.10_原文精细补证_20261021/merge_manifest.json']:
        for item in read(ROOT/manifest)['outputs']:
            p=ROOT/item['path'];actual=sha(p)
            if actual!=item['sha256'] and item['path'].replace('\\','/') in mutable:
                mutable_changes.append({'path':item['path'],'expected_historical_sha256':item['sha256'],'current_sha256':actual,'reason':'Authorized evolving public continuation/index; not immutable scientific payload'})
            else:check('prior_payload:'+item['path'],actual==item['sha256'])
            prior.append(item['path'])
    # Every inventoried external original remains byte-identical, including duplicates.
    for item in read(BATCH/'external_library_inventory.json'):
        check('external_original:'+item['path'],sha(Path(item['path']))==item['sha256'])
    for item in read(BATCH/'archive_inventory_audit.json')['archives']:
        check('original_archive:'+item['path'],sha(Path(item['path']))==item['sha256'])
    digest_cache={};evidence_count=0
    with sqlite3.connect(RELEASE/'cycling_v0_11.sqlite') as c:
        for path,expected in c.execute('select distinct path,sha256 from document_evidence_v11'):
            resolved=(ROOT/path).resolve();digest_cache.setdefault(str(resolved),sha(resolved))
            check('curated_original:'+path,digest_cache[str(resolved)]==expected);evidence_count+=1
    report={'passed':True,'check_count':len(checks),'checks':checks,'3E_records':33,'3E_source_groups':25,'low_retention_source_groups':3,
            'review_rows':277,'new_pending_own_table_tests':4,'training_new_or_filled_material_cells':training_new_cells,
            'material_field_coverage':coverage,'prior_payload_occurrences_checked':len(prior),'mutable_public_index_changes':mutable_changes,
            'external_original_file_occurrences_checked':len(read(BATCH/'external_library_inventory.json')),'curated_evidence_originals_checked':evidence_count,
            'model_fits':0,'precision_improvement_demonstrated':False,'all_literature_admitted':False}
    if not (RELEASE/'merge_manifest.json').exists():
        (BATCH/'independent_verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n','utf-8')
    else:
        print('Sealed verification report retained; this rerun is read-only.')
    print(json.dumps({k:v for k,v in report.items() if k not in ['checks','material_field_coverage','mutable_public_index_changes']},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
