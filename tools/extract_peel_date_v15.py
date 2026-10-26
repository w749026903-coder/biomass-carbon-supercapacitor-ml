"""One-use, additive primary-source extraction; no fitting or cycling admission."""
from pathlib import Path
from contextlib import closing
import collections,hashlib,json,re,sqlite3,sys,xml.etree.ElementTree as E,zipfile
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tools'))
from extract_onion_composite_v8 import sha,write,ro,insert,mk
from extract_palm_kernel_v7 import xml_grid
from extract_source_series_v13 import clean
OUT=ROOT/'文献全量利用复核_20261026/批次15_花椒皮籽与椰枣叶';DB=OUT/'literature_material_pool_v15.sqlite'
PARENT=ROOT/'文献全量利用复核_20261026/批次14_糠醛渣倍率曲线与全图审查/literature_material_pool_v14.sqlite';PSHA='bd946bc7ad52c38d2ab9360566a0515d935e7ad1331a78e94d629c20d3c02d1f'
PE='10.3390/nano14100836';DA='10.3390/nano12010122'
PE_DIR=ROOT/'同体系文献补充_第二批_20261017/定向扩搜40至60篇_20261017/sources/OA022'
PATHS={PE:PE_DIR/'main.xml',DA:ROOT/'三电极端点扩充_20261018/new_sources/PMC8746510/main.xml'}
DOCKEY={PE:'Zanthoxylum15',DA:'DateFrond15'}
TEMPS=[600,700,800,900,1000];NAMES={PE:[a+'-'+str(t)for a in ['PAC','SAC']for t in TEMPS]+['raw_peel','raw_seed'],DA:['CO2-activated','NaOH-activated']}

def number(raw):
    if raw=='near 1, no numeric ratio reported':return None
    m=re.fullmatch(r'([+-]?(?:\d+(?:\.\d+)?|\.\d+))(?:\s+(?:m2/g|cm3/g|nm|kJ/mol)|%)?',raw)
    assert m,raw
    return float(m[1])

