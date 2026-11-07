"""Reproduce the 3E regression on fixed papers and compare fixed model combinations."""

import argparse
from collections import defaultdict
import json
from pathlib import Path
import subprocess
import sys
import warnings

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.retention_new_evidence_development_v59 import (
    BASE, P31, OUT as P59, Encoder, environment, estimator, exact_score, expressed,
    fit, now, paired_error, predicted, read, sha, weights, write,
)

OUT=BASE/"第六十轮_回档与单因素回归诊断_20261107"
P1=BASE/"第一轮_参数与表达"
GPR="GPR_early_p1_continuation_delta"
RF="RF_early_p0_raw_delta"
XGB="XGB_early_p1_raw_delta"
BASELINES={"3E":RF,"2E":GPR}
MIXES={"3E":[RF,XGB],"2E":[GPR,RF]}
REF_FILES=("training_plan.json","input_snapshot.json","heldout_predictions.json","results.json")
BOOT={"seed":20261107,"draws":10000,"interval":[.025,.975],"unit":"source"}


def freeze():
    assert not OUT.exists()
    p31,p59=(read(p/"input_snapshot.json") for p in (P31,P59))
    specs=read(P31/"training_plan.json")
    assert environment()==specs["environment"]
    assert all(p59[system][:len(rows)]==rows for system,rows in p31.items())
    a,b=p59["3E"][len(p31["3E"]):]
    assert (a["sample_name"],b["sample_name"])==("SPC3","Rice-straw AC")
    saved=read(P31/"results.json")["scores"]
    rf,gb=(saved["3E"]["results"][key]["full"] for key in (RF,XGB))
    assert rf["mae"]<gb["mae"] and rf["p90_absolute_error"]<gb["p90_absolute_error"]
    assert saved["2E"]["results"][GPR]["full"]["mae"]==min(s["full"]["mae"] for s in saved["2E"]["results"].values())
    folded=specs["cohorts"]["3E"]["folds"]
    assert len(folded)==27
    guards=[Path(__file__), BASE/"research_goal.json", P1/"input_snapshot.json",
            *(p/f for p in (P31,P59) for f in REF_FILES)]
    guards.extend(ROOT/"tools"/f"{n}.py" for n in (
        "retention_new_evidence_development_v59","retention_sawdust_verify_v31","retention_shape_v4",
        "retention_horizon_normalization_v19","run_small_sample_routes","retention_v3_optimizer"))
    OUT.mkdir()
    plan=dict(frozen_at=now(),parent_git="95f797b",environment=environment(),old_source_folds=folded,
              rollback_reference={s:{"configuration":k,"archive":P31.relative_to(ROOT).as_posix(),
                                     "metrics":saved[s]["results"][k]["full"]} for s,k in BASELINES.items()},
              additions={"strawberry_only":[a["row_id"]],"rice_only":[b["row_id"]],
                         "both_frozen_encoder":[a["row_id"],b["row_id"]]},
              configurations={c["id"]:c for c in specs["cohorts"]["3E"]["configurations"] if c["id"] in (GPR,RF)},
              cases={"rice_only":[GPR,RF],"strawberry_only":[GPR,RF],"both_frozen_encoder":[GPR]},
              archived_combinations=MIXES,combination_weights=[0.5,0.5],planned_fits=135,
              bootstrap=BOOT,regression_anchor="A-NSC8",
              protected={p.relative_to(ROOT).as_posix():sha(p) for p in guards},
              scope="Matched old 33 3E rows, 27 whole-paper holdouts; no post hoc splitting or label edits. The encoder intervention learns scaling on the old training rows inside each fold.",
              promotion="Archive metrics and diagnostics are development evidence. Keep rollback reference until a later candidate improves matched sources and hard cases and can undergo untouched-source validation.",
              validation_references=[
                  "https://link.springer.com/article/10.1186/1471-2105-7-91",
                  "https://pmc.ncbi.nlm.nih.gov/articles/PMC2473869/",
              ])
    write(OUT/"training_plan.json",plan)


def checked():
    plan=read(OUT/"training_plan.json")
    path=(OUT/"training_plan.json").relative_to(ROOT).as_posix()
    git=["git","-c",f"safe.directory={ROOT.as_posix()}"]
    assert subprocess.check_output([*git,"show",f"HEAD:{path}"],cwd=ROOT)==(ROOT/path).read_bytes()
    assert plan["environment"]==environment()
    assert all(sha(ROOT/p)==h for p,h in plan["protected"].items())
    return plan


def frozen_encoder_gp(cfg,old,train,test,event):
    tr,te=([expressed(r,cfg,"six") for r in rows] for rows in (train,test))
    enc=Encoder().fit(tr[:len(old)])
    w=weights(train)
    delta=np.array([r["target"]-r["last_early"] for r in train])
    center=float(np.average(delta,weights=w))
    scale=float(np.sqrt(np.average((delta-center)**2,weights=w))) or 1.
    model=estimator(cfg)
    model.set_params(alpha=cfg["parameters"]["alpha"]/(w*len(train)))
    event["attempted"]=True
    model.fit(enc.transform(tr),(delta-center)/scale)
    forecast=model.predict(enc.transform(te))*scale+center+np.array([r["last_early"] for r in test])
    assert np.isfinite(forecast).all()
    return forecast.tolist()


