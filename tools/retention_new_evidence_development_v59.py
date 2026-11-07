"""One frozen, source-held-out comparison on four reviewed retention endpoints."""

import argparse
from collections import defaultdict
import json
import math
from pathlib import Path
import subprocess
import sys
import warnings

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.retention_corrected2e_v13 import environment
from tools.retention_horizon_normalization_v19 import gates, paired_error
from tools.retention_sawdust_development_v31 import BASE, BASELINES, OUT as P31
from tools.retention_sawdust_verify_v31 import exact_score
from tools.retention_shape_v4 import Encoder, SIX, estimator, expressed, metrics, now, predicted, read, sha, weights, write

OUT = BASE / "第五十九轮_四条补证曲线来源留出再训练_20261107"
P33 = BASE / "第三十三轮_刊本原图盲态复核_20261105/native_curve_evidence.json"
P35 = BASE / "第三十五轮_长循环补证与草莓秸秆原图_20261106/strawberry_evidence.json"
P36 = BASE / "第三十六轮_对照样品与极端衰减_20261106/control_evidence.json"
P57 = BASE / "第五十七轮_木源碳数据包与归一化证据_20261107/early_observations.json"
EXCLUDED = {"doi:10.1002/smsc.202500540", "doi:10.1016/j.cartre.2024.100436"}


def row(source, system, sample, target, window, static, origin):
    key = f"development:{source}::{system}::{sample}"
    f = window["features"]
    assert set(f) == set(SIX) and window["markers"] >= 3
    assert f["target_cycle_count"] == 10000 and f["early_observed_cycle_count"] <= 2000
    assert math.isfinite(target) and target > 0
    return dict(row_id=key+"::early20", endpoint_id=key, curve_id=key, material_key=key, source_family=source,
                sample_name=sample, target=target, features=f, static_features=static,
                last_early=f["last_early_retention_pct"], role="development_only_author_reported",
                evidence=origin.relative_to(ROOT).as_posix(), early_markers=window["markers"])


def additions():
    coffee, strawberry, rice = read(P33), read(P35), read(P36)["records"]["rice"]
    a, b = (strawberry["records"][system] for system in ("3E", "2E"))
    assert coffee["system"] == "2E" and coffee["eligible_development_trace"] == "AC-CSS"
    assert rice["system"] == "3E" and "asymmetric" in strawberry["device_conflict"]
    rice_static = dict(reported_current_A_g=rice["reported_current_A_g"], electrolyte="H2SO4",
                       concentration_mol_L=1.0, BET_m2_g=rice["own_BET_m2_g"],
                       cycle_voltage_lower_V=None, cycle_voltage_upper_V=None, reference_electrode=rice["reference"])
    strawberry_rows = [row(strawberry["source_family"], item["system"], item["sample_name"],
                           item["author_retention_pct"], item["windows"]["0.2"], item["static_features"], P35)
                       for item in (a, b)]
    rice_row = row(rice["source_family"], "3E", "Rice-straw AC", rice["author_retention_10000_pct"],
                   rice["windows"]["0.2"], rice_static, P36)
    coffee_row = row(coffee["source_family"], "2E", "AC-CSS", coffee["author_reported_retention_pct"],
                     coffee["windows"]["0.2"], coffee["static_features"], P33)
    assert [r["target"] for r in (*strawberry_rows, rice_row, coffee_row)] == [95.6, 70.1, 83.54, 75.0]
    return (
        {"3E": [strawberry_rows[0], rice_row], "2E": [coffee_row, strawberry_rows[1]]},
        {"coffee_plot": (coffee_row["row_id"], coffee["terminal_plot_retention_pct"]),
         "strawberry_plot": (strawberry_rows[1]["row_id"], b["terminal_geometry"]["ordinate_retention_pct"])},
    )


