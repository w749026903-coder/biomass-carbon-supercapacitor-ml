"""Lignin/commercial-CF primary CV, gel GCD and absolute cycle-capacitance data."""
from pathlib import Path
import collections,json,sqlite3,sys
from xml.etree import ElementTree as E
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.extract_corn_soot_v3 import sha,read,write,dump
BASE=ROOT/'全量文献训练数据接入_v3_玉米秸秆与烟炱_20261028'
OUT=ROOT/'全量文献训练数据接入_v4_木质素碳布与凝胶_20261028';DB=OUT/'training_extension_v4.sqlite'
DOI='10.1016/j.isci.2024.110433';PRIOR='10.3390/polym15204036';FAMILY='family:Munoz_CF_PVA_lignin_and_prior_controls'
MAIN='文献扩充_大批补齐_20261018/sources/SUP_110/main.xml';SI='文献扩充_大批补齐_20261018/sources/SUP_110/assets/mmc1.pdf'
FIG7='文献扩充_大批补齐_20261018/sources/SUP_110/assets/gr7.jpg'

def table(tid):
    t=E.parse(ROOT/MAIN).getroot().find('.//table-wrap[@id="'+tid+'"]')
    return [[' '.join(''.join(x.itertext()).split())for x in tr]for tr in t.findall('.//tbody/tr')]

