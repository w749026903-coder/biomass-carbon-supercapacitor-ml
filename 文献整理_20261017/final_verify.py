from pathlib import Path
import collections,hashlib,html,json,re,sys,zipfile,xml.etree.ElementTree as ET
from urllib.parse import unquote
sys.stdout.reconfigure(encoding='utf-8')
OUT=Path(__file__).resolve().parent;ROOT=OUT.parent;LIB=Path(r'D:\文献')
CAT=ROOT/'文献分类与审核准备_20261016';AUDIT=ROOT/'训练适用性审核_20261016'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
plan=read(OUT/'整理计划.json');locations=read(OUT/'当前唯一文献位置.json')
rows=read(AUDIT/'逐份训练用途审核.json')
for a in plan['actions']:
    assert Path(a['target']).is_file() and sha(Path(a['target']))==a['sha256'],a
    assert not Path(a['source']).exists(),a['source']
for a in plan['duplicate_copies_to_recycle']:assert not Path(a['path']).exists()
assert len(locations)==122
active=[x for x in locations if x['in_active_library']]
assert len(active)==121
allpdf=sorted(LIB.rglob('*.pdf'))
hashes=collections.Counter(sha(p) for p in allpdf)
assert len(allpdf)==len(hashes)==124
assert not list(LIB.glob('*.pdf')) and not list(LIB.rglob('*.zip'))
assert len(list(LIB.rglob('*.docx')))==1
assert len(list(LIB.rglob('正文.pdf')))==121
expected={'01_优先提取实验数据':39,'02_分体系或限定字段':17,'03_待核与冻结':14,'04_方法与背景':24,'05_范围外资料':27}
actual={p.name:len(list(p.rglob('正文.pdf'))) for p in LIB.iterdir() if p.is_dir()}
assert actual==expected,(actual,expected)
assert sum(len(x['supplements']) for x in active)==4
for x in active:
    p=Path(x['local_pdf'])
    assert p.resolve().is_relative_to(LIB.resolve())
    assert (p.parent/'使用说明.md').exists()
    for si in x['supplements']:assert Path(si).parent==p.parent and Path(si).is_file()
for row in rows:assert sha(Path(row['local_pdf']))==row['sha256']
for p in [CAT/'主清单分类.json',CAT/'额外资料分类.json',CAT/'下载归档最终台账_分类准备后.json']:
    for x in read(p):
        if x.get('local_pdf'):assert Path(x['local_pdf']).is_file()
inv=read(CAT/'本地与压缩包文件盘点.json')
assert len(inv['records'])==122
assert sum(x['in_active_library'] for x in inv['records'])==121
for rec in inv['records']:
    local=[s for s in rec['sources'] if s['kind']=='local_pdf']
    assert len(local)==1 and sha(Path(local[0]['path']))==rec['sha256']

# Confirm all generated local navigation links, including URL-encoded special characters.
markup=(LIB/'打开文献目录.html').read_text(encoding='utf-8')
hrefs=re.findall('href="([^"]+)"',markup)
assert len(hrefs)==121
for href in hrefs:assert (LIB/unquote(html.unescape(href))).is_file(),href
assert collections.Counter(re.findall(r'<tr data-cat="([A-E])">',markup))=={'A':39,'B':17,'C':14,'D':24,'E':27}
current_markdown=list((AUDIT/'逐份证据卡').glob('*.md'))+[AUDIT/'训练用途审核报告.md']
current_markdown+=list((CAT/'分类阅读目录').glob('*/阅读索引.md'))
for p in current_markdown:
    for target in re.findall(r'\]\(<([^>]+)>\)',p.read_text(encoding='utf-8')):
        assert Path(target).exists(),(p,target)

