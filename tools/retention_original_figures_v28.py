"""Read retention markers from SSC-700 Fig. 7(g) and onion carbon Fig. 11(c)."""

import json
from hashlib import sha256
from pathlib import Path
from statistics import mean
import sys

from PIL import Image
import pypdfium2 as pdf


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.retention_suaeda_case_v16 import feature_row

CACHE = ROOT / '.local-literature-cache/P28'
PII = 'S0926669022003892'
ASSET = f'https://ars.els-cdn.com/content/image/1-s2.0-{PII}-'
FIG7_SHA = '8ef4859e961c1dc3f9b8905b342760de8368f34abe43026df1bc90d5be31f84f'
FIG8_SHA = '13e94ab5fbf88ac5944a29295ffb87a0efac216926e912ccca352708643326c4'
PANEL = (2320, 675, 3200, 1325)
X_TICKS = (128., 253.5, 379.5, 506.5, 632., 759.5)
Y_TICKS = (549., 443., 337., 233., 127., 21.)
MARKER_Y_SEEDS = (22, 33, 43, 53, 59, 69, 75, 82, 90, 98, 106, 111, 115, 122, 133,
                  139, 147, 151, 155, 158, 160)
PIXEL_HALF_WIDTH = 3.
ONION_PDF = ROOT / '三电极端点扩充_20261018/corpus/B_R112/main.pdf'
ONION_SHA = '1896ad67cd384bb3e8ca07ab4bd53177ea0d0e479f17ed6983dda00f216023f3'


def asset_info(filename, url, expected):
    path = CACHE / filename
    assert sha256(path.read_bytes()).hexdigest() == expected
    with Image.open(path) as img:
        size = list(img.size)
        img.verify()
    return dict(path=path.relative_to(ROOT).as_posix(), url=url, sha256=expected, size_px=size)


def centers(panel, cutoff):
    for index, y_seed in enumerate(MARKER_Y_SEEDS):
        x_seed = round(X_TICKS[0] + (X_TICKS[-1] - X_TICKS[0]) * index / 20)
        pixels = [(x, y) for x in range(x_seed-10, x_seed+11)
                  for y in range(max(y_seed-10, 18), y_seed+11) if panel.getpixel((x, y)) < cutoff]
        assert 80 < len(pixels) < 180
        x, y = zip(*pixels)
        assert min(x) > x_seed-10 and max(x) < x_seed+10
        yield (mean(x), mean(y), len(pixels))


