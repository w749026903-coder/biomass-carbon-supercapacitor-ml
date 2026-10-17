import json,hashlib,re,html,concurrent.futures
from pathlib import Path
from lxml import etree,html as lhtml
from pypdf import PdfReader
ROOT=Path(__file__).resolve().parent;PARENT=ROOT.parent
def save(p,obj):p.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
bundle=json.loads((ROOT/'新增50篇_逐篇数据与获取状态.json').read_text(encoding='utf-8'));rows=bundle['records'];stats=bundle['stats']
readers=json.loads((ROOT/'完整正文原图与阅读版获取记录.json').read_text(encoding='utf-8'))
stats.update(readable_html_with_local_figures=len(readers),missing_graphic_references=sum(len(x['missing_graphic_references']) for x in readers),main_XML_papers=sum(any(p.endswith('.xml') for p in x['complete_main_files']) for x in rows),main_PDF_papers=sum(any(p.endswith('.pdf') for p in x['complete_main_files']) for x in rows))
save(ROOT/'扩搜统计.json',stats)
old=json.loads((PARENT/'候选文献审核表.json').read_text(encoding='utf-8'))['records']
pending=[]
for x in rows:
    if not x['complete_main_files']:pending.append({'id':x['temporary_id'],'doi':x['doi'],'title':x['title'],'needed':'正文及已声明的SI','purpose':x['material']+'；'+x['reported_retention_or_observation']+' / '+str(x['reported_cycle_count'])+'圈；补循环电流、实际窗口和质量口径','group':'本次新增50篇缺正文'})
for x in old:
    if not x['fulltext'].get('path'):pending.append({'id':x['candidate_id'],'doi':x['doi_normalized'],'title':x['title'],'needed':'正文及已声明的SI','purpose':x['material']+'；补循环协议、孔体积及材料关系','group':'上轮20篇缺正文'})
prior=json.loads((PARENT/'现有来源补件表.json').read_text(encoding='utf-8'))['records']
for x in prior:
    pending.append({'id':x['existing_id'],'doi':x['related_doi'],'title':x['existing_id']+'既有来源补件','needed':x['needed'],'purpose':x['result'],'group':{'existing_paper_missing_SI':'既有正文已取得，仅补SI','prior_work_for_provenance_only':'仅核出处的2016前作','previous_batch_pending_main':'前批9条中缺正文'}[x['kind']]})
