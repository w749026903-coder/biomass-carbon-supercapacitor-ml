"""Material-to-task integration over immutable literature v26/cycling v029. No fitting."""
from pathlib import Path
import collections,csv,io,json,math,re,sqlite3,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.train_model_v1 import read,write,sha
from data.literature_current import open_literature_database
from data.cycling_db import open_database
from tools.prepare_model_v12 import PROCESS
OUT=ROOT/'全量文献训练数据接入_v1_20261028';DB=OUT/'training_data_v1.sqlite'
ORDINARY={'final_biomass_carbon_before_test','final_sample_before_cycling','final_biomass_carbon_before_cycling',
 'final_biomass_carbon','carbonized_control','precarbonized_char_control_before_test','final_biomass_carbon_unactivated_control',
 'reheated_nonactivated_control','nonactivated_carbon_before_test','final_washed_biomass_carbon_before_test',
 'final_H2O2_oxidized_lignin_F127_carbon_before_test','final_non_gel_biomass_carbon','final_gel_assisted_biomass_carbon',
 'final_activated_biomass_carbon','activated_aerogel_before_test','unactivated_carbon_control','unactivated_control','final_carbon_zero_Cu_control'}
FROZEN_STAGE_WORDS=['after_cycling','unresolved','unbound','origin_unverified','prior_sample_overlap_pending','commercial','non_biomass']
MAP={'BET_surface_area_m2_g':'BET_m2_g','total_pore_volume_cm3_g':'total_pore_volume_cm3_g',
 'micropore_volume_cm3_g':'micropore_volume_cm3_g','mesopore_volume_cm3_g':'mesopore_volume_cm3_g',
 'micropore_surface_area_m2_g':'micropore_surface_area_m2_g','external_surface_area_m2_g':'external_surface_area_m2_g',
 'Raman_ID_IG':'Raman_ID_IG','XPS_N_at_pct':'XPS_N_atomic_pct_v15','XPS_O_at_pct':'XPS_O_atomic_pct_v15'}
PROFILE_NAMES=['reported_3e','reported_2e','reported_3e_residue_sensitivity','reported_3e_sensitivity','reported_3e_all_years','reported_2e_residue','reported_2e_approx','reported_2e_all_years']

def measurement_group(field):
    if field.startswith('XPS_'):return 'XPS'
    if field.startswith(('EDX_','EDS_')):return 'EDS'
    if field.startswith('bulk_EA'):return 'bulk_EA'
    if field.startswith('Raman_'):return 'Raman'
    if any(x in field.lower()for x in ['pore','bet_','tplot','t_plot','bjh','nldft','dft_','hk_','dh_']):return 'adsorption_porosity'
    return 'other:'+field

def field_unit_allowed(f,unit):
    if f=='Raman_ID_IG':return unit=='ratio'
    if re.fullmatch(r'XPS_[A-Z][a-z]?_at_pct',f):return unit in ['at%','at.%']
    if re.fullmatch(r'(?:EDX|EDS)_[A-Z][a-z]?_(?:at|wt)_pct',f):return unit in ['at%','at.%','wt%']
    if re.fullmatch(r'bulk_EA_[A-Z][a-z]?_wt_pct',f):return unit=='wt%'
    if any(x in f.lower()for x in ['uncert','raw','as_printed','component','envelope','fraction','ratio','yield','cost','efficiency','after','reported_pct']):return False
    return (unit in ['m2/g','cm3/g','nm'] and any(x in f.lower()for x in ['surface_area','pore_volume','pore_diameter','pore_area','tplot_','t_plot_','bjh_','dh_','hk_']))

def scope(m):
    s=m['material_stage']
    if any(t in s for t in FROZEN_STAGE_WORDS):return 'reference_or_unresolved'
    if s in ORDINARY:return 'ordinary_biomass_pretest'
    if s.startswith('final_') and any(t in s for t in ['residual','native_CaP','Zn_Ca']):return 'native_residue_separate'
    if s.startswith('final_') and any(t in s for t in ['composite','mixed_coffee','PEO']):return 'composite_or_mixed_separate'
    return 'stage_specific_material_only'

