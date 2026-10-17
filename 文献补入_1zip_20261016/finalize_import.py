from pathlib import Path
import json,csv,hashlib,collections,shutil,re,sys
sys.stdout.reconfigure(encoding='utf-8')
OUT=Path(__file__).resolve().parent;ROOT=OUT.parent
original_path=ROOT/'文献更新_2023至今/下载归档最终台账_2023至今.json'
rows=json.loads(original_path.read_text(encoding='utf-8'))
checked=json.loads((OUT/'核对结果.json').read_text(encoding='utf-8'))
manifest=json.loads((OUT/'归档清单_17篇.json').read_text(encoding='utf-8'))
byid={r['collection_id']:r for r in rows}
for item in manifest:
    row=byid[item['paper_id']];p=Path(item['target'])
    assert not row.get('local_pdf') and p.is_file()
    assert hashlib.sha256(p.read_bytes()).hexdigest()==item['sha256']
    row['download_status_before_zip']=row.get('download_status')
    row.update(local_pdf=str(p),download_status='用户压缩包补入_文件对应已核验',
               sha256=item['sha256'],bytes=p.stat().st_size,pages=item['pages'],
               source_kind='user_provided_archive',source_version=item['source_version'],
               source_archive=checked['archive_path'],source_archive_sha256=checked['archive_sha256'],
               source_archive_entry=item['archive_entry'],source_staged_path=item['source'],
               archive_import_date='2026-10-16',verification_scope=item['verification'],
               eligible_for_database=False)
    # Retrieval audit only; experiment/model quality has not been cleared.
    row['audit_status']='用户补入全文_题名DOI版本形式核对_待实验与数据质量审核'
assert len(rows)==120 and len({r['doi'].lower() for r in rows})==120
downloaded=[r for r in rows if r.get('local_pdf')]
missing=[r for r in rows if not r.get('local_pdf')]
assert len(downloaded)==46 and len(missing)==74
for row in downloaded:
    p=Path(row['local_pdf']);assert p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest()==row['sha256']
assert hashlib.sha256(Path(checked['archive_path']).read_bytes()).hexdigest()==checked['archive_sha256']
ledger_path=OUT/'下载归档最终台账_补入1zip后.json'
with ledger_path.open('x',encoding='utf-8') as f:json.dump(rows,f,ensure_ascii=False,indent=2)
headers=['编号','首次发表日期','年份','题名','期刊','DOI','DOI链接','用途初分','获取状态','本地PDF','是否允许进入数据库']
with (OUT/'120篇文献清单_补入后.csv').open('x',encoding='utf-8-sig',newline='') as f:
    w=csv.writer(f);w.writerow(headers)
    for x in rows:w.writerow([x['collection_id'],x['first_publication_date'],x['year'],x['title'],x['journal'],x['doi'],'https://doi.org/'+x['doi'],x['role'],x['download_status'],x.get('local_pdf',''),False])
def safe(s):return str(s).replace('|','\\|').replace('\n',' ')
md=['# 当前120篇文献清单：补入1.zip后','',
    '更新日期：2026-10-16。范围：2023年至今。候选组成仍为120篇；其中46篇有本地全文、74篇待补。全文取得不等于实验数据审核通过。','',
    '| 编号 | 年份 | 题名 | DOI | 全文状态 |','|---|---|---|---|---|']
for x in rows:
    status=f"[本地PDF](<{x['local_pdf']}>)" if x.get('local_pdf') else '待补'
    md.append(f"| {x['collection_id']} | {x['year']} | {safe(x['title'])} | [{x['doi']}](https://doi.org/{x['doi']}) | {status} |")
(OUT/'120篇文献清单_补入后.md').write_text('\n'.join(md)+'\n',encoding='utf-8')
md=['# 待补全文：74篇（补入1.zip后）','',
    '范围：2023年至今。原91篇待补清单已由本清单接续；本轮17篇已补齐，不再列入。R073收到的是2022年预印本，尚未确认对应的2023年正式版全文，因此仍保留在待补清单。','',
    '| 编号 | 年份 | 题名 | DOI | 备注 |','|---|---|---|---|---|']
for x in missing:
    note='收到2022年预印本，仍需2023年正式版' if x['collection_id']=='R073' else x.get('failure_summary','尚未取得全文')
    md.append(f"| {x['collection_id']} | {x['year']} | {safe(x['title'])} | [{x['doi']}](https://doi.org/{x['doi']}) | {safe(note)} |")
