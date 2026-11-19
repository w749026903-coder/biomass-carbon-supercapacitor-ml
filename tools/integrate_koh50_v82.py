"""50-paper screening cohort. Reuses existing primary files; never fits a model."""
import collections,csv,hashlib,io,json,logging,re,sqlite3,sys,unicodedata,urllib.parse as uq,urllib.request as ur
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from xml.etree import ElementTree as ET
from pypdf import PdfReader
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from data.cycling_db import open_database
C=ROOT/'.local-literature-cache/P82';BASE=next(ROOT.glob('保持率达标研究_v3*'));OLD=next(BASE.glob('第八十轮*'));OUT=BASE/'第八十二轮_同工况50篇文献与下载清单_20261120';PDF=OUT/'本次取得的正文PDF'
read=lambda p:json.loads(p.read_text('utf-8-sig'))
def dump(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rel(p):return p.relative_to(ROOT).as_posix() if p.is_relative_to(ROOT) else str(p)
# Source assignments were read in full text; paragraph indices below are zero-based body/p in JATS.
NEW=[
('9091489',6,5,10000,90.1,'700-3','eq','Fig.4f',[7,15,17]),
('9056913',2,10,10000,99.1,'BSAC-A-800','eq','Fig.7 (not symmetric Fig.9)',[8,18]),
('5302551',6,2.5,5000,100,'N-BPPCF','eq','Fig.7b',[19,25]),
('5302551',6,2.5,5000,100,'BPPCF','eq','Fig.7b',[19,25]),
('11858159',1,10,10000,92.4,'DC-900','eq','Fig.3g; electrode before device section',[5,11]),
('9042292',6,10,10000,96.4,'YPC-4','eq','Fig.7d',[6,26]),
('9061113',6,5,5000,92,'CACNF-ZnCl2-20%','eq','Fig.7d',[11,14]),
('12750383',1,7,7000,98,'TAK5','eq_abstract','Abstract: 98%; Fig.6B/body: close to 100%; not two independent values',[15,68]),
('9608428',6,1,4000,99.6,'DAC-700','eq','Fig.6F',[28,31]),
('10415863',6,10,10000,94.68,'OAC-4-700','eq','Fig.5f (not symmetric Fig.S3)',[8,21,24]),
('13691559',6,10,5000,92.1,'AC700','eq','Fig.7b; pristine carbon only; published version of SSRN 6799753, counted once',[10,27]),
('9417857',3,10,10000,95.6,'APVPC-2','approx','Fig.2f, not device Fig.3',[7,29,30])]
LOCAL=['candidate:TE040','candidate:TE042','candidate:TE043','candidate:TE047','candidate:TE048','candidate:TE049','candidate:TE050','candidate:V05:017','candidate:TE017','incoming:ADD_016_T01']
def get(url):
    with ur.urlopen(ur.Request(url,headers={'User-Agent':'Mozilla/5.0; research literature verification'}),timeout=12) as resp:return resp.read(45000000)
def valid(p):
    with p.open('rb') as h:
        if b'%PDF-' not in h.read(1024):return False
        h.seek(max(0,p.stat().st_size-8192));return b'%%EOF' in h.read()
def restore_discovery():
    # Rebuild the selected inputs directly from the frozen URL ledger on another checkout.
    saved=OUT/'检索留档.json'
    if not saved.exists():return
    ledger=read(saved);C.mkdir(parents=True,exist_ok=True)
    for i,url in ledger['selected_pmc'].items():
        p=C/('PMC'+i+'.xml')
        if not p.exists():p.write_bytes(get(url))
        tree=ET.parse(p);meta=tree.find('.//article-meta');body=tree.find('.//body')
        tx=lambda e:' '.join(''.join(e.itertext()).split())
        if not p.with_suffix('.json').exists():dump(p.with_suffix('.json'),dict(doi=tx(meta.find("article-id[@pub-id-type='doi']")).lower(),title=tx(meta.find('title-group/article-title')),ps=[tx(y) for y in body.iter('p')]))
        if not p.with_suffix('.url').exists():p.with_suffix('.url').write_text(url,encoding='utf8')
    for f,q in zip(('query.json','query2.json','query3.json'),ledger['queries']):
        if not (C/f).exists():dump(C/f,dict(query=q))
    if not (C/'leads.json').exists():dump(C/'leads.json',ledger['leads'])
def main():
    restore_discovery()
    logging.getLogger('pypdf').setLevel(logging.ERROR);OUT.mkdir(exist_ok=True);PDF.mkdir(exist_ok=True)
    (OUT/'.gitignore').write_text('/本次取得的正文PDF/\n',encoding='utf8')
    d=open_database();db=sqlite3.connect((OLD/'retention50.sqlite').as_uri()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
    info={}; rows=[]; candidates=collections.defaultdict(list);pmc={}; notes={}
    def add(s,title,origin,k,sample,m,a,n,y,kind,ev,ready=False,why=''):
        assert 1<=m<=6 and 1<=a<=10 and 1000<=n<=10000
        info[s]=title;rows.append(dict(doi=s,origin=origin,id=k,sample=sample,KOH_M=m,current_A_g=a,cycles=n,retention_pct=y,relation=kind,source=ev,early20_ready=bool(ready),restriction=why))
    for x in db.execute("select * from endpoints join papers using(doi) where electrolyte='KOH' and concentration_mol_L between 1 and 6 and reported_current_A_g between 1 and 10 and cycle_count between 1000 and 10000 order by doi,endpoint_id"):
        add(x['doi'],x['title'],'旧名单同工况',x['endpoint_id'],x['sample'],x['concentration_mol_L'],x['reported_current_A_g'],x['cycle_count'],x['retention_pct'],x['relation'],dict(database=rel(OLD/'retention50.sqlite'),id=x['endpoint_id'],audit=json.loads(x['evidence_json'])),x['early_b'],x['notes'])
        for ev in json.loads(x['evidence_json']):
            if ev.get('file'):candidates[x['doi']].append(ROOT/ev['file'])
    assert len(info)==29
    config=read(ROOT/'data/current_literature.json');lib=sqlite3.connect((ROOT/config['directory']/config['database_file']).as_uri()+'?mode=ro',uri=True)
    tit=dict((s.lower(),t) for s,t in lib.execute('select doi,title from identity_inventory where doi is not null'))
    for s,p in lib.execute("select doi,path from source_documents where role='main'"):
        if s and p:candidates[s.lower()].append(ROOT/p)
    for p in C.glob('PMC*.json'):
        z=read(p);pmc[z['doi']]=p.stem
    for z in read(next(ROOT.glob('三电极端点扩充*/corpus_index.json'))):
        if z.get('doi') and z.get('source_path'):candidates[z['doi'].lower()].append(ROOT/z['source_path'])
    for z in read(next(ROOT.glob('保持率双路线*/curve_resource_inventory.json')))['papers']:
        s=z['identity'].removeprefix('doi:');candidates[s].extend(ROOT/v['path'] for v in z['sources'] if v.get('path'))
    for k in LOCAL:
        x=d.by_endpoint(k);s=x['source_group'].removeprefix('doi:');ev=[{'source_id':u['source_id'],'locator':u['locator']} for u in d.evidence(k,'retention_pct') if u.get('currently_selected')]
        why=d.holds(k).get('reason','');title=tit[s]
        if k=='candidate:TE047':why+=' 补充端点：原文结果另报1000圈约92%；本清单沿用2000圈的原审查记录。'
        if x.get('source_pdf'):candidates[s].append(ROOT/x['source_pdf'])
        if k=='candidate:TE040':why+=' 摘要写 more than 96%，结果段写96%；图5f保留定位，保留两种表述，不作无争议精确点标签。'
        add(s,title,'项目复核库补入',k,x['sample_name'],x['concentration_mol_L'],x['reported_current_A_g'],x['cycle_count'],x['retention_pct'],('abstract_gt_vs_results_eq' if k=='candidate:TE040' else x['retention_relation']),{'endpoint':k,'selected_evidence':ev,'old_value':x['retention_pct'],'old_relation':x['retention_relation'],'source_pdf':x.get('source_pdf'),'pages':x.get('evidence_pages')},why=why)
    assert len(info)==39
    for i,m,a,n,y,sample,kind,loc,ix in NEW:
        p=C/('PMC'+i+'.json');z=read(p);s=z['doi'];path=p.with_suffix('.xml'); assert path.exists() and all(z['ps'][j] for j in ix)
        ev=dict(url=p.with_suffix('.url').read_text(),xml_sha256=sha(path),figure=loc,body_paragraphs=ix,pmcid='PMC'+i); add(s,z['title'].rstrip('†').strip(),'公开原文补入',f'PMC{i}:{sample}',sample,m,a,n,y,kind,ev,why='正文终点已定位；早期点未做版本化读图。')
    assert len(info)==50
    # Also collect DOI-matched official main-text references from the original 53-row source review.
    for x in read(next(ROOT.glob('三电极端点扩充*/三电极端点_53条.json')))['rows']:
        if not x.get('doi') or not x.get('source_file'):continue
        s=x['doi'].lower();path=ROOT/x['source_file'];candidates[s].append(path)
        match=re.search(r'PMC\d+',str(path));
        if match and s not in pmc:pmc[s]=match.group()
    fallback={'10.1039/c7ra13013a':'PMC9078325','10.1016/j.heliyon.2023.e21804':'PMC10651512','10.1039/d4ra08818b':'PMC11770366'};pmc.update(fallback)
    if (OUT/'检索留档.json').exists():pmc.update(read(OUT/'检索留档.json').get('roster_pmc',{}))
    # Fulltext PDF candidates by title in the user's library (no movements or edits).
    leads={x['doi']:x for x in read(C/'leads.json') if x['doi'] in ('10.1016/j.rsurfi.2026.100746','10.1021/acsaem.4c00141')}
    target=info|{k:v['title'] for k,v in leads.items()};norm=lambda s:re.sub(r'[^a-z0-9]+','',unicodedata.normalize('NFKD',s).lower())
    for p in Path('D:/文献').rglob('*.pdf'):
        f=norm(p.stem)
        for s,title in target.items():
            t=norm(title)
            if len(f)>29 and (t==f or t in f or (len(f)>45 and t.startswith(f))) and not re.search('supplement|supportinginfor',f):candidates[s].append(p)
    def full(t):
        s,title=t;history=[];oldpaths=list(dict.fromkeys(candidates[s]));key=urllib_name=s.replace('/','_');dest=PDF/(key+'.pdf')
        for p in [*oldpaths,dest]:
            if s=='10.1007/s00226-023-01515-0' and p!=dest:continue # ADD_016 is Research Square, not journal version
            if p.suffix.lower()=='.pdf' and p.is_file() and valid(p):
                previous=read(OUT/'核验.json')['files'].get(s,{}) if (OUT/'核验.json').exists() else {}
                if previous.get('sha256')==sha(p) and previous.get('path')==rel(p):return s,previous
                return s,dict(path=rel(p),sha256=sha(p),status='已有或已落盘正文PDF',checks=history)
        urls=[]
        if s in pmc:
            i=pmc[s];host='https://pmc-oa-opendata.s3.amazonaws.com/'
            try:
                keys=sorted(z.text for z in ET.fromstring(get(host+'?list-type=2&prefix='+i+'.')).findall('.//{*}Key') if re.fullmatch(i+r'\.\d+/'+i+r'\.\d+\.pdf',z.text));urls.extend(host+k for k in keys[-1:])
            except Exception as e:history.append(['PMC',str(e)[:100]])
        if s.startswith('10.1039/'):urls.append('https://pubs.rsc.org/en/content/articlepdf/'+('2024/nj/' if s=='10.1039/d3nj04881k' else '2022/ra/')+s.split('/')[1]) if s=='10.1039/d3nj04881k' else None
        if s.startswith('10.1021/'):urls.append('https://pubs.acs.org/doi/pdf/'+s)
        if s.startswith('10.1007/'):urls.append('https://link.springer.com/content/pdf/'+s+'.pdf')
        if s in leads:urls+=leads[s]['urls']
        if s=='10.1016/j.rsurfi.2026.100746':
            try:
                md=json.loads(get('https://api.crossref.org/works/'+s))['message'];pid=next((k for k in md.get('alternative-id',[]) if k.startswith('S')),None)
                if pid:urls+=['https://www.sciencedirect.com/science/article/pii/'+pid+'/pdfft?isDTMRedir=true&download=true','https://api.elsevier.com/content/article/pii/'+pid+'?httpAccept=application/pdf']
            except Exception as e:history.append(['Crossref',str(e)[:100]])
        if not urls or s in leads:
            try:
                oa=json.loads(get('https://api.openalex.org/works/https://doi.org/'+s));urls.extend(l['pdf_url'] for l in oa['locations'] if l and l.get('pdf_url'))
            except Exception as e:history.append(['OpenAlex',str(e)[:100]])
        urls+=['https://doi.org/'+s]
        for url in dict.fromkeys(urls):
            try:
                raw=get(url)
                if b'%PDF-' not in raw[:1024] or b'%%EOF' not in raw[-8192:]:history.append([url,'返回网页，非正文PDF']);continue
                rr=PdfReader(io.BytesIO(raw));assert len(rr.pages)>=2;dest.write_bytes(raw)
                return s,dict(path=rel(dest),sha256=sha(dest),status='本次下载正文PDF',checks=history+[[url,'PDF verified']])
            except Exception as e:history.append([url,str(e)[:110]])
        xml=[rel(p) for p in oldpaths if p.suffix=='.xml' and p.is_file()]
        return s,dict(path=None,sha256=None,status='未取得正文PDF',checks=history,available_xml=xml)
    with ThreadPoolExecutor(9) as pool:files=dict(pool.map(full,target.items()))
    def writecsv(name,rs):
        with (OUT/name).open('w',encoding='utf-8-sig',newline='') as h:
            w=csv.DictWriter(h,fieldnames=list(rs[0]));w.writeheader();w.writerows(rs)
    book=[]
    for i,s in enumerate(sorted(info),1):
        rr=[r for r in rows if r['doi']==s];book.append(dict(编号=i,DOI=s,题名=info[s],来源=rr[0]['origin'],样品及终点='；'.join(f"{r['sample']}: {r['KOH_M']:g} M KOH，{r['current_A_g']:g} A/g，{r['cycles']:g}圈，{r['retention_pct']:g}% ({r['relation']})" for r in rr),可用早期曲线='是' if any(r['early20_ready'] for r in rr) else '尚未准入',正文PDF=files[s]['path'] or '见待下载清单',原文入口='https://doi.org/'+s))
    writecsv('同工况50篇逐篇清单.csv',book);dump(OUT/'逐测试证据.json',rows)
    miss=[dict(DOI=s,题名=t,用途='已列入50篇，补正文PDF' if s in info else '额外候选，不占50篇',所需资料='正文PDF及循环图对应的SI（如有）',原文入口='https://doi.org/'+s) for s,t in target.items() if not files[s]['path']]
    if miss:writecsv('待下载正文_DOI清单.csv',miss)
    dump(OUT/'核验.json',dict(roster_sha256=sha(OUT/'同工况50篇逐篇清单.csv'),papers=len(info),tests=len(rows),early_ready=sum(b['可用早期曲线']=='是' for b in book),files=files,fits=0,metric='held-out prediction R2 > 0.90',inventories=['prior 29 from P80', '10 additional previously reviewed', '11 OA fulltext'],queries=[read(C/f)['query'] for f in ('query.json','query2.json','query3.json')],new_source_ids=[a[0] for a in NEW],as_of='2026-11-20'))
    print('papers',len(info),'rows',len(rows),'early',sum(b['可用早期曲线']=='是' for b in book),'pdf',sum(bool(files[s]['path']) for s in info));print('missing',[(x['DOI'],x['用途']) for x in miss]);print('new',sum(str(x.get('path')).startswith(rel(PDF)) for x in files.values()))
if __name__=='__main__':main()
