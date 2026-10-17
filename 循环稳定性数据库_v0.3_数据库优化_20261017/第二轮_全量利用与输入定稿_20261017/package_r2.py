"""Publish the local second-round handoff after successful evidence/interface checks."""
from pathlib import Path
import json,hashlib,ast
ROOT=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(name,s):(ROOT/name).write_text(s,encoding='utf-8')
def save(name,v):write(name,json.dumps(v,ensure_ascii=False,indent=2))
def main():
 report=json.loads((ROOT/'核验与字段覆盖_r2.json').read_text(encoding='utf-8'));assert report['all_passed']
 write('循环稳定性预测_输入已确定.md','''# 循环稳定性预测：输入规范

本项目输出继续采用此前确定的循环稳定性指标：给定循环次数和测试条件，预测电容保持率。这里决定的是输入，而不是更改输出。日期：2026-10-17。

主模型输入现固定为7项，总孔体积为第8项可选扩展。此前只有三套候选配置、没有明确实际填写要求的问题，本轮已落实到`prediction_input_contract.json`、模型配置、填写模板和代码检查。

## 主模型：7项必填

| 输入 | 填什么、单位 | 在预测中的作用 |
|---|---|---|
| 计划循环次数N | 正整数，次；模型内部取log10(N) | 定义预测到哪一循环；由使用者预先指定，不是观察到失效后再填的终止圈号 |
| 循环电流密度 | A/g，需直接明确活性质量分母 | 定义充放电负荷；统一到正负两极活性物总质量口径后使用 |
| 电解液种类 | KOH、H₂SO₄、Na₂SO₄等实际化学组成 | 区分不同化学环境，训练折内进行类别编码 |
| 电解液浓度 | mol/L | 区分测试环境；必须同时保留原单位以核验换算 |
| 器件循环电压下限 | V，整个器件两端电压 | 确定循环窗口，不能套用三电极参比电位 |
| 器件循环电压上限 | V，整个器件两端电压 | 表示测试的电压要求；与下限共同确定窗口 |
| 循环前成品BET比表面积 | m²/g，N₂-BET | 为模型提供材料结构信息；不能只有测试条件却声称比较材料结构 |

这里的7项是本项目本轮明确的输入设计，不是文献规定的通用固定变量数，也不是已经证明的最优特征组合。适用范围沿用水系、两电极对称、生物质衍生碳、GCD循环；器件质量配平和材料范围仍需审核。当前尚无真实数据训练结果，不能声称某个变量已被统计证明最重要。

### 电流质量口径怎样统一

本版将主模型的A/g规定为`I/(m正+m负)`，两片均指活性材料质量。保留作者原报值与原分母。若作者直接定义的是`I/m正`或`I/m负`，且两片活性物质量都有直接证据，才可按对应质量比例换算。分母不清则继续阻断，不能从电容公式猜分母，也不能看到两电极就自动除以2。

这是明确的项目标准化选择，已作为拟议契约变更写进本轮manifest；没有改写共同基线文件。实际研究行还必须经审查后保存标准化值及变换出处。本次主队列仍缺直接分母证据，因此没有借这个选择放行任何记录。

### 单位是校验信息，不是性能特征

M与mol/L等价；mM可精确除以1000。小写m常表示mol/kg，不能当大写M；mol/kg、质量分数不能缺少额外证据就换成mol/L。代码已有这项拦截。浓度单位从类别特征中删除，避免让“同样6 mol/L但写法不同”成为模型的伪规律。

## 第8项：总孔体积，可选扩展

填循环前同一成品的总孔体积，单位cm³/g。不能用微孔体积、某段孔体积、原料孔体积或循环后表征代替。原印单位有疑点时保留原值与单位，模型字段留空。

主模型使用7项；预先规定的8项扩展在同一批合格记录上比较。只有可选孔体积允许在每个训练折内做中位数填补并加缺失标记，真实标签和7项核心输入不填补。全部孔体积缺失时，扩展只能视为没有获得该项材料信息，不能宣称学到孔体积影响。

## 明确保留的比较方案

1. 主方案：7项输入，即测试条件加实际BET。
2. 条件参照：从完全相同的已准入记录中去掉BET，只用6项条件，检查材料信息是否带来改善。
3. 孔体积扩展：相同记录加第8项总孔体积，作预先列出的敏感性比较。

不能挑外层得分最高的一套后称为无偏最终效果。模型仍为均值、岭回归、随机森林、XGBoost和小型MLP；按来源分组，预处理在训练折内，模型清单及调参预算不变。

## 暂不列为主输入的内容

氮氧含量、Raman、负载量、原料和制备参数继续逐字段利用，保存方法、单位和阶段。当前89候选终点中，N原子百分数有当前值7条/5个暂定材料，O为10条/6材料，负载量仅4条/3材料，还混有待核方法和口径，暂不足以作本轮所有材料都必须填写的主输入。

Raman的ID/IG与IG/ID分开存；XPS和EDS、at%和wt%分开；活化剂/原始生物质与活化剂/预碳比例分开。原料名称、碳化/活化温度和时间、活化剂等先进入扩展特征库，不把材料已经制成才能测到的BET伪装成制备前可知参数。后续若研究使用场景需要只凭制备参数预测，可在相同输出目标下另建相应输入方案，当前没有把它冒称准备完毕。

论文ID、DOI、来源组、准入状态、浓度单位、质量口径、表征阶段、测量方法等是审查或验证信息，不作为本轮性能预测特征。末圈电容、同次目标损失率、循环后EIS/XPS/SEM和目标参与计算的放电时间禁止作输入。

## 使用和验收

填写`预测输入填写模板.json`。除7项物理量外，还要提供单位、分母、BET方法/循环前阶段和适用范围的证据元信息；它们用于验证输入，不被当成额外性能变量。空值不能填0。一次填写给出一个指定循环次数的稳定性问题；想比较多个N可以逐个指定，但同材料多个请求不成为独立材料样本。

`modeling/prediction_inputs.py`能检验和标准化输入，目前没有已训练模型，因此不返回虚构保持率。28项输入/单位/泄漏边界检查通过；16项更新后的合成接口检查实际通过，合成拟合与研究库隔离。所有真实研究训练仍受禁止开关保护，正式准入仍0。

输入设计的物理和报告依据采用原始方法文献，而具体7项选择是本项目判断：[ACS储能报告建议](https://pubs.acs.org/doi/10.1021/acsami.5b06029)要求交代电极组成、活性质量、电压窗口及电流；[Nature Communications碳材料原始研究](https://www.nature.com/articles/s41467-023-40282-1)展示孔结构与表面组成对碳电极性能研究的用途。后者主要研究比电容，不能把其特征重要性当成我们循环稳定性任务的已验证结论。
''')
 write('全量利用与本轮优化结果.md','''# 全量利用与第二轮优化结果

本轮完整读取并核对现有126篇、137份来源文件的可提取文本，保留了5539处检索线索。检索线索用于定位，不能直接当作同样品、同测试、同目标证据；这也不是宣称126篇每个字段都已人工终审。

已为126篇登记用途、89个正式候选终点逐一分配后续去向。没有删除原数据或以模型需要为由抹掉低保持率、超过100%的结果。全量利用落实为材料证据、方法参考、同体系候选、其他体系候选和冻结审查等具体用途。

## 89个终点的当前去向

| 去向 | 终点数 | 如何使用 |
|---|---:|---|
| 水系两电极对称GCD候选 | 29 | 再按标签精度、完整条件、材料范围和审查位筛选，不等于29条可训练 |
| 三电极GCD旁系 | 19 | 独立协议库与表征/规律核验，不混作器件主模型标签 |
| CV循环旁系 | 5 | 保留扫描速率与指标定义，不能把CV循环当GCD |
| 凝胶旁系 | 2 | 另保留，电解质相态不并入液体水系主集 |
| 质量不平衡器件 | 2 | 独立器件设计问题，质量比不能被忽略 |
| 混合器件/半电池 | 4 | 分开保存，不替代本项目器件输出 |
| 材料范围/复合材料待审 | 26 | 包含矿物或金属、复合范围等未决，继续冻结或另作参考 |
| 协议/体系尚待定位 | 2 | 精确列缺口，不强行归类 |

以上8个去向互斥，合计89。近似标签、下限、冲突、短循环、缺失标签另外保存在label_tier中，不因分入某个去向便升级精确标签。普通RF/XGBoost/MLP点值回归不能直接把“超过99%”当99%；以后如做含删失/区间标签的研究，需另定义方法，当前只保留信息。

## 本轮实际核实或补录

- R013：确认EUAC1-60的BET1589 m²/g、总孔体积0.82 cm³/g；为同一材料的锌混合器件记录补结构特征，协议与标签仍分开。ID/IG0.92独立保存。
- R069：进一步落实正文与表格在Na₂SO₄/H₂SO₄标签配对上的冲突。保留原数值与配对，两个记录当前明确冻结；没有擅自交换数值。
- R078：回正文确认成品BET2074.72 m²/g和总孔体积0.930 cm³/g，仍是三电极体系。
- R085：表头和脚注明确0.187 cm³/g是t-plot微孔体积；单独保存，模型总孔体积字段继续空。不能因摘要笼统写pore volume就增加总孔覆盖。
- R117：ACRS-700和ACEW-700分别补BET3345/1253 m²/g、孔体积2.0/0.5 cm³/g；原文明确I/m为电流密度且m为活性物，因此只确认这两条三电极记录的质量分母。标签仍未获得可直接摘录点值，不从图造值。IG/ID1.1与1.03按原定义保存，没有倒置成ID/IG。
- SRC121：补BET1374 m²/g，核实原负载0.5 mg/cm²；不从吸附量450 cc/g反推总孔体积。
- R112：同成品的三电极记录也继承硅材料范围待审问题。前轮电压误读更正保留，不重新恢复已经纠正的1.2 V冲突。

本轮新增27条来源审查事件、21条材料观测；审查总数181，材料观测112。原字段更改与新路由修正均有日志，变更日志总177。原数值标签、循环次数、原摘录和全部旧审查/冻结历史保留。

## 新恢复的三条信息，仅暂存

REC_001为SRC025的AC3凝胶器件：5000次、10 A/g、0–1 V、98%。正文及图7g明确凝胶，不能转给同篇液体KOH器件。没有新造材料独立性或解除残留/分母审查。

REC_002为R031凝胶相关短循环400次，作者描述20圈前活化后趋稳，没有直接末端保持率点值。没有用168/154计算一个新标签。

REC_003为SRC005的2500次CV氧化峰电流趋势，明确三电极。指标不是GCD电容保持率，不生成保持率标签。

三条只进入staged_recovery_endpoints，不进入正式89条计数，也不进入training_ready。原库正式登记仍126篇、67暂定材料、83暂定测试、89终点。

## 数据究竟能支撑哪些输入

| 当前值非空的字段 | 终点 | 暂定材料 | 来源论文 |
|---|---:|---:|---:|
| BET | 38 | 27 | 25 |
| 总孔体积 | 24 | 17 | 16 |
| N at% | 7 | 5 | 5 |
| O at% | 10 | 6 | 6 |
| 活性物负载量 | 4 | 3 | 3 |

这是当前配对覆盖，包含未完成方法/阶段/独立性终审的数据，不能称真实训练缺失率。BET从34→38终点，总孔体积21→24；新值主要改善旁系和同材料表征，不能用它们宣布主队列扩充。

现严格筛查仍10终点/9暂定材料/9篇，7项核心输入均有有效当前值的为8/8/8；加总孔体积4/4/4。首批主记录的电流分母和所有材料的跨来源独立性仍未核清，正式准入0。现89条中16有条件保留、20冻结、1明确主体系外、52沿用待终审；分配用途不替代逐字段准入。

## 其他文献与核验

文献侧先前完成的20条暂存审核内容只作已发布版本的输入覆盖参考，未导入正式SQLite或归档。本轮期间文献侧进入用户要求的下载续作，manifest改为ready_for_merge=false；已引用内容指纹未变，新清单文件哈希核对通过，变化单独留档。没有把其续作新增内容当已核事实，当前不能执行统一合并。

41项数据/历史/指纹检查通过；检查411个保护文件，其中文献侧控制清单的授权续作变化单独报告，其他410个文件指纹不变。原始137来源均不变。28项输入边界检查和16项更新后合成接口检查通过；后者使用明确SYNTH假数据验证新特征配置，不能报研究模型分数。真实数据入口实际预检查0条，未进行真实研究训练。
''')
 write('README.md','''# 第二轮：全量利用与循环稳定性输入定稿

本轮接续前轮v0.3，全部新产物独占写入本子目录，前轮118份签名产物不覆盖。

先看`循环稳定性预测_输入已确定.md`：输出继续为指定循环次数和条件下的电容保持率；主输入7项、总孔体积为第8项可选扩展，已写入程序。再看`全量利用与本轮优化结果.md`和`核验与字段覆盖_r2.json`。

主库`cycling_v0_3r2.sqlite`承接全部历史；89个正式终点均在`utilization_routes`，126篇均在`paper_utilization`。3条恢复信息单独暂存，未加入正式89条或训练视图。表征112条，保留来源、样品、方法、单位、阶段和未决状态。

当前正式准入0。本轮没有启动真实研究训练、没有上传，也没有修改原文、v0.1/v0.2或前轮签名数据。文献侧正在续作，当前不满足统一合并条件；本轮只引用其先前完成且内容指纹不变的审核记录。

`prediction_input_contract.json`为输入规范，`预测输入填写模板.json`为填写表。`modeling/prediction_inputs.py`只验证输入，不返回虚构预测。模型科学输入变化已在本轮manifest的proposed_contract_changes列明，不能冒称旧共同合同完全没变；共同文件本身保持只读。

`全量利用与输入复核.ipynb`保存实际执行的只读SQL输出，从本目录打开。`exports`提供JSON/UTF-8 CSV；核验报告区分非空覆盖、候选、已准入及软件检查。

本轮`profile_all.py`、`setup_input_contract.py`、`review_allocation_and_features.py`、`append_raman_definition.py`为已执行增量历史，不重跑。不要重跑旧版生成、整理、下载或迁移脚本。未来继续核录请创建新批次和新版本。

验证配置用现有v0.2项目环境，未创建新环境。数据检查41项、输入检查28项、更新后的合成接口16项均通过。合成目录中的数值是软件测试，不是论文模型结果；不选择研究赢家。
''')
 write('进度与交接.md','''# 第二轮交接：循环稳定性目标不变，输入已明确

日期2026-10-17。用户要求继续细致优化、全量利用现有数据，并明确输入；用户再次强调输出是循环稳定性预测，不能重问或改目标。本轮输出沿用规定N与测试条件下的电容保持率。

本轮自前轮v0.3真实库承接到本目录cycling_v0_3r2.sqlite。前轮数据库和manifest保留。126篇/137来源全文文本检索完成，无提取失败；5539处命中只是线索。全部126篇登记用途、89条分配去向，不假称全部字段人工终审。新增针对11条记录的来源核验；加前轮35条，累计46条得到新来源核验，其余43条本轮只是明确路由，仍未获得逐字段通过。

输入定为7项：计划循环次数、循环电流密度、电解液种类、摩尔浓度、器件循环电压下限/上限、循环前成品N2-BET。第8项总孔体积为可选扩展。单位/分母/阶段是元信息。N/O、Raman、负载和制备参数继续入扩展库，不能因“全量利用”把稀疏/混口径字段强塞主模型。主模型需要实测BET，与相同合格队列的6项测试条件参照、8项孔体积扩展作预设比较。没有根据模型得分挑特征。

浓度单位已移出类别特征，M/mol/L同义，mM可精确转换；小写m、mol/kg和质量分数禁止凭空转换。电流目标口径是两片活性物总质量；单片口径需直接知道分母及两片质量才可换。主队列尚未核清分母，因此仍0准入。研究入口新增禁止训练开关，本轮只运行SYNTH软件检查。

实际增量：R013同材料表征配对，R117两材料BET/总孔体积和直接I/m定义，SRC121 BET及负载核实，R085微孔与总孔分开，R117 IG/ID与ID/IG分开，R069正文/表格配对冲突落实冻结，R112成品范围跨测试一致。BET当前38终点/27暂定材料/25篇，总孔体积24/17/16，均非最终训练覆盖。

新增REC_001 SRC025凝胶器件98%/5000次/10 A/g；REC_002 R031凝胶相关400次但无精确末端标签；REC_003 SRC005三电极CV峰电流趋势。三条仅暂存，不改正式89终点或67材料计数。

当前库126篇、137来源、67暂定材料、83暂定测试、89正式候选终点，3条暂存恢复信息；181审查事件、177变更、112材料观测、245问题。16有条件、20冻结、1主体系外、52待终审；正式训练0。41项数据核验、28输入边界检查、16更新合成接口检查通过。41项包括父库历史和原始指纹、全89/126分配、3暂存隔离、核心输入、无研究训练等。Notebook已实际只读运行。

外部状态：文献侧在本轮开始时ready=true，其旧20条审核资料哈希已核；后来用户要求下载续作，文献侧manifest变为ready=false，其余已引用内容不变。外部文献续作状态记录.json保留前后清单SHA与当前状态。此处不读取未完成新增资料作结论，不归档或合并对方成果。发起对话须等其新版ready，再核对两边manifest。

本轮manifest的共同基线仍为v0.2固定SHA，另记录直接父v0.3SHA。proposed_contract_changes必须保留：删浓度单位预测特征、核心BET必填、7+可选1输入、明确电流归一化。共同契约文件未改。合并时对方若按旧9字段准备数据，应由发起对话统一映射和复核，不强行沿用两套冲突配置。

未决：主体系循环电流分母、材料独立性、R111/SRC035 SI、R001/SRC123前作、R107继承窗口、R106/R112材料范围、R091孔体积单位等。已完成的是本轮证据/输入交付，不是科学准入已经完成。
''')
 for p in ROOT.rglob('*.py'):ast.parse(p.read_text(encoding='utf-8'))
 outputs=[]
 for p in sorted(ROOT.rglob('*')):
  if p.is_file() and p.name!='merge_manifest.json' and '__pycache__' not in p.parts:
   role='review_artifact'
   if 'synthetic_interfaces_r2_fixed_inputs' in p.parts:role='SYNTHETIC_SOFTWARE_CHECK_NOT_RESEARCH'
   elif p.suffix=='.sqlite':role='candidate_review_database'
   elif p.name=='prediction_input_contract.json':role='fixed_prediction_input_contract'
   elif 'evidence_text' in p.parts or 'evidence_images' in p.parts:role='read_only_source_derivative'
   outputs.append({'path':str(p),'sha256':sha(p),'role':role})
 parent=json.loads((ROOT/'parent_manifest_snapshot.json').read_text(encoding='utf-8'))
 manifest={'schema_version':'parallel-preparation-v1','task_role':'database','revision':'v0.3r2_all_data_and_fixed_inputs','baseline_database_sha256':parent['baseline_database_sha256'],'baseline_model_contract_sha256':parent['baseline_model_contract_sha256'],'parent_database_sha256':sha(ROOT.parent/'cycling_v0_3.sqlite'),'parent_manifest_sha256':sha(ROOT.parent/'merge_manifest.json'),'ready_for_merge':True,'outputs':outputs,'checks':report['checks'],'unresolved_issues':['Formal admitted rows remain0; first primary records current mass basis and source independence unresolved.','Other literature task is continuing and its current manifest ready_for_merge=false; no unified merge performed.','43 existing endpoints routed but not newly source-cleared; search across126 papers is not complete semantic clearance.','Missing SI, prior-work curves, material scopes and unit conflicts remain as documented.'],'proposed_contract_changes':[{'change':'Drop concentration_unit as categorical predictor; canonicalize only supported molar units.','reason':'Prevent unit spelling or incompatible concentration bases being learned as performance predictors.'},{'change':'Declare seven core physical inputs with measured precycling product BET required; total pore volume is an eighth optional sensitivity feature.','reason':'Fix prediction-time interface and stop implicit core characterization imputation.'},{'change':'Use identical admitted BET-complete cohort for protocol-only vs material vs pore comparisons.','reason':'Separate feature effect from cohort selection.'},{'change':'Declare cycling current normalization to two-electrode total active mass with evidence-backed conversions only.','reason':'Make A/g meaning consistent; no current primary rows automatically cleared.'}],'research_training_performed':False,'software_synthetic_fitting_only':True,'manifest_self_hash_excluded':True,'new_literature_archived_or_merged':False}
 assert all(sha(x['path'])==x['sha256'] for x in outputs)
 save('merge_manifest.json',manifest)
 print(json.dumps({'ready_for_merge':True,'files_hashed':len(outputs),'all_data_checks':True,'research_training_performed':False},ensure_ascii=False))
if __name__=='__main__':main()
