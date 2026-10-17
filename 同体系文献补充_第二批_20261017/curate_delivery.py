"""Curated staging release. Reads baseline only; never imports into SQLite/library."""
import json,re,hashlib,sqlite3,difflib,html,zipfile
from pathlib import Path
from collections import Counter
from lxml import etree
from pypdf import PdfReader
ROOT=Path(__file__).resolve().parent
PROJECT=ROOT.parent
def save(name,obj): (ROOT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def clean(t):return re.sub(r'\s+',' ',html.unescape(re.sub('<[^>]+>','',t))).strip().rstrip('.')
def nt(t):return re.sub('[^a-z0-9]','',clean(t).lower())
base=read(ROOT/'DOI去重基线.json')['records'];snap=read(ROOT/'基线只读快照.json')
known={x['doi_normalized'] for x in base if x['doi_normalized']}

def m(sample,cycles,value,current,electrolyte,window,location,kind='reported_point',baseline='not_located'):
    return dict(sample=sample,cycles=cycles,retention_percent=value,retention_kind=kind,cycling_current_reported=current,electrolyte=electrolyte,voltage_window=window,location=location,baseline=baseline)
def c(folder,material,prep,characterization,measurements,gaps,priority='P1',domain='aqueous_2E_GCD_candidate',nodes=None):
    return dict(folder=folder,material=material,preparation=prep,pre_cycle_characterization=characterization,measurements=measurements,gaps=gaps,priority=priority,domain=domain,reviewed_node_indices=nodes or [])

items=[
c('L01','SAC，高粱衍生碳','两阶段碳化/活化；具体比例和最终温度待完整正文复核。',{'BET_m2_g':1271,'BET_qualifier':'approximate','pore_volume':'not_located','location':'出版社摘要/§2.1、Fig.4f定位片段'},[m('SAC',10000,97.5,'10 A/g','1 M KOH',None,'出版社器件段Fig.4f；§2.1组装方法')],['仅有出版社摘要和索引展开片段；尚未取得本地完整正文/SI，不冒称全文核查。','窗口、循环电流质量分母、基线定义和前作样品关系未核清。']),
c('L02','OPBNP，橙皮B/N/P掺杂碳','水热掺杂、600 ℃碳化/活化；硼酸和磷酸氢二铵作掺杂剂。',{'BET_m2_g':1774.8,'BET_status':'conflicting','conflicting_BET_m2_g':[774.8,1774.8],'total_pore_volume_cm3_g':0.81,'micropore_volume_cm3_g':0.69,'location':'出版社Table1及正文引言；完整SI待获取'},[m('OPBNP//OPBNP',10000,97.61,'5 A/g','6 M KOH',None,'出版社Fig.4e器件段；98.24%是库仑效率，不能替代标签')],['未取得完整正文/SI；器件循环97.61%与摘要93.6%电极值分开。','BET在引言印774.8、摘要/表1印1774.8，保留冲突，未自动纠正。','质量分母、基线、窗口和独立性待核。']),
c('L03','SSC2-0.6，大豆秸秆碳','600 ℃/3 h预碳化；碳:KOH:KNO3=1:2:0.6，800 ℃/3 h。',{'BET_m2_g':1658.8,'O_at_percent':16.77,'pore_volume':'not_located','location':'出版社摘要/制备段与表征定位片段'},[m('SSC2-0.6',14000,None,'10 A/g','6 M KOH',None,'出版社Fig.8c正文96.94%；摘要96.6%',kind='conflicting_reported_values',baseline='author_initial_in_abstract')],['未取得本地完整正文/SI；96.6%与96.94%两种表述暂不择一。','不能采用Fig.5的三电极2000次93.18%替代器件长期标签。','窗口、质量分母及独立性待核。']),
c('L04','PAC/SAC/LAC，松/云杉/落叶松球果碳','500 ℃/2 h碳化，KOH:碳8:1，850 ℃/3 h活化；循环对应压片路线。',{'materials':[{'sample':'PAC','BET_m2_g':2813,'pore_volume_cm3_g':1.43},{'sample':'SAC','BET_m2_g':3565,'pore_volume_cm3_g':1.88},{'sample':'LAC','BET_m2_g':2981,'pore_volume_cm3_g':1.67}],'location':'XML node46 Table1；原粉/去灰校正值不同，不混用'},[m('PAC',10000,88.31,'3 A/g','6 M KOH',None,'XML node77 Table5；node30方法/80循环段'),m('SAC',10000,93.10,'3 A/g','6 M KOH',None,'XML node77 Table5'),m('LAC',10000,93.53,'3 A/g','6 M KOH',None,'XML node77 Table5')],['同文有机电解液节点只列旁系，不增加独立材料；Table6在node85。','作者明确提及既有松果工作；PAC批次/曲线是否复用待核，文献新不等于所有材料新。','喷涂分散路线另含硅/rGO，不能将该路线材料和循环混入压片数据。','窗口、循环质量分母、基线精确定义待核。'],nodes=[16,18,25,27,29,30,46,77,80,85]),
c('L05','OAC-4-700，土霉素发酵残渣碳','K2CO3温和活化；700 ℃样品，比例代号4。',{'BET_m2_g':948,'N_wt_percent':3.42,'O_wt_percent':14.86,'O_method':'elemental oxygen by subtraction, not XPS at%','pore_volume':'not_located','location':'XML摘要/表征段；SI p5 TableS1'},[m('OAC-4-700//OAC-4-700',10000,97.25,'10 A/g','6 M KOH',None,'XML node55；SI p4 Fig.S3图注及97.25%图中标注')],['SI Fig.S3内嵌potential为−1至0 V，虽然图注明确对称器件，不能径直将负电极电位改录为0–1 V器件窗口。','摘要5.32%损失/94.68%是三电极，不是该器件标签。','质量分母、基线、独立性和制备细节待终审。'],nodes=[20,22,55,60]),
c('L06','GLAC-2，银杏叶碳','H3PO4水热碳化/活化；具体剂量和热程序在全文制备段，尚待字段级复核。',{'BET_m2_g':1133.66,'total_pore_volume_cm3_g':0.42,'micropore_volume_cm3_g':0.105,'location':'XML node34 Table1；N2-BET/DFT/t-plot方法node17'},[m('GLAC-2',10000,98.24,'10 A/g','1 M KOH','0–1.2 V','XML node60/62；Fig.3f',baseline='author_initial; initial activation described, exact reference cycle unresolved')],['三电极SI的98.9%与器件98.24%分开。','SI页脚2022版权不能当正式上线年份；EPMC首发2023-01-10，Crossref为2023。','循环电流分母和前作独立性待核。'],nodes=[17,21,34,51,60,62]),
c('L08','BLC_KOH，榕树落叶碳','700 ℃热化学活化，KOH处理；BLC与BLC_KOH分别保留。',{'BET_m2_g':495.56,'total_pore_volume_cm3_g':0.397,'micropore_volume_cm3_g':0.215,'location':'XML node29/Table1'},[m('BLC_KOH',1000,99.99,'4 A/g','1 M Na2SO4','0–1 V','XML node41/45/50；Fig.8b',kind='approximate_reported')],['满足1000次项目筛查约定，不据此称充分长期稳定。','83.2%是库仑效率；保留作者约数，不写成测量无限精度。','质量分母、归一化基线和独立性未核清。'],nodes=[29,41,45,50]),
c('L09','ALC，Acacia auriculiformis落叶碳','原料与EDTA二钠1:1；450 ℃/30 min预碳化、KOH活化700 ℃/30 min。',{'BET_m2_g':1913,'pore_volume':'not_located','location':'XML摘要/表征段，原始N2表征；不使用比较表他人数据'},[m('ALC',5000,89.3,'5 A/g','1 M H2SO4','0–1 V','XML node19方法/43及Fig.5g',baseline='author_starting_specific_capacitance')],['窗口来自常规GCD共同方法段，循环5 A/g在node43直接报告，仍需协议范围终审。','总孔体积、质量分母和前作独立性尚未完成。'],nodes=[15,19,43]),
c('L10','BAC，欧洲落叶树木碳','热解制备，器件使用BAC；硫/BAC的锂硫电池另列。',{'BET_m2_g':616,'total_pore_volume_cm3_g':0.564,'micropore_volume_cm3_g':0.274,'location':'XML node33'},[m('BAC coin cell',5000,89,'3.33 A/g','EMIMBF4 ionic liquid','0–2.5 V','XML node17/40/43；SI Fig.S8a未取得',kind='approximate_reported',baseline='author_initial_specific_capacitance')],['有机/离子液体旁系，不能直接拼入当前水系条件分布。','印刷IDE的0.75 mA/86.90%和硫复合锂电池不并为本材料的新样本。','SI未获取；质量分母与独立性待核。'],domain='separate_ionic_liquid',nodes=[17,22,33,40,43,46,54]),
c('L11','LP-C，木质素磺酸钠激光碳','石墨箔/聚合物黏附中间层支撑激光碳化；层间组分和取样范围待核。',{'BET_m2_g':None,'SSA_N2_DFT_m2_g':13,'SSA_CO2_DFT_m2_g':504,'pore_volume_N2_cm3_g':0.05,'pore_volume_CO2_cm3_g':0.21,'location':'XML node26；DFT/CO2值不得冒充N2-BET'},[m('LP-C symmetric',20000,81,'2.2 mA/cm²','1 M H2SO4',None,'XML node33/40 Fig.4f；node65组装',baseline='author_initial_capacitance')],['面积电流及多层电极旁系；无可靠负载不换算A/g。','SSA测法不同，不能填成统一BET特征；体相有沿厚度梯度。','循环窗口、SI、材料范围和来源独立性待核。'],domain='separate_areal_current',nodes=[8,26,33,40,65,95]),
c('L13','SPC3，草莓秸秆碳','600 ℃/2 h碳化，KOH:碳3:1，800 ℃/2 h活化。',{'BET_m2_g':2746.5,'total_pore_volume_cm3_g':1.20,'O_at_percent':5.2,'location':'XML表1及XPS段；均为循环前；循环后SEM不作为输入'},[m('SPC3//SPC3',10000,70.1,'10 A/g','6 M KOH','0–1.2 V','XML node61；Fig.9e')],['摘要95.6%在电极/三电极段，不能用于器件。','Fig.9图注写asymmetric，正文明确同材料对称；Table3本工作95.3%又不同。保留体系命名/标签范围冲突，不准入。','循环后孔坍塌SEM只解释衰减，不作为预测特征。','电流分母、基线和独立性待核。'],nodes=[1,49,57,61,62,68]),
c('L14','CS-800，玉米秸秆直接碳化','800 ℃/2 h、Ar；后经10 wt% HCl除灰；不用未除灰材料值。',{'BET_m2_g':7.8495,'total_pore_volume_cm3_g':0.0216,'micropore_volume_cm3_g':0.0011,'location':'XML node129 Table1；循环前除灰CS-800'},[m('CS-800//CS-800',30000,93.75,'2 A/g','1 M KOH','0–1.5 V','XML node47/48；Fig.5e',kind='approximate_reported')],['低BET原值保留，不按预期改写成千位数。','Fig.5e含多条散点轨迹，作者约93.75%保留为约数，单曲线身份与基线须终审。','质量分母、独立性待核。'],nodes=[17,18,19,47,48,129]),
c('L15','HPC-KCO，琼脂糖碳','琼脂糖/K2CO3/KOH冻干后900 ℃/2 h碳化。',{'BET_m2_g':None,'pore_volume':'not_located','location':'正文有N2表征和SI TableS2，字段值未完成核配'},[m('HPC-KCO SSC at −60°C',10000,80,'2 A/g','TEABF4 in MPN; concentration not_located','0–2.5 V','XML node18/46；SI Fig.S7未获取',baseline='author_initial'),m('HPC-KCO SSC at 100°C',10000,80,'20 A/g','TEABF4 in MPN; concentration not_located','0–1.5 V','XML node18/52；Fig.7d',baseline='author_initial')],['有机/宽温域器件旁系；两个温度测试仍是同一材料。','Zn//HPC的88%和282→270不属于该SSC；不凭相减纠正原文。','浓度、SI和电流分母未核，温度必须作为条件保留。'],domain='separate_organic_temperature',nodes=[14,18,20,45,46,52]),
c('L16','SE_GLC，田菁衍生碳','0.5 M HNO3、220 ℃/8 h水热，KOH:碳1:1、800 ℃/1 h。',{'BET_m2_g':None,'pore_volume':'SI TableS1 acquired; not yet field-paired','Fe_at_percent':0.02,'Si_at_percent':0.08,'location':'XML node39 XPS；SI已取得'},[m('SE_GLC//SE_GLC',1000,84.05,'0.1 A/g','12 m NaNO3 (molality; not 12 M)','0–1.9 V','XML node49/51/53')],['正文检出Fe及可能Fe3C赝电容，需判定最终材料范围；不按痕量比例设通用阈值。','molality与molarity严格区分；不能把12 m录成12 M。','SI Fig.S18的1 m NaNO3约72.58%暂不单独计终点，次数/协议待核。','质量分母、基线和独立性待核。'],domain='hold_material_scope',nodes=[16,18,32,39,46,49,51,53]),
c('L18','CAC700-4，玉米芯碳','KOH活化700 ℃样品；正文制备段与SI结合，比例4需终审释义。',{'BET_m2_g':1945.70,'total_pore_volume_raw':0.9812,'micropore_volume_raw':0.9122,'pore_volume_unit_raw':'m³/g','pore_volume_status':'unit_conflict_no_conversion','location':'XML node68 Table1原表头m³/g，不自行改cm³/g'},[m('CAC700-4//CAC700-4',10000,95.5,'10 A/g','6 M KOH','0–1 V','XML node24 Fig.7d；SI p1与Fig.7b视觉核对')],['与R103作者高度重叠，原料为玉米芯而R103为木质素；暂未发现同材料证明，仍须批次/曲线排查。','孔体积单位冻结，不按数量级自动修。','循环分母、基线和独立性待核。'],nodes=[14,24,68]),
c('L20','NSOC-800，柚子皮自掺杂碳','原料与KOH一步活化；800 ℃。',{'BET_m2_g':1267.913,'total_pore_volume_cm3_g':0.189,'location':'XML node17；EDS wt%与XPS原子百分比区分'},[m('NSOC-800//NSOC-800',5000,None,None,'6 M KOH','0–1.2 V','XML node22及Fig.4d：仅给平均每圈衰减0.0038%',kind='endpoint_not_explicit')],['90.1%/5000次/1 A/g是三电极Fig.3，不搬到器件。','器件只有平均每圈衰减描述；不机械乘5000生成81%训练标签。','需图读数方案或明确终点及循环电流；分母/基线/独立性未核。'],'P2',nodes=[17,20,21,22]),
c('L21','CSAC，椰壳碳','KOH一步活化800 ℃/2 h；CSC对照和CSAC分开。',{'BET_m2_g':2228,'total_pore_volume_cm3_g':1.07,'micropore_volume_cm3_g':0.64,'O_at_percent':11.92,'location':'XML node14/17 Table1；循环前N2与XPS'},[m('CSAC symmetric',10000,92.09,'10 A/g','6 M KOH','0–1.0 V','XML node23/27；Fig.6d明确标92.09%')],['93.04%是库仑效率；93.81%属于锌离子混合器件，不移用。','SI与正文公式中的总质量定义不能直接认证循环电流分母。','基线和跨论文样品关系仍待核。'],nodes=[14,17,23,26,27,30,45,48]),
c('L22','F-A-BLGR-PC，板蓝根药渣碳','白腐菌预处理、碳化与活化；三种处理组分别保留。',{'BET_m2_g':898,'total_pore_volume_cm3_g':0.97,'micropore_volume_cm3_g':0.38,'location':'XML node33 Table1'},[m('F-A-BLGR-PC (system unresolved)',20000,100,'5 A/g','conflicting: abstract 1 M Na2SO4; Fig.5 caption 6 M KOH',None,'XML node1 vs node49/50/52，Fig.5F',kind='near_100_qualitative')],['摘要把循环归于两电极1 M Na2SO4，但Fig.5F所在整图图注明确6 M KOH电极，正文段也接在三电极分析。','没有足够证据将该曲线确定为对称器件；不计已核同体系来源。','near/no obvious decay不能录为精确100.00%；保留范围与协议冲突。'],'P2',domain='hold_system_attribution',nodes=[1,20,21,23,33,49,50,52]),
c('L24','LSB-AC，荔枝种子CO2活化碳','700 ℃炭样筛选后CO2活化；最终活化热程序待全文。',{'BET_m2_g':None,'pore_volume':'not_located','location':'出版社仅确认开展BET/XPS等表征，数值待正文'},[m('LSB-AC symmetric',10000,92,'5 A/g','1 M H2SO4',None,'出版社Highlights为92%；摘要仅above90%',kind='reported_in_highlights')],['只核到官方摘要/Highlights/结论片段；尚未全文核查。','摘要above90%与Highlights92%保留不同精度，不冒称全文一致。','循环窗口、材料配对、分母/基线/独立性待核。']),
c('L30','CS-800，小麦秸秆活化碳','小麦秸秆/KOH共热解；不能与B2_012玉米秸秆CS-800按同名合并。',{'BET_m2_g':None,'pore_volume':'not_located','location':'正文p3 Fig.3有孔结构；2210 m²/g属于CS-700，不能搬给CS-800'},[m('CS-800 symmetric',20000,96.94,'1 A/g','6 M KOH','0–1 V','正文p6 §3.2；p7 Fig.5h/d，循环负载2.6 mg/cm²',baseline='author_initial_capacity')],['循环图明确2.6 mg/cm²；正文7.1 mg/cm²是另项倍率/负载实验，不借标签。','正文未定位该样品精确BET/孔体积，保留not_located。','质量分母、基线可比性及独立性未核。'],nodes=[]),
]

records=[];mapping={}
for i,x in enumerate(items,1):
    folder=x.pop('folder');ident=f'B2_{i:03}';mapping[folder]=ident;d=ROOT/'sources'/folder
    crpath=d/'crossref.json';ep=read(d/'open_record_access.json');em=ep.get('epmc_record',{})
    cr=read(crpath).get('message',{}) if crpath.exists() else {}
    doi=(cr.get('DOI') or em['doi']).lower().strip();assert doi not in known
    title=clean((cr.get('title') or [em['title']])[0]);authors=[clean(' '.join([a.get('given',''),a.get('family','')])) for a in cr.get('author',[])] or em.get('authorString','').split(', ')
    dates=cr.get('published-online',cr.get('published',{})).get('date-parts',[[int(em.get('pubYear',2023))]])[0]
    year=dates[0];first=em.get('firstPublicationDate') or '-'.join(f'{n:02}' if j else str(n) for j,n in enumerate(dates));assert 2023<=year<=2026
    if folder=='L01':first='2023-11-22' # Publisher first-online date; journal issue year remains 2024.
    matches=sorted(({'id':b.get('id'),'title':b.get('title'),'similarity':round(difflib.SequenceMatcher(None,nt(title),nt(b.get('title',''))).ratio(),4)} for b in base if b.get('title')),key=lambda y:y['similarity'],reverse=True)
    xml=d/'fulltext.xml';pdf=d/'main.pdf';fmt='XML' if xml.exists() else ('PDF' if pdf.exists() else None)
    if xml.exists():
        tree=etree.parse(str(xml));xml_dois=[clean(''.join(z.itertext())).lower() for z in tree.xpath('//article-id[@pub-id-type="doi"]')];assert doi in xml_dois
    if pdf.exists():assert pdf.read_bytes().startswith(b'%PDF') and doi in ''.join(p.extract_text() for p in PdfReader(pdf).pages).lower()
    si=[p for p in d.iterdir() if p.suffix.lower() in ['.pdf','.docx'] and p.name!='main.pdf']
    url=(cr.get('resource',{}).get('primary',{}).get('URL') or 'https://doi.org/'+doi)
    if doi.startswith('10.1039/'):
        code=doi.split('/')[1];j=code[2:4];url=f'https://pubs.rsc.org/en/content/articlehtml/{year}/{j}/{code}'
    if folder=='L30':url='https://link.springer.com/article/10.1007/s44291-025-00057-y'
    if folder=='L24':url='https://www.sciencedirect.com/science/article/pii/S0961953423000454'
    measurements=x.pop('measurements')
    if si:
        x['gaps']=[g.replace('SI未获取','SI已获取但尚未逐字段终审').replace('SI未取得','SI已取得但尚未逐字段终审') for g in x['gaps']]
        for mm in measurements:mm['location']=mm['location'].replace('SI Fig.S8a未取得','SI Fig.S8a已取得待字段核对').replace('SI Fig.S7未获取','SI Fig.S7已取得待字段核对')
    if folder=='L15':
        x['pre_cycle_characterization']={'BET_m2_g':1670.5,'total_pore_volume_raw':1.02,'micropore_volume_raw':0.40,'pore_volume_unit_raw':'m³/g','pore_volume_status':'unit_conflict_no_conversion','location':'新取得SI p7 TableS2；孔体积表头原印m³/g，不自动改为cm³/g'}
        x['gaps'].append('SI TableS2孔体积单位也印m³/g，保持原值/单位并冻结该特征。')
    if folder=='L16':
        x['pre_cycle_characterization'].update(BET_m2_g=1140,total_pore_volume_cm3_g=0.62,pore_volume_status='DOCX_TableS1_text_located_pending_visual_final_review',location='XML node39 XPS；SI DOCX TableS1 SE_GLC行，BET/t-plot方法')
    for mm in measurements:
        mm.update(method='GCD',system='2E_symmetric' if x['domain']!='hold_system_attribution' else 'unresolved_2E_vs_3E',cycling_current_mass_basis_status='not_checked_direct_definition_required',baseline_exact_cycle='not_located',independence_checked=False,eligible=False)
        mm['baseline']=mm['baseline'] or 'not_located'
    records.append(dict(candidate_id=ident,working_source_folder=folder,doi_original=cr.get('DOI') or em['doi'],doi_normalized=doi,title=title,authors=authors,year=year,first_publication_date=first,official_url=url,doi_url='https://doi.org/'+doi,identity_verified=True,identity_basis=['Crossref or publisher-deposited EPMC metadata','DOI/XML identity or publisher original title and device evidence'],bibliographic_new=True,original_experiment_evidence=True,dedup={'normalized_DOI_in_126_papers':False,'normalized_DOI_in_previous_9':False,'exact_normalized_title_matches':[b['id'] for b in base if b.get('title') and nt(b['title'])==nt(title)],'nearest_title_matches':matches[:2],'material_curve_independence':'pending; DOI novelty alone is insufficient'},fulltext={'status':'obtained_complete_'+fmt.lower() if fmt else 'not_obtained; publisher_indexed_sections_only; NOT fulltext_verified','main_format':fmt,'path':str(xml if fmt=='XML' else pdf) if fmt else None,'pages':len(PdfReader(pdf).pages) if fmt=='PDF' else None,'doi_verified_in_local_main':bool(fmt)},supplements={'status':'obtained' if si else 'not_obtained_or_not_declared; do_not_infer_absence','paths':[str(p) for p in si],'identity_status':'publisher-deposited OA package; document title/header checked where present, see file-level report' if si else 'not_checked'},measurements=measurements,archive_status='staged_only_not_archived',admission_status='not_admitted',**x))
    records[-1]['first_publication_date_precision']={4:'year',7:'month',10:'day'}.get(len(first),'unknown')
    records[-1]['first_publication_date_basis']='publisher first online' if folder=='L01' else ('EPMC firstPublicationDate' if em.get('firstPublicationDate') else 'Crossref publication date; precision preserved')
    records[-1]['evidence_paths']=[str(p) for p in [xml,d/'fulltext_nodes.json',pdf,d/'main.pages.json',crpath,d/'epmc_search.json'] if p.exists()]
assert len(records)==20 and len({x['doi_normalized'] for x in records})==20
save('候选文献审核表.json',{'schema_version':'literature-batch2-audit-v1','date':'2026-10-17','scope_note':'20 bibliographically new audited leads; 15 aqueous 2E GCD candidates, 3 separate domains, 2 scope holds. Neither candidates nor fulltexts are admitted training sources.','counts':{'new_bibliographic_records':len(records),'aqueous_2E_GCD_candidates':sum(x['domain']=='aqueous_2E_GCD_candidate' for x in records),'separate_domains':sum(x['domain'].startswith('separate_') for x in records),'scope_holds':sum(x['domain'].startswith('hold_') for x in records),'local_complete_fulltexts':sum(x['fulltext']['main_format'] is not None for x in records),'fulltexts_among_aqueous_candidates':sum(x['domain']=='aqueous_2E_GCD_candidate' and x['fulltext']['main_format'] is not None for x in records),'admitted_papers':0,'independent_materials_finalized':0},'records':records})
save('临时编号映射.json',mapping)

supp=[]
for pid,doi,need,attempt,note in [
 ('R111','10.1016/j.biombioe.2025.108253','SI Fig.S3及器件窗口/电流口径','SUP_R111','官方摘要身份已再核，SI公开CDN返回403；未取得，不解除R111窗口缺口。'),
 ('SRC035','10.1016/j.jallcom.2025.182201','SI TableS1孔体积及器件协议','SUP_SRC035','官方身份已再核，SI公开CDN返回403；未取得，不称原文未报告。'),
 ('SRC123','10.1016/j.colsurfa.2016.10.009','2016前作完整正文及曲线','PRIOR_SRC123','官方预览可读；3263 m²/g、1.772 cm³/g只属于2016前作。未获全文，不能判定2025批次/曲线独立或复用；不计新增合格来源。')]:
    supp.append({'existing_id':pid,'related_doi':doi,'kind':'prior_work_for_provenance_only' if pid=='SRC123' else 'existing_paper_missing_SI','needed':need,'local_evidence_folder':str(ROOT/'sources'/attempt),'status':'not_obtained','result':note,'official_url':'https://doi.org/'+doi,'freeze_cleared':False,'new_paper_count_increment':0})
for x in snap['previous_batch']:
    if x['id'] in ['N003','N006','N007','N008']:
        supp.append({'existing_id':x['id'],'related_doi':x['doi'],'kind':'previous_batch_pending_main','needed':'正文和SI（如有）','status':'prior_request_retained_not_repeated_new_candidate','result':x['caveat'],'official_url':x['url'],'new_paper_count_increment':0,'note':'本轮未重新下载/归档，不能把旧121篇历史措辞作为现126篇状态。'})
save('现有来源补件表.json',{'records':supp,'obtained_existing_SI':0,'obtained_prior_complete_main':0,'existing_freezes_unchanged':True})

exclude_reasons={
'L07':('mass_unbalanced','正文node82报告负/正质量比约1.2，虽称symmetric仍属质量不平衡；题名水果皮而摘要Tondolo也需澄清。94%不能入等质量主集。'),
'L12':('abstract_only_organic_and_LiC','同时涉及有机EDLC和锂离子混合电容；仅核出版社摘要，96%/10000次不能与LiC的69%混用；未完成全文身份/协议核查，不计主批20。'),
'L17':('metal_catalyst_and_label_scope','Fe/Ni/Co催化路线及隔膜干燥/体系范围需核；多种循环节点100%/4000、95%/5000、99.9%/4500并存，未选作主批。'),
'L19':('three_electrode_cycle_only_located','98.8%/5000次/20 A/g在Fig.6电极段；器件能量不证明该循环属于器件，不计主体系新增。'),
'L23':('gel_and_metal_scope','正文柔性/防漏器件为凝胶；FeCl2活化材料范围另审；约88%/10000次不混水溶液主集。'),
'L25':('insufficient_protocol_evidence','出版社给对称器件10万次线索；精确保持率、电解液、循环电流与体系归属尚未核全，不计主批20。'),
'L26':('fulltext_missing_copper_scope','APC-H800/APC-C800及CuCl2处理，摘要no decrease/10000次不是精确100%；需材料范围/全文，不计主批20。'),
'L27':('cycle_system_not_paired','99.74%/20000次公开摘要未核循环对应三/两电极及电解液；SI链接403。与N007、SRC102的Fenton路线需追溯，不能因DOI新认独立。'),
'L28':('cycle_system_not_paired_Mn_scope','MnO牺牲模板，93.7%/100000次摘要未绑定3E/2E或电解液；待全文/最终Mn残留核查。'),
'L29':('mixed_3E_aqueous_and_gel','摘要84.6%/10000次属于三电极；另有水系及PVA器件，未把不同体系标签合并。')}
ex=[]
for folder,(code,reason) in exclude_reasons.items():
    cp=ROOT/'sources'/folder/'crossref.json'
    cr=read(cp)['message'] if cp.exists() else None
    em=read(ROOT/'sources'/folder/'open_record_access.json').get('epmc_record',{})
    dd=cr['DOI'] if cr else em['doi'];tt=cr['title'][0] if cr else em['title']
    ex.append({'working_source_folder':folder,'doi_normalized':dd.lower(),'title':clean(tt),'decision':code,'reason':reason,'new_primary_count_increment':0,'official_url':'https://doi.org/'+dd,'evidence_status':'complete_XML_available' if (ROOT/'sources'/folder/'fulltext.xml').exists() else 'publisher_abstract_or_indexed_sections_only'})
for row in records:
    if row['domain'].startswith(('hold_','separate_')):ex.append({'candidate_id':row['candidate_id'],'doi_normalized':row['doi_normalized'],'decision':row['domain'],'reason':row['gaps'],'new_primary_count_increment':0,'retained_in_audit_table':True})
duplicates=[{'id':b.get('id'),'doi':b['doi_normalized'],'decision':'existing_DOI_excluded_from_new_count','note':'检索命中现库或前批；不重复下载/计新。'} for b in base if b.get('id') in ['R001','R103','R106','R107','SRC123','SRC124','SRC125','SRC126','SRC127','N003','N006','N007','N008']]
save('重复与排除记录.json',{'normalization':read(ROOT/'DOI去重基线.json')['normalization'],'existing_and_previous_hits':duplicates,'scope_or_insufficient_evidence':ex,'existing_frozen_registry_preserved':snap['freezes'],'note':'不同原料同名不自动合并；同作者/相似制备仅是复用核查线索。新增论文数、材料、测试、节点、准入分开。'})

evidence_files=[]
for p in sorted((ROOT/'sources').rglob('*')):
    if not p.is_file():continue
    ent={'path':str(p),'sha256':sha(p),'bytes':p.stat().st_size,'format':p.suffix.lstrip('.'),'source_folder':p.parent.name}
    if p.suffix=='.pdf':
        rd=PdfReader(p);ent.update(valid_pdf_header=p.read_bytes().startswith(b'%PDF'),pages=len(rd.pages),first_page_text=rd.pages[0].extract_text()[:220])
    if p.name=='fulltext.xml':
        tr=etree.parse(str(p));ent['has_body']=tr.find('body') is not None;ent['article_doi']=[''.join(n.itertext()) for n in tr.xpath('//article-id[@pub-id-type="doi"]')]
    evidence_files.append(ent)
save('来源文件指纹.json',{'files':evidence_files,'pdfs_are_parseable':all(x.get('valid_pdf_header',True) for x in evidence_files)})

qa=[{'source':'L05','image':'visual_checks/L05_p4.png','result':'SI p4图注对称器件/10 A/g、10000次97.25%可见；内嵌potential为−1至0 V，登记窗口表达疑点。'},
 {'source':'L18','image':'sources/L18/materials-17-04341-g007.jpg','result':'Fig.7d标95.5%/10000；GCD为0–1 V；SI p1题名/作者一致、6 M KOH、2032器件。'},
 {'source':'L21','image':'sources/L21/molecules-28-07187-g006.jpg','result':'Fig.6d橙色电容曲线92.09%，红色库仑效率93.04%，不互换。'},
 {'source':'L14','image':'sources/L14/materials-19-03741-g005.webp','result':'Fig.5明确CS-800/1 M KOH、0–1.5 V和30000次；多条黑色散点轨迹不用于自行算精确标签。'},
 {'source':'L30','image':'visual_checks/L30_p7.png','result':'Fig.5h标96.94%、1 A/g、2.6 mg/cm²及20000次；Fig.5d GCD 0–1 V。'}]
save('视觉核查记录.json',qa)

lines=['# 第二批候选DOI与获取状态','','这是一份暂存审核清单，未归档、未准入。15条水系两电极GCD候选包含协议/标签缺口；另3条旁系、2条范围冻结单列。', '', '|临时号|DOI|题名|状态|循环标签|', '|---|---|---|---|---|']
for x in records:
    labs='；'.join(f"{z['sample']}: {z['cycles']}次/"+(f"{z['retention_percent']}%（约数）" if z['retention_kind'] in ['approximate_reported','near_100_qualitative'] else f"{z['retention_percent']}%") if z['retention_percent'] is not None else f"{z['sample']}: {z['cycles']}次/终点缺失或冲突" for z in x['measurements'])
    domainlabel='水系主候选' if x['domain'].startswith('aqueous') else ('旁系单列' if x['domain'].startswith('separate') else '范围待澄清')
    lines.append(f"|{x['candidate_id']}|[{x['doi_normalized']}]({x['doi_url']})|{x['title']}|{domainlabel}；{'完整'+x['fulltext']['main_format'] if x['fulltext']['main_format'] else '未取得完整正文'}|{labs}|")
lines+=['','逐字段条件、出处、冲突和优先级见《候选文献审核表.json》。XML为完整正文，不能因没有PDF就称缺全文。','', '尚缺完整正文的本批候选：']
for x in records:
    if x['fulltext']['main_format'] is None:lines.append(f"- {x['candidate_id']} [{x['title']}]({x['official_url']})；DOI {x['doi_normalized']}；需要正文及SI。")
(ROOT/'候选DOI与获取状态.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
(ROOT/'本批需补正文_DOI.txt').write_text('\n'.join(x['doi_normalized'] for x in records if x['fulltext']['main_format'] is None)+'\n',encoding='utf-8')
(ROOT/'本批候选_DOI.txt').write_text('\n'.join(x['doi_normalized'] for x in records)+'\n',encoding='utf-8')

report='''# 第二批同体系文献补充：进度与交接

日期：2026-10-17。文献侧本批已完成，可进入发起对话的合并核对；只交付候选暂存和证据，未归档、未写入SQLite、未训练。此处“完成”表示审核包已交付，未决事项并未解决或自动解除。

本批审核20条库外论文身份及原始实验依据：15条水系两电极GCD待审候选、3条旁系（离子液体、面积电流、有机宽温域），2条范围待澄清。20条均未在现126篇和前批9条中命中DOI，也无规范化题名完全相同项；这只证明书目不重复，不能证明材料/曲线完全独立。16条有本地完整正文（15 XML、1 PDF）；4条仅有官方摘要及索引展开片段，未冒称全文核查。15条主候选中11条有完整正文。严格准入0，材料独立性终审0；未按多个终点增加独立材料数。

可优先复核B2_006银杏叶、B2_007榕叶、B2_008金合欢叶、B2_017椰壳和B2_020小麦秸秆。它们有正文明确的器件循环标签；仍缺电流质量分母、基线可比性或其他字段，不能直接进训练。B2_004同篇3种球果材料先按论文内名记录，但PAC有前作复用线索；同篇水系/有机测试不叠算材料。

关键发现：B2_005器件97.25%与三电极94.68%分开；SI器件图内嵌负电位表达继续待审。B2_010是面积电流2.2 mA/cm²，不能换成A/g；其504 m²/g是CO2-DFT表面积，不能填成N2-BET。B2_011草莓秸秆的器件为70.1%，摘要95.6%属于电极段，图注又有asymmetric措辞冲突。B2_015玉米芯孔体积表头原印m³/g，未纠正。B2_016柚皮器件未给明确终点，不能用平均衰减乘圈数生成81%。B2_019荔枝种子全文未取得，Highlights92%和摘要above90%按不同精度保存。B2_020循环负载2.6 mg/cm²，不移给7.1 mg/cm²倍率实验。低BET值和较低保持率均原样保留，不按性能筛除。

范围冻结另列：B2_014田菁碳XPS检出Fe/Si及可能Fe3C，材料范围待核，不设自创痕量阈值；12 m NaNO3是质量摩尔浓度，不能录成12 M。B2_018板蓝根药渣摘要称两电极1 M Na2SO4，但循环图在6 M KOH电极整图中，不能确认同体系。搜索命中的质量比约1.2的N-TAC、三电极花生壳循环、凝胶器件和协议未配对线索均另留排除记录，不凑主批。

现有来源补件：R111和SRC035的官方身份已核；公开SI入口403，未取得SI，不补窗口/孔体积。SRC123的2016前作仍只读到官方预览，未取得完整曲线；旧BET3263与2025的3185既不证明同批也不证明独立。其2016来源只作出处核查，不计新增合格训练文献。N003/N006/N007/N008沿用前批待补正文状态，未重新计新、未重复下载或归档。

检索覆盖：检索出版社RSC、Elsevier、Wiley、Springer/Nature原始页面，结合Crossref身份和出版社存入EuropePMC的开放全文；EuropePMC发现查询在2023-01-01至2026-10-17范围返回35项，随后按原料、体系和实验归属审核。主批及旁支合计30条新DOI线索，10条未选入20条主审核表；原库和前批命中另排除。不是穷尽性系统综述，公开可得全文偏向开放期刊，需在后续付费正文补齐时警惕来源覆盖偏差。检索词和覆盖见《检索覆盖与限制.json》。遇403停止，不绕过登录/付费；DNB镜像TLS验证失败后未关闭TLS，改从正式出版社公开PDF取得同一OA论文。

文件入口：《候选DOI与获取状态.md》供直接浏览，《候选文献审核表.json》供逐字段审查，《现有来源补件表.json》《重复与排除记录.json》供追踪缺口。《本批需补正文_DOI.txt》只列本批4条新缺正文；旧4条N编号留在补件表。原文/SI暂存在sources，原始获取日志、XML节点/页码文本和SHA256均可追溯。五项图像核查见《视觉核查记录.json》，不声称逐图全部审核。

下一步由发起对话等待两边ready_for_merge，再核共同基线、文件哈希、DOI/材料/曲线关系与冲突。文献侧先合入候选索引，归档仍须新批审核确认；逐记录准入另审。任何相似作者/路线只生成关系线索，不强行判同组或独立。全部原冻结保留。没有拟议放宽口径；有机、凝胶、面积电流、质量不平衡等均未隐式放进水系主集。首轮30–50篇/50–100材料、更充分60–100篇/150–300材料只是项目规划，不是文献证明阈值，本批不为数字降标准。
'''
(ROOT/'进度与交接.md').write_text(report,encoding='utf-8')
save('检索覆盖与限制.json',{'date':'2026-10-17','period':['2023-01-01','2026-10-17'],'search_families':['biomass symmetric cycling 2023/2024/2025/2026 porous carbon supercapacitor','site:pubs.rsc.org symmetric carbon retention peel/shell/straw','site:mdpi.com/site:nature.com/site:link.springer.com biomass carbon symmetric retention','DOI/title exact searches for R111/SRC035/2016 RHC prior work','EuropePMC TITLE_ABS symmetric supercapacitor + biomass/derived + date + OPEN_ACCESS:Y'],'discovery_file':'epmc_discovery.json','epmc_hit_count':35,'new_DOI_leads_reviewed':30,'main_audit_table':20,'other_leads':10,'databases_not_systematically_searched':['Web of Science','Scopus','CNKI'],'primary_evidence_policy':'Only original publisher papers, original public fulltexts/SI and publisher metadata used for experimental claims; reviews/comparison tables not counted as new experiments.','limitations':['Not an exhaustive systematic review','Open-text availability creates publisher/journal selection bias','4 main-audit records have only publisher indexed sections, not fulltext verification','No account/paywall bypass; HTTP 403 retained','Independent materials and baseline/current mass normalization not finalized']})
save('额外访问记录.json',{'accesses':[{'source':'L04','url':'https://www.ebi.ac.uk/europepmc/webservices/rest/PMC10177221/fullTextXML','result':'one retry after HTTP500 succeeded; original failure log retained'},{'source':'L30','url':'https://d-nb.info/1369369662/34','result':'TLS certificate validation failed; no TLS bypass'},{'source':'L30','url':'https://link.springer.com/content/pdf/10.1007/s44291-025-00057-y.pdf','result':'official OA PDF obtained, 11 pages, DOI verified'},{'source':'L27','url':'https://advanced.onlinelibrary.wiley.com/doi/suppl/10.1002/adfm.202403448/supinfo/adfm202403448-sup-0001-SuppMat.pdf','result':'HTTP403, no bypass'}]})

baseline=read(PROJECT/'并行协作契约_v1_20261017.json')['baseline'];fp=read(ROOT/'基线与原文保护指纹.json')
source_unchanged=all(Path(x['path']).exists() and sha(x['path'])==x['sha256'] for x in fp['source_files'])
checks={'baseline_database_sha256_matches':sha(baseline['database'])==baseline['database_sha256'],'baseline_model_contract_sha256_matches':sha(baseline['model_contract'])==baseline['model_contract_sha256'],'137_original_source_hashes_unchanged':source_unchanged,'baseline_readonly_inputs_unchanged':all(sha(x['path'])==x['sha256'] for x in fp['inputs']),'20_unique_new_DOIs_no_existing_or_previous_hits':len({x['doi_normalized'] for x in records})==20 and all(x['doi_normalized'] not in known for x in records),'20_no_exact_title_duplicate':all(not x['dedup']['exact_normalized_title_matches'] for x in records),'all_candidates_staged_not_admitted':all(x['archive_status']=='staged_only_not_archived' and x['admission_status']=='not_admitted' for x in records),'all_XML_has_body_and_DOI_identity':all(x.get('has_body',True) for x in evidence_files),'all_PDF_headers_and_pages_parseable':all(x.get('valid_pdf_header',True) and x.get('pages',1)>0 for x in evidence_files),'year_scope_2023_to_2026':all(2023<=x['year']<=2026 for x in records),'count_partition_15_plus_3_plus_2_equals_20':Counter(x['domain'].split('_')[0] for x in records)=={'aqueous':15,'separate':3,'hold':2}}
save('交付核验.json',{'checks':checks,'all_passed':all(checks.values()),'statistics':read(ROOT/'候选文献审核表.json')['counts'],'note':'No database import, raw-library archive, model fitting, account action, global-runtime or system modification was performed.'})
assert all(checks.values()),checks
outputs=[]
for p in sorted(ROOT.rglob('*')):
    if p.is_file() and p.name!='merge_manifest.json':outputs.append({'path':str(p),'sha256':sha(p),'role':'source_evidence' if 'sources' in p.parts else 'review_artifact'})
save('merge_manifest.json',{'schema_version':'parallel-preparation-v1','task_role':'literature','baseline_database_sha256':baseline['database_sha256'],'baseline_model_contract_sha256':baseline['model_contract_sha256'],'ready_for_merge':True,'outputs':outputs,'checks':checks,'unresolved_issues':['No existing R111/SRC035 SI or full 2016 RHC prior text obtained','4 new main-audit records still need complete text/SI','All current mass normalization, comparable baselines and material/curve independence require record review','15 primary candidates include explicit label/protocol conflicts; 3 side domains and 2 scope holds never implicitly admitted','New archive decision still required; original freezes unchanged'],'proposed_contract_changes':[],'archive_authorization_required':True,'admitted_rows':0})
print(json.dumps({'counts':read(ROOT/'候选文献审核表.json')['counts'],'checks':checks,'outputs':len(outputs),'ready_for_merge':True},ensure_ascii=False))
