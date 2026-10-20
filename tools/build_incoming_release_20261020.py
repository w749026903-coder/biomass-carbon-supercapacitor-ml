"""Seal the manually reviewed incoming batch as an additive v0.8 release.

No downloading, source-library moves, fitting, admission inference or parent updates.
Refuses an existing release. Run only after reviewing the curated JSON inputs.
"""
from __future__ import annotations
import collections, csv, hashlib, html, importlib.util, json, pathlib, re, shutil, sqlite3, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
BATCH = ROOT / '新增文献整理_20261020'
PARENT = ROOT / '循环稳定性数据库_v0.7_数据补充_20261018'
RELEASE = ROOT / '循环稳定性数据库_v0.8_新增文献整理_20261020'
PARENT_SHA = '65af93be781d858ea8c7a9a2b3b1515acf799be1ad8e94d2231199c9c31f95f1'
CORE = ['cycle_count','reported_current_A_g','electrolyte','concentration_mol_L',
        'cycle_voltage_lower_V','cycle_voltage_upper_V','BET_m2_g']
PROFILES = ['reported_3e','reported_2e','reported_2e_residue','reported_2e_approx']

def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''): h.update(block)
    return h.hexdigest()

def read(name): return json.loads((BATCH / name).read_text('utf-8'))
def write(path, value): path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n','utf-8')
def dump_csv(path, rows, keys):
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        w=csv.DictWriter(f, fieldnames=keys, extrasaction='ignore');w.writeheader()
        for row in rows:
            w.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v for k,v in row.items() if k in keys})

def prepare():
    sources=read('source_reviews.json'); docs={r['document_id']:r for r in read('intake_index.json')}
    tests=read('reviewed_tests.json'); sm={s['document_id']:s for s in sources}
    relationships={r['document_id']:r for r in read('existing_relationships.json')}
    for s in sources:
        s['source_group']=s['existing_source_group'] or ('doi:'+s['doi'] if s['doi'] else 'document:'+s['sha256'])
        s['archived']=False
        s['training_eligible']=False  # Admission is always per test/profile, never per PDF.
        ts=[r for r in tests if r['document_id']==s['document_id']]
        s['test_review_status']='bounded_own_test_review_completed' if ts else (
            'existing_admitted_endpoints_reconfirmed_no_duplicate' if s['document_id']=='ADD_033' else
            s['test_review_status'] if 'not_located' in s['test_review_status'] else
            'scope_review_completed_no_own_endurance_row_located')
        s['review_limit']='Provided main PDF, native full text and cited original pages; not an exhaustive SI or plotted-point digitization claim.'
    normalized=[]
    for t in tests:
        s=sm[t['document_id']]; r={**t,**t['fields']}
        r.update(endpoint_id='incoming:'+t['record_id'],identity_key=s['existing_identity'] or s['source_group'],
                 source_group=s['source_group'],source_year=s['year'],doi=s['doi'],source_pdf=s['storage_path'],
                 source_sha256=s['sha256'],source_weight=None,canonical_current_A_g=None,
                 admission_status=t['review_status'],eligible=0)
        r['related_existing_endpoints']=[x['endpoint_id'] for x in relationships[t['document_id']]['old_endpoints']
            if x['cycle_count']==r['cycle_count'] and x['system']==r['system'] and x['retention_pct']==r['retention_pct']]
        needed=CORE+(['reference_electrode'] if r['system']=='3E' else [])
        missing=[k for k in needed if r.get(k) is None]
        t['core_missing_fields']=missing;r['core_missing_fields']=missing
        reasons=[]
        if missing: reasons.append('missing_core_fields:'+','.join(missing))
        if r['system'] not in ('3E','2E_symmetric'):reasons.append('configuration_outside_or_unresolved')
        if r['retention_relation']!='eq':reasons.append('nonexact_label_relation:'+r['retention_relation'])
        if r['retention_pct'] is None:reasons.append('numeric_retention_not_located')
        if not s['year'] or not 2023<=s['year']<=2026:reasons.append('publication_year_unresolved_or_outside')
        if s['publication_type']!='original_experiment' or s['category_code']=='03':reasons.append('publication_identity_or_preprint_hold')
        if r['scope_status'] not in ('ordinary_carbon_candidate','ordinary_biomass_carbon_reviewed'):reasons.append('material_or_electrolyte_scope_requires_review')
        if r['system']=='2E_symmetric' and not r.get('pairing_basis'):reasons.append('paired_electrode_evidence_not_bound')
        if r['review_status']!='approved_for_reported_protocol':reasons.append('manual_scientific_review_not_approved')
        t['remaining_evidence_work']=reasons;r['remaining_evidence_work']=reasons
        if r['review_status']=='approved_for_reported_protocol':
            if reasons:raise ValueError((r['record_id'],reasons))
            if not r.get('evidence_pages',{}).get('label_protocol'):raise ValueError('No label evidence')
            if any(not r.get('field_evidence',{}).get(k,{}).get('pages') for k in t['fields'] if k in needed):
                raise ValueError('Missing own field evidence: '+r['record_id'])
            r['eligible']=1
        normalized.append(r)
    write(BATCH/'source_reviews.json',sources);write(BATCH/'reviewed_tests.json',tests)
    write(BATCH/'normalized_tests.json',normalized)
    return sources,docs,normalized

