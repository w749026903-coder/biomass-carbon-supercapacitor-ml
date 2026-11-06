"""Audit the sealed seaweed figure without reading its late plotting region."""

from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import numpy as np
from PIL import Image
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.prepare_small_sample_routes import read, sha
from tools.retention_blind_reserve_v22 import BASE, db_matches, flat
from tools.retention_mask_gate_v46 import evidence_regions

OUT = BASE / "第四十七轮_海藻碳循环证据核验_20261106"
CACHE = ROOT / ".local-literature-cache/P47"
FREEZE = "4f18965"
DOI = "10.3390/ma15165748"
FIG = "materials-15-05748-f009"
PREFIX = "materials-15-05748"
GIT = ["git", "-c", f"safe.directory={ROOT.as_posix()}"]


def protocol(xml):
    body = xml.find("body")
    materials = flat(body.find(f'.//sec[@id="sec2dot1-{PREFIX}"]'))
    method = flat(body.find(f'.//sec[@id="sec2dot4-{PREFIX}"]'))
    section = body.find(f'.//sec[@id="sec3dot4-{PREFIX}"]')
    p, = [p for p in section.findall("p") if any(FIG in n.get("rid", "").split() for n in p.findall(".//xref"))]
    sentences = re.split(r"(?<=[.!?])\s+", flat(p))
    test, = [s for s in sentences if re.search(r"10[ ,]?000\s*(?:charge.discharge\s+)?cycles?", s, re.I)]
    assert re.search(r"at a current density of\s*1\s*A\s*(?:/\s*g\b|[· ]?g\s*[-−]\s*1\b)", test, re.I)
    assert re.search(r"1\s*(?:M|mol\s*(?:L[−-]?1|/L))\s*Na\s*2\s*SO\s*4\b", method, re.I)
    assert all(key.casefold() in method.casefold() for key in ("three-electrode", "SCE"))
    assert "seaweed" in materials.casefold()
    assert any("initial capacitance" in s.casefold() and re.search(r"Figure\s*9", s, re.I) for s in sentences)
    return {"precursor":"seaweed","system":"3E","test":"repeated charge-discharge","reported_current_A_g":1,
            "planned_cycles":10000,"method_electrolyte":"1 M Na2SO4","method_reference":"SCE",
            "normalization_reference":"author mentions the initial capacitance; exact observation cycle and normalization value not digitized",
            "cycle_protocol_locator":"§2.4, §3.4 and Fig. 9","terminal_retention_released":False}


def paper_matches(plan):
    exact = db_matches({DOI})[DOI]
    assert len(exact)==2 and not any(exact.values())
    pointer = read(ROOT/"data/current_training_latest.json")
    db = ROOT/(pointer["database"] if "database" in pointer else Path(pointer["directory"])/pointer["database_file"])
    assert sha(db)==pointer["sha256"]
    path = next(ROOT/p for p in plan["protected"] if p.endswith("training_plan.json"))
    folds = {key:set(value["folds"]) for key,value in read(path)["cohorts"].items()}
    assert all("doi:"+DOI not in group for group in folds.values())
    terms = re.compile(r"seaweed|kelp|alga[el]|sargassum|enteromorpha|laminaria|gracilaria|undaria|ulva|海藻|海带|浒苔|海草",re.I)
    with sqlite3.connect(db.as_uri()+"?mode=ro",uri=True) as conn:
        rows = [{"doi":doi,"p31_development_systems":sorted(k for k,v in folds.items() if "doi:"+doi.lower() in v)}
                for doi,text in conn.execute("SELECT doi,record_json FROM sources ORDER BY doi")
                if terms.search(json.loads(text).get("title",""))]
    assert len(rows)==2 and not any(r["p31_development_systems"] for r in rows)
    return {"exact_catalog_matches":exact,"p31_exact_doi_match":False,"catalog_title_precursor_alias_matches":rows,
            "experimental_lineage_confirmed":False}


def image_review(image, plot, xaxis, yaxis, band, calibration, guard):
    views = evidence_regions(image,plot,xaxis,yaxis,band,calibration,guard)
    early = {}
    for name in ("early10","early20"):
        pixels = np.asarray(views[name].convert("RGB"))
        occupied = (pixels.max(axis=2)<110).any(axis=0)
        assert occupied.all()
        early[name] = {"occupied_columns":int(occupied.sum()),"columns":len(occupied),
                       "separable_markers_visually_verified":0}
    return {"native_dimensions":list(image.size),"x_axis":"Cycle Number","y_axis":"Specific Capacitance (F/g)",
            "plot_envelope":plot,"x_axis_crop":xaxis,"y_axis_crop":yaxis,"trace_band":band,
            "x_axis_0_10000_cycle_px":calibration,"conservative_guard_px":guard,"early":early,
            "visual_disposition":"A dense continuous trace in the guarded early band; no individually separable marker centers confirmed."}


