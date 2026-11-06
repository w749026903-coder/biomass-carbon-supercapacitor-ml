"""Verify downloaded archives and release only metadata for retention screening."""

import argparse
from collections import Counter
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import re
import subprocess
from xml.etree import ElementTree as ET
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "保持率达标研究_v3_主线与近优组合_20261030"
OUT = BASE / "第五十一轮_公开逐圈数据筛查与阶段图表_20261107"
CACHE = ROOT / ".local-literature-cache/P51"
FREEZE = "435b81c"
NMOVC_DOI = "10.1007/s11581-025-06590-w"
NUMBER = re.compile(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?")


def read(name):
    return json.loads((CACHE / name).read_bytes())


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def receipt(path, catalog):
    sha = digest(path)
    assert sha == catalog["content_details"]["sha256_hash"]
    assert path.stat().st_size == catalog["size"] == catalog["content_details"]["size"]
    return {"filename": catalog["filename"], "bytes": path.stat().st_size, "sha256": sha}


def inspect_tpac(seven_zip):
    path = CACHE / "tpac_source_sealed.rar"
    item, = read("rwzdbth4jx_public.body")
    archive = receipt(path, item)
    names = subprocess.check_output(["tar", "-tf", str(path)], timeout=15).decode("utf-8").splitlines()
    listing = subprocess.check_output(["tar", "-tvf", str(path)], timeout=15).splitlines()
    assert len(listing) == len(names) == 41 and all(row[:1] in (b"-", b"d") for row in listing)
    files = [name for name, row in zip(names, listing) if row.startswith(b"-")]
    assert len(files) == 25
    types = Counter(Path(name).suffix.casefold() for name in files)
    assert types == {".pdf": 4, ".xls": 4, ".docx": 3, ".txt": 4, ".xy": 4, ".emf": 2, ".csv": 2, ".xrdml": 2}
    assert all("/xrd data/" in name.casefold() for name in files if name.casefold().endswith(".csv"))
    assert all(any(f"/{test} data/" in name.casefold() for test in ("ftir", "bet"))
               for name in files if name.casefold().endswith(".xls"))

    def extract(member):
        # Send exactly one allowlisted member to memory, without expanding the archive to disk.
        return subprocess.check_output([seven_zip, "x", "-so", "-y", "-bd", "-spd", str(path), member], timeout=15)

    doc, = [name for name in files if Path(name).name == "CV GCD EIS data.docx"]
    raw_doc = extract(doc)
    with ZipFile(BytesIO(raw_doc)) as zipped:
        members = zipped.namelist()
        text = ET.fromstring(zipped.read("word/document.xml"))
        images = [n for n in members if re.fullmatch(r"word/media/image\d+\.png", n)]
        assert len(images) == 11 and not text.findall(".//{*}tbl")
        assert not any(name.startswith(("word/embeddings/", "word/charts/")) for name in members)

    thermal = {}
    for name in files:
        if "/tgasonular/" not in name.casefold() or not name.casefold().endswith(".txt"):
            continue
        raw = extract(name)
        lines = raw.decode("utf-8", errors="replace").splitlines()
        header = next(line for line in lines[:20] if all(term in line for term in ("Time", "Temperature", "TG", "dTG")))
        assert not re.search(r"cycle|capacitance", header, re.I)
        rows = sum(len(fields) == 4 and all(NUMBER.fullmatch(field) for field in fields)
                   for fields in (re.split(r"[\s,;]+", line.strip()) for line in lines))
        assert rows == 11850
        thermal["MgO@TPAC" if "mgo@" in name.casefold() else "TPAC"] = {
            "numeric_rows": rows, "sha256": sha256(raw).hexdigest(), "axis_roles": ["time", "temperature", "TG", "dTG"]}
    assert set(thermal) == {"TPAC", "MgO@TPAC"}
    return {"dataset_doi": "10.17632/rwzdbth4jx.1", "archive": archive, "members": len(files),
            "member_types": dict(sorted(types.items())), "thermal_tables": thermal,
            "electrochem_document": {"sha256": sha256(raw_doc).hexdigest(), "png_figures": len(images),
                                      "native_tables": 0, "native_charts": 0, "embedded_files": 0},
            "article_doi": None, "electrochem_axes_classified": False,
            "disposition": "hold_no_machine_readable_cycling_table_located_and_test_binding_unverified"}


def inspect_nmovc():
    path = CACHE / "h63_source_sealed.zip"
    item, = read("h63_folder_members.json")
    folder, = read("h63ydcsjd6_folders_v1.json")
    assert not read("h63ydcsjd6_public.body")
    archive = receipt(path, item)
    data = read("h63ydcsjd6_doi.body")["data"]["attributes"]
    assert data["doi"] == "10.17632/h63ydcsjd6.1"
    assert any("full battery data" in d["description"].casefold() for d in data["descriptions"])
    paper, = [row for row in read("nmovc_crossref.json")["message"]["items"] if row["DOI"] == NMOVC_DOI]
    assert "NMOVC cathode composite materials for aqueous sodium-ion batteries" in paper["title"][0]
    assert (paper["author"][0]["given"], paper["author"][0]["family"]) == ("Bo", "Ding")
    with ZipFile(path) as zipped:
        names = [n.filename for n in zipped.infolist() if not n.is_dir()]
    cycles = [Path(n).name for n in names if "cycle" in Path(n).name.casefold()]
    assert len(names) == 16 and len(cycles) == 4 and any(n.endswith("/Battery Date.xls") for n in names)
    assert any("NMOVC" in n for n in cycles)
    return {"dataset_doi": data["doi"], "archive": archive, "folder": folder["name"], "members": len(names),
            "cycling_file_names": sorted(cycles), "battery_workbook_listed": True, "battery_workbook_values_read": False,
            "matched_article": {"doi": NMOVC_DOI, "title": paper["title"][0],
                                "match_evidence": "author and NMOVC sample label; deposit has no explicit article link"},
            "out_of_scope_outcome_in_bibliographic_search_snippet": True,
            "disposition": "exclude_battery_capacity_retention"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seven-zip", default="7z", help="Existing 7-Zip executable")
    parser.add_argument("--write", action="store_true", help="Write a new evidence file")
    args = parser.parse_args()
    path = OUT / "screen_plan.json"
    git = ["git", "-c", f"safe.directory={ROOT.as_posix()}"]
    assert subprocess.check_output(git + ["show", f"{FREEZE}:{path.relative_to(ROOT).as_posix()}"], cwd=ROOT) == path.read_bytes()
    plan = json.loads(path.read_bytes())
    assert all(digest(ROOT / name) == h for name, h in plan["protected"].items())
    tpac, nmovc = inspect_tpac(args.seven_zip), inspect_nmovc()
    assert [r["dataset_doi"] for r in (tpac, nmovc)] == [c["doi"] for c in plan["candidates"]]
    prior_root = read("samanea_probe_root.json")
    prior_folders = read("samanea_probe_folders.json")
    assert not prior_root and len(prior_folders) == 14
    evidence = {"phase": 51, "freeze_commit": FREEZE, "plan_sha256": digest(path),
                "archives_verified": 2, "candidates": [tpac, nmovc],
                "public_access": {"root_listing": "GET /public-api/datasets/{id}/files?folder_id=root&version=1",
                                  "folder_listing": "GET /public-api/datasets/{id}/folders/1",
                                  "nested_listing": "GET /public-api/datasets/{id}/files?folder_id={folder_id}&version=1",
                                  "downloads_validated_against_public_catalog_sha256": True},
                "next_metadata_only": {"dataset_doi": "10.17632/3w6yb4d844.1", "root_files": 0, "folders": 14,
                                       "member_bodies_examined": 0},
                "new_early_inputs": 0, "new_fits": 0, "prediction_locks": 0, "in_scope_endpoints_revealed": 0,
                "canonical_admissions": 0, "external_acceptances": 0}
    dest = OUT / "evidence.json"
    payload = json.dumps(evidence, ensure_ascii=False, indent=2) + "\n"
    if args.write:
        with dest.open("x", encoding="utf-8", newline="\n") as f:
            f.write(payload)
    assert dest.read_bytes() == payload.encode("utf-8")
    print("Two archive SHA-256 checks, 41 file members across two archives, six protected hashes. Usable early inputs: 0.")


if __name__ == "__main__":
    main()
