"""Paired endpoint-only and intermediate-supervision trials on the approved 20% windows."""
from collections import Counter, defaultdict
import gzip
import hashlib
import json
import math
from pathlib import Path
import sqlite3
import sys
import time
import warnings

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from data.retention_research import load_windows
from tools.retention_corrected2e_v13 import BASE, OLD, OUT as P13, ROOT, environment
from tools.retention_shape_v4 import SIX, Encoder, estimator, expressed, metrics, now, predicted, read, sha, weights, write
from tools.verify_retention_v3b import score as independent_score

OUT = BASE / '第十四轮_中段监督对照_20261104'
SYSTEMS = ('2E', '3E')
ARMS = {'author_only': 0.0, 'intermediate_25': 0.25}
BASELINES = ('training_mean', 'early_persistence', 'early_linear')


def endpoint_snapshot(system):
    out = []
    for row in load_windows(system, .2):
        f = {k: row[k] for k in SIX}
        out.append(dict(row_id=row['endpoint_id']+'::early20', endpoint_id=row['endpoint_id'],
                        curve_id=row['curve_id'], source_family=row['source_family'], sample_name=row['sample_name'],
                        material_key=row['source_family']+'::'+row['sample_name'], target=row['target_retention_pct'],
                        last_early=f['last_early_retention_pct'], features=f, static_features=row['static_features']))
    return out


def auxiliary_snapshot(system, endpoints, inventory, db):
    index = {r['curve_id']:r for r in endpoints}
    group = next(x for x in inventory['inventory'] if x['system']==system and x['fraction']==.2)
    assert set(index)=={r['curve_id'] for r in group['detail']}
    out = []
    for curve in group['detail']:
        cid = curve['curve_id']
        parent = index[cid]
        points = {i:json.loads(j) for i,j in db.execute('SELECT marker_index,raw_json FROM curve_points WHERE curve_id=?',(cid,))}
        assert db.execute('SELECT approved FROM curves WHERE curve_id=?',(cid,)).fetchone()==(1,)
        assert parent['target']==curve['author_endpoint_retention_pct']
        for candidate in curve['selected']:
            marker = candidate['marker_index']
            target = points[marker]
            lo, hi = candidate['cycle_interval']
            ids = candidate['early_marker_indices']
            assert ids==sorted(i for i,p in points.items() if p['cycle_upper']<=.2*lo)
            assert len(ids)>=3 and marker not in ids and hi<curve['author_endpoint_cycle']
            assert (lo,hi)==(target['cycle_lower'],target['cycle_upper'])
            assert target['retention_pct']==candidate['retention_reading_pct']
            assert target['reading_interval_pp']==candidate['reading_interval_pp']
            x = np.array([points[i]['cycle_coordinate'] for i in ids]); y = np.array([points[i]['retention_pct'] for i in ids])
            slope = float(np.dot(x-x.mean(),y-y.mean())/np.dot(x-x.mean(),x-x.mean()))
            f = dict(zip(SIX,[float(y[-1]),float(y.mean()),slope*1000.,float(np.ptp(y)),float(x[-1]),target['cycle_coordinate']]))
            out.append(dict(parent,row_id=f'{cid}::digitized{marker}',target=target['retention_pct'],last_early=f['last_early_retention_pct'],
                            features=f,reading_interval_pp=target['reading_interval_pp'],cycle_interval=[lo,hi],
                            shared_reference=curve['shared_reference'],early_marker_indices=ids,label_kind='digitized_intermediate'))
    assert len(out)==group['capped_selected_positions']==len({r['row_id'] for r in out})
    return out


def splits(rows):
    sources = sorted({r['source_family'] for r in rows})
    plan = {}
    for held in sources:
        pool = sorted(set(sources)-{held},key=lambda s:hashlib.sha256(s.encode()).hexdigest())
        plan[held] = [pool[k::4] for k in range(4)]
    return plan


