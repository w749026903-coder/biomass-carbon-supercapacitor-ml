# 循环稳定性数据库 v0.2：首批训练前优化

2026-10-17。已承接v0.1，完成首批核查、模型配置修正和隔离环境接口验证。本版仍是候选与审查数据库，正式训练记录为0，没有研究性能分数。

先读[训练前优化说明与验收.md](训练前优化说明与验收.md)。逐记录结论在[首批逐记录审查.json](首批逐记录审查.json)，字段出处在[字段覆盖与出处.json](字段覆盖与出处.json)。SQLite主文件是`cycling_v0_2.sqlite`；JSON只是读取副本，不能绕过准入。

本版登记126篇、137份来源文件、67个暂定材料、83次测试、89个候选终点。首批审查原主队列12终点/10暂定材料/10篇：8条有条件保留、4条继续冻结、0条通过正式准入。所有材料身份仍未完成跨论文独立性终审。

80条审查事件追加保存；69条字段变更日志保留旧值、新值和理由。R107共享测试的措辞更正也保留在日志中。`field_evidence`与`raw_records`保留v0.1导入证据，当前补录/审查应结合`field_review_latest`和`revision_changes`读取。

已通过23项版本与数据保护核验、16项最终合成接口检查。原始论文、SI、候选快照、v0.1数据库与建模文件未修改。原冻结事项保留。检查结果见`核验与覆盖_v02.json`；只读SQL复核见`首批核查复核.ipynb`，从本目录打开运行。

模型入口在`modeling/train_grouped.py`，默认只做预检查。实际参数空间在`model_spaces.json`；折数、预算、随机种子、模型清单和特征集由`model_contract.json`驱动。已提供条件输入、加BET、再加总孔体积三种预先规定的探索性敏感性比较；不能用外层最高分事后选择特征后宣称无偏最终结果。

项目环境为本目录`.venv`，Python 3.12.14，依赖精确版本见`modeling/requirements-lock.txt`，`pip check`通过。它不启用共享site-packages，没有修改全局环境。可直接预检查：

```powershell
& '.\.venv\Scripts\python.exe' -B '.\modeling\train_grouped.py'
```

合成接口检查输出位于`modeling/synthetic_interface_checks_v2`，是软件检查，不能作为论文模型结果。`injected_failure`为故意制造的失败，用来验证错误记录机制；测试本身通过。先前的14项版本输出也保留。复验时必须换一个新输出目录名：

```powershell
& '.\.venv\Scripts\python.exe' -B '.\modeling\check_interfaces.py' synthetic_interface_checks_v3
```

`initialize_revision.py`、`review_batch1.py`、`review_batch1_erratum.py`和`review_field_confirmations.py`是本版已执行的增量历史，带重复执行保护；不要重跑，也不要重跑旧的一次性下载/整理/入库/建库脚本。未来补录另建增量批次或v0.3。

仍待解决：循环电流质量分母、部分基线精确圈号与统一口径、跨来源复用/材料独立性、R106循环电流与FMC范围、R111循环窗口和SI、R112电压一致性与材料范围。4篇待补正文仍为N003/N006/N007/N008，本轮没有重复下载或归档。
