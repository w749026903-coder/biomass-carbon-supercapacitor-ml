"""Compare candidate held-out predictions on the exact rollback benchmark cohort."""

import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.retention_horizon_normalization_v19 import paired_error
from tools.retention_sawdust_verify_v31 import exact_score
from tools.retention_shape_v4 import read, sha

POINTER=ROOT/"data/current_retention_model_benchmarks.json"
METRICS=("r2","mae","rmse","p90_absolute_error","source_p90_mae")


def follow(data,keys):
    for key in keys:
        data=data[key]
    return data


def by_id(rows):
    index={r["row_id"]:r for r in rows}
    if len(index)!=len(rows):
        raise ValueError("duplicate prediction row")
    return index


def compare(system,candidate):
    pointer=read(POINTER)
    expected=pointer["predictions"]
    path=ROOT/expected["path"]
    if sha(path)!=expected["sha256"]:
        raise ValueError("rollback prediction archive hash mismatch")
    ref=by_id(follow(read(path),pointer["reference_by_system"][system]["archived_prediction_keys"]))
    current=by_id(candidate)
    if not ref.keys()<=current.keys():
        raise ValueError(f"missing reference rows: {sorted(ref.keys()-current.keys())}")
    matched=[current[k] for k in ref]
    for k,old in ref.items():
        new=current[k]
        if any(old[field]!=new[field] for field in ("observed","source_family","curve_id")):
            raise ValueError(f"target or source identity changed for {k}")
    before=exact_score(list(ref.values()))
    after=exact_score(matched)
    diff={metric:after[metric]-before[metric] for metric in METRICS}
    regressions=[metric for metric,v in diff.items() if (v < -1e-9 if metric=="r2" else v > 1e-9)]
    paired=paired_error(matched,list(ref.values()),{"seed":20261107,"draws":10000,"interval":[.025,.975]})
    per_row=[dict(row_id=k,source_family=old["source_family"],sample_name=old["sample_name"],
                  benchmark=old["predicted"],candidate=current[k]["predicted"],observed=old["observed"],
                  change_in_absolute_error_pp=abs(current[k]["predicted"]-old["observed"])-abs(old["predicted"]-old["observed"]))
             for k,old in ref.items()]
    return dict(system=system,matched_rows=len(ref),candidate_extra_rows=len(current)-len(ref),
                benchmark_metrics=before,candidate_matched_metrics=after,delta=diff,regressed_metrics=regressions,
                matched_point_metrics_non_regressing=not regressions,paired_common_mae=paired,
                most_regressed_rows=sorted(per_row,key=lambda r:(-r["change_in_absolute_error_pp"],r["row_id"]))[:5],
                interpretation="Development regression screen. Prediction records alone cannot verify training isolation or external acceptance.")


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("predictions",type=Path)
    parser.add_argument("--system",choices=("3E","2E"),required=True)
    parser.add_argument("--key",action="append",default=[],help="A nested JSON key; repeat from outer to inner.")
    args=parser.parse_args()
    output=compare(args.system,follow(read(args.predictions),args.key))
    print(json.dumps(output,indent=2,ensure_ascii=False,allow_nan=False))


if __name__=="__main__":
    main()
