"""Measure how much each held-out paper influences the P68 scope scores."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.retention_scope_screen_v68 import BASE, OUT as P68, exact_score, read, sha, write

OUT = BASE / "第六十九轮_范围稳健性与活化工艺核查_20261116"


def paired_scope(candidate, baseline):
    fields = ("source_family", "curve_id", "observed")
    identities = lambda rows: {r["row_id"]: tuple(r[f] for f in fields) for r in rows}
    assert len(candidate) == len(baseline) == len(identities(candidate))
    assert identities(candidate) == identities(baseline)
    full = exact_score(candidate)
    full_control = exact_score(baseline)
    cases = {}
    for source in sorted({row["source_family"] for row in candidate}):
        keep = lambda rows: [row for row in rows if row["source_family"] != source]
        after = exact_score(keep(candidate))
        control = exact_score(keep(baseline))
        cases[source] = dict(candidate=after, control=control, delta_mae_pp=after["mae"]-control["mae"])
    bands = {
        key: [min(case["candidate"][key] for case in cases.values()),
              max(case["candidate"][key] for case in cases.values())]
        for key in ("mae", "r2", "rmse")
    }
    limiting_source = min(cases, key=lambda source:cases[source]["candidate"]["r2"])
    variance = full["rmse"]**2 / (1 - full["r2"])
    return dict(
        rows=len(candidate), sources=len(cases), full=full, baseline=full_control,
        sensitivity_bands=bands, limiting_source_by_r2=limiting_source,
        mae_improved_without_each_source=sum(case["delta_mae_pp"] < 0 for case in cases.values()),
        required_rmse_exclusive_at_r2_gt_095_pp=(.05 * variance)**.5, omissions=cases,
    )


def audit():
    files = [P68 / name for name in ("scope_routing_diagnostic.json", "predictions.json", "training_plan.json")]
    routed, matched, plan = map(read, files)
    assert routed["scope_plan_sha256"] == sha(files[2])
    result = {}
    for name, scope in plan["scopes"].items():
        candidate = routed["scopes"][name]["predictions"]
        baseline = matched[name]["current_matched"]
        assert {r["row_id"] for r in candidate} == set(scope["rows"])
        result[name] = paired_scope(candidate, baseline)
        assert result[name]["full"] == routed["scopes"][name]["metrics"]
    return dict(
        purpose="Scoring sensitivity with predictions held fixed, one whole source omitted at a time.",
        new_fits=0, new_external_sources=0, formal_acceptance=False,
        source_files={p.relative_to(ROOT).as_posix():sha(p) for p in files},
        scopes=result,
    )


if __name__ == "__main__":
    result = audit()
    OUT.mkdir(exist_ok=True)
    write(OUT / "scope_robustness.json", result)
    for name, scope in result["scopes"].items():
        print(name, scope["mae_improved_without_each_source"], scope["sources"],
              scope["sensitivity_bands"]["r2"], scope["required_rmse_exclusive_at_r2_gt_095_pp"])
