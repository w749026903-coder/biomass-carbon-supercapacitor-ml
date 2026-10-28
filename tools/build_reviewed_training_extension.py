"""Build one explicitly reviewed, append-only input extension from a source spec.

This is not an automatic paper extractor. The spec carries curated sample-stage
bindings, original evidence and held fields. Sealed releases cannot be rebuilt.
"""
from pathlib import Path
import collections,copy,hashlib,json,math,sqlite3,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from data.training_store import TrainingStore
from tools.extract_lignin_cf_v4 import read,write,dump,sha

def build(out):
    out=Path(out).resolve();assert ROOT in out.parents
    spec=read(out/'reviewed_extraction_spec.json');base=ROOT/spec['parent_directory'];route=read(base/'entrypoint_snapshot.json');db=out/spec['database_file']
    assert not db.exists()and not(out/'merge_manifest.json').exists()
    assert len({s['doi']for s in spec['sources']})==len(spec['sources'])
    assert len({m['material_key']for m in spec['materials']})==len(spec['materials'])
    for m in spec['materials']:
        assert len({f['field_name']for f in m['facts']})==len(m['facts'])
        for f in m['facts']:
            assert f['value']is None or isinstance(f['value'],(int,float))and not isinstance(f['value'],bool)and math.isfinite(f['value'])
    pm=read(base/'merge_manifest.json')
    for f in pm['outputs']:assert sha(ROOT/f['path'])==f['sha256'],f['path']
    for src in spec['sources']:assert sha(ROOT/src['path'])==src['sha256']
    with TrainingStore(base/route['database_file'],route['sha256'])as old:
        c=sqlite3.connect(db);c.row_factory=sqlite3.Row;c.execute('pragma foreign_keys=on')
        for r in old.connection.execute('select sql from main.sqlite_master where type="table"and name!="metadata"'):c.execute(r[0])
        c.execute('create table metadata(key text primary key,value_json text)')
        c.execute('create table if not exists source_author_claims_v7(claim_id text primary key,record_json text)')
        bysrc={s['doi']:s for s in spec['sources']};mats={};facts=[];ids=collections.defaultdict(dict);selected=collections.defaultdict(dict);changes=[];caps=[];responses=[]
        for s in spec['sources']:
            assert not old.connection.execute('select 1 from sources where doi=?',(s['doi'],)).fetchone()
            c.execute('insert into sources values(?,?)',(s['doi'],dump(s|dict(full_source_review_complete=False))))
            c.execute('insert into source_receipts_v3 values(?,?)',(s['path'],s['sha256']))
        fid=old.connection.execute('select max(fact_id)from facts').fetchone()[0]+1
        for ms in spec['materials']:
            m={k:copy.deepcopy(v)for k,v in ms.items()if k!='facts'};mk=m['material_key'];mats[mk]=m;c.execute('insert into materials values(?,?,?)',(mk,m['doi'],dump(m)))
            for supplied in ms['facts']:
                src=bysrc[m['doi']];f=copy.deepcopy(supplied)|dict(fact_id=fid,material_key=mk,doi=m['doi'],sample_name=m['sample_name'],material_stage=m['material_stage'],source_path=src['path'],source_sha256=src['sha256'],training_eligible=0)
                f.setdefault('raw_value',str(f['value'])if f['value']is not None else'not_reported');f.setdefault('selected_for_this_purpose',f['value']is not None);f.setdefault('method','author own material/method; unresolved algorithm not guessed')
                c.execute('insert into facts values(?,?,?,?)',(fid,mk,int(f['value']is not None),dump(f)));facts.append(f)
                if f['selected_for_this_purpose']and f['value']is not None:selected[mk][f['field_name']]=f['value'];ids[mk][f['field_name']]=fid
                elif f.get('disposition')=='measurement_metadata_not_independent_predictor':c.execute('insert into measurement_metadata values(?,?,?)',(fid,mk,dump(f)))
                elif f['value']is not None:c.execute('insert into held_features values(?,?,?)',(mk,f['field_name'],dump(f)))
                fid+=1
            m['features']=selected[mk];c.execute('update materials set record_json=?where material_key=?',(dump(m),mk))
        for mk,fields in selected.items():
            for f,v in fields.items():c.execute('insert into selected_features values(?,?,?,?)',(mk,f,v,dump([ids[mk][f]])))
        def use(fid,task,rid,field,role):c.execute('insert into fact_uses values(?,?,?,?,?)',(fid,task,rid,field,role))
        def add_input(task,row):
            c.execute('insert into inputs values(?,?,?,?)',(task,row['row_id'],row['material_key'],dump(row)))
            for f in row['features']:
                if f in ids[row['material_key']]:use(ids[row['material_key']][f],task,row['row_id'],f,'input')
            target=row['target_name']
            if target in ids[row['material_key']]:use(ids[row['material_key']][target],task,row['row_id'],target,'target')
        def change(table,key,a,b,reason,source):
            h=lambda text:hashlib.sha256(text.encode()).hexdigest();v=dict(table=table,key=key,before_sha256=h(a),after_sha256=h(b),before_record=json.loads(a),after_record=json.loads(b),reason=reason,source_path=source['path'],source_sha256=source['sha256'])
            c.execute('insert into overlay_changes values(?,?)',(spec['version']+':'+table+':'+hashlib.sha256(dump(key).encode()).hexdigest()[:20],dump(v)));changes.append(v)
        added=attested=0;bridges=[]
        for link in spec['cycle_links']:
            eid,mk=link['endpoint_id'],link['material_key'];m=mats[mk];src=bysrc[m['doi']];a=old.connection.execute('select record_json from cycle_records where endpoint_id=?',(eid,)).fetchone()[0];rr=json.loads(a)
            assert rr['sample_name']==m['sample_name']and rr['source_group']=='doi:'+m['doi']
            assert not old.connection.execute('select 1 from cycle_material_links where endpoint_id=?',(eid,)).fetchone()
            c.execute('insert into cycle_records values(?,?)',(eid,a));change('cycle_records',[eid],a,a,'Identical physical FK passthrough; no profile/label change',src)
            c.execute('insert into cycle_material_links values(?,?,?)',(eid,mk,dump(link|dict(source_path=src['path'],source_sha256=src['sha256'],new_admission=False))))
            for r in old.connection.execute('select *from inputs where row_id=?and task like "cycle:%"',(eid,)):
                b=json.loads(r['record_json']);b['material_key']=mk;new=[];same=[];receipts=[]
                for field,v in selected[mk].items():
                    name=spec.get('main_field_aliases',{}).get(field,field)
                    if b['features'].get(name)is not None:assert b['features'][name]==v,(eid,name,b['features'][name],v);same.append(name)
                    else:b['features'][name]=v;new.append(name)
                    receipts.append(dict(fact_id=ids[mk][field],field=name))
                b['current_material_evidence']=dict(release=spec['version'],added_nonmissing_fields=new,existing_values_attested=same,receipts=receipts,stage_binding=link['status'])
                after=dump(b);c.execute('insert into inputs values(?,?,?,?)',(r['task'],eid,mk,after))
                for x in receipts:use(x['fact_id'],r['task'],eid,x['field'],'input')
                change('inputs',[r['task'],eid],r['record_json'],after,'Own-source feature bridge; target/conditions/all old nonempty values preserved',src)
                if r['task']=='cycle:reported_3e':added+=len(new);attested+=len(same);bridges.append(dict(endpoint_id=eid,sample_name=m['sample_name'],doi=m['doi'],added_nonmissing_fields=new,existing_values_attested=same,target=b['target']))
        def block(field):
            if field in spec['measurement_blocks']:return spec['measurement_blocks'][field]
            if any(x in field for x in ['pore','BET_']):return'adsorption_porosity'
            if field.startswith('XPS_'):return'XPS'
            if field.startswith('Raman_'):return'Raman'
            if field.startswith('electrode_')or field.startswith('mass_loading_'):return'electrode_protocol'
            if 'contact_angle'in field:return'wettability'
            return'process'
        material_rows=0
        for ms in spec['materials']:
            m=mats[ms['material_key']];mk=m['material_key'];ff=selected[mk]
            for target in ms.get('property_targets',[]):
                assert target in ff
                row=dict(row_id=mk,material_key=mk,sample_name=m['sample_name'],source_family='doi:'+m['doi'],features={f:v for f,v in ff.items()if block(f)!=block(target)and block(f)!='electrode_protocol'},target=ff[target],target_name=target,conditions=dict(material_stage=m['material_stage']),excluded_target_measurement_block=block(target),ready_for_training_inputs=True,ordinary_cycle_admission=False)
                add_input('material:'+m['task_scope']+':'+target,row);material_rows+=1
        for obs in spec['capacities']+spec['responses']:
            m=mats[obs['material_key']];src=bysrc[m['doi']];oid=obs['observation_id'];rec=copy.deepcopy(obs)|dict(doi=m['doi'],sample_name=m['sample_name'],source_path=src['path'],source_sha256=src['sha256'],not_cycling_label=True)
            if obs in spec['capacities']:caps.append(rec);c.execute('insert into capacity_reports_v3 values(?,?,?)',(oid,m['material_key'],dump(rec)))
            else:responses.append(rec);c.execute('insert into response_reports_v3 values(?,?)',(oid,dump(rec)))
            for task in obs['tasks']:
                features={f:v for f,v in selected[m['material_key']].items()if not(obs['conditions'].get('configuration')=='2e_symmetric'and block(f)=='electrode_protocol')};features.update(obs['conditions'])
                add_input(task,dict(row_id=oid,material_key=m['material_key'],sample_name=m['sample_name'],source_family='doi:'+m['doi'],features=features,target=obs['value'],target_name=obs['target_name'],conditions=obs['conditions'],source_receipt=rec,ready_for_training_inputs=True,not_cycling_label=True))
        for x in spec['issues']:c.execute('insert into evidence_issues_v3 values(?,?)',(x['issue_id'],dump(x)))
        for x in spec['coverage']:c.execute('insert into extraction_coverage_v3 values(?,?,?)',(x['doi'],x['unit_id'],dump(x)))
        for x in spec['inspection_claims']:c.execute('insert into source_author_claims_v7 values(?,?)',(x['claim_id'],dump(x)))
        for f in facts:
            uses=[dict(task=r['task'],row_id=r['row_id'],feature=r['feature'],role=r['role'])for r in c.execute('select *from fact_uses where fact_id=?',(f['fact_id'],))]
            disposition='connected_to_training_inputs'if uses else'nonpoint_or_missing_retained'if f['value']is None else f.get('disposition','stage_specific_or_no_qualified_target')
            c.execute('insert into usage_ledger values(?,?,?)',(f['fact_id'],disposition,dump(dict(fact_id=f['fact_id'],fact=f,disposition=disposition,uses=uses,training_connected=bool(uses)))))
        before=copy.deepcopy(old.summary);s=copy.deepcopy(before)
        for k in list(s):
            if k.startswith('new_')and isinstance(s[k],(int,float)):s[k]=0
        counts=copy.deepcopy(s['task_counts'])
        for task, in c.execute('select distinct task from inputs where task not like "cycle:%"'):
            own=[json.loads(x[0])for x in c.execute('select record_json from inputs where task=?',(task,))];families={r['source_family']for r in old.rows(task)}if task in counts else set();families|={r['source_family']for r in own};counts[task]=dict(rows=counts.get(task,{}).get('rows',0)+len(own),source_families=len(families),source_holdout_validation_possible=len(families)>1)
        num=sum(f['value']is not None for f in facts);used=[r[0]for r in c.execute('select distinct fact_id from fact_uses')];meta=c.execute('select count(*)from measurement_metadata').fetchone()[0]
        s.update(version=spec['version'],total_facts=s['total_facts']+len(facts),numeric_facts=s['numeric_facts']+num,nonpoint_facts=s['nonpoint_facts']+len(facts)-num,material_registrations=s['material_registrations']+len(mats),reviewed_sources=s['reviewed_sources']+len(spec['sources']),numeric_facts_connected_to_training_inputs=s['numeric_facts_connected_to_training_inputs']+len(used),confirmed_cycle_material_links=s['confirmed_cycle_material_links']+len(spec['cycle_links']),main3e_material_links=s['main3e_material_links']+len(bridges),additional_main3e_nonmissing_cells=added,new_main3e_nonmissing_feature_cells=added,main3e_existing_cells_attested=attested,cumulative_main3e_material_cells_added_since_v12=s['cumulative_main3e_material_cells_added_since_v12']+added,new_sources=len(spec['sources']),new_material_registrations=len(mats),new_material_facts=len(facts),new_numeric_material_facts=num,additional_connected_numeric_facts=len(used),new_connected_fact_ids=used,new_capacity_reports=len(caps),new_ready_capacity_rows=len(caps),new_response_training_rows=len(responses),new_material_or_precursor_task_rows=material_rows,new_existing_cycle_material_links=len(spec['cycle_links']),new_input_representations=c.execute('select count(*)from inputs where task not like "cycle:%"').fetchone()[0],updated_existing_cycle_input_representations=c.execute('select count(*)from inputs where task like "cycle:%"').fetchone()[0],new_measurement_metadata_facts=meta,measurement_metadata_facts=s['measurement_metadata_facts']+meta,new_graph_captures=0,net_new_graph_conditions=0,task_counts=counts,parent_database_sha256=route['sha256'])
        s['numeric_fact_connection_rate']=s['numeric_facts_connected_to_training_inputs']/s['numeric_facts'];s['remaining_unconnected_numeric_facts']=s['numeric_facts']-s['numeric_facts_connected_to_training_inputs'];s['net_connection_change_from_v1']=s['numeric_facts_connected_to_training_inputs']-2823
        uc=collections.Counter(s['usage_counts']);uc.update(r[0]for r in c.execute('select disposition from usage_ledger'));s['usage_counts']=dict(uc)
        parents=[dict(path=(base/route['database_file']).relative_to(ROOT).as_posix(),sha256=route['sha256'])]+json.loads(old.connection.execute("select value_json from main.metadata where key='readonly_parent_chain'").fetchone()[0])
        tables=[r[0]for r in c.execute('select name from sqlite_master where type="table"and name!="metadata"')]
        for k,v in [('summary',s),('readonly_parent_chain',parents),('append_only_union_tables',tables),('override_primary_keys',dict(inputs=['task','row_id'],cycle_records=['endpoint_id']))]:c.execute('insert into metadata values(?,?)',(k,dump(v)))
        assert c.execute('pragma integrity_check').fetchone()[0]=='ok'and not c.execute('pragma foreign_key_check').fetchall();c.commit();c.close()
    for name,v in [('summary',s),('new_facts',facts),('new_materials',list(mats.values())),('new_capacity_reports',caps),('new_response_reports',responses),('overlay_changes',changes),('main_feature_changes',bridges),('summary_delta_audit',dict(before=before,after=s))]:write(out/(name+'.json'),v)
    write(out/'source_family_rules.json',read(base/'source_family_rules.json'));protected=read(base/'protected_inputs.json');protected.update({x['path']:x['sha256']for x in pm['outputs']});protected[(base/'merge_manifest.json').relative_to(ROOT).as_posix()]=sha(base/'merge_manifest.json');protected.update({x['path']:x['sha256']for x in spec['sources']});write(out/'protected_inputs.json',protected)
    route=dict(version=spec['version'],directory=out.relative_to(ROOT).as_posix(),database_file=db.name,sha256=sha(db),entry='data.training_latest',new_model_fits=0);write(out/'entrypoint_snapshot.json',route);write(ROOT/'data/current_training_latest.json',route)
    print(dump({k:s[k]for k in ['new_material_facts','new_numeric_material_facts','additional_connected_numeric_facts','additional_main3e_nonmissing_cells','main3e_existing_cells_attested','main3e_material_links']}))

if __name__=='__main__':build(ROOT/sys.argv[1])
