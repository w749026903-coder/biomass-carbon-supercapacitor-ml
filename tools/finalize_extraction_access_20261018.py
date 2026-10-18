"""Apply final access-contract metadata to the new extraction version only."""
from pathlib import Path
import json,sqlite3
R=Path(__file__).resolve().parents[1];O=R/'循环稳定性数据库_v0.4_提取与调用_20261018'
def main():
 c=sqlite3.connect(O/'cycling_v0_4.sqlite');c.row_factory=sqlite3.Row;c.execute('pragma foreign_keys=ON')
 # Re-expose inherited restrictions and baseline evidence when rebuilding a NEW version.
 if not c.execute("select 1 from extraction_run where key='legacy_scope_and_baseline_indexed'").fetchone():
  def attach(ep,field,value,provenance,locator,status):
   old=c.execute('select observation_id from field_selection where endpoint_id=? and field_name=?',(ep,field)).fetchone();oid=c.execute('insert into field_observations(endpoint_id,field_name,value_json,status,locator,provenance_json) values (?,?,?,?,?,?)',(ep,field,json.dumps(value,ensure_ascii=False),status,locator,json.dumps(provenance,ensure_ascii=False))).lastrowid;c.execute('insert or replace into field_selection values (?,?,?)',(ep,field,oid));c.execute('insert into field_selection_history(endpoint_id,field_name,old_observation_id,new_observation_id,reason) values (?,?,?,?,?)',(ep,field,old[0] if old else None,oid,'Expose inherited scope/baseline evidence without changing scientific admission or inventing missing values.'))
  for x in c.execute('select * from modeling_effective_inputs').fetchall():
   flags={k:x[k] for k in ['material_scope','category','Si_residue_review_required','pore_unit_review_required','conflict','short_test']};attach('legacy:'+x['record_id'],'scope_flags',flags,dict(x),'Inherited modeling_effective_inputs record '+x['record_id'],'inherited_scope_and_freezes_retained')
  for x in c.execute("select b.*,e.endpoint_id from current_baseline_evidence b join model_endpoints e on e.legacy_record_id=b.record_id where b.legacy_baseline_json is null and b.status like 'reported_reference%' ").fetchall():
   data=json.loads(x['review_evidence_json']);values=[v for v in data.get('review_events',[])+data.get('domain_reviews_r4',[]) if v.get('value_json') and json.loads(v['value_json']) is not None]
   if values:attach(x['endpoint_id'],'baseline_reference',json.loads(values[-1]['value_json']),data,'current_baseline_evidence '+x['record_id'],'inherited_reviewed_reference_exact_cycle_still_unknown')
  c.execute('insert into extraction_run values (?,?)',('legacy_scope_and_baseline_indexed','true'))
 # Explicit mask status for the two printedm3/g pore values; original numbers remain observations.
 if not c.execute("select 1 from extraction_run where key='unit_masks_indexed'").fetchone():
  for alias in ['TE033','TE034']:
   ep=c.execute("select endpoint_id from endpoint_aliases where namespace='TE' and alias=?",(alias,)).fetchone()[0];src=c.execute("select o.* from field_selection f join field_observations o using(observation_id) where f.endpoint_id=? and f.field_name='raw_total_pore_volume_m3_g'",(ep,)).fetchone();old=c.execute("select observation_id from field_selection where endpoint_id=? and field_name='total_pore_volume_cm3_g'",(ep,)).fetchone()[0]
   oid=c.execute('insert into field_observations(endpoint_id,field_name,value_json,unit,status,source_id,segment_id,locator,evidence_excerpt,provenance_json) values (?,?,?,?,?,?,?,?,?,?)',(ep,'total_pore_volume_cm3_g','null','cm3/g','printed_unit_conflict_canonical_withheld',src['source_id'],src['segment_id'],src['locator'],src['evidence_excerpt'],json.dumps({'raw_field':'raw_total_pore_volume_m3_g','reason':'Printedm3/g cannot be silently rewritten ascm3/g'}))).lastrowid;c.execute("update field_selection set observation_id=? where endpoint_id=? and field_name='total_pore_volume_cm3_g'",(oid,ep));c.execute('insert into field_selection_history(endpoint_id,field_name,old_observation_id,new_observation_id,reason) values (?,?,?,?,?)',(ep,'total_pore_volume_cm3_g',old,oid,'Expose already-known printed-unit hold in the feature status as well as in the issue table.'))
  c.execute('insert into extraction_run values (?,?)',('unit_masks_indexed','true'))
 for name,basis,ref in [('training_ready_2e','two_electrode_total_active_mass',False),('training_ready_3e','working_electrode_active_mass',True)]:
  sql=c.execute('select sql from sqlite_master where name=?',(name,)).fetchone()[0]
  if "f.current_mass_basis=" not in sql:
   c.execute('DROP VIEW '+name);sql+=f" AND f.current_mass_basis='{basis}'"+(" AND f.reference_electrode IS NOT NULL" if ref else '')+" AND NOT EXISTS(SELECT 1 FROM record_blockers b LEFT JOIN blocker_scopes bs USING(record_id,code) WHERE b.record_id=f.legacy_record_id AND b.status='open' AND COALESCE(bs.affects_core7,1)=1)";c.execute(sql)
 c.execute('delete from model_feature_cache');c.execute('insert into model_feature_cache select * from model_feature_rows');c.execute("update feature_cache_meta set value=? where key='selection_history_max_id'",(str(c.execute('select max(selection_id) from field_selection_history').fetchone()[0]),));c.execute("update feature_cache_meta set value=? where key='selected_fields'",(str(c.execute('select count(*) from field_selection').fetchone()[0]),));c.commit();c.close()
 p=O/'data_contract.json';d=json.loads(p.read_text(encoding='utf-8'));d['strict_3e_contract_status']='preparation_gate_only; final scientific protocol and real-training authorization still required';d['machine_preextraction']='native_measurement_claims are isolated unreviewed leads and never training rows';p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
if __name__=='__main__':main()
