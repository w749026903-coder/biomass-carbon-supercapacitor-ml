"""Manually reviewed reported endpoints. This is a feasibility ledger, never training admission."""
from pathlib import Path
import json, collections, sys
sys.stdout.reconfigure(encoding='utf-8')
OUT=Path(__file__).resolve().parent
sources={x['id']:x for x in json.loads((OUT/'全库循环证据定位.json').read_text(encoding='utf-8'))}
rows=[]
def add(pid,sample,n,r,system,method,j,electrolyte,pages,**kw):
    s=sources[pid]
    row=dict(record_id=f'{pid}_CY{sum(x["paper_id"]==pid for x in rows)+1:02d}',paper_id=pid,
             material_id=f'{pid}::{sample}',sample=sample,study_group=s['doi'] or pid,
             cycle_test_id=f'{pid}::{sample}::{system}::{electrolyte}::{kw.get("test_tag", "default")}',
             source_category=s['category'],doi=s['doi'],year=s['year'],pdf=s['path'],pdf_pages=pages,
             system=system,method=method,cycle_count=n,retention_pct=r,retention_relation='eq',
             current_density_A_g=j,scan_rate_mV_s=None,current_density_mA_cm2=None,
             electrolyte=electrolyte,concentration_value=None,concentration_unit=None,
             voltage_lower_V=None,voltage_upper_V=None,temperature_C=None,mass_loading_mg_cm2=None,
             BET_m2_g=None,total_pore_volume_cm3_g=None,N_at_pct=None,O_at_pct=None,
             material_scope='carbon_candidate' if s['category']=='A' else 'separate_system',
             value_kind='reported',conflict=False,provenance_note='',input_provenance={},
             eligible_for_database=False,admission_status='feasibility_only_pending_record_audit')
    row.update(kw); rows.append(row)

add('R012','OPL_KOH12',100,92.9,'2E_symmetric','GCD',.1,'LiTFSI',[15,16],concentration_value=20,concentration_unit='mol/kg',voltage_lower_V=.1,voltage_upper_V=2,supplement_index=1,provenance_note='SI Figure S14; short test, substrate corrosion discussed')
add('R012','OPL_KOH12',100,88.7,'2E_symmetric','GCD',.1,'LiCl',[15,16],concentration_value=20,concentration_unit='mol/kg',voltage_lower_V=.1,voltage_upper_V=1,supplement_index=1,provenance_note='SI Figure S14; short test, Al substrate corrosion')
add('R013','EUAC1-60',10000,89.9,'3E','GCD',1,'KOH',[3,8,10],concentration_value=1,concentration_unit='mol/L',voltage_lower_V=-1,voltage_upper_V=.2,BET_m2_g=1589,total_pore_volume_cm3_g=.82,provenance_note='Figure 6d; reported Coulombic efficiency 117.21% requires clarification; not substituted for retention')
add('R013','EUAC1-60',10000,93.7,'Zn_hybrid','GCD',1,None,[10],material_scope='Zn_hybrid',provenance_note='Figure 7i; Zn-ion hybrid must remain separate')
add('R017','BCF-U',5000,99,'2E_symmetric','GCD',.2,'Na2SO4',[13,14,16],retention_relation='gt',concentration_value=1,concentration_unit='mol/L',provenance_note='>99%, censored report, not an exact 99%')
add('R017','BCF-U',1000,None,'2E_symmetric','GCD',8,'KOH',[13,14],concentration_value=6,concentration_unit='mol/L',provenance_note='about 230 to about 141 F/g; curve digitization needed; no exact retention entered')
add('R018','C-4',5000,None,'3E','GCD',2.5,None,[11,13],conflict=True,provenance_note='p11 138.5 to 36.45 F/g implies ~26.32%; p13 says 40%; nearly 100% is Coulombic efficiency, not retention')
add('R028','EF-900',10000,94,'2E_symmetric_gel','GCD',None,None,[7,8],BET_m2_g=1082.8,total_pore_volume_cm3_g=.7849,provenance_note='Figure 9; acidic solid-state device; exact cycling current/electrolyte recipe not paired yet')
add('R032','ONPC-700',10000,100.5,'3E','CV',None,None,[4,5],scan_rate_mV_s=200,provenance_note='Figure 4f; CV cycles must not be treated as GCD')
add('R032','ONPC-700',10000,94,'2E_symmetric','CV',None,None,[6],scan_rate_mV_s=200,provenance_note='Figure 6f caption specifies CV at 200 mV/s')
add('R033','aGCL-800',5000,96.7,'3E','GCD_unspecified_protocol',None,'H3PO4',[4],concentration_value=2,concentration_unit='mol/L',provenance_note='Figure 3f; four other materials only reported as 94-95%, not four exact labels')
add('R033','aGCL-800',10000,99.9,'2E_symmetric','GCD',20,'H3PO4',[5],concentration_value=2,concentration_unit='mol/L',provenance_note='Figure 5f; p6 also mentions 86% after 10000 cycles without matching protocol; assignment needs review',conflict=True)
add('R036','APC-700',10000,100.98,'3E','CV',None,'KOH',[4,5],scan_rate_mV_s=200,concentration_value=6,concentration_unit='mol/L',voltage_lower_V=-1,voltage_upper_V=0,BET_m2_g=804.8)
add('R036','APC-700',10000,99.7,'2E_symmetric','CV',None,'Na2SO4',[6,7],scan_rate_mV_s=200,concentration_value=1,concentration_unit='mol/L',voltage_lower_V=0,voltage_upper_V=1.6,BET_m2_g=804.8)
add('R062','TPC-850',4500,95.83,'2E_as_reported','CV',None,'KOH',[4,7],scan_rate_mV_s=500,concentration_value=6,concentration_unit='mol/L',voltage_lower_V=-1,voltage_upper_V=0,BET_m2_g=1767.66,total_pore_volume_cm3_g=1.43,provenance_note='two symmetric electrodes as reported; negative cell window needs confirmation')
add('R069','RCS-AC',5000,97.2,'3E','GCD',None,'KOH',[5,7,8],concentration_value=3,concentration_unit='mol/L',BET_m2_g=1917,provenance_note='Figure 6a; do not borrow 1 A/g from capacitance test as cycle current')
for e,r in [('Na2SO4',93.6),('H2SO4',84.8)]:
    add('R069','RCS-AC',5000,r,'3E','GCD',None,e,[7,8],concentration_value=1,concentration_unit='mol/L',BET_m2_g=1917,conflict=True,provenance_note='p7 prose assigns 93.6 to Na2SO4 and 84.8 to H2SO4; p8 Table 2 reverses labels; retain conflict, no correction')
