"""Render selected immutable PDF pages for original-figure visual review."""
from pathlib import Path
import hashlib,json,sys
import pypdfium2 as pdfium
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'待补证原文复核_20261022'

if __name__=='__main__':
    packet=json.loads((OUT/'original_review_packets.json').read_text('utf-8'))
    log=OUT/'page_render_provenance.json'
    entries=json.loads(log.read_text('utf-8')) if log.exists() else []
    for specification in sys.argv[1:]:
        key,number=specification.rsplit('@',1);number=int(number)
        paper=next(p for p in packet if any(r['endpoint_id']==key for r in p['rows']))
        source=next(s for s in paper['sources'] if s['format']=='pdf' and 'SI' not in s['role'])
        path=Path(source['path']);target=OUT/'evidence_images'/(key.replace(':','_')+f'_p{number}.png')
        if target.exists():continue
        assert hashlib.sha256(path.read_bytes()).hexdigest()==source['sha256']
        doc=pdfium.PdfDocument(path);page=doc[number-1];bitmap=page.render(scale=1.5);picture=bitmap.to_pil()
        target.parent.mkdir(exist_ok=True);picture.save(target);picture.close();bitmap.close();page.close();doc.close()
        entries.append({'source_path':path.relative_to(ROOT).as_posix(),'source_sha256':source['sha256'],'page_1based':number,'scale':1.5,'render_path':target.relative_to(ROOT).as_posix(),'render_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'purpose':'Original figure visual examination; no numerical digitization inferred.'})
        log.write_text(json.dumps(entries,ensure_ascii=False,indent=2)+'\n','utf-8')
        print(target.relative_to(ROOT).as_posix())
