"""Read-only verification of the evidence expansion and the sealed v0.6 parent."""
from pathlib import Path
import collections,csv,json,sqlite3
from build_expansion_v07_20261018 import ROOT,PARENT,OUT,BATCH,api,sha
from verify_training_ready_v06_20261018 import verify as verify_parent

def verify():
    parent_report=verify_parent();checks=[]
    def check(name,ok):
        checks.append({'check':name,'passed':bool(ok)})
        if not ok:raise AssertionError(name)
    p=sqlite3.connect((PARENT/'cycling_v0_6.sqlite').as_uri()+'?mode=ro',uri=True);p.row_factory=sqlite3.Row
    with api().Database() as db:
        c=db.conn
        check('sqlite_integrity',c.execute('pragma integrity_check').fetchone()[0]=='ok')
        check('foreign_keys',not c.execute('pragma foreign_key_check').fetchall())
        mutable={'field_observations','field_selection','field_selection_history','feature_cache_meta','model_feature_cache','extraction_run','reported_profile_admissions_v06','reported_training_rows_v06','source_visual_reviews_v06'}
        for name, in p.execute("select name from sqlite_master where type='table' and name not like 'sqlite_%'"):
            if name in mutable:continue
            quoted='"'+name.replace('"','""')+'"'
            check('inherited_table:'+name,collections.Counter(tuple(r) for r in c.execute('select * from '+quoted))==collections.Counter(tuple(r) for r in p.execute('select * from '+quoted)))
        for name in ['field_observations','field_selection_history','extraction_run','reported_training_rows_v06','source_visual_reviews_v06']:
            old=collections.Counter(tuple(r) for r in p.execute('select * from '+name));new=collections.Counter(tuple(r) for r in c.execute('select * from '+name));check('append_only:'+name,all(new[k]>=v for k,v in old.items()))
        for row in c.execute('select * from reported_admission_history_v07'):
            old=dict(p.execute('select * from reported_profile_admissions_v06 where profile=? and endpoint_id=?',(row['profile'],row['endpoint_id'])).fetchone());new=dict(c.execute('select * from reported_profile_admissions_v06 where profile=? and endpoint_id=?',(row['profile'],row['endpoint_id'])).fetchone())
            check('admission_change_chain:'+row['endpoint_id'],json.loads(row['old_json'])==old and json.loads(row['new_json'])==new)
        check('seven_admission_changes_only',c.execute('select count(*) from reported_admission_history_v07').fetchone()[0]==7)
        oldsel={(r['endpoint_id'],r['field_name']):r['observation_id'] for r in p.execute('select * from field_selection')};oldmax=p.execute('select max(selection_id) from field_selection_history').fetchone()[0]
        for row in c.execute('select * from field_selection_history where selection_id>? order by selection_id',(oldmax,)):
            key=(row['endpoint_id'],row['field_name']);check('field_change_chain:'+str(row['selection_id']),oldsel.get(key)==row['old_observation_id']);oldsel[key]=row['new_observation_id']
        check('selection_chain_final',oldsel=={(r['endpoint_id'],r['field_name']):r['observation_id'] for r in c.execute('select * from field_selection')})
        check('cache_matches_selection',set(tuple(r) for r in c.execute('select * from model_feature_cache'))==set(tuple(r) for r in c.execute('select * from model_feature_rows')))
        summary={}
        for profile,expected in [('reported_3e',(21,13)),('reported_2e',(11,11)),('reported_2e_residue',(13,12)),('reported_2e_approx',(14,13))]:
            ds=db.fetch(profile);matrix=ds.feature_matrix();groups=sorted(set(matrix['groups']));n=len(ds.rows)
            check(profile+':shape',(n,len(groups))==expected)
            export=json.loads((OUT/'training_inputs'/(profile+'.json')).read_text(encoding='utf-8'));check(profile+':export',export['matrix']==matrix and export['dataset_fingerprint']==ds.fingerprint())
            if profile!='reported_3e':check(profile+':unchanged',ds.fingerprint()==parent_report['cohorts'][profile]['fingerprint'])
            weights=collections.defaultdict(float)
            for r in ds.rows:
                weights[r['source_group']]+=r['source_weight'];check(profile+':group:'+r['endpoint_id'],r['source_group']==c.execute('select group_id from unified_source_groups where identity_key=?',(r['identity_key'],)).fetchone()[0])
            check(profile+':source_weights',all(abs(x-1)<1e-12 for x in weights.values()))
            tested=[]
            for i,fold in enumerate(ds.source_folds(len(groups))):
                tr,te=fold['train'],fold['test'];tested+=te
                check(profile+':source_fold:'+str(i),set(tr).isdisjoint(te) and set(tr)|set(te)==set(range(n)) and {matrix['groups'][j] for j in tr}.isdisjoint(matrix['groups'][j] for j in te))
            check(profile+':held_once',sorted(tested)==list(range(n)))
            with (OUT/'training_inputs'/(profile+'.csv')).open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
            check(profile+':csv',len(rows)==n and all(float(a['retention_pct'])==b['retention_pct'] for a,b in zip(rows,ds.rows)))
            summary[profile]={'records':n,'source_groups':len(groups),'features':len(ds.features),'fingerprint':ds.fingerprint()}
        for a in ['TE036','TE037','TE038']:check('derived_label:'+a,db.by_alias('TE',a)['retention_relation']=='derived_complement')
        for a in ['V05_008','V05_009','V05_010','V05_011']:check('no_fake_concentration_correction:'+a,db.by_alias('V05',a)['concentration_mol_L']==3)
        current_ids={r['endpoint_id'] for r in db.fetch().rows}
        for r in c.execute("select * from record_expansion_reviews_v07 where status!='approved_for_reported_protocol'"):check('pending_not_admitted:'+r['endpoint_id'],r['endpoint_id'] not in current_ids)
        check('candidate_counts',c.execute('select count(*),sum(new_to_registry) from candidate_sources_v07').fetchone()[:]==(15,13))
        check('new_article_types',dict(c.execute('select article_type,count(*) from candidate_sources_v07 where new_to_registry=1 group by article_type'))=={'research-article':11,'review-article':2})
        check('candidate_fulltext_search',bool(db.search_candidates('cycling')))
        check('unchanged_preprocessor',sha(OUT/'preprocessing.py')==sha(PARENT/'preprocessing.py'))
        check('no_research_training',not db.contract['research_training_authorized'])
        maxobs=p.execute('select max(observation_id) from field_observations').fetchone()[0]
        for o in c.execute('select o.*,e.identity_key from field_observations o join model_endpoints e using(endpoint_id) where observation_id>?',(maxobs,)):
            check('own_source_observation:'+str(o['observation_id']),bool(c.execute('select 1 from paper_documents where identity_key=? and source_id=?',(o['identity_key'],o['source_id'])).fetchone()))
        for r in c.execute('select * from source_visual_reviews_v06'):check('visual:'+r['path'],sha(ROOT/r['path'])==r['sha256'])
    for r in json.loads((BATCH/'source_collection.json').read_text(encoding='utf-8')):check('collected_xml:'+r['pmcid'],sha(BATCH/'sources'/r['pmcid']/'main.xml')==r['sha256'])
    for r in json.loads((BATCH/'asset_collection.json').read_text(encoding='utf-8')):check('collected_asset_zip:'+r['pmcid'],sha(BATCH/'sources'/r['pmcid']/'primary_assets.zip')==r['sha256'])
    manifest=OUT/'merge_manifest.json'
    if manifest.exists():
        for r in json.loads(manifest.read_text(encoding='utf-8'))['outputs']:check('payload:'+r['path'],sha(ROOT/r['path'])==r['sha256'])
    p.close()
    return {'all_checks_passed':True,'parent_check_count':parent_report['check_count'],'parent_protected_file_count':parent_report['protected_file_count'],'new_check_count':len(checks),'cohorts':summary,'new_main_3e_records':7,'new_main_3e_source_groups':4,'new_candidate_identities':13,'all_candidates_admitted':False,'research_fits':0,'checks':checks}

if __name__=='__main__':
    import sys
    result=verify()
    if '--write-report' in sys.argv:(OUT/'最终核验.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='checks'},ensure_ascii=False))
