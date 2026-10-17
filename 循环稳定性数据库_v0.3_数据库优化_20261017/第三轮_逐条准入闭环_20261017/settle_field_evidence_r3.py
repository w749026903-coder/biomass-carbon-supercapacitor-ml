"""One-time current evidence-ledger synchronization, preserving old ledger rows in history."""
from pathlib import Path
import sqlite3, json, hashlib
ROOT=Path(__file__).resolve().parent
c=sqlite3.connect(ROOT/'cycling_v0_3r3.sqlite');c.row_factory=sqlite3.Row
c.execute('PRAGMA foreign_keys=ON')
if c.execute("SELECT 1 FROM metadata WHERE key='r3_field_ledger_settled'").fetchone():raise SystemExit('Already settled')
def ledger(rid,field,value,path,loc):
    old=c.execute('SELECT * FROM field_evidence WHERE record_id=? AND field_name=?',(rid,field)).fetchone()
    new={'value_json':json.dumps(value,ensure_ascii=False),'source_path':str(path),'locator':loc,'status':'verified_r3'}
    c.execute('INSERT INTO revision_changes(table_name,row_key,field_name,old_json,new_json,rationale) VALUES(?,?,?,?,?,?)',
        ('field_evidence',rid+'::'+field,'current_evidence',json.dumps(dict(old),ensure_ascii=False) if old else None,
         json.dumps(new,ensure_ascii=False),'r3直接来源复核后同步当前字段证据；旧值保留在本条历史及父库。'))
    c.execute('INSERT INTO field_evidence(record_id,field_name,value_json,source_path,locator,status) VALUES(?,?,?,?,?,?) ON CONFLICT(record_id,field_name) DO UPDATE SET value_json=excluded.value_json,source_path=excluded.source_path,locator=excluded.locator,status=excluded.status',
        (rid,field,new['value_json'],str(path),loc,'verified_r3'))

for e in c.execute("SELECT * FROM review_events WHERE review_id>181 AND decision='verified_r3'").fetchall():
    value=json.loads(e['value_json'])
    if e['field_name']=='device_voltage_window':
        ledger(e['record_id'],'voltage_lower_V',value[0],e['source_path'],e['locator'])
        ledger(e['record_id'],'voltage_upper_V',value[1],e['source_path'],e['locator'])
    elif e['field_name'] in ('BET_m2_g','total_pore_volume_cm3_g','baseline_definition'):
        ledger(e['record_id'],e['field_name'],value,e['source_path'],e['locator'])

# These nonpoint-label records are retained separately; restore their explicitly reported device windows.
inv=json.loads((ROOT.parent/'第二轮_全量利用与输入定稿_20261017'/'source_inventory_all137.json').read_text('utf-8'))
for rid,pid,lo,hi,loc in [('SRC112_CY01','SRC112',0.0,1.0,'PDF p10 Fig7a/b: same CSK-750-2 symmetric device; trace peaks at1.0V'),
                         ('R020_CY01','R020',0.0,1.0,'PDF p11 sec3.5 and Fig6a/b: AC symmetric cell; do not borrow asymmetric0–1.8V')]:
    path=next(f['path'] for f in inv if f['paper_id']==pid and f['role']=='main')
    tid=c.execute('SELECT cycle_test_id FROM cycling_endpoints WHERE record_id=?',(rid,)).fetchone()[0]
    c.execute('INSERT INTO review_events(record_id,field_name,decision,value_json,source_path,source_sha256,locator,evidence_excerpt,rationale,review_date) VALUES(?,?,?,?,?,?,?,?,?,?)',
        (rid,'device_voltage_window','verified_r3',json.dumps([lo,hi]),path,hashlib.sha256(Path(path).read_bytes()).hexdigest(),loc,
         'Device CV and GCD traces span0–1.0V.','同一对称器件协议；近似标签仍保持原关系，不因此准入。','2026-10-17'))
    for field,value in [('voltage_lower_V',lo),('voltage_upper_V',hi)]:
        old=c.execute(f'SELECT {field} FROM cycling_tests WHERE cycle_test_id=?',(tid,)).fetchone()[0]
        c.execute(f'UPDATE cycling_tests SET {field}=? WHERE cycle_test_id=?',(value,tid))
        c.execute('INSERT INTO revision_changes(table_name,row_key,field_name,old_json,new_json,rationale) VALUES(?,?,?,?,?,?)',
            ('cycling_tests',tid,field,json.dumps(old),json.dumps(value),loc))
        ledger(rid,field,value,path,loc)

# Recovered table labels and questionable point labels are not silently promoted.
rid='R020_CY01';path=next(f['path'] for f in inv if f['paper_id']=='R020' and f['role']=='main')
c.execute('INSERT INTO review_events(record_id,field_name,decision,value_json,source_path,source_sha256,locator,evidence_excerpt,rationale,review_date) VALUES(?,?,?,?,?,?,?,?,?,?)',
 (rid,'cycling_current_mass_basis_scope','reviewed_not_transferable',json.dumps({'symmetric_current_basis':None}),path,
  hashlib.sha256(Path(path).read_bytes()).hexdigest(),'PDF p14-15 sec3.6 asymmetric cells',
  'Current density calculations were based on a single supercapacitor electrode (SC) with similar masses for both electrodes',
  '该句位于非对称器件段；不能借给p12-13的AC对称循环，也不能自动除以2。保留近似89%标签。','2026-10-17'))
c.execute("INSERT INTO metadata(key,value) VALUES('r3_field_ledger_settled','true')")
c.commit();c.close();print('Field evidence ledger synchronized; original raw records unchanged.')
