"""Verify native plots and prepare the disclosed AC-CSS record for development."""

from io import BytesIO
from pathlib import Path
import sys
from zipfile import ZipFile

import numpy as np
from pypdf import PdfReader
from pypdf.generic import ContentStream

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.retention_blind_geometry_v32 import ASSETS, CACHE, OUT as P32, ROOT, read, sha, write
from tools.retention_blind_reserve_v22 import db_matches
from tools.retention_suaeda_case_v16 import feature_row


OUT = P32.parent / '第三十三轮_刊本原图盲态复核_20261105'
DOI = '10.3390/nano12152647'
X_TICKS = (229.62, 270.72, 311.70, 352.74, 393.78, 434.82)
Y_TICKS = (560.30, 586.40, 612.56, 638.72, 664.88, 691.04, 717.20)
COLORS = {
    (1., .715, .078): ('3 mM MHQ', 'quinone_modified_electrolyte'),
    (.5,): ('YP-80F', 'commercial_reference'),
    (.547, .375, 0.): ('2.3 M MHQ', 'quinone_modified_electrolyte'),
    (0., .621, .449): ('3 mM pBQ', 'quinone_modified_electrolyte'),
    (.336, .707, .914): ('AC-CSS', 'development_only_author_reported'),
    (0., .383, .277): ('0.1 M pBQ', 'quinone_modified_electrolyte'),
    (.941, .895, .258): ('3 mM CA', 'quinone_modified_electrolyte'),
}


def coffee_raster():
    pdf = PdfReader(CACHE / 'coffee_publisher_sealed.pdf')
    page = pdf.pages[10]
    form = page['/Resources']['/XObject']['/Im13'].get_object()
    operations = ContentStream(form, pdf).operations
    strips = []
    for (matrix, transform), (args, operator) in zip(operations, operations[1:]):
        if (transform, operator) != (b'cm', b'Do') or abs(float(matrix[4]) - 302.52) > 0.001:
            continue
        if form['/Resources']['/XObject'][args[0]].get_object().get('/Width') == 1729:
            strips.append(np.asarray(page.images[('/Im13', args[0])].image.convert('RGB')))
    pixels = np.concatenate(strips)
    assert len(strips) == 31 and pixels.shape == (1323, 1729, 3)
    dark = pixels.max(axis=2) < 100
    x_ticks = (342.5, 565., 787.5, 1010., 1232.5, 1454.5)
    low_y_ticks = (1077.5, 915., 752.5, 590.5, 427.5)
    assert all(dark[1115:1124, round(x)].sum() >= 7 for x in x_ticks)
    assert all(dark[round(y), 295:305].sum() >= 7 for y in low_y_ticks)
    assert dark[232, 295:305].sum() >= 7
    return dict(panel='Fig. 6(b)', shape_px=[1729, 1323], x_tick_cycles=list(range(0, 10001, 2000)),
                x_tick_px=x_ticks, low_y_tick_F_g=[0, 50, 100, 150, 200], low_y_tick_px=low_y_ticks,
                upper_y_label_F_g=400, upper_y_tick_px=232, broken_y_axis=True, used_for_features=False)


def vector_tick_centers(operations, start, stop, tick_direction):
    x = y = 0.
    centers = []
    for operands, op in operations[start:stop]:
        if op == b'cm':
            assert list(operands[:4]) == [1, 0, 0, 1]
            x += float(operands[4])
            y += float(operands[5])
        if op == b'l' and list(map(float, operands)) == tick_direction:
            centers.append(x if tick_direction[0] == 0 else y)
    return centers


