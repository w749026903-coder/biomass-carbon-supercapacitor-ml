"""Freeze and run one source-excluded PSAC-3 case before allowing endpoint access."""

from itertools import product
import json
from pathlib import Path
import re
import subprocess
import sys
import warnings
from xml.etree import ElementTree as ET

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.prepare_small_sample_routes import now, read, sha, write
from tools.retention_corrected2e_v13 import environment
from tools.retention_shape_v4 import Encoder, SIX, estimator, expressed, weights
from tools.retention_suaeda_case_v16 import BASE, feature_row


P31 = BASE / "第三十一轮_杉木屑双体系开发对照_20261105"
P39 = BASE / "第三十九轮_柚子籽盲态输入核验_20261106"
OUT = BASE / "第四十轮_柚子籽三电极外部锁定_20261106"
XML = ROOT / ".local-literature-cache/P32/PMC9419826_sealed_fulltext.xml"
PDF = XML.with_name("pomelo_publisher_sealed.pdf")
FAMILY = "doi:10.1039/d0na00778a"
PRIMARY = "GPR_early_p1_continuation_delta"
BASELINES = ("training_mean", "early_persistence", "early_linear")
REMOTE = [
    "-c", "http.proxy=http://127.0.0.1:7890", "-c", "https.proxy=http://127.0.0.1:7890",
    "-c", "http.version=HTTP/1.1", "-c", "http.sslBackend=openssl",
]


def git(*args):
    return subprocess.check_output(
        ["git", "-c", f"safe.directory={ROOT.as_posix()}", *args], cwd=ROOT,
    )


def exact_commit(commit, paths):
    assert re.fullmatch(r"[0-9a-f]{40}", commit)
    for path in paths:
        assert git("show", commit + ":" + path.relative_to(ROOT).as_posix()) == path.read_bytes()


def text(node):
    return " ".join("".join(node.itertext()).split())


def static_inputs():
    # Only BET table cells and Boolean checks of protocol wording are extracted.
    root = ET.parse(XML).getroot().find("body")
    method = text(root.find('.//sec[@id="sec7"]/p'))
    assert re.search(r"For the three-electrode system[^.]+Hg/HgO", method)
    electrolyte = r"three-electrode configuration in 1 M KOH solution"
    assert any(electrolyte in text(p) for p in root.findall(".//p"))
    table = root.find('.//table-wrap[@id="tab1"]')
    assert "BET characteristics" in text(table.find("caption"))
    assert "S BET" in text(table.find(".//th[2]"))
    row, = (r for r in table.findall(".//tr") if r.find("td") is not None and text(r.find("td")) == "PSAC-3")
    return {
        "reported_current_A_g": 10, "electrolyte": "KOH", "concentration_mol_L": 1,
        "cycle_voltage_lower_V": None, "cycle_voltage_upper_V": None,
        "BET_m2_g": float(text(row.findall("td")[1])), "reference_electrode": "Hg/HgO",
    }


def scenarios(points):
    centers = tuple((p["cycle_reading"], p["early_ordinate_pct"]) for p in points)
    yield "center", centers
    for y in product((0, 1), repeat=4):
        yield "y:" + "".join(map(str, y)), tuple(
            (x, p["geometry_interval_pct"][j]) for (x, _), p, j in zip(centers, points, y)
        )
    for x in product((0, 1), repeat=4):
        for y in product((0, 1), repeat=4):
            tag = "xy:" + "".join(map(str, x)) + ":" + "".join(map(str, y))
            yield tag, tuple((p["cycle_interval"][i], p["geometry_interval_pct"][j])
                             for p, i, j in zip(points, x, y))