def build():
    assert not OUT.exists(),'New integration output required; no overwrite'
    lp=read(ROOT/'data/current_literature.json');cp=read(ROOT/'data/current_database.json')
    assert lp['sha256']=='c48964f31d2e7bcd9745785c1a21c51cb81000afd26d0e8ace73fd8de06ccef5'
    assert cp['sha256']=='092124bd9df25ae2d258cd46588ae27fde9371ace329cb3070ae3f48b4f7d279'
    with open_literature_database()as l,open_database()as d:
        facts=l.facts();materials={r['material_key']:r for r in l.materials()};tests={r['candidate_id']:r for r in l.tests()}
        rawcycles={r['endpoint_id']:r for r in d.fetch('all_review').rows};synth=collections.defaultdict(list)
        for r in l.synthesis():synth[r['material_key']].append(r)
        family=lambda doi:l.isolation_group(doi if doi.startswith(('doi:','family:'))else'doi:'+doi)
        sources=[dict(r)for r in l.connection.execute('select *from reviewed_sources')]
        bymat=collections.defaultdict(list)
        for f in facts:bymat[f['material_key']].append(f)
        assert len(facts)==4670 and sum(f['value']is not None for f in facts)==4469 and len(materials)==458 and len(rawcycles)==287
        selected={};selection_audit={};rejected={}
        for mk,m in materials.items():
            canon=l.canonical_material_features_v13(m['doi'],m['sample_name']);ff={};aa={}
            for f in bymat[mk]:
                key=(mk,f['field_name'])
                if f['value']is None:rejected[f['fact_id']]='nonpoint_or_missing';continue
                if not field_unit_allowed(f['field_name'],f['unit']):rejected[f['fact_id']]='method_unit_or_feature_role_not_in_model_contract';continue
                value=canon['values'].get(f['field_name']);provenance=canon['provenance'].get(f['field_name'],{})
                explicit=isinstance(provenance.get('decision'),dict) and 'selected_value'in provenance['decision']
                if value is None or f['value']!=value:rejected[f['fact_id']]='competing_or_nonselected_report';continue
                if any(word in f['review_status']for word in ['ambiguous','unknown_unit','conflict'])and not explicit:
                    rejected[f['fact_id']]='ambiguous_or_conflicting_method';continue
                if not math.isfinite(value) or value<0:rejected[f['fact_id']]='numeric_domain';continue
                ff[f['field_name']]=value;aa.setdefault(f['field_name'],[]).append(f['fact_id'])
            selected[mk]=ff;selection_audit[mk]=aa
        preparations={};preparation_evidence={}
        for mk,items in synth.items():
            prep={};ev=[];conflicts=set()
            for item in items:
                for stage in item['stages']:
                    name=stage.get('stage','unknown')
                    if name=='electrode_preparation'or any(t in name for t in ['device','same_material_2e']):continue
                    for key in ['temperature_C','duration_h','heating_rate_C_min']:
                        v=stage.get(key)
                        if isinstance(v,(float,int))and not isinstance(v,bool):
                            f='process__'+name+'__'+key
                            if f in conflicts:continue
                            if f in prep and prep[f]!=v:prep.pop(f);conflicts.add(f);continue
                            prep[f]=v;ev.append(dict(field=f,value=v,path=item['source_path'],sha256=item['sha256'],locator=item['locator'],stage=name))
            preparations[mk]=prep;preparation_evidence[mk]=ev
        # Identity receipts already present in the immutable versions, supplemented
        # only by unique exact designation + stage + matching own BET evidence.
        proposed=collections.defaultdict(list)
        def propose(eid,mk,basis):
            if eid in rawcycles and mk in materials:proposed[eid].append(dict(material_key=mk,basis=basis))
        def mat_by(doi,name):return [mk for mk,m in materials.items() if family(m['doi'])==family(doi) and m['sample_name']==name]
        for v in d.literature_links():
            if v['candidate_id']in tests:propose(v['endpoint_id'],tests[v['candidate_id']]['material_key'],'sealed cycling literature_links '+v['review_version'])
        for t in tests.values():
            if t['record'].get('legacy_endpoint_id'):propose(t['record']['legacy_endpoint_id'],t['material_key'],'sealed candidate explicit legacy_endpoint_id')
        for table, in l.connection.execute("select name from sqlite_master where type='table'and(name like'%identity_link%'or name like'cycle_links%')"):
            for row in l.connection.execute('select *from '+table):
                a=dict(row);v=json.loads(a.get('record_json','{}'));eid=v.get('existing_endpoint_id',v.get('endpoint_id',a.get('endpoint_id')));cid=v.get('candidate_id',a.get('candidate_id'))
                if cid in tests:propose(eid,tests[cid]['material_key'],'sealed '+table+' candidate identity')
                if v.get('doi')and(v.get('sample')or v.get('sample_name')):
                    for mk in mat_by(v['doi'],v.get('sample',v.get('sample_name'))):propose(eid,mk,'sealed '+table+' explicit source/sample identity')
        exact_candidates=[]
        for eid,r in rawcycles.items():
            for mk,m in materials.items():
                if r.get('material_key_v11','').endswith(mk):propose(eid,mk,'existing cycling material_key includes exact literature material_key')
            matches=mat_by(r['source_group'],r.get('sample_name'))
            if len(matches)==1:
                mk=matches[0];good=scope(materials[mk])in ['ordinary_biomass_pretest','native_residue_separate','composite_or_mixed_separate']
                corroborated=r.get('BET_m2_g')is not None and r['BET_m2_g']==selected[mk].get('BET_surface_area_m2_g')
                if good and corroborated:propose(eid,mk,'unique exact same-source sample, pretest stage, and own selected BET corroboration')
                else:exact_candidates.append(dict(endpoint_id=eid,material_key=mk,status='identity_candidate_not_approved',reason='Exact name/source without safe stage and matching own BET; needs individual evidence review'))
        links={};link_audit=[]
        for eid,v in proposed.items():
            candidates={x['material_key'] for x in v if family(materials[x['material_key']]['doi'])==family(rawcycles[eid]['source_group'])}
            if len(candidates)==1:
                mk=next(iter(candidates));links[eid]=mk;link_audit.append(dict(endpoint_id=eid,material_key=mk,status='confirmed_identity_not_new_admission',receipts=v))
            else:exact_candidates.append(dict(endpoint_id=eid,status='source_or_material_identity_conflict',receipts=v))
        profiles={name:d.fetch(name).rows for name in PROFILE_NAMES};memberships=collections.defaultdict(list)
        for name,rs in profiles.items():
            for r in rs:memberships[r['endpoint_id']].append(name)
        frozen=collections.defaultdict(set)
        for eid,fs in d.freezes_v21.items():
            for f in fs:
                for lib,cyc in MAP.items():
                    if f==cyc or(f=='N_at_pct'and lib=='XPS_N_at_pct')or(f=='O_at_pct'and lib=='XPS_O_at_pct'):frozen[eid].add(lib)
                if f=='C_at_pct':frozen[eid].add('XPS_C_at_pct')
        for item in d.feature_conflicts_v24():
            for eid,r in rawcycles.items():
                if r.get('material_key_v11')==item['material_key']:frozen[eid].update(['XPS_N_at_pct','XPS_O_at_pct'])
        OUT.mkdir();c=sqlite3.connect(DB);c.execute('pragma foreign_keys=on')
        c.executescript('''create table sources(doi text primary key,record_json text not null);
        create table materials(material_key text primary key,doi text references sources,record_json text not null);
        create table facts(fact_id integer primary key,material_key text references materials,numeric integer,record_json text not null);
        create table selected_features(material_key text references materials,field text,value real,fact_ids_json text,primary key(material_key,field));
        create table cycle_records(endpoint_id text primary key,record_json text not null);
        create table cycle_material_links(endpoint_id text primary key references cycle_records,material_key text references materials,record_json text);
        create table candidates(candidate_id text primary key,material_key text references materials,record_json text);
        create table inputs(task text,row_id text,material_key text references materials,record_json text not null,primary key(task,row_id));
        create table fact_uses(fact_id integer references facts,task text,row_id text,feature text,role text,primary key(fact_id,task,row_id,feature,role),foreign key(task,row_id)references inputs);
        create table usage_ledger(fact_id integer primary key references facts,disposition text,record_json text);
        create table review_queue(queue_id integer primary key,record_json text);
        create table metadata(key text primary key,value_json text);''')
        def ins(table,values):
            keys=list(values);c.execute('insert into '+table+'('+','.join(keys)+')values('+','.join('?'for k in keys)+')',list(values.values()))
        dump=lambda v:json.dumps(v,ensure_ascii=False,allow_nan=False)
        for r in sources:ins('sources',dict(doi=r['doi'],record_json=dump(r)))
        for mk,m in materials.items():
            ins('materials',dict(material_key=mk,doi=m['doi'],record_json=dump(dict(m,source_family=family(m['doi']),task_scope=scope(m),features=selected[mk],synthesis=synth[mk]))))
        for f in facts:ins('facts',dict(fact_id=f['fact_id'],material_key=f['material_key'],numeric=int(f['value']is not None),record_json=dump(f)))
        for mk,ff in selected.items():
            for f,v in ff.items():ins('selected_features',dict(material_key=mk,field=f,value=v,fact_ids_json=dump(selection_audit[mk][f])))
        for eid,r in rawcycles.items():ins('cycle_records',dict(endpoint_id=eid,record_json=dump(dict(r,source_family=family(r['source_group']),current_profiles=memberships[eid]))))
        for r in link_audit:ins('cycle_material_links',dict(endpoint_id=r['endpoint_id'],material_key=r['material_key'],record_json=dump(r)))
        for cid,t in tests.items():
            linked=[r['endpoint_id']for r in d.literature_links()if r['candidate_id']==cid]
            if t['record'].get('legacy_endpoint_id'):linked.append(t['record']['legacy_endpoint_id'])
            ins('candidates',dict(candidate_id=cid,material_key=t['material_key'],record_json=dump(dict(t,existing_endpoint_ids=sorted(set(linked)),new_training_admission=False))))
        uses=collections.defaultdict(list);rows_by_task=collections.defaultdict(list);field_changes=[]
        def row(task,row_id,mk,record,refs):
            ins('inputs',dict(task=task,row_id=row_id,material_key=mk,record_json=dump(record)));rows_by_task[task].append(record)
            for f,role,ids in refs:
                for fid in ids:
                    ins('fact_uses',dict(fact_id=fid,task=task,row_id=row_id,feature=f,role=role));uses[fid].append(dict(task=task,row_id=row_id,feature=f,role=role))
        for profile,rs in profiles.items():
            matrix=d.method_specific_material_matrix(profile);base={eid:dict(zip(matrix['feature_names'],x))for eid,x in zip(matrix['endpoint_ids'],matrix['X'])}
            old_snapshot=read(ROOT/'模型v1.2_来源隔离再训练_20261028/input_snapshot.json')
            old_inputs={r['endpoint_id']:{f:r.get(f)for f in old_snapshot['features']}for r in old_snapshot['records']}
            for r in rs:
                eid=r['endpoint_id'];mk=links.get(eid);xx=dict(base[eid]);refs=[];decisions=[]
                xx.update({f:r.get(f)for f in PROCESS});xx.update(old_inputs.get(eid,{}))
                if mk and scope(materials[mk])not in ['reference_or_unresolved','stage_specific_material_only']:
                    for f,v in selected[mk].items():
                        target=MAP.get(f,'lib__'+f)
                        if f in frozen[eid]:decisions.append(dict(field=f,status='frozen_kept',value=v));continue
                        current=xx.get(target)
                        if current is not None and current!=v:
                            decisions.append(dict(field=f,status='current_vs_library_conflict_held',current=current,library=v));continue
                        xx[target]=v;refs.append((target,'input',selection_audit[mk][f]));status='new_nonmissing_feature'if current is None else'existing_value_with_fact_receipt'
                        decisions.append(dict(field=f,target=target,status=status,value=v,fact_ids=selection_audit[mk][f]))
                    field_changes.append(dict(profile=profile,endpoint_id=eid,decisions=decisions))
                    # Keep source-native stage names as explicit additional channels;
                    # do not recast a joint step or precursor step into a final one.
                    xx.update(preparations.get(mk,{}))
                rec=dict(row_id=eid,endpoint_id=eid,material_key=mk,sample_name=r['sample_name'],source_family=family(r['source_group']),features=xx,
                         target=r['retention_pct'],target_name='capacitance_retention_pct',conditions={f:r.get(f)for f in ['system','method','electrolyte','concentration_mol_L','cycle_count','reported_current_A_g','current_mass_basis','baseline_reference','baseline_cycle']},
                         feature_decisions=decisions,process_evidence=preparation_evidence.get(mk,[]),ready_for_training_inputs=True,new_admission=False)
                row('cycle:'+profile,eid,mk,rec,refs)
        # Existing reviewed purposes are reused, never promoted from raw reports.
        aux={'capacity:3e_reported':l.auxiliary_gcd('3e'),'capacity:3e_with_graph':l.expanded_graph_3e_inputs(),
             'capacity:2e_device':l.auxiliary_gcd('2e_device'),'capacity:3e_native_mineral':l.auxiliary_gcd('native_mineral_3e'),
             'capacity:2e_author_factor2':l.auxiliary_gcd('2e_author_factor2')}
        for task,rs in aux.items():
            for r in rs:
                mk=r['material_key'];ff=selected[mk];cond=r['conditions'];refs=[(f,'input',selection_audit[mk][f])for f in ff]
                rec=dict(row_id=r['observation_id'],material_key=mk,sample_name=materials[mk]['sample_name'],source_family=family(materials[mk]['doi']),
                    target=r.get('target_value',r['value']),target_name=r.get('target_name','author_capacitance_F_g'),features=dict(ff,
                        reported_current_A_g=r['current_A_g'],electrolyte=r['electrolyte'],concentration_mol_L=r['concentration_mol_L'],
                        voltage_lower_V=cond.get('voltage_lower_V'),voltage_upper_V=cond.get('voltage_upper_V'),reference_electrode=cond.get('reference_electrode')),
                    conditions=dict(cond,system=r['system'],method=r['method'],electrolyte=r['electrolyte'],concentration_mol_L=r['concentration_mol_L'],reported_current_A_g=r['current_A_g']),
                    original_report=dict(observation_id=r['observation_id'],path=r['source_path'],sha256=r['source_sha256'],locator=r['locator'],status=r['status']),
                    ready_for_training_inputs=True,not_cycling_label=True,source_reviewed_purpose=task)
                row(task,r['observation_id'],mk,rec,refs)
        # Property reconstruction tasks: hold out the whole measurement block of
        # the target to prevent learning a pore-area sum, XPS complement or Raman inverse.
        for mk,m in materials.items():
            if scope(m)not in ['ordinary_biomass_pretest','native_residue_separate','composite_or_mixed_separate']:continue
            ff=selected[mk];prep=preparations.get(mk,{});prep_evidence=preparation_evidence.get(mk,[])
            for target,v in ff.items():
                block=measurement_group(target);xx={f:value for f,value in ff.items()if measurement_group(f)!=block};xx.update(prep)
                if not xx:continue
                task='material:'+scope(m)+':'+target
                refs=[(f,'input',selection_audit[mk][f])for f in xx if f in ff]+[(target,'target',selection_audit[mk][target])]
                rec=dict(row_id=mk,material_key=mk,sample_name=m['sample_name'],source_family=family(m['doi']),features=xx,target=v,target_name=target,
                    excluded_target_measurement_block=block,process_evidence=prep_evidence,conditions=dict(material_stage=m['material_stage'],material_task_scope=scope(m)),ready_for_training_inputs=True,
                    ordinary_cycle_admission=False)
                row(task,mk,mk,rec,refs)
        for a in exact_candidates:ins('review_queue',dict(record_json=dump(a)))
        # Preserve every not-yet-admitted canonical endpoint and every candidate.
        for eid,r in rawcycles.items():
            if not memberships[eid]:ins('review_queue',dict(record_json=dump(dict(endpoint_id=eid,status='no_current_ready_profile',remaining=r.get('remaining_evidence_work',r.get('open_issues',[])),material_link=links.get(eid)))))
        for f in facts:
            fid=f['fact_id'];mk=f['material_key'];us=uses[fid]
            if us:status='connected_to_training_inputs'
            elif f['value']is None:status='nonpoint_or_missing_retained'
            elif fid in rejected:status=rejected[fid]
            elif scope(materials[mk])=='reference_or_unresolved':status='reference_or_identity_unresolved'
            elif scope(materials[mk])=='stage_specific_material_only':status='stage_specific_material_catalog'
            else:status='selected_fact_without_suitable_current_task'
            ins('usage_ledger',dict(fact_id=fid,disposition=status,record_json=dump(dict(fact_id=fid,material_key=mk,field=f['field_name'],numeric=f['value']is not None,
                    disposition=status,uses=us,missing_cycle_label_not_claimed_absent=True,source=f['source_path'],sha256=f['source_sha256'],locator=f['locator']))))
        counts={task:dict(rows=len(rs),source_families=len({r['source_family']for r in rs}))for task,rs in rows_by_task.items()}
        numericused=sum(f['value']is not None and bool(uses[f['fact_id']])for f in facts)
        main_changes=[x for x in field_changes if x['profile']=='reported_3e'];add=sum(x['status']=='new_nonmissing_feature'for r in main_changes for x in r['decisions'])
        main_mapped=sum(r['endpoint_id']in links for r in profiles['reported_3e'])
        summary=dict(total_facts=4670,numeric_facts=4469,nonpoint_facts=201,material_registrations=458,reviewed_sources=65,
            numeric_facts_connected_to_training_inputs=numericused,numeric_fact_connection_rate=numericused/4469,
            denominator='Distinct numeric material fact IDs in immutable v26; numerator unique IDs with feature/target receipts into the prepared tasks, not estimator use or independent sample counts.',
            confirmed_cycle_material_links=len(links),main3e_material_links=main_mapped,new_main3e_nonmissing_feature_cells=add,
            task_counts=counts,usage_counts=dict(collections.Counter(r[0]for r in c.execute('select disposition from usage_ledger'))),
            old_model_fits=560,new_model_fits=0,new_cycling_admissions=0,original_pending=37,
            unsealed_batch27_used=False,property_tasks_do_not_supply_missing_cycle_labels=True,
            ordinary3e_and_graph_tasks_nested=True,source_databases=dict(literature=lp,cycling=cp))
        ins('metadata',dict(key='summary',value_json=dump(summary)));c.commit();assert c.execute('pragma integrity_check').fetchone()[0]=='ok';assert not c.execute('pragma foreign_key_check').fetchall();c.close()
        write(OUT/'summary.json',summary);write(OUT/'field_connection_changes.json',field_changes);write(OUT/'cycle_identity_decisions.json',link_audit)
        write(OUT/'source_family_rules.json',d.source_family_rules());write(OUT/'candidate_identity_review_queue.json',exact_candidates)
        protect={}
        for ptr in [lp,cp]:
            folder=ROOT/ptr.get('directory',ptr.get('version_directory'));p=folder/ptr['database_file'];assert sha(p)==ptr['sha256'];protect[p.relative_to(ROOT).as_posix()]=ptr['sha256']
        for doc in l.connection.execute('select path,sha256 from source_documents'):protect[doc['path']]=doc['sha256']
        for p in (ROOT/'模型v1.2_来源隔离再训练_20261028').rglob('*'):
            if p.is_file():protect[p.relative_to(ROOT).as_posix()]=sha(p)
        write(OUT/'protected_inputs.json',protect)
    # Rectangular, immediately readable exports, with masks and source grouping.
    for task in ['cycle:reported_3e','cycle:reported_2e','capacity:3e_reported','capacity:3e_with_graph','capacity:2e_device']:
        rs=rows_by_task[task];fields=sorted({f for r in rs for f in r['features']});b=io.StringIO(newline='');w=csv.writer(b,lineterminator='\n');w.writerow(['row_id','source_family','target']+fields)
        for r in rs:w.writerow([r['row_id'],r['source_family'],r['target']]+[r['features'].get(f)for f in fields])
        (OUT/(task.replace(':','_')+'.csv')).write_text(b.getvalue(),encoding='utf-8-sig',newline='')
    print(json.dumps({k:v for k,v in summary.items()if k not in ['task_counts','source_databases']},ensure_ascii=False))

if __name__=='__main__':build()
