"""Fix the prediction-time interface; no fitting and no shared-file mutation."""
from pathlib import Path
import json,shutil
ROOT=Path(__file__).resolve().parent;PARENT=ROOT.parent
model=ROOT/'modeling'
for p in (PARENT/'modeling').iterdir():
 if p.is_file() and p.suffix in ['.py','.txt','.json'] and p.name not in ['preflight_result_v03.json','v03_group_guard_checks.json']:
  out=model/p.name
  if out.exists():raise RuntimeError('Already prepared; do not regenerate.')
  shutil.copyfile(p,out)
cfg=json.loads((model/'model_contract.json').read_text(encoding='utf-8'))
cfg['database_file']='cycling_v0_3r2.sqlite'
cfg['required_conditions']=['cycle_count','current_density_A_g','electrolyte','concentration_value','voltage_lower_V','voltage_upper_V']
cfg['categorical_features']=['electrolyte']
cfg['forbidden_features']+=['concentration_unit','reported_concentration_value','reported_concentration_unit','positive_negative_mass_ratio','retention_relation','year','source_category']
cfg['primary_required_material_features']=['BET_m2_g']
cfg['common_cohort_policy']='All three primary comparisons use the same admitted cohort with directly available BET; optional pore values may be missing. Protocol-only on a larger cohort is a separate diagnostic, not a fair material-feature comparison.'
cfg['normalization_policy']='Concentration canonicalized to mol/L; M and mol/L synonymous, mM divided by1000. mol/kg and mass fraction never converted without solvent-density/composition evidence. Units remain provenance, not predictors.'
cfg['comparison_policy']='Main declared model is plus_BET (seven physical inputs); protocol_only is the same-cohort six-input comparator; plus_BET_pore is an eight-input prespecified sensitivity analysis, never selected on outer scores as an unbiased final result.'
cfg['missing_feature_policy']='Core seven inputs are not imputed. Optional pore only: fold-trained median plus missing indicator. Missing material characterization cannot be hidden by inventing BET.'
cfg['research_training_authorized']=False
(model/'model_contract.json').write_text(json.dumps(cfg,ensure_ascii=False,indent=2),encoding='utf-8')
contract={
 'schema_version':'retention-input-contract-v1','decision_status':'fixed_for_characterized_material_prediction','output':'capacitance_retention_pct_at_requested_cycle_count_and_protocol',
 'prediction_moment':'After material fabrication and pre-cycle characterization, before the requested long cycling test.',
 'scope':{'system':'2E_symmetric','cycling_method':'GCD','electrolyte_phase':'aqueous_liquid','material':'biomass_derived_carbon_scope_cleared','mass_balance':'matched_or_justified_equal_active_masses','not_a_feature':'Scope predicates and evidence gates are not one-hot shortcuts for mixing incompatible systems.'},
 'required_physical_inputs':[
 {'name':'cycle_count','label':'计划预测的循环次数','unit':'cycles','transform':'log10','reason':'Defines the prediction horizon; not an observed failure cycle or achieved test length at inference.'},
 {'name':'current_density_A_g','label':'循环电流密度','unit':'A/g','normalization_metadata_required':'Explicit active-mass denominator; one-electrode and two-electrode total mass are not silently interchangeable.'},
 {'name':'electrolyte','label':'电解液种类','unit':'categorical chemical identity','transform':'one-hot fitted on training groups only'},
 {'name':'concentration_value','label':'电解液摩尔浓度','unit':'mol/L','normalization_metadata_required':'concentration_unit; M=mol/L. No automatic mol/kg→mol/L.'},
 {'name':'voltage_lower_V','label':'器件循环电压下限','unit':'V','reference':'full-device terminals, not reference-electrode potentials'},
 {'name':'voltage_upper_V','label':'器件循环电压上限','unit':'V','reference':'full-device terminals'},
 {'name':'BET_m2_g','label':'循环前成品BET比表面积','unit':'m2/g','method':'N2-BET; CO2-DFT or unqualified surface area not substituted'}],
 'optional_physical_inputs':[{'name':'total_pore_volume_cm3_g','label':'循环前成品总孔体积','unit':'cm3/g','policy':'Only plus_BET_pore. Missing allowed with fold-only imputation/indicator. Micropore volume is not total volume; ambiguous printed unit remains missing.'}],
 'input_counts':{'main_required_physical_inputs':7,'extended_physical_inputs':8,'protocol_comparator_physical_inputs':6,'one_hot_and_missing_indicator_expand_model_columns':True},
 'not_yet_primary_features':['XPS_N_at_pct','XPS_O_at_pct','Raman_ID_IG_with_definition','active_mass_loading_mg_cm2','micropore_volume_cm3_g','carbonization_temperature_C','carbonization_duration_h','activation_temperature_C','activation_duration_h','activator_identity','activator_to_char_or_biomass_ratio_with_denominator','precursor_class'],
 'metadata_not_predictors':['paper_id','DOI','material_id','test_id','study_group','source_location','concentration_unit','current_mass_basis','baseline_definition','scope_review','freeze_state','precycling_stage','measurement_method','electrode_mass_balance','test_temperature_if_reported'],
 'prohibited_predictors':['retention_pct','final_capacitance','capacitance_loss_from_same_target','post_cycle_EIS','post_cycle_XPS','post_cycle_SEM','discharge_time_used_in_target_calculation','observed_failure_cycle','paper_id','doi','study_group'],
 'process_only_route':'A separate future route can use feedstock/activation/carbonization parameters plus requested test conditions. It may not require measured BET. No process-only model is currently claimed ready; evidence must support stage and ratio definitions.',
 'training_authorized':False,'no_model_performance_claims':True,
 'definition_change_from_v03':['Drop concentration unit from categorical predictors after exact unit canonicalization.','Require actual BET for the primary material prediction and keep a same-cohort protocol comparator.','Fix seven core plus one optional input instead of leaving an unexplained list of alternatives.']}
(ROOT/'prediction_input_contract.json').write_text(json.dumps(contract,ensure_ascii=False,indent=2),encoding='utf-8')
(ROOT/'预测输入填写模板.json').write_text(json.dumps({'scope_confirmation':contract['scope'],'inputs':{'cycle_count':None,'current_density_A_g':None,'electrolyte':None,'concentration_value':None,'concentration_unit':'mol/L','voltage_lower_V':None,'voltage_upper_V':None,'BET_m2_g':None,'total_pore_volume_cm3_g':None},'evidence_metadata':{'current_mass_basis':None,'BET_method':'N2-BET','characterization_stage':'precycling_as_prepared','test_temperature_C':None,'baseline_reference_to_be_used':None},'note':'Null is a blank to fill, never zero. This is an input form, not fabricated experimental data or a prediction.'},ensure_ascii=False,indent=2),encoding='utf-8')
print('Fixed seven core inputs plus optional pore volume; no research fitting.')
