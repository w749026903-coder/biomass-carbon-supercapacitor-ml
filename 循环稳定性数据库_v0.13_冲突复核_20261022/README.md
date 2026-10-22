# v0.13：冲突复核与来源覆盖

2026-10-22。在封版v0.12上增加16条已复核记录的小型叠加层，旧数据库与118.43 MiB全文索引原位只读复用。新SI、原图处置及限制见[本轮报告](../冲突复核与来源充分性_20261022/README.md)。35项字段补充/更正；四个同篇AHPC样品补足报告工况用途审查，未给真实图文冲突直接准入。

| 用途 | 测试条数 | 来源组 |
|---|---:|---:|
| `reported_3e` 默认主集 | 42 | 30 |
| `reported_3e_residue_sensitivity` 含Si残留 | 43 | 31 |
| `reported_3e_sensitivity` 含近似/派生/读图及残留 | 51 | 37 |
| `reported_2e` | 26 | 21 |
| `reported_2e_residue` | 28 | 22 |
| `reported_2e_approx` | 30 | 24 |

每个系统内的敏感性集合均为嵌套集合，不能相加。来源总权重相同；同篇AHPC五样品作为一个组。所有277条观察和旧主集核心/标签保留；年份2023–2026、至少1000圈、GCD及原范围边界保持。

```python
from data.cycling_db import open_database
from tools.material_feature_inputs_v011 import prepare_material_fold

with open_database() as db:
    dataset = db.fetch("reported_3e")
    core = dataset.feature_matrix()
    material = db.material_matrix()
    fold = material["source_folds"][0]
    inputs = prepare_material_fold(material, fold)  # 只做折内准备，不拟合
    review = db.holds("legacy:R018_CY01")
    evidence = db.evidence("incoming:ADD_059_T01", "micropore_volume_cm3_g")
    si = db.search_tables("LCC-3", doi="10.1016/j.indcrop.2026.123626")
```

`baseline_references`保留表格作者循环保持率语义及未知下标，未借其它样品曲线。C-4的26.32%在`preferred_retention_derivation_v13`中可追溯，旧候选标签未替换，也未进入训练矩阵。新准入字段为`admission_profiles_v13`，旧v0.11/v0.12字段仍是历史；查询当前准入请用`fetch`、`holds`或`admission_checks`。

`evidence(endpoint, field)`尊重每段证据的字段清单；新字段仅返回直接适用的证据。`search_native`与`search_tables`能检索新SI，但命中不代表训练准入。`by_alias`继续定位当前端点；`full_review_queue`含所有未准入，`pending_evidence`还需结合年度/体系筛选。本轮具体41条现行3E队列见批次JSON。

默认核心8项完整；18项可选字段206/756非空，仍保留None和缺失掩码。仅达到探索性分组基线输入质量，不代表可靠泛化或大模型规模。现有可视化面板仍展示v0.10两轮实验；本轮实际拟合0次，没有产生新的模型精度结论。

核验见`verification.json`，输入预检见`training_readiness.json`，交付哈希见`merge_manifest.json`。只读复核可运行`python -B tools/verify_conflict_review_v013.py`；不要重跑一次性review/build工具或覆写任何封版。旧API及已交付版本均保留。
