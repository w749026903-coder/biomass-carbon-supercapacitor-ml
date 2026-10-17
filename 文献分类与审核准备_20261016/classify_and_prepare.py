from pathlib import Path
import json,re,csv,collections,hashlib,html,shutil,sys
sys.stdout.reconfigure(encoding='utf-8')
OUT=Path(__file__).resolve().parent;ROOT=OUT.parent
inv=json.loads((OUT/'本地与压缩包文件盘点.json').read_text(encoding='utf-8'))
records=inv['records']
master=json.loads((ROOT/'文献补入_1zip_20261016/下载归档最终台账_补入1zip后.json').read_text(encoding='utf-8'))
extras_meta=json.loads((OUT/'额外资料_书目核对结果.json').read_text(encoding='utf-8'))
rawpool={x['DOI'].lower():x for x in json.loads((ROOT/'文献更新_2023至今/Crossref_去重总池.json').read_text(encoding='utf-8'))}
blocked=json.loads((ROOT/'文献扩充_生物质碳_120篇/禁止入库与待核查来源.json').read_text(encoding='utf-8-sig'))
byid={x['collection_id']:x for x in master};by_source={x.get('paper_id'):x for x in records if x.get('paper_id')}
assert len(by_source)==57
incoming=[]
for rec in records:
    if rec.get('match_status')!='新增全文_题名DOI对应':continue
    row=byid[rec['paper_id']];assert not row.get('local_pdf') and rec['local_pdf']
    row.update(local_pdf=rec['local_pdf'],sha256=rec['sha256'],pages=rec['pages'],
               download_status='用户新增散装PDF_题名DOI对应已核验',source_kind='user_provided_local_pdf',
               source_version='出版社排版PDF_版本细节待全文审核',import_date='2026-10-16',
               audit_status='身份与文件已核对_实验数据待审核',eligible_for_database=False)
    incoming.append(row['collection_id'])
assert len(incoming)==11
SHELVES={'A':'01_多孔碳与杂原子掺杂','B':'02_复合材料与特殊成分','C':'03_机器学习与数据方法','D':'04_综述与机制背景','E':'05_年份版本与质量待核','F':'06_范围外资料'}
reviews={'R008','R009','R010','R011','R021','R023','R027','R034','R037','R041','R051'}
methods={'R001','R002','R003','R004','R005','R006','R007','R057','R098','R110'}
composites={'R015','R016','R020','R024','R026','R030','R035','R042','R043','R047','R048','R052','R056','R076','R095','R097','R099','R114','R115'}
special_material={'R024':'N/Si/Ti掺杂碳，含金属Ti','R115':'木质素与活性炭复合，木质素未碳化','R097':'纤维素/还原氧化石墨烯碳气凝胶','R017':'化学活化与功能化碳，成品残余金属待核','R066':'金属辅助木质素组装，成品残余金属待核','R081':'Fe辅助制备碳，成品残余金属待核','R095':'冶金渣辅助制备，成品金属/非金属成分需分层'}
extra_category={
 'SRC002':'F','SRC005':'E','SRC018':'D','SRC019':'D','SRC022':'E','SRC023':'E','SRC025':'A','SRC026':'F','SRC027':'F','SRC028':'A','SRC030':'E','SRC032':'F','SRC035':'A',
 'SRC069':'D','SRC070':'D','SRC071':'E','SRC072':'C','SRC073':'E','SRC074':'C','SRC075':'D','SRC077':'C','SRC078':'D','SRC080':'D','SRC081':'F','SRC082':'C','SRC083':'C','SRC084':'F','SRC085':'D','SRC086':'E','SRC087':'C','SRC088':'F','SRC089':'F','SRC090':'F','SRC091':'F','SRC092':'E','SRC093':'A','SRC094':'E','SRC095':'F','SRC096':'F','SRC097':'D','SRC098':'F','SRC099':'E','SRC100':'E','SRC101':'B','SRC102':'A','SRC103':'F','SRC104':'E','SRC105':'F','SRC106':'F','SRC107':'E','SRC108':'F','SRC109':'F','SRC110':'A','SRC111':'E','SRC112':'A','SRC113':'E','SRC114':'F','SRC115':'A','SRC116':'F','SRC117':'F','SRC118':'F','SRC119':'F','SRC120':'A','SRC121':'A','SRC122':'F'}
