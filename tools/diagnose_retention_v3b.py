"""No-fit diagnostics: selection instability, reading bounds and extrapolation support."""
from pathlib import Path
import collections,hashlib,json,math
ROOT=Path(__file__).resolve().parents[1];R=ROOT/'保持率达标研究_v3_主线与近优组合_20261030/第三轮_扩充来源验证'
def read(p):return json.loads(Path(p).read_text('utf8'))
def main():
 data=read(R/'input_snapshot.json');sel=read(R/'nested_selection.json');pred=read(R/'heldout_predictions.json');res=read(R/'results.json');out={}
 for route,rows in data.items():
  p={r['row_id']:r for r in pred if r['route']==route and r['model']=='nested_selected'};a=[]
  for r in rows:
   early=r['early_points'];x=[v['cycle_coordinate']for v in early];xm=sum(x)/len(x);den=sum((v-xm)**2 for v in x);co=[(v-xm)/den*1000 for v in x];lo=sum(c*v['reading_interval_pp'][0 if c>=0 else 1]for c,v in zip(co,early));hi=sum(c*v['reading_interval_pp'][1 if c>=0 else 0]for c,v in zip(co,early));tr=[z for z in rows if z['source_family']!=r['source_family']];N=r['features']['target_cycle_count'];trainN=[z['features']['target_cycle_count']for z in tr]
   a.append(dict(row_id=r['row_id'],sample=r['sample_name'],source_family=r['source_family'],target_cycles=N,observed_retention_pct=r['target'],predicted_retention_pct=p[r['row_id']]['predicted'],absolute_error_pp=abs(r['target']-p[r['row_id']]['predicted']),early_points=len(early),last_early=r['last_early'],mean_early=r['features']['early_mean_retention_pct'],early_range=r['features']['early_retention_range_pp'],slope=r['features']['early_retention_slope_per_1000_cycles'],slope_y_bounds_only=[lo,hi],maximum_reading_bound_pp=r['reading_bound_pp'],target_cycles_outside_other_source_range=N<min(trainN)or N>max(trainN),other_source_cycle_range=[min(trainN),max(trainN)],actual_remaining_change_pp=r['target']-r['last_early']))
  m=next(m for m in res['metrics']if m['route']==route and m['model']=='nested_selected');choices=collections.Counter(s['overall_selected']['family']for s in sel if s['route']==route)
  out[route]=dict(rows=len(rows),sources=len({r['source_family']for r in rows}),primary_r2=m['r2'],primary_mae=m['mae'],primary_rmse=m['rmse'],target_weighted_sd=m['target_weighted_sd'],rmse_needed_for_r2_gt_095=m['target_weighted_sd']*math.sqrt(.05),inner_family_choices=dict(choices),difficult_cases=sorted(a,key=lambda r:-r['absolute_error_pp']),reading_bound_warning='Pixel reading intervals are deterministic digitization bounds, not Gaussian standard deviations or experimental replicate errors. Slope intervals use y bounds only at fixed read x; they are sensitivity descriptions, not calibrated confidence intervals.')
 report=dict(status='diagnostics_complete_no_new_fits',model_fits=0,goal_status='active',input_sha256=hashlib.sha256((R/'input_snapshot.json').read_bytes()).hexdigest(),routes=out,interpretation=[
 'Expanded coverage does not preserve the small8-source highR2. Cohorts changed, so old/new R2 are not a matched causal improvement comparison.',
 'Primary inner selection frequently chooses GPR-static even when other fixed families have lower outer aggregate error; this is selection instability, not authority to replace the primary posthoc.',
 'CCL50k activation growth is poorly represented by near-flat first10k data and lies beyond other-source target-cycle support. Keep actual109.2% and the error; no100% clipping.',
 'OAC short-horizon fast initial loss and later plateau challenge linear continuation. EUAC initial activation peak similarly weakens a single slope summary.',
 'Graph-reading uncertainty can be comparable with the accuracy budget implied by R2>.95. It is not proof of an irreducible error floor; prioritize better original trace evidence and train-only uncertainty treatment.',
 'Next hypotheses: stable/risk-controlled family selection and fixed mixtures; nonlinear activation/degradation continuation within approved inputs; richer same-window shape representation only after checking input-contract boundary; new source validation frozen before revealing external endpoints. Preserve all near branches and A/2E evidence.'
 ])
 (R/'error_diagnostics.json').write_bytes((json.dumps(report,ensure_ascii=False,indent=2)+'\n').encode('utf8'));print(json.dumps({k:{z:v[z]for z in['rows','sources','rmse_needed_for_r2_gt_095','inner_family_choices']}for k,v in out.items()},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
