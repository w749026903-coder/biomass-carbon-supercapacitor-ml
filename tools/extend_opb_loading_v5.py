"""Use the reported 1-2mg/cm2 protocol interval without inventing a midpoint."""
from pathlib import Path
import hashlib,json,sqlite3,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.extract_opb_main_v5 import OUT,DB,SOURCE,SOURCE_SHA,DOI,read,write,dump,sha

def extend():
    assert not(OUT/'merge_manifest.json').exists()and not(OUT/'loading_interval_review.json').exists()
    c=sqlite3.connect(DB);c.row_factory=sqlite3.Row;c.execute('pragma foreign_keys=on');fs=read(OUT/'new_facts.json');mats=read(OUT/'new_materials.json');nf=[];fids={};fid=c.execute('select max(fact_id)from facts').fetchone()[0]+1
    for m in mats:
        fids[m['material_key']]={}
        for field,v in [('electrode_active_loading_lower_mg_cm2',1),('electrode_active_loading_upper_mg_cm2',2)]:
            f=dict(fact_id=fid,material_key=m['material_key'],doi=DOI,sample_name=m['sample_name'],material_stage=m['material_stage'],field_name=field,value=v,raw_value='1-2 mg cm-2',unit='mg/cm2',method='Author common electrode protocol interval boundary, not a measured point or midpoint',source_path=SOURCE,source_sha256=SOURCE_SHA,locator='PDF physicalp7 §2.4 active loading interval',review_status='reported_interval_boundary_not_exact_mass_loading',selected_for_this_purpose=True,training_eligible=0,value_kind='protocol_interval_boundary',not_independent_experiment=True,usage_stage='electrode_preparation_not_intrinsic_characterization')
            fs.append(f);nf.append(f);fids[m['material_key']][field]=fid;c.execute('insert into facts values(?,?,?,?)',(fid,m['material_key'],1,dump(f)));c.execute('insert into selected_features values(?,?,?,?)',(m['material_key'],field,v,dump([fid])));m['features'][field]=v;fid+=1
        c.execute('update materials set record_json=?where material_key=?',(dump(m),m['material_key']))
    changed={}
    for row in c.execute('select *from inputs').fetchall():
        if row['task'].startswith('material:'):continue
        v=json.loads(row['record_json']);mk=row['material_key']
        for field,ffid in fids[mk].items():
            value=1 if'lower'in field else 2;v['features'][field]=value;c.execute('insert into fact_uses values(?,?,?,?,?)',(ffid,row['task'],row['row_id'],field,'input'))
            if row['task'].startswith('cycle:'):
                v['v5_material_evidence']['added_nonmissing_fields'].append(field);v['v5_material_evidence']['receipts'].append(dict(fact_id=ffid,field=field))
                v['v5_material_evidence']['loading_interval_semantics']='Common reported1-2mg/cm2; exact mass_loading_mg_cm2 remains unknown, no1.5 midpoint.'
        text=dump(v);c.execute('update inputs set record_json=?where task=?and row_id=?',(text,row['task'],row['row_id']));changed[row['task'],row['row_id']]=text
    records=[]
    for r in c.execute('select *from overlay_changes').fetchall():
        v=json.loads(r['record_json']);key=tuple(v['key'])
        if v['table']=='inputs'and key in changed:
            v['after_record']=json.loads(changed[key]);v['after_sha256']=hashlib.sha256(changed[key].encode()).hexdigest();v['loading_bounds_added_without_midpoint']=True;c.execute('update overlay_changes set record_json=?where change_id=?',(dump(v),r['change_id']))
        records.append(v)
    for f in nf:
        uses=[dict(task=r['task'],row_id=r['row_id'],feature=r['feature'],role=r['role'])for r in c.execute('select *from fact_uses where fact_id=?',(f['fact_id'],))];c.execute('insert into usage_ledger values(?,?,?)',(f['fact_id'],'connected_to_training_inputs',dump(dict(fact_id=f['fact_id'],disposition='connected_to_training_inputs',uses=uses,training_connected=True,fact=f))))
    s=read(OUT/'summary.json');s.update(total_facts=s['total_facts']+8,numeric_facts=s['numeric_facts']+8,numeric_facts_connected_to_training_inputs=s['numeric_facts_connected_to_training_inputs']+8,new_material_facts=114,new_numeric_material_facts=110,additional_connected_numeric_facts=104,additional_main3e_nonmissing_cells=60,new_connected_fact_ids=sorted(s['new_connected_fact_ids']+[f['fact_id']for f in nf]))
    s['numeric_fact_connection_rate']=s['numeric_facts_connected_to_training_inputs']/s['numeric_facts'];s['usage_counts']['connected_to_training_inputs']+=8
    c.execute('update metadata set value_json=?where key="summary"',(dump(s),));c.commit();c.close()
    for name,val in [('summary',s),('new_facts',fs),('new_materials',mats),('overlay_changes',records)]:write(OUT/(name+'.json'),val)
    write(OUT/'loading_interval_review.json',dict(original_report='1-2mg/cm2',exact_point_unknown=True,midpoint_not_invented=True,used_as_two_named_bounds=True,not_used_for_intrinsic_property_targets=True,source_path=SOURCE,sha256=SOURCE_SHA))
    p=read(OUT/'entrypoint_snapshot.json');p['sha256']=sha(DB);write(OUT/'entrypoint_snapshot.json',p);write(ROOT/'data/current_training_store.json',p)
    print('Added8 interval-bound receipts /8 main feature cells; exact mass-loading stays unknown.')

if __name__=='__main__':extend()