add('R078','C/600C',8000,98.1,'3E','GCD',5,'KOH',[1,2,3,6],concentration_value=6,concentration_unit='mol/L',voltage_lower_V=-1,voltage_upper_V=0,BET_m2_g=2074.72,total_pore_volume_cm3_g=.930,provenance_note='abstract 98.1%; body >98%; Figure 6b')
add('R085','NPCA-600-0.5',5000,80,'3E','GCD',10,'KOH',[2,9,10],retention_relation='approx',concentration_value=6,concentration_unit='mol/L',voltage_lower_V=-1,voltage_upper_V=0,BET_m2_g=582.9,provenance_note='Figure 7i; 91% after 10 CO2 adsorption cycles is not electrochemical cycling; .187 cm3/g is micropore volume, not total')
add('R087','OAC623',1000,85.5,'system_pending','GCD',.1,'NaOH',[8,9],concentration_value=2,concentration_unit='mol/L',voltage_lower_V=0,voltage_upper_V=1,provenance_note='Figure 12; electrode count/initial-baseline definition needs verification')
add('R091','HPCS-800-2',5000,73,'2E_symmetric','GCD_unspecified_protocol',None,None,[8,9],voltage_lower_V=0,voltage_upper_V=1.8,provenance_note='Figure 6g; no cycling current borrowed from rate tests')
add('R092','iodine@S-doped SPAC',1000,89.72,'system_pending','GCD',.08,'H2SO4',[8,11],concentration_value=1,concentration_unit='mol/L',conflict=True,provenance_note='p8 cycle current .08 A/g; conclusion .06 A/g describes efficiency/retention together; protocol review required')
add('R093','PR-2',10000,108.8,'2E_symmetric','GCD',5,'KOH',[3,10,12],concentration_value=6,concentration_unit='mol/L',provenance_note='Figure 8e; activation >100% is retained, not clipped')
add('R103','LAC800-4',10000,96.1,'2E_symmetric','GCD',20,'KOH',[7,8,9],concentration_value=6,concentration_unit='mol/L',value_kind='100_minus_reported_loss',provenance_note='100 - reported 3.9% loss = 96.1%; repeated embedded page text counted once')
add('R104','SSC-Na3C6H5O7-KCl-1.5-1.5L-850',20000,98.4,'2E_symmetric','GCD',10,'sodium_acetate',[11],retention_sd_pct=.3,provenance_note='Figure 10; reported mean +/- .3, repeats not independent materials')
add('R105','GCK-3',10000,100,'2E_symmetric','GCD',2,None,[7],retention_relation='approx',provenance_note='close to 100%, not exact; Figure 6g')
for sample,r in [('FMC',86.82),('FMCA',94.89)]:
    add('R106',sample,5000,r,'2E_symmetric','GCD',None,None,[15],provenance_note='Figure 11; cycle current not given in extracted caption; not borrowed from other GCD curves')