extra_reason={
 'SRC005':'材料制备研究，尚未确认提供超级电容器测试。',
 'SRC018':'采用商业YP-50F等碳，生物质来源未证；作质量负载与离子传输方法背景。',
 'SRC019':'电解液机理背景，不能默认电极为生物质碳。',
 'SRC022':'无首页DOI和正式发表日期，复合器件体系，先核版本身份。',
 'SRC028':'生物质碳电化学储能候选，需核实具体超级电容器测试与质量口径。',
 'SRC030':'Co-MOF镍泡沫预印本，属于历史方法背景，非生物质碳实验库。',
 'SRC069':'综述；中文DOI在Crossref无记录，保留本地出版信息待核。',
 'SRC070':'会议论文/综述，不能按原始实验数据入库。',
 'SRC072':'广义碳电极机器学习方法，生物质子集与旧底层年份须重查。',
 'SRC074':'PANI电极优化方法，不直接提供本项目生物质碳样本。',
 'SRC077':'统一测量与适用域方法背景，主体CDC并非生物质碳。',
 'SRC082':'无机材料机器学习方法，不能当电容实验样本。',
 'SRC083':'广义碳电极公开数据方法，先重建来源/材料标识并过滤底层年份。',
 'SRC087':'来源分组验证相关方法；PDF为Accepted Manuscript，正式出版及原始数据需核。',
 'SRC089':'染料去除研究，不作为超级电容器性能数据。',
 'SRC090':'煤基碳，不属于生物质衍生碳主线。',
 'SRC092':'Al-MOF衍生碳，生物质前驱体尚未证实，不直接入库。',
 'SRC093':'生物质碳与超级电容器相关，ACS在线先行版，须核正式日期及SI。',
 'SRC094':'白桦碳预印本，正式发表身份与日期待核。',
 'SRC097':'生物质分馏与脱木质素工艺背景，不视为新电容实验。',
 'SRC099':'印尼文生物质电极论文，首页给2026年，DOI/书目及术语需进一步核对。',
 'SRC100':'Fe/壳聚糖/SiO2体系，尚未确认碳化与成品碳属性。',
 'SRC104':'Research Square预印本，不当作正式期刊版。',
 'SRC106':'电容去离子研究，非当前超级电容器储能标签。',
 'SRC107':'SSRN预印本，正式出版与版本对应待核。',
 'SRC109':'电容去离子与MXene综述，不用于当前储能标签。',
 'SRC111':'竹笋壳作者稿，无首页DOI与发表日期，版本待核。',
 'SRC113':'2022-08-02预印本；不符合当前年份范围，不补算R073正式版。',
 'SRC117':'PFAS吸附论文，R046 DOI仅见于引文，不补算目标全文。',
 'SRC119':'甲醛/苯酚树脂碳，不能默认生物质来源。','SRC122':'析氧反应催化研究，不能当超级电容器储能性能记录。'}
def clean(s):return re.sub(r'\s+',' ',html.unescape(re.sub('<[^>]*>','',s))).strip()
def get_year(m):
    ds=[m.get(k,{}).get('date-parts',[[]])[0] for k in ['published','published-online','published-print','issued']]
    ds=[p for p in ds if p and p[0]]
    return min(p[0] for p in ds) if ds else None
def feature_hint(rec):
    if not rec:return '待全文确认'
    cues=rec.get('text_cues',{});labels={'process_parameters':'制备条件','specific_capacitance':'比电容','rate_performance':'不同电流/倍率','cycling_stability':'循环保持','energy_power':'能量/功率'}
    return '、'.join(v for k,v in labels.items() if cues.get(k))+'（关键词定位，数值尚未审核）'
