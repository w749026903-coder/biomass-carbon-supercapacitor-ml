"""Append the explicit Figure1 argon-flow condition before sealing v4."""
from pathlib import Path
import collections,json,sqlite3,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.extract_lignin_cf_v4 import OUT,DB,read,write,sha,dump,DOI

def extend():
    assert not(OUT/'merge_manifest.json').exists()and not(OUT/'gas_flow_review.json').exists()
    image='文献扩充_大批补齐_20261018/sources/SUP_110/assets/gr1.jpg';h=sha(ROOT/image)
    c=sqlite3.connect(DB);c.row_factory=sqlite3.Row;c.execute('pragma foreign_keys=on')
    c.execute('insert into source_receipts_v3 values(?,?)',(image,h))
    mats=read(OUT/'new_materials.json');fs=read(OUT/'new_facts.json');fid=c.execute('select max(fact_id)from facts').fetchone()[0]+1;added=[];newids={}
    for m in mats:
        if'electrode'not in m['material_stage']:continue
        calc=m['features']['calcination_applied']==1;v=.5 if calc else None;field='calcination_Ar_flow_L_min'
        f=dict(fact_id=fid,material_key=m['material_key'],doi=DOI,sample_name=m['sample_name'],material_stage=m['material_stage'],field_name=field,value=v,raw_value='Ar 0,5l/min'if calc else'not_applied_not_zero',unit='L/min',method='Exact printed argon flow in own WCF Figure1; not inherited into separate lignin controls',source_path=image,source_sha256=h,locator='Main Figure1 calcination arrow Ar0,5l/min',review_status='own_v27B_figure_printed_process',selected_for_this_purpose=calc,training_eligible=0)
        c.execute('insert into facts values(?,?,?,?)',(fid,m['material_key'],int(calc),dump(f)));fs.append(f);added.append(f)
        if calc:
            c.execute('insert into selected_features values(?,?,?,?)',(m['material_key'],field,.5,dump([fid])));newids[m['material_key']]=fid;m['features'][field]=.5
            c.execute('update materials set record_json=?where material_key=?',(dump(m),m['material_key']))
        fid+=1
    for row in c.execute('select *from inputs').fetchall():
        v=json.loads(row['record_json']);mk=row['material_key'];field=None;source=mk
        if mk in newids:field='calcination_Ar_flow_L_min'
        elif v['ingredient_material_keys']and v['ingredient_material_keys'][0]in newids:source=v['ingredient_material_keys'][0];field='electrode__calcination_Ar_flow_L_min'
        if field:
            v['features'][field]=.5;c.execute('update inputs set record_json=?where task=?and row_id=?',(dump(v),row['task'],row['row_id']))
            c.execute('insert into fact_uses values(?,?,?,?,?)',(newids[source],row['task'],row['row_id'],field,'input'))
    for f in added:
        uses=[dict(task=r['task'],row_id=r['row_id'],feature=r['feature'],role=r['role'])for r in c.execute('select *from fact_uses where fact_id=?',(f['fact_id'],))];status='connected_to_training_inputs'if uses else'nonpoint_or_missing_retained'
        c.execute('insert into usage_ledger values(?,?,?)',(f['fact_id'],status,dump(dict(fact_id=f['fact_id'],disposition=status,uses=uses,training_connected=bool(uses),fact=f))))
    s=read(OUT/'summary.json');s.update(total_facts=s['total_facts']+10,numeric_facts=s['numeric_facts']+7,nonpoint_facts=s['nonpoint_facts']+3,numeric_facts_connected_to_training_inputs=s['numeric_facts_connected_to_training_inputs']+7,new_material_facts=140,new_numeric_material_facts=113,additional_connected_numeric_facts=109,new_connected_fact_ids=sorted(s['new_connected_fact_ids']+list(newids.values())))
    s['numeric_fact_connection_rate']=s['numeric_facts_connected_to_training_inputs']/s['numeric_facts'];s['remaining_unconnected_numeric_facts']=s['numeric_facts']-s['numeric_facts_connected_to_training_inputs']
    s['usage_counts']['connected_to_training_inputs']+=7;s['usage_counts']['nonpoint_or_missing_retained']+=3
    c.execute("update metadata set value_json=?where key='summary'",(dump(s),));c.commit();c.close()
    write(OUT/'summary.json',s);write(OUT/'new_facts.json',fs);write(OUT/'new_materials.json',mats);write(OUT/'gas_flow_review.json',dict(source_path=image,sha256=h,printed='Ar 0,5l/min',new_numeric_fields=7,not_applied_nulls=3,independent_lignin_control_inherited=False))
    for name in ['protected_inputs.json','source_receipts.json']:
        val=read(OUT/name);val[image]=h;write(OUT/name,val)
    pointer=read(OUT/'entrypoint_snapshot.json');pointer['sha256']=sha(DB);write(OUT/'entrypoint_snapshot.json',pointer);write(ROOT/'data/current_training_catalog.json',pointer)
    print('Added seven own Figure1 argon-flow values; three not-applied cells remain null.')

if __name__=='__main__':extend()
