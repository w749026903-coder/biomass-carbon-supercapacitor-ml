"""Read-only merged-data preflight. No estimator imports or fit calls."""
from pathlib import Path
import json,sqlite3
ROOT=Path(__file__).resolve().parents[1]
def target_errors(row):
 errors=[]
 if row.get('metric_kind')!='capacitance_retention':errors.append('wrong_target_metric')
 if row.get('system')!='2E_symmetric':errors.append('wrong_system_for_canonical_2E_contract')
 if row.get('method')!='GCD':errors.append('wrong_cycle_method')
 if row.get('retention_relation')!='eq':errors.append('non_exact_label')
 if row.get('mass_basis')!='two_electrode_total_active_mass':errors.append('canonical_current_denominator_not_established')
 return errors

def run():
 contract=json.loads((ROOT/'merge_contract.json').read_text(encoding='utf-8'))
 c=sqlite3.connect((ROOT/contract['database_file']).as_uri()+'?mode=ro',uri=True);c.row_factory=sqlite3.Row
 strict=[dict(x) for x in c.execute('select * from training_ready')]
 invalid=[{'record_id':x['record_id'],'errors':target_errors(x)} for x in strict if target_errors(x)]
 valid_fixture={'metric_kind':'capacitance_retention','system':'2E_symmetric','method':'GCD','retention_relation':'eq','mass_basis':'two_electrode_total_active_mass'}
 wrong_target=dict(valid_fixture,metric_kind='capacity_retention')
 wrong_system=dict(valid_fixture,system='3E')
 checks={'training_disabled':contract['research_training_authorized'] is False,'correct_target_fixture_accepted':not target_errors(valid_fixture),'capacity_retention_fixture_rejected':'wrong_target_metric' in target_errors(wrong_target),'3E_fixture_rejected_by_2E_contract':'wrong_system_for_canonical_2E_contract' in target_errors(wrong_system),'all_exported_rows_target_safe':not invalid,'new_candidates_not_admitted':c.execute('select sum(training_admitted) from staged_cycling_evidence').fetchone()[0]==0}
 profiles=[dict(x) for x in c.execute('select profile,count(*) as rows,count(distinct validation_group_id) as source_groups from training_rows_r4 group by profile')]
 weights=[dict(x) for x in c.execute('select profile,validation_group_id,sum(source_weight) as total from training_rows_r4 group by profile,validation_group_id having abs(sum(source_weight)-1)>0.000001')]
 checks['source_weights_sum_to_one_per_profile_group']=not weights
 sets={p['profile']:{x[0] for x in c.execute('select record_id from training_rows_r4 where profile=?',(p['profile'],))} for p in profiles}
 checks['profiles_nested_not_additive']=sets['literature_core7_exact']<=sets['literature_residue_sensitivity']<=sets['literature_approx_sensitivity']
 c.close()
 return {'all_checks_passed':all(checks.values()),'checks':checks,'canonical_rows':len(strict),'proposal_profiles':profiles,'invalid_exported_rows':invalid,'research_fit_calls':0,'synthetic_fit_calls':0,'formal_training_ready':False,'reason':'Canonical current export empty; proposal profiles and 3E evidence retain distinct contracts. No data fitted.'}
if __name__=='__main__':
 result=run();print(json.dumps(result,ensure_ascii=False,indent=2));raise SystemExit(0 if result['all_checks_passed'] else 1)
