"""Read-only auxiliary input preflight, CSV exports and source-leakage checks; no fit."""
from pathlib import Path
from collections import Counter
import csv,hashlib,io,json,math,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from data.literature_v3 import open_literature_database
from data.cycling_db import open_database
OUT=ROOT/'文献全量利用复核_20261025/批次03_多样品与工况';DB=OUT/'literature_material_pool_v3.sqlite'
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def norm(s):return s.lower().removeprefix('doi:').strip()
def main():
 digest=sha(DB);checks=[]
 def check(name,ok):
  if not ok:raise AssertionError(name)
  checks.append(name)
 with open_literature_database(DB,digest) as db,open_database() as cycling:
  profiles={profile:db.auxiliary_feature_rows(profile) for profile in ['3e','2e_device']}
  all_eligible=[r for rows in profiles.values() for r in rows]
  main_rows=cycling.fetch('reported_3e').rows
  check('core_cycling_unchanged',len(main_rows)==43 and len({r['source_group'] for r in main_rows})==31)
  check('profiles_are_separate_targets',{r['target_name'] for r in profiles['3e']}=={'reported_3e_capacitance_F_g'} and {r['target_name'] for r in profiles['2e_device']}=={'reported_2e_device_capacitance_F_g'})
  check('expected_20_5_rows',len(profiles['3e'])==20 and len(profiles['2e_device'])==5)
  check('three_DOI_groups',len({norm(r['source_group']) for r in all_eligible})==3)
  check('no_new_sources_recounted_as_core_members',not {norm(r['source_group']) for r in all_eligible}&{norm(r['source_group']) for r in main_rows})
  rawcap=db.capacitances();candidate_cycles=db.tests();all_materials={r['material_key']:r for r in db.materials()}
  ce=[dict(r['record'],source_group='doi:'+all_materials[r['material_key']]['doi']) for r in db.outcomes()]
  folds=[]
  for source in sorted({norm(r['source_group']) for r in all_eligible}):
   train=[r for r in all_eligible if norm(r['source_group'])!=source]
   validation=[r for r in all_eligible if norm(r['source_group'])==source]
   check('heldout_whole_source_'+source,not {norm(r['source_group']) for r in train}&{norm(r['source_group']) for r in validation})
   # All other labels from that source are quarantined, including ineligible candidates.
   heldcap=[r for r in rawcap if norm(r['source_group'])==source]
   heldcycles=[r for r in candidate_cycles if norm(r['record']['source_group'])==source]
   heldce=[r for r in ce if norm(r['source_group'])==source]
   folds.append(dict(heldout_source=source,auxiliary_train_rows=len(train),auxiliary_validation_rows=len(validation),quarantined_all_capacitance_reports=len(heldcap),quarantined_cycling_candidates=len(heldcycles),quarantined_CE_reports=len(heldce),actual_model_fit=False))
  for profile,rows in profiles.items():
   counts=Counter(r['source_group'] for r in rows)
   for r in rows:
    r['source_balanced_weight']=1/counts[r['source_group']]
    check('target_finite_'+r['observation_id'],math.isfinite(r['capacitance_F_g']) and r['capacitance_F_g']>0)
    check('current_bound_'+r['observation_id'],r['current_A_g'] is not None and r['concentration_mol_L'] is not None)
    for field,value in r.items():
     if field.endswith('_is_missing'):check('mask_'+r['observation_id']+'_'+field,value==(r[field.removesuffix('_is_missing')] is None))
   for source in counts:check('unit_source_weight_'+source+'_'+profile,abs(sum(r['source_balanced_weight'] for r in rows if r['source_group']==source)-1)<1e-12)
  cmns=next(r for r in profiles['3e'] if r['sample_name']=='C-MNS')
  check('conflict_feature_not_zero_or_repaired',cmns['mesopore_volume_cm3_g'] is None and cmns['mesopore_volume_cm3_g_is_missing'])
  hurd=next(r for r in profiles['3e'] if r['sample_name']=='Hurd-1')
  check('Raman_direction_explicit',hurd['Raman_ID_IG'] is None and hurd['Raman_IG_ID']==1.03 and abs(hurd['Raman_ID_IG_derived_from_IG_ID']-1/1.03)<1e-12)
  check('CE_not_input_feature',all(not any('coulombic' in f.lower() or 'retention' in f.lower() or 'energy_density' in f.lower() for f in r) for r in all_eligible))
  outputs={}
  for profile,rows in profiles.items():
   stream=io.StringIO(newline='');writer=csv.DictWriter(stream,fieldnames=list(rows[0]),lineterminator='\n');writer.writeheader();writer.writerows(rows)
   outputs['auxiliary_'+profile+'_inputs.csv']=stream.getvalue()
  report=dict(status='passed',checks=len(checks),check_names=list(checks),database_sha256=digest,
    profile_rows={k:len(v) for k,v in profiles.items()},profile_sources={k:len({r['source_group'] for r in v}) for k,v in profiles.items()},
    missingness_by_profile={k:{f:sum(r[f] is None for r in rows) for f in rows[0] if any(r[f] is None for r in rows)} for k,rows in profiles.items()},
    source_group_folds=folds,read_only_input_precheck_passed=True,real_model_fits=0,scientific_goal_complete=False,
    performance_sufficiency='Not established. Only3DOI groups in3E subset and1group in2E device subset;input-readiness is not accuracy evidence or new independent validation.',
    label_boundary='25purpose-reviewed capacitance inputs,not25new cycling retention records. Keep profiles separate;no random row split or same-source auxiliary labels across folds.')
  outputs['auxiliary_input_preflight.json']=json.dumps(report,ensure_ascii=False,indent=2)+'\n'
  sealed=(OUT/'merge_manifest.json').exists()
  for name,value in outputs.items():
   path=OUT/name
   if sealed:check('sealed_'+name,path.read_text('utf8')==value)
   else:path.write_text(value,encoding='utf8',newline='')
 check('database_unchanged_by_precheck',sha(DB)==digest)
 print(json.dumps({k:v for k,v in report.items() if k not in ['check_names','missingness_by_profile']},ensure_ascii=False))
if __name__=='__main__':main()
