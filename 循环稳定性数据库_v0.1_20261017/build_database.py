"""Build a new, versioned SQLite database from reviewed local candidate snapshots.
Never modifies source documents, prior tables, or an existing database.
"""
import collections, hashlib, io, json, pathlib, sqlite3, sys
from pypdf import PdfReader

OUT=pathlib.Path(__file__).resolve().parent
BASE=OUT.parent
SUP=BASE/'循环稳定性文献补充_20261017'
DB=OUT/'cycling_v0_1.sqlite'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def js(x):return json.dumps(x,ensure_ascii=False,sort_keys=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def insert(table,values):
 keys=list(values);conn.execute(f'INSERT INTO {table} ({",".join(keys)}) VALUES ({",".join("?" for _ in keys)})',[values[k] for k in keys])
assert not DB.exists(),'Existing database preserved. Build the next version in a new directory.'
index=read(BASE/'文献整理_20261017/当前唯一文献位置.json')
papers={r['id']:r for r in index if r.get('in_active_library')}
audit={r['id']:r for r in read(BASE/'训练适用性审核_20261016/逐份训练用途审核.json')}
alias=read(SUP/'文献入库审核/已确认入库执行/补充编号与正式文献编号映射.json')
newmeta={alias[x['id']]:x for x in read(SUP/'第一批文献清单_核验后.json') if x['id'] in alias}
inputs=[SUP/'现有数据补齐/循环稳定性逐记录候选_v2.json',SUP/'新增来源循环候选_单列未并库.json']
raw=[]
for path in inputs:raw.extend((r,path) for r in read(path))
assert len(papers)==126 and len(raw)==89
for p in papers.values():
 main=pathlib.Path(p.get('local_fulltext') or p['local_pdf']);assert main.is_file() and sha(main)==p['sha256'],p['id']
conn=sqlite3.connect(DB)
conn.executescript((OUT/'schema.sql').read_text(encoding='utf-8'))
conn.execute('BEGIN')
for k,v in {'schema_version':'0.1','created_date':'2026-10-17','target':'capacitance retention at specified cycle count and conditions','status':'candidate_database_not_training_release','source_scope':'126 current papers, 89 extracted candidate endpoints; no new experiments fabricated','source_group_status':'provisional pending cross-paper overlap audit'}.items():insert('metadata',dict(key=k,value=v))
for path in inputs:insert('ingestion_sources',dict(path=str(path),sha256=sha(path),role='candidate_snapshot'))
for ident,p in papers.items():
 meta=newmeta.get(ident) or audit.get(ident,{})
 main=pathlib.Path(p.get('local_fulltext') or p['local_pdf']);fmt=p.get('main_format','PDF')
 doi=(meta.get('doi') or p.get('doi') or '').lower() or None
 group=doi or ident
 if ident=='SRC087':group=(audit['R002'].get('doi') or 'R002').lower()
 insert('papers',dict(paper_id=ident,doi=doi,title=meta.get('title') or p.get('title') or ident,year=meta.get('year',p.get('year')),category=p['category'],study_group=group,main_format=fmt,main_path=str(main),main_sha256=p['sha256'],archive_restrictions=p.get('restrictions') or meta.get('restrictions','')))
 files=[(main,'main')]+[(pathlib.Path(x),'supplement') for x in p['supplements']]
 if p.get('local_text'):files.append((pathlib.Path(p['local_text']),'readable_text'))
 for f,role in files:
  assert f.is_file();pages=None
  if f.suffix.lower()=='.pdf':
   b=f.read_bytes();assert b.startswith(b'%PDF-');pages=len(PdfReader(io.BytesIO(b)).pages)
  insert('source_files',dict(paper_id=ident,path=str(f),role=role,format=f.suffix[1:].upper(),sha256=sha(f),pages=pages))

material_ids=set();test_rows={};record_rows=[]
material_fields={'BET_m2_g':'m2/g','total_pore_volume_cm3_g':'cm3/g','N_at_pct':'at%','O_at_pct':'at%','N_wt_pct':'wt%','O_wt_pct':'wt%','S_at_pct':'at%','EDS_composition':None,'total_pore_volume_reported':None}
core_fields=['cycle_count','retention_pct','current_density_A_g','current_density_mA_cm2','scan_rate_mV_s','electrolyte','concentration_value','concentration_unit','voltage_lower_V','voltage_upper_V','mass_loading_mg_cm2','temperature_C']
protocol_fields=['electrolyte','concentration_value','concentration_unit','current_density_A_g','current_density_mA_cm2','scan_rate_mV_s','voltage_lower_V','voltage_upper_V','temperature_C']
def issue(paper,record,code,description,severity='high',source=None,scope='endpoint'):
 insert('issues',dict(paper_id=paper,record_id=record,severity=severity,code=code,description=description,status='open',source_path=source,scope=scope))
for original,input_path in raw:
 r=original;legacy=r['paper_id'];paper=alias.get(legacy,legacy);assert paper in papers
 rid=r['record_id'].replace(legacy+'_',paper+'_',1)
 mid=r['material_id'].replace(legacy+'::',paper+'::',1)
 tid=r['cycle_test_id'].replace(legacy+'::',paper+'::',1)
 p=papers[paper];main=p.get('local_fulltext') or p['local_pdf']
 evidence=r.get('evidence_path') or r.get('pdf') or main
 # New-paper evidence now points to its canonical archived copy; raw JSON retains original path.
 if legacy in alias:evidence=main
 assert pathlib.Path(evidence).is_file(),(rid,evidence)
 insert('raw_records',dict(record_id=rid,legacy_record_id=r['record_id'],paper_id=paper,input_path=str(input_path),raw_json=js(r)))
 if mid not in material_ids:
  insert('materials',dict(material_id=mid,paper_id=paper,sample_name=r['sample'],legacy_material_id=r['material_id']));material_ids.add(mid)
 baseline={k:r[k] for k in ['baseline_cycle','baseline_definition','normalization_reference'] if r.get(k) is not None}
 proto=dict(cycle_test_id=tid,paper_id=paper,material_id=mid,legacy_cycle_test_id=r['cycle_test_id'],system=r['system'],method=r['method'],**{k:r.get(k) for k in protocol_fields},mass_basis=r.get('cycle_current_mass_basis'),baseline_json=js(baseline) if baseline else None,positive_negative_mass_ratio=r.get('positive_negative_mass_ratio'),protocol_note='Current normalization and capacitance formula mass basis are distinct; see raw_record and field evidence.')
 if tid not in test_rows:test_rows[tid]=proto
 else:
  for k,v in proto.items():
   prior=test_rows[tid].get(k)
   if prior is None and v is not None:test_rows[tid][k]=v
   elif v is not None and prior!=v:raise ValueError(f'Conflicting test-level field {tid} {k}: {prior} versus {v}')
 record_rows.append((rid,tid,mid,paper,r,evidence))
 for key in sorted(set(core_fields)|set(material_fields)|{'capacitance_mass_basis','cycle_current_mass_basis','EDS_composition','active_mass_range_mg','device_single_electrode_active_mass_mg','baseline_cycle','baseline_definition','normalization_reference'}):
  value=r.get(key);locator=r.get('input_provenance',{}).get(key) or r.get('evidence_locator') or r.get('provenance_note') or ('record PDF pages '+js(r.get('pdf_pages',[])))
  field_path=evidence
  if str(locator).lower().startswith('main'):field_path=main
  elif 'si ' in str(locator).lower() or 'si p' in str(locator).lower():
   candidate=r.get('supplement_evidence_path')
   if candidate and pathlib.Path(candidate).is_file():field_path=candidate
   elif len(p['supplements'])==1:field_path=p['supplements'][0]
  status=r.get('field_status',{}).get(key) or ('recorded_from_candidate_evidence_pending_field_audit' if value is not None else 'not_yet_paired_or_not_recorded_not_proven_absent')
  insert('field_evidence',dict(record_id=rid,field_name=key,value_json=js(value),source_path=field_path,locator=str(locator),status=status))
  if key in material_fields and value is not None:
   method='EDS' if key=='EDS_composition' else ('elemental_method_not_finalized' if '_at_' in key or '_wt_' in key else 'reported_characterization')
   insert('material_observations',dict(material_id=mid,record_id=rid,property_name=key,value_json=js(value),unit=material_fields[key],method=method,stage='as_prepared_candidate_stage_requires_final_audit',source_path=field_path,locator=str(locator),provenance_status=status))
for proto in test_rows.values():insert('cycling_tests',proto)
for rid,tid,mid,paper,r,evidence in record_rows:
 note='; '.join(str(r[k]) for k in ['provenance_note','conflict_note','note','followup_review_note'] if r.get(k))
 short=bool(r.get('short_test') or (r.get('cycle_count') is not None and r['cycle_count']<1000))
 insert('cycling_endpoints',dict(record_id=rid,cycle_test_id=tid,cycle_count=r.get('cycle_count'),retention_pct=r.get('retention_pct'),retention_relation=r.get('retention_relation','eq'),retention_sd_pct=r.get('retention_sd_pct'),metric_kind='capacity_retention' if 'half_cell' in r['system'] else 'capacitance_retention',value_kind=r.get('value_kind') or 'reported',material_scope='Cu_containing_biomass_carbon' if paper=='SRC126' else r['material_scope'],conflict=int(bool(r.get('conflict'))),short_test=int(short),evidence_path=evidence,evidence_pages_json=js(r.get('pdf_pages',[])),evidence_locator=r.get('evidence_locator') or r.get('provenance_note'),note=note,legacy_json_flags=js({k:r.get(k) for k in ['candidate_clean','provisional_core_conditions','provisional_minimal_features','configuration_id','test_tag','alternate_reported_retention_pct','concentration_reported_conflict']})))
 insert('endpoint_features',dict(record_id=rid,**{k:r.get(k) for k in ['BET_m2_g','total_pore_volume_cm3_g','N_at_pct','O_at_pct','N_wt_pct','O_wt_pct','mass_loading_mg_cm2']},Si_residue_review_required=int(bool(r.get('Si_residue_review_required'))),pore_unit_review_required=int(bool(r.get('pore_unit_review_required')))))
 insert('admissions',dict(record_id=rid,status='candidate_pending_final_record_audit',eligible=0,rationale='Raw evidence preserved. Archive review is separate from record admission; baseline, cycle-current mass basis, independence and freezes require explicit record decisions.'))
 issue(paper,rid,'final_record_audit_pending','基线、电流质量分母、材料独立性及冻结范围尚未逐记录终审。','high',evidence)
 if r.get('conflict'):issue(paper,rid,'reported_conflict',r.get('conflict_note') or r.get('provenance_note') or '原候选已标冲突，保留原值。',source=evidence)
 if papers[paper]['category']=='C':issue(paper,rid,'paper_frozen_or_pending','论文处于待核/冻结分类，不因文献归档而解冻。',source=evidence)
 if r.get('retention_relation')!='eq':issue(paper,rid,'non_exact_label','近似值或下限单列，普通点值回归默认不使用。','medium',evidence)
 if r.get('cycle_count') is None or r.get('retention_pct') is None:issue(paper,rid,'label_incomplete','次数或保持率尚未配对；空值不是0。',source=evidence)
 if short:issue(paper,rid,'short_cycle_screening','小于本轮1000次筛查边界，保留资料但单列。此边界不是通用质量标准。','medium',evidence)
 if r['method']!='GCD':issue(paper,rid,'protocol_not_explicit_GCD','CV或GCD措辞待核，不直接进入明确GCD主体系。','medium',evidence)
 if r['method']=='GCD' and r.get('current_density_A_g') is None:
  issue(paper,rid,'gravimetric_cycle_current_unpaired','质量电流密度未配对；若原文为面积电流，不自动换算。','medium',evidence)
 if r.get('Si_residue_review_required'):issue(paper,rid,'silicon_residue_scope_review','SI EDS硅11.68 at%；EDS与XPS分开，复核无机残留后再确定纯碳范围。',source=evidence)
 if r.get('pore_unit_review_required'):issue(paper,rid,'printed_pore_unit_review','孔体积原表印m³/g，原值另存，不擅改为cm³/g。',source=evidence)
 if r['system']!='2E_symmetric':issue(paper,rid,'separate_system','非主体系：'+r['system']+'，分体系保留。','medium',evidence)
 if paper in ['R001','SRC123']:issue(paper,rid,'sample_reuse_review','与作者前作的材料/曲线是否复用仍待核，未确定独立性。',source=evidence)

insert('source_relationships',dict(paper_id='SRC087',related_paper_id='R002',related_doi=audit['R002']['doi'],relationship='reuses_underlying_secondary_dataset',status='documented_in_prior_audit',note='Do not count secondary data as new experiments. Sources share a split group.'))
insert('source_relationships',dict(paper_id='SRC123',related_paper_id=None,related_doi=None,relationship='references_authors_2016_RHC_study',status='sample_overlap_pending',note='2016 prior-work link does not by itself establish reuse of the 2025 cycling data. No independence clearance.'))
for x in read(BASE/'文献扩充_生物质碳_120篇/禁止入库与待核查来源.json'):
 match=next((k for k,v in papers.items() if (v.get('doi') or audit.get(k,{}).get('doi') or '').lower()==x['doi'].lower()),None)
 issue(match,None,'historical_source_freeze',js(x),source=str(BASE/'文献扩充_生物质碳_120篇/禁止入库与待核查来源.json'),scope='paper_or_external_source')
for x in read(BASE/'训练适用性审核_20261016/训练相关问题登记.json'):
 for ident in x['papers']:
  if ident in papers:issue(ident,None,'prior_audit_'+x['id'],x['topic']+'；'+x.get('action',''),source=str(BASE/'训练适用性审核_20261016/训练相关问题登记.json'),scope='paper_or_field_as_previously_reported')
conn.commit()
assert conn.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
assert conn.execute('PRAGMA foreign_key_check').fetchall()==[]
assert conn.execute('SELECT count(*) FROM endpoint_review').fetchone()[0]==89
assert conn.execute('SELECT count(*) FROM training_ready').fetchone()[0]==0
for rid,tid,mid,paper,r,evidence in record_rows:
 got=conn.execute('SELECT cycle_count,retention_pct,retention_relation,conflict FROM cycling_endpoints WHERE record_id=?',(rid,)).fetchone()
 assert got==(r.get('cycle_count'),r.get('retention_pct'),r.get('retention_relation','eq'),int(bool(r.get('conflict')))),rid
 # Every original snapshot value, including unknowns and >100% retention, survives in raw_json.
 assert json.loads(conn.execute('SELECT raw_json FROM raw_records WHERE record_id=?',(rid,)).fetchone()[0])==r
conn.row_factory=sqlite3.Row
exports=OUT/'exports';exports.mkdir(exist_ok=True)
for table in ['papers','materials','cycling_tests','endpoint_review','issues','admissions','primary_screening_candidates','training_ready','source_relationships']:
 rows=[dict(x) for x in conn.execute('SELECT * FROM '+table)]
 (exports/(table+'.json')).write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
def profile(view,where='1=1'):
 return dict(conn.execute(f'SELECT count(*) endpoints,count(distinct material_id) provisional_materials,count(distinct paper_id) papers,count(distinct study_group) study_groups FROM {view} WHERE {where}').fetchone())
counts={t:conn.execute('SELECT count(*) FROM '+t).fetchone()[0] for t in ['papers','source_files','materials','cycling_tests','cycling_endpoints','material_observations','field_evidence','issues','admissions','training_ready']}
summary={'date':'2026-10-17','counts':counts,'all_candidates':profile('endpoint_review'),'main_screening_pool':profile('primary_screening_candidates'),'main_basic_conditions':profile('primary_screening_candidates',"current_density_A_g IS NOT NULL AND electrolyte IS NOT NULL AND concentration_value IS NOT NULL AND concentration_unit IS NOT NULL"),'main_basic_BET_voltage':profile('primary_screening_candidates',"current_density_A_g IS NOT NULL AND electrolyte IS NOT NULL AND concentration_value IS NOT NULL AND concentration_unit IS NOT NULL AND BET_m2_g IS NOT NULL AND voltage_lower_V IS NOT NULL AND voltage_upper_V IS NOT NULL"),'cohorts':[dict(x) for x in conn.execute('SELECT system,method,count(*) endpoints,count(distinct material_id) provisional_materials FROM endpoint_review GROUP BY system,method')],'label_relations':[dict(x) for x in conn.execute('SELECT retention_relation,count(*) n FROM cycling_endpoints GROUP BY retention_relation')],'missing_fields_in_current_extraction':{},'checks':{'sqlite_integrity':'ok','foreign_key_violations':0,'flattened_join_rows':89,'raw_snapshot_values_preserved':True,'training_rows':0,'retention_above_100_not_clipped':conn.execute('SELECT count(*) FROM cycling_endpoints WHERE retention_pct>100').fetchone()[0]},'limitations':['All material identities are provisional; 89 endpoints do not mean 89 independent samples.','Missing values describe current extraction, not proven absence from original papers.','Primary screening pool is a work queue, not training admission.','126 papers catalogued does not mean 126 papers have extracted cycling labels.','1000 cycles is a project screening convention, not a universal quality threshold.']}
for key in ['cycle_count','retention_pct','current_density_A_g','concentration_value','voltage_lower_V','BET_m2_g','total_pore_volume_cm3_g']:
 summary['missing_fields_in_current_extraction'][key]=conn.execute('SELECT count(*) FROM endpoint_review WHERE '+key+' IS NULL').fetchone()[0]
write_json=lambda p,x:p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
write_json(OUT/'数据库核验与覆盖摘要.json',summary)
write_json(OUT/'输入快照指纹.json',[dict(path=str(p),sha256=sha(p)) for p in inputs]+[dict(path=str(BASE/'文献整理_20261017/当前唯一文献位置.json'),sha256=sha(BASE/'文献整理_20261017/当前唯一文献位置.json'))])
conn.close()
print(json.dumps(summary,ensure_ascii=False,indent=2))
