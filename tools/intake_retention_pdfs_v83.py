"""Rebuild a versioned local intake into an empty output directory. No model fits."""
from pathlib import Path
import argparse,csv,json,hashlib,logging,math,shutil
import numpy as np
from pypdf import PdfReader

ROOT=Path(__file__).resolve().parents[1];BASE=next(ROOT.glob('保持率达标研究_v3*'))
P82=next(BASE.glob('第八十二轮*'));P81=next(BASE.glob('第八十一轮*'));DEFAULT=BASE/'第八十三轮_两篇来稿核验与高粱曲线_20261122'
S='10.1039/d3nj04881k';W='10.1007/s00226-023-01515-0'
HS='a52155adf66e63ec0ff06b54d4c05e08b49e16dc513622df1b43b6b1f6007fa1';HW='6df08390abea7d4e3d76cac91688a26da687e1457c7c4a933ee53658414f8f2c'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def get(p):return json.loads(p.read_text('utf-8-sig'))
def save(p,o):p.write_text(json.dumps(o,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf8')
def csvr(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def csvw(p,rows):
    with p.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,list(rows[0]));w.writeheader();w.writerows(rows)
def extract(pdf):
    # One embedded figure on PDF page 5. Coordinates below are relative to the
    # crop of its original raster (not a render or rescaled screenshot).
    imgs=list(pdf.pages[4].images);assert len(imgs)==1 and imgs[0].image.size==(2004,2173)
    arr=np.asarray(imgs[0].image.convert('RGB').crop((1050,1460,1980,2150))).astype(int)
    rr,gg,bb=arr.transpose(2,0,1)
    def parse(x,threshold):
        mask=(gg-rr>threshold)&(gg-bb>65);xx=np.arange(x-5,x+6)
        # Locate the top and bottom tips of each outlined two-colour diamond.
        spans=[np.where(mask[19:78,i])[0]+19 for i in xx];assert all(len(s)>1 for s in spans)
        tops=np.array([min(s) for s in spans]);bottoms=np.array([max(s) for s in spans]);t,b=min(tops),max(bottoms)
        xa,xb=xx[tops==t].mean(),xx[bottoms==b].mean()
        assert abs(xa-xb)<3 and 29<b-t<40
        return [float((xa+xb)/2),float((t+b)/2)]
    points=[]
    for x in (114,130,146,162,177,194,225):
        pos=[parse(x,k) for k in (55,70,100)];xc,yc=pos[1]; assert max(np.ptp(pos,axis=0))<=2
        cycle=(xc-97.5)/797*10000;ret=(606-yc)/(606-41.5)*100
        dx=3/797*10000;dy=3/(606-41.5)*100
        assert 0<cycle-dx and cycle+dx<2000
        points.append(dict(centers_px=pos,cycle=cycle,cycle_bounds=[cycle-dx,cycle+dx],retention_pct=ret,retention_bounds_pct=[ret-dy,ret+dy]))
    x=np.array([v['cycle'] for v in points]);y=np.array([v['retention_pct'] for v in points]);assert np.all(np.diff(x)>0)
    out=dict(last_early_retention_pct=float(y[-1]),early_mean_retention_pct=float(y.mean()),early_retention_slope_per_1000_cycles=float(np.polyfit(x/1000,y,1)[0]),early_retention_range_pp=float(np.ptp(y)),early_observed_cycle_count=float(x[-1]),target_cycle_count=10000.)
    return dict(doi=S,pdf_sha256=HS,page=5,figure='2f',crop_in_embedded_raster=[1050,1460,1980,2150],axes_px={'cycle_0':97.5,'cycle_10000':894.5,'pct_0':606,'pct_100':41.5},algorithm='Top/bottom tips of the same green outline with orange lower fill; thresholds 55/70/100 with fixed blue margin 65. Exclude origin and 2000-cycle boundary; 3px conservative digitizing allowance, not instrument accuracy. Late retention annotation not used as an input.',points=points,features=out)
def main(s,w,dest):
    logging.getLogger('pypdf').setLevel(logging.ERROR)
    original=ROOT/'新增文献整理_20261020/originals/ADD_016.pdf'
    assert sha(w)==sha(original)==HW and sha(s)==HS
    wood=PdfReader(w);sac=PdfReader(s)
    assert len(wood.pages)==21 and len(sac.pages)==10
    ev=extract(sac)
    meta=get(P82/'核验.json');book=csvr(P82/'同工况50篇逐篇清单.csv');todo=csvr(P82/'待下载正文_DOI清单.csv')
    assert len(book)==len({r['DOI'] for r in book})==50 and {r['DOI'] for r in todo if r['DOI'] in {b['DOI'] for b in book}}=={S,W}
    for row in book:
        d=row['DOI']
        if d not in (S,W):
            f=meta['files'][d];assert f['path'] and sha(ROOT/f['path'])==f['sha256']
    projection=get(P82/'逐测试证据.json');prior=get(P81/'inputs.json')['early_B']
    early=[{'id':t['id'],'doi':t['doi'],'features':t['x'],'retention_pct':t['y']} for t in prior if t['id'] in {r['id'] for r in projection if r['early20_ready']}]
    assert len(early)==27 and len({t['doi'] for t in early})==22
    row=next(t for t in projection if t['doi']==S);assert row['retention_pct']==98.4 and row['cycles']==10000 and row['KOH_M']==2 and row['current_A_g']==10 and not row['early20_ready']
    early.append(dict(id=row['id'],doi=S,features=ev['features'],retention_pct=row['retention_pct']))
    assert set(ev['features'])==set(early[0]['features']) and len({r['id'] for r in early})==28 and len({r['doi'] for r in early})==23
    dest.mkdir(exist_ok=False); local=dest/'本地正文';local.mkdir();pdf=local/s.name;shutil.copyfile(s,pdf);assert sha(pdf)==HS
    (dest/'.gitignore').write_text('/本地正文/\n',encoding='utf8')
    for b in book:
        if b['DOI']==S:b.update(正文PDF=pdf.relative_to(ROOT).as_posix(),可用早期曲线='是')
        if b['DOI']==W:b['正文PDF']='期刊版待补；已存预印本：'+original.relative_to(ROOT).as_posix()
    csvw(dest/'同工况50篇逐篇清单.csv',book);csvw(dest/'待下载正文_DOI清单.csv',[r for r in todo if r['DOI']!=S]);save(dest/'SAC-2_早期曲线证据.json',ev);save(dest/'同工况早期曲线输入.json',early)
    save(dest/'核验.json',dict(parent=meta['roster_sha256'],source_hashes={k:sha(v) for k,v in {'prior_roster':P82/'同工况50篇逐篇清单.csv','prior_records':P82/'逐测试证据.json','prior_inputs':P81/'inputs.json'}.items()},roster_dois=50,distinct_existing_endpoints=len(projection),journal_pdfs=49,early_curve_rows=28,early_curve_dois=23,model_fits=0,new_blind_sources=0,incoming=[dict(doi=S,name=s.name,sha256=HS,pages=10,stage='publisher typeset; New Journal of Chemistry, published online 2023-11-22',local=pdf.relative_to(ROOT).as_posix(),electrode='3E: Fig.2f; 2 M KOH / 10 A/g / 10000 cycles = 98.4%. Pg 7 text, pg 5 figure; Hg/HgO reference p2',direct_route='Fig.2c suggests -1 to 0 V for fresh GCD. Exact cycling limits not newly assigned.',device='Different experiment: 97.5%, Fig.4f on p8; separate from SAC-2 three-electrode label.'),dict(doi=W,name=w.name,sha256=HW,pages=21,stage='Research Square v1 preprint, 2023-02-21; cover refers readers to later published version',preprint_doi='10.21203/rs.3.rs-2596680/v1',same_as=original.relative_to(ROOT).as_posix(),relation='exact byte duplicate; no second archived copy',figure='Preprint Fig.6f p20: K-LWCA3 94.11% (text describes nearly); H-LWCA 81.37% plotted vs 81.3% body, kept separately; neither newly admitted.')],outputs={p.name:sha(p) for p in dest.iterdir() if p.is_file() and p.name!='.gitignore'}))
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('sorghum',type=Path);ap.add_argument('wood',type=Path);ap.add_argument('--out',type=Path,default=DEFAULT);a=ap.parse_args();main(a.sorghum,a.wood,a.out)