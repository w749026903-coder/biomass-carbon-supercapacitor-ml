"""Receive the user's PDF additions as a separate evidence package; never update a scientific DB."""
from pathlib import Path
import json,hashlib,shutil,collections
ROOT=Path(__file__).resolve().parents[1];OUT=Path(__file__).resolve().parent
old=ROOT/'同体系文献补充_第二批_20261017'
inv=json.loads((OUT/'initial_inventory.json').read_text(encoding='utf-8'))['records']
# Human-reviewed observations: PDF page numbers include covers and manuscript title pages.
A={
'U001':('excluded_background','10.17756/jfcn.2025-s2-010',[],[1],'食品/生物活性综述，不是EXT_040的蛇瓜碳电极论文。DOI按首页链接纠正，不能把紧接其后的Journal字母J拼进DOI。'),
'U002':('missing_main_received','10.1039/d4ta02115k',['B2_002'],[7,17,19],'RSC Accepted Manuscript，完整正文非出版社排版版。三电极OPBNP：93.6%/10000圈/5 A/g；双电极器件：97.61%/10000圈/5 A/g；钠离子电池循环不得混入电容标签。SI Text S1仍需补。'),
'U003':('separate_domain','10.1021/acs.langmuir.6c04300',[],[1,8],'有原创超级电容循环数据：95.6%/10000圈与器件95.82%/5000圈分别记录；酚醛树脂前驱体，不按生物质碳主队列准入。'),
'U004':('excluded_other_application','10.21625/resourceedings.v3i3.1035',[],[1],'研究竹炭微生物燃料电池，不提供本项目所需超级电容循环保持率标签。'),
'U005':('missing_main_received','10.1002/slct.74152',['EXT_044'],[1,10,11],'桉树种子碳，双电极器件76.5%/10000次充放电；电流和质量分母须再定位，不将倍率测试电流冒充循环电流。'),
'U006':('missing_main_received','10.1021/acsaem.5c00606',['EXT_045'],[1,2,17,18],'ACS稿件版，PDF正文未印自身DOI；题名、作者与ACS正式题录一致。双电极器件98.2%/10000圈/10 A/g；三电极倍率66.0%@50 A/g不是循环标签。需SI。'),
'U007':('missing_main_received','10.1002/est2.70057',['EXT_046'],[1,10,11],'芋头皮CEPAC 1:1双电极器件98.4%/10000圈；正文报告的1 A/g电容/能量密度条件不能直接继承为循环条件。'),
'U008':('existing_archived_copy','10.1016/j.biombioe.2025.108852',['SRC102'],[1],'已有SRC102正文。与缺件N007（10.1016/j.electacta.2025.145880）题名和DOI均不同，不能解除N007缺件。此次不重新裁定SRC102循环字段。'),
'U009':('existing_archived_copy','10.1016/j.jics.2025.102074',['SRC127','N009'],[1,8],'狗尾草PVA/H2SO4凝胶双电极正文，89%/10000圈已经有记录；此次提供的是正文，不是待补SI，SI缺件仍保留。'),
'U010':('missing_main_received','10.1021/acsaem.5c00130',['EXT_042'],[7,8,9],'龙眼壳N3OPC-3：三电极CV在200 mV/s下10000圈后93.5%；双电极GCD在20 A/g下10000圈后89%。两个标签和方法必须隔离，需SI。'),
'U011':('new_biomass_candidate','10.1021/acsanm.4c04517',[],[2,10,11],'木质素火焰氧化碳，双电极/1 M Na2SO4/5 A/g/10000圈。正文与摘要96.85%，结论96.48%，且样品缩写F-ANFC/F-ACNF混写；保留冲突，不任选数值、不准入。论文声明SI。'),
'U012':('excluded_background','10.1201/9781003633808-14',[],[1],'Organic Waste Conversion for the Supercapacitor书章，汇总前人结果；只能追溯原研究，不能按新独立实验样本计数。'),
'U013':('missing_main_received','10.1039/d4ya00076e',['B2_003'],[8,10],'大豆秸秆SSC2-0.6：三电极93.18%/2000圈/5 A/g；双电极96.6%/14000圈/10 A/g。不可合为一个端点；需ESI。'),
'U014':('missing_main_received','10.1155/2024/4961636',['EXT_035'],[1,13],'花生油饼HPC-P8双电极93.8%/5000圈/10 A/g；电解液1 M Na2SO4，器件窗口0–2.0 V；质量分母仍须审查，需SI。'),
'U015':('missing_main_received','10.1088/1402-4896/ae73bc',['EXT_039'],[2,13],'花生壳PPC-500-1-1h双电极99.30%/20000圈/10 A/g。首页为IOP封面，不代表仅摘要；正文至结论和参考文献可读。'),
'U016':('missing_main_received','10.1002/ente.202201281',['EXT_036'],[7,8],'地肤KAC-5：三电极90.31%/10000圈与双电极88.83%/10000圈分开。6 M KOH；器件正文讨论1.2 V，不从单电极窗口推断；需SI核循环电流等。'),
'U017':('missing_main_received','10.1039/d6nj00244g',['N003'],[1,2,5,6,7],'过期蜂蜜CMC三电极GCD循环：摘要10000圈，正文/图4/结论15000圈；正文为超过96.7%，不是精确96.7%。保留冲突；正文涉及Co/CoO/Co2+，材料是否允许进入纯碳队列待审；需SI。'),
'U018':('new_biomass_candidate','10.2174/0124055204420251250827064022',[],[1,2,5],'木质素磺酸钠/GO复合碳LC/rGO：三电极97%/10000圈/5 A/g/6 M KOH，与双电极95%/10000圈分别记录；复合配方与独立性待审。'),
'U019':('missing_main_received','10.1002/est2.70547',['EXT_047'],[1,13],'稻穗RPPAC-0.25-850双电极GCD88%/6000圈/10 A/g。循环后的49%为能量密度保持、141%为功率密度变化，不能当电容保持率。'),
'U020':('excluded_background',None,[],[1,3],'Sustainable Materials in Supercapacitors图书/预览节选，52页；不是一篇新独立原始实验论文，不据综述表格复制训练标签。'),
'U021':('new_biomass_candidate','10.1002/slct.202506886',[],[1,10],'榛子壳ACA-US，三电极/3 M KOH，约85%/2000圈/10 A/g；近似值不当精确值，循环电流分母和重复关系待审。'),
'U022':('separate_domain','10.1002/est2.540',[],[1,9],'柚木碳ATC2锌离子混合超级电容器102.8%/10000圈/10 A/g；Zn电极混合储能旁系，不混入对称碳EDLC主队列。'),
'U023':('separate_domain',None,[],[1,2,15,18],'带SSRN预印本水印的TiO2/PVA-NaOH凝胶器件稿件，约100%/5000圈/10 A/g。未核得自身DOI，留空；79.25%是倍率保持，不是循环保持。凝胶电解质旁系，不并入普通水系生物质碳主队列。'),
'U024':('missing_main_received','10.1021/acssusresmgt.3c00028',['EXT_050'],[1,10,11],'沉香叶ALPC-800：三电极在0.5 M H2SO4及0.5 M Na2SO4各100%/2000圈/10 A/g；双电极91%/6000圈，摘要写1 A/g而正文/图8/结论写10 A/g，保留冲突。需SI。'),
'U025':('existing_archived_copy','10.1007/s40243-026-00393-3',['SRC120'],[1,16],'已有SRC120的Article in Press正文，双电极79%/4500圈/5 A/g；不计新论文，此次不重审其数据库字段。'),
'U026':('existing_archived_copy','10.1038/s41598-026-63280-x',['SRC121'],[1,7],'已有SRC121正文；循环图6a为1 M KOH，83.3%/2000圈/10 A/g，不能绑定到另做的3 M KOH测试；不计新增论文。')}

