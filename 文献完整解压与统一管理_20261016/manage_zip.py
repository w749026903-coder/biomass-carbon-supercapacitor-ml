from pathlib import Path
import collections, csv, hashlib, io, json, re, shutil, sys, zipfile
from pypdf import PdfReader

sys.stdout.reconfigure(encoding='utf-8')
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
CAT = ROOT / '文献分类与审核准备_20261016'
LIB = Path(r'D:\文献')
ARCHIVE = LIB / '1.zip'
DEST = LIB / '1_完整解压'

def read(p):
    return json.loads(p.read_text(encoding='utf-8-sig'))

def write(p, data):
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def paper_files():
    return sorted(p for p in LIB.rglob('*.pdf')
                  if not any(part.startswith('补充材料') for part in p.relative_to(LIB).parts[:-1]))

def plan():
    inv = read(CAT / '本地与压缩包文件盘点.json')
    main = read(CAT / '主清单分类.json')
    extras = read(CAT / '额外资料分类.json')
    classes = {x['sha256']: x for x in main + extras if x.get('sha256')}
    records = {x['sha256']: x for x in inv['records']}
    assert sha(ARCHIVE) == inv['zip_sha256']
    before = [{'path': str(p), 'sha256': sha(p)} for p in paper_files()]
    assert set(x['sha256'] for x in before) <= set(records), 'New unclassified PDF: refresh required'
    assert not DEST.exists(), 'Extraction destination already exists; inspect before continuing'
    entries = []
    with zipfile.ZipFile(ARCHIVE) as z:
        for info in z.infolist():
            if info.is_dir():
                continue
            assert info.filename.lower().endswith('.pdf'), info.filename
            assert not info.flag_bits & 1
            assert info.file_size < 60 * 1024 * 1024
            data = z.read(info)
            digest = hashlib.sha256(data).hexdigest()
            assert data[:1024].lstrip().startswith(b'%PDF-')
            rec, c = records[digest], classes[digest]
            assert any(s.get('entry') == info.filename for s in rec['sources'])
            number = len(entries) + 1
            # Bounded names avoid Windows path limits; manifest preserves exact original names.
            stem = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', Path(info.filename).stem)
            stem = stem[:95].strip(' .') or 'paper'
            folder = DEST / c['shelf']
            if c.get('year') and c['year'] < 2023:
                folder = folder / '已排除_早于2023年'
            target = folder / f'{number:03d}_{c["id"]}__{stem}.pdf'
            assert target.resolve().is_relative_to(DEST.resolve())
            entries.append({'member_index': number, 'entry': info.filename,
                            'target': str(target), 'sha256': digest, 'bytes': len(data),
                            'id': c['id'], 'shelf': c['shelf'], 'title': c['title'],
                            'year': c.get('year'), 'doi': c.get('doi'),
                            'quality_gate': c['quality_gate'],
                            'local_pdf_before': rec.get('local_pdf'),
                            'eligible_for_database': False})
    result = {'archive': str(ARCHIVE), 'archive_sha256': sha(ARCHIVE),
              'destination': str(DEST), 'entries': entries, 'paper_files_before': before}
    write(HERE / '完整解压计划.json', result)
    print(json.dumps({'members': len(entries), 'unique_contents': len({x['sha256'] for x in entries}),
                      'existing_paper_files': len(before), 'destination': str(DEST)}, ensure_ascii=False))

def extract():
    p = read(HERE / '完整解压计划.json')
    assert sha(ARCHIVE) == p['archive_sha256']
    checked = []
    with zipfile.ZipFile(ARCHIVE) as z:
        assert len([i for i in z.infolist() if not i.is_dir()]) == len(p['entries'])
        for row in p['entries']:
            target = Path(row['target'])
            assert target.resolve().is_relative_to(DEST.resolve())
            data = z.read(row['entry'])
            assert hashlib.sha256(data).hexdigest() == row['sha256']
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                assert sha(target) == row['sha256'], 'Existing target differs; no overwrite'
            else:
                with target.open('xb') as f:
                    f.write(data)
            assert sha(target) == row['sha256']
            pages = len(PdfReader(io.BytesIO(target.read_bytes())).pages)
            assert pages > 0
            checked.append({**row, 'pages': pages, 'verified': True})
    assert sha(ARCHIVE) == p['archive_sha256']
    assert len(list(DEST.rglob('*.pdf'))) == len(checked)
    for old in p['paper_files_before']:
        assert sha(Path(old['path'])) == old['sha256']
    write(HERE / '完整解压结果.json', {**p, 'entries': checked,
          'archive_unchanged': True, 'existing_pdfs_unchanged': True})
    print(json.dumps({'extracted': len(checked), 'verified_hashes_and_pdf_pages': len(checked),
                      'archive_unchanged': True, 'existing_pdfs_unchanged': True}, ensure_ascii=False))

