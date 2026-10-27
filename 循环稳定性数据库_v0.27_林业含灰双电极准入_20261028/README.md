# 循环v0.27：林业含灰双电极逐测试准入

三条既有端点 candidate:B20:B2_004:1/2/3（PAC/SAC/LAC）补齐自身循环前BET2813/3565/2981 m²/g、适用的0～1 V压片GCD程序、作者保持率初始参照及材料范围证据。保持率88.31/93.10/93.53%、10000圈、3 A/g、6 M KOH、2023年份、样品/材料/测试/曲线ID均保持原值；没有新增实验或观察行。

现行第四轮合同已明确“biomass carbon main; residue-inclusive sensitivity separately declared”。原文报告灰分与Al(OH)₃杂质，因此只纳入现有reported_2e_residue及其嵌套reported_2e_approx，不进入普通双电极主集、普通跨年份主集或严格物理电流用途。三材料同一DOI，来源权重各1/3；文献v22的材料、前驱体、氢存储另批、两电解液电容、所有候选及其它任务一起隔离。

- reported_2e：仍31条/25家族；reported_2e_all_years：仍33/27。
- reported_2e_residue：33/26增至36/27；reported_2e_approx：35/28增至38/29。两个用途嵌套，不能相加。
- 三电极四个用途仍45/33、46/34、54/40、49/36。
- 全部观察仍286条/185原始来源组；新端点0，既有端点按残留用途准入3，新增来源家族仅1。
- 原固定39条仍2解决、37待证/23来源；三条不在该39条及历史41条审查视图内，不能抵扣37。

BET选原样品SSA_AC而非去灰折算；TGA空气燃尽的作者碳分数不是元素C，Al(OH)₃具体质量分数未报。主表3/Fig8为8:1:1压片电极，不是未取得SI中的SiO₂/GO涂布配方。MainP21明确两相同电极、3 A/g水系10000循环；Fig8b给同电池压片GCD程序0～1 V，该程序绑定显式标作适用共同GCD程序，不能称Fig8e单独绘出了循环电压。保持率直接用Table3自身列，作者初始参照保留，精确循环下标和物理电流质量分母仍未知。

原值、旧遗漏、旧审查与冻结均保留；新的evidence_v27/changes_v27记录前后值、出处和理由。1904项核验覆盖原表、原件SHA、283条其它观察、所有旧矩阵/标签元数据、八个队列、37/41固定审查、四个苏铁绒掩码、完整历史链，以及必需输入缺失/无成员资格/普通用途误混的拒绝测试。原101.7%未裁剪，没有真实拟合、发布或外部资料下载。

稳定入口data.cycling_db.open_database()；显式调用fetch('reported_2e_residue').feature_matrix()或reported_2e_approx。new_residue_purpose_rows.csv列出新增准入的三条既有端点，model_inputs_preflight.json给八个队列预检。单一新增DOI的三条不能作为三次独立来源验证。

封版后只读执行：python -B tools/verify_forest_cycles_v027.py verify。不要再次运行build/prepare/seal。文献层仍v22，全量文献利用目标仍active，731候选及已有来源剩余波形/SI、原37待证继续推进。
