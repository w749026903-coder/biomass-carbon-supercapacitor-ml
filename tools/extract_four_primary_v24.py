"""One-use, literal-cell extraction of four existing biomass studies; no fitting."""
from pathlib import Path
from contextlib import closing
import json,re,sqlite3,sys,xml.etree.ElementTree as E
import pdfplumber
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tools'))
from extract_onion_composite_v8 import sha,write,ro,insert,mk
from extract_palm_kernel_v7 import xml_grid
from extract_source_series_v13 import clean
from extract_peer_feather_v23 import numeric_details as previous_details
OUT=ROOT/'文献全量利用复核_20261028/批次24_糠醛渣食物气凝胶柚皮与麦壳全样品'
DB=OUT/'literature_material_pool_v24.sqlite'
PARENT=ROOT/'文献全量利用复核_20261028/批次23_同体系机器学习蜜瓜皮鹅羽与综述对账/literature_material_pool_v23.sqlite'
PSHA='f200c54a1430c09e2a2ab00628d27524ba0bdae76841aa4a5d3b84074f20a9fa'
CYCLE=ROOT/'循环稳定性数据库_v0.27_林业含灰双电极准入_20261028/cycling_v0_27.sqlite';CSHA='9c5689c6b7806f64f3fbe51b469e23efff2fa508626e94287a792a9c7bdf555e'
NATIVE=ROOT/'全库复检与特征补提取_20261021/full_corpus_search_native.sqlite'
FR='10.3390/polym15193976';FW='10.3390/nano15050387';NS='10.3390/ma16134577';HP='10.3390/nano12213804'
KEYS={FR:'FR24',FW:'FW24',NS:'NS24',HP:'HP24'}
TARGETS=('reported_aqueous_3e_GCD_capacitance','food_waste_2e_author_capacity','grapefruit_2e_author_capacity','wheat_husk_2e_factor4_total_active_mass_Cs')

def numeric_details(raw):
    token=str(raw).strip()
    if token in ['','-','--','−','–','—']:return dict(raw_token=raw,value=None,kind='author_unreported_dash',not_zero=True)
    m=re.fullmatch(r'(\d+(?:\.\d+)?)\s*\((wheat husk|carbon|salt|KOH)\)',token)
    if m:return dict(raw_token=raw,value=float(m[1]),kind='scalar_with_explicit_material_annotation',material_annotation=m[2])
    if re.fullmatch(r'\d+\.',token):return dict(raw_token=raw,value=float(token),kind='author_trailing_decimal_point')
    return previous_details(raw)
def number(raw):return numeric_details(raw)['value']

