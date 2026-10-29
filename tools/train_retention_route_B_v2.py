"""One frozen source-held pass of early-window-assisted retention prediction."""
from pathlib import Path
import collections,json,math,sys,time
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.prepare_small_sample_routes import read,write,sha,now
import tools.run_small_sample_routes as engine
OUT=ROOT/'保持率双路线预研_v2_20261029';RUN=OUT/'B_早期实测辅助预测'
EARLY=['last_early_retention_pct','early_mean_retention_pct','early_retention_slope_per_1000_cycles','early_retention_range_pp','early_observed_cycle_count','target_cycle_count']
STATIC=['reported_current_A_g','electrolyte','concentration_mol_L','cycle_voltage_lower_V','cycle_voltage_upper_V','BET_m2_g']
CANDIDATES=[('ridge_early_residual','ridge',False),('RF_early_residual','random_forest',False),('XGB_early_residual','xgboost',False),('GPR_early_residual','fixed_Matern_GPR',False),('ridge_static_residual','ridge',True),('RF_static_residual','random_forest',True)]

def make_row(q,f):
 points=[p for p in q['points']if p['cycle_upper']<=f*q['target_cycle_count']]
 if len(points)<3:return None
 x=np.array([p['cycle_coordinate']for p in points]);y=np.array([p['retention_pct']for p in points]);xc=x-x.mean();slope=float(np.dot(xc,y-y.mean())/np.dot(xc,xc))
 features=dict(zip(EARLY,[float(y[-1]),float(y.mean()),slope*1000,float(np.ptp(y)),float(x[-1]),q['target_cycle_count']]))
 fields=STATIC+(['reference_electrode']if q['system']=='3E'else[])
 return dict(row_id=q['endpoint_id']+f'::early{int(f*100)}',endpoint_id=q['endpoint_id'],curve_id=q['curve_id'],material_key=q['source_family']+'::'+q['sample_name'],sample_name=q['sample_name'],source_family=q['source_family'],system=q['system'],target=q['author_retention_pct'],features=features,static_features={k:q['features'].get(k)for k in fields},fraction=f,point_indices=[p['marker_index']for p in points],early_points=points,figure_path=q['figure_path'],figure_sha256=q['figure_sha256'],maximum_reading_bound_pp=max(p['reading_bound_pp']for p in points),first_plotted_reference=q['first_plotted_reference'],last_early=float(y[-1]),linear_forecast=float(y[-1]+slope*(q['target_cycle_count']-x[-1])),normalization='Own first plotted marker only when graph reports absolute C; explicit retention axis otherwise. Never normalized by target endpoint.')

def paired_ci(a,b):
 assert [r['row_id']for r in a]==[r['row_id']for r in b]
 w=engine.weights(a);delta=np.array([abs(r['predicted']-r['observed'])-abs(s['predicted']-s['observed'])for r,s in zip(a,b)]);gs=sorted({r['source_family']for r in a});rng=np.random.default_rng(engine.SEED);vals=[]
 for _ in range(2000):
  counts=collections.Counter(rng.choice(gs,len(gs),replace=True));ww=w*np.array([counts.get(r['source_family'],0)for r in a]);vals.append(float(np.average(delta,weights=ww)))
 return dict(delta_mae_pp=float(np.average(delta,weights=w)),source_bootstrap_95pct=np.quantile(vals,[.025,.975]).tolist(),negative_means_better=True,exploratory=True)

def add(route,model,rows,values):
 if values is None:return
 for r,p in zip(rows,values):
  if not math.isfinite(p):continue
  engine.PREDS.append(dict(route=route,model=model,row_id=r['row_id'],endpoint_id=r['endpoint_id'],source_family=r['source_family'],material_key=r['material_key'],curve_id=r['curve_id'],sample_name=r['sample_name'],observed=r['target'],predicted=float(p),fraction=r['fraction'],system=r['system'],last_early=r['last_early'],early_point_indices=r['point_indices'],maximum_reading_bound_pp=r['maximum_reading_bound_pp']))

