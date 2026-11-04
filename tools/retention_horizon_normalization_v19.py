"""Compare one horizon-normalized target against the frozen P17 controls."""

from pathlib import Path
import json
import math
import sys
import warnings

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.retention_tail_development_v17 import BASE, OUT as P17, PRIMARY, BASELINES
from tools.retention_corrected2e_v13 import environment
from tools.retention_shape_v4 import Encoder, estimator, expressed, metrics, predicted, weights
from tools.prepare_small_sample_routes import read, write, sha, now
from tools.verify_retention_v3b import score

OUT = BASE / '第十九轮_剩余圈数目标对照_20261105'
OBSERVED = 'early_observed_cycle_count'
HORIZON = 'target_cycle_count'


def protect(plan):
    assert all(sha(ROOT / file) == digest for file, digest in plan['protected'].items())
    assert environment() == plan['environment']


def freeze():
    assert not OUT.exists()
    parent = read(P17 / 'training_plan.json')
    data = read(P17 / 'input_snapshot.json')
    assert data['system'] == '3E' and data['fraction'] == .2
    rows = data['rows']
    configs = parent['configurations']
    sources = sorted({r['source_family'] for r in rows})
    assert (len(rows), len(sources), len(configs)) == (32, 26, 8)
    assert len({r['row_id'] for r in rows}) == len(rows)
    assert all(r['features'][OBSERVED] <= .2 * r['features'][HORIZON] for r in rows)
    assert parent['environment'] == environment()
    assert all(c['target'] == 'delta' for c in configs)
    guarded = [Path(__file__), BASE / 'research_goal.json',
               *(P17 / f for f in ('training_plan.json', 'input_snapshot.json', 'results.json',
                                    'heldout_predictions.json', 'fit_events.json', 'completion.json')),
               *(ROOT / f for f in ('data/current_training_latest.json', 'data/current_retention_research.json',
                                    'tools/retention_v3_optimizer.py', 'tools/run_small_sample_routes.py',
                                    'tools/retention_shape_v4.py', 'tools/verify_retention_v3b.py',
                                    'tools/retention_tail_development_v17.py', 'tools/retention_corrected2e_v13.py'))]
    plan = dict(frozen_at=now(), system='3E', early_fraction=.2, rows=32, sources=sources,
                configurations=configs, primary=PRIMARY, planned_new_fits=208, reused_control_fits=208,
                environment=environment(), criteria=read(BASE / 'research_goal.json')['criteria'],
                protected={p.relative_to(ROOT).as_posix(): sha(p) for p in guarded},
                target='z=(retention_at_N-last_early)/log1p((N-N_observed)/1000); exact inverse in pp, no clipping',
                contrast='Only fitted target changes. Exact P17 predictions on identical whole-source splits. All data and difficulties retained.',
                inference='Predeclared GPR primary. Fixed-family exploration on seen development sources. No reselection using outer scores.',
                neighborhood=dict(horizon_ratio_max=1.10, last_pp=2, early_mean_pp=2, nominal_window_trend_pp=2,
                                  range_pp=2, observed_fraction=.04, distance='RMS across 5 scaled differences',
                                  role='Outcome-blind nearest other source per row; inspect target gap only afterward. Descriptive.'),
                bootstrap=dict(draws=10000, seed=20261105, unit='source', interval=[.025,.975]),
                external_sources=0, other_routes='A, 2E, 10% and prior alternatives retained as separate research routes')
    OUT.mkdir()
    write(OUT / 'training_plan.json', plan)
    write(OUT / 'freeze_receipt.json', dict(plan_sha256=sha(OUT / 'training_plan.json'), fits_at_freeze=0))


def factor(row):
    f = row['features']
    return math.log1p((f[HORIZON] - f[OBSERVED]) / 1000.)


def groups(rows, field):
    result = {}
    for row in rows:
        result.setdefault(row[field], []).append(row)
    return result


