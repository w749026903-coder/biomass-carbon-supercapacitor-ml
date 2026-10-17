import copy, difflib, hashlib, io, json, pathlib, re, xml.etree.ElementTree as ET
from pypdf import PdfReader
from collect_batch1 import ROOT, BASE
def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
acq=load(ROOT/'第一批获取原始记录.json')
old=load(BASE/'训练适用性审核_20261016/逐份训练用途审核.json')
locations=load(BASE/'文献整理_20261017/当前唯一文献位置.json')
active=[x for x in old if x.get('in_active_library')]
titles={x['id']:x['title'] for x in active}
def norm(t):return re.sub(r'[^a-z0-9]+','',t.lower())
facts={
'N001':dict(short='稻壳碳：电极质量配比',evidence='正文p2-4、图2/3：RHC，6 M KOH，1 A/g，0-1 V。质量比1时2000次约90.1%、10000次27.9%；质量比2时10000次96.4%。同一材料，不能算成多个独立材料。',url='https://pubs.rsc.org/en/content/articlehtml/2025/ra/d5ra03028e',caveat='质量比1.25、1.5也有曲线，尚未读数；质量不平衡的器件单列。需追查作者前作RHC的样品/曲线复用。',full='PDF正文及8页SI已保存'),
'N002':dict(short='棉浆板碳：50000次循环',evidence='公开全文Fig5h：MHDHPC-600对称器件，6 M KOH，10 A/g，50000次92%；SI S2/S7/S8能配对负载、XPS和孔结构。',url='https://pubs.rsc.org/en/content/articlehtml/2026/ra/d5ra08165c',caveat='正文已保存完整XML和可读TXT，未取得排版PDF；放大制备样品有倍率数据，不能自动认为各有长期循环标签。',full='完整正文XML/TXT及12页SI已保存；排版PDF未取得'),
'N003':dict(short='过期蜂蜜微波碳',evidence='出版社摘要：CMC，三电极，2 M H2SO4，10 A/g，10000次保持率超过96.7%。',url='https://pubs.rsc.org/en/content/articlelanding/2026/nj/d6nj00244g',caveat='仅核到出版社摘要与题录；超过96.7%是下限，不能写成精确点值。正文及SI尚未取得。',full='需要用户补正文及SI'),
'N004':dict(short='甘蔗渣碳：原碳和活化碳对照',evidence='正文p15-16、Fig12：两电极SCB/SCB-A，10000次，图注明确5 A/g；正文分别约93.89%与超过98.43%。',url='https://www.mdpi.com/2079-4991/15/13/1028',caveat='p4方法写2 M KOH，p14-15器件段写3 M；p3还写94.7%而后文为98.43%。条件和激活样品标签归属须澄清，当前不进入干净候选池。',full='PDF正文及5页SI已保存'),
'N005':dict(short='鹅毛与松木屑共碳化',evidence='正文p8、Fig5f：M-3-25三电极，6 M KOH，10 A/g，10000次91.39%。不是两电极器件的循环值。',url='https://www.mdpi.com/1420-3049/30/1/26',caveat='正文明确讨论样品重金属参与；单列含金属/残留待核组，不能当成纯碳直接拼接。2024-12-25上线，编入2025年第30卷。',full='PDF正文及3页SI已保存'),
'N006':dict(short='香蕉叶多孔碳',evidence='出版社摘要与Highlights：BLAC器件在6 M KOH、0-2 V条件下，5000次保持96%。',url='https://www.sciencedirect.com/science/article/abs/pii/S096195342500515X',caveat='循环电流、具体样品配对及所报0-2 V窗口需正文核实；未据摘要补齐所有字段。',full='需要用户补正文及SI（如有）'),
'N007':dict(short='Fenton预处理生物质碳',evidence='出版社摘要：优化碳比表面积2801 m²/g；对称器件70000次保持99%。',url='https://doi.org/10.1016/j.electacta.2025.145880',caveat='摘要同时提3 M KOH与1 M Na2SO4，不能直接把某个电解液绑定到70000次标签；循环电流、最终金属残留待正文。与已有SRC102题名和DOI不同，底层材料独立性仍待核。',full='需要用户补正文及SI'),
'N008':dict(short='萝卜熔融碱活化碳',evidence='出版社和作者学校仓储：原料湿萝卜，优化样品700°C；20000次保持92.6%，比表面积1172 m²/g。',url='https://www.sciencedirect.com/science/article/pii/S1385894725022089',caveat='学校公开仓储列有正文和SI；本机正文直链握手失败、仓储入口403。尚未核清循环体系、电流，不标成已读全文。',full='需要用户补正文及SI；公开仓储可优先尝试'),
'N009':dict(short='狗尾草秆柔性碳器件',evidence='作者学校PDF正文p6/p8、Fig10B：SVS-900，PVA/H2SO4凝胶，两电极，10 A/g，10000次89%。',url='https://ticnn.tju.edu.cn/dfiles/12783/images/publication/2025/jw.pdf',caveat='凝胶器件单列；SI未取得，正文BET转述需SI复核，不混入纯水溶液主体系。',full='10页PDF正文已保存；SI待补'),
}
new=[]
for r in acq:
 ident=r['id'];f=facts[ident]
 if ident=='N008':title='Molten base carbonisation and activation of non-lignin-rich biomass into hierarchically porous carbon with surface-rich functionalities for supercapacitor electrodes'
 else:title=r['crossref']['title'][0]
 doi=r['doi'];scores=sorted([(difflib.SequenceMatcher(None,norm(title),norm(t)).ratio(),k) for k,t in titles.items()],reverse=True)
 exact=[x['id'] for x in active if (x.get('doi') or '').lower()==doi]
 assert not exact
 row=dict(id=ident,title=title,doi=doi,doi_url='https://doi.org/'+doi,year=(r.get('crossref',{}).get('published') or {}).get('date-parts',[[2025]])[0][0],doi_verified=True,doi_verification=('Crossref canonical DOI and title + publisher/primary evidence' if r.get('crossref') else 'Publisher ScienceDirect DOI/title + author institution repository'),duplicate_current_library=False,duplicate_doi_ids=exact,normalized_title_exact_matches=[k for k,t in titles.items() if norm(t)==norm(title)],nearest_title_match={'id':scores[0][1],'similarity':round(scores[0][0],3)},eligible_for_database=False,independence_finalized=False,**f)
 assert not row['normalized_title_exact_matches']
 row['files']=[]
 for p in sorted((ROOT/ident).glob('*.pdf')):
  raw=p.read_bytes();reader=PdfReader(io.BytesIO(raw));t=' '.join((x.extract_text() or '') for x in reader.pages);role='main' if p.name.startswith('正文') else 'supplement'
  row['files'].append({'path':str(p),'role':role,'bytes':len(raw),'pages':len(reader.pages),'sha256':hashlib.sha256(raw).hexdigest(),'valid_pdf_header':raw.startswith(b'%PDF-'),'doi_found':doi in re.sub(r'\s+','',t).lower(),'identity_review':'Main title/DOI checked; SI title and authors matched to main and repository package'})
 row['fulltext_xml_path']=str(ROOT/ident/'公开全文.xml') if (ROOT/ident/'公开全文.xml').exists() else None
 row['main_obtained']=bool(row['fulltext_xml_path'] or any(x['role']=='main' for x in row['files']))
 new.append(row)
