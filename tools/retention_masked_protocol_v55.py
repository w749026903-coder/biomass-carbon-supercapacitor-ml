"""Check figure attribution and preserve sealed source files without reading endpoints."""

import argparse
from hashlib import md5, sha256
import json
import logging
from pathlib import Path
import re
import subprocess
import sys
from xml.etree import ElementTree as ET

import numpy as np
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.retention_blind_reserve_v22 import BASE, flat

CACHE = ROOT / ".local-literature-cache"
OUT = BASE / "第五十五轮_两篇封存候选循环归属核查_20261107"
FREEZE = "0d25bcd"


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def xml_body(pmcid, doi, expected):
    path = CACHE / "P54" / f"{pmcid}.sealed.xml"
    assert digest(path) == expected
    tree = ET.parse(path).getroot()
    assert any(n.get("pub-id-type") == "doi" and flat(n).lower() == doi for n in tree.findall(".//article-meta/article-id"))
    body = tree.find("body")
    return body, [flat(p) for p in body.findall(".//p")]


def ranges(row, offset):
    hits = np.flatnonzero(row) + offset
    return [(int(a[0]), int(a[-1])) for a in np.split(hits, np.where(np.diff(hits) != 1)[0] + 1) if a.size]


def periodic_axis_hypotheses(image):
    # Check only for a reproducible, long perpendicular frame and periodic tick stubs.
    # Coordinates from unverified hypotheses do not leave this function.
    dark = np.asarray(image.convert("RGB")).max(axis=2) < 145
    count = 0
    for y in range(1000, 1475):
        for l, r in ranges(dark[y, 625:], 625):
            if r - l < 280 or l <= 625:
                continue
            if max(np.any(dark[y - 80:y, x - 2:x + 3], axis=1).mean() for x in range(l - 7, l + 9)) < .82:
                continue
            for off in (-10, -9, -8, -7, -6, -5, -4, 4, 5, 6, 7, 8, 9, 10):
                stubs = [(a + b) / 2 for a, b in ranges(dark[y + off, l - 5:r + 5], l - 5) if 1 <= b - a <= 8]
                gaps = np.diff(stubs)
                count += int(len(gaps) >= 3 and min(gaps) > 18 and max(gaps) < 110 and np.ptp(gaps) <= 4)
    return count


