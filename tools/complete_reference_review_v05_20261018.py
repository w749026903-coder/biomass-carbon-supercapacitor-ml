"""Own methods and SI reference-electrode review; append only in v0.5."""
from pathlib import Path
import json,sqlite3
R=Path(__file__).resolve().parents[1];O=R/'循环稳定性数据库_v0.5_逐条准入审查_20261018'
def enc(x):return json.dumps(x,ensure_ascii=False)
def main():
 c=sqlite3.connect(O/'cycling_v0_5.sqlite');c.row_factory=sqlite3.Row;c.execute('pragma foreign_keys=ON')
 if c.execute("select count(*) from extraction_run where key='v05_reference_review'").fetchone()[0]:raise RuntimeError('Already applied')
 refs={1:('Hg/HgO',46),2:('SCE',1035),3:('SCE',176),4:('SCE',196),5:('Ag/AgCl',696),6:('Hg/HgO; reported potentials converted to RHE',953),7:('Ag/AgCl',3868),9:('HgO/Hg (reported order)',3957),10:('Hg/HgO',4042),11:('Hg/HgO',4283),12:('Ag/AgCl',4456),13:('Hg/HgO',4564),20:('Hg/Hg2SO4 (saturated K2SO4)',4688),21:('Hg/HgO',5801),22:('Hg/HgO',5801),23:('Hg/HgO',5801),24:('Hg/HgO',5801),25:('Hg/HgO',5950),26:('Hg/HgO',5999),27:('Hg/HgO',6012),28:('Hg/HgO',6097),29:('Ag/AgCl',6136),30:('Ag/AgCl',6136),31:('Hg/HgO',2576),32:('calomel (saturation not separately specified)',6443),33:('Ag/AgCl',6161),34:('Ag/AgCl',6161),35:('Ag/AgCl',6219),36:('Ag/AgCl',6285),37:('Ag/AgCl',6285),38:('Ag/AgCl',6285),39:('Ag/AgCl',6481),40:('Hg/HgO',6937),41:('AgCl/Ag (reported order)',6860),42:('Ag/AgCl',6637),43:('SCE',6798),44:('Hg/HgO',6816),45:('Ag/AgCl (NaCl-saturated)',6710),46:('Ag/AgCl',6747),49:('SCE',6579),50:('Hg/HgO',6895),51:('Ag/AgCl',183),52:('Hg/HgO',6415),53:('Ag/AgCl',6654)}
 log=[]
 def select(ep,f,v,seg,unit=None,note='Own methods bind reference to the three-electrode experiment; this does not determine physical current normalization.'):
  s=c.execute('select * from source_segments where segment_id=?',(seg,)).fetchone();identity=c.execute('select identity_key from model_endpoints where endpoint_id=?',(ep,)).fetchone()[0]
  assert c.execute('select 1 from paper_documents where identity_key=? and source_id=?',(identity,s['source_id'])).fetchone()
  old=c.execute('select observation_id from field_selection where endpoint_id=? and field_name=?',(ep,f)).fetchone()[0]
  oid=c.execute('insert into field_observations(endpoint_id,field_name,value_json,unit,status,source_id,segment_id,locator,evidence_excerpt,provenance_json) values (?,?,?,?,?,?,?,?,?,?)',(ep,f,enc(v),unit,'own_primary_method_reference_review',s['source_id'],seg,s['locator'],s['text'],enc({'reason':note}))).lastrowid
  c.execute('update field_selection set observation_id=? where endpoint_id=? and field_name=?',(oid,ep,f));c.execute('insert into field_selection_history(endpoint_id,field_name,old_observation_id,new_observation_id,reason) values (?,?,?,?,?)',(ep,f,old,oid,note));log.append({'endpoint_id':ep,'field':f,'value':v,'segment_id':seg,'reason':note})
 for n,(ref,seg) in refs.items():
  ep=c.execute("select endpoint_id from endpoint_aliases where namespace='TE' and alias=?",(f'TE{n:03}',)).fetchone()[0]
  note='Own SC methods specify Ag/AgCl; Hg/HgO in the same page belongs to ORR and cannot be transferred.' if n in (29,30) else 'Own method binds reference electrode; loading or capacitance formula does not define current-density denominator.'
  select(ep,'reference_electrode',ref,seg,note=note)
 ep=c.execute("select endpoint_id from endpoint_aliases where namespace='TE' and alias='TE048'").fetchone()[0]
 select(ep,'BET_m2_g',425,7113,'m2/g','Own Table1 Betelnut shell row marked This work; BSPC is the own electrode, comparisons are separate rows.')
 for issue, in c.execute("select issue_id from extraction_issues where endpoint_id=? and code='BET_unlocated_or_binding_unresolved'",(ep,)).fetchall():
  c.execute('insert into extraction_issue_resolutions values (?,?,?)',(issue,'resolved_by_own_comparison_table_this_work_row',enc({'segment_id':7113,'BET_m2_g':425})))
 c.execute('insert into extraction_issues(endpoint_id,identity_key,field_name,code,status,evidence_json,reason) values (?,?,?,?,?,?,?)',(ep,'doi:10.3390/ma14247793','reference_electrode','printed_Hg_HgO4_reference_unclear','open',enc({'segment_id':6730,'reported':'Hg/HgO4'}),'Retain printed reference identity; do not silently correct a chemically unclear reference.'))
 ep=c.execute("select endpoint_id from endpoint_aliases where namespace='TE' and alias='TE020'").fetchone()[0]
 for f,v in [('cycle_voltage_lower_V',-.1),('cycle_voltage_upper_V',.6)]:select(ep,f,v,4669,'V','Own actual continuous GCD cycling paragraph explicitly states -0.1 to0.6V, not borrowed characterization window.')
 # Refresh newversion cache and dependent gatevalues after appended evidence.
 c.execute('delete from model_feature_cache');c.execute('insert into model_feature_cache select * from model_feature_rows')
 for k,v in [('selection_history_max_id',c.execute('select max(selection_id) from field_selection_history').fetchone()[0]),('selected_fields',c.execute('select count(*) from field_selection').fetchone()[0])]:c.execute('update feature_cache_meta set value=? where key=?',(str(v),k))
 for x in log:
  ep=x['endpoint_id'];f=x['field'];r=c.execute('select * from model_feature_cache where endpoint_id=?',(ep,)).fetchone();criterion='reference_electrode' if f=='reference_electrode' else 'sample_specific_BET' if f=='BET_m2_g' else 'cycle_specific_window'
  fs=['reference_electrode'] if criterion=='reference_electrode' else ['BET_m2_g'] if criterion=='sample_specific_BET' else ['cycle_voltage_lower_V','cycle_voltage_upper_V']
  evidence={'selected_observations':{field:c.execute('select observation_id from field_selection where endpoint_id=? and field_name=?',(ep,field)).fetchone()[0] for field in fs},'current_values':{field:r[field] for field in fs},'additional':x}
  c.execute("update record_admission_checks set status='pass',reason=?,evidence_json=? where endpoint_id=? and criterion=? and (criterion!='reference_electrode' or profile='canonical_3e')",(x['reason'],enc(evidence),ep,criterion))
 # New reference issue is an open hold even though its historical year already excludes it.
 te48=c.execute("select endpoint_id from endpoint_aliases where namespace='TE' and alias='TE048'").fetchone()[0]
 c.execute("update record_admission_checks set status='unresolved',reason=?,evidence_json=? where endpoint_id=? and criterion='open_scientific_holds'",('Unclear printed Hg/HgO4 reference remains open.',enc({'segment_id':6730}),te48))
 for r in c.execute('select * from record_gate_outcomes').fetchall():
  counts=dict(c.execute('select status,count(*) from record_admission_checks where endpoint_id=? and profile=? group by status',(r['endpoint_id'],r['profile'])))
  c.execute('update record_gate_outcomes set failed_count=?,unresolved_count=? where endpoint_id=? and profile=?',(counts.get('fail',0),counts.get('unresolved',0),r['endpoint_id'],r['profile']))
  old=c.execute('select status,reason from admission_reviews where endpoint_id=? and profile=?',(r['endpoint_id'],r['profile'])).fetchone()
  reason=f"v0.5 explicit gates: {counts.get('fail',0)} failed, {counts.get('unresolved',0)} unresolved; see record_admission_checks. No approval."
  c.execute('insert into admission_review_history(endpoint_id,profile,old_status,old_reason,new_status,new_reason) values (?,?,?,?,?,?)',(r['endpoint_id'],r['profile'],old['status'],old['reason'],old['status'],reason))
  c.execute('update admission_reviews set reason=? where endpoint_id=? and profile=?',(reason,r['endpoint_id'],r['profile']))
 c.execute('insert into extraction_run values (?,?)',('v05_reference_review',enc({'field_changes':len(log)})));c.commit();c.close()
 (O/'参比电极与进一步补字段.json').write_text(json.dumps(log,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(enc({'field_changes':len(log)}))
if __name__=='__main__':main()
