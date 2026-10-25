# 只读来源组兼容核验补充

2026-10-26。主manifest、SQLite、原验证器/6480项报告、v0.20及原988项报告均保持原字节。

v7新串联候选的material_key外键已绑定PK700及原始DOI，JSON没有冗余source_group键。原v0.20校验器直接访问record[source_group]，在新记录上KeyError；这不是原文数值或来源身份缺件，也不能据此跳过来源隔离检查。

data.literature_groups按materials.doi与外键生成只读标准组，原30条的已有组必须与材料DOI一致；31条全部对账。只对新候选补1个派生来源键并附来源说明，不写回SQLite、原JSON或旧API。若已有组与材料DOI冲突，接口直接报错；反例验证通过，不以新值覆盖冲突。

```python
from data.literature_groups import open_grouped_literature_database
with open_grouped_literature_database() as db:
    candidates = db.tests() # 全31条带校验后的来源组，保留旧值
    electrical = db.palm_responses("electrical")
```

当前组合验证入口：python -B tools/verify_current_source_groups.py。其在独立进程内将旧校验器的读取依赖注入为当前版本的只读来源组接口，原988项条件、历史/冻结链、CSV和原manifest检查逐项保留；结束即还原模块依赖。没有改旧检查、断言或报告。主文献v7原6480项依旧用tools/extract_palm_kernel_v7.py verify；v6原590项用tools/extract_remaining_si_v6.py verify。旧v0.20独立入口是历史假设，遇当前新JSON时用此补充入口，不能把KeyError隐去后声称旧独立命令通过。

本补充的报告、代码和本说明由grouping_addendum_manifest.json另行钉住，原primary_manifest_sha256不变。无新实验、准入或拟合。
