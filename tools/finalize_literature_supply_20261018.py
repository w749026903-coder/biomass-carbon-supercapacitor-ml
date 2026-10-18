"""Audit this acquisition batch and build component-specific manual download tasks.

Never imports candidates into the scientific database or grants admission.
"""
from pathlib import Path, PurePosixPath
import collections, concurrent.futures, csv, hashlib, json, re, unicodedata
import xml.etree.ElementTree as ET
import zipfile
from acquire_literature_supply_20261018 import ROOT, OUT, crossref, dump, pdf_identity

DB_HASH = '65af93be781d858ea8c7a9a2b3b1515acf799be1ad8e94d2231199c9c31f95f1'

# Reviewed against each target's primary metadata; classification is a retrieval
# priority, not a record-level scientific admission decision.
BACKGROUND = {
    22: '摘要为木质素磺酸盐/石墨烯/高铁酸钾三元水凝胶，面积口径；不作本轮普通生物质碳优先下载',
    45: '摘要为Fe3O4@C与NiCo2S4@C非对称器件',
    52: '摘要碳源为间苯二酚-甲醛树脂；非生物质主体碳源',
    53: '题名明确Cu/Ni/S、MOF、FeCo硫化物复合电极',
    54: '摘要含高比例铁/钴氧化物；所述循环为50 mV/s，非本轮GCD主线',
    55: '摘要明确NiS负载木质碳微球复合物',
    81: '题名明确NiMo-LDH复合物',
    82: '题名明确尖晶石氧化物/ZIF复合物',
    88: '题名明确碳/赤铁矿复合物',
    95: '摘要主体为ZIF-67衍生碳，CMC为粘结组分，含金属催化剂；本轮降为背景',
    103: '题名明确RuO2/Ru复合结构',
    106: '摘要为碳氮化物与HQ氧化还原凝胶电解液体系',
    112: '摘要为C60碳球添加到PVA/TEMPO纤维素凝胶电解液；非目标碳电极',
    114: '摘要明确Ni(OH)2/NiO与金属硫化物复合物',
    116: '摘要为电纺合成聚合物碳纳米纤维，未建立目标生物质前驱体',
    120: '题名为NiO薄膜/碳纸复合电极',
}
SEPARATE = {
    9: '摘要同时含水系3E表征与HEC/KOH柔性器件循环；逐测试分开，不能将器件循环标为3E',
    38: '摘要为PAN与木炭混合前驱体及对称器件；混合碳源另列',
    41: '摘要明确Fe残留1.7 wt.%及固态器件；金属残留和循环配置待逐记录审查',
    46: '题名明确有机体系，保留为旁系',
    47: '摘要明确木质素/PAN混合碳源，另列',
    50: '摘要明确rGO/木焦油碳/纤维素复合碳源，另列',
    68: '题名与摘要明确准固态器件，逐测试另列',
    69: '题名明确固态器件，另列',
    76: '题名明确准固态器件，另列',
    87: '摘要明确金属辅助活化与金属-碳界面模型，最终残留相需审查',
    90: '题名明确PAN增强纤维素/木质素混合碳源，另列',
    99: '摘要同时含HAC水系电极与HAC/EMD钠离子混合器件，逐测试另列',
    102: '题名明确准固态器件，另列',
    104: '摘要明确Fe-Nx位点及对称器件，金属位点另列',
    110: '摘要为商业碳纤维表面木质素涂层与PVA/H3PO4器件，另列',
    115: '摘要为木纤维素/石墨烯纳米片混合电极，另列',
    119: '摘要为纤维素/MWCNT混合碳源与准固态器件，面积口径另列',
}
CORRECTIONS = {
    98: {'original_doi': '10.1021/acssusresmgt.4c00258', 'reason': '正文勘误修正SEM/XPS图、C/O/S元素组成并补FTIR/XRD方法；不独立计数，未来审查原文必须连同此文，保留修正前后证据。原文不在当前231个已知DOI基线中。'},
    107: {'original_doi': '10.3390/molecules30010089', 'reason': '已读一页PDF：只更正通讯作者顺序，未更正实验数据；不新增独立研究，也不因此冻结原文已准入记录。'},
}


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def csvwrite(name, rows, fields):
    with (OUT / name).open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        w.writeheader()
        w.writerows(rows)


