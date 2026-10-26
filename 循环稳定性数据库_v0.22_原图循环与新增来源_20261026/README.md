# v0.22：原图循环补证与新增来源

基于不可变v0.21增量，保留15个氮/Raman特征冻结和完整历史。新增3条记录并补正2条既有记录；合计281观察/181来源组，不是281条可训练数据。新用途下共核定5项测试，无真实拟合。

|测试|保持率 %|圈数|作者 A/g|实际用途窗口 V|准入视图|
|---|---:|---:|---:|---|---|
|棉花CDAP800-350，3E，6M KOH|92|5000|5|−1～0|跨年份3E|
|棉花CDAP800-350，2E，6M KOH|86|5000|5|0～1|跨年份2E|
|藜麦QSC-3，2E，3M KOH|97.55|10000|5|0～1.5|原队列2E及跨年份2E|
|藜麦QSC-3，2E，1M Na₂SO₄|96.2|10000|5|0～2.0|原队列2E及跨年份2E|
|藻类NFACc，2E，1M H₂SO₄|101.7|10000|1|0～0.8|跨年份2E|

棉花2018、NFAC2019，不能放进原2023—2026研究队列。新增reported_3e_all_years=44条/32来源、reported_2e_all_years=31/25，显式由已验证旧主集加逐测试复核的早期来源构成；不自动开放其它旧候选。原reported_3e仍43/31，reported_2e增至29/23；残留敏感2E31/24，近似2E33/26，原三电极敏感44/32、52/38不变。

藜麦沿用candidate:V05:012/013，不重复建记录；BET旧空值从自身Table1 QSC-3行1802 m²/g补齐，电压来自实际循环插图。棉花2E86%由自身实际Fig11a和正文支持，摘要87/结论89保留为未选异文。真实101.7%不裁100；新鲜倍率与循环前后值分开。作者A/g保留，未知质量分母及精确基线下标仍未知，不从公式推算。N未检出不填0，XPS质量百分比不混为原子百分比。

统一入口data.cycling_db.open_database；fetch/by_endpoint/evidence/holds/field_changes/material_properties/literature_links全链只读。feature_matrix验证所声明队列、测试体系、真实条件、缺失与有限数值；method_specific_material_matrix保留缺失掩码，不插值、不拟合。来源权重各DOI和为1；同论文材料、工况、端点、辅助与曲线必须整体留出。

verification.json记录SQLite完整性/外键、父版全部产物SHA、原值/变更链、旧观察与15冻结保持、5链接、计数、全部来源折、缺失掩码、跨年份筛选与异常输入拒绝。原39条固定补正仍1完成/38待证，不能抵扣。protected_inputs.json绑定原文、原图、v10和v0.21。未封版草稿曾修复用途年份与BET绑定；旧封版没有覆写。

只读核验：`python -B tools/release_cycle_admissions_v022.py verify`；全链`python -B tools/verify_corpus_chain_v10.py`。不要重跑build/repair/seal。本文与原模型评价不构成新精度证明，所有模型拟合为0。
