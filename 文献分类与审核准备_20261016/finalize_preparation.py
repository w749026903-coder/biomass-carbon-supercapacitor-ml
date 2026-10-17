from pathlib import Path
import json,hashlib,shutil,zipfile,xml.etree.ElementTree as ET,collections,sys
sys.stdout.reconfigure(encoding='utf-8')
OUT=Path(__file__).resolve().parent;ROOT=OUT.parent
summary=json.loads((OUT/'分类汇总.json').read_text(encoding='utf-8'))
main=json.loads((OUT/'主清单分类.json').read_text(encoding='utf-8'))
extras=json.loads((OUT/'额外资料分类.json').read_text(encoding='utf-8'))
inv=json.loads((OUT/'本地与压缩包文件盘点.json').read_text(encoding='utf-8'))
master=json.loads((OUT/'下载归档最终台账_分类准备后.json').read_text(encoding='utf-8'))
assert len(main)==len(master)==120 and len(extras)==65
assert len({x['doi'].lower() for x in main})==120
assert sum(x['fulltext_status']=='已取得全文' for x in main)==57
assert sum(x['fulltext_status']=='待补全文' for x in main)==63
assert all(x['eligible_for_database'] is False for x in main+extras)
assert hashlib.sha256(Path(r'D:\文献\1.zip').read_bytes()).hexdigest()==inv['zip_sha256']
for x in master:
    if x.get('local_pdf'):assert Path(x['local_pdf']).is_file() and hashlib.sha256(Path(x['local_pdf']).read_bytes()).hexdigest()==x['sha256']
for rec in inv['records']:
    for src in rec['sources']:
        if src['kind']=='local_pdf':assert hashlib.sha256(Path(src['path']).read_bytes()).hexdigest()==rec['sha256']
