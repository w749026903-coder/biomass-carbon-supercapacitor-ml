"""Evaluate fixed prediction-time scope rules without excluding any in-scope outcomes."""

import argparse
from collections import defaultdict
import json
from pathlib import Path
import subprocess
import sys
import warnings

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.retention_new_evidence_development_v59 import environment, exact_score, fit, fold_data, gates, now, predicted, read, sha, write
from tools.retention_physical_scope_v61 import BASE, P59, OUT as P61, GPR, RF, baselines, blend
from tools.retention_decline_guard_v63 import OUT as P63
from tools.retention_rollback_regression_v60 import BOOT, paired_error

OUT=BASE/"第六十四轮_三电极温和早期适用范围_20261108"
SCOPES={
    "koh_1_to_6m_mild_early":{"mol_L_min":1.,"mol_L_max":6.,"A_g_min":1.,"A_g_max":10.},
    "koh_6m_mild_early":{"mol_L_min":6.,"mol_L_max":6.,"A_g_min":3.,"A_g_max":10.},
}
CYCLES=(1000,10000)
LIMIT_PP=10.


def outside_reasons(row,scope):
    s=row["static_features"]
    f=row["features"]
    current=s["reported_current_A_g"]
    electrolyte=s["concentration_mol_L"]
    early_delta=f["early_retention_slope_per_1000_cycles"]*f["early_observed_cycle_count"]/1000.
    tests={
        "electrolyte_and_concentration":s["electrolyte"]=="KOH" and electrolyte is not None
           and scope["mol_L_min"]<=electrolyte<=scope["mol_L_max"],
        "reported_cycle_current_A_g":current is not None and scope["A_g_min"]<=current<=scope["A_g_max"],
        "target_cycle_range":CYCLES[0]<=f["target_cycle_count"]<=CYCLES[1],
        "early_window":0<f["early_observed_cycle_count"]<=.20*f["target_cycle_count"],
        "early_amplitude":0<=f["early_retention_range_pp"]<LIMIT_PP,
        "fitted_early_change":abs(early_delta)<LIMIT_PP,
    }
    return [rule for rule,value in tests.items() if not value]


