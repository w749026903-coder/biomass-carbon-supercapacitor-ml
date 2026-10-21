"""Compact the new automatic cue index without altering a single cue value.

The first layout duplicated long excerpts in a UNIQUE B-tree. A short SHA key
preserves deduplication while the full excerpt stays in its original data column.
"""
from pathlib import Path
import hashlib,json,sqlite3
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'全库复检与特征补提取_20261021'
RELEASE=ROOT/'循环稳定性数据库_v0.11_全库复检与材料特征_20261021'
FIELDS='hit_id,sha256,locator,theme,excerpt,context_role,status,training_eligible'


def sha(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def logical(c):
    h=hashlib.sha256();count=0
    for row in c.execute('select '+FIELDS+' from evidence_hits order by hit_id'):
        h.update(json.dumps(tuple(row),ensure_ascii=False,separators=(',',':')).encode());h.update(b'\n');count+=1
    return {'rows':count,'logical_sha256':h.hexdigest()}


def main():
    if (RELEASE/'merge_manifest.json').exists():raise FileExistsError('Do not change a sealed release index')
    path=OUT/'full_corpus_search_native.sqlite';before_bytes=path.stat().st_size;before_sha=sha(path)
    c=sqlite3.connect(path);c.execute('PRAGMA foreign_keys=ON')
    if 'excerpt_sha256' in {r[1] for r in c.execute('pragma table_info(evidence_hits)')}:
        c.close();raise FileExistsError('Index already uses compact digest deduplication')
    before=logical(c)
    terms=['Raman','capacitance','KOH','QSC']
    query_counts={term:c.execute('select count(*) from hit_search where hit_search match ?',(term,)).fetchone()[0] for term in terms}
    c.execute('BEGIN IMMEDIATE')
    try:
        c.execute('''create table evidence_hits_compact(hit_id integer primary key,sha256 text not null references sources(sha256),locator text,theme text,excerpt text,context_role text,status text not null default 'automatic_unreviewed',training_eligible integer not null default 0 check(training_eligible=0),excerpt_sha256 text not null,unique(sha256,locator,theme,excerpt_sha256))''')
        reader=c.execute('select '+FIELDS+' from evidence_hits order by hit_id')
        for row in reader.fetchall():
            c.execute('insert into evidence_hits_compact values(?,?,?,?,?,?,?,?,?)',(*row,hashlib.sha256(row[4].encode()).hexdigest()))
        c.execute('drop table evidence_hits')
        c.execute('alter table evidence_hits_compact rename to evidence_hits')
        if logical(c)!=before:raise AssertionError('Logical cue rows changed')
        if any(c.execute('select count(*) from hit_search where hit_search match ?',(term,)).fetchone()[0]!=query_counts[term] for term in terms):raise AssertionError('FTS results changed')
        c.execute('insert or replace into metadata values(?,?)',('cue_dedup_storage',json.dumps('SHA256 excerpt key; full source/excerpt values retained')))
        c.commit()
    except Exception:
        c.rollback();c.close();raise
    c.execute('VACUUM')
    assert logical(c)==before
    assert c.execute('pragma integrity_check').fetchone()[0]=='ok'
    assert not c.execute('pragma foreign_key_check').fetchall()
    assert c.execute('select count(*) from evidence_hits where training_eligible!=0').fetchone()[0]==0
    c.close()
    after_sha=sha(path);after_bytes=path.stat().st_size
    contract_path=RELEASE/'data_contract.json';contract=json.loads(contract_path.read_text('utf-8'))
    assert contract['corpus_search_database_sha256']==before_sha
    contract['corpus_search_database_sha256']=after_sha
    contract_path.write_text(json.dumps(contract,ensure_ascii=False,indent=2)+'\n','utf-8')
    report={'before_bytes':before_bytes,'after_bytes':after_bytes,'redundant_index_bytes_removed':before_bytes-after_bytes,'before_file_sha256':before_sha,'after_file_sha256':after_sha,'cue_values_and_ids_unchanged':True,'logical_fingerprint':before,'FTS_query_counts_preserved':query_counts,'originals_changed':0,'scientific_training_rows_changed':0,'model_fits':0}
    (OUT/'index_storage_optimization.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n','utf-8')
    cleanup_path=OUT/'cleanup_record.json';cleanup=json.loads(cleanup_path.read_text('utf-8'))
    cleanup['replacement_index_sha256_at_cleanup']=cleanup.pop('replacement_index_sha256')
    cleanup['subsequent_storage_optimization']='index_storage_optimization.json'
    cleanup_path.write_text(json.dumps(cleanup,ensure_ascii=False,indent=2)+'\n','utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
