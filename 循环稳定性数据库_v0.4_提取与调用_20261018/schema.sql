CREATE INDEX idx_admission_profile ON admission_reviews(profile,status);

CREATE INDEX idx_alias_endpoint ON endpoint_aliases(endpoint_id);

CREATE UNIQUE INDEX idx_feature_cache_endpoint ON model_feature_cache(endpoint_id);

CREATE INDEX idx_feature_cache_group ON model_feature_cache(source_group);

CREATE INDEX idx_feature_cache_identity ON model_feature_cache(identity_key);

CREATE INDEX idx_feature_cache_system_year ON model_feature_cache(system,source_year);

CREATE INDEX idx_field_observations_endpoint ON field_observations(endpoint_id,field_name);

CREATE INDEX idx_field_source ON field_observations(source_id,segment_id);

CREATE INDEX idx_leads_identity ON extraction_leads(identity_key);

CREATE INDEX idx_model_endpoints_group ON model_endpoints(source_group);

CREATE INDEX idx_model_endpoints_identity ON model_endpoints(identity_key);

CREATE INDEX idx_native_claim_cycle ON native_measurement_claims(cycle_count_candidate);

CREATE INDEX idx_native_claim_identity ON native_measurement_claims(identity_key);

CREATE INDEX idx_paper_docs_identity ON paper_documents(identity_key,role);

CREATE INDEX idx_queue_priority ON extraction_queue(priority,status);

CREATE INDEX idx_segments_source ON source_segments(source_id);

CREATE INDEX idx_tests_system ON model_tests(system,method);

CREATE UNIQUE INDEX paper_doi ON papers(lower(doi)) WHERE doi IS NOT NULL AND doi<>'';

CREATE TABLE admission_decisions_r3(
 record_id TEXT PRIMARY KEY REFERENCES cycling_endpoints,primary_disposition TEXT NOT NULL,
 failures_json TEXT NOT NULL,core_fields_present INTEGER NOT NULL,optional_pore_value REAL,
 review_extent TEXT NOT NULL);

CREATE TABLE admission_reviews(endpoint_id TEXT REFERENCES model_endpoints,profile TEXT,status TEXT NOT NULL CHECK(status IN ('pending','approved','excluded')),reason TEXT NOT NULL,PRIMARY KEY(endpoint_id,profile));

CREATE TABLE admissions(
 record_id TEXT PRIMARY KEY REFERENCES cycling_endpoints,status TEXT NOT NULL,
 source_checked INTEGER NOT NULL DEFAULT 0,material_checked INTEGER NOT NULL DEFAULT 0,
 protocol_checked INTEGER NOT NULL DEFAULT 0,baseline_checked INTEGER NOT NULL DEFAULT 0,
 mass_basis_checked INTEGER NOT NULL DEFAULT 0,independence_checked INTEGER NOT NULL DEFAULT 0,
 freeze_cleared INTEGER NOT NULL DEFAULT 0,eligible INTEGER NOT NULL DEFAULT 0 CHECK(eligible IN (0,1)),
 rationale TEXT NOT NULL,
 CHECK(eligible=0 OR (status='approved' AND source_checked=1 AND material_checked=1 AND protocol_checked=1 AND baseline_checked=1 AND mass_basis_checked=1 AND independence_checked=1 AND freeze_cleared=1))
);

CREATE TABLE blocker_scopes(
 record_id TEXT NOT NULL,code TEXT NOT NULL,scope_kind TEXT NOT NULL,field_name TEXT,
 affects_core7 INTEGER NOT NULL,policy TEXT NOT NULL,PRIMARY KEY(record_id,code),
 FOREIGN KEY(record_id,code) REFERENCES record_blockers(record_id,code));

CREATE TABLE candidate_measurement_claims(claim_id INTEGER PRIMARY KEY,identity_key TEXT REFERENCES literature_registry,batch TEXT,local_id TEXT,raw_json TEXT,status TEXT NOT NULL);

CREATE TABLE candidate_review_holds(observation_id INTEGER PRIMARY KEY REFERENCES literature_observations,identity_key TEXT REFERENCES literature_registry,batch TEXT,issues_json TEXT,status TEXT CHECK(status='staged_no_admission'));

CREATE TABLE current_baseline_evidence(record_id TEXT PRIMARY KEY REFERENCES cycling_endpoints,legacy_baseline_json TEXT,review_evidence_json TEXT,status TEXT,exact_baseline_cycle INTEGER);

CREATE TABLE current_field_evidence(record_id TEXT REFERENCES cycling_endpoints,field_name TEXT,ledger_value_json TEXT,effective_value_json TEXT,ledger_status TEXT,resolution_status TEXT,review_ids_json TEXT,provenance_json TEXT,PRIMARY KEY(record_id,field_name));

CREATE TABLE cycling_endpoints(
 record_id TEXT PRIMARY KEY REFERENCES raw_records,cycle_test_id TEXT NOT NULL REFERENCES cycling_tests,
 cycle_count INTEGER CHECK(cycle_count IS NULL OR cycle_count>0),retention_pct REAL CHECK(retention_pct IS NULL OR retention_pct>=0),
 retention_relation TEXT NOT NULL CHECK(retention_relation IN ('eq','approx','gt')),
 retention_sd_pct REAL,metric_kind TEXT NOT NULL,value_kind TEXT NOT NULL,
 material_scope TEXT NOT NULL,conflict INTEGER NOT NULL CHECK(conflict IN (0,1)),short_test INTEGER NOT NULL,
 evidence_path TEXT NOT NULL,evidence_pages_json TEXT NOT NULL,evidence_locator TEXT,
 note TEXT,legacy_json_flags TEXT NOT NULL
);

