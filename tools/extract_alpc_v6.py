"""New ALPC extension over immutable v5; never rerun against a sealed output."""
from pathlib import Path
import collections, copy, hashlib, json, sqlite3, sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from data.training_store import open_training_datasets as open_parent
from tools.extract_lignin_cf_v4 import sha,read,write,dump
BASE=ROOT/'全量文献训练数据接入_v5_OPB主集关联_20261028'
OUT=ROOT/'全量文献训练数据接入_v6_ALPC主集与补充表_20261029'
DB=OUT/'training_extension_v6.sqlite'
DOI='10.1021/acssusresmgt.3c00028'
MAIN='三电极端点扩充_20261018/corpus/U024/main.pdf'
SI='文献扩充_大批补齐_20261018/sources/SUP_139/SI/rm3c00028_si_001.pdf'
EIDS=['candidate:TE029','candidate:TE030']
TABLE={'ALPC-900':[375,307,.202,.144,81.65,9.46,8.89],
       'ALPC-800':[718,757,.35,.382,80.23,11.23,8.54],
       'ALPC-700':[25,37,.019,.017,81.82,11.19,6.99]}
FIELDS=['BET_surface_area_m2_g','micropore_surface_area_m2_g','total_pore_volume_cm3_g','micropore_volume_cm3_g','EDX_C_atomic_pct','EDX_N_atomic_pct','EDX_O_atomic_pct']
HELD={('ALPC-800','micropore_surface_area_m2_g'),('ALPC-800','micropore_volume_cm3_g'),('ALPC-700','micropore_surface_area_m2_g')}

def block(f):
    if 'pore' in f or f.startswith('BET_'):return 'adsorption_porosity'
    if f.startswith('EDX_'):return 'EDX'
    if f.startswith('XPS_'):return 'XPS'
    if f.startswith('Raman_'):return 'Raman'
    if f.startswith('XRD_'):return 'XRD'
    if f.startswith('electrode_'):return 'electrode_protocol'
    return 'process'