def curate():
    assert sha(PARENT)==PSHA and sha(CYCLE)==CSHA and not DB.exists()and not(OUT/'curation_spec.json').exists()and not(OUT/'merge_manifest.json').exists()
    notes=json.loads((OUT/'source_review_notes.json').read_text('utf8'));spec={k:[]for k in ['sources','documents','tables','units','materials','facts','caps','responses','synthesis','decisions','feature_decisions','figures','candidates','annotations','identity_links','raw_dispositions','lineage','protocol_reviews','inspection']};roots={};docs={}
    def doc(key,doi,path,role):
        p=ROOT/path;assert p.is_file();d=dict(key=key,doi=doi,path=path,sha256=sha(p),role=role);spec['documents'].append(d);docs[key]=d
    with closing(ro(NATIVE))as c:
        c.row_factory=sqlite3.Row
        for s in notes['sources']:
            p=ROOT/s['path'];assert sha(p)==s['sha256'];r=E.parse(p).getroot();doi=s['doi'];roots[doi]=r
            assert {clean(x).lower()for x in r.findall('./front/article-meta/article-id')if x.get('pub-id-type')=='doi'}=={doi}
            years={int(x.text)for x in r.findall('./front/article-meta/pub-date/year')};spec['sources'].append(dict(s,year=max(years),classification='original_biomass_carbon_with_explicit_protocol_disputes'if doi in [FR,NS]else'original_biomass_carbon'));doc(s['key'],doi,s['path'],'primary_XML')
            raw={x['locator']:x['table_id']for x in c.execute('select table_id,locator from raw_tables_v11 where source_sha256=?',(s['sha256'],))}
            for t in r.findall('.//table-wrap'):
                loc='XML table-wrap '+t.get('id');spec['tables'].append(dict(doi=doi,id=t.get('id'),document=s['key'],locator=loc,caption=clean(t.find('caption')),footnote=clean(t.find('table-wrap-foot')),grid=xml_grid(t),raw_table_id=raw[loc],kind='native_XML_own_rows_with_foreign_context_retained'))
    for r in json.loads((OUT/'figure_scope_inventory.json').read_text('utf8')):
        if not r['path']:continue
        assert r['scope_visually_inspected'];n=int(re.search(r'\d+',r['printed_label'])[0]);key=r['key']+'_Fig'+str(n);doc(key,r['doi'],r['path'],'original_main_figure')
        spec['figures'].append(dict(r,figure_number=n,document=key,scope_visually_inspected=True,full_waveform_extracted=False))
    inv=json.loads((OUT/'local_document_inventory.json').read_text('utf8'));d=inv['documents'][0];doc(d['key'],FW,d['path'],'own_SI_PDF')
    def unit(doi,id,head,rows,loc,document=None,kind='own_prose_or_printed_label_transcription'):
        spec['units'].append(dict(doi=doi,id=id,header=head,rows=[[str(v)for v in row]for row in rows],locator=loc,document=document or KEYS[doi],kind=kind));return id
    def fact(doi,s,id,row,col,f,un,met,status='own_stage_method_qualified'):spec['facts'].append(dict(doi=doi,sample=s,id=id,row=row,col=col,field=f,unit=un,method=met,status=status))
    def reg(doi,s,stage,feed):spec['materials'].append(dict(doi=doi,sample=s,stage=stage,feedstock=feed))
    def cap(doi,s,id,row,col,j,purpose=None,**cond):spec['caps'].append(dict(doi=doi,sample=s,id=id,row=row,col=col,j=j,purpose=purpose,method='GCD',scan=None,conditions=cond))
    def resp(doi,s,id,row,col,f,un,**cond):spec['responses'].append(dict(doi=doi,sample=s,id=id,row=row,col=col,metric=f,unit=un,conditions=cond))
    def synth(doi,s,stages,loc):spec['synthesis'].append(dict(doi=doi,sample=s,document=KEYS[doi],locator=loc,stages=stages))
    def issue(doi,id,evidence,decision):spec['decisions'].append(dict(id='V24_'+id,doi=doi,evidence=evidence,decision=decision,not_author_erratum=True))
    def link(doi,s,eid,evidence):spec['identity_links'].append(dict(doi=doi,sample=s,existing_endpoint_id=eid,evidence=evidence,not_new_cycling_endpoint=True,core_endpoint_unchanged=True))
    # Furfural: complete four-sample table, not just best-performing nitrogenated sample.
    fr=['FRPC','FRPC-Urea','FRPCK','FRPCK-Urea']
    for s in ['Pre-FRPC','Pre-FRPCK','Pre-FRPC-Urea','Pre-FRPCK-Urea']+fr:reg(FR,s,'final_biomass_carbon'if s in fr else'precarbonized_or_urea_feed_mixture_before_final_thermal_step','furfural_industrial_residue')
    for row,s in enumerate(fr,2):
        for col,f,un in [(1,'BET_surface_area_m2_g','m2/g'),(2,'micropore_area_reported_m2_g','m2/g'),(3,'mesopore_area_reported_m2_g','m2/g'),(4,'total_pore_volume_cm3_g','cm3/g'),(5,'micropore_volume_cm3_g','cm3/g'),(6,'mesopore_volume_cm3_g','cm3/g'),(7,'author_mesopore_volume_fraction_pct','%')]:fact(FR,s,'polymers-15-03976-t001',row,col,f,un,'OwnN2BET/BJHporedistribution; compartmentvolume methodnotseparatelydeclared')
        for col,f in enumerate(['XPS_C_reported_pct_basis_unspecified','XPS_N_reported_pct_basis_unspecified','XPS_O_reported_pct_basis_unspecified','XPS_S_reported_pct_basis_unspecified','XPS_C1s_graphitic_envelope_pct','XPS_C1s_CN_CO_envelope_pct','XPS_C1s_CO_envelope_pct','XPS_N1s_pyridinic_envelope_pct','XPS_N1s_pyrrolic_envelope_pct','XPS_N1s_graphitic_envelope_pct','XPS_N1s_oxidic_envelope_pct'],1):fact(FR,s,'polymers-15-03976-t002',row+1,col,f,'%'if col>4 else'%basis_unspecified','OwnXPS; elementalbasisnotexplicit; C/Ncomponents explicitlywithinrespectivepeak, notwholeatomfractions','ambiguous_percent_basis'if col<5 else'own_within_envelope_component')
        koh='K'in s;urea='Urea'in s;parent='Pre-'+s;spec['lineage'].append(dict(doi=FR,parent=parent,child=s,kind='final800Cthermalstep'))
        synth(FR,s,[dict(stage='precarbonization',temperature_C=400,duration_h=1,atmosphere='N2',raw_feedstock_to_KOH_mass_ratio=[1,1 if koh else 0]),dict(stage='second_carbonization',temperature_C=800,duration_h=1,heating_rate_C_min=5,precarbonized_feed_to_urea_mass_ratio=[1,1 if urea else 0],atmosphere='N2',KOH_carried_from_first_stage=koh),dict(stage='wash',HCl_M=2,ethanol=True,water=True,drying_temperature_C=105)],'MainP7; rawfeed/KOH isnotfinalprechar/KOHmass; no inferredsameprecursorSSA')
    u=unit(FR,'four_sample_Raman',['sample','ID_IG'],[[s,v]for s,v in zip(fr,[.8912,.8932,.8678,.9269])],'MainP19/actualFig3a', 'FR24_Fig3')
    for i,s in enumerate(fr,1):fact(FR,s,u,i,1,'Raman_ID_IG','ratio','OwnRaman intensityratio, notarea')
    u=unit(FR,'body_volume_fraction_variants',['sample','reported_ratio'],[['FRPC-Urea',43.70],['FRPCK',19.90],['FRPCK-Urea',25.59]],'MainP18 versusTable1 43.87/19.89/25.48; rawvaluesnotreplacedbyarithmetic')
    for i,s in enumerate(fr[1:],1):fact(FR,s,u,i,1,'author_mesopore_volume_fraction_pct','%','Competingauthorprose; underlyingvolumesretained','conflict_body_table_ratio')
    rows=[[s,f'XPS_C1s_component_{i}_binding_eV',v]for s in fr for i,v in enumerate([284.8,286.1,288.6],1)]+[['FRPCK-Urea',f'XPS_N1s_component_{i}_binding_eV',v]for i,v in enumerate([398.2,400.1,401.2,404.0],1)]+[['FRPC-Urea','raw_prose_misattributed_Vmeso_cm3_g',.2541]]
    u=unit(FR,'own_peak_positions_and_misattribution',['sample','metric','value'],rows,'MainP23specificpeakpositions; MainP18Vmeso.2541misnamesFRPCUrea whilealsoquotingits.0397')
    for i,(s,f,v)in enumerate(rows,1):fact(FR,s,u,i,2,f,'eV'if 'binding'in f else'cm3/g','Own literalreport; rawmisattributedprosenotcanonicalporosity','ambiguous_prose_sample_binding'if i==17 else'own_stage_method_qualified')
    u=unit(FR,'own_GCD_half_A_g',['sample','C','j'],[[s,c,.5]for s,c in zip(fr,[50.23,77.11,147.6,222.7])],'MainP25/actualFig4b, caption1M vsMethods6M')
    for i,s in enumerate(fr,1):
        cap(FR,s,u,i,1,.5,None,system='3E',electrolyte='KOH',concentration_mol_L=None,voltage_lower_V=-1,voltage_upper_V=0,reference_electrode='Hg/HgO',binder='PVDF',capacitance_basis='I_dt_over_working_active_m_dV',physical_test_group='doi:'+FR+'#'+s+'#3EGCD0.5',concentration_claims_mol_L=[1,6],concentration_status='conflict_method6M_vs_result_and_caption1M',cross_source_comparable=False)
        spec['inspection'].append(dict(doi=FR,sample=s,id=u,row=i,col=1,purpose='furfural_concentration_disputed_inspection',training_input_ready=False))
    u=unit(FR,'resistance_and_rate',['sample','value'],[[s,v]for s,v in zip(fr,[.1412,.1649,.1861,.1411])]+[['FRPCK-Urea',81.90]],'MainP27unspecifiedresistance/P30rate, notlifetime')
    for i,s in enumerate(fr,1):resp(FR,s,u,i,1,'author_EIS_resistance_role_unselected','ohm',not_intrinsic_conductivity=True)
    resp(FR,'FRPCK-Urea',u,5,1,'current_rate_retention_pct','%',current_from_A_g=.5,current_to_A_g=20,not_cycling_lifetime=True)
    # Food waste: raw dry-basis chemistry stays separate from four final carbons.
    fw=['FWCA-3','FWCA-4','FWCA-5','FWPC']
    for s in ['simulated food waste','food waste hydrogel','freeze dried food aerogel','CA before KOH']+fw:reg(FW,s,'final_gel_assisted_biomass_carbon'if s in fw[:3]else'final_non_gel_biomass_carbon'if s=='FWPC'else'raw_or_gel_or_precarbonized_stage','proportioned_vegetable_rice_and_meat_food_waste')
    for col,f in enumerate(['raw_moisture_wt_pct','raw_dry_ash_wt_pct','raw_dry_volatiles_wt_pct','raw_bulk_EA_C_dry_wt_pct','raw_bulk_EA_H_dry_wt_pct','raw_bulk_EA_N_dry_wt_pct','raw_bulk_EA_S_dry_wt_pct','raw_O_by_difference_dry_wt_pct']):fact(FW,'simulated food waste','nanomaterials-15-00387-t001',3,col,f,'wt%','OwnTable1drybasisexceptmoisture; Osubtraction; stated±error typeunknown, at leasttwomeasurements notassumedSD')
    for row,s in enumerate(fw,2):
        for col,f in enumerate(['BET_surface_area_m2_g','total_pore_volume_cm3_g','HK_micropore_volume_cm3_g','mesopore_volume_cm3_g','author_micropore_volume_fraction'],1):fact(FW,s,'nanomaterials-15-00387-t002',row,col,f,'m2/g'if col==1 else'ratio'if col==5 else'cm3/g','OwnTable2: BET,P/P0.990total,HKmicro; mesovolume methodunspecified, no assumedexhaustivepartition')
        gel=s!='FWPC';ratio=4 if s=='FWPC'else int(s[-1]);stages=[]
        if gel:stages.extend([dict(stage='gelation',raw_food_waste_g=30,water_mL=120,temperature_C=70,KPS_mmol_L=2,acrylic_acid_g=.005,MBA_g=.005,synthetic_additives_not_final_composition=True),dict(stage='freeze_drying',temperature_C=-45,duration_h=48)])
        stages.extend([dict(stage='microwave_carbonization',temperature_C=700,duration_min=5,heating_rate_C_min=45,atmosphere='N2',equipment_available_power_W=2000,actual_power_W=None,frequency_MHz=2450),dict(stage='chemical_activation',temperature_C=700,duration_min=20,heating_mode='microwave',activator='KOH',carbon_to_activator_mass_ratio=[1,ratio],atmosphere='N2'),dict(stage='wash',HCl_M=2,water_to_neutral=True)])
        synth(FW,s,stages,'MainP6..7; FWPComitsgel, lyophilizationnotassumed; 2kWavailableequipmentpowernotactualpower')
        if gel:spec['lineage'].append(dict(doi=FW,parent='CA before KOH',child=s,kind='KOHmicrowaveactivation'))
    u=unit(FW,'own_scalar_features',['sample','metric','value'],[['FWCA-4','Raman_IG_ID',1.25],['FWPC','Raman_IG_ID',1.02],['FWCA-4','XPS_C_reported_pct_basis_unspecified',89.69],['FWCA-4','XPS_O_reported_pct_basis_unspecified',9.31],['FWCA-4','XPS_N_reported_pct_basis_unspecified',.85],['FWCA-4','TEM_graphite_fringe_spacing_nm',.34],['FWCA-4','DFT_pore_peak_1_nm',.67],['FWCA-4','DFT_pore_peak_2_nm',1.21],['FWCA-4','DFT_pore_peak_3_nm',1.97],['FWCA-4','DFT_pore_peak_4_nm',2.49],['FWCA-4','raw_prose_pore_volume_m3_g',.634]],'MainP10..13 andconclusion; rawm3/gproseconflictswithTable2cm3/g')
    for i,row in enumerate(next(x for x in spec['units']if x['id']==u)['rows'],1):
        s,f,_=row;fact(FW,s,u,i,2,f,'ratio'if f.startswith('Raman')else'%basis_unspecified'if f.startswith('XPS')else'm3/g_as_printed'if f.startswith('raw_')else'nm','Ownsamplemethod-bound claim; no rawEAinheritance','ambiguous_percent_basis'if f.startswith('XPS')else'conflict_prose_unit'if f.startswith('raw_')else'own_stage_method_qualified')
    rows=[[f'XPS_{el}_component_{i}_binding_eV',v]for el,vs in [('C1s',[284.72,285.51,287.1,289.3]),('O1s',[532.25,533.25,534.2]),('N1s',[398.6,400.3,401.25])]for i,v in enumerate(vs,1)]
    u=unit(FW,'FWCA4_printed_peak_positions',['metric','binding_eV'],rows,'ActualFig3b/c/d printedpeakpositions; N6/N5/N4 rawlabels retained, no speciesfractionderived','FW24_Fig3')
    for i,(f,v)in enumerate(rows,1):fact(FW,'FWCA-4',u,i,1,f,'eV','Ownactualprintedbindingposition, notwholeelementcontent')
    u=unit(FW,'own_rate_capacity',['sample','C','j'],[['FWCA-4',322.8,.5],['FWCA-4',314.4,1],['FWCA-4',243,20],['FWCA-4',314,1],['FWCA-4',49.7,.2]],'MainP17/18/20 andconclusion314rounded; 3EactualFig6/7 -1..0, deviceFig8 0..1.8')
    for i,j in enumerate([.5,1,20,1,.2],1):
        device=i==5;cap(FW,'FWCA-4',u,i,1,j,TARGETS[1]if device else TARGETS[0]if i<4 else None,system='2E_symmetric'if device else'3E',electrolyte='Na2SO4'if device else'KOH',concentration_mol_L=1 if device else 6,voltage_lower_V=0 if device else-1,voltage_upper_V=1.8 if device else 0,reference_electrode=None,reference_status='not_in_current_or_accessed_cited_method_metadata',binder=None,capacitance_basis='author_two_electrode_mass_scope_not_verified'if device else'author_reported_working_active_mass',physical_test_group='doi:'+FW+'#FWCA-4#'+('2E'if device else'3E')+'#GCD'+str(j),cross_source_comparable=not device,report_kind='rounded_repeat'if i==4 else'own_reported')
    with pdfplumber.open(ROOT/docs['FW24_SI']['path'])as pdf:raw=pdf.pages[1].extract_text()
    assert 'FWCA-4'in raw and '1470'in raw and '314'in raw
    u=unit(FW,'SI_TableS1_own_row',['sample','SSA','C','j'],[['FWCA-4',1470,314,1]],'SIp2TableS1lastownrow:1470/6MKOH/314(1.0Ag); allforeignrowscontextonly','FW24_SI','own_SI_comparison_row_transcription')
    fact(FW,'FWCA-4',u,1,1,'BET_surface_area_m2_g','m2/g','OwnSIrepeat ofmainTable2, notnewmeasurement')
    cap(FW,'FWCA-4',u,1,2,1,None,system='3E',electrolyte='KOH',concentration_mol_L=6,capacitance_basis='author_reported_working_active_mass',physical_test_group='doi:'+FW+'#FWCA-4#3E#GCD1',cross_source_comparable=True,report_kind='rounded_repeat_of_MainP17_314.4')
    u=unit(FW,'own_response_values',['sample','value','metric'],[['FWCA-4',.77,'combined_resistance'],['FWCA-4',24.7,'rate_loss'],['FWPC',33.2,'rate_loss'],['FWCA-4',22.35,'device_energy'],['FWCA-4',179.9,'device_power'],['FWCA-4',6.1,'device_energy'],['FWCA-4',5500.5,'device_power'],['FWCA-4',179.9,'raw_claimed_energy_with_power_unit'],['FWCA-4',.05,'IR_drop10'],['FWCA-4',.008,'IR_drop1'],['FWCA-4',.15,'IR_drop20']],'MainP16..20; abstract/conclusionenergy179.9Wkgcontradictionpreserved, actualFig8denergy/poweraxes supportdetailedpair')
    for i,row in enumerate(next(x for x in spec['units']if x['id']==u)['rows'],1):resp(FW,row[0],u,i,1,row[2],'ohm'if i==1 else'%'if i<4 else'Wh/kg'if i in [4,6]else'W/kg'if i<9 else'V',not_pretest_predictor=True,raw_role_conflict=i==8)
    # Grapefruit: preserve calomel/HgHgO and nominal sample name versus actual Kelvin protocol.
    reg(NS,'NSOC-800','final_biomass_carbon','grapefruit_peel')
    synth(NS,'NSOC-800',[dict(stage='single_carbonization_activation',temperature_K=873,temperature_C=None,duration_h=2,atmosphere='N2',raw_feedstock_g=1,KOH_g=4,raw_feedstock_to_KOH_mass_ratio=[1,4],not_assumed_800C_from_name=True),dict(stage='wash',water=True,drying_temperature_C=80,drying_duration_h=10)],'MainP5explicit873K; no temperature800C report, nameisnottemperature')
    features=[('BET_surface_area_m2_g',1267.913,'m2/g'),('total_pore_volume_cm3_g',.189,'cm3/g'),('Raman_ID_IG',1.31,'ratio')]+[('EDS_'+el+'_wt_pct',v,'wt%')for el,v in [('C',79.34),('S',11.72),('O',7.50),('N',1.44)]]
    features += [(f'XPS_{el}_component_{i}_binding_eV',v,'eV')for el,vs in [('C1s',[284.4,285.2,286.3,288.6]),('N1s',[397.2,400,402.6]),('S2p',[163.8,164.7]),('O1s',[531.4,532.6,533.9])]for i,v in enumerate(vs,1)]
    features += [('Raman_D_position_cm_inv',1350,'cm-1'),('Raman_G_position_cm_inv',1590,'cm-1')]
    u=unit(NS,'own_pretest_features',['sample','metric','value','unit'],[['NSOC-800',f,v,un]for f,v,un in features],'MainP8..9 andactualFig2: D/G1355/1595 vsbody1350/1590; N402.6figureoxidized vsbodygraphitic')
    for i,(f,v,un)in enumerate(features,1):fact(NS,'NSOC-800',u,i,2,f,un,'EDSweightnotXPSatoms; bindingpositionsnotatomicpercent; rawbody/figureassignmentsretained','conflict_peak_position'if f in ['Raman_D_position_cm_inv','Raman_G_position_cm_inv']else'ambiguous_N_component_assignment'if f=='XPS_N1s_component_3_binding_eV'else'own_stage_method_qualified')
    u=unit(NS,'printed_Raman_peak_positions',['sample','metric','value'],[['NSOC-800','Raman_D_position_cm_inv',1355],['NSOC-800','Raman_G_position_cm_inv',1595]],'ActualFig2a printed1355/1595, body1350/1590 retained as separate evidence unit','NS24_Fig2')
    for i,f in enumerate(['Raman_D_position_cm_inv','Raman_G_position_cm_inv'],1):fact(NS,'NSOC-800',u,i,2,f,'cm-1','ActualprintedFig2a, notbodyunit','conflict_peak_position')
    u=unit(NS,'own_GCD_values',['sample','C','j','system'],[['NSOC-800',280,1,'3E'],['NSOC-800',30,10,'3E'],['NSOC-800',24.3,1,'2E'],['NSOC-800',22.5,2,'2E'],['NSOC-800',18.7,5,'2E'],['NSOC-800',18.1,8,'2E'],['NSOC-800',75,'unbound','2E']],'MainP10/12values andactualFig3/4currentlegends; introductory75lacksboundcurrent')
    for i,j in enumerate([1,10,1,2,5,8,None],1):
        device=i>2;cap(NS,'NSOC-800',u,i,1,j,TARGETS[0]if not device else TARGETS[2]if i<7 else None,system='2E_symmetric'if device else'3E',electrolyte='KOH',concentration_mol_L=6,voltage_lower_V=0 if device else-1,voltage_upper_V=1.2 if device else 0,reference_electrode=None,reference_status='method_calomel_vs_3E_axes_HgHgO',reference_claims=['calomel','Hg/HgO'],binder='PVDF',mass_loading_mg_cm2=4,capacitance_basis='author_two_electrode_C_mass_scope_unresolved'if device else'I_dt_over_working_active_m_dV',physical_test_group='doi:'+NS+'#NSOC-800#'+('2E'if device else'3E')+'#GCD'+str(j),cross_source_comparable=not device,reference_conflict_not_resolved=True,intro75_unbound_context=i==7,device_axis_HgHgO_vs_2E_context=device)
    vals=[100,100,96.4,93,90.8,97.3,93.7,92.4,90.9,.58,1.2,5,473,.003,.0038]
    u=unit(NS,'own_responses',['sample','value'],[['NSOC-800',v]for v in vals],'MainP3/10..12; CEisnotretention; averagepercyclelossclaimnotexponentialdecayrate')
    for i in range(1,16):resp(NS,'NSOC-800',u,i,1,'coulombic_efficiency'if i<10 else'EIS_Rct'if i<12 else'device_energy'if i==12 else'device_power'if i==13 else'author_average_per_cycle_capacitance_loss','%'if i<10 or i>13 else'ohm'if i<12 else'Wh/kg'if i==12 else'W/kg',system='3E'if i in list(range(1,6))+[10]else'2E_symmetric',not_cycling_retention_label=True,not_pretest_predictor=True)
    # Wheat: final and prechar all seven table rows, including the unactivated nitrogen control.
    hp=['HPC-700','HPC-800','HPC-900','NHPC-700','MHPC-700','MHPC-800','MHPC-900'];reg(HP,'raw wheat husk','raw_biomass','wheat_husk')
    for s in hp:reg(HP,s,'final_activated_biomass_carbon'if s.startswith('HPC')else'precarbonized_before_KOH','wheat_husk')
    order=['MHPC-700','MHPC-800','MHPC-900','NHPC-700','HPC-700','HPC-800','HPC-900']
    for row,s in enumerate(order,2):
        for col,f,un in [(1,'synthesis_stage_input_material_mass_g','g'),(2,'synthesis_stage_salt_or_KOH_mass_g','g'),(3,'synthesis_stage_carbon_product_mass_g','g'),(4,'activation_stage_yield_pct'if s.startswith('HPC')else'precarbonization_stage_yield_pct','%')]:fact(HP,s,'nanomaterials-12-03804-t001',row,col,f,un,'Ownstage-specific yield; HPCyieldparentcarbon-to-activated, MHPC/NHPCyieldrawwheathusk-to-prechar')
    for row,s in enumerate(hp,2):
        for col,f in enumerate(['BET_surface_area_m2_g','total_pore_volume_cm3_g','tplot_micropore_volume_cm3_g','mesopore_volume_cm3_g'],1):fact(HP,s,'nanomaterials-12-03804-t002',row,col,f,'m2/g'if col==1 else'cm3/g','N2BET P/P0.03..0.30; total.990;tplotmicro; NLDFTcylinder/slitPSD; mesovolumemethodunspecified')
        if s.startswith('HPC'):
            pre='M'+s;t=int(s[-3:]);spec['lineage'].append(dict(doi=HP,parent=pre,child=s,kind='KOH800Cactivation'))
            synth(HP,s,[dict(stage='salt_sealed_precarbonization',temperature_C=t,duration_h=1,atmosphere='air',raw_wheat_husk_g=4,KCl_g=8,NaCl_g=8,not_inferred_final_residue=True),dict(stage='chemical_activation',temperature_C=800,duration_h=1,atmosphere='N2',activator='KOH',carbon_to_activator_mass_ratio=[1,2]),dict(stage='wash',HCl_M=3,water_to_pH=[6,7],drying_temperature_C=80)],'MainP5; suffixprecarbonizationtemperature notKOHactivationtemperature; no inheritedprecharproperties')
    u=unit(HP,'own_XPS',['sample','C_at_pct','O_at_pct'],[[s,c,o]for s,c,o in zip(hp[:3],[89.34,89.98,90.56],[10.66,10.02,9.44])],'MainP12 explicitatomicpercent')
    for i,s in enumerate(hp[:3],1):
        for col,el in [(1,'C'),(2,'O')]:fact(HP,s,u,i,col,'XPS_'+el+'_at_pct','at%','OwnsurfaceXPS, no precursorsorunreportedNassumed')
    u=unit(HP,'HPC700_binding_positions',['sample','metric','value'],[['HPC-700',f'XPS_C1s_component_{i}_binding_eV',v]for i,v in enumerate([284.5,285.8,287.8],1)]+[['HPC-700',f'XPS_O1s_component_{i}_binding_eV',v]for i,v in enumerate([532.8,531.6],1)],'MainP12; originalFig4unobtained, prosepositionsonly')
    for i,row in enumerate(next(x for x in spec['units']if x['id']==u)['rows'],1):fact(HP,'HPC-700',u,i,2,row[1],'eV','OwnMainP12, not falselyclaimedoriginalfigureinspection')
    rows=[[s,c,j,'3E']for j,cs in [(1,[402,210,199]),(20,[346,134,122])]for s,c in zip(hp[:3],cs)]+[['HPC-700',346,1,'2E'],['HPC-700',262,20,'2E']]
    u=unit(HP,'own_GCD_reports',['sample','C','j','system'],rows,'MainP15/16/18; 3E vs2E346are distinct tests andnormalizations')
    for i,(s,c,j,sy)in enumerate(rows,1):cap(HP,s,u,i,1,j,TARGETS[0]if sy=='3E'else TARGETS[3],system='3E'if sy=='3E'else'2E_symmetric',electrolyte='H2SO4',concentration_mol_L=1,voltage_lower_V=0 if sy=='3E'else None,voltage_upper_V=1 if sy=='3E'else None,reference_electrode='Ag/AgCl'if sy=='3E'else None,binder='PTFE',mass_loading_mg_cm2=3,capacitance_basis='I_dt_over_working_active_m_dV'if sy=='3E'else'4I_dt_over_total_two_electrode_active_m_dV',physical_test_group='doi:'+HP+'#'+s+'#'+sy+'GCD'+str(j),cross_source_comparable=sy=='3E',device_window_not_inherited_from_3E=sy!='3E')
    cap(HP,'HPC-700','nanomaterials-12-03804-t003',2,1,1,None,system='3E',electrolyte='H2SO4',concentration_mol_L=1,capacitance_basis='I_dt_over_working_active_m_dV',physical_test_group='doi:'+HP+'#HPC-700#3EGCD1',cross_source_comparable=True,report_kind='own_comparison_table_repeat')
    vals=[[s,v,'EIS_Rct']for s,v in zip(hp[:3],[3.1,4.9,5.2])]+[[s,v,'EIS_Zw']for s,v in zip(hp[:3],[.42,.53,.58])]+[[s,v,'current_rate_retention_pct']for s,v in zip(hp[:3],[86.1,63.6,61.31])]+[['HPC-700',99.2,'device_coulombic_efficiency'],['HPC-700',12.02,'device_energy'],['HPC-700',250,'device_power']]
    u=unit(HP,'own_electrochemical_responses',['sample','value','metric'],vals,'MainP16..18; rate20/1 isnotlifetime, EISnotpretestfeatures')
    for i,(s,v,met)in enumerate(vals,1):resp(HP,s,u,i,1,met,'ohm'if i<7 else'%'if i<11 else'Wh/kg'if i==11 else'W/kg',not_pretest_predictor=True)
    for doi,s,eid,ev in [(FR,'FRPCK-Urea','candidate:TE010','96.43/5000/20Ag sameoldcycle,1M/6Mconflictunchanged'),(FW,'FWCA-4','candidate:TE008','94.1/10000/10Ag sameoldcycle,referenceuncertaintyunchanged'),(NS,'NSOC-800','candidate:V05:017','90.1/5000/1Ag sameold3Ecycle,calomel/HgHgOunchanged')]:link(doi,s,eid,ev)
    for doi,s,cid,ret,n,j in [(NS,'NSOC-800','LP24:NSOC:2E:C5000',81,5000,1),(HP,'HPC-700','LP24:HPC700:2E:C30000',98.59,30000,5)]:spec['candidates'].append(dict(doi=doi,sample=s,candidate_id=cid,record=dict(method='GCD',system='2E_symmetric',electrolyte='KOH'if doi==NS else'H2SO4',concentration_mol_L=6 if doi==NS else 1,current_A_g=j,cycle_count=n,retention_pct=ret,retention_relation='approximately'if doi==NS else'eq',value_kind='author_approximate'if doi==NS else'author_reported',voltage_lower_V=0 if doi==NS else None,voltage_upper_V=1.2 if doi==NS else None,evidence='OwnNS_Table1~81/Fig4dnot3E90.1'if doi==NS else'OwnMainP18, initialreference, deviceFig8unobtained; notoldHPCcache93.8',scope='new_candidate_only_requires_per_test_admission',training_eligible=False)))
    issue(FR,'concentration_and_ratio_conflicts',dict(method6M='MainP9',result_and_caption1M='MainP25/Fig4caption',ratios_body=[43.70,19.90,25.59],ratios_table=[43.87,19.89,25.48],body_Vmeso_misattributed_sample='MainP18callsFRPCUrea.2541 buttableFRPCKUrea'),'KeepfourGCDasinspectiononly; no concentrationchoice/no cyclingunfreeze. Maskcompetingratiocells, keeptablevolumes and4samplefeatures; XPSunknownpercentagebasisnotatomic.')
    issue(FW,'unit_roles_and_cited_protocol_scope',dict(raw_prose_volume='.634m3/g',table_volume='.634cm3/g',abstract_energy='179.9W/kg',detailed_energy_power=[22.35,179.9],cited_method_metadata_characters=360,reference_electrode_not_available=True),'TableunitsanddetailedFig8rolesareexplicit; rawclaimsretainedseparately, no silentunitconversion. 3EreportedGCD auxiliarymaymaskoptionalreference; cyclingcontractstillholds reference. 314roundedwithin314.4roundinginterval, selectdetailnotbyperformance. No geladditiveorrawEAinheritanceasfinalcomposition.')
    issue(NS,'reference_temperature_and_peak_assignment',dict(method_reference='calomel',actual_Fig3_axes='Hg/HgO',anneal_K=873,sample_name='NSOC800',N402_6_body='graphitic',N402_6_figure='OxidsedN',Raman_body=[1350,1590],Raman_figure=[1355,1595]),'No true referenceselected; cyclingholdretained. 3Ecapacity defined workingmass andauthors1Vwindow canenterreportedcapacityaux withreferenceconflictflag, notlifetime. Kelvinconversionexplicitderived; name800notclaimed800C. KeepbothNassignments andRamanpositions, maskambiguousfeatures.')
    issue(NS,'three_two_electrode_and_unbound_claims',dict(three_electrode_retention=90.1,two_electrode_own_table_approx_retention=81,intro_capacity75_current=None,two_electrode_body_rates=[24.3,22.5,18.7,18.1],average_losses=[.003,.0038]),'3E/2E testsdistinct; ~81notexact81labelor3E90.1. Intro75unboundnotassigned1Ag; bodycurrentpairsandfigurelegends retainedsource-specificwithmassscopeunknown and2Eaxislabeldissent. CEnotretention andaveragecyclelossnotassumedexponential.')
    issue(HP,'prechar_alias_mass_and_unobtained_figures',dict(known_control='NHPC700',prose_variant='NHPC900',figure_scope_unobtained=9,old_HPC_p15_different_journal_year='IJE2024,93.8pct/5000'), 'Do notinventNHPC900sampleorinheritprecharfeatures. 3E/2E346distinct, Cs=4I/(totalmass)notdeviceC. Main3Ewindowdoesnotprove2Ewindow; new2Ecyclecandidateonly. Name-onlyHPCcachebindingrejected; no fakeimageinspection.')
    for doi in KEYS:spec['protocol_reviews'].append(dict(doi=doi,body_paragraphs_read=len(roots[doi].findall('./body//p')),all_native_main_tables_read=True,own_main_figure_scopes_seen=0 if doi==HP else sum(f['doi']==doi for f in spec['figures']),full_source_review_complete=False,remaining='Undigitizedwaveforms/ratepoints; ownHPCoriginalfiguresunobtained; protocolconflictsnotauthorresolved',no_model_fit=True))
    # Validate every scalar token before creating a new SQLite file.
    tt={(t['doi'],t['id']):t for t in spec['tables']+spec['units']}
    for q in spec['facts']+spec['caps']+spec['responses']:
        t=tt[q['doi'],q['id']];rows=[[v['raw']for v in row]for row in t['grid']]if'grid'in t else t['rows'];numeric_details(rows[q['row']-1][q['col']])
    unique={(q['doi'],q['sample'],q['field'],q['id'])for q in spec['facts']}
    assert len(unique)==len(spec['facts']),'Competing same-field claims need separate source evidence units'
    write(OUT/'curation_spec.json',spec);print(json.dumps({k:len(v)for k,v in spec.items()}))

