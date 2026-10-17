"""One-time evidence increment on the r3 copy. Never run against parent databases."""
from pathlib import Path
import sqlite3, json, hashlib, sys

ROOT = Path(__file__).resolve().parent
PARENT = ROOT.parent / '第二轮_全量利用与输入定稿_20261017'
sys.stdout.reconfigure(encoding='utf-8')
c = sqlite3.connect(ROOT / 'cycling_v0_3r3.sqlite')
c.row_factory = sqlite3.Row
c.execute('PRAGMA foreign_keys=ON')
if c.execute("select count(*) from review_batches where batch_id='r3_admission_closure'").fetchone()[0]:
    raise SystemExit('Already applied; do not duplicate evidence events.')
inv = json.loads((PARENT / 'source_inventory_all137.json').read_text('utf-8'))
def source(pid, role='main'):
    return next(f for f in inv if f['paper_id'] == pid and f['role'] == role)
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def event(rid, field, value, path, loc, excerpt, reason, decision='verified_r3'):
    cur = c.execute('INSERT INTO review_events(record_id,field_name,decision,value_json,source_path,source_sha256,locator,evidence_excerpt,rationale,review_date) VALUES(?,?,?,?,?,?,?,?,?,?)',
        (rid,field,decision,json.dumps(value,ensure_ascii=False),str(path),sha(path),loc,excerpt,reason,'2026-10-17'))
    return cur.lastrowid
def change(table,key,field,value,reason):
    keyname = {'cycling_tests':'cycle_test_id','endpoint_features':'record_id','admissions':'record_id','papers':'paper_id'}[table]
    old = c.execute(f'SELECT {field} FROM {table} WHERE {keyname}=?',(key,)).fetchone()[0]
    if old == value: return
    c.execute(f'UPDATE {table} SET {field}=? WHERE {keyname}=?',(value,key))
    c.execute('INSERT INTO revision_changes(table_name,row_key,field_name,old_json,new_json,rationale) VALUES(?,?,?,?,?,?)',
              (table,key,field,json.dumps(old,ensure_ascii=False),json.dumps(value,ensure_ascii=False),reason))
def close(rid, code, review, reason):
    c.execute("UPDATE record_blockers SET status='resolved_by_review',review_id=?,rationale=? WHERE record_id=? AND code=? AND status='open'",(review,reason,rid,code))
def flag(rid, name, review, reason):
    change('admissions',rid,name,1,reason); close(rid,name,review,reason)
def feature(rid, field, value, path, loc, method, unit):
    r=c.execute('SELECT * FROM endpoint_effective_review WHERE record_id=?',(rid,)).fetchone()
    reason='直接核对同名成品的循环前表征；字段补齐不等于整条准入。'
    review=event(rid,field,value,path,loc,str(value),reason)
    change('endpoint_features',rid,field,value,reason)
    c.execute('INSERT INTO material_observations(material_id,record_id,property_name,value_json,unit,method,stage,source_path,locator,provenance_status) VALUES(?,?,?,?,?,?,?,?,?,?)',
        (r['material_id'],rid,field,json.dumps(value),unit,method,'precycling_as_prepared',str(path),loc,'verified_r3'))
    return review

base_sha=sha(PARENT/'cycling_v0_3r2.sqlite')
c.execute('INSERT INTO review_batches VALUES(?,?,?,?)',('r3_admission_closure',base_sha,
 'Existing 89 endpoints; focused main-cohort decisions, scoped optional blockers, new SI and complete eligibility preflight.',
 'No inferred current denominator, no target changes, no research fitting; retain all parent history.'))

# Register genuine acquired supplements; no originals moved or replaced.
new_sources=[('R091','R091_supplement.pdf','PDF',6),('R111','R111_mmc1.docx','DOCX',None),('SRC035','SRC035_mmc1.docx','DOCX',None)]
receipt=ROOT/'R104_EPMC_SI_receipt.json'
if receipt.exists():
    r=json.loads(receipt.read_text('utf-8'))
    if r.get('pdf_path'):
        from pypdf import PdfReader
        pp=Path(r['pdf_path']);new_sources.append(('R104',pp.name,'PDF',len(PdfReader(pp).pages)))
for pid, name, fmt, pages in new_sources:
    path=ROOT/'external_sources'/name
    c.execute('INSERT INTO source_files(paper_id,path,role,format,sha256,pages) VALUES(?,?,?,?,?,?)',
        (pid,str(path),'supplement',fmt,sha(path),pages))

