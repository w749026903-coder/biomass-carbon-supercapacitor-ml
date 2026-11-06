"""Verify primary long-cycle figure evidence while keeping held inputs out of training."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess
import sys

import numpy as np
from PIL import Image
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.retention_blind_reserve_v22 import BASE, db_matches

OUT = BASE / "第五十三轮_三电极长循环定向补证_20261107"
CACHE = ROOT / ".local-literature-cache/P53"
FREEZE = "f1bf974"
ACS_ANCHORS = (100, 300, 500, 700, 900, 1100, 1300, 1500, 1700, 1900)
SAM_ANCHORS = (100, 200, 300, 400, 600, 700, 800, 900)


def read(path):
    return json.loads(path.read_bytes())


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def pixels(path, size):
    with Image.open(path) as image:
        assert image.size == size
        return np.asarray(image.convert("RGB"), dtype=np.int16)


def assert_tick(mask, x, y):
    assert np.any(mask[y - 1:y + 2, x - 1:x + 2])


def project_mark(anchor, samples, axes, horizon, margin):
    assert len(samples) == 3 and max(np.ptp(samples, axis=0)) <= 2
    x, y = map(float, np.median(samples, axis=0))
    x0, xn, y100, y0 = axes
    dx, dy = margin
    cycle = lambda px: horizon * (px - x0) / (xn - x0)
    percent = lambda py: 100 * (y0 - py) / (y0 - y100)
    window = 10 if anchor < horizon / 10 else 20
    bounds = [round(cycle(x - dx), 1), round(cycle(x + dx), 1)]
    assert 0 < bounds[0] < bounds[1] < horizon * window / 100
    return {"nominal_search_center_cycles": anchor, "pixel_xy": [x, y], "threshold_centers": samples,
            "first_window_pct": window, "cycle_geometry_estimate": round(cycle(x), 1), "cycle_geometry_range": bounds,
            "retention_pct_estimate": round(percent(y), 3),
            "retention_pct_geometry_range": [round(percent(y + dy), 3), round(percent(y - dy), 3)]}


def acs_marks(path):
    a = pixels(path, (3493, 1971))
    r, g, b = a.transpose(2, 0, 1)
    x0, xn, y100, y0 = axes = (1525, 3442, 1074.5, 1793.5)
    for x in (x0, xn):
        assert_tick(a.max(axis=2) < 65, x, 1801)
    for y in (1074, 1794):
        assert_tick((r - g > 45) & (b - g > 17), 1495, y)
    points = {anchor: [] for anchor in ACS_ANCHORS}
    for t in (55, 75, 95):
        mask = (r - g > t) & (b - g > 18) & (r > 95)
        # Compare the center and eight offsets on the visible X arms.
        score = sum(np.roll(mask, (dy, dx), (0, 1)).astype(np.uint8)
                    for dx, dy in ((0, 0), (-4, -4), (-4, 4), (4, -4), (4, 4), (-7, -7), (-7, 7), (7, -7), (7, 7)))
        for anchor in points:
            x = round(x0 + anchor / 10000 * (xn - x0))
            band = score[1058:1145, x - 6:x + 7]
            assert band.max() >= 8
            yi, xi = np.where(band == band.max())
            points[anchor].append([round(float(np.median(xi)) + x - 6), round(float(np.median(yi)) + 1058)])
    return {"panel": "Fig. 5(e)", "horizon": 10000, "image_sha256": digest(path), "axes_pixels": axes,
            "margin_xy_pixels": [5, 7], "thresholds": [55, 75, 95], "image_annotation_pct": 80,
            "first_reference_cycle_known": False, "reported_cycle_current_A_g": None, "cycle_electrode_configuration": None,
            "points": [project_mark(n, rows, axes, 10000, (5, 7)) for n, rows in points.items()],
            "disposition": "hold_cycle_configuration_and_actual_current_not_bound"}


def sam_marks(path):
    a = pixels(path, (3445, 1794))
    dark = a.max(axis=2)
    x0, xn, y100, y0 = axes = (156, 1068.5, 1002.5, 1676)
    for x in (156, 1068):
        assert_tick(dark < 65, x, 1687)
    for y in (1002, 1676):
        assert_tick(dark < 65, 145, y)
    points = {anchor: [] for anchor in SAM_ANCHORS}
    edge_y = []
    for t in (45, 65, 90):
        mask = dark < t
        for anchor in points:
            x = round(x0 + anchor / 5000 * (xn - x0))
            cols = np.arange(x - 4, x + 5)
            counts = mask[997:1060, cols].sum(axis=0)
            x = round(float(np.median(cols[counts == counts.max()])))
            hit = np.flatnonzero(mask[997:1060, x]) + 997
            assert 15 <= len(hit) <= 20 and hit[-1] - hit[0] == len(hit) - 1
            points[anchor].append([x, (int(hit[0]) + int(hit[-1])) / 2])
        # Read a near-center column on the last circle clear of the vertical frame.
        hit = np.flatnonzero(mask[1104:1140, 1063]) + 1104
        assert len(hit) >= 12
        edge_y.append((int(hit[0]) + int(hit[-1])) / 2)
    y = float(np.median(edge_y))
    percent = lambda py: 100 * (y0 - py) / (y0 - y100)
    interval = [round(percent(y + 4), 3), round(percent(y - 4), 3)]
    assert interval[0] > 75.11
    return {"panel": "Fig. 9(d)", "horizon": 5000, "image_sha256": digest(path), "axes_pixels": axes,
            "margin_xy_pixels": [4, 4], "thresholds": [45, 65, 90], "first_reference_cycle_known": False,
            "terminal_figure_pct": round(percent(y), 3), "terminal_figure_geometry_range": interval,
            "terminal_review_pct_unbound": 75.11, "paper_abstract_device": "SAM-700-4 symmetric PVA/SA/KOH gel device",
            "figure_and_adjacent_device_panels_support_2E": True, "cycle_caption_verified": False,
            "reported_cycle_current_A_g": None,
            "points": [project_mark(n, rows, axes, 5000, (4, 4)) for n, rows in points.items()],
            "disposition": "hold_unresolved_cycle_current_caption_and_secondary_value"}


def hsw_protocol(image, pdf):
    a = pixels(image, (2056, 1108))
    r, g, b = a[655:705, 1428:1525].transpose(2, 0, 1)
    coverage = [int(np.count_nonzero(np.any((r - g > t) & (r - b > t) & (r > 130), axis=0)))
                for t in (60, 80, 100)]
    assert coverage == [97, 97, 97]
    doc = PdfReader(pdf)
    page_text = [" ".join((page.extract_text() or "").split()) for page in doc.pages]
    full = " ".join(page_text)
    assert re.search(r"3.8.*?electrochemical", full, re.I)
    assert "10 A/g over 10,000 cycles (Fig. 10f)" in full and "cyclic retention was 84.6%" in full
    assert re.search(r"1\s*M Na2SO4 aqueous electrolyte \(three-electrode configuration\)", full)
    assert len(doc.pages[14].images) == 1 and doc.pages[14].images[0].image.size == (2056, 1108)
    return {"panel": "Fig. 10(f)", "horizon": 10000, "image_sha256": digest(image), "pdf_sha256": digest(pdf),
            "publisher_pdf_page": 15, "pdf_embeds_figure_as_raster": True,
            "system": "3E working electrode", "electrolyte": "1 M Na2SO4 aqueous", "reported_cycle_current_A_g": 10,
            "terminal_author_pct": 84.6, "red_left_axis_role": "capacitance retention", "black_right_axis_role": "coulombic efficiency",
            "early_color_band_coverage_columns_by_threshold": coverage, "early_color_band_columns": 97,
            "separable_early_markers_10_20": [0, 0], "within_long_low_retention_subset": False,
            "disposition": "hold_no_distinct_early_markers_and_no_original_cycle_table"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="Create evidence if absent")
    args = parser.parse_args()
    path = OUT / "screen_plan.json"
    git = ["git", "-c", f"safe.directory={ROOT.as_posix()}"]
    assert subprocess.check_output(git + ["show", f"{FREEZE}:{path.relative_to(ROOT).as_posix()}"], cwd=ROOT) == path.read_bytes()
    plan = read(path)
    assert all(digest(ROOT / name) == h for name, h in plan["protected"].items())
    access = read(CACHE / "publisher_access.json")
    targeted = read(CACHE / "target_access.json")
    hsw_access = read(CACHE / "access.json")["hsw_fig10"]
    for k, receipt in (("acs_gr5", access["acs_gr5"]), ("sam_gr9", targeted["sam_gr9"]), ("hsw_pdf", access["hsw_pdf"])):
        assert digest(CACHE / f"{k}.body") == receipt["sha256"]
    assert digest(CACHE / "hsw_fig10.body") == hsw_access["receipt"][3]
    assert access["acs_publisher"]["status"] == access["sam_publisher"]["status"] == 403
    result = [sam_marks(CACHE / "sam_gr9.body"), acs_marks(CACHE / "acs_gr5.body"),
              hsw_protocol(CACHE / "hsw_fig10.body", CACHE / "hsw_pdf.body")]
    dois = [p["doi"] for p in plan["candidates"]]
    matches = db_matches(set(dois))
    rows = [{"article_doi": doi, "sample": p["sample"], "catalog_exact_matches": matches[doi], **r}
            for doi, p, r in zip(dois, plan["candidates"], result)]
    evidence = {"phase": 53, "freeze_commit": FREEZE, "plan_sha256": digest(path), "candidates": rows,
                "target_assets": {"acs_fig5": access["acs_gr5"], "sam_fig9": targeted["sam_gr9"],
                                  "hsw_fig10": hsw_access, "hsw_publisher_pdf": access["hsw_pdf"]},
                "publisher_access": {"acs_body": 403, "sam_body": 403, "hsw_pdf": 200,
                                     "acs_supplement_probe": access["acs_si"]["status"],
                                     "sam_supplement_probe": access["sam_si"]["status"]},
                "scope": "all three previously seen source endpoints or cues; development only",
                "held_selected_early_plot_marks": 18, "new_early_inputs": 0, "new_fits": 0,
                "prediction_locks": 0, "canonical_admissions": 0, "external_acceptances": 0}
    dest = OUT / "evidence.json"
    payload = json.dumps(evidence, ensure_ascii=False, indent=2) + "\n"
    if args.write:
        with dest.open("x", encoding="utf-8", newline="\n") as f:
            f.write(payload)
    assert dest.read_bytes() == payload.encode("utf-8")
    print("Three primary curves checked. Eighteen selected early plotted markers held; no usable new inputs.")


if __name__ == "__main__":
    main()
