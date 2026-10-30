"""Freeze the expanded-source 2E study before any new fit or score is seen."""
from pathlib import Path
import hashlib,json,sys,platform
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.retention_shape_v4 import SIX,FIELDS,shape_summaries,load_windows,read,write,sha,now
BASE=ROOT/'保持率达标研究_v3_主线与近优组合_20261030';OUT=BASE/'第十二轮_扩充双电极来源验证';BATCH=BASE/'第十一轮_双电极原文曲线补充/batch4_20261031'

def main():
    assert not OUT.exists(),'Never replace a frozen round'
    audit=read(BATCH/'independent_verification.json');assert audit['status']=='passed'and audit['checks']==781
    ptr=read(ROOT/'data/current_retention_research.json');assert ptr['sha256']==audit['sqlite_sha256']
    data={};counts={};splits={}
    for fraction in[.2,.1]:
        route=f'B_2E_early{int(fraction*100)}';rows=[]
        for r in load_windows('2E',fraction,include_shape=True):
            q=dict(row_id=r['endpoint_id']+'::early'+str(int(100*fraction)),endpoint_id=r['endpoint_id'],source_family=r['source_family'],curve_id=r['curve_id'],material_key=r['source_family']+'::'+r['sample_name'],sample_name=r['sample_name'],system='2E',target=r['target_retention_pct'],features={k:r[k]for k in SIX},static_features=r['static_features'],last_early=r['last_early_retention_pct'],linear_forecast=r['last_early_retention_pct']+r['early_retention_slope_per_1000_cycles']*(r['target_cycle_count']-r['early_observed_cycle_count'])/1000,fraction=fraction,point_indices=r['point_indices'],early_points=r['early_points'],reading_bound_pp=r['maximum_reading_bound_pp'],shape_features=r['shape_features'])
            assert q['shape_features']==shape_summaries(q['early_points'])and len(q['early_points'])>=3;rows.append(q)
        sources=sorted({r['source_family']for r in rows});good=[r for r in rows if r['shape_features'][FIELDS[0]]is not None];data[route]=rows;counts[route]=dict(rows=len(rows),sources=len(sources),shape_computable_rows=len(good),shape_computable_sources=len({r['source_family']for r in good}));splits[route]=[]
        for held in sources:
            rest=sorted([s for s in sources if s!=held],key=lambda s:hashlib.sha256(s.encode('utf8')).hexdigest());folds=[rest[k::4]for k in range(4)];assert all(folds);splits[route].append(dict(outer_source=held,inner_held_sources=folds))
    assert [(counts[k]['rows'],counts[k]['sources'])for k in data]==[(27,22),(23,18)]
    cfg=read(BASE/'第九轮_同窗口形状对照/candidate_configurations.json');assert len(cfg)==16
    OUT.mkdir();write(OUT/'input_snapshot.json',data);write(OUT/'candidate_configurations.json',cfg)
    protected=read(BATCH/'source_protection.json')['files'];protected=dict(protected)
    for rel in ['data/current_retention_research.json','data/retention_research.py','data/retention_shape.py','tools/prepare_retention_expanded2e_v6.py','tools/retention_expanded2e_v6.py','tools/verify_retention_expanded2e_v6.py','tools/retention_shape_v4.py','tools/retention_v3_optimizer.py','tools/run_small_sample_routes.py','tools/verify_retention_v3b.py','tools/verify_retention_shape_v4.py']:
        protected[rel]=sha(ROOT/rel)
    for name in ['cycling_research_v3g.sqlite','curve_dataset_v3g.json','independent_verification.json','five_case_followup.json']:
        p=BATCH/name;protected[p.relative_to(ROOT).as_posix()]=sha(p)
    for module in list(sys.modules.values()):
        path=getattr(module,'__file__',None)
        if path:
            p=Path(path).resolve()
            if p.is_file()and p.is_relative_to(ROOT)and p.suffix=='.py'and'.venv'not in p.parts:protected[p.relative_to(ROOT).as_posix()]=sha(p)
    write(OUT/'source_protection.json',protected)
    import sklearn,xgboost,numpy,scipy
    write(OUT/'environment.json',dict(python=platform.python_version(),executable=sys.executable,sklearn=sklearn.__version__,xgboost=xgboost.__version__,numpy=numpy.__version__,scipy=scipy.__version__,global_environment_changes=False))
    total=sum(len(v)for v in splits.values())*len(cfg)*2*5;assert total==6400
    plan=dict(frozen_at=now(),runner_sha256=sha(ROOT/'tools/retention_expanded2e_v6.py'),verifier_sha256=sha(ROOT/'tools/verify_retention_expanded2e_v6.py'),input_sha256=sha(OUT/'input_snapshot.json'),candidate_sha256=sha(OUT/'candidate_configurations.json'),source_protection_sha256=sha(OUT/'source_protection.json'),database_pointer_at_freeze=ptr,curve_dataset=(BATCH/'curve_dataset_v3g.json').relative_to(ROOT).as_posix(),counts=counts,splits=splits,planned_new_fits=6400,planned_reused_control_fits=0,planned_new_ensemble_weight_fits=0,primary='six_oneSE_family_mean',paired_control='shape_oneSE_family_mean',views=['six','shape'],base_configurations_per_view=16,candidate_policy='Exact sixteen P9/P3 configurations retained in each view: RF/GPR/XGB early and static families, Ridge/ExtraTrees; no new score-selected grid. Every fit on the expanded2E cohorts is new; old7-source predictions are not interchangeable.',selection='Whole-source outerLOSO; inner4 deterministic hashed-source folds. Rank inner source-weightedMAE,RMSE,configID. For each six/shape/joint view, choose family representative, average those within winnerMAE+sampleSD(per-sourceMAE)/sqrt(G). Primary is predeclared six stable rule, not changed to highest outerR2. Per-family,near4 and joint secondary results retained.',criteria=read(BASE/'research_goal.json')['criteria'],baselines=['training_mean','early_persistence','early_linear'],generalization=read(BASE/'research_goal.json')['generalization'],input_scope='Existing approved2E10%/20%,minimum3 actual positions; all27/23 rows retained. Four approved same-window shapes require3 actual points in each half; unsupported values remain missing and train-only encoder eligibility/imputation applies. Six original summaries and static prior eligible conditions only. Source/sample/DOI not predictors.',data_purpose='Expanded2E development-source study, not a new untouched external test;3E unchanged, do not refit old3E rounds merely to produce a new score. A direct route andP6/BP/P10 robust/hybrid histories remain live research alternatives, not rejected by absence from this fixed data-expansion comparison.',precision_limit='MMC own-first reference and shared numerator/reference3px boxes retained; author95.6 matches rounding interval only. Ordinate boxes are not confidence intervals; numeric pass alone cannot prove precision or scientific completeness.',immutable_output='capacitance_retention_pct_at_declared_cycle_count_and_conditions',unchanged_labels=True,untouched_external_sources=0,no_failure_dropping='Every job, warning, failed fit and hard source retained; any incomplete prediction coverage fails acceptance.',stop='Exactly6400 new fits,0 old predictions reused,0 learned ensemble-weight fits. No candidate additions or hard-source deletions after seeing outer scores.',goal_status='active')
    write(OUT/'training_plan.json',plan);write(OUT/'progress.json',dict(status='frozen_not_started',new_fits=0,planned_new_fits=6400,goal_status='active'))
    print(json.dumps(dict(status='frozen_not_started',planned_new_fits=6400,counts=counts,primary=plan['primary'],new_external_sources=0),ensure_ascii=False,indent=2))
if __name__=='__main__':main()