pending.append({'id':'N009/SRC127','doi':'10.1016/j.jics.2025.102074','title':'High-performance flexible supercapacitors based on porous carbon derived from Setaria viridis stalks','needed':'SI（正文已取得）','purpose':'PVA/H2SO4凝胶器件旁系；补BET/孔结构，后置下载，不计新篇数','group':'保留旁系的SI，可后置'})
assert len({x['doi'] for x in pending})==len(pending),(len(pending),len({x['doi'] for x in pending}))
# N003 is the old three-electrode lead and becomes the highest-priority outstanding main.
pending.sort(key=lambda x:(0 if x['id']=='N003' else {'本次新增50篇缺正文':1,'前批9条中缺正文':2,'上轮20篇缺正文':3,'既有正文已取得，仅补SI':4,'仅核出处的2016前作':5,'保留旁系的SI，可后置':6}[x['group']],x['id']))
save(PARENT/'全部需下载资料_逐项用途.json',{'as_of':'2026-10-17','scope':'现有明确缺件及本次50篇目标；不是原126篇全部重新下载','records':pending,'unique_dois':len(pending)})
(PARENT/'全部待补资料_完整DOI.txt').write_text('\n'.join(x['doi'] for x in pending)+'\n',encoding='utf-8')
lines=['# 全部需下载文献与用途','', '核验日期：2026-10-17。后续以三电极为搜索优先方向；双电极、CV、有机/DES及凝胶等既有资料全部保留并分开标注。','',f'本次新增50篇实验文献：{stats["complete_main_papers"]}篇取得完整正文，其中{stats["main_XML_papers"]}篇为XML并配有本地原图/HTML阅读版，{stats["main_PDF_papers"]}篇为出版社PDF；{stats["missing_complete_main_papers"]}篇未取得完整正文。{stats["papers_with_supporting_documents"]}篇取得了补充文档。它们均有本篇原始循环实验数据依据，但16篇只有原始摘要/出版社元数据核验，不能保证全部建模字段齐全。','', '此前20篇候选与前批9条原样保留，未用旧文献充作本次新增数量。以下将当前明确待补的正文、SI和核出处前作合并列出，每个DOI只出现一次。','', f'共{len(pending)}个待补资料DOI：本次50篇缺正文16项、上轮20篇缺正文4项、前批缺正文4项、已有正文缺SI2项、核出处前作1项、可后置的凝胶SI1项。这里“尚未取得”包括付费、公开入口403、超时等情况，不代表文献不存在或原文未报告。','', '未遇到可直接取得的公开正文时已保留原始访问记录；没有绕过付费、登录或访问限制。已取得XML正文的论文无需为纯文本阅读重复下载PDF；需要引用出版社版式时仍可从DOI页获取PDF。','', '## 待补全量清单','', '|优先类别/编号|完整DOI|所需文件|用途与限制|','|---|---|---|---|']
for x in pending:lines.append(f'|{x["group"]} / {x["id"]}|[{x["doi"]}](https://doi.org/{x["doi"]})|{x["needed"]}|{x["purpose"]}|')
lines+=['','## 完整DOI列表','', '```text']+[x['doi'] for x in pending]+['```','','## 已取得资料入口','',f'- [新增50篇清单与数据用途]({ROOT / "新增50篇_清单与下载结果.md"})',f'- [文献导航（可筛三电极、已取得正文、待补正文）]({ROOT / "文献导航.html"})',f'- [逐篇结构化证据]({ROOT / "新增50篇_逐篇数据与获取状态.json"})',f'- [上轮20篇候选]({PARENT / "候选DOI与获取状态.md"})','', '完整DOI纯文本另存《全部待补资料_完整DOI.txt》。额外检索的旁系、CV以及未完成配对的线索见本次扩搜目录《保留的其它体系与未选线索.json》，不计入新增50篇，也不建议为凑数量直接批量采购。','']
(PARENT/'全部需下载文献与用途.md').write_text('\n'.join(lines),encoding='utf-8')
direction='''# 检索方向与资料保留说明

2026-10-17，用户根据导师意见明确要求：后续检索尽量优先三电极；不删除双电极或其它体系的数据资料。

已将三电极作为本轮后半程及后续检索的优先方向。三电极必须从方法、循环图及参比/对电极配置核实，不能只看摘要的electrode措辞；同一论文三电极表征、双电极循环必须逐测试区分。

原20篇候选、前批9条和本次扩展资料全部保留。此前因只找到三电极循环而另列的L19花生壳等资料仍在sources，现在可优先复核；不重复计为本次新增。前批N003过期蜂蜜属于三电极线索，已将其待补正文提高到全量缺件清单首位。

CV循环、GCD循环、普通水系、DES、有机、凝胶、面积电流以及金属复合材料继续分别标记。搜索优先级的调整不自动修改数据库、model_contract或解除既有冻结，不把不同测试配置未经审核混入同一个学习目标。

本次“50篇有实际数据”指50个新论文身份内定位到原始循环实验或可核循环图；不是50条已准入标签，也不是50个材料的独立性终审结果。缺全文的16篇保留明确限制。
'''
(PARENT/'搜索方向与资料保留说明_20261017.md').write_text(direction,encoding='utf-8')
# A local, self-contained reading index; no external scripts, uploads or services.
def e(s):return html.escape(str(s),quote=True)
tr=[]
for r in rows:
    reader=r['readable_html'] or (r['complete_main_files'][0] if r['complete_main_files'] else None)
    href=Path(reader).as_uri() if reader else r['doi_url']
    tr.append('<tr data-three="'+str(int(r['cycle_configuration'].startswith('三电极')))+'" data-full="'+str(int(bool(r['complete_main_files'])))+'"><td>'+e(r['temporary_id'])+'<br>'+e(r['cycle_configuration'])+'</td><td><a href="'+e(href)+'">'+e(r['material'])+'</a><div class="title">'+e(r['title'])+'</div><a class="doi" href="'+e(r['doi_url'])+'">'+e(r['doi'])+'</a></td><td>'+e(r['reported_cycle_count'])+'圈<br>'+e(r['reported_retention_or_observation'])+'<br><small>'+e(r['reported_current'])+'</small></td><td>'+('已取得正文' if reader else '待补正文')+('<br>SI已取得' if r['supporting_documents_obtained'] else '')+'</td><td>'+e(r['audit_notes'])+'</td></tr>')
