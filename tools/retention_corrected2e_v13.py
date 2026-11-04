"""Freeze and run the MK9 correction comparison under the original P12 protocol."""
import collections
import gzip
import hashlib
import json
import math
from pathlib import Path
import platform
import sys
import time
import warnings

import numpy as np
import scipy
import sklearn
import xgboost

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.retention_expanded2e_v6 import Experiment
from tools.retention_shape_v4 import (
    Encoder, FIELDS, SIX, decode_target, encode_target, estimator, expressed,
    load_windows, metrics, now, predicted, read, sha, weights, write,
)

BASE = ROOT / '保持率达标研究_v3_主线与近优组合_20261030'
OLD = BASE / '第十二轮_扩充双电极来源验证'
OUT = BASE / '第十三轮_MK9纠错复验_20261104'
BATCH = BASE / '第十一轮_双电极原文曲线补充/batch5_指标纠错_20261031'
R20, R10 = 'B_2E_early20', 'B_2E_early10'
MK9 = 'v25:Mango_MK9_2E_C100000'
KEY_FIELDS = ('route', 'outer_source', 'config_id', 'role', 'inner_fold')


def key(record):
    return tuple(record[field] for field in KEY_FIELDS)


def snapshot(fraction):
    rows = []
    for row in load_windows('2E', fraction, include_shape=True):
        features = {k: row[k] for k in SIX}
        last = features['last_early_retention_pct']
        remaining = features['target_cycle_count'] - features['early_observed_cycle_count']
        rows.append(dict(
            row_id=f"{row['endpoint_id']}::early{int(100*fraction)}", endpoint_id=row['endpoint_id'],
            source_family=row['source_family'], curve_id=row['curve_id'],
            material_key=row['source_family']+'::'+row['sample_name'], sample_name=row['sample_name'],
            system='2E', target=row['target_retention_pct'], features=features, static_features=row['static_features'],
            last_early=last, linear_forecast=last+features['early_retention_slope_per_1000_cycles']*remaining/1000,
            fraction=fraction, point_indices=row['point_indices'], early_points=row['early_points'],
            reading_bound_pp=row['maximum_reading_bound_pp'], shape_features=row['shape_features'],
        ))
    return rows


def jobs(route, rows, plan, configs):
    """Enumerate exactly the train and test rows used by the fixed P12 fold order."""
    for split in plan['splits'][route]:
        held = split['outer_source']
        development = [r for r in rows if r['source_family'] != held]
        test_outer = [r for r in rows if r['source_family'] == held]
        for view in plan['views']:
            for c in configs:
                config_id = view+'::'+c['id']
                for fold, validation_sources in enumerate(split['inner_held_sources']):
                    train = [r for r in development if r['source_family'] not in validation_sources]
                    test = [r for r in development if r['source_family'] in validation_sources]
                    yield (route, held, config_id, 'inner', fold), train, test
                yield (route, held, config_id, 'outer', None), development, test_outer


def verify_old10(data, plan, configs):
    """Confirm every reused fit's key, inputs, membership and prediction payload."""
    prior_data = read(OLD / 'input_snapshot.json')
    prior_plan = read(OLD / 'training_plan.json')
    assert data[R10] == prior_data[R10]
    assert plan['splits'][R10] == prior_plan['splits'][R10]
    assert configs == read(OLD / 'candidate_configurations.json')
    with (OLD / 'fit_events.jsonl').open(encoding='utf8') as stream:
        events = {key(q): q for line in stream if (q := json.loads(line))['route'] == R10}
    predictions = {}
    with gzip.open(OLD / 'fit_predictions.jsonl.gz', 'rt', encoding='utf8') as stream:
        for line in stream:
            q = json.loads(line)
            if q['route'] == R10:
                assert key(q) not in predictions
                predictions[key(q)] = q
    expected = set()
    for job, train, test in jobs(R10, data[R10], plan, configs):
        expected.add(job)
        event, pred = events[job], predictions[job]
        assert event['status'] == 'complete' and not event['warnings'] and not pred['reused']
        assert event['fit_index'] == pred['fit_index']
        assert event['train_row_ids'] == [r['row_id'] for r in train]
        assert event['test_row_ids'] == [r['row_id'] for r in test]
        assert [(p['row_id'], p['observed']) for p in pred['predictions']] == [(r['row_id'], r['target']) for r in test]
        assert all(math.isfinite(p['predicted']) for p in pred['predictions'])
    assert expected == set(events) == set(predictions) and len(expected) == 2880
    return dict(route=R10, fit_predictions_reused=len(expected), snapshot_exact=True, ordered_membership_exact=True,
                scores_path=(OLD / 'results.json').relative_to(ROOT).as_posix(),
                scores_sha256=sha(OLD / 'results.json'), prediction_archive_sha256=sha(OLD / 'fit_predictions.jsonl.gz'),
                prediction_keys_sha256=hashlib.sha256(json.dumps(sorted(expected)).encode()).hexdigest())


