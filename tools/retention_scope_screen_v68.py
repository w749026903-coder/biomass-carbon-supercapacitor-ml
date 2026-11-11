"""Screen ten prediction-time scopes against matched wide and current fits."""

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
from tools.retention_literature_svr_v65 import BASE, P59, P64, SCOPE, dataset, mix
from tools.retention_mild_scope_v64 import baselines
from tools.retention_new_evidence_development_v59 import (
    environment, exact_score, fit, fold_data, gates, now, predicted, read, sha, write,
)
from tools.retention_rollback_regression_v60 import BOOT, GPR, RF, paired_error
from tools.retention_shape_mild_scope_v66 import GIT

OUT = BASE / "第六十八轮_十个物理适用范围_20261111"
RULES = {
    "bet1000": {"bet_min": 1000},
    "bet1500": {"bet_min": 1500},
    "koh2to6": {"koh_min": 2},
    "current5to10": {"current_min": 5},
    "window_minus1_to_0": {"voltage_window": [-1, 0]},
    "hghgo": {"reference": ["Hg/HgO", "HgO/Hg (reported order)"]},
    "cycles5000to10000": {"cycle_min": 5000},
    "mild_under5pp": {"early_max_exclusive": 5},
    "bet1000_current5to10": {"bet_min": 1000, "current_min": 5},
    "bet1000_window_minus1_to_0": {"bet_min": 1000, "voltage_window": [-1, 0]},
}


def exclusion(row, rules):
    f, s = row["features"], row["static_features"]
    early_change = f["early_retention_slope_per_1000_cycles"] * f["early_observed_cycle_count"] / 1000
    conditions = {
        "bet_min": lambda threshold: s["BET_m2_g"] is not None and s["BET_m2_g"] >= threshold,
        "koh_min": lambda threshold: s["concentration_mol_L"] >= threshold,
        "current_min": lambda threshold: s["reported_current_A_g"] >= threshold,
        "voltage_window": lambda bounds: [s["cycle_voltage_lower_V"], s["cycle_voltage_upper_V"]] == bounds,
        "reference": lambda references: s["reference_electrode"] in references,
        "cycle_min": lambda threshold: f["target_cycle_count"] >= threshold,
        "early_max_exclusive": lambda limit: max(f["early_retention_range_pp"], abs(early_change)) < limit,
    }
    return [name for name,value in rules.items() if not conditions[name](value)]


def scope_spec(pool, rules):
    excluded = {r["row_id"]: reasons for r in pool if (reasons := exclusion(r,rules))}
    rows = [r for r in pool if r["row_id"] not in excluded]
    sources = sorted({r["source_family"] for r in rows})
    folds = {
        source: {
            "train":[r["row_id"] for r in rows if r["source_family"] != source],
            "test":[r["row_id"] for r in rows if r["source_family"] == source],
        } for source in sources
    }
    return dict(rules=rules, rows=[r["row_id"] for r in rows], folds=folds, excluded=excluded)


def freeze():
    assert not OUT.exists()
    old, base, pool = dataset()
    assert environment() == old["environment"]
    minimum = old["source_minimum"]
    scopes = {name:scope_spec(pool,rules) for name,rules in RULES.items()}
    assert len({tuple(s["rows"]) for s in scopes.values()}) == len(scopes)
    assert all(len(s["folds"]) >= minimum for s in scopes.values())
    files = [
        Path(__file__), P59/"input_snapshot.json", P59/"heldout_predictions.json",
        *(P64/name for name in ("training_plan.json","predictions.json","applicability.json")),
    ]
    files.extend(ROOT/"tools"/f"{name}.py" for name in (
        "retention_mild_scope_v64","retention_literature_svr_v65","retention_new_evidence_development_v59",
        "retention_shape_v4","retention_v3_optimizer","run_small_sample_routes",
        "retention_horizon_normalization_v19","retention_sawdust_verify_v31",
    ))
    OUT.mkdir()
    write(OUT/"training_plan.json",dict(
        frozen_at=now(), parent_git=subprocess.check_output([*GIT,"rev-parse","HEAD"],cwd=ROOT,text=True).strip(),
        environment=environment(), target=old["output"], parent_rules=base["rules"], parent_rows=base["included"],
        scopes=scopes, minimum_development_sources=minimum, configurations=old["configurations"], criteria=old["criteria"],
        planned_fits=len(old["configurations"])*sum(len(s["folds"]) for s in scopes.values()),
        decision="Exploratory parallel screening. Rank matched MAE, jointly report R2, RMSE, tail, worst overprediction, sources and coverage. A challenger must have lower MAE and no regression in other tracked metrics or worst overprediction against P64 on exactly the same rows. Confirm selected scopes on untouched sources.",
        training_scope="Two fixed P64 configurations with 50/50 output average. Each scope trains only in-scope sources; P64 and P59 archived controls filtered to exact matched test rows.",
        thresholds="Round-number material/condition criteria for exploration, not universal standards. Exact voltage range refers to reported cycling window. No label used for scope membership.",
        protected={p.relative_to(ROOT).as_posix():sha(p) for p in files},
    ))


def checked():
    path = OUT/"training_plan.json"
    rel = path.relative_to(ROOT).as_posix()
    assert subprocess.check_output([*GIT,"show",f"HEAD:{rel}"],cwd=ROOT) == path.read_bytes()
    plan = read(path)
    assert environment() == plan["environment"]
    assert all(sha(ROOT/p) == value for p,value in plan["protected"].items())
    _, base, pool = dataset()
    assert plan["parent_rows"] == base["included"]
    assert {key:scope_spec(pool,value) for key,value in RULES.items()} == plan["scopes"]
    return plan,pool


