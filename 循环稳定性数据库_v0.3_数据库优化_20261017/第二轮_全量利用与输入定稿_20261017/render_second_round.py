from pathlib import Path
import json,pypdfium2 as pdf
ROOT=Path(__file__).resolve().parent
inv=json.loads((ROOT/'source_inventory_all137.json').read_text(encoding='utf-8'))
for paper,nums in {'R069':[8],'R085':[6],'R117':[6],'SRC025':[8,10]}.items():
 s=next(x for x in inv if x['paper_id']==paper and x['role']=='main');d=pdf.PdfDocument(s['path'])
 for n in nums:
  p=ROOT/'evidence_images'/f'{paper}_p{n}.png'
  if not p.exists():d[n-1].render(scale=1.6).to_pil().save(p)
print('Rendered five original pages to second-round evidence directory.')
