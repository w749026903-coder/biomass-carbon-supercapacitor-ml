"""Audit SD-AC retention in two configurations from publisher PDF and SI."""

from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
from statistics import mean, median
import sys
from zipfile import ZipFile

from PIL import Image
import pypdfium2 as pdf

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.retention_suaeda_case_v16 import feature_row

SOURCE = 'doi:10.3390/nano12050810'
CACHE = ROOT / '.local-literature-cache/P30'
PDF = CACHE / 'sd_archive.pdf'
SI = ROOT / '三电极端点扩充_20261018/new_sources/PMC8912637/figures_and_supplements.zip'
PDF_SHA = 'dff79cdc804f7abb75ce4dc9bd577f98ab653df66133670c09732427422cd05e'
SI_SHA = '8b2502485539c06ec11266bc01376034f041262e84adbda2f7586f18195fd133'
PARAMETERS = {
    '3E': dict(page=7, figure='6(e)', width=2118, x0=812., x10000=2080., y0=959.5, y100=555.5,
               early_roi=(816, 550, 1072, 620), terminal_band=(598, 616), author=87.03),
    '2E': dict(page=8, figure='7(e)', width=2135, x0=806.5, x10000=2094., y0=967.5, y100=560.,
               early_roi=(811, 552, 1071, 616), terminal_band=(634, 650), author=80.),
}


def page_text(page):
    return ' '.join(page.get_textpage().get_text_range().split())


def figure_from_strips(page, width):
    objects = sorted([o for o in page.get_objects() if o.type == pdf.raw.FPDF_PAGEOBJ_IMAGE],
                     key=lambda o:o.get_bounds()[3], reverse=True)
    assert [o.get_px_size() for o in objects] == [(width,355),(width,355),(width,354)]
    assert all(abs(a.get_bounds()[1]-b.get_bounds()[3]) < .001 for a,b in zip(objects,objects[1:]))
    fig = Image.new('RGB',(width,1064))
    for i,o in enumerate(objects):
        fig.paste(o.get_bitmap().to_pil().convert('RGB'),(0,355*i))
    return fig


def ring_holes(fig, roi, white_threshold):
    left, top, right, bottom = roi
    remaining = {(x,y) for y in range(top,bottom) for x in range(left,right)
                 if min(fig.getpixel((x,y))) >= white_threshold}
    result = []
    while remaining:
        stack, group = [remaining.pop()], []
        while stack:
            x,y = stack.pop()
            group.append((x,y))
            for pt in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)):
                if pt in remaining:
                    remaining.remove(pt)
                    stack.append(pt)
        if 2 <= len(group) <= 65 and all(left < x < right-1 and top < y < bottom-1 for x,y in group):
            xs,ys = zip(*group)
            result.append((mean(xs),mean(ys),len(group)))
    return sorted(result)


def curve(fig, cfg):
    x0,x1,y0,y1 = (cfg[k] for k in ('x0','x10000','y0','y100'))
    cycle_scale, y_scale = 10000/(x1-x0), 100/(y0-y1)
    markers = []
    base = ring_holes(fig,cfg['early_roi'],145)
    alternate = ring_holes(fig,cfg['early_roi'],165)
    for x,y,n in base:
        matches = [(a,b,c) for a,b,c in alternate if abs(a-x)<1 and abs(b-y)<1]
        assert len(matches) == 1
        cyc,r = (x-x0)*cycle_scale,(y0-y)*y_scale
        markers.append(dict(index=len(markers), center_px=[x,y], white_pixels=n, checked_center_px=list(matches[0][:2]),
                            cycle_reading=cyc, cycle_interval=[cyc-2*cycle_scale,cyc+2*cycle_scale],
                            early_ordinate_pct=r, ordinate_interval_pp=[r-2*y_scale,r+2*y_scale]))
    assert all(a['cycle_interval'][1] < b['cycle_interval'][0] for a,b in zip(markers,markers[1:]))
    # The terminal stroke abuts the plot boundary; verify the author label against its colored band.
    low,high = cfg['terminal_band']
    red_pixels = [(x,y) for x in range(int(x1)-9,int(x1)-3) for y in range(low,high)
                  if (p:=fig.getpixel((x,y)))[0]>130 and p[0]-p[1]>85 and p[0]-p[2]>85]
    ys = [y for _,y in red_pixels]
    assert len(ys)>35
    terminal = [(y0-max(ys)-2)*y_scale,(y0-min(ys)+2)*y_scale]
    assert terminal[0] <= cfg['author'] <= terminal[1]
    windows = {}
    for f in (.1,.2):
        features,n = feature_row(markers,10000,f)
        windows[str(f)] = dict(features=features,markers=n)
    return dict(markers=markers, windows=windows, terminal_band_pct=terminal,
                terminal_stroke_median_pct=(y0-median(ys))*y_scale,
                unmatched_alternate_only=len(alternate)-len(base),
                read_bound='Geometric pixel half-width ±2; no invented missing dots or exact cycle grid.')


