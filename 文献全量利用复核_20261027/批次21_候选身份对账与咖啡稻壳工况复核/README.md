# 文献v21：候选身份对账、CV方法补正与倍率点

本批检查83个文献层循环候选与当前286个循环观察的DOI身份。32个候选在旧观察的直接DOI字段中有同DOI记录；其余51个没有直接匹配，不代表51次新实验。6个旧观察的直接字段未给可规范化DOI，保留单列。原始DOI、`doi:`前缀与DOI URL只在查找时统一，不改原记录，也不把同DOI自动认作同测试。

上一批的三个候选核定为既有端点的文献层关联：

| 文献候选 | 既有端点 | 当前状态 |
|---|---|---|
| LP20:Coffee:citrate_2E | legacy:R104_CY01 | 98.4%/20000圈/10 A/g，早已在报告工况用途准入 |
| LP20:RHC:ratio1 | legacy:SRC123_CY02 | 27.9%/10000圈/1 A/g，前作样品重叠待核继续保留 |
| LP20:RHC:ratio2 | legacy:SRC123_CY03 | 96.4%/10000圈/1 A/g，质量不平衡且前作重叠待核，不混入对称主集 |

旧`legacy:SRC123_CY01`的约90.1%/2000圈与一万圈端点同曲线，仍保留约值关系，未冒充新端点。原库286观察、185原始来源组、正式3E45/33和2E31/25、原39中2解决/37待证均不变。83项DOI审查是检索与候选对账，不是83项科学准入。

## CV与GCD方法补正

稻壳10.1039/d5ra03028e实际Fig6(b)图注明确：155/167/141 F/g是5 mV/s的CV结果。v20暂未选定的方法/速率已通过`protocol_corrections_v21`前向选择为CV、5 mV/s，电流仍空。原数据库三行的空方法、原值和条件保留；当前API附`original_protocol_v20`及原图注证据，并在方法筛选前应用补正，不能因旧SQL为空漏掉当前CV行。

Fig6(c)的GCD倍率点另行转录，不能用这三个CV数值作GCD作者锚点。新24个GCD图点覆盖同一RHC的四种正负极质量比、每种六个电流工况，继续仅供证据检查。原库明确记录2016前作样品重叠待核；已有公开预览的同配方、不同BET不能证明或排除批次/曲线复用。本轮没有用同样证据撤销旧冻结。

## 有界倍率点

原始像素转录36次，均有读取值；原图、坐标、局部彩色像素、选定标记行及核查叠加图保留。纵向±4像素、横向±2像素是图像读取界限，不是实验SD或置信区间；没有插值新工况。

- 咖啡/污泥Fig7(d)：三种材料/粘结剂组合，各1、5、10、20 A/g，共12个图工况。1 A/g的3个作者均值与SD保留旧ID作锚点，混合点模式为3旧作者值+9新近似条件，不重复扩样。作者C/Cg表达尚未统一，只在该来源的作者容量用途调用。图中的SD误差棒未量化，不能把像素读取界限当SD。
- 稻壳Fig6(c)：质量比1/1.25/1.5/2，各0.5、1、2、5、10、20 A/g，共24个图报告。真实配置与已有前作重叠冻结保留，`purpose_input_ready=False`；训练矩阵接口拒绝这一检查用途。相同碳的四个质量配置不是四种独立材料或四个来源。

累计1178电容报告（1166数值）、439次图捕获（429数值、2仅区间、8遮挡）、20面板/68曲线组。材料仍4035事实/3854数值/367登记，52来源；214原候选触及/745未触及不变。482声明单元、468实际表键、451 extraction_units与245物理表分计。两张新图转录不是新增物理表，也未声明任何来源已全篇完成。

## 调用

```python
from data.literature_current import open_literature_database
with open_literature_database() as db:
    audits = db.batch21_candidate_audits()
    links = db.batch21_identity_links()
    cv = db.capacitances(doi='10.1039/d5ra03028e', method='CV')
    coffee = db.batch21_rate_matrix('point_mixed')
    inspection = db.batch21_rate_rows('point_mixed', 'rice_mass_ratio_inspection')
```

咖啡三模式`author_exact / point_mixed / figure_only`为3/12/12行，不能相加；各模式同一来源权重合计1。三份CSV保留来源、空值和图界限。稻壳另存`RHC_inspection_only.csv`，明确待核状态，不宣称训练输入。

核验见`verification.json`及`chain_verification.json`。检查覆盖旧行/旧接口、图原像素/标记/作者锚点、真实CV图注、DOI前缀等价与冲突拒绝、83项身份候选、原冻结和来源隔离。载荷含重复表达，不作实验数。仅只读运行`python -B tools/verify_identity_rates_v21.py verify`；封版后不重跑curate/build/prepare/seal。没有新增循环端点、准入或模型拟合，没有删除原始资料。
