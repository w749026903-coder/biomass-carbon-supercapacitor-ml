"""Research progress, including failures and nearby branches; never acceptance spin."""
from pathlib import Path
import html,json
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'保持率达标研究_v3_主线与近优组合_20261030';RUN=OUT/'第一轮_参数与表达'
def read(p):return json.loads(Path(p).read_text('utf8'))
def esc(x):return html.escape(str(x))
def table(headers,rows):return'<div class="table"><table><thead><tr>'+''.join('<th>'+esc(x)+'</th>'for x in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+esc(x)+'</td>'for x in row)+'</tr>'for row in rows)+'</tbody></table></div>'
def main():
 result=read(RUN/'results.json');verification=read(RUN/'independent_verification.json');lookup={(s['route'],s['model']):s for s in result['metrics']};rows=[]
 labels=[('nested_selected','内层统一选模（预定主方法）'),('nested_family::RF_early','RF早期组合'),('nested_family::GPR_early','GPR早期组合'),('nested_family::XGB_early','XGBoost早期组合'),('nested_family::RF_static','RF＋静态特征'),('nested_family::GPR_static','GPR＋静态特征'),('nested_family::XGB_static','XGBoost＋静态特征'),('nested_family::Ridge_early','Ridge早期组合'),('nested_family::ExtraTrees_early','ExtraTrees早期组合'),('near4_equal','四个近优分支等权组合'),('near4_inner_convex','四分支内层权重组合'),('early_persistence','早期保持率直接沿用')]
 for method,name in labels:
  s=lookup[('B_3E_early20',method)];rows.append([name,f'{s["r2"]:.3f}',f'{s["mae"]:.3f}',f'{s["rmse"]:.3f}','未达标'])
 best=max([s for s in result['metrics']if s['route']=='B_3E_early20'and s['model'].startswith('fixed::')],key=lambda s:s['r2'])
 phase2=OUT/'第二轮_证据与曲线扩充';new=read(phase2/'new_curve_reviewed.json')if(phase2/'new_curve_reviewed.json').exists()else[]
 notes=[
 '持续研究目标保持active：R²>0.95、MAE≤2pp、RMSE≤3pp、尾部/简单基线与来源泛化共同通过。用户明确以早期循环辅助为主线，同时保留其他近优组合和材料/工况直接预测。',
 '第一轮已按冻结计划完成6324次基础模型拟合、20次内层组合权重拟合；72个B候选和12个A对照，无失败。没有追加本轮候选、修改真实终值或删除难例。',
 '同一条13曲线/8来源主数据上，内层选择后的主要结果如下。每个外层来源的模型选择只用其他来源内部的验证；当前来源此前均已参与项目开发，因此仍属探索。',
 f'事后查看全部固定候选，最高R²为{best["r2"]:.6f}、MAE{best["mae"]:.6f}pp、RMSE{best["rmse"]:.6f}pp，来自{best["model"]}。它仍未达到0.95，也不能替换预定主方法或称新独立验证。',
 '近优候选值得保留，但更大的选模池和组合没有自动改善泛化。外层结果表明，在目前少量来源上，内层排名也不稳定；后续必须增加可核验信息，而非继续围绕本轮外层成绩扩参数。',
 '材料/工况直接预测A已保留两/三电极各12个新对照，不因B一次较高分弃用；当前仍无A候选全面过线。两电极B和10%窗口也有独立结果，不能混到三电极20%成绩里。',
 f'已有PDF继续挖掘：已从YZPC-3、KAC-5、RMAC-800正文原嵌入图提取{len(new)}条实际循环曲线，终点与作者值在读图界限内一致。20%三电极研究输入可扩到16条/11来源，10%为10条/9来源；尚未进行第二轮拟合。它们是旧端点的新早期曲线信息，不是真正全新外部来源。',
 '三个新图读保持率界限约±0.52、±0.63、±1.61pp；不借未来终值校准早期曲线。旧3条图文争议继续冻结；旧QSC绝对电容图的较大不确定性也保留。20来源已有PDF队列还剩17来源待实际图核验。',
 f'本阶段独立检查{verification["checks"]}项，203份保护哈希一致，所有外层指标另算通过。审计限制：冻结程序未保存逐条内层预测，内层排名核对的是已存分数表、划分成员和代码，未另算每一项内层误差；下一阶段应补存。核验没有模型拟合。'
 ]
 body='''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>保持率持续达标研究：当前进度</title><style>*{box-sizing:border-box}body{background:#f4f6f5;color:#20392e;font:16px/1.8 "Microsoft YaHei",sans-serif;margin:0}main{max-width:1080px;margin:32px auto;padding:0 20px 40px}h1{font-size:28px;line-height:1.4}h2{font-size:21px}.status{padding:18px;background:#fff0de;border-left:5px solid #9a5b30}.cards{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:20px 0}.card{background:white;padding:16px;border:1px solid #dae4df}.number{font-size:26px;display:block;font-weight:bold;color:#28654d}.table{overflow:auto;background:white}table{border-collapse:collapse;width:100%;font-size:14px}td,th{padding:9px 12px;text-align:left;min-width:80px;border-bottom:1px solid #e0e7e2}td:first-child{min-width:225px}th{background:#e3eee7}.small{font-size:14px;color:#53665b}a{color:#176344;overflow-wrap:anywhere}.box{background:white;padding:18px;margin:16px 0}details{margin:18px 0}summary{cursor:pointer}@media(max-width:650px){.cards{grid-template-columns:1fr}h1{font-size:23px}}</style></head><body><main><p class="small">2026-10-30 · 主线推进，保留多个竞争组合</p><h1>保持率持续达标研究：第一轮结果与下一步</h1><p class="status"><b>目标继续active，目前没有全面达标模型。</b>参数和表达调整已完成一轮有限检验；RF、GPR、XGBoost及静态特征组合均保留。下一阶段先补原文曲线证据，再冻结新试验。</p><div class="cards"><div class="card"><span class="number">6324＋20</span>基础模型拟合＋内层权重拟合</div><div class="card"><span class="number">72＋12</span>B主线候选＋A直接预测对照</div><div class="card"><span class="number">0个</span>模型全面达标</div></div>'''
 body+='<p>'+esc(notes[2])+'</p>'+table(['三电极20%方案','R²','MAE/pp','RMSE/pp','验收'],rows)+'<p class="small">各算法家族均在内层选择自己的参数，未按外层最高分改称主方法。pp为保持率百分点。</p><div class="box">'+esc(notes[3])+'</div><p>'+esc(notes[4])+'</p><h2>数据补充已开始</h2><p>'+esc(notes[6])+'</p><p>'+esc(notes[7])+'</p><h2>接下来怎样继续</h2><ol><li>继续完成已有20来源PDF队列，逐篇核循环图、条件和样品；新曲线立即进入单独可调用的研究增量，不夸大独立样本数。</li><li>改善高误差读图和未决图文证据，优先增加可识别的循环信息；不因某论文难预测而删除。</li><li>冻结下一批数据与少量有依据的竞争组合；保留原输入和代数表达对照、各家族及A路线，补存逐条内层预测。</li><li>真正的新来源单独留作外部验证。数值过线、阶段完成与持续目标完成分别判断。</li></ol><p class="small">'+esc(notes[8])+'</p><p><a href="research_goal.json">持续目标</a> · <a href="第一轮_参数与表达/training_plan.json">冻结计划</a> · <a href="第一轮_参数与表达/results.json">全部结果</a> · <a href="第一轮_参数与表达/independent_verification.json">独立核验与限制</a> · <a href="第二轮_证据与曲线扩充/new_curve_reviewed.json">新曲线增量</a> · <a href="第二轮_证据与曲线扩充/existing_pdf_queue.json">已有PDF队列</a></p></main></body></html>'
 (OUT/'研究进度.html').write_bytes(body.encode('utf8'))
 (RUN/'阶段结论.md').write_bytes(('# 第一轮阶段结论：目标仍active\n\n'+''.join('- '+n+'\n'for n in notes)).encode('utf8'))
 print('Progress report saved. No new fits; goal active.')
if __name__=='__main__':main()