CREATE TABLE cycling_tests(
 cycle_test_id TEXT PRIMARY KEY,paper_id TEXT NOT NULL REFERENCES papers,material_id TEXT NOT NULL REFERENCES materials,
 legacy_cycle_test_id TEXT NOT NULL,system TEXT NOT NULL,method TEXT NOT NULL,electrolyte TEXT,
 concentration_value REAL,concentration_unit TEXT,current_density_A_g REAL,current_density_mA_cm2 REAL,
 scan_rate_mV_s REAL,voltage_lower_V REAL,voltage_upper_V REAL,temperature_C REAL,
 mass_basis TEXT,baseline_json TEXT,positive_negative_mass_ratio REAL,protocol_note TEXT
);

CREATE TABLE document_locations(source_id TEXT REFERENCES document_sources,path TEXT,PRIMARY KEY(source_id,path));

CREATE TABLE document_sources(source_id TEXT PRIMARY KEY,sha256 TEXT NOT NULL UNIQUE,format TEXT,parse_status TEXT,parse_error TEXT,segment_count INTEGER,text_characters INTEGER);

CREATE TABLE domain_reviews_r4(
      record_id TEXT NOT NULL REFERENCES cycling_endpoints,topic TEXT NOT NULL,
      decision TEXT NOT NULL,value_json TEXT,source_path TEXT NOT NULL,source_sha256 TEXT NOT NULL,
      locator TEXT NOT NULL,rationale TEXT NOT NULL,PRIMARY KEY(record_id,topic));

CREATE TABLE endpoint_aliases(namespace TEXT,alias TEXT,endpoint_id TEXT REFERENCES model_endpoints,PRIMARY KEY(namespace,alias));

CREATE TABLE endpoint_features(
 record_id TEXT PRIMARY KEY REFERENCES cycling_endpoints,BET_m2_g REAL,total_pore_volume_cm3_g REAL,
 N_at_pct REAL,O_at_pct REAL,N_wt_pct REAL,O_wt_pct REAL,mass_loading_mg_cm2 REAL,
 Si_residue_review_required INTEGER NOT NULL DEFAULT 0,pore_unit_review_required INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE endpoint_protocol_overrides(record_id TEXT NOT NULL REFERENCES cycling_endpoints,field_name TEXT NOT NULL CHECK(field_name IN ('voltage_lower_V','voltage_upper_V')),value_json TEXT NOT NULL,status TEXT NOT NULL,review_id INTEGER NOT NULL REFERENCES review_events,PRIMARY KEY(record_id,field_name));

CREATE TABLE extraction_issue_resolutions(issue_id INTEGER PRIMARY KEY REFERENCES extraction_issues,decision TEXT NOT NULL,evidence_json TEXT NOT NULL);

CREATE TABLE extraction_issues(issue_id INTEGER PRIMARY KEY,endpoint_id TEXT REFERENCES model_endpoints,identity_key TEXT REFERENCES literature_registry,field_name TEXT,code TEXT,status TEXT,evidence_json TEXT,reason TEXT);

CREATE TABLE extraction_leads(lead_id INTEGER PRIMARY KEY,identity_key TEXT REFERENCES literature_registry,source_id TEXT REFERENCES document_sources,segment_id INTEGER REFERENCES source_segments,lead_kind TEXT,claim_status TEXT,excerpt TEXT);

CREATE TABLE extraction_queue(identity_key TEXT PRIMARY KEY REFERENCES literature_registry,priority INTEGER,document_type TEXT,main_source_id TEXT REFERENCES document_sources,status TEXT NOT NULL,reason TEXT NOT NULL);

CREATE TABLE extraction_run(key TEXT PRIMARY KEY,value_json TEXT NOT NULL);

CREATE TABLE feature_cache_meta(key TEXT PRIMARY KEY,value TEXT);

CREATE TABLE field_evidence(
 evidence_id INTEGER PRIMARY KEY,record_id TEXT NOT NULL REFERENCES raw_records,field_name TEXT NOT NULL,
 value_json TEXT NOT NULL,source_path TEXT NOT NULL,locator TEXT NOT NULL,status TEXT NOT NULL,
 UNIQUE(record_id,field_name)
);

CREATE TABLE field_observations(observation_id INTEGER PRIMARY KEY,endpoint_id TEXT REFERENCES model_endpoints,field_name TEXT,value_json TEXT NOT NULL,unit TEXT,status TEXT NOT NULL,source_id TEXT REFERENCES document_sources,segment_id INTEGER REFERENCES source_segments,locator TEXT,evidence_excerpt TEXT,provenance_json TEXT NOT NULL);

CREATE TABLE field_selection(endpoint_id TEXT REFERENCES model_endpoints,field_name TEXT,observation_id INTEGER REFERENCES field_observations,PRIMARY KEY(endpoint_id,field_name));

CREATE TABLE field_selection_history(selection_id INTEGER PRIMARY KEY,endpoint_id TEXT REFERENCES model_endpoints,field_name TEXT,old_observation_id INTEGER REFERENCES field_observations,new_observation_id INTEGER REFERENCES field_observations,reason TEXT NOT NULL);

CREATE TABLE ingestion_sources(path TEXT PRIMARY KEY,sha256 TEXT NOT NULL,role TEXT NOT NULL);

CREATE TABLE issue_resolutions(issue_id INTEGER PRIMARY KEY REFERENCES issues,review_id INTEGER NOT NULL REFERENCES review_events,effective_status TEXT NOT NULL,rationale TEXT NOT NULL);

CREATE TABLE issues(
 issue_id INTEGER PRIMARY KEY,paper_id TEXT REFERENCES papers,record_id TEXT REFERENCES raw_records,
 severity TEXT NOT NULL,code TEXT NOT NULL,description TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'open',
 source_path TEXT,scope TEXT NOT NULL
);

CREATE TABLE literature_aliases(batch TEXT,local_id TEXT,identity_key TEXT REFERENCES literature_registry,PRIMARY KEY(batch,local_id,identity_key));

CREATE TABLE literature_availability(identity_key TEXT PRIMARY KEY REFERENCES literature_registry,repository_main_files_json TEXT,declared_external_files_json TEXT,status TEXT,admission_status TEXT CHECK(admission_status='not_changed_by_availability'));

CREATE TABLE literature_observations(observation_id INTEGER PRIMARY KEY,identity_key TEXT REFERENCES literature_registry,batch TEXT,local_id TEXT,source_json TEXT NOT NULL);

CREATE TABLE literature_registry(identity_key TEXT PRIMARY KEY,doi TEXT UNIQUE,title TEXT,has_archived_paper INTEGER NOT NULL,archive_status TEXT NOT NULL,training_admitted INTEGER NOT NULL CHECK(training_admitted=0));

CREATE TABLE mass_definition_audits(
 record_id TEXT PRIMARY KEY REFERENCES cycling_endpoints,review_id INTEGER REFERENCES review_events,
 current_basis_status TEXT NOT NULL,current_basis_evidence TEXT NOT NULL,
 capacitance_basis_separately_reported TEXT,remaining_required_evidence TEXT NOT NULL,
 acquisition_limit TEXT NOT NULL);

CREATE TABLE material_identity_aliases(old_material_id TEXT PRIMARY KEY REFERENCES model_materials,canonical_material_id TEXT REFERENCES model_materials,reason TEXT NOT NULL);

CREATE TABLE material_observations(
 observation_id INTEGER PRIMARY KEY,material_id TEXT NOT NULL REFERENCES materials,
 record_id TEXT NOT NULL REFERENCES raw_records,property_name TEXT NOT NULL,value_json TEXT NOT NULL,
 unit TEXT,method TEXT,stage TEXT NOT NULL,source_path TEXT NOT NULL,locator TEXT NOT NULL,
 provenance_status TEXT NOT NULL
);

CREATE TABLE material_properties(property_id INTEGER PRIMARY KEY,material_id TEXT REFERENCES model_materials,property_name TEXT,reported_value TEXT,numeric_value REAL,unit TEXT,stage TEXT,method TEXT,status TEXT,source_id TEXT REFERENCES document_sources,segment_id INTEGER REFERENCES source_segments,locator TEXT,raw_row_json TEXT);

CREATE TABLE materials(
 material_id TEXT PRIMARY KEY,paper_id TEXT NOT NULL REFERENCES papers,sample_name TEXT NOT NULL,
 legacy_material_id TEXT NOT NULL,identity_status TEXT NOT NULL DEFAULT 'provisional_within_paper'
);

CREATE TABLE merge_conflicts(conflict_id INTEGER PRIMARY KEY,kind TEXT,record_ref TEXT,status TEXT,old_json TEXT,new_json TEXT,evidence_json TEXT,decision TEXT NOT NULL);

CREATE TABLE merge_contract(key TEXT PRIMARY KEY,value_json TEXT NOT NULL);

CREATE TABLE merge_input_files(manifest TEXT,path TEXT,sha256 TEXT,role TEXT,PRIMARY KEY(manifest,path));

CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);

