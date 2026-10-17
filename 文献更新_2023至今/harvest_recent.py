from pathlib import Path
import json,re,sys,urllib.request,urllib.parse,concurrent.futures,collections,datetime,hashlib
from pypdf import PdfReader
sys.stdout.reconfigure(encoding='utf-8')
ROOT=Path(__file__).resolve().parent.parent
OUT=Path(__file__).resolve().parent
META=OUT/'检索元数据';META.mkdir(exist_ok=True)
TODAY=datetime.date(2026,10,16)
def fetch(url):
    req=urllib.request.Request(url,headers={'User-Agent':'BiomassCarbonLiteratureAudit/1.0','Accept':'application/json'})
    with urllib.request.urlopen(req,timeout=35) as response:
        data=response.read(30*1024*1024)
    return json.loads(data)
def dates(meta):
    result={}
    for k in ['published','published-online','published-print','issued']:
        parts=meta.get(k,{}).get('date-parts',[[]])[0]
        if parts and parts[0]: result[k]=parts
    return result
def first_date(meta):
    ds=dates(meta)
    if not ds:return None
    return min(tuple(v+[1]*(3-len(v))) for v in ds.values())
queries=[
    'biomass derived carbon supercapacitor',
    'biochar porous carbon supercapacitor',
    'waste derived porous carbon supercapacitors',
    'lignin cellulose coconut carbon supercapacitor',
    'machine learning biomass carbon supercapacitors',
]
def search(pair):
    i,q=pair;p=META/f'Crossref_检索_{i}.json'
    if p.exists():return json.loads(p.read_text(encoding='utf-8'))
    url='https://api.crossref.org/works?'+urllib.parse.urlencode({'query.bibliographic':q,'filter':'from-pub-date:2023-01-01,until-pub-date:2026-10-16,type:journal-article','rows':200,'sort':'relevance'})
    try:
        data=fetch(url)
        p.write_text(json.dumps({'query':q,'url':url,'result':data},ensure_ascii=False,indent=2),encoding='utf-8')
        print('SEARCH',i,'items',len(data['message']['items']),flush=True)
        return {'result':data}
    except Exception as e:
        print('SEARCH_ERROR',i,str(e),flush=True);return {}
ledger=json.loads((ROOT/'文献下载_120篇/下载归档最终台账.json').read_text(encoding='utf-8-sig'))
oldraw=json.loads((ROOT/'文献扩充_生物质碳_120篇/检索合并原始.json').read_text(encoding='utf-8-sig'))
metadata={r['DOI'].lower():r for r in oldraw}
for p in (ROOT/'文献搜集_生物质碳_第一批').glob('*_Crossref.json'):
    data=json.loads(p.read_text(encoding='utf-8-sig'))
    if data.get('DOI'):metadata[data['DOI'].lower()]=data
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
    for result in pool.map(search,enumerate(queries,1)):
        for row in result.get('result',{}).get('message',{}).get('items',[]):metadata[row['DOI'].lower()]=row
# Refresh each downloaded candidate before proposing irreversible deletion.
def refresh(rec):
    doi=rec['doi'].lower();p=META/('DOI_'+doi.replace('/','__')+'.json')
    try:
        if p.exists():data=json.loads(p.read_text(encoding='utf-8'))
        else:
            data=fetch('https://api.crossref.org/works/'+urllib.parse.quote(doi,safe=''))['message']
            p.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
        return doi,data
    except Exception as e:
        print('DATE_REFRESH_ERROR',doi,str(e),flush=True);return doi,None
downloaded=[r for r in ledger if r.get('local_pdf') and Path(r['local_pdf']).is_file()]
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
    for doi,data in pool.map(refresh,downloaded):
        if data: metadata[doi]=data
inventory=[]
for rec in ledger:
    m=metadata.get(rec['doi'].lower(),{})
    d=first_date(m)
    inventory.append({'old_id':rec['collection_id'],'doi':rec['doi'],'title':rec['title'],
                      'dates':dates(m),'first_publication':d,'year':d[0] if d else None,
                      'in_range':bool(d and (2023,1,1)<=d<=(2026,10,16)),
                      'local_pdf':rec.get('local_pdf'),'has_pdf':bool(rec.get('local_pdf') and Path(rec['local_pdf']).is_file()),
                      'date_live_refreshed':(META/('DOI_'+rec['doi'].lower().replace('/','__')+'.json')).is_file()})
(OUT/'旧120篇_年份复核.json').write_text(json.dumps(inventory,ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'Crossref_去重总池.json').write_text(json.dumps(list(metadata.values()),ensure_ascii=False,indent=2),encoding='utf-8')
print('YEAR_COUNTS',dict(collections.Counter(x['year'] for x in inventory)))
print('IN_RANGE',sum(x['in_range'] for x in inventory),'OLD_DOWNLOADED',sum(x['has_pdf'] and x['year'] and x['year']<2023 for x in inventory))
# Inventory only the explicitly authorized literature directory and project PDFs.
known_paths={Path(x['local_pdf']).resolve():x for x in inventory if x.get('local_pdf')}
unmapped=[]
for p in Path(r'D:\文献').glob('*.pdf'):
    if p.resolve() in known_paths:continue
    try:
        doc=PdfReader(p)
        text='\n'.join(page.extract_text() or '' for page in doc.pages[:2])
        doi_matches=re.findall(r'10\.\d{4,9}/[^\s<>"\)]+',text,re.I)
        unmapped.append({'path':str(p),'doi_candidates':list(dict.fromkeys(s.rstrip('.,;') for s in doi_matches))[:5], 'first_page_snippet':text[:350]})
    except Exception as e:unmapped.append({'path':str(p),'error':str(e)})
(OUT/'其他本地PDF_识别.json').write_text(json.dumps(unmapped,ensure_ascii=False,indent=2),encoding='utf-8')
print('POOL',len(metadata),'UNMAPPED_LOCAL',len(unmapped),flush=True)
