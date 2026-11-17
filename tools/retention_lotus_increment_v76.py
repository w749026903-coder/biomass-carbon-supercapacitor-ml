"""One predeclared data-addition comparison using an already-seen lotus paper."""

import argparse
from collections import defaultdict
from copy import deepcopy
from pathlib import Path
import subprocess
import sys
import warnings
from xml.etree import ElementTree as ET

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.retention_literature_svr_v65 import BASE, P64, SCOPE, dataset, mix
from tools.retention_new_evidence_development_v59 import (
    environment, exact_score, fit, fold_data, gates, now, predicted, read, sha, weights, write,
)
from tools.retention_horizon_routes_v67 import OUT as P67, fit_weighted, worst_overprediction
from tools.retention_mild_scope_v64 import baselines, outside_reasons
from tools.retention_decline_guard_v63 import METRICS

OUT = BASE / "第七十六轮_莲茎补证与同批增量对照_20261118"
P73 = BASE / "第七十三轮_循环协议与历史终点核查_20261116"
P75 = BASE / "第七十五轮_盲测预测锁定核验_20261116"
CACHE = ROOT / ".local-literature-cache/P73"
SOURCE = "doi:10.1039/c7ra13013a"
GIT = ["git", "-c", f"safe.directory={ROOT.as_posix()}"]


def evidence():
    prior = read(P73 / "evidence.json")
    plot = CACHE / "sealed_c7ra13013a-f6.jpg"
    document = CACHE / "PMC9078325.sealed.xml"
    assert sha(plot) == prior["sealed_figures"][0]["sha256"]
    assert sha(document) == "c9dea3a7a6f0ac7b1df327ea64091675df0af08765fff5f86b502077584a0d15"
    xml = ET.fromstring(document.read_bytes())
    assert any(p.get("pub-id-type") == "doi" and p.text == SOURCE[4:]
               for p in xml.findall(".//article-meta/article-id"))
    caption = "".join(xml.find(".//fig[@id='fig6']").itertext())
    assert "three electrodes" in caption and "5 A" in caption
    img = np.asarray(Image.open(plot).convert("RGB")).astype(float)
    # Tick calibration is recorded independently of the stars and the endpoint.
    axes = dict(x_zero_px=388., x_5000_px=693., y_zero_pct_px=458.5, y_100_pct_px=282.5)
    points = []
    for center in [395, 403, 411, 419, 426, 434, 441]:
        rgb = img[278:288, center-3:center+4]
        xx, yy = np.meshgrid(np.arange(center-3, center+4), np.arange(278, 288))
        mass = np.maximum(0, np.ptp(rgb, axis=2)-30)
        x, y = (float((z*mass).sum()/mass.sum()) for z in (xx, yy))
        cycle = (x-axes['x_zero_px'])/(axes['x_5000_px']-axes['x_zero_px'])*5000
        error = 2/(axes['x_5000_px']-axes['x_zero_px'])*5000
        retention = (axes['y_zero_pct_px']-y)/(axes['y_zero_pct_px']-axes['y_100_pct_px'])*100
        points.append(dict(pixel_x=x, pixel_y=y, cycle_coordinate=cycle,
                           cycle_lower=cycle-error, cycle_upper=cycle+error,
                           retention_pct=retention))
    assert all(0 < p['cycle_lower'] <= p['cycle_upper'] <= 1000 for p in points)
    x, y = (np.array([p[k] for p in points]) for k in ('cycle_coordinate', 'retention_pct'))
    f = dict(last_early_retention_pct=float(y[-1]), early_mean_retention_pct=float(y.mean()),
             early_retention_slope_per_1000_cycles=float(np.polyfit(x/1000, y, 1)[0]),
             early_retention_range_pp=float(np.ptp(y)), early_observed_cycle_count=float(x[-1]),
             target_cycle_count=5000.)
    key = f"development:{SOURCE}::3E::LS-NC-600"
    r = dict(row_id=key+'::early20', endpoint_id=key, curve_id=key, material_key=key,
             source_family=SOURCE, sample_name="LS-NC-600", target=96., features=f,
             static_features=dict(electrolyte="KOH", concentration_mol_L=6., reported_current_A_g=5.,
                                  BET_m2_g=1322., cycle_voltage_lower_V=None,
                                  cycle_voltage_upper_V=None, reference_electrode="Hg/HgO"),
             last_early=f['last_early_retention_pct'], role="development_only_author_reported",
             evidence=(OUT/'curve_evidence.json').relative_to(ROOT).as_posix(), early_markers=len(points))
    return dict(source=SOURCE, sample="LS-NC-600", figure="6(d)", system="3E", axes=axes,
                points=points, row=r, historical_terminal_exposure=True, blind_external_eligible=False,
                figure_url="https://pmc-oa-opendata.s3.amazonaws.com/PMC9078325.1/c7ra13013a-f6.jpg",
                source_url="https://pmc.ncbi.nlm.nih.gov/articles/PMC9078325/",
                protected_files={p.relative_to(ROOT).as_posix():sha(p) for p in (plot,document,P73/'evidence.json')},
                axis_reading_uncertainty_px=1, marker_reading_uncertainty_px=1,
                x_coordinate_bound_px=2, ordinate_uncertainty_approx_pp=2/176*100,
                normalization="Author retention axis in percent; no reanchoring to the first visible marker.",
                label="Author text in Electrochemical performance, paragraph 4, 96% at 5000 cycles; already exposed in historical abstract.",
                protocol="Methods and Fig. 6(d) explicitly link 3E, 6 M KOH and 5 A/g. No current mass-denominator inference from capacitance formula.",
                bet="Body adsorption paragraph gives 600/700/800/900 C values 1322/2013/2221/1986 m2/g in order. LS-NC-600 is outside BET>=1500.",
                unresolved="Exact original capacitance reference and mass denominator not additionally specified. Three-electrode cycling potential limits not inferred from two-electrode Fig. 6(a,b). Coloured star centers are figure readings, not raw instrument data.")


