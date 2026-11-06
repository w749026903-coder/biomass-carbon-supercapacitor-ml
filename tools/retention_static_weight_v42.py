"""Compare fixed low weights for the static block on the unchanged 3E folds."""

from pathlib import Path
import re
import subprocess
import sys
import warnings

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.retention_static_ablation_v41 import (
    BASE, OUT as P41, P31, checked as checked_parent, environment, gates, get_mae,
    now, predicted, read, rows_and_folds, sha, subsets, weights, write,
)
from tools.retention_static_verify_v41 import check_scores
from tools.retention_sawdust_verify_v31 import exact_score
from tools.retention_shape_v4 import Encoder, estimator, expressed


OUT = BASE / "第四十二轮_静态距离低权重_20261106"
VIEWS = ("raw", "continuation")
LOW = {"one_sixteenth": 1/16, "one_quarter": 1/4}
CONTROLS = {"zero": 0., "one": 1.}


def freeze():
    assert not OUT.exists()
    parent = checked_parent()
    rows, folds = rows_and_folds()
    guard = [Path(__file__), ROOT/"tools/retention_static_verify_v41.py",
             *(ROOT/p for p in parent["protected"]),
             *(P41/f for f in ("training_plan.json", "results.json", "heldout_predictions.json", "verification.json"))]
    OUT.mkdir()
    plan = {
        "frozen_at": now(), "system": "3E", "window": .2, "environment": environment(),
        "scope": "The exact P31/P41 33 records and 27 source families. Exploratory whole-source holdout. PSAC-3 is not in the development cohort.",
        "source_families": list(folds), "row_ids": [r["row_id"] for r in rows],
        "views": VIEWS, "squared_static_distance_weights": {"zero": 0., **LOW, "one": 1.},
        "configs": {v: parent["arms"][v+"_static"]["configuration"] for v in VIEWS},
        "columns": "Only the encoded static columns, including their missingness and one-hot indicators, are multiplied by sqrt(weight). All early columns retain unit weight.",
        "reuse": {view: {"zero": view+"_early", "one": view+"_static"} for view in VIEWS},
        "new_fits": 108, "reused_folds": 108, "protected": {p.relative_to(ROOT).as_posix(): sha(p) for p in guard},
        "criteria": parent["criteria"], "low_retention_pct_max": parent["low_retention_pct_max"],
        "bootstrap": parent["bootstrap"],
        "contrast_rule": "For each view and each low weight, compare with both endpoints using common paired source bootstrap draws. All contrasts reported; no promotion based on outer data.",
        "further_validation_rule": "A low weight warrants prospective follow-up on model performance if both views have upper MAE delta interval below zero against both endpoints, with neither p90 absolute nor pooled <=80% MAE higher than the corresponding zero-weight control. All formal acceptance gates remain.",
        "retained_primary": "continuation_zero", "other_routes": parent["other_routes"],
    }
    write(OUT/"training_plan.json", plan)
    write(OUT/"freeze_receipt.json", {"plan_sha256": sha(OUT/"training_plan.json"), "fits_at_freeze": 0})


def checked():
    path = OUT/"training_plan.json"
    plan = read(path)
    assert read(OUT/"freeze_receipt.json")["plan_sha256"] == sha(path)
    assert environment() == plan["environment"]
    assert all(sha(ROOT/p) == h for p, h in plan["protected"].items())
    return plan


def design(train, test, config):
    rows = train+test
    full = [expressed(r, config, "six") for r in rows]
    early = [expressed(r, dict(config, static=False), "six") for r in rows]
    encoder = Encoder().fit(full[:len(train)])
    early_encoder = Encoder().fit(early[:len(train)])
    encoded = encoder.transform(full)
    early_fields = {field["field"] for field in early_encoder.schema}
    early_columns = []
    offset = 0
    for field in encoder.schema:
        width = len(field["vocab"])+1 if field["kind"] == "categorical" else 2
        if field["field"] in early_fields:
            early_columns.extend(range(offset, offset+width))
        offset += width
    assert offset == encoded.shape[1]
    static_columns = sorted(set(range(offset))-set(early_columns))
    assert static_columns and np.array_equal(encoded[:, early_columns], early_encoder.transform(early))
    return encoded, static_columns


