import json,urllib.request,urllib.parse,concurrent.futures,hashlib,io
from pathlib import Path
from pypdf import PdfReader
ROOT=Path(__file__).resolve().parent
def get(url):
    with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'AcademicEvidenceReview/1.0'}),timeout=35) as r:
        b=r.read(35_000_001)
        if len(b)>35_000_000:raise ValueError('size cap')
        return b,r.url,r.headers.get('Content-Type','')
def document(item):
    ident,url,name,doi=item;d=ROOT/'sources'/ident;d.mkdir(parents=True,exist_ok=True);a={'id':ident,'url':url,'filename':name,'doi':doi}
    try:
        b,fu,typ=get(url);a.update(final_url=fu,content_type=typ,bytes=len(b))
        if not b.startswith(b'%PDF'):raise ValueError('response is not a PDF; no mislabeled file saved')
        rr=PdfReader(io.BytesIO(b));tx=[{'page':i+1,'text':p.extract_text()} for i,p in enumerate(rr.pages)]
        a.update(pages=len(tx),doi_in_text=doi.lower() in ''.join(p['text'] for p in tx).lower(),first_page_text=tx[0]['text'][:900],sha256=hashlib.sha256(b).hexdigest())
        p=d/name
        if not p.exists():p.write_bytes(b)
        (d/(name+'.pages.json')).write_text(json.dumps(tx,ensure_ascii=False,indent=2),encoding='utf-8');a.update(status='downloaded_pending_identity_review',path=str(p))
    except Exception as e:a.update(status='failed_no_bypass',error=str(e))
    return a
def oa(item):
    ident,doi=item;d=ROOT/'sources'/ident;d.mkdir(parents=True,exist_ok=True)
    url='https://api.openalex.org/works/https://doi.org/'+doi;a={'id':ident,'doi':doi,'url':url}
    try:
        b,fu,typ=get(url);x=json.loads(b);(d/'openalex.json').write_bytes(b)
        a.update(status='metadata_obtained',title=x.get('title'),oa=x.get('open_access'),locations=[{'is_oa':p.get('is_oa'),'landing_page_url':p.get('landing_page_url'),'pdf_url':p.get('pdf_url'),'version':p.get('version'),'source':(p.get('source') or {}).get('display_name')} for p in x.get('locations',[])])
    except Exception as e:a.update(status='failed_no_bypass',error=str(e))
    return a
if __name__=='__main__':
    docs=[('N008','https://files01.core.ac.uk/download/pdf/645984773.pdf','main_CORE_OA.pdf','10.1016/j.cej.2025.161386'),
      ('B2_003','https://pubs.rsc.org/en/content/articlepdf/2024/ya/d4ya00076e','main_official.pdf','10.1039/d4ya00076e'),
      ('B2_001','https://www.rsc.org/suppdata/d3/nj/d3nj04881k/d3nj04881k1.pdf','SI_official.pdf','10.1039/d3nj04881k'),
      ('B2_002','https://www.rsc.org/suppdata/d4/ta/d4ta02115k/d4ta02115k1.pdf','SI_official.pdf','10.1039/d4ta02115k'),
      ('B2_003','https://www.rsc.org/suppdata/d4/ya/d4ya00076e/d4ya00076e1.pdf','SI_official.pdf','10.1039/d4ya00076e')]
    ids=[('B2_001','10.1039/d3nj04881k'),('B2_002','10.1039/d4ta02115k'),('B2_003','10.1039/d4ya00076e'),('B2_019','10.1016/j.biombioe.2023.106747'),('N006','10.1016/j.biombioe.2025.108104'),('N007','10.1016/j.electacta.2025.145880'),('N008','10.1016/j.cej.2025.161386'),('SRC123_prior2016','10.1016/j.colsurfa.2016.10.009')]
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as p:
        results=list(p.map(document,docs))
    (ROOT/'direct_document_attempts.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    for a in results:print(a['id'],a['filename'],a['status'],a.get('bytes'),a.get('error'),flush=True)
    # OA metadata checks identify lawful author/repository copies, not alternate routes through restrictions.
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as p:results=list(p.map(oa,ids))
    (ROOT/'openalex_locations.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    for a in results:print(a['id'],a['status'],a.get('locations'),a.get('error'),flush=True)