(ROOT/'第一批文献清单_核验后.json').write_text(json.dumps(new,ensure_ascii=False,indent=2),encoding='utf-8')
(ROOT/'全部新增DOI_纯文本.txt').write_text('\n'.join(x['doi'] for x in new)+'\n',encoding='utf-8')
needs=[x for x in new if not x['main_obtained']]
(ROOT/'需用户下载DOI_纯文本.txt').write_text('\n'.join(x['doi'] for x in needs)+'\n',encoding='utf-8')

# Newly read endpoints are kept apart from the existing 81-row v2 snapshot.
def rec(ident,sample,system,n,ret,rel='eq',**kw):
 p=next(x for x in new if x['id']==ident)
 return dict(record_id=ident+'_CY'+str(1+sum(x['paper_id']==ident for x in endpoints)).zfill(2),paper_id=ident,doi=p['doi'],study_group=p['doi'],sample=sample,material_id=ident+'::'+sample,system=system,method='GCD',cycle_count=n,retention_pct=ret,retention_relation=rel,eligible_for_database=False,admission_status='new_source_pending_record_audit',independent_material_identity_finalized=False,**kw)
endpoints=[]
common=dict(current_density_A_g=1,electrolyte='KOH',concentration_value=6,concentration_unit='mol/L',voltage_lower_V=0,voltage_upper_V=1,BET_m2_g=3185,O_at_pct=8.54,total_pore_volume_cm3_g=None,capacitance_mass_basis='total_positive_and_negative_electrode_mass',cycle_current_mass_basis='not_separately_defined_for_current_density',normalization_reference='initial_capacitance_reported',evidence_path=str(ROOT/'N001/正文_OA副本.pdf'),pdf_pages=[2,3,4,5])
for n,val,ratio in [(2000,90.1,1),(10000,27.9,1),(10000,96.4,2)]:
 endpoints.append(rec('N001','RHC','2E_symmetric' if ratio==1 else '2E_same_carbon_mass_unbalanced',n,val,rel='approx' if n==2000 else 'eq',cycle_test_id='N001::RHC::ratio'+str(ratio),configuration_id='N001::ratio'+str(ratio),positive_negative_mass_ratio=ratio,positive_loading_mg_cm2=4,conflict=False,material_scope='carbon_candidate',**common))
