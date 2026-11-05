"""Inspect source protocol and early image coverage without returning labels or pixels."""

from io import BytesIO
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET
from zipfile import ZipFile

import numpy as np
from PIL import Image
from pypdf import PdfReader
from pypdf.generic import ContentStream

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.retention_blind_structures_v32 import CACHE, OUT, ROOT, flat, read, sha, write


ASSETS = {
    'pomelo3e_sealed.jpg': ('PMC9419826.1', 'd0na00778a-f2.jpg', 'b40cca950661f603bbcd64cf8b3833211bdd23e7d36c94f86cdee3b6f459d3bf'),
    'pomelo2e_sealed.jpg': ('PMC9419826.1', 'd0na00778a-f3.jpg', 'bc73836d653fa9e7f07eb0ad8a770c7510e65ced93f673e22c9fba4bee8e81c5'),
    'coffee_sealed.jpg': ('PMC9370518.1', 'nanomaterials-12-02647-g006.jpg', '27600cb40e1be39d1a9541d5708e55cec001ff00a926be81ef07e0ee1076cc52'),
    'chitosan_sealed.jpg': ('PMC9465634.1', 'd2ra03949d-f6.jpg', 'b96629e95735de377aa0e8c4d217212876c5a3d9b64d1b0e8cb8b299a41328cb'),
    'lignin_sealed.jpg': ('PMC7992182.1', 'ao1c00448_0009.jpg', 'f3210ef4dd4b3efd548e2204bde80691e6581334fe87b1c67b5ab0eb7a4e4d21'),
    'pomelo_publisher_sealed.pdf': ('PMC9419826.1', 'PMC9419826.1.pdf', '5b036b935f1e1427c2a1a76a7f2fa6187aaa04a2d22edd5f7b831bc24cd1dd24'),
    'pomelo_si_sealed.pdf': ('PMC9419826.1', 'NA-003-D0NA00778A-s001.pdf', 'd81259c06e70e75849028e937482524e6d562fe7106d8b6195cc8b1a112fea8a'),
    'coffee_publisher_sealed.pdf': ('PMC9370518.1', 'PMC9370518.1.pdf', 'b519b04f441dbd83993015d00cd480bd0d327d575d57eca9c7a042ba8590ec51'),
    'coffee_si_sealed.zip': ('PMC9370518.1', 'nanomaterials-12-02647-s001.zip', '4390740ce6074e3ebdcab712f1f4e9d513d9387c7776638eb3f1b308cbaaa456'),
}

# Bounds are in the archive thumbnails, with the right edge inside the relevant axis tick.
# No display, OCR or export of the pixels. Dense columns are a geometry diagnostic only.
GEOMETRY = {
    'pomelo3e': (5, (458, 497, 529), {10: 482, 20: 510}, ('blue',)),
    'pomelo2e': (7, (446, 577, 610), {10: 472, 20: 503}, ('red', 'yellow')),
    'coffee': (None, (455, 58, 135), {10: 474, 20: 498}, ('red', 'cyan', 'yellow')),
}


def protocol(archive, figure_id, panel, system, current, section):
    body = ET.parse(CACHE / f'{archive}_sealed_fulltext.xml').getroot().find('body')
    figure = next(f for f in body.findall('.//fig') if f.get('id') == figure_id)
    caption = flat(figure.find('caption'))
    parts = re.split(r'\(([a-g])\)', caption)
    panel_caption = parts[parts.index(panel) + 1]
    assert re.search(rf'\b{current}\s*A\s*g\s*[−–-]?\s*1\b', panel_caption)
    mentions = [flat(p) for p in body.findall('.//p') if any(
        figure_id in x.get('rid', '').split() for x in p.findall('.//xref'))]
    panel_number = re.search(r'\d+', figure.findtext('label'))[0]
    panel_ref = rf'fig(?:ure)?[.\s]*{panel_number}\s*\(?{panel}\)?'
    cycle_words = r'\b10[,\s]?000(?:th)?\s+(?:GCD\s+)?cycles?\b'
    paired = [p for p in mentions if re.search(panel_ref, p, re.I) and re.search(cycle_words, p, re.I)]
    assert paired
    method = flat(body.find(f'.//sec[@id="{section}"]'))
    qualifier = r'three[\s-]+electrode' if system == '3E' else r'two[\s-]+electrode'
    assert re.search(qualifier, method, re.I)
    # Article methods may describe multiple tests. Record only explicitly detected method cues.
    return dict(pmcid=archive, figure_id=figure_id, panel=panel, system=system,
                reported_A_g=current, target_cycles=10000, method_section=section,
                method_mentions_1M_KOH=bool(re.search(r'\b1\s*M\s*KOH\b', method, re.I)),
                figure_paragraph_mentions_initial_capacitance=any(
                    re.search(r'initial\s+(?:specific\s+)?capacitance|first\s+cycle', p, re.I) for p in paired))


