from pathlib import Path
import hashlib,json,zipfile,io,re,sys,collections
from pypdf import PdfReader
sys.stdout.reconfigure(encoding='utf-8')
OUT=Path(__file__).resolve().parent;ROOT=OUT.parent
TEXT=OUT/'阅读摘录';TEXT.mkdir(exist_ok=True)
ledger=json.loads((ROOT/'文献补入_1zip_20261016/下载归档最终台账_补入1zip后.json').read_text(encoding='utf-8'))
blocked=json.loads((ROOT/'文献扩充_生物质碳_120篇/禁止入库与待核查来源.json').read_text(encoding='utf-8-sig'))
def norm(s):return re.sub('[^a-z0-9]','',s.lower())
def words(s):return set(re.findall('[a-z]{4,}',s.lower()))
def overlap(title,text):return len(words(title)&words(text))/max(1,len(words(title)))
def distinctive_overlap(title,text):
    generic={'with','from','their','based','using','high','performance','derived','carbon','supercapacitor','supercapacitors','biomass','materials','material','electrodes','electrode','porous','activated','preparation','synthesis','applications','application','enhanced','efficient','efficiently'}
    title_words=words(title)-generic
    return len(title_words&words(text))/max(1,len(title_words))
groups={}
rootfiles=sorted(Path(r'D:\文献').glob('*.pdf'),key=lambda p:p.name.casefold())
for p in rootfiles:
    digest=hashlib.sha256(p.read_bytes()).hexdigest()
    groups.setdefault(digest,{'sha256':digest,'sources':[]})['sources'].append({'kind':'local_pdf','path':str(p),'filename':p.name,'bytes':p.stat().st_size})
zip_path=Path(r'D:\文献\1.zip');zipsha=hashlib.sha256(zip_path.read_bytes()).hexdigest()
with zipfile.ZipFile(zip_path) as z:
    for info in z.infolist():
        if info.is_dir() or not info.filename.lower().endswith('.pdf'):continue
        if info.flag_bits&1 or info.file_size>60*1024*1024:raise ValueError('Archive member not processable')
        digest=hashlib.sha256(z.read(info)).hexdigest()
        groups.setdefault(digest,{'sha256':digest,'sources':[]})['sources'].append({'kind':'zip_member','archive':str(zip_path),'archive_sha256':zipsha,'entry':info.filename,'filename':Path(info.filename).name,'bytes':info.file_size})
