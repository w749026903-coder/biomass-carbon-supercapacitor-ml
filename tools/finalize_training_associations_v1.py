"""Cross-task freeze propagation and complete usage/queue exports before sealing."""
from pathlib import Path
import collections,csv,io,json,sqlite3,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.build_training_associations_v1 import OUT,DB,scope
from tools.train_model_v1 import read,write
from data.cycling_db import open_database

def finalize():
    assert not(OUT/'merge_manifest.json').exists()and not(OUT/'cross_task_freeze_review.json').exists()
    c=sqlite3.connect(DB);c.row_factory=sqlite3.Row;c.execute('pragma foreign_keys=on');dump=lambda v:json.dumps(v,ensure_ascii=False,allow_nan=False)
    c.execute('create table held_features(material_key text,field text,record_json text,primary key(material_key,field))')
    c.execute('create table held_inputs(task text,row_id text,record_json text,reason text,primary key(task,row_id))')
    links={r['endpoint_id']:r['material_key']for r in c.execute('select *from cycle_material_links')};blocks=collections.defaultdict(set)
    with open_database()as d:
        for eid,fs in d.freezes_v21.items():
            if eid not in links:continue
            if 'Raman_ID_IG'in fs:blocks[links[eid]].add('Raman_ratio')
            if 'N_at_pct'in fs:blocks[links[eid]].add('N')
        for conf in d.feature_conflicts_v24():
            for r in d.fetch('all_review').rows:
                if r.get('material_key_v11')==conf['material_key']and r['endpoint_id']in links:blocks[links[r['endpoint_id']]].update(['N','O'])
    def blocked(mk,f):
        if f.startswith(('lib__','precursor__')):f=f.split('__',1)[1]
        if 'Raman_ratio'in blocks[mk] and f.startswith(('Raman_ID_IG','Raman_IG_ID','Raman_derived_crystallite')):return True
        if 'N'in blocks[mk]and(f.startswith(('XPS_N_at_pct','XPS_N_wt_pct','XPS_N_reported_pct','XPS_C_to_N_atomic_ratio'))):return True
        if 'O'in blocks[mk]and f.startswith(('XPS_O_at_pct','XPS_O_wt_pct','XPS_O_reported_pct')):return True
        return False
    frozen_ids=set();held=[]
    for r in c.execute('select *from selected_features').fetchall():
        if blocked(r['material_key'],r['field']):
            held.append(dict(r));frozen_ids.update(json.loads(r['fact_ids_json']));c.execute('insert into held_features values(?,?,?)',(r['material_key'],r['field'],dump(dict(r))))
            c.execute('delete from selected_features where material_key=?and field=?',(r['material_key'],r['field']))
    rows_held=0;fields_removed=0
    for r in c.execute('select *from inputs').fetchall():
        v=json.loads(r['record_json']);mk=r['material_key'];parent=None
        if r['task'].startswith('lineage:'):parent=v['lineage_path'][0]
        target_bad=blocked(mk,v['target_name']);xx={f:value for f,value in v['features'].items()if not blocked(parent or mk,f)}
        if target_bad or not xx:
            c.execute('insert into held_inputs values(?,?,?,?)',(r['task'],r['row_id'],r['record_json'],'historical_freeze_or_no_independent_predictor'))
            c.execute('delete from fact_uses where task=?and row_id=?',(r['task'],r['row_id']));c.execute('delete from inputs where task=?and row_id=?',(r['task'],r['row_id']));rows_held+=1
        else:
            for f in set(v['features'])-set(xx):c.execute('delete from fact_uses where task=?and row_id=?and feature=?',(r['task'],r['row_id'],f));fields_removed+=1
            v['features']=xx;c.execute('update inputs set record_json=?where task=?and row_id=?',(dump(v),r['task'],r['row_id']))
    for r in c.execute('select *from materials').fetchall():
        v=json.loads(r['record_json']);v['excluded_by_cross_task_freeze']=[f for f in v['features']if blocked(r['material_key'],f)]
        v['features']={f:x for f,x in v['features'].items()if not blocked(r['material_key'],f)};c.execute('update materials set record_json=?where material_key=?',(dump(v),r['material_key']))
    uses=collections.defaultdict(list)
    for r in c.execute('select *from fact_uses'):uses[r['fact_id']].append(dict(task=r['task'],row_id=r['row_id'],feature=r['feature'],role=r['role']))
    mats={r['material_key']:json.loads(r['record_json'])for r in c.execute('select *from materials')};facts={r['fact_id']:json.loads(r['record_json'])for r in c.execute('select *from facts')}
    selected_ids={fid for r in c.execute('select fact_ids_json from selected_features')for fid in json.loads(r[0])}
    for fid,f in facts.items():
        value=f['value'];old=json.loads(c.execute('select record_json from usage_ledger where fact_id=?',(fid,)).fetchone()[0]);us=uses.get(fid,[])
        if us:status='connected_to_training_inputs'
        elif value is None:status='nonpoint_or_missing_retained'
        elif fid in frozen_ids:status='historical_field_freeze_across_all_tasks'
        elif fid in selected_ids:
            status='reference_or_identity_unresolved'if scope(mats[f['material_key']])=='reference_or_unresolved'else'stage_specific_or_no_qualified_target'
        elif 'ambiguous'in f['review_status']or'as_printed'in f['unit']:status='method_or_unit_ambiguity_retained'
        elif any(x in f['field_name'].lower()for x in ['uncert','error']):status='measurement_uncertainty_metadata_not_independent_predictor'
        elif any(x in f['unit'].lower()for x in ['unspec','unknown','as_reported']):status='composition_or_measurement_basis_unresolved'
        elif 'conflict'in f['review_status']or old['disposition']=='competing_or_nonselected_report':status='competing_or_nonselected_report'
        else:status='specialized_target_or_feature_contract_pending'
        old.update(disposition=status,uses=us,training_connected=bool(us));c.execute('update usage_ledger set disposition=?,record_json=?where fact_id=?',(status,dump(old),fid))
    s=read(OUT/'summary.json');n=c.execute('select count(distinct u.fact_id)from fact_uses u join facts f using(fact_id)where numeric=1').fetchone()[0]
    s.update(numeric_facts_connected_to_training_inputs=n,numeric_fact_connection_rate=n/4469,usage_counts=dict(collections.Counter(r[0]for r in c.execute('select disposition from usage_ledger'))),
             cross_task_freeze_selected_fields_held=len(held),cross_task_freeze_input_rows_held=rows_held)
    counts={}
    for task, in c.execute('select distinct task from inputs'):
        rr=[json.loads(r[0])for r in c.execute('select record_json from inputs where task=?',(task,))];gg={r['source_family']for r in rr};counts[task]=dict(rows=len(rr),source_families=len(gg),source_holdout_validation_possible=len(gg)>=2)
    s['task_counts']=counts;c.execute("update metadata set value_json=?where key='summary'",(dump(s),));c.commit()
    write(OUT/'summary.json',s);write(OUT/'cross_task_freeze_review.json',dict(material_blocks={k:sorted(v)for k,v in blocks.items()if v},selected_fields_held=held,input_rows_held=rows_held,input_fields_removed=fields_removed,original_source_rows_changed=False,new_fits=0))
    export=[('all_fact_usage.csv',['fact_id','material_key','doi','sample_name','material_stage','field','value','raw_value','unit','method','source_path','source_sha256','locator','disposition','task_receipts']),
            ('unconnected_numeric_queue.csv',['fact_id','material_key','doi','sample_name','material_stage','field','value','raw_value','unit','method','source_path','source_sha256','locator','disposition','task_receipts'])]
    for name,fields in export:
        b=io.StringIO(newline='');w=csv.DictWriter(b,fieldnames=fields,lineterminator='\n');w.writeheader()
        for r in c.execute('select fact_id,disposition,record_json from usage_ledger order by fact_id'):
            f=facts[r['fact_id']];u=json.loads(r['record_json'])
            if name.startswith('unconnected')and(f['value']is None or u['uses']):continue
            row={k:f.get(k)for k in fields};row.update(fact_id=f['fact_id'],field=f['field_name'],disposition=r['disposition'],task_receipts=len(u['uses']));w.writerow(row)
        (OUT/name).write_text(b.getvalue(),encoding='utf-8-sig',newline='')
    for task in ['cycle:reported_3e','cycle:reported_2e','capacity:3e_reported','capacity:3e_with_graph','capacity:2e_device']:
        rs=[json.loads(r[0])for r in c.execute('select record_json from inputs where task=?order by row_id',(task,))];fields=sorted({f for r in rs for f in r['features']});b=io.StringIO(newline='');w=csv.writer(b,lineterminator='\n');w.writerow(['row_id','source_family','target']+fields)
        for r in rs:w.writerow([r['row_id'],r['source_family'],r['target']]+[r['features'].get(f)for f in fields])
        (OUT/(task.replace(':','_')+'.csv')).write_text(b.getvalue(),encoding='utf-8-sig',newline='')
    c.close();print(json.dumps({k:v for k,v in s.items()if k not in ['task_counts','source_databases']},ensure_ascii=False))
if __name__=='__main__':finalize()