add('R107','DUGPC',10000,95.5,'2E_symmetric','GCD',5,'KOH',[3,7,8],concentration_value=6,concentration_unit='mol/L',BET_m2_g=3006,total_pore_volume_cm3_g=1.779,provenance_note='Figure 6d; same material as 20000-cycle endpoint')
add('R107','DUGPC',20000,94.9,'2E_symmetric','GCD',None,'KOH',[8],concentration_value=6,concentration_unit='mol/L',BET_m2_g=3006,total_pore_volume_cm3_g=1.779,provenance_note='Figure S11; cycle current to be checked in local SI, not copied from Figure 6d')
for sample,r in [('CTW',81.5),('CRTW-1',92),('CRTW-2',97.1),('CRTW-3',98.9)]:
    add('R108',sample,12000,r,'3E','GCD_protocol_wording_issue',None,None,[8,10],current_density_mA_cm2=50,provenance_note='paper calls 50 mA/cm2 a scan rate; preserve areal current, no conversion to A/g')
add('R108','CRTW-3',15000,92,'2E_symmetric','GCD_unspecified_protocol',None,None,[8,9],provenance_note='Figure 6e; cycle current needs plot/method confirmation')
add('R111','ACK-700',2000,89.44,'2E_symmetric','GCD',1,None,[8])
add('R112','Act_OFSCBC',1000,100,'3E','GCD',6,'H2SO4',[9,11,12],concentration_value=1,concentration_unit='mol/L')
for n,r in [(5000,90.77),(10000,74.4)]:
    add('R112','Act_OFSCBC',n,r,'2E_symmetric','GCD',6,'H2SO4',[10,11,13],concentration_value=1,concentration_unit='mol/L',voltage_lower_V=0,voltage_upper_V=1,provenance_note='Figure 11c; shared curve and material, not independent samples')
for sample in ['ACRS-700','ACEW-700']:
    add('R117',sample,8000,None,'3E','GCD',10,'NaCl',[3,10,11],concentration_value=2,concentration_unit='mol/L',provenance_note='Figure 7G; >initial qualitative, numerical endpoint requires digitization')
add('SRC025','AC3',10000,91,'3E','GCD',20,None,[7,9],provenance_note='Figure 6d; 93% is Coulombic efficiency, not retention')
for sample,r in [('ZK-S',105),('ZK-C',104),('ZN-S',102.8),('ZN-C',102.5),('NK-S',100.6),('NK-C',96.9)]:
    add('SRC028',sample,10000,r,'2E_symmetric','GCD',.4,None,[8],provenance_note='Figure 6e; salt residue/metal involvement explicitly unresolved, no assumption of metal-free carbon',material_scope='carbon_metal_residue_pending')
add('SRC035','O-PC-700C',10000,100,'2E_symmetric','GCD',5,None,[8],BET_m2_g=938.6,provenance_note='Figure 8g; electrolyte/system context requires confirmation')
add('SRC093','AC3',1000,78,'2E_symmetric','GCD',None,'KOH',[3,4,12],retention_relation='approx',concentration_value=2,concentration_unit='mol/L',provenance_note='Figure 8d; methods reports 2.0 mA/cm^-1 rather than area unit; current unit unresolved')
add('SRC112','CSK-750-2',10000,106,'2E_symmetric','GCD',10,None,[10,11],retention_relation='approx')
add('SRC120','Z7',4500,79,'2E_symmetric','GCD',5,None,[15,16])
add('SRC121','DSAC',2000,83.3,'3E','GCD',10,'KOH',[3,7],concentration_value=1,concentration_unit='mol/L',mass_loading_mg_cm2=.5,provenance_note='Figure 5d; 450 F/g estimated full device is excluded; potentials vs RHE/HgHgO need explicit reference mapping')

