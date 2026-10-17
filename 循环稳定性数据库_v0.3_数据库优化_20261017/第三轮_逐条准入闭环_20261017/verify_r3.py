"""Integrity checks and in-memory gate regressions. No scientific model is fitted."""
from pathlib import Path
import sqlite3, json, hashlib, sys
from admission_policy import assess, CHECKS
ROOT=Path(__file__).resolve().parent
PARENT=ROOT.parent/'第二轮_全量利用与输入定稿_20261017'
sys.stdout.reconfigure(encoding='utf-8')
results=[]
def check(name, condition):
    results.append({'check':name,'passed':bool(condition)})
    if not condition: raise AssertionError(name)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def ro(p):
    x=sqlite3.connect(p.as_uri()+'?mode=ro',uri=True);x.row_factory=sqlite3.Row;return x
c=ro(ROOT/'cycling_v0_3r3.sqlite');parent=ro(PARENT/'cycling_v0_3r2.sqlite')
check('SQLite integrity',c.execute('PRAGMA integrity_check').fetchone()[0]=='ok')
check('Foreign keys',not c.execute('PRAGMA foreign_key_check').fetchall())
for table in ['raw_records','ingestion_sources','materials','cycling_endpoints']:
    old=[tuple(r) for r in parent.execute('SELECT * FROM '+table+' ORDER BY 1')]
    new=[tuple(r) for r in c.execute('SELECT * FROM '+table+' ORDER BY 1')]
    check(table+' unchanged',old==new)
for table,idfield in [('review_events','review_id'),('revision_changes','change_id'),('material_observations','observation_id')]:
    n=parent.execute('SELECT MAX('+idfield+') FROM '+table).fetchone()[0]
    check(table+' parent history retained',[tuple(r) for r in parent.execute(f'SELECT * FROM {table} ORDER BY {idfield}')]==
          [tuple(r) for r in c.execute(f'SELECT * FROM {table} WHERE {idfield}<=? ORDER BY {idfield}',(n,))])
protected=json.loads((ROOT/'protected_parent_fingerprints.json').read_text('utf-8'))
changed=[r['path'] for r in protected if not Path(r['path']).exists() or sha(r['path'])!=r['sha256']]
check('310 signed parent files unchanged',not changed)
originals=[dict(r) for r in parent.execute('SELECT * FROM source_files')]
check('137 original sources unchanged',all(sha(r['path'])==r['sha256'] for r in originals))
check('4 acquired supplements match hashes',all(sha(r['path'])==r['sha256'] for r in c.execute('SELECT * FROM source_files WHERE file_id>?',(max(r['file_id'] for r in originals),))))
contract=json.loads((ROOT.parent.parent/'并行协作契约_v1_20261017.json').read_text('utf-8'))
check('v02 baseline unchanged',sha(contract['baseline']['database'])==contract['baseline']['database_sha256'])
check('v02 model contract unchanged',sha(contract['baseline']['model_contract'])==contract['baseline']['model_contract_sha256'])
check('89 live decisions',c.execute('SELECT count(*) FROM admission_decisions_r3').fetchone()[0]==89)
check('Only10 focused mass audits',c.execute('SELECT count(*) FROM mass_definition_audits').fetchone()[0]==10)
check('Main formal admission remains0',c.execute('SELECT count(*) FROM training_ready').fetchone()[0]==0)
check('R111 SI window0–1',tuple(c.execute("SELECT voltage_lower_V,voltage_upper_V FROM endpoint_effective_review WHERE record_id='R111_CY01'").fetchone())==(0.0,1.0))
check('SRC035 total pore0.53 not micro0.40',c.execute("SELECT total_pore_volume_cm3_g FROM endpoint_features WHERE record_id='SRC035_CY01'").fetchone()[0]==0.53)
check('R10720k window remains unknown',tuple(c.execute("SELECT voltage_lower_V,voltage_upper_V FROM endpoint_effective_review WHERE record_id='R107_CY02'").fetchone())==(None,None))
check('5 baseline origin cycle numbers not fabricated',all(json.loads(r[0])['cycle_index'] is None for r in c.execute("SELECT baseline_json FROM cycling_tests WHERE cycle_test_id IN (SELECT cycle_test_id FROM cycling_endpoints WHERE record_id IN ('R093_CY01','R103_CY01','R104_CY01','R111_CY01','SRC035_CY01'))")))
check('Greater-than100 target values retained',c.execute('SELECT count(*) FROM cycling_endpoints WHERE retention_pct>100').fetchone()[0]==parent.execute('SELECT count(*) FROM cycling_endpoints WHERE retention_pct>100').fetchone()[0])
check('Approximate/bound labels retained',[tuple(r) for r in c.execute('SELECT record_id,retention_relation FROM cycling_endpoints ORDER BY record_id')]==[tuple(r) for r in parent.execute('SELECT record_id,retention_relation FROM cycling_endpoints ORDER BY record_id')])
check('Same-paper group never split',not c.execute('SELECT e.paper_id FROM validation_group_assignments g JOIN endpoint_effective_review e USING(record_id) GROUP BY e.paper_id HAVING count(DISTINCT g.group_id)>1').fetchall())
check('Known endpoint pair links share groups',not c.execute("SELECT l.link_id FROM validation_links l JOIN validation_group_assignments a ON a.record_id=l.record_a JOIN validation_group_assignments b ON b.record_id=l.record_b WHERE a.group_id<>b.group_id").fetchall())
check('Unresolved predecessor stays blocked',c.execute("SELECT independence_checked FROM admissions WHERE record_id='SRC123_CY02'").fetchone()[0]==0)
check('Actual cycling currents and mass bases unchanged',
      [tuple(r) for r in c.execute('SELECT cycle_test_id,current_density_A_g,mass_basis FROM cycling_tests ORDER BY cycle_test_id')]==
      [tuple(r) for r in parent.execute('SELECT cycle_test_id,current_density_A_g,mass_basis FROM cycling_tests ORDER BY cycle_test_id')])

