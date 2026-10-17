"""Verify all historical protections and deliver the all-data utilization/input decision."""
from pathlib import Path
import sqlite3,json,hashlib,csv,sys,ast,subprocess,io,os,contextlib
sys.stdout.reconfigure(encoding='utf-8')
ROOT=Path(__file__).resolve().parent;PARENT=ROOT.parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def js(v):return json.dumps(v,ensure_ascii=False)
def save(name,v):(ROOT/name).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def write(name,text):(ROOT/name).write_text(text,encoding='utf-8')
def connect(p):
 c=sqlite3.connect(p.as_uri()+'?mode=ro',uri=True);c.row_factory=sqlite3.Row;return c
def rows(c,t):return [dict(x) for x in c.execute('select * from '+t)]
def tier(rs):return {'endpoints':len(rs),'materials_provisional':len({x['material_id'] for x in rs}),'papers':len({x['paper_id'] for x in rs})}
def main():
 # Bring the newly introduced routing table into alignment with this round's material flag.
 c=sqlite3.connect(ROOT/'cycling_v0_3r2.sqlite');c.row_factory=sqlite3.Row
 with c:
  old=c.execute("select track from utilization_routes where record_id='R112_CY01'").fetchone()[0]
  if old!='material_scope_or_composite_hold':
   why='Allocate using the final shared-product Si review flag, not the pre-increment cached row.'
   c.execute('insert into revision_changes(table_name,row_key,field_name,old_json,new_json,rationale) values (?,?,?,?,?,?)',('utilization_routes','R112_CY01','track',js(old),js('material_scope_or_composite_hold'),why))
   c.execute("update utilization_routes set track='material_scope_or_composite_hold',reason=? where record_id='R112_CY01'",(why,))
 c.close()
 contract=json.loads((ROOT/'prediction_input_contract.json').read_text(encoding='utf-8'))
 contract['required_physical_inputs'][1]['canonical_mass_basis']='two_electrode_total_active_mass'
 contract['current_unit_policy']='Normalize I/(m_positive+m_negative). A reported I/m_single is converted only when its electrode-specific denominator and both active masses are directly established; otherwise remain blocked. Never derive current basis from a capacitance equation.'
 save('prediction_input_contract.json',contract)
 template=json.loads((ROOT/'预测输入填写模板.json').read_text(encoding='utf-8'))
 template['evidence_metadata'].update(positive_active_mass_g=None,negative_active_mass_g=None,pore_volume_kind=None)
 save('预测输入填写模板.json',template)
 cfg=json.loads((ROOT/'modeling/model_contract.json').read_text(encoding='utf-8'))
 cfg['canonical_current_mass_basis']='two_electrode_total_active_mass'
 save('modeling/model_contract.json',cfg)
 c=connect(ROOT/'cycling_v0_3r2.sqlite');b=connect(PARENT/'cycling_v0_3.sqlite');checks={}
 protected=json.loads((ROOT/'protected_fingerprints.json').read_text(encoding='utf-8'))['files']
 protected.update(json.loads((PARENT/'baseline_fingerprints.json').read_text(encoding='utf-8'))['protected_files'])
 external_manifest=PARENT.parent/'同体系文献补充_第二批_20261017/merge_manifest.json'
 external_current=json.loads(external_manifest.read_text(encoding='utf-8'))
 mutable_external=str(external_manifest)
 reference_changes=[{'path':p,'before_sha256':h,'current_sha256':sha(p)} for p,h in protected.items() if sha(p)!=h]
 checks['all_immutable_parent_and_original_source_files_unchanged']=all(sha(p)==h for p,h in protected.items() if p!=mutable_external)
 checks['external_manifest_update_is_isolated']=all(x['path']==mutable_external for x in reference_changes)
 checks['external_manifest_current_list_hashes_valid']=all(sha(x['path'])==x['sha256'] for x in external_current['outputs'])
 save('外部文献续作状态记录.json',{'initial_complete_receipt':json.loads((ROOT/'completed_literature_receipt.json').read_text(encoding='utf-8')),'current_manifest_sha256':sha(external_manifest),'current_ready_for_merge':external_current['ready_for_merge'],'current_continuation_status':external_current.get('continuation_status'),'reference_changes':reference_changes,'previously_referenced_payloads_unchanged':checks['all_immutable_parent_and_original_source_files_unchanged'],'merge_performed':False,'rule':'Only prior completed payloads with unchanged fingerprints are referenced; no ongoing additions read as verified evidence.'})
 checks['integrity']=c.execute('pragma integrity_check').fetchone()[0]=='ok'
 checks['foreign_keys']=not c.execute('pragma foreign_key_check').fetchall()
 for table in ['raw_records','field_evidence','papers','source_files','ingestion_sources','materials','cycling_endpoints','source_relationships','validation_links','issue_resolutions','endpoint_protocol_overrides']:
  checks[table+'_preserved']=rows(c,table)==rows(b,table)
 for table,key in [('review_events','review_id'),('revision_changes','change_id'),('material_observations','observation_id'),('issues','issue_id')]:
  cur={x[key]:x for x in rows(c,table)};checks['parent_'+table+'_history_preserved']=all(cur[x[key]]==x for x in rows(b,table))
 deltas=[]
 for table,key in [('admissions','record_id'),('endpoint_features','record_id'),('cycling_tests','cycle_test_id')]:
  before={x[key]:x for x in rows(b,table)};after={x[key]:x for x in rows(c,table)}
  for k,old in before.items():
   for field,value in old.items():
    if value==after[k][field]:continue
    chain=[x for x in rows(c,'revision_changes') if x['change_id']>160 and x['table_name']==table and x['row_key']==k and x['field_name']==field]
    cur=value
    for change in chain:assert json.loads(change['old_json'])==cur;cur=json.loads(change['new_json']);assert change['rationale']
    assert cur==after[k][field] and chain,(table,k,field)
    deltas.append({'table':table,'row_key':k,'field':field,'old':value,'new':cur,'change_ids':[x['change_id'] for x in chain]})
 checks['all_current_value_changes_have_contiguous_history']=True
 inventory=json.loads((ROOT/'source_inventory_all137.json').read_text(encoding='utf-8'))
 checks['all_137_sources_have_text_and_hashes']=len(inventory)==137 and all(x.get('extraction_path') and sha(x['path'])==x['sha256'] and sha(x['extraction_path'])==x['extraction_sha256'] for x in inventory)
 checks['all_126_papers_have_declared_use']=c.execute('select count(*) from paper_utilization').fetchone()[0]==126
 checks['all_89_endpoints_have_exactly_one_route']=c.execute('select count(*) from utilization_routes').fetchone()[0]==89
 checks['no_staged_record_admitted']=c.execute('select count(*) from staged_recovery_endpoints where eligible<>0').fetchone()[0]==0
 checks['official_endpoint_count_unchanged']=c.execute('select count(*) from cycling_endpoints').fetchone()[0]==89
 checks['all_raw_targets_preserved']=rows(c,'raw_records')==rows(b,'raw_records') and rows(c,'cycling_endpoints')==rows(b,'cycling_endpoints')
 checks['R117_only_direct_mass_clarification']=set(x[0] for x in c.execute('select record_id from admissions where mass_basis_checked=1'))=={'R117_CY01','R117_CY02'}
 checks['R117_missing_targets_not_filled']=all(c.execute('select retention_pct from cycling_endpoints where record_id=?',(rid,)).fetchone()[0] is None for rid in ['R117_CY01','R117_CY02'])
 checks['micropore_not_inserted_as_total']=c.execute("select total_pore_volume_cm3_g from endpoint_features where record_id='R085_CY01'").fetchone()[0] is None
 checks['IG_ID_stored_separately']=c.execute("select count(*) from material_observations where property_name='Raman_IG_ID'").fetchone()[0]==2
 checks['all_review_source_hashes_match']=all(sha(x['source_path'])==x['source_sha256'] for x in rows(c,'review_events'))
 checks['no_current_admission']=c.execute('select count(*) from training_ready').fetchone()[0]==c.execute('select count(*) from admissions where eligible=1').fetchone()[0]==0
 core=[x['name'] for x in contract['required_physical_inputs']]
 checks['exact_seven_core_plus_one_optional']=len(core)==7 and len(contract['optional_physical_inputs'])==1 and core==['cycle_count','current_density_A_g','electrolyte','concentration_value','voltage_lower_V','voltage_upper_V','BET_m2_g']
 checks['concentration_unit_excluded_from_predictors']=cfg['categorical_features']==['electrolyte'] and all('concentration_unit' not in v for v in cfg['feature_sets'].values())
 checks['BET_core_required']=cfg['primary_required_material_features']==['BET_m2_g']
 checks['no_research_training_authorized']=cfg['research_training_authorized']==False and not (ROOT/'modeling/research_runs').exists()
 input_checks=json.loads((ROOT/'modeling/input_contract_checks.json').read_text(encoding='utf-8'))
 synthetic=json.loads((ROOT/'modeling/synthetic_interfaces_r2_fixed_inputs/summary.json').read_text(encoding='utf-8'))
 checks['28_input_contract_checks_passed']=input_checks['all_passed'] and len(input_checks['checks'])==28 and not input_checks['fitting_performed']
 checks['16_updated_synthetic_interface_checks_passed']=synthetic['passed'] and synthetic['tests_run']==16 and not synthetic['research_training_performed']
 for p in ROOT.rglob('*.py'):ast.parse(p.read_text(encoding='utf-8'))
 checks['python_syntax']=True
 py=PARENT.parent/'循环稳定性数据库_v0.2_20261017/.venv/Scripts/python.exe'
 pre=json.loads(subprocess.run([str(py),'-B',str(ROOT/'modeling/train_grouped.py')],capture_output=True,text=True,encoding='utf-8',check=True).stdout)
 checks['actual_preflight_no_research_fitting']=not pre['training_performed'] and pre['approved_rows']==0
 save('modeling/preflight_result_r2.json',pre)
 allrows=rows(c,'endpoint_effective_review')
 snapshot=ROOT/'parent_endpoint_snapshot.json'
 if not snapshot.exists():save('parent_endpoint_snapshot.json',json.loads((ROOT/'all_current_endpoints.json').read_text(encoding='utf-8')))
 save('all_current_endpoints.json',allrows)
 paired={}
 for field in core+['total_pore_volume_cm3_g','N_at_pct','O_at_pct','mass_loading_mg_cm2']:
  rs=[r for r in allrows if r[field] is not None];paired[field]=tier(rs)
 primary=rows(c,'primary_screening_candidates');ids={r['record_id'] for r in primary}
 candidate_features=[r for r in allrows if r['record_id'] in ids and all(r[x] is not None for x in core)]
 report={'checks':checks,'all_passed':all(checks.values()),'protected_files_checked':len(protected),'counts':{t:c.execute('select count(*) from '+t).fetchone()[0] for t in ['papers','source_files','materials','cycling_tests','cycling_endpoints','staged_recovery_endpoints','review_events','revision_changes','material_observations','issues','training_ready']},'utilization_tracks':[dict(x) for x in c.execute('select track,count(*) endpoints from utilization_routes group by track')],'admission_outcomes':[dict(x) for x in c.execute('select status,count(*) endpoints from admissions group by status')],'field_nonnull_pairing_not_verified_training_coverage':paired,'seven_core_nonnull_primary_candidates_not_admitted':tier(candidate_features),'same_cohort_optional_pore_present':tier([r for r in candidate_features if r['total_pore_volume_cm3_g'] is not None]),'primary_screening_not_admitted':tier(primary),'source_triage':{'papers':126,'files':137,'search_hits':5539,'complete_field_audit_claimed':False},'new_targeted_record_reviews':len({r['record_id'] for r in c.execute('select distinct record_id from review_events where review_id>154')}),'research_training_performed':False,'software_synthetic_fitting_only':True,'database_sha256':sha(ROOT/'cycling_v0_3r2.sqlite')}
 save('核验与字段覆盖_r2.json',report);save('版本字段差异_r2.json',deltas)
 for table in ['paper_utilization','utilization_routes','endpoint_effective_review','admissions','material_observations','review_events','revision_changes','record_blockers','staged_recovery_endpoints','issues_effective']:
  data=rows(c,table);save('exports/'+table+'.json',data)
  if data:
   with (ROOT/'exports'/f'{table}.csv').open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
 save('本轮新增审查与特征.json',[dict(x) for x in c.execute('select * from review_events where review_id>154')])
 # Finished literature is indexed only as a future-input coverage reference, not merged.
 liter=PARENT.parent/'同体系文献补充_第二批_20261017'
 staged=json.loads((liter/'候选文献审核表.json').read_text(encoding='utf-8'))['records']
 save('已完成文献批次_输入覆盖参考_未合并.json',{'status':'read_only_completed_manifest_reference_not_database_ingestion','records':[{'temporary_id':x['candidate_id'],'doi':x['doi_normalized'],'domain':x['domain'],'fulltext_status':x['fulltext']['status'],'measurements_as_reviewed_by_completed_task':x['measurements'],'pre_cycle_characterization_as_reviewed_by_completed_task':x['pre_cycle_characterization'],'gaps':x['gaps'],'eligible':False,'formal_database_id_assigned':False} for x in staged],'formal_database_paper_count_increment':0})
 observations=rows(c,'material_observations')
 save('材料特征全量登记.json',{'observations':observations,'interpretation':'112 material observations, with scope/method/unit/stage retained. Repeated endpoints do not create independent materials. Parent pending statuses remain pending.','required_features':core,'candidate_feature_states':[dict(x) for x in c.execute('select property_name,unit,method,stage,provenance_status,count(*) observations,count(distinct material_id) materials from material_observations group by property_name,unit,method,stage,provenance_status')]})
 # Real read-only notebook outputs, captured from executed SQL cells.
 codecells=["from pathlib import Path\nimport sqlite3,json\nr=Path.cwd()\nc=sqlite3.connect((r/'cycling_v0_3r2.sqlite').as_uri()+'?mode=ro',uri=True)\nc.row_factory=sqlite3.Row\nprint(c.execute('pragma integrity_check').fetchone()[0])", "print(json.dumps([dict(x) for x in c.execute('select track,count(*) endpoints from utilization_routes group by track')],ensure_ascii=False,indent=2))", "print(json.dumps([dict(x) for x in c.execute(\"select record_id,mass_basis_checked,eligible from admissions where mass_basis_checked=1\")],ensure_ascii=False,indent=2))\nprint('approved',c.execute('select count(*) from training_ready').fetchone()[0])", "print(json.dumps([dict(x) for x in c.execute('select candidate_id,paper_id,system,metric_kind,cycle_count,retention_pct,eligible from staged_recovery_endpoints')],ensure_ascii=False,indent=2))\nc.close()"]
 cells=[{'cell_type':'markdown','metadata':{},'source':['# 第二轮：全部数据用途与输入定稿只读复核\n从本目录打开。SQL均mode=ro，输出为本轮实际执行结果；不含研究训练。']}];ns={};cwd=os.getcwd();os.chdir(ROOT)
 try:
  for n,code in enumerate(codecells,1):
   o=io.StringIO()
   with contextlib.redirect_stdout(o):exec(code,ns)
   cells.append({'cell_type':'code','metadata':{},'execution_count':n,'source':code.splitlines(True),'outputs':[{'output_type':'stream','name':'stdout','text':o.getvalue().splitlines(True)}]})
 finally:os.chdir(cwd)
 save('全量利用与输入复核.ipynb',{'nbformat':4,'nbformat_minor':5,'metadata':{'kernelspec':{'name':'python3','language':'python','display_name':'Python 3'}},'cells':cells})
 (ROOT/'schema_r2.sql').write_text('\n'.join(x[0]+';' for x in c.execute('select sql from sqlite_master where sql is not null order by type,name')),encoding='utf-8')
 assert report['all_passed'],[k for k,v in checks.items() if not v]
 print(json.dumps({'all_passed':True,'data_checks':len(checks),'input_checks':28,'synthetic_interface_checks':16,'counts':report['counts'],'field_pairing':paired,'protected_files':len(protected)},ensure_ascii=False,indent=2))
 return report
if __name__=='__main__':main()
