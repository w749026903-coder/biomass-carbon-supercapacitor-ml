"""Read-only validation and exports. Behavioral gate tests use an in-memory copy."""
from pathlib import Path
import hashlib,json,sqlite3,sys,ast,csv
sys.stdout.reconfigure(encoding='utf-8')
ROOT=Path(__file__).resolve().parent;BASE=ROOT.parent/'循环稳定性数据库_v0.2_20261017'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(name,v):(ROOT/name).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def connect(p):
 c=sqlite3.connect(p.as_uri()+'?mode=ro',uri=True);c.row_factory=sqlite3.Row;return c
def rows(c,t):return [dict(x) for x in c.execute('select * from '+t)]
def tier(rs):return {'endpoints':len(rs),'provisional_materials':len({r['material_id'] for r in rs}),'papers':len({r['paper_id'] for r in rs}),'study_groups':len({r['study_group'] for r in rs})}
def main():
 c=connect(ROOT/'cycling_v0_3.sqlite');b=connect(BASE/'cycling_v0_2.sqlite');checks={}
 fingerprints=json.loads((ROOT/'baseline_fingerprints.json').read_text(encoding='utf-8'))
 checks['288_protected_files_unchanged']=all(sha(p)==h for p,h in fingerprints['protected_files'].items())
 checks['baseline_contract_hash']=sha(BASE/'cycling_v0_2.sqlite')=='35d4bbf895501ec306ea215b40f865cc5d1da4e7959173d73e279dd3eaaa22fa'
 checks['sqlite_integrity']=c.execute('pragma integrity_check').fetchone()[0]=='ok'
 checks['foreign_keys']=not c.execute('pragma foreign_key_check').fetchall()
 for table in ['raw_records','field_evidence','source_files','ingestion_sources','papers','materials']:
  checks[table+'_unchanged']=rows(c,table)==rows(b,table)
 for table,key in [('review_events','review_id'),('revision_changes','change_id'),('issues','issue_id'),('material_observations','observation_id'),('source_relationships','relationship_id')]:
  current={r[key]:r for r in rows(c,table)}
  checks['all_parent_'+table+'_preserved']=all(current[r[key]]==r for r in rows(b,table))
 changes=rows(c,'revision_changes');old_count=b.execute('select count(*) from revision_changes').fetchone()[0]
 actual_diffs=[]
 for table,key in [('admissions','record_id'),('cycling_endpoints','record_id'),('cycling_tests','cycle_test_id'),('endpoint_features','record_id'),('metadata','key')]:
  before={r[key]:r for r in rows(b,table)};after={r[key]:r for r in rows(c,table)}
  for k,r in before.items():
   for field,v in r.items():
    new=after[k][field]
    if v!=new:
     chain=[x for x in changes[old_count:] if x['table_name']==table and x['row_key']==k and x['field_name']==field]
     previous=v
     for item in chain:
      assert json.loads(item['old_json'])==previous,(table,k,field)
      previous=json.loads(item['new_json']);assert item['rationale']
     assert previous==new and chain,(table,k,field)
     actual_diffs.append({'table':table,'row_key':k,'field':field,'old':v,'new':new,'change_ids':[x['change_id'] for x in chain]})
 checks['all_changed_existing_cells_have_contiguous_reasoned_history']=True
 checks['numeric_targets_and_cycle_counts_preserved']=all((a['record_id'],a['retention_pct'],a['cycle_count'])==(z['record_id'],z['retention_pct'],z['cycle_count']) for a,z in zip(rows(b,'cycling_endpoints'),rows(c,'cycling_endpoints')))
 checks['review_source_hashes_match']=all(sha(r['source_path'])==r['source_sha256'] for r in rows(c,'review_events'))
 checks['sources137_hashes_match']=all(sha(r['path'])==r['sha256'] for r in rows(c,'source_files'))
 checks['old_issue_statuses_preserved']=all(c.execute('select status from issues where issue_id=?',(r['issue_id'],)).fetchone()[0]==r['status'] for r in rows(b,'issues'))
 checks['no_records_admitted']=c.execute('select count(*) from training_ready').fetchone()[0]==c.execute('select count(*) from admissions where eligible=1').fetchone()[0]==0
 checks['no_mass_basis_or_independence_auto_pass']=all(r['mass_basis_checked']==0 and r['independence_checked']==0 for r in rows(c,'admissions'))
 effective=rows(c,'endpoint_effective_review');allrows=rows(c,'endpoint_review')
 e={r['record_id']:r for r in effective};a={r['record_id']:r for r in allrows}
 checks['R107_test_not_invented']=a['R107_CY01']['cycle_test_id']==a['R107_CY02']['cycle_test_id']
 checks['R107_inherited_window_withheld']=e['R107_CY02']['voltage_lower_V'] is None and e['R107_CY02']['voltage_upper_V'] is None and a['R107_CY02']['voltage_upper_V']==1
 checks['R112_axis_erratum_preserves_window']=all(e[r]['voltage_upper_V']==1 and c.execute("select decision from field_review_latest where record_id=? and field_name='voltage_window_consistency'",(r,)).fetchone()[0]=='resolved_by_visual_erratum' for r in ['R112_CY02','R112_CY03'])
 checks['R112_scope_still_frozen']=all(a[r]['admission_status']=='frozen_pending_clarification' and a[r]['Si_residue_review_required']==1 for r in ['R112_CY02','R112_CY03'])
 checks['R112_old_issues_resolved_via_append_only_links']=c.execute("select count(*) from issues_effective where code='batch1_voltage_window_consistency' and status='open' and effective_status='resolved_by_visual_erratum'").fetchone()[0]==2
 checks['R091_recovered_without_unit_rewrite']=a['R091_CY01']['current_density_A_g']==3 and a['R091_CY01']['total_pore_volume_cm3_g'] is None and a['R091_CY01']['pore_unit_review_required']==1
 checks['R033_unequal_mass_scope']=a['R033_CY02']['system']=='2E_same_carbon_mass_unbalanced'
 checks['R087_three_electrode_scope']=a['R087_CY01']['system']=='3E'
 checks['approximate_and_bound_labels_preserved']=all(a[r]['retention_relation']==v for r,v in [('SRC123_CY01','approx'),('SRC125_CY01','approx'),('SRC125_CY02','gt'),('R105_CY01','approx'),('SRC112_CY01','approx')])
 checks['areal_currents_not_converted']=a['R108_CY05']['current_density_mA_cm2']==20 and a['SRC093_CY01']['current_density_mA_cm2']==2 and a['R108_CY05']['current_density_A_g'] is None and a['SRC093_CY01']['current_density_A_g'] is None
 checks['known_secondary_sources_same_group']=c.execute("select p.study_group=q.study_group from source_relationships r join papers p on p.paper_id=r.paper_id join papers q on q.paper_id=r.related_paper_id where r.relationship='reuses_underlying_secondary_dataset'").fetchone()[0]==1
 # Verify new gate behavior, without touching disk or invoking estimators.
 mem=sqlite3.connect(':memory:');c.backup(mem);mem.execute('pragma foreign_keys=ON')
 for rid in ['R093_CY01','R107_CY02']:
  mem.execute("update admissions set status='approved',source_checked=1,material_checked=1,protocol_checked=1,baseline_checked=1,mass_basis_checked=1,independence_checked=1,freeze_cleared=1,eligible=1 where record_id=?",(rid,))
 checks['flags_alone_cannot_bypass_open_blockers']=mem.execute("select count(*) from training_ready where record_id='R093_CY01'").fetchone()[0]==0
 mem.execute("update record_blockers set status='resolved_by_review' where record_id in ('R093_CY01','R107_CY02')")
 checks['inherited_window_still_blocks_after_flags']=mem.execute("select count(*) from training_ready where record_id='R107_CY02'").fetchone()[0]==0
 checks['gate_can_admit_only_in_isolated_hypothetical_fixture']=mem.execute("select count(*) from training_ready where record_id='R093_CY01'").fetchone()[0]==1
 mem.close()
 parent_contract=json.loads((BASE/'modeling/model_contract.json').read_text(encoding='utf-8'));cfg=json.loads((ROOT/'modeling/model_contract.json').read_text(encoding='utf-8'))
 cfg_compare=dict(cfg);cfg_compare['database_file']=parent_contract['database_file']
 checks['model_scientific_contract_unchanged']=cfg_compare==parent_contract
 checks['model_search_spaces_unchanged']=sha(ROOT/'modeling/model_spaces.json')==sha(BASE/'modeling/model_spaces.json')
 sys.path.insert(0,str(ROOT/'modeling'))
 from prepare_dataset import normalized_doi
 dois=[normalized_doi(r['doi']) for r in rows(c,'papers') if r['doi']]
 checks['normalized_doi_unique']=len(dois)==len(set(dois))
 guards=json.loads((ROOT/'modeling/v03_group_guard_checks.json').read_text(encoding='utf-8'))
 checks['five_new_group_guard_checks_passed_without_fitting']=guards['all_passed'] and guards['fitting_performed']==False
 for p in ROOT.rglob('*.py'):ast.parse(p.read_text(encoding='utf-8'))
 checks['python_syntax']=True
 checks['no_research_output_or_venv_created']=not (ROOT/'modeling/runs').exists() and not (ROOT/'.venv').exists()
 # Fields retain original evidence and explicit review states; non-null is not verified.
 fields=cfg['required_conditions']+['retention_pct','retention_relation','system','method','BET_m2_g','total_pore_volume_cm3_g','N_at_pct','O_at_pct','mass_loading_mg_cm2']
 latest={(r['record_id'],r['field_name']):r for r in rows(c,'field_review_latest')}
 original={(r['record_id'],r['field_name']):r for r in rows(c,'field_evidence')}
 coverage=[]
 for r in effective:
  ff={}
  for field in fields:
   rev=latest.get((r['record_id'],field));raw=original.get((r['record_id'],field))
   state=rev['decision'] if rev else ('inherited_candidate_value_unverified' if r[field] is not None else 'not_located_or_not_paired_in_parent_not_proven_absent')
   ff[field]={'current_effective_value':r[field],'parent_level_current_value':a[r['record_id']][field],'review_state':state,'latest_review':rev,'original_import_evidence':raw}
  coverage.append({'record_id':r['record_id'],'paper_id':r['paper_id'],'material_id':r['material_id'],'fields':ff,'admission_status':r['admission_status'],'eligible':r['eligible']})
 primary=rows(c,'primary_screening_candidates');primary_ids={r['record_id'] for r in primary}
 eff_primary=[r for r in effective if r['record_id'] in primary_ids]
 paired=[r for r in eff_primary if all(r[f] is not None for f in cfg['required_conditions'])]
 bet=[r for r in paired if r['BET_m2_g'] is not None];pore=[r for r in bet if r['total_pore_volume_cm3_g'] is not None]
 reviewed_ids={r['record_id'] for r in rows(c,'review_events') if r['review_id']>80}
 decisions=[]
 for r in allrows:
  admission=dict(c.execute('select * from admissions where record_id=?',(r['record_id'],)).fetchone())
  reasons=[]
  if r['system']!='2E_symmetric':reasons.append('system='+r['system'])
  if r['method']!='GCD':reasons.append('method='+r['method'])
  if r['retention_relation']!='eq':reasons.append('label_relation='+r['retention_relation'])
  if r['retention_pct'] is None:reasons.append('target_not_paired')
  if r['conflict']:reasons.append('unresolved_label_conflict')
  if r['cycle_count'] is None or r['cycle_count']<1000:reasons.append('below_current_cycle_screen_or_missing')
  if r['material_scope'] not in ['carbon_candidate','carbon_control']:reasons.append('material_scope='+r['material_scope'])
  if r['Si_residue_review_required']:reasons.append('product_Si_scope_review')
  if r['category'] not in ['A','B']:reasons.append('archive_category='+r['category'])
  decisions.append({'record_id':r['record_id'],'paper_id':r['paper_id'],'material_id':r['material_id'],'study_group':r['study_group'],'review_extent':'v03_source_and_record_review' if r['record_id'] in reviewed_ids else 'inherited_routing_only_no_new_source_clearance','screening_exclusions':reasons,'admission':admission,'blocking_items':[dict(x) for x in c.execute("select * from record_blockers where record_id=? and status='open'",(r['record_id'],))]})
 counts={t:c.execute('select count(*) from '+t).fetchone()[0] for t in ['papers','source_files','materials','cycling_tests','cycling_endpoints','review_events','revision_changes','material_observations','issues','record_blockers','validation_links','training_ready']}
 report={'date':'2026-10-17','checks':checks,'all_passed':all(checks.values()),'counts':counts,'baseline_counts':json.loads((ROOT/'baseline_profile.json').read_text(encoding='utf-8'))['tables'],'coverage':{'all_candidates':tier(allrows),'v03_source_reviewed':tier([r for r in allrows if r['record_id'] in reviewed_ids]),'current_screening_not_admission':tier(primary),'effective_required_fields_paired_not_admission':tier(paired),'plus_BET_paired_not_admission':tier(bet),'plus_BET_pore_paired_not_admission':tier(pore)},'field_nonnull_coverage_not_verified':{f:{'screening_endpoints':len(eff_primary),'nonnull_endpoints':sum(r[f] is not None for r in eff_primary),'explicit_direct_review_endpoints':sum((r['record_id'],f) in latest and latest[(r['record_id'],f)]['decision'].startswith('verified') for r in eff_primary)} for f in fields},'outcomes':[dict(r) for r in c.execute('select status,count(*) endpoints from admissions group by status')],'database_sha256':sha(ROOT/'cycling_v0_3.sqlite'),'research_training_performed':False,'limitations':['35 records received new source review; other 54 remain routed from parent, not newly cleared.','No direct cycling mass denominator or cross-paper independence cleared.','No time-series of experiments exists for temporal drift analysis.','External predecessor full curves and missing SI remain unavailable.','Views distinguish raw inherited protocol from effective reviewed protocol.']}
 save('核验报告_v03.json',report);save('版本字段差异.json',actual_diffs);save('逐记录准入与冻结.json',decisions);save('字段覆盖与出处_v03.json',coverage)
 save('来源与材料关系.json',{'papers':rows(c,'papers'),'materials':rows(c,'materials'),'source_relationships':rows(c,'source_relationships'),'validation_links':rows(c,'validation_links'),'policy':'Same material/curve/source must share a validation group. Unresolved external predecessors remain blocked and must be union-grouped if ingested until resolved.'})
 for t in ['endpoint_review','endpoint_effective_review','admissions','review_events','revision_changes','material_observations','issues','issues_effective','issue_resolutions','source_relationships','record_blockers','endpoint_protocol_overrides','validation_links','training_ready']:
  data=rows(c,t);save('exports/'+t+'.json',data)
  if data:
   with (ROOT/'exports'/f'{t}.csv').open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
 (ROOT/'schema_v03.sql').write_text('\n'.join(r[0]+';' for r in c.execute("select sql from sqlite_master where sql is not null order by type,name")),encoding='utf-8')
 print(json.dumps({'all_passed':report['all_passed'],'checks':len(checks),'failed':[k for k,v in checks.items() if not v],'counts':counts,'coverage':report['coverage']},ensure_ascii=False,indent=2))
 assert report['all_passed']
if __name__=='__main__':main()
