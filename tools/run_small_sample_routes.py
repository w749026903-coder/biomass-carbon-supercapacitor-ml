"""One bounded pass of frozen small-sample feasibility routes; no score-driven search."""
from pathlib import Path
import collections, hashlib, json, math, sys, time, warnings
import numpy as np
from scipy.interpolate import PchipInterpolator
from scipy.optimize import nnls, least_squares
from sklearn.linear_model import Ridge
from sklearn.ensemble import RandomForestRegressor
from sklearn.neural_network import MLPRegressor
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import Matern
from xgboost import XGBRegressor
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.prepare_small_sample_routes import RUN,MATERIAL_FIELDS,CONDITION_FIELDS,read,write,sha,now
SEED=20261029
START=time.monotonic();EVENTS=[];PREDS=[];FAILURES=[];JOBS=[]

def weights(rows):
 units=collections.defaultdict(lambda:collections.Counter())
 for r in rows:units[r['source_family']][r.get('curve_id')or r.get('material_key')or r['row_id']]+=1
 return np.array([1/(len(units)*len(units[r['source_family']])*units[r['source_family']][r.get('curve_id')or r.get('material_key')or r['row_id']])for r in rows])

class Encoder:
 def fit(self,rows,local=False):
  self.schema=[];minimum=1 if local else 3
  for k in sorted({k for r in rows for k in r['features']}):
   obs=[r for r in rows if r['features'].get(k)is not None]
   if len(obs)<max(2,int(.15*len(rows)))or len({r['source_family']for r in obs})<minimum:continue
   vals=[r['features'][k]for r in obs]
   if all(isinstance(v,str)for v in vals):
    vocab=sorted(set(vals));self.schema.append(dict(field=k,kind='categorical',vocab=vocab))
   else:
    assert all(isinstance(v,(int,float))for v in vals),k
    med=float(np.median(vals));z=np.array([r['features'].get(k)if r['features'].get(k)is not None else med for r in rows]);w=weights(rows)
    log=all(v>=0 for v in vals)and any(s in k.lower()for s in ['bet','volume','current','ratio','cycle_count'])
    if log:z=np.log1p(z)
    center=float(np.average(z,weights=w));scale=float(np.sqrt(np.average((z-center)**2,weights=w)))or 1
    self.schema.append(dict(field=k,kind='numeric',median=med,log=log,center=center,scale=scale))
  assert self.schema,'No eligible fields';return self
 def transform(self,rows):
  out=[]
  for r in rows:
   v=[]
   for s in self.schema:
    x=r['features'].get(s['field'])
    if s['kind']=='categorical':v.extend([float(x==c)for c in s['vocab']]+[float(x not in s['vocab'])])
    else:
     missing=x is None;x=s['median']if missing else x;x=math.log1p(x)if s['log']else x;v.extend([(x-s['center'])/s['scale'],float(missing)])
   out.append(v)
  return np.array(out,dtype=float)

def log_event(event):
 assert len(EVENTS)<1200,'Frozen fit budget exceeded'
 event.update(fit_index=len(EVENTS)+1,elapsed_seconds=round(time.monotonic()-START,3));EVENTS.append(event)
 with (RUN/'fit_events.jsonl').open('a',encoding='utf8')as f:f.write(json.dumps(event,ensure_ascii=False,allow_nan=False)+'\n')
 write(RUN/'progress.json',dict(status='running',completed_fits=len(EVENTS),planned_fits=PLANNED,elapsed_seconds=event['elapsed_seconds'],last_route=event['route'],last_model=event['model']))
 if len(EVENTS)%25==0:print(f"{len(EVENTS)}/{PLANNED} fits; {event['route']} {event['model']}; {event['elapsed_seconds']}s",flush=True)