endpoints.append(rec('N002','MHDHPC-600','2E_symmetric',50000,92,current_density_A_g=10,electrolyte='KOH',concentration_value=6,concentration_unit='mol/L',voltage_lower_V=0,voltage_upper_V=1,voltage_provenance='Fig5b/c and cycling inset Fig5h axis; direct axis reading',BET_m2_g=501,total_pore_volume_cm3_g=0.25,N_at_pct=2.1,O_at_pct=8.8,S_at_pct=1.3,mass_loading_mg_cm2=1.5,mass_loading_relation='approx',evidence_path=str(ROOT/'N002/公开全文.xml'),evidence_locator='main Table1 + Fig5h; SI p2,p7,p8',cycle_test_id='N002::MHDHPC-600::2E',configuration_id='N002::MHDHPC-600::2E',material_scope='carbon_candidate',conflict=False,normalization_reference='initial_Cg216_Fg_reported',cycle_current_mass_basis='not_separately_defined',note='Reported 92%; do not replace with recomputed 200/216. Scaled batches not assumed to have this label.'))
for sample,ret,rel in [('SCB',93.89,'approx'),('SCB-A',98.43,'gt')]:
 endpoints.append(rec('N004',sample,'2E_symmetric',10000,ret,rel=rel,current_density_A_g=5,electrolyte='KOH',concentration_value=None,concentration_reported_conflict={'method_M':2,'device_results_M':3},voltage_lower_V=0,voltage_upper_V=1,evidence_path=str(ROOT/'N004/正文_OA副本.pdf'),pdf_pages=[4,13,14,15,16],material_scope='carbon_candidate_pending_protocol',conflict=True,conflict_note='2 M methods versus3 M device; activated row also has94.7% at p3 whose system attribution remains unresolved.',cycle_test_id='N004::'+sample+'::2E',configuration_id='N004::'+sample+'::2E'))
endpoints.append(rec('N005','M-3-25','3E',10000,91.39,current_density_A_g=10,electrolyte='KOH',concentration_value=6,concentration_unit='mol/L',voltage_lower_V=None,voltage_upper_V=None,evidence_path=str(ROOT/'N005/正文_出版社CDN.pdf'),pdf_pages=[7,8,12],material_scope='metal_containing_or_residual_review',conflict=False,cycle_test_id='N005::M-3-25::3E',configuration_id='N005::M-3-25::3E',note='Fig5f is explicitly a three-electrode test. Metal participation is discussed in paper.'))
endpoints.append(rec('N009','SVS-900','2E_symmetric_gel',10000,89,current_density_A_g=10,electrolyte='PVA/H2SO4',concentration_value=None,voltage_lower_V=None,voltage_upper_V=None,evidence_path=str(ROOT/'N009/正文.pdf'),pdf_pages=[6,8],material_scope='carbon_candidate_gel_separate',conflict=False,cycle_test_id='N009::SVS900::gel',configuration_id='N009::SVS900::gel',note='Electrochemical cycles, distinct from bending test. SI BET not copied without its original table.'))
(ROOT/'新增来源循环候选_单列未并库.json').write_text(json.dumps(endpoints,ensure_ascii=False,indent=2),encoding='utf-8')

summary=load(ROOT/'现有数据补齐/补录统计.json')
md=['# 循环稳定性补资料：第一批交付','日期：2026-10-17（北京时间）。','',
'本批核到9篇新文献，DOI和题名与当前121篇逐项去重，无重复。5篇已取得全文：4篇PDF、1篇完整XML/TXT。另有4篇正文需要你补下载。已下载的资料先放待审区，未搬入D:/文献。',
'4篇新文献各取得1份SI，旧库R103、R106各补到1份SI；共10个有效PDF（4正文+6SI）。N009的SI还没有取得。','',
'“有循环实验”只表示值得继续核录，不代表材料纯度、协议和独立性已通过审核。N004有电解液浓度及标签归属问题；N005涉及重金属；N009为凝胶体系。','',
'## 已下载或已取得完整正文','',
'| 编号 | 文献 | DOI | 文件情况 |','|---|---|---|---|']
for x in new:
 if x['main_obtained']:md.append(f"| {x['id']} | {x['short']} | [{x['doi']}]({x['doi_url']}) | {x['full']} |")
