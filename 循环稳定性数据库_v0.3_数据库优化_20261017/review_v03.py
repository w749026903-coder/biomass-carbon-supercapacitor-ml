"""Explicit incremental review. Preserves raw evidence and all v0.2 history."""
from pathlib import Path
import json,sqlite3,hashlib,sys
sys.stdout.reconfigure(encoding='utf-8')
ROOT=Path(__file__).resolve().parent
def js(v):return json.dumps(v,ensure_ascii=False)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(name,v):(ROOT/name).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')

def main():
 c=sqlite3.connect(ROOT/'cycling_v0_3.sqlite');c.row_factory=sqlite3.Row;c.execute('PRAGMA foreign_keys=ON')
 assert not c.execute("select 1 from metadata where key='v03_review_applied'").fetchone(),'Already applied; use a new increment.'
 sources={(r['paper_id'],r['role']):dict(r) for r in c.execute('select * from source_files')}
 rows={r['record_id']:dict(r) for r in c.execute('select * from endpoint_review')}
 def evidence(paper,role,page,anchor):
  s=sources[(paper,role)]; assert sha(s['path'])==s['sha256']
  pages=json.loads((ROOT/'evidence_text'/f'{paper}_{role}.json').read_text(encoding='utf-8'))
  for p in pages:
   if page is not None and p['page']!=page:continue
   t=' '.join(p['text'].split());i=t.find(anchor)
   if i>=0:return s,t[max(0,i-100):i+len(anchor)+250],p['page']
  raise ValueError((paper,role,page,anchor))
 def event(rid,field,state,value,page,anchor,reason,role='main',locator=None):
  r=rows[rid];s,excerpt,p=evidence(r['paper_id'],role,page,anchor)
  q=c.execute('insert into review_events(record_id,field_name,decision,value_json,source_path,source_sha256,locator,evidence_excerpt,rationale,review_date) values (?,?,?,?,?,?,?,?,?,?)',(rid,field,state,js(value),s['path'],s['sha256'],locator or f'{role} PDF p{p}' if p else (locator or f'{role} document'),excerpt,reason,'2026-10-17'))
  return q.lastrowid
 def change(table,keyfield,key,field,new,why):
  old=c.execute(f'select {field} from {table} where {keyfield}=?',(key,)).fetchone()[0]
  if old!=new:
   c.execute('insert into revision_changes(table_name,row_key,field_name,old_json,new_json,rationale) values (?,?,?,?,?,?)',(table,key,field,js(old),js(new),why))
   c.execute(f'update {table} set {field}=? where {keyfield}=?',(new,key))
 def issue(rid,code,why,scope='endpoint'):
  r=rows[rid];c.execute('insert into issues(paper_id,record_id,severity,code,description,status,source_path,scope) values (?,?,?,?,?,?,?,?)',(r['paper_id'],rid,'high',code,why,'open',sources[(r['paper_id'],'main')]['path'],scope))
 def blocker(rid,code,state,why,review=None):
  c.execute('insert into record_blockers values (?,?,?,?,?)',(rid,code,state,why,review))
 def decision(rid,status,why,checks=None):
  for f,v in {'status':status,'rationale':why,**(checks or {})}.items():change('admissions','record_id',rid,f,v,why)
  for f,v in (checks or {}).items():
   if v==1:c.execute("update record_blockers set status='resolved_by_review',rationale=?,review_id=(select max(review_id) from review_events where record_id=?) where record_id=? and code=?",(why,rid,rid,f))
 def observation(rid,prop,val,unit,method,page,anchor,why,role='main'):
  s,excerpt,p=evidence(rows[rid]['paper_id'],role,page,anchor)
  c.execute('insert into material_observations(material_id,record_id,property_name,value_json,unit,method,stage,source_path,locator,provenance_status) values (?,?,?,?,?,?,?,?,?,?)',(rows[rid]['material_id'],rid,prop,js(val),unit,method,'precycling_as_prepared',s['path'],f'{role} p{p}; {anchor}','verified_v03_scope_bounded'))
  return event(rid,prop,'verified_precycling_scope',val,page,anchor,why,role,locator=f'{role} p{p}; method={method}; unit={unit}; stage=precycling')
 c.executescript('''
 CREATE TABLE record_blockers(record_id TEXT NOT NULL REFERENCES cycling_endpoints,code TEXT NOT NULL,status TEXT NOT NULL CHECK(status IN ('open','resolved_by_review','resolved_by_erratum')),rationale TEXT NOT NULL,review_id INTEGER REFERENCES review_events,PRIMARY KEY(record_id,code));
 CREATE TABLE endpoint_protocol_overrides(record_id TEXT NOT NULL REFERENCES cycling_endpoints,field_name TEXT NOT NULL CHECK(field_name IN ('voltage_lower_V','voltage_upper_V')),value_json TEXT NOT NULL,status TEXT NOT NULL,review_id INTEGER NOT NULL REFERENCES review_events,PRIMARY KEY(record_id,field_name));
 CREATE TABLE validation_links(link_id INTEGER PRIMARY KEY,record_a TEXT REFERENCES cycling_endpoints,record_b TEXT REFERENCES cycling_endpoints,related_doi TEXT,relation TEXT NOT NULL,status TEXT NOT NULL,group_policy TEXT NOT NULL,rationale TEXT NOT NULL,review_id INTEGER REFERENCES review_events);
 CREATE TABLE review_batches(batch_id TEXT PRIMARY KEY,baseline_sha256 TEXT NOT NULL,scope TEXT NOT NULL,policy TEXT NOT NULL);
 ''')
 with c:
  # Every row starts blocked by the existing admission audit; no auto-approval.
  for rid,r in rows.items():
   for f in ['source_checked','material_checked','protocol_checked','baseline_checked','mass_basis_checked','independence_checked','freeze_cleared']:
    if c.execute(f'select {f} from admissions where record_id=?',(rid,)).fetchone()[0]!=1:
     blocker(rid,f,'open','Inherited incomplete admission gate; a later evidence-backed review is required.')
  first12=['R093_CY01','R103_CY01','R104_CY01','R106_CY01','R107_CY01','R107_CY02','R111_CY01','R112_CY02','R112_CY03','SRC035_CY01','SRC123_CY02','SRC124_CY01']
  mass_specs={'R093':(4,'m is the active mass'),'R103':(None,'single electrode'),'R104':(4,'mass of the active material'),'R106':(5,'total mass'),'R107':(3,'total mass'),'R111':(3,'mass of porous carbon'),'R112':(3,'mass of the electrode'),'SRC035':(2,'mass'),'SRC123':(2,'current density of 1 A'),'SRC124':(3,'mass of MHDHPC')}
  for rid in first12:
   paper=rows[rid]['paper_id'];page,anchor=mass_specs[paper];role='supplement' if paper in ['R103','SRC124'] else 'main'
   reason='已检查本地正文/已有SI的方法与循环段：当前仅有电容公式质量、负载或A/g报告，未定位单独定义循环电流I/m中m的直接证据；不从电容公式外推。缺SI的来源仅限当前可读资料。'
   event(rid,'cycle_current_mass_basis','not_located_in_available_evidence',None,page,anchor,reason,role)
  # R106: residue evidence belongs to the specified product, never cross-sample transfer.
  for rid in ['R106_CY01','R106_CY02']:
   eid=event(rid,'material_scope','needs_product_residue_review',None,6,'inherent presence of SiO', '正文两种成品的定性SiO2说明不等于FMC定量硅；FMCA的SI EDS百分比不能搬给FMC。')
   blocker(rid,'silicon_product_scope','open','Clarify carbon/SiO2 product scope without a universal silicon cutoff.',eid)
   issue(rid,'v03_product_silicon_scope','成品SiO2定性证据与材料范围待澄清；不跨FMC/FMCA配对硅数据。','material')
   change('endpoint_features','record_id',rid,'Si_residue_review_required',1,'Product residue review flag, not a silicon exclusion threshold.')
   decision(rid,'frozen_pending_clarification','FMC/FMCA循环电流仍未定位；正文定性SiO2要求成品范围审查，EDS定量仅属于FMCA。',{'source_checked':1})
  observation('R106_CY02','Si_EDS_at_pct',11.68,'at%','SEM-EDS',1,'11.68','仅FMCA成品EDS，不映射FMC或XPS。','supplement')
  observation('R106_CY02','Si_EDS_wt_pct',22.20,'wt%','SEM-EDS',1,'22.20','同一EDS表同时保留质量和原子百分比，不转换。','supplement')
  # R112 visual erratum: 1.2 is an axis tick, traces peak near 1.0 V.
  for rid in ['R112_CY02','R112_CY03']:
   why='v0.2把纵轴最高刻度1.2 V当成循环曲线峰值。放大PDF p13 Fig11c：红/蓝曲线峰值约1.0 V，与p10明确0–1 V一致；更正此前冲突判断，保留全部旧事件与事项。'
   eid=event(rid,'voltage_window_consistency','resolved_by_visual_erratum',{'text_window_V':[0,1],'axis_upper_tick_V':1.2,'trace_peak_approx_V':1.0},13,'Fig. 11.',why,locator='main PDF p10, p13 Fig11c; evidence_images/R112_Fig11c_detail.png')
   blocker(rid,'v02_voltage_axis_interpretation','resolved_by_erratum',why,eid)
   for f,v in [('voltage_lower_V',0.),('voltage_upper_V',1.)]:event(rid,f,'verified_text_and_graph',v,10,'voltage range of 0',why)
   event(rid,'Si_XPS_reported_percent','percent_basis_not_explicit',1.7,6,'Si 2p','Fig4明确Act_OFSCBC成品XPS；该处未明确at%或wt%，保持原百分数，不能强填at%字段。')
   observation(rid,'Si_XPS_reported_percent_unspecified_basis',1.7,'reported %; at/wt unspecified','XPS',6,'Si 2p','属于成品Act_OFSCBC而非原料；严格材料范围尚需澄清。')
   change('endpoint_features','record_id',rid,'Si_residue_review_required',1,'XPS Si is on the tested product; scope review still pending, no cutoff imposed.')
   blocker(rid,'silicon_product_scope','open','Product identity confirmed, percentage basis and permitted carbon/mineral scope remain unresolved.',eid)
   decision(rid,'frozen_pending_clarification','电压旧疑点已通过放大原图更正：曲线约1.0 V，1.2是刻度；仍冻结于硅材料范围、循环电流分母、基线可比性和来源独立性。',{'protocol_checked':1})
   c.execute("update record_blockers set status='resolved_by_erratum',rationale=?,review_id=? where record_id=? and code='protocol_checked'",(why,eid,rid))
  # Shared provisional test: effective protocol must not silently inherit a verified window.
  for f in ['voltage_lower_V','voltage_upper_V']:
   eid=event('R107_CY02',f,'inherited_shared_test_unverified',rows['R107_CY02'][f],7,'Fig. 6.','两万次SI仅直接证实循环次数、电流和电解液；一万次图的窗口由共享暂定测试字段继承。有效核验视图将本节点窗口留空，不拆出未经证明的新测试。')
   c.execute('insert into endpoint_protocol_overrides values (?,?,?,?,?)',('R107_CY02',f,'null','withheld_inherited_protocol',eid))
  eid=event('R107_CY02','test_identity','shared_provisional_identity_pending',rows['R107_CY02']['cycle_test_id'],None,'Fig.S11.','暂不能确认两节点为同一连续测试或独立重复；共同材料/来源必须同组。','supplement')
  c.execute('insert into validation_links(record_a,record_b,relation,status,group_policy,rationale,review_id) values (?,?,?,?,?,?,?)',('R107_CY01','R107_CY02','shared_provisional_cycle_test','pending','must_share_group','No new test or independent material invented.',eid))
  blocker('R107_CY02','inherited_voltage_protocol','open','Await direct 20000-cycle window evidence or an explicit protocol inheritance resolution.',eid)
  # Explicitly record missing SI as an access gap, not an author omission.
  for rid,page,anchor,field in [('R111_CY01',8,'Fig. S3','voltage_window'),('SRC035_CY01',4,'Table S1','total_pore_volume_cm3_g')]:
   eid=event(rid,field,'requires_missing_SI',None,page,anchor,'本地source_files无本篇SI。公开出版社检索未取得可读SI；不称作者未报告，不借三电极窗口或凭图估算。')
   blocker(rid,'missing_SI_for_'+field,'open','Missing local/accessible SI, not established not-reported.',eid)
  # Existing source relation gets a structured endpoint link; no independence clearance.
  eid=event('SRC123_CY02','source_independence','prior_work_overlap_pending',{'related_doi':'10.1016/j.colsurfa.2016.10.009'},2,'RHC','前作身份和近似路线可核，BET差异不足证明独立，尚无完整前作曲线/批次对照。')
  c.execute('insert into validation_links(record_a,related_doi,relation,status,group_policy,rationale,review_id) values (?,?,?,?,?,?,?)',('SRC123_CY02','10.1016/j.colsurfa.2016.10.009','prior_material_or_curve_overlap','pending','if_ingested_union_until_resolved','Cannot assign an independent test group to a potentially reused predecessor.',eid))
  eid=event('R001_CY01','source_independence','prior_work_identified_overlap_pending',{'related_doi':'10.1002/asia.202400622'},13,'e202400622','本篇p2明确building on previous work[17]，p13参考文献与出版社元数据匹配；未读到前作完整曲线，不判复用或独立。')
  c.execute('insert into source_relationships(paper_id,related_doi,relationship,status,note) values (?,?,?,?,?)',('R001','10.1002/asia.202400622','references_authors_2024_honeydew_study','sample_overlap_pending','Local p2 and reference17; official Wiley identity matched. Batch/curve comparison still pending.'))
  c.execute('insert into validation_links(record_a,related_doi,relation,status,group_policy,rationale,review_id) values (?,?,?,?,?,?,?)',('R001_CY01','10.1002/asia.202400622','prior_material_or_curve_overlap','pending','if_ingested_union_until_resolved','Citing prior work alone proves neither reuse nor independence.',eid))
  decision('R001_CY01','frozen_pending_clarification','前作DOI已核，材料/曲线独立性仍待逐图对照；器件窗口及电流质量分母待核。',{'source_checked':1,'baseline_checked':1})
  # R091 genuinely recoverable protocol from figure annotations (not nearby rate plots).
  rid='R091_CY01';why='已目视PDF p8 Fig6g直接印Current density:3 A g−1，5000次、73%；p9明确initial specific capacitance。Table1孔体积原单位m³/g保留冻结，不改成cm³/g。'
  eid=event(rid,'current_density_A_g','verified_cycle_figure_annotation',3.0,8,'Fig. 6','数值来自已目视Fig6g内部标注；文本抽取未识别该字，截图单独保存。',locator='main p8 Fig6g; evidence_images/R091_p8.png')
  change('cycling_tests','cycle_test_id',rows[rid]['cycle_test_id'],'current_density_A_g',3.,why)
  event(rid,'method','verified_constant_current_cycle_figure','GCD',8,'Fig. 6','图6g明确恒电流密度循环，结合方法段GCD；没有借用CV循环。',locator='main p3 electrochemistry and p8 Fig6g')
  change('cycling_tests','cycle_test_id',rows[rid]['cycle_test_id'],'method','GCD',why)
  event(rid,'normalization_reference','verified_author_initial_unspecified_cycle','author_initial_specific_capacitance',9,'initial specific',why)
  observation(rid,'BET_m2_g',1098.07,'m2/g','N2 adsorption; BET',5,'1098.07','Table1成品HPCS-800-2循环前表征。')
  observation(rid,'total_pore_volume_as_printed',0.68,'m3/g as printed; unresolved','N2 adsorption',5,'0.68','不修正原印单位，数值不进入cm3/g模型特征。')
  blocker(rid,'pore_volume_unit','open','m3/g as printed cannot be silently relabeled cm3/g.',eid)
  decision(rid,'conditional_hold',why+'循环电流质量分母、来源独立性及旧冻结仍未清。',{'source_checked':1,'material_checked':1,'protocol_checked':1,'baseline_checked':1})
  for code in ['source_checked','material_checked','protocol_checked','baseline_checked']:
   c.execute("update record_blockers set status='resolved_by_erratum',rationale=?,review_id=? where record_id=? and code=?",(why,eid,rid,code))
  # Other recoverable/scope-pending sources: retain disqualifying distinctions.
  secondary={
   'R017_CY01':(13,'5000','conditional_hold','原标签为more than 99%，摘要/正文近完全保持不提供更精确点值；gt保留，排除严格精确标签集。'),
   'R017_CY02':(13,'two-','conditional_hold','一千次KOH节点未取得直接数值标签，不图读生成精确值。'),
   'R020_CY01':(None,'89','conditional_hold','AC对照保持约89%，继续保留approx，复合样品不进入主体系。'),
   'R033_CY02':(6,'2.040','frozen_pending_clarification','正文称SSC但正负极活性物2.040/2.872 mg，按本项目定义属同碳质量不平衡；99.9%/86%对应关系也仍需SI，不能只挑较高标签。'),
   'R087_CY01':(3,'three-electrode setup','outside_primary_scope','方法段明确铂辅助/饱和甘汞参比的三电极体系；不再把system_pending当潜在两电极主来源。'),
   'R092_CY01':(8,'89.72','frozen_pending_clarification','正文使用约89.72%，摘要up to；体系与原标签冲突未解决，表征引用前作，不直接配对未掺碘前体BET。'),
   'R105_CY01':(7,'close to 100','conditional_hold','摘要100%与正文close to100%限定并存，保留approx，不用摘要消除正文限定。'),
   'R108_CY05':(9,'Fig. 6.','conditional_hold','图6e直接标20 mA/cm²、15000次92.0%；不换算A/g。窗口需进一步与器件协议核对，仍非严格A/g主集。'),
   'SRC093_CY01':(12,'2.0 mA','conditional_hold','图8给0–0.8V和2.0 mA/cm²，正文单位排版为cm−1但图注明确cm−2；保留面电流而不臆造质量换算，约78%不升级精确。'),
   'SRC112_CY01':(11,'approximately 106','conditional_hold','正文明确approximately106%，不升级精确；有效活性碳负载计算不能替代循环电流分母定义。'),
   'SRC120_CY01':(13,'79.4','frozen_pending_clarification','Table5本作79.4%而正文p15为79%；保留approx79并登记数值分歧，不选79.4或升级eq。'),
   'SRC123_CY01':(3,'approximately 90.1','frozen_pending_clarification','两千次为approximately90.1%，修正当前关系eq为approx；与一万次同曲线同材料，继承前作复用未决。'),
   'SRC125_CY01':(16,'around 93.89','frozen_pending_clarification','正文SCB对照around93.89%，摘要却把93.89%赋给KOH活化材料，材料标签分歧；保留原数值并降为approx。'),
   'SRC125_CY02':(15,'over 98.43','frozen_pending_clarification','正文over98.43%，结论精确98.43%；另有引言94.7%和摘要93.89%需核对应，当前关系用gt保留明确限定，继续冻结。')
  }
  for rid,(page,anchor,status,why) in secondary.items():
   eid=event(rid,'v03_record_review','bounded_review_no_admission',None,page,anchor,why)
   decision(rid,status,why,{'source_checked':1})
   blocker(rid,'v03_specific_review_gap','open',why,eid)
  for rid in ['SRC028_CY01','SRC028_CY02','SRC028_CY03','SRC028_CY04','SRC028_CY05','SRC028_CY06']:
   why='正文p8的六个成品/循环值有对应；使用含Zn盐熔盐不自动证明残留，也不自动证明纯碳。缺成品残留核验，仍为carbon_metal_residue_pending。'
   eid=event(rid,'material_scope','metal_residue_not_cleared',None,8,'cycling stability',why)
   decision(rid,'frozen_pending_clarification',why,{'source_checked':1})
   blocker(rid,'metal_residue_scope','open',why,eid)
  # Real field corrections, all chained. Original raw values/evidence retained.
  change('cycling_tests','cycle_test_id',rows['R087_CY01']['cycle_test_id'],'system','3E','Main p3 explicitly three-electrode setup.')
  change('cycling_tests','cycle_test_id',rows['R033_CY02']['cycle_test_id'],'system','2E_same_carbon_mass_unbalanced','Main p6 explicitly unequal active masses 2.040 and 2.872 mg; scope definition unchanged.')
  for rid,relation in [('SRC123_CY01','approx'),('SRC125_CY01','approx'),('SRC125_CY02','gt')]:change('cycling_endpoints','record_id',rid,'retention_relation',relation,'Preserve explicit approximate/bound wording in source; original eq remains in raw_records and change history.')
  for rid in ['SRC120_CY01','SRC125_CY01','SRC125_CY02']:
   change('cycling_endpoints','record_id',rid,'conflict',1,'Unresolved within-source numeric/material assignment conflict documented in v0.3.')
   issue(rid,'v03_label_or_assignment_conflict',secondary[rid][3],'label')
  for rid,val,page,anchor in [('R108_CY05',20.,9,'Fig. 6.'),('SRC093_CY01',2.,12,'2.0 mA')]:
   event(rid,'current_density_mA_cm2','verified_cycle_graph_or_caption',val,page,anchor,'保留原面电流单位，不使用不明负载换算A/g。',locator=f'main p{page}; cycling figure annotation/caption')
   change('cycling_tests','cycle_test_id',rows[rid]['cycle_test_id'],'current_density_mA_cm2',val,'Direct cycling figure annotation/caption, not a rate-test current.')
  for f,v in [('voltage_lower_V',0.),('voltage_upper_V',0.8)]:
   event('SRC093_CY01',f,'verified_device_figure_caption',v,12,'0.0','Fig8给AC3全电池窗口；保留面电流和approx标签。')
   change('cycling_tests','cycle_test_id',rows['SRC093_CY01']['cycle_test_id'],f,v,'Main p12 Fig8 caption full-cell range.')
  for rid in ['SRC125_CY01','SRC125_CY02']:
   event(rid,'current_density_A_g','verified_cycle_caption',5.,16,'constant current density 5','图12循环图注明确5 A/g；标签冲突和范围冻结不解除。')
   change('cycling_tests','cycle_test_id',rows[rid]['cycle_test_id'],'current_density_A_g',5.,'Main p16 Fig12 caption explicitly cycling at 5 A/g.')
  # Stage/method-rich process observations, kept outside current model feature sets.
  for prop,v,u in [('carbonization_temperature_C',550,'C'),('carbonization_duration_h',2,'h'),('activation_temperature_C',700,'C'),('activation_duration_h',1,'h'),('KOH_to_PC_mass_ratio',4,'g/g')]:
   observation('R111_CY01',prop,v,u,'reported synthesis',2,'550','ACK-700制备信息；预碳化与活化分开，不改模型特征集。')
  for prop,v,u in [('carbonization_temperature_C',600,'C'),('carbonization_duration_h',2,'h'),('activation_temperature_C',800,'C'),('activation_duration_h',2,'h'),('KOH_to_carbon_mass_ratio',4,'g/g')]:
   observation('R107_CY01',prop,v,u,'reported synthesis',2,'Carbonization-activation','DUGPC前处理后碳化/活化信息，未引入循环后信号。')
  # Shared curves/materials never become independent rows for validation.
  for a,b,why in [('R112_CY02','R112_CY03','Same Fig11c curve, two endpoints.'),('SRC123_CY01','SRC123_CY02','Same equal-mass RHC cycling curve, two endpoints.')]:
   c.execute('insert into validation_links(record_a,record_b,relation,status,group_policy,rationale) values (?,?,?,?,?,?)',(a,b,'shared_curve_material','documented','must_share_group',why))
  cols=[r[1] for r in c.execute('pragma table_info(endpoint_review)')]
  expressions=[]
  for col in cols:
   if col in ['voltage_lower_V','voltage_upper_V']:
    expressions.append(f"CASE WHEN EXISTS(SELECT 1 FROM endpoint_protocol_overrides o WHERE o.record_id=e.record_id AND o.field_name='{col}') THEN (SELECT json_extract(o.value_json,'$') FROM endpoint_protocol_overrides o WHERE o.record_id=e.record_id AND o.field_name='{col}') ELSE e.{col} END AS {col}")
   else:expressions.append('e.'+col)
  c.execute('CREATE VIEW endpoint_effective_review AS SELECT '+','.join(expressions)+' FROM endpoint_review e')
  c.execute('DROP VIEW training_ready')
  c.execute('''CREATE VIEW training_ready AS SELECT e.* FROM endpoint_effective_review e
   JOIN admissions a USING(record_id)
   WHERE e.system='2E_symmetric' AND e.method='GCD' AND e.metric_kind='capacitance_retention'
   AND e.material_scope IN ('carbon_candidate','carbon_control') AND e.retention_relation='eq'
   AND e.retention_pct IS NOT NULL AND e.cycle_count>=1000 AND e.conflict=0 AND e.short_test=0
   AND e.category IN ('A','B') AND e.Si_residue_review_required=0
   AND a.eligible=1 AND a.status='approved' AND a.source_checked=1 AND a.material_checked=1
   AND a.protocol_checked=1 AND a.baseline_checked=1 AND a.mass_basis_checked=1
   AND a.independence_checked=1 AND a.freeze_cleared=1
   AND e.current_density_A_g>0 AND e.electrolyte IS NOT NULL AND e.concentration_value>0
   AND e.concentration_unit IS NOT NULL AND e.voltage_lower_V IS NOT NULL AND e.voltage_upper_V>e.voltage_lower_V
   AND NOT EXISTS(SELECT 1 FROM record_blockers b WHERE b.record_id=e.record_id AND b.status='open')''')
  for key,val in [('schema_version','0.3_candidate_review'),('v03_review_applied','2026-10-17'),('v03_baseline_sha256','35d4bbf895501ec306ea215b40f865cc5d1da4e7959173d73e279dd3eaaa22fa')]:
   old=c.execute('select value from metadata where key=?',(key,)).fetchone()
   if old:change('metadata','key',key,'value',val,'v0.3 incremental review metadata; immediate parent hash stored separately.')
   else:c.execute('insert into metadata values (?,?)',(key,val))
  c.execute('insert into review_batches values (?,?,?,?)',('v03_20261017',sha(ROOT.parent/'循环稳定性数据库_v0.2_20261017/cycling_v0_2.sqlite'),'12 original endpoints plus remaining potentially recoverable primary-system sources','No research training; exact-label and mass-basis gates unchanged; visual errata appended.'))
  assert c.execute('pragma foreign_key_check').fetchall()==[]
  assert c.execute('select count(*) from training_ready').fetchone()[0]==0
 c.close(); print('Incremental v0.3 review committed. No admissions or research training.')
if __name__=='__main__':main()
