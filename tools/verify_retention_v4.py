"""Recompute stability rules and nonlinear-study nested arithmetic without refitting."""
from pathlib import Path
import collections,gzip,hashlib,json,math,sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import tools.verify_retention_v3b as a
from tools.retention_nonlinear_v4 import view
BASE=ROOT/'保持率达标研究_v3_主线与近优组合_20261030';OLD=BASE/'第三轮_扩充来源验证';ST=BASE/'第四轮_选模稳定性复核';NEW=BASE/'第六轮_非线性延拓与稳健学习'
def read(p):return json.loads(Path(p).read_text('utf8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def archive(folder):
 out={}
 with gzip.open(folder/'fit_predictions.jsonl.gz','rt',encoding='utf8')as f:
  for line in f:
   q=json.loads(line);k=(q['route'],q['outer_source'],q['config_id'],q['role'],q['inner_fold']);a.check(k not in out);out[k]=q
 return out
def inner_stats(arc,route,outer,cid):
 rows=[p for k in range(4)for p in arc[(route,outer,cid,'inner',k)]['predictions']];m=a.score(rows);source_mae=[]
 for source in sorted({p['source_family']for p in rows}):
  pp=[p for p in rows if p['source_family']==source];w=a.wts(pp);source_mae.append(float(sum(w*np.array([abs(p['observed']-p['predicted'])for p in pp]))))
 return m,float(np.std(source_mae,ddof=1)/math.sqrt(len(source_mae))),rows
def verify_metrics(folder):
 pred=read(folder/'heldout_predictions.json');group=collections.defaultdict(list)
 for p in pred:group[(p['route'],p['model'])].append(p)
 data=read(OLD/'input_snapshot.json')
 for m in read(folder/'results.json')['metrics']:
  pp=group[(m['route'],m['model'])];s=a.score(pp);a.check(len(pp)==len(data[m['route']]));a.check(len(pp)==len({p['row_id']for p in pp}))
  for k,v in s.items():a.close(m[k],v)
  for b in['training_mean','early_persistence','early_linear']:a.close(m['mae_reduction_vs_'+b],1-s['mae']/a.score(group[(m['route'],b)])['mae'])
  expected=dict(r2=s['r2']>.95,mae=s['mae']<=2,rmse=s['rmse']<=3,mape=s['mape_pct']<=5,p90_ape=s['p90_ape_pct']<=10,p90_abs=s['p90_absolute_error']<=5,source_tail=s['source_p90_mae']<=5,coverage=len(pp)==len(data[m['route']]),positive=all(p['predicted']>0 for p in pp))
  for b in['training_mean','early_persistence','early_linear']:expected['beat_'+b]=(1-s['mae']/a.score(group[(m['route'],b)])['mae'])>=.2
  a.check(m['checks']==expected);a.check(m['numeric_pass']==all(expected.values()));a.check(not m['reliable_model_accepted'])
 return {(p['route'],p['model'],p['row_id']):p for p in pred}
def main():
 oldarc=archive(OLD);a.check(len(oldarc)==3440);stplan=read(ST/'analysis_plan.json')
 for p,h in stplan['protected'].items():a.check(sha(ROOT/p)==h,p)
 a.check(sha(ROOT/'tools/retention_stability_v4.py')==stplan['runner_sha256']);stpred=verify_metrics(ST);oldsel={(s['route'],s['outer_source']):s for s in read(OLD/'nested_selection.json')};data=read(OLD/'input_snapshot.json');controls=read(OLD/'candidate_configurations.json')
 for s in read(ST/'rule_selection.json'):
  route=s['route'];outer=s['outer_source'];old=oldsel[(route,outer)];win=old['overall_selected'];m,se,pp=inner_stats(oldarc,route,outer,win['config_id']);a.close(s['inner_source_mae_standard_error'],se);a.close(s['minimum_inner_mae'],m['mae']);fam=old['family_selected'];eligible=[f for f in stplan['simplicity_order']if fam[f]['mae']<=m['mae']+se+1e-12];a.check(eligible==s['eligible_oneSE_families']);a.check(s['simplest_selected']==eligible[0]);families=sorted(fam);scores=np.array([fam[f]['mae']for f in families])
  soft={T:np.exp(-(scores-min(scores))/T)for T in[1,2]};soft={T:z/sum(z)for T,z in soft.items()};inv=1/(scores+.25);inv/=sum(inv)
  for key,z in [('soft_T1_weights',soft[1]),('soft_T2_weights',soft[2]),('inverse_weights',inv)]:a.check(np.allclose(s[key],z,rtol=0,atol=1e-12))
  for r in data[route]:
   if r['source_family']!=outer:continue
   rid=r['row_id']
   def fp(cid):return next(p['predicted']for p in oldarc[(route,outer,cid,'outer',None)]['predictions']if p['row_id']==rid)
   pv={f:fp(fam[f]['config_id'])for f in fam};v=np.array([pv[f]for f in families]);expected=dict(prior_nested_selected=fp(win['config_id']),family8_equal=v.mean(),candidate16_equal=np.mean([fp(c['id'])for c in controls]),oneSE_family_mean=np.mean([pv[f]for f in eligible]),oneSE_simplest=pv[eligible[0]],near4_median=np.median([pv[f]for f in stplan['near_families']]),soft_family_T1=v@soft[1],soft_family_T2=v@soft[2],inverse_family_MAE=v@inv)
   for k,z in expected.items():a.close(stpred[(route,k,rid)]['predicted'],float(z))
 stability_checks=a.CHECKS
 plan=read(NEW/'training_plan.json');a.check(sha(ROOT/'tools/retention_nonlinear_v4.py')==plan['runner_sha256']);a.check(sha(NEW/'input_snapshot.json')==plan['input_sha256']);a.check(sha(NEW/'candidate_configurations.json')==plan['candidate_sha256']);a.check((NEW/'input_snapshot.json').read_bytes()==(OLD/'input_snapshot.json').read_bytes())
 protected=read(NEW/'source_protection.json')
 for p,h in protected.items():a.check(sha(ROOT/p)==h,p)
 cfg=read(NEW/'candidate_configurations.json');newcfg={c['id']:c for c in cfg['new']};events=[json.loads(v)for v in(NEW/'fit_events.jsonl').read_text('utf8').splitlines()];newarc=archive(NEW);a.check(len(events)==len(newarc)==2580);arc={**oldarc,**newarc};a.check(len(arc)==6020);rows={k:{r['row_id']:r for r in pp}for k,pp in data.items()};splits={(route,s['outer_source']):s for route,ss in plan['splits'].items()for s in ss}
 for e in events:
  route=e['route'];outer=e['outer_source'];k=(route,outer,e['config_id'],e['role'],e['inner_fold']);q=newarc[k];a.check(q['fit_index']==e['fit_index']);a.check(e['status']=='complete');exclude={outer}
  if e['role']=='inner':exclude.update(splits[(route,outer)]['inner_held_sources'][e['inner_fold']]);held=set(splits[(route,outer)]['inner_held_sources'][e['inner_fold']])
  else:held={outer}
  tr=[r for r in data[route]if r['source_family']not in exclude];te=[r for r in data[route]if r['source_family']in held];a.check(e['train_row_ids']==[r['row_id']for r in tr]);a.check(e['test_row_ids']==[r['row_id']for r in te]);a.check(not set(e['train_sources'])&set(e['test_sources']));a.check(outer not in e['train_sources']);a.check([p['row_id']for p in q['predictions']]==e['test_row_ids']);a.check(all(p['observed']==rows[route][p['row_id']]['target']for p in q['predictions']))
  w=a.wts(tr);y=np.array([r['target']-r['last_early']for r in tr]);mu=float(sum(w*y));sc=float(np.sqrt(sum(w*(y-mu)**2)))or 1.;a.close(e['target_center'],mu);a.close(e['target_scale'],sc)
  for r in tr+te:
   f=r['features'];N=f['target_cycle_count'];obs=f['early_observed_cycle_count'];h=N/obs;power=newcfg[e['config_id']]['power'];mult=h**power-1;level=f['last_early_retention_pct']-100;drift=f['early_retention_slope_per_1000_cycles']*obs/1000;gap=f['early_mean_retention_pct']-f['last_early_retention_pct'];expected=dict(early_level_change_pp=level,mean_minus_last_pp=gap,early_range_pp=f['early_retention_range_pp'],early_local_drift_pp=drift,observed_fraction=obs/N,target_cycle_count=N,horizon_log=math.log(h),positive_level_extension_pp=max(0,level)*mult,negative_level_extension_pp=min(0,level)*mult,positive_drift_extension_pp=max(0,drift)*mult,negative_drift_extension_pp=min(0,drift)*mult,mean_gap_extension_pp=gap*mult);actual=view(r,newcfg[e['config_id']])['features'];a.check(set(actual)==set(expected))
   for field,z in expected.items():a.close(actual[field],z)
 pred=verify_metrics(NEW)
 for s in read(NEW/'nested_selection.json'):
  route=s['route'];outer=s['outer_source'];stats={}
  for c in cfg['reused_controls']+cfg['new']:
   m,se,pp=inner_stats(arc,route,outer,c['id']);stats[c['id']]=(m,se);old=next(v for v in s['inner_scores']if v['config_id']==c['id']);a.close(old['mae'],m['mae']);a.close(old['rmse'],m['rmse'])
  win=s['overall_selected'];a.check(stats[win['config_id']][0]['mae']<=min(v[0]['mae']for v in stats.values())+1e-10);a.close(s['oneSE'],stats[win['config_id']][1]);fam=s['family_selected'];eligible=[f for f in sorted(fam)if stats[fam[f]['config_id']][0]['mae']<=win['mae']+s['oneSE']+1e-12];a.check(eligible==s['oneSE_eligible_families'])
  for f,v in fam.items():a.check(stats[v['config_id']][0]['mae']<=min(stats[c['id']][0]['mae']for c in cfg['reused_controls']+cfg['new']if c['family']==f)+1e-10)
  for r in data[route]:
   if r['source_family']!=outer:continue
   rid=r['row_id']
   def fp(cid):return next(p['predicted']for p in arc[(route,outer,cid,'outer',None)]['predictions']if p['row_id']==rid)
   for method,families in [('oneSE_family_mean',eligible),('family_all_equal',sorted(fam)),('near4_equal',['RF_early','GPR_early','XGB_early','RF_static'])]:a.close(pred[(route,method,rid)]['predicted'],float(np.mean([fp(fam[f]['config_id'])for f in families])))
   a.close(pred[(route,'nested_selected',rid)]['predicted'],fp(win['config_id']))
   for f,v in fam.items():a.close(pred[(route,'nested_family::'+f,rid)]['predicted'],fp(v['config_id']))
   for c in cfg['reused_controls']:a.close(pred[(route,'fixed::'+c['id'],rid)]['predicted'],fp(c['id']))
 warnings_count=sum(bool(e.get('warnings'))for e in events);types=collections.Counter(w for e in events for w in e.get('warnings',[]));audit=dict(status='passed',checks=a.CHECKS,stability_checks=stability_checks,new_estimator_fits=2580,reused_fits=3440,source_hashes=len(protected),fit_warnings_count=warnings_count,warning_types=dict(types),old_author_labels_unchanged=True,no_new_input_measurements=True,all_inner_scores_recomputed=True,source_split_and_original_predictions_checked=True,goal_status='active',limits='No refit in audit. Reused development sources remain exploratory; no source candidate from phase5/shape proposal from phase7 enters these models. Digitization bounds do not prove physical truth.')
 (NEW/'independent_verification.json').write_bytes((json.dumps(audit,ensure_ascii=False,indent=2)+'\n').encode('utf8'));(ST/'independent_verification.json').write_bytes((json.dumps(dict(status='passed',checks=stability_checks,model_refits=0,rule_outputs_recomputed=True,original_primary_reproduced=True,new_external_sources=0),ensure_ascii=False,indent=2)+'\n').encode('utf8'));print(json.dumps({k:v for k,v in audit.items()if k!='warning_types'},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
