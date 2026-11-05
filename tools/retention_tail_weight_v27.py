"""Prespecified comparison of tail-weighted and archived retention regressors."""

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
from tools.retention_ddhpc_development_v21 import OUT as P21
from tools.retention_horizon_normalization_v19 import OUT as P19, factor, gates, paired_error
from tools.retention_shape_v4 import Encoder, estimator, expressed, metrics, predicted, weights
from tools.retention_tail_development_v17 import BASE, BASELINES, OUT as P17
from tools.verify_retention_v3b import score

OUT = BASE / '第二十七轮_低保持率训练加权_20261105'
ARCHIVES = {
    '3E_delta': (P17, P17, '3E', 'full', 32, 26, 'doi:10.3390/nano16211412'),
    '3E_horizon': (P19, P17, '3E', 'variant', 32, 26, 'doi:10.3390/nano16211412'),
    '2E_delta': (P21, P21, '2E', 'full', 29, 23, 'doi:10.1039/c9ra06603a'),
}


def freeze():
    assert not OUT.exists(), 'A frozen research round cannot be replaced'
    paths = [Path(__file__), BASE / 'research_goal.json']
    paths.extend(p for p in (Path(__file__).parent / name for name in (
        'prepare_small_sample_routes.py', 'retention_corrected2e_v13.py',
        'retention_ddhpc_development_v21.py', 'retention_horizon_normalization_v19.py',
        'retention_shape_v4.py', 'retention_tail_development_v17.py',
        'retention_v3_optimizer.py', 'run_small_sample_routes.py', 'verify_retention_v3b.py')))
    for name in ('current_retention_research.json', 'current_training_latest.json'):
        pointer = ROOT / 'data' / name
        d = read(pointer)
        database = ROOT / (d['database'] if 'database' in d else Path(d['directory']) / d['database_file'])
        assert sha(database) == d['sha256']
        paths.extend([pointer, database])
    cohorts = {}
    for name, (archive, pool, system, measure, n, source_count, difficult) in ARCHIVES.items():
        snapshot = pool / 'input_snapshot.json'
        data = read(snapshot)
        rows = data['rows']
        sources = sorted({r['source_family'] for r in rows})
        assert (len(rows), len(sources), data['system'], data['fraction']) == (n, source_count, system, .2)
        assert len({r['row_id'] for r in rows}) == n and difficult in sources
        assert all(r['features']['early_observed_cycle_count'] <= .2*r['features']['target_cycle_count'] for r in rows)
        parent = read(archive / 'training_plan.json')
        assert parent['environment'] == environment()
        configs = parent['configurations']
        assert len(configs) == 8 and all(c['target'] == 'delta' for c in configs)
        paths.extend([snapshot, *(archive / file for file in ('training_plan.json', 'heldout_predictions.json',
                                                              'fit_events.json', 'results.json'))])
        cohorts[name] = dict(system=system, rows=n, sources=source_count,
                             difficult_source=difficult, archive_score_key=measure, configurations=configs,
                             target_transform='horizon_normalized_delta' if measure == 'variant' else 'delta',
                             primary=parent['primary'], snapshot=snapshot.relative_to(ROOT).as_posix(),
                             archive=archive.relative_to(ROOT).as_posix(),
                             baseline_archive=pool.relative_to(ROOT).as_posix(),
                             splits={s: dict(train=[r['row_id'] for r in rows if r['source_family'] != s],
                                             test=[r['row_id'] for r in rows if r['source_family'] == s])
                                     for s in sources})
    plan = dict(frozen_at=now(), environment=environment(), cohorts=cohorts, early_fraction=.2,
                protected={p.relative_to(ROOT).as_posix(): sha(p) for p in paths},
                planned_new_fits=sum(c['sources']*len(c['configurations']) for c in cohorts.values()),
                reused_control_folds=600, reused_control_endpoint_predictions=744,
                threshold_retention_pct=80., train_multiplier=2.,
                weight_rule=('Training only: multiply base source/curve weights for author terminal retention <=80% by 2; '
                             'renormalize to training row count. Same sample_weight for non-GP, inverse alpha for GPR. '
                             'Keep fold-local feature encoding and original base-weight target center/scale.'),
                target_rule=('Use the archived terminal minus last early retention target, either in pp or divided by '
                             'log1p((N-N_observed)/1000). Apply the exact inverse in pp; no clipping.'),
                comparison=('Exact archival controls on identical whole-paper splits, full prediction coverage, '
                            'all 8 configs per cohort. Report <=80%, >80%, and named difficult source separately. '
                            'An exploratory joint gain requires smaller MAE in both <=80% and >80% subsets.'),
                bootstrap=dict(seed=20261105, draws=10000, interval=[.025, .975], unit='source'),
                output='author_defined_capacitance_retention_pct_at_declared_cycle_count_and_conditions',
                criteria=read(BASE / 'research_goal.json')['criteria'], new_external_sources=0,
                scope='Exposed development sources. Keep A and early10 research separately. One factor; no outer-result selection.')
    OUT.mkdir()
    write(OUT / 'training_plan.json', plan)
    write(OUT / 'freeze_receipt.json', dict(plan_sha256=sha(OUT / 'training_plan.json'), fits_at_freeze=0))


