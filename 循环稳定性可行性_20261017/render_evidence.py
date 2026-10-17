from pathlib import Path
import json, pypdfium2 as pdfium
OUT=Path(__file__).resolve().parent
sources={x['id']:x for x in json.loads((OUT/'全库循环证据定位.json').read_text(encoding='utf-8'))}
tasks=[('R069',7),('R069',8),('R018',11),('R033',5),('R104',11),('R106',15),('SRC035',8),('SRC028',8),('R012_SI',16)]
(OUT/'视觉复核').mkdir(exist_ok=True)
for pid,pg in tasks:
    path=sources['R012']['supplements'][0] if pid=='R012_SI' else sources[pid]['path']
    doc=pdfium.PdfDocument(path)
    image=doc[pg-1].render(scale=1.6).to_pil()
    image.save(OUT/'视觉复核'/f'{pid}_p{pg}.png')
    doc.close()
print('Rendered',len(tasks),'original PDF pages')
