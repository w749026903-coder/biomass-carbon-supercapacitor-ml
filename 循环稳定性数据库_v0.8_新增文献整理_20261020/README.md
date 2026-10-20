# v0.8 新增文献整理与可调用数据

本版在v0.7上增加独立`incoming_*_v08`表，旧科学表、原值、冻结、准入历史和归档表保持原样。新增来源仍为暂存文献，只有18条经过逐测试审查的记录获得报告工况用途，未自动将整篇论文或其余测试放行。

| 调用profile | 记录 | 来源组 | 用途 |
|---|---:|---:|---|
| reported_3e（默认） | 30 | 22 | 普通水系碳电极、三电极GCD，8项输入 |
| reported_2e | 20 | 17 | 对称双电极普通水系GCD，7项输入 |
| reported_2e_residue | 22 | 18 | 含原已审查残留敏感性记录的嵌套集合 |
| reported_2e_approx | 23 | 19 | 再含原已审查近似标签的嵌套集合 |
| incoming_review | 82 | 见逐记录分组 | 本批全部自有测试观察，拒绝直接导出训练矩阵 |

敏感性集合不能相加；同篇多材料、不同电解液和多个端点仍按同一来源组留出。数据规模适合继续开发小样本基线，不能宣称已足够训练大模型或证明泛化精度。实际研究拟合为0。

```python
from data.cycling_db import open_database

with open_database() as db:
    dataset = db.fetch()                    # 默认3E，不混入2E或待核
    inputs = dataset.feature_matrix()       # X/y/groups/sample_weight，无拟合
    folds = dataset.source_folds(5)         # 按来源分组，编码/缩放须在训练折内
    candidates = db.incoming_tests('ADD_025')
    evidence = db.evidence('incoming:ADD_027_T01', 'BET_m2_g')
    pages = db.search_incoming('cycling', doi='10.1016/j.biombioe.2026.109168')
    holds = db.holds('incoming:ADD_052_T01')
```

除Python标准库外无需依赖。新API继承项目保留的v0.7接口文件，部署时按仓库完整目录使用；`cycling_v0_8.sqlite`包含历史表、新逐页全文、FTS检索、逐测试数据、字段观察、页码外键与逐profile准入表。直接SQL读取待审表时，须检查`eligible`、`review_status`和`incoming_admissions_v08`，不能只筛非空标签。

`reported_*_inputs.json/CSV`保存实际矩阵、标签、来源权重和指纹，JSON另存留一来源折。`data_contract.json`继续沿用v0.6报告工况合同；作者A/g作为报告描述，未知质量分母和未知精确基线圈号保留，没有换算物理电流。严格物理电流视图保持原样，不代表全部可用数据数量。

## 本轮科学处置

新增9条3E来自AUACW、A-BC-0.2、RMAC-800、CCL-K2CO3-1-700、SS-300、NPC-700-6、YZPC-3、AMFS碳、P-doped CSKOH。新增9条2E来自AUACW、OPBNP、NDB-E、CE-K-PC两种电解液、玉米秸秆PC/PC-D/PC-W及MMC。OPBNP器件链接已有候选端点，共用旧来源组，其四条已准入3E未重复收录。

证据可以是作者明确适用的GCD程序或同样品/配置/电解液的实际GCD波形，不能只从CV范围推断。2E配对保存作者原话（例如similar masses或identical electrodes），没有伪造精确活性质量。109.2%、106.3%、101.17%等活化保持率原值保留，不裁到100%。

主要冲突及处置见[原值与冲突处置](冲突处置.md)。本批64条未准入观察包含近似/不等式、预印本、设计复合物、凝胶/有机体系、配置不清、缺核心字段和未决冲突；不能全部称作可补成主集的缺数据。详见[待补证据](../新增文献整理_20261020/待补证据清单.md)。

## 核验与版本保护

父库SHA256为`65af93be781d858ea8c7a9a2b3b1515acf799be1ad8e94d2231199c9c31f95f1`。`最终核验.json`检查SQLite完整性/外键、继承表逐行指纹、原文哈希、输入33文件、ZIP成员、去重、来源分组/权重、分组留出与错误矩阵拒绝；技术通过不意味着未决科学问题已通过。

只读重验：`python tools/verify_incoming_v08_20261020.py`。构建工具拒绝覆盖已封版的`merge_manifest.json`；禁止对旧版本重跑一次性补丁。每次更正应保存新证据与历史，形成新版本。
