"""Build the open-ended source cohort from the reviewed v86 snapshot and journal figures."""
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
PARENT = next(ROOT.glob("保持率达标研究_v3*/第八十六轮*/retention50.sqlite"))
CACHE = ROOT / ".local-literature-cache/P87"
SAKURA = "10.1039/c8ra09685f"
WALNUT = "10.1039/d4ra01608d"
SWEET = "10.1002/asia.202401971"
POMELO = "10.13801/j.cnki.fhclxb.20250227.001"
PAPERS = {
    SAKURA: ("Sakura-based activated carbon preparation and its performance in supercapacitor applications","sakura.pdf","1a3b8100470c0e16f6e468dd54622ef949bca2ba5294a5cdf4b20736854c5b31","https://pmc-oa-opendata.s3.amazonaws.com/PMC9059875.1/PMC9059875.1.pdf"),
    WALNUT: ("Catalytic pyrolysis and in situ carbonization of walnut shells: poly-generation and enhanced electrochemical performance of carbons","walnut.pdf","6b8dc36082a01fbe4034b959c9ddf56f9f365e8894ff3642fe1be4beaea624bf","https://pmc-oa-opendata.s3.amazonaws.com/PMC11019962.1/PMC11019962.1.pdf"),
    SWEET: ("Ultrahigh-Surface Area Hierarchically Porous Carbon Derived From Sweet Potato Extraction Residue-Syrup for High Performance Supercapacitor","","","https://onlinelibrary.wiley.com/doi/pdfdirect/10.1002/asia.202401971"),
    POMELO: ("自掺杂柚子皮多孔碳的制备及其电容特性研究","","","https://fhclxb.buaa.edu.cn/article/doi/10.13801/j.cnki.fhclxb.20250227.001"),
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False)+"\n",encoding="utf8")


def read_sakura():
    im = PdfReader(CACHE/"sakura.pdf").pages[6].images[0].image.convert("RGB")
    assert im.size == (1646,2603)
    a = np.asarray(im.crop((825,1310,1646,1970)),dtype=int)
    evidence = {}
    for name,lo,hi in [("SAC-4",22,110),("SC",350,409),("SAC-3",135,225),("SAC-5",130,220)]:
        # x=0 touches the vertical axis. Read its visible right-hand portion.
        def read(x):
            r,g,b = a[:,x-2:x+3,:].transpose(2,0,1)
            band = lo if not (name=="SC" and x==774) else 380
            mask={"SAC-4":(b-r>40)&(b-g>14),"SC":(r<70)&(g<70)&(b<70),
                  "SAC-3":(r-g>70)&(r-b>63),"SAC-5":(r-g>23)&(b-g>23)&(r-b<55)}[name]
            ink = np.where(mask[band:hi])[0]+band
            assert len(ink) and ink.max()-ink.min()>=5
            y=(int(ink.max())+int(ink.min()))/2
            return {"x_px":x,"y_px":y,"ink_y":[int(ink.min()),int(ink.max())],"F_g":(501.5-y)*250/492}
        start=read(133)
        end=read(774)
        def relative(pt,x):
            convert=lambda y: (501.5-y)*250/492
            pct=100*pt["F_g"]/start["F_g"]
            bounds=[100*convert(pt["ink_y"][1]+2)/convert(start["ink_y"][0]-2),
                    100*convert(pt["ink_y"][0]-2)/convert(start["ink_y"][1]+2)]
            return dict(**pt,pct=pct,pct_interval=bounds,cycle=(x-130)*2000/644,
                        cycle_interval=[(x-137)*2000/644,(x-123)*2000/644])
        anchors=[162,194,226] if name in ("SC","SAC-4") else [162,194]
        pts=[relative(read(x),x) for x in anchors]
        terminal=relative(end,774)
        evidence[name]=dict(start=start,endpoint=terminal,markers=pts,
                            note="红紫在约300圈交叠，保留两个内部点" if len(pts)==2 else "可分离的三个内部标记")
    c=evidence["SAC-4"]["endpoint"]
    assert abs(c["pct"]-90.2)<1 and abs(c["F_g"]-209)<2
    return evidence


def read_walnut():
    im=PdfReader(CACHE/"walnut.pdf").pages[7].images[0].image.convert("RGB")
    assert im.size==(877,705)
    a=np.asarray(im,dtype=int)
    def point(x):
        r,g,b=a[397:430,x-2:x+3,:].transpose(2,0,1)
        ys=np.where((r-g>70)&(r-b>70))[0]+397
        y=(int(ys.min())+int(ys.max()))/2
        pct=lambda px:(654.5-px)*100/241
        cycles=lambda px:1000+(px-335)*4000/286
        return dict(x_px=x,y_px=y,ink_y=[int(ys.min()),int(ys.max())],pct=pct(y),
                    pct_interval=[pct(ys.max()+2),pct(ys.min()-2)],cycle=cycles(x),
                    cycle_interval=[cycles(x-5),cycles(x+5)])
    pts=[point(306),point(321)]
    end=point(621)
    assert end["pct_interval"][0]<98.16<end["pct_interval"][1]
    return dict(markers=pts,endpoint=end,at_boundary=point(335))


