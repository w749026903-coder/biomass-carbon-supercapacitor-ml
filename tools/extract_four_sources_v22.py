"""One-use, source-bound append for four existing publications; no model fitting."""
from pathlib import Path
from contextlib import closing
import json,re,sqlite3,sys,xml.etree.ElementTree as E
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tools'))
from extract_onion_composite_v8 import sha,write,ro,insert,mk
from extract_palm_kernel_v7 import xml_grid
from extract_source_series_v13 import clean
from extract_five_sources_v20 import numeric_details as original_number
OUT=ROOT/'文献全量利用复核_20261027/批次22_林业多前驱体松木配方与参考体系'
DB=OUT/'literature_material_pool_v22.sqlite'
PARENT=ROOT/'文献全量利用复核_20261027/批次21_候选身份对账与咖啡稻壳工况复核/literature_material_pool_v21.sqlite'
PSHA='6285308f75b13925ff1ee6482ac1143b30712271d7b7809d4f45120cba4bedac'
FO='10.1039/d3ra00820g';PI='10.3390/mi14030572';DI='10.1039/d5ra00450k';MN='10.3390/molecules26237104'
KEYS={FO:'Forest22',PI:'Pine22',DI:'Diaper22',MN:'LigninMn22'}
def numeric_details(raw):
    m=re.fullmatch(r'\(([\d.]+) ± ([\d.]+)\) × 10([+-]?\d+)',raw)
    if m:
        mean,spread,ex=m.groups();factor=10**int(ex)
        return dict(raw_token=raw,value=float(mean)*factor,uncertainty=float(spread)*factor,kind='author_mean_plus_minus_times_ten_power',uncertainty_kind='author_unspecified_not_assumed_SD',exponent=int(ex))
    return original_number(raw)
def number(raw):return numeric_details(raw)['value']

