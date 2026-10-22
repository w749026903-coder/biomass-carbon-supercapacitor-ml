"""Independent arithmetic, lineage, leakage and serialized-artifact checks; never fit."""
from pathlib import Path
from collections import Counter, defaultdict
import hashlib
import io
import json
import math
import sqlite3
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from models.v1_0.model import CORE, MATERIAL


def read(path):
    return json.loads(path.read_text('utf-8'))


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def independent_metrics(rows):
    counts = Counter(r['source_group'] for r in rows)
    total = len(counts)
    w = [1 / counts[r['source_group']] for r in rows]
    center = math.fsum(r['observed'] * weight for r, weight in zip(rows, w)) / total
    mae = math.fsum(abs(r['predicted'] - r['observed']) * weight for r, weight in zip(rows, w)) / total
    mse = math.fsum((r['predicted'] - r['observed']) ** 2 * weight for r, weight in zip(rows, w)) / total
    var = math.fsum((r['observed'] - center) ** 2 * weight for r, weight in zip(rows, w)) / total
    return {'mae': mae, 'rmse': math.sqrt(mse), 'r2': 1 - mse / var if var else None}


def verify(folder):
    import joblib
    import numpy as np
    from data.cycling_db import open_database
    folder = folder.resolve()
    plan, snapshot, results = [read(folder / p) for p in ['training_plan.json','data_snapshot.json','results.json']]
    records = snapshot['records']
    checks = 0

    def check(condition, message):
        nonlocal checks
        checks += 1
        if not condition:
            raise AssertionError(message)

    def near(a, b, message, tolerance=1e-8):
        check(abs(a-b) <= tolerance, message)

    protected_count = 0
    source_files = read(ROOT / '主集参数精提取_20261022/protected_sources.json')
    for relative, expected in source_files.items():
        check(sha(ROOT / relative) == expected, 'Original source changed: ' + relative)
    for relative, expected in read(folder / 'protected_inputs.json').items():
        check(sha(ROOT / relative) == expected, 'Protected input changed: ' + relative)
        path = ROOT / relative
        if path.name.endswith('manifest.json'):
            for payload in read(path)['outputs']:
                check(sha(ROOT / payload['path']) == payload['sha256'], 'Sealed payload changed: ' + payload['path'])
                protected_count += 1
    seal = read(folder / 'frozen_run_hashes.json')
    for relative, digest in seal.items():
        path = folder / ('training_plan.json' if relative == 'training_plan' else 'data_snapshot.json') if relative in ['training_plan','snapshot'] else ROOT / relative
        check(sha(path) == digest, 'Frozen run file changed: ' + str(path))
    with open_database() as db:
        ds = db.fetch('reported_3e')
        check(ds.fingerprint() == snapshot['dataset_fingerprint'], 'Dataset fingerprint drift')
        original = {r['endpoint_id']: r for r in ds.rows}
    for row in records:
        raw = original[row['endpoint_id']]
        for field in CORE + ['retention_pct']:
            check(raw[field] == row[field], 'Core or target changed')
        for field in MATERIAL:
            if field in ['N_at_pct','O_at_pct'] and raw.get('XPS_percentage_basis') == 'atomic_explicit':
                explicit = raw.get('XPS_' + field[0] + '_reported_pct')
                expected = raw.get(field) if explicit is None else explicit
            else:
                expected = raw.get(field)
            check(row[field] == expected, 'Material field changed or ambiguous XPS used: ' + field)
    conn = sqlite3.connect('file:' + (folder / 'evaluation.sqlite').as_posix() + '?mode=ro', uri=True)
    check(conn.execute('PRAGMA integrity_check').fetchone()[0] == 'ok', 'Checkpoint integrity')
    check(conn.execute('PRAGMA foreign_key_check').fetchall() == [], 'Checkpoint FK')
    jobs = [json.loads(p) for p, in conn.execute('SELECT payload FROM jobs ORDER BY rowid')]
    conn.close()
    check(len(jobs) == 581, 'Actual job count')
    check(sum(j['estimator_fits'] for j in jobs) == results['actual_estimator_fits'] == 534, 'Actual fit count')
    specs = {s['id']: s for s in plan['candidates']}
    held = set(plan['reserved_source_test_indices'])
    dev_predictions = defaultdict(list)
    enabled_support = defaultdict(list)
    for job in jobs:
        train, test = job['train_indices'], job['test_indices']
        tr = [records[i] for i in train]
        train_sources = {r['source_group'] for r in tr}
        check(not train_sources & {records[i]['source_group'] for i in test}, 'Source leakage')
        if job['stage'] == 'development':
            check(not held & set(train + test), 'Reserved source entered model selection')
            check(len(train_sources) == 22, 'Development training-source count')
            dev_predictions[job['candidate']] += job['predictions']
        if job['stage'] == 'reserved_source_test':
            check(set(test) == held and set(train) == set(plan['development_indices']), 'Holdout partition')
        for item in job['schema']:
            f = item['field']
            check(f in CORE + MATERIAL, 'Unexpected predictor: ' + f)
            if item['kind'] == 'categorical':
                check(item['vocabulary'] == sorted({r[f] for r in tr if r[f] is not None}), 'Held-out vocabulary leakage')
                continue
            observed = [r for r in tr if r[f] is not None]
            check(item['source_support'] == len({r['source_group'] for r in observed}), 'Support is not distinct sources')
            if f in MATERIAL:
                check(item['enabled'] == (item['source_support'] >= 5), 'Optional support threshold')
            if not item['enabled']:
                continue
            if job['stage'] == 'development' and f in MATERIAL:
                enabled_support[f].append(item['source_support'])
            values = [(r['source_group'], math.log1p(r[f]) if item['transform'] == 'log1p' else r[f]) for r in observed]
            grouped = defaultdict(list)
            for group, value in values:
                grouped[group].append(value)
            legacy = specs[job['candidate']].get('legacy', False)
            mean = statistics.fmean(v for _, v in values) if legacy else statistics.fmean(statistics.fmean(v) for v in grouped.values())
            variance = statistics.fmean((v - mean)**2 for _, v in values) if legacy else statistics.fmean(statistics.fmean((v-mean)**2 for v in vs) for vs in grouped.values())
            near(item['mean'], mean, 'Training feature center')
            near(item['scale'], math.sqrt(variance) or 1., 'Training feature scale')
        if job['stage'] != 'final_all_data_refit' and specs[job['candidate']]['kind'] != 'median':
            grouped_y = defaultdict(list)
            for r in tr:
                grouped_y[r['source_group']].append(r['retention_pct'])
            near(job['target_center'], statistics.fmean(statistics.fmean(v) for v in grouped_y.values()), 'Target center uses held-out y')
        for pred in job['predictions']:
            check(pred['observed'] == records[pred['index']]['retention_pct'], 'Label changed in scoring')
            check(math.isfinite(pred['predicted']), 'Nonfinite prediction')
    for score in results['selection']['development_scores']:
        rows = dev_predictions[score['candidate']]
        check(len(rows) == 35 and len({r['endpoint_id'] for r in rows}) == 35, 'OOF duplicated or omitted records')
        for metric, value in independent_metrics(rows).items():
            near(score[metric], value, 'CV metric: ' + metric)
    choice = min((r for r in results['selection']['development_scores'] if r['eligible']), key=lambda r: r['mae'])
    check(results['selected_id'] == choice['candidate'] == 'ridge_core_noI_10', 'Selection changed after reserved evaluation')
    reserved = read(folder / 'reserved_predictions.json')
    for score in results['reserved_metrics']:
        rows = [r for r in reserved if r['variant'] == score['variant']]
        check(len(rows) == 7 and len({r['source_group'] for r in rows}) == 7, 'Reserved group count')
        for metric, value in independent_metrics(rows).items():
            near(score[metric], value, 'Reserved metric: ' + metric)
        # Independently reconstruct the paired bootstrap with the documented RNG and groups.
        for base_key, variant in [('vs_mean','source_mean'),('vs_legacy','legacy_mlp_noI')]:
            base = {r['source_group']: r for r in reserved if r['variant'] == variant}
            sorted_rows = sorted(rows, key=lambda r: r['source_group'])
            diffs = np.array([abs(r['predicted']-r['observed'])-abs(base[r['source_group']]['predicted']-r['observed']) for r in sorted_rows])
            indices = np.random.default_rng(20261022).integers(0, 7, (5000, 7))
            lo, hi = np.quantile(diffs[indices].mean(axis=1), [.025,.975])
            near(score[base_key]['delta_mae'], float(diffs.mean()), 'Paired delta')
            near(score[base_key]['delta_ci_low'], float(lo), 'Bootstrap lower')
            near(score[base_key]['delta_ci_high'], float(hi), 'Bootstrap upper')
    evaluated, final = [joblib.load(folder / file) for file in ['evaluated_development_model.joblib','model_v1_0.joblib']]
    test_records = [records[i] for i in sorted(held)]
    expected = [r['predicted'] for r in reserved if r['variant'] == 'selected']
    check(np.allclose(evaluated.predict(test_records), expected, atol=1e-12, rtol=0), 'Saved evaluated model differs from reported results')
    check(len(evaluated.training_sources) == 23 and len(evaluated.training_endpoint_ids) == 35, 'Evaluated artifact scope')
    check(len(final.training_sources) == 30 and len(final.training_endpoint_ids) == 42, 'Refit artifact scope')
    check(final.spec == evaluated.spec == specs[results['selected_id']], 'All-data specification changed')
    check(read(folder / 'model_schema.json') == final.encoder.schema, 'Final schema differs from artifact')
    check(read(folder / 'evaluated_model_schema.json') == evaluated.encoder.schema, 'Evaluated schema differs from artifact')
    memory = io.BytesIO()
    joblib.dump(final, memory)
    memory.seek(0)
    check(np.array_equal(final.predict(test_records), joblib.load(memory).predict(test_records)), 'Serialization roundtrip')
    try:
        final.predict_with_context([dict(test_records[0], system='2E')])
        check(False, 'Wrong system accepted')
    except ValueError:
        check(True, 'Wrong system rejected')
    try:
        final.predict_with_context([dict(test_records[0], BET_m2_g=None)])
        check(False, 'Missing required field accepted')
    except ValueError:
        check(True, 'Missing required field rejected')
    progress = read(folder / 'progress.json')
    check(progress['completed'] == progress['total'] == 581 and progress['status'] == 'complete', 'Progress mismatch')
    check([e['completed'] for e in progress['events']] == list(range(1,582)), 'Progress has fake, duplicate or missing jobs')
    check(all(a['seconds'] <= b['seconds'] for a,b in zip(progress['events'],progress['events'][1:])), 'Progress is not monotonic')
    primary = [r for r in reserved if r['variant'] == 'selected']
    sorted_errors = sorted(primary, key=lambda r: abs(r['predicted']-r['observed']), reverse=True)
    total_sse = sum((r['predicted']-r['observed'])**2 for r in primary)
    def distribution(ids):
        groups = defaultdict(list)
        for i in ids:
            groups[records[i]['source_group']].append(records[i]['retention_pct'])
        return {'rows':len(ids),'sources':len(groups),'source_equal_target_mean':statistics.fmean(statistics.fmean(v) for v in groups.values()),
                'sources_with_target_below91':sum(any(y<91 for y in v) for v in groups.values())}
    diagnosis = {'development':distribution(plan['development_indices']), 'reserved':distribution(sorted(held)),
        'largest_errors':sorted_errors, 'top2_squared_error_share':sum((r['predicted']-r['observed'])**2 for r in sorted_errors[:2])/total_sse,
        'material_candidate_enabled_fields_in_development':{f:{'minimum_source_support':min(v),'fold_candidate_uses':len(v)} for f,v in enabled_support.items()},
        'material_feature_effect_ridge100_reserved_mae':next(r['mae'] for r in results['reserved_metrics'] if r['variant']=='ridge_material_noI_100')-next(r['mae'] for r in results['reserved_metrics'] if r['variant']=='ridge_core_noI_100'),
        'interpretation':'Observed distribution shift, sparse low-retention source coverage, and unseen NaOH category; these are measured associations, not proof of a unique causal mechanism.'}
    (folder / 'diagnosis.json').write_text(json.dumps(diagnosis,ensure_ascii=False,indent=2)+'\n', encoding='utf-8')
    report = {'passed':True, 'check_count':checks, 'new_estimator_fits':0, 'protected_sealed_payloads':protected_count,
        'original_source_files_verified':len(source_files),
        'validation_scope':'All581jobs, all folds, all input values, artifact predictions, independent weighted arithmetic, paired bootstrap and original sealed payload hashes.',
        'performance_gate_passed':False, 'fit_warnings':len(results['warnings']),
        'model_hashes':{p:sha(folder / p) for p in ['model_v1_0.joblib','evaluated_development_model.joblib']}}
    (folder / 'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))


if __name__ == '__main__':
    verify(ROOT / '模型v1.0_来源留出训练_20261022')