def paired_error(variant, control, bootstrap):
    other = groups(control, 'source_family')
    changes = []
    for source, rows in sorted(groups(variant, 'source_family').items()):
        a, b = get_mae(rows), get_mae(other[source])
        changes.append(a - b)
    changes = np.array(changes)
    rng = np.random.default_rng(bootstrap['seed'])
    draws = rng.choice(changes, (bootstrap['draws'], len(changes)), replace=True).mean(axis=1)
    return dict(delta_mae_pp=float(changes.mean()), percentile_interval_pp=np.quantile(draws, bootstrap['interval']).tolist())


def get_mae(rows):
    errors = [abs(r['observed'] - r['predicted']) for r in rows]
    return float(np.dot(weights(rows), errors))


def neighborhood(rows, spec):
    def inputs(row):
        f = row['features']
        return np.array([f['last_early_retention_pct'] / spec['last_pp'],
                         f['early_mean_retention_pct'] / spec['early_mean_pp'],
                         f['early_retention_slope_per_1000_cycles'] * (.2 * f[HORIZON] / 1000.) / spec['nominal_window_trend_pp'],
                         f['early_retention_range_pp'] / spec['range_pp'],
                         (f[OBSERVED] / f[HORIZON]) / spec['observed_fraction']])

    projected = {r['row_id']: inputs(r) for r in rows}
    result = []
    for row in rows:
        candidates = []
        n = row['features'][HORIZON]
        for other in rows:
            if other['source_family'] == row['source_family']:
                continue
            m = other['features'][HORIZON]
            if max(n, m) / min(n, m) > spec['horizon_ratio_max']:
                continue
            gap = np.abs(projected[row['row_id']] - projected[other['row_id']])
            candidates.append((float(np.sqrt(np.mean(gap**2))), other['row_id'], other, gap))
        q = dict(row_id=row['row_id'], source_family=row['source_family'], horizon=n, possible_neighbors=len(candidates))
        if candidates:
            d, key, other, gap = min(candidates, key=lambda c: c[:2])
            q.update(neighbor_id=key, neighbor_source=other['source_family'], neighbor_horizon=other['features'][HORIZON],
                     distance=d, scaled_feature_gaps=gap.tolist(), observed_retention_pct=row['target'],
                     neighbor_retention_pct=other['target'], target_gap_pp=abs(row['target'] - other['target']))
        result.append(q)
    return result


def gates(predictions, values, baselines, c, n):
    return dict(coverage=len({p['row_id'] for p in predictions}) == len(predictions) == n,
                positive=all(p['predicted'] > 0 for p in predictions), r2=values['r2'] > c['r2_gt'],
                mae=values['mae'] <= c['mae_pp_max'], rmse=values['rmse'] <= c['rmse_pp_max'],
                mape=values['mape_pct'] <= c['mape_pct_max'], p90ape=values['p90_ape_pct'] <= c['p90_ape_pct_max'],
                p90abs=values['p90_absolute_error'] <= c['p90_abs_pp_max'],
                tail=values['source_p90_mae'] <= c['source_p90_mae_pp_max'],
                baselines=all(1 - values['mae'] / v['mae'] >= c['mae_reduction_vs_each_baseline_min']
                              for v in baselines.values()))


