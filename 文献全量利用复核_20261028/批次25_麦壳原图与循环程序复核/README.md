# 文献v25：麦壳原图与倍率工况

2026-10-28。DOI 10.3390/nano12213804，2022年原始研究。按PMC9655081的正式公开附件接口取得9张原始JPG（Scheme1及Figure1—8），与已有正文和文章身份绑定；ZIP内仅图像及其GIF预览，没有另行补充材料。没有改写v24、原XML或其它文献。获取记录见acquisition.json，SHA见protected_inputs.json。

实际Figure8(a)的双电极GCD电压为0～1V。v24中两条双电极电容的窗口以新决策补入读取接口，原SQL行与旧空值保留。Figure8(d)是保持率循环，不是库仑效率；正文P18给出30000圈、5A/g、相对初始电容98.59%。循环逐测试准入由独立版本完成，这份文献库本身不授予循环训练资格。器件窗口依据适用的同电池GCD程序，没有伪称循环图内另有逐圈电压插图。

提取Figure7(d)三个样品各5点和Figure8(b)器件5点，共20个实际标记。已有8个正文数值作为锚点，只有12个额外标称工况。±4个y像素/±2个x像素为读图包络，不是作者实验SD、置信区间或精确目标；所有锚点在相应读图界限内。review中保留读取框，不插值生成曲线或看不见的点。

三电极工作电极比电容与双电极作者Cs分开：后者明确采用正负两电极活性物总质量和四倍因子，不与普通器件比电容混用。调用示例：

```python
from data.literature_current import open_literature_database
with open_literature_database() as db:
    # 6个作者原值 / 15个混合点 / 15个纯读图值：三个嵌套选择
    matrix = db.batch25_rate_matrix('point_mixed', 'wheat_husk_3e_reported_capacity')
    # 2个作者原值 / 5个混合点 / 5个纯读图值
    device = db.batch25_rate_matrix('point_mixed', 'wheat_husk_2e_factor4_total_active_mass_Cs')
```

六份CSV按同样用途/模式导出，空特征保留空值和掩码。同论文全部样品、前后阶段、曲线、材料、电容和循环标签一起隔离；三电极15条、双电极5条只有1个DOI家族。普通精确报告辅助集仍205/30DOI；明确包含读图的三电极集由374增至383/30DOI，其中9个是本批额外读图工况，两个集合嵌套不可相加。

累计459个图捕获（449数值、2区间、8遮挡）、1266电容报告/1252数值；材料事实4656/4459数值及447阶段登记保持。只增加2个图标记证据单元，不改变959个原自动候选的252已触及/707未触及。所有64来源仍部分完成：连续谱图、吸附、CV/GCD/EIS及其它Ragone/CE/循环标记未全部数字化。原固定39中2解决、37待证，本批不抵扣；无新拟合或性能改善声明。

只读核验：`python -B tools/verify_wheat_figures_v25.py verify`。封版后不要重跑curate/build/prepare/seal。历史复现须显式指定数据库路径和SHA，旧模块的无参数入口也会随当前指针读取。
