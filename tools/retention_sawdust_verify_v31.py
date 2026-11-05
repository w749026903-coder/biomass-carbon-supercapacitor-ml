"""Verify existing P31 fits using exact source-weighted percentile boundaries."""

from collections import Counter, defaultdict
from fractions import Fraction
import math
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.retention_sawdust_development_v31 import (
    BASELINES, OUT, SOURCE, checked_plan, gates, metrics, paired_error, predicted,
    read, score, sha, subsets, weights, write,
)


def exact_score(rows):
    """Keep the archived metrics except exact arithmetic for the weighted p90 rank."""
    per_source = defaultdict(Counter)
    for r in rows:
        per_source[r['source_family']][r['curve_id']] += 1
    weighted = []
    for r in rows:
        group = per_source[r['source_family']]
        w = Fraction(1, len(per_source) * len(group) * group[r['curve_id']])
        err = abs(r['predicted']-r['observed'])
        weighted.append((err, err/r['observed']*100, w))
    assert sum(w for _,_,w in weighted)==1
    values = score(rows)
    for axis,field in enumerate(('p90_absolute_error','p90_ape_pct')):
        cumulative = Fraction()
        for item in sorted(weighted,key=lambda x:x[axis]):
            cumulative += item[2]
            if cumulative >= Fraction(9,10):
                values[field] = item[axis]
                break
    return values


def main():
    plan = checked_plan()
    assert not (OUT/'results.json').exists(), 'Never overwrite scored outcomes'
    data,events = (read(OUT/k) for k in ('input_snapshot.json','fit_events.json'))
    index = {(e['system'],e['held'],e['config']):e for e in events}
    assert len(index)==len(events)==plan['planned_new_fits']
    assert set(index)=={(s,h,c['id']) for s,spec in plan['cohorts'].items() for h in spec['folds'] for c in spec['configurations']}
    scores,predictions,comparisons = {},{},[]
    checks = 0
    quantiles = {'p90_absolute_error','p90_ape_pct'}
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
        base = {name:exact_score(v) for name,v in baselines.items()}
        results = {}
        for key,v in variants.items():
            control = controls[key]
            ref = score(control)
            assert ref == archived[key]['full']
            if len(v)!=len(rows):
                results[key]=dict(complete=False,numeric_pass=False)
                continue
            assert {r['row_id']:r['observed'] for r in v}=={r['row_id']:r['target'] for r in rows}
            common = [p for p in v if p['source_family']!=SOURCE]
            assert {r['row_id']:r['observed'] for r in common}=={r['row_id']:r['observed'] for r in control}
            full = exact_score(v)
            left,right = score(v),metrics(v)
            for k,x in full.items():
                if k in quantiles:
                    if not all(math.isclose(x,a[k],abs_tol=1e-9) for a in (left,right)):
                        comparisons.append(dict(system=system,config=key,metric=k,archive_float=left[k],
                                                independent_float=right[k],exact_rank=x))
                else:
                    assert math.isclose(x,right[k],abs_tol=1e-9,rel_tol=1e-9)
                checks+=1
            gate = gates(v,full,base,plan['criteria'],len(rows))
            addition, = [p for p in v if p['source_family']==SOURCE]
            lo,hi = spec['sd_endpoint_geometry_band_pct']
            assert lo<=addition['observed']<=hi
            before = {p['row_id']:p for p in control}
            low_rows = [dict(row_id=p['row_id'],sample_name=p['sample_name'],observed=p['observed'],
                             before=before[p['row_id']]['predicted'],after=p['predicted'])
                        for p in common if p['observed']<=80.]
            results[key]=dict(complete=True,control_common=exact_score(control),expanded_common=exact_score(common),full=full,
                    common_mae_change=paired_error(common,control,plan['bootstrap']),old_low_rows=low_rows,
                    added=addition,added_signed_error_vs_band_pp=[addition['predicted']-hi,addition['predicted']-lo],
                    gates=gate,numeric_pass=all(gate.values()))
        scores[system]=dict(primary=spec['primary'],results=results,baselines=base,
                            numeric_passes=sum(x['numeric_pass'] for x in results.values()))
        predictions[system]=dict(loso=variants,baselines=baselines)
    write(OUT/'quantile_boundary_audit.json',dict(
        status='post_fit_verification_correction',
        first_verification='Floating point p90 implementations disagreed at the cumulative 0.9 boundary.',
        rule='First observation whose exact cumulative source and curve weight is at least 9/10. No interpolation.',
        discrepancies=comparisons,fit_events_sha256=sha(OUT/'fit_events.json'),
        frozen_plan_sha256=sha(OUT/'training_plan.json'),additional_fits=0))
    write(OUT/'heldout_predictions.json',predictions)
    write(OUT/'results.json',dict(status='verified_development',scores=scores,new_fits=sum(e['fit_attempted'] for e in events),
        failures=sum(e['status']!='complete' for e in events),warnings=sum(len(e['warnings']) for e in events),
        checks=checks,numeric_passes=sum(x['numeric_passes'] for x in scores.values()),external_sources=0,goal_achieved=False))


if __name__ == '__main__':
    main()
