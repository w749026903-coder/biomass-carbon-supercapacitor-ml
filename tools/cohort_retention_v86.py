"""Rebuild the AF-MMTC3 early input and audit the separate TCZn-800 waveform insets."""
import argparse
import csv
import hashlib
import json
import shutil
import sqlite3
from pathlib import Path

import numpy as np
from pypdf import PdfReader
from review_cohort_v84 import features

ROOT = Path(__file__).resolve().parents[1]
BASE = next(ROOT.glob("保持率达标研究_v3*"))
PREVIOUS = next(BASE.glob("第八十五轮*"))
AF = "10.1039/d4ra08818b"
STRAW = "10.3390/ma15030924"

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))

def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+"\n", encoding="utf8")

def af_points(path):
    image = PdfReader(path).pages[5].images[0].image.convert("RGB")
    assert image.size == (1964,2485)
    geom = read(PREVIOUS/"source_geometry.json")["30"]
    assert sha(path) == geom["sha256"] and hashlib.sha256(image.tobytes()).hexdigest() == geom["panel_rgb_sha256"]
    def locate(x):
        rgb = np.asarray(image.crop((x-2,1652,x+3,1703)),dtype=int)
        r,g,b=rgb.transpose(2,0,1)
        centres=[]
        for t in (0,6,12):
            ys=np.where((r>=190)&(g>125)&(r-g>=12+t)&(g-b>=18+t)&(b<227))[0]+1652
            assert len(ys)>=6 and ys.max()-ys.min()>=6
            centres.append([int(ys.min()),int(ys.max())])
        top,bottom=centres[1]
        y=(top+bottom)/2
        cycle=(x-146)*5000/(1919-146)
        pct=(2370-y)*100/(2370-1662)
        # Bounds include the visible symbol and an extra 3 pixels for calibration.
        bounds=[(2370-max(v[1] for v in centres)-3)*100/708,(2370-min(v[0] for v in centres)+3)*100/708]
        dx=5*5000/(1919-146)
        return dict(x_px=x,y_px=y,ink_spans_px=centres,cycle=cycle,cycle_interval=[cycle-dx,cycle+dx],pct=pct,pct_interval=bounds)
    points = [locate(x) for x in (163,180,234,322,411)]
    end = locate(1919)
    assert end["pct_interval"][0]<=96.9<=end["pct_interval"][1]
    return dict(doi=AF,sample="AF-MMTC3",figure="4e",pdf_page=6,source_sha256=sha(path),
                colour="orange outline, upright triangles",cycle_calibration_px=[146,1919],
                retention_0_100_px=[2370,1662],markers=points,features=features(points,5000),
                end_check=end,author_pct=96.9,use="sensitivity_only")

def intersections(arr,y,xlo,xhi,threshold):
    idx=np.where(arr[y,xlo:xhi]<threshold)[0]+xlo
    groups=np.split(idx,np.flatnonzero(np.diff(idx)>1)+1)
    if len(groups)!=8 or any(not len(g) for g in groups):
        raise ValueError("Eight separate waveform crossings required")
    return np.array([(g[0]+g[-1])/2 for g in groups])

def waveform(path):
    image=PdfReader(path).pages[7].images[4].image.convert("L")
    assert image.size==(1775,698)
    out={}
    for phase,box,yt,yb,tx1,tx2,xlo,xhi in [
        ("begin",(185,202,550,541),56,286,78,325,66,345),
        ("end",(552,202,938,541),54,282,89,335,70,343)]:
        a=np.asarray(image.crop(box))
        configurations=[]
        for thr in (115,145,175):
            for offset in (-1,0,1):
                upper=intersections(a,round(yt+.2*(yb-yt))+offset,xlo,xhi,thr)
                lower=intersections(a,round(yt+.8*(yb-yt))+offset,xlo,xhi,thr)
                configurations.append(abs(upper-lower))
        duration=np.asarray(configurations)
        scale=200/(tx2-tx1)
        estimates=duration[4]*scale
        # Both voltage crossings and the two time calibration ticks have readout uncertainty.
        lows=np.maximum(0,duration.min(axis=0)-3)*200/(tx2-tx1+2)
        highs=(duration.max(axis=0)+3)*200/(tx2-tx1-2)
        out[phase]=dict(crop_px=box,time_ticks_px=[tx1,tx2],time_tick_span_s=200,
                        voltage_0_minus1_px=[yt,yb],potential_interval_V=[-0.8,-0.2],
                        traversals=[dict(displayed_loop=i//2+1,direction="up" if i%2==0 else "down",seconds=float(t),
                                         pixel_bounds_s=[float(lows[i]),float(highs[i])]) for i,t in enumerate(estimates)])
    return dict(doi=STRAW,sample="TCZn-800",pdf_page=8,figure="7a",pdf_sha256=sha(path),
                purpose="Diagnostic time measurements. The authors identify first and last few cycles. Absolute cycle indices and the normalization used for the main retention series are not supplied by these insets.",
                insets=out,training_role=None)