def build():
    assert OUT.is_dir() and not DB.exists() and not(OUT/'merge_manifest.json').exists()
    receipts=read(OUT/'source_receipts.json');src={x['path']:x['sha256']for x in receipts}
    for p,h in src.items():assert sha(ROOT/p)==h
    parent_manifest=read(BASE/'merge_manifest.json')
    for x in parent_manifest['outputs']:assert sha(ROOT/x['path'])==x['sha256'],x['path']
    route=read(BASE/'entrypoint_snapshot.json')
    with open_parent(ROOT/route['directory']/route['database_file'],route['sha256'])as old:
        c=sqlite3.connect(DB);c.row_factory=sqlite3.Row;c.execute('pragma foreign_keys=on')
        for r in old.connection.execute('select sql from main.sqlite_master where type="table" and name!="metadata"'):c.execute(r[0])
        c.execute('create table metadata(key text primary key,value_json text)')
        for t,key in [('graph_rate_captures_v6','capture_id'),('secondary_comparisons_v6','comparison_id'),('DFT_reports_v6','report_id')]:c.execute('create table '+t+'('+key+' text primary key,record_json text)')
        c.execute('insert into sources values(?,?)',(DOI,dump(dict(doi=DOI,source_path=MAIN,sha256=src[MAIN],supporting_information=SI,full_source_review_complete=False))))
        for p,h in src.items():c.execute('insert into source_receipts_v3 values(?,?)',(p,h))
        facts=[];mats={};selected=collections.defaultdict(dict);ids=collections.defaultdict(dict);changes=[];caps=[];responses=[]
        fid=old.connection.execute('select max(fact_id) from facts').fetchone()[0]+1
        def fact(m,field,value,unit,locator,source=MAIN,select=True,**extra):
            nonlocal fid
            f=dict(fact_id=fid,material_key=m['material_key'],doi=DOI,sample_name=m['sample_name'],material_stage=m['material_stage'],field_name=field,value=value,raw_value=str(value)if value is not None else'not_reported',unit=unit,source_path=source,source_sha256=src[source],locator=locator,method=extra.pop('method','author declared own material/protocol'),selected_for_this_purpose=bool(select and value is not None),training_eligible=0,review_status='ALPC_method_stage_qualified_v6',**extra)
            c.execute('insert into facts values(?,?,?,?)',(fid,m['material_key'],int(value is not None),dump(f)));facts.append(f)
            if select and value is not None:selected[m['material_key']][field]=value;ids[m['material_key']][field]=fid
            fid+=1;return f
        for name,values in TABLE.items():
            mk='literature:v29_ALPC:'+name;m=dict(material_key=mk,doi=DOI,sample_name=name,material_stage='final_biomass_carbon_before_test',source_family='doi:'+DOI,task_scope='ordinary_biomass_pretest',features={},synthesis=[],full_source_review_complete=False)
            mats[name]=m;c.execute('insert into materials values(?,?,?)',(mk,DOI,dump(m)))
            for field,v,unit in zip(FIELDS,values,['m2/g','m2/g','cm3/g','cm3/g','at.%','at.%','at.%']):
                held=(name,field)in HELD
                f=fact(m,field,v,unit,'SI physicalp6 TableS1 row '+name,source=SI,select=not held,method='FESEM-EDX atomic explicit'if field.startswith('EDX_')else'Author SI table; micropore algorithm unspecified, not silently labeled DFT/t-plot',quality_issue='micropore_exceeds_corresponding_total'if held else None)
                if held:c.execute('insert into held_features values(?,?,?)',(mk,field,dump(dict(fact_id=f['fact_id'],value=v,reason='Own table micropore quantity exceeds corresponding own total; no correction guessed',source_path=SI))))
            fact(m,'Raman_ID_IG',.96 if name.endswith('700')else .97,'ratio','Main physicalp3 Fig1c and p5 Raman paragraph')
            for field,v in [('Raman_D_position_cm_inv',1357),('Raman_G_position_cm_inv',1591)]:fact(m,field,v,'cm-1','Main physicalp5 approximate common Raman positions, not sample-resolved',select=False,value_kind='coarse_series_approximate_metadata')
            recipe=[('raw_leaf_dry_temperature_C',80,'degC'),('raw_leaf_dry_duration_h',12,'h'),('NH4Cl_to_raw_leaf_mass_ratio',1,'mass_ratio'),('NH4Cl_mixing_duration_min',10,'min'),('NH4Cl_predry_temperature_C',80,'degC'),('NH4Cl_predry_duration_h',24,'h'),('KOH_preactivation_predry_temperature_C',80,'degC'),('KOH_preactivation_predry_duration_h',24,'h'),('activation_temperature_C',int(name[-3:]),'degC'),('activation_duration_h',2,'h'),('heating_rate_C_min',5,'degC/min'),('HCl_wash_mol_L',3,'mol/L'),('final_dry_temperature_C',90,'degC')]
            for field,v,unit in recipe:fact(m,field,v,unit,'Main physicalp3 synthesis; similar KOH predrying procedure; joint KOH/carbonization heat treatment',method='Shared explicitly stated procedure; no separate second carbonization step')
            fact(m,'KOH_to_raw_leaf_mass_ratio',None,'mass_ratio','Main physicalp3 "similar procedure" does not unambiguously specify ratio basis',select=False)
            fact(m,'final_dry_duration_h',None,'h','Main physicalp3 overnight; no invented numerical hours',select=False)
            for field,v,unit in [('electrode_active_mass_mg',1.2,'mg'),('electrode_coated_area_cm2',1,'cm2'),('electrode_dry_temperature_C',80,'degC'),('electrode_dry_duration_h',12,'h')]:fact(m,field,v,unit,'Main physicalp3 supercapacitor electrode method, not ORR ink',value_kind='author_approximate_temperature'if field=='electrode_dry_temperature_C'else'author_reported_or_explicit_geometry')
            m.update(features=selected[mk],synthesis=[dict(source_path=MAIN,sha256=src[MAIN],atmosphere='Ar',joint_activation_carbonization=True,temperature_C=int(name[-3:]),duration_h=2,heating_rate_C_min=5)])
            if name=='ALPC-800':
                for field,v in [('XPS_N_atomic_pct_v15',4.64),('XPS_O_atomic_pct_v15',7.44)]:fact(m,field,v,'at.%','Main physicalp6 XPS explicitly atomic; not TableS1 EDX')
                for field,v in [('XRD_002_2theta_degree',24.9),('XRD_100_2theta_degree',42.4)]:fact(m,field,v,'degree','Main physicalp5 XRD own ALPC800; no Bragg d002 silently calculated')
            m['features']=selected[mk];c.execute('update materials set record_json=?where material_key=?',(dump(m),mk))
        for mk,ff in selected.items():
            for f,v in ff.items():c.execute('insert into selected_features values(?,?,?,?)',(mk,f,v,dump([ids[mk][f]])))
        def use(f,task,rid,field,role):c.execute('insert into fact_uses values(?,?,?,?,?)',(f,task,rid,field,role))
        def add_input(task,row):
            c.execute('insert into inputs values(?,?,?,?)',(task,row['row_id'],row['material_key'],dump(row)))
            for f in row['features']:
                if f in ids[row['material_key']]:use(ids[row['material_key']][f],task,row['row_id'],f,'input')
            if row['target_name']in ids[row['material_key']]:use(ids[row['material_key']][row['target_name']],task,row['row_id'],row['target_name'],'target')
        def change(table,key,before,after,reason):
            h=lambda x:hashlib.sha256(x.encode()).hexdigest();v=dict(table=table,key=key,before_sha256=h(before),after_sha256=h(after),before_record=json.loads(before),after_record=json.loads(after),reason=reason,source_path=MAIN,source_sha256=src[MAIN],supporting_information=SI,supporting_sha256=src[SI])
            c.execute('insert into overlay_changes values(?,?)',('v6:'+table+':'+hashlib.sha256(dump(key).encode()).hexdigest()[:20],dump(v)));changes.append(v)
        added=attested=0
        for eid in EIDS:
            mk=mats['ALPC-800']['material_key'];before=old.connection.execute('select record_json from cycle_records where endpoint_id=?',(eid,)).fetchone()[0];r=json.loads(before)
            assert r['sample_name']=='ALPC-800'and r['source_group']=='doi:'+DOI
            c.execute('insert into cycle_records values(?,?)',(eid,before));change('cycle_records',[eid],before,before,'Identical physical FK passthrough; existing label/protocol/status unchanged')
            c.execute('insert into cycle_material_links values(?,?,?)',(eid,mk,dump(dict(endpoint_id=eid,material_key=mk,status='confirmed_own_sample_TableS1_and_main_Fig8c',source_path=SI,source_sha256=src[SI],new_admission=False))))
            for rr in old.connection.execute('select * from inputs where row_id=? and task like "cycle:%"',(eid,)):
                a=json.loads(rr['record_json']);b=copy.deepcopy(a);b['material_key']=mk;new=[];prev=[];receipt=[]
                for field,v in selected[mk].items():
                    field2='BET_m2_g'if field=='BET_surface_area_m2_g'else field if field in b['features']or field.startswith('EDX_')else'process__'+field
                    if b['features'].get(field2)is not None:assert b['features'][field2]==v,(field2,v);prev.append(field2)
                    else:b['features'][field2]=v;new.append(field2)
                    receipt.append(dict(fact_id=ids[mk][field],field=field2))
                b['v6_material_evidence']=dict(added_nonmissing_fields=new,existing_values_attested=prev,receipts=receipt,EDX_not_XPS=True,held_pore_fields=['micropore_surface_area_m2_g','micropore_volume_cm3_g'],same_joint_heating_step=True)
                after=dump(b);c.execute('insert into inputs values(?,?,?,?)',(rr['task'],eid,mk,after))
                for x in receipt:use(x['fact_id'],rr['task'],eid,x['field'],'input')
                change('inputs',[rr['task'],eid],rr['record_json'],after,'Own-material bridge and qualified features; preserve all prior nonempty values and target/conditions')
                if rr['task']=='cycle:reported_3e':added+=len(new);attested+=len(prev)
        # Same-measurement block withheld; electrode preparation cannot predict intrinsic properties.
        material_rows=0
        for name,m in mats.items():
            mk=m['material_key'];ff=selected[mk]
            for target in list(ff):
                if block(target)in ['process','electrode_protocol']:continue
                row=dict(row_id=mk,material_key=mk,sample_name=name,source_family='doi:'+DOI,features={f:v for f,v in ff.items()if block(f)!=block(target)and block(f)!='electrode_protocol'},target=ff[target],target_name=target,conditions=dict(material_stage=m['material_stage']),excluded_target_measurement_block=block(target),ready_for_training_inputs=True,ordinary_cycle_admission=False,provenance_release='ALPC_v6')
                add_input('material:ordinary_biomass_pretest:'+target,row);material_rows+=1
        def capacity(name,method,electrolyte,rate,value,role='author_reported',extra=None):
            m=mats[name];mk=m['material_key'];oid='v29_ALPC:'+name+':'+method+':'+electrolyte+':'+str(rate)
            cond=dict(configuration='3e',method=method,electrolyte=electrolyte,concentration_mol_L=.5,reference_electrode='Ag/AgCl',voltage_lower_V=-.2 if electrolyte=='H2SO4'else-.9,voltage_upper_V=1 if electrolyte=='H2SO4'else .9,current_mass_basis='author_reported_not_inferred')
            cond['reported_current_A_g'if method=='GCD'else'scan_rate_mV_s']=rate
            cap=dict(observation_id=oid,material_key=mk,doi=DOI,sample_name=name,value=value,unit='F/g',conditions=cond,source_path=MAIN,source_sha256=src[MAIN],locator='Main physicalp10 body and physicalp9 Fig7/8',role=role,ready_for_training_inputs=True,not_cycling_label=True,**(extra or{}));caps.append(cap);c.execute('insert into capacity_reports_v3 values(?,?,?)',(oid,mk,dump(cap)))
            row=dict(row_id=oid,material_key=mk,sample_name=name,source_family='doi:'+DOI,features={**selected[mk],**cond},target=value,target_name='specific_capacitance_F_g',conditions=cond,source_receipt=cap,ready_for_training_inputs=True,not_cycling_label=True)
            if method=='CV':add_input('capacity:ordinary_biomass:3e_CV_author',row)
            else:
                if role=='author_reported':add_input('capacity:3e_reported',row)
                add_input('capacity:3e_with_graph',row)
        graph=read(OUT/'graph_rate_captures.json')
        for x in graph['captures']:
            c.execute('insert into graph_rate_captures_v6 values(?,?)',(x['sample_name']+':'+str(x['current_A_g']),dump(x)))
            if x['current_A_g']==1:
                anchor={'ALPC-700':170,'ALPC-800':421,'ALPC-900':264}[x['sample_name']]
                assert x['readout_interval_F_g'][0]<=anchor<=x['readout_interval_F_g'][1]
                capacity(x['sample_name'],'GCD','H2SO4',1,anchor,extra=dict(graph_anchor_check=x))
            else:capacity(x['sample_name'],'GCD','H2SO4',x['current_A_g'],x['readout_F_g'],'bounded_graph_readout',dict(readout=x))
        capacity('ALPC-800','GCD','Na2SO4',1,255)
        for rate,value in [(5,369),(100,168)]:capacity('ALPC-800','CV','Na2SO4',rate,value)
        # Device formula is retained in its own namespace, no silent fourfold conversion.
        m=mats['ALPC-800'];oid='v29_ALPC:device:GCD:1';cond=dict(configuration='2e_symmetric',method='GCD',electrolyte='Na2SO4',concentration_mol_L=.5,reported_current_A_g=1,voltage_lower_V=0,voltage_upper_V=1.8,current_mass_basis='author_formula_m_active_not_unambiguously_total_or_single')
        cap=dict(observation_id=oid,material_key=m['material_key'],doi=DOI,sample_name='ALPC-800//ALPC-800',value=47,unit='F/g',conditions=cond,source_path=MAIN,source_sha256=src[MAIN],locator='Main physicalp4 eq4 and p10',ready_for_training_inputs=True,not_cycling_label=True,role='author_device_formula_separate');caps.append(cap);c.execute('insert into capacity_reports_v3 values(?,?,?)',(oid,m['material_key'],dump(cap)))
        add_input('capacity:2e_ALPC_author_formula',dict(row_id=oid,material_key=m['material_key'],sample_name=cap['sample_name'],source_family='doi:'+DOI,features={k:v for k,v in selected[m['material_key']].items()if block(k)!='electrode_protocol'}|cond,target=47,target_name='specific_capacitance_F_g',conditions=cond,source_receipt=cap,not_cycling_label=True,ready_for_training_inputs=True))
        # EIS is an output in its own task, not a predictor of an intrinsic material property.
        for name,v in [('ALPC-900',15.06),('ALPC-800',12.50),('ALPC-700',25.25)]:
            m=mats[name];rr=dict(observation_id='v29_ALPC:'+name+':Rct',sample_name=name,material_key=m['material_key'],doi=DOI,value=v,unit='ohm',field='Rct_author_ohm',source_path=MAIN,source_sha256=src[MAIN],locator='Main physicalp10 EIS Fig7f paragraph',electrolyte='H2SO4',concentration_mol_L=.5,method='EIS',ready_for_training_inputs=True);responses.append(rr);c.execute('insert into response_reports_v3 values(?,?)',(rr['observation_id'],dump(rr)))
            add_input('response:ordinary_biomass:3e_Rct_author_ohm',dict(row_id=rr['observation_id'],material_key=m['material_key'],sample_name=name,source_family='doi:'+DOI,features=selected[m['material_key']]|dict(electrolyte='H2SO4',concentration_mol_L=.5),target=v,target_name='Rct_author_ohm',conditions=dict(method='EIS',frequency_lower_Hz=.1,frequency_upper_Hz=1e6,amplitude_mV=5),source_receipt=rr,ready_for_training_inputs=True))
        # Report anomalies and out-of-task numerical observations without promoting them.
        held_reports=[dict(id='acid_CV_sequence',values=[634,587,519,459,423,396,375],unit='F/g',scan_sequence_text='100 to5mV/s',reason='Rate/value direction ambiguous; no one-to-one scan-rate mapping guessed'),dict(id='device_cycle',retention_pct=91,cycles=6000,current_reports_A_g=[1,10],selected_current_for_inspection=10,reason='MainFig8f/body10 vs abstract1; no new cycling admission'),dict(id='ORR_retention',current_retention_pct=70,duration_s=14000,reason='ORR current durability, not capacitance retention'),dict(id='acid_S5_alternate',specific_capacitance_F_g=409,selected_body_F_g=421,current_A_g=1,reason='SI comparison409 vs own body421;421 corroborated by Fig7e own anchor, alternate retained'),dict(id='device_energy_power',ED_Wh_kg=21.15,paired_PD_kW_kg=.45,second_ED_Wh_kg=1.35,second_PD_kW_kg=4.93,reason='Keep paired Ragone points; conclusion cross-pair not a single observation')]
        for rr in held_reports:c.execute('insert into response_reports_v3 values(?,?)',('v29_ALPC:inspection:'+rr['id'],dump(rr|dict(doi=DOI,ready_for_training_inputs=False,source_path=MAIN,source_sha256=src[MAIN]))))
        issues=[dict(issue_id='ALPC_micro_exceeds_total',held=[dict(sample=s,field=f,raw_value=TABLE[s][FIELDS.index(f)])for s,f in sorted(HELD)],decision='Retain original image/cells; no swapped columns or guessed correction; selected inputs masked.'),dict(issue_id='ALPC_EDX_XPS_methods',decision='EDX C/N/O atomic table and XPS N4.64/O7.44 atomic are different measurement channels, not interchangeable.'),dict(issue_id='ALPC_421_409',decision='Keep own body421 corroborated by ownFig7e anchor; SI comparison409 retained without declaring author correction.'),dict(issue_id='ALPC_CV_sequence',decision='Do not assign seven acidic CV values to reversed prose scan-rate sequence; graph/integration review remains.'),dict(issue_id='ALPC_recipe_KOH_ratio',decision='NH4Cl1:1 explicit; similar KOH procedure ratio/basis unresolved, left null.'),dict(issue_id='ALPC_device_current',decision='10A/g matchesFig8f/body/conclusion; abstract1 preserved as alternate; no new cycling admission.')]
        for x in issues:c.execute('insert into evidence_issues_v3 values(?,?)',(x['issue_id'],dump(x|dict(doi=DOI))))
        # Every SI table has a disposition, including computational and secondary literature rows.
        comp=read(OUT/'secondary_and_DFT_tables.json')
        for x in comp['secondary_rows']:c.execute('insert into secondary_comparisons_v6 values(?,?)',(x['comparison_id'],dump(x)))
        for x in comp['DFT_rows']:c.execute('insert into DFT_reports_v6 values(?,?)',(x['report_id'],dump(x)))
        for f in facts:
            uses=[dict(task=r['task'],row_id=r['row_id'],feature=r['feature'],role=r['role'])for r in c.execute('select * from fact_uses where fact_id=?',(f['fact_id'],))]
            status='connected_to_training_inputs'if uses else'nonpoint_or_missing_retained'if f['value']is None else'coarse_series_Raman_metadata_not_predictor'if f.get('value_kind')=='coarse_series_approximate_metadata'else'micropore_exceeds_total_held'
            c.execute('insert into usage_ledger values(?,?,?)',(f['fact_id'],status,dump(dict(fact_id=f['fact_id'],fact=f,disposition=status,uses=uses,training_connected=bool(uses)))))
            if 'metadata'in status:c.execute('insert into measurement_metadata values(?,?,?)',(f['fact_id'],f['material_key'],dump(f)))
        coverage=read(OUT/'extraction_coverage.json')
        for x in coverage:c.execute('insert into extraction_coverage_v3 values(?,?,?)',(DOI,x['unit_id'],dump(x)))
        s=copy.deepcopy(old.summary);before=copy.deepcopy(s)
        counts=copy.deepcopy(s['task_counts'])
        for task, in c.execute('select distinct task from inputs where task not like "cycle:%"'):
            own=[json.loads(x[0])for x in c.execute('select record_json from inputs where task=?',(task,))];families={x['source_family']for x in old.rows(task)}if task in counts else set();families.add('doi:'+DOI)
            counts[task]=dict(rows=counts.get(task,{}).get('rows',0)+len(own),source_families=len(families),source_holdout_validation_possible=len(families)>1)
        num=sum(f['value']is not None for f in facts);used=[x[0]for x in c.execute('select distinct fact_id from fact_uses')]
        # Release counters cannot inherit the preceding paper's incremental claims.
        for key in list(s):
            if key.startswith('new_')and isinstance(s[key],(int,float)):s[key]=0
        s.update(version='training_latest_v6_ALPC',denominator='Distinct numeric material facts across v26 and reviewed extensions; not unique experiments, full-paper utilization or fitted estimator use.',total_facts=s['total_facts']+len(facts),numeric_facts=s['numeric_facts']+num,nonpoint_facts=s['nonpoint_facts']+len(facts)-num,numeric_facts_connected_to_training_inputs=s['numeric_facts_connected_to_training_inputs']+len(used),material_registrations=s['material_registrations']+3,reviewed_sources=s['reviewed_sources']+1,confirmed_cycle_material_links=s['confirmed_cycle_material_links']+2,main3e_material_links=23,additional_main3e_nonmissing_cells=added,new_main3e_nonmissing_feature_cells=added,main3e_existing_cells_attested=attested,new_material_registrations=3,new_sources=1,new_material_facts=len(facts),new_numeric_material_facts=num,additional_connected_numeric_facts=len(used),new_connected_fact_ids=used,new_capacity_reports=len(caps),new_ready_capacity_rows=len(caps),new_material_or_precursor_task_rows=material_rows,new_response_training_rows=3,new_existing_cycle_material_links=2,new_measurement_metadata_facts=6,measurement_metadata_facts=before['measurement_metadata_facts']+6,updated_existing_cycle_input_representations=c.execute('select count(*) from inputs where task like "cycle:%"').fetchone()[0],new_input_representations=c.execute('select count(*) from inputs where task not like "cycle:%"').fetchone()[0],cumulative_main3e_material_cells_added_since_v12=before['cumulative_main3e_material_cells_added_since_v12']+added,task_counts=counts,parent_database_sha256=route['sha256'],storage_mode='readonly_explicit_derived_row_overlays',new_graph_captures=30,net_new_graph_conditions=27)
        s['numeric_fact_connection_rate']=s['numeric_facts_connected_to_training_inputs']/s['numeric_facts'];s['remaining_unconnected_numeric_facts']=s['numeric_facts']-s['numeric_facts_connected_to_training_inputs'];s['net_connection_change_from_v1']=s['numeric_facts_connected_to_training_inputs']-2823
        uc=collections.Counter(s['usage_counts']);uc.update(x[0]for x in c.execute('select disposition from usage_ledger'));s['usage_counts']=dict(uc)
        parents=[dict(path=(BASE/route['database_file']).relative_to(ROOT).as_posix(),sha256=route['sha256'])]+json.loads(old.connection.execute("select value_json from main.metadata where key='readonly_parent_chain'").fetchone()[0])
        tables=[x[0]for x in c.execute('select name from sqlite_master where type="table" and name!="metadata"')]
        for k,v in [('summary',s),('readonly_parent_chain',parents),('append_only_union_tables',tables),('override_primary_keys',dict(inputs=['task','row_id'],cycle_records=['endpoint_id']))]:c.execute('insert into metadata values(?,?)',(k,dump(v)))
        assert c.execute('pragma integrity_check').fetchone()[0]=='ok' and not c.execute('pragma foreign_key_check').fetchall()
        c.commit();c.close()
    for name,val in [('summary',s),('new_facts',facts),('new_materials',list(mats.values())),('new_capacity_reports',caps),('EIS_reports',responses),('overlay_changes',changes),('scientific_issues',issues),('inspection_reports',held_reports),('summary_delta_audit',dict(before=before,after=s))]:write(OUT/(name+'.json'),val)
    write(OUT/'source_family_rules.json',read(BASE/'source_family_rules.json'))
    protected=read(BASE/'protected_inputs.json');protected.update({x['path']:x['sha256']for x in parent_manifest['outputs']});protected[(BASE/'merge_manifest.json').relative_to(ROOT).as_posix()]=sha(BASE/'merge_manifest.json');protected.update(src);write(OUT/'protected_inputs.json',protected)
    route=dict(version=s['version'],directory=OUT.relative_to(ROOT).as_posix(),database_file=DB.name,sha256=sha(DB),entry='data.training_latest',new_model_fits=0)
    write(OUT/'entrypoint_snapshot.json',route);write(ROOT/'data/current_training_latest.json',route)
    print(dump({k:s[k]for k in ['new_material_facts','new_numeric_material_facts','additional_connected_numeric_facts','additional_main3e_nonmissing_cells','main3e_existing_cells_attested','new_capacity_reports','main3e_material_links']}))

if __name__=='__main__':build()
