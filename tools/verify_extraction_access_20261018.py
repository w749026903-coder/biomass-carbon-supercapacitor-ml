"""Validate, export and seal the first systematic extraction/access release. Never fits."""
from pathlib import Path
import argparse,collections,csv,hashlib,json,math,sqlite3,statistics,sys,time
R=Path(__file__).resolve().parents[1];O=R/'循环稳定性数据库_v0.4_提取与调用_20261018';P=R/'循环稳定性数据库_v0.3_合并版_20261017';sys.path.insert(0,str(O))
from ml_data import Database,Dataset,DataNotReady,StaleCacheError

def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def js(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def dump(p,x):p.parent.mkdir(exist_ok=True,parents=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def export(name,rows,headers=None):
 dump(O/'exports'/f'{name}.json',rows)
 with (O/'exports'/f'{name}.csv').open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=headers or list(rows[0]) if rows else headers or ['endpoint_id']);w.writeheader();w.writerows(rows)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--seal',action='store_true');args=ap.parse_args()
 if args.seal and (O/'merge_manifest.json').exists():raise RuntimeError('Already sealed; default invocation verifies it read-only.')
 checks=[]
 def check(name,ok,detail=None):
  checks.append({'name':name,'passed':bool(ok),'detail':detail})
  if not ok:raise RuntimeError(name+': '+str(detail))
 sys.path.insert(0,str(R))
 from data.cycling_db import open_database
 with open_database() as public:
  check('Stable public entry returns53review rows',len(public.fetch('review_3e').rows)==53)
  check('Stable public pointer does not authorize training',public.contract['research_training_authorized'] is False)
 db=Database();c=db.conn;p=sqlite3.connect((P/'cycling_v0_3_merged.sqlite').as_uri()+'?mode=ro',uri=True);p.row_factory=sqlite3.Row
 check('SQLite integrity',c.execute('pragma integrity_check').fetchone()[0]=='ok');check('Foreign keys',not c.execute('pragma foreign_key_check').fetchall())
 for table, in p.execute("select name from sqlite_master where type='table' and name not like 'sqlite_%'"):
  check('Parent table all cells unchanged:'+table,p.execute('select * from "'+table+'"').fetchall()==c.execute('select * from "'+table+'"').fetchall())
 check('Parent database exact hash',sha(P/'cycling_v0_3_merged.sqlite')==json.loads(c.execute("select value_json from extraction_run where key='parent_database_sha256'").fetchone()[0]))
 # Protect the entire merged baseline, historical artifacts and read originals.
 protection={}
 for entry in js(P/'原始文件与父版本保护.json')+js(O/'本轮读取原件指纹.json')+js(P/'merge_manifest.json')['outputs']:
  path=Path(entry['path']);path=path if path.is_absolute() else R/path
  if str(path) in protection:check('Consistent expected hash:'+str(path),protection[str(path)]==entry['sha256'])
  protection[str(path)]=entry['sha256']
 for path,expected in protection.items():check('Protected input:'+path,Path(path).is_file() and sha(Path(path))==expected)
 check('Corpus identities all accounted',c.execute('select count(*) from extraction_queue').fetchone()[0]==226)
 check('Parse errors explicit',c.execute("select count(*) from document_sources where parse_status='parse_failed'").fetchone()[0]==0)
 check('No source/segment mismatch',c.execute('select count(*) from field_observations o join source_segments s using(segment_id) where o.source_id!=s.source_id').fetchone()[0]==0)
 check('Direct evidence belongs to same identity',c.execute('select count(*) from field_selection fs join field_observations o using(observation_id) join model_endpoints e on fs.endpoint_id=e.endpoint_id where o.source_id is not null and not exists(select 1 from paper_documents pd where pd.identity_key=e.identity_key and pd.source_id=o.source_id)').fetchone()[0]==0)
 check('Cache equals field projection',c.execute('select * from model_feature_cache order by endpoint_id').fetchall()==c.execute('select * from model_feature_rows order by endpoint_id').fetchall())
 histories=collections.defaultdict(list)
 for x in c.execute('select * from field_selection_history order by selection_id'):histories[(x['endpoint_id'],x['field_name'])].append(dict(x))
 for (ep,f),seq in histories.items():
  for a,b in zip(seq,seq[1:]):check('Append-only field transition:'+str(b['selection_id']),b['old_observation_id']==a['new_observation_id'])
  check('Final field selection:'+ep+':'+f,c.execute('select observation_id from field_selection where endpoint_id=? and field_name=?',(ep,f)).fetchone()[0]==seq[-1]['new_observation_id'])
 check('Automatic leads not promoted',c.execute('select count(*) from model_endpoints').fetchone()[0]==156 and c.execute('select sum(eligible) from native_measurement_claims').fetchone()[0]==0)
 check('No new approvals',c.execute("select count(*) from admission_reviews where status='approved'").fetchone()[0]==0)
 datasets={p:db.fetch(p) for p in ['strict_2e','strict_3e','review_3e','all_review','proposal_2e']}
 check('Strict cohorts remain empty',len(datasets['strict_2e'].rows)==len(datasets['strict_3e'].rows)==0)
 check('TE aliases all retained',len(datasets['review_3e'].rows)==53 and c.execute("select count(*) from endpoint_aliases where namespace='TE'").fetchone()[0]==53)
 check('BET40 and pore22',c.execute('select sum(BET_m2_g is not null),sum(total_pore_volume_cm3_g is not null) from review_3e_rows').fetchone()[:]==(40,22))
 check('TE005 concentration corrected2M',db.by_alias('TE','TE005')['concentration_mol_L']==2)
 check('TE044 concentration corrected3M',db.by_alias('TE','TE044')['concentration_mol_L']==3)
 check('TE043 current recovered5A/g and approx retained',db.by_alias('TE','TE043')['reported_current_A_g']==5 and db.by_alias('TE','TE043')['retention_relation']=='approx')
 check('Conflicting1M/6M withheld',db.by_alias('TE','TE010')['concentration_mol_L'] is None)
 check('BET area unit conflict withheld',db.by_alias('TE','TE009')['BET_m2_g'] is None)
 check('Printed pore unit conflict withheld',all(db.by_alias('TE',x)['total_pore_volume_cm3_g'] is None for x in ['TE008','TE033','TE034']))
 check('uMPC uses own SI1704.20 not precursor1554.54',db.by_alias('TE','TE053')['BET_m2_g']==1704.2)
 check('NSHPC2 own SI672.19',db.by_alias('TE','TE049')['BET_m2_g']==672.19)
 check('BJH and micropore not mislabeled total',db.by_alias('TE','TE012')['total_pore_volume_cm3_g'] is None and db.by_alias('TE','TE051')['total_pore_volume_cm3_g'] is None)
 check('Method window never fills cycle window',db.by_alias('TE','TE007')['characterization_voltage_lower_V']==-1 and db.by_alias('TE','TE007')['cycle_voltage_lower_V'] is None)
 check('Own cycle-specific window extracted',db.by_alias('TE','TE013')['cycle_voltage_lower_V']==-1 and db.by_alias('TE','TE013')['cycle_voltage_upper_V']==0)
 check('Qualitative near100 not exact numeric label',db.by_alias('B20','B2_018:1')['retention_pct'] is None)
 temps=[db.by_alias('B20',x) for x in ['B2_013:1','B2_013:2']];check('Same material separate temperature tests',temps[0]['material_id']==temps[1]['material_id'] and temps[0]['test_id']!=temps[1]['test_id'] and {v['temperature_C'] for v in temps}=={-60,100})
 check('mol/kg not converted to mol/L',db.by_alias('legacy','R012_CY01')['concentration_mol_L'] is None)
 check('R091 printed pore unit still masked',db.by_alias('legacy','R091_CY01')['total_pore_volume_cm3_g'] is None)
 check('Source field statuses distinguish holds',len({x['BET_m2_g_status'] for x in datasets['review_3e'].rows})>3)
 check('Forbidden predictors absent',not set(db.contract['forbidden_predictors'])&set(db.contract['core_features']))
 for name in ['strict_3e','review_3e','proposal_2e']:
  try:datasets[name].feature_matrix();ok=False
  except DataNotReady:ok=True
  check('No silent training fallback:'+name,ok)
 sample={'metric_kind':'capacity_retention','retention_relation':'eq','system':'3E','method':'GCD'}
 try:Dataset('strict_3e',[sample],db.contract['core_features']).feature_matrix();ok=False
 except DataNotReady:ok=True
 check('Wrong capacity target rejected',ok)
 sample={'metric_kind':'capacitance_retention','retention_relation':'eq','system':'2E_symmetric','method':'GCD'}
 try:Dataset('strict_3e',[sample],db.contract['core_features']).feature_matrix();ok=False
 except DataNotReady:ok=True
 check('Wrong electrode system rejected',ok)
 coverage=set()
 for i,fold in enumerate(datasets['review_3e'].source_folds(5)):
  train={datasets['review_3e'].rows[j]['source_group'] for j in fold['train']};test={datasets['review_3e'].rows[j]['source_group'] for j in fold['test']};check('Source-group disjoint fold:'+str(i),not train&test);coverage.update(fold['test'])
 check('Every TE row in one heldout source fold',coverage==set(range(53)))
 for name,ds in datasets.items():
  weights=collections.defaultdict(float)
  for row in ds.rows:weights[row['source_group']]+=row['source_weight']
  check('Per-source weights sum one:'+name,all(abs(w-1)<1e-9 for w in weights.values()))
 try:c.execute('CREATE TABLE should_never_exist(x)');ok=False
 except sqlite3.OperationalError:ok=True
 check('API writes rejected by SQLite',ok)
 shadow=Database.__new__(Database);shadow.conn=sqlite3.connect(':memory:');c.backup(shadow.conn);shadow.conn.execute("update feature_cache_meta set value='-1' where key='selection_history_max_id'")
 try:shadow._check_cache();ok=False
 except StaleCacheError:ok=True
 shadow.close();check('Stale cache rejected in isolated memory fixture',ok)
 check('FTS locates own SI evidence',any(x['doi']=='10.1021/acsomega.8b03586' and x['locator']=='PDF p7' for x in db.search('672.19')))
 timings=[]
 for _ in range(10):
  start=time.perf_counter();db.fetch('review_3e');timings.append(1000*(time.perf_counter()-start))
 stats={'version':'v0.4_first_systematic_extraction_and_access','registry_identities':226,'documents':c.execute('select count(*) from document_sources').fetchone()[0],'segments':c.execute('select count(*) from source_segments').fetchone()[0],'structured_measurement_records':156,'records_with_numeric_N_and_retention':c.execute('select count(*) from model_feature_cache where cycle_count is not null and retention_pct is not null').fetchone()[0],'3E_priority_records':53,'3E_papers':41,'3E_BET_before_after':[5,40],'3E_total_pore_before_after':[3,22],'3E_reported_current_located':c.execute('select sum(reported_current_A_g is not null) from review_3e_rows').fetchone()[0],'main_and_SI_review_selection_events':90,'material_property_cells':c.execute('select count(*) from material_properties').fetchone()[0],'native_unreviewed_claims':495,'native_claim_papers':123,'fulltext_papers_scanned':179,'queue':[dict(x) for x in c.execute('select status,count(*) as count from extraction_queue group by status')],'open_extraction_issues':c.execute('select count(*) from extraction_issues i left join extraction_issue_resolutions r using(issue_id) where r.issue_id is null').fetchone()[0],'profile_counts':{k:len(v.rows) for k,v in datasets.items()},'query_latency_ms_same_process':{'median':statistics.median(timings),'max':max(timings),'calls':10},'protected_unique_files':len(protection),'research_fit_calls':0,'manual_full_corpus_admission_complete':False}
 if args.seal:
  for name,ds in datasets.items():export(name,ds.rows,['endpoint_id','source_group']+ds.features+['retention_pct'] if not ds.rows else None)
  for name in ['extraction_queue','extraction_issues','extraction_issue_resolutions','material_properties','admission_reviews','candidate_measurement_claims']:export(name,[dict(x) for x in c.execute('select * from '+name)])
  dump(O/'统计与质量.json',stats);dump(O/'核验报告.json',{'all_checks_passed':True,'checks_count':len(checks),'checks':checks,'technical_pass_does_not_clear_scientific_holds':True,'research_fit_calls':0})
  dump(O/'dataset_snapshots.json',{k:{'rows':len(v.rows),'source_groups':len({x['source_group'] for x in v.rows}),'fingerprint':v.fingerprint(),'training_authorized':False} for k,v in datasets.items()})
  (O/'schema.sql').write_text('\n\n'.join(x[0]+';' for x in c.execute('select sql from sqlite_master where sql is not null order by type,name')),encoding='utf-8')
  dump(O/'merge_manifest.json',{'schema':'existing-literature-extraction-access-v1','stage':'first_systematic_extraction_and_access_complete','parent_database_sha256':sha(P/'cycling_v0_3_merged.sqlite'),'database_sha256':sha(O/'cycling_v0_4.sqlite'),'scientific_training_admission':False,'ready_for_review':True,'ready_for_research_training':False,'remaining_manual_record_review_papers':138,'stats':stats,'outputs':[{'path':f.relative_to(R).as_posix(),'sha256':sha(f),'bytes':f.stat().st_size} for f in sorted(O.rglob('*')) if f.is_file() and f.name!='merge_manifest.json' and '__pycache__' not in f.parts]})
 elif (O/'merge_manifest.json').exists():
  for x in js(O/'merge_manifest.json')['outputs']:check('Sealed output:'+x['path'],sha(R/x['path'])==x['sha256'])
 p.close();db.close();print(json.dumps({'verified':True,'checks':len(checks),'stats':stats,'sealed':args.seal},ensure_ascii=False))
if __name__=='__main__':main()