def curate():
    assert sha(PARENT)==PSHA and not DB.exists()and not(OUT/'curation_spec.json').exists()and not(OUT/'merge_manifest.json').exists()
    notes=json.loads((OUT/'source_review_notes.json').read_text('utf8'))
    spec={k:[]for k in ['sources','documents','tables','units','materials','facts','caps','responses','synthesis','decisions','feature_decisions','figures','candidates','annotations','identity_links','raw_dispositions','lineage','protocol_reviews']}
    roots={}
    def doc(key,doi,path,role):
        p=Path(path);p=p if p.is_absolute()else ROOT/p
        assert p.is_file();spec['documents'].append(dict(key=key,doi=doi,path=p.relative_to(ROOT).as_posix(),sha256=sha(p),role=role))
    with closing(ro(ROOT/'全库复检与特征补提取_20261021/full_corpus_search_native.sqlite'))as c:
        c.row_factory=sqlite3.Row
        for s in notes['sources']:
            doi=s['doi'];p=ROOT/s['path'];assert sha(p)==s['sha256'];r=E.parse(p).getroot();roots[doi]=r
            assert {clean(x).lower()for x in r.findall('./front/article-meta/article-id')if x.get('pub-id-type')=='doi'}=={doi}
            years={int(x.text)for x in r.findall('./front/article-meta/pub-date/year')};assert len(years)==1
            spec['sources'].append(dict(s,year=years.pop(),classification='original_SAP_rich_mixed_waste_reference'if doi==DI else'original_biomass_and_explicit_Mn_composite_CV'if doi==MN else'original_biomass_carbon_with_native_residue'if doi==FO else'original_biomass_carbon'))
            doc(KEYS[doi],doi,p,'primary_XML')
            raw={x['locator']:x['table_id']for x in c.execute('select table_id,locator from raw_tables_v11 where source_sha256=?',(s['sha256'],))}
            for t in r.findall('.//table-wrap'):
                loc='XML table-wrap '+t.get('id');spec['tables'].append(dict(doi=doi,id=t.get('id'),document=KEYS[doi],locator=loc,caption=clean(t.find('caption')),footnote=clean(t.find('table-wrap-foot')),grid=xml_grid(t),raw_table_id=raw[loc],kind='native_XML_own_cells_with_foreign_comparison_context_retained'))
            if doi==FO:
                f=next(f for f in r.findall('.//fig')if clean(f.find('label'))=='Fig. 8')
                href=f.find('.//graphic').get('{http://www.w3.org/1999/xlink}href');path=ROOT/'同体系文献补充_第二批_20261017/sources/L04'/href
                binding=[dict(id=f.get('id'),label=clean(f.find('label')),href=href,path=path.relative_to(ROOT).as_posix())]
            else:binding=json.loads((OUT/'evidence'/(KEYS[doi]+'_figure_bindings.json')).read_text('utf8'))
            for b in binding:
                f=next(f for f in r.findall('.//fig')if f.get('id')==b['id']);assert clean(f.find('label'))==b['label']and f.find('.//graphic').get('{http://www.w3.org/1999/xlink}href')==b['href']
                num=int(re.search(r'\d+',b['label'])[0]);key=KEYS[doi]+'_Fig'+str(num);doc(key,doi,b['path'],'original_main_figure')
                spec['figures'].append(dict(doi=doi,figure_number=num,printed_label=b['label'],xml_id=b['id'],graphic_href=b['href'],document=key,equivalent_local_paths=[b['path']],caption=clean(f.find('caption')),scope_visually_inspected=True,full_waveform_extracted=False))
    def unit(doi,id,header,rows,locator,document=None):
        spec['units'].append(dict(doi=doi,id=id,header=header,rows=[[str(v)for v in rr]for rr in rows],locator=locator,document=document or KEYS[doi],kind='own_bound_prose_or_exact_printed_figure_transcription'));return id
    def fact(doi,s,id,row,col,field,un,method,status='own_reported_stage_and_method_qualified'):
        spec['facts'].append(dict(doi=doi,sample=s,id=id,row=row,col=col,field=field,unit=un,method=method,status=status))
    def reg(doi,s,stage,feed):spec['materials'].append(dict(doi=doi,sample=s,stage=stage,feedstock=feed))
    def resp(doi,s,id,row,col,metric,un,**conditions):spec['responses'].append(dict(doi=doi,sample=s,id=id,row=row,col=col,metric=metric,unit=un,conditions=conditions))
    def cap(doi,s,id,row,col,j,purpose=None,method='GCD',scan=None,**conditions):spec['caps'].append(dict(doi=doi,sample=s,id=id,row=row,col=col,j=j,purpose=purpose,method=method,scan=scan,conditions=conditions))
    def issue(doi,id,evidence,decision):spec['decisions'].append(dict(id='V22_'+id,doi=doi,evidence=evidence,decision=decision,not_author_erratum=True))
    def choose(doi,s,f,v,reason):spec['feature_decisions'].append(dict(doi=doi,sample=s,field=f,selected_value=v,reason=reason,not_author_erratum=True))
    def synth(doi,s,loc,stages):spec['synthesis'].append(dict(doi=doi,sample=s,document=KEYS[doi],locator=loc,stages=stages))
    def link(doi,s,endpoint,evidence):spec['identity_links'].append(dict(doi=doi,sample=s,existing_endpoint_id=endpoint,evidence=evidence,not_new_cycling_endpoint=True,core_endpoint_unchanged=True))
    # Forest materials: uncorrected measured carbon, author ash-free recalculation and precursors are distinct.
    forests=['PAC','SAC','LAC','SSAC','SBAC','Full spruce cone']
    feeds=['pine_cone_scales','spruce_cone_scales','larch_cone_scales','silver_spruce_cone_scales','pine_bark_chips','whole_spruce_cone']
    pores=[]
    for row,(s,feed)in enumerate(zip(forests,feeds),2):
        reg(FO,s,'final_biomass_carbon_with_residual_inorganic_before_test',feed);reg(FO,s+' biochar500','precarbonized_biomass_before_activation',feed)
        fact(FO,s,'tab1',row,2,'author_overall_AC_mass_yield_pct','%','Authorapproximateoverallrawbiomass-to-ACmassyield, notcarbonization-onlyyield')
        fact(FO,s+' biochar500','tab1',row,3,'BET_surface_area_m2_g','m2/g','N2BET beforeKOHactivation; fullcone dashnotzero')
        fact(FO,s,'tab1',row,4,'BET_surface_area_m2_g','m2/g','MeasuredN2BET wholeas-preparedACincludingresidue')
        fact(FO,s,'tab1',row,5,'author_ash_free_recalculated_BET_m2_g','m2/g','AuthorBET/TGAmassfraction recalculation, notnewmeasurement')
        fact(FO,s,'tab1',row,7,'TGA_air_author_carbon_fraction_pct','%','AuthorTGAairburnofffraction, notbulkEAelementalC orXPS')
        raw=next(t for t in spec['tables']if t['doi']==FO and t['id']=='tab1')['grid'][row-1][6]['raw'];a,b=re.fullmatch(r'([\d.]+) \(([\d.]+)\)',raw).groups();pores.append([s,a,b])
        stages=[dict(stage='precarbonization',temperature_C=500,duration_h=2,heating_rate_C_min=5,atmosphere='Ar'),dict(stage='chemical_activation',temperature_C=850,duration_h=3,heating_rate_C_min=None,atmosphere='Ar',activator='KOH',carbon_to_activator_mass_ratio=[1,8],prehold_temperature_C=200,prehold_duration_min=30,subsequent_ramp_duration_min=160,solvent='75%ethanol_basis_unspecified',solvent_volume_mL=200),dict(stage='wash',reagent='acetic_acid',concentration_vol_pct=10,water_volume_L=4)]
        synth(FO,s,'MainP11..15 actualtwohold schedule; finalrampnotassumed5Cmin',stages);spec['lineage'].append(dict(doi=FO,parent=s+' biochar500',child=s,kind='KOHactivation'))
    u=unit(FO,'QSDFT_pore_pair',['sample','total','micro'],pores,'Table1 porecellssplit onlybyexplicitcaption total/micro; rawunsplitcells retained')
    for row,s in enumerate(forests,1):
        fact(FO,s,u,row,1,'QSDFT_total_pore_volume_cm3_g','cm3/g','OwnQSDFTslitporemodel total');fact(FO,s,u,row,2,'QSDFT_micropore_volume_cm3_g','cm3/g','OwnQSDFTmicroporevolumeexplicitparentheses')
    reg(FO,'Carbonized spruce Raman','precarbonized_spruce_identity_unbound_to_scale_or_wholecone','spruce_stage_identity_unresolved')
    for row,s in enumerate(['PAC','SAC','LAC','SBAC','Carbonized spruce Raman'],2):
        for col,f in enumerate(['Raman_D_position_cm_inv','Raman_G_position_cm_inv','Raman_ID_IG_author_intensity_area_ambiguous'],1):fact(FO,s,'tab2',row,col,f,'cm-1'if col<3 else'ratio','OwnTable2 declaresintensityratio whilecaptionalsomentionsareas; no assumedfittedarea','ambiguous_peak_intensity_vs_area'if col==3 else'own_reported_stage_and_method_qualified')
    for tid,j,el,con,cycj,prefix in [('tab3',.5,'KOH',6,3,'aqueous'),('tab4',1,'TEA-BF4_acetonitrile',1,5,'organic')]:
        for row,s in enumerate(forests[:3],2):
            base=dict(system='2E_symmetric',electrolyte=el,concentration_mol_L=con,voltage_lower_V=0 if tid=='tab3'else None,voltage_upper_V=1 if tid=='tab3'else None,binder=None,AC_CB_binder_mass_ratio=[8,1,1],electrode_form='pressed_pellet',pressure_MPa=80,electrode_mass_approx_mg=7,electrode_area_cm2=1.2,postelectrode_anneal_C=200,postelectrode_anneal_h=1,postelectrode_anneal_atmosphere='air',current_mass_basis='author_reported_unknown_not_inferred',cross_source_comparable=False)
            for col,norm in [(1,'raw_whole_sample'),(2,'ash_free_author_recalculation')]:
                cap(FO,s,tid,row,col,j,'forest_'+prefix+'_'+norm+'_author_capacity',**base,capacitance_basis='author_source_specific_C_no_main_formula_'+norm,physical_test_group='doi:'+FO+'#'+s+'#'+prefix+'#j'+str(j),same_experiment_recalculation=col==2,not_pooled_with_other_normalization=True)
            for col,metric,un in [(3,'energy_density','Wh/kg'),(4,'power_density','kW/kg'),(5,'response_time','s'),(6,'capacitance_retention','%')]:
                resp(FO,s,tid,row,col,metric,un,**base,current_A_g=cycj if col==6 else 30 if col in [3,4]else None,cycle_count=10000 if col==6 else None,table4_response_time_electrolyte_header_conflict=tid=='tab4'and col==5,not_pretest_predictor=True)
            if tid=='tab3':link(FO,s,'candidate:B20:B2_004:'+str(row-1),'OwnrawBET/actualFig8water0..1V; Table3exactretention10k3Ag andP43pressedpellet. Residualscope andbaseline requireseparatecyclingreview, notadmittedhere.')
            else:spec['candidates'].append(dict(doi=FO,sample=s,candidate_id='LP22:Forest:organic:'+s,record=dict(method='GCD',system='2E_symmetric',electrolyte=el,concentration_mol_L=con,current_A_g=5,cycle_count=10000,retention_pct=float(next(t for t in spec['tables']if t['doi']==FO and t['id']==tid)['grid'][row-1][6]['raw']),voltage_lower_V=None,voltage_upper_V=None,electrode_form='pressed_pellet',evidence='MainTable4/P47; organicwindowunobtained, notinferredfromenergy',scope='organic_and_native_residue_separate',training_eligible=False)))
    for s,bet,hyd in [('LAC H2 separate batch','2981','.96'),('Full larch cone H2 separate batch','2656','.87')]:
        reg(FO,s,'hydrogen_storage_separate_synthesis_batch_not_electrochemical_sample','larch_scales'if s.startswith('LAC ')else'whole_larch_cone')
        u=unit(FO,'H2_'+('scales'if s.startswith('LAC ')else'wholecone'),['sample','BET','H2excess'],[[s,bet,hyd]],'MainP52explicitdifferentLACbatch andP53wholelarchcone; 120bar296K')
        fact(FO,s,u,1,1,'BET_surface_area_m2_g','m2/g','SeparatelysynthesizedH2batch ownBET');resp(FO,s,u,1,2,'hydrogen_excess_storage','wt%',pressure_bar=120,temperature_K=296,not_capacitance_retention=True)
    u=unit(FO,'H2_other',['sample','H2_77K','Gmat','bulk_density'],[['LAC H2 separate batch','4.6','8.9','.2']],'MainP53/P55 H2batch; bulkdensityauthorapprox, Gmatstoragevesselfractionnotpurity')
    resp(FO,'LAC H2 separate batch',u,1,1,'hydrogen_excess_storage','wt%',temperature_K=77,pressure_bar=None);resp(FO,'LAC H2 separate batch',u,1,2,'hydrogen_vessel_Gmat','%',not_composition=True);fact(FO,'LAC H2 separate batch',u,1,3,'author_approx_bulk_density_g_cm3','g/cm3','ApproximateH2batchbulk density, notelectrochemACskeletaldensity')
    issue(FO,'forest_residue_normalization_and_missing_SI',dict(TGA='airburnoffproxy',XRD='Al(OH)3fromceramicboat',aqueous_pellet=True,SI='notobtained',EIS_as_printed='1MHzto10MHz',organic_response_header='inKOH'), 'Keepraw/authorashfreeBET andCseparate. MainTables3/4pressedpellets, notSiO2/GOdispersionSI. No mainCnormalizationformula ororganicwindowguessed; response-timecolumnheaderdissentandliteralEISfrequencyretained. Threeaqueousoldendpointslinkednotadded; residualmaterialscopeandbaselinehandledinlatercyclingreview.')
    # Pine: all five actual samples, one combined thermal step, method-resolved textural cells.
    pine=['Ref-600C','DRY-1','WET-1','DRY-2','WET-2'];t1='micromachines-14-00572-t001';t2='micromachines-14-00572-t002'
    for row,s in enumerate(pine,2):
        reg(PI,s,'final_biomass_carbon_unactivated_control'if row==2 else'final_biomass_carbon_before_test','pine_sawdust')
        for col,el in [(1,'C'),(2,'O')]:fact(PI,s,t1,row,col,'XPS_'+el+'_at_pct','at%','Wholematerials XPSatomicpercentage, no forcedC+O100renormalization')
        for col,peak in [(3,'CC'),(4,'C_O'),(5,'OCO')]:fact(PI,s,t1,row,col,'XPS_C1s_'+peak+'_envelope_pct','%withinC1s','OwnC1sdeconvolutionfractions sumapproximately100; notwholematerialatomicpercent')
        col=row-1
        for rr,field,un,met,status in [(2,'BET_surface_area_m2_g','m2/g','N2BET','own'),(3,'tplot_micropore_area_m2_g','m2/g','tplot','own'),(4,'tplot_external_area_m2_g','m2/g','tplot','own'),(5,'tplot_micropore_volume_raw_m3_g','m3/g_as_printed','RawTable2headingm3/g; actualunitunresolved','ambiguous_unit'),(6,'total_pore_volume_raw_m3_g','m3/g_as_printed','RawTable2headingm3/g; P42cm3/g supportsDRY1/WET1correctionseparately','ambiguous_unit'),(7,'BJH_ads_pore_volume_cm3_g','cm3/g','BJHadsorption','own'),(8,'BJH_des_pore_volume_cm3_g','cm3/g','BJHdesorption','own'),(9,'DH_ads_pore_volume_cm3_g','cm3/g','DollimoreHealadsorption','own'),(10,'DH_des_pore_volume_cm3_g','cm3/g','DollimoreHealdesorption','own'),(11,'HK_at_0_31_pore_volume_cm3_g','cm3/g','AuthorHorvathKawazoeat0.31literal','own'),(12,'BJH_ads_pore_width_reported_nm','nm','BJHheader vs4VT/Sfootnotedisputed; noassumedSdenominator','ambiguous_diameter_method')]:fact(PI,s,t2,rr,col,field,un,met,status)
        stages=[dict(stage='single_carbonization_activation',temperature_C=600,duration_h=2,heating_rate_C_min=5,atmosphere='N2',activator=None if row==2 else'ZnCl2',feedstock_to_activator_mass_ratio=None if row==2 else[1,int(s[-1])],mixing='none_control'if row==2 else'water_impregnation4h_then105Cdry'if s.startswith('WET')else'dry_powder_mix'),dict(stage='wash_dry',reagent='HCl',concentration_M=.5,water_until_neutral=True,drying_temperature_C=105)]
        synth(PI,s,'MainP11..14 onecombined600Cstep, referenceunactivated',stages)
    u=unit(PI,'Vtotal_resolved',['sample','Vtotal'],[['DRY-1','.637'],['WET-1','.664']],'MainP42explicitcm3/g agreesTable2numbers; rawm3/gnotconvertedbymillion')
    for row,s in enumerate(['DRY-1','WET-1'],1):fact(PI,s,u,row,1,'total_pore_volume_cm3_g','cm3/g','WorkingunitselectedviaownexplicitP42, rawTablem3/gretained')
    # Actual Fig4b axis resolves direction; bar heights remain untranscribed, no false exact scalar.
    issue(PI,'pine_Raman_XPS_and_units',dict(actual_Fig4b_axis='ID/IG',caption='IG/ID',body_D_G_word_reversal=True,actual_Fig5e='DRY-2',caption_Fig5e='DRY-1',raw_Vmicro_Vtotal_unit='m3/g',body_Vtotal='cm3/g',He_density=True),'ActualFigure4b ID/IGandFigure5eDRY2 resolvebindingwithrawcaptionretained. Do not treatoverview.86/.89asfiveexactbarvalues. KeepHe-densitybarsundigitized. C1sfractionswithinpeak; rawporeunits/methodsretained andonlyexplicitDRY1/WET1Vtotalunitresolved.')
    u=unit(PI,'Own_GCD',['sample','C_F_g'],[['DRY-1','146'],['WET-1','247'],['DRY-1','59'],['WET-1','64']],'MainP37/P42 Table3ownrows andactualFig7e; WET1.1Ag247 conflictswithplottedfirstredpointbelow220')
    for row,s,j in [(1,'DRY-1',.1),(2,'WET-1',.1),(3,'DRY-1',15),(4,'WET-1',15)]:
        cap(PI,s,u,row,1,j,'reported_aqueous_3e_GCD_capacitance'if row!=2 else None,system='3E',electrolyte='KOH',concentration_mol_L=6,reference_electrode='Ag/AgCl',counter_electrode='Pt',voltage_lower_V=-1,voltage_upper_V=0,binder='PVDF',AC_CB_binder_mass_ratio=[80,10,10],capacitance_basis='author_single_working_active_mass_I_dt_m_dV_excluding_IRdrop',physical_test_group='doi:'+PI+'#'+s+'#3E#j'+str(j),target_issue='Body247 versusactualFig7efirstredpointbelow220unresolved'if row==2 else None)
    issue(PI,'pine_WET1_point1_capacitance_conflict',dict(body_P37=247,body_P42=247,own_Table3=247,actual_Fig7e='RedWET1firstpointbelow220onaxiswhoseupperframeis230',current_A_g=.1),'Retain247asauthorreport, butexcludeonlythisconflictedcapacitanceconditionfrompurposereadyinputs. OtherconsistentownGCDreports146at.1,59/64at15remainusable; nochange94.4/97.8cyclinglabels. Nochoicebyhighercapacitanceorperformancescore.')
    u=unit(PI,'EIS_and_cycles',['sample','ESR','tau','retention'],[['DRY-1','.81','.21','97.8'],['WET-1','.60','.37','94.4']],'MainP39..41 actualFigure8; EISnotintrinsicmaterialconductivity')
    for row,s,endpoint in [(1,'DRY-1','candidate:TE034'),(2,'WET-1','candidate:TE033')]:
        resp(PI,s,u,row,1,'EIS_ESR','ohm',system='3E',frequency_Hz=[.01,1000000]);resp(PI,s,u,row,2,'EIS_time_constant','s',system='3E');resp(PI,s,u,row,3,'capacitance_retention','%',system='3E',cycle_count=5000,current_A_g=5,existing_endpoint_id=endpoint);link(PI,s,endpoint,'Alreadyapprovedexisting3E5000/5Ag, notnewendpoints; actualFig8alsohascycle1/5000inset. Optionalmaterialevidenceonly.')
    # SAP-rich reference: all actual prechars/final carbons, no invented 3x3 matrix.
    diaper=['NHPC-650','NHPC-750','NHPC-850','NAPC-650-1','NAPC-650-2','NAPC-650-4'];reg(DI,'SAP','isolated_diaper_SAP_rich_raw_mixed_waste_reference','isolated_used_diaper_absorbent_unknown_cellulose_fraction')
    for row,s in enumerate(diaper,2):
        stage='SAP_rich_precarbonized_intermediate_reference'if s.startswith('NHPC')else'final_SAP_rich_mixed_waste_carbon_reference';reg(DI,s,stage,'isolated_used_diaper_absorbent_unknown_cellulose_fraction')
        fact(DI,s,'tab1',row,1,'BET_surface_area_m2_g','m2/g','N2BET Table1; competingbodyvalues retainedbelow');fact(DI,s,'tab1',row,2,'tplot_micropore_area_m2_g','m2/g','MethodsP10explicit tplotSmicro, notporevolume')
        temp=int(s.split('-')[1]);stages=[dict(stage='precarbonization',temperature_C=temp,duration_h=3,heating_rate_C_min=2,atmosphere='N2',freeze_drying_days=3,acid_wash_M=.1,drying_temperature_C=100)]
        if s.startswith('NAPC'):
            stages.append(dict(stage='chemical_activation',temperature_C=650,duration_h=3,heating_rate_C_min=2,atmosphere='N2',activator='KOH',carbon_to_activator_mass_ratio=[1,int(s[-1])],acid_wash_M=1,drying_temperature_C=120));spec['lineage'].append(dict(doi=DI,parent='NHPC-650',child=s,kind='separateKOHactivation'))
        else:spec['lineage'].append(dict(doi=DI,parent='SAP',child=s,kind='precarbonization'))
        synth(DI,s,'MainP7..11 actualtemperatures/materialnames, notallpossiblecombination',stages)
    for row,s in enumerate(['SAP','NHPC-650','NHPC-750','NHPC-850','NAPC-650-1','NAPC-650-2'],2):
        for col,el in enumerate(['C','H','N','O'],1):fact(DI,s,'tab2',row,col,'elemental_analysis_'+el+'_pct_basis_unspecified','%basis_unspecified','Table2elementalanalysis; noinstrumentorwt/atbasisdeclared; notXPS','ambiguous_percent_basis')
        for col,f in enumerate(['H_C','O_C','O_N_C'],5):fact(DI,s,'tab2',row,col,'elemental_analysis_author_'+f+'_ratio','ratio','PrintedC/H/N/Oratios, massvsatomicbasisunreported','ambiguous_percent_basis')
    u=unit(DI,'Body_BET_competing',['sample','BET'],[['NAPC-650-1','1277'],['NAPC-650-2','2299']],'MainP16body versusTable1 1678/2239, notdeclaredworkingcorrection')
    for row,s in enumerate(['NAPC-650-1','NAPC-650-2'],1):fact(DI,s,u,row,1,'BET_surface_area_m2_g','m2/g','OwnbodyP16competingwithTable1','conflict_body_vs_table');choose(DI,s,'BET_surface_area_m2_g',None,'Table1andbodydisagree; noauthoritytoresolvenumerically, freezeoptionalBETforonlythissample')
    u=unit(DI,'Printed_Raman',['sample','ID_IG'],list(zip(diaper,['.780','.818','.827','.769','.791','.856'])),'ActualFig4b printedID/IG, allsixvalues including750/850unreportedindetailedbody',KEYS[DI]+'_Fig4')
    for row,s in enumerate(diaper,1):fact(DI,s,u,row,1,'Raman_ID_IG','ratio','ActualoriginalFig4bprintedintensityratio')
    # Literal peak labels, not quantitative N fractions. Body and figure disagree for O/N assignments.
    peaks=[['C1s_CC','284.8'],['C1s_CN','286.3'],['C1s_OCOH','289.98'],['O1s_CO','531.28'],['O1s_COH','532.68'],['O1s_OCOCO','533.88'],['N1s_N6','398.48'],['N1s_N5','399.98'],['N1s_NQ','400.68'],['N1s_NX','402.1']]
    u=unit(DI,'Printed_XPS_peak_positions',['component','eV'],peaks,'ActualFig6hasthreeO1sandfourN1scomponents; bodylistsothercentres/componentcounts; claimskeptseparate',KEYS[DI]+'_Fig6')
    for row,(peak,val)in enumerate(peaks,1):fact(DI,'NAPC-650-4',u,row,1,'XPS_printed_'+peak+'_binding_energy_eV','eV','ActualFig6printedpeaklabel, notfraction; bodyassignmentsdissent')
    u=unit(DI,'Body_XPS_positions',['component','eV'],[['C1s_CC','284.88'],['O1s_CO','532.47'],['O1s_OCO','533.68'],['N1s_N6','398.44'],['N1s_N5','400.5'],['N1s_NX','402.93']],'MainP20literalprosepositionsdissentfromactualFig6')
    for row,(peak,val)in enumerate([['C1s_CC','284.88'],['O1s_CO','532.47'],['O1s_OCO','533.68'],['N1s_N6','398.44'],['N1s_N5','400.5'],['N1s_NX','402.93']],1):fact(DI,'NAPC-650-4',u,row,1,'XPS_body_'+peak+'_binding_energy_eV','eV','Literalbodyclaim, notresolvedchemicalassignment','conflict_body_peak_assignment')
    u=unit(DI,'Own_GCD',['sample','C_F_g'],[['NHPC-650','140'],['NAPC-650-4','353'],['NAPC-650-4','250'],['NAPC-650-4','208.1']],'MainP22/P24 exactownGCD; actualFig7threeelectrode-1..0V andFig9device0..1V')
    for row,s,j in [(1,'NHPC-650',1),(2,'NAPC-650-4',1),(3,'NAPC-650-4',10),(4,'NAPC-650-4',.5)]:
        cap(DI,s,u,row,1,j,'SAP_rich_reference_3e_GCD'if row<4 else'SAP_rich_reference_2e_author_factor2',system='3E'if row<4 else'2E_symmetric',electrolyte='KOH',concentration_mol_L=6,voltage_lower_V=-1 if row<4 else 0,voltage_upper_V=0 if row<4 else 1,reference_electrode='calomel'if row<4 else None,binder='PTFE',AC_CB_binder_mass_ratio=[80,10,10],capacitance_basis='author_I_dt_m_dV'if row<4 else'author_2I_t_m_dV_m_identity_not_redefined_for2E',physical_test_group='doi:'+DI+'#'+s+'#'+('3E'if row<4 else'2E')+'#j'+str(j),cross_source_comparable=False,material_scope='SAP_rich_mixed_waste_reference_not_ordinary_biomass')
    u=unit(DI,'Own_responses',['sample','Rct','cycle_retention','energy_low','power_low','energy_high','power_high','body_rate_retention_claim'],[['NAPC-650-4','.126','87.65','7.22','125','3.12','5.1','87.65']],'MainP22..25; cycle10k10Ag vsrateclaim87.65roleconflict; CE96..100notretention')
    for col,metric,un in [(1,'EIS_Rct','ohm'),(2,'capacitance_retention','%'),(3,'energy_density','Wh/kg'),(4,'power_density','W/kg'),(5,'energy_density','Wh/kg'),(6,'power_density','kW/kg'),(7,'author_rate_retention_claim_conflicting','%')]:resp(DI,'NAPC-650-4',u,1,col,metric,un,cycle_count=10000 if col==2 else None,current_A_g=10 if col==2 else None,system='3E'if col in [1,2,7]else'2E_symmetric',not_ordinary_biomass=True)
    link(DI,'NAPC-650-4','candidate:TE032','Existingmixed_cellulose_SAP_diaper_feedstockineligible. 87.65cycle10k10Agretained; trueSAPfractionunknown, notsilentlyincludedordinarybiomass.')
    issue(DI,'SAP_scope_methods_BET_and_formula',dict(Table3_caption='CHNC7004-25stray',ownrow='NAPC6504',BET_table=[1678,2239],BET_body=[1277,2299],Table2_missing='NAPC6504',CV_body_window=[-1.1,1.1],actual_Fig7_window=[-1,0],actual_Fig9_window=[0,1],body_XPS='2O/3Ncomponents',actual_XPS='3O/4Ncomponents',energy_formula_graphic='E=1/2*1/4*dV^2/3.6_withoutC'), 'KeepallactualstagesandownreportsasSAP-richmixedreference. Elementalpercentbasisnotdeclared, notinheritedbyNAPC6504. Preservebody/plot/unitsandformulaomission; chooseactualtestedwindowsforGCD, do notconstructenergyfrommalformedformula. Cyclic87.65notrate250/353, noordinarycyclingadmission.')
    # Lignin: all eight CV-tested finals, two distinct kinetic precursors and raw extracted lignin.
    reg(MN,'extracted lignin','organosolv_lignin_precursor','oil_palm_wood');reg(MN,'LS120% precursor','crosslinked_lignin_F127_precursor','oil_palm_lignin_F127_formaldehyde');reg(MN,'LS120%-Mn20% precursor','crosslinked_lignin_F127_Mn_precursor','oil_palm_lignin_F127_formaldehyde_MnNO3')
    mn=['C-LS0%','C-LS20%','C-LS40%','C-LS80%','C-LS120%','C-LS120%-Mn5%','C-LS120%-Mn10%','C-LS120%-Mn20%']
    for row,s in enumerate(mn,2):
        composite='-Mn'in s;reg(MN,s,'final_Mn3O4_MnO_lignin_carbon_composite_oxidized_before_test'if composite else'final_H2O2_oxidized_lignin_F127_carbon_before_test','oil_palm_organosolv_lignin')
        ratio=120 if composite else int(re.search(r'LS(\d+)',s)[1]);load=int(re.search(r'Mn(\d+)',s)[1])if composite else None
        synth(MN,s,'MainP33..34/P42; N2carbonizationthensteam900C2h, heatingrate/durationofpriorstepnotgiven',[dict(stage='organosolv_extraction',temperature_C=150,duration_min=150,ethanol_vol_pct=70,atmosphere='pressurized_N2',mesh=50),dict(stage='template_crosslink',lignin_mass_g=4,F127_to_lignin_mass_pct=ratio,Mn_precursor_nominal_loading_wt_pct=load,nominal_loading_not_final_composition=True,water_mL=30,HCl_M=1,HCl_mL=3,formaldehyde_pct=37,formaldehyde_mL=5),dict(stage='carbonization',atmosphere='N2',temperature_C=None,duration_h=None,heating_rate_C_min=None),dict(stage='steam_activation',temperature_C=900,duration_h=2),dict(stage='pretest_oxidation',H2O2_vol_pct=15,material_to_solution_w_v=[1,200],drying='room_temperature')])
        cap(MN,s,'molecules-26-07104-t004',row,1,None,'lignin_Mn_author_CV_10mVs'if composite else'lignin_F127_author_CV_10mVs',method='CV',scan=10,system='3E',electrolyte='H2SO4',concentration_mol_L=1,voltage_lower_V=-.2,voltage_upper_V=.7,reference_electrode='Ag/AgCl',counter_electrode='Pt',binder='Nafion',capacitance_basis='author_specific_CV_no_calculation_formula_provided',physical_test_group='doi:'+MN+'#'+s+'#CV10',cross_source_comparable=False,material_scope='Mnoxide_composite'if composite else'template_assisted_oxidized_lignin_carbon',drop_volume_as_printed='10liters',glassy_carbon_diameter_as_printed_mm=.3,not_assumed_typographical_correction=True)
    for row,s in [(3,'C-LS20%'),(4,'C-LS80%'),(5,'C-LS120%'),(6,'C-LS120%-Mn5%'),(7,'C-LS120%-Mn20%')]:
        for col,f,un,met in [(2,'BET_surface_area_m2_g','m2/g','AuthorN2sorptionSSA BETformulaunspecified'),(3,'author_micropore_volume_fraction_pct','%','TableVmicaspercentage notabsolutevolume'),(4,'average_pore_diameter_reported_nm','nm','Authoraverageporediameternomodelspecified')]:fact(MN,s,'molecules-26-07104-t003',row,col,f,un,met)
    for col,el in enumerate(['C','O','Mn'],1):fact(MN,mn[-1],'molecules-26-07104-t002',3,col,'SEM_EDX_'+el+'_reported_pct_basis_unspecified','%basis_unspecified','SEM-EDX15kV; percentbasisnotdeclared, notXPSorassumedwt','ambiguous_percent_basis')
    for row in range(2,10):
        s='LS120% precursor'if row<6 else'LS120%-Mn20% precursor';ramp=5 if row in [2,3,6,7]else 10;order=1 if row in [2,4,6,8]else 2
        for col,metric,un in [(3,'pyrolysis_model_pre_exponential_factor','s-1_as_table_vs_min-1_body'),(4,'pyrolysis_model_activation_energy','kJ/mol'),(5,'pyrolysis_model_fit_R2','ratio')]:resp(MN,s,'molecules-26-07104-t001',row,col,metric,un,heating_rate_C_min=ramp,reaction_order=order,not_model_predictive_performance=True,not_cycle_count=True,A_unit_conflict=col==3)
    u=unit(MN,'Lignin_yield',['sample','yield'],[['extracted lignin','30']],'MainP6 averagefiveextractions, notfinalcarbonyield');resp(MN,'extracted lignin',u,1,1,'organosolv_extraction_yield','%',replicates=5,not_carbonization_yield=True)
    issue(MN,'lignin_CV_composite_and_process_roles',dict(phases=['Mn3O4','MnO'],Table4_own=[22,14.1,33.6,81.7,140.9,128.3,223.8,345.3],method='CV10mVs',GCD_cyclelife='explicitfuturework',EDX_basis='unspecified',A_unit_table='s-1',A_unit_body='min-1',drop_volume='10liters',GC_diameter_mm=.3), 'EightownCVcapacityreports retainedbytemplate/carbonvsMncompositepurpose, noGCD/lifetime/currentinvented. EDXmethodexplicitbutat/wtbasisunknown; nominalMnloadingnotactualMnOweightpercent. KineticsA/Ea/R2arecarbonizationmodelresponses, notbatterycyclesorourmodelaccuracy. Literalvolume/dimensionsandAunitdissentretained; no silent10uLor3mmrepair.')
    for doi in KEYS:
        spec['annotations'].append(dict(id='V22_'+KEYS[doi]+'_scope',doi=doi,document=KEYS[doi],scope='All own native main tables and full body reviewed; 25 available original figure scopes inspected. Continuous waveforms/undigitizedbars remain; ForestSI and10 mainfigures notobtained.',full_source_review_complete=False))
        spec['protocol_reviews'].append(dict(doi=doi,scope='Per-condition exact method/window/material/normalization in caps and response records',current_mass_basis='author_reported_unknown_not_inferred',full_source_complete=False))
    for p in sorted((OUT/'evidence/Diaper22').glob('*-t*.jpg')):doc('Diaper22_formula_'+p.stem,DI,p,'original_formula_graphic')
    write(OUT/'curation_spec.json',spec);print({k:len(v)for k,v in spec.items()})