def protocol_hint(rec):
    if not rec:return '待全文确认'
    cues=rec.get('text_cues',{});s=[]
    if cues.get('two_electrode'):s.append('两电极')
    if cues.get('three_electrode'):s.append('三电极')
    if cues.get('asymmetric'):s.append('非对称')
    if cues.get('symmetric'):s.append('对称')
    return '、'.join(s)+'（正文关键词，需逐测试确认）' if s else '待逐测试确认'
def si_status(row,rec):
    supplements=[*row.get('supplements',[]),*row.get('supplements_current',[])]
    paths={s.get('local_path') for s in supplements if s.get('local_path') and Path(s['local_path']).is_file()}
    if paths:return f'本地已取得{len(paths)}份，内容待核'
    return '文中提及，尚未取得' if rec and rec.get('text_cues',{}).get('supplement_mentioned') else '待核'
classified=[]
for row in master:
    pid=row['collection_id'];rec=by_source.get(pid)
    cat='D' if pid in reviews else 'C' if pid in methods else 'B' if pid in composites else 'A'
    genre='综述/背景' if cat=='D' else '机器学习/数据分析' if cat=='C' else '原始实验候选'
    material='多孔碳/非金属掺杂碳候选' if cat=='A' else '复合材料候选' if cat=='B' else '不作单一材料样本分类'
    material=special_material.get(pid,material)
    gate='待逐条实验审核'
    note='题名与摘要初分；有全文者已定位方法与测试关键词，未逐条审计实验值。'
    if not rec:note='仅依据已核验书目题名初分；全文尚缺，分类待确认。'
    if pid=='R001':gate='S1二手训练表禁止直接导入';note='S1含旧来源、重复与输入/标签冲突；主文可作方法阅读。'
    if pid=='R088':cat='E';gate='关键单位待核，禁止数据导入';note='首页摘要表面积写389.3 cm²/g，负载写21.93 g/cm²；已图像核对，不能擅自改成m²/g或mg/cm²。'
    if pid=='R115':note='PDF首页确认木质素/活性炭复合；木质素未碳化，活性炭前驱体仍待核，禁止与纯衍生碳直接合并。'
    if pid=='R024':note='PDF首页确认N、Si、Ti共同掺杂，Ti为金属，需与非金属掺杂分层。'
    if pid=='R037':note='首页明确REVIEW，纠正旧台账原始研究候选标签。'
    if pid in {'R008','R011'}:note='综述兼机器学习背景，不当作新的独立实验样本。'
    if pid=='R057':note='PCA数据分析方法，底层实验出处和重复材料需单独追溯。'
    x={'id':pid,'population':'主120篇','doi':row['doi'],'title':row['title'],'year':row['year'],'journal':row['journal'],
       'category':cat,'shelf':SHELVES[cat],'genre':genre,'material_family':material,'fulltext_status':'已取得全文' if rec else '待补全文',
       'local_pdf':row.get('local_pdf'),'sha256':row.get('sha256'),'pages':row.get('pages') if rec else None,
       'version':row.get('source_version','待取得全文') if rec else '待取得全文','quality_gate':gate,'note':note,
       'basis':'题名/摘要与方法页定位' if rec else '题名/书目初分',
       'electrode_hint':protocol_hint(rec),'metric_hint':feature_hint(rec),'supplement_status':si_status(row,rec),
       'reading_excerpt':rec.get('reading_excerpt') if rec else None,'source_record_id':rec.get('source_record_id') if rec else None,
       'eligible_for_database':False}
    classified.append(x)
    row['classification']=x
