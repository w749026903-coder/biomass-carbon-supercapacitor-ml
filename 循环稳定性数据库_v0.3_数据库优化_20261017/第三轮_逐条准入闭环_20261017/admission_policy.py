"""Auditable preflight only. No fitting, target imputation, or assumed mass factors."""
from __future__ import annotations

CORE = ('cycle_count', 'current_density_A_g', 'electrolyte',
        'concentration_value', 'voltage_lower_V', 'voltage_upper_V', 'BET_m2_g')
CHECKS = ('source_checked', 'material_checked', 'protocol_checked',
          'baseline_checked', 'mass_basis_checked', 'independence_checked', 'freeze_cleared')
CANONICAL_MASS = 'two_electrode_total_active_mass'
OPTIONAL_CODES = {'pore_volume_unit', 'missing_SI_for_total_pore_volume_cm3_g'}
WATER_ELECTROLYTES = {'KOH', 'H2SO4', 'Na2SO4', 'Li2SO4', 'CH3COONa', 'sodium_acetate', 'KNO3', 'LiCl', 'LiTFSI'}


def assess(row, flags, blockers):
    """Return complete blockers; a completed review is distinct from an admitted row."""
    failures = []
    if row.get('paper_year') is None or not 2023 <= row['paper_year'] <= 2026:
        failures.append('scope:publication_year')
    if row.get('group_review_status') != 'reviewed_available_corpus':
        failures.append('review:validation_group_not_final')
    if row['system'] != '2E_symmetric': failures.append('scope:system')
    if row['method'] != 'GCD': failures.append('scope:cycling_method')
    if row['metric_kind'] != 'capacitance_retention': failures.append('scope:target_metric')
    if row['material_scope'] not in ('carbon_candidate', 'carbon_control'):
        failures.append('scope:material')
    if row['category'] not in ('A', 'B'): failures.append('scope:paper_category')
    if row['electrolyte'] not in WATER_ELECTROLYTES: failures.append('scope:aqueous_electrolyte')
    if row['retention_relation'] != 'eq': failures.append('label:nonpoint_relation')
    if row['retention_pct'] is None: failures.append('label:missing_retention')
    if row['cycle_count'] is None or row['cycle_count'] < 1000 or row['short_test']:
        failures.append('scope:short_test_convention')
    if row['conflict']: failures.append('record:unresolved_conflict')
    if row['Si_residue_review_required']: failures.append('record:product_silicon_scope')
    for field in CORE:
        if row[field] is None or row[field] == '': failures.append('input:missing_' + field)
    for field in ('cycle_count', 'current_density_A_g', 'concentration_value', 'BET_m2_g'):
        if row[field] is not None and row[field] <= 0: failures.append('input:nonpositive_' + field)
    lo, hi = row['voltage_lower_V'], row['voltage_upper_V']
    if lo is not None and hi is not None and hi <= lo: failures.append('input:invalid_voltage_window')
    if row['concentration_unit'] not in ('M', 'mol/L'): failures.append('input:noncanonical_concentration')
    if row['mass_basis'] != CANONICAL_MASS: failures.append('input:current_mass_not_canonical')
    for field in CHECKS:
        if not flags[field]: failures.append('review:' + field)
    for b in blockers:
        if b['status'] == 'open' and b['code'] not in OPTIONAL_CODES:
            failures.append('blocker:' + b['code'])
    return sorted(set(failures))


def clean_optional_pore(row, blockers):
    """An unresolved optional value is masked before any downstream imputation."""
    unsafe = bool(row['pore_unit_review_required']) or any(
        b['status'] == 'open' and b['code'] in OPTIONAL_CODES for b in blockers)
    return None if unsafe else row['total_pore_volume_cm3_g']
