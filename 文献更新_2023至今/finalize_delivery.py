from pathlib import Path
import json,csv,hashlib,collections,re,sys,shutil,datetime
from pypdf import PdfReader
sys.stdout.reconfigure(encoding='utf-8')
OUT=Path(__file__).resolve().parent;ROOT=OUT.parent
rows=json.loads((OUT/'获取结果_归档前.json').read_text(encoding='utf-8'))
archive=json.loads((OUT/'新增归档清单.json').read_text(encoding='utf-8'))
archive_map={x['source']:x['target'] for x in archive}
deleted=json.loads((OUT/'删除清单_2022年及以前.json').read_text(encoding='utf-8'))
old_inventory=json.loads((OUT/'旧120篇_年份复核.json').read_text(encoding='utf-8'))
blocked=json.loads((ROOT/'文献扩充_生物质碳_120篇/禁止入库与待核查来源.json').read_text(encoding='utf-8-sig'))
for x in rows:
    if x.get('download_status')=='新增全文已核验_待归档':
        x['local_pdf']=archive_map[x['staged_path']];x['download_status']='新增全文已归档并核验'
    if x.get('local_pdf'):
        p=Path(x['local_pdf']);assert p.is_file(),p
        assert hashlib.sha256(p.read_bytes()).hexdigest()==x['sha256']
        x['pages']=len(PdfReader(p).pages)
    for s in x.get('supplements_current',[]):
        s['local_path']=archive_map[s['staged_path']]
        assert hashlib.sha256(Path(s['local_path']).read_bytes()).hexdigest()==s['sha256']
    assert 2023<=x['year']<=2026
    assert x['first_publication_date']<='2026-10-16'
    assert x['eligible_for_database'] is False
    assert x['doi'].lower() not in {b['doi'].lower() for b in blocked}
    assert x.get('openalex_retracted') is False
assert len(rows)==120 and len({x['doi'].lower() for x in rows})==120
assert not any(Path(x['path']).exists() for x in deleted)
ledger_path=OUT/'下载归档最终台账_2023至今.json'
with ledger_path.open('x',encoding='utf-8') as f:json.dump(rows,f,ensure_ascii=False,indent=2)
missing=[x for x in rows if not x.get('local_pdf')]
downloaded=[x for x in rows if x.get('local_pdf')]
new=[x for x in rows if x['download_status']=='新增全文已归档并核验']
years=collections.Counter(x['year'] for x in rows)
summary={'date':'2026-10-16','range_start':'2023-01-01','range_end':'2026-10-16','candidate_count':len(rows),
    'retained_candidates':sum(x['origin']=='旧候选保留' for x in rows),'added_candidates':sum(x['origin']=='本轮补充' for x in rows),
    'excluded_old_candidate_count':sum(x['year']<2023 for x in old_inventory),
    'excluded_relevance_count':1,'new_fulltexts':len(new),'existing_fulltexts':len(downloaded)-len(new),
    'local_fulltexts':len(downloaded),'missing_fulltexts':len(missing),'new_supplements':sum(len(x.get('supplements_current',[])) for x in rows),
    'recycled_downloaded_old_files':len(deleted),'recycled_old_papers':len({x['doi'] for x in deleted}),
    'recycled_generated_extracts_and_previews':18,'years':dict(years),'openalex_retraction_flags':sum(x.get('openalex_retracted') is True for x in rows),
    'training_eligible_records':0,'model_trained':False}
with (OUT/'本轮核验结果.json').open('x',encoding='utf-8') as f:json.dump(summary,f,ensure_ascii=False,indent=2)
headers=['编号','首次发表日期','年份','题名','期刊','DOI','DOI链接','用途初分','获取状态','本地PDF','原编号','是否允许进入数据库']
with (OUT/'120篇文献清单_2023至今.csv').open('x',encoding='utf-8-sig',newline='') as f:
    w=csv.writer(f);w.writerow(headers)
    for x in rows:w.writerow([x['collection_id'],x['first_publication_date'],x['year'],x['title'],x['journal'],x['doi'],'https://doi.org/'+x['doi'],x['role'],x['download_status'],x.get('local_pdf',''),x.get('old_collection_id',''),False])
