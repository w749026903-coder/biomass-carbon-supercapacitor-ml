"""Explain every preparation gate. Technical/data passes never grant scientific approval."""
from pathlib import Path
import collections,json,sqlite3
R=Path(__file__).resolve().parents[1];O=R/'循环稳定性数据库_v0.5_逐条准入审查_20261018'
def enc(x):return json.dumps(x,ensure_ascii=False)
def main():
 c=sqlite3.connect(O/'cycling_v0_5.sqlite');c.row_factory=sqlite3.Row;c.execute('pragma foreign_keys=ON')
 if c.execute("select count(*) from extraction_run where key='v05_gate_build'").fetchone()[0]:raise RuntimeError('Already built')
 c.executescript('''
 CREATE TABLE record_admission_checks(endpoint_id TEXT REFERENCES model_endpoints,profile TEXT,criterion TEXT,status TEXT CHECK(status IN ('pass','fail','unresolved','not_applicable')),reason TEXT,evidence_json TEXT,PRIMARY KEY(endpoint_id,profile,criterion));
 CREATE TABLE admission_review_history(history_id INTEGER PRIMARY KEY,endpoint_id TEXT REFERENCES model_endpoints,profile TEXT,old_status TEXT,old_reason TEXT,new_status TEXT,new_reason TEXT);
 CREATE TABLE record_gate_outcomes(endpoint_id TEXT REFERENCES model_endpoints,profile TEXT,status TEXT CHECK(status IN ('excluded','pending','approved')),failed_count INTEGER,unresolved_count INTEGER,PRIMARY KEY(endpoint_id,profile));
 CREATE INDEX idx_admission_check_status ON record_admission_checks(profile,criterion,status);
 ''')
 # Ownmethods provides reference,characterizationwindow andloading; does not
 # establish the cycling current mass denominator or cycle-specific window.
 source=c.execute('select * from source_segments where segment_id=4620').fetchone()
 for alias in [f'TE{i:03}' for i in range(14,20)]:
  ep=c.execute("select endpoint_id from endpoint_aliases where namespace='TE' and alias=?",(alias,)).fetchone()[0]
  for field,val,unit in [('reference_electrode','Hg/HgO',None),('characterization_voltage_lower_V',-.8,'V'),('characterization_voltage_upper_V',0,'V'),('mass_loading_mg_cm2',1.8,'mg/cm2')]:
   old=c.execute('select observation_id from field_selection where endpoint_id=? and field_name=?',(ep,field)).fetchone()[0]
   oid=c.execute('insert into field_observations(endpoint_id,field_name,value_json,unit,status,source_id,segment_id,locator,evidence_excerpt,provenance_json) values (?,?,?,?,?,?,?,?,?,?)',(ep,field,enc(val),unit,'own_primary_method_group_applicable_not_cycle_transfer',source['source_id'],source['segment_id'],source['locator'],source['text'],enc({'aliases':'AF-MMTC0/1/3/5/7/9','warning':'Characterizationwindowisnotcyclewindow;massloadingisnotcurrentmassdenominator.'}))).lastrowid
   c.execute('update field_selection set observation_id=? where endpoint_id=? and field_name=?',(oid,ep,field));c.execute('insert into field_selection_history(endpoint_id,field_name,old_observation_id,new_observation_id,reason) values (?,?,?,?,?)',(ep,field,old,oid,'Ownthree-electrodemethodcoverssixAFsamples; noimplicitcyclewindow/currentbasis.'))
 # Add new primary conflict as an additional review, never rewrite old notes.
 c.execute("insert into review_search_audit(scope,expression,result_count,interpretation) values (?,?,?,?)",('doi:10.1007/s10904-026-04338-1','OwnhighlightsPDFp2andbodyPDFp17cyclecurrentcross-check',2,'12A/gv20A/gnewconflict; bothvaluesretainedinfield_observations,selectedcurrentNULL.'))
 # Rebuild only the newversion cache; allselectedobservationsremainjoinable.
 c.execute('delete from model_feature_cache');c.execute('insert into model_feature_cache select * from model_feature_rows')
 c.execute("update feature_cache_meta set value=? where key='selection_history_max_id'",(str(c.execute('select max(selection_id) from field_selection_history').fetchone()[0]),))
 c.execute("update feature_cache_meta set value=? where key='selected_fields'",(str(c.execute('select count(*) from field_selection').fetchone()[0]),))
 for r in c.execute('select * from model_feature_cache order by endpoint_id').fetchall():
  ep=r['endpoint_id'];obs={x['field_name']:dict(x) for x in c.execute('select o.* from field_selection s join field_observations o using(observation_id) where s.endpoint_id=?',(ep,))}
  issues=[dict(x) for x in c.execute('select i.* from extraction_issues i left join extraction_issue_resolutions z using(issue_id) where i.endpoint_id=? and z.issue_id is null',(ep,))]
  blockers=[dict(x) for x in c.execute("select b.*,bs.affects_core7 from record_blockers b left join blocker_scopes bs using(record_id,code) where b.record_id=? and b.status='open' and coalesce(bs.affects_core7,1)=1",(r['legacy_record_id'],))]
  for profile,system,basis in [('canonical_2e','2E_symmetric','two_electrode_total_active_mass'),('canonical_3e','3E','working_electrode_active_mass')]:
   checks=[]
   def ck(criterion,status,reason,fields=(),other=None):
    evidence={'selected_observations':{f:obs[f]['observation_id'] for f in fields if f in obs},'current_values':{f:r[f] for f in fields},'additional':other}
    checks.append((ep,profile,criterion,status,reason,enc(evidence)))
   ck('target_metric','pass' if r['metric_kind']=='capacitance_retention' else 'fail','Requiredcapacitanceretention; capacity/CEcannotbesubstituted.',other={'metric':r['metric_kind']})
   ck('actual_system','unresolved' if r['system'] in (None,'unresolved','not_located') else 'pass' if r['system']==system else 'fail','Mustmatchactualcyclingconfigurationofthisprofile;characterizationdoesnotassignsystem.',other={'system':r['system'],'expected':system})
   ck('actual_method','unresolved' if not r['method'] or r['method'] in ('unresolved','not_located') else 'pass' if r['method']=='GCD' else 'fail','MainprofilesrequireGCD;CVretentionpreservedseparately.',other={'method':r['method']})
   ck('publication_year','unresolved' if r['source_year'] is None else 'pass' if 2023<=r['source_year']<=2026 else 'fail','Currentcontract2023–2026;oldpapersstayavailablebutcannotbeforceadmitted.',other={'year':r['source_year'],'basis':r['year_basis']})
   ck('cycle_horizon','unresolved' if r['cycle_count'] is None else 'pass' if r['cycle_count']>=1000 else 'fail','Atleast1000cycles;shorttestsarenotextendedbyimputation.',['cycle_count'])
   exact=r['retention_relation']=='eq' and not any(k in str(r['value_kind']).lower() for k in ['loss','derived','qualitative','approx'])
   ck('reported_exact_label','unresolved' if r['retention_pct'] is None else 'pass' if exact else 'fail','Exactreportedpointonly;approximate,censored,losscomplementremainreview/sensitivitydata.',['retention_pct','retention_relation','value_kind'])
   ck('reported_cycle_current','pass' if r['reported_current_A_g'] is not None and r['reported_current_A_g']>0 else 'fail' if r['current_mA_cm2'] is not None else 'unresolved','A/gmustbeowncyclingcurrent;arealvaluescannotbeconvertedwithoutmatchingmass.',['reported_current_A_g','current_mA_cm2'])
   ck('physical_current_mass_basis','pass' if r['current_mass_basis']==basis and r['canonical_current_A_g'] is not None and r['canonical_current_A_g']>0 else 'unresolved','Directcurrentnormalizationdefinitionrequired;C=IΔt/(mΔV)alonecannotdefinejmass.',['current_mass_basis','canonical_current_A_g'],{'expected':basis})
   ck('electrolyte_identity','pass' if r['electrolyte'] else 'unresolved','Reportedidentitypresentonly;doesnotclearordinaryaqueousscope.',['electrolyte'])
   ck('molar_concentration','pass' if r['concentration_mol_L'] is not None and r['concentration_mol_L']>0 else 'unresolved','Knownmol/Lrequired;mol/kgandunlocatedvaluesnotconverted.',['concentration_mol_L'])
   ck('cycle_specific_window','pass' if r['cycle_voltage_lower_V'] is not None and r['cycle_voltage_upper_V'] is not None and r['cycle_voltage_upper_V']>r['cycle_voltage_lower_V'] else 'unresolved','Actualcyclingwindowmustbelinked;CV/GCDcharacterizationwindowcannotfillthisgate.',['cycle_voltage_lower_V','cycle_voltage_upper_V'])
   ck('sample_specific_BET','pass' if r['BET_m2_g'] is not None and r['BET_m2_g']>0 else 'unresolved','OwnsampleBETbeforecycling;m2/gandmaterialbindingmustbeunambiguous.',['BET_m2_g'])
   ck('baseline_definition','unresolved','Noadditionalterminalbaselineclearanceinthisreview;initial-capacitancewordingdoesnotestablishconditioningandreferencedcyclebyitself.',['baseline_reference','baseline_cycle'])
   ck('reference_electrode','not_applicable' if profile=='canonical_2e' else 'pass' if r['reference_electrode'] else 'unresolved','Three-electrodeprofilemustretainreferenceidentity.',['reference_electrode'])
   ck('material_and_electrolyte_scope_clearance','unresolved','Precursor,purecarbon/composite/Siresidue,aqueous/gel/DESandown-materialbindingrequireterminalreview;nonemptyscopeflagsareretained,notautocleared.',['scope_flags'],{'sample':r['sample_name'],'identity':r['identity_key']})
   ck('open_scientific_holds','unresolved' if issues or blockers else 'pass','Noopenholdisclearedbynewversion,Gitormachineextraction.',other={'issues':issues,'legacy_blockers':blockers})
   ck('source_independence_clearance','unresolved','Samepaperremainssamegroup;possiblepreviouswork/sharedprecursor/sharedcurveareunresolveduntilterminalreview.',other={'source_group':r['source_group'],'material_id':r['material_id'],'test_id':r['test_id']})
   ck('terminal_source_review','unresolved','Full record-level protocol and provenance review remains incomplete. Training permission is separate from dataset admission.')
   c.executemany('insert into record_admission_checks values (?,?,?,?,?,?)',checks)
   statuses=collections.Counter(x[3] for x in checks);outcome='excluded' if statuses['fail'] else 'pending'
   reason=f"v0.5explicitgates: {statuses['fail']}failed,{statuses['unresolved']}unresolved; see record_admission_checks. Noapproval."
   old=c.execute('select status,reason from admission_reviews where endpoint_id=? and profile=?',(ep,profile)).fetchone()
   c.execute('insert into admission_review_history(endpoint_id,profile,old_status,old_reason,new_status,new_reason) values (?,?,?,?,?,?)',(ep,profile,old['status'],old['reason'],outcome,reason))
   c.execute('update admission_reviews set status=?,reason=? where endpoint_id=? and profile=?',(outcome,reason,ep,profile))
   c.execute('insert into record_gate_outcomes values (?,?,?,?,?)',(ep,profile,outcome,statuses['fail'],statuses['unresolved']))
 # Strictexports require everyapplicablecheckpassplusapprovedreview; absence
 # ofchecks cannot be treatedaspass. Oldstrictviewsretainedin SQLhistory.
 c.executescript('''
 CREATE TABLE prior_admission_view_sql(name TEXT PRIMARY KEY,sql TEXT);
 INSERT INTO prior_admission_view_sql SELECT name,sql FROM sqlite_master WHERE name IN ('training_ready_2e','training_ready_3e');
 DROP VIEW training_ready_2e;
 DROP VIEW training_ready_3e;
 CREATE VIEW training_ready_2e AS SELECT f.* FROM model_feature_rows f JOIN admission_reviews a USING(endpoint_id) JOIN record_gate_outcomes o ON o.endpoint_id=f.endpoint_id AND o.profile=a.profile WHERE a.profile='canonical_2e' AND a.status='approved' AND o.status='approved' AND (SELECT count(*) FROM record_admission_checks q WHERE q.endpoint_id=f.endpoint_id AND q.profile=a.profile)=18 AND NOT EXISTS(SELECT 1 FROM record_admission_checks q WHERE q.endpoint_id=f.endpoint_id AND q.profile=a.profile AND q.status NOT IN ('pass','not_applicable'));
 CREATE VIEW training_ready_3e AS SELECT f.* FROM model_feature_rows f JOIN admission_reviews a USING(endpoint_id) JOIN record_gate_outcomes o ON o.endpoint_id=f.endpoint_id AND o.profile=a.profile WHERE a.profile='canonical_3e' AND a.status='approved' AND o.status='approved' AND (SELECT count(*) FROM record_admission_checks q WHERE q.endpoint_id=f.endpoint_id AND q.profile=a.profile)=18 AND NOT EXISTS(SELECT 1 FROM record_admission_checks q WHERE q.endpoint_id=f.endpoint_id AND q.profile=a.profile AND q.status NOT IN ('pass','not_applicable'));
 CREATE VIEW v05_relevant_admission AS SELECT r.*,o.profile,o.status AS preparation_gate_status,o.failed_count,o.unresolved_count FROM model_feature_cache r JOIN record_gate_outcomes o USING(endpoint_id) WHERE (r.system='3E' AND o.profile='canonical_3e') OR (r.system='2E_symmetric' AND o.profile='canonical_2e');
 ''')
 c.execute('insert into extraction_run values (?,?)',('v05_gate_build',enc({'checks':c.execute('select count(*) from record_admission_checks').fetchone()[0],'training_authorized':False})));c.commit()
 print(enc({'records':c.execute('select count(*) from model_endpoints').fetchone()[0],'checks':c.execute('select count(*) from record_admission_checks').fetchone()[0],'ready_2e':c.execute('select count(*) from training_ready_2e').fetchone()[0],'ready_3e':c.execute('select count(*) from training_ready_3e').fetchone()[0]}));c.close()
if __name__=='__main__':main()