doc='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>超级电容器实验文献</title><style>body{margin:0;background:#f5f6f8;color:#252b31;font:15px/1.65 "Microsoft YaHei",Arial,sans-serif}main{max-width:1500px;margin:30px auto;padding:0 24px}h1{font-size:29px;margin-bottom:8px}.intro{max-width:1100px;color:#56606a}.counts{font-size:19px;margin:20px 0}.controls{display:flex;gap:10px;flex-wrap:wrap;margin:20px 0}input,select{padding:10px 12px;border:1px solid #bdc8d2;border-radius:6px;background:white;font:inherit}input{min-width:330px}table{width:100%;border-collapse:collapse;background:white}td,th{text-align:left;padding:15px 12px;border-bottom:1px solid #e0e5e9;vertical-align:top}th{background:#233e50;color:white;position:sticky;top:0}td:first-child{width:110px}.title{font-size:13px;color:#68727c;margin:5px 0}.doi{font-size:12px}a{color:#16618a;text-decoration:none}a:hover{text-decoration:underline}small{color:#69757f}td:last-child{width:28%;font-size:13px}.note{font-size:13px;color:#66727c;margin:20px 0}</style><main><h1>超级电容器实验文献</h1><p class="intro">新增50篇，按三电极优先整理。双电极和其它资料保留。每篇附循环数据依据与待核事项；点击原料名称可打开已取得的正文或原文入口。</p><div class="counts">50篇新增 · 34篇完整正文 · 16篇待补正文 · '''+str(stats['papers_with_supporting_documents'])+'''篇含补充文档</div><div class="controls"><input id="q" placeholder="搜索原料、题名、DOI或循环数据"><select id="kind"><option value="all">全部资料</option><option value="three">三电极优先</option><option value="full">已取得正文</option><option value="missing">待补正文</option></select><span id="count"></span></div><table><thead><tr><th>编号与配置</th><th>文献</th><th>循环数据</th><th>取得情况</th><th>用途与待核事项</th></tr></thead><tbody>'''+''.join(tr)+'''</tbody></table><p class="note">截至2026-10-17。XML本地阅读版配有原图，原始文件保留；它不是出版社版式PDF。缺全文的条目只核过原始摘要或出版社元数据。所有条目仍需逐测试准入审核，未直接写入训练数据库。</p></main><script>const q=document.querySelector('#q'),k=document.querySelector('#kind');function filter(){let n=0;for(const r of document.querySelectorAll('tbody tr')){const t=q.value.trim().toLowerCase();let yes=r.innerText.toLowerCase().includes(t);if(k.value==='three')yes=yes&&r.dataset.three==='1';if(k.value==='full')yes=yes&&r.dataset.full==='1';if(k.value==='missing')yes=yes&&r.dataset.full==='0';r.hidden=!yes;if(yes)n++;}document.querySelector('#count').textContent='显示 '+n+' 篇';}q.addEventListener('input',filter);k.addEventListener('change',filter);filter();</script></html>'''
(ROOT/'文献导航.html').write_text(doc,encoding='utf-8')
# Durable evidence of the visual spot checks actually performed.
save(ROOT/'图像核查记录_扩搜.json',{'scope':'4项抽查，不声称逐图全审','checks':[{'working_id':'OA003','location':'Fig.7c','file':str(ROOT/'sources/OA003/nanomaterials-15-00387-g007.jpg'),'finding':'94.1%标签、10000圈、10 A/g插图可见；三电极段图示负电位窗口，不移器件窗口'},{'working_id':'OA006','location':'Fig.7c','file':str(ROOT/'sources/OA006/nanomaterials-14-00071-g007.jpg'),'finding':'三种样品绝对电容曲线可读；图和正文衰减描述不完全一致，未捏造保持率终点'},{'working_id':'OA050','location':'Fig.8','file':str(ROOT/'sources/OA050/materials-17-03233-g008.jpg'),'finding':'WHAC100约99%，其它剂量下降；插图电位约-0.3至0.3 V，与CV窗口区别保留'},{'working_id':'P057','location':'PDF p16 Fig.13F','file':str(ROOT/'qa/P057_page16.png'),'finding':'器件循环曲线近95%/10000圈，正文p17报告95.23%和20 A/g；图注D/E标题错置保留'}]})
# Validate source integrity without touching any shared inputs.
baseline=json.loads((PARENT/'基线与原文保护指纹.json').read_text(encoding='utf-8'))
def check(x):
    p=Path(x['path']);expected=x.get('expected_sha256') or x.get('sha256');actual=sha(p) if p.exists() else None
    return {'path':str(p),'expected_sha256':expected,'actual_sha256':actual,'unchanged':expected==actual}
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:protected=list(ex.map(check,baseline['source_files']+baseline['inputs']))
db=Path(baseline['database']);protected.append({'path':str(db),'expected_sha256':baseline['database_sha256'],'actual_sha256':sha(db),'unchanged':sha(db)==baseline['database_sha256']})
errors=[];pdfs=[]
for x in rows:
    if x['complete_main_files'] and not x['source_evidence']:errors.append(x['temporary_id']+': no local evidence locator')
    if x['readable_html']:
        p=Path(x['readable_html']);tree=lhtml.fromstring(p.read_text(encoding='utf-8'))
        for src in tree.xpath('//img/@src'):
            if not (p.parent/src).is_file():errors.append(x['temporary_id']+': missing local image '+src)
    for fn in x['complete_main_files']+x['supporting_documents_obtained']:
        p=Path(fn)
        if p.suffix.lower()=='.pdf':
            try:pages=len(PdfReader(str(p)).pages);pdfs.append({'path':str(p),'pages':pages,'valid':True})
            except Exception as er:errors.append(str(p)+': '+str(er))
