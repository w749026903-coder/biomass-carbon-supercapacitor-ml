from pathlib import Path
import json,sys
p=Path('D:/机器学习-超级电容器/文献下载_120篇/download_public.py')
# Reuse only locally authored helper definitions; the batch runner is excluded.
s=p.read_text(encoding='utf-8-sig').split('result=[]\n')[0]
ns={'__file__':str(p)};exec(compile(s,str(p),'exec'),ns)
ROOT=ns['ROOT'];fetch=ns['fetch'];save_pdf=ns['save_pdf'];oa=ns['oa'];concurrent=ns['concurrent'];re=ns['re'];urllib=ns['urllib'];html=ns['html']
from html.parser import HTMLParser
class Links(HTMLParser):
 def __init__(self):super().__init__();self.pdf=[];self.hrefs=[];self.doi=[]
 def handle_starttag(self,tag,attrs):
  d=dict(attrs)
  if tag=='meta':
   k=d.get('name',d.get('property','')).lower();v=d.get('content','')
   if k in ['citation_pdf_url','eprints.document_url','bepress_citation_pdf_url']:self.pdf.append(v)
   if k in ['citation_doi','dc.identifier.doi']:self.doi.append(v.lower().removeprefix('https://doi.org/'))
  if tag=='a' and d.get('href') and re.search(r'\.pdf(?:\?|$)|/bitstream/|/download(?:/|\?|$)',d['href'],re.I):self.hrefs.append(d['href'])
results=json.loads((ROOT/'下载执行结果.json').read_text(encoding='utf-8'));todo=[x for x in results if x['download_status']=='本轮未取得PDF']
def retry(x):
 x=dict(x);x.setdefault('attempts',[]);a=oa[x['doi']];candidates=[]
 # Previously observed public PDF URLs, including institution-hosted author manuscripts.
 for loc in a.get('locations',[]):
  u=loc.get('pdf_url');source=loc.get('source') or {}
  if u and source.get('type')=='repository' and loc.get('is_oa') and 'ssrn' not in u.lower():candidates.append((u,True,'机构公开作者稿_需与正式版核对'))
 if x['doi'].startswith('10.3390/jcs'):
  m=re.fullmatch(r'jcs(\d{2})(\d{2})(\d+)',x['doi'].split('/')[-1])
  if m:
   slug=f'jcs-{int(m[1]):02d}-{int(m[3]):05d}';candidates.insert(0,(f'https://mdpi-res.com/d_attachment/jcs/{slug}/article_deploy/{slug}.pdf',False,'出版社公开版'))
 if x['doi']=='10.3390/c9010024':candidates.insert(0,('https://mdpi-res.com/d_attachment/carbon/carbon-09-00024/article_deploy/carbon-09-00024-v2.pdf',False,'出版社公开版'))
 for u,proven,version in candidates:
  try:
   b,final,_=fetch(u);x.update(save_pdf(b,x,final,proven),download_status='新增PDF已核验_待归档',source_version=version);return x
  except Exception as e:x['attempts'].append({'url':u,'error':'复查PDF: '+str(e)})
 landings=[]
 for loc in a.get('locations',[]):
  u=loc.get('landing_page_url');source=loc.get('source') or {}
  if loc.get('is_oa') and u and source.get('display_name') not in ['SSRN Electronic Journal','DOAJ (DOAJ: Directory of Open Access Journals)']:landings.append((u,source.get('type')=='repository'))
 if not landings:landings=[('https://doi.org/'+x['doi'],False)]
 seen=set()
 for u,isrepo in landings[:2]:
  if u in seen:continue
  seen.add(u)
  try:
   # Public Figshare API exposes downloadable files without account interaction.
   fm=re.search(r'figshare.com/articles/(?:[^/]+/[^/]+/)?(\d+)',u)
   if fm:
    api='https://api.figshare.com/v2/articles/'+fm[1];b,_,_=fetch(api);record=json.loads(b);(ROOT/'来源元数据'/(x['collection_id']+'_Figshare.json')).write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    pdfs=[f['download_url'] for f in record.get('files',[]) if f.get('name','').lower().endswith('.pdf')]
    for pu in pdfs[:2]:
     try:
      pb,pfinal,_=fetch(pu);x.update(save_pdf(pb,x,pfinal,True),download_status='新增PDF已核验_待归档',source_version='作者机构公开存档_版本待全文核对');return x
     except Exception as e:x['attempts'].append({'url':pu,'error':str(e)})
   b,final,ctype=fetch(u,8*1024*1024)
   if b[:1024].lstrip().startswith(b'%PDF-'):
    x.update(save_pdf(b,x,final,isrepo),download_status='新增PDF已核验_待归档',source_version='公开存档版_版本待核对');return x
   parser=Links();parser.feed(b.decode('utf-8',errors='replace'))
   pdfs=parser.pdf+parser.hrefs[:2]
   for pu in list(dict.fromkeys(pdfs))[:3]:
    pu=urllib.parse.urljoin(final,html.unescape(pu))
    if urllib.parse.urlparse(pu).scheme not in ['http','https']:continue
    try:
     pb,pfinal,_=fetch(pu);identity=isrepo and x['doi'] in parser.doi
     x.update(save_pdf(pb,x,pfinal,identity),download_status='新增PDF已核验_待归档',source_version='公开存档版_版本待全文核对');return x
    except Exception as e:x['attempts'].append({'url':pu,'error':str(e)})
   if not pdfs:x['attempts'].append({'url':u,'error':'公开页面未发现可用PDF链接（可能需要机构访问）'})
  except Exception as e:x['attempts'].append({'url':u,'error':'复查公开页面: '+str(e)})
 x['failure_summary']='；'.join(dict.fromkeys(y.get('error','') for y in x['attempts'])) or '未发现公开全文直链';return x
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
 fs={ex.submit(retry,x):x['collection_id'] for x in todo};n=0
 for f in concurrent.futures.as_completed(fs):
  n+=1
  try:x=f.result()
  except Exception as e:
   x=next(z for z in todo if z['collection_id']==fs[f]);x['failure_summary']='复查处理异常:'+str(e)
  results=[x if z['collection_id']==x['collection_id'] else z for z in results]
  (ROOT/'下载复查结果.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
  print(n,'/',len(todo),x['collection_id'],x['download_status'],flush=True)
print('RECHECK COMPLETE',len(results))