CREATE TABLE model_endpoints(endpoint_id TEXT PRIMARY KEY,identity_key TEXT REFERENCES literature_registry,material_id TEXT REFERENCES model_materials,test_id TEXT REFERENCES model_tests,metric_kind TEXT NOT NULL,source_group TEXT NOT NULL,source_year INTEGER,year_basis TEXT,workflow_status TEXT NOT NULL,legacy_record_id TEXT REFERENCES cycling_endpoints);

CREATE TABLE model_feature_cache(
  endpoint_id TEXT,
  identity_key TEXT,
  material_id TEXT,
  test_id TEXT,
  metric_kind TEXT,
  source_group TEXT,
  source_year INT,
  year_basis TEXT,
  workflow_status TEXT,
  legacy_record_id TEXT,
  sample_name TEXT,
  system TEXT,
  method TEXT,
  curve_group TEXT,
  BET_m2_g,
  BET_m2_g_status,
  N_at_pct,
  N_at_pct_status,
  O_at_pct,
  O_at_pct_status,
  baseline_cycle,
  baseline_cycle_status,
  baseline_reference,
  baseline_reference_status,
  canonical_current_A_g,
  canonical_current_A_g_status,
  characterization_voltage_lower_V,
  characterization_voltage_lower_V_status,
  characterization_voltage_upper_V,
  characterization_voltage_upper_V_status,
  concentration_mol_L,
  concentration_mol_L_status,
  current_mA_cm2,
  current_mA_cm2_status,
  current_mass_basis,
  current_mass_basis_status,
  cycle_count,
  cycle_count_status,
  cycle_voltage_lower_V,
  cycle_voltage_lower_V_status,
  cycle_voltage_upper_V,
  cycle_voltage_upper_V_status,
  electrolyte,
  electrolyte_status,
  mass_loading_mg_cm2,
  mass_loading_mg_cm2_status,
  raw_total_pore_volume_m3_g,
  raw_total_pore_volume_m3_g_status,
  reference_electrode,
  reference_electrode_status,
  reported_current_A_g,
  reported_current_A_g_status,
  retention_pct,
  retention_pct_status,
  retention_relation,
  retention_relation_status,
  scope_flags,
  scope_flags_status,
  temperature_C,
  temperature_C_status,
  total_pore_volume_cm3_g,
  total_pore_volume_cm3_g_status,
  value_kind,
  value_kind_status
);