def freeze():
    assert not OUT.exists()
    pool=read(P59/"input_snapshot.json")["3E"]
    src=read(P59/"training_plan.json")
    assert src["environment"]==environment()
    choices=[c for c in src["cohorts"]["3E"]["configurations"] if c["id"] in (GPR,RF)]
    assert len(choices)==2
    scopes={}
    for name,rule in SCOPES.items():
        cohort=[r for r in pool if not outside_reasons(r,rule)]
        sources=sorted({r["source_family"] for r in cohort})
        scopes[name]=dict(rules=rule,
             folds={s:{"train":[r["row_id"] for r in cohort if r["source_family"]!=s],
                       "test":[r["row_id"] for r in cohort if r["source_family"]==s]} for s in sources},
             included=[r["row_id"] for r in cohort],
             excluded={r["row_id"]:outside_reasons(r,rule) for r in pool if outside_reasons(r,rule)})
    files=[Path(__file__),BASE/"research_goal.json",P59/"input_snapshot.json",P59/"training_plan.json",
           P59/"heldout_predictions.json",P61/"original13_scorecard.json",P61/"original13_predictions.json",
           P63/"training_plan.json",ROOT/"data/current_retention_scope_scorecard.json"]
    files.extend(ROOT/"tools"/f"{name}.py" for name in (
        "retention_new_evidence_development_v59","retention_physical_scope_v61","retention_shape_v4",
        "retention_v3_optimizer","run_small_sample_routes"))
    OUT.mkdir()
    write(OUT/"training_plan.json",dict(frozen_at=now(),parent_git="4085dc2",environment=environment(),
       input="3E, original six early20 summaries; the chemistry, cycle current and range gate are known before prediction",
       output="author capacitance retention pct at declared cycle count",
       cycle_limits=CYCLES,early_magnitude_limit_pp=LIMIT_PP,scopes=scopes,configurations=choices,
       equal_ensemble=[GPR,RF],planned_fits=2*sum(len(c["folds"]) for c in scopes.values()),
       criteria=src["criteria"],source_minimum=10,minimum_external_sources_for_acceptance="unseen-source validation required",
       promotion="Compare the frozen equal ensemble against its wider-fit equivalent on the same test rows. Numeric and formal gates are separate; out-of-scope labels stay in the ledger. Original 13 is a separate historical benchmark.",
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
    with (OUT/"run_claim.json").open("x",encoding="utf-8") as f:
        json.dump(dict(started_at=now(),plan_sha256=sha(OUT/"training_plan.json")),f)
    events=[]
    for name,spec in plan["scopes"].items():
        rows=[r for r in pool if not outside_reasons(r,spec["rules"])]
        assert [r["row_id"] for r in rows]==spec["included"]
        for source,split in spec["folds"].items():
            train,test=fold_data(rows,source,split)
            for cfg in plan["configurations"]:
                e=dict(scope=name,source=source,model=cfg["id"],attempted=False)
                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter("always")
                    try:
                        y=fit(cfg,train,test,e)
                        e.update(status="complete",predictions=[predicted("3E",cfg["id"],r,v) for r,v in zip(test,y,strict=True)])
                    except Exception as exc:
                        e.update(status="failed",error=repr(exc))
                e["warnings"]=[str(w.message) for w in caught]
                events.append(e)
        print(f"{name}: {len(events)}/{plan['planned_fits']}",flush=True)
    assert len(events)==plan["planned_fits"]
    write(OUT/"fit_events.json",events)


def verification():
    plan=checked()
    pool=read(P59/"input_snapshot.json")["3E"]
    old13={r["row_id"] for r in read(P61/"original13_predictions.json")}
    wide=read(P59/"heldout_predictions.json")["author:3E"]["configurations"]
    wide_mix=blend(wide[GPR],wide[RF],"P59_half_GPR_RF")
    events=read(OUT/"fit_events.json")
    expected={(s,h,c["id"]) for s,d in plan["scopes"].items() for h in d["folds"] for c in plan["configurations"]}
    assert len(expected)==len(events)==plan["planned_fits"]
    for e in events:
        expected.remove((e["scope"],e["source"],e["model"]))
    assert not expected
    results,all_predictions={},{}
    for name,spec in plan["scopes"].items():
        rows=[r for r in pool if not outside_reasons(r,spec["rules"])]
        by={r["row_id"]:r for r in rows}
        assert list(by)==spec["included"] and len(by)+len(spec["excluded"])==len(pool)
        methods=defaultdict(list)
        for e in events:
            if e["scope"]==name and e["status"]=="complete":
                assert set(spec["folds"][e["source"]]["test"])=={r["row_id"] for r in e["predictions"]}
                methods[e["model"]].extend(e["predictions"])
        if len(methods[GPR])==len(methods[RF])==len(rows):
            methods["half_GPR_RF"]=blend(methods[GPR],methods[RF],"half_GPR_RF")
        standard=baselines(rows,spec["folds"])
        bs={k:exact_score(v) for k,v in standard.items()}
        comparison={}
        for model,preds in methods.items():
            if len(preds)!=len(rows):
                comparison[model]=dict(complete=False,numeric_pass=False)
                continue
            assert {r["row_id"]:r["observed"] for r in preds}=={r["row_id"]:r["target"] for r in rows}
            ref=[r for r in (wide_mix if model=="half_GPR_RF" else wide[model]) if r["row_id"] in by]
            assert {r["row_id"]:r["observed"] for r in ref}=={r["row_id"]:r["observed"] for r in preds}
            m=exact_score(preds)
            flags=gates(preds,m,bs,plan["criteria"],len(rows))
            comparison[model]=dict(complete=True,metrics=m,gates=flags,numeric_pass=all(flags.values()),
                                   wider_on_same_rows=exact_score(ref),paired_mae=paired_error(preds,ref,BOOT))
        excluded=[dict(row_id=r["row_id"],sample_name=r["sample_name"],source=r["source_family"],
                       reasons=spec["excluded"][r["row_id"]])
                  for r in pool if r["row_id"] in spec["excluded"]]
        results[name]=dict(rows=len(rows),sources=len(spec["folds"]),old13_membership=len(old13&by.keys()),
                           pool_rows=len(pool),scope_coverage=len(rows)/len(pool),excluded=excluded,
                           minimum_source_count_gate=len(spec["folds"])>=plan["source_minimum"],models=comparison)
        all_predictions[name]=dict(methods=dict(methods),baselines=standard)
    write(OUT/"results.json",dict(status="predeclared_applicability_pilot",scopes=results,
          new_fits=sum(e["attempted"] for e in events),failures=sum(e["status"]!="complete" for e in events),
          warnings=sum(len(e["warnings"]) for e in events),formal_external_sources=0,formal_acceptance=False))
    write(OUT/"predictions.json",all_predictions)


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("step",choices=("freeze","run","verify"))
    {"freeze":freeze,"run":run,"verify":verification}[parser.parse_args().step]()
