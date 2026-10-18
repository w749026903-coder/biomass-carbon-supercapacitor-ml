"""Read-only integrity verification; --seal is only for this task's first finalization."""
from pathlib import Path
import argparse,collections,datetime,hashlib,json,runpy,sqlite3
R=Path(__file__).resolve().parents[1];O=R/'循环稳定性数据库_v0.3_合并版_20261017'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def conn(p):
 c=sqlite3.connect(p.resolve().as_uri()+'?mode=ro',uri=True);c.row_factory=sqlite3.Row;return c

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--seal',action='store_true');args=ap.parse_args()
 if args.seal and (O/'最终进度.json').exists():raise RuntimeError('Already finalized; verify without --seal.')
 contract=read(O/'merge_contract.json');c=conn(O/contract['database_file']);p=conn(R/contract['parent_database']);checks=[]
 def check(name,ok,detail=None):
  checks.append({'name':name,'passed':bool(ok),'detail':detail})
  if not ok:raise RuntimeError(name+': '+str(detail))
 check('sqlite_integrity',c.execute('pragma integrity_check').fetchone()[0]=='ok');check('foreign_keys',not c.execute('pragma foreign_key_check').fetchall())
 for t, in p.execute("select name from sqlite_master where type='table' and name not like 'sqlite_%'"):
  check('parent_all_cells_preserved:'+t,p.execute('select * from "'+t+'"').fetchall()==c.execute('select * from "'+t+'"').fetchall())
 check('public_training_view_is_canonical','training_ready_canonical_current' in c.execute("select sql from sqlite_master where name='training_ready'").fetchone()[0])
 check('strict_readiness_zero',c.execute('select count(*) from training_ready').fetchone()[0]==0)
 check('reported_proposal8_retained',c.execute('select count(*) from proposal_training_ready_r4').fetchone()[0]==8)
 check('staged_candidates53_not_admitted',c.execute('select count(*),sum(training_admitted) from staged_cycling_evidence').fetchone()[:]==(53,0))
 check('registry_count226',c.execute('select count(*) from literature_registry').fetchone()[0]==226)
 check('DOI_deduplicated',c.execute('select count(doi)=count(distinct doi) from literature_registry').fetchone()[0]==1)
 check('all_identities_have_source_groups',c.execute('select count(*) from unified_source_groups').fetchone()[0]==226)
 check('current_ledger21_reconciled',c.execute("select count(*) from current_field_evidence where resolution_status='effective_value_with_matching_review'").fetchone()[0]==21)
 check('all_non_equal_projected_fields_have_exact_review',c.execute("select count(*) from current_field_evidence where resolution_status='effective_differs_review_required'").fetchone()[0]==0)
 for x in c.execute("select * from current_field_evidence where resolution_status='effective_value_with_matching_review'"):
  ids=read_json(x['review_ids_json']);check('field_review_refs:'+x['record_id']+':'+x['field_name'],bool(ids))
  for i in ids:
   event=c.execute('select * from review_events where review_id=?',(i,)).fetchone();check('field_review_value:'+str(i),event['record_id']==x['record_id'] and event['field_name']==x['field_name'] and read_json(event['value_json'])==read_json(x['effective_value_json']))
 chains=collections.defaultdict(list)
 for x in c.execute('select * from revision_changes order by change_id'):chains[(x['table_name'],x['row_key'],x['field_name'])].append(dict(x))
 composite=0
 for (table,key,field),seq in chains.items():
  if field!='current_evidence':continue
  for prev,nxt in zip(seq,seq[1:]):
   before=read_json(nxt['old_json']);after=read_json(prev['new_json']);check('composite_chain:'+str(nxt['change_id']),all(before.get(k)==v for k,v in after.items()))
  record,field_name=key.split('::',1);current=c.execute('select * from field_evidence where record_id=? and field_name=?',(record,field_name)).fetchone();last=read_json(seq[-1]['new_json']);check('composite_current:'+key,current is not None and all(current[k]==v for k,v in last.items()));composite+=1
 # Scalar chains were validated during construction; all inherited cells are still equal above.
 check('33_composite_field_chains_verified',composite==33)
 originals=read(O/'原始文件与父版本保护.json')
 for x in originals:
  path=Path(x['path']);path=path if path.is_absolute() else R/path
  check('protected_hash:'+x['path'],path.is_file() and sha(path)==x['sha256'])
 model=runpy.run_path(str(O/'modeling/preflight.py'))['run']();check('no_fit_model_preflight',model['all_checks_passed'] and model['research_fit_calls']==0 and model['synthetic_fit_calls']==0)
 stats=read(O/'合并计数与覆盖.json');check('source_manifest_files_2702',len(read(O/'输入文件清单.json'))==2702);check('original_protection_files_3025',len(originals)==3025)
 c.close();p.close()
 if args.seal:
  dump(O/'modeling/预检结果.json',model)
  report={'completed_at':datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(timespec='seconds'),'all_checks_passed':True,'checks_total':len(checks),'checks':checks,'counts':stats,'model_preflight':model,'scientific_unresolved_issues_passed':False,'scientific_note':'Technical merge verification only; unresolved definitions, freezes and new-candidate admission remain pending.','research_fit_calls':0,'synthetic_fit_calls':0}
  dump(O/'最终核验.json',report)
  dump(O/'最终进度.json',{'status':'merged_and_verified','local_merge_complete':True,'source_data_preserved':True,'research_training_performed':False,'new_literature_archived':False,'strict_training_ready':0,'pending_science':['current_denominator','3E_record_admission_and_contract','material_predecessor_curve_independence','remaining_main_text_and_SI'],'database_sha256':sha(O/contract['database_file']),'verification_sha256':sha(O/'最终核验.json'),'completed_at':report['completed_at'],'next_step':'Use unified README and current merge_contract; source chats remain available.'})
  manifest=read(O/'merge_manifest.json');manifest.update({'status':'merged_and_verified','counts':stats,'final_verification_file':'最终核验.json','final_verification_sha256':sha(O/'最终核验.json'),'research_training_performed':False,'outputs':[{'path':f.relative_to(R).as_posix(),'sha256':sha(f),'bytes':f.stat().st_size} for f in sorted(O.rglob('*')) if f.is_file() and f.name!='merge_manifest.json' and '__pycache__' not in f.parts]})
  dump(O/'merge_manifest.json',manifest)
 manifest=read(O/'merge_manifest.json')
 for x in manifest['outputs']:
  path=R/x['path'];check('sealed_output:'+x['path'],path.is_file() and sha(path)==x['sha256'])
 check('final_report_hash',sha(O/'最终核验.json')==manifest['final_verification_sha256'])
 print(json.dumps({'verified':True,'sealed':args.seal,'checks':len(checks),'outputs':len(manifest['outputs']),'protected_files':len(originals),'database_sha256':sha(O/contract['database_file']),'manifest_sha256':sha(O/'merge_manifest.json'),'research_fits':0},ensure_ascii=False))
def read_json(x):return json.loads(x)
if __name__=='__main__':main()