def geometry(name, pomelo_pdf):
    page, (x0, y0, y1), limits, colors = GEOMETRY[name]
    with Image.open(CACHE / f'{name}_sealed.jpg') as archive_image:
        thumb_size = archive_image.size
        original = archive_image if page is None else pomelo_pdf.pages[page - 1].images[0].image
        width, height = original.size
        sx, sy = width / thumb_size[0], height / thumb_size[1]
        assert abs(sx - sy) < 0.01
        out = {}
        for window, edge in limits.items():
            # Round inward and use an exclusive right edge.
            bounds = (round(x0 * sx), round(y0 * sy), int(edge * sx), round(y1 * sy))
            pixels = np.asarray(original.crop(bounds).convert('RGB'), dtype=np.int16)
            red, green, blue = pixels.transpose(2, 0, 1)
            masks = {
                'blue': (blue - red > 55) & (blue - green > 45),
                'red': (red - green > 50) & (red - blue > 50),
                'cyan': (green - red > 43) & (blue - red > 43),
                'yellow': (red - blue > 60) & (green - blue > 52),
            }
            out[str(window)] = dict(bounds_ltrb=bounds, columns=pixels.shape[1],
                                    occupied_columns={c: int(masks[c].any(axis=0).sum()) for c in colors})
        return dict(publisher_pdf_page=page, image_size=(width, height), windows=out,
                    verified_markers=0, confirmed_training_features=0)


def coffee_native_layout():
    """Locate the right-hand panel without decoding the PDF page or any tile pixels."""
    pdf = PdfReader(CACHE / 'coffee_publisher_sealed.pdf')
    page = pdf.pages[10]
    form = page['/Resources']['/XObject']['/Im13'].get_object()
    sources = form['/Resources']['/XObject']
    operations = ContentStream(form, pdf).operations
    tiles = []
    for (matrix, transform), (args, operator) in zip(operations, operations[1:]):
        if (transform, operator) != (b'cm', b'Do') or abs(float(matrix[4]) - 302.52) > 0.001:
            continue
        obj = sources[args[0]].get_object()
        if obj.get('/Width') == 1729:
            tiles.append((float(matrix[5]), int(obj['/Height'])))
    assert len(tiles) == 31 and sorted(tiles, reverse=True) == tiles
    assert len({offset for offset, _ in tiles}) == len(tiles)
    return dict(pdf_page=11, panel='b', width_px=1729, untrimmed_height_px=sum(h for _, h in tiles),
                tile_placements=len(tiles), aligned_to_axes=False)


def main():
    plan = read(OUT / 'metadata_freeze.json')
    screen = read(OUT / 'structural_screen.json')
    assert sha(OUT / 'metadata_freeze.json') == screen['metadata_sha256'] == read(OUT / 'freeze_receipt.json')['plan_sha256']
    assert all(sha(ROOT / path) == value for path, value in plan['protected'].items())
    xml_assets = [*screen['results'], screen['correction']]
    assert all(sha(ROOT / row['local']) == row['sha256'] for row in xml_assets)
    receipts = {}
    for name, (version, archive_name, digest) in ASSETS.items():
        path = CACHE / name
        assert sha(path) == digest, name
        receipts[name] = dict(sha256=digest, bytes=path.stat().st_size,
                              url=f'https://pmc-oa-opendata.s3.amazonaws.com/{version}/{archive_name}')
    protocols = {
        'pomelo3e': protocol('PMC9419826', 'fig2', 'f', '3E', 10, 'sec7'),
        'pomelo2e': protocol('PMC9419826', 'fig3', 'f', '2E', 10, 'sec7'),
        'coffee': protocol('PMC9370518', 'nanomaterials-12-02647-f006', 'b', '2E', 2, 'sec2dot11-nanomaterials-12-02647'),
    }
    pdf = PdfReader(CACHE / 'pomelo_publisher_sealed.pdf')
    bounds = {name: geometry(name, pdf) for name in GEOMETRY}
    correction = flat(ET.parse(ROOT / screen['correction']['local']).getroot().find('body'))
    check = {f'Fig3{panel}': bool(re.search(rf'fig(?:ure)?[.\s]*3\s*\(?{panel}\)?', correction, re.I))
             for panel in ('c', 'f')}
    assert check == {'Fig3c': True, 'Fig3f': False} and re.search(r'replac', correction, re.I)
    with ZipFile(CACHE / 'coffee_si_sealed.zip') as z:
        members = z.infolist()
        assert len(members) == 1 and Path(members[0].filename).suffix == '.pdf'
        coffee_si_pages = len(PdfReader(BytesIO(z.read(members[0]))).pages)
    result = dict(structural_screen_sha256=sha(OUT / 'structural_screen.json'), assets=receipts,
                  sealed_xml_count=len(xml_assets), protocols=protocols, early_geometry=bounds,
                  coffee_native_layout=coffee_native_layout(),
                  pomelo_correction_figure_flags=check,
                  supplement_pages={'pomelo': len(PdfReader(CACHE / 'pomelo_si_sealed.pdf').pages), 'coffee': coffee_si_pages},
                  verified_early_inputs=0, endpoints_revealed=0, fits=0, independent_acceptances=0)
    write(OUT / 'sealed_geometry.json', result)


if __name__ == '__main__':
    main()
