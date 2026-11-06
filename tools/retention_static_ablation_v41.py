"""Complete the two missing cells of a frozen GPR static-feature comparison."""

from pathlib import Path
import re
import subprocess
import sys
import warnings

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.prepare_small_sample_routes import now, read, sha, write
from tools.retention_corrected2e_v13 import environment
from tools.retention_horizon_normalization_v19 import gates, get_mae, groups
from tools.retention_sawdust_development_v31 import BASE, OUT as P31, subsets
from tools.retention_sawdust_verify_v31 import exact_score
from tools.retention_shape_v4 import Encoder, estimator, expressed, predicted, weights


OUT = BASE/"第四十一轮_三电极GPR静态项配对_20261106"
P40 = BASE/"第四十轮_柚子籽三电极外部锁定_20261106"
CASES = {
    "raw_early": ("raw", False, None),
    "raw_static": ("raw", True, "GPR_static_p1_raw_delta"),
    "continuation_early": ("continuation", False, "GPR_early_p1_continuation_delta"),
    "continuation_static": ("continuation", True, None),
}
CONTRASTS = {
    "static_on_raw": {"raw_static": 1, "raw_early": -1},
    "static_on_continuation": {"continuation_static": 1, "continuation_early": -1},
    "continuation_without_static": {"continuation_early": 1, "raw_early": -1},
    "continuation_with_static": {"continuation_static": 1, "raw_static": -1},
    "interaction_static_raw_minus_continuation": {
        "raw_static": 1, "raw_early": -1, "continuation_static": -1, "continuation_early": 1,
    },
}


def rows_and_folds():
    rows = read(P31/"input_snapshot.json")["3E"]
    folds = read(P31/"training_plan.json")["cohorts"]["3E"]["folds"]
    assert len(rows) == 33 and len(folds) == 27
    assert set(folds) == {r["source_family"] for r in rows}
    assert all(r["features"]["early_observed_cycle_count"] <= .2*r["features"]["target_cycle_count"] for r in rows)
    assert "doi:10.1039/d0na00778a" not in folds
    for source, split in folds.items():
        assert split["test_ids"] == [r["row_id"] for r in rows if r["source_family"] == source]
        assert split["train_ids"] == [r["row_id"] for r in rows if r["source_family"] != source]
    return rows, folds


def freeze():
    assert not OUT.exists()
    parent = read(P31/"training_plan.json")
    old = {c["id"]: c for c in parent["cohorts"]["3E"]["configurations"]}
    ref = old[CASES["continuation_early"][2]]
    assert parent["environment"] == environment() and ref["kind"] == "GPR" and ref["target"] == "delta"
    arms = {}
    for name, (view, static, existing) in CASES.items():
        config = dict(ref, id=existing or name, family="GPR_static" if static else "GPR_early",
                      feature_view=view, static=static)
        assert existing is None or config == old[existing]
        arms[name] = {"configuration": config, "reuse_p31": existing}
    assert read(P40/"case_result.json")["scored_sources"] == 1
    rows, folds = rows_and_folds()
    guard = [
        Path(__file__), BASE/"research_goal.json", P40/"case_result.json",
        *(P31/file for file in ("training_plan.json", "input_snapshot.json", "heldout_predictions.json",
                               "fit_events.json", "results.json", "independent_verification.json")),
        *(ROOT/"tools"/f"{name}.py" for name in (
            "retention_sawdust_development_v31", "retention_sawdust_verify_v31", "retention_onion_development_v29",
            "retention_shape_v4", "retention_v3_optimizer", "run_small_sample_routes",
            "retention_horizon_normalization_v19", "verify_retention_v3b", "prepare_small_sample_routes",
        )),
    ]
    goal = read(BASE/"research_goal.json")
    OUT.mkdir()
    write(OUT/"training_plan.json", {
        "frozen_at": now(), "system": "3E", "early_fraction": .2,
        "scope": "Fixed P31 3E development cohort, exact whole-source folds. The already-seen pomelo case is excluded. No new external validation.",
        "train_eval_rows": [r["row_id"] for r in rows], "source_families": list(folds),
        "environment": environment(), "arms": arms, "primary_model_retained": "continuation_early",
        "planned_fits": 54, "planned_reused_folds": 54,
        "criteria": goal["criteria"], "baselines": parent["baselines"], "contrasts": CONTRASTS,
        "bootstrap": {"draws": 10000, "seed": 20261106, "interval": [.025, .975], "unit": "source"},
        "treatment_evidence_rule": "Static benefit requires both matched MAE changes with upper paired interval below zero and no increase in p90 absolute error or in pooled <=80% endpoint MAE in either view. A development result cannot satisfy external acceptance.",
        "low_retention_pct_max": 80,
        "interpretation": "An added block under fixed Matérn geometry changes distances and missingness representation. The comparison does not establish the intrinsic value of each feature or its value under retuning.",
        "other_routes": "RF, XGBoost, A, other curve features, 2E and early10 kept in prior results. Do not promote by these development outcomes.",
        "protected": {p.relative_to(ROOT).as_posix(): sha(p) for p in guard},
    })
    write(OUT/"freeze_receipt.json", {"plan_sha256": sha(OUT/"training_plan.json"), "new_fits_at_freeze": 0})


