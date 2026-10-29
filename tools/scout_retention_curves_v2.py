"""Locate existing original cycling figures for the two authorized retention routes."""
from pathlib import Path
import collections, hashlib, json, re, sqlite3, subprocess, sys, xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from data.training_latest import open_training_datasets
OUT=ROOT/'保持率双路线预研_v2_20261029'
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n','utf8')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
PATTERN=re.compile(r'cycling|cyclic\s+stability|cycle\s+stability|capacitance\s+retention|cycle\s+performance|long.term\s+stability',re.I)
def main():
 target=OUT/'curve_resource_inventory.json';assert not target.exists(),'Do not replace a reviewed resource inventory'
 with open_training_datasets()as d:
  input={s:d.rows('cycle:reported_'+s.lower())for s in ['2E','3E']};cycles={r['endpoint_id']:r for r in d.canonical_cycles()}
 baseline=OUT/'baseline_inputs.json'
 if baseline.exists():assert json.loads(baseline.read_text('utf8'))==input,'Baseline changed'
 else:write(baseline,input)
 family_by_identity=collections.defaultdict(set);samples=collections.defaultdict(list)
 for system,rows in input.items():
  for r in rows:
   rec=cycles.get(r['row_id'],{});identity=rec.get('identity_key')or r['source_family'];family_by_identity[identity].add(r['source_family']);samples[identity].append(dict(system=system,row_id=r['row_id'],sample=r['sample_name'],cycles=r['features']['cycle_count'],retention=r['target']))
 paths=subprocess.check_output(['rg','--files','-g','*.jpg','-g','*.jpeg','-g','*.png','-g','*.svg','-g','!**/.venv/**'],cwd=ROOT).decode('utf8').splitlines();images=collections.defaultdict(list)
 for p in paths:images[Path(p).name].append(p.replace('\\','/'))
 c=sqlite3.connect((ROOT/'全库复检与特征补提取_20261021/full_corpus_search_native.sqlite').as_uri()+'?mode=ro',uri=True);c.row_factory=sqlite3.Row;papers=[];figures=[]
 from pypdf import PdfReader
 for identity in sorted(samples):
  sources=[dict(r)for r in c.execute("select distinct s.sha256,s.path,s.format from sources s join identity_sources i on i.sha256=s.sha256 where i.identity_key=? and i.role='main'",(identity,))]
  p=dict(identity=identity,source_families=sorted(family_by_identity[identity]),baseline_records=samples[identity],sources=[],candidate_figures=[],pdf_candidate_pages=[])
  for s in sources:
   f=Path(s['path']);f=f if f.is_absolute()else ROOT/f
   if not f.exists():p['sources'].append(dict(**s,available=False));continue
   assert sha(f)==s['sha256'],str(f);rel=f.relative_to(ROOT).as_posix()if ROOT in f.parents else f.as_posix();p['sources'].append(dict(path=rel,sha256=s['sha256'],format=s['format'],available=True,location_scope='project'if ROOT in f.parents else'external_user_literature'))
   if s['format']=='xml':
    try:tree=ET.parse(f)
    except ET.ParseError as e:p['xml_error']=str(e);continue
    for fig in tree.iter():
     if fig.tag.rsplit('}',1)[-1]not in ['fig','figure']:continue
     text=' '.join(''.join(fig.itertext()).split())
     if not PATTERN.search(text):continue
     graphics=[]
     for x in fig.iter():
      if x.tag.rsplit('}',1)[-1]not in ['graphic','inline-graphic']:continue
      link=x.attrib.get('{http://www.w3.org/1999/xlink}href')or x.attrib.get('href','');basename=Path(link).name
      if basename.lower().endswith(('.jpg','.jpeg','.png','.svg')):graphics.append(dict(href=link,local_paths=images.get(basename,[])))
     fr=dict(identity=identity,figure_id=fig.attrib.get('id'),caption=text,graphics=graphics,source_path=rel,source_sha256=s['sha256'],status='caption_candidate_not_curve_admission')
     p['candidate_figures'].append(fr);figures.append(fr)
   elif s['format']=='pdf':
    try:
     reader=PdfReader(f)
     for i,page in enumerate(reader.pages):
      text=page.extract_text()or'';matches=list(PATTERN.finditer(text))
      if matches:p['pdf_candidate_pages'].append(dict(page=i+1,mentions=len(matches),excerpt=' '.join(text[max(0,matches[-1].start()-100):matches[-1].end()+300].split())))
    except Exception as e:p['pdf_scan_error']=repr(e)
  papers.append(p)
 result=dict(status='resource_inventory_not_training_admission',baseline_counts={s:dict(rows=len(rs),sources=len({r['source_family']for r in rs}))for s,rs in input.items()},papers=papers,summary=dict(source_identities=len(papers),caption_candidate_figures=len(figures),figures_with_existing_local_images=sum(any(g['local_paths']for g in f['graphics'])for f in figures),pdf_sources_with_candidate_pages=sum(bool(p['pdf_candidate_pages'])for p in papers)),new_model_fits=0,new_curve_admissions=0)
 write(target,result)
 print(json.dumps(result['summary'],ensure_ascii=False))
 for p in papers:
  if p['candidate_figures']:print(p['identity'],'baseline',len(p['baseline_records']),'figures',[(f['figure_id'],[q for g in f['graphics']for q in g['local_paths']][:2])for f in p['candidate_figures']])
  elif p['pdf_candidate_pages']:print(p['identity'],'PDF pages',[x['page']for x in p['pdf_candidate_pages']][-5:])
if __name__=='__main__':main()