def build(out):
    assert digest(PARENT)=="684f6d854aa555de0fbf7e1d96fb7e1a72f95a2fed5c7f4d2994667c067da014"
    for _,file,sha,_ in PAPERS.values():
        if file:
            assert digest(CACHE/file)==sha
    s=read_sakura()
    w=read_walnut()
    out.mkdir(parents=True,exist_ok=False)
    database=out/"保持率扩充.sqlite"
    shutil.copyfile(PARENT,database)
    with sqlite3.connect(database.resolve().as_uri(),uri=True) as db:
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("ATTACH DATABASE ? AS previous",(PARENT.resolve().as_uri()+"?mode=ro",))
        db.execute("CREATE TABLE expansion_sources(doi TEXT PRIMARY KEY REFERENCES papers(doi), url TEXT NOT NULL, sha256 TEXT, figure TEXT NOT NULL)")
        figures={SAKURA:"图7f，期刊PDF第7页",WALNUT:"图10c，期刊PDF第8页",SWEET:"图3g及正文，图4h属于双电极",POMELO:"方法1.3，图6f及结论"}
        for doi,(title,file,sha,url) in PAPERS.items():
            path=(CACHE/file).relative_to(ROOT).as_posix() if file else "已核期刊原文；本地缺高清图或PDF"
            db.execute("INSERT INTO papers VALUES(?,?,?)",(doi,title,path))
            db.execute("INSERT INTO expansion_sources VALUES(?,?,?,?)",(doi,url,sha or None,figures[doi]))
        def add(doi,name,current,cycles,value,relation,label,use,pts):
            row_id="v87:"+name
            db.execute("INSERT INTO endpoints VALUES(?,?,?,?,?,?,?,?,?,?)",(row_id,doi,name,6,current,cycles,value,relation,label,use))
            for pt in pts:
                db.execute("INSERT INTO marker_points VALUES(?,?,?,?,?,?,?,?,?)",(row_id,pt["x_px"],pt["y_px"],pt["cycle"],*pt["cycle_interval"],pt["pct"],*pt["pct_interval"]))
            if use in ("development","sensitivity_only"):
                ft=features(pts,cycles)
                db.execute("INSERT INTO early_inputs VALUES(?,?,?,?,?,?,?)",(row_id,*ft.values()))
        for name,row in s.items():
            author=name=="SAC-4"
            use={"SAC-4":"development","SC":"sensitivity_only","SAC-3":"partial","SAC-5":"partial"}[name]
            add(SAKURA,name,1,2000,90.2 if author else row["endpoint"]["pct"],"eq" if author else "approx",
                "as_reported" if author else "figure_normalized_to_own_start",use,row["markers"])
        add(WALNUT,"WSC–PC",2,5000,98.16,"eq","as_reported","partial",w["markers"])
        add(SWEET,"SPR-HPC-3.5-800",10,5000,87,"approx","as_reported_3e","no_early_input",[])
        add(POMELO,"SPC-800",10,5000,96,"eq","as_reported_3e","no_early_input",[])
        for tab in ("papers","endpoints","early_inputs","marker_points","early_development"):
            assert not db.execute(f"SELECT * FROM previous.{tab} EXCEPT SELECT * FROM main.{tab}").fetchall()
        assert db.execute("PRAGMA integrity_check").fetchone()==("ok",)
        assert not db.execute("PRAGMA foreign_key_check").fetchall()
        def counts(sql):return db.execute(sql).fetchone()
        n=counts("SELECT count(*),count(distinct doi) FROM endpoints")
        active=counts("SELECT count(*),count(distinct doi) FROM early_development")
        all_early=counts("SELECT count(*),count(distinct doi) FROM early_inputs JOIN endpoints USING(id)")
        assert n==(77,54) and active==(40,35) and all_early==(54,43)
        cur=db.execute("SELECT * FROM early_development ORDER BY doi,id")
        with (out/"主模型训练输入.csv").open("w",encoding="utf-8-sig",newline="") as f:
            writer=csv.writer(f);writer.writerow([v[0] for v in cur.description]);writer.writerows(cur)
    write_json(out/"新增图读依据.json",{"sakura":{"crop_native_px":[825,1310,1646,1970],"x_ticks_cycles":[[130,0],[774,2000]],"y_ticks_F_g":[[9.5,250],[501.5,0]],"samples":s},
        "walnut":{"x_ticks_cycles":[[335,1000],[621,5000]],"y_ticks_pct":[[654.5,0],[413.5,100]],**w}})
    write_json(out/"核验.json",dict(papers=n[1],endpoint_records=n[0],development_rows_sources=active,all_early_rows_sources=all_early,
        source_pdf_sha256={d:v[2] for d,v in PAPERS.items() if v[2]},baseline_sha256=digest(PARENT),database_sha256=digest(database),
        integrity="ok",foreign_key_violations=0,old_data_preserved=True,model_fits=0))


if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--out",required=True,type=Path)
    build(ap.parse_args().out)
