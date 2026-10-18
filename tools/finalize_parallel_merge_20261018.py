"""Finalize this task's new merge with source groups, evidence indexes and no-fit QA."""
from pathlib import Path
import csv,datetime,hashlib,json,sqlite3,subprocess,sys
R=Path(__file__).resolve().parents[1];O=R/'循环稳定性数据库_v0.3_合并版_20261017'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rr(c,q,args=()):return [dict(x) for x in c.execute(q,args)]
def export(c,t):
 data=rr(c,'select * from '+t);dump(O/'exports'/f'{t}.json',data)
 with (O/'exports'/f'{t}.csv').open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=[x[0] for x in c.execute('select * from '+t+' limit 0').description]);w.writeheader();w.writerows(data)
def main():
 if (O/'最终进度.json').exists():raise RuntimeError('Finalized release exists; do not overwrite. Use verify_parallel_merge_20261018.py.')
 c=sqlite3.connect(O/'cycling_v0_3_merged.sqlite');c.row_factory=sqlite3.Row;c.execute('pragma foreign_keys=ON')
 contract=read(O/'merge_contract.json');contract.update({'physical_core_inputs':['cycle_count','current_density_A_g','electrolyte','concentration_value','voltage_lower_V','voltage_upper_V','BET_m2_g'],'optional_input':'total_pore_volume_cm3_g','canonical_current_basis':'two_electrode_total_active_mass','concentration_unit':'mol/L','three_electrode_model_contract_status':'requires_separate_record_review_and_contract','proposal_training_view':'proposal_training_ready_r4','public_training_view':'training_ready','legacy_metadata_policy':'metadata table retained verbatim as history; merge_contract table is current release contract'})
 for k,v in contract.items():c.execute('insert or replace into merge_contract values (?,?)',(k,json.dumps(v,ensure_ascii=False)))
 c.execute('CREATE TABLE IF NOT EXISTS unified_source_groups(identity_key TEXT PRIMARY KEY REFERENCES literature_registry,group_id TEXT NOT NULL,review_status TEXT NOT NULL,basis_json TEXT NOT NULL)')
 for row in rr(c,'select * from literature_registry'):
  papers=rr(c,"select p.paper_id,p.study_group,g.group_id,g.review_status from papers p left join modeling_effective_inputs e on e.paper_id=p.paper_id left join validation_group_assignments g on e.record_id=g.record_id where lower(p.doi)=?",(row['doi'],)) if row['doi'] else []
  if not papers:
   obs=rr(c,"select source_json from literature_observations where identity_key=? and batch='archived_126'",(row['identity_key'],));papers=[json.loads(x['source_json']) for x in obs]
  groups={x.get('group_id') or x.get('study_group') for x in papers};groups.discard(None)
  if len(groups)>1:raise RuntimeError('Conflicting inherited groups: '+row['identity_key'])
  gid=next(iter(groups)) if groups else row['identity_key']
  status='inherits_existing_group_and_review_limits' if groups else 'provisional_identity_group_not_independence_clearance'
  c.execute('insert or replace into unified_source_groups values (?,?,?,?)',(row['identity_key'],gid,status,json.dumps(papers,ensure_ascii=False)))
 # The previously empty baseline_json cells remain intact; add a searchable composite reference.
 for x in rr(c,'select * from current_baseline_evidence'):
  reviews=json.loads(x['review_evidence_json']);reviews=reviews.get('review_events',[]) if isinstance(reviews,dict) else reviews;domain=rr(c,"select * from domain_reviews_r4 where record_id=? and topic in ('normalization_reference','numeric_label')",(x['record_id'],))
  status=x['status']
  if any(json.loads(v['value_json']) is not None for v in domain):status='reported_reference_evidence_indexed_no_cycle_inferred'
  c.execute('update current_baseline_evidence set review_evidence_json=?,status=? where record_id=?',(json.dumps({'review_events':reviews,'domain_reviews_r4':domain},ensure_ascii=False),status,x['record_id']))
 for x in rr(c,'select * from profile_blocker_dispositions'):
  profile=rr(c,'select * from profile_admissions_r4 where profile=? and record_id=?',(x['profile'],x['record_id']))
  domain=rr(c,'select * from domain_reviews_r4 where record_id=?',(x['record_id'],))
  basis=rr(c,'select * from mass_definition_audits where record_id=?',(x['record_id'],))
  c.execute('update profile_blocker_dispositions set evidence_json=? where profile=? and record_id=? and code=?',(json.dumps({'strict_blocker':json.loads(x['evidence_json']).get('strict_blocker',json.loads(x['evidence_json'])),'proposal_qualification':profile,'domain_reviews':domain,'current_basis_audits':basis},ensure_ascii=False),x['profile'],x['record_id'],x['code']))
 c.executescript("""CREATE TABLE IF NOT EXISTS literature_availability(identity_key TEXT PRIMARY KEY REFERENCES literature_registry,repository_main_files_json TEXT,declared_external_files_json TEXT,status TEXT,admission_status TEXT CHECK(admission_status='not_changed_by_availability'));
 CREATE TABLE IF NOT EXISTS candidate_review_holds(observation_id INTEGER PRIMARY KEY REFERENCES literature_observations,identity_key TEXT REFERENCES literature_registry,batch TEXT,issues_json TEXT,status TEXT CHECK(status='staged_no_admission'));""")
 for entry in rr(c,'select * from literature_registry'):
  local=set();external=set()
  for ob in rr(c,'select * from literature_observations where identity_key=?',(entry['identity_key'],)):
   x=json.loads(ob['source_json']);paths=[]
   paths+=x.get('complete_main_files',[])
   paths+=[x.get(k) for k in ['main_path','repository_pdf','repository_source','source_path']]
   if isinstance(x.get('fulltext'),dict):paths.append(x['fulltext'].get('path'))
   for loc in x.get('portable_source_locations',[]):
    if loc.get('kind')=='repository_file':paths.append(loc.get('path'))
   for name in paths:
    if not name:continue
    path=Path(name);path=path if path.is_absolute() else R/path
    if not path.is_file():continue
    if R in path.resolve().parents:local.add(path.resolve().relative_to(R).as_posix())
    else:external.add(str(path))
   if ob['batch']!='archived_126':
    gaps={k:x[k] for k in ['gaps','audit_notes','review_note','mass_basis_and_window_review','scientific_status','scope_flags','classification','admission_status','baseline_definition_status','cycle_voltage_status','experimental_data_status'] if k in x}
    if gaps:c.execute('insert or replace into candidate_review_holds values (?,?,?,?,?)',(ob['observation_id'],ob['identity_key'],ob['batch'],json.dumps(gaps,ensure_ascii=False),'staged_no_admission'))
  c.execute('insert or replace into literature_availability values (?,?,?,?,?)',(entry['identity_key'],json.dumps(sorted(local),ensure_ascii=False),json.dumps(sorted(external),ensure_ascii=False),'repository_file_available' if local else 'external_file_only' if external else 'complete_main_not_located_in_this_index','not_changed_by_availability'))
 c.commit()
 for t in ['current_baseline_evidence','profile_blocker_dispositions','unified_source_groups','literature_availability','candidate_review_holds']:export(c,t)
 (O/'schema.sql').write_text('\n\n'.join(x[0]+';' for x in c.execute('select sql from sqlite_master where sql is not null order by type,name')),encoding='utf-8')
 for p in [O/'merge_contract.json',O/'modeling/model_contract.json']:dump(p,contract)
 groups=rr(c,'select group_id,count(*) as identities from unified_source_groups group by group_id')
 summary=read(O/'合并计数与覆盖.json');summary['source_groups']=len(groups);summary['registry_count_note']='226 indexed identities/documents = 217 classified identities + 2 B20 candidates without classification entry + 7 B50 candidates without classification entry; not 226 eligible target papers.'
 summary['main_file_availability_index']=rr(c,'select status,count(*) as identities from literature_availability group by status')
 summary['registry_without_DOI']=c.execute('select count(*) from literature_registry where doi is null').fetchone()[0]
 summary['core_field_coverage_archived_endpoints']=rr(c,"select count(*) as endpoints,sum(cycle_count is not null) as cycle_count,sum(current_density_A_g is not null) as current_A_g,sum(electrolyte is not null) as electrolyte,sum(concentration_value is not null) as concentration,sum(voltage_lower_V is not null and voltage_upper_V is not null) as voltage_window,sum(BET_m2_g is not null) as BET,sum(total_pore_volume_cm3_g is not null) as optional_pore from modeling_effective_inputs")[0]
 summary['3E_candidate_missingness']=rr(c,'select count(*) as endpoints,sum(reported_current_A_g is not null) as reported_A_g,sum(linked_record_id is not null) as linked_existing from staged_cycling_evidence')[0]
 summary['baseline_empty_cells_indexed_for_R4_proposals']=rr(c,"select distinct b.record_id,b.status from current_baseline_evidence b join profile_admissions_r4 p using(record_id) where p.eligible=1 and b.legacy_baseline_json is null")
 dump(O/'合并计数与覆盖.json',summary);c.close()
 print(json.dumps({'registry':summary['registry_identities'],'groups':len(groups),'baseline_index':summary['baseline_empty_cells_indexed_for_R4_proposals']},ensure_ascii=False))
if __name__=='__main__':main()
