# v0.14：主集制备与负载参数

2026-10-22。以封版v0.13为只读父库，新增填空式参数层，原非空值、标签、用途成员、来源权重和冻结全部保持。原文/SI及旧数据库不覆写，不复制大全文索引。本轮实际拟合0次。

主集仍为**42条／30来源**；18项可选字段非空206→299/756，覆盖率27.25%→39.55%。活化温度35条/25来源，时长33条/23来源，活化升温速率23条/16来源，负载点值16条/10来源。其它用途仍是3E残留43/31、综合51/37；2E26/21、28/22、30/24，均与父版一致，嵌套集合不能相加。

```python
from data.cycling_db import open_database
from tools.material_feature_inputs_v011 import prepare_material_fold

with open_database() as db:
    dataset = db.fetch("reported_3e")
    core = dataset.feature_matrix()       # 旧8项核心和标签保持
    material = db.material_matrix()       # 原18项可选字段，补录已经生效
    recipe = db.material_matrix(
        extra_features=db.contract["model_material_features"]
                       + db.contract["process_feature_fields_v14"]
    )                                    # 额外阶段/电极字段，须预先选择用途
    inputs = prepare_material_fold(material, material["source_folds"][0])
    key = next(r["endpoint_id"] for r in dataset.rows if r["sample_name"] == "KAC-5")
    parameters = db.parameters(key)
    evidence = db.evidence(key, "activation_temperature_C")
    si = db.search_native("Fabrication", doi="10.3390/nano13101654")
```

`parameters()`返回本轮参数、前后值、作用域与直接证据。制备字段仅按相同`material_key_v11`复用，负载仅绑定审查过的测试。原`admission_profiles_v13`仍是有效成员标记，本版未变更准入，不凭属性变多给候选自动训练资格。

`heating_rate_C_min`只填活化阶段的明确升温速率；预碳化、独立碳化、前处理、水热和后处理使用带阶段的字段。没有明确活化步骤的样品保留阶段/适用性说明，不补0；微波功率不当温度，质量范围不取中点，无有效面积不转面密度。读图标签、>100%保持率和历史冲突仍原样保留。

新增阶段数值候选在`extra_material_feature_whitelist`中声明，默认18项材料特征不扩大。`None`和缺失掩码保留，编码、填补和缩放仍只在训练折拟定。`reported_3e_process_inputs.json`是输入候选快照，不是新训练结果或推荐直接使用全部字段。

详见[本轮原文审查与提升](../主集参数精提取_20261022/README.md)、`verification.json`、`training_readiness.json`及`merge_manifest.json`。只读验证可运行`python -B tools/verify_parameter_enrichment_v014.py`；一次性prepare/retrieve/curate/build工具不得原位重跑。已有模型面板仍展示v0.10历史实验，不能用本次字段增量宣称误差下降。