def curate():
    assert not DB.exists()and not(OUT/'curation_spec.json').exists()and not(OUT/'merge_manifest.json').exists()
    assert sha(PARENT)==PSHA
    spec={k:[]for k in ['sources','documents','tables','units','facts','caps','responses','synthesis','components','annotations','figures','decisions','candidates']}
    paragraphs={}
    def document(key,doi,path,role):spec['documents'].append(dict(key=key,doi=doi,path=path.relative_to(ROOT).as_posix(),sha256=sha(path),role=role))
    with closing(ro(ROOT/'全库复检与特征补提取_20261021/full_corpus_search_native.sqlite'))as c:
        for doi,path in PATHS.items():
            root=E.parse(path).getroot();digest=sha(path)
            assert {x.text.lower()for x in root.findall('./front/article-meta/article-id')if x.get('pub-id-type')=='doi'}=={doi}
            roles=c.execute('select identity_key,role,basis from identity_sources where sha256=?',(digest,)).fetchall();assert{r[0]for r in roles}=={'doi:'+doi}
            years={int(x.text)for x in root.findall('./front/article-meta/pub-date/year')};assert years==({2024}if doi==PE else{2021})
            spec['sources'].append(dict(doi=doi,path=path.relative_to(ROOT).as_posix(),sha256=digest,title=clean(root.find('.//article-title')),year=years.pop(),identity_roles=roles,classification='original_biomass_research'))
            document(DOCKEY[doi],doi,path,'primary_XML');paragraphs[doi]=[clean(x)for x in root.findall('./body//p')]
            raw={r[1]:r[0]for r in c.execute('select table_id,locator from raw_tables_v11 where source_sha256=?',(digest,))}
            for t in root.findall('.//table-wrap'):
                locator='XML table-wrap '+t.get('id');spec['tables'].append(dict(doi=doi,id=t.get('id'),document=DOCKEY[doi],locator=locator,caption=clean(t.find('caption')),footnote=clean(t.find('table-wrap-foot')),grid=xml_grid(t),raw_table_id=raw[locator],kind='own_original_XML_table'))
            for i,f in enumerate(root.findall('.//fig'),1):
                key=DOCKEY[doi]+'_Fig'+str(i);p=(PE_DIR/'figures'if doi==PE else OUT/'evidence')/('nanomaterials-'+('14-00836'if doi==PE else'12-00122')+'-g'+str(i).zfill(3)+'.jpg');document(key,doi,p,'original_figure')
                spec['figures'].append(dict(doi=doi,figure_number=i,document=key,caption=clean(f.find('caption')),inspected=True,full_waveform_extracted=False,remaining='Continuous adsorption/CV/GCD/EIS/Raman and morphology distributions not digitized; selected printed quantities only'))
    document('Zanthoxylum15_SI',PE,PE_DIR/'nanomaterials-2978200-supplementary.pdf','original_SI_PDF')
    spec['figures'].append(dict(doi=PE,figure_number=101,document='Zanthoxylum15_SI',caption='SI FigureS1 p2 XPS surveys',inspected=True,full_waveform_extracted=False,remaining='Survey has no additional printed composition percentages'))
    assert '211.0, 201.4, 188.0, 182.2, 177.3, 173.0, 169.5, and 165.5'in paragraphs[PE][35]
    assert '219.7, 196.0, 187.0, 180.4, 175.0, 170.0, 165.2, and 161.0'in paragraphs[PE][35]
    assert '125.9 vs. 56.8'in paragraphs[DA][22]and'156.8 F/g at 0.4 A/g'in paragraphs[DA][21]
    def unit(doi,id,header,rows,locator,doc=None,kind='own_prose_transcription'):
        spec['units'].append(dict(doi=doi,id=id,header=header,rows=rows,locator=locator,document=doc or DOCKEY[doi],kind=kind));return id
    def fact(doi,s,id,row,col,field,unit,method,status='own_reported_method_qualified'):
        spec['facts'].append(dict(doi=doi,sample=s,id=id,row=row,col=col,field=field,unit=unit,method=method,status=status))
    def cap(doi,s,id,row,col,j,select=True,**cond):spec['caps'].append(dict(doi=doi,sample=s,id=id,row=row,col=col,j=j,select=select,conditions=cond))
    def response(doi,s,id,row,col,metric,unit,**extra):spec['responses'].append(dict(doi=doi,sample=s,id=id,row=row,col=col,metric=metric,unit=unit,extra=extra))
    def decision(doi,id,text):spec['decisions'].append(dict(doi=doi,id='LP15_'+id,decision=text))
    # All ten final samples, not just the two electrochemical optima.
    ptab='nanomaterials-14-00836-t001'
    for row,s in enumerate(NAMES[PE][:10],2):
        for col,field,un in [(1,'BET_surface_area_m2_g','m2/g'),(2,'micropore_surface_area_m2_g','m2/g'),(3,'total_pore_volume_cm3_g','cm3/g'),(4,'micropore_volume_cm3_g','cm3/g'),(5,'mesopore_volume_cm3_g','cm3/g'),(6,'mean_pore_diameter_reported_nm','nm')]:fact(PE,s,ptab,row,col,field,un,'Own Table1; BET P/P0 .05-.20, Vt .99, BJH adsorption PSD; micro method not further stated')
    xtab='nanomaterials-14-00836-t002';table=next(t for t in spec['tables']if t['id']==xtab)
    assert len(table['grid'])==18
    for s,namecol,valuecol in [('PAC-700',1,2),('SAC-600',3,4)]:
        for row,e in [(2,'C'),(6,'N'),(10,'S'),(15,'O')]:fact(PE,s,xtab,row,valuecol,'XPS_'+e+'_at_pct','at%','OwnTable2 survey total; not a relative envelope fraction')
        for row in [3,4,5,7,8,9,11,12,13,14,16,17,18]:
            cells=table['grid'][row-1];name=cells[namecol]['raw'];energy=cells[0]['raw'];field='XPS_component_'+name.replace('-','_')+'_at_pct';status='conflict_table_zero_vs_visible_fitted_component'if name in ['S-II','S-IV']else'conflict_component_sum_C_not_normalized'if s=='PAC-700'and name.startswith('C-')else'own_reported_component_absolute_at_pct'
            fact(PE,s,xtab,row,valuecol,field,'at%','OwnTable2 component atomic percentage on full survey scale; not percentage within element',status)
            spec['components'].append(dict(doi=PE,sample=s,id=xtab,row=row,col=valuecol,name=name,energy_eV=float(energy),absolute_at_pct=float(cells[valuecol]['raw']),relative_envelope_pct=None,status=status))
    u=unit(PE,'feedstock_composition',['sample','C','N','O','S'],[['raw_peel','62.35','7.94','27.35','2.36'],['raw_seed','55.61','9.37','31.84','3.18']],'bodyP4 raw biomass composition; analytical method and atom/wt basis unspecified')
    for row,s in enumerate(['raw_peel','raw_seed'],1):
        for col,e in enumerate(['C','N','O','S'],1):fact(PE,s,u,row,col,'raw_feedstock_'+e+'_reported_pct','%basis_unspecified','Only raw feedstockP4; not final carbon XPS')
    u=unit(PE,'Fig5_Raman',['sample','ID_IG'],[[s,v]for s,v in zip(NAMES[PE][:10],['2.84','2.64','1.74','1.39','1.23','2.64','2.53','2.32','2.23','2.21'])],'ActualFig5c/d printed ratios, bodyP29 integral intensity definition','Zanthoxylum15_Fig5','own_printed_figure_annotations')
    for row,s in enumerate(NAMES[PE][:10],1):fact(PE,s,u,row,1,'Raman_ID_IG','ratio','PrintedFig5c/d, integrated D/G intensity not assumed peak height')
    u=unit(PE,'FWHM_endpoints',['sample','FWHM'],[[s,v]for s,v in [('PAC-600','10.6'),('PAC-1000','2.3'),('SAC-600','9.5'),('SAC-1000','7.2')]],'bodyP28 explicit (002) width endpoints, no intermediate widths inferred')
    for row,s in enumerate(['PAC-600','PAC-1000','SAC-600','SAC-1000'],1):fact(PE,s,u,row,1,'XRD_002_FWHM_deg','degree','Author endpoint values; not inferred from inconsistent subsequent plane wording','author_approximate_report')
    rows=[['PAC-700','970.6','211.0','6 M KOH','1.0','This work'],['SAC-600','1557.9','219.7','6 M KOH','1.0','This work'],['Pine sawdust','2331','175.6','6 M KOH','0.5','S1'],['Casein','2212','177','6 M KOH','0.5','S2'],['Rice husk','1183','148','6 M KOH','0.2','S3'],['Licorice residues','2186','221','6 M KOH','0.5','S4'],['Camphor tree grains','470','384','6 M NaOH','1.0','S5'],['Rice straw','3345','365','2 M NaCl','0.5','S6']]
    u=unit(PE,'SI_TableS1',['material','BET','C','electrolyte','j','reference'],rows,'SI PDF p3 TableS1; only first two rows own, six literature rows not admitted','Zanthoxylum15_SI','own_SI_comparison_table_own_rows_only')
    pcond=dict(system='3E',electrolyte='KOH',concentration_mol_L=6,voltage_lower_V=-1,voltage_upper_V=0,reference_electrode='Hg/HgO',capacitance_basis='author_reported_single_working_electrode',target_stage='fresh_reported_GCD_rate_test')
    for row,s in enumerate(['PAC-700','SAC-600'],1):
        fact(PE,s,u,row,1,'BET_surface_area_m2_g','m2/g','OwnSI TableS1 repeat of main Table1; not independent BET')
        cap(PE,s,u,row,2,1,select=False,**pcond,report_kind='repeat_SI_same_test',physical_test_group='doi:'+PE+':'+s+':3E:j1')
    for s,vals in [('PAC-700',['211.0','201.4','188.0','182.2','177.3','173.0','169.5','165.5']),('SAC-600',['219.7','196.0','187.0','180.4','175.0','170.0','165.2','161.0'])]:
        u=unit(PE,'body35_rate_'+s,['sample','j','C'],[[s,str(j),v]for j,v in zip([1,3,5,7,9,11,13,15],vals)],'bodyP35 own individually enumerated GCD values; Fig8c/9c shared physical tests')
        for row,j in enumerate([1,3,5,7,9,11,13,15],1):cap(PE,s,u,row,2,j,**pcond,physical_test_group='doi:'+PE+':'+s+':3E:j'+str(j))
    u=unit(PE,'rate_retention',['sample','rate_retention'],[['PAC-700','78.4'],['SAC-600','73.3']],'bodyP35 rate1to15 A/g, not cycling retention')
    for row,s in enumerate(['PAC-700','SAC-600'],1):response(PE,s,u,row,1,'rate_capacitance_retention','%',low_current_A_g=1,high_current_A_g=15)
    u=unit(PE,'Fig7_contributions',['sample','author_pseudocap_pct'],[['PAC-700','20'],['SAC-600','26']],'bodyP33 plus actualFig7 50mV/s; author calls Dunn diffusion term pseudocapacitance, do not relabel physical mechanism','Zanthoxylum15_Fig7','own_figure_bound_prose')
    for row,s in enumerate(['PAC-700','SAC-600'],1):response(PE,s,u,row,1,'author_Dunn_pseudocapacitance_contribution','%',scan_rate_mV_s=50,mechanism_label_not_revalidated=True)
    u=unit(PE,'p27_pseudocap_claims',['sample_as_written','pct'],[['SAC-600','15.20'],['SAC-700','13.53']],'bodyP27 as-written SAC700 label and unspecified rate; not replaced with PAC700/Fig7values')
    for row,s in enumerate(['SAC-600','SAC-700'],1):response(PE,s,u,row,1,'author_other_pseudocapacitance_claim','%',scan_rate_mV_s=None,identity_or_condition_dispute=True)
    u=unit(PE,'Bode_prose',['sample','phase_abs','peak_frequency'],[[s,a,'30000'if s=='PAC-1000'else'20000']for s,a in zip(NAMES[PE][:10],['82.2','82.8','83.5','85.2','84.6','81.8','84.1','85.0','85.1','81.6'])],'bodyP37 reported phase angle magnitudes at.01Hz and approximate peak frequencies; no sign invented')
    for row,s in enumerate(NAMES[PE][:10],1):response(PE,s,u,row,1,'Bode_phase_angle_reported_magnitude','degree',frequency_Hz=.01,approximate=True);response(PE,s,u,row,2,'Bode_author_peak_frequency','Hz',approximate=True)
    u=unit(PE,'Ragone_prose',['sample','energy','power'],[['PAC-700','29.3','500'],['PAC-700','22.9','7500'],['SAC-600','30.5','500'],['SAC-600','22.4','7500']],'bodyP38 paired Ragone device operating points; no current/window reverse-calculation')
    for row,s in enumerate(['PAC-700','PAC-700','SAC-600','SAC-600'],1):
        for col,metric,un in [(1,'device_energy_density','Wh/kg'),(2,'device_power_density','W/kg')]:response(PE,s,u,row,col,metric,un,system='2E_symmetric',paired_operating_point='doi:'+PE+':Ragone:row'+str(row))
    u=unit(PE,'device_cycle_prose',['sample','retention','final_C'],[['PAC-700','99.1','47.2'],['SAC-600','93.4','44.6']],'bodyP38 explicit symmetric devices, Fig8f/9f original labels; Fig9caption SAC700 dissent')
    for row,s in enumerate(['PAC-700','SAC-600'],1):
        response(PE,s,u,row,1,'cycling_retention','%',system='2E_symmetric',cycle_count=10000,reported_current_A_g=1)
        cap(PE,s,u,row,2,1,select=False,system='2E_symmetric',electrolyte='KOH',concentration_mol_L=6,target_stage='post_10000_cycles',cycle_count=10000,voltage_lower_V=None,voltage_upper_V=None,capacitance_basis='author_device_formula_no_factor4_assumed',physical_test_group='doi:'+PE+':'+s+':2E:cycle10000')
        spec['candidates'].append(dict(candidate_id='LP15_'+s+'_2E_C10000',doi=PE,sample=s,record=dict(source_year=2024,system='2E_symmetric',method='GCD',metric_kind='capacitance_retention',retention_pct=[99.1,93.4][row-1],retention_relation='approx',cycle_count=10000,reported_current_A_g=1,current_mass_basis='author_reported_unknown',electrolyte='KOH',concentration_mol_L=6,cycle_voltage_lower_V=None,cycle_voltage_upper_V=None,baseline_cycle=None,baseline_reference='author_retention_normalization_not_assumed_cycle1',reference_electrode=None,purpose_reviewed_candidate_ready=False,reason='ActualFigf/ownbody supports device/sample; own physical2E cycling voltage missing, do not transfer3E HgHgO -1..0V or infer Ragonewindow',locator='bodyP15/P38 andFig8f/9f',curve_group='doi:'+PE+':Fig'+str(7+row)+'f:'+s)))
    for s in NAMES[PE][:10]:
        spec['synthesis'].append(dict(doi=PE,sample=s,document=DOCKEY[PE],locator='bodyP5/P6/P14; explicit same pyrolysis conditions in activation',stages=[dict(stage='feedstock_wash_dry',drying_C=80,drying_h=24,precursor_part='peel'if s.startswith('PAC')else'seed'),dict(stage='carbonization',temperature_C=500,duration_h=2,heating_rate_C_min=10,atmosphere='Ar',gas_flow_mL_min=100),dict(stage='chemical_activation',temperature_C=int(s.split('-')[1]),duration_h=2,heating_rate_C_min=10,atmosphere='Ar',gas_flow_mL_min=100,conditions_explicitly_same_as_pyrolysis=True,agent='KOH',carbon_mass_g=2,solution_mass_g=20,solution_KOH_wt_pct=10,carbon_to_activator_mass_ratio=[1,1],ratio_is_recipe_arithmetic=True,stirring_h=2,post_wash_HCl_M=2,post_drying_C=80,post_drying_h=6),dict(stage='electrode_preparation',slurry_carbon_mg=4,slurry_acetylene_black_mg=.5,PVDF_solution_mg=10,PVDF_solution_wt_pct=5,collector='Ni_foam_sandwich',collector_piece_dimensions_mm=[15,10,.5],collector_pieces=2,working_active_mass_approx_mg=2,not_4mg_slurry_input_assumed_on_final_electrode=True,press_MPa_approx=.5,drying_C=80,drying_h=12)]))
    # Date-frond: model-specific pore quantities stay distinct.
    dtab='nanomaterials-12-00122-t001'
    fields=[(2,'BET_surface_area_m2_g','m2/g','BET'),(4,'DFT_pore_volume_cm3_g','cm3/g','DFT'),(5,'DFT_surface_area_m2_g','m2/g','DFT'),(6,'DFT_reported_lower_confidence_limit_nm','nm','DFT software label, not an experimental CI'),(7,'DFT_fitting_error_pct','%','DFT fit statistic, not ML error'),(8,'DFT_pore_width_mode_nm','nm','DFT mode, not average'),(10,'DA_best_E_kJ_mol','kJ/mol','Dubinin-Astakhov fitted energy'),(11,'DA_best_n','dimensionless','DA fitted exponent'),(12,'DA_micropore_volume_cm3_g','cm3/g','DA model volume, not DFT volume'),(13,'DA_pore_diameter_mode_nm','nm','DA mode, not average')]
    for col,s in enumerate(NAMES[DA],1):
        for row,fld,un,method in fields:fact(DA,s,dtab,row,col,fld,un,method)
    u=unit(DA,'Fig3_survey',['sample','C','O','Ca','Cl','Si','Na'],[['CO2-activated','82.2','15.9','1.5','0.3','',''],['NaOH-activated','78.9','17.9','','','1.6','1.5']],'ActualFig3a/c printed Atomic%; blanks are not zeros','DateFrond15_Fig3','own_printed_figure_annotations')
    for row,s,cols in [(1,'CO2-activated',[(1,'C'),(2,'O'),(3,'Ca'),(4,'Cl')]),(2,'NaOH-activated',[(1,'C'),(2,'O'),(5,'Si'),(6,'Na')])]:
        for col,e in cols:fact(DA,s,u,row,col,'XPS_'+e+'_at_pct','at%','OwnFig3 printed survey atomic composition, not fitted C1s area fraction')
    u=unit(DA,'Fig3_C1s_fit',['sample','component','energy','area_pct'],[['CO2-activated','C_C','284.78','49.25'],['CO2-activated','C_O','285.99','43.24'],['CO2-activated','C_double_O','289.92','7.5'],['NaOH-activated','C_C','284.86','54.44'],['NaOH-activated','C_O','285.48','39.47'],['NaOH-activated','C_double_O','289.52','6.08']],'ActualFig3b/d Pos and%Area in C1s envelope; not total atomic%','DateFrond15_Fig3','own_printed_figure_annotations')
    for row,rr in enumerate(spec['units'][-1]['rows'],1):
        s,name,energy,area=rr;fact(DA,s,u,row,3,'XPS_'+name+'_envelope_pct','%C1s_envelope','Own fitted C1s %Area, no atomic conversion');spec['components'].append(dict(doi=DA,sample=s,id=u,row=row,col=3,name=name,energy_eV=float(energy),absolute_at_pct=None,relative_envelope_pct=float(area),status='reported_relative_C1s_area_not_whole_surface_atomic_percent'))
    u=unit(DA,'Raman_qualitative',['sample','ratio_description'],[[s,'near 1, no numeric ratio reported']for s in NAMES[DA]],'bodyP17 near1; Fig4 no printed numeric ratio, exact1 not fabricated')
    for row,s in enumerate(NAMES[DA],1):fact(DA,s,u,row,1,'Raman_ID_IG','ratio','Author qualitative nearone; exact scalar unavailable','qualitative_not_exact_numeric')
    u=unit(DA,'coating_loading',['sample','loading'],[['CO2-activated','1.8'],['NaOH-activated','1.4']],'bodyP8 mass before/after coating; 80:20 carbon/PTFE coating mass, not separately weighed active carbon')
    for row,s in enumerate(NAMES[DA],1):fact(DA,s,u,row,1,'electrode_coating_mass_loading_mg_cm2','mg/cm2','Coating including binder; no automatic active-mass conversion')
    dcond=dict(system='3E',electrolyte='H2SO4',concentration_mol_L=1,voltage_lower_V=0,voltage_upper_V=1,reference_electrode='Ag/AgCl',reference_electrode_dissent='bodyP19 says SCE; methodP8 and actualFig5/6 axes support Ag/AgCl; no author erratum claimed',capacitance_basis='author_reported_3E_not_further_mass_unified',target_stage='fresh_reported_GCD_rate_test')
    u=unit(DA,'own_cap_prose',['sample','j','C'],[['NaOH-activated','.4','156.8'],['NaOH-activated','20','55.9'],['NaOH-activated','1','125.9'],['CO2-activated','1','56.8']],'bodyP21/P22 own GCD, Fig5/6 supports Ag/AgCl0..1V')
    for row,rr in enumerate(spec['units'][-1]['rows'],1):cap(DA,rr[0],u,row,2,float(rr[1]),**dcond,physical_test_group='doi:'+DA+':'+rr[0]+':3E:j'+str(float(rr[1])))
    u=unit(DA,'ESR_prose',['sample','ESR'],[['CO2-activated','1.544'],['NaOH-activated','1.842']],'bodyP22 own ESR fromFig6d; response not pretest feature')
    for row,s in enumerate(NAMES[DA],1):response(DA,s,u,row,1,'EIS_ESR','ohm')
    for s in NAMES[DA]:
        activation=dict(stage='physical_activation',temperature_C=900,duration_h=1.5,atmosphere='CO2',gas_pressure_Torr=320,heating_rate_C_min=None,agent='CO2')if s.startswith('CO2')else dict(stage='chemical_activation',temperature_C=700,duration_h=2,heating_rate_C_min=None,atmosphere='N2',agent='NaOH',carbon_to_activator_mass_ratio=[1,4],stirring_h=2,impregnated_drying_C=100,impregnated_drying_duration_h=None)
        spec['synthesis'].append(dict(doi=DA,sample=s,document=DOCKEY[DA],locator='bodyP6/P8; initial carbonization method refers patent, not acquired here',stages=[dict(stage='carbonization',temperature_C=None,duration_h=None,heating_rate_C_min=None,atmosphere=None,unreported_in_article=True),dict(stage='ball_milling',sample_mass_g=10,duration_h_range=[5,7],midpoint_not_assigned=True),dict(stage='sonication',duration_h=3,power_W=200,water_mL_range=[50,100],drying_C=80,drying_h=None),activation,dict(stage='electrode_preparation',carbon_wt_pct=80,PTFE_wt_pct=20,collector='carbon_cloth',area_cm2=1,coating_mass_loading_mg_cm2=1.8 if s.startswith('CO2')else 1.4,active_carbon_mass_loading_mg_cm2=None,drying_C=60,drying_h=None)]))
    for value,assignment in [(3435,'O-H or N-H stretch'),(2919,'C-H stretch'),(2851,'C-H stretch'),(1621,'C=O stretch'),(1387,'O-H inplane bend'),(1085,'C-O or C-S-C stretch')]:spec['annotations'].append(dict(doi=PE,id='FTIR_'+str(value),document='Zanthoxylum15_Fig5',kind='collective_series_assignment',value=value,unit='cm^-1',assignment=assignment,scope_samples=NAMES[PE][:10],individual_measured_intensities=False,source_locator='bodyP30/Fig5e/f'))
    spec['annotations'] += [dict(doi=PE,id='XRD_position_ranges',document='Zanthoxylum15_Fig5',kind='collective_ranges',range_002_deg=[22,25.8],range_100_deg=[42.9,43.5],source_locator='bodyP28 initial range statement; subsequent42.9..43.5 called002 once, retained as dissent',scope_samples=NAMES[PE][:10],not_per_sample_positions=True),dict(doi=PE,id='EIS_collective_bounds',document=DOCKEY[PE],kind='collective_response_bounds',Rs_approx_ohm=.1,Rct_upper_bound_ohm=1,Rct_relation='lt',source_locator='bodyP36; not ten exact Rs=.1 or Rct=1 measurements',scope_samples=NAMES[PE][:10],predictor_ready=False)]
    for doi,id,text in [(PE,'XPS_scale','Table2 component values are whole-survey at%, not percentages within each element. PAC Ccomponents sum80.93 vs total80.84, retain both; no renormalization.'),(PE,'XPS_zero_dissent','Table2 S-II/S-IV printedzero but fitted components visible inFig3c/4c; retain zeros with dispute, no element absence or corrected fit fractions inferred.'),(PE,'raw_stage','P4 raw peel/seed percentages method/basis unspecified, kept under raw feedstock registrations; never copied as final carbon XPS.'),(PE,'mass_recipe','4mg carbon enters slurry but actual workingelectrode approximately2mg. KOH10wt% x20g /2gchar gives1:1 recipe ratio, explicitly derived; activation same conditionsaspyrolysis authored.'),(PE,'spectral_dissent','Table1 uses per-sample textural values; prose maximum/ranking and XRD002/100 wording do not overwrite it. Raman integral ratio matches printedFig5. FTIRranges are collective annotations.'),(PE,'Dunn_claim','P33 author pseudocap20/26 atFig7 50mV/s kept as author interpretation. P27 SAC60015.20/SAC70013.53 unspecifiedscan kept as separate disputed claims, no sample-name repair or mechanism proof.'),(PE,'device_config','BodyP38 explicit symmetric2E not3E. Fig9f actualSAC600 andbody agree, captionSAC700 dissent retained. Devicecycling voltage not reported; do not copy3E-1..0V.'),(PE,'repeat_foreign','SI TableS1 onlytwo own rows; cap repeats j1 alreadyinP35. Six foreign rows not new sources or training labels. Finalcycle47.2/44.6 distinct from fresh211/219.7.'),(DA,'reference','Working Ag/AgCl from methodP8 and actualFig5/6axes0..1; bodyP19SCE retained as dissent. No author correction or electrode-potential conversion claimed.'),(DA,'pore_models','DFT and DA pore volumes/modes remain model-qualified. DA volume may exceed DFT volume without violating single-model mass balance. DFTlower confidence limit is original software label, not experimentalCI.'),(DA,'XPS_scales','Atomic survey percentages distinct from C1s relative fitted%Area. All reported impurities kept; blank elements not0. Near-one Raman statement not exact1.'),(DA,'stages_year','Initial carbonization conditions not in article; 5..7h ballmill is range, not6h. Source XML/ePMC publishyear2021 retained despite volume12issue1. Coating mass includesPTFE, no inferred purecarbon mass.')]:decision(doi,id,text)
    write(OUT/'curation_spec.json',spec)
    print(json.dumps({k:len(v)for k,v in spec.items()},ensure_ascii=False))

