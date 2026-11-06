"""Reproduce the bounded phase 44 screen from local bibliographic and source evidence."""

from hashlib import sha256
from html import unescape
import json
from pathlib import Path
import re
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
from tools.retention_blind_reserve_v22 import BASE, ENDPOINT, db_matches, flat
from tools import retention_blind_reserve_v22 as blind_source

OUT = BASE / "第四十四轮_三电极端点反查与定向盲筛_20261106"
CACHE = ROOT / ".local-literature-cache/P44"
FREEZE = "4a6214e"
CANDIDATE_LOCK = "7411e3f"
GIT = ["git", "-c", f"safe.directory={ROOT.as_posix()}"]
TEXT_PATHS = ["*.md", "*.json", "*.xml", "*.txt", "*.csv", "*.html"]


def title_words(value):
    plain = unescape(re.sub(r"<[^>]+>", "", value)).casefold()
    return re.findall(r"[^\W_]+", plain)


def title_in_project(title):
    words = title_words(title)
    # Flexible separators for HTML, hyphenation and punctuation. Confirm the whole title in Python.
    for start in range(0, min(4, len(words) - 3)):
        anchor = words[start:start + 4]
        if all(word.isascii() for word in anchor):
            pattern = r"[[:space:][:punct:]]+".join(map(re.escape, anchor))
            result = subprocess.run(GIT + ["grep", "-IhiE", "-e", pattern, FREEZE, "--"] + TEXT_PATHS,
                                    cwd=ROOT, capture_output=True, check=False)
            assert result.returncode in (0, 1), result.stderr
            normalized = " ".join(words)
            return any(normalized in " ".join(title_words(line))
                       for line in result.stdout.decode("utf-8", "replace").splitlines())
    return False


def doi_in_project(doi):
    result = subprocess.run(GIT + ["grep", "-qIiF", "-e", doi, FREEZE, "--"] + TEXT_PATHS,
                            cwd=ROOT, capture_output=True, check=False)
    assert result.returncode in (0, 1), result.stderr
    return result.returncode == 0


def metadata(plan):
    queries = read(CACHE / "metadata_access.json")
    by_doi = {}
    for key in plan["blind"]["title_precursor_terms"]:
        source = CACHE / f"{key}_metadata.json"
        raw = read(source)
        rows = raw["resultList"]["result"]
        assert queries[key][:3] == [raw["hitCount"], len(rows), sha(source)]
        assert len(rows) <= plan["blind"]["limits"]["page_size"]
        for row in rows:
            assert "abstractText" not in row
            if row.get("doi"):
                by_doi.setdefault(row["doi"].lower(), row)
    bibliography = sorted(by_doi.values(), key=lambda x: (-int(x["firstPublicationDate"].replace("-", "")), x["doi"].lower()))
    terms = [term for group in plan["blind"]["title_precursor_terms"].values() for term in group]
    exclude_title = re.compile(r"\breview\b|\bcorrection\b|\d[\d,]*\s+cycles|\d\s*%|\b(?:composite|hybrid)\b|batter(?:y|ies)|photocatal|pitch.derived", re.I)
    database = db_matches(by_doi)
    records, candidates = [], []
    for row in bibliography:
        doi, title = row["doi"].lower(), unescape(row.get("title", ""))
        title = re.sub(r"<[^>]+>", "", title)
        if doi_in_project(doi):
            reason = "tracked_doi"
        elif any(database[doi].values()):
            reason = "catalog_doi"
        elif not (row.get("pmcid") and row.get("isOpenAccess") == "Y" and row.get("hasPDF") == "Y"):
            reason = "public_figure_source_unavailable"
        elif exclude_title.search(title) or not any(re.search(r"\b" + re.escape(t) + r"\b", title, re.I) for t in terms):
            reason = "out_of_scope_title_or_outcome_in_title"
        elif title_in_project(title):
            reason = "tracked_normalized_title"
        elif len(candidates) >= plan["blind"]["limits"]["candidate_cap"]:
            reason = "candidate_cap"
        else:
            reason = "candidate_reserved"
            candidates.append({"doi":doi,"pmcid":row["pmcid"],"title":title,"date":row["firstPublicationDate"],
                               "authors":row["authorString"],"locator":ENDPOINT+row["pmcid"]+"/fullTextXML",
                               "exact_catalog_hits":database[doi]})
        records.append({"doi":doi,"decision":reason})
    return {"plan_commit":FREEZE,"query_receipts":queries,"deduplicated_dois":len(by_doi),
            "decisions":records,"candidates":candidates,"blind_endpoints_exposed":0}


