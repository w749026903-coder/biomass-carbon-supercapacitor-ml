"""User-confirmed bounded copy/import. No moves, deletes, or original paper edits."""
import collections, copy, hashlib, html, io, json, pathlib, re, shutil, urllib.parse
from html.parser import HTMLParser
from pypdf import PdfReader

REVIEW=pathlib.Path(__file__).resolve().parent
SUP=REVIEW.parent
BASE=SUP.parent
LIB=pathlib.Path('D:/文献').resolve()
RUN=REVIEW/'已确认入库执行'
INDEX=BASE/'文献整理_20261017/当前唯一文献位置.json'
GUIDE=LIB/'打开文献目录.html'
LIBNOTE=LIB/'整理说明.md'
STATE=BASE/'当前文献状态.md'
ENTRY=BASE/'READ_ME_FIRST_FOR_NEXT_CHAT.md'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def write_json(p,obj):p.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
def within(p,parent):
 p=p.resolve();assert p.is_relative_to(parent),str(p);return p
def uri(p):return urllib.parse.quote(pathlib.Path(p).relative_to(LIB).as_posix())

assert not RUN.exists(),'One-time import already has a run directory; inspect before continuing.'
plan=read(REVIEW/'待确认逐文件入库清单.json')
cards=read(REVIEW/'文献级归档审核.json')
old=read(INDEX)
active=[x for x in old if x.get('in_active_library')]
assert len(plan)==17 and len(cards)==5 and len(active)==121
assert {c['proposed_paper_id'] for c in cards}=={'SRC123','SRC124','SRC125','SRC126','SRC127'}
for p in plan:
 src=within(pathlib.Path(p['source']),BASE);dest=within(pathlib.Path(p['target']),LIB)
 assert src.is_file() and sha(src)==p['sha256'] and not dest.exists(),str(dest)
for p in active:assert sha(pathlib.Path(p['local_pdf']))==p['sha256'],p['id']
before={str(p):sha(p) for p in LIB.rglob('*') if p.is_file()}
assert len(list(LIB.rglob('正文.pdf')))==121
RUN.mkdir()
backup=RUN/'更新前备份';backup.mkdir()
backups=[]
for i,p in enumerate([INDEX,GUIDE,LIBNOTE,STATE,ENTRY,REVIEW/'待确认逐文件入库清单.json']):
 dest=backup/f'{i+1:02d}_{p.name}';shutil.copy2(p,dest)
 assert sha(dest)==sha(p)
 backups.append({'original':str(p),'backup':str(dest),'sha256':sha(dest)})
write_json(RUN/'更新前文件备份清单.json',backups)
write_json(RUN/'入库前文献库文件哈希.json',before)
approved_hash=sha(REVIEW/'待确认逐文件入库清单.json')

# Finalize only the five newly authored usage notes to reflect confirmed status.
execution=copy.deepcopy(plan)
for p in execution:
 if pathlib.Path(p['source']).name=='使用说明.md':
  src=pathlib.Path(p['source']);dest=RUN/(p['paper_id']+'_使用说明.md')
  text=src.read_text(encoding='utf-8').replace('（原补充编号','（项目补充编号')
  text=text.replace('本文件为待确认的入库说明，目前原资料仍在项目补充目录。','本篇于2026-10-17经用户确认归档；项目补充目录保留来源副本。文献级归档不解除数据冻结，也不增加已准入训练记录。')
  dest.write_text(text,encoding='utf-8');p['approved_source']=p['source'];p['approved_source_sha256']=p['sha256'];p['source']=str(dest);p['sha256']=sha(dest)
