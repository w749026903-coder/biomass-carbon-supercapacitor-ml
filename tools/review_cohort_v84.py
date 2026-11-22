"""Build round 84's source-reviewed three-electrode retention cohort from frozen inputs."""
import argparse
import csv
import hashlib
import json
import sqlite3
from pathlib import Path

import numpy as np
import pypdfium2 as pdfium

ROOT = Path(__file__).resolve().parents[1]
BASE = next(ROOT.glob("保持率达标研究_v3*"))
P39 = next(BASE.glob("第三十九轮*"))
P40 = next(BASE.glob("第四十轮*"))
P81 = next(BASE.glob("第八十一轮*"))
P82 = next(BASE.glob("第八十二轮*"))
P83 = next(BASE.glob("第八十三轮*"))
DEFAULT = BASE / "第八十四轮_三电极归属修正与早期曲线_20261122"
POMELO = "10.1039/d0na00778a"

# Positions are in crops of pages rendered to 1790 pixels across. Anchors are
# visually identifiable symbol centres, not a regularly spaced interpolation.
# axes: x=0, x=target, y=0%, y=100%; band bounds exclude neighbouring axes.
PANELS = {
    "10.1016/j.ultsonch.2026.108104": (11, "7b", (167,121,324,254), (165,655,532,164), (166,178), "black",
        [169,174,179,184,189,194,199,204,208,213,218,223,228,233,238,243,248,253,258], "pp.3,9,11–12；AC700黑色左轴，橙色对应库仑效率。"),
    "10.1039/d1ra06154b": (7, "7d", (25,309,258,428), (137,999,454,206), (195,230), "green",
        [147,156,164,173,181,190,198,207,216,225,233,242,250,259,267,276,285,293,302], "pp.1,6–7；YPC-4绿色圆点，插图为充放电曲线。"),
    "10.1039/d3ra04164f": (7, "5f", (195,86,345,203), (266.5,623,437,169), (163,186), "red",
        [274,281,288,295,302,309,316,323,330], "pp.6–7；OAC-4-700红色圆点。"),
    "10.3390/nano12234204": (8, "5f", (185,113,343,239), (264,612,434,166), (155,185), "red",
        [278,292,306,320], "pp.3,7–8；MGCs-2红色菱形。摘要>96%，结果段96%，仅供敏感性分析。"),
}
ISSUES = [
    ("10.1039/c8ra07587e","CACNF-ZnCl2-20%","exclude_2e","pp.6–8 Fig.6 / Fig.7d","第7图明确为双电极6 M KOH。第6图才是三电极。5000圈92%移出三电极清单，保留器件原值。"),
    ("10.3390/nano15040304","DC-900","freeze_label","p.6 Fig.3g / p.7","图内绿色容量标注90.3%，橙色98.3%为效率。正文写92.4%。两项容量原值同时保留。"),
    ("10.1021/acsomega.5c08826","TAK5","review_plot","p.8 Fig.6B / abstract","图上末点约94%，原标签98%来自摘要；待核作者数值或原始序列。"),
    ("10.1016/j.heliyon.2023.e21804","FPC","review_plot","p.8 Fig.6","图内文字98.4%，按纵轴末点约96%。保留原约数，暂缓配对早期点。"),
    ("10.1021/acsomega.9b01977","WW-KOH9","review_plot","p.6 Fig.7d","图上末点约92%，原文约94%。在图读误差和原始序列进一步核对前暂缓。"),
    ("10.3390/molecules31132329","AHPC-850","review_plot","p.14 Fig.4d / p.15","红色左轴绘制保持率，末点约93%，图内文字和正文写96.3%。只标记AHPC-850。"),
    ("10.1039/d0ra07448a","BSAC-A-800","baseline_needed","p.8 Fig.7","纵轴为比电容。将曲线换算成保持率还需能定位作者的初始归一化参照。"),
    ("10.3390/polym17091198","CMC-ZnK-800","baseline_needed","p.11 Fig.8d","曲线图左轴为比电容，右轴也有百分数。双轴对应关系及归一化基准尚待核验。"),
]
def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def get(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))

