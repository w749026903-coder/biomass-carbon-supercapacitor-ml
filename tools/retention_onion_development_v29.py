"""Frozen 2E development addition and paired transfer check for onion carbon."""

import argparse
import json
import math
from pathlib import Path
import sys
import warnings

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.prepare_small_sample_routes import now, read, sha, write
from tools.retention_corrected2e_v13 import environment
from tools.retention_ddhpc_development_v21 import BASE, BASELINES, OUT as P21
from tools.retention_horizon_normalization_v19 import gates, paired_error
from tools.retention_shape_v4 import Encoder, SIX, estimator, expressed, metrics, predicted, weights
from tools.verify_retention_v3b import score

P28 = BASE / '第二十八轮_SSC700出版社原图补证_20261105'
OUT = BASE / '第二十九轮_洋葱花籽双电极扩充_20261105'
JOINT_FOLD = 'onion_and_DDHPC'


def freeze():
    assert not OUT.exists(), 'Never replace a frozen plan or a past result'
    parent = read(P21 / 'training_plan.json')
    previous = read(P21 / 'input_snapshot.json')
    assert (previous['system'], previous['fraction'], parent['environment']) == ('2E', .2, environment())
    old = previous['rows']
    assert (len(old), len({r['source_family'] for r in old})) == (29, 23)
    ddhpc = previous['source']
    assert sorted(r['target'] for r in old if r['source_family'] == ddhpc) == [56., 65.]
    p28 = P28 / 'onion_2e_evidence.json'
    evidence = read(p28)
    assert evidence['status'] == 'ready_for_separately_frozen_2E_development_sensitivity'
    assert sha(p28) == 'a1dcbb3e64bbb6a3c0599216952cba891d3eeef3fd2afb6cfe09ddbf29ed3397'
    assert sha(ROOT / evidence['pdf']) == evidence['pdf_sha256']
    sample = evidence['known_endpoint']
    onion = evidence['source_family']
    assert onion not in {r['source_family'] for r in old}
    assert (sample['system'], sample['target_cycle_count'], sample['retention_pct']) == ('2E', 10000, 74.40)
    assert evidence['windows']['0.2']['markers'] == 9
    f = evidence['windows']['0.2']['features']
    assert set(f) == set(SIX) and f['target_cycle_count'] == sample['target_cycle_count']
    key = f'development:{onion}::{sample["sample_name"]}'
    addition = dict(row_id=key+'::early20', endpoint_id=key, curve_id=key, material_key=key,
                    source_family=onion, sample_name=sample['sample_name'], target=sample['retention_pct'],
                    last_early=f['last_early_retention_pct'], features=f, static_features=evidence['static_features'],
                    role='development_only_author_reported')
    rows = old + [addition]
    sources = sorted({r['source_family'] for r in rows})
    configs = parent['configurations']
    assert len(sources) == 24 and len(configs) == 8 and all(c['target'] == 'delta' for c in configs)
    assert all(r['features']['early_observed_cycle_count'] <= .2*r['features']['target_cycle_count'] for r in rows)
    folds = {}
    for label, held in [(s, [s]) for s in sources] + [(JOINT_FOLD, [onion, ddhpc])]:
        folds[label] = dict(test_sources=held, train_ids=[r['row_id'] for r in rows if r['source_family'] not in held],
                            test_ids=[r['row_id'] for r in rows if r['source_family'] in held])
    assert folds[JOINT_FOLD]['train_ids'] == [r['row_id'] for r in old if r['source_family'] != ddhpc]
    guarded = [Path(__file__), p28, ROOT / evidence['pdf'], BASE / 'research_goal.json',
               *(P21 / file for file in ('input_snapshot.json', 'training_plan.json', 'heldout_predictions.json', 'results.json')),
               *(ROOT / f'tools/{name}.py' for name in ('prepare_small_sample_routes', 'retention_corrected2e_v13',
                     'retention_ddhpc_development_v21', 'retention_horizon_normalization_v19', 'retention_shape_v4',
                     'retention_v3_optimizer', 'run_small_sample_routes', 'verify_retention_v3b'))]
    for name in ('current_retention_research.json', 'current_training_latest.json'):
        ptr = ROOT / 'data' / name
        d = read(ptr)
        db = ROOT / (d['database'] if 'database' in d else Path(d['directory']) / d['database_file'])
        assert sha(db) == d['sha256']
        guarded.extend([ptr, db])
    OUT.mkdir()
    snapshot = OUT / 'input_snapshot.json'
    write(snapshot, dict(system='2E', fraction=.2, rows=rows, old_rows=29, onion_source=onion, ddhpc_source=ddhpc))
    guarded.append(snapshot)
    plan = dict(frozen_at=now(), environment=environment(), folds=folds, configurations=configs,
                primary=parent['primary'], planned_outer_fits=len(sources)*len(configs), planned_joint_fits=len(configs),
                exact_reference_folds=23*len(configs), exact_reference_endpoints=29*len(configs),
                protected={p.relative_to(ROOT).as_posix():sha(p) for p in guarded},
                criteria=read(BASE / 'research_goal.json')['criteria'], baselines=BASELINES,
                bootstrap=dict(draws=10000, seed=20261105, interval=[.025,.975], unit='source'),
                scope='Approved 2E early20 six-summary and static branches; original target, features and weights.',
                comparisons=('P21 and expanded LOSO on identical 29 endpoints; complete 30 separately. '
                             'One prespecified joint held fold for the two hard sources. Its results stay outside '
                             'the LOSO metric and are compared against single held-source predictions.'),
                limitations='Onion target already observed. The single and joint folds are development only; new external acceptances zero.',
                no_selection='Fixed GPR primary; all 8 configurations reported without outer-result selection.',
                other_routes='A, 3E, and early10 kept separate; SSC-700 pending primary cycling protocol.')
    write(OUT / 'training_plan.json', plan)
    write(OUT / 'freeze_receipt.json', dict(plan_sha256=sha(OUT / 'training_plan.json'), fits_at_freeze=0))