CREATE TABLE model_materials(material_id TEXT PRIMARY KEY,identity_key TEXT REFERENCES literature_registry,sample_name TEXT,identity_status TEXT NOT NULL,legacy_material_id TEXT);

CREATE TABLE model_tests(test_id TEXT PRIMARY KEY,material_id TEXT REFERENCES model_materials,system TEXT,method TEXT,curve_group TEXT,protocol_status TEXT NOT NULL,legacy_test_id TEXT);

CREATE TABLE native_measurement_claims(claim_id INTEGER PRIMARY KEY,identity_key TEXT REFERENCES literature_registry,source_id TEXT REFERENCES document_sources,segment_id INTEGER REFERENCES source_segments,start_offset INTEGER,end_offset INTEGER,cycle_count_candidate INTEGER,retention_pct_candidate REAL,metric_wording TEXT,qualifier TEXT,source_context TEXT,evidence_span TEXT,review_status TEXT NOT NULL CHECK(review_status='machine_pair_candidate_unreviewed'),eligible INTEGER NOT NULL CHECK(eligible=0),UNIQUE(identity_key,segment_id,start_offset,end_offset));

CREATE TABLE paper_documents(identity_key TEXT REFERENCES literature_registry,source_id TEXT REFERENCES document_sources,role TEXT,basis TEXT,PRIMARY KEY(identity_key,source_id,role));

CREATE TABLE paper_utilization(paper_id TEXT PRIMARY KEY REFERENCES papers,use_role TEXT NOT NULL,existing_endpoint_count INTEGER NOT NULL,search_hits INTEGER NOT NULL,decision_extent TEXT NOT NULL,reason TEXT NOT NULL);

CREATE TABLE papers(
 paper_id TEXT PRIMARY KEY,doi TEXT,title TEXT NOT NULL,year INTEGER,category TEXT NOT NULL,
 study_group TEXT NOT NULL,main_format TEXT NOT NULL,main_path TEXT NOT NULL,main_sha256 TEXT NOT NULL,
 archive_restrictions TEXT,independence_status TEXT NOT NULL DEFAULT 'pending_review'
);

CREATE TABLE profile_admissions_r4(
      profile TEXT NOT NULL,record_id TEXT NOT NULL REFERENCES cycling_endpoints,
      eligible INTEGER NOT NULL CHECK(eligible IN(0,1)),status TEXT NOT NULL,
      failures_json TEXT NOT NULL,qualified_use TEXT NOT NULL,caveats_json TEXT NOT NULL,
      evidence_json TEXT NOT NULL,review_extent TEXT NOT NULL,
      PRIMARY KEY(profile,record_id),CHECK(eligible=0 OR status='approved_for_declared_profile'));

CREATE TABLE profile_blocker_dispositions(profile TEXT,record_id TEXT,code TEXT,strict_status TEXT,proposal_disposition TEXT,evidence_json TEXT,PRIMARY KEY(profile,record_id,code),FOREIGN KEY(profile,record_id) REFERENCES profile_admissions_r4(profile,record_id));

CREATE TABLE profile_definitions_r4(profile TEXT PRIMARY KEY,definition_json TEXT NOT NULL);

CREATE TABLE raw_records(
 record_id TEXT PRIMARY KEY,legacy_record_id TEXT NOT NULL,paper_id TEXT NOT NULL REFERENCES papers,
 input_path TEXT NOT NULL REFERENCES ingestion_sources(path),raw_json TEXT NOT NULL
);

CREATE TABLE record_blockers(record_id TEXT NOT NULL REFERENCES cycling_endpoints,code TEXT NOT NULL,status TEXT NOT NULL CHECK(status IN ('open','resolved_by_review','resolved_by_erratum')),rationale TEXT NOT NULL,review_id INTEGER REFERENCES review_events,PRIMARY KEY(record_id,code));

CREATE TABLE review_batches(batch_id TEXT PRIMARY KEY,baseline_sha256 TEXT NOT NULL,scope TEXT NOT NULL,policy TEXT NOT NULL);

CREATE TABLE review_events(
              review_id INTEGER PRIMARY KEY,record_id TEXT NOT NULL REFERENCES cycling_endpoints,
              field_name TEXT NOT NULL,decision TEXT NOT NULL,value_json TEXT,
              source_path TEXT NOT NULL,source_sha256 TEXT NOT NULL,locator TEXT NOT NULL,
              evidence_excerpt TEXT NOT NULL,rationale TEXT NOT NULL,review_date TEXT NOT NULL);

CREATE TABLE revision_changes(
              change_id INTEGER PRIMARY KEY,table_name TEXT NOT NULL,row_key TEXT NOT NULL,
              field_name TEXT NOT NULL,old_json TEXT,new_json TEXT,rationale TEXT NOT NULL);

CREATE TABLE source_files(
 file_id INTEGER PRIMARY KEY,paper_id TEXT NOT NULL REFERENCES papers,path TEXT NOT NULL UNIQUE,
 role TEXT NOT NULL,format TEXT NOT NULL,sha256 TEXT NOT NULL,pages INTEGER
);

CREATE TABLE source_group_reviews(
 paper_id TEXT PRIMARY KEY REFERENCES papers,group_id TEXT NOT NULL,status TEXT NOT NULL,
 corpus_audit_path TEXT NOT NULL,scope_notes TEXT NOT NULL,review_id INTEGER REFERENCES review_events);

