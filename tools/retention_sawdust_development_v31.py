"""Compare two source-isolated cohorts after adding the corresponding SD-AC test."""

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
from tools.retention_horizon_normalization_v19 import gates, paired_error
from tools.retention_onion_development_v29 import OUT as P29, subsets
from tools.retention_shape_v4 import Encoder, SIX, estimator, expressed, metrics, predicted, weights
from tools.retention_tail_development_v17 import BASE, BASELINES, OUT as P17
from tools.verify_retention_v3b import score

P30 = BASE / '第三十轮_杉木屑双体系原图_20261105'
OUT = BASE / '第三十一轮_杉木屑双体系开发对照_20261105'
PARENTS = {'3E': (P17, 32, 26), '2E': (P29, 30, 24)}
SOURCE = 'doi:10.3390/nano12050810'


def freeze():
    assert not OUT.exists(), 'A frozen research round cannot be replaced'
    evidence = P30/'curve_evidence.json'
    assert sha(evidence) == 'cba6f05756e45a692edad48a2c25b8d042f52dc9cc497e71d4f615b61fbc095c'
    proof = read(evidence)
    assert sha(ROOT/proof['pdf']) == proof['pdf_sha256']
    assert sha(ROOT/proof['si_package']) == proof['si_package_sha256']
    guarded = [Path(__file__), evidence, ROOT/proof['pdf'], ROOT/proof['si_package'], BASE/'research_goal.json']
    guarded.extend(ROOT/'tools'/f'{name}.py' for name in (
        'prepare_small_sample_routes','retention_corrected2e_v13','retention_horizon_normalization_v19',
        'retention_onion_development_v29','retention_shape_v4','retention_tail_development_v17',
        'retention_v3_optimizer','run_small_sample_routes','verify_retention_v3b'))
    for name in ('current_retention_research','current_training_latest'):
        path = ROOT/'data'/f'{name}.json'
        ptr = read(path)
        db = ROOT/(ptr['database'] if 'database' in ptr else Path(ptr['directory'])/ptr['database_file'])
        assert sha(db) == ptr['sha256']
        guarded.extend([path,db])
    pools, cohorts = {}, {}
    for system,(parent,n,g) in PARENTS.items():
        snapshot = read(parent/'input_snapshot.json')
        assert (snapshot['system'],snapshot['fraction']) == (system,.2)
        old = snapshot['rows']
        assert (len(old),len({r['source_family'] for r in old})) == (n,g)
        assert all(r['source_family'] != SOURCE for r in old)
        t = proof['records'][system]
        assert (t['system'],t['source_family'],t['target_cycle_count']) == (system,SOURCE,10000)
        features = t['windows']['0.2']['features']
        assert set(features) == set(SIX) and t['windows']['0.2']['markers'] == (39 if system=='3E' else 38)
        key = f'development:{SOURCE}::{system}::{t["sample_name"]}'
        addition = dict(row_id=key+'::early20',endpoint_id=key,curve_id=key,material_key=key,source_family=SOURCE,
                        sample_name=t['sample_name'],target=t['author_retention_pct'],features=features,
                        static_features=t['static_features'],last_early=features['last_early_retention_pct'],
                        author_approximate=t['author_approximate'],role='development_only_author_reported')
        rows = old+[addition]
        sources = sorted({r['source_family'] for r in rows})
        assert len(sources)==g+1 and all(r['features']['early_observed_cycle_count']<=.2*r['features']['target_cycle_count'] for r in rows)
        folds = {s:dict(test_sources=[s],train_ids=[r['row_id'] for r in rows if r['source_family']!=s],
                        test_ids=[r['row_id'] for r in rows if r['source_family']==s]) for s in sources}
        p = read(parent/'training_plan.json')
        assert p['environment']==environment()
        assert len(p['configurations'])==8 and all(c['target']=='delta' for c in p['configurations'])
        guarded.extend(parent/f for f in ('input_snapshot.json','training_plan.json','heldout_predictions.json','results.json'))
        cohorts[system] = dict(parent=parent.relative_to(ROOT).as_posix(),old_rows=n,old_sources=g,folds=folds,
                               configurations=p['configurations'],primary=p['primary'],
                               sd_endpoint_geometry_band_pct=t['terminal_band_pct'])
        pools[system] = rows
    assert {c['id'] for c in cohorts['3E']['configurations']} == {c['id'] for c in cohorts['2E']['configurations']}
    OUT.mkdir()
    snapshot = OUT/'input_snapshot.json'
    write(snapshot,pools)
    guarded.append(snapshot)
    plan = dict(frozen_at=now(),environment=environment(),cohorts=cohorts,early_fraction=.2,
                planned_new_fits=sum(len(c['folds'])*len(c['configurations']) for c in cohorts.values()),
                exact_reference_folds=400,exact_reference_endpoints=496,
                protected={p.relative_to(ROOT).as_posix():sha(p) for p in guarded},
                baselines=BASELINES,criteria=read(BASE/'research_goal.json')['criteria'],
                bootstrap=dict(draws=10000,seed=20261105,interval=[.025,.975],unit='source'),
                scope='Fixed B early20; separate 3E and 2E pools, the same paper never contributes across systems.',
                comparisons=('All original matched endpoints and full expanded cohorts reported separately. '
                             'Show every previous <=80% endpoint and the added SD-AC paper. '
                             'For SD-AC only, calculate signed residual vs the terminal pixel band without altering the target or fitting.'),
                output='Author-reported capacitance retention percent, with the 2E 80% approximation explicitly flagged.',
                outside_this_round='A, early10, shape and prior target transforms retained. No untouched external acceptance.')
    write(OUT/'training_plan.json',plan)
    write(OUT/'freeze_receipt.json',dict(plan_sha256=sha(OUT/'training_plan.json'),fits_at_freeze=0))