# R111: the SI is now available, and Fig S3B is a device GCD trace 0--1.0 V.
rid='R111_CY01';path=ROOT/'external_sources'/'R111_mmc1.docx'
review=event(rid,'device_voltage_window',[0.0,1.0],path,'Fig S3A/B; source main p8 identifies the same ACK-700 device',
 'ACK-700 supercapacitor: (A) CV graphs, (B) GCD graphs, (C) Cs graphs.',
 '目视补图S3B曲线端点为0–1.0 V，S3A相符；正文p8把该图与ACK-700器件对应。器件协议关联已核，不声称取得独立循环仪日志。')
test=c.execute('SELECT cycle_test_id FROM cycling_endpoints WHERE record_id=?',(rid,)).fetchone()[0]
change('cycling_tests',test,'voltage_lower_V',0.0,'r3新SI FigS3B器件GCD端点')
change('cycling_tests',test,'voltage_upper_V',1.0,'r3新SI FigS3B器件GCD端点')
close(rid,'missing_SI_for_voltage_window',review,'新SI已取得，目视S3A/B核清同一器件0–1 V。')
flag(rid,'protocol_checked',review,'循环电流/次数/电解液沿用已核正文；新SI补齐器件窗口。')

# SRC035: total pore volume, not the micropore column and not species fractions.
rid='SRC035_CY01';path=ROOT/'external_sources'/'SRC035_mmc1.docx'
review=feature(rid,'total_pore_volume_cm3_g',0.53,path,'Table S1, O-PC-700 C row, Vt column','N2 sorption; total pore volume','cm3/g')
close(rid,'missing_SI_for_total_pore_volume_cm3_g',review,'新取得SI TableS1明确Vt=0.53 cm3/g，Vmicro=0.40另列。')

# No exact baseline cycle number is fabricated. The normalized starting value is explicit in the published plot.
baseline_info={
 'R093_CY01':('R093',11,'Fig8e; main p10 describes 1st/2500th/5000th/10000th cycles','Retention of capacity starts at 100%; first-cycle GCD is shown.'),
 'R103_CY01':('R103',8,'Fig7c','Retention starts at 100%; endpoint is directly annotated 96.1%.'),
 'R104_CY01':('R104',11,'Fig10a','Capacity retention starts at 100%; 98.4% is directly annotated.'),
 'R111_CY01':('R111',9,'Fig5F; main p8','Capacitance retention starts at 100%; 89.44% endpoint annotation is distinct from Coulombic efficiency.'),
 'SRC035_CY01':('SRC035',8,'Fig8g','Capacitance retention is normalized to 100% at the plotted start and remains around 100%.')}
for rid,(pid,page,loc,excerpt) in baseline_info.items():
    val={'definition':'author_plotted_start_normalized_to_100pct','cycle_index':None,
         'cycle_index_status':'not_explicitly_reported','source_locator':f'PDF p{page} {loc}'}
    review=event(rid,'baseline_definition',val,source(pid)['path'],f'PDF p{page} {loc}',excerpt,
        '接受作者图示起始归一化基准；通过的是保持率基准定义，不是精确起始循环编号。未把首个可见标记捏造成cycle1。')
    test=c.execute('SELECT cycle_test_id FROM cycling_endpoints WHERE record_id=?',(rid,)).fetchone()[0]
    change('cycling_tests',test,'baseline_json',json.dumps(val,ensure_ascii=False),'r3目视起始100%归一化，保留精确圈号未知')
    flag(rid,'baseline_checked',review,'已核作者图示起始归一化定义；圈号未明不再单独阻挡。')

# Material properties from original tables. None of these additions bypass scope/label gates.
props=[('R017_CY01',25.0,0.071,5),('R017_CY02',25.0,0.071,5),
 ('SRC028_CY01',2280.0,0.8880,6),('SRC028_CY02',1951.0,1.0288,6),
 ('SRC028_CY03',1862.0,1.0123,6),('SRC028_CY04',1942.0,0.9642,6),
 ('SRC028_CY05',1853.0,0.8812,6),('SRC028_CY06',1461.0,0.7089,6),
 ('SRC093_CY01',459.5,0.274,8),('SRC112_CY01',1701.0,1.22,7),('R020_CY01',1081.0,None,8)]
for rid,bet,pore,page in props:
    pid=rid.split('_CY')[0];path=source(pid)['path']
    feature(rid,'BET_m2_g',bet,path,f'PDF p{page}; same sample row/text','N2-BET','m2/g')
    if pore is not None:feature(rid,'total_pore_volume_cm3_g',pore,path,f'PDF p{page}; total pore volume column','N2 sorption; total pore volume','cm3/g')

