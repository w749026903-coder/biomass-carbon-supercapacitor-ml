"""Resolve what the native WHAC and C-4 figures support without changing labels."""

from itertools import product
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

import numpy as np
from pypdf import PdfReader

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.retention_suaeda_case_v16 import BASE, ROOT, sha, write


CACHE = ROOT / '.local-literature-cache/P37'
OUT = BASE / '第三十七轮_迟发衰减与冲突复核_20261106'
OA = ROOT / '同体系文献补充_第二批_20261017/定向扩搜40至60篇_20261017/sources/OA050'
FILES = {
    CACHE/'whac_publisher_complete.pdf': '1f322b38547f96efa1b346c8c46b63154f49209ad22d336e4ceb4826f8403971',
    OA/'main.xml': '83ea243fc959d69b5f9f56a1464367b36e7e2f114ea4bbe39a5b6bf3112124fc',
    OA/'materials-3005630-supplementary.pdf': '9db7b6244db2e5e760cc95fc8561ed49500cd2d1120be27dfb8bba26777c638b',
    ROOT/'三电极端点扩充_20261018/corpus/B_R018/main.pdf': 'f08eadb564726b73890353c032e8d364a2d962f7d598592260d39b61c11db617',
}


def native_page(path, number, size):
    reader = PdfReader(path)
    page = reader.pages[number-1]
    image = page.images[0].image.convert('RGB')
    assert image.size == size
    return reader, np.asarray(image, dtype=np.int16)


def center(image, seed, radius, color):
    x,y = seed
    q = image[y-radius:y+radius+1,x-radius:x+radius+1]
    red,green,blue = q.transpose(2,0,1)
    hits = []
    for offset in (0,15):
        if color == 'magenta':
            mask = (red-green > 70+offset) & (blue-green > 65+offset) & (red>145) & (blue>120)
        else:
            mask = (blue-red > 65+offset) & (blue-green > 60+offset) & (blue>110)
        yy,xx = np.where(mask)
        assert len(xx) >= (750 if color=='magenta' else 55), seed
        hits.append((float(x-radius+xx.mean()),float(y-radius+yy.mean())))
    assert np.ptp(hits,axis=0).max()<1.5, seed
    return hits[0]


def whac():
    _, image = native_page(CACHE/'whac_publisher_complete.pdf',11,(3699,1347))
    body = ' '.join(''.join(ET.parse(OA/'main.xml').getroot().find('body').itertext()).split())
    assert all(s in body for s in ('76.87%', '99.45%', 'first 1500 cycles', '1–5 A g−1 current density'))
    # Major ticks outside the graph, read from the native pixels.
    x0,xn,y0,y80 = 289.,1660.,1096.,380.5
    assert (image[1103:1117,int(x0)].max(axis=1)<110).sum()>=5
    assert (image[1103:1117,int(xn)].max(axis=1)<110).sum()>=5
    assert (image[round(y80),270:279].max(axis=1)<110).sum()>=5
    sx,sy = 7000/(xn-x0), 80/(y0-y80)
    guesses = (205,205,205,205,205,205,205,205,269,316,329,353,395,395,410)
    markers = []
    for i,gy in enumerate(guesses):
        x,y = center(image,(round(289+i*98),gy),17,'magenta')
        cycles = (x-x0)*sx
        retention = (y0-y)*sy
        markers.append(dict(index=i, plotted_nominal_cycle=i*500, center_px=[x,y], cycle_reading=cycles,
            cycle_interval=[cycles-4*sx,cycles+4*sx], retention_pct=retention,
            retention_geometry_band_pct=[retention-4*sy,retention+4*sy]))
    for a,b in zip(markers,markers[1:]):
        assert a['cycle_interval'][1]<b['cycle_interval'][0]
    assert markers[-1]['retention_geometry_band_pct'][0]<=76.87<=markers[-1]['retention_geometry_band_pct'][1]
    assert markers[7]['retention_geometry_band_pct'][0]>95>markers[8]['retention_geometry_band_pct'][1]
    # The overlapping zero-cycle glyph is the normalization reference.
    windows = {str(f):[r['index'] for r in markers[1:] if r['cycle_interval'][1] <= 7000*f] for f in (.1,.2)}
    assert windows=={'0.1':[1],'0.2':[1,2]}
    return dict(doi='10.3390/ma17133233', sample='WHAC150', figure='8(a)', page=11, target_cycle_count=7000,
        author_retention_pct=76.87, markers=markers, window_marker_indices=windows,
        observed_95pct_crossing_bracket_nominal_cycles=[3500,4000],
        sibling_WHAC100_panel_a_author_retention_pct=99.45, panel_a_author_terminal_gap_pp=99.45-76.87,
        sibling_WHAC100_panel_b_author_retention_pct=99.40,
        author_same_early_plateau_through_cycles=1500, reported_cycling_current_A_g=None,
        status='late_decline_development_evidence_only_missing_protocol_and_early_coverage')


