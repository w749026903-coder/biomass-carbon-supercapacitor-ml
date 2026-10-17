from pathlib import Path,PurePosixPath
import json,urllib.request,zipfile,hashlib,concurrent.futures
OUT=Path(__file__).resolve().parent
rows=json.loads((OUT/'manual_endpoint_reviews.json').read_text(encoding='utf-8'));pmcs=sorted({x['source_tag'] for x in rows if x['source_tag'].startswith('PMC')})
def get(pmc):
 d=OUT/'new_sources'/pmc;u='https://www.ebi.ac.uk/europepmc/webservices/rest/'+pmc+'/supplementaryFiles';a={'pmcid':pmc,'url':u}
 try:
  with urllib.request.urlopen(u,timeout=45) as f:b=f.read(85000001)
  if len(b)>85000000:raise ValueError('85MB size limit; kept pending')
  import io
  if not zipfile.is_zipfile(io.BytesIO(b)):raise ValueError('response is not ZIP')
  (d/'figures_and_supplements.zip').write_bytes(b);target=d/'assets';target.mkdir(exist_ok=True);items=[]
  with zipfile.ZipFile(io.BytesIO(b)) as z:
   for member in z.infolist():
    if member.is_dir() or member.file_size>80000000:continue
    name=PurePosixPath(member.filename).name
    if Path(name).suffix.lower() not in ['.jpg','.jpeg','.png','.gif','.tif','.tiff','.pdf','.docx','.doc','.xlsx','.xls','.txt','.csv']:continue
    p=(target/name).resolve()
    if p.parent!=target.resolve():raise ValueError('invalid member name')
    blob=z.read(member)
    if p.exists() and p.read_bytes()!=blob:raise ValueError('basename collision')
    if not p.exists():p.write_bytes(blob)
    items.append({'member':member.filename,'file':'assets/'+name,'bytes':len(blob),'sha256':hashlib.sha256(blob).hexdigest()})
  a.update(status='obtained',zip_bytes=len(b),zip_sha256=hashlib.sha256(b).hexdigest(),files=items)
 except Exception as exc:a.update(status='failed',error=type(exc).__name__+': '+str(exc))
 (d/'figure_package_acquisition.json').write_text(json.dumps(a,ensure_ascii=False,indent=2),encoding='utf-8');return a
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
 results=[]
 for x in pool.map(get,pmcs):results.append(x);print(x['pmcid'],x['status'],x.get('zip_bytes'),flush=True)
(OUT/'figure_packages.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
