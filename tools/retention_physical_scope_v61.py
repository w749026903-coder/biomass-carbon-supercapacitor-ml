"""Check whether predeclared aqueous-KOH scopes improve 3E retention prediction."""

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
    BASE, P31, OUT as P59, BASELINES, environment, exact_score, fit, fold_data, gates,
    now, predicted, read, sha, weights, write,
)
from tools.retention_rollback_regression_v60 import P1, OUT as P60, RF, GPR, XGB

OUT=BASE/"第六十一轮_物理适用范围与原十三条_20261108"
RF_STATIC="RF_static_p2_raw_delta"
SCOPES={
    "koh_1_to_6m_1000_to_10000": {"concentration_min":1,"concentration_max":6,"cycles_min":1000,"cycles_max":10000},
    "koh_6m_5000_to_10000": {"concentration_min":6,"concentration_max":6,"cycles_min":5000,"cycles_max":10000},
}
MIXES={"half_GPR_RF":[GPR,RF],"half_RF_XGB":[RF,XGB]}


def inside(row,scope):
    static=row["static_features"]
    concentration=static["concentration_mol_L"]
    return (static["electrolyte"]=="KOH" and concentration is not None
            and scope["concentration_min"]<=concentration<=scope["concentration_max"]
            and scope["cycles_min"]<=row["features"]["target_cycle_count"]<=scope["cycles_max"])


def freeze():
    assert not OUT.exists()
    pool=read(P59/"input_snapshot.json")["3E"]
    prior=read(P59/"training_plan.json")
    assert prior["environment"]==environment()
    configs=[c for c in prior["cohorts"]["3E"]["configurations"] if c["id"] in (GPR,RF,XGB,RF_STATIC)]
    assert len(configs)==4
    cohorts={}
    for name,scope in SCOPES.items():
        selected=[r for r in pool if inside(r,scope)]
        sources=sorted({r["source_family"] for r in selected})
        assert len(sources)>=10
        folds={s:{"train":[r["row_id"] for r in selected if r["source_family"]!=s],
                  "test":[r["row_id"] for r in selected if r["source_family"]==s]} for s in sources}
        cohorts[name]={"rules":scope,"rows":[r["row_id"] for r in selected],"folds":folds,
                       "out_of_scope_rows":[r["row_id"] for r in pool if not inside(r,scope)]}
    files=[Path(__file__),BASE/"research_goal.json",ROOT/"data/current_retention_model_benchmarks.json",
           P1/"input_snapshot.json",P1/"heldout_predictions.json",P31/"heldout_predictions.json",
           P59/"training_plan.json",P59/"input_snapshot.json",P59/"heldout_predictions.json",P60/"predictions.json"]
    files.extend(ROOT/"tools"/f"{n}.py" for n in (
        "retention_new_evidence_development_v59","retention_sawdust_verify_v31","retention_shape_v4",
        "retention_horizon_normalization_v19","run_small_sample_routes","retention_v3_optimizer"))
    OUT.mkdir()
    write(OUT/"training_plan.json",dict(frozen_at=now(),parent_git="e017c27",environment=environment(),
          model_contract="Three electrodes, reported cycling, original early20 inputs and retention output.",
          scopes=cohorts,configurations=configs,fixed_mixtures=MIXES,
          original13_comparison="Unchanged historical rows only; compare existing predictions and one fixed equal GPR + RF mix.",
          criteria=prior["criteria"],minimum_development_sources=10,formal_independent_sources=0,
          planned_fits=4*sum(len(c["folds"]) for c in cohorts.values()),
          promotion="Require all numerical gates and sufficient source coverage before proposing scope. Scope stays exploratory and cannot substitute for independent evaluation.",
          protected={p.relative_to(ROOT).as_posix():sha(p) for p in files}))


def checked():
    path=OUT/"training_plan.json"
    spec=path.relative_to(ROOT).as_posix()
    git=["git","-c",f"safe.directory={ROOT.as_posix()}"]
    assert subprocess.check_output([*git,"show",f"HEAD:{spec}"],cwd=ROOT)==path.read_bytes()
    plan=read(path)
    assert environment()==plan["environment"]
    assert all(sha(ROOT/p)==h for p,h in plan["protected"].items())
    return plan


def run():
    plan=checked()
    pool=read(P59/"input_snapshot.json")["3E"]
    with (OUT/"run_claim.json").open("x",encoding="utf-8") as claim:
        json.dump(dict(started_at=now(),plan_sha256=sha(OUT/"training_plan.json")),claim)
    records=[]
    for name,spec in plan["scopes"].items():
        rows=[r for r in pool if inside(r,spec["rules"])]
        assert [r["row_id"] for r in rows]==spec["rows"]
        for source,split in spec["folds"].items():
            train,test=fold_data(rows,source,split)
            for cfg in plan["configurations"]:
                event=dict(scope=name,source=source,configuration=cfg["id"],attempted=False)
                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter("always")
                    try:
                        values=fit(cfg,train,test,event)
                        event.update(status="complete",predictions=[predicted("3E",cfg["id"],r,y)
                                     for r,y in zip(test,values,strict=True)])
                    except Exception as exc:
                        event.update(status="failed",error=repr(exc))
                event["warnings"]=[str(w.message) for w in caught]
                records.append(event)
        print(f"{name}: {len(records)}/{plan['planned_fits']}",flush=True)
    assert len(records)==plan["planned_fits"]
    write(OUT/"fit_events.json",records)


