"""Check declining-trend corrections against the unchanged 13-row retention reference."""

import argparse
import json
import math
from pathlib import Path
import subprocess
import sys
import warnings

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.retention_new_evidence_development_v59 import environment, exact_score, fit, fold_data, now, predicted, read, sha, write
from tools.retention_physical_scope_v61 import BASE, P59, P60, OUT as P61, GPR, RF, blend
from tools.retention_rollback_regression_v60 import BOOT, paired_error
from tools.retention_transfer_scope_v62 import OUT as P62

OUT=BASE/"第六十三轮_强衰减尾部修正与双队列守门_20261108"
METRICS=("r2","mae","rmse","p90_absolute_error","source_p90_mae","mape_pct","p90_ape_pct")
RULE={"minimum_early_range_pp":10.,"minimum_regressed_decline_pp":10.,"minimum_observed_fraction":.10,
      "maximum_observed_fraction":.20,"weights":[.25,.50]}
BASE_METHOD="P60_half_GPR_RF"


def inputs():
    plan=read(P60/"training_plan.json")
    original=read(P59/"input_snapshot.json")["3E"]
    removed,=plan["additions"]["rice_only"]
    extra,=plan["additions"]["strawberry_only"]
    data=[r for r in original if r["row_id"]!=removed]
    folds={source:{"train":[*fold["train_ids"],extra],"test":fold["test_ids"]}
           for source,fold in plan["old_source_folds"].items()}
    assert len(data)==34 and len(folds)==27
    return plan,data,folds


def freeze():
    assert not OUT.exists()
    parent,rows,folds=inputs()
    assert environment()==parent["environment"]
    paths=[Path(__file__),BASE/"research_goal.json",ROOT/"data/current_retention_scope_scorecard.json",
           P59/"input_snapshot.json",P60/"training_plan.json",P60/"predictions.json",P61/"original13_scorecard.json",
           P61/"original13_predictions.json",P62/"evidence.json"]
    paths.extend(ROOT/"tools"/f"{n}.py" for n in (
        "retention_new_evidence_development_v59","retention_physical_scope_v61",
        "retention_shape_v4","retention_v3_optimizer","run_small_sample_routes"))
    OUT.mkdir()
    write(OUT/"training_plan.json",dict(frozen_at=now(),parent_git="72a5155",environment=environment(),
          data_rows=len(rows),matched_test_rows=33,folds=folds,configurations=parent["configurations"],
          postprocess_rule=RULE,global_prior_weight=.5,planned_fits=54,
          prior_formula="last + slope_per_1000 * observed_cycles/1000 * ln(target_cycles/observed_cycles)",
          interpretation="A decreasing-rate extrapolation heuristic, not an asserted electrochemical mechanism.",
          promotion={"legacy13":"no point metric regression, including both P90 and relative errors",
                     "other20":"no point metric regression, MAE decrease >=0.10 pp and RMSE decrease >=0.20 pp",
                     "any_changed_record":"absolute error increase at most 0.50 pp",
                     "formal":"one retrospectively selected candidate can be prepared for independent testing; no production release"},
          protected={p.relative_to(ROOT).as_posix():sha(p) for p in paths}))


def checked():
    path=OUT/"training_plan.json"
    spec=path.relative_to(ROOT).as_posix()
    git=["git","-c",f"safe.directory={ROOT.as_posix()}"]
    assert subprocess.check_output([*git,"show",f"HEAD:{spec}"],cwd=ROOT)==path.read_bytes()
    plan=read(path)
    assert environment()==plan["environment"]
    assert all(sha(ROOT/p)==h for p,h in plan["protected"].items())
    return plan


def early_prior(row):
    f=row["features"]
    n=f["early_observed_cycle_count"]
    target=f["target_cycle_count"]
    assert 0<n<=.2*target
    early_change=f["early_retention_slope_per_1000_cycles"]*n/1000.
    prior=f["last_early_retention_pct"]+early_change*math.log(target/n)
    return prior,early_change,n/target


def triggered(row,rule,early_change,fraction):
    return (rule["minimum_observed_fraction"]<=fraction<=rule["maximum_observed_fraction"]
            and row["features"]["early_retention_range_pp"]>=rule["minimum_early_range_pp"]
            and early_change<=-rule["minimum_regressed_decline_pp"])


def run():
    plan=checked()
    _,rows,folds=inputs()
    assert folds==plan["folds"]
    with (OUT/"run_claim.json").open("x",encoding="utf-8") as f:
        json.dump(dict(started_at=now(),plan_sha256=sha(OUT/"training_plan.json")),f)
    anchored=[]
    for r in rows:
        prior,_,_=early_prior(r)
        anchor=r["last_early"]+plan["global_prior_weight"]*(prior-r["last_early"])
        anchored.append(dict(r,last_early=anchor))
    events=[]
    for source,split in folds.items():
        train,test=fold_data(anchored,source,split)
        for method,cfg in plan["configurations"].items():
            event=dict(source=source,model=method,attempted=False)
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                try:
                    values=fit(cfg,train,test,event)
                    event.update(status="complete",predictions=[predicted("3E",method,r,y) for r,y in zip(test,values,strict=True)])
                except Exception as exc:
                    event.update(status="failed",error=repr(exc))
            event["warnings"]=[str(w.message) for w in caught]
            events.append(event)
    assert len(events)==plan["planned_fits"]
    write(OUT/"fit_events.json",events)


