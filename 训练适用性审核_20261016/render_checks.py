from pathlib import Path
import json,sys
import pypdfium2 as pdfium
sys.stdout.reconfigure(encoding='utf-8')
base=Path(__file__).resolve().parent
rows={x['id']:x for x in json.loads((base/'正文证据定位.json').read_text(encoding='utf-8'))}
out=base/'表图复核';out.mkdir(exist_ok=True)
checks={'R038':[3], 'R045':[10], 'SRC106':[14], 'SRC111':[11],
        'SRC099':[1,3], 'R031':[5], 'SRC121':[3,8], 'R005':[4,10], 'R081':[7]}
for pid,pages in checks.items():
    doc=pdfium.PdfDocument(rows[pid]['local_pdf'])
    for number in pages:
        p=out/f'{pid}_p{number}.png'
        doc[number-1].render(scale=1.45).to_pil().save(p)
    doc.close()
print('Rendered',sum(map(len,checks.values())),'pages')
