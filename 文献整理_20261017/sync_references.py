from pathlib import Path
import csv,hashlib,json,re,shutil,sys
sys.stdout.reconfigure(encoding='utf-8')
OUT=Path(__file__).resolve().parent;ROOT=OUT.parent
CAT=ROOT/'文献分类与审核准备_20261016';AUDIT=ROOT/'训练适用性审核_20261016'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
plan=read(OUT/'整理计划.json')
mapping=plan['old_to_new_paths']
variants={}
for old,new in mapping.items():
    variants[old]=new;variants[old.replace('\\','/')]=new.replace('\\','/')
pairs=sorted(variants.items(),key=lambda x:len(x[0]),reverse=True)
def translate(value):
    if isinstance(value,str):
        for old,new in pairs:value=value.replace(old,new)
        return value
    if isinstance(value,list):return [translate(x) for x in value]
    if isinstance(value,dict):return {k:translate(v) for k,v in value.items()}
    return value
def backup(p):
    target=OUT/'更新前项目快照'/p.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True)
    assert not target.exists(),target
    shutil.copy2(p,target)
def update_json(p):
    backup(p);save(p,translate(read(p)))

assert (OUT/'去重完成.json').exists()
changed=[]
# Current state files are updated. Historical transaction manifests remain immutable.
jsons=[
 CAT/'主清单分类.json',CAT/'额外资料分类.json',CAT/'工作簿数据.json',
 CAT/'下载归档最终台账_分类准备后.json',CAT/'分类汇总.json',
 AUDIT/'逐份训练用途审核.json',AUDIT/'正文证据定位.json',
 AUDIT/'R107_SI_6材料30测试_报告值样例.json']
for p in jsons:update_json(p);changed.append(str(p))
paper_moves={x['id']:x for x in plan['actions'] if x['kind']=='paper'}
rows=read(AUDIT/'逐份训练用途审核.json')
for row in rows:
    row['in_active_library']=row['id']!='SRC113'
    row['storage_status']='已移出有效文献库，保留归档追溯' if row['id']=='SRC113' else '唯一PDF已物理分类'
save(AUDIT/'逐份训练用途审核.json',rows)
for p in [CAT/'主清单分类.json',CAT/'额外资料分类.json']:
    contents=read(p)
    for row in contents:
        if row.get('local_pdf'):row['local_pdf_copies']=[row['local_pdf']]
        if row.get('id')=='SRC113':row['storage_status']='2022年版本，已移出当前文献库'
    save(p,contents)
workbook=read(CAT/'工作簿数据.json')
workbook['main']=read(CAT/'主清单分类.json');workbook['extras']=read(CAT/'额外资料分类.json')
save(CAT/'工作簿数据.json',workbook)
inv_path=CAT/'本地与压缩包文件盘点.json';backup(inv_path)
inv=read(inv_path)
for rec in inv['records']:
    rec['sources_before_physical_organization']=rec['sources']
    translated=translate(rec)
    rec['local_pdf']=translated['local_pdf']
    # Collapse active file paths while retaining archive-member provenance.
    sources=[];seen=set()
    for src in translated['sources']:
        key=(src['kind'],src.get('path'),src.get('archive'),src.get('entry'))
        if key in seen:continue
        seen.add(key);sources.append(src)
    rec['sources']=sources
    rec['in_active_library']=Path(rec['local_pdf']).resolve().is_relative_to(Path(r'D:\文献').resolve())
inv.update({'library_pdf_files':0,'paper_pdf_files':121,'library_all_pdf_files':124,
            'unique_pdf_contents_in_active_library':121,'archived_pre2023_contents':1,
            'root_pdf_files':0,'duplicate_pdf_copies_in_library':0,'archive_current_path':str(OUT/'原始压缩包/1.zip'),
            'counting_note':'unique_pdf_contents=122为已审核历史总内容，含已移出库的1个旧版本；当前论文121、补充PDF3、Word补充1，无重复PDF。'})
save(inv_path,inv);changed.append(str(inv_path))
dups=CAT/'重复与多位置文件.json';backup(dups)
save(dups,{'current_duplicate_pdf_groups':[], 'duplicate_copies_recycled':21,
           'historical_duplicate_manifest':str(OUT/'整理计划.json'),
           'current_unique_locations':str(OUT/'当前唯一文献位置.json')})
