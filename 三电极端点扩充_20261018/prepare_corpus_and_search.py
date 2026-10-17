from pathlib import Path
import json,re,hashlib,shutil,concurrent.futures,urllib.request,urllib.parse,xml.etree.ElementTree as ET
from pypdf import PdfReader
ROOT=Path(__file__).resolve().parents[1];OUT=Path(__file__).resolve().parent
(OUT/'corpus').mkdir(exist_ok=True)
def xmltext(blob):
 root=ET.fromstring(blob);body=root.find('.//body');parts=[]
 if body is None:body=root
 for e in body.iter():
  if e.tag in ['p','caption','table']:parts.append(' '.join(''.join(e.itertext()).split()))
 return '\n'.join(f'[P{i:04d}] '+s for i,s in enumerate(parts,1))
def make(tag,doi,path,title=''):
 path=Path(path);dest=OUT/'corpus'/tag;dest.mkdir(exist_ok=True)
 if path.suffix.lower()=='.pdf':
  b=path.read_bytes();pdf=PdfReader(path);text='\n'.join(f'[PDF_PAGE_{i+1}]\n'+(p.extract_text() or '') for i,p in enumerate(pdf.pages))
  cp=dest/'main.pdf'
  if not cp.exists():cp.write_bytes(b)
  source=cp.relative_to(ROOT).as_posix()
 else:b=path.read_bytes();text=xmltext(b);source=path.relative_to(ROOT).as_posix()
 (dest/'main.txt').write_text(text,encoding='utf-8')
 return {'tag':tag,'doi':doi.lower(),'title':title,'source_path':source,'source_sha256':hashlib.sha256(b).hexdigest(),'text_path':(dest/'main.txt').relative_to(ROOT).as_posix()}
records=[];seen=set()
base=json.loads((OUT/'existing_29_full.json').read_text(encoding='utf-8'))
for x in base:
 p=x['paper']
 if p['doi'] in seen:continue
 seen.add(p['doi']);records.append(make('B_'+p['paper_id'],p['doi'],p['main_path'],p['title']))
a=json.loads((ROOT/'同体系文献补充_第二批_20261017/定向扩搜40至60篇_20261017/新增50篇_逐篇数据与获取状态.json').read_text(encoding='utf-8'))['records']
for x in a:
 if x['temporary_id']>'EXT_015':continue
 if x['doi'] in seen:continue
 seen.add(x['doi']);records.append(make(x['temporary_id'],x['doi'],x['complete_main_files'][0],x['title']))
user=json.loads((ROOT/'用户补充文献核验_20261018/核验记录_26份.json').read_text(encoding='utf-8'))['records']
for x in user:
 if x['id'] not in ['U002','U006','U010','U013','U014','U016','U017','U018','U021','U024']:continue
 if x['doi'] in seen:continue
 seen.add(x['doi']);records.append(make(x['id'],x['doi'],ROOT/x['repository_pdf'],x['filename']))
(OUT/'corpus_index.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
queries=['OPEN_ACCESS:Y AND supercapacitor AND (biomass OR cellulose OR lignin OR shell) AND "three-electrode" NOT TITLE:review','OPEN_ACCESS:Y AND supercapacitor AND "cycling stability" AND (wood OR peel OR straw OR carbon) NOT TITLE:review']
def search(q):
 url='https://www.ebi.ac.uk/europepmc/webservices/rest/search?'+urllib.parse.urlencode({'query':q,'format':'json','pageSize':100,'resultType':'core'})
 with urllib.request.urlopen(url,timeout=40) as resp:o=json.load(resp)
 return {'query':q,'url':url,'data':o}
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(search,queries))
(OUT/'discovery_epmc.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
cands={}
for result in results:
 for x in result['data'].get('resultList',{}).get('result',[]):
  if not x.get('pmcid') or re.search(r'review|progress|overview|recent advances',x.get('title',''),re.I):continue
  if x.get('doi','').lower() in seen:continue
  cands[x['pmcid']]={k:x.get(k) for k in ['pmcid','doi','title','pubYear','isOpenAccess']}
(OUT/'new_open_candidates.json').write_text(json.dumps(list(cands.values()),ensure_ascii=False,indent=2),encoding='utf-8')
print('LOCAL_CORPUS',len(records),'NEW_CANDIDATES',len(cands))
for x in list(cands.values())[:45]:print(json.dumps(x,ensure_ascii=False))
