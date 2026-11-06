# 第四十九轮 · 木源碳长期循环数据核查

本轮找到一篇有明确长循环数据文件名、且能回原论文核对条件的木源碳研究。两个 CSV 的字节、表头和逐圈数值尚未取得，新增可用早期输入、预测锁定、模型拟合和正式独立验收均为 0。

## 数据包与试验条件

Zenodo 概念 DOI 为 `10.5281/zenodo.15628303`。早期版本只有 README。已核到有实质数据文件的版本 `10.5281/zenodo.19549171`。ZIP 预览列出 9 个成员，其中两个文件专门标为 `Book1.Long-term cycling (KxHyPO4).csv` 和 `Book1.Long-term cycling (NaCl).csv`。记录页给出 ZIP 的 MD5。官方文件、旧路径及文件 API 返回 403，直连 DNS 未能解析。本次只确认目录和下载状态。 [版本记录](https://zenodo.org/records/19549171) · [ZIP 预览](https://zenodo.org/records/19549171/preview/Small%20Science%20Paper.zip?include_deleted=0)

论文 `10.1002/smsc.202500540` 的数据声明指向同一概念 DOI。印刷木源活性碳器件为双电极。方法写明以 10 mA 恒流充放电至 1.2 V，上限 10,000 圈，每 100 圈记录一次电容。10 mA 保留为绝对电流。实际循环质量分母、同一试验的归一化参照和每一行的器件身份仍待核对。图注将 Fig. 8(a) 分给 NaCl、Fig. 8(b) 分给磷酸盐体系。 [论文全文入口](https://pmc.ncbi.nlm.nih.gov/articles/PMC12904054/)

## 来源隔离和图像备选

目标论文和同团队的 Carbon Trends 论文在两份现行来源目录与第 31 轮整篇留出快照均无 DOI 命中。两者有共同数据作者，仓库历史检索中也已有题录线索。实验谱系未核前先按一个候选簇管理，两种电解液文件均归本篇。精确终点没有揭示。

在冻结备选方案后封存 PMC 的 Fig. 8 图件，文件与仓储 MD5 一致。未显示图内像素。下一轮可尝试正式刊本原生图并先定位两个面板，证明遮蔽边界后再核前段标记；若取得 CSV，优先核样品、列名、独立圈数和同一试验的初始参照。正式独立验收还需确认来源谱系。 [图像备选计划](figure_fallback_plan.json) · [公开目录](public_file_inventory.json) · [证据回执](evidence.json)
