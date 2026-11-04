"""Extract only approved early pixels and input features for Fig. 8C."""

from pathlib import Path
import hashlib
import json
import re
import xml.etree.ElementTree as ET

import numpy as np
from PIL import Image
import pypdfium2 as pdf

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / '保持率达标研究_v3_主线与近优组合_20261030'
CACHE = ROOT / '.local-literature-cache/P22'
P22 = BASE / '第二十二轮_外部验证来源盲态预留_20261105'
OUT = BASE / '第二十三轮_花椒壳早期盲态输入_20261105'
DOI = '10.1039/c9ra08319g'
PDF_SHA = 'e965c57d5abb3ac761a3b18aacdb52e7d2d78e1ee822d63d3f7d68a2415a5ea3'
PAPER = CACHE / 'PMC9049566_sealed_published.pdf'
MARKERS = ((83,424),(87,424),(91,425),(95,425),(99,425),(103,425),(107,426),(111,426),
           (115,425),(118,426),(123,426),(127,426),(130,427),(134,426),(138,426),(142,426),(146,426))
X0, XN, Y100, Y70 = 74.5, 464.5, 426.25, 627.5
CROP = (77, 412, 152, 450)
HORIZON = 5000


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def flat(node):
    return ' '.join(''.join(node.itertext()).split())


def source_evidence():
    screening = read(P22/'structural_screen.json')
    assert screening['endpoint_values_exposed'] == 0
    entry = next(r for r in screening['results'] if r['doi'] == DOI)
    path = ROOT / entry['sealed_cache']
    assert sha(path) == entry['sha256']
    root = ET.parse(path).getroot()
    caption = flat(root.find(".//fig[@id='fig8']/caption"))
    cycle_panel = re.search(r'\(C\)\s*cyclic stability(.*?)\(D\)', caption, re.I)
    assert cycle_panel and re.search(r'0\.5\s*A\s*g\s*[−–-]\s*1', cycle_panel[1])
    assert '6 M KOH' in caption and 'symmetric' in caption.lower()
    paragraphs = [p for p in root.findall('./body//p') if any('fig8' in (q.get('rid') or '').split() for q in p.findall('.//xref'))]
    # A whitelist of facts, never serialize the entire sentence or any percentage.
    assert any(re.search(r'5000\s+times of charge/discharge', flat(p), re.I) and 'Fig. 8C' in flat(p) for p in paragraphs)
    tab = root.find(".//table-wrap[@id='tab2']")
    bet_rows = [[flat(c) for c in t.findall('./td')] for t in tab.findall('.//tr')]
    nc3, = [t for t in bet_rows if t and t[0] == 'NC-3']
    assert nc3[1] == '1473.6663'
    return dict(doi=DOI, source_family='doi:'+DOI, sample='NC-3//NC-3', system='2E', device='symmetric',
                biomass='Zanthoxylum schinifolium husk', cycle_count=HORIZON, method='reported galvanostatic cycling',
                static_features=dict(reported_current_A_g=.5, electrolyte='KOH', concentration_mol_L=6.,
                                     BET_m2_g=float(nc3[1]), cycle_voltage_lower_V=None, cycle_voltage_upper_V=None,
                                     reference_electrode=None), current_mass_basis=None,
                locators=['Fig. 8(C) and caption', 'Electrochemical performance paragraph naming Fig. 8C',
                          'Electrochemical measurements device subsection', 'Table 2 NC-3 BET'],
                unresolved='Cycle-specific voltage limits and mass basis remain unresolved. Fig. 8(B) rate current is separate.',
                terminal_label=None)


def crop():
    assert sha(PAPER) == PDF_SHA
    with pdf.PdfDocument(PAPER) as doc:
        obj, = [o for o in doc[4].get_objects() if o.type == pdf.raw.FPDF_PAGEOBJ_IMAGE and o.get_px_size() == (981,726)]
        x0,y0,x1,y1 = CROP
        assert x0 >= X0 and x1-1 < X0+.2*(XN-X0)
        a = np.asarray(obj.get_bitmap().to_pil().convert('RGB').crop(CROP), dtype=np.int16)
    red,green,blue = np.moveaxis(a,2,0)
    trace = (red>125)&(red-green>50)&(red-blue>40)
    clean = np.full(a.shape,255,np.uint8)
    clean[trace] = a[trace]
    return clean, trace, green


def read_markers(trace, green):
    marks = []
    dx = HORIZON/(XN-X0)
    dy = 30/(Y70-Y100)
    for x,y in MARKERS:
        i,j = y-CROP[1],x-CROP[0]
        assert trace[i-2,j] and trace[i+2,j] and green[i,j] >= 190
        assert x+2 <= X0+.2*(XN-X0)
        cycle = (x-X0)*dx
        value = 100+(Y100-y)*dy
        marks.append(dict(pixel=[x,y],hole_green=int(green[i,j]),cycle_reading=cycle,
                          cycle_interval=[max(0.,cycle-2*dx),cycle+2*dx],retention_pct=value,
                          reading_interval_pp=[value-2.5*dy,value+2.5*dy]))
    return marks


def window(marks,fraction):
    valid = [p for p in marks if p['cycle_interval'][1] <= fraction*HORIZON]
    assert len(valid) == (8 if fraction == .1 else 17)
    x = np.array([p['cycle_reading'] for p in valid])
    y = np.array([p['retention_pct'] for p in valid])
    return dict(marker_count=len(valid),features=dict(target_cycle_count=HORIZON,
                last_early_retention_pct=float(y[-1]),early_mean_retention_pct=float(y.mean()),
                early_retention_slope_per_1000_cycles=float(np.polyfit(x,y,1)[0]*1000),
                early_retention_range_pp=float(np.ptp(y)),early_observed_cycle_count=float(x[-1])))


def main():
    assert not OUT.exists()
    evidence = source_evidence()
    clean,trace,green = crop()
    marks = read_markers(trace,green)
    windows = {str(f):window(marks,f) for f in (.1,.2)}
    image = CACHE / 'NC3_Fig8C_early_mask.png'
    with image.open('xb') as stream:
        Image.fromarray(clean).save(stream,format='PNG')
    OUT.mkdir()
    result = dict(status='blind_input_reviewed_pending_prediction_freeze',source=evidence,
                  pdf=dict(local_cache=PAPER.relative_to(ROOT).as_posix(),sha256=PDF_SHA,page=5,embedded_size=[981,726]),
                  mask=dict(local_cache=image.relative_to(ROOT).as_posix(),sha256=sha(image),crop=CROP,
                            x0=X0,xN=XN,y100=Y100,y70=Y70,x_bound_px=2.,y_bound_px=2.5,
                            recipe='Only early window red pixels; no captions, legends or later plot region.'),
                  marker_method='Selected hollow glyph centers in the native early segment; require bright centre and red at both vertical sides.',
                  markers=marks,windows=windows,terminal_values_exposed_for_this_candidate=0,
                  acceptance='Provisional prospective candidate; source-family independence and generalization not established by one paper.',
                  new_fits=0,accepted_external_sources=0)
    with (OUT/'blind_early_input.json').open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(result,stream,ensure_ascii=False,indent=2,allow_nan=False)
        stream.write('\n')


if __name__ == '__main__':
    main()
