"""Review early arcs and lock a one-paper external case before endpoint disclosure."""
from pathlib import Path
import json
import sys
import warnings

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.prepare_small_sample_routes import read, write, sha, now

BASE = ROOT/'保持率达标研究_v3_主线与近优组合_20261030'
P14 = BASE/'第十四轮_中段监督对照_20261104'
P15 = BASE/'第十五轮_外部候选盲态核验_20261104'
OUT = BASE/'第十六轮_外部单篇预测锁定_20261104'
DOI = '10.3390/nano16211412'
SOURCE_ID = 'doi:'+DOI
PANELS = {
    '3E': dict(page=12, figure='13', crop=(354,33,652,310), observed_from=(354,42), radius=16,
               centers=(384,404,424,444,464,484,504,524,544,565,584,604,624,644), expected=(7,14)),
    '2E': dict(page=13, figure='14e', crop=(1440,1092,1904,1360), observed_from=(1447,1097), radius=14,
               centers=(1444,1451,1477,1500,1512,1535,1559,1581,1627,1673), expected=(9,10)),
}


def best_arc(mask, panel, expected_x):
    """Find a circle supported by the transition from coloured to uncoloured pixels."""
    left,top,right,bottom = panel['crop']
    x_min,y_min = panel['observed_from']
    X,Y = np.meshgrid(np.arange(expected_x-3,expected_x+4),np.arange(top+3,bottom-15))
    angles = np.linspace(0,2*np.pi,96,endpoint=False)
    best = None
    for radius in (panel['radius']-.5,panel['radius'],panel['radius']+.5):
        support = np.zeros(X.shape,dtype=int)
        visible = np.zeros_like(support)
        quadrants = np.zeros((*X.shape,4),dtype=int)
        for k,t in enumerate(angles):
            xi = X+round((radius-1.5)*np.cos(t)); yi = Y+round((radius-1.5)*np.sin(t))
            xo = X+round((radius+1.5)*np.cos(t)); yo = Y+round((radius+1.5)*np.sin(t))
            valid = (xi>=x_min)&(xo>=x_min)&(yi>=y_min)&(yo>=y_min)&(xi<right)&(xo<right)&(yi<bottom)&(yo<bottom)
            inside = mask[np.clip(yi-top,0,mask.shape[0]-1),np.clip(xi-left,0,mask.shape[1]-1)]
            outside = mask[np.clip(yo-top,0,mask.shape[0]-1),np.clip(xo-left,0,mask.shape[1]-1)]
            hit = valid & inside & ~outside
            support += hit; visible += valid; quadrants[...,k//24] += hit
        merit = support + .08*support/np.maximum(visible,1)
        i,j = np.unravel_index(merit.argmax(),merit.shape)
        found = dict(x=int(X[i,j]),y=int(Y[i,j]),radius_px=radius,matched_rays=int(support[i,j]),
                     visible_rays=int(visible[i,j]),quadrant_matches=quadrants[i,j].tolist(),merit=float(merit[i,j]))
        if best is None or found['merit']>best['merit']:
            best=found
    assert best['matched_rays']>=30 and sum(q>0 for q in best['quadrant_matches'])>=2
    return best


def feature_row(rows, horizon, fraction):
    points = [p for p in rows if p['cycle_interval'][1]<=horizon*fraction]
    assert len(points)>=3
    x=np.array([p['cycle_reading'] for p in points]); y=np.array([p['early_ordinate_pct'] for p in points])
    assert np.all(np.diff(x)>0)
    slope=np.dot(x-x.mean(),y-y.mean())/np.dot(x-x.mean(),x-x.mean())
    return dict(last_early_retention_pct=float(y[-1]),early_mean_retention_pct=float(y.mean()),
                early_retention_slope_per_1000_cycles=float(slope*1000),early_retention_range_pp=float(np.ptp(y)),
                early_observed_cycle_count=float(x[-1]),target_cycle_count=horizon),len(points)


def refine():
    from PIL import Image, ImageDraw
    import pypdfium2 as pdf
    from tools.screen_suaeda_early_v15 import trace_mask

    assert not OUT.exists()
    receipt=read(P15/'candidate_evidence.json')
    assert receipt['terminal_label_records']==0
    source=receipt['candidate']; pdf_path=ROOT/source['file']['cache_path']
    assert sha(pdf_path)==source['file']['sha256']
    old=read(P15/'early_marker_screen.json'); calibration={p['system']:p['panel'] for p in old['panels']}
    assert sha(P15/'early_marker_screen.json')==receipt['marker_screen_sha256']
    images={}; results={}
    doc=pdf.PdfDocument(pdf_path)
    try:
        for system,panel in PANELS.items():
            c=calibration[system]; horizon=source['target_cycle_count']
            left,top,right,bottom=panel['crop']
            assert right-1<=c['x0']+.2*(c['xN']-c['x0'])
            page=doc[panel['page']-1]
            embedded=[o for o in page.get_objects() if o.type==pdf.raw.FPDF_PAGEOBJ_IMAGE][-1]
            assert tuple(embedded.get_px_size())==tuple(c['size'])
            rgb=np.array(embedded.get_bitmap().to_pil().convert('RGB').crop(panel['crop']))
            mask=trace_mask(system,rgb); safe=np.full_like(rgb,255); safe[mask]=rgb[mask]
            image=Image.fromarray(safe); draw=ImageDraw.Draw(image)
            points=[]; cycle_scale=horizon/(c['xN']-c['x0']); y_scale=100/(c['y0']-c['y100'])
            for expected in panel['centers']:
                m=best_arc(mask,panel,expected); x,y=m['x'],m['y']
                draw.rectangle((x-left-2,y-top-2,x-left+2,y-top+2),outline='black')
                cycle=(x-c['x0'])*cycle_scale; value=(c['y0']-y)*y_scale
                points.append(dict(m,expected_x_band=expected,cycle_reading=cycle,early_ordinate_pct=value,
                                   cycle_interval=[max(0.,cycle-4*cycle_scale),cycle+4*cycle_scale],
                                   ordinate_interval_pp=[value-4*y_scale,value+4*y_scale]))
            windows={}
            for f,n in zip((.1,.2),panel['expected']):
                feat,count=feature_row(points,horizon,f);assert count==n
                windows[str(f)]=dict(features=feat,marker_count=count)
            # Missing optional fields remain missing. No use of current normalization formulas.
            static=dict(reported_current_A_g=5.,electrolyte='KOH',concentration_mol_L=6.,BET_m2_g=1536.,
                        cycle_voltage_lower_V=None,cycle_voltage_upper_V=None)
            if system=='3E':static['reference_electrode']='Hg/HgO'
            results[system]=dict(figure=panel['figure'],page=panel['page'],pixels=points,windows=windows,
                                 static_features=static,source_family=SOURCE_ID,voltage_window_status='not linked to the cycle test',
                                 current_mass_basis_status='not verified',early_mask_crop=list(panel['crop']))
            images[system]=image
    finally:
        doc.close()
    OUT.mkdir()
    for system,image in images.items():
        path=OUT/f'{system}_圆弧复核.png';image.save(path)
        results[system]['image']=path.name;results[system]['image_sha256']=sha(path)
    write(OUT/'locked_early_inputs.json',dict(doi=DOI,source_count=1,raw_pdf_sha256=source['file']['sha256'],
          original_screen_sha256=sha(P15/'early_marker_screen.json'),target_cycle_count=10000,
          terminal_labels_entered=0,geometry_rule='Visible pixel arcs, not marker highlights. Four-pixel allowance; include only if upper cycle bound is inside each window.',
          boundary_exclusion='Fig. 14e blue marker adjacent to the 2,000-cycle tick is only partly exposed and can cross the 20% cutoff. Excluded from features and retained in the visible crop.',
          figure_normalization='Use published retention-axis ordinate directly, including values above 100. No re-normalizing the near-origin 2E points.',
          systems=results))
    print({s:{k:v['marker_count'] for k,v in g['windows'].items()} for s,g in results.items()})


def freeze():
    """Commit before fitting. Model ranking uses only P14 held-source errors."""
    from tools.retention_corrected2e_v13 import environment

    assert not (OUT/'training_plan.json').exists()
    evidence=read(OUT/'locked_early_inputs.json');assert evidence['terminal_labels_entered']==0
    previous=read(P14/'training_plan.json'); data=read(P14/'input_snapshot.json'); result=read(P14/'results.json')
    assert result['status']=='verified' and result['external_sources']==0
    assert sha(P14/'input_snapshot.json')==previous['data_sha256'] and environment()==previous['environment']
    selected={}
    for s,d in data.items():
        assert all(r['source_family']!=SOURCE_ID for r in d['endpoints']+d['intermediate'])
        ids={c['id'] for c in previous['configurations']}
        ranked=sorted((v['mae'],v['rmse'],v['method']) for v in result['methods']
                      if v['system']==s and v['arm']=='author_only' and v['method'] in ids and v['gates']['coverage'])
        assert len(ranked)==8
        selected[s]=dict(primary=ranked[0][-1],development_ranking=ranked)
    protected={p.relative_to(ROOT).as_posix():sha(p) for p in [Path(__file__),OUT/'locked_early_inputs.json',
            P14/'training_plan.json',P14/'input_snapshot.json',P14/'results.json',P15/'candidate_evidence.json',
            P15/'early_marker_screen.json',ROOT/'data/current_retention_research.json',ROOT/'data/current_training_latest.json',
            ROOT/'tools/retention_intermediate_v14.py',ROOT/'tools/retention_v3_optimizer.py',ROOT/'tools/retention_shape_v4.py',
            ROOT/'tools/run_small_sample_routes.py',ROOT/'tools/prepare_small_sample_routes.py',BASE/'research_goal.json']}
    plan=dict(frozen_at=now(),protected=protected,environment=environment(),source=SOURCE_ID,
              scope='One prospective literature case, 2E and 3E evaluated separately at the approved 20% window. This cannot establish group R2 or reliable external generalization.',
              source_overlap='Published own sample preparation, zero exact DOI in prior 3h/v7r1, no direct matching names or sample identified. Broader data-family overlap not proved absent.',
              admission='Case evidence only under reported protocol and optional static values. Both cycling voltage limits and current mass basis unresolved.',
              configurations=previous['configurations'],selected=selected,planned_fits=16,window_fraction=.2,
              model='P14 author-only training, same feature expression, source/curve weights and GPR precision weighting; all 8 models per system. Primary fixed by development MAE, then RMSE, then config ID.',
              baselines=['training_mean','early_persistence','early_linear'],criteria=read(BASE/'research_goal.json')['criteria'],
              unlocking_rule='Record and commit predictions before accessing or exporting any author endpoint value. Preserve separate raw graph reading and author evidence.',
              no_refit_after_case=True,terminal_labels_available=False)
    write(OUT/'training_plan.json',plan)
    write(OUT/'freeze_receipt.json',dict(plan_sha256=sha(OUT/'training_plan.json'),new_fits=0,terminal_label_records=0))
    print({s:v['primary'] for s,v in selected.items()})


def fit():
    from tools.retention_corrected2e_v13 import environment
    from tools.retention_shape_v4 import Encoder, estimator, expressed, weights

    plan=read(OUT/'training_plan.json')
    assert sha(OUT/'training_plan.json')==read(OUT/'freeze_receipt.json')['plan_sha256']
    assert all(sha(ROOT/p)==h for p,h in plan['protected'].items()) and environment()==plan['environment']
    assert not (OUT/'predictions_locked.json').exists()
    data=read(P14/'input_snapshot.json'); inputs=read(OUT/'locked_early_inputs.json')['systems']
    with (OUT/'fit_claim.json').open('x',encoding='utf8') as stream:
        json.dump(dict(started_at=now(),plan_sha256=sha(OUT/'training_plan.json')),stream)
    outcomes={}
    for s,d in data.items():
        train=d['endpoints']; assert all(r['source_family']!=SOURCE_ID for r in train)
        f=inputs[s]['windows']['0.2']['features']; last=f['last_early_retention_pct']
        test=dict(features=f,static_features=inputs[s]['static_features'],source_family=SOURCE_ID,last_early=last)
        w=weights(train);delta=np.array([r['target']-r['last_early'] for r in train])
        center=float(np.average(delta,weights=w));scale=float(np.sqrt(np.average((delta-center)**2,weights=w))) or 1.
        estimates=[]
        for config in plan['configurations']:
            event=dict(config_id=config['id'],family=config['family'])
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter('always')
                try:
                    tr=[expressed(r,config,'six') for r in train]
                    encoder=Encoder().fit(tr);x=encoder.transform(tr);xt=encoder.transform([expressed(test,config,'six')])
                    model=estimator(config);mass=w*len(train)
                    kwargs={'sample_weight':mass}
                    if config['kind']=='GPR':model.set_params(alpha=config['parameters']['alpha']/mass);kwargs={}
                    model.fit(x,(delta-center)/scale,**kwargs)
                    prediction=float(model.predict(xt)[0]*scale+center+last);assert np.isfinite(prediction)
                    event.update(status='complete',predicted_retention_pct=prediction,encoder=encoder.schema)
                except Exception as error:
                    event.update(status='failed',error=repr(error))
            event['warnings']=[str(v.message) for v in caught];estimates.append(event)
        baseline=dict(training_mean=float(np.average([r['target'] for r in train],weights=w)),early_persistence=last,
                      early_linear=last+f['early_retention_slope_per_1000_cycles']*(f['target_cycle_count']-f['early_observed_cycle_count'])/1000)
        outcomes[s]=dict(training_rows=len(train),training_sources=len({r['source_family'] for r in train}),
                         train_row_ids=[r['row_id'] for r in train],primary=plan['selected'][s]['primary'],predictions=estimates,baselines=baseline)
    attempts=[v for o in outcomes.values() for v in o['predictions']]
    assert len(attempts)==plan['planned_fits']
    result=dict(status='predictions_locked_before_author_endpoint_access',frozen_at=now(),source=SOURCE_ID,
                plan_sha256=sha(OUT/'training_plan.json'),input_sha256=sha(OUT/'locked_early_inputs.json'),
                fits=len(attempts),failures=sum(e['status']=='failed' for e in attempts),warnings=sum(len(e['warnings']) for e in attempts),
                terminal_labels_entered=0,results=outcomes)
    write(OUT/'predictions_locked.json',result)
    print(f"Locked {len(attempts)} fits. Failures: {result['failures']}.")


if __name__=='__main__':
    {'refine':refine,'freeze':freeze,'fit':fit}[sys.argv[1]]()