def checked_plan():
    plan = read(OUT/'training_plan.json')
    assert sha(OUT/'training_plan.json') == read(OUT/'freeze_receipt.json')['plan_sha256']
    assert environment() == plan['environment']
    assert all(sha(ROOT/p) == h for p,h in plan['protected'].items())
    return plan


def run():
    plan = checked_plan()
    data = read(OUT/'input_snapshot.json')
    with (OUT/'run_claim.json').open('x',encoding='utf-8') as f:
        json.dump(dict(started_at=now(),plan_sha256=sha(OUT/'training_plan.json')),f)
    events = []
    for system,spec in plan['cohorts'].items():
        lookup = {r['row_id']:r for r in data[system]}
        for held,split in spec['folds'].items():
            train,test = subsets(split,lookup)
            w = weights(train)
            delta = np.array([r['target']-r['last_early'] for r in train])
            center = float(np.average(delta,weights=w))
            scale = float(np.sqrt(np.average((delta-center)**2,weights=w))) or 1.
            for c in spec['configurations']:
                event = dict(system=system,held=held,config=c['id'],fit_attempted=False)
                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter('always')
                    try:
                        tr = [expressed(r,c,'six') for r in train]
                        te = [expressed(r,c,'six') for r in test]
                        enc = Encoder().fit(tr)
                        model = estimator(c)
                        mass = w*len(train)
                        kw = {'sample_weight':mass}
                        if c['kind']=='GPR':
                            model.set_params(alpha=c['parameters']['alpha']/mass)
                            kw = {}
                        x,xt = enc.transform(tr),enc.transform(te)
                        event['fit_attempted']=True
                        model.fit(x,(delta-center)/scale,**kw)
                        y = model.predict(xt)*scale+center+np.array([r['last_early'] for r in test])
                        assert len(y)==len(test) and np.isfinite(y).all()
                        event.update(status='complete',predictions=y.tolist())
                    except Exception as exc:
                        event.update(status='failed',error=repr(exc))
                event['warnings']=[str(x.message) for x in caught]
                events.append(event)
        print(f'{system}: {len(spec["folds"])*len(spec["configurations"])} fit jobs completed',flush=True)
    assert len(events)==plan['planned_new_fits']==416
    checked_plan()
    write(OUT/'fit_events.json',events)