def add_details(c,spec):
    c.executescript('create table inspection_rows_v24(observation_id text primary key references capacitance_observations,record_json text);')
    for r in spec['inspection']:
        rid=r['doi']+'#'+r['id']+'#'+str(r['row'])+'#'+str(r['col']);insert(c,'inspection_rows_v24',dict(observation_id=rid,record_json=json.dumps(r,ensure_ascii=False)))
    c.commit()

def build():
    assert sha(PARENT)==PSHA and not DB.exists()and not(OUT/'merge_manifest.json').exists()
    spec=json.loads((OUT/'curation_spec.json').read_text('utf8'));docs={d['key']:d for d in spec['documents']}
    with closing(ro(PARENT))as parent,closing(sqlite3.connect(DB))as c:
        parent.backup(c);c.row_factory=sqlite3.Row;c.execute('pragma foreign_keys=on')
        c.executescript('''create table source_reviews_v24(doi text primary key references reviewed_sources,record_json text);create table cell_extractions_v24(kind text,record_id text,table_key text references reviewed_tables,row_ordinal integer,column_ordinal integer,primary key(kind,record_id));create table decisions_v24(decision_id text primary key,doi text references reviewed_sources,record_json text);create table material_feature_decisions_v24(material_key text references materials,field_name text,record_json text,primary key(material_key,field_name));create table purpose_reviews_v24(observation_id text primary key references capacitance_observations,purpose text,eligible integer,record_json text);create table figure_scope_reviews_v24(doi text references reviewed_sources,figure_number integer,document_key text references source_documents,record_json text,primary key(doi,figure_number));create table annotations_v24(annotation_id text primary key,doi text references reviewed_sources,document_key text references source_documents,record_json text);create table cycle_identity_links_v24(link_id text primary key,record_json text);''')
        for s in spec['sources']:insert(c,'reviewed_sources',dict(doi=s['doi'],path=s['path'],sha256=s['sha256'],title=s['title'],stage='Four own biomass sources; all-stage/native tables and method-qualified body reports; protocol conflicts and missing wheat figures retained'))
        for d in docs.values():assert sha(ROOT/d['path'])==d['sha256'];insert(c,'source_documents',dict(document_key=d['key'],doi=d['doi'],path=d['path'],sha256=d['sha256'],role=d['role']))
        for t in spec['tables']+spec['units']:
            key=t['doi']+'#'+t['id'];rows=[[v['raw']for v in r]for r in t['grid']]if'grid'in t else t['rows'];insert(c,'reviewed_tables',dict(table_key=key,doi=t['doi'],xml_id=t['id'],caption=t.get('caption',t['id']),header_json=json.dumps(rows[0]if'grid'in t else t['header']),footnote=t.get('footnote','Own bounded transcription; stages/repeats/foreign comparisons kept distinct'),source_raw_table_id=t.get('raw_table_id')));insert(c,'table_source_links',dict(table_key=key,document_key=t['document'],locator=t['locator']));insert(c,'extraction_units_v3',dict(table_key=key,kind=t['kind'],scope='Own explicitly bound cells only; foreign rows retained as context, never admitted'))
            for i,row in enumerate(rows,1):insert(c,'transcribed_rows',dict(table_key=key,row_ordinal=i,cells_json=json.dumps(row,ensure_ascii=False)));insert(c,'transcription_origins_v7',dict(table_key=key,row_ordinal=i,origin_json=json.dumps(t['grid'][i-1]if'grid'in t else dict(document=t['document'],locator=t['locator'],row=i),ensure_ascii=False)))
            if t.get('raw_table_id'):
                assert c.execute('select review_state from raw_table_queue where table_id=?',(t['raw_table_id'],)).fetchone()[0]=='automatic_candidate_unreviewed'
                c.execute('update raw_table_queue set review_state=?where table_id=?',('v24_own_cells_methods_stage_and_conflicts_reviewed',t['raw_table_id']))
        for r in spec['materials']:
            insert(c,'materials',dict(material_key=mk(r['doi'],r['sample']),doi=r['doi'],sample_name=r['sample'],material_stage=r['stage']))
            insert(c,'material_scopes_v8',dict(material_key=mk(r['doi'],r['sample']),scope_json=json.dumps(dict(origin_class=r['stage'],feedstock=r['feedstock'],stage=r['stage'],not_assumed_pure_carbon=True,same_source_not_independent=True))))
        def cell(r):
            key=r['doi']+'#'+r['id'];raw=json.loads(c.execute('select cells_json from transcribed_rows where table_key=?and row_ordinal=?',(key,r['row'])).fetchone()[0])[r['col']];return key,raw,number(raw)
        def receipt(kind,rid,r,key):insert(c,'cell_extractions_v24',dict(kind=kind,record_id=str(rid),table_key=key,row_ordinal=r['row'],column_ordinal=r['col']))
        for r in spec['facts']:
            key,raw,value=cell(r);doc=c.execute('select document_key from table_source_links where table_key=?',(key,)).fetchone()[0];q=insert(c,'material_facts',dict(material_key=mk(r['doi'],r['sample']),field_name=r['field'],value=value,raw_value=raw,unit=r['unit'],method=r['method'],table_key=key,row_ordinal=r['row'],column_ordinal=r['col'],source_sha256=docs[doc]['sha256'],review_status=r['status'],training_eligible=0));receipt('fact',q.lastrowid,r,key)
        for r in spec['caps']:
            key,raw,value=cell(r);rid=key+'#'+str(r['row'])+'#'+str(r['col']);cond=dict(extraction_batch='v24',current_mass_basis='author_reported_unknown_not_inferred',repeat_reports_not_independent=True);cond.update(r['conditions'])
            insert(c,'capacitance_observations',dict(observation_id=rid,material_key=mk(r['doi'],r['sample']),table_key=key,row_ordinal=r['row'],column_ordinal=r['col'],value=value,raw_value=raw,unit='F/g',method=r['method'],system=cond['system'],electrolyte=cond['electrolyte'],concentration_mol_L=cond['concentration_mol_L'],current_A_g=r['j'],scan_rate_mV_s=r['scan'],conditions_json=json.dumps(cond,ensure_ascii=False),status='own_reported'if r['purpose']else'own_repeat_or_competing_report',source_group='doi:'+r['doi'],training_eligible=0));receipt('capacitance',rid,r,key)
            if r['purpose']:
                reason='Own bound fresh method-specific report; explicit target/normalization/material scope, optional missing fields masked; source-specific ambiguous C/Cg never mixed into unified targets'
                insert(c,'purpose_reviews_v24',dict(observation_id=rid,purpose=r['purpose'],eligible=1,record_json=json.dumps(dict(reason=reason,purpose_input_ready=True,cyclic_retention_training_admitted=False,training_authorized=False))))
                if r['purpose']=='reported_aqueous_3e_GCD_capacitance':insert(c,'auxiliary_gcd_reviews_v3',dict(observation_id=rid,purpose=r['purpose'],eligible=1,reason=reason,review_basis='Own specific results/actual printed plot and matched own protocol, variants retained; no performance-based selection'))
        for r in spec['responses']:
            key,raw,value=cell(r);rid=key+'#'+str(r['row'])+'#'+str(r['col']);insert(c,'outcome_observations_v3',dict(outcome_id=rid,material_key=mk(r['doi'],r['sample']),table_key=key,record_json=json.dumps(dict(source_group='doi:'+r['doi'],extraction_batch='v24',metric=r['metric'],value=value,raw_value=raw,unit=r['unit'],**(dict(feature_role='test_or_process_response_not_pretest_predictor')|r['conditions'])),ensure_ascii=False),training_eligible=0));receipt('response',rid,r,key)
        for r in spec['synthesis']:insert(c,'synthesis_stages_v3',dict(material_key=mk(r['doi'],r['sample']),document_key=r['document'],locator=r['locator'],stages_json=json.dumps(r['stages'],ensure_ascii=False)))
        for r in spec['feature_decisions']:insert(c,'material_feature_decisions_v24',dict(material_key=mk(r['doi'],r['sample']),field_name=r['field'],record_json=json.dumps(r,ensure_ascii=False)))
        for r in spec['decisions']:insert(c,'decisions_v24',dict(decision_id=r['id'],doi=r['doi'],record_json=json.dumps(r,ensure_ascii=False)));insert(c,'scientific_issues',dict(issue_id=r['id'],doi=r['doi'],sample_name=None,issue_json=json.dumps(dict(kind=r['id'],action=r['decision']),ensure_ascii=False)))
        for r in spec['figures']:insert(c,'figure_scope_reviews_v24',dict(doi=r['doi'],figure_number=r['figure_number'],document_key=r['document'],record_json=json.dumps(r,ensure_ascii=False)))
        for r in spec['annotations']:insert(c,'annotations_v24',dict(annotation_id=r['id'],doi=r['doi'],document_key=r['document'],record_json=json.dumps(r,ensure_ascii=False)))
        for r in spec['identity_links']:insert(c,'cycle_identity_links_v24',dict(link_id='LP22_'+r['existing_endpoint_id'],record_json=json.dumps(r,ensure_ascii=False)))
        sources={r['doi']:r for r in spec['sources']}
        for r in spec['candidates']:insert(c,'test_candidates',dict(candidate_id=r['candidate_id'],material_key=mk(r['doi'],r['sample']),record_json=json.dumps(dict(r['record'],source_group='doi:'+r['doi'],source_year=sources[r['doi']]['year'],evidence_source_path=sources[r['doi']]['path'],source_sha256=sources[r['doi']]['sha256'],current_mass_basis='author_reported_unknown_not_inferred',baseline_cycle=None,baseline_reference='author_reference_not_assumed_cycle1'),ensure_ascii=False),training_eligible=0))
        for s in spec['sources']:
            review=dict(source_year=s['year'],classification=s['classification'],scope='All four native bodies/eight main tables;17 available original figure scopes and one own SI; wheat nine figure assets unavailable',remaining='Continuous spectra/isotherms/CV/GCD/EIS, untranscribed rate markers, unresolved protocols/identities; not full-source extraction.',full_source_review_complete=False)
            insert(c,'source_scope_decisions',dict(doi=s['doi'],scope=review['scope'],reason=review['remaining'],evidence_json=json.dumps(review,ensure_ascii=False),full_source_review_complete=0));insert(c,'source_reviews_v24',dict(doi=s['doi'],record_json=json.dumps(review,ensure_ascii=False)))
        c.executescript('create table raw_candidate_dispositions_v24(table_id text primary key references raw_table_queue,record_json text);create table numeric_details_v24(fact_id integer primary key references material_facts,record_json text);create table material_lineage_v24(lineage_id integer primary key,parent_key text references materials,child_key text references materials,record_json text);')
        for r in spec['raw_dispositions']:
            c.execute('update raw_table_queue set review_state=?where table_id=?',(r['disposition'],r['table_id']));insert(c,'raw_candidate_dispositions_v24',dict(table_id=r['table_id'],record_json=json.dumps(r,ensure_ascii=False)))
        for r in c.execute('select f.fact_id,f.raw_value,f.method from material_facts f join cell_extractions_v24 x on x.record_id=cast(f.fact_id as text)and x.kind="fact"').fetchall():
            nd=numeric_details(r['raw_value'])
            if 'mean±SD'in r['method']:nd['uncertainty_kind']='author_mean_and_SD'
            insert(c,'numeric_details_v24',dict(fact_id=r['fact_id'],record_json=json.dumps(nd,ensure_ascii=False)))
        for r in spec['lineage']:insert(c,'material_lineage_v24',dict(parent_key=mk(r['doi'],r['parent']),child_key=mk(r['doi'],r['child']),record_json=json.dumps(r,ensure_ascii=False)))
        c.execute('create table protocol_reviews_v24(doi text primary key references reviewed_sources,record_json text)')
        for r in spec['protocol_reviews']:insert(c,'protocol_reviews_v24',dict(doi=r['doi'],record_json=json.dumps(r,ensure_ascii=False)))
        c.commit()
        add_details(c,spec)
    protected={ROOT/d['path']for d in docs.values()}|{PARENT,CYCLE,NATIVE}
    protected.update(ROOT/d['path']for d in json.loads((OUT/'local_document_inventory.json').read_text('utf8'))['documents'])
    protected.update(ROOT/r['archive_origin']['archive']for r in spec['figures']if r.get('archive_origin'))
    write(OUT/'protected_inputs.json',dict(files=[dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p),bytes=p.stat().st_size)for p in sorted(protected)]))
    print('Built unsealed v24; no original cycling modification or model fitting')
if __name__=='__main__':
    mode=sys.argv[1]
    if mode not in ['curate','build']:raise SystemExit(mode)
    globals()[mode]()