def supplementary():
    receipt = read(CACHE/"supplement_access.json")
    zpath = CACHE/"materials-15-05748-s001.zip"
    assert sha(zpath)==receipt["sha256"]
    with ZipFile(zpath) as z:
        assert z.namelist()==["materials-1833372-supplementary.pdf"]
        payload=z.read(z.namelist()[0])
    pdf = PdfReader(BytesIO(payload))
    assert len(pdf.pages)==4 and not pdf.attachments
    pages = [" ".join((p.extract_text() or "").split()) for p in pdf.pages]
    assert re.search(r"Box.Be[h]nken|matrix|factor",pages[0],re.I)
    assert re.search(r"Table\s*S\s*1.{0,150}(?:properties|samples|surface|capacitance)",pages[1],re.I)
    assert re.search(r"Figure\s*S\s*[12].{0,150}(?:SEM|TEM|image|micrograph)",pages[2],re.I)
    assert re.search(r"Figure\s*S\s*3.{0,150}(?:SEM|TEM|image|micrograph)",pages[3],re.I)
    assert not any(re.search(r"cycle\s*(?:number|count|index)|number of cycles|capacitance retention|\b[\d,]+\s+cycles\b",p,re.I) for p in pages)
    return {"archive":receipt,"pdf_sha256":sha256(payload).hexdigest(),"pdf_pages":len(pages),
            "pdf_attachments":len(pdf.attachments),"document_content":["design equation","material properties table S1",
                      "microscopy Figs S1/S2","microscopy Fig. S3 including before/after"],"cycling_table_located":False}


def main():
    path = OUT/"screen_plan.json"
    plan=read(path)
    assert subprocess.check_output(GIT+["show",f"{FREEZE}:{path.relative_to(ROOT).as_posix()}"],cwd=ROOT)==path.read_bytes()
    assert all(sha(ROOT/p)==h for p,h in plan["protected"].items())
    role_path=next(ROOT/p for p in plan["protected"] if "第四十六轮_" in p and p.endswith("evidence.json"))
    record,=[x for x in read(role_path)["candidate_reviews"] if x["doi"]==DOI]
    xml_path=ROOT/".local-literature-cache/P32/PMC9416258_sealed_fulltext.xml"
    assert sha(xml_path)==record["sealed_xml_sha256"]
    xml=ET.parse(xml_path).getroot()
    assert any(x.get("pub-id-type")=="doi" and flat(x).lower()==DOI for x in xml.findall(".//article-id"))
    jpeg=ROOT/".local-literature-cache/P46"/record["asset"]["filename"]
    assert sha(jpeg)==record["asset"]["sha256"]
    with Image.open(jpeg) as img:
        small=image_review(img,(88,10,735,486),(60,486,746,515),(48,12,80,482),(94,25,63),(88.5,710.5),5)
    native_receipt=read(CACHE/"publisher_pdf_access.json")
    native_path=CACHE/"PMC9416258.1.pdf"
    assert sha(native_path)==native_receipt["sha256"]
    native,=PdfReader(native_path).pages[14].images
    assert native.image.size==(1400,1068)
    high=image_review(native.image,(160,12,1385,935),(105,935,1394,962),(118,15,148,918),(178,43,117),(164.5,1324.),10)
    results={"plan_commit":FREEZE,"source_doi":DOI,"xml_sha256":sha(xml_path),"protocol":protocol(xml),
             "source_matches":paper_matches(plan),"archive_image":small,"publisher_image_page":15,
             "publisher_pdf":native_receipt,"publisher_native_image":high,"supplement_review":supplementary(),
             "candidate_disposition":"held_sealed_pending_per_cycle_measurements","new_early_inputs":0,
             "exact_endpoints_revealed":0,"predictions_locked":0,"new_fits":0,"canonical_admissions":0,"independent_acceptances":0}
    payload=(json.dumps(results,ensure_ascii=False,indent=2)+"\n").encode()
    out=OUT/"evidence.json"
    if out.exists():
        assert out.read_bytes()==payload
    else:
        with out.open("xb") as f:f.write(payload)
    print(out.name,sha(out))


if __name__=="__main__":
    main()
