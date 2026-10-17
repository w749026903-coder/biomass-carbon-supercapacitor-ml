import json,urllib.request,urllib.parse,concurrent.futures,hashlib,io,re,time
from pathlib import Path
from pypdf import PdfReader
ROOT=Path(__file__).resolve().parent
ids='''10.1021/acs.energyfuels.2c02916
10.1155/2024/4961636
10.5796/electrochemistry.25-71119
10.1002/ente.202201281
10.1002/ente.202500429
10.1016/j.crcon.2024.100267
10.1021/acsaem.4c01027
10.3390/batteries11010007
10.1016/j.greenca.2025.12.003
10.1016/j.crcon.2025.100399
10.1088/1402-4896/ae73bc
10.1002/cnma.202400112
10.1016/j.ijoes.2023.01.011
10.1016/j.est.2026.121336
10.1002/adsu.202300189
10.1007/s42773-023-00293-z
10.1016/j.rsurfi.2024.100353
10.1016/j.indcrop.2025.122014
10.1021/acsaem.5c00130
10.1016/j.est.2023.110167
10.1002/est2.616
10.1002/slct.74152
10.1002/ente.202500410
10.1021/acsaem.5c00606
10.1016/j.mset.2025.03.001
10.1016/j.diamond.2023.110531
10.1021/acsaem.3c02391
10.1002/est2.70057
10.1002/est2.70547
10.1016/j.matlet.2023.135201
10.1016/j.colsurfa.2024.133292
10.1016/j.biteb.2024.101765
10.1002/cssc.202400932
10.1002/cssc.202400780
10.3390/inorganics13070224
10.1021/acsomega.6c03559
10.1016/j.est.2026.125122
10.3390/catal16040368'''.split()
bydoi={x['doi']:x for x in json.loads((ROOT/'开放与付费候选发现.json').read_text(encoding='utf-8'))}
existing={json.loads(p.read_text(encoding='utf-8'))['doi']:p.parent for p in (ROOT/'sources').glob('*/acquisition.json')}
def fetch(u):
    req=urllib.request.Request(u,headers={'User-Agent':'LiteratureEvidenceAudit/1.0'})
    with urllib.request.urlopen(req,timeout=30) as r:return r.read(25000001),r.geturl(),r.headers.get('Content-Type')
def run(z):
    i,doi=z;d=existing.get(doi,ROOT/'sources'/('P'+str(i+1).zfill(3)));d.mkdir(parents=True,exist_ok=True)
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
(ROOT/'定向候选身份与获取记录.json').write_text(json.dumps(outs,ensure_ascii=False,indent=2),encoding='utf-8')
