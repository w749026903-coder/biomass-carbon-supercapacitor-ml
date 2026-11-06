"""Enforce early-pixel boundaries and check the next sealed candidate queue."""

import json
import math
from pathlib import Path
import re
import subprocess
import sys
from xml.etree import ElementTree as ET

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.prepare_small_sample_routes import read, sha
from tools.retention_blind_reserve_v22 import BASE, db_matches, flat
from tools.retention_mango_early_v45 import CACHE as MANGO_CACHE, native_figures

OUT = BASE / "第四十六轮_遮蔽回归与封存候选核查_20261106"
CACHE = ROOT / ".local-literature-cache/P46"
FREEZE = "355264e"
GIT = ["git", "-c", f"safe.directory={ROOT.as_posix()}"]
SEAWEED = "10.3390/ma15165748"
FUNGUS = "10.1002/gch2.202300315"
MIXED = "10.1002/smll.202513011"
FIG9 = "materials-15-05748-f009"
CYCLE = r"cycl(?:e|ing|ic) (?:stabilit|durabilit|performance|life)|cyclability|capacitance retention|\b[\d,]+\s*(?:charge.discharge\s+)?cycles\b"


def evidence_regions(image, plot, x_axis, y_axis, band, calibration, x_guard):
    """Return independent image copies. Never return the original panel or inspect its interior beyond the windows."""
    width,height = image.size
    for l,t,r,b in (plot,x_axis,y_axis):
        if not 0 <= l < r <= width or not 0 <= t < b <= height:
            raise ValueError("rectangle outside native image")
    l,t,r,b = plot
    if x_axis[1] < b or y_axis[2] > l or x_axis[3]-x_axis[1] > 32 or y_axis[2]-y_axis[0] > 32:
        raise ValueError("axis strip must be narrow and wholly outside the plot")
    x0,xt = calibration
    left,top,bottom = band
    if not l <= x0 < xt <= r or not x0 < left < r or not t <= top < bottom <= b or x_guard < 1:
        raise ValueError("incompatible plot, calibration or trace band")
    right_10 = math.floor(x0+.10*(xt-x0)-x_guard)
    right_20 = math.floor(x0+.20*(xt-x0)-x_guard)
    if not left < right_10 < right_20 <= r:
        raise ValueError("invalid calibrated early window")
    return {"x_axis":image.crop(x_axis),"y_axis":image.crop(y_axis),
            "early10":image.crop((left,top,right_10,bottom)),
            "early20":image.crop((left,top,right_20,bottom))}


def pixel_identity(regions):
    return {key:(im.size,im.tobytes()) for key,im in regions.items()}


def regression(mango_pdf):
    a,b = native_figures(mango_pdf)
    rng = np.random.default_rng(46)
    synthetic = Image.fromarray(rng.integers(0,256,(210,300,3),dtype=np.uint8))
    geometries = {
        "synthetic":(synthetic,(33,12,277,176),(33,176,277,190),(20,12,33,176),(39,35,149),(33,273),3),
        "mango_3E_native":(a,(108,16,735,525),(106,525,682,534),(99,14,107,525),(113,30,312),(108.5,676.5),3),
        "mango_2E_native":(b,(94,13,693,497),(91,497,676,505),(85,14,93,496),(98,37,57),(94.,669.),3),
    }
    checks = {}
    for key,(image,plot,x_axis,y_axis,band,ticks,guard) in geometries.items():
        args = plot,x_axis,y_axis,band,ticks,guard
        original = pixel_identity(evidence_regions(image,*args))
        cutoff = math.floor(ticks[0]+.20*(ticks[1]-ticks[0])-guard)
        late_bounds = (cutoff,plot[1],plot[2],plot[3])
        tests = 0
        for color in ((0,0,0),(255,255,255),(0,0,255),(255,0,0),(0,255,0),(255,0,255),None):
            variant = image.copy()
            if color is None:
                w,h = late_bounds[2]-late_bounds[0],late_bounds[3]-late_bounds[1]
                tile = Image.fromarray(rng.integers(0,256,(h,w,3),dtype=np.uint8))
                variant.paste(tile,late_bounds[:2])
            else:
                variant.paste(color,late_bounds)
            assert pixel_identity(evidence_regions(variant,*args)) == original
            tests += 1
        # Changes within the allowed band must affect the early views without altering axes.
        early_variant = image.copy()
        left,top,_ = band
        early_variant.putpixel((left,top),tuple(255-x for x in image.getpixel((left,top))))
        changed = pixel_identity(evidence_regions(early_variant,*args))
        assert {name for name in original if original[name]!=changed[name]} == {"early10","early20"}
        checks[key] = {"late_mutations_with_byte_identical_outputs":tests,"regions_compared_per_mutation":len(original),
                       "early_mutation_changes_only_early_views":True}
    invalid = [((33,175,277,190),(20,12,33,176),(39,35,149),(33,273),3),
               ((33,176,277,190),(20,12,34,176),(39,35,149),(33,273),3),
               ((33,176,301,190),(20,12,33,176),(39,35,149),(33,273),3),
               ((33,176,277,190),(20,12,33,176),(80,35,149),(33,273),3),
               ((33,176,277,190),(20,12,33,176),(39,35,149),(33,279),3)]
    for args in invalid:
        try:
            evidence_regions(synthetic,(33,12,277,176),*args)
        except ValueError:
            continue
        raise AssertionError("unsafe rectangle was accepted")
    return {"panel_checks":checks,"invalid_cases_rejected":len(invalid)}


