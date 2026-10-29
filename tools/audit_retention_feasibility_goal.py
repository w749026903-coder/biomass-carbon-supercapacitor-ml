"""Close the feasibility-report gaps using existing predictions only; zero fits."""
from pathlib import Path
import collections, hashlib, html, json, math, subprocess
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'小样本方向预研_20261029';RUN=BASE/'保持率固定输入输出';OUT=BASE/'审计补充'
COMPARISONS=[('R1_KOH6_10000','random_forest','R1 固定6M KOH与10000圈'),('R2_KOH6_10000_j10','random_forest','R2 再固定10 A/g'),('R3_plant_residue_KOH6','random_forest','R3 植物残余物与6M KOH'),('R4_per_cycle_rate','random_forest','R4 每圈衰减速率变换'),('R5_known_family','fixed_Matern_GPR','R5 已知家族内留材料')]
def read(p):return json.loads(Path(p).read_text('utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n','utf8')
def weights(a):
 groups=collections.defaultdict(lambda:collections.Counter())
 for r in a:groups[r['source_family']][r['material_key']]+=1
 return np.array([1/len(groups)/len(groups[r['source_family']])/groups[r['source_family']][r['material_key']]for r in a])
def main():
 assert not OUT.exists(),'Audit is a new additive artifact; do not overwrite'
 OUT.mkdir();checks=[]
 def check(value,name):
  assert value,name;checks.append(name)
 plan=read(RUN/'training_plan.json');result=read(RUN/'results.json');data=read(RUN/'input_snapshot.json');lookup={r['row_id']:r for r in data['rows']};preds=read(RUN/'heldout_predictions.json');metrics={(r['route'],r['model']):r for r in result['metrics']}
 protected=read(BASE/'source_protection.json')
 for path,h in protected.items():check(sha(ROOT/path)==h,'protected:'+path)
 for x in read(BASE/'merge_manifest.json')['files']:check(sha(ROOT/x['path'])==x['sha256'],'run_manifest:'+x['path'])
 old_manifest=read(ROOT/'模型v1.3_新数据与辅助学习_20261029/merge_manifest.json')
 for x in old_manifest['outputs']:check(sha(ROOT/x['path'])==x['sha256'],'old_v13:'+x['path'])
 check(sha(ROOT/'tools/run_fixed_io_retention_routes.py')==plan['runner_sha256'],'frozen_runner')
 check(sha(ROOT/'tools/run_small_sample_routes.py')==plan['engine_sha256'],'frozen_engine')
 check(sha(BASE/'input_snapshot.json')==plan['source_snapshot_sha256'],'frozen_source_snapshot')
 check(sha(ROOT/'docs/RETENTION_DIRECTION_GOAL.json')==plan['goal_sha256'],'frozen_original_contract')
 events=[json.loads(x)for x in(RUN/'fit_events.jsonl').read_text('utf8').splitlines()]
 check(len(events)==plan['planned_fits']==result['actual_fits']==251,'finite_fit_count')
 for e in events:
  train=set(e['train_row_ids']);test=set(e['test_row_ids']);check(not train&test,'split:'+str(e['fit_index']))
  if e['route']=='R5_known_family':check(not{lookup[x]['material_key']for x in train}&{lookup[x]['material_key']for x in test},'material:'+str(e['fit_index']))
  else:check(not set(e['train_sources'])&set(e['test_sources']),'source:'+str(e['fit_index']))
  check(all(x['field']in plan['fixed_inputs']for x in e.get('encoder',[])),'input_whitelist:'+str(e['fit_index']))
 check(len([e for e in events if e['status']=='failed'])==len(result['failures'])==1,'failure_retained')
 rows=[]
 for route,model,label in COMPARISONS:
  a=sorted([r for r in preds if r['route']==route and r['model']==model],key=lambda r:r['row_id']);b={r['row_id']:r for r in preds if r['route']==route and r['model']=='training_mean'}
  check(len(a)==len(b)and {r['row_id']for r in a}==set(b),'matched_baseline:'+route)
  check(all(r['observed']==b[r['row_id']]['observed']==lookup[r['row_id']]['target']for r in a),'same_observed:'+route)
  check(all(not r['calibration_row_ids']for r in a),'no_added_observed_input:'+route)
  w=weights(a);y=np.array([r['observed']for r in a]);p=np.array([r['predicted']for r in a]);q=np.array([b[r['row_id']]['predicted']for r in a]);err=np.abs(p-y);baseline=np.abs(q-y);var=np.average((y-np.average(y,weights=w))**2,weights=w)
  values=dict(mae_pp=float(np.average(err,weights=w)),rmse_pp=float(np.sqrt(np.average(err**2,weights=w))),r2=float(1-np.average(err**2,weights=w)/var),mape_pct=float(np.average(err/y,weights=w)*100),baseline_mae_pp=float(np.average(baseline,weights=w)),baseline_mape_pct=float(np.average(baseline/y,weights=w)*100))
  s=metrics[(route,model)]
  for ours,theirs in [('mae_pp','mae'),('rmse_pp','rmse'),('r2','r2'),('mape_pct','mape_pct')]:check(math.isclose(values[ours],s[theirs],rel_tol=1e-10,abs_tol=1e-9),'recompute:'+route+':'+ours)
  delta=err-baseline;groups=sorted({r['source_family']for r in a});delta_by_group=np.array([np.average(delta[[r['source_family']==g for r in a]],weights=w[[r['source_family']==g for r in a]])for g in groups]);rng=np.random.default_rng(20261029);boot=np.mean(rng.choice(delta_by_group,size=(2000,len(groups)),replace=True),axis=1);ci=np.quantile(boot,[.025,.975]).tolist()
  check(math.isclose(float(np.mean(delta_by_group)),values['mae_pp']-values['baseline_mae_pp'],abs_tol=1e-10),'paired_source_weighting:'+route)
  rows.append(dict(route=route,model=model,label=label,rows=len(a),sources=len(groups),**values,mae_change_vs_baseline_pp=values['mae_pp']-values['baseline_mae_pp'],mae_improvement_pct=100*(1-values['mae_pp']/values['baseline_mae_pp']),paired_source_bootstrap_95pct_delta_mae_pp=ci,statistically_confirmed_improvement=ci[1]<0,generalization_scope='known-family new-material exploration'if route=='R5_known_family'else'whole-source-family-held-out exploration',untouched_external_test=False))
 failed_model=[s for s in result['metrics']if not s['numerical_checks']['complete_predictions']]
 check(all(not s['numerical_pass']for s in failed_model),'partial_coverage_cannot_pass')
 review=read(RUN/'文献与开源方法审查.json');check(len(review['repositories'])==2 and all(r.get('commit')and r.get('read_files')for r in review['repositories']),'pinned_read_repository_evidence')
 check(not review['third_party_code_executed'],'third_party_read_only')
 acceptance=sum(s['numerical_pass']for s in result['metrics']);check(acceptance==0,'no_false_acceptance')
 write(OUT/'相对误差与配对基线核验.json',dict(comparisons=rows,bootstrap='2000 paired source resamples; descriptive, reused development sources, no new fits',relative_error_definition='100*source/material-balanced mean(abs(predicted-actual)/actual). Retention actuals positive. Near100 labels can yield small MAPE despite poor R2.',failed_model_coverage=[dict(route=s['route'],model=s['model'],valid_predictions=s['rows'],complete=False)for s in failed_model]))
 requirements=[
 ('多条保持率预测路线','保持率固定输入输出/training_plan.json: R1–R6，五类实际范围/变换/家族方案及固定组合；比电容/BET另标偏离目标','proved'),
 ('初步验证及可行性结论','251次拟合尝试、逐次成员与留出预测；全部未通过的负结论保留，未来曲线方案明确尚未训练','proved'),
 ('R²、MAE、RMSE、相对误差、简单基线','results.json加本次逐条配对和MAPE复算；5个事前方法与均值在完全相同记录比较','proved'),
 ('冻结计划、有限候选、可复现','计划/源快照/两训练程序SHA一致，251次停止，无本轮新增拟合；环境版本和成员均保存','proved'),
 ('来源/样品隔离或实测条件明确','R1–R4整来源隔离；R5整材料留出但仅已知家族，明确不能称新来源；无测试保持率输入','proved'),
 ('原值与旧库/模型保护','63份保护源、原试验26项manifest、旧v1.3全部46项输出SHA匹配；原合同未回写','proved'),
 ('真实报告与可视化交付','保持率方向预研报告.html、MAE图、版式核验.json及已向用户报告；附合同提案、论文/固定GitHub版本','proved'),
 ('达到0.95是否为本预研完成的必要条件','原目标明确“不承诺或伪造达到0.95”“完成标准…初步可行性结论…而非强行达标”；本轮0个模型达标','not_required_and_not_achieved'),
 ('用户允许的输入合同变更是否已执行','未执行。A/B讨论等待选择，属于下一轮实验前置，不阻止报告既有基准的可行性结论','pending_future_experiment_only')]
 write(OUT/'目标逐项完成审计.json',dict(objective_scope='Multiple-route preliminary feasibility assessment and report; not the overarching successful-model challenge.',requirements=[dict(requirement=a,evidence=b,status=c)for a,b,c in requirements],checks=len(checks),estimator_fits_during_audit=0,baseline_numeric_pass_count=0,retention_high_accuracy_goal_achieved=False,input_contract_change_pending=True,feasibility_report_objective_verified=True,check_names=checks))
 headers=['方案','R²','MAE/百分点','MAPE/%','均值MAE','相对均值改善/%','MAE差95%区间/百分点']
 bodyrows=[[r['label'],f"{r['r2']:.3f}",f"{r['mae_pp']:.3f}",f"{r['mape_pct']:.2f}",f"{r['baseline_mae_pp']:.3f}",f"{r['mae_improvement_pct']:.2f}",f"[{r['paired_source_bootstrap_95pct_delta_mae_pp'][0]:.3f}, {r['paired_source_bootstrap_95pct_delta_mae_pp'][1]:.3f}]"]for r in rows]
 md='# 保持率预研：相对误差与基线补充\n\n只重算既有留出预测，本次新增模型拟合0次。原输出保持率不变，新输入合同仍待讨论。\n\n| '+' | '.join(headers)+' |\n|'+ '|'.join(['---']*len(headers))+'|\n'+''.join('| '+' | '.join(r)+' |\n'for r in bodyrows)
 md+='\n改善为正表示模型MAE比均值更低；配对MAE差的区间上限小于0，才支持本次描述性比较中的稳定改善。当前五个对比没有任何一个满足该条件。R5只检验已知家族内的新材料，并未验证全新来源。\n\nMAPE约4%不等于模型已好：大部分保持率接近100%，相对误差看起来小，仍可能不如简单均值，R²也可能为负。因此R²、绝对误差、简单基线和泛化必须合看。\n\n本轮多个路线的预研结论和报告已具备交付证据；高精度保持率模型尚未训练成功。下一轮输入或电极合同改变仍需用户讨论确认，不能把预研完成当作R²>0.95目标完成。\n'
 (OUT/'指标与基线补充.md').write_text(md,'utf8')
 table='<table><thead><tr>'+''.join('<th>'+html.escape(h)+'</th>'for h in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+html.escape(c)+'</td>'for c in r)+'</tr>'for r in bodyrows)+'</tbody></table>'
 content='<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>保持率预研：指标与基线补充</title><style>body{max-width:1140px;margin:40px auto;padding:0 22px;font:16px/1.8 "Microsoft YaHei",sans-serif;color:#21372c;background:#f7f9f7}h1{font-size:27px}.table{overflow:auto}table{border-collapse:collapse;background:white;width:100%;font-size:14px}th,td{padding:12px;border-bottom:1px solid #dbe5df;text-align:left;min-width:74px}th{background:#e6f0e9}a{color:#176447}.status{border-left:4px solid #a55635;background:#fff0e5;padding:16px}</style><h1>保持率预研：相对误差与简单基线</h1><p class="status">本次新增拟合0次；模型尚未达标。输入合同变更仍等待讨论。</p><p>以下比较采用完全相同的留出记录和来源/材料均衡权重，模型为原计划预定方法，未按外层最高分重选。</p><div class="table">'+table+'</div><p>改善为正，表示模型MAE比训练均值更低；MAE差区间的上限小于0，才支持本次来源重采样中的稳定改善。当前五个对比均未满足。R5只有3个已知家族，不能解释成全新来源泛化。</p><p>MAPE约4%仍可能不如均值：保持率多数接近100%，相对误差看似小，R²仍可能为负。应同时检查R²、绝对误差、基线和泛化。区间基于已探索来源，仅作描述性比较。</p><p>251次有限保持率试验与多个路线的取舍已经形成预研报告；R²>0.95的高精度模型目标尚未实现。下一步新合同须用户确认。</p><p><a href="../保持率固定输入输出/保持率方向预研报告.html">查看完整路线报告</a> · <a href="相对误差与配对基线核验.json">逐项复算数据</a> · <a href="目标逐项完成审计.json">目标要求与证据</a></p></html>'
 (OUT/'指标与基线补充.html').write_text(content,'utf8')
 print(json.dumps(dict(checks=len(checks),comparisons=rows,new_fits=0,old_v13_hashes=46,feasibility_report_objective_verified=True),ensure_ascii=False,indent=2))
if __name__=='__main__':main()
