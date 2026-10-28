"""Withdraw uncertainty-as-predictor errors without changing original evidence."""
from pathlib import Path
import collections,csv,io,json,sqlite3,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.improve_training_inputs_v2 import OUT,DB,BASE,read,write,sha,dump

def finalize():
    assert not(OUT/'merge_manifest.json').exists()and not(OUT/'quality_corrections.json').exists()
    c=sqlite3.connect(DB);c.row_factory=sqlite3.Row;c.execute('pragma foreign_keys=on')
    c.execute('create table v2_withdrawn_rows(task text,row_id text,record_json text,reason text,primary key(task,row_id))')
    c.execute('create table v2_withdrawn_features(material_key text,field text,record_json text,reason text,primary key(material_key,field))')
    metadata={r['fact_id'] for r in c.execute('select fact_id from measurement_metadata')}
    affected=set(metadata)&{r[0] for r in c.execute('select distinct fact_id from fact_uses')}
    withdrawn_features=[];withdrawn_rows=[];removed_receipts=[];changes=[]
    for r in c.execute('select *from selected_features').fetchall():
        if set(json.loads(r['fact_ids_json']))&affected:
            c.execute('insert into v2_withdrawn_features values(?,?,?,?)',(r['material_key'],r['field'],dump(dict(r)),'uncertainty_is_measurement_metadata'))
            c.execute('delete from selected_features where material_key=?and field=?',(r['material_key'],r['field']))
            withdrawn_features.append(dict(r))
    for r in c.execute('select *from inputs').fetchall():
        v=json.loads(r['record_json']);refs=c.execute('select *from fact_uses where task=?and row_id=?',(r['task'],r['row_id'])).fetchall()
        bad=[u for u in refs if u['fact_id']in affected]
        if not bad:continue
        if any(u['role']=='target'for u in bad):
            withdrawn_rows.append(dict(task=r['task'],row_id=r['row_id']))
            c.execute('insert into v2_withdrawn_rows values(?,?,?,?)',(r['task'],r['row_id'],r['record_json'],'uncertainty_is_not_a_material_property_target'))
            removed_receipts.extend(dict(u)for u in refs)
            c.execute('delete from fact_uses where task=?and row_id=?',(r['task'],r['row_id']))
            c.execute('delete from inputs where task=?and row_id=?',(r['task'],r['row_id']))
        else:
            fields={u['feature']for u in bad};old={f:v['features'].pop(f)for f in fields}
            v['v2_uncertainty_withdrawal']=old
            if 'v2_additions'in v:v['v2_additions']=[f for f in v['v2_additions']if f not in fields]
            c.execute('update inputs set record_json=?where task=?and row_id=?',(dump(v),r['task'],r['row_id']))
            for u in bad:
                c.execute('delete from fact_uses where fact_id=?and task=?and row_id=?and feature=?and role=?',tuple(u))
                removed_receipts.append(dict(u))
            changes.append(dict(task=r['task'],row_id=r['row_id'],fields=old))
    for mk,rr in c.execute('select material_key,record_json from materials').fetchall():
        v=json.loads(rr);v['features']={r['field']:r['value']for r in c.execute('select *from selected_features where material_key=?',(mk,))}
        c.execute('update materials set record_json=?where material_key=?',(dump(v),mk))
    uses=collections.defaultdict(list)
    for u in c.execute('select *from fact_uses'):uses[u['fact_id']].append(dict(task=u['task'],row_id=u['row_id'],feature=u['feature'],role=u['role']))
    facts={r['fact_id']:json.loads(r['record_json'])for r in c.execute('select *from facts')}
    for fid in facts:
        v=json.loads(c.execute('select record_json from usage_ledger where fact_id=?',(fid,)).fetchone()[0]);us=uses.get(fid,[])
        status='connected_to_training_inputs'if us else 'measurement_metadata_not_independent_predictor'if fid in metadata else v['disposition']
        # A fact can lose all uses when the only row consuming it was an invalid
        # uncertainty target. Restore its actual unresolved status rather than
        # leaving an empty "connected" label.
        if not us and status=='connected_to_training_inputs':status='no_remaining_qualified_target_after_quality_correction'
        v.update(uses=us,training_connected=bool(us),disposition=status)
        c.execute('update usage_ledger set disposition=?,record_json=?where fact_id=?',(status,dump(v),fid))
    s=read(OUT/'summary.json');used={fid for fid in uses if facts[fid]['value']is not None};old=read(BASE/'summary.json')
    s.update(numeric_facts_connected_to_training_inputs=len(used),numeric_fact_connection_rate=len(used)/4469,
             remaining_unconnected_numeric_facts=4469-len(used),net_connection_change_from_v1=len(used)-old['numeric_facts_connected_to_training_inputs'],
             withdrawn_uncertainty_facts=len(affected),withdrawn_uncertainty_target_rows=len(withdrawn_rows))
    s['usage_counts']=dict(collections.Counter(r[0]for r in c.execute('select disposition from usage_ledger')))
    counts={}
    for task, in c.execute('select distinct task from inputs'):
        rows=[json.loads(r[0])for r in c.execute('select record_json from inputs where task=?',(task,))];n=len({r['source_family']for r in rows})
        counts[task]=dict(rows=len(rows),source_families=n,source_holdout_validation_possible=n>=2)
    s['task_counts']=counts;c.execute("update metadata set value_json=?where key='summary'",(dump(s),));c.commit()
    correction=dict(withdrawn_fact_ids=sorted(affected),withdrawn_rows=withdrawn_rows,withdrawn_features=withdrawn_features,
                    removed_receipts=removed_receipts,input_field_changes=changes,old_source_values_changed=False,old_model_training_affected=False,
                    reason='Old v1 field-name filter omitted author_plusminus. Ten BET/volume uncertainty numbers must be metadata, not independent predictors or property targets.')
    write(OUT/'quality_corrections.json',correction);write(OUT/'summary.json',s)
    pointer=read(ROOT/'data/current_training_inputs.json');pointer['sha256']=sha(DB);write(ROOT/'data/current_training_inputs.json',pointer)
    fields=['fact_id','doi','sample_name','material_stage','field_name','value','raw_value','unit','method','source_path','source_sha256','locator','disposition','task_receipts']
    for name,only_unconnected in [('all_fact_usage.csv',False),('unconnected_numeric_queue.csv',True)]:
        stream=io.StringIO(newline='');writer=csv.DictWriter(stream,fieldnames=fields,lineterminator='\n');writer.writeheader()
        for fid,f in facts.items():
            if only_unconnected and (f['value']is None or uses.get(fid)):continue
            u=c.execute('select disposition from usage_ledger where fact_id=?',(fid,)).fetchone()[0]
            record={k:f.get(k)for k in fields};record.update(disposition=u,task_receipts=len(uses.get(fid,[])));writer.writerow(record)
        (OUT/name).write_text(stream.getvalue(),encoding='utf-8-sig')
    c.close();print(dump(dict(connected=len(used),withdrawn_fact_ids=sorted(affected),withdrawn_rows=len(withdrawn_rows))))

if __name__=='__main__':finalize()