def freeze():
    assert not OUT.exists()
    parent = read(P31/"training_plan.json")
    assert environment() == parent["environment"]
    old = read(P31/"input_snapshot.json")
    added, sensitivity = additions()
    paths = [Path(__file__), P33, P35, P36, P57, BASE/"research_goal.json",
             *(P31/name for name in ("training_plan.json", "input_snapshot.json", "heldout_predictions.json", "results.json")),
             *(ROOT/"data"/f"{name}.json" for name in ("current_training_latest","current_retention_research"))]
    paths.extend(ROOT/"tools"/f"{name}.py" for name in (
        "retention_shape_v4","retention_v3_optimizer","run_small_sample_routes","retention_sawdust_verify_v31",
        "retention_horizon_normalization_v19","retention_corrected2e_v13","verify_retention_v3b"))
    data, specs = {}, {}
    for system, rows in old.items():
        prior = {r["source_family"] for r in rows}
        new = {r["source_family"] for r in added[system]}
        assert not prior & new and not (prior | new) & EXCLUDED
        joined = rows + added[system]
        assert len({r["row_id"] for r in joined}) == len(joined)
        assert all(r["features"]["early_observed_cycle_count"] <= .2*r["features"]["target_cycle_count"] for r in joined)
        folds = {s: {"train": [r["row_id"] for r in joined if r["source_family"] != s],
                     "test": [r["row_id"] for r in joined if r["source_family"] == s]}
                 for s in sorted(prior | new)}
        old_spec = parent["cohorts"][system]
        assert len(old_spec["configurations"]) == 8 and all(c["target"] == "delta" for c in old_spec["configurations"])
        data[system] = joined
        specs[system] = dict(folds=folds, configurations=old_spec["configurations"], primary=old_spec["primary"],
                             old_rows=len(rows), old_sources=len(prior), added_ids=[r["row_id"] for r in added[system]])
    assert {s: (len(data[s]),len(specs[s]["folds"])) for s in specs} == {"3E":(35,29),"2E":(33,27)}
    OUT.mkdir()
    snapshot = OUT/"input_snapshot.json"
    write(snapshot, data)
    plan = dict(frozen_at=now(), environment=environment(), parent=P31.relative_to(ROOT).as_posix(),
                cohorts=specs, sensitivity=sensitivity, planned_main_fits=448, planned_sensitivity_fits=54,
                planned_fits=502, criteria=read(BASE/"research_goal.json")["criteria"], baselines=list(BASELINES),
                protected={p.relative_to(ROOT).as_posix():sha(p) for p in [*paths,snapshot]},
                bootstrap={"seed":20261107,"draws":10000,"interval":[.025,.975],"unit":"source"},
                scope="Fixed B early20 2E/3E author endpoints. Hold whole paper, equal source/curve weights, fit encoder only on training folds.",
                label_policy="Use author text for both new 2E rows; independently replace each by same-trace figure reading for GPR sensitivity only.",
                strawberry_device_conflict="2E attribution is supported on both sides. Symmetry wording differs; symmetry is not an input.",
                excluded_untouched_source_families=sorted(EXCLUDED), external_acceptance=0)
    write(OUT/"training_plan.json",plan)
    write(OUT/"freeze_receipt.json",dict(plan_sha256=sha(OUT/"training_plan.json"),fits_at_freeze=0))


def check_plan():
    path = OUT/"training_plan.json"
    plan = read(path)
    assert sha(path)==read(OUT/"freeze_receipt.json")["plan_sha256"]
    assert plan["environment"]==environment()
    assert all(sha(ROOT/p)==value for p,value in plan["protected"].items())
    git = ["git","-c",f"safe.directory={ROOT.as_posix()}"]
    spec = path.relative_to(ROOT).as_posix()
    assert subprocess.check_output([*git,"show",f"HEAD:{spec}"],cwd=ROOT)==path.read_bytes()
    return plan


def datasets(plan):
    data = read(OUT/"input_snapshot.json")
    for system, spec in plan["cohorts"].items():
        yield "author", system, spec, data[system], spec["configurations"]
    spec = plan["cohorts"]["2E"]
    primary, = (c for c in spec["configurations"] if c["id"] == spec["primary"])
    for case, (key,target) in plan["sensitivity"].items():
        assert sum(r["row_id"]==key for r in data["2E"])==1
        rows = [dict(r,target=target) if r["row_id"]==key else r for r in data["2E"]]
        yield case,"2E",spec,rows,[primary]


def fold_data(rows, held, split):
    lookup = {r["row_id"]:r for r in rows}
    train, test = ([lookup[k] for k in split[key]] for key in ("train","test"))
    assert {r["source_family"] for r in test}=={held}
    assert held not in {r["source_family"] for r in train}
    assert not {r["curve_id"] for r in train} & {r["curve_id"] for r in test}
    assert len(train)+len(test)==len(rows)
    return train, test


def fit(cfg, train, test, event):
    tr, te = ([expressed(r,cfg,"six") for r in rows] for rows in (train,test))
    enc = Encoder().fit(tr)
    x, xt = enc.transform(tr), enc.transform(te)
    w = weights(train)
    delta = np.array([r["target"]-r["last_early"] for r in train])
    mean = float(np.average(delta, weights=w))
    scale = float(np.sqrt(np.average((delta-mean)**2,weights=w))) or 1.
    estimator_ = estimator(cfg)
    mass = w*len(train)
    kwargs = {"sample_weight":mass}
    if cfg["kind"]=="GPR":
        estimator_.set_params(alpha=cfg["parameters"]["alpha"]/mass)
        kwargs = {}
    event["attempted"]=True
    estimator_.fit(x,(delta-mean)/scale,**kwargs)
    values = estimator_.predict(xt)*scale+mean+np.array([r["last_early"] for r in test])
    assert values.shape==(len(test),) and np.isfinite(values).all()
    return values.tolist()


