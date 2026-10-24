"""One bounded public OpenAlex location discovery, not scientific admission.

Do not rerun unchanged; results are leads, never substitutes for actual sources.
"""
from pathlib import Path
import concurrent.futures, datetime, hashlib, json, urllib.request, urllib.parse, urllib.error
ROOT=Path(__file__).resolve().parents[1];BATCH=ROOT/'持续补正_v017_20261024'

def main():
    target=BATCH/'pending_open_location_discovery.json'
    if target.exists():raise FileExistsError('Existing discovery preserved; read it before any new request.')
    queue=json.loads((BATCH/'work_queue.json').read_text('utf8'))
    dois={r['source_group'].lower().removeprefix('doi:') for r in queue if r['goal_status']=='pending_scientific_resolution' and not r['source_group'].startswith('document:')}
    dois.add('10.1016/j.micromeso.2021.111277')
    folder=BATCH/'retrieved/open_locations';folder.mkdir(exist_ok=True)
    def query(doi):
        url='https://api.openalex.org/works/https://doi.org/'+urllib.parse.quote(doi,safe='')
        row=dict(doi=doi,url=url,checked_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),purpose='Public location leads only; no full-text or numeric verification implied.')
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({'http':'http://127.0.0.1:7890','https':'http://127.0.0.1:7890'}))
        try:
            with opener.open(urllib.request.Request(url,headers={'User-Agent':'LiteratureEvidenceAudit/1.0','Accept':'application/json'}),timeout=30) as response:
                payload=response.read();row['status']=response.status
            value=json.loads(payload);path=folder/(hashlib.sha256(doi.encode()).hexdigest()[:12]+'.json')
            path.write_bytes(payload)
            locations=value.get('locations',[])
            row.update(state='metadata_location_leads',path=path.relative_to(ROOT).as_posix(),sha256=hashlib.sha256(payload).hexdigest(),
                title=value.get('display_name'),open_access=value.get('open_access'),locations_count=len(locations),
                locations=[{k:l.get(k) for k in ['is_oa','landing_page_url','pdf_url','source','version','license','is_accepted','is_published']} for l in locations])
        except urllib.error.HTTPError as exc:row.update(status=exc.code,state='not_retrieved')
        except Exception as exc:row.update(state='not_retrieved',error=type(exc).__name__+': '+str(exc)[:180])
        return row
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:rows=list(pool.map(query,sorted(dois)))
    target.write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n','utf8')
    print(json.dumps(dict(queried=len(rows),retrieved=sum(r.get('status')==200 for r in rows),leads_with_pdf=sum(any(l.get('pdf_url') for l in r.get('locations',[])) for r in rows),scientific_admissions=0)))

if __name__=='__main__':main()