CREATE TABLE source_relationships(
 relationship_id INTEGER PRIMARY KEY,paper_id TEXT NOT NULL REFERENCES papers,related_paper_id TEXT REFERENCES papers,
 related_doi TEXT,relationship TEXT NOT NULL,status TEXT NOT NULL,note TEXT NOT NULL
);

CREATE VIRTUAL TABLE source_search USING fts5(text,content='source_segments',content_rowid='segment_id');

CREATE TABLE 'source_search_config'(k PRIMARY KEY, v) WITHOUT ROWID;

CREATE TABLE 'source_search_data'(id INTEGER PRIMARY KEY, block BLOB);

CREATE TABLE 'source_search_docsize'(id INTEGER PRIMARY KEY, sz BLOB);

CREATE TABLE 'source_search_idx'(segid, term, pgno, PRIMARY KEY(segid, term)) WITHOUT ROWID;

CREATE TABLE source_segments(segment_id INTEGER PRIMARY KEY,source_id TEXT REFERENCES document_sources,locator TEXT NOT NULL,section_kind TEXT NOT NULL,text TEXT NOT NULL,UNIQUE(source_id,locator));

CREATE TABLE staged_cycling_evidence(endpoint_id TEXT PRIMARY KEY,identity_key TEXT REFERENCES literature_registry,system TEXT,method TEXT,cycle_count INTEGER,retention_pct REAL,retention_relation TEXT,value_kind TEXT,reported_current_A_g REAL,source_file TEXT,source_sha256 TEXT,linked_record_id TEXT REFERENCES cycling_endpoints,link_status TEXT NOT NULL,training_admitted INTEGER NOT NULL CHECK(training_admitted=0),evidence_json TEXT NOT NULL);

CREATE TABLE staged_recovery_endpoints(candidate_id TEXT PRIMARY KEY,paper_id TEXT NOT NULL REFERENCES papers,material_id TEXT REFERENCES materials,sample_name TEXT,system TEXT,method TEXT,metric_kind TEXT,cycle_count INTEGER,retention_pct REAL,retention_relation TEXT,current_density_A_g REAL,electrolyte TEXT,concentration_value REAL,concentration_unit TEXT,voltage_lower_V REAL,voltage_upper_V REAL,source_path TEXT NOT NULL,source_sha256 TEXT NOT NULL,locator TEXT NOT NULL,evidence_excerpt TEXT NOT NULL,rationale TEXT NOT NULL,eligible INTEGER NOT NULL CHECK(eligible=0));

CREATE TABLE unified_source_groups(identity_key TEXT PRIMARY KEY REFERENCES literature_registry,group_id TEXT NOT NULL,review_status TEXT NOT NULL,basis_json TEXT NOT NULL);

CREATE TABLE utilization_routes(record_id TEXT PRIMARY KEY REFERENCES cycling_endpoints,track TEXT NOT NULL,label_tier TEXT NOT NULL,usable_role TEXT NOT NULL,main_eligible INTEGER NOT NULL CHECK(main_eligible=0),reason TEXT NOT NULL,review_extent TEXT NOT NULL);

CREATE TABLE validation_group_assignments(
 record_id TEXT PRIMARY KEY REFERENCES cycling_endpoints,group_id TEXT NOT NULL,
 basis TEXT NOT NULL,review_status TEXT NOT NULL);

CREATE TABLE validation_links(link_id INTEGER PRIMARY KEY,record_a TEXT REFERENCES cycling_endpoints,record_b TEXT REFERENCES cycling_endpoints,related_doi TEXT,relation TEXT NOT NULL,status TEXT NOT NULL,group_policy TEXT NOT NULL,rationale TEXT NOT NULL,review_id INTEGER REFERENCES review_events);

CREATE VIEW endpoint_effective_review AS SELECT e.record_id,e.cycle_test_id,e.cycle_count,e.retention_pct,e.retention_relation,e.retention_sd_pct,e.metric_kind,e.value_kind,e.material_scope,e.conflict,e.short_test,e.evidence_path,e.evidence_pages_json,e.evidence_locator,e.note,e.legacy_json_flags,e.paper_id,e.material_id,e.system,e.method,e.electrolyte,e.concentration_value,e.concentration_unit,e.current_density_A_g,e.current_density_mA_cm2,CASE WHEN EXISTS(SELECT 1 FROM endpoint_protocol_overrides o WHERE o.record_id=e.record_id AND o.field_name='voltage_lower_V') THEN (SELECT json_extract(o.value_json,'$') FROM endpoint_protocol_overrides o WHERE o.record_id=e.record_id AND o.field_name='voltage_lower_V') ELSE e.voltage_lower_V END AS voltage_lower_V,CASE WHEN EXISTS(SELECT 1 FROM endpoint_protocol_overrides o WHERE o.record_id=e.record_id AND o.field_name='voltage_upper_V') THEN (SELECT json_extract(o.value_json,'$') FROM endpoint_protocol_overrides o WHERE o.record_id=e.record_id AND o.field_name='voltage_upper_V') ELSE e.voltage_upper_V END AS voltage_upper_V,e.mass_basis,e.baseline_json,e.study_group,e.doi,e.category,e.sample_name,e.BET_m2_g,e.total_pore_volume_cm3_g,e.N_at_pct,e.O_at_pct,e.N_wt_pct,e.O_wt_pct,e.mass_loading_mg_cm2,e.Si_residue_review_required,e.pore_unit_review_required,e.admission_status,e.eligible FROM endpoint_review e;

