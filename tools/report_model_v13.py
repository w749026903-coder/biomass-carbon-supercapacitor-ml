"""Create a two-page plain-language brief and auditable training dashboard."""
from pathlib import Path
import base64,collections,csv,html,json,sqlite3,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.prepare_model_v13 import RUN,read,write,sha
BRIEF=ROOT/'项目进展简报_训练后_20261029'

def chart(rows,path,progress=False):
    from reportlab.graphics.shapes import Drawing,String
    from reportlab.graphics.charts.lineplots import LinePlot
    from reportlab.graphics.widgets.markers import makeMarker
    from reportlab.graphics import renderSVG
    from reportlab.lib import colors
    d=Drawing(620,340);p=LinePlot();p.x=68;p.y=54;p.width=510;p.height=230
    if progress:
        p.data=[[(x['elapsed_seconds'],x['completed'])for x in rows]];p.joinedLines=1;p.lines[0].strokeColor=colors.HexColor('#1f685b');p.lines[0].strokeWidth=1.5
        xlabel='Elapsed time (seconds)';ylabel='Completed estimator fits';p.yValueAxis.valueMin=0;p.yValueAxis.valueMax=508
    else:
        p.data=[[(x['observed'],x['predicted'])for x in rows]];p.joinedLines=0;p.lines[0].symbol=makeMarker('FilledCircle');p.lines[0].symbol.size=4;p.lines[0].symbol.fillColor=colors.HexColor('#236c60');p.lines[0].symbol.strokeColor=colors.HexColor('#236c60')
        p.xValueAxis.valueMin=60;p.xValueAxis.valueMax=112;p.yValueAxis.valueMin=60;p.yValueAxis.valueMax=112
        xlabel='Observed retention (%)';ylabel='Source-held-out prediction (%)'
    p.xValueAxis.labels.fontSize=9;p.yValueAxis.labels.fontSize=9;d.add(p)
    d.add(String(310,18,xlabel,textAnchor='middle',fontName='Helvetica',fontSize=11));d.add(String(68,309,ylabel,fontName='Helvetica',fontSize=11))
    renderSVG.drawToFile(d,str(path))

def table(headers,rows):
    return '<table><thead><tr>'+''.join('<th>'+html.escape(str(v))+'</th>'for v in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+html.escape(str(v))+'</td>'for v in row)+'</tr>'for row in rows)+'</tbody></table>'

