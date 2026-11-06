"""Reproduce early-only readings from the sealed publisher-native Fig. 8."""

import argparse
from hashlib import md5
import json
import math
from pathlib import Path
import sys
from xml.etree import ElementTree as ET

import numpy as np
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.retention_mask_gate_v46 import BASE, evidence_regions, pixel_identity
from tools.retention_wood_archive_v49 import FIGURE_ID, OUT as P49, flat, frozen, protocol, read, sha

OUT = BASE / "第五十轮_木源碳双电极早期盲态图读_20261107"
CACHE = ROOT / ".local-literature-cache/P50"
FREEZE = "623fbc8"
PDF_SHA = "3daf6421aa326fea0ce240ec9d65d408fb9f87452fe6adc61d9c0bf3ce0f6ea2"
PDF_MD5 = "0873a30424092e24611579af0e0c4dbe"
XML_SHA = "a4063c2ba7948d7e37836191d924211c9da93f7d24d67c05e984c219dbd85458"
THRESHOLDS = (70, 85, 100)
ANCHORS = (300, 500, 700, 800, 1200, 1400, 1600, 1800)
X_MARGIN, Y_MARGIN = 6, 16
PANELS = {
    "a": ((98, 5, 1000, 768), (65, 770, 1000, 800), (65, 41, 94, 760), (104, 74, 340), (100.5, 958.5), 8),
    "b": ((98, 835, 1000, 1598), (65, 1600, 1000, 1628), (65, 867, 94, 1587), (104, 925, 1160), (100.5, 959.5), 8),
}


def pixel_gate(image, geometry):
    regions = evidence_regions(image, *geometry)
    original = pixel_identity(regions)
    plot, _, _, band, (x0, xt), guard = geometry
    comparisons = 0
    for fraction, unchanged in ((0.1, ("early10", "x_axis", "y_axis")), (0.2, tuple(regions))):
        right = math.floor(x0 + fraction * (xt - x0) - guard)
        assert right == band[0] + regions[f"early{int(fraction * 100)}"].width
        for color in ((0, 0, 0), (255, 255, 255), (255, 0, 0), (0, 0, 255)):
            late = image.copy()
            late.paste(color, (right, plot[1], plot[2], plot[3]))
            actual = pixel_identity(evidence_regions(late, *geometry))
            assert all(actual[key] == original[key] for key in unchanged)
            comparisons += len(unchanged)
    early = image.copy()
    xy = band[:2]
    early.putpixel(xy, tuple(255 - value for value in early.getpixel(xy)))
    actual = pixel_identity(evidence_regions(early, *geometry))
    assert {key for key in original if actual[key] != original[key]} == {"early10", "early20"}
    return regions, comparisons


def y_ticks(strip, box):
    # Black glyph bands at the right edge of the exterior y-label strip.
    pixels = np.asarray(strip)[:, -5:]
    indexes = np.flatnonzero(np.any(pixels.max(axis=2) < 100, axis=1)) + box[1]
    bands = np.split(indexes, np.where(np.diff(indexes) > 1)[0] + 1)
    values = [float(band.mean()) for band in bands if len(band) > 1]
    assert len(values) == 6 and all(115 < gap < 130 for gap in np.diff(values))
    return values


def track_points(regions, geometry, color, ticks, cycles):
    _, _, _, (left, top, bottom), (x0, xt), _ = geometry
    slope, intercept = np.polyfit(ticks, [100, 98, 96, 94, 92, 90], 1)
    selected, held = [], []
    for anchor in ANCHORS:
        window = 10 if anchor < cycles / 10 else 20
        rgb = np.asarray(regions[f"early{window}"], dtype=np.int16)
        r, g, b = rgb.transpose(2, 0, 1)
        y, x = np.mgrid[top:bottom, left:left + r.shape[1]]
        # Keep the upper blue b-track separate from the purple line in the same crop.
        center_band = np.clip(941 + 1.26 * (x - 116), 960, 1170)
        approx = round(x0 + anchor / cycles * (xt - x0))
        cols = np.arange(approx - 3, approx + 6)
        assert left <= cols[0] and cols[-1] < left + r.shape[1]
        centers = []
        for threshold in THRESHOLDS:
            if color == "red":
                mask = (r - g > threshold) & (r - b > threshold) & (r > 120)
            else:
                mask = (b - r > threshold) & (b - g > threshold) & (r < 55)
                mask &= (y > center_band - 38) & (y < center_band + 28)
            strength = mask[:, cols - left].sum(axis=0)
            px = int(cols[np.argmax(strength)])
            marked = np.flatnonzero(mask[:, px - left]) + top
            if len(marked) < 3 or marked[0] <= top or marked[-1] >= bottom - 1:
                break
            centers.append((px, float((marked[0] + marked[-1]) / 2)))
        if len(centers) != len(THRESHOLDS) or max(np.ptp(centers, axis=0)) > 2:
            held.append({"nominal_search_center_cycles": anchor, "reason": "insufficient or unstable peak across color thresholds"})
            continue
        px, py = map(float, np.median(centers, axis=0))
        cycle = cycles * (px - x0) / (xt - x0)
        dx = cycles * X_MARGIN / (xt - x0)
        retention = float(slope * py + intercept)
        dy = float(abs(slope) * Y_MARGIN)
        assert 0 < cycle - dx < cycle + dx <= cycles * window / 100
        selected.append({
            "nominal_search_center_cycles": anchor, "first_covered_window_pct": window,
            "median_pixel_xy": [px, py], "threshold_pixel_xy": centers,
            "cycle_geometry_estimate": round(cycle), "cycle_geometry_range": [math.floor(cycle - dx), math.ceil(cycle + dx)],
            "cr_plot_pct_geometry_estimate": round(retention, 3),
            "cr_plot_pct_geometry_range": [math.floor(1000 * (retention - dy)) / 1000, math.ceil(1000 * (retention + dy)) / 1000],
        })
    assert len({point["median_pixel_xy"][0] for point in selected}) == len(selected)
    return {"early10": sum(point["first_covered_window_pct"] == 10 for point in selected), "early20": len(selected),
            "points": selected, "held_searches": held}