def fit_predict(kind,train,test,route,unit,local=False):
 event=dict(route=route,model=kind,held_unit=unit,local_within_family=local,train_sources=sorted({r['source_family']for r in train}),test_sources=sorted({r['source_family']for r in test}),train_row_ids=[r['row_id']for r in train],test_row_ids=[r['row_id']for r in test])
 assert local or not(set(event['train_sources'])&set(event['test_sources']))
 if local:assert not({r['material_key']for r in train}&{r['material_key']for r in test})
 try:
  encoder=Encoder().fit(train,local);x=encoder.transform(train);xt=encoder.transform(test);w=weights(train);y=np.log([r['target']for r in train]);center=float(np.average(y,weights=w));scale=float(np.sqrt(np.average((y-center)**2,weights=w)))or 1.;z=(y-center)/scale
  if kind=='ridge':model=Ridge(alpha=1.)
  elif kind=='random_forest':model=RandomForestRegressor(n_estimators=160,max_depth=6,min_samples_leaf=2,random_state=SEED,n_jobs=1)
  elif kind=='xgboost':model=XGBRegressor(n_estimators=160,max_depth=2,learning_rate=.04,reg_lambda=5.,subsample=1.,colsample_bytree=1.,random_state=SEED,n_jobs=1,objective='reg:squarederror')
  elif kind=='small_BP_MLP':model=MLPRegressor(hidden_layer_sizes=(16,),solver='lbfgs',alpha=1.,max_iter=1500,random_state=SEED)
  elif kind=='fixed_Matern_GPR':model=GaussianProcessRegressor(kernel=Matern(length_scale=2.,nu=1.5),alpha=.04,optimizer=None,normalize_y=False)
  else:raise ValueError(kind)
  with warnings.catch_warnings(record=True)as caught:
   warnings.simplefilter('always')
   if kind in ['small_BP_MLP','fixed_Matern_GPR']:model.fit(x,z)
   else:model.fit(x,z,sample_weight=w*len(train))
   p=np.exp(model.predict(xt)*scale+center)
  assert np.isfinite(p).all()and(p>0).all()
  event.update(status='complete',encoder=encoder.schema,target_center=center,target_scale=scale,warnings=[str(a.message)for a in caught]);log_event(event);return p
 except Exception as e:
  event.update(status='failed',error=repr(e));FAILURES.append(event);log_event(event);return None

def add_predictions(route,model,train,test,p,**extra):
 if p is None:return
 for r,pred in zip(test,p):
  PREDS.append(dict(route=route,model=model,row_id=r['row_id'],source_family=r['source_family'],material_key=r.get('material_key'),curve_id=r.get('curve_id'),sample_name=r.get('sample_name'),observed=float(r['target']),predicted=float(pred),is_author_reported=r.get('is_author_reported',True),current_A_g=r['features'].get('reported_current_A_g'),calibration_row_ids=r.get('calibration_row_ids',[]),calibration_current_A_g=r.get('calibration_current_A_g',[]),reference_capacitance=r.get('reference_capacitance'),**extra))

def source_cv(route,rows,models,local=False):
 if local:
  grouped=collections.defaultdict(list)
  for r in rows:grouped[r['source_family']].append(r)
  splits=[]
  for source,a in sorted(grouped.items()):
   mats=sorted({r['material_key']for r in a})
   if len(mats)<5:continue
   for m in mats:splits.append((m,[r for r in a if r['material_key']!=m],[r for r in a if r['material_key']==m]))
 else:
  sources=sorted({r['source_family']for r in rows});splits=[(g,[r for r in rows if r['source_family']!=g],[r for r in rows if r['source_family']==g])for g in sources]
 for unit,train,test in splits:
  for kind in models:add_predictions(route,kind,train,test,fit_predict(kind,train,test,route,unit,local))
  baseline=float(np.average([r['target']for r in train],weights=weights(train)))
  add_predictions(route,'training_mean',train,test,[baseline]*len(test))

def normalize_curve(curve,anchor_count=1):
 rs=curve['rows'];anchor=rs[0];j0=anchor['features']['reported_current_A_g'];c0=anchor['target'];out=[]
 for r in rs[anchor_count:]:
  f={k:r['features'].get(k)for k in MATERIAL_FIELDS};f.update(log_current_ratio=math.log(r['features']['reported_current_A_g']/j0),calibration_C_low_F_g=c0)
  out.append(dict(r,features=f,target=r['target']/c0,absolute_target=r['target'],curve_id=curve['curve_id'],reference_capacitance=c0,calibration_row_ids=[anchor['row_id']],calibration_current_A_g=[j0]))
 return out

