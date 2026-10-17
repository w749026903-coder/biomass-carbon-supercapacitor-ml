"""Prediction-time validation only; does not invent a trained predictor."""
import copy,json,math
from pathlib import Path
from prepare_dataset import canonicalize_concentration
ROOT=Path(__file__).resolve().parents[1]
CONTRACT=json.loads((ROOT/'prediction_input_contract.json').read_text(encoding='utf-8'))
def canonical_current(value,basis,positive_mass_g=None,negative_mass_g=None):
    if not isinstance(value,(int,float)) or isinstance(value,bool) or not math.isfinite(value) or value<=0:
        raise ValueError('Positive finite cycle current density required')
    if basis=='two_electrode_total_active_mass':return value
    if basis in ['positive_electrode_active_mass','negative_electrode_active_mass']:
        masses=[positive_mass_g,negative_mass_g]
        if any(not isinstance(m,(int,float)) or isinstance(m,bool) or not math.isfinite(m) or m<=0 for m in masses):
            raise ValueError('Both active masses must be directly available for current normalization')
        numerator=positive_mass_g if basis.startswith('positive') else negative_mass_g
        return value*numerator/(positive_mass_g+negative_mass_g)
    raise ValueError('Unspecified or capacitance-formula-only current mass basis is not usable')

def prepare_prediction_inputs(payload,feature_set='plus_BET'):
    if feature_set not in ['plus_BET','plus_BET_pore','protocol_only']:raise ValueError('Unknown input contract')
    scope=payload.get('scope_confirmation',{})
    expected={'system':'2E_symmetric','cycling_method':'GCD','electrolyte_phase':'aqueous_liquid','material':'biomass_derived_carbon_scope_cleared','mass_balance':'matched_or_justified_equal_active_masses'}
    if any(scope.get(k)!=v for k,v in expected.items()):raise ValueError('Scope confirmation required; incompatible systems are separate tasks')
    row=copy.deepcopy(payload.get('inputs',{}));metadata=payload.get('evidence_metadata',{})
    allowed={x['name'] for x in CONTRACT['required_physical_inputs']+CONTRACT['optional_physical_inputs']}|{'concentration_unit'}
    if set(row)-allowed:raise ValueError('Unexpected/target-derived input fields are forbidden')
    for item in CONTRACT['required_physical_inputs']:
        key=item['name'];v=row.get(key)
        if v is None:raise ValueError('Required prediction input missing: '+key)
        if key=='electrolyte':
            if not isinstance(v,str) or not v.strip():raise ValueError('Chemical electrolyte identity required')
        elif not isinstance(v,(int,float)) or isinstance(v,bool) or not math.isfinite(v):raise ValueError('Finite numeric input required: '+key)
    if row['cycle_count']<1000 or int(row['cycle_count'])!=row['cycle_count']:raise ValueError('Primary prediction horizon is an integer >=1000; not a universal physical limit')
    if row['voltage_lower_V']<0 or row['voltage_upper_V']<=row['voltage_lower_V']:raise ValueError('Full-device positive voltage window required')
    if row['BET_m2_g']<=0:raise ValueError('Positive measured BET required')
    if metadata.get('BET_method')!='N2-BET' or metadata.get('characterization_stage')!='precycling_as_prepared':raise ValueError('Precycling product N2-BET required')
    row=canonicalize_concentration(row)
    row['current_density_A_g']=canonical_current(row['current_density_A_g'],metadata.get('current_mass_basis'),metadata.get('positive_active_mass_g'),metadata.get('negative_active_mass_g'))
    pore=row.get('total_pore_volume_cm3_g')
    if pore is not None and (not isinstance(pore,(int,float)) or isinstance(pore,bool) or not math.isfinite(pore) or pore<=0):raise ValueError('Pore volume must be positive or missing')
    if pore is not None and metadata.get('pore_volume_kind')!='total':raise ValueError('Micropore volume cannot substitute total pore volume')
    keys=['cycle_count','current_density_A_g','electrolyte','concentration_value','voltage_lower_V','voltage_upper_V']
    if feature_set!='protocol_only':keys+=['BET_m2_g']
    if feature_set=='plus_BET_pore':keys+=['total_pore_volume_cm3_g']
    result={k:row.get(k) for k in keys};result['log10_cycle_count']=math.log10(row['cycle_count']);result.pop('cycle_count')
    return {'features':result,'unit':'current per total active mass of both electrodes; concentration mol/L','prediction_computed':False,'note':'No model is trained; this validates inputs only. External extrapolation also requires checking the future admitted training range.'}