assert len(list(Path(r'D:\文献').glob('*.pdf')))==inv['library_pdf_files']==94
ns={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
workbook_checks=[]
with zipfile.ZipFile(OUT/'文献分类总表.xlsx') as z:
    for i,expected in [(1,120),(2,65),(3,12)]:
        tree=ET.fromstring(z.read(f'xl/worksheets/sheet{i}.xml'))
        populated=[r for r in tree.findall('.//m:sheetData/m:row',ns) if int(r.attrib['r'])>=9 and r.find('m:c',ns) is not None]
        assert len(populated)==expected,(i,len(populated),expected)
        assert not tree.findall('.//m:c[@t="e"]',ns)
        pane=tree.find('.//m:pane',ns)
        workbook_checks.append({'sheet_index':i,'records':len(populated),'pane':pane.attrib if pane is not None else None})
checks={'main_candidates':120,'local_fulltexts':57,'missing':63,'extra_unique_pdf_contents':65,'all_source_hashes_unchanged':True,'archive_unchanged':True,'workbook_sheets':workbook_checks,'all_training_eligibility_false':True}
with (OUT/'最终核验.json').open('x',encoding='utf-8') as f:json.dump(checks,f,ensure_ascii=False,indent=2)
labels={'A':'多孔碳与杂原子掺杂','B':'复合材料与特殊成分','C':'机器学习与数据方法','D':'综述与机制背景','E':'年份、版本与质量待核','F':'范围外资料'}
overview=['# 文献分类与审核准备','',
 '更新日期：2026-10-16。本轮只接收新增全文、分类并准备后续审核。预测输出与模型类型尚未确定。','',
 '## 当前情况','',
 '| 项目 | 数量 |','|---|---:|','| 主候选文献 | 120篇 |','| 本轮新增匹配全文 | 11篇 |','| 主清单已有全文 | 57篇 |','| 主清单待补全文 | 63篇 |','| 文献目录散装PDF | 94份 |','| 原压缩包PDF成员 | 49份 |','| 散装与压缩包按SHA256合并的不同PDF内容 | 122份 |','| 多位置或同内容重复出现的额外份数 | 21份 |','| 主清单之外的不同PDF内容 | 65份 |','',
 '120篇是候选书目数，122份是文件内容数，均不是独立材料样本数。主清单内63篇没有全文；清单外有65份文件/版本，部分相关、部分范围外或待核。不同版本可能来自同一底层研究，不能据文件数估计训练样本量。','',
 '## 分类入口','',
 '分类目录内存放阅读索引，点击可打开原PDF；原件、文件名和1.zip均保留，没有批量移动或删除原件。工作簿提供筛选，分类目录提供按类阅读入口。尚缺全文的条目明确标为题名初分，不能把分类当作准入批准。','',
 '[打开分类总表](文献分类总表.xlsx) · [审核与录入准备](审核与录入准备.md) · [剩余63篇DOI](待补全文_DOI清单_63篇.md)','',
 '| 类别 | 主120篇条目 | 额外资料条目 | 阅读入口 |','|---|---:|---:|---|']
for code,label in labels.items():
    folder=next(p.name for p in (OUT/'分类阅读目录').iterdir() if p.is_dir() and p.name.startswith({'A':'01','B':'02','C':'03','D':'04','E':'05','F':'06'}[code]))
    overview.append(f"| {label} | {sum(x['category']==code for x in main)} | {sum(x['category']==code for x in extras)} | [索引](分类阅读目录/{folder}/阅读索引.md) |")
overview += ['',
 '分类综合题名、摘要、首页和局部方法定位。已取得全文不等于完整实验质量审计；自动识别到两/三电极、循环、倍率等关键词，也不能直接认定某个具体样品的测试条件。','',
 '## 已完成的准备','',
 '- 主120篇更新到本轮台账，新增11篇直接引用用户现有文件路径，避免再复制一套PDF。',
 '- 将机器学习、综述、原始实验和复合材料分开；R037首页明确为REVIEW，已纠正旧初分标签。',
 '- 建立12条问题登记，包括已有5个冻结来源，以及R001、R088、R115、R024、R073、R046和SRC087的具体限制。',
 '- 建立文献、材料样品、测试记录和问题日志四张空模板，字段字典明确单位、样品层级、测试分母及出处。模板只有表头，没有伪造样例或填补缺失值。',
 '- 排好首批10篇原始实验阅读顺序。用户已补入其余能取得的论文，本阶段不再追逐下载缺口，先审核已有全文。','',
 '## 优先审核顺序','',
 '| 编号 | 题名 | 阅读重点 |','|---|---|---|']
queue=['R078','R091','R093','R103','R105','R106','R108','R111','R112','R117']
for pid in queue:
    x=next(x for x in main if x['id']==pid)
    overview.append(f"| {pid} | [{x['title']}](<{x['local_pdf']}>) | 样品系列、工艺条件、测试口径、原始表图与SI |")
overview += ['',
 '这些是阅读优先级，不是已通过数据质量审计的名单。R002、R005与额外SRC087另作方法阅读，重点核对数据来源、底层年份、材料分组和预处理隔离。','',
 '## 需要先处理的具体事项','',
 'R088首页摘要的表面积、质量负载单位已发现疑点并经图像确认，暂停数据录入，不能擅自改单位。R024含Ti，按金属参与材料分层。R115是未碳化木质素与活性炭复合，不能与纯生物质衍生碳直接合并。R001的二手训练表S1继续禁止整体导入。原5个冻结来源没有因补到PDF或年份符合而解冻。','',
 '本轮核对了题名/DOI、文件哈希、分类与版本线索；未逐篇确认所有公式和每个实验值，未建立可训练数据库，未运行模型。']
(OUT/'分类与准备总览.md').write_text('\n'.join(overview)+'\n',encoding='utf-8')
readme=ROOT/'READ_ME_FIRST_FOR_NEXT_CHAT.md';backup=OUT/'接续入口_分类前.md';assert not backup.exists();shutil.copy2(readme,backup)
t=readme.read_text(encoding='utf-8')
t=t.replace('1. 文献补入_1zip_20261016/补入结果总览.md。','1. 文献分类与审核准备_20261016/分类与准备总览.md。')
t=t.replace('2. 文献补入_1zip_20261016/下载归档最终台账_补入1zip后.json：当前120篇、46份全文、74篇待补、文件路径、发表日期、SHA256及压缩包出处。','2. 文献分类与审核准备_20261016/下载归档最终台账_分类准备后.json：当前120篇、57份全文、63篇待补、文件路径、分类、限制和SHA256。')
t=t.replace('3. 文献补入_1zip_20261016/120篇文献清单_补入后.md及同名CSV。','3. 文献分类与审核准备_20261016/文献分类总表.xlsx、主120篇_分类清单.csv、分类阅读目录。')
t=t.replace('4. 文献补入_1zip_20261016/待补全文_DOI清单_74篇.md，以及待补全文_DOI纯文本_74篇.txt。','4. 文献分类与审核准备_20261016/待补全文_DOI清单_63篇.md，以及待补全文_DOI纯文本_63篇.txt。')
t=t.replace('当前主120篇内已有46份全文：筛选后原有29份，加上本轮从用户D:/文献/1.zip补入17份；74篇待补，已给新DOI清单。原有补充材料不变。','当前主120篇内已有57份全文：筛选后29份、1.zip补入17份、本轮用户散装PDF补入11份；63篇待补，已给新DOI清单。原有补充材料不变。')
t=t.replace('主120篇的46份统计','主120篇的57份统计')
t=t.replace('## 研究目标与边界','## 最新分类准备阶段\n\n用户最新要求是“剩下能取得的论文已加入，先做好分类和准备”。本轮核对D:/文献内94份散装PDF及1.zip的49个PDF成员，按SHA256合并为122份不同PDF内容，21份属于重复出现；其中57份对应主120篇，另65份是清单外资料/版本。不能把122或185个目录条目当独立论文或样本数量。\n\n已建立6类阅读索引、分类总表、12条问题登记、四张空录入模板和首批10篇审核队列。分类以题名、摘要及局部方法定位为准，不代表实验质量已通过。缺全文条目为书目初分。原件未移动、重命名或删除，原ZIP未修改。\n\nR037是综述而非原始实验。R024含Ti，不归纯非金属掺杂。R115是未碳化木质素与活性炭复合，需核活性炭前驱体。R088摘要表面积与质量负载单位有疑点（首页图像确认），本轮冻结其数据录入，详见问题登记。原5个冻结/排除来源和R001的S1限制均保持。\n\n用户已补到其余能取得的全文，后续先审核已有文献，不反复追逐剩余下载缺口。下一步参考“审核与录入准备.md”和数据库录入准备下的空模板。文献补入_1zip_20261016内46份全文/74篇待补是旧快照，不能当当前台账。\n\n## 研究目标与边界')
readme.write_text(t,encoding='utf-8')
pointer=ROOT/'当前文献状态.md';assert not (OUT/'当前文献状态_分类前.md').exists();shutil.copy2(pointer,OUT/'当前文献状态_分类前.md')
pointer.write_text('''# 当前文献状态

更新：2026-10-16，用户新增其余可取得论文并完成分类准备后。

主候选120篇，57篇已有全文，63篇待补。有效发表范围为2023年至今。

- [分类与准备总览](文献分类与审核准备_20261016/分类与准备总览.md)
- [分类总表](文献分类与审核准备_20261016/文献分类总表.xlsx)
- [当前台账](文献分类与审核准备_20261016/下载归档最终台账_分类准备后.json)
- [审核与录入准备](文献分类与审核准备_20261016/审核与录入准备.md)
- [待补63篇](文献分类与审核准备_20261016/待补全文_DOI清单_63篇.md)
- [接续入口](READ_ME_FIRST_FOR_NEXT_CHAT.md)

文献目录和ZIP按内容去重后有122份PDF，其中65份在主清单之外，已分类。分类不等于实验数据质量合格。原件保留，没有训练模型。
''',encoding='utf-8')
print(json.dumps(checks,ensure_ascii=False,indent=2))
