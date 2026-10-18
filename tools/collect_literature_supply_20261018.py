"""Task-scoped primary literature discovery; candidates are never training rows."""
from pathlib import Path
import concurrent.futures,hashlib,html,json,re,sqlite3,time,unicodedata,urllib.parse,urllib.request
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'文献扩充_大批补齐_20261018'
DB=ROOT/'循环稳定性数据库_v0.7_数据补充_20261018/cycling_v0_7.sqlite'
PROXY={'http':'http://127.0.0.1:7890','https':'http://127.0.0.1:7890'}

def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def clean(s):return ' '.join(re.sub('<[^>]+>',' ',html.unescape(s or '')).split())
def safeurl(s):
    p=urllib.parse.urlsplit(s)
    if p.scheme not in ('http','https'):return None
    return urllib.parse.urlunsplit((p.scheme,p.netloc,p.path,'',''))
def fetch(url,limit=15000000,timeout=25):
    op=urllib.request.build_opener(urllib.request.ProxyHandler(PROXY));req=urllib.request.Request(url,headers={'User-Agent':'LiteratureEvidenceCollection/1.0','Accept':'application/json, application/xml, application/pdf, text/html;q=0.8, */*;q=0.5'})
    with op.open(req,timeout=timeout) as f:
        body=f.read(limit+1);final=safeurl(f.geturl());ctype=f.headers.get('Content-Type','')
    if len(body)>limit:raise ValueError('response exceeds size limit')
    return body,final,ctype
def jsonget(url):return json.loads(fetch(url)[0])

def baseline():
    c=sqlite3.connect(DB.as_uri()+'?mode=ro',uri=True);c.row_factory=sqlite3.Row;known={}
    for row in c.execute('select * from literature_registry where doi is not null'):
        r=dict(row);r.update({'main_paths':[],'SI_paths':[]})
        for d in c.execute('select p.role,l.path from paper_documents p join document_locations l using(source_id) where p.identity_key=?',(r['identity_key'],)):
            path=Path(d['path']);path=path if path.is_absolute() else ROOT/path
            if path.is_file():r['main_paths' if d['role']=='main' else 'SI_paths'].append(str(path))
        known[r['doi'].lower()]=r
    for row in c.execute('select * from candidate_sources_v07'):
        r=dict(row);doi=r['doi'].lower()
        if doi not in known:
            known[doi]={'doi':doi,'title':r['title'],'identity_key':'doi:'+doi,'main_paths':[str(ROOT/'数据补充_v07_20261018/sources'/r['pmcid']/'main.xml')],'SI_paths':[],'archive_status':'candidate_only'}
        for path in (ROOT/'数据补充_v07_20261018/sources'/r['pmcid']/'assets').glob('*'):
            if 'si_' in path.name.lower() or 'supp' in path.name.lower():known[doi]['SI_paths'].append(str(path))
    previous=json.loads((ROOT/'三电极端点扩充_20261018/仍需下载资料_逐项DOI.json').read_text(encoding='utf-8'))
    for component,key in [('main','missing_main'),('SI','missing_SI')]:
        for item in previous[key]:
            doi=item['doi'].lower();r=known.setdefault(doi,{'doi':doi,'title':item['title'],'identity_key':'doi:'+doi,'main_paths':[],'SI_paths':[],'archive_status':'old_pending'})
            r.setdefault('historical_requests',[]).append({'component':component,**item})
    return known

