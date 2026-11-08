"""Test the approved early shape terms without changing the P64 scope or targets."""

import argparse
from collections import defaultdict
import json
from pathlib import Path
import subprocess
import sys
import warnings

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.retention_decline_guard_v63 import METRICS
from tools.retention_literature_svr_v65 import BASE, P59, P64, SCOPE, OUT as P65, dataset, mix
from tools.retention_new_evidence_development_v59 import (
    environment, exact_score, expressed, fit, fold_data, gates, now, predicted, read, sha, write,
)
from tools.retention_rollback_regression_v60 import BOOT, paired_error

OUT = BASE / "第六十六轮_温和范围曲线形状对照_20261108"
SHAPES = (
    "first_half_slope_pp", "last_half_slope_pp", "quadratic_curvature_pp",
    "peak_relative_time_fraction",
)
GIT = ["git", "-c", f"safe.directory={ROOT.as_posix()}"]


def shape_rows(rows):
    audit = read(P65 / "shape_readiness.json")
    indexed = {r["row_id"]: r for r in audit["scores"]}
    assert len(indexed) == len(audit["scores"]) == len(rows)
    assert all(sha(ROOT / path) == digest for path, digest in audit["input_files"].items())
    for row in rows:
        evidence = indexed[row["row_id"]]
        shapes = evidence["shapes"]
        assert set(shapes) == set(SHAPES)
        complete = all(value is not None for value in shapes.values())
        assert complete == evidence["all_shapes_available"]
        assert complete or all(value is None for value in shapes.values())
        assert evidence["source_family"] == row["source_family"]
        assert evidence["sample"] == row["sample_name"]
    return indexed


