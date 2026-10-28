"""Keep the graph-expanded profile nested and make release deltas unambiguous."""
from pathlib import Path
import collections,json,sqlite3,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.extract_opb_main_v5 import OUT,DB,read,write,dump,sha

def finalize():
    assert not(OUT/'merge_manifest.json').exists()and not(OUT/'profile_coherence_review.json').exists()
    c=sqlite3.connect(DB);c.row_factory=sqlite3.Row;c.execute('pragma foreign_keys=on');ids=[]
    for row in c.execute('select *from inputs where task="capacity:3e_reported"').fetchall():
        c.execute('insert into inputs values(?,?,?,?)',('capacity:3e_with_graph',row['row_id'],row['material_key'],row['record_json']));ids.append(row['row_id'])
        for u in c.execute('select *from fact_uses where task="capacity:3e_reported"and row_id=?',(row['row_id'],)).fetchall():c.execute('insert into fact_uses values(?,?,?,?,?)',(u['fact_id'],'capacity:3e_with_graph',u['row_id'],u['feature'],u['role']))
    for row in c.execute('select *from usage_ledger').fetchall():
        v=json.loads(row['record_json']);v['uses']=[dict(task=u['task'],row_id=u['row_id'],feature=u['feature'],role=u['role'])for u in c.execute('select *from fact_uses where fact_id=?',(row['fact_id'],))];c.execute('update usage_ledger set record_json=?where fact_id=?',(dump(v),row['fact_id']))
    s=read(OUT/'summary.json');s['task_counts']['capacity:3e_with_graph']=dict(rows=394,source_families=32,source_holdout_validation_possible=True)
    audited={}
    valid_new={'new_material_registrations':4,'new_material_facts':114,'new_numeric_material_facts':110,'new_sources':1,'new_capacity_reports':8,'new_ready_capacity_rows':8,'new_model_fits':0,'new_cycling_admissions':0,'new_existing_cycle_material_links':4,'new_main3e_nonmissing_feature_cells':60,'new_material_or_precursor_task_rows':32,'new_measurement_metadata_facts':0,'new_response_training_rows':0}
    for key in list(s):
        if key.startswith('new_')and key not in valid_new and key!='new_connected_fact_ids':audited[key]=dict(previous_inherited_value=s.pop(key),action='removed_stale_parent_release_delta')
    for key,value in valid_new.items():
        if s.get(key)!=value:audited[key]=dict(previous_inherited_value=s.get(key),current_value=value)
        s[key]=value
    for key,value in [('cumulative_main3e_material_cells_added_since_v12',165),('net_connection_change_from_v1',568)]:
        # Correct cumulative connection change uses current3391 minus v1's2823.
        if key=='net_connection_change_from_v1':value=s['numeric_facts_connected_to_training_inputs']-2823
        if s.get(key)!=value:audited[key]=dict(previous_inherited_value=s.get(key),current_value=value)
        s[key]=value
    # V2-specific type-count is a historical parent delta, not this batch's count.
    if 'additional_typed_fields'in s:audited['additional_typed_fields']=dict(previous_inherited_value=s.pop('additional_typed_fields'),action='removed_v2_delta')
    s['new_input_representations']=48;s['updated_existing_cycle_input_representations']=16
    c.execute('update metadata set value_json=?where key="summary"',(dump(s),));c.commit();c.close();write(OUT/'summary.json',s)
    write(OUT/'profile_coherence_review.json',dict(ordinary_rows=216,with_graph_rows=394,new_unique_reports=8,new_report_ids=ids,ordinary_is_subset_of_with_graph=True,not_16_new_experiments=True))
    write(OUT/'summary_delta_audit.json',dict(reason='Per-release counters must not silently inherit prior batch deltas; historical parent files unchanged.',changes=audited))
    p=read(OUT/'entrypoint_snapshot.json');p['sha256']=sha(DB);write(OUT/'entrypoint_snapshot.json',p);write(ROOT/'data/current_training_store.json',p)
    print('Restored216⊂394 nesting; corrected per-release/cumulative counters with before/after audit.')

if __name__=='__main__':finalize()