def environment():
    return dict(python=platform.python_version(), sklearn=sklearn.__version__, xgboost=xgboost.__version__,
                numpy=np.__version__, scipy=scipy.__version__)


def freeze():
    assert not OUT.exists(), 'A frozen research round cannot be replaced'
    old = read(OLD / 'training_plan.json')
    previous = read(OLD / 'input_snapshot.json')
    goal = read(BASE / 'research_goal.json')
    closeout = read(BATCH / 'closeout_verification.json')
    assert closeout['status'] == 'passed' and not closeout['old20pct_scientific_result_valid']
    data = {R20: snapshot(.2), R10: snapshot(.1)}
    assert data[R10] == previous[R10]
    assert len(data[R20]) == len(previous[R20]) == 27
    assert [a['endpoint_id'] for a,b in zip(data[R20], previous[R20]) if a != b] == [MK9]
    assert [(r['target'], len(r['early_points'])) for r in data[R20] if r['endpoint_id'] == MK9] == [(65.,4)]
    assert old['criteria'] == goal['criteria'] and old['generalization'] == goal['generalization']
    configs = read(OLD / 'candidate_configurations.json')
    assert len(configs) == 16
    plan = {k: old[k] for k in ('splits', 'views', 'primary', 'paired_control', 'selection', 'criteria',
                               'baselines', 'generalization', 'input_scope', 'precision_limit', 'immutable_output')}
    counts = {}
    for route, rows in data.items():
        source_set = {r['source_family'] for r in rows}
        assert source_set == {r['outer_source'] for r in plan['splits'][route]}
        assert len({r['row_id'] for r in rows}) == len(rows)
        counts[route] = dict(rows=len(rows), sources=len(source_set))
    assert len(list(jobs(R20, data[R20], plan, configs))) == 3520
    prior = verify_old10(data, plan, configs)
    assert environment() == {k:read(OLD / 'environment.json')[k] for k in environment()}
    archive = read(OLD / 'post_fit_data_correction_receipt.json')['pointer_substitutions']
    protected = {archive.get(p, {}).get('frozen_pointer_archive', p): h for p,h in read(OLD / 'source_protection.json').items()}
    release = read(ROOT / 'data/current_retention_research.json')
    current = read(ROOT / 'data/current_training_latest.json')
    protected_paths = [ROOT/'data/current_retention_research.json', ROOT/'data/current_training_latest.json',
                       ROOT/release['database'], ROOT/current['directory']/current['database_file'],
                       BATCH/'closeout_verification.json', BATCH/'metric_supersession.json', BATCH/'curve_dataset_v3h.json',
                       Path(__file__), ROOT/'tools/verify_retention_corrected2e_v13.py']
    protected_paths += [OLD/name for name in ('input_snapshot.json', 'candidate_configurations.json', 'training_plan.json',
                                               'environment.json', 'fit_events.jsonl', 'fit_predictions.jsonl.gz',
                                               'heldout_predictions.json', 'results.json', 'independent_verification.json',
                                               'scientific_validity_review.json', 'post_fit_data_correction_receipt.json')]
    for p in protected_paths:
        protected[p.relative_to(ROOT).as_posix()] = sha(p)
    assert all(sha(ROOT/p) == h for p,h in protected.items())
    OUT.mkdir()
    write(OUT/'input_snapshot.json', data)
    write(OUT/'candidate_configurations.json', configs)
    write(OUT/'source_protection.json', protected)
    write(OUT/'verified_old10_reuse.json', prior)
    plan.update(frozen_at=now(), counts=counts, changed_endpoint=MK9, planned_new_fits=3520,
                planned_exact_reused_fits=2880, new_fit_route=R20, reuse_route=R10, new_external_sources=0,
                goal_status='active', environment=environment(),
                science='MK9 Fig10a blue retention65%; green CE79.3% preserved separately. Old P12 20% is invalid history.',
                stop='Freeze identical configurations, folds and gates. Fit corrected 20% only. 10% uses pinned P12 predictions.',
                fingerprints={n:sha(OUT/n) for n in ('input_snapshot.json','candidate_configurations.json','source_protection.json','verified_old10_reuse.json')})
    write(OUT/'training_plan.json', plan)
    write(OUT/'freeze_receipt.json', dict(plan_sha256=sha(OUT/'training_plan.json'),
                                        protected_objects=len(protected), exact_reuse_fits=2880, new_fits=0))
    write(OUT/'progress.json', dict(status='frozen_not_started', new_fits=0, planned_new_fits=3520, exact_reuse_fits=2880))
    print('Frozen 3h corrected 20% with 3520 planned fits and 2880 verified historical 10% fits.')


