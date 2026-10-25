# 文献提取与补正进度

本地预览：http://127.0.0.1:8770/?view=1&tab=dashboard 。只提供本目录dist下的面板，不发布网站、不提供模型推理服务。

按核验批次刷新，全量目标未完成，用户本轮手动续行；应用目标工具usageLimited；面板buildStatus完成仅表示这批快照页面制作完成，不表示全量文献目标结束。展示目录身份、材料数值、比电容、争议、959表候选队列；支持DOI/方法筛选、表内搜索分页、原始来源与SQL查看和复制数据；辅助目标筛选47/5/5/6/All63。默认数字来自data/current_literature.json和循环只读API；材料单元、测试报告和正式准入分开。

更新同一页面，不另建重复面板：

```powershell
python -B tools/refresh_literature_progress.py --build-status updating
```

随后按本目录AGENTS.md，以已安装Data插件scripts/data-app.mjs build --project-dir本目录 --separate-data构建。内容和核验结束后将buildStatus设complete再构建。不得修改受保护运行时、安装全局环境或发布网站。静态预览绑定127.0.0.1并仅以dist为根；示例端口8770，不打断其它既有服务。

科学数据库见[第四批README](../文献全量利用复核_20261025/批次04_循环原图与新来源/README.md)，当前只读核验tools/verify_literature_pool_v4.py。1803项、四CSV、20原载荷及2附加载荷通过。累计603材料数值、147比电容报告不是603/147独立训练样本；四个辅助任务分别47/5/5/6条，合计6个DOI组，不拼接成一个目标。原循环主集43/31和原固定39条中38待证保持；历史725属性不与603相加。

界面检查及截图保存在output/playwright。只检查本页的实际两幅图、各表、DOI/方法范围、空结果、数据来源与复制范围、正常/窄屏；不以成功构建代替渲染核验。原文与科学版本均未改写。
