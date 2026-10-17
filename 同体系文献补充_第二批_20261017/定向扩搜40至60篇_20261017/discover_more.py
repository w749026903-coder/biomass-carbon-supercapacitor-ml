import json,re,urllib.request,urllib.parse
from pathlib import Path
ROOT=Path(__file__).resolve().parent
PARENT=ROOT.parent
known={x['doi_normalized'] for x in json.loads((PARENT/'DOI去重基线.json').read_text(encoding='utf-8'))['records'] if x['doi_normalized']}
for p in (PARENT/'sources').glob('*/open_record_access.json'):known.add(json.loads(p.read_text(encoding='utf-8'))['doi'].lower())
def abstract(inv):
    if not inv:return ''
    a=[(p,w) for w,ps in inv.items() for p in ps];return ' '.join(w for p,w in sorted(a))
allrows={};log=[]
for i,q in enumerate(['symmetric supercapacitor carbon leaves','symmetric supercapacitor carbon fruit','symmetric supercapacitor carbon food','symmetric supercapacitor carbon sawdust'],1):
    u='https://api.openalex.org/works?search='+urllib.parse.quote(q)+'&filter=from_publication_date:2023-01-01,to_publication_date:2026-10-17,type:article&per-page=200'
    try:
        with urllib.request.urlopen(u,timeout=40) as r:b=r.read()
        (ROOT/f'openalex_moresearch{i}.json').write_bytes(b);a=json.loads(b);log.append({'q':q,'url':u,'count':a['meta']['count'],'returned':len(a['results'])})
        for x in a['results']:
            doi=(x.get('doi') or '').lower().replace('https://doi.org/','')
            if not doi or doi in known:continue
            t=abstract(x.get('abstract_inverted_index'));title=x['title']
            if re.search(r'\breview\b|perspective|progress|overview',title,re.I):continue
            score=5*bool(re.search('symmetr|two.electrode',t,re.I))+4*bool(re.search(r'\d[\d ,]*(?:cycles|cycle)',t,re.I))+3*bool(re.search('retention|capacitance loss',t,re.I))-6*bool(re.search(r'oxide|sulfide|MXene|metal.organic|MOF|asymmetric|polyaniline|hydrogel|zinc.ion|coal|coke',title,re.I))
            allrows[doi]={'doi':doi,'title':title,'score':score,'date':x['publication_date'],'abstract':t,'primary_location':x.get('primary_location'),'locations':x.get('locations'),'open_access':x.get('open_access'),'openalex_id':x['id']}
        print('SEARCH',i,len(a['results']),flush=True)
    except Exception as e:log.append({'q':q,'url':u,'error':str(e)});print('ERROR',str(e),flush=True)
a=sorted(allrows.values(),key=lambda x:x['score'],reverse=True)
(ROOT/'补充原料候选发现.json').write_text(json.dumps(a,ensure_ascii=False,indent=2),encoding='utf-8')
(ROOT/'OpenAlex补充原料检索日志.json').write_text(json.dumps(log,ensure_ascii=False,indent=2),encoding='utf-8')
for i,x in enumerate(a[:120],1):print(i,x['score'],x['doi'],x['title'],flush=True)
