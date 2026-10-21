"""Prepare original-source material tables/paragraphs for explicit agent review.

No numeric extraction, no admission and no changes to published experiments.
"""
from pathlib import Path
import collections, hashlib, json, re, sqlite3, sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '全库复检与特征补提取_20261021'
sys.path.insert(0, str(ROOT))
from data.cycling_db import open_database


def text(element):
    return ' '.join(''.join(element.itertext()).split())


def main():
    if (ROOT / '循环稳定性数据库_v0.11_全库复检与材料特征_20261021/merge_manifest.json').exists():
        raise FileExistsError('Do not overwrite sealed review packets.')
    corpus = sqlite3.connect((OUT / 'full_corpus_search_native.sqlite').as_uri() + '?mode=ro', uri=True)
    corpus.row_factory = sqlite3.Row
    grouped = collections.defaultdict(list)
    with open_database() as db:
        for row in db.fetch().rows:
            grouped[row['identity_key']].append(row)
        for row in db.fetch('all_review').rows:
            if row['endpoint_id'] in ['legacy:R087_CY01', 'legacy:R013_CY01']:
                grouped[row['identity_key']].append(row)
    result = []
    for identity, rows in sorted(grouped.items()):
        documents = [dict(s) for s in corpus.execute('select distinct s.* from sources s join identity_sources i using(sha256) where i.identity_key=? and s.format in(?,?,?)', (identity, 'xml', 'pdf', 'html'))]
        documents.sort(key=lambda s: (s['format'] != 'xml', not str(s['path']).endswith('main.xml'), not str(s['path']).endswith('main.pdf'), len(str(s['path']))))
        document = next((s for s in documents if s['path'] and Path(s['path']).is_file()), None)
        entry = {'identity_key': identity, 'samples': [r['sample_name'] for r in rows], 'endpoints': [r['endpoint_id'] for r in rows], 'source': document, 'tables': [], 'paragraphs': []}
        if document and document['format'] == 'xml':
            tree = ET.parse(document['path'])
            for table in tree.findall('.//table-wrap'):
                caption = text(table.find('caption')) if table.find('caption') is not None else ''
                body = []
                for tr in table.findall('.//tr'):
                    body.append(' | '.join(text(td) for td in list(tr)))
                entry['tables'].append({'locator': 'XML table-wrap ' + str(table.get('id')), 'caption': caption, 'rows': body, 'footnotes': text(table.find('table-wrap-foot')) if table.find('table-wrap-foot') is not None else ''})
            for p in tree.findall('.//body//p'):
                content = text(p)
                if re.search(r'Raman|I.?D.?/I.?G|atomic|at\.?%|weight percent|mass loading|mg.?cm|XPS|micropore volume|pore diameter', content, re.I):
                    entry['paragraphs'].append({'locator': 'XML p ' + str(p.get('id')), 'text': content})
        else:
            seen = set()
            for s in documents:
                for h in corpus.execute("select locator,theme,excerpt from evidence_hits where sha256=? and theme in('porosity','raman_defects','composition','loading_electrode') and context_role!='possible_reference_or_comparison'", (s['sha256'],)):
                    if h['excerpt'] in seen:
                        continue
                    seen.add(h['excerpt'])
                    entry['paragraphs'].append({'locator': h['locator'], 'theme': h['theme'], 'text': h['excerpt']})
                if len(entry['paragraphs']) > 18:
                    break
        result.append(entry)
    corpus.close()
    (OUT / 'material_review_packets.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', 'utf-8')
    print(json.dumps([{'doi': e['identity_key'], 'samples': e['samples'], 'source': e['source']['path'] if e['source'] else None, 'tables': len(e['tables']), 'passages': len(e['paragraphs'])} for e in result], ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
