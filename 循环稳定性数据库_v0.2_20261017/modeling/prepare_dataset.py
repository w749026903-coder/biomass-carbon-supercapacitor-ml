"""Read-only preparation. Candidate exports cannot bypass admission."""
import importlib.util
import json
import math
import pathlib
import sqlite3

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONTRACT = json.loads((ROOT/'modeling/model_contract.json').read_text(encoding='utf-8'))

def database_path(config=None):
    return ROOT / (config or CONTRACT)['database_file']

def connect():
    conn = sqlite3.connect(database_path().as_uri()+'?mode=ro', uri=True)
    conn.row_factory = sqlite3.Row
    return conn

def validate_rows(rows, config=None, require_admission=True):
    cfg = config or CONTRACT
    seen = set()
    identities = {key:{} for key in ['paper_id','material_id','cycle_test_id']}
    for r in rows:
        if not r.get('record_id') or r['record_id'] in seen:
            raise ValueError('Missing or duplicate endpoint identity')
        seen.add(r['record_id'])
        if require_admission and (r.get('eligible') != 1 or r.get('admission_status') != 'approved'):
            raise ValueError('Record admission required')
        if r.get('system') != cfg['primary_system'] or r.get('method') != cfg['method'] or r.get('conflict'):
            raise ValueError('Outside approved primary protocol')
        if r.get('retention_relation') != cfg['label_relation']:
            raise ValueError('Exact labels required')
        for k in cfg['required_conditions'] + ['retention_pct']:
            v = r.get(k)
            if v is None or (isinstance(v,str) and not v.strip()):
                raise ValueError('Missing required field: '+k)
            if k not in cfg['categorical_features'] and (not isinstance(v,(int,float)) or not math.isfinite(v)):
                raise ValueError('Invalid numeric field: '+k)
        if r['cycle_count'] < cfg['screening_min_cycles'] or int(r['cycle_count']) != r['cycle_count']:
            raise ValueError('Invalid cycle count')
        if r['retention_pct'] < 0 or r['current_density_A_g'] <= 0 or r['concentration_value'] <= 0:
            raise ValueError('Invalid nonpositive input or negative label')
        if r['voltage_upper_V'] <= r['voltage_lower_V']:
            raise ValueError('Invalid voltage window')
        for k in ['BET_m2_g','total_pore_volume_cm3_g']:
            v = r.get(k)
            if v is not None and (not isinstance(v,(int,float)) or not math.isfinite(v) or v <= 0):
                raise ValueError('Invalid optional characterization: '+k)
        if not r.get('study_group'):
            raise ValueError('Source group required')
        for k, mapping in identities.items():
            if not r.get(k):
                raise ValueError('Identity required: '+k)
            if r[k] in mapping and mapping[r[k]] != r['study_group']:
                raise ValueError('Shared identity assigned to multiple source groups: '+k)
            mapping[r[k]] = r['study_group']
        r['log10_cycle_count'] = math.log10(r['cycle_count'])
    return rows

def load_ready():
    with connect() as c:
        rows = [dict(x) for x in c.execute('SELECT * FROM training_ready ORDER BY study_group,material_id,cycle_test_id,cycle_count,record_id')]
        for r in rows:
            a = dict(c.execute('SELECT * FROM admissions WHERE record_id=?',(r['record_id'],)).fetchone())
            if any(a[k] != 1 for k in ['source_checked','material_checked','protocol_checked','baseline_checked','mass_basis_checked','independence_checked','freeze_cleared']):
                raise ValueError('Incomplete admission checks')
        for rel in c.execute("SELECT p.study_group AS a,q.study_group AS b FROM source_relationships r JOIN papers p ON p.paper_id=r.paper_id JOIN papers q ON q.paper_id=r.related_paper_id WHERE r.relationship='reuses_underlying_secondary_dataset'"):
            if rel['a'] != rel['b']:
                raise ValueError('Documented reused sources must share a group')
    return validate_rows(rows)

def preflight():
    rows = load_ready()
    deps = {name:importlib.util.find_spec(name) is not None for name in ['numpy','sklearn','xgboost']}
    return {'status':'waiting_for_record_admission' if not rows else 'review_training_run_before_execution',
            'approved_rows':len(rows),'study_groups':len({r['study_group'] for r in rows}),
            'provisional_materials':len({r['material_id'] for r in rows}),
            'dependencies':deps,'training_performed':False,'database_file':database_path().name,
            'note':'Preflight does not fit estimators. Synthetic interface checks are separate.'}

if __name__ == '__main__':
    print(json.dumps(preflight(),ensure_ascii=False,indent=2))
