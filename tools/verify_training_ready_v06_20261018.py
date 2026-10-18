"""Read-only scientific-contract and payload checks; never calls model fit."""
from pathlib import Path
import collections,copy,csv,hashlib,json,sqlite3,sys
from prepare_training_inputs_v06 import module,VERSION,ROOT
PARENT=ROOT/'循环稳定性数据库_v0.5_逐条准入审查_20261018'

def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()

def verify():
    checks=[]
    def check(name,ok,detail=None):
        checks.append({'check':name,'passed':bool(ok),'detail':detail})
        if not ok:raise AssertionError(name+': '+str(detail))
    api=module()
    p=sqlite3.connect((PARENT/'cycling_v0_5.sqlite').as_uri()+'?mode=ro',uri=True)
    with api.Database() as db:
        c=db.conn
        check('parent_database_fingerprint',sha(PARENT/'cycling_v0_5.sqlite')==db.contract['parent_database_sha256'])
        check('sqlite_integrity',c.execute('pragma integrity_check').fetchone()[0]=='ok')
        check('foreign_keys',not c.execute('pragma foreign_key_check').fetchall())
        check('read_only_access',c.execute('pragma query_only').fetchone()[0]==1)
        changed={'field_observations','field_selection','field_selection_history','feature_cache_meta','model_feature_cache','extraction_run'}
        for name, in p.execute("select name from sqlite_master where type='table' and name not like 'sqlite_%'"):
            if name in changed:continue
            quoted='"'+name.replace('"','""')+'"'
            old=collections.Counter(tuple(x) for x in p.execute('select * from '+quoted))
            new=collections.Counter(tuple(x) for x in c.execute('select * from '+quoted))
            check('parent_table_preserved:'+name,old==new)
        for name,key in [('field_observations','observation_id'),('field_selection_history','selection_id'),('extraction_run','key')]:
            previous=[tuple(r) for r in p.execute('select * from '+name)]
            current={r[0]:tuple(r) for r in c.execute('select * from '+name)}
            check('append_only:'+name,all(current.get(r[0])==r for r in previous))
        check('feature_cache_matches_current_selection',set(tuple(r) for r in c.execute('select * from model_feature_cache'))==set(tuple(r) for r in c.execute('select * from model_feature_rows')))
        check('selection_matches_observation',c.execute('select count(*) from field_selection s join field_observations o using(observation_id) where s.endpoint_id!=o.endpoint_id or s.field_name!=o.field_name').fetchone()[0]==0)
        oldmax=p.execute('select max(selection_id) from field_selection_history').fetchone()[0]
        states={(r[0],r[1]):r[2] for r in p.execute('select * from field_selection')}
        for h in c.execute('select * from field_selection_history where selection_id>? order by selection_id',(oldmax,)):
            check('selection_chain:'+str(h['selection_id']),states.get((h['endpoint_id'],h['field_name']))==h['old_observation_id'])
            states[h['endpoint_id'],h['field_name']]=h['new_observation_id']
        check('selection_chain_final',states=={(r[0],r[1]):r[2] for r in c.execute('select * from field_selection')})
        expected={'reported_3e':(14,9,8),'reported_2e':(11,11,7),'reported_2e_residue':(13,12,7),'reported_2e_approx':(14,13,7)}
        datasets={};cohorts={};source_identities={}
        for profile,(n,g,f) in expected.items():
            ds=db.fetch(profile);datasets[profile]=ds;matrix=ds.feature_matrix()
            check(profile+':shape',(len(ds.rows),len(set(matrix['groups'])),len(ds.features))==(n,g,f))
            check(profile+':no_predictor_leakage',not set(ds.features)&set(db.contract['forbidden_predictors']))
            check(profile+':not_fitted',not matrix['training_authorized'])
            weights=collections.defaultdict(float)
            for row in ds.rows:
                weights[row['source_group']]+=row['source_weight']
                group=c.execute('select group_id from unified_source_groups where identity_key=?',(row['identity_key'],)).fetchone()[0]
                check(profile+':group:'+row['endpoint_id'],group==row['source_group'])
                if row['identity_key'] in source_identities:check(profile+':cross_profile_group:'+row['endpoint_id'],source_identities[row['identity_key']]==group)
                source_identities[row['identity_key']]=group
                check(profile+':review:'+row['endpoint_id'],bool(row['profile_review']['evidence']))
                check(profile+':no_invented_current_conversion:'+row['endpoint_id'],row['canonical_current_A_g'] is None and row['physical_current_harmonized'] is False)
            check(profile+':equal_source_weight',all(abs(w-1)<1e-12 for w in weights.values()))
            folds=ds.source_folds(g);seen=[]
            for i,fold in enumerate(folds):
                train,test=fold['train'],fold['test'];seen+=test
                check(profile+':fold:'+str(i),bool(train) and bool(test) and set(train).isdisjoint(test) and set(train)|set(test)==set(range(n)) and set(matrix['groups'][j] for j in train).isdisjoint(matrix['groups'][j] for j in test))
            check(profile+':each_row_held_once',sorted(seen)==list(range(n)))
            export=json.loads((VERSION/'training_inputs'/(profile+'.json')).read_text(encoding='utf-8'))
            check(profile+':json_export',export['dataset_fingerprint']==ds.fingerprint() and export['matrix']==matrix and export['leave_one_source_out']==folds)
            with (VERSION/'training_inputs'/(profile+'.csv')).open(encoding='utf-8-sig',newline='') as file:
                csvrows=list(csv.DictReader(file))
            check(profile+':csv_export',len(csvrows)==n and all(float(a['retention_pct'])==b['retention_pct'] and all(a[k]==str(b[k]) for k in ds.features) for a,b in zip(csvrows,ds.rows)))
            cohorts[profile]={'records':n,'source_groups':g,'features':f,'fingerprint':ds.fingerprint()}
        check('default_restored',db.fetch().profile=='reported_3e')
        ids=lambda profile:{r['endpoint_id'] for r in datasets[profile].rows}
        check('nested_sensitivity',ids('reported_2e')<ids('reported_2e_residue')<ids('reported_2e_approx'))
        for old,new in [('literature_core7_exact','reported_2e'),('literature_residue_sensitivity','reported_2e_residue'),('literature_approx_sensitivity','reported_2e_approx')]:
            parentrows=[dict(zip([x[1] for x in p.execute('pragma table_info(training_rows_r4)')],r)) for r in p.execute('select * from training_rows_r4 where profile=?',(old,))]
            effective={r['record_id']:r for r in datasets[new].rows if 'record_id' in r}
            keys=['cycle_count','retention_pct','retention_relation','system','method','reported_current_A_g','BET_m2_g','voltage_lower_V','voltage_upper_V']
            check('r4_effective_values_preserved:'+old,all(all(effective[r['record_id']][k]==r[k] for k in keys) for r in parentrows))
        good=datasets['reported_3e']
        allowed=copy.deepcopy(good);allowed.rows[0]['current_mass_basis']=None;allowed.rows[0]['baseline_cycle']=None
        check('unknown_mass_and_cycle_index_do_not_block_reported',bool(allowed.feature_matrix()['X']))
        for field,value in [('reported_current_A_g',None),('metric_kind','capacity_retention'),('system','2E_symmetric'),('method','CV'),('cycle_voltage_upper_V',-2),('retention_relation','approx'),('BET_m2_g',0),('retention_pct',float('nan'))]:
            bad=copy.deepcopy(good);bad.rows[0][field]=value
            try:bad.feature_matrix();rejected=False
            except api.DataNotReady:rejected=True
            check('bad_input_rejected:'+field,rejected)
        for profile in ['strict_2e','strict_3e','review_3e','review_3e_all','all_review','proposal_2e']:
            try:db.fetch(profile).feature_matrix();rejected=False
            except api.DataNotReady:rejected=True
            check('unadmitted_not_exported:'+profile,rejected)
        ca=db.by_alias('TE','TE035');oldobs=db.evidence(ca['endpoint_id'],'retention_pct')
        check('CA_AA_configuration_correction',ca['retention_pct']==101.35 and any(json.loads(r['value_json'])==102 for r in oldobs))
        for alias in ['TE033','TE034']:
            r=db.by_alias('TE',alias);check('optional_pore_mask:'+alias,r['total_pore_volume_cm3_g'] is None and r['raw_total_pore_volume_m3_g'] is not None)
        for namespace,alias in [('TE','TE011'),('V05','V05_016')]:
            r=db.by_alias(namespace,alias);check('real_pending_retained:'+alias,r['endpoint_id'] not in set.union(*(ids(k) for k in expected)))
        check('all_endpoints_have_reported_disposition',c.execute('select count(*) from model_endpoints e where not exists(select 1 from reported_profile_admissions_v06 a where a.endpoint_id=e.endpoint_id)').fetchone()[0]==0)
        check('automatic_claims_not_admitted',c.execute('select count(*) from native_measurement_claims where eligible!=0').fetchone()[0]==0)
        for r in c.execute('select * from source_visual_reviews_v06'):
            check('visual_evidence:'+r['path'],sha(ROOT/r['path'])==r['sha256'])
        check('fulltext_search_available',bool(db.search('cycling',limit=1)))
    p.close()
    protected=json.loads((PARENT/'原始文件与父版本保护.json').read_text(encoding='utf-8'))
    protected+=json.loads((PARENT/'merge_manifest.json').read_text(encoding='utf-8'))['outputs']
    protected.append({'path':(PARENT/'merge_manifest.json').relative_to(ROOT).as_posix(),'sha256':sha(PARENT/'merge_manifest.json')})
    seen=set()
    for r in protected:
        path=(ROOT/r['path']).resolve()
        if path in seen:continue
        label=path.relative_to(ROOT).as_posix() if ROOT in path.parents else str(path)
        seen.add(path);check('protected:'+label,path.is_file() and sha(path)==r['sha256'])
    manifest=VERSION/'merge_manifest.json'
    if manifest.exists():
        for r in json.loads(manifest.read_text(encoding='utf-8'))['outputs']:
            check('payload:'+r['path'],sha(ROOT/r['path'])==r['sha256'])
    return {'all_checks_passed':True,'check_count':len(checks),'protected_file_count':len(seen),'cohorts':cohorts,'research_model_fits':0,'all_records_admitted':False,'checks':checks}

if __name__=='__main__':
    result=verify()
    if '--write-report' in sys.argv:
        (VERSION/'最终核验.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='checks'},ensure_ascii=False))
