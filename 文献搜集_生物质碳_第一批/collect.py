import concurrent.futures,hashlib,io,json,re,sys,urllib.parse,urllib.request
from pathlib import Path
from pypdf import PdfReader
sys.stdout.reconfigure(encoding='utf-8')
ROOT=Path(__file__).resolve().parent
STAGE=ROOT/'下载暂存'; STAGE.mkdir(exist_ok=True)
TEXT=ROOT/'全文核查'; TEXT.mkdir(exist_ok=True)
rows=json.loads((ROOT/'候选清单.json').read_text(encoding='utf-8'))
cache={'R01':'Review_NXMATE2026101971.pdf','R02':'下载_Review_JPS2020227794.pdf','E07':'下载_nano12213804.pdf','E08':'下载_nano14161368.pdf','E09':'下载_molecules27030791.pdf'}
def fetch(u):
 req=urllib.request.Request(u,headers={'User-Agent':'LiteratureCollection/1.0'})
 with urllib.request.urlopen(req,timeout=22) as f:
  b=f.read(35*1024*1024+1)
  if len(b)>35*1024*1024:raise ValueError('PDF exceeds 35 MiB')
  return b,f.geturl()
def collect(row):
 row=dict(row);row['attempts']=[];row['metadata_verified']=False
 try:
  b,_=fetch('https://api.crossref.org/works/'+urllib.parse.quote(row['doi'],safe=''));m=json.loads(b)['message']
  row.update(title=m.get('title',[''])[0],journal=m.get('container-title',[''])[0],authors=[(a.get('given','')+' '+a.get('family','')).strip() for a in m.get('author',[])],publication_date=m.get('published',{}).get('date-parts'),metadata_verified=True,metadata_url='https://api.crossref.org/works/'+row['doi'])
  (ROOT/(row['id']+'_Crossref.json')).write_text(json.dumps(m,ensure_ascii=False,indent=2),encoding='utf-8')
 except Exception as e:row['metadata_error']=str(e)
 if '库内已有' in row['category']:
  row.update(status='库内已有',local_path=str(Path('D:/文献')/(row['doi'].split('/')[-1]+'.pdf')));return row
 name=row['id']+'__'+row['doi'].replace('/','__')+'.pdf';out=STAGE/name;b=None;source=None
 if out.exists():b=out.read_bytes();source='previous verified stage'
 elif row['id'] in cache and (ROOT.parent/'文献研读'/cache[row['id']]).exists():b=(ROOT.parent/'文献研读'/cache[row['id']]).read_bytes();source=row['pdf_urls'][0]
 else:
  for u in row['pdf_urls']:
   try:
    b,source=fetch(u)
    if not b.lstrip().startswith(b'%PDF-'):raise ValueError('response is not PDF')
    break
   except Exception as e:row['attempts'].append({'url':u,'error':str(e)});b=None
 if b is None:row['status']='本轮未取得PDF';return row
 try:
  d=PdfReader(io.BytesIO(b));pages=[p.extract_text() or '' for p in d.pages];body='\n'.join(pages)
  match=re.sub(r'\s+','',''.join(pages)).lower().find(row['doi'].lower())>=0
  if not match:raise ValueError('DOI not found in PDF; requires manual check')
  if not out.exists():
   with out.open('xb') as f:f.write(b)
  (TEXT/(row['id']+'.txt')).write_text('\n'.join(f'\n--- PDF页 {i+1} ---\n'+p for i,p in enumerate(pages)),encoding='utf-8')
  row.update(status='PDF已核验_待归入文献库',staged_path=str(out),filename=name,source_pdf_url=source,pages=len(pages),bytes=len(b),sha256=hashlib.sha256(b).hexdigest(),pdf_doi_verified=match,fulltext_status='已提取全文；本轮为文献搜集及数据可提取性初筛，未逐篇完成方法审计')
 except Exception as e:row.update(status='PDF需人工核验',pdf_error=str(e))
 return row
result=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
 for row in ex.map(collect,rows):
  result.append(row);print(row['id'],row['status'],row.get('title',row['doi']),flush=True)
  (ROOT/'搜集结果.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