def build():
    assert not DB.exists()and not(OUT/'merge_manifest.json').exists()and sha(PARENT)==PSHA
    spec=json.loads((OUT/'curation_spec.json').read_text('utf8'));docs={d['key']:d for d in spec['documents']}
    with closing(ro(PARENT))as parent,closing(sqlite3.connect(DB))as c:
        parent.backup(c);c.row_factory=sqlite3.Row;c.execute('pragma foreign_keys=on');c.executescript('''create table source_reviews_v15(doi text primary key references reviewed_sources,record_json text);create table cell_extractions_v15(kind text,record_id text,table_key text references reviewed_tables,row_ordinal integer,column_ordinal integer,primary key(kind,record_id));create table decisions_v15(decision_id text primary key,doi text references reviewed_sources,record_json text);create table xps_components_v15(component_id text primary key,material_key text references materials,record_json text);create table series_annotations_v15(annotation_id text primary key,doi text references reviewed_sources,document_key text references source_documents,record_json text);create table figure_scope_reviews_v15(doi text references reviewed_sources,figure_number integer,document_key text references source_documents,record_json text,primary key(doi,figure_number));''')
        for s in spec['sources']:insert(c,'reviewed_sources',dict(doi=s['doi'],path=s['path'],sha256=s['sha256'],title=s['title'],stage='All main relevant paragraphs/tables andallfigure scope inspected; continuouswaveforms incomplete'))
        for d in docs.values():assert sha(ROOT/d['path'])==d['sha256'];insert(c,'source_documents',dict(document_key=d['key'],doi=d['doi'],path=d['path'],sha256=d['sha256'],role=d['role']))
        for t in spec['tables']+spec['units']:
            key=t['doi']+'#'+t['id'];rows=[[v['raw']for v in r]for r in t['grid']]if'grid'in t else t['rows'];insert(c,'reviewed_tables',dict(table_key=key,doi=t['doi'],xml_id=t['id'],caption=t.get('caption',t['id']),header_json=json.dumps(rows[0]if'grid'in t else t['header']),footnote=t.get('footnote','Declared own scope; duplicate/foreign values not independent tests'),source_raw_table_id=t.get('raw_table_id')));insert(c,'table_source_links',dict(table_key=key,document_key=t['document'],locator=t['locator']));insert(c,'extraction_units_v3',dict(table_key=key,kind=t['kind'],scope='Only explicitly bound own cells; method/stage/repetition retained'))
            for i,row in enumerate(rows,1):insert(c,'transcribed_rows',dict(table_key=key,row_ordinal=i,cells_json=json.dumps(row,ensure_ascii=False)));insert(c,'transcription_origins_v7',dict(table_key=key,row_ordinal=i,origin_json=json.dumps(t['grid'][i-1]if'grid'in t else dict(document=t['document'],locator=t['locator'],row=i),ensure_ascii=False)))
            if t.get('raw_table_id'):
                assert c.execute('select review_state from raw_table_queue where table_id=?',(t['raw_table_id'],)).fetchone()[0]=='automatic_candidate_unreviewed'
                c.execute('update raw_table_queue set review_state=?where table_id=?',('v15_declared_own_scope_methods_and_disputes_retained',t['raw_table_id']))
        for doi,names in NAMES.items():
            for s in names:
                stage='raw_feedstock'if s.startswith('raw_')else'final_biomass_carbon_before_test';insert(c,'materials',dict(material_key=mk(doi,s),doi=doi,sample_name=s,material_stage=stage));insert(c,'material_scopes_v8',dict(material_key=mk(doi,s),scope_json=json.dumps(dict(origin_class='biomass_carbon'if stage!='raw_feedstock'else'raw_biomass',feedstock='Zanthoxylum_bungeanum_'+('peel'if s.startswith('PAC')or s=='raw_peel'else'seed')if doi==PE else'date_palm_frond',stage=stage,not_assumed_pure_carbon=True,same_source_not_independent=True))))
        def cell(r):
            key=r['doi']+'#'+r['id'];raw=json.loads(c.execute('select cells_json from transcribed_rows where table_key=?and row_ordinal=?',(key,r['row'])).fetchone()[0])[r['col']];return key,raw,number(raw)
        def receipt(kind,rid,r,key):insert(c,'cell_extractions_v15',dict(kind=kind,record_id=str(rid),table_key=key,row_ordinal=r['row'],column_ordinal=r['col']))
        for r in spec['facts']:
            key,raw,value=cell(r);doc=c.execute('select document_key from table_source_links where table_key=?',(key,)).fetchone()[0];q=insert(c,'material_facts',dict(material_key=mk(r['doi'],r['sample']),field_name=r['field'],value=value,raw_value=raw,unit=r['unit'],method=r['method'],table_key=key,row_ordinal=r['row'],column_ordinal=r['col'],source_sha256=docs[doc]['sha256'],review_status=r['status'],training_eligible=0));receipt('fact',q.lastrowid,r,key)
        for r in spec['caps']:
            key,raw,value=cell(r);cond=dict(extraction_batch='v15',current_mass_basis='author_reported_unknown_not_inferred',voltage_lower_V=None,voltage_upper_V=None,reference_electrode=None,repeat_reports_not_independent=True);cond.update(r['conditions']);rid=key+'#'+str(r['row'])+'#'+str(r['col']);insert(c,'capacitance_observations',dict(observation_id=rid,material_key=mk(r['doi'],r['sample']),table_key=key,row_ordinal=r['row'],column_ordinal=r['col'],value=value,raw_value=raw,unit='F/g',method='GCD',system=cond['system'],electrolyte=cond['electrolyte'],concentration_mol_L=cond['concentration_mol_L'],current_A_g=r['j'],scan_rate_mV_s=None,conditions_json=json.dumps(cond,ensure_ascii=False),status='own_reported_author_approximate'if r['doi']==PE else'own_reported',source_group='doi:'+r['doi'],training_eligible=0));receipt('capacitance',rid,r,key)
            if r['select']:insert(c,'auxiliary_gcd_reviews_v3',dict(observation_id=rid,purpose='reported_aqueous_3e_GCD_capacitance',eligible=1,reason='Own individually enumerated GCD values/protocol; unknown current mass denominator allowed by reported-purpose decision; different stages and repeats excluded',review_basis='OwnbodyP35/PE protocol orDatebodyP21/P22+method/actualfigures; no performance-based selection'))
        for r in spec['responses']:
            key,raw,value=cell(r);rid=key+'#'+str(r['row'])+'#'+str(r['col']);insert(c,'outcome_observations_v3',dict(outcome_id=rid,material_key=mk(r['doi'],r['sample']),table_key=key,record_json=json.dumps(dict(source_group='doi:'+r['doi'],extraction_batch='v15',metric=r['metric'],value=value,raw_value=raw,unit=r['unit'],feature_role='test_response_not_pretest_material_predictor',**r['extra']),ensure_ascii=False),training_eligible=0));receipt('response',rid,r,key)
        for r in spec['synthesis']:insert(c,'synthesis_stages_v3',dict(material_key=mk(r['doi'],r['sample']),document_key=r['document'],locator=r['locator'],stages_json=json.dumps(r['stages'],ensure_ascii=False)))
        for r in spec['components']:insert(c,'xps_components_v15',dict(component_id='LP15_'+r['sample']+'_'+r['name'],material_key=mk(r['doi'],r['sample']),record_json=json.dumps(dict(r,table_key=r['doi']+'#'+r['id'],source_group='doi:'+r['doi']),ensure_ascii=False)))
        for r in spec['annotations']:insert(c,'series_annotations_v15',dict(annotation_id='LP15_'+r['id'],doi=r['doi'],document_key=r['document'],record_json=json.dumps(dict(r,not_independent_per_sample_measurements=True),ensure_ascii=False)))
        for r in spec['figures']:insert(c,'figure_scope_reviews_v15',dict(doi=r['doi'],figure_number=r['figure_number'],document_key=r['document'],record_json=json.dumps(r,ensure_ascii=False)))
        sources={s['doi']:s for s in spec['sources']}
        for r in spec['candidates']:insert(c,'test_candidates',dict(candidate_id=r['candidate_id'],material_key=mk(r['doi'],r['sample']),record_json=json.dumps(dict(r['record'],source_group='doi:'+r['doi'],evidence_source_path=sources[r['doi']]['path'],source_sha256=sources[r['doi']]['sha256']),ensure_ascii=False),training_eligible=0))
        for r in spec['decisions']:insert(c,'decisions_v15',dict(decision_id=r['id'],doi=r['doi'],record_json=json.dumps(r,ensure_ascii=False)));insert(c,'scientific_issues',dict(issue_id=r['id'],doi=r['doi'],sample_name=None,issue_json=json.dumps(dict(kind=r['id'],action=r['decision']),ensure_ascii=False)))
        for s in spec['sources']:
            review=dict(classification=s['classification'],source_year=s['year'],scope='All main paragraphs and ownmain tables, all figure scopes; PE entire4pageSI read andTableS1 ownrows, Date original6figures obtained',remaining='Other eight PE samples ratecurves and all continuous waveforms; PE2Ecyclewindow; raw spectral/adsorption/EIS values; Date patent carbonization method unacquired',full_source_review_complete=False)
            insert(c,'source_scope_decisions',dict(doi=s['doi'],scope=review['scope'],reason=review['remaining'],evidence_json=json.dumps(review,ensure_ascii=False),full_source_review_complete=0));insert(c,'source_reviews_v15',dict(doi=s['doi'],record_json=json.dumps(review,ensure_ascii=False)))
        c.commit()
    protected={ROOT/d['path']for d in docs.values()}|{PARENT,PE_DIR/'supplementary_package.zip',OUT/'evidence/DatePalm_original_assets.zip',ROOT/'循环稳定性数据库_v0.25_芒果核皮革循环准入_20261026/cycling_v0_25.sqlite',ROOT/'全库复检与特征补提取_20261021/full_corpus_search_native.sqlite'}
    write(OUT/'protected_inputs.json',dict(files=[dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p),bytes=p.stat().st_size)for p in sorted(protected)]))
    print('Built unsealed v15; no model fits or cycling admissions')

