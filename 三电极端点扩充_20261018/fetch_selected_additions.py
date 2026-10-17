"""Fetch selected primary PDFs/figure packages and recheck old missing DOIs.
Only task-owned files are written. Never treat HTML or an HTTP error as a PDF.
"""
from pathlib import Path, PurePosixPath
import json, urllib.request, urllib.parse, concurrent.futures, hashlib, zipfile, io, xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]; OUT=Path(__file__).resolve().parent
def write(name,obj): (OUT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
def fetch(url,limit=85000000):
 with urllib.request.urlopen(url,timeout=22) as f: b=f.read(limit+1)
 if len(b)>limit: raise ValueError('size limit')
 return b
def selected(pmc):
 d=OUT/'new_sources'/pmc; log={'pmcid':pmc,'attempts':[]}
 pack=d/'figure_package_acquisition.json'
 if not pack.exists():
  url=f'https://www.ebi.ac.uk/europepmc/webservices/rest/{pmc}/supplementaryFiles'
  try:
   b=fetch(url); z=zipfile.ZipFile(io.BytesIO(b)); (d/'figures_and_supplements.zip').write_bytes(b)
   target=d/'assets';target.mkdir(exist_ok=True);items=[]
   for m in z.infolist():
    if m.is_dir() or m.file_size>80000000:continue
    name=PurePosixPath(m.filename).name
    if Path(name).suffix.lower() not in ['.jpg','.jpeg','.gif','.png','.pdf','.doc','.docx','.xls','.xlsx','.txt','.csv']:continue
    p=(target/name).resolve();assert p.parent==target.resolve();blob=z.read(m)
    if p.exists() and p.read_bytes()!=blob:raise ValueError('collision')
    if not p.exists():p.write_bytes(blob)
    items.append({'member':m.filename,'file':'assets/'+name,'bytes':len(blob),'sha256':hashlib.sha256(blob).hexdigest()})
   record={'pmcid':pmc,'url':url,'status':'obtained','zip_bytes':len(b),'zip_sha256':hashlib.sha256(b).hexdigest(),'files':items}
   pack.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
   log['attempts'].append({'url':url,'status':'obtained','format':'ZIP'})
  except Exception as e:log['attempts'].append({'url':url,'status':'failed','error':str(e)})
 if not (d/'main.pdf').exists():
  url=f'https://europepmc.org/articles/{pmc}?pdf=render'
  try:
   b=fetch(url,30000000)
   if not b.startswith(b'%PDF-'):raise ValueError('response is not a PDF; XML retained as available full text')
   (d/'main.pdf').write_bytes(b);log['attempts'].append({'url':url,'status':'obtained','format':'PDF','sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b)})
  except Exception as e:log['attempts'].append({'url':url,'status':'failed','format':'PDF','error':str(e)})
 (d/'additional_acquisition.json').write_text(json.dumps(log,ensure_ascii=False,indent=2),encoding='utf-8');return log
if __name__=='__main__':
 rows=json.loads((OUT/'manual_endpoint_reviews.json').read_text('utf-8'));pmcs=sorted({r['source_tag'] for r in rows if r['source_tag'].startswith('PMC')})
 with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
  logs=[]
  for x in pool.map(selected,pmcs):logs.append(x);print(x['pmcid'],[(a['format'] if 'format' in a else 'package',a['status']) for a in x['attempts']],flush=True)
 write('selected_additional_downloads.json',logs)
 pending=json.loads((ROOT/'用户补充文献核验_20261018/待补资料_更新.json').read_text('utf-8'))
 dois=sorted({r['doi'].lower() for k in ['missing_main','missing_si'] for r in pending.get(k,[])})
 q=' OR '.join('DOI:"'+d+'"' for d in dois)
 u='https://www.ebi.ac.uk/europepmc/webservices/rest/search?'+urllib.parse.urlencode({'query':q,'format':'json','resultType':'core','pageSize':100})
 try:write('old_pending_epmc_recheck.json',{'url':u,'requested_dois':dois,'data':json.loads(fetch(u))})
 except Exception as e:write('old_pending_epmc_recheck.json',{'url':u,'requested_dois':dois,'error':str(e)})
