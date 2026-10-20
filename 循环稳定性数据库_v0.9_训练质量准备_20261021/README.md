# v0.9 训练质量准备（2026-10-21）

当前数据已通过训练输入质量检查，可以开始按文献来源分组的小样本基线实验。本版没有运行模型拟合，也没有把所有文献写成合格训练样本。数据量和覆盖仍不足以证明可靠泛化或支撑大模型训练。

| 数据用途 | 记录 | 来源组 | 本轮变化 |
|---|---:|---:|---|
| reported_3e（默认） | 31 | 23 | 新增NCHU20自身循环GCD窗口补证 |
| reported_2e | 25 | 20 | 新增菊花碳两个工况、MF、LYS、CLK100C10 |
| reported_2e_residue | 27 | 21 | 同上，保留原残留敏感性范围 |
| reported_2e_approx | 29 | 23 | 同上，另准入CA-700的approx84.6% |

后两个是嵌套敏感性集合，不能相加。原82条自有测试观察中累计25条获得至少一种报告工况用途，57条仍待核或范围外。新增7条用途准入中6条为精确主集记录，1条只用于近似敏感性；另2条仅补字段/年份，未放行。

## 已达到的质量要求

必需输入和标签完整、有效；实际3E/2E配置分开；同源材料与条件不跨验证组；重复检查使用样品、配置、电流、圈数、电解液、窗口与参比的完整条件键；来源总权重相同；未准入记录不进入主集；原值、替代说法与证据可查；不把标签或测试后表征当输入。

已导出真实矩阵、CSV、留一来源外层折和训练来源内的五折内层计划。数值标准化和类别字典仅由当前训练折计算；验证集新类别进入明确的UNKNOWN列。改变验证集数值、类别和标签不会改变训练编码；来源内随机拆行会被拒绝。额外提供去掉报告电流的对照准备，用来在后续获授权训练时检查报告口径敏感性。

这些检查回答“训练输入能否安全、清楚地交给实验流程”，不证明模型效果。当前3E的Na2SO4、SCE及硫酸亚汞参比、2E的Li2SO4与乙酸钠等类别只来自单一来源，不能据此宣称已能学出稳定类别效应。后续应报告按来源验证的误差与不确定性，不使用随机按行划分来宣称新文献泛化。

## 直接调用

```python
from data.cycling_db import open_database
from tools.training_input_quality import prepare_source_fold

with open_database() as db:
    dataset = db.fetch('reported_3e')
    raw_inputs = dataset.feature_matrix()
    outer = dataset.source_folds(5)[0]
    prepared = prepare_source_fold(dataset, outer)
    # prepared: X_train / X_validation / y_train / y_validation /
    # feature_names / training_only_schema / source weights
    control = prepare_source_fold(dataset, outer, drop_reported_current=True)
    evidence = db.evidence('incoming:ADD_026_T02', 'BET_m2_g')
    readiness = db.quality_readiness()
```

函数只准备数据和折内编码，不创建或拟合估计器。内层计划文件的每项包含`train`、`test`和`outer_holdout`，可直接传给同一函数；外层留出数据不参与内层编码或参数选择。数值统计与编码可直接交给后续RF/XGBoost等流程，不能再次先在全量数据上拟合预处理。

SQLite可以直接读取已物化训练记录：

```sql
SELECT endpoint_id, source_group,
       json_extract(row_json, '$.BET_m2_g') AS BET_m2_g,
       json_extract(row_json, '$.retention_pct') AS retention_pct
FROM training_rows_v09 WHERE profile = 'reported_3e';
```

## 存储、证据与边界

`cycling_v0_9.sqlite`只保存补证历史和最新训练快照，复用已封版v0.8父库，不再复制完整历史SQLite。Python接口检查v0.8父库SHA256后以只读方式打开；迁移时保留完整仓库并取齐Git LFS。单独的v0.9 SQLite可以查询训练快照，历史逐页证据仍依赖v0.8及原文。

新增官方SI位于[本轮数据补证](../数据质量优化_20261021/README.md)，身份经DOI→出版社PII→SI题名/作者复核。MF/LYS的BET为2773/2721 m²/g，LYS窗口来自自身SI FigS7；未借MF窗口代填。CLK100C10的配对依据来自其SI的共同制备、报告负载与几何参数及主文明确对称器件，未伪造已测等活性质量。NCHU20窗口由自身循环插图按0.1V轴精度读取，保留图像精度局限。CA-700保持近似标签，不进精确主集。

作者报告A/g的未知质量分母、未知精确基线圈号继续保留。没有把电容公式的分母当电流分母，也没有把严格物理口径0条当作全部不可用。当前57条未准入观察的冲突、预印本、复合物、特殊电解液及缺证问题仍保持。

详细核验：`最终核验.json`；可复现的检查与准备代码为`tools/verify_quality_v09.py`、`tools/training_input_quality.py`。构建工具拒绝改写已封版版本。`training_readiness.json`中的“ready”仅指本用途数据准备，`formal_model_fit_authorized=false`。
