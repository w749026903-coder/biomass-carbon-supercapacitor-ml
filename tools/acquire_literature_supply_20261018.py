"""Acquire public primary materials and log blocked components, without admission."""
from collect_literature_supply_20261018 import ROOT,OUT,DB,baseline,fetch,jsonget,dump,clean,safeurl,profile
from pathlib import Path,PurePosixPath
import concurrent.futures,hashlib,io,json,re,unicodedata,urllib.parse,xml.etree.ElementTree as ET,zipfile
NS='{http://www.w3.org/1999/xlink}'
SEEDS=['10.1016/j.biombioe.2026.109168','10.1002/bte2.20230058','10.1002/cplu.202400408','10.1002/smsc.202500174','10.1016/j.biombioe.2025.107773','10.1016/j.mseb.2025.118944','10.1039/d5ta06070b']
REPOSITORY_PDFS={
'10.1002/bte2.20230058':'https://discovery.ucl.ac.uk/id/eprint/10187086/1/Biochar%20for%20supercapacitor%20electrodes.pdf',
'10.1016/j.mseb.2025.118944':'https://www.ac1.hhu.de/fileadmin/redaktion/Fakultaeten/Mathematisch-Naturwissenschaftliche_Fakultaet/Chemie/AnorganischeChemie/AnorganischeChemie_I/Publikations-Dateien_ab_743/776.pdf'}

def crossref(doi):
    raw=jsonget('https://api.crossref.org/works/'+urllib.parse.quote(doi,safe=''))['message'];canonical=raw['DOI'].lower()
    if canonical!=doi.lower():raise ValueError('Crossref DOI mismatch')
    dates=raw.get('published-online') or raw.get('published') or raw.get('published-print') or {};year=dates.get('date-parts',[[None]])[0][0]
    return {'doi':canonical,'title':clean((raw.get('title') or [''])[0]),'year':year,'abstract':clean(raw.get('abstract','')),'metadata_sources':['Crossref exact DOI'],'pdf_urls':[safeurl(x['URL']) for x in raw.get('link',[]) if x.get('URL') and 'pdf' in x.get('content-type','').lower()],'pmcid':None,'is_open_access':False,'training_eligible':False}

