"""Source-reviewed YZPC/Kochia sample-stage specification; not an auto extractor."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.extract_lignin_cf_v4 import read,write,sha
OUT=ROOT/'全量文献训练数据接入_v7_药渣与地肤主集_20261029'
YZ='10.1002/asia.70648';KA='10.1002/ente.202201281'
YZTABLE={'YZ':[3.35,0,.00067,0,0,75.37,22.18,2.45],'YZC':[3.5,0,.00039,0,0,83.35,14.05,2.6],'YZPC-0':[167,101.611,.1,.043,.43,87.34,10.7,1.96],'YZPC-1':[1438.704,1320,.722,.598,.83,86.37,11.53,2.1],'YZPC-2':[2532.737,2231.765,1.119,.928,.83,82.49,15.38,2.12],'YZPC-3':[3358.574,2544.4,1.223,.63,.37,82,16.11,1.89],'YZPC-4':[2331.706,750.734,1.457,.319,.22,82.9,16.13,.97]}
FIELDS=['BET_surface_area_m2_g','micropore_surface_area_m2_g','total_pore_volume_cm3_g','micropore_volume_cm3_g','reported_micropore_volume_fraction','XPS_C_atomic_pct_v15','XPS_O_atomic_pct_v15','XPS_N_atomic_pct_v15']
UNITS=['m2/g','m2/g','cm3/g','cm3/g','fraction','at.%','at.%','at.%']

def curate():
    assert not(OUT/'merge_manifest.json').exists()and not(OUT/'training_extension_v7.sqlite').exists()
    receipts=read(OUT/'source_receipts.json');sources=[dict(doi=doi,**{k:v for k,v in s.items()if k!='source_id'})for doi,s in zip([YZ,KA],receipts)]
    mats=[];caps=[];resp=[];issues=[];coverage=[];claims=[]
    def material(doi,name,stage,scope):
        m=dict(material_key='literature:v30:'+('YZ:'if doi==YZ else'KAC:')+name,doi=doi,sample_name=name,material_stage=stage,task_scope=scope,facts=[],property_targets=[],full_source_review_complete=False);mats.append(m);return m
    def fact(m,f,v,u,loc,select=True,target=False,**extra):
        row=dict(field_name=f,value=v,unit=u,locator=loc,selected_for_this_purpose=bool(select and v is not None),**extra);m['facts'].append(row)
        if target and select and v is not None:m['property_targets'].append(f)
    def protocol(m,yz):
        # These preparation quantities describe the electrode, not the carbon's BET.
        for f,v,u in [('electrode_active_fraction',.8,'fraction'),('electrode_PVDF_fraction',.15 if yz else .1,'fraction'),('electrode_conductive_fraction',.05 if yz else .1,'fraction'),('electrode_coated_area_cm2',1,'cm2'),('electrode_dry_temperature_C',80 if yz else 75,'degC'),('electrode_dry_duration_h',12 if yz else 1,'h'),('electrode_press_pressure_MPa',10,'MPa')]:
            fact(m,f,v,u,'Main physicalp3 electrode recipe16:3:1'if yz else'Main physicalp8 electrode recipe8:1:1',raw_value='16:3:1'if yz and f.endswith('_fraction')else'8:1:1'if not yz and f.endswith('_fraction')else str(v),derivation='component/(sum of reported ratio parts)'if f.endswith('_fraction')else None)
        if yz:
            for f,v in [('electrode_active_loading_lower_mg_cm2',2),('electrode_active_loading_upper_mg_cm2',3)]:fact(m,f,v,'mg/cm2','Main physicalp3 author interval2-3; no midpoint',value_kind='protocol_interval_boundary')
            fact(m,'mass_loading_mg_cm2',None,'mg/cm2','Author interval2-3; exact point not reported',select=False)
            fact(m,'electrode_post_lamination_dry_duration_h',12,'h','Main physicalp3 second drying after lamination; distinct from film initial12h')
        else:
            fact(m,'mass_loading_mg_cm2',3,'mg/cm2','Main physicalp8 explicit single-electrode active loading')
            fact(m,'electrode_press_duration_min',1,'min','Main physicalp8 pressed10MPa1min')
    yz={}
    for name,values in YZTABLE.items():
        final=name.startswith('YZPC');stage='final_biomass_carbon_before_test'if final else'precarbonized_intermediate'if name=='YZC'else'raw_mixed_herbal_residue'
        scope='ordinary_biomass_pretest'if final else'precarbonized_stage_separate'if name=='YZC'else'raw_biomass_stage_separate'
        m=material(YZ,name,stage,scope);yz[name]=m
        for f,v,u in zip(FIELDS,values,UNITS):
            held=name=='YZPC-3'and f in ['micropore_volume_cm3_g','reported_micropore_volume_fraction']
            fact(m,f,v,u,'Main physicalp5 Table1 own row '+name,select=not held,target=not held,method='XPS atomic explicit Table1'if f.startswith('XPS_')else'Own Table1; pore algorithm not inferred from DFT distribution caption',disposition='YZPC3_existing_volume_fraction_freeze_preserved'if held else None)
        for f,v,u in [('raw_grind_mesh',200,'mesh'),('raw_dry_temperature_C',80,'degC')]:fact(m,f,v,u,'Main physicalp2 synthesis raw precursor')
        fact(m,'raw_dry_duration_h',None,'h','Main physicalp2 overnight, no exact duration',select=False)
        if name!='YZ':
            for f,v,u in [('precarbonization_temperature_C',400,'degC'),('precarbonization_duration_h',2,'h'),('precarbonization_heating_rate_C_min',10,'degC/min')]:fact(m,f,v,u,'Main physicalp2 measured YZC precursor stage400C2h N2')
        if final:
            for f,v,u in [('KOH_to_precarbonized_carbon_mass_ratio',int(name[-1]),'mass_ratio'),('KOH_mixing_duration_min',6,'min'),('activation_temperature_C',700,'degC'),('activation_duration_h',.5,'h'),('heating_rate_C_min',10,'degC/min'),('final_dry_temperature_C',80,'degC')]:fact(m,f,v,u,'Main physicalp2-3 YZC:KOH and activation700C0.5h; not KOH/raw-residue basis')
            fact(m,'HCl_wash_mol_L',None,'mol/L','Dilute HCl, numerical concentration not reported',select=False)
            fact(m,'final_dry_duration_h',None,'h','Main physicalp3 overnight',select=False)
            fact(m,'Raman_ID_IG',[.85,.96,.97,.97,.98][int(name[-1])],'ratio','Main physicalp6 and physicalp5 Fig3b',target=True)
            protocol(m,True)
        if name=='YZPC-3':
            fact(m,'water_contact_angle_deg_v15',92,'degree','Main physicalp7 own contact-angle statement; SI S2 not acquired',target=True,method='Author reported snapshot; measurement time unspecified, not equilibrium angle')
            fact(m,'contact_angle_time_ms_v15',None,'ms','Snapshot time not stated in available main text',select=False)
    kac={}
    raw=material(KA,'Kochia_raw','raw_Kochia','raw_biomass_stage_separate');kac['Kochia_raw']=raw
    for label,pos in [('lignin_C_H',830),('aromatic_skeleton',1624),('C_H_stretch',2926),('O_H_stretch',3357),('cellulose_ring',895),('glucosidic_C_O',1038),('cellulose_C_O',1157),('cellulose_C_H',1375),('hemicellulose_C_O',1240),('acetyl_C_O',1733)]:fact(raw,'FTIR_'+label+'_position_cm_inv',pos,'cm-1','Main physicalp3 Fig2g raw Kochia; not final-carbon composition',select=False,disposition='measurement_metadata_not_independent_predictor')
    for field,v in [('TGA_stage1_weight_loss_reported_pct',6.7),('TGA_stage2_weight_loss_reported_pct',71.9),('TGA_stage3_weight_loss_reported_pct',21.4)]:fact(raw,field,v,'%','Main physicalp3 TGA prose; last-stage loss/residue role requires original-curve review',select=False,disposition='raw_TGA_stage_semantics_pending_not_yield')
    for name in ['KC','KAC-4','KAC-5','KAC-6']:
        m=material(KA,name,'precarbonized_intermediate'if name=='KC'else'final_biomass_carbon_before_test','precarbonized_stage_separate'if name=='KC'else'ordinary_biomass_pretest');kac[name]=m
        for f,v,u in [('raw_grind_mesh',35,'mesh'),('precarbonization_temperature_C',800,'degC'),('precarbonization_duration_h',2,'h'),('precarbonization_heating_rate_C_min',5,'degC/min')]:fact(m,f,v,u,'Main physicalp8 Kochia->KC800C2h; KC aliases optimized KC-800, not a duplicate sample')
        if name!='KC':
            for f,v,u in [('KOH_to_precarbonized_carbon_mass_ratio',int(name[-1]),'mass_ratio'),('KOH_predry_temperature_C',75,'degC'),('KOH_predry_duration_h',12,'h'),('activation_temperature_C',600,'degC'),('activation_duration_h',2,'h'),('heating_rate_C_min',5,'degC/min'),('HCl_wash_mol_L',1,'mol/L')]:fact(m,f,v,u,'Main physicalp8 explicit KC:KOH1:n; second activation600C2h, N2')
        else:
            fact(m,'KOH_to_precarbonized_carbon_mass_ratio',0,'mass_ratio','Unactivated KC control before KOH step; none added, not zero K content')
        fact(m,'BET_surface_area_m2_g',None,'m2/g','Own BET not reported for this sample in available main'if name!='KAC-5'else'See own Table1 below',select=False)if name!='KAC-5'else None
        fact(m,'Raman_ID_IG',{'KC':.96,'KAC-4':.98,'KAC-5':.99,'KAC-6':1.0}[name],'ratio','Main physicalp4 Raman and physicalp5 Fig3b',target=True)
        protocol(m,False)
        if name=='KAC-5':
            for f,v,u in [('BET_surface_area_m2_g',1441.3,'m2/g'),('total_pore_volume_cm3_g',.5992,'cm3/g'),('micropore_volume_cm3_g',.493,'cm3/g'),('mesopore_volume_cm3_g',.1062,'cm3/g'),('average_pore_diameter_nm',1.6632,'nm')]:fact(m,f,v,u,'Main physicalp4 Table1 KAC5 own row',target=True)
            fact(m,'reported_micropore_volume_fraction',.8228,'fraction','Main physicalp4 Table1 82.28%, explicit /100 conversion',target=True,raw_value='82.28%',derivation='82.28/100')
            for f,v in [('XPS_C_atomic_pct_v15',91.75),('XPS_O_atomic_pct_v15',8.25)]:fact(m,f,v,'at.%','Main physicalp5 Fig3c inset At%; p4 own prose',target=True)
            fact(m,'water_contact_angle_deg_v15',58.25,'degree','Main physicalp5 Fig3f 70ms snapshot, not equilibrium',target=True)
            fact(m,'contact_angle_time_ms_v15',70,'ms','Main physicalp5 Fig3f printed time70ms',target=False)
    def capacity(m,rate,value,partial=False,device=False):
        prefix='v30:'+('YZ:'if m['doi']==YZ else'KAC:');oid=prefix+m['sample_name']+(':2e:'if device else':3e:')+str(rate)
        cond=dict(configuration='2e_symmetric'if device else'3e',method='GCD',electrolyte='KOH',concentration_mol_L=6,voltage_lower_V=0 if device else -1,voltage_upper_V=1.2 if device else 0,reported_current_A_g=rate,current_mass_basis='total_active_mass_both_electrodes_explicit'if device else'author_reported_not_inferred')
        if not device:cond['reference_electrode']='Hg/HgO'
        task=['capacity:2e_device']if device else['capacity:3e_reported_without_BET']if partial else['capacity:3e_reported','capacity:3e_with_graph']
        caps.append(dict(observation_id=oid,material_key=m['material_key'],value=value,unit='F/g',target_name='specific_capacitance_F_g',conditions=cond,tasks=task,locator='Main physicalp8 own GCD paragraph'if m['doi']==YZ else'Main physicalp4 own GCD or physicalp7 device/physicalp8 eq2',role='partial_material_protocol_task'if partial else'explicit_total_mass_device'if device else'author_reported'))
    for name,value in zip(['YZPC-0','YZPC-1','YZPC-2','YZPC-3','YZPC-4'],[77,196,218,344,278]):capacity(yz[name],1,value)
    capacity(yz['YZPC-3'],10,270)
    for name,value in [('KC',184),('KAC-4',256),('KAC-5',284),('KAC-6',239)]:capacity(kac[name],1,value,partial=name!='KAC-5')
    for rate,v in [(.5,288),(10,227)]:capacity(kac['KAC-5'],rate,v)
    for rate,v in [(.5,61.7),(10,41.7)]:capacity(kac['KAC-5'],rate,v,device=True)
    for name,rs,rct,zw in [('YZPC-0',1.22,.35,4.26),('YZPC-1',.96,1.19,3.85),('YZPC-2',.85,1.13,2.85),('YZPC-3',.60,.23,1.38),('YZPC-4',.75,.45,.83)]:
        for field,v in [('Rs_author_ohm',rs),('Rct_author_ohm',rct),('Warburg_author_reported_ohm',zw)]:resp.append(dict(observation_id='v30:YZ:'+name+':'+field,material_key=yz[name]['material_key'],value=v,unit='ohm_author_reported',target_name=field,conditions=dict(method='EIS',configuration='3e',electrolyte='KOH',concentration_mol_L=6,frequency_lower_Hz=.01,frequency_upper_Hz=1e5),tasks=['response:ordinary_biomass:3e_'+field],locator='Main physicalp9 EIS own sample values',reported_dimension_caveat='Warburg fitted units/form unknown; author Ω channel only'if field.startswith('Warburg')else None))
    for name,rs,rct in [('KC',.360,.055),('KAC-4',.365,.05),('KAC-5',.368,.039),('KAC-6',.370,.041)]:
        for field,v in [('Rs_author_ohm',rs),('Rct_author_ohm',rct)]:resp.append(dict(observation_id='v30:KAC:'+name+':'+field,material_key=kac[name]['material_key'],value=v,unit='ohm',target_name=field,conditions=dict(method='EIS',configuration='3e',electrolyte='KOH',concentration_mol_L=6,frequency_lower_Hz=.01,frequency_upper_Hz=1e5,amplitude_mV=5),tasks=['response:ordinary_biomass:3e_'+field],locator='Main physicalp5 EIS own ordered KC/KAC4/5/6 values'))
    issues=[dict(issue_id='v7_YZPC3_volume_fraction_existing_freeze',doi=YZ,raw_volume=.63,total_volume=1.223,raw_fraction=.37,decision='Keep original volume/fraction frozen as already reviewed 2026-10-21; do not fill derived mesopore volume or override canonical fields.'),dict(issue_id='v7_YZPC_feedstock_identity',doi=YZ,decision='Methods mixed industrial herbal residues; conclusion rhubarb-root wording retained as alternate, no invented detailed feedstock proportions.'),dict(issue_id='v7_YZPC_power_equation',doi=YZ,decision='Printed power equation divides by voltage, not time; retain literal and no derived energy/power labels.'),dict(issue_id='v7_SI_unavailable',doi=YZ,decision='Publisher linked SuppMat.docx; public fetch403, no table/curve content fabricated.'),dict(issue_id='v7_KAC_TGA_semantics',doi=KA,decision='Raw TGA prose21.4%loss vs residue/stage interpretation unresolved; not yield or final carbon composition.'),dict(issue_id='v7_KAC_KC_identity',doi=KA,decision='KC is optimized800C precursor already shown as KC800 in screening; no duplicate184Fg experiment or activated BET copied to controls.')]
    for doi,nmain in [(YZ,8),(KA,5)]:
        for n in range(1,nmain+1):coverage.append(dict(doi=doi,unit_id='Main_Fig'+str(n),status='scope read and author text anchors structured; full continuous curves/image descriptors remain',full_paper_complete=False))
        coverage.append(dict(doi=doi,unit_id='Table1',status='56own cells across7stages;2 existing frozen'if doi==YZ else'6own table values including explicit82.28pct normalization',numeric_cells=56 if doi==YZ else 6,full_paper_complete=False))
        coverage.append(dict(doi=doi,unit_id='Methods',status='stage-specific shared preparation and electrode protocol structured; absent quantities remain null',full_paper_complete=False))
        coverage.append(dict(doi=doi,unit_id='SI',status='public fetch403; all SI tables/curves still unacquired',full_paper_complete=False))
    claims=[dict(claim_id='v7_YZPC_energy_pairs',doi=YZ,role='inspection_only_not_inverted_to_capacitance',KOH_energy_Wh_kg=9.17,Na2SO4_energy_Wh_kg=16.04,Na2SO4_power_W_kg=250,locator='Mainp9-10; no device capacitance inverted from energy'),dict(claim_id='v7_KAC_energy_pairs',doi=KA,pairs=[dict(energy_Wh_kg=12.3,power_W_kg=300),dict(energy_Wh_kg=8.3,power_W_kg=6000)],role='paired_author_Ragone_claims_not_new_cycling_labels'),dict(claim_id='v7_KAC_2e_cycle',doi=KA,retention_pct=88.83,cycles=10000,current_A_g=5,role='device_claim_preserved_not_new_cycling_admission',locator='MainFig5d and p8; main3E90.31 kept separate'),dict(claim_id='v7_KC_temperature_screening',doi=KA,mentioned_samples=['KC-600','KC-700','KC-800','KC-900'],KC800_alias='KC',role='SI missing; only explicitKC800184Fg own body anchor is used once, other screening outcomes not guessed')]
    spec=dict(version='training_latest_v7_YZPC_Kochia',parent_directory='全量文献训练数据接入_v6_ALPC主集与补充表_20261029',database_file='training_extension_v7.sqlite',sources=sources,materials=mats,capacities=caps,responses=resp,issues=issues,coverage=coverage,inspection_claims=claims,cycle_links=[dict(endpoint_id='incoming:ADD_039_T01',material_key=yz['YZPC-3']['material_key'],status='own_Table1_Fig5d_exact_final_sample'),dict(endpoint_id='candidate:TE026',material_key=kac['KAC-5']['material_key'],status='own_Table1_Fig4f_exact_final_sample')],main_field_aliases={'BET_surface_area_m2_g':'BET_m2_g'},measurement_blocks={})
    write(OUT/'reviewed_extraction_spec.json',spec);write(OUT/'extraction_coverage.json',coverage);write(OUT/'scientific_issues.json',issues)
    print('Reviewed spec:',len(mats),'stages/materials,',sum(len(m['facts'])for m in mats),'facts,',len(caps),'capacity reports,',len(resp),'response reports')

if __name__=='__main__':curate()
