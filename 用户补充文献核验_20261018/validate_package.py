"""Validate exact PDF copies, source immutability, local links and scope before task sync."""
from pathlib import Path
import json,hashlib,re,urllib.parse,sys
ROOT=Path(__file__).resolve().parents[1];OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tools'))
from repository_checks import scan

def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8',newline='\n')
checks=[]
def add(name,ok,details):checks.append({'name':name,'passed':bool(ok),'details':details})
records=json.loads((OUT/'核验记录_26份.json').read_text(encoding='utf-8'))['records']
add('26 user PDF files identified',len(records)==26,len(records))
add('All user originals unchanged',all(sha(Path(x['original_path']))==x['sha256'] for x in records),26)
copied=[x for x in records if x['repository_pdf']]
add('22 byte-identical project copies',len(copied)==22 and all(sha(ROOT/x['repository_pdf'])==x['sha256'] for x in copied),len(copied))
add('Evidence page references in range',all(all(1<=p<=x['pages'] for p in x['pdf_evidence_pages']) for x in records),True)
protected=json.loads((OUT/'protected_existing_fingerprints.json').read_text(encoding='utf-8'))
add('Existing databases and manifests unchanged',all(sha(ROOT/x['path'])==x['sha256'] for x in protected),len(protected))
a=json.loads((OUT/'新增50篇_正文可用状态更新.json').read_text(encoding='utf-8'))
add('50-paper main availability 43/7',len(a['records'])==50 and sum(x['main_available_now'] for x in a['records'])==43,{'available':43,'missing':7})
pending=json.loads((OUT/'待补资料_更新.json').read_text(encoding='utf-8'))
add('13 main and 9 SI tasks separated',len(pending['missing_main'])==13 and len(pending['main_received_but_declared_SI_missing_or_existing_SI_only_task'])==9,True)
for name,expected in [('仍缺正文_完整DOI.txt',13),('仍需SI_完整DOI.txt',9),('原目标仍需下载_全部DOI.txt',22)]:
 ds=(OUT/name).read_text(encoding='utf-8').splitlines();add(name,len(ds)==len(set(ds))==expected,len(ds))
add('No scientific admissions',all(not x['training_admitted'] for x in records),0)
missing=[];count=0
for p in [ROOT/'README.md',ROOT/'docs/CURRENT_STATE.md',ROOT/'docs/LITERATURE_INDEX.md',OUT/'核验报告与交接.md']:
 text=p.read_text(encoding='utf-8')
 add('No hidden controls in '+p.name,not re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f\ufeff]',text),True)
 for m in re.finditer(r'\]\(([^)]+)\)',text):
  url=m.group(1)
  if re.match(r'(https?:|mailto:|#)',url):continue
  count+=1
  if not (p.parent/urllib.parse.unquote(url.split('#')[0])).resolve().exists():missing.append({'file':p.name,'target':url})
add('Local delivery links valid',not missing,{'checked':count,'missing':missing})
for p in OUT.glob('*.py'):compile(p.read_text(encoding='utf-8-sig'),str(p),'exec')
add('New scripts parse',True,len(list(OUT.glob('*.py'))))
paths=[p for p in OUT.rglob('*') if p.is_file() and p.name not in ['validation.json','merge_manifest.json']]
security=scan(paths,ROOT)
add('Known credential and size checks',not(security['credential_pattern_findings'] or security['oversize_non_lfs_files'] or security['archive_findings']),security)
all_ok=all(x['passed'] for x in checks)
dump(OUT/'validation.json',{'all_passed':all_ok,'checks':checks,'visual_review':{'26_first_pages_rendered_and_reviewed':True,'key_pages':['U002 p2 Accepted Manuscript','U010 p7 three-electrode CV','U011 p10 conflicting retention','U017 p6 lower-bound and 15000-cycle claim','U024 p10 three-electrode vs device and current conflict']}})
if not all_ok:print(json.dumps([x for x in checks if not x['passed']],ensure_ascii=False));raise SystemExit(1)
files=[p for p in OUT.rglob('*') if p.is_file() and p.name!='merge_manifest.json']
dump(OUT/'merge_manifest.json',{'date':'2026-10-18','task_role':'user_supplied_literature_receipt_and_identity_audit','ready_for_review':True,'ready_for_merge':False,'scientific_database_modified':False,'research_fits':0,'training_admitted':0,'new_independent_materials_finalized':0,'outputs':[{'path':p.relative_to(ROOT).as_posix(),'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(files)],'unresolved':['13 original-target DOIs still lack main text','9 original-target DOIs with available main text still need declared/requested SI','Protocol conflicts, mass denominator and material identity are not finalized','Three extra biomass studies are staged candidates only'],'manifest_excludes_itself':True})
print(json.dumps({'all_passed':True,'checks':len(checks),'local_links_checked':count,'files_in_package':len(files)+1,'pdf_copies':22,'copy_bytes':sum(x['bytes'] for x in copied)},ensure_ascii=False))
