"""Audit cycling evidence with separate development and sealed-source paths."""

from concurrent.futures import ThreadPoolExecutor
import html
import json
from pathlib import Path
import re
import subprocess
import sys
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener
from xml.etree import ElementTree as ET

import numpy as np
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.prepare_small_sample_routes import read, sha, write
from tools.retention_blind_reserve_v22 import BASE, db_matches


OUT = BASE/"第四十三轮_循环工况与盲态来源复核_20261106"
P32 = BASE/"第三十二轮_盲态文献筛选扩充_20261105"
CACHE = ROOT/".local-literature-cache/P43"
TAK = ROOT/"同体系文献补充_第二批_20261017/定向扩搜40至60篇_20261017/sources/OA047/main.xml"


def flat(node):
    return " ".join("".join(node.itertext()).split())


def blind_roles(plan):
    registry = {r["doi"]: r for r in read(P32/"structural_screen.json")["results"]}
    records = {}
    for doi, (fid, panel) in {
        "10.1039/d2ra03949d": ("fig6", "e"),
        "10.1021/acsomega.1c00448": ("fig8", "c"),
    }.items():
        source = registry[doi]
        assert doi in plan["blind_existing"]
        path = ROOT/source["local"]
        assert sha(path) == source["sha256"]
        root = ET.parse(path).getroot()
        assert any(x.get("pub-id-type") == "doi" and x.text.lower() == doi for x in root.findall(".//article-id"))
        body = root.find("body")
        cap = flat(body.find(f'.//fig[@id="{fid}"]/caption'))
        pieces = re.split(r"\(([a-f])\)", cap)
        panel_text = pieces[pieces.index(panel)+1]
        linked = [flat(p) for p in body.findall(".//p")
                  if any(fid in x.get("rid", "").split() for x in p.findall(".//xref"))]
        if doi.startswith("10.1039"):
            assert "GOAC3" in panel_text and "capacitance retention" in panel_text.lower()
            assert any("GOAC3" in p and "two-electrode" in p.lower() for p in linked)
            headings = [flat(x) for x in body.findall(".//sec/title")]
            assert any("composite electrode (GOACs)" in x for x in headings)
            role = "GOAC3 graphene-activated carbon composite two-electrode device"
        else:
            assert re.search(r"cycl(?:ing|e)", panel_text, re.I)
            assert any("device" in p.lower() and "coulombic efficiency" in p.lower()
                       and "capacitance retention" in p.lower() for p in linked)
            role = "device cycling; no separate neat-lignin 3E cycling trace established"
        records[doi] = {"xml_sha256": source["sha256"], "figure_panel": fid+panel, "confirmed_role": role,
                        "3e_neat_carbon_early_inputs_added": 0, "endpoint_exposed": False}
    return records


