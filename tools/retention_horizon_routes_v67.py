"""Compare additional observed targets and horizon-specific training on frozen endpoints."""

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import warnings

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.retention_decline_guard_v63 import METRICS
from tools.retention_literature_svr_v65 import BASE, P59, P64, SCOPE, dataset, mix
from tools.retention_mild_scope_v64 import baselines, outside_reasons
from tools.retention_new_evidence_development_v59 import (
    environment, exact_score, expressed, fit, fold_data, gates, now, predicted, read, sha, weights, write,
)
from tools.retention_rollback_regression_v60 import BOOT, paired_error
from tools.retention_shape_v4 import Encoder, estimator
from tools.retention_shape_mild_scope_v66 import GIT

OUT = BASE / "第六十七轮_中间圈数与万圈限域_20261111"
POINTER = ROOT / "data/current_retention_research.json"
HORIZON = 10_000
MID_LIMITS = (.4, .6)
MID_SHARE = .25
ROUTES = ("midpoint", "10000_only", "10000_weighted")


def verified_points(connection, row):
    records = connection.execute(
        "SELECT raw_json FROM curve_points WHERE curve_id=? ORDER BY cycle_coordinate,marker_index",
        (row["curve_id"],),
    )
    return [json.loads(value) for (value,) in records]


def midpoint_rows(rows, scope, database):
    additions = {}
    assert len({row["curve_id"] for row in rows}) == len(rows)
    with sqlite3.connect(database.as_uri() + "?mode=ro&immutable=1", uri=True) as connection:
        for row in rows:
            points = verified_points(connection, row)
            horizon = row["features"]["target_cycle_count"]
            candidates = [
                p for p in points if p["cycle_lower"] >= max(1000, horizon * MID_LIMITS[0])
                and p["cycle_upper"] <= horizon * MID_LIMITS[1]
            ]
            for p in sorted(candidates, key=lambda p: abs(p["cycle_coordinate"] - horizon / 2)):
                early = [q for q in points if 0 < q["cycle_coordinate"]
                         and q["cycle_upper"] <= .2 * p["cycle_lower"]]
                if len(early) < 3:
                    continue
                x = np.array([q["cycle_coordinate"] for q in early])
                y = np.array([q["retention_pct"] for q in early])
                assert len(set(x)) == len(x)
                features = dict(
                    last_early_retention_pct=float(y[-1]), early_mean_retention_pct=float(np.mean(y)),
                    early_retention_range_pp=float(np.ptp(y)),
                    early_retention_slope_per_1000_cycles=float(np.polyfit(x / 1000, y, 1)[0]),
                    early_observed_cycle_count=float(x[-1]), target_cycle_count=p["cycle_coordinate"],
                )
                new = dict(row, row_id=row["row_id"] + "::observed_midpoint", features=features,
                           target=p["retention_pct"], last_early=float(y[-1]))
                if not outside_reasons(new, scope):
                    additions[row["row_id"]] = dict(row=new, target_point=p, early_points=early)
                    break
    return additions


