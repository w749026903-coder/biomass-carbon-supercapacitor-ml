"""Read local primary/SI sources for the fixed v0.14 cohort and pending queue.

No scientific values or admission decisions are inferred by this retrieval tool.
The snapshot records identities and hashes; text is read from existing originals.
"""
from pathlib import Path
import argparse, collections, hashlib, json, re, sqlite3, sys, xml.etree.ElementTree as ET, zipfile
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from data.cycling_db import open_database
BATCH = ROOT / '已有文献表图与41条复核_20261024'
SNAPSHOT = BATCH / 'baseline_inventory.json'

def read(p): return json.loads(p.read_text('utf-8'))
def sha(p):
    with p.open('rb') as f: return hashlib.file_digest(f, 'sha256').hexdigest()
def norm(x): return x.lower().removeprefix('doi:')
def segments(source):
    p = Path(source['path'])
    if not p.is_absolute(): p = ROOT / p
    assert sha(p) == source['sha256'], p
    if p.suffix.lower() == '.pdf':
        import pypdfium2 as P
        doc = P.PdfDocument(p)
        for i in range(len(doc)):
            pg=doc[i]; tp=pg.get_textpage(); text=tp.get_text_range(); tp.close(); pg.close()
            yield f'PDF p{i+1}', text
        doc.close()
    elif p.suffix.lower() == '.xml':
        root=ET.fromstring(p.read_bytes())
        for i, el in enumerate(root.iter('table-wrap'),1):
            text=' '.join(' '.join(el.itertext()).split())
            rows=[' | '.join(' '.join(' '.join(c.itertext()).split()) for c in tr if c.tag in ('th','td')) for tr in el.iter('tr')]
            yield f'XML table-wrap {i} id={el.get("id")}', text+'\n'+'\n'.join(rows)
        for i, el in enumerate(root.iter('p'),1):
            if el.find('table-wrap') is None:
                yield f'XML p{i}', ' '.join(' '.join(el.itertext()).split())
        for i, el in enumerate(root.iter('fig'),1):
            yield f'XML fig{i} id={el.get("id")}', ' '.join(' '.join(el.itertext()).split())
    elif p.suffix.lower() == '.docx':
        with zipfile.ZipFile(p) as z: root=ET.fromstring(z.read('word/document.xml'))
        ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
        for i, el in enumerate(root.findall('.//w:tbl',ns),1):
            rows=[' | '.join(''.join(c.itertext()) for c in row.findall('w:tc',ns)) for row in el.findall('w:tr',ns)]
            yield f'DOCX table {i}', '\n'.join(rows)
        for i, el in enumerate(root.findall('.//w:p',ns),1):
            yield f'DOCX p{i}', ''.join(el.itertext())

