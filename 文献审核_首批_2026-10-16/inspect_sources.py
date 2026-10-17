"""Read-only source checks; outputs only in this new audit directory."""
from pathlib import Path
import json, hashlib, collections, sys
from pypdf import PdfReader

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
OUT = Path(__file__).resolve().parent
ledger_path = ROOT / "文献下载_120篇/下载归档最终台账.json"
blocked_path = ROOT / "文献扩充_生物质碳_120篇/禁止入库与待核查来源.json"
ledger = json.loads(ledger_path.read_text(encoding="utf-8-sig"))
blocked = json.loads(blocked_path.read_text(encoding="utf-8-sig"))
blocked_dois = {x["doi"].lower() for x in blocked}
checks = []
for rec in ledger:
    path = Path(rec["local_pdf"]) if rec.get("local_pdf") else None
    check = {"paper_id": rec["collection_id"], "doi": rec["doi"], "local_pdf": str(path) if path else None,
             "exists": bool(path and path.is_file()), "blocked": rec["doi"].lower() in blocked_dois,
             "download_status": rec.get("download_status"), "retrieval_status": rec.get("retrieval_status"),
             "eligible_for_database": rec.get("eligible_for_database")}
    if check["exists"]:
        check["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        check["expected_sha256"] = rec.get("sha256")
        check["hash_match"] = check["sha256"] == rec["sha256"] if rec.get("sha256") else None
        check["pages"] = len(PdfReader(path).pages)
    checks.append(check)
summary = {"candidate_count": len(ledger), "unique_dois": len({x["doi"].lower() for x in ledger}),
           "local_fulltext_count": sum(x["exists"] for x in checks),
           "missing_fulltext_count": sum(not x["exists"] for x in checks),
           "hash_mismatches": [x["paper_id"] for x in checks if x.get("hash_match") is False],
           "hash_unavailable": [x["paper_id"] for x in checks if x["exists"] and x.get("hash_match") is None],
           "blocked_in_candidates": [x["paper_id"] for x in checks if x["blocked"]],
           "blocked_count": len(blocked), "eligible_count": sum(x.get("eligible_for_database") is True for x in checks)}
supp_checks = []
for rec in ledger:
    for sup in rec.get("supplements", []):
        p = Path(sup["local_path"])
        digest = hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None
        supp_checks.append({"paper_id": rec["collection_id"], "path": str(p), "exists": p.is_file(),
                            "sha256": digest, "hash_match": digest == sup.get("sha256"), "role": sup.get("role")})
summary["supplement_count"] = len(supp_checks)
summary["supplement_failures"] = [x for x in supp_checks if not x["exists"] or not x["hash_match"]]
with (OUT / "文件复核.json").open("x", encoding="utf-8") as f:
    json.dump({"summary": summary, "ledger_sha256": hashlib.sha256(ledger_path.read_bytes()).hexdigest(),
               "blocked_sha256": hashlib.sha256(blocked_path.read_bytes()).hexdigest(),
               "papers": checks, "supplements": supp_checks}, f, ensure_ascii=False, indent=2)
for rec in ledger:
    if rec["collection_id"] not in {"B001", "B020", "B021"}:
        continue
    sources = [(rec["collection_id"], Path(rec["local_pdf"]))]
    sources += [(rec["collection_id"] + "_SI", Path(s["local_path"])) for s in rec.get("supplements", []) if s["local_path"].lower().endswith(".pdf")]
    for label, path in sources:
        pages = PdfReader(path).pages
        with (OUT / (label + "_逐页文本.txt")).open("x", encoding="utf-8") as f:
            for num, page in enumerate(pages, 1):
                f.write(f"\n\n===== PDF PAGE {num} =====\n" + page.extract_text())
        print(label, "pages", len(pages))
print(json.dumps(summary, ensure_ascii=False, indent=2))