def checked():
    path = OUT/"training_plan.json"
    plan = read(path)
    assert sha(path) == read(OUT/"freeze_receipt.json")["plan_sha256"]
    assert environment() == plan["environment"]
    assert all(sha(ROOT/p) == h for p, h in plan["protected"].items())
    return plan


def run(commit):
    plan = checked()
    assert re.fullmatch(r"[0-9a-f]{40}", commit)
    for path in (Path(__file__), OUT/"training_plan.json", OUT/"freeze_receipt.json"):
        spec = commit+":"+path.relative_to(ROOT).as_posix()
        assert subprocess.check_output(
            ["git", "-c", f"safe.directory={ROOT.as_posix()}", "show", spec], cwd=ROOT,
        ) == path.read_bytes()
    rows, folds = rows_and_folds()
    lookup = {r["row_id"]: r for r in rows}
    assert [r["row_id"] for r in rows] == plan["train_eval_rows"] and list(folds) == plan["source_families"]
    with (OUT/"run_claim.json").open("x", encoding="utf-8") as claim:
        claim.write(commit+"\n")
    events = []
    for source, split in folds.items():
        train, test = subsets(split, lookup)
        w = weights(train)
        delta = np.asarray([r["target"]-r["last_early"] for r in train])
        center = float(np.average(delta, weights=w))
        scale = float(np.sqrt(np.average((delta-center)**2, weights=w))) or 1.
        for arm, design in plan["arms"].items():
            if design["reuse_p31"]:
                continue
            config = design["configuration"]
            event = {"held_source": source, "arm": arm, "test_rows": split["test_ids"], "fit_attempted": False}
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                try:
                    tr = [expressed(r, config, "six") for r in train]
                    te = [expressed(r, config, "six") for r in test]
                    encoder = Encoder().fit(tr)
                    model = estimator(config)
                    model.set_params(alpha=config["parameters"]["alpha"]/(w*len(train)))
                    event["fit_attempted"] = True
                    model.fit(encoder.transform(tr), (delta-center)/scale)
                    result = model.predict(encoder.transform(te))*scale+center+np.asarray([r["last_early"] for r in test])
                    assert len(result) == len(test) and np.isfinite(result).all()
                    event.update(status="complete", predictions=result.tolist(),
                                 encoded_fields=[field["field"] for field in encoder.schema])
                except Exception as error:
                    event.update(status="failed", error=repr(error))
            event["warnings"] = [str(item.message) for item in caught]
            events.append(event)
    assert len(events) == plan["planned_fits"]
    write(OUT/"fit_events.json", events)


