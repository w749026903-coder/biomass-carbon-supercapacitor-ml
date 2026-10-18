# v0.7 数据补充版

本轮新增7条三电极准入记录、4个主集来源组，继续使用v0.6报告工况合同，没有放宽标签、配置或字段要求。当前可直接读取的数据如下。

| profile | 记录 | 来源组 | 特征 |
|---|---:|---:|---:|
| reported_3e（默认） | 21 | 13 | 8 |
| reported_2e | 11 | 11 | 7 |
| reported_2e_residue | 13 | 12 | 7 |
| reported_2e_approx | 14 | 13 | 7 |

双电极三个集合仍为嵌套敏感性用途，不相加。三/双电极分别调用。同篇藜麦四样品共同留出、来源总权重为1。所有旧训练行保持原样。

```python
from data.cycling_db import open_database

with open_database() as db:
    ds = db.fetch()  # reported_3e
    matrix = ds.feature_matrix()
    X, y = matrix['X'], matrix['y']
    groups, weights = matrix['groups'], matrix['sample_weight']
    folds = ds.source_folds(len(set(groups)))
    candidates = db.candidate_sources()  # 审核用，不是训练数据
```

[training_inputs](training_inputs/cohort_summary.json)含JSON/CSV矩阵、标签、权重、来源分组、逐条复核及留一来源验证折。只按feature_names取特征，端点ID/来源/标签关系不能当预测输入。预处理器见[preprocessing.py](preprocessing.py)，现有项目环境依赖仍按[锁定文件](requirements-model-lock.txt)；没有安装全局软件。编码、缩放、可选插补及调参均限训练折，未执行真实拟合。

## 新增证据

螺旋藻SNPB-800-4用实际首尾GCD波形确认−1至0 V。SC-0.03用自身同一3E水系GCD程序和循环段落绑定。藜麦QSC/QSC-2/QSC-3/QSC-4补入自身BET表365/708/1802/886 m²/g，方法明确统一GCD窗口−1至0 V，3 M KOH原值保持不变。AC3保留通用方法正电位范围与自身多处负电位GCD图文的冲突，以一致的自身GCD/结果证据选择−0.5至0 V，详列理由和局限。各记录都使用作者报告的保持率，不从曲线另算新比值，不虚构基线圈号或电流质量分母。

见[本轮准入复核](本轮准入复核.json)、[未决与范围处置](本轮未决与范围处置.json)和[专业知识](../docs/KNOWLEDGE_BASE.md)。未知质量分母继续作为元数据，严格物理电流用途另列。主集保留超过100%的已报告值，不按高性能筛选来源。

## 候选与科学未决

本批取得15份原文XML，其中13个新身份（11篇原始研究、2篇综述），其余2个为已有身份。候选单独入库搜索：[新增来源候选索引](新增来源候选索引.json)；调用`search_candidates()`返回待审来源片段，不会混入`fetch()`。

葡萄柚方法/图轴参比冲突继续待审；YPAC-1和EUO的循环电流仍未定位；鹅毛/松木样品的铜氧化物、尿布合成聚合物前驱体和芦苇样品的g-C₃N₄相单列。Heliyon三个候选90.3/76.4/59.2%补记为100减已报告损失的派生关系，旧值和旧关系保留。没有把这些问题清成“通过”。

当前主集规模仍较小，来源与协议分布有限，适合继续开发和核验小样本基线，不能据此声称已有可靠泛化能力或足够从头训练大模型。新论文尚未自动归档，真实拟合为0。

## 核验与保护

v0.6和所有历史版本、原文/SI原位保留。观察/选择追加历史；7条准入状态变化保留旧状态快照。SQLite完整性、外键、缓存、原值、原训练行、分组、矩阵和源文件哈希见[最终核验](最终核验.json)，载荷见[交付清单](merge_manifest.json)。下一轮按[补证据队列](../数据补充_v07_20261018/下一批补证据队列.md)继续。
