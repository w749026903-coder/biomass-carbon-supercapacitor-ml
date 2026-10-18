"""Seal review exports after exact lineage, evidence and gate verification. No training."""
from pathlib import Path
import argparse,collections,csv,hashlib,importlib.util,json,sqlite3,sys,time
R=Path(__file__).resolve().parents[1];O=R/'循环稳定性数据库_v0.5_逐条准入审查_20261018';P=R/'循环稳定性数据库_v0.4_提取与调用_20261018'
def enc(x):return json.dumps(x,ensure_ascii=False)
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def dump(p,x):p.parent.mkdir(exist_ok=True,parents=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def export(name,rows):
 dump(O/'exports'/f'{name}.json',rows)
 with (O/'exports'/f'{name}.csv').open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]) if rows else ['endpoint_id']);w.writeheader();w.writerows(rows)

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--seal',action='store_true');args=ap.parse_args()
 if args.seal and (O/'merge_manifest.json').exists():raise RuntimeError('Already sealed; rerun without --seal for read-only validation.')
 if args.seal:
  w=sqlite3.connect(O/'cycling_v0_5.sqlite')
  # Reference is not applicable to2E. Keep that decision while refreshing its
  # evidence link after the3Efield review, and preserve the old link as audit.
  w.execute('CREATE TABLE IF NOT EXISTS gate_evidence_link_updates(update_id INTEGER PRIMARY KEY,endpoint_id TEXT,profile TEXT,criterion TEXT,old_evidence_json TEXT,new_evidence_json TEXT,reason TEXT)')
  for ep,profile,criterion,state,raw in w.execute("select endpoint_id,profile,criterion,status,evidence_json from record_admission_checks where profile='canonical_2e' and criterion='reference_electrode' and status='not_applicable'").fetchall():
   ev=json.loads(raw);current=w.execute("select f.observation_id,o.value_json from field_selection f join field_observations o using(observation_id) where f.endpoint_id=? and f.field_name='reference_electrode'",(ep,)).fetchone()
   if ev['selected_observations']['reference_electrode']!=current[0]:
    ev['selected_observations']['reference_electrode']=current[0];ev['current_values']['reference_electrode']=json.loads(current[1]);updated=enc(ev)
    w.execute('insert into gate_evidence_link_updates(endpoint_id,profile,criterion,old_evidence_json,new_evidence_json,reason) values (?,?,?,?,?,?)',(ep,profile,criterion,raw,updated,'Refresh observation reference after source review;2E not_applicable judgment unchanged.'))
    w.execute('update record_admission_checks set evidence_json=? where endpoint_id=? and profile=? and criterion=?',(updated,ep,profile,criterion))
  # Combine dynamic physical predicates from the parent with the new explicit
  # gates. Gate state is never an alternative to physical field validation.
  for name,system,profile,basis in [('training_ready_2e','2E_symmetric','canonical_2e','two_electrode_total_active_mass'),('training_ready_3e','3E','canonical_3e','working_electrode_active_mass')]:
   old=w.execute('select sql from prior_admission_view_sql where name=?',(name,)).fetchone()[0]
   w.execute('drop view '+name)
   extra=" AND f.retention_pct>=0 AND f.electrolyte IS NOT NULL AND f.electrolyte!='' AND EXISTS(SELECT 1 FROM record_gate_outcomes q WHERE q.endpoint_id=f.endpoint_id AND q.profile=a.profile AND q.status='approved') AND (SELECT count(*) FROM record_admission_checks q WHERE q.endpoint_id=f.endpoint_id AND q.profile=a.profile)=18 AND NOT EXISTS(SELECT 1 FROM record_admission_checks q WHERE q.endpoint_id=f.endpoint_id AND q.profile=a.profile AND q.status NOT IN ('pass','not_applicable'))"
   w.execute(old+extra)
  w.commit();w.close()
 name='_v05_seal_ml_data';spec=importlib.util.spec_from_file_location(name,O/'ml_data.py');module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
 db=module.Database();c=db.conn;p=sqlite3.connect((P/'cycling_v0_4.sqlite').as_uri()+'?mode=ro',uri=True);p.row_factory=sqlite3.Row
 checks=[]
 def ck(name,ok,detail=None):
  checks.append({'name':name,'passed':bool(ok),'detail':detail})
  if not ok:raise RuntimeError(name+':'+str(detail))
 ck('SQLite integrity',c.execute('pragma integrity_check').fetchone()[0]=='ok');ck('SQLite foreign keys',not c.execute('pragma foreign_key_check').fetchall())
 pm=read(P/'merge_manifest.json');ck('Parent DB unchanged',sha(P/'cycling_v0_4.sqlite')==pm['database_sha256'])
 special={'model_materials','model_tests','model_endpoints','endpoint_aliases','field_observations','field_selection','field_selection_history','extraction_issues','extraction_issue_resolutions','admission_reviews','extraction_run','model_feature_cache','feature_cache_meta'}
 for table, in p.execute("select name from sqlite_master where type='table' and name not like 'sqlite_%'"):
  if table in special:continue
  ck('Inherited table exact:'+table,[tuple(x) for x in p.execute('select * from "'+table+'"')]==[tuple(x) for x in c.execute('select * from "'+table+'"')])
 for table,pk in [('model_materials','material_id'),('model_tests','test_id'),('field_observations','observation_id'),('field_selection_history','selection_id'),('extraction_issues','issue_id'),('extraction_issue_resolutions','issue_id')]:
  for row in p.execute('select * from '+table):ck('Original row retained:'+table+':'+str(row[pk]),tuple(row)==tuple(c.execute('select * from '+table+' where '+pk+'=?',(row[pk],)).fetchone()))
 for row in p.execute('select * from endpoint_aliases'):ck('Original alias retained:'+row['namespace']+':'+row['alias'],tuple(row)==tuple(c.execute('select * from endpoint_aliases where namespace=? and alias=?',(row['namespace'],row['alias'])).fetchone()))
 changes=collections.defaultdict(list)
 for row in c.execute('select * from endpoint_metadata_changes order by change_id'):changes[row['endpoint_id']].append(dict(row))
 for old in p.execute('select * from model_endpoints'):
  new=dict(c.execute('select * from model_endpoints where endpoint_id=?',(old['endpoint_id'],)).fetchone());prior=dict(old)
  if prior!=new:
   seq=changes[old['endpoint_id']];ck('Changed metadata exact history:'+old['endpoint_id'],bool(seq))
   expected=json.loads(seq[-1]['new_value_json']);ck('Changed metadata limited to year:'+old['endpoint_id'],{k for k in prior if prior[k]!=new[k]}<= {'source_year','year_basis'} and new['source_year']==expected['source_year'])
   ck('Metadata old values retained:'+old['endpoint_id'],json.loads(seq[0]['old_value_json'])['source_year']==prior['source_year'])
  else:ck('Endpoint all metadata retained:'+old['endpoint_id'],True)
 histories=collections.defaultdict(list)
 for row in c.execute('select * from field_selection_history order by selection_id'):histories[(row['endpoint_id'],row['field_name'])].append(dict(row))
 for (ep,field),seq in histories.items():
  for left,right in zip(seq,seq[1:]):ck('Field transition linked:'+str(right['selection_id']),left['new_observation_id']==right['old_observation_id'])
  ck('Final selection linked:'+ep+':'+field,c.execute('select observation_id from field_selection where endpoint_id=? and field_name=?',(ep,field)).fetchone()[0]==seq[-1]['new_observation_id'])
 ck('Admission histories preserve parent initial state',all(c.execute('select old_status,old_reason from admission_review_history where endpoint_id=? and profile=? order by history_id limit 1',(x['endpoint_id'],x['profile'])).fetchone()[:]==(x['status'],x['reason']) for x in p.execute('select * from admission_reviews')))
 for pair in c.execute('select distinct endpoint_id,profile from admission_review_history'):
  seq=c.execute('select * from admission_review_history where endpoint_id=? and profile=? order by history_id',tuple(pair)).fetchall()
  ck('Admission chain:'+str(tuple(pair)),all((a['new_status'],a['new_reason'])==(b['old_status'],b['old_reason']) for a,b in zip(seq,seq[1:])) and (seq[-1]['new_status'],seq[-1]['new_reason'])==tuple(c.execute('select status,reason from admission_reviews where endpoint_id=? and profile=?',tuple(pair)).fetchone()))
 ck('Source segment hashes and locations same as parent',all([tuple(x) for x in p.execute('select * from '+t)]==[tuple(x) for x in c.execute('select * from '+t)] for t in ['document_sources','document_locations','source_segments','paper_documents']))
 ck('Selected evidence same identity',c.execute('select count(*) from field_selection f join field_observations o using(observation_id) join model_endpoints e on f.endpoint_id=e.endpoint_id where o.source_id is not null and not exists(select 1 from paper_documents p where p.identity_key=e.identity_key and p.source_id=o.source_id)').fetchone()[0]==0)
 ck('No cross-source segment links',c.execute('select count(*) from field_observations o join source_segments s using(segment_id) where o.source_id!=s.source_id').fetchone()[0]==0)
 ck('Feature cache exact', [tuple(x) for x in c.execute('select * from model_feature_cache order by endpoint_id')]==[tuple(x) for x in c.execute('select * from model_feature_rows order by endpoint_id')])
 ck('All191rowswith36profilechecks',c.execute('select count(*) from record_admission_checks').fetchone()[0]==191*36 and not c.execute('select endpoint_id,profile from record_admission_checks group by endpoint_id,profile having count(*)!=18').fetchall())
 ck('Gate selected observations current',all(c.execute('select observation_id from field_selection where endpoint_id=? and field_name=?',(q['endpoint_id'],f)).fetchone()[0]==oid for q in c.execute('select endpoint_id,evidence_json from record_admission_checks') for f,oid in json.loads(q['evidence_json']).get('selected_observations',{}).items()))
 ck('Gate outcome counts exact',all(x['failed_count']==c.execute("select count(*) from record_admission_checks where endpoint_id=? and profile=? and status='fail'",(x['endpoint_id'],x['profile'])).fetchone()[0] and x['unresolved_count']==c.execute("select count(*) from record_admission_checks where endpoint_id=? and profile=? and status='unresolved'",(x['endpoint_id'],x['profile'])).fetchone()[0] for x in c.execute('select * from record_gate_outcomes')))
 ck('81boundedpaperreviews',c.execute('select count(*) from paper_source_reviews').fetchone()[0]==81)
 ck('146isolatedclaimadjudications',c.execute('select count(*) from native_claim_adjudications').fetchone()[0]==146 and c.execute('select sum(eligible) from native_claim_adjudications').fetchone()[0]==0)
 ck('All495nativeclaimsremainisolated',c.execute('select count(*),sum(eligible) from native_measurement_claims').fetchone()[:]==(495,0))
 ck('No approvals',c.execute("select count(*) from admission_reviews where status='approved'").fetchone()[0]==0)
 ck('50TEreferencesandBET41',c.execute('select sum(reference_electrode is not null),sum(BET_m2_g is not null) from review_3e_rows').fetchone()[:]==(50,41))
 ck('SCreferenceAgClnotORRmercury',all(db.by_alias('TE',a)['reference_electrode']=='Ag/AgCl' for a in ['TE029','TE030']))
 ck('BSPCprintedreferenceunclearretained',db.by_alias('TE','TE048')['reference_electrode'] is None and db.by_alias('TE','TE048')['BET_m2_g']==425)
 ck('AFcharacterizationnotcycletransfer',all(db.by_alias('TE',f'TE{n:03}')['characterization_voltage_lower_V']==-.8 and db.by_alias('TE',f'TE{n:03}')['cycle_voltage_lower_V'] is None for n in range(14,20)))
 ck('RHcurrentconflictmasked',db.by_alias('V05','V05_004')['reported_current_A_g'] is None and {json.loads(x[0]) for x in c.execute("select value_json from field_observations where endpoint_id='candidate:V05:004' and status='conflicting_primary_report_not_selected'")}=={12,20})
 ck('Oldchemicalconflictfreeze',db.by_alias('TE','TE010')['concentration_mol_L'] is None and db.by_alias('TE','TE009')['BET_m2_g'] is None)
 ck('No invented admission/training permission',not db.contract['research_training_authorized'])
 ds={profile:db.fetch(profile) for profile in ['strict_2e','strict_3e','review_3e','review_3e_all','all_review','proposal_2e']}
 ck('Profiles exact sizes',{k:len(v.rows) for k,v in ds.items()}=={'strict_2e':0,'strict_3e':0,'review_3e':53,'review_3e_all':90,'all_review':191,'proposal_2e':8})
 ck('APIadmissionquery18',len(db.admission_checks('candidate:V05:004','canonical_2e'))==18 and db.review_summary()['records']==191)
 for profile in ds:
  if profile in ('strict_2e','strict_3e','review_3e','review_3e_all','proposal_2e','all_review'):
   try:ds[profile].feature_matrix();ok=False
   except module.DataNotReady:ok=True
   ck('Nounadmittedmatrixfallback:'+profile,ok)
  if len({x['source_group'] for x in ds[profile].rows})>=5:
   folds=ds[profile].source_folds(5);seen=[]
   for fold in folds:
    ck('Sourcefoldseparation:'+profile+':'+str(len(seen)),not {ds[profile].rows[i]['source_group'] for i in fold['train']}&{ds[profile].rows[i]['source_group'] for i in fold['test']});seen.extend(fold['test'])
   ck('Sourcefoldcoversexactlyonce:'+profile,sorted(seen)==list(range(len(ds[profile].rows))))
  weights=collections.defaultdict(float)
  for row in ds[profile].rows:weights[row['source_group']]+=row['source_weight']
  ck('Per-sourceweightsonly:'+profile,all(abs(x-1)<1e-9 for x in weights.values()))
 try:c.execute('create table invalid_write(x)');ok=False
 except sqlite3.OperationalError:ok=True
 ck('APIqueryonly',ok)
 # Mutating only an isolated RAMcopy proves an approval toggle cannot bypass
 # unresolvedgates, and fakegatepasses cannot bypassdynamicfieldpredicates.
 shadow=sqlite3.connect(':memory:');c.backup(shadow)
 shadow.execute("update admission_reviews set status='approved'");shadow.execute("update record_gate_outcomes set status='approved'")
 ck('Approvaltogglenotgatebypass',all(shadow.execute('select count(*) from '+v).fetchone()[0]==0 for v in ['training_ready_2e','training_ready_3e']))
 shadow.execute("update record_admission_checks set status='pass'")
 ck('Forgedgatepassesnotphysicalbypass',all(shadow.execute('select count(*) from '+v).fetchone()[0]==0 for v in ['training_ready_2e','training_ready_3e']))
 shadow.close()
 # Every protected source/historyinput from the previous manifest plus the
 # entire sealedv0.4payload must still match its recordedfingerprint.
 protection={}
 merged=R/'循环稳定性数据库_v0.3_合并版_20261017'
 for row in read(merged/'原始文件与父版本保护.json')+read(P/'本轮读取原件指纹.json')+read(merged/'merge_manifest.json')['outputs']+pm['outputs']:
  path=Path(row['path']);path=path if path.is_absolute() else R/path
  if str(path) in protection:ck('Consistent protection digest:'+str(path),protection[str(path)]==row['sha256'])
  protection[str(path)]=row['sha256']
 protection[str(P/'merge_manifest.json')]=sha(P/'merge_manifest.json')
 for path,digest in protection.items():ck('Protectedfile:'+path,Path(path).is_file() and sha(Path(path))==digest)
 timings=[]
 for _ in range(10):
  start=time.perf_counter();db.fetch('review_3e_all');timings.append(1000*(time.perf_counter()-start))
 stats={'version':'v0.5','structured_records':191,'new_own_label_candidates':35,'new_candidate_papers':c.execute("select count(distinct identity_key) from model_endpoints where endpoint_id like 'candidate:V05:%'").fetchone()[0],'numeric_N_and_retention':c.execute('select count(*) from model_feature_cache where cycle_count is not null and retention_pct is not null').fetchone()[0],'strict_2e':0,'strict_3e':0,'3E_priority':53,'3E_priority_BET':41,'3E_priority_reference':50,'all_3E_typed':90,'bounded_new_paper_reviews':81,'isolated_native_claims':495,'claim_adjudications':146,'unadjudicated_native_claims':349,'preparation_checks':6876,'relevant_profile_records':168,'relevant_profile_outcomes':[dict(x) for x in c.execute('select preparation_gate_status,count(*) as records from v05_relevant_admission group by preparation_gate_status')],'other_system_records':23,'publication_metadata_changes':c.execute('select count(*) from endpoint_metadata_changes').fetchone()[0],'protected_files':len(protection),'research_fit_calls':0,'all_literature_admitted':False,'full_corpus_terminal_source_review_complete':False,'90row_query_ms_same_process':{'median':sorted(timings)[5],'max':max(timings)}}
 if args.seal:
  for profile,v in ds.items():export(profile,v.rows)
  for t in ['paper_source_reviews','native_claim_adjudications','bibliography_reviews','endpoint_metadata_changes','record_admission_checks','record_gate_outcomes','review_search_audit','extraction_issues','admission_reviews']:export(t,[dict(x) for x in c.execute('select * from '+t)])
  concise=[]
  for r in c.execute('select endpoint_id,identity_key,sample_name,system,method,source_year from model_feature_cache order by endpoint_id'):
   profile='canonical_3e' if r['system']=='3E' else 'canonical_2e' if r['system']=='2E_symmetric' else None
   gates=[dict(x) for x in c.execute("select criterion,status,reason from record_admission_checks where endpoint_id=? and profile=? and status in ('fail','unresolved')",(r['endpoint_id'],profile))] if profile else []
   concise.append({**dict(r),'profile':profile,'disposition':'outside_strict_system_profiles' if not profile else c.execute('select status from record_gate_outcomes where endpoint_id=? and profile=?',(r['endpoint_id'],profile)).fetchone()[0],'failed':enc([x['criterion'] for x in gates if x['status']=='fail']),'unresolved':enc([x['criterion'] for x in gates if x['status']=='unresolved'])})
  export('逐条准入缺口',concise);dump(O/'统计与质量.json',stats)
  dump(O/'核验报告.json',{'technical_checks_passed':True,'checks_count':len(checks),'checks':checks,'scientific_admission_passed':False,'research_fit_calls':0})
  dump(O/'原始文件与父版本保护.json',[{'path':str(Path(path).relative_to(R)) if Path(path).is_relative_to(R) else path,'sha256':digest} for path,digest in protection.items()])
  dump(O/'dataset_snapshots.json',{k:{'rows':len(v.rows),'source_groups':len({x['source_group'] for x in v.rows}),'fingerprint':v.fingerprint(),'training_authorized':False} for k,v in ds.items()})
  (O/'schema.sql').write_text('\n\n'.join(row[0]+';' for row in c.execute('select sql from sqlite_master where sql is not null order by type,name')),encoding='utf-8')
  dump(O/'merge_manifest.json',{'schema':'record-admission-review-v1','stage':'bounded_source_review_and_explicit_gate_audit','parent_database_sha256':pm['database_sha256'],'database_sha256':sha(O/'cycling_v0_5.sqlite'),'ready_for_review':True,'ready_for_research_training':False,'scientific_training_admission':False,'remaining_work':'Current-mass basis, cycle baseline, field binding, source independence and source/figure/SI terminal reviews remain. Some records fail immutable scope/year/horizon conditions.','stats':stats,'outputs':[{'path':f.relative_to(R).as_posix(),'sha256':sha(f),'bytes':f.stat().st_size} for f in sorted(O.rglob('*')) if f.is_file() and f.name!='merge_manifest.json' and '__pycache__' not in f.parts]})
 else:
  for row in read(O/'merge_manifest.json')['outputs']:ck('Sealedpayload:'+row['path'],sha(R/row['path'])==row['sha256'])
 print(enc({'verified':True,'checks':len(checks),'stats':stats,'sealed':args.seal}));p.close();db.close()
if __name__=='__main__':main()
