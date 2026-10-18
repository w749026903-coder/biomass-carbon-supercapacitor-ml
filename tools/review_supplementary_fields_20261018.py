"""Additional own-source SI review; append new field selections and issue resolutions."""
from pathlib import Path
import json,sqlite3
R=Path(__file__).resolve().parents[1];O=R/'循环稳定性数据库_v0.4_提取与调用_20261018'
def main():
 c=sqlite3.connect(O/'cycling_v0_4.sqlite');c.row_factory=sqlite3.Row;c.execute('pragma foreign_keys=ON')
 if c.execute("select count(*) from extraction_run where key='SI_review_complete'").fetchone()[0]:raise RuntimeError('Already applied')
 c.execute('CREATE TABLE IF NOT EXISTS extraction_issue_resolutions(issue_id INTEGER PRIMARY KEY REFERENCES extraction_issues,decision TEXT NOT NULL,evidence_json TEXT NOT NULL)')
 rows=json.loads((R/'三电极端点扩充_20261018/三电极端点_53条.json').read_text(encoding='utf-8'))['rows'];log=[]
 reviews=[('TE011',None,'952.27',None,{'BET_m2_g':952.27}),('TE039',None,'compared with 201',None,{'BET_m2_g':201.0}),('TE037',None,'280', 'XML p p0350',{'BET_m2_g':280.0}),('TE038',None,'67 m','XML p p0350',{'BET_m2_g':67.0}),('TE047',None,'ECNFs-6','XML table-wrap polymers-10-01306-t001',{'BET_m2_g':675.0,'total_pore_volume_cm3_g':0.29}),('TE049','ao8b03586_si_001.pdf','672.19','PDF p7',{'BET_m2_g':672.19}),('TE053','40820_2020_393_MOESM1_ESM.pdf','1704.20','PDF p3',{'BET_m2_g':1704.20,'total_pore_volume_cm3_g':0.81})]
 for alias,filehint,needle,locator,fields in reviews:
  x=next(x for x in rows if x['endpoint_id']==alias);sid=x['source_sha256'] if not filehint else c.execute('select source_id from document_locations where path like ?',('%'+filehint,)).fetchone()[0]
  segs=c.execute('select * from source_segments where source_id=?',(sid,)).fetchall();found=[s for s in segs if (not locator or s['locator']==locator) and needle in s['text']]
  if not found:raise RuntimeError(alias+' missing evidence '+needle)
  seg=found[0];ep=c.execute("select endpoint_id from endpoint_aliases where namespace='TE' and alias=?",(alias,)).fetchone()[0]
  for f,value in fields.items():
   old=c.execute('select observation_id from field_selection where endpoint_id=? and field_name=?',(ep,f)).fetchone()[0]
   reason='Own sample-specific SI table, visually checked' if filehint else 'Own sample-specific main table/passage; do not borrow another treatment/material.'
   q=c.execute('insert into field_observations(endpoint_id,field_name,value_json,unit,status,source_id,segment_id,locator,evidence_excerpt,provenance_json) values (?,?,?,?,?,?,?,?,?,?)',(ep,f,json.dumps(value),'m2/g' if f=='BET_m2_g' else 'cm3/g','reported_direct_SI_visual' if filehint else 'reported_direct_primary_passage',sid,seg['segment_id'],seg['locator'],seg['text'],json.dumps({'reason':reason},ensure_ascii=False)))
   c.execute('update field_selection set observation_id=? where endpoint_id=? and field_name=?',(q.lastrowid,ep,f));c.execute('insert into field_selection_history(endpoint_id,field_name,old_observation_id,new_observation_id,reason) values (?,?,?,?,?)',(ep,f,old,q.lastrowid,reason));log.append({'alias':alias,'endpoint_id':ep,'field':f,'value':value,'source_id':sid,'locator':seg['locator']})
   if f=='BET_m2_g':
    for issue, in c.execute("select issue_id from extraction_issues where endpoint_id=? and code='BET_unlocated_or_binding_unresolved'",(ep,)).fetchall():c.execute('insert into extraction_issue_resolutions values (?,?,?)',(issue,'resolved_by_later_same_task_primary_evidence',json.dumps(log[-1],ensure_ascii=False)))
 c.execute('insert into extraction_run values (?,?)',('SI_review_complete','true'));c.commit();(O/'补充材料逐字段提取.json').write_text(json.dumps(log,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({'additional_fields':len(log),'3E_BET_and_total_pore':list(c.execute('select sum(BET_m2_g is not null),sum(total_pore_volume_cm3_g is not null) from review_3e_rows').fetchone())},ensure_ascii=False));c.close()
if __name__=='__main__':main()
