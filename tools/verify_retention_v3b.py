"""Independently recompute expanded-store windows, nested scores and predictions."""
from pathlib import Path
import collections,gzip,hashlib,json,math,sqlite3,sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'保持率达标研究_v3_主线与近优组合_20261030';RUN=BASE/'第三轮_扩充来源验证';P=BASE/'第二轮_证据与曲线扩充'
def read(p):return json.loads(Path(p).read_text('utf8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
CHECKS=0
def check(x,why=''):
 global CHECKS
 assert bool(x),why;CHECKS+=1
def close(a,b):check(abs(a-b)<=1e-8*max(1,abs(a),abs(b)),(a,b))
def wts(rows):
 groups=collections.defaultdict(lambda:collections.Counter())
 for r in rows:groups[r['source_family']][r['curve_id']]+=1
 return np.array([1/(len(groups)*len(groups[r['source_family']])*groups[r['source_family']][r['curve_id']])for r in rows])
def score(rows):
 w=wts(rows);y=np.array([r['observed']for r in rows]);p=np.array([r['predicted']for r in rows]);e=np.abs(y-p);ape=e/y*100;mu=np.sum(w*y);var=np.sum(w*(y-mu)**2);mse=np.sum(w*e**2)
 def q(v,p):
  order=np.argsort(v);return float(v[order][min(len(v)-1,np.searchsorted(np.cumsum(w[order]),p*sum(w)))])
 sources=sorted({r['source_family']for r in rows});sm=[]
 for s in sources:
  ix=np.array([r['source_family']==s for r in rows]);sm.append(float(np.sum(w[ix]*e[ix])/sum(w[ix])))
 return dict(mae=float(sum(w*e)),rmse=float(np.sqrt(mse)),r2=float(1-mse/var),mape_pct=float(sum(w*ape)),p90_ape_pct=q(ape,.9),p90_absolute_error=q(e,.9),source_p90_mae=float(np.quantile(sm,.9)))
def main():
 plan=read(RUN/'training_plan.json');data=read(RUN/'input_snapshot.json');cfg={c['id']:c for c in read(RUN/'candidate_configurations.json')};curves={c['curve_id']:c for c in read(P/'curve_dataset_v3b.json')}
 check(sha(ROOT/'tools/run_retention_v3b.py')==plan['runner_sha256']);check(sha(RUN/'input_snapshot.json')==plan['input_sha256']);check(sha(RUN/'candidate_configurations.json')==plan['candidate_sha256'])
 protected=read(RUN/'source_protection.json')
 for p,h in protected.items():check(sha(ROOT/p)==h,p)
 for item in read(P/'existing_pdf_queue.json')['items']:
  for s in item['sources']:
   if s['available']:check(sha(ROOT/s['path'])==s['sha256'],s['path'])
 db=sqlite3.connect((P/'cycling_research_v3b.sqlite').as_uri()+'?mode=ro',uri=True);check(db.execute('PRAGMA integrity_check').fetchone()[0]=='ok');check(not db.execute('PRAGMA foreign_key_check').fetchall());check(sha(P/'cycling_research_v3b.sqlite')==plan['sqlite_sha256']);db.close()
 original={r['row_id']:r for r in read(ROOT/'保持率双路线预研_v2_20261029/baseline_inputs.json')['3E']}
 byroute={k:{r['row_id']:r for r in v}for k,v in data.items()}
 for route,rows in data.items():
  check(len(rows)==plan['counts'][route]['rows']);check(len({r['source_family']for r in rows})==plan['counts'][route]['sources'])
  for r in rows:
   q=curves[r['curve_id']];check(q['training_eligible_pending_visual_review']);check(r['target']==original[r['endpoint_id']]['target']);ps=[p for p in q['points']if p['cycle_upper']<=r['fraction']*q['target_cycle_count']];check(len(ps)>=3);check([p['marker_index']for p in ps]==r['point_indices']);check(ps==r['early_points']);x=np.array([p['cycle_coordinate']for p in ps]);y=np.array([p['retention_pct']for p in ps]);slope=float(sum((x-x.mean())*(y-y.mean()))/sum((x-x.mean())**2)*1000)
   expected=dict(last_early_retention_pct=y[-1],early_mean_retention_pct=y.mean(),early_retention_slope_per_1000_cycles=slope,early_retention_range_pp=max(y)-min(y),early_observed_cycle_count=x[-1],target_cycle_count=q['target_cycle_count'])
   for k,v in expected.items():close(r['features'][k],v)
   close(r['linear_forecast'],y[-1]+slope*(q['target_cycle_count']-x[-1])/1000)
   for k,v in r['static_features'].items():check(v==q['features'].get(k),k)
 events=[json.loads(x)for x in(RUN/'fit_events.jsonl').read_text('utf8').splitlines()]
 with gzip.open(RUN/'fit_predictions.jsonl.gz','rt',encoding='utf8')as f:fp=[json.loads(x)for x in f]
 check(len(events)==len(fp)==plan['planned_estimator_fits']);check([e['fit_index']for e in events]==list(range(1,len(events)+1)))
 index=collections.defaultdict(list);outer={};inner={}
 for e,p in zip(events,fp):
  route=e['route'];outer_source=e['outer_source'];rows=byroute[route];check(e['status']=='complete');check(e['fit_index']==p['fit_index']);check(e['role']==p['role']);check(not set(e['train_sources'])&set(e['test_sources']));check(outer_source not in e['train_sources']);check(set(e['train_sources'])=={rows[r]['source_family']for r in e['train_row_ids']});check(set(e['test_sources'])=={rows[r]['source_family']for r in e['test_row_ids']});check(not{rows[r]['curve_id']for r in e['train_row_ids']}&{rows[r]['curve_id']for r in e['test_row_ids']});check(e['test_row_ids']==[r['row_id']for r in p['predictions']]);check(len(e['test_row_ids'])==len(set(e['test_row_ids'])))
  c=cfg[e['config_id']];tr=[rows[r]for r in e['train_row_ids']];y=np.array([r['target']-r['last_early']if c['target']=='delta'else math.log(r['target']/r['last_early'])for r in tr]);w=wts(tr);mu=float(sum(y*w));sc=float(np.sqrt(sum(w*(y-mu)**2)))or 1.;close(e['target_center'],mu);close(e['target_scale'],sc)
  for r in p['predictions']:check(r['observed']==rows[r['row_id']]['target']);check(math.isfinite(r['predicted']))
  key=(route,outer_source,e['config_id'])
  if e['role']=='inner':
   check(outer_source not in e['test_sources']);inner.setdefault(key,[]).extend(p['predictions'])
  else:
   check(set(e['test_sources'])=={outer_source});check(key not in outer);outer[key]={r['row_id']:r for r in p['predictions']}
 for key,rows in inner.items():
  route,source,cid=key;check({r['row_id']for r in rows}=={r['row_id']for r in data[route]if r['source_family']!=source});check(len(rows)==len({r['row_id']for r in rows}))
 pred=read(RUN/'heldout_predictions.json');predindex={(r['route'],r['model'],r['row_id']):r for r in pred};check(len(predindex)==len(pred))
 near=['RF_early','GPR_early','XGB_early','RF_static'];selections=read(RUN/'nested_selection.json');check(len(selections)==plan['planned_ensemble_fits'])
 for sel in selections:
  route=sel['route'];source=sel['outer_source'];scores=[]
  for cid in cfg:
   m=score(inner[(route,source,cid)]);scores.append(dict(config_id=cid,family=cfg[cid]['family'],mae=m['mae'],rmse=m['rmse']))
  old={s['config_id']:s for s in sel['inner_scores']}
  for s in scores:close(s['mae'],old[s['config_id']]['mae']);close(s['rmse'],old[s['config_id']]['rmse'])
  rank=lambda v:(v['mae'],v['rmse'],v['config_id']);win=min(scores,key=rank);check(win['config_id']==sel['overall_selected']['config_id']);families={f:min([s for s in scores if s['family']==f],key=rank)for f in{c['family']for c in cfg.values()}}
  for f,s in families.items():check(s['config_id']==sel['family_selected'][f]['config_id'])
  z=np.array(sel['ensemble_weights']);close(float(sum(z)),1);check(min(z)>-1e-8)
  tr=[r for r in data[route]if r['source_family']!=source];mean=float(sum(wts(tr)*np.array([r['target']for r in tr])))
  for r in data[route]:
   if r['source_family']!=source:continue
   rid=r['row_id']
   for method,s in dict(nested_selected=win,**{'nested_family::'+f:v for f,v in families.items()}).items():close(predindex[(route,method,rid)]['predicted'],outer[(route,source,s['config_id'])][rid]['predicted'])
   vec=np.array([outer[(route,source,families[f]['config_id'])][rid]['predicted']for f in near]);close(predindex[(route,'near4_equal',rid)]['predicted'],float(vec.mean()));close(predindex[(route,'near4_inner_convex',rid)]['predicted'],float(vec@z));close(predindex[(route,'training_mean',rid)]['predicted'],mean);close(predindex[(route,'early_persistence',rid)]['predicted'],r['last_early']);close(predindex[(route,'early_linear',rid)]['predicted'],r['linear_forecast'])
 for m in read(RUN/'results.json')['metrics']:
  rows=[r for r in pred if r['route']==m['route']and r['model']==m['model']];check(len(rows)==len(data[m['route']]))
  s=score(rows)
  for k,v in s.items():close(m[k],v)
  for b in['training_mean','early_persistence','early_linear']:
   base=score([r for r in pred if r['route']==m['route']and r['model']==b]);close(m['mae_reduction_vs_'+b],1-s['mae']/base['mae'])
  check(m['numeric_pass']==all(m['checks'].values()));check(not m['reliable_model_accepted']);check(not m['untouched_external_test'])
 for p,h in protected.items():check(sha(ROOT/p)==h,p)
 result=dict(status='passed',checks=CHECKS,source_files_protected=len(protected),estimator_fits_checked=len(events),inner_and_outer_prediction_files_saved=True,inner_scores_independently_recomputed=True,outer_metrics_independently_recomputed=True,sqlite_integrity='ok',foreign_keys='ok',author_labels_changed=0,new_external_sources=0,goal_status='active',limits='Audit recomputes derived windows, source isolation, train target scaling, every inner score/selection and outer arithmetic. It does not retrain3440 estimators or claim graph pixels are raw measurements.')
 (RUN/'independent_verification.json').write_bytes((json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode('utf8'));print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