def npca_evidence(plan):
    ledger = next(path for path in plan["protected"] if path.endswith("三电极端点_53条.json"))
    previous = next(path for path in plan["protected"] if path.endswith("training_plan.json"))
    represented = read(ROOT / previous)["cohorts"]["3E"]["folds"]
    rows = [row for row in read(ROOT / ledger)["rows"] if row["system"] == "3E" and row["cycle_method"] == "GCD"
            and row["cycle_count"] >= 5000 and row["retention_pct"] <= 80]
    audit = [{"id":row["endpoint_id"], "doi":row["doi"], "cycles":row["cycle_count"],
              "recorded_retention_pct":row["retention_pct"], "in_p31":row["study_group"] in represented} for row in rows]
    selected, = [row for row in rows if row["study_group"] not in represented]
    assert selected["doi"] == "10.1016/j.seppur.2024.130569"
    source = ROOT / selected["source_file"]
    assert sha(source) == selected["source_sha256"]
    pdf = PdfReader(source)
    pages = {index+1:" ".join(pdf.pages[index].extract_text().split()) for index in (1,8,9,10)}
    assert all(token in pages[2] for token in ("three-electrode system", "Ag/AgCl", "6 M KOH"))
    assert "Cycling performance of NPCA-600 – 0.5 at 10 A/g" in pages[9]
    assert all(token in pages[10] for token in ("5000 charge/discharge", "approximately 80 %"))
    assert "Data will be made available on request" in pages[11]
    access = read(CACHE / "npca_access.json")
    supplement = CACHE / "npca_mmc1.docx"
    figure = CACHE / "npca_gr7_lrg.jpg"
    assert sha(supplement) == access["mmc1.docx"]["sha256"] and sha(figure) == access["gr7_lrg.jpg"]["sha256"]
    ns = {"w":"http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    with ZipFile(supplement) as z:
        root = ET.fromstring(z.read("word/document.xml"))
        nodes = root.findall(".//w:p", ns)
        paragraphs = ["".join(x.text or "" for x in p.findall(".//w:t", ns)).strip() for p in nodes]
        embedded_data_files = [n for n in z.namelist() if n.startswith("word/embeddings/")]
        relations = {n.attrib["Id"]:n.attrib["Target"] for n in ET.fromstring(z.read("word/_rels/document.xml.rels"))}
        origin_objects = [(i,n) for i,p in enumerate(nodes) for n in p.iter() if n.tag.endswith("}OLEObject")]
        (index, origin), = origin_objects
        relation = next(v for k,v in origin.attrib.items() if k.endswith("relationships}id"))
        origin_path = "word/" + relations[relation]
        origin_blob = z.read(origin_path)
    captions = [line for line in paragraphs if re.match(r"Fig\. S\d+\.", line)]
    assert len(captions) == 5 and not any(re.search(r"cycl(?:e|ing)|retention", line, re.I) for line in captions)
    assert embedded_data_files == [origin_path] and origin.attrib["ProgID"] == "Origin95.Graph"
    assert paragraphs[index+1].startswith("Fig. S1. TG curves")
    assert b"Temperature" in origin_blob and origin_blob[:8].hex() == "d0cf11e0a1b11ae1"
    assert "Table S2. Elemental composition" in " ".join(paragraphs)

    with Image.open(figure) as img:
        assert img.size == (3181, 2493)
        # Fig. 7(i) crop from the native CDN figure. Use the left blue axis only.
        rgb = np.asarray(img.convert("RGB").crop((2068, 1645, 3181, 2493)), dtype=np.int16)
    red, green, blue = rgb.transpose(2, 0, 1)
    y0, y200 = 721., 36.
    assert all(np.count_nonzero(rgb[y, 116:305].max(axis=1) < 85) > 170 for y in (36,721))
    terminal_blue = ((blue > red + 65) & (blue > green + 65) & (blue > 100))[425:484,930:951]
    terminal_rows = np.where(terminal_blue.sum(axis=1) >= 18)[0] + 425
    assert 14 <= len(terminal_rows) <= 24
    interval = [(y0-terminal_rows[-1])*200/(y0-y200), (y0-terminal_rows[0])*200/(y0-y200)]
    return {"staged_rows_audited":len(read(ROOT / ledger)["rows"]), "matches":audit, "sample":selected["sample"],
            "source_pdf_sha256":sha(source),"figure":"7(i)","pages":[2,9,10,11],
            "system":"3E","electrolyte":"6 M KOH","reference":"Ag/AgCl","cycle_current_A_g":10,
            "author_approx_retention_pct":80,"cycle_count":5000,"terminal_blue_pixel_band_pct":interval,
            "terminal_blue_band_center_pct":sum(interval)/2,"separable_early_points_10_20":[0,0],
            "marker_disposition":"No distinct marker centers in either early window on the continuous blue ink; no interpolated points.",
            "supplement_figure_ids":[re.match(r"Fig\. (S\d+)", line)[1] for line in captions],
            "supplement_embedded_objects":[{"path":origin_path,"linked_figure":"S1","role":"TG vs temperature",
                                             "sha256":sha256(origin_blob).hexdigest()}],
            "supplement_source_data_for_cycling":False,"publisher_access":access,
            "raw_cycles_availability":"author reports data on request","development_input_added":False}


def screen_blind():
    lock_path = OUT / "blind_candidate_lock.json"
    frozen = subprocess.check_output(GIT + ["show", f"{CANDIDATE_LOCK}:{lock_path.relative_to(ROOT).as_posix()}"], cwd=ROOT)
    assert lock_path.read_bytes() == frozen
    lock = read(lock_path)
    assert lock["screen_plan_commit"] == FREEZE and lock["endpoints_exposed"] == 0
    receipt_path = OUT / "sealed_structure.json"
    assert not receipt_path.exists()
    # Use the same no-outcome output allowlist as the earlier blind screens.
    blind_source.CACHE = CACHE
    structural = blind_source.screen_one({"doi":lock["doi"],"pmcid":lock["pmcid"],
                                          "locator":ENDPOINT+lock["pmcid"]+"/fullTextXML"})
    if structural["status"] == "sealed_fulltext_identity_confirmed":
        doc = ET.parse(ROOT / structural["sealed_cache"]).getroot()
        body = doc.find("body")
        three = r"(?:three|3)[\s‐-–-]+electrode"
        two = r"(?:two|2)[\s‐-–-]+electrode|symmetric (?:cell|device|supercapacitor)"
        links = []
        for hint in structural["figure_structure_hints"]:
            fid = hint["figure_id"]
            figure = body.find(f'.//fig[@id="{fid}"]')
            refs = [flat(p) for p in body.findall(".//p") if any(fid in x.get("rid", "").split() for x in p.findall(".//xref"))]
            links.append({"figure_id":fid,"graphic_count":len(figure.findall(".//graphic")),
                          "caption_mentions_3E":bool(re.search(three,flat(figure.find("caption")),re.I)),
                          "linked_text_mentions_3E":any(re.search(three,p,re.I) for p in refs),
                          "caption_or_linked_text_mentions_2E":any(re.search(two,p,re.I) for p in [flat(figure.find("caption")),*refs]),
                          "independent_early_markers_verified":0})
        structural["cycle_figure_role_hints"] = links
    structural.update(candidate_lock_commit=CANDIDATE_LOCK, endpoint_exposed=False, figure_viewed=False,
                      eligible_for_prediction_lock=False)
    persist(receipt_path, structural)


def persist(dest, report):
    payload = (json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if dest.exists():
        assert dest.read_bytes() == payload
    else:
        with dest.open("xb") as output:
            output.write(payload)
    print(dest.name, sha256(payload).hexdigest())


def main():
    plan_path = OUT / "screen_plan.json"
    plan = read(plan_path)
    frozen = subprocess.check_output(GIT + ["show", f"{FREEZE}:{plan_path.relative_to(ROOT).as_posix()}"], cwd=ROOT)
    assert frozen == plan_path.read_bytes()
    assert all(sha(ROOT / p) == h for p, h in plan["protected"].items())
    if sys.argv[1:] == ["screen-blind"]:
        screen_blind()
    else:
        persist(OUT / "npca_evidence.json", npca_evidence(plan))
        persist(OUT / "metadata_freeze.json", metadata(plan))


if __name__ == "__main__":
    main()
