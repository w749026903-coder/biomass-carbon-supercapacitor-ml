"""New user-steered phase: preserve all eight external inputs and retention output."""
from pathlib import Path
import collections, hashlib, json, sys, time
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import tools.run_small_sample_routes as engine
from tools.prepare_small_sample_routes import read,write,sha,now
BASE=ROOT/'小样本方向预研_20261029';RUN=BASE/'保持率固定输入输出'
FIELDS=['cycle_count','reported_current_A_g','electrolyte','concentration_mol_L','cycle_voltage_lower_V','cycle_voltage_upper_V','BET_m2_g','reference_electrode']
MODELS=['ridge','random_forest','xgboost','small_BP_MLP','fixed_Matern_GPR']

def main():
 assert not RUN.exists(),'New finite phase only; no overwrite or repeat'
 RUN.mkdir();data=read(BASE/'input_snapshot.json');rows=[]
 for old in data['retention']:
  r=dict(old,features={k:old['features'].get(k)for k in FIELDS})
  if r['features']['reference_electrode']is None:
   # The inventory projection retained the live full retention features.
   raise ValueError('Fixed external input missing')
  r['material_key']=r['material_key']or r['source_family']+'::'+r['sample_name'];rows.append(r)
 filters={
  'R1_KOH6_10000':lambda r:r['features']['electrolyte']=='KOH'and r['features']['concentration_mol_L']==6 and r['features']['cycle_count']==10000,
  'R2_KOH6_10000_j10':lambda r:r['features']['electrolyte']=='KOH'and r['features']['concentration_mol_L']==6 and r['features']['cycle_count']==10000 and r['features']['reported_current_A_g']==10,
  'R3_plant_residue_KOH6':lambda r:r['features']['electrolyte']=='KOH'and r['features']['concentration_mol_L']==6 and next(x for x in data['retention']if x['row_id']==r['row_id'])['features'].get('precursor_origin_class')=='plant_residue'}
 scopes={k:[r for r in rows if f(r)]for k,f in filters.items()};counts={k:dict(rows=len(v),sources=len({r['source_family']for r in v}))for k,v in scopes.items()}
 local=collections.Counter(r['source_family']for r in rows);localn=sum(n for n in local.values()if n>=4)
 expected=sum(v['sources']*len(MODELS)for v in counts.values())+34*3+localn*3
 plan=dict(frozen_at=now(),authorization='2026-10-29 follow-up explicitly fixes capacitance retention and original input/output; this new phase excludes early-cycle/history inputs and all capacitance/BET targets.',fixed_inputs=FIELDS,fixed_output='capacitance_retention_pct',scope_counts=counts,source_snapshot_sha256=sha(BASE/'input_snapshot.json'),runner_sha256=sha(Path(__file__)),engine_sha256=sha(ROOT/'tools/run_small_sample_routes.py'),goal_sha256=sha(ROOT/'docs/RETENTION_DIRECTION_GOAL.json'),models=MODELS,primary='random_forest',scope_filters='6M KOH+10000 cycles; same+j10; plant-residue metadata filter+6M KOH. All eight API inputs retained, class/DOI/sample never encoded.',routes=['R1/R2/R3: narrow-domain full source holdout','R4: 10000-normalized log-retention-rate target transformation over all47, using original N in reconstruction','R5: known source family leave one material out, only families with>=4 materials; one shared input schema, no identity predictor','R6: fixed equal RF+XGB and RF+GPR prediction blends on R1/R2/R3, no learned weights'],planned_fits=expected,max_fits=400,parameters=read(BASE/'training_plan.json')['model_parameters'],criteria=read(ROOT/'docs/RETENTION_DIRECTION_GOAL.json')['engineering_acceptance'],validation='Exploratory reused sources; no outcome-based added scope or hyperparameter search. R5 tests known families only, cannot pass unseen-family generalization gate.',stop='Exactly scheduled fits; failures kept, no further candidates after seeing results. No extra measured inputs, simulated labels, old plan reruns or data admission.')
 assert expected<=400;write(RUN/'training_plan.json',plan);write(RUN/'input_snapshot.json',dict(rows=rows,scopes={k:[r['row_id']for r in v]for k,v in scopes.items()}))
 engine.RUN=RUN;engine.START=time.monotonic();engine.EVENTS=[];engine.PREDS=[];engine.FAILURES=[];engine.PLANNED=expected
 for route,rs in scopes.items():engine.source_cv(route,rs,MODELS)
 # A per-cycle rate target uses no new external information: ln(R/100)*10000/N.
 rate=[]
 for r in rows:
  n=r['features']['cycle_count'];rate.append(dict(r,target=float(np.exp(np.log(r['target']/100)*10000/n))))
 for g in sorted({r['source_family']for r in rate}):
  train=[r for r in rate if r['source_family']!=g];test=[r for r in rate if r['source_family']==g]
  for kind in ['ridge','random_forest','xgboost']:
   p=engine.fit_predict(kind,train,test,'R4_per_cycle_rate',g)
   orig=[next(r for r in rows if r['row_id']==q['row_id'])for q in test]
   restored=None if p is None else[float(100*np.exp(np.log(v)*r['features']['cycle_count']/10000))for v,r in zip(p,orig)]
   engine.add_predictions('R4_per_cycle_rate',kind,train,orig,restored)
  tr=[r for r in rows if r['source_family']!=g];mean=float(np.average([r['target']for r in tr],weights=engine.weights(tr)));engine.add_predictions('R4_per_cycle_rate','training_mean',tr,orig,[mean]*len(orig))
 for source,n in sorted(local.items()):
  if n<4:continue
  rs=[r for r in rows if r['source_family']==source]
  for mat in sorted({r['material_key']for r in rs}):
   train=[r for r in rs if r['material_key']!=mat];test=[r for r in rs if r['material_key']==mat]
   for kind in ['ridge','random_forest','fixed_Matern_GPR']:engine.add_predictions('R5_known_family',kind,train,test,engine.fit_predict(kind,train,test,'R5_known_family',mat,True))
   mean=float(np.mean([r['target']for r in train]));engine.add_predictions('R5_known_family','training_mean',train,test,[mean]*len(test))
 assert len(engine.EVENTS)==expected,(len(engine.EVENTS),expected)
 # Prespecified blends use paired held-out predictions, no fitting or outer-score selection.
 for route in scopes:
  for name,models in [('equal_RF_XGB',['random_forest','xgboost']),('equal_RF_GPR',['random_forest','fixed_Matern_GPR'])]:
   maps=[{r['row_id']:r for r in engine.PREDS if r['route']==route and r['model']==m}for m in models]
   for rid in sorted(set(maps[0])&set(maps[1])):
    p=dict(maps[0][rid],model=name,predicted=(maps[0][rid]['predicted']+maps[1][rid]['predicted'])/2);engine.PREDS.append(p)
 groups=collections.defaultdict(list)
 for p in engine.PREDS:groups[(p['route'],p['model'])].append(p)
 metrics=[]
 for (route,model),p in sorted(groups.items()):
  s=engine.metrics(p,True);base=engine.metrics(groups[(route,'training_mean')]);s.update(route=route,model=model,mae_reduction_vs_mean=1-s['mae']/base['mae'],unseen_source_generalization_tested=route!='R5_known_family',prospective_external_validation=False)
  checks=dict(r2=s['r2']is not None and s['r2']>.95,mae=s['mae']<=2,rmse=s['rmse']<=3,p90_abs=s['p90_absolute_error']<=5,source_tail=s['source_p90_mae']<=5,baseline=s['mae_reduction_vs_mean']>=.2,complete_predictions=s['rows']==base['rows'])
  s['numerical_checks']=checks;s['numerical_pass']=all(checks.values());s['final_acceptance']=False;metrics.append(s)
 write(RUN/'heldout_predictions.json',engine.PREDS);write(RUN/'results.json',dict(completed_at=now(),actual_fits=len(engine.EVENTS),planned_fits=expected,failures=engine.FAILURES,warnings=sum(bool(e.get('warnings'))for e in engine.EVENTS),metrics=metrics,fixed_io_preserved=True,final_acceptance=False,new_training_admissions=0))
 write(RUN/'progress.json',dict(status='complete',completed_fits=expected,planned_fits=expected))
 for s in metrics:
  if s['model']!='training_mean':print(s['route'],s['model'],'n',s['rows'],'R2',round(s['r2'],4),'MAE',round(s['mae'],3),'RMSE',round(s['rmse'],3),'pass',s['numerical_pass'],flush=True)
if __name__=='__main__':main()
