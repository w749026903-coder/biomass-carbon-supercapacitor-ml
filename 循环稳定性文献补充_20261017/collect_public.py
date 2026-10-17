import concurrent.futures, importlib.util, json, pathlib, re, urllib.parse, xml.etree.ElementTree as ET
spec=importlib.util.spec_from_file_location('batch',pathlib.Path(__file__).with_name('collect_batch1.py')); b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
PMCS=[('N001','PMC12278731'),('N002','PMC12794195'),('N004','PMC12251455'),('N005','PMC11722056')]
def collect(item):
 ident,pmc=item;folder=b.ROOT/ident;source=json.loads((folder/'acquisition.json').read_text(encoding='utf-8'));doi=source['doi']; out={'id':ident,'pmcid':pmc,'downloads':[]}
 try:
  raw,_,_=b.get('https://www.ebi.ac.uk/europepmc/webservices/rest/'+pmc+'/fullTextXML')
  xml=ET.fromstring(raw); (folder/'公开全文.xml').write_bytes(raw)
  paras=[' '.join(x.itertext()) for x in xml.iter() if x.tag in ['p','title','table','article-title','caption']]
  (folder/'公开全文.txt').write_text('\n\n'.join(paras),encoding='utf-8')
  out['fulltext_xml']={'path':str(folder/'公开全文.xml'),'doi_match':doi.lower() in raw.decode('utf-8').lower(),'url':'https://www.ebi.ac.uk/europepmc/webservices/rest/'+pmc+'/fullTextXML'}
  links=[]
  for x in xml.iter():
   for k,v in x.attrib.items():
    if k.endswith('href') and re.search(r'\.(pdf|docx?|zip)$',v,re.I):links.append(v)
  out['xml_file_links']=list(dict.fromkeys(links))
  # Explicit public repository attachment endpoints.
  for i,v in enumerate(out['xml_file_links']):
   if v.lower().endswith('.pdf'):
    u=v if v.startswith('http') else 'https://pmc.ncbi.nlm.nih.gov/articles/'+pmc+'/bin/'+v
    out['downloads'].append(b.save_pdf(u,folder/f'公开SI_{i+1}.pdf',doi,'supplement'))
  # PMC landing exposes its PDF filename.
  try:
   raw,_,_=b.get('https://pmc.ncbi.nlm.nih.gov/articles/'+pmc+'/');html=raw.decode('utf-8');(folder/'pmc.html').write_text(html,encoding='utf-8')
   urls=re.findall(r'href=["\']([^"\']*pdf/[^"\']+\.pdf)["\']',html)
   if urls:
    u=urllib.parse.urljoin('https://pmc.ncbi.nlm.nih.gov/articles/'+pmc+'/',urls[0]);out['downloads'].append(b.save_pdf(u,folder/'正文_公开仓储.pdf',doi,'main'))
  except Exception as e:out['pmc_pdf_error']=str(e)[:150]
 except Exception as e:out['error']=str(e)[:200]
 (folder/'public_acquisition.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8');return out
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
 for r in ex.map(collect,PMCS):print(json.dumps(r,ensure_ascii=False),flush=True)
