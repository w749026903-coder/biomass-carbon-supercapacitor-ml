from pathlib import Path
import json,zipfile,hashlib,re,sys
import pypdfium2 as pdfium
sys.stdout.reconfigure(encoding='utf-8')
OUT=Path(__file__).resolve().parent;ROOT=OUT.parent;STAGE=OUT/'已核验PDF暂存';STAGE.mkdir(exist_ok=True)
inspected=json.loads((OUT/'压缩包初检.json').read_text(encoding='utf-8'))
entries=inspected['entries']
ledger=json.loads((ROOT/'文献更新_2023至今/下载归档最终台账_2023至今.json').read_text(encoding='utf-8'))
byid={x['collection_id']:x for x in ledger}
def norm(s):return re.sub('[^a-z0-9]','',s.lower())
# This publisher PDF joins text words during extraction; its complete title
# and DOI are present on page 1, checked directly instead of word-token overlap.
special=entries[37];row=byid['R041'];text=Path(special['front_text_path']).read_text(encoding='utf-8')
assert norm(row['title']) in norm(text) and norm(row['doi']) in norm(text)
special['verified_match']={**next(m for m in special['candidate_matches'] if m['paper_id']=='R041'),'manual_verification':'完整规范化题名与DOI均在首页；已处理文字连写'}
special['status']='清单内已核对_可补全文'
local_hashes={hashlib.sha256(p.read_bytes()).hexdigest():str(p) for p in Path(r'D:\文献').glob('*.pdf')}
for rec in entries:
    if rec.get('sha256') in local_hashes:rec['exact_local_duplicate']=local_hashes[rec['sha256']]
    if rec['archive_index']==37:
        rec['disposition']='2022-08-02预印本，DOI为10.21203/rs.3.rs-1895857/v1；与R073正式论文题名相同，但年份及版本不符合当前归档条件，不解压归档，也不算R073全文已补齐。'
    elif rec.get('exact_duplicate_of'):
        rec['disposition']='压缩包内字节完全重复；只保留原压缩包，不重复归档。'
    elif rec.get('exact_local_duplicate'):
        rec['disposition']='与本地已有文件SHA256相同，且不是当前120篇清单内来源，不重复归档。'
    elif rec['archive_index']==44:
        rec['disposition']='正文是PFAS吸附研究；目标R046的DOI只出现在参考文献，不能据此认定已取得R046全文。'
    elif rec.get('verified_match'):
        rec['disposition']='按DOI与首页题名核对，归入当前120篇清单；只更新全文获取状态，不代表实验数据审核通过。'
    else:
        rec['disposition']='未匹配当前120篇的原文题名和DOI；作为压缩包内额外材料另列，未纳入主清单或训练数据库。'
manifest=[]
with zipfile.ZipFile(inspected['archive_path']) as z:
    for rec in entries:
        if not rec.get('verified_match') or rec.get('exact_duplicate_of'):continue
        match=rec['verified_match'];row=byid[match['paper_id']]
        assert not row.get('local_pdf'),row['collection_id']
        data=z.read(rec['archive_entry']);assert hashlib.sha256(data).hexdigest()==rec['sha256']
        name=row['collection_id']+'__'+row['doi'].replace('/','__')+'.pdf'
        source=STAGE/name;target=Path(r'D:\文献')/name
        assert not target.exists()
        with source.open('xb') as f:f.write(data)
        rec['staged_path']=str(source)
        manifest.append({'paper_id':row['collection_id'],'doi':row['doi'],'source':str(source),'target':str(target),'sha256':rec['sha256'],'pages':rec['pages'],
                         'archive_path':inspected['archive_path'],'archive_sha256':inspected['archive_sha256'],'archive_entry':rec['archive_entry'],
                         'source_kind':'user_provided_archive','source_version':'出版社排版PDF_版本细节待全文审核','verification':'DOI与首页题名对应、PDF页数、ZIP CRC及SHA256'} )
assert len(manifest)==len({x['paper_id'] for x in manifest})==17
assert hashlib.sha256(Path(inspected['archive_path']).read_bytes()).hexdigest()==inspected['archive_sha256']
with (OUT/'核对结果.json').open('x',encoding='utf-8') as f:json.dump(inspected,f,ensure_ascii=False,indent=2)
with (OUT/'归档清单_17篇.json').open('x',encoding='utf-8') as f:json.dump(manifest,f,ensure_ascii=False,indent=2)
for index in [38,37,44]:
    rec=entries[index-1]
    data=z.read(rec['archive_entry']) if False else None
    with zipfile.ZipFile(inspected['archive_path']) as checkzip:data=checkzip.read(rec['archive_entry'])
    doc=pdfium.PdfDocument(data)
    doc[0].render(scale=1.5).to_pil().save(OUT/f'PDF{index:02d}_首页核验.png')
print('Verified new matching fulltexts:',len(manifest),'extra/unmatched entries:',len(entries)-len(manifest))
