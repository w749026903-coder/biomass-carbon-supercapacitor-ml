"""Add two verified, already-exposed 3E sources to a bounded development trial."""
from collections import defaultdict
from pathlib import Path
import json
import math
import re
import sys
import warnings

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.retention_suaeda_case_v16 import BASE, P14, OUT as P16, feature_row
from tools.prepare_small_sample_routes import read, write, sha, now

OUT = BASE/'第十七轮_三电极衰减尾部开发_20261104'
CGBC_DOI = 'doi:10.1016/j.solidstatesciences.2025.108046'
SUAEDA_DOI = 'doi:10.3390/nano16211412'
CGBC_PDF = ROOT/'三电极端点扩充_20261018/corpus/B_R042/main.pdf'
NPCA_PDF = ROOT/'三电极端点扩充_20261018/corpus/B_R085/main.pdf'
PRIMARY = 'GPR_early_p1_continuation_delta'
BASELINES = ('training_mean','early_persistence','early_linear')


def native_image(doc, page, size):
    import pypdfium2 as pdf
    images=[obj for obj in doc[page-1].get_objects() if obj.type==pdf.raw.FPDF_PAGEOBJ_IMAGE]
    matches=[obj for obj in images if tuple(obj.get_px_size())==size]
    assert len(matches)==1
    return matches[0].get_bitmap().to_pil().convert('RGB')


def cgbc_evidence():
    from PIL import ImageDraw
    import pypdfium2 as pdf

    assert sha(CGBC_PDF)=='76621ae97c381191b3f27960bbae1d0216bb25c44ef39263d747f2fa7eb3affd'
    with pdf.PdfDocument(CGBC_PDF) as doc:
        method=' '.join(doc[1].get_textpage().get_text_range().split())
        end=' '.join(doc[8].get_textpage().get_text_range().split())
        assert 'three-electrode electrochemical system' in method and 'saturated calomel electrode' in method
        assert re.search(r'64\.8\s*%\s*for CGBC',end) and '1000 cycles at 1 A/g' in end
        image=native_image(doc,9,(1654,589))
    pixels=np.asarray(image).astype(np.int16); r,g,b=np.moveaxis(pixels,2,0)
    red=(r>100)&(r-g>55)&(r-b>55)
    x0,xN,y0,y100=155.5,673.5,504.,50.
    cycle_scale=1000/(xN-x0); y_scale=100/(y0-y100)
    markers=[]
    for x,y in [(156,50),(169,26),(182,52),(208,95),(221,113),(233,125),(246,135),(259,144),(673,210)]:
        count=int(red[y-7:y+8,x-7:x+8].sum());assert count>=215
        cycle=(x-x0)*cycle_scale; value=(y0-y)*y_scale
        markers.append(dict(x=x,y=y,red_pixels_in_15px_square=count,cycle_reading=cycle,early_ordinate_pct=value,
                            cycle_interval=[max(0.,cycle-4*cycle_scale),cycle+4*cycle_scale],
                            ordinate_interval_pp=[value-4*y_scale,value+4*y_scale]))
    end=markers[-1];assert end['ordinate_interval_pp'][0]<=64.8<=end['ordinate_interval_pp'][1]
    assert end['cycle_interval'][0]<=1000<=end['cycle_interval'][1]
    windows={}
    for frac,n in ((.1,3),(.2,7)):
        feat,count=feature_row(markers,1000,frac);assert count==n
        windows[str(frac)]=dict(features=feat,points=count)
    evidence=image.crop((0,0,816,589)); draw=ImageDraw.Draw(evidence)
    for marker in markers:
        x,y=marker['x'],marker['y'];draw.ellipse((x-9,y-9,x+9,y+9),outline='black',width=1)
    draw.rectangle((187,70,204,87),outline='black',width=2)
    path=OUT/'CGBC_Fig11a_红色保持率复核.png';evidence.save(path)
    return dict(source_family=CGBC_DOI,author_retention_pct=64.8,target_cycle_count=1000,system='3E',
                author_locator='p.8 results, p.9 Fig.11(a) and conclusion. Red squares/left axis retention; blue squares/right axis CE.',
                pdf=CGBC_PDF.relative_to(ROOT).as_posix(),pdf_sha256=sha(CGBC_PDF),windows=windows,markers=markers,
                image=path.name,image_sha256=sha(path),graph_endpoint=end,
                withheld_marker='The red square near x=195 is partially covered by blue CE. Its lower band is visible; no centre assigned.',
                calibration=dict(x0=x0,xN=xN,y0=y0,y100=y100,bound_px=4),
                static_features=dict(reported_current_A_g=1.,electrolyte='KOH',concentration_mol_L=1.,reference_electrode='SCE',
                                     BET_m2_g=None,cycle_voltage_lower_V=None,cycle_voltage_upper_V=None),
                current_mass_basis='not verified',scope='Own coffee-grounds carbon control. Ni(OH)2 composite 55.9% is a separate sample and outside this trial.')


