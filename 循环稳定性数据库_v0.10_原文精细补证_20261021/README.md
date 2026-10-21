# v0.10 原文精细补证与调用

在v0.9基础上审查4条记录；新增BLAC900一条报告工况用途准入。小型SQLite叠加层保存本批前后值、原文证据、用途决定和训练快照，只读复用v0.9/v0.8；保留整仓库和LFS，旧版不覆写。

| 用途 | 记录数 | 来源组 |
|---|---:|---:|
| reported_3e（默认） | 31 | 23 |
| reported_2e（主集） | 26 | 21 |
| reported_2e_residue | 28 | 22 |
| reported_2e_approx | 30 | 24 |

敏感性集合是嵌套的，不能相加。新增批次82条自有观察中26条获得至少一种报告工况用途，其余56条待核或范围外；不代表全库只有这些记录，也不代表全库已终审。

```python
from data.cycling_db import open_database
from tools.training_input_quality import prepare_source_fold

with open_database() as db:
    ds = db.fetch('reported_2e')
    fold = prepare_source_fold(ds, ds.source_folds(5)[0])
    evidence = db.evidence('incoming:ADD_007_T01', 'BET_m2_g')
    holds = db.holds('incoming:ADD_007_T02')
    pending = db.review_queue()
```

折内编码、缩放和来源权重只从训练折计算；`*_nested_fold_plan.json`含内层划分和外层留出索引，均使用同一来源组规则。CSV/JSON/SQL快照、错误输入拒绝和防泄漏检查通过。没有实际模型拟合或性能指标；仅达到有边界的小样本基线输入准备质量，稀疏类别与来源数限制继续保留。

BLAC900的1260是自己材料的BET，BLAC800不能借用。对称配对依据为共同名义负载和几何加明确器件身份，非严格等质量测量。保留原文孤立Ag/AgCl说法、作者0–2V水系报告、未知A/g质量分母与未知精确基线圈号；不自动物理归一化。三电极31条及其指纹未变，旧SI/年份修正、原值和冻结链全部继承。

核验：[最终核验](最终核验.json)、[训练准备质量](training_readiness.json)、[交付清单](merge_manifest.json)。逐条出处：[本批README](../数据精细补证_20261021_第二批/README.md)、[变更台账](../数据精细补证_20261021_第二批/curation_delta.json)、[当前待补证据](../数据精细补证_20261021_第二批/当前待补证据队列.md)。

已封版目录不可重建；`tools/verify_evidence_v010.py`封版后仅只读复核，`tools/build_evidence_v010.py`对既存SQLite或manifest拒绝写入。任何后续科学更正需另做审查增量。
