"""Current goal dashboard; historical experimental records remain immutable."""
from pathlib import Path
import html,json
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'保持率达标研究_v3_主线与近优组合_20261030';RUN=BASE/'第三轮_扩充来源验证'
def read(p):return json.loads(Path(p).read_text('utf8'))
def main():
 result=read(RUN/'results.json');audit=read(RUN/'independent_verification.json');diag=read(RUN/'error_diagnostics.json');goal=read(BASE/'research_goal.json');pred=read(RUN/'heldout_predictions.json')
 label={'nested_selected':'预定主方法：内层统一选模','near4_equal':'RF/GPR/XGB/RF静态：等权组合','near4_inner_convex':'四分支：内层学习权重','training_mean':'参照：训练来源平均值','early_persistence':'参照：沿用最后早期保持率','early_linear':'参照：早期斜率直接外推'}
 order=['nested_selected']+['nested_family::'+s for s in['RF_early','GPR_early','XGB_early','RF_static','GPR_static','XGB_static','Ridge_early','ExtraTrees_early']]+['near4_equal','near4_inner_convex','training_mean','early_persistence','early_linear']
 labels={'RF_early':'RF早期','GPR_early':'GPR早期','XGB_early':'XGBoost早期','RF_static':'RF＋材料/工况','GPR_static':'GPR＋材料/工况','XGB_static':'XGBoost＋材料/工况','Ridge_early':'Ridge早期','ExtraTrees_early':'ExtraTrees早期'}
 label.update({'nested_family::'+k:v for k,v in labels.items()})
 def table(route):
  rows=[];m={r['model']:r for r in result['metrics']if r['route']==route}
  for method in order:
   s=m[method];rows.append(f'<tr><td>{label[method]}</td><td>{s["r2"]:.3f}</td><td>{s["mae"]:.3f}</td><td>{s["rmse"]:.3f}</td><td>{s["p90_absolute_error"]:.3f}</td><td>{"数值通过"if s["numeric_pass"]else"未达标"}</td></tr>')
  return '<div class="table"><table><thead><tr><th>方法</th><th>R²</th><th>MAE/pp</th><th>RMSE/pp</th><th>90%误差/pp</th><th>验收</th></tr></thead><tbody>'+''.join(rows)+'</tbody></table></div>'
 primary=next(r for r in result['metrics']if r['route']=='B_3E_early20'and r['model']=='nested_selected');ens=next(r for r in result['metrics']if r['route']=='B_3E_early20'and r['model']=='near4_equal');best=max([r for r in result['metrics']if r['route']=='B_3E_early20'and r['model'].startswith('fixed::')],key=lambda r:r['r2']);bad=diag['routes']['B_3E_early20']['difficult_cases'][:5]
 cases=''.join(f'<tr><td>{html.escape(r["sample"])}</td><td>{r["observed_retention_pct"]:.2f}</td><td>{r["predicted_retention_pct"]:.2f}</td><td>{r["absolute_error_pp"]:.2f}</td></tr>'for r in bad)
 # A scientific scatter of the actual30 held-source predictions; no smoothed/fabricated points.
 pts=[r for r in pred if r['route']=='B_3E_early20'and r['model']=='nested_selected'];dots=''.join(f'<circle cx="{55+(r["observed"]-60)/55*440:.2f}" cy="{270-(r["predicted"]-60)/55*230:.2f}" r="4" fill="#33735b"><title>{html.escape(r["sample_name"])}：实测{r["observed"]:.2f}，预测{r["predicted"]:.2f}</title></circle>'for r in pts)
 scatter=f'<svg viewBox="0 0 540 315" role="img" aria-label="30条整来源留出预测与真实保持率散点"><path d="M55 30 V270 H510" fill="none" stroke="#53665b"/><path d="M55 270 L495 40" fill="none" stroke="#b7773d" stroke-dasharray="6 4"/>{dots}<text x="180" y="307">真实保持率（%）</text><text x="58" y="21">预测保持率（%）</text><text x="20" y="273">60</text><text x="16" y="44">115</text><text x="50" y="290">60</text><text x="480" y="290">115</text></svg>'
 style='*{box-sizing:border-box}body{background:#f4f6f5;color:#20392e;font:16px/1.8 "Microsoft YaHei",sans-serif;margin:0}main{max-width:1080px;margin:30px auto;padding:0 20px 40px}h1{font-size:28px;line-height:1.4}h2{font-size:21px}.status{padding:18px;background:#fff0de;border-left:5px solid #9a5b30}.cards{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:20px 0}.card,.box{background:white;padding:18px;border:1px solid #dae4df}.number{font-size:26px;display:block;font-weight:bold}.table{overflow:auto;background:white}table{border-collapse:collapse;width:100%;font-size:14px}td,th{padding:9px 12px;text-align:left;min-width:76px;border-bottom:1px solid #e0e7e2}td:first-child{min-width:230px}th{background:#e3eee7}.small{font-size:14px;color:#53665b}a{color:#176344;overflow-wrap:anywhere}details{margin:20px 0}summary{cursor:pointer}svg{max-width:600px;width:100%;height:auto}code{overflow-wrap:anywhere}@media(max-width:650px){.cards{grid-template-columns:1fr}h1{font-size:23px}}'
 page=f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>保持率主线：扩充来源后的验证进度</title><style>{style}</style></head><body><main>