def checked_plan():
    plan = read(OUT/'training_plan.json')
    assert sha(OUT/'training_plan.json') == read(OUT/'freeze_receipt.json')['plan_sha256']
    assert all(sha(OUT/n) == h for n,h in plan['fingerprints'].items())
    assert all(sha(ROOT/p) == h for p,h in read(OUT/'source_protection.json').items())
    assert environment() == plan['environment']
    return plan


class CorrectedExperiment(Experiment):
    """Use the same nested selection as P12, with a separate fit archive and claim."""

    def fit(self, route, config, view, train, test, outer, role, fold=None):
        assert route == R20 and self.n < self.plan['planned_new_fits']
        train_sources = sorted({r['source_family'] for r in train})
        test_sources = sorted({r['source_family'] for r in test})
        assert outer not in train_sources and not set(train_sources).intersection(test_sources)
        assert not {r['curve_id'] for r in train}.intersection(r['curve_id'] for r in test)
        assert role == 'outer' or outer not in test_sources
        config_id = view+'::'+config['id']
        event = dict(fit_index=self.n+1, route=route, config_id=config_id, base_config_id=config['id'],
                     view=view, outer_source=outer, role=role, inner_fold=fold, train_sources=train_sources,
                     test_sources=test_sources, train_row_ids=[r['row_id'] for r in train], test_row_ids=[r['row_id'] for r in test])
        predictions = []
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            try:
                train_features = [expressed(r,config,view) for r in train]
                test_features = [expressed(r,config,view) for r in test]
                encoder = Encoder().fit(train_features)
                x, xt = encoder.transform(train_features), encoder.transform(test_features)
                w = weights(train)
                y = np.array([encode_target(r,config) for r in train])
                center = float(np.average(y, weights=w))
                scale = float(np.sqrt(np.average((y-center)**2, weights=w))) or 1.
                model = estimator(config)
                kwargs = {} if config['kind'] == 'GPR' else {'sample_weight': w*len(train)}
                model.fit(x, (y-center)/scale, **kwargs)
                decoded = [decode_target(z, r, config) for r,z in zip(test,model.predict(xt)*scale+center)]
                assert len(decoded) == len(test) and all(math.isfinite(v) for v in decoded)
                predictions = [predicted(route,config_id,r,v,fit_index=event['fit_index']) for r,v in zip(test,decoded)]
                event.update(status='complete', encoder=encoder.schema, target_center=center, target_scale=scale,
                             shape_fields_retained=[v['field'] for v in encoder.schema if v['field'] in FIELDS])
            except Exception as exc:
                event.update(status='failed', error=repr(exc))
        event['warnings'] = [str(w.message) for w in caught]
        if event['status'] == 'failed':
            self.failed.append(event)
        self.n += 1
        with (OUT/'fit_events.jsonl').open('a', encoding='utf8') as stream:
            stream.write(json.dumps(event,ensure_ascii=False,allow_nan=False)+'\n')
        record = {k:event[k] for k in (*KEY_FIELDS,'view','fit_index')}
        with gzip.open(OUT/'fit_predictions.jsonl.gz','at',encoding='utf8') as stream:
            stream.write(json.dumps(dict(record, predictions=predictions, reused=False),ensure_ascii=False,allow_nan=False)+'\n')
        if self.n == 1 or self.n % 80 == 0:
            publish_progress('running', self)
        return predictions


