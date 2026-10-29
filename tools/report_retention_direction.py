"""Plain-language, fixed-I/O feasibility report, using measured results only."""
from pathlib import Path
import html,json,math
from reportlab.graphics.shapes import Drawing,Rect,Line,String
from reportlab.graphics import renderSVG
from reportlab.lib import colors
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'小样本方向预研_20261029';RUN=BASE/'保持率固定输入输出'
def read(p):return json.loads(Path(p).read_text('utf8'))
def table(headers,rows):
 return '<div class="table"><table><thead><tr>'+''.join('<th>'+html.escape(str(x))+'</th>'for x in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+html.escape(str(x))+'</td>'for x in row)+'</tr>'for row in rows)+'</tbody></table></div>'
def main():
 results=read(RUN/'results.json');verify=read(RUN/'independent_verification.json');by={(s['route'],s['model']):s for s in results['metrics']}
 selected=[('R1_KOH6_10000','random_forest','6M KOH、10000圈，整来源留出'),('R2_KOH6_10000_j10','random_forest','再固定10 A/g，整来源留出'),('R3_plant_residue_KOH6','random_forest','植物残余物、6M KOH，整来源留出'),('R4_per_cycle_rate','random_forest','每圈衰减速率变换，整来源留出'),('R5_known_family','fixed_Matern_GPR','已知论文家族，留出整个材料')]
 rows=[]
 for route,model,label in selected:
  s=by[(route,model)];rows.append([label,str(s['rows'])+'/'+str(s['sources']),f"{s['r2']:.3f}",f"{s['mae']:.2f}",f"{s['rmse']:.2f}",'未通过'])
 d=Drawing(700,290);x0=80;y0=50;width=560;maxerr=9
 for tick in [0,2,4,6,8]:
  y=y0+tick/maxerr*190;d.add(Line(x0,y,x0+width,y,strokeColor=colors.HexColor('#dce3df')));d.add(String(x0-10,y-4,str(tick),textAnchor='end',fontSize=10))
 d.add(String(x0,263,'Source-balanced retention MAE (percentage points)',fontSize=13))
 for i,(route,model,label)in enumerate(selected):
  s=by[(route,model)];x=x0+28+i*108;h=s['mae']/maxerr*190;d.add(Rect(x,y0,55,h,fillColor=colors.HexColor('#a34838'),strokeColor=None));d.add(String(x+27,y0+h+9,f"{s['mae']:.2f}",textAnchor='middle',fontSize=11));d.add(String(x+27,28,'R'+str(i+1),textAnchor='middle',fontSize=11))
 y=y0+2/maxerr*190;d.add(Line(x0,y,x0+width,y,strokeColor=colors.HexColor('#126b53'),strokeWidth=2,strokeDashArray=[5,3]));d.add(String(645,y+5,'Goal: 2 pp',fontSize=10,textAnchor='end',fillColor=colors.HexColor('#126b53')))
 (RUN/'figures').mkdir(exist_ok=True);renderSVG.drawToFile(d,str(RUN/'figures/retention_mae.svg'))
 criteria=[['输出','指定循环次数与工况下的电容保持率（%）'],['固定输入','循环次数、电流密度、电解液、浓度、电位窗下限/上限、BET、参比电极'],['决定系数','R² > 0.95，按真实预测残差计算'],['误差','MAE ≤ 2个百分点；RMSE ≤ 3个百分点；优选1/1.5个百分点'],['误差尾部','90%预测的绝对误差 ≤ 5个百分点；来源MAE第90百分位 ≤ 5个百分点'],['基线','来源均衡MAE至少优于训练均值20%，保留来源重采样区间'],['泛化','整来源留出；全部预处理限训练折；最终另用没有参与路线选择的新来源验证']]
 routes=[
 ['优先1：完整循环曲线监督','将论文R(N)曲线上的多个圈数作为训练标签，输入仍是原八项；RF/XGB/GPR拟合R(N,x)。新材料整条曲线和同来源材料共同留出。','已核对AHPC和木粉原图；47行当前主表以端点为主，现行规范库没有可直接调用的密集保持率轨迹表。新增标签需逐图审查，尚未训练这一新库。'],
 ['优先2：真正同化学系列的小模型','按相同前驱体、固定掺杂体系、活化路线与电极/测试协议选范围，元数据只用于范围核查，部署输入仍八项。先20–40个独立材料的试点，并按来源/批次验证。','目前只有少数每篇4–5材料的系列；13材料/3家族留材料结果未过线。原OPBNP/OPNP近BET却差10.1pp，说明“都是生物质碳”还不够窄。20–40是试点规划量，不是达标保证。'],
 ['优先3：学习曲线参数的物理启发模型','由训练材料全曲线拟合活化与衰减参数，再从八项输入预测参数并还原R(N)。允许真实>100的活化，参数只从训练来源学习。','已审作者GitHub的参数学习与组隔离代码；其电池模型和早期电学输入不直接迁入。简单恒定每圈速率本轮失败，需多阶段曲线证据而非直接套公式。'],
 ['候选4：核方法与固定融合','以log(圈数/电流/BET)、条件类别和相互作用构造核，GPR/核岭刻画局部响应；RF/XGB/GPR的组合权重只能在训练来源内部选择。','固定GPR、RF、XGB、BP及两种等权融合本轮均未过线。可以在新的有效训练曲线库形成后另做计划，本轮不追分。'],
 ['候选5：外部保持率数据作受审先验','对801例公共保持率数据先审字段、材料、原文与来源；能映射到同一八项合同的才作训练/迁移候选，其余只作先验或方法资料。','Zenodo原始CSV约162KB，资源成本低；尚未下载/逐记录审查，论文混有金属、聚合物等体系，不能直接算成生物质碳有效样本。']]
 allrows=[]
 for s in results['metrics']:
  if s['model']=='training_mean':continue
  allrows.append([s['route'],s['model'],s['rows'],f"{s['r2']:.3f}",f"{s['mae']:.3f}",f"{s['rmse']:.3f}",'缺预测，不可比较'if not s['numerical_checks']['complete_predictions']else'未通过'])
 sources=read(RUN/'文献与开源方法审查.json')
 refhtml='<ul>'+''.join('<li><a href="'+html.escape(s['url'])+'">'+html.escape(s.get('title',s.get('repository',s['url'])))+'</a>：'+html.escape(s.get('use',s.get('transferable','')))+'。'+html.escape(s.get('limit',s.get('limitations',s.get('excluded_as_direct_candidate',''))))+'</li>'for s in sources['sources']+sources['repositories'])+'</ul>'
 body='<header><p class="eyebrow">主项目 · 2026-10-29 · 固定输入输出的方向预研</p><h1>先守住输入输出，再缩小预测问题</h1><p class="lead">目标始终是电容保持率。251次固定输入拟合完成，目前没有方案同时通过R²、误差和泛化要求。新的重点应是同化学系列与完整循环曲线监督。</p><p class="status">状态：初步路线审查完成，R²＞0.95挑战目标尚未达到。</p></header>'
 body+='<section><h2>先明确什么算达标</h2>'+table(['项目','约定'],criteria)+'<p>这些是项目建议验收线，属于工程目标，并非行业统一标准。保持率专门研究（Batteries 2025，表6/7）报告MLP在未见器件上R²约0.941、MAE约2.15、RMSE约3.15个百分点；其训练R²约0.976不能移作未见数据成绩。本项目目标更高，而且须保留原八项输入。</p><p>所有门槛要在同一批测试上同时通过。R²取决于测试集波动：R²＞0.95要求RMSE小于该测试集标准差的约22.36%。当前窄范围的标准差约4.5–5.2个百分点，实际需要约1.0–1.2个百分点的RMSE，单有RMSE≤3还不够。</p></section>'
 body+='<section><h2>已经实际试过什么</h2><p>下表使用事前指定RF；R5为GPR方法检查，属于已知家族内的留材料检验。没有从外层成绩中挑最高分来宣称成功。R1–R4按整来源留出，范围之间有嵌套，不相加样本。</p>'+table(['方案','记录/来源','R²','MAE/百分点','RMSE/百分点','结论'],rows)+'<img src="figures/retention_mae.svg" alt="五条保持率试验的来源均衡MAE与2个百分点门槛"><p>另试岭回归、XGBoost、小型BP、固定核GPR及RF/XGB、RF/GPR等权组合，均未过线。共251次拟合尝试，1次BP未产生有效完整预测，保留失败，不隐藏或重试挑结果。</p></section>'
 body+='<section><h2>为什么缩小范围还不够</h2><p>原有47条主集只来自34个来源；单固定6M KOH和10000圈，就只剩14条/7来源，再固定10 A/g只剩10条/6来源。范围更统一，同时也更缺独立材料信息。</p><p>更具体地，OPBNP与OPNP的原八项中七项相同，BET分别1774.8和1894.9 m²/g，保持率却是93.6%和83.5%，相差10.1个百分点。两者组成有区别；BET相近不能代替化学体系相同。这不是证明模型永远做不到，而是要求我们在原输入不变的前提下，认真限定材料的适用范围。</p><p>窄范围也会使保持率变化更小，对R²反而更苛刻。不能只选90%以上的容易材料，或删掉困难来源来获得漂亮分数。</p></section>'
 body+='<section><h2>下一轮值得做的五条路线</h2>'+table(['路线','怎样守住八项输入与保持率输出','已有依据与尚缺内容'],routes)+'<p>我建议先做优先1与优先2的联合试点：先审现有论文中约10–20个来源、30–50个材料的完整循环记录，再按证据实际覆盖决定是否建模。此数量是规划范围；一条曲线采20点仍是一个材料的一次试验，不能声称增加20份独立样本。若资料不足，应给出具体论文/图表清单，不先把更多模型堆上去。</p><p>完整曲线的用途是给训练集提供不同N的真实保持率标签。预测端仍只有原八项，禁止把待测材料的早期实测保持率、终点值、来源ID塞入模型。需要预测新材料时，其所有曲线点必须共同留出。</p></section>'
 body+='<section><h2>论文与开源方法：学什么，哪些不直接迁入</h2>'+refhtml+'<p>寿命预测的MAPE、比电容的F/g误差、其他材料体系的高R²，仅是方法资料。它们不属于本项目的保持率验收结果。没有运行第三方代码、安装大模型或下载大型数据。</p></section>'
 body+='<section><h2>核验与当前边界</h2><p>独立核验'+str(verify['checks'])+'项通过；核对八项字段、原标签、整来源/整材料隔离、指标重算及63份输入/源文件哈希。旧数据库、模型和原文保持。所有当前来源已被探索，最终可靠性仍需未参与路线选择的新来源验证。</p><p>本轮早期还做过比电容/BET方向的986次拟合或曲线参数拟合，其中三点倍率插值出现高R²。用户纠正方向后，这些结果已单列为偏离目标的方法试验，绝不算保持率达标，也不进入本表。</p><details><summary>全部保持率模型结果（含失败覆盖）</summary>'+table(['范围','模型','有效预测','R²','MAE','RMSE','状态'],allrows)+'</details></section><footer>数据v7固定历史；本轮新增循环准入0。训练计划、逐次拟合、逐条留出预测与独立核验均在本目录。</footer>'
 style='body{margin:0;background:#f3f5f2;color:#1e2c29;font:16px/1.75 "Microsoft YaHei",sans-serif}main{max-width:1060px;margin:auto;padding:40px 24px}header,section{background:#fff;padding:30px 34px;margin-bottom:22px;border:1px solid #dce4de;border-radius:12px}h1{font-size:32px;line-height:1.4;margin:10px 0}h2{font-size:23px;line-height:1.4;color:#145c47}.eyebrow{color:#42705e;font-size:14px}.lead{font-size:19px}.status{border-left:4px solid #b15a38;padding:10px 14px;background:#fff3e9}.table{overflow:auto}table{width:100%;border-collapse:collapse;font-size:14px}td,th{padding:12px;text-align:left;border-bottom:1px solid #dce4de;vertical-align:top}th{background:#e9f1eb;color:#264e3c}td{min-width:65px}a{color:#145c47;word-break:break-word}img{width:100%;height:auto;margin:20px 0}li{margin:12px 0}summary{cursor:pointer;color:#145c47}footer{color:#5c6c64;font-size:13px}@media(max-width:600px){main{padding:15px 10px}header,section{padding:22px 18px}h1{font-size:26px}h2{font-size:21px}}'
 body=body.replace('<header>','<header><p class="status">最新澄清：本报告评估的是原八项基准。用户允许协商修改输入、电极体系与范围；输出始终是保持率。<a href="../../docs/RETENTION_CONTRACT_DISCUSSION_20261029.md">查看具体合同备选</a>，新合同尚待选择。</p>',1)
 (RUN/'保持率方向预研报告.html').write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>保持率固定输入输出：方向预研</title><style>'+style+'</style><main>'+body+'</main></html>','utf8')
 md='# 保持率固定输入输出：方向预研\n\n原八项输入保持，输出为电容保持率；251次固定输入拟合后，没有方案通过所有数值与泛化门槛。\n\n建议验收线：R²>0.95，MAE≤2个百分点、RMSE≤3个百分点、90%绝对误差≤5个百分点；最终采用未参与路线选择的新来源检验。阈值是项目建议，不是行业统一标准。\n\n'
 md+='| 范围 | 记录/来源 | R² | MAE | RMSE | 结论 |\n|---|---|---|---|---|---|\n'+''.join('| '+' | '.join(row)+' |\n'for row in rows)
 md+='\n优先：完整循环曲线提供R(N)监督＋同化学系列范围。其余候选为曲线参数学习、核方法/预先固定融合、外部保持率数据的字段与来源审查。完整曲线尚未形成新训练库，不能称新方案已达标。\n\n核心合同、具体路线、论文与GitHub版本、所有试验和局限见同目录HTML报告、training_plan.json、文献与开源方法审查.json及independent_verification.json。前期比电容/BET试验高分不计保持率成果。\n'
 (RUN/'README.md').write_text(md,'utf8')
 print(str(RUN/'保持率方向预研报告.html'))
if __name__=='__main__':main()
