"""Find previously unlisted article candidates without exposing retention endpoints."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from html import unescape
import json
from pathlib import Path
import re
import subprocess
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import ProxyHandler, build_opener
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.retention_blind_reserve_v22 import BASE, ENDPOINT, db_matches, flat
from tools.retention_shape_mild_scope_v66 import GIT
from tools.retention_shape_v4 import read, sha, write

OUT = BASE / "第七十轮_定向盲测计划与题录筛查_20261116"
CACHE = ROOT / ".local-literature-cache/P70"
PROXY = {"https": "http://127.0.0.1:7890"}
QUERIES = (
    'TITLE_ABS:supercapacitor* AND (TITLE_ABS:"biomass-derived" OR TITLE_ABS:"porous carbon") AND '
    'TITLE_ABS:KOH AND TITLE_ABS:"three-electrode" AND OPEN_ACCESS:Y',
    'TITLE:supercapacitor* AND (TITLE:biomass OR TITLE:straw OR TITLE:peel OR TITLE:shell OR TITLE:seed) AND '
    'TITLE_ABS:KOH AND TITLE_ABS:cycling AND OPEN_ACCESS:Y',
    'TITLE_ABS:supercapacitor* AND (TITLE:biochar OR TITLE:"activated carbon" OR TITLE:"biomass derived") '
    'AND (TITLE_ABS:"10000 cycles" OR TITLE_ABS:"10,000 cycles") AND OPEN_ACCESS:Y',
)
TITLE = re.compile(r"carbon|biochar", re.I)
MATERIAL = re.compile(r"biomass|plant|leaf|leaves|straw|peel|shell|seed|wood|waste|bagasse|biowaste|"
                      r"bamboo|lignin|cellulose|husk|algae|biochar|flower|grass|pomace|stalk|fruit", re.I)
EXCLUDE = re.compile(r"review|hydrogel|asymmetric|solid.state|lithium.ion|sodium.ion|zinc.ion|mxene|hybrid", re.I)


def checked():
    path = OUT / "plan.json"
    assert subprocess.check_output([*GIT, "show", f"HEAD:{path.relative_to(ROOT).as_posix()}"],
                                   cwd=ROOT) == path.read_bytes()
    plan = read(path)
    assert all(sha(ROOT / p) == digest for p,digest in plan["protected"].items())
    return plan


def get(url):
    opener = build_opener(ProxyHandler(PROXY))
    with opener.open(url, timeout=18) as response:
        return response.read()


def metadata(query, page_size):
    url = ENDPOINT + "search?" + urlencode(dict(query=query, format="json", resultType="lite", pageSize=page_size))
    try:
        source = json.loads(get(url))
        allowed = ("doi", "pmcid", "title", "authorString", "firstPublicationDate", "isOpenAccess")
        return dict(query=query, hit_count=source["hitCount"],
                    rows=[{key:r.get(key) for key in allowed} for r in source["resultList"]["result"]])
    except (HTTPError, URLError, TimeoutError, ValueError) as error:
        return dict(query=query, error_type=type(error).__name__, http=getattr(error, "code", None), rows=[])


def match_history(pattern):
    argv = ["rg", "--hidden", "-ilF", "-g", "*.md", "-g", "*.json", "-g", "*.csv", "-g", "*.xml",
            "-g", "*.html", "-g", "*.txt", "-g", "!.git/**", "-g",
            "!**/第七十轮_定向盲测计划与题录筛查_20261116/**", "-g", "!**/P70/**", "--", pattern, "."]
    result = subprocess.run(argv, cwd=ROOT, capture_output=True, check=False)
    assert result.returncode in (0,1), result.returncode
    return result.stdout.decode("utf-8").splitlines()


def inspect_structure(row):
    pmc = row["pmcid"]
    try:
        payload = get(ENDPOINT + pmc + "/fullTextXML")
        document = ET.fromstring(payload)
    except (HTTPError, URLError, TimeoutError, ET.ParseError) as error:
        return dict(doi=row["doi"], pmcid=pmc, status="access_unavailable",
                    error_type=type(error).__name__, http=getattr(error,"code",None))
    ids = [flat(node).casefold() for node in document.findall(".//article-meta/article-id")
           if node.get("pub-id-type") == "doi"]
    if row["doi"] not in ids:
        return dict(doi=row["doi"], pmcid=pmc, status="identity_mismatch")
    cache = CACHE / f"{pmc}.sealed.xml"
    with cache.open("xb") as file:
        file.write(payload)
    body = document.find("body")
    methods = []
    figures = []
    if body is not None:
        for section in body.findall(".//sec"):
            title = section.find("title")
            if title is not None and re.search(r"experimental|methods?|electrochemical (?:measurement|test|character)",flat(title),re.I):
                methods.extend(flat(p) for p in section.findall("p"))
        for fig in body.findall(".//fig"):
            caption = fig.find("caption")
            if caption is None:
                continue
            text = flat(caption)
            if re.search(r"cycl(?:ing|ic|e)\s+(?:stabilit|durabilit|life|performance)|capacitance retention|"
                         r"\b(?:consecutive|charge.discharge) cycles\b",text,re.I):
                figures.append(dict(id=fig.get("id"), explicit_3e=bool(re.search(r"three[\s–-]+electrode|\b3E\b",text,re.I)),
                    explicit_2e=bool(re.search(r"two[\s–-]+electrode|symmetric device|\b2E\b",text,re.I)),
                    assets=[value for graphic in fig.findall(".//graphic") for key,value in graphic.attrib.items()
                            if key.endswith("href")]))
    method_text = " ".join(methods)
    return dict(doi=row["doi"],pmcid=pmc,status="structure_available",sealed_xml_sha256=sha(cache),
                methods_mention_3e=bool(re.search(r"three[\s–-]+electrode|\b3E\b",method_text,re.I)),
                methods_mention_koh=bool(re.search(r"\bKOH\b",method_text,re.I)),cycling_figures=figures)


def run():
    plan = checked()
    CACHE.mkdir(exist_ok=True)
    with ThreadPoolExecutor(max_workers=3) as pool:
        batches = list(pool.map(lambda q:metadata(q,plan["page_size"]),plan["queries"]))
    records = {}
    for batch in batches:
        for row in batch["rows"]:
            if row["doi"] and row["pmcid"] and row["title"] and row["isOpenAccess"] == "Y":
                row["doi"] = row["doi"].casefold()
                row["title"] = re.sub(r"<[^>]*>", "", unescape(row["title"])).strip().rstrip(".")
                records.setdefault(row["doi"], row)
    plausible = [row for row in records.values() if TITLE.search(row["title"])
                 and MATERIAL.search(row["title"]) and not EXCLUDE.search(row["title"])]
    plausible.sort(key=lambda row:(row["firstPublicationDate"] or "",row["doi"]),reverse=True)
    catalogs = db_matches([row["doi"] for row in plausible])
    candidates, reviewed = [], []
    for row in plausible:
        doi = row["doi"]
        history_doi = match_history(doi)
        if any(catalogs[doi].values()) or history_doi:
            reviewed.append(dict(doi=doi,catalog=catalogs[doi],project_doi_matches=len(history_doi)))
            continue
        history_title = match_history(row["title"])
        reviewed.append(dict(doi=doi,catalog=catalogs[doi],project_doi_matches=0,project_title_matches=len(history_title)))
        if not history_title:
            candidates.append(row)
        if len(candidates) >= plan["max_structural_candidates"]:
            break
    with ThreadPoolExecutor(max_workers=3) as pool:
        structures = list(pool.map(inspect_structure,candidates))
    result = dict(
        checked_at=datetime.now().astimezone().isoformat(),plan_sha256=sha(OUT/"plan.json"),
        query_receipts=[{k:v for k,v in batch.items() if k!="rows"} |
                        {"returned":len(batch["rows"])} for batch in batches],
        unique_open_pmc_dois=len(records), plausible_titles=len(plausible), dedupe_review=reviewed,
        reserved_metadata=candidates, structures=structures, terminal_values_displayed=0,
        approved_early_inputs=0, prediction_locks=0, revealed_sources=0, formal_acceptance=False,
    )
    with (OUT/"screen.json").open("x",encoding="utf-8",newline="\n") as file:
        json.dump(result,file,ensure_ascii=False,indent=2)
        file.write("\n")
    print(f"{len(records)} unique DOI, {len(plausible)} plausible titles, "
          f"{len(candidates)} reserved, {sum(s['status']=='structure_available' for s in structures)} full texts")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("step",choices=("queries","run"))
    if parser.parse_args().step == "queries":
        print(json.dumps(QUERIES))
    else:
        run()