write_json(RUN/'已确认逐文件执行清单.json',execution)
log=[]
for p in execution:
 src=pathlib.Path(p['source']);dest=within(pathlib.Path(p['target']),LIB)
 dest.parent.mkdir(parents=True,exist_ok=True)
 with src.open('rb') as inf,dest.open('xb') as outf:shutil.copyfileobj(inf,outf)
 assert sha(dest)==p['sha256']
 entry={**p,'status':'copied_and_hash_verified'};log.append(entry)
 with (RUN/'复制日志.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(entry,ensure_ascii=False)+'\n')

current=copy.deepcopy(old);by_id={x['id']:x for x in current}
paper_manifest=read(SUP/'第一批文献清单_核验后.json')
by_source={x['id']:x for x in paper_manifest}
for ident in ['R103','R106']:
 dest=next(x['target'] for x in execution if x['paper_id']==ident)
 assert dest not in by_id[ident]['supplements'];by_id[ident]['supplements'].append(dest)
newrows=[]
for c in cards:
 ident=c['proposed_paper_id'];source=by_source[c['source_id']]
 items=[p for p in execution if p['paper_id']==ident]
 main=next(pathlib.Path(p['target']) for p in items if pathlib.Path(p['target']).name in ['正文.pdf','正文.xml'])
 fmt='PDF' if main.suffix.lower()=='.pdf' else 'XML'
 supplements=[p['target'] for p in items if pathlib.Path(p['target']).name.startswith('补充材料__')]
 row=dict(id=ident,category=c['recommended_category'],title=c['title'],doi=c['doi'],year=source['year'],local_pdf=str(main) if fmt=='PDF' else None,local_fulltext=str(main),main_format=fmt,sha256=sha(main),sha256_kind='main_'+fmt,in_active_library=True,supplements=supplements,source_supplement_id=c['source_id'],eligible_for_database=False,archive_review_level=c['review_level'],restrictions=c['restrictions'])
 if fmt=='XML':row['local_text']=str(main.parent/'正文_文本.txt')
 current.append(row);newrows.append(row)
assert len([x for x in current if x.get('in_active_library')])==126
write_json(INDEX,current)
write_json(RUN/'新增文献归档审核增量.json',[{**c,'archive_recommendation':'archived_after_user_confirmation','copy_executed':True} for c in cards])
write_json(RUN/'补充编号与正式文献编号映射.json',{x['source_supplement_id']:x['id'] for x in newrows})

# Preserve the existing catalog UI and original rows; add only the confirmed entries and SI links.
guide=GUIDE.read_text(encoding='utf-8-sig')
tbody=re.search(r'<tbody>(.*?)</tbody>',guide,re.S);assert tbody
old_html_rows=re.findall(r'<tr data-cat="[A-E]">.*?</tr>',tbody.group(1),re.S);assert len(old_html_rows)==121
for ident in ['R103','R106']:
 dest=next(x['target'] for x in execution if x['paper_id']==ident)
 for i,row in enumerate(old_html_rows):
  if f'<td>{ident}</td>' in row:
   marker='</a></td><td>'
   assert marker in row
   old_html_rows[i]=row.replace(marker,f'</a><br><a href="{uri(dest)}">新增补充材料</a></td><td>',1)
labels={'A':'主要实验数据来源候选','B':'分体系或限定字段','C':'待核与冻结'}
new_html_rows=[]
for r in newrows:
 main=r.get('local_text') if r['main_format']=='XML' else r['local_pdf']
 links=f'<a href="{uri(main)}">{html.escape(r["title"])}</a>'
 if r['main_format']=='XML':links+=f'<br><a href="{uri(r["local_fulltext"])}">原始XML</a>（完整正文，暂无排版PDF）'
 for si in r['supplements']:links+=f'<br><a href="{uri(si)}">补充材料</a>'
 if not r['supplements']:links+='<br>补充材料待补'
 links+=f'<br><a href="https://doi.org/{r["doi"]}">DOI：{r["doi"]}</a>'
 new_html_rows.append(f'<tr data-cat="{r["category"]}"><td>{r["id"]}</td><td>{r["year"]}</td><td>{labels[r["category"]]}</td><td>{links}</td><td>{html.escape(r["restrictions"])}</td></tr>')
allrows=old_html_rows+new_html_rows
allrows.sort(key=lambda x:re.search(r'data-cat="([A-E])"',x).group(1))
guide=guide[:tbody.start(1)]+''.join(allrows)+guide[tbody.end(1):]
guide=guide.replace('121份不重复论文，4份补充材料。主要来源候选39，分体系或限定字段17，待核14，方法背景24，范围外27。','126篇文献：125篇PDF正文、1篇XML完整正文；10份补充材料（9份PDF、1份Word）。主要来源候选41，分体系或限定字段19，待核15，方法背景24，范围外27。')
guide=guide.replace('题名（点击打开PDF）','题名（点击打开正文）')
GUIDE.write_text(guide,encoding='utf-8')
LIBNOTE.write_text('''# 文献库使用说明

更新日期：2026-10-17。

当前126篇文献：125篇正文PDF，1篇完整原文XML（SRC124，另有可读TXT）。补充材料10份，其中9份PDF、1份Word。每篇独占一个按编号、年份和题名命名的文件夹，使用说明列出用途和限制。

01_优先提取实验数据：41篇。
02_分体系或限定字段：19篇。
03_待核与冻结：15篇。
04_方法与背景：24篇。
05_范围外资料：27篇。

打开“打开文献目录.html”搜索、筛选和打开正文。SRC124的正文题名链接打开TXT，并另列原始XML；不能把它的SI当成正文PDF。读取项目唯一位置索引时，应先检查main_format；XML文献的local_pdf为空，使用local_fulltext/local_text。

本次经用户确认新增SRC123–SRC127，R103和R106各补一份SI。项目内来源副本保留。文件按已核清单复制，原论文没有移动、覆盖或删除。N004现编号SRC125，仅在待核分类归档，数据资格继续冻结。含铜SRC126和凝胶SRC127单列体系。

此前21份相同副本回收、2022年预印本及原ZIP移出均为历史已完成操作，本次未重复执行。历史备份仍在项目“文献整理_20261017”。

本次入库备份、逐文件哈希、复制日志和审核增量在D:/机器学习-超级电容器/循环稳定性文献补充_20261017/文献入库审核/已确认入库执行。当前唯一位置为项目“文献整理_20261017/当前唯一文献位置.json”。历史审核报告及工作簿保留原阶段范围，新增5篇见本次审核增量，不能拿历史行数代替当前文献总数。

文献归档分类不等于训练数据准入；正式逐记录准入仍为0，未训练模型，旧冻结继续保留。
''',encoding='utf-8')

# Verify physical library, retained files, HTML destinations, and format-aware index.
class Links(HTMLParser):
 def __init__(self):super().__init__();self.links=[]
 def handle_starttag(self,tag,attrs):
  if tag=='a':
   u=dict(attrs).get('href')
   if u:self.links.append(u)
parser=Links();parser.feed(guide)
local_links=[u for u in parser.links if not urllib.parse.urlsplit(u).scheme]
assert all((LIB/urllib.parse.unquote(u)).is_file() for u in local_links)
pdfs=list(LIB.rglob('*.pdf'));hashes=[sha(p) for p in pdfs]
assert len(pdfs)==134 and len(set(hashes))==134
assert len(list(LIB.rglob('正文.pdf')))==125
assert len(list(LIB.rglob('正文.xml')))==1
cats=collections.Counter(x['category'] for x in current if x.get('in_active_library'))
assert dict(cats)=={'A':41,'B':19,'C':15,'D':24,'E':27}
changed_originals=[p for p,h in before.items() if sha(pathlib.Path(p))!=h]
assert set(changed_originals)=={str(GUIDE),str(LIBNOTE)},changed_originals
for r in current:
 if not r.get('in_active_library'):continue
 main=pathlib.Path(r.get('local_fulltext') or r['local_pdf']);assert main.is_file() and sha(main)==r['sha256']
 for si in r['supplements']:assert pathlib.Path(si).is_file()
for r in old:
 after=next(x for x in current if x['id']==r['id'])
 if r['id'] not in ['R103','R106']:assert after==r
 else:assert all(after[k]==v for k,v in r.items() if k!='supplements')
result=dict(date='2026-10-17',user_confirmation='用户明确回复：确认',approved_plan_sha256=approved_hash,files_copied=17,new_papers=5,existing_SI_added=2,total_papers=126,main_PDFs=125,main_XMLs=1,PDF_supplements=9,Word_supplements=1,total_PDFs=134,unique_PDF_hashes=134,category_counts=dict(cats),original_121_main_PDFs_unchanged=True,all_original_library_files_unchanged_except_confirmed_catalog_and_guide=True,all_17_source_copies_retained=True,all_local_catalog_links_exist=True,active_catalog_rows=len(allrows),eligible_records=0,no_training=True,no_original_file_move_or_delete=True)
write_json(RUN/'入库完成核验.json',result)

STATE.write_text('''# 当前文献状态

核对日期：2026-10-17。经用户确认，第一批新资料已完成文献级归档审核并入库。

D:/文献现有126篇文献：125篇PDF正文、1篇XML完整正文（SRC124，另附TXT）；另10份SI（9份PDF、1份Word）。全部134份PDF的内容哈希不同。分类数量为41、19、15、24、27。

新增SRC123–SRC127，R103/R106各补一份SI。原121篇PDF及原补充材料未改变，项目来源副本保留。SRC125只放待核分类，SRC126含铜、SRC127为凝胶体系；归档不解除数据冻结。

研究方向为规定循环次数与条件下的循环保持率预测。正式逐记录准入仍为0，未训练模型。历史122份用途审核及旧工作簿保留原阶段范围，不冒充当前126篇覆盖结果。

- [打开当前文献目录](<D:/文献/打开文献目录.html>)
- [当前唯一位置](文献整理_20261017/当前唯一文献位置.json)
- [本次入库核验](循环稳定性文献补充_20261017/文献入库审核/已确认入库执行/入库完成核验.json)
- [最新接续](NEXT_CHAT_20261017_已确认入库126篇.md)
- [原有数据补录v2](循环稳定性文献补充_20261017/现有数据补齐/循环稳定性逐记录候选_v2.json)

原81终点候选保留；新8终点仍单列待逐条核审，不能把终点数当独立样本数。4篇未取得正文的DOI清单继续有效。
''',encoding='utf-8')
old_entry=ENTRY.read_text(encoding='utf-8-sig')
prefix='''# 当前接续入口：已确认入库126篇

2026-10-17更新：用户已确认第一批归档方案，现已实际复制入D:/文献并核验完成。请优先读[NEXT_CHAT_20261017_已确认入库126篇.md](NEXT_CHAT_20261017_已确认入库126篇.md)和[当前文献状态.md](当前文献状态.md)。

当前126篇：125篇正文PDF、1篇XML正文；10份SI（9 PDF、1 Word），总计134个不同内容PDF。分类41/19/15/24/27。原121篇及原SI未变。唯一位置索引已同步，SRC124的local_pdf为空，请按main_format读取local_fulltext/local_text。

研究方向已选择循环稳定性，用户已授权补现有数据、搜集2023年至今文献及直接下载可取得资料。本次5篇入库与2份旧文献SI归档已确认并完成，不要再次询问或重复复制。后续新批次审核完成后再按用户要求确认是否归档。未授权训练，正式记录准入0，旧冻结保留。

## 以下为入库前历史阶段说明，仅供追溯

下文的121篇、输出未定、等待安排及不自动下载等均为早期阶段信息，当前状态以上方与最新接续文件为准。历史审核与工作簿不自动改写。

'''
ENTRY.write_text(prefix+old_entry,encoding='utf-8')
handoff='''# 已确认入库126篇：后续接续

2026-10-17用户明确回复“确认”，批准上一轮具体入库方案。执行已完成，不能仍称待确认。

先按AGENTS读取长期记忆，再读本文件、当前文献状态、循环稳定性文献补充_20261017/文献入库审核/已确认入库执行/入库完成核验.json。

## 当前归档

- N001 → SRC123，A类稻壳碳，PDF正文+SI。
- N002 → SRC124，A类棉浆板碳，XML完整原文+TXT+SI，无排版正文PDF。
- N004 → SRC125，C类甘蔗渣碳，正文+SI，仅归档待核，冻结保留。
- N005 → SRC126，B类鹅毛/松木屑含铜碳，正文+SI，明确含Cu，不作纯碳。
- N009 → SRC127，B类狗尾草凝胶器件，正文PDF，SI仍待补。
- R103/R106新SI已归入原文件夹，不重复计论文。

当前库126篇，125篇正文PDF+1篇XML正文，SI9 PDF+1 Word；全库134 PDF哈希均不同。分类A/B/C/D/E=41/19/15/24/27。原121篇及原补充材料未变，17份复制来源均保留在项目。仅目录HTML与整理说明按批准范围更新。唯一位置索引已备份后同步；其中SRC124 local_pdf=null，请先检查main_format，使用local_fulltext/local_text，不再把所有文献假设成PDF。

当前正式位置以文献整理_20261017/当前唯一文献位置.json为准。旧训练审核122份、旧总表/可行性统计121篇均保留历史范围；本次新增5篇另见归档审核增量，不声称旧审核已自动覆盖新5篇。

## 后续数据

原81终点候选的最新版本仍为循环稳定性文献补充_20261017/现有数据补齐/循环稳定性逐记录候选_v2.json。新8终点在新增来源循环候选_单列未并库.json，原N编号保留，通过正式编号映射追溯，不因归档就准入。正式记录0，未训练。

原先的审核限制全部保留：SRC123追查2016前作材料/曲线复用；SRC124放大批次无独立循环标签证明；SRC125同段2/3 M和94.7/98.43归属待核；SRC126三电极循环、Cu及孔结构印刷问题；SRC127凝胶配方不当作最终溶液摩尔浓度。R091孔体积印m³/g不擅改；R106新SI有Si/EDS测法限制。

继续核补原候选基线、电流质量分母、输入配对，并寻找新增真实原始实验。4篇待用户下载正文（N003/N006/N007/N008）仍在同目录需用户下载清单.md，用户补入后核验身份并审核，不重复让用户下载已归档正文。

## 执行证据

本次备份、复制日志、执行清单、编号映射、审核增量与入库完成核验均位于循环稳定性文献补充_20261017/文献入库审核/已确认入库执行。审核前方案与第一批交付说明是历史快照，其中待确认/未入库描述已被本文件更新。

不要重跑任何历史整理、下载、删除或本轮execute_confirmed_import.py一次性脚本。后续修改另存新版并保留已录结果。未经新授权不移动、覆盖、删除原论文，不上传，不训练。
'''
(BASE/'NEXT_CHAT_20261017_已确认入库126篇.md').write_text(handoff,encoding='utf-8')
write_json(RUN/'项目入口更新清单.json',[str(STATE),str(ENTRY),str(BASE/'NEXT_CHAT_20261017_已确认入库126篇.md')])
print(json.dumps(result,ensure_ascii=False,indent=2))