def freeze():
    assert not OUT.exists()
    inventory_file = P13/'curve_supervision_inventory_v3h.json'
    inventory = read(inventory_file)
    assert sha(inventory_file)==read(P13/'curve_supervision_inventory_verification.json')['inventory_sha256']
    pointer = read(ROOT/'data/current_retention_research.json')
    db_path = ROOT/pointer['database']
    assert sha(db_path)==pointer['sha256']==inventory['database_sha256']
    assert read(P13/'completion.json')['status']=='complete_verified'
    by_family = {}
    for config in read(P13/'candidate_configurations.json'):
        if config['target']=='delta':
            by_family.setdefault(config['family'],config)
    assert len(by_family)==8
    configs = list(by_family.values())
    data = {}
    with sqlite3.connect(db_path.as_uri()+'?mode=ro',uri=True) as db:
        for system in SYSTEMS:
            endpoints = endpoint_snapshot(system)
            data[system] = dict(endpoints=endpoints,intermediate=auxiliary_snapshot(system,endpoints,inventory,db))
    prior = read(P13/'input_snapshot.json')['B_2E_early20']
    assert [{k:r[k] for k in data['2E']['endpoints'][0]} for r in prior]==data['2E']['endpoints']
    folds = {system:splits(d['endpoints']) for system,d in data.items()}
    assert {g:groups for g,groups in folds['2E'].items()}=={v['outer_source']:v['inner_held_sources'] for v in read(P13/'training_plan.json')['splits']['B_2E_early20']}
    total = sum(len(v) for v in folds.values())*5*len(configs)*len(ARMS)
    assert total==3680
    protection = read(P13/'source_protection.json')
    for path in [Path(__file__),inventory_file,P13/'curve_supervision_inventory_verification.json',P13/'input_snapshot.json',
                 P13/'training_plan.json',P13/'completion.json',P13/'results.json',P13/'independent_verification.json']:
        protection[path.relative_to(ROOT).as_posix()] = sha(path)
    assert all(sha(ROOT/p)==h for p,h in protection.items())
    OUT.mkdir()
    write(OUT/'input_snapshot.json',data)
    plan = dict(frozen_at=now(),data_sha256=sha(OUT/'input_snapshot.json'),protected=protection,
                environment=environment(),arms=ARMS,configurations=configs,folds=folds,planned_fits=total,
                criteria=read(BASE/'research_goal.json')['criteria'],baselines=BASELINES,
                primary='Per arm, choose by inner author-endpoint source-weighted MAE, then RMSE, then config ID. Report both arms and all fixed families.',
                weight_rule='Equal source, then equal curves. 25% of each curve mass shared by its intermediate points; 75% retained by its author endpoint. Encoder, target centering and scaling use training author endpoints only in both arms.',
                gpr_rule='Fixed Matern; per observation alpha=base alpha/(row mass * number of author endpoints); same formula in both arms. Controlled observation weighting, not a statistical interpretation of digitization boxes.',
                interval_rule='Use reported digitized ordinate as central supervision; preserve cycle/ordinate boxes and shared reference. Reading boxes are not independent measurement noise.',
                external_sources=0,scope='B 2E and 3E approved 20% windows, separate models. Author endpoints only in inner validation and outer evaluation. No contract expansion.')
    write(OUT/'training_plan.json',plan)
    write(OUT/'freeze_receipt.json',dict(plan_sha256=sha(OUT/'training_plan.json'),protected_files=len(protection),fit_count=0))
    write(OUT/'progress.json',dict(status='frozen_not_started',completed_fits=0,planned_fits=total))
    print(f'Frozen {total} paired fits across 2E and 3E.',flush=True)


def checked():
    plan = read(OUT/'training_plan.json')
    assert sha(OUT/'training_plan.json')==read(OUT/'freeze_receipt.json')['plan_sha256']
    assert sha(OUT/'input_snapshot.json')==plan['data_sha256'] and plan['environment']==environment()
    assert all(sha(ROOT/p)==h for p,h in plan['protected'].items())
    return plan, read(OUT/'input_snapshot.json')


def jobs(plan,data):
    for system, group in data.items():
        rows = group['endpoints']
        for outer, inner in plan['folds'][system].items():
            for k in [None,*range(4)]:
                validation = {outer} if k is None else set(inner[k])
                blocked = validation|{outer}
                train = [r for r in rows if r['source_family'] not in blocked]
                test = [r for r in rows if r['source_family'] in validation]
                auxiliary = [r for r in group['intermediate'] if r['source_family'] not in blocked]
                assert not {r['curve_id'] for r in auxiliary+train}&{r['curve_id'] for r in test}
                for config in plan['configurations']:
                    yield system,outer,k,config,train,test,auxiliary


def weight_trial(train,auxiliary,portion):
    mass = weights(train)
    lookup = {r['curve_id']:w for r,w in zip(train,mass)}
    counts = Counter(r['curve_id'] for r in auxiliary)
    if not portion:
        return train,mass
    endpoint_mass = [w*(1-portion) if r['curve_id'] in counts else w for r,w in zip(train,mass)]
    intermediate_mass = [lookup[r['curve_id']]*portion/counts[r['curve_id']] for r in auxiliary]
    return train+auxiliary,np.array(endpoint_mass+intermediate_mass)


