# 药渣YZPC与地肤KAC训练数据接入 v7

本批以受SHA保护的v6为父版，只新增小型SQLite增量；v6/v5/v4/v3及原论文、历史结果保持。总体质量目标active，未新增模型拟合或循环准入。两条既有主记录旧标签/工况/非空特征均保留。

## 调用与用途

```python
from data.training_latest import open_training_datasets
with open_training_datasets() as db:
    main = db.rows('cycle:reported_3e')
    ordinary = db.rows('capacity:3e_reported')
    with_graph = db.rows('capacity:3e_with_graph')
    no_bet_controls = db.rows('capacity:3e_reported_without_BET')
    devices = db.rows('capacity:2e_device')
    bundle = db.source_split_bundle('cycle:reported_3e', ['10.1002/asia.70648'])
```

主3E仍47条/34来源、主2E31条/25来源。普通3E GCD为229行/35来源，包含于含图434行/35来源，不相加。三个缺自身BET的地肤对照在`capacity:3e_reported_without_BET`单独读取，只有一个来源家族；可以研究报告工况/配方/Raman的辅助关系，不能声称它们有完整材料描述或可独立检验。器件任务7行/2来源，KAC两行采用作者明确的正负极总活性质量，不暗乘4。

最新路由`data/current_training_latest.json`指向本版；本目录`entrypoint_snapshot.json`为固定历史快照。通用只读API与旧接口未改。当前本版加4个父库共5库，后续接近SQLite附件上限时必须审查物化，不丢失父版。构建器仅接收明确审查过的spec，不是自动提取器，不自动放宽准入。

## 实际产出

- 12项材料/阶段登记：药渣YZ原料、YZC预碳化、五个最终YZPC；地肤原料、KC与三个KAC。只有2个DOI，阶段和多工况不成为独立论文。
- 301项事实、275数值、26未报告；260个唯一数值事实有实际输入/辅助目标回执。累计3727/5197=71.71%，279非标量/空值、1470未接入数值另列。这不是整篇文献利用率或拟合使用率。
- 主集规范桥接23→25/47。YZPC-3与KAC-5各新增17个非空特征单元，共34；分别12、14个旧值补证，共26。配方分量与区间边界有关联，不称34个独立材料参数。
- 自身两表62个数值格有去向：YZ表1七阶段×8字段=56；KAC表1五个物性及82.28%显式单位换算共6。2个原YZPC争议字段继续冻结。
- 14独特电容报告：9个普通3E GCD、3个缺自身BET对照、2个总质量器件条件；23个EIS响应按Rs/Rct/作者报告WarburgΩ通道分开。73个材料属性目标排除同一测量块；共119个新输入表示，8个旧循环输入表示有更新回执。

## 已决规则与新边界

1. YZPC-3 Vmicro0.63、Vtotal1.223与比例0.37不相容，早在2026-10-21已视觉核过，沿用冻结；不填微孔/介孔，不把“找到数值”当作解除争议。
2. YZPC的KOH比以YZC为分母；KC800→KAC的KOH比同样以KC为分母，不是对原始生物质。KAC800°C/2h是前段，600°C/2h是后段，不能反置。KC是已优化KC-800同一材料，184F/g仅记一次；其它KC600/700/900筛选结果需SI，未猜数值或时长。
3. 原配方YZPC:PVDF:炭黑16:3:1、KAC:PVDF:乙炔黑8:1:1按总份数换算为0.8/0.15/0.05与0.8/0.1/0.1，原比例及公式保留。两次药渣干燥分别是成膜后和层压后，不能随意合成24h单一处理。
4. 药渣负载2–3mg/cm²只存上下界；精确负载未知，不填2.5。地肤3mg/cm²为明确作者值，不用配料绝对质量猜分母。
5. 地肤接触角58.25°是70ms图内标记，不能当平衡角；药渣92°来自正文自身测量声明，SI未取、时点未知，不贴“完全亲水”标签或借其它样品时点。
6. 地肤表1 BET仅KAC-5明报，KC/KAC4/KAC6不继承1441.3。原料FTIR仅元数据；TGA三段原报6.7/71.9/21.4%的损失/残余语义仍待图核，不转最终碳收率。
7. 药渣详细方法称工业混合药渣，结论出现大黄根措辞，异文保留不猜配比。器件功率公式原印以电压作分母，原式留存，不据此造计算标签，也不从能量逆推电容。
8. Warburg值按作者Ω报告单独响应任务；模型类型/拟合量纲未明，不强并标准Warburg系数。EIS响应作为独立输出，不加入材料本征属性的输入。

## 证据、核验及未完成范围

正文源SHA见`source_receipts.json`；原图保存`evidence/`。`verification.json`包含68594项检查，62表格数值格由新鲜PDF解析核对。KAC图3c的At%与图3f的70ms时间经视觉核读，不声称独立OCR。完整性/外键、历史原值与SHA、派生行前后回执、来源整组隔离、同测量块泄漏及229包含于434均通过。

已从出版商页面定位药渣SI文件`asia70648-sup-0001-SuppMat.docx`，公开下载仍403；地肤SI同样403。见`SI_access_attempts.json`。这不是“SI不存在”的结论。没有绕过访问控制，没有新SI归档，也没有创造其表格/曲线。

`extraction_coverage.json`分别列出两张主表、方法、主图及未取SI范围；尚未完成所有连续波形/图像描述符。原37条待补证、15字段冻结和苏铁掩码保持；全量目标未完成。剩22条/22来源主集均有本地原文，下一批OAC623和AMFS，继续原文与SI，不拟合追分。

只读核验：具备pypdf的可用解释器运行`python -B tools/verify_yzpc_kochia_v7.py`。封版后不重跑curate/build/report或带`--save`覆写交付。`build_reviewed_training_extension.py`记录一次构建流程，要求空新库、显式来源/材料spec、有限数值、无重复字段和父版SHA，不能当批量重跑脚本。
