# 循环稳定性数据库 v0.18

本批2026-10-24开始核读，2026-10-25收尾。以不可变v0.17为父库，补5项题录/版本/测量质量字段，作用于2条待证记录。新增准入0、模型拟合0；主集仍43条/31来源，固定目标剩38条/24来源，目标未完成。

AC700补source_year=2026及自身预印本DOI10.2139/ssrn.6799753；依据SSRN发布于2026-05-20的记录，不用Crossref创建时间推测发表日期。正式DOI10.1016/j.ultsonch.2026.108104仅保留为同研究候选版本，正式无Au对照数值仍未核验。保留旧document来源组、92.1%标签和冻结，不因年份/DOI补齐就准入。

DSAC新增单位复算及方法质量记录。0.0232 g样品、N₂分子量28.013 g/mol和0.162 nm²截面积，在明确说明的常规STP假设下复现原报告斜率、截距、面积及负C。该复现不能验证拟合有效；IUPAC2015的三项条件与RSC的额外压力一致性条件分开，提供的78个区间均未通过前三项的联合检查。1374报告值不改，不另选替代面积，不新增所有论文必须报告C的门槛。

```python
from data.cycling_db import open_database
with open_database() as db:
    inputs = db.fetch('reported_3e').feature_matrix()
    materials = db.method_specific_material_matrix()
    ac = db.by_endpoint('incoming:ADD_073_T01')
    current_issues = db.holds(ac['endpoint_id'])
    source_identifiers = db.source_aliases()
    pending = db.reviewed_pending_batch()
```

source_aliases()用于题录查询，区分实际预印本DOI和正式候选；本次未迁移大型原生语料索引。按新补SSRN DOI过滤旧search_native索引可能没有结果，按endpoint的source_pdf/evidence定位原文；不能把索引无命中当作原文不存在。当前成员继续继承admission_profiles_v17，当前冻结查holds；旧issues及版本字段保留历史，新增current_open_issues_v18明确本次审查。

3E嵌套敏感性44/32、52/38，2E26/21、28/22、30/24保持；全部277观察和现有训练矩阵、来源权重、可选覆盖327/774均不变。没有新模型或精度结论。该小SQLite依赖父版本与原文目录，不是独立完整语料副本。

本轮[证据与仓储核查](../持续补正_v017_20261024/post_v017_figure_review/README.md)、data_contract.json、training_readiness.json、verification.json及merge_manifest.json保存依据、边界和哈希。只读复核：`python -B tools/release_source_quality_v018.py verify`。不要重跑build/relation/title查询或覆盖封版文件。
