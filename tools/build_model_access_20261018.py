"""Finalize read-only data access structures. No model fit, no original data overwrite."""
from pathlib import Path
import hashlib,json,re,sqlite3
R=Path(__file__).resolve().parents[1];O=R/'循环稳定性数据库_v0.4_提取与调用_20261018'
def enc(x):return json.dumps(x,ensure_ascii=False)
def main():
 c=sqlite3.connect(O/'cycling_v0_4.sqlite');c.row_factory=sqlite3.Row;c.execute('pragma foreign_keys=ON')
 if c.execute("select count(*) from extraction_run where key='access_cache_built'").fetchone()[0]:raise RuntimeError('Access structures already finalized')
 def put(ep,f,v,unit,status,provenance,reason):
  old=c.execute('select observation_id from field_selection where endpoint_id=? and field_name=?',(ep,f)).fetchone();oid=c.execute('insert into field_observations(endpoint_id,field_name,value_json,unit,status,locator,evidence_excerpt,provenance_json) values (?,?,?,?,?,?,?,?)',(ep,f,enc(v),unit,status,provenance['locator'],enc(provenance.get('measurement')),enc(provenance))).lastrowid;c.execute('insert or replace into field_selection values (?,?,?)',(ep,f,oid));c.execute('insert into field_selection_history(endpoint_id,field_name,old_observation_id,new_observation_id,reason) values (?,?,?,?,?)',(ep,f,old[0] if old else None,oid,reason))
 for ob in c.execute("select * from literature_observations where batch='B20'").fetchall():
  x=json.loads(ob['source_json'])
  for i,m in enumerate(x.get('measurements',[]),1):
   a=c.execute("select endpoint_id from endpoint_aliases where namespace='B20' and alias=?",(x['candidate_id']+':'+str(i),)).fetchone()
   if not a:continue
   ep=a[0];provenance={'path':'同体系文献补充_第二批_20261017/候选文献审核表.json','locator':x['candidate_id']+f'.measurements[{i-1}]','measurement':m,'status':'prior_curated_claim_not_primary_source_reaudit'}
   current=m.get('cycling_current_reported','');mat=re.fullmatch(r'\s*([\d.]+)\s*A\s*/\s*g\s*',current)
   if mat:put(ep,'reported_current_A_g',float(mat[1]),'A/g','prior_candidate_report_descriptor',provenance,'Parse only an explicit single A/g candidate string; never infer the physical denominator.')
   elec=m.get('electrolyte','');match=re.fullmatch(r'\s*([\d.]+)\s*(M|mol/L|mM)\s+([A-Za-z0-9]+)\s*',elec)
   if match:
    val=float(match[1])/(1000 if match[2]=='mM' else 1);put(ep,'electrolyte',match[3],None,'prior_candidate_protocol',provenance,'Candidate condition retained as unreviewed primary binding.');put(ep,'concentration_mol_L',val,'mol/L','prior_candidate_protocol',provenance,'Only explicit M/mol/L/mM unit normalization; no mol/kg or mass-fraction conversion.')
   if x['candidate_id']=='B2_018':
    # Replace a historical numeric100 claim with its actual qualitative interpretation.
    put(ep,'retention_pct',None,'%', 'qualitative_near100_no_exact_numeric_label',provenance,'Historical candidate table explicitly says near_100_qualitative; no numeric100 target.');put(ep,'retention_relation','qualitative',None,'qualified_prior_claim',provenance,'Unresolved2E/3E; retained as a review claim.')
   if x['candidate_id']=='B2_013':
    temp=-60 if '60' in m['sample'] else 100;put(ep,'temperature_C',temp,'degC','prior_candidate_protocol',provenance,'Explicit candidate test temperature; same material, different test conditions.')
 # Material identity correction: these are two temperatures of the sameHPC-KCO, not two materials.
 c.execute('CREATE TABLE material_identity_aliases(old_material_id TEXT PRIMARY KEY REFERENCES model_materials,canonical_material_id TEXT REFERENCES model_materials,reason TEXT NOT NULL)')
 eps=c.execute("select e.* from model_endpoints e join endpoint_aliases a using(endpoint_id) where a.namespace='B20' and a.alias like 'B2_013:%'").fetchall()
 if eps:
  identity=eps[0]['identity_key'];mid='material:'+hashlib.sha256(enc((identity,'hpckco')).encode()).hexdigest()[:24];c.execute('insert into model_materials values (?,?,?,?,NULL)',(mid,identity,'HPC-KCO','same_material_two_temperature_tests_pending_primary_audit'))
  for e in eps:
   c.execute('insert into material_identity_aliases values (?,?,?)',(e['material_id'],mid,'B2_013 hasHPC-KCO at−60 and100degC; temperatures are test metadata, not independent materials.'));c.execute('update model_tests set material_id=? where test_id=?',(mid,e['test_id']));c.execute('update model_endpoints set material_id=? where endpoint_id=?',(mid,e['endpoint_id']));c.execute("update model_materials set identity_status='superseded_label_kept_as_alias_history' where material_id=?",(e['material_id'],))
 # Build a complete inspectable projection, then an indexed cache checked for staleness by the API.
 fields=[x[0] for x in c.execute('select distinct field_name from field_selection order by field_name')];c.execute('DROP VIEW model_feature_rows');cols=[]
 for f in fields:
  if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*',f):raise RuntimeError('Unsafe field name')
  cols += [f"MAX(CASE WHEN o.field_name='{f}' THEN json_extract(o.value_json,'$') END) AS {f}",f"MAX(CASE WHEN o.field_name='{f}' THEN o.status END) AS {f}_status"]
 c.execute('CREATE VIEW model_feature_rows AS SELECT e.*,m.sample_name,t.system,t.method,t.curve_group,'+','.join(cols)+' FROM model_endpoints e JOIN model_materials m USING(material_id) JOIN model_tests t USING(test_id) JOIN field_selection s USING(endpoint_id) JOIN field_observations o ON o.observation_id=s.observation_id GROUP BY e.endpoint_id')
 c.execute('CREATE TABLE model_feature_cache AS SELECT * FROM model_feature_rows');c.executescript('CREATE UNIQUE INDEX idx_feature_cache_endpoint ON model_feature_cache(endpoint_id);CREATE INDEX idx_feature_cache_system_year ON model_feature_cache(system,source_year);CREATE INDEX idx_feature_cache_group ON model_feature_cache(source_group);CREATE INDEX idx_feature_cache_identity ON model_feature_cache(identity_key);CREATE TABLE feature_cache_meta(key TEXT PRIMARY KEY,value TEXT);')
 for k,v in {'selection_history_max_id':c.execute('select max(selection_id) from field_selection_history').fetchone()[0],'selected_fields':c.execute('select count(*) from field_selection').fetchone()[0]}.items():c.execute('insert into feature_cache_meta values (?,?)',(k,str(v)))
 contract={'schema':'local-training-data-access-v1','database_file':'cycling_v0_4.sqlite','parent':'../循环稳定性数据库_v0.3_合并版_20261017/cycling_v0_3_merged.sqlite','target':'capacitance_retention_pct_at_requested_cycle_count_and_conditions','research_training_authorized':False,'priority_system':'3E','read_only_api':True,'core_features':['cycle_count','canonical_current_A_g','electrolyte','concentration_mol_L','cycle_voltage_lower_V','cycle_voltage_upper_V','BET_m2_g'],'optional_features':['total_pore_volume_cm3_g'],'reported_protocol_current':'reported_current_A_g','forbidden_predictors':['endpoint_id','identity_key','material_id','test_id','source_group','source_year','sample_name','retention_pct','retention_relation','workflow_status','post_cycle_EIS','post_cycle_XPS'],'profiles':{'strict_2e':'training_ready_2e','strict_3e':'training_ready_3e','review_3e':'53 prioritized evidence records; pending admission','all_review':'mixed systems for review only','proposal_2e':'inherited exact reported-protocol8; unknown physical current denominator'},'missingness':'NULL remains unknown; field status distinguishes unreviewed, not located, conflicting, qualitative and derived','voltage_rule':'characterization windows are not substituted for cycle-specific windows','source_group_rule':'same-paper samples/currents/electrolytes/horizons stay together; known inherited cross-paper groups retained; new-source grouping not independence clearance','strict_admission':'No new approvals; records must pass own-source identity, material/scope, exact label, actual cycle conditions, current denominator, baseline and source-independence review. Existing freezes preserved.'}
 (O/'data_contract.json').write_text(json.dumps(contract,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');c.execute('insert into extraction_run values (?,?)',('access_cache_built','true'));c.commit();print(enc({'cached_rows':c.execute('select count(*) from model_feature_cache').fetchone()[0],'fields':len(fields),'active_materials':c.execute('select count(distinct material_id) from model_endpoints').fetchone()[0],'tests':c.execute('select count(distinct test_id) from model_endpoints').fetchone()[0]}));c.close()
if __name__=='__main__':main()