DDL = '''
CREATE TABLE incoming_sources_v08(document_id TEXT PRIMARY KEY,doi TEXT,source_group TEXT NOT NULL,year INTEGER,category_code TEXT NOT NULL,repository_path TEXT NOT NULL,sha256 TEXT NOT NULL UNIQUE,review_json TEXT NOT NULL);
CREATE TABLE incoming_pages_v08(document_id TEXT NOT NULL REFERENCES incoming_sources_v08,page_number INTEGER NOT NULL,text TEXT NOT NULL,PRIMARY KEY(document_id,page_number));
CREATE VIRTUAL TABLE incoming_search_v08 USING fts5(document_id UNINDEXED,page_number UNINDEXED,text);
CREATE TABLE incoming_tests_v08(record_id TEXT PRIMARY KEY,document_id TEXT NOT NULL REFERENCES incoming_sources_v08,source_group TEXT NOT NULL,system TEXT NOT NULL,review_status TEXT NOT NULL,row_json TEXT NOT NULL);
CREATE TABLE incoming_observations_v08(observation_id INTEGER PRIMARY KEY,record_id TEXT NOT NULL REFERENCES incoming_tests_v08,field_name TEXT NOT NULL,value_json TEXT NOT NULL,selected INTEGER NOT NULL CHECK(selected IN(0,1)),reason TEXT,evidence_kind TEXT NOT NULL);
CREATE TABLE incoming_observation_pages_v08(observation_id INTEGER NOT NULL REFERENCES incoming_observations_v08,document_id TEXT NOT NULL,page_number INTEGER NOT NULL,PRIMARY KEY(observation_id,document_id,page_number),FOREIGN KEY(document_id,page_number) REFERENCES incoming_pages_v08(document_id,page_number));
CREATE TABLE incoming_admissions_v08(profile TEXT NOT NULL,record_id TEXT NOT NULL REFERENCES incoming_tests_v08,status TEXT NOT NULL,reasons_json TEXT NOT NULL,PRIMARY KEY(profile,record_id));
CREATE TABLE incoming_batch_meta_v08(key TEXT PRIMARY KEY,value_json TEXT NOT NULL);
CREATE INDEX incoming_test_group_v08 ON incoming_tests_v08(source_group);
CREATE INDEX incoming_observation_field_v08 ON incoming_observations_v08(record_id,field_name);
'''

def populate(conn, sources, docs, tests):
    conn.executescript(DDL)
    conn.execute('PRAGMA foreign_keys=ON')
    for s in sources:
        conn.execute('insert into incoming_sources_v08 values(?,?,?,?,?,?,?,?)',(s['document_id'],s['doi'],s['source_group'],s['year'],s['category_code'],s['storage_path'],s['sha256'],json.dumps(s,ensure_ascii=False)))
    raw=sqlite3.connect((BATCH/'batch.sqlite').as_uri()+'?mode=ro',uri=True)
    pages=raw.execute('select document_id,page_number,text from pages order by document_id,page_number').fetchall();raw.close()
    conn.executemany('insert into incoming_pages_v08 values(?,?,?)',pages)
    conn.executemany('insert into incoming_search_v08 values(?,?,?)',pages)
    for r in tests:
        conn.execute('insert into incoming_tests_v08 values(?,?,?,?,?,?)',(r['record_id'],r['document_id'],r['source_group'],r['system'],r['review_status'],json.dumps(r,ensure_ascii=False)))
        evidence=r.get('field_evidence',{});label=r['evidence_pages']['label_protocol']
        values={k:r[k] for k in ['sample_name','system','method','cycle_count','retention_pct','retention_relation','reported_current_A_g','baseline_reference','current_mass_basis']}
        values.update(r['fields'])
        for field,value in values.items():
            obs=conn.execute('insert into incoming_observations_v08(record_id,field_name,value_json,selected,reason,evidence_kind) values(?,?,?,?,?,?)',
                (r['record_id'],field,json.dumps(value,ensure_ascii=False),1,'Reviewed value; null retains unlocated/unknown state','own_source_text_or_reviewed_figure')).lastrowid
            for p in sorted(set(evidence.get(field,{}).get('pages',label))):
                conn.execute('insert into incoming_observation_pages_v08 values(?,?,?)',(obs,r['document_id'],p))
        for x in r.get('extra_observations',[]):
            obs=conn.execute('insert into incoming_observations_v08(record_id,field_name,value_json,selected,reason,evidence_kind) values(?,?,?,?,?,?)',
                (r['record_id'],x['field'],json.dumps(x.get('value'),ensure_ascii=False),int(x.get('selected',False)),x.get('reason') or x.get('status'),'preserved_alternative')).lastrowid
            for p in sorted(set(x.get('pages',[]))):conn.execute('insert into incoming_observation_pages_v08 values(?,?,?)',(obs,r['document_id'],p))
        for profile in PROFILES:
            expected='3E' if profile=='reported_3e' else '2E_symmetric'
            ok=r['eligible']==1 and r['system']==expected
            reasons=[] if ok else r['remaining_evidence_work']+(['profile_configuration_mismatch'] if r['system']!=expected else [])
            conn.execute('insert into incoming_admissions_v08 values(?,?,?,?)',(profile,r['record_id'],'approved_for_reported_protocol' if ok else 'pending_or_outside',json.dumps(reasons,ensure_ascii=False)))
    conn.execute('insert into incoming_batch_meta_v08 values(?,?)',('parent_database_sha256',json.dumps(PARENT_SHA)))
    conn.execute('insert into incoming_batch_meta_v08 values(?,?)',('research_training_authorized','false'))
    conn.commit()
    if conn.execute('PRAGMA integrity_check').fetchone()[0]!='ok' or conn.execute('PRAGMA foreign_key_check').fetchall():raise ValueError('SQLite verification failed')