def profile(title,abstract):
    s=(title+' '+abstract).lower();t=title.lower()
    compact=re.sub(r'\s+','',unicodedata.normalize('NFKC',t))
    if re.search(r'\breview\b|overview|perspectives|recent advances|recent progress|research progress|future directions|current technologies|source and performance|bibliometric',t) or re.search(r'this review|review (summari[sz]|comprehensively)',abstract.lower()):return None
    if not re.search(r'supercapacitor|electrochemical capacitor',t):return None
    if not re.search(r'carbon|biochar|graphen',t):return None
    if re.search(r'mno.?2|manganese|nickel|cobalt|ferrite|mxene|polyaniline|polypyrrole|zinc.ion|lithium|batteries|supercapatter|nanocomposite|tio.?2|metal.organic framework',t):return None
    if any(k in compact for k in ['cuo','cu2o','comoo','nico','ni(oh)','ni–co','ni-co','nixco','nimn','cos2','cu7','cufe','cocu','cuco','cose','nise','zno','znco','znfe','cofe','fe3o','feconi','mno2','mn3o','mno₂','vоx','vox/','copper','cu-ion','cuprous','ironsulfide','ironphosphate','zirconium','bismuth','bife','pedot','pani','ldh','mask-derived','organohydrogel','redox-activealizarin','azurea','anthraquinoneanchored']):return None
    if not re.search(r'biomass|biochar|peel|shell|straw|lignin|cellulose|chitosan|wood|bamboo|leaf|leaves|algae|seed|husk|fruit|waste|bagasse|sawdust|hemp|reed|pulp|agarose|tannin|starch|corn|cotton|coconut|coffee|tea |flower|nut |pectin|gelatin',s):return None
    three=bool(re.search(r'three[ -]electrode|3[ -]electrode',s));endurance=bool(re.search(r'\b[\d,]{3,}\s*(?:charge.discharge\s*)?cycles\b|cycling stability|cyclic stability|long.term stability|cycle life',abstract.lower()))
    other=bool(re.search(r'all.solid.state|gel electrolyte|ionic liquid|organic electrolyte|lithium|zinc.ion',t))
    bio_title=bool(re.search(r'biomass|biochar|peel|shell|straw|lignin|cellulose|chitosan|wood|bamboo|leaf|leaves|algae|seed|husk|fruit|waste|bagasse|sawdust|hemp|reed|pulp|agarose|tannin|starch|corn|cotton|coconut|coffee|tea |flower|pectin|gelatin|albumen|protein|sesame|silk',t))
    if not bio_title and not re.search(r'(derived|prepared|synthesi[sz]ed|precursor|using).{0,130}(biomass|biochar|peel|shell|straw|lignin|cellulose|chitosan|wood|bamboo|leaf|leaves|algae|seed|husk|fruit|waste|bagasse|hemp|reed|agarose|tannin|starch)',abstract.lower()):return None
    score=10+4*three+3*endurance+int('porous' in t)+int('biomass' in t)+4*bio_title-5*other
    return {'screen_score':score,'three_electrode_abstract_mention':three,'cycling_abstract_mention':endurance,'screen_scope':'secondary_or_special_electrolyte_title' if other else 'carbon_supercapacitor_candidate','configuration_status':'abstract_mentions_3E_but_cycling_configuration_requires_full_text' if three else 'configuration_requires_full_text','training_eligible':False}

