from pathlib import Path
import json,re,html,sys,collections
sys.stdout.reconfigure(encoding='utf-8')
OUT=Path(__file__).resolve().parent;ROOT=OUT.parent
ledger=json.loads((ROOT/'文献下载_120篇/下载归档最终台账.json').read_text(encoding='utf-8-sig'))
inventory={x['doi'].lower():x for x in json.loads((OUT/'旧120篇_年份复核.json').read_text(encoding='utf-8'))}
pool={x['DOI'].lower():x for x in json.loads((OUT/'Crossref_去重总池.json').read_text(encoding='utf-8'))}
additions=json.loads((OUT/'新增原始研究候选池.json').read_text(encoding='utf-8'))
chosen_indices=[1,2,3,4,5,6,8,9,10,11,12,14,18,19,20,21,22,23,24,25,26,28,29,30,31,34,35,36,38,40,44,45,47,50,51,55,56,57,58,61,64,68,69,70,71,75,76,77,80,81,85,88,90,92,93,94,95,97,99,100,102,103,105]
assert len(chosen_indices)==63
selected=[]
for x in ledger:
    if not inventory[x['doi'].lower()]['in_range']:continue
    if x['collection_id']=='B019':continue # synthesis-only paper; no demonstrated supercapacitor testing yet
    x=dict(x);x['old_collection_id']=x['collection_id'];x['origin']='旧候选保留'
    selected.append(x)
for i in chosen_indices:
    x=additions[i-1];m=x['metadata'];title=html.unescape(re.sub('<[^>]+>','',x['title']));title=re.sub(r'\s+',' ',title).strip()
    selected.append({'doi':x['doi'],'title':title,'journal':html.unescape(x['journal']),
        'authors':[(a.get('given','')+' '+a.get('family','')).strip() for a in m.get('author',[])],
        'origin':'本轮补充','local_pdf':None,'metadata_source':'https://api.crossref.org/works/'+x['doi'],
        'role':'机器学习/数据方法候选' if re.search('machine learning|neural network',title,re.I) else '原始研究候选'})
assert len(selected)==120
for i,x in enumerate(selected,1):
    m=pool[x['doi'].lower()];ds={}
    for k in ['published','published-online','published-print','issued']:
        p=m.get(k,{}).get('date-parts',[[]])[0]
        if p:ds[k]=p
    first=min(tuple(p+[1]*(3-len(p))) for p in ds.values())
    assert (2023,1,1)<=first<=(2026,10,16)
    earliest_parts=min(ds.values(),key=lambda p:tuple(p+[1]*(3-len(p))))
    x['collection_id']=f'R{i:03d}';x['publication_dates']=ds;x['first_publication_date']='-'.join(f'{v:02d}' if j else str(v) for j,v in enumerate(earliest_parts))
    x['date_precision']={1:'year',2:'month',3:'day'}[len(earliest_parts)]
    x['year']=first[0];x['eligible_for_database']=False;x['audit_status']='候选_待全文与数据审核'
    x['crossref_type']=m.get('type');x['crossref_pdf_links']=[link for link in m.get('link',[]) if 'pdf' in link.get('content-type','').lower() or re.search(r'/pdf|\.pdf',link.get('URL',''),re.I)]
    x['scope_subtype_audit']='待全文确认_不由题名关键词决定材料类别'
    if x['doi']=='10.1002/cplu.202500342':
        x['audit_status']='二手训练表S1禁止直接导入_旧底层来源与报告问题待核';x['note']='2025论文本身可保留作方法阅读，但S1含2023年前的底层来源，须逐条核定原始发表年份，不能按2025年重新计为本轮近年实验数据。重复与冲突证据见首批审核目录。'
    x['download_status']='已有全文_本轮复核' if x.get('local_pdf') and Path(x['local_pdf']).is_file() else '待公开直链检查'
assert len({x['doi'].lower() for x in selected})==120
assert len({re.sub(r'[^a-z0-9]','',x['title'].lower()) for x in selected})==120
with (OUT/'120篇候选文献_2023至今.json').open('x',encoding='utf-8') as f:json.dump(selected,f,ensure_ascii=False,indent=2)
print('SELECTED',len(selected),'RETAINED',sum(x['origin']=='旧候选保留' for x in selected),'NEW',sum(x['origin']=='本轮补充' for x in selected),'LOCAL',sum(bool(x.get('local_pdf') and Path(x['local_pdf']).is_file()) for x in selected))
print('YEARS',dict(collections.Counter(x['year'] for x in selected)))