# B: separate systems, pure-carbon controls remain visible.
add('R001','HDP-AC',15000,98.2,'2E_symmetric','GCD',1.3,'H2SO4',[11],concentration_value=1,concentration_unit='mol/L',material_scope='carbon_originality_pending',provenance_note='check overlap with earlier authors samples; never import second-hand S1')
for sample,r,rel in [('AC',89,'approx'),('ACN',99,'gt'),('ACP',92,'approx')]:
    add('R020',sample,5000,r,'2E_symmetric','GCD',3,'KNO3',[12,13,17],retention_relation=rel,concentration_value=1,concentration_unit='mol/L',material_scope='carbon_control' if sample=='AC' else 'metal_or_polymer_composite')
add('R020','ACN//AC',5000,86,'2E_asymmetric','GCD',3,'KNO3',[15,16,17],retention_relation='gt',concentration_value=1,concentration_unit='mol/L',voltage_lower_V=0,voltage_upper_V=1.8,material_scope='metal_composite',conflict=True,provenance_note='main text >86%; conclusion ambiguous >75%; do not force single number')
add('R024','DHPAC//HPAC',5000,94.5,'2E_asymmetric','GCD',1,None,[14,15,16],voltage_lower_V=0,voltage_upper_V=1.5,material_scope='Ti_composite')
add('R035','WS-dAC/NiO-0.01',2000,98,'system_pending','GCD',1,None,[9],retention_relation='approx',voltage_lower_V=0,voltage_upper_V=.9,material_scope='NiO_composite',baseline_cycle=100,provenance_note='~98% from cycle 100 to 2000, not first-cycle baseline')
for sample,r,scope in [('CGBC',64.8,'carbon_control'),('Ni(OH)2-CGBC_10mM',55.9,'Ni_composite')]:
    add('R042',sample,1000,r,'3E','GCD',1,None,[8,9],material_scope=scope)
add('R043','Ni@MCTAC',10000,89,'3E','GCD',2,'H2SO4',[8,10,11],concentration_value=1,concentration_unit='mol/L',material_scope='Ni_CNT_composite',provenance_note='89% from summary table/conclusion; text also gives 513->490 F/g at 8000, different endpoint')
add('R043','Ni@MCTAC//AC-CTB',10000,88,'2E_asymmetric_gel','GCD',4,'PVA-H2SO4',[11],voltage_lower_V=0,voltage_upper_V=.8,material_scope='Ni_CNT_composite',provenance_note='5000 bending repetitions and their retention values are excluded')
add('R045','RSM-0.33-550',5000,96.3,'3E','GCD',20,None,[3,8,10],conflict=True,material_scope='carbon_field_freeze',provenance_note='existing high-current/unit freeze remains effective; cycling uses affected 20 A/g condition')
add('R047','FAPC-10_device',5000,78,'2E_asymmetric','GCD_unspecified_protocol',None,None,[4],material_scope='Fe_composite',provenance_note='Figure S10 not available locally; cycle current pending')
add('R048','Sm-doped MS-AC',3000,71.91,'3E','GCD',None,None,[11],retention_relation='gt',material_scope='Sm_composite',provenance_note='p11 mentions 6500th cycle and then >71.91% at 3000; do not equate without curve check',conflict=True)
add('R056','GPBC/NMS',10000,90,'3E','GCD',5,'KOH',[8],concentration_value=3,concentration_unit='mol/L',material_scope='Ni_Mo_sulfide_composite')
add('R056','GPBC/NMS//GPBC',10000,93,'2E_asymmetric','GCD',5,'KOH',[9],concentration_value=3,concentration_unit='mol/L',voltage_lower_V=0,voltage_upper_V=1.6,material_scope='Ni_Mo_sulfide_composite')
add('R081','Fe-SN6C@900',None,102,'3E','GCD',5,None,[10],retention_relation='approx',material_scope='Fe_involvement_pending',provenance_note='cycle count only in plot; not entered from visual guess')
add('R097','BCRCA',5000,93,'3E','GCD',2,None,[6,7,8],material_scope='RGO_composite',provenance_note='100 mechanical cycles and 3500 strain-sensing cycles are excluded')
for n,r in [(5000,72),(10000,63.6)]:
    add('SRC101','15%-Fe-ZnO/AC_coin',n,r,'2E_asymmetric','GCD',1,'H2SO4',[11,14],concentration_value=1,concentration_unit='mol/L',material_scope='Fe_ZnO_composite')
