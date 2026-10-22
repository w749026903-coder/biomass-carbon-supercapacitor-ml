"""Independent protection, provenance and fixed-cohort coverage checks; no fitting."""
from pathlib import Path
import collections,copy,hashlib,importlib.util,json,math,sqlite3,sys
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'tools')]
PARENT=ROOT/'循环稳定性数据库_v0.13_冲突复核_20261022';OUT=ROOT/'循环稳定性数据库_v0.14_主集参数精提取_20261022';BATCH=ROOT/'主集参数精提取_20261022'
from training_input_quality import assess
from material_feature_inputs_v011 import prepare_material_fold
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(p.read_text('utf-8'))
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n','utf-8')
def module(p,n):
    sp=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(sp);sys.modules[n]=m;sp.loader.exec_module(m);return m

def main():
    checks=[]
    def check(label,ok):
        if not ok:raise AssertionError(label)
        checks.append(label)
    for folder in [PARENT,ROOT/'循环稳定性数据库_v0.12_待补证精细复核_20261022']:
        for e in read(folder/'merge_manifest.json')['outputs']:check('sealed_'+e['path'],sha(ROOT/e['path'])==e['sha256'])
    check('large_corpus_unchanged',sha(ROOT/'全库复检与特征补提取_20261021/full_corpus_search_native.sqlite')=='f2720c3e417904dad5857a6574cc72d5cf996f9b8716620d69594f11380c658c')
    originals=read(BATCH/'protected_sources.json')
    for p,h in originals.items():check('original_'+p,sha(ROOT/p)==h)
    with sqlite3.connect((OUT/'cycling_v0_14.sqlite').as_uri()+'?mode=ro',uri=True) as c:
        check('sqlite_integrity',c.execute('pragma integrity_check').fetchone()[0]=='ok');check('foreign_keys',not c.execute('pragma foreign_key_check').fetchall())
    parent=module(PARENT/'ml_data.py','_v014_verify_old');api=module(OUT/'ml_data.py','_v014_verify_new')
    changes=read(BATCH/'field_changes.json');lookup={(c['endpoint_id'],c['field_name']):c for c in changes}
    check('unique_change_keys',len(lookup)==len(changes))
    reviews=read(BATCH/'reviewed_parameters.json')['records']
    check('fixed_42_main_reviews',len(reviews)==len({r['endpoint_id'] for r in reviews})==42)
    with parent.Database() as old,api.Database() as db:
        before={r['endpoint_id']:r for r in old.fetch('all_review').rows};after={r['endpoint_id']:r for r in db.fetch('all_review').rows}
        check('all_277_records',set(before)==set(after) and len(after)==277)
        for key,r in before.items():
            for field,value in r.items():
                if field.endswith('_status') and (key,field.removesuffix('_status')) in lookup:
                    check('new_field_status_'+key+'_'+field,after[key][field]=='v014_agent_reviewed_precycling_source')
                    continue
                if (key,field) not in lookup:check('old_field_'+key+'_'+field,after[key].get(field)==value)
                elif value is not None:raise AssertionError('Nonempty old value was changed')
            check('holds_identical_'+key,db.holds(key)==old.holds(key))
        for c in changes:
            key=c['endpoint_id'];field=c['field_name'];r=after[key]
            check('fill_only_'+key+'_'+field,before[key].get(field) is None and r[field]==c['after'])
            if c['scope']=='test':check('no_test_transfer_'+key+'_'+field,key==c['reviewed_endpoint'])
            else:check('same_material_only_'+key+'_'+field,r['material_key_v11']==before[c['reviewed_endpoint']]['material_key_v11']==c['material_key'])
            check('direct_evidence_'+key+'_'+field,bool(c['evidence']) and all(field in e['fields'] and sha(ROOT/e['path'])==e['sha256'] for e in c['evidence']))
            check('public_evidence_'+key+'_'+field,any(e.get('review_version')=='v0.14' and e.get('value_json')==json.dumps(c['after'],ensure_ascii=False,sort_keys=True) for e in db.evidence(key,field)))
        cohorts={}
        for profile in db.contract['profiles']:
            a=old.fetch(profile);b=db.fetch(profile)
            check('membership_identical_'+profile,[r['endpoint_id'] for r in a.rows]==[r['endpoint_id'] for r in b.rows])
            check('core_target_weight_identical_'+profile,a.feature_matrix()==b.feature_matrix())
            q=assess(b);checks.extend(profile+'_'+x for x in q['quality_checks'])
            cohorts[profile]=dict(rows=len(b.rows),source_groups=len({r['source_group'] for r in b.rows}))
        matrices=[db.material_matrix(),db.material_matrix(extra_features=db.contract['model_material_features']+db.contract['process_feature_fields_v14'])]
        for j,mat in enumerate(matrices):
            for n,fold in enumerate(mat['source_folds']):
                prepared=prepare_material_fold(mat,fold)
                check(f'material_fold_{j}_{n}',all(math.isfinite(x) for key in ['X_train','X_validation'] for row in prepared[key] for x in row))
                altered=copy.deepcopy(mat)
                for i in fold['test']:
                    for k,f in enumerate(mat['feature_names']):
                        if f not in mat['categorical_features']:altered['X'][i][k]=999999999
                    altered['y'][i]=999999
                again=prepare_material_fold(altered,fold)
                check(f'material_no_holdout_leak_{j}_{n}',prepared['X_train']==again['X_train'])
        rows=db.fetch().rows;by_name={r['sample_name']:r for r in rows}
        check('KAC_two_temperatures',by_name['KAC-5']['precarbonization_temperature_C']==800 and by_name['KAC-5']['activation_temperature_C']==600)
        check('SS300_two_temperatures',by_name['SS-300']['precarbonization_temperature_C']==300 and by_name['SS-300']['activation_temperature_C']==600)
        for name in ['QSC','AC-850','CA-AA','AC_rice_straw','AO-PC','SC-0.03']:
            check('no_false_activation_'+name,by_name[name].get('activation_temperature_C') is None)
        for name in ['OPBNP','OPB','OPNP','OPC','YZPC-3','CA-AA']:
            check('no_range_midpoint_'+name,by_name[name].get('mass_loading_mg_cm2') is None and by_name[name].get('mass_loading_range_mg_cm2_v14') is not None)
        check('no_device_loading_to_SS3E',by_name['SS-300'].get('mass_loading_mg_cm2') is None)
        check('no_stock_ink_mass_as_loading',by_name['P-doped CSKOH'].get('mass_loading_mg_cm2') is None)
        check('no_pretreatment_ramp_to_NCHU_activation',by_name['NCHU20'].get('heating_rate_C_min') is None and by_name['NCHU20']['pretreatment_heating_rate_C_min']==10)
        check('no_precarbonization_ramp_to_AHPC_activation',by_name['AHPC-850'].get('heating_rate_C_min') is None and by_name['AHPC-850']['precarbonization_heating_rate_C_min']==5)
        check('microwave_power_not_temperature',by_name['EUAC1-60'].get('activation_temperature_C') is None and by_name['EUAC1-60']['microwave_power_W_v14']==900)
        check('AO_SI_DOI_search_rebound',any('supplementary.pdf' in e['path'] for e in db.search_native('Fabrication',doi='10.3390/nano13101654')))
        coverage={}
        fields=list(db.contract['model_material_features'])
        for field in fields:
            coverage[field]={}
            for label,d in [('before',old),('after',db)]:
                z=[r for r in d.fetch().rows if r.get(field) is not None]
                coverage[field][label]=dict(rows=len(z),source_groups=len({r['source_group'] for r in z}))
        oldcells=sum(v['before']['rows'] for v in coverage.values());newcells=sum(v['after']['rows'] for v in coverage.values());total=len(rows)*len(fields)
        check('fixed_denominator',len(fields)==18 and total==756)
        check('expected_coverage',oldcells==206 and newcells==299)
        audit=[]
        for r in rows:
            material_meta={f:r.get(f) for f in db.contract['parameter_fields_v14'] if r.get(f) is not None}
            audit.append(dict(endpoint_id=r['endpoint_id'],sample_name=r['sample_name'],source_group=r['source_group'],parameters=material_meta,
                still_missing_optional=[f for f in fields if r.get(f) is None],notes=next(x['notes'] for x in reviews if x['endpoint_id']==r['endpoint_id'])))
        stats=dict(version='v0.14',fixed_main_rows=42,fixed_source_groups=30,model_fits=0,
            field_changes=len(changes),enriched_endpoints=len({c['endpoint_id'] for c in changes}),
            optional_feature_count=18,optional_total_cells=total,before_nonmissing=oldcells,after_nonmissing=newcells,
            before_coverage_pct=100*oldcells/total,after_coverage_pct=100*newcells/total,feature_coverage=coverage,
            process_feature_fields=db.contract['process_feature_fields_v14'],all_records_admitted=False,
            note='Fixed18-feature/42-test denominator; stage-qualified optional features are additional and not mixed into this comparison.')
        write(BATCH/'parameter_coverage.json',stats);write(BATCH/'per_test_parameter_audit.json',audit)
    for p,h in originals.items():check('final_original_'+p,sha(ROOT/p)==h)
    result=dict(status='passed',checks_count=len(checks),checks=checks,cohorts=cohorts,parent_database_sha256=sha(PARENT/'cycling_v0_13.sqlite'),
        database_sha256=sha(OUT/'cycling_v0_14.sqlite'),field_changes=len(changes),reviewed_sources=30,reviewed_main_tests=42,
        protected_original_files=len(originals),model_fits=0,all_scientific_questions_resolved=False,all_records_admitted=False)
    write(OUT/'verification.json',result)
    print(json.dumps({k:v for k,v in result.items() if k!='checks'},ensure_ascii=False))
    print(json.dumps(stats,ensure_ascii=False))
if __name__=='__main__':main()
