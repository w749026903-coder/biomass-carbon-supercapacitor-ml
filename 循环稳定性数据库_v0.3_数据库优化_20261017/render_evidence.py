from pathlib import Path
import json,pypdfium2 as pdfium
ROOT=Path(__file__).resolve().parent
inv=json.loads((ROOT/'source_inventory.json').read_text(encoding='utf-8'))
targets={'R106':[8,15],'R112':[6,8,13],'R033':[5,6],'R091':[8],'R108':[9],'SRC120':[14,15]}
for paper,nums in targets.items():
 source=next(r for r in inv if r['paper_id']==paper and r['role']=='main')
 doc=pdfium.PdfDocument(source['path'])
 for n in nums:
  out=ROOT/'evidence_images'/f'{paper}_p{n}.png'
  if not out.exists():doc[n-1].render(scale=1.7).to_pil().save(out)
print('Rendered selected original pages; no source modifications.')