def checked_plan():
    plan = read(OUT / 'training_plan.json')
    assert sha(OUT / 'training_plan.json') == read(OUT / 'freeze_receipt.json')['plan_sha256']
    assert environment() == plan['environment']
    assert all(sha(ROOT / p) == digest for p, digest in plan['protected'].items())
    return plan


def subsets(split, lookup):
    train, test = ([lookup[k] for k in split[kind]] for kind in ('train_ids', 'test_ids'))
    assert len(train)+len(test) == len(lookup)
    assert {r['source_family'] for r in test} == set(split['test_sources'])
    assert not {r['source_family'] for r in train} & set(split['test_sources'])
    assert not {r['curve_id'] for r in train} & {r['curve_id'] for r in test}
    return train, test


def run():
    plan = checked_plan()
    lookup = {r['row_id']:r for r in read(OUT / 'input_snapshot.json')['rows']}
    with (OUT / 'run_claim.json').open('x', encoding='utf-8') as f:
        json.dump(dict(started_at=now(), plan_sha256=sha(OUT / 'training_plan.json')), f)
    events = []
    for label, split in plan['folds'].items():
        train, test = subsets(split, lookup)
        w = weights(train)
        delta = np.array([r['target']-r['last_early'] for r in train])
        center = float(np.average(delta, weights=w))
        scale = float(np.sqrt(np.average((delta-center)**2, weights=w))) or 1.
        for config in plan['configurations']:
            event = dict(fold=label, config=config['id'], fit_attempted=False)
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter('always')
                try:
                    x_train = [expressed(r, config, 'six') for r in train]
                    x_test = [expressed(r, config, 'six') for r in test]
                    encoder = Encoder().fit(x_train)
                    model = estimator(config)
                    mass = w * len(train)
                    kw = {'sample_weight':mass}
                    if config['kind'] == 'GPR':
                        model.set_params(alpha=config['parameters']['alpha']/mass)
                        kw = {}
                    x, xt = encoder.transform(x_train), encoder.transform(x_test)
                    event['fit_attempted'] = True
                    model.fit(x, (delta-center)/scale, **kw)
                    y = model.predict(xt)*scale + center + np.array([r['last_early'] for r in test])
                    assert len(y) == len(test) and np.isfinite(y).all()
                    event.update(status='complete', predictions=y.tolist())
                except Exception as exc:
                    event.update(status='failed', error=repr(exc))
            event['warnings'] = [str(item.message) for item in caught]
            events.append(event)
    assert len(events) == plan['planned_outer_fits'] + plan['planned_joint_fits']
    checked_plan()
    write(OUT / 'fit_events.json', events)


