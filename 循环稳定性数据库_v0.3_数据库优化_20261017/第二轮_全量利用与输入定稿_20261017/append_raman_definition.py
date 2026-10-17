"""Explicit IG/ID measurements remain distinct from ID/IG."""
from pathlib import Path
import json,sqlite3
ROOT=Path(__file__).resolve().parent
inv=json.loads((ROOT/'source_inventory_all137.json').read_text(encoding='utf-8'))
s=next(r for r in inv if r['paper_id']=='R117' and r['role']=='main')
pages=json.loads(Path(s['extraction_path']).read_text(encoding='utf-8'));text=' '.join(next(p['text'] for p in pages if p['page']==6).split())
c=sqlite3.connect(ROOT/'cycling_v0_3r2.sqlite');c.row_factory=sqlite3.Row;c.execute('pragma foreign_keys=ON')
assert not c.execute("select 1 from material_observations where property_name='Raman_IG_ID'").fetchone()
with c:
 for rid,value in [('R117_CY01',1.1),('R117_CY02',1.03)]:
  r=c.execute('select material_id from endpoint_review where record_id=?',(rid,)).fetchone()
  why='PDF p6明确用IG/ID：ACRS-700为1.1、ACEW-700为1.03。保留原定义，不写成ID/IG，也不取倒数后冒称原报值。'
  anchor='1.03';i=text.find(anchor);assert i>=0
  c.execute('insert into review_events(record_id,field_name,decision,value_json,source_path,source_sha256,locator,evidence_excerpt,rationale,review_date) values (?,?,?,?,?,?,?,?,?,?)',(rid,'Raman_IG_ID','verified_precycling_property_scope',json.dumps(value),s['path'],s['sha256'],'PDF p6 Raman paragraph; IG/ID',text[max(0,i-300):i+200],why,'2026-10-17'))
  c.execute('insert into material_observations(material_id,record_id,property_name,value_json,unit,method,stage,source_path,locator,provenance_status) values (?,?,?,?,?,?,?,?,?,?)',(r['material_id'],rid,'Raman_IG_ID',json.dumps(value),'dimensionless','Raman IG/ID','precycling_as_prepared',s['path'],'main p6; IG/ID','verified_r2_scope_bounded'))
print('Added two IG/ID observations; no reciprocal substitution.')