def freeze():
    assert not OUT.exists()
    old, cohort, rows = dataset()
    assert environment() == old['environment']
    proof = evidence()
    addition = proof['row']
    assert SOURCE not in {r['source_family'] for r in rows}
    assert not outside_reasons(addition, cohort['rules'])
    assert len(rows) == 23 and len({r['source_family'] for r in rows}) == 18
    expanded = rows+[addition]
    sources = sorted({r['source_family'] for r in expanded})
    folds = {s:dict(train=[r['row_id'] for r in expanded if r['source_family'] != s],
                         test=[r['row_id'] for r in expanded if r['source_family'] == s]) for s in sources}
    long_sources = sorted({r['source_family'] for r in rows if r['features']['target_cycle_count'] == 10000})
    OUT.mkdir()
    write(OUT/'curve_evidence.json', proof)
    write(OUT/'input_snapshot.json', expanded)
    guard = [Path(__file__), OUT/'curve_evidence.json', OUT/'input_snapshot.json',
             *(P64/n for n in ('training_plan.json','predictions.json','applicability.json')),
             *(P67/n for n in ('training_plan.json','midpoint_evidence.json','diagnostic_10000.json')),
             P75/'early_registry.json', P75/'locked_predictions.json', P75/'revealed_case.json',
             BASE/'research_goal.json', ROOT/'data/current_training_latest.json',
             ROOT/'data/current_retention_research.json']
    guard.extend(ROOT/p for p in proof['protected_files'])
    guard.extend(ROOT/'tools'/f'{name}.py' for name in (
        'retention_new_evidence_development_v59','retention_mild_scope_v64','retention_horizon_routes_v67',
        'retention_literature_svr_v65','retention_shape_v4','retention_sawdust_verify_v31'))
    write(OUT/'training_plan.json', dict(
        frozen_at=now(), parent_git=subprocess.check_output([*GIT,'rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        environment=old['environment'], configurations=old['configurations'], criteria=old['criteria'],
        folds=folds, long_sources=long_sources, old_ids=[r['row_id'] for r in rows], new_id=addition['row_id'],
        planned_fits=2*(len(sources)+len(long_sources)), routes=['p64','p67_routed'],
        single_change="One previously exposed development source added. Same fixed models, 50/50 blend, original 15 midpoint observations and 75:25 original/midpoint shares; no new midpoint extraction or parameter changes.",
        decision="Primary matched old 20-row KOH2-6 scope, secondary old23 and expanded21/24. Promote only if matched MAE decreases and no other tracked metric, worst overprediction or long-target MAE regresses. Judge independent acceptance separately. Preserve the frozen P70/P75 external predictions.",
        research_direction_review="If added evidence fails the matched regression test, preserve archived model and reassess usable data, digitization, scope and input information. Do not add another parameter grid just to pursue the observed score.",
        external_scope="PSCN P75 is kept out of every fit and new candidate selection. No new independent test here.",
        protected={p.relative_to(ROOT).as_posix():sha(p) for p in guard}))
    print('Frozen',len(expanded),'rows',len(sources),'sources',2*(len(sources)+len(long_sources)),'fits')


def checked():
    p = OUT/'training_plan.json'
    plan = read(p)
    assert subprocess.check_output([*GIT,'show',f'HEAD:{p.relative_to(ROOT).as_posix()}'],cwd=ROOT) == p.read_bytes()
    assert environment() == plan['environment']
    assert all(sha(ROOT/k) == v for k,v in plan['protected'].items())
    rows = read(OUT/'input_snapshot.json')
    assert SOURCE in {r['source_family'] for r in rows}
    assert 'doi:10.1039/d1ma00679g' not in {r['source_family'] for r in rows}
    return plan, rows


def run():
    plan, rows = checked()
    assert not (OUT/'fit_events.json').exists()
    with (OUT/'run_claim.json').open('x',encoding='utf-8') as h:
        import json
        json.dump(dict(started=now(),plan_sha256=sha(OUT/'training_plan.json')),h)
    midpoint = read(P67/'midpoint_evidence.json')
    old67 = read(P67/'training_plan.json')
    events = []
    for route in ('p64','midpoint'):
        for source, split in plan['folds'].items():
            if route == 'midpoint' and source not in plan['long_sources']:
                continue
            train, test = fold_data(rows,source,split)
            if route == 'midpoint':
                test = [r for r in test if r['features']['target_cycle_count'] == 10000]
            for cfg in plan['configurations']:
                event = dict(route=route,source=source,model=cfg['id'],train=[r['row_id'] for r in train],
                             test=[r['row_id'] for r in test],attempted=False)
                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter('always')
                    if route == 'p64':
                        values = fit(cfg,train,test,event)
                        event['extra'] = []
                    else:
                        w = weights(train)
                        extra, parts = [], []
                        for i,r in enumerate(train):
                            if r['row_id'] in midpoint:
                                extra.append(midpoint[r['row_id']]['row'])
                                part = w[i]*old67['midpoint_share']
                                w[i] -= part
                                parts.append(part)
                        assert source not in {r['source_family'] for r in train+extra}
                        assert not {r['curve_id'] for r in train+extra} & {r['curve_id'] for r in test}
                        values = fit_weighted(cfg,train,extra,test,w,parts,event)
                        event['extra'] = [r['row_id'] for r in extra]
                    event.update(status='complete',predictions=[predicted('3E',cfg['id'],r,v) for r,v in zip(test,values,strict=True)])
                event['warnings'] = [str(w.message) for w in caught]
                events.append(event)
    assert len(events) == plan['planned_fits']
    write(OUT/'fit_events.json', events)
    print('Finished',len(events),'fits')


def verify():
    plan, rows = checked()
    events = read(OUT/'fit_events.json')
    assert read(OUT/'run_claim.json')['plan_sha256'] == sha(OUT/'training_plan.json')
    assert len(events) == plan['planned_fits']
    assert len({(e['route'],e['source'],e['model']) for e in events}) == len(events)
    by = defaultdict(list)
    for e in events:
        assert e['status'] == 'complete' and e['attempted']
        assert e['train'] == plan['folds'][e['source']]['train']
        assert all(r['source_family'] == e['source'] for r in e['predictions'])
        assert [r['row_id'] for r in e['predictions']] == e['test']
        by[e['route'],e['model']].extend(e['predictions'])
    methods = {}
    for route in ('p64','midpoint'):
        a,b = (by[route,c['id']] for c in plan['configurations'])
        methods[route] = mix(a,b,[.5,.5],route)
    long = {r['row_id']:r for r in methods['midpoint']}
    methods['p67_routed'] = [long.get(r['row_id'],r) for r in methods['p64']]
    old = dict(p64=read(P64/'predictions.json')[SCOPE]['methods']['half_GPR_RF'],
               p67_routed=read(P67/'diagnostic_10000.json')['predictions'])
    simple = baselines(rows,plan['folds'])
    results = {}
    for method in ('p64','p67_routed'):
        values = methods[method]
        assert {r['row_id']:r['observed'] for r in values} == {r['row_id']:r['target'] for r in rows}
        selections = dict(old23=set(plan['old_ids']), expanded24={r['row_id'] for r in rows})
        koh = {r['row_id'] for r in rows if r['static_features']['concentration_mol_L'] >= 2}
        selections.update(old20=selections['old23'] & koh, expanded21=selections['expanded24'] & koh)
        sections = {}
        for name, ids in selections.items():
            current = [r for r in values if r['row_id'] in ids]
            reference = [r for r in old[method] if r['row_id'] in ids]
            s = exact_score(current)
            bases = {k:exact_score([r for r in v if r['row_id'] in ids]) for k,v in simple.items()}
            section = dict(rows=len(current),sources=len({r['source_family'] for r in current}),metrics=s,
                           worst_overprediction=worst_overprediction(current),baselines=bases,
                           gates=gates(current,s,bases,plan['criteria'],len(ids)))
            if name.startswith('old'):
                assert {r['row_id']:r['observed'] for r in current} == {r['row_id']:r['observed'] for r in reference}
                before = exact_score(reference)
                failures = [k for k in METRICS if (s[k] < before[k]-1e-10 if k=='r2' else s[k] > before[k]+1e-10)]
                if worst_overprediction(current)['pp'] > worst_overprediction(reference)['pp']+1e-10:
                    failures.append('worst_overprediction')
                lc = [r for r in current if r['row_id'] in long]
                lr = [r for r in reference if r['row_id'] in long]
                if exact_score(lc)['mae'] > exact_score(lr)['mae']+1e-10:
                    failures.append('10000_mae')
                section.update(before=before,delta={k:s[k]-before[k] for k in s},regression=failures,
                               eligible=not failures and s['mae'] < before['mae']-1e-10)
            sections[name] = section
        results[method] = sections
    new_rows = {k:[r for r in v if r['row_id'] == plan['new_id']][0] for k,v in methods.items() if k!='midpoint'}
    write(OUT/'predictions.json', {k:methods[k] for k in ('p64','p67_routed')})
    write(OUT/'results.json',dict(fits=len(events),failures=0,warnings=sum(len(e['warnings']) for e in events),
        results=results,new_source_heldout=new_rows,model_promoted=False,
        independent_external_scored_sources_preserved=1,new_external_sources=0,formal_acceptance=False))
    print({k:{s:v[s]['metrics'] for s in ('old20','expanded21')} for k,v in results.items()})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('step',choices=('freeze','run','verify'))
    {'freeze':freeze,'run':run,'verify':verify}[parser.parse_args().step]()