def main():
    BRIEF.mkdir(exist_ok=True);(RUN/'figures').mkdir(exist_ok=True)
    result=read(RUN/'results.json');data=read(RUN/'input_snapshot.json');metrics=result['metrics'];p=metrics['latest_assisted_ridge'];util=read(RUN/'actual_fact_utilization.json')
    out=read(RUN/'outer_predictions.json');state=read(RUN/'progress.json');audit=read(RUN/'input_audit.json');old=read(ROOT/'模型v1.2_来源隔离再训练_20261028/results.json')
    inv=read(ROOT/'项目进展报告_20261029/统计核验.json');assert inv['literature_inventory']['identity_entries_with_primary_content']==420
    c=sqlite3.connect((RUN/'evaluation.sqlite').as_uri()+'?mode=ro',uri=True);jobs={k:json.loads(v)for k,v in c.execute('select *from fits')};c.close()
    finalkeys=['main/refit/latest_assisted_ridge','main/refit/helper/capacity','main/refit/helper/BET'];finalfacts=set().union(*(set(jobs[k]['actual_fact_ids'])for k in finalkeys))
    analysis=dict(actual_experiment_unique_facts=len(util['fact_ids']),actual_final_assisted_system_unique_facts=len(finalfacts),
                  experiment_facts_appended_after_v26=sum(i>4670 for i in util['fact_ids']),final_system_facts_appended_after_v26=sum(i>4670 for i in finalfacts),
                  experiment_source_family_union=len({r['source_family']for k,rs in data.items()if k!='legacy'for r in rs}),
                  main_final_enabled_fields=sum(x['enabled']for x in jobs['main/refit/latest_assisted_ridge']['schema']),
                  main_final_actual_nonempty_source_features=30,generated_auxiliary_features=2,
                  input_cell_comparison='325 canonical nonempty cells vs old50-field snapshot includes already-existing previously omitted library fields; not325 newly measured parameters.',
                  warnings=sum(bool(x['warnings'])for x in jobs.values()),dataset_remediation_pending='Four pre-existing same-adsorption area ratios masked in this training projection; next database version must forward-correct task measurement-block rules.',
                  old_report_stats_sha256=sha(ROOT/'项目进展报告_20261029/统计核验.json'))
    write(RUN/'postrun_analysis.json',analysis)
    chart(out['latest_assisted_ridge'],RUN/'figures/source_holdout.svg');chart(state['events'],RUN/'figures/actual_progress.svg',True)
    with (RUN/'outer_predictions.csv').open('w',encoding='utf-8-sig',newline='')as f:
        w=csv.writer(f);w.writerow(['recipe','row_id','source_family','observed','predicted'])
        for recipe in ['legacy_input_ridge','latest_ridge','latest_trees','latest_assisted_ridge','capacity','BET']:
            for r in out[recipe]:w.writerow([recipe,r['row_id'],r['source_family'],r['observed'],r['predicted']])
    css='''*{box-sizing:border-box}body{margin:0;background:#eef1ed;color:#21332c;font:16px/1.8 "Microsoft YaHei",sans-serif}main{max-width:980px;margin:24px auto;background:white;padding:38px 48px}h1{font-size:29px;line-height:1.45}h2{font-size:21px;color:#205a4a;margin:24px 0 10px}p{margin:12px 0}table{border-collapse:collapse;width:100%;font-size:14px;line-height:1.65;margin:16px 0}th,td{text-align:left;vertical-align:top;padding:9px;border-bottom:1px solid #d6e0d8}th{background:#e7f0e9}.muted{color:#5c7066;font-size:13px}.lead{border-left:4px solid #2a6b54;padding-left:15px;font-size:18px}a{color:#14678d;overflow-wrap:anywhere}nav{display:flex;gap:14px;flex-wrap:wrap}figure{margin:20px 0}img{max-width:100%}details{margin:20px 0}button{font:inherit;padding:6px 12px;border:0;color:white;background:#235f4c;cursor:pointer}@media(max-width:650px){main{padding:22px 16px;margin:0}h1{font-size:24px}table{font-size:12px}th,td{padding:6px 4px}}@media print{@page{size:A4;margin:15mm 15mm}body{font-size:10.5pt;line-height:1.72;background:white}main{margin:0;padding:0;max-width:none}h1{font-size:21pt;margin:4px 0 16px}h2{font-size:14pt;break-after:avoid;margin:16px 0 8px}p{margin:9px 0;orphans:3;widows:3}table{font-size:9.5pt;margin:10px 0}th,td{padding:7px}tr{break-inside:avoid}nav{display:none}.lead{font-size:12pt}.page2{break-before:page}.muted{font-size:9pt}a{color:inherit;text-decoration:none}}'''
    rows=[['只猜训练来源均值',metrics['mean_baseline']['mae'],metrics['mean_baseline']['rmse'],metrics['mean_baseline']['r2']],
          ['上次模型v1.2（历史方案）',old['metrics'][0]['mae'],old['metrics'][0]['rmse'],old['metrics'][0]['r2']],
          ['本轮同一配方＋旧输入',metrics['legacy_input_ridge']['mae'],metrics['legacy_input_ridge']['rmse'],metrics['legacy_input_ridge']['r2']],
          ['本轮新参数',metrics['latest_ridge']['mae'],metrics['latest_ridge']['rmse'],metrics['latest_ridge']['r2']],
          ['本轮新参数＋树模型',metrics['latest_trees']['mae'],metrics['latest_trees']['rmse'],metrics['latest_trees']['r2']],
          ['本轮新参数＋辅助学习（预定主方案）',p['mae'],p['rmse'],p['r2']]]
    rows=[[r[0]]+[f'{v:.4f}'for v in r[1:]]for r in rows]
    page1='''<section><p class="muted">2026年10月29日 · 已完成本轮训练 · 数据v7 / 模型v1.3</p><h1>项目进展简报：让新数据真正参与训练</h1>
<p class="lead">新数据已经进入模型，预测有小幅改善；目前仍是研究原型，尚不能可靠指导材料配方。</p>
<h2>1．我们手里有多少资料和数据？</h2>
<p>现有索引中，<b>420条文献条目能定位正文</b>，约400篇规模；正文PDF与XML重复格式已按身份关联处理。这个口径沿用上份已核验索引，包含背景和其他体系，尚未全部精读提取。</p>
<p>材料、制备事实库有<b>5,197项数值</b>，其中<b>3,727项已接入可调用训练输入，接入率71.71%</b>。这里的一项数值可能是一个孔容、温度或组分比例，不能当成一条独立寿命实验。</p>
<h2>2．这次实际训练用了什么？</h2>'''
    page1+=table(['训练任务','实际任务行数','来源组数','怎样使用'],[
        ['循环保持率','47','34','主任务：预测指定条件、圈数下的保持率'],['三电极比电容','434','35','辅助任务：229条普通记录＋205条有界读图条件'],['BET比表面积','266','51','辅助任务：学习材料孔结构信息']])
    page1+='''<p>上述747行是三个任务的合计，同一论文和材料会跨任务出现，不能说成747个独立实验。跨任务合并后涉及74个来源组，包含既有循环来源。</p>
<p><b>本轮实验实际用到1,147项材料／制备数值</b>，其中174项来自文献v26之后的追加批次；最终保存的主方案及其辅助模型涉及1,072项。其余数据按不同体系、阶段、用途或稀疏程度保留，没有硬塞进同一个预测器。</p>
<p>做法是先让辅助模型学习电容和孔结构，再把它们对未见来源的预测作为两个参考特征，帮助预测循环保持率。不会把电容值冒充寿命标签；同篇论文在主任务和所有辅助任务中一起留出。</p>
<p class="muted">本轮共508次拟合，方案在训练前冻结。读图值保留误差范围，并在同来源内降权。4条可能泄漏BET测量信息的面积比已在训练投影中屏蔽，原值保留。未封版v8未使用。</p></section>'''
    page2='<section class="page2"><h2>3．训练结果有没有变好？</h2>'+table(['方案','MAE／百分点','RMSE／百分点','R²'],rows)
    page2+='''<p><b>主方案平均偏差约4.92个百分点。</b>例如实测保持率90%、预测95%，就是偏了5个百分点。RMSE为6.74，对少数严重预测错误更敏感；R²为0.1386，刻画样品之间差异的能力仍弱，不能读成“准确率13.86%”。</p>
<p>与上次公开结果相比，MAE从5.1509降至4.9249，R²从0.0955升至0.1386。上次方案与本轮不同，因此另设了“同一配方＋旧输入”对照：其MAE为5.0454，新参数为5.0134，加辅助学习后为4.9249。说明这批数据有改善迹象，但幅度不大。</p>
<p><b>可靠性门槛仍未通过。</b>主方案相对直接猜均值，MAE平均改善0.2240个百分点；描述性95%差值范围为−0.7540至＋0.2996，仍包含“没有改善”。本轮预定方案没有因看到外层成绩而继续调参，也没有全新的外部测试。</p>
<p>辅助任务同样不强：比电容留出R²为0.0887，BET为−0.0435。更复杂的树模型在保持率任务上反而较差。这表明不能只靠换模型或增加同篇论文的图点解决问题。</p>
<h2>4．下一步先做什么？</h2>
<p><b>先把已有论文用深。</b>继续剩余22条主记录的材料关联，优先补齐孔结构、组成、负载和制备参数；逐项核读表格、曲线及补充材料。原37条待补证记录只在找到原始依据后处理，确实未报告的保留未知。</p>
<p><b>再补独立来源和困难情况。</b>同一论文再提取很多点，不能替代新的独立来源。优先关注明显衰减、循环活化增长及关键条件完整的研究，保留未参与选模的新来源或真实实验检验。</p>
<p><b>下一轮以可验证收益为准。</b>先修正本次发现的测量块屏蔽缺口，再围绕覆盖足够的关键特征设计有限实验；同时报告均值参照和逐来源误差，不为追分删除困难记录。</p>
<p class="muted">依据：v7封版输入、v1.3冻结方案、逐次拟合回执与逐来源预测；指标由保存的留出预测另行复算。本次核验通过，未新增循环准入。较早六页报告保留为历史；当前报告为训练后的两页简报。</p></section>'''
    title='项目进展简报：新数据训练后'
    nav='<nav><button onclick="window.print()">打印 / 保存PDF</button><a href="项目进展简报.pdf">下载两页PDF</a><a href="../'+RUN.name+'/训练结果.html">完整训练结果与依据</a></nav>'
    document='<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+title+'</title><style>'+css+'</style></head><body><main>'+nav+page1+page2+'</main></body></html>'
    (BRIEF/'项目进展简报.html').write_text(document,'utf8')
    # Plain text counterpart preserves all prose and table contents without layout dependencies.
    from html.parser import HTMLParser
    class Plain(HTMLParser):
        def __init__(self):super().__init__();self.parts=[]
        def handle_data(self,s):self.parts.append(s)
        def handle_starttag(self,tag,attrs):
            if tag in ['p','h1','h2','tr']:self.parts.append('\n\n')
            if tag in ['td','th']:self.parts.append(' | ')
    parser=Plain();parser.feed(page1+page2);(BRIEF/'项目进展简报.txt').write_text(''.join(parser.parts).strip()+'\n','utf8')
    image=lambda name:'<img alt="'+name+'" src="figures/'+name+'.svg">'
    dashboard='<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>模型v1.3实际训练结果</title><style>'+css+'</style><main><h1>模型v1.3：新参数与辅助数据已实际训练</h1><p>已完成508/508次拟合；预定主方案MAE4.9249、RMSE6.7422、R²0.1386，可靠性门槛未过。1,147项材料数值有实际拟合回执；不是3,727项全部被模型使用。</p>'+table(['方案','MAE','RMSE','R²'],rows)+image('source_holdout')+'<p>按来源留出。保持率可真实高于100%，没有统一截断。</p>'+image('actual_progress')+'<p>进度来自每一次完成拟合后的持久回执，共508次、约52秒；不是模拟进度。</p><details><summary>辅助任务与使用量</summary>'+table(['任务','MAE','RMSE','R²'],[[name]+[f"{metrics[name]['model'][k]:.4f}"for k in ['mae','rmse','r2']]for name in ['capacity','BET']])+'<p>最终辅助系统使用1,072项材料数值；整个实验去重1,147项，跨任务不可相加。74来源组含原循环来源，不是本轮新增74篇论文。</p></details><h2>记录与复现</h2><p>'+''.join('<a href="'+name+'">'+name+'</a>　'for name in ['training_plan.json','input_audit.json','training_projection_masks.json','results.json','actual_fact_utilization.json','outer_predictions.csv','verification.json','README.md'])+'</p><p><a href="../'+BRIEF.name+'/项目进展简报.html">两页白话报告</a></p></main></html>'
    (RUN/'训练结果.html').write_text(dashboard,'utf8')
    readme='''# 模型v1.3：实际使用v7新数据与辅助任务

本轮用户授权先利用新数据训练，再生成短报告。508次固定拟合已经完成，预定主方案不是事后挑选的外层最高分方案。保持率47条/34来源，MAE4.924935、RMSE6.742200、R²0.138594；对均值差值描述性范围[-.754045,.299570]，预设门槛未过，不能可靠指导设计。比电容434/35、BET266/51已真实拟合并产生跨来源辅助表示；各自R².088703/-.043532，不能误称可靠子模型。

全部747任务行的最终研究重拟合不是747独立样本。实验涉及74来源组（含旧循环来源），1,147唯一材料事实有实际拟合回执，其中174在原v26事实序号4670之后；最终主系统1,072事实（139后追加）。既有3,727接入与5,197数值分母保持，不说全部参与拟合。旧、新输入用相同新编码配方作固定对照，不把历史v1.2嵌套选模差值全归因数据。原始数组、配方、每次训练成员、来源排除、列筛选/插补/标准化、辅助交叉拟合赋值及fact_id去向完整保存。

主方案的两个辅助预测在主训练集内部三折整来源交叉生成；外层与查询来源的所有辅助数据均排除。数值至少3个训练来源，主集20%/辅助10%覆盖，类别词表也只训练内生成。读图205条相对普通229条在同来源中赋0.5权重（启发式，不是实验方差），各来源总权重1。正值log目标不裁100%；未用v8，不改原37/原冻结/旧模型/数据库。

BET视图发现4个micro_to_meso_surface_area_ratio__v2来自同吸附测量；在任何拟合前记录训练投影掩码。旧v7保留，后续数据库版本应前向修正规则。325个规范输入新增单元相对旧50列快照，包含原来已提取但未投影的字段，不说325个本轮新测量。

不要重跑prepare/train。已有项目环境运行tools/verify_model_v13.py只读检查，无估计器拟合。默认研究权重latest_assisted_ridge.joblib包含最终主模型与capacity/BET辅助模型，joblib加载需本仓库models.v1_3.model可导入。输入结构见inference_example.json；用AssistedModel.predict(rows)返回百分数，比例需÷100。这些示例是重拟合预测，不是留出验证。其它五份权重只作为本轮固定对照/辅助任务保留。

入口为训练结果.html；最终报告在../项目进展简报_训练后_20261029/项目进展简报.pdf。frozen_run_hashes.json和merge_manifest.json锁定实验与交付，进度文件记录实际完成事件。上次六页报告保持历史，不覆盖。本轮新全局依赖/系统更改0，正式部署0。
'''
    (RUN/'README.md').write_text(readme,'utf8')
    write(BRIEF/'报告数据依据.json',dict(training_directory=RUN.name,training_result_sha256=sha(RUN/'results.json'),plan_sha256=sha(RUN/'training_plan.json'),verification_sha256=sha(RUN/'verification.json'),model_fits=508,short_report_target_pages=2,old_corpus_inventory_sha256=analysis['old_report_stats_sha256'],database_version='v7',new_training_use_facts=1147,final_system_use_facts=1072))
    print(json.dumps(dict(report=str(BRIEF),training=str(RUN),analysis=analysis),ensure_ascii=False))
if __name__=='__main__':main()