def build(out):
    if out.exists():
        raise FileExistsError(out)
    with (PREVIOUS/"同工况50篇逐篇清单.csv").open(encoding="utf-8-sig") as f:
        book={r["DOI"]:r for r in csv.DictReader(f)}
    parent=PREVIOUS/"retention50.sqlite"
    assert sha(parent)==read(PREVIOUS/"核验.json")["hashes"][parent.name]
    for doi in (STRAW,AF):
        path=ROOT/book[doi]["正文PDF"]
        expected=read(next(BASE.glob("第八十四轮*/核验.json")))["journal_pdf_sha256"][doi]
        assert sha(path)==expected
    af=af_points(ROOT/book[AF]["正文PDF"])
    wave=waveform(ROOT/book[STRAW]["正文PDF"])
    out.mkdir(parents=True)
    database=out/"retention50.sqlite"
    shutil.copyfile(parent,database)
    with sqlite3.connect(database) as db:
        db.execute("PRAGMA foreign_keys=ON")
        before=db.execute("SELECT id,retention_pct FROM endpoints ORDER BY id").fetchall()
        id,y,role=db.execute("SELECT id,retention_pct,early20_use FROM endpoints WHERE doi=? AND sample=?",(AF,"AF-MMTC3")).fetchone()
        assert (y,role)==(96.9,"no_early_input")
        db.execute("UPDATE endpoints SET early20_use='sensitivity_only' WHERE id=?",(id,))
        cols=list(af['features'])
        db.execute("INSERT INTO early_inputs (id,"+",".join(cols)+") VALUES(?,?,?,?,?,?,?)",(id,*af['features'].values()))
        for pt in af['markers']:
            db.execute("INSERT INTO marker_points VALUES(?,?,?,?,?,?,?,?,?)",(id,pt['x_px'],pt['y_px'],pt['cycle'],*pt['cycle_interval'],pt['pct'],*pt['pct_interval']))
        db.execute("""CREATE TABLE waveform_diagnostics(doi TEXT REFERENCES papers(doi),sample TEXT,
        phase TEXT,displayed_loop INTEGER,direction TEXT,duration_s REAL,low_s REAL,high_s REAL,
        PRIMARY KEY(doi,sample,phase,displayed_loop,direction))""")
        for phase, inset in wave["insets"].items():
            for t in inset["traversals"]:
                db.execute("INSERT INTO waveform_diagnostics VALUES(?,?,?,?,?,?,?,?)",(STRAW,wave['sample'],phase,t['displayed_loop'],t['direction'],t['seconds'],*t['pixel_bounds_s']))
        assert before==db.execute("SELECT id,retention_pct FROM endpoints ORDER BY id").fetchall()
        assert db.execute("PRAGMA integrity_check").fetchone()==('ok',) and not db.execute("PRAGMA foreign_key_check").fetchall()
        dev=db.execute("SELECT count(*),count(distinct doi) FROM early_development").fetchone()
        ready=db.execute("SELECT count(*),count(distinct doi) FROM early_inputs JOIN endpoints USING(id)").fetchone()
        assert dev==(39,34) and ready==(52,42)
        assert db.execute("SELECT count(*) FROM waveform_diagnostics").fetchone()==(16,)
        sens=db.execute("SELECT count(*),count(distinct doi) FROM endpoints WHERE early20_use='sensitivity_only'").fetchone()
        assert sens==(12,7)
        export=read(PREVIOUS/"早期输入及用途.json")
        export.append(dict(id=id,doi=AF,features=af["features"],retention_pct=y,use="sensitivity_only",source_round=86))
        assert {entry["id"] for entry in export}=={row[0] for row in db.execute("SELECT id FROM early_inputs")}
        assert len(export)==len({entry["id"] for entry in export})
    write(out/"早期输入及用途.json",export)
    write(out/"逐图证据.json",dict(early_input=af,waveform=wave))
    write(out/"核验.json",dict(parent_sha256=sha(parent),database_sha256=sha(database),known_papers=50,endpoints=70,development_rows_papers=dev,
        usable_rows_papers=ready,sensitivity_rows_papers=sens,historical_control=[1,1],uncovered_papers=8,model_fits=0,
        observed_waveforms=8,diagnostic_traversals=16,original_labels_preserved=True,integrity="ok",foreign_key_violations=0))
if __name__=="__main__":
    ap=argparse.ArgumentParser();ap.add_argument("--out",required=True,type=Path);build(ap.parse_args().out)