def calculate():
    assert sha256(PDF.read_bytes()).hexdigest() == PDF_SHA
    assert sha256(SI.read_bytes()).hexdigest() == SI_SHA
    with ZipFile(SI) as a, ZipFile(BytesIO(a.read('nanomaterials-12-00810-s001.zip'))) as b:
        name, = b.namelist()
        supplemental = b.read(name)
    si_sha = sha256(supplemental).hexdigest()
    assert si_sha == '386fe50afd55521109538af5fc584c6a6da5b100083cad08eb5eacf4134d772b'
    with pdf.PdfDocument(supplemental) as doc:
        text = page_text(doc[1])
        assert 'This work (SD-AC) Chinese fir sawdust 3 M KOH' in text
        assert 'This work Chinese fir sawdust 19.9 650 80%' in text
    records = {}
    with pdf.PdfDocument(PDF) as doc:
        assert SOURCE[4:] in page_text(doc[0])
        all_text = ' '.join(page_text(p) for p in doc)
        assert 'setup in 3 M KOH solution' in all_text
        assert 'SD-AC electrode in a three-electrode test' in page_text(doc[6])
        assert 'tested in a two-electrode system' in all_text
        assert '87.03% capacitance over 10,000 cycles' in all_text and 'about 80.0% of capacitance' in all_text
        for system,cfg in PARAMETERS.items():
            page = doc[cfg['page']-1]
            caption_page = page_text(page).lower()
            assert all(x in caption_page for x in ('cycling', '10 a g−1', '10,000 cycles'))
            fig = figure_from_strips(page,cfg['width'])
            readout = curve(fig,cfg)
            records[system] = dict(source_family=SOURCE, system=system, target_cycle_count=10000,
                    sample_name='SD-AC' if system=='3E' else 'SD-AC//SD-AC',
                    author_retention_pct=cfg['author'], author_approximate=system=='2E', figure_geometry=cfg,
                    static_features=dict(reported_current_A_g=10., BET_m2_g=621.,
                        electrolyte='KOH' if system=='3E' else None,concentration_mol_L=3. if system=='3E' else None,
                        cycle_voltage_lower_V=None,cycle_voltage_upper_V=None,reference_electrode=None),
                    current_mass_basis=None, **readout)
    assert [len(x['markers']) for x in records.values()] == [39,39]
    return dict(pdf=PDF.relative_to(ROOT).as_posix(),pdf_sha256=PDF_SHA,
        publisher_pdf='https://pmc-oa-opendata.s3.amazonaws.com/PMC8912637.1/PMC8912637.1.pdf',
        si_package=SI.relative_to(ROOT).as_posix(),si_package_sha256=SI_SHA,si_pdf_member=name,si_pdf_sha256=si_sha,
        records=records,
        boundary_3E='Reference is Hg/HgO in Methods but SCE in Figure 6(a,c); actual cycling reference unresolved.',
        boundary_2E='3 M KOH is explicit for 3E; the device section and SI Table S2 do not separately bind electrolyte concentration.',
        ready_for_separately_frozen_development=['3E','2E'],
        role='Same study and final material; separate test configurations, one study for any cross-route comparison.',
        new_fits=0, canonical_admissions=0, external_acceptances=0)


if __name__ == '__main__':
    print(json.dumps(calculate(),ensure_ascii=False,indent=2,allow_nan=False))