def build():
    assert sha(PARENT)==PSHA and not DB.exists()and not(OUT/'merge_manifest.json').exists()
    spec=json.loads((OUT/'curation_spec.json').read_text('utf8'));docs={d['key']:d for d in spec['documents']}
    with closing(ro(PARENT))as parent,closing(sqlite3.connect(DB))as c:
        parent.backup(c);c.row_factory=sqlite3.Row;c.execute('pragma foreign_keys=on')
        c.executescript('''create table source_reviews_v22(doi text primary key references reviewed_sources,record_json text);create table cell_extractions_v22(kind text,record_id text,table_key text references reviewed_tables,row_ordinal integer,column_ordinal integer,primary key(kind,record_id));create table decisions_v22(decision_id text primary key,doi text references reviewed_sources,record_json text);create table material_feature_decisions_v22(material_key text references materials,field_name text,record_json text,primary key(material_key,field_name));create table purpose_reviews_v22(observation_id text primary key references capacitance_observations,purpose text,eligible integer,record_json text);create table figure_scope_reviews_v22(doi text references reviewed_sources,figure_number integer,document_key text references source_documents,record_json text,primary key(doi,figure_number));create table annotations_v22(annotation_id text primary key,doi text references reviewed_sources,document_key text references source_documents,record_json text);create table cycle_identity_links_v22(link_id text primary key,record_json text);''')
        for s in spec['sources']:insert(c,'reviewed_sources',dict(doi=s['doi'],path=s['path'],sha256=s['sha256'],title=s['title'],stage='Four own sources; main tables, full body and available original figures; missing ForestSI/figures and untranscribed waveforms remain'))
        for d in docs.values():assert sha(ROOT/d['path'])==d['sha256'];insert(c,'source_documents',dict(document_key=d['key'],doi=d['doi'],path=d['path'],sha256=d['sha256'],role=d['role']))
        for t in spec['tables']+spec['units']:
            key=t['doi']+'#'+t['id'];rows=[[v['raw']for v in r]for r in t['grid']]if'grid'in t else t['rows'];insert(c,'reviewed_tables',dict(table_key=key,doi=t['doi'],xml_id=t['id'],caption=t.get('caption',t['id']),header_json=json.dumps(rows[0]if'grid'in t else t['header']),footnote=t.get('footnote','Own bounded transcription; stages/repeats/foreign comparisons kept distinct'),source_raw_table_id=t.get('raw_table_id')));insert(c,'table_source_links',dict(table_key=key,document_key=t['document'],locator=t['locator']));insert(c,'extraction_units_v3',dict(table_key=key,kind=t['kind'],scope='Own explicitly bound cells only; foreign rows retained as context, never admitted'))
            for i,row in enumerate(rows,1):insert(c,'transcribed_rows',dict(table_key=key,row_ordinal=i,cells_json=json.dumps(row,ensure_ascii=False)));insert(c,'transcription_origins_v7',dict(table_key=key,row_ordinal=i,origin_json=json.dumps(t['grid'][i-1]if'grid'in t else dict(document=t['document'],locator=t['locator'],row=i),ensure_ascii=False)))
            if t.get('raw_table_id'):
                assert c.execute('select review_state from raw_table_queue where table_id=?',(t['raw_table_id'],)).fetchone()[0]=='automatic_candidate_unreviewed'
                c.execute('update raw_table_queue set review_state=?where table_id=?',('v22_own_cells_methods_stage_and_conflicts_reviewed',t['raw_table_id']))
        for r in spec['materials']:
            insert(c,'materials',dict(material_key=mk(r['doi'],r['sample']),doi=r['doi'],sample_name=r['sample'],material_stage=r['stage']));insert(c,'material_scopes_v8',dict(material_key=mk(r['doi'],r['sample']),scope_json=json.dumps(dict(origin_class='SAP_rich_mixed_waste_reference'if r['doi']==DI else'Mnoxide_lignin_carbon_composite'if'Mn3O4'in r['stage']else'biomass_carbon_or_precursor',feedstock=r['feedstock'],stage=r['stage'],not_assumed_pure_carbon=True,same_source_not_independent=True))))
        def cell(r):
            key=r['doi']+'#'+r['id'];raw=json.loads(c.execute('select cells_json from transcribed_rows where table_key=?and row_ordinal=?',(key,r['row'])).fetchone()[0])[r['col']];return key,raw,number(raw)
        def receipt(kind,rid,r,key):insert(c,'cell_extractions_v22',dict(kind=kind,record_id=str(rid),table_key=key,row_ordinal=r['row'],column_ordinal=r['col']))
        for r in spec['facts']:
            key,raw,value=cell(r);doc=c.execute('select document_key from table_source_links where table_key=?',(key,)).fetchone()[0];q=insert(c,'material_facts',dict(material_key=mk(r['doi'],r['sample']),field_name=r['field'],value=value,raw_value=raw,unit=r['unit'],method=r['method'],table_key=key,row_ordinal=r['row'],column_ordinal=r['col'],source_sha256=docs[doc]['sha256'],review_status=r['status'],training_eligible=0));receipt('fact',q.lastrowid,r,key)
        for r in spec['caps']:
            key,raw,value=cell(r);rid=key+'#'+str(r['row'])+'#'+str(r['col']);cond=dict(extraction_batch='v22',current_mass_basis='author_reported_unknown_not_inferred',repeat_reports_not_independent=True);cond.update(r['conditions'])
            insert(c,'capacitance_observations',dict(observation_id=rid,material_key=mk(r['doi'],r['sample']),table_key=key,row_ordinal=r['row'],column_ordinal=r['col'],value=value,raw_value=raw,unit='F/g',method=r['method'],system=cond['system'],electrolyte=cond['electrolyte'],concentration_mol_L=cond['concentration_mol_L'],current_A_g=r['j'],scan_rate_mV_s=r['scan'],conditions_json=json.dumps(cond,ensure_ascii=False),status='own_reported'if r['purpose']else'own_repeat_or_competing_report',source_group='doi:'+r['doi'],training_eligible=0));receipt('capacitance',rid,r,key)
            if r['purpose']:
                reason='Own bound fresh method-specific report; explicit target/normalization/material scope, optional missing fields masked; source-specific ambiguous C/Cg never mixed into unified targets'
                insert(c,'purpose_reviews_v22',dict(observation_id=rid,purpose=r['purpose'],eligible=1,record_json=json.dumps(dict(reason=reason,purpose_input_ready=True,cyclic_retention_training_admitted=False,training_authorized=False))))
                if r['purpose']=='reported_aqueous_3e_GCD_capacitance':insert(c,'auxiliary_gcd_reviews_v3',dict(observation_id=rid,purpose=r['purpose'],eligible=1,reason=reason,review_basis='Own specific results/actual printed plot and matched own protocol, variants retained; no performance-based selection'))
        for r in spec['responses']:
            key,raw,value=cell(r);rid=key+'#'+str(r['row'])+'#'+str(r['col']);insert(c,'outcome_observations_v3',dict(outcome_id=rid,material_key=mk(r['doi'],r['sample']),table_key=key,record_json=json.dumps(dict(source_group='doi:'+r['doi'],extraction_batch='v22',metric=r['metric'],value=value,raw_value=raw,unit=r['unit'],**(dict(feature_role='test_or_process_response_not_pretest_predictor')|r['conditions'])),ensure_ascii=False),training_eligible=0));receipt('response',rid,r,key)
        for r in spec['synthesis']:insert(c,'synthesis_stages_v3',dict(material_key=mk(r['doi'],r['sample']),document_key=r['document'],locator=r['locator'],stages_json=json.dumps(r['stages'],ensure_ascii=False)))
        for r in spec['feature_decisions']:insert(c,'material_feature_decisions_v22',dict(material_key=mk(r['doi'],r['sample']),field_name=r['field'],record_json=json.dumps(r,ensure_ascii=False)))
        for r in spec['decisions']:insert(c,'decisions_v22',dict(decision_id=r['id'],doi=r['doi'],record_json=json.dumps(r,ensure_ascii=False)));insert(c,'scientific_issues',dict(issue_id=r['id'],doi=r['doi'],sample_name=None,issue_json=json.dumps(dict(kind=r['id'],action=r['decision']),ensure_ascii=False)))
        for r in spec['figures']:insert(c,'figure_scope_reviews_v22',dict(doi=r['doi'],figure_number=r['figure_number'],document_key=r['document'],record_json=json.dumps(r,ensure_ascii=False)))
        for r in spec['annotations']:insert(c,'annotations_v22',dict(annotation_id=r['id'],doi=r['doi'],document_key=r['document'],record_json=json.dumps(r,ensure_ascii=False)))
        for r in spec['identity_links']:insert(c,'cycle_identity_links_v22',dict(link_id='LP22_'+r['existing_endpoint_id'],record_json=json.dumps(r,ensure_ascii=False)))
        sources={r['doi']:r for r in spec['sources']}
        for r in spec['candidates']:insert(c,'test_candidates',dict(candidate_id=r['candidate_id'],material_key=mk(r['doi'],r['sample']),record_json=json.dumps(dict(r['record'],source_group='doi:'+r['doi'],source_year=sources[r['doi']]['year'],evidence_source_path=sources[r['doi']]['path'],source_sha256=sources[r['doi']]['sha256'],current_mass_basis='author_reported_unknown_not_inferred',baseline_cycle=None,baseline_reference='author_reference_not_assumed_cycle1'),ensure_ascii=False),training_eligible=0))
        for s in spec['sources']:
            review=dict(source_year=s['year'],classification=s['classification'],scope='Ownmain tables, fullbody, actualprintedlabels and available mainfigure scope',remaining='Continuous spectra/isotherms/CV/GCD/EIS, untranscribed rate markers, unresolved protocols/identities; not full-source extraction.',full_source_review_complete=False)
            insert(c,'source_scope_decisions',dict(doi=s['doi'],scope=review['scope'],reason=review['remaining'],evidence_json=json.dumps(review,ensure_ascii=False),full_source_review_complete=0));insert(c,'source_reviews_v22',dict(doi=s['doi'],record_json=json.dumps(review,ensure_ascii=False)))
        c.executescript('create table raw_candidate_dispositions_v22(table_id text primary key references raw_table_queue,record_json text);create table numeric_details_v22(fact_id integer primary key references material_facts,record_json text);create table material_lineage_v22(lineage_id integer primary key,parent_key text references materials,child_key text references materials,record_json text);')
        for r in spec['raw_dispositions']:
            c.execute('update raw_table_queue set review_state=?where table_id=?',(r['disposition'],r['table_id']));insert(c,'raw_candidate_dispositions_v22',dict(table_id=r['table_id'],record_json=json.dumps(r,ensure_ascii=False)))
        for r in c.execute('select f.fact_id,f.raw_value,f.method from material_facts f join cell_extractions_v22 x on x.record_id=cast(f.fact_id as text)and x.kind="fact"').fetchall():
            nd=numeric_details(r['raw_value'])
            if 'mean±SD'in r['method']:nd['uncertainty_kind']='author_mean_and_SD'
            insert(c,'numeric_details_v22',dict(fact_id=r['fact_id'],record_json=json.dumps(nd,ensure_ascii=False)))
        for r in spec['lineage']:insert(c,'material_lineage_v22',dict(parent_key=mk(r['doi'],r['parent']),child_key=mk(r['doi'],r['child']),record_json=json.dumps(r,ensure_ascii=False)))
        c.execute('create table protocol_reviews_v22(doi text primary key references reviewed_sources,record_json text)')
        for r in spec['protocol_reviews']:insert(c,'protocol_reviews_v22',dict(doi=r['doi'],record_json=json.dumps(r,ensure_ascii=False)))
        c.commit()
    protected={ROOT/d['path']for d in docs.values()}|{PARENT,ROOT/'循环稳定性数据库_v0.26_蛋米循环电流补正_20261027/cycling_v0_26.sqlite',ROOT/'全库复检与特征补提取_20261021/full_corpus_search_native.sqlite'}
    protected.update(p for p in (OUT/'evidence').rglob('*.zip'))
    protected.update(ROOT/p for p in ['三电极端点扩充_20261018/new_sources/PMC10056672/figures_and_supplements.zip','三电极端点扩充_20261018/new_sources/PMC12175059/figures_and_supplements.zip'])
    write(OUT/'protected_inputs.json',dict(files=[dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p),bytes=p.stat().st_size)for p in sorted(protected)]));print('Built unsealed v22; originalcyclinglabels unchanged, no fitting')



if __name__=='__main__':
    if len(sys.argv)!=2 or sys.argv[1]not in ['curate','build']:raise SystemExit('One-use curate/build only before sealing')
    globals()[sys.argv[1]]()