# All following mutations exist only in RAM, on an explicitly synthetic gate fixture.
m=sqlite3.connect(':memory:');m.row_factory=sqlite3.Row;c.backup(m)
rid='R091_CY01';tid=m.execute('SELECT cycle_test_id FROM cycling_endpoints WHERE record_id=?',(rid,)).fetchone()[0]
m.execute("UPDATE admissions SET source_checked=1,material_checked=1,protocol_checked=1,baseline_checked=1,mass_basis_checked=1,independence_checked=1,freeze_cleared=1,status='approved',eligible=1 WHERE record_id=?",(rid,))
m.execute("UPDATE cycling_tests SET mass_basis='two_electrode_total_active_mass' WHERE cycle_test_id=?",(tid,))
m.execute("UPDATE record_blockers SET status='resolved_by_review' WHERE record_id=? AND code<>'pore_volume_unit'",(rid,))
m.execute("UPDATE endpoint_features SET total_pore_volume_cm3_g=999,pore_unit_review_required=1 WHERE record_id=?",(rid,))
def ready():return m.execute('SELECT count(*) FROM training_ready WHERE record_id=?',(rid,)).fetchone()[0]==1
check('SYNTH: open optional pore issue permits core7',ready())
check('SYNTH: unsafe optional value masked toNULL',m.execute('SELECT total_pore_volume_cm3_g FROM training_ready WHERE record_id=?',(rid,)).fetchone()[0] is None)
check('SYNTH: optional variant uses same admitted cohort',m.execute('SELECT count(*) FROM training_ready_pore').fetchone()[0]==m.execute('SELECT count(*) FROM training_ready').fetchone()[0])
m.execute('SAVEPOINT valid_fixture')
cases=[
 ('missing BET',"UPDATE endpoint_features SET BET_m2_g=NULL WHERE record_id=?",(rid,)),
 ('zero BET',"UPDATE endpoint_features SET BET_m2_g=0 WHERE record_id=?",(rid,)),
 ('undefined current basis',"UPDATE cycling_tests SET mass_basis=NULL WHERE cycle_test_id=?",(tid,)),
 ('single electrode current not converted',"UPDATE cycling_tests SET mass_basis='single_electrode_active_mass' WHERE cycle_test_id=?",(tid,)),
 ('molal m not molar M',"UPDATE cycling_tests SET concentration_unit='m' WHERE cycle_test_id=?",(tid,)),
 ('unknown voltage',"UPDATE cycling_tests SET voltage_upper_V=NULL WHERE cycle_test_id=?",(tid,)),
 ('conflicting target',"UPDATE cycling_endpoints SET conflict=1 WHERE record_id=?",(rid,)),
 ('approx target',"UPDATE cycling_endpoints SET retention_relation='approx' WHERE record_id=?",(rid,)),
 ('lower bound target',"UPDATE cycling_endpoints SET retention_relation='gt' WHERE record_id=?",(rid,)),
 ('post-scope silicon hold',"UPDATE endpoint_features SET Si_residue_review_required=1 WHERE record_id=?",(rid,)),
 ('source group unreviewed',"UPDATE validation_group_assignments SET review_status='inherited_not_final' WHERE record_id=?",(rid,)),
 ('unknown blocker fail closed',"INSERT INTO record_blockers(record_id,code,status,rationale) VALUES(?,'NEW_UNKNOWN_ISSUE','open','SYNTH ONLY')",(rid,)),
 ('short cycle convention',"UPDATE cycling_endpoints SET cycle_count=100 WHERE record_id=?",(rid,)),
 ('old paper excluded',"UPDATE papers SET year=2016 WHERE paper_id='R091'",()),
 ('future publication excluded',"UPDATE papers SET year=2027 WHERE paper_id='R091'",()),
 ('gel electrolyte excluded',"UPDATE cycling_tests SET electrolyte='PVA/KOH' WHERE cycle_test_id=?",(tid,))]
for name,query,args in cases:
    m.execute(query,args);check('SYNTH reject: '+name,not ready());m.execute('ROLLBACK TO valid_fixture')
m.execute("UPDATE cycling_tests SET electrolyte='sodium_acetate' WHERE cycle_test_id=?",(tid,))
check('SYNTH sodium acetate spelling accepted',ready());m.execute('ROLLBACK TO valid_fixture')
m.close()
check('Regression mutations did not reach real database',c.execute('SELECT count(*) FROM training_ready').fetchone()[0]==0)
(ROOT/'核验结果_r3.json').write_text(json.dumps({'checks':results,'passed':sum(r['passed'] for r in results),'failed':sum(not r['passed'] for r in results),'research_fits':0,'protected_parent_files':len(protected),'original_sources':len(originals)},ensure_ascii=False,indent=2),'utf-8')
print(f'{len(results)} checks passed;0 research fits.');c.close();parent.close()
