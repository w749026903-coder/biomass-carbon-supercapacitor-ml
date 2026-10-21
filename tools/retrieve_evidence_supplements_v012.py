"""Bounded public publisher SI retrieval for three explicitly identified gaps."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import hashlib, json, zipfile, io, urllib.request, urllib.error, sys

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'待补证原文复核_20261022'
TARGETS=[('NCHU20','10.1016/j.biombioe.2026.109160','S0961953426002357'),
         ('NPC7006','10.1016/j.jenvman.2025.125582','S0301479725015580'),
         ('CCL','10.1016/j.biombioe.2026.109168','S0961953426002436')]
MAX_BYTES = (96 if '--large-nchu' in sys.argv else 20)*1024*1024
FOLLOW_METHODS=[('FWCA_cited_method15','10.1016/j.micromeso.2021.111277','S1387181121004030'),
                ('SSK05','10.1016/j.diamond.2026.113577','S0925963526002888')]

def fetch(target):
    name,doi,pii=target; attempts=[]
    for ext in ['docx','pdf']:
        url=f'https://ars.els-cdn.com/content/image/1-s2.0-{pii}-mmc1.{ext}'
        entry={'doi':doi,'component':'supplementary','url':url,'url_basis':'publisher public attachment naming convention; existence not assumed','extension':ext}
        try:
            opener=urllib.request.build_opener(urllib.request.ProxyHandler({'https':'http://127.0.0.1:7890','http':'http://127.0.0.1:7890'}))
            try:
                response=opener.open(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=25)
            except urllib.error.HTTPError as error:
                response=error
            with response:
                content=response.read(MAX_BYTES+1);status=response.code;ctype=response.headers.get('Content-Type')
            entry.update(status_code=status,bytes_received=len(content),content_type=ctype)
            valid=status==200 and len(content)<=MAX_BYTES and ((ext=='pdf' and content.startswith(b'%PDF-')) or (ext=='docx' and content.startswith(b'PK') and zipfile.is_zipfile(io.BytesIO(content))))
            if valid:
                path=OUT/'new_supplements'/f'{name}_mmc1.{ext}';path.parent.mkdir(exist_ok=True)
                if path.exists():raise FileExistsError(path)
                path.write_bytes(content)
                entry.update(path=path.relative_to(ROOT).as_posix(),sha256=hashlib.sha256(content).hexdigest(),state='downloaded_format_valid_identity_pending',training_eligible=False)
            else:entry['state']='response_exceeds_size_cap' if len(content)>MAX_BYTES else 'unavailable_or_not_requested_document_format'
        except Exception as exc:
            entry.update(state='network_or_file_error',error_type=type(exc).__name__)
        attempts.append(entry)
        if entry.get('path'):break
    return attempts

if __name__=='__main__':
    report=OUT/('publisher_method_followup.json' if '--follow-methods' in sys.argv else 'publisher_SI_size_followup.json' if '--large-nchu' in sys.argv else 'publisher_SI_acquisition.json')
    if report.exists():raise FileExistsError('Retain existing acquisition evidence; do not blindly retry.')
    OUT.mkdir(exist_ok=True)
    targets=FOLLOW_METHODS if '--follow-methods' in sys.argv else TARGETS[:1] if '--large-nchu' in sys.argv else TARGETS
    with ThreadPoolExecutor(max_workers=3) as pool:results=[item for group in pool.map(fetch,targets) for item in group]
    report.write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n','utf-8')
    print(json.dumps(results,ensure_ascii=False,indent=2))
