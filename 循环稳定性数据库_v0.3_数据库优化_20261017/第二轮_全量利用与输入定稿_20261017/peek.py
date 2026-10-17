from pathlib import Path
import json,re,sys
sys.stdout.reconfigure(encoding='utf-8');ROOT=Path(__file__).resolve().parent
ids=sys.argv[1].split(',');pat=sys.argv[2] if len(sys.argv)>2 else 'Table|initial|retention'
inventory=json.loads((ROOT/'source_inventory_all137.json').read_text(encoding='utf-8'))
for pid in ids:
 print('\nPAPER',pid)
 for f in inventory:
  if f['paper_id']!=pid:continue
  print('ROLE',f['role'])
  for p in json.loads(Path(f['extraction_path']).read_text(encoding='utf-8')):
   t=' '.join(p['text'].split());spans=[]
   for m in re.finditer(pat,t,re.I):
    a,b=max(0,m.start()-120),min(len(t),m.end()+400)
    if spans and a<spans[-1][1]:spans[-1][1]=b
    else:spans.append([a,b])
   for a,b in spans:print('p',p['page'],t[a:b])