def freeze():
    assert not OUT.exists()
    old, cohort, rows = dataset()
    assert old["environment"] == environment()
    pointer = read(POINTER)
    database = ROOT / pointer["database"]
    assert sha(database) == pointer["sha256"]
    additions = midpoint_rows(rows, cohort["rules"], database)
    long_rows = [r for r in rows if r["features"]["target_cycle_count"] == HORIZON]
    long_ids = {r["row_id"] for r in long_rows}
    long_folds = {
        source: {key: [row_id for row_id in ids if row_id in long_ids] for key, ids in fold.items()}
        for source, fold in cohort["folds"].items() if long_ids.intersection(fold["test"])
    }
    assert (len(rows), len(cohort["folds"]), len(long_rows), len(long_folds)) == (23, 18, 14, 11)
    assert additions
    protected = [
        Path(__file__), POINTER, database, P59 / "input_snapshot.json",
        *(P64 / name for name in ("training_plan.json", "predictions.json", "results.json")),
    ]
    protected.extend(ROOT / "tools" / f"{name}.py" for name in (
        "retention_new_evidence_development_v59", "retention_mild_scope_v64", "retention_literature_svr_v65",
        "retention_shape_v4", "retention_v3_optimizer", "run_small_sample_routes",
        "retention_horizon_normalization_v19", "retention_sawdust_verify_v31",
    ))
    OUT.mkdir()
    write(OUT / "midpoint_evidence.json", additions)
    protected.append(OUT / "midpoint_evidence.json")
    write(OUT / "training_plan.json", dict(
        frozen_at=now(), parent_git=subprocess.check_output([*GIT, "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        environment=environment(), rows=cohort["included"], folds=cohort["folds"],
        long_rows=[r["row_id"] for r in long_rows], long_folds=long_folds,
        routes=ROUTES, configurations=old["configurations"], criteria=old["criteria"],
        midpoint_limits=MID_LIMITS, midpoint_share=MID_SHARE, long_horizon=HORIZON,
        planned_fits=2 * (len(cohort["folds"]) + 2 * len(long_folds)),
        target=old["output"], blend_original_weight=.5,
        midpoint_policy="One independently observed marker per curve. Use only in training folds. Original and midpoint share original curve weight 75:25; preserve total original effective mass and fit encoder on original training records.",
        long_policy="10,000-only restricts training to target-matched records. 10,000-weighted preserves the cohort and weights each original curve by target cycles divided by 10,000, renormalizing total mass. Score both against frozen P64 on the same 14 records.",
        decision="Rank by matched MAE among candidates with no regression in any key point metric and no increase in worst signed overprediction. For full cohort require no MAE increase on the fixed 10,000-cycle subset. Compare cohorts only to their matched controls. All results are development evidence.",
        protected={p.relative_to(ROOT).as_posix():sha(p) for p in protected},
    ))


def checked():
    file = OUT / "training_plan.json"
    rel = file.relative_to(ROOT).as_posix()
    assert subprocess.check_output([*GIT, "show", f"HEAD:{rel}"], cwd=ROOT) == file.read_bytes()
    plan = read(file)
    assert environment() == plan["environment"]
    assert all(sha(ROOT / p) == digest for p, digest in plan["protected"].items())
    _, cohort, rows = dataset()
    assert plan["rows"] == cohort["included"] and plan["folds"] == cohort["folds"]
    return plan, rows, read(OUT / "midpoint_evidence.json")


def fit_weighted(cfg, original, additional, test, original_weights, additional_weights, event):
    tr, te = ([expressed(row,cfg,"six") for row in values] for values in (original,test))
    encoder = Encoder().fit(tr)
    tr.extend(expressed(row,cfg,"six") for row in additional)
    x, xt = encoder.transform(tr), encoder.transform(te)
    w = np.concatenate([original_weights, additional_weights])
    assert np.all(w > 0) and np.isclose(w.sum(), 1.)
    target_delta = np.array([r["target"] - r["last_early"] for r in original + additional])
    center = float(np.average(target_delta, weights=w))
    scale = float(np.sqrt(np.average((target_delta - center)**2, weights=w))) or 1.
    model = estimator(cfg)
    mass = w * len(original)
    kwargs = {"sample_weight": mass}
    if cfg["kind"] == "GPR":
        model.set_params(alpha=cfg["parameters"]["alpha"] / mass)
        kwargs = {}
    event["attempted"] = True
    model.fit(x, (target_delta - center) / scale, **kwargs)
    result = model.predict(xt) * scale + center + np.array([r["last_early"] for r in test])
    assert result.shape == (len(test),) and np.isfinite(result).all()
    return result


def run():
    plan, rows, midpoint = checked()
    long_rows = [r for r in rows if r["row_id"] in plan["long_rows"]]
    with (OUT / "run_claim.json").open("x", encoding="utf-8") as file:
        json.dump(dict(started_at=now(), plan_sha256=sha(OUT / "training_plan.json")), file)
    events = []
    for route in plan["routes"]:
        folds = plan["folds"] if route == "midpoint" else plan["long_folds"]
        for source, split in folds.items():
            if route == "10000_only":
                train, test = fold_data(long_rows, source, split)
            else:
                train, test = fold_data(rows, source, plan["folds"][source])
                test = [r for r in test if r["row_id"] in split["test"]]
            extra, extra_weights = [], []
            w = weights(train)
            if route == "midpoint":
                for i, row in enumerate(train):
                    item = midpoint.get(row["row_id"])
                    if item:
                        extra.append(item["row"])
                        part = w[i] * plan["midpoint_share"]
                        w[i] -= part
                        extra_weights.append(part)
            elif route == "10000_weighted":
                w *= np.array([r["features"]["target_cycle_count"] for r in train]) / plan["long_horizon"]
                w /= w.sum()
            assert not {r["source_family"] for r in train + extra}.intersection({source})
            assert not {r["curve_id"] for r in train + extra}.intersection(r["curve_id"] for r in test)
            for cfg in plan["configurations"]:
                event = dict(route=route, source=source, model=cfg["id"], attempted=False,
                             train=[r["row_id"] for r in train], extra=[r["row_id"] for r in extra])
                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter("always")
                    try:
                        if route == "10000_only":
                            values = fit(cfg, train, test, event)
                        else:
                            values = fit_weighted(cfg, train, extra, test, w, extra_weights, event)
                        event.update(status="complete", predictions=[
                            predicted("3E", cfg["id"], row, value) for row, value in zip(test,values,strict=True)
                        ])
                    except Exception as exc:
                        event.update(status="failed", error=repr(exc))
                event["warnings"] = [str(w.message) for w in caught]
                events.append(event)
    assert len(events) == plan["planned_fits"]
    write(OUT / "fit_events.json", events)


def worst_overprediction(rows):
    row = max(rows, key=lambda r:r["predicted"] - r["observed"])
    return dict(row_id=row["row_id"], sample=row["sample_name"], pp=row["predicted"] - row["observed"])


def verify():
    plan, pool, midpoint = checked()
    events = read(OUT / "fit_events.json")
    assert read(OUT / "run_claim.json")["plan_sha256"] == sha(OUT / "training_plan.json")
    expected = {(route, source, cfg["id"]) for route in plan["routes"] for source in
                (plan["folds"] if route == "midpoint" else plan["long_folds"]) for cfg in plan["configurations"]}
    assert len(events) == len(expected) and {(e["route"],e["source"],e["model"]) for e in events} == expected
    archive = read(P64 / "predictions.json")[SCOPE]
    control = archive["methods"]["half_GPR_RF"]
    long_ids = set(plan["long_rows"])
    long_only = lambda rows: [r for r in rows if r["row_id"] in long_ids]
    long_control = long_only(control)
    base_full = {key:exact_score(rows) for key,rows in archive["baselines"].items()}
    base_long = {key:exact_score(rows) for key,rows in baselines(long_only(pool),plan["long_folds"]).items()}
    by = defaultdict(list)
    for event in events:
        source, route = event["source"], event["route"]
        train = plan["long_folds"] if route == "10000_only" else plan["folds"]
        test = plan["folds"] if route == "midpoint" else plan["long_folds"]
        assert event["train"] == train[source]["train"]
        assert event["extra"] == ([row_id + "::observed_midpoint" for row_id in event["train"]
                                   if row_id in midpoint] if route == "midpoint" else [])
        if event["status"] == "complete":
            assert [r["row_id"] for r in event["predictions"]] == test[source]["test"]
            assert all(r["source_family"] == source for r in event["predictions"])
            by[(route,event["model"])].extend(event["predictions"])
    predictions = {"control":control, "control_10000":long_control}
    results = {}
    for route in plan["routes"]:
        ref = control if route == "midpoint" else long_control
        a, b = (by[(route,cfg["id"])] for cfg in plan["configurations"])
        if len(a) != len(ref) or len(b) != len(ref):
            continue
        combo = mix(a,b,[.5,.5],route)
        share = plan["blend_original_weight"]
        blend = mix(ref,combo,[share,1-share],route + "_blend")
        for name, values in ((route,combo),(route+"_blend",blend)):
            assert {r["row_id"]:r["observed"] for r in values} == {r["row_id"]:r["observed"] for r in ref}
            metrics, old_metrics = exact_score(values), exact_score(ref)
            failures = [key for key in METRICS if
                        (metrics[key] < old_metrics[key]-1e-10 if key=="r2" else metrics[key] > old_metrics[key]+1e-10)]
            worst = worst_overprediction(values)
            if worst["pp"] > worst_overprediction(ref)["pp"] + 1e-10:
                failures.append("worst_overprediction")
            long_metrics = exact_score(long_only(values))
            if long_metrics["mae"] > exact_score(long_control)["mae"] + 1e-10:
                failures.append("10000_mae")
            checks = gates(values,metrics,base_full if route=="midpoint" else base_long,plan["criteria"],len(ref))
            results[name] = dict(scope_rows=len(ref), metrics=metrics, metrics_10000=long_metrics,
                                 worst_overprediction=worst, regression=failures,
                                 paired_mae=paired_error(values,ref,BOOT), gates=checks,
                                 eligible=not failures and metrics["mae"] < old_metrics["mae"]-1e-10)
            predictions[name] = values
    write(OUT / "predictions.json", predictions)
    write(OUT / "results.json", dict(
        fits=sum(e["attempted"] for e in events), failures=sum(e["status"]!="complete" for e in events),
        warnings=sum(len(e["warnings"]) for e in events),
        midpoint_rows=len(midpoint), midpoint_sources=len(Counter(item["row"]["source_family"] for item in midpoint.values())),
        control=exact_score(control), control_10000=exact_score(long_control),
        control_worst_overprediction=worst_overprediction(control),
        control_worst_overprediction_10000=worst_overprediction(long_control),
        long_simple_baselines=base_long, candidates=results, independent_external_sources=0, formal_acceptance=False,
    ))
    print({name:{key:round(value["metrics"][key],5) for key in ("r2","mae","rmse")} for name,value in results.items()})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("step", choices=("freeze", "run", "verify"))
    {"freeze":freeze, "run":run, "verify":verify}[parser.parse_args().step]()
