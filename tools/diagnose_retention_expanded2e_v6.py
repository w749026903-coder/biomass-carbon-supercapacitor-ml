"""Posthoc source diagnostics and no-fit full-curve supervision inventory.

No target, window, model, or existing admission is changed. Candidate intermediate
labels are an inventory of existing digitized positions, not new experiments.
"""
from pathlib import Path
import json,collections,math,sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'保持率达标研究_v3_主线与近优组合_20261030';OUT=BASE/'第十二轮_扩充双电极来源验证'
def read(p):return json.loads(Path(p).read_text('utf8'))
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n','utf8')
def score(pred):
    count=collections.Counter(p['source_family']for p in pred);w=np.array([1/(len(count)*count[p['source_family']])for p in pred]);y=np.array([p['observed']for p in pred]);z=np.array([p['predicted']for p in pred]);mae=float(sum(w*abs(y-z)));mse=float(sum(w*(y-z)**2));den=float(sum(w*(y-sum(w*y))**2));return dict(rows=len(pred),sources=len(count),mae=mae,rmse=math.sqrt(mse),r2=1-mse/den)
def main():
    assert read(OUT/'independent_verification.json')['status']=='passed'
    data=read(OUT/'input_snapshot.json');pred=read(OUT/'heldout_predictions.json');res=read(OUT/'results.json');curves=read(ROOT/read(OUT/'training_plan.json')['curve_dataset']);ci={q['curve_id']:q for q in curves};diagnostic={}
    for route,rows in data.items():
        G=len({r['source_family']for r in rows});ps=[p for p in pred if p['route']==route and p['model']=='six_oneSE_family_mean'];index={p['row_id']:p for p in ps};m=next(m for m in res['metrics']if m['route']==route and m['model']=='six_oneSE_family_mean');sources=[]
        for source in sorted({r['source_family']for r in rows}):
            rr=[r for r in rows if r['source_family']==source];ss=[index[r['row_id']]for r in rr];mae=sum(abs(p['observed']-p['predicted'])for p in ss)/len(ss);train=[r for r in rows if r['source_family']!=source];maxtrain=max(r['features']['target_cycle_count']for r in train);testmax=max(r['features']['target_cycle_count']for r in rr);ely={r['static_features']['electrolyte']for r in train}
            sources.append(dict(source=source,rows=len(rr),equal_total_evaluation_weight=1/G,MAE_pp=mae,contribution_to_overall_MAE_pp=mae/G,share_of_total_absolute_error=mae/G/m['mae'],held_max_cycle_count=testmax,training_max_cycle_count=maxtrain,beyond_all_training_horizons=testmax>maxtrain,held_electrolytes=sorted({r['static_features']['electrolyte']for r in rr}),unknown_electrolytes=sorted({r['static_features']['electrolyte']for r in rr}-ely),records=[dict(row_id=r['row_id'],sample=r['sample_name'],target=r['target'],prediction=index[r['row_id']]['predicted'],last_early=r['last_early'],required_future_change_pp=r['target']-r['last_early'],predicted_future_change_pp=index[r['row_id']]['predicted']-r['last_early'],cycle_count=r['features']['target_cycle_count'],early_point_count=len(r['early_points']),maximum_feature_reading_bound_pp=r['reading_bound_pp'],figure_path=ci[r['curve_id']]['figure_path'])for r in rr]))
        sources.sort(key=lambda r:-r['MAE_pp']);selections=[s for s in read(OUT/'nested_selection.json')if s['route']==route];counts=collections.Counter(f for s in selections for f in s['views']['six']['eligible_oneSE_families']);diagnostic[route]=dict(source_count=G,max_single_source_weight=1/G,largest_error_source_share=sources[0]['share_of_total_absolute_error'],top5_error_source_share=sum(s['share_of_total_absolute_error']for s in sources[:5]),sources=sources,primary_eligible_family_outer_counts=dict(counts),primary_MAE_change_vs_persistence=1-m['mae']/next(z for z in res['metrics']if z['route']==route and z['model']=='early_persistence')['mae'])
    # A descriptive paired subset; trained cohorts still differ, so this is not
    # an isolated or causal estimate of increasing the observation window.
    def baseid(p):return p['row_id'].split('::early')[0]
    a=[p for p in pred if p['route']=='B_2E_early20'and p['model']=='six_oneSE_family_mean'];b=[p for p in pred if p['route']=='B_2E_early10'and p['model']=='six_oneSE_family_mean'];common={baseid(p)for p in a}&{baseid(p)for p in b};matched=dict(early20=score([p for p in a if baseid(p)in common]),early10=score([p for p in b if baseid(p)in common]),interpretation='Descriptive matched endpoint comparison only. Different training cohorts and source fold compositions; not a causal window-length effect. No row deleted from any acceptance result.')
    write(OUT/'posthoc_diagnostics.json',dict(status='complete_no_new_fits',routes=diagnostic,matched_endpoints=matched,interpretation='Source coverage, early/late trajectory patterns and prior shrinkage are diagnostic hypotheses, not proof of a unique cause. Independent verifier checks implementation and provenance, not scientific sufficiency. All difficult sources retained.'))
    # Count actual intermediate target positions with strictly earlier approved
    # window observations. Position-only log-time selection, never label-based.
    inventory=[]
    for system in['2E','3E']:
        for f in[.2,.1]:
            qq=[q for q in curves if q['system']==system and q['training_eligible_pending_visual_review']];items=[]
            for q in qq:
                pts=q['points'];candidates=[]
                for point in pts:
                    N=point['cycle_coordinate']
                    if N<=0 or point['cycle_upper']>=q['target_cycle_count']:continue
                    early=[p for p in pts if p['cycle_upper']<=f*N]
                    if len(early)>=3:candidates.append((point,early))
                if not candidates:continue
                grid=np.exp(np.linspace(math.log(candidates[0][0]['cycle_coordinate']),math.log(candidates[-1][0]['cycle_coordinate']),min(16,len(candidates))));chosen=sorted({min(range(len(candidates)),key=lambda j:(abs(math.log(candidates[j][0]['cycle_coordinate'])-math.log(v)),j))for v in grid});selected=[candidates[i]for i in chosen]
                items.append(dict(curve_id=q['curve_id'],endpoint_id=q['endpoint_id'],source_family=q['source_family'],author_endpoint_N=q['target_cycle_count'],all_existing_digitized_targets=len(candidates),position_only_selected_targets=len(selected),minimum_target_cycle=min(p['cycle_coordinate']for p,e in selected),maximum_target_cycle=max(p['cycle_coordinate']for p,e in selected),label_kind='existing_digitized_retention_with_reading_box_not_author_reported_exact_value',selected_points=[dict(marker_index=p['marker_index'],cycle_coordinate=p['cycle_coordinate'],cycle_lower=p['cycle_lower'],cycle_upper=p['cycle_upper'],retention_reading_pct=p['retention_pct'],reading_interval_pp=p['reading_interval_pp'],early_marker_indices=[v['marker_index']for v in e])for p,e in selected]))
            inventory.append(dict(system=system,fraction=f,curves=len(items),source_families=len({q['source_family']for q in items}),all_existing_digitized_targets=sum(q['all_existing_digitized_targets']for q in items),selected_targets_at_most16_each=sum(q['position_only_selected_targets']for q in items),curves_detail=items))
    write(OUT/'curve_supervision_feasibility.json',dict(status='no_fit_inventory_only_not_training_admission',input_measurements_changed=False,observation_windows_changed=False,author_labels_changed=False,additional_independent_sources=0,new_model_fits=0,selection='Existing actual digitized target positions;>=3actual early positions within0.1/0.2times each candidateN; exclude points whose cycle box reaches author endpoint; cap16 percurve by position-only log-time grid. Preserve author endpoint separately; no interpolation or synthetic values.',future_requirements=['Whole source/curve isolation in every inner/outer fold, including all new targets.','Equal source and per-curve weighting so dense traces are not independent experiments.','Reading intervals and shared-reference uncertainty must remain labelled; no exact author target impersonation.','No intermediate target from an outer held source may enter training.','Freeze a new finite plan before any score;keep current failed study unchanged.','Original author endpoints remain the main heldout acceptance task; added positions are training supervision only.'],inventory=inventory))
    print('Posthoc diagnostics,0 new fits.')
    for r,v in diagnostic.items():print(r,'largestsource absoluteerror share',round(v['largest_error_source_share'],4),'top5',round(v['top5_error_source_share'],4),'vs persistence',round(v['primary_MAE_change_vs_persistence'],4))
    print('Matched endpoints',matched)
    for x in inventory:print('Curve supervision inventory',x['system'],x['fraction'],'curves',x['curves'],'sources',x['source_families'],'alltargets',x['all_existing_digitized_targets'],'cap16actualtargets',x['selected_targets_at_most16_each'])
if __name__=='__main__':main()
