# v0.12：待补证原文精细复核

2026-10-22。对v0.11固定的87条三电极待核观察逐条处置，取得5份出版社SI，保存309项逐记录字段补充或更正。新增5条主集准入，来自5个来源组。原文、父库、原值、科学冻结与既有模型实验均保留。

| 用途 | 观察数 | 来源组 | 边界 |
|---|---:|---:|---|
| `reported_3e`，默认 | 38 | 30 | 现行年度、GCD、完整8核心字段、作者报告点标签 |
| `reported_3e_residue_sensitivity` | 39 | 31 | 包含主集，另含已记录成品Si问题的Act_OFSCBC |
| `reported_3e_sensitivity` | 47 | 37 | 包含上述集合及8条近似、明确损失补数或有误差界限的原图读数 |
| `reported_2e` | 26 | 21 | 主集成员与核心数值保持原样 |
| `reported_2e_residue` | 28 | 22 | 原嵌套残留集合 |
| `reported_2e_approx` | 30 | 24 | 原嵌套近似集合 |

这些集合相互包含，不能相加作为样本总量。原277条观察全部保留。87条已完成本轮复核，其中14条获得至少一种本轮用途；仍有73条3E未获任何上述用途，包含年度范围外、CV、复合物、面积电流等。现行年度内仍有45条存在资料或图文争议缺口，具体见[逐条处置与后续证据](../待补证原文复核_20261022/README.md)。本轮没有把这些问题写成科学通过。

## 新增主集记录

| 样品 | DOI | 圈数 | 循环A/g | 保持率/% |
|---|---|---:|---:|---:|
| KAC-5 | [10.1002/ente.202201281](https://doi.org/10.1002/ente.202201281) | 10000 | 10 | 90.31 |
| RSM-0.33-550 | [10.3390/molecules28124633](https://doi.org/10.3390/molecules28124633) | 5000 | 20 | 96.3 |
| AHC-CL-TU | [10.3390/polym15234478](https://doi.org/10.3390/polym15234478) | 20000 | 10 | 99.96 |
| CMC-ZnK-800 | [10.3390/polym17091198](https://doi.org/10.3390/polym17091198) | 5000 | 10 | 94.3 |
| 稻草AC无ZnO对照 | [10.1039/d6na00276e](https://doi.org/10.1039/d6na00276e) | 10000 | 5 | 83.54 |

逐条方法、窗口、参比、材料与基准绑定见`test_reviews_v12`和`effective_reviews.json`。综述比较表不作为被引样品的新独立来源；同篇多样品始终按来源整体留出。主集最大单来源4条，来源权重按每组总和1计算。

## 读取与训练准备

在仓库根目录运行：

```python
from data.cycling_db import open_database
from tools.material_feature_inputs_v011 import prepare_material_fold

with open_database() as db:
    data = db.fetch("reported_3e")
    core = data.feature_matrix()
    material = db.material_matrix()
    split = material["source_folds"][0]
    prepared = prepare_material_fold(material, split)
    values = db.by_endpoint("incoming:ADD_027_T01")
    proof = db.evidence("incoming:ADD_027_T01", "bulk_N_wt_pct")
    rows = db.search_tables("NCHU", doi="10.1016/j.biombioe.2026.109160")
```

默认核心仍为8字段。材料矩阵的18个可选字段在38条主集上有186个非空单元，原33条视图为158个；没有丢弃旧非空材料特征。未知值保留`None`及缺失掩码；编码、缩放、填补都在训练折拟合。测试后BET/XPS/EIS、末圈比电容、样品名、DOI及保持率不进入预测列。

敏感性矩阵还输出`label_relations`、`label_evidence_kind`和`label_reading_bound_pp`。ACRS/ACEW原图约186%/146%，读图界限各±5个百分点；保持活化超过100%的原义。读图界限是保守读数范围，不是统计置信区间。作者报告的近似值未擅自赋予零误差；损失补数保持派生标记。SSK0.5约91.6%仍缺3E参比/电解液浓度，因此没有进入这47条。

`full_review_queue()`保留所有未获用途的观察，`pending_evidence()`排除明确范围/方法排除项；其中仍可能包含需要保留历史争议的旧年度记录。本文45条按当前2023—2026年度用途单独计数。所有原始SI/全文/表格检索命中都不自动授予训练资格。

## 核验与保护

[verification.json](verification.json)记录SQLite完整性、外键、原值与变更链、科学冲突冻结、同材料特征共享、旧核心/标签及可选字段保护、原图/SI哈希、去重与来源分组、折内变换和错误输入拒绝。新库只保存小型叠加层；复用v0.11及118.43MiB原生索引，不复制大父库。

```powershell
python -B tools/verify_pending_review_v012.py
```

`training_readiness.json`及各`*_inputs.json`提供已核验输入、来源折及指纹。`build_pending_review_v012.py`拒绝覆盖已生成数据库，不能原位重跑。后续修改应继续版本化。

本轮真实模型拟合0次。可开始预先计划的小样本来源分组实验；本轮没有验证误差改善，也没有证明大模型训练规模或可靠泛化。现有模型面板继续展示v0.10固定实验。
