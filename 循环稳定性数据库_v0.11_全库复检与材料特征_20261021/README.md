# v0.11 全库复检与材料特征版

当前3E报告工况主集33条/25来源组；2E主集26条/21组，两套嵌套敏感性集合仍28条/22组及30条/24组，不能相加。父v0.10/v0.9/v0.8只读保留，新SQLite约1.64MiB，保存当前行视图、逐材料证据、前后变更与用途成员关系。

本轮新增OAC623（85.5%、1000圈、0.1A/g、2MNaOH、SCE）和EUAC1-60（89.9%、10000圈、1A/g、1MKOH、Hg/HgO）两个独立来源。旧31条核心及标签未改。训练视图新增或补齐186个材料属性单元，Raman25条，明确原子N/O各10条；完整数据说明见[全库复检报告](../全库复检与特征补提取_20261021/README.md)。

## 直接调用

在仓库根目录使用现有Python环境，无需安装全局软件：

```python
from data.cycling_db import open_database
from tools.material_feature_inputs_v011 import prepare_material_fold

with open_database() as db:
    core = db.fetch("reported_3e")
    print(len(core.rows))  #33
    material_inputs = db.material_matrix()
    first_fold = prepare_material_fold(
        material_inputs, material_inputs["source_folds"][0]
    )
    #X_train/X_validation已在训练折内编码；这里不执行模型拟合。
    print(first_fold["feature_names"])
```

`db.fetch().feature_matrix()`继续提供可复核的完整核心8字段矩阵。**需要使用本轮新增材料特征时调用`material_matrix()`**，不要把旧实验的31条冻结快照或核心矩阵当作已使用新特征。原始材料矩阵保留None和缺失掩码；训练折编码生成显式缺失标志，不把数据库空值改为0。

`prepare_material_fold`在训练来源内计算来源等权均值/尺度、类别词表；未知验证类别独立编码。稀疏额外数值字段若少于2个已观察训练来源，该折禁用其数值通道并记录原因。该固定覆盖规则在折内执行，不看标签、不用验证数据选择字段。来源/材料键、样品名、标签、循环后EIS/XPS等不进入预测字段。

如需仅采用明确原子口径的化学字段，可调用`db.material_matrix(extra_features=["N_at_pct", "O_at_pct"])`；作者百分数基准未明的材料在此保持None，不用报告百分数回填。

## 查原文、表格和证据

```python
with open_database() as db:
    #完整原生文本，不局限于自动关键词片段；结果本身不代表准入。
    passages = db.search_native(
        "NCHU20", doi="10.1016/j.biombioe.2026.109160"
    )
    #保留表头/单位/原始单元，PDF布局表仍需要视觉绑定。
    tables = db.search_tables("QSC", doi="10.1021/acsomega.3c04692")
    field_evidence = db.evidence("candidate:TE021", "Raman_ID_IG")
    history = db.holds("legacy:R087_CY01")
    pending = db.full_review_queue()
```

`by_endpoint`、旧`by_alias`和`incoming_tests`也返回当前顶层有效属性；嵌套`fields`、原始issues及历史审查结构保留溯源。单记录查询不附带队列特定权重，来源权重由`fetch(profile)`确定。

212项材料属性按`material_key_v11`关联自身材料，同时保留原material_id及旧身份；同论文多样品不成为独立来源，ALPC两种工况共享材料属性但仍是两个测试。质量负载是配置/测试属性，本轮3E负载不传播给2E器件。物理统一电流仍缺证保持未知，默认报告工况用途不因此受阻。

全文索引引用只读父文本和新增原生段，查询校验上游文本指纹。当前指针校验v0.11 SQLite，合同校验父库指纹，封版清单校验索引、API、输入快照及文档。`all_review`与待审队列不能导出已准入训练矩阵。

## 状态与复核

- [数据合同](data_contract.json)、[训练输入预检](training_readiness.json)、[稀疏材料输入](reported_3e_material_inputs.json)。
- [独立核验](../全库复检与特征补提取_20261021/independent_verification.json)、[字段变更](../全库复检与特征补提取_20261021/record_field_changes.json)、[逐测试队列](../全库复检与特征补提取_20261021/逐测试利用与待补证据.csv)。
- [表格/全文/来源去向](../全库复检与特征补提取_20261021/README.md)及[需补资料DOI](../全库复检与特征补提取_20261021/需补资料_DOI清单.md)。

本轮拟合0次，未重跑或覆盖旧两轮实验。稀疏输入与分组预检通过，只说明输入和调用可用，不证明误差已经改善或足以训练大模型。仍有87条3E观察待核，4条新增同篇样品测试继续暂存；原值、冻结与未选证据均保留。

不要重跑已完成建库/下载工具或原位覆盖本版。需要复核可运行`python tools/verify_full_review_v011.py`；后续增量使用新版本。
