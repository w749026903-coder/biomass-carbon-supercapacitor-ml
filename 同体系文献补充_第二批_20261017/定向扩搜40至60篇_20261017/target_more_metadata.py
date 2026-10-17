import json,urllib.request,urllib.parse,concurrent.futures,hashlib,io,re,time
from pathlib import Path
from pypdf import PdfReader
ROOT=Path(__file__).resolve().parent
ids='''10.1016/j.indcrop.2025.120584
10.1021/acsaem.4c01748
10.1021/acssusresmgt.4c00329
10.1021/acssusresmgt.3c00028
10.1016/j.rineng.2026.112940
10.1021/acsomega.4c06494
10.1007/s10904-026-04338-1
10.1002/eem2.70174
10.1002/slct.202506431
10.1021/acsomega.3c00816
10.3390/polym15234478
10.3390/ma17133091'''.split()
bydoi={x['doi']:x for name in ['开放与付费候选发现.json','补充原料候选发现.json'] for x in json.loads((ROOT/name).read_text(encoding='utf-8'))}
existing={json.loads(p.read_text(encoding='utf-8'))['doi']:p.parent for p in (ROOT/'sources').glob('*/acquisition.json')}
def fetch(u):
    req=urllib.request.Request(u,headers={'User-Agent':'LiteratureEvidenceAudit/1.0'})
    with urllib.request.urlopen(req,timeout=30) as r:return r.read(25000001),r.geturl(),r.headers.get('Content-Type')
def run(z):
    i,doi=z;d=existing.get(doi,ROOT/'sources'/('P'+str(i+51).zfill(3)));d.mkdir(parents=True,exist_ok=True)
    rec={'doi':doi,'folder':str(d),'discovery_metadata':bydoi.get(doi),'attempts':[]}
    try:
        u='https://api.crossref.org/works/'+urllib.parse.quote(doi,safe='');b,_,_=fetch(u);a=json.loads(b)['message'];assert a['DOI'].lower()==doi
        (d/'crossref.json').write_bytes(b);rec['crossref_title']=a.get('title');rec['crossref_date']={k:a[k] for k in ('published','published-online','published-print','created') if k in a};rec['crossref_abstract']=re.sub('<[^>]+>',' ',a.get('abstract',''));rec['crossref_url']=a.get('URL');rec['authors']=a.get('author');rec['type']=a.get('type')
        rec['attempts'].append({'url':u,'status':'identity_metadata_obtained'})
    except Exception as e:rec['attempts'].append({'type':'crossref','error':str(e)})
    if not (d/'main.xml').exists():
        urls=[]
        for loc in (bydoi.get(doi,{}).get('locations') or []):
            u=loc.get('pdf_url')
            if u and u not in urls:urls.append(u)
        if 's42773' in doi:urls.append('https://link.springer.com/content/pdf/'+doi+'.pdf')
        for u in urls[:2]:
            try:
                b,fin,ct=fetch(u);assert b.startswith(b'%PDF'),f'Not PDF; content-type {ct}'
                pr=PdfReader(io.BytesIO(b));pages=[{'page':j+1,'text':p.extract_text() or ''} for j,p in enumerate(pr.pages)]
                (d/'main.pdf').write_bytes(b);(d/'pages.json').write_text(json.dumps(pages,ensure_ascii=False,indent=2),encoding='utf-8')
                rec['attempts'].append({'url':u,'final_url':fin,'status':'full_pdf_obtained','bytes':len(b),'pages':len(pages),'sha256':hashlib.sha256(b).hexdigest()});break
            except Exception as e:rec['attempts'].append({'url':u,'status':'failed_no_bypass','error':str(e)})
    (d/'target_metadata.json').write_text(json.dumps(rec,ensure_ascii=False,indent=2),encoding='utf-8');print(d.name,doi,'CR',bool(rec.get('crossref_title')),'MAIN',any((d/f).exists() for f in ['main.xml','main.pdf']),flush=True);return rec
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as p:outs=list(p.map(run,enumerate(ids)))
(ROOT/'第二轮定向身份与获取记录.json').write_text(json.dumps(outs,ensure_ascii=False,indent=2),encoding='utf-8')
