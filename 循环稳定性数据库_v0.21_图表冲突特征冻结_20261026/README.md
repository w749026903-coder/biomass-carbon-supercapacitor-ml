# v0.21：图表冲突特征冻结

新核读藻类原图3d/e发现与表3/4的氮含量、拉曼比值不一致。增量库只将五个既有循环端点的N_at_pct、XPS_N_reported_pct、Raman_ID_IG选值设为null，共15格。原表/图两值及旧选值保留；不填0、不择最新/最高，不删除样本，不改变原循环标签或准入。

仍278观察/179来源组；普通3E43条/31来源、2E27条/22来源；原固定队列1完成、38待证。18条新辅助GCD与该DOI的五条循环记录共同来源隔离。没有新模型拟合，旧成绩属于旧版数据，未证明这些修正会降低误差。

稳定调用`data.cycling_db.open_database()`；fetch/by_endpoint、material_matrix/method_specific_material_matrix均屏蔽冲突字段，field_changes、evidence与material_properties(selected_only=False)保存历史。默认selected_only的属性接口不得重新选回有争议值。合同和原v0.20不可变父库校验保持。

核验`python -B tools/release_feature_freezes_v021.py verify`。所有观察和用途成员、目标、权重、其它字段逐项对比；新特征选择单独版本化，不修改旧数据库、原文或已交付模型。
