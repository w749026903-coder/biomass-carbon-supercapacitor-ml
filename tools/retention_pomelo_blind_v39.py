"""Read only the approved early pixels and axis ticks of the sealed pomelo plots."""

from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

import numpy as np
from pypdf import PdfReader

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.retention_blind_geometry_v32 import CACHE, OUT as P32, ROOT, flat, protocol, read, sha, write
from tools.retention_blind_reserve_v22 import db_matches
from tools.retention_suaeda_case_v16 import feature_row


OUT = P32.parent / "第三十九轮_柚子籽盲态输入核验_20261106"
DOI = "10.1039/d0na00778a"
XML = CACHE / "PMC9419826_sealed_fulltext.xml"


def pixels(image, bounds):
    return np.asarray(image.crop(bounds).convert("RGB"), dtype=np.int16)


def three_electrode(image, early_bound):
    assert image.size == (1979, 1835)
    assert early_bound == 1277
    # The x-axis strip below the plotting area contains ticks and labels only.
    x_strip = pixels(image, (1130, 1743, 1873, 1748)).max(axis=2) < 145
    x_ticks = [1138.5, 1283.5, 1429., 1572.5, 1718.5, 1863.5]
    assert all(x_strip[:, round(x)-1130].sum() >= 4 for x in x_ticks)
    y_strip = pixels(image, (1081, 1268, 1104, 1742)).max(axis=2) < 155
    y_ticks = [1275., 1390.5, 1506., 1622.5, 1738.5]
    assert all(y_strip[round(y)-1268].sum() >= 10 for y in y_ticks)
    cycle_scale = 10000 / (x_ticks[-1] - x_ticks[0])
    pct_scale = 80 / (y_ticks[-1] - y_ticks[0])
    assert early_bound < x_ticks[1]
    left, top = 1197, 1253
    red, green, blue = pixels(image, (left, top, early_bound, 1301)).transpose(2, 0, 1)
    marker_bands = [(1216, 1229), (1232, 1240), (1247, 1256), (1260, 1270)]
    centers = []
    points = []
    for lo, hi in marker_bands:
        threshold_centers = []
        for threshold in (60, 65, 70):
            mask = (blue-red > threshold) & (blue-green > threshold-10)
            core = mask[:, lo-left:hi-left]
            count = core.sum(axis=0)
            assert count.max() >= 13
            prominent = np.flatnonzero(count >= .8 * count.max())
            yy, xx = np.where(core[:, prominent])
            threshold_centers.append((float(lo + prominent[xx].mean()), float(top + yy.mean())))
        assert np.ptp(threshold_centers, axis=0).max() < 1
        x, y = threshold_centers[1]
        cycle = (x - x_ticks[0]) * cycle_scale
        retention = 100 - (y - y_ticks[0]) * pct_scale
        points.append({
            "cycle_reading": cycle,
            "cycle_interval": [cycle - 6 * cycle_scale, cycle + 6 * cycle_scale],
            "early_ordinate_pct": retention,
            "geometry_interval_pct": [retention - 5 * pct_scale, retention + 5 * pct_scale],
        })
        centers.append({"color_core_px": [x, y], "x_band_ltr": [lo, hi]})
    # The four glyph cores have low-color valleys between them at the central threshold.
    core_count = ((blue-red > 65) & (blue-green > 55)).sum(axis=0)
    assert all(core_count[hi-left:next_lo-left].min() <= 1
               for (_, hi), (next_lo, _) in zip(marker_bands, marker_bands[1:]))
    assert all(a["cycle_interval"][1] < b["cycle_interval"][0] for a, b in zip(points, points[1:]))
    assert all(1000 < point["cycle_interval"][0] < point["cycle_interval"][1] < 2000 for point in points)
    features, count = feature_row(points, 10000, .2)
    # With cycle centers fixed, linear regression is affine in the four ordinate reads.
    x = np.asarray([point["cycle_reading"] for point in points])
    weights = (x - x.mean()) / np.square(x - x.mean()).sum() * 1000
    slope_half_width = np.abs(weights).sum() * 5 * pct_scale
    slope = features["early_retention_slope_per_1000_cycles"]
    return {
        "marker_counts_10_20": [0, count],
        "scope": "Four later cores within the allowed early crop. Earlier overlapping points are excluded.",
        "centers": centers, "points": points,
        "x_tick_centers_px": x_ticks, "y_tick_centers_px": y_ticks,
        "geometry_feature_estimate": features,
        "fixed_cycle_ordinate_stress_slope_pp_per_1000": [slope-slope_half_width, slope+slope_half_width],
        "status": "passes_20pct_marker_gate_pending_prediction_freeze_and_uncertainty_handling",
    }


