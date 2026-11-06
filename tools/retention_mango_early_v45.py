"""Reproduce the allowed early-pixel and source checks for the quarantined mango paper."""

import json
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
from xml.etree import ElementTree as ET

import numpy as np
from PIL import Image
from pypdf import PdfReader
from pypdf.generic import ContentStream

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.prepare_small_sample_routes import read, sha
from tools.retention_blind_reserve_v22 import BASE, db_matches, flat

OUT = BASE / "第四十五轮_芒果核盲态输入与阶段图表_20261106"
CACHE = ROOT / ".local-literature-cache/P45"
P44 = BASE / "第四十四轮_三电极端点反查与定向盲筛_20261106"
FREEZE = "bbb1186"
GIT = ["git", "-c", f"safe.directory={ROOT.as_posix()}"]
DOI = "10.3390/mi13091518"
RELATED = "10.1039/d5ra02129d"
FIGURE = "micromachines-13-01518-"


def author_keys(root):
    return {re.sub(r"[^a-z]", "", flat(a).casefold())
            for a in root.findall(".//article-meta//contrib/name")}


def lineage(root, plan):
    matches = db_matches({DOI})[DOI]
    assert len(matches) == 2 and not any(matches.values())
    ptr = read(ROOT / "data/current_training_latest.json")
    path = ROOT / (ptr["database"] if "database" in ptr else Path(ptr["directory"]) / ptr["database_file"])
    assert sha(path) == ptr["sha256"]
    with sqlite3.connect(path.as_uri()+"?mode=ro", uri=True) as db:
        row, = db.execute("SELECT record_json FROM sources WHERE lower(doi)=?", (RELATED,)).fetchone()
    source = json.loads(row)
    prior = ROOT / source["path"]
    assert sha(prior) == source["sha256"] and "mango kernel" in source["title"].lower()
    related = ET.parse(prior).getroot()
    incoming_authors, related_authors = author_keys(root), author_keys(related)
    assert incoming_authors and related_authors and incoming_authors.isdisjoint(related_authors)
    known_affiliations = ["Guiyang University", "B. M. S. College of Engineering"]
    for paper, affiliation in zip((root, related), known_affiliations):
        assert any(affiliation in flat(a) for a in paper.findall(".//article-meta//aff"))
    p31 = next(ROOT/p for p in plan["protected"] if p.endswith("training_plan.json"))
    folds = {system:set(group["folds"]) for system, group in read(p31)["cohorts"].items()}
    assert all(f"doi:{DOI}" not in groups for groups in folds.values())
    related_systems = sorted(system for system, groups in folds.items() if f"doi:{RELATED}" in groups)
    assert related_systems
    return {"exact_catalog_hits":matches,"p31_candidate_doi_present":False,"related_doi":RELATED,
            "related_p31_systems":related_systems,"shared_named_authors":0,"comparison_lab_names":known_affiliations,
            "related_source_sha256":sha(prior),"disposition":"Similar precursor name; no common author found, shared experimental lineage not established."}


