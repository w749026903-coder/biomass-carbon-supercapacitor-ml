from pathlib import Path
import sys
import pypdfium2 as pdfium
import pdfplumber
sys.stdout.reconfigure(encoding="utf-8")
OUT = Path(__file__).resolve().parent
sources = {
    "B001": (r"D:\文献\B001__10.1002__cplu.202500342.pdf", [2,3,4,5,10]),
    "B001_SI": (r"D:\文献\补充材料_120篇\B001__CPLU-90-e202500342-s001.pdf", [3,8,9]),
    "B020": (r"D:\文献\E07__10.3390__nano12213804.pdf", [2,3,8,9]),
    "B021": (r"D:\文献\E09__10.3390__molecules27030791.pdf", [2,3,4,8]),
}
for label, (source, selected) in sources.items():
    with pdfplumber.open(source) as doc:
        with (OUT / (label + "_排版文本.txt")).open("x", encoding="utf-8") as f:
            for num, page in enumerate(doc.pages,1):
                f.write(f"\n\n===== PDF PAGE {num} =====\n" + (page.extract_text() or ""))
    doc = pdfium.PdfDocument(source)
    for num in selected:
        target = OUT / f"{label}_p{num:02d}.png"
        if target.exists():
            raise FileExistsError(target)
        doc[num-1].render(scale=1.6).to_pil().save(target)
    print(label, "rendered", selected)
