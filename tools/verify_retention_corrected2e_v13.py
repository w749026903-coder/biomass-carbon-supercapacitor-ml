"""Audit P13 against the frozen source splits and the corrected SQL approval."""
import collections
import gzip
import json
import math
import sqlite3
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools import verify_retention_v3b as independent
from tools.verify_retention_expanded2e_v6 import rawfeatures
from tools.retention_shape_v4 import FIELDS, NEAR, SIMPLE
from tools.retention_corrected2e_v13 import BATCH, MK9, OLD, OUT, R10, R20, ROOT, checked_plan, key, read, sha, verify_old10, write


def audit_encoding(event, config, train):
    w = independent.wts(train)
    target = [r['target']-r['last_early'] if config['target']=='delta' else math.log(r['target']/r['last_early']) for r in train]
    center = float(np.dot(w,target))
    scale = float(np.sqrt(np.dot(w,(np.asarray(target)-center)**2))) or 1.
    independent.close(center,event['target_center'])
    independent.close(scale,event['target_scale'])
    features = [rawfeatures(r,config,event['view']) for r in train]
    expected = []
    for field in sorted(set().union(*features)):
        known = [i for i,row in enumerate(features) if row.get(field) is not None]
        if len(known) < max(2,int(.15*len(train))) or len({train[i]['source_family'] for i in known}) < 3:
            continue
        expected.append(field)
        observed = [features[i][field] for i in known]
        column = next(c for c in event['encoder'] if c['field'] == field)
        if all(isinstance(v,str) for v in observed):
            independent.check(column['kind']=='categorical' and column['vocab']==sorted(set(observed)))
            continue
        med = float(np.median(observed))
        values = np.asarray([row[field] if row.get(field) is not None else med for row in features])
        log = min(observed)>=0 and any(tag in field.lower() for tag in ('bet','volume','current','ratio','cycle_count'))
        values = np.log1p(values) if log else values
        mean = float(np.dot(w,values))
        sd = float(np.sqrt(np.dot(w,(values-mean)**2))) or 1.
        independent.check(column['kind']=='numeric' and column['log']==log)
        for actual, reconstructed in ((column['median'],med),(column['center'],mean),(column['scale'],sd)):
            independent.close(actual,reconstructed)
    independent.check([c['field'] for c in event['encoder']]==expected)
    independent.check(event['shape_fields_retained']==[f for f in expected if f in FIELDS])


