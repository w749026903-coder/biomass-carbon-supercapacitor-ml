"""Standalone local training report and ReportLab scientific SVG plots."""
from pathlib import Path
import csv,html,io,json,math,sys
ROOT=Path(__file__).resolve().parents[1];RUN=ROOT/'模型v1.2_来源隔离再训练_20261028'
def read(name):return json.loads((RUN/name).read_text('utf8'))

def figures(predictions,progress,coverage):
    from reportlab.graphics.shapes import Drawing,String,Line,Rect
    from reportlab.graphics.charts.lineplots import LinePlot
    from reportlab.graphics.widgets.markers import makeMarker
    from reportlab.graphics import renderSVG
    from reportlab.lib import colors
    folder=RUN/'figures';folder.mkdir(exist_ok=True)
    def save(d,name):renderSVG.drawToFile(d,str(folder/(name+'.svg')))
    def plot(data,xlabel,ylabel,bounds,size=(640,390)):
        d=Drawing(*size);p=LinePlot();p.x=65;p.y=50;p.width=size[0]-95;p.height=size[1]-80;p.data=data
        p.xValueAxis.valueMin,p.xValueAxis.valueMax,p.yValueAxis.valueMin,p.yValueAxis.valueMax=bounds
        p.xValueAxis.visibleGrid=p.yValueAxis.visibleGrid=True;p.xValueAxis.gridStrokeColor=p.yValueAxis.gridStrokeColor=colors.HexColor('#dfe6ee')
        d.add(p);d.add(String(size[0]/2,12,xlabel,textAnchor='middle',fontSize=11));d.add(String(8,size[1]-12,ylabel,fontSize=10))
        return d,p
    ys=[p['observed_pct'] for p in predictions];ps=[p['predicted_pct'] for p in predictions]
    lo=5*math.floor((min(ys+ps)-3)/5);hi=5*math.ceil((max(ys+ps)+3)/5)
    d,p=plot([list(zip(ys,ps)),[(lo,lo),(hi,hi)]],'Observed retention (%)','Source-held-out prediction (%)',(lo,hi,lo,hi))
    p.lines[0].strokeColor=None;p.lines[0].symbol=makeMarker('FilledCircle');p.lines[0].symbol.size=5;p.lines[0].symbol.fillColor=colors.HexColor('#176c9c')
    p.lines[1].strokeColor=colors.HexColor('#a8b5c6');p.lines[1].strokeDashArray=[4,3];save(d,'heldout_predictions')
    grouped={}
    for r in predictions:grouped.setdefault(r['source_group'],[]).append(r)
    ranking=[]
    for group,rs in grouped.items():ranking.append(dict(source_group=group,rows=len(rs),mae=sum(abs(r['error_pct'])for r in rs)/len(rs),mean_baseline_mae=sum(abs(r['source_mean_pct']-r['observed_pct'])for r in rs)/len(rs)))
    ranking.sort(key=lambda r:-r['mae'])
    d=Drawing(690,410);maxv=max(r['mae'] for r in ranking)*1.08
    for i,r in enumerate(ranking[:12]):
        y=365-i*27;label=r['source_group'].removeprefix('doi:');d.add(String(245,y+2,label,textAnchor='end',fontSize=8.3))
        width=r['mae']/maxv*365;d.add(Rect(255,y,width,14,fillColor=colors.HexColor('#d27843'),strokeColor=None));d.add(String(261+width,y+2,f"{r['mae']:.2f}",fontSize=9))
    d.add(String(350,20,'Worst 12 held-out source families: MAE (percentage points)',textAnchor='middle',fontSize=11));save(d,'source_errors')
    fields=['BET_m2_g','total_pore_volume_cm3_g','micropore_volume_cm3_g','Raman_ID_IG','XPS_N_atomic_pct_v15','XPS_O_atomic_pct_v15','activation_temperature_C','activation_duration_h','carbonization_temperature_C','precarbonization_temperature_C','mass_loading_mg_cm2']
    d=Drawing(690,390)
    for i,f in enumerate(fields):
        y=350-i*27;count=coverage[f]['rows'];families=coverage[f]['families'];d.add(String(255,y+2,f,textAnchor='end',fontSize=8.4));d.add(Rect(265,y,count/47*300,14,fillColor=colors.HexColor('#368a89'),strokeColor=None));d.add(String(273+count/47*300,y+2,f'{count}/47; {families} families',fontSize=8.5))
    d.add(String(350,15,'Observed feature coverage before fold-specific preprocessing',textAnchor='middle',fontSize=11));save(d,'feature_coverage')
    data=[(0,0)]+[(r['seconds'],r['fits'])for r in progress['events']];duration=max(x for x,y in data)
    d,p=plot([data],'Elapsed seconds','Actual estimator fits',(0,max(1,duration),0,560));p.lines[0].strokeColor=colors.HexColor('#176c9c');save(d,'actual_training_progress')
    return ranking