def freeze():
    assert not OUT.exists()
    evidence = read(P39 / "early_input_evidence.json")
    assert evidence["source_family"] == FAMILY and evidence["endpoints_revealed"] == 0
    assert evidence["predictions_locked"] == 0 and evidence["panels"]["3E"]["marker_counts_10_20"] == [0, 4]
    assert sha(XML) == evidence["protected_xml_sha256"] and sha(PDF) == evidence["protected_pdf_sha256"]
    archived = read(P31 / "training_plan.json")
    cohort = archived["cohorts"]["3E"]
    train = read(P31 / "input_snapshot.json")["3E"]
    source_ids = sorted({row["source_family"] for row in train})
    assert len(train) == 33 and len(source_ids) == 27 and FAMILY not in source_ids
    assert all(row["features"]["early_observed_cycle_count"] <= .2 * row["features"]["target_cycle_count"] for row in train)
    assert archived["environment"] == environment() and cohort["primary"] == PRIMARY
    assert len(cohort["configurations"]) == 8 and all(c["target"] == "delta" for c in cohort["configurations"])
    points = evidence["panels"]["3E"]["points"]
    source = evidence["protocols"]["3E"]
    assert (source["sample"], source["reported_A_g"], source["target_cycles"], source["figure_id"]) == ("PSAC-3", 10, 10000, "fig2")
    guard = [
        Path(__file__), BASE/"research_goal.json", P31/"training_plan.json", P31/"input_snapshot.json",
        P39/"screen_plan.json", P39/"early_input_evidence.json", XML, PDF,
        *(ROOT/"tools"/f"{name}.py" for name in (
            "retention_shape_v4", "retention_v3_optimizer", "run_small_sample_routes", "retention_suaeda_case_v16",
            "retention_corrected2e_v13", "prepare_small_sample_routes")),
    ]
    plan = {
        "frozen_at": now(), "source_family": FAMILY, "sample": source["sample"],
        "system": "3E", "cycle_count": 10000, "window": .2, "figure": "Fig. 2(f)",
        "input_points": points, "static_features": static_inputs(),
        "static_provenance": "PSAC-3 Table 1 BET; 3E results for 1 M KOH; methods for Hg/HgO; Fig. 2(f) for A/g. The precise cycling voltage window remains unknown.",
        "environment": environment(), "train_rows": [r["row_id"] for r in train], "train_sources": source_ids,
        "configurations": cohort["configurations"], "primary": PRIMARY, "baselines": BASELINES,
        "planned_fits": 8, "scenario_counts": {"center": 1, "y_only_corners": 16, "xy_corners": 256},
        "stress_rule": "Four original points, center and coordinate-box corners. Report discrete sensitivity only, without probability or a global interval guarantee. Identical frozen test scenarios for all eight methods and three baselines.",
        "criteria": read(BASE/"research_goal.json")["criteria"],
        "single_case_scope": "Per-case errors and sensitivity, no aggregate R2 or independent acceptance. No source exchange with 2E. Early10 and A are out of this case and retained.",
        "endpoint_at_freeze": None,
        "reveal_rule": "Verify plan and prediction bytes on origin/main first. Use the original author retention statement for PSAC-3 tied to Fig. 2(f) and 10000 GCD cycles. Preserve a same-panel graph reading separately if available. A conflict remains explicit. No refits after reveal.",
        "protected": {path.relative_to(ROOT).as_posix(): sha(path) for path in guard},
    }
    OUT.mkdir()
    write(OUT/"training_plan.json", plan)
    write(OUT/"freeze_receipt.json", {"plan_sha256": sha(OUT/"training_plan.json"), "fits_at_freeze": 0, "revealed_endpoints": 0})


def checked():
    path = OUT/"training_plan.json"
    plan = read(path)
    assert sha(path) == read(OUT/"freeze_receipt.json")["plan_sha256"]
    assert all(sha(ROOT/rel) == digest for rel, digest in plan["protected"].items())
    assert environment() == plan["environment"]
    return plan


def test_rows(plan):
    rows = {}
    for tag, coords in scenarios(plan["input_points"]):
        features, count = feature_row([
            {"cycle_reading": x, "cycle_interval": (x, x), "early_ordinate_pct": y}
            for x, y in coords
        ], plan["cycle_count"], plan["window"])
        assert count == 4 and set(features) == set(SIX)
        rows[tag] = {"features": features, "last_early": features["last_early_retention_pct"],
                     "static_features": plan["static_features"]}
    assert len(rows) == sum(plan["scenario_counts"].values())
    return rows


