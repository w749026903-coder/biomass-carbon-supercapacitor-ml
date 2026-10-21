"""Bind native XML metadata/SI package links and verify the external library.

Only the new unsealed automatic search index is updated. No scientific admission.
"""
from pathlib import Path
import collections, hashlib, json, re, sqlite3, subprocess
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '全库复检与特征补提取_20261021'


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def local(tag):
    return tag.split('}')[-1]


def main():
    path = OUT / 'full_corpus_search_native.sqlite'
    c = sqlite3.connect(path); c.row_factory = sqlite3.Row
    c.execute('PRAGMA foreign_keys=ON')
    if (ROOT / '循环稳定性数据库_v0.11_全库复检与材料特征_20261021/merge_manifest.json').exists():
        raise FileExistsError('Do not change a sealed search index.')
    c.execute('create table if not exists identity_metadata_v11(identity_key text,source_sha256 text,metadata_json text not null,primary key(identity_key,source_sha256))')
    original_links = c.execute('select count(*) from identity_sources').fetchone()[0]
    xml_documents = []
    for s in c.execute("select * from sources where format='xml'").fetchall():
        p = Path(s['path']) if s['path'] else None
        if not p or not p.is_file():
            continue
        if sha(p) != s['sha256']:
            raise ValueError('XML original fingerprint changed.')
        root = ET.parse(p).getroot()
        front = next((e for e in root.iter() if local(e.tag) == 'front'), None)
        meta = next((e for e in front.iter() if local(e.tag) == 'article-meta'), None) if front is not None else None
        if meta is None:
            continue
        ids = {e.get('pub-id-type'): ''.join(e.itertext()).strip() for e in list(meta) if local(e.tag) == 'article-id'}
        doi = ids.get('doi', '').lower().removeprefix('https://doi.org/')
        if not re.fullmatch(r'10\.\d{4,9}/\S+', doi):
            continue
        key = 'doi:' + doi
        title = next((' '.join(''.join(e.itertext()).split()) for e in meta.iter() if local(e.tag) == 'article-title'), '')
        dates = []
        for date in meta.iter():
            if local(date.tag) == 'pub-date':
                year = next((''.join(e.itertext()) for e in date.iter() if local(e.tag) == 'year'), None)
                dates.append({'year': year, 'type': date.get('pub-type') or date.get('publication-format') or date.get('date-type')})
        m = {'doi':doi,'title':title,'article_type':root.get('article-type'),'dates':dates,'pmcid':ids.get('pmcid'),
             'basis':'Primary XML front/article-meta fields; source acquisition identity still requires scientific review','path':str(p)}
        c.execute('insert or ignore into identities values(?,?,?,?)',(key,doi,title,'structural_XML_front_metadata_not_admission'))
        c.execute('insert or ignore into identity_sources values(?,?,?,?)',(key,s['sha256'],'main_XML_metadata','XML front/article-meta DOI'))
        c.execute('insert or replace into identity_metadata_v11 values(?,?,?)',(key,s['sha256'],json.dumps(m,ensure_ascii=False)))
        hrefs = {str(v).split('/')[-1] for e in root.iter() for k,v in e.attrib.items() if local(k) == 'href'}
        xml_documents.append((p,key,hrefs,m))
    unresolved_supplements = []
    for s in c.execute("select * from sources s where format='pdf' and not exists(select 1 from identity_sources i where i.sha256=s.sha256)").fetchall():
        p = Path(s['path']) if s['path'] else None
        matches = [(x,key) for x,key,hrefs,_ in xml_documents if p and p.name in hrefs and x.parent in p.parents]
        if len({key for _,key in matches}) == 1:
            key = matches[0][1]
            c.execute('insert or ignore into identity_sources values(?,?,?,?)',(key,s['sha256'],'supplementary_package_verified_href','Same source package; primary XML href exactly matches local filename'))
        else:
            unresolved_supplements.append({'sha256':s['sha256'],'path':s['path'],'reason':'No unique primary-XML attachment binding; keep unbound'})
    # External paths are read-only. Generated navigation/reading HTML adds no paper.
    library = Path('D:/文献')
    files = subprocess.check_output(['rg','--files','-g','*.pdf','-g','*.xml','-g','*.docx','-g','*.html','-g','*.htm',str(library)],encoding='utf-8').splitlines()
    known = {r[0] for r in c.execute('select sha256 from sources')}
    pmcids = {m['pmcid'] for _,_,_,m in xml_documents if m['pmcid']}
    inventory = []; gaps = []
    for name in files:
        p = Path(name); fingerprint = sha(p)
        state = 'covered_primary_or_acquired_content' if fingerprint in known else 'unmapped'
        if state == 'unmapped' and p.suffix.lower() in ['.html','.htm']:
            if p.name.startswith('打开'):
                state = 'excluded_generated_directory_navigation'
            elif p.name == '正文阅读版.html':
                pmcid = re.search(r'PMC\d+',str(p))
                if pmcid and pmcid.group() in pmcids:
                    state = 'excluded_derived_reading_view_original_XML_covered'
        record = {'path':str(p),'sha256':fingerprint,'bytes':p.stat().st_size,'coverage':state}
        inventory.append(record)
        if state == 'covered_primary_or_acquired_content':
            c.execute('insert or ignore into locations values(?,?)',(fingerprint,str(p)))
        elif state == 'unmapped':
            gaps.append(record)
    c.commit()
    assert c.execute('pragma integrity_check').fetchone()[0]=='ok'
    assert not c.execute('pragma foreign_key_check').fetchall()
    result = {'external_library':str(library),'external_file_counts':dict(collections.Counter(Path(r['path']).suffix.lower() for r in inventory)),
              'external_coverage_counts':dict(collections.Counter(r['coverage'] for r in inventory)),'external_unresolved':gaps,
              'structural_XML_documents':len(xml_documents),'new_identity_links':c.execute('select count(*) from identity_sources').fetchone()[0]-original_links,
              'catalog_identity_entries_not_verified_paper_count':c.execute('select count(*) from identities').fetchone()[0],
              'unbound_SI_candidates':unresolved_supplements,'scientific_admissions':0,'model_fits':0}
    (OUT/'external_library_inventory.json').write_text(json.dumps(inventory,ensure_ascii=False,indent=2)+'\n','utf-8')
    (OUT/'identity_and_library_coverage.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n','utf-8')
    c.close()
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