def reconcile(sources):
    with (ROOT/'文献扩充_大批补齐_20261018/下载任务单.csv').open(encoding='utf-8-sig',newline='') as f:old=list(csv.DictReader(f))
    bydoi=collections.defaultdict(list)
    for s in sources:
        if s['doi']:bydoi[s['doi'].lower()].append(s)
    result=[]
    for t in old:
        matches=bydoi[t['DOI'].lower()];si='已声明SI' in t['需要下载']
        result.append({**t,'本批对应文档':[s['document_id'] for s in matches],
            '本批组件处置':'本批为正文，不能关闭SI任务' if si and matches else '未匹配本批原文' if not matches else '正文取得；类型更正，属于背景资料' if all(s['publication_type']!='original_experiment' for s in matches) else '正文取得；SI状态不随正文自动关闭',
            '本批正文取得':bool(matches),'本批SI取得':False})
    write(BATCH/'download_task_reconciliation.json',result)
    dump_csv(BATCH/'95项下载任务对账.csv',result,list(result[0]))
    return {'old_tasks':len(result),'matched_main_tasks':sum(x['本批正文取得'] and '已声明SI' not in x['需要下载'] for x in result),'SI_tasks_matched_only_main':sum(x['本批正文取得'] and '已声明SI' in x['需要下载'] for x in result)}

def catalog(sources, docs, tests):
    totals=collections.Counter(s['category'] for s in sources)
    counts=collections.Counter(r['document_id'] for r in tests)
    header='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>新增文献 · 分类与证据</title>