qa={'as_of':'2026-10-17','stats':stats,'identity_and_dedup_assertions_passed':True,'original_137_documents_unchanged':all(x['unchanged'] for x in protected[:137]),'protected_files':protected,'local_reader_checks':{'readers':len(readers),'missing_graphic_references':stats['missing_graphic_references']},'pdf_parse_checks':pdfs,'errors':errors,'missing_download_unique_DOIs':len(pending),'database_writes':False,'training_executed':False}
save(ROOT/'交付核验_扩搜.json',qa)
assert not errors,errors
assert all(x['unchanged'] for x in protected),'A protected input changed externally; inspect report before merging'
# Versioned continuation handoff preserves the earlier handoff intact.
handoff=f'''# 文献侧续搜交付与三电极方向调整

日期：2026-10-17。此前20篇交付保留；本次另外完成50篇库外原始实验文献的候选审核包。50个DOI均未命中共同基线、前批9条及原20篇的DOI/规范化题名；材料、批次、前作及曲线独立性尚未终审。

取得34篇完整正文（32 XML、2 PDF）；32篇XML均配本地HTML及原图，未匹配graphic引用数为0。{stats['papers_with_supporting_documents']}篇有补充文档。16篇只有原始摘要/出版社存入的元数据及访问记录，未冒称全文核验。50篇中15篇优先按三电极数据整理，35篇主要保留双电极；三电极组包含1篇DES旁系，另有2篇同时有3E/2E。不是50篇全为三电极。

用户中途根据导师意见要求后续尽量三电极，双电极及其它资料不删除，已执行新的三电极定向检索并记录到《搜索方向与资料保留说明_20261017.md》。三电极/器件须逐测试配对，既有model_contract未擅自修改。严格准入0，独立材料数终审0，不执行训练。

全量缺件清单28个唯一DOI：16新缺正文、4上轮缺正文、4前批缺正文、2既有SI、1仅核出处的2016前作、1可后置凝胶SI。N003蜂蜜3E待补全文已提高优先级。所有额外未选线索及旁系保留，不凑50篇、不删原文件。

图文矛盾继续保留：杜仲木91.4/92.3%；Tucuma摘要98/正文近100%；水葫芦浓度与循环窗；聚苯并噁嗪151→117 F/g却称89%；橙汁曲线与文字趋势；碧根果90/约93%；稻壳3E98/96及BET1985/1935。芒果79.3%是CE，紫玉米芯循环6 A/g而读出1 A/g，不跨字段套用。

入口：本批《文献导航.html》《新增50篇_清单与下载结果.md》；全局《全部需下载文献与用途.md》《全部待补资料_完整DOI.txt》。机器可读逐篇证据在扩搜目录JSON中。原137份资料、共同数据库和输入指纹全部核对未变。ready_for_merge仅代表候选审核资料包可供发起对话合并复核，不表示任一记录已经准入。
'''
(PARENT/'进度与交接_续搜50篇_20261017.md').write_text(handoff,encoding='utf-8')
# Fingerprints cover actual downloaded content, not search-result counts.
sources=[{'path':str(p),'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted((ROOT/'sources').rglob('*')) if p.is_file()]
save(ROOT/'扩搜来源文件指纹.json',sources)
manifest=json.loads((PARENT/'merge_manifest.json').read_text(encoding='utf-8'));manifest.update(ready_for_merge=True,continuation_status='新增50篇及三电极优先方向已完成候选交付；既有20篇保留；待逐记录准入审核',continuation_stats=stats,continuation_audit_path=str(ROOT/'交付核验_扩搜.json'),latest_user_direction='后续优先三电极，双电极和其它资料全部保留',no_database_writes=True,training_admitted=0)
outputs=[]
for p in sorted(PARENT.rglob('*')):
    if p.is_file() and p!=PARENT/'merge_manifest.json' and '__pycache__' not in p.parts:outputs.append({'path':str(p),'sha256':sha(p),'bytes':p.stat().st_size,'role':'staged_literature_or_review_artifact'})
manifest['outputs']=outputs;manifest['manifest_excludes_itself']=True
save(PARENT/'merge_manifest.json',manifest)
print(json.dumps({'stats':stats,'pending_dois':len(pending),'protected_checks':len(protected),'all_protected_unchanged':all(x['unchanged'] for x in protected),'reader_errors':errors,'output_files':len(outputs),'ready_for_merge':True},ensure_ascii=False,indent=2))
