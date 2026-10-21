"""Finish original-Word discovery, reviewed SI bindings and full native-text FTS.

The full-text index is contentless: immutable upstream text is not recopied.
Scientific admissions remain exclusively in the separate reviewed v0.11 ledger.
"""
from pathlib import Path
import collections, csv, hashlib, json, re, sqlite3, subprocess, sys
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'全库复检与特征补提取_20261021'
sys.path.insert(0,str(ROOT))
from data.cycling_db import open_database
from search_full_corpus_v011 import parse_original, PATTERNS


def sha(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def read(path):return json.loads(path.read_text('utf-8'))


def write(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n','utf-8')


def main():
    if (ROOT/'循环稳定性数据库_v0.11_全库复检与材料特征_20261021/merge_manifest.json').exists():raise FileExistsError('Sealed corpus cannot change')
    c=sqlite3.connect(OUT/'full_corpus_search_native.sqlite');c.row_factory=sqlite3.Row;c.execute('PRAGMA foreign_keys=ON')
    if c.execute("select 1 from metadata where key='full_native_index_complete' and value_json='true'").fetchone():raise FileExistsError('Full native index already complete; inspect rather than rerun')
    receipts={r['sha256']:r for r in read(ROOT/'数据质量优化_20261021/SI_identity_reviews.json')}
    discovered=[]
    with open_database() as db:
        source_map={r['document_id']:r for r in db.incoming_sources()}
        docx_files=subprocess.check_output(['rg','--files','-g','*.docx'],cwd=ROOT,encoding='utf-8').splitlines()
        for name in docx_files:
            p=ROOT/name;fingerprint=sha(p)
            if c.execute('select 1 from sources where sha256=?',(fingerprint,)).fetchone():continue
            receipt=receipts.get(fingerprint)
            if not receipt or not receipt['identity_verified']:raise ValueError('New Word source needs explicit provenance review: '+name)
            source=source_map[receipt['document_id']];identity='doi:'+source['doi'].lower()
            segments=parse_original(p);chars=sum(len(text) for _,text in segments)
            c.execute('insert into sources values(?,?,?,?,?,?,?,?)',(fingerprint,'docx',str(p),'verified_existing_SI_receipt_original','native_text_searched',len(segments),chars,None))
            c.execute('insert into locations values(?,?)',(fingerprint,str(p)))
            c.execute('insert or ignore into identities values(?,?,?,?)',(identity,source['doi'].lower(),receipt['title'],'existing_verified_SI_receipt'))
            c.execute('insert or ignore into identity_sources values(?,?,?,?)',(identity,fingerprint,'supplementary_verified_receipt',receipt['basis']))
            for loc,text in segments:
                c.execute('insert into new_native_segments values(?,?,?)',(fingerprint,loc,text))
                for theme,pattern in PATTERNS.items():
                    starts=[]
                    for match in pattern.finditer(text):
                        if any(abs(match.start()-x)<500 for x in starts):continue
                        starts.append(match.start());excerpt=text[max(0,match.start()-220):match.start()+850]
                        c.execute('insert or ignore into evidence_hits(sha256,locator,theme,excerpt,context_role,excerpt_sha256) values(?,?,?,?,?,?)',(fingerprint,loc,theme,excerpt,'native_context_not_scientifically_bound',hashlib.sha256(excerpt.encode()).hexdigest()))
                        if len(starts)>=8:break
            discovered.append({'path':name,'sha256':fingerprint,'doi':source['doi'],'text_chars':chars})
        for review in read(OUT/'supplement_identity_reviews.json'):
            if sha(ROOT/review['si_path'])!=review['si_sha256'] or sha(ROOT/review['main_xml_path'])!=review['main_xml_sha256']:raise ValueError('SI identity evidence changed')
            c.execute('insert or ignore into identity_sources values(?,?,?,?)',('doi:'+review['doi'],review['si_sha256'],'supplementary_agent_title_authors_verified',review['basis']))
        c.executescript('''
        create table full_native_map_v11(map_id integer primary key,source_sha256 text references sources(sha256),locator text,provider text,upstream_key_json text,content_sha256 text,text_chars integer);
        create virtual table full_native_fts_v11 using fts5(text,content='');
        ''')
        known={r[0] for r in c.execute('select sha256 from sources')};parent_shas=set()
        def insert(fingerprint,loc,provider,key,text):
            if fingerprint not in known or not text:return
            cursor=c.execute('insert into full_native_map_v11(source_sha256,locator,provider,upstream_key_json,content_sha256,text_chars) values(?,?,?,?,?,?)',(fingerprint,loc,provider,json.dumps(key),hashlib.sha256(text.encode()).hexdigest(),len(text)))
            c.execute('insert into full_native_fts_v11(rowid,text) values(?,?)',(cursor.lastrowid,text))
        for row in db.conn.execute('select segment_id,source_id,locator,text from source_segments order by segment_id'):
            parent_shas.add(row['source_id']);insert(row['source_id'],row['locator'],'v08_source_segments',{'segment_id':row['segment_id']},row['text'])
        for row in db.conn.execute('select * from candidate_sources_v07'):
            fingerprint=json.loads(row['metadata_json'])['sha256']
            if fingerprint in parent_shas:continue
            for segment in db.conn.execute('select segment_id,locator,text from candidate_source_segments_v07 where pmcid=? order by ordinal',(row['pmcid'],)):
                insert(fingerprint,segment['locator'],'v07_candidate_segments',{'segment_id':segment['segment_id']},segment['text'])
            parent_shas.add(fingerprint)
        for source in source_map.values():
            fingerprint=source['sha256']
            if fingerprint in parent_shas:continue
            for row in db.conn.execute('select page_number,text from incoming_pages_v08 where document_id=? order by page_number',(source['document_id'],)):
                insert(fingerprint,'PDF p'+str(row['page_number']),'v08_incoming_pages',{'document_id':source['document_id'],'page_number':row['page_number']},row['text'])
            parent_shas.add(fingerprint)
        for row in c.execute('select * from new_native_segments').fetchall():
            if row['sha256'] not in parent_shas:insert(row['sha256'],row['locator'],'v11_new_native_segments',{'sha256':row['sha256'],'locator':row['locator']},row['text'])
    c.execute("insert into hit_search(hit_search) values('rebuild')")
    c.execute('insert into metadata values(?,?)',('full_native_index_complete','true'));c.commit()
    with (OUT/'逐来源检索覆盖.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f);w.writerow(['identity_key','doi','title','identity_basis','linked_source_contents','native_text_searched_sources','automatic_unreviewed_hits'])
        w.writerows(c.execute("select i.identity_key,i.doi,i.title,i.basis,count(distinct s.sha256),count(distinct case when s.scan_state='native_text_searched' then s.sha256 end),count(distinct h.hit_id) from identities i left join identity_sources l using(identity_key) left join sources s on s.sha256=l.sha256 left join evidence_hits h on h.sha256=s.sha256 group by i.identity_key order by i.identity_key"))
    summary={'unique_source_contents':c.execute('select count(*) from sources').fetchone()[0],'source_states':dict(c.execute('select scan_state,count(*) from sources group by scan_state')),
             'catalog_identity_entries_not_verified_paper_count':c.execute('select count(*) from identities').fetchone()[0],
             'full_native_index_segments':c.execute('select count(*) from full_native_map_v11').fetchone()[0],
             'full_native_index_source_contents':c.execute('select count(distinct source_sha256) from full_native_map_v11').fetchone()[0],
             'automatic_evidence_hits':c.execute('select count(*) from evidence_hits').fetchone()[0],
             'new_Word_SI_receipt_sources':discovered,'native_unbound_source_count':c.execute("select count(*) from sources s where scan_state='native_text_searched' and not exists(select 1 from identity_sources i where i.sha256=s.sha256)").fetchone()[0],
             'automatic_admissions':0,'model_fits':0,'originals_changed':0,'native_text_not_full_figure_scientific_review':True}
    assert c.execute('pragma integrity_check').fetchone()[0]=='ok'
    assert not c.execute('pragma foreign_key_check').fetchall()
    assert c.execute('select count(*) from evidence_hits where training_eligible!=0').fetchone()[0]==0
    c.close();write(OUT/'final_corpus_summary.json',summary);print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
