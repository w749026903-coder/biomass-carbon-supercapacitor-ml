from pathlib import Path
import collections, csv, hashlib, json, re, sys, zipfile, xml.etree.ElementTree as ET
sys.stdout.reconfigure(encoding='utf-8')
HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
CAT=ROOT/'文献分类与审核准备_20261016'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
result=read(HERE/'完整解压结果.json')
inv=read(CAT/'本地与压缩包文件盘点.json')
main=read(CAT/'主清单分类.json'); extras=read(CAT/'额外资料分类.json')
master=read(CAT/'下载归档最终台账_分类准备后.json')
stats=read(HERE/'统一计数与核验.json')
with zipfile.ZipFile(result['archive']) as z:
    members=[x for x in z.infolist() if not x.is_dir()]
    assert len(members)==len(result['entries'])==49
    assert {x.filename for x in members}=={x['entry'] for x in result['entries']}
    for row in result['entries']:
        assert sha(Path(row['target']))==row['sha256']==hashlib.sha256(z.read(row['entry'])).hexdigest()
assert sha(Path(result['archive']))==result['archive_sha256']
for row in result['paper_files_before']:
    assert sha(Path(row['path']))==row['sha256']
assert len(inv['records'])==122
for rec in inv['records']:
    assert rec.get('local_pdf') and sha(Path(rec['local_pdf']))==rec['sha256']
    for source in rec['sources']:
        if source['kind']=='local_pdf':assert sha(Path(source['path']))==rec['sha256']
for row in main+extras:
    if row.get('local_pdf'):assert sha(Path(row['local_pdf']))==row['sha256']
    assert row['eligible_for_database'] is False
assert len(main)==len(master)==120 and len(extras)==65
assert sum(bool(x.get('local_pdf')) for x in main)==57
assert sum(not x.get('local_pdf') for x in main)==63
assert all(x.get('local_pdf') for x in extras)
old_extras=read(HERE/'更新前快照/文献分类与审核准备_20261016/额外资料分类.json')
for before,after in zip(old_extras,extras):
    for key in before:
        if key not in ('local_pdf','fulltext_status'):assert before[key]==after[key],(after['id'],key)
for p in (CAT/'分类阅读目录').glob('*/阅读索引.md'):
    text=p.read_text(encoding='utf-8')
    assert '[1.zip]' not in text,p
    for target in re.findall(r'\]\(<([^>]+)>\)',text):
        assert Path(target).exists(),target
ns={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
def workbook_cells(p):
    sheets=[]
    with zipfile.ZipFile(p) as z:
        strings=[]
        if 'xl/sharedStrings.xml' in z.namelist():
            strings=[''.join(x.itertext()) for x in ET.fromstring(z.read('xl/sharedStrings.xml'))]
        for index in (1,2,3):
            tree=ET.fromstring(z.read(f'xl/worksheets/sheet{index}.xml'))
            cells={}
            for cell in tree.findall('.//m:sheetData/m:row/m:c',ns):
                v=cell.find('m:v',ns);f=cell.find('m:f',ns)
                typ=cell.get('t')
                value=v.text if v is not None else ''
                if typ=='s':value=strings[int(value)] if value else ''
                elif typ=='inlineStr':value=''.join(cell.find('m:is',ns).itertext())
                assert typ!='e',(p,index,cell.get('r'),value)
                if value or f is not None:cells[cell.get('r')]=(value, f.text if f is not None else None)
            sheets.append({'cells':cells,'pane':tree.find('.//m:pane',ns).attrib,
                           'tables':len(tree.findall('.//m:tablePart',ns)),
                           'conditional_formats':ET.tostring(tree.find('.//m:conditionalFormatting',ns)) if tree.find('.//m:conditionalFormatting',ns) is not None else None})
    return sheets
before=workbook_cells(HERE/'更新前快照/文献分类与审核准备_20261016/文献分类总表.xlsx')
after=workbook_cells(CAT/'文献分类总表.xlsx')
changed=[]
for index,(b,a) in enumerate(zip(before,after),1):
    assert b['pane']==a['pane'],('pane',index,b['pane'],a['pane'])
    assert b['tables']==a['tables'],('tables',index)
    for address in b['cells'].keys()|a['cells'].keys():
        if b['cells'].get(address)!=a['cells'].get(address):
            assert index==2 and (address=='D4' or re.fullmatch(r'[DN](?:[1-9]\d*)',address)),(index,address)
            changed.append({'sheet':index,'cell':address})
assert len(changed)==57,len(changed)
assert after[1]['cells']['D4'][0]=='0'
row_by_id={after[1]['cells'][f'A{i}'][0]:i for i in range(9,74)}
for row in extras:
    i=row_by_id[row['id']]
    assert after[1]['cells'][f'N{i}'][0]==row['local_pdf']
    assert after[1]['cells'][f'D{i}'][0]==row['fulltext_status']
for name,rows in [('主120篇_分类清单.csv',main),('额外65份_分类清单.csv',extras)]:
    with (CAT/name).open(encoding='utf-8-sig',newline='') as f:table=list(csv.DictReader(f))
    assert len(table)==len(rows)
    data={x['id']:x for x in rows}
    for x in table:assert x['本地PDF']==(data[x['编号']].get('local_pdf') or '')
checks={'all_49_members_extracted_and_SHA256_verified':True,
        'zip_unchanged':True,'original_94_pdfs_unchanged':True,
        'all_122_content_records_have_local_pdf':True,'all_6_reading_indexes_link_to_existing_pdfs':True,
        'main_120_57_fulltexts_63_missing_unchanged':True,'quality_and_year_flags_preserved':True,
        'workbook_changed_cells':len(changed),'workbook_only_authorized_cells_changed':True,
        'workbook_freeze_panes_tables_preserved':True,'workbook_formula_errors':0,
        'all_eligible_for_database_false':True,'counts':stats}
(HERE/'管理更新最终核验.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
prior=read(CAT/'最终核验.json')
prior['complete_zip_extraction_verification']=checks
(CAT/'最终核验.json').write_text(json.dumps(prior,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in checks.items() if k!='counts'},ensure_ascii=False,indent=2))