def predict(freeze_commit):
    plan = checked()
    exact_commit(freeze_commit, (Path(__file__), OUT/"training_plan.json", OUT/"freeze_receipt.json"))
    train = read(P31/"input_snapshot.json")["3E"]
    assert [row["row_id"] for row in train] == plan["train_rows"]
    assert sorted({row["source_family"] for row in train}) == plan["train_sources"]
    assert plan["source_family"] not in plan["train_sources"]
    tests = test_rows(plan)
    with (OUT/"run_claim.json").open("x", encoding="utf-8") as claim:
        json.dump({"started_at": now(), "freeze_commit": freeze_commit}, claim)
    w = weights(train)
    mass = w * len(train)
    delta = np.asarray([row["target"]-row["last_early"] for row in train])
    center = float(np.average(delta, weights=w))
    scale = float(np.sqrt(np.average((delta-center)**2, weights=w))) or 1.
    last = np.asarray([row["last_early"] for row in tests.values()])
    events = []
    for config in plan["configurations"]:
        event = {"configuration": config["id"], "fit_attempted": False}
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            try:
                x = [expressed(row, config, "six") for row in train]
                encoder = Encoder().fit(x)
                model = estimator(config)
                kwargs = {"sample_weight": mass}
                if config["kind"] == "GPR":
                    model.set_params(alpha=config["parameters"]["alpha"]/mass)
                    kwargs = {}
                event["fit_attempted"] = True
                model.fit(encoder.transform(x), (delta-center)/scale, **kwargs)
                encoded = encoder.transform([expressed(row, config, "six") for row in tests.values()])
                predictions = model.predict(encoded) * scale + center + last
                assert len(predictions) == len(tests) and np.isfinite(predictions).all()
                event.update(status="complete", predictions_pct=predictions.tolist(), encoder=encoder.schema)
            except Exception as exc:
                event.update(status="failed", error=repr(exc))
        event["warnings"] = [str(item.message) for item in caught]
        events.append(event)
    mean = float(np.average([row["target"] for row in train], weights=w))
    linear = [row["last_early"] + f["early_retention_slope_per_1000_cycles"]
              * (f["target_cycle_count"]-f["early_observed_cycle_count"])/1000.
              for row in tests.values() for f in [row["features"]]]
    write(OUT/"predictions_locked.json", {
        "status": "before_author_endpoint_access", "predicted_at": now(), "freeze_commit": freeze_commit,
        "plan_sha256": sha(OUT/"training_plan.json"), "terminal_label": None,
        "scenario_ids": list(tests), "target_delta_center": center, "target_delta_scale": scale,
        "events": events, "baselines": dict(zip(BASELINES, ([mean]*len(tests), last.tolist(), linear))),
    })


def reveal(lock_commit):
    plan = checked()
    locked, receipt = OUT/"predictions_locked.json", OUT/"pre_reveal_verification.json"
    assert git(*REMOTE, "ls-remote", "--exit-code", "origin", "refs/heads/main").split()[0].decode() == lock_commit
    exact_commit(lock_commit, (locked, receipt, OUT/"training_plan.json"))
    verified = read(receipt)
    assert verified["predictions_sha256"] == sha(locked) and verified["endpoints_revealed"] == 0
    assert verified["fit_failures"] == 0 and read(locked)["terminal_label"] is None
    with (OUT/"reveal_claim.json").open("x", encoding="utf-8") as claim:
        json.dump({"started_at": now(), "verified_remote_lock_commit": lock_commit, "predictions_sha256": sha(locked)}, claim)
    body = ET.parse(XML).getroot().find("body")
    paragraphs = [text(p) for p in body.findall(".//p")
                  if any("fig2" in x.get("rid", "").split() for x in p.findall(".//xref"))
                  and re.search(r"Fig\.\s*2\(?f\)?", text(p), re.I)
                  and re.search(r"10[,\s]?000(?:th)?\s+(?:GCD\s+)?cycles?", text(p), re.I)
                  and plan["sample"] in text(p)]
    para, = paragraphs
    print(para)


if __name__ == "__main__":
    {"freeze": freeze, "predict": predict, "reveal": reveal}[sys.argv[1]](*sys.argv[2:])
