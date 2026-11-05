"""Reproduce the published-image readings and keep cycling protocol holds explicit."""

from pathlib import Path
import sys
import xml.etree.ElementTree as ET

import numpy as np
from PIL import Image
from pypdf import PdfReader

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.retention_suaeda_case_v16 import BASE, ROOT, sha, write


CACHE = ROOT / ".local-literature-cache/P38"
OUT = BASE / "第三十八轮_橙皮低保持率与原文归属_20261106"
LOCAL = ROOT / "三电极端点扩充_20261018/new_sources"
FILES = {
    CACHE / "opac_gr7.jpg": "a6a1688cc287546481a19c42f82e00e1ce09a42f733c8099803e15ab6c68708a",
    CACHE / "corn_straw.pdf": "ed8c3d2bf11a7b541bfaa0c9bdbd7665c4a31ea8467f730eb7aa04b62bf0e99d",
    LOCAL / "PMC8707477/main.xml": "1ca0bc7f7e5e9336382bea8c096e0fb08ddfe171f917b2575447e99d7863a025",
    LOCAL / "PMC10958655/main.xml": "615850ad32df82a442126cb54476f1740f2dc665567edf75b4056ef1e8b7ce93",
    LOCAL / "PMC10958655/assets/vg3c00048_0007.jpg": "5f9badb4fa31222f2dd7d89e222936c4a134ec1fb3646a820584c54b461e0e9d",
}


def normalized(value):
    return " ".join(value.split())


def orange_peel():
    with Image.open(CACHE / "opac_gr7.jpg") as figure:
        assert figure.size == (1634, 1341)
        pixels = np.asarray(figure.convert("RGB"), dtype=np.int16)
    black = pixels.max(axis=2) < 70
    for x in (318, 557, 1507):
        assert black[1155:1171, x].sum() >= 12
    for y in (36, 259, 1149):
        assert black[y, 178:190].sum() >= 10
    cycle_per_pixel = 5000 / (1507 - 318)
    pct_per_pixel = 100 / (1149 - 36)
    red, green, blue = pixels.transpose(2, 0, 1)
    red_trace = (red - green > 105) & (red - blue > 105) & (red > 180)
    # Hand-located glyph centers checked against the red trace. The overlapping
    # early cluster and the legend are excluded.
    markers = []
    for x, y in ((366, 176), (438, 211), (497, 211), (557, 229), (1507, 343)):
        assert red_trace[y-5:y+6, x-5:x+6].sum() >= 90
        markers.append({
            "center_px": [x, y],
            "cycles": (x - 318) * cycle_per_pixel,
            "cycle_interval": [(x + delta - 318) * cycle_per_pixel for delta in (-8, 8)],
            "retention_pct": (1149 - y) * pct_per_pixel,
            "geometry_interval_pct": [(1149 - y + delta) * pct_per_pixel for delta in (-8, 8)],
        })
    assert markers[-1]["geometry_interval_pct"][0] <= 72 <= markers[-1]["geometry_interval_pct"][1]
    windows = {
        str(limit): [idx for idx, mark in enumerate(markers) if mark["cycle_interval"][1] <= limit]
        for limit in (500, 1000)
    }
    assert windows == {"500": [0], "1000": [0, 1, 2]}
    return {
        "doi": "10.1016/j.inoche.2021.108523",
        "panel": "Figure 7",
        "sample": "OPAC",
        "author_endpoint": {"cycle_count": 5000, "retention_pct": 72},
        "same_paper_composite_endpoint_pct": 75,
        "markers": markers,
        "conservative_windows": windows,
        "unknown_cycling_fields": ["electrode_configuration", "current_A_g", "electrolyte", "voltage_window", "reference_electrode"],
        "status": "hold_actual_cycling_protocol",
    }