# Complete a bounded, evidence-backed grouping review for eight papers, not all 126 papers.
# Different DOI is only one diagnostic, never the reason by itself for an independent group.
schema='''CREATE TABLE source_group_reviews(
 paper_id TEXT PRIMARY KEY REFERENCES papers,group_id TEXT NOT NULL,status TEXT NOT NULL,
 corpus_audit_path TEXT NOT NULL,scope_notes TEXT NOT NULL,review_id INTEGER REFERENCES review_events);
 CREATE TABLE validation_group_assignments(
 record_id TEXT PRIMARY KEY REFERENCES cycling_endpoints,group_id TEXT NOT NULL,
 basis TEXT NOT NULL,review_status TEXT NOT NULL);
 CREATE TABLE blocker_scopes(
 record_id TEXT NOT NULL,code TEXT NOT NULL,scope_kind TEXT NOT NULL,field_name TEXT,
 affects_core7 INTEGER NOT NULL,policy TEXT NOT NULL,PRIMARY KEY(record_id,code),
 FOREIGN KEY(record_id,code) REFERENCES record_blockers(record_id,code));
 CREATE TABLE mass_definition_audits(
 record_id TEXT PRIMARY KEY REFERENCES cycling_endpoints,review_id INTEGER REFERENCES review_events,
 current_basis_status TEXT NOT NULL,current_basis_evidence TEXT NOT NULL,
 capacitance_basis_separately_reported TEXT,remaining_required_evidence TEXT NOT NULL,
 acquisition_limit TEXT NOT NULL);
 CREATE TABLE admission_decisions_r3(
 record_id TEXT PRIMARY KEY REFERENCES cycling_endpoints,primary_disposition TEXT NOT NULL,
 failures_json TEXT NOT NULL,core_fields_present INTEGER NOT NULL,optional_pore_value REAL,
 review_extent TEXT NOT NULL);'''
for statement in schema.split(';'):
    if statement.strip(): c.execute(statement)
primary=[dict(r) for r in c.execute('SELECT * FROM primary_screening_candidates')]
for row in primary:
    rid,pid=row['record_id'],row['paper_id']
    if pid=='SRC123':continue
    note=('原文为该材料制备和测试研究；126篇DOI/题名/正文指纹无重复；样品缩写跨正文检索无同一数据重报证据。'
          'R091命中R041为其他HPCS复合材料综述，并非该HPCS-800-2曲线。'
          'SRC035与SRC124有同单位/共同作者，但分别桂花O-PC与棉浆MHDHPC，不据作者重合判同一材料。'
          '同一论文全部终点强制同组；R107两个节点同组，不能当独立材料。'
          '这是可得语料范围的来源分组审查，不是绝对独立性证明，也未核遍所有未取得的前作全文。')
    review=event(rid,'validation_group_review',{'group_id':row['study_group'],'scope':'available_126_paper_corpus'},
        source(pid)['path'],'Original sample preparation/results + corpus_duplicate_and_sample_audit.json',
        row['sample_name'],note,'reviewed_grouping_bounded')
    flag(rid,'independence_checked',review,note)
    c.execute('INSERT OR IGNORE INTO source_group_reviews VALUES(?,?,?,?,?,?)',
        (pid,row['study_group'],'reviewed_grouped_no_documented_reuse_in_available_corpus',str(ROOT/'corpus_duplicate_and_sample_audit.json'),note,review))
    change('papers',pid,'independence_status','reviewed_grouping_available_corpus',note)
    # Missing protocol or current definition is handled by its own gate, not an indefinite generic freeze.
    flag(rid,'freeze_cleared',review,'专项材料范围/数值冲突已核且未发现新全记录冻结理由；缺失的电流/协议门槛仍分别生效，eligible仍为0。')

for r in c.execute('SELECT record_id,study_group,paper_id FROM endpoint_effective_review').fetchall():
    reviewed=c.execute('SELECT 1 FROM source_group_reviews WHERE paper_id=?',(r['paper_id'],)).fetchone()
    c.execute('INSERT INTO validation_group_assignments VALUES(?,?,?,?)',
        (r['record_id'],r['study_group'],'same paper endpoints always grouped; known links must be unioned before any split',
         'reviewed_available_corpus' if reviewed else 'inherited_not_final'))

