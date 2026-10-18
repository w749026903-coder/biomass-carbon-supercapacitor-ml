"""Evidence-preserving local integration. No downloads, source edits or model fitting.
Run once to a new output directory; never overwrites a release. Python stdlib only.
"""
from pathlib import Path
import collections,csv,datetime,hashlib,json,re,sqlite3,unicodedata
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'循环稳定性数据库_v0.3_合并版_20261017'
A=ROOT/'循环稳定性数据库_v0.3_数据库优化_20261017'
B=ROOT/'同体系文献补充_第二批_20261017'
R4=A/'第四轮_专业复核与训练数据_20261017'
TE=ROOT/'三电极端点扩充_20261018'
U=ROOT/'用户补充文献核验_20261018'
BASE='35d4bbf895501ec306ea215b40f865cc5d1da4e7959173d73e279dd3eaaa22fa'
CONTRACT='63db1238c429d6a26b2467e529e9ebc589e70487e1def3d5108803cbc5e3ade5'
STAMP=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(timespec='seconds')
def js(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def enc(x):return json.dumps(x,ensure_ascii=False,sort_keys=True)
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def rel(p):
 try:return p.relative_to(ROOT).as_posix()
 except ValueError:return str(p)
def write(name,x):
 p=OUT/name;p.parent.mkdir(parents=True,exist_ok=True)
 p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def ro(p):
 c=sqlite3.connect(p.resolve().as_uri()+'?mode=ro',uri=True);c.row_factory=sqlite3.Row;return c
def rows(c,q,args=()):return [dict(x) for x in c.execute(q,args)]
def doi(v):return re.sub(r'^https?://(?:dx\.)?doi\.org/','',str(v or '').strip().lower()).removeprefix('doi:').strip()
def norm(v):return ''.join(x for x in unicodedata.normalize('NFKC',str(v or '')).casefold().replace('−','-') if x.isalnum())
def resolve(v,m):
 p=Path(v)
 return p if p.is_absolute() else ROOT/p if (ROOT/p).exists() else m.parent/p
MANIFESTS=[A/'merge_manifest.json',A/'第二轮_全量利用与输入定稿_20261017/merge_manifest.json',A/'第三轮_逐条准入闭环_20261017/merge_manifest.json',R4/'merge_manifest.json',A/'数据分层只读审计_20261017/audit_manifest.json',B/'merge_manifest.json',U/'merge_manifest.json',TE/'merge_manifest.json']
def main():
 if OUT.exists():raise RuntimeError('Release already exists; verify it instead of overwriting: '+str(OUT))
 checks=[];protected={};inventory=[];historical_manifest_updates=[]
 def check(name,ok,detail=None):
  checks.append({'name':name,'passed':bool(ok),'detail':detail})
  if not ok:raise RuntimeError(name+': '+str(detail))
 def protect(p,expected,kind):
  check('file_hash:'+rel(p),p.is_file() and sha(p)==expected,kind)
  if str(p) in protected:check('consistent_expected_hash:'+rel(p),protected[str(p)]==expected)
  protected[str(p)]=expected
 for m in MANIFESTS:
  d=js(m);protect(m,sha(m),'input_manifest')
  if d.get('task_role') in ('database','literature'):
   check('manifest_ready:'+rel(m),d.get('ready_for_merge') is True)
  if 'baseline_database_sha256' in d:check('common_v02:'+rel(m),d['baseline_database_sha256']==BASE)
  if 'baseline_model_contract_sha256' in d:check('common_contract:'+rel(m),d['baseline_model_contract_sha256']==CONTRACT)
  for x in d.get('outputs',d.get('artifacts',[])):
   p=resolve(x['path'],m).resolve();check('artifact_inside_project:'+rel(p),ROOT in p.parents)
   protect(p,x['sha256'],'manifest_output')
   inventory.append({'manifest':rel(m),'path':rel(p),'sha256':x['sha256'],'role':x.get('role','review_artifact')})
 protect(ROOT/'循环稳定性数据库_v0.2_20261017/cycling_v0_2.sqlite',BASE,'common_baseline')
 protect(ROOT/'循环稳定性数据库_v0.2_20261017/modeling/model_contract.json',CONTRACT,'common_model_contract')
 # Historical fingerprints include v0.1/v0.2 and original literature, not just delivered outputs.
 for p in [A/'baseline_fingerprints.json',A/'第二轮_全量利用与输入定稿_20261017/protected_fingerprints.json',R4/'protected_parent_fingerprints.json']:
  d=js(p);d=d.get('protected_files',d.get('files',{})) if isinstance(d,dict) else d
  entries=[{'path':k,'sha256':v} for k,v in d.items()] if isinstance(d,dict) else d
  for x in entries:
   target=resolve(x['path'],p)
   if target==B/'merge_manifest.json' and sha(target)!=x['sha256']:
    receipt=js(A/'第二轮_全量利用与输入定稿_20261017/外部文献续作状态记录.json')
    check('documented_mutable_literature_manifest',any(v['path']==str(target) and v['before_sha256']==x['sha256'] for v in receipt['reference_changes']))
    historical_manifest_updates.append({'path':rel(target),'historical_sha256':x['sha256'],'current_sha256':sha(target),'evidence':rel(A/'第二轮_全量利用与输入定稿_20261017/外部文献续作状态记录.json'),'decision':'Historical receipt retained; current ready manifest and all its payload hashes checked independently.'})
   else:protect(target,x['sha256'],'historical_protection')
 for x in js(U/'核验记录_26份.json')['records']:protect(Path(x['original_path']),x['sha256'],'user_supplied_original')
 for x in js(TE/'文献类型分类索引.json')['records']:
  for v in x.get('source_versions',[]):
   if v.get('path') and v.get('sha256'):protect(Path(v['path']),v['sha256'],'classified_source_original')
 parent=ro(R4/'cycling_v0_3r4.sqlite')
 for x in rows(parent,'select * from source_files'):protect(Path(x['path']),x['sha256'],'original_source')
 for x in rows(parent,'select distinct source_path,source_sha256 from review_events where source_sha256!=""'):
  protect(Path(x['source_path']),x['source_sha256'],'review_source')
 check('parent_integrity',parent.execute('pragma integrity_check').fetchone()[0]=='ok')
 check('parent_foreign_keys',not parent.execute('pragma foreign_key_check').fetchall())
 OUT.mkdir();(OUT/'exports').mkdir();(OUT/'modeling').mkdir()
 c=sqlite3.connect(OUT/'cycling_v0_3_merged.sqlite');c.row_factory=sqlite3.Row;parent.backup(c);c.execute('pragma foreign_keys=ON')
 # Preserve every inherited table cell. Only the public readiness VIEW changes.
 c.executescript('''
 CREATE TABLE merge_contract(key TEXT PRIMARY KEY,value_json TEXT NOT NULL);
 CREATE TABLE merge_input_files(manifest TEXT,path TEXT,sha256 TEXT,role TEXT,PRIMARY KEY(manifest,path));
 CREATE TABLE literature_registry(identity_key TEXT PRIMARY KEY,doi TEXT UNIQUE,title TEXT,has_archived_paper INTEGER NOT NULL,archive_status TEXT NOT NULL,training_admitted INTEGER NOT NULL CHECK(training_admitted=0));
 CREATE TABLE literature_observations(observation_id INTEGER PRIMARY KEY,identity_key TEXT REFERENCES literature_registry,batch TEXT,local_id TEXT,source_json TEXT NOT NULL);
 CREATE TABLE literature_aliases(batch TEXT,local_id TEXT,identity_key TEXT REFERENCES literature_registry,PRIMARY KEY(batch,local_id,identity_key));
 CREATE TABLE staged_cycling_evidence(endpoint_id TEXT PRIMARY KEY,identity_key TEXT REFERENCES literature_registry,system TEXT,method TEXT,cycle_count INTEGER,retention_pct REAL,retention_relation TEXT,value_kind TEXT,reported_current_A_g REAL,source_file TEXT,source_sha256 TEXT,linked_record_id TEXT REFERENCES cycling_endpoints,link_status TEXT NOT NULL,training_admitted INTEGER NOT NULL CHECK(training_admitted=0),evidence_json TEXT NOT NULL);
 CREATE TABLE merge_conflicts(conflict_id INTEGER PRIMARY KEY,kind TEXT,record_ref TEXT,status TEXT,old_json TEXT,new_json TEXT,evidence_json TEXT,decision TEXT NOT NULL);
 CREATE TABLE current_field_evidence(record_id TEXT REFERENCES cycling_endpoints,field_name TEXT,ledger_value_json TEXT,effective_value_json TEXT,ledger_status TEXT,resolution_status TEXT,review_ids_json TEXT,provenance_json TEXT,PRIMARY KEY(record_id,field_name));
 CREATE TABLE current_baseline_evidence(record_id TEXT PRIMARY KEY REFERENCES cycling_endpoints,legacy_baseline_json TEXT,review_evidence_json TEXT,status TEXT,exact_baseline_cycle INTEGER);
 CREATE TABLE profile_blocker_dispositions(profile TEXT,record_id TEXT,code TEXT,strict_status TEXT,proposal_disposition TEXT,evidence_json TEXT,PRIMARY KEY(profile,record_id,code),FOREIGN KEY(profile,record_id) REFERENCES profile_admissions_r4(profile,record_id));
 CREATE VIEW proposal_training_ready_r4 AS SELECT * FROM training_rows_r4 WHERE profile='literature_core7_exact';
 DROP VIEW training_ready;
 CREATE VIEW training_ready AS SELECT * FROM training_ready_canonical_current;
 CREATE VIEW unified_endpoint_inventory AS
 SELECT 'archived' AS lifecycle,record_id AS endpoint_id,doi,system,method,cycle_count,retention_pct,retention_relation,'record_audit_required' AS scientific_status FROM modeling_effective_inputs
 UNION ALL SELECT 'staged',s.endpoint_id,l.doi,s.system,s.method,s.cycle_count,s.retention_pct,s.retention_relation,'staged_no_admission' FROM staged_cycling_evidence s JOIN literature_registry l USING(identity_key) WHERE s.linked_record_id IS NULL;
 ''')
 contract={'schema':'merged-preparation-v1','merged_at':STAMP,'directory_date_is_original_plan_date':True,'database_file':'cycling_v0_3_merged.sqlite','target':'capacitance_retention_pct_at_specified_cycles_and_conditions','literature_search_priority':'3E','strict_model_scope':'2E_symmetric_GCD_canonical_current','public_training_view':'training_ready','reported_protocol_proposals':['literature_core7_exact','literature_residue_sensitivity','literature_approx_sensitivity'],'reported_protocol_semantics':'author_reported_descriptor_not_calibrated_current','reported_protocol_profiles_are_nested':True,'new_literature_lifecycle':'candidate_staging_only','research_training_authorized':False,'research_fit_calls':0,'archive_changes_authorized':False,'field_conflict_policy':'preserve_each_observation_and_provenance_hold_unresolved','current_denominator_policy':'never_infer_from_capacitance_equation','parent_database':rel(R4/'cycling_v0_3r4.sqlite'),'parent_sha256':sha(R4/'cycling_v0_3r4.sqlite'),'baseline_database_sha256':BASE,'baseline_model_contract_sha256':CONTRACT}
 c.executemany('insert into merge_contract values (?,?)',[(k,enc(v)) for k,v in contract.items()]);c.executemany('insert into merge_input_files values (:manifest,:path,:sha256,:role)',inventory)
 def conflict(kind,ref,status,old,new,evidence,decision):c.execute('insert into merge_conflicts(kind,record_ref,status,old_json,new_json,evidence_json,decision) values (?,?,?,?,?,?,?)',(kind,ref,status,enc(old),enc(new),enc(evidence),decision))
 def observe(batch,x,ident,title=None,archived=False,local=None):
  nd=doi(ident);key='doi:'+nd if nd else 'sha256:'+str(x.get('sha256') or x.get('source_sha256') or x.get('main_sha256')) if x.get('sha256') or x.get('source_sha256') or x.get('main_sha256') else 'title:'+norm(title or x.get('title') or x.get('filename'))
  if not nd and x.get('sha256'):
   same_hash=[v['identity_key'] for v in rows(c,"select identity_key,source_json from literature_observations") if x['sha256'] in (json.loads(v['source_json']).get('source_sha256'),json.loads(v['source_json']).get('sha256'),json.loads(v['source_json']).get('main_sha256'))]
   if len(set(same_hash))==1:key=same_hash[0]
  check('identity_nonempty:'+batch,bool(nd or key!='title:'))
  title=title or x.get('title') or x.get('filename') or ''
  old=c.execute('select * from literature_registry where identity_key=?',(key,)).fetchone()
  if old and norm(old['title'])!=norm(title) and title and old['title']:
   conflict('bibliographic_title_variant',key,'retained_both',old['title'],title,{'batch':batch},'Identity joined by explicit normalized DOI only; titles retained in observations; no latest-write replacement.')
  if not old:c.execute('insert into literature_registry values (?,?,?,?,?,0)',(key,nd or None,title,int(archived),'existing_archive_metadata' if archived else 'candidate_or_background_only'))
  elif archived:c.execute("update literature_registry set has_archived_paper=1,archive_status='existing_archive_metadata' where identity_key=?",(key,))
  # Existing public excerpts remain in the source package; keep structured metadata here.
  compact={k:v for k,v in x.items() if k not in ['front','front_excerpt','source_evidence']}
  c.execute('insert into literature_observations(identity_key,batch,local_id,source_json) values (?,?,?,?)',(key,batch,str(local or x.get('id') or x.get('temporary_id') or x.get('candidate_id') or x.get('endpoint_id') or ''),enc(compact)))
  aliases=[str(local or x.get('id') or x.get('temporary_id') or x.get('candidate_id') or x.get('endpoint_id') or '')]+x.get('aliases',[])
  for alias in aliases:
   if alias:c.execute('insert or ignore into literature_aliases values (?,?,?)',(batch,str(alias),key))
  return key
 for x in rows(parent,'select * from papers'):observe('archived_126',x,x['doi'],archived=True,local=x['paper_id'])
 for batch,path,listkey in [('B20',B/'候选文献审核表.json','records'),('B50',B/'定向扩搜40至60篇_20261017/新增50篇_逐篇数据与获取状态.json','records'),('classified_217',TE/'文献类型分类索引.json','records'),('user_pdf_26',U/'核验记录_26份.json','records')]:
  data=js(path);data=data[listkey] if isinstance(data,dict) else data
  for x in data:observe(batch,x,x.get('doi') or x.get('doi_normalized'),archived=False)
 endpoints=rows(parent,'select * from modeling_effective_inputs');staged=js(TE/'三电极端点_53条.json')['rows']
 for x in staged:
  key=observe('three_electrode_53',x,x['doi']);same=[y for y in endpoints if doi(y['doi'])==doi(x['doi']) and norm(y['sample_name'])==norm(x['sample']) and y['cycle_count']==x['cycle_count']]
  exact=[y for y in same if y['system']==x['system'] and y['method']==x['cycle_method'] and y['retention_pct']==x['retention_pct'] and y['retention_relation']==x['retention_relation']]
  link=exact[0]['record_id'] if len(exact)==1 else None
  state='exact_same_reported_endpoint_linked_not_readmitted' if link else 'staged_unmatched_or_ambiguous'
  if same and not link:conflict('endpoint_overlap',x['endpoint_id'],'frozen_for_review',same,x,{'source':x['source_file'],'locator':x['locator']},'Keep both observations. No endpoint overwrite or independent training count.')
  protect(ROOT/x['source_file'],x['source_sha256'],'staged_endpoint_source')
  c.execute('insert into staged_cycling_evidence values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(x['endpoint_id'],key,x['system'],x['cycle_method'],x['cycle_count'],x['retention_pct'],x['retention_relation'],x['value_kind'],x['reported_current_A_g'],x['source_file'],x['source_sha256'],link,state,0,enc(x)))
 # Reconcile the old field ledger through an explicit effective layer. No old cells are overwritten.
 emap={x['record_id']:x for x in endpoints};reconciled=[]
 for x in rows(parent,'select * from field_evidence'):
  projected=x['field_name'] in emap[x['record_id']];legacy=json.loads(x['value_json']);effective=emap[x['record_id']].get(x['field_name']) if projected else legacy;rv=rows(parent,'select * from review_events where record_id=? and field_name=? order by review_id',(x['record_id'],x['field_name']))
  matches=[v for v in rv if json.loads(v['value_json'])==effective and effective is not None and v['source_path'] and v['locator']]
  status='ledger_only_not_projected_in_model_view' if not projected else 'legacy_and_effective_equal' if legacy==effective else 'effective_value_with_matching_review' if matches else 'effective_differs_review_required'
  c.execute('insert into current_field_evidence values (?,?,?,?,?,?,?,?)',(x['record_id'],x['field_name'],x['value_json'],enc(effective),x['status'],status,enc([v['review_id'] for v in matches]),enc({'ledger':x,'matching_reviews':matches})))
  if legacy!=effective:
   reconciled.append({'record_id':x['record_id'],'field':x['field_name'],'status':status,'review_ids':[v['review_id'] for v in matches]})
   conflict('field_ledger_vs_effective',x['record_id']+'::'+x['field_name'],'reconciled_index_only' if matches else 'frozen_for_review',legacy,effective,{'matching_review_ids':[v['review_id'] for v in matches],'ledger_status':x['status']},'Current effective value linked to matching review; old ledger retained; no new admission.' if matches else 'No direct exact-field matching review; retain both and withhold any new clearance.')
 for x in endpoints:
  rv=rows(parent,"select * from review_events where record_id=? and field_name in ('baseline_definition','normalization_reference') order by review_id",(x['record_id'],))
  known=[v for v in rv if json.loads(v['value_json']) is not None]
  c.execute('insert into current_baseline_evidence values (?,?,?,?,NULL)',(x['record_id'],x['baseline_json'],enc(rv),'reported_reference_evidence_indexed_no_cycle_inferred' if known or x['baseline_json'] not in (None,'null','{}') else 'unresolved'))
 for x in rows(parent,'select a.profile,a.record_id,b.*,s.affects_core7 from profile_admissions_r4 a join record_blockers b using(record_id) left join blocker_scopes s using(record_id,code) where a.eligible=1 and b.status="open"'):
  c.execute('insert into profile_blocker_dispositions values (?,?,?,?,?,?)',(x['profile'],x['record_id'],x['code'],x['status'],'not_cleared_by_merge; candidate_profile_qualification_only',enc(x)))
 conflict('profile_contract','training_ready','resolved_by_explicit_merge_contract',{'parent_default':'literature_core7_exact','rows':8},{'merged_default':'canonical_current','rows':0},contract,'Retain all R4 proposal memberships and evidence; canonical current gate is the merged public readiness definition. No research fits.')
 # Inherited cells/constraints/foreign keys and all historical freezes must survive byte-for-byte at row level.
 table_names=[x[0] for x in parent.execute("select name from sqlite_master where type='table' and name not like 'sqlite_%'")]
 for t in table_names:check('all_parent_rows_preserved:'+t,parent.execute('select * from "'+t+'"').fetchall()==c.execute('select * from "'+t+'"').fetchall())
 check('sqlite_integrity',c.execute('pragma integrity_check').fetchone()[0]=='ok');check('foreign_keys',not c.execute('pragma foreign_key_check').fetchall())
 check('strict_readiness_zero',c.execute('select count(*) from training_ready').fetchone()[0]==0)
 check('no_new_admission',c.execute('select sum(training_admitted) from staged_cycling_evidence').fetchone()[0]==0)
 check('source_group_per_paper',not rows(c,'select paper_id from modeling_effective_inputs join validation_group_assignments using(record_id) group by paper_id having count(distinct group_id)>1'))
 check('unique_normalized_DOI',c.execute('select count(doi)=count(distinct doi) from literature_registry').fetchone()[0]==1)
 check('staged_actual_configuration',all(x['system']=='3E' and x['cycle_method']=='GCD' for x in staged))
 # Verify the parent's scalar change chains; composite evidence changes remain preserved and directly inspected above.
 chains=collections.defaultdict(list)
 for x in rows(c,'select * from revision_changes order by change_id'):
  check('reasoned_change:'+str(x['change_id']),bool(x['rationale']) and x['old_json'] is not None and x['new_json'] is not None)
  chains[(x['table_name'],x['row_key'],x['field_name'])].append(x)
 scalar_verified=0;composite=[]
 for (t,key,f),values in chains.items():
  if f=='current_evidence':composite.append({'table':t,'key':key,'field':f,'changes':len(values)});continue
  for prev,nxt in zip(values,values[1:]):check('continuous_change_chain:'+str(nxt['change_id']),json.loads(prev['new_json'])==json.loads(nxt['old_json']))
  info=list(c.execute('pragma table_info("'+t+'")'));pk=[v['name'] for v in info if v['pk']]
  if len(pk)==1 and f in [v['name'] for v in info]:
   result=c.execute('select "'+f+'" from "'+t+'" where "'+pk[0]+'"=?',(key,)).fetchone()
   check('current_value_matches_history:'+t+':'+key+':'+f,result is not None and result[0]==json.loads(values[-1]['new_json']));scalar_verified+=1
 c.commit()
 stats={'archived':{t:c.execute('select count(*) from '+t).fetchone()[0] for t in ['papers','source_files','materials','cycling_tests','cycling_endpoints','review_events','revision_changes','issues','record_blockers']},'registry_identities':c.execute('select count(*) from literature_registry').fetchone()[0],'classified_identities':217,'staged_3E_endpoints':len(staged),'staged_3E_papers':len({doi(x['doi']) for x in staged}),'linked_to_existing_endpoints':c.execute('select count(*) from staged_cycling_evidence where linked_record_id is not null').fetchone()[0],'unified_endpoint_inventory_observations':c.execute('select count(*) from unified_endpoint_inventory').fetchone()[0],'strict_training_ready':c.execute('select count(*) from training_ready').fetchone()[0],'reported_protocol_profiles_nested':rows(c,'select profile,count(*) as endpoints,count(distinct e.paper_id) as papers from profile_admissions_r4 a join modeling_effective_inputs e using(record_id) where a.eligible=1 group by profile'),'field_ledger_differences':len(reconciled),'field_differences_with_exact_review':sum(x['status']=='effective_value_with_matching_review' for x in reconciled),'conflicts_by_status':rows(c,'select kind,status,count(*) as count from merge_conflicts group by kind,status'),'protected_unique_files':len(protected),'manifest_output_entries':len(inventory),'scalar_history_chains_verified':scalar_verified,'composite_evidence_chains_preserved':len(composite),'research_fit_calls':0}
 for name in ['literature_registry','literature_aliases','staged_cycling_evidence','current_field_evidence','current_baseline_evidence','profile_blocker_dispositions','merge_conflicts','unified_endpoint_inventory']:
  rr=rows(c,'select * from '+name)
  with (OUT/'exports'/f'{name}.csv').open('w',encoding='utf-8-sig',newline='') as f:
   writer=csv.DictWriter(f,fieldnames=[d[0] for d in c.execute('select * from '+name+' limit 0').description]);writer.writeheader();writer.writerows(rr)
  write('exports/'+name+'.json',rr)
 write('历史清单版本衔接.json',historical_manifest_updates);write('merge_contract.json',contract);write('合并计数与覆盖.json',stats);write('字段证据衔接.json',reconciled);write('输入文件清单.json',inventory)
 write('原始文件与父版本保护.json',[{'path':rel(Path(p)),'sha256':h} for p,h in protected.items()]);write('变更链核验.json',{'scalar_chains_verified':scalar_verified,'composite_evidence_chains':composite,'all_original_rows_preserved':True})
 (OUT/'schema.sql').write_text('\n\n'.join(x[0]+';' for x in c.execute("select sql from sqlite_master where sql is not null order by type,name")),encoding='utf-8')
 c.close();parent.close()
 # Recheck input hashes AFTER all output construction. No modification/move of external originals.
 for p,h in protected.items():check('protected_after_merge:'+rel(Path(p)),sha(Path(p))==h)
 write('合并核验.json',{'completed_at':STAMP,'all_checks_passed':True,'checks_total':len(checks),'checks':checks,'remaining_scientific_issues_preserved':True,'source_files_moved_or_modified':False,'research_training_performed':False})
 write('modeling/model_contract.json',contract)
 write('merge_manifest.json',{'schema':'unified-scientific-preparation-v1','ready_for_review':True,'merge_complete':True,'ready_for_research_training':False,'created_at':STAMP,'baseline_database_sha256':BASE,'baseline_model_contract_sha256':CONTRACT,'counts':stats,'source_manifests':[{'path':rel(p),'sha256':sha(p)} for p in MANIFESTS],'outputs':[{'path':rel(p),'sha256':sha(p),'bytes':p.stat().st_size} for p in OUT.rglob('*') if p.is_file() and p.name!='merge_manifest.json']})
 print(json.dumps(stats,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
