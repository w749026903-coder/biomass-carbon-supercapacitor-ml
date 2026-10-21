"""Search every catalogued/local literature source into a new evidence queue.

No scientific admission or model fitting. Reuse immutable parsed text by SHA;
parse newly discovered originals once. Original files and prior databases stay read-only.
"""
from pathlib import Path
import collections
import csv
import hashlib
import io
import json
import os
import re
import sqlite3
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
import zipfile
from html.parser import HTMLParser

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '全库复检与特征补提取_20261021'
sys.path.insert(0, str(ROOT))
from data.cycling_db import open_database

THEMES = {
    'cycling_label': r'retent|cyclab|cyclic stability|cycling stability|\d[\d, ]{2,}\s*cycles',
    'porosity': r'BET|specific surface area|pore volume|micropor|mesopor|pore diameter',
    'composition': r'XPS|atomic percent|at\.?\s*%|wt\.?\s*%|heteroatom|elemental analysis|N\s*1s|O\s*1s',
    'raman_defects': r'Raman|I\s*D\s*/\s*I\s*G|I[Dd][ /_]*I[Gg]|D.band|G.band|d002',
    'synthesis': r'carboniz|carbonis|pyrolys|activat.{0,20}temperature|heating rate|residence time|impregnat',
    'loading_electrode': r'mass loading|mg\s*/\s*cm|binder|PVDF|PTFE|nickel foam|working electrode',
    'cycle_protocol': r'galvanostatic|charge.discharge|GCD|current density|potential window|voltage window',
    'reference_electrolyte': r'Hg/HgO|Ag/AgCl|calomel|SCE|reference electrode|KOH|NaOH|H2SO4|Na2SO4',
    'morphology': r'nanofib|carbon fib|nanosheet|aerogel|self.support|morpholog',
}
PATTERNS = {k: re.compile(v, re.I) for k, v in THEMES.items()}


def read(p):
    return json.loads(p.read_text(encoding='utf-8'))


def digest(p):
    with p.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def write(p, obj):
    tmp = p.with_suffix(p.suffix + '.tmp')
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    for n in range(12):
        try:
            os.replace(tmp, p)
            return
        except PermissionError:
            if n == 11:
                raise
            time.sleep(.04)


def canonical(doi):
    return str(doi or '').strip().lower().removeprefix('https://doi.org/').removeprefix('doi:').rstrip('.,;')


class TextHTML(HTMLParser):
    def __init__(self):
        super().__init__(); self.text = []; self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ['script', 'style']:
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in ['script', 'style']:
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data):
        if not self.hidden:
            self.text.append(data)


def parse_original(path, blob=None):
    suffix = path.suffix.lower()
    if suffix == '.zip':
        result = []
        with zipfile.ZipFile(io.BytesIO(blob) if blob is not None else path) as archive:
            for member in archive.infolist():
                ext = Path(member.filename).suffix.lower()
                if member.is_dir() or ext not in ['.pdf', '.xml', '.html', '.htm', '.docx', '.xlsx', '.csv', '.tsv', '.txt']:
                    continue
                if member.file_size > 64 * 1024 * 1024:
                    result.append(('ZIP member ' + member.filename, '[Native member exceeds64MiB review cap; manual follow-up]'))
                    continue
                payload = archive.read(member)
                member_sha = hashlib.sha256(payload).hexdigest()
                try:
                    for locator, text in parse_original(Path(member.filename), payload):
                        result.append(('ZIP ' + member.filename + ' SHA256=' + member_sha + ' / ' + locator, text))
                except Exception as exc:
                    result.append(('ZIP member ' + member.filename, '[Parse unresolved: ' + type(exc).__name__ + ']'))
        return result
    if suffix in ['.docx', '.xlsx']:
        with zipfile.ZipFile(io.BytesIO(blob) if blob is not None else path) as archive:
            if suffix == '.docx':
                doc = ET.fromstring(archive.read('word/document.xml'))
                return [('DOCX body/tables', ' '.join(doc.itertext()))]
            ns = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
            strings = []
            if 'xl/sharedStrings.xml' in archive.namelist():
                shared = ET.fromstring(archive.read('xl/sharedStrings.xml'))
                strings = [''.join(e.itertext()) for e in shared.findall('s:si', ns)]
            result = []
            for name in archive.namelist():
                if not re.fullmatch(r'xl/worksheets/sheet\d+\.xml', name):
                    continue
                sheet = ET.fromstring(archive.read(name)); rows = []
                for row in sheet.findall('.//s:row', ns):
                    values = []
                    for cell in row.findall('s:c', ns):
                        value = cell.find('s:v', ns)
                        text = value.text if value is not None else ''.join(cell.itertext())
                        if cell.get('t') == 's' and text is not None:
                            text = strings[int(text)]
                        values.append(cell.get('r', '') + '=' + str(text or ''))
                    rows.append(' | '.join(values))
                result.append(('XLSX ' + name, '\n'.join(rows)))
            return result
    if suffix == '.pdf':
        from pypdf import PdfReader
        if blob is None:
            with path.open('rb') as f:
                if f.read(5) != b'%PDF-':
                    raise ValueError('Not a PDF signature')
        elif not blob.startswith(b'%PDF-'):
            raise ValueError('Not a PDF signature')
        document = PdfReader(io.BytesIO(blob) if blob is not None else path)
        return [('PDF p' + str(i + 1), page.extract_text() or '') for i, page in enumerate(document.pages)]
    text = blob.decode('utf-8-sig', errors='replace') if blob is not None else path.read_text(encoding='utf-8-sig', errors='replace')
    if suffix == '.xml':
        article = ET.fromstring(text)
        # Preserve sections/table location; extraction candidates remain unreviewed.
        sections = article.findall('.//sec') or [article]
        return [('XML section ' + str(i + 1), ' '.join(s.itertext())) for i, s in enumerate(sections)]
    if suffix in ['.html', '.htm']:
        parser = TextHTML(); parser.feed(text)
        return [('HTML full native text', ' '.join(parser.text))]
    if suffix in ['.txt', '.csv', '.tsv']:
        return [('Native tabular/text SI', text)]
    raise ValueError('Non-native attachment; never decode binary assets as experimental text')


