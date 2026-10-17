"""Append issue resolution links; never rewrite parent issue rows."""
from pathlib import Path
import sqlite3
ROOT=Path(__file__).resolve().parent
c=sqlite3.connect(ROOT/'cycling_v0_3.sqlite');c.execute('pragma foreign_keys=ON')
assert not c.execute("select 1 from sqlite_master where name='issue_resolutions'").fetchone()
with c:
 c.execute('CREATE TABLE issue_resolutions(issue_id INTEGER PRIMARY KEY REFERENCES issues,review_id INTEGER NOT NULL REFERENCES review_events,effective_status TEXT NOT NULL,rationale TEXT NOT NULL)')
 for issue_id,rid in c.execute("select issue_id,record_id from issues where code='batch1_voltage_window_consistency'").fetchall():
  eid=c.execute("select review_id from field_review_latest where record_id=? and field_name='voltage_window_consistency' and decision='resolved_by_visual_erratum'",(rid,)).fetchone()[0]
  c.execute('insert into issue_resolutions values (?,?,?,?)',(issue_id,eid,'resolved_by_visual_erratum','Axis upper tick 1.2 V was misread as trace maximum; magnified traces peak around 1.0 V, consistent with text. Original issue remains unchanged.'))
 c.execute("CREATE VIEW issues_effective AS SELECT i.*,coalesce(r.effective_status,i.status) AS effective_status,r.review_id AS resolution_review_id,r.rationale AS resolution_rationale FROM issues i LEFT JOIN issue_resolutions r USING(issue_id)")
assert c.execute('select count(*) from issue_resolutions').fetchone()[0]==2
c.close();print('Two R112 issue resolutions linked without rewriting historical issues.')
