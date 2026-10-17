import json,urllib.request,zipfile,io,concurrent.futures
from pathlib import Path
from pypdf import PdfReader
from lxml import etree
ROOT=Path(__file__).resolve().parent
def fetch(ident):
    d=ROOT/'sources'/ident;em=json.loads((d/'open_record_access.json').read_text(encoding='utf-8'))['epmc_record'];pc=em['pmcid']
    url=f'https://www.ebi.ac.uk/europepmc/webservices/rest/{pc}/supplementaryFiles';rec={'id':ident,'url':url,'saved':[]}
    def extract(data,depth=0):
        z=zipfile.ZipFile(io.BytesIO(data))
        for m in z.infolist():
            if m.file_size>20_000_000:continue
            name=Path(m.filename).name
            if name.endswith('.zip') and depth<1:extract(z.read(m),depth+1)
            elif name.lower().endswith(('.pdf','.docx')) or ident=='L13' and 'fig9' in name.lower() and name.lower().endswith(('.jpg','.webp')):
                p=d/name
                if not p.exists():p.write_bytes(z.read(m))
                rec['saved'].append(str(p))
    try:
        with urllib.request.urlopen(url,timeout=40) as r:data=r.read(45_000_001)
        assert len(data)<=45_000_000;extract(data);rec['status']='saved'
    except Exception as e:rec.update(status='failed_no_bypass',error=str(e))
    print(ident,rec['status'],len(rec['saved']),rec.get('error'),flush=True);return rec
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as p:records=list(p.map(fetch,['L10','L11','L13','L15','L20']))
for rec in records:
    for name in rec['saved']:
        p=Path(name)
        if p.suffix=='.pdf':
            rr=PdfReader(p);a=[{'page':i+1,'text':pg.extract_text()} for i,pg in enumerate(rr.pages)];p.with_suffix('.pages.json').write_text(json.dumps(a,ensure_ascii=False,indent=2),encoding='utf-8')
        elif p.suffix=='.docx':
            z=zipfile.ZipFile(p);tx=' '.join(etree.fromstring(z.read('word/document.xml')).itertext());p.with_suffix('.docx.txt').write_text(tx,encoding='utf-8')
(ROOT/'公开SI补取日志.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
