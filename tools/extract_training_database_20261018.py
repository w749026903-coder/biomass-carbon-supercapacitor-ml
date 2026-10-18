"""Normalize existing curated measurements; preserve all legacy rows and source evidence."""
from pathlib import Path
import collections,hashlib,json,re,sqlite3,unicodedata,xml.etree.ElementTree as ET
R=Path(__file__).resolve().parents[1];O=R/'循环稳定性数据库_v0.4_提取与调用_20261018'
def enc(x):return json.dumps(x,ensure_ascii=False)
def norm(x):return ''.join(v for v in unicodedata.normalize('NFKC',str(x or '')).casefold() if v.isalnum())
def key(*xs):return hashlib.sha256(enc(xs).encode()).hexdigest()[:24]
def main():
 c=sqlite3.connect(O/'cycling_v0_4.sqlite');c.row_factory=sqlite3.Row;c.execute('pragma foreign_keys=ON')
 
 if c.execute("select count(*) from sqlite_master where name='model_endpoints'").fetchone()[0] and c.execute('select count(*) from model_endpoints').fetchone()[0]:raise RuntimeError('Normalized rows already exist; do not duplicate')
 c.executescript('''
 CREATE TABLE IF NOT EXISTS model_materials(material_id TEXT PRIMARY KEY,identity_key TEXT REFERENCES literature_registry,sample_name TEXT,identity_status TEXT NOT NULL,legacy_material_id TEXT);
 CREATE TABLE IF NOT EXISTS model_tests(test_id TEXT PRIMARY KEY,material_id TEXT REFERENCES model_materials,system TEXT,method TEXT,curve_group TEXT,protocol_status TEXT NOT NULL,legacy_test_id TEXT);
 CREATE TABLE IF NOT EXISTS model_endpoints(endpoint_id TEXT PRIMARY KEY,identity_key TEXT REFERENCES literature_registry,material_id TEXT REFERENCES model_materials,test_id TEXT REFERENCES model_tests,metric_kind TEXT NOT NULL,source_group TEXT NOT NULL,source_year INTEGER,year_basis TEXT,workflow_status TEXT NOT NULL,legacy_record_id TEXT REFERENCES cycling_endpoints);
 CREATE TABLE IF NOT EXISTS endpoint_aliases(namespace TEXT,alias TEXT,endpoint_id TEXT REFERENCES model_endpoints,PRIMARY KEY(namespace,alias));
 CREATE TABLE IF NOT EXISTS field_observations(observation_id INTEGER PRIMARY KEY,endpoint_id TEXT REFERENCES model_endpoints,field_name TEXT,value_json TEXT NOT NULL,unit TEXT,status TEXT NOT NULL,source_id TEXT REFERENCES document_sources,segment_id INTEGER REFERENCES source_segments,locator TEXT,evidence_excerpt TEXT,provenance_json TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS field_selection(endpoint_id TEXT REFERENCES model_endpoints,field_name TEXT,observation_id INTEGER REFERENCES field_observations,PRIMARY KEY(endpoint_id,field_name));
 CREATE TABLE IF NOT EXISTS field_selection_history(selection_id INTEGER PRIMARY KEY,endpoint_id TEXT REFERENCES model_endpoints,field_name TEXT,old_observation_id INTEGER REFERENCES field_observations,new_observation_id INTEGER REFERENCES field_observations,reason TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS material_properties(property_id INTEGER PRIMARY KEY,material_id TEXT REFERENCES model_materials,property_name TEXT,reported_value TEXT,numeric_value REAL,unit TEXT,stage TEXT,method TEXT,status TEXT,source_id TEXT REFERENCES document_sources,segment_id INTEGER REFERENCES source_segments,locator TEXT,raw_row_json TEXT);
 CREATE TABLE IF NOT EXISTS extraction_issues(issue_id INTEGER PRIMARY KEY,endpoint_id TEXT REFERENCES model_endpoints,identity_key TEXT REFERENCES literature_registry,field_name TEXT,code TEXT,status TEXT,evidence_json TEXT,reason TEXT);
 CREATE TABLE IF NOT EXISTS admission_reviews(endpoint_id TEXT REFERENCES model_endpoints,profile TEXT,status TEXT NOT NULL CHECK(status IN ('pending','approved','excluded')),reason TEXT NOT NULL,PRIMARY KEY(endpoint_id,profile));
 CREATE TABLE IF NOT EXISTS candidate_measurement_claims(claim_id INTEGER PRIMARY KEY,identity_key TEXT REFERENCES literature_registry,batch TEXT,local_id TEXT,raw_json TEXT,status TEXT NOT NULL);
 CREATE INDEX IF NOT EXISTS idx_model_endpoints_identity ON model_endpoints(identity_key);
 CREATE INDEX IF NOT EXISTS idx_model_endpoints_group ON model_endpoints(source_group);
 CREATE INDEX IF NOT EXISTS idx_tests_system ON model_tests(system,method);
 CREATE INDEX IF NOT EXISTS idx_field_observations_endpoint ON field_observations(endpoint_id,field_name);
 CREATE INDEX IF NOT EXISTS idx_field_source ON field_observations(source_id,segment_id);
 CREATE INDEX IF NOT EXISTS idx_alias_endpoint ON endpoint_aliases(endpoint_id);
 CREATE INDEX IF NOT EXISTS idx_admission_profile ON admission_reviews(profile,status);
 ''')
 fields={'cycle_count':None,'retention_pct':'%','retention_relation':None,'value_kind':None,'reported_current_A_g':'A/g','current_mA_cm2':'mA/cm2','canonical_current_A_g':'A/g','current_mass_basis':None,'electrolyte':None,'concentration_mol_L':'mol/L','cycle_voltage_lower_V':'V','cycle_voltage_upper_V':'V','characterization_voltage_lower_V':'V','characterization_voltage_upper_V':'V','reference_electrode':None,'BET_m2_g':'m2/g','total_pore_volume_cm3_g':'cm3/g','mass_loading_mg_cm2':'mg/cm2','baseline_reference':None,'baseline_cycle':None,'N_at_pct':'at%','O_at_pct':'at%','scope_flags':None}
 def select(ep,f,value,status,source=None,segment=None,locator='',excerpt='',provenance=None,reason='Initial normalized observation; no admission implied.'):
  old=c.execute('select observation_id from field_selection where endpoint_id=? and field_name=?',(ep,f)).fetchone()
  cur=c.execute('insert into field_observations(endpoint_id,field_name,value_json,unit,status,source_id,segment_id,locator,evidence_excerpt,provenance_json) values (?,?,?,?,?,?,?,?,?,?)',(ep,f,enc(value),fields.get(f),status,source,segment,locator,excerpt,enc(provenance or {})));oid=cur.lastrowid
  c.execute('insert or replace into field_selection values (?,?,?)',(ep,f,oid));c.execute('insert into field_selection_history(endpoint_id,field_name,old_observation_id,new_observation_id,reason) values (?,?,?,?,?)',(ep,f,old[0] if old else None,oid,reason));return oid
 def identity_for_paper(pid):return c.execute("select identity_key from literature_aliases where batch='archived_126' and local_id=?",(pid,)).fetchone()[0]
 def year(identity):
  for x in c.execute('select batch,source_json from literature_observations where identity_key=? order by case batch when "archived_126" then 0 when "B20" then 1 else 2 end',(identity,)):
   d=json.loads(x['source_json'])
   if isinstance(d.get('year'),int):return d['year'],'existing_verified_bibliography:'+x['batch']
   dates=d.get('bibliography',{}).get('dates',[]);ys=[int(t['date_components']['year']) for t in dates if isinstance(t,dict) and t.get('date_components',{}).get('year')]
   if ys:return min(ys),'publisher_deposited_bibliographic_dates'
  # Read publication metadata, never infer publication year from PDF creation time or references.
  paths=c.execute("select l.path from paper_documents p join document_sources d using(source_id) join document_locations l using(source_id) where p.identity_key=? and d.format='xml' and p.role='main'",(identity,)).fetchall()
  for path, in paths:
   q=Path(path);q=q if q.is_absolute() else R/q;root=ET.parse(q).getroot();ys=[int(e.text) for e in root.findall('.//article-meta/pub-date/year') if e.text and e.text.isdigit()]
   if ys:return min(ys),'XML article-meta/pub-date/year'
  return None,'not_located_do_not_guess'
 def material(identity,sample,old=None):
  mid='legacy_material:'+old if old else 'material:'+key(identity,norm(sample))
  c.execute('insert or ignore into model_materials values (?,?,?,?,?)',(mid,identity,sample,'inherited_identity_review_limits' if old else 'candidate_identity_pending',old));return mid
 def endpoint(ep,identity,sample,system,method,values,namespace,alias,legacy=None,source=None,locator='',status='prior_curated_candidate_not_newly_admitted'):
  if c.execute('select 1 from model_endpoints where endpoint_id=?',(ep,)).fetchone():c.execute('insert or ignore into endpoint_aliases values (?,?,?)',(namespace,alias,ep));return ep
  mid=material(identity,sample,legacy['material_id'] if legacy else None);tid='legacy_test:'+legacy['cycle_test_id'] if legacy else 'test:'+key(mid,system,method,values.get('electrolyte'),values.get('concentration_mol_L'),values.get('reported_current_A_g'))
  c.execute('insert or ignore into model_tests values (?,?,?,?,?,?,?)',(tid,mid,system,method,tid,'conditions_require_record_review',legacy['cycle_test_id'] if legacy else None));y,yb=year(identity);gid=c.execute('select group_id from unified_source_groups where identity_key=?',(identity,)).fetchone()[0]
  c.execute('insert into model_endpoints values (?,?,?,?,?,?,?,?,?,?)',(ep,identity,mid,tid,'capacitance_retention',gid,y,yb,'extracted_candidate_not_admitted',legacy['record_id'] if legacy else None));c.execute('insert into endpoint_aliases values (?,?,?)',(namespace,alias,ep))
  for f in fields:select(ep,f,values.get(f),status if values.get(f) is not None else 'not_yet_located_or_reviewed',source,locator=locator,provenance={'namespace':namespace,'alias':alias})
  for profile in ['canonical_2e','canonical_3e']:c.execute('insert into admission_reviews values (?,?,?,?)',(ep,profile,'pending','No new scientific admission. Current denominator, applicable scope, baseline, source independence, field evidence and freezes require record review.'))
  return ep
 match={}
 for x in c.execute('select * from modeling_effective_inputs').fetchall():
  d=dict(x);identity=identity_for_paper(d['paper_id']);sid=next((s[0] for s in c.execute('select source_id from document_locations where path=?',(d['evidence_path'],))),None)
  cv=d['concentration_value'];unit=d['concentration_unit'];cv=cv if unit in ('M','mol/L') else cv/1000 if unit=='mM' and cv is not None else None
  vals={'cycle_count':d['cycle_count'],'retention_pct':d['retention_pct'],'retention_relation':d['retention_relation'],'value_kind':d['value_kind'],'reported_current_A_g':d['current_density_A_g'],'current_mA_cm2':d['current_density_mA_cm2'],'canonical_current_A_g':d['current_density_A_g'] if d['mass_basis']=='two_electrode_total_active_mass' else None,'current_mass_basis':d['mass_basis'],'electrolyte':d['electrolyte'],'concentration_mol_L':cv,'cycle_voltage_lower_V':d['voltage_lower_V'],'cycle_voltage_upper_V':d['voltage_upper_V'],'BET_m2_g':d['BET_m2_g'],'total_pore_volume_cm3_g':d['total_pore_volume_cm3_g'],'mass_loading_mg_cm2':d['mass_loading_mg_cm2'],'baseline_reference':json.loads(d['baseline_json']) if d['baseline_json'] else None,'N_at_pct':d['N_at_pct'],'O_at_pct':d['O_at_pct']}
  ep='legacy:'+d['record_id'];endpoint(ep,identity,d['sample_name'],d['system'],d['method'],vals,'legacy',d['record_id'],legacy=d,source=sid,locator=d['evidence_locator'],status='inherited_effective_value_original_review_limits_preserved')
  # Preserve explicit field-ledger references even when its original status is incomplete.
  for f in c.execute('select * from current_field_evidence where record_id=?',(d['record_id'],)).fetchall():
   fmap={'current_density_A_g':'reported_current_A_g','concentration_value':'concentration_mol_L','voltage_lower_V':'cycle_voltage_lower_V','voltage_upper_V':'cycle_voltage_upper_V'};ff=fmap.get(f['field_name'],f['field_name'])
   if ff not in fields:continue
   data=json.loads(f['provenance_json']);ledger=data['ledger'];evidence=data['matching_reviews'];v=vals.get(ff)
   select(ep,ff,v,'inherited_review_linked' if evidence else 'inherited_ledger_status:'+f['ledger_status'],locator=ledger['locator'],provenance=data,reason='Attach inherited field evidence without changing its admission or scientific interpretation.')
  match[(identity,norm(d['sample_name']),d['system'],d['method'],d['cycle_count'],d['retention_pct'],d['retention_relation'])]=ep
 for x in c.execute('select * from staged_cycling_evidence').fetchall():
  d=json.loads(x['evidence_json']);ep='legacy:'+x['linked_record_id'] if x['linked_record_id'] else 'candidate:'+d['endpoint_id'];vals={'cycle_count':d['cycle_count'],'retention_pct':d['retention_pct'],'retention_relation':d['retention_relation'],'value_kind':d['value_kind'],'reported_current_A_g':d['reported_current_A_g'],'current_mA_cm2':d['reported_current_other']['value'] if d.get('reported_current_other') else None,'current_mass_basis':'not_finalized','electrolyte':d['electrolyte'],'concentration_mol_L':d['concentration_mol_L'],'scope_flags':d['scope_flags']}
  endpoint(ep,x['identity_key'],d['sample'],d['system'],d['cycle_method'],vals,'TE',d['endpoint_id'],source=d['source_sha256'],locator=d['locator'])
  match[(x['identity_key'],norm(d['sample']),d['system'],d['cycle_method'],d['cycle_count'],d['retention_pct'],d['retention_relation'])]=ep
  # Linked old endpoints still retain the second observation as evidence, without changing selection.
  if x['linked_record_id']:
   for f in ['cycle_count','retention_pct','reported_current_A_g','concentration_mol_L']:
    c.execute('insert into field_observations(endpoint_id,field_name,value_json,unit,status,source_id,locator,provenance_json) values (?,?,?,?,?,?,?,?)',(ep,f,enc(vals.get(f)),fields[f],'linked_TE_observation_not_preferred_by_recency',d['source_sha256'],d['locator'],enc(d)))
 for ob in c.execute("select * from literature_observations where batch in ('B20','B50')").fetchall():
  x=json.loads(ob['source_json']);c.execute('insert into candidate_measurement_claims(identity_key,batch,local_id,raw_json,status) values (?,?,?,?,?)',(ob['identity_key'],ob['batch'],ob['local_id'],ob['source_json'],'prior_candidate_claims_not_terminal_source_review'))
  if ob['batch']!='B20':continue
  for i,m in enumerate(x.get('measurements',[]),1):
   relation='approx' if 'approx' in str(m.get('retention_kind')) else 'eq';N=m.get('cycles');ret=m.get('retention_percent');system=m.get('system','unresolved');method=m.get('method','unresolved');sample=m.get('sample','unresolved')
   if not isinstance(N,(int,float)) or not isinstance(ret,(int,float)):continue
   alias=x['candidate_id']+':'+str(i);lookup=(ob['identity_key'],norm(sample),system,method,N,ret,relation);ep=match.get(lookup,'candidate:B20:'+alias)
   vals={'cycle_count':N,'retention_pct':ret,'retention_relation':relation,'value_kind':m.get('retention_kind'),'baseline_reference':m.get('baseline') if m.get('baseline') not in ('not_located',None) else None}
   endpoint(ep,ob['identity_key'],sample,system,method,vals,'B20',alias,locator=m.get('location',''))
 # Each wide value remains joined to its selected observation ID, not an untraceable overwrite.
 cols=[]
 for f in fields:
  cols.append("MAX(CASE WHEN o.field_name='"+f+"' THEN json_extract(o.value_json,'$') END) AS "+f)
  cols.append("MAX(CASE WHEN o.field_name='"+f+"' THEN o.status END) AS "+f+'_status')
 c.execute('CREATE VIEW model_feature_rows AS SELECT e.*,m.sample_name,t.system,t.method,t.curve_group,'+','.join(cols)+' FROM model_endpoints e JOIN model_materials m USING(material_id) JOIN model_tests t USING(test_id) JOIN field_selection s USING(endpoint_id) JOIN field_observations o ON o.observation_id=s.observation_id GROUP BY e.endpoint_id')
 c.execute("CREATE VIEW review_3e_rows AS SELECT f.* FROM model_feature_rows f WHERE EXISTS(SELECT 1 FROM endpoint_aliases a WHERE a.endpoint_id=f.endpoint_id AND a.namespace='TE')")
 for name,system,profile in [('training_ready_2e','2E_symmetric','canonical_2e'),('training_ready_3e','3E','canonical_3e')]:
  c.execute(f"CREATE VIEW {name} AS SELECT f.* FROM model_feature_rows f JOIN admission_reviews a USING(endpoint_id) WHERE a.profile='{profile}' AND a.status='approved' AND f.system='{system}' AND f.method='GCD' AND f.metric_kind='capacitance_retention' AND f.retention_relation='eq' AND f.cycle_count>=1000 AND f.source_year BETWEEN 2023 AND 2026 AND f.canonical_current_A_g>0 AND f.concentration_mol_L>0 AND f.BET_m2_g>0 AND f.cycle_voltage_upper_V>f.cycle_voltage_lower_V AND f.baseline_reference IS NOT NULL")
 c.execute("update extraction_run set value_json=? where key='phase'",(enc('normalized_curated_data'),));c.commit();print(enc({'endpoints':c.execute('select count(*) from model_endpoints').fetchone()[0],'3E_priority_rows':c.execute('select count(*) from review_3e_rows').fetchone()[0],'B20_aliases':c.execute("select count(*) from endpoint_aliases where namespace='B20'").fetchone()[0],'observations':c.execute('select count(*) from field_observations').fetchone()[0]}));c.close()
if __name__=='__main__':main()
