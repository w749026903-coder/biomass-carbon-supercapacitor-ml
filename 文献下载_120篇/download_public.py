import concurrent.futures,hashlib,html,io,json,re,sys,urllib.parse,urllib.request,xml.etree.ElementTree as ET
from pathlib import Path
from pypdf import PdfReader
sys.stdout.reconfigure(encoding='utf-8')
ROOT=Path(__file__).resolve().parent; PROJECT=ROOT.parent; STAGE=ROOT/'PDF暂存'; META=ROOT/'来源元数据'; SUPP=ROOT/'补充材料暂存'
for p in [STAGE,META,SUPP]:p.mkdir(exist_ok=True)
rows=json.loads((PROJECT/'文献扩充_生物质碳_120篇/120篇候选文献.json').read_text(encoding='utf-8'))
oa={x['doi'].removeprefix('https://doi.org/').lower():x for x in json.loads((ROOT/'OpenAlex_全部匹配.json').read_text(encoding='utf-8'))}
epmc={x['doi'].lower():x for x in json.loads((ROOT/'EuropePMC_匹配.json').read_text(encoding='utf-8')) if x.get('doi')}
raw={x['DOI'].lower():x for x in json.loads((PROJECT/'文献扩充_生物质碳_120篇/检索合并原始.json').read_text(encoding='utf-8'))}
prior=json.loads((PROJECT/'文献搜集_生物质碳_第一批/搜集结果.json').read_text(encoding='utf-8'))
prior={x['doi'].lower():x for x in prior}
blocked={x['doi'].lower() for x in json.loads((PROJECT/'文献扩充_生物质碳_120篇/禁止入库与待核查来源.json').read_text(encoding='utf-8'))}

def fetch(url,limit=40*1024*1024):
 req=urllib.request.Request(url,headers={'User-Agent':'AcademicLiteratureCollector/1.0','Accept':'*/*'})
 with urllib.request.urlopen(req,timeout=22) as f:
  data=f.read(limit+1)
  if len(data)>limit:raise ValueError('超过本轮单文件40MiB上限')
  return data,f.geturl(),f.headers.get('Content-Type','')
