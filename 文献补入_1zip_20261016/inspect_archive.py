from pathlib import Path
import zipfile,io,json,hashlib,re,sys,collections
from pypdf import PdfReader
sys.stdout.reconfigure(encoding='utf-8')
OUT=Path(__file__).resolve().parent;ROOT=OUT.parent
archive=Path(r'D:\文献\1.zip')
ledger=json.loads((ROOT/'文献更新_2023至今/下载归档最终台账_2023至今.json').read_text(encoding='utf-8'))
blocked=json.loads((ROOT/'文献扩充_生物质碳_120篇/禁止入库与待核查来源.json').read_text(encoding='utf-8-sig'))
def norm(s):return re.sub(r'[^a-z0-9]','',s.lower())
def words(s):return set(re.findall(r'[a-z]{4,}',s.lower()))-{'with','from','their','based','using','high','performance','derived','carbon','supercapacitor','supercapacitors','biomass'}
def overlap(title,text):
    w=words(title);return len(w&words(text))/max(1,len(w))
seen={};results=[];archive_sha=hashlib.sha256(archive.read_bytes()).hexdigest()
with zipfile.ZipFile(archive) as z:
    for index,info in enumerate([i for i in z.infolist() if not i.is_dir()],1):
        rec={'archive_entry':info.filename,'archive_index':index,'compressed_bytes':info.compress_size,'bytes':info.file_size,'crc32':f'{info.CRC:08x}', 'eligible_for_database':False}
        if Path(info.filename).suffix.lower()!='.pdf' or info.flag_bits&1 or info.file_size>60*1024*1024:
            rec['status']='非PDF/加密/超出检查大小_未提取';results.append(rec);continue
        try:
            data=z.read(info) # also verifies ZIP CRC
            rec['sha256']=hashlib.sha256(data).hexdigest()
            if rec['sha256'] in seen:
                rec['exact_duplicate_of']=seen[rec['sha256']]
            else:seen[rec['sha256']]=info.filename
            if not data[:1024].lstrip().startswith(b'%PDF-'):raise ValueError('Not PDF signature')
            doc=PdfReader(io.BytesIO(data));rec['pages']=len(doc.pages)
            if doc.is_encrypted:raise ValueError('Encrypted PDF')
            page_texts=[p.extract_text() or '' for p in doc.pages[:3]]
            text='\n'.join(page_texts);first=page_texts[0]
            rec['front_page_text_chars']=len(first)
            rec['first3_doi_strings']=list(dict.fromkeys(x.rstrip('.,;:') for x in re.findall(r'10\.\d{4,9}/[^\s<>"\)]+',text,re.I)))[:18]
            matches=[]
            for row in ledger:
                doi=norm(row['doi']);doi_first=doi in norm(first);doi_first3=doi in norm(text)
                title_score=overlap(row['title'],first)
                file_score=overlap(row['title'],info.filename)
                if doi_first3 or file_score>=.8:
                    matches.append({'paper_id':row['collection_id'],'doi':row['doi'],'title':row['title'],
                                    'doi_in_first_page':doi_first,'doi_in_first3':doi_first3,
                                    'title_content_overlap':round(title_score,3),'title_filename_overlap':round(file_score,3),
                                    'already_have_pdf':bool(row.get('local_pdf') and Path(row['local_pdf']).is_file()),
                                    'year':row['year']})
            rec['candidate_matches']=sorted(matches,key=lambda x:(x['doi_in_first_page'],x['doi_in_first3'],x['title_content_overlap']),reverse=True)
            qualified=[m for m in matches if m['doi_in_first3'] and m['title_content_overlap']>=.65]
            if len(qualified)==1:
                rec['verified_match']=qualified[0]
                rec['status']='清单内已核对_已有全文' if qualified[0]['already_have_pdf'] else '清单内已核对_可补全文'
            else:rec['status']='待人工确认或不在当前120篇内'
            rec['blocked_doi_hits']=[x['doi'] for x in blocked if norm(x['doi']) in norm(text)]
            snippet_path=OUT/f'PDF{index:02d}_首页与DOI.txt'
            with snippet_path.open('x',encoding='utf-8') as f:
                for i,t in enumerate(page_texts,1):f.write(f'\n===== PDF PAGE {i} =====\n{t}\n')
            rec['front_text_path']=str(snippet_path)
        except Exception as e:rec['status']='PDF解析失败_待核查';rec['error']=str(e)
        results.append(rec)
        print(index,rec['status'],rec.get('verified_match',{}).get('paper_id',''),rec.get('first3_doi_strings',[])[:2],flush=True)
with (OUT/'压缩包初检.json').open('x',encoding='utf-8') as f:json.dump({'archive_path':str(archive),'archive_sha256':archive_sha,'entries':results},f,ensure_ascii=False,indent=2)
print('SUMMARY',dict(collections.Counter(x['status'] for x in results)),'EXACT_DUPLICATES',sum(bool(x.get('exact_duplicate_of')) for x in results),flush=True)