def calculate_ssc():
    fig7 = asset_info('gr7__lrg.jpg', ASSET+'gr7_lrg.jpg', FIG7_SHA)
    fig8 = asset_info('gr8__lrg.jpg', ASSET+'gr8_lrg.jpg', FIG8_SHA)
    assert fig7['size_px'] == [3493, 1337] and fig8['size_px'] == [3493, 1819]
    with Image.open(ROOT / fig7['path']) as fig:
        panel = fig.crop(PANEL).convert('L')
    x_to_cycle = 10000. / (X_TICKS[-1] - X_TICKS[0])
    y_to_pct = 100. / (Y_TICKS[0] - Y_TICKS[-1])
    assert all(abs((x-X_TICKS[0])*x_to_cycle - i*2000) < x_to_cycle*2 for i, x in enumerate(X_TICKS))
    assert all(abs((Y_TICKS[0]-y)*y_to_pct - i*20) < y_to_pct*2 for i, y in enumerate(Y_TICKS))
    main = list(centers(panel, 100))
    alternative = [list(centers(panel, t)) for t in (80, 120)]
    markers = []
    for index, (x, y, count) in enumerate(main):
        max_shift = max(abs(a[index][j]-v) for a in alternative for j, v in enumerate((x, y)))
        assert max_shift < 1
        cycle = (x-X_TICKS[0])*x_to_cycle
        retention = (Y_TICKS[0]-y)*y_to_pct
        markers.append(dict(index=index, center_px=[x, y], dark_pixels=count, contrast_shift_max_px=max_shift,
                            cycle_coordinate=cycle, cycle_bounds=[max(0., cycle-PIXEL_HALF_WIDTH*x_to_cycle),
                                                                  cycle+PIXEL_HALF_WIDTH*x_to_cycle],
                            retention_pct=retention, retention_bounds_pct=[retention-PIXEL_HALF_WIDTH*y_to_pct,
                                                                          retention+PIXEL_HALF_WIDTH*y_to_pct],
                            usable_shape_marker=index != 0))
    assert all(a['cycle_bounds'][1] < b['cycle_bounds'][0] for a, b in zip(markers, markers[1:]))
    terminal = markers[-1]
    assert terminal['cycle_bounds'][0] <= 10000 <= terminal['cycle_bounds'][1]
    assert terminal['retention_bounds_pct'][0] <= 73.97 <= terminal['retention_bounds_pct'][1]
    windows = {str(f): [p['index'] for p in markers if p['usable_shape_marker'] and p['cycle_bounds'][1] <= f*10000]
               for f in (.1, .2)}
    assert windows == {'0.1': [1], '0.2': [1, 2, 3]}
    early20 = [dict(cycle_interval=markers[i]['cycle_bounds'], cycle_reading=markers[i]['cycle_coordinate'],
                    early_ordinate_pct=markers[i]['retention_pct']) for i in windows['0.2']]
    candidate, count = feature_row(early20, 10000, .2)
    assert count == 3
    return dict(doi='10.1016/j.indcrop.2022.114906', source_family='doi:10.1016/j.indcrop.2022.114906',
                publisher_pii=PII,
                fig7=fig7, fig8=fig8, fig7g_crop_ltrb=PANEL, x_tick_pixels_0_to_10000=X_TICKS,
                y_tick_pixels_0_to_100_pct=Y_TICKS, grayscale_cutoff=100, contrast_check_cutoffs=[80, 120],
                conservative_half_width_px=PIXEL_HALF_WIDTH,
                read_bounds_role='Image-reading bounds only, not statistical confidence intervals.',
                figure_role='Black dots are author-plotted retention observations. No interpolated points.',
                markers=markers, window_indices=windows, excluded_first='Marker meets top plot border.',
                excluded_boundary='Upper x bounds of markers 2 and 4 cross 1000 and 2000 respectively.',
                early20_held_candidate_features=candidate, early10_minimum_point_rule_met=False,
                author_endpoint_3E=dict(sample='SSC-700', cycle_count=10000, retention_pct=73.97,
                                       cycle_current_A_g=None, evidence='Publisher abstract and matching Fig. 7(g) geometry.'),
                separate_author_endpoint_2E=dict(sample='SSC-700 symmetric device', cycle_count=5000,
                                                 reported_loss_pct=0.5, panel='Fig. 8(d)', cycle_current_A_g=None),
                protocol_evidence=dict(primary_abstract_current_for_specific_capacitance_A_g=0.5,
                                       secondary_citation_cycle_current_A_g=10.,
                                       secondary_citation_doi='10.1007/s10854-025-16551-8',
                                       another_secondary_table_doi='10.1039/d4ya00076e',
                                       another_secondary_table_conflict='Same 10 A/g but labels row Two, unlike original abstract.',
                                       secondary_is_locator_only=True,
                                       cycle_voltage_window_V=None, reference_electrode=None, current_mass_basis=None),
                status='known_endpoint_development_evidence_held_for_primary_cycling_protocol',
                training_admissions=0, fitted_models=0, accepted_external_sources=0)


def onion_red_center(im, x0, y0, cutoff):
    points = []
    for y in range(y0-7, y0+8):
        for x in range(x0-4, min(x0+5, 789)):
            r, g, b = im.getpixel((x, y))
            if r > 85 and r-g > cutoff and r-b > cutoff-8:
                points.append((x, y))
    minimum = 30 if x0 >= 785 else 75
    assert minimum < len(points) < 135
    x, y = zip(*points)
    return mean(x), mean(y), len(points)