def checked_plan():
    path = OUT / 'training_plan.json'
    plan = read(path)
    assert sha(path) == read(OUT / 'freeze_receipt.json')['plan_sha256']
    assert environment() == plan['environment']
    for path, digest in plan['protected'].items():
        assert sha(ROOT / path) == digest, path
    return plan


def fold_data(pool, split, source, plan):
    train, test = ([pool[k] for k in split[subset]] for subset in ('train', 'test'))
    assert all(r['source_family'] != source for r in train) and all(r['source_family'] == source for r in test)
    assert not {r['curve_id'] for r in train} & {r['curve_id'] for r in test}
    assert set(split['train'] + split['test']) == set(pool) and len(train) + len(test) == len(pool)
    w = weights(train)
    low = np.array([r['target'] <= plan['threshold_retention_pct'] for r in train])
    mass = w * np.where(low, plan['train_multiplier'], 1.)
    mass *= len(train) / mass.sum()
    return train, test, w, low, mass


def run():
    plan = checked_plan()
    with (OUT / 'run_claim.json').open('x', encoding='utf-8') as stream:
        json.dump(dict(started_at=now(), plan_sha256=sha(OUT / 'training_plan.json')), stream)
    total = 0
    with (OUT / 'fit_events.jsonl').open('x', encoding='utf-8') as stream:
        for name, c in plan['cohorts'].items():
            rows = read(ROOT / c['snapshot'])['rows']
            pool = {r['row_id']: r for r in rows}
            previous = {(e.get('outer_source', e.get('source')), e['config_id']): e
                        for e in read(ROOT / c['archive'] / 'fit_events.json')}
            encoder_archive = previous
            normalize = c['target_transform'] == 'horizon_normalized_delta'
            if normalize:
                encoder_archive = {(e['outer_source'], e['config_id']): e for e in read(P17 / 'fit_events.json')}
            for source, split in c['splits'].items():
                train, test, w, low, mass = fold_data(pool, split, source, plan)
                norm_train, norm_test = ([factor(r) if normalize else 1. for r in subset]
                                         for subset in (train, test))
                target = np.array([r['target'] - r['last_early'] for r in train]) / norm_train
                if normalize:
                    center = float(np.dot(w, target))
                    scale = float(np.sqrt(np.dot(w, (target-center)**2))) or 1.
                else:
                    center = float(np.average(target, weights=w))
                    scale = float(np.sqrt(np.average((target-center)**2, weights=w))) or 1.
                for config in c['configurations']:
                    key = config['id']
                    control = previous[source, key]
                    assert control['status'] == 'complete' and all(control[k+'_ids'] == split[k] for k in split)
                    assert math.isclose(control['target_center'], center, abs_tol=1e-12)
                    assert math.isclose(control['target_scale'], scale, abs_tol=1e-12)
                    total += 1
                    event = dict(index=total, cohort=name, source=source, config_id=key, control_index=control['index'],
                                 low_train_rows=int(low.sum()), low_train_mass=float(mass[low].sum()), fit_attempted=False)
                    with warnings.catch_warnings(record=True) as caught:
                        warnings.simplefilter('always')
                        try:
                            tr = [expressed(r, config, 'six') for r in train]
                            te = [expressed(r, config, 'six') for r in test]
                            encoder = Encoder().fit(tr)
                            assert encoder.schema == encoder_archive[source, key]['encoder']
                            model = estimator(config)
                            kw = {'sample_weight': mass}
                            if config['kind'] == 'GPR':
                                model.set_params(alpha=config['parameters']['alpha']/mass)
                                kw = {}
                            x = encoder.transform(tr)
                            event['fit_attempted'] = True
                            model.fit(x, (target-center)/scale, **kw)
                            z = (model.predict(encoder.transform(te))*scale + center) * norm_test
                            y = z + np.array([r['last_early'] for r in test])
                            assert len(y) == len(test) and np.isfinite(y).all()
                            event.update(status='complete', predictions=y.tolist())
                        except Exception as exc:
                            event.update(status='failed', error=repr(exc))
                    event['warnings'] = [str(item.message) for item in caught]
                    stream.write(json.dumps(event, ensure_ascii=False, allow_nan=False) + '\n')
                    stream.flush()
                if total % 80 == 0:
                    print(f'{total}/{plan["planned_new_fits"]} jobs completed', flush=True)
    assert total == plan['planned_new_fits']
    checked_plan()
    print(f'{total}/{total} jobs completed', flush=True)