TEMPLATE='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>模型v1.2｜来源隔离训练</title>
<style>body{margin:0;background:#f4f6f8;color:#203044;font:15px/1.65 "Microsoft YaHei",sans-serif}main{max-width:1220px;margin:32px auto;padding:0 24px}h1{font-size:31px;margin:6px 0}h2{font-size:21px;margin:0 0 12px}.sub{color:#5c6c7d}section,.card{background:white;border:1px solid #dfe5ec;border-radius:12px;padding:22px;margin:18px 0}.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}.card{margin:0}.big{font-size:28px;font-weight:bold}.plotgrid{display:grid;grid-template-columns:1fr 1fr;gap:18px}.plotgrid section{margin:0}.plotgrid img{width:100%;height:auto}progress{width:100%;height:17px;accent-color:#176c9c}table{width:100%;border-collapse:collapse;font-size:13px}th,td{border-bottom:1px solid #e2e7ed;padding:10px;text-align:right}th:first-child,td:first-child{text-align:left}th{background:#f4f7fa}a{color:#176c9c}.badge{display:inline-block;padding:3px 11px;background:#e9f1f5;border-radius:5px}.warn{background:#fff1e7;border-left:4px solid #ca763f;padding:15px}.scroll{overflow:auto;max-height:590px}input,select{padding:8px;margin:4px;border:1px solid #b9c6d3;border-radius:5px}small{color:#607184}#qualifier{font-size:14px}footer{margin:24px 0;color:#5c6c7d}@media(max-width:760px){main{margin:16px auto;padding:0 12px}.grid{grid-template-columns:1fr 1fr}.plotgrid{grid-template-columns:1fr}h1{font-size:25px}section{padding:15px}}
</style><main><div class="badge">生物质衍生多孔碳 · 三电极 GCD</div><h1>模型v1.2：来源隔离训练</h1><p class="sub">47条已准入测试 · 34个来源组 · 当前已封版数据库v0.29／文献v26</p>
<div class="grid"><div class="card"><div class="sub">实际拟合</div><div class="big" id="fits">0 / 560</div></div><div class="card"><div class="sub">外层来源评估</div><div class="big" id="folds">0 / 34</div></div><div class="card"><div class="sub">模型 MAE · 百分点</div><div class="big" id="mae">—</div></div><div class="card"><div class="sub">均值参照 MAE</div><div class="big" id="base">—</div></div></div>
<section><h2 id="state">已冻结方案，等待训练</h2><progress id="progress" max="560" value="0"></progress><p id="detail" class="sub"></p><div class="warn" id="verdict">结果尚未产生；不提前宣称模型有效。</div><p id="qualifier">这是既有来源上的探索性来源隔离验证。外层每次留出一整个来源组，所有处理和选模仅使用训练来源。真实保持率允许超过100%；95%来源重采样范围不是单样品预测区间。</p></section>
<section><h2>同一数据、同一留出方式的对照</h2><div class="scroll"><table><thead><tr><th>方案</th><th>MAE／百分点</th><th>RMSE／百分点</th><th>R²</th><th>相对均值 ΔMAE</th></tr></thead><tbody id="metrics"></tbody></table></div><p class="sub" id="recipe"></p><p><a href="training_plan.json">冻结计划</a> · <a href="results.json">结果数据</a> · <a href="outer_predictions.csv">逐记录预测</a> · <a href="source_errors.csv">逐来源误差</a> · <a href="README.md">完整说明</a></p></section>
<div class="plotgrid" id="plots" hidden><section><h2>来源留出预测</h2><img id="scatter" alt="实测保持率与来源留出预测；灰线为理想一致线"><small>每个点均来自未参与该折拟合的来源，不能作为全量重训权重的独立测试。</small></section><section><h2>误差最大的来源</h2><img id="errors" alt="12个误差最大来源的MAE"><small>保留困难来源，不因误差高删除记录。</small></section><section><h2>原文特征覆盖</h2><img id="coverage" alt="关键特征的实测覆盖数和独立来源数"><small>共50项候选输入；每折按来源支持筛选。缺失值填补不会增加真实证据覆盖。</small></section><section><h2>真实训练进度</h2><img id="timeline" alt="实际拟合次数随真实运行时间变化"><small>来自每次拟合提交后的计数和时间，不是模拟进度。</small></section></div>
<section><h2>逐记录预测与误差</h2><p><input id="search" placeholder="检索样品或 DOI" aria-label="检索样品或DOI"><select id="sort" aria-label="排序"><option value="error">按绝对误差降序</option><option value="observed">按真实保持率升序</option></select></p><div class="scroll"><table><thead><tr><th>样品／来源</th><th>真实 %</th><th>预测 %／比例</th><th>误差／百分点</th><th>均值参照 %</th></tr></thead><tbody id="records"></tbody></table></div><p id="rowcount" class="sub"></p></section>
<section><h2>适用边界</h2><p>本轮使用已审查三电极报告工况。双电极31条单列，未混入；未封版批次27、待证记录与冻结字段未放宽准入。孔结构、方法限定XPS与分阶段制备参与有限候选比较；比电容、同次CE和循环响应不作为预试验材料特征。</p><p>保存的权重在全部47条上重训，用于研究调用，没有新的独立外部检验。旧v1.1的42条／30来源与本轮数据集合不同，两个MAE不能直接相减解释为进步。当前仍不提供可靠工程设计值或校准预测区间。</p></section><footer>本地独立实验报告 · 没有覆盖旧数据库与历史模型 · 交互页与静态SVG均可保存查看</footer></main>
<script>const embedded=__DATA__;let D=embedded;const $=x=>document.getElementById(x);const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));const fmt=x=>x==null?'—':Number(x).toFixed(3);const names={nested:'内层选模＋外层来源留出',source_mean:'训练来源等权均值',source_median:'训练来源等权中位数'};
function records(){let rs=(D.predictions||[]).filter(r=>(r.sample_name+' '+r.source_group).toLowerCase().includes($('search').value.toLowerCase()));rs.sort($('sort').value==='observed'?(a,b)=>a.observed_pct-b.observed_pct:(a,b)=>Math.abs(b.error_pct)-Math.abs(a.error_pct));$('records').innerHTML=rs.map(r=>`<tr><td>${esc(r.sample_name)}<br><small>${esc(r.source_group)}</small></td><td>${r.observed_pct.toFixed(2)}</td><td>${r.predicted_pct.toFixed(2)}%<br><small>${r.predicted_ratio.toFixed(4)}</small></td><td>${r.error_pct.toFixed(2)}</td><td>${r.source_mean_pct.toFixed(2)}</td></tr>`).join('');$('rowcount').textContent=`当前显示 ${rs.length} / ${(D.predictions||[]).length} 条`}
function render(){const p=D.progress||{};const result=D.result;$('fits').textContent=`${p.actual_estimator_fits||0} / 560`;$('folds').textContent=`${p.completed_outer_sources||0} / 34`;$('progress').value=p.completed||0;$('state').textContent=({planned:'方案已冻结，等待训练',running:'正在执行来源隔离训练',completed:'本次训练已完成',failed:'训练中止，保留现场'})[p.status]||'读取进度';$('detail').textContent=`实际运行 ${p.elapsed_seconds||0} 秒`+(p.active?' · '+p.active.stage+' · '+p.active.candidate:'');if(result){let m=result.metrics[0],b=result.metrics[1];$('mae').textContent=fmt(m.mae);$('base').textContent=fmt(b.mae);$('verdict').textContent=result.descriptive_acceptance_passed?'本轮描述性门槛通过；仍需新的独立来源验证。':m.mae<b.mae?'本轮MAE低于均值，但没有通过全部预设性能门槛。':'本轮没有超过均值参照；尚未证明可可靠预测。';$('metrics').innerHTML=result.metrics.map(x=>`<tr><td>${names[x.variant]}</td><td>${fmt(x.mae)}</td><td>${fmt(x.rmse)}</td><td>${fmt(x.r2)}</td><td>${fmt(x.vs_mean.delta_mae)}</td></tr>`).join('');$('recipe').textContent='全量研究权重配方：'+result.final_candidate+'。误差为来源等权；均为已用来源上的探索性结果。';if(D.figuresReady){$('plots').hidden=false;for(let [id,name]of[['scatter','heldout_predictions'],['errors','source_errors'],['coverage','feature_coverage'],['timeline','actual_training_progress']])if(!$(id).getAttribute('src'))$(id).src='figures/'+name+'.svg';}}records()}
$('search').addEventListener('input',records);$('sort').addEventListener('change',records);render();async function poll(){if(location.protocol==='file:')return;try{const p=await fetch('progress.json',{cache:'no-store'});D.progress=await p.json();if(D.progress.status==='completed'){for(let [key,name]of[['result','results.json'],['predictions','outer_predictions.json']]){let r=await fetch(name,{cache:'no-store'});if(r.ok)D[key]=await r.json();}const f=await fetch('figures/heldout_predictions.svg',{cache:'no-store'});D.figuresReady=f.ok;}render();}catch(e){$('detail').textContent='暂未读取到最新进度，保留上次状态。'}setTimeout(poll,1500)}poll();</script></html>'''

def build():
    result=read('results.json') if (RUN/'results.json').exists() else None
    progress=read('progress.json');predictions=read('outer_predictions.json') if result else [];coverage=read('feature_coverage.json')
    ranking=figures(predictions,progress,coverage) if result else []
    if result:
        for name,rows in [('outer_predictions.csv',predictions),('source_errors.csv',ranking)]:
            b=io.StringIO(newline='');w=csv.DictWriter(b,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows);(RUN/name).write_text(b.getvalue(),encoding='utf-8-sig',newline='')
    data=dict(result=result,progress=progress,predictions=predictions,figuresReady=bool(result))
    template=TEMPLATE.replace('</style>','[hidden]{display:none!important}td small{overflow-wrap:anywhere}</style>')
    content=template.replace('__DATA__',json.dumps(data,ensure_ascii=False,allow_nan=False).replace('</','<\\/'))
    (RUN/'模型v1.2训练结果.html').write_text(content,encoding='utf8')
    print(json.dumps(dict(report=str(RUN/'模型v1.2训练结果.html'),completed=bool(result),prediction_rows=len(predictions))))
if __name__=='__main__':build()