def calculate_onion():
    assert sha256(ONION_PDF.read_bytes()).hexdigest() == ONION_SHA
    with pdf.PdfDocument(ONION_PDF) as doc:
        def page_text(index):
            return ' '.join(doc[index].get_textpage().get_text_range().split())

        assert '10.1016/j.diamond.2024.111703' in page_text(0)
        assert '100 % capacity retention over 1000 cycles in the three-electrode system' in page_text(0)
        assert 'over 1000 cycles at 6 A/g' in page_text(8)
        assert 'two identical biochar-based electrodes' in page_text(2) and '1 M H2SO4' in page_text(2)
        assert 'Act_OFSCBC recorded a surface area of 2538.31' in page_text(4)
        body = page_text(9)
        assert '10,000 cycles at a current density of 6 A/g' in body and 'voltage range of 0–1 V' in body
        assert '90.77 % at the 5000th cycle and 74.40 % at the 10000th cycle' in body
        page = doc[12]
        assert 'Cyclability at 6 A/g for 10,000 cycles' in page_text(12)
        bitmap, = [o for o in page.get_objects() if o.type == pdf.raw.FPDF_PAGEOBJ_IMAGE and o.get_px_size() == (1582, 1244)]
        im = bitmap.get_bitmap().to_pil().convert('RGB')
    x_start, x_end, y_zero, y_hundred = 127.5, 786., 1136., 757.5
    x_scale, y_scale = 10000/(x_end-x_start), 100/(y_zero-y_hundred)
    early_y = (741, 745, 801, 786, 794, 793, 798, 804, 784, 778)
    samples = [(i, round(x_start+(x_end-x_start)*i/50), y) for i, y in enumerate(early_y, 1)]
    samples.extend([(25, 456, 791), (50, 786, 852)])
    markers = []
    for i, sx, sy in samples:
        x, y, count = onion_red_center(im, sx, sy, 42)
        alternatives = [onion_red_center(im, sx, sy, t) for t in (32, 52)]
        max_shift = max(abs(v-a[j]) for a in alternatives for j, v in enumerate((x, y)))
        assert max_shift < 1.2
        cycle, retention = (x-x_start)*x_scale, (y_zero-y)*y_scale
        markers.append(dict(index=i, center_px=[x, y], dark_red_pixels=count, contrast_shift_max_px=max_shift,
                            cycle_reading=cycle, cycle_interval=[cycle-3*x_scale, cycle+3*x_scale],
                            early_ordinate_pct=retention, ordinate_interval_pp=[retention-3*y_scale, retention+3*y_scale]))
    assert all(a['cycle_reading'] < b['cycle_reading'] for a, b in zip(markers, markers[1:]))
    for marker, (n, author) in zip(markers[-2:], [(5000, 90.77), (10000, 74.40)]):
        assert marker['cycle_interval'][0] <= n <= marker['cycle_interval'][1]
        assert marker['ordinate_interval_pp'][0] <= author <= marker['ordinate_interval_pp'][1]
    windows = {str(f): dict(features=features, markers=count) for f in (.1, .2)
               for features, count in [feature_row(markers, 10000, f)]}
    assert [r['markers'] for r in windows.values()] == [4, 9]
    source = 'doi:10.1016/j.diamond.2024.111703'
    sample = 'Act_OFSCBC//Act_OFSCBC'
    return dict(status='ready_for_separately_frozen_2E_development_sensitivity', source_family=source,
                pdf=ONION_PDF.relative_to(ROOT).as_posix(), pdf_sha256=ONION_SHA,
                publisher='https://www.sciencedirect.com/science/article/pii/S0925963524009166',
                figure='Fig. 11(c), PDF p.13, original embedded figure 1582 × 1244 px',
                protocol_locator='PDF p.3 two identical electrodes and electrolyte; p.10 cycling; p.5 Table 2 BET.',
                axis_pixels=dict(x0=x_start, x10000=x_end, y0=y_zero, y100=y_hundred),
                conservative_half_width_px=3, markers=markers, windows=windows,
                exclusions=('Border-crossing first marker withheld. Boundary markers near 1000 and 2000 cross '
                            'the strict upper-bound criterion. The final marker meets the frame and corroborates the '
                            'author endpoint only. The 5000-cycle value belongs to the same trajectory.'),
                known_endpoint=dict(sample_name=sample, system='2E', target_cycle_count=10000, retention_pct=74.40),
                same_test_5000_retention_pct=90.77, current_mass_basis=None,
                figure_inset_note='GCD inset says vs Ag/AgCl. Do not infer a reference electrode for the explicit two-electrode device.',
                separate_3E=dict(cycles=1000, retention_pct=100, current_A_g=6, locator='PDF p.9 Fig. 9 result'),
                static_features=dict(reported_current_A_g=6., electrolyte='H2SO4', concentration_mol_L=1.,
                                     BET_m2_g=2538.31, cycle_voltage_lower_V=0., cycle_voltage_upper_V=1.,
                                     reference_electrode=None),
                canonical_admissions=0, fitted_models=0, accepted_external_sources=0)


if __name__ == '__main__':
    print(json.dumps({'SSC700': calculate_ssc(), 'onion_2E': calculate_onion()}, ensure_ascii=False, indent=2,
                     allow_nan=False))