(OUT/'待补全文_DOI清单_74篇.md').write_text('\n'.join(md)+'\n',encoding='utf-8')
(OUT/'待补全文_DOI纯文本_74篇.txt').write_text('\n'.join(x['doi'] for x in missing)+'\n',encoding='utf-8')
with (OUT/'待补全文_74篇.csv').open('x',encoding='utf-8-sig',newline='') as f:
    w=csv.writer(f);w.writerow(['编号','年份','题名','期刊','DOI','DOI链接','备注'])
    for x in missing:w.writerow([x['collection_id'],x['year'],x['title'],x['journal'],x['doi'],'https://doi.org/'+x['doi'],'收到2022年预印本，仍需2023年正式版' if x['collection_id']=='R073' else x.get('failure_summary','尚未取得全文')])
extras=[x for x in checked['entries'] if not x.get('verified_match')]
assert len(extras)==32
md=['# 压缩包内未计入本次补齐数量的32个文件','',
    '不计入不等于全部无用。这里包含清单外相关候选、不同研究方向的资料、重复件和版本待核文件。原压缩包1.zip完整保留，没有删除其中任何成员。未将这些文件自动加入120篇主清单或训练数据库。','',
    '## 已明确的问题','',
    '- 包内第37份：与R073题名相同，但首页标明2022-08-02、Research Square预印本及DOI 10.21203/rs.3.rs-1895857/v1。当前R073登记的正式论文是2023年、DOI 10.1007/s10854-023-09885-8，两者不能按同一版本直接记为补齐。','- 包内第44份：正文研究PFAS吸附，本身DOI为10.1016/j.matlet.2025.138050。R046的DOI出现在参考文献，不能作为R046全文已到手的证据。','- 包内第46、47份：SHA256完全相同，是同一PDF的两个文件名。','- 包内第23份：与D:/文献内已有Co-MOF镍泡沫预印本SHA256相同；该论文不在当前120篇内，不重复归档。','',
    '清单外还包括看起来与生物质碳储能方向相关的资料，例如白桦碳、竹碳、玉米秸秆碳、黑液碳、青香蕉皮碳、椰枣废弃物碳和来源分组机器学习论文等。这里只依据本地首页和题名做相关性提示，尚未逐一核验正式发表信息及实验质量。它们可以作为后续扩充候选，不与已补齐的17篇混算。','',
    '| 包内序号 | 文件名 | 前3页识别的DOI（不保证均为该文自身DOI） | 当前处理 |','|---|---|---|---|']
for x in extras:
    md.append(f"| {x['archive_index']} | {safe(Path(x['archive_entry']).name)} | {safe('; '.join(x.get('first3_doi_strings',[])[:3]) or '前三页未识别')} | {safe(x['disposition'])} |")
(OUT/'未计入主清单的32文件_原因说明.md').write_text('\n'.join(md)+'\n',encoding='utf-8')
summary={'date':'2026-10-16','archive_path':checked['archive_path'],'archive_sha256':checked['archive_sha256'],
         'archive_pdf_entries':49,'archive_unique_pdf_hashes':48,'new_matching_fulltexts':17,'outside_main_or_unresolved_entries':32,
         'duplicate_within_archive_extra_copies':1,'duplicate_with_existing_local_pdf':1,'older_preprint_not_imported':1,
         'candidates':120,'fulltexts_before':29,'fulltexts_after':46,'missing_before':91,'missing_after':74,
         'new_pdf_pages':sum(x['pages'] for x in manifest),'training_eligible_records':0,'archive_preserved':True}
with (OUT/'补入核验汇总.json').open('x',encoding='utf-8') as f:json.dump(summary,f,ensure_ascii=False,indent=2)
md=['# 1.zip文献补入结果','',
    '日期：2026-10-16。来源：D:/文献/1.zip，原压缩包保留且前后SHA256一致。','',
    '| 项目 | 结果 |','|---|---:|','| 包内PDF文件 | 49 |','| 去除包内字节重复后的文件 | 48 |','| 本次确认补齐主清单全文 | 17 |','| 其余另列文件 | 32 |','| 主候选文献数 | 120，组成未改变 |','| 当前主清单已有全文 | 46（原29+本次17） |','| 当前待补全文 | 74（原91-本次17） |','',
    '本次17份PDF按DOI、首页题名和当前台账发表年份核对，检查PDF标识、页数、ZIP CRC及SHA256，保存到D:/文献，归档后哈希一致。第38份出版社首页因文字连写使初次自动分词匹配不足，已通过完整规范化题名、DOI及首页图像确认，纳入R041。没有覆盖既有PDF，没有修改原压缩包，没有将取得全文等同于实验质量合格。','',
    '## 本次补齐的17篇','',
    '| 编号 | 年份 | 题名 | DOI | 页数 | 本地全文 |','|---|---|---|---|---:|---|']
