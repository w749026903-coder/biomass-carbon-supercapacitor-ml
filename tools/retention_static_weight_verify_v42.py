"""Verify archived controls and low-weight comparisons without refitting the GPR."""

from math import isclose, sqrt
from pathlib import Path
from statistics import median
import subprocess
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.retention_static_weight_v42 import OUT, P41, VIEWS, checked, design, read, rows_and_folds, sha, write
from tools.retention_static_verify_v41 import check_scores, source_weights


def nearest_support(plan, rows, folds):
    lookup = {row["row_id"]: row for row in rows}
    report = {}
    for view in VIEWS:
        strengths = {k: [] for k in plan["squared_static_distance_weights"]}
        config = plan["configs"][view]
        for fold in folds.values():
            train, test = ([lookup[key] for key in fold[side]] for side in ("train_ids", "test_ids"))
            x, stat = design(train, test, config)
            delta = x[len(train):, None, :] - x[None, :len(train), :]
            early = sorted(set(range(x.shape[1]))-set(stat))
            early_dist = np.square(delta[:, :, early]).sum(axis=2)
            static_dist = np.square(delta[:, :, stat]).sum(axis=2)
            previous = None
            for name, weight in plan["squared_static_distance_weights"].items():
                d = (early_dist+weight*static_dist).min(axis=1)
                z = np.sqrt(3*d)/config["parameters"]["length_scale"]
                support = (1+z)*np.exp(-z)
                if previous is not None:
                    assert (support <= previous+1e-15).all()
                previous = support
                strengths[name].extend(support.tolist())
        assert all(len(s) == 33 for s in strengths.values())
        report[view] = {k: median(v) for k, v in strengths.items()}
    return report


def main():
    plan = checked()
    rows, folds = rows_and_folds()
    fits = read(OUT/"fit_events.json")
    predictions = read(OUT/"heldout_predictions.json")
    archived = read(P41/"heldout_predictions.json")
    results = read(OUT/"results.json")
    commit = (OUT/"run_claim.json").read_text(encoding="utf-8").strip()
    path = OUT/"training_plan.json"
    assert subprocess.check_output(["git", "-c", f"safe.directory={ROOT.as_posix()}", "show",
                                   commit+":"+path.relative_to(ROOT).as_posix()], cwd=ROOT) == path.read_bytes()
    assert results["new_fits"] == results["reused_folds"] == len(fits) == 108
    assert results["failures"] == results["warnings"] == results["numeric_passes"] == results["external_sources"] == 0
    assert not results["goal_achieved"] and not results["low_weights_meeting_followup_rule"]
    assert results["plan_sha256"] == sha(path)
    assert len(predictions) == 8
    for event in fits:
        assert event["status"] == "complete" and event["fit_attempted"] and not event["warnings"]
        assert event["test_ids"] == folds[event["source"]]["test_ids"]
        arm = f'{event["view"]}_{event["weight"]}'
        held = [r["predicted"] for r in predictions[arm] if r["source_family"] == event["source"]]
        assert held == event["predictions"]
    errors = {}
    for arm, preds in predictions.items():
        assert len(preds) == len({r["row_id"] for r in preds}) == len(rows)
        view, level = arm.split("_", 1)
        reused = plan["reuse"][view].get(level)
        if reused:
            assert preds == archived[reused]
        low = [r for r in preds if r["observed"] <= plan["low_retention_pct_max"]]
        assert len(low) == 4 and low == results["arms"][arm]["low_records"]
        mae = sum(w*abs(r["predicted"]-r["observed"]) for w, r in zip(source_weights(low), low))
        assert isclose(mae, results["arms"][arm]["low_retention_mae_pp"], abs_tol=1e-11)
        errors[arm] = check_scores(preds, results["arms"][arm]["metrics"])
        assert all(r["predicted"] > 0 for r in preds)
        assert results["arms"][arm]["gates"]["r2"] is False
    bootstrap = plan["bootstrap"]
    draws = np.random.default_rng(bootstrap["seed"]).integers(len(folds), size=(bootstrap["draws"], len(folds)))
    assert len(results["contrasts"]) == 8
    for key, contrast in results["contrasts"].items():
        arm, control = key.split("_vs_")
        d = np.asarray([errors[arm][s]-errors[control][s] for s in folds])
        assert np.allclose(d, list(contrast["per_source_change_pp"].values()), atol=1e-11)
        assert isclose(d.mean(), contrast["mae_change_pp"], abs_tol=1e-11)
        assert np.allclose(np.quantile(d[draws].mean(axis=1), bootstrap["interval"]),
                           contrast["source_paired_interval_pp"], atol=1e-11)
    report = nearest_support(plan, rows, folds)
    parent = read(P41/"verification.json")["kernel_support"]
    for view in VIEWS:
        assert isclose(report[view]["zero"], parent[view]["median_nearest_kernel_early"], abs_tol=1e-11)
        assert isclose(report[view]["one"], parent[view]["median_nearest_kernel_static"], abs_tol=1e-11)
    assert sqrt(plan["squared_static_distance_weights"]["one_sixteenth"]) == .25
    write(OUT/"verification.json", {
        "status": "passed", "freeze_commit": commit, "results_sha256": sha(OUT/"results.json"),
        "verified_fit_events": 108, "verified_reused_folds": 108, "aggregate_metrics_verified": 56,
        "paired_contrasts_verified": 8, "source_contrasts_verified": 216, "difficult_predictions_checked": 32,
        "median_nearest_kernel": report,
        "diagnostic_scope": "Descriptive diagnostic on frozen development folds. Encoders use training rows only. No new GPR fitting.",
    })


if __name__ == "__main__":
    main()
