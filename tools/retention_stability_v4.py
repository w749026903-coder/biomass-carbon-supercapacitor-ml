"""Finite no-refit stability comparison using archived source-isolated predictions."""
from pathlib import Path
import argparse,collections,gzip,hashlib,json,math,sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.run_small_sample_routes import metrics
from tools.retention_v3_optimizer import now
BASE=ROOT/'保持率达标研究_v3_主线与近优组合_20261030';OLD=BASE/'第三轮_扩充来源验证';OUT=BASE/'第四轮_选模稳定性复核'
RULES=['prior_nested_selected','family8_equal','candidate16_equal','oneSE_family_mean','oneSE_simplest','near4_median','soft_family_T1','soft_family_T2','inverse_family_MAE']
SIMPLE=['Ridge_early','RF_early','ExtraTrees_early','GPR_early','XGB_early','RF_static','GPR_static','XGB_static']
NEAR=['RF_early','GPR_early','XGB_early','RF_static']
def read(p):return json.loads(Path(p).read_text('utf8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,x):Path(p).write_bytes((json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode('utf8'))
def prepare():
 assert not OUT.exists(),'Never overwrite a planned study';OUT.mkdir()
 paths=['input_snapshot.json','candidate_configurations.json','training_plan.json','nested_selection.json','fit_predictions.jsonl.gz','heldout_predictions.json','results.json','independent_verification.json']
 protected={str((OLD/p).relative_to(ROOT).as_posix()):sha(OLD/p)for p in paths};protected['tools/run_small_sample_routes.py']=sha(ROOT/'tools/run_small_sample_routes.py')
 plan=dict(frozen_at=now(),runner_sha256=sha(Path(__file__)),protected=protected,rules=RULES,primary='oneSE_family_mean',simplicity_order=SIMPLE,near_families=NEAR,cohorts=['B_3E_early20','B_3E_early10'],source_counts={'B_3E_early20':[30,24],'B_3E_early10':[20,19]},new_estimator_fits=0,new_ensemble_weight_fits=0,rule_definition={'oneSE':'For each outer source, use winning candidate inner-source MAE standard error=std(per-sourceMAE,ddof1)/sqrt(G); accept selected family representatives with innerMAE<=winner+SE; mean them or choose first fixed simplicity order. No outer error informs eligibility.', 'soft':'Weights=softmax(-(innerMAE-minMAE)/T), T fixed1 or2pp over8 family winners.', 'inverse':'Weights proportional1/(innerMAE+.25pp) over8 family winners. No outer weights learned.','candidate16_equal':'Equal mean all16 archived candidate predictions; no candidate eliminated.','near4_median':'Median RF/GPR/XGB-early andRF-static selected in prior inner folds.'},metrics_unchanged=read(OLD/'training_plan.json')['criteria'],scientific_status='New prespecified analysis rules on already exposed development sources. Model predictions reused, not new prospective confirmation. Keep original third-round primary/results intact. No highest-score replacement of this primary.',output='capacitance_retention_pct_at_declaredN_and_conditions',inputs='Same six approved early summaries and optional static values, windows/minimum3 unchanged.',A_and_2E='Historical A/2E results retained; no corresponding new inner prediction archive or new data in this batch, no false new fits.',stop='Exactly9 finite rules x2 unchanged cohorts. No outcome-driven rules added.',goal_status='active')
 write(OUT/'analysis_plan.json',plan);write(OUT/'progress.json',dict(status='frozen_ready',rules=9,model_fits=0));print('Frozen9 rules, primaryoneSE_family_mean, no new fits')
def run():
 plan=read(OUT/'analysis_plan.json');assert not(OUT/'results.json').exists(),'Do not rerun a completed analysis'
 assert plan['runner_sha256']==sha(Path(__file__))
 for p,h in plan['protected'].items():assert sha(ROOT/p)==h,p
 data=read(OLD/'input_snapshot.json');oldpred=read(OLD/'heldout_predictions.json');cfg=read(OLD/'candidate_configurations.json');inner=collections.defaultdict(list)
 with gzip.open(OLD/'fit_predictions.jsonl.gz','rt',encoding='utf8')as f:
  for line in f:
   q=json.loads(line)
   if q['role']=='inner':inner[(q['route'],q['outer_source'],q['config_id'])].extend(q['predictions'])
 final={(r['route'],r['model'].removeprefix('fixed::'),r['row_id']):r for r in oldpred if r['model'].startswith('fixed::')};byroute={k:{r['row_id']:r for r in rows}for k,rows in data.items()};pred=[];selection=[]
 for s in read(OLD/'nested_selection.json'):
  route=s['route'];outer=s['outer_source'];scores=s['inner_scores'];fam=s['family_selected'];winner=s['overall_selected'];winrows=inner[(route,outer,winner['config_id'])];stat=metrics(winrows);G=len(stat['per_source']);se=float(np.std([r['mae']for r in stat['per_source']],ddof=1)/math.sqrt(G));eligible=[f for f in SIMPLE if fam[f]['mae']<=winner['mae']+se+1e-12];assert eligible
  families=sorted(fam);fscore=np.array([fam[f]['mae']for f in families]);soft={T:np.exp(-(fscore-min(fscore))/T)for T in[1,2]};soft={T:(z/sum(z))for T,z in soft.items()};inv=1/(fscore+.25);inv/=sum(inv);test=[r for r in data[route]if r['source_family']==outer]
  selection.append(dict(route=route,outer_source=outer,minimum_inner_mae=winner['mae'],winner=winner['config_id'],inner_source_mae_standard_error=se,eligible_oneSE_families=eligible,simplest_selected=eligible[0],soft_families=families,soft_T1_weights=soft[1].tolist(),soft_T2_weights=soft[2].tolist(),inverse_weights=inv.tolist(),uses_only_inner_row_ids=[r['row_id']for r in winrows]))
  for r in test:
   rid=r['row_id'];pv={f:final[(route,fam[f]['config_id'],rid)]['predicted']for f in fam};values=np.array([pv[f]for f in families]);v=dict(prior_nested_selected=final[(route,winner['config_id'],rid)]['predicted'],family8_equal=float(values.mean()),candidate16_equal=float(np.mean([final[(route,c['id'],rid)]['predicted']for c in cfg])),oneSE_family_mean=float(np.mean([pv[f]for f in eligible])),oneSE_simplest=pv[eligible[0]],near4_median=float(np.median([pv[f]for f in NEAR])),soft_family_T1=float(values@soft[1]),soft_family_T2=float(values@soft[2]),inverse_family_MAE=float(values@inv));assert set(v)==set(RULES)
   for name,z in v.items():pred.append(dict(route=route,model=name,row_id=rid,source_family=outer,curve_id=r['curve_id'],material_key=r['material_key'],sample_name=r['sample_name'],observed=r['target'],predicted=z))
 for p in oldpred:
  if p['model']in['training_mean','early_persistence','early_linear']:pred.append(p)
 write(OUT/'heldout_predictions.json',pred);write(OUT/'rule_selection.json',selection);grouped=collections.defaultdict(list)
 for p in pred:grouped[(p['route'],p['model'])].append(p)
 summaries=[]
 for(route,method),a in sorted(grouped.items()):
  m=metrics(a,bootstrap=method==plan['primary']);m.update(route=route,model=method)
  m['checks']=dict(r2=m['r2']>.95,mae=m['mae']<=2,rmse=m['rmse']<=3,mape=m['mape_pct']<=5,p90_ape=m['p90_ape_pct']<=10,p90_abs=m['p90_absolute_error']<=5,source_tail=m['source_p90_mae']<=5,coverage=len(a)==len(data[route]),positive=all(r['predicted']>0 for r in a))
  for b in['training_mean','early_persistence','early_linear']:
   bm=metrics(grouped[(route,b)]);z=1-m['mae']/bm['mae'];m['mae_reduction_vs_'+b]=z;m['checks']['beat_'+b]=z>=.2
  m['numeric_pass']=all(m['checks'].values());m['reliable_model_accepted']=False;summaries.append(m)
 # Exact control reproduction is mandatory, not an optional favourable result.
 old={(m['route'],m['model']):m for m in read(OLD/'results.json')['metrics']}
 for s in summaries:
  if s['model']=='prior_nested_selected':
   for k in['r2','mae','rmse']:assert abs(s[k]-old[(s['route'],'nested_selected')][k])<1e-10
 for p,h in plan['protected'].items():assert sha(ROOT/p)==h,p
 write(OUT/'results.json',dict(status='complete',new_estimator_fits=0,new_weight_fits=0,rules=9,metrics=summaries,numeric_pass_count=sum(s['numeric_pass']for s in summaries),genuinely_new_external_sources=0,old_results_changed=False,goal_achieved=False,completed_at=now()))
 write(OUT/'progress.json',dict(status='complete',rules=9,model_fits=0,goal_status='active'))
 for s in summaries:
  if s['route']=='B_3E_early20':print(s['model'],round(s['r2'],4),round(s['mae'],4),round(s['rmse'],4),flush=True)
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','run']);a=parser.parse_args();prepare()if a.action=='prepare'else run()
