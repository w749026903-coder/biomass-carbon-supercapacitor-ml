"""Verify/seal candidate supply delivery without changing scientific datasets."""
from pathlib import Path
import csv, hashlib, json, re, sys, urllib.parse
from collect_literature_supply_20261018 import ROOT, OUT, dump
from repository_checks import scan

TOOLS = ['collect_literature_supply_20261018.py','acquire_literature_supply_20261018.py','complete_literature_supply_20261018.py','finalize_literature_supply_20261018.py','verify_literature_supply_20261018.py']
DOCS = ['README.md','docs/CURRENT_STATE.md','docs/LITERATURE_INDEX.md','docs/KNOWLEDGE_BASE.md','docs/knowledge/文献补齐与缺件判定_20261018.md']
DB = ROOT/'循环稳定性数据库_v0.7_数据补充_20261018/cycling_v0_7.sqlite'
EXPECTED = '65af93be781d858ea8c7a9a2b3b1515acf799be1ad8e94d2231199c9c31f95f1'

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def payload():
    return sorted([p for p in OUT.rglob('*') if p.is_file() and 'transport_cache' not in p.parts and '__pycache__' not in p.parts and p.name != 'delivery_manifest.json'])

def verify(seal=False):
    checks=[]
    def ck(name,ok):
        checks.append({'check':name,'passed':bool(ok)})
        if not ok:raise AssertionError(name)
    report=json.loads((OUT/'最终核验.json').read_text(encoding='utf-8'))
    rows=json.loads((OUT/'master_index.json').read_text(encoding='utf-8'))
    ck('scientific_protection_and_file_identity_audit',report['all_checks_passed'] and all(x['passed'] for x in report['checks']))
    ck('current_db_unchanged',sha(DB)==EXPECTED)
    ck('144_unique_DOIs',len(rows)==len({r['doi'] for r in rows})==144)
    ck('no_auto_admission',all(r['training_eligible'] is False for r in rows))
    for f in json.loads((OUT/'已获取资料索引.json').read_text(encoding='utf-8')):
        ck('file:'+f['path'],sha(ROOT/f['path'])==f['sha256'])
    for md in [*OUT.glob('*.md'),*(ROOT/d for d in DOCS)]:
        # Validate local links in the new batch and entry docs. Ignore links
        # inside inline code and external URLs; preserve all old evidence.
        text=md.read_text(encoding='utf-8')
        for angled,ordinary in re.findall(r'\]\((?:<([^>]+)>|([^)]*))\)',text):
            target=angled or ordinary
            if re.match(r'^[a-zA-Z]+://',target) or target.startswith('#'):continue
            target=urllib.parse.unquote(target.split('#')[0])
            p=(md.parent/target).resolve()
            ck('link:'+md.relative_to(ROOT).as_posix()+':'+target,p.exists())
    with (OUT/'下载任务单.csv').open(encoding='utf-8-sig',newline='') as f:tasks=list(csv.DictReader(f))
    ck('95_CSV_tasks',len(tasks)==len({r['DOI'] for r in tasks})==95)
    bydoi={r['doi']:r for r in rows}
    for t in tasks:
        r=bydoi[t['DOI']]
        ck('task_component:'+r['supply_id'],r['manual_download_recommended'] and r['needed_component']==t['需要下载'])
    ck('first30_exact',len((OUT/'先下载这30篇_DOI.txt').read_text(encoding='utf-8').splitlines())==30)
    files=payload()+[ROOT/'tools'/name for name in TOOLS]+[ROOT/d for d in DOCS]
    scanned=scan(files,ROOT)
    ck('no_known_credential_or_archive_findings',not scanned['credential_pattern_findings'] and not scanned['archive_findings'] and not scanned['oversize_non_lfs_files'])
    for p in payload():
        ck('no_runtime_files:'+p.relative_to(OUT).as_posix(),not any(x in p.parts for x in ['.venv','node_modules','__pycache__','transport_cache']) and p.name not in ['.env','cookies.json','cookies.txt'])
    structure={'all_checks_passed':True,'checks':checks,'preflight':scanned,'scope':'candidate_supply_only','current_v07_sha256':EXPECTED,'training_admissions_added':0,'research_fits':0}
    manifest=OUT/'delivery_manifest.json'
    if seal:
        ck('do_not_overwrite_delivery_manifest',not manifest.exists())
        dump(OUT/'交付结构核验.json',structure)
        result={'delivery_type':'literature_candidate_supply','ready_for_review':True,'ready_for_database_import':False,'automatic_archive':False,'training_eligible':False,'current_database_sha256':EXPECTED,'current_database_pointer_sha256':sha(ROOT/'data/current_database.json'),'source_scope':'120 new targets + 22 historical component gaps + 2 existing candidate SI checks; originals preserved','summary':report['counts'],'outputs':[{'path':p.relative_to(ROOT).as_posix(),'sha256':sha(p),'bytes':p.stat().st_size} for p in payload()],'task_tools':[{'path':(Path('tools')/name).as_posix(),'sha256':sha(ROOT/'tools'/name)} for name in TOOLS],'entry_docs':[{'path':d,'sha256':sha(ROOT/d)} for d in DOCS],'excluded':['transport_cache/','__pycache__/','delivery_manifest.json (self)']}
        dump(manifest,result)
    else:
        result=json.loads(manifest.read_text(encoding='utf-8'))
        for item in result['outputs']+result['task_tools']+result['entry_docs']:
            ck('sealed:'+item['path'],sha(ROOT/item['path'])==item['sha256'])
        ck('sealed_outputs_complete',set(x['path'] for x in result['outputs'])==set(p.relative_to(ROOT).as_posix() for p in payload()))
    print(json.dumps({'all_checks_passed':True,'checks':len(checks),'sealed_outputs':len(result['outputs']),'credential_findings':len(scanned['credential_pattern_findings']),'research_fits':0},ensure_ascii=False))

if __name__=='__main__':verify('--seal' in sys.argv)
