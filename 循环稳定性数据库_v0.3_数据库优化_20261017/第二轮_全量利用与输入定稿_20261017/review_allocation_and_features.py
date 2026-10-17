"""Second evidence-bounded increment, with all-row allocation and targeted recovery."""
from pathlib import Path
import json,sqlite3,hashlib,sys
sys.stdout.reconfigure(encoding='utf-8');ROOT=Path(__file__).resolve().parent
def js(v):return json.dumps(v,ensure_ascii=False)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(name,v):(ROOT/name).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def main():
 c=sqlite3.connect(ROOT/'cycling_v0_3r2.sqlite');c.row_factory=sqlite3.Row;c.execute('pragma foreign_keys=ON')
 assert not c.execute("select 1 from metadata where key='r2_applied'").fetchone()
 inv=json.loads((ROOT/'source_inventory_all137.json').read_text(encoding='utf-8'))
 records={r['record_id']:dict(r) for r in c.execute('select * from endpoint_effective_review')}
 def evidence(pid,page,anchor,role='main'):
  src=next(f for f in inv if f['paper_id']==pid and f['role']==role)
  assert sha(src['path'])==src['sha256']
  for p in json.loads(Path(src['extraction_path']).read_text(encoding='utf-8')):
   if page is not None and p['page']!=page:continue
   t=' '.join(p['text'].split());i=t.find(anchor)
   if i>=0:return src,t[max(0,i-100):i+len(anchor)+350]
  raise ValueError((pid,page,anchor))
 def event(rid,field,decision,value,page,anchor,why,method=None,unit=None):
  src,text=evidence(records[rid]['paper_id'],page,anchor)
  loc=f'main PDF p{page}; {anchor}'+(f'; method={method}; unit={unit}; precycling_as_prepared' if method else '')
  cur=c.execute('insert into review_events(record_id,field_name,decision,value_json,source_path,source_sha256,locator,evidence_excerpt,rationale,review_date) values (?,?,?,?,?,?,?,?,?,?)',(rid,field,decision,js(value),src['path'],src['sha256'],loc,text,why,'2026-10-17'))
  return cur.lastrowid
 def change(t,keycol,key,field,value,why):
  old=c.execute(f'select {field} from {t} where {keycol}=?',(key,)).fetchone()[0]
  if old!=value:
   c.execute('insert into revision_changes(table_name,row_key,field_name,old_json,new_json,rationale) values (?,?,?,?,?,?)',(t,key,field,js(old),js(value),why))
   c.execute(f'update {t} set {field}=? where {keycol}=?',(value,key))
 def obs(rid,field,value,unit,method,page,anchor,why,to_endpoint=False):
  src,text=evidence(records[rid]['paper_id'],page,anchor)
  eid=event(rid,field,'verified_precycling_property_scope',value,page,anchor,why,method,unit)
  c.execute('insert into material_observations(material_id,record_id,property_name,value_json,unit,method,stage,source_path,locator,provenance_status) values (?,?,?,?,?,?,?,?,?,?)',(records[rid]['material_id'],rid,field,js(value),unit,method,'precycling_as_prepared',src['path'],f'PDF p{page}; {anchor}','verified_r2_scope_bounded'))
  if to_endpoint:change('endpoint_features','record_id',rid,field,value,why)
  return eid
 c.executescript('''
 CREATE TABLE utilization_routes(record_id TEXT PRIMARY KEY REFERENCES cycling_endpoints,track TEXT NOT NULL,label_tier TEXT NOT NULL,usable_role TEXT NOT NULL,main_eligible INTEGER NOT NULL CHECK(main_eligible=0),reason TEXT NOT NULL,review_extent TEXT NOT NULL);
 CREATE TABLE paper_utilization(paper_id TEXT PRIMARY KEY REFERENCES papers,use_role TEXT NOT NULL,existing_endpoint_count INTEGER NOT NULL,search_hits INTEGER NOT NULL,decision_extent TEXT NOT NULL,reason TEXT NOT NULL);
 CREATE TABLE staged_recovery_endpoints(candidate_id TEXT PRIMARY KEY,paper_id TEXT NOT NULL REFERENCES papers,material_id TEXT REFERENCES materials,sample_name TEXT,system TEXT,method TEXT,metric_kind TEXT,cycle_count INTEGER,retention_pct REAL,retention_relation TEXT,current_density_A_g REAL,electrolyte TEXT,concentration_value REAL,concentration_unit TEXT,voltage_lower_V REAL,voltage_upper_V REAL,source_path TEXT NOT NULL,source_sha256 TEXT NOT NULL,locator TEXT NOT NULL,evidence_excerpt TEXT NOT NULL,rationale TEXT NOT NULL,eligible INTEGER NOT NULL CHECK(eligible=0));
 ''')
 with c:
  # Same prepared material, two systems: transfer only directly identified precycling properties.
  for rid in ['R013_CY01','R013_CY02']:
   obs(rid,'BET_m2_g',1589.0,'m2/g','N2-BET',1,'1589.0','摘要/表2均指EUAC1-60成品；跨该材料两种测试只共享循环前结构，不共享协议和标签。',True)
   obs(rid,'total_pore_volume_cm3_g',0.82,'cm3/g','N2 sorption; table total volume',1,'0.82','EUAC1-60总孔体积；微/介孔子项叙述差异不改变该总量，子项另待审。',True)
  obs('R013_CY01','Raman_ID_IG',0.92,'dimensionless','Raman intensity ID/IG',5,'0.92','Raman比值定义按ID/IG保存，不和IG/ID倒置。')
  for rid in ['R069_CY02','R069_CY03']:
   why='p7正文按KOH/Na2SO4/H2SO4列97.2/93.6/84.8%，p8 Table2按Na2SO4/H2SO4列84.8/93.6%；不自动交换现值，先冻结电解液-标签配对。'
   eid=event(rid,'electrolyte_retention_pairing','conflict_body_vs_table',{'body':{'Na2SO4':93.6,'H2SO4':84.8},'table':{'Na2SO4':84.8,'H2SO4':93.6}},7,'Cyclic stability of 97.2',why)
   change('cycling_endpoints','record_id',rid,'conflict',1,why)
   change('admissions','record_id',rid,'status','frozen_pending_clarification',why)
   change('admissions','record_id',rid,'rationale',why,why)
   c.execute('insert into issues(paper_id,record_id,severity,code,description,status,source_path,scope) values (?,?,?,?,?,?,?,?)',('R069',rid,'high','r2_electrolyte_label_pairing_conflict',why,'open',records[rid]['evidence_path'],'label_protocol_pair'))
   c.execute('insert into record_blockers values (?,?,?,?,?)',(rid,'r2_electrolyte_label_pairing','open',why,eid))
  for rid in ['R069_CY01','R069_CY02','R069_CY03']:obs(rid,'BET_m2_g',1917.0,'m2/g','N2-BET',4,'1917','同成品RCS-AC循环前BET；不解决不同电解液标签归属冲突。',True)
  for field,v,u,method in [('BET_m2_g',2074.72,'m2/g','N2-BET'),('total_pore_volume_cm3_g',0.930,'cm3/g','N2 sorption; total pore volume')]:
   obs('R078_CY01',field,v,u,method,3,'2074.72','C/600C成品循环前属性，明确三电极循环，不能据此新增两电极标签。',True)
  obs('R085_CY01','BET_m2_g',582.9,'m2/g','N2-BET',6,'582.9','Table1明确NPCA-600-0.5成品BET。',True)
  eid=obs('R085_CY01','micropore_volume_cm3_g',0.187,'cm3/g','t-plot micropore volume',6,'V mic','Table1脚注明确Vmicro，保留为微孔体积；total_pore_volume_cm3_g仍空，不能扩大总孔覆盖。')
  event('R085_CY01','total_pore_volume_cm3_g','not_located_micropore_not_total',None,6,'V mic','摘要笼统pore volume的0.187须由表头具体定义为微孔体积，不能当总孔体积。')
  for rid,bet,pore,anchor in [('R117_CY01',3345.,2.0,'3345'),('R117_CY02',1253.,0.5,'1253')]:
   obs(rid,'BET_m2_g',bet,'m2/g','N2-BET',6,anchor,'成品ACRS-700/ACEW-700分开配对，循环标签未报告可直接摘录的点值，不从图粗造。',True)
   obs(rid,'total_pore_volume_cm3_g',pore,'cm3/g','N2 sorption; reported total pore volume',6,'2.0 cm','本段比较两成品总孔体积2.0/0.5，和BET一起按样品配对。',True)
   eid=event(rid,'cycle_current_mass_basis','verified_direct_I_over_m','single_working_electrode_active_material',3,'I/m stands for current density','正文明确m为ACRS/ACEW活性物，且直接定义I/m为电流密度；对应本段三电极测试。不得搬成两电极总质量定义。')
   change('cycling_tests','cycle_test_id',records[rid]['cycle_test_id'],'mass_basis','single_working_electrode_active_material','Direct I/m definition in three-electrode methods, not capacitance-formula inference.')
   change('admissions','record_id',rid,'mass_basis_checked',1,'Direct current/mass definition found for this three-electrode record only.')
   c.execute("update record_blockers set status='resolved_by_review',rationale=?,review_id=? where record_id=? and code='mass_basis_checked'",('Direct I/m and active material definition in main p3, limited to this 3E protocol.',eid,rid))
  obs('SRC121_CY01','BET_m2_g',1374.,'m2/g','N2-BET',4,'1374','DSAC成品BET；未从450 cc/g吸附量推算孔体积。',True)
  obs('SRC121_CY01','Raman_ID_IG',0.98,'dimensionless','Raman ID/IG',4,'0.98','原文约0.98，单独注明近似表征，不改变精确保持率标签。')
  obs('SRC121_CY01','mass_loading_mg_cm2',0.5,'mg/cm2','reported DSAC active loading on GCE',3,'0.5 mg','仅限本三电极GCE负载，不迁移到作者估算的full-device指标。',True)
  # Product scope is material-level: the same R112 product in 3E is not magically cleared.
  why='R112三电极与器件均为Act_OFSCBC成品；p6/8 Si-XPS材料范围问题同样涉及该材料，未设硅阈值。'
  eid=event('R112_CY01','material_scope','shared_product_scope_pending',None,6,'Si 2p',why)
  change('endpoint_features','record_id','R112_CY01','Si_residue_review_required',1,why)
  c.execute('insert into record_blockers values (?,?,?,?,?)',('R112_CY01','r2_shared_product_silicon_scope','open',why,eid))
  # New findings are staging only, separate from the 89 official endpoint records.
  staged=[
   ('REC_001','SRC025','SRC025::AC3','AC3','2E_symmetric_gel','GCD','capacitance_retention',5000,98.,'eq',10.,'PVA/KOH',2.,'M',0.,1.,10,'gravimetric capacitance retention of 98','原候选只含三电极；本次定位正文/图7g凝胶器件98%，不得搬给液体KOH器件；分母/基线/独立性仍待审。'),
   ('REC_002','R031',None,'Cyperus_pangorei_carbon','gel_system_unspecified','GCD','capacitance_stability_qualitative',400,None,'approx',50.,'PVA/Na2SO4',None,None,0.,1.5,7,'400 continuous','400次短循环，20圈前有活化；没有直接末端保持率点值，不能由168/154造标签。体系电极数待审。'),
   ('REC_003','SRC005',None,'MC-S-3@NF','3E','CV','oxidation_peak_current_trend',2500,None,'approx',None,'KOH',3.,'M',None,None,8,'oxidation peak currents','CV氧化峰电流随循环变化，不是GCD电容保持率；保留方法旁系，不能从电流趋势造保持率。')]
  for x in staged:
   cid,pid,mid,sample,system,method,metric,n,y,relation,current,el,conc,unit,lo,hi,page,anchor,reason=x
   s,text=evidence(pid,page,anchor)
   c.execute('insert into staged_recovery_endpoints values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(cid,pid,mid,sample,system,method,metric,n,y,relation,current,el,conc,unit,lo,hi,s['path'],s['sha256'],f'PDF p{page}; {anchor}',text,reason,0))
  # All89 receive an explicit use; none gain approval from allocation alone.
  for rid,r in records.items():
   if r['system'] in ['Zn_hybrid','Li_half_cell']:track='hybrid_or_half_cell_reference'
   elif r['material_scope'] not in ['carbon_candidate','carbon_control','carbon_candidate_gel_separate','carbon_candidate_pending_protocol','carbon_field_freeze','carbon_originality_pending','carbon_metal_residue_pending'] or r['Si_residue_review_required']:track='material_scope_or_composite_hold'
   elif 'mass_unbalanced' in r['system']:track='mass_unbalanced_separate'
   elif 'gel' in r['system']:track='gel_separate'
   elif r['method']=='CV':track='CV_cycle_separate'
   elif r['system']=='3E':track='three_electrode_GCD_separate'
   elif r['system']=='2E_symmetric' and r['method']=='GCD':track='aqueous_symmetric_GCD_candidate'
   else:track='protocol_or_system_pending'
   label='target_missing' if r['retention_pct'] is None else 'conflicting' if r['conflict'] or rid in ['R069_CY02','R069_CY03'] else 'short_cycle' if r['short_test'] else 'approximate' if r['retention_relation']=='approx' else 'lower_bound' if r['retention_relation']=='gt' else 'reported_point'
   extent='targeted_source_review_this_round' if rid in [x[0] for x in c.execute('select distinct record_id from review_events where review_id>154')] else 'explicit_routing_from_curated_parent_not_new_field_clearance'
   c.execute('insert into utilization_routes values (?,?,?,?,?,?,?)',(rid,track,label,'separate_review_and_descriptive_use_no_fitting',0,'体系/方法/材料/标签精度分开利用；沿用全部冻结与准入门槛，不能将分配用途当通过。',extent))
  srcs=json.loads((ROOT/'全126篇利用登记_初筛.json').read_text(encoding='utf-8'))
  explicit={'R005':'本篇新样品的循环终点未定位；文献汇总不当新实验，供方法与特征词典参考。','R031':'短循环凝胶体系，已新增REC_002待审；不造末端保持率。','R053':'检索命中±6%为CV仪器误差，不是循环保持率；仅表征/方法用途。','SRC005':'检索命中2500次为CV峰电流趋势；新增REC_003方法旁系。','R095':'100000次属于引言一般描述，不是本样品循环结果；制备/表征用途。','R061':'未定位可配对循环保持率，保存制备和材料特征线索，不造标签。','R102':'未定位可配对循环保持率，器件电容和能量不能替代循环目标。','R115':'聚合物/活性碳复合和方法参考；未定位可配对长循环保持率。','SRC102':'材料制备/表征及生命周期分析，不把CO2减排百分比当电容保持率。','SRC099':'当前可读正文未定位明确循环保持率配对，保留原始身份及方法线索待核。'}
  for p in srcs:
   role='existing_endpoint_audit_and_feature_recovery' if p['candidate_endpoints'] else 'review_and_method_reference' if p['category']=='D' else 'outside_material_or_application_reference' if p['category']=='E' else 'archive_category_C_identity_scope_hold' if p['category']=='C' else 'material_method_evidence_without_paired_target'
   why=explicit.get(p['paper_id'],'有候选终点按utilization_routes逐条使用；无候选的检索命中不自动变成独立实验或标签。')
   c.execute('insert into paper_utilization values (?,?,?,?,?,?)',(p['paper_id'],role,p['candidate_endpoints'],p['possible_cycle_label_hits'],'full_corpus_text_triage_with_targeted_semantic_review',why))
  c.execute('insert into metadata values (?,?)',('r2_applied','2026-10-17 all-source allocation and fixed prediction input contract'))
  c.execute('insert into review_batches values (?,?,?,?)',('v03_r2_20261017',sha(ROOT.parent/'cycling_v0_3.sqlite'),'126 papers/137 sources text triage; 89 endpoint allocation; bounded feature recovery','No original overwrites, no all-record approval, no research fitting, no literature merge.'))
  assert c.execute('pragma foreign_key_check').fetchall()==[]
  assert c.execute('select count(*) from training_ready').fetchone()[0]==0
 save('本轮新增审查与特征.json',[dict(r) for r in c.execute('select * from review_events where review_id>154')])
 save('待审恢复终点.json',[dict(r) for r in c.execute('select * from staged_recovery_endpoints')])
 print(json.dumps({'new_review_events':c.execute('select count(*) from review_events where review_id>154').fetchone()[0],'routes':c.execute('select count(*) from utilization_routes').fetchone()[0],'papers':c.execute('select count(*) from paper_utilization').fetchone()[0],'staged_not_admitted':3,'training_ready':0},ensure_ascii=False))
if __name__=='__main__':main()
