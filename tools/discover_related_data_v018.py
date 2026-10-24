"""Bounded DOI-related public DataCite discovery; never scientific admission.

The known DSAC dataset is a positive control: if its article relation is absent,
zero relation hits cannot prove there is no data. Do not rerun unchanged queries.
"""
from pathlib import Path
import concurrent.futures, csv, datetime, hashlib, json, sys, urllib.request, urllib.parse, urllib.error
ROOT=Path(__file__).resolve().parents[1]
B=ROOT/'持续补正_v017_20261024/post_v017_figure_review'
FOLDER=B/'datacite_metadata'

def main(mode='relation'):
    assert mode in ['relation','title']
    out=B/('related_data_discovery.json' if mode=='relation' else 'title_data_discovery.json')
    if out.exists():raise FileExistsError('Existing discovery retained; do not repeat unchanged queries.')
    FOLDER.mkdir(exist_ok=True)
    with (ROOT/'持续补正_v017_20261024/剩余补证资料清单.csv').open(encoding='utf-8-sig',newline='') as f:
        dois={r['doi_or_formal_doi'] for r in csv.DictReader(f)}
    dois.add('10.2139/ssrn.6799753')
    pilot='10.1038/s41598-026-63280-x'
    def get(job):
        key,kind=job
        query='titles.title:"'+key.replace('"','\\"')+'"' if kind=='title_search' else 'relatedIdentifiers.relatedIdentifier:"'+key+'"'
        url='https://api.datacite.org/dois/'+key if kind=='known_dataset_control' else 'https://api.datacite.org/dois?'+urllib.parse.urlencode({'query':query,'page[size]':10})
        row=dict(identifier=key,kind=kind,url=url,checked_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),scientific_admission=False)
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({'https':'http://127.0.0.1:7890','http':'http://127.0.0.1:7890'}))
        try:
            with opener.open(urllib.request.Request(url,headers={'Accept':'application/vnd.api+json','User-Agent':'LiteratureEvidenceAudit/1.0'}),timeout=25) as f:
                data=f.read(3*1024*1024+1);row['status']=f.status
            if len(data)>3*1024*1024:raise ValueError('Metadata response exceeds3MiB bound')
            value=json.loads(data);p=FOLDER/(hashlib.sha256((kind+key).encode()).hexdigest()[:12]+'.json');p.write_bytes(data)
            records=value.get('data',[]);records=records if isinstance(records,list) else [records]
            matches=[]
            for record in records:
                a=record.get('attributes',{})
                matches.append(dict(doi=a.get('doi',record.get('id')),titles=a.get('titles'),url=a.get('url'),types=a.get('types'),
                   related_identifiers=a.get('relatedIdentifiers'),content_urls=a.get('contentUrl'),version=a.get('version'),publisher=a.get('publisher')))
            row.update(state='metadata_only',path=p.relative_to(ROOT).as_posix(),sha256=hashlib.sha256(data).hexdigest(),
                       total=value.get('meta',{}).get('total',len(records)),returned=len(records),matches=matches)
        except urllib.error.HTTPError as exc:row.update(state='not_retrieved',status=exc.code)
        except Exception as exc:row.update(state='not_retrieved',error=type(exc).__name__+': '+str(exc)[:180])
        return row
    # A completed same-turn pilot is retained as an observed zero result, without
    # claiming an archived raw response that was not saved during the pilot.
    pilot_row=dict(identifier=pilot,kind='article_relation',status=200,total=0,returned=0,matches=[],
        state='same_turn_pilot_observation',raw_response_archived=False,
        url='https://api.datacite.org/dois?'+urllib.parse.urlencode({'query':'relatedIdentifiers.relatedIdentifier:"'+pilot+'"','page[size]':5}),
        scientific_admission=False)
    if mode=='relation':
        jobs=[(d,'article_relation') for d in sorted(dois) if d!=pilot]+[('10.17632/f7m96z8dgm.1','known_dataset_control')]
        prefix=[pilot_row]
    else:
        metadata=json.loads((ROOT/'持续补正_v017_20261024/publisher_metadata_pass.json').read_text('utf8'))
        wanted={r['source_group'] for r in json.loads((ROOT/'持续补正_v017_20261024/work_queue.json').read_text('utf8')) if r['goal_status']=='pending_scientific_resolution'}
        titles={t for r in metadata if r['source_group'] in wanted for t in r.get('title',[])}
        titles.add('Preparation of high-performance supercapacitor from Au nanoparticles decorated porous carbon by ultrasound irradiation')
        control=json.loads((B/'related_data_discovery.json').read_text('utf8'))
        c=next(r for r in control['rows'] if r['kind']=='known_dataset_control')
        for r in c.get('matches',[]):
            for title in r.get('titles',[]):titles.add(title['title'])
        jobs=[(t,'title_search') for t in sorted(titles)]
        prefix=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:rows=prefix+list(pool.map(get,jobs))
    result=dict(method_source='https://support.datacite.org/docs/queries',mode=mode,article_identifiers_queried=len(dois) if mode=='relation' else None,
        title_queries=len(jobs) if mode=='title' else None,
        fixed_pending_sources=24,extra_old_AC700_preprint_identifier=True,rows=rows,
        interpretation='Relation metadata only; absent linkage or empty result is not absence of data or supplementary information.',
        new_scientific_admissions=0)
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n','utf8')
    print(json.dumps(dict(mode=mode,queries=len(rows),metadata_success=sum(r.get('status')==200 for r in rows),
         queries_with_hits=sum(r.get('returned',0)>0 and r['kind']!='known_dataset_control' for r in rows),new_admissions=0)))

if __name__=='__main__':main(sys.argv[1] if len(sys.argv)>1 else 'relation')
