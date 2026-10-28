"""Complete metadata/queue accounting before this new release is sealed."""
from pathlib import Path
import collections,csv,io,json,sqlite3,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.extract_corn_soot_v3 import BASE,OUT,DB,sha,read,write,dump

def finalize():
    assert not(OUT/'merge_manifest.json').exists()and not(OUT/'accounting_finalized.json').exists()
    c=sqlite3.connect(DB);c.row_factory=sqlite3.Row;c.execute('pragma foreign_keys=on');facts=read(OUT/'new_facts.json');meta=[]
    nextq=c.execute('select coalesce(max(queue_id),0)+1 from review_queue').fetchone()[0]
    for f in facts:
        fid=f['fact_id'];u=json.loads(c.execute('select record_json from usage_ledger where fact_id=?',(fid,)).fetchone()[0])
        if not u['uses'] and f['value']is not None:
            field=f['field_name']
            if 'plusminus'in field or 'Uncert'in field:
                status='measurement_metadata_not_independent_predictor';targets=[a['fact_id']for a in facts if a['material_key']==f['material_key']and(a['field_name']=='reported_gravimetric_yield_pct_of_dry_precursor'if'plusminus'in field else a['field_name']==field.replace('_author_Uncert_pct','_wt_pct'))]
                v=dict(fact_id=fid,material_key=f['material_key'],field=field,value=f['value'],unit=f['unit'],kind='author_uncertainty_unspecified_statistic',measured_fact_ids=targets,source_receipt=f,not_predictor=True,not_independent_target=True)
                c.execute('insert into measurement_metadata values(?,?,?)',(fid,f['material_key'],dump(v)));meta.append(v)
            elif field=='BET_surface_area_m2_g':status='BET_table_prose_dispute_frozen'
            elif field=='BET_prose_report_m2_g':status='BET_table_prose_dispute_frozen'if f['sample_name']=='CS-1000'else 'coarse_repeat_not_independent_predictor'
            elif field=='EDS_N_wt_pct':status='EDS_N_table_figure_dispute_frozen'
            elif 'particle_size'in field:status='particle_size_measurement_method_unresolved'
            elif 'TGA'in field:status='TGA_separate_basis_no_qualified_target'
            else:raise AssertionError('Unclassified new unconnected numeric '+str(fid))
            u['disposition']=status;c.execute('update usage_ledger set disposition=?,record_json=?where fact_id=?',(status,dump(u),fid))
            if status!='measurement_metadata_not_independent_predictor':
                q=dict(kind='v3_new_fact_review',fact_id=fid,disposition=status,source_receipt=f)
                c.execute('insert into review_queue values(?,?)',(nextq,dump(q)));nextq+=1
    s=read(OUT/'summary.json');s.update(additional_connected_numeric_facts=len(s['new_connected_fact_ids']),additional_main3e_nonmissing_cells=0,
      measurement_metadata_facts=c.execute('select count(*)from measurement_metadata').fetchone()[0],new_measurement_metadata_facts=len(meta),
      new_cycling_labels=0,cumulative_main3e_material_cells_added_since_v12=105,
      usage_counts=dict(collections.Counter(r[0]for r in c.execute('select disposition from usage_ledger'))))
    c.execute("update metadata set value_json=?where key='summary'",(dump(s),));c.commit()
    for name,only in [('all_fact_usage.csv',False),('unconnected_numeric_queue.csv',True)]:
        stream=io.StringIO(newline='');fields=['fact_id','doi','sample_name','material_stage','field_name','value','raw_value','unit','method','source_path','source_sha256','locator','disposition','task_receipts'];w=csv.DictWriter(stream,fieldnames=fields,lineterminator='\n');w.writeheader()
        for fid,rr,disp,uu in c.execute('select f.fact_id,f.record_json,u.disposition,u.record_json from facts f join usage_ledger u using(fact_id)order by f.fact_id'):
            f=json.loads(rr);u=json.loads(uu)
            if only and(f['value']is None or u['uses']):continue
            row={k:f.get(k)for k in fields};row.update(disposition=disp,task_receipts=len(u['uses']));w.writerow(row)
        (OUT/name).write_text(stream.getvalue(),encoding='utf-8-sig')
    for table in ['capacity_reports_v3','response_reports_v3','evidence_issues_v3']:
        write(OUT/(table+'.json'),[json.loads(r[0])for r in c.execute('select record_json from '+table)])
    write(OUT/'summary.json',s);write(OUT/'accounting_finalized.json',dict(new_measurement_metadata=len(meta),new_fact_review_items=nextq-4,new_fits=0,main3e_labels_changed=False))
    pointer=read(OUT/'entrypoint_snapshot.json');pointer['sha256']=sha(DB);write(OUT/'entrypoint_snapshot.json',pointer);write(ROOT/'data/current_training_ready.json',pointer)
    c.close();print(dump(dict(connected=s['numeric_facts_connected_to_training_inputs'],numeric=s['numeric_facts'],new_connected=s['additional_connected_numeric_facts'],rate=s['numeric_fact_connection_rate'])))

if __name__=='__main__':finalize()
