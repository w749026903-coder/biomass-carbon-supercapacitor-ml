"""Export early-only authors' cycling data and bind the three masked Fig. 8 traces."""

from decimal import Decimal
from hashlib import md5
from itertools import islice, product
import csv
import io
import json
import math
from pathlib import Path
import re
import sys
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.retention_wood_archive_v49 import BASE, frozen, protocol, read, sha

OUT = BASE / "第五十七轮_木源碳数据包与归一化证据_20261107"
CACHE = ROOT / ".local-literature-cache/P57"
JATS = ROOT / ".local-literature-cache/P49/wood_epmc.xml"
ARCHIVE = CACHE / "wood_v2_archive_sealed.zip"
P50 = BASE / "第五十轮_木源碳双电极早期盲态图读_20261107"
FREEZE = "89e8a21"
ARCHIVE_MD5 = "c57733a0acc2f1f5db6c2ed9a62b8c47"
ARCHIVE_SHA = "92c825237e3a529c73ddcd08c661cace2100ae88caeca835aea85795e951d63a"
CYCLES = tuple(range(100, 2001, 100))
SAMPLES = ("YP-80F", "AWC 3-800", "AWC 2-600", "AWC 3-600", "AWC 4-700")
PANELS = {"a": "NaCl", "b": "KxHyPO4"}
FAMILY = "provisional:10.1002/smsc.202500540+10.1016/j.cartre.2024.100436"


def read_early(rows):
    labels, formulas = next(rows), next(rows)
    assert labels == ["", "A", *SAMPLES] and formulas[:2] == ["F(x)=", ""]
    for column, formula in zip("BCDEF", formulas[2:], strict=True):
        assert re.fullmatch(rf"\({column}/\d+(?:\.\d+)?\)\*100", formula)
    early = {}
    for expected, row in zip(CYCLES, islice(rows, len(CYCLES)), strict=True):
        assert len(row) == 7 and Decimal(row[1]) == expected
        for value in row[2:]:
            assert Decimal(value).is_finite() and Decimal(value) > 0
        early[expected] = row[2:]
    assert all(Decimal(v) == 100 for v in early[100])
    return dict(zip(SAMPLES, formulas[2:], strict=True)), early


def scored_matches(points, rows):
    points = sorted(points, key=lambda item: item["cycle_geometry_estimate"])
    choices = [[cycle for cycle in rows if pt["cycle_geometry_range"][0] <= cycle <= pt["cycle_geometry_range"][1]]
               for pt in points]
    alignments = [cycles for cycles in product(*choices) if list(cycles) == sorted(set(cycles))]
    assert alignments
    comparison = {}
    for col, sample in enumerate(SAMPLES):
        def score(cycles):
            observed = [float(rows[cycle][col]) for cycle in cycles]
            hits = sum(pt["cr_plot_pct_geometry_range"][0] <= y <= pt["cr_plot_pct_geometry_range"][1]
                       for pt, y in zip(points, observed, strict=True))
            rmse = math.sqrt(sum((pt["cr_plot_pct_geometry_estimate"] - y) ** 2
                                 for pt, y in zip(points, observed, strict=True)) / len(points))
            return -hits, rmse, cycles
        hits, rmse, cycles = min(score(cycles) for cycles in alignments)
        comparison[sample] = {"points_in_interval": -hits, "rmse_pp": round(rmse, 6), "aligned_cycles": cycles}
    selected, = [sample for sample, score in comparison.items() if score["points_in_interval"] == len(points)]
    return {"sample": selected, "required_interval_matches": len(points), "column_comparisons": comparison,
            "distinct_monotonic_alignments_checked": len(alignments)}


def receipts():
    access = read(CACHE / "access.json")
    range_trial = read(CACHE / "range_followup.json")
    sources = {}
    for i, label in ((0, "record"), (2, "files")):
        path = CACHE / f"{label}.json"
        entry = access["attempts"][i]
        assert entry["http"] == 200 and sha(path) == entry["sha256"]
        sources[label] = read(path)
    assert sources["record"]["doi"] == "10.5281/zenodo.19549171"
    meta = sources["record"]["metadata"]
    assert meta["license"]["id"] == "cc-by-4.0"
    item, = (item for item in sources["files"]["entries"] if item["key"] == "Small Science Paper.zip")
    assert item["checksum"] == f"md5:{ARCHIVE_MD5}" and item["links"]["content"] == range_trial["url"]
    assert range_trial["http"] == 206 and range_trial["verified_archive"]
    assert ARCHIVE.stat().st_size == item["size"] == range_trial["bytes"] == 994338
    assert sha(ARCHIVE) == range_trial["sha256"] == ARCHIVE_SHA
    assert md5(ARCHIVE.read_bytes()).hexdigest() == ARCHIVE_MD5
    return {"api_access": access["attempts"], "verified_range_download": range_trial,
            "archive_md5": ARCHIVE_MD5, "archive_sha256": ARCHIVE_SHA,
            "license": meta["license"]["id"], "dataset_creators": [c["name"] for c in meta["creators"]]}


