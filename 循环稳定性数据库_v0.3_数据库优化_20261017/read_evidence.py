from pathlib import Path
import json,sys,re
sys.stdout.reconfigure(encoding='utf-8')
root=Path(__file__).resolve().parent
papers=sys.argv[1].split(','); pattern=sys.argv[2] if len(sys.argv)>2 else r'cycl|mass|silic|initial'
for paper in papers:
 for p in (root/'evidence_text').glob(paper+'_*.json'):
  print('\nFILE',p.name)
  for page in json.loads(p.read_text(encoding='utf-8')):
   text=' '.join(page['text'].split())
   spans=[]
   for m in re.finditer(pattern,text,re.I):
    a,b=max(0,m.start()-180),min(len(text),m.end()+350)
    if spans and a<=spans[-1][1]:spans[-1][1]=b
    else:spans.append([a,b])
   for a,b in spans: print('PAGE',page['page'],text[a:b])