for p in [CAT/'主120篇_分类清单.csv',CAT/'额外65份_分类清单.csv']:
    backup(p)
    with p.open(encoding='utf-8-sig',newline='') as f:table=list(csv.DictReader(f))
    translated=[translate(x) for x in table]
    with p.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(table[0]));w.writeheader();w.writerows(translated)
    changed.append(str(p))
markdown=[AUDIT/'训练用途审核报告.md',CAT/'分类与准备总览.md',ROOT/'当前文献状态.md',ROOT/'READ_ME_FIRST_FOR_NEXT_CHAT.md']
markdown+=list((AUDIT/'逐份证据卡').glob('*.md'))
markdown+=list((CAT/'分类阅读目录').glob('*/阅读索引.md'))
for p in markdown:
    backup(p);text=translate(p.read_text(encoding='utf-8'))
    p.write_text(text,encoding='utf-8');changed.append(str(p))

latest='''## 文献文件夹已物理整理（2026-10-17，最新）

D:/文献当前只有一套正文：121篇论文PDF、3份PDF补充和1份Word补充。21个内容完全相同的PDF副本已经核验后移入回收站。1份2022年预印本移到项目归档；原始1.zip也移出文献库单独归档。没有更改PDF正文内容。

按训练用途建立5类文件夹，数量依次39、17、14、24、27；每篇一个“编号_年份_题名”文件夹，内有正文.pdf、对应补充材料及使用说明.md。D:/文献/打开文献目录.html可搜索、筛选并打开原文。全部当前目录递归PDF为124个，按SHA256无任何重复。审核总表仍是122份历史已审内容（含1份移出库的旧版本），不是当前文件夹论文数。

当前唯一文献位置以文献整理_20261017/当前唯一文献位置.json为准。训练用途审核JSON、证据卡、报告、分类索引、当前台账和两个工作簿的文献路径已同步。较早补包/解压日志是历史事务记录，路径不再代表当前存放位置，不可重跑历史一次性脚本来恢复旧文件。

回退：文献整理_20261017/整理前文件备份.zip已逐成员哈希验证（147个文件），原ZIP另存在原始压缩包/1.zip；整理计划.json保存每个原位置、目标位置、SHA256和重复保留件。原件未永久删除，重复件在回收站。年份排除_不在文献库/SRC113_2022_椰壳碳预印本.pdf是归档副本，不是有效来源。

'''
readme=ROOT/'READ_ME_FIRST_FOR_NEXT_CHAT.md'
text=readme.read_text(encoding='utf-8').replace('## 最新工作：检查全部已有文献的训练用途',latest+'## 最新工作：检查全部已有文献的训练用途')
readme.write_text(text,encoding='utf-8')
pointer=ROOT/'当前文献状态.md'
text=pointer.read_text(encoding='utf-8').replace('# 当前文献状态','# 当前文献状态\n\n'+latest,1)
pointer.write_text(text,encoding='utf-8')
note='''\n## 当前物理目录（2026-10-17）

文献库已经实际去重并按训练用途整理：当前121篇正文、4份补充材料。2022年版本已移出到项目归档，因此本报告122份是已审历史范围，包含那1份归档件。21个重复PDF副本已移入回收站。

[打开可搜索文献目录](<D:/文献/打开文献目录.html>) · [整理后位置清单](../文献整理_20261017/当前唯一文献位置.json)

'''
for p,anchor in [(AUDIT/'训练用途审核报告.md','## 结论'),(CAT/'分类与准备总览.md','## 压缩包已完整解压')]:
    text=p.read_text(encoding='utf-8');text=text.replace(anchor,note+anchor,1);p.write_text(text,encoding='utf-8')
summary=read(AUDIT/'审核汇总.json');summary.update({'active_library_papers_after_organization':121,
    'archived_year_excluded_papers':1,'current_library_duplicate_pdf_copies':0})
backup(AUDIT/'审核汇总.json');save(AUDIT/'审核汇总.json',summary)
for p in [CAT/'文献分类总表.xlsx',AUDIT/'训练用途审核总表.xlsx']:backup(p)
save(OUT/'已更新项目文件.json',{'files':changed,'xlsx_pending':['文献分类总表.xlsx','训练用途审核总表.xlsx']})
print('Updated',len(changed),'current JSON/CSV/Markdown references; workbook update pending')
