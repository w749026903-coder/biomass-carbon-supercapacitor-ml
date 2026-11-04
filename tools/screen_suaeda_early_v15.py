"""Reproduce the outcome-masked geometry screen for Zhao et al. Figures 13 and 14e.

Run with the local PDF rendering interpreter. The original PDF stays in the
ignored literature cache. Only early coloured pixels and provisional marker
centres are written. This screen does not create a training or scoring row.
"""
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
import pypdfium2 as pdfium

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / '.local-literature-cache/P15/suaeda_source.pdf'
OUT = ROOT / '保持率达标研究_v3_主线与近优组合_20261030/第十五轮_外部候选盲态核验_20261104'
DOI = '10.3390/nano16211412'
PDF_SHA = '324c3143535561ee031ec898c3d37e4ecc3890b09044de1c9c28928660b69b46'
HORIZON = 10000

# Pixel coordinates of the original embedded image. Major ticks were checked
# with axis-only views. Use each image's last embedded raster for these pages.
PANELS = {
    '3E': dict(page=12, figure='13', size=(1890, 1557), crop=(355, 39, 652, 405),
               x0=383.5, xN=1721.5, y0=1334.5, y100=65.5, radius=16, expected_markers=9),
    '2E': dict(page=13, figure='14e', size=(3823, 2098), crop=(1447, 1097, 1904, 1430),
               x0=1443.5, xN=3742., y0=1938.5, y100=1170., radius=14, expected_markers=8),
}


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def trace_mask(system, rgb):
    red, green, blue = np.moveaxis(rgb.astype(np.int16), 2, 0)
    if system == '3E':
        return (red > 100) & (red-green > 45) & (red-blue > 45)
    return (blue > 90) & (blue-red > 35) & (blue-green > 30)


def marker_centres(mask, radius, x_start, x_end):
    theta = np.linspace(0, 2*np.pi, 48, endpoint=False)

    def ring(r):
        offsets = zip(r*np.cos(theta), r*np.sin(theta))
        return np.mean([np.roll(mask, (round(y), round(x)), (0, 1)) for x,y in offsets], axis=0)

    inside = (ring(radius-2)+ring(radius-5))/2
    outside = (ring(radius+2)+ring(radius+4))/2
    score = inside-outside
    margin = radius+4
    score[:margin] = score[-margin:] = 0
    score[:,:margin] = score[:,-margin:] = 0
    score[:,:max(0,round(x_start))] = 0
    score[:,int(x_end)-4:] = 0
    score[(inside < .64) | (outside > .4)] = 0
    y_grid, x_grid = np.ogrid[:mask.shape[0], :mask.shape[1]]
    centres = []
    while len(centres) < 24:
        y, x = np.unravel_index(np.argmax(score), score.shape)
        if score[y,x] < .37:
            break
        centres.append((int(x), int(y), float(score[y,x])))
        score[(x_grid-x)**2+(y_grid-y)**2 < radius**2] = 0
    return sorted(centres)


def screen(document, system, panel):
    page = document[panel['page']-1]
    embedded = [x for x in page.get_objects() if x.type == pdfium.raw.FPDF_PAGEOBJ_IMAGE][-1]
    assert tuple(embedded.get_px_size()) == panel['size']
    x_start, y_start, x_stop, y_stop = panel['crop']
    cycle_per_pixel = HORIZON/(panel['xN']-panel['x0'])
    x_cut = panel['x0'] + .2*(panel['xN']-panel['x0'])
    assert x_stop-1 <= x_cut
    rgb = np.array(embedded.get_bitmap().to_pil().convert('RGB').crop(panel['crop']))
    mask = trace_mask(system, rgb)
    centres = marker_centres(mask, panel['radius'], panel['x0']-x_start, x_cut-x_start)
    assert len(centres) == panel['expected_markers']
    safe = np.full_like(rgb, 255)
    safe[mask] = rgb[mask]
    visual = Image.fromarray(safe)
    draw = ImageDraw.Draw(visual)
    rows = []
    for x,y,score in centres:
        draw.rectangle((x-2,y-2,x+2,y+2), outline='black')
        x += x_start
        y += y_start
        cycle = (x-panel['x0'])*cycle_per_pixel
        ordinate = 100*(panel['y0']-y)/(panel['y0']-panel['y100'])
        cycle_bound = 4*cycle_per_pixel
        ordinate_bound = 400/(panel['y0']-panel['y100'])
        rows.append(dict(pixel_center=[x,y],shape_match=score,cycle_reading=cycle,
                         cycle_interval=[max(0,cycle-cycle_bound),cycle+cycle_bound],
                         early_ordinate_pct=ordinate,ordinate_interval_pp=[ordinate-ordinate_bound,ordinate+ordinate_bound]))
    assert all(r['cycle_interval'][1] <= .2*HORIZON for r in rows)
    assert len({r['pixel_center'][0] for r in rows}) == len(rows)
    destination = OUT / f'{system}_前20pct_遮蔽标记.png'
    assert not destination.exists()
    visual.save(destination)
    return dict(system=system, panel=panel, visible_pixel_xmax=x_stop-1, max_allowed_early_x=x_cut,
                provisional_marker_count_10pct=sum(r['cycle_interval'][1]<=.1*HORIZON for r in rows),
                provisional_marker_count_20pct=len(rows), markers=rows,
                image=destination.name, image_sha256=sha(destination))


def main():
    assert sha(SOURCE) == PDF_SHA
    assert not (OUT/'early_marker_screen.json').exists()
    OUT.mkdir(parents=True, exist_ok=True)
    document = pdfium.PdfDocument(SOURCE)
    try:
        assert len(document) == 16 and DOI in document[0].get_textpage().get_text_range()
        result = [screen(document, system, panel) for system,panel in PANELS.items()]
    finally:
        document.close()
    record = dict(status='geometry_screen_only', doi=DOI, paper_source_count=1, original_pdf_sha256=PDF_SHA,
                  article_url='https://www.mdpi.com/2079-4991/16/21/1412',
                  license='CC BY 4.0; masked crops derived from Zhao et al. Figures 13 and 14e',
                  image_processing='Pixel crop through nominal 20%, red/blue channel threshold, circle-ring candidate detector. Only the shown early colours and center boxes are visible.',
                  marker_bound='Provisional four-pixel geometry allowance, not a measurement confidence interval. Border-clipped and overlapping markers can be missed.',
                  full_prediction_input_frozen=False, terminal_ordinates_exported=0, training_rows_added=0, panels=result)
    with (OUT/'early_marker_screen.json').open('x', encoding='utf8') as stream:
        json.dump(record, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print([(p['system'],p['provisional_marker_count_10pct'],p['provisional_marker_count_20pct']) for p in result])


if __name__ == '__main__':
    main()
