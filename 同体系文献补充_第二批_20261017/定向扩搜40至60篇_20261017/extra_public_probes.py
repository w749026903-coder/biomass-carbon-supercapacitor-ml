import json,urllib.request,hashlib,concurrent.futures,io
from pathlib import Path
from pypdf import PdfReader
from lxml import html
ROOT=Path(__file__).resolve().parent
jobs=[('P003','https://www.jstage.jst.go.jp/article/electrochemistry/93/10/93_25-71119/_pdf','main.pdf'),('P021','https://data.mendeley.com/public-api/datasets/3w6yb4d844/versions/1','dataset_metadata.json'),('P058','https://onlinelibrary.wiley.com/doi/10.1002/eem2.70174','publisher.html'),('P021','https://onlinelibrary.wiley.com/doi/suppl/10.1002/est2.616/supinfo/est2616-sup-0001-figures.pdf','supporting_information.pdf'),('P007','https://acs.figshare.com/doi/suppl/10.1021/acsaem.4c01027','public_supplement_landing.html')]
def run(item):
    wid,u,fn=item;d=ROOT/'sources'/wid;d.mkdir(parents=True,exist_ok=True);rec={'working_id':wid,'url':u,'filename':fn}
    try:
        with urllib.request.urlopen(u,timeout=25) as r:b=r.read(25000001);rec.update(final_url=r.geturl(),content_type=r.headers.get('Content-Type'))
        if fn.endswith('.pdf'):
            assert b.startswith(b'%PDF');ps=[{'page':i+1,'text':p.extract_text() or ''} for i,p in enumerate(PdfReader(io.BytesIO(b)).pages)];(d/(fn+'.pages.json')).write_text(json.dumps(ps,ensure_ascii=False,indent=2),encoding='utf-8')
        elif fn.endswith('.json'):json.loads(b)
        (d/fn).write_bytes(b);rec.update(status='obtained_check_content',bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
        if fn.endswith('.html'):(d/(fn+'.txt')).write_text(' '.join(html.fromstring(b).text_content().split()),encoding='utf-8')
    except Exception as e:rec.update(status='failed_no_bypass',error=str(e))
    print(wid,fn,rec['status'],flush=True);return rec
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as p:outs=list(p.map(run,jobs))
(ROOT/'额外公开入口获取日志.json').write_text(json.dumps(outs,ensure_ascii=False,indent=2),encoding='utf-8')