def safe(s):return s.replace('|','\\|').replace('\n',' ')
md=['# 2023年至今的120篇候选文献','',
    '范围：2023-01-01至2026-10-16。按Crossref的正式发表/在线发表/纸本发表/issued中最早的已登记日期判定，不使用DOI字符串中的年份，也不使用网页更新时间、收稿日期或索引收录日期。缺日/月的日期在JSON中保留精度标记；这里只是书目准入，实验数据仍待审核。','',
    '新编号R001–R120对应当前台账；旧B编号只用于追溯。题名和DOI双重去重。复合材料、特殊电解液、器件类型及综述/方法论文仍需分层审核。','',
    '| 编号 | 年份 | 题名 | 期刊 | DOI | 全文 |','|---|---|---|---|---|---|']
for x in rows:
    pdf=f"[本地PDF](<{x['local_pdf']}>)" if x.get('local_pdf') else '待补'
    md.append(f"| {x['collection_id']} | {x['year']} | {safe(x['title'])} | {safe(x['journal'])} | [{x['doi']}](https://doi.org/{x['doi']}) | {pdf} |")
(OUT/'120篇文献清单_2023至今.md').write_text('\n'.join(md)+'\n',encoding='utf-8')
md=[f'# 待补全文：{len(missing)}篇（2023年至今）','',
    '以下均未取得本地全文；DOI和题名已向Crossref书目核对。可自行通过学校/机构图书馆或出版社查找。403、429、证书错误和没有公开直链均记入台账，不绕过付费或登录限制。','',
    '| 编号 | 年份 | 题名 | DOI | 获取情况 |','|---|---|---|---|---|']
for x in missing:md.append(f"| {x['collection_id']} | {x['year']} | {safe(x['title'])} | [{x['doi']}](https://doi.org/{x['doi']}) | {safe(x.get('failure_summary','未发现公开直链'))} |")
(OUT/f'待补全文_DOI清单_{len(missing)}篇.md').write_text('\n'.join(md)+'\n',encoding='utf-8')
(OUT/f'待补全文_DOI纯文本_{len(missing)}篇.txt').write_text('\n'.join(x['doi'] for x in missing)+'\n',encoding='utf-8')
(OUT/'全部120篇_DOI纯文本.txt').write_text('\n'.join(x['doi'] for x in rows)+'\n',encoding='utf-8')
with (OUT/f'待补全文_{len(missing)}篇.csv').open('x',encoding='utf-8-sig',newline='') as f:
    w=csv.writer(f);w.writerow(['编号','年份','题名','期刊','DOI','DOI链接','获取情况'])
    for x in missing:w.writerow([x['collection_id'],x['year'],x['title'],x['journal'],x['doi'],'https://doi.org/'+x['doi'],x.get('failure_summary','未发现公开直链')])
md=['# 已移出的旧文献与删除记录','',
    '用户于2026-10-16明确要求只保留2023年至今的文献，并删除已下载的过早论文。本次按逐文件清单核对发表年份、绝对路径和SHA256后移入Windows回收站。没有清空回收站；需要时可从回收站恢复。','',
    f'原120篇中移出早于2023年的{summary["excluded_old_candidate_count"]}篇，其中17篇有本地全文。已删除的下载文件共47个：D:/文献中17篇论文和5份附属材料，项目内25份同内容暂存/下载副本。另外撤下本轮新生成的18个2022年论文摘录和预览。','',
    '近期但未计入主清单：旧B019（10.1039/d4ra08322a），2025年材料制备论文，目前尚未确认提供超级电容器测试。其PDF和补充文件保留，未因相关性疑问删除；以一篇直接相关新论文替换主清单名额。','',
    '| 旧编号 | 年份 | 题名 | DOI | 原本地全文 |','|---|---|---|---|---|']
for x in old_inventory:
    if x['year']<2023:md.append(f"| {x['old_id']} | {x['year']} | {safe(x['title'])} | {x['doi']} | {'已移入回收站' if x['has_pdf'] else '原未取得全文'} |")
