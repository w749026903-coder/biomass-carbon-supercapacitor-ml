"""Audit development coverage and one frozen applicability-based prediction rule."""
import argparse, collections, json, hashlib, math, re, sys, subprocess, warnings
from fractions import Fraction
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R))
from tools.retention_mild_scope_v64 import outside_reasons
from tools.retention_new_evidence_development_v59 import fit, environment
B=next(R.glob('保持率达标研究_v3*')); O=next(B.glob('第七十九轮*'))
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'));plan=read(O/'plan.json')
def get(k):return read(R/plan['sources'][k][0])
def collect(rows):
    return [dict(id=x['row_id'],doi=x['source_family'],y=x['observed'],p=x['predicted'],curve=x.get('curve_id',x['row_id'])) for x in rows]
def scores(rows):
    by=collections.defaultdict(collections.Counter)
    for x in rows:by[x['doi']][x['curve']]+=1
    assert all(re.fullmatch(r'doi:10\.\d{4,9}/\S+',s) and s==s.lower() for s in by) and len({x['id'] for x in rows})==len(rows)
    w=[Fraction(1,len(by)*len(by[x['doi']])*by[x['doi']][x['curve']]) for x in rows];assert sum(w)==1
    a=np.array([x['y'] for x in rows]);p=np.array([x['p'] for x in rows]);ww=np.array(w,float);da=a-ww@a;dp=p-ww@p;e=p-a
    q=0
    for err,m in sorted(zip(abs(e),w)):
        q+=m
        if q>=Fraction(9,10):break
    var=ww@(da**2);vp=ww@(dp**2)
    return dict(papers=len(by),rows=len(rows),r=float((ww@(da*dp))/math.sqrt(var*vp)) if vp*var>1e-15 else None,r2=float(1-(ww@(e**2))/var) if var>1e-15 else None,mae=float(ww@abs(e)),rmse=math.sqrt(ww@(e**2)),p90_abs=float(err))
def sensitivity(rows):
    src=sorted({x['doi'] for x in rows});removed=[]
    for s in src:
        sc=scores([x for x in rows if x['doi']!=s]);removed.append([s,sc['r2'],sc['r']])
    return dict(r2_range=[min(r[1] for r in removed),max(r[1] for r in removed)],r_range=[min(r[2] for r in removed),max(r[2] for r in removed)],per_source=removed)