def write(p,obj):p.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8',newline='\n')
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
records=[]
for x in inv:
 group,doi,ids,pages,note=A[x['id']];p=Path(x['original_path'])
 if sha(p)!=x['sha256']:raise RuntimeError('User input changed: '+x['id'])
 y={**x,'doi':doi,'doi_url':('https://doi.org/'+doi) if doi else None,'classification':group,'related_existing_ids':ids,'pdf_evidence_pages':pages,'review_note':note,'training_admitted':False,'independent_materials_finalized':False,'current_density_mass_denominator_finalized':False,'repository_pdf':None}
 if not group.startswith('excluded_'):
  dst=OUT/'pdfs'/group/(x['id']+'.pdf');dst.parent.mkdir(parents=True,exist_ok=True)
  if dst.exists() and sha(dst)!=x['sha256']:raise RuntimeError('Do not overwrite differing copy')
  if not dst.exists():shutil.copyfile(p,dst)
  if sha(dst)!=x['sha256']:raise RuntimeError('Copy mismatch')
  y['repository_pdf']=dst.relative_to(ROOT).as_posix()
 if x['id']=='U006':y['identity_verification']={'method':'Exact title and authors in user manuscript matched against ACS primary bibliographic page','url':'https://pubs.acs.org/aaemcq/article/8/12/8100/3627199/Enhanced-Supercapacitance-Performance-of','publisher_doi':'10.1021/acsaem.5c00606','version':'manuscript; not claimed to be Version of Record'}
 if x['id']=='U023':y['identity_verification']={'method':'Title and authors on user-provided SSRN manuscript; own DOI not established','lead_url':'https://papers.ssrn.com/sol3/papers.cfm?abstract_id=7354344','lead_page_access':'not_accessible_via_web_tool; do not infer DOI'}
 records.append(y)
