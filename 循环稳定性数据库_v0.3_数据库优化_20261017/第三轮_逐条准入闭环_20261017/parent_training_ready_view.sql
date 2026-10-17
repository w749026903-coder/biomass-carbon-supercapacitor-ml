CREATE VIEW training_ready AS SELECT e.* FROM endpoint_effective_review e
   JOIN admissions a USING(record_id)
   WHERE e.system='2E_symmetric' AND e.method='GCD' AND e.metric_kind='capacitance_retention'
   AND e.material_scope IN ('carbon_candidate','carbon_control') AND e.retention_relation='eq'
   AND e.retention_pct IS NOT NULL AND e.cycle_count>=1000 AND e.conflict=0 AND e.short_test=0
   AND e.category IN ('A','B') AND e.Si_residue_review_required=0
   AND a.eligible=1 AND a.status='approved' AND a.source_checked=1 AND a.material_checked=1
   AND a.protocol_checked=1 AND a.baseline_checked=1 AND a.mass_basis_checked=1
   AND a.independence_checked=1 AND a.freeze_cleared=1
   AND e.current_density_A_g>0 AND e.electrolyte IS NOT NULL AND e.concentration_value>0
   AND e.concentration_unit IS NOT NULL AND e.voltage_lower_V IS NOT NULL AND e.voltage_upper_V>e.voltage_lower_V
   AND NOT EXISTS(SELECT 1 FROM record_blockers b WHERE b.record_id=e.record_id AND b.status='open');
