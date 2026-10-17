from pathlib import Path
import json, urllib.request, urllib.parse, concurrent.futures, hashlib
ROOT=Path(__file__).resolve().parents[1];OUT=Path(__file__).resolve().parent
if __name__=='__main__':
 pending=json.loads((ROOT/'用户补充文献核验_20261018/待补资料_更新.json').read_text('utf-8'))
 si=pending['main_received_but_declared_SI_missing_or_existing_SI_only_task']
 q=' OR '.join('DOI:"'+r['doi']+'"' for r in si)
 u='https://www.ebi.ac.uk/europepmc/webservices/rest/search?'+urllib.parse.urlencode({'query':q,'format':'json','resultType':'core','pageSize':100})
 with urllib.request.urlopen(u,timeout=25) as f:x=json.load(f)
 (OUT/'old_si_epmc_recheck.json').write_text(json.dumps({'url':u,'data':x},ensure_ascii=False,indent=2),encoding='utf-8')
 # Publisher SI routes are public. Try each requested component once; retain HTTP failures.
 tasks=[]
 for r in si:
  doi=r['doi'].lower();url=None
  if doi.startswith('10.1039/'):
   key=doi.split('/')[1];url=f'https://www.rsc.org/suppdata/{key[:2]}/{key[2:4]}/{key}/{key}1.pdf'
  elif doi.startswith('10.1021/'):
   key=doi.split('/')[1];journal,code=key.split('.',1);url=f'https://pubs.acs.org/doi/suppl/{doi}/suppl_file/{journal}{code}_si_001.pdf'
  elif doi=='10.1002/ente.202201281':url='https://onlinelibrary.wiley.com/doi/suppl/10.1002/ente.202201281/supinfo/ente202201281-sup-0001-suppmat.pdf'
  elif doi=='10.1155/2024/4961636':url='https://onlinelibrary.wiley.com/doi/suppl/10.1155/2024/4961636/supinfo/4961636-sup-0001.pdf'
  elif doi=='10.1016/j.jics.2025.102074':url=None
  tasks.append((r,url))
 def get(task):
  r,u=task;rec={'id':r['id'],'doi':r['doi'],'component':'SI','url':u,'status':'pending'}
  if u is None:return {**rec,'reason':'No verified direct public SI file URL; publisher component still pending'}
  try:
   with urllib.request.urlopen(u,timeout=20) as f:b=f.read(30000001)
   if len(b)>30000000 or not b.startswith(b'%PDF-'):raise ValueError('not a valid bounded PDF response')
   from pypdf import PdfReader
   import io
   reader=PdfReader(io.BytesIO(b));front=' '.join((p.extract_text() or '') for p in reader.pages[:2])
   # Even a real PDF must match its article; unresolved identities stay pending.
   if r['doi'].split('/')[1].lower() not in front.lower():
    rec.update(status='downloaded_identity_pending',reason='PDF downloaded; title/DOI identity needs review')
   else:rec['status']='obtained_identity_verified'
   d=OUT/'old_requested_si';d.mkdir(exist_ok=True);p=d/(r['id']+'_SI.pdf');p.write_bytes(b)
   rec.update(path=p.relative_to(ROOT).as_posix(),sha256=hashlib.sha256(b).hexdigest(),bytes=len(b),front_excerpt=front[:1800])
  except Exception as e:rec['reason']=str(e)
  return rec
 with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:results=list(pool.map(get,tasks))
 (OUT/'old_si_download_attempts.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps([{'doi':x['doi'],'status':x['status'],'reason':x.get('reason')} for x in results],ensure_ascii=False,indent=2))
