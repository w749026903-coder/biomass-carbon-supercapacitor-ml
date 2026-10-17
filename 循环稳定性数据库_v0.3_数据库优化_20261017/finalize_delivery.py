"""Create review documents and inspectable receipt, then hash all deliverables."""
from pathlib import Path
import json,hashlib,sqlite3,subprocess,io,contextlib,os
ROOT=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(name,obj):(ROOT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
def write(name,text):(ROOT/name).write_text(text,encoding='utf-8')
def main():
 # Finish the readable-text companion extraction; the complete XML main source was already read.
 inv=json.loads((ROOT/'source_inventory.json').read_text(encoding='utf-8'))
 for item in inv:
  if item.get('extraction_error') and item['format']=='TXT':
   out=ROOT/'evidence_text'/f"{item['paper_id']}_{item['role']}.json"
   save(str(out.relative_to(ROOT)),[{'page':None,'text':Path(item['path']).read_text(encoding='utf-8-sig')}])
   item['initial_extraction_note']='Plain TXT was initially offered to an XML parser; corrected with plain UTF-8 reader. Complete main XML was never missing.'
   item.pop('extraction_error');item['extraction_path']=str(out);item['extraction_sha256']=sha(out)
 save('source_inventory.json',inv)
 save('公开证据核查.json',[
  {'paper':'SRC123 predecessor','doi':'10.1016/j.colsurfa.2016.10.009','url':'https://www.sciencedirect.com/science/article/abs/pii/S0927775716308627','scope':'Official public preview only','findings':'2016 identity and rice-husk RHC confirmed. Route: carbonization 500 C/1 h; KOH activation 700 C/1 h at 4:1. Preview BET3263 m2/g and pore volume1.772 cm3/g belong to the predecessor, not the 2025 batch. No complete predecessor cycling curve was obtained.','decision':'Neither reuse nor independence established.'},
  {'paper':'R001 predecessor','doi':'10.1002/asia.202400622','url':'https://aces.onlinelibrary.wiley.com/doi/10.1002/asia.202400622','scope':'Official Wiley search metadata, matched to local reference17','findings':'2024 Chemistry An Asian Journal honeydew-peel carbon paper identity matched.','fulltext_attempt':'NIMS official repository link found; local HTTPS certificate authentication failed, web fetch timed out. No certificate validation disabled and no PDF claimed as read.','repository_url':'https://mdr.nims.go.jp/filesets/a9e8f5f6-c96f-4683-ac31-229837e845e0/download','decision':'Full curve and batch comparison pending.'},
  {'paper':'R111','doi':'10.1016/j.biombioe.2025.108253','url':'https://www.sciencedirect.com/science/article/abs/pii/S0961953425006646','scope':'Official metadata found; page fetch returned403','decision':'No SI acquired. Missing device window remains a source access gap, not proven author omission.'},
  {'paper':'SRC035','doi':'10.1016/j.jallcom.2025.182201','url':'https://www.sciencedirect.com/science/article/abs/pii/S0925838825037624','scope':'Official metadata found; page retrieval unavailable','decision':'No SI acquired; local main refers to TableS1. Pore volume remains unlocated pending SI.'}
 ])
 py=ROOT.parent/'循环稳定性数据库_v0.2_20261017/.venv/Scripts/python.exe'
 run=subprocess.run([str(py),'-B',str(ROOT/'modeling/train_grouped.py')],capture_output=True,text=True,encoding='utf-8',check=True)
 preflight=json.loads(run.stdout);assert not preflight['training_performed'] and preflight['approved_rows']==0
 save('modeling/preflight_result_v03.json',preflight)
 # A small notebook whose SQL cells are actually executed against this revision read-only.
 codes=["from pathlib import Path\nimport sqlite3, json\nroot=Path.cwd()\nc=sqlite3.connect((root/'cycling_v0_3.sqlite').as_uri()+'?mode=ro',uri=True)\nc.row_factory=sqlite3.Row\nprint(c.execute('PRAGMA integrity_check').fetchone()[0])",
 "print(json.dumps([dict(r) for r in c.execute('SELECT status,count(*) AS endpoints FROM admissions GROUP BY status')],ensure_ascii=False,indent=2))\nprint('training_ready',c.execute('SELECT count(*) FROM training_ready').fetchone()[0])",
 "print(json.dumps([dict(r) for r in c.execute(\"SELECT record_id,voltage_lower_V,voltage_upper_V FROM endpoint_effective_review WHERE paper_id='R107'\")],ensure_ascii=False,indent=2))",
 "print(json.dumps([dict(r) for r in c.execute(\"SELECT issue_id,record_id,status,effective_status,resolution_review_id FROM issues_effective WHERE code='batch1_voltage_window_consistency'\")],ensure_ascii=False,indent=2))",
 "print(json.dumps([dict(r) for r in c.execute(\"SELECT record_id,current_density_A_g,pore_unit_review_required,total_pore_volume_cm3_g FROM endpoint_review WHERE paper_id='R091'\")],ensure_ascii=False,indent=2))\nprint(json.dumps([dict(r) for r in c.execute('SELECT * FROM validation_links')],ensure_ascii=False,indent=2))\nc.close()"]
 cells=[{'cell_type':'markdown','metadata':{},'source':['# v0.3 只读复核\n从本 Notebook 所在目录打开。所有SQL以mode=ro连接研究库；不包含训练或写库代码。已保存本次实际执行输出。\n\n旧问题表保留原状，当前结论请读issues_effective；有效窗口请读endpoint_effective_review。']}]
 ns={};old=os.getcwd();os.chdir(ROOT)
 try:
  for i,code in enumerate(codes,1):
   capture=io.StringIO()
   with contextlib.redirect_stdout(capture):exec(code,ns)
   cells.append({'cell_type':'code','metadata':{},'execution_count':i,'source':code.splitlines(True),'outputs':[{'output_type':'stream','name':'stdout','text':capture.getvalue().splitlines(True)}]})
 finally:os.chdir(old)
 save('v03只读复核.ipynb',{'nbformat':4,'nbformat_minor':5,'metadata':{'kernelspec':{'name':'python3','display_name':'Python 3','language':'python'},'language_info':{'name':'python','version':'3.12.14'}},'cells':cells})
 write('README.md','''# 循环稳定性数据库 v0.3：数据库优化审查版

日期：2026-10-17。当前为可合并的候选/审查交付，不是正式训练数据集。正式准入0，未进行研究训练、上传或统一合并。

从共同基线v0.2真实SQLite承接。原126篇、137份来源文件、67个暂定材料、83个暂定测试、89个候选终点保留；其中51篇存在循环候选。本次对24篇/31个暂定材料/35终点做了新增来源核验，其余54终点仅承接既有分类和未决审查，未假称重新逐项核清。

## 先看哪里

- `审查结果与优化说明.md`：白话结果、完成标准、逐来源判断和缺口。
- `cycling_v0_3.sqlite`：真实主库。`逐记录准入与冻结.json`覆盖89条当前决定和阻断项。
- `字段覆盖与出处_v03.json`：当前有效值、原测试级值、原摘录和最新审查证据；非空不等于已核实。
- `来源与材料关系.json`：暂定材料、来源组、前作关系和曲线/测试关联。
- `版本字段差异.json`、`核验报告_v03.json`：逐字段前后值和42项核验结果。
- `v03只读复核.ipynb`：已执行的只读SQL；从本目录打开。
- `进度与交接.md`、`merge_manifest.json`：发起对话合并入口。

## 当前计数的含义

首批原12终点仍为8条有条件保留、4条冻结、0条准入。整个89终点当前为16条有条件保留、18条冻结、1条明确在主体系外、54条沿用待终审。这里的“有条件保留”只准继续核录。

筛查队列从12变成10终点/9暂定材料/9篇：R106 FMC和R112两个节点增加成品硅范围待审标记，R091恢复明确循环电流和恒流协议。模型所需有效条件都有配对值的为8终点/8暂定材料/8篇；再加BET仍8；再加总孔体积4。此处仍包含冻结或未终审值，不能作训练覆盖率或独立实验样本量。

## 读取当前结论的方法

`raw_records`、`field_evidence`是保留的原始摘录。`endpoint_review`保留共享暂定测试字段，`endpoint_effective_review`将R107两万次未经独立证明的继承窗口留空。模型`training_ready`从有效视图读取，要求全部准入位及所有显式阻断项清除。

`issues`保留全部旧事项，包括此前R112电压误读；`issue_resolutions`追加更正链接，`issues_effective`给出有效状态。不要把历史open直接当作仍有效的科学结论。

`record_blockers`的621行是原有准入缺项与具体阻碍的显式展开，含已核后解决项，不代表发现621个独立科学错误。新表的写入与旧字段更新均有来源、理由或基线继承说明。

## 复验

不重跑`inspect_baseline.py`、`review_v03.py`、`prepare_v03_modeling.py`或`link_errata.py`；它们是本次一次性增量历史，带防重复保护。复核可运行`verify_and_export.py`（只读研究库，刷新本任务核验/导出副本）。不重跑任何v0.1/v0.2旧生成器。

模型只读预检查用v0.2已存在的项目环境：

```powershell
& '..\\循环稳定性数据库_v0.2_20261017\\.venv\\Scripts\\python.exe' -B '.\\modeling\\train_grouped.py'
```

它实际返回waiting_for_record_admission和0条准入，未拟合。没有创建新环境或改共享环境。模型/特征集/折数/预算/种子沿用共同合同，仅将database_file定位到本版，并加强来源关系分组拦截。原16项假数据拟合检查不在本次重复运行，本次新增5项内存来源分组行为检查不含拟合。

本任务目录未读取对方未完成文件作证据，也未修改文献补充任务目录或共同契约。由发起对话核双方manifest后，在新合并目录统一处理。
''')
 write('审查结果与优化说明.md','''# 本次优化解决了什么

本次把“数据库有值”与“这个值有资格进入模型”进一步分开。关键进展是更正一处旧图读错误、恢复真实循环电流、纠正体系与标签限定，并让继承字段和冻结事项在模型入口实际生效。正式准入仍为0；质量分母与来源独立性尚无足够证据，不能把软件检查通过写成数据已就绪。

## 具体改法和完成标准

| 需要优化 | 已落实的改法 | 怎样才算完成 |
|---|---|---|
| 循环电流“每克” | 首批12条逐源复查公式、负载与循环段；单独记录电容质量与循环电流分母未定位 | 取得直接电流归一化说明，明确单片活性物/两片总活性物/涂层等；不能仅有电容公式 |
| 初始参照 | 保留作者initial定义，不猜首圈或活化结束圈号；R091补作者initial证据 | 定义可追溯且完成跨来源可比性审查；数值圈号不是强制凭空补齐项 |
| 图读与协议 | R112用放大图纠正刻度误读；R091从循环图直接补3 A/g | 原文与曲线实际峰值相符，数值属于对应循环测试而非相邻倍率测试 |
| 继承协议 | R107两万次窗口在有效视图留空，原共享测试值保留 | 有直接两万次窗口证据，或明确且可审查的继承协议结论；测试身份仍不能虚构拆分 |
| 材料与单位范围 | FMC/FMCA分开；成品XPS硅与原料分开；R091保留原印m³/g；面电流不换算A/g | 样品、方法、阶段、单位和分母均有出处；不设未经约定的硅阈值 |
| 标签口径 | SRC123两千次eq→approx；SRC125两节点eq→approx/gt；数字原值不改 | 冲突得到来源级澄清后按明确口径使用；不能靠挑更高值或摘要凑精确标签 |
| 来源独立性 | 新增R001前作DOI；记录R107暂定测试和R112/SRC123同曲线；前作若入库须连组 | 获得批次/曲线复用或独立的证据并完成来源分组终审 |

## 逐来源结论

| 来源与记录 | 本次落实 | 当前判断与具体缺口 |
|---|---|---|
| R106 FMC / FMCA | 图11没有循环电流标注；正文定性SiO2涉及成品，SI表S1定量EDS只属于FMCA：Si11.68 at%、22.20 wt% | 两条冻结。FMC电流/分母和本身成品范围仍缺，FMCA也不能因知道硅数值便自动准入 |
| R111 ACK-700 | 已核已有6 M KOH与2000次/1 A/g/89.44%；补制备温度、时长、KOH/预碳比例，均注明循环前 | 有条件保留。缺SI FigS3器件窗口；未借三电极电压，未用能量密度反算 |
| R112 CY02 / CY03 | 放大p13 Fig11c看到最高刻度1.2 V，实际红/蓝曲线峰值约1.0 V，与p10的0–1 V一致 | 更正v0.2电压冲突误读，旧事项经追加链接标有效已解决。两条仍冻结于成品硅范围、质量分母、基线与来源独立性 |
| R112 硅 | p6、p8 Fig4明确Act_OFSCBC成品XPS Si1.7% | 样品身份清楚；此处百分比未明确at/wt，保留未指定口径，未填入at%字段 |
| R107 CY01 / CY02 | 一万次图6窗口0–1 V；SI FigS11仅直接确认两万次5 A/g、6 M KOH | 两条有条件保留。原测试编号继续共用；两万次窗口有效值留空，两节点必须同组，不增加独立材料/测试数量 |
| SRC123 | 前作2016 DOI已复核；两千次原文approximately90.1%，当前关系更正为approx；一万次27.9%数值保留 | 两节点冻结；等质量两节点同曲线。前作路线相近、BET不同均不能解决批次/曲线复用，质量不平衡器件另列 |
| SRC124 | 完整XML主文与SI均在本地；标准MHDHPC-600作者报告92%保留 | 有条件保留。不用200/216替换标签，不搬到100/400 cm²放大批；质量分母、独立性未过 |
| R093 / R103 / R104 / SRC035 | 原标签和已核条件保留；本次复查质量说明仍未单独定义循环电流分母 | 有条件保留。R103总孔体积未定位；SRC035所指SI TableS1未取得，不能称原文未报告 |
| R091 | 目视p8 Fig6g明确3 A/g、5000次、73%；p9为作者initial；Table1给BET1098.07 | 恢复到筛查队列，有条件保留。原印孔体积0.68 m³/g只作待审观测，cm³/g特征仍空；质量分母、独立性未过 |
| R033 CY02 | p6正极2.040 mg、负极2.872 mg | 纠正为同碳质量不平衡体系，主体系外且继续冻结；99.9%与86%归属仍不擅择 |
| R087 | p3直接写三电极、铂辅助和甘汞参比 | 当前体系改为3E，明确排除主体系 |
| R108 CY05 | 图6e明确20 mA/cm²、15000次92.0% | 有条件保留为面电流候选，不用相邻曲线负载推A/g；器件协议还需核，不能纳入当前A/g主集 |
| SRC093 | 图8直接给AC3全电池0–0.8 V、2.0 mA/cm²；正文单位印刷和图注不同 | 补窗口和面电流，按图注存；约78%保留approx，不转换A/g |
| R105 / SRC112 | 正文明示close to100% / approximately106% | 有条件保留，保留approx，不用摘要整数升级精确标签 |
| R017 两节点 | >99%和未配对数值标签仍存在 | 有条件保留用于继续核录，不进入当前精确标签主集 |
| R020 AC对照 | 约89%及复合样品范围分开 | 对照有条件保留为approx；镍/聚合物复合样品不能混入 |
| SRC120 | 本作Table5写79.4%，正文写79% | 冻结，保留原候选approx79并登记分歧，不挑一个消除冲突 |
| SRC125 两节点 | 图12直接5 A/g；正文SCB around93.89%、SCB-A over98.43%，摘要样品赋值不同 | 补循环电流，关系分别approx/gt并冻结；类别C不改变，未静默调整研究范围 |
| SRC028 六材料 | p8六条循环值有对应，但含Zn盐制备后成品残留未清 | 六条冻结，不能把使用Zn盐自动当复合材料或自动当纯碳；需成品证据 |

35条新增审查结论已逐记录保存，另外54条沿用既有体系/方法/材料/标签/短循环筛查与待终审状态，没有重新认证。

## 覆盖、历史和模型核验

当前筛查10终点/9暂定材料/9篇，必需有效条件非空8/8/8，加BET8/8/8，再加总孔体积4/4/4。R107两万次继承窗口留空是有效配对数量下降的原因之一；筛查资格和有值均不是准入。

新增74条审查事件（80→154）、91条字段变更日志（69→160）、16条材料观测（75→91）与5条问题（238→243）。两个R112旧电压事项未覆写，通过2条追加解决链接表达更正。全部旧原始记录、字段证据、冻结事项、审查与更正历史保留。621条显式阻断展开不能当作621项新科学发现。

42项核验通过，包括288个受保护文件指纹、137来源哈希、完整性/外键、全部旧行保护、字段旧新值连续链、原始数字标签与循环次数保护、归一化DOI去重、冻结与继承窗口拦截、模型科学配置不变。新增5项来源分组行为检查只用内存身份行，没有拟合。两条“假设把准入位全改通过”的门禁检查也只在内存副本执行，研究库仍0准入。

模型入口实际执行只读preflight，依赖由既有v0.2项目环境满足；没有新装软件或共享环境变动，没有研究分数或模型赢家。此前的16项合成拟合检查是v0.2历史，本次未冒称重跑。

可公开核对的前作身份：[SRC123前作出版社页](https://www.sciencedirect.com/science/article/abs/pii/S0927775716308627)、[R001前作Wiley页](https://aces.onlinelibrary.wiley.com/doi/10.1002/asia.202400622)。本次没有取得二者完整曲线对照，也未取得R111/SRC035 SI。访问失败仅记为访问缺口，不作作者未报告的证据。
''')
 report=json.loads((ROOT/'核验报告_v03.json').read_text(encoding='utf-8'));assert report['all_passed']
 unresolved=[
 '首批12条循环电流质量分母仍未直接核清，全部mass_basis_checked=0。',
 '所有材料跨来源独立性仍未终审，全部independence_checked=0。',
 'R106 FMC/FMCA循环电流和成品硅材料范围；不跨样品转移EDS数据。',
 'R111缺SI FigS3窗口；SRC035缺SI TableS1孔体积。',
 'R112电压误读已更正，但成品Si百分比口径、范围和其他准入事项仍未清。',
 'R107共享暂定测试身份未决，两万次窗口目前仅继承，保守有效值为空。',
 'SRC123/R001前作完整批次与曲线对照尚不可得，未判独立或复用。',
 'R091孔体积原印m3/g不改，严格单位特征仍空。',
 'R033质量不平衡及标签归属，SRC120数值分歧，SRC125材料赋值/限定冲突，SRC028成品残留。',
 '其余54终点为原筛查路由承接，不是本次全文逐项认证；范围外体系不放宽。',
 '未读取对方未完成交付，不执行合并、归档或研究训练。'
 ]
 write('进度与交接.md','''# v0.3 数据库任务交接

日期：2026-10-17。状态：本任务交付已完成，可进入发起对话统一合并；科学准入仍0，证据缺口继续保留。

已读取E盘长期记忆入口及四项必要索引、共同契约、任务安排、v0.2交接与优化说明。从共同基线35d4bbf895501ec306ea215b40f865cc5d1da4e7959173d73e279dd3eaaa22fa承接完整数据库。只写本目录；v0.1/v0.2、原文、共同文档和对方目录未改，288份受保护文件复核一致。

已完成24篇/31暂定材料/35终点的本轮新增核验，完整89条路由及准入/冻结清单已导出。首批原12条仍8有条件、4冻结。全库16有条件、18冻结、1主体系外、54沿用待终审；0准入。当前筛查10终点/9材料/9篇，有效条件配对8/8/8；加BET8/8/8、再加孔体积4/4/4，均不等于准入。

最重要更正：R112的1.2 V是纵轴刻度，实际曲线峰值约1 V；追加更正并关联旧问题解决，未隐藏历史。R112仍冻结于材料范围等。最重要补值：R091循环图直接3 A/g；R108为20 mA/cm²、SRC093为2 mA/cm²，绝不转换成A/g。R033更正为质量不平衡，R087为3E；SRC123/SRC125非精确限定已落实。

合并请先核merge_manifest.json所有文件哈希及共同基线。新增表：record_blockers、endpoint_protocol_overrides、validation_links、review_batches、issue_resolutions；新增视图endpoint_effective_review、issues_effective；training_ready已增强。旧表字段变动详见版本字段差异.json，全部有旧新值和理由。共同研究体系、阈值、模型、特征、折数与预算未改。

合并阅读入口须采用endpoint_effective_review和issues_effective。R107原测试级窗口仍保存，但两万次有效窗口留空；R112历史问题原status仍open，有效状态由追加解决链接提供。不要把旧open重新当作未解决电压冲突，也不要让继承窗口变成已核输入。

已执行42项数据/历史/版本核验与5项新分组行为检查；模型preflight实际0条、training_performed=false。不重跑旧建库、下载、迁移脚本，也不重跑本版一次性增量脚本。若需复验，verify_and_export.py只读主库并刷新本目录导出，Notebook也仅只读。

未完成的科学缺口：首批电流分母、跨论文独立性、R106硅范围、R111/SRC035 SI、R107测试身份/窗口继承、R001/SRC123前作完整对照、R091单位及SRC120/SRC125冲突。作者initial可记录，不猜精确圈号。可读官方资料不足时继续保持未定位/缺访问，不称未报告。

另一文献任务未在本轮并入，未对其成果作任何确定结论。统一合并责任仍在发起对话；新文献先暂存候选，不能因合并自动归档或准入。
''')
 # All delivered files except this self-referential manifest are hashed.
 outputs=[]
 for p in sorted(ROOT.rglob('*')):
  if p.is_file() and p.name!='merge_manifest.json' and '__pycache__' not in p.parts:
   role='review_artifact'
   if p.suffix=='.sqlite':role='candidate_review_database'
   elif p.suffix=='.py':role='inspectable_code_or_once_only_history'
   elif 'evidence' in str(p.relative_to(ROOT)):role='source_inventory_or_local_evidence_derivative'
   outputs.append({'path':str(p),'sha256':sha(p),'role':role})
 manifest={'schema_version':'parallel-preparation-v1','task_role':'database','baseline_database_sha256':'35d4bbf895501ec306ea215b40f865cc5d1da4e7959173d73e279dd3eaaa22fa','baseline_model_contract_sha256':'63db1238c429d6a26b2467e529e9ebc589e70487e1def3d5108803cbc5e3ade5','ready_for_merge':True,'outputs':outputs,'checks':report['checks']|{'actual_model_preflight_no_fitting':preflight['training_performed']==False,'all_deliverable_hashes_saved':True},'unresolved_issues':unresolved,'proposed_contract_changes':[],'schema_and_implementation_notes':['Scientific scope and admission definitions unchanged.','Add explicit record blockers, endpoint protocol overrides, validation links, batch audit, append-only issue resolution links.','Use effective protocol/issue views; strengthen training_ready and normalized predecessor group guard.','Model contract changes only database_file to cycling_v0_3.sqlite.','Manifest itself is excluded from its own hash list to avoid self-reference.'],'research_training_performed':False,'counts':report['counts'],'limitations_saved':True}
 assert all(sha(x['path'])==x['sha256'] for x in outputs)
 save('merge_manifest.json',manifest)
 print(json.dumps({'ready_for_merge':True,'files_hashed':len(outputs),'approved_rows':0,'preflight_training_performed':False},ensure_ascii=False))
if __name__=='__main__':main()
