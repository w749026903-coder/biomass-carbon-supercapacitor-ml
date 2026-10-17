"""Behavior checks for scientific unit and prediction-time boundaries; no fitting."""
import copy,json
from pathlib import Path
from prediction_inputs import prepare_prediction_inputs,canonical_current
from prepare_dataset import canonicalize_concentration,validate_rows
from train_nested import train
checks={}
payload={'scope_confirmation':{'system':'2E_symmetric','cycling_method':'GCD','electrolyte_phase':'aqueous_liquid','material':'biomass_derived_carbon_scope_cleared','mass_balance':'matched_or_justified_equal_active_masses'},'inputs':{'cycle_count':10000,'current_density_A_g':5.,'electrolyte':'KOH','concentration_value':6.,'concentration_unit':'M','voltage_lower_V':0.,'voltage_upper_V':1.,'BET_m2_g':1500.,'total_pore_volume_cm3_g':None},'evidence_metadata':{'BET_method':'N2-BET','characterization_stage':'precycling_as_prepared','current_mass_basis':'two_electrode_total_active_mass'}}
def reject(name,p):
 try:prepare_prediction_inputs(p)
 except ValueError:checks[name]=True
 else:checks[name]=False
valid=prepare_prediction_inputs(payload)
checks['seven_core_physical_features_emitted']=len(valid['features'])==7 and valid['features']['log10_cycle_count']==4
checks['concentration_unit_not_a_predictor']='concentration_unit' not in valid['features']
checks['optional_pore_missing_allowed']=prepare_prediction_inputs(payload,'plus_BET_pore')['features']['total_pore_volume_cm3_g'] is None
for field in ['BET_m2_g','cycle_count','current_density_A_g','electrolyte','concentration_value','voltage_lower_V','voltage_upper_V']:
 p=copy.deepcopy(payload);p['inputs'].pop(field);reject('missing_'+field+'_rejected',p)
for unit in ['m','mol/kg','wt%']:
 p=copy.deepcopy(payload);p['inputs']['concentration_unit']=unit;reject('ambiguous_or_nonmolar_'+unit+'_rejected',p)
p=copy.deepcopy(payload);p['inputs'].update(concentration_unit='mM',concentration_value=6000.)
checks['exact_mM_conversion_to_molar']=prepare_prediction_inputs(p)['features']['concentration_value']==6.
p=copy.deepcopy(payload);p['inputs']['retention_pct']=99.;reject('target_leakage_input_rejected',p)
p=copy.deepcopy(payload);p['evidence_metadata']['characterization_stage']='postcycling';reject('post_cycle_BET_rejected',p)
p=copy.deepcopy(payload);p['evidence_metadata']['BET_method']='CO2-DFT';reject('CO2_DFT_not_substituted_for_BET',p)
p=copy.deepcopy(payload);p['inputs']['total_pore_volume_cm3_g']=0.2;p['evidence_metadata']['pore_volume_kind']='micropore';reject('micropore_not_total',p)
p=copy.deepcopy(payload);p['scope_confirmation']['system']='3E';reject('three_electrode_scope_rejected',p)
p=copy.deepcopy(payload);p['scope_confirmation']['electrolyte_phase']='gel';reject('gel_scope_rejected',p)
p=copy.deepcopy(payload);p['scope_confirmation']['cycling_method']='CV';reject('CV_cycle_scope_rejected',p)
p=copy.deepcopy(payload);p['scope_confirmation']['material']='metal_composite';reject('metal_composite_scope_rejected',p)
p=copy.deepcopy(payload);p['scope_confirmation']['mass_balance']='unequal';reject('unequal_mass_scope_rejected',p)
p=copy.deepcopy(payload);p['evidence_metadata']['current_mass_basis']='capacitance_formula_mass';reject('capacitance_formula_mass_not_current_mass',p)
p=copy.deepcopy(payload);p['evidence_metadata']['current_mass_basis']='positive_electrode_active_mass';reject('single_mass_without_both_active_masses_rejected',p)
checks['defined_single_to_total_current_conversion']=canonical_current(5.,'positive_electrode_active_mass',0.004,0.004)==2.5
p=copy.deepcopy(payload);p['inputs']['cycle_count']=500;reject('short_cycle_outside_primary_horizon',p)
try:train('plus_BET','SHOULD_NEVER_RUN')
except RuntimeError:checks['research_train_hard_gate_rejects_before_fitting']=True
else:checks['research_train_hard_gate_rejects_before_fitting']=False
out={'checks':checks,'all_passed':all(checks.values()),'fixture':'Explicit synthetic form values only; never inserted in SQLite','fitting_performed':False,'prediction_computed':False}
(Path(__file__).parent/'input_contract_checks.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(out,ensure_ascii=False,indent=2));assert out['all_passed']