def score():
    plan = checked()
    rows, folds = rows_and_folds()
    outcomes = read(OUT/"fit_events.json")
    parent = read(P31/"heldout_predictions.json")["3E"]
    past_events = {(e["held"], e["config"]): e for e in read(P31/"fit_events.json") if e["system"] == "3E"}
    tests = {r["row_id"]: r for r in rows}
    assert not (OUT/"results.json").exists()
    predictions = {}
    for arm, design in plan["arms"].items():
        previous = design["reuse_p31"]
        if previous:
            predictions[arm] = parent["loso"][previous]
            pred_by_id = {r["row_id"]: r["predicted"] for r in predictions[arm]}
            for source, split in folds.items():
                event = past_events[source, previous]
                assert event["status"] == "complete" and event["fit_attempted"]
                assert event["predictions"] == [pred_by_id[key] for key in split["test_ids"]]
        else:
            events = {e["held_source"]: e for e in outcomes if e["arm"] == arm}
            assert set(events) == set(folds)
            assert all(e["test_rows"] == folds[source]["test_ids"] for source, e in events.items())
            predictions[arm] = [predicted("3E", arm, tests[key], value)
                                for e in events.values() if e["status"] == "complete"
                                for key, value in zip(e["test_rows"], e["predictions"])]
    write(OUT/"heldout_predictions.json", predictions)
    complete = all(len(preds) == len(rows) for preds in predictions.values())
    summary = {
        "plan_sha256": sha(OUT/"training_plan.json"), "complete": complete,
        "new_fits": sum(e["fit_attempted"] for e in outcomes), "reused_folds": 54,
        "failures": sum(e["status"] != "complete" for e in outcomes),
        "warnings": sum(len(e["warnings"]) for e in outcomes), "external_sources": 0, "goal_achieved": False,
    }
    if complete:
        expected = {r["row_id"]: (r["target"], r["source_family"]) for r in rows}
        all_predictions = {**predictions, **parent["baselines"]}
        for v in all_predictions.values():
            assert {r["row_id"]: (r["observed"], r["source_family"]) for r in v} == expected
        baselines = {k: exact_score(v) for k, v in parent["baselines"].items()}
        summaries, errors = {}, {}
        for arm, preds in predictions.items():
            values = exact_score(preds)
            low = [r for r in preds if r["observed"] <= plan["low_retention_pct_max"]]
            summaries[arm] = {"metrics": values, "gates": gates(preds, values, baselines, plan["criteria"], len(rows)),
                              "low_retention_mae_pp": get_mae(low), "low_retention_records": low}
            errors[arm] = {s: get_mae(p) for s, p in groups(preds, "source_family").items()}
        bootstrap = plan["bootstrap"]
        rng = np.random.default_rng(bootstrap["seed"])
        draws = rng.integers(len(folds), size=(bootstrap["draws"], len(folds)))
        contrasts = {}
        for key, signed in plan["contrasts"].items():
            changes = np.asarray([sum(k*errors[a][s] for a, k in signed.items()) for s in folds])
            ci = np.quantile(changes[draws].mean(axis=1), bootstrap["interval"])
            contrasts[key] = {"mean_mae_change_pp": float(changes.mean()), "paired_interval_pp": ci.tolist(),
                              "per_source_mae_change_pp": dict(zip(folds, changes.tolist()))}
        supported = all(contrasts[f"static_on_{v}"]["paired_interval_pp"][1] < 0
                        and summaries[f"{v}_static"]["metrics"]["p90_absolute_error"]
                        <= summaries[f"{v}_early"]["metrics"]["p90_absolute_error"]
                        and summaries[f"{v}_static"]["low_retention_mae_pp"]
                        <= summaries[f"{v}_early"]["low_retention_mae_pp"] for v in ("raw", "continuation"))
        summary.update(arms=summaries, baselines=baselines, contrasts=contrasts,
                       static_benefit_rule_met=supported,
                       numeric_passes=sum(all(arm["gates"].values()) for arm in summaries.values()))
    write(OUT/"results.json", summary)


if __name__ == "__main__":
    {"freeze": freeze, "run": run, "score": score}[sys.argv[1]](*sys.argv[2:])