def subset_result(preds):
    errors = np.array([p['predicted']-p['observed'] for p in preds])
    w = weights(preds)
    return dict(rows=len(preds), sources=len({p['source_family'] for p in preds}),
                mae_pp=float(np.dot(w, abs(errors))), signed_error_pp=float(np.dot(w, errors)))


def verify():
    plan = checked_plan()
    with (OUT / 'fit_events.jsonl').open(encoding='utf-8') as stream:
        events = [json.loads(line) for line in stream]
    assert len(events) == plan['planned_new_fits']
    assert [e['index'] for e in events] == list(range(1, len(events)+1))
    index = {(e['cohort'], e['source'], e['config_id']): e for e in events}
    assert len(index) == len(events)
    results, outputs, checks = {}, {}, 0
    for name, c in plan['cohorts'].items():
        pool = {r['row_id']: r for r in read(ROOT / c['snapshot'])['rows']}
        controls = read(ROOT / c['archive'] / 'heldout_predictions.json')
        previous = read(ROOT / c['archive'] / 'results.json')['results']
        baseline_rows = read(ROOT / c['baseline_archive'] / 'heldout_predictions.json')
        base = {key: score(baseline_rows[key]) for key in BASELINES}
        variants = {config['id']: [] for config in c['configurations']}
        for source, split in c['splits'].items():
            train, test, w, low, mass = fold_data(pool, split, source, plan)
            assert math.isclose(float(mass.sum()), len(train), abs_tol=1e-10)
            if low.any() and not low.all():
                relative = mass / w
                assert np.allclose(relative[low]/relative[~low][0], plan['train_multiplier'], rtol=0, atol=1e-12)
            checks += 2
            for key, preds in variants.items():
                e = index[name, source, key]
                assert e['low_train_rows'] == int(low.sum()) and math.isclose(e['low_train_mass'], float(mass[low].sum()))
                if e['status'] == 'complete':
                    assert e['fit_attempted'] and len(e['predictions']) == len(test)
                    preds.extend(predicted(c['system'], key, r, y) for r, y in zip(test, e['predictions']))
                checks += 2
        detail = {}
        for key, preds in variants.items():
            old = controls[key]
            ids = {r['row_id']: (r['source_family'], r['target']) for r in pool.values()}
            assert {p['row_id']: (p['source_family'], p['observed']) for p in old} == ids
            reference = score(old)
            assert reference == previous[key][c['archive_score_key']]
            checks += 2
            if len(preds) != len(ids):
                detail[key] = dict(complete=False, numeric_pass=False, rows_with_predictions=len(preds))
                continue
            assert {p['row_id']: (p['source_family'], p['observed']) for p in preds} == ids
            current = score(preds)
            independent = metrics(preds)
            for field, val in current.items():
                assert math.isclose(val, independent[field], abs_tol=1e-9, rel_tol=1e-9)
                checks += 1
            blocks = {}
            threshold = plan['threshold_retention_pct']
            for block, selector in (
                ('low', lambda p: p['observed'] <= threshold),
                ('ordinary', lambda p: p['observed'] > threshold),
                ('named_source', lambda p: p['source_family'] == c['difficult_source']),
            ):
                before, after = (subset_result([p for p in a if selector(p)]) for a in (old, preds))
                blocks[block] = dict(control=before, variant=after, delta_mae_pp=after['mae_pp']-before['mae_pp'])
            gate = gates(preds, current, base, plan['criteria'], len(ids))
            detail[key] = dict(complete=True, control=reference, variant=current, blocks=blocks,
                               paired_mae=paired_error(preds, old, plan['bootstrap']), gates=gate,
                               numeric_pass=all(gate.values()), joint_gain=all(blocks[b]['delta_mae_pp'] < 0
                                                                            for b in ('low', 'ordinary')))
        results[name] = dict(primary=c['primary'], baselines=base, configurations=detail,
                             numeric_passes=sum(x['numeric_pass'] for x in detail.values()),
                             joint_gains=sum(x.get('joint_gain', False) for x in detail.values()))
        outputs[name] = variants
    summary = dict(status='verified_development', planned_jobs=len(events),
                   fit_attempts=sum(e['fit_attempted'] for e in events),
                   failures=sum(e['status'] != 'complete' for e in events),
                   warnings=sum(len(e['warnings']) for e in events), checks=checks, external_sources=0,
                   numeric_passes=sum(c['numeric_passes'] for c in results.values()),
                   goal_achieved=False, results=results)
    assert not (OUT / 'results.json').exists()
    write(OUT / 'heldout_predictions.json', outputs)
    write(OUT / 'results.json', summary)
    print(json.dumps({k: {q: v[q] for q in ('primary', 'numeric_passes', 'joint_gains')}
                      for k, v in results.items()}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('step', choices=['freeze', 'run', 'verify'])
    {'freeze': freeze, 'run': run, 'verify': verify}[parser.parse_args().step]()
