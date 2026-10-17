"""All existing sources are used for evidence triage, never auto-admitted."""
from pathlib import Path
import sqlite3,json,hashlib,re,sys,zipfile
from xml.etree import ElementTree as ET
from pypdf import PdfReader
sys.stdout.reconfigure(encoding='utf-8')
ROOT=Path(__file__).resolve().parent;PARENT=ROOT.parent;PROJECT=PARENT.parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(name,obj):(ROOT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
def main():
 assert not (ROOT/'cycling_v0_3r2.sqlite').exists(),'Already initialized; do not regenerate.'
 parent_manifest=json.loads((PARENT/'merge_manifest.json').read_text(encoding='utf-8'))
 assert parent_manifest['ready_for_merge']
 for item in parent_manifest['outputs']:assert sha(item['path'])==item['sha256'],item['path']
 c=sqlite3.connect((PARENT/'cycling_v0_3.sqlite').as_uri()+'?mode=ro',uri=True);c.row_factory=sqlite3.Row
 with sqlite3.connect(ROOT/'cycling_v0_3r2.sqlite') as dest:c.backup(dest)
 for folder in ['evidence_text','evidence_images','exports','modeling']:(ROOT/folder).mkdir(exist_ok=True)
 save('parent_manifest_snapshot.json',parent_manifest)
 protected={x['path']:x['sha256'] for x in parent_manifest['outputs']};protected[str(PARENT/'merge_manifest.json')]=sha(PARENT/'merge_manifest.json')
 files=[dict(r) for r in c.execute('select * from source_files')]
 old={(r['paper_id'],r['role']):r for r in json.loads((PARENT/'source_inventory.json').read_text(encoding='utf-8'))}
 inventory=[]
 for f in files:
  assert sha(f['path'])==f['sha256'];protected[f['path']]=f['sha256']
  previous=old.get((f['paper_id'],f['role']))
  if previous and previous.get('extraction_path') and Path(previous['extraction_path']).exists():
   f['extraction_path']=previous['extraction_path'];f['extraction_sha256']=sha(f['extraction_path']);f['extraction_policy']='reused_verified_v03_derivative'
  else:
   p=Path(f['path']);out=ROOT/'evidence_text'/f"{f['paper_id']}_{f['role']}.json"
   try:
    if p.suffix.lower()=='.pdf':pages=[{'page':i+1,'text':page.extract_text() or ''} for i,page in enumerate(PdfReader(p).pages)]
    elif p.suffix.lower()=='.docx':
     with zipfile.ZipFile(p) as z:el=ET.fromstring(z.read('word/document.xml'))
     ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
     pages=[{'page':None,'text':'\n'.join(''.join(x.itertext()) for x in el.findall('.//w:p',ns))}]
    elif p.suffix.lower()=='.txt':pages=[{'page':None,'text':p.read_text(encoding='utf-8-sig')}]
    else:pages=[{'page':None,'text':'\n'.join(ET.parse(p).getroot().itertext())}]
    save(str(out.relative_to(ROOT)),pages);f['extraction_path']=str(out);f['extraction_sha256']=sha(out);f['extraction_policy']='new_read_only_extraction'
   except Exception as e:f['extraction_error']=str(e)
  inventory.append(f)
 save('source_inventory_all137.json',inventory)
 # Read completed literature handoff only; no new papers or archive IDs ingested.
 lit=PROJECT/'同体系文献补充_第二批_20261017';lm=json.loads((lit/'merge_manifest.json').read_text(encoding='utf-8'))
 assert lm['ready_for_merge'] and lm['baseline_database_sha256']==parent_manifest['baseline_database_sha256']
 for item in lm['outputs']:assert sha(item['path'])==item['sha256'],item['path']
 for name in ['merge_manifest.json','候选文献审核表.json','现有来源补件表.json','进度与交接.md']:
  protected[str(lit/name)]=sha(lit/name)
 save('completed_literature_receipt.json',{'manifest_path':str(lit/'merge_manifest.json'),'manifest_sha256':sha(lit/'merge_manifest.json'),'ready_for_merge':True,'verified_outputs':len(lm['outputs']),'read_only_support_only':True,'new_papers_ingested':0,'archive_performed':False})
 save('protected_fingerprints.json',{'parent_database_sha256':sha(PARENT/'cycling_v0_3.sqlite'),'files':protected})
 papers=[dict(r) for r in c.execute('select * from papers')];endpoints=[dict(r) for r in c.execute('select * from endpoint_effective_review')]
 evidence=[];source_profile=[]
 patterns={
  'cycle_and_label':r'(?:cycl\w*|retention|retain\w*|durab\w*)[^.\n]{0,100}(?:\d[\d,. ]*\s*%|\d[\d, ]*\s*cycles)',
  'cycling_current_mass':r'(?:current density|specific current|normaliz\w*)[^.\n]{0,120}(?:mass|single electrode|both electrodes|total active)',
  'material_features':r'(?:BET|pore volume|XPS|atomic\s*%|atom\s*%|Raman|I\s*D\s*/\s*I\s*G|mass loading|carbonization|activation temperature)',
 }
 for p in papers:
  these=[f for f in inventory if f['paper_id']==p['paper_id']];hits=[]
  for f in these:
   if not f.get('extraction_path'):continue
   for page in json.loads(Path(f['extraction_path']).read_text(encoding='utf-8')):
    text=' '.join(page['text'].split())
    for kind,pattern in patterns.items():
     for m in re.finditer(pattern,text,re.I):
      item={'paper_id':p['paper_id'],'kind':kind,'source_path':f['path'],'source_sha256':f['sha256'],'role':f['role'],'page':page['page'],'offset':m.start(),'excerpt':text[max(0,m.start()-120):m.end()+260],'status':'search_hit_only_requires_semantic_sample_and_protocol_review'}
      hits.append(item)
  evidence+=hits;rs=[r for r in endpoints if r['paper_id']==p['paper_id']]
  source_profile.append({'paper_id':p['paper_id'],'doi':p['doi'],'category':p['category'],'title':p['title'],'source_files':len(these),'extraction_complete':all(f.get('extraction_path') for f in these),'candidate_endpoints':len(rs),'possible_cycle_label_hits':sum(h['kind']=='cycle_and_label' for h in hits),'material_feature_hits':sum(h['kind']=='material_features' for h in hits),'use_role':('candidate_endpoint_and_material_evidence' if rs else 'possible_recovery_requires_review' if any(h['kind']=='cycle_and_label' for h in hits) else 'background_method_or_material_feature_source_no_paired_target'),'do_not_count_as_new_training_examples':True})
 save('all_source_search_hits.json',evidence);save('全126篇利用登记_初筛.json',source_profile)
 save('all_current_endpoints.json',endpoints)
 save('existing_material_observations.json',[dict(r) for r in c.execute('select * from material_observations')])
 print(json.dumps({'sources':len(inventory),'papers':len(papers),'errors':[r for r in inventory if r.get('extraction_error')],'search_hits':len(evidence),'no_endpoint_papers_with_hits':[r['paper_id'] for r in source_profile if r['candidate_endpoints']==0 and r['possible_cycle_label_hits']>0]},ensure_ascii=False))
if __name__=='__main__':main()
