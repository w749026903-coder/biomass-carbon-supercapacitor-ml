"""Materialize reviewed v0.10 deltas in a new, compact SQLite overlay. No fitting."""
from pathlib import Path
import csv
import hashlib
import importlib.util
import json
import sqlite3
import sys

from training_input_quality import assess, prepare_source_fold

ROOT = Path(__file__).resolve().parents[1]
BATCH = ROOT / '数据精细补证_20261021_第二批'
OUT = ROOT / '循环稳定性数据库_v0.10_原文精细补证_20261021'
PARENT = ROOT / '循环稳定性数据库_v0.9_训练质量准备_20261021'
PARENT_SHA = '0f439a229b6c5e9e917abb1382b78587eeaea428f714c5b108fdc5b867a894aa'


def read(p):
    return json.loads(p.read_text('utf-8'))


def write(p, v):
    p.write_text(json.dumps(v, ensure_ascii=False, indent=2) + '\n', 'utf-8')


def sha(p):
    with p.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def api(folder=OUT):
    name = '_evidence_release_' + folder.name.split('_')[1].replace('.', '_')
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, folder / 'ml_data.py')
        m = importlib.util.module_from_spec(spec)
        sys.modules[name] = m
        spec.loader.exec_module(m)
    return sys.modules[name]


def build():
    path = OUT / 'cycling_v0_10.sqlite'
    if (OUT / 'merge_manifest.json').exists() or path.exists():
        raise FileExistsError('Never rebuild or overwrite an existing v0.10 database.')
    if sha(PARENT / 'cycling_v0_9.sqlite') != PARENT_SHA:
        raise ValueError('Parent fingerprint changed')
    cases = read(BATCH / 'curation_delta.json')
    with api(PARENT).Database() as parent:
        rows = {r['endpoint_id']: r for r in parent.incoming_tests()}
        for c in cases:
            if c['before'] != rows[c['endpoint_id']]:
                raise ValueError('Stale before value: ' + c['endpoint_id'])
            for e in c['evidence']:
                if sha(ROOT / e['path']) != e['sha256']:
                    raise ValueError('Evidence fingerprint changed: ' + e['path'])
    contract = read(PARENT / 'data_contract.json')
    contract.update(version='v0.10', database_file=path.name, parent_database_sha256=PARENT_SHA,
                    storage_layout='Read-only v0.9 and v0.8 chain plus compact v0.10 deltas/snapshots; retain whole repository.')
    write(OUT / 'data_contract.json', contract)
    with sqlite3.connect(path) as c:
        c.executescript('''
        CREATE TABLE evidence_decisions_v10(endpoint_id TEXT PRIMARY KEY, record_id TEXT UNIQUE NOT NULL, decision_json TEXT NOT NULL);
        CREATE TABLE training_rows_v10(profile TEXT, endpoint_id TEXT, source_group TEXT NOT NULL, row_json TEXT NOT NULL, PRIMARY KEY(profile,endpoint_id));
        CREATE TABLE training_folds_v10(profile TEXT, fold_index INTEGER, split_json TEXT NOT NULL, PRIMARY KEY(profile,fold_index));
        CREATE TABLE metadata_v10(key TEXT PRIMARY KEY, value_json TEXT NOT NULL);
        ''')
        for case in cases:
            c.execute('insert into evidence_decisions_v10 values(?,?,?)',
                      (case['endpoint_id'], case['record_id'], json.dumps(case, ensure_ascii=False)))
        c.execute('insert into metadata_v10 values(?,?)', ('parent_database_sha256', json.dumps(PARENT_SHA)))
    readiness = {'purpose': 'reported_protocol_retention', 'data_preparation_ready': True,
                 'formal_model_fit_authorized': False, 'all_literature_admitted': False, 'cohorts': {}}
    with api().Database() as db, sqlite3.connect(path) as c:
        for prof in contract['profiles']:
            ds = db.fetch(prof)
            readiness['cohorts'][prof] = assess(ds)
            folds = ds.source_folds(len({r['source_group'] for r in ds.rows}))
            write(OUT / (prof + '_inputs.json'), {'rows': ds.rows, 'matrix': ds.feature_matrix(),
                  'source_folds': folds, 'fingerprint': ds.fingerprint()})
            for r in ds.rows:
                c.execute('insert into training_rows_v10 values(?,?,?,?)',
                          (prof, r['endpoint_id'], r['source_group'], json.dumps(r, ensure_ascii=False)))
            for i, fold in enumerate(folds):
                c.execute('insert into training_folds_v10 values(?,?,?)', (prof, i, json.dumps(fold)))
            with (OUT / (prof + '_inputs.csv')).open('w', encoding='utf-8-sig', newline='') as f:
                fields = ['endpoint_id', 'source_group', 'source_year', 'sample_name', *ds.features,
                          'retention_pct', 'retention_relation', 'source_weight']
                w = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
                w.writeheader()
                w.writerows(ds.rows)
            write(OUT / (prof + '_fold_example.json'), prepare_source_fold(ds, folds[0]))
            nested = []
            for outer in folds:
                groups = sorted({ds.rows[i]['source_group'] for i in outer['train']})
                inner = []
                for k in range(min(5, len(groups))):
                    held = set(groups[k::min(5, len(groups))])
                    inner.append({'train': [i for i in outer['train'] if ds.rows[i]['source_group'] not in held],
                                  'test': [i for i in outer['train'] if ds.rows[i]['source_group'] in held],
                                  'outer_holdout': outer['test']})
                nested.append({**outer, 'inner_folds': inner})
            write(OUT / (prof + '_nested_fold_plan.json'), nested)
        write(BATCH / 'current_review_rows.json', db.incoming_tests())
        write(BATCH / '当前待补证据队列.json', db.review_queue())
    write(OUT / 'training_readiness.json', readiness)
    return readiness


if __name__ == '__main__':
    result = build()
    print(json.dumps({p: {k: q[k] for k in ['rows', 'source_groups', 'status', 'model_fits']}
                      for p, q in result['cohorts'].items()}, ensure_ascii=False))