def main():
 assert not RUN.exists(),'Never replace or repeat a started experiment'
 curves=read(OUT/'reviewed_curve_data.json');data={}
 for system in ['2E','3E']:
  for f in [.1,.2]:
   rows=[make_row(q,f)for q in curves if q['system']==system and q['training_eligible_pending_visual_review']];rows=[r for r in rows if r]
   assert len({r['source_family']for r in rows})>=4
   data[f'B_{system}_early{int(100*f)}']=rows
 RUN.mkdir();write(RUN/'input_snapshot.json',data)
 protected={str(p.relative_to(ROOT)).replace('\\','/'):sha(p)for p in[OUT/'contract.json',OUT/'reviewed_curve_data.json',OUT/'curve_review_receipt.json',OUT/'curve_marker_candidates.json',OUT/'baseline_inputs.json',ROOT/'tools/run_small_sample_routes.py',Path(__file__)]}
 for q in curves:protected[q['figure_path']]=q['figure_sha256'];assert sha(ROOT/q['figure_path'])==q['figure_sha256']
 expected=sum(len({r['source_family']for r in rows})*len(CANDIDATES)for rows in data.values())
 plan=dict(frozen_at=now(),authorization='User selected both A/B with separate evaluation. B early10/20% of declared target cycle count is authorized.',output='author_reported_capacitance_retention_pct_at_declared_target_N',protected_sha256=protected,input_sha256=sha(RUN/'input_snapshot.json'),planned_fits=expected,primary_model='ridge_early_residual',primary_window_fraction=.2,other_window_fraction=.1,candidates=[dict(name=n,engine=k,verified_static_inputs=s)for n,k,s in CANDIDATES],parameters=read(ROOT/'小样本方向预研_20261029/training_plan.json')['model_parameters'],residual_target='Training rows encode exp((author_Rfinal-last_early_R)/10) for unchanged log-target engine; at prediction decode last_early_R+10*log(pred). Test encoded target is the constant1, so no query future value enters fitting.',input_fields=EARLY,optional_static_by_system={'2E':STATIC,'3E':STATIC+['reference_electrode']},minimum_early_points=3,cutoff='upper x-coordinate reading bound <= fraction * predeclared targetN',normalization='Explicit retention as printed; absolute-C curves use only own first plotted reference mark, whose cycle index remains unknown. No future endpoint normalization.',source_weighting='Equal family, then curve; every curve/window is one endpoint prediction, no pixel-level sample inflation. GPR fit is unweighted, all evaluations are source-balanced.',validation='Entire source family held out separately for each electrode/window; all samples of a family stay together. Fractions fit separately, never train10% and test20% of same curve.',baselines=['training_mean','early_persistence','early_linear_extrapolation'],criteria=dict(r2_gt=.95,mae_pp_max=2,rmse_pp_max=3,mape_pct_max=5,p90_ape_pct_max=10,p90_abs_pp_max=5,source_p90_mae_pp_max=5,mae_reduction_vs_each_baseline_min=.2,positive_predictions=True,complete_coverage=True),generalization='At least10 source families plus untouched later external sources needed before reliable-model claim; current pilot is exploratory regardless of numeric scores.',predeclared_sensitivity=['Re-evaluate the same held-out predictions on early-reading-bound<=2pp, no refit.','Compare10/20% on shared endpoint cohort only; full-cohort difference is not an observation-window effect.','Leave each held-out source out of aggregate metrics as a composition stress check, without refitting.'],exclusions='3 graph/text conflicts fixed before fitting; do not modify original labels. Large feature-reading bounds retained in primary and disclosed.',stop='Exactly this pass; no outcome-driven scope, hyperparameter or candidate additions.')
 write(RUN/'training_plan.json',plan)
 engine.RUN=RUN;engine.START=time.monotonic();engine.EVENTS=[];engine.PREDS=[];engine.FAILURES=[];engine.PLANNED=expected
 for route,rows in data.items():
  for source in sorted({r['source_family']for r in rows}):
   train=[r for r in rows if r['source_family']!=source];test=[r for r in rows if r['source_family']==source]
   for name,kind,static in CANDIDATES:
    def encoded(r,is_train):
     return dict(r,features=dict(r['features'],**(r['static_features']if static else{})),target=math.exp((r['target']-r['last_early'])/10)if is_train else 1.)
    p=engine.fit_predict(kind,[encoded(r,True)for r in train],[encoded(r,False)for r in test],route+'::'+name,source)
    add(route,name,test,None if p is None else[r['last_early']+10*math.log(v)for r,v in zip(test,p)])
   mean=float(np.average([r['target']for r in train],weights=engine.weights(train)))
   add(route,'training_mean',test,[mean]*len(test));add(route,'early_persistence',test,[r['last_early']for r in test]);add(route,'early_linear_extrapolation',test,[r['linear_forecast']for r in test])
 assert len(engine.EVENTS)==expected
 for p,h in protected.items():assert sha(ROOT/p)==h,p
 write(RUN/'heldout_predictions.json',engine.PREDS);groups=collections.defaultdict(list)
 for p in engine.PREDS:groups[(p['route'],p['model'])].append(p)
 scores=[]
 for (route,model),a in sorted(groups.items()):
  s=engine.metrics(a,True);base={k:groups[(route,k)]for k in plan['baselines']};s.update(route=route,model=model)
  s['mae_reduction_vs_baselines']={k:1-s['mae']/engine.metrics(b)['mae']for k,b in base.items()};s['paired_baseline_comparisons']={k:paired_ci(a,b)for k,b in base.items()}
  s['checks']=dict(r2=s['r2']is not None and s['r2']>.95,mae=s['mae']<=2,rmse=s['rmse']<=3,mape=s['mape_pct']<=5,p90_ape=s['p90_ape_pct']<=10,p90_abs=s['p90_absolute_error']<=5,source_tail=s['source_p90_mae']<=5,baseline=all(v>=.2 for v in s['mae_reduction_vs_baselines'].values()),positive=all(p['predicted']>0 for p in a),coverage=len(a)==len(data[route]))
  s['numeric_pass']=all(s['checks'].values());s['generalization_confirmed']=False;s['final_reliable']=False
  h=[p for p in a if p['maximum_reading_bound_pp']<=2];s['reading_bound_le2pp_sensitivity']=engine.metrics(h)if len(h)>=2 else None
  stress=[]
  for source in sorted({p['source_family']for p in a}):
   subset=[p for p in a if p['source_family']!=source];m=engine.metrics(subset);stress.append(dict(removed_source=source,rows=m['rows'],sources=m['sources'],mae=m['mae'],r2=m['r2']))
  s['composition_stress_no_refits']=stress;scores.append(s)
 shared=[]
 for system in ['2E','3E']:
  r10=f'B_{system}_early10';r20=f'B_{system}_early20';ids={r['endpoint_id']for r in data[r10]}&{r['endpoint_id']for r in data[r20]}
  for model in[name for name,_,_ in CANDIDATES]+plan['baselines']:
   for route in[r10,r20]:
    a=[p for p in groups[(route,model)]if p['endpoint_id']in ids];m=engine.metrics(a);shared.append(dict(route=route,model=model,shared_endpoint_ids=sorted(ids),**m))
 write(RUN/'results.json',dict(status='complete',completed_at=now(),fits=expected,failures=engine.FAILURES,metrics=scores,shared_cohort_window_comparison=shared,old_author_labels_changed=0,new_formal_admissions=0,no_untouched_external_test=True,final_reliable=False))
 write(RUN/'progress.json',dict(status='complete',completed_fits=expected,planned_fits=expected))
 for s in scores:
  if s['model']in['ridge_early_residual','early_persistence','early_linear_extrapolation','RF_early_residual']:print(s['route'],s['model'],'n/source',s['rows'],s['sources'],'R2',round(s['r2'],3),'MAE',round(s['mae'],3),'RMSE',round(s['rmse'],3),'pass',s['numeric_pass'])
if __name__=='__main__':main()
