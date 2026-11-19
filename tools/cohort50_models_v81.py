"""Frozen DOI-grouped, small N first-stage experiments. fit does not choose winners."""
from pathlib import Path
import sys, json, collections, hashlib, sqlite3, argparse, platform, subprocess
import numpy as np, sklearn
from sklearn.feature_extraction import DictVectorizer
from sklearn.linear_model import Ridge
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.preprocessing import StandardScaler
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.retention_cohort_v80 import DEST,A,B,sha,dump,read
from data.training_latest import open_training_datasets
from models.v1_3.model import canonical
OUT=DEST.parent/'第八十一轮_固定50篇多输出预测_20261120'
GIT=['git','-c',f'safe.directory={ROOT.as_posix()}']
MEAN='fold_mean';REF='measured_anchor'
def collect():
    m=read(DEST/'manifest.json')
    for name,h in m['outputs'].items():assert sha(DEST/name)==h
    assert sha(DEST/'retention50.sqlite')=='d4944ce49ccd42dbb893fbcb52a90921d8df726399316edb297604ce81871499'
    db=sqlite3.connect((DEST/'retention50.sqlite').as_uri()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
    roster={r[0] for r in db.execute('select doi from papers')};tasks=collections.defaultdict(list)
    def put(t,i,s,f,y,train=True,anchor=None,role='registered',material=None):
        assert s in roster and y>0 and any(v is not None for v in f.values())
        tasks[t].append(dict(id=i,doi=s,x={k:v for k,v in f.items() if v is not None},y=float(y),train=bool(train),anchor=anchor,role=role,material=material))
    for a in db.execute('select * from endpoints order by endpoint_id'):
        for t,fields,test,train in [('protocol50',A[:4],True,a['all_years_a']),('direct_A',A,a['all_years_a'],True),('early_B',B,a['early_b'],True)]:
            if test:put(t,a['endpoint_id'],a['doi'],{k:a[k] for k in fields},a['retention_pct'],train,a[B[0]] if t=='early_B' else None,'A-eligible' if a['all_years_a'] else ('B-only' if a['early_b'] else ('sensitivity-only' if a['sensitivity_a'] else 'evidence-only')))
    db.close()
    with open_training_datasets() as ds:
        cap=ds.rows('capacity:3e_with_graph');direct={r['row_id'] for r in ds.rows('capacity:3e_reported')}; gr=collections.defaultdict(list)
        for r in cap:
            s=r['source_family'].removeprefix('doi:').lower()
            if s not in roster:continue
            f,_=canonical(r['features']);c=r['conditions'];assert c.get('method','GCD')=='GCD' and c.get('system','3E')=='3E' and r['target_name'] in ('specific_capacitance_F_g','reported_3e_capacitance_F_g') and r['ready_for_training_inputs'] # typed 3E GCD task supplies missing redundant tags
            keep=['reported_current_A_g','electrolyte','concentration_mol_L','voltage_lower_V','voltage_upper_V','reference_electrode','BET_m2_g','total_pore_volume_cm3_g','micropore_volume_cm3_g','activation_temperature_C','activation_duration_h']
            put('specific_C',r['row_id'],s,{k:f.get(k) for k in keep},r['target'],role='reported' if r['row_id'] in direct else 'graph',material=r['material_key'])
            key=(s,r['material_key'],*(c.get(k) for k in ['electrolyte','concentration_mol_L','voltage_lower_V','voltage_upper_V','reference_electrode','current_mass_basis','capacitance_basis']))
            gr[key].append((f['reported_current_A_g'],r))
        for key,rs in gr.items():
            anchor=[r for a,r in rs if a==1]
            if len(anchor)!=1:continue
            for amp,r in rs:
                if amp<2:continue
                ac=float(anchor[0]['target']); f={'C_at_1_A_g':ac,'log_target_A_g':float(np.log(amp)),'electrolyte':key[2],'concentration_mol_L':key[3]}
                put('rate_C',r['row_id'],key[0],f,r['target'],anchor=ac,role='anchor:'+anchor[0]['row_id'],material=r['material_key'])
        for r in ds.rows('material:ordinary_biomass_pretest:BET_surface_area_m2_g'):
            s=r['source_family'].removeprefix('doi:').lower()
            if s not in roster:continue
            f,_=canonical(r['features']); allowable={k:v for k,v in f.items() if k.startswith('process__') and k.endswith(('temperature_C','duration_h','heating_rate_C_min')) or k in ('activation_temperature_C','activation_duration_h','precarbonization_temperature_C','heating_rate_C_min','Raman_ID_IG','XPS_C_atomic_pct_v15','XPS_O_atomic_pct_v15','XPS_N_atomic_pct_v15')}
            # May lack any of these predictors: keep the row and use training-fold imputation.
            allow={k:v for k,v in allowable.items() if v is not None};put('BET',r['row_id'],s,allow or {'intercept':1.0},r['target'],material=r['material_key'])
    for t,rs in tasks.items():assert len({r['id'] for r in rs})==len(rs)
    return tasks
def freeze():
    assert not OUT.exists();tasks=collect();OUT.mkdir();dump(OUT/'inputs.json',tasks)
    dump(OUT/'plan.json',dict(cohort_commit='b7f86a5',database_sha256=sha(DEST/'retention50.sqlite'),inputs_sha256=sha(OUT/'inputs.json'),code_sha256=sha(Path(__file__)),latest=read(ROOT/'data/current_training_latest.json'),versions=[platform.python_version(),np.__version__,sklearn.__version__],coverage={t:[len(rs),len(set(r['doi'] for r in rs)),len(set(r['doi'] for r in rs if r['train']))] for t,rs in tasks.items()},evaluators=['fold_mean','measured_anchor where applicable','ridge alpha 10','RF 48 depth 5 leaf 2','Huber GB 40 depth 2 leaf 3','fixed 50% ridge + 50% RF (primary)'],seed=811,units={'protocol50':'pp','direct_A':'pp','early_B':'pp','specific_C':'F/g','rate_C':'F/g','BET':'m²/g'},rules='Every DOI held out entirely; equal total training and scoring weight per DOI. Only A-admitted rows train the 50-DOI protocol stress test. Keep all held-only rows for a separate audit, not primary training admissions. Group bootstrap measures descriptive uncertainty. Pearson r>0.90 is a screen, original retention goal R²>0.95, MAE<=2pp, RMSE<=3pp remains distinct. Do not select secondary winner as externally validated. No additional configurations after results. No formal threshold for non-retention MAE yet; compare source-weighted mean and measured reference. No prospective external cohort.'))
def weights(gs):
    c=collections.Counter(gs);a=np.array([1/c[k] for k in gs]);return a/a.mean()
def encode(tr,te):
    fields=sorted(set().union(*(r['x'] for r in tr))); fill={};cat=set()
    for k in fields:
        vs=[r['x'][k] for r in tr if k in r['x']]
        if isinstance(vs[0],str):cat.add(k)
        else:fill[k]=float(np.median(vs))
    def conv(r):
        return {k:(str(r['x'].get(k,'missing')) if k in cat else float(r['x'].get(k,fill.get(k,0)))) for k in fields}
    dv=DictVectorizer(sparse=False);X=dv.fit_transform([conv(r) for r in tr]);Z=dv.transform([conv(r) for r in te]);ss=StandardScaler().fit(X,sample_weight=weights([r['doi'] for r in tr]));return ss.transform(X),ss.transform(Z)
def metrics(y,p,w):
    w=w/w.sum();m=np.sum(y*w);v=np.sum(w*(y-m)**2);e=p-y;pm=np.sum(w*p);vp=np.sum(w*(p-pm)**2);return dict(r=float(np.sum(w*(y-m)*(p-pm))/np.sqrt(v*vp)) if v>1e-15 and vp>1e-15 else None,R2=float(1-np.sum(w*e*e)/v) if v>1e-15 else None,MAE=float(np.sum(w*abs(e))),RMSE=float(np.sqrt(np.sum(w*e*e))))
def run():
    plan=read(OUT/'plan.json');assert sha(OUT/'inputs.json')==plan['inputs_sha256'] and sha(Path(__file__))==plan['code_sha256']; assert not (OUT/'results.json').exists()
    committed=subprocess.check_output(GIT+['show','HEAD:'+(OUT/'plan.json').relative_to(ROOT).as_posix()],cwd=ROOT);assert json.loads(committed)==plan
    tasks=read(OUT/'inputs.json');allscore={};preds={};fits=0
    for t,rs in tasks.items():
        pred=[]; folds=sorted({r['doi'] for r in rs})
        for doi in folds:
            tr=[r for r in rs if r['doi']!=doi and r['train']];te=[r for r in rs if r['doi']==doi];assert all(r['doi']!=doi for r in tr);X,Z=encode(tr,te);y=np.array([r['y'] for r in tr]);w=weights([r['doi'] for r in tr]);yp={MEAN:np.repeat(np.average(y,weights=w),len(te))}
            if all(r['anchor'] is not None for r in te):yp[REF]=[r['anchor'] for r in te]
            for n,m in [('ridge',Ridge(alpha=10)),('RF',RandomForestRegressor(n_estimators=48,max_depth=5,min_samples_leaf=2,random_state=811,n_jobs=1)),('GB',GradientBoostingRegressor(loss='huber',n_estimators=40,max_depth=2,min_samples_leaf=3,random_state=811))]:
                yp[n]=m.fit(X,y,sample_weight=w).predict(Z);fits+=1
            yp['blend']=(yp['ridge']+yp['RF'])*0.5
            for i,r in enumerate(te):pred.append(dict(id=r['id'],doi=doi,y=r['y'],role=r['role'],admitted_fit=r['train'],pred={k:float(v[i]) for k,v in yp.items()}))
        preds[t]=pred;gs=[r['doi'] for r in pred];y=np.array([r['y'] for r in pred]);w=weights(gs);allscore[t]={}
        for k in pred[0]['pred']:
            p=np.array([r['pred'][k] for r in pred]);allscore[t][k]=metrics(y,p,w)
        rng=np.random.default_rng(811);gidx=np.array([folds.index(s) for s in gs]);bp=[];p=np.array([r['pred']['blend'] for r in pred])
        for _ in range(2000):
            counts=np.bincount(rng.integers(len(folds),size=len(folds)),minlength=len(folds));ws=w*counts[gidx];bp.append(metrics(y,p,ws))
        allscore[t]['blend_interval']={k:np.quantile([r[k] for r in bp if r[k] is not None],[.025,.975]).tolist() for k in bp[0]}
        if t=='protocol50':
            allscore[t]['strata']={}
            for role in sorted(set(r['role'] for r in pred)):
                sub=[r for r in pred if r['role']==role];allscore[t]['strata'][role]=dict(rows=len(sub),sources=len(set(r['doi'] for r in sub)),**metrics(np.array([r['y'] for r in sub]),np.array([r['pred']['blend'] for r in sub]),weights([r['doi'] for r in sub])))
    dump(OUT/'predictions.json',preds);dump(OUT/'results.json',dict(fits=fits,coverage=plan['coverage'],scores=allscore))
    for t,v in allscore.items():print(t,plan['coverage'][t],[(k,round(s['r'],3) if s['r'] else None,round(s['R2'],3)) for k,s in v.items() if k not in ('blend_interval','strata')])
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('action',choices=['freeze','run']);(freeze if ap.parse_args().action=='freeze' else run)()