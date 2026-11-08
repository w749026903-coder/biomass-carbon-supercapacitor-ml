"""Test literature-inspired SVR and a small condition block on the fixed P64 cohort."""

import argparse
from collections import defaultdict
import json
import math
from pathlib import Path
import subprocess
import sys
import warnings

import numpy as np
from sklearn.svm import SVR

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.retention_new_evidence_development_v59 import (
    environment, exact_score, expressed, fold_data, gates, now, predicted, read, sha, weights, write,
)
from tools.retention_shape_v4 import Encoder
from tools.retention_mild_scope_v64 import BASE, OUT as P64, P59
from tools.retention_rollback_regression_v60 import BOOT, paired_error
from tools.retention_decline_guard_v63 import METRICS

OUT=BASE/"第六十五轮_文献借鉴与支持向量对照_20261108"
SCOPE="koh_1_to_6m_mild_early"
SVR_SETTINGS={"kernel":"rbf","C":2.,"epsilon":.10,"gamma":"scale"}
VARIANTS={"SVR_early":False,"SVR_early_conditions":True}


def condition_block(row):
    s=row["static_features"]
    lower,upper=s["cycle_voltage_lower_V"],s["cycle_voltage_upper_V"]
    voltage=upper-lower if lower is not None and upper is not None else None
    assert voltage is None or voltage>0
    return {"reported_current_A_g":s["reported_current_A_g"],"concentration_mol_L":s["concentration_mol_L"],
            "cycle_voltage_span_V":voltage}


def dataset():
    old=read(P64/"training_plan.json")
    cohort=old["scopes"][SCOPE]
    pool=read(P59/"input_snapshot.json")["3E"]
    rows=[r for r in pool if r["row_id"] in cohort["included"]]
    assert [r["row_id"] for r in rows]==cohort["included"]
    return old,cohort,rows


def freeze():
    assert not OUT.exists()
    old,cohort,rows=dataset()
    assert len(rows)==23 and len(cohort["folds"])==18 and environment()==old["environment"]
    coverage={key:sum(condition_block(r)[key] is not None for r in rows) for key in condition_block(rows[0])}
    assert list(coverage.values())==[23,23,22]
    guard=[Path(__file__),BASE/"research_goal.json",P59/"input_snapshot.json",
           *(P64/k for k in ("training_plan.json","predictions.json","results.json","applicability.json"))]
    guard.extend(ROOT/"tools"/f"{name}.py" for name in (
        "retention_new_evidence_development_v59","retention_shape_v4","retention_v3_optimizer",
        "run_small_sample_routes","retention_mild_scope_v64"))
    OUT.mkdir()
    write(OUT/"training_plan.json",dict(frozen_at=now(),parent_git="25b7ddb",environment=environment(),
        scope=SCOPE,rows=cohort["included"],folds=cohort["folds"],base_case="P64 fixed 50/50 GPR/RF",
        variants=VARIANTS,svr_settings=SVR_SETTINGS,condition_coverage=coverage,
        weights_in_mix=[2/3,1/3],planned_new_fits=36,criteria=old["criteria"],
        material_features="Only original early20 summaries; optional three existing test conditions, voltage span derived from both limits.",
        target="Scale author endpoint minus last early observation inside each training fold; undo scaling for predictions.",
        literature={
          "review_small_samples_and_transfer":"https://www.sciencedirect.com/science/article/pii/S2352152X2504633X",
          "primary_gaussian_svr_on_specific_capacitance":"https://doi.org/10.1002/cplu.202500342",
          "primary_cycling_plus_conditions_device_retention":"https://doi.org/10.3390/batteries11070264",
          "primary_selection_bias":"https://link.springer.com/article/10.1186/1471-2105-7-91",
        },
        decision="All matched point accuracy metrics must hold or improve and RMSE must improve before proposing a next-stage candidate. Final approval requires all numeric and unseen-source gates.",
        protected={p.relative_to(ROOT).as_posix():sha(p) for p in guard}))


def checked():
    path=OUT/"training_plan.json"
    rel=path.relative_to(ROOT).as_posix()
    git=["git","-c",f"safe.directory={ROOT.as_posix()}"]
    assert subprocess.check_output([*git,"show",f"HEAD:{rel}"],cwd=ROOT)==path.read_bytes()
    plan=read(path)
    assert environment()==plan["environment"]
    assert all(sha(ROOT/p)==h for p,h in plan["protected"].items())
    return plan


