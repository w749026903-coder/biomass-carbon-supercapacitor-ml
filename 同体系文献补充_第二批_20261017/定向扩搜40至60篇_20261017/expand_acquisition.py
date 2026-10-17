import json,re,urllib.request,urllib.parse,concurrent.futures,hashlib,time
from pathlib import Path
from lxml import etree
ROOT=Path(__file__).resolve().parent
ids='''10.1155/2024/4961636
10.3390/nano16161035
10.3390/batteries11010007
10.3390/nano14100836
10.1021/acsomega.5c08616
10.1007/s42773-023-00293-z
10.3390/polym15030663
10.3390/catal16040368
10.3390/nano13050817
10.3390/polym15081947
10.1039/d3ra07014j
10.3390/molecules29225413
10.3390/polym15193976
10.3390/inorganics13070224
10.3390/applnano7030019
10.3390/sym15040846
10.3390/molecules28248136
10.1021/acsomega.6c03559
10.1002/cssc.202400932
10.1002/cssc.202400780
10.1002/adsu.202300189
10.1007/s44246-025-00255-z'''.split()
rows=json.loads((ROOT/'开放与付费候选发现.json').read_text(encoding='utf-8'))
bydoi={x['doi']:x for x in rows}
def fetch(u):
    req=urllib.request.Request(u,headers={'User-Agent':'LiteratureEvidenceAudit/1.0'})
    with urllib.request.urlopen(req,timeout=35) as r:return r.read(),r.geturl()
def run(z):
    i,doi=z;wid='OA'+str(i+19).zfill(3);d=ROOT/'sources'/wid;d.mkdir(parents=True,exist_ok=True)
    out={'working_id':wid,'doi':doi,'title':bydoi.get(doi,{}).get('title'),'attempts':[]}
    try:
        u='https://www.ebi.ac.uk/europepmc/webservices/rest/search?query='+urllib.parse.quote('DOI:"'+doi+'"')+'&format=json&resultType=core'
        b,_=fetch(u);(d/'epmc_metadata.json').write_bytes(b);a=json.loads(b)['resultList']['result'];x=next((x for x in a if x.get('doi','').lower()==doi),None)
        if x:out['metadata']=x;out['title']=x.get('title');out['pmcid']=x.get('pmcid')
        if not x or not x.get('pmcid'):raise ValueError('No deposited PMC full text located')
        u=f"https://www.ebi.ac.uk/europepmc/webservices/rest/{x['pmcid']}/fullTextXML";b,_=fetch(u);t=etree.fromstring(b);assert t.find('body') is not None
        (d/'main.xml').write_bytes(b);nodes=[]
        for j,n in enumerate(t.xpath('//article-title|//abstract//p|//body//title|//body//p|//table-wrap|//fig|//supplementary-material')):nodes.append({'node':j,'tag':n.tag,'id':n.get('id'),'text':' '.join(' '.join(n.itertext()).split())})
        (d/'nodes.json').write_text(json.dumps(nodes,ensure_ascii=False,indent=2),encoding='utf-8');out.update(status='complete_xml_obtained',url=u,sha256=hashlib.sha256(b).hexdigest(),nodes=len(nodes))
    except Exception as e:out.update(status='no_fulltext_obtained',error=str(e))
    (d/'acquisition.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8');print(wid,doi,out['status'],flush=True)
    return out
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as p:outs=list(p.map(run,enumerate(ids)))
(ROOT/'追加开放全文获取记录.json').write_text(json.dumps(outs,ensure_ascii=False,indent=2),encoding='utf-8')