def run():
    plan,data = checked()
    path = OUT/'fit_events.jsonl.gz'
    with (OUT/'run_claim.json').open('x',encoding='utf8') as claim:
        json.dump(dict(started_at=now(),plan_sha256=sha(OUT/'training_plan.json')),claim)
    start = time.monotonic(); n=0; failures=0; warning_count=0
    with gzip.open(path,'xt',encoding='utf8') as stream:
        for system,outer,fold,config,train,test,auxiliary in jobs(plan,data):
            encode = lambda rows: [expressed(r,config,'six') for r in rows]
            anchor = encode(train)
            encoder = Encoder().fit(anchor)
            x, xv = encoder.transform(anchor), encoder.transform(encode(test))
            xa = encoder.transform(encode(auxiliary))
            delta = lambda rows: np.array([r['target']-r['last_early'] for r in rows])
            d = delta(train); w = weights(train)
            center = float(np.average(d,weights=w))
            scale = float(np.sqrt(np.average((d-center)**2,weights=w))) or 1.
            for arm,portion in plan['arms'].items():
                tr,mass = weight_trial(train,auxiliary,portion)
                n+=1
                event = dict(index=n,system=system,outer=outer,inner_fold=fold,config=config['id'],arm=arm,
                             train_ids=[r['row_id'] for r in tr],test_ids=[r['row_id'] for r in test],
                             masses=mass.tolist(),encoder=encoder.schema,target_center=center,target_scale=scale)
                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter('always')
                    try:
                        model = estimator(config)
                        fit_weight = mass*len(train)
                        kwargs = {'sample_weight':fit_weight}
                        if config['kind']=='GPR':
                            model.set_params(alpha=config['parameters']['alpha']/fit_weight)
                            kwargs={}
                        model.fit(np.vstack([x,xa]) if portion else x,(delta(tr)-center)/scale,**kwargs)
                        predictions = model.predict(xv)*scale+center+np.array([r['last_early'] for r in test])
                        assert len(predictions)==len(test) and np.isfinite(predictions).all()
                        event.update(status='complete',predictions=predictions.tolist())
                    except Exception as error:
                        failures+=1
                        event.update(status='failed',error=repr(error))
                event['warnings']=[str(w.message) for w in caught]; warning_count+=len(caught)
                stream.write(json.dumps(event,ensure_ascii=False,allow_nan=False)+'\n')
                if n%80==0 or n==1:
                    stream.flush()
                    state=dict(status='running',completed_fits=n,planned_fits=plan['planned_fits'],failed_fits=failures,
                               warnings=warning_count,system=system,elapsed_seconds=round(time.monotonic()-start,1))
                    write(OUT/'progress.json',state);print(json.dumps(state),flush=True)
    assert n==plan['planned_fits']
    write(OUT/'progress.json',dict(status='fits_complete',completed_fits=n,planned_fits=n,failed_fits=failures,warnings=warning_count))


