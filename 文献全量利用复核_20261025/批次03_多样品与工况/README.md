# 第三批：多样品、分阶段制备和分用途GCD输入

2026-10-25。全量提取目标仍active，尚未完成480身份/959表候选的逐项科学处置。本批处理18个表候选的声明范围，累计33个已处理指定范围、926个未进入本流程处理；不把表候选、论文、样品和参数单元互相替代。

## 已落实内容

四个已有来源：夏威夷果壳10.1021/acsomega.5c06396、大麻芯10.1021/acsomega.5c10175、爆米花10.1021/acsomega.5c03461，以及CNF/MWCNT复合碳10.1002/advs.202206320。新增22材料登记、354材料数值、4个非数值受限单元和53条分工况比电容报告。当前证据层累计46材料、511材料数值、8个非数值单元；比电容94报告/92数值/2未报告。数值包括孔结构、XPS原子组成与各元素包络内比例/峰能、Raman和打印几何；不是354个独立实验。

20材料已有独立阶段制备对象：本批16个，再补上一批紫玉米芯4个。区分MNS600℃18h碳化与800℃1h活化；Hurd500℃2h碳化与720℃1h活化；爆米花火焰预碳化温度未知，800℃2h煅烧的air/N2分开。紫玉米芯KOH5–30%基准未明，不能当碳/KOH质量比。电极干燥、BET脱气不当制备碳化。

SI中8条库仑效率保存为独立outcome，不作保持率或材料特征。增加Hurd-4有机器件78%/10000圈循环候选，仍无正式循环准入。现有循环库仍v0.19、277观察、主集43条/31来源；固定原39条仍1完成、38待证。没有新模型拟合、服务或精度改善声明。

## 可调用的辅助输入

本次逐用途审查得到水系三电极GCD比电容20条/3个DOI组，以及水系双电极器件比电容5条/1个DOI组。二者是不同目标，各有独立CSV和读取接口；合计25条辅助输入不等于25条循环保持率，也不等于25篇文献。不可将两类目标拼成一列或把同DOI的材料/其它电流/辅助标签拆进留出训练两边。

```python
from data.literature_v3 import open_literature_database
with open_literature_database() as db:
    three_e = db.auxiliary_feature_rows('3e')
    two_e_device = db.auxiliary_feature_rows('2e_device')
    process = db.synthesis(doi='10.1021/acsomega.5c10175', sample='Hurd-4')
    all_raw_reports = db.capacitances(doi='10.1021/acsomega.5c03461')
    ce_outcomes = db.outcomes('coulombic_efficiency_pct')
```

auxiliary_3e_inputs.csv与auxiliary_2e_device_inputs.csv保留目标定义、DOI来源组、报告电流、条件、原文路径/哈希/定位、主要材料字段及缺失掩码。空值输出空单元，不填0。Raman IG/ID保留原方向，倒数仅作为明确派生列。每来源权重总和为1。原始层training_eligible=0保留历史，独立auxiliary_gcd_reviews_v3/view给出当前特定用途输入资格；不会改变正式循环资格。

290项输入预检检查API、原值/冲突屏蔽、缺失掩码和跨任务来源隔离；没有拟合模型。三电极子集目前只有3来源，器件子集仅1来源，尚不足证明泛化精度。这里的输入可调用不表示全量文献目标完成或模型性能门槛通过。

## 保留的科学边界

- MNS的C-MNS介孔容原表为0.36cm³/g，但自身脚注明确Vmeso=Vtotal−Vmicro，另报0.176、0.140、20.5%和3.89。原值同存，不擅自改成0.036。该孔容及耦合比例在辅助特征中屏蔽，BET等独立证据保留。
- MNS Table2的C–MNS与方法/同文其它表C-MNS仅排版横线不同，已记录专门别名依据。EDS atom%不代替XPS atom%；SI三个K的“-”不填0，也不声称已知检出限。
- Hurd的Raman是IG/ID；61.1%是库仑效率；78%是有机器件循环保持率。Hurd-4速率测试在0.5A/g的38F/g不能替换其独立循环初始28F/g，也不以22/28重算覆盖作者取整78%。
- Hurd-BC虽在孔表标题中出现，表中没有其数值，不借用其它样品BET。Hurd-5由正文明确提到但作者未呈现数值，已记入来源待办，不推算或从趋势补值。
- 爆米花Table6的器件Ccp和作者单电极Cs=4Ccp属于同一物理测试的两种表达，四对记录共享physical_test_group，不能当两次实验。各列作者舍入值保留；不与实测三电极电容混列。
- CNF/MWCNT是有意保留CNT的复合碳。CNF:MWCNT3:7和MWCNT:urea1:5分别记录，不把70%误认成最终碳质量分数。四个打印层数的几何参数来自SI自身表；通用表征块的BET/XPS不自动分配给所有厚度。面积电流mA/cm²不猜算A/g；保留复合体系独立用途。

## 核验和接续

`python -B tools/extract_literature_material_pool_v3.py verify`：1417项，包括旧行完整保留、来源/父库/全库索引哈希、完整性/外键、逐XML行、源单元分量解析、SI原生数值/已查看渲染页、GCD协议、阶段制备及用途分离。`python -B tools/check_literature_auxiliary_inputs_v3.py`只读复核290项输入预检与两个CSV。封版后两者不改已封版载荷。

source_review_notes.json列明各来源实际核读和剩余工作。本批不是所有曲线完全数字化；MNS的循环图只有“minimal change”文字，没有把100%或某个像素读数冒充精确标签。下一批优先HempHoneycomb、Hardwood、Tucuma三个已有全文，继续自身表/SI/真实循环条件；本批未完成图点与SI继续在各来源待办中保留。原论文/SI、旧库/模型和38条待证范围均不覆盖。
