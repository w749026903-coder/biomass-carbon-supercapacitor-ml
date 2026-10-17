from pathlib import Path
import json,hashlib,collections,sqlite3,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1];OUT=Path(__file__).resolve().parent
def read(p):return json.loads(Path(p).read_text('utf-8'))
def dump(n,x):(OUT/n).write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8',newline='\n')
def lines(n,dois):(OUT/n).write_text('\n'.join(sorted(set(dois)))+'\n',encoding='utf-8')
if __name__=='__main__':
 ledger=read(OUT/'三电极端点_53条.json')['rows'];counts=read(OUT/'endpoint_counts.json');lib=read(OUT/'文献类型分类索引.json')
 acquisition=[]
 for n in ['new_acquisition.json','older_acquisition.json','older2_acquisition.json','older3_acquisition.json']:acquisition+=read(OUT/n)
 pending=read(ROOT/'用户补充文献核验_20261018/待补资料_更新.json');si=pending['main_received_but_declared_SI_missing_or_existing_SI_only_task']
 available={r['doi'] for r in acquisition};missing=[r for r in pending['missing_main'] if r['doi'].lower() not in available]
 dump('仍需下载资料_逐项DOI.json',{'scope':'Unresolved prior target components, not a claim that other studies have no SI. A valid full-text XML plus original figures is available full text, even when publisher PDF could not be fetched.','missing_main':missing,'missing_SI':si,'SI_attempt_log':'old_si_download_attempts.json','missing_main_recheck':'old_pending_epmc_recheck.json','known_obtained_round3':pending['already_acquired_in_database_round3']})
 lines('仍缺正文_完整DOI.txt',[r['doi'] for r in missing]);lines('仍需SI_完整DOI.txt',[r['doi'] for r in si]);lines('仍需下载_全部DOI.txt',[r['doi'] for r in missing+si]);lines('已获XML原图但未获出版社PDF_完整DOI.txt',[r['doi'] for r in ledger if r['source_tag'].startswith('PMC')])
 selected={r['source_tag'] for r in ledger};screen=[]
 explicit={
 'PMC10958655':('excluded_2E_cycle','Figure7 caption explicitly says two-electrode cell; original 3E characterization cannot label its 50000-cycle endpoint 3E.'),
 'PMC6841744':('hold_system_ambiguous','Fig15 calls it a device; prose and three-electrode methods do not uniquely bind that cycling test.72.88%/6000 not counted.'),
 'PMC11357087':('excluded_2E_cycle_and_value_conflict','Fig8 two-electrode lifecycle and text100% vs conclusion95.08%; not a 3E endpoint.'),
 'PMC7564396':('excluded_2E_cycle','NSATC4/ATC3 Fig7 assembled devices; not 3E cycling.'),
 'PMC9655081':('excluded_2E_cycle','HPC70098.59%/30000 explicitly two-electrode; not counted.'),
 'PMC9597690':('excluded_2E_cycle','AWCK lifecycle belongs to assembled symmetric device.'),
 'PMC13006829':('hold_conflict','Own cycling descriptions and symmetric-device conclusion need resolution; not counted.'),
 }
 for r in acquisition:
  tag=r['pmcid'];status,note=('counted_3E_GCD','See endpoint ledger; same-paper group retained') if tag in selected else explicit.get(tag,('screening_only_not_counted','Retrieved original XML retained for screening. No endpoint admitted on abstract, cited comparison tables, or unverified curves.'))
  screen.append({'pmcid':tag,'doi':r['doi'],'title':r['title'],'source_path':r['source_path'],'sha256':r['sha256'],'status':status,'reason':note,'training_admitted':False})
 dump('公开正文130篇_筛选状态.json',screen)
 base=[]
 for r in read(OUT/'existing_29_full.json'):
  tag='B_'+r['paper']['paper_id'];base.append({'paper_id':r['paper']['paper_id'],'doi':r['paper']['doi'],'legacy_endpoint':r['endpoint'],'legacy_test':r['test'],'current_counted_endpoints':[e['endpoint_id'] for e in ledger if e['source_tag']==tag],'legacy_status_preserved':True,'note':'A legacy record is not automatically a verified 3E GCD point. CV, bounds, composites, missing N/retention, conflicts and protocol holds remain separate.'})
 dump('原29条_与本轮计数对照.json',base)
 dump('视觉核验记录.json',[
  {'pmcid':'PMC12158216','figure':'Fig7','file':'new_sources/PMC12158216/assets/polymers-17-01544-g007.jpg','finding':'5000cycles,93.7% explicitly labeled; agrees with P0019.'},
  {'pmcid':'PMC6401840','figure':'Fig7c','file':'new_sources/PMC6401840/assets/polymers-10-01306-g007.jpg','finding':'Specific-capacitance lifecycle to2000; sample/current assigned by original caption, retention88.8 by original body, not inferred from pixels.'},
  {'pmcid':'PMC8707477','figure':'Fig8a','file':'new_sources/PMC8707477/assets/nanomaterials-11-03175-g008.jpg','finding':'Three LTSC samples to10000; retain only original reported K9000.3% loss=>99.7; not fabricated values for two other curves.'},
  {'pmcid':'PMC13400085','figure':'Fig7C','file':'new_sources/PMC13400085/assets/d6na00276e-f7.jpg','finding':'AC control83.54%/10000 and inset5A/g. Body coulombic efficiency75 vs figure85 conflicts; neither used as capacitance retention.'}])
 pkgs=[read(p) for p in (OUT/'new_sources').glob('*/figure_package_acquisition.json')];docs=[(p['pmcid'],f['file']) for p in pkgs if p['pmcid'] in selected for f in p.get('files',[]) if Path(f['file']).suffix.lower() in ['.pdf','.doc','.docx','.xls','.xlsx']]
 dump('新增已取得补充文档.json',[{'pmcid':t,'file':'new_sources/'+t+'/'+f,'purpose':'Same-paper original SI, retained with primary XML and original figure package; not a separate study.'} for t,f in docs])
 summary=f'''# 三电极端点扩充与文献类型整理：交接

日期：2026-10-18。独立文献证据批次，不修改任何旧数据库、原文或共同契约。

已达到“超过50个三电极端点”的文献收集数量目标：**53个3E-GCD循环端点，来自41篇论文**。其中43个原文明确报告的点值、6个原文近似值、4个按原文损失率计算的100−损失率值；后三类在JSON和阅读清单中分开。若后续模型只接受未经换算的精确点值，本批对应43条，不能说53条都符合该更窄标准。端点不是独立论文、独立训练样本或最终准入数。

## 打开入口

- [53个端点与原文定位](三电极端点清单.html)，机器可读[完整端点记录](三电极端点_53条.json)。
- [按文献类型浏览](文献类型目录.html)，[身份、原路径和仓库来源映射](文献类型分类索引.json)。本机分类副本入口为 `D:/文献/按文献类型_20261018/打开按类型分类目录.html`。
- [仍需下载的全部DOI](仍需下载_全部DOI.txt)：正文{len(missing)}个DOI、SI{len(si)}个DOI；分件见[用途和缺件清单](仍需下载资料_逐项DOI.json)。
- [已获XML/原图但未获出版社PDF的DOI](已获XML原图但未获出版社PDF_完整DOI.txt)。这些19篇有完整正文，不应误计为缺全文。

## 获取与筛选

本轮从Europe PMC官方开放接口取得130份完整XML正文（130个DOI，其中6个已在原126篇身份表内，不声称130个都是库外新论文）。取得21份原图/SI压缩包，其中19篇进入本轮三电极证据集，另2份用于排除/存疑核验。本轮计数的19篇均有本地完整XML、原图和HTML阅读版；其中{len(set(t for t,f in docs))}篇另有{len(docs)}份独立补充文档。读取XML中位于文末floats-group的图表，避免漏图。公开PDF请求返回403或证书/协议错误时保留XML阅读版，没有把网页保存成PDF，也未关闭TLS或尝试权限绕过。

原来取得的正文和用户补充PDF继续使用；本轮从已有资料核定31个端点，从新取得正文核定22个端点，共53个。旧29条3E标记不是29条均可用：[逐条对照](原29条_与本轮计数对照.json)。

新增130篇的筛选身份见[筛选状态](公开正文130篇_筛选状态.json)。未进入本轮端点集的XML为检索暂存，不自动进入实验库或用于训练。紫茉莉AC-10%的50000圈图注明确2E，已排除；KHC的6000圈循环配置绑定仍有歧义，保留待核。综述引用表、倍率保持率、库仑效率、CV循环和器件循环均不冒充3E-GCD目标。

## 文献类型分类

新分类视图有**217个去重文献身份**：机器学习综述4；机器学习/统计建模原始研究17；原始实验研究179；材料与储能综述10；其它主题综述4；书籍/章节3。机器学习建模研究不自动等于新实验，PCA研究单列在建模类；旧目录A/B/C/D/E是用途分类，不能替代本次文献类型。原始实验类包括仍须核验循环配置、旁系材料和范围外应用，均有用途/端点标记，不能把179篇全部当作训练资料。

本机使用新增目录 `D:/文献/按文献类型_20261018/` 保存分类副本和逐篇身份说明，旧目录、根目录26份原件与数据库引用路径保留。DOI或内容SHA相同的版本只算一个身份，原编号保留为别名；SI跟随同篇论文，不另算论文。复制记录及原件/副本SHA见[分类复制核验](分类复制与原件哈希.json)。远程合作人使用仓库索引的相对路径；原127份来源可依[可移植来源表](../data/source_locations_portable.json)定位到文件或压缩包成员。不要把分类副本与旧原件相加。

## 边界与下一步

48条定位到A/g循环电流，1条为1mA/cm²（不转成A/g），4条循环电流未定位。2条为混合前驱体（尿布纤维/SAP、木质素/PAN）单独标记；不默认为纯生物质范围。近似值、损失率换算、缺浓度、缺循环窗口、缺基线与质量分母等均按字段保留。图7C中AC库仑效率正文/图示75/85的冲突保留，83.54%的电容保持率一致；没有用库仑效率替换目标。

**训练准入0，研究拟合0，科学合并0。**下一步由数据库/合并负责人按本批manifest审材料身份、重复/前作关系、循环窗口、质量分母、起始基线及7项输入完整性，并先修订3E/2E分队列规则。不得将本批复制直接覆盖旧数据库，不得为得到非零训练条数而放宽规则。

## 复核与重现

本目录下载脚本是本批获取记录，含网络和写入操作，**不要为查看结果直接重跑**。`build_delivery.py`还会写外部分类副本目录；换电脑时按索引定位已交付来源即可。`validate_delivery.py`只核验文件/哈希/计数与链接，可单独运行，不访问网络、不训练。验证结果见 `核验结果.json`。`protected_fingerprints.json`保护6个旧SQLite与原共同契约。

Git任务收尾按根AGENTS：仅提交本目录及本任务入口文档与进度增量，正常push到已核实origin/main，并比较远程SHA；外部D:/文献副本不属于Git仓库，Git内保存可重建的类型索引和来源映射。
'''
 (OUT/'README.md').write_text(summary,encoding='utf-8',newline='\n')
 (OUT/'仍需下载资料与用途.md').write_text('# 待补件及完整 DOI\n\n这里区分缺正文、缺SI和只缺出版社PDF；不要重复下载已取得正文。\n\n## 缺正文\n\n'+ '\n'.join('- **'+r['doi']+'** — '+r.get('title','')+'；'+r.get('purpose','') for r in missing)+'\n\n## 正文已有、仍缺SI\n\n'+'\n'.join('- **'+r['doi']+'** — '+r.get('title','')+'；'+r.get('purpose','') for r in si)+'\n\n本轮旧SI再次尝试结果见 `old_si_download_attempts.json`；部分直连为出版社常用路由候选，失败不证明SI不存在。通过403、协议错误或未定位直链的条目保留待补。原来已取得的R111/SRC035等SI继续有效。\n',encoding='utf-8')
 print('REPORT_READY',counts,'SI_docs',len(docs),'SI_papers',len(set(t for t,f in docs)))
