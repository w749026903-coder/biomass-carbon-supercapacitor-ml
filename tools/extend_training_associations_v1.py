"""Explicit second-pass typed properties and precursor transitions, before sealing."""
from pathlib import Path
import collections,csv,io,json,re,sqlite3,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.build_training_associations_v1 import OUT,DB,MAP,scope,measurement_group
from tools.train_model_v1 import read,write,sha
from data.literature_current import open_literature_database
from data.cycling_db import open_database

def extra_contract(field,unit):
    if any(x in field.lower()for x in ['uncertainty','error','raw_','as_printed','proxy','unspecified','_component_']):return False
    if field.startswith(('XPS_','EDS_','EDX_')):
        return unit in ['wt%','ratio','%withinC1s','% of C1s envelope','% of O1s envelope','% of N1s envelope','% of corresponding element envelope','%ofN1s','%withinN1s']
    if field.startswith('Raman_'):return unit in ['ratio','cm-1','cm^-1','nm']
    if field.startswith('XRD_'):return unit in ['nm','angstrom','degree','deg']
    if field.startswith('NMR31P_'):return unit=='mmol/g'
    if field.startswith('extrusion_'):return unit in ['rpm','degC','g/min']
    if 'yield'in field or 'carbon_efficiency'in field:return unit in ['%','wt%','% of dryrawprecursor','% of raw dry hemp mass','%carbon_to_lignin_plus_Nsource_mass']
    if any(x in field for x in ['pore','tplot','t_plot'])and not any(x in field for x in ['raw','as_printed']):return unit in ['%','% reported','angstrom','nm','ratio']
    if field.startswith('bulk_EA_')and 'ratio'in field:return unit in ['mass_ratio','ratio']
    return False

def block(field):
    if field.startswith('XRD_'):return 'XRD'
    if field.startswith('NMR31P_'):return 'NMR31P'
    if field.startswith('extrusion_'):return 'process'
    if 'yield'in field or 'carbon_efficiency'in field:return 'reported_yield'
    return measurement_group(field)

