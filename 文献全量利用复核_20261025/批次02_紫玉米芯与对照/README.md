# 第二批：紫玉米芯自身材料、分方法比电容及合成碳对照

2026-10-25。持续目标已由用户明确要求建立并启动，见[全量提取目标](../../docs/LITERATURE_EXTRACTION_GOAL.json)。本批完成指定表格范围，全部现有文献提取目标仍进行中；没有开展新训练。

本批新增9种材料的69项数值和4个“低于误差”空值；证据层累计24材料、157项材料数值及4个受限空值。新增41条分方法/电解液比电容记录，39个数值、2个未报告空值；其中包含8条EIS分表复述/竞争及1条合成碳参考，不能称为39个独立样本。另增紫玉米芯AC-10%循环候选1条，现有7条候选均无训练资格。现行循环主集仍43条/31来源，原固定39条仍1完成、38待证。

## 原文核定与适用范围

紫玉米芯论文 DOI **10.1021/acsenvironau.3c00048**：正文Table1及SI Tables1S、2S、3S、7S、8S、9S。孔结构、Raman强度比、EDS口径未知百分比、XPS原子百分比分开。SI的AC-0%作为无活化对照保留，不自动合并主文AC别名。AC-30%的四个“-a”对应脚注“Below the error”，不是零，也不是作者未报告。SI其余表和全部曲线尚未完整提取。

比电容表分CV、GCD、EIS和F/g、F/cm³，酸/碱各自保留。正文自身Fig4及Fig6图注明确CV5mV/s、GCD0.5A/g；方法2.3为三电极、Ag/AgCl(3M KCl)、1M电解液。EIS为OCP、幅度0.005V、0.01–1000Hz，不能给它赋CV扫描速率。SI Table7S的AC-5%酸/碱EIS为70/25F/g；Tables8S/9S分别25/70F/g，四原值同存并冻结标准值，不自动交换列。

摘要明确50000圈保持率76%。但方法写三电极生命周期、器件方法写2E/酸液，Fig7示意与图注写2E/KOH，波形纵轴仍带Ag/AgCl参照；正文另写6A/g循环、1A/g读数。故配置、电解液与循环电流标准字段保持空，不据电容公式猜电流分母。76%候选不是库准入，不能将充放电效率98–99%混作保持率。

AC-30%XPS表C1s标532.0eV、O1s标284.5eV，与元素指认冲突；保留作者标注下80.00/17.59at%，状态限定并冻结，不擅自换C/O。微孔率表未给面积/体积比例基准，不用面积之比替换报告百分数。

合成碳对照 DOI **10.3390/molecules29225413**：正文Table1、SI TableS1和TableS2。自身原料为resorcinol/formaldehyde，未报告生物质来源；4材料20项数值留作方法参考，不纳入生物质主训练范围。S2只抽自身C1的261.9F/g、1A/g、6M KOH；GCD由自身正文结果段明确，六行前作不变成自身样本。此条配置尚未绑定，方法细节须后续按原文2.4补充。

## 可调用与复核

```python
from data.literature_v2 import open_literature_database
with open_literature_database() as db:
    material = db.facts(doi='10.1021/acsenvironau.3c00048', sample='AC-10%')
    gcd = db.capacitances(method='GCD', electrolyte='H2SO4')
    conflicts = db.issues(doi='10.1021/acsenvironau.3c00048')
    reference_scope = db.scopes()
```

新接口按每张表返回实际正文或SI路径、SHA及定位；旧data.literature_db保留v1封版代码，不用于新SI的文档出处解释。稳定指针data/current_literature.json注明新API。SQLite只读、外键和索引可直接调用；material_facts是材料层，capacitance_observations是测试层，source_group用于来源整组隔离，均不自动赋训练资格。

核验命令：`python -B tools/extract_literature_material_pool_v2.py verify`。404项包括原件、父库/循环指针、逐XML行、已渲染SI与原生文字行、源单元、数值与空值、方法分离、来源组和零自动准入。SI分组表头由agent看原页核对，未冒称人工复核。工程核验通过不解决科学冲突。SQLite四个“-a”状态在封版前由通用空值改为低于误差，原值/数值均未变，保留preseal_validation_repair.json。

本批处理8个原始表候选，其中两个候选各含两张表。累计17张表单元关联15个原始候选，944个候选尚未进入本流程处理；“已处理”仅指记录内声明的提取范围，不能推断整篇或全部参数完成。历史725项材料属性全部建立出处对账，其中171项与候选表有相同源SHA，但只是同源线索，不是单元匹配或新计数，不相加冒充882项独立新事实。

继续顺序：核对CNF/MWCNT复合体系全文/SI及其用途；优先其它未利用的生物质自身多样品表；补制备阶段和多工况曲线；逐项解决协议冲突和固定38条缺证；全量覆盖足够后再定模型计划与输入预检。原PDF/XML/SI、v1证据层、v0.1–v0.19循环库及旧模型保持。
