"""Exact ordinate-reading bound propagation, not probabilistic error bars or refits."""
from pathlib import Path
import argparse,hashlib,json,sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.retention_shape_v4 import OUT,FIELDS,read,write,sha,now
def prepare():
 p=OUT/'shape_precision_plan.json';assert not p.exists()
 write(p,dict(frozen_at=now(),input_sha256=sha(OUT/'input_snapshot.json'),runner_sha256=sha(Path(__file__)),model_fits=0,scope='All current rows; four already approved shape summaries; no new model inputs or row filtering.',method='For each computable row and fixed observed x coordinates, slopes/curvature are linear functions a dot y. Exact independent per-point ordinate-box bound=sum(abs(a_i)*b_i), using original per-point reading_bound_pp. Peak possible indices satisfy upper_i>=max_j lower_j. Bounds are deterministic sensitivity sets, not SD,CI,noise distributions or physical uncertainty truth.',limits='No horizontal-coordinate/calibration uncertainty propagated; no independent error assumption or MonteCarlo. Slope/curvature conditional on unchanged x/half assignment. No claim that perturbation produces a physically realizable full curve.',report='Retain all rows and flag unidentifiable signs without rejecting records. Check extreme ordinate vectors reproduce both analytic extrema. No training or changes to author targets.'))
 print('Precision analysis frozen;0model fits')
def run():
 plan=read(OUT/'shape_precision_plan.json');assert not(OUT/'shape_precision_results.json').exists();assert plan['runner_sha256']==sha(Path(__file__))and plan['input_sha256']==sha(OUT/'input_snapshot.json');data=read(OUT/'input_snapshot.json');rows=[];checks=0
 for route,rr in data.items():
  for r in rr:
   if r['shape_features'][FIELDS[0]]is None:rows.append(dict(route=route,row_id=r['row_id'],source_family=r['source_family'],sample_name=r['sample_name'],computable=False));continue
   ps=r['early_points'];x=np.array([p['cycle_coordinate']for p in ps]);y=np.array([p['retention_pct']for p in ps]);bound=np.array([p['reading_bound_pp']for p in ps]);z=(x-x.min())/(x.max()-x.min());left=z<=.5;right=z>.5;coeff={}
   for key,mask in[(FIELDS[0],left),(FIELDS[1],right)]:
    a=np.zeros(len(z));zz=z[mask]-z[mask].mean();a[mask]=zz/sum(zz**2);coeff[key]=a
   design=np.column_stack([np.ones(len(z)),z,z*z]);coeff[FIELDS[2]]=2*np.linalg.pinv(design)[2];features={}
   for key,a in coeff.items():
    value=float(a@y);radius=float(abs(a)@bound);assert abs(value-r['shape_features'][key])<1e-8;checks+=1;lo=y-np.sign(a)*bound;hi=y+np.sign(a)*bound
    if key==FIELDS[2]:calc=lambda yy:float(2*np.linalg.lstsq(design,yy,rcond=None)[0][2])
    else:
     mask=left if key==FIELDS[0]else right;calc=lambda yy:float(np.linalg.lstsq(np.column_stack([np.ones(mask.sum()),z[mask]]),yy[mask],rcond=None)[0][1])
    assert abs(calc(lo)-(value-radius))<1e-8 and abs(calc(hi)-(value+radius))<1e-8;checks+=2
    features[key]=dict(value=value,reading_box_radius=radius,interval=[value-radius,value+radius],sign_identified=abs(value)>radius,conditional_on_fixed_cycles=True)
   possible=np.flatnonzero(y+bound>=max(y-bound));features[FIELDS[3]]=dict(value=r['shape_features'][FIELDS[3]],possible_marker_indices=[ps[i]['marker_index']for i in possible],conservative_relative_time_interval=[float(min(z[possible])),float(max(z[possible]))],unique_peak_identifiable=len(possible)==1);checks+=1
   rows.append(dict(route=route,row_id=r['row_id'],source_family=r['source_family'],sample_name=r['sample_name'],computable=True,features=features))
 summary={}
 for route in data:
  group=[r for r in rows if r['route']==route and r['computable']];summary[route]=dict(all_rows=len(data[route]),computable=len(group),**{k+'_sign_identified':sum(r['features'][k]['sign_identified']for r in group)for k in FIELDS[:3]},peak_unique=sum(r['features'][FIELDS[3]]['unique_peak_identifiable']for r in group))
 write(OUT/'shape_precision_results.json',dict(status='complete',checks=checks,new_fits=0,summary=summary,rows=rows,method_limits=plan['limits'],scientific_interpretation='Sensitivity to fixed ordinate reading bounds, not proof of error floor or permission to change labels/drop sources.'))
 print(json.dumps(summary,ensure_ascii=False,indent=2));print('Analytic bound/extreme-vector checks',checks)
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','run']);args=parser.parse_args();prepare()if args.action=='prepare'else run()
