import json,re,hashlib,unicodedata
from pathlib import Path
from lxml import etree
ROOT=Path(__file__).resolve().parent
PARENT=ROOT.parent
# Human-reviewed experimental observations; no inferred endpoint or unit correction.
DATA='''OA001|三电极|藻类 AHPC-850|10000|96.3%|10 A/g|待逐测试绑定|GCD|68,121|摘要及Fig.4明确为三电极；不把器件能量密度移给循环实验
OA003|三电极|餐厨废物碳气凝胶 FWCA-4|10000|94.1%|10 A/g|6 M KOH|GCD|29,93,95|Fig.5说明三电极，Fig.7c有终点；孔体积原印m³/g，保留单位疑点
OA007|三电极|蛋/米饭混合生物质 YPAC-1|10000|82.26%|10 A/g|待逐测试绑定|GCD|35,94|Fig.6d标明三电极；摘要所列器件能量密度属于另一个测试
OA025|三电极|杜仲木 EC-400/EC-10%|10000|正文91.4%/89.8%；摘要92.3%冲突|循环电流待SI配对|1 M H2SO4|GCD待SI确认|12,56,63|SI Fig.S5含循环；不能擅选摘要值；与库中杜仲木前作需核材料关系
OA031|三电极|糠醛渣 FRPCK-Urea|5000|96.43%|20 A/g|6 mol/L KOH|GCD|18,49|倍率保持率81.90%不等于循环保持率；该论文只按1篇计数
OA041|三电极旁系|海洋生物废物糖原碳|1000|三电极99%；固态器件75%另列|1 A/g|DES及固态电解质，分开|GCD|101,115,125|主核糖原碳三电极99%；DES不并入普通水系；论文内多前驱体不先认定独立材料数
OA043|三电极|废富营养化螺旋藻 SNPB-800-4|10000|94.14%|10 A/g|6 M KOH|GCD|16,45,46|器件段另列，循环Fig.6在三电极段；能量/功率单位存在原文互换疑点
OA044|三电极|纤维素 AHC-CL-TU|20000|99.96%|10 A/g|6 mol/L KOH|GCD|23,47,111|Fig.7明确三电极；同段引用别人的76.55%/97.82%不采为本篇数据
OA047|三电极|亚马孙Tucuma树皮 TAK5|7000|摘要98%；正文接近100%|7 A/g|1 M KOH|GCD|25,94,116|保留精度/表述差异，不把正文近100%改写成精确100%
OA050|三电极|辐照预处理水葫芦 WHAC100|7000|99.40%及99.45%不同段表述|未明确绑定循环电流|方法2 M H2SO4；比较段1 M冲突|GCD|16,27,105|Fig.8已目视核对；循环插图约-0.3至0.3 V，不能套CV的-0.3至0.7 V；不同剂量保留成组
OA052|三电极|Alnus nepalensis FPC|1000|98.4%|3 A/g|6.0 M KOH|GCD|30,70,81,112|参比Ag/AgCl、对电极Pt；原文器件/三电极能量换算论述不用于本批换算
OA053|三电极|全生物质聚苯并噁嗪碳 ESC-G|5000|原文声称89%，同时给151→117 F/g|0.5 A/g|1 M H2SO4|GCD|26,33|绝对电容与百分数不一致，冻结终点；保留实测曲线和制备/孔结构作待审资料
OA057|三电极+双电极|羧甲基纤维素 CMC-ZnK-800|5000|三电极94.3%；器件见正文另一段|10 A/g|三电极6 M KOH；器件3 M KOH|GCD|13,38,39,46|优先提取Fig.8三电极；不得把器件电解液移给三电极循环
OA058|三电极+双电极|壳聚糖双模板 AF-MMTCs|5000|三电极6样品98.8/97.0/96.9/98.5/98.0/97.9%|10 A/g|6 M KOH|GCD|36,37,39,40|三电极Fig.4e；器件85.1%另列且圈数待图核；6样品按同文成组，不宣称6个独立论文
OA059|三电极|腰果种皮 AO-PC|10000|97%|5 A/g|1 M H2SO4|GCD|31,34,41|循环窗口-0.1至0.6 V；碳布承载，须保留集流体和质量口径
OA004|双电极|藜麦秸秆 QSC-3|10000|3 M KOH 97.55%；1 M Na2SO4 96.20%|5 A/g|两电解液分别保留|GCD|64,71|同一种材料的两电解液循环不能当成两个独立材料；Na2SO4器件窗口0至2.0 V
OA005|双电极|紫玉米芯 AC-10%|50000|76%，正文称efficiency而摘要/Table称capacitance retention|循环6 A/g；读出1 A/g；图注1 A/g|1 mol/L KOH；方法与器件段酸碱需核|GCD|22,69,70,72,73|分清循环应力与测量电流；76%不直接当CE，也不把CE98–99%填成保持率
OA006|双电极|意大利橙汁碳 4:1@120、5:1@120、5:1@210|5000|有绝对电容循环曲线，未给明确终点百分数|1 A/g|待方法逐项复核|GCD|80,86,87|循环0至1 V而CV0至1.4 V；Fig.7c目视与正文衰减描述不完全一致，保留图文冲突，不生成百分数
OA008|双电极|罗望子果种壳 TFS-AC(KOH)/TFS-AC|10000|98.2%/95.4%|5 A/g|3 M KOH|GCD|55,115|两种样品同文成组；BET124.72 m²/g为原文低值，不放大到千位
OA009|双电极|废牛仔布 AC800|3000|83.01%|1 A/g|1 M H2SO4|GCD|31,35,91,93|三电极另有1000圈及1.33%下降；牛仔布含弹性纤维，保留混合前驱体范围标记
OA011|双电极|青豌豆荚 NSGP|5000|99.46%|5 A/g|1 M H2SO4|GCD|57,59,63|器件Fig.8f绑定明确；电流质量分母仍需统一审核
OA012|双电极|新西兰林业砍伐剩余物 C-HS-NZS|10000|384→360 F/g|10 A/g|6 M KOH|GCD|22,55,59,62|论文报告绝对起终点；未把360/384派生成报告保持率；倍率86%另列；每极1.2 mg见方法
OA013|双电极|六种木质素 LCNF|10000|82.8%至95.5%；另有NaNO3 54%对KOH89%|10 A/g|6 M KOH；12 mol/kg NaNO3另组|GCD|89,90,132|不同木质素来源保留论文内组；12 mol/kg不能录成12 M；电解液对比需与具体样品配对
OA014|双电极|澳洲坚果壳 AC-MNS-3|10000|正文minimal change；定量曲线在图中|3 A/g|6 M KOH|GCD|81,82|有真实循环图，但未冒填精确100%终点；可提取制备、BET和循环曲线
OA015|双电极|芒果核 MK9|100000|有保持率曲线；79.3%原文指库仑效率|2 A/g|3 M KOH|GCD|73,74,76|循环保持率须从Fig.10独立复核；不能把79.3%移填为保持率
OA018|双电极|椰枣核 C:K:M|5000|正文no apparent degradation，定量图待提取|10 A/g|原文1 m H2SO4|GCD|43,75|原文m大小写照录，待确认浓度口径；装置称symmetric；不把定性描述改成精确100%
OA022|双电极|花椒皮PAC-700/花椒籽SAC-600|10000|约99.1%/93.4%|1 A/g|待方法逐项绑定|GCD|49,51|两种原料同文成组；不能把倍率/功率点当循环电流
OA023|双电极|猪肉衍生 APE-2|20000|99.7%|循环电流待图/方法配对|待方法逐项绑定|GCD|46|不把near-zero-loss改为零衰减；两电极结果单独保留
OA024|双电极|生物焦油 AC-N|10000|80.1%|1 A/g|待方法逐项绑定|GCD|p12,p13|PDF正文Fig.5h明确；3E309.5 F/g与2E循环分开；SI另待公开获取
OA045|双电极|碧根果壳 PSAC-10|15000|正文90%；结论约93%矛盾|2 A/g|6 M KOH|GCD|12,23,29|CE约97%另列；终点冲突冻结，不选较高值
OA048|双电极|黄瓜皮 ACP-800|2000|100%|1 A/g|6 M KOH|GCD|25,51,58,122|循环0至0.9 V；CV测试0至1.0 V，不能混用；虽题名electrode仍是双电极
OA049|双电极|雪松木生物炭/炭黑/壳聚糖或PVDF|10000|约95%（壳聚糖）；约93%（PVDF）|循环电流待绑定|1 M Na2SO4|GCD|21,47,57|不同粘结剂与温度组成多组；非三电极，保留全部而不误标；低比电容照录
OA051|双电极，另有3E表征|木质素NaOH模板 LCF-AW|10000|约117%；CE99.9%另列|10 A/g|3 M KOH|GCD|30,36,38,81,91|方法明确循环2E；结果段又称symmetric three-electrode，保留配置冲突；2V为作者假定，不自动用作循环实测窗口
P057|双电极，另有3E数据|稻壳 RH-900|10000|器件95.23%；3E图与结论98%/96%冲突|器件20 A/g|6 M KOH|GCD|p13,p16,p17|PDF Fig.13F器件循环；BET摘要1985/结论1935冲突；Data Availability声明与实验文章语境也须复核
OA019|双电极|花生油饼 HPC-P8|5000|93.8%|官方全文片段10 A/g|1 M Na2SO4|GCD待正文获取|官方摘要、Fig.11c片段|本地未取得完整正文；窗口0至2.0 V；先确认有实验数据，准入仍待全文
P004|双电极|地肤 KAC-5|10000|器件88.83%；电极90.31%分开|循环电流待正文|原文6 m KOH|待正文确认|出版社存入Crossref的摘要|不要把器件88.83与电极90.31混合；m/M须正文核对
P006|双电极|腰果壳 AC-CNS|10000|87%|1.0 A/g|1 M Na2SO4|GCD待正文获取|官方摘要|有明确器件循环数据；本地全文下载失败，未声称逐图核验
P007|双电极|单宁酸/芦苇秸秆 N-RTC-1.5|10000|约96%|3 A/g|循环电解液待正文|待正文确认|ACS官方摘要|需正文及免费SI中的表S1/测试方法，已核原始数据非综述引用
P011|双电极|花生壳磷酸活化碳|20000|99.3%|10 A/g|待正文获取|待正文确认|出版社存入Crossref的摘要|书目信息已核；不能凭三电极比电容把循环也归为三电极
P012|双电极|蛇瓜果皮 SGC900|5000|95%|待正文获取|1 M H2SO4用于电极；器件配对待核|待正文确认|出版社存入Crossref的摘要|保留装置和电解液未完全绑定状态
P013|双电极|西洋参废渣活性炭|10000|97.47%|待正文获取|6 M KOH|待正文确认|Elsevier官方摘要|摘要器件循环明确；不把20 A/g倍率/功率点自动当循环电流
P019|双电极|龙眼壳 N3OPC-3|10000|89%|待正文获取|3E为6 M KOH；循环器件待正文|待正文确认|ACS官方摘要|三电极463 F/g与器件循环分开；需正文及SI
P021|双电极|雨树 Samanea saman NSAC|5000|H2SO4 91.3%；Na2SO4 94.3%|待正文获取|两种电解液浓度待核|GCD（官方明确）|Wiley官方摘要及作者数据仓库|公开数据DOI 10.17632/3w6yb4d844.1；本次入口未取到文件，不能计原始数据已下载
P022|双电极|桉树种子活性炭|10000|76.5%|待正文获取|2 M KOH|GCD（摘要charge-discharge）|出版社存入Crossref的摘要|首次在线2026-08-14，未超检索截止日；低保持率保留
P024|双电极|Terminalia bellirica种石|10000|98.2%|待正文获取|1 M H2SO4|GCD（摘要charge/discharge）|ACS官方摘要|BET2301 m²/g、总孔容1.887 cm³/g为样品表征；不把倍率66%混入循环
P028|双电极|芋头皮 CEPAC 1:1|10000|98.4%|待正文获取|三电极3 M KOH，器件配对待核|GCD（摘要charge-discharge）|Wiley官方摘要|需要正文确认循环质量口径和电解液；不跨体系直接合训
P029|双电极|稻穗 RPPAC-0.25-850|6000|88%|10 A/g|待正文获取|GCD（出版社明确）|出版社存入Crossref的摘要|在线2026-10-09；期刊卷期2026-12仍未来，按已在线论文记，不把未来卷期当已出版纸刊
P030|双电极|杏仁果皮 BNPSC|10000|98%|待正文获取|待正文获取|待正文确认|Elsevier官方摘要|B/N/P/S掺杂，循环1 V线索；能量密度原文单位需核，不能自动修正
P031|双电极|木质素形貌调控 LDPC|10000|96.4%|1 A/g|待正文获取|GCD（官方continuous charging/discharging）|Elsevier官方摘要|同原料不同喷雾形貌为论文内对比，独立性待核
P054|双电极|沉香叶 ALPC-800|6000|91%|1 A/g|酸性电解液，浓度/器件配对待正文|待正文确认|ACS官方摘要|ORR和电容实验并列，循环来自supercapacitor段，不采ORR稳定性'''

