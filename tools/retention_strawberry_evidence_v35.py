"""Read strawberry-straw cycling markers from the publisher's native PDF images."""

from pathlib import Path
import sys
import xml.etree.ElementTree as ET

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.retention_blind_reserve_v22 import db_matches
from tools.retention_suaeda_case_v16 import BASE, ROOT, feature_row, sha, write


OUT = BASE / '第三十五轮_长循环补证与草莓秸秆原图_20261106'
CACHE = ROOT / '.local-literature-cache/P35'
DOI = '10.1038/s41598-026-36557-4'
XML = ROOT / '三电极端点扩充_20261018/new_sources/PMC12891511/main.xml'
PDF = CACHE / 'strawberry_source.pdf'
ARCHIVE = 'https://pmc-oa-opendata.s3.amazonaws.com/PMC12891511.1/'
SETUP = {
    '2E': dict(page=10, size=(1617, 1906), fig='9(e)', author=70.1, x0=183., x10000=720.5,
               y0=1792., y100=1323.5, y_axis_outer=(120, 126),
               early=(170, 1309, 307, 1387), terminal=(713, 1450, 732, 1472), early_thresholds=(132,145),
               terminal_thresholds=(132,145), sample='SPC3//SPC3', voltage=(0., 1.2), reference=None),
    '3E': dict(page=8, size=(1456, 2157), fig='7(g)', author=95.6, x0=438.5, x10000=1128.5,
               y0=2062., y100=1645., y_axis_outer=(359, 365),
               early=(430, 1637, 594, 1677), terminal=(1119, 1651, 1145, 1673), early_thresholds=(132,145),
               terminal_thresholds=(145,160), sample='SPC3', voltage=(-1.,0.), reference='Hg/HgO'),
}


def shared_centers(image, roi, thresholds):
    from tools.retention_sawdust_figures_v30 import ring_holes

    low, high = [ring_holes(image, roi, level) for level in thresholds]
    pairs = []
    for x, y, count in low:
        match = [(a,b,n) for a,b,n in high if abs(a-x) <= 1 and abs(b-y) <= 1]
        if match:
            assert len(match) == 1
            pairs.append(((x,y,count), match[0]))
    return pairs


def read_curve(image, c):
    assert image.size == c['size']
    pixels = np.asarray(image)
    dark = pixels.max(axis=2) < 120
    x0, x1, y0, y1 = (c[key] for key in ('x0','x10000','y0','y100'))
    for x in (x0,x1):
        assert dark[int(y0)+2:int(y0)+7, round(x)].sum() >= 4
    for y in (y0,y1):
        assert dark[round(y), slice(*c['y_axis_outer'])].sum() >= 4
    sx, sy = 10000/(x1-x0), 100/(y0-y1)

    def point(pair):
        (x,y,_),(a,b,_) = pair
        cycle, value = (x-x0)*sx, (y0-y)*sy
        return dict(center_px=[x,y], alternate_center_px=[a,b], cycle_reading=cycle,
                    cycle_interval=[cycle-3*sx, cycle+3*sx], early_ordinate_pct=value,
                    ordinate_interval_pp=[value-3*sy,value+3*sy])

    early = [point(p) for p in shared_centers(image, c['early'], c['early_thresholds'])]
    assert early[0]['cycle_reading'] < 0 and early[1]['cycle_interval'][0] > 0
    origin = early[0]
    points = [p for p in early[1:] if p['cycle_interval'][1] <= 2000]
    assert all(a['cycle_interval'][1] < b['cycle_interval'][0] for a,b in zip(points,points[1:]))
    windows = {}
    for f in (.1,.2):
        features, count = feature_row(points, 10000, f)
        windows[str(f)] = dict(features=features, markers=count)
    terminal, = [point(p) for p in shared_centers(image,c['terminal'],c['terminal_thresholds'])]
    assert terminal['cycle_interval'][0] <= 10000 <= terminal['cycle_interval'][1]
    terminal['ordinate_retention_pct'] = terminal.pop('early_ordinate_pct')
    return dict(normalization_origin_geometry=origin, early_markers=points, windows=windows,
                terminal_geometry=terminal, author_in_terminal_geometry_band=
                terminal['ordinate_interval_pp'][0] <= c['author'] <= terminal['ordinate_interval_pp'][1])


