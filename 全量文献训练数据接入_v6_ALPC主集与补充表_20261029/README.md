# ALPC正文、SI表格与主训练记录补齐 v6

本批接续已封版v5，只创建小型SQLite增量，按SHA只读连接v5/v4/v3。原文、旧库、历史模型和旧版入口不改。总体质量目标active，本批无模型拟合、无新循环准入，不能据此宣称误差改善或全文提取完成。

## 当前调用

```python
from data.training_latest import open_training_datasets
with open_training_datasets() as db:
    main = db.rows('cycle:reported_3e')
    material_features = db.feature_coverage('cycle:reported_3e')
    ordinary_gcd = db.rows('capacity:3e_reported')
    including_graph = db.rows('capacity:3e_with_graph')
    heldout = db.source_split_bundle('cycle:reported_3e',
                                   ['10.1021/acssusresmgt.3c00028'])
```

`data/current_training_latest.json`是可更新路由；本目录`entrypoint_snapshot.json`为封版快照。旧v1～v5路由仍钉住旧版本。`data.training_store.TrainingStore`负责只读父链和派生行前后哈希检查；原始事实只追加，不允许最新写入覆盖科学争议。当前父链4层数据库，未来接近SQLite附件上限时需要审查后物化快照，不能静默丢父库。

## 实际新增

- ALPC-700、800、900三材料登记，只有一个来源家族；两条既有ALPC-800循环记录规范桥接，主集关联21→23/47。
- 主集新增38个非空特征单元、16个已有单元补证。两工况共有信息重复出现，不当38个独立参数。旧目标100%、2000圈、10A/g、两电解液/电压和原非空特征均不改变。
- 91项事实、85数值、6未报告；76个唯一数值事实有实际输入/目标回执。累计3467/4922=70.44%，其余1455数值、253非标量/空值各有去向。不是论文整体利用率或拟合使用率。
- 34个独特电容报告：31个3E GCD条件、2个3E中性CV、1个2E器件作者公式用途。普通3E GCD 220/33家族，含图425/33家族，两者嵌套。2E与CV各在明确独立任务中读取，不混入普通GCD。
- 图7e有30个倍率标记、3个正文锚点确认、净27个新条件。作者明报1A/g采用170、421、264F/g；读图中心与±8F/g包络另存，不复制为第二个独立实验。不强制ALPC-700曲线单调。
- 3个EIS Rct辅助目标、25个材料物性目标，共66个新输入表示；8个既有循环输入表示仅有记录更新回执。
- 表S1的21个自身数值格逐格保留；S2/S5/S6共28条二手比较单独索引；S3/S4为5种吸附物的10个DFT数值格，另表保存，不冒充实测材料属性或循环标签。

## 质量处置

1. ALPC-800微孔面积757/BET718、微孔体积0.382/总0.35，以及ALPC-700微孔面积37/BET25，存在名义微孔/总量计量一致性问题。方法与原始分析未厘清，3格原值冻结；不猜交换列、不改成0、不以新值强填已有空字段。不同模型的面积估计可能有方法差异，未据此武断宣布作者笔误。
2. 表S1标题明示FESEM-EDX原子百分比，ALPC-800 N11.23/O8.54；正文XPS明示N4.64/O7.44 atom%。二者是不同方法通道，EDX不能覆盖XPS，也不能转作体相质量百分数。
3. ALPC-800酸性GCD正文421与表S5比较行409并存。421有自身图7e锚点包络支持，沿用正文值；409单独保留，不称已取得作者更正。七个酸性CV值与正文100→5mV/s序列未可靠逐项配对，未猜反序加入训练。
4. ORR催化剂约0.35mg/cm²不替换超级电容器1.2mg/1cm²。ORR的70%电流耐久、14,000s和模拟石墨烯温度不成为超级电容器循环标签或真实碳制备数据。
5. NH₄Cl与叶粉1:1明确；KOH“similar procedure”质量比口径未充分明确，留空。类似预处理干燥80°C/24h按共同程序留证；Ar中700/800/900°C、2h、5°C/min是共同碳化/活化热处理，不拆成两个独立过程。最终90°C过夜不猜小时。
6. 器件GCD47F/g按作者式4独立命名空间保存，不暗乘4；器件循环摘要1A/g与图8f/正文/结论10A/g差异保留，本批不新增循环准入。Ragone成对值21.15Wh/kg–0.45kW/kg、1.35Wh/kg–4.93kW/kg分别保留，不能拼接摘要/结论成假配对。

## 证据与验证

正文U024共14页、SI共27页，原件SHA见`source_receipts.json`。`TableS1_visual_transcription.json`保存21格视觉转录、单位/基准和原图SHA。该表内数值是嵌入图像，**未声称独立OCR核验**。新鲜PDF解析另检查正文XPS/GCD/EIS以及二手/DFT文本数值；读图保留原页面和裁切证据。

`verification.json`检查原件/旧交付SHA、SQLite完整性/外键、父链所有未变行、去重、派生行回执、旧目标工况和非空值、真实输入回执、测量块泄漏、全任务来源隔离以及220包含于425。`report_visual_verification.json`检查桌面/手机、链接和30行展开收起。

只读核验命令使用具备pypdf的项目可用PDF解释器：`python -B tools/verify_alpc_v6.py`。不要对封版目录重跑prepare/extract/report或带`--save`覆写核验产物。首次构建流程由`prepare_alpc_evidence_v6.py`、`extract_alpc_v6.py`记录，非日常重跑脚本。

## 未完成范围

现有主集剩24条/24来源尚待规范材料桥接，均已有本地原文索引。下一批先YZPC-3（10.1002/asia.70648，ADD_039.pdf），再KAC-5。固定37待补证、原15字段冻结与苏铁掩码保持；剩余连续波形、SI图S14/S16等仍需核读与提取。原批次27整体未封版，不将本批完成外推为全部文献已利用。
