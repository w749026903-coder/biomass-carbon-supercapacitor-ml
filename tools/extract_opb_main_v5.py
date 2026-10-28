"""Bridge four existing primary-cycle rows using own Table1 and preparation."""
from pathlib import Path
import collections,hashlib,json,sqlite3,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from data.training_catalog import open_training_datasets as open_v4
from tools.extract_lignin_cf_v4 import sha,read,write,dump
BASE=ROOT/'全量文献训练数据接入_v4_木质素碳布与凝胶_20261028'
OUT=ROOT/'全量文献训练数据接入_v5_OPB主集关联_20261028';DB=OUT/'training_extension_v5.sqlite'
DOI='10.1039/d4ta02115k';SOURCE='三电极端点扩充_20261018/corpus/U002/main.pdf'
SOURCE_SHA='91466159221eff1915c059b26cd7d1927ad00ce0c5f4121ff324882eace3d98e'
EIDS={'OPBNP':'candidate:TE021','OPB':'candidate:TE022','OPNP':'candidate:TE023','OPC':'candidate:TE024'}
TABLE={'OPC':[.374,.84,10.9,.053,.003,19.54],'OPB':[.378,.87,871.9,.36,.28,1.64],
       'OPNP':[.384,.93,1894.9,.83,.75,1.75],'OPBNP':[.392,.99,1774.8,.81,.69,1.82]}

