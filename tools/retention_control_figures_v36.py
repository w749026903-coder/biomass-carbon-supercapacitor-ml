"""Reproduce the honey and rice-straw evidence from native publisher images."""

from itertools import product
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

import numpy as np
from pypdf import PdfReader

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.retention_blind_reserve_v22 import db_matches
from tools.retention_suaeda_case_v16 import BASE, ROOT, feature_row, sha, write


CACHE = ROOT / '.local-literature-cache/P36'
OUT = BASE / '第三十六轮_对照样品与极端衰减_20261106'
RECORDS = {
    'honey': dict(doi='10.1038/s41598-026-62039-8', pmc='PMC13381972.1', page=21, panel='16(b)',
        xml='文献扩充_大批补齐_20261018/sources/SUP_118/main.xml', x0=214., x_end=1381.,
        y_low=2148., y_high=1301., low=0., high=100., size=(1564,2363),
        markers=((273,1823),(331,1918),(389,2005),(448,2050)), start=(215,1292), end=(1381,2140)),
    'rice': dict(doi='10.1039/d6na00276e', pmc='PMC13400085.1', page=11, panel='7(C)',
        xml='三电极端点扩充_20261018/new_sources/PMC13400085/main.xml', x0=172.5, x_end=717.5,
        y_low=1010.5, y_high=925., low=90., high=120., size=(1882,1776),
        markers=((200,982),(228,982),(255,982),(282,985)), start=None, end=(718,1030)),
}
EXPECTED = {
    'honey': ('92ccce5a662bfe408bdfd98d784e0fb77bbbd23f7e93714cb04eed30bd616bf6',
              '0618a985c248247fcbd9100f0eb107762c55d0587560ce93375e244f80be0ecb',
              'ae3e316dafcd6120a1d0b03fe04f97e5415ccf3abbbc74868b0fc8b043a6f4da'),
    'rice': ('c4e5ca055429bf7930335dcb87507725d6d8fa5fb28682c576c98d261537c9cb',
             'c10a3238b3cac4fc378afe1ff7be55a6b39ad744834a82bcd5e48de47e8736e2',
             'beb50260fc8a7f65a038fe56a2a8db259453884645501d48714de12daa73e707'),
}


def centroid(pixels, seed):
    x, y = seed
    roi = pixels[y-11:y+12, x-11:x+12]
    centers = []
    for threshold in (115,135,155):
        rows, cols = np.where((roi.max(axis=2)<threshold) & (np.ptp(roi,axis=2)<28))
        assert len(rows)>180 and np.ptp(rows)>15 and np.ptp(cols)>15
        centers.append((float(x-11+cols.mean()), float(y-11+rows.mean())))
    assert np.ptp(centers,axis=0).max()<1
    return centers[1]


