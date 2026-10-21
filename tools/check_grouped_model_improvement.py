"""Regression checks of the real preprocessing/partition seams before selection fits."""
from pathlib import Path
import copy
import json
import sys
import numpy as np
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from data.cycling_db import open_database
from grouped_model_improvement import prepare, weights, inner_splits, weighted_median, select

with open_database() as db:
    ds = db.fetch()
rows = ds.rows
outer = ds.source_folds(23)[0]
checks = []
for kind in ['raw', 'log']:
    spec = {'transform': kind, 'current': True}
    a = prepare(rows, outer['train'], outer['test'], spec)
    changed = copy.deepcopy(rows)
    for i in outer['test']:
        changed[i].update(cycle_count=10**8, BET_m2_g=10**9, retention_pct=999999,
                          electrolyte='UNSEEN', reference_electrode='UNSEEN')
    b = prepare(changed, outer['train'], outer['test'], spec)
    assert a['schema'] == b['schema'] and np.array_equal(a['X'], b['X'])
    assert a['target_center'] == b['target_center'] and a['target_scale'] == b['target_scale']
    checks.append(kind + ': heldout features and labels cannot change training statistics')
group = next(g for g in {r['source_group'] for r in rows} if sum(r['source_group'] == g for r in rows) > 1)
ids = [i for i, r in enumerate(rows) if r['source_group'] == group]
try:
    prepare(rows, [i for i in range(len(rows)) if i != ids[0]], [ids[0]], {'transform': 'raw', 'current': True})
except ValueError:
    checks.append('within-source split rejected')
else:
    raise AssertionError('Source leakage accepted')
for tr, va in inner_splits(rows, outer['train'], outer['test']):
    assert set(tr) | set(va) == set(outer['train']) and not (set(tr) | set(va)) & set(outer['test'])
checks.append('all inner samples stay within outer training')
# One study with four rows must not dominate one study with a single row.
toy = [dict(rows[0], source_group='A', BET_m2_g=100)] + [dict(rows[0], source_group='B', BET_m2_g=300) for _ in range(4)] + [dict(rows[0], source_group='C', BET_m2_g=1e6)]
p = prepare(toy, [0, 1, 2, 3, 4], [5], {'transform': 'raw', 'current': True})
assert next(s for s in p['schema'] if s['field'] == 'BET_m2_g')['mean'] == 200
checks.append('source weighted numeric mean independently equals200 rather than row mean260')
assert weighted_median([0, 100, 100, 100, 100], [1, .25, .25, .25, .25]) == 0
checks.append('weighted median uses source weights')
fake_specs=[{'id':'simple','kind':'ridge','complexity':1},{'id':'complex','kind':'mlp','complexity':3}]
choices, cutoff = select([{'candidate':'simple','mae':3.1,'source_error_se':.2},
                          {'candidate':'complex','mae':3,'source_error_se':.2}], fake_specs)
assert choices == {'nested_min':'complex','nested_1se':'simple','nested_linear':'simple'}
checks.append('predeclared oneSE/linear rules follow inner scores only')
out=ROOT/'模型诊断与改进_20261021/preprocessing_checks.json'
out.write_text(json.dumps({'passed':True,'checks':checks},ensure_ascii=False,indent=2)+'\n','utf-8')
print(json.dumps({'passed':True,'checks':len(checks)}))