def run(commit):
    plan = checked()
    assert re.fullmatch(r"[0-9a-f]{40}", commit)
    for path in (Path(__file__), OUT/"training_plan.json", OUT/"freeze_receipt.json"):
        spec = commit+":"+path.relative_to(ROOT).as_posix()
        assert subprocess.check_output(["git", "-c", f"safe.directory={ROOT.as_posix()}", "show", spec],
                                       cwd=ROOT) == path.read_bytes()
    rows, folds = rows_and_folds()
    assert plan["row_ids"] == [r["row_id"] for r in rows] and plan["source_families"] == list(folds)
    lookup = {r["row_id"]: r for r in rows}
    with (OUT/"run_claim.json").open("x", encoding="utf-8") as claim:
        claim.write(commit+"\n")
    events = []
    for source, fold in folds.items():
        train, test = subsets(fold, lookup)
        w = weights(train)
        delta = np.array([row["target"]-row["last_early"] for row in train])
        center = float(np.dot(w, delta))
        scale = float(np.sqrt(np.dot(w, (delta-center)**2))) or 1.
        for view, config in plan["configs"].items():
            encoded, static_columns = design(train, test, config)
            for name in LOW:
                weight = plan["squared_static_distance_weights"][name]
                event = {"source": source, "view": view, "weight": name, "test_ids": fold["test_ids"],
                         "fit_attempted": False, "static_columns": len(static_columns)}
                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter("always")
                    try:
                        x = encoded.copy()
                        x[:, static_columns] *= np.sqrt(weight)
                        model = estimator(config)
                        model.set_params(alpha=config["parameters"]["alpha"]/(w*len(train)))
                        event["fit_attempted"] = True
                        model.fit(x[:len(train)], (delta-center)/scale)
                        response = model.predict(x[len(train):])*scale+center+np.array([r["last_early"] for r in test])
                        assert len(response) == len(test) and np.isfinite(response).all()
                        event.update(status="complete", predictions=response.tolist())
                    except Exception as error:
                        event.update(status="failed", error=repr(error))
                event["warnings"] = [str(item.message) for item in caught]
                events.append(event)
    assert len(events) == plan["new_fits"]
    write(OUT/"fit_events.json", events)


def score():
    plan = checked()
    rows, folds = rows_and_folds()
    by_id = {r["row_id"]: r for r in rows}
    events = read(OUT/"fit_events.json")
    assert len(events) == len({(e["source"], e["view"], e["weight"]) for e in events}) == plan["new_fits"]
    old = read(P41/"heldout_predictions.json")
    baseline_rows = read(P31/"heldout_predictions.json")["3E"]["baselines"]
    baselines = {name: exact_score(v) for name, v in baseline_rows.items()}
    output, predictions = {}, {}
    failures = sum(e["status"] != "complete" for e in events)
    for view in plan["views"]:
        for label in plan["squared_static_distance_weights"]:
            arm = f"{view}_{label}"
            reused = plan["reuse"][view].get(label)
            if reused:
                predictions[arm] = old[reused]
                continue
            fit = [e for e in events if (e["view"], e["weight"]) == (view, label)]
            assert {e["source"] for e in fit} == set(folds)
            assert all(e["test_ids"] == folds[e["source"]]["test_ids"] for e in fit)
            predictions[arm] = [predicted("3E", arm, by_id[key], val)
                                for e in fit if e["status"] == "complete"
                                for key, val in zip(e["test_ids"], e["predictions"])]
    write(OUT/"heldout_predictions.json", predictions)
    output.update(plan_sha256=sha(OUT/"training_plan.json"), new_fits=sum(e["fit_attempted"] for e in events),
                  reused_folds=plan["reused_folds"], failures=failures, warnings=sum(len(e["warnings"]) for e in events),
                  external_sources=0, goal_achieved=False, baselines=baselines)
    if not failures:
        evaluated, source_errors = {}, {}
        expected = {r["row_id"]: (r["target"], r["source_family"]) for r in rows}
        for name, preds in predictions.items():
            assert len(preds) == len(expected)
            assert {r["row_id"]: (r["observed"], r["source_family"]) for r in preds} == expected
            values = exact_score(preds)
            source_errors[name] = check_scores(preds, values)
            low = [r for r in preds if r["observed"] <= plan["low_retention_pct_max"]]
            evaluated[name] = {"metrics": values, "gates": gates(preds, values, baselines, plan["criteria"], len(rows)),
                               "low_retention_mae_pp": get_mae(low), "low_records": low}
        boot = plan["bootstrap"]
        draws = np.random.default_rng(boot["seed"]).integers(len(folds), size=(boot["draws"], len(folds)))
        contrasts = {}
        for view in plan["views"]:
            for candidate in LOW:
                arm = f"{view}_{candidate}"
                for ref in CONTROLS:
                    other = f"{view}_{ref}"
                    changes = np.array([source_errors[arm][s]-source_errors[other][s] for s in folds])
                    interval = np.quantile(changes[draws].mean(axis=1), boot["interval"])
                    contrasts[f"{arm}_vs_{other}"] = {
                        "mae_change_pp": float(changes.mean()), "source_paired_interval_pp": interval.tolist(),
                        "per_source_change_pp": dict(zip(folds, changes.tolist())),
                    }
        supported = []
        for candidate in LOW:
            if all(
                contrasts[f"{v}_{candidate}_vs_{v}_{ref}"]["source_paired_interval_pp"][1] < 0
                and evaluated[f"{v}_{candidate}"]["low_retention_mae_pp"] <= evaluated[f"{v}_zero"]["low_retention_mae_pp"]
                and evaluated[f"{v}_{candidate}"]["metrics"]["p90_absolute_error"] <= evaluated[f"{v}_zero"]["metrics"]["p90_absolute_error"]
                for v in VIEWS for ref in CONTROLS
            ):
                supported.append(candidate)
        output.update(arms=evaluated, contrasts=contrasts, low_weights_meeting_followup_rule=supported,
                      numeric_passes=sum(all(v["gates"].values()) for v in evaluated.values()))
    write(OUT/"results.json", output)


if __name__ == "__main__":
    {"freeze": freeze, "run": run, "score": score}[sys.argv[1]](*sys.argv[2:])
