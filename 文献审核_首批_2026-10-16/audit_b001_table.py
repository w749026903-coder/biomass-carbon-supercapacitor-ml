from pathlib import Path
import re, json, csv, collections, sys
from decimal import Decimal
from pypdf import PdfReader
sys.stdout.reconfigure(encoding="utf-8")
OUT = Path(__file__).resolve().parent
source = Path(r"D:\文献\补充材料_120篇\B001__CPLU-90-e202500342-s001.pdf")
names = ["activation_temperature_raw", "activation_time_raw", "carbonisation_temperature_raw", "carbonisation_time_raw", "surface_area_m2_g", "pore_volume_cm3_g", "voltage_window_V", "current_density_A_g", "capacitance_F_g"]
rows = []
with source.open("rb") as stream:
    doc = PdfReader(stream)
    for page_num in range(2,9):
        text = doc.pages[page_num-1].extract_text()
        text = re.sub(r"(?m)^\s*(?:\d+|\[OFFICIAL\])\s*$", "", text)
        matches = list(re.finditer(r"(?m)^\s*(\d+)\s+(10\.\S+)\s+", text))
        for i, match in enumerate(matches):
            block = text[match.end():matches[i+1].start() if i+1 < len(matches) else len(text)].strip()
            tokens = block.split()
            assert len(tokens) >= 12, (page_num, match.group(1), block)
            numbers = tokens[-9:]
            for value in numbers:
                try:
                    Decimal(value)
                except Exception as exc:
                    raise ValueError((page_num, match.group(1), block)) from exc
            rows.append({"row_id": int(match.group(1)), "source_doi": match.group(2),
                         "categorical_prefix_raw": " ".join(tokens[:-9]),
                         **dict(zip(names, numbers)), "pdf_page": page_num,
                         "table": "S1", "audit_status": "quarantined_secondary_table_not_original_verified", "eligible_for_database": False})
assert [r["row_id"] for r in rows] == list(range(1,167))
def signature(r, target=True):
    ns = names if target else names[:-1]
    return (r["source_doi"].lower(), r["categorical_prefix_raw"].lower(), *(Decimal(r[k]) for k in ns))
exact, inputs = collections.defaultdict(list), collections.defaultdict(list)
for row in rows:
    exact[signature(row)].append(row["row_id"])
    inputs[signature(row,False)].append(row)
duplicates = [group for group in exact.values() if len(group)>1]
conflicts = [{"row_ids": [r["row_id"] for r in group], "capacitances_F_g": [r["capacitance_F_g"] for r in group], "doi": group[0]["source_doi"]}
             for group in inputs.values() if len({Decimal(r["capacitance_F_g"]) for r in group})>1]
dois = collections.Counter(r["source_doi"].lower() for r in rows)
summary = {"row_count": len(rows), "unique_source_dois": len(dois), "exact_duplicate_groups": duplicates,
           "same_listed_input_different_target_groups": conflicts,
           "independent_material_count": None, "warning": "Same listed inputs do not establish identical physical samples; omitted identifiers or conditions may explain conflicts. All S1 rows remain quarantined."}
with (OUT / "B001_S1_隔离摘录.json").open("x", encoding="utf-8") as f:
    json.dump({"source": str(source), "summary": summary, "records": rows}, f, ensure_ascii=False, indent=2)
with (OUT / "B001_S1_原始来源DOI.csv").open("x", newline="", encoding="utf-8-sig") as f:
    writer=csv.writer(f); writer.writerow(["source_doi", "record_count_in_S1", "original_verified"])
    for doi, count in dois.items(): writer.writerow([doi,count,False])
print(json.dumps(summary, ensure_ascii=False, indent=2))
