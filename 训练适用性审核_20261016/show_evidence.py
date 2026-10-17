from pathlib import Path
import json,re,sys
sys.stdout.reconfigure(encoding='utf-8')
base=Path(__file__).resolve().parent
rows=json.loads((base/'正文证据定位.json').read_text(encoding='utf-8'))
ids=set(sys.argv[1].split(',')) if len(sys.argv)>1 else set()
for x in rows:
    if ids and x['id'] not in ids:continue
    print('\n###',x['id'],x['year'],x['title'])
    pages=re.split(r'\n===== PDF PAGE (\d+) =====\n',Path(x['fulltext_file']).read_text(encoding='utf-8'))
    body=[]
    for i in range(1,len(pages),2):
        text=pages[i+1]
        ref=re.search(r'(?im)^\s*(?:\d+\.?\s*)?references\s*$',text)
        body.append((int(pages[i]),re.sub(r'\s+',' ',text[:ref.start()] if ref else text)))
        if ref:break
    pats=[('PREP',r'(?:denoted|abbreviated|designated|labelled|labeled|named).{0,180}|(?:carboni[sz]ed|pyroly[sz]ed|activated|heated).{0,85}\d\s*(?:[°◦℃]|h\b)'),
          ('TEST',r'(?:three[ -]electrode|two[ -]electrode|[1236]\s*M\s*(?:KOH|H2SO4|Na2SO4)|mass loading).{0,160}'),
          ('RESULT',r'\d[\d.,]*\s*(?:F\s*[/·⋅]?\s*g|F\s*/\s*cm|mF\s*cm).{0,140}'),
          ('ACCESS',r'(?:supporting information|supplementary (?:information|data|material)|data availability).{0,130}')]
    for key,pat in pats:
        matches=[]
        for page,text in body:
            if key!='ACCESS' and page<2:continue
            for m in re.finditer(pat,text,re.I):
                chunk=text[max(0,m.start()-80):m.end()+40]
                if 'et al' in chunk.lower():continue
                matches.append((page,chunk))
        # First methods/sample locator; last result avoids most introduction citations.
        if key=='RESULT':chosen=matches[-2:]
        else:chosen=matches[:2 if key=='PREP' else 1]
        for page,text in chosen:print(f'{key} p{page}: {text}')
