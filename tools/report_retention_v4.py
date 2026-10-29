"""Forward current dashboard for stability, nonlinear models and pending evidence."""
from pathlib import Path
import html,json,re,subprocess
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'保持率达标研究_v3_主线与近优组合_20261030';ST=BASE/'第四轮_选模稳定性复核';N=BASE/'第六轮_非线性延拓与稳健学习'
def read(p):return json.loads(Path(p).read_text('utf8'))
def main():
 old=subprocess.check_output(['git','-c','safe.directory='+ROOT.as_posix(),'show','74c7db9bd76c4c7ebc6b5ae898f99e027dffaad3:保持率达标研究_v3_主线与近优组合_20261030/研究进度.html']).decode('utf8');style=re.search(r'<style>(.*?)</style>',old,re.S).group(1)
 results=read(N/'results.json');st=read(ST/'results.json');audit=read(N/'independent_verification.json');proposal=read(BASE/'第七轮_同窗口形状表达提案/proposal.json')
 labels={'oneSE_family_mean':'成绩相近分支均值（本轮预定主方法）','nested_selected':'内层单一选模（对照）','near4_equal':'原四个近优分支：等权组合','family_all_equal':'全部12个分支：等权组合','training_mean':'参照：训练来源平均值','early_persistence':'参照：沿用早期保持率','early_linear':'参照：早期斜率外推'}
 names={'RF_early':'RF早期','GPR_early':'GPR早期','XGB_early':'XGBoost早期','RF_static':'RF＋材料/工况','GPR_static':'GPR＋材料/工况','XGB_static':'XGBoost＋材料/工况','Ridge_early':'Ridge早期（原分支）','ExtraTrees_early':'ExtraTrees早期','Ridge_signed':'新增：正负趋势分开的非线性Ridge','Huber_signed':'新增：正负趋势分开的Huber','GPR_linear_kernel':'新增：线性核＋局部核GPR','BP_signed':'新增：小型正则化BP网络'};labels.update({'nested_family::'+k:v for k,v in names.items()})
 order=['oneSE_family_mean','nested_selected']+['nested_family::'+k for k in names]+['near4_equal','family_all_equal','training_mean','early_persistence','early_linear']
 def table(route):
  lookup={m['model']:m for m in results['metrics']if m['route']==route};rows=[]
  for method in order:
   m=lookup[method];rows.append(f'<tr><td>{html.escape(labels[method])}</td><td>{m["r2"]:.3f}</td><td>{m["mae"]:.3f}</td><td>{m["rmse"]:.3f}</td><td>{m["p90_absolute_error"]:.3f}</td><td>{"数值通过"if m["numeric_pass"]else"未达标"}</td></tr>')
  return '<div class="table"><table><thead><tr><th>方法</th><th>R²</th><th>MAE/pp</th><th>RMSE/pp</th><th>90%误差/pp</th><th>验收</th></tr></thead><tbody>'+''.join(rows)+'</tbody></table></div>'
 def mget(ms,method):return next(m for m in ms if m['route']=='B_3E_early20'and m['model']==method)
 stable=mget(st['metrics'],'oneSE_family_mean');main=mget(results['metrics'],'oneSE_family_mean');oldprimary=mget(st['metrics'],'prior_nested_selected')
 body=f'''<p class="small">2026-10-30 · 主线与近优分支全部保留</p><h1>保持率研究：稳定性复核与非线性表达验证</h1><p class="status"><b>目标继续active，当前仍没有全面达标模型。</b>输出始终是指定圈数与条件下的电容保持率。原RF、GPR、XGBoost、材料/工况组合及A直接预测、两电极路线保留；输入窗口和原始标签均未改变。</p>
<div class="cards"><div class="card"><span class="number">30条 / 24来源</span>三电极20%研究数据保持完整</div><div class="card"><span class="number">2580新拟合</span>另复用3440次旧拟合的预测</div><div class="card"><span class="number">0个全面达标</span>尚无真正独立外部来源验证</div></div>
<h2>先把选模做稳，再检验复杂方法</h2><p>这次先冻结9种选模/组合规则，直接复用全部归档预测，不重新拟合基础模型。在同一批30条/24来源上，把内层成绩相近的家族一起平均，R²={stable['r2']:.3f}、MAE={stable['mae']:.3f}pp、RMSE={stable['rmse']:.3f}pp；此前单一选模为{oldprimary['r2']:.3f}/{oldprimary['mae']:.3f}/{oldprimary['rmse']:.3f}。这是已见开发来源上的规则比较，不能称为新的独立验证。</p>
<p>随后另行冻结12个新候选：正负趋势分开的非线性Ridge、Huber稳健回归、线性核＋局部核GPR、小型BP网络。所有表达仅由原六项摘要计算，未加入后期观测。与原16候选在完全相同的来源/折划分上比较；新增2580次拟合，旧3440次预测复用，没有重复计算成新训练。</p>
<div class="box"><b>更复杂没有带来进一步改善。</b>加入新候选后，本轮预定的相近成绩家族均值R²={main['r2']:.3f}、MAE={main['mae']:.3f}pp、RMSE={main['rmse']:.3f}pp。未把事后最高分换成主方法。7次拟合产生LBFGS收敛警告，输出与警告均保留；所有结果仍未全面达标。</div>
<h2>三电极前20%：全部分支同场比较</h2>{table('B_3E_early20')}<p class="small">pp为保持率百分点；每个家族只在训练来源内选参数。Huber的稳健损失不等于删除异常来源。真实保持率超过100%继续保留。目标仍为R²&gt;0.95、MAE≤2pp、RMSE≤3pp、尾部误差、超过各简单参照及真正新来源检验；本批R²门槛实际要求同权RMSE&lt;1.632pp。</p>
<details><summary>展开：前10%方案（20条 / 19来源）</summary>{table('B_3E_early10')}</details>
<h2>数据补查：保留来源缺口，也保留原文问题</h2><p>当前30条中，只有CCL这一个来源的终值超过100%，也只有它达到50000圈。把它整篇留出时，训练集没有同类的长周期活化增长标签。这是可核实的覆盖缺口，不靠删除CCL消除误差。</p>
<ul><li><a href="https://pmc.ncbi.nlm.nih.gov/articles/PMC7992145/">火龙果皮N-dfAC原文</a>：已取得作者存档图，读取55个可见轨迹位置。正文终值123%，图读约127.34%，固定读图区间125.09～129.59%，仍不一致；500mA/cm²保留为面积电流，不冒充报告A/g。该记录留作候选，尚未训练。</li><li><a href="https://www.mdpi.com/2073-4344/16/4/368">木质素HPCN论文</a>及<a href="https://pubs.rsc.org/en/content/articlelanding/2025/su/d4su00701h">稻壳GAC论文</a>：身份和公开检索内容已补查，但正文/图/SI获取仍被403拒绝。HPCN循环图对应配置、GAC与吸附染料后处理的组分阶段都需要原图核实，不从摘要拼接训练记录。</li></ul>
<p>这些来源部分早已在项目候选索引中，不能把本次补查称为收集了3个全新独立测试来源。当前新增训练行0，正式循环准入0，原v7和3b研究数据库哈希保持。</p>
<h2>下一项具体提案：同一窗口的曲线形状</h2><p>原六项摘要可能丢失“先升后降”或“斜率改变”等信息。已准备一个具体对照：仍只用前10%/20%的真实早期点，加入前后半段斜率、曲率和峰值相对位置，不增加实验。每半段至少3点，否则这些新特征保持空值、原记录保留。</p><p>前20%目前18条/16来源可计算这组形状特征；前10%为4条/4来源。<b>该输入扩展待用户确认，训练未启用。</b>此前2点稀疏观测提案同样未擅自实施。没有把等待答复当作同意，也没有因此关闭其他数据与证据工作。</p>
<p class="small">本轮{audit['checks']}项检查通过，396份保护SHA一致，原始标签不改；全部内层分数与来源划分另算、控制预测逐条核对。核验没有重训模型，不证明论文图文冲突已解决。总体目标继续active。</p>
<p><a href="research_goal.json">持续目标</a> · <a href="第四轮_选模稳定性复核/analysis_plan.json">9规则冻结计划</a> · <a href="第四轮_选模稳定性复核/results.json">稳定性结果</a> · <a href="第六轮_非线性延拓与稳健学习/training_plan.json">新候选冻结计划</a> · <a href="第六轮_非线性延拓与稳健学习/results.json">完整新结果</a> · <a href="第六轮_非线性延拓与稳健学习/independent_verification.json">核验与警告</a> · <a href="第五轮_长周期来源补证/source_review.json">候选来源审查</a> · <a href="第七轮_同窗口形状表达提案/proposal.json">形状表达提案</a> · <a href="第三轮_扩充来源验证/results.json">此前完整结果</a></p>'''
 page='<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>保持率研究：稳定性与非线性表达</title><style>'+style+'</style></head><body><main>'+body+'</main></body></html>'
 (BASE/'研究进度.html').write_bytes(page.encode('utf8'));progress=read(BASE/'research_progress.json');progress.update(phase4='9_stability_rules_complete_no_new_model_fits',phase4_primary={k:stable[k]for k in['r2','mae','rmse']},phase5='3_candidates_reviewed_no_training_admission',phase6='complete_2580_new_fits_3440_reused_prediction_fits',phase6_primary={k:main[k]for k in['r2','mae','rmse']},phase6_warnings=7,phase6_verification_checks=audit['checks'],phase7='same_window_shape_proposal_awaiting_confirmation_no_fit',model_process_running=False,finished_exec_session_id=65008,pending_contracts=['2point_sparse_comparison','4_same_window_shape_summaries'],next='While contract questions remain unanswered, continue evidence/source-quality work within existing inputs; do not apply proposal data to training or rerun completed plans. Seek actual original cyclic data/clear plots, keep near branches and A/2E, freeze genuine external test before new evaluation.');(BASE/'research_progress.json').write_bytes((json.dumps(progress,ensure_ascii=False,indent=2)+'\n').encode('utf8'));print('Dashboard updated; goalactive,0fully accepted models')
if __name__=='__main__':main()
