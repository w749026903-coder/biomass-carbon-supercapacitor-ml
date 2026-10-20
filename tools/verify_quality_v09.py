"""Verify scientific delta lineage, frozen base, materialized inputs and grouped readiness."""
from pathlib import Path
import collections, copy, csv, hashlib, importlib.util, json, math, sqlite3, sys
from build_quality_v09 import ROOT,BATCH,OUT,PARENT,PARENT_SHA,sha,read,write,api
from training_input_quality import assess,prepare_source_fold

def verify():
    checks=[]
    def check(name,ok):
        if not ok:raise AssertionError(name)
        checks.append(name)
    # Reuse the established audit without rewriting any sealed reports.
    import verify_incoming_v08_20261020 as prior
    parent_report=prior.verify(write=False)
    check('parent_full_audit',parent_report['all_technical_checks_passed'])
    check('parent_database_sha256',sha(PARENT/'cycling_v0_8.sqlite')==PARENT_SHA)
    for item in read(PARENT/'merge_manifest.json')['outputs']:
        check('sealed_parent_payload:'+item['path'],sha(ROOT/item['path'])==item['sha256'])
    c=sqlite3.connect((OUT/'cycling_v0_9.sqlite').as_uri()+'?mode=ro',uri=True)
    check('delta_integrity',c.execute('pragma integrity_check').fetchone()[0]=='ok')
    check('delta_foreign_keys',not c.execute('pragma foreign_key_check').fetchall())
    cases=read(BATCH/'curation_delta.json');old={r['record_id']:r for r in read(ROOT/'新增文献整理_20261020/normalized_tests.json')}
    for case in cases:
        check('previous_values_preserved:'+case['record_id'],case['before']==old[case['record_id']])
        for e in case['evidence']:check('own_delta_evidence:'+case['record_id']+':'+e['locator'],sha(ROOT/e['path'])==e['sha256'] and e.get('document_id',case['after']['document_id'])==case['after']['document_id'])
        check('no_fake_canonical_current:'+case['record_id'],case['after']['canonical_current_A_g'] is None and not case['after']['physical_current_harmonized'])
    check('corrected_records',len(cases)==9)
    check('new_approved_records',sum(bool(r['profiles']) for r in cases)==7)
    check('two_exact_SI_identities',len(read(BATCH/'SI_identity_reviews.json'))==2 and all(x['identity_verified'] for x in read(BATCH/'SI_identity_reviews.json')))
    expected={'reported_3e':(31,23),'reported_2e':(25,20),'reported_2e_residue':(27,21),'reported_2e_approx':(29,23)}
    report={}
    with api().Database() as db:
        for profile,shape in expected.items():
            ds=db.fetch(profile);quality=assess(ds);report[profile]={**quality,'fingerprint':ds.fingerprint()}
            check('cohort:'+profile,(len(ds.rows),len({r['source_group'] for r in ds.rows}))==shape)
            snapshot=read(OUT/(profile+'_inputs.json'))
            check('JSON_matrix:'+profile,snapshot['matrix']==ds.feature_matrix() and snapshot['fingerprint']==ds.fingerprint())
            cached=[json.loads(r[0]) for r in c.execute('select row_json from training_rows_v09 where profile=? order by source_group,endpoint_id',(profile,))]
            check('SQL_snapshot:'+profile,cached==ds.rows)
            with (OUT/(profile+'_inputs.csv')).open(encoding='utf-8-sig',newline='') as f:csvrows=list(csv.DictReader(f))
            check('CSV_labels:'+profile,len(csvrows)==len(ds.rows) and all(a['endpoint_id']==b['endpoint_id'] and float(a['retention_pct'])==b['retention_pct'] for a,b in zip(csvrows,ds.rows)))
            # Exact conditional-test keys; same sample tested in different electrolyte stays distinct.
            keys=[(r['source_group'],r['system'],str(r['sample_name']).lower(),r['cycle_count'],r['reported_current_A_g'],r['electrolyte'],r['concentration_mol_L'],r['cycle_voltage_lower_V'],r['cycle_voltage_upper_V'],r.get('reference_electrode')) for r in ds.rows]
            check('no_duplicate_tests:'+profile,len(keys)==len(set(keys)))
            # Inner model-selection folds must only reference the outer training sources.
            for n,outer in enumerate(snapshot['source_folds']):
                train=outer['train'];groups=sorted({ds.rows[i]['source_group'] for i in train})
                inner=[]
                for k in range(min(5,len(groups))):
                    held=set(groups[k::min(5,len(groups))]);tr=[i for i in train if ds.rows[i]['source_group'] not in held];va=[i for i in train if ds.rows[i]['source_group'] in held]
                    check('nested_group_split:'+profile+':'+str(n)+':'+str(k),set(tr)|set(va)==set(train) and set(tr).isdisjoint(va) and {ds.rows[i]['source_group'] for i in tr}.isdisjoint(ds.rows[i]['source_group'] for i in va) and set(va).isdisjoint(outer['test']))
                    split={'train':tr,'test':va,'outer_holdout':outer['test']}
                    encoded=prepare_source_fold(ds,split)
                    check('nested_preprocessor_isolated:'+profile+':'+str(n)+':'+str(k),set(encoded['train_indices'])==set(tr) and set(encoded['validation_indices'])==set(va) and set(encoded['outer_holdout_indices'])==set(outer['test']))
                    inner.append(split)
                outer['inner_folds']=inner
            write(OUT/(profile+'_nested_fold_plan.json'),snapshot['source_folds'])
            for field,value in [('metric_kind','coulombic_efficiency'),('reported_current_A_g',None),('BET_m2_g',float('nan')),('method','CV')]:
                invalid=copy.deepcopy(ds);invalid.rows[0][field]=value
                try:invalid.feature_matrix()
                except ValueError:checks.append('bad_inputs_rejected:'+profile+':'+field)
                else:raise AssertionError('Invalid training input accepted')
        ids={r['endpoint_id'] for r in db.fetch().rows}|{r['endpoint_id'] for r in db.fetch('reported_2e').rows}
        for r in db.incoming_tests():
            case=next((x for x in cases if x['record_id']==r['record_id']),None)
            if not r['eligible']:check('pending_excluded:'+r['record_id'],r['endpoint_id'] not in ids)
        check('approx_not_exact_main','incoming:ADD_030_T01' not in ids)
        check('year_correction_applied',any(r['record_id']=='ADD_052_T01' and r['source_year']==2025 for r in db.fetch('incoming_review',year_min=2025,year_max=2025).rows))
        check('LYS_window_own_SI',any(e.get('kind')=='publisher_SI_DOCX' and 'FigS7' in e.get('locator','') for e in db.evidence('incoming:ADD_026_T02','cycle_voltage_upper_V') if e.get('selected')))
        check('sparse_profile_separation',all(r['system']=='3E' for r in db.fetch().rows) and all(r['system']=='2E_symmetric' for r in db.fetch('reported_2e').rows))
        check('strict_views_unchanged',not db.fetch('strict_2e').rows and not db.fetch('strict_3e').rows)
        check('research_fit_not_authorized',not db.contract['research_training_authorized'])
    c.close()
    return {'all_technical_checks_passed':True,'check_count':len(checks),'fold_quality_checks':sum(len(q['quality_checks']) for q in report.values()),
            'parent_v08_checks':parent_report['check_count'],'older_checks':parent_report['inherited_v07_check_counts'],
            'parent_database_unchanged':True,'all_original_sources_retained':True,'data_preparation_ready':True,'all_literature_admitted':False,
            'cohorts':report,'research_model_fits':0,'formal_training_authorized':False,'checks':checks}
if __name__=='__main__':
    result=verify();write(OUT/'最终核验.json',result)
    print(json.dumps({k:v for k,v in result.items() if k not in ['checks','cohorts']},ensure_ascii=False,indent=2))
