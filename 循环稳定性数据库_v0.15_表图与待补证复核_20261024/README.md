# v0.15：已有表图与待补证复核

2026-10-24。小型只读增量层，复用封版v0.14及原全文索引，不复制大父库，不改原论文/SI或旧训练结果。

默认三电极42条/30来源，双电极26条/21来源；嵌套敏感性集合与父版相同。固定18项可选字段非空299→320/756（39.55%→42.33%）。70项字段变更中66项补空、4项ALPC的EDS/XPS测量方法纠错；原值和来源均可查。41条待补证完成逐条处置，2条明确范围外、39条仍待证，新增准入0条。实际训练0次。

```python
from data.cycling_db import open_database
from tools.material_feature_inputs_v011 import prepare_material_fold

with open_database() as db:
    core = db.fetch('reported_3e').feature_matrix()
    matrix = db.method_specific_material_matrix()
    prepared = prepare_material_fold(matrix, matrix['source_folds'][0])
    changes = db.field_changes('candidate:TE029')
    xps = db.evidence('candidate:TE029', 'XPS_N_reported_pct')
    pending = db.reviewed_pending_batch()       # 39条当前待证
    all_reviews = db.reviewed_pending_batch(include_outside=True)  # 固定41条
```

`material_matrix()`保留原18字段口径，包含作者原始报告百分数及其基准标记。推荐方法分列视图`method_specific_material_matrix()`：XPS N/O分别按明确at%和wt%输出，未知基准为空，不换算、不代入EDS。历史通用N_at_pct/O_at_pct不应被一律称为XPS；ALPC保留的11.23/8.54来自EDS，XPS已更正为4.64/7.44。

接触角、压片电导率和电解液吸收等新增量只是声明过的循环前候选，适用协议和来源数仍需在训练内审查；不默认加入下一轮所有模型。数据输入就绪不等于可靠预测已达成。旧v1.1 MAE4.75百分点来自v0.14，本轮没有重训，不能直接宣称误差改善。

完整证据、冲突与计数见[本轮报告](../已有文献表图与41条复核_20261024/README.md)、`verification.json`、`training_readiness.json`和`merge_manifest.json`。只读核验用`python -B tools/verify_existing_sources_v015.py`；禁止原位重跑一次性构建或改写父版。
