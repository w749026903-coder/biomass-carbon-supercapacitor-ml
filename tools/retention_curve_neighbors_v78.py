"""One frozen development experiment. No endpoint from the query source enters matching."""
import argparse, hashlib, json, math, sqlite3, subprocess
from bisect import bisect_left
from collections import Counter, defaultdict
from fractions import Fraction
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
BASE=next(ROOT.glob('保持率达标研究_v3*'))
OUT=next(BASE.glob('第七十八轮*'))
GIT=['git','-c',f'safe.directory={ROOT.as_posix()}']
def read(p):return json.loads(p.read_text(encoding='utf8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def git(*cmd):return subprocess.check_output(GIT+list(cmd),cwd=ROOT)
def source_data():
    plan=read(OUT/'plan.json');assert git('show','a7a82d4:'+(OUT/'plan.json').relative_to(ROOT).as_posix())==(OUT/'plan.json').read_bytes()
    files={k:ROOT/v['path'] for k,v in plan['protected'].items()}
    assert all(sha(f)==plan['protected'][k]['sha256'] for k,f in files.items())
    scoped=read(files['cohort'])['scopes']['koh_1_to_6m_mild_early']['included']; orig=read(files['rows'])['3E']
    keep={r['row_id']:r for r in orig if r['row_id'] in scoped and 2<=r['static_features']['concentration_mol_L']<=6}
    assert len(keep)==20 and len({r['source_family'] for r in keep.values()})==15
    refs={p['row_id']:p for p in read(files['reference'])['predictions'] if p['row_id'] in keep}
    assert set(refs)==set(keep) and all(refs[k]['observed']==r['target'] and refs[k]['source_family']==r['source_family'] for k,r in keep.items())
    ptr=read(files['db_pointer']);db=ROOT/ptr['database'];assert sha(db)==ptr['sha256']
    shapes={};truth={}; raw={}
    with sqlite3.connect(db.as_uri()+'?mode=ro&immutable=1',uri=True) as conn:
        for k,r in keep.items():
            if r['features']['target_cycle_count']!=10000:continue
            points=[]
            if r['sample_name'] in ('SD-AC','SPC3'):
                file_key,field=('wood','markers') if r['sample_name']=='SD-AC' else ('strawberry','early_markers')
                s=read(files[file_key])['records']['3E'];assert s['sample_name']==r['sample_name'] and s['target_cycle_count']==10000
                for a in s[field]:
                    if a['cycle_interval'][1]<=2000 and a['cycle_reading']>0:
                        points.append([a['cycle_reading'],*a['cycle_interval'],a['early_ordinate_pct'],*a['ordinate_interval_pp']])
            else:
                file_key='db_pointer'; items=conn.execute('SELECT raw_json FROM curve_points WHERE curve_id=? AND cycle_coordinate>0 AND cycle_coordinate<=2000 ORDER BY cycle_coordinate',(r['curve_id'],))
                for (txt,) in items:
                    a=json.loads(txt)
                    if a['cycle_upper']<=2000:
                        points.append([a['cycle_coordinate'],a['cycle_lower'],a['cycle_upper'],a['retention_pct'],*a['reading_interval_pp']])
            points.sort();assert len(points)>=3 and all(lo<=x<=hi<=2000 and yl<=y<=yh for x,lo,hi,y,yl,yh in points)
            assert all(p[0]<q[0] for p,q in zip(points,points[1:]))
            assert math.isclose(points[-1][0],r['features']['early_observed_cycle_count'],abs_tol=1e-7) and math.isclose(points[-1][3],r['last_early'],abs_tol=1e-7)
            shapes[k]=dict(id=k,source=r['source_family'],sample=r['sample_name'],static=r['static_features'],points=points,origin=file_key,curve_id=r['curve_id'])
            truth[k]=r['target']
    assert len(shapes)==12 and len({r['source'] for r in shapes.values()})==9
    return files,keep,refs,shapes,truth
def at(points,g):
    xs=[p[0] for p in points];i=bisect_left(xs,g)
    if i<len(xs) and xs[i]==g:return points[i][3:]
    if not 0<i<len(xs):return None
    a,b=points[i-1:i+1];t=(g-a[0])/(b[0]-a[0])
    return [(1-t)*v+t*w for v,w in zip(a[3:],b[3:])]
def width(p):return max(p[0]-p[1],p[2]-p[0])
def compare(q,d):
    assert q['source']!=d['source']
    a,b=q['static'],d['static'];jratio=a['reported_current_A_g']/b['reported_current_A_g'];md=a['concentration_mol_L']-b['concentration_mol_L']
    span=lambda s:None if None in (s['cycle_voltage_lower_V'],s['cycle_voltage_upper_V']) else s['cycle_voltage_upper_V']-s['cycle_voltage_lower_V']
    v,w=span(a),span(b);reasons=[]
    if max(jratio,1/jratio)>2 or abs(md)>3:reasons.append('current_or_molarity')
    if v is not None and w is not None and abs(v-w)>.2000000001:reasons.append('window_width')
    m=[];excluded=[]
    for g in [500,1000,1500]:
        x=at(q['points'],g);y=at(d['points'],g)
        if x is None or y is None or max(width(x),width(y))>2:excluded.append(g);continue
        m.append(dict(cycle=g,query=x,donor=y,overlap=max(x[1],y[1])<=min(x[2],y[2])))
    if len(m)<2:reasons.append('too_few_precise_common_coordinates')
    if max(width(q['points'][-1][3:]),width(d['points'][-1][3:]))>2:reasons.append('last_point_uncertainty')
    rms=math.sqrt(sum((r['query'][0]-r['donor'][0])**2 for r in m)/len(m)) if m else None
    if rms is not None and rms>2:reasons.append('early_shape_distance')
    return dict(query=q['id'],donor=d['id'],query_source=q['source'],donor_source=d['source'],missing_voltage_width=(v is None or w is None),matched_grid=m,unusable_grid=excluded,shape_rms=rms,distance=math.sqrt(rms*rms+math.log2(jratio)**2+(md/3)**2) if rms is not None else None,reasons=reasons)
def forecast(q,others,training_y,fallback):
    assert q['id'] not in training_y and all(a['source']!=q['source'] and a['id'] in training_y for a in others)
    pairs=[compare(q,d) for d in others]; per={}
    for a in sorted((v for v in pairs if not v['reasons']),key=lambda x:(x['distance'],x['donor'])):per.setdefault(a['donor_source'],a)
    neighbors=list(per.values())[:3]
    if len(neighbors)<2:return fallback,pairs,[],len(per)
    parts=[]
    for a in neighbors:
        at_last=a['matched_grid'][-1];est=at_last['query'][0]+training_y[a['donor']]-at_last['donor'][0]
        parts.append(dict(donor=a['donor'],source=a['donor_source'],shared_cycle=at_last['cycle'],estimate=est,weight=1/(1+a['distance'])))
    val=sum(c['estimate']*c['weight'] for c in parts)/sum(c['weight'] for c in parts)
    return val,pairs,parts,len(per)
def stats(rows,model):
    by=defaultdict(list)
    for r in rows:by[r['source']].append(r)
    wt=[Fraction(1,len(by)*len(by[r['source']])) for r in rows];assert sum(wt)==1 and len({r['curve_id'] for r in rows})==len(rows)
    y=np.array([r['observed'] for r in rows]); diff=np.array([r[model] for r in rows])-y;a=np.abs(diff);fw=np.array(wt,dtype=float);sse=np.dot(fw,diff**2);var=np.dot(fw,(y-np.dot(fw,y))**2)
    def q90(v):
        mass=Fraction()
        for value,w in sorted(zip(v,wt)):
            mass+=w
            if mass>=Fraction(9,10):return float(value)
    ae=a/y*100;return dict(rows=len(rows),papers=len(by),mae=float(np.dot(fw,a)),rmse=float(math.sqrt(sse)),r2=float(1-sse/var),mape=float(np.dot(fw,ae)),p90_ape=q90(ae),p90_abs=q90(a),src_p90_mae=float(np.quantile([np.mean([abs(r[model]-r['observed']) for r in arr]) for arr in by.values()],.9)),max_abs=float(max(a)))
def batch():
    files,keep,refs,shapes,truth=source_data();events=[];pairs=[];preds=[]
    for k,r in keep.items():
        held=r['source_family'];control=refs[k]['predicted'];pred=control;donors=[];usable=0
        if k in shapes:
            pool=[d for d in shapes.values() if d['source']!=held];pred,logs,donors,usable=forecast(shapes[k],pool,{d['id']:truth[d['id']] for d in pool},control);pairs.extend(logs)
        preds.append(dict(row=k,curve_id=r['curve_id'],source=held,sample=r['sample_name'],horizon=r['features']['target_cycle_count'],observed=r['target'],control=control,candidate=pred,donors=donors,eligible_donor_sources=usable))
    metrics={sub:{m:stats(rr,m) for m in ['control','candidate']} for sub,rr in [('all',preds),('10000',[r for r in preds if r['horizon']==10000])]}
    c=metrics['all']['control'];assert abs(c['mae']-1.8734588672202577)<1e-10 and abs(c['r2']-.8959345212343076)<1e-10 and abs(c['rmse']-2.368998989404671)<1e-10
    for sub,ds in metrics.items():
        t,o=ds['candidate'],ds['control'];events.extend([(f'{sub} {m}',t[m]<o[m]) for m in ('mae','rmse')]+[(sub+' r2',t['r2']>o['r2'])])
    events += [(m,metrics['all']['candidate'][m]<=c[m]) for m in ('p90_abs','src_p90_mae','max_abs')]+[('coverage_positive',len(preds)==20 and all(r['candidate']>0 for r in preds)),('changed_source_count',len({r['source'] for r in preds if abs(r['candidate']-r['control'])>1e-12})>=2)]
    deltas=[]
    for s in sorted({r['source'] for r in preds}):
        d=[r for r in preds if r['source']==s];deltas.append(np.mean([abs(r['candidate']-r['observed'])-abs(r['control']-r['observed']) for r in d]))
    draws=np.random.default_rng(20261118).choice(deltas,(10000,len(deltas)),replace=True).mean(axis=1)
    return {'metrics':metrics,'gates':dict(events),'retain_as_research_candidate':all(ok for _,ok in events),'delta_mae_source_bootstrap_95pp':np.quantile(draws,[.025,.975]).tolist(),'rows':preds,'locked_new_external_sources':0,'pointer_switched':False}, {'grid_and_interval_order':['pct','low','high'],'point_column_order':['cycle','low_x','high_x','pct','low_y','high_y'],'curves':shapes,'comparisons':pairs}
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--verify',action='store_true');args=ap.parse_args(); result,audit=batch()
    for name,v in [('results.json',result),('curve_comparisons.json',audit)]:
        p=OUT/name
        if args.verify:assert read(p)==v
        else:
            with p.open('x',encoding='utf8',newline='\n') as f:json.dump(v,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps({k:v for k,v in result.items() if k!='rows'},ensure_ascii=False));print([(r['sample'],r['eligible_donor_sources'],round(r['candidate']-r['observed'],2)) for r in result['rows'] if r['horizon']==10000])
