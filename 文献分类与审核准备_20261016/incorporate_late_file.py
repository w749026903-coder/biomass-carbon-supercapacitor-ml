from pathlib import Path
import json,hashlib,re,sys,urllib.request,urllib.parse
from pypdf import PdfReader
sys.stdout.reconfigure(encoding='utf-8')
OUT=Path(__file__).resolve().parent
inventory_path=OUT/'本地与压缩包文件盘点.json'
inventory=json.loads(inventory_path.read_text(encoding='utf-8'))
p=Path(r'D:\文献\Synthesis of defect-rich metal-free carbon from coconut shell for catalyzing oxygen evolution reaction.pdf')
digest=hashlib.sha256(p.read_bytes()).hexdigest()
assert not any(x['sha256']==digest for x in inventory['records'])
doc=PdfReader(p);pages=[x.extract_text() or '' for x in doc.pages]
front='\n'.join(pages[:3]);first=pages[0]
doi_hits=list(dict.fromkeys(x.rstrip('.,;:') for x in re.findall(r'10\.\d{4,9}/[^\s<>"\)]+',front,re.I)))
assert re.search(r'oxygen evolution|析氧',front,re.I)
rec={'source_record_id':'SRC122','sha256':digest,'sources':[{'kind':'local_pdf','path':str(p),'filename':p.name,'bytes':p.stat().st_size}],
 'local_pdf':str(p),'filename':p.name,'pages':len(doc.pages),'first3_doi_strings':doi_hits,'paper_id':None,'doi':None,'title':p.stem,
 'match_status':'清单外或身份版本待核','possible_matches':[],'blocked_own_doi':[],'preprint_notice':False,
 'accepted_manuscript_notice':False,'pdf_firstpage_text':first[:8000],'text_cues':{},'status':'可解析_待分类复核',
 'reading_excerpt':str(OUT/'阅读摘录/SRC122.json'),'late_addition':True}
with (OUT/'阅读摘录/SRC122.json').open('x',encoding='utf-8') as f:json.dump([{'pdf_page':i+1,'text':x} for i,x in enumerate(pages[:3])],f,ensure_ascii=False,indent=2)
with (OUT/'阅读摘录/SRC122_全文.txt').open('x',encoding='utf-8') as f:
 for i,text in enumerate(pages,1):f.write(f'\n===== PDF PAGE {i} =====\n{text}\n')
inventory['records'].append(rec);inventory['library_pdf_files']=94;inventory['unique_pdf_contents']=122
inventory_path.write_text(json.dumps(inventory,ensure_ascii=False,indent=2),encoding='utf-8')
meta_path=OUT/'额外资料_书目核对结果.json';meta=json.loads(meta_path.read_text(encoding='utf-8'))
if doi_hits:
 doi=doi_hits[0].lower();url='https://api.crossref.org/works/'+urllib.parse.quote(doi,safe='')
 try:
  req=urllib.request.Request(url,headers={'User-Agent':'BiomassCarbonLiteratureAudit/1.0'})
  with urllib.request.urlopen(req,timeout=20) as response:result={'metadata_source':url,'data':json.load(response)['message']}
 except Exception as e:result={'metadata_source':url,'error':str(e)}
 meta[doi]=result;meta_path.write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
print('Added SRC122',len(pages),'pages',doi_hits[:1])
print(re.sub(r'\s+',' ',first)[:1500])
