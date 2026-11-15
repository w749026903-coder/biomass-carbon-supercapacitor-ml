"""Search Crossref and check open full-text structure without displaying endpoints."""

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import re
import subprocess
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import retention_prospective_screen_v70 as prior
from tools.retention_shape_mild_scope_v66 import GIT

OUT = prior.BASE / "第七十一轮_Crossref候选与全文结构_20261116"
CACHE = ROOT / ".local-literature-cache/P71"
CROSSREF = "https://api.crossref.org/works?"
QUERIES = (
    "biomass waste porous activated carbon supercapacitors cycling stability three electrode KOH",
    "fruit peel seed shell activated carbon supercapacitor 6 M KOH cycling 10000 cycles",
    "wood cellulose lignin bamboo porous carbon supercapacitor electrode specific capacitance cycling stability",
    "agricultural residue straw stalk leaves biomass carbon supercapacitor aqueous potassium hydroxide cycling",
)
CAPACITOR = re.compile(r"super.?capacit|ultra.?capacit|electrochemical capac", re.I)
EXCLUDE = re.compile(
    r"\breview\b|hydrogel|solid.state|lithium.ion|sodium.ion|zinc.ion|mxene|"
    r"\bcarbon cloth\b|\bhybrid\b|\basymmetric\b|\bmetal oxide\b|retract|correction", re.I
)


def search(query, page_size, latest):
    params = dict(rows=page_size, select="DOI,title,issued,publisher,type",
                  filter=f"type:journal-article,until-pub-date:{latest}")
    params["query.bibliographic"] = query
    try:
        response = json.loads(prior.get(CROSSREF + urlencode(params)))["message"]
    except (HTTPError, URLError, TimeoutError, ValueError, KeyError) as exc:
        return dict(query=query, error_type=type(exc).__name__, http=getattr(exc, "code", None), records=[])
    rows = []
    for item in response["items"]:
        title = (item.get("title") or [""])[0]
        title = re.sub(r"\s+", " ", re.sub(r"<[^>]*>", "", prior.unescape(title))).strip().rstrip(".")
        if item.get("DOI") and title and not re.search(r"\d\s*(?:%|percent\b)",title,re.I):
            rows.append(dict(doi=item["DOI"].lower(), title=title,
                             year=item["issued"]["date-parts"][0][0], publisher=item.get("publisher")))
    return dict(query=query, total=response["total-results"], returned=len(response["items"]), records=rows)


def project_doi_counts(dois):
    argv = ["rg","--hidden","--no-heading","--color","never","-i","-o","-F","--with-filename",
            "-g","*.md","-g","*.json","-g","*.csv","-g","*.xml","-g","*.html","-g","*.txt",
            "-g","!.git/**","-g","!**/第七十一轮_Crossref候选与全文结构_20261116/**","-g","!**/P71/**","-f","-","."]
    match = subprocess.run(argv,cwd=ROOT,input="\n".join(dois).encode(),capture_output=True)
    assert match.returncode in (0,1), match.stderr.decode("utf-8",errors="replace")
    paths = {doi:set() for doi in dois}
    for line in match.stdout.decode("utf-8").splitlines():
        loc, _, doi = line.rpartition(":")
        if doi.lower() in paths:
            paths[doi.lower()].add(loc)
    return {doi:len(files) for doi,files in paths.items()}


def locate(row):
    query = f'DOI:"{row["doi"]}" AND OPEN_ACCESS:Y'
    response = prior.metadata(query,5)
    matches = [item for item in response["rows"]
               if item["pmcid"] and (item["doi"] or "").lower() == row["doi"]]
    if not matches:
        return dict(doi=row["doi"],status="no_open_pmc_match",
                    lookup_error=response.get("error_type"),publisher_metadata=row["publisher"])
    row = dict(row,pmcid=matches[0]["pmcid"])
    return prior.inspect_structure(row)


def checked():
    path = OUT / "plan.json"
    assert subprocess.check_output([*GIT,"show",f"HEAD:{path.relative_to(ROOT).as_posix()}"],
                                   cwd=ROOT) == path.read_bytes()
    plan = prior.read(path)
    assert all(prior.sha(ROOT / key) == digest for key,digest in plan["protected"].items())
    return plan


def run():
    plan = checked()
    with ThreadPoolExecutor(max_workers=4) as pool:
        batches = list(pool.map(lambda q:search(q,plan["page_size"],plan["latest"]),plan["queries"]))
    unique = {}
    for batch in batches:
        for item in batch["records"]:
            unique.setdefault(item["doi"],item)
    plausible = [row for row in unique.values() if CAPACITOR.search(row["title"]) and
                 prior.TITLE.search(row["title"]) and prior.MATERIAL.search(row["title"]) and not EXCLUDE.search(row["title"])]
    dois = [row["doi"] for row in plausible]
    history, catalogs = (project_doi_counts(dois),prior.db_matches(dois)) if dois else ({},{})
    unseen, dedupe = [], []
    for row in plausible:
        doi = row["doi"]
        catalog = catalogs[doi]
        title_matches = 0
        if not any(catalog.values()) and not history[doi]:
            title_matches = len(prior.match_history(row["title"]))
            if not title_matches:
                unseen.append(row)
        dedupe.append(dict(doi=doi,history_doi_paths=history[doi],catalog=catalog,history_title_paths=title_matches))
    # Keep query relevance order. Publication date is recorded as context.
    shortlisted = unseen[:plan["max_fulltext_lookups"]]
    CACHE.mkdir(exist_ok=True)
    prior.CACHE = CACHE
    with ThreadPoolExecutor(max_workers=4) as pool:
        screened = list(pool.map(locate,shortlisted))
    result = dict(
        plan_sha256=prior.sha(OUT/"plan.json"),
        query_receipts=[{k:v for k,v in b.items() if k!="records"} for b in batches],
        unique_titles=len(unique), plausible_titles=len(plausible), dedupe=dedupe, unseen_metadata=unseen,
        screened=screened, endpoints_displayed=0, approved_early_inputs=0, new_predictions_locked=0,
    )
    with (OUT/"screen.json").open("x",encoding="utf-8",newline="\n") as stream:
        json.dump(result,stream,ensure_ascii=False,indent=2)
        stream.write("\n")
    print(len(unique),len(plausible),len(unseen),len(screened),
          sum(r["status"]=="structure_available" for r in screened),flush=True)


if __name__ == "__main__":
    run()
