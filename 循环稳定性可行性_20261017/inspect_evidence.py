from pathlib import Path
import json, re, sys
sys.stdout.reconfigure(encoding='utf-8')
OUT=Path(__file__).resolve().parent
mode=sys.argv[1]
for paper in sys.argv[2:]:
    parts=paper.split(':'); pid=parts[0]
    pages=json.loads((OUT/'page_text'/f'{pid}.json').read_text(encoding='utf-8'))
    print('\n### '+pid)
    if len(parts)>1:
        chosen={int(x) for x in parts[1].split(',')}
        for p in pages:
            if p.get('page') in chosen: print('p'+str(p['page'])+' '+re.sub(r'\s+',' ',p['text']))
        continue
    if mode=='cycling':
        pattern=r'(?:cycl(?:ing|ic)\s+(?:stabil|perform|test)|\d[\d, ]*\s*cycles|capacitance\s+retention)'
    elif mode=='methods':
        pattern=r'(?:three.electrode|two.electrode|electrolyte|mass\s+loading|potential\s+(?:window|range)|voltage\s+(?:window|range))'
    elif mode=='properties':
        pattern=r'(?:surface\s+area|pore\s+volume|nitrogen\s+content|oxygen\s+content|at\.?\s*%)'
    elif mode=='compact':
        pattern=r'(?:three.electrode|two.electrode|\d+(?:\.\d+)?\s*M\s*(?:KOH|Na|H|Li)|surface\s+area|pore\s+volume|potential\s+(?:window|range)|voltage\s+(?:window|range))'
    elif mode=='conditions':
        pattern=r'(?:\d+(?:\.\d+)?\s*M\s*(?:KOH|Na|H|Li)|potential\s+(?:window|range)|voltage\s+(?:window|range))'
    else: raise ValueError(mode)
    chunks=[]
    for p in pages:
        if p.get('page',0)<3 and mode=='cycling':continue
        flat=re.sub(r'\s+',' ',p['text'])
        # keep each paragraph bounded, including captions; review snippets are never records.
        for m in re.finditer(pattern,flat,re.I):
            lo=max(0,m.start()-(70 if mode in ['compact','conditions'] else 200));hi=min(len(flat),m.end()+(130 if mode in ['compact','conditions'] else 600))
            if chunks and chunks[-1][0]==p.get('page') and lo<=chunks[-1][2]:
                prev=chunks[-1];chunks[-1]=(prev[0],prev[1],min(max(hi,prev[2]),prev[1]+2200),flat)
            else:chunks.append((p.get('page'),lo,hi,flat))
    if mode=='compact': chunks=[x for x in chunks if x[0] and x[0]>1][:14]
    if mode=='conditions': chunks=[x for x in chunks if x[0] and x[0]>2][:7]
    for pg,lo,hi,flat in chunks:
        txt=flat[lo:hi]
        if mode=='cycling' and not re.search(r'\d[\d,.]*\s*%|\d[\d, ]*\s*cycles',txt,re.I): continue
        print('p'+str(pg)+' '+txt)
