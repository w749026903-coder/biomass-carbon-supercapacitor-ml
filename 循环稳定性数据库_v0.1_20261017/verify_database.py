"""Read-only integrity and leakage guard checks against the actual imported records."""
import importlib.util,json,pathlib,sqlite3,sys
ROOT=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'modeling'))
from prepare_dataset import load_ready,preflight
from train_grouped import source_disjoint
conn=sqlite3.connect((ROOT/'cycling_v0_1.sqlite').as_uri()+'?mode=ro',uri=True);conn.row_factory=sqlite3.Row
checks={}
checks['integrity']=conn.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
checks['foreign_keys']=not conn.execute('PRAGMA foreign_key_check').fetchall()
checks['one_flat_row_per_endpoint']=conn.execute('SELECT count(*)=count(distinct record_id) FROM endpoint_review').fetchone()[0]==1
checks['raw_values_preserved']=True
for row in conn.execute('SELECT r.raw_json,e.cycle_count,e.retention_pct,e.retention_relation FROM raw_records r JOIN cycling_endpoints e USING(record_id)'):
 raw=json.loads(row['raw_json'])
 if (row['cycle_count'],row['retention_pct'],row['retention_relation'])!=(raw.get('cycle_count'),raw.get('retention_pct'),raw.get('retention_relation','eq')):checks['raw_values_preserved']=False
checks['R107_shared_material']=conn.execute("SELECT count(distinct material_id) FROM endpoint_review WHERE paper_id='R107'").fetchone()[0]==1
checks['SRC123_one_material_two_tests']=tuple(conn.execute("SELECT count(distinct material_id),count(distinct cycle_test_id),count(*) FROM endpoint_review WHERE paper_id='SRC123'").fetchone())==(1,2,3)
checks['R112_systems_do_not_merge']=conn.execute("SELECT count(distinct cycle_test_id) FROM endpoint_review WHERE paper_id='R112'").fetchone()[0]==2
checks['above100_not_clipped']=conn.execute('SELECT count(*) FROM cycling_endpoints WHERE retention_pct>100').fetchone()[0]==10
checks['CV_not_in_main_view']=conn.execute("SELECT count(*) FROM primary_screening_candidates WHERE method<>'GCD'").fetchone()[0]==0
checks['nonexact_labels_not_in_main_view']=conn.execute("SELECT count(*) FROM primary_screening_candidates WHERE retention_relation<>'eq'").fetchone()[0]==0
checks['freezes_and_separate_systems_not_admitted']=conn.execute("SELECT count(*) FROM training_ready WHERE conflict=1 OR category='C' OR system<>'2E_symmetric'").fetchone()[0]==0
checks['no_implicit_admission']=len(load_ready())==0
# The actual repeated nodes must be rejected if someone tries to put them on both sides.
rr=[dict(r) for r in conn.execute("SELECT * FROM endpoint_review WHERE paper_id='R107' ORDER BY cycle_count")]
try:source_disjoint(rr[:1],rr[1:]);checks['repeated_node_leakage_guard']=False
except ValueError:checks['repeated_node_leakage_guard']=True
allrows=[dict(r) for r in conn.execute('SELECT * FROM primary_screening_candidates')]
groups=sorted({r['study_group'] for r in allrows})
source_disjoint([r for r in allrows if r['study_group'] in groups[:1]],[r for r in allrows if r['study_group'] not in groups[:1]])
checks['source_disjoint_preview']=True
# Exercise the admission constraint in a temporary in-memory database, never in the file.
mem=sqlite3.connect(':memory:');mem.execute('PRAGMA foreign_keys=OFF');mem.executescript((ROOT/'schema.sql').read_text(encoding='utf-8'));mem.execute('PRAGMA foreign_keys=OFF')
try:
 mem.execute("INSERT INTO admissions(record_id,status,eligible,rationale) VALUES ('guard-test','approved',1,'missing checks')")
 checks['cannot_approve_with_unchecked_fields']=False
except sqlite3.IntegrityError:checks['cannot_approve_with_unchecked_fields']=True
mem.close()
for path in ROOT.rglob('*.py'):compile(path.read_text(encoding='utf-8'),str(path),'exec')
checks['python_syntax']=True
result={'checks':checks,'all_passed':all(checks.values()),'preflight':preflight(),'model_fit_executed':False}
(ROOT/'数据库与建模入口核验.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
assert result['all_passed'],result
print(json.dumps(result,ensure_ascii=False,indent=2))
