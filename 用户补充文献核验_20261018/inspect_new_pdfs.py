from pathlib import Path
import json,re,hashlib,datetime
from pypdf import PdfReader
ROOT=Path(__file__).resolve().parents[1]
OUT=Path(__file__).resolve().parent
(OUT/'texts').mkdir(exist_ok=True)
inputs=sorted(Path('D:/文献').glob('*.pdf'),key=lambda p:p.name.casefold())
needed=json.loads((ROOT/'同体系文献补充_第二批_20261017/全部需下载资料_逐项用途.json').read_text(encoding='utf-8'))['records']
pat=re.compile(r'10\.\d{4,9}/[-._;()/:A-Z0-9]+',re.I)
records=[]
for i,p in enumerate(inputs,1):
 uid=f'U{i:03d}';record={'id':uid,'original_path':str(p),'filename':p.name,'bytes':p.stat().st_size,'mtime_ns':p.stat().st_mtime_ns}
 with p.open('rb') as f:record['sha256']=hashlib.file_digest(f,'sha256').hexdigest()
 try:
  reader=PdfReader(p);pages=[page.extract_text() or '' for page in reader.pages]
  full='\n\n'.join(f'=== PDF PAGE {j+1} ===\n'+s for j,s in enumerate(pages))
  (OUT/'texts'/f'{uid}.txt').write_text(full,encoding='utf-8')
  front='\n'.join(pages[:2]);record.update({'pages':len(pages),'text_characters':sum(map(len,pages)),'metadata_title':str((reader.metadata or {}).get('/Title','')),'front_dois':list(dict.fromkeys(m.group().rstrip('.,;:').lower() for m in pat.finditer(front))),'matched_pending':[{k:n[k] for k in ['id','doi','needed','title']} for n in needed if n['doi'].lower() in re.sub(r'\s+','',front).lower()],'front_excerpt':front[:1700],'page_text_file':f'texts/{uid}.txt'})
 except Exception as exc:record['error']=type(exc).__name__+': '+str(exc)
 records.append(record)
(OUT/'initial_inventory.json').write_text(json.dumps({'scope':'Only the 26 PDFs newly placed in D:/文献 root; existing classified folders were not scanned or altered.','records':records},ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps([{'id':x['id'],'file':x['filename'],'pages':x.get('pages'),'front_dois':x.get('front_dois'),'matched_pending':x.get('matched_pending'),'front_excerpt':x.get('front_excerpt','')[:300],'error':x.get('error')} for x in records],ensure_ascii=False,indent=2))