def two_electrode(image, early_bound):
    assert image.size == (2003, 2155) and early_bound == 1260
    red, green, blue = pixels(image, (1112, 1442, early_bound, 1500)).transpose(2, 0, 1)
    trace = (red-blue > 63) & (green-blue > 33) & (red-green > 35)
    occupied = trace.any(axis=0)
    assert occupied[:75].all() and occupied.sum() > 130
    return {
        "marker_counts_10_20": [0, 0],
        "orange_trace_columns": int(occupied.sum()),
        "status": "hold_overlapping_glyphs_and_connected_trace",
    }


def protocol_facts():
    xml = ET.parse(XML).getroot()
    assert any(p.get("pub-id-type") == "doi" and p.text.lower() == DOI for p in xml.findall(".//article-id"))
    body = xml.find("body")
    methods = body.find('.//sec[@id="sec7"]').findall("p")
    assert all(term in flat(methods[0]) for term in ("three-electrode", "two-electrode", "1 M KOH", "Hg/HgO"))
    # These tokens identify a sample; no raw caption or endpoint-bearing prose leaves this function.
    caption = re.split(r"\(([a-f])\)", flat(body.find('.//fig[@id="fig2"]/caption')))
    assert "PSAC-3" in caption[caption.index("f")+1]
    return {
        "3E": {**protocol("PMC9419826", "fig2", "f", "3E", 10, "sec7"), "sample": "PSAC-3",
               "method_reference": "Hg/HgO", "ordinate": "author-plotted capacitance retention (%)"},
        "2E": {**protocol("PMC9419826", "fig3", "f", "2E", 10, "sec7"), "sample": "PSAC symmetric device",
               "mass_basis_review": "method mentions a single electrode; cycling-current denominator not inferred"},
    }


def main():
    plan_path = OUT / "screen_plan.json"
    plan = read(plan_path)
    metadata_path = P32 / "metadata_freeze.json"
    geometry_path = P32 / "sealed_geometry.json"
    pdf_path = CACHE / "pomelo_publisher_sealed.pdf"
    assert sha(metadata_path) == plan["prior_metadata_sha256"]
    assert sha(geometry_path) == plan["prior_geometry_sha256"]
    assert sha(pdf_path) == plan["publisher_pdf_sha256"]
    structure = read(P32 / "structural_screen.json")
    xml_row = next(row for row in structure["results"] if row["doi"] == DOI)
    assert ROOT / xml_row["local"] == XML and sha(XML) == xml_row["sha256"]
    matches = db_matches({DOI})[DOI]
    assert matches and not any(matches.values())
    p31 = next(P32.parent.glob("第三十一轮_*")) / "training_plan.json"
    assert DOI.encode() not in p31.read_bytes().lower()
    geo = read(geometry_path)
    assert geo["pomelo_correction_figure_flags"] == {"Fig3c": True, "Fig3f": False}
    pdf = PdfReader(pdf_path)
    panels = {}
    for system, key, screen in (("3E", "pomelo3e", three_electrode), ("2E", "pomelo2e", two_electrode)):
        details = geo["early_geometry"][key]
        page = pdf.pages[details["publisher_pdf_page"] - 1]
        panels[system] = screen(page.images[0].image, details["windows"]["20"]["bounds_ltrb"][2])
    write(OUT / "early_input_evidence.json", {
        "source_family": "doi:" + DOI, "source_family_count": 1,
        "frozen_plan_sha256": sha(plan_path), "frozen_plan_commit": "1913348",
        "protected_pdf_sha256": sha(pdf_path), "protected_xml_sha256": sha(XML),
        "current_database_exact_matches": matches, "p31_plan_exact_doi_present": False,
        "panels": panels, "protocols": protocol_facts(),
        "endpoints_revealed": 0, "predictions_locked": 0, "fits": 0,
        "canonical_admissions": 0, "independent_acceptances": 0,
    })


if __name__ == "__main__":
    main()
