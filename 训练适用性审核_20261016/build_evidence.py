from pathlib import Path
import json,re,sys,hashlib,collections
sys.stdout.reconfigure(encoding='utf-8')
OUT=Path(__file__).resolve().parent;ROOT=OUT.parent
CAT=ROOT/'文献分类与审核准备_20261016'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
inv=read(CAT/'本地与压缩包文件盘点.json')
classes={x['sha256']:x for x in read(CAT/'主清单分类.json')+read(CAT/'额外资料分类.json') if x.get('local_pdf')}
patterns={
 'process':r'(?:carboni[sz]|pyroly|activat|anneal|heated|furnace).{0,110}(?:\d\s*[°◦℃]|\d\s*(?:min|hours?|h\b))|(?:\d{2,4}\s*[°◦℃]).{0,100}(?:carboni|activat|pyroly|heat)',
 'samples':r'\b(?:samples?|denoted|designated|labelled|labeled|named|abbreviated)\b.{0,130}',
 'numeric_capacitance':r'(?:\d[\d.,]*\s*(?:F\s*(?:[/·⋅]?\s*g|g\s*[−-]?\s*1)|F\s*/\s*cm|mF\s*cm|F\s*cm))|(?:capacitance.{0,65}\d)',
 'test':r'(?:three[ -]electrode|two[ -]electrode|symmetric.{0,20}(?:cell|device)|electrolyte|mass loading|potential window|voltage window).{0,180}',
 'porosity':r'(?:surface area|BET|pore volume|micropore|mesopore).{0,95}\d',
 'cycle_rate':r'(?:\d[\d,.]*\s*(?:cycles|%|Wh\s*kg|W\s*kg)).{0,85}',
 'source':r'(?:collected|purchased|obtained|commercial|precursor|biomass|wood|shell|lignin|leaves|straw|peel|bamboo|husk|resin).{0,155}',
 'data_access':r'(?:data availability|data.{0,15}(?:available|request)|supporting information|supplementary (?:material|information|data)).{0,180}',
 'genre':r'(?:review article|review paper|this review|in this review|accepted manuscript|research square|preprint|ssrn|posted date|received.{0,50}\d{4}).{0,100}'
}
allrows=[]
for rec in inv['records']:
    c=classes[rec['sha256']]
    source=Path(rec['reading_excerpt']).with_name(Path(rec['reading_excerpt']).stem+'_全文.txt')
    text=source.read_text(encoding='utf-8')
    parts=re.split(r'\n===== PDF PAGE (\d+) =====\n',text)
    pages=[{'pdf_page':int(parts[i]),'text':parts[i+1]} for i in range(1,len(parts),2)]
    assert len(pages)==rec['pages'],c['id']
    evidence={k:[] for k in patterns}
    ref_seen=False
    for page in pages:
        raw=page['text']
        ref=re.search(r'(?im)^\s*(?:\d+\.?\s*)?references\s*$',raw)
        if ref:raw=raw[:ref.start()];ref_seen=True
        flat=re.sub(r'\s+',' ',raw)
        for name,pattern in patterns.items():
            for m in re.finditer(pattern,flat,re.I):
                excerpt=flat[max(0,m.start()-110):min(len(flat),m.end()+100)]
                if len(evidence[name])<24 and excerpt not in [x['text'] for x in evidence[name]]:
                    evidence[name].append({'pdf_page':page['pdf_page'],'text':excerpt})
        if ref_seen:break
    item={'id':c['id'],'title':c['title'],'doi':c.get('doi'),'year':c.get('year'),
          'source_record_id':rec['source_record_id'],'local_pdf':rec['local_pdf'],
          'sha256':rec['sha256'],'pages':rec['pages'],'prior_category':c['category'],
          'prior_genre':c['genre'],'prior_note':c['note'],'prior_gate':c['quality_gate'],
          'version':c['version'],'evidence':evidence,'first_page':pages[0]['text'],
          'fulltext_file':str(source)}
    allrows.append(item)
(OUT/'正文证据定位.json').write_text(json.dumps(allrows,ensure_ascii=False,indent=2),encoding='utf-8')
for batch in range(4):
    selected=allrows[batch*32:(batch+1)*32]
    lines=[]
    for x in selected:
        lines+=['\n### '+x['id']+' '+str(x['year'])+' '+x['title'],
                '原分类 '+x['prior_category']+'；'+x['prior_gate']+'；'+x['prior_note']]
        for key,limit in [('genre',1),('source',2),('process',2),('samples',2),('numeric_capacitance',3),('test',2),('porosity',1)]:
            for y in x['evidence'][key][:limit]:
                lines.append(f'{key} p{y["pdf_page"]}: {y["text"]}')
    (OUT/f'证据阅读批次_{batch+1}.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print(json.dumps({'documents':len(allrows),'prior_categories':dict(collections.Counter(x['prior_category'] for x in allrows)),
                  'without_numeric_capacitance_locator':[x['id'] for x in allrows if not x['evidence']['numeric_capacitance']]},ensure_ascii=False))