def run():
    plan,pool = checked()
    with (OUT/"run_claim.json").open("x",encoding="utf-8") as file:
        json.dump(dict(started_at=now(),plan_sha256=sha(OUT/"training_plan.json")),file)
    events = []
    for name,scope in plan["scopes"].items():
        selected = [r for r in pool if r["row_id"] in scope["rows"]]
        for source,split in scope["folds"].items():
            train,test = fold_data(selected,source,split)
            for cfg in plan["configurations"]:
                e = dict(scope=name,source=source,configuration=cfg["id"],attempted=False)
                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter("always")
                    try:
                        values = fit(cfg,train,test,e)
                        e.update(status="complete",predictions=[
                            predicted("3E",cfg["id"],r,value) for r,value in zip(test,values,strict=True)
                        ])
                    except Exception as exc:
                        e.update(status="failed",error=repr(exc))
                e["warnings"] = [str(w.message) for w in caught]
                events.append(e)
        print(f"{name} {len(events)}/{plan['planned_fits']}",flush=True)
    assert len(events) == plan["planned_fits"]
    write(OUT/"fit_events.json",events)


def worst_overprediction(rows):
    row = max(rows,key=lambda p:p["predicted"]-p["observed"])
    return dict(sample=row["sample_name"],pp=row["predicted"]-row["observed"],row_id=row["row_id"])


def verify():
    plan,pool = checked()
    events = read(OUT/"fit_events.json")
    assert read(OUT/"run_claim.json")["plan_sha256"] == sha(OUT/"training_plan.json")
    keys = {(name,source,cfg["id"]) for name,scope in plan["scopes"].items()
            for source in scope["folds"] for cfg in plan["configurations"]}
    assert len(events) == len(keys) == plan["planned_fits"]
    assert keys == {(e["scope"],e["source"],e["configuration"]) for e in events}
    by = defaultdict(list)
    for event in events:
        name,source,cfg = (event[key] for key in ("scope","source","configuration"))
        if event["status"] == "complete":
            assert [r["row_id"] for r in event["predictions"]] == plan["scopes"][name]["folds"][source]["test"]
            assert all(r["source_family"] == source for r in event["predictions"])
            by[(name,cfg)].extend(event["predictions"])
    old = read(P64/"predictions.json")[SCOPE]["methods"]["half_GPR_RF"]
    wide = read(P59/"heldout_predictions.json")["author:3E"]["configurations"]
    wide_mix = mix(wide[GPR],wide[RF],[.5,.5],"P59")
    results,preds = {},{}
    for name,scope in plan["scopes"].items():
        ids = set(scope["rows"])
        a,b = (by[(name,cfg["id"])] for cfg in plan["configurations"])
        if len(a) != len(ids) or len(b) != len(ids):
            results[name] = dict(complete=False)
            continue
        values = mix(a,b,[.5,.5],name)
        ref = [r for r in old if r["row_id"] in ids]
        wider = [r for r in wide_mix if r["row_id"] in ids]
        labels = {r["row_id"]:r["observed"] for r in ref}
        assert set(labels) == ids and all(labels == {r["row_id"]:r["observed"] for r in rows}
                                           for rows in (values,wider))
        scores = {key:exact_score(rows) for key,rows in
                  (("limited",values),("current_matched",ref),("wide_matched",wider))}
        m,control = scores["limited"],scores["current_matched"]
        regressions = [key for key in METRICS if
                       (m[key] < control[key]-1e-10 if key=="r2" else m[key] > control[key]+1e-10)]
        worst = worst_overprediction(values)
        worst_control = worst_overprediction(ref)
        if worst["pp"] > worst_control["pp"]+1e-10:
            regressions.append("worst_overprediction")
        simple = {key:exact_score(rows) for key,rows in baselines(
            [r for r in pool if r["row_id"] in ids],scope["folds"]).items()}
        gate = gates(values,m,simple,plan["criteria"],len(ids))
        results[name] = dict(
            complete=True,rows=len(ids),sources=len(scope["folds"]),scores=scores,
            worst_overprediction=worst,matched_worst_overprediction=worst_control,
            regression=regressions,paired_mae=paired_error(values,ref,BOOT),gates=gate,
            target_rmse_exclusive_pp=m["rmse"]*(.05/(1-m["r2"]))**.5,
            eligible_challenger=not regressions and m["mae"] < control["mae"]-1e-10,
            numeric_pass=all(gate.values()),
        )
        preds[name] = dict(limited=values,current_matched=ref,wide_matched=wider)
    write(OUT/"predictions.json",preds)
    write(OUT/"results.json",dict(
        fits=sum(e["attempted"] for e in events),failures=sum(e["status"]!="complete" for e in events),
        warnings=sum(len(e["warnings"]) for e in events),scopes=results,external_sources=0,formal_acceptance=False,
    ))
    for key,v in results.items():
        if v["complete"]:
            m = v["scores"]["limited"]
            print(key,v["rows"],v["sources"],round(m["r2"],4),round(m["mae"],4),
                  round(v["scores"]["current_matched"]["mae"],4),v["eligible_challenger"],v["numeric_pass"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("step",choices=("freeze","run","verify"))
    {"freeze":freeze,"run":run,"verify":verify}[parser.parse_args().step]()
