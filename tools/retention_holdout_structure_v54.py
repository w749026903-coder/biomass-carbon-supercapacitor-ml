"""Verify provisional holdout identities, test signals and sealed figure bytes."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess
import sys
from xml.etree import ElementTree as ET

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.retention_blind_reserve_v22 import BASE, db_matches, flat

OUT = BASE / "第五十四轮_独立候选结构筛查与阶段图表_20261107"
CACHE = ROOT / ".local-literature-cache/P54"
FREEZE = "67342fa"
GCD = r"galvanostatic|\bGCD\b|constant.current charge"
CV = r"cyclic voltammetr|\bCV\b|voltammo"
CYCLES = r"\b\d(?:[,\s]?\d){1,5}\s*(?:continuous |consecutive |charge.discharge |gcd |cv )?cycles\b|number\s+of\s+cycles"
ROLE = r"cycl(?:ing|ic|e)\s+(?:stabilit|durabilit|performance|life|test)|capacitance retention"
DEVICE = r"two[\s‐–-]+electrode|2[\s‐–-]+electrode|symmetric (?:super)?capacitor"


def read(name):
    return json.loads((CACHE / name).read_bytes())


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def has(text, pattern):
    return bool(re.search(pattern, text, re.I))


def panel(caption, letter):
    parts = re.split(r"\(([a-h])\)", caption)
    sections = dict(zip(parts[1::2], parts[2::2]))
    return sections[letter]


def article_structure(row, access, assets):
    pmc = row["pmcid"]
    path = CACHE / f"{pmc}.sealed.xml"
    assert digest(path) == access["sha256"]
    doc = ET.parse(path).getroot()
    assert any(i.get("pub-id-type") == "doi" and flat(i).casefold() == row["doi"]
               for i in doc.findall(".//article-meta/article-id"))
    body = doc.find("body")
    result = {"article_doi": row["doi"], "pmcid": pmc, "sealed_xml_sha256": access["sha256"],
              "figures_in_body": len(body.findall(".//fig")),
              "supplement_nodes": len(doc.findall(".//supplementary-material")),
              "sealed_assets": assets, "new_endpoint_exposed": False, "independent_qualified": False}
    if pmc == "PMC10094988":
        fig = body.find('.//fig[@id="materials-16-02551-f007"]')
        caption = flat(fig.find("caption"))
        assert has(panel(caption, "c"), GCD) and has(panel(caption, "c"), CYCLES)
        assert has(panel(caption, "e"), DEVICE)
        assert len(assets) == 2
        result.update(figure="Fig. 7(c)", figure_gcd_and_cycle_number_signals=True,
                      other_panel_has_device_signal=True, exact_cycle_test_cell_verified=False,
                      disposition="reserve_figure_for_protocol_and_early_only_review")
    elif pmc == "PMC6641454":
        fig = body.find('.//fig[@id="fig4"]')
        caption = flat(fig.find("caption"))
        assert all(has(caption, p) for p in (GCD, ROLE, DEVICE))
        assert len(assets) == 1
        result.update(figure="Fig. 4", figure_gcd_cycle_and_device_signals=True,
                      exact_cycle_test_cell_verified=False, disposition="reserve_figure_check_device_cycling_panel")
    else:
        assert pmc == "PMC9056314" and not assets
        fig4 = body.find('.//fig[@id="fig4"]')
        fig5 = body.find('.//fig[@id="fig5"]')
        cap4, cap5 = flat(fig4.find("caption")), flat(fig5.find("caption"))
        assert has(cap4, DEVICE) and has(panel(cap4, "b"), GCD)
        assert has(panel(cap5, "a"), CV) and has(panel(cap5, "a"), CYCLES)
        result.update(figure="Figs. 4–5", device_gcd_signal=True, repeated_cv_signal=True,
                      distinct_3E_gcd_cycling_bound=False, disposition="hold_distinguish_repeated_cv_and_device_gcd")
        return result
    graphic_names = {v for g in fig.findall(".//graphic") for k, v in g.attrib.items() if k.endswith("href")}
    for receipt in assets:
        path = CACHE / receipt["asset"]
        assert receipt["asset"] in graphic_names and not receipt["displayed"]
        assert path.stat().st_size == receipt["bytes"] and digest(path) == receipt["sha256"]
        with Image.open(path) as image:
            assert list(image.size) == receipt["dimensions"]
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="Create evidence only if absent")
    args = parser.parse_args()
    path = OUT / "screen_plan.json"
    git = ["git", "-c", f"safe.directory={ROOT.as_posix()}"]
    assert subprocess.check_output(git + ["show", f"{FREEZE}:{path.relative_to(ROOT).as_posix()}"], cwd=ROOT) == path.read_bytes()
    plan = json.loads(path.read_bytes())
    assert all(digest(ROOT / name) == h for name, h in plan["protected"].items())
    recent, older = read("metadata_screen.json"), read("older_metadata.json")
    names = {r["doi"].casefold() for q in recent["queries"] for r in q["rows"]} | set(older["rows"])
    assert plan["metadata_only_counts"] == {"recent_unique": recent["unique_dois"], "older_unique": len(older["rows"]),
                                            "union_unique": len(names)}
    dois = {row["doi"] for row in plan["new_article_candidates"]}
    catalog = db_matches(dois)
    assert all(len(hits) == 2 and not any(hits.values()) for hits in catalog.values())
    assets = read("sealed_assets.json")
    assert len(assets) == 3
    access = read("access.json")
    access["PMC6641454"] = read("plant_recovery.json")["plant_retry"]
    assert access["acs_full"]["status"] == access["sam_full"]["status"] == 401
    candidates = []
    for row in plan["new_article_candidates"]:
        pmc = row["pmcid"]
        summary = article_structure(row, access[pmc], [item for item in assets if item["pmcid"] == pmc])
        candidates.append({**summary, "title": row["title"], "exact_current_catalog_hits": catalog[row["doi"]],
                           "prior_project_doi_paths": len(row["prior_doi_paths"])})
    evidence = {"phase": 54, "freeze_commit": FREEZE, "plan_sha256": digest(path),
                "metadata_only_counts": plan["metadata_only_counts"], "candidates": candidates,
                "development_followup": {"ACS-600": access["acs_full"], "SAM-700-4": access["sam_full"]},
                "sealed_figure_files": 3, "provisional_figure_sources": 2, "new_early_inputs": 0,
                "prediction_locks": 0, "new_fits": 0, "canonical_admissions": 0, "external_acceptances": 0}
    dest = OUT / "evidence.json"
    payload = json.dumps(evidence, ensure_ascii=False, indent=2) + "\n"
    if args.write:
        with dest.open("x", encoding="utf-8", newline="\n") as f:
            f.write(payload)
    assert dest.read_bytes() == payload.encode("utf-8")
    print("Three XML identities and test structures, three sealed figure files, five protected hashes, two fulltext access limits verified.")


if __name__ == "__main__":
    main()