def one_anchor(curves):
 normalized=[r for c in curves for r in normalize_curve(c)]
 for source in sorted({r['source_family']for r in normalized}):
  train=[r for r in normalized if r['source_family']!=source];test=[r for r in normalized if r['source_family']==source]
  for kind in ['ridge','random_forest','xgboost']:
   p=fit_predict(kind,train,test,'B_one_anchor',source)
   absolute=[dict(r,target=r['absolute_target'],features=dict(r['features'],reported_current_A_g=next(x['features']['reported_current_A_g']for c in curves if c['curve_id']==r['curve_id']for x in c['rows']if x['row_id']==r['row_id'])))for r in test]
   add_predictions('B_one_anchor',kind,train,absolute,None if p is None else[pred*r['reference_capacitance']for pred,r in zip(p,test)])
  absolute=[dict(r,target=r['absolute_target'])for r in test];add_predictions('B_one_anchor','constant_low_anchor',train,absolute,[r['reference_capacitance']for r in test])

def calibrate(kind,anchor,test):
 j=np.array([r['features']['reported_current_A_g']for r in anchor]);c=np.array([r['target']for r in anchor]);jt=np.array([r['features']['reported_current_A_g']for r in test]);x=np.log(j);xt=np.log(jt)
 if kind=='linear_logcurrent':return np.interp(xt,x,c)
 if kind=='pchip_logcurrent':return PchipInterpolator(x,c)(xt)
 if kind=='powerlaw':return np.exp(np.polyval(np.polyfit(x,np.log(c),1),xt))
 if kind=='nonnegative_inverse_sqrt':
  ab,_=nnls(np.column_stack([np.ones(len(j)),1/np.sqrt(j)]),c);return np.column_stack([np.ones(len(jt)),1/np.sqrt(jt)])@ab
 if kind=='positive_saturating':
  def fun(p,jj):return p[0]/(1+(jj/p[1])**p[2])
  fitted=least_squares(lambda p:(fun(p,j)-c)/max(c),[float(max(c))*1.1,float(np.median(j)),.5],bounds=([1e-8,1e-6,.01],[float(max(c))*100,1e6,5]),max_nfev=1500)
  if not fitted.success:raise ValueError('Calibration optimizer did not converge')
  return fun(fitted.x,jt)
 raise ValueError(kind)