def build():
    assert not OUT.exists(),'New version only; do not rebuild sealed outputs'
    parent_manifest=read(BASE/'merge_manifest.json')
    for r in parent_manifest['outputs']:assert sha(ROOT/r['path'])==r['sha256'],r['path']
    assert sha(ROOT/SOURCE)==SOURCE_SHA;OUT.mkdir()
    pointer=read(BASE/'entrypoint_snapshot.json')
    with open_v4(ROOT/pointer['directory']/pointer['database_file'],pointer['sha256'])as old:
        c=sqlite3.connect(DB);c.row_factory=sqlite3.Row;c.execute('pragma foreign_keys=on')
        # Empty schema only. Cross-parent FK targets for the four new links are
        # copied byte-for-byte as explicit identical passthroughs below.
        for r in old.connection.execute('select name,sql from main.sqlite_master where type="table"and name!="metadata"'):c.execute(r['sql'])
        c.execute('create table metadata(key text primary key,value_json text)')
        c.execute('create table overlay_changes(change_id text primary key,record_json text)')
        c.execute('create table field_methods_v5(field text primary key,record_json text)')
        c.execute('insert into sources values(?,?)',(DOI,dump(dict(doi=DOI,source_path=SOURCE,sha256=SOURCE_SHA,full_source_review_complete=False,document_version='accepted_manuscript_not_2018_template_cover'))))
        c.execute('insert into source_receipts_v3 values(?,?)',(SOURCE,SOURCE_SHA))
        facts=[];mats={};ids=collections.defaultdict(lambda:collections.defaultdict(list));selected=collections.defaultdict(dict);changes=[];newrows=[];caps=[];issues=[]
        nextid=old.connection.execute('select max(fact_id)from facts').fetchone()[0]+1
        def fact(m,field,value,unit,locator,select=True,**extra):
            nonlocal nextid
            f=dict(fact_id=nextid,material_key=m['material_key'],doi=DOI,sample_name=m['sample_name'],material_stage=m['material_stage'],field_name=field,value=value,
              raw_value=str(value),unit=unit,method=extra.pop('method','Own declared Table1/methods comparison protocol'),source_path=SOURCE,source_sha256=SOURCE_SHA,locator=locator,review_status='own_OPB_v5_method_stage_qualified',selected_for_this_purpose=select and value is not None,training_eligible=0,**extra)
            c.execute('insert into facts values(?,?,?,?)',(nextid,m['material_key'],int(value is not None),dump(f)));facts.append(f)
            if select and value is not None:selected[m['material_key']][field]=value;ids[m['material_key']][field].append(nextid)
            nextid+=1
        def change(table,key,before,after,reason,**extra):
            h=lambda x:hashlib.sha256(x.encode()).hexdigest();row=dict(table=table,key=key,before_sha256=h(before),after_sha256=h(after),reason=reason,before_record=json.loads(before),after_record=json.loads(after),source_path=SOURCE,source_sha256=SOURCE_SHA,**extra)
            rid='v5:'+table+':'+hashlib.sha256(dump(key).encode()).hexdigest()[:20];c.execute('insert into overlay_changes values(?,?)',(rid,dump(row)));changes.append(row)
        for name,values in TABLE.items():
            mk='literature:v28_OPB:'+name;m=dict(material_key=mk,doi=DOI,sample_name=name,material_stage='final_biomass_carbon_before_test',task_scope='ordinary_biomass_pretest',source_family='doi:'+DOI,features={},synthesis=[],full_source_review_complete=False)
            mats[name]=m;c.execute('insert into materials values(?,?,?)',(mk,DOI,dump(m)))
            for field,value,unit in zip(['XRD_d002_nm','Raman_ID_IG','BET_surface_area_m2_g','total_pore_volume_cm3_g','HK_micropore_volume_cm3_g','average_pore_diameter_nm'],values,['nm','ratio','m2/g','cm3/g','cm3/g','nm']):fact(m,field,value,unit,'PDF physicalp12 Table1 '+name,method='HK micropore volume'if field.startswith('HK_')else'Own Table1, original method/units retained')
            i=['OPC','OPB','OPNP','OPBNP'].index(name)
            for field,value in [('Raman_D_position_cm_inv',[1335,1334,1329,1327][i]),('Raman_G_position_cm_inv',[1598,1591,1585,1580][i])]:fact(m,field,value,'cm-1','PDF physicalp12 Raman paragraph '+name)
            # Absence of added dopant is not a claim that total elemental content
            # equals zero. Shared conditions are explicitly stated for controls.
            recipe=[('OP_powder_input_g',2,'g'),('diammonium_phosphate_input_g',1 if name in ['OPNP','OPBNP']else 0,'g'),('boric_acid_input_g',1 if name in ['OPB','OPBNP']else 0,'g'),('hydrothermal_water_mL',60,'mL'),('pre_hydrothermal_stir_h',4,'h'),('hydrothermal_temperature_C',180,'degC'),('hydrothermal_duration_h',12,'h'),('KOH_to_hydrothermal_product_mass_ratio',3,'mass_ratio'),('KOH_impregnation_water_mL',50,'mL'),('KOH_impregnation_stir_h',10,'h'),('KOH_predry_temperature_C',100,'degC'),('activation_temperature_C',600,'degC'),('activation_duration_h',3,'h'),('heating_rate_C_min',3,'degC/min'),('HCl_wash_mol_L',2,'mol/L'),('final_dry_temperature_C',80,'degC')]
            for field,value,unit in recipe:fact(m,field,value,unit,'PDF physicalp6-7 §2.2 shared synthesis and explicitly named control '+name,method='Joint calcination/KOH activation; products:KOH1:3, not raw-OP:KOH mass ratio')
            fact(m,'final_dry_duration_h',None,'h','PDF physicalp6 overnight drying',select=False,raw_qualifier='overnight_no_numeric_duration')
            m['features']=selected[mk];m['synthesis']=[dict(source_path=SOURCE,sha256=SOURCE_SHA,locator='PDF p6-7',stages=[dict(stage='hydrothermal',temperature_C=180,duration_h=12),dict(stage='joint_calcination_KOH_activation',temperature_C=600,duration_h=3,heating_rate_C_min=3,atmosphere='N2')])]
            c.execute('update materials set record_json=?where material_key=?',(dump(m),mk))
        # Literal XPS percentages: sequence is C/O/N/B/P, but atomic versus weight
        # percentage is not explicitly stated. Keep outside unified atom channels.
        for el,value in zip(['C','O','N','B','P'],[84.21,11.46,3.28,.90,.15]):fact(mats['OPBNP'],'XPS_'+el+'_reported_pct',value,'%basis_unspecified','PDF physicalp13-14 XPS elemental-content sequence C/O/N/B/P',select=False)
        fact(mats['OPBNP'],'BET_intro_alternate_report_m2_g',774.8,'m2/g','PDF physicalp5 introduction alternate; Table1/p13/abstract1774.8',select=False)
        for mk,ff in selected.items():
            for f,v in ff.items():c.execute('insert into selected_features values(?,?,?,?)',(mk,f,v,dump(ids[mk][f])))
        def put_use(fid,task,rid,field,role):c.execute('insert into fact_uses values(?,?,?,?,?)',(fid,task,rid,field,role))
        def target_field(field,old_features):
            if field=='BET_surface_area_m2_g':return 'BET_m2_g'
            if field=='HK_micropore_volume_cm3_g':return 'micropore_volume_cm3_g'
            if field in ['Raman_D_position_cm_inv','Raman_G_position_cm_inv']:return 'lib__'+field+'__unit_cm_1'
            if field in old_features:return field
            return 'process__'+field
        added_cells=0;attested_cells=0
        for name,eid in EIDS.items():
            mk=mats[name]['material_key'];rr=old.connection.execute('select record_json from cycle_records where endpoint_id=?',(eid,)).fetchone()[0];r=json.loads(rr)
            assert r['source_group']=='doi:'+DOI and r['sample_name']==name
            assert r['BET_m2_g']==selected[mk]['BET_surface_area_m2_g']and r['Raman_ID_IG']==selected[mk]['Raman_ID_IG']
            c.execute('insert into cycle_records values(?,?)',(eid,rr));change('cycle_records',[eid],rr,rr,'Identical physical FK passthrough, no value/profile/status change')
            link=dict(endpoint_id=eid,material_key=mk,status='confirmed_same_source_exact_sample_and_Table1',source_path=SOURCE,source_sha256=SOURCE_SHA,locator='Own Table1 p12 and cycle results p17/Fig3',new_admission=False)
            c.execute('insert into cycle_material_links values(?,?,?)',(eid,mk,dump(link)))
            for prior in old.connection.execute('select *from inputs where row_id=?and task like "cycle:%"',(eid,)):
                before=prior['record_json'];row=json.loads(before);row['material_key']=mk;ff=row['features'];added=[];attested=[];receipts=[]
                for f,value in selected[mk].items():
                    target=target_field(f,ff)
                    if ff.get(target)is not None:
                        assert ff[target]==value,(eid,target,ff[target],value);attested.append(target)
                    else:ff[target]=value;added.append(target)
                    for fid in ids[mk][f]:receipts.append(dict(fact_id=fid,field=target))
                row['v5_material_evidence']=dict(material_key=mk,receipts=receipts,added_nonmissing_fields=added,existing_values_attested=attested,micropore_method='HK',activation_stage='joint_calcination_KOH_activation',BET_alternate_intro_retained=True)
                after=dump(row);c.execute('insert into inputs values(?,?,?,?)',(prior['task'],eid,mk,after))
                for receipt in receipts:put_use(receipt['fact_id'],prior['task'],eid,receipt['field'],'input')
                change('inputs',[prior['task'],eid],before,after,'Explicit own-material feature augmentation; labels/conditions/old nonempty values preserved')
                if prior['task']=='cycle:reported_3e':added_cells+=len(added);attested_cells+=len(attested)
        # Property targets block all values from the same physical measurement.
        def group(field):
            if any(x in field for x in ['pore','BET_']):return 'adsorption_porosity'
            if field.startswith('Raman_'):return 'Raman'
            if field.startswith('XRD_'):return 'XRD'
            return 'process'
        material_targets=['XRD_d002_nm','Raman_ID_IG','BET_surface_area_m2_g','total_pore_volume_cm3_g','HK_micropore_volume_cm3_g','average_pore_diameter_nm','Raman_D_position_cm_inv','Raman_G_position_cm_inv']
        def add_input(task,row,source_report=None):
            c.execute('insert into inputs values(?,?,?,?)',(task,row['row_id'],row['material_key'],dump(row)));newrows.append(dict(task=task,row_id=row['row_id']))
            for field in row['features']:
                for fid in ids[row['material_key']].get(field,[]):put_use(fid,task,row['row_id'],field,'input')
            for fid in ids[row['material_key']].get(row['target_name'],[]):put_use(fid,task,row['row_id'],row['target_name'],'target')
        for name,m in mats.items():
            mk=m['material_key'];ff=selected[mk]
            for target in material_targets:
                row=dict(row_id=mk,material_key=mk,sample_name=name,source_family='doi:'+DOI,features={f:v for f,v in ff.items()if group(f)!=group(target)},target=ff[target],target_name=target,conditions=dict(material_stage=m['material_stage']),excluded_target_measurement_block=group(target),ready_for_training_inputs=True,provenance_release='OPB_v5',ordinary_cycle_admission=False)
                add_input('material:ordinary_biomass_pretest:'+target,row)
        cap_values=[('OPC',1,45.5),('OPB',1,217.3),('OPNP',1,274.5),('OPBNP',1,318.8),('OPBNP',2,303.6),('OPBNP',5,289),('OPBNP',10,271),('OPBNP',20,248)]
        for name,j,value in cap_values:
            m=mats[name];oid='v28_OPB:'+name+':GCD:'+str(j);cond=dict(reported_current_A_g=j,current_mass_basis='author_reported_unknown_not_inferred',electrolyte='KOH',concentration_mol_L=6,voltage_lower_V=-1,voltage_upper_V=0,reference_electrode='Hg/HgO')
            cap=dict(observation_id=oid,material_key=m['material_key'],doi=DOI,sample_name=name,value=value,unit='F/g',conditions=cond,source_family='doi:'+DOI,source_path=SOURCE,source_sha256=SOURCE_SHA,locator='PDF physicalp15 own GCD report',not_cycling_label=True,ready_for_training_inputs=True)
            caps.append(cap);c.execute('insert into capacity_reports_v3 values(?,?,?)',(oid,m['material_key'],dump(cap)))
            features=dict(selected[m['material_key']]);features.update(cond)
            row=dict(row_id=oid,material_key=m['material_key'],sample_name=name,source_family='doi:'+DOI,features=features,target=value,target_name='specific_capacitance_F_g',conditions=cond,not_cycling_label=True,ready_for_training_inputs=True,source_receipt=cap,provenance_release='OPB_v5')
            add_input('capacity:3e_reported',row)
        # Explicitly retain device/SIB roles without turning them into new cycle labels.
        for rid,record in [('device',dict(doi=DOI,sample_name='OPBNP//OPBNP',configuration='2e_symmetric',current_A_g=5,cycles=10000,retention_pct=97.61,coulombic_efficiency_pct=98.24,capacitance_reports=[dict(current_A_g=1,author_single_electrode_F_g=257.2,author_other_basis_F_g=64.3),dict(current_A_g=20,author_single_electrode_F_g=224)],role='inspection_only_ESI_formula_not_acquired',ready_for_cycling=False)),('SIB',dict(doi=DOI,sample_name='OPBNP',configuration='Na_half_cell',retention_pct=63.79,cycles=1000,current_A_g=1,capacity_mAh_g=206.6,role='sodium_battery_not_supercapacitor_retention',ready_for_cycling=False))]:
            record.update(source_path=SOURCE,source_sha256=SOURCE_SHA,locator='PDF p19 or p22-24');c.execute('insert into response_reports_v3 values(?,?)',('v28_OPB:'+rid,dump(record)))
        issues=[dict(issue_id='OPB_SSA_intro_table',doi=DOI,values=[1774.8,774.8],decision='Keep existing/Table1 BET1774.8 corroborated in abstract and p13; alternate intro retained, no author correction claimed.',all_scientific_questions_resolved=False),dict(issue_id='OPB_XPS_basis',doi=DOI,decision='C/O/N/B/P sequence retained; unspecified percentage basis not promoted to atom or mass features.'),dict(issue_id='OPB_SI_unavailable',doi=DOI,url='https://www.rsc.org/suppdata/d4/ta/d4ta02115k/d4ta02115k1.pdf',attempt='2026-10-28 public retrieval403; web fetch404; no usable SI acquired',remaining='Full rate table, TextS1 device normalization and additional SI curves remain unreviewed.')]
        for r in issues:c.execute('insert into evidence_issues_v3 values(?,?)',(r['issue_id'],dump(r)))
        for fid,f in [(f['fact_id'],f)for f in facts]:
            uses=[dict(task=r['task'],row_id=r['row_id'],feature=r['feature'],role=r['role'])for r in c.execute('select *from fact_uses where fact_id=?',(fid,))]
            status='connected_to_training_inputs'if uses else'nonpoint_or_missing_retained'if f['value']is None else'XPS_basis_or_BET_alternate_inspection_only'
            c.execute('insert into usage_ledger values(?,?,?)',(fid,status,dump(dict(fact_id=fid,disposition=status,uses=uses,training_connected=bool(uses),fact=f))))
        coverage=[dict(doi=DOI,unit_id='Table1',status='24own_cells_structured',source_path=SOURCE,full_paper_complete=False),dict(doi=DOI,unit_id='methods2.2',status='shared_conditions_and_controls_structured',source_path=SOURCE,full_paper_complete=False),dict(doi=DOI,unit_id='Fig2_Fig3',status='own_Raman_positions_GCD_rates_and4existing_cycles_linked;continuous_curves_pending',source_path=SOURCE,full_paper_complete=False),dict(doi=DOI,unit_id='SI',status='not_acquired_403;no_fake_table_or_formula',source_path=SOURCE,full_paper_complete=False),dict(doi=DOI,unit_id='SIB_Fig5',status='separate_sodium_battery_scope_not_cycle_target',source_path=SOURCE,full_paper_complete=False)]
        for r in coverage:c.execute('insert into extraction_coverage_v3 values(?,?,?)',(DOI,r['unit_id'],dump(r)))
        s=read(BASE/'summary.json');num=sum(f['value']is not None for f in facts);used=c.execute('select count(distinct fact_id)from fact_uses').fetchone()[0]
        counts={k:dict(v)for k,v in s['task_counts'].items()}
        for task, in c.execute('select distinct task from inputs'):
            if task.startswith('cycle:'):continue
            rows=[json.loads(r[0])for r in c.execute('select record_json from inputs where task=?',(task,))]
            previous=counts.get(task,dict(rows=0,source_families=0));oldfamilies={r['source_family']for r in old.rows(task)}if task in counts else set();families=oldfamilies|{'doi:'+DOI}
            counts[task]=dict(rows=previous['rows']+len(rows),source_families=len(families),source_holdout_validation_possible=len(families)>=2)
        s.update(version='training_store_v5_OPB_main',total_facts=s['total_facts']+len(facts),numeric_facts=s['numeric_facts']+num,nonpoint_facts=s['nonpoint_facts']+len(facts)-num,
          numeric_facts_connected_to_training_inputs=s['numeric_facts_connected_to_training_inputs']+used,new_material_registrations=4,new_material_facts=len(facts),new_numeric_material_facts=num,additional_connected_numeric_facts=used,new_connected_fact_ids=[r[0]for r in c.execute('select distinct fact_id from fact_uses')],
          material_registrations=s['material_registrations']+4,reviewed_sources=s['reviewed_sources']+1,new_sources=1,new_capacity_reports=8,new_ready_capacity_rows=8,confirmed_cycle_material_links=s['confirmed_cycle_material_links']+4,main3e_material_links=21,additional_main3e_nonmissing_cells=added_cells,main3e_existing_cells_attested=attested_cells,task_counts=counts,new_model_fits=0,new_cycling_admissions=0,storage_mode='readonly_explicit_derived_row_overlays',parent_database_sha256=pointer['sha256'])
        s['numeric_fact_connection_rate']=s['numeric_facts_connected_to_training_inputs']/s['numeric_facts'];s['remaining_unconnected_numeric_facts']=s['numeric_facts']-s['numeric_facts_connected_to_training_inputs'];uc=collections.Counter(s['usage_counts']);uc.update(r[0]for r in c.execute('select disposition from usage_ledger'));s['usage_counts']=dict(uc)
        parents=[dict(path=(BASE/pointer['database_file']).relative_to(ROOT).as_posix(),sha256=pointer['sha256'])]+json.loads(old.connection.execute("select value_json from main.metadata where key='readonly_parent_chain'").fetchone()[0])
        tables=[r[0]for r in c.execute('select name from sqlite_master where type="table"and name!="metadata"')]
        for key,value in [('summary',s),('readonly_parent_chain',parents),('append_only_union_tables',tables),('override_primary_keys',dict(inputs=['task','row_id'],cycle_records=['endpoint_id']))]:c.execute('insert into metadata values(?,?)',(key,dump(value)))
        c.commit();c.close()
    for name,val in [('summary',s),('new_facts',facts),('new_materials',list(mats.values())),('new_capacity_reports',caps),('overlay_changes',changes),('scientific_issues',issues),('extraction_coverage',coverage)]:write(OUT/(name+'.json'),val)
    write(OUT/'source_family_rules.json',read(BASE/'source_family_rules.json'))
    protected={r['path']:r['sha256']for r in parent_manifest['outputs']};protected[(BASE/'merge_manifest.json').relative_to(ROOT).as_posix()]=sha(BASE/'merge_manifest.json');protected.update(read(BASE/'protected_inputs.json'));protected[SOURCE]=SOURCE_SHA;write(OUT/'protected_inputs.json',protected)
    route=dict(version='training_store_v5_OPB_main',directory=OUT.relative_to(ROOT).as_posix(),database_file=DB.name,sha256=sha(DB),entry='data.training_store',new_model_fits=0)
    write(OUT/'entrypoint_snapshot.json',route);write(ROOT/'data/current_training_store.json',route)
    print(dump({k:s[k]for k in ['new_material_facts','new_numeric_material_facts','additional_connected_numeric_facts','additional_main3e_nonmissing_cells','main3e_existing_cells_attested','main3e_material_links']}))

if __name__=='__main__':build()
