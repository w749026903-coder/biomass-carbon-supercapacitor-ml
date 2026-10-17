import importlib.util,json,concurrent.futures
from pathlib import Path
from lxml import etree
ROOT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('supp_fetch',ROOT.parent/'get_supplements.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);m.ROOT=ROOT
items=[]
for p in (ROOT/'sources').glob('*/main.xml'):
    t=etree.parse(str(p));ids=t.xpath('//article-id[@pub-id-type="pmc"]/text()');supp=t.xpath('//supplementary-material')
    if not supp:continue
    if not ids:
        a=json.loads((p.parent/'acquisition.json').read_text(encoding='utf-8'));pc=a.get('pmcid')
        if not pc:
            meta=next((x for x in json.loads((ROOT/'OA初筛待全文核查.json').read_text(encoding='utf-8')) if x['working_id']==p.parent.name),{})
            pc=meta.get('pmcid')
    else:pc=ids[0];pc=pc if pc.startswith('PMC') else 'PMC'+pc
    if pc:items.append((p.parent.name,f'https://www.ebi.ac.uk/europepmc/webservices/rest/{pc}/supplementaryFiles','supplementary.zip'))
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:out=list(ex.map(m.fetch,items))
(ROOT/'扩搜补充材料获取日志.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
