# 循环 v0.24：苏铁绒两个跨年份三电极用途

原始研究 DOI10.1039/d2ra02141b，2022年。v12文献层候选经逐测试审查后，本版新增同一CF-HPC-2材料的两条报告工况循环端点；一篇来源、一种材料、两种电解液，不能当两篇独立论文。

| 端点 | 电解液 | 保持率 | 圈数 | 作者电流 | 匹配自身GCD窗口 |
|---|---|---:|---:|---:|---|
| v24:CFHPC2_KOH_3E_C10000 | 6M KOH | 96.71% | 10000 | 1A/g | −1～0V vs Hg/HgO |
| v24:CFHPC2_Na2SO4_3E_C10000 | 1M Na2SO4 | 96.36% | 10000 | 1A/g | 0～1V，共同Hg/HgO协议 |

两个印字端点来自实际Fig8f，电流由该图注明确给出。正文20说明三电极及Na2SO4沿用共同方法；正文8给出Hg/HgO。窗口依据自身同材料/同盐GCD Fig7b/e与Fig8b/e及共同协议，不冒称取得逐圈原始GCD文件。1M三电极Na2SO4与2M双电极器件Fig9分开。

只进入`reported_3e_all_years`。原2023—2026普通3E仍43条/31来源家族；2E30/24及其它旧敏感队列保持。跨年份3E从45/33变47/34，跨年份2E32/26保持。全部观察284条/183原始来源组，不全部是训练记录；两新行在矩阵权重中各0.5，总来源权重1，任何来源折都一起留出。

材料BET516.7m²/g、总孔容0.33、微孔容0.14、微孔面积268.31、Raman峰强度比0.91可用。XPS N/O摘要与Table1竞争继续保留：3.54和4.09两套原值均存证据，N/O及报告百分比别名通道保持null；不是经循环准入就解决了成分争议。CF控制样品身份未决不借给HPC2；计算密度不冒称实测密度。

700℃2h、Ar、5℃/min为一次共同炭化/活化，不填独立后活化温度/时长。约2.5mg/cm²保留作者近似标记，不变成精确称量。电流质量分母及精确基线圈下标未知；使用作者初始比电容参照，不猜第1圈，不从电容公式推定电流分母。

```python
from data.cycling_db import open_database
with open_database() as db:
    ds = db.fetch("reported_3e_all_years")
    matrix = ds.feature_matrix()
    folds = ds.source_folds(5)
    row = db.by_endpoint("v24:CFHPC2_KOH_3E_C10000")
    proof = db.evidence(row["endpoint_id"], "retention_pct")
    masks = db.feature_conflicts_v24()
```

矩阵和来源折同用既有前作家族规则。N/O原子/重量通道都保留缺失；其它明确材料特征不被连带抹掉。新版本不拟合或插值，不承诺误差下降；旧模型成绩仍对应旧输入。原固定39条中1完成、38待证以及15格历史特征冻结保持；本材料新增的N/O屏蔽单独记录，不抵扣原待证。

本版为只读增量SQLite，v0.23及所有父版、v12文献、原XML与原图均保留并保护哈希。`identity_audit.json`确认旧循环源组/样品/别名无重复；`protected_inputs.json`、`verification.json`、`model_inputs_preflight.json`和`chain_verification.json`记录证据与验证。

只读复核：`python -B tools/release_cycas_cycles_v024.py verify`、`python -B tools/verify_cycas_chain_v024.py`。不要重跑封版build/seal。

接续仍须核读芒果核、废皮革、糠醛渣、商业活性炭等已有来源及828个未触及表候选、各部分来源剩余正文/表图/SI。工程通过和本版两条用途不构成全量完成。
