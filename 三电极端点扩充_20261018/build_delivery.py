"""Build a separate literature evidence ledger and a portable type index.
No legacy database, source PDF, manifest, or contract is edited.
External classification is a NEW copy view, with collision and hash checks.
"""
from pathlib import Path
import json, re, hashlib, sqlite3, html, shutil, collections, xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]; OUT=Path(__file__).resolve().parent
LIB=Path('D:/文献/按文献类型_20261018')
def read(p):return json.loads(Path(p).read_text('utf-8'))
def dump(name,obj): (OUT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8',newline='\n')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def local(p):
 p=Path(p);return p if p.is_absolute() else ROOT/p
def rel(p):return Path(p).resolve().relative_to(ROOT).as_posix()
STYLE='body{font:16px/1.65 system-ui,sans-serif;max-width:1380px;margin:32px auto;padding:0 22px;color:#172b3a;background:#f6f8fa}h1{font-size:28px}table{border-collapse:collapse;background:white;width:100%}td,th{border:1px solid #dce3e9;padding:9px;text-align:left;vertical-align:top}th{background:#e6edf4}a{color:#125b91}input,select{padding:9px;margin:8px 8px 16px 0;min-width:240px}article,figure{background:white;padding:16px;margin:16px 0}img{max-width:100%;height:auto}small{color:#526577}.warn{background:#fff1d7;padding:15px}pre{white-space:pre-wrap}thead{position:sticky;top:0}'
def page(title,body):return '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+html.escape(title)+'</title><style>'+STYLE+'</style><body>'+body+'</body></html>'
def reading_html(source):
 """Render full body text + original figures/tables. XML/PDF remains the authority."""
 d=Path(source).parent;root=ET.parse(source).getroot();title=' '.join(''.join(root.find('.//article-title').itertext()).split())
 parts=['<h1>'+html.escape(title)+'</h1><p>本地阅读版：出版社提交的完整 XML 正文与原图。排版由本项目生成；原始 XML 为证据。不是出版社 PDF。</p>']
 for doi in root.findall('.//article-id[@pub-id-type="doi"]'):parts.append('<p>DOI: '+html.escape(doi.text or '')+'</p>')
 for abstract in root.findall('.//article-meta/abstract'):parts.append('<article><h2>Abstract</h2><p>'+html.escape(' '.join(''.join(abstract.itertext()).split()))+'</p></article>')
 body=root.find('.//body')
 if body is not None:
  # Paragraph IDs agree with corpus extraction. Avoid duplicate nested paragraphs in tables/captions.
  idx=0
  def visit(e):
   nonlocal idx
   if e.tag in ['p','caption','table']:
    idx+=1
    text=' '.join(''.join(e.itertext()).split())
    parts.append(f'<article id="P{idx:04d}"><small>P{idx:04d}</small><p>'+html.escape(text)+'</p></article>')
    # Descendant nodes count in corpus numbering even when not displayed twice.
    idx+=sum(1 for x in list(e.iter())[1:] if x.tag in ['p','caption','table'])
    return
   if e.tag=='title':parts.append('<h2>'+html.escape(''.join(e.itertext()))+'</h2>')
   for child in e:visit(child)
  visit(body)
 # Some publishers place ALL figures/tables in floats-group outside body.
 parts.append('<h2>原文图表（含文末 floats-group）</h2>')
 for f in root.findall('.//fig'):
  caption=' '.join(''.join(f.itertext()).split());parts.append('<figure>');seen=set()
  for g in f.findall('.//graphic'):
   stem=Path(g.attrib.get('{http://www.w3.org/1999/xlink}href','')).stem
   if stem in seen:continue
   seen.add(stem);candidates=[p for p in (d/'assets').glob('*') if p.stem==stem and p.suffix.lower() in ['.jpg','.jpeg','.png']]
   if candidates:parts.append('<img loading="lazy" src="assets/'+html.escape(candidates[0].name,quote=True)+'" alt="原文图">')
  parts.append('<figcaption>'+html.escape(caption)+'</figcaption></figure>')
 for tab in root.findall('.//table-wrap'):
  parts.append('<article><p>'+html.escape(' '.join(''.join(tab.find('caption').itertext()).split()) if tab.find('caption') is not None else '')+'</p><table>')
  for tr in tab.findall('.//tr'):
   parts.append('<tr>'+''.join('<td>'+html.escape(' '.join(''.join(c.itertext()).split()))+'</td>' for c in tr if c.tag in ['th','td'])+'</tr>')
  parts.append('</table></article>')
 refs=root.find('.//ref-list')
 if refs is not None:parts.append('<h2>References</h2><article>'+html.escape(' '.join(''.join(refs.itertext()).split()))+'</article>')
 if (d/'assets').exists():
  docs=[p for p in (d/'assets').iterdir() if p.suffix.lower() in ['.pdf','.doc','.docx','.xls','.xlsx']]
  if docs:parts.append('<h2>原始补充文件</h2><ul>'+''.join('<li><a href="assets/'+html.escape(p.name,quote=True)+'">'+html.escape(p.name)+'</a></li>' for p in docs)+'</ul>')
 dest=d/'正文阅读版.html';dest.write_text(page(title,''.join(parts)),encoding='utf-8');return dest
def sources():
 src={r['tag']:r for r in read(OUT/'corpus_index.json')}
 for f in ['new_acquisition.json','older_acquisition.json','older2_acquisition.json','older3_acquisition.json']:
  for r in read(OUT/f):
   if r['status']=='obtained':src[r['pmcid']]={'tag':r['pmcid'],'doi':r['doi'].lower(),'title':r['title'],'source_path':r['source_path'],'source_sha256':r['sha256'],'text_path':r['text_path']}
 return src
def make_ledger(src):
 rows=read(OUT/'manual_endpoint_reviews.json');ledger=[]
 for i,r in enumerate(rows,1):
  s=src[r['source_tag']];text=local(s['text_path']).read_text('utf-8');lines=text.splitlines();tag=r['source_tag']
  r={**r,'endpoint_id':f'TE{i:03d}','doi':s['doi'],'title':s['title'],'source_file':s['source_path'],'source_sha256':s['source_sha256'],'text_file':s['text_path'],'study_group':'doi:'+s['doi'],'count_profile':'three_electrode_GCD_numeric_N_and_retention','counted':True,'scientific_status':'staged_evidence_only_not_database_admission','reported_current_other':{'value':1,'unit':'mA/cm2'} if tag=='PMC9033565' else None,'scope_flags':['mixed_cellulose_SAP_diaper_feedstock'] if tag=='PMC12175059' else ['mixed_lignin_PAN_feedstock'] if tag=='PMC6401840' else [],'current_mass_basis':'not_finalized_do_not_infer_from_C_formula','cycle_voltage_lower_V':None,'cycle_voltage_upper_V':None,'cycle_voltage_status':'not_finalized_for_this_delivery','baseline_definition_status':'not_finalized','BET_features_status':'not_merged_not_finalized'}
  if tag.startswith('PMC'):
   root=ET.parse(local(s['source_path'])).getroot()
   r['publisher_url']='https://pmc.ncbi.nlm.nih.gov/articles/'+tag+'/'
   r['figure_captions']=[' '.join(''.join(f.itertext()).split()) for f in root.findall('.//fig') if any(w in ''.join(f.itertext()).lower() for w in ['cycling','stability','cycles'])]
   r['reading_file']=rel(reading_html(local(s['source_path'])))
  else:r['publisher_url']='https://doi.org/'+s['doi'];r['reading_file']=s['source_path']
  # Small, inspectable excerpts for navigation. They do not replace the explicit human locator.
  r['configuration_evidence_excerpts']=[l[:2500] for l in lines if re.search(r'three[ -]electrode|three.and.two|two.and.three',l,re.I)][:3]
  r['cycling_evidence_excerpts']=[l[:5000] for l in lines if re.search(r'cycling|cycles|retention|retained',l,re.I) and re.search(r'%|percent|capacitance',l,re.I)][-12:]
  ledger.append(r)
 dump('三电极端点_53条.json',{'schema':'three-electrode-staged-ledger-v1','date':'2026-10-18','definition':'One material × electrolyte × cycling protocol × terminal N. Same-paper variants share DOI study_group. Explicit approximate and 100-loss values remain distinguished. Not 53 independent papers and not training-admitted records.','rows':ledger})
 counts={'endpoints':len(ledger),'papers':len({r['doi'] for r in ledger}),'reported_point':sum(r['value_kind']=='reported' and r['retention_relation']=='eq' for r in ledger),'reported_approximate':sum(r['retention_relation']=='approx' for r in ledger),'loss_complement':sum(r['value_kind']=='loss_complement' for r in ledger),'current_A_g_located':sum(r['reported_current_A_g'] is not None for r in ledger),'areal_current_only':sum(r['reported_current_other'] is not None for r in ledger),'current_unlocated':sum(r['reported_current_A_g'] is None and r['reported_current_other'] is None for r in ledger),'mixed_feedstock_flagged':sum(bool(r['scope_flags']) for r in ledger),'training_admitted':0}
 dump('endpoint_counts.json',counts)
 trs=[]
 for r in ledger:
  link='../'+r['reading_file'];ret=('约' if r['retention_relation']=='approx' else '')+str(r['retention_pct'])+('%（100−损失率）' if r['value_kind']=='loss_complement' else '%')
  current=str(r['reported_current_A_g'])+' A/g' if r['reported_current_A_g'] is not None else '1 mA/cm²' if r['reported_current_other'] else '未定位'
  vals=[r['endpoint_id'],r['sample'],str(r['cycle_count']),ret,current,str(r['concentration_mol_L'])+' M '+r['electrolyte'] if r['concentration_mol_L'] is not None else r['electrolyte']+' 浓度未定位',r['doi'],r['locator'],r['review_note']]
  trs.append('<tr>'+''.join('<td>'+('<a href="'+html.escape(link,quote=True)+'">'+html.escape(v)+'</a>' if j==6 else html.escape(v))+'</td>' for j,v in enumerate(vals))+'</tr>')
 script='<script>document.querySelector("input").oninput=e=>document.querySelectorAll("tbody tr").forEach(r=>r.hidden=!r.textContent.toLowerCase().includes(e.target.value.toLowerCase()))</script>'
 (OUT/'三电极端点清单.html').write_text(page('三电极循环端点清单','<h1>53 个三电极 GCD 循环端点 · 41 篇论文</h1><p class="warn">'+html.escape(str(counts))+'。暂存证据，不等于训练准入。近似值和换算值单列；同篇多样品不算独立论文。质量分母、循环窗口、BET、材料身份及基线仍须后续终审。</p><input placeholder="搜索材料、DOI、端点编号"><table><thead><tr>'+''.join('<th>'+t+'</th>' for t in ['编号','材料','循环次数','保持率','循环电流','电解液','原文 DOI','定位','备注'])+'</tr></thead><tbody>'+''.join(trs)+'</tbody></table>'+script),encoding='utf-8')
 return ledger,counts
TYPES=['01_机器学习综述','02_机器学习与统计建模原始研究','03_原始实验研究','04_材料与储能综述','05_方法与基础理论','06_其他主题综述','07_书籍与章节','08_类型待核']
MLREV={'R008','R011','SRC075','SRC078'}
MLRES={'R001','R002','R005','R007','R057','SRC026','SRC030','SRC071','SRC072','SRC073','SRC074','SRC077','SRC081','SRC082','SRC083','SRC086','SRC087'}
REV={'R009','R010','R021','R027','R037','R041','SRC069','SRC070','SRC084','SRC085'}
OTHERREV={'SRC097','SRC109','SRC118'}
BOOK={'SRC095','U012','U020'}
def doctype(r):
 i=r['id'];t=r['title'];front=r.get('front','');at=r.get('article_type','')
 if i in MLREV:return TYPES[0],'已核首页/摘要：机器学习主题综述'
 if i in MLRES:return TYPES[1],'已核标题与摘要：原创建模/PCA研究；原始实验与汇编数据需另区分'
 if i in REV:return TYPES[3],'已核首页/摘要：Review/研究进展，非本文新实验'
 if i in OTHERREV or i=='U001':return TYPES[5],'已核首页/摘要：其他主题综述；保留背景用途'
 if i in BOOK:return TYPES[6],'已核书籍/章节或书籍预览；不计独立实验论文'
 if at in ['review-article','systematic-review']:return TYPES[3],'出版社XML article-type='+at
 if i.startswith(('R','SRC','U','B2_','EXT_','PMC')):return TYPES[2],'已有逐篇核验/原文研究正文；类型为原始研究，循环目标准入另审'
 return TYPES[7],'类型证据不足，待核；不计目标'
def build_library(src,ledger):
 assert LIB.resolve()==Path('D:/文献/按文献类型_20261018').resolve()
 LIB.mkdir(exist_ok=True);records=[];bykey={};doi_rows={}
 con=sqlite3.connect('file:'+str(ROOT/'循环稳定性数据库_v0.3_数据库优化_20261017/第四轮_专业复核与训练数据_20261017/cycling_v0_3r4.sqlite')+'?mode=ro',uri=True);con.row_factory=sqlite3.Row
 papers={r['paper_id']:dict(r) for r in con.execute('select * from papers')};con.close()
 def add(i,doi,title,p,si=None,front='',article_type='',note=''):
  if not p or not local(p).exists():return
  p=local(p).resolve();key=('doi:'+doi.lower()) if doi else ('sha:'+sha(p));supp=[local(x) for x in si or [] if local(x).exists()]
  if key in bykey:
   old=bykey[key];old['aliases'].append(i);old['source_versions'].append({'path':str(p),'sha256':sha(p)})
   old['supplement_sources']=list(dict.fromkeys(old['supplement_sources']+[str(x) for x in supp]));return
  r={'id':i,'aliases':[],'doi':doi.lower() if doi else None,'title':title,'source_path':str(p),'source_sha256':sha(p),'source_versions':[{'path':str(p),'sha256':sha(p)}],'supplement_sources':[str(x) for x in supp],'front':front[:1800],'article_type':article_type,'note':note,'training_admitted':False}
  r['document_type'],r['type_basis']=doctype(r)
  r['experimental_data_status']='original_experiments_present_target_endpoint_requires_review' if r['document_type']==TYPES[2] else 'original_modeling_or_statistics_not_automatically_original_experiments' if r['document_type']==TYPES[1] else 'not_used_as_new_experimental_endpoint'
  r['endpoint_ids']=[e['endpoint_id'] for e in ledger if e['doi']==r['doi']];r['cycle_system_status']='3E_GCD_has_reviewed_endpoint' if r['endpoint_ids'] else 'not_in_current_3E_count_keep_2E_CV_other_and_unreviewed_separate'
  bykey[key]=r;records.append(r)
 for r in read(OUT/'classification_review_inputs.json'):
  p=papers.get(r['id'],{});add(r['id'],p.get('doi') or '',p.get('title') or Path(r['local_pdf']).parent.name,r['local_pdf'],r.get('supplements'),r.get('front',''))
 for r in read(ROOT/'用户补充文献核验_20261018/核验记录_26份.json')['records']:
  add(r['id'],r.get('doi') or '',r['filename'].removesuffix('.pdf'),r['original_path'],front=r.get('front_excerpt',''),note=r['review_note'])
 batch=ROOT/'同体系文献补充_第二批_20261017'
 for r in read(batch/'候选文献审核表.json')['records']:
  add(r['candidate_id'],r['doi_normalized'],r['title'],r['fulltext'].get('path'),r['supplements'].get('paths',[]),note='前20篇独立候选批次；未并入正式数据库')
 for r in read(batch/'定向扩搜40至60篇_20261017/新增50篇_逐篇数据与获取状态.json')['records']:
  paths=r.get('complete_main_files',[])
  if paths:add(r['temporary_id'],r['doi'],r['title'],paths[0],r.get('supporting_documents_obtained',[]),note='前50篇候选；测试配置与科学准入分开')
 # Promote only the 19 newly reviewed study sources, not the other screening-only XML downloads.
 for tag in sorted({e['source_tag'] for e in ledger if e['source_tag'].startswith('PMC')}):
  s=src[tag];p=local(s['source_path']);root=ET.parse(p).getroot();docs=list((p.parent/'assets').glob('*.pdf'))+list((p.parent/'assets').glob('*.docx'))+list((p.parent/'assets').glob('*.xlsx'))
  add(tag,s['doi'],s['title'],p,docs,article_type=root.attrib.get('article-type',''),note='本轮已核三电极来源；完整XML+原图阅读版，PDF请求受限时不伪装成PDF')
 portable={r['sha256']:r['portable_copies'] for r in read(ROOT/'data/source_locations_portable.json')['records']}
 user_pdf={r['sha256']:r.get('repository_pdf') for r in read(ROOT/'用户补充文献核验_20261018/核验记录_26份.json')['records'] if r.get('repository_pdf')}
 copylog=[]
 def copy(p,d):
  p=Path(p).resolve();d=Path(d).resolve();assert d.is_relative_to(LIB.resolve())
  d.parent.mkdir(parents=True,exist_ok=True)
  if d.exists():
   if sha(d)!=sha(p):
    if p.is_relative_to(OUT) and p.name=='正文阅读版.html':shutil.copy2(p,d)
    else:raise ValueError('Existing different destination: '+str(d))
  else:shutil.copy2(p,d)
  copylog.append({'source':str(p),'destination':str(d),'sha256':sha(p),'bytes':p.stat().st_size});return d
 for r in records:
  p=Path(r['source_path']);d=LIB/r['document_type']/r['id'];d.mkdir(parents=True,exist_ok=True)
  if p.suffix.lower()=='.pdf':main=copy(p,d/'正文.pdf');repo=next((e['source_file'] for e in ledger if e['doi']==r['doi'] and e['source_file'].endswith('.pdf')),None)
  elif p.suffix.lower()=='.xml':
   # Existing XML packs have an existing reader or can be rendered with local images.
   generated=reading_html(p) if p.is_relative_to(OUT) else None
   copy(p,d/'main.xml');
   for f in ['main.txt','正文阅读版.html','reading.html','main.html','readable_article.html']:
    if (p.parent/f).exists():copy(p.parent/f,d/f)
   assets=p.parent/'assets'
   if assets.exists():
    for f in assets.iterdir():
     if f.is_file():copy(f,d/'assets'/f.name)
   # Older batches use figures/ and their own full HTML. Copy only their same-paper assets.
   for folder in ['figures','supplements']:
    if (p.parent/folder).exists():
     for f in (p.parent/folder).rglob('*'):
      if f.is_file():copy(f,d/folder/f.relative_to(p.parent/folder))
   mains=[d/f for f in ['正文阅读版.html','reading.html','main.html','readable_article.html'] if (d/f).exists()]
   main=mains[0] if mains else d/'main.xml';repo=rel(p) if p.is_relative_to(ROOT) else None
  else:main=copy(p,d/p.name);repo=rel(p) if p.is_relative_to(ROOT) else None
  for i,s in enumerate(r['supplement_sources'],1):
   copy(s,d/'补充材料'/(str(i).zfill(2)+'_'+Path(s).name))
   if p.suffix.lower()=='.xml':copy(s,d/Path(s).name)
  if repo is None and p.is_relative_to(ROOT):repo=rel(p)
  if repo is None and r['source_sha256'] in user_pdf:repo=user_pdf[r['source_sha256']]
  r['portable_source_locations']=portable.get(r['source_sha256'],[])
  if repo is None:
   direct=next((x['path'] for x in r['portable_source_locations'] if x['kind']=='repository_file'),None)
   if direct:repo=direct
  if repo is None and not r['portable_source_locations']:
   # Four user-supplied background/book originals previously had metadata only.
   target=OUT/'classified_background'/r['id']/p.name;target.parent.mkdir(parents=True,exist_ok=True)
   if target.exists():assert sha(target)==sha(p)
   else:shutil.copy2(p,target)
   repo=rel(target)
  r['classified_main']=str(main);r['classified_folder']=str(d);r['repository_source']=repo
  (d/'文献身份与用途.json').write_text(json.dumps({k:v for k,v in r.items() if k!='front'},ensure_ascii=False,indent=2),encoding='utf-8')
 dump('文献类型分类索引.json',{'date':'2026-10-18','mode':'new_copies_original_paths_preserved','external_root':str(LIB),'counts':dict(collections.Counter(r['document_type'] for r in records)),'records':records})
 dump('分类复制与原件哈希.json',copylog)
 def index(external):
  trs=[]
  for r in records:
   p=Path(r['classified_main']);href=p.relative_to(LIB).as_posix() if external else p.as_uri()
   doi=r['doi'] or '未核定 DOI，不编造';flags='三电极端点 '+','.join(r['endpoint_ids']) if r['endpoint_ids'] else '未计本轮三电极目标；保留其它体系/待核'
   portable=r.get('repository_source')
   if not external and portable:href='../'+portable
   elif not external and r['portable_source_locations']:
    archive=next(x for x in r['portable_source_locations'] if x['kind']=='archive_member');href='../'+archive['archive']
    vals_hint='（正文位于压缩包：'+archive['member']+'；按SHA核对后提取该成员）'
   else:vals_hint=''
   vals=[r['document_type'][3:],r['id']+(' / '+','.join(r['aliases']) if r['aliases'] else ''),r['title']+(vals_hint if not external and not portable and r['portable_source_locations'] else ''),doi,flags,r['experimental_data_status']]
   trs.append('<tr data-type="'+r['document_type']+'">'+''.join('<td>'+('<a href="'+html.escape(href,quote=True)+'">'+html.escape(v)+'</a>' if j==2 else html.escape(v))+'</td>' for j,v in enumerate(vals))+'</tr>')
  counts=collections.Counter(r['document_type'] for r in records)
  return page('按文献类型分类目录','<h1>按文献类型分类 · '+str(len(records))+' 个文献身份</h1><p>机器学习综述、建模原始研究、实际实验研究分开。测试体系是另一标签；有实验不等于有合格循环端点。SI 随所属论文保存，不另算论文。旧路径与唯一原件保留；本目录为分类副本视图。</p><p>'+html.escape('；'.join(k+': '+str(v) for k,v in sorted(counts.items())))+'</p><input id="q" placeholder="搜索标题、DOI、编号"><select id="t"><option value="">全部类型</option>'+''.join('<option>'+t+'</option>' for t in TYPES)+'</select><table><thead><tr>'+''.join('<th>'+s+'</th>' for s in ['文献类型','编号/别名','打开正文','DOI','循环核验状态','数据性质'])+'</tr></thead><tbody>'+''.join(trs)+'</tbody></table><script>function filter(){let q=document.getElementById("q").value.toLowerCase(),t=document.getElementById("t").value;document.querySelectorAll("tbody tr").forEach(r=>r.hidden=!(r.textContent.toLowerCase().includes(q)&&(!t||r.dataset.type===t)))}document.getElementById("q").oninput=filter;document.getElementById("t").onchange=filter</script>')
 (LIB/'打开按类型分类目录.html').write_text(index(True),encoding='utf-8');(OUT/'文献类型目录.html').write_text(index(False),encoding='utf-8')
 (LIB/'整理说明.md').write_text('这是2026-10-18按文献类型建立的分类副本视图。旧目录和根目录原件均保留，数据库引用继续有效。不要把副本和原件相加当作新论文。原文与SI按论文编号同存。130份检索XML中的未入本轮核验集资料仍在项目new_sources暂存，不自动归档或准入。\n',encoding='utf-8')
 return records
if __name__=='__main__':
 s=sources();ledger,counts=make_ledger(s);library=build_library(s,ledger)
 print(json.dumps({'endpoint_counts':counts,'classified_identities':len(library),'types':dict(collections.Counter(r['document_type'] for r in library))},ensure_ascii=False,indent=2))