def verify():
    plan = checked_plan()
    data,events = (read(OUT/k) for k in ('input_snapshot.json','fit_events.json'))
    index = {(e['system'],e['held'],e['config']):e for e in events}
    assert len(index)==len(events)==plan['planned_new_fits']
    assert set(index)=={(s,h,c['id']) for s,spec in plan['cohorts'].items() for h in spec['folds'] for c in spec['configurations']}
    scores,predictions,checks = {},{},0
    for system,spec in plan['cohorts'].items():
        rows = data[system]
        lookup = {r['row_id']:r for r in rows}
        parent = ROOT/spec['parent']
        old = read(parent/'heldout_predictions.json')
        archived = read(parent/'results.json')['results']
        controls = old['loso'] if system=='2E' else old
        variants = {c['id']:[] for c in spec['configurations']}
        baselines = {k:[] for k in BASELINES}
        for held,split in spec['folds'].items():
            train,test = subsets(split,lookup)
            mu = float(np.average([r['target'] for r in train],weights=weights(train)))
            for r in test:
                f = r['features']
                linear = r['last_early']+f['early_retention_slope_per_1000_cycles']*(f['target_cycle_count']-f['early_observed_cycle_count'])/1000.
                for name,value in zip(BASELINES,(mu,r['last_early'],linear)):
                    baselines[name].append(predicted(system,name,r,value))
            for key,preds in variants.items():
                e = index[system,held,key]
                if e['status']=='complete':
                    assert e['fit_attempted'] and len(e['predictions'])==len(test)
                    preds.extend(predicted(system,key,r,y) for r,y in zip(test,e['predictions']))
                checks+=1
        base = {name:score(v) for name,v in baselines.items()}
        results = {}
        for key,v in variants.items():
            control = controls[key]
            ref = score(control)
            assert ref == archived[key]['full']
            if len(v)!=len(rows):
                results[key]=dict(complete=False,numeric_pass=False)
                continue
            targets = {r['row_id']:r['target'] for r in rows}
            assert {r['row_id']:r['observed'] for r in v}==targets
            common = [p for p in v if p['source_family']!=SOURCE]
            assert {r['row_id']:r['observed'] for r in common}=={r['row_id']:r['observed'] for r in control}
            full = score(v)
            independently = metrics(v)
            for k,x in full.items():
                assert math.isclose(x,independently[k],abs_tol=1e-9,rel_tol=1e-9)
                checks+=1
            gate = gates(v,full,base,plan['criteria'],len(rows))
            addition, = [p for p in v if p['source_family']==SOURCE]
            lo,hi = spec['sd_endpoint_geometry_band_pct']
            assert lo<=addition['observed']<=hi
            before = {p['row_id']:p for p in control}
            low_rows = [dict(row_id=p['row_id'],sample_name=p['sample_name'],observed=p['observed'],
                             before=before[p['row_id']]['predicted'],after=p['predicted'])
                        for p in common if p['observed']<=80.]
            results[key]=dict(complete=True,control_common=ref,expanded_common=score(common),full=full,
                    common_mae_change=paired_error(common,control,plan['bootstrap']),old_low_rows=low_rows,
                    added=addition,added_signed_error_vs_band_pp=[addition['predicted']-hi,addition['predicted']-lo],
                    gates=gate,numeric_pass=all(gate.values()))
        scores[system]=dict(primary=spec['primary'],results=results,baselines=base,
                            numeric_passes=sum(x['numeric_pass'] for x in results.values()))
        predictions[system]=dict(loso=variants,baselines=baselines)
    assert not (OUT/'results.json').exists()
    write(OUT/'heldout_predictions.json',predictions)
    write(OUT/'results.json',dict(status='verified_development',scores=scores,new_fits=sum(e['fit_attempted'] for e in events),
        failures=sum(e['status']!='complete' for e in events),warnings=sum(len(e['warnings']) for e in events),
        checks=checks,numeric_passes=sum(x['numeric_passes'] for x in scores.values()),external_sources=0,goal_achieved=False))


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('step',choices=['freeze','run','verify'])
    {'freeze':freeze,'run':run,'verify':verify}[parser.parse_args().step]()
