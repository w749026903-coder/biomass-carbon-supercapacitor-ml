"""Read-only original text packets for the fixed 87 pending v0.11 3E tests.

Packets are retrieval aids, never an automatic scientific admission decision.
The sealed v0.11 corpus is read in place; no full-text database is copied.
"""
from pathlib import Path
import collections, hashlib, json, re, sqlite3, sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '待补证原文复核_20261022'
INDEX = ROOT / '全库复检与特征补提取_20261021/full_corpus_search_native.sqlite'
sys.path.insert(0, str(ROOT))
from data.cycling_db import open_database


def full_text(db, conn, row):
    key = json.loads(row['upstream_key_json'])
    provider = row['provider']
    if provider == 'v08_source_segments':
        value = db.conn.execute('select text from source_segments where segment_id=?', (key['segment_id'],)).fetchone()[0]
    elif provider == 'v07_candidate_segments':
        value = db.conn.execute('select text from candidate_source_segments_v07 where segment_id=?', (key['segment_id'],)).fetchone()[0]
    elif provider == 'v08_incoming_pages':
        value = db.conn.execute('select text from incoming_pages_v08 where document_id=? and page_number=?', (key['document_id'], key['page_number'])).fetchone()[0]
    elif provider == 'v11_new_native_segments':
        value = conn.execute('select text from new_native_segments where sha256=? and locator=?', (key['sha256'],key['locator'])).fetchone()[0]
    else:
        raise ValueError(provider)
    assert hashlib.sha256(value.encode()).hexdigest() == row['content_sha256']
    return value


def packets():
    with open_database() as db, sqlite3.connect(INDEX.as_uri()+'?mode=ro',uri=True) as conn:
        conn.row_factory = sqlite3.Row
        pending = [r for r in db.fetch('review_3e_all').rows if not r.get('admission_profiles_v11')]
        assert len(pending) == 87, 'This task requires the fixed v0.11 baseline.'
        groups = collections.defaultdict(list)
        for r in pending:groups[r['source_group'].removeprefix('doi:')].append(r)
        result = []
        for doi,rows in groups.items():
            identity = doi if doi.startswith('document:') else 'doi:'+doi
            sources = [dict(r) for r in conn.execute('select distinct s.*,i.role from sources s join identity_sources i using(sha256) where i.identity_key=? order by s.format,s.path',(identity,))]
            segments=[];seen=set()
            for source in sources:
                for seg in conn.execute('select * from full_native_map_v11 where source_sha256=? order by map_id',(source['sha256'],)).fetchall():
                    text=full_text(db,conn,seg)
                    fingerprint=hashlib.sha256(text.encode()).hexdigest()
                    if fingerprint in seen:continue
                    seen.add(fingerprint)
                    segments.append({'path':source['path'],'sha256':source['sha256'],'format':source['format'],'role':source['role'],'locator':seg['locator'],'text':text})
            result.append({'doi':doi,'rows':rows,'sources':sources,'segments':segments,'scientific_admission':False})
        return result


def show(data, dois):
    for paper in data:
        if not any(d.lower() in paper['doi'].lower() for d in dois):continue
        print('\nPAPER',paper['doi'])
        print('ROWS',[(r['endpoint_id'],r['sample_name'],r.get('retention_pct')) for r in paper['rows']])
        prefer_xml=any(s['format']=='xml' for s in paper['segments'])
        for s in paper['segments']:
            if prefer_xml and s['format']!='xml':continue
            text=s['text']
            pattern=r'reference electrode|counter electrode|potential window|potential range|voltage window|voltage range|capacitance retention|cycling stability|retention rate|initial capacitance|S.?BET|Table 7|Table7'
            if re.search(pattern,text,re.I):
                print('SOURCE',s['path'],s['sha256'],'LOC',s['locator'])
                if s['format']=='pdf':
                    spans=[]
                    for match in re.finditer(pattern,text,re.I):
                        if any(a<=match.start()<=b for a,b in spans):continue
                        spans.append((max(0,match.start()-280),min(len(text),match.end()+950)))
                    for a,b in spans:print(text[a:b])
                else:print(text[:6500])


if __name__ == '__main__':
    if '--prepare' in sys.argv:
        OUT.mkdir(exist_ok=True)
        target=OUT/'original_review_packets.json'
        if target.exists():raise FileExistsError('Packets exist; do not overwrite original task snapshot.')
        data=packets()
        target.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n','utf-8')
        print(json.dumps({'papers':len(data),'tests':sum(len(p['rows']) for p in data),'sources':sum(len(p['sources']) for p in data),'segments':sum(len(p['segments']) for p in data),'admissions':0},ensure_ascii=False))
    elif '--show' in sys.argv:
        data=json.loads((OUT/'original_review_packets.json').read_text('utf-8'))
        show(data,sys.argv[sys.argv.index('--show')+1:])
    else:
        raise SystemExit('Choose --prepare or --show DOI...')