def corn_straw():
    reader = PdfReader(CACHE / "corn_straw.pdf")
    method = normalized(reader.pages[3].extract_text())
    results = normalized(reader.pages[11].extract_text())
    caption_and_conclusion = normalized(reader.pages[12].extract_text())
    assert all(value in method for value in ("saturated calomel", "6 M KOH", "three -electrode"))
    assert all(value in results for value in ("5,000 cycles", "97.12%", "92.6%", "25 cycles"))
    assert "50,000 cycles" in caption_and_conclusion and "5,000 cycles" in caption_and_conclusion
    figure = reader.pages[12].images[0].image.convert("RGB")
    assert figure.size == (883, 713)
    rgb = np.asarray(figure, dtype=np.int16)
    assert all((rgb[626:637, x].max(axis=1) < 80).sum() >= 7 for x in (190, 315, 818))
    curves = []
    for name, body, initial, terminal, y0 in (
        ("CS-AKAC803", 97.12, 239.0, 232.1, 99),
        ("CS-MSAC", 92.6, 135.0, 125.2, 496),
    ):
        red, _, blue = rgb.transpose(2, 0, 1)
        color = red - blue if name == "CS-AKAC803" else blue - red
        assert all((color[y0-11:y0+12, x-4:x+5] > 50).sum() >= 10
                   for x in (202, 215, 227, 240, 252, 265, 278, 290, 303, 315))
        curves.append({
            "legend": name,
            "body_retention_pct": body,
            "annotated_capacitance_F_g": [initial, terminal],
            "annotation_ratio_pct": 100 * terminal / initial,
            "first_visible_marker_nominal_cycles": 100,
            "separable_marker_counts_10_20_excluding_first_and_boundary": [3, 8],
        })
    return {
        "doi": "10.20964/2019.08.38", "panel": "Figure 7", "pdf_page": 13,
        "electrode_system": "3E", "reported_current_A_g": 1, "electrolyte": "6 M KOH",
        "reference_electrode": "SCE", "caption_cycles_raw": 50000,
        "body_cycles": 5000, "figure_axis_last_marker_nominal_cycles": 5000,
        "controls": curves, "molten_salt_sample_alias_body": "CS-MSAC3",
        "CS-SHAC": {"qualitative_decay_after_cycles": 25, "plotted_curve": False, "long_cycle_retention": None},
        "status": "high_retention_controls_cycle_caption_conflict_preserved",
    }


def role_checks():
    lotus = normalized("".join(ET.parse(LOCAL / "PMC8707477/main.xml").getroot().itertext()))
    assert "65.9% (LTSC_K900)" in lotus and "more than 99% capacitance" in lotus
    purple_root = ET.parse(LOCAL / "PMC10958655/main.xml").getroot()
    purple = normalized("".join(purple_root.itertext()))
    fig = next(f for f in purple_root.findall(".//fig") if f.findtext("label") == "Figure 7")
    caption = normalized("".join(fig.find("caption").itertext()))
    assert "1.0 mol L" in caption and "KOH" in caption and "two-electrode cell" in caption
    assert "current density of 6 A" in purple and "registered at 1.0 A" in purple
    return {
        "lotus_seed": {"doi": "10.3390/nano11123175", "rate_retention_pct": 65.9, "rate_current_A_g": 50,
                       "actual_cycle_retention_gt_pct": 99, "actual_cycle_count": 10000},
        "mantis_shrimp": {"doi": "10.1016/j.est.2023.106900", "hybrid_zinc_ion_retention_pct": 79.82,
                         "hybrid_zinc_ion_cycle_count": 50000, "symmetric_device_retention_pct": 96.7,
                         "symmetric_device_cycle_count": 10000},
        "exfoliated_corncob": {"doi": "10.1039/c4ta06110a", "rate_retention_pct": 78, "rate_current_A_g": 40,
                              "potential_cycle_count": 5000, "potential_cycle_loss_pct": 3},
        "purple_corncob": {"doi": "10.1021/acsenvironau.3c00048", "reported_retention_pct": 76,
                           "cycle_count": 50000, "figure7c_visible_early_cycles": [2500],
                           "figure7_caption_A_g": 1, "device_body_cycle_A_g": 6, "device_body_read_A_g": 1,
                           "status": "existing_hold_configuration_electrolyte_protocol_and_sparse_early_points"},
    }


if __name__ == "__main__":
    assert all(sha(path) == digest for path, digest in FILES.items())
    evidence = {
        "opac": orange_peel(), "corn_straw": corn_straw(), "role_checks": role_checks(),
        "protected": {path.relative_to(ROOT).as_posix(): digest for path, digest in FILES.items()},
        "new_fits": 0, "new_admissions": 0, "external_acceptances": 0,
    }
    OUT.mkdir(exist_ok=True)
    write(OUT / "protocol_evidence.json", evidence)