ns={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
def unpack(p):
    result=[]
    with zipfile.ZipFile(p) as z:
        strings=[]
        if 'xl/sharedStrings.xml' in z.namelist():strings=[''.join(x.itertext()) for x in ET.fromstring(z.read('xl/sharedStrings.xml'))]
        names=[x for x in z.namelist() if re.fullmatch(r'xl/worksheets/sheet\d+.xml',x)]
        for name in sorted(names):
            tree=ET.fromstring(z.read(name));cells={}
            for c in tree.findall('.//m:sheetData/m:row/m:c',ns):
                assert c.get('t')!='e'
                v=c.find('m:v',ns);f=c.find('m:f',ns)
                value=v.text if v is not None else ''
                if c.get('t')=='s':value=strings[int(value)] if value else ''
                elif c.get('t')=='inlineStr':value=''.join(c.find('m:is',ns).itertext())
                if value or f is not None:cells[c.get('r')]=(value,f.text if f is not None else None)
            result.append({'cells':cells,'pane':tree.find('.//m:pane',ns).attrib,
                           'table_count':len(tree.findall('.//m:tablePart',ns))})
    return result
workbook_changes=[]
for p in [CAT/'文献分类总表.xlsx',AUDIT/'训练用途审核总表.xlsx']:
    b=unpack(OUT/'更新前项目快照'/p.relative_to(ROOT));a=unpack(p)
    assert len(a)==len(b)
    changed=[]
    for index,(before,after) in enumerate(zip(b,a),1):
        assert before['pane']==after['pane'] and before['table_count']==after['table_count']
        for cell in before['cells'].keys()|after['cells'].keys():
            previous=before['cells'].get(cell);current=after['cells'].get(cell)
            if previous!=current:
                changed.append((index,cell))
                if len(a)==3:assert (index in [1,2] and cell.startswith('N')) or (index==2 and cell=='A6'),(p,index,cell)
                else:assert (cell.startswith('I') and int(cell[1:])>=10) or cell in ['A8','J131'],(p,cell)
            if current and isinstance(current[0],str) and current[0].startswith('D:\\'):
                assert Path(current[0]).exists(),current[0]
    assert len(changed)==(123 if len(a)==3 else 124)
    workbook_changes.append({'file':str(p),'changed_cells':len(changed),'only_paths_and_required_notes_changed':True})

stats=read(CAT/'分类汇总.json')
stats.setdefault('before_physical_organization', {k:stats.get(k) for k in ['root_pdf_files','paper_pdf_files','duplicate_extra_occurrences','library_all_pdf_files']})
stats.update({'root_pdf_files':0,'paper_pdf_files':121,'library_all_pdf_files':124,'supplement_pdf_files':3,
              'duplicate_extra_occurrences':0,'unique_pdf_contents_in_active_library':121,
              'archived_year_excluded_contents':1,'physical_organization_date':'2026-10-17',
              'counting_note':'历史已审内容122含1个已移出库2022版本；当前文献库121正文PDF+3补充PDF+1Word，无重复。'})
save(CAT/'分类汇总.json',stats)
book=read(CAT/'工作簿数据.json');book['summary']=stats;save(CAT/'工作簿数据.json',book)
for p in [CAT/'最终核验.json',AUDIT/'最终一致性核验.json']:
    contents=read(p);contents['physical_organization_20261017']={'active_library_papers':121,'supplements':4,'duplicate_pdf_groups':0,
        'all_122_audited_contents_still_accessible':True,'current_paths_verified':True};save(p,contents)
result={'date':'2026-10-17','library':str(LIB),'paper_pdfs':121,'pdf_supplements':3,'docx_supplements':1,
        'all_pdf_files':124,'unique_pdf_hashes':124,'duplicate_pdf_groups':0,'category_counts':actual,
        'recycled_duplicate_copies':21,'archived_pre2023_papers':1,'original_zip_moved_outside_library':True,
        'all_retained_file_hashes_unchanged':True,'all_121_html_links_exist':True,'all_current_markdown_links_exist':True,
        'all_current_json_pdf_paths_exist':True,'workbook_changes':workbook_changes,
        'backup_verified_member_count':read(OUT/'备份核验.json')['verified_members']}
save(OUT/'整理后最终核验.json',result)
log=read(OUT/'已更新项目文件.json');log['xlsx_pending']=[];save(OUT/'已更新项目文件.json',log)
(OUT/'整理结果.md').write_text('''# 文献整理结果

完成：2026-10-17。

D:/文献已按训练用途实际分成五类：优先提取39篇，分体系或限定字段17篇，待核14篇，方法背景24篇，范围外27篇。每篇独立文件夹存放正文、对应补充材料与使用说明。

当前共121篇论文PDF，另有3份PDF补充和1份Word补充；全部124个PDF的内容哈希均不同。21个完全重复副本已移入回收站。1份2022年预印本移出当前文献库，原始1.zip亦移到项目归档。

[打开可搜索文献目录](<D:/文献/打开文献目录.html>)

整理前147个文件已逐件校验后压缩备份，备份核验、每件移动日志和原/新位置映射均保存在本目录。PDF内容未更改。两份当前工作簿、分类索引、训练审核证据卡和台账已同步路径，核验链接及表格格式通过。

恢复原布局时，按整理计划.json查询原位置，使用整理前文件备份.zip中对应成员恢复；原始ZIP在原始压缩包/1.zip。不要未经核对覆盖当前文件。历史事务日志仍保留整理前路径，不用作当前打开入口。
''',encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))
