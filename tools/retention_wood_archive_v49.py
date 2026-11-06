"""Verify the public archive inventory and sealed manuscript protocol for the wood-carbon case."""

from hashlib import md5
import json
from pathlib import Path
import re
import subprocess
import sys
from xml.etree import ElementTree as ET

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.prepare_small_sample_routes import read, sha
from tools.retention_blind_reserve_v22 import BASE, db_matches, flat

OUT = BASE / "第四十九轮_木源长循环原始数据核查_20261107"
CACHE = ROOT / ".local-literature-cache/P49"
GIT = ["git", "-c", f"safe.directory={ROOT.as_posix()}"]
FREEZE, FALLBACK = "87679ad", "4ea5a48"
DOI, COMPANION = "10.1002/smsc.202500540", "10.1016/j.cartre.2024.100436"
CONCEPT, VERSION = "10.5281/zenodo.15628303", "10.5281/zenodo.19549171"
FIGURE_ID = "smsc70209-fig-0008"


def frozen(path, commit):
    spec = f"{commit}:{path.relative_to(ROOT).as_posix()}"
    assert subprocess.check_output(GIT+["show",spec],cwd=ROOT)==path.read_bytes()
    return read(path)


def protocol(path):
    doc = ET.parse(path).getroot()
    assert any(el.get("pub-id-type")=="doi" and flat(el).lower()==DOI for el in doc.findall(".//article-id"))
    methods = doc.find(".//sec[@id='smsc70209-sec-0008']")
    items = [flat(p) for p in methods.findall("p")]
    run, = [p for p in items if "10 000 cycles" in p and "100 cycles" in p]
    assert "constant current of 10 mA up to 1.2 V for 10 000 cycles" in run
    assert "Capacitance was monitored and recorded every 100 cycles" in run
    assert any(re.search(r"two.{0,20}electrodes|two.electrode",p,re.I) for p in items)
    assert any(re.search(r"\balder\b",flat(p),re.I) for p in doc.findall(".//body//p"))
    fig = doc.find(f".//fig[@id='{FIGURE_ID}']")
    caption = flat(fig.find("caption"))
    assert "retention" in caption.casefold()
    split = list(re.finditer(r"(?<![\w])(?:\(([ab])\)|([ab])\))",caption,re.I))
    assert len(split)==2
    assert re.search("NaCl",caption[split[0].end():split[1].start()],re.I)
    assert re.search(r"phosphate|PO\s*4",caption[split[1].end():],re.I)
    data_statement = next(flat(x) for x in doc.findall(".//sec") if "data availability" in x.findtext("title","").casefold())
    assert CONCEPT in data_statement
    return {"article_doi":DOI,"system":"2E printed device","biomass_material":"alder wood-derived activated carbon (AWC)",
            "long_cycle_protocol":{"current_mA_absolute":10,"mass_normalized_current_A_g_verified":None,"upper_voltage_V":1.2,
                                   "cycle_count":10000,"author_stated_record_interval_cycles":100},
            "figure_id":FIGURE_ID,"figure_caption_panel_roles":{"a":"NaCl","b":"phosphate"},
            "sample_row_binding_and_same_run_normalization_pending":True,"exact_outcome_emitted":False}


def lineage(plan):
    exact = db_matches({DOI,COMPANION})
    assert all(len(matches)==2 and not any(matches.values()) for matches in exact.values())
    p31 = next(ROOT/p for p in plan["protected"] if p.endswith("training_plan.json"))
    folded = {group for item in read(p31)["cohorts"].values() for group in item["folds"]}
    assert all("doi:"+doi not in folded for doi in (DOI,COMPANION))
    matches = {}
    for doi in (DOI,COMPANION):
        check = subprocess.run(GIT+["grep","-IlFi","-e",doi,plan["parent"],"--","*.md","*.json","*.csv","*.txt","*.xml"],
                               cwd=ROOT,capture_output=True,check=False)
        assert check.returncode in (0,1)
        matches[doi] = [p.split(":",1)[1] for p in check.stdout.decode("utf-8").splitlines()]
    assert matches[DOI] and all("openalex_" in f or "补充原料候选发现.json" in f for f in matches[DOI])
    metadata = [read(CACHE/n)["data"]["attributes"] for n in ("datacite_15628303.json","datacite_14728843.json")]
    names = [{c["name"].casefold() for c in value["creators"]} for value in metadata]
    shared = sorted(names[0]&names[1])
    assert len(shared)>=2
    return {"exact_live_catalog_matches":exact,"exact_P31_fold_doi_matches":0,"existing_tracked_mentions":matches,
            "shared_named_data_creators":shared,"provisional_source_clusters":1,
            "experimental_overlap_verified":False,"independent_source_qualified":False}


def main():
    plan = frozen(OUT/"screen_plan.json",FREEZE)
    backup = frozen(OUT/"figure_fallback_plan.json",FALLBACK)
    assert all(sha(ROOT/p)==v for p,v in plan["protected"].items())
    assert all(sha(CACHE/p)==v for p,v in backup["receipts"].items())
    meta = read(CACHE/"metadata_access.json")
    for key in ("datacite_15628303.json","datacite_14728843.json"):
        assert sha(CACHE/key)==meta[key]["sha256"]
    concept = meta["datacite_15628303.json"]
    assert concept["datacite_id"]==CONCEPT
    assert any(x["relationType"]=="HasVersion" and x["relatedIdentifier"]==VERSION for x in concept["related"])
    inventory = read(OUT/"public_file_inventory.json")
    assert inventory["record_version_doi"]==VERSION
    assert set(inventory["long_cycle_member_names"])=={"Book1.Long-term cycling (KxHyPO4).csv","Book1.Long-term cycling (NaCl).csv"}
    access = read(CACHE/"asset_access.json")
    assert all(x["status"]=="unavailable" for key,x in access.items() if key.startswith("v2_file_"))
    f = read(CACHE/"fallback_access.json")
    image = CACHE/f["asset"]
    assert f["doi"]==DOI and f["figure"]=="8" and not f["visible_figure_pixels_released"]
    assert sha(image)==f["sha256"] and md5(image.read_bytes()).hexdigest()==f["md5"]
    with Image.open(image) as im:
        assert list(im.size)==f["dimensions"]
        im.verify()
    result = {"freeze_commit":FREEZE,"fallback_freeze_commit":FALLBACK,"inventory":inventory,
              "metadata_access":meta,"attachment_access":access,"protocol_access":read(CACHE/"protocol_access.json"),
              "transport_receipt":read(CACHE/"transport_receipt.json"),"sealed_figure":f,
              "publisher_protocol":protocol(CACHE/"wood_epmc.xml"),"source_lineage":lineage(plan),
              "verified_cycling_csv_bytes":False,"csv_headers_verified":False,"early_data_rows_verified":0,
              "new_early_inputs":0,"exact_endpoints_revealed":0,"predictions_locked":0,"fits":0,"formal_admissions":0,"independent_acceptances":0}
    payload=(json.dumps(result,ensure_ascii=False,indent=2)+"\n").encode()
    output=OUT/"evidence.json"
    if output.exists():
        assert output.read_bytes()==payload
    else:
        with output.open("xb") as stream: stream.write(payload)
    print(output.name,sha(output))


if __name__=="__main__":
    main()
