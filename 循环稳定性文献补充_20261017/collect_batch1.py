"""New, bounded collection; never modifies the existing library or snapshots."""
import concurrent.futures, hashlib, io, json, pathlib, re, urllib.request, urllib.error
from pypdf import PdfReader

ROOT = pathlib.Path(__file__).resolve().parent
BASE = ROOT.parent
PAPERS = [
 ('N001','10.1039/d5ra03028e','https://pubs.rsc.org/en/content/articlehtml/2025/ra/d5ra03028e','https://pubs.rsc.org/en/content/articlepdf/2025/ra/d5ra03028e'),
 ('N002','10.1039/d5ra08165c','https://pubs.rsc.org/en/content/articlehtml/2026/ra/d5ra08165c','https://pubs.rsc.org/en/content/articlepdf/2026/ra/d5ra08165c'),
 ('N003','10.1039/d6nj00244g','https://pubs.rsc.org/en/content/articlelanding/2026/nj/d6nj00244g','https://pubs.rsc.org/en/content/articlepdf/2026/nj/d6nj00244g'),
 ('N004','10.3390/nano15131028','https://www.mdpi.com/2079-4991/15/13/1028','https://www.mdpi.com/2079-4991/15/13/1028/pdf'),
 ('N005','10.3390/molecules30010026','https://www.mdpi.com/1420-3049/30/1/26','https://www.mdpi.com/1420-3049/30/1/26/pdf'),
 ('N006','10.1016/j.biombioe.2025.108104','https://www.sciencedirect.com/science/article/abs/pii/S096195342500515X',None),
 ('N007','10.1016/j.electacta.2025.145880','https://doi.org/10.1016/j.electacta.2025.145880',None),
 ('N008','10.1016/j.cej.2025.161386','https://nottingham-repository.worktribe.com/output/46459620','https://files01.core.ac.uk/download/pdf/645984773.pdf'),
 ('N009','10.1016/j.jics.2025.102074','https://doi.org/10.1016/j.jics.2025.102074','https://ticnn.tju.edu.cn/dfiles/12783/images/publication/2025/jw.pdf'),
]

def get(url):
 req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (compatible; literature research)'})
 with urllib.request.urlopen(req,timeout=35) as r:
  return r.read(),r.geturl(),r.headers.get('Content-Type','')

def save_pdf(url, dest, doi, role):
 out={'url':url,'role':role}
 try:
  b,final,ct=get(url)
  if not b.startswith(b'%PDF-'): raise ValueError('Not a PDF: '+ct)
  reader=PdfReader(io.BytesIO(b)); texts=[p.extract_text() or '' for p in reader.pages]
  if not texts: raise ValueError('zero PDF pages')
  dest.write_bytes(b)
  textdest=dest.with_suffix('.pages.json')
  textdest.write_text(json.dumps([{'page':i+1,'text':t} for i,t in enumerate(texts)],ensure_ascii=False,indent=2),encoding='utf-8')
  out.update(status='downloaded_pending_identity_review',path=str(dest),bytes=len(b),sha256=hashlib.sha256(b).hexdigest(),pages=len(texts),doi_in_text=doi.lower() in re.sub(r'\s+','', '\n'.join(texts)).lower(),final_url=final,content_type=ct)
 except Exception as e: out.update(status='failed',error=type(e).__name__+': '+str(e)[:230])
 return out

def run(p):
 ident,doi,landing,pdf=p; folder=ROOT/ident;folder.mkdir(exist_ok=True)
 existing=json.loads((BASE/'训练适用性审核_20261016/逐份训练用途审核.json').read_text(encoding='utf-8-sig'))
 matches=[x['id'] for x in existing if (x.get('doi') or '').lower()==doi]
 out={'id':ident,'doi':doi,'landing_url':landing,'existing_doi_matches':matches,'downloads':[],'eligible_for_database':False}
 try:
  b,_,_=get('https://api.crossref.org/works/'+doi); m=json.loads(b)['message']
  out['crossref']={k:m.get(k) for k in ['DOI','title','type','publisher','container-title','published','published-online','published-print','link','relation','update-to']}
 except Exception as e: out['crossref_error']=str(e)[:200]
 if matches: out['status']='duplicate_existing';return out
 try:
  b,final,ct=get(landing)
  html=b.decode('utf-8',errors='replace');(folder/'landing.html').write_text(html,encoding='utf-8')
  out['landing_final_url']=final
  supp=re.findall(r'(?:href|src)=["\']([^"\']+(?:suppldata|supplementary|suppinfo)[^"\']+)["\']',html,re.I)
  out['supplement_links']=list(dict.fromkeys(urllib.parse.urljoin(final,u.replace('&amp;','&')) for u in supp))
 except Exception as e: out['landing_error']=str(e)[:200]
 if pdf: out['downloads'].append(save_pdf(pdf,folder/'正文.pdf',doi,'main'))
 for i,u in enumerate(out.get('supplement_links',[])[:4]):
  if '.pdf' in u.lower(): out['downloads'].append(save_pdf(u,folder/f'SI_{i+1}.pdf',doi,'supplement'))
 out['status']='downloaded_some' if any(x['status'].startswith('downloaded') for x in out['downloads']) else 'needs_user_download'
 (folder/'acquisition.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
 return out

if __name__=='__main__':
 results=[]
 with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
  for r in ex.map(run,PAPERS):
   results.append(r); print(r['id'],r['doi'],r['status'],r.get('crossref',{}).get('title'),[(x['role'],x['status'],x.get('pages'),x.get('error')) for x in r['downloads']],flush=True)
 (ROOT/'第一批获取原始记录.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
