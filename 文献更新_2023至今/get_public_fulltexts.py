from pathlib import Path
import concurrent.futures,urllib.request,urllib.parse,json,re,sys,hashlib,io,xml.etree.ElementTree as ET
from pypdf import PdfReader
sys.stdout.reconfigure(encoding='utf-8')
OUT=Path(__file__).resolve().parent;ROOT=OUT.parent
META=OUT/'获取元数据';STAGE=OUT/'PDF暂存';SUPP=OUT/'补充材料暂存'
for p in [META,STAGE,SUPP]:p.mkdir(exist_ok=True)
rows=json.loads((OUT/'120篇候选文献_2023至今.json').read_text(encoding='utf-8'))
old=json.loads((ROOT/'文献下载_120篇/下载归档最终台账.json').read_text(encoding='utf-8-sig'))
previous_failed={a.get('url') for x in old for a in x.get('attempts',[]) if a.get('error') and a.get('url')}
def fetch(url,limit=40*1024*1024):
    req=urllib.request.Request(url,headers={'User-Agent':'BiomassCarbonLiteratureAudit/1.0','Accept':'*/*'})
    with urllib.request.urlopen(req,timeout=22) as f:
        b=f.read(limit+1);final=f.geturl()
    if len(b)>limit:raise ValueError('超过40MiB单文件上限')
    return b,final
def getjson(url):return json.loads(fetch(url)[0])
def cached_json(name,url):
    p=META/name
    if p.exists():return json.loads(p.read_text(encoding='utf-8'))
    try:
        result=getjson(url)
        p.write_text(json.dumps({'url':url,'data':result},ensure_ascii=False,indent=2),encoding='utf-8');return {'data':result}
    except Exception as e:
        result={'url':url,'error':str(e)};p.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(name,str(e),flush=True);return result