def run():
    plan = check_plan()
    with (OUT/"run_claim.json").open("x",encoding="utf-8") as f:
        json.dump({"started_at":now(),"plan_sha256":sha(OUT/"training_plan.json")},f)
    count=0
    with (OUT/"fit_events.jsonl").open("x",encoding="utf-8") as log:
        for case, system, spec, rows, configurations in datasets(plan):
            for held, split in spec["folds"].items():
                train,test=fold_data(rows,held,split)
                for cfg in configurations:
                    event=dict(case=case,system=system,held=held,config=cfg["id"],attempted=False)
                    with warnings.catch_warnings(record=True) as caught:
                        warnings.simplefilter("always")
                        try:
                            event["values"]=fit(cfg,train,test,event)
                            event["status"]="complete"
                        except Exception as exc:
                            event.update(status="failed",error=repr(exc))
                    event["warnings"]=[str(w.message) for w in caught]
                    log.write(json.dumps(event,ensure_ascii=False,allow_nan=False)+"\n")
                    count+=1
                    if count % 20==0:
                        log.flush()
            print(f"{case} {system}: {count}/{plan['planned_fits']} cumulative fit jobs",flush=True)
    assert count==plan["planned_fits"]
    check_plan()


def verify():
    plan=check_plan()
    events=[json.loads(line) for line in (OUT/"fit_events.jsonl").read_text(encoding="utf-8").splitlines()]
    event_index={(e["case"],e["system"],e["held"],e["config"]):e for e in events}
    assert len(event_index)==len(events)==plan["planned_fits"]
    references=read(P31/"heldout_predictions.json")
    previous=read(P31/"results.json")["scores"]
    outputs, predictions = {}, {}
    validated, used = 0, set()
    for case,system,spec,rows,configs in datasets(plan):
        methods=defaultdict(list)
        bases=defaultdict(list)
        for held,split in spec["folds"].items():
            train,test=fold_data(rows,held,split)
            ybar=float(np.average([r["target"] for r in train],weights=weights(train)))
            for r in test:
                f=r["features"]
                linear=r["last_early"]+f["early_retention_slope_per_1000_cycles"]*(f["target_cycle_count"]-f["early_observed_cycle_count"])/1000.
                for name,value in zip(BASELINES,(ybar,r["last_early"],linear),strict=True):
                    bases[name].append(predicted(system,name,r,value))
            for cfg in configs:
                key=(case,system,held,cfg["id"])
                e=event_index[key]
                used.add(key)
                if e["status"]=="complete":
                    assert e["attempted"]
                    methods[cfg["id"]].extend(predicted(system,cfg["id"],r,value)
                                              for r,value in zip(test,e["values"],strict=True))
                validated+=1
        results={}
        baseline={name:exact_score(values) for name,values in bases.items()}
        for cfg in configs:
            key=cfg["id"]
            values=methods[key]
            if len(values)!=len(rows):
                results[key]=dict(complete=False,numeric_pass=False)
                continue
            assert {r["row_id"]:r["observed"] for r in values}=={r["row_id"]:r["target"] for r in rows}
            reference=references[system]["loso"][key]
            ids={r["row_id"] for r in reference}
            old=[p for p in values if p["row_id"] in ids]
            assert {p["row_id"]:p["observed"] for p in old}=={p["row_id"]:p["observed"] for p in reference}
            before, after, full = map(exact_score,(reference,old,values))
            assert before==previous[system]["results"][key]["full"]
            independent=metrics(values)
            for k,x in full.items():
                if k not in {"p90_ape_pct","p90_absolute_error"}:
                    assert math.isclose(x,independent[k],abs_tol=1e-9,rel_tol=1e-9)
                    validated+=1
            flags=gates(values,full,baseline,plan["criteria"],len(rows))
            results[key]=dict(complete=True,control_common=before,expanded_common=after,full=full,
                              paired_common_mae=paired_error(old,reference,plan["bootstrap"]),gates=flags,
                              numeric_pass=all(flags.values()),
                              added=[p for p in values if p["row_id"] in spec["added_ids"]],
                              low_retention=[p for p in values if p["observed"]<=80.])
        case_id=f"{case}:{system}"
        outputs[case_id]=dict(primary=spec["primary"],rows=len(rows),sources=len(spec["folds"]),
                              baseline=baseline,results=results,
                              numeric_passes=sum(item["numeric_pass"] for item in results.values()))
        predictions[case_id]=dict(configurations=methods,baselines=bases)
    assert used==set(event_index)
    assert not (OUT/"results.json").exists()
    write(OUT/"heldout_predictions.json",predictions)
    write(OUT/"results.json",dict(status="source_held_out_development_only",cases=outputs,
          new_fits=sum(e["attempted"] for e in events),failures=sum(e["status"]!="complete" for e in events),
          warnings=sum(len(e["warnings"]) for e in events),checks=validated,
          numeric_passes=sum(value["numeric_passes"] for value in outputs.values()),
          external_sources=0,goal_achieved=False))


if __name__=="__main__":
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument("step",choices=("freeze","run","verify"))
    {"freeze":freeze,"run":run,"verify":verify}[cli.parse_args().step]()