def repository_pdf(name, key):
    index = ET.parse(CACHE / "P54/plant_s3_list.xml").getroot()
    row, = [i for i in index.findall("{*}Contents") if i.findtext("{*}Key") == f"PMC6641454.1/{key}"]
    path = CACHE / "P55" / name
    b = path.read_bytes()
    assert len(b) == int(row.findtext("{*}Size")) and md5(b).hexdigest() == row.findtext("{*}ETag").strip('"')
    return PdfReader(path), {"sha256": sha256(b).hexdigest(), "repository_etag_md5": md5(b).hexdigest(), "bytes": len(b)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="Create the evidence file if absent")
    args = parser.parse_args()
    logging.getLogger("pypdf").setLevel(logging.ERROR)
    path = OUT / "screen_plan.json"
    git = ["git", "-c", f"safe.directory={ROOT.as_posix()}"]
    assert subprocess.check_output(git + ["show", f"{FREEZE}:{path.relative_to(ROOT).as_posix()}"], cwd=ROOT) == path.read_bytes()
    plan = json.loads(path.read_bytes())
    assert all(digest(ROOT / name) == h for name, h in plan["protected"].items())
    prev_path, = [ROOT / n for n in plan["protected"] if n.endswith("evidence.json")]
    prev = {c["pmcid"]: c for c in json.loads(prev_path.read_bytes())["candidates"]}

    black, black_text = xml_body("PMC10094988", "10.3390/ma16072551", prev["PMC10094988"]["sealed_xml_sha256"])
    cap7 = flat(black.find('.//fig[@id="materials-16-02551-f007"]/caption'))
    part_c = re.split(r"\(c\)|\(d\)", cap7)[1]
    assert re.search(r"\bCV\b.{0,35}\bcurves?\b", cap7, re.I)
    assert re.search(r"after.{0,40}\b1000\s+cycles\b", part_c, re.I) and re.search(r"\bGCD\b", part_c, re.I)
    assert re.search(r"\bCV\b.*?\bcurves?\b", black_text[31], re.I) and "1000 cycles" in black_text[31]
    assert re.search(r"Figure\s*7\s*c", black_text[30], re.I)
    a = {"article_doi": "10.3390/ma16072551", "panel": "Fig. 7(c)", "post_gcd_cycles": 1000,
         "observation_role": "post-cycling CV comparison", "retention_vs_cycle_plot_verified": False,
         "early_markers_examined": False, "disposition": "hold_no_retention_trajectory_at_target_panel"}

    plant, plant_text = xml_body("PMC6641454", "10.1021/acsomega.7b01876", prev["PMC6641454"]["sealed_xml_sha256"])
    cap4 = flat(plant.find('.//fig[@id="fig4"]/caption'))
    assert re.search(r"\(F\).+\b5\s*A/g", cap4) and re.search(r"Figure\s*4\s*F", plant_text[27])
    assert re.search(r"3000\s+charge\s+and\s+discharge\s+cycles", plant_text[27], re.I)
    assert "initial capacitance" in plant_text[27].casefold() and "6 M KOH" in plant_text[22]
    assert "two-electrode" in plant_text[24] and "two-electrode" in plant_text[35] and "symmetric" in plant_text[35]
    main_pdf, main_receipt = repository_pdf("plant_publisher_sealed.pdf", "PMC6641454.1.pdf")
    img, = [im for im in main_pdf.pages[4].images if im.name == "Im5.png"]
    assert img.image.size == (1250, 1505) and len(main_pdf.pages) == 10
    axes = periodic_axis_hypotheses(img.image)
    assert axes == 0
    si, si_receipt = repository_pdf("plant_supp_sealed.pdf", "ao7b01876_si_001.pdf")
    assert len(si.pages) == 6 and len(si.attachments) == 0
    s5 = " ".join((si.pages[-1].extract_text() or "").split())
    assert re.search(r"Figure\s+S5", s5) and "two-electrode" in s5 and "stability" in s5
    assert not any(re.search(r"\bTable\s+S\d+", p.extract_text() or "", re.I) for p in si.pages)
    b = {"article_doi": "10.1021/acsomega.7b01876", "panel": "Fig. 4(F)", "system": "2E symmetric device",
         "target_cycles": 3000, "reported_cycle_current_A_g": 5, "reference_role": "initial capacitance",
         "precise_reference_cycle_index": None, "reported_general_electrolyte": "6 M KOH",
         "fig_4f_electrolyte_directly_bound": False, "publisher_pdf": {**main_receipt, "page": 5, "object": "Im5.png", "dimensions": [1250, 1505]},
         "supplement_pdf": {**si_receipt, "pages": 6, "embedded_attachments": 0, "table_labels": 0, "device_figure": "Fig. S5"},
         "validated_periodic_axis_hypotheses": axes, "graph_interior_displayed": False,
         "early_markers_10_20": None, "disposition": "hold_safe_axes_not_validated_no_cycle_table_located"}
    evidence = {"phase": 55, "freeze_commit": FREEZE, "plan_sha256": digest(path), "candidates": [a, b],
                "endpoint_exposures": 0, "new_early_inputs": 0, "predictions_locked": 0, "new_fits": 0,
                "canonical_admissions": 0, "external_acceptances": 0}
    dest = OUT / "evidence.json"
    payload = json.dumps(evidence, ensure_ascii=False, indent=2) + "\n"
    if args.write:
        with dest.open("x", encoding="utf-8", newline="\n") as f:
            f.write(payload)
    assert dest.read_bytes() == payload.encode("utf-8")
    print("Two panel attributions, two repository PDF ETags and six protected hashes verified. No endpoints read.")


if __name__ == "__main__":
    main()
