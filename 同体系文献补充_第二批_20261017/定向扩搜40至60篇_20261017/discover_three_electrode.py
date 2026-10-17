import json,urllib.request,urllib.parse,re
from pathlib import Path
ROOT=Path(__file__).resolve().parent
q='(TITLE_ABS:"three-electrode" OR TITLE_ABS:"three electrode") AND TITLE_ABS:carbon AND TITLE_ABS:supercapacitor AND FIRST_PDATE:[2023-01-01 TO 2026-10-17] NOT PUB_TYPE:review'
u='https://www.ebi.ac.uk/europepmc/webservices/rest/search?query='+urllib.parse.quote(q)+'&format=json&resultType=core&pageSize=1000'
with urllib.request.urlopen(u,timeout=35) as r:b=r.read()
(ROOT/'三电极优先检索原始响应.json').write_bytes(b)
a=json.loads(b);known={x['doi_normalized'] for x in json.loads((ROOT.parent/'DOI去重基线.json').read_text(encoding='utf-8'))['records'] if x['doi_normalized']}
for p in (ROOT.parent/'sources').glob('*/open_record_access.json'):known.add(json.loads(p.read_text(encoding='utf-8'))['doi'].lower())
already={json.loads(p.read_text(encoding='utf-8'))['doi'] for p in (ROOT/'sources').glob('*/acquisition.json')}
out=[]
for x in a['resultList']['result']:
    doi=x.get('doi','').lower();t=re.sub('<[^>]+>',' ',x.get('abstractText',''))
    if not doi or doi in known or doi in already:continue
    title=x.get('title','')
    if not re.search(r'cycl|retention',t,re.I):continue
    if re.search(r'NiCo|oxide|sulfide|MOF|graphene|MXene|NiS|Co3|zinc.ion|nickel|cobalt|manganese|MoS|Ti3|Fe3|CuO|vanadium|tin.sulf|polyethylene|terephthalate|coal|plastic',title,re.I):continue
    row={'doi':doi,'title':title,'abstract':t,'pmcid':x.get('pmcid'),'metadata':x};out.append(row)
    print(doi,title,'\n',t,flush=True)
(ROOT/'三电极优先新线索.json').write_text(json.dumps({'query':q,'url':u,'hits':a['hitCount'],'new_candidates':out},ensure_ascii=False,indent=2),encoding='utf-8')
