from pathlib import Path
import json,re,sys
sys.stdout.reconfigure(encoding='utf-8')
base=Path(__file__).resolve().parent
rows=json.loads((base/'正文证据定位.json').read_text(encoding='utf-8'))
ids=set(sys.argv[1].split(','));pattern=sys.argv[2];limit=int(sys.argv[3]) if len(sys.argv)>3 else 3000
for x in rows:
    if x['id'] not in ids:continue
    print('\n###',x['id'],x['title'])
    parts=re.split(r'\n===== PDF PAGE (\d+) =====\n',Path(x['fulltext_file']).read_text(encoding='utf-8'))
    budget=limit;lastend={}
    for i in range(1,len(parts),2):
        text=re.sub(r'\s+',' ',parts[i+1]);page=int(parts[i])
        if len(sys.argv)>4 and page not in {int(p) for p in sys.argv[4].split(',')}:continue
        for m in re.finditer(pattern,text,re.I):
            if m.start()<lastend.get(page,-1):continue
            start=max(0,m.start()-220);end=min(len(text),m.end()+650)
            chunk=text[start:end][:budget]
            if not chunk:break
            print(f'p{page}: {chunk}')
            budget-=len(chunk);lastend[page]=end
            if budget<=0:break
        if budget<=0:break
