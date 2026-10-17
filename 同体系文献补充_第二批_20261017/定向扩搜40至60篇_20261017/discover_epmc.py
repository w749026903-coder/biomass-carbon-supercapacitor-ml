import json,urllib.request,urllib.parse,re,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent
PARENT=ROOT.parent
known={x['doi_normalized'] for x in json.loads((PARENT/'DOI去重基线.json').read_text(encoding='utf-8'))['records'] if x['doi_normalized']}
for p in (PARENT/'sources').glob('*/open_record_access.json'):
    known.add(json.loads(p.read_text(encoding='utf-8'))['doi'].lower())
queries=[
 'TITLE_ABS:supercapacitor AND TITLE_ABS:carbon AND (TITLE_ABS:biomass OR TITLE_ABS:derived OR TITLE_ABS:waste) AND FIRST_PDATE:[2023-01-01 TO 2026-10-17] AND OPEN_ACCESS:Y NOT PUB_TYPE:review',
 'TITLE_ABS:supercapacitor AND (TITLE_ABS:biochar OR TITLE_ABS:lignin OR TITLE_ABS:cellulose) AND FIRST_PDATE:[2023-01-01 TO 2026-10-17] AND OPEN_ACCESS:Y NOT PUB_TYPE:review'
]
allrows={};log=[]
for qi,q in enumerate(queries,1):
    cursor='*'
    for page in range(1,5):
        u='https://www.ebi.ac.uk/europepmc/webservices/rest/search?query='+urllib.parse.quote(q)+'&format=json&resultType=core&pageSize=100&cursorMark='+urllib.parse.quote(cursor)
        try:
            with urllib.request.urlopen(u,timeout=40) as r:b=r.read()
            (ROOT/f'epmc_query{qi}_page{page}.json').write_bytes(b);a=json.loads(b);rows=a['resultList']['result']
            log.append({'query':q,'page':page,'hitCount':a['hitCount'],'rows':len(rows),'url':u})
            for x in rows:
                doi=(x.get('doi') or '').lower()
                if doi and doi not in known:allrows[doi]=x
            print('PAGE',qi,page,a['hitCount'],len(rows),flush=True)
            if len(rows)<100:break
            cursor=a['nextCursorMark']
        except Exception as e:log.append({'url':u,'error':str(e)});print('ERROR',str(e),flush=True);break
ranked=[]
for doi,x in allrows.items():
    t=re.sub('<[^>]+>',' ',x.get('abstractText',''));title=x.get('title','')
    score=4*bool(re.search(r'symmetr|two.electrode',t,re.I))+3*bool(re.search(r'\d[\d ,]*(?:cycles|cycle)',t,re.I))+2*bool(re.search(r'retention|capacitance loss',t,re.I))-5*bool(re.search(r'\breview\b',title,re.I))-3*bool(re.search(r'oxide|sulfide|MXene|MOF|asymmetric|polyaniline|hybrid capacitor|hydrogel',title,re.I))
    ranked.append({'doi':doi,'title':title,'score':score,'date':x.get('firstPublicationDate'),'pmcid':x.get('pmcid'),'abstract':t})
ranked.sort(key=lambda x:(x['score'],x.get('date') or ''),reverse=True)
(ROOT/'新DOI发现与摘要.json').write_text(json.dumps(ranked,ensure_ascii=False,indent=2),encoding='utf-8')
(ROOT/'检索日志.json').write_text(json.dumps(log,ensure_ascii=False,indent=2),encoding='utf-8')
for i,x in enumerate(ranked[:100],1):print(i,x['score'],x['doi'],x['title'],flush=True)