def extend():
    assert DB.exists()and not(OUT/'merge_manifest.json').exists()and not(OUT/'extension_history.json').exists()
    original_sha=sha(DB);initial=read(OUT/'summary.json');write(OUT/'phase1_summary.json',initial)
    c=sqlite3.connect(DB);c.row_factory=sqlite3.Row;c.execute('pragma foreign_keys=on')
    c.execute('create table lineage_pairs(pair_id text primary key,parent_material_key text references materials,child_material_key text references materials,record_json text)')
    dump=lambda v:json.dumps(v,ensure_ascii=False,allow_nan=False)
    def add_use(fid,task,rid,feature,role):c.execute('insert or ignore into fact_uses values(?,?,?,?,?)',(fid,task,rid,feature,role))
    with open_literature_database()as l,open_database()as d:
        mats={r['material_key']:r for r in l.materials()};facts={r['fact_id']:r for r in l.facts()};by=collections.defaultdict(list)
        for f in facts.values():by[f['material_key']].append(f)
        new_fields=collections.defaultdict(dict);annotations={};new_count=0
        for mk,m in mats.items():
            canon=l.canonical_material_features_v13(m['doi'],m['sample_name'])
            for f in by[mk]:
                if f['value']is None or not extra_contract(f['field_name'],f['unit']):continue
                selected=canon['values'].get(f['field_name']);p=canon['provenance'].get(f['field_name'],{});explicit=isinstance(p.get('decision'),dict)and'selected_value'in p['decision']
                if selected is None or f['value']!=selected:continue
                if any(t in f['review_status']for t in ['ambiguous','conflict'])and not explicit:continue
                field=f['field_name']+'__unit_'+re.sub(r'[^A-Za-z0-9]+','_',f['unit']).strip('_')
                annotations[field]=dict(original_field=f['field_name'],unit=f['unit'],method=f['method'],measurement_group=block(f['field_name']))
                new_fields[mk][field]=selected
                old=c.execute('select fact_ids_json from selected_features where material_key=?and field=?',(mk,field)).fetchone()
                if old:
                    ids=json.loads(old[0]);ids.append(f['fact_id']);c.execute('update selected_features set fact_ids_json=?where material_key=?and field=?',(dump(sorted(set(ids))),mk,field))
                else:c.execute('insert into selected_features values(?,?,?,?)',(mk,field,selected,dump([f['fact_id']])));new_count+=1
        allff=collections.defaultdict(dict);ids=collections.defaultdict(dict)
        for r in c.execute('select *from selected_features'):allff[r['material_key']][r['field']]=r['value'];ids[r['material_key']][r['field']]=json.loads(r['fact_ids_json'])
        cyclic={r['endpoint_id']:r for r in d.fetch('all_review').rows};blocked=collections.defaultdict(set)
        for eid,fs in d.freezes_v21.items():
            if 'Raman_ID_IG'in fs:blocked[eid].add('Raman')
            if 'N_at_pct'in fs:blocked[eid].add('XPS_N')
        for conf in d.feature_conflicts_v24():
            for eid,r in cyclic.items():
                if r.get('material_key_v11')==conf['material_key']:blocked[eid].update(['XPS_N','XPS_O'])
        def forbidden(eid,field):
            return any(field.startswith(b)or(b=='XPS_N'and field.startswith('XPS_C_to_N'))for b in blocked[eid])
        added_cycle_cells=0
        for r in c.execute('select task,row_id,material_key,record_json from inputs').fetchall():
            mk=r['material_key'];v=json.loads(r['record_json']);task=r['task'];changes=[]
            for f,value in new_fields.get(mk,{}).items():
                if task.startswith('cycle:'):
                    original=annotations[f]['original_field']
                    if forbidden(r['row_id'],original):continue
                    target='lib__'+f
                elif task.startswith('material:'):
                    if annotations[f]['measurement_group']==v['excluded_target_measurement_block']:continue
                    target=f
                else:target=f
                if target in v['features']:continue
                v['features'][target]=value;changes.append(target)
                for fid in ids[mk][f]:add_use(fid,task,r['row_id'],target,'input')
            if task=='cycle:reported_3e':added_cycle_cells+=len(changes)
            if changes:
                v['typed_contract_additions']=changes;c.execute('update inputs set record_json=?where task=?and row_id=?',(dump(v),task,r['row_id']))
        new_tasks=0
        for mk,m in mats.items():
            catalog=json.loads(c.execute('select record_json from materials where material_key=?',(mk,)).fetchone()[0]);catalog['features']=allff[mk]
            c.execute('update materials set record_json=?where material_key=?',(dump(catalog),mk))
            if scope(m)in ['reference_or_unresolved','stage_specific_material_only']:continue
            # Source-native process channels are useful predictors, never outcomes
            # of this material-property reconstruction task.
            prep={};prep_ev=[]
            for item in catalog['synthesis']:
                for s in item['stages']:
                    if s.get('stage')=='electrode_preparation':continue
                    for k in ['temperature_C','duration_h','heating_rate_C_min']:
                        if isinstance(s.get(k),(int,float))and not isinstance(s.get(k),bool):
                            key='process__'+s['stage']+'__'+k
                            if key not in prep:prep[key]=s[k];prep_ev.append(dict(field=key,path=item['source_path'],sha256=item['sha256'],locator=item['locator']))
            for target,value in new_fields.get(mk,{}).items():
                group=annotations[target]['measurement_group']
                if group=='process':continue
                xx={f:v for f,v in allff[mk].items()if block(annotations.get(f,{}).get('original_field',f))!=group};xx.update(prep)
                if not xx:continue
                task='material:'+scope(m)+':'+target;v=dict(row_id=mk,material_key=mk,sample_name=m['sample_name'],source_family=catalog['source_family'],features=xx,target=value,target_name=target,
                    excluded_target_measurement_block=group,process_evidence=prep_ev,conditions=dict(material_stage=m['material_stage'],material_task_scope=scope(m),target_unit=annotations[target]['unit']),
                    ready_for_training_inputs=True,ordinary_cycle_admission=False)
                c.execute('insert into inputs values(?,?,?,?)',(task,mk,mk,dump(v)));new_tasks+=1
                for f in xx:
                    for fid in ids[mk].get(f,[]):add_use(fid,task,mk,f,'input')
                for fid in ids[mk][target]:add_use(fid,task,mk,target,'target')
        # Resolve only explicit lineage edges to known exact registrations. Never
        # copy a precursor property into a final-material field.
        parents=collections.defaultdict(list);edge_records=[]
        byname={(m['doi'],m['sample_name']):mk for mk,m in mats.items()}
        for table, in l.connection.execute("select name from sqlite_master where type='table'and name like'material_lineage%'"):
            for r in l.connection.execute('select record_json from '+table):
                a=json.loads(r[0]);pm=a.get('parent_material_key');cm=a.get('child_material_key')
                if not(pm in mats and cm in mats):
                    pm=byname.get((a.get('doi'),a.get('parent')));cm=byname.get((a.get('doi'),a.get('child')))
                if pm in mats and cm in mats and mats[pm]['doi']==mats[cm]['doi']:
                    kind=a.get('kind','')
                    is_transition=kind not in ['own_P14_legal_factor_levels_and_raw_table_alias_kept','temperature_variant_not_an_independent_source','postcycle_not_pretest_feature_inheritance','lower_solid_loading_dope']
                    if is_transition:parents[cm].append(pm)
                    edge_records.append(dict(parent=pm,child=cm,table=table,record=a,physical_transition_eligible=is_transition))
                else:c.execute('insert into review_queue(record_json)values(?)',(dump(dict(kind='lineage_identity_unresolved',table=table,record=a)),))
        pairs=0
        for child,m in mats.items():
            if scope(m)not in ['ordinary_biomass_pretest','native_residue_separate','composite_or_mixed_separate']:continue
            if 'BET_surface_area_m2_g'not in allff[child]:continue
            ancestors=[];todo=[(p,[p,child])for p in parents[child]];seen=set()
            while todo:
                parent,path=todo.pop()
                if parent in seen or len(path)>6:continue
                seen.add(parent);ancestors.append((parent,path));todo.extend((p,[p]+path)for p in parents[parent]if p not in path)
            for parent,path in ancestors:
                if any(t in mats[parent]['material_stage']for t in ['after_cycling','commercial','unresolved','unbound']):continue
                xx={'precursor__'+f:v for f,v in allff[parent].items()}
                if not xx:continue
                pair=parent+'->'+child;task='lineage:'+scope(m)+':final_BET_from_measured_precursor';catalog=json.loads(c.execute('select record_json from materials where material_key=?',(child,)).fetchone()[0])
                v=dict(row_id=pair,material_key=child,sample_name=m['sample_name'],source_family=catalog['source_family'],features=xx,target=allff[child]['BET_surface_area_m2_g'],target_name='final_BET_surface_area_m2_g',
                    conditions=dict(parent_stage=mats[parent]['material_stage'],child_stage=m['material_stage']),lineage_path=path,ready_for_training_inputs=True,not_final_feature_inheritance=True)
                c.execute('insert into inputs values(?,?,?,?)',(task,pair,child,dump(v)));c.execute('insert into lineage_pairs values(?,?,?,?)',(pair,parent,child,dump(v)));pairs+=1
                for f in allff[parent]:
                    for fid in ids[parent][f]:add_use(fid,task,pair,'precursor__'+f,'input')
                for fid in ids[child]['BET_surface_area_m2_g']:add_use(fid,task,pair,'final_BET_surface_area_m2_g','target')
        uses=collections.defaultdict(list)
        for r in c.execute('select *from fact_uses'):uses[r['fact_id']].append(dict(task=r['task'],row_id=r['row_id'],feature=r['feature'],role=r['role']))
        for r in c.execute('select *from usage_ledger').fetchall():
            v=json.loads(r['record_json']);v['uses']=uses[r['fact_id']]
            if v['uses']:v['disposition']='connected_to_training_inputs'
            c.execute('update usage_ledger set disposition=?,record_json=?where fact_id=?',(v['disposition'],dump(v),r['fact_id']))
        summary=read(OUT/'summary.json');summary.update(numeric_facts_connected_to_training_inputs=len({fid for fid,receipts in uses.items() if receipts and facts[fid]['value']is not None}),
            typed_additional_selected_features=new_count,additional_main3e_typed_cells=added_cycle_cells,new_main3e_nonmissing_feature_cells=initial['new_main3e_nonmissing_feature_cells']+added_cycle_cells,
            explicit_lineage_edges=len(edge_records),prepared_lineage_pairs=pairs,new_model_fits=0,
            usage_counts=dict(collections.Counter(r[0]for r in c.execute('select disposition from usage_ledger'))))
        summary['numeric_fact_connection_rate']=summary['numeric_facts_connected_to_training_inputs']/4469
        counts={}
        for task, in c.execute('select distinct task from inputs'):
            rs=[json.loads(r[0])for r in c.execute('select record_json from inputs where task=?',(task,))];groups={r['source_family']for r in rs}
            counts[task]=dict(rows=len(rs),source_families=len(groups),source_holdout_validation_possible=len(groups)>=2)
        summary['task_counts']=counts;c.execute("update metadata set value_json=?where key='summary'",(dump(summary),));c.commit();c.close()
        write(OUT/'summary.json',summary);write(OUT/'typed_feature_contract.json',annotations);write(OUT/'explicit_lineage_edges.json',edge_records)
        write(OUT/'extension_history.json',dict(phase1_database_sha256=original_sha,phase1_connected_numeric=initial['numeric_facts_connected_to_training_inputs'],new_selected_features=new_count,lineage_pairs=pairs,
            unchanged_original_fact_rows=True,training_or_estimator_fits=0,scope='Additional typed predictors/targets with explicit units; target measurement block excluded; source/phase lineage separately labeled.'))
    c=sqlite3.connect(DB)
    for task in ['cycle:reported_3e','cycle:reported_2e','capacity:3e_reported','capacity:3e_with_graph','capacity:2e_device']:
        rs=[json.loads(r[0])for r in c.execute('select record_json from inputs where task=?order by row_id',(task,))];fields=sorted({f for r in rs for f in r['features']});b=io.StringIO(newline='');w=csv.writer(b,lineterminator='\n');w.writerow(['row_id','source_family','target']+fields)
        for r in rs:w.writerow([r['row_id'],r['source_family'],r['target']]+[r['features'].get(f)for f in fields])
        (OUT/(task.replace(':','_')+'.csv')).write_text(b.getvalue(),encoding='utf-8-sig',newline='')
    c.close();print(json.dumps({k:v for k,v in summary.items()if k not in ['task_counts','source_databases','usage_counts']},ensure_ascii=False))

if __name__=='__main__':extend()
