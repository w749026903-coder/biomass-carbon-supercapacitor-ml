"""Rebuild the round-85 evidence projection without changing a prior cohort."""
import argparse
import csv
import hashlib
import json
import shutil
import sqlite3
from pathlib import Path
from urllib.request import urlopen

import numpy as np
import pypdfium2 as pdfium
from PIL import Image
from pypdf import PdfReader
from review_cohort_v84 import features

ROOT=Path(__file__).resolve().parents[1]
BASE=next(ROOT.glob("保持率达标研究_v3*"))
P84=next(BASE.glob("第八十四轮*"))
DEFAULT=BASE/"第八十五轮_全队列早期曲线补证_20261124"
CACHE=ROOT/".local-literature-cache/P85"
def get(p):
    return json.loads(p.read_text(encoding="utf-8-sig"))
def save(p,v):
    p.write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf8")
def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()
def csvout(p,rows):
    with p.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def pdf_image(path,page,width):
    with pdfium.PdfDocument(path) as doc:
        pg=doc[page-1]
        return pg.render(scale=width/pg.get_size()[0]).to_pil().convert("RGB")
def fractional(im,box):
    bounds=[round(z*im.size[i%2]) for i,z in enumerate(box)]
    return im.crop(bounds)
def panel(n,book,spec):
    conf=spec[str(n)]
    path=ROOT/book[n]['正文PDF']
    kind=conf['kind']
    if kind=='public_figure':
        path=CACHE/conf['file']
        if not path.is_file():
            CACHE.mkdir(parents=True,exist_ok=True)
            data=urlopen(conf['url'],timeout=30).read()
            assert hashlib.sha256(data).hexdigest()==conf['sha256']
            path.write_bytes(data)
        im=Image.open(path).convert("RGB")
    elif kind=='embedded':
        im=PdfReader(path).pages[conf['page']-1].images[conf['image']].image.convert("RGB")
    else:
        im=pdf_image(path,conf['page'],conf['width'])
        if 'roi' in conf:
            im=im.crop([v*5 for v in conf['roi']])
    assert sha(path)==conf['sha256'],(n,path)
    im=fractional(im,conf['crop'])
    if n!=30:
        im=im.resize((600,round(600*im.height/im.width)),Image.Resampling.BICUBIC if n==31 else Image.Resampling.LANCZOS)
    assert hashlib.sha256(im.tobytes()).hexdigest()==conf['panel_rgb_sha256'],n
    return np.asarray(im,dtype=int)
def mask(rgb,c,t):
    r,g,b=rgb.transpose(2,0,1)
    if c=='black': return rgb.max(axis=2)<(t+42)
    if c=='red':return (r>g+t)&(r>b+t)
    if c=='blue':return (b>r+t)&(b>g+t)
    if c=='green':return (g>r+t*.7)&(g>b+t*.45)
    if c=='magenta':return (r>g+t*.65)&(b>g+t*.65)
    if c=='teal':return (g>r+t*.6)&(b>r+t*.45)
    if c=='cyan':return (g>r+t)&(b>r+t)
    raise ValueError(c)
def digitize(c,img,N):
    x0,xn=c['x_axis'];(y0,v0),(y1,v1)=c['y_ticks']
    dy=(v1-v0)/(y1-y0)
    def ordinate(y):return v0+(y-y0)*dy
    def centre(x, override=None):
        band=override or c['band'];ys=[]
        for threshold in (37,52,67):
            m=mask(img[band[0]:band[1]+1,x-1:x+2],c['color'],threshold)
            where=np.where(m)[0]+band[0]
            if len(where):ys.append(float((np.min(where)+np.max(where))/2))
        assert len(ys)>=2,(c['sample'],x)
        return float(np.median(ys)),ys
    delta=5 if c['number']==30 else 3
    norm=c['norm'];base=1.;unc=0.
    if isinstance(norm,(int,float)):base=norm
    elif norm in ('origin','first'):
        basex=83 if norm=='first' else round(x0)
        base=ordinate(centre(basex,(35,50) if norm=="first" else None)[0]);unc=abs(dy)*delta
    def read(x):
        y,ys=centre(x);v=ordinate(y)
        err=(delta+max(abs(y-z) for z in ys))*abs(dy)
        if norm is None:
            value,interval=v,[v-err,v+err]
        else:
            value,interval=100*v/base,[100*(v-err)/(base+unc),100*(v+err)/(base-unc)]
        cyc=(x-x0)*N/(xn-x0);dx=N*delta/(xn-x0)
        return dict(x_px=x,y_px=y,y_threshold_px=ys,axis_value=v,cycle=cyc,cycle_interval=[cyc-dx,cyc+dx],pct=value,pct_interval=interval)
    pts=[read(x) for x in c['markers']]
    assert all(p['cycle_interval'][0]>0 and p['cycle_interval'][1]<N*.2 for p in pts),c['sample']
    terminal=read(c['tip']) if c['tip'] is not None else None
    return dict(markers=pts,calibration=c,reference=base if norm else None,reference_margin=unc,
                end_check=terminal,features=features(pts,N) if len(pts)>=3 else None)