def snapshot():
    if SNAPSHOT.exists(): raise FileExistsError(SNAPSHOT)
    pending=read(ROOT/'冲突复核与来源充分性_20261022/current_pending_records.json')
    with open_database() as db:
        assert db.contract['version']=='v0.14'
        main=db.fetch().rows; allrows={r['endpoint_id']:r for r in db.fetch('all_review').rows}
        allkeys={r['endpoint_id'] for r in main+pending}
        lookup={}
        for p in [ROOT/'待补证原文复核_20261022/effective_reviews.json',ROOT/'冲突复核与来源充分性_20261022/effective_reviews.json']:
            for c in read(p):
                if c['endpoint_id'] in allkeys:
                    for e in c['evidence']:
                        path=Path(e['path']); path=path if path.is_absolute() else ROOT/path
                        lookup[(norm(allrows[c['endpoint_id']]['source_group']),str(path.resolve()))]=e
        for r in main:
            for e in db.evidence(r['endpoint_id']):
                if not e.get('path'): continue
                path=Path(e['path']); path=path if path.is_absolute() else ROOT/path
                lookup[(norm(r['source_group']),str(path.resolve()))]=e
        c=sqlite3.connect((ROOT/'全库复检与特征补提取_20261021/full_corpus_search_native.sqlite').as_uri()+'?mode=ro',uri=True);c.row_factory=sqlite3.Row
        bydoi=collections.defaultdict(list)
        for r in main+pending: bydoi[norm(r['source_group'])].append(r['endpoint_id'])
        papers=[]
        for doi,keys in bydoi.items():
            identity=doi if doi.startswith('document:') else 'doi:'+doi
            files={}
            for s in c.execute("select s.*,i.role from sources s join identity_sources i using(sha256) where i.identity_key=? and s.format in ('pdf','xml','docx')",(identity,)):
                s=dict(s); files[s['sha256']]={k:s[k] for k in ['path','sha256','format','role']}
            for (d,p),e in lookup.items():
                if d!=doi or Path(p).suffix.lower() not in ('.pdf','.xml','.docx'):continue
                files[e['sha256']]=dict(path=p,sha256=e['sha256'],format=Path(p).suffix[1:],role='previous_direct_evidence')
            for f in files.values():
                path=Path(f['path']); path=path if path.is_absolute() else ROOT/path
                assert sha(path)==f['sha256']
                try:f['path']=path.relative_to(ROOT).as_posix()
                except ValueError:f['path']=str(path)
            papers.append(dict(doi=doi,endpoint_ids=sorted(set(keys)),sources=list(files.values())))
        c.close()
    BATCH.mkdir(exist_ok=True)
    result=dict(parent_pointer=read(ROOT/'data/current_database.json'),pending_count=len(pending),pending=pending,
        main_rows=main,all_rows=allrows,papers=papers,model_fits=0)
    SNAPSHOT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n','utf-8')
    print(json.dumps(dict(papers=len(papers),pending=41,main=42,original_files=sum(len(p['sources']) for p in papers)),ensure_ascii=False))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--snapshot',action='store_true');ap.add_argument('--doi',nargs='*');ap.add_argument('--pattern',default=r'BET|pore|XPS|atomic|nitrogen|oxygen|Raman|Table|cycling|retention|reference electrode');ap.add_argument('--tables',action='store_true');ap.add_argument('--all',action='store_true');ap.add_argument('--clip',type=int,default=0);ap.add_argument('--locator',default='');ap.add_argument('--brief',action='store_true');args=ap.parse_args()
    if args.snapshot:return snapshot()
    data=read(SNAPSHOT)
    for p in data['papers']:
        if args.doi and not any(x.lower() in p['doi'] for x in args.doi):continue
        print('\nDOI',p['doi'],'TESTS',p['endpoint_ids'])
        files=p['sources']
        if any(s['format']=='xml' for s in files):
            files=[s for s in files if s['format']!='pdf' or not any(n in Path(s['path']).name for n in ['main.pdf','正文','ADD_'])]
        for source in files:
            print('FILE',source['path'],source['sha256'])
            for loc,txt in segments(source):
                if args.locator and not re.search(args.locator,loc,re.I):continue
                if args.tables and 'table' not in loc.lower() and source['format']=='xml':continue
                if args.all or re.search(args.pattern,txt,re.I):
                    if args.brief:
                        m=re.search(args.pattern,txt,re.I);a=max(0,m.start()-70) if m else 0
                        print(loc,' '.join(txt[a:a+270].split()));continue
                    if args.clip and len(txt)>args.clip:
                        spans=[]
                        for m in re.finditer(args.pattern,txt,re.I):
                            a=max(0,m.start()-220);b=min(len(txt),m.end()+450)
                            if spans and a<=spans[-1][1]:spans[-1]=(spans[-1][0],b)
                            else:spans.append((a,b))
                        txt=' [...] '.join(' '.join(txt[a:b].split()) for a,b in spans)[:args.clip]
                    print(loc,txt)
if __name__=='__main__':main()