(OUT/'旧文献移出与删除说明.md').write_text('\n'.join(md)+'\n',encoding='utf-8')
overview=f'''# 文献年份筛选与补充结果

完成日期：2026-10-16（北京时间）。当前有效范围：2023-01-01至2026-10-16。

## 本轮结果

| 项目 | 结果 |
|---|---:|
| 当前候选文献 | 120篇 |
| 原候选保留 | 57篇 |
| 本轮补充候选 | 63篇 |
| 过早文献移出 | 62篇 |
| 另移出相关性待证条目 | 1篇（旧B019，原件保留） |
| 已有全文 | 18篇 |
| 本轮新增全文 | 11篇 |
| 当前120篇内本地全文合计 | 29篇 |
| 待补全文 | 91篇 |
| 本轮新增补充材料 | 1份 |

年份分布：2023年45篇、2024年31篇、2025年30篇、2026年14篇。

## 文件入口

- [当前120篇清单](120篇文献清单_2023至今.md)：年份、题名、期刊、DOI及本地全文链接。
- [可用Excel或WPS打开的总清单](120篇文献清单_2023至今.csv)。
- [待补全文91篇](待补全文_DOI清单_91篇.md)：题名、年份、DOI及获取结果。
- [91个DOI纯文本](待补全文_DOI纯文本_91篇.txt)：每行一个，方便复制检索。
- [待补全文CSV](待补全文_91篇.csv)。
- [新下载归档最终台账](下载归档最终台账_2023至今.json)：当前权威文件状态。
- [旧文献移出与删除说明](旧文献移出与删除说明.md)。

新论文PDF已归档到D:/文献；1份新补充文件放在D:/文献/补充材料_2023至今。新文件名以R编号开头；原有近期论文保留原文件名，避免重复下载。29篇只统计当前主120篇，不包括文件夹内的历史方法背景、冻结来源和相关性待证材料。

## 删除与校验

17篇2022年及以前的已下载论文、5份附属文件，以及项目内25份暂存/下载副本，共47个文件已移入回收站。每个文件在删除前核对SHA256及绝对路径，删除后确认原路径不存在；详见删除清单与执行日志。本轮曾生成的18份2022年论文文本与预览也已撤下。没有删除2023年及以后的论文。

120条DOI及规范化题名均去重，发表日期均在规定范围内。当前120条OpenAlex记录的撤稿标记均为false；这是索引标记检查，不是全面的勘误或撤稿审计。11份新论文PDF检查了PDF标识、可解析页数、前三页DOI和首页题名对应关系，归档后SHA256一致。原有18篇再次核对本地文件和SHA256。

## 获取与使用边界

题名、DOI、期刊和发表日期依据Crossref出版社登记元数据；公开全文线索使用OpenAlex、EuropePMC、出版社和机构地址。优先尝试明确公开的直链；403/429、证书错误或没有公开直链时直接记录，不反复尝试失败入口。Crossref两条广泛检索发生429，其余检索已提供足够候选，没有重试失败查询。X-MOL补查未获得足够可核验的近期新线索，未把无关检索结果算入清单；旧X02/X03/X04的2013/2015年线索不再推荐。

所有文献仍为候选，eligible_for_database=false。没有建立正式训练数据库，也没有训练模型；预测输出性质继续保留候选状态。综述和方法论文仅作背景/方法，不视为独立实验数据。若2023年之后的汇总论文引用2022年及更早的底层实验，不能把旧数据按新综述的年份重新入库。

旧B001（当前R001，2025年）主文仍可用于方法阅读；其补充Table S1有166条二手记录、41个来源DOI，并发现89/164行重复及32/33行相同列示输入对应不同电容。该表不符合直接导入条件，且含2023年前的底层来源，逐条来源年份尚需核定；不得整体导入。原5个冻结/排除来源仍禁止自动入库；年份符合不解除质量冻结。

当前参考资料仅完成书目、年份、获取及文件对应检查，尚未逐篇完成实验质量审计。复合材料、金属离子混合电容器、不同电解液、电极体系和质量分母需分开审核。文献多不等于有同等数量的独立材料样本。
'''
(OUT/'本轮结果总览.md').write_text(overview,encoding='utf-8')
readme=ROOT/'READ_ME_FIRST_FOR_NEXT_CHAT.md';backup=OUT/'历史接续入口_更新前.md'
assert not backup.exists();shutil.copy2(readme,backup)
handoff=f'''# 下个对话先读：生物质衍生碳超级电容器机器学习项目

更新时间：2026-10-16（北京时间）。项目：D:/机器学习-超级电容器；论文原件：D:/文献。

## 最新用户指令优先

只收集2023年1月1日至今的文献。本轮截止2026-10-16；不是滚动36个月，也不是仅2024至2026。早于2023年的不再作为当前资料/实验数据来源。用户明确授权删除已下载的旧论文；本轮已按已核验清单移入回收站，不得从旧暂存日志自动恢复。

候选不足120篇就补充。能直接下载的保存D:/文献；没有公开直链、403/429、证书错误或需登录付费时直接提供题名与DOI，不反复折腾入口。不要绕过登录、付费或验证码，不关闭TLS验证，不安装全局依赖，不运行论文附带exe。

## 当前权威入口

1. 文献更新_2023至今/本轮结果总览.md。
2. 文献更新_2023至今/下载归档最终台账_2023至今.json：当前120篇、下载状态、文件路径、发表日期、SHA256、失败记录。
3. 文献更新_2023至今/120篇文献清单_2023至今.md及同名CSV。
4. 文献更新_2023至今/待补全文_DOI清单_91篇.md，以及待补全文_DOI纯文本_91篇.txt。
5. 文献扩充_生物质碳_120篇/禁止入库与待核查来源.json：每次抽取前必须检查。年份符合不解除冻结。
6. 文献更新_2023至今/旧文献移出与删除说明.md、删除清单_2022年及以前.json和删除执行日志.jsonl。

原“文献下载_120篇”和“文献扩充_生物质碳_120篇”中的120篇/36份全文/84篇待补均为过时历史状态，只能追溯，不能当当前台账。更新前交接入口保存在文献更新_2023至今/历史接续入口_更新前.md。

## 已核验数字

当前120篇：旧候选保留57篇，新补63篇；2023年45、2024年31、2025年30、2026年14。旧清单62篇早于2023年，另1篇旧B019相关性待证移出主清单但保留近期原件。

当前主120篇内18份已有全文、11份本轮新全文，合计29份；91篇待补，已给DOI。新补充材料1份。17篇旧论文及附属/暂存副本共47个文件已移入回收站；本轮生成的18个2022年论文摘录和预览已撤下。不能用D:/文献文件夹总PDF数代替主120篇的29份统计。

题名与DOI去重，发表日期在规定范围；120条OpenAlex均无撤稿标记，但这不代表完成实验质量审计。所有eligible_for_database仍false，尚无正式训练数据和模型。

## 研究目标与边界

研究对象是生物质衍生碳超级电容器，最早碳纤维研究框架仅作历史。输出性质未定，不擅自锁定比电容、倍率、循环寿命或能量/功率，也不预选CNN。

顺序：收集近期文献及补充材料→逐篇来源和数据审核→建立数据库→根据实际完整性选输出和验证问题→建模。用户不是专业研究者，用白话说明术语及限制。

近年综述/机器学习汇总论文不是新的独立实验。旧底层研究数据不能按新综述年份混入。旧B001/当前R001（10.1002/cplu.202500342）的Table S1有166条二手记录、41个来源DOI，89/164行重复，32/33行同列示输入不同电容；含2023年前底层来源，逐条来源年份尚需核定，禁止整体导入。保留主文仅作方法/质量核查阅读。

原5个质量/范围冻结来源保持不变，具体见禁止入库JSON。本轮没有以论文性能高低、降低模型分数或不符合预期趋势作为排除理由。没有物理删除近期的冻结论文。

## 下一步

若用户补入PDF：先与当前120篇DOI去重，核对题名、首次发表日期、版本、来源和文件哈希，再更新当前台账；不要恢复早于2023年的文件。

若继续审核：优先当前R069、R081、R093、R095、R103、R104、R106等已下载的近期原始研究，先核对原文与补充材料，再做少量带出处的样例。2022年的旧B020/旧B021已退出且PDF删除，不再拿它们示范录入。

数据库分别记录文献、材料、测试和问题日志，保留DOI、样品号、页码/表图、单位、提取方式、实测/推算标记和核验状态；缺失不编造。同一材料不同电流点共用material_id。两/三电极、对称/非对称、纯碳/金属或聚合物复合、质量/面积/体积口径、原料/成品元素含量、倍率保持/循环保持必须分开。

训练按来源/材料分组验证，预处理和调参在训练折内完成。不能以放电时间等计算目标所需量冒充制备前输入。不以高R²作为唯一目标。

所有新脚本、说明、暂存、结果保存在本项目；论文归档D:/文献。新对话先读取E:/codex_memory/READ_ME_FIRST__Codex长期记忆.md及其索引必要文件，失败须明确提示。本轮未修改跨项目长期记忆。

## 工具

Python：C:/Users/ASUS/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe。pypdf、pdfplumber、pypdfium2可用，中文输出UTF-8。脚本有一次性输出/创建模式，禁止不检查就重跑全量下载、归档或删除脚本。下载、删除和归档均有独立清单及核验结果。
'''
readme.write_text(handoff,encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2))
