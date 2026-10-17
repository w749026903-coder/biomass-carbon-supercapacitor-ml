import json,urllib.request,concurrent.futures,hashlib,zipfile,io
from pathlib import Path
from lxml import etree
from pypdf import PdfReader
ROOT=Path(__file__).resolve().parent
def fetch(item):
    ident,url,name=item;d=ROOT/'sources'/ident;d.mkdir(parents=True,exist_ok=True)
    rec={'id':ident,'url':url,'filename':name}
    try:
        with urllib.request.urlopen(url,timeout=40) as r:
            data=r.read(45_000_001);rec['content_type']=r.headers.get('Content-Type');rec['final_url']=r.url
        if len(data)>45_000_000:raise ValueError('download size exceeds task cap')
        rec['bytes']=len(data)
        if name.endswith('.zip'):
            z=zipfile.ZipFile(io.BytesIO(data));files=[]
            for m in z.infolist():
                # Only supplement documents, never unpack arbitrary paths or executables.
                if m.filename.lower().endswith(('.pdf','.docx','.doc')) and m.file_size<20_000_000:
                    b=z.read(m);p=d/Path(m.filename).name
                    if not p.exists():p.write_bytes(b)
                    files.append({'path':str(p),'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b)})
            rec['documents']=files;rec['archive_members']=[m.filename for m in z.infolist()]
        else:
            if name.endswith('.pdf'):
                assert data.startswith(b'%PDF');rec['pages']=len(PdfReader(io.BytesIO(data)).pages)
            elif name.endswith('.docx'):
                z=zipfile.ZipFile(io.BytesIO(data));assert 'word/document.xml' in z.namelist()
                tx=' '.join(etree.fromstring(z.read('word/document.xml')).itertext());(d/(name+'.txt')).write_text(tx,encoding='utf-8')
            (d/name).write_bytes(data);rec['sha256']=hashlib.sha256(data).hexdigest()
        rec['status']='saved'
    except Exception as e:rec['status']='failed_no_bypass';rec['error']=str(e)
    print(ident,name,rec['status'],rec.get('bytes'),rec.get('error'),flush=True)
    return rec
if __name__=='__main__':
    items=[('SUP_R111','https://ars.els-cdn.com/content/image/1-s2.0-S0961953425006646-mmc1.docx','supplement.docx'),('SUP_SRC035','https://ars.els-cdn.com/content/image/1-s2.0-S0925838825037624-mmc1.docx','supplement.docx')]
    for ident in ['L05','L06','L08','L09','L14','L16','L18','L21','L22']:
        rec=json.loads((ROOT/'sources'/ident/'open_record_access.json').read_text(encoding='utf-8'))
        pc=rec['epmc_record']['pmcid'];items.append((ident,f'https://www.ebi.ac.uk/europepmc/webservices/rest/{pc}/supplementaryFiles','supplementary.zip'))
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as p:records=list(p.map(fetch,items))
    (ROOT/'补件获取日志.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
