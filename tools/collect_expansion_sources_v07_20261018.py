"""Collect primary OA XML into a new batch and deduplicate against v0.6."""
from pathlib import Path
import hashlib,json,sqlite3,urllib.request,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
BATCH=ROOT/'数据补充_v07_20261018'
PARENT=ROOT/'循环稳定性数据库_v0.6_报告工况训练就绪_20261018'

def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def text(e):return ' '.join(' '.join(e.itertext()).split()) if e is not None else ''

def collect(pmcids):
    BATCH.mkdir(exist_ok=True);(BATCH/'sources').mkdir(exist_ok=True)
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({'http':'http://127.0.0.1:7890','https':'http://127.0.0.1:7890'}))
    c=sqlite3.connect((PARENT/'cycling_v0_6.sqlite').as_uri()+'?mode=ro',uri=True)
    results=[]
    for pmc in pmcids:
        folder=BATCH/'sources'/pmc;folder.mkdir(exist_ok=True);file=folder/'main.xml'
        url='https://www.ebi.ac.uk/europepmc/webservices/rest/'+pmc+'/fullTextXML'
        try:
            if not file.exists():
                req=urllib.request.Request(url,headers={'User-Agent':'LiteratureDataResearch/1.0'})
                body=opener.open(req,timeout=35).read();article=ET.fromstring(body)
                if article.tag!='article':raise ValueError('Not full article XML')
                with file.open('xb') as f:f.write(body)
            article=ET.parse(file).getroot();doi=next((text(n).lower() for n in article.findall('.//article-meta/article-id') if n.get('pub-id-type')=='doi'),None)
            known=c.execute('select identity_key from literature_registry where doi=?',(doi,)).fetchone()
            item={'pmcid':pmc,'doi':doi,'title':text(article.find('.//article-title')),'source_url':url,'sha256':sha(file),'existing_identity':known[0] if known else None,'new_to_registry':not bool(known),'automatic_training_admission':False}
            result=[]
            for section in article.findall('./body//sec'):
                for node in list(section):
                    if node.tag in ('p','table-wrap','fig'):
                        result.append({'locator':node.tag+' '+str(node.get('id',len(result)+1)),'text':text(node)})
            dump(folder/'segments.json',result)
            item['segments']=len(result);results.append(item)
        except Exception as e:results.append({'pmcid':pmc,'source_url':url,'error':str(e),'automatic_training_admission':False})
    previous=BATCH/'source_collection.json'
    current=json.loads(previous.read_text(encoding='utf-8')) if previous.exists() else []
    current={x['pmcid']:x for x in current};current.update({x['pmcid']:x for x in results});dump(previous,list(current.values()))
    return results

if __name__=='__main__':
    import sys
    print(json.dumps(collect(sys.argv[1:]),ensure_ascii=False))