def screen(name,rows,baseline,legacy):
    ref={r["row_id"]:r for r in baseline}
    assert set(ref)=={r["row_id"] for r in rows}
    assert all((r["observed"],r["source_family"],r["curve_id"])==
               (ref[r["row_id"]]["observed"],ref[r["row_id"]]["source_family"],ref[r["row_id"]]["curve_id"]) for r in rows)
    detail={}
    changes=[]
    for r in rows:
        old=ref[r["row_id"]]
        if r["predicted"]!=old["predicted"]:
            changes.append(dict(row_id=r["row_id"],sample_name=r["sample_name"],observed=r["observed"],
                           baseline=old["predicted"],candidate=r["predicted"],source=r["source_family"],
                           delta_abs_error_pp=abs(r["predicted"]-r["observed"])-abs(old["predicted"]-old["observed"])))
    for tag,ids in (("legacy13",legacy),("other20",ref.keys()-legacy),("all33",ref.keys())):
        a=[r for r in rows if r["row_id"] in ids]
        b=[r for r in baseline if r["row_id"] in ids]
        u,v=exact_score(a),exact_score(b)
        delta={key:u[key]-v[key] for key in METRICS}
        regressed=[key for key in METRICS if (delta[key]<-1e-10 if key=="r2" else delta[key]>1e-10)]
        detail[tag]=dict(metrics=u,delta=delta,regressed_metrics=regressed,
                         paired_mae=paired_error(a,b,BOOT))
    no_regression=all(not d["regressed_metrics"] for d in detail.values())
    delta=detail["other20"]["delta"]
    worth=delta["mae"]<=-.10 and delta["rmse"]<=-.20
    hard_ok=all(r["delta_abs_error_pp"]<=.50 for r in changes)
    positive=all(r["predicted"]>0 and math.isfinite(r["predicted"]) for r in rows)
    return dict(candidate=name,cohorts=detail,changed=changes,complete=True,positive=positive,
                development_screen_pass=no_regression and worth and hard_ok and positive,
                formal_acceptance=False)


def verify():
    plan=checked()
    events=read(OUT/"fit_events.json")
    assert {(e["source"],e["model"]) for e in events}=={(s,m) for s in plan["folds"] for m in plan["configurations"]}
    assert len(events)==plan["planned_fits"]
    p=read(P60/"predictions.json")
    original=blend(p[GPR]["strawberry_only"],p[RF]["strawberry_only"],BASE_METHOD)
    legacy={r["row_id"] for r in read(P61/"original13_predictions.json")}
    assert [r for r in original if r["row_id"] in legacy]==read(P61/"original13_predictions.json")
    rows={r["row_id"]:r for r in inputs()[1]}
    candidate_results={}
    predictions={}
    active=[]
    for r in original:
        row=rows[r["row_id"]]
        prior,change,fraction=early_prior(row)
        if triggered(row,plan["postprocess_rule"],change,fraction):
            active.append(dict(row_id=r["row_id"],sample_name=r["sample_name"],source=r["source_family"],
                               early_change_pp=change,log_prior_pct=prior,observed_fraction=fraction))
    priors={r["row_id"]:r["log_prior_pct"] for r in active}
    for w in plan["postprocess_rule"]["weights"]:
        name=f"strong_log_{round(w*100)}"
        data=[dict(r,model=name,predicted=(1-w)*r["predicted"]+w*priors[r["row_id"]]) if r["row_id"] in priors else r
              for r in original]
        predictions[name]=data
        candidate_results[name]=screen(name,data,original,legacy)
    raw={}
    for model in (GPR,RF):
        raw[model]=[]
        for e in events:
            if e["model"]==model and e["status"]=="complete":
                assert e["attempted"]
                assert {r["row_id"] for r in e["predictions"]}==set(plan["folds"][e["source"]]["test"])
                raw[model].extend(e["predictions"])
    name="globally_anchored_residual_mix"
    if len(raw[GPR])==len(raw[RF])==len(original):
        data=blend(raw[GPR],raw[RF],name)
        predictions[name]=data
        candidate_results[name]=screen(name,data,original,legacy)
    else:
        candidate_results[name]={"complete":False,"development_screen_pass":False}
    write(OUT/"predictions.json",predictions)
    write(OUT/"results.json",dict(status="retrospective_regression_screen",fits=sum(e["attempted"] for e in events),
          failures=sum(e["status"]!="complete" for e in events),warnings=sum(len(e["warnings"]) for e in events),
          triggered_rows=active,candidates=candidate_results,external_sources=0,formal_acceptance=False))


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("step",choices=("freeze","run","verify"))
    {"freeze":freeze,"run":run,"verify":verify}[parser.parse_args().step]()