CREATE VIEW endpoint_review AS
 SELECT e.*,t.paper_id,t.material_id,t.system,t.method,t.electrolyte,t.concentration_value,t.concentration_unit,
 t.current_density_A_g,t.current_density_mA_cm2,t.voltage_lower_V,t.voltage_upper_V,t.mass_basis,t.baseline_json,
 p.study_group,p.doi,p.category,m.sample_name,f.BET_m2_g,f.total_pore_volume_cm3_g,
 f.N_at_pct,f.O_at_pct,f.N_wt_pct,f.O_wt_pct,f.mass_loading_mg_cm2,
 f.Si_residue_review_required,f.pore_unit_review_required,a.status AS admission_status,a.eligible
 FROM cycling_endpoints e JOIN cycling_tests t USING(cycle_test_id)
 JOIN papers p ON p.paper_id=t.paper_id JOIN materials m ON m.material_id=t.material_id
 JOIN endpoint_features f USING(record_id) JOIN admissions a USING(record_id);

CREATE VIEW field_review_latest AS SELECT r.* FROM review_events r WHERE review_id=(SELECT max(x.review_id) FROM review_events x WHERE x.record_id=r.record_id AND x.field_name=r.field_name);

CREATE VIEW issues_effective AS SELECT i.*,coalesce(r.effective_status,i.status) AS effective_status,r.review_id AS resolution_review_id,r.rationale AS resolution_rationale FROM issues i LEFT JOIN issue_resolutions r USING(issue_id);

CREATE VIEW model_feature_rows AS SELECT e.*,m.sample_name,t.system,t.method,t.curve_group,MAX(CASE WHEN o.field_name='BET_m2_g' THEN json_extract(o.value_json,'$') END) AS BET_m2_g,MAX(CASE WHEN o.field_name='BET_m2_g' THEN o.status END) AS BET_m2_g_status,MAX(CASE WHEN o.field_name='N_at_pct' THEN json_extract(o.value_json,'$') END) AS N_at_pct,MAX(CASE WHEN o.field_name='N_at_pct' THEN o.status END) AS N_at_pct_status,MAX(CASE WHEN o.field_name='O_at_pct' THEN json_extract(o.value_json,'$') END) AS O_at_pct,MAX(CASE WHEN o.field_name='O_at_pct' THEN o.status END) AS O_at_pct_status,MAX(CASE WHEN o.field_name='baseline_cycle' THEN json_extract(o.value_json,'$') END) AS baseline_cycle,MAX(CASE WHEN o.field_name='baseline_cycle' THEN o.status END) AS baseline_cycle_status,MAX(CASE WHEN o.field_name='baseline_reference' THEN json_extract(o.value_json,'$') END) AS baseline_reference,MAX(CASE WHEN o.field_name='baseline_reference' THEN o.status END) AS baseline_reference_status,MAX(CASE WHEN o.field_name='canonical_current_A_g' THEN json_extract(o.value_json,'$') END) AS canonical_current_A_g,MAX(CASE WHEN o.field_name='canonical_current_A_g' THEN o.status END) AS canonical_current_A_g_status,MAX(CASE WHEN o.field_name='characterization_voltage_lower_V' THEN json_extract(o.value_json,'$') END) AS characterization_voltage_lower_V,MAX(CASE WHEN o.field_name='characterization_voltage_lower_V' THEN o.status END) AS characterization_voltage_lower_V_status,MAX(CASE WHEN o.field_name='characterization_voltage_upper_V' THEN json_extract(o.value_json,'$') END) AS characterization_voltage_upper_V,MAX(CASE WHEN o.field_name='characterization_voltage_upper_V' THEN o.status END) AS characterization_voltage_upper_V_status,MAX(CASE WHEN o.field_name='concentration_mol_L' THEN json_extract(o.value_json,'$') END) AS concentration_mol_L,MAX(CASE WHEN o.field_name='concentration_mol_L' THEN o.status END) AS concentration_mol_L_status,MAX(CASE WHEN o.field_name='current_mA_cm2' THEN json_extract(o.value_json,'$') END) AS current_mA_cm2,MAX(CASE WHEN o.field_name='current_mA_cm2' THEN o.status END) AS current_mA_cm2_status,MAX(CASE WHEN o.field_name='current_mass_basis' THEN json_extract(o.value_json,'$') END) AS current_mass_basis,MAX(CASE WHEN o.field_name='current_mass_basis' THEN o.status END) AS current_mass_basis_status,MAX(CASE WHEN o.field_name='cycle_count' THEN json_extract(o.value_json,'$') END) AS cycle_count,MAX(CASE WHEN o.field_name='cycle_count' THEN o.status END) AS cycle_count_status,MAX(CASE WHEN o.field_name='cycle_voltage_lower_V' THEN json_extract(o.value_json,'$') END) AS cycle_voltage_lower_V,MAX(CASE WHEN o.field_name='cycle_voltage_lower_V' THEN o.status END) AS cycle_voltage_lower_V_status,MAX(CASE WHEN o.field_name='cycle_voltage_upper_V' THEN json_extract(o.value_json,'$') END) AS cycle_voltage_upper_V,MAX(CASE WHEN o.field_name='cycle_voltage_upper_V' THEN o.status END) AS cycle_voltage_upper_V_status,MAX(CASE WHEN o.field_name='electrolyte' THEN json_extract(o.value_json,'$') END) AS electrolyte,MAX(CASE WHEN o.field_name='electrolyte' THEN o.status END) AS electrolyte_status,MAX(CASE WHEN o.field_name='mass_loading_mg_cm2' THEN json_extract(o.value_json,'$') END) AS mass_loading_mg_cm2,MAX(CASE WHEN o.field_name='mass_loading_mg_cm2' THEN o.status END) AS mass_loading_mg_cm2_status,MAX(CASE WHEN o.field_name='raw_total_pore_volume_m3_g' THEN json_extract(o.value_json,'$') END) AS raw_total_pore_volume_m3_g,MAX(CASE WHEN o.field_name='raw_total_pore_volume_m3_g' THEN o.status END) AS raw_total_pore_volume_m3_g_status,MAX(CASE WHEN o.field_name='reference_electrode' THEN json_extract(o.value_json,'$') END) AS reference_electrode,MAX(CASE WHEN o.field_name='reference_electrode' THEN o.status END) AS reference_electrode_status,MAX(CASE WHEN o.field_name='reported_current_A_g' THEN json_extract(o.value_json,'$') END) AS reported_current_A_g,MAX(CASE WHEN o.field_name='reported_current_A_g' THEN o.status END) AS reported_current_A_g_status,MAX(CASE WHEN o.field_name='retention_pct' THEN json_extract(o.value_json,'$') END) AS retention_pct,MAX(CASE WHEN o.field_name='retention_pct' THEN o.status END) AS retention_pct_status,MAX(CASE WHEN o.field_name='retention_relation' THEN json_extract(o.value_json,'$') END) AS retention_relation,MAX(CASE WHEN o.field_name='retention_relation' THEN o.status END) AS retention_relation_status,MAX(CASE WHEN o.field_name='scope_flags' THEN json_extract(o.value_json,'$') END) AS scope_flags,MAX(CASE WHEN o.field_name='scope_flags' THEN o.status END) AS scope_flags_status,MAX(CASE WHEN o.field_name='temperature_C' THEN json_extract(o.value_json,'$') END) AS temperature_C,MAX(CASE WHEN o.field_name='temperature_C' THEN o.status END) AS temperature_C_status,MAX(CASE WHEN o.field_name='total_pore_volume_cm3_g' THEN json_extract(o.value_json,'$') END) AS total_pore_volume_cm3_g,MAX(CASE WHEN o.field_name='total_pore_volume_cm3_g' THEN o.status END) AS total_pore_volume_cm3_g_status,MAX(CASE WHEN o.field_name='value_kind' THEN json_extract(o.value_json,'$') END) AS value_kind,MAX(CASE WHEN o.field_name='value_kind' THEN o.status END) AS value_kind_status FROM model_endpoints e JOIN model_materials m USING(material_id) JOIN model_tests t USING(test_id) JOIN field_selection s USING(endpoint_id) JOIN field_observations o ON o.observation_id=s.observation_id GROUP BY e.endpoint_id;

