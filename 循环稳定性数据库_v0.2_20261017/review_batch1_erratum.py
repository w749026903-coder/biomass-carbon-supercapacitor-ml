"""Append explicit clarification of the shared R107 test; preserve audit history."""
import json
import sqlite3
from review_batch1 import ROOT,REVIEWS,js

def main():
    c=sqlite3.connect(ROOT/'cycling_v0_2.sqlite');c.row_factory=sqlite3.Row
    if c.execute("SELECT count(*) FROM review_events WHERE decision='inherited_shared_test_pending_final_audit'").fetchone()[0]:
        raise RuntimeError('Clarification already recorded')
    with c:
        for rid in ['R107_CY01','R107_CY02']:
            old=c.execute('SELECT rationale FROM admissions WHERE record_id=?',(rid,)).fetchone()[0]
            reason=REVIEWS['R107']['reason']
            c.execute('INSERT INTO revision_changes(table_name,row_key,field_name,old_json,new_json,rationale) VALUES (?,?,?,?,?,?)',
                ('admissions',rid,'rationale',js(old),js(reason),'Audit wording correction: both nodes share a provisional test identity; never independently certify inherited evidence'))
            c.execute('UPDATE admissions SET rationale=? WHERE record_id=?',(reason,rid))
        for field in ['voltage_lower_V','voltage_upper_V']:
            original=dict(c.execute('SELECT * FROM review_events WHERE record_id=? AND field_name=?',('R107_CY01',field)).fetchone())
            keys=['record_id','field_name','decision','value_json','source_path','source_sha256','locator','evidence_excerpt','rationale','review_date']
            for rid,decision in [('R107_CY01','verified_graph_axis'),('R107_CY02','inherited_shared_test_pending_final_audit')]:
                row={**original,'record_id':rid,'decision':decision,
                     'rationale':'更正首批措辞：v0.1两个终点共享cycle_test_id，图6直接支持一万次窗口；测试级0–1 V会显示于两万次节点。两万次为继承协议，仍需测试归并与窗口终审，不是独立核实。'}
                c.execute('INSERT INTO review_events('+','.join(keys)+') VALUES ('+','.join('?' for _ in keys)+')',[row[k] for k in keys])
    out=[dict(r) for r in c.execute('SELECT record_id,status,source_checked,material_checked,protocol_checked,baseline_checked,mass_basis_checked,independence_checked,freeze_cleared,eligible,rationale FROM admissions WHERE source_checked=1 ORDER BY record_id')]
    (ROOT/'首批逐记录审查.json').write_text(js(out),encoding='utf-8')
    c.close()
    print('Shared-test clarification appended; original audit events retained.')

if __name__=='__main__':main()
