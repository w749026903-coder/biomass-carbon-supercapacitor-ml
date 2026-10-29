"""Authorized direct-prediction route: separate 2E and3E fixed-input pilots."""
from pathlib import Path
import collections,json,sys,time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.prepare_small_sample_routes import read,write,sha,now
import tools.run_small_sample_routes as engine
OUT=ROOT/'保持率双路线预研_v2_20261029';RUN=OUT/'A_材料工况直接预测'
BASE=['cycle_count','reported_current_A_g','electrolyte','concentration_mol_L','cycle_voltage_lower_V','cycle_voltage_upper_V','BET_m2_g']
MODELS=['ridge','random_forest','xgboost','small_BP_MLP','fixed_Matern_GPR']
def main():
 assert not RUN.exists(),'Do not replace or repeat a started experiment'
 RUN.mkdir();raw=read(OUT/'baseline_inputs.json');data={}
 for system,a in raw.items():
  fields=BASE+(['reference_electrode']if system=='3E'else[]);data[system]=[]
  for r in a:data[system].append(dict(r,features={k:r['features'].get(k)for k in fields},material_key=r['material_key']or r['source_family']+'::'+r['sample_name']))
 expected=sum(len({r['source_family']for r in a})*len(MODELS)for a in data.values());write(RUN/'input_snapshot.json',data)
 plan=dict(frozen_at=now(),authorization='User selected both A/B scenarios, separately evaluated; this is material/condition-only A.',output='capacitance_retention_pct',inputs_by_system={'2E':BASE,'3E':BASE+['reference_electrode']},input_sha256=sha(RUN/'input_snapshot.json'),baseline_source_sha256=sha(OUT/'baseline_inputs.json'),contract_sha256=sha(OUT/'contract.json'),runner_sha256=sha(Path(__file__)),engine_sha256=sha(ROOT/'tools/run_small_sample_routes.py'),models=MODELS,primary_model='random_forest',planned_fits=expected,parameters=read(ROOT/'小样本方向预研_20261029/training_plan.json')['model_parameters'],validation='Whole-source-family holdout separately within each electrode configuration. Existing explored sources, no untouched external claim. No early measured retention as input.',stop='One named pass only; no score-driven new model, scope or hyperparameters.',criteria=dict(r2_gt=.95,mae_pp_max=2,rmse_pp_max=3,p90_abs_pp_max=5,source_p90_mae_pp_max=5,mae_improvement_vs_mean_min=.2),data_admissions=0)
 write(RUN/'training_plan.json',plan);engine.RUN=RUN;engine.START=time.monotonic();engine.EVENTS=[];engine.PREDS=[];engine.FAILURES=[];engine.PLANNED=expected
 for system,a in data.items():engine.source_cv('A_'+system,a,MODELS)
 assert len(engine.EVENTS)==expected
 write(RUN/'heldout_predictions.json',engine.PREDS);groups=collections.defaultdict(list)
 for p in engine.PREDS:groups[(p['route'],p['model'])].append(p)
 scores=[]
 for (route,model),a in sorted(groups.items()):
  s=engine.metrics(a,True);base=engine.metrics(groups[(route,'training_mean')]);s.update(route=route,model=model,mae_reduction_vs_mean=1-s['mae']/base['mae'])
  s['checks']=dict(r2=s['r2']is not None and s['r2']>.95,mae=s['mae']<=2,rmse=s['rmse']<=3,p90_abs=s['p90_absolute_error']<=5,source_tail=s['source_p90_mae']<=5,baseline=s['mae_reduction_vs_mean']>=.2,coverage=s['rows']==base['rows']);s['numeric_pass']=all(s['checks'].values());s['final_reliable']=False;scores.append(s)
 write(RUN/'results.json',dict(status='complete',fits=expected,failures=engine.FAILURES,metrics=scores,old_data_unchanged=True,new_admissions=0,final_reliable=False));write(RUN/'progress.json',dict(status='complete',completed_fits=expected,planned_fits=expected))
 for s in scores:print(s['route'],s['model'],'R2',round(s['r2'],3),'MAE',round(s['mae'],3),'RMSE',round(s['rmse'],3),'pass',s['numeric_pass'])
if __name__=='__main__':main()
