"""Read-only database preparation. No estimator fitting, no implicit admission."""
import collections, importlib.util, json, math, pathlib, sqlite3
ROOT=pathlib.Path(__file__).resolve().parents[1]
CONTRACT=json.loads((ROOT/'modeling/model_contract.json').read_text(encoding='utf-8'))
def connect():
 conn=sqlite3.connect((ROOT/'cycling_v0_1.sqlite').as_uri()+'?mode=ro',uri=True)
 conn.row_factory=sqlite3.Row
 return conn
def load_ready():
 with connect() as c:rows=[dict(x) for x in c.execute('SELECT * FROM training_ready ORDER BY study_group,material_id,cycle_test_id,cycle_count,record_id')]
 for r in rows:
  assert r['eligible']==1 and r['admission_status']=='approved'
  assert r['system']=='2E_symmetric' and r['method']=='GCD' and not r['conflict']
  assert r['retention_relation']=='eq' and r['cycle_count']>0 and r['retention_pct'] is not None
  assert all(r[k] is not None for k in CONTRACT['required_conditions'])
  r['log10_cycle_count']=math.log10(r['cycle_count'])
 return rows
def preflight():
 rows=load_ready()
 sklearn=importlib.util.find_spec('sklearn') is not None
 xgboost=importlib.util.find_spec('xgboost') is not None
 return {'status':('waiting_for_record_admission' if not rows else ('runtime_dependencies_missing' if not (sklearn and xgboost) else 'ready_for_review_of_training_run')),
         'approved_rows':len(rows),'study_groups':len({r['study_group'] for r in rows}),
         'provisional_materials':len({r['material_id'] for r in rows}),
         'sklearn_available':sklearn,'xgboost_available':xgboost,
         'training_performed':False,'note':'This check prepares data only. Installing dependencies and running training are separate future steps.'}
if __name__=='__main__':
 report=preflight();out=ROOT/'modeling/preflight_result.json'
 out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps(report,ensure_ascii=False,indent=2))