def c4():
    reader,image = native_page(ROOT/'三电极端点扩充_20261018/corpus/B_R018/main.pdf',11,(1947,785))
    body = ' '.join(reader.pages[10].extract_text().split())
    conclusion = ' '.join(reader.pages[12].extract_text().split())
    assert all(s in body for s in ('C-4 exhibited', '138.5 F/g', '36.45 F/g', '5000 cycles at 2.5 A/g'))
    assert '40% capacitance' in conclusion
    x0,xn,y20,y160 = 1055.5,1802.5,648.,33.5
    assert (image[653:666,round(x0)].max(axis=1)<110).sum()>=5
    assert (image[653:666,round(xn)].max(axis=1)<110).sum()>=5
    assert (image[round(y20),1042:1052].max(axis=1)<150).sum()>=5
    sx,sy = 5000/(xn-x0),140/(y20-y160)
    y0 = y20 + 20/sy
    start = center(image,(1057,127),17,'blue')
    end = center(image,(1803,577),17,'blue')
    assert abs(end[0]-xn)<6 and start[0]-x0<10
    terminal = 100*(y0-end[1])/(y0-start[1])
    possible = [100*(y0+o-end[1]-e)/(y0+o-start[1]-s) for o,e,s in product((-5.,5.),repeat=3)]
    assert min(possible)<100*36.45/138.5<max(possible)<40
    seeds = ((1101,214),(1116,234),(1130,265),(1145,287),(1160,302),(1175,320),(1190,338))
    early = []
    for seed in seeds:
        x,y = center(image,seed,8,'blue')
        cycles = (x-x0)*sx
        early.append(dict(center_px=[x,y], cycle_reading=cycles,cycle_interval=[cycles-5*sx,cycles+5*sx],
            graph_capacitance_F_g=(y0-y)*sy))
    assert all(a['cycle_interval'][1]<b['cycle_interval'][0] for a,b in zip(early,early[1:]))
    assert early[-1]['cycle_interval'][1]<1000
    return dict(doi='10.1007/s13399-025-06799-9', main_panel_author_sample='C-4', figure='8(b)', page=11,
        target_cycle_count=5000, reported_cycling_current_A_g=2.5,
        original_body_capacitances_F_g=[138.5,36.45], original_body_ratio_pct=100*36.45/138.5,
        original_conclusion_retention_pct=40., plotted_capacitances_F_g=[(y0-start[1])*sy,(y0-end[1])*sy],
        graph_center_px={'initial':start,'terminal':end}, graph_retention_pct=terminal,
        graph_retention_geometry_band_pct=[min(possible),max(possible)], selected_separable_early_points=early,
        inset_label='2.5A/g@C-5', inset_binding='Current agrees with the main panel, inset material label differs.',
        status='graph_supports_body_ratio_but_original_conclusion_and_inset_label_stay_frozen')


def main():
    assert all(sha(p)==h for p,h in FILES.items())
    OUT.mkdir(exist_ok=True)
    write(OUT/'held_curve_evidence.json',dict(WHAC150=whac(),C4=c4(),
        protected={p.relative_to(ROOT).as_posix():h for p,h in FILES.items()},
        new_fits=0, new_admissions=0, external_acceptances=0))


if __name__=='__main__':
    main()
