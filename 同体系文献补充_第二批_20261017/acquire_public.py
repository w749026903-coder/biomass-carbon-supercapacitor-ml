import json,re,hashlib,concurrent.futures,urllib.request,urllib.parse
from pathlib import Path
from lxml import html
ROOT=Path(__file__).resolve().parent
def get(url):
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (academic literature evidence review)'})
    with urllib.request.urlopen(req,timeout=35) as r:return r.read(),r.url,r.headers.get('Content-Type','')
def one(item):
    ident,url=item;dest=ROOT/'sources'/ident;dest.mkdir(parents=True,exist_ok=True)
    result={'id':ident,'url':url,'requests':[]}
    try:
        b,final,ct=get(url);(dest/'publisher.html').write_bytes(b)
        soup=html.fromstring(b)
        for s in soup.xpath('//script|//style'):s.drop_tree()
        text=' '.join(soup.text_content().split());(dest/'publisher.txt').write_text(text,encoding='utf-8')
        meta={}
        for m in soup.xpath('//meta'):
            key=m.get('name') or m.get('property')
            if key and m.get('content'):meta.setdefault(key,[]).append(m['content'])
        result.update(final_url=final,content_type=ct,bytes=len(b),metadata=meta)
        result['requests'].append({'url':url,'status':'obtained','bytes':len(b)})
        links=[]
        for a in soup.xpath('//a[@href]'):
            href=urllib.parse.urljoin(final,a.get('href'));label=' '.join(a.text_content().split())
            if ('suppdata' in href or 'supplement' in href.lower() or 'articlepdf' in href.lower()) and href not in [x['url'] for x in links]:links.append({'url':href,'label':label})
        result['document_links']=links
        doi=(meta.get('citation_doi') or [None])[0]
        if doi:
            try:
                cb,_,_=get('https://api.crossref.org/works/'+urllib.parse.quote(doi,safe=''))
                (dest/'crossref.json').write_bytes(cb)
            except Exception as e:result['crossref_error']=str(e)
        # All linked supplements and openly served PDF versions; no guesses at hidden endpoints.
        for n,link in enumerate(links):
            if not ('.pdf' in link['url'].lower() or 'articlepdf' in link['url'].lower()):continue
            try:
                data,fu,typ=get(link['url'])
                if data.startswith(b'%PDF'):
                    role='SI' if 'suppdata' in link['url'] or 'supplement' in link['url'].lower() else 'main'
                    name=f'{role}_{n+1:02}.pdf';(dest/name).write_bytes(data)
                    result['requests'].append({'url':link['url'],'final_url':fu,'status':'valid_pdf_header','path':str(dest/name),'bytes':len(data)})
                else:result['requests'].append({'url':link['url'],'status':'not_pdf','content_type':typ,'bytes':len(data)})
            except Exception as e:result['requests'].append({'url':link['url'],'status':'failed_no_bypass','error':str(e)})
    except Exception as e:result['error']=str(e)
    (dest/'acquisition.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return result
if __name__=='__main__':
    import sys
    items=json.loads((ROOT/sys.argv[1]).read_text(encoding='utf-8'))
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for r in pool.map(one,items):print(r['id'],r.get('bytes'),r.get('error'),len(r.get('requests',[])),flush=True)
