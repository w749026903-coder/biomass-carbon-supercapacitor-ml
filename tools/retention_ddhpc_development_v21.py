"""Freeze and evaluate a single-source addition to the fixed 2E 20% models."""

from pathlib import Path
import gzip
import json
import math
import sys
import warnings

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.prepare_small_sample_routes import read, write, sha, now
from tools.retention_corrected2e_v13 import environment
from tools.retention_shape_v4 import Encoder, SIX, estimator, expressed, metrics, predicted, weights
from tools.retention_suaeda_case_v16 import BASE, P14, OUT as P16
from tools.retention_horizon_normalization_v19 import BASELINES, gates, paired_error
from tools.verify_retention_v3b import score

P20 = BASE / '第二十轮_DDHPC双电极刊本补证_20261105'
OUT = BASE / '第二十一轮_DDHPC双电极来源扩充_20261105'


def control_events():
    events = {}
    with gzip.open(P14 / 'fit_events.jsonl.gz', 'rt', encoding='utf-8') as stream:
        for line in stream:
            row = json.loads(line)
            if row['system'] == '2E' and row['inner_fold'] is None and row['arm'] == 'author_only':
                events[row['outer'], row['config']] = row
    assert len(events) == 176 and all(e['status'] == 'complete' for e in events.values())
    return events


def freeze():
    assert not OUT.exists()
    p14 = read(P14 / 'training_plan.json')
    assert environment() == p14['environment']
    assert sha(P14 / 'input_snapshot.json') == p14['data_sha256']
    check = read(P20 / 'verification.json')
    evidence = read(P20 / 'curve_evidence.json')
    assert sha(P20 / 'curve_evidence.json') == check['curve_evidence_sha256'] and check['ready_2E_records'] == 2
    assert evidence['system'] == '2E' and evidence['external_sources'] == 0
    assert all(sha(ROOT / f) == h for f, h in check['protected_pointers'].items())
    old = read(P14 / 'input_snapshot.json')['2E']['endpoints']
    families = {r['source_family'] for r in old}
    assert (len(old), len(families)) == (27, 22)
    source = evidence['source_family']
    assert source not in families
    add = []
    for s in evidence['samples']:
        if not s['status'].startswith('ready_'):
            continue
        key = f'development:{source}::{s["sample_name"]}'
        windows = s['windows']['0.2']
        assert windows['actual_marker_count'] == 4
        f = {k: windows[k] for k in SIX}
        add.append(dict(row_id=key+'::early20', endpoint_id=key, curve_id=key,
                        source_family=source, sample_name=s['sample_name'], material_key=key,
                        target=s['author_retention_pct'], last_early=f['last_early_retention_pct'],
                        features=f, static_features=s['static_features'], role='development_only_author_approximate'))
    assert len(add) == 2 and {r['target'] for r in add} == {65., 56.}
    rows = old + add
    assert len({r['row_id'] for r in rows}) == 29
    primary = read(P16 / 'training_plan.json')['selected']['2E']['primary']
    configs = p14['configurations']
    assert len(configs) == 8 and primary in {c['id'] for c in configs}
    archived = control_events()
    assert set(archived) == {(s,c['id']) for s in families for c in configs}
    OUT.mkdir()
    write(OUT / 'input_snapshot.json', dict(system='2E', fraction=.2, old_rows=27, source=source, rows=rows))
    guarded = [Path(__file__), OUT / 'input_snapshot.json', BASE / 'research_goal.json',
               *(P14/f for f in ('input_snapshot.json','training_plan.json','fit_events.jsonl.gz','heldout_predictions.json','results.json')),
               P16/'training_plan.json', P20/'curve_evidence.json', P20/'verification.json',
               *(ROOT/f for f in (*check['protected_pointers'], 'tools/retention_horizon_normalization_v19.py',
                                   'tools/retention_v3_optimizer.py', 'tools/retention_shape_v4.py',
                                   'tools/run_small_sample_routes.py', 'tools/verify_retention_v3b.py'))]
    plan = dict(frozen_at=now(), environment=environment(), protected={p.relative_to(ROOT).as_posix():sha(p) for p in guarded},
                sources=sorted(families|{source}), configurations=configs, primary=primary, planned_new_fits=184,
                reused_p14_control_fits=176, criteria=read(BASE/'research_goal.json')['criteria'], baselines=BASELINES,
                scope='B 2E approved early20 only; retain P14 encoder, fixed model, weights and delta target. Two P20 records from one source.',
                source_roles='DDHPC is one exposed development source; both records held together; external accepted sources = 0.',
                comparisons='Primary matched contrast uses exact original 27 endpoints; expanded 29-endpoint and DDHPC-only predictions reported separately.',
                sensitivity='DDHPC-only held-source fold: reuse the same fit, vary shared reference ordinate by ±4 px and zero axis by ±1 px; hold other pixels fixed. No selection or statistical confidence interpretation.',
                bootstrap=dict(draws=10000,seed=20261105,interval=[.025,.975],unit='source'), external_sources=0)
    write(OUT/'training_plan.json', plan)
    write(OUT/'freeze_receipt.json', dict(plan_sha256=sha(OUT/'training_plan.json'),fits_at_freeze=0))