def build():
    assert not OUT.exists(),'Append-only release: no rebuilding an existing output'
    parent=read(BASE/'merge_manifest.json')
    for r in parent['outputs']:assert sha(ROOT/r['path'])==r['sha256'],r['path']
    expected={MAIN:'a07a85d0ab4b61d198a6778a4a2b2ce6527c4811c76a964b3602a018de2f5ed4',SI:'a0cfe1580c76691fc293394431585176b46ba823ec9435c6a3eb475d344b5b26',FIG7:sha(ROOT/FIG7)}
    for p,h in expected.items():assert sha(ROOT/p)==h
    OUT.mkdir();p=sqlite3.connect((BASE/'training_data_v3.sqlite').as_uri()+'?mode=ro',uri=True);p.row_factory=sqlite3.Row
    c=sqlite3.connect(DB);c.row_factory=sqlite3.Row;c.execute('pragma foreign_keys=on')
    union=[]
    for row in p.execute("select name,sql from sqlite_master where type='table'and name!='metadata'"):
        c.execute(row['sql']);union.append(row['name'])
    c.execute('create table metadata(key text primary key,value_json text)')
    c.execute('create table report_purposes_v4(report_id text primary key,record_json text)')
    c.execute('create table recipe_bindings_v4(binding_id text primary key,record_json text)')
    union+=['report_purposes_v4','recipe_bindings_v4']
    rules=read(BASE/'source_family_rules.json');rules.append(dict(doi=DOI,related_doi=PRIOR,isolation_group=FAMILY,basis='Explicit Table2 prior-work controls; conservatively isolate both papers, without claiming all tests are the same experiment.'))
    write(OUT/'source_family_rules.json',rules)
    c.execute('insert into sources values(?,?)',(DOI,dump(dict(doi=DOI,source_path=MAIN,sha256=expected[MAIN],full_source_review_complete=False))))
    for path,h in expected.items():c.execute('insert into source_receipts_v3 values(?,?)',(path,h))
    nextid=p.execute('select max(fact_id)from facts').fetchone()[0]+1
    mats={};facts=[];selected=collections.defaultdict(dict);ids=collections.defaultdict(lambda:collections.defaultdict(list));reports=[];issues=[];bindings=[]
    def mat(name,stage):
        key='literature:v27B:'+name.replace(' ','_');scope='gel_device_separate'if'device'in stage else'commercial_CF_lignin_separate'if'electrode'in stage else'lignin_stage_only'if'lignin'in stage else'binding_unresolved'
        m=dict(material_key=key,doi=DOI,sample_name=name,material_stage=stage,source_family=FAMILY,task_scope=scope,synthesis=[],features={},full_source_review_complete=False)
        mats[name]=m;c.execute('insert into materials values(?,?,?)',(key,DOI,dump(m)));return m
    def fact(m,field,v,unit,locator,select=True,raw=None,**extra):
        nonlocal nextid
        path=SI if locator.startswith('SI ')else MAIN
        f=dict(fact_id=nextid,material_key=m['material_key'],doi=DOI,sample_name=m['sample_name'],material_stage=m['material_stage'],field_name=field,value=v,
          raw_value=str(v)if raw is None else raw,unit=unit,method='Author own stage/recipe or declared measurement; no constituent BET inheritance',source_path=path,source_sha256=expected[path],locator=locator,review_status='own_v27B_method_stage_qualified',selected_for_this_purpose=select and v is not None,training_eligible=0,**extra)
        c.execute('insert into facts values(?,?,?,?)',(nextid,m['material_key'],int(v is not None),dump(f)));facts.append(f)
        if select and v is not None:selected[m['material_key']][field]=v;ids[m['material_key']][field].append(nextid)
        nextid+=1;return f
    def issue(code,reason,**extra):
        a=dict(issue_id=code,doi=DOI,reason=reason,scientific_resolution=False,**extra);issues.append(a);c.execute('insert into evidence_issues_v3 values(?,?)',(code,dump(a)))
    def report(m,kind,value,unit,locator,conditions,ready=True,**extra):
        rid='v27B:'+str(len(reports)+1);path=FIG7 if locator.startswith('Figure7D')else MAIN
        r=dict(observation_id=rid,report_id=rid,material_key=m['material_key'],doi=DOI,sample_name=m['sample_name'],kind=kind,value=value,unit=unit,locator=locator,conditions=conditions,source_family=FAMILY,source_path=path,source_sha256=expected[path],not_cycling_retention=True,ready_for_training_inputs=ready,**extra)
        reports.append(r);c.execute('insert into capacity_reports_v3 values(?,?,?)',(rid,m['material_key'],dump(r)));return r
    electrode_rows=table('tbl1')
    for row in electrode_rows:
        entry,name,method,layers,conc,calc,mass,cv,lignin_cv=row;plain=name=='Plain CF';m=mat(name,'commercial_CF_control_electrode'if plain else'commercial_CF_lignin_composite_electrode_pretest')
        yes=calc=='Yes'
        for field,v,u,raw in [('coating_layers',None if layers=='–'else int(layers),'count',layers),('lignin_suspension_author_wt_pct',None if conc=='–'else float(conc),'author_wt%',conc),('calcination_applied',int(yes),'boolean_from_Yes_No',calc),('calcination_temperature_C',600 if yes else None,'degC','600'if yes else'not_applied_temperature_not_zero'),('calcination_duration_h',.5 if yes else None,'h','30min'if yes else'not_applied'),('heating_rate_C_min',5 if yes else None,'degC/min','5'if yes else'not_applied'),('author_Table1_weight_g',float(mass),'g',mass),('sizing_solution_author_wt_pct',None if plain else 5,'author_wt%','not_applicable'if plain else'5')]:
            fact(m,field,v,u,'XML Table1 '+entry+'; methods p4/p55-p60 zero based',raw=raw)
        fact(m,'BET_surface_area_m2_g',.2 if plain else None,'m2/g','XML body p16/p59 zero based',select=False,raw='~0.2'if plain else'fabric_measurements_not_reproducible_no_own_value',value_kind='approximate'if plain else'missing_not_reproducible')
        cond=dict(configuration='3e',method='CV',scan_mV_s=10,electrolyte='KCl',concentration_mol_L=3,voltage_lower_V=-.1,voltage_upper_V=.1,reference_electrode='Ag/AgCl',active_mass_basis='author_immersed_length_based_ma',coating_method=method,substrate='commercial_HexForce48193_plain12K',biomass_coating_present=not plain)
        report(m,'electrode_CV_F_g',float(cv),'F/g','XML Table1 entry '+entry,cond)
        if lignin_cv!='–':report(m,'lignin_normalized_CV_author_F_g',float(lignin_cv),'F/g_lignin_author','XML Table1 entry '+entry,cond,False,reason='Retain author normalization; TGA sample suffix/assignment ambiguity remains.')
    # Separate precursor properties. These are never the composite-fabric BET.
    for name,values,calc in [('Commercial lignin',[.3576,.001595,178.3851,565.341],False),('Calcinated lignin',[.3439,.000592,68.8408,235.209],True)]:
        m=mat(name,'raw_commercial_lignin'if not calc else'calcined_lignin_control')
        for f,v,u in zip(['BET_surface_area_m2_g','total_pore_volume_cm3_g','author_pore_width_angstrom','author_pore_diameter_angstrom'],values,['m2/g','cm3/g','angstrom','angstrom']):fact(m,f,v,u,'SI physicalp5 TableS1 '+name,measurement_group='adsorption_porosity')
        fact(m,'calcination_applied',int(calc),'boolean_from_sample_label','SI physicalp5 TableS1 '+name)
        for f,v,u in [('calcination_temperature_C',600 if calc else None,'degC'),('calcination_duration_h',.5 if calc else None,'h'),('heating_rate_C_min',5 if calc else None,'degC/min')]:fact(m,f,v,u,'XML p4; SI TableS1 separate lignin material')
    issue('v27B_BET_inheritance_forbidden','Composite-fabric BET not reproducible; lignin SI BET belongs to separate raw/calcined lignin only, not coated CF.')
    # Body/figure names disagree on whether TGA loading samples carry C suffix.
    for name,v in [('DCx4-10C_TGA_unbound',20.5),('SCx4-10_TGA_unbound',16.8),('DChx4-10_TGA_unbound',15.8)]:
        m=mat(name,'TGA_loading_sample_binding_unresolved');fact(m,'author_TGA_lignin_loading_wt_pct',v,'wt%','XML p15; SI FigS1 naming',select=False)
    issue('v27B_TGA_suffix','Body p15 and SI FigS1 differ in C suffixes; loading numbers and lignin-normalized capacitances retained, no silent sample alias repair.')
    dev_to_electrode={'LIG-DC':'DCx4-10C','LIG-DCh':'DChx4-10C','LIG-SC':'SCx4-10C'}
    for dev,el in dev_to_electrode.items():
        m=mat(dev,'assembled_commercial_CF_lignin_gel_device_before_bending')
        for field,v,u in [('gel_PVA_mass_g',3,'g'),('gel_H3PO4_stock_mass_g',3,'g'),('gel_water_mL',30,'mL'),('gel_mixing_temperature_C',85,'degC'),('gel_mixing_duration_h',.5,'h'),('gel_cure_temperature_C',60,'degC'),('gel_cure_duration_h',8,'h')]:fact(m,field,v,u,'XML p63 zero based')
        b=dict(binding_id=dev,electrode_material_key=mats[el]['material_key'],device_material_key=m['material_key'],sample_names=[dev,el],basis='Own Table2 electrode column and symmetric assembly methods p23/p63; explicit ingredient role, no property inheritance.')
        bindings.append(b);c.execute('insert into recipe_bindings_v4 values(?,?)',(dev,dump(b)))
    device_cv=[];eis=[]
    for row in table('tbl2'):
        entry,dev,el,area,mass,rs,combined,sigma,ref=row
        if ref!='this':
            c.execute('insert into response_reports_v3 values(?,?)',('v27B:prior:'+entry,dump(dict(doi=DOI,cited_doi=PRIOR,raw_cells=row,role='prior_work_context_not_new_own_response',ready_for_cycling=False))));continue
        base='LIG-DC'if dev=='LIG-DC-AB'else dev;m=mats[base];after=dev.endswith('-AB')
        cond=dict(configuration='2e_symmetric_gel',method='CV',scan_mV_s=10,electrolyte='PVA/H3PO4 gel',concentration_mol_L=None,voltage_lower_V=-.5,voltage_upper_V=.5,reference_electrode=None,after_bending=after,physical_device_group='v27B:'+base,active_mass_basis='author_electrodes_mass_no_single_electrode_factor_inferred')
        for kind,v,u in [('gel_device_CV_mF_cm2',area,'mF/cm2'),('gel_device_CV_mF_g',mass,'mF/g')]:device_cv.append(report(m,kind,float(v),u,'XML Table2 entry '+entry,cond,not after))
        for target,v,unit in [('Rs_author_ohm',rs,'ohm'),('Rs_plus_Rct_author_ohm',combined,'ohm'),('effective_device_sigma_mS_cm',sigma,'mS/cm')]:
            r=dict(report_id='v27B:EIS:'+entry+':'+target,material_key=m['material_key'],doi=DOI,sample_name=dev,field=target,value=float(v),unit=unit,conditions=cond,source_path=MAIN,source_sha256=expected[MAIN],locator='XML Table2 entry '+entry,ready_for_training_inputs=not after,ready_for_cycling=False)
            eis.append(r);c.execute('insert into response_reports_v3 values(?,?)',(r['report_id'],dump(r)))
    gcd=[]
    for row in table('tbl3'):
        entry,dev,j,td,cap,energy,power=row;m=mats[dev]
        cond=dict(configuration='2e_symmetric_gel',method='GCD',reported_current_mA_g=float(j),reported_current_A_g=float(j)/1000,current_conversion=dict(from_unit='mA/g',to_unit='A/g',factor=.001),current_mass_basis='author_reported_electrode_mass_unknown_physical_denominator',electrolyte='PVA/H3PO4 gel',concentration_mol_L=None,voltage_lower_V=0,voltage_upper_V=1,reference_electrode=None,after_bending=False,discharge_time_s=float(td),physical_device_group='v27B:'+dev)
        r=report(m,'gel_device_GCD_mF_g',float(cap),'mF/g','XML Table3 entry '+entry,cond,True,energy_mWh_kg=float(energy),power_mW_kg=float(power),raw_table_header='Scan rate (mA/g), physically mass-normalized current; not mV/s')
        gcd.append(r)
    issue('v27B_GCD_units','Table3 mA/g is consistent with C=current*discharge_time for 1V; preserve native units and explicit /1000 conversion to A/g, not silent thousandfold repair.')
    issue('v27B_power_typo','Conclusion reports 664mW/kg while Table3 entry8 is674 and text gives other rounded values; retain report-specific numbers, no preference for maximum.',values=[664,674])
    # Absolute capacitance trace, not retention. Avoid the unlabeled low-origin
    # marks and never infer that first cycle is the normalization reference.
    import numpy as np
    from PIL import Image
    image=Image.open(ROOT/FIG7).convert('RGB');arr=np.asarray(image);(OUT/'evidence').mkdir();image.crop((0,185,245,386)).resize((980,804)).save(OUT/'evidence/Figure7D_absolute_Csp_review.png')
    captures=[]
    for count,expected_cap in [(10,122),(20,102),(30,83),(40,83),(50,90),(60,90),(70,90),(80,78),(90,71),(99,71)]:
        x=57.5+count*142.75/100;y=353.5-expected_cap*130.75/200;xi,yi=round(x),round(y)
        z=arr[yi-4:yi+5,xi-2:xi+3];mask=np.max(z,axis=2)<105;yy,xx=np.where(mask)
        assert len(yy)>2,(count,len(yy));cy=float(yy.mean()+yi-4);cx=float(xx.mean()+xi-2);value=round((353.5-cy)*200/130.75,1)
        capture=dict(x0_px=57.5,x100_px=200.25,y0_px=353.5,y200_px=222.75,marker_center_px=[cx,cy],readout_tolerance_mF_g=4,cycle_interval=[max(1,count-2),min(100,count+2)],cycle_count_nominal=count,not_author_SD=True,not_independent_experiment=True)
        cond=dict(configuration='2e_symmetric_gel',method='GCD',reported_current_mA_g=.05,reported_current_A_g=.00005,current_conversion=dict(from_unit='mA/g',to_unit='A/g',factor=.001),electrolyte='PVA/H3PO4 gel',concentration_mol_L=None,voltage_lower_V=0,voltage_upper_V=1,reference_electrode=None,cycle_count=count,cycle_count_interval=capture['cycle_interval'],physical_device_group='v27B:LIG-DC:100cycle_trace')
        r=report(mats['LIG-DC'],'absolute_cycle_Csp_mF_g',value,'mF/g','Figure7D bounded black trace at nominal cycle '+str(count),cond,True,readout=capture,value_kind='bounded_curve_reading',not_retention_ratio=True)
        captures.append(dict(report_id=r['report_id'],**capture))
    mechanical=dict(report_id='v27B:mechanical_unbending_recovery',doi=DOI,material_key=mats['LIG-DC']['material_key'],metric_kind='capacitance_recovery_after_return_to_unbent',value=99,unit='%',source_path=MAIN,source_sha256=expected[MAIN],locator='XML conclusion p45 zero based',value_kind='author_reported_mechanical_recovery',ready_for_cycling=False,ready_for_training_inputs=False)
    c.execute('insert into response_reports_v3 values(?,?)',(mechanical['report_id'],dump(mechanical)))
    issue('v27B_99percent_role','99% is unbending recovery. Figure7D separately shows absolute GCD capacitance decay and CE. No retention normalization is invented from its first visible point.')
    for mk,ff in selected.items():
        for field,value in ff.items():c.execute('insert into selected_features values(?,?,?,?)',(mk,field,value,dump(ids[mk][field])))
    for m in mats.values():m['features']=selected[m['material_key']];c.execute('update materials set record_json=?where material_key=?',(dump(m),m['material_key']))
    def input_row(task,r,features,refs,target_name):
        row=dict(row_id=r['report_id'],material_key=r['material_key'],sample_name=r['sample_name'],source_family=FAMILY,features=features,target=r['value'],target_name=target_name,conditions=r['conditions'],source_receipt=r,not_cycling_label=True,ready_for_training_inputs=True,ingredient_material_keys=refs,provenance_release='v27B',independent_validation_required=True)
        c.execute('insert into inputs values(?,?,?,?)',(task,row['row_id'],row['material_key'],dump(row)))
        for field in features:
            owner=row['material_key'];native=field
            if field.startswith('electrode__'):owner=refs[0];native=field.removeprefix('electrode__')
            for fid in ids[owner].get(native,[]):c.execute('insert into fact_uses values(?,?,?,?,?)',(fid,task,row['row_id'],field,'input'))
    for r in reports:
        if not r['ready_for_training_inputs']:continue
        m=next(m for m in mats.values()if m['material_key']==r['material_key']);xx=dict(selected[m['material_key']]);refs=[]
        if m['sample_name']in dev_to_electrode:
            el=mats[dev_to_electrode[m['sample_name']]];refs=[el['material_key']];xx.update({'electrode__'+f:v for f,v in selected[el['material_key']].items()})
        for key in ['scan_mV_s','reported_current_A_g','cycle_count','electrolyte','concentration_mol_L','voltage_lower_V','voltage_upper_V','reference_electrode','coating_method','substrate']:
            if key in r['conditions']:xx[key]=r['conditions'][key]
        # Discharge time is retained as evidence but never predicts C=I*t/dV.
        input_row('capacity:commercial_CF_lignin:'+r['kind'],r,xx,refs,r['kind'])
    for r in eis:
        if not r['ready_for_training_inputs']:continue
        dev=r['sample_name'];m=mats[dev];el=mats[dev_to_electrode[dev]];xx=dict(selected[m['material_key']]);xx.update({'electrode__'+f:v for f,v in selected[el['material_key']].items()})
        input_row('response:commercial_CF_lignin:'+r['field'],r,xx,[el['material_key']],r['field'])
    for name in ['Commercial lignin','Calcinated lignin']:
        m=mats[name];mk=m['material_key'];ff=selected[mk]
        for target in ['BET_surface_area_m2_g','total_pore_volume_cm3_g','author_pore_width_angstrom','author_pore_diameter_angstrom']:
            rid='v27B:property:'+name+':'+target;r=dict(report_id=rid,material_key=mk,sample_name=name,value=ff[target],conditions=dict(material_stage=m['material_stage']))
            xx={f:v for f,v in ff.items()if f.startswith(('calcination_','heating_'))};task='material:lignin_stage_only:'+target
            input_row(task,r,xx,[],target)
            for fid in ids[mk][target]:c.execute('insert into fact_uses values(?,?,?,?,?)',(fid,task,rid,target,'target'))
    for f in facts:
        refs=[dict(task=r['task'],row_id=r['row_id'],feature=r['feature'],role=r['role'])for r in c.execute('select *from fact_uses where fact_id=?',(f['fact_id'],))]
        status='connected_to_training_inputs'if refs else'nonpoint_or_missing_retained'if f['value']is None else'approximate_BET_or_TGA_binding_inspection_only'
        c.execute('insert into usage_ledger values(?,?,?)',(f['fact_id'],status,dump(dict(fact_id=f['fact_id'],disposition=status,uses=refs,training_connected=bool(refs),fact=f))))
    coverage=[]
    for tid in ['tbl1','tbl2','tbl3','undtbl1']:coverage.append(dict(doi=DOI,unit_id=tid,status='own_report_values_structured_and_context_separated'if tid!='undtbl1'else'reagent_metadata_indexed',source_path=MAIN,full_paper_complete=False))
    for fig in E.parse(ROOT/MAIN).getroot().iter('fig'):
        if fig.get('id')=='undfig1':continue
        coverage.append(dict(doi=DOI,unit_id=fig.get('id'),status='partial_absolute_capacitance_trace10_bounded_reads'if fig.get('id')=='fig7'else'scope_reviewed_remaining_curves_not_exhaustive',source_path=MAIN,full_paper_complete=False))
    for unit,status in [('SI_TableS1','8_numeric_properties_structured'),('SI_FigS1','scope_read_TGA_sample_binding_unresolved'),('SI_FigS2_S6','scope_read_continuous_curves_remaining')]:coverage.append(dict(doi=DOI,unit_id=unit,status=status,source_path=SI,full_paper_complete=False))
    for r in coverage:c.execute('insert into extraction_coverage_v3 values(?,?,?)',(DOI,r['unit_id'],dump(r)))
    s=read(BASE/'summary.json');newnum=sum(f['value']is not None for f in facts);newused=c.execute('select count(distinct fact_id)from fact_uses').fetchone()[0]
    counts=dict(s['task_counts'])
    for task, in c.execute('select distinct task from inputs'):
        count=c.execute('select count(*)from inputs where task=?',(task,)).fetchone()[0];assert task not in counts;counts[task]=dict(rows=count,source_families=1,source_holdout_validation_possible=False)
    s.update(version='training_catalog_v4_v27B',total_facts=s['total_facts']+len(facts),numeric_facts=s['numeric_facts']+newnum,nonpoint_facts=s['nonpoint_facts']+len(facts)-newnum,
      numeric_facts_connected_to_training_inputs=s['numeric_facts_connected_to_training_inputs']+newused,new_material_registrations=len(mats),new_material_facts=len(facts),new_numeric_material_facts=newnum,
      new_connected_fact_ids=[r[0]for r in c.execute('select distinct fact_id from fact_uses')],additional_connected_numeric_facts=newused,new_sources=1,new_capacity_reports=len(reports),new_ready_capacity_rows=sum(r['ready_for_training_inputs']for r in reports),new_response_training_rows=sum(r['ready_for_training_inputs']for r in eis),
      material_registrations=s['material_registrations']+len(mats),reviewed_sources=s['reviewed_sources']+1,task_counts=counts,new_model_fits=0,new_cycling_admissions=0,storage_mode='append_only_readonly_parent_union',parent_database_sha256=sha(BASE/'training_data_v3.sqlite'))
    s['numeric_fact_connection_rate']=s['numeric_facts_connected_to_training_inputs']/s['numeric_facts'];s['remaining_unconnected_numeric_facts']=s['numeric_facts']-s['numeric_facts_connected_to_training_inputs']
    oldusage=collections.Counter(s['usage_counts']);oldusage.update(r[0]for r in c.execute('select disposition from usage_ledger'));s['usage_counts']=dict(oldusage)
    chain=[dict(path=(BASE/'training_data_v3.sqlite').relative_to(ROOT).as_posix(),sha256=sha(BASE/'training_data_v3.sqlite'))]
    for key,value in [('summary',s),('readonly_parent_chain',chain),('append_only_union_tables',union)]:c.execute('insert into metadata values(?,?)',(key,dump(value)))
    c.commit();c.close();p.close()
    for name,val in [('summary',s),('new_facts',facts),('new_materials',list(mats.values())),('capacity_reports',reports),('EIS_reports',eis),('mechanical_recovery_report',mechanical),('scientific_issues',issues),('recipe_bindings',bindings),('curve_captures',captures),('extraction_coverage',coverage),('source_receipts',expected)]:write(OUT/(name+'.json'),val)
    protected={r['path']:r['sha256']for r in parent['outputs']};protected[(BASE/'merge_manifest.json').relative_to(ROOT).as_posix()]=sha(BASE/'merge_manifest.json');protected.update(read(BASE/'protected_inputs.json'));protected.update(expected);write(OUT/'protected_inputs.json',protected)
    pointer=dict(version='training_catalog_v4_v27B',directory=OUT.relative_to(ROOT).as_posix(),database_file=DB.name,sha256=sha(DB),entry='data.training_catalog',new_model_fits=0)
    write(OUT/'entrypoint_snapshot.json',pointer);write(ROOT/'data/current_training_catalog.json',pointer)
    print(dump({k:s[k]for k in ['new_material_registrations','new_material_facts','new_numeric_material_facts','additional_connected_numeric_facts','new_capacity_reports','new_ready_capacity_rows','new_response_training_rows']}))

if __name__=='__main__':build()
