import json,re,urllib.request,concurrent.futures,hashlib
from pathlib import Path
from lxml import etree
ROOT=Path(__file__).resolve().parent
a=json.loads((ROOT/'新DOI发现与摘要.json').read_text(encoding='utf-8'))
ids=['10.3390/molecules31132329','10.1039/d5ra00450k','10.3390/nano15050387','10.1021/acsomega.3c04692','10.1021/acsenvironau.3c00048','10.3390/nano14010071','10.3390/molecules28186543','10.3390/nano16150957','10.55730/1300-0527.3579','10.1021/acsomega.5c10175','10.1039/d5ra01262g','10.1002/cssc.202500396','10.1021/acssuschemeng.6c00388','10.1021/acsomega.5c06396','10.1039/d5ra02129d','10.1039/d6ra04144b','10.3390/molecules30163430','10.1002/open.202500271']
items=[dict(x,working_id='OA'+str(ids.index(x['doi'])+1).zfill(3)) for x in a if x['doi'] in ids]
(ROOT/'OA初筛待全文核查.json').write_text(json.dumps(items,ensure_ascii=False,indent=2),encoding='utf-8')
def run(x):
    d=ROOT/'sources'/x['working_id'];d.mkdir(parents=True,exist_ok=True);u=f"https://www.ebi.ac.uk/europepmc/webservices/rest/{x['pmcid']}/fullTextXML";out={'id':x['working_id'],'doi':x['doi'],'url':u}
    try:
        with urllib.request.urlopen(u,timeout=35) as r:b=r.read()
        t=etree.fromstring(b);assert t.find('body') is not None
        (d/'main.xml').write_bytes(b);nodes=[]
        for i,n in enumerate(t.xpath('//article-title|//abstract//p|//body//title|//body//p|//table-wrap|//fig|//supplementary-material')):nodes.append({'node':i,'tag':n.tag,'id':n.get('id'),'text':' '.join(' '.join(n.itertext()).split())})
        (d/'nodes.json').write_text(json.dumps(nodes,ensure_ascii=False,indent=2),encoding='utf-8');out.update(status='complete_xml_obtained',sha256=hashlib.sha256(b).hexdigest(),nodes=len(nodes))
    except Exception as e:out.update(status='failed_no_bypass',error=str(e))
    (d/'acquisition.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8');print(x['working_id'],x['doi'],out['status'],flush=True)
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as p:list(p.map(run,items))
