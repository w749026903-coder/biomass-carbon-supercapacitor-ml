"""Audit the wood-carbon holdout against old abstract artifacts without printing endpoints."""

from hashlib import md5
import json
from pathlib import Path
import re
import subprocess
import sys
from xml.etree import ElementTree as ET
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.retention_wood_archive_v49 import BASE, DOI, COMPANION, db_matches, flat, frozen, read, sha

OUT = BASE/"第五十八轮_木源碳来源隔离与暴露核查_20261107"
CACHE = ROOT/".local-literature-cache/P58"
P31 = BASE/"第三十一轮_杉木屑双体系开发对照_20261105"
P57 = BASE/"第五十七轮_木源碳数据包与归一化证据_20261107"
JATS = ROOT/".local-literature-cache/P49/wood_epmc.xml"
PRE_RESERVATION = "cf0607d"
FREEZE = "0e7ecf6"
GIT = ["git","-c",f"safe.directory={ROOT.as_posix()}"]
ENDPOINT_LANGUAGE = (
    r"retention|retai(?:n|ned|ning)|capacity loss|capacitance loss",
    r"\b10[,\s]?000\s+(?:charge.discharge\s+)?cycles?\b",
    r"\d\s*(?:%|percent\b)",
)


def matches(query):
    call=subprocess.run([*GIT,"grep","-i","-I","-l","-F","-e",query,PRE_RESERVATION,"--",
                         "*.json","*.md","*.txt","*.csv","*.xml","*.html"],cwd=ROOT,capture_output=True)
    assert call.returncode in (0,1)
    return [line.split(":",1)[1] for line in call.stdout.decode("utf-8").splitlines()]


def entry_for_doi(node):
    if isinstance(node,dict):
        if isinstance(node.get("doi"),str) and node["doi"].casefold().rstrip("/").endswith(DOI):
            yield node
        else:
            for value in node.values():
                yield from entry_for_doi(value)
    if isinstance(node,list):
        for value in node:
            yield from entry_for_doi(value)


def abstract_flags(entry):
    abstract=entry.get("abstract") or entry.get("abstract_inverted_index")
    if isinstance(abstract,dict):
        abstract=" ".join(word for _,word in sorted((i,w) for w,places in abstract.items() for i in places))
    assert isinstance(abstract,str) and abstract
    sentences=re.split(r"(?<=[.!?])\s+(?=[A-Z])",abstract)
    return [i for i,s in enumerate(sentences,1) if all(re.search(pattern,s,re.I) for pattern in ENDPOINT_LANGUAGE)]


def audit():
    path=OUT/"screen_plan.json"
    plan=frozen(path,FREEZE)
    assert all(sha(ROOT/p)==h for p,h in plan["protected"].items())
    assert sha(JATS)==plan["sealed_main_jats_sha256"]
    doi_paths=matches(DOI)
    assert len(doi_paths)==3 and set(doi_paths)==set(matches("10.5281/zenodo.19549171"))
    history=[]
    for p in doi_paths:
        raw=subprocess.check_output([*GIT,"show",f"{PRE_RESERVATION}:{p}"],cwd=ROOT)
        entry,=entry_for_doi(json.loads(raw))
        flags=abstract_flags(entry)
        assert flags==[7]
        history.append(dict(path=p,has_terminal_sentence_flags=True,sentence_indexes=flags))
    catalogs=db_matches({DOI,COMPANION})
    assert not any(any(item.values()) for item in catalogs.values())
    snapshots=read(P31/"input_snapshot.json")
    folds={s:len({r["source_family"] for r in rows}) for s,rows in snapshots.items()}
    assert folds=={"3E":27,"2E":25}
    assert all(r["source_family"].lower().removeprefix("doi:") not in {DOI,COMPANION}
               for rows in snapshots.values() for r in rows)
    doc=ET.parse(JATS).getroot()
    refs=[]
    for el in doc.findall(".//ref-list/ref"):
        record=" ".join([flat(el),*(v for node in el.iter() for v in node.attrib.values())]).casefold()
        if COMPANION in record or ("carbon trends" in record and "100436" in record):
            refs.append(el.get("id"))
    cite,=refs
    sections=sorted({sec.get("id") for sec in doc.findall(".//body//sec")
                     if any(cite in x.get("rid","").split() for p in sec.findall("p") for x in p.findall(".//xref"))})
    assert len(sections)==5 and "smsc70209-sec-0007" in sections
    access=read(CACHE/"access.json")
    listing=CACHE/"converted_archive_listing.json"
    assert sha(listing)==access["converted_archive_listing"]["sha256"]
    item,=read(listing)["entries"]
    archive=CACHE/"companion_open_archive.zip"
    transport=read(CACHE/"companion_range.json")
    assert transport["http"]==206 and sha(archive)==transport["sha256"]
    assert "md5:"+md5(archive.read_bytes()).hexdigest()==item["checksum"]
    with ZipFile(archive) as z:
        members=[entry.filename for entry in z.infolist() if not entry.is_dir()]
    assert members==transport["members"] and not any(p.endswith((".csv",".xlsx",".tsv",".opju")) for p in members)
    early=read(P57/"early_observations.json")
    assert early["reported_cycle_current_A_g"] is None
    assert all(len(p["cycles"])==20 and p["cycles"][-1]==2000 for p in early["panels"].values())
    return dict(phase=58,freeze_commit=FREEZE,plan_sha256=sha(path),protection_checks=len(plan["protected"]),
        pre_reservation_commit=PRE_RESERVATION,main_doi=DOI,companion_doi=COMPANION,archive_doi="10.5281/zenodo.19549171",
        tracked_abstract_artifacts=history,training_catalog_exact_matches=catalogs,archived_fold_source_counts=folds,
        main_paper_companion_reference=cite,main_paper_citing_sections=sections,
        companion_primary_pdf="https://dspace.lu.lv/bitstreams/d9c81a56-0cf7-4c2f-844f-dd07f9894675/download",
        companion_reports_shared_sample_name="AWC 3-800",
        companion_cycle_run_identity="unverified; retain papers within one cluster",
        archive_access=access,converted_repository_receipt=transport,
        converted_repository_role="conversion software only",
        new_early_inputs=0,early_series_retained=3,endpoint_values_emitted=0,
        status="development_only_due_to_pre_reservation_abstract_terminal_exposure_risk",
        independent_blind_eligible=False,predictions_locked=0,new_fits=0,external_sources=0,canonical_admissions=0)


if __name__=="__main__":
    (OUT/"evidence.json").write_text(json.dumps(audit(),ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