def protocol(root):
    body = root.find("body")
    paragraphs = [flat(p) for p in body.find(f'.//sec[@id="sec3dot2-{FIGURE.rstrip("-")}"]').findall("p")]
    three_method = flat(body.find(f'.//sec[@id="sec2dot3-{FIGURE.rstrip("-")}"]'))
    two_method = flat(body.find(f'.//sec[@id="sec2dot1-{FIGURE.rstrip("-")}"]'))
    assert all(token in three_method for token in ("three-electrode", "Hg/HgO", "6 M KOH"))
    assert "two-electrode" in two_method
    current = r"\b\d+(?:\.\d+)?\s*A\s*/?\s*g\b"
    result = {}
    for system, index, panel, samples, paragraph, role in (
        ("3E",2,"f",["C-800","NC-800"],paragraphs[0],"three-electrode"),
        ("2E",3,"d",["NC-800"],paragraphs[1],"symmetric"),
    ):
        cap = flat(body.find(f'.//fig[@id="{FIGURE}f00{index}"]/caption'))
        chunks = re.split(r"\(([a-h])\)", cap)
        text = chunks[chunks.index(panel)+1]
        assert all(re.search(r"(?<![\w-])"+re.escape(sample)+r"(?![\w-])",text) for sample in samples)
        assert "5000" in text and "cycl" in text.casefold() and role in paragraph
        assert not re.search(current,text,re.I)
        # An A/g elsewhere in the paragraph, e.g. the rate series, is insufficient.
        cycle_clauses = [x for x in re.split(r"(?<=[.!?])\s+",paragraph) if "5000" in x and "cycl" in x.casefold()]
        assert cycle_clauses and not any(re.search(current,x,re.I) for x in cycle_clauses)
        assert not any(re.search(r"initial|first\s+cycle",x,re.I) for x in cycle_clauses)
        result[system] = {"figure":f"{index}({panel})","samples_in_caption":samples,"target_cycles":5000,
                          "reported_cycling_current_A_g":None,"raw_ordinate":"capacitance (F/g)",
                          "same_test_normalizer_F_g":None,"known_reference_cycle":None}
    result["3E"].update(method_electrolyte="6 M aqueous KOH", method_reference="Hg/HgO",
                        color_sample_binding="Two curves plotted; sample assignment by color not asserted.")
    result["2E"].update(method_electrolyte=None, method_reference=None, color_sample_binding="Single NC-800 symmetric-device curve.")
    return result


def native_figures(path):
    pdf = PdfReader(path)
    page = pdf.pages[4]
    form = page["/Resources"]["/XObject"]["/Im7"].get_object()
    strips = []
    placement = None
    for args, operator in ContentStream(form,pdf).operations:
        if operator == b"cm":
            placement = tuple(map(float,args))
        if operator == b"Do" and str(args[0]) in {f"/Im{i}" for i in range(41,47)}:
            strips.append((str(args[0]),placement))
    assert len(strips) == 6 and all(a[1][4] == b[1][4] and abs(a[1][5]-b[1][5]-24.72)<.001
                                   for a,b in zip(strips,strips[1:]))
    panel = Image.new("RGB",(762,624))
    for i,(name,_) in enumerate(strips):
        tile = page.images[("/Im7",name)].image
        assert tile.size == (762,104)
        panel.paste(tile.convert("RGB"),(0,i*104))
    other = pdf.pages[5].images[("/Im8","/Im50")].image
    assert other.size == (720,580)
    return panel, other


def exterior_axis(panel, xbounds, ybounds, xticks, yticks):
    # Read only the tick extensions outside the plot. The interior is never part of the rail probe.
    xink = (np.asarray(panel.crop(xbounds).convert("RGB")).max(axis=2)<160).sum(axis=0)
    yink = (np.asarray(panel.crop(ybounds).convert("RGB")).max(axis=2)<160).sum(axis=1)
    assert all(max(xink[round(x)-xbounds[0]-1:round(x)-xbounds[0]+2]) >= 7 for x in xticks)
    assert all(max(yink[round(y)-ybounds[1]-1:round(y)-ybounds[1]+2]) >= 6 for y in yticks)


def points(image, x_range, y_range, xticks, y_bottom, y_top, y_value, seeds, y_seeds=None):
    x0, x5000 = xticks
    l,r = x_range
    t,b = y_range
    assert x0 < l < r < x0+.2*(x5000-x0)
    data = np.asarray(image.crop((l,t,r,b)).convert("RGB"), dtype=np.int16)
    light = data.min(axis=2)
    score = light.sum(axis=0)
    scale_x, scale_y = 5000/(x5000-x0), y_value/(y_bottom-y_top)
    readings = []
    for index,x in enumerate(seeds):
        i=x-l
        assert np.argmax(score[i-2:i+3]) in (1,2,3)
        assert score[i] > min(score[i+3:i+6])+100
        y_start = 0 if y_seeds is None else y_seeds[index]-t-2
        y_stop = len(light) if y_seeds is None else y_start+5
        patch = light[y_start:y_stop,i-1:i+2]
        yy,xx = np.where(patch>=int(patch.max())-20)
        assert len(xx)>1 and np.ptp(yy)<=6
        y = float(t+y_start+yy.mean())
        cycle, cap = (x-x0)*scale_x,(y_bottom-y)*scale_y
        readings.append({"center_px":[x,y],"cycle":cycle,"cycle_interval":[cycle-4*scale_x,cycle+4*scale_x],
                         "capacitance_F_g":cap,"capacitance_geometry_interval_F_g":[cap-5*scale_y,cap+5*scale_y]})
    assert all(a["cycle_interval"][1]<b["cycle_interval"][0] for a,b in zip(readings,readings[1:]))
    assert all(0<a["cycle_interval"][0]<a["cycle_interval"][1]<1000 for a in readings)
    return {"counts_10_20":[sum(p["cycle_interval"][1]<=limit for p in readings) for limit in (500,1000)],
            "bounds_ltrb":[l,t,r,b],"points":readings}