oa={};epmc={}
for i in range(0,len(rows),30):
    batch=rows[i:i+30]
    url='https://api.openalex.org/works?'+urllib.parse.urlencode({'filter':'doi:'+'|'.join('https://doi.org/'+x['doi'] for x in batch),'per-page':50})
    result=cached_json(f'OpenAlex_{i//30+1}.json',url)
    for x in result.get('data',{}).get('results',[]):oa[x.get('doi','').removeprefix('https://doi.org/').lower()]=x
    print('OA_BATCH',i//30+1,'cumulative',len(oa),flush=True)
for i in range(0,len(rows),20):
    batch=rows[i:i+20]
    query=' OR '.join('DOI:'+x['doi'] for x in batch)
    url='https://www.ebi.ac.uk/europepmc/webservices/rest/search?'+urllib.parse.urlencode({'query':'('+query+')','format':'json','pageSize':100,'resultType':'core'})
    result=cached_json(f'EuropePMC_{i//20+1}.json',url)
    for x in result.get('data',{}).get('resultList',{}).get('result',[]):
        if x.get('doi'):epmc[x['doi'].lower()]=x
    print('EPMC_BATCH',i//20+1,'cumulative',len(epmc),flush=True)
def norm(s):return re.sub('[^a-z0-9]','',s.lower())
def save_pdf(data,row,url,proven=False,md5=None):
    if not data[:1024].lstrip().startswith(b'%PDF-'):raise ValueError('响应不是PDF')
    if md5 and hashlib.md5(data).hexdigest()!=md5:raise ValueError('源站MD5校验失败')
    doc=PdfReader(io.BytesIO(data));text='\n'.join(p.extract_text() or '' for p in doc.pages[:3]);first=doc.pages[0].extract_text() or ''
    words=set(re.findall('[a-z]{4,}',row['title'].lower()));overlap=len(words&set(re.findall('[a-z]{4,}',first.lower())))/max(1,len(words))
    doiok=norm(row['doi']) in norm(text)
    if len(doc.pages)<2 or not ((doiok and overlap>=.5) or (proven and overlap>=.78)):raise ValueError(f'PDF对应关系待核验 DOI={doiok}, title={overlap:.2f}')
    name=row['collection_id']+'__'+row['doi'].replace('/','__')+'.pdf';p=STAGE/name
    with p.open('xb') as f:f.write(data)
    return {'staged_path':str(p),'filename':name,'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),'pages':len(doc.pages),'source_pdf_url':url,'doi_in_first3_pages':doiok,'title_overlap':round(overlap,3)}
def process(original):
    row=dict(original);row['attempts_current']=[];row['supplements_current']=[]
    a=oa.get(row['doi'].lower(),{});e=epmc.get(row['doi'].lower(),{})
    row['openalex_retracted']=a.get('is_retracted');row['openalex_id']=a.get('id')
    if a.get('is_retracted'):
        row['download_status']='撤稿标记_不下载不入库';row['audit_status']='冻结_撤稿标记';return row
    if row.get('local_pdf') and Path(row['local_pdf']).is_file():
        p=Path(row['local_pdf']);row['sha256']=hashlib.sha256(p.read_bytes()).hexdigest();row['download_status']='已有全文_本轮复核';return row
    pmcid=e.get('pmcid')
    if pmcid and e.get('isOpenAccess')=='Y':
        try:
            u='https://pmc-oa-opendata.s3.amazonaws.com/?'+urllib.parse.urlencode({'list-type':'2','prefix':pmcid+'.','delimiter':'/'})
            tree=ET.fromstring(fetch(u)[0]);prefixes=[x.text for x in tree.findall('.//{*}CommonPrefixes/{*}Prefix')]
            variants=[]
            for prefix in prefixes[:2]:
                mu='https://pmc-oa-opendata.s3.amazonaws.com/'+prefix+prefix.rstrip('/')+'.json';m=getjson(mu)
                if str(m.get('doi','')).lower()!=row['doi'].lower():continue
                (META/(row['collection_id']+'_'+prefix.rstrip('/')+'.json')).write_text(json.dumps(m,ensure_ascii=False,indent=2),encoding='utf-8')
                if m.get('is_retracted'):row['download_status']='PMC撤稿标记_冻结';return row
                if m.get('pdf_url'):variants.append(m)
            variants.sort(key=lambda x:bool(x.get('is_manuscript')))
            if variants:
                m=variants[0];u=m['pdf_url'].replace('s3://pmc-oa-opendata/','https://pmc-oa-opendata.s3.amazonaws.com/')
                if u not in previous_failed:
                    b,final=fetch(u);md5=urllib.parse.parse_qs(urllib.parse.urlparse(u).query).get('md5',[None])[0]
                    row.update(save_pdf(b,row,final,True,md5),download_status='新增全文已核验_待归档',source_version='author_manuscript' if m.get('is_manuscript') else 'published_version',license=m.get('license_code'),pmcid=pmcid)
                    for media in m.get('media_urls',[])[:10]:
                        su=media.replace('s3://pmc-oa-opendata/','https://pmc-oa-opendata.s3.amazonaws.com/');name=Path(urllib.parse.urlparse(su).path).name
                        if not re.search(r'\.(pdf|docx|xlsx|csv|txt|tsv)$',name,re.I):continue
                        try:
                            sb,final=fetch(su,15*1024*1024);want=urllib.parse.parse_qs(urllib.parse.urlparse(su).query).get('md5',[None])[0]
                            if want and hashlib.md5(sb).hexdigest()!=want:raise ValueError('补充材料MD5不符')
                            if name.lower().endswith('.pdf') and not sb[:1024].lstrip().startswith(b'%PDF-'):raise ValueError('补充材料非PDF')
                            sp=SUPP/(row['collection_id']+'__'+name)
                            with sp.open('xb') as f:f.write(sb)
                            row['supplements_current'].append({'staged_path':str(sp),'filename':sp.name,'sha256':hashlib.sha256(sb).hexdigest(),'url':final,'role':'补充材料_待内容审核'})
                        except Exception as ex:row['attempts_current'].append({'url':su,'error':str(ex)})
                    return row
        except Exception as ex:row['attempts_current'].append({'source':'PMC公开云','error':str(ex)})
    # One best new direct link per paper. Previously failed links are never retried.
    links=[]
    for loc in [a.get('best_oa_location')]+a.get('locations',[]):
        if loc and loc.get('is_oa') and loc.get('pdf_url'):links.append((loc['pdf_url'],'OpenAlex公开全文位置'))
    doi=row['doi'].lower()
    if doi.startswith('10.3390/'):
        match=re.fullmatch(r'([a-z]+)(\d{2})(\d{2})(\d+)',doi.split('/')[-1]);journals={'nano':'nanomaterials','molecules':'molecules','ma':'materials','batteries':'batteries','su':'sustainability','catal':'catalysts','coatings':'coatings','jcs':'jcs','c':'carbon'}
        if match and match[1] in journals:
            j=journals[match[1]];slug=f'{j}-{int(match[2]):02d}-{int(match[4]):05d}'
            links.insert(0,(f'https://mdpi-res.com/d_attachment/{j}/{slug}/article_deploy/{slug}.pdf','MDPI出版社CDN'))
    for link in row.get('crossref_pdf_links',[]):links.append((link['URL'],'Crossref出版社链接'))
    # Publisher RSC full-text link is a public direct PDF for this OA journal.
    if doi.startswith('10.1039/') and doi.split('/')[-1][3:5]=='ra':
        code=doi.split('/')[-1];year=2000+int(code[1:3]);links.insert(0,(f'https://pubs.rsc.org/en/content/articlepdf/{year}/ra/{code}','RSC开放期刊PDF'))
    unique=[]
    for u,label in links:
        if not u.startswith('https://') or u in previous_failed or u in [x[0] for x in unique]:continue
        unique.append((u,label))
    if unique:
        u,label=unique[0]
        try:
            b,final=fetch(u);row.update(save_pdf(b,row,final),download_status='新增全文已核验_待归档',source_version='公开源版本_以PDF核验为准',source_discovery=label);return row
        except Exception as ex:row['attempts_current'].append({'url':u,'error':str(ex)})
    row['download_status']='未取得全文_列DOI';row['failure_summary']='；'.join(dict.fromkeys(x.get('error','') for x in row['attempts_current'])) or ('原公开链接已失败_不重试' if links else '未发现可直接下载的公开PDF链接')
    return row
result=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
    futures={pool.submit(process,x):x for x in rows}
    for future in concurrent.futures.as_completed(futures):
        original=futures[future]
        try:x=future.result()
        except Exception as ex:x={**original,'download_status':'未取得全文_列DOI','failure_summary':str(ex)}
        result.append(x);result.sort(key=lambda x:x['collection_id'])
        (OUT/'获取结果_归档前.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        print(len(result),x['collection_id'],x['download_status'],flush=True)
print('DONE',dict(__import__('collections').Counter(x['download_status'] for x in result)),flush=True)
