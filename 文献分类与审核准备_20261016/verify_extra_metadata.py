from pathlib import Path
import json,re,urllib.request,urllib.parse,concurrent.futures,sys
sys.stdout.reconfigure(encoding='utf-8')
OUT=Path(__file__).resolve().parent;ROOT=OUT.parent;META=OUT/'书目核对';META.mkdir(exist_ok=True)
# Inventory identity fields remain useful while page-text exports are regenerated.
inventory=json.loads((OUT/'本地与压缩包文件盘点.json').read_text(encoding='utf-8'))
pool={x['DOI'].lower():x for x in json.loads((ROOT/'文献更新_2023至今/Crossref_去重总池.json').read_text(encoding='utf-8'))}
for path in (ROOT/'文献搜集_生物质碳_第一批').glob('*_Crossref.json'):
    data=json.loads(path.read_text(encoding='utf-8-sig'))
    if data.get('DOI'):pool[data['DOI'].lower()]=data
def doi_front(rec):
    hits=re.findall(r'10\.\d{4,9}/[^\s<>"\)]+',rec.get('pdf_firstpage_text',''),re.I)
    return hits[0].rstrip('.,;:').lower() if hits else None
dois=sorted({doi_front(x) for x in inventory['records'] if not x.get('paper_id') and doi_front(x)})
def fetch(doi):
    p=META/(doi.replace('/','__')+'.json')
    if p.exists():return doi,json.loads(p.read_text(encoding='utf-8'))
    if doi in pool:return doi,{'metadata_source':'existing_Crossref_snapshot','data':pool[doi]}
    url='https://api.crossref.org/works/'+urllib.parse.quote(doi,safe='')
    try:
        request=urllib.request.Request(url,headers={'User-Agent':'BiomassCarbonLiteratureAudit/1.0'})
        with urllib.request.urlopen(request,timeout=22) as response:result={'metadata_source':url,'data':json.load(response)['message']}
    except Exception as e:result={'metadata_source':url,'error':str(e)}
    p.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');return doi,result
metadata={}
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
    for doi,data in ex.map(fetch,dois):metadata[doi]=data
with (OUT/'额外资料_书目核对结果.json').open('x',encoding='utf-8') as f:json.dump(metadata,f,ensure_ascii=False,indent=2)
print('DOIs',len(metadata),'metadata obtained',sum(bool(x.get('data')) for x in metadata.values()),flush=True)
