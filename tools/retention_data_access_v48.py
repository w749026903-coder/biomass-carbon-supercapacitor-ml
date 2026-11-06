"""Audit three public records without importing their outcome labels into model inputs."""

from collections import Counter
from hashlib import md5, sha256
from io import BytesIO
import json
from pathlib import Path
import re
import subprocess
import sys
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.prepare_small_sample_routes import read, sha
from tools.retention_blind_reserve_v22 import BASE, db_matches

OUT = BASE / "第四十八轮_公开数据附件审查与阶段图表_20261106"
CACHE = ROOT / ".local-literature-cache/P48"
FREEZE = "ed32cd5"
GIT = ["git", "-c", f"safe.directory={ROOT.as_posix()}"]
SAMANEA_DOI = "10.1002/est2.616"
NS = {"w":"http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


def samanea(manuscript_path, snapshot_path):
    with ZipFile(manuscript_path) as archive:
        doc = ET.fromstring(archive.read("word/document.xml"))
        nodes = doc.findall(".//w:p", NS)
        texts = [" ".join("".join(n.text or "" for n in node.findall(".//w:t",NS)).split()) for node in nodes]
        paragraph, = [p for p in texts if "77.6% followed by" in p]
        caption, = [p for p in texts if p.startswith("Figure 6:")]
        assert "three-electrode" in paragraph and "good rate performance" in paragraph
        assert "fig. 6(e)" in paragraph and "comparison of specific capacitances" in caption
        assert "10 Ag−1" in paragraph and "H2SO4" in caption
        cycle, = [p for p in texts if "cyclic capacitance retention or cyclic stability" in p]
        explicit = next(s for s in re.split(r"(?<!Fig)\. ",cycle) if "cyclic capacitance retention or cyclic stability" in s)
        assert all(term in explicit for term in ("91.3 %", "94.3%", "5000 cycles", "Fig. 8(d)","H2SO4","Na2SO4"))
        assert not re.search(r"A\s*[/ ]?\s*g",explicit,re.I)
        assert "0.5-10 Ag−1" in cycle and "fig. S5" in cycle
        conclusion, = [p for p in texts if "99.6% and 99.8%" in p]
        assert "symmetric supercapacitor" in conclusion
        i8, = [i for i,p in enumerate(texts) if p.startswith("Figure 8:")]
        assert "(d) Cycle stability" in texts[i8]
        rel = {n.attrib["Id"]:n.attrib["Target"] for n in ET.fromstring(archive.read("word/_rels/document.xml.rels"))}
        panels = ["word/"+rel[value] for node in nodes[i8-3:i8] for n in node.iter()
                  for key,value in n.attrib.items() if key.endswith("}embed")]
        assert len(panels)==6 and panels[3]=="word/media/image36.png"
        image = archive.read(panels[3])
        with Image.open(BytesIO(image)) as panel:
            assert panel.size==(3216,2461)
        assert not any(name.startswith("word/embeddings/") for name in archive.namelist())
    metadata = read(snapshot_path)
    assert metadata["doi"]=="10.17632/3w6yb4d844.1" and metadata["version"]==1
    assert any(r["href"].endswith(SAMANEA_DOI) for r in metadata["related_links"])
    assert "files" not in metadata
    return {"known_project_source":"EXT_043","article_doi":SAMANEA_DOI,"accepted_manuscript_sha256":sha(manuscript_path),
            "dataset_identity_verified":True,"dataset_files_individually_verified":False,
            "3E_rate_test":{"panel":"6(e)","electrolyte":"H2SO4","current_density_A_g":10,
                            "relative_capacitance_pct":{"NSAC8":77.6,"NSAC7":66.0},"is_cycle_target":False},
            "2E_cycling":{"panel":"8(d)","cell":"NSAC8||NSAC8","cycles":5000,
                           "author_fig8d_retention_pct":{"H2SO4":91.3,"Na2SO4":94.3},"actual_cycle_current_A_g":None,
                           "conclusion_retention_pct_unbound_to_cycle_horizon":{"H2SO4":99.6,"Na2SO4":99.8},
                           "native_image":panels[3],"native_image_sha256":sha256(image).hexdigest(),
                           "native_image_dimensions":[3216,2461],"visually_reviewed_positive_markers_per_curve_by_10pct":0,
                           "visually_reviewed_positive_markers_per_curve_at_or_before_20pct_at_most":1,
                           "first_positive_marker_nominal_cycle":1000},
            "manuscript_raw_embedded_data_files":0,"development_only":True,
            "current_catalog_exact_matches":db_matches({SAMANEA_DOI})[SAMANEA_DOI]}


def dataverse(metadata_path, readme_path):
    data = read(metadata_path)["data"]["latestVersion"]
    assert data["datasetPersistentId"].casefold()=="doi:10.18710/f4nfmj"
    files = data["files"]
    info, = [x["dataFile"] for x in files if x["label"]=="README.txt"]
    assert info["checksum"]["type"]=="MD5" and md5(readme_path.read_bytes()).hexdigest()==info["checksum"]["value"]
    folders = Counter(x.get("directoryLabel","root") for x in files)
    readme = readme_path.read_text(encoding="utf-8-sig")
    assert re.search("cycling stability data", readme, re.I)
    described = re.findall(r"^-\s*(\w+)",readme,re.M)
    dedicated_cycling = [x["label"] for x in files
                         if re.search(r"cycle|cycling|durability|retention|stability",x["label"]+" "+x.get("directoryLabel",""),re.I)
                         and not re.search("cyclicvoltammetry",x["label"],re.I)]
    assert not dedicated_cycling and not any(re.search(r"cycling|durability|retention|stability",item,re.I) for item in described)
    pub = next(x["value"] for x in data["metadataBlocks"]["citation"]["fields"] if x["typeName"]=="publication")
    assert pub[0]["publicationCitation"]["value"]=="Submitted for review" and not pub[0].get("publicationIDNumber")
    assert len(files)==26 and folders["Electrochemistry/GalvanostaticChargeDischarge"]==2 and folders["Electrochemistry/RatePerformance"]==2
    return {"total_files":len(files),"folder_counts":dict(sorted(folders.items())),"dedicated_long_cycle_assets_in_inventory":dedicated_cycling,
            "readme_overview_mentions_cycling":True,"readme_file_list_has_dedicated_long_cycle_asset":False,
            "underlying_article_doi":None,"biomass_origin_confirmed":False,"readme_md5":info["checksum"]["value"],
            "disposition":"No dedicated long-cycle file located in the public inventory or the README listing. Raw CSV contents were not screened."}


def main():
    path = OUT/"screen_plan.json"
    plan = read(path)
    assert subprocess.check_output(GIT+["show",f"{FREEZE}:{path.relative_to(ROOT).as_posix()}"],cwd=ROOT)==path.read_bytes()
    assert all(sha(ROOT/p)==h for p,h in plan["protected"].items())
    first = read(CACHE/"access.json")
    alt = read(CACHE/"alternate_access.json")
    for name,item in first.items():
        if item["status"]=="downloaded":
            assert sha(CACHE/name)==item["sha256"]
    for item in alt.values():
        if item["status"]=="verified_payload":
            assert sha(CACHE/item["cache"])==item["sha256"]
    assert read(CACHE/"samanea_files.json")=={"error":400}
    assert first["nanda.csv"]["status"]=="unavailable"
    assert all(item.get("http")==403 for name,item in alt.items() if name.startswith("nanda_"))
    result={"freeze_commit":FREEZE,"primary_access":first,"alternate_access":alt,
            "nanda":{"record":"10.5281/zenodo.7882621","verified_downloads":0,"csv_header_verified":False,"rows_audited":0,
                     "repository_advertised_md5":plan["records"]["10.5281/zenodo.7882621"]["repository_md5"]},
            "samanea":samanea(CACHE/alt["samanea_spiral_api"]["cache"],CACHE/alt["samanea_mendeley_snapshot"]["cache"]),
            "dataverse":dataverse(CACHE/"dataverse.json",CACHE/alt["dataverse_readme"]["cache"]),
            "new_early_inputs":0,"predictions_locked":0,"new_fits":0,"canonical_admissions":0,"independent_acceptances":0}
    payload=(json.dumps(result,ensure_ascii=False,indent=2)+"\n").encode()
    output=OUT/"evidence.json"
    if output.exists():
        assert output.read_bytes()==payload
    else:
        with output.open("xb") as stream: stream.write(payload)
    print(output.name,sha(output))


if __name__ == "__main__":
    main()