def evidence(name, setup, protected):
    paths = (CACHE/f'{name}_paper.pdf',CACHE/f'{name}_figure.jpg',ROOT/setup['xml'])
    assert tuple(map(sha,paths))==EXPECTED[name]
    protected.update({p.relative_to(ROOT).as_posix():sha(p) for p in paths})
    article = ET.parse(paths[2]).getroot()
    assert any(n.get('pub-id-type')=='doi' and n.text==setup['doi'] for n in article.iter('article-id'))
    body = ' '.join(''.join(article.find('body').itertext()).split())
    signals = ('1.1 A g⁻¹', '0.5 M Na₂SO₄', 'three-electrode system', 'after 1000 cycles', '0.9 F/g') if name=='honey' else (
        'three-electrode configuration with 1 M H2SO4', '83.54%', '75.34%', '5 A g−1')
    assert all(s in body for s in signals)
    page = PdfReader(paths[0]).pages[setup['page']-1]
    raw = page.images[0].image.convert('RGB')
    assert raw.size==setup['size']
    img = np.asarray(raw, dtype=np.int16)
    sx = 10000/(setup['x_end']-setup['x0'])
    sy = (setup['high']-setup['low'])/(setup['y_low']-setup['y_high'])
    start = centroid(img,setup['start']) if setup['start'] else None
    origin = setup['y_low']

    def ratio(y, y_start):
        center = 100*(origin-y)/(origin-y_start)
        limits = [100*(origin+o-y-z)/(origin+o-y_start-a) for o,z,a in product((-3.,3.),repeat=3)]
        return center, [min(limits),max(limits)]

    def locate(seed):
        x,y = centroid(img,seed)
        cycles = (x-setup['x0'])*sx
        raw_ordinate = setup['low']+(origin-y)*sy
        value, band = ratio(y,start[1]) if start else (raw_ordinate,[raw_ordinate-3*sy,raw_ordinate+3*sy])
        return dict(center_px=[x,y], cycle_reading=cycles,cycle_interval=[cycles-3*sx,cycles+3*sx],
                    axis_ordinate=raw_ordinate, retention_pct=value, retention_geometry_band_pct=band)

    marks = [locate(s) for s in setup['markers']]
    terminal = locate(setup['end'])
    assert terminal['cycle_interval'][0]<=10000<=terminal['cycle_interval'][1]
    assert all(a['cycle_interval'][1]<b['cycle_interval'][0] for a,b in zip(marks,marks[1:]))
    windows = {}
    for fraction in (.1,.2):
        points = [dict(p,early_ordinate_pct=p['retention_pct']) for p in marks if p['cycle_interval'][1]<=10000*fraction]
        features = feature_row(points,10000,fraction)[0] if len(points)>=3 else None
        windows[str(fraction)] = dict(markers=len(points),features=features)
    assert [w['markers'] for w in windows.values()]==[1,3]
    return dict(source_family='doi:'+setup['doi'], system='3E',figure=setup['panel'],page=setup['page'],
                publisher_pdf=f'https://pmc-oa-opendata.s3.amazonaws.com/{setup["pmc"]}/{setup["pmc"]}.pdf',
                cycle_count=10000, axis_unit='F/g' if start else '% retention',
                initial_graph_center_px=start, initial_axis_ordinate=(origin-start[1])*sy if start else None,
                markers=marks, windows=windows, terminal=terminal)


def main():
    protected = {}
    result = {k:evidence(k,s,protected) for k,s in RECORDS.items()}
    honey,rice = (result[k] for k in ('honey','rice'))
    assert honey['terminal']['retention_geometry_band_pct'][1]<2
    low,high = rice['terminal']['retention_geometry_band_pct']
    assert low <= 83.54 <= high
    honey.update(author_retention_10000_pct=None, reported_current_A_g=1.1, electrolyte='0.5 M Na2SO4',
        reported_GCD_method_window_V=[0,1], reference='Ag/AgCl (saturated KCl)', current_mass_basis=None,
        disposition='seen_graph_derived_extreme_candidate_hold_for_endpoint_and_protocol_conflicts',
        author_conflicts=['Fig. 14 cited for cycling but depicts impedance; Fig. 16 is the cycling plot.',
        '0.9 F/g appears in the 1000-cycle sentence but matches the 10000-cycle graph scale.',
        '0.9 mg and 0.9 mg/cm² are both reported; exact cycling drying setting and current mass basis unconfirmed.'])
    rice.update(author_retention_10000_pct=83.54, reported_current_A_g=5., electrolyte='1 M H2SO4',
        reported_GCD_method_window_V=[0,1], reference='Ag/AgCl', current_mass_basis=None, own_BET_m2_g=201.,
        disposition='seen_development_candidate_3E_near_tail_control',
        other_values=dict(AC_text_CE_pct=75,AC_figure_CE_pct=85,ZnO_retention_pct=75.34,AC_ZnO_retention_pct=89.98))
    counts = db_matches({s['doi'] for s in RECORDS.values()})
    assert all(not any(v.values()) for v in counts.values())
    OUT.mkdir(exist_ok=True)
    write(OUT/'control_evidence.json',dict(records=result, protected=protected, exact_catalog_matches=counts,
         scope='Known outcomes and exploratory evidence only. No change to canonical admission or frozen labels.',
         geometry_bound='±3 native pixels; honey ratio propagates the common zero and the two marker ordinates.',
         new_fits=0, new_admissions=0, external_acceptances=0))


if __name__=='__main__':
    main()
