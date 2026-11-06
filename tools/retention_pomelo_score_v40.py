"""Score the frozen case and compare the author label with the same-panel plot."""

from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess
from xml.etree import ElementTree as ET

import numpy as np
from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "保持率达标研究_v3_主线与近优组合_20261030"
OUT = BASE / "第四十轮_柚子籽三电极外部锁定_20261106"
P39 = BASE / "第三十九轮_柚子籽盲态输入核验_20261106"


def read(path):
    return json.loads(path.read_bytes())


def sha(path):
    return sha256(path.read_bytes()).hexdigest()


def check_lock():
    claim = read(OUT/"reveal_claim.json")
    receipt = read(OUT/"pre_reveal_verification.json")
    commit = claim["verified_remote_lock_commit"]
    assert re.fullmatch(r"[0-9a-f]{40}", commit)
    for name in ("training_plan.json", "predictions_locked.json", "pre_reveal_verification.json"):
        path = OUT/name
        spec = commit + ":" + path.relative_to(ROOT).as_posix()
        assert subprocess.check_output(
            ["git", "-c", f"safe.directory={ROOT.as_posix()}", "show", spec], cwd=ROOT,
        ) == path.read_bytes()
    assert claim["predictions_sha256"] == receipt["predictions_sha256"] == sha(OUT/"predictions_locked.json")
    assert receipt["endpoints_revealed"] == 0 and receipt["fit_failures"] == 0
    return commit


def author_value(path):
    results = ET.parse(path).getroot().find("body")
    found = []
    for paragraph in results.findall(".//p"):
        if not any("fig2" in ref.get("rid", "").split() for ref in paragraph.findall(".//xref")):
            continue
        s = " ".join("".join(paragraph.itertext()).split())
        if not re.search(r"Fig\.\s*2\(?f\)?", s, re.I):
            continue
        found.extend(re.findall(r"PSAC-3[^.]*?capacitance retention of (\d+(?:\.\d+)?)% after 10\s*000 cycles", s))
    value, = found
    return value


def graph_endpoint(path):
    early = read(P39/"early_input_evidence.json")["panels"]["3E"]
    x_ticks, y_ticks = early["x_tick_centers_px"], early["y_tick_centers_px"]
    figure = PdfReader(path).pages[4].images[0].image
    assert figure.size == (1979, 1835)
    left, top = 1852, 1288
    pixels = np.asarray(figure.crop((left, top, 1870, 1334)).convert("RGB"), dtype=np.int16)
    red, green, blue = pixels.transpose(2, 0, 1)
    centers = []
    for threshold in (55, 65, 75):
        rows, cols = np.where((blue-red > threshold) & (blue-green > threshold-10))
        assert len(rows) > 70
        centers.append((left + float(cols.mean()), top + float(rows.mean())))
    assert np.ptp(centers, axis=0).max() < 2
    x, y = centers[1]
    sx = 10000/(x_ticks[-1]-x_ticks[0])
    sy = 80/(y_ticks[-1]-y_ticks[0])
    cycle_range = [(x + dx - x_ticks[0])*sx for dx in (-8, 8)]
    assert cycle_range[0] < 10000 < cycle_range[1]
    retention = 100 - (y-y_ticks[0])*sy
    return {"center_px": [x, y], "cycle_geometry_band": cycle_range,
            "retention_pct": retention, "geometry_band_pct": [retention-5*sy, retention+5*sy]}


def score(values, truth, baselines):
    center_error = abs(values[0]-truth)
    stress = np.asarray(values[17:])
    errors = abs(stress-truth)
    result = {
        "center_prediction_pct": values[0], "center_signed_error_pp": values[0]-truth,
        "center_absolute_error_pp": center_error, "xy_corner_prediction_pct": [float(stress.min()), float(stress.max())],
        "xy_corner_absolute_error_pp": [float(errors.min()), float(errors.max())],
        "xy_corners_with_absolute_error_at_most_2pp": int((errors <= 2).sum()),
    }
    if baselines:
        result["center_relative_error_reduction_vs_baselines"] = {
            key: 1-center_error/abs(other[0]-truth) for key, other in baselines.items()
        }
        better = np.ones(len(stress), dtype=bool)
        for other in baselines.values():
            better &= errors <= .8 * abs(np.asarray(other[17:])-truth)
        result["xy_corners_at_least_20pct_better_than_every_baseline"] = int(better.sum())
    return result


if __name__ == "__main__":
    lock = check_lock()
    plan = read(OUT/"training_plan.json")
    xml = ROOT/".local-literature-cache/P32/PMC9419826_sealed_fulltext.xml"
    pdf = xml.with_name("pomelo_publisher_sealed.pdf")
    assert all(sha(p) == plan["protected"][p.relative_to(ROOT).as_posix()] for p in (xml, pdf))
    raw = author_value(xml)
    truth = float(raw)
    graph = graph_endpoint(pdf)
    graph["consistent_with_author_value"] = graph["geometry_band_pct"][0] <= truth <= graph["geometry_band_pct"][1]
    predictions = read(OUT/"predictions_locked.json")
    methods = {event["configuration"]: score(event["predictions_pct"], truth, predictions["baselines"])
               for event in predictions["events"]}
    baselines = {name: score(values, truth, {}) for name, values in predictions["baselines"].items()}
    output = {
        "status": "one_prospective_external_case_scored", "source_family": plan["source_family"],
        "sample": plan["sample"], "system": plan["system"], "cycle_count": plan["cycle_count"],
        "source_locator": "Electrochemical performance, paragraph linked to Fig. 2(f); publisher PDF page 5",
        "author_retention_pct": truth, "author_numeric_token": raw, "graph": graph,
        "prediction_lock_commit": lock, "prediction_lock_sha256": sha(OUT/"predictions_locked.json"),
        "reveal_claim_sha256": sha(OUT/"reveal_claim.json"),
        "primary": plan["primary"], "methods": methods, "baselines": baselines,
        "scored_sources": 1, "aggregate_r2": None, "external_sources_accepted": 0,
        "post_reveal_refits": 0, "goal_achieved": False,
    }
    (OUT/"case_result.json").write_bytes((json.dumps(output, ensure_ascii=False, indent=2, allow_nan=False)+"\n").encode())
