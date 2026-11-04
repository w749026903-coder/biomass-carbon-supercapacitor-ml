"""Extract the reviewed DDHPC Fig. 5(d) markers from the open publisher PDF."""

from pathlib import Path
import hashlib
import json

import numpy as np
import pypdfium2 as pdf

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / '.local-literature-cache/P20'
BASE = ROOT / '保持率达标研究_v3_主线与近优组合_20261030'
OUT = BASE / '第二十轮_DDHPC双电极刊本补证_20261105'
BUCKET = 'https://pmc-oa-opendata.s3.amazonaws.com/PMC9075029.1/'
DOI = '10.1039/c9ra06603a'
HORIZON = 5000
X0, XN, Y0, Y200 = 548., 889.5, 717., 461.
BOUND_X, BOUND_Y, BOUND_AXIS = 3., 4., 1.


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source(name, url, expected):
    path = CACHE / name
    assert digest(path) == expected
    return dict(local_cache=path.relative_to(ROOT).as_posix(), sha256=expected, url=url)


def read_page(doc, i):
    return ' '.join(doc[i].get_textpage().get_text_range().split())


def read_pdf():
    with pdf.PdfDocument(CACHE / 'DDHPC.pdf') as doc:
        assert len(doc) == 8 and DOI in read_page(doc, 0).lower()
        assert 'two-electrode system' in read_page(doc, 2)
        assert '10 A g' in read_page(doc, 5) and '5000 cycles' in read_page(doc, 5)
        assert '77%, 72%, 65%, and 56%' in read_page(doc, 6)
        image, = [o for o in doc[5].get_objects() if o.type == pdf.raw.FPDF_PAGEOBJ_IMAGE and o.get_px_size() == (912, 784)]
        rgb = np.array(image.get_bitmap().to_pil().convert('RGB'), dtype=np.int16)
    with pdf.PdfDocument(CACHE / 'DDHPC_SI.pdf') as si:
        assert len(si) == 6 and 'DDHPC-kh' in read_page(si, 2)
        assert all('cycle' not in read_page(si, i).lower() for i in range(len(si)))
    return rgb


def capacitance(y):
    return (Y0 - y) * 200. / (Y0 - Y200)


def ratio_box(y, ref):
    lower = 100 * (Y0 - BOUND_AXIS - y - BOUND_Y) / (Y0 - BOUND_AXIS - ref + BOUND_Y)
    upper = 100 * (Y0 + BOUND_AXIS - y + BOUND_Y) / (Y0 + BOUND_AXIS - ref - BOUND_Y)
    return [lower, upper]


def marker(x, y, mask, ref):
    run = np.flatnonzero(mask[y-6:y+7, x]) + y - 6
    assert len(run) >= 6 and abs(np.median(run) - y) <= .5
    scale = HORIZON / (XN - X0)
    return dict(pixel=[x, y], column_color_span_px=[int(run.min()), int(run.max())],
                cycle_reading=(x - X0) * scale, cycle_interval=[(x - X0 - BOUND_X)*scale, (x - X0 + BOUND_X)*scale],
                capacitance_F_g=capacitance(y), early_ordinate_pct=100 * (Y0-y)/(Y0-ref),
                ordinate_interval_pp=ratio_box(y, ref))


def summarize(points, fraction):
    eligible = [p for p in points if p['cycle_interval'][1] <= fraction * HORIZON]
    assert len(eligible) == (3 if fraction == .1 else 4)
    x = np.array([p['cycle_reading'] for p in eligible])
    y = np.array([p['early_ordinate_pct'] for p in eligible])
    return dict(actual_marker_count=len(eligible), last_early_retention_pct=float(y[-1]),
                early_mean_retention_pct=float(y.mean()),
                early_retention_slope_per_1000_cycles=float(np.polyfit(x, y, 1)[0]*1000),
                early_retention_range_pp=float(np.ptp(y)), early_observed_cycle_count=float(x[-1]),
                target_cycle_count=HORIZON)


