import json,urllib.request,urllib.parse,concurrent.futures,re
from pathlib import Path
from lxml import etree
ROOT=Path(__file__).resolve().parent
def get(url):
    with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'ResearchEvidenceReview/1.0'}),timeout=30) as r:return r.read()
def process(item):
    ident,doi=item;d=ROOT/'sources'/ident;d.mkdir(parents=True,exist_ok=True)
    rec={'id':ident,'doi':doi,'accesses':[]}
    for name,url in [('crossref.json','https://api.crossref.org/works/'+urllib.parse.quote(doi,safe='')),('epmc_search.json','https://www.ebi.ac.uk/europepmc/webservices/rest/search?query='+urllib.parse.quote('DOI:'+doi)+'&format=json')]:
        try:
            data=get(url);(d/name).write_bytes(data);rec['accesses'].append({'url':url,'saved':name,'status':'ok'})
        except Exception as e:rec['accesses'].append({'url':url,'status':'failed','error':str(e)})
    p=d/'epmc_search.json'
    if p.exists():
        records=json.loads(p.read_bytes()).get('resultList',{}).get('result',[])
        if records:
            rec['epmc_record']=records[0];pmcid=records[0].get('pmcid')
            if pmcid and records[0].get('isOpenAccess')=='Y':
                url=f'https://www.ebi.ac.uk/europepmc/webservices/rest/{pmcid}/fullTextXML'
                try:
                    data=get(url);tree=etree.fromstring(data)
                    assert tree.find('body') is not None
                    (d/'fulltext.xml').write_bytes(data)
                    nodes=[]
                    for i,node in enumerate(tree.xpath('//article-title|//abstract//p|//body//title|//body//p|//table-wrap|//fig|//supplementary-material')):
                        txt=' '.join(' '.join(node.itertext()).split()); nodes.append({'node':i,'tag':node.tag,'id':node.get('id'),'text':txt})
                    (d/'fulltext_nodes.json').write_text(json.dumps(nodes,ensure_ascii=False,indent=2),encoding='utf-8')
                    (d/'fulltext.txt').write_text('\n'.join(f"[{n['node']} {n['tag']} {n['id']}] {n['text']}" for n in nodes),encoding='utf-8')
                    rec['accesses'].append({'url':url,'status':'full_xml_saved','bytes':len(data)})
                    rec['supplement_links']=[{'tag':x.tag,'href':x.get('{http://www.w3.org/1999/xlink}href'),'text':' '.join(x.itertext())} for x in tree.xpath('//*[local-name()="supplementary-material"]//*[@*[local-name()="href"]]')]
                except Exception as e:rec['accesses'].append({'url':url,'status':'failed','error':str(e)})
    (d/'open_record_access.json').write_text(json.dumps(rec,ensure_ascii=False,indent=2),encoding='utf-8')
    print(ident,doi,rec.get('epmc_record',{}).get('pmcid'),any(x['status']=='full_xml_saved' for x in rec['accesses']),flush=True)
if __name__=='__main__':
    import sys
    items=json.loads((ROOT/sys.argv[1]).read_text(encoding='utf-8'))
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as p:list(p.map(process,items))
