# v0.16只读数据库

本版小型SQLite增量依次复用v0.15及之前版本，不复制原118MiB全文索引。57项补录作用于3条冻结候选；新SI和读图证据可检索。训练成员、默认预测特征、标签/权重保持，主集仍42条/30来源，待证39条/25来源；没有新增准入或模型拟合。

```python
from data.cycling_db import open_database

with open_database() as db:
    dataset = db.fetch('reported_3e')
    matrix = db.method_specific_material_matrix()  # XPS原子/质量口径分开
    record = db.by_endpoint('legacy:R081_CY01')
    evidence = db.evidence('legacy:R081_CY01', 'EDS_Fe_wt_pct_v16')
    holds = db.holds('incoming:ADD_016_T02')
    pending = db.reviewed_pending_batch()  # 39条，包含新旧审查版本
    hits = db.search_native('0.3315', doi='10.1186/s42825-023-00122-w')
```

`field_changes(key)`返回本版增量；`include_history=True`额外返回父版v0.15增量，并非所有早期数据库的完整变更表。早期证据和冻结仍通过`evidence`、`holds.previous_holds`和父版文件追溯。`material_properties`保留选中与历史状态；某字段补齐不自动赋予该材料训练资格。

新检索结果`reading_kind=native_text`为附件原生文本/表格，`agent_reviewed_image_transcription`为agent核图转录，不冒称OCR原文或独立专家签字。所有命中`training_eligible=0`；API题录响应不纳入“方法全文”。源路径/SHA/定位均保留。

Fe的EDS与bulk、XPS分列，EDS不能判化学态；N1s组分比例不当整体N%。LWCA的正式图与预印本同一来源组；部分协议/BET有明确预印本版本标记，正式方法尚待核验。原81.3%与图81.37%竞争证据另存，未改旧标签。面积表头冲突未隐去，BET采用作者正文明确的1780/1996m²/g，未把表格精确值强制换单位。

详见[本轮证据报告](../补证与测量口径复核_v016_20261024/README.md)、[数据合同](data_contract.json)、[核验](verification.json)、[交付清单](merge_manifest.json)。`ready_for_training_inputs`仅表示已有准入集合的数据工程检查通过；不是所有候选通过，也不是模型精度改善。旧v1.0/v1.1成绩属于历史实验，不能换成这次数据版本的成绩。