def main():
    ck, close, score = independent.check, independent.close, independent.score
    plan = checked_plan()
    data = read(OUT/'input_snapshot.json')
    rows = data[R20]
    configs = read(OUT/'candidate_configurations.json')
    prior = verify_old10(data,plan,configs)
    ck(prior==read(OUT/'verified_old10_reuse.json'))
    ck(prior['fit_predictions_reused']==2880)
    old = read(OLD/'input_snapshot.json')
    ck(data[R10]==old[R10])
    ck([a['endpoint_id'] for a,b in zip(rows,old[R20]) if a!=b]==[MK9] and len(rows)==len(old[R20]))
    by_id = {r['row_id']:r for r in rows}
    ck(len(rows)==len(by_id)==27 and len({r['source_family'] for r in rows})==22)
    ck(all(r['system']=='2E' and r['fraction']==.2 for r in rows))

    db_path = BATCH/'cycling_research_v3h.sqlite'
    with sqlite3.connect(db_path.as_uri()+'?mode=ro',uri=True) as db:
        ck(db.execute('PRAGMA integrity_check').fetchone()[0]=='ok')
        ck(not db.execute('PRAGMA foreign_key_check').fetchall())
        approved = {a:b for a,b in db.execute('SELECT curve_id,target_retention_pct FROM training_B_2E_early20')}
        ck(set(approved)=={r['curve_id'] for r in rows})
        for r in rows:
            ck(r['target']==approved[r['curve_id']])
            sql = 'SELECT raw_json FROM curve_points WHERE curve_id=? AND cycle_upper<=? ORDER BY marker_index'
            points = [json.loads(p[0]) for p in db.execute(sql,(r['curve_id'],.2*r['features']['target_cycle_count']))]
            ck(len(points)>=3 and r['early_points']==points)
        ck(db.execute('SELECT approved FROM curves WHERE curve_id=?',('marker_v2:'+MK9,)).fetchone()==(0,))
        ck(approved['metric_v3h:'+MK9]==65.)

    with (OUT/'fit_events.jsonl').open(encoding='utf8') as stream:
        events = [json.loads(line) for line in stream]
    ck([e['fit_index'] for e in events]==list(range(1,3521)))
    all_predictions = {}
    with gzip.open(OUT/'fit_predictions.jsonl.gz','rt',encoding='utf8') as stream:
        for line in stream:
            p = json.loads(line)
            ck(key(p) not in all_predictions and not p['reused'])
            all_predictions[key(p)] = p
    ck(len(all_predictions)==3520 and len({key(e) for e in events})==3520)
    ck(set(all_predictions)=={key(e) for e in events})
    splits = {s['outer_source']:s['inner_held_sources'] for s in plan['splits'][R20]}
    cfg = {c['id']:c for c in configs}
    warning_counts = collections.Counter()
    inner = collections.defaultdict(list)
    outer = {}
    for e in events:
        route,held,config_id,role,fold = key(e)
        ck(route==R20 and e['status']=='complete')
        view, base_id = config_id.split('::',1)
        ck(view in plan['views'] and e['view']==view and e['base_config_id']==base_id)
        ck(role in ('outer','inner') and ((role=='outer' and fold is None) or (role=='inner' and fold in range(4))))
        test_groups = {held} if role=='outer' else set(splits[held][fold])
        train = [r for r in rows if r['source_family'] not in test_groups|{held}]
        test = [r for r in rows if r['source_family'] in test_groups]
        ck(not {r['curve_id'] for r in train}&{r['curve_id'] for r in test})
        ck(e['train_row_ids']==[r['row_id'] for r in train] and e['test_row_ids']==[r['row_id'] for r in test])
        ck(e['train_sources']==sorted({r['source_family'] for r in train}) and e['test_sources']==sorted(test_groups))
        archive = all_predictions[key(e)]
        ck(archive['fit_index']==e['fit_index'])
        pred = archive['predictions']
        ck([(p['row_id'],p['observed']) for p in pred]==[(r['row_id'],r['target']) for r in test])
        ck(all(math.isfinite(p['predicted']) for p in pred))
        audit_encoding(e,cfg[base_id],train)
        warning_counts.update(e['warnings'])
        if role=='inner':
            inner[(held,config_id)].extend(pred)
        else:
            outer[(held,config_id)]={p['row_id']:p['predicted'] for p in pred}

    prediction_rows = read(OUT/'heldout_predictions.json')
    by_model = collections.defaultdict(dict)
    for r in prediction_rows:
        ck(r['route']==R20 and r['observed']==by_id[r['row_id']]['target'])
        ck(r['row_id'] not in by_model[r['model']])
        by_model[r['model']][r['row_id']]=r
    selections = read(OUT/'nested_selection.json')
    ck(len(selections)==len(splits) and {s['outer_source'] for s in selections}==set(splits))
    config_ids = [v+'::'+c for v in plan['views'] for c in cfg]
    for selection in selections:
        held = selection['outer_source']
        tr = [r for r in rows if r['source_family']!=held]
        test = [r for r in rows if r['source_family']==held]
        scores = {}
        for cid in config_ids:
            pp = inner[(held,cid)]
            ck(len(pp)==len(tr) and {p['row_id'] for p in pp}=={r['row_id'] for r in tr})
            scores[cid] = score(pp)
            summary = next(v for v in selection['scores'] if v['config_id']==cid)
            for field in ('mae','rmse'):
                close(scores[cid][field], summary[field])
        rank = lambda c:(scores[c]['mae'],scores[c]['rmse'],c)
        methods = {}
        for view in ('six','shape','joint'):
            candidates = [c for c in config_ids if view=='joint' or c.startswith(view+'::')]
            best = min(candidates,key=rank)
            families = {f:min([c for c in candidates if cfg[c.split('::',1)[1]]['family']==f],key=rank) for f in SIMPLE}
            source_errors = collections.defaultdict(list)
            for p in inner[(held,best)]:
                source_errors[p['source_family']].append(abs(p['observed']-p['predicted']))
            se = float(np.std([np.mean(v) for v in source_errors.values()],ddof=1)/math.sqrt(len(source_errors)))
            selected = [f for f in SIMPLE if scores[families[f]]['mae']<=scores[best]['mae']+se+1e-12]
            ck(selection['views'][view]['winner']==best)
            close(selection['views'][view]['inner_source_mae_standard_error'],se)
            methods[view+'_nested_selected']=[best]
            methods[view+'_oneSE_family_mean']=[families[f] for f in selected]
            methods[view+'_near4_equal']=[families[f] for f in NEAR]
            methods.update({view+'_family::'+f:[c] for f,c in families.items()})
        ck(methods==selection['methods'])
        candidates = dict(methods, **{'fixed::'+c:[c] for c in config_ids})
        mean = float(np.dot(independent.wts(tr),[r['target'] for r in tr]))
        for r in test:
            rid = r['row_id']
            for m,cids in candidates.items():
                close(by_model[m][rid]['predicted'],float(np.mean([outer[(held,c)][rid] for c in cids])))
            for name,value in dict(training_mean=mean,early_persistence=r['last_early'],early_linear=r['linear_forecast']).items():
                close(by_model[name][rid]['predicted'],value)

    result = read(OUT/'results.json')
    ck(len(result['metrics'])==len(by_model)==68)
    ck(result['primary']==plan['primary'] and result['exact_reuse']==prior)
    ck(result['new_estimator_fits']==3520 and not result['goal_achieved'] and result['new_external_sources']==0)
    ck(result['failed_estimator_fits']==0 and read(OUT/'fit_failures.json')==[])
    scores = {m:score(list(pred.values())) for m,pred in by_model.items()}
    limits = plan['criteria']
    for m in result['metrics']:
        s = scores[m['model']]
        for name,value in s.items():
            close(m[name],value)
        checks = dict(r2=s['r2']>limits['r2_gt'],mae=s['mae']<=limits['mae_pp_max'],rmse=s['rmse']<=limits['rmse_pp_max'],
                      mape=s['mape_pct']<=limits['mape_pct_max'],p90_ape=s['p90_ape_pct']<=limits['p90_ape_pct_max'],
                      p90_abs=s['p90_absolute_error']<=limits['p90_abs_pp_max'],source_tail=s['source_p90_mae']<=limits['source_p90_mae_pp_max'],
                      coverage=set(by_model[m['model']])==set(by_id),positive=all(p['predicted']>0 for p in by_model[m['model']].values()))
        for name in plan['baselines']:
            reduction = 1-s['mae']/scores[name]['mae']
            close(m['mae_reduction_vs_'+name],reduction)
            checks['beat_'+name]=reduction>=limits['mae_reduction_vs_each_baseline_min']
        ck(checks==m['checks'] and all(checks.values())==m['numeric_pass'])
        ck(m['at_least10_sources'] and not m['untouched_external_test'] and not m['reliable_model_accepted'])
    ck(result['numeric_pass_count']==sum(m['numeric_pass'] for m in result['metrics']))
    checked_plan()
    audit = dict(status='passed',checks=independent.CHECKS,protected_objects=read(OUT/'freeze_receipt.json')['protected_objects'],
                 new_fits=3520,reused_10pct_fits=2880,warnings=dict(warning_counts),failures=0,untouched_external_sources=0,
                 endpoint_retention_MK9=65.,old_misclassified_P12_20pct_invalid=True,numeric_passes=result['numeric_pass_count'],
                 results_sha256=sha(OUT/'results.json'),verifier_sha256=sha(Path(__file__)),
                 limits='Audit reconstructs input membership, encoders, inner selection, predictions aggregation and metrics. Model weights were not independently refit.')
    write(OUT/'independent_verification.json',audit)
    print(json.dumps(audit,ensure_ascii=False),flush=True)


if __name__=='__main__':
    main()