<style>body{font:16px/1.6 system-ui,"Microsoft YaHei",sans-serif;background:#f4f6f8;color:#17283b;max-width:1300px;margin:32px auto;padding:0 24px}h1{font-size:30px}input,select{font:inherit;padding:9px;border:1px solid #bac8d3;border-radius:6px;margin:4px}article{background:white;border:1px solid #dce2e8;border-radius:10px;padding:18px;margin:12px 0}a{color:#075e9d}small{color:#536579}.tag{background:#e8eff4;padding:2px 8px;border-radius:5px}summary{cursor:pointer}pre{white-space:pre-wrap;font:13px/1.6 system-ui}nav{position:sticky;top:0;background:#f4f6f8;padding:10px 0}</style>
<h1>新增文献：原文、分类与数据</h1><p>80份不同内容PDF；75份直接原文入库，5份复用已有相同原文。按实际测试审查，分类不等于训练准入。点击原文可直接阅读，无需解压；页码均为PDF页码。</p>
<p><a href="README.md">整理说明</a> · <a href="逐测试数据.csv">逐测试数据</a> · <a href="待补证据清单.md">待补证据</a> · <a href="95项下载任务对账.csv">旧下载任务对账</a></p>
<nav><input id="q" placeholder="搜索题名、DOI、样品或字段" size="38"><select id="category"><option value="">全部类别</option>'''
    header+=''.join('<option>'+html.escape(k)+'</option>' for k in totals)+'</select><span id="count"></span></nav>'
    cards=[]
    for s in sources:
        ts=[r for r in tests if r['document_id']==s['document_id']]
        detail=json.dumps({'tests':ts,'source_review':s,'original_locations':docs[s['document_id']]['input_locations'] if 'input_locations' in docs[s['document_id']] else docs[s['document_id']].get('locations',[])},ensure_ascii=False,indent=2)
        href='../'+s['storage_path']
        cards.append('<article data-category="'+html.escape(s['category'],quote=True)+'"><small>'+s['document_id']+' · '+str(s['year'] or '年份待核')+' · <span class="tag">'+html.escape(s['category'])+'</span></small><h2>'+html.escape(s['title'])+'</h2><p>'+html.escape(s['doi'] or 'DOI未定位')+' · '+str(counts[s['document_id']])+'条自有测试观察</p><p><a href="'+html.escape(href,quote=True)+'">打开原文PDF</a> · '+html.escape(s['scope_reason'])+'</p><details><summary>逐测试字段、页码与审查处置</summary><pre>'+html.escape(detail)+'</pre></details></article>')
    footer='''<script>const q=document.querySelector('#q'),c=document.querySelector('#category');function filter(){let n=0;for(const a of document.querySelectorAll('article')){const ok=(!c.value||a.dataset.category===c.value)&&a.textContent.toLowerCase().includes(q.value.toLowerCase());a.hidden=!ok;if(ok)n++}document.querySelector('#count').textContent=n+' / 80篇'}q.addEventListener('input',filter);c.addEventListener('change',filter);filter();</script></html>'''
    (BATCH/'文献分类入口.html').write_text(header+'\n'.join(cards)+footer,'utf-8')
    dump_csv(BATCH/'文献分类索引.csv',sources,['document_id','doi','title','year','publication_type','category','scope_reason','source_group','storage_path','sha256','test_review_status'])
    dump_csv(BATCH/'逐测试数据.csv',tests,['record_id','document_id','doi','sample_name','system','method','cycle_count','retention_pct','retention_relation',*CORE[1:],'reference_electrode','total_pore_volume_cm3_g','current_mass_basis','source_group','source_year','eligible','admission_status','related_existing_endpoints','evidence_pages','field_evidence','remaining_evidence_work','review_notes'])

def main():
    refresh='--refresh-unsealed' in sys.argv
    if RELEASE.exists() and (not refresh or (RELEASE/'merge_manifest.json').exists()):
        raise FileExistsError('Existing release is protected: '+str(RELEASE))
    parent=PARENT/'cycling_v0_7.sqlite'
    if sha(parent)!=PARENT_SHA:raise ValueError('Parent baseline changed')
    sources,docs,tests=prepare()
    if not RELEASE.exists():
        RELEASE.mkdir();shutil.copyfile(parent,RELEASE/'cycling_v0_8.sqlite')
    conn=sqlite3.connect(RELEASE/'cycling_v0_8.sqlite')
    if refresh:
        # Only this new batch's unsealed tables. Inherited scientific tables are untouched.
        for name in ['incoming_observation_pages_v08','incoming_admissions_v08','incoming_observations_v08','incoming_tests_v08','incoming_search_v08','incoming_pages_v08','incoming_sources_v08','incoming_batch_meta_v08']:
            conn.execute('DROP TABLE IF EXISTS '+name)
        conn.commit()
    populate(conn,sources,docs,tests);conn.close()
    contract=json.loads((PARENT/'data_contract.json').read_text('utf-8'))
    contract.update(version='v0.8',database_file='cycling_v0_8.sqlite',parent_database_sha256=PARENT_SHA,
                    expansion_rule='Explicit own-test approvals only; old tables and all old freezes untouched; staged sources not globally archived.',
                    new_test_review_only_profile='incoming_review')
    write(RELEASE/'data_contract.json',contract)
    stats={'documents':len(sources),'new_original_PDFs':75,'reused_original_PDFs':5,'own_test_observations':len(tests),
           'documents_with_test_observations':len({r['document_id'] for r in tests}),
           'new_explicit_approvals':sum(r['eligible'] for r in tests),'categories':dict(collections.Counter(s['category'] for s in sources)),
           'download_task_reconciliation':reconcile(sources),'research_training_runs':0}
    write(BATCH/'batch_summary.json',stats);catalog(sources,docs,tests)
    queue=['# 待补证据与范围处置','',
        '以下是已提供正文的有边界复核结果，不将未定位写成未报告。缺件不插补；预印本、旁系、近似与冲突保留。页码与原值见逐测试JSON/SQLite；缺配对证据时优先检查原文SI，不重新争论未知电流质量分母。','']
    for r in tests:
        if not r['eligible']:
            queue+=['## '+r['record_id']+' · '+str(r['sample_name']),'',r['doi'] or 'DOI未定位',
                    '', '；'.join(r['remaining_evidence_work']), '', '；'.join(r['open_issues']), '']
    (BATCH/'待补证据清单.md').write_text('\n'.join(queue),'utf-8')
    print(json.dumps(stats,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