def backup(p):
    target = HERE / '更新前快照' / p.relative_to(ROOT)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        shutil.copy2(p, target)

def update():
    result = read(HERE / '完整解压结果.json')
    inv = read(CAT / '本地与压缩包文件盘点.json')
    main = read(CAT / '主清单分类.json')
    extras = read(CAT / '额外资料分类.json')
    master = read(CAT / '下载归档最终台账_分类准备后.json')
    workbook = read(CAT / '工作簿数据.json')
    summary = read(CAT / '分类汇总.json')
    for name in ['本地与压缩包文件盘点.json', '主清单分类.json', '额外资料分类.json',
                 '工作簿数据.json', '分类汇总.json', '重复与多位置文件.json',
                 '主120篇_分类清单.csv', '额外65份_分类清单.csv', '文献分类总表.xlsx',
                 '分类与准备总览.md', '最终核验.json']:
        backup(CAT / name)
    for p in (CAT / '分类阅读目录').glob('*/阅读索引.md'):
        backup(p)
    for name in ['当前文献状态.md', 'READ_ME_FIRST_FOR_NEXT_CHAT.md']:
        backup(ROOT / name)
    records = {x['sha256']: x for x in inv['records']}
    canonical = {}
    for row in result['entries']:
        rec = records[row['sha256']]
        target = Path(row['target'])
        assert sha(target) == row['sha256']
        source = {'kind': 'local_pdf', 'path': str(target), 'filename': target.name,
                  'bytes': target.stat().st_size, 'origin': 'zip_extraction',
                  'archive': str(ARCHIVE), 'archive_entry': row['entry']}
        if not any(s.get('path') == str(target) for s in rec['sources']):
            rec['sources'].append(source)
        if not rec.get('local_pdf'):
            rec['local_pdf'] = str(target)
        canonical[row['sha256']] = rec['local_pdf']
    changed = []
    for x in extras:
        if not x.get('local_pdf'):
            x['local_pdf'] = canonical[x['sha256']]
            x['fulltext_status'] = '本地PDF（压缩包已解压）'
            changed.append(x['id'])
        x['local_pdf_copies'] = [s['path'] for s in records[x['sha256']]['sources'] if s['kind'] == 'local_pdf']
    files = paper_files()
    file_rows = [{'path': str(p), 'sha256': sha(p), 'bytes': p.stat().st_size} for p in files]
    counts = collections.Counter(x['sha256'] for x in file_rows)
    assert len(counts) == len(records) == 122
    assert len(files) == len(result['paper_files_before']) + len(result['entries'])
    assert all(rec.get('local_pdf') and Path(rec['local_pdf']).is_file() for rec in records.values())
    all_pdf_files = list(LIB.rglob('*.pdf'))
    stats = {'date': '2026-10-16', 'archive_pdf_members': len(result['entries']),
             'archive_unique_contents': len({x['sha256'] for x in result['entries']}),
             'extracted_pdf_files': len(result['entries']), 'zip_only_members_remaining': 0,
             'root_pdf_files': len(list(LIB.glob('*.pdf'))), 'paper_pdf_files': len(files),
             'unique_paper_pdf_contents': len(counts), 'duplicate_paper_file_copies': len(files)-len(counts),
             'supplement_pdf_files': len(all_pdf_files)-len(files), 'library_all_pdf_files': len(all_pdf_files),
             'main_candidates': len(main), 'main_fulltexts': sum(bool(x.get('local_pdf')) for x in main),
             'main_missing': sum(not x.get('local_pdf') for x in main),
             'extra_unique_contents': len(extras), 'newly_accessible_unique_contents': len(changed),
             'confirmed_pre2023_excluded_contents': [x['id'] for x in extras if x.get('year') and x['year'] < 2023],
             'all_eligible_for_database_false': all(x['eligible_for_database'] is False for x in main+extras)}
    inv.update({'library_pdf_files': stats['root_pdf_files'], 'paper_pdf_files': len(files),
                'library_all_pdf_files': len(all_pdf_files), 'extracted_pdf_files': len(result['entries']),
                'zip_only_members_remaining': 0, 'counting_note': 'library_pdf_files仅指根目录；paper_pdf_files含解压副本、排除补充材料。'})
    summary.update({'paper_pdf_files': len(files), 'extracted_pdf_files': len(result['entries']),
                    'zip_only_members_remaining': 0, 'library_all_pdf_files': len(all_pdf_files),
                    'supplement_pdf_files': stats['supplement_pdf_files'], 'duplicate_extra_occurrences': len(files)-len(counts),
                    'counting_note': 'duplicate_extra_occurrences为独立PDF文件数减SHA256去重数，ZIP内成员不另算文件副本。'})
    workbook.update({'main': main, 'extras': extras, 'summary': summary})
    for name, data in [('本地与压缩包文件盘点.json', inv), ('额外资料分类.json', extras),
                       ('工作簿数据.json', workbook), ('分类汇总.json', summary)]:
        write(CAT / name, data)
    duplicates = [{'id': rec.get('paper_id') or rec['source_record_id'], 'sha256': rec['sha256'],
                   'occurrences': len(rec['sources']),
                   'physical_pdf_copies': sum(s['kind'] == 'local_pdf' for s in rec['sources']),
                   'sources': rec['sources'], 'action': '按内容计1份；保留ZIP出处和实际PDF副本'}
                  for rec in inv['records'] if len(rec['sources']) > 1]
    write(CAT / '重复与多位置文件.json', duplicates)
    # Retain the original CSV fields and all bibliographic classifications.
    for name, rows in [('主120篇_分类清单.csv', main), ('额外65份_分类清单.csv', extras)]:
        p = CAT / name
        with p.open(encoding='utf-8-sig', newline='') as f:
            table = list(csv.DictReader(f))
        by_id = {x['id']: x for x in rows}
        for row in table:
            c = by_id[row['编号']]
            row['本地PDF'] = c.get('local_pdf') or ''
            row['全文状态'] = c['fulltext_status']
        with p.open('w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=list(table[0]))
            writer.writeheader(); writer.writerows(table)
    for p in (CAT / '分类阅读目录').glob('*/阅读索引.md'):
        text = p.read_text(encoding='utf-8')
        for x in extras:
            if x.get('archive_entry'):
                old = f'[1.zip](<D:/文献/1.zip>)内：{x["archive_entry"]}'
                text = text.replace(old, f'[PDF](<{x["local_pdf"]}>)')
        p.write_text(text, encoding='utf-8')
    # Physical file management list: one row per unique PDF content, all copies retained.
    managed = []
    classified = {x['sha256']: x for x in main + extras if x.get('sha256')}
    for rec in inv['records']:
        c = classified[rec['sha256']]
        copies = [s['path'] for s in rec['sources'] if s['kind'] == 'local_pdf']
        managed.append({'编号': c['id'], '范围': c['population'], '分类': c['shelf'],
                        '年份': c.get('year') or '', '题名': c['title'], 'DOI': c.get('doi') or '',
                        '准入状态': c['quality_gate'], '推荐PDF': rec['local_pdf'],
                        '实际副本数': len(copies), '全部PDF位置': '\n'.join(copies),
                        'SHA256': rec['sha256'], '允许训练': False})
    with (HERE / '全部122份PDF_统一管理清单.csv').open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(managed[0])); writer.writeheader(); writer.writerows(managed)
    write(HERE / '全部PDF文件清单.json', file_rows)
    write(HERE / '统一计数与核验.json', stats)
    lines = ['# 压缩包完整解压与统一管理', '', '更新：2026-10-16。', '',
             f'1.zip的{stats["archive_pdf_members"]}个PDF成员已全部解压，逐件校验SHA256及PDF可读性，未遗漏。原ZIP和原有PDF未改动。', '',
             f'解压位置：[{DEST.name}](<{DEST}>)。按既有六类存放；文件名含ZIP成员序号和文献编号，原始全名见下面逐件清单。', '',
             '| 统计口径 | 数量 |', '|---|---:|',
             f'| ZIP中的PDF成员 | {stats["archive_pdf_members"]} |',
             f'| ZIP按内容去重 | {stats["archive_unique_contents"]} |',
             f'| 完成解压的PDF文件 | {stats["extracted_pdf_files"]} |',
             '| 仍只在ZIP中、没有独立PDF的成员 | 0 |',
             f'| 原文献根目录散装PDF | {stats["root_pdf_files"]} |',
             f'| 论文PDF文件总数（含解压副本） | {stats["paper_pdf_files"]} |',
             f'| 论文PDF按内容去重 | {stats["unique_paper_pdf_contents"]} |',
             f'| 重复PDF副本数 | {stats["duplicate_paper_file_copies"]} |',
             f'| 补充材料PDF（单独统计） | {stats["supplement_pdf_files"]} |',
             f'| 文献目录所有独立PDF文件合计 | {stats["library_all_pdf_files"]} |',
             '| 主候选书目 | 120 |', '| 主清单已取得全文 | 57 |', '| 主清单待补全文 | 63 |',
             '| 主清单外不同PDF内容/版本 | 65 |', '',
             '122份表示不同PDF内容，包含范围外、待核、不同版本等资料，不表示122篇合格独立研究；主120篇的全文数量仍为57篇。', '',
             '包内2022年预印本SRC113单独放入“已排除_早于2023年”，仅保留为本次完整解包的原始材料，不计入有效年份文献或训练数据。其余待核/范围外/冻结状态保持。', '',
             '[分类总表](../文献分类与审核准备_20261016/文献分类总表.xlsx) · '
             '[全部122份PDF管理清单](全部122份PDF_统一管理清单.csv) · '
             '[六类阅读目录](../文献分类与审核准备_20261016/分类与准备总览.md)', '',
             '## ZIP逐件核对', '', '| 序号 | 文献编号 | 年份 | 解压PDF | 核验 |', '|---|---|---|---|---|']
    for row in result['entries']:
        lines.append(f'| {row["member_index"]} | {row["id"]} | {row.get("year") or "待核"} | [{row["title"].replace("|", "／")}]' 
                     f'(<{row["target"]}>) | SHA256一致，{row["pages"]}页 |')
    (HERE / '完整解压与统一管理说明.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    p = CAT / '分类与准备总览.md'
    text = p.read_text(encoding='utf-8')
    block = ('\n## 压缩包已完整解压（最新）\n\n'
             '1.zip的49个PDF已全部解压至D:/文献/1_完整解压，按六类存放并逐件核验。'
             '原根目录94个PDF，加49个解压文件，共143个论文PDF；按内容去重122份，重复副本21份。'
             '另有3个补充材料PDF，因此资源管理器递归数到的全部PDF为146个。ZIP本身及包内成员不再另加进独立文件总数。'
             '其中2022年预印本已单独标记排除，122不是有效近期独立文献数量。主清单仍为120篇、57份全文、63篇待补。\n\n'
             '[完整解压和统一管理说明](../文献完整解压与统一管理_20261016/完整解压与统一管理说明.md)\n\n')
    text = text.replace('## 当前情况', block + '## 分类准备时的统计快照')
    p.write_text(text, encoding='utf-8')
    p = ROOT / '当前文献状态.md'
    text = p.read_text(encoding='utf-8').replace('更新：2026-10-16，用户新增其余可取得论文并完成分类准备后。', '更新：2026-10-16，压缩包完整解压并统一管理后。')
    text += ('\n1.zip的49个PDF成员已全部解压，包内去重48份，未遗漏。论文PDF现有143个实际文件，内容去重122份，重复副本21份；另有3个补充材料PDF，目录递归PDF总数146个。2022年预印本单独标记排除，不算有效近期文献。\n\n'
             '- [完整解压与统一管理说明](文献完整解压与统一管理_20261016/完整解压与统一管理说明.md)\n')
    p.write_text(text, encoding='utf-8')
    p = ROOT / 'READ_ME_FIRST_FOR_NEXT_CHAT.md'
    text = p.read_text(encoding='utf-8')
    addition = ('## 压缩包完整解压与统一计数（最新）\n\n'
                '用户已明确授权全部解压并统一管理。1.zip的49个PDF成员已完整解压到D:/文献/1_完整解压，按六类存放；每件SHA256与ZIP一致且PDF页数可读。原ZIP、原有94个散装PDF都未改动。\n\n'
                '最新物理口径：143个论文PDF文件，内容去重122份，重复副本21份；补充材料PDF另计3份，全目录递归PDF为146个。包内49成员/48独立内容是来源审计口径，不再加进实际文件总数。ZIP-only剩余0。主120篇/57份全文/63篇待补、额外65份内容的分类和冻结规则不变。\n\n'
                '原先只在包内的28份独立内容已全部有本地路径，分类JSON、CSV、阅读索引与总表已同步。2022年SRC113解压件置于“已排除_早于2023年”，仅保留原始包材料，不计有效文献或训练。新的完整解压和管理入口：文献完整解压与统一管理_20261016/完整解压与统一管理说明.md；逐件结果为完整解压结果.json；统一计数与核验.json含本次最终数字。\n\n')
    text = text.replace('## 研究目标与边界', addition + '## 研究目标与边界')
    p.write_text(text, encoding='utf-8')
    assert len(main) == len(master) == 120 and len(extras) == 65
    assert sum(bool(x.get('local_pdf')) for x in main) == 57
    assert all(x.get('local_pdf') for x in extras)
    assert len(changed) == 28
    print(json.dumps(stats, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    {'plan': plan, 'extract': extract, 'update': update}[sys.argv[1]]()