def three_anchors(curves,extrapolate):
 route='D_low_current_extrapolation'if extrapolate else'C_three_anchor_interpolation'
 models=['powerlaw','nonnegative_inverse_sqrt','positive_saturating']if extrapolate else['linear_logcurrent','pchip_logcurrent','nonnegative_inverse_sqrt']
 for curve in curves:
  rows=curve['rows'];n=len(rows);indices=[0,1,2]if extrapolate else[0,(n-1)//2,n-1];anchors=[rows[i]for i in indices];test=[dict(r,curve_id=curve['curve_id'],reference_capacitance=anchors[0]['target'],calibration_row_ids=[r['row_id']for r in anchors],calibration_current_A_g=[r['features']['reported_current_A_g']for r in anchors])for i,r in enumerate(rows)if i not in indices]
  for kind in models:
   event=dict(route=route,model=kind,held_unit=curve['curve_id'],train_sources=[],test_sources=[curve['source_family']],train_row_ids=[],test_row_ids=[r['row_id']for r in test],calibration_row_ids=[r['row_id']for r in anchors],anchor_indices=indices)
   assert not(set(event['calibration_row_ids'])&set(event['test_row_ids']))
   try:
    p=calibrate(kind,anchors,test);assert np.isfinite(p).all()and(p>0).all();event['status']='complete';log_event(event);add_predictions(route,kind,anchors,test,p)
   except Exception as e:event.update(status='failed',error=repr(e));FAILURES.append(event);log_event(event)
  add_predictions(route,'constant_low_anchor',anchors,test,[anchors[0]['target']]*len(test))

def metrics(a,bootstrap=False):
 y=np.array([r['observed']for r in a]);p=np.array([r['predicted']for r in a]);w=weights(a);err=abs(y-p);ape=err/y*100;mu=np.average(y,weights=w);var=np.average((y-mu)**2,weights=w);mse=np.average(err**2,weights=w)
 def wquantile(values,q):
  order=np.argsort(values);return float(values[order][min(len(order)-1,np.searchsorted(np.cumsum(w[order]),q*w.sum()))])
 out=dict(rows=len(a),sources=len({r['source_family']for r in a}),materials=len({r['material_key']for r in a}),curves=len({r['curve_id']for r in a if r['curve_id']}),mae=float(np.average(err,weights=w)),rmse=float(np.sqrt(mse)),r2=float(1-mse/var)if var>0 else None,mape_pct=float(np.average(ape,weights=w)),p90_ape_pct=wquantile(ape,.9),p90_absolute_error=wquantile(err,.9),target_weighted_sd=float(np.sqrt(var)),row_equal_r2=float(1-np.mean(err**2)/np.var(y))if np.var(y)>0 else None)
 source_stats=[]
 for source in sorted({r['source_family']for r in a}):
  mask=np.array([r['source_family']==source for r in a]);ww=w[mask]/w[mask].sum();source_stats.append(dict(source=source,rows=int(mask.sum()),mae=float(np.average(err[mask],weights=ww)),mape_pct=float(np.average(ape[mask],weights=ww))))
 out['per_source']=source_stats;out['source_p90_mape_pct']=float(np.quantile([r['mape_pct']for r in source_stats],.9));out['source_p90_mae']=float(np.quantile([r['mae']for r in source_stats],.9))
 if any(r.get('reference_capacitance')for r in a):
  ref=np.array([r['reference_capacitance']for r in a]);yn=y/ref;pn=p/ref;vv=np.average((yn-np.average(yn,weights=w))**2,weights=w);out['normalized_curve_r2']=float(1-np.average((yn-pn)**2,weights=w)/vv)if vv>0 else None;out['normalized_curve_mae']=float(np.average(abs(yn-pn),weights=w))
 if bootstrap:
  gs=sorted({r['source_family']for r in a});idx={g:np.array([r['source_family']==g for r in a])for g in gs};rng=np.random.default_rng(SEED);samples=[]
  for _ in range(2000):
   counts=collections.Counter(rng.choice(gs,len(gs),replace=True));wb=w*np.array([counts.get(r['source_family'],0)for r in a]);wb/=wb.sum();vm=np.average((y-np.average(y,weights=wb))**2,weights=wb)
   if vm>0:samples.append([np.average(err,weights=wb),1-np.average(err**2,weights=wb)/vm,np.average(ape,weights=wb)])
  ci=np.quantile(np.array(samples),[.025,.975],axis=0);out['source_bootstrap_95pct']=dict(mae=ci[:,0].tolist(),r2=ci[:,1].tolist(),mape_pct=ci[:,2].tolist(),descriptive_reused_sources=True)
 return out

def main():
 global PLANNED
 assert not(RUN/'fit_events.jsonl').exists()and not(RUN/'results.json').exists(),'Never repeat a completed/started pass to chase scores'
 plan=read(RUN/'training_plan.json');data=read(RUN/'input_snapshot.json');assert sha(RUN/'input_snapshot.json')==plan['input_sha256']
 for p,h in read(RUN/'source_protection.json').items():assert sha(ROOT/p)==h,p
 cap=data['capacity'];curves=data['curves'];bet=[r for r in data['BET']if sum(v is not None for v in r['features'].values())>=3]
 scopes={'A_KOH6':[r for r in cap if r['features'].get('electrolyte')=='KOH'and r['features'].get('concentration_mol_L')==6], 'A_H2SO4_1':[r for r in cap if r['features'].get('electrolyte')=='H2SO4'and r['features'].get('concentration_mol_L')==1]}
 eligible={k:v for k,v in scopes.items()if len(v)>=25 and len({r['source_family']for r in v})>=5}
 ret=[]
 ret_fields=['cycle_count','reported_current_A_g','electrolyte','concentration_mol_L','cycle_voltage_lower_V','cycle_voltage_upper_V','BET_m2_g','total_pore_volume_cm3_g','activation_temperature_C','activation_duration_h','precursor_origin_class']
 for r in data['retention']:
  if r['features'].get('electrolyte')=='KOH'and r['features'].get('concentration_mol_L')==6:ret.append(dict(r,features={k:r['features'].get(k)for k in ret_fields}))
 local_sources=collections.Counter(r['source_family']for r in bet);local_rows=sum(n for n in local_sources.values()if n>=5)
 PLANNED=sum(len({r['source_family']for r in a})*5 for a in eligible.values())+len({r['source_family']for r in curves})*3+len(curves)*6+len({r['source_family']for r in bet})*3+local_rows*3+len({r['source_family']for r in ret})*3
 assert PLANNED<=1200,PLANNED
 spec=dict(frozen_at=now(),runner_sha256=sha(Path(__file__)),plan_sha256=sha(RUN/'training_plan.json'),planned_fits=PLANNED,bet_rows=len(bet),bet_sources=len(local_sources),bet_local_rows=local_rows,bet_criteria=dict(r2_gt=.95,mae_max_m2_g=100.,rmse_max_m2_g=150.,mape_max_pct=5.,p90_ape_max_pct=10.,source_p90_mape_max_pct=10.),retention_additional_criteria=dict(p90_absolute_error_max_pp=2.,source_p90_mae_max_pp=2.),baseline_improvement_min_fraction=.2,all_thresholds_are_project_engineering_goals=True,mlp_and_gp_training_weights='MLP/GPR library fit has no sample weights here; source-balanced evaluation still enforced',predefined_sensitivity='Author-only curves are evaluated from the same predictions, no new fits and no outcome-based subset selection; no retrospective replacement of primary',weights='Equal source, then material or curve, then row; no sample identity predictor')
 write(RUN/'pre_fit_specification.json',spec);print(json.dumps(dict(planned_fits=PLANNED,bet_eligible=len(bet),bet_local_rows=local_rows),ensure_ascii=False),flush=True)
 for route,a in eligible.items():source_cv(route,a,plan['model_candidates'])
 one_anchor(curves);three_anchors(curves,False);three_anchors(curves,True)
 source_cv('E_BET_unseen_source',bet,['ridge','random_forest','xgboost']);source_cv('E_BET_known_family_new_material',bet,['ridge','random_forest','xgboost'],True)
 source_cv('F_retention_KOH6',ret,['ridge','random_forest','xgboost'])
 assert len(EVENTS)==PLANNED,(len(EVENTS),PLANNED)
 write(RUN/'heldout_predictions.json',PREDS);summaries=[]
 groups=collections.defaultdict(list)
 for r in PREDS:groups[(r['route'],r['model'])].append(r)
 for (route,model),a in sorted(groups.items()):
  s=metrics(a,True);s.update(route=route,model=model)
  baseline='constant_low_anchor'if route.startswith(('B','C','D'))else'training_mean';b=groups.get((route,baseline));bm=metrics(b)if b else None
  s['baseline']=baseline;s['mae_reduction_vs_baseline']=1-s['mae']/bm['mae']if bm and bm['mae']>0 else None
  if route.startswith('F'):
   checks=dict(r2=s['r2']is not None and s['r2']>.95,mae=s['mae']<=1,rmse=s['rmse']<=1.5,p90_abs=s['p90_absolute_error']<=2,source_tail=s['source_p90_mae']<=2)
  else:
   checks=dict(r2=s['r2']is not None and s['r2']>.95,mae=s['mae']<=(100 if route.startswith('E')else 10),rmse=s['rmse']<=(150 if route.startswith('E')else 15),mape=s['mape_pct']<=5,p90_ape=s['p90_ape_pct']<=10,source_tail=s['source_p90_mape_pct']<=10)
  checks['baseline_improvement']=s['mae_reduction_vs_baseline']is not None and s['mae_reduction_vs_baseline']>=.2
  s['screening_checks']=checks;s['all_numeric_screening_gates_pass']=all(checks.values());s['prospective_generalization_confirmed']=False
  if route.startswith(('B','C','D')):
   authorids={c['curve_id']for c in curves if c['author_only']};aa=[r for r in a if r['curve_id']in authorids];s['author_only_sensitivity']=metrics(aa,True)if aa else None
  summaries.append(s)
 write(RUN/'results.json',dict(status='complete',completed_at=now(),planned_fits=PLANNED,actual_fits=len(EVENTS),failed_fits=len(FAILURES),warnings=sum(bool(r.get('warnings'))for r in EVENTS),elapsed_seconds=round(time.monotonic()-START,3),metrics=summaries,failures=FAILURES,reliable_for_design=False,no_untouched_prospective_test=True))
 write(RUN/'progress.json',dict(status='complete',completed_fits=len(EVENTS),planned_fits=PLANNED,elapsed_seconds=round(time.monotonic()-START,3)))
 print(json.dumps([dict(route=s['route'],model=s['model'],r2=s['r2'],mae=s['mae'],rmse=s['rmse'],mape=s['mape_pct'],pass_numeric=s['all_numeric_screening_gates_pass'])for s in summaries if s['model']not in ['training_mean','constant_low_anchor']],ensure_ascii=False,indent=2),flush=True)
if __name__=='__main__':main()