def link_known_history():
    """Add an identity relationship only; never replace an endpoint or candidate."""
    assert DB.exists()and not(OUT/'merge_manifest.json').exists()
    from data.cycling_db import open_database
    with open_database()as old:
        matches=[r for r in old.fetch('all_review').rows if r['source_group']=='doi:'+PE and r['sample_name']=='PAC-700'and r['system']=='2E_symmetric'and r['cycle_count']==10000 and r['retention_pct']==99.1]
        assert len(matches)==1 and matches[0]['endpoint_id']=='candidate:V05:034'
    before=sha(DB)
    record=dict(candidate_id='LP15_PAC-700_2E_C10000',existing_endpoint_id=matches[0]['endpoint_id'],cycling_database='循环稳定性数据库_v0.25_芒果核皮革循环准入_20261026/cycling_v0_25.sqlite',cycling_database_sha256='8a8f311509df7d72738840aac31ced027849a538ee31ec785ede71aa4abcc5b2',relation='same_source_sample_and_own_Fig8f_cycling_report',basis='Same DOI/PAC700/symmetric2E/10000/99.1 and sole own PAC cycling trace; not a second independent test',formal_admission_changed=False)
    with closing(sqlite3.connect(DB))as c:
        assert not c.execute("select name from sqlite_master where name='cycle_identity_links_v15'").fetchone()
        c.execute('pragma foreign_keys=on');c.execute('create table cycle_identity_links_v15(candidate_id text primary key references test_candidates,record_json text)');insert(c,'cycle_identity_links_v15',dict(candidate_id=record['candidate_id'],record_json=json.dumps(record,ensure_ascii=False)));c.commit()
    write(OUT/'cycle_identity_review.json',dict(before_draft_sha256=before,after_draft_sha256=sha(DB),additive_relationship_only=True,previous_values_replaced=0,links=[record],reason='Review found PAC cycling report already registered in historical CDB; raw literature transcription remains but cannot count as another endpoint'))

if __name__=='__main__':
    if len(sys.argv)!=2 or sys.argv[1]not in ['curate','build','link_known_history']:raise SystemExit('One-use curate/build/identity link on a new unsealed release only')
    globals()[sys.argv[1]]()