def audit():
    plan_path = OUT / "screen_plan.json"
    plan = frozen(plan_path, FREEZE)
    assert all(sha(ROOT / path) == value for path, value in plan["protected"].items())
    assert sha(JATS) == plan["sealed_jats_sha256"]
    trial = protocol(JATS)
    assert trial["long_cycle_protocol"] == {
        "current_mA_absolute": 10, "mass_normalized_current_A_g_verified": None,
        "upper_voltage_V": 1.2, "cycle_count": 10000, "author_stated_record_interval_cycles": 100}
    access = receipts()
    original = read(P50 / "evidence.json")
    assert not original["endpoint_exposed"] and original["source_lineage"] == 1
    evidence, inputs = {}, {}
    with ZipFile(ARCHIVE) as archive:
        for panel, electrolyte in PANELS.items():
            member, = [item for item in archive.infolist()
                       if item.filename.endswith(f"Book1.Long-term cycling ({electrolyte}).csv")]
            with archive.open(member) as raw:
                rows = csv.reader(io.TextIOWrapper(raw, encoding="utf-8-sig", newline=""))
                formulas, values = read_early(rows)
            tracks = {color: scored_matches(track["points"], values)
                      for color, track in original["panels"][panel]["unbound_tracks"].items()}
            evidence[panel] = {"electrolyte_label": electrolyte, "member": member.filename,
                               "member_zip_crc32": f"{member.CRC:08x}", "member_byte_size": member.file_size,
                               "sample_formulas_as_reported": formulas, "first_observation_cycle": 100,
                               "all_first_retention_values_exactly_100_pct": True, "figure_trace_links": tracks}
            inputs[panel] = {
                "electrolyte_label": electrolyte, "cycles": CYCLES,
                "all_source_columns": {sample: {
                    "archived_retention_pct_text": [row[index] for row in values.values()],
                    "matched_figure_trace": next((color for color, match in tracks.items()
                                                 if match["sample"] == sample), None),
                } for index, sample in enumerate(SAMPLES)},
            }
    assert evidence["a"]["figure_trace_links"]["red"]["sample"] == "AWC 3-600"
    assert {color: match["sample"] for color, match in evidence["b"]["figure_trace_links"].items()} == {
        "red": "AWC 3-600", "blue": "AWC 3-800"}
    info = {
        "phase": 57, "freeze_commit": FREEZE, "plan_sha256": sha(plan_path),
        "protected_hashes_checked": len(plan["protected"]), "article_doi": "10.1002/smsc.202500540",
        "dataset_version_doi": "10.5281/zenodo.19549171", "source_family_provisional": FAMILY,
        "archive_receipt": access, "system": "2E", "protocol": trial["long_cycle_protocol"], "panels": evidence,
        "denominator_identity": "author's sample-specific numeric divisor from workbook formula",
        "denominator_cycle_index": None,
        "sample_condition_series_with_early_data": 10, "normalized_early_values": 200,
        "linked_biomass_sample_condition_series": 3, "linked_distinct_source_families": 1,
        "early10_post_reference_observations_per_series": 9,
        "early20_post_reference_observations_per_series": 19,
        "source_lineage_status": "held pending companion experiment attribution and historical exposure audit",
        "admissible_to_prediction_lock": 0, "endpoint_exposures": 0, "predictions_locked": 0,
        "new_fits": 0, "canonical_admissions": 0, "external_sources": 0,
    }
    observations = {
        "scope": "first 20% only; source data for audit and input preparation",
        "source_family_provisional": FAMILY, "system": "2E", "target_cycle_count": 10000,
        "first_logged_reference_cycle": 100, "physical_denominator_cycle_confirmed": False,
        "absolute_cycle_current_mA": 10, "reported_cycle_current_A_g": None, "panels": inputs,
    }
    return info, observations


if __name__ == "__main__":
    for path, result in zip(("evidence.json", "early_observations.json"), audit(), strict=True):
        (OUT / path).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