extra_rows=[]
for rec in records:
    if rec.get('paper_id'):continue
    sid=rec['source_record_id'];front=rec.get('pdf_firstpage_text','')
    matches=re.findall(r'10\.\d{4,9}/[^\s<>"\)]+',front,re.I)
    doi=matches[0].rstrip('.,;:').lower() if matches else None
    m=extras_meta.get(doi or '',{}).get('data',{}) or rawpool.get(doi or '',{})
    title=clean(m['title'][0]) if m.get('title') else Path(rec['filename']).stem
    year=get_year(m);cat=extra_category[sid];note=extra_reason.get(sid,'与题名方向相符或仅作范围外背景，未纳入主120篇；后续核对原文和适用范围。')
    if rec.get('blocked_own_doi'):
        cat='E';note='；'.join(b['reason'] for b in rec['blocked_own_doi']);gate='既有冻结来源，禁止数据导入'
    elif sid=='SRC113':gate='早于2023年，不入库'
    elif rec['preprint_notice'] or not year:gate='发表身份/年份待核，不入库'
    elif cat=='F':gate='范围不符，不进入当前实验库'
    elif cat=='E':gate='范围/版本/字段待核，不入库'
    else:gate='清单外候选，尚未完成准入审核'
    x={'id':sid,'population':'额外资料','doi':doi,'title':title,'year':year,'journal':clean(' '.join(m.get('container-title',[]))) if m else '',
       'category':cat,'shelf':SHELVES[cat],'genre':'综述/机制背景' if cat=='D' else '机器学习/数据方法' if cat=='C' else '待核' if cat=='E' else '范围外' if cat=='F' else '原始实验候选',
       'material_family':'需核对前驱体与成品组成','fulltext_status':'本地PDF' if rec['local_pdf'] else '仅在1.zip内',
       'local_pdf':rec['local_pdf'],'archive_entry':next((s['entry'] for s in rec['sources'] if s['kind']=='zip_member'),None),
       'sha256':rec['sha256'],'pages':rec['pages'],'version':'Accepted Manuscript' if rec['accepted_manuscript_notice'] else '预印本' if rec['preprint_notice'] else '版式/出版状态待核',
       'quality_gate':gate,'note':note,'basis':'首页/摘要与局部方法阅读，出版年份优先Crossref登记',
       'electrode_hint':protocol_hint(rec),'metric_hint':feature_hint(rec),'supplement_status':'待核','reading_excerpt':rec['reading_excerpt'],
       'source_record_id':sid,'eligible_for_database':False}
    extra_rows.append(x)
assert len(extra_rows)==65
all_rows=classified+extra_rows
for filename,data in [('下载归档最终台账_分类准备后.json',master),('主清单分类.json',classified),('额外资料分类.json',extra_rows)]:
    with (OUT/filename).open('w',encoding='utf-8') as f:json.dump(data,f,ensure_ascii=False,indent=2)
columns=[('id','编号'),('year','年份'),('shelf','分类'),('genre','文献用途'),('material_family','材料分层'),('fulltext_status','全文状态'),('quality_gate','准入状态'),('title','题名'),('doi','DOI'),('electrode_hint','测试体系线索'),('metric_hint','指标定位线索'),('supplement_status','补充材料'),('note','分类依据与待核问题'),('local_pdf','本地PDF'),('archive_entry','压缩包成员'),('reading_excerpt','页码摘录')]
for filename,data in [('主120篇_分类清单.csv',classified),('额外65份_分类清单.csv',extra_rows)]:
    with (OUT/filename).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f);w.writerow([label for _,label in columns]);w.writerows([[x.get(k) for k,_ in columns] for x in data])
def link(x):
    if x.get('local_pdf'):return f"[PDF](<{x['local_pdf']}>)"
    if x.get('archive_entry'):return '[1.zip](<D:/文献/1.zip>)内：'+x['archive_entry']
    return '待补全文'
