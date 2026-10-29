"""Inventory and freeze a new, finite feasibility experiment; never rerun old plans."""
from pathlib import Path
import collections, datetime, hashlib, importlib.metadata, json, sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from data.training_latest import open_training_datasets
RUN=ROOT/'小样本方向预研_20261029'
TASKS={'capacity':'capacity:3e_with_graph','reported':'capacity:3e_reported','retention':'cycle:reported_3e','BET':'material:ordinary_biomass_pretest:BET_surface_area_m2_g'}
MATERIAL_FIELDS=['BET_surface_area_m2_g','total_pore_volume_cm3_g','micropore_volume_cm3_g','mesopore_volume_cm3_g','micropore_surface_area_m2_g','XPS_N_at_pct','XPS_O_at_pct','Raman_ID_IG']
CONDITION_FIELDS=['reported_current_A_g','electrolyte','concentration_mol_L','voltage_lower_V','voltage_upper_V','reference_electrode']
def read(p):return json.loads(Path(p).read_text('utf-8-sig'))
def write(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n','utf8')
def sha(p):
 with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def now():return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(timespec='seconds')
def curve_key(r):
 f=r['features'];c=r['conditions']
 return json.dumps([r['source_family'],r['material_key'],*[f.get(k)for k in CONDITION_FIELDS[1:]],c.get('physical_test_group')],ensure_ascii=False)

def main():
 assert not RUN.exists(),'Do not overwrite an existing feasibility run'
 RUN.mkdir();pointer=read(ROOT/'data/current_training_latest.json');data={};protected={}
 def protect(path,expected=None):
  path=Path(path).resolve();assert path==ROOT or ROOT in path.parents
  h=sha(path);assert expected is None or h==expected,str(path)
  protected[path.relative_to(ROOT).as_posix()]=h
 with open_training_datasets()as d:
  raw={k:d.rows(t)for k,t in TASKS.items()};catalog={r['material_key']:r for r in d.material_catalog()}
  for r in d.connection.execute('pragma database_list'):
   if r['file']:protect(r['file'])
  reported={r['row_id']for r in raw['reported']}
  for kind,rows in raw.items():
   if kind=='reported':continue
   data[kind]=[]
   for r in rows:
    fields=MATERIAL_FIELDS+CONDITION_FIELDS if kind=='capacity'else list(r['features'])
    f={k:r['features'].get(k)for k in fields}
    if kind=='BET':f={k:v for k,v in f.items()if k.startswith('process__')}
    rec={k:r.get(k)for k in ['row_id','material_key','sample_name','source_family','target','target_name','conditions']}
    rec.update(features=f,is_author_reported=(r['row_id']in reported)if kind=='capacity'else True,original_report=r.get('original_report'),process_evidence=r.get('process_evidence',[]))
    if kind=='capacity':
     cat=catalog.get(r['material_key'],{});rec['material_stage']=cat.get('material_stage');rec['synthesis']=cat.get('synthesis',[])
    data[kind].append(rec)
    evidences=[r.get('original_report')]+r.get('process_evidence',[])
    for e in evidences:
     if isinstance(e,dict)and e.get('path')and e.get('sha256'):protect(ROOT/e['path'],e['sha256'])
 groups=collections.defaultdict(list)
 for r in data['capacity']:groups[curve_key(r)].append(r)
 curves=[];excluded=[]
 for key,rows in sorted(groups.items()):
  byj=collections.defaultdict(list)
  for r in rows:byj[r['features']['reported_current_A_g']].append(r)
  conflict=[j for j,a in byj.items()if len({r['target']for r in a})>1]
  if conflict:
   excluded.append(dict(key=key,reason='same_protocol_same_current_conflicting_values_no_averaging',currents=conflict,row_ids=[r['row_id']for r in rows]));continue
  rs=[sorted(a,key=lambda r:(not r['is_author_reported'],r['row_id']))[0]for j,a in sorted(byj.items())if j>0]
  if len(rs)<5:
   excluded.append(dict(key=key,reason='fewer_than_five_unique_current_conditions',row_ids=[r['row_id']for r in rows]));continue
  cid='curve:'+hashlib.sha256(key.encode()).hexdigest()[:16]
  curves.append(dict(curve_id=cid,key=key,source_family=rs[0]['source_family'],material_key=rs[0]['material_key'],sample_name=rs[0]['sample_name'],rows=rs,author_only=all(r['is_author_reported']for r in rs)))
 data['curves']=curves;data['curve_exclusions']=excluded
 domains={
 'capacity_all':data['capacity'],
 'capacity_KOH6':[r for r in data['capacity']if r['features'].get('electrolyte')=='KOH'and r['features'].get('concentration_mol_L')==6],
 'capacity_H2SO4_1':[r for r in data['capacity']if r['features'].get('electrolyte')=='H2SO4'and r['features'].get('concentration_mol_L')==1],
 'retention_KOH6':[r for r in data['retention']if r['features'].get('electrolyte')=='KOH'and r['features'].get('concentration_mol_L')==6],
 'BET_process_only':[r for r in data['BET']if any(v is not None for v in r['features'].values())]}
 inv={k:dict(rows=len(a),sources=len({r['source_family']for r in a}),materials=len({r['material_key']or r['row_id']for r in a}))for k,a in domains.items()}
 inv['curves']=dict(curves=len(curves),sources=len({r['source_family']for r in curves}),points=sum(len(r['rows'])for r in curves),author_only_curves=sum(r['author_only']for r in curves),author_only_sources=len({r['source_family']for r in curves if r['author_only']}),excluded_groups=len(excluded))
 write(RUN/'input_snapshot.json',data);write(RUN/'scope_inventory.json',inv);write(RUN/'source_protection.json',protected)
 plan=dict(run_id='small-sample-routes-20261029',frozen_at=now(),authorization='2026-10-29 user explicitly requests new directions, multiple methods and preliminary feasibility training; all basic metrics and generalization must meet declared targets.',input_pointer=pointer,input_sha256=sha(RUN/'input_snapshot.json'),inventory=inv,
  selection_policy='Scopes and curve anchoring chosen by scientific input availability and independent counts, not favorable held-out scores. Existing literature/labels were previously viewed; exploratory feasibility, no untouched prospective validation.',
  criteria=dict(capacity=dict(r2_gt=.95,mae_max_F_g=10.,rmse_max_F_g=15.,mape_max_pct=5.,p90_ape_max_pct=10.,source_p90_mape_max_pct=10.,baseline_mae_improvement_min_fraction=.2),retention=dict(r2_gt=.95,mae_max_percentage_points=1.,rmse_max_percentage_points=1.5),generalization='Whole source-family holdout; calibrated routes permit only predeclared target-curve anchors. Source bootstrap 2000 intervals; report source-wise and curve-normalized diagnostics. Truly prospective new-source validation remains required for final reliability, not claimed by this experiment.'),
  threshold_basis='Engineering goals, not a universal standard. Biomass-carbon J Energy Storage S2352152X2402560X reports R2 .951, MAE11.090, RMSE14.756; target MAE10/RMSE15 deliberately demanding, plus relative errors and source validation. Retention1/1.5pp is a provisional design goal rather than a published universal cutoff.',
  model_candidates=['ridge','random_forest','xgboost','small_BP_MLP','fixed_Matern_GPR'],
  model_parameters=dict(ridge_alpha=1.,forest_trees=160,forest_max_depth=6,forest_leaf=2,xgb_trees=160,xgb_depth=2,xgb_learning_rate=.04,mlp_hidden=[16],mlp_alpha=1.,mlp_solver='lbfgs',mlp_max_iter=1500,gpr_optimizer=None,gpr_Matern_nu=1.5,gpr_length_scale=2.,gpr_alpha=.04,seed=20261029),
  routes=[
   dict(id='A',name='限定工况的零实测比电容预测',domains=['capacity_KOH6','capacity_H2SO4_1'],primary='random_forest',validation='Leave one entire source family out; no target-source capacitance or sample identity input. Fit only training-fold encoding and imputation.'),
   dict(id='B',name='一个低倍率实测点+跨来源归一化迁移',primary='random_forest',models=['ridge','random_forest','xgboost'],validation='Leave source out; other sources train C/C_low from log(j/j_low), C_low and static material features. The new material has exactly its minimum-current capacitance anchor; test all other currents.'),
   dict(id='C',name='三个预定倍率实测点补全中间倍率',primary='pchip_logcurrent',models=['linear_logcurrent','pchip_logcurrent','nonnegative_inverse_sqrt'],validation='Per curve anchor indices 0,(n-1)//2,n-1, determined only by sorted currents. Test remaining currents, never score anchors. Independent new curves may be calibrated with those three measurements. All normalized-curve and author-only sensitivities retained.'),
   dict(id='D',name='三个低电流点外推高电流',primary='nonnegative_inverse_sqrt',models=['powerlaw','nonnegative_inverse_sqrt','positive_saturating'],validation='Per curve anchor first three currents; predict all higher currents. All eligible curves kept, no selection on errors.'),
   dict(id='E',name='只用制备参数预测BET或同家族插值',primary='random_forest',models=['ridge','random_forest','xgboost'],validation='BET process-only >=3 nonmissing process fields. Both leave-source-out and leave-material-out within sources with>=5 materials; latter assumes known family/protocol and is not unseen-source generalization.'),
   dict(id='F',name='保留循环任务但限制6M KOH',primary='random_forest',models=['ridge','random_forest','xgboost'],validation='New narrowed task leave source out; keep difficult records and true >100 labels, no inherited old training plan rerun.')],
  eligibility=dict(zero_shot_min_sources=5,zero_shot_min_rows=25,curves_min_points=5,bet_min_fields=3,bet_within_source_min_materials=5),
  stop='One frozen pass of named scopes/models; no hyperparameter search, no stacking selected on outer outcomes, no added scopes after seeing scores. Maximum1200 estimator/calibration fits; invalid runs stop, failures preserved. No global packages or pretrained weights installed/downloaded, LightGBM and TabPFN noted as untested resource options.',new_data_admission=False,new_service=False)
 write(RUN/'training_plan.json',plan);write(RUN/'goal.json',dict(status='active',objective='Design multiple feasible small-sample prediction directions and validate them before reporting; R2>.95 plus error/generalization gates, no fabricated success.',plan_sha256=sha(RUN/'training_plan.json')))
 write(RUN/'environment.json',{p:importlib.metadata.version(p)for p in ['numpy','scipy','scikit-learn','xgboost']})
 print(json.dumps(dict(run=str(RUN),inventory=inv,plan_sha256=sha(RUN/'training_plan.json'),protected_files=len(protected)),ensure_ascii=False,indent=2))
if __name__=='__main__':main()