def main():
    plan_path = OUT/"screen_plan.json"
    plan = read(plan_path)
    assert subprocess.check_output(GIT+["show",f"{FREEZE}:{plan_path.relative_to(ROOT).as_posix()}"],cwd=ROOT)==plan_path.read_bytes()
    assert all(sha(ROOT/p)==h for p,h in plan["protected"].items())
    sealed = read(P44/"sealed_structure.json")
    xml = ROOT/sealed["sealed_cache"]
    assert sha(xml) == sealed["sha256"] and sealed["endpoint_exposed"] is False
    root = ET.parse(xml).getroot()
    assert any(x.get("pub-id-type")=="doi" and flat(x).lower()==DOI for x in root.findall(".//article-id"))
    assets = read(CACHE/"asset_receipt.json")
    assert all(sha(CACHE/name)==entry["sha256"] for name,entry in assets.items())
    a,b = native_figures(CACHE/"PMC9502334.1.pdf")
    xt3, xt2 = (108.5,222.5,336.,449.5,563.5,676.5), (94.,209.,324.,439.5,554.,669.)
    exterior_axis(a,(106,525,682,534),(99,14,107,525),xt3,(34.5,88.5,143.,197.5,251.5,306.,360.5,415.,469.,523.5))
    exterior_axis(b,(91,497,676,505),(85,14,93,496),xt2,(46.,110.,175.,238.5,303.,367.,432.,495.))
    seeds = (117,129,140,151,163,174,186,197,208)
    traces = {"3E_neutral":points(a,(113,219),(31,38),(xt3[0],xt3[-1]),523.5,34.5,270,seeds),
              "3E_red":points(a,(113,219),(301,312),(xt3[0],xt3[-1]),523.5,34.5,270,seeds),
              "2E_magenta":points(b,(98,206),(40,55),(xt2[0],xt2[-1]),495.5,46.,140,
                                  (114,125,137,148,160,171,183,194),(43,44,45,46,46,47,47,48))}
    assert [row["counts_10_20"] for row in traces.values()]==[[4,9],[4,9],[3,8]]
    result = {"doi":DOI,"one_paper_source":1,"frozen_plan_commit":FREEZE,"protected_xml_sha256":sha(xml),
              "asset_receipt":assets,"protocols":protocol(root),"lineage":lineage(root,plan),"traces":traces,
              "exposure_disposition":{"status":"whole_source_development_only",
                "reason":"A pre-crop neutral-line diagnostic emitted late 3E trace runs. Position can be converted to late absolute capacitance with the exterior axis.",
                "exact_terminal_revealed":False,"both_electrode_systems_excluded_from_blind_scoring":True,
                "correction":"Require fixed exterior tick strips and verify the right edge of every plot-interior slice before emitting diagnostics."},
              "new_blind_early_inputs":0,"predictions_locked":0,"new_fits":0,"formal_admissions":0,"independent_acceptances":0}
    payload = (json.dumps(result,ensure_ascii=False,indent=2)+"\n").encode()
    output = OUT/"early_evidence.json"
    if output.exists():
        assert output.read_bytes()==payload
    else:
        with output.open("xb") as f:
            f.write(payload)
    print(output.name,sha(output))


if __name__ == "__main__":
    main()
