"""Verify current APIs and preserve the wrong-metric study as immutable history."""
from pathlib import Path
import ast
import hashlib
import json
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from data.retention_research import load_windows
from data.training_latest import open_training_datasets
from tools.retention_shape_v4 import SIX

BASE = ROOT / '保持率达标研究_v3_主线与近优组合_20261030'
RUN = BASE / '第十二轮_扩充双电极来源验证'
BATCH = BASE / '第十一轮_双电极原文曲线补充/batch5_指标纠错_20261031'
EID = 'v25:Mango_MK9_2E_C100000'


def read(p):
    return json.loads(p.read_text('utf8'))


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    checks = []

    def ck(name, ok):
        if not ok:
            raise AssertionError(name)
        checks.append(name)

    receipt = read(RUN / 'post_fit_data_correction_receipt.json')
    protected = read(RUN / 'source_protection.json')
    for name, expected in protected.items():
        replacement = receipt['pointer_substitutions'].get(name)
        p = ROOT / (replacement['frozen_pointer_archive'] if replacement else name)
        ck('frozen_object:' + name, sha(p) == expected)
        if replacement:
            ck('current_pointer:' + name, sha(ROOT / name) == replacement['current_pointer_sha256'])
    for name, key in [('input_snapshot.json', 'frozen_input_snapshot_sha256'),
                      ('results.json', 'frozen_results_sha256'),
                      ('heldout_predictions.json', 'frozen_predictions_sha256'),
                      ('independent_verification.json', 'frozen_technical_audit_sha256')]:
        ck('frozen_fit_payload:' + name, sha(RUN / name) == receipt[key])

    canonical = read(ROOT / 'data/current_training_latest.json')
    with open_training_datasets() as store:
        ck('canonical_integrity', store.connection.execute('PRAGMA main.integrity_check').fetchone()[0] == 'ok')
        ck('canonical_FKs', not store.connection.execute('PRAGMA main.foreign_key_check').fetchall())
        row = json.loads(store.connection.execute('SELECT record_json FROM cycle_records WHERE endpoint_id=?', (EID,)).fetchone()[0])
        ck('current_retention65_CE79point3', row['retention_pct'] == 65 and row['co_reported_coulombic_efficiency_pct'] == 79.3)
        inputs = [json.loads(r[0]) for r in store.connection.execute('SELECT record_json FROM inputs WHERE row_id=?', (EID,))]
        ck('four_current_training_profiles', len(inputs) == 4 and all(r['target'] == 65 for r in inputs))

    old = read(RUN / 'input_snapshot.json')
    current, counts = {}, {}
    for system, fraction, expected in [('2E', .2, (27, 22)), ('2E', .1, (23, 18)), ('3E', .2, (30, 24)), ('3E', .1, (20, 19))]:
        rows = load_windows(system, fraction, include_shape=True)
        route = f'B_{system}_early{int(100*fraction)}'
        counts[route] = [len(rows), len({r['source_family'] for r in rows})]
        ck('current_coverage:' + route, tuple(counts[route]) == expected)
        ck('no_active_duplicate:' + route, len(rows) == len({r['endpoint_id'] for r in rows}))
        if system != '2E':
            continue
        current[route] = []
        for r in rows:
            q = dict(row_id=r['endpoint_id']+'::early'+str(int(100*fraction)), endpoint_id=r['endpoint_id'], source_family=r['source_family'], curve_id=r['curve_id'], material_key=r['source_family']+'::'+r['sample_name'], sample_name=r['sample_name'], system=system, target=r['target_retention_pct'], features={k:r[k] for k in SIX}, static_features=r['static_features'], last_early=r['last_early_retention_pct'], linear_forecast=r['last_early_retention_pct']+r['early_retention_slope_per_1000_cycles']*(r['target_cycle_count']-r['early_observed_cycle_count'])/1000, fraction=fraction, point_indices=r['point_indices'], early_points=r['early_points'], reading_bound_pp=r['maximum_reading_bound_pp'], shape_features=r['shape_features'])
            current[route].append(q)
        if fraction == .1:
            ck('10pct_snapshot_exactly_unchanged', current[route] == old[route])
            ck('10pct_has_no_MK9', not any(r['endpoint_id'] == EID for r in rows))
        else:
            changed = [a['endpoint_id'] for a, b in zip(current[route], old[route]) if a != b]
            ck('20pct_only_MK9_changed', len(current[route]) == len(old[route]) and changed == [EID])
            q = next(r for r in rows if r['endpoint_id'] == EID)
            ck('20pct_uses_blue_four_positions_target65', q['target_retention_pct'] == 65 and len(q['early_points']) == 4 and q['curve_id'].startswith('metric_v3h:'))

    p = read(ROOT / 'data/current_retention_research.json')
    with sqlite3.connect((ROOT / p['database']).as_uri()+'?mode=ro', uri=True) as db:
        ck('research_integrity', db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok')
        ck('research_FKs', not db.execute('PRAGMA foreign_key_check').fetchall())
        ck('oldCE_inactive', db.execute('SELECT approved FROM curves WHERE curve_id=?', ('marker_v2:'+EID,)).fetchone()[0] == 0)
    ck('6400_original_events_preserved', sum(1 for _ in (RUN / 'fit_events.jsonl').open('rb')) == 6400)
    ck('no_corrected_model_fits_claimed', read(RUN / 'completion.json')['post_correction_model_fits'] == 0)
    ck('separate_proposal_not_frozen', not read(RUN / 'completion.json')['correction_validation_plan_frozen'])
    for file in ['correct_MK9_metric_v8.py', 'build_retention_curve_store_v3h.py', 'diagnose_retention_expanded2e_v6.py', 'publish_retention_metric_correction_v9.py', 'report_retention_expanded2e_live_v6.py', 'verify_retention_metric_closeout_v9.py']:
        ast.parse((ROOT / 'tools' / file).read_text('utf8'))
        ck('AST:' + file, True)
    result = dict(status='passed', checks=len(checks), protected_frozen_objects=len(protected), check_names=checks, current_canonical=canonical['version'], current_research=p['version'], current_coverage=counts, old20pct_scientific_result_valid=False, corrected_data_model_fits=0, correction_revalidation_frozen=False, goal_status='active')
    (BATCH / 'closeout_verification.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', 'utf8')
    print(json.dumps({k:v for k,v in result.items() if k != 'check_names'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