def doiwrite(name, rows):
    dois = list(dict.fromkeys(r['doi'] for r in rows))
    (OUT / name).write_text(''.join(d + '\n' for d in dois), encoding='utf-8')


def finalize():
    from pypdf import PdfReader
    from verify_expansion_v07_20261018 import verify as verify_parent
    historical = {r['doi']: r for r in canonical_history()}
    rows = [json.loads(p.read_text(encoding='utf-8')) for p in sorted((OUT / 'records').glob('SUP_???.json'))]
    checks = []
    def check(name, ok):
        checks.append({'check': name, 'passed': bool(ok)})
        if not ok:
            raise AssertionError(name)
    check('144_unique_targets', len(rows) == len({r['doi'] for r in rows}) == 144)
    check('new_120_historical_22_existing_2', collections.Counter(r['cohort'] for r in rows) == {'new_target':120, 'historical_gap':22, 'existing_candidate_SI_check':2})
    baseline = json.loads((OUT / 'existing_availability_baseline.json').read_text(encoding='utf-8'))
    reviews = []
    audit_files = []
    for r in rows:
        n = int(r['supply_id'].split('_')[1])
        r['retrieval_title'] = r['title']
        meta = historical.get(r['doi'])
        if meta and meta['verified']:
            r['title'] = meta['title']
            r['year'] = meta['year']
            r['metadata_identity'] = 'Crossref exact DOI verified; original acquisition title retained'
        else:
            r['metadata_identity'] = '; '.join(r.get('metadata_sources', []))
        if n in CORRECTIONS:
            r['final_scope'] = 'correction_only'
            r['scope_reason'] = CORRECTIONS[n]['reason']
            r['corrects_doi'] = CORRECTIONS[n]['original_doi']
        elif n in BACKGROUND:
            r['final_scope'] = 'background_only'
            r['scope_reason'] = BACKGROUND[n]
        elif n in SEPARATE:
            r['final_scope'] = 'separate_system_candidate'
            r['scope_reason'] = SEPARATE[n]
        elif r['cohort'] != 'new_target':
            r['final_scope'] = 'historical_component_recovery'
            r['scope_reason'] = '沿用此前逐项缺件任务；本次只补正文/SI，不改历史科学判定'
        else:
            r['final_scope'] = 'priority_carbon_candidate'
            r['scope_reason'] = '题名/摘要为生物质或生物聚合物碳电极候选；尚需全文逐测试确认循环配置、工况与端点'
        r['training_eligible'] = False
        r['admission_status'] = 'not_reviewed_for_admission_this_batch'
        check(r['supply_id'] + ':new_not_in_known_baseline', r['cohort'] != 'new_target' or r['doi'] not in baseline)
        for f in r['files']:
            p = ROOT / f['path']
            check(f['path'] + ':contained', ROOT in p.resolve().parents)
            check(f['path'] + ':sha256', p.is_file() and sha(p) == f['sha256'] and p.stat().st_size == f['bytes'])
            extra = {}
            if f['role'] == 'main_pdf':
                extra['strong_pdf_identity'] = pdf_identity(p.read_bytes(), r)
            if f['role'] == 'main_xml':
                x = ET.parse(p).getroot()
                doi = next((''.join(a.itertext()).strip().lower() for a in x.findall('.//article-meta/article-id') if a.get('pub-id-type')=='doi'), None)
                check(f['path'] + ':exact_article_doi', doi == r['doi'])
            if p.suffix.lower() == '.zip':
                with zipfile.ZipFile(p) as z:
                    check(f['path'] + ':zip_crc', z.testzip() is None)
                    check(f['path'] + ':zip_paths', all(not PurePosixPath(a.filename).is_absolute() and '..' not in PurePosixPath(a.filename.replace('\\','/')).parts for a in z.infolist()))
            audit_files.append({'supply_id':r['supply_id'], 'doi':r['doi'], **f, **extra})
        names = {Path(f['path']).name.lower() for f in r['files']}
        declared_missing = set(r.get('declared_supplement_filenames', [])) - names
        check(r['supply_id'] + ':SI_not_claimed_complete_with_missing_names', not r['SI_obtained'] or not declared_missing)
        for pstr in r.get('existing_main_paths', []) + r.get('existing_SI_paths', []):
            p = Path(pstr)
            check(r['supply_id'] + ':historical_path_exists', p.is_file())
        r['missing_main'] = not r['main_complete']
        r['missing_declared_SI'] = r['SI_declared'] and not r['SI_obtained']
        r['SI_existence_unknown'] = not r['SI_declared'] and not r['SI_obtained']
        r['manual_download_recommended'] = r['final_scope'] not in ['background_only','correction_only'] and (r['missing_main'] or r['missing_declared_SI'])
        reviews.append({k:r.get(k) for k in ['supply_id','doi','title','year','cohort','final_scope','scope_reason','corrects_doi','metadata_identity','training_eligible','admission_status']})

    # Deterministic retrieval priorities: known 3E evidence gaps and exact
    # abstract 3E hints first. No ranking by reported high performance.
    old3e = {128,129,130,131,132,134,140,141}
    for r in rows:
        n = int(r['supply_id'].split('_')[1])
        rank = r.get('screen_score',0) or 0
        if r['cohort'] == 'historical_gap':
            rank = 30 if n in old3e else 14
        if r['manual_download_recommended'] and r['final_scope'] == 'separate_system_candidate':
            rank -= 35
        if n == 133:
            rank = -45
        r['download_rank'] = rank
    tasks = sorted([r for r in rows if r['manual_download_recommended']], key=lambda r:(-r['download_rank'], -(r.get('year') or 0), r['doi']))
    first = tasks[:30]
    first_ids = {r['supply_id'] for r in first}
    table = []
    main_map = {'existing_or_new_complete_fulltext':'已有可用全文','xml_obtained_figures_incomplete':'已有XML但原图不全','main_not_obtained':'正文未取得'}
    si_map = {'obtained':'已取得SI','declared_but_not_obtained':'已声明SI未取得','declaration_not_confirmed':'是否提供SI尚未确认'}
    for r in tasks:
        components = ['正文PDF'] if r['missing_main'] else []
        if r['missing_declared_SI']:
            components.append('已声明SI')
        r['priority'] = 'P1：先下载这30篇' if r['supply_id'] in first_ids else 'P3：旁系/历史背景' if r['final_scope']=='separate_system_candidate' or r['year'] and r['year']<2023 else 'P2：继续补齐'
        needed = ' + '.join(components)
        if r['missing_main'] and r['SI_obtained']:
            needed += '（SI已取得，不用重复下载）'
        elif r['missing_main'] and r['SI_existence_unknown']:
            needed += '；顺手核对SI是否存在'
        r['needed_component'] = needed
        if int(r['supply_id'].split('_')[1]) in old3e:
            reason = '旧三电极证据任务，优先补全现有记录的来源组件'
        elif r.get('three_electrode_abstract_mention'):
            reason = '摘要有3E线索；循环测试配置仍须全文确认'
        elif r['final_scope']=='separate_system_candidate':
            reason = r['scope_reason']
        elif r['cohort']=='historical_gap':
            reason = '历史缺件；保留原有双电极/其它用途分组'
        else:
            reason = '扩大生物质碳前驱体与工况覆盖；待全文核实'
        errors = list(dict.fromkeys(a.get('reason','') for a in r['attempts'] if a.get('reason')))
        failures = ' | '.join(errors[-3:])[:700] or '公开路径未取得可核验正文/SI；不表示DOI无效'
        table.append({'编号':r['supply_id'],'优先级':r['priority'],'DOI':r['doi'],'年份':r['year'],'题名':r['title'],'需要下载':needed,'正文状态':main_map[r['main_status']],'SI状态':si_map[r['SI_status']],'体系与配置提示':r['scope_reason'],'排序理由':reason,'自动获取结果':failures,'DOI链接':'https://doi.org/'+r['doi'],'建议文件名':r['supply_id']+'__'+r['doi'].replace('/','_')+'__main.pdf 或 __SI原文件名','用户完成情况':''})
    csvwrite('下载任务单.csv', table, list(table[0]))
    doiwrite('先下载这30篇_DOI.txt', first)
    doiwrite('待下载_全部DOI.txt', tasks)
    doiwrite('缺正文_DOI.txt', [r for r in tasks if r['missing_main']])
    doiwrite('缺已声明SI_DOI.txt', [r for r in tasks if r['missing_declared_SI']])
    eligible = [r for r in rows if r['final_scope'] not in ['background_only','correction_only']]
    optional_pdf = [r for r in eligible if r['main_complete'] and not r['main_pdf_obtained']]
    optional_si = [r for r in eligible if r['main_complete'] and r['SI_existence_unknown']]
    doiwrite('已有全文_可选出版社PDF_DOI.txt', optional_pdf)
    doiwrite('SI待核实_不等于缺件_DOI.txt', optional_si)
    for name, seq in [('背景与勘误_暂不优先下载.md',[r for r in rows if r['final_scope'] in ['background_only','correction_only']]),('已取得全文_阅读索引.md',[r for r in rows if r['main_complete']])]:
        lines=['# '+name.removesuffix('.md'),'','本表不表示训练准入。原始获取文件全部保留，分类只影响本次下载优先级。','', '| 编号 | DOI | 题名 | 说明 |','|---|---|---|---|']
        for r in seq:
            paths=[f['path'] for f in r['files'] if f['role'] in ['main_pdf','main_xml']] or r.get('existing_main_paths',[])
            link=''
            if paths:
                p=Path(paths[0]);p=p if p.is_absolute() else ROOT/p
                import os
                relative=Path(os.path.relpath(p,OUT)).as_posix()
                link=' [全文](<'+relative+'>)'
            lines.append('| '+r['supply_id']+' | ['+r['doi']+'](https://doi.org/'+r['doi']+') | '+r['title'].replace('|','/')+' | '+r['scope_reason']+link+' |')
        (OUT/name).write_text('\n'.join(lines)+'\n',encoding='utf-8')
    md=['# 本轮下载任务单','','按顺序下载。P1共30项，含“只缺SI”的项目；请看组件列，避免重复下载正文。P2继续补齐，P3为旁系/历史背景。','', '摘要提及三电极只用于检索排序，不能证明循环也用三电极。“SI未确认”不等于已确认缺SI。','', '| 顺序 | 编号 | 优先级 | DOI | 年份 | 题名 | 需要下载 |','|---|---|---|---|---|---|---|']
    for i,(r,t) in enumerate(zip(tasks,table),1):
        md.append(f"| {i} | {r['supply_id']} | {r['priority']} | [{r['doi']}](https://doi.org/{r['doi']}) | {r['year']} | {r['title'].replace('|','/')} | {r['needed_component']} |")
    (OUT/'下载任务单.md').write_text('\n'.join(md)+'\n',encoding='utf-8')
    dump(OUT/'scope_review.json', reviews)
    dump(OUT/'master_index.json', rows)
    dump(OUT/'已获取资料索引.json', audit_files)
    csvwrite('已获取资料索引.csv', audit_files, ['supply_id','doi','role','path','sha256','bytes','source_url','identity_basis'])
    new = [r for r in rows if r['cohort']=='new_target']
    counts = {
        'targets':len(rows),'new_targets':len(new),'historical_component_targets':22,'existing_candidate_SI_checks':2,
        'discovery_screened_candidates':248,'known_baseline_DOIs':len(baseline),
        'new_target_scopes':dict(collections.Counter(r['final_scope'] for r in new)),
        'new_target_fulltexts':sum(r['main_complete'] for r in new),
        'new_target_fulltexts_by_scope':dict(collections.Counter(r['final_scope'] for r in new if r['main_complete'])),
        'new_target_SI_sources':sum(r['SI_obtained'] for r in new),
        'all_target_SI_sources':sum(r['SI_obtained'] for r in rows),
        'all_target_complete_fulltext':sum(r['main_complete'] for r in rows),
        'historical_SI_recovered':sum(r['cohort']=='historical_gap' and 'SI' in r.get('requested_components',[]) and r['SI_obtained'] for r in rows),
        'manual_download_DOIs':len(tasks),'manual_main_DOIs':sum(r['missing_main'] for r in tasks),
        'manual_declared_SI_DOIs':sum(r['missing_declared_SI'] for r in tasks),
        'manual_priority_counts':dict(collections.Counter(r['priority'] for r in tasks)),
        'optional_publisher_PDF_DOIs':len(optional_pdf),'optional_SI_existence_checks':len(optional_si),
        'newly_saved_files':len(audit_files),'saved_payload_bytes':sum(f['bytes'] for f in audit_files),
        'newly_admitted_records':0,'research_fits':0,
    }
    dump(OUT/'summary.json',counts)
    check('parent_db_hash_unchanged',sha(ROOT/'循环稳定性数据库_v0.7_数据补充_20261018/cycling_v0_7.sqlite')==DB_HASH)
    parent=verify_parent()
    check('parent_science_and_protected_sources_pass',parent['all_checks_passed'])
    check('no_auto_admission',all(r['training_eligible'] is False for r in rows))
    check('no_background_or_correction_in_download_tasks',all(r['final_scope'] not in ['background_only','correction_only'] for r in tasks))
    check('manual_components_exact',all(r['missing_main'] or r['missing_declared_SI'] for r in tasks))
    check('six_remaining_known_SI',counts['manual_declared_SI_DOIs']==6)
    check('histories_exact_metadata_verified',len(historical)==22 and all(x['verified'] for x in historical.values()))
    check('correction_98_not_original_known',CORRECTIONS[98]['original_doi'] not in baseline)
    for name,expected in [('先下载这30篇_DOI.txt',30),('待下载_全部DOI.txt',len(tasks)),('缺正文_DOI.txt',counts['manual_main_DOIs']),('缺已声明SI_DOI.txt',6)]:
        lines=(OUT/name).read_text(encoding='utf-8').splitlines()
        check(name+':unique_count',len(lines)==len(set(lines))==expected)
    report={'all_checks_passed':True,'counts':counts,'current_v07_sha256':DB_HASH,'current_3e_records':21,'current_3e_source_groups':13,'parent_new_checks':parent['new_check_count'],'parent_earlier_checks':parent['parent_check_count'],'parent_protected_files':parent['parent_protected_file_count'],'checks':checks,'limitations':['全文已取得不等于所有SI已提供；SI未声明不等于缺件','实际循环配置、材料归属、标签和输入需要逐记录审查','本轮未改变当前数据库、未新增训练准入、未拟合模型']}
    dump(OUT/'最终核验.json',report)
    write_readme(counts)
    return counts


