from pathlib import Path
import json,re,concurrent.futures,urllib.request,hashlib,xml.etree.ElementTree as ET
OUT=Path(__file__).resolve().parent;ROOT=OUT.parent
rows=json.loads((OUT/'older2_candidates.json').read_text(encoding='utf-8'))
exclude=re.compile(r'review|overview|advancements|progress|mechanism elucidation|MOF|metal.organic|NiV|trimetal|coordination polymer|selenite|nickel|cobalt|ferrite|copper oxide|MnO|TiO|MXene|polyaniline|polypyrrole|hydrogel electrolyte|ZIF',re.I)
known={x['doi'] for x in json.loads((OUT/'corpus_index.json').read_text(encoding='utf-8'))};selected=[x for x in rows if str(x.get('doi','')).lower() not in known]
forced=[]
for pmc in forced:
 if pmc not in {x['pmcid'] for x in selected}:selected.append({'pmcid':pmc,'doi':None,'title':'targeted primary fulltext from web search'})
selected=selected[:70]
def get(x):
 dest=OUT/'new_sources'/x['pmcid'];dest.mkdir(parents=True,exist_ok=True);url='https://www.ebi.ac.uk/europepmc/webservices/rest/'+x['pmcid']+'/fullTextXML';rec={**x,'url':url}
 try:
  with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'AcademicLiteratureEvidence/1.0'}),timeout=30) as resp:b=resp.read(15000001)
  if len(b)>15000000:raise ValueError('XML size cap')
  xml=ET.fromstring(b)
  if xml.tag!='article':raise ValueError('not article XML')
  doi=next((e.text for e in xml.findall('.//article-id') if e.get('pub-id-type')=='doi'),x.get('doi'))
  title=''.join(xml.find('.//article-title').itertext());parts=[];body=xml.find('.//body')
  if body is None:raise ValueError('body missing')
  for e in body.iter():
   if e.tag in ['p','caption','table']:parts.append(' '.join(''.join(e.itertext()).split()))
  text='\n'.join(f'[P{i:04d}] '+s for i,s in enumerate(parts,1))
  (dest/'main.xml').write_bytes(b);(dest/'main.txt').write_text(text,encoding='utf-8')
  rec.update(status='obtained',doi=doi,title=title,source_path=(dest/'main.xml').relative_to(ROOT).as_posix(),text_path=(dest/'main.txt').relative_to(ROOT).as_posix(),sha256=hashlib.sha256(b).hexdigest(),bytes=len(b))
  (dest/'acquisition.json').write_text(json.dumps(rec,ensure_ascii=False,indent=2),encoding='utf-8')
 except Exception as exc:rec.update(status='failed',error=type(exc).__name__+': '+str(exc))
 return rec
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
 results=[]
 for rec in pool.map(get,selected):
  results.append(rec);print(rec['pmcid'],rec['status'],rec.get('doi'),flush=True)
(OUT/'older2_acquisition.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
print('ACQUIRED',sum(x['status']=='obtained' for x in results),'ATTEMPTED',len(results))