def dump(name,obj):
    (ROOT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
def norm(s):return re.sub(r'[^a-z0-9]','',unicodedata.normalize('NFKC',s).lower())
baseline=json.loads((PARENT/'DOI去重基线.json').read_text(encoding='utf-8'))['records']
known_dois={x['doi_normalized'] for x in baseline if x['doi_normalized']}
known_titles={norm(x.get('title','')):x['id'] for x in baseline if x.get('title')}
for p in (PARENT/'sources').glob('*/open_record_access.json'):
    a=json.loads(p.read_text(encoding='utf-8'));known_dois.add(a['doi'].lower())
prior=json.loads((PARENT/'候选文献审核表.json').read_text(encoding='utf-8'))['records']
for x in prior:
    if x.get('title'):known_titles[norm(x['title'])]=x.get('temporary_id','previous_batch')
discovery={x['doi']:x for fn in ['开放与付费候选发现.json','补充原料候选发现.json'] for x in json.loads((ROOT/fn).read_text(encoding='utf-8'))}
records=[]
for i,line in enumerate(DATA.splitlines(),1):
    wid,category,material,cycles,ret,current,electrolyte,method,loc,notes=line.split('|')
    d=ROOT/'sources'/wid;acq={};metadata={};tree=None
    if (d/'acquisition.json').exists():acq=json.loads((d/'acquisition.json').read_text(encoding='utf-8'))
    if (d/'target_metadata.json').exists():metadata=json.loads((d/'target_metadata.json').read_text(encoding='utf-8'))
    doi=acq.get('doi') or metadata.get('doi');title=acq.get('title') or ''
    # The first 18 acquisition records use id and store title in the shortlist.
    short=next((x for x in json.loads((ROOT/'OA初筛待全文核查.json').read_text(encoding='utf-8')) if x['working_id']==wid),{})
    title=title or short.get('title') or (metadata.get('crossref_title') or [''])[0]
    pub={};evidence=[]
    if (d/'main.xml').exists():
        tree=etree.parse(str(d/'main.xml'))
        actual=tree.xpath('/article/front/article-meta/article-id[@pub-id-type="doi"]/text()');assert actual and actual[0].lower()==doi,(wid,actual,doi)
        title=' '.join(' '.join(tree.xpath('/article/front/article-meta/title-group/article-title')[0].itertext()).split())
        pub={'journal':' '.join(tree.xpath('/article/front/journal-meta/journal-title-group/journal-title//text()')),'authors':[' '.join(n.xpath('.//surname/text()|.//given-names/text()')) for n in tree.xpath('/article/front/article-meta/contrib-group/contrib[@contrib-type="author"]')],'dates':[{'attributes':dict(n.attrib),'date_components':{k:n.findtext(k) for k in ['year','month','day']}} for n in tree.xpath('/article/front/article-meta/pub-date')]}
        nodes=json.loads((d/'nodes.json').read_text(encoding='utf-8'))
        picks={int(x) for x in loc.split(',') if x.isdigit()};evidence=[x for x in nodes if x['node'] in picks]
    elif (d/'crossref.json').exists():
        m=json.loads((d/'crossref.json').read_text(encoding='utf-8'))['message'];pub={'journal':m.get('container-title'),'authors':m.get('author'),'dates':{k:m[k] for k in ['published','published-online','published-print'] if k in m},'volume':m.get('volume'),'issue':m.get('issue'),'page':m.get('page'),'article_number':m.get('article-number')}
    main=[str(d/f) for f in ['main.xml','main.pdf'] if (d/f).exists()]
    if (d/'pages.json').exists():
        pages=json.loads((d/'pages.json').read_text(encoding='utf-8'));picks={int(x[1:]) for x in loc.split(',') if x.startswith('p')};evidence=[x for x in pages if x['page'] in picks]
        assert doi.lower() in ''.join(x['text'] for x in pages[:2]).lower(),(wid,'PDF identity mismatch')
    si=[str(p) for p in d.iterdir() if p.suffix.lower() in ['.pdf','.docx','.doc','.csv','.xlsx','.xls'] and p.name!='main.pdf']
    assert doi not in known_dois,(wid,'baseline DOI duplicate',doi)
    title_match=known_titles.get(norm(title));assert not title_match,(wid,'baseline title match',title_match)
    o=discovery.get(doi,{})
    primary=(o.get('primary_location') or {}).get('landing_page_url') or 'https://doi.org/'+doi
    r={'temporary_id':f'EXT_{i:03d}','working_id':wid,'doi':doi,'title':title,'bibliography':pub,'cycle_configuration':category,'material':material,'reported_cycle_count':int(cycles),'reported_retention_or_observation':ret,'reported_current':current,'electrolyte_binding':electrolyte,'cycle_method':method,'evidence_location':loc,'audit_notes':notes,'source_url':primary,'doi_url':'https://doi.org/'+doi,'complete_main_files':main,'main_status':'完整正文已取得' if main else '完整正文未取得；仅原始摘要/出版社元数据核验','supporting_documents_obtained':si,'priority':1 if category.startswith('三电极') and category!='三电极旁系' else (3 if category=='三电极旁系' else 2),'novelty':{'doi_not_in_baseline_or_prior_batches':True,'exact_normalized_title_duplicate':False,'material_or_curve_independence':'未终审；同篇多样品/测试保留成组'},'training_admitted':False,'mass_basis_and_window_review':'电流质量分母、实际循环窗口、起始基线与加载量须逐测试终审，未统一推定','source_evidence':evidence}
    r['readable_html']=str(d/'readable_article.html') if (d/'readable_article.html').exists() else None
    r['metadata_evidence_files']=[str(d/f) for f in ['main.xml','crossref.json','epmc_metadata.json','target_metadata.json','acquisition.json','reader_acquisition.json'] if (d/f).exists()]
    r['web_evidence_logs']=[str(f) for f in ROOT.glob('web_round*.json') if doi in f.read_text(encoding='utf-8')]
    if not main:
        r['publisher_deposited_abstract']=metadata.get('crossref_abstract') or '';r['discovery_abstract_not_primary_evidence']=o.get('abstract') or ''
    records.append(r)
assert len(records)==50
assert len({x['doi'] for x in records})==50
stats={'new_papers':len(records),'complete_main_papers':sum(bool(x['complete_main_files']) for x in records),'missing_complete_main_papers':sum(not x['complete_main_files'] for x in records),'papers_with_supporting_documents':sum(bool(x['supporting_documents_obtained']) for x in records),'three_electrode_containing_papers':sum(x['cycle_configuration'].startswith('三电极') for x in records),'two_electrode_primary_papers':sum(not x['cycle_configuration'].startswith('三电极') for x in records),'strict_training_admissions':0,'independent_material_count_finalized':0}
dump('新增50篇_逐篇数据与获取状态.json',{'as_of':'2026-10-17','latest_user_direction':'后续优先搜索三电极；双电极及其它资料全部保留','stats':stats,'records':records})
missing=[x for x in records if not x['complete_main_files']]
(ROOT/'新增50篇_未取得正文完整DOI.txt').write_text('\n'.join(x['doi'] for x in missing)+'\n',encoding='utf-8')
(ROOT/'新增50篇_全部DOI.txt').write_text('\n'.join(x['doi'] for x in records)+'\n',encoding='utf-8')
lines=['# 新增50篇实验文献与下载结果','',f'检索与核验截止：2026-10-17。新增50篇，不含原库、前批9条及上一轮20篇。{stats["complete_main_papers"]}篇完整正文已取得，{stats["missing_complete_main_papers"]}篇仅核验原始摘要或出版社元数据，尚未取得完整正文。','',f'按最新要求，三电极优先，已有双电极及其它资料全部保留。本清单有{stats["three_electrode_containing_papers"]}篇含已定位的三电极循环实验（包括1篇DES旁系和2篇同时报告两种配置的论文）；其余{stats["two_electrode_primary_papers"]}篇主要保留双电极循环结果。这是检索方向调整前后累积的50篇，并不声称50篇都属于三电极。','',f'{stats["papers_with_supporting_documents"]}篇已取得PDF/Word等补充文档。XML为完整正文文件，包含正文、图注和表格，但多数不内嵌原始图像；需要量化曲线时仍须取得相应高清图。原始获取包、页码/节点文本及哈希均留在sources。','', '“有实际数据”表示已在本篇原始实验结果中定位到循环次数、保持率/绝对电容或可读循环图，并排除仅引用别人的对比表。它不等于已完成全部特征提取或可直接训练；未取得正文的16篇不能保证所有必需字段齐全。','', '三电极、双电极、CV、GCD、DES/有机电解液及面积电流分开；不按性能高低删数据。保留图文冲突与定性终点，不生成缺失百分数。数据库与既有model_contract未更改，严格准入0，材料独立性终审0。','', '## 逐篇清单','', '|编号/原料|DOI与原文|循环数据及方法|取得情况|用途和待核事项|','|---|---|---|---|---|']
for r in records:
    doi=r['doi'];status='正文已取得'
    if r['complete_main_files']:status=f'[正文]({r["complete_main_files"][0]})'
    else:status='待获取正文'
    if r['readable_html']:status=f'[可读全文与原图]({r["readable_html"]})；XML保留'
    if r['supporting_documents_obtained']:status+='；SI已取得'
    data=f'{r["cycle_configuration"]}；{r["reported_cycle_count"]}圈；{r["reported_retention_or_observation"]}；{r["reported_current"]}；{r["cycle_method"]}'
    lines.append(f'|{r["temporary_id"]} {r["material"]}|[{doi}]({r["doi_url"]})<br>{r["title"]}|{data}|{status}|{r["audit_notes"]}|')
lines+=['','## 尚未取得完整正文的16篇','', '下面是本次新增50篇中的缺正文DOI；旧任务及缺SI项另见上级《全部需下载文献与用途.md》。','', '```text']+[x['doi'] for x in missing]+['```','','## 三电极优先阅读顺序','','优先复核EXT_005糠醛渣、EXT_007螺旋藻、EXT_008纤维素、EXT_011 Alnus、EXT_013羧甲基纤维素、EXT_014壳聚糖双模板及EXT_015腰果种皮。它们的三电极循环标签已定位；仍需统一检查测试质量分母、基线和特征配对。','', 'EXT_004杜仲木、EXT_009 Tucuma、EXT_010水葫芦和EXT_012聚苯并噁嗪碳存在数字、图文或电解液口径冲突，先审冲突再录标签。EXT_006糖原碳属于DES旁系，保持独立。','']
report='\n'.join(lines).replace('篇含已定位的三电极循环实验','篇优先按三电极循环整理').replace('XML为完整正文文件，包含正文、图注和表格，但多数不内嵌原始图像；需要量化曲线时仍须取得相应高清图。','32份XML已配本地HTML及原图，另有2篇出版社PDF。所有JATS graphic图像引用均有本地对应文件；曲线数值化尚未逐点完成。')
(ROOT/'新增50篇_清单与下载结果.md').write_text(report,encoding='utf-8')
# Retain all inspected leads without inflating the count of 50.
selected={r['doi'] for r in records};extras=[]
special={'OA002':'尿布SAP主要为合成高吸水树脂；生物质范围待核，不计50篇','OA016':'三电极皮革碳，有10,000圈数据；金属残留/原料范围待核，不丢弃资料','OA017':'MnO2复合材料，保留旁系','OA020':'10000圈采用200 mV/s CV，不能作为GCD循环标签','OA027':'间苯二酚/甲醛气凝胶，非已确认生物质来源','OA028':'Ni催化石墨化且有机电解液；保留旁系','OA029':'间苯二酚等合成气凝胶，不计生物质新文献','OA030':'间苯二酚/甲醛气凝胶且三电极，非目标生物质来源','OA035':'有双电极91.85%/5000圈；保留备选，样品N-YAC/N-PAC名称冲突需核','OA037':'循环压缩为机械测试；未定位电化学长循环，不计50篇','OA038':'摘要74.04%为倍率保持率；未定位循环次数，不计50篇','OA042':'有3E/2E数据，但2E5000圈106%来自CV 100 mV/s；单列CV旁系','OA046':'10000圈97.2%为200 mV/s CV循环，单列','OA056':'三电极孔结构/倍率数据有用，但尚未定位长循环，单列特征补充','OA060':'三电极CV 20 mV/s 3000圈95.2%，明确单列CV，不混GCD标签'}
for d in sorted((ROOT/'sources').iterdir()):
    a={}
    for fn in ['acquisition.json','target_metadata.json']:
        if (d/fn).exists():a.update(json.loads((d/fn).read_text(encoding='utf-8')))
    doi=a.get('doi')
    if not doi or doi in selected:continue
    if any(x['doi']==doi for x in extras):continue
    extras.append({'working_id':d.name,'doi':doi,'reason_not_counted_in_50':special.get(d.name,'保留额外发现/待核线索；尚未完成与本篇原始循环测试的完整配对，不计50篇'),'complete_main_files':[str(d/f) for f in ['main.xml','main.pdf'] if (d/f).exists()]})
dump('保留的其它体系与未选线索.json',extras)
dump('扩搜统计.json',stats)
print(json.dumps(stats,ensure_ascii=False,indent=2))
