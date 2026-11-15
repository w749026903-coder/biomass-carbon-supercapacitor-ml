"""Lock predictions from the frozen P64/P67 recipes using early observations only."""

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.retention_horizon_routes_v67 import OUT as P67
from tools.retention_horizon_routes_v67 import fit_weighted
from tools.retention_literature_svr_v65 import BASE, P64, SCOPE, dataset
from tools.retention_mild_scope_v64 import outside_reasons
from tools.retention_new_evidence_development_v59 import environment, fit, now, read, sha, weights
from tools.retention_shape_mild_scope_v66 import GIT

P70 = BASE / "第七十轮_定向盲测计划与题录筛查_20261116" / "plan.json"
OUT = BASE / "第七十五轮_盲测预测锁定核验_20261116"
CASES_KEYS = {
    "doi", "sample", "curve_id", "system", "material_class", "electrolyte", "concentration_mol_L",
    "reported_current_A_g", "target_cycles", "bet_m2_g", "early_points", "evidence",
    "no_development_source_overlap", "no_prior_terminal_exposure", "confirmed_same_test_and_basis",
}
POINT_KEYS = {"cycle", "cycle_lower", "cycle_upper", "retention_pct"}


def committed(path):
    path = path.resolve(strict=True)
    name = path.relative_to(ROOT).as_posix()
    commit = subprocess.check_output([*GIT, "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    stored = subprocess.check_output([*GIT, "show", f"{commit}:{name}"], cwd=ROOT)
    assert path.read_bytes() == stored, f"Working file differs from committed bytes: {name}"
    return commit


def checked():
    path = OUT / "plan.json"
    committed(path)
    plan = read(path)
    assert environment() == plan["environment"]
    assert all(sha(ROOT / name) == h for name,h in plan["protected"].items())
    p64, cohort, pool = dataset()
    p67 = read(P67 / "training_plan.json")
    midpoint = read(P67 / "midpoint_evidence.json")
    assert p64["configurations"] == p67["configurations"] and p67["rows"] == cohort["included"]
    return plan, cohort, pool, p64["configurations"], p67, midpoint


def from_early_case(case, scope):
    assert set(case) == CASES_KEYS
    assert all(case.get(key) is True for key in ("no_development_source_overlap", "no_prior_terminal_exposure",
                                                 "confirmed_same_test_and_basis"))
    doi = case["doi"]
    assert isinstance(doi,str) and doi == doi.lower() and re.fullmatch(r"10\.\d{4,9}/\S+",doi)
    assert case["system"] == "3E" and case["material_class"] == scope["material"]
    assert isinstance(case["curve_id"],str) and case["curve_id"].strip()
    assert isinstance(case["sample"],str) and case["sample"].strip()
    assert type(case["target_cycles"]) is int
    n = case["target_cycles"]
    points = case["early_points"]
    assert len(points) >= scope["minimum_verified_early_points"]
    for point in points:
        assert set(point) == POINT_KEYS
        assert all(type(value) in (int,float) and np.isfinite(value) for value in point.values())
        assert 0 <= point["cycle_lower"] <= point["cycle"] <= point["cycle_upper"] <= n * scope["maximum_early_fraction"]
        assert point["cycle"] > 0 and point["retention_pct"] > 0
    x,y = (np.array([p[k] for p in points]) for k in ("cycle","retention_pct"))
    assert np.all(np.diff(x) > 0)
    f = dict(
        last_early_retention_pct=float(y[-1]), early_mean_retention_pct=float(y.mean()),
        early_retention_slope_per_1000_cycles=float(np.polyfit(x / 1000,y,1)[0]),
        early_retention_range_pp=float(np.ptp(y)), early_observed_cycle_count=float(x[-1]), target_cycle_count=n,
    )
    for key in ("concentration_mol_L","reported_current_A_g"):
        assert type(case[key]) in (int,float) and np.isfinite(case[key])
    bet = case["bet_m2_g"]
    assert bet is None or (type(bet) in (int,float) and np.isfinite(bet) and bet > 0)
    assert case["evidence"] and all(isinstance(name,str) for name in case["evidence"])
    for name,h in case["evidence"].items():
        path = (ROOT/name).resolve(strict=True)
        path.relative_to(ROOT)
        assert re.fullmatch(r"[a-f0-9]{64}",h) and sha(path) == h
    row = dict(row_id=case["curve_id"], curve_id=case["curve_id"], source_family="doi:"+doi,
               features=f, last_early=float(y[-1]), material_key=case["sample"], sample_name=case["sample"],
               static_features={key:case[key] for key in ("electrolyte","concentration_mol_L","reported_current_A_g","bet_m2_g")})
    lo,hi = scope["electrolyte_mol_L_inclusive"]
    j_min,j_max = scope["reported_cycle_current_A_g_inclusive"]
    reasons = outside_reasons(row,dict(mol_L_min=lo,mol_L_max=hi,A_g_min=j_min,A_g_max=j_max))
    assert not reasons, reasons
    return row


def predict(train, query, configurations, midpoint, p67):
    assert {r["source_family"] for r in train}.isdisjoint(r["source_family"] for r in query)
    assert {r["curve_id"] for r in train}.isdisjoint(r["curve_id"] for r in query)
    case10k = [r for r in query if r["features"]["target_cycle_count"] == p67["long_horizon"]]
    base_w = weights(train)
    add_w = base_w.copy()
    addon, addon_w = [], []
    for i,row in enumerate(train):
        item = midpoint.get(row["row_id"])
        if item is not None:
            addon.append(item["row"])
            part = add_w[i] * p67["midpoint_share"]
            add_w[i] -= part
            addon_w.append(part)
    baseline = np.mean([fit(cfg,train,query,{}) for cfg in configurations],axis=0)
    routed = {}
    if case10k:
        aug = np.mean([fit_weighted(cfg,train,addon,case10k,add_w,addon_w,{})
                       for cfg in configurations],axis=0)
        routed = {row["row_id"]:float(v) for row,v in zip(case10k,aug,strict=True)}
    mean = float(np.average([r["target"] for r in train],weights=base_w))
    outputs = []
    for r,y0 in zip(query,baseline,strict=True):
        f = r["features"]
        remaining = f["target_cycle_count"] - f["early_observed_cycle_count"]
        linear = r["last_early"] + f["early_retention_slope_per_1000_cycles"] * remaining / 1000
        outputs.append(dict(row_id=r["row_id"], source_family=r["source_family"],
            target_cycles=f["target_cycle_count"], p64=float(y0), p67=routed.get(r["row_id"],float(y0)),
            training_source_mean=mean, early_persistence=r["last_early"], early_linear=linear))
    return outputs, len(configurations) * (1 + bool(case10k))


def check_archived():
    plan, cohort, pool, configs, p67, midpoint = checked()
    ref = read(P64 / "predictions.json")[SCOPE]
    route = read(P67 / "diagnostic_10000.json")["predictions"]
    names = {"p64":ref["methods"]["half_GPR_RF"], "p67":route, **ref["baselines"]}
    records, total = [], 0
    for source in plan["historical_reproduction_sources"]:
        selected = cohort["folds"][source]
        train = [r for r in pool if r["row_id"] in selected["train"]]
        query = [{k:v for k,v in r.items() if k!="target"} for r in pool if r["row_id"] in selected["test"]]
        predictions, count = predict(train,query,configs,midpoint,p67)
        records.extend(predictions)
        total += count
    aliases = {"training_mean":"training_source_mean"}
    for model, archived in names.items():
        index = {r["row_id"]:r["predicted"] for r in archived}
        for r in records:
            value = r[aliases.get(model,model)]
            assert np.isclose(index[r["row_id"]],value,rtol=0,atol=1e-10), model
    assert total == plan["planned_historical_reproduction_fits"]
    record = dict(status="historical_reproduction_only", fits=total, rows=len(records),
                  sources=plan["historical_reproduction_sources"], matched_columns=list(names),
                  candidates_scored=0, new_independent_sources=0, predictions=records)
    with (OUT/"reproduction.json").open("x",encoding="utf-8",newline="\n") as stream:
        json.dump(record,stream,ensure_ascii=False,indent=2)
        stream.write("\n")
    print(f"Matched {len(records)} archived rows across {len(names)} columns using {total} reproduction fits.")


def lock(registry):
    plan,_,pool,configs,p67,midpoint = checked()
    commit = committed(registry)
    data = read(registry)
    assert set(data) == {"plan_sha256","cases"} and data["plan_sha256"] == sha(P70)
    assert data["cases"]
    query = [from_early_case(case,read(P70)["primary_scope"]) for case in data["cases"]]
    assert len({r["row_id"] for r in query}) == len(query)
    dest = registry.parent/"locked_predictions.json"
    assert not dest.exists()
    outputs,count = predict(pool,query,configs,midpoint,p67)
    for row,case in zip(outputs,data["cases"],strict=True):
        row.update(bet_m2_g=case["bet_m2_g"])
    result = dict(status="predictions_locked_locally",time=now(),registry_sha256=sha(registry),
                  registry_commit=commit,plan_sha256=sha(P70),runner_plan_sha256=sha(OUT/"plan.json"),
                  fits=count,new_external_sources_not_yet_scored=len({r["source_family"] for r in query}),
                  predictions=outputs)
    with dest.open("x",encoding="utf-8",newline="\n") as stream:
        json.dump(result,stream,ensure_ascii=False,indent=2,allow_nan=False)
        stream.write("\n")
    print(dest)


if __name__ == "__main__":
    if not __debug__:
        raise RuntimeError("Run without optimized assertions.")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry",type=Path,help="Committed independently audited early-only input registry")
    parser.add_argument("--reproduce-history",action="store_true")
    args = parser.parse_args()
    if bool(args.registry) == args.reproduce_history:
        parser.error("Choose exactly one execution mode.")
    if args.reproduce_history:
        check_archived()
    else:
        lock(args.registry)