CREATE VIEW modeling_effective_inputs AS SELECT e.record_id,e.cycle_test_id,e.cycle_count,e.retention_pct,e.retention_relation,e.retention_sd_pct,e.metric_kind,e.value_kind,e.material_scope,e.conflict,e.short_test,e.evidence_path,e.evidence_pages_json,e.evidence_locator,e.note,e.legacy_json_flags,e.paper_id,e.material_id,e.system,e.method,e.electrolyte,e.concentration_value,e.concentration_unit,e.current_density_A_g,e.current_density_mA_cm2,e.voltage_lower_V,e.voltage_upper_V,e.mass_basis,e.baseline_json,e.study_group,e.doi,e.category,e.sample_name,e.BET_m2_g,CASE WHEN e.pore_unit_review_required=1 OR EXISTS(SELECT 1 FROM record_blockers b JOIN blocker_scopes s USING(record_id,code) WHERE b.record_id=e.record_id AND b.status='open' AND s.scope_kind='field' AND s.field_name='total_pore_volume_cm3_g') THEN NULL ELSE e.total_pore_volume_cm3_g END AS total_pore_volume_cm3_g,e.N_at_pct,e.O_at_pct,e.N_wt_pct,e.O_wt_pct,e.mass_loading_mg_cm2,e.Si_residue_review_required,e.pore_unit_review_required,e.admission_status,e.eligible FROM endpoint_effective_review e;

CREATE VIEW primary_screening_candidates AS
 SELECT * FROM endpoint_review
 WHERE system='2E_symmetric' AND method='GCD' AND metric_kind='capacitance_retention'
 AND material_scope IN ('carbon_candidate','carbon_control')
 AND retention_relation='eq' AND retention_pct IS NOT NULL AND cycle_count>=1000
 AND conflict=0 AND short_test=0 AND category IN ('A','B') AND Si_residue_review_required=0;

CREATE VIEW proposal_training_ready_r4 AS SELECT * FROM training_rows_r4 WHERE profile='literature_core7_exact';

CREATE VIEW review_3e_rows AS SELECT f.* FROM model_feature_rows f WHERE EXISTS(SELECT 1 FROM endpoint_aliases a WHERE a.endpoint_id=f.endpoint_id AND a.namespace='TE');

CREATE VIEW training_ready AS SELECT * FROM training_ready_canonical_current;

CREATE VIEW training_ready_2e AS SELECT f.* FROM model_feature_rows f JOIN admission_reviews a USING(endpoint_id) WHERE a.profile='canonical_2e' AND a.status='approved' AND f.system='2E_symmetric' AND f.method='GCD' AND f.metric_kind='capacitance_retention' AND f.retention_relation='eq' AND f.cycle_count>=1000 AND f.source_year BETWEEN 2023 AND 2026 AND f.canonical_current_A_g>0 AND f.concentration_mol_L>0 AND f.BET_m2_g>0 AND f.cycle_voltage_upper_V>f.cycle_voltage_lower_V AND f.baseline_reference IS NOT NULL AND f.current_mass_basis='two_electrode_total_active_mass' AND NOT EXISTS(SELECT 1 FROM record_blockers b LEFT JOIN blocker_scopes bs USING(record_id,code) WHERE b.record_id=f.legacy_record_id AND b.status='open' AND COALESCE(bs.affects_core7,1)=1);