def verify():
    plan = checked_plan()
    data = read(OUT / 'input_snapshot.json')
    rows, onion, ddhpc = data['rows'], data['onion_source'], data['ddhpc_source']
    lookup = {r['row_id']:r for r in rows}
    controls = read(P21 / 'heldout_predictions.json')
    archived = read(P21 / 'results.json')['results']
    events = read(OUT / 'fit_events.json')
    index = {(e['fold'],e['config']):e for e in events}
    configs = [c['id'] for c in plan['configurations']]
    assert len(index) == len(events) == 200 and set(index) == {(f,c) for f in plan['folds'] for c in configs}
    predictions = {c:[] for c in configs}
    joint = {c:[] for c in configs}
    baselines = {b:[] for b in BASELINES}
    checks = 0
    for label, split in plan['folds'].items():
        train, test = subsets(split, lookup)
        destination = joint if label == JOINT_FOLD else predictions
        if label != JOINT_FOLD:
            mean = float(np.average([r['target'] for r in train], weights=weights(train)))
            for r in test:
                f = r['features']
                linear = r['last_early']+f['early_retention_slope_per_1000_cycles']*(f['target_cycle_count']-f['early_observed_cycle_count'])/1000.
                for b, value in zip(BASELINES, (mean,r['last_early'],linear)):
                    baselines[b].append(predicted('2E', b, r, value))
        for key, preds in destination.items():
            e = index[label,key]
            if e['status'] == 'complete':
                assert e['fit_attempted'] and len(e['predictions']) == len(test)
                preds.extend(predicted('2E', key, r, y) for r,y in zip(test,e['predictions']))
            checks += 1
    base = {k:score(v) for k,v in baselines.items()}
    results = {}
    for key, preds in predictions.items():
        if len(preds) != len(rows) or len(joint[key]) != 3:
            results[key] = dict(complete=False, numeric_pass=False)
            continue
        assert {r['row_id']:r['observed'] for r in preds} == {r['row_id']:r['target'] for r in rows}
        common = [p for p in preds if p['source_family'] != onion]
        control = controls[key]
        assert {r['row_id']:r['observed'] for r in common} == {r['row_id']:r['observed'] for r in control}
        old_score, full = score(control), score(preds)
        assert old_score == archived[key]['full']
        independent = metrics(preds)
        assert all(math.isclose(v, independent[k], abs_tol=1e-9) for k,v in full.items())
        single = {r['row_id']:r for r in preds if r['source_family'] in (onion,ddhpc)}
        control_idx = {r['row_id']:r for r in control}
        transfer = []
        for p in joint[key]:
            r = single[p['row_id']]
            if r['source_family'] == ddhpc:
                assert math.isclose(p['predicted'], control_idx[p['row_id']]['predicted'], abs_tol=1e-8)
            transfer.append(dict(row_id=r['row_id'], sample_name=r['sample_name'], source=r['source_family'],
                                 observed=r['observed'], single_hold_prediction=r['predicted'], joint_hold_prediction=p['predicted'],
                                 absolute_error_change_with_other_source_pp=(abs(r['predicted']-r['observed'])-
                                                                            abs(p['predicted']-p['observed']))))
            checks += 1
        gate = gates(preds, full, base, plan['criteria'], len(rows))
        results[key] = dict(complete=True, control_common=old_score, expanded_common=score(common), full=full,
                            common_mae_change=paired_error(common, control, plan['bootstrap']),
                            cross_source_transfer=transfer, gates=gate, numeric_pass=all(gate.values()))
        checks += 11
    assert not (OUT / 'results.json').exists()
    write(OUT / 'heldout_predictions.json', dict(loso=predictions, joint=joint, baselines=baselines))
    write(OUT / 'results.json', dict(status='verified_development', primary=plan['primary'],
          new_fits=sum(e['fit_attempted'] for e in events), failures=sum(e['status'] != 'complete' for e in events),
          warnings=sum(len(e['warnings']) for e in events), checks=checks, baselines=base, results=results,
          numeric_passes=sum(r['numeric_pass'] for r in results.values()), external_sources=0, goal_achieved=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('step', choices=['freeze','run','verify'])
    {'freeze':freeze, 'run':run, 'verify':verify}[parser.parse_args().step]()
