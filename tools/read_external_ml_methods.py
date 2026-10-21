"""Inspect six public, revision-pinned files as text/data; never execute them."""
import csv
import hashlib
import io
import json
from pathlib import Path
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / '.local-literature-cache/method-audit-20261021'
TARGETS = [
    ('Shan-Zhu/ML-Carbon_Supercapacitor', '2e7ca3e8b3755819c038fde1402741ab708a719f', 'NN-train'),
    ('Shan-Zhu/ML-Carbon_Supercapacitor', '2e7ca3e8b3755819c038fde1402741ab708a719f', 'Database of Carbon-based Supercapacitors.csv'),
    ('Shan-Zhu/ML-SC_3DCN', 'f3094e00269513e97d64d45b6fd8c8f9c53b0e6a', 'TPOT.py'),
    ('Shan-Zhu/ML-SC_3DCN', 'f3094e00269513e97d64d45b6fd8c8f9c53b0e6a', '3DCN-2022.csv'),
    ('khub-crystalparadigm/capacitance_pred', 'ca7fcfdb0f432d30312ccb87175fe17798f53030', 'Final_Model_Catboost.ipynb'),
    ('khub-crystalparadigm/capacitance_pred', 'ca7fcfdb0f432d30312ccb87175fe17798f53030', 'composites.csv'),
]


def main():
    target = ROOT / '文献利用与外部方法审查_20261021/external_reads.json'
    if target.exists():
        raise FileExistsError('Preserve the completed access record.')
    CACHE.mkdir(parents=True, exist_ok=True)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler(
        {'http': 'http://127.0.0.1:7890', 'https': 'http://127.0.0.1:7890'}))
    index = []
    for n, (repo, commit, name) in enumerate(TARGETS):
        url = 'https://raw.githubusercontent.com/' + repo + '/' + commit + '/' + urllib.parse.quote(name)
        item = {'repository': repo, 'commit': commit, 'path': name, 'raw_url': url}
        try:
            request = urllib.request.Request(url, headers={'User-Agent': 'literature-method-audit'})
            with opener.open(request, timeout=25) as response:
                blob = response.read(8 * 1024 * 1024 + 1)
            if len(blob) > 8 * 1024 * 1024:
                raise ValueError('Read cap exceeded.')
            cache_path = CACHE / (str(n) + '_' + name)
            cache_path.write_bytes(blob)
            item.update(sha256=hashlib.sha256(blob).hexdigest(), bytes=len(blob),
                        cache_path=cache_path.relative_to(ROOT).as_posix())
            text = blob.decode('utf-8-sig', 'replace')
            if name.endswith('.csv'):
                dialect = csv.Sniffer().sniff(text[:6000], delimiters=',;\t')
                rows = list(csv.DictReader(io.StringIO(text), dialect=dialect))
                item.update(data_rows=len(rows), columns=list(rows[0]) if rows else [])
                print('DATA', json.dumps(item, ensure_ascii=False), flush=True)
            elif name.endswith('.ipynb'):
                cells = [(i, ''.join(c.get('source', []))) for i, c in enumerate(json.loads(text)['cells']) if c['cell_type'] == 'code']
                item['code_cell_count'] = len(cells)
                print('NOTEBOOK', repo, 'code cells', len(cells), flush=True)
                for i, code in cells:
                    lines = code.splitlines()
                    hits = [j for j, line in enumerate(lines) if any(k in line for k in
                            ['GroupShuffle', 'GroupKFold', 'train_test_split', 'fit_transform', 'fillna',
                             'SimpleImputer', 'external', 'External', 'DOI', 'groups', 'eval_set', 'r2_score', 'median'])]
                    selected = sorted({j for h in hits for j in range(max(0, h - 1), min(len(lines), h + 3))})
                    print('CELL', i, 'LINES', len(lines), '\n' + '\n'.join(str(j + 1) + ':' + lines[j] for j in selected)[:15000], flush=True)
            else:
                print('CODE', repo, name, '\n' + text[:7500], flush=True)
        except Exception as exc:
            item['error'] = type(exc).__name__ + ': ' + str(exc)[:200]
            print('ACCESS', item, flush=True)
        index.append(item)
    target.write_text(json.dumps(index, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('READ_INDEX', json.dumps(index, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