def coffee_vectors():
    with ZipFile(CACHE / 'coffee_si_sealed.zip') as zip_file:
        member, = zip_file.infolist()
        page = PdfReader(BytesIO(zip_file.read(member))).pages[2]
    operations = page.get_contents().operations
    assert 'Capacitance retention over 10000 cycles' in page.extract_text()
    assert np.allclose(vector_tick_centers(operations, 96, 139, [0., -3.42]), X_TICKS, atol=.01)
    assert np.allclose(vector_tick_centers(operations, 150, 205, [-3.42, 0.]), Y_TICKS, atol=.01)
    trace_markers = {}
    color = None
    for i, (args, op) in enumerate(operations[:1811]):
        if op == b'scn':
            color = tuple(map(float, args))
        if op != b'cm' or color not in COLORS:
            continue
        if [op for _, op in operations[i + 1:i + 7]] != [b'm', b'c', b'c', b'c', b'c', b'b*']:
            continue
        vertices = np.asarray([a[-2:] for a, _ in operations[i + 1:i + 6]], dtype=float)
        assert np.all((np.ptp(vertices, axis=0) > 3.7) & (np.ptp(vertices, axis=0) < 4.3))
        x, y = (vertices.min(axis=0) + vertices.max(axis=0)) / 2 + np.asarray(args[4:], dtype=float)
        trace_markers.setdefault(color, []).append((x, y))
    assert set(trace_markers) == set(COLORS)
    cycle_scale = 10000. / (X_TICKS[-1] - X_TICKS[0])
    retention_scale = 100. / (Y_TICKS[5] - Y_TICKS[0])
    traces = {}
    for color, (label, role) in COLORS.items():
        points = []
        assert len(trace_markers[color]) == 18
        for index, (x, y) in enumerate(trace_markers[color]):
            cycle = (x - X_TICKS[0]) * cycle_scale
            retention = (y - Y_TICKS[0]) * retention_scale
            dx, dy = .30 * cycle_scale, .60 * retention_scale
            points.append(dict(index=index, center_pdf_pt=[x, y], cycle_reading=cycle,
                               cycle_interval=[max(0., cycle-dx), cycle+dx], ordinate_retention_pct=retention,
                               ordinate_interval_pp=[retention-dy, retention+dy]))
        assert points[0]['cycle_interval'][0] == 0 and abs(points[0]['ordinate_retention_pct']-100.) < .01
        assert points[-1]['cycle_interval'][0] <= 10000 <= points[-1]['cycle_interval'][1]
        assert np.all(np.diff([r['cycle_reading'] for r in points]) > 0)
        traces[label] = dict(role=role, color_operands=color, markers=points)
    neat = traces['AC-CSS']['markers']
    terminal = neat[-1]
    assert abs(terminal['ordinate_retention_pct']-75) <= 1.0
    # Shared normalization origin is retained as evidence, separate from measured early features.
    windows = {}
    for f in (.1, .2):
        eligible = [dict(cycle_reading=p['cycle_reading'], cycle_interval=p['cycle_interval'],
                         early_ordinate_pct=p['ordinate_retention_pct']) for p in neat[1:-1]
                    if p['cycle_interval'][1] <= 10000*f]
        features, n = feature_row(eligible, 10000, f)
        windows[str(f)] = dict(features=features, markers=n)
    assert [w['markers'] for w in windows.values()] == [6, 8]
    return traces, windows


def pomelo_geometry(receipt):
    pdf = PdfReader(CACHE / 'pomelo_publisher_sealed.pdf')
    report = {}
    for name, color in [('pomelo3e', 'blue'), ('pomelo2e', 'orange')]:
        panel = receipt['early_geometry'][name]
        image = pdf.pages[panel['publisher_pdf_page'] - 1].images[0].image
        runs = {}
        for window, evidence in panel['windows'].items():
            red, green, blue = np.asarray(image.crop(evidence['bounds_ltrb']).convert('RGB'), dtype=np.int16).transpose(2, 0, 1)
            mask = ((blue-red > 55) & (blue-green > 45)) if color == 'blue' else (
                (red-blue > 70) & (red-green > 35) & (green-blue > 38))
            columns = np.flatnonzero(mask.sum(axis=0) >= 2)
            consecutive = np.split(columns, np.where(np.diff(columns) > 1)[0]+1)
            runs[window] = dict(columns=int(len(columns)), longest_run=max(map(len, consecutive)))
        report[name] = dict(saturated_trace_color=color, windows=runs, verified_markers=0,
                            disposition='keep_blind_pending_separable_observations_and_sample_binding')
    return report


def main():
    plan = read(OUT / 'evidence_plan.json')
    receipt_path = P32 / 'sealed_geometry.json'
    assert sha(receipt_path) == plan['previous_receipt_sha256']
    receipt = read(receipt_path)
    assets = ['coffee_publisher_sealed.pdf', 'coffee_si_sealed.zip', 'pomelo_publisher_sealed.pdf']
    protected = {name: sha(CACHE / name) for name in assets}
    assert all(protected[name] == ASSETS[name][2] for name in assets)
    traces, windows = coffee_vectors()
    counts = db_matches({DOI})[DOI]
    assert not any(counts.values())
    result = dict(source_family='doi:' + DOI, figure='SI Fig. S3', system='2E', target_cycle_count=10000,
                  source_disposition='development_only_after_endpoint_geometry_exposure',
                  author_reported_retention_pct=75.,
                  terminal_plot_retention_pct=traces['AC-CSS']['markers'][-1]['ordinate_retention_pct'],
                  label_disposition='Retain integer prose and graph evidence separately. Any development trial must freeze '
                                    'label handling and sensitivity before fitting. Same test, one source and one record.',
                  static_features=dict(reported_current_A_g=2., BET_m2_g=None, electrolyte='H2SO4', concentration_mol_L=1.,
                                       cycle_voltage_lower_V=0., cycle_voltage_upper_V=1., reference_electrode=None),
                  current_mass_basis='mass of activated carbon in one electrode',
                  active_carbon_mass_mg_each=[2.93, 2.93],
                  normalization='Publisher SI normalized trace; exact physical start cycle not inferred.',
                  eligible_development_trace='AC-CSS', source_catalog_matches=counts, windows=windows,
                  traces=traces, main_figure_native_axes=coffee_raster(), pomelo=pomelo_geometry(receipt),
                  axes_si_pdf_pt=dict(x=X_TICKS, y=Y_TICKS), protected_assets=protected,
                  independent_acceptances=0, new_fits=0, canonical_admissions=0)
    write(OUT / 'native_curve_evidence.json', result)


if __name__ == '__main__':
    main()
