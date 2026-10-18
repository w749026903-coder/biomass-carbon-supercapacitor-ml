"""Index existing local primary sources and SI. No downloads or estimator calls."""
from pathlib import Path
import collections,datetime,hashlib,json,logging,re,sqlite3,sys,xml.etree.ElementTree as ET
from pypdf import PdfReader
R=Path(__file__).resolve().parents[1];O=R/'循环稳定性数据库_v0.4_提取与调用_20261018';P=R/'循环稳定性数据库_v0.3_合并版_20261017'
def js(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def enc(x):return json.dumps(x,ensure_ascii=False)
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def tag(e):return e.tag.split('}')[-1]
def text(e):return re.sub(r'\s+',' ',' '.join(e.itertext())).strip()
def main():
 db=O/'cycling_v0_4.sqlite'
 if db.exists():raise RuntimeError('New version only; database exists')
 parent=sqlite3.connect((P/'cycling_v0_3_merged.sqlite').as_uri()+'?mode=ro',uri=True);parent.row_factory=sqlite3.Row
 c=sqlite3.connect(db);c.row_factory=sqlite3.Row;parent.backup(c);c.execute('pragma foreign_keys=ON')
 c.executescript('''
 CREATE TABLE extraction_run(key TEXT PRIMARY KEY,value_json TEXT NOT NULL);
 CREATE TABLE document_sources(source_id TEXT PRIMARY KEY,sha256 TEXT NOT NULL UNIQUE,format TEXT,parse_status TEXT,parse_error TEXT,segment_count INTEGER,text_characters INTEGER);
 CREATE TABLE document_locations(source_id TEXT REFERENCES document_sources,path TEXT,PRIMARY KEY(source_id,path));
 CREATE TABLE paper_documents(identity_key TEXT REFERENCES literature_registry,source_id TEXT REFERENCES document_sources,role TEXT,basis TEXT,PRIMARY KEY(identity_key,source_id,role));
 CREATE TABLE source_segments(segment_id INTEGER PRIMARY KEY,source_id TEXT REFERENCES document_sources,locator TEXT NOT NULL,section_kind TEXT NOT NULL,text TEXT NOT NULL,UNIQUE(source_id,locator));
 CREATE VIRTUAL TABLE source_search USING fts5(text,content='source_segments',content_rowid='segment_id');
 CREATE TABLE extraction_queue(identity_key TEXT PRIMARY KEY REFERENCES literature_registry,priority INTEGER,document_type TEXT,main_source_id TEXT REFERENCES document_sources,status TEXT NOT NULL,reason TEXT NOT NULL);
 CREATE TABLE extraction_leads(lead_id INTEGER PRIMARY KEY,identity_key TEXT REFERENCES literature_registry,source_id TEXT REFERENCES document_sources,segment_id INTEGER REFERENCES source_segments,lead_kind TEXT,claim_status TEXT,excerpt TEXT);
 ''')
 c.executemany('insert into extraction_run values (?,?)',[(k,enc(v)) for k,v in {'parent_database_sha256':sha(P/'cycling_v0_3_merged.sqlite'),'created_at':datetime.datetime.now().isoformat(),'research_training_authorized':False,'source_scope':'existing_local_226_registry_identities','phase':'source_indexing'}.items()])
 candidates=collections.defaultdict(dict);types={}
 def add(identity,path,role,basis):
  if not isinstance(path,str) or not path:return
  q=Path(path);q=q if q.is_absolute() else R/q
  if q.suffix.lower() not in ('.pdf','.xml','.docx') or not q.is_file():return
  candidates[identity][(str(q.resolve()),role)]=basis
 for row in parent.execute('select * from literature_observations'):
  x=json.loads(row['source_json']);identity=row['identity_key'];batch=row['batch']
  for k in ['main_path','repository_pdf','repository_source','source_path']:add(identity,x.get(k),'main',batch+':'+k)
  for q in x.get('complete_main_files',[]):add(identity,q,'main',batch+':complete_main_files')
  if isinstance(x.get('fulltext'),dict):add(identity,x['fulltext'].get('path'),'main',batch+':fulltext')
  for v in x.get('source_versions',[]):add(identity,v.get('path'),'main',batch+':version')
  for v in x.get('portable_source_locations',[]):
   if v.get('kind')=='repository_file':add(identity,v.get('path'),'main',batch+':portable')
  if x.get('document_type'):types[identity]=x['document_type']
  supp=x.get('supplements',{});supp=supp.get('paths',[]) if isinstance(supp,dict) else []
  for v in supp+x.get('supporting_documents_obtained',[])+x.get('supplement_sources',[]):
   if isinstance(v,str):add(identity,v,'SI',batch+':supplement')
   elif isinstance(v,dict):
    for k in ['path','local_path','source_path','file']:add(identity,v.get(k),'SI',batch+':supplement')
 for x in parent.execute('select s.*,p.doi from source_files s join papers p using(paper_id)'):
  ident=parent.execute("select identity_key from literature_observations where batch='archived_126' and local_id=?",(x['paper_id'],)).fetchone()[0];add(ident,x['path'],x['role'],'legacy_source_files')
 for x in parent.execute('select * from staged_cycling_evidence'):add(x['identity_key'],x['source_file'],'main','3E_endpoint_source')
 parsed={};logging.getLogger('pypdf').setLevel(logging.ERROR);originals={};n=0
 def parse(path):
  digest=sha(path);originals[str(path)]=digest
  if digest in parsed:return digest
  segments=[];error=None
  try:
   if path.suffix.lower()=='.pdf':
    reader=PdfReader(path)
    for i,page in enumerate(reader.pages,1):segments.append((f'PDF p{i}','page',(page.extract_text() or '').replace('\x00','�')))
   elif path.suffix.lower()=='.docx':
    import zipfile
    with zipfile.ZipFile(path) as z:root=ET.fromstring(z.read('word/document.xml'))
    segments=[(f'DOCX paragraph {i}','paragraph',text(e)) for i,e in enumerate((e for e in root.iter() if tag(e)=='p'),1)]
   else:
    root=ET.parse(path).getroot();body=next((e for e in root.iter() if tag(e)=='body'),None)
    if body is None:raise ValueError('XML has no body; metadata is not full text')
    for i,e in enumerate((e for e in body.iter() if tag(e) in ('p','table-wrap','fig')),1):
     if not text(e):continue
     segments.append((f'XML {tag(e)} {e.get("id") or i}',tag(e),text(e)))
    known={v[0] for v in segments}
    for e in root.iter():
     if tag(e) in ('table-wrap','fig') and e.get('id'):
      loc=f'XML {tag(e)} {e.get("id")}'
      if loc not in known:segments.append((loc,tag(e),text(e)));known.add(loc)
   segments=[s for s in segments if s[2].strip()]
  except Exception as exc:error=type(exc).__name__+': '+str(exc)[:500]
  c.execute('insert into document_sources values (?,?,?,?,?,?,?)',(digest,digest,path.suffix.lower()[1:],'parsed' if segments and not error else 'parse_failed',error,len(segments),sum(len(s[2]) for s in segments)))
  c.executemany('insert into source_segments(source_id,locator,section_kind,text) values (?,?,?,?)',[(digest,*s) for s in segments]);parsed[digest]=digest
  return digest
 for identity,items in candidates.items():
  for (name,role),basis in items.items():
   path=Path(name);sid=parse(path)
   c.execute('insert or ignore into document_locations values (?,?)',(sid,str(path.relative_to(R)) if R in path.parents else str(path)))
   c.execute('insert or ignore into paper_documents values (?,?,?,?)',(identity,sid,role,basis))
  n+=1
  if n%20==0:print('Indexed identities',n,'documents',len(parsed),flush=True);c.commit()
 c.execute("insert into source_search(source_search) values ('rebuild')")
 for row in parent.execute('select * from literature_registry'):
  identity=row['identity_key'];dtype=types.get(identity,'unclassified_candidate');sources=c.execute("select d.* from paper_documents p join document_sources d using(source_id) where identity_key=? and role='main' and parse_status='parsed' order by case d.format when 'xml' then 0 else 1 end,text_characters desc",(identity,)).fetchall()
  stage3=parent.execute('select count(*) from staged_cycling_evidence where identity_key=?',(identity,)).fetchone()[0]
  relevant='原始实验' in dtype or dtype=='unclassified_candidate'
  state='indexed_target_review_pending' if sources and relevant else 'indexed_background_separate' if sources else 'complete_main_unavailable_or_parse_failed'
  sid=sources[0]['source_id'] if sources else None
  c.execute('insert into extraction_queue values (?,?,?,?,?,?)',(identity,1 if stage3 else 2 if relevant else 3,dtype,sid,state,'Full text indexed; semantic extraction and record admission are separate.' if sources else 'No parseable complete main file among declared local sources.'))
  if sid and relevant:
   for s in c.execute('select * from source_segments where source_id=?',(sid,)).fetchall():
    if re.search(r'cycl(?:ing|ability|e stability)|capacitance retention|retained.*capacitance',s['text'],re.I):
     c.execute('insert into extraction_leads(identity_key,source_id,segment_id,lead_kind,claim_status,excerpt) values (?,?,?,?,?,?)',(identity,sid,s['segment_id'],'cycling_candidate_passage','machine_located_not_semantically_admitted',s['text'][:2500]))
 c.executescript('CREATE INDEX idx_paper_docs_identity ON paper_documents(identity_key,role);CREATE INDEX idx_segments_source ON source_segments(source_id);CREATE INDEX idx_leads_identity ON extraction_leads(identity_key);CREATE INDEX idx_queue_priority ON extraction_queue(priority,status);')
 c.commit();summary={'identities':parent.execute('select count(*) from literature_registry').fetchone()[0],'documents':len(parsed),'segments':c.execute('select count(*) from source_segments').fetchone()[0],'queue':[{k:v for k,v in dict(x).items()} for x in c.execute('select status,count(*) as count from extraction_queue group by status')],'original_files':len(originals),'research_fits':0}
 (O/'来源索引结果.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');(O/'本轮读取原件指纹.json').write_text(json.dumps([{'path':k,'sha256':v} for k,v in originals.items()],ensure_ascii=False,indent=2)+'\n',encoding='utf-8');c.close();parent.close();print(enc(summary),flush=True)
if __name__=='__main__':main()