for n,r in [(5000,55.7),(10000,34.9)]:
    add('SRC101','15%-Fe-ZnO/AC_flexible',n,r,'2E_asymmetric_gel','GCD',None,'PVA-H2SO4',[14,15],material_scope='Fe_ZnO_composite',provenance_note='flat device; cycle current needs Figure 11c; 45deg bend electrochemical tests separate')
for n,r in [(1500,56.5),(3000,15.2)]:
    add('SRC101','15%-Fe-ZnO/AC_flexible',n,r,'2E_asymmetric_gel','GCD',None,'PVA-H2SO4',[15],material_scope='Fe_ZnO_composite',test_tag='45deg_bent',bending_angle_deg=45,provenance_note='electrochemical cycles under fixed 45deg bend, not mechanical bending-cycle count')
for sample,r in [('AC600',81.50),('AC650',84.61),('AC700',85.69)]:
    add('SRC115',sample,3000,r,'Li_half_cell','GCD',.5,None,[9],material_scope='Li_capacitor_half_cell',baseline_definition='post_initial_activation_stabilized_capacity',provenance_note='capacity mAh/g; post-stabilization baseline; YP50 commercial control excluded')

def enrich(pid,sample=None,system=None,provenance='',**fields):
    for row in rows:
        if row['paper_id']==pid and (sample is None or row['sample']==sample) and (system is None or row['system']==system):
            row.update(fields)
            for field in fields: row['input_provenance'][field]=provenance

enrich('R032',provenance='main p5 Table 1; main p6 XPS conclusion',BET_m2_g=627,total_pore_volume_cm3_g=.6264,N_at_pct=7.43,O_at_pct=13.98)
enrich('R032',system='3E',provenance='main p3',electrolyte='KOH',concentration_value=6,concentration_unit='mol/L')
enrich('R032',system='2E_symmetric',provenance='main p5-6',electrolyte='Na2SO4',concentration_value=1,concentration_unit='mol/L',voltage_lower_V=0,voltage_upper_V=1.8)
enrich('R033',system='2E_symmetric',provenance='main p5, visual Figure 5',voltage_lower_V=0,voltage_upper_V=1)
enrich('R036',provenance='main p4 Table 1',total_pore_volume_cm3_g=.4439)
enrich('R069',sample='RCS-AC',provenance='visual main p7-8; figure/prose/table disagreement',conflict=True)
enrich('R091',provenance='main p3 device methods',electrolyte='Li2SO4',concentration_value=.5,concentration_unit='mol/L')
enrich('R093',provenance='main p7 Table 2',BET_m2_g=2035.6,total_pore_volume_cm3_g=1.4166)
enrich('R103',provenance='main p5-6',BET_m2_g=2285)
enrich('R104',provenance='main p3 methods, p7 Table 3, p11 Figure 10',concentration_value=1,concentration_unit='mol/L',voltage_lower_V=0,voltage_upper_V=1.5,BET_m2_g=1198,total_pore_volume_cm3_g=.86)
enrich('R105',provenance='main p4, p6-8',BET_m2_g=2640,electrolyte='KOH',concentration_value=6,concentration_unit='mol/L',voltage_lower_V=0,voltage_upper_V=1.4,N_wt_pct=.63,O_wt_pct=2.91)
enrich('R106',provenance='main p5 device methods',electrolyte='KOH',concentration_value=3,concentration_unit='mol/L',voltage_lower_V=0,voltage_upper_V=1)
enrich('R106',sample='FMC',provenance='main p9 BET text',BET_m2_g=9.515)
enrich('R106',sample='FMCA',provenance='main p9 BET text',BET_m2_g=14.946,total_pore_volume_cm3_g=.024)
for row in rows:
    if row['paper_id']=='R107' and row['cycle_count']==20000:
        row['current_density_A_g']=5
        row['input_provenance']['current_density_A_g']='local Word SI Figure S11 caption, text lines 641-644'