# Source-by-source current normalization audit: an equation for capacitance is not an equation for j.
mass_notes={
 'R091':('main p3 methods; main p8 Fig6g; new SI all6pages','m is mass of active electrode materials in capacitance equation; no separate cycling-current denominator','new SI obtained, no normalization definition located'),
 'R093':('main p3-4 methods; p10-11 Fig8e','m is active mass on each electrode in capacitance calculation; cycling j=5 A/g has no separate denominator','available main reviewed; no SI link in available paper'),
 'R103':('SI p1-2 electrochemical measurements; main p8 Fig7c','SI defines capacitance mass on a single electrode; no separate cycling-current definition','main and available SI reviewed'),
 'R104':('main p3 sec2.6 and p4 equations; p11 Fig10; newly acquired SI all6pages','GCD says current-to-mass ratio; m on each electrode is defined for capacitance equations; this does not uniquely resolve cycling I/m','main and newly acquired 6-page SI reviewed; no direct cycling-current denominator located'),
 'R107':('main p2-3 methods and p7 Fig6; SI FigS11','total active mass on two sheets explicitly defines Csingle/Ccell formulas, not independently the j=5 A/g denominator','main and all available SI reviewed'),
 'R111':('main p3 sec2.4-2.5 and p8; new SI all paragraphs and FigS3','2 mg and equal-mass electrodes are reported; m for capacitance is porous-carbon mass; j denominator not separately defined','new SI obtained and inspected'),
 'SRC035':('main p2 sec2.3 and p8 Fig8g; new SI sec2.4','single mass m and total mt define capacitance formulas; j=5 A/g is not separately normalized in text','new SI obtained and inspected'),
 'SRC123':('main p2-3 experimental and Fig2; SI all pages','mt is total positive and negative mass for capacitance, not a separate current-density definition','2016 predecessor full cycling curve still unavailable'),
 'SRC124':('main Experimental and Fig5h; SI p2-3 electrochemical','m is mass of MHDHPC in capacitance formulas; j=10 A/g denominator not separately defined','main and available SI reviewed')}
for row in primary:
    rid,pid=row['record_id'],row['paper_id'];loc,cap,limit=mass_notes[pid]
    reason='已完成指定来源的分母审查，但仍不能唯一确认I/(m+ + m−)或可精确换算的单片口径；不从电容式、能量式、GCD时间或相似负载反推。'
    review=event(rid,'cycling_current_mass_basis_audit',{'status':'reviewed_but_not_uniquely_defined','canonical_value':None},
        source(pid)['path'],loc,cap,reason,'reviewed_unresolved_current_basis')
    c.execute('INSERT INTO mass_definition_audits VALUES(?,?,?,?,?,?,?)',
        (rid,review,'reviewed_but_not_uniquely_defined','no unambiguous direct j normalization found in listed sources',cap,
         f'确认该{row["cycle_count"]}次循环的{row["current_density_A_g"]} A/g是I除以哪一个质量；若为单片口径，需两片活性物质量或明确等质量定义。',limit))
    c.execute("UPDATE record_blockers SET rationale=?,review_id=? WHERE record_id=? AND code='mass_basis_checked' AND status='open'",(reason+' '+loc,review,rid))
    change('admissions',rid,'rationale',reason+' '+loc+'；其余当前阻碍见admission_decisions_r3。','r3逐条终审留下明确未决项')

# Fix scope, keeping the optional issue OPEN and preventing the questionable value from leaking.
for b in c.execute('SELECT record_id,code FROM record_blockers').fetchall():
    opt=b['code'] in ('pore_volume_unit','missing_SI_for_total_pore_volume_cm3_g')
    c.execute('INSERT INTO blocker_scopes VALUES(?,?,?,?,?,?)',
        (b['record_id'],b['code'],'field' if opt else 'record',
         'total_pore_volume_cm3_g' if opt else None,0 if opt else 1,
         'mask to NULL before optional imputation; never block core7' if opt else 'fail closed for all selected input sets'))

# Correct a stale protocol issue without changing the historical issue row.
review=c.execute("SELECT MAX(review_id) FROM review_events WHERE record_id='R091_CY01' AND field_name='cycling_current_mass_basis_audit'").fetchone()[0]
for issue in c.execute("SELECT issue_id FROM issues WHERE record_id='R091_CY01' AND code='protocol_not_explicit_GCD'"):
    c.execute('INSERT OR IGNORE INTO issue_resolutions(issue_id,review_id,effective_status,rationale) VALUES(?,?,?,?)',
        (issue[0],review,'resolved_by_review','v0.3已核原图Fig6g循环电流与GCD；关闭遗留协议问题，电流分母缺口另保留。'))

c.commit();c.close()
print('Applied r3 evidence; eligible flags have not been forced to 1.')