def main():
    from pypdf import PdfReader

    assert sha(PDF)=='cdf2e579375577c3b8d61247d982ef1a04254b075609f4e3c556ed034c817339'
    assert sha(XML)=='588856da16b86750de19c3401e486fbd8dd9fce06b7be16a474508601fd67a2f'
    article = ET.parse(XML).getroot()
    assert any(n.get('pub-id-type')=='doi' and n.text==DOI for n in article.iter('article-id'))
    body = ' '.join(''.join(article.find('body').itertext()).split())
    for text in ('95.6%', '70.1%', 'using SPC3 as both the cathode and anode', '6 M KOH electrolyte system',
                 'Hg/HgO electrode as the reference electrode', 'Cycling stability of the asymmetric supercapacitor', '2746.5'):
        assert text in body
    pdf = PdfReader(PDF)
    records = {}
    for system, c in SETUP.items():
        image = pdf.pages[c['page']-1].images[0].image.convert('RGB')
        record = read_curve(image,c)
        assert [w['markers'] for w in record['windows'].values()] == [4, 9]
        records[system] = dict(system=system,sample_name=c['sample'],figure=c['fig'],publisher_page=c['page'],
            target_cycle_count=10000,author_retention_pct=c['author'],current_mass_basis=None,
            static_features=dict(reported_current_A_g=10., electrolyte='KOH', concentration_mol_L=6., BET_m2_g=2746.5,
                                 cycle_voltage_lower_V=c['voltage'][0],cycle_voltage_upper_V=c['voltage'][1],
                                 reference_electrode=c['reference']), **record)
    assert records['3E']['author_in_terminal_geometry_band'] and not records['2E']['author_in_terminal_geometry_band']
    counts = db_matches({DOI})[DOI]
    assert not any(counts.values())
    assets = {'pdf':PDF, 'xml':XML, 'fig7':CACHE/'strawberry_fig7.jpg', 'fig9':CACHE/'strawberry_fig9.jpg'}
    assert sha(assets['fig7'])=='d6eedcecc9c05006da84128ec5413dcb6079ba3b12c85bec2c466b52bbc0107e'
    assert sha(assets['fig9'])=='bd3a0841d2ab52a63a0a76b3c99a53141eef9bf46a723f8b84f47f89b8c5263f'
    OUT.mkdir(exist_ok=True)
    write(OUT/'strawberry_evidence.json',dict(source_family='doi:'+DOI,role='observed_development_candidates_only',
        records=records, fingerprinted_assets={n:dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p)) for n,p in assets.items()},
        publisher_pdf=ARCHIVE+'PMC12891511.1.pdf', source_catalog_exact_matches=counts,
        device_conflict='Fig. 9(e) caption says asymmetric; device subsection and both named electrodes identify symmetric SPC3//SPC3.',
        read_uncertainty='One native-axis calibration per panel; geometric center ±3 px in each axis. Initial reference excluded from inputs.',
        canonical_admissions=0, new_fits=0, external_acceptances=0))


def compare():
    from tools.retention_direction_review_v34 import P33, read
    from tools.retention_horizon_normalization_v19 import OUT as P19, neighborhood
    from tools.retention_sawdust_development_v31 import OUT as P31

    scale_path, data_path = P19/'training_plan.json', P31/'input_snapshot.json'
    source_path = OUT/'strawberry_evidence.json'
    data, strawberry, coffee = (read(p) for p in (data_path,source_path,P33))
    scale = read(scale_path)['neighborhood']
    fields = ('electrolyte','concentration_mol_L','reported_current_A_g',
              'cycle_voltage_lower_V','cycle_voltage_upper_V')

    def candidate(row, source, name):
        return dict(row_id=name, source_family=source, target=row['author_retention_pct'],
                    features=row['windows']['0.2']['features'], static_features=row['static_features'])

    systems = {}
    for system, existing in data.items():
        row = candidate(strawberry['records'][system],strawberry['source_family'],'strawberry')
        peer = neighborhood([*existing,row],scale)[-1]
        assert peer['row_id']==row['row_id'] and 'neighbor_id' in peer
        peer_static = next(r['static_features'] for r in existing if r['row_id']==peer['neighbor_id'])
        matches = [r['row_id'] for r in existing if all(r['static_features'].get(k)==row['static_features'][k]
                   for k in fields) and r['features']['target_cycle_count']==10000]
        systems[system] = dict(nearest=peer, nearest_static=peer_static,
                               same_reported_protocol_at_10000=matches, strawberry_static=row['static_features'])
    coffee_row = candidate(dict(coffee,author_retention_pct=coffee['author_reported_retention_pct']),
                           coffee['source_family'],'coffee')
    two_e = candidate(strawberry['records']['2E'],strawberry['source_family'],'strawberry')
    pair = neighborhood([coffee_row,two_e],scale)[-1]
    assert pair['neighbor_id']=='coffee'
    write(OUT/'comparability.json',dict(systems=systems, coffee_strawberry_2E=pair,
        coffee_static=coffee_row['static_features'], protocol_match_fields=fields,
        nearest_rule='Previously fixed early-curve scales and horizon ratio; no use of endpoint in neighbor selection.',
        qualification='Reported protocol matches do not establish common mass denominator or raw test equivalence.',
        input_sha256={p.relative_to(ROOT).as_posix():sha(p) for p in (data_path,scale_path,source_path,P33)},new_fits=0))


if __name__=='__main__':
    {'read':main, 'compare':compare}[sys.argv[1] if len(sys.argv)>1 else 'read']()
