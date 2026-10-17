CREATE UNIQUE INDEX paper_doi ON papers(lower(doi)) WHERE doi IS NOT NULL AND doi<>'';
CREATE TABLE admissions(
 record_id TEXT PRIMARY KEY REFERENCES cycling_endpoints,status TEXT NOT NULL,
 source_checked INTEGER NOT NULL DEFAULT 0,material_checked INTEGER NOT NULL DEFAULT 0,
 protocol_checked INTEGER NOT NULL DEFAULT 0,baseline_checked INTEGER NOT NULL DEFAULT 0,
 mass_basis_checked INTEGER NOT NULL DEFAULT 0,independence_checked INTEGER NOT NULL DEFAULT 0,
 freeze_cleared INTEGER NOT NULL DEFAULT 0,eligible INTEGER NOT NULL DEFAULT 0 CHECK(eligible IN (0,1)),
 rationale TEXT NOT NULL,
 CHECK(eligible=0 OR (status='approved' AND source_checked=1 AND material_checked=1 AND protocol_checked=1 AND baseline_checked=1 AND mass_basis_checked=1 AND independence_checked=1 AND freeze_cleared=1))
);
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
CREATE TABLE endpoint_features(
 record_id TEXT PRIMARY KEY REFERENCES cycling_endpoints,BET_m2_g REAL,total_pore_volume_cm3_g REAL,
 N_at_pct REAL,O_at_pct REAL,N_wt_pct REAL,O_wt_pct REAL,mass_loading_mg_cm2 REAL,
 Si_residue_review_required INTEGER NOT NULL DEFAULT 0,pore_unit_review_required INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE endpoint_protocol_overrides(record_id TEXT NOT NULL REFERENCES cycling_endpoints,field_name TEXT NOT NULL CHECK(field_name IN ('voltage_lower_V','voltage_upper_V')),value_json TEXT NOT NULL,status TEXT NOT NULL,review_id INTEGER NOT NULL REFERENCES review_events,PRIMARY KEY(record_id,field_name));
CREATE TABLE field_evidence(
 evidence_id INTEGER PRIMARY KEY,record_id TEXT NOT NULL REFERENCES raw_records,field_name TEXT NOT NULL,
 value_json TEXT NOT NULL,source_path TEXT NOT NULL,locator TEXT NOT NULL,status TEXT NOT NULL,
 UNIQUE(record_id,field_name)
);
CREATE TABLE ingestion_sources(path TEXT PRIMARY KEY,sha256 TEXT NOT NULL,role TEXT NOT NULL);
CREATE TABLE issue_resolutions(issue_id INTEGER PRIMARY KEY REFERENCES issues,review_id INTEGER NOT NULL REFERENCES review_events,effective_status TEXT NOT NULL,rationale TEXT NOT NULL);
CREATE TABLE issues(
 issue_id INTEGER PRIMARY KEY,paper_id TEXT REFERENCES papers,record_id TEXT REFERENCES raw_records,
 severity TEXT NOT NULL,code TEXT NOT NULL,description TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'open',
 source_path TEXT,scope TEXT NOT NULL
);
CREATE TABLE material_observations(
 observation_id INTEGER PRIMARY KEY,material_id TEXT NOT NULL REFERENCES materials,
 record_id TEXT NOT NULL REFERENCES raw_records,property_name TEXT NOT NULL,value_json TEXT NOT NULL,
 unit TEXT,method TEXT,stage TEXT NOT NULL,source_path TEXT NOT NULL,locator TEXT NOT NULL,
 provenance_status TEXT NOT NULL
);
CREATE TABLE materials(
 material_id TEXT PRIMARY KEY,paper_id TEXT NOT NULL REFERENCES papers,sample_name TEXT NOT NULL,
 legacy_material_id TEXT NOT NULL,identity_status TEXT NOT NULL DEFAULT 'provisional_within_paper'
);
CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE papers(
 paper_id TEXT PRIMARY KEY,doi TEXT,title TEXT NOT NULL,year INTEGER,category TEXT NOT NULL,
 study_group TEXT NOT NULL,main_format TEXT NOT NULL,main_path TEXT NOT NULL,main_sha256 TEXT NOT NULL,
 archive_restrictions TEXT,independence_status TEXT NOT NULL DEFAULT 'pending_review'
);
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
CREATE TABLE source_relationships(
 relationship_id INTEGER PRIMARY KEY,paper_id TEXT NOT NULL REFERENCES papers,related_paper_id TEXT REFERENCES papers,
 related_doi TEXT,relationship TEXT NOT NULL,status TEXT NOT NULL,note TEXT NOT NULL
);
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
CREATE VIEW primary_screening_candidates AS
 SELECT * FROM endpoint_review
 WHERE system='2E_symmetric' AND method='GCD' AND metric_kind='capacitance_retention'
 AND material_scope IN ('carbon_candidate','carbon_control')
 AND retention_relation='eq' AND retention_pct IS NOT NULL AND cycle_count>=1000
 AND conflict=0 AND short_test=0 AND category IN ('A','B') AND Si_residue_review_required=0;
CREATE VIEW training_ready AS SELECT e.* FROM endpoint_effective_review e
   JOIN admissions a USING(record_id)
   WHERE e.system='2E_symmetric' AND e.method='GCD' AND e.metric_kind='capacitance_retention'
   AND e.material_scope IN ('carbon_candidate','carbon_control') AND e.retention_relation='eq'
   AND e.retention_pct IS NOT NULL AND e.cycle_count>=1000 AND e.conflict=0 AND e.short_test=0
   AND e.category IN ('A','B') AND e.Si_residue_review_required=0
   AND a.eligible=1 AND a.status='approved' AND a.source_checked=1 AND a.material_checked=1
   AND a.protocol_checked=1 AND a.baseline_checked=1 AND a.mass_basis_checked=1
   AND a.independence_checked=1 AND a.freeze_cleared=1
   AND e.current_density_A_g>0 AND e.electrolyte IS NOT NULL AND e.concentration_value>0
   AND e.concentration_unit IS NOT NULL AND e.voltage_lower_V IS NOT NULL AND e.voltage_upper_V>e.voltage_lower_V
   AND NOT EXISTS(SELECT 1 FROM record_blockers b WHERE b.record_id=e.record_id AND b.status='open');