def check_plan(plan):
    assert environment() == plan['environment']
    assert all(sha(ROOT/p) == h for p,h in plan['protected'].items())


def sensitivity_inputs(row, item, figure):
    points = [p for p in item['points'] if p['cycle_interval'][1] <= 1000.]
    x = np.array([p['cycle_reading'] for p in points])
    y_pixels = np.array([p['pixel'][1] for p in points])
    for ref_shift in (-4.,4.):
        for zero_shift in (-1.,1.):
            zero = figure['y0'] + zero_shift
            ref = item['reference']['center_y_px'] + ref_shift
            y = 100. * (zero-y_pixels)/(zero-ref)
            f = dict(row['features'], last_early_retention_pct=float(y[-1]), early_mean_retention_pct=float(y.mean()),
                     early_retention_slope_per_1000_cycles=float(np.polyfit(x,y,1)[0]*1000.),
                     early_retention_range_pp=float(np.ptp(y)))
            yield ref_shift, zero_shift, dict(row,features=f,last_early=f['last_early_retention_pct'])


def run():
    plan = read(OUT/'training_plan.json')
    assert sha(OUT/'training_plan.json') == read(OUT/'freeze_receipt.json')['plan_sha256']
    check_plan(plan)
    snapshot = read(OUT/'input_snapshot.json')
    rows, added = snapshot['rows'],snapshot['source']
    old = rows[:snapshot['old_rows']]
    archive = control_events()
    author = [p for p in read(P14/'heldout_predictions.json') if p['route']=='2E' and p['arm']=='author_only']
    evidence = read(P20/'curve_evidence.json')
    by_sample = {r['sample_name']:r for r in evidence['samples']}
    with (OUT/'run_claim.json').open('x',encoding='utf-8') as stream:
        json.dump(dict(plan_sha256=sha(OUT/'training_plan.json'),started_at=now()),stream)
    events = []
    outputs = {c['id']:[] for c in plan['configurations']}
    baselines = {b:[] for b in BASELINES}
    for source in plan['sources']:
        train = [r for r in rows if r['source_family']!=source]
        test = [r for r in rows if r['source_family']==source]
        assert not {r['curve_id'] for r in train} & {r['curve_id'] for r in test}
        w = weights(train)
        if source != added:
            assert math.isclose(sum(a for a,r in zip(w,train) if r['source_family']==added), 1./22.)
        else:
            assert train == old and len(test)==2
        d = np.array([r['target']-r['last_early'] for r in train])
        center = float(np.average(d,weights=w))
        scale = float(np.sqrt(np.average((d-center)**2,weights=w))) or 1.
        mean = float(np.average([r['target'] for r in train],weights=w))
        for r in test:
            f = r['features']
            linear = r['last_early'] + f['early_retention_slope_per_1000_cycles']*(f['target_cycle_count']-f['early_observed_cycle_count'])/1000.
            for key,value in zip(BASELINES,(mean,r['last_early'],linear)):
                baselines[key].append(predicted('2E',key,r,value))
        for c in plan['configurations']:
            key = c['id']
            control = archive.get((source,key))
            e = dict(index=len(events)+1,source=source,config_id=key,train_ids=[r['row_id'] for r in train],
                     test_ids=[r['row_id'] for r in test],control_index=control['index'] if control else None,
                     target_center=center,target_scale=scale)
            if control:
                assert e['test_ids']==control['test_ids']
                assert [r['row_id'] for r in train if r['source_family']!=added]==control['train_ids']
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter('always')
                try:
                    train_x = [expressed(r,c,'six') for r in train]
                    enc = Encoder().fit(train_x)
                    model = estimator(c)
                    mass = w*len(train)
                    kw = {'sample_weight':mass}
                    if c['kind']=='GPR':
                        model.set_params(alpha=c['parameters']['alpha']/mass)
                        kw = {}
                    model.fit(enc.transform(train_x),(d-center)/scale,**kw)
                    def predict(subset):
                        x = enc.transform([expressed(r,c,'six') for r in subset])
                        y = model.predict(x)*scale + center + np.array([r['last_early'] for r in subset])
                        assert np.isfinite(y).all() and len(y)==len(subset)
                        return y.tolist()
                    result = predict(test)
                    sensitivity = []
                    if source==added:
                        for r in test:
                            scenarios = list(sensitivity_inputs(r,by_sample[r['sample_name']],evidence['figure']))
                            ys = predict([scenario[2] for scenario in scenarios])
                            sensitivity.append(dict(row_id=r['row_id'],corners=[dict(ref_shift_px=a,zero_shift_px=b,predicted=y)
                                                                 for (a,b,_),y in zip(scenarios,ys)]))
                    outputs[key].extend(predicted('2E',key,r,p) for r,p in zip(test,result))
                    e.update(status='complete',predictions=result,reference_sensitivity=sensitivity,encoder=enc.schema)
                except Exception as exc:
                    e.update(status='failed',error=repr(exc))
            e['warnings'] = [str(v.message) for v in caught]
            events.append(e)
    assert len(events)==plan['planned_new_fits']
    write(OUT/'fit_events.json',events)
    write(OUT/'heldout_predictions.json',{**outputs,**baselines})
    results = {}
    reference = {r['method']:r for r in read(P14/'results.json')['methods'] if r['system']=='2E' and r['arm']=='author_only'}
    base = {key:score(v) for key,v in baselines.items()}
    targets = {r['row_id']:r['target'] for r in old}
    for key,out in outputs.items():
        if len(out)!=len(rows):
            results[key] = dict(complete=False,numeric_pass=False)
            continue
        common = [r for r in out if r['source_family']!=added]
        control = [r for r in author if r['method']==key]
        assert {r['row_id']:r['observed'] for r in common}=={r['row_id']:r['observed'] for r in control}==targets
        old_scores, full = score(control),score(out)
        assert all(math.isclose(value,reference[key][k],abs_tol=1e-8) for k,value in old_scores.items())
        other = metrics(out)
        assert all(math.isclose(value,other[k],abs_tol=1e-8) for k,value in full.items())
        passed = gates(out,full,base,plan['criteria'],len(rows))
        results[key] = dict(complete=True,old_common=old_scores,expanded_common=score(common),full=full,gates=passed,
                            numeric_pass=all(passed.values()),paired_delta=paired_error(common,control,plan['bootstrap']),
                            added_source_cases=[r for r in out if r['source_family']==added])
    check_plan(plan)
    write(OUT/'results.json',dict(status='complete_development_trial',fits=len(events),primary=plan['primary'],results=results,
                                 failures=sum(e['status']=='failed' for e in events), warnings=sum(len(e['warnings']) for e in events),
                                 baselines=base,numeric_passes=sum(r['numeric_pass'] for r in results.values()),
                                 external_sources=0,goal_achieved=False))
    print(results[plan['primary']])


if __name__=='__main__':
    {'freeze':freeze,'run':run}[sys.argv[1]]()