def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False)+"\n", encoding="utf8")

def csvwrite(path, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

def relative(path):
    return path.relative_to(ROOT).as_posix()

def features(points, target):
    x = np.array([p["cycle"] for p in points])
    y = np.array([p["pct"] for p in points])
    assert len(x) >= 3 and np.all(np.diff(x)>0)
    assert all(0 < p["cycle_interval"][0] <= p["cycle"] <= p["cycle_interval"][1] < target*.2 for p in points)
    return dict(last_early_retention_pct=float(y[-1]), early_mean_retention_pct=float(y.mean()),
                early_retention_slope_per_1000_cycles=float(np.polyfit(x/1000,y,1)[0]),
                early_retention_range_pp=float(np.ptp(y)), early_observed_cycle_count=float(x[-1]),
                target_cycle_count=float(target))

def read_panel(doi, path, target):
    page_no, figure, roi, axes, band, colour, anchors, note = PANELS[doi]
    with pdfium.PdfDocument(path) as doc:
        page = doc[page_no-1]
        bitmap = page.render(scale=1790/page.get_size()[0])
        image = bitmap.to_pil().convert("RGB").crop(tuple(p*5 for p in roi))
        rgb = np.asarray(image, dtype=int)
    r,g,b = rgb.transpose(2,0,1)
    x0,x1,y0,y100 = axes
    dx = 3*target/(x1-x0)
    dy = 3*100/(y0-y100)
    points = []
    for x in anchors:
        centers = []
        for thr in (50,70,90):
            if colour == "black":
                mask = np.maximum.reduce([r,g,b]) < thr+25
            elif colour == "green":
                mask = (g>r+thr*.65)&(g>b+thr*.65)
            else:
                mask = (r>g+thr)&(r>b+thr)
            ys = np.where(mask[band[0]:band[1],x-1:x+2])[0]+band[0]
            assert len(ys) >= 3, (doi,x,thr)
            centers.append(float((ys.min()+ys.max())/2))
        assert max(centers)-min(centers) <= 2, (doi,x,centers)
        cycle = (x-x0)*target/(x1-x0)
        value = (y0-centers[1])*100/(y0-y100)
        points.append(dict(x_px=x,y_px_by_threshold=centers,cycle=cycle,cycle_interval=[cycle-dx,cycle+dx],
                           pct=value,pct_interval=[value-dy,value+dy]))
    return dict(pdf=relative(path),sha256=digest(path),page=page_no,figure=figure,trace=colour,
                crop_px=[p*5 for p in roi],page_width_px=1790,axis_0_N_0pct_100pct=axes,
                geometry_margin_px=3,vertical_search_band_px=band,marker_points=points,protocol=note,
                features=features(points,target))

def build(out):
    out.mkdir(parents=True,exist_ok=False)
    with (P83/"同工况50篇逐篇清单.csv").open(encoding="utf-8-sig") as f:
        book={r["DOI"]:r for r in csv.DictReader(f)}
    old=get(P82/"逐测试证据.json")
    records=[dict(r) for r in old]
    prior=get(P83/"同工况早期曲线输入.json")
    p81={r["id"]:r for r in get(P81/"inputs.json")["early_B"]}
    assert all(p81[r["id"]]["train"] for r in prior if r["id"] in p81)
    assert len(book)==50 and len(records)==63 and len(prior)==28
    source_path=lambda d: ROOT/book[d]["正文PDF"]
    refs={d:dict(path=relative(source_path(d)),sha256=digest(source_path(d))) for d in sorted(set(PANELS)|{a[0] for a in ISSUES})}
    prior_pdf=get(P82/"核验.json")["files"]
    assert all(v["sha256"]==prior_pdf[d]["sha256"] for d,v in refs.items())
    newrows=[dict(r,use="development",source_round=83) for r in prior]
    ev={}
    for doi in PANELS:
        record,=[r for r in old if r["doi"]==doi]
        ev[doi]=read_panel(doi,source_path(doi),record["cycles"])
        use="sensitivity_only" if record["relation"]=="abstract_gt_vs_results_eq" else "development"
        newrows.append(dict(id=record["id"],doi=doi,features=ev[doi]["features"],retention_pct=record["retention_pct"],use=use,source_round=84))
    removed=ISSUES[0][0]
    removed_row,=[r for r in old if r["doi"]==removed]
    assert removed_row["retention_pct"]==92 and not any(r["doi"]==removed for r in prior)
    removed_book=book.pop(removed)
    records=[r for r in records if r["doi"]!=removed]
    pp=ROOT/".local-literature-cache/P32/pomelo_publisher_sealed.pdf"
    pe=get(P39/"early_input_evidence.json")
    case=get(P40/"case_result.json")
    assert digest(pp)==pe["protected_pdf_sha256"] and case["author_retention_pct"]==93.8 and POMELO not in book
    points=[dict(cycle=p["cycle_reading"],cycle_interval=p["cycle_interval"],pct=p["early_ordinate_pct"],pct_interval=p["geometry_interval_pct"]) for p in pe["panels"]["3E"]["points"]]
    rowid="P40:PSAC-3:3E:10000"
    ev[POMELO]=dict(pdf=relative(pp),sha256=digest(pp),page=5,figure="2f",marker_points=points,features=features(points,10000),early_source=relative(P39/"early_input_evidence.json"),target_source=relative(P40/"case_result.json"))
    refs[POMELO]=dict(path=relative(pp),sha256=digest(pp),public_pdf="https://pmc-oa-opendata.s3.amazonaws.com/PMC9419826.1/PMC9419826.1.pdf")
    book[POMELO]=dict(removed_book,DOI=POMELO,题名="Effect of pomelo seed-derived carbon on the performance of supercapacitors",来源="已揭盲历史对照，第40轮",样品及终点="PSAC-3: 1 M KOH，10 A/g，10000圈，93.8% (eq)",正文PDF=relative(pp),原文入口="https://doi.org/"+POMELO)
    records.append(dict(doi=POMELO,id=rowid,sample="PSAC-3",KOH_M=1,current_A_g=10,cycles=10000,retention_pct=93.8,relation="eq",origin="历史对照",source=ev[POMELO]["target_source"],restriction="既往外部单例，保留历史对照用途"))
    newrows.append(dict(id=rowid,doi=POMELO,features=ev[POMELO]["features"],retention_pct=93.8,use="historical_check",source_round=40))
    uses={r["id"]:r["use"] for r in newrows}
    issues={(d,s):action for d,s,action,_,_ in ISSUES}
    for r in records:
        r["early20_use"]=uses.get(r["id"],issues.get((r["doi"],r["sample"]),"no_early_input"))
        r["early20_ready"]=r["id"] in uses
        r["label_review"]=issues.get((r["doi"],r["sample"]),"as_reported")
        if r["label_review"]=="baseline_needed":
            r["label_review"]="as_reported"
        if r["early20_use"]=="sensitivity_only":
            r["label_review"]="abstract_vs_results"
        if r["early20_use"]=="freeze_label":
            r["competing_observations"]=[dict(locator="p.6 Fig.3g",pct=90.3),dict(locator="p.7 results",pct=92.4)]
    for b in book.values():
        roles=sorted({r["use"] for r in newrows if r["doi"]==b["DOI"]})
        b["可用早期曲线"]="是" if roles else "待核"
        b["早期输入用途"]=",".join(roles)
    csvwrite(out/"同工况50篇逐篇清单.csv",sorted(book.values(),key=lambda r:int(r["编号"])))
    save(out/"逐测试证据.json",records)
    save(out/"早期逐点证据.json",ev)
    save(out/"早期输入及用途.json",newrows)
    save(out/"归属与争议.json",dict(withdrawn=dict(original=removed_row,roster=removed_book),changes=[dict(doi=d,sample=s,action=a,locator=p,reason=n) for d,s,a,p,n in ISSUES],sources=refs))
    db=sqlite3.connect(out/"retention50.sqlite")
    db.execute("PRAGMA foreign_keys=ON")
    db.executescript("""CREATE TABLE papers(doi TEXT PRIMARY KEY,title TEXT NOT NULL,pdf TEXT NOT NULL);
    CREATE TABLE endpoints(id TEXT PRIMARY KEY,doi TEXT NOT NULL REFERENCES papers(doi),sample TEXT NOT NULL,koh_m REAL,current_a_g REAL,cycles INTEGER NOT NULL,retention_pct REAL NOT NULL,relation TEXT NOT NULL,label_review TEXT NOT NULL,early20_use TEXT NOT NULL);
    CREATE TABLE early_inputs(id TEXT PRIMARY KEY REFERENCES endpoints(id),last_early_retention_pct REAL NOT NULL,early_mean_retention_pct REAL NOT NULL,early_retention_slope_per_1000_cycles REAL NOT NULL,early_retention_range_pp REAL NOT NULL,early_observed_cycle_count REAL NOT NULL,target_cycle_count REAL NOT NULL);
    CREATE VIEW early_development AS SELECT e.doi,e.sample,e.retention_pct,x.* FROM early_inputs x JOIN endpoints e USING(id) WHERE e.early20_use='development';""")
    cols=list(newrows[0]["features"])
    for r in book.values():
        db.execute("INSERT INTO papers VALUES(?,?,?)",(r["DOI"],r["题名"],r["正文PDF"]))
    for r in records:
        db.execute("INSERT INTO endpoints VALUES(?,?,?,?,?,?,?,?,?,?)",tuple(r[k] for k in ("id","doi","sample","KOH_M","current_A_g","cycles","retention_pct","relation","label_review","early20_use")))
    for r in newrows:
        assert set(r["features"])==set(cols) and all(np.isfinite(list(r["features"].values())))
        assert r["retention_pct"]==next(v["retention_pct"] for v in records if v["id"]==r["id"] and v["doi"]==r["doi"])
        db.execute("INSERT INTO early_inputs (id,"+",".join(cols)+") VALUES(?,?,?,?,?,?,?)",(r["id"],*[r["features"][c] for c in cols]))
    db.commit()
    counts=db.execute("SELECT count(*),count(distinct doi) FROM early_development").fetchone()
    assert counts==(31,26) and len(newrows)==33 and len({r["doi"] for r in newrows})==28
    assert len(book)==50 and len(records)==63 and db.execute("PRAGMA integrity_check").fetchone()==("ok",) and not db.execute("PRAGMA foreign_key_check").fetchall()
    assert sum((ROOT/r["正文PDF"]).is_file() for r in book.values())==49
    db.close()
    pdf_hashes={}
    p83_source=get(P83/"核验.json")["incoming"][0]
    for doi,b in book.items():
        path=ROOT/b["正文PDF"]
        if not path.is_file():
            assert doi=="10.1007/s00226-023-01515-0"
            continue
        expected=(pe["protected_pdf_sha256"] if doi==POMELO else
                  p83_source["sha256"] if doi==p83_source["doi"] else prior_pdf[doi]["sha256"])
        assert digest(path)==expected
        pdf_hashes[doi]=expected
    save(out/"核验.json",dict(papers=50,listed_endpoints=63,journal_pdfs=49,early_any_rows=33,early_any_papers=28,development_rows=31,development_papers=26,sensitivity_rows=1,historical_check_rows=1,added_marker_counts={d:len(v["marker_points"]) for d,v in ev.items()},journal_pdf_sha256=pdf_hashes,fits=0,new_blind_sources=0,sqlite="integrity ok / no FK violations",parent_hashes={relative(p):digest(p) for p in (P83/"同工况50篇逐篇清单.csv",P83/"同工况早期曲线输入.json",P82/"逐测试证据.json",P81/"inputs.json",P39/"early_input_evidence.json",P40/"case_result.json")},outputs={p.name:digest(p) for p in sorted(out.iterdir())}))
if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--out",type=Path,default=DEFAULT)
    build(parser.parse_args().out)