def select():
    known=baseline();allrows=json.loads((OUT/'discovery_candidates.json').read_text(encoding='utf-8'));bydoi={r['doi']:r for r in allrows};chosen={}
    for doi in SEEDS:
        if doi in known:continue
        try:r=bydoi.get(doi) or crossref(doi)
        except Exception as e:continue
        r.update(profile(r['title'],r.get('abstract','')) or {'screen_score':20,'configuration_status':'primary_page_suggested_scope_full_text_required'});r['manual_seed']=True;chosen[doi]=r
    # Include all relevant OA candidates, then fill by evidence relevance and year.
    allowed=lambda r:r['doi'].startswith(('10.1002/','10.1007/','10.1016/','10.1021/','10.1038/','10.1039/','10.1088/','10.3390/'))
    for r in allrows:
        if allowed(r) and r['pmcid'] and r['is_open_access'] and r['screen_scope']!='secondary_or_special_electrolyte_title':chosen.setdefault(r['doi'],r)
    for year in [2023,2024,2025,2026]:
        count=sum(r['year']==year for r in chosen.values())
        for r in allrows:
            if count>=30:break
            if r['year']!=year or not allowed(r) or r['doi'] in chosen or r['screen_scope']=='secondary_or_special_electrolyte_title':continue
            if re.search(r'CNT|carbon nanotube|graphene nanoplatelet|magnetic nanoparticles|high.entropy|asymmetric',r['title'],re.I):continue
            chosen[r['doi']]=r;count+=1
    selected=[]
    for r in sorted(chosen.values(),key=lambda r:(-r.get('screen_score',0),-r['year'],r['doi'])):
        r=dict(r);r['cohort']='new_target';r['existing_main_paths']=[];r['existing_SI_paths']=[];r['declared_SI_before_fetch']=False;selected.append(r)
    pending=json.loads((ROOT/'三电极端点扩充_20261018/仍需下载资料_逐项DOI.json').read_text(encoding='utf-8'))
    old={}
    for key,component in [('missing_main','main'),('missing_SI','SI')]:
        for item in pending[key]:
            doi=item['doi'].lower();r=old.setdefault(doi,{'doi':doi,'title':item['title'],'year':None,'abstract':'','metadata_sources':['historical component review'],'pdf_urls':[],'pmcid':None,'is_open_access':False,'cohort':'historical_gap','requested_components':[],'historical_purpose':item.get('purpose',''),'existing_main_paths':known.get(doi,{}).get('main_paths',[]),'existing_SI_paths':known.get(doi,{}).get('SI_paths',[]),'training_eligible':False,'declared_SI_before_fetch':False})
            r['requested_components'].append(component)
            if component=='SI':r['declared_SI_before_fetch']=True
    selected+=list(old.values())
    # Recheck SI for new candidates closest to a useful cycle endpoint.
    for doi in ['10.1039/d6ra04144b','10.3390/nano16040260']:
        if doi in known and doi not in {r['doi'] for r in selected}:
            k=known[doi];selected.append({'doi':doi,'title':k['title'],'year':2026,'abstract':'','metadata_sources':['v07 candidate source'],'pdf_urls':[],'pmcid':None,'is_open_access':True,'cohort':'existing_candidate_SI_check','existing_main_paths':k['main_paths'],'existing_SI_paths':k['SI_paths'],'declared_SI_before_fetch':False,'training_eligible':False})
    # Exact DOI lookup enriches archive IDs; never fuzzy-match a different paper.
    for offset in range(0,len(selected),30):
        rows=selected[offset:offset+30];q=' OR '.join('DOI:"'+r['doi']+'"' for r in rows)
        u='https://www.ebi.ac.uk/europepmc/webservices/rest/search?'+urllib.parse.urlencode({'query':q,'format':'json','resultType':'core','pageSize':100})
        cache=OUT/'metadata'/('exact_doi_'+str(offset//30)+'.json')
        try:
            if cache.exists():data=json.loads(cache.read_text(encoding='utf-8'))
            else:data=jsonget(u);dump(cache,data)
            lookup={r.get('doi','').lower():r for r in data['resultList']['result'] if r.get('doi')}
            for row in rows:
                match=lookup.get(row['doi'])
                if match:
                    row['pmcid']=match.get('pmcid');row['is_open_access']=match.get('isOpenAccess')=='Y';row['abstract']=clean(match.get('abstractText','')) or row.get('abstract','')
                    if not row.get('year'):row['year']=int(match.get('pubYear',0) or 0) or None
                    row['epmc_doi_verified']=True
        except Exception as e:dump(OUT/'metadata'/('exact_doi_'+str(offset//30)+'_error.json'),{'error':str(e)})
    for i,r in enumerate(selected,1):r['supply_id']='SUP_'+str(i).zfill(3)
    dump(OUT/'selected_targets.json',selected)
    print(json.dumps({'targets':len(selected),'new_targets':sum(r['cohort']=='new_target' for r in selected),'historical_targets':len(old),'with_pmc':sum(bool(r.get('pmcid')) for r in selected)},ensure_ascii=False),flush=True)

def pdf_identity(body,row):
    from pypdf import PdfReader
    if not body.startswith(b'%PDF-'):raise ValueError('not a PDF response')
    pdf=PdfReader(io.BytesIO(body));front=pdf.pages[0].extract_text() or ''
    normalize=lambda s:re.sub(r'[^a-z0-9]','',unicodedata.normalize('NFKD',s.lower()))
    exact=normalize(row['doi']) in normalize(front)
    words={w for w in re.findall(r'[a-z0-9]+',row['title'].lower()) if len(w)>3};seen={w for w in re.findall(r'[a-z0-9]+',front.lower()) if len(w)>3};overlap=len(words&seen)/max(1,len(words))
    full_title=len(words)>=5 and normalize(row['title']) in normalize(front)
    if not ((exact and overlap>=.6) or full_title):raise ValueError('PDF first-page DOI/title identity not verified')
    return {'pages':len(pdf.pages),'identity_basis':'first-page DOI plus title coverage >=60%' if exact and overlap>=.6 else 'full normalized title on first page','title_token_coverage':overlap}

def acquire(row):
    logpath=OUT/'records'/(row['supply_id']+'.json')
    if logpath.exists():return json.loads(logpath.read_text(encoding='utf-8'))
    folder=OUT/'sources'/row['supply_id'];folder.mkdir(parents=True,exist_ok=True)
    record={**row,'attempts':[],'files':[],'main_complete':bool(row['existing_main_paths']),'main_pdf_obtained':any(Path(x).suffix.lower()=='.pdf' for x in row['existing_main_paths']),'xml_obtained':any(Path(x).suffix.lower()=='.xml' for x in row['existing_main_paths']),'SI_obtained':bool(row['existing_SI_paths']),'SI_declared':row.get('declared_SI_before_fetch',False),'figures_complete':False,'article_type_verified':None,'training_eligible':False}
    def save(name,body,role,basis,url):
        p=folder/name;p.parent.mkdir(parents=True,exist_ok=True)
        if p.exists():
            if p.read_bytes()!=body:raise ValueError('file collision; preserve existing content')
        else:
            with p.open('xb') as f:f.write(body)
        record['files'].append({'path':p.relative_to(ROOT).as_posix(),'sha256':hashlib.sha256(body).hexdigest(),'bytes':len(body),'role':role,'identity_basis':basis,'source_url':safeurl(url)})
        return p
    def get(url,limit=30000000):
        try:
            body,final,ctype=fetch(url,limit=limit,timeout=16);record['attempts'].append({'url':safeurl(url),'final_url':final,'content_type':ctype,'status':'response_received','bytes':len(body)});return body
        except Exception as e:record['attempts'].append({'url':safeurl(url),'status':'failed','reason':str(e)});return None
    xml=None;expected=[];supplement_names=[]
    if row.get('pmcid') and row.get('is_open_access'):
        u='https://www.ebi.ac.uk/europepmc/webservices/rest/'+row['pmcid']+'/fullTextXML';body=get(u,18000000)
        if body:
            try:
                article=ET.fromstring(body);assert article.tag=='article';assert article.find('body') is not None and len(' '.join(article.find('body').itertext()))>=1500;doi=next((''.join(n.itertext()).strip().lower() for n in article.findall('.//article-meta/article-id') if n.get('pub-id-type')=='doi'),None);assert doi==row['doi']
                save('main.xml',body,'main_xml','Primary archive XML DOI exact match',u);xml=article;record['xml_obtained']=True;record['article_type_verified']=article.get('article-type')
                expected=[PurePosixPath(urllib.parse.urlsplit(g.get(NS+'href','')).path).name.lower() for g in article.findall('./body//fig//graphic') if g.get('content-type')!='thumb' and not g.get(NS+'href','').lower().endswith('.gif')]
                supps=article.findall('.//supplementary-material');record['SI_declared']=record['SI_declared'] or bool(supps)
                for node in supps:
                    for item in [node]+list(node.iter()):
                        if item.get(NS+'href'):supplement_names.append(PurePosixPath(item.get(NS+'href')).name.lower())
                record['declared_supplement_filenames']=sorted(set(supplement_names))
            except Exception as e:record['attempts'].append({'url':u,'status':'invalid_xml_or_identity','reason':str(e)})
        if xml is not None:
            u='https://www.ebi.ac.uk/europepmc/webservices/rest/'+row['pmcid']+'/supplementaryFiles';body=get(u,65000000)
            if body:
                try:
                    z=zipfile.ZipFile(io.BytesIO(body));save('primary_assets.zip',body,'archive','Bound to exact article PMC ID',u);names=set();suppfiles=[]
                    for member in z.infolist():
                        if member.is_dir() or member.file_size>45000000:continue
                        name=PurePosixPath(member.filename).name;ext=Path(name).suffix.lower()
                        if ext not in ('.pdf','.jpg','.jpeg','.png','.tif','.tiff','.doc','.docx','.xls','.xlsx','.txt','.csv','.zip'):continue
                        if (member.external_attr>>16)&0o170000==0o120000:raise ValueError('archive symlink not accepted')
                        names.add(name.lower());role='SI' if name.lower() in supplement_names or re.search(r'(^|[_-])(si|s\d+|supp|suppl|supplementary)([_-]|\.)|supplement|suppl',name.lower()) else 'original_figure_or_asset'
                        if ext in ('.pdf','.doc','.docx','.xls','.xlsx','.csv','.zip') and name.lower() not in expected:role='SI'
                        save('assets/'+name,z.read(member),role,'Primary archive package associated with exact DOI',u)
                        if role=='SI':suppfiles.append(name)
                    record['figures_complete']=all(n in names for n in expected);record['expected_figure_files']=len(expected);record['SI_obtained']=record['SI_obtained'] or bool(suppfiles)
                    record['main_complete']=record['main_complete'] or record['figures_complete']
                except Exception as e:record['attempts'].append({'url':u,'status':'invalid_package_or_extraction','reason':str(e)})
            if not expected and not article.findall('./body//fig'):record['main_complete']=True;record['figures_complete']=True
    # ACS primary SI repository can be accessed without the paywalled article.
    if row['doi'].startswith('10.1021/') and not record['SI_obtained']:
        u='https://api.figshare.com/v2/articles?'+urllib.parse.urlencode({'resource_doi':row['doi']});body=get(u,3000000)
        if body:
            try:
                matches=[r for r in json.loads(body) if (r.get('resource_doi') or '').lower()==row['doi'] and 'acs.figshare.com' in r.get('url_public_html','')]
                for match in matches[:3]:
                    detail=json.loads(get(match['url'],5000000) or b'{}')
                    if (detail.get('resource_doi') or '').lower()!=row['doi']:continue
                    record['SI_declared']=True
                    public_detail={k:detail.get(k) for k in ['id','title','doi','resource_doi','url_public_html']};public_detail['files']=[{'id':f['id'],'name':f['name'],'size':f.get('size'),'download_url':safeurl(f['download_url'])} for f in detail.get('files',[])]
                    save('figshare_'+str(match['id'])+'.json',json.dumps(public_detail,ensure_ascii=False,indent=2).encode(),'metadata','Exact resource_doi plus ACS publisher repository',match['url'])
                    for file in detail.get('files',[]):
                        name=Path(file['name']).name
                        if Path(name).suffix.lower() not in ('.pdf','.docx','.xlsx','.csv','.txt','.zip'):continue
                        blob=get(file['download_url'],45000000)
                        if blob:
                            if name.lower().endswith('.pdf') and not blob.startswith(b'%PDF-'):continue
                            save('SI/'+name,blob,'SI','ACS Figshare exact resource_doi',file['download_url']);record['SI_obtained']=True
            except Exception as e:record['attempts'].append({'url':u,'status':'SI_identity_or_download_issue','reason':str(e)})
    urls=[]
    if row['doi'] in REPOSITORY_PDFS:urls.append(REPOSITORY_PDFS[row['doi']])
    urls+=row.get('pdf_urls',[])
    key=row['doi'].split('/',1)[1]
    if row['doi'].startswith('10.1039/') and row.get('year'):urls.append('https://pubs.rsc.org/en/content/articlepdf/'+str(row['year'])+'/'+key[2:4]+'/'+key)
    if row['doi'].startswith('10.3390/'):
        match=re.fullmatch(r'(nano|molecules|ma|polym|mi|gels|en|ijms|catal|jcs)(\d{2})(\d{2})(\d+)',key)
        if match:
            journal,volume,issue,page=match.groups();full={'nano':'nanomaterials','ma':'materials','polym':'polymers','mi':'micromachines','en':'energies','ijms':'ijms','molecules':'molecules','gels':'gels','catal':'catalysts','jcs':'jcs'}[journal];code=full+'-'+volume+'-'+page.zfill(5);urls.append('https://mdpi-res.com/d_attachment/'+full+'/'+code+'/article_deploy/'+code+'.pdf')
    # XML with original figures is already usable full text; publisher PDF is optional.
    if not record['main_complete']:
        for u in list(dict.fromkeys(urls))[:2]:
            body=get(u,45000000)
            if not body:continue
            try:
                identity=pdf_identity(body,row);save('main.pdf',body,'main_pdf',identity,u);record['main_complete']=True;record['main_pdf_obtained']=True;break
            except Exception as e:record['attempts'].append({'url':safeurl(u),'status':'not_verified_main_pdf','reason':str(e)})
    if not record['main_complete']:
        u='https://doi.org/'+row['doi'];body=get(u,3000000)
        if body:
            page=body.decode('utf-8','replace')
            match=re.search(r'<meta[^>]+name=["\x27]citation_pdf_url["\x27][^>]+content=["\x27]([^"\x27]+)',page,re.I)
            if match:
                pdfurl=match.group(1).replace('&amp;','&');blob=get(pdfurl,45000000)
                if blob:
                    try:identity=pdf_identity(blob,row);save('main.pdf',blob,'main_pdf',identity,pdfurl);record['main_complete']=True;record['main_pdf_obtained']=True
                    except Exception as e:record['attempts'].append({'url':safeurl(pdfurl),'status':'not_verified_main_pdf','reason':str(e)})
            if re.search(r'supporting information|supplementary material|electronic supplementary',page,re.I):record['SI_declaration_hint_from_landing']=True
    # Public publisher SI patterns are attempts, never proof of SI existence.
    if not record['SI_obtained'] and (record['SI_declared'] or row['doi'].startswith('10.1039/')):
        si_url=None
        if row['doi'].startswith('10.1039/'):si_url='https://www.rsc.org/suppdata/'+key[:2]+'/'+key[2:4]+'/'+key+'/'+key+'1.pdf'
        oldlogs=json.loads((ROOT/'三电极端点扩充_20261018/old_si_download_attempts.json').read_text(encoding='utf-8'))
        previous=next((r for r in oldlogs if r['doi']==row['doi'] and r.get('url')),None)
        if previous:si_url=previous['url']
        if si_url:
            body=get(si_url,35000000)
            if body:
                try:identity=pdf_identity(body,row);save('SI/publisher_SI.pdf',body,'SI',identity,si_url);record['SI_obtained']=True;record['SI_declared']=True
                except Exception as e:record['attempts'].append({'url':safeurl(si_url),'status':'SI_identity_pending','reason':str(e)})
    record['main_status']='existing_or_new_complete_fulltext' if record['main_complete'] else 'xml_obtained_figures_incomplete' if record['xml_obtained'] else 'main_not_obtained'
    record['SI_status']='obtained' if record['SI_obtained'] else 'declared_but_not_obtained' if record['SI_declared'] else 'declaration_not_confirmed'
    dump(logpath,record);return record

def run():
    rows=json.loads((OUT/'selected_targets.json').read_text(encoding='utf-8'));(OUT/'records').mkdir(exist_ok=True);(OUT/'sources').mkdir(exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures={pool.submit(acquire,r):r for r in rows};completed=0
        for future in concurrent.futures.as_completed(futures):
            r=futures[future]
            try:x=future.result();print(r['supply_id'],x['main_status'],x['SI_status'],flush=True)
            except Exception as e:dump(OUT/'records'/(r['supply_id']+'_error.json'),{'doi':r['doi'],'error':str(e)});print(r['supply_id'],'ERROR',str(e),flush=True)
            completed+=1
    print('completed',completed,flush=True)

if __name__=='__main__':
    import sys
    select() if '--select' in sys.argv else run()
