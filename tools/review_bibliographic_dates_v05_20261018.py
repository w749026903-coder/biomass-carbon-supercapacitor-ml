"""Normalize two historical publisher-date encodings without guessing DOI years."""
from pathlib import Path
import hashlib,json,sqlite3
R=Path(__file__).resolve().parents[1];O=R/'循环稳定性数据库_v0.5_逐条准入审查_20261018'
def enc(x):return json.dumps(x,ensure_ascii=False)
def main():
 c=sqlite3.connect(O/'cycling_v0_5.sqlite');c.row_factory=sqlite3.Row
 if c.execute("select count(*) from extraction_run where key='v05_bibliography_date_review'").fetchone()[0]:raise RuntimeError('Already applied')
 log=[]
 for ident, in c.execute('select distinct identity_key from model_endpoints where source_year is null').fetchall():
  candidates=[]
  for ob in c.execute('select rowid as observation_rowid,* from literature_observations where identity_key=?',(ident,)):
   d=json.loads(ob['source_json']);dates=d.get('bibliography',{}).get('dates',{})
   if not isinstance(dates,dict):continue
   # Crossref deposited dates, with explicit publication-date keys only.
   for kind in ('published','published-online','published-print','issued'):
    raw=dates.get(kind,{});parts=raw.get('date-parts',[]) if isinstance(raw,dict) else []
    if parts and parts[0] and isinstance(parts[0][0],int):candidates.append((parts[0][0],kind,ob,dates))
  if not candidates:continue
  year,kind,ob,dates=min(candidates,key=lambda x:x[0])
  evidence={'literature_observation_rowid':ob['observation_rowid'],'batch':ob['batch'],'identity_key':ident,'date_key':kind,'dates':dates,'source_json_sha256':hashlib.sha256(ob['source_json'].encode()).hexdigest()}
  c.execute('insert into bibliography_reviews(identity_key,publication_year,date_type,locator,excerpt,decision) values (?,?,?,?,?,?)',(ident,year,'publisher_deposited_'+kind,'literature_observations.source_json/bibliography/dates',enc(evidence),'Existingpublisher-depositedpublicationdate; dictionaryencodinghandledexplicitly. No DOI-yearorreceived/acceptedsubstitution.'))
  for ep in c.execute('select endpoint_id,source_year,year_basis from model_endpoints where identity_key=? and source_year is null',(ident,)).fetchall():
   c.execute('insert into endpoint_metadata_changes(endpoint_id,field_name,old_value_json,new_value_json,reason,evidence_json) values (?,?,?,?,?,?)',(ep['endpoint_id'],'publication_metadata',enc({'source_year':ep['source_year'],'year_basis':ep['year_basis']}),enc({'source_year':year,'year_basis':'publisher_deposited_'+kind}),'Normalizeexistingbibliographicdateobjectwithoutwebrefresh.',enc(evidence)))
   c.execute('update model_endpoints set source_year=?,year_basis=? where endpoint_id=?',(year,'existing_publisher_date_dictionary:'+kind,ep['endpoint_id']))
   c.execute('update record_admission_checks set status=?,reason=?,evidence_json=? where endpoint_id=? and criterion=?',('pass' if 2023<=year<=2026 else 'fail','2023–2026 publication year checked against existing deposited publication-date object; receipt dates excluded.',enc(evidence),ep['endpoint_id'],'publication_year'))
   log.append({'endpoint_id':ep['endpoint_id'],'year':year,'evidence':evidence})
 c.execute('delete from model_feature_cache');c.execute('insert into model_feature_cache select * from model_feature_rows')
 for r in c.execute('select * from record_gate_outcomes').fetchall():
  counts=dict(c.execute('select status,count(*) from record_admission_checks where endpoint_id=? and profile=? group by status',(r['endpoint_id'],r['profile'])));state='excluded' if counts.get('fail') else 'pending'
  c.execute('update record_gate_outcomes set status=?,failed_count=?,unresolved_count=? where endpoint_id=? and profile=?',(state,counts.get('fail',0),counts.get('unresolved',0),r['endpoint_id'],r['profile']))
  old=c.execute('select status,reason from admission_reviews where endpoint_id=? and profile=?',(r['endpoint_id'],r['profile'])).fetchone();reason=f"v0.5 explicit gates: {counts.get('fail',0)} failed, {counts.get('unresolved',0)} unresolved; see record_admission_checks. No approval."
  if old['status']!=state or old['reason']!=reason:
   c.execute('insert into admission_review_history(endpoint_id,profile,old_status,old_reason,new_status,new_reason) values (?,?,?,?,?,?)',(r['endpoint_id'],r['profile'],old['status'],old['reason'],state,reason));c.execute('update admission_reviews set status=?,reason=? where endpoint_id=? and profile=?',(state,reason,r['endpoint_id'],r['profile']))
 c.execute('insert into extraction_run values (?,?)',('v05_bibliography_date_review',enc({'metadata_updates':len(log),'web_refresh':False})));c.commit();c.close()
 (O/'出版元数据编码核查.json').write_text(json.dumps(log,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(enc({'metadata_updates':len(log)}))
if __name__=='__main__':main()