def norm(s):return re.sub(r'[^a-z0-9]','',s.lower())
def s3http(s):return s.replace('s3://pmc-oa-opendata/','https://pmc-oa-opendata.s3.amazonaws.com/')
def validate(data,row,proven=False):
 if not data[:1024].lstrip().startswith(b'%PDF-'):raise ValueError('响应不是PDF，未保存为论文')
 d=PdfReader(io.BytesIO(data))
 if len(d.pages)<2:raise ValueError('PDF不足2页，需确认是否摘要')
 text='\n'.join((p.extract_text() or '') for p in d.pages[:3]);first=d.pages[0].extract_text() or ''
 doiok=norm(row['doi']) in norm(text)
 words=set(re.findall(r'[a-z]{4,}',row['title'].lower()))
 overlap=len(words & set(re.findall(r'[a-z]{4,}',first.lower())))/max(1,len(words))
 if not (doiok and overlap>=0.5) and not (proven and overlap>=0.75):raise ValueError(f'论文对应关系待人工核对 DOI={doiok}, title={overlap:.2f}')
 return {'pages':len(d.pages),'doi_in_first3_pages':doiok,'title_token_overlap':round(overlap,3),'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)}
def save_pdf(data,row,url,proven=False,md5=None):
 if md5 and hashlib.md5(data).hexdigest()!=md5:raise ValueError('源站MD5校验不符')
 info=validate(data,row,proven);name=row['collection_id']+'__'+row['doi'].replace('/','__')+'.pdf';p=STAGE/name
 if p.exists():
  if hashlib.sha256(p.read_bytes()).hexdigest()!=info['sha256']:raise ValueError('暂存存在不同内容同名文件')
 else:
  with p.open('xb') as f:f.write(data)
 return dict(info,staged_path=str(p),filename=name,source_pdf_url=url)
def collect(original):
 row=dict(original);row['attempts']=[];row['supplements']=[]
 doi=row['doi'];a=oa.get(doi,{})
 if doi in blocked or a.get('is_retracted'):
  row['download_status']='冻结或撤稿标记_不下载';return row
 if row.get('local_pdf') and Path(row['local_pdf']).is_file():
  p=Path(row['local_pdf']);row.update(download_status='已有PDF_未重复下载',sha256=hashlib.sha256(p.read_bytes()).hexdigest());return row
 # Official PMC open-data metadata provides identity, licensing and published/manuscript version.
 pmcid=epmc.get(doi,{}).get('pmcid')
 if not pmcid:
  for loc in a.get('locations',[]):
   m=re.search(r'pubmedcentral.nih.gov:(\d+)',loc.get('id',''))
   if m:pmcid='PMC'+m[1];break
 if pmcid:
  try:
   url='https://pmc-oa-opendata.s3.amazonaws.com/?'+urllib.parse.urlencode({'list-type':'2','prefix':pmcid+'.','delimiter':'/'})
   b,_,_=fetch(url);tree=ET.fromstring(b);prefixes=[v.text for v in tree.findall('.//{*}CommonPrefixes/{*}Prefix')]
   variants=[]
   for prefix in prefixes[:4]:
    u='https://pmc-oa-opendata.s3.amazonaws.com/'+prefix+prefix.rstrip('/')+'.json';b,_,_=fetch(u);m=json.loads(b)
    if str(m.get('doi','')).lower()!=doi:continue
    (META/(row['collection_id']+'_'+prefix.rstrip('/')+'.json')).write_text(json.dumps(m,ensure_ascii=False,indent=2),encoding='utf-8')
    if m.get('is_retracted'):
     row['download_status']='PMC撤稿标记_冻结';return row
    if m.get('pdf_url'):variants.append(m)
   variants.sort(key=lambda m:bool(m.get('is_manuscript')))
   for m in variants:
    try:
     u=s3http(m['pdf_url']);b,final,_=fetch(u);md5=urllib.parse.parse_qs(urllib.parse.urlparse(u).query).get('md5',[None])[0]
     row.update(save_pdf(b,row,final,True,md5),download_status='新增PDF已核验_待归档',source_version='author_manuscript' if m.get('is_manuscript') else 'published_version',license=m.get('license_code'),pmcid=pmcid)
     for media in m.get('media_urls',[]):
      mu=s3http(media);base=Path(urllib.parse.urlparse(mu).path).name
      if not re.search(r'\.(pdf|xlsx|xls|csv|tsv|docx|txt)$',base,re.I):continue
      if base==Path(urllib.parse.urlparse(u).path).name:continue
      try:
       sb,surl,_=fetch(mu,15*1024*1024);want=urllib.parse.parse_qs(urllib.parse.urlparse(mu).query).get('md5',[None])[0]
       if want and hashlib.md5(sb).hexdigest()!=want:raise ValueError('补充文件MD5不符')
       if base.lower().endswith('.pdf') and not sb[:1024].lstrip().startswith(b'%PDF-'):raise ValueError('补充PDF类型不符')
       sp=SUPP/(row['collection_id']+'__'+base)
       if not sp.exists():
        with sp.open('xb') as f:f.write(sb)
       row['supplements'].append({'filename':sp.name,'staged_path':str(sp),'sha256':hashlib.sha256(sb).hexdigest(),'bytes':len(sb),'url':surl})
      except Exception as e:row['attempts'].append({'url':mu,'error':'supplement: '+str(e)})
     return row
    except Exception as e:row['attempts'].append({'url':m['pdf_url'],'error':str(e)})
  except Exception as e:row['attempts'].append({'source':'PMC official cloud','error':str(e)})
 # Public PDF URLs recorded by OpenAlex and Crossref, plus publisher CDN equivalents.
 candidates=[]
 for loc in ([a.get('best_oa_location')] + a.get('locations',[])):
  if loc and loc.get('pdf_url') and loc.get('is_oa'):candidates.append(loc['pdf_url'])
 p=prior.get(doi,{})
 candidates.extend(p.get('pdf_urls',[]))
 cr=raw.get(doi,{})
 for link in cr.get('link',[]):
  u=link.get('URL','')
  if 'pdf' in link.get('content-type','').lower() or re.search(r'\.pdf(?:\?|$)|/pdf(?:direct)?/',u,re.I):candidates.append(u)
 if doi.startswith('10.3390/'):
  code=doi.split('/')[-1];m=re.fullmatch(r'([a-z]+)(\d{2})(\d{2})(\d+)',code)
  journals={'nano':'nanomaterials','molecules':'molecules','ma':'materials','c':'carbon','batteries':'batteries','en':'energies','su':'sustainability','catal':'catalysts','polym':'polymers','ijms':'ijms','app':'applsci','chemistry':'chemistry'}
  if m and m[1] in journals:
   j=journals[m[1]];slug=f'{j}-{int(m[2]):02d}-{int(m[4]):05d}';candidates.insert(0,f'https://mdpi-res.com/d_attachment/{j}/{slug}/article_deploy/{slug}.pdf')
 seen=set()
 for u in candidates[:8]:
  if u in seen:continue
  seen.add(u)
  if not u.startswith('https://'):continue
  # Never use paid mirrors, cached API content or credentials.
  if any(v in urllib.parse.urlparse(u).hostname.lower() for v in ['sci-hub','libgen']):continue
  try:
   b,final,_=fetch(u);row.update(save_pdf(b,row,final),download_status='新增PDF已核验_待归档',source_version='公开源版本_以PDF为准');return row
  except Exception as e:row['attempts'].append({'url':u,'error':str(e)})
 row['download_status']='本轮未取得PDF'
 row['failure_summary']='；'.join(dict.fromkeys(x.get('error','') for x in row['attempts'])) or '未发现可直接获取的公开PDF链接'
 row['oa_reported']=bool(a.get('open_access',{}).get('is_oa'))
 return row
result=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
 futures={ex.submit(collect,row):row['collection_id'] for row in rows}
 for f in concurrent.futures.as_completed(futures):
  try:z=f.result()
  except Exception as e:
   z=dict(next(x for x in rows if x['collection_id']==futures[f]));z.update(download_status='本轮未取得PDF',failure_summary='处理异常:'+str(e))
  result.append(z);result.sort(key=lambda x:x['collection_id'])
  (ROOT/'下载执行结果.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
  print(len(result),z['collection_id'],z['download_status'],flush=True)
print('COMPLETE',len(result),flush=True)
