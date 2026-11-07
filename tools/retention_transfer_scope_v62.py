"""Audit where the fixed retention blend transfers and verify the bounded source screen."""

from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.retention_blind_reserve_v22 import db_matches
from tools.retention_new_evidence_development_v59 import weights
from tools.retention_physical_scope_v61 import BASE, P1, P59, P60, OUT as P61, GPR, RF, blend, exact_score, inside, read, sha, write
from tools.retention_wood_archive_v49 import frozen

OUT=BASE/"第六十二轮_原组合转移诊断与新来源核查_20261108"
CACHE=ROOT/".local-literature-cache/P62"
FREEZE="af42a8f"


def score(rows):
    return dict(rows=len(rows),sources=len({r["source_family"] for r in rows}),metrics=exact_score(rows))


def transfer():
    old=read(P1/"input_snapshot.json")["B_3E_early20"]
    ids={r["row_id"] for r in old}
    inputs={r["row_id"]:r for r in read(P59/"input_snapshot.json")["3E"]}
    a=read(P60/"predictions.json")
    pred=blend(a[GPR]["strawberry_only"],a[RF]["strawberry_only"],"P60_half_GPR_RF")
    core=[r for r in pred if r["row_id"] in ids]
    extra=[r for r in pred if r["row_id"] not in ids]
    assert (len(core),len(extra))==(13,20)
    archived=read(P61/"original13_predictions.json")
    assert core==archived
    assert not {r["source_family"] for r in core}&{r["source_family"] for r in extra}
    assert all(r["observed"]==inputs[r["row_id"]]["target"] for r in pred)
    terms=[]
    for r,w in zip(extra,weights(extra),strict=True):
        f=inputs[r["row_id"]]["features"]
        error=r["predicted"]-r["observed"]
        terms.append(dict(row_id=r["row_id"],sample_name=r["sample_name"],source=r["source_family"],
                          observed=r["observed"],predicted=r["predicted"],signed_error_pp=error,
                          feature_values=f,static_conditions=inputs[r["row_id"]]["static_features"],
                          source_weighted_squared_error=float(w)*error**2,
                          early_linear_pct=f["last_early_retention_pct"]+f["early_retention_slope_per_1000_cycles"]*
                            (f["target_cycle_count"]-f["early_observed_cycle_count"])/1000.))
    denom=sum(r["source_weighted_squared_error"] for r in terms)
    for r in terms:
        r["fraction_of_other20_weighted_square_error"]=r["source_weighted_squared_error"]/denom
    terms.sort(key=lambda x:-x["source_weighted_squared_error"])
    scopes=frozen(P61/"training_plan.json","ebe5032")["scopes"]
    scope_scores={name:score([r for r in pred if inside(inputs[r["row_id"]],spec["rules"])])
                  for name,spec in scopes.items()}
    assert terms[0]["sample_name"]=="JPC-800-0.5"
    first=inputs[terms[0]["row_id"]]
    assert all(inside(first,spec["rules"]) for spec in scopes.values())
    return dict(original13=score(core),other20=score(extra),all33=score(pred),
                fixed_combination_under_predeclared_scope=scope_scores,other20_error_terms=terms,
                all_sources_known_development=True,independent_acceptance=0)


def source_audit(plan):
    known=read(CACHE/"history.json")
    recent=read(CACHE/"recent_lite.json")
    fixed=read(CACHE/"fixed_candidates.json")
    assert [(r["pmcid"],r["doi"]) for r in fixed]==[(r["pmcid"],r["doi"]) for r in plan["fixed_primary_candidates"]]
    assert all(r["tracked_paths"] for r in known)
    assert all(r["tracked_matches"] for r in fixed)
    current=db_matches({r["doi"] for r in known+fixed})
    assert all(current[r["doi"]]==r["catalog"] for r in known+fixed)
    record=read(CACHE/"rsc_structure.json")
    xml=CACHE/"PMC13618356.sealed.xml"
    assert sha(xml)==record["sha256"]
    assert len(record["cycle_caption_flags"])==1
    assert {"CNT","TiO2","cycle"}<=set(record["cycle_caption_flags"][0]["flags"])
    assert "controls" not in record["cycle_caption_flags"][0]["flags"]
    history=read(CACHE/"rsc_history_roles.json")
    assert len(history)==9 and all(not h["abstract_terminal_risk"] for h in history)
    public_checks=[read(CACHE/"rsc_supplement_receipt.json"),*read(CACHE/"rsc_supplement_alt.json")]
    assert not any(r.get("is_pdf") for r in public_checks)
    return dict(recent_metadata=dict(query=recent["query"],api_hit_count=recent["hit_count"],
                                      unique_doi_with_pmc_count=len({r["doi"] for r in recent["rows"]})),
                preselected_known_screen=[dict(doi=r["doi"],pmcid=r["pmcid"],tracked_paths=len(r["tracked_paths"]),
                                               catalog=r["catalog"]) for r in known],
                fixed_candidates=fixed,rsc_structure=record,rsc_abstract_screen=history,
                supplement_attempts=public_checks,
                decisions={"10.1016/j.ultsonch.2026.108104":"prior full text and audit in AC700 project files; development only",
                           "10.1039/d6ra08646b":"known bibliographic source, composite cycle figure, no linked bare-carbon long-cycle series; supplement unavailable"},
                fit_ready_new_sources=0,locked_predictions=0,formal_external_acceptance=0)


def audit():
    plan=frozen(OUT/"screen_plan.json",FREEZE)
    assert all(sha(ROOT/p)==h for p,h in plan["protected"].items())
    return dict(phase=62,freeze_commit=FREEZE,protected_files_checked=len(plan["protected"]),
                transfer=transfer(),source_screen=source_audit(plan),new_fits=0,scope_promoted=False)


if __name__=="__main__":
    assert not (OUT/"evidence.json").exists()
    write(OUT/"evidence.json",audit())
