"""Local, byte-preserving PDF intake. Classification/admission are separate.

Creates a new batch only; reads ZIP members in memory and never extracts paths
from untrusted archives. Reuses exact Git-tracked PDF bytes where possible.
"""
from pathlib import Path, PurePosixPath
import argparse, collections, concurrent.futures, hashlib, io, json, logging
import os, re, sqlite3, subprocess, zipfile
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
logging.getLogger('pypdf').setLevel(logging.ERROR)


def sha(blob):
    return hashlib.sha256(blob).hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


def git(*args):
    env = os.environ.copy()
    env['GIT_OPTIONAL_LOCKS'] = '0'
    r = subprocess.run(['git','-c','safe.directory='+ROOT.as_posix(),*args],capture_output=True,env=env)
    if r.returncode:
        raise RuntimeError('Git read failed: '+str(r.returncode))
    return r.stdout


def run(folder, output, date):
    folder, output = folder.resolve(), output.resolve()
    if ROOT not in output.parents or output.exists():
        raise RuntimeError('A new batch directory inside this repository is required')
    inputs = []
    entries = []
    unique = {}
    # Entire input receipt is created before any output; only declared PDFs and
    # ZIPs are processed, without deleting or changing the original folder.
    for p in sorted(folder.rglob('*')):
        if not p.is_file():
            continue
        if p.is_symlink():
            raise ValueError('Input symlink requires explicit review')
        body = p.read_bytes()
        info = {'path':str(p),'sha256':sha(body),'bytes':len(body)}
        inputs.append(info)
        if p.suffix.lower()=='.pdf':
            chunks = [(None, body)]
        elif p.suffix.lower()=='.zip':
            chunks = []
            with zipfile.ZipFile(io.BytesIO(body)) as z:
                for m in z.infolist():
                    name = PurePosixPath(m.filename.replace('\\','/'))
                    if name.is_absolute() or '..' in name.parts or ((m.external_attr>>16)&0o170000)==0o120000:
                        raise ValueError('Unsafe archive member')
                    if m.is_dir():
                        continue
                    if m.file_size>100_000_000:
                        raise ValueError('Oversize member requires explicit review')
                    if name.suffix.lower()!='.pdf':
                        raise ValueError('Non-PDF archive member requires explicit review')
                    chunks.append((m.filename,z.read(m)))
        else:
            raise ValueError('Unexpected input type: '+p.name)
        for member, blob in chunks:
            h = sha(blob)
            location = {'input_path':str(p),'archive_member':member,'filename':PurePosixPath(member).name if member else p.name,'sha256':h,'bytes':len(blob)}
            entries.append(location)
            unique.setdefault(h, {'body':blob,'locations':[]})['locations'].append(location)
    output.mkdir()
    dump(output/'input_manifest.json',{'date':date,'input_directory':str(folder),'input_files':inputs,'document_occurrences':entries,'originals_preserved':True,'archive_policy':'Original ZIP remains at input path; deliver its PDF members as directly readable originals, without a second archive copy.'})
    existing = collections.defaultdict(list)
    lfs = json.loads(git('lfs','ls-files','--json'))['files']
    for f in lfs:
        if f['name'].lower().endswith('.pdf'):
            existing[f['oid'].removeprefix('sha256:')].append(f['name'])
    work = []
    for i, (h,r) in enumerate(unique.items(),1):
        source = next((s for s in existing[h] if (ROOT/s).is_file() and sha((ROOT/s).read_bytes())==h),None)
        docid = 'ADD_'+str(i).zfill(3)
        if source is None:
            p = output/'originals'/(docid+'.pdf')
            p.parent.mkdir(exist_ok=True)
            with p.open('xb') as f:
                f.write(r['body'])
            source = p.relative_to(ROOT).as_posix()
            status = 'new_direct_original_bytes'
        else:
            status = 'reused_exact_existing_direct_PDF'
        work.append({'document_id':docid,'sha256':h,'bytes':len(r['body']),'repository_path':source,'storage_status':status,'input_locations':r['locations']})
    db = sqlite3.connect(output/'batch.sqlite')
    db.executescript('''
      PRAGMA foreign_keys=ON;
      CREATE TABLE documents(document_id TEXT PRIMARY KEY,sha256 TEXT UNIQUE NOT NULL,bytes INTEGER,repository_path TEXT NOT NULL,storage_status TEXT,parse_status TEXT,page_count INTEGER,text_characters INTEGER,first_page_dois_json TEXT,pdf_metadata_json TEXT);
      CREATE TABLE input_locations(document_id TEXT REFERENCES documents,input_path TEXT,archive_member TEXT,filename TEXT);
      CREATE TABLE pages(document_id TEXT REFERENCES documents,page_number INTEGER,text TEXT,PRIMARY KEY(document_id,page_number));
      CREATE VIRTUAL TABLE page_search USING fts5(document_id UNINDEXED,page_number UNINDEXED,text);
      CREATE TABLE batch_meta(key TEXT PRIMARY KEY,value_json TEXT);
    ''')
    def parse(r):
        reader = PdfReader(ROOT/r['repository_path'])
        pages = []
        error = None
        try:
            for page in reader.pages:
                pages.append((page.extract_text() or '').replace('\x00',''))
        except Exception as exc:
            error = type(exc).__name__+': '+str(exc)[:300]
        first = '\n'.join(pages[:2])
        first_page_dois = list(dict.fromkeys(x.rstrip('.,;:') for x in re.findall(r'10\.\d{4,9}/[-._;()/:a-z0-9]+',first,re.I)))
        meta = {str(k):str(v) for k,v in (reader.metadata or {}).items() if k in ['/Title','/Subject','/Creator','/Producer','/doi','/DOI']}
        return r, pages, error, first_page_dois, meta
    summaries = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for r, pages, error, dois, meta in pool.map(parse,work):
            chars = sum(len(t) for t in pages)
            status = 'parsed' if chars>100 and not error else 'parse_partial' if chars>100 else 'needs_visual_or_OCR'
            db.execute('INSERT INTO documents VALUES (?,?,?,?,?,?,?,?,?,?)',(r['document_id'],r['sha256'],r['bytes'],r['repository_path'],r['storage_status'],status,len(pages),chars,json.dumps(dois),json.dumps(meta,ensure_ascii=False)))
            db.executemany('INSERT INTO input_locations VALUES (?,?,?,?)',[(r['document_id'],a['input_path'],a['archive_member'],a['filename']) for a in r['input_locations']])
            db.executemany('INSERT INTO pages VALUES (?,?,?)',[(r['document_id'],i,t) for i,t in enumerate(pages,1)])
            db.executemany('INSERT INTO page_search VALUES (?,?,?)',[(r['document_id'],i,t) for i,t in enumerate(pages,1)])
            summaries.append({**r,'parse_status':status,'parse_error':error,'page_count':len(pages),'text_characters':chars,'first_page_dois':dois,'pdf_metadata':meta,'first_page_preview':pages[0][:2400] if pages else ''})
            print(r['document_id'],len(pages),chars,status,flush=True)
            db.commit()
    meta={'date':date,'input_files':len(inputs),'PDF_occurrences':len(entries),'unique_PDFs':len(work),'stored_new_originals':sum(r['storage_status']=='new_direct_original_bytes' for r in work),'reused_existing_originals':sum(r['storage_status']!='new_direct_original_bytes' for r in work),'research_fits':0,'training_admissions_added':0,'phase':'intake_only_not_classification_or_admission'}
    db.executemany('INSERT INTO batch_meta VALUES (?,?)',[(k,json.dumps(v,ensure_ascii=False)) for k,v in meta.items()])
    db.commit()
    assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    assert not db.execute('PRAGMA foreign_key_check').fetchall()
    db.close()
    dump(output/'intake_index.json',summaries)
    dump(output/'intake_summary.json',meta)
    print(json.dumps(meta,ensure_ascii=False),flush=True)


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--input',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--date',required=True)
    a=ap.parse_args()
    run(a.input,a.output,a.date)