def tak_curve():
    pdf_path = CACHE/"tak_publisher.pdf"
    assert sha(pdf_path) == "105e0d31416dbbe16c2f16555e583926fd73f5e492c50d2470c81f03238fec88"
    body = ET.parse(TAK).getroot().find("body")
    paragraphs = [flat(p) for p in body.findall(".//p")]
    method, = [p for p in paragraphs if "Electrochemical stability was evaluated at 7 A" in p]
    assert all(term in method for term in ("three-electrode", "saturated Ag/AgCl", "1 M KOH", "−1.0 to 0.0 V"))
    prose, = [p for p in paragraphs if "cycling stability of the TAK5 sample over 7000" in p]
    assert "close to 100%" in prose
    figure = PdfReader(pdf_path).pages[7].images[0].image
    assert figure.size == (1992, 3080)
    a = np.asarray(figure.convert("RGB")).max(axis=2)
    assert all((a[2871:2888, x] < 80).sum() > 10 for x in (248, 479, 711, 942, 1174, 1405, 1636, 1867))
    assert all((a[y, 222:240] < 80).sum() > 12 for y in (1609, 1860, 2111, 2360, 2611, 2861))

    def highlight(x, y, threshold):
        yy, xx = np.where(a[y-7:y+8, x-7:x+8] > threshold)
        assert len(xx) > 50
        return x-7+xx.mean(), y-7+yy.mean()

    offsets = []
    for x in (611, 703, 796):
        y = 1664
        h = highlight(x, y, 165)
        yy, xx = np.where(a[y-24:y+43, x-23:x+37] < 35)
        offsets.append((x-23+xx.mean()-h[0], y-24+yy.mean()-h[1]))
    assert np.ptp(offsets, axis=0).max() < 1
    dx, dy = np.mean(offsets, axis=0)
    sx = 7000/(1867.5-248.)
    sy = 100/(2861.5-1609.)
    records = []
    for seed in ((354, 1664), (424, 1664), (471, 1664), (516, 1664), (1860, 1670)):
        h = [highlight(*seed, t) for t in (155, 165, 175)]
        assert np.ptp(h, axis=0).max() < 2
        cx, cy = h[1][0]+dx, h[1][1]+dy
        cycle, retention = (cx-248.)*sx, (2861.5-cy)*sy
        records.append({"center_estimate_px": [float(cx), float(cy)], "cycles": float(cycle),
                        "cycle_geometry_interval": [float(cycle-12*sx), float(cycle+12*sx)],
                        "retention_pct": float(retention),
                        "ordinate_geometry_interval_pct": [float(retention-8*sy), float(retention+8*sy)]})
    ends = records[-1]["cycle_geometry_interval"]
    assert ends[0] < 7000 < ends[1]
    assert all(a["cycle_geometry_interval"][1] < b["cycle_geometry_interval"][0]
               for a, b in zip(records, records[1:]))
    windows = [sum(r["cycle_geometry_interval"][1] <= limit for r in records[:-1]) for limit in (700, 1400)]
    assert windows == [1, 4]
    return {"doi": "10.1021/acsomega.5c08826", "sample": "TAK5", "figure": "6(B)", "publisher_pdf_page": 8,
            "source_sha256": sha(pdf_path), "system": "3E", "current_A_g": 7, "electrolyte": "1 M KOH",
            "reference": "saturated Ag/AgCl", "gcd_potential_window_V": [-1., 0.], "cycle_count": 7000,
            "author_terminal_qualifier": "close to 100%", "author_exact_retention_pct": None,
            "early_markers": records[:-1], "early_markers_10_20": windows, "plot_terminal": records[-1],
            "role": "already-known long-cycle plateau control; graph ordinate and author qualitative statement kept separate"}


def exact_exists(term):
    result = subprocess.run(["rg", "-qiF", "-g", "*.{md,json,txt,csv,xml}", "-g",
                             "!**/第四十三轮_循环工况与盲态来源复核_20261106/**", term, "."],
                            cwd=ROOT, capture_output=True, check=False)
    assert result.returncode in (0, 1)
    return result.returncode == 0


def new_metadata(plan):
    path = CACHE/"metadata_lite.json"
    raw = read(path)
    rows = raw["resultList"]["result"]
    assert len(rows) <= plan["novel_metadata"]["max_page_size"]
    candidates = []
    for row in rows:
        assert "abstractText" not in row
        title = html.unescape(re.sub(r"<[^>]+>", "", html.unescape(row.get("title", ""))))
        if re.search(r"%|\b\d[\d,]*\s+cycles|review|correction|hybrid|composite|batter|symmetric|graphene|solid.state|"
                     r"oxide@|nanoparticles|nanosheets prepared from templating|promise of|near.zero.loss|metal nanocrystals", title, re.I):
            continue
        if not re.search(r"porous carbon|activated carbon|biomass.derived carbon", title, re.I):
            continue
        if not re.search(r"biomass|algae|agarose|peel|shell|seed|leaf|lignin|wood|corn|waste|straw|coconut", title, re.I):
            continue
        if not (row.get("doi") and row.get("pmcid") and row.get("isOpenAccess") == "Y" and row.get("hasPDF") == "Y"):
            continue
        candidates.append((row, title))
    candidates.sort(key=lambda item: item[0]["firstPublicationDate"], reverse=True)
    output, prior_matches, catalog_matches = [], [], []
    for row, title in candidates:
        doi = row["doi"].lower()
        doi_match = exact_exists(doi)
        if doi_match or exact_exists(title.rstrip(".")):
            prior_matches.append({"doi": doi, "exact_match_basis": "doi" if doi_match else "title"})
            continue
        matches = db_matches({doi})[doi]
        if any(matches.values()):
            catalog_matches.append({"doi": doi, "counts": matches})
            continue
        output.append({"doi": doi, "pmcid": row["pmcid"], "title": title,
                       "publication_date": row["firstPublicationDate"], "exact_catalog_matches": matches,
                       "role": "blind metadata reserve; test role, independence and early markers still need screening"})
        if len(output) == plan["novel_metadata"]["max_reserved"]:
            break
    return {"query_hit_count": raw["hitCount"], "records_read": len(rows), "metadata_sha256": sha(path),
            "title_and_access_candidates": len(candidates), "prior_matches": prior_matches,
            "catalog_matches": catalog_matches, "reserved": output}


