"""Small plain-language report of the two authorized scenarios; no new fits."""
from pathlib import Path
import collections,hashlib,html,json,math,sys
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'保持率双路线预研_v2_20261029'
def read(p):return json.loads(Path(p).read_text('utf-8-sig'))
def write(p,x):Path(p).write_bytes((json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode('utf8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def f(v,n=3):return f'{v:.{n}f}'if v is not None else'—'
def esc(x):return html.escape(str(x))
def table(headers,rows):return'<div class="table"><table><thead><tr>'+''.join('<th>'+esc(x)+'</th>'for x in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+esc(x)+'</td>'for x in row)+'</tr>'for row in rows)+'</tbody></table></div>'
def scatter(preds,path):
 a=[r for r in preds if r['route']=='B_3E_early20'and r['model']=='RF_early_residual'];w=660;h=310;x0=62;y0=18;plotw=550;ploth=242;lo=58;hi=104
 def xy(x,y):return(x0+(x-lo)/(hi-lo)*plotw,y0+ploth-(y-lo)/(hi-lo)*ploth)
 out=[f'<svg xmlns="http://www.w3.org/2000/svg" role="img" aria-label="三电极前20%观测随机森林的整来源留出预测散点图" viewBox="0 0 {w} {h}"><rect width="100%" height="100%" fill="white"/>']
 for t in[60,70,80,90,100]:
  x,y=xy(t,t);out+=[f'<path d="M{x},{y0}V{y0+ploth}M{x0},{y}H{x0+plotw}" stroke="#e6eae7"/><text x="{x}" y="{y0+ploth+20}" text-anchor="middle" font-size="12">{t}</text><text x="{x0-8}" y="{y+4}" text-anchor="end" font-size="12">{t}</text>']
 for delta,color in[(0,'#376b55'),(2,'#a8b7ae'),(-2,'#a8b7ae')]:
  x,y=xy(lo,lo+delta);xx,yy=xy(hi,hi+delta);out.append(f'<path d="M{x},{y}L{xx},{yy}" stroke="{color}" stroke-dasharray="5 4"/>')
 for p in a:
  x,y=xy(p['observed'],p['predicted']);out.append(f'<circle cx="{x}" cy="{y}" r="4.5" fill="#a55232" opacity=".85"><title>{esc(p["sample_name"])}：实测{f(p["observed"],2)}%，预测{f(p["predicted"],2)}%</title></circle>')
 out.append(f'<text x="{x0+plotw/2}" y="303" text-anchor="middle" font-size="13">论文报告的最终保持率 / %</text><text transform="translate(16,150) rotate(-90)" text-anchor="middle" font-size="13">留出预测 / %</text></svg>');path.write_bytes(''.join(out).encode('utf8'))
def main():
 a=read(OUT/'A_材料工况直接预测/results.json');b=read(OUT/'B_早期实测辅助预测/results.json');q=read(OUT/'reviewed_curve_data.json');check=read(OUT/'independent_verification.json');lookup={(s['route'],s['model']):s for s in a['metrics']+b['metrics']}
 comparison=[]
 specs=[('A_2E','random_forest','A 两电极：材料/工况'),('A_3E','random_forest','A 三电极：材料/工况'),('B_2E_early10','ridge_early_residual','B 两电极：最多前10% · 预定线性主方案'),('B_2E_early20','ridge_early_residual','B 两电极：最多前20% · 预定线性主方案'),('B_3E_early10','ridge_early_residual','B 三电极：最多前10% · 预定线性主方案'),('B_3E_early20','ridge_early_residual','B 三电极：最多前20% · 预定线性主方案'),('B_3E_early20','RF_early_residual','B 三电极：最多前20% · 随机森林候选')]
 for route,model,name in specs:
  s=lookup[(route,model)];comparison.append([name,f"{s['rows']} / {s['sources']}",f(s['r2']),f(s['mae']),f(s['rmse']),'未通过'])
 best=lookup[('B_3E_early20','RF_early_residual')];persist=lookup[('B_3E_early20','early_persistence')];mean=lookup[('B_3E_early20','training_mean')]
 ci=best['source_bootstrap_95pct']['r2'];delta=best['paired_baseline_comparisons']['early_persistence']['source_bootstrap_95pct'];sensitivity=best['reading_bound_le2pp_sensitivity'];stress=next(t for t in best['composition_stress_no_refits']if t['removed_source']=='doi:10.1016/j.heliyon.2024.e25628')
 preds=read(OUT/'B_早期实测辅助预测/heldout_predictions.json');scatter(preds,OUT/'三电极早期预测散点.svg')
 fullrows=[]
 for s in a['metrics']+b['metrics']:fullrows.append([s['route'],s['model'],f(s['r2']),f(s['mae']),f(s['rmse']),f(s['mape_pct']),str(s['numeric_pass'])])
 conflicts=[[z['endpoint_id'],z['sample_name'],f(z['author_retention_pct'],2),f(z['points'][-1]['retention_pct'],2),'；'.join(z['visual_review']['reasons'])]for z in q if not z['training_eligible_pending_visual_review']]
 (OUT/'冲突与读图限制.md').write_bytes(('# 本轮曲线核验中的限制\n\n'+table(['ID','样品','原作者终值/%','图读终值/%','冻结原因'],conflicts)+'\n\n以上只冻结本轮B曲线，不覆写原数据库标签，也不宣告图一定胜过正文。坐标标定、分辨率、作者图文差异仍可能参与原因。CA-AA早期红色标记与其他系列重叠，未强造早期点。\n\nQSC黑色绝对电容曲线初始高度很小，按自身初始标记归一化后，±3像素界限会扩大到最高约±30个百分点；红、蓝、粉曲线也有约±3～7pp界限。主分析保留这些特征不确定性，另报告≤2pp敏感性；图读界限不是统计置信区间。C(N)归一化仅使用自身最初可见标记，实际基准循环下标仍未知。\n\n616个可见图点来自19条已复核曲线/13个来源，不能称616个独立样品；在20%窗口实际入训2E6/6、3E13/8。不同窗口是独立任务，不互相拆为训练/测试。\n').encode('utf8'))
 notes=[
  '输出始终是指定圈数和条件下的电容保持率。A不需要新材料先做循环实测；B必须先测目标圈数的最多10%或20%，使用场景不同。两/三电极分别训练、验收。',
  'A本轮295次、B本轮144次固定拟合，共439次；没有重复旧计划，没有根据外层得分追加调参。预定B线性主方案未通过，RF是事先列出的探索候选，不能事后改称预定主模型。',
  '查阅55个来源身份的原文资源，核对22条曲线；19条/13来源进入独立的探索输入，3条图文终值争议冻结。20%窗口只有两电极6条/6来源、三电极13条/8来源。616个图点不是616个独立实验。A先使用既有标签完成基准，这3条质量提示也限制A结果的解释；原标签保留，后续需前向复核。',
  f'三电极前20%RF：R²={f(best["r2"],4)}，MAE={f(best["mae"],4)}pp，RMSE={f(best["rmse"],4)}pp，MAPE={f(best["mape_pct"],2)}%。保持率多数接近100%，MAPE小不能单独证明可靠。',
  f'同批简单参照：训练均值MAE={f(mean["mae"])}pp，早期保持率直接沿用到终点MAE={f(persist["mae"])}pp。RF相对后者平均改善{f(100*(1-best["mae"]/persist["mae"]),1)}%，但配对来源重采样MAE差区间[{f(delta[0])},{f(delta[1])}]pp跨0，仍未证明稳定优势。',
  f'只有8个来源，R²来源重采样区间[{f(ci[0])},{f(ci[1])}]很宽；从汇总中去掉木粉炭化来源后R²={f(stress["r2"])}。这不是删除后重训，而是检查结果受某来源影响多大。该区间未包含读图误差，也未消除模型选择影响。',
  f'只看早期读图界限≤2pp的同批预测：9条/7来源，R²={f(sensitivity["r2"])}, MAE={f(sensitivity["mae"])}, RMSE={f(sensitivity["rmse"])}。未重训，也不能代替高质量新测试。',
  '两电极MK9在前段接近平稳，后段出现明显下降：作者终值79.3%，20%RF预测约96.5%。这是早期窗口尚未显示后期拐点的真实困难案例，必须保留。',
  'A/B原始数据覆盖不同，不能把0.246与0.908之差全归因于模型进步。10%/20%共同测试对象比较已另存，但训练来源数量仍不同，也不构成严格窗口因果实验。',
  '验收建议为R²>0.95、MAE≤2pp、RMSE≤3pp、90%绝对误差≤5pp、来源尾部误差≤5pp、相对误差与简单参照同时合格；这些是项目工程目标，不是文献统一标准。另需未参加选择的新来源/批次验证，目前没有。',
  f'独立完成{check["checks"]}项核验：输入/原文/图像/代码哈希、整来源/材料/曲线隔离、早期窗口、训练折预处理和指标复算通过。旧63项保护源、v1.3的46项输出未变；无新增正式循环准入。'
 ]
 nexts=[
  ('优先B三电极早期辅助','这是当前更值得投入的候选方向。先补齐高分辨率原图或作者循环表，降低读图误差，保留相同目标圈数和工况；补更多独立来源及重复实验，而不是加密一条曲线充数。'),
  ('A继续作为无实测基准','固定输入的信息不足问题仍在。可优先同一活化化学/前驱体系列，并补实际孔结构、表面化学与测试条件；改变合同字段或范围时先讨论。窄范围不保证R²提高。'),
  ('后期拐点另设计验证','保留MK9这类难例。后续可讨论允许更长早期窗口、带激活/衰减阶段的模型或异常提示；目前不自行放宽到30%/50%，也不强制所有保持率单调下降。'),
  ('下一轮先登记再训练','RF候选在本轮已被看过分数；若选其继续，先冻结新数据/候选/评价方案，把后续全新来源留作真正测试。现有结果不能再次包装为未见验证。')
 ]
 body='''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>电容保持率：双路线预研结果</title><style>
 *{box-sizing:border-box}body{margin:0;background:#f4f6f3;color:#21392c;font:16px/1.8 "Microsoft YaHei",sans-serif}main{max-width:1120px;margin:30px auto;padding:0 22px 45px}h1{font-size:29px;line-height:1.4}h2{font-size:21px;margin-top:30px}.lead,.note{padding:18px 22px;border-radius:10px;background:#fff1df;border-left:5px solid #a65b2f}.cards{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:20px 0}.card{padding:18px;background:white;border:1px solid #dae4d9;border-radius:10px}.number{display:block;font-size:29px;font-weight:bold;color:#27664d}.table{max-width:100%;overflow:auto;background:white}table{border-collapse:collapse;width:100%;font-size:14px}th,td{padding:10px 12px;border-bottom:1px solid #dce5dc;text-align:left;min-width:64px}th{background:#e4eee4}td:first-child{min-width:225px}figure{margin:18px 0;background:white;padding:16px;border-radius:10px}figure img{display:block;width:100%;max-width:660px;margin:auto}figcaption{font-size:14px;color:#4d6053}a{color:#196348;overflow-wrap:anywhere}.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}.panel{padding:18px;background:white;border-radius:10px}details{margin:20px 0}summary{cursor:pointer;font-weight:bold}.small{font-size:14px;color:#526457}code{overflow-wrap:anywhere}@media(max-width:700px){main{padding:0 14px}.cards,.grid{grid-template-columns:1fr}h1{font-size:24px}}@media print{body{background:white;font-size:10pt}main{max-width:none;margin:0;padding:0}h1{font-size:20pt}.cards{margin:10px 0}.card{padding:8px}.number{font-size:19pt}h2{margin-top:12px}details{display:none}figure{break-inside:avoid}a{color:inherit}.panel{padding:10px}}
 </style></head><body><main><p class="small">2026-10-29 · 已获授权的A/B分别验收 · 有限探索试验</p><h1>电容保持率：两种输入方案，走到了哪一步</h1><p class="lead"><b>还没有模型全面达标。</b>三电极“前20%实测＋随机森林”出现值得继续研究的结果，R²约0.908，平均误差约1.98个百分点；仍低于0.95，只有8个来源，不能称已获得可靠预测模型。</p>'''
 body+='<div class="cards"><div class="card"><span class="number">439次</span>本轮固定拟合，已停止追加</div><div class="card"><span class="number">19条 / 13来源</span>曲线通过本轮证据核验</div><div class="card"><span class="number">0个</span>全面通过精度与泛化要求</div></div><h2>先看实际结果</h2><p>A只用材料和测试条件。B先取得新材料一小段真实循环结果，再预测最终保持率。以下按整个文献来源留出；单位“pp”是保持率的百分点，比如预测95%、实测93%，误差为2pp。</p>'
 body+=table(['输入与模型','记录 / 来源','R²','MAE/pp','RMSE/pp','验收'],comparison)
 body+='<p class="small">B线性主方案在训练前已指定；RF等比较候选也在训练前冻结。当前较好的RF结果仍是探索候选。不同数据覆盖不能直接作A/B因果比较。</p><figure><img src="三电极早期预测散点.svg" alt="三电极前20%实测RF候选预测与作者报告值散点图"><figcaption>13个点代表13条曲线的终点预测，来自8个整组留出的来源。中间虚线表示完全预测正确，旁边两线表示±2pp；图点不是新的独立论文。</figcaption></figure><h2>为什么还不能宣布成功</h2>'
 body+='<div class="grid">'+''.join('<div class="panel">'+esc(x)+'</div>'for x in notes[4:9])+'</div>'
 body+='<p class="note">读图质量也限制了结论。部分低分辨率绝对电容曲线归一化后，早期特征界限达±3～30pp。筛出≤2pp特征读数的同批预测仍未全面过线。3处图文终值争议暂时冻结，原值完整保留。A在新图核验前使用既有标签完成基准，这3条质量提示也限制A结果的解释，后续需前向复核。原始图点、核验规则和留出预测均可追溯。</p><h2>接下来怎样投入更划算</h2><ol>'+''.join('<li><b>'+esc(t)+'：</b>'+esc(x)+'</li>'for t,x in nexts)+'</ol>'
 body+='<p>'+esc(notes[9])+'</p><p class="small">'+esc(notes[10])+'</p><details><summary>展开：所有预定模型的成绩</summary>'+table(['任务','模型','R²','MAE/pp','RMSE/pp','MAPE/%','全数值门槛通过'],fullrows)+'</details><p><a href="A_材料工况直接预测/training_plan.json">A冻结计划</a> · <a href="B_早期实测辅助预测/training_plan.json">B冻结计划</a> · <a href="B_早期实测辅助预测/heldout_predictions.json">B逐条留出预测</a> · <a href="independent_verification.json">独立核验</a> · <a href="冲突与读图限制.md">争议与读图界限</a> · <a href="../小样本方向预研_20261029/保持率固定输入输出/文献与开源方法审查.json">论文与开源学习证据</a></p></main></body></html>'
 (OUT/'双路线保持率预研报告.html').write_bytes(body.encode('utf8'))
 md='# 电容保持率双路线预研\n\n'+''.join('- '+x+'\n'for x in notes)+'\n## 主要结果\n\n|方案|记录/来源|R²|MAE/pp|RMSE/pp|验收|\n|---|---|---|---|---|---|\n'+''.join('| '+' | '.join(row)+' |\n'for row in comparison)+'\n## 建议\n\n'+''.join('- '+t+'：'+x+'\n'for t,x in nexts)+'\n完整表、计划、原图哈希及逐来源预测见同目录HTML/JSON。两路线本轮初步评估完成；高精度模型目标未达成。旧库和旧模型不改。\n'
 (OUT/'README.md').write_bytes(md.encode('utf8'))
 write(OUT/'completion.json',dict(status='both_authorized_scenarios_preliminarily_evaluated',fits_A=295,fits_B=144,new_fits_total=439,failed_fits=0,all_numeric_gate_pass_count=0,prospective_generalization_confirmed=False,high_accuracy_retention_goal_achieved=False,primary_B_model='ridge_early_residual',promising_exploratory_candidate=dict(route='B_3E_early20',model='RF_early_residual',r2=best['r2'],mae_pp=best['mae'],rmse_pp=best['rmse'],rows=13,sources=8),source_curve_QC=dict(scanned_identities=55,reviewed_curves=22,accepted_curves=19,accepted_sources=13,frozen_conflicts=3),verification_checks=check['checks'],next='Improve graph/raw-cycle evidence and add genuinely independent matched sources; preregister next phase, no ongoing fits.'))
 print(json.dumps(dict(report=str(OUT/'双路线保持率预研报告.html'),fits=439,all_pass=0,preliminary_assessment_complete=True,high_accuracy_goal_achieved=False),ensure_ascii=False))
if __name__=='__main__':main()