def freeze():
    assert not OUT.exists()
    old, cohort, rows = dataset()
    assert environment() == old["environment"]
    audit = shape_rows(rows)
    eligible = [r["row_id"] for r in rows if audit[r["row_id"]]["all_shapes_available"]]
    assert (len(rows), len(cohort["folds"]), len(eligible)) == (23, 18, 15)
    assert len({audit[r]["source_family"] for r in eligible}) == 13
    files = [
        Path(__file__), BASE / "research_goal.json", P59 / "input_snapshot.json",
        *(P64 / name for name in ("training_plan.json", "predictions.json", "results.json", "applicability.json")),
        P65 / "shape_readiness.json",
    ]
    files.extend(ROOT / "tools" / f"{name}.py" for name in (
        "retention_literature_svr_v65", "retention_new_evidence_development_v59",
        "retention_shape_v4", "retention_v3_optimizer", "run_small_sample_routes",
        "retention_horizon_normalization_v19", "retention_sawdust_verify_v31",
    ))
    OUT.mkdir()
    write(OUT / "training_plan.json", dict(
        frozen_at=now(), parent_git=subprocess.check_output([*GIT, "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        environment=environment(), scope=SCOPE, rows=cohort["included"], folds=cohort["folds"],
        eligible=eligible, shape_features=SHAPES, configurations=old["configurations"],
        planned_fits=len(cohort["folds"]) * len(old["configurations"]),
        shape_ensemble=[.5, .5], guarded_blend_on_complete=[.5, .5],
        guarded_blend_on_missing="exact P64 baseline",
        training_policy="All P64 training rows retained. Four approved shape terms are null when evidence is incomplete; Encoder fits within each training fold.",
        target=old["output"], criteria=old["criteria"],
        selection="RMSE must improve and all matched accuracy metrics must hold or improve. Both variants are exploratory. External acceptance is separate.",
        protected={p.relative_to(ROOT).as_posix(): sha(p) for p in files},
    ))


def checked():
    path = OUT / "training_plan.json"
    rel = path.relative_to(ROOT).as_posix()
    assert subprocess.check_output([*GIT, "show", f"HEAD:{rel}"], cwd=ROOT) == path.read_bytes()
    plan = read(path)
    assert environment() == plan["environment"]
    assert all(sha(ROOT / p) == digest for p, digest in plan["protected"].items())
    _, cohort, rows = dataset()
    assert plan["rows"] == cohort["included"] and plan["folds"] == cohort["folds"]
    audit = shape_rows(rows)
    assert plan["eligible"] == [r["row_id"] for r in rows if audit[r["row_id"]]["all_shapes_available"]]
    return plan, rows, audit


def augment(rows, cfg, audit):
    result = [expressed(row, cfg, "six") for row in rows]
    for row in result:
        fields = audit[row["row_id"]]["shapes"]
        assert set(row["features"]).isdisjoint(fields)
        row["features"].update(fields)
    return result


def run():
    plan, rows, audit = checked()
    with (OUT / "run_claim.json").open("x", encoding="utf-8") as file:
        json.dump(dict(started_at=now(), plan_sha256=sha(OUT / "training_plan.json")), file)
    events = []
    for source, split in plan["folds"].items():
        train, test = fold_data(rows, source, split)
        for cfg in plan["configurations"]:
            event = dict(source=source, model=cfg["id"], attempted=False)
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                try:
                    values = fit(dict(cfg, feature_view="raw"), augment(train, cfg, audit),
                                 augment(test, cfg, audit), event)
                    event.update(status="complete", predictions=[
                        predicted("3E", cfg["id"], r, value) for r, value in zip(test, values, strict=True)
                    ])
                except Exception as exc:
                    event.update(status="failed", error=repr(exc))
            event["warnings"] = [str(w.message) for w in caught]
            events.append(event)
    assert len(events) == plan["planned_fits"]
    write(OUT / "fit_events.json", events)


def strata_score(rows, eligible):
    return {tag: exact_score([r for r in rows if (r["row_id"] in eligible) == complete])
            for tag, complete in (("complete_shapes", True), ("missing_shapes", False))}


def verify():
    plan, _, audit = checked()
    events = read(OUT / "fit_events.json")
    expected = {(s, cfg["id"]) for s in plan["folds"] for cfg in plan["configurations"]}
    assert len(events) == len(expected) == plan["planned_fits"]
    assert {(e["source"], e["model"]) for e in events} == expected
    assert read(OUT / "run_claim.json")["plan_sha256"] == sha(OUT / "training_plan.json")
    prev = read(P64 / "predictions.json")[SCOPE]
    control = prev["methods"]["half_GPR_RF"]
    eligible = set(plan["eligible"])
    assert {r["row_id"] for r in control} == set(plan["rows"])
    reference = exact_score(control)
    baselines = {name: exact_score(rows) for name, rows in prev["baselines"].items()}
    by_model = defaultdict(list)
    for event in events:
        if event["status"] == "complete":
            assert event["attempted"]
            assert [r["row_id"] for r in event["predictions"]] == plan["folds"][event["source"]]["test"]
            assert all(r["source_family"] == event["source"] for r in event["predictions"])
            by_model[event["model"]].extend(event["predictions"])
    results = dict(
        status="same_cohort_exploratory_shape_ablation", control=reference,
        control_strata=strata_score(control, eligible),
        fits=sum(e["attempted"] for e in events), failures=sum(e["status"] != "complete" for e in events),
        warnings=sum(len(e["warnings"]) for e in events), candidates={}, external_sources=0,
        formal_acceptance=False,
    )
    predictions = dict(control=control, components=by_model)
    if not results["failures"]:
        a, b = (by_model[cfg["id"]] for cfg in plan["configurations"])
        expanded = mix(a, b, plan["shape_ensemble"], "shape_equal")
        assert {r["row_id"]: r["observed"] for r in expanded} == {r["row_id"]: r["observed"] for r in control}
        blended = mix(control, expanded, plan["guarded_blend_on_complete"], "guarded_shape")
        guarded = [r if r["row_id"] in eligible else dict(base, model=r["model"])
                   for r, base in zip(blended, control, strict=True)]
        assert all(p["predicted"] == q["predicted"] for p, q in zip(guarded, control, strict=True)
                   if p["row_id"] not in eligible)
        for tag, rows in (("shape_equal", expanded), ("guarded_shape", guarded)):
            score = exact_score(rows)
            delta = {name: score[name] - reference[name] for name in METRICS}
            regressions = [name for name, d in delta.items() if (d < -1e-10 if name == "r2" else d > 1e-10)]
            passed = gates(rows, score, baselines, plan["criteria"], len(control))
            results["candidates"][tag] = dict(
                metrics=score, delta=delta, regressions=regressions, strata=strata_score(rows, eligible),
                paired_mae=paired_error(rows, control, BOOT), gates=passed,
                eligible_challenger=not regressions and delta["rmse"] < -1e-10 and passed["positive"],
            )
            predictions[tag] = rows
    results["largest_control_errors"] = [
        dict(sample=audit[r["row_id"]]["sample"], row_id=r["row_id"], source_family=r["source_family"],
             absolute_error_pp=abs(r["predicted"] - r["observed"]), has_shapes=r["row_id"] in eligible)
        for r in sorted(control, key=lambda r: -abs(r["predicted"] - r["observed"]))[:5]
    ]
    write(OUT / "results.json", results)
    write(OUT / "predictions.json", predictions)
    print(json.dumps({key: [val["metrics"][m] for m in ("r2", "mae", "rmse")]
                      for key, val in results["candidates"].items()}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("step", choices=("freeze", "run", "verify"))
    {"freeze": freeze, "run": run, "verify": verify}[parser.parse_args().step]()
