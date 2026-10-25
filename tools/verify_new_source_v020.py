"""Read-only v0.20 verifier: canonical check-name ordering, all original checks retained.
Original primary manifest, scripts, science DB and reports remain unchanged.
"""
from release_new_source_v020 import *
def verify():
 if not (OUT/'merge_manifest.json').exists():raise FileNotFoundError('Read-only verifier requires sealed release.')
 checks=[]
 def check(name,condition):
  if not condition:raise AssertionError(name)
  checks.append(name)
 for p in json.loads((OUT/'protected_inputs.json').read_text('utf8')):check('protected_'+p['path'],sha(ROOT/p['path'])==p['sha256'])
 # The literature release is immutable; its old verifier assumes the old global cycling pointer.
 # Verify its sealed payloads directly rather than changing that historical verifier/report.
 for p in json.loads((LIT/'merge_manifest.json').read_text('utf8'))['outputs']:check('literature_sealed_'+p['path'],sha(ROOT/p['path'])==p['sha256'])
 with closing(ro(DB)) as c:
  check('sqlite_integrity',c.execute('pragma integrity_check').fetchone()[0]=='ok');check('foreign_keys',not c.execute('pragma foreign_key_check').fetchall())
  check('one_new_endpoint',c.execute('select count(*) from endpoints_v20').fetchone()[0]==1)
  check('three_2e_memberships',c.execute('select count(*) from profile_membership_v20').fetchone()[0]==3)
  check('raw_SI_dissent_retained',c.execute('select count(*) from evidence_v20 where selected=0').fetchone()[0]==2)
  check('no_overwrite_history',c.execute("select count(*) from field_changes_v20 where before_json!='null' or operation!='insert_new_endpoint_field'").fetchone()[0]==0)
 api=load_api(OUT,'_v020_release_verify');parent_api=load_api(PARENT,'_v019_release_verify_parent')
 lp=json.loads((ROOT/'data/current_literature.json').read_text('utf8'));from data.literature_v4 import open_literature_database,PROFILES
 exports={}
 with api.Database(DB) as new,parent_api.Database() as old,open_literature_database() as lit:
  oldall={r['endpoint_id']:r for r in old.fetch('all_review').rows};newall={r['endpoint_id']:r for r in new.fetch('all_review').rows}
  check('append_exactly_one',set(newall)-set(oldall)=={KEY} and len(newall)==278)
  for key,row in oldall.items():
   check('old_row_'+key,newall[key]==row)
   check('old_holds_'+key,new.holds(key)==old.holds(key))
  check('old_change_chain',new.field_changes(include_history=True)[:len(old.field_changes(include_history=True))]==old.field_changes(include_history=True))
  check('old_material_fields',new.material_properties()[:len(old.material_properties())]==old.material_properties())
  check('fixed38_unmodified',new.reviewed_pending_batch()==old.reviewed_pending_batch() and len(new.reviewed_pending_batch())==38)
  cohort_counts={};coverage={}
  for profile in new.contract['profiles']:
   before=old.fetch(profile);after=new.fetch(profile);ids={r['endpoint_id'] for r in after.rows}
   expected={r['endpoint_id'] for r in before.rows}|({KEY} if profile in APPROVED else set())
   check('membership_'+profile,ids==expected)
   matrix=after.feature_matrix();cohort_counts[profile]=dict(rows=len(after.rows),sources=len(set(matrix['groups'])))
   check('matrix_rows_'+profile,len(matrix['X'])==len(matrix['y'])==len(after.rows) and not matrix['training_authorized'])
   for source in set(matrix['groups']):check('weights_'+profile+source,abs(sum(w for g,w in zip(matrix['groups'],matrix['sample_weight']) if g==source)-1)<1e-12)
   for fold in after.source_folds(len(set(matrix['groups']))):check('fold_'+profile+str(fold['test'][0]),not {matrix['groups'][i] for i in fold['train']}&{matrix['groups'][i] for i in fold['test']})
   material=new.method_specific_material_matrix(profile)
   check('no_imputation_'+profile,not material['imputed'] and material['estimators_fitted']==0 and all(mask==(value is None) for row,flags in zip(material['X'],material['missing_mask']) for value,mask in zip(row,flags)))
   coverage[profile]=dict(non_null=sum(v is not None for r in material['X'] for v in r),cells=sum(len(r) for r in material['X']),feature_names=material['feature_names'])
   if profile in APPROVED:
    fields=list(dict.fromkeys(['endpoint_id','source_group','sample_name','source_year']+after.features+['retention_pct','retention_relation','baseline_reference','current_mass_basis','canonical_current_A_g','source_weight']))
    buf=io.StringIO(newline='');writer=csv.DictWriter(buf,fieldnames=fields);writer.writeheader()
    # Audit identifiers are columns for provenance, never implicit model predictors.
    writer.writerows([{k:r.get(k) for k in fields} for r in after.rows])
    exports[profile+'.csv']=buf.getvalue()
  row=new.by_endpoint(KEY);check('same_by_endpoint',row==newall[KEY])
  check('source_identity_new_to_parent',DOI not in {norm(r['source_group']) for r in oldall.values()})
  check('core_values',[(row[k]) for k in ['cycle_count','reported_current_A_g','electrolyte','concentration_mol_L','cycle_voltage_lower_V','cycle_voltage_upper_V','BET_m2_g','retention_pct']]==[10000,5,'KOH',6,0,1,2916,99.8])
  check('unknowns_remain_null',all(row.get(k) is None for k in ['canonical_current_A_g','current_mass_basis','baseline_cycle','hydrothermal_temperature_C','active_mass_mg_v14','mass_loading_mg_cm2','mesopore_volume_cm3_g']))
  check('no_3e_or_strict_approval',not any(c['status']=='approved_for_reported_protocol' for p in ['reported_3e','strict_2e'] for c in new.admission_checks(KEY,p)))
  check('2e_approval',all(c['status']=='approved_for_reported_protocol' for p in APPROVED for c in new.admission_checks(KEY,p)))
  check('resolved_caveat_not_suppressed',not new.holds(KEY)['open_issues'] and bool(new.holds(KEY)['caveats']) and new.holds(KEY)['resolution']['preserved_SI_window_V']==[-1,0])
  check('all_core_evidence',all(new.evidence(KEY,f) for f in new.contract['profiles']['reported_2e']['features']+['retention_pct','system','method']))
  check('XPS_method_projection',row['XPS_N_reported_pct']==14.83 and row['XPS_O_reported_pct']==8.12 and row['XPS_percentage_basis']=='atomic_explicit')
  check('combined_volume_not_meso',row['meso_plus_macro_volume_cm3_g_v20']==1.48 and row['mesopore_volume_cm3_g'] is None)
  check('own_process_doses',row['activation_temperature_C']==800 and row['activation_duration_h']==2 and row['activation_KOH_to_hydrochar_mass_ratio_v20']==1 and row['activation_melamine_to_hydrochar_mass_ratio_v20']==2)
  check('new_alias',any(a['endpoint_id']==KEY and a['doi']==DOI for a in new.source_aliases()))
  check('linked_candidate',new.literature_links()[0]['candidate_id']=='LP5_SSC')
  check('source_search',any(r.get('endpoint_id')==KEY for r in new.search_native('99.8',doi=DOI)))
  check('year_exclusion',KEY not in {r['endpoint_id'] for r in new.fetch('reported_2e',year_max=2025).rows})
  check('year_inclusion',KEY in {r['endpoint_id'] for r in new.fetch('reported_2e',year_min=2026).rows})
  # A cycling holdout quarantines that DOI across every other task, even previously prepared auxiliary data.
  auxiliary=[r for p in PROFILES for r in lit.auxiliary_feature_rows(p)];allcaps=lit.capacitances();cycles=lit.tests()
  excluded_aux=[r for r in auxiliary if norm(r['source_group'])==DOI];train_aux=[r for r in auxiliary if norm(r['source_group'])!=DOI]
  check('29_same_source_aux_quarantined',len(excluded_aux)==29 and len(train_aux)==90 and not {norm(r['source_group']) for r in train_aux}&{DOI})
  check('119_aux_original_rows_retained',len(auxiliary)==119)
  check('33_raw_cap_reports_quarantined',sum(norm(r['source_group'])==DOI for r in allcaps)==33)
  check('2_cycle_candidates_quarantined',sum(norm(r['record']['source_group'])==DOI for r in cycles)==2)
  check('new_only_group_weight',row['source_weight']==1)
  check('parent3E_material_matrix_unchanged',new.method_specific_material_matrix('reported_3e')==old.method_specific_material_matrix('reported_3e'))
  projected=new.method_specific_material_matrix('reported_2e');idx=projected['endpoint_ids'].index(KEY)
  for field,value in [('XPS_N_atomic_pct_v15',14.83),('XPS_O_atomic_pct_v15',8.12),('XPS_N_weight_pct_v15',None),('XPS_O_weight_pct_v15',None)]:check('explicit_XPS_channel_'+field,projected['X'][idx][projected['feature_names'].index(field)]==value)
  check('connections_readonly',new.delta_v20.execute('pragma query_only').fetchone()[0]==1)
  for field,bad in [('reported_current_A_g',None),('retention_pct',float('nan')),('system','3E')]:
   sample=dict(row);sample[field]=bad
   try:api.Dataset('reported_2e',[sample],new.contract['profiles']['reported_2e']['features']).feature_matrix()
   except api.DataNotReady:rejected=True
   else:rejected=False
   check('invalid_row_rejected_'+field,rejected)
  hypothetical=dict(row,retention_pct=105)
  check('retention_is_not_probability_no_upper_clip',api.Dataset('reported_2e',[hypothetical],new.contract['profiles']['reported_2e']['features']).feature_matrix()['y']==[105])
  preflight=dict(model_fits=0,new_endpoint_id=KEY,holdout_source=DOI,auxiliary_all_rows=len(auxiliary),quarantined_auxiliary_rows=len(excluded_aux),remaining_auxiliary_training_rows=len(train_aux),quarantined_raw_capacitance_reports=33,quarantined_cycle_candidates=2,rule='Exclude every label and learned preprocessing contribution from this DOI across auxiliary andcycling tasks. Raw facts and historical candidates are preserved; candidate-to-formal link is not a second experiment.',profiles=cohort_counts,material_matrix_coverage=coverage,performance_improvement_proven=False)
  summary=dict(version='0.20',observations=278,source_groups=len({r['source_group'] for r in newall.values()}),material_keys=len({r['material_key_v11'] for r in newall.values()}),new_endpoints=1,new_source_groups=1,new_admission_purpose='reported aqueous2E symmetricGCD only',profiles=cohort_counts,original_fixed_records=39,original_resolved=1,original_pending=38,newly_linked_literature_candidate='LP5_SSC',material_fields_added=len(new.material_properties())-len(old.material_properties()),formal_main_3e_rows=43,formal_main_3e_sources=31,model_fits=0,full_literature_goal_complete=False)
 sealed=(OUT/'merge_manifest.json').exists();report=dict(status='passed',checks=len(checks),check_names=checks,model_fits=0,scientific_goal_complete=False)
 for name,value in [('summary.json',summary),('verification.json',report),('model_input_preflight.json',preflight)]:
  if sealed:
   saved=json.loads((OUT/name).read_text('utf8'));actual=value
   if name=='verification.json':
    # Check success and multiplicity must agree; set enumeration order is not scientific data.
    saved=dict(saved,check_names=sorted(saved['check_names']))
    actual=dict(actual,check_names=sorted(actual['check_names']))
   assert saved==actual,'sealed_report_'+name
  else:write(OUT/name,value)
 for name,value in exports.items():
  if sealed:
   with (OUT/name).open('r',encoding='utf8',newline='') as f:assert f.read()==value,'sealedCSV_'+name
  else:
   with (OUT/name).open('w',encoding='utf8',newline='') as f:f.write(value)
 if sealed:
  for p in json.loads((OUT/'merge_manifest.json').read_text('utf8'))['outputs']:assert sha(ROOT/p['path'])==p['sha256'],p['path']
 print(json.dumps(dict(status='passed',checks=report['checks'],summary=summary),ensure_ascii=False))

if __name__=='__main__':
 verify()
 addendum=json.loads((OUT/'verification_addendum.json').read_text('utf8'))
 assert sha(OUT/'merge_manifest.json')==addendum['primary_manifest_sha256']
 for p in addendum['outputs']:assert sha(ROOT/p['path'])==p['sha256'],p['path']
 print(json.dumps(dict(addendum_status='passed',payloads=len(addendum['outputs']))))
