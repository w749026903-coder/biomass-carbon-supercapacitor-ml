# v0.19：摘要与制备漏项补正

本轮按现有原文纠正提取遗漏，新增46项字段，涉及AF-MMTC六种自身样品。原277观察、主集43条/31来源、所有标签/成员/来源组及旧冻结保留；新增准入0、真实拟合0。固定39条目标仍仅CMC1条完成，剩38条/24来源。

原文摘要明确AF-MMTC5自身比表面积1772 m²/g、microporous content41%。此前把六样品一律记作“无自身数值”不准确。现保存为reported_specific_surface_area_m2_g_v19等四个带口径字段。全文只报告ASAP2020孔结构仪器和N₂吸附图，未明确1772的面积计算法，BET_m2_g仍为空；41%的面积/体积基准未知，不推算微孔面积或体积。

六样品各补6项明确制备参数，共36个数值单元：初始氮气碳化800℃、2 h、5℃/min，经HCl/HF去模板，再进行KOH活化800℃、2 h、5℃/min。是两个独立热处理阶段；另存六份分阶段出处及各自KCl添加量。它们属于同一论文，不是36个独立实验或6篇新文献。

23466项核验覆盖SQLite完整性/外键、逐原值与变更链、旧载荷、全部来源权重、训练矩阵一致、材料查取与摘要检索。新字段中只有已有合同的制备项进入可选材料字段；仍未准入的样品不会进入训练。原文和旧模型哈希未变。

```python
from data.cycling_db import open_database
with open_database() as db:
    sample = db.by_endpoint('candidate:TE017')
    area = sample['reported_specific_surface_area_m2_g_v19']  #1772，方法仍待证
    holds = db.holds('candidate:TE017')
    evidence = db.evidence('candidate:TE017', 'reported_specific_surface_area_m2_g_v19')
    hits = db.search_native('1772', doi='10.1039/d4ra08818b')
```

只读复核：python -B tools/release_abstract_corrections_v019.py verify。不要重跑build或seal；旧版本保留。构建期修正过一个XML摘要定位（.//p0实际为作者注），记录在本批preseal_locator_repair.json；封版前已核验，数字未改变。

原始证据及新的全量文献利用方向见[本批说明](../持续补正_v017_20261024/resumed_20261025/README.md)。模型路线应以现有文献可提取的信息为基础，不以当前43条反过来界定文献利用范围。