def main():
    OUT.mkdir(exist_ok=True)
    path = OUT / 'full_corpus_search_native.sqlite'
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA foreign_keys=ON')
    con.executescript('''
    CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY,value_json TEXT);
    CREATE TABLE IF NOT EXISTS sources(sha256 TEXT PRIMARY KEY,format TEXT,path TEXT,provider TEXT,scan_state TEXT,segments INTEGER,text_chars INTEGER,error TEXT);
    CREATE TABLE IF NOT EXISTS locations(sha256 TEXT,path TEXT,PRIMARY KEY(sha256,path));
    CREATE TABLE IF NOT EXISTS identities(identity_key TEXT PRIMARY KEY,doi TEXT,title TEXT,basis TEXT);
    CREATE TABLE IF NOT EXISTS identity_sources(identity_key TEXT,sha256 TEXT,role TEXT,basis TEXT,PRIMARY KEY(identity_key,sha256,role));
    CREATE TABLE IF NOT EXISTS evidence_hits(hit_id INTEGER PRIMARY KEY,sha256 TEXT NOT NULL REFERENCES sources(sha256),locator TEXT,theme TEXT,excerpt TEXT,context_role TEXT,status TEXT NOT NULL DEFAULT 'automatic_unreviewed',training_eligible INTEGER NOT NULL DEFAULT 0 CHECK(training_eligible=0),excerpt_sha256 TEXT NOT NULL,UNIQUE(sha256,locator,theme,excerpt_sha256));
    CREATE TABLE IF NOT EXISTS new_native_segments(sha256 TEXT,locator TEXT,text TEXT,PRIMARY KEY(sha256,locator));
    CREATE VIRTUAL TABLE IF NOT EXISTS hit_search USING fts5(excerpt,theme,content='evidence_hits',content_rowid='hit_id');
    ''')
    status = con.execute("select value_json from metadata where key='complete'").fetchone()
    if status and json.loads(status[0]):
        raise FileExistsError('Completed full-corpus search is immutable; do not rerun.')
    pointer = read(ROOT / 'data/current_database.json')
    stored = con.execute("select value_json from metadata where key='baseline_pointer'").fetchone()
    if stored and json.loads(stored[0]) != pointer:
        raise RuntimeError('Baseline changed during this review.')
    con.execute('insert or ignore into metadata values(?,?)', ('baseline_pointer', json.dumps(pointer, ensure_ascii=False)))
    sources = {}; inherited = {}; identity_map = {}; links = set()

    def identity(key, doi=None, title='', basis='existing_registry'):
        if not key:
            key = 'doi:' + canonical(doi)
        identity_map.setdefault(key, {'doi': canonical(doi), 'title': title, 'basis': basis})
        return key

    def source(sha, fmt, location=None):
        item = sources.setdefault(sha, {'format': fmt, 'paths': set()})
        if location:
            p = Path(str(location).replace('\\\\', '\\'))
            if not p.is_absolute(): p = ROOT / p
            item['paths'].add(str(p))
        return item

    with open_database() as db:
        baseline_rows = db.fetch('all_review').rows
        for r in db.conn.execute('select * from literature_registry'):
            identity(r['identity_key'], r['doi'], r['title'])
        for r in db.conn.execute('select * from document_sources'):
            source(r['sha256'], r['format'])
        for r in db.conn.execute('select * from document_locations'):
            source(r['source_id'], sources[r['source_id']]['format'], r['path'])
        for r in db.conn.execute('select * from paper_documents'):
            links.add((r['identity_key'], r['source_id'], r['role'], r['basis']))
        for r in db.conn.execute('select source_id,locator,text from source_segments order by segment_id'):
            inherited.setdefault(r['source_id'], []).append((r['locator'], r['text']))
        for r in db.conn.execute('select * from candidate_sources_v07'):
            meta = json.loads(r['metadata_json']); sha = meta['sha256']
            key = identity(r['existing_identity'] or 'doi:' + canonical(r['doi']), r['doi'], r['title'], 'v07_candidate_metadata')
            source(sha, 'xml'); links.add((key, sha, 'main', 'v07_candidate_metadata'))
            inherited.setdefault(sha, [(s['locator'], s['text']) for s in db.conn.execute('select locator,text from candidate_source_segments_v07 where pmcid=? order by ordinal', (r['pmcid'],))])
        for r in db.incoming_sources():
            key = identity(r.get('existing_identity') or r['source_group'], r['doi'], r['title'], 'v08_provided_document')
            source(r['sha256'], 'pdf', r['storage_path']); links.add((key, r['sha256'], 'main', 'v08_identity_review'))
            inherited.setdefault(r['sha256'], [('PDF p' + str(s['page_number']), s['text']) for s in db.conn.execute('select page_number,text from incoming_pages_v08 where document_id=? order by page_number', (r['document_id'],))])
        acquisition = read(ROOT / '文献扩充_大批补齐_20261018/master_index.json')
        for r in acquisition:
            key = identity(r.get('existing_identity') or 'doi:' + canonical(r['doi']), r['doi'], r.get('title', ''), 'acquisition_catalog_not_scientific_admission')
            for f in r.get('files', []):
                if isinstance(f, dict) and f.get('path') and f.get('sha256'):
                    p = ROOT / f['path']; source(f['sha256'], p.suffix.lstrip('.'), p)
                    links.add((key, f['sha256'], f.get('component', 'unreviewed_component'), 'acquisition_metadata'))

        files = subprocess.check_output(['rg', '--files', '-g', '*.pdf', '-g', '*.xml', '-g', 'readable_article.html'], cwd=ROOT, text=True, encoding='utf-8').splitlines()
        for i, name in enumerate(files, 1):
            p = ROOT / name; sha = digest(p); source(sha, p.suffix.lstrip('.'), p)
            if i % 30 == 0 or i == len(files):
                write(OUT / 'progress.json', {'phase': 'inventory_sha', 'completed': i, 'total': len(files), 'original_files_changed': 0, 'training_fits': 0})
        for key, item in identity_map.items():
            con.execute('insert or ignore into identities values(?,?,?,?)', (key, item['doi'], item['title'], item['basis']))
        for args in links:
            con.execute('insert or ignore into identity_sources values(?,?,?,?)', args)
        con.commit()

        for number, (sha, info) in enumerate(sorted(sources.items()), 1):
            paths = sorted(info['paths'], key=lambda s: (not str(s).startswith(str(ROOT)), len(s)))
            original = next((Path(p) for p in paths if Path(p).is_file()), None)
            for p in paths:
                con.execute('insert or ignore into locations values(?,?)', (sha, p))
            done = con.execute('select scan_state from sources where sha256=?', (sha,)).fetchone()
            if done and done[0] == 'native_text_searched':
                continue
            provider = 'immutable_existing_segments' if sha in inherited else 'new_original_parse'
            con.execute('insert or replace into sources values(?,?,?,?,?,?,?,?)', (sha, info['format'], str(original) if original else None, provider, 'in_progress', 0, 0, None))
            try:
                if original and digest(original) != sha:
                    raise ValueError('Original hash mismatch')
                if sha not in inherited and info['format'].lower() not in ['pdf', 'xml', 'html', 'htm', 'docx', 'xlsx', 'zip', 'csv', 'tsv', 'txt']:
                    con.execute('update sources set scan_state=?,segments=0,text_chars=0 where sha256=?', ('nontext_asset_or_acquisition_metadata_not_experimental_text', sha))
                    con.commit()
                    continue
                segments = inherited.get(sha)
                if segments is None:
                    if not original:
                        raise FileNotFoundError('No accessible original or inherited text')
                    segments = parse_original(original)
                    for locator, text in segments:
                        con.execute('insert or replace into new_native_segments values(?,?,?)', (sha, locator, text))
                    first = segments[0][1][:7000] if segments else ''
                    matches = list(dict.fromkeys(re.findall(r'(?:doi\.org/|DOI[:\s]+)(10\.\d{4,9}/[^\s<>]+)', first, re.I)))
                    if len(matches) == 1:
                        doi = canonical(matches[0]); key = 'doi:' + doi
                        con.execute('insert or ignore into identities values(?,?,?,?)', (key, doi, '', 'first_page_doi_candidate_not_identity_reviewed'))
                        con.execute('insert or ignore into identity_sources values(?,?,?,?)', (key, sha, 'component_unreviewed', 'first_page_doi_candidate'))
                chars = sum(len(t) for _, t in segments)
                for locator, text in segments:
                    for theme, pattern in PATTERNS.items():
                        starts = []
                        for match in pattern.finditer(text):
                            if any(abs(match.start() - start) < 500 for start in starts):
                                continue
                            starts.append(match.start())
                            excerpt = text[max(0, match.start() - 220):match.start() + 850]
                            context = 'possible_reference_or_comparison' if re.search(r'REFERENCES|Table\s+\d.{0,30}comparison', text[:max(0, match.start())], re.I) else 'native_context_not_scientifically_bound'
                            con.execute('insert or ignore into evidence_hits(sha256,locator,theme,excerpt,context_role,excerpt_sha256) values(?,?,?,?,?,?)', (sha, locator, theme, excerpt, context, hashlib.sha256(excerpt.encode()).hexdigest()))
                            if len(starts) >= 8:
                                break
                state = 'native_text_searched' if chars >= 100 else 'insufficient_native_text_needs_visual_or_ocr'
                con.execute('update sources set scan_state=?,segments=?,text_chars=?,error=NULL where sha256=?', (state, len(segments), chars, sha))
            except Exception as exc:
                con.execute('update sources set scan_state=?,error=? where sha256=?', ('access_or_parse_unresolved', type(exc).__name__ + ': ' + str(exc)[:500], sha))
            con.commit()
            write(OUT / 'progress.json', {'phase': 'full_corpus_native_search', 'completed': number, 'total': len(sources), 'original_files_changed': 0, 'automatic_admissions': 0, 'training_fits': 0})
            if number % 20 == 0:
                print(json.dumps({'searched_sources': number, 'total': len(sources)}, ensure_ascii=False), flush=True)
        con.execute("insert into hit_search(hit_search) values('rebuild')")
        con.execute('insert or replace into metadata values(?,?)', ('complete', 'true'))
        con.execute('insert or replace into metadata values(?,?)', ('scope', json.dumps({'sources': 'All inherited sources plus all rg-visible PDF/XML/readable_article.html originals; native text only is not full figure/SI scientific review.', 'scientific_admissions': 0, 'new_fits': 0})))
        con.commit()
        assert db.fetch('all_review').rows == baseline_rows
    summary = {'physical_native_files_inventoried': len(files), 'unique_source_contents': len(sources),
               'source_states': dict(con.execute('select scan_state,count(*) from sources group by scan_state')),
               'catalog_identities': con.execute('select count(*) from identities').fetchone()[0],
               'automatic_unreviewed_hits': con.execute('select count(*) from evidence_hits').fetchone()[0],
               'topics': dict(con.execute('select theme,count(*) from evidence_hits group by theme')),
               'automatic_admissions': 0, 'training_fits': 0, 'baseline_unchanged': True}
    with (OUT / '逐来源检索覆盖.csv').open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f); w.writerow(['identity_key', 'doi', 'title', 'identity_basis', 'linked_source_contents', 'native_text_searched_sources', 'automatic_unreviewed_hits'])
        w.writerows(con.execute('''select i.identity_key,i.doi,i.title,i.basis,count(distinct s.sha256),count(distinct case when s.scan_state='native_text_searched' then s.sha256 end),count(distinct h.hit_id) from identities i left join identity_sources l using(identity_key) left join sources s on s.sha256=l.sha256 left join evidence_hits h on h.sha256=s.sha256 group by i.identity_key order by i.identity_key'''))
    assert con.execute('pragma integrity_check').fetchone()[0] == 'ok'
    assert not con.execute('pragma foreign_key_check').fetchall()
    assert con.execute('select count(*) from evidence_hits where training_eligible!=0').fetchone()[0] == 0
    con.close()
    write(OUT / 'search_summary.json', summary)
    write(OUT / 'progress.json', {'phase': 'native_search_complete_manual_curation_running', 'completed': len(sources), 'total': len(sources), **summary})
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)


if __name__ == '__main__':
    main()
