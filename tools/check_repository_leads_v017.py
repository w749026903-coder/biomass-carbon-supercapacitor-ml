"""Read three newly observed public repository/version URLs once, with deduplication."""
from pathlib import Path
import concurrent.futures, datetime, hashlib, json, re, urllib.request, urllib.error, urllib.parse
ROOT=Path(__file__).resolve().parents[1];B=ROOT/'持续补正_v017_20261024'
JOBS=[
 ('KF_PSAC_author_repository','https://avesis.yyu.edu.tr/publication/details/86dd3c8c-cdf5-4ae3-b3c8-1b0645d5bfc9/oai',None),
 ('FeSN_Griffith_repository','https://research-repository.griffith.edu.au/bitstreams/f8b09d76-d558-4f7e-bffc-596dea243ecd/download','三电极端点扩充_20261018/corpus/B_R081/main.pdf'),
 ('HTWB_latest_preprint','https://www.researchsquare.com/article/rs-11058750/latest.pdf','新增文献整理_20261020/originals/ADD_058.pdf')]

def sha(path):
 with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def main():
 out=B/'new_repository_lead_checks.json'
 if out.exists():raise FileExistsError('Do not repeat unchanged repository checks.')
 def get(job):
  name,url,existing=job;r=dict(name=name,url=url,checked_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),scientific_admission=False)
  opener=urllib.request.build_opener(urllib.request.ProxyHandler({'http':'http://127.0.0.1:7890','https':'http://127.0.0.1:7890'}))
  try:
   with opener.open(urllib.request.Request(url,headers={'User-Agent':'LiteratureEvidenceAudit/1.0'}),timeout=25) as f:
    payload=f.read(20*1024*1024+1);r.update(status=f.status,content_type=f.headers.get('Content-Type'),final_url=f.url)
   if len(payload)>20*1024*1024:raise ValueError('Response exceeds bounded20MiB; not saved.')
   digest=hashlib.sha256(payload).hexdigest();r.update(bytes=len(payload),sha256=digest)
   if existing and sha(ROOT/existing)==digest:
    r.update(state='same_existing_document_no_duplicate_saved',existing_path=existing);return r
   if payload.startswith(b'%PDF'):
    path=B/'retrieved'/('newlead_'+name+'.pdf');path.write_bytes(payload);r.update(state='new_PDF_identity_and_content_review_required',path=path.relative_to(ROOT).as_posix())
   else:
    text=payload.decode('utf8','replace')
    if any(x in text.lower() for x in ['just a moment','captcha','checking your browser']):
     r.update(state='browser_check_not_article_not_saved');return r
    path=B/'retrieved'/('newlead_'+name+'.html');path.write_bytes(payload);r.update(state='repository_page_not_article',path=path.relative_to(ROOT).as_posix())
    r['candidate_links']=sorted(set(urllib.parse.urljoin(r['final_url'],x.replace('&amp;','&')) for x in re.findall(r'(?:href|src)=[\"\']([^\"\']+)',text) if any(s in x.lower() for s in ['pdf','file','download','document','upload','bitstream'])))[:60]
  except urllib.error.HTTPError as e:r.update(status=e.code,state='not_retrieved')
  except Exception as e:r.update(state='not_retrieved',error=type(e).__name__+': '+str(e)[:220])
  return r
 with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:rows=list(pool.map(get,JOBS))
 out.write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n','utf8')
 print(json.dumps(rows,ensure_ascii=False))

if __name__=='__main__':main()