enrich('R108',system='3E',provenance='main p7',voltage_lower_V=-1,voltage_upper_V=0)
enrich('R111',provenance='main p6 Tables 1 and 2',BET_m2_g=2768,total_pore_volume_cm3_g=1.312,N_at_pct=.2,O_at_pct=15.7)
enrich('R112',provenance='main p5 Table 1',BET_m2_g=2538.31,total_pore_volume_cm3_g=1.63)
enrich('SRC025',provenance='main p3 methods and p6 Table 1',electrolyte='KOH',concentration_value=2,concentration_unit='mol/L',BET_m2_g=2333.4,total_pore_volume_cm3_g=2.625)
enrich('SRC028',provenance='main p3 methods, p8 device tests',electrolyte='KOH',concentration_value=6,concentration_unit='mol/L',voltage_lower_V=0,voltage_upper_V=1)
enrich('SRC035',provenance='main p7-8 Figure 8c-h caption; visually verified',electrolyte='Na2SO4',concentration_value=1,concentration_unit='mol/L',voltage_lower_V=0,voltage_upper_V=2)
enrich('SRC120',provenance='main p4 and p15 device text',electrolyte='KOH',concentration_value=6,concentration_unit='mol/L',voltage_lower_V=0,voltage_upper_V=1.4,BET_m2_g=1636,retention_relation='approx',provenance_note='body says 79%; Table p13 says 79.4%; preserve approximate 79 with alternate 79.4',alternate_reported_retention_pct=79.4)
enrich('R042',provenance='main p5-7; main p8-9 stability analysis',electrolyte='KOH',concentration_value=1,concentration_unit='mol/L')

# Device formats and multiple endpoints never create additional independent materials.
canonical={('R020','ACN//AC'):'ACN',('R024','DHPAC//HPAC'):'DHPAC',
           ('R043','Ni@MCTAC//AC-CTB'):'Ni@MCTAC',('R047','FAPC-10_device'):'FAPC-10',
           ('R056','GPBC/NMS//GPBC'):'GPBC/NMS'}
for row in rows:
    row['configuration_id']=row['material_id']
    canonical_sample=canonical.get((row['paper_id'],row['sample']),row['sample'])
    if row['paper_id']=='SRC101': canonical_sample='15%-Fe-ZnO/AC'
    row['material_id']=row['paper_id']+'::'+canonical_sample
    row['independent_material_identity_finalized']=False
    row['field_status']={k:('recorded_from_cited_source' if row.get(k) is not None else 'not_yet_paired_or_not_found_in_local_evidence') for k in [
        'current_density_A_g','electrolyte','concentration_value','voltage_lower_V','voltage_upper_V',
        'BET_m2_g','total_pore_volume_cm3_g','N_at_pct','O_at_pct','temperature_C','mass_loading_mg_cm2']}
    if row['paper_id']=='R069': row['provenance_note']+='; Figure 6 absolute-capacitance start/end also needs independent check; no plotted ratios substituted'
    if row.get('supplement_index'):
        row['evidence_path']=sources[row['paper_id']]['supplements'][row['supplement_index']-1]
    else:row['evidence_path']=row['pdf']
    row['short_test']=row['cycle_count'] is not None and row['cycle_count']<1000
    row['point_label']=row['retention_pct'] is not None and row['retention_relation'] in ['eq','approx']
    row['condition_basic_complete']=all(row.get(k) is not None for k in ['cycle_count','retention_pct','current_density_A_g','electrolyte','concentration_value']) and row['method']=='GCD' and row['system'] in ['3E','2E_symmetric']
    row['voltage_complete']=all(row.get(k) is not None for k in ['voltage_lower_V','voltage_upper_V'])
    row['candidate_clean']=row['point_label'] and not row['conflict'] and not row['short_test'] and row['material_scope'] in ['carbon_candidate','carbon_control']
    row['provisional_core_conditions']=row['candidate_clean'] and row['condition_basic_complete']
    row['provisional_minimal_features']=row['provisional_core_conditions'] and row['BET_m2_g'] is not None and row['total_pore_volume_cm3_g'] is not None and row['voltage_complete']
(OUT/'循环稳定性逐记录候选.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'endpoint_rows':len(rows),'papers':len({x['paper_id'] for x in rows}),
                 'material_keys':len({x['material_id'] for x in rows}),
                 'clean_point_candidates':sum(x['candidate_clean'] for x in rows),
                 'core_conditions':sum(x['provisional_core_conditions'] for x in rows),
                 'minimal_features':sum(x['provisional_minimal_features'] for x in rows)},ensure_ascii=False,indent=2))