counts=dict(collections.Counter(x['classification'] for x in records));write(OUT/'核验记录_26份.json',{'date':'2026-10-18','records':records,'counts':counts,'scientific_database_modified':False,'training_admitted':0})
new={i:x for x in records if x['classification']=='missing_main_received' for i in x['related_existing_ids']}
old50=json.loads((old/'定向扩搜40至60篇_20261017/新增50篇_逐篇数据与获取状态.json').read_text(encoding='utf-8'))['records'];avail=[]
for x in old50:
 uid=x['temporary_id'];y={'id':uid,'doi':x['doi'],'previous_main_available':bool(x['complete_main_files']),'previous_main_files':x['complete_main_files'],'user_addition':new.get(uid,{}).get('repository_pdf'),'main_available_now':bool(x['complete_main_files']) or uid in new}
 avail.append(y)
assert sum(x['main_available_now'] for x in avail)==43
write(OUT/'新增50篇_正文可用状态更新.json',{'scope':'Availability overlay only; original scientific record unchanged','records':avail,'main_available':43,'main_missing':7,'training_admitted':0})
needed=json.loads((old/'全部需下载资料_逐项用途.json').read_text(encoding='utf-8'))['records']
remaining_main=[x for x in needed if x['id'] not in new and '正文' in x['needed'] and x['id'] not in ['R111','SRC035','N009/SRC127']]
assert len(remaining_main)==13
siids=['B2_002','B2_003','N003','EXT_035','EXT_036','EXT_042','EXT_045','EXT_050','N009/SRC127'];si=[x for x in needed if x['id'] in siids]
assert len(si)==9
existing_si=[];siroot=ROOT/'循环稳定性数据库_v0.3_数据库优化_20261017/第三轮_逐条准入闭环_20261017/external_sources'
for ident in ['R111','SRC035']:
 ps=[p for p in siroot.glob(ident+'*') if p.is_file() and p.suffix.lower() in ['.pdf','.docx','.zip']]
 if not ps:raise RuntimeError('Cannot confirm already acquired SI '+ident)
 existing_si.append({'id':ident,'files':[p.relative_to(ROOT).as_posix() for p in ps]})
write(OUT/'待补资料_更新.json',{'scope':'Original 28 DOI task list only; no claim that all unmentioned SI does not exist','missing_main':remaining_main,'main_received_but_declared_SI_missing_or_existing_SI_only_task':si,'already_acquired_in_database_round3':existing_si,'new_candidates_not_yet_in_formal_download_queue':['U011','U018','U021'],'no_SI_claimed_obtained_by_user_addition':True})
for name,rows in [('仍缺正文_完整DOI.txt',remaining_main),('仍需SI_完整DOI.txt',si),('原目标仍需下载_全部DOI.txt',remaining_main+si)]:
 (OUT/name).write_text('\n'.join(dict.fromkeys(x['doi'] for x in rows))+'\n',encoding='utf-8',newline='\n')