<p class="small">2026-10-30 · 持续研究，输出始终为指定圈数与条件下的电容保持率</p><h1>保持率主线：先扩大证据，再检验模型</h1>
<p class="status"><b>目标继续active，尚无全面达标模型。</b>早期循环辅助作为研究主线；RF、GPR、XGBoost和含材料/工况的组合全部保留，A直接预测与两电极历史结果也继续保留。算法不会因为一轮高分就被认定为最终方案。</p>
<div class="cards"><div class="card"><span class="number">30条 / 24来源</span>三电极前20%循环研究输入</div><div class="card"><span class="number">3440＋43</span>本轮基础拟合＋内层组合权重拟合</div><div class="card"><span class="number">0个</span>模型通过全部数值与泛化验收</div></div>
<h2>本轮真正增加了什么</h2><p>已有PDF的固定20来源队列已逐篇核读。先前3条曲线之后，又审查21条、接入14条，7条因图文冲突、起点不清或早期点数不足保留待处理。研究库共接入17条新的早期曲线信息；前20%方案从最初13条/8来源扩大到30条/24来源，前10%为20条/19来源。像素和曲线点没有当成独立材料。</p>
<p>这些是以前已使用端点的新早期信息，<b>新增真正独立外部来源仍为0</b>。旧作者标签没有改写，新增正式循环准入为0。新曲线可从<a href="第二轮_证据与曲线扩充/cycling_research_v3b.sqlite">研究SQLite</a>的training_B_3E_early20等只读视图调用；旧研究库和v7入口均保留。</p>
<h2>更多来源没有维持住旧高分</h2><p>本轮预定主方法R²={primary['r2']:.3f}、MAE={primary['mae']:.3f}pp、RMSE={primary['rmse']:.3f}pp。四分支等权组合为{ens['r2']:.3f}、{ens['mae']:.3f}pp、{ens['rmse']:.3f}pp。事后固定候选最高R²={best['r2']:.3f}，仍未达标，也不替换预定主方法。旧8来源结果和新24来源结果不是同一测试集，不能直接当成参数改善或退步的因果证据。</p>
{table('B_3E_early20')}<p class="small">pp为保持率百分点；“90%误差”是绝对误差的加权90%分位。每个算法家族在训练来源内选择参数。外层整篇来源留出，内层4折整来源验证；同篇样品及电解液不拆散。16候选先冻结，所有内层和外层逐条预测均已保存。</p>
<details><summary>展开：前10%循环方案（20条 / 19来源）</summary>{table('B_3E_early10')}</details>
<div class="box"><b>达标比“RMSE小于3”更严格。</b>本批来源加权目标标准差约7.30pp；按同一加权定义，R²&gt;0.95实际要求RMSE&lt;1.632pp。MAE≤2pp、RMSE≤3pp、尾部误差、较三个简单参照至少改善20%，以及真正新来源验证都要同时看。它们是本项目工程验收目标，并非所有文献通用的统一阈值。</div>
<h2>当前误差集中在哪里</h2>{scatter}<div class="table"><table><thead><tr><th>预定主方法难例</th><th>作者保持率/%</th><th>预测/%</th><th>误差/pp</th></tr></thead><tbody>{cases}</tbody></table></div>
<p>CCL真实保持率109.2%属于活化上升，不能裁到100%；其50000圈目标也超出了其余来源的圈数范围。OAC的短周期快速下降、EUAC的先活化再下降，都使一条早期直线难以代表后期过程。除此之外，主方法24次外层选择中有15次选了GPR＋静态特征，但外层表现未优于多个固定分支，说明选模本身也不稳定。</p>
<p>部分图读界限已接近1～2pp；它们不是实验重复的标准差，不能据此宣布误差已无法降低。本轮已纠正CMC印字混入、AMFS宽标记重复计点，以及AUACW边框遮挡的终点读数。NPC、AC3、OPB、RSM的争议仍保留；稀疏点数门槛未擅自降低。</p>
<h2>后续研究顺序</h2><ol><li>保留所有近优家族，研究更稳定的训练内选模和固定组合，不按本轮外层成绩换主方案。</li><li>用已批准的早期输入检验非线性活化/衰减表达及误差处理，优先解决长周期外推和早期斜率不稳。若需新增输入或改变范围，先协商。</li><li>继续补真实曲线证据，准备与开发来源隔离的验证队列；先冻结最终方法和准入条件，再打开外部终值。</li><li>把每轮成功、失败和不确定性写入知识库；阶段完成不等于总体目标完成。</li></ol>
<p class="small">本轮{audit['checks']}项独立核验通过，375份保护文件SHA一致；SQLite完整性和外键通过。逐条内层预测已补存，本轮可另算内层分数与选择。核验没有重训3440模型，也不把图读像素当原始实验测量。</p>
<p><a href="research_goal.json">持续目标</a> · <a href="第三轮_扩充来源验证/training_plan.json">本轮冻结计划</a> · <a href="第三轮_扩充来源验证/results.json">全部结果</a> · <a href="第三轮_扩充来源验证/independent_verification.json">独立核验</a> · <a href="第三轮_扩充来源验证/error_diagnostics.json">逐来源误差诊断</a> · <a href="第二轮_证据与曲线扩充/existing_pdf_queue_reviewed.json">20来源逐篇审查</a> · <a href="第一轮_参数与表达/results.json">第一轮历史结果</a></p></main></body></html>'''
 (BASE/'研究进度.html').write_bytes(page.encode('utf8'))
 progress=dict(goal_status='active',high_accuracy_goal_achieved=False,phase1='complete_6324_plus20_preserved',phase2='all20_source_figures_reviewed',phase2_new_curves=17,phase2_batch2_reviewed=21,phase2_batch2_accepted=14,phase2_batch2_held=7,phase2_3E20_rows_sources=[30,24],phase2_3E10_rows_sources=[20,19],phase3='complete_independently_verified',phase3_estimator_fits=3440,phase3_ensemble_fits=43,model_process_running=False,finished_exec_session_id=37040,new_untouched_external_sources=0,phase3_primary_3E20={k:primary[k]for k in['r2','mae','rmse']},next='Continue train-only stability/continuation/reading-quality hypotheses and frozen truly external-source queue; preserve near branches and A/2E. Pending2-point threshold question is not applied. Do not rerun completed plans.')
 (BASE/'research_progress.json').write_bytes((json.dumps(progress,ensure_ascii=False,indent=2)+'\n').encode('utf8'))
 print(json.dumps(progress,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
