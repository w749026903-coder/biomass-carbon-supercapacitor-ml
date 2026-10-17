import json,zipfile,io,urllib.request
from pathlib import Path
from pypdf import PdfReader
from lxml import etree
ROOT=Path(__file__).resolve().parent
records=[]
for ident,figs in [('L14',['g005']),('L18',['g007']),('L21',['g006']),('L13',['g009']),('L04',['f8'])]:
    d=ROOT/'sources'/ident
    info=json.loads((d/'open_record_access.json').read_text(encoding='utf-8'));pc=info['epmc_record']['pmcid']
    url=f'https://www.ebi.ac.uk/europepmc/webservices/rest/{pc}/supplementaryFiles';rec={'id':ident,'url':url,'saved':[]}
    try:
        with urllib.request.urlopen(url,timeout=35) as r:data=r.read(45_000_001)
        assert len(data)<=45_000_000
        z=zipfile.ZipFile(io.BytesIO(data))
        for m in z.infolist():
            if m.file_size>20_000_000:continue
            name=Path(m.filename).name
            if name.endswith('.zip'):
                sub=zipfile.ZipFile(io.BytesIO(z.read(m)))
                for sm in sub.infolist():
                    if sm.file_size<20_000_000 and sm.filename.lower().endswith(('.pdf','.docx')):
                        p=d/Path(sm.filename).name
                        if not p.exists():p.write_bytes(sub.read(sm))
                        rec['saved'].append(str(p))
            elif any(f in name for f in figs) and name.lower().endswith(('.jpg','.webp')):
                p=d/name
                if not p.exists():p.write_bytes(z.read(m))
                rec['saved'].append(str(p))
        rec['status']='saved'
    except Exception as e:rec['status']='failed';rec['error']=str(e)
    records.append(rec);print(ident,rec['status'],rec.get('saved'),rec.get('error'),flush=True)
for p in (ROOT/'sources').glob('*/*'):
    if p.suffix=='.pdf':
        rd=PdfReader(p);pgs=[{'page':i+1,'text':pg.extract_text()} for i,pg in enumerate(rd.pages)];p.with_suffix('.pages.json').write_text(json.dumps(pgs,ensure_ascii=False,indent=2),encoding='utf-8')
    elif p.suffix=='.docx':
        z=zipfile.ZipFile(p);tx=' '.join(etree.fromstring(z.read('word/document.xml')).itertext());p.with_suffix('.docx.txt').write_text(tx,encoding='utf-8')
(ROOT/'嵌套SI与图像获取日志.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
