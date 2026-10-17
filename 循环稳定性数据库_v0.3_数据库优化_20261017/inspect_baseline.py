"""One-time v0.3 evidence inventory; never run legacy migration scripts."""
from pathlib import Path
import hashlib, json, sqlite3, zipfile, re
from pypdf import PdfReader
from xml.etree import ElementTree as ET

ROOT=Path(__file__).resolve().parent
BASE=ROOT.parent/'循环稳定性数据库_v0.2_20261017'
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,obj): p.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
def main():
    target=ROOT/'cycling_v0_3.sqlite'
    if target.exists(): raise RuntimeError('Revision already exists. Do not overwrite.')
    contract=json.loads((ROOT.parent/'并行协作契约_v1_20261017.json').read_text(encoding='utf-8-sig'))
    assert sha(BASE/'cycling_v0_2.sqlite')==contract['baseline']['database_sha256']
    assert sha(BASE/'modeling/model_contract.json')==contract['baseline']['model_contract_sha256']
    c=sqlite3.connect((BASE/'cycling_v0_2.sqlite').as_uri()+'?mode=ro',uri=True); c.row_factory=sqlite3.Row
    with sqlite3.connect(target) as dest: c.backup(dest)
    protected={}
    for p in BASE.rglob('*'):
        if p.is_file() and '.venv' not in p.parts and '__pycache__' not in p.parts: protected[str(p)]=sha(p)
    old=ROOT.parent/'循环稳定性数据库_v0.1_20261017'
    for p in old.rglob('*'):
        if p.is_file() and '.venv' not in p.parts and '__pycache__' not in p.parts: protected[str(p)]=sha(p)
    for table in ['source_files','ingestion_sources']:
        for r in c.execute('SELECT path,sha256 FROM '+table):
            assert sha(r['path'])==r['sha256'],r['path']
            protected[r['path']]=r['sha256']
    for name in ['并行协作契约_v1_20261017.json','双对话任务安排_20261017.md','NEXT_CHAT_20261017_v02首批优化后.md']:
        protected[str(ROOT.parent/name)]=sha(ROOT.parent/name)
    save(ROOT/'baseline_fingerprints.json',{'baseline_database_sha256':sha(BASE/'cycling_v0_2.sqlite'),'protected_files':protected})
    for folder in ['evidence_text','evidence_images','exports','modeling']: (ROOT/folder).mkdir(exist_ok=True)
    papers={r[0] for r in c.execute("SELECT DISTINCT paper_id FROM endpoint_review WHERE system LIKE '2E%' OR system='system_pending'")}
    inventory=[]
    for r in c.execute('SELECT * FROM source_files ORDER BY paper_id,role'):
        if r['paper_id'] not in papers: continue
        r=dict(r); p=Path(r['path']); out=ROOT/'evidence_text'/f"{r['paper_id']}_{r['role']}.json"
        try:
            if r['format']=='pdf' or p.suffix.lower()=='.pdf':
                pages=[{'page':i+1,'text':page.extract_text() or ''} for i,page in enumerate(PdfReader(p).pages)]
            elif p.suffix.lower()=='.docx':
                with zipfile.ZipFile(p) as z: el=ET.fromstring(z.read('word/document.xml'))
                ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
                pages=[{'page':None,'text':'\n'.join(''.join(x.itertext()) for x in el.findall('.//w:p',ns))}]
            elif p.suffix.lower()=='.txt':
                pages=[{'page':None,'text':p.read_text(encoding='utf-8-sig')}]
            else:
                el=ET.parse(p).getroot(); pages=[{'page':None,'text':'\n'.join(el.itertext())}]
            save(out,pages);r['extraction_path']=str(out);r['extraction_sha256']=sha(out)
        except Exception as e:r['extraction_error']=str(e)
        inventory.append(r)
    save(ROOT/'source_inventory.json',inventory)
    save(ROOT/'baseline_profile.json',{'tables':{r[0]:c.execute('select count(*) from '+r[0]).fetchone()[0] for r in c.execute("select name from sqlite_master where type='table'").fetchall()},'endpoint_rows':[dict(r) for r in c.execute('select * from endpoint_review')],'issues':[dict(r) for r in c.execute('select * from issues')],'relationships':[dict(r) for r in c.execute('select * from source_relationships')]})
    print(json.dumps({'protected_files':len(protected),'extracted_sources':len(inventory),'errors':[r for r in inventory if 'extraction_error' in r]},ensure_ascii=False))
if __name__=='__main__':main()