lines=['# 用户补充PDF核验（2026-10-18）','','本次只核对D:/文献根目录用户新增的26份PDF，原件保持原位；未重排原126篇分类目录。22份与超级电容研究/旁系有关的PDF制作逐字节相同的仓库副本，4份不适用资料仅保留核验记录、文本和首页核查图，其原件仍在D:/文献。','','## 结果','','- 补齐既有目标正文12篇：新增50篇中的9篇、上轮20篇中的2篇及N003。50篇的正文可用状态由34篇变为43篇，其中EXT_045为稿件版；仍缺7篇。B2_002为Accepted Manuscript。','- 已归档论文对应的正文4份，不计新篇数；其中狗尾草待补的是SI，正文副本不能解除SI缺口。','- 额外取得生物质碳原始实验候选3篇：U011木质素、U018木质素磺酸钠/GO、U021榛子壳。只暂存，与正式126篇、前批9篇及20/50篇受审清单未发现DOI重复；材料/曲线独立性未终审，未穷尽历史检索池。','- 另保留3份旁系原创实验：合成酚醛树脂、锌离子混合器件、凝胶电解质预印本；未混入主队列。','- 食品综述、微生物燃料电池、综述书章和图书节选4份不能作为本项目新增独立循环实验数据。','- 本次补充未取得独立SI文件。原28项任务中仍缺正文13个DOI，另9个已有目标的已声明/待补SI仍缺。R111、SRC035的SI已在第三轮取得，不重复索要。','- 正式归档126篇、已有数据库与冻结结论不变；新增训练准入0，科学合并0，研究拟合0。','','## 关键误配和冲突','','1. U001蛇瓜食品综述不能替代EXT_040（10.1002/cnma.202400112）。','2. U008玉米秸秆Fenton论文为SRC102（10.1016/j.biombioe.2025.108852），不是N007（10.1016/j.electacta.2025.145880）。','3. U010龙眼壳的三电极93.5%是CV循环，双电极89%是GCD循环，不混用。','4. U017蜂蜜摘要10000圈与正文/图4/结论15000圈冲突；超过96.7%是下限。CMC涉及Co/CoO，是否符合纯碳范围仍须复核。','5. U024沉香叶双电极6000圈/91%的循环电流，摘要1 A/g，正文/结论10 A/g；原文冲突保留。','6. U011木质素摘要/正文96.85%，结论96.48%，样品缩写亦有混写，暂不裁定单一标签。','','## 可打开的资料与逐篇结论','','页码均为PDF物理页（包含封面和稿件题名页），不是印刷页码。报告提供原文已报值作定位线索，尚未逐条裁定质量分母、电压协议、材料批次独立性或训练用途。','','|编号|DOI/身份|处理|原始数据与限制|','|---|---|---|']
labels={'missing_main_received':'补齐正文','existing_archived_copy':'已有论文正文','new_biomass_candidate':'新候选待审','separate_domain':'旁系保留','excluded_background':'背景/综述','excluded_other_application':'应用不符'}
for x in records:
 doi=f'[{x["doi"]}]({x["doi_url"]})' if x['doi'] else '自身DOI未核得'
 link='[PDF]('+str(Path(x['repository_pdf']).relative_to(OUT.relative_to(ROOT)).as_posix())+')' if x['repository_pdf'] else '原件留在D:/文献'
 lines.append(f'|{x["id"]}|{doi}|{labels[x["classification"]]}；{link}|PDF页{",".join(map(str,x["pdf_evidence_pages"]))}：{x["review_note"]}|')
lines+=['','## 仍缺正文（13个DOI）','','以下为原28项清单的更新视图；不覆盖旧历史清单。']
for x in remaining_main:lines.append(f'- {x["id"]}：[{x["doi"]}](https://doi.org/{x["doi"]})；{x["title"]}')
lines+=['','## 已有正文但仍需SI（9个DOI）','','“未取得SI”与“原文未报告”不同。桉树/芋头/花生壳/稻穗正文未定位明确SI声明时不自动宣告不存在SI；后续字段审核再核。']
for x in si:lines.append(f'- {x["id"]}：[{x["doi"]}](https://doi.org/{x["doi"]})')
lines+=['','## 交接','','- `核验记录_26份.json`：身份、原件哈希、仓库副本和逐篇证据页。','- `新增50篇_正文可用状态更新.json`：只叠加正文获取状态，不修改历史科学记录。','- `待补资料_更新.json`及3个DOI纯文本：分开列缺正文与缺SI。','- `evidence_images/`：26份首页联系表及5份关键页的渲染核查。','- U006稿件的DOI由[ACS正式题录](https://pubs.acs.org/aaemcq/article/8/12/8100/3627199/Enhanced-Supercapacitance-Performance-of)与题名/作者匹配；U023仅有SSRN稿件身份线索，未猜测自身DOI。','- 根入口已补充第四轮及只读审计链接；本次不代替数据库任务修复审计问题、修订科学合同或解除冻结。','- 下次任务从本核验包接续，不将旧28项快照当作当前待下载清单。']
(OUT/'核验报告与交接.md').write_text('\n'.join(lines)+'\n',encoding='utf-8',newline='\n')
print(json.dumps({'classifications':counts,'main_received':12,'main_in_50_now':43,'remaining_main_all_original_targets':len(remaining_main),'SI_targets_still_missing':len(si),'copied_pdfs':sum(x['repository_pdf'] is not None for x in records)},ensure_ascii=False))
