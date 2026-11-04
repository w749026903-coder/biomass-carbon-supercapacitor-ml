"""Audit squared error on archived source-held-out predictions without refitting."""

import json
import math
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.verify_retention_v3b import BASE, read, sha, wts


ARCHIVES = (
    ('P17', '第十七轮_三电极衰减尾部开发_20261104', '3E', 'full',
     32, 26, 'doi:10.3390/nano16211412', (55.0,)),
    ('P19', '第十九轮_剩余圈数目标对照_20261105', '3E', 'variant',
     32, 26, 'doi:10.3390/nano16211412', (55.0,)),
    ('P21', '第二十一轮_DDHPC双电极来源扩充_20261105', '2E', 'full',
     29, 23, 'doi:10.1039/c9ra06603a', (56.0, 65.0)),
)


def audit():
    goal_path = BASE / 'research_goal.json'
    criteria = read(goal_path)['criteria']
    receipt = {
        'input_sha256': {goal_path.relative_to(ROOT).as_posix(): sha(goal_path)},
        'new_fits': 0,
        'new_external_acceptances': 0,
        'scope': 'Fixed archived development predictions. Keep all targets, rows and weights.',
        'method': ('Compare the specified held source contribution w*error^2 against '
                   'the stricter of (1-R2_min)*weighted_target_variance and RMSE_max^2. '
                   'Best-case bounds condition on keeping the specified archived errors.'),
        'archives': {},
    }
    identities = {}
    for phase, dirname, system, metric_key, n, groups, source, expected in ARCHIVES:
        pred_path = BASE / dirname / 'heldout_predictions.json'
        scores_path = BASE / dirname / 'results.json'
        for path in (pred_path, scores_path):
            receipt['input_sha256'][path.relative_to(ROOT).as_posix()] = sha(path)
        by_model = read(pred_path)
        scores = read(scores_path)
        assert len(scores['results']) == 8
        configs = {}
        for model, archived in scores['results'].items():
            rows = by_model[model]
            assert len(rows) == len({r['row_id'] for r in rows}) == n
            assert len({r['source_family'] for r in rows}) == groups
            assert {r['route'] for r in rows} == {system}
            identity = {r['row_id']: (r['source_family'], r['curve_id'], r['observed']) for r in rows}
            assert identities.setdefault(system, identity) == identity
            w = wts(rows)
            assert math.isclose(float(w.sum()), 1.)
            y = np.array([r['observed'] for r in rows])
            err = np.array([r['predicted'] for r in rows]) - y
            assert np.isfinite(err).all()
            tail = np.array([r['source_family'] == source for r in rows])
            assert tuple(sorted(y[tail])) == expected
            assert math.isclose(float(w[tail].sum()), 1. / groups)
            var = float(np.dot(w, (y - np.dot(w, y)) ** 2))
            contribution = w * err ** 2
            mse = float(contribution.sum())
            source_mse = float(contribution[tail].sum())
            other_mse = float(contribution[~tail].sum())
            assert math.isclose(mse, source_mse + other_mse)
            assert math.isclose(math.sqrt(mse), archived[metric_key]['rmse'], abs_tol=1e-9)
            assert math.isclose(1 - mse / var, archived[metric_key]['r2'], abs_tol=1e-9)
            r2_budget = (1 - criteria['r2_gt']) * var
            rmse_budget = criteria['rmse_pp_max'] ** 2
            configs[model] = {
                'source_signed_errors_pp': err[tail].tolist(),
                'full_weighted_mse_pp2': mse,
                'source_weighted_mse_pp2': source_mse,
                'source_share_of_full_mse': source_mse / mse,
                'rmse_floor_if_other_sources_perfect_pp': math.sqrt(source_mse),
                'r2_ceiling_if_other_sources_perfect': 1 - source_mse / var,
                'r2_ceiling_if_tail_source_perfect': 1 - other_mse / var,
                'joint_r2_rmse_impossible_if_tail_errors_unchanged': (
                    source_mse >= r2_budget or source_mse > rmse_budget),
                'joint_r2_rmse_impossible_if_other_errors_unchanged': (
                    other_mse >= r2_budget or other_mse > rmse_budget),
            }
        receipt['archives'][phase] = {
            'system': system, 'rows': n, 'sources': groups, 'source_family': source,
            'weighted_target_variance_pp2': var, 'r2_strict_mse_budget_pp2': r2_budget,
            'rmse_mse_budget_pp2': rmse_budget, 'primary': scores['primary'],
            'source_rmse_limit_if_other_sources_perfect_pp': math.sqrt(groups * min(r2_budget, rmse_budget)),
            'configs': configs,
        }
    return receipt


if __name__ == '__main__':
    print(json.dumps(audit(), ensure_ascii=False, indent=2, allow_nan=False))