for item in manifest:
    x=byid[item['paper_id']]
    md.append(f"| {x['collection_id']} | {x['year']} | {safe(x['title'])} | [{x['doi']}](https://doi.org/{x['doi']}) | {x['pages']} | [PDF](<{x['local_pdf']}>) |")
md += ['', '## 当前文件入口','',
    '- [最新120篇清单](120篇文献清单_补入后.md)。',
    '- [最新待补74篇，题名与DOI](待补全文_DOI清单_74篇.md)。',
    '- [74个DOI纯文本](待补全文_DOI纯文本_74篇.txt)。',
    '- [未计入主清单的32个文件及原因](未计入主清单的32文件_原因说明.md)。',
    '- [当前权威台账](下载归档最终台账_补入1zip后.json)。','',
    '当前台账只更新获取状态；所有eligible_for_database仍false，没有训练模型。原质量冻结与2023年至今的年份要求继续生效。']
(OUT/'补入结果总览.md').write_text('\n'.join(md)+'\n',encoding='utf-8')
readme=ROOT/'READ_ME_FIRST_FOR_NEXT_CHAT.md';backup=OUT/'接续入口_补入前.md'
assert not backup.exists();shutil.copy2(readme,backup)
t=readme.read_text(encoding='utf-8')
t=t.replace('1. 文献更新_2023至今/本轮结果总览.md。','1. 文献补入_1zip_20261016/补入结果总览.md。')
t=t.replace('2. 文献更新_2023至今/下载归档最终台账_2023至今.json：当前120篇、下载状态、文件路径、发表日期、SHA256、失败记录。','2. 文献补入_1zip_20261016/下载归档最终台账_补入1zip后.json：当前120篇、46份全文、74篇待补、文件路径、发表日期、SHA256及压缩包出处。')
t=t.replace('3. 文献更新_2023至今/120篇文献清单_2023至今.md及同名CSV。','3. 文献补入_1zip_20261016/120篇文献清单_补入后.md及同名CSV。')
t=t.replace('4. 文献更新_2023至今/待补全文_DOI清单_91篇.md，以及待补全文_DOI纯文本_91篇.txt。','4. 文献补入_1zip_20261016/待补全文_DOI清单_74篇.md，以及待补全文_DOI纯文本_74篇.txt。')
t=t.replace('当前主120篇内18份已有全文、11份本轮新全文，合计29份；91篇待补，已给DOI。新补充材料1份。','当前主120篇内已有46份全文：筛选后原有29份，加上本轮从用户D:/文献/1.zip补入17份；74篇待补，已给新DOI清单。原有补充材料不变。')
t=t.replace('主120篇的29份统计','主120篇的46份统计')
t=t.replace('## 研究目标与边界','## 本轮用户压缩包接收情况\n\nD:/文献/1.zip有49个PDF、48个独立SHA256。其中17份确认补齐主清单，已归档D:/文献；原ZIP保留且哈希未变。另32个文件未算作主清单补齐，详见文献补入_1zip_20261016/未计入主清单的32文件_原因说明.md：包含清单外资料、1个包内重复副本、1个与本地已有Co-MOF预印本重复的文件、R073同题的2022年Research Square预印本、以及DOI仅在参考文献出现的PFAS吸附论文。不要自动把这32份都当无用，也不要未经进一步核对就计入主清单或训练库。\n\n文献更新_2023至今目录的29份全文/91篇待补是补包前快照；从现在起以本轮补入后台账为准。新增文件有ZIP成员名和ZIP SHA256，原始下载渠道由用户提供，未验证用户具体从何站点下载。\n\n## 研究目标与边界')
readme.write_text(t,encoding='utf-8')
pointer=f'''# 当前文献状态

更新：2026-10-16，接收D:/文献/1.zip后。

当前120篇候选，46篇已有全文，74篇待补。有效发表范围为2023年至今。

- [接续入口](READ_ME_FIRST_FOR_NEXT_CHAT.md)
- [本轮结果](文献补入_1zip_20261016/补入结果总览.md)
- [当前台账](文献补入_1zip_20261016/下载归档最终台账_补入1zip后.json)
- [待补74篇](文献补入_1zip_20261016/待补全文_DOI清单_74篇.md)
- [未计入主清单的包内32文件](文献补入_1zip_20261016/未计入主清单的32文件_原因说明.md)

文献更新_2023至今目录中的29份全文、91篇待补是上一阶段快照。未完成实验数据审核，未训练模型。
'''
with (ROOT/'当前文献状态.md').open('x',encoding='utf-8') as f:f.write(pointer)
print(json.dumps(summary,ensure_ascii=False,indent=2))