def publish_progress(status, exp):
    state = dict(status=status, new_fits=exp.n, planned_new_fits=3520, exact_reuse_fits=2880,
                 failures=len(exp.failed), elapsed_seconds=round(time.monotonic()-exp.start,1))
    write(OUT/'progress.json', state)
    print(json.dumps(state,ensure_ascii=False), flush=True)


def gate_metrics(predictions, plan, rows):
    grouped = collections.defaultdict(list)
    for prediction in predictions:
        grouped[prediction['model']].append(prediction)
    base_mae = {name:metrics(grouped[name])['mae'] for name in plan['baselines']}
    result = []
    for model, pred in sorted(grouped.items()):
        m = metrics(pred,bootstrap=model in ('shape_oneSE_family_mean','six_oneSE_family_mean'))
        checks = dict(r2=m['r2'] is not None and m['r2']>.95,mae=m['mae']<=2,rmse=m['rmse']<=3,
                      mape=m['mape_pct']<=5,p90_ape=m['p90_ape_pct']<=10,p90_abs=m['p90_absolute_error']<=5,
                      source_tail=m['source_p90_mae']<=5,coverage=len(pred)==len(rows),positive=all(p['predicted']>0 for p in pred))
        for name, base in base_mae.items():
            m['mae_reduction_vs_'+name] = 1-m['mae']/base
            checks['beat_'+name] = m['mae_reduction_vs_'+name] >= .2
        m.update(route=R20,model=model,checks=checks,numeric_pass=all(checks.values()),at_least10_sources=m['sources']>=10,
                 untouched_external_test=False,reliable_model_accepted=False)
        result.append(m)
    return result


def run():
    plan = checked_plan()
    data = read(OUT/'input_snapshot.json')
    configs = read(OUT/'candidate_configurations.json')
    prior = verify_old10(data, plan, configs)
    assert prior == read(OUT/'verified_old10_reuse.json')
    assert not (OUT/'fit_events.jsonl').exists() and not (OUT/'fit_predictions.jsonl.gz').exists()
    with (OUT/'run_claim.json').open('x',encoding='utf8') as claim:
        json.dump(dict(started_at=now(), plan_sha256=sha(OUT/'training_plan.json')), claim)
    exp = CorrectedExperiment(plan)
    try:
        exp.run_route(R20, data[R20], configs)
        assert exp.n == plan['planned_new_fits']
        checked_plan()
        result = gate_metrics(exp.pred, plan, data[R20])
        write(OUT/'heldout_predictions.json',exp.pred)
        write(OUT/'nested_selection.json',exp.selections)
        write(OUT/'results.json',dict(status='fit_complete',new_estimator_fits=exp.n,exact_reuse=prior,
                                    metrics=result,numeric_pass_count=sum(m['numeric_pass'] for m in result),
                                    failed_estimator_fits=len(exp.failed),new_external_sources=0,
                                    primary=plan['primary'],goal_achieved=False,completed_at=now()))
    except Exception as exc:
        write(OUT/'terminal_error.json',dict(error=repr(exc),new_fits=exp.n,failed_attempts=len(exp.failed)))
        publish_progress('terminal_error',exp)
        raise
    finally:
        write(OUT/'fit_failures.json',exp.failed)
    publish_progress('fit_complete', exp)


if __name__ == '__main__':
    {'freeze':freeze,'run':run}[sys.argv[1]]()