md+=['','N002已可核读全文，不需要你重新找正文；如方便，可补排版PDF。原文XML和可读TXT均在N002文件夹。','',
'## 需要你补下载的4篇正文','',
'纯DOI见同目录《需用户下载DOI_纯文本.txt》。优先下载正文和SI；不要重复下载已在本地的R103、R106正文。','']
for x in needs:
 md += [f"### {x['id']} {x['title']}",'',f"DOI：[{x['doi']}]({x['doi_url']})。",f"[出版社/原始入口]({x['url']})。",f"已核到的依据：{x['evidence']}",f"待补：{x['full']}。{x['caveat']}",'']
md += ['N008另有[作者学校公开仓储](https://nottingham-repository.worktribe.com/output/46459620)，页面列出正文与SI，可先尝试。','',
'## 全部9篇完整题名及核读限制','']
for x in new:
 md += [f"**{x['id']} {x['title']}**",f"DOI：[{x['doi']}]({x['doi_url']})；{x['full']}。",x['evidence'],f"需保留的限制：{x['caveat']}",'']
md += ['## 现有论文补到了哪里','',
'保留原81行快照和原工作簿，本轮另存《现有数据补齐/循环稳定性逐记录候选_v2.json》。补了6篇、7个暂定材料、8条已有终点的29项字段及来源/审核说明；没有增加旧库终点数。',
'', '| 来源 | 这次补录 | 尚未解决 |','|---|---|---|',
'| R012 | OPL_KOH12：BET1840.51 m²/g、总孔体积1.16 cm³/g、单电极约2 mg/cm²；配到原有两条记录 | 仍只有100次短程测试 |',
'| R093 | PR-2器件电压0-1.2 V；单电极活性质量的电容公式 | 循环电流质量分母、基线仍需终审；108.8%原值保留 |',
'| R091 | BET1098.07、XPS氮0.84 at%、氧6.72 at%；工作电极负载4 mg/cm² | 表I孔体积0.68的单位印为m³/g，留原值待核；循环电流未补造 |',
'| R103 | 新SI确认电容按单电极LAC质量计；图7b电压0-1 V | 总孔体积仍未核到，不填0 |',
'| R106 | 新SI的FMCA循环前EDS组成单列；原文1.3-2.8 mg负载范围单列 | Si为11.68 at%，需核残留；EDS不冒充XPS；循环电流仍未知 |',
'| R111 | 对称器件每个电极2 mg活性物质；电容公式质量定义 | 电解液浓度、电压和循环电流分母仍需查SI，不从引用文献借值 |',
'',
'按与上一版相同的“字段已配对”口径：次数/保持率/电流/电解液浓度仍为18终点、15材料、15篇；再加BET和电压由9终点变为11终点（10材料、10篇）；再加总孔体积由5终点变为6终点（5材料、5篇）。这些是配对进度，不是质量准入。','',
'新读全文另记8个终点、6个暂定材料编号、5篇来源，保存在《新增来源循环候选_单列未并库.json》。其中稻壳同材料含多个循环节点/器件配比，未重复计材料；其余问题来源保留单列。没有把8个终点当作8个独立样本。','',
'## 复核与下一步','',
'所有PDF检查文件头、可读页数、题名/DOI或SI配对、SHA256。原库121篇正文的SHA256重新核验，结果见《本轮完整性核验.json》。关键表图视觉复核图在《视觉核对》。网络返回403/证书错误或握手失败均如实留在获取日志中，没有关闭TLS或改代理。',
'',
'后续优先补R091的SI与循环电流、R111/R105的SI；继续逐篇核配原候选的基线、质量分母、孔结构及循环前组成。N001四种配比的中间两条曲线还未数字化，不能臆造终点。N004先澄清浓度与94.7/98.43归属，N005核重金属，N009保留凝胶子集。',
'',
'所有记录eligible_for_database仍为false，未训练、未解除旧冻结，未修改/移动/删除原论文，未上传。']
(ROOT/'第一批交付说明.md').write_text('\n'.join(md)+'\n',encoding='utf-8')
print('manifest',len(new),'main obtained',sum(x['main_obtained'] for x in new),'user needs',len(needs),'new endpoints',len(endpoints))