def run():
    plan=checked()
    old={r["row_id"]:r for r in read(P31/"input_snapshot.json")["3E"]}
    new={r["row_id"]:r for r in read(P59/"input_snapshot.json")["3E"]}
    with (OUT/"run_claim.json").open("x",encoding="utf-8") as f:
        json.dump({"started_at":now(),"plan_sha256":sha(OUT/"training_plan.json")},f)
    events=[]
    for case,config_ids in plan["cases"].items():
        extra=[new[k] for k in plan["additions"][case]]
        for source,fold in plan["old_source_folds"].items():
            old_train=[old[k] for k in fold["train_ids"]]
            test=[old[k] for k in fold["test_ids"]]
            train=old_train+extra
            assert {r["source_family"] for r in test}=={source}
            assert source not in {r["source_family"] for r in train}
            assert not {r["curve_id"] for r in train}&{r["curve_id"] for r in test}
            for cfg_id in config_ids:
                event=dict(case=case,configuration=cfg_id,source=source,attempted=False)
                cfg=plan["configurations"][cfg_id]
                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter("always")
                    try:
                        if case=="both_frozen_encoder":
                            values=frozen_encoder_gp(cfg,old_train,train,test,event)
                        else:
                            values=fit(cfg,train,test,event)
                        event.update(status="complete",predictions=[
                            predicted("3E",cfg_id,r,y) for r,y in zip(test,values,strict=True)])
                    except Exception as exc:
                        event.update(status="failed",error=repr(exc))
                event["warnings"]=[str(w.message) for w in caught]
                events.append(event)
        print(f"{case}: {len(events)}/{plan['planned_fits']}",flush=True)
    assert len(events)==plan["planned_fits"]
    checked()
    write(OUT/"fit_events.json",events)


def summary(rows,reference=None):
    result={"rows":len(rows),"sources":len({r["source_family"] for r in rows}),"metrics":exact_score(rows)}
    if reference is not None:
        assert {r["row_id"]:(r["observed"],r["source_family"]) for r in rows}=={
            r["row_id"]:(r["observed"],r["source_family"]) for r in reference}
        result["paired_mae"]=paired_error(rows,reference,BOOT)
    for row in rows:
        if row["sample_name"]=="A-NSC8":
            result["ansc8_predicted"]=row["predicted"]
            result["ansc8_observed"]=row["observed"]
    return result


def verify():
    plan=checked()
    events=read(OUT/"fit_events.json")
    expected={(case,cfg,source) for case,cfgs in plan["cases"].items() for cfg in cfgs for source in plan["old_source_folds"]}
    assert {(e["case"],e["configuration"],e["source"]) for e in events}==expected
    assert len(events)==len(expected)==plan["planned_fits"]
    records=defaultdict(list)
    for e in events:
        if e["status"]=="complete":
            assert e["attempted"]
            assert {r["row_id"] for r in e["predictions"]}==set(plan["old_source_folds"][e["source"]]["test_ids"])
            records[e["case"],e["configuration"]].extend(e["predictions"])
    p31=read(P31/"heldout_predictions.json")
    p59=read(P59/"heldout_predictions.json")
    audit,models={},{}
    original={r["row_id"] for r in read(P1/"input_snapshot.json")["B_3E_early20"]}
    for method in (GPR,RF):
        ref=p31["3E"]["loso"][method]
        ids={r["row_id"] for r in ref}
        both=[r for r in p59["author:3E"]["configurations"][method] if r["row_id"] in ids]
        variants={"rollback_neither":ref,"existing_both":both}
        for case,configs in plan["cases"].items():
            if method in configs and len(records[case,method])==len(ref):
                variants[case]=records[case,method]
        audit[method]={key:dict(summary(v,ref),original13=summary([r for r in v if r["row_id"] in original]))
                       for key,v in variants.items()}
        models[method]=variants
    blends={}
    for phase in ("P31","P59"):
        for system,methods in plan["archived_combinations"].items():
            c=p31[system]["loso"] if phase=="P31" else p59[f"author:{system}"]["configurations"]
            left,right=(c[m] for m in methods)
            index={r["row_id"]:r for r in right}
            assert set(index)=={r["row_id"] for r in left}
            blend=[]
            for row in left:
                pair=index[row["row_id"]]
                assert (row["observed"],row["source_family"],row["curve_id"])==(pair["observed"],pair["source_family"],pair["curve_id"])
                value=sum(w*r["predicted"] for w,r in zip(plan["combination_weights"],(row,pair),strict=True))
                blend.append(dict(row,model="fixed_half_blend",predicted=value))
            key=f"{phase}:{system}"
            ref=c[BASELINES[system]]
            blends[key]=dict(members=methods,benchmark=summary(ref),blend=summary(blend,ref))
            models[key]=blend
    result=dict(status="rollback_development_benchmark_reinstated",
                fits=sum(e["attempted"] for e in events),failures=sum(e["status"]!="complete" for e in events),
                warnings=sum(len(e["warnings"]) for e in events),audit=audit,fixed_blends=blends,
                external_sources=0,goal_achieved=False)
    assert not (OUT/"results.json").exists()
    write(OUT/"results.json",result)
    write(OUT/"predictions.json",models)


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("step",choices=("freeze","run","verify"))
    {"freeze":freeze,"run":run,"verify":verify}[parser.parse_args().step]()