# Sample, figure, intended use, colour, 0 and target x, two labelled y ticks (pixel,value), band, marker centres, endpoint x.
# For raw F/g plots norm is the stated initial value or a graph origin marker.
def trace(n,s,fig,use,color,x0,xn,y1,v1,y2,v2,band,markers,tip=None,norm=None):
    return dict(number=n,sample=s,figure=fig,use=use,color=color,x_axis=[x0,xn],y_ticks=[[y1,v1],[y2,v2]],
                band=band,markers=markers,tip=tip,norm=norm)
TRACES=[
trace(3,'K-LWCA3','6f','sensitivity_only','red',101.5,557.5,429,0,82,100,(74,112),[111,120,129,138,147,156,166,175,184],557),
trace(5,'FPC','6','frozen','red',128,465,403,0,81,100,(70,105),[179],465),
trace(12,'DAC-700','6F','development','red',131,546.5,402,0,68,100,(55,83),[137,142,147,153,158,163,168,173,178,183,188,194,199,204,209],546),
trace(15,'TAK5','6B','frozen','black',108,520,387,0,68,100,(72,103),[137,154,167,180],520),
trace(16,'NSHPC2','6F','sensitivity_only','red',79.5,555.5,405,0,39,100,(30,102),[98,112,126,138,151,163],554),
trace(17,'WW-KOH9','7d','frozen','magenta',76.5,526.5,396,0,66,100,(54,105),[91,104,118,131,145,158],523),
trace(19,'CDAP800-350','8c','development','red',133,549,351,0,95,250,(83,125),[142,150,158,166,174,182,190,199,207],548,250),
trace(22,'700-3','4f','development','red',143.5,562,403,0,103,100,(90,146),[152,160,169,177,185,194,202,211,219],562),
trace(23,'APVPC-2','2f','sensitivity_only','red',99,543,413,0,60,100,(49,89),[152,161,170,178],543),
trace(24,'BSAC-A-800','7','sensitivity_only','black',125.5,554,385,0,31,250,(22,53),[134,139,143,148,152,160,168,177,186,194,203],554,'origin'),
trace(25,'ACST-2','4f','development','blue',89.5,575.5,421,0,74,100,(59,123),[109,119,138,167],575),
trace(27,'CF-HPC-2','8f lower','development','red',139.5,555,390,40,308.5,80,(251,292),[145,150,155,160,165,170,175,180,185,190,195,200,205,210,215],554),
trace(35,'BSPC','4e','development','black',115.5,515,377,0,85,100,(94,106),[124,131,138,146,160,167,174,181,188],514),
trace(36,'TCZn-800','7a','partial','black',103.5,575,304,0,26.5,100,(20,54),[135,166],575),
trace(37,'NSOC-800','3d','development','green',85.5,542,401,0,27.5,100,(17,78),[95,104,113,122,131,140,150,159,168],541),
trace(40,'AHPC-850','4d','frozen','red',145,468,323,0,135.5,100,(127,157),[159,173,186,200],468),
trace(44,'DC-900','3g','frozen','green',105.5,499.5,211,0,108.5,100,(94,109),[114,125,134,145,157,168,178],None),
trace(47,'BPPCF','7b','partial','black',75.5,574,385,80,156,180,(308,340),[125],None,'origin'),
trace(47,'N-BPPCF','7b','partial','red',75.5,574,385,80,156,180,(219,255),[125],None,'origin'),
trace(48,'ECNFs-6','7c','sensitivity_only','black',79,533.5,365,140,28.5,220,(33,160),[91,102,125],533,'first'),
trace(49,'CMC-ZnK-800','8d right axis','development','black',171.5,485.5,335,0,135.5,100,(127,155),[184,196,209,221],485),
]
for name,colour,markers in [('AF-MMTC1','red',[235,304,376,393,411]),('AF-MMTC5','blue',[180,215,287,358,429]),('AF-MMTC7','cyan',[198,250,269,287,340,357,429,447,464,482]),('AF-MMTC9','magenta',[163,181,216,234,270,304,341,376,464])]:
    TRACES.append(trace(30,name,'4e','sensitivity_only',colour,146,1919,2370,0,1662,100,(1646,1699),markers))
