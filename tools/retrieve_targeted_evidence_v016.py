"""Bounded retrieval of observed public publisher links, never access controls."""
from pathlib import Path
import concurrent.futures,datetime,hashlib,io,json,sys,urllib.request,urllib.error,zipfile
ROOT=Path(__file__).resolve().parents[1]
BATCH=ROOT/'补证与测量口径复核_v016_20261024'
URLS=[
 ('Fe_SN6C_SI','10.1186/s42825-023-00122-w','supplementary','docx','https://media.springernature.com/original/springer-static/esm/art%3A10.1186%2Fs42825-023-00122-w/MediaObjects/42825_2023_122_MOESM1_ESM.docx','Current official article supplementary link119'),
 ('aGCL_SI','10.1002/slct.202204616','supplementary','pdf','https://chemistry-europe.onlinelibrary.wiley.com/doi/suppl/10.1002/slct.202204616/supinfo/slct202204616-sup-0001-misc_information.pdf','Current official supporting-information filename/link21'),
 ('FWCA_cited_method15','10.1016/j.micromeso.2021.111277','publisher_api','xml','https://api.elsevier.com/content/article/pii/S1387181121004030?httpAccept=text/xml','Known DOI/PII public publisher API; no credentials or access entitlement assumed'),
 ('LWCA_publisher','10.1007/s00226-023-01515-0','publisher_page','html','https://link.springer.com/article/10.1007/s00226-023-01515-0','Current official version of record landing page'),
 ('Fe_SN6C_publisher','10.1186/s42825-023-00122-w','publisher_page','html','https://link.springer.com/article/10.1186/s42825-023-00122-w','Current official open-access main article'),
]
def fetch(item):
    name,doi,kind,ext,url,basis=item
    rec=dict(name=name,doi=doi,component=kind,url=url,url_basis=basis,checked_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),scientific_admission=False)
    try:
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({'https':'http://127.0.0.1:7890','http':'http://127.0.0.1:7890'}))
        req=urllib.request.Request(url,headers={'User-Agent':'ResearchEvidenceReview/1.0','Accept':'*/*'})
        with opener.open(req,timeout=35) as response:
            data=response.read(30*1024*1024+1);rec.update(status=response.status,content_type=response.headers.get('Content-Type'),final_url=response.url,bytes=len(data))
        if len(data)>30*1024*1024:rec['state']='size_bound_reached_not_saved';return rec
        valid=(data.startswith(b'%PDF') if ext=='pdf' else zipfile.is_zipfile(io.BytesIO(data)) and 'word/document.xml' in zipfile.ZipFile(io.BytesIO(data)).namelist() if ext=='docx' else data.lstrip().startswith(b'<'))
        if not valid:rec['state']='not_requested_document_format_not_saved';return rec
        p=BATCH/'retrieved'/(name+'.'+ext)
        if p.exists():raise FileExistsError(p)
        p.write_bytes(data);rec.update(state='retrieved_format_checked_identity_pending',path=p.relative_to(ROOT).as_posix(),sha256=hashlib.sha256(data).hexdigest())
    except Exception as e:
        rec.update(state='retrieval_failed',error_type=type(e).__name__)
        if isinstance(e,urllib.error.HTTPError):rec['status']=e.code
    return rec
def main():
    receipt=BATCH/'publisher_acquisition.json'
    if receipt.exists():raise FileExistsError('Use saved receipt; do not repeat the same acquisition batch.')
    (BATCH/'retrieved').mkdir(parents=True,exist_ok=True)
    pointer=json.loads((ROOT/'data/current_database.json').read_text('utf-8'));assert pointer['version_directory'].startswith('循环稳定性数据库_v0.15_')
    (BATCH/'parent_pointer.json').write_text(json.dumps(pointer,ensure_ascii=False,indent=2)+'\n','utf-8')
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(fetch,URLS))
    receipt.write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n','utf-8')
    print(json.dumps([{k:r.get(k) for k in ['name','state','status','bytes','path']} for r in results],ensure_ascii=False))
if __name__=='__main__':main()
