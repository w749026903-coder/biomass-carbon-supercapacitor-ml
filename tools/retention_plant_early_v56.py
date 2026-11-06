"""Reproduce the Fig. 4(F) audit using only guarded early plot regions."""

from hashlib import sha256
import json
import logging
from pathlib import Path
import subprocess
import sys

import numpy as np
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.retention_wood_fig8_early_v50 import pixel_gate

BASE = ROOT / "保持率达标研究_v3_主线与近优组合_20261030"
OUT = BASE / "第五十六轮_植物蛋白木质素盲态轴与早期输入_20261107"
FREEZE = "e9635ae"
CACHE = ROOT / ".local-literature-cache/P55"
MAIN_SHA = "e21a31fcbf86d21e17b1cfcc5059b061dd1067f3dc46bb71c4757366b3d42df7"
SI_SHA = "f6e4481f814f6ea245735825c570728194bf300a174e58b7c5a055566165a89b"
# External labels and the 1,000/2,000/3,000 tick centers, established before viewing.
GEOMETRY = ((734, 1038, 1248, 1445), (735, 1445, 1248, 1476), (701, 1040, 733, 1444),
            (777, 1040, 1438), (771.8, 1207.8), 7)


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def early_blue(image, threshold):
    red, green, blue = np.asarray(image, dtype=np.int16).transpose(2, 0, 1)
    return (blue - red > threshold) & (blue - green > threshold)


def audit():
    plan = OUT / "screen_plan.json"
    git = ["git", "-c", f"safe.directory={ROOT.as_posix()}"]
    rel = plan.relative_to(ROOT).as_posix()
    assert subprocess.check_output(git + ["show", f"{FREEZE}:{rel}"], cwd=ROOT) == plan.read_bytes()
    protected = json.loads(plan.read_text(encoding="utf-8"))["protected"]
    assert all(digest(ROOT / path) == expected for path, expected in protected.items())
    main = CACHE / "plant_publisher_sealed.pdf"
    supplement = CACHE / "plant_supp_sealed.pdf"
    assert digest(main) == MAIN_SHA and digest(supplement) == SI_SHA
    logging.getLogger("pypdf").setLevel(logging.ERROR)
    page = PdfReader(main).pages[4]
    figure, = (entry.image.convert("RGB") for entry in page.images if entry.name == "Im5.png")
    assert figure.size == (1250, 1505)
    regions, comparisons = pixel_gate(figure, GEOMETRY)
    assert comparisons == 28

    thresholds = (25, 50, 75)
    counts = {}
    for name in ("early10", "early20"):
        counts[name] = []
        for threshold in thresholds:
            mask = early_blue(regions[name], threshold)
            counts[name].append(int(mask.sum()))
            # Reproduce the blue ring at x≈842, with a blank center and ink on each side.
            if name == "early20":
                assert not mask[81, 65]
                assert mask[76:80, 65].any() and mask[83:87, 65].any()
                assert mask[81, 60:64].any() and mask[81, 67:71].any()
    assert counts == {"early10": [142, 123, 105], "early20": [371, 320, 274]}, counts
    return {
        "phase": 56,
        "freeze_commit": FREEZE,
        "plan_sha256": digest(plan),
        "protected_hashes_checked": len(protected),
        "doi": "10.1021/acsomega.7b01876",
        "main": {
            "sha256": MAIN_SHA, "figure": "4(F)", "system": "2E", "current_a_g_reported": 5,
            "horizon_cycles": 3000, "x_tick_centers_px": [771.8, 917.3, 1062.0, 1207.8],
            "x_ticks_cycles": [0, 1000, 2000, 3000],
            "plot_axis_band_calibration_guard": GEOMETRY, "late_pixel_byte_comparisons": comparisons,
            "early_positive_control_passed": True, "blue_thresholds": thresholds,
            "early_blue_pixel_counts": counts,
            "safe_crop_right_edges_exclusive_px": [808, 852],
            "manually_separable_positive_marks_early10_early20": [0, 1],
            "single_early_marker_center_x_px_approx": 842,
            "normalization": "author initial capacitance; exact cycle unreported",
            "held": "too few early markers, sample and same-test electrolyte linkage and source lineage open",
        },
        "supplement": {"sha256": SI_SHA, "figure": "S5", "axis_max_cycles": 6000,
                       "disposition": "separate candidate pending test linkage; axis only"},
        "new_early_inputs": 0, "predictions_locked": 0, "endpoint_exposures": 0, "new_fits": 0,
        "canonical_admissions": 0, "external_sources": 0,
    }


if __name__ == "__main__":
    print(json.dumps(audit(), indent=2, ensure_ascii=False))