def safe(s):return str(s or '').replace('|','\\|').replace('\n',' ')
for code,shelf in SHELVES.items():
    folder=OUT/'分类阅读目录'/shelf;folder.mkdir(parents=True,exist_ok=True)
    subset=[x for x in all_rows if x['category']==code]
    lines=[f'# {shelf[3:]}','',f'共{len(subset)}条，其中主清单{sum(x["population"]=="主120篇" for x in subset)}条，额外资料{sum(x["population"]=="额外资料" for x in subset)}条。分类不等于数据审核通过。原PDF保留原位置。','',
           '| 编号 | 范围 | 年份 | 题名 | 获取 | 待核事项 |','|---|---|---|---|---|---|']
    lines += [f"| {x['id']} | {x['population']} | {x['year'] or '待核'} | {safe(x['title'])} | {safe(link(x))} | {safe(x['note'])} |" for x in subset]
    (folder/'阅读索引.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
duplicates=[]
for rec in records:
    if len(rec['sources'])>1:
        duplicates.append({'id':rec.get('paper_id') or rec['source_record_id'],'sha256':rec['sha256'],'occurrences':len(rec['sources']),'sources':rec['sources'],'action':'按内容计1份，原文件及压缩包保留'})
with (OUT/'重复与多位置文件.json').open('w',encoding='utf-8') as f:json.dump(duplicates,f,ensure_ascii=False,indent=2)
pending=[x for x in master if not x.get('local_pdf')]
assert len(pending)==63
lines=['# 待补全文63篇','', '用户已表示其余能取得的论文已补入。本清单用于记录剩余缺口，不继续反复尝试失败下载，也不要求全部补齐后才能开始已有全文审核。R073现只有2022年预印本，不算正式版全文。','', '| 编号 | 年份 | 题名 | DOI |','|---|---|---|---|']
lines += [f"| {x['collection_id']} | {x['year']} | {safe(x['title'])} | [{x['doi']}](https://doi.org/{x['doi']}) |" for x in pending]
(OUT/'待补全文_DOI清单_63篇.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
(OUT/'待补全文_DOI纯文本_63篇.txt').write_text('\n'.join(x['doi'] for x in pending)+'\n',encoding='utf-8')
issues=[
 {'issue_id':'Q001','paper_id':'R001','topic':'二手训练表来源/重复/冲突','evidence':'补充Table S1，89/164行重复，32/33行同列示输入对应不同电容；含2023年前原始来源。','action':'禁止整体导入S1；只作方法阅读，逐原文核对年份和材料标识。'},
 {'issue_id':'Q002','paper_id':'R088','topic':'关键单位','evidence':'PDF第1页摘要，表面积389.3 cm²/g、质量负载21.93 g/cm²，图像核对与文本一致。','action':'冻结数据录入；核正文、图表、SI或勘误，禁止猜测换成m²/g或mg/cm²。'},
 {'issue_id':'Q003','paper_id':'R115','topic':'材料范围','evidence':'PDF第1页摘要为木质素/活性炭复合，并强调不需预先碳化。','action':'单列聚合物/碳复合；核活性炭前驱体与未碳化木质素分母，不与纯衍生碳合并。'},
 {'issue_id':'Q004','paper_id':'R024','topic':'成品组成','evidence':'PDF第1页写N、Si、Ti共同掺杂，Ti是金属。','action':'归入复合/特殊成分；逐样品核成分，不能仅凭heteroatoms标签归入非金属掺杂。'},
 {'issue_id':'Q005','paper_id':'R073/SRC113','topic':'年份和版本','evidence':'用户包内为2022-08-02 Research Square v1，DOI 10.21203/rs.3.rs-1895857/v1。','action':'不补算2023正式版R073全文，不引入该2022版本数据。'},
 {'issue_id':'Q006','paper_id':'R046/SRC117','topic':'论文对应关系','evidence':'PFAS论文自身DOI 10.1016/j.matlet.2025.138050；目标R046 DOI仅见于参考文献。','action':'维持R046待补，不能因DOI字符串命中就导入。'},
 {'issue_id':'Q007','paper_id':'SRC087','topic':'版本与底层数据','evidence':'PDF第1页为Accepted Manuscript，标题含source-aware materials informatics。','action':'可优先读来源分组验证方法；正式信息、训练数据来源年份与代码待核，不复制成绩。'}]
for n,b in enumerate(blocked,8):issues.append({'issue_id':f'Q{n:03d}','paper_id':b['doi'],'topic':'继承冻结/范围限制','evidence':b['reason'],'action':b['action']})
with (OUT/'问题登记.json').open('w',encoding='utf-8') as f:json.dump(issues,f,ensure_ascii=False,indent=2)
with (OUT/'问题登记.csv').open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=['issue_id','paper_id','topic','evidence','action']);w.writeheader();w.writerows(issues)
templates=OUT/'数据库录入准备';templates.mkdir(exist_ok=True)
schemas={
 '文献表_空模板.csv':['paper_id','doi','title','publication_year','article_type','source_version','pdf_path','pdf_sha256','supplement_paths','scope_status','audit_status'],
 '材料样品表_空模板.csv':['material_id','paper_id','sample_label_original','precursor_species','precursor_part','precursor_state','route','carbonization_temperature_C','carbonization_time_h','carbonization_atmosphere','activation_agent','activation_mass_ratio_basis','activation_temperature_C','activation_time_h','washing_conditions','composite_components','residual_metal_status','SSA_m2_g','pore_volume_cm3_g','micropore_volume_cm3_g','mesopore_volume_cm3_g','pore_size_nm','element_content_stage','element_measurement_method','source_pdf_page','source_table_figure','extraction_method','verification_status'],
 '测试记录表_空模板.csv':['test_id','material_id','paper_id','electrode_count','device_symmetry','counter_electrode','reference_electrode','electrolyte_solute','electrolyte_concentration_mol_L','electrolyte_type','active_mass_mg','mass_loading_mg_cm2','mass_basis','metric_name','metric_value','metric_unit','normalization_basis','current_density_value','current_density_unit','voltage_window_V','scan_rate_mV_s','cycle_number','retention_reference_test_id','retention_endpoint_test_id','calculation_equation_original','reported_or_derived','source_pdf_page','source_table_figure','extraction_method','verification_status'],
 '问题日志_空模板.csv':['issue_id','paper_id','material_id','test_id','field','problem_description','source_pdf_page','source_table_figure','evidence','status','resolution','verified_date']}
for name,headers in schemas.items():
    with (templates/name).open('w',encoding='utf-8-sig',newline='') as f:csv.writer(f).writerow(headers)
queue_ids=['R078','R091','R093','R103','R105','R106','R108','R111','R112','R117']
queue=[next(x for x in classified if x['id']==pid) for pid in queue_ids]
summary={'date':'2026-10-16','root_pdf_files':inv['library_pdf_files'],'zip_pdf_members':49,'unique_pdf_contents':len(records),
 'duplicate_extra_occurrences':sum(len(x['sources'])-1 for x in records),'master_candidates':120,'fulltexts_before':46,'new_fulltexts':11,'fulltexts_after':57,'missing_fulltexts':63,
 'extra_unique_documents':len(extra_rows),'main_categories':dict(collections.Counter(x['category'] for x in classified)),
 'all_categories':dict(collections.Counter(x['category'] for x in all_rows)), 'incoming_ids':incoming,'eligible_for_database_count':0}
with (OUT/'分类汇总.json').open('w',encoding='utf-8') as f:json.dump(summary,f,ensure_ascii=False,indent=2)
workbook={'main':classified,'extras':extra_rows,'issues':issues,'summary':summary,'shelves':SHELVES,'queue':queue}
with (OUT/'工作簿数据.json').open('w',encoding='utf-8') as f:json.dump(workbook,f,ensure_ascii=False,indent=2)
print(json.dumps(summary,ensure_ascii=False,indent=2))
