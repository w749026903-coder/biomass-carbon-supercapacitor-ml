"""Verify the frozen comparisons and diagnose the fixed kernel without refitting it."""

from collections import Counter, defaultdict
from fractions import Fraction
from math import exp, isclose, sqrt
from pathlib import Path
from statistics import median
import subprocess
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.retention_static_ablation_v41 import OUT, P31, checked, read, rows_and_folds, sha, write
from tools.retention_shape_v4 import Encoder, expressed


def source_weights(rows):
    by_source = defaultdict(Counter)
    for row in rows:
        by_source[row["source_family"]][row["curve_id"]] += 1
    return [Fraction(1, len(by_source) * len(by_source[row["source_family"]])
                     * by_source[row["source_family"]][row["curve_id"]]) for row in rows]


def check_scores(rows, values):
    weights = source_weights(rows)
    assert sum(weights) == 1
    errors = [abs(r["predicted"]-r["observed"]) for r in rows]
    mean = sum(w*r["observed"] for w, r in zip(weights, rows))
    var = sum(w*(r["observed"]-mean)**2 for w, r in zip(weights, rows))
    mse = sum(w*e**2 for w, e in zip(weights, errors))
    ape = [e/r["observed"]*100 for r, e in zip(rows, errors)]
    observed = {"mae": sum(w*e for w, e in zip(weights, errors)), "rmse": sqrt(mse),
                "r2": 1-mse/var, "mape_pct": sum(w*e for w, e in zip(weights, ape))}
    for kind, series in (("p90_absolute_error", errors), ("p90_ape_pct", ape)):
        cumulative = Fraction()
        for error, weight in sorted(zip(series, weights)):
            cumulative += weight
            if cumulative >= Fraction(9, 10):
                observed[kind] = error
                break
    sources = defaultdict(list)
    for r, w, e in zip(rows, weights, errors):
        sources[r["source_family"]].append((w, e))
    means = {s: sum(w*e for w, e in v)/sum(w for w, _ in v) for s, v in sources.items()}
    observed["source_p90_mae"] = float(np.quantile(list(means.values()), .9))
    assert set(observed) == set(values)
    assert all(isclose(v, values[k], rel_tol=1e-11, abs_tol=1e-11) for k, v in observed.items())
    return means


def kernel_diagnostic(plan, rows, folds):
    lookup = {row["row_id"]: row for row in rows}
    pairs = {}
    for view in ("raw", "continuation"):
        records = []
        for source, split in folds.items():
            train, test = ([lookup[key] for key in split[subset]] for subset in ("train_ids", "test_ids"))
            spaces = {}
            for option in ("early", "static"):
                config = plan["arms"][f"{view}_{option}"]["configuration"]
                enc = Encoder().fit([expressed(r, config, "six") for r in train])
                combined = enc.transform([expressed(r, config, "six") for r in train+test])
                fields = {}
                offset = 0
                for field in enc.schema:
                    width = len(field["vocab"])+1 if field["kind"] == "categorical" else 2
                    fields[field["field"]] = combined[:, offset:offset+width]
                    offset += width
                assert offset == combined.shape[1]
                distance = np.linalg.norm(combined[len(train):, None, :]-combined[None, :len(train), :], axis=2).min(axis=1)
                assert config["parameters"]["nu"] == 1.5
                z = sqrt(3)*distance/config["parameters"]["length_scale"]
                spaces[option] = (fields, [float((1+t)*exp(-t)) for t in z])
            early, early_k = spaces["early"]
            static, static_k = spaces["static"]
            assert early.keys() < static.keys()
            assert all(np.array_equal(x, static[key]) for key, x in early.items())
            for row, a, b in zip(test, early_k, static_k):
                assert 0 <= b <= a+1e-15 <= 1+1e-15
                records.append({"row_id": row["row_id"], "source_family": source, "author_retention_pct": row["target"],
                                "nearest_kernel_early": a, "nearest_kernel_static": b})
        assert len(records) == 33
        pairs[view] = {
            "median_nearest_kernel_early": median(r["nearest_kernel_early"] for r in records),
            "median_nearest_kernel_static": median(r["nearest_kernel_static"] for r in records),
            "rows_with_decrease": sum(r["nearest_kernel_static"] < r["nearest_kernel_early"] for r in records),
            "records": records,
        }
    return pairs


def main():
    plan = checked()
    rows, folds = rows_and_folds()
    results = read(OUT/"results.json")
    predictions = read(OUT/"heldout_predictions.json")
    events = read(OUT/"fit_events.json")
    previous = read(P31/"heldout_predictions.json")["3E"]
    commit = (OUT/"run_claim.json").read_text(encoding="utf-8").strip()
    path = OUT/"training_plan.json"
    assert subprocess.check_output(["git", "-c", f"safe.directory={ROOT.as_posix()}", "show",
                                   commit+":"+path.relative_to(ROOT).as_posix()], cwd=ROOT) == path.read_bytes()
    assert results["complete"] and results["new_fits"] == len(events) == 54
    assert results["failures"] == results["warnings"] == results["numeric_passes"] == results["external_sources"] == 0
    assert results["reused_folds"] == 54 and results["goal_achieved"] is False
    assert all(e["fit_attempted"] and e["status"] == "complete" and not e["warnings"] for e in events)
    assert {(e["held_source"], e["arm"]) for e in events} == {(s, a) for s in folds for a in plan["arms"] if not plan["arms"][a]["reuse_p31"]}
    error_means = {}
    for name, pred in predictions.items():
        assert len(pred) == len({r["row_id"] for r in pred}) == 33
        original = plan["arms"][name]["reuse_p31"]
        if original:
            assert pred == previous["loso"][original]
        error_means[name] = check_scores(pred, results["arms"][name]["metrics"])
        assert all(r["predicted"] > 0 for r in pred)
        assert results["arms"][name]["gates"]["coverage"]
    for name, pred in previous["baselines"].items():
        check_scores(pred, results["baselines"][name])
    boot = plan["bootstrap"]
    draws = np.random.default_rng(boot["seed"]).integers(len(folds), size=(boot["draws"], len(folds)))
    for name, recipe in plan["contrasts"].items():
        s = results["contrasts"][name]
        changes = np.array([sum(v*error_means[k][source] for k, v in recipe.items()) for source in folds])
        assert np.allclose(changes, list(s["per_source_mae_change_pp"].values()), atol=1e-11)
        assert isclose(changes.mean(), s["mean_mae_change_pp"], abs_tol=1e-11)
        assert np.allclose(np.quantile(changes[draws].mean(axis=1), boot["interval"]), s["paired_interval_pp"], atol=1e-11)
    assert not results["static_benefit_rule_met"]
    write(OUT/"verification.json", {
        "status": "passed", "freeze_commit": commit, "results_sha256": sha(OUT/"results.json"),
        "paired_contrasts_verified": 5, "source_contrasts_verified": 135,
        "aggregate_metrics_verified": 49, "new_fit_records_verified": 54, "old_folds_exactly_reused": 54,
        "kernel_scope": "Post-result descriptive audit. Train-fold preprocessing only. No estimator fitted. "
                        "Nearest Matérn similarity is a support diagnostic; it does not attribute each error.",
        "kernel_support": kernel_diagnostic(plan, rows, folds),
    })


if __name__ == "__main__":
    main()
