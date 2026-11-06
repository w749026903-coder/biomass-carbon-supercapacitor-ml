"""Verify the Fig. 8(d) repository image and keep it separate from raw cycling data."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "保持率达标研究_v3_主线与近优组合_20261030"
OUT = BASE / "第五十二轮_雨树碳循环附件与工况复核_20261107"
CACHE = ROOT / ".local-literature-cache"
FREEZE = "7ea55e8"


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def rgb_on_white(path):
    with Image.open(path) as source:
        assert source.format == "PNG" and source.size == (3216, 2461)
        image = source.convert("RGBA")
    return np.asarray(Image.alpha_composite(Image.new("RGBA", image.size, "white"), image).convert("RGB"))


def bands(mask, offset):
    hit = np.flatnonzero(mask) + offset
    return [(int(row[0]), int(row[-1])) for row in np.split(hit, np.where(np.diff(hit) != 1)[0] + 1) if row.size]


def center(mask, offset):
    (low, high), = bands(mask, offset)
    return (low + high) / 2


def compare_figure(repository, accepted):
    pixels = rgb_on_white(repository)
    other = rgb_on_white(accepted)
    diff = np.any(pixels != other, axis=2)
    ys, xs = np.nonzero(diff)
    assert len(xs) == 3417 and not np.any(diff[270:2060, 560:2780])
    bbox = [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1]
    dark = pixels.max(axis=2) < 50
    x_ticks = [(low + high) // 2 for low, high in bands(dark[2076, 540:2800], 540)]
    y_ticks = [(low + high) // 2 for low, high in bands(dark[270:2070, 570], 270)]
    assert x_ticks == [597, 1027, 1457, 1887, 2317, 2747] and y_ticks == [369, 790, 1211, 1632, 2052]
    color = pixels[400:550, x_ticks[-1], :]
    red = (color[:, 0] > 180) & (color[:, 1] < 60) & (color[:, 2] < 60)
    black_center = center(dark[440:550, 2735], 440)
    red_center = center(red, 400)
    normalize = lambda y: 100 * (y_ticks[-1] - y) / (y_ticks[-1] - y_ticks[0])
    endpoints = {}
    for label, y in (("H2SO4", black_center), ("Na2SO4", red_center)):
        endpoints[label] = {"center_y": y, "digitized_pct": round(normalize(y), 3),
                            "digitized_pct_range": [round(normalize(y + 4), 3), round(normalize(y - 4), 3)]}
    x_error = 3 * 5000 / (x_ticks[-1] - x_ticks[0])
    assert 1000 - x_error < 1000 < 1000 + x_error
    return {"repository_sha256": digest(repository), "accepted_image_sha256": digest(accepted),
            "file_bytes_identical": False, "rgb_differing_pixels": len(xs), "rgb_diff_bbox_exclusive": bbox,
            "comparison_plot_roi_rgb_identical": True, "dimensions": [3216, 2461],
            "axes": ["Cycles", "Capacitance retention (%)"], "x_tick_pixels": x_ticks, "y_tick_pixels": y_ticks,
            "nominal_positive_marker_cycles_per_trace": [1000, 2000, 3000, 4000, 5000],
            "visual_marker_roles": {"black_square": "H2SO4", "red_circle": "Na2SO4"},
            "graph_origin_100_pct": True, "physical_reference_cycle_known": False,
            "first_positive_marker_geometry_cycles": [round(1000 - x_error, 1), round(1000 + x_error, 1)],
            "early10_max_positive_markers_per_trace": 0, "early20_max_positive_markers_per_trace": 1,
            "early20_conservative_positive_markers_per_trace": 0,
            "endpoints": endpoints, "endpoints_geometry_y_margin_pixels": 4}


def test_protocol(manuscript):
    with ZipFile(manuscript) as archive:
        doc = ET.fromstring(archive.read("word/document.xml"))
    paragraphs = [" ".join("".join(n.text or "" for n in p.findall(".//{*}t")).split()) for p in doc.findall(".//{*}p")]
    relevant, = [p for p in paragraphs if "cyclic capacitance retention or cyclic stability" in p]
    rate, cyclic = relevant.split("The cyclic capacitance retention or cyclic stability", 1)
    cyclic = cyclic.split("The CV of the same symmetric supercapacitor", 1)[0]
    assert all(k in rate for k in ("NSAC8||NSAC8", "0-1.2V", "0-1.8V", "0.5-10 Ag−1", "Fig. 8(b) and 8(c)", "0.5 Ag−1"))
    assert all(k in cyclic for k in ("91.3 %", "94.3%", "5000 cycles", "Fig. 8(d)"))
    assert not re.search(r"Ag[−-]1|A\s*/\s*g", cyclic)
    return {"accepted_sha256": digest(manuscript), "system": "2E symmetric device", "sample": "NSAC8||NSAC8",
            "cycles": 5000, "author_figure_8d_retention_pct": {"H2SO4": 91.3, "Na2SO4": 94.3},
            "fig8d_actual_cycle_current_A_g": None,
            "device_cv_window_V_not_explicitly_bound_to_cycle_test": {"H2SO4": [0, 1.2], "Na2SO4": [0, 1.8]},
            "fig8bc_rate_sweep_A_g": [0.5, 10], "reported_device_specific_capacitance_test_A_g": 0.5,
            "fig_s5_role": "CV after long GCD cycling", "development_only": True, "source_groups": 1}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="Create the evidence file if absent")
    args = parser.parse_args()
    plan_path = OUT / "screen_plan.json"
    git = ["git", "-c", f"safe.directory={ROOT.as_posix()}"]
    assert subprocess.check_output(git + ["show", f"{FREEZE}:{plan_path.relative_to(ROOT).as_posix()}"], cwd=ROOT) == plan_path.read_bytes()
    plan = json.loads(plan_path.read_bytes())
    assert all(digest(ROOT / name) == h for name, h in plan["protected"].items())
    inventories = {}
    for name, count in zip(plan["folders"], (6, 1, 9)):
        raw = CACHE / "P52" / f"{name.lower().replace(' ', '_')}.json"
        rows = json.loads(raw.read_bytes())
        assert len(rows) == count and all(row["content_details"]["content_type"] == "image/png" for row in rows)
        inventories[name] = [{"filename": row["filename"], "bytes": row["size"], "sha256": row["content_details"]["sha256_hash"]}
                             for row in rows]
    image = CACHE / "P52/samanea_figure_8d.png"
    item, = [row for row in inventories["Figure 8"] if row["filename"] == "Figure 8(d).png"]
    assert image.stat().st_size == item["bytes"] and digest(image) == item["sha256"]
    figure = compare_figure(image, CACHE / "P48/samanea_fig8d_aam.png")
    paper = test_protocol(CACHE / "P48/samanea_spiral_api.payload")
    for label, value in paper["author_figure_8d_retention_pct"].items():
        lo, hi = figure["endpoints"][label]["digitized_pct_range"]
        assert lo <= value <= hi
    evidence = {"phase": 52, "freeze_commit": FREEZE, "plan_sha256": digest(plan_path), "dataset_doi": plan["dataset_doi"],
                "article_doi": plan["article_doi"], "inventories": inventories, "figure": figure, "protocol": paper,
                "status": "hold_raster_only_early_window_sparse_cycle_current_unverified",
                "new_early_inputs": 0, "prediction_locks": 0, "new_fits": 0, "canonical_admissions": 0,
                "external_acceptances": 0}
    dest = OUT / "evidence.json"
    payload = json.dumps(evidence, ensure_ascii=False, indent=2) + "\n"
    if args.write:
        with dest.open("x", encoding="utf-8", newline="\n") as f:
            f.write(payload)
    assert dest.read_bytes() == payload.encode("utf-8")
    print("Three relevant folders, 16 PNG files, Fig. 8(d) plot identity, two endpoints, five protected hashes verified.")


if __name__ == "__main__":
    main()
