from pathlib import Path
import json,urllib.request,urllib.parse,re,concurrent.futures
OUT=Path(__file__).resolve().parent
query='OPEN_ACCESS:Y AND (TITLE_ABS:supercapacitor) AND (TITLE_ABS:biomass OR TITLE_ABS:cellulose OR TITLE_ABS:lignin OR TITLE_ABS:wood OR TITLE_ABS:shell) AND FIRST_PDATE:[2015-01-01 TO 2024-12-31] NOT PUB_TYPE:review'
url='https://www.ebi.ac.uk/europepmc/webservices/rest/search?'+urllib.parse.urlencode({'query':query,'format':'json','pageSize':100,'resultType':'core'})
with urllib.request.urlopen(url,timeout=40) as f:o=json.load(f)
(OUT/'discovery_older_epmc.json').write_text(json.dumps({'query':query,'url':url,'data':o},ensure_ascii=False,indent=2),encoding='utf-8')
existing=json.loads((OUT/'new_open_candidates.json').read_text(encoding='utf-8'));seen={x['pmcid'] for x in existing}
exclude=re.compile(r'review|overview|progress|nickel|cobalt|ferrite|MnO|TiO|MXene|polyaniline|polypyrrole|battery|deionization|electrocatal|hydrogen|Coal',re.I)
new=[]
for x in o.get('resultList',{}).get('result',[]):
 if not x.get('pmcid') or x['pmcid'] in seen or exclude.search(x['title']):continue
 if 'carbon' not in x['title'].lower() and 'biochar' not in x['title'].lower():continue
 new.append({k:x.get(k) for k in ['pmcid','doi','title','pubYear','isOpenAccess']});seen.add(x['pmcid'])
(OUT/'older_candidates.json').write_text(json.dumps(new,ensure_ascii=False,indent=2),encoding='utf-8')
print('QUERY_HITS',o.get('hitCount'),'FILTERED',len(new))
for x in new:print(x['pmcid'],x['doi'],x['title'][:105])