def build(archive_access):
    plan = frozen(OUT / "screen_plan.json", FREEZE)
    assert all(sha(ROOT / name) == digest for name, digest in plan["protected"].items())
    source = read(P49 / "evidence.json")
    assert archive_access["dataset_version_doi"] == source["inventory"]["record_version_doi"]
    assert archive_access["result"] == "no_verified_archive_or_member_body"
    pdf_file = CACHE / "wood_publisher_sealed.pdf"
    assert sha(pdf_file) == PDF_SHA and md5(pdf_file.read_bytes()).hexdigest() == PDF_MD5
    pdf = PdfReader(pdf_file)
    assert len(pdf.pages) == 14
    native = next(img.image.convert("RGB") for img in pdf.pages[11].images if img.name == "Im10.png")
    assert native.size == (1000, 1670)
    xml = CACHE.parent / "P49/wood_epmc.xml"
    assert sha(xml) == XML_SHA and protocol(xml) == source["publisher_protocol"]
    xml_doc = ET.parse(xml).getroot()
    caption = flat(xml_doc.find(f".//fig[@id='{FIGURE_ID}']/caption")).casefold()
    assert all(term not in caption for term in ("awc", "yp-80f", "initial", "red", "blue"))
    panel_roles = source["publisher_protocol"]["figure_caption_panel_roles"]
    panels = {}
    for name, geometry in PANELS.items():
        regions, comparisons = pixel_gate(native, geometry)
        ticks = y_ticks(regions["y_axis"], geometry[2])
        colors = ("red",) if name == "a" else ("red", "blue")
        tracks = {color: track_points(regions, geometry, color, ticks, plan["target_cycles"]) for color in colors}
        panels[name] = {"electrolyte_panel": panel_roles[name], "x_axis": "Number of Cycles", "y_axis": "CR%",
                        "calibration_geometry": geometry, "exterior_y_label_centers": ticks,
                        "late_mutations": 8, "byte_identical_region_comparisons": comparisons,
                        "early_positive_control_changed_only_early_regions": True, "unbound_tracks": tracks}
    return {"status": "hold_unbound_early_figure_values_no_trainable_inputs", "plan_sha256": sha(OUT / "screen_plan.json"),
            "frozen_commit": FREEZE, "pdf": {"sha256": PDF_SHA, "repository_md5": PDF_MD5, "page": 12,
                                             "object": "Im10.png", "native_size": native.size},
            "xml_sha256": XML_SHA, "archive_access": archive_access,
            "protocol": source["publisher_protocol"], "source_lineage": source["source_lineage"]["provisional_source_clusters"],
            "figure_scope": "selected glyphs only; incomplete trace inventory; no sample-to-track or reference binding",
            "figure_geometry_uncertainty": {"x_pixels": X_MARGIN, "y_pixels": Y_MARGIN, "thresholds": THRESHOLDS,
                                            "interval_kind": "readout sensitivity, not confidence interval or author measurement"},
            "panels": panels, "unbound_plot_markers": sum(track["early20"] for panel in panels.values()
                                                            for track in panel["unbound_tracks"].values()),
            "endpoint_exposed": False, "prediction_locks": 0, "new_early_inputs": 0, "new_fits": 0,
            "canonical_admissions": 0, "external_acceptances": 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="Create a new audit artifact only if absent.")
    args = parser.parse_args()
    out = OUT / "evidence.json"
    # The historical HTTP receipt is an input to the audit, independent of image recomputation.
    access = read(CACHE / "archive_access.json") if args.write else read(out)["archive_access"]
    evidence = build(access)
    payload = json.dumps(evidence, ensure_ascii=False, indent=2) + "\n"
    if args.write:
        with out.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
    assert out.read_bytes() == payload.encode("utf-8")
    for name, panel in evidence["panels"].items():
        print(name, [(color, track["early10"], track["early20"]) for color, track in panel["unbound_tracks"].items()])
    print("Verified early-only evidence; new usable inputs:", evidence["new_early_inputs"])


if __name__ == "__main__":
    main()