def write_readme(c):
    scopes=c['new_target_scopes'];full=c['new_target_fulltexts_by_scope']
    text=f'''# 本轮文献扩充与下载交接（2026-10-18）

已完成144项获取尝试：120个新目标、22个历史缺件任务、2个既有候选SI核对。检索以2023—2026年生物质碳超级电容器为主，优先寻找三电极线索；另保留一项2016年循环稳定性背景缺件。检索截至2026-10-18，不宣称穷尽全部文献。

## 你现在下载哪些

1. [先下载这30篇：纯DOI](先下载这30篇_DOI.txt)；下载前看[组件任务单](下载任务单.md)，其中有只需SI的任务。
2. [全部待下载：{c['manual_download_DOIs']}个DOI](待下载_全部DOI.txt)，分为[缺正文{c['manual_main_DOIs']}项](缺正文_DOI.txt)与[已声明但未取得SI的6项](缺已声明SI_DOI.txt)。每个DOI只出现一次；体系与优先级见[Excel可打开的CSV](下载任务单.csv)。
3. 请将新文件保存在本项目的新文件夹，例如`用户补充资料_第二轮_20261018`；建议命名`SUP_编号__DOI中斜杠改下划线__main.pdf`和`__SI原文件名`。SI的PDF、Word、Excel或ZIP请保留原件。这里只给保存建议，没有自动移动文件或创建归档。

只有正文没取得时才列入缺正文；正文已经是XML加完整原图的无需优先重复下载出版社PDF。待下载的“正文PDF；顺手核对SI是否存在”表示SI存在性未知，不能写成已缺SI。自动失败常见为403、429、无可验证公开PDF或TLS/网络错误，不代表DOI无效。

## 本轮实际拿到什么

| 口径 | 数量与含义 |
|---|---|
| 初筛发现 | 248个新元数据候选；未全部下载，也未全部确认为同体系 |
| 本轮新目标范围复核 | 普通碳候选{scopes.get('priority_carbon_candidate',0)}；旁系待分组{scopes.get('separate_system_candidate',0)}；背景{scopes.get('background_only',0)}；勘误{scopes.get('correction_only',0)} |
| 新目标可用全文 | {c['new_target_fulltexts']}项：普通碳候选{full.get('priority_carbon_candidate',0)}、旁系{full.get('separate_system_candidate',0)}、背景{full.get('background_only',0)}、勘误{full.get('correction_only',0)}；不能全称新增同体系研究 |
| 新目标SI | {c['new_target_SI_sources']}个来源取得SI，含只取得SI而未取得正文的来源；不能与正文数相加当论文数 |
| 全部任务SI | {c['all_target_SI_sources']}个来源；其中历史9项已声明SI缺件补回3项、仍缺6项，另补回一篇缺正文来源的SI和2个既有候选SI |
| 本地保存 | {c['newly_saved_files']}个文件、约{c['saved_payload_bytes']/1024**2:.1f} MiB；原包与解包文件并存，大小非独立数据量 |
| 本轮新增准入 | 0；当前v0.7三电极仍21条/13来源组，真实拟合0 |

全文、原图、SI、来源URL及SHA256见[逐文件索引](已获取资料索引.csv)、[可读全文入口](已取得全文_阅读索引.md)。32项新目标全文不表示32篇新的可训练研究；其中有勘误和不匹配背景。

## 仍需补齐的边界

- 新目标尚有正文缺口；历史13项缺正文本轮仍未取得，已经并入任务单。六项已确认SI缺口优先单独补齐。
- [可选出版社PDF清单](已有全文_可选出版社PDF_DOI.txt)有{c['optional_publisher_PDF_DOIs']}项，已有可用XML和原图，不是紧急正文缺件。
- [SI存在性待核实清单](SI待核实_不等于缺件_DOI.txt)有{c['optional_SI_existence_checks']}项，已有全文且未确认是否发布SI；没有伪装成缺件或完整。
- [背景与勘误](背景与勘误_暂不优先下载.md)单列，避免浪费下载时间。保留所有原始材料，不删除无用文献。
- 10.1021/acssusresmgt.5c00386修正原文10.1021/acssusresmgt.4c00258的SEM/XPS和元素组成；原文不在本次已知DOI基线。今后若引入原文，必须同时读取勘误并保留修正前后值。本轮不把勘误计为独立研究。
- 10.3390/molecules30030521仅调整10.3390/molecules30010089的通讯作者顺序，未更正实验数据；不因此更改现有科学记录。

候选是否有三电极GCD循环、循环电流、电解液、给定圈数保持率、BET与材料输入，要在下载后逐测试核实。三电极表征不等于三电极循环；凝胶前驱体也不等于凝胶电解液。下载、Git同步、候选完整性与训练准入是分开的状态。

## 核验与复现

[最终核验](最终核验.json)检查目标DOI去重、文件哈希、XML文章DOI、PDF首页DOI/完整题名、ZIP CRC与路径、声明SI文件、旧源文件与v0.7数据保护。当前数据库SHA256为`{DB_HASH}`，数据入口未变。没有启动真实训练、上传到其它远程或修改共享运行时。

本批脚本依次为`tools/collect_literature_supply_20261018.py`、`tools/acquire_literature_supply_20261018.py`、`tools/complete_literature_supply_20261018.py`和`tools/finalize_literature_supply_20261018.py`。前三者含获取或恢复操作，不能为补齐清单直接重跑。原始获取记录在`records/`，最终范围与人工下载决策在`master_index.json`和`scope_review.json`；原始决定保留，不回写旧数据库。
'''
    (OUT/'README.md').write_text(text,encoding='utf-8')


def canonical_history():
    cache = OUT / 'metadata' / 'historical_exact_crossref.json'
    if cache.exists():
        return json.loads(cache.read_text(encoding='utf-8'))
    records = [json.loads(p.read_text(encoding='utf-8')) for p in sorted((OUT / 'records').glob('SUP_???.json'))]
    def one(r):
        try:
            item = crossref(r['doi'])
            return {'supply_id': r['supply_id'], 'verified': True, **item}
        except Exception as exc:
            return {'supply_id': r['supply_id'], 'doi': r['doi'], 'verified': False, 'reason': str(exc)}
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        result = list(pool.map(one, [r for r in records if r['cohort'] == 'historical_gap']))
    dump(cache, result)
    return result


if __name__ == '__main__':
    import sys
    if '--metadata' in sys.argv:
        result = canonical_history()
        print(json.dumps({'exact_historical': len(result), 'verified': sum(r['verified'] for r in result)}))
    else:
        print(json.dumps(finalize(),ensure_ascii=False))