def run():
    path = OUT / 'training_plan.json'
    plan = read(path)
    assert read(OUT / 'freeze_receipt.json')['plan_sha256'] == sha(path)
    protect(plan)
    rows = read(P17 / 'input_snapshot.json')['rows']
    previous = read(P17 / 'heldout_predictions.json')
    index = {(e['outer_source'], e['config_id']): e for e in read(P17 / 'fit_events.json')}
    assert len(index) == plan['reused_control_fits']
    group = groups(rows, 'source_family')
    with (OUT / 'run_claim.json').open('x', encoding='utf-8') as claim:
        json.dump(dict(started_at=now(), plan_sha256=sha(path)), claim)
    events = []
    variants = {c['id']: [] for c in plan['configurations']}
    for source in plan['sources']:
        train = [r for r in rows if r['source_family'] != source]
        test = group[source]
        assert not {r['curve_id'] for r in train} & {r['curve_id'] for r in test}
        train_ids, test_ids = ([r['row_id'] for r in subset] for subset in (train, test))
        w = weights(train)
        scaled = np.array([(r['target'] - r['last_early']) / factor(r) for r in train])
        mean = float(np.dot(w, scaled))
        sd = float(np.sqrt(np.dot(w, (scaled - mean)**2))) or 1.
        for c in plan['configurations']:
            key = c['id']
            control = index[source, key]
            assert control['status'] == 'complete' and control['train_ids'] == train_ids and control['test_ids'] == test_ids
            event = dict(index=len(events) + 1, config_id=key, outer_source=source, train_ids=train_ids, test_ids=test_ids,
                         reused_control_index=control['index'], target_center=mean, target_scale=sd)
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter('always')
                try:
                    enc = Encoder().fit([expressed(r, c, 'six') for r in train])
                    assert enc.schema == control['encoder']
                    x = enc.transform([expressed(r, c, 'six') for r in train])
                    xt = enc.transform([expressed(r, c, 'six') for r in test])
                    m = estimator(c)
                    mass = w * len(train)
                    kwargs = {'sample_weight': mass}
                    if c['kind'] == 'GPR':
                        m.set_params(alpha=c['parameters']['alpha'] / mass)
                        kwargs = {}
                    m.fit(x, (scaled - mean) / sd, **kwargs)
                    z = m.predict(xt) * sd + mean
                    values = [r['last_early'] + float(v) * factor(r) for r, v in zip(test, z)]
                    assert len(values) == len(test) and np.isfinite(values).all()
                    variants[key].extend(predicted('3E', key, r, v) for r, v in zip(test, values))
                    event.update(status='complete', latent=z.tolist(), predictions=values)
                except Exception as exc:
                    event.update(status='failed', error=repr(exc))
            event['warnings'] = [str(item.message) for item in caught]
            events.append(event)
    assert len(events) == plan['planned_new_fits']
    write(OUT / 'fit_events.json', events)
    write(OUT / 'heldout_predictions.json', variants)
    neigh = neighborhood(rows, plan['neighborhood'])
    write(OUT / 'neighborhood.json', neigh)
    base = {key: score(previous[key]) for key in BASELINES}
    reference = read(P17 / 'results.json')['results']
    targets = {r['row_id']: r['target'] for r in rows}
    results = {}
    for key, v in variants.items():
        p = previous[key]
        assert {r['row_id']: r['observed'] for r in p} == targets
        if len(v) != len(rows):
            results[key] = dict(numeric_pass=False, complete=False)
            continue
        assert {r['row_id']: r['observed'] for r in v} == targets
        values, control = score(v), score(p)
        assert control == reference[key]['full']
        independent = metrics(v)
        assert all(math.isclose(x, independent[k], rel_tol=1e-9, abs_tol=1e-9) for k, x in values.items())
        gate = gates(v, values, base, plan['criteria'], len(rows))
        results[key] = dict(complete=True, control=control, variant=values, gates=gate, numeric_pass=all(gate.values()),
                            paired_delta=paired_error(v, p, plan['bootstrap']))
    protect(plan)
    write(OUT / 'results.json', dict(status='complete_development_trial', fits=len(events),
                                    failures=sum(e['status'] != 'complete' for e in events),
                                    warnings=sum(len(e['warnings']) for e in events), primary=PRIMARY, results=results,
                                    numeric_passes=sum(r['numeric_pass'] for r in results.values()),
                                    baselines=base, external_sources=0, goal_achieved=False))
    print(results[PRIMARY])


if __name__ == '__main__':
    {'freeze': freeze, 'run': run}[sys.argv[1]]()
