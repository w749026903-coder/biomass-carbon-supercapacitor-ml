# 第六批：剩余SI、DES协议与可调用输入

2026-10-26。父库v5保持原样，本批追加到literature_material_pool_v6.sqlite；循环库保持v0.20。全量文献利用目标继续active，尚未完成。

## 本批成果与计数

| 项目 | 本批增加 | 累计 |
|---|---:|---:|
| 材料登记 | 2 | 86 |
| 材料数值单元 | 71 | 862 |
| 全部材料单元（含空值） | 103 | 908 |
| 比电容报告 | 2（自身SI复述） | 295（293数值、2空） |
| 实际表格 | 7 | 63 |
| 制备阶段记录 | 1（共同系列继承明确标记） | 57 |
| EIS拟合参数响应 | 60 | 172项各类独立响应记录 |
| XRD峰 | 6 | 6（不计为6个d002） |

两种新增登记为NWJPC-2.5和碳化前raw_glycogen。数值单元包含同源复述和方法限定字段，不能作为独立实验数。当前16篇来源仅完成所声明范围，未声称整篇充分利用。93证据单元=63真实表+27数值叙述+1既有图读数+2本批协议原图审查。原959自动候选中55个处理了指定范围、904个尚未进入本流程；新取得锦带花SI表不属于原959分母，不扣减原队列。

## 原文范围与科学处理

- 锦带花DOI10.1016/j.isci.2026.117248：SI物理p6 TableS1的NWJPC-2.5，6项自身孔结构；BET2308 m²/g，介孔+大孔1.62 cm³/g保留组合口径。共同系列800℃/2h、KOH比例和水热4h是明确继承字段，水热温度继续未知；没有给2.5样品转借NWJPC-2电化学标签。
- 糖原DOI10.1021/acsomega.3c00816：SI物理p8～11的S1～S6，按curation_spec声明自身行提取。XPS原子百分比的ND（未检出，限值未知）、横杠（未量化）和缺失测量分别保留；原始糖原不移植到碳化样品。Raman的均值、作者±和派生La分列。
- XRD的6峰包含30个描述值，只有两条(002)峰形成d002。5h自身表3.7 Å及23.9°与Bragg几何检查相符，选择0.37 nm；正文3.8 Å作为异文保留。1000℃1h的Raman±0.004/±0.007同时保存，不猜SD/SEM。
- EIS共12样品×5参数=60响应，均值和作者±保留。Q与Wd按SI单位存储，不当成一般电容或预实验材料特征；“±s confidence intervals”未报置信水平，不自造95%。
- SSE器件802 F/g的电流：原正文0.01 A/g保留；实际Figure11e的0.1→10 A/g注记与图注、正文另一处支持0.1 A/g，API返回所选值并附原值和证据，不改父库。
- SI S6的自身657/703 F/g、99%/75%为已存在样品的复述，不新增训练实验。3E的99%在主表100±2%范围内，两种报告保存，均值用途采用有作者±的自身Table3，不平均或假称作者勘误。

## DES两项目的输入

12组液态3E样品分别通过两个用途审查：首圈比电容均值、1000圈保持率均值。每目标12行，合计24条用途审查对应同12样品、同1个DOI，不能作为24个独立实验或外部来源检验。

自身Table3将首圈电容与1000圈保持率在同一行绑定于1 A/g、30℃的共同协议；Figure10实际显示各样品0～1 V首圈GCD，SI物理p3～4确认液态体系/银丝伪参比。按既有“自身表格＋共同协议”和适用自身GCD程序规则，可用于独立DES作者报告均值用途，未增设每圈都必须绘图的门槛；后续每圈独立电压图未展示的事实仍明示。固态Figure11d是10 A/g前8圈，不能借给1 A/g、1000圈的器件测试。

ethaline为ChCl:EG=1:2摩尔组成，不是2 M；不混入普通水系3E/2E循环集。作者A/g未强行换成统一质量分母。原始层training_eligible仍0，用途资格由purpose_reviews_v6逐行另存；本批普通水系循环新增准入0，实际拟合0。

```python
from data.literature_current import open_literature_database
with open_literature_database() as db:
    facts = db.facts(doi="10.1021/acsomega.3c00816")
    peaks = db.diffraction_peaks()
    eis = db.eis_fits()
    rows = db.des_reported_inputs("retention")
    matrix = db.des_model_inputs("retention") # X/y/mask/groups/weights/作者±分开
    capacitance = db.des_model_inputs("capacitance") # 另一个目标，不能拼y
```

matrix保留可选null及掩码，不插补0；特征白名单不含DOI、样品ID、作者±、目标、其它同测试响应或EIS拟合量。全部12样品/所有目标按同DOI整组隔离，目前只有1个来源，无法验证跨来源泛化。用途合同见purpose_contract.json。两份model_inputs.json可直接读取；历史命名的DES_*_preparation.csv现为已审用途的扁平导出，资格以字段和合同为准，不从文件名推断。

四个既有辅助GCD任务逐行保持：103/5/5/6，共119行、8 DOI组。普通水系循环3E43/31、2E27/22和原固定38条待证均保持，不因这批单独DES用途而减少。

## 核验与剩余工作

590项核验覆盖SQLite完整性/外键、父表原值保留、队列身份、转录单元与数值/单位、ND/横杠、继承字段、变体、电流裁决、用途审查、矩阵维度/空值/特征边界/整组隔离、原文件SHA及只读性。prepare_reports与另一个Python进程verify比对JSON和导出文本；封版再检查全部载荷SHA。可运行：

```text
python -B tools/extract_remaining_si_v6.py verify
python -B tools/verify_new_source_v020.py
```

build/prepare_reports/seal只用于本批未封版阶段，不重跑。原文、父库、v0.20、旧模型和审计链未覆盖。截图是本批证据引用，保留；本批未执行删除，空间回收0。没有以自动索引、工程通过或这两篇的部分提取声称全部利用，下一批继续已有原生表图及木苹果壳循环原图的数值电流核查。