def screen_npca():
    import pypdfium2 as pdf

    with pdf.PdfDocument(NPCA_PDF) as doc:
        t=' '.join(doc[9].get_textpage().get_text_range().split())
        assert re.search(r'approximately\s+80\s*%\s+of its initial capacity',t)
        image=native_image(doc,9,(1909,1496))
    raw=np.asarray(image).astype(np.int16);r,g,b=np.moveaxis(raw,2,0)
    blue=(b>90)&(b-r>35)&(b-g>30)
    per_column=[np.flatnonzero(blue[1235:1285,x])+1235 for x in range(1790,1816)]
    assert all(len(v)>0 for v in per_column)
    top=min(int(v.min()) for v in per_column);bottom=max(int(v.max()) for v in per_column)
    y0,y100=1419.5,1214.5
    value=lambda y:100*(y0-y)/(y0-y100)
    p=OUT/'NPCA_Fig7i_轴与终点.png';image.crop((1215,995,1909,1496)).save(p)
    return dict(status='held_author_approximation_vs_plot',pdf=NPCA_PDF.relative_to(ROOT).as_posix(),pdf_sha256=sha(NPCA_PDF),
                author_text_approx_pct=80.,graph_blue_center_pct=value((top+bottom)/2),graph_blue_band_pct=[value(bottom),value(top)],
                graph_blue_pixel_band=[top,bottom],image=p.name,image_sha256=sha(p),author_locator='p.10 and p.9 Fig.7i',
                note='No exact 80% label. The trace is blue retention, not red CE. The text approximation and native blue pixel band remain separate.')


def screen():
    assert not OUT.exists()
    case=read(P16/'external_case_results.json')
    assert case['locked_prediction_sha256']==sha(P16/'predictions_locked.json')
    assert case['systems']['3E']['author_retention_pct']==55. and case['systems']['3E']['author_rounding_compatible']
    OUT.mkdir()
    cgbc=cgbc_evidence(); npca=screen_npca()
    write(OUT/'source_decisions.json',dict(
          CGBC=cgbc,NPCA=npca,JPC=dict(author_retention_pct=55.,role='exposed_case_retired_into_development_only',
          prior_case_sha256=sha(P16/'external_case_results.json'),prior_prediction_preserved=True),
          LCNC3=dict(status='held_sample_identity_conflict',body_label='LCNC-3',fig10d_caption='LCNC-1',author_value_pct=78.1,
                     original='新增文献整理_20261020/originals/ADD_059.pdf'),
          WHAC=dict(status='held_insufficient_early_markers_and_current_unverified',author_value_pct=67.03,cycle_count=3000,
                    early_visible_positions_max=2,source='https://pmc.ncbi.nlm.nih.gov/articles/PMC11242469/',
                    original_image='同体系文献补充_第二批_20261017/定向扩搜40至60篇_20261017/sources/OA050/figures/materials-17-03233-g008.jpg'),
          OPC=dict(status='held_insufficient_early_markers',author_value_pct=76.7,previous_early20_count=2),
          H_LWCA=dict(status='held_published_version_not_verified',preprint_body_pct=81.3,preprint_graph_printed_pct=81.37),
          LC67=dict(status='deferred_mixed_precursor_scope_review',author_value_pct=76.16,ethanol_lignin_to_PAN='2:1 before carbonization'),
          outer_validation='Development source holdout only. Two new developer sources, zero accepted external sources. The original P16 prediction remains sealed history.'))
    print('Verified CGBC 3/7 points and kept NPCA, WHAC, OPC, LCNC3, H-LWCA and LC67 decisions separate.')


