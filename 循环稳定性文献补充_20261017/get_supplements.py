import concurrent.futures, hashlib, io, json, pathlib, urllib.parse, zipfile, xml.etree.ElementTree as ET
from pypdf import PdfReader
from collect_batch1 import ROOT, get
JOBS=[('N001','PMC12278731',None),('N002','PMC12794195',None),('N004','PMC12251455',None),('N005','PMC11722056',None),('已有_R103',None,'10.3390/molecules30010089'),('已有_R106',None,'10.3390/nano15080575')]
def run(job):
 ident,pmc,doi=job;folder=ROOT/ident;folder.mkdir(exist_ok=True);out={'id':ident,'doi':doi,'pdfs':[]}
 try:
  if not pmc:
   url='https://www.ebi.ac.uk/europepmc/webservices/rest/search?query='+urllib.parse.quote('DOI:'+doi)+'&format=json'
   raw,_,_=get(url);rs=json.loads(raw)['resultList']['result'];pmc=next(x['pmcid'] for x in rs if x.get('pmcid'));out['search_url']=url
  out['pmcid']=pmc
  if not (folder/'公开全文.xml').exists():
   raw,_,_=get('https://www.ebi.ac.uk/europepmc/webservices/rest/'+pmc+'/fullTextXML');ET.fromstring(raw);(folder/'公开全文.xml').write_bytes(raw)
  path=folder/'公开补充包.zip'
  u='https://www.ebi.ac.uk/europepmc/webservices/rest/'+pmc+'/supplementaryFiles';out['package_url']=u
  if not path.exists():
   raw,_,_=get(u)
   if not raw.startswith(b'PK'):raise ValueError('not a ZIP')
   path.write_bytes(raw)
  out['package_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
  with zipfile.ZipFile(path) as z:
   for entry in z.infolist():
    if entry.filename.lower().endswith(('.pdf','.zip','.docx')):
     raw=z.read(entry);name=pathlib.PurePosixPath(entry.filename).name;target=folder/name
     # Only selected regular attachments, flat basename, no arbitrary ZIP paths.
     if name.lower().endswith('.pdf'):
      if not raw.startswith(b'%PDF-'):raise ValueError('invalid PDF')
      reader=PdfReader(io.BytesIO(raw));texts=[{'page':i+1,'text':p.extract_text() or ''} for i,p in enumerate(reader.pages)]
      target.write_bytes(raw);target.with_suffix('.pages.json').write_text(json.dumps(texts,ensure_ascii=False,indent=2),encoding='utf-8')
      out['pdfs'].append({'path':str(target),'pages':len(texts),'sha256':hashlib.sha256(raw).hexdigest(),'member':entry.filename,'role':'supplement'})
     elif name.lower().endswith('.zip'):
      target.write_bytes(raw)
      with zipfile.ZipFile(io.BytesIO(raw)) as inner:
       out['nested_members']=[x.filename for x in inner.infolist()]
       for ent in inner.infolist():
        if ent.filename.lower().endswith('.pdf'):
         bb=inner.read(ent);rr=PdfReader(io.BytesIO(bb));tt=[{'page':i+1,'text':p.extract_text() or ''} for i,p in enumerate(rr.pages)];dest=folder/pathlib.PurePosixPath(ent.filename).name
         if not bb.startswith(b'%PDF-'):raise ValueError('invalid nested PDF')
         dest.write_bytes(bb);dest.with_suffix('.pages.json').write_text(json.dumps(tt,ensure_ascii=False,indent=2),encoding='utf-8');out['pdfs'].append({'path':str(dest),'pages':len(tt),'sha256':hashlib.sha256(bb).hexdigest(),'role':'supplement'})
  out['status']='saved'
 except Exception as e:out['error']=str(e)[:200];out['status']='failed'
 (folder/'supplement_acquisition.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(out,ensure_ascii=False),flush=True);return out
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:rs=list(ex.map(run,JOBS))
(ROOT/'补充材料获取记录.json').write_text(json.dumps(rs,ensure_ascii=False,indent=2),encoding='utf-8')
