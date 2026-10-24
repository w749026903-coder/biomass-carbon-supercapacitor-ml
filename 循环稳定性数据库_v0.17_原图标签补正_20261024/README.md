# 循环稳定性数据库 v0.17

以只读v0.16为底座，新增CMC原图标签审查增量和当前用途成员表。完整报告见[本轮补正](../持续补正_v017_20261024/release_report.md)。旧库、原件与旧模型不改。

默认3E主集43条/31来源；嵌套敏感性44/32、52/38，2E26/21、28/22、30/24。全部观察277条；固定待证目标39条已完成1条，还剩38条/24来源，目标未完成。

```python
from data.cycling_db import open_database
with open_database() as db:
    ds = db.fetch('reported_3e')
    matrix = ds.feature_matrix()
    materials = db.method_specific_material_matrix()
    cmc = db.by_endpoint('incoming:ADD_035_T01')
    evidence = db.evidence(cmc['endpoint_id'], 'retention_relation')
    history = db.holds(cmc['endpoint_id'])
    pending = db.reviewed_pending_batch()
```

CMC保持率96.7%、15000圈不变，关系gt→eq依据作者自身图的明确印字和正文点值；未知基准圈号不猜。当前成员使用admission_profiles_v17；admission_profiles_v13同步为兼容当前矩阵验证器的投影，旧v11/v12成员及旧审查字段仅留历史。历史值看field_changes、holds.previous_holds和不可变父库。include_outside=True返回固定原41条的审查全账，而非当前待证数量。

DSAC负BET C问题和AC700正式身份线索只是审查元数据，均未新增准入。CMC的初始/循环后性质、酸洗后残余Co界限与中间Co/CoO分开。eq是作者圆整报告点值，不表示真实测量无限精度。

训练输入检查通过不表示泛化精度达标；本批拟合0，不自动重训旧模型，不发布推理服务。v0.17依赖父版本目录和原文证据，不能只复制这个小SQLite作为完整独立语料库。

只读核验：`python -B tools/release_original_label_v017.py verify`。verification.json、data_contract.json、training_readiness.json和merge_manifest.json保存检查、规则、用途与哈希。
