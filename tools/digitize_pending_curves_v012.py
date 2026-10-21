"""Three explicitly calibrated figure readings, never author-exact labels.

The fixed pixel anchors below were inspected on the retained original figure or
the hash-bound PDF rendering. Bounds are conservative reading bounds, not CIs.
No model is fitted and no database/admission state is changed here.
"""
from pathlib import Path
import hashlib,json,statistics
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
BATCH=ROOT/'待补证原文复核_20261022'

def fingerprint(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def read_markers(image_path,box,kind):
    image=Image.open(image_path).convert('RGB');points=[]
    for x in range(box[0],box[2]):
        for y in range(box[1],box[3]):
            r,g,b=image.getpixel((x,y))
            ok=(kind=='green' and g>60 and r<g*.65 and b<g*.65)
            ok|=(kind=='red' and r>130 and g<r*.65 and b<r*.65)
            ok|=(kind=='gray' and max(r,g,b)-min(r,g,b)<4 and 60<=(r+g+b)/3<=200)
            if ok:points.append((x,y))
    if len(points)<8:raise RuntimeError('Marker not recovered at the reviewed location.')
    return {'x':statistics.median(x for x,y in points),'y':statistics.median(y for x,y in points),'pixels':len(points)}

def main():
    output=BATCH/'figure_digitization.json'
    if output.exists():raise FileExistsError('Reviewed readings already exist; do not overwrite.')
    packets=json.loads((BATCH/'original_review_packets.json').read_text('utf-8'))
    paper=next(p for p in packets if p['doi']=='10.1002/est2.554')
    source=next(s for s in paper['sources'] if s['role']=='main')
    assert fingerprint(Path(source['path']))==source['sha256']
    image=BATCH/'evidence_images/legacy_R117_CY01_p10.png';rows=[]
    for endpoint,box,color in [('legacy:R117_CY01',(732,273,740,291),'green'),('legacy:R117_CY02',(732,292,740,311),'red')]:
        point=read_markers(image,box,color)
        value=(370-point['y'])/(370-252)*250
        rows.append({'endpoint_id':endpoint,'source_path':source['path'],'source_sha256':source['sha256'],
          'locator':'PDF p10 Fig7G, own sample at8000 cycles','render_path':image.relative_to(ROOT).as_posix(),
          'render_sha256':fingerprint(image),'calibration':{'zero_pct_y_px':370,'250_pct_y_px':252,'end_cycle':8000,'last_marker_roi':box},
          'marker':point,'retention_pct':round(value),'retention_relation':'approx','evidence_kind':'digitized_own_figure',
          'reading_bound_pp':5,'note':'Whole-percent graph reading; +/-5 percentage points is a conservative reading bound, not a statistical confidence interval. Values above100 are retained.'})
    image=BATCH/'evidence_images/SSK05_FigS4a.png'
    initial=read_markers(image,(113,145,120,164),'gray');final=read_markers(image,(652,169,659,187),'gray')
    value=(448-final['y'])/(448-initial['y'])*100
    si=BATCH/'new_supplements/SSK05_mmc1.docx'
    rows.append({'endpoint_id':'incoming:ADD_060_T01','source_path':si.relative_to(ROOT).as_posix(),'source_sha256':fingerprint(si),
      'locator':'Own FigS4a, black specific-capacitance series at5000 cycles; not red Coulombic efficiency',
      'render_path':image.relative_to(ROOT).as_posix(),'render_sha256':fingerprint(image),
      'calibration':{'zero_F_g_y_px':448,'initial_marker':initial,'final_marker':final,'end_cycle':5000},
      'retention_pct':round(value,1),'retention_relation':'approx','evidence_kind':'digitized_own_figure_ratio',
      'reading_bound_pp':1.5,'note':'Final/first plotted specific capacitance, conservative reading bound, not a CI. Exact initial cycle index not inferred. FigS4b labels5001 whereas caption says5000; retained in review caveats.'})
    output.write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n','utf-8')
    print(json.dumps([{k:r[k] for k in ['endpoint_id','retention_pct','retention_relation','reading_bound_pp']} for r in rows],ensure_ascii=False))

if __name__=='__main__':main()