def blend(left,right,label):
    peer={r["row_id"]:r for r in right}
    assert set(peer)=={r["row_id"] for r in left}
    records=[]
    for r in left:
        other=peer[r["row_id"]]
        assert all(r[k]==other[k] for k in ("observed","source_family","curve_id"))
        records.append(dict(r,model=label,predicted=.5*r["predicted"]+.5*other["predicted"]))
    return records


def baselines(rows,folds):
    results=defaultdict(list)
    for source,split in folds.items():
        train,test=fold_data(rows,source,split)
        center=float(np.average([r["target"] for r in train],weights=weights(train)))
        for r in test:
            f=r["features"]
            linear=r["last_early"]+f["early_retention_slope_per_1000_cycles"]*(f["target_cycle_count"]-f["early_observed_cycle_count"])/1000.
            for name,y in zip(BASELINES,(center,r["last_early"],linear),strict=True):
                results[name].append(predicted("3E",name,r,y))
    return dict(results)


def old_panel():
    old=read(P1/"input_snapshot.json")["B_3E_early20"]
    ids={r["row_id"] for r in old}
    p1=[r for r in read(P1/"heldout_predictions.json")
        if r["route"]=="B_3E_early20" and r["model"]=="fixed::"+GPR]
    p31=read(P31/"heldout_predictions.json")["3E"]["loso"][GPR]
    p60=read(P60/"predictions.json")
    only_straw=p60[GPR]["strawberry_only"]
    mix=blend(only_straw,p60[RF]["strawberry_only"],"P60_half_GPR_RF")
    result={}
    for name,group in (("P1_GPR",p1),("P31_GPR",p31),("P60_strawberry_GPR",only_straw),("P60_half_GPR_RF",mix)):
        selected=[r for r in group if r["row_id"] in ids]
        assert {r["row_id"]:(r["observed"],r["source_family"],r["curve_id"]) for r in selected}=={
            r["row_id"]:(r["target"],r["source_family"],r["curve_id"]) for r in old}
        result[name]=exact_score(selected)
    return result


def verify():
    plan=checked()
    events=read(OUT/"fit_events.json")
    expected={(n,s,c["id"]) for n,cohort in plan["scopes"].items()
              for s in cohort["folds"] for c in plan["configurations"]}
    assert len(expected)==len(events)==plan["planned_fits"]
    for e in events:
        expected.remove((e["scope"],e["source"],e["configuration"]))
    assert not expected
    pool=read(P59/"input_snapshot.json")["3E"]
    archived=read(P59/"heldout_predictions.json")["author:3E"]["configurations"]
    all_cases,predictions={},{}

    for name,spec in plan["scopes"].items():
        rows=[r for r in pool if inside(r,spec["rules"])]
        methods=defaultdict(list)
        for e in events:
            if e["scope"]!=name or e["status"]!="complete":
                continue
            ids={r["row_id"] for r in e["predictions"]}
            assert ids==set(spec["folds"][e["source"]]["test"])
            methods[e["configuration"]].extend(e["predictions"])
        for mix,(left,right) in plan["fixed_mixtures"].items():
            if len(methods[left])==len(methods[right])==len(rows):
                methods[mix]=blend(methods[left],methods[right],mix)
        simple=baselines(rows,spec["folds"])
        bs={name:exact_score(p) for name,p in simple.items()}
        details={}
        endpoints={r["row_id"]:r["target"] for r in rows}
        for cfg,preds in methods.items():
            if len(preds)!=len(rows):
                details[cfg]=dict(complete=False,numeric_pass=False)
                continue
            assert {r["row_id"]:r["observed"] for r in preds}==endpoints
            metrics=exact_score(preds)
            flags=gates(preds,metrics,bs,plan["criteria"],len(rows))
            ref=[r for r in archived.get(cfg,[]) if r["row_id"] in endpoints]
            if ref:
                assert {r["row_id"]:r["observed"] for r in ref}==endpoints
            details[cfg]={"complete":True,"metrics":metrics,"gates":flags,"numeric_pass":all(flags.values()),
                          "wider_training_same_test_rows":exact_score(ref) if ref else None}
        all_cases[name]={"rows":len(rows),"sources":len(spec["folds"]),"out_of_scope_rows":len(spec["out_of_scope_rows"]),
                         "author_retention_sd_pp":float(np.sqrt(np.average(
                             (np.array(list(endpoints.values()))-np.average(list(endpoints.values()),weights=weights(rows)))**2,
                             weights=weights(rows)))),
                         "reference_baselines":bs,"models":details,"numeric_passes":sum(d["numeric_pass"] for d in details.values())}
        predictions[name]={"methods":dict(methods),"simple_baselines":simple}
    assert not (OUT/"results.json").exists()
    write(OUT/"results.json",dict(status="exploratory_physical_scope",old13=old_panel(),scopes=all_cases,
         fits=sum(e["attempted"] for e in events),failures=sum(e["status"]!="complete" for e in events),
         warnings=sum(len(e["warnings"]) for e in events),formal_external_sources=0,scope_promoted=False))
    write(OUT/"heldout_predictions.json",predictions)


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("step",choices=("freeze","run","verify"))
    {"freeze":freeze,"run":run,"verify":verify}[parser.parse_args().step]()
