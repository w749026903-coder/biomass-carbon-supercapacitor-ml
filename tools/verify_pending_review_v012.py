"""Independently verify the additive review, protected inputs and public model API."""
from pathlib import Path
from contextlib import closing
import collections,copy,hashlib,importlib.util,json,math,sqlite3,sys

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'循环稳定性数据库_v0.12_待补证精细复核_20261022'
BATCH=ROOT/'待补证原文复核_20261022'
PARENT=ROOT/'循环稳定性数据库_v0.11_全库复检与材料特征_20261021'

def read(p):return json.loads(p.read_text('utf-8'))
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def module(p,n):
    s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);sys.modules[n]=m;s.loader.exec_module(m);return m

def main():
    checks=[]
    def check(name,condition):
        if not condition:raise AssertionError(name)
        checks.append(name)
    current=module(OUT/'ml_data.py','_v012_verifier_current');previous=module(PARENT/'ml_data.py','_v012_verifier_previous')
    check('immutable_v11_parent',sha(PARENT/'cycling_v0_11.sqlite')=='5492ec9c8b321aa27af72273d60ffb32d4a26b986528cda27c28db2b3ad12322')
    corpus=ROOT/'全库复检与特征补提取_20261021/full_corpus_search_native.sqlite'
    check('immutable_native_corpus',sha(corpus)=='f2720c3e417904dad5857a6574cc72d5cf996f9b8716620d69594f11380c658c')
    for path in [OUT/'cycling_v0_12.sqlite',PARENT/'cycling_v0_11.sqlite',corpus]:
        with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)) as c:
            check('integrity_'+path.name,c.execute('pragma integrity_check').fetchone()[0]=='ok')
            check('foreign_keys_'+path.name,not c.execute('pragma foreign_key_check').fetchall())
    protected=read(BATCH/'protected_sources.json')
    for p,h in protected.items():check('source_hash_'+p,sha(ROOT/p)==h)
    # Also verify the complete fixed-queue source inventory, including sources
    # which generated no selected field and were not copied or rewritten.
    packet_sources={s['path']:s['sha256'] for p in read(BATCH/'original_review_packets.json') for s in p['sources']}
    for p,h in packet_sources.items():check('packet_source_hash_'+p,sha(Path(p))==h)
    cases=read(BATCH/'effective_reviews.json');changes=read(BATCH/'field_changes.json')
    with previous.Database() as old,current.Database() as db:
        before={r['endpoint_id']:r for r in old.fetch('all_review').rows}
        after={r['endpoint_id']:r for r in db.fetch('all_review').rows}
        check('all_277_rows_retained',len(before)==len(after)==277 and set(before)==set(after))
        allowed=collections.defaultdict(set)
        for c in cases:
            check('historical_holds_'+c['endpoint_id'],c['previous_holds']==old.holds(c['endpoint_id']))
            keys=[c['endpoint_id']]
            for field in c['changes']:
                if c.get('propagate_material_fields') and field in {'BET_m2_g','bulk_N_wt_pct','bulk_O_wt_pct','bulk_O_method','XPS_N_reported_pct','XPS_O_reported_pct','XPS_percentage_basis','N_at_pct','O_at_pct','C_at_pct','S_at_pct','activation_temperature_C','activation_duration_h','total_pore_volume_cm3_g','micropore_volume_cm3_g','micropore_surface_area_m2_g','average_pore_diameter_nm','XRD_d002_nm'}:
                    keys=[k for k,r in before.items() if r.get('material_key_v11')==before[c['endpoint_id']].get('material_key_v11')]
                else:keys=[c['endpoint_id']]
                for key in keys:allowed[key]|={field,field+'_status'}
        system_fields={'source_weight','eligible','admission_status','admission_profiles_v12','review_disposition_v12','review_reason_v12'}
        for key,row in before.items():
            for field in row:
                if field not in allowed[key]|system_fields:check('unchanged_'+key+'_'+field,row[field]==after[key].get(field))
        for change in changes:
            key,f=change['endpoint_id'],change['field_name']
            check('original_value_'+key+'_'+f,before[key].get(f)==change['before'])
            check('current_value_'+key+'_'+f,after[key].get(f)==change['after'])
        for profile in ['reported_3e','reported_2e','reported_2e_residue','reported_2e_approx']:
            a=old.fetch(profile);b=db.fetch(profile);core=a.features+['retention_pct','source_group','retention_relation']
            check('old_members_retained_'+profile,{r['endpoint_id'] for r in a.rows}<={r['endpoint_id'] for r in b.rows})
            for row in a.rows:check('old_core_unchanged_'+profile+'_'+row['endpoint_id'],all(row[f]==after[row['endpoint_id']][f] for f in core))
            if profile!='reported_3e':check('unchanged_2e_members_'+profile,{r['endpoint_id'] for r in a.rows}=={r['endpoint_id'] for r in b.rows})
        membership={p:{r['endpoint_id'] for r in db.fetch(p).rows} for p in db.contract['profiles']}
        check('nested_3e_purposes',membership['reported_3e']<=membership['reported_3e_residue_sensitivity']<=membership['reported_3e_sensitivity'])
        expected_new={'candidate:TE026','legacy:R045_CY01','candidate:TE011','candidate:TE013','candidate:TE039'}
        check('five_explicit_main_admissions',membership['reported_3e']-{r['endpoint_id'] for r in old.fetch('reported_3e').rows}==expected_new)
        frozen={'candidate:TE010','candidate:V05:017','legacy:R069_CY01','legacy:R069_CY02','legacy:R069_CY03','legacy:R018_CY01','incoming:ADD_002_T01','incoming:ADD_002_T02','incoming:ADD_048_T01','incoming:ADD_035_T01','candidate:TE032'}
        check('scientific_conflicts_not_admitted',not(frozen&set.union(*membership.values())))
        check('Si_not_silently_main','legacy:R112_CY01' not in membership['reported_3e'] and 'legacy:R112_CY01' in membership['reported_3e_residue_sensitivity'])
        for key in ['legacy:R036_CY01','legacy:R032_CY01','candidate:V05:006']:
            check('CV_retained_not_GCD_'+key,after[key]['method']=='CV' and key not in set.union(*membership.values()))
        # Selected values are tied to the own-sample SI rows, not a comparison
        # material, a precursor, an atomic/weight conversion or post-cycle data.
        expected={'incoming:ADD_005_T01':{'bulk_N_wt_pct':5.69,'bulk_O_wt_pct':20.94,'activation_duration_h':1.5},
                  'incoming:ADD_027_T01':{'N_at_pct':1.62,'O_at_pct':12.33,'bulk_N_wt_pct':1.39,'bulk_O_wt_pct':19.23,'total_pore_volume_cm3_g':0.62},
                  'incoming:ADD_037_T01':{'total_pore_volume_cm3_g':1.4271,'micropore_volume_cm3_g':0.837}}
        for key,fields in expected.items():
            for same in [r for r in after.values() if r['material_key_v11']==after[key]['material_key_v11']]:
                check('same_material_fields_'+same['endpoint_id'],all(same[f]==v for f,v in fields.items()))
        check('LC67_author_label_recovered',after['incoming:ADD_013_T01']['retention_pct']==76.16)
        check('BET_not_BJH',after['candidate:V05:025']['BET_m2_g']==865.26)
        check('SSK_not_CE',after['incoming:ADD_060_T01']['retention_pct']==91.6 and after['incoming:ADD_060_T01']['retention_relation']=='approx')
        check('raw_SI_table_query',any('5.69' in r['cells_json'] for r in db.search_tables('NCHU',doi='10.1016/j.biombioe.2026.109160',limit=30)))
        check('native_SI_query',any(r.get('path','').endswith('NCHU20_mmc1.docx') and r['training_eligible']==0 for r in db.search_native('5.69',doi='10.1016/j.biombioe.2026.109160')))
        check('field_evidence_callable',bool(db.evidence('incoming:ADD_027_T01','bulk_N_wt_pct')))
        check('material_history_callable',bool(db.material_properties(after['incoming:ADD_027_T01']['material_key_v11'],selected_only=False)))
        check('current_nested_admission_checks',all(r['status']=='approved_for_reported_protocol' for r in db.admission_checks(next(iter(membership['reported_3e'])), 'reported_3e_sensitivity')))
        ds=db.fetch('reported_3e')
        for field,value in [('BET_m2_g',None),('BET_m2_g',0),('BET_m2_g',math.nan),('baseline_reference',None),('method','CV'),('retention_relation','gt'),('metric_kind','coulombic_efficiency')]:
            invalid=copy.deepcopy(ds);invalid.rows[0][field]=value
            try:invalid.feature_matrix()
            except current.DataNotReady:checks.append('invalid_input_rejected_'+field+'_'+str(value))
            else:raise AssertionError('Invalid model input accepted: '+field)
        for profile in db.contract['profiles']:
            rows=db.fetch(profile).rows;doi_groups=collections.defaultdict(set)
            for r in rows:doi_groups[r['source_group'].lower().removeprefix('doi:')].add(r['source_group'])
            check('no_DOI_alias_group_leak_'+profile,all(len(v)==1 for v in doi_groups.values()))
            check('no_duplicate_test_'+profile,len({(r['source_group'],r['sample_name'],r['cycle_count'],r['reported_current_A_g'],r['electrolyte'],r['concentration_mol_L']) for r in rows})==len(rows))
        try:db.delta_v12.execute('update review_rows_v12 set row_json=row_json where 0')
        except sqlite3.OperationalError:checks.append('readonly_api_enforced')
        else:raise AssertionError('Writable public database connection')
        cohorts={p:{'rows':len(db.fetch(p).rows),'source_groups':len({r['source_group'] for r in db.fetch(p).rows})} for p in db.contract['profiles']}
        dispositions=collections.Counter(c['disposition'] for c in cases if c['endpoint_id'] in {r['endpoint_id'] for p in read(BATCH/'original_review_packets.json') for r in p['rows']})
        material=db.material_matrix();coverage={f:sum(row[i] is not None for row in material['X']) for i,f in enumerate(material['feature_names']) if f not in db.contract['core_features']}
        old_material=old.material_matrix();old_values={key:dict(zip(old_material['feature_names'],row)) for key,row in zip(old_material['endpoint_ids'],old_material['X'])}
        new_values={key:dict(zip(material['feature_names'],row)) for key,row in zip(material['endpoint_ids'],material['X'])}
        check('existing_optional_features_not_lost',all(new_values[key].get(field) is not None for key,row in old_values.items() for field,value in row.items() if value is not None))
        broad=db.fetch('reported_3e_sensitivity');bm=broad.feature_matrix()
        check('derived_complements_explicit',all(kind=='complement_of_author_reported_loss' for row,kind in zip(broad.rows,bm['label_evidence_kind']) if row['retention_relation']=='derived_complement'))
        table_count=db.delta_v12.execute('select count(*) from native_tables_v12').fetchone()[0]
    readiness=read(OUT/'training_readiness.json')
    check('zero_model_fits',readiness['model_fits']==0 and all(x['model_fits']==0 for x in readiness['cohorts'].values()))
    report={'status':'passed','checks_count':len(checks),'checks':checks,'protected_case_sources':len(protected),'fixed_queue_source_files_verified':len(packet_sources),
      'cohorts':cohorts,'fixed_queue_reviewed':87,'fixed_queue_dispositions':dict(dispositions),'field_changes':len(changes),
      'new_SI_files':len(read(BATCH/'SI_identity_reviews.json')),'new_raw_SI_tables':table_count,'sparse_material_nonmissing_counts':coverage,
      'model_fits':0,'all_scientific_questions_resolved':False,'all_records_admitted':False,
      'database_sha256':sha(OUT/'cycling_v0_12.sqlite'),'parent_database_sha256':sha(PARENT/'cycling_v0_11.sqlite'),'corpus_sha256':sha(corpus)}
    (OUT/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n','utf-8')
    print(json.dumps({k:report[k] for k in ['status','checks_count','field_changes','new_SI_files','new_raw_SI_tables','cohorts']},ensure_ascii=False))

if __name__=='__main__':main()
