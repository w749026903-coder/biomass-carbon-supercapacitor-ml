"""Rebuild the endpoint/DOI cohort from frozen sources into a NEW directory."""
from pathlib import Path
import argparse, csv, hashlib, json, math, sqlite3, sys
from xml.etree import ElementTree as ET
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from data.cycling_db import open_database
BASE=ROOT/'保持率达标研究_v3_主线与近优组合_20261030'
DEST=BASE/'第八十轮_50篇三电极文献整合_20261119'
A=['cycle_count','reported_current_A_g','electrolyte','concentration_mol_L','cycle_voltage_lower_V','cycle_voltage_upper_V','BET_m2_g','reference_electrode']
B=['last_early_retention_pct','early_mean_retention_pct','early_retention_slope_per_1000_cycles','early_retention_range_pp','early_observed_cycle_count','target_cycle_count']
V=['reported_3e','reported_3e_all_years','reported_3e_sensitivity']
RESERVE={'10.1039/d1ma00679g','10.1016/j.sajce.2026.100908','10.1002/smsc.202500540','10.1016/j.cartre.2024.100436'}
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rel(p):return p.relative_to(ROOT).as_posix()
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def j(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,allow_nan=False)
def doi(s):return s.lower().strip().removeprefix('doi:')
def csvout(p,rows):
    with p.open('w',encoding='utf-8-sig',newline='') as h:
        w=csv.DictWriter(h,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
def fwca():
    folder=next(ROOT.glob('同体系文献补充_第二批*/定向扩搜*/sources/OA003')); fig=folder/'figures/nanomaterials-15-00387-g007.jpg'; xml=folder/'main.xml';tree=ET.parse(xml)
    assert any(x.text=='10.3390/nano15050387' for x in tree.findall('.//article-meta/article-id'))
    img=np.asarray(Image.open(fig).convert('RGB')).astype(int); assert img.shape==(600,784,3)
    x0,x10,y0,y100=74.,351.5,559.5,314.5; points=[]
    for anchor in (74,88,102,116,130):
        patch=img[306:330,anchor-5:anchor+6]; readings=[]
        for lim in (80,110):
            yy,xx=np.where((patch[:,:,0]-patch[:,:,1]>lim)&(patch[:,:,0]-patch[:,:,2]>60));assert len(xx)>25
            readings.append((float(xx.mean()+anchor-5),float(yy.mean()+306)))
        (x,y),(u,v)=readings;assert max(abs(x-u),abs(y-v))<0.65
        n=(x-x0)*10000/(x10-x0); e=3*10000/(x10-x0)
        points.append(dict(px=x,py=y,alternate_centroid=list(readings[1]),cycle=n,low=n-e,high=n+e,retention=(y0-y)*100/(y0-y100),included=(n-e>0 and n+e<=2000)))
    accepted=[p for p in points if p['included']]; assert len(accepted)==3
    x,y=(np.array([p[k] for p in accepted]) for k in ('cycle','retention'))
    features=dict(zip(B,map(float,(y[-1],y.mean(),np.polyfit(x/1000,y,1)[0],np.ptp(y),x[-1],10000))))
    return features,dict(doi='10.3390/nano15050387',figure='Fig.7(c), left lower panel, red FWCA-4 markers; known development label',axes=dict(x0=x0,x10000=x10,y0=y0,y100=y100),reading_bound_px=3,approx_y_bound_pp=3*100/(y0-y100),notes='Use original percentage axis. Exclude points whose uncertainty crosses zero or 20%. The rightmost label and inset are not inputs. Alternate threshold is a processing check, not a second human reader.',figure_path=rel(fig),figure_sha256=sha(fig),xml_path=rel(xml),xml_sha256=sha(xml),points=points,features=features)
def main(out):
    if out.exists() and any(out.iterdir()):raise FileExistsError('Refusing to replace an existing delivery')
    out.mkdir(parents=True,exist_ok=True); d=open_database(); cfg=read(ROOT/'data/current_database.json'); assert cfg['sha256']=='092124bd9df25ae2d258cd46588ae27fde9371ace329cb3070ae3f48b4f7d279'
    l=read(ROOT/'data/current_literature.json'); lp=ROOT/l['directory']/l['database_file']; assert sha(lp)==l['sha256']; reg=sqlite3.connect(lp.as_uri()+'?mode=ro',uri=True)
    titles={doi(k):v for k,v in reg.execute('select doi,title from identity_inventory where doi is not null')}; reg.close()
    titles.update({'10.1039/c7ra13013a':'Preparation of nitrogen-doped porous carbons for high-performance supercapacitor using biomass of waste lotus stems','10.3390/nano16211412':'KOH-Activated Hierarchical Porous Carbon Derived from Suaeda salsa for Supercapacitor Electrodes: Pore-Structure Evolution and Electrochemical Behavior','10.1039/d3nj04881k':'Sorghum-derived porous carbon for outstanding green supercapacitors'})
    rows={}; seen={v:set() for v in V}; ar={}; provenance={}; years={}
    srcs=[]
    def basic(k,s,sample,y,feat,yr=None,relation=None):
        if yr: years.setdefault(s,set()).add(int(yr))
        if k not in rows:rows[k]=dict(doi=s,sample=sample,target=float(y),A=dict(feat),B=None,relation=relation,flags=set(),notes=[],evidence=[])
        r=rows[k];assert r['doi']==s and abs(r['target']-float(y))<1e-8 and r['A']['cycle_count']==feat['cycle_count']; return r
    for v in V:
        for a in d.fetch(v).rows:
            k=a['endpoint_id'];s=doi(a.get('source_family_group_v23') or a['source_group']);assert doi(a['source_group'])==s and a['system']=='3E'
            r=basic(k,s,a['sample_name'],a['retention_pct'],{z:a.get(z) for z in A},a.get('source_year'),a.get('retention_relation'));r['flags'].add(v);seen[v].add(k);ar[k]=a
    for k,a in ar.items():
        r=rows[k]; ev=[{z:e.get(z) for z in ('source_id','locator','observation_id')} for e in d.evidence(k,'retention_pct') if e.get('currently_selected')];r['evidence'].append({'database':cfg['version'],'endpoint_id':k,'selected':ev,'pages':a.get('evidence_pages'),'file':a.get('source_pdf'),'sha256':a.get('source_sha256')});
        if k not in seen[V[1]]: r['notes'].append(d.holds(k).get('reason') or a.get('review_reason_v12') or 'Sensitivity only; preserve original review.')
    for prefix in ('第五十九','第七十六'):
        p=next(BASE.glob(prefix+'*/input_snapshot.json'));snap=read(p);srcs.append(p)
        for b in (snap['3E'] if isinstance(snap,dict) else snap):
            k=b['endpoint_id'];s=doi(b['source_family']);f=dict(b['static_features'],cycle_count=int(b['features']['target_cycle_count']));r=basic(k,s,b['sample_name'],b['target'],f);r['flags'].add('early20');features={z:b['features'][z] for z in B};assert not r['B'] or r['B']==features;r['B']=features
            r['evidence'].append({'source_snapshot':rel(p),'row_id':b['row_id'],'curve_id':b.get('curve_id'),'local_evidence':b.get('evidence')})
            if k not in ar and not r['relation']:r['relation']='as_frozen_in_curve_snapshot'
            if k in ar:
                for z in A:
                    if f.get(z)!=r['A'].get(z):r['evidence'][-1].setdefault('original_B_static_differences',{})[z]=f.get(z)
    a=d.by_endpoint('candidate:TE008'); bf,proof=fwca(); s=doi(a['source_group']);r=basic(a['endpoint_id'],s,a['sample_name'],a['retention_pct'],{z:a.get(z) for z in A},a['source_year'],'eq'); r['flags'].add('early20');r['B']=bf;r['notes'].append('A冻结：参比仍未核实。B仅使用已核 Fig.7(c) 早期点与目标圈数。');r['evidence'].append({'local':'FWCA-4_fig7c.json','database_endpoint':a['endpoint_id'],'source_url':'https://www.mdpi.com/2079-4991/15/5/387'}); dump(out/'FWCA-4_fig7c.json',proof)
    s='10.1039/d3nj04881k'; k='P80:SAC-2:3E:10000';r=basic(k,s,'SAC-2',98.4,dict(zip(A,[10000,10,'KOH',2,None,None,1270.67,'Hg/HgO'])),2024,'eq');r['notes'].append('Fig.2(f) 三电极；Fig.4(f) 的97.5%属于双电极器件。CV电位窗不填作循环窗；前20%尚缺清晰读数。');r['evidence'].append({'source_url':'https://pubs.rsc.org/en/content/articlehtml/2024/nj/d3nj04881k','label':'§3.2, Fig.2(f), SAC-2, 10000 GCD cycles at 10 A/g vs initial','conditions':'§2.3, §3.2, Table 1. First published 2023-11-22; issue 2024.'})
    dbp=out/'retention50.sqlite'; db=sqlite3.connect(dbp);db.execute('pragma foreign_keys=on');db.execute('create table papers(doi text primary key,title text not null,issue_or_database_year integer)');
    db.execute('create table endpoints(endpoint_id text primary key, doi text not null references papers, sample text not null, retention_pct real not null, relation text, '+','.join(z+(' text' if z in ('electrolyte','reference_electrode') else ' real') for z in A+B)+',recent_a integer,all_years_a integer,sensitivity_a integer,early_b integer,notes text,evidence_json text not null)');
    papers=sorted({r['doi'] for r in rows.values()});assert len(papers)==50 and not RESERVE.intersection(papers)
    for s in papers:
        y=years.get(s,set());assert len(y)<=1 and titles.get(s);db.execute('insert into papers values(?,?,?)',(s,titles[s],next(iter(y),None)))
    for k,r in sorted(rows.items()):
        ff=r['flags'];v=[k,r['doi'],r['sample'],r['target'],r['relation']]+[r['A'].get(z) for z in A]+[(r['B'] or {}).get(z) for z in B]+[int(v in ff) for v in V+['early20']]+[' '.join(r['notes']),j(r['evidence'])];db.execute('insert into endpoints values('+','.join('?'*len(v))+')',v)
        if 'early20' in ff:assert all(math.isfinite(r['B'][z]) for z in B) and 0<r['B'][B[-2]]<=0.2*r['A']['cycle_count']+1e-5
        if 'reported_3e_all_years' in ff:assert all(r['A'].get(z) is not None for z in A)
    for name,condition,cols in [('direct_recent','recent_a=1',A),('direct_cross_year','all_years_a=1',A),('direct_sensitivity','sensitivity_a=1',A),('curve_early20','early_b=1',B)]:db.execute(f"create view {name} as select endpoint_id,doi,sample,"+','.join(cols)+f",retention_pct from endpoints where {condition}")
    db.execute('create view protocol_inventory as select endpoint_id,doi,sample,cycle_count,electrolyte,concentration_mol_L,reported_current_A_g,retention_pct,relation,notes from endpoints');db.commit()
    assert db.execute('pragma integrity_check').fetchone()==('ok',) and not db.execute('pragma foreign_key_check').fetchall()
    def count(cond):return list(db.execute('select count(*),count(distinct doi) from endpoints where '+cond).fetchone())
    assert db.execute('select count(*) from (select doi,sample,cycle_count,electrolyte,concentration_mol_L,reported_current_A_g,count(*) n from endpoints group by 1,2,3,4,5,6 having n>1)').fetchone()[0]==0
    counts={k:count(v) for k,v in {'labels':'1','direct_recent':'recent_a','direct_cross_year':'all_years_a','direct_sensitivity':'sensitivity_a','early20':'early_b','either_main':'all_years_a or early_b','any_registered_use':'all_years_a or early_b or sensitivity_a','known_protocol':'cycle_count is not null and electrolyte is not null and concentration_mol_L is not null and reported_current_A_g is not null','KOH':"lower(electrolyte)='koh'",'matched_static':"lower(electrolyte)='koh' and concentration_mol_L between 1 and 6 and reported_current_A_g between 1 and 10 and cycle_count between 1000 and 10000",'matched_static_with_early':"early_b and lower(electrolyte)='koh' and concentration_mol_L between 1 and 6 and reported_current_A_g between 1 and 10 and cycle_count between 1000 and 10000"}.items()};assert counts['labels']==[66,50] and counts['early20']==[37,31] and counts['direct_cross_year']==[51,37] and counts['either_main'][1]==43 and counts['any_registered_use'][1]==49
    book=[]
    for s in papers:
        rr=[(k,r) for k,r in rows.items() if r['doi']==s]; af=[sum(z in r['flags'] for _,r in rr) for z in V+['early20']];
        uq=lambda seq:'；'.join(dict.fromkeys(str(x) for x in seq));
        priority='已接入早期曲线' if af[3] else ('优先核原图：协议相符' if any((r['A'].get('electrolyte')=='KOH' and 1<=(r['A'].get('concentration_mol_L') or -1)<=6 and 1<=(r['A'].get('reported_current_A_g') or -1)<=10 and 1000<=r['A']['cycle_count']<=10000) for _,r in rr) else '次批核图：工况另分层');
        book.append(dict(序号=len(book)+1,DOI=s,题名=titles[s],样品=uq(r['sample'] for _,r in rr),循环测试='；'.join(f"{r['sample']}: {r['A']['cycle_count']:g}圈 / {r['A'].get('electrolyte')} {r['A'].get('concentration_mol_L')} M / {r['A'].get('reported_current_A_g')} A/g / {r['target']:g}% [{r['relation']}]" for _,r in rr),去重终点=len(rr),原A记录=af[0],跨年份A记录=af[1],A敏感性视图记录=af[2],早期曲线B记录=af[3],下一步=priority,审查备注=uq(n for _,r in rr for n in r['notes']),证据键=uq(k for k,_ in rr)))
    csvout(out/'50篇文献清单.csv',book);db.close();dump(out/'manifest.json',dict(counts_order=['endpoint_rows','distinct_dois'],counts=counts,protected_sources={rel(p):sha(p) for p in srcs+[lp,ROOT/cfg['version_directory']/cfg['database_file']]},protected_outside=sorted(RESERVE),new_curve_original=proof['figure_sha256'],outputs={p.name:sha(p) for p in (dbp,out/'50篇文献清单.csv',out/'FWCA-4_fig7c.json')},new_fits=0));print(json.dumps(counts,indent=2))
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,default=DEST); main(ap.parse_args().out)