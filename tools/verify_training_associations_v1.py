"""Independent fact coverage, task semantics, original-value and isolation verification."""
from pathlib import Path
import collections,csv,json,math,sqlite3,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.build_training_associations_v1 import OUT,DB,MAP
from tools.extend_training_associations_v1 import block
from tools.train_model_v1 import read,write,sha
from data.literature_current import open_literature_database
from data.cycling_db import open_database
from data.training_datasets import open_training_datasets

def verify(save=False):
    counts=collections.Counter()
    def ck(group,ok):assert ok,group;counts[group]+=1
    summary=read(OUT/'summary.json');c=sqlite3.connect(DB.resolve().as_uri()+'?mode=ro',uri=True);c.row_factory=sqlite3.Row
    ck('SQLite_integrity',c.execute('pragma integrity_check').fetchone()[0]=='ok');ck('foreign_keys',not c.execute('pragma foreign_key_check').fetchall())
    for p,h in read(OUT/'protected_inputs.json').items():ck('protected_original_SHA',sha(ROOT/p)==h)
    facts={r['fact_id']:json.loads(r['record_json'])for r in c.execute('select *from facts')};ledger={r['fact_id']:json.loads(r['record_json'])for r in c.execute('select *from usage_ledger')}
    ck('4670_all_facts_accounted',set(facts)==set(ledger)and len(facts)==4670);ck('4469numeric201nonpoint',sum(f['value']is not None for f in facts.values())==4469)
    with open_literature_database()as l,open_database()as d:
        expected={r['fact_id']:r for r in l.facts()}
        for fid,f in facts.items():ck('all_original_fact_values_and_receipts',f==expected[fid])
        old={r['endpoint_id']:r for r in d.fetch('all_review').rows}
        for r in c.execute('select *from cycle_records'):
            v=json.loads(r['record_json']);v.pop('source_family');v.pop('current_profiles');ck('287_original_cycle_records',v==old[r['endpoint_id']])
        ck('original_pending37',len(d.reviewed_pending_batch())==37)
        for name in summary['task_counts']:
            if name.startswith('cycle:'):
                original={r['endpoint_id']:r for r in d.fetch(name.split(':',1)[1]).rows}
                actual={r['row_id']:json.loads(r['record_json'])for r in c.execute('select row_id,record_json from inputs where task=?',(name,))}
                ck('no_unreviewed_cycle_admission',set(actual)==set(original))
                for eid,r in actual.items():ck('cycle_labels_protocol_unchanged',r['target']==original[eid]['retention_pct']and r['conditions']['reported_current_A_g']==original[eid]['reported_current_A_g'])
        for r in c.execute('select *from cycle_material_links'):
            m=json.loads(c.execute('select record_json from materials where material_key=?',(r['material_key'],)).fetchone()[0]);ck('identity_source_family_matches',l.isolation_group(old[r['endpoint_id']]['source_group'])==m['source_family'])
    inputs={(r['task'],r['row_id']):json.loads(r['record_json'])for r in c.execute('select *from inputs')};use_ids=set()
    for use in c.execute('select *from fact_uses'):
        f=facts[use['fact_id']];r=inputs[use['task'],use['row_id']];value=r['target']if use['role']=='target'else r['features'][use['feature']]
        ck('every_input_and_target_has_actual_fact_value',f['value']is not None and value==f['value']);use_ids.add(use['fact_id'])
        ck('fact_same_material_or_explicit_precursor',f['material_key']==r['material_key']or(use['task'].startswith('lineage:')and f['material_key']==r['lineage_path'][0]))
    numericused={fid for fid in use_ids if facts[fid]['value']is not None}
    ck('independent_usage_count_not_defaultdict_keys',len(numericused)==summary['numeric_facts_connected_to_training_inputs']==2823)
    ck('usage_rate_exact_denominator',summary['numeric_fact_connection_rate']==2823/4469)
    for fid,u in ledger.items():ck('per_fact_usage_disposition',bool(u['uses'])==(fid in use_ids))
    annotations=read(OUT/'typed_feature_contract.json')
    for (task,rid),r in inputs.items():
        ck('finite_target',isinstance(r['target'],(int,float))and math.isfinite(r['target']))
        if task.startswith('material:'):
            for f in r['features']:
                original=annotations.get(f,{}).get('original_field',f);ck('no_measurement_block_target_leakage',block(original)!=r['excluded_target_measurement_block'])
        if task.startswith('capacity:'):
            ck('capacity_not_cycle_label',r['not_cycling_label']and 'cycle_count'not in r['features']);ck('multi_condition_current_is_feature',r['features']['reported_current_A_g']==r['conditions']['reported_current_A_g'])
        if task.startswith('lineage:'):
            decisions={(e['parent'],e['child']):e['physical_transition_eligible']for e in read(OUT/'lineage_training_decisions.json')}
            path=r['lineage_path'];ck('actual_physical_transition_not_factor_variant',all(decisions.get((a,b),False)for a,b in zip(path,path[1:])))
            ck('precursor_not_inherited_into_final_fields',all(f.startswith('precursor__')for f in r['features']))
    expected208={k[1]for k in inputs if k[0]=='capacity:3e_reported'};expected386={k[1]for k in inputs if k[0]=='capacity:3e_with_graph'}
    ck('208_nested_in386_not594',len(expected208)==208 and len(expected386)==386 and expected208<=expected386)
    frozen_blocks=read(OUT/'cross_task_freeze_review.json')['material_blocks']
    for r in c.execute('select *from selected_features'):
        f=r['field'];b=frozen_blocks.get(r['material_key'],[])
        ck('frozen_Raman_ratio_not_revived',not('Raman_ratio'in b and f.startswith(('Raman_ID_IG','Raman_IG_ID','Raman_derived_crystallite'))))
        ck('frozen_N_O_not_revived',not('N'in b and f.startswith(('XPS_N_at_pct','XPS_N_wt_pct','XPS_C_to_N_atomic_ratio')))and not('O'in b and f.startswith(('XPS_O_at_pct','XPS_O_wt_pct'))))
    old=read(ROOT/'模型v1.2_来源隔离再训练_20261028/input_snapshot.json');main={rid:r for (task,rid),r in inputs.items()if task=='cycle:reported_3e'}
    for r in old['records']:
        for f in old['features']:
            if r.get(f)is not None:ck('v12_existing_nonmissing_inputs_preserved',main[r['endpoint_id']]['features'][f]==r[f])
    c.close()
    with open_training_datasets(DB,sha(DB))as api:
        for task,info in api.tasks().items():
            matrix=api.matrix(task);ck('public_matrix_shapes',len(matrix['X'])==len(matrix['y'])==info['rows']and len(set(matrix['groups']))==info['source_families'])
            ck('correct_missing_masks',matrix['missing_mask']==[[x is None for x in row]for row in matrix['X']])
            weights=collections.defaultdict(float)
            for g,w in zip(matrix['groups'],matrix['sample_weight']):weights[g]+=w
            ck('source_equal_weights',all(abs(w-1)<1e-10 for w in weights.values()))
        held='doi:10.1016/j.heliyon.2024.e25628';bundle=api.training_bundle([held])
        for task,m in bundle.items():ck('all_tasks_whole_source_quarantine',held not in m['groups'])
        ck('all_fact_API',len(api.fact_usage())==4670)
    report=dict(status='passed',checks=sum(counts.values()),check_groups=dict(counts),numeric_facts=4469,connected_numeric_facts=2823,unconnected_numeric_facts=1646,
        nonpoint_facts=201,material_registrations=458,cycle_records=287,candidates=96,model_fits=0,original_pending=37,database_sha256=sha(DB))
    if save:write(OUT/'verification.json',report)
    else:assert read(OUT/'verification.json')==report
    if(OUT/'merge_manifest.json').exists():
        for r in read(OUT/'merge_manifest.json')['outputs']:assert sha(ROOT/r['path'])==r['sha256'],r['path']
    print(json.dumps({k:v for k,v in report.items()if k!='check_groups'}))
if __name__=='__main__':verify('--save'in sys.argv)