def candidate_roles(plan, structure):
    catalog = db_matches(plan["sealed_candidates"])
    results = []
    for row in structure["results"]:
        doi = row["doi"]
        if doi not in plan["sealed_candidates"]:
            continue
        xml = ROOT / row["local"]
        assert sha(xml)==row["sha256"] and not any(catalog[doi].values())
        doc = ET.parse(xml).getroot()
        assert any(el.get("pub-id-type")=="doi" and flat(el).lower()==doi for el in doc.findall(".//article-id"))
        body = doc.find("body")
        result = {"doi":doi,"sealed_xml_sha256":sha(xml),"exact_catalog_matches":catalog[doi],"endpoint_exposed":False}
        if doi == FUNGUS:
            fig6 = flat(body.find('.//fig[@id="gch21596-fig-0006"]/caption'))
            assert re.search(r"scan rates?|\bCV\b",fig6,re.I)
            assert not any(re.search(CYCLE,flat(p),re.I) for p in body.findall(".//p"))
            result.update(status="hold_no_long_cycle_in_sealed_body",figure_6_has_cv_or_rate_cue=True,
                          author_supplement_listed=True,source_supplement_audited=False)
        elif doi == SEAWEED:
            method = flat(body.find('.//sec[@id="sec2dot4-materials-15-05748"]'))
            section = body.find('.//sec[@id="sec3dot4-materials-15-05748"]')
            facts = [flat(p) for p in section.findall("p")]
            targets = [flat(p) for p in section.findall("p") if any(FIG9 in n.get("rid","").split() for n in p.findall(".//xref"))]
            assert "three-electrode" in method and "three-electrode" in " ".join(facts)
            assert not any(re.search(r"two.electrode|symmetric cell",text,re.I) for text in facts)
            assert len(targets)==1 and re.search(CYCLE,targets[0],re.I)
            assert all(token in targets[0].casefold() for token in ("stability","charge","discharge","capacitance"))
            assert re.search(r"seaweed",flat(body.find('.//sec[@id="sec2dot1-materials-15-05748"]')),re.I)
            asset = read(CACHE/"asset_receipt.json")
            figure = body.find(f'.//fig[@id="{FIG9}"]')
            assert any(v==asset["filename"] for n in figure.iter() for k,v in n.attrib.items() if k.endswith("href"))
            assert asset["figure_id"]==FIG9 and asset["doi"]==doi
            assert sha(CACHE/asset["filename"])==asset["sha256"]
            assert not asset["displayed"] and not asset["pixel_values_emitted"]
            result.update(status="sealed_fig9_for_3E_cycling_panel_review",article_method_3E=True,
                          same_section_links_fig9_to_cycling=True,plot_axis_role_verified=False,asset=asset)
        else:
            methods = flat(body.find('.//sec[@id="smll73416-sec-0030"]'))
            fig3 = flat(body.find('.//fig[@id="smll73416-fig-0003"]/caption'))
            fig4 = flat(body.find('.//fig[@id="smll73416-fig-0004"]/caption'))
            assert re.search(r"\bsucrose\b",methods,re.I)
            assert not re.search(r"\b(?:biomass|crop)\b|plant.derived|waste.derived",methods,re.I)
            assert re.search(r"supercapacitor",fig3,re.I) and re.search(CYCLE,fig3,re.I)
            assert re.search(r"batter|lithium|\bLIBs?\b",fig4,re.I)
            result.update(status="hold_sucrose_biomass_origin_unverified",supercapacitor_cycling_fig3=True,
                          battery_figure4_separate=True)
        results.append(result)
    assert len(results)==3
    return results


def main():
    path = OUT/"screen_plan.json"
    plan = read(path)
    assert subprocess.check_output(GIT+["show",f"{FREEZE}:{path.relative_to(ROOT).as_posix()}"],cwd=ROOT)==path.read_bytes()
    assert all(sha(ROOT/p)==h for p,h in plan["protected"].items())
    p45 = next(ROOT/p for p in plan["protected"] if p.endswith("early_evidence.json"))
    mango = MANGO_CACHE/"PMC9502334.1.pdf"
    assert sha(mango)==read(p45)["asset_receipt"][mango.name]["sha256"]
    verified = regression(mango)
    structure = next(ROOT/p for p in plan["protected"] if p.endswith("structural_screen.json"))
    roles = candidate_roles(plan,read(structure))
    report = {"freeze_commit":FREEZE,"mask_regression":verified,"candidate_reviews":roles,
              "new_figures_sealed":1,"new_early_inputs":0,"exact_endpoints_revealed":0,
              "predictions_locked":0,"fits":0,"formal_admissions":0,"external_acceptances":0}
    payload = (json.dumps(report,ensure_ascii=False,indent=2)+"\n").encode()
    output = OUT/"evidence.json"
    if output.exists():
        assert output.read_bytes()==payload
    else:
        with output.open("xb") as f:
            f.write(payload)
    print(output.name,sha(output))


if __name__ == "__main__":
    main()