records=[]
with zipfile.ZipFile(zip_path) as z:
    for index,rec in enumerate(groups.values(),1):
        local=next((s for s in rec['sources'] if s['kind']=='local_pdf'),None)
        rec['local_pdf']=local['path'] if local else None
        rec['filename']=(local or rec['sources'][0])['filename']
        try:
            data=Path(local['path']).read_bytes() if local else z.read(rec['sources'][0]['entry'])
            if not data[:1024].lstrip().startswith(b'%PDF-'):raise ValueError('Bad PDF signature')
            doc=PdfReader(io.BytesIO(data));rec['pages']=len(doc.pages)
            pages=[p.extract_text() or '' for p in doc.pages]
            front='\n'.join(pages[:3]);first=pages[0]
            rec['first3_doi_strings']=list(dict.fromkeys(x.rstrip('.,;:') for x in re.findall(r'10\.\d{4,9}/[^\s<>"\)]+',front,re.I)))[:20]
            known_by_hash=[x for x in ledger if x.get('sha256')==rec['sha256'] and x.get('local_pdf')]
            verified=[]
            for x in ledger:
                doiok=norm(x['doi']) in norm(front)
                score=overlap(x['title'],first)
                distinctive=distinctive_overlap(x['title'],first)
                compact=norm(x['title']) in norm(first)
                doi_first=norm(x['doi']) in norm(first)
                if doiok and (compact or (doi_first and score>=.75 and distinctive>=.65) or (score>=.90 and distinctive>=.80)):verified.append((x,score,compact))
            if known_by_hash:
                row=known_by_hash[0];rec['paper_id']=row['collection_id'];rec['doi']=row['doi'];rec['title']=row['title'];rec['match_status']='原已取得全文_哈希一致'
            elif len(verified)==1:
                row,score,compact=verified[0];rec['paper_id']=row['collection_id'];rec['doi']=row['doi'];rec['title']=row['title'];rec['match_status']='新增全文_题名DOI对应';rec['title_overlap']=round(score,3);rec['compact_title_match']=compact
            else:
                rec['paper_id']=None;rec['doi']=None;rec['title']=Path(rec['filename']).stem;rec['match_status']='清单外或身份版本待核'
                rec['possible_matches']=[{'paper_id':x['collection_id'],'doi':x['doi'],'overlap':round(score,3)} for x,score,_ in verified]
            rec['blocked_own_doi']=[x for x in blocked if norm(x['doi']) in norm(first)]
            rec['preprint_notice']=bool(re.search('preprint|not.{0,15}peer.review|research square|posted date',front,re.I))
            rec['accepted_manuscript_notice']=bool(re.search('accepted manuscript|journal pre.proof|author accepted',front,re.I))
            rec['pdf_firstpage_text']=first[:8000]
            # Preserve short context and page numbers for later manual reading.
            chosen=[]
            for pnum,text in enumerate(pages,1):
                if pnum<=3 or (pnum<=12 and re.search(r'(?:\bmethods\b|electrochemical measurements|electrode preparation|dataset description|data collection|machine learning)',text,re.I)):
                    chosen.append({'pdf_page':pnum,'text':text[:14000]})
            with (TEXT/((rec.get('paper_id') or f'SRC{index:03d}')+'.json')).open('x',encoding='utf-8') as f:json.dump(chosen,f,ensure_ascii=False,indent=2)
            rec['reading_excerpt']=str(TEXT/((rec.get('paper_id') or f'SRC{index:03d}')+'.json'))
            with (TEXT/((rec.get('paper_id') or f'SRC{index:03d}')+'_全文.txt')).open('x',encoding='utf-8') as f:
                for pnum,text in enumerate(pages,1):f.write(f'\n===== PDF PAGE {pnum} =====\n{text}\n')
            # Classification cues are locators, not proof of a protocol.
            body='\n'.join(pages[:min(len(pages),12)])
            refs=re.search(r'(?im)^\s*(?:\d+\.?\s*)?references\s*$',body)
            if refs:body=body[:refs.start()]
            patterns={
                'three_electrode':r'three[ -]?electrode|3[ -]?electrode',
                'two_electrode':r'two[ -]?electrode|2[ -]?electrode',
                'symmetric':r'\bsymmetric\b|\bsymmetrical\b',
                'asymmetric':r'\basymmetric\b|\basymmetrical\b',
                'specific_capacitance':r'specific capacitance|F\s*[· ]?\s*g',
                'rate_performance':r'rate (?:performance|capability)|current densit',
                'cycling_stability':r'cycl(?:ing|e) stabil|capacitance retention',
                'energy_power':r'energy densit|power densit',
                'supplement_mentioned':r'supporting information|supplementary (?:data|material|information)',
                'process_parameters':r'carboni[sz]ation|pyrolysis|activation temperature',
                'raw_data_access':r'data availability|data and code availability|data are available|data that support'}
            rec['text_cues']={key:bool(re.search(pat,body,re.I)) for key,pat in patterns.items()}
            rec['status']='可解析_待分类复核'
        except Exception as e:rec['status']='解析异常_待核';rec['error']=str(e)
        rec['source_record_id']=f'SRC{index:03d}';records.append(rec)
        print(index,rec.get('paper_id','') or '',rec.get('match_status'),rec['filename'][:80],flush=True)
with (OUT/'本地与压缩包文件盘点.json').open('w',encoding='utf-8') as f:json.dump({'library_pdf_files':len(rootfiles),'zip_pdf_members':49,'zip_sha256':zipsha,'unique_pdf_contents':len(records),'records':records},f,ensure_ascii=False,indent=2)
print('SUMMARY','root',len(rootfiles),'unique',len(records),'matched',sum(bool(x.get('paper_id')) for x in records),'new',sum(x.get('match_status')=='新增全文_题名DOI对应' for x in records),flush=True)
