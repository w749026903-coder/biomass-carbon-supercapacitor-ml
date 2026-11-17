"""Recalculate P76 scores with standard-library arithmetic, without refitting."""

from collections import Counter, defaultdict
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / '保持率达标研究_v3_主线与近优组合_20261030'
OUT = BASE / '第七十六轮_莲茎补证与同批增量对照_20261118'


def read(p):
    return json.loads(p.read_text(encoding='utf-8'))


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def score(rows):
    groups = defaultdict(Counter)
    for r in rows:
        groups[r['source_family']][r['curve_id']] += 1
    triples = []
    for r in rows:
        g = groups[r['source_family']]
        w = Fraction(1, len(groups)*len(g)*g[r['curve_id']])
        e = abs(r['observed']-r['predicted'])
        triples.append((r,w,e))
    assert sum(w for _,w,_ in triples) == 1
    mean = math.fsum(float(w)*r['observed'] for r,w,_ in triples)
    mse = math.fsum(float(w)*e**2 for _,w,e in triples)
    var = math.fsum(float(w)*(r['observed']-mean)**2 for r,w,_ in triples)
    def q(relative):
        values = [(e/r['observed']*100 if relative else e,w) for r,w,e in triples]
        acc = Fraction()
        for v,w in sorted(values):
            acc += w
            if acc >= Fraction(9,10):
                return v
    source_mae = []
    for s in groups:
        t = [(float(w),e) for r,w,e in triples if r['source_family'] == s]
        source_mae.append(math.fsum(w*e for w,e in t)/math.fsum(w for w,_ in t))
    ordered = sorted(source_mae)
    rank = .9*(len(ordered)-1)
    lower = math.floor(rank)
    tail = ordered[lower]+(ordered[min(lower+1,len(ordered)-1)]-ordered[lower])*(rank-lower)
    return dict(mae=math.fsum(float(w)*e for _,w,e in triples),rmse=math.sqrt(mse),
                r2=1-mse/var,mape_pct=math.fsum(float(w)*e/r['observed']*100 for r,w,e in triples),
                p90_absolute_error=q(False),p90_ape_pct=q(True),source_p90_mae=tail)


def main():
    plan, data, events, predictions, results = (read(OUT/f) for f in
        ('training_plan.json','input_snapshot.json','fit_events.json','predictions.json','results.json'))
    checks = []
    def check(ok,label):
        assert ok,label
        checks.append(label)
    for p,h in plan['protected'].items():
        check(sha(ROOT/p)==h,'protected '+p)
    for name in ('current_retention_research','current_training_latest'):
        ptr = read(ROOT/'data'/f'{name}.json')
        db = ROOT/(ptr['database'] if 'database' in ptr else str(Path(ptr['directory'])/ptr['database_file']))
        check(sha(db)==ptr['sha256'],'database '+name)
    check(len(data)==24 and len({r['source_family'] for r in data})==19,'24 rows19 sources')
    check(all(r['source_family']!='doi:10.1039/d1ma00679g' for r in data),'P75 external held outside training')
    lookup = {r['row_id']:r for r in data}
    for e in events:
        held = e['source']
        check(all(lookup[r]['source_family']!=held for r in e['train']),'training isolation '+e['route']+held+e['model'])
        check(all(r['source_family']==held for r in e['predictions']),'test isolation '+e['route']+held+e['model'])
        check(all(lookup[r.removesuffix('::observed_midpoint')]['source_family']!=held for r in e['extra']),
              'auxiliary isolation '+e['route']+held+e['model'])
    check(len(events)==plan['planned_fits']==60,'60 fits')
    check(all(e['status']=='complete' and not e['warnings'] for e in events),'zero failures and warnings')
    for method,rows in predictions.items():
        check(len(rows)==len({r['row_id'] for r in rows})==24,'coverage '+method)
        for cohort,section in results['results'][method].items():
            selected = [r for r in rows if (not cohort.startswith('old') or r['row_id'] in plan['old_ids'])
                        and (cohort in ('old23','expanded24') or lookup[r['row_id']]['static_features']['concentration_mol_L']>=2)]
            for k,v in score(selected).items():
                check(abs(v-section['metrics'][k])<1e-9,'arithmetic '+method+cohort+k)
    result = dict(status='passed',checks=checks,fit_count=60,new_fits_in_verification=0,
                  model_outputs_recalculated=True,raw_databases_hash_protected=True,
                  limits='Arithmetic, provenance hashes and split isolation checked; no independent remeasurement of figure pixels, new experimental validation or estimator refit.',
                  inputs={p.name:sha(p) for p in OUT.glob('*.json') if p.name!='verification.json'})
    with (OUT/'verification.json').open('x',encoding='utf-8') as h:
        json.dump(result,h,ensure_ascii=False,indent=2)
        h.write('\n')
    print(len(checks),'checks passed')


if __name__=='__main__':
    main()