TRACES.append(trace(30,'AF-MMTC0','4e','partial','black',146,1919,2370,0,1662,100,(1646,1699),[322,482]))
for name,colour in [('OPB','blue'),('OPNP','magenta'),('OPC','teal')]:
    TRACES.append(trace(31,name,'3g','partial',colour,136,550,377,0,75,100,(85,137),[177]))

TRACES.append(trace(3,'H-LWCA','6f green','sensitivity_only','green',101.5,557.5,429,0,82,100,(75,156),[111,120,129,138,147,156,166,175,184],557))

def build(out):
    assert not out.exists(),out
    spec=get(DEFAULT/'source_geometry.json')
    with (P84/'同工况50篇逐篇清单.csv').open(encoding='utf-8-sig') as f:
        book={int(r['编号']):r for r in csv.DictReader(f)}
    records=get(P84/'逐测试证据.json')
    original={r['id']:r.copy() for r in records}
    old=get(P84/'早期输入及用途.json')
    index={(r['doi'],r['sample']):r for r in records}
    samples={30:[('AF-MMTC0',98.8),('AF-MMTC1',97.0),('AF-MMTC3',96.9),('AF-MMTC7',98.0),('AF-MMTC9',97.9)],3:[('H-LWCA',81.37)]}
    for n,items in samples.items():
        doi=book[n]['DOI'];ref=index[(doi,'AF-MMTC5' if n==30 else 'K-LWCA3')]
        for name,y in items:
            r=dict(id='P85:'+doi+':'+name,doi=doi,sample=name,KOH_M=ref['KOH_M'],current_A_g=ref['current_A_g'],cycles=ref['cycles'],retention_pct=y,relation='eq' if n==30 else 'graph_81.37_preprint_text_81.3',source='publisher PDF p.5 Fig.4e; p.2 methods' if n==30 else 'Springer Fig.6f with preprint method',origin='第85轮同篇样品',restriction='同DOI同折',label_review='as_reported' if n==30 else 'version_precision',early20_ready=False,early20_use='no_early_input')
            records.append(r);index[(doi,name)]=r
    ev={};images={}
    for c in TRACES:
        n=c['number'];r=index[(book[n]['DOI'],c['sample'])]
        if n not in images:images[n]=panel(n,book,spec)
        v=digitize(c,images[n],r['cycles']);v.update(id=r['id'],doi=r['doi'],sample=r['sample'],author_pct=r['retention_pct'])
        use=c['use']
        if use=='development':
            e=v['end_check'];assert e and e['pct_interval'][0]-.5 <= r['retention_pct'] <= e['pct_interval'][1]+.5,(r['sample'],e,r['retention_pct'])
        ev[r['id']]=v;r['early20_use']=use;r['early20_ready']=use in ('development','sensitivity_only')
        if r['early20_ready']:
            assert v['features']
            if c['tip'] is not None and c['use']!='frozen':
                assert abs(c['tip']-c['x_axis'][1])<=3,(n,c['tip'])
            old.append(dict(id=r['id'],doi=r['doi'],features=v['features'],retention_pct=r['retention_pct'],use=use,source_round=85))
        if n==49:r['label_review']='as_reported'
    # Preserve the paper's second explicit ECNFs-6 endpoint with its own shorter early window.
    ref=index[(book[48]['DOI'],'ECNFs-6')]
    r=dict(ref,id='P85:ECNFs-6:1000',cycles=1000,retention_pct=92.,early20_use='partial',early20_ready=False,source='publisher PDF p.10 Fig.7c / results; 1 A/g',origin='第85轮同曲线第二终点')
    records.append(r);parent=ev[ref['id']]
    ev[r['id']]=dict(id=r['id'],sample=r['sample'],doi=r['doi'],author_pct=92.,parent=ref['id'],markers=[p for p in parent['markers'] if p['cycle_interval'][1]<200],features=None)
    byid={r['id']:r for r in records}
    assert all(byid[k]['retention_pct']==v['retention_pct'] for k,v in original.items())
    assert len(records)==len(byid)==70 and len(book)==50 and len(set(b['DOI'] for b in book.values()))==50
    assert all(r['doi']==byid[r['id']]['doi'] and r['use']==byid[r['id']]['early20_use'] for r in old)
    out.mkdir(parents=True)
    shutil.copyfile(P84/'retention50.sqlite',out/'retention50.sqlite')
    with sqlite3.connect(out/'retention50.sqlite') as db:
        db.execute('PRAGMA foreign_keys=ON')
        db.execute('CREATE TABLE marker_points(endpoint_id TEXT NOT NULL REFERENCES endpoints(id), x_px REAL, y_px REAL, cycle REAL, cycle_lo REAL, cycle_hi REAL, retention_pct REAL, pct_lo REAL,pct_hi REAL, PRIMARY KEY(endpoint_id,x_px))')
        for r in records:
            if r['id'] in original:
                db.execute('UPDATE endpoints SET label_review=?,early20_use=? WHERE id=?',(r['label_review'],r['early20_use'],r['id']))
            else:
                db.execute('INSERT INTO endpoints VALUES(?,?,?,?,?,?,?,?,?,?)',tuple(r[k] for k in ('id','doi','sample','KOH_M','current_A_g','cycles','retention_pct','relation','label_review','early20_use')))
        for r in old:
            if r['source_round']==85:
                cols=list(r['features']);db.execute('INSERT INTO early_inputs(id,'+','.join(cols)+') VALUES(?,?,?,?,?,?,?)',(r['id'],*[r['features'][c] for c in cols]))
        for id,v in ev.items():
            for pt in v['markers']:
                db.execute('INSERT INTO marker_points VALUES(?,?,?,?,?,?,?,?,?)',(id,pt['x_px'],pt['y_px'],pt['cycle'],*pt['cycle_interval'],pt['pct'],*pt['pct_interval']))
        assert db.execute('PRAGMA integrity_check').fetchone()==('ok',) and not db.execute('PRAGMA foreign_key_check').fetchall()
        stats=db.execute('SELECT early20_use,count(*),count(distinct doi) FROM endpoints GROUP BY early20_use').fetchall()
        covered=db.execute('SELECT count(*),count(distinct doi) FROM early_inputs JOIN endpoints USING(id)').fetchone()
        dev=db.execute('SELECT count(*),count(distinct doi) FROM early_development').fetchone()
    for b in book.values():
        rs=[r for r in records if r['doi']==b['DOI']]
        b['样品及终点']='；'.join(f"{r['sample']} {r['KOH_M']:g} M KOH {r['current_A_g']:g} A/g {r['cycles']:g}圈 {r['retention_pct']:g}% ({r['relation']})" for r in rs)
        u=sorted({r['early20_use'] for r in rs});b['早期输入用途']=','.join(u)
        b['可用早期曲线']='是' if any(r['early20_ready'] for r in rs) else '待补'
    csvout(out/'同工况50篇逐篇清单.csv',sorted(book.values(),key=lambda b:int(b['编号'])))
    save(out/'逐测试证据.json',records);save(out/'早期输入及用途.json',old);save(out/'逐点读图.json',ev)
    save(out/'核验.json',dict(parent_sqlite=sha(P84/'retention50.sqlite'),papers=50,endpoints=len(records),roles=stats,usable_rows_and_dois=covered,development_rows_and_dois=dev,curve_readouts=sum(len(v['markers']) for k,v in ev.items() if not v.get('parent')),fits=0,sqlite_checks='ok',hashes={f.name:sha(f) for f in sorted(out.iterdir())}))
    print(stats,covered,dev)
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);build(ap.parse_args().out)
