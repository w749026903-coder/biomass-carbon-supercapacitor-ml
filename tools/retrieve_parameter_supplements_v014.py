"""Bounded retrieval of two declared publisher supplements; no raw-library changes."""
from pathlib import Path
import datetime,hashlib,io,json,urllib.request,zipfile
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'主集参数精提取_20261022'
def main():
    receipt=OUT/'supplement_access.json'
    if receipt.exists():raise FileExistsError('Do not repeat completed retrieval.')
    destination=OUT/'new_supplements';destination.mkdir(exist_ok=True)
    jobs=[('10.3390/nano13101654','AO_PC','https://mdpi-res.com/d_attachment/nanomaterials/nanomaterials-13-01654/article_deploy/nanomaterials-13-01654-s001.zip'),
          ('10.1039/d4cp01914h','AUACW','https://www.rsc.org/suppdata/d4/cp/d4cp01914h/d4cp01914h1.pdf')]
    op=urllib.request.build_opener(urllib.request.ProxyHandler({'http':'http://127.0.0.1:7890','https':'http://127.0.0.1:7890'}));log=[]
    for doi,name,url in jobs:
        r=dict(doi=doi,url=url,checked_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),identity_verified=False)
        try:
            with op.open(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=22) as z:
                data=z.read(12000001);r.update(status=z.status,final_url=z.url,content_type=z.headers.get('Content-Type'),bytes=len(data))
            if len(data)>12000000:raise ValueError('Attachment exceeds bounded retrieval size.')
            r['transport_sha256']=hashlib.sha256(data).hexdigest();r['files']=[]
            if data.startswith(b'%PDF'):
                files=[(name+'_SI.pdf',data,None)]
            elif data.startswith(b'PK'):
                with zipfile.ZipFile(io.BytesIO(data)) as archive:
                    files=[];r['archive_members']=[i.filename for i in archive.infolist()]
                    for i in archive.infolist():
                        if Path(i.filename).suffix.lower() not in ['.pdf','.docx'] or i.file_size>10000000:continue
                        files.append((name+'_'+Path(i.filename).name,archive.read(i),i.filename))
                r['archive_storage']='original document member bytes retained; transport archive hash/list saved without duplicate ZIP'
            else:raise ValueError('Response is not a PDF or ZIP document.')
            for fn,raw,member in files:
                p=destination/fn
                if p.exists():raise FileExistsError(p)
                p.write_bytes(raw);r['files'].append(dict(path=p.relative_to(ROOT).as_posix(),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),archive_member=member))
        except Exception as e:r['error']=str(e)
        log.append(r);print(json.dumps(r,ensure_ascii=False),flush=True)
    receipt.write_text(json.dumps(log,ensure_ascii=False,indent=2)+'\n','utf-8')
if __name__=='__main__':main()