def run():
    assert subprocess.check_output(['git','-c',f'safe.directory={R.as_posix()}','show','4e9dee0:'+(O/'plan.json').relative_to(R).as_posix()],cwd=R)==(O/'plan.json').read_bytes()
    for path,h in plan['sources'].values():assert hashlib.sha256((R/path).read_bytes()).hexdigest()==h
    a=get('59/input_snapshot')['3E'];n=get('76/input_snapshot'); pool={x['row_id']:x for x in a+n}; assert len(pool)==36
    assert all(pool[x['row_id']]==x for x in a+n) and len({x['source_family'] for x in pool.values()})==30
    p59=get('59/training_plan');assert p59['environment']==environment();p64=get('64/training_plan')['scopes']['koh_1_to_6m_mild_early']; p67=get('67/diagnostic_10000')['predictions'];p76=get('76/predictions')['p67_routed'];lotusid=get('76/training_plan')['new_id'];lot=pool[lotusid]; locus={x['row_id'] for x in a};assert lotusid not in locus
    assert lot['source_family'] not in {x['source_family'] for x in a}
    ext={'doi:10.1039/d1ma00679g','doi:10.1016/j.sajce.2026.100908'};assert not ext.intersection(x['source_family'] for x in pool.values())
    def checkfold(folds,k,src):
        f=folds[src];assert k in f['test'] and all(pool[t]['source_family']!=src for t in f['train']) and set(f['train']).isdisjoint(f['test'])
    narrow={x['row_id']:x for x in p67};recent={x['row_id']:x for x in p76};assert set(narrow)==set(p64['included']) and set(recent)==set(narrow)|{lotusid}
    rf='RF_static_p2_raw_delta';arch=get('59/heldout_predictions')['author:3E']['configurations']; wide={x['row_id']:dict(x) for x in arch[rf]};cfg=next(c for c in p59['cohorts']['3E']['configurations'] if c['id']==rf)
    with warnings.catch_warnings(record=True) as warn:pred,=fit(cfg,a,[{k:v for k,v in lot.items() if k!='target'}],{})
    assert not warn;wide[lotusid]=dict(recent[lotusid],predicted=pred,model=rf)
    routed=[];routes={}; outside=[]
    for k,obs in pool.items():
        src=obs['source_family'];why=outside_reasons(obs,p64['rules']);assert bool(why)==(k not in recent)
        if k in locus:checkfold(p59['cohorts']['3E']['folds'],k,src)
        if k in narrow:
            checkfold(get('67/training_plan')['folds'],k,src);chosen=narrow[k];rule='P67_mild'
        elif k==lotusid:
            checkfold(get('76/training_plan')['folds'],k,src);chosen=recent[k];rule='P67_lotus_held_out'
        else: chosen=wide[k];rule='broad_RF';outside.append(chosen)
        assert chosen['observed']==wide[k]['observed']==obs['target'] and chosen['source_family']==wide[k]['source_family']==src
        routes[k]=dict(rule=rule,reasons=why);routed.append(chosen)
    cohorts={'historical8':get('61/original13_predictions'),'current15': [x for x in p67 if pool[x['row_id']]['static_features']['concentration_mol_L']>=2],'mild18':p67,'lotus19':p76,'broad27':get('63/predictions')['strong_log_25'],'primary29':arch[p59['cohorts']['3E']['primary']],'rf29':arch[rf],'rf30':list(wide.values()),'route30':routed,'outside_mild':outside,'direct34':get('A/outer_predictions')['latest_assisted_ridge']}
    allrows={k:collect(v) for k,v in cohorts.items()};metrics={k:scores(v) for k,v in allrows.items()}
    for g,ref in [('current15',get('78/results')['metrics']['all']['control']),('mild18',get('67/diagnostic_10000')['full_score']),('historical8',get('61/original13_scorecard')['metrics']),('lotus19',get('76/results')['results']['p67_routed']['expanded24']['metrics'])]:
        assert all(math.isclose(metrics[g][m],ref[m],abs_tol=1e-9) for m in ('r2','mae','rmse'))
    simple=get('59/heldout_predictions')['author:3E']['baselines']['early_persistence'];simple=collect(simple)+[dict(id=lotusid,doi=lot['source_family'],y=lot['target'],p=lot['last_early'],curve=lot['curve_id'])];metrics['last30']=scores(simple)
    sources=sorted({x['doi'] for x in allrows['route30']}); rng=np.random.default_rng(20261119);batches=rng.integers(0,len(sources),(10000,len(sources)));suff=[]
    for s in sources:
        v=[x for x in allrows['route30'] if x['doi']==s];assert len({x['curve'] for x in v})==len(v)
        y=np.array([x['y'] for x in v]);p=np.array([x['p'] for x in v]);suff.append([y.mean(),p.mean(),(y*y).mean(),(p*p).mean(),(y*p).mean(),((y-p)**2).mean()])
    av=np.array(suff)[batches].mean(axis=1);y,p,y2,p2,yp,mse=av.T;vy=y2-y*y;vp=p2-p*p;assert min(vy)>0 and min(vp)>0
    boot={'R2':np.quantile(1-mse/vy,[.025,.975]).tolist(),'Pearson_r':np.quantile((yp-y*p)/np.sqrt(vy*vp),[.025,.975]).tolist(),'draws':len(av),'note':'descriptive resampling of DOI blocks; no refitting, tuning or novel external evaluation'}
    cases=get('A/input_snapshot')['retention']; ix={x['row_id']:x for x in cases}; aids={x['source_family'] for x in cases}; bids=set(sources); missing=aids-bids
    catalog=read(R/'三电极端点扩充_20261018/corpus_index.json'); candidates=[]
    for s in sorted(missing):
        hits=[z for z in catalog if z.get('doi','').lower()==s[4:] and (R/z.get('source_path','_absent')).is_file()]
        arr=[x for x in cases if x['source_family']==s];candidates.append(dict(doi=s[4:],cases=[dict(sample=x['sample_name'],cycles=x['conditions']['cycle_count'],electrolyte=x['conditions']['electrolyte'],mol_L=x['conditions']['concentration_mol_L'],current=x['conditions']['reported_current_A_g'],row_id=x['row_id']) for x in arr],located_local_files=[z['source_path'] for z in hits],evidence_status='existing endpoint only; exact eligible early curves and prior deferrals require audit',unseen=False))
    sensitivity_by_scope={k:sensitivity(allrows[k]) for k in ['current15','mild18','lotus19','rf30','route30']}
    return dict(metrics=metrics,sensitivity=sensitivity_by_scope,bootstrap_route30=boot,route_details=routes,routed_rows=allrows['route30'],fixed_rf_rows=allrows['rf30'],outside_narrow_ids=[x['row_id'] for x in outside],current_literature_gap={'A':len(aids),'B':len(bids),'overlap':len(aids&bids),'union':len(aids|bids),'A_not_in_B':candidates},fresh_fits=1,independent_scored_unchanged=1,model_promoted=False)
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--verify',action='store_true');args=ap.parse_args();d=run();f=O/'results.json'
 if args.verify: assert read(f)==d
 else:
    with f.open('x',encoding='utf8',newline='\n') as o:json.dump(d,o,ensure_ascii=False,indent=2,allow_nan=False);o.write('\n')
 print('papers records r R2 MAE RMSE')
 for k,s in d['metrics'].items(): print(k,*[round(s[c],4) for c in ['papers','rows','r','r2','mae','rmse']])
 print('intervals',d['bootstrap_route30']);print('sensitivity18',d['sensitivity']['mild18']['r2_range']);q=d['current_literature_gap'];print('coverage',q['A'],q['B'],q['overlap'],q['union']);print('gap',[(x['doi'],len(x['located_local_files'])) for x in q['A_not_in_B']])