def freeze():
    from tools.retention_corrected2e_v13 import environment

    assert not (OUT/'training_plan.json').exists()
    p14=read(P14/'training_plan.json');assert environment()==p14['environment']
    old=read(P14/'input_snapshot.json')['3E']['endpoints'];assert len(old)==30 and len({r['source_family'] for r in old})==24
    decisions=read(OUT/'source_decisions.json'); cgbc=decisions['CGBC']
    assert sha(OUT/cgbc['image'])==cgbc['image_sha256'] and sha(CGBC_PDF)==cgbc['pdf_sha256']
    assert sha(P16/'external_case_results.json')==decisions['JPC']['prior_case_sha256']
    jpc=read(P16/'locked_early_inputs.json')['systems']['3E'];assert jpc['windows']['0.2']['marker_count']==14
    assert len({CGBC_DOI,SUAEDA_DOI}&{r['source_family'] for r in old})==0
    additions=[]
    for source,sample,row_id,target,features,statics in [
        (CGBC_DOI,'CGBC','legacy:R042_CY01::early20',64.8,cgbc['windows']['0.2']['features'],cgbc['static_features']),
        (SUAEDA_DOI,'JPC-800-0.5','retired_case:JPC-800-0.5_3E::early20',55.,jpc['windows']['0.2']['features'],jpc['static_features'])]:
        additions.append(dict(row_id=row_id,endpoint_id=row_id.removesuffix('::early20'),curve_id=row_id.removesuffix('::early20'),
                              material_key=source+'::'+sample,sample_name=sample,source_family=source,target=target,
                              last_early=features['last_early_retention_pct'],features=features,static_features=statics,role='development_only'))
    write(OUT/'input_snapshot.json',dict(system='3E',fraction=.2,rows=old+additions,original_row_count=len(old),additions=additions))
    inputs=[Path(__file__),CGBC_PDF,NPCA_PDF,P14/'training_plan.json',P14/'input_snapshot.json',P14/'results.json',
            P14/'heldout_predictions.json',P16/'locked_early_inputs.json',P16/'external_case_results.json',
            P16/'predictions_locked.json',OUT/'input_snapshot.json',OUT/'source_decisions.json',
            ROOT/'data/current_retention_research.json',ROOT/'data/current_training_latest.json',BASE/'research_goal.json',
            ROOT/'tools/retention_shape_v4.py',ROOT/'tools/run_small_sample_routes.py',ROOT/'tools/retention_v3_optimizer.py']
    plan=dict(frozen_at=now(),protected={p.relative_to(ROOT).as_posix():sha(p) for p in inputs},
              scope='Fixed family replication on 3E, 20% early window. Whole source leave-one-out across 32 rows from 26 families.',
              configurations=p14['configurations'],primary=PRIMARY,planned_fits=208,environment=environment(),
              baselines=BASELINES,criteria=read(BASE/'research_goal.json')['criteria'],
              old_match='Use exact P14 fixed-model predictions on identical 30 author endpoints. New and old models share configs and fold-level weighting. Compare on these common endpoints only.',
              weight_rule=p14['gpr_rule'],external_sources=0,static_unknowns='Maintain B optional feature handling and strict A admission; no imputed source metadata in evidence.',
              no_selection='Do not rank on the new outer results to replace the primary. All eight families and difficult sources stay visible.')
    write(OUT/'training_plan.json',plan)
    write(OUT/'freeze_receipt.json',dict(plan_sha256=sha(OUT/'training_plan.json'),fits_at_freeze=0))