def opac_routes():
    links = {
        "publisher_pdf": "https://www.sciencedirect.com/science/article/pii/S1387700321000824/pdfft?isDTMRedir=true&download=true",
        "publisher_standard": "https://api.elsevier.com/content/article/pii/S1387700321000824?httpAccept=text/xml",
        "publisher_full": "https://api.elsevier.com/content/article/pii/S1387700321000824?httpAccept=text/xml&view=FULL",
        "openalex": "https://api.openalex.org/works/https://doi.org/10.1016/j.inoche.2021.108523",
    }
    def check(item):
        name, url = item
        opener = build_opener(ProxyHandler({"https": "http://127.0.0.1:7890"}))
        try:
            with opener.open(Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=14) as r:
                status, data = r.status, r.read(1_000_001)
        except (HTTPError, URLError, TimeoutError) as e:
            return name, {"url": url, "http": getattr(e, "code", None), "access": type(e).__name__}
        result = {"url": url, "http": status}
        if name == "openalex":
            meta = json.loads(data)["open_access"]
            result.update(oa_status=meta["oa_status"], oa_url=meta["oa_url"])
        elif data.startswith(b"%PDF-"):
            result["access"] = "PDF available for a separate source verification"
        else:
            xml = ET.fromstring(data)
            tags = {x.tag.rsplit("}", 1)[-1] for x in xml.iter()}
            result["access"] = "metadata_only" if "coredata" in tags and "body" not in tags else "further_check_needed"
        return name, result
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = dict(pool.map(check, links.items()))
    return {"doi": "10.1016/j.inoche.2021.108523", "fig7_protocol_found": False,
            "route_checks": results, "prior_early_counts_retained": [1, 3],
            "required_source": "Original Fig. 7 cycling section or equivalent original evidence for configuration and actual cycling current"}


def main():
    path = OUT/"screen_plan.json"
    plan = read(path)
    assert sha(path) == "5b3df97f461a1a9ee78f35184c496610a522ee040d171fad815d53e3d5948b1a"
    correction_path = OUT/"freeze_hash_correction.json"
    correction = read(correction_path)
    guard = plan["protected"].copy()
    prior = correction["path"]
    assert guard[prior] == correction["transcribed_sha256"]
    guard[prior] = correction["verified_sha256"]
    assert all(sha(ROOT/f) == s for f, s in guard.items())
    assert subprocess.check_output(
        ["git", "-c", f"safe.directory={ROOT.as_posix()}", "show", correction["frozen_plan_commit"]+":"+prior],
        cwd=ROOT,
    ) == (ROOT/prior).read_bytes()
    target = OUT/"source_triage.json"
    assert not target.exists()
    result = {
        "frozen_plan_sha256": sha(path), "blind_roles": blind_roles(plan),
        "freeze_hash_correction_sha256": sha(correction_path),
        "tak": tak_curve(), "opac": opac_routes(), "new_metadata": new_metadata(plan),
        "new_blind_early_inputs": 0, "blind_endpoints_revealed": 0,
        "new_fits": 0, "admissions": 0, "independent_acceptances": 0,
    }
    write(target, result)


if __name__ == "__main__":
    if sys.argv[1:] == ["audit-metadata"]:
        write(OUT/"metadata_audit.json", new_metadata(read(OUT/"screen_plan.json")))
    else:
        main()