def fit_svr(train,test,settings,with_conditions,event):
    cfg={"feature_view":"continuation","static":False}
    tr,te=([expressed(r,cfg,"six") for r in rows] for rows in (train,test))
    if with_conditions:
        for r in tr+te:
            r["features"].update(condition_block(r))
    encoder=Encoder().fit(tr)
    x,xt=encoder.transform(tr),encoder.transform(te)
    w=weights(train)
    d=np.array([r["target"]-r["last_early"] for r in train])
    center=float(np.average(d,weights=w))
    sd=float(np.sqrt(np.average((d-center)**2,weights=w))) or 1.
    model=SVR(**settings)
    event["attempted"]=True
    model.fit(x,(d-center)/sd,sample_weight=w*len(train))
    y=model.predict(xt)*sd+center+np.array([r["last_early"] for r in test])
    assert np.isfinite(y).all()
    event["encoder_fields"]=[s["field"] for s in encoder.schema]
    return y


def run():
    plan=checked()
    _,cohort,rows=dataset()
    assert cohort["folds"]==plan["folds"]
    with (OUT/"run_claim.json").open("x",encoding="utf-8") as f:
        json.dump(dict(started_at=now(),plan_sha256=sha(OUT/"training_plan.json")),f)
    events=[]
    for source,split in plan["folds"].items():
        train,test=fold_data(rows,source,split)
        for name,with_conditions in plan["variants"].items():
            event=dict(source=source,model=name,attempted=False)
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                try:
                    y=fit_svr(train,test,plan["svr_settings"],with_conditions,event)
                    event.update(status="complete",predictions=[predicted("3E",name,r,v) for r,v in zip(test,y,strict=True)])
                except Exception as exc:
                    event.update(status="failed",error=repr(exc))
            event["warnings"]=[str(w.message) for w in caught]
            events.append(event)
    assert len(events)==plan["planned_new_fits"]
    write(OUT/"fit_events.json",events)


def mix(old,new,weights_,name):
    ids={r["row_id"]:r for r in new}
    assert set(ids)=={r["row_id"] for r in old}
    result=[]
    for p in old:
        q=ids[p["row_id"]]
        assert all(p[k]==q[k] for k in ("source_family","curve_id","observed"))
        result.append(dict(p,model=name,predicted=weights_[0]*p["predicted"]+weights_[1]*q["predicted"]))
    return result


def verify():
    plan=checked()
    events=read(OUT/"fit_events.json")
    assert len(events)==plan["planned_new_fits"] and {(e["source"],e["model"]) for e in events}=={
        (s,m) for s in plan["folds"] for m in plan["variants"]}
    prev=read(P64/"predictions.json")[SCOPE]
    control=prev["methods"]["half_GPR_RF"]
    baseline={k:exact_score(r) for k,r in prev["baselines"].items()}
    ref=exact_score(control)
    by_model=defaultdict(list)
    for e in events:
        if e["status"]=="complete":
            assert e["attempted"]
            assert {r["row_id"] for r in e["predictions"]}==set(plan["folds"][e["source"]]["test"])
            assert all(r["source_family"]==e["source"] for r in e["predictions"])
            by_model[e["model"]].extend(e["predictions"])
    out={}
    for name in plan["variants"]:
        values=by_model[name]
        if len(values)!=len(control):
            out[name]={"complete":False,"eligible_challenger":False}
            continue
        name_mix=name+"_one_third"
        by_model[name_mix]=mix(control,values,plan["weights_in_mix"],name_mix)
        for tag,rows in ((name,values),(name_mix,by_model[name_mix])):
            assert {r["row_id"]:r["observed"] for r in rows}=={r["row_id"]:r["observed"] for r in control}
            score=exact_score(rows)
            delta={k:score[k]-ref[k] for k in METRICS}
            regression=[k for k,x in delta.items() if (x < -1e-10 if k=="r2" else x > 1e-10)]
            passed=gates(rows,score,baseline,plan["criteria"],len(control))
            out[tag]=dict(complete=True,metrics=score,delta=delta,regressed_metrics=regression,
                          paired_mae=paired_error(rows,control,BOOT),gates=passed,
                          eligible_challenger=not regression and delta["rmse"]<-1e-10 and passed["positive"])
    write(OUT/"results.json",dict(status="literature_inspired_exploratory_screen",control=ref,
          fits=sum(e["attempted"] for e in events),failures=sum(e["status"]!="complete" for e in events),
          warnings=sum(len(e["warnings"]) for e in events),candidates=out,external_sources=0,formal_acceptance=False))
    write(OUT/"predictions.json",dict(control=control,candidates=by_model))


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("step",choices=("freeze","run","verify"))
    {"freeze":freeze,"run":run,"verify":verify}[parser.parse_args().step]()