def develop(name, color, mask, upper_band, centers, terminal, reported, bet):
    top = min(np.flatnonzero(mask[slice(*upper_band), x])[0] + upper_band[0] for x in (547, 548, 549))
    assert top in (518, 457)
    # Add four pixels from the visible upper edge to the estimated square centre. The
    # left boundary obscures the full shape, so this is a shared graph reference box.
    ref = int(top + 4)
    points = [marker(x, y, mask, ref) for x, y in zip((561, 568, 575, 582), centers, strict=True)]
    endpoint = marker(887, terminal, mask, ref)
    assert endpoint['cycle_interval'][0] <= HORIZON <= endpoint['cycle_interval'][1]
    lo, hi = endpoint['ordinate_interval_pp']
    assert lo <= reported <= hi
    return dict(sample_name=name, color=color, status='ready_for_separately_frozen_2E_development_sensitivity',
                author_retention_pct=reported, author_precision='integer; results use about; conclusion repeats integer',
                reference=dict(upper_edge_y_px=int(top), center_y_px=ref, center_y_interval_px=[ref-4,ref+4],
                               graph_C_ref_F_g=capacitance(ref), author_baseline_cycle=None),
                points=points, terminal_compatibility=endpoint,
                windows={str(f): summarize(points,f) for f in (.1,.2)},
                static_features=dict(reported_current_A_g=10., electrolyte='H2SO4', concentration_mol_L=1.,
                                     BET_m2_g=bet, cycle_voltage_lower_V=0., cycle_voltage_upper_V=1., reference_electrode=None))


def main():
    sources = dict(published_pdf=source('DDHPC.pdf', BUCKET+'PMC9075029.1.pdf',
                                       '9d7d5881da4f6881d5a86a833bb09ad64eb29fcafe1a9224e2af672947b95983'),
                   supplementary_pdf=source('DDHPC_SI.pdf', BUCKET+'RA-009-C9RA06603A-s001.pdf',
                                            '14cdfcea14031ed7fee66adcfd82bf44718904c48036df1d12209ad5be3eb3b8'),
                   open_archived_preview=source('DDHPC_f5.jpg', BUCKET+'c9ra06603a-f5.jpg',
                                                'fd63edf63b0ba9c0be6238811f3d5dcf18081e03ab594a5251ad39060e35b635'))
    a = read_pdf()
    r,g,b = np.moveaxis(a, 2, 0)
    blue = (b>78)&(b-r>28)&(b-g>24)&(r-g<38)
    purple = (r>95)&(b>90)&(r-g>35)&(b-g>34)&(r>b-22)
    records = [develop('DDHPC-3kh','blue',blue,(515,550),(534,536,539,541),590,65.,2204.),
               develop('DDHPC-4kh','purple',purple,(450,490),(495,502,508,512),572,56.,2502.)]
    for name, y in [('DDHPC-1kh',77),('DDHPC-2kh',72)]:
        records.append(dict(sample_name=name, author_retention_pct=y, status='held_overlap_at_left_axis',
                            reason='Red and black first-marker geometry is not separately auditable at the left axis.'))
    efb = CACHE / 'EFB_fig8.jpg'
    efb_sha = digest(efb)
    OUT.mkdir(exist_ok=True)
    with (OUT / 'curve_evidence.json').open('x', encoding='utf-8', newline='\n') as file:
        json.dump(dict(status='development_evidence_ready_no_fits', doi=DOI, source_family='doi:'+DOI, system='2E',
                       n_cycles=HORIZON, reported_current_mass_basis=None, symmetry_explicit=None, fits=0, external_sources=0,
                       sources=sources, figure=dict(page=6,panel='Fig.5(d)',size=[912,784],rgb_sha256=hashlib.sha256(a.astype(np.uint8).tobytes()).hexdigest(),
                                                  x0=X0,xN=XN,y0=Y0,y200=Y200,bounds_px=dict(x=BOUND_X,y=BOUND_Y,axis_y=BOUND_AXIS)),
                       input_rule='Visible square centers only. Clipped initial point supplies a conservative graph reference but no input point. Boundary-overlapping points excluded. Author endpoints separate from graph ratios.',
                       samples=records,
                       EFB=dict(doi='10.1016/j.nxmate.2026.101640',role='held_early_marks_and_cycle_protocol',
                                native_fig8_sha256=efb_sha,local_cache=efb.relative_to(ROOT).as_posix(),
                                native_fig8_url='https://ars.els-cdn.com/content/image/1-s2.0-S2949822826000572-gr8_lrg.jpg',
                                reason='Connected lines without distinct point glyphs; paper gives CV reference separately, but actual cycle settings need direct binding.')),
                  file, ensure_ascii=False, indent=2, allow_nan=False)
        file.write('\n')


if __name__ == '__main__':
    main()
