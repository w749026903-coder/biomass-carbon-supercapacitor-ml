"""Bounded public publisher metadata check for all25 fixed pending sources.

Metadata locates corrections, versions and files; it never proves experiment
conditions or absence of a correction. Existing AC700 metadata is reused.
"""
from pathlib import Path
import concurrent.futures,datetime,hashlib,json,urllib.error,urllib.parse,urllib.request
ROOT=Path(__file__).resolve().parents[1];BATCH=ROOT/'持续补正_v017_20261024'
def main():
    receipt=BATCH/'publisher_metadata_pass.json'
    if receipt.exists():raise FileExistsError('Inspect saved receipts; do not repeat unchanged metadata requests.')
    queue=json.loads((BATCH/'work_queue.json').read_text('utf8'));groups={}
    for r in queue:groups.setdefault(r['source_group'],[]).append(r['endpoint_id'])
    assert len(groups)==25
    folder=BATCH/'retrieved/publisher_metadata';folder.mkdir(exist_ok=True)
    def fetch(item):
        group,keys=item;doi=group.lower().removeprefix('doi:')
        if doi.startswith('document:'):doi='10.1016/j.ultsonch.2026.108104'
        url='https://api.crossref.org/works/'+urllib.parse.quote(doi,safe='')
        out=dict(source_group=group,endpoint_ids=keys,doi=doi,url=url,checked_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),scientific_admission=False)
        try:
            existing=BATCH/'retrieved/AC700_Crossref.json'
            if doi=='10.1016/j.ultsonch.2026.108104':raw=existing.read_bytes();out.update(status=200,state='reused_existing_metadata',path=existing.relative_to(ROOT).as_posix())
            else:
                op=urllib.request.build_opener(urllib.request.ProxyHandler({'https':'http://127.0.0.1:7890'}))
                with op.open(urllib.request.Request(url,headers={'User-Agent':'ResearchEvidenceReview/1.0','Accept':'application/json'}),timeout=18) as response:raw=response.read(5*1024*1024+1);out['status']=response.status
                assert len(raw)<5*1024*1024
                data=json.loads(raw);assert data['status']=='ok' and data['message']['DOI'].lower()==doi
                path=folder/(hashlib.sha256(doi.encode()).hexdigest()[:12]+'.json');path.write_bytes(raw);out.update(state='metadata_retrieved',path=path.relative_to(ROOT).as_posix())
            data=json.loads(raw)['message']
            out.update(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),title=data.get('title'),type=data.get('type'),relation=data.get('relation',{}),update_to=data.get('update-to',[]),
                links=data.get('link',[]),resource=data.get('resource',{}),published=data.get('published'),published_online=data.get('published-online'),published_print=data.get('published-print'),
                caveat='No relation/update field is not proof there is no correction, supplement or repository.')
        except Exception as e:
            out.update(state='metadata_request_failed',error_type=type(e).__name__)
            if isinstance(e,urllib.error.HTTPError):out['status']=e.code
        return out
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:rows=list(pool.map(fetch,sorted(groups.items())))
    receipt.write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n','utf8')
    print(json.dumps(dict(sources=len(rows),retrieved=sum('path' in r for r in rows),relations=[dict(doi=r['doi'],relation=r.get('relation'),updates=r.get('update_to')) for r in rows if r.get('relation') or r.get('update_to')],failed=[dict(doi=r['doi'],status=r.get('status')) for r in rows if 'path' not in r]),ensure_ascii=False))
if __name__=='__main__':main()