def run():
    from tools.retention_corrected2e_v13 import environment
    from tools.retention_shape_v4 import Encoder, estimator, expressed, metrics, predicted, weights
    from tools.verify_retention_v3b import score

    plan=read(OUT/'training_plan.json');assert sha(OUT/'training_plan.json')==read(OUT/'freeze_receipt.json')['plan_sha256']
    assert environment()==plan['environment'] and all(sha(ROOT/p)==h for p,h in plan['protected'].items())
    data=read(OUT/'input_snapshot.json'); rows=data['rows']; sources=sorted({r['source_family'] for r in rows});assert len(sources)==26
    with (OUT/'run_claim.json').open('x',encoding='utf8') as f:json.dump(dict(plan_sha256=sha(OUT/'training_plan.json'),started_at=now()),f)
    events=[]; heldout=defaultdict(list); baselines=defaultdict(list)
    for source in sources:
        train=[r for r in rows if r['source_family']!=source];test=[r for r in rows if r['source_family']==source]
        assert not {r['curve_id'] for r in train}&{r['curve_id'] for r in test}
        w=weights(train);d=np.array([r['target']-r['last_early'] for r in train]);mean=float(np.average(d,weights=w));sd=float(np.sqrt(np.average((d-mean)**2,weights=w))) or 1.
        avg=float(np.average([r['target'] for r in train],weights=w))
        for r in test:
            f=r['features'];last=r['last_early'];linear=last+f['early_retention_slope_per_1000_cycles']*(f['target_cycle_count']-f['early_observed_cycle_count'])/1000
            for name,z in zip(BASELINES,(avg,last,linear)):baselines[name].append(predicted('3E',name,r,z))
        for c in plan['configurations']:
            cid=c['id'];event=dict(index=len(events)+1,outer_source=source,config_id=cid,
                train_ids=[r['row_id'] for r in train],test_ids=[r['row_id'] for r in test])
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter('always')
                try:
                    tr=[expressed(r,c,'six') for r in train];te=[expressed(r,c,'six') for r in test]
                    enc=Encoder().fit(tr); x=enc.transform(tr);xt=enc.transform(te);m=estimator(c)
                    mass=w*len(train);kw={'sample_weight':mass}
                    if c['kind']=='GPR':m.set_params(alpha=c['parameters']['alpha']/mass);kw={}
                    m.fit(x,(d-mean)/sd,**kw);y=m.predict(xt)*sd+mean+np.array([r['last_early'] for r in test]);assert len(y)==len(test) and np.isfinite(y).all()
                    event.update(status='complete',predictions=y.tolist(),target_center=mean,target_scale=sd,encoder=enc.schema)
                    heldout[cid].extend(predicted('3E',cid,r,z) for r,z in zip(test,y))
                except Exception as e:event.update(status='failed',error=repr(e))
            event['warnings']=[str(v.message) for v in caught];events.append(event)
    assert len(events)==plan['planned_fits']
    write(OUT/'fit_events.json',events)
    write(OUT/'heldout_predictions.json',{**heldout,**baselines})
    old=defaultdict(list); original={r['row_id']:r['target'] for r in rows[:data['original_row_count']]}
    for p in read(P14/'heldout_predictions.json'):
        if p['route']=='3E' and p['arm']=='author_only' and p['method'] in {c['id'] for c in plan['configurations']}:old[p['method']].append(p)
    checks=0;results={};c=plan['criteria'];base={b:score(p) for b,p in baselines.items()}
    for cid,pp in heldout.items():
        assert {p['row_id']:p['observed'] for p in old[cid]}==original
        matched=[p for p in pp if p['row_id'] in original]
        assert all(p['observed']==original[p['row_id']] for p in matched)
        m=metrics(pp);s=score(pp)
        for k,z in s.items():assert math.isclose(m[k],z,abs_tol=1e-9,rel_tol=1e-9);checks+=1
        reduce={b:1-s['mae']/v['mae'] for b,v in base.items()}
        gates=dict(coverage=len(pp)==len(rows) and len({p['row_id'] for p in pp})==len(rows),positive=all(p['predicted']>0 for p in pp),
                   r2=s['r2']>c['r2_gt'],mae=s['mae']<=c['mae_pp_max'],rmse=s['rmse']<=c['rmse_pp_max'],mape=s['mape_pct']<=c['mape_pct_max'],
                   p90ape=s['p90_ape_pct']<=c['p90_ape_pct_max'],p90abs=s['p90_absolute_error']<=c['p90_abs_pp_max'],
                   tail=s['source_p90_mae']<=c['source_p90_mae_pp_max'],baselines=all(v>=c['mae_reduction_vs_each_baseline_min'] for v in reduce.values()))
        results[cid]=dict(full=s,gates=gates,mae_reduction=reduce,numeric_pass=all(gates.values()),old_common=score(old[cid]),
                          new_common=score(matched) if matched else None,added_source_cases=[p for p in pp if p['source_family'] in (CGBC_DOI,SUAEDA_DOI)])
    for e in events:
        src=e['outer_source'];assert e['train_ids']==[r['row_id'] for r in rows if r['source_family']!=src]
        assert e['test_ids']==[r['row_id'] for r in rows if r['source_family']==src];checks+=2
    assert all(sha(ROOT/p)==h for p,h in plan['protected'].items())
    result=dict(status='complete_development_trial',fits=len(events),checks=checks,
                failures=sum(e['status']=='failed' for e in events),warnings=sum(len(e['warnings']) for e in events),
                old_rows=30,old_sources=24,expanded_rows=len(rows),expanded_sources=len(sources),primary=PRIMARY,results=results,
                baselines=base,numeric_passes=sum(v['numeric_pass'] for v in results.values()),external_sources_accepted=0,goal_achieved=False)
    write(OUT/'results.json',result);print(json.dumps(result['results'][PRIMARY],ensure_ascii=False))


if __name__=='__main__':
    {'screen':screen,'freeze':freeze,'run':run}[sys.argv[1]]()