CREATE VIEW training_ready_3e AS SELECT f.* FROM model_feature_rows f JOIN admission_reviews a USING(endpoint_id) WHERE a.profile='canonical_3e' AND a.status='approved' AND f.system='3E' AND f.method='GCD' AND f.metric_kind='capacitance_retention' AND f.retention_relation='eq' AND f.cycle_count>=1000 AND f.source_year BETWEEN 2023 AND 2026 AND f.canonical_current_A_g>0 AND f.concentration_mol_L>0 AND f.BET_m2_g>0 AND f.cycle_voltage_upper_V>f.cycle_voltage_lower_V AND f.baseline_reference IS NOT NULL AND f.current_mass_basis='working_electrode_active_mass' AND f.reference_electrode IS NOT NULL AND NOT EXISTS(SELECT 1 FROM record_blockers b LEFT JOIN blocker_scopes bs USING(record_id,code) WHERE b.record_id=f.legacy_record_id AND b.status='open' AND COALESCE(bs.affects_core7,1)=1);

CREATE VIEW training_ready_canonical_current AS SELECT e.*,g.group_id AS validation_group_id
 FROM modeling_effective_inputs e JOIN admissions a USING(record_id)
 JOIN validation_group_assignments g USING(record_id)
 JOIN papers p ON p.paper_id=e.paper_id
 WHERE e.system='2E_symmetric' AND e.method='GCD' AND e.metric_kind='capacitance_retention'
 AND e.material_scope IN ('carbon_candidate','carbon_control') AND e.category IN ('A','B')
 AND e.retention_relation='eq' AND e.retention_pct IS NOT NULL
 AND e.cycle_count>=1000 AND e.short_test=0 AND e.conflict=0 AND e.Si_residue_review_required=0
 AND e.current_density_A_g>0 AND e.mass_basis='two_electrode_total_active_mass'
 AND e.electrolyte IN ('CH3COONa','H2SO4','KNO3','KOH','Li2SO4','LiCl','LiTFSI','Na2SO4','sodium_acetate') AND e.concentration_value>0 AND e.concentration_unit IN ('M','mol/L')
 AND e.voltage_lower_V IS NOT NULL AND e.voltage_upper_V>e.voltage_lower_V AND e.BET_m2_g>0
 AND p.year>=2023 AND p.year<=2026
 AND a.status='approved' AND a.eligible=1
 AND a.source_checked=1 AND a.material_checked=1 AND a.protocol_checked=1
 AND a.baseline_checked=1 AND a.mass_basis_checked=1 AND a.independence_checked=1 AND a.freeze_cleared=1
 AND g.review_status='reviewed_available_corpus'
 AND NOT EXISTS(SELECT 1 FROM record_blockers b LEFT JOIN blocker_scopes s USING(record_id,code)
 WHERE b.record_id=e.record_id AND b.status='open' AND COALESCE(s.affects_core7,1)=1);

CREATE VIEW training_ready_pore AS SELECT * FROM training_ready;

CREATE VIEW training_rows_r4 AS SELECT e.record_id,e.cycle_test_id,e.cycle_count,e.retention_pct,e.retention_relation,e.retention_sd_pct,e.metric_kind,e.value_kind,e.material_scope,e.conflict,e.short_test,e.evidence_path,e.evidence_pages_json,e.evidence_locator,e.note,e.legacy_json_flags,e.paper_id,e.material_id,e.system,e.method,e.electrolyte,e.concentration_value,e.concentration_unit,e.current_density_A_g,e.current_density_mA_cm2,e.voltage_lower_V,e.voltage_upper_V,e.mass_basis,e.baseline_json,e.study_group,e.doi,e.category,e.sample_name,e.BET_m2_g,e.total_pore_volume_cm3_g,e.N_at_pct,e.O_at_pct,e.N_wt_pct,e.O_wt_pct,e.mass_loading_mg_cm2,e.Si_residue_review_required,e.pore_unit_review_required,
      e.admission_status AS legacy_admission_status,e.eligible AS legacy_eligible,
      a.profile,a.status AS admission_status,a.eligible,a.caveats_json,
      e.current_density_A_g AS reported_current_A_g,
      CAST(NULL AS REAL) AS canonical_current_A_g,
      'not_uniquely_defined' AS current_denominator_status,
      'author_reported_protocol_descriptor' AS current_input_semantics,
      g.group_id AS validation_group_id,
      1.0 / COUNT(*) OVER(PARTITION BY a.profile,g.group_id) AS source_weight
      FROM modeling_effective_inputs e JOIN profile_admissions_r4 a USING(record_id)
      JOIN validation_group_assignments g USING(record_id) WHERE a.eligible=1;

CREATE VIEW unified_endpoint_inventory AS
 SELECT 'archived' AS lifecycle,record_id AS endpoint_id,doi,system,method,cycle_count,retention_pct,retention_relation,'record_audit_required' AS scientific_status FROM modeling_effective_inputs
 UNION ALL SELECT 'staged',s.endpoint_id,l.doi,s.system,s.method,s.cycle_count,s.retention_pct,s.retention_relation,'staged_no_admission' FROM staged_cycling_evidence s JOIN literature_registry l USING(identity_key) WHERE s.linked_record_id IS NULL;