def discover():
    OUT.mkdir(exist_ok=True);(OUT/'metadata').mkdir(exist_ok=True);known=baseline();dump(OUT/'existing_availability_baseline.json',known)
    tasks=[]
    for year in [2023,2024,2025,2026]:
        q='TITLE_ABS:supercapacitor AND TITLE_ABS:carbon AND (TITLE_ABS:biomass OR TITLE_ABS:biochar OR TITLE_ABS:peel OR TITLE_ABS:shell OR TITLE_ABS:straw OR TITLE_ABS:lignin OR TITLE_ABS:cellulose OR TITLE_ABS:chitosan) AND FIRST_PDATE:['+str(year)+'-01-01 TO '+str(year)+('-10-18' if year==2026 else '-12-31')+']'
        u='https://www.ebi.ac.uk/europepmc/webservices/rest/search?'+urllib.parse.urlencode({'query':q,'format':'json','resultType':'core','pageSize':200})
        tasks.append(('epmc_'+str(year),'epmc',u))
    for i,q in enumerate(['biomass porous carbon supercapacitor','peel shell straw carbon supercapacitor','lignin cellulose chitosan porous carbon supercapacitor']):
        u='https://api.crossref.org/works?'+urllib.parse.urlencode({'query.title':q,'filter':'from-pub-date:2023-01-01,until-pub-date:2026-10-18,type:journal-article','rows':160})
        tasks.append(('crossref_'+str(i+1),'crossref',u))
    def run(task):
        name,kind,url=task;file=OUT/'metadata'/(name+'.json')
        try:
            if file.exists():data=json.loads(file.read_text(encoding='utf-8'))
            else:
                raw=jsonget(url)
                # Persist bibliographic fields, not account/signed URL parameters.
                if kind=='crossref':
                    items=[]
                    for r in raw['message']['items']:
                        rr={k:r.get(k) for k in ['DOI','title','type','abstract','published','published-online','published-print','publisher']};rr['URL']=safeurl(r.get('URL',''));rr['link']=[{'URL':safeurl(l['URL']),'content-type':l.get('content-type')} for l in r.get('link',[]) if l.get('URL')];items.append(rr)
                    data={'kind':kind,'url':url,'total_results':raw['message']['total-results'],'items':items}
                else:data={'kind':kind,'url':url,'hit_count':raw['hitCount'],'items':raw['resultList']['result']}
                dump(file,data)
            return data
        except Exception as e:return {'kind':kind,'url':url,'error':str(e),'items':[]}
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:results=list(pool.map(run,tasks))
    pool={};rejected=0
    for data in results:
        for raw in data['items']:
            kind=data['kind'];doi=((raw.get('doi') if kind=='epmc' else raw.get('DOI')) or '').lower();title=clean(raw.get('title') if kind=='epmc' else (raw.get('title') or [''])[0]);abstract=clean(raw.get('abstractText','') if kind=='epmc' else raw.get('abstract',''))
            if not re.fullmatch(r'10\.\d{4,9}/\S+',doi):continue
            if doi.startswith(('10.21203/','10.20944/','10.26434/','10.22541/','10.1149/ma','10.4028/')):continue
            types=' '.join(raw.get('pubTypeList',{}).get('pubType',[])).lower() if kind=='epmc' else ''
            screen=profile(title,abstract)
            if screen is None or 'review' in types:rejected+=1;continue
            if kind=='epmc':year=int(raw.get('pubYear',0) or 0)
            else:
                date=raw.get('published-online') or raw.get('published') or raw.get('published-print') or {};parts=date.get('date-parts',[[0]]);year=parts[0][0]
            if not 2023<=year<=2026:continue
            r=pool.setdefault(doi,{'doi':doi,'title':title,'year':year,'abstract':abstract,'metadata_sources':[],'pdf_urls':[],'pmcid':None,'is_open_access':False,'existing_identity':doi in known,**screen})
            r['metadata_sources'].append(kind);r['screen_score']=max(r['screen_score'],screen['screen_score'])
            if kind=='epmc':r.update({'pmcid':raw.get('pmcid'),'is_open_access':raw.get('isOpenAccess')=='Y','abstract':abstract or r['abstract'],'first_publication_date':raw.get('firstPublicationDate')})
            else:
                r['pdf_urls']+= [u['URL'] for u in raw.get('link',[]) if u.get('URL') and 'pdf' in (u.get('content-type') or '').lower()]
    candidates=sorted([r for r in pool.values() if r['doi'] not in known],key=lambda r:(-r['screen_score'],not r['is_open_access'],-r['year'],r['doi']))
    for i,r in enumerate(candidates,1):r['discovery_id']='DISC_'+str(i).zfill(3);r['metadata_sources']=sorted(set(r['metadata_sources']));r['pdf_urls']=list(dict.fromkeys(r['pdf_urls']))
    dump(OUT/'discovery_candidates.json',candidates);dump(OUT/'discovery_log.json',{'queries':[{'kind':r['kind'],'url':r['url'],'items':len(r['items']),'error':r.get('error')} for r in results],'known_identities':len(known),'new_screened_candidates':len(candidates),'rejected_screen_rows':rejected,'training_eligible':False})
    print(json.dumps({'known':len(known),'candidates':len(candidates),'new_open_access_with_pmc':sum(bool(r['pmcid']) and r['is_open_access'] for r in candidates),'queries':[{'kind':r['kind'],'items':len(r['items']),'error':r.get('error')} for r in results]},ensure_ascii=False),flush=True)

if __name__=='__main__':discover()
