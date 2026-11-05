"""Audit the current retention direction with stored predictions and no estimator fits."""

from collections import defaultdict
import math
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.retention_sawdust_verify_v31 import exact_score
from tools.retention_sawdust_development_v31 import BASE, OUT as P31, ROOT, read, sha, write
from tools.retention_horizon_normalization_v19 import OUT as P19, gates, neighborhood
from tools.verify_retention_v3b import wts


P33 = BASE / '第三十三轮_刊本原图盲态复核_20261105' / 'native_curve_evidence.json'
OUT = BASE / '第三十四轮_阶段诊断与研究转向_20261106'


def ranked_source_budget(predictions, baselines, criteria):
    """Bound the number of perfect source repairs needed for the two squared-error gates."""
    w = wts(predictions)
    observed = np.array([r['observed'] for r in predictions])
    predicted = np.array([r['predicted'] for r in predictions])
    variance = float(np.dot(w, (observed - np.dot(w, observed))**2))
    r2_budget = (1 - criteria['r2_gt']) * variance
    rmse_budget = criteria['rmse_pp_max']**2
    by_source = defaultdict(float)
    for r, e in zip(predictions, w * (predicted - observed)**2, strict=True):
        by_source[r['source_family']] += float(e)
    order = sorted(by_source, key=lambda s: (-by_source[s], s))
    total = sum(by_source.values())
    remaining = total
    for k, source in enumerate(order, start=1):
        remaining -= by_source[source]
        if remaining < r2_budget and remaining <= rmse_budget:
            break
    repaired = set(order[:k])
    optimistic = [dict(r, predicted=r['observed']) if r['source_family'] in repaired else r for r in predictions]
    score = exact_score(optimistic)
    assert math.isclose(score['rmse']**2, remaining, abs_tol=1e-10)
    assert remaining + by_source[order[k-1]] >= r2_budget or remaining + by_source[order[k-1]] > rmse_budget
    return dict(current_weighted_mse_pp2=total, r2_implied_mse_limit_pp2=r2_budget, rmse_limit_pp2=rmse_budget,
                mse_share_top1=by_source[order[0]] / total,
                mse_share_top3=sum(by_source[s] for s in order[:3]) / total,
                min_perfect_source_repairs_for_squared_error_gates=k,
                source_squared_error_contributions=[dict(source=s, weighted_mse_pp2=by_source[s]) for s in order],
                other_gates_after_these_repairs=gates(optimistic, score, baselines, criteria, len(predictions)))


def coverage(rows, spec):
    checks = neighborhood(rows, spec)
    low = [r for r in rows if r['target'] <= 80]
    long = [r for r in rows if r['features']['target_cycle_count'] >= 5000]
    hard = {r['row_id'] for r in low} & {r['row_id'] for r in long}
    close = [a for a in checks if a.get('distance', math.inf) <= 1]
    pairs = {tuple(sorted((a['row_id'], a['neighbor_id']))): a['target_gap_pp'] for a in close}
    return dict(rows=len(rows), sources=len({r['source_family'] for r in rows}), low_rows=len(low),
                long_horizon_rows=len(long), long_low_rows=len(hard),
                long_low_sources=len({r['source_family'] for r in rows if r['row_id'] in hard}),
                close_pair_count=len(pairs), close_pairs_gap_gt_5=sum(v > 5 for v in pairs.values()),
                long_low_nearest=[a for a in checks if a['row_id'] in hard],
                row_level_nearest=checks)


def main():
    goal = BASE / 'research_goal.json'
    paths = [goal, P33, P19/'training_plan.json', *(P31/f for f in ('input_snapshot.json', 'training_plan.json',
                    'heldout_predictions.json', 'results.json', 'independent_verification.json'))]
    criteria = read(goal)['criteria']
    earlier = read(P31/'training_plan.json')
    assert earlier['criteria'] == criteria
    result = read(P31/'results.json')
    stored = read(P31/'heldout_predictions.json')
    data = read(P31/'input_snapshot.json')
    spec = read(P19/'training_plan.json')['neighborhood']
    systems = {}
    for system, rows in data.items():
        detail = result['scores'][system]
        assert set(detail['results']) == set(stored[system]['loso'])
        baselines = {name: exact_score(p) for name, p in stored[system]['baselines'].items()}
        outcomes = {}
        for name, forecasts in stored[system]['loso'].items():
            prior = detail['results'][name]
            assert {r['row_id']:r['observed'] for r in forecasts} == {r['row_id']:r['target'] for r in rows}
            values = exact_score(forecasts)
            assert values == prior['full'] and baselines == detail['baselines']
            outcomes[name] = dict(values=values, matched_mae_change=prior['common_mae_change'],
                                  gate_passes=prior['gates'], budget=ranked_source_budget(forecasts, baselines, criteria))
        systems[system] = dict(primary=detail['primary'], diagnostics=outcomes, baselines=baselines,
                               coverage=coverage(rows, spec), numeric_passes=detail['numeric_passes'])
    coffee = read(P33)
    assert coffee['system']=='2E' and coffee['source_family'] not in {r['source_family'] for r in data['2E']}
    query = dict(row_id='coffee_pending', source_family=coffee['source_family'], target=coffee['author_reported_retention_pct'],
                 features=coffee['windows']['0.2']['features'])
    candidate = neighborhood([*data['2E'], query], spec)[-1]
    assert candidate['row_id']==query['row_id']
    if 'neighbor_id' in candidate:
        peer = next(r for r in data['2E'] if r['row_id'] == candidate['neighbor_id'])
        candidate['neighbor_static_features'] = peer['static_features']
        candidate['coffee_static_features'] = coffee['static_features']
    OUT.mkdir(exist_ok=True)
    write(OUT/'direction_audit.json', dict(status='retrospective_no_fits', systems=systems,
          coffee_neighbor_before_training=candidate, neighbor_scale=spec, numeric_passes=result['numeric_passes'],
          external_acceptances=result['external_sources'], new_fits=0, goal_achieved=False,
          squared_error_budget_limit='Sets highest-error whole sources to perfect predictions only in arithmetic. '
                                      'Existing outcomes, samples, and weights are fixed. This is not a model-performance ceiling.',
          protected={p.relative_to(ROOT).as_posix():sha(p) for p in paths}))


if __name__ == '__main__':
    main()