def evaluate():
    """Audit the archived fit memberships and masses, then score only author endpoints."""
    plan,data = checked()
    path = OUT/'fit_events.jsonl.gz'
    stored = {}
    with gzip.open(path,'rt',encoding='utf8') as stream:
        for line in stream:
            e=json.loads(line)
            key=(e['system'],e['outer'],e['inner_fold'],e['config'],e['arm'])
            assert key not in stored
            stored[key]=e
    assert len(stored)==plan['planned_fits']
    assert sorted(e['index'] for e in stored.values())==list(range(1,len(stored)+1))
    predictions=defaultdict(list); selections=[]; inner=defaultdict(list); outer_pred={}; audits=0
    for system,outer,fold,config,train,test,auxiliary in jobs(plan,data):
        original={r['curve_id']:w for r,w in zip(train,weights(train))}
        paired=[]
        for arm,portion in plan['arms'].items():
            e=stored[(system,outer,fold,config['id'],arm)]
            paired.append(e)
            tr=train+auxiliary if portion else train
            assert e['train_ids']==[r['row_id'] for r in tr] and e['test_ids']==[r['row_id'] for r in test]
            assert len(e['masses'])==len(tr) and min(e['masses'])>0
            total=defaultdict(float); extra=defaultdict(float); counts=Counter(r['curve_id'] for r in auxiliary)
            for i,(r,w) in enumerate(zip(tr,e['masses'])):
                total[r['curve_id']]+=w
                if i>=len(train):
                    extra[r['curve_id']]+=w
                    assert math.isclose(w,original[r['curve_id']]*portion/counts[r['curve_id']],rel_tol=1e-12)
                audits+=1
            for cid,w in original.items():
                assert math.isclose(total[cid],w,rel_tol=1e-12)
                assert math.isclose(extra[cid],w*portion if counts[cid] else 0.,rel_tol=1e-12)
                audits+=2
            if e['status']!='complete':
                continue
            assert len(e['predictions'])==len(test) and all(math.isfinite(v) for v in e['predictions'])
            pp=[predicted(system,config['id'],r,v) for r,v in zip(test,e['predictions'])]
            if fold is None:
                outer_pred[(system,outer,arm,config['id'])]=pp
                predictions[(system,arm,config['id'])].extend(pp)
            else:
                inner[(system,outer,arm,config['id'])].extend(pp)
        for field in ('encoder','target_center','target_scale'):
            assert paired[0][field]==paired[1][field]
            audits+=1
        # Cross-check the archived preprocessing with author rows only.
        assert paired[0]['encoder']==Encoder().fit([expressed(r,config,'six') for r in train]).schema
        audits+=1
    for system,group in data.items():
        rows=group['endpoints']
        for outer in plan['folds'][system]:
            train=[r for r in rows if r['source_family']!=outer]
            test=[r for r in rows if r['source_family']==outer]
            for r in test:
                mean=float(np.average([v['target'] for v in train],weights=weights(train)))
                f=r['features']; last=r['last_early']
                baseline=(mean,last,last+f['early_retention_slope_per_1000_cycles']*(f['target_cycle_count']-f['early_observed_cycle_count'])/1000.)
                for name,value in zip(BASELINES,baseline):
                    predictions[(system,'baseline',name)].append(predicted(system,name,r,value))
            for arm in plan['arms']:
                candidates=[]
                for config in plan['configurations']:
                    cid=config['id']; pp=inner[(system,outer,arm,cid)]
                    if len(pp)!=len(train) or {p['row_id'] for p in pp}!={r['row_id'] for r in train}:
                        continue
                    s=independent_score(pp)
                    candidates.append((s['mae'],s['rmse'],cid))
                if candidates:
                    chosen=min(candidates)[-1]
                    selections.append(dict(system=system,outer=outer,arm=arm,chosen=chosen,inner_scores=sorted(candidates)))
                    predictions[(system,arm,'nested_selected')].extend(outer_pred.get((system,outer,arm,chosen),[]))
    summary=[]; c=plan['criteria']
    for (system,arm,name),pp in sorted(predictions.items()):
        if not pp:
            continue
        m=metrics(pp,bootstrap=name=='nested_selected')
        s=independent_score(pp)
        for k,v in s.items():
            assert math.isclose(m[k],v,abs_tol=1e-9,rel_tol=1e-9)
            audits+=1
        reduction={b:1-m['mae']/independent_score(predictions[(system,'baseline',b)])['mae'] for b in BASELINES}
        gates=dict(coverage=len(pp)==len(data[system]['endpoints']) and len({r['row_id'] for r in pp})==len(pp),
                   positive=all(p['predicted']>0 for p in pp),r2=m['r2'] is not None and m['r2']>c['r2_gt'],
                   mae=m['mae']<=c['mae_pp_max'],rmse=m['rmse']<=c['rmse_pp_max'],mape=m['mape_pct']<=c['mape_pct_max'],
                   p90ape=m['p90_ape_pct']<=c['p90_ape_pct_max'],p90abs=m['p90_absolute_error']<=c['p90_abs_pp_max'],
                   source_tail=m['source_p90_mae']<=c['source_p90_mae_pp_max'],
                   baselines=all(v>=c['mae_reduction_vs_each_baseline_min'] for v in reduction.values()))
        summary.append(dict(m,system=system,arm=arm,method=name,gates=gates,mae_reduction=reduction,numeric_pass=all(gates.values())))
    failures=[e for e in stored.values() if e['status']!='complete']
    write(OUT/'fit_failures.json',failures)
    write(OUT/'selection.json',selections)
    write(OUT/'heldout_predictions.json',[dict(p,arm=arm,method=name) for (_,arm,name),pp in predictions.items() for p in pp])
    write(OUT/'results.json',dict(status='verified',fit_count=len(stored),failures=len(failures),warning_count=sum(len(e['warnings']) for e in stored.values()),
                                  checks=audits,protected_objects=len(plan['protected']),methods=summary,
                                  numeric_pass_count=sum(m['numeric_pass'] for m in summary),external_sources=0,
                                  goal_achieved=False,event_sha256=sha(path)))
    print(json.dumps([dict(system=m['system'],arm=m['arm'],r2=m['r2'],mae=m['mae'],rmse=m['rmse']) for m in summary if m['method']=='nested_selected']),flush=True)


if __name__=='__main__':
    {'freeze':freeze,'run':run,'evaluate':evaluate}[sys.argv[1]]()
