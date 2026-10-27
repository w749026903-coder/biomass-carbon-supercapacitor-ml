"""One-use source-bound extraction, with stages, formulas and disputed reports retained."""
from pathlib import Path
from contextlib import closing
import json,re,sqlite3,sys,xml.etree.ElementTree as E
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tools'))
from extract_onion_composite_v8 import sha,write,ro,insert,mk
from extract_palm_kernel_v7 import xml_grid
from extract_source_series_v13 import clean
from extract_lignin_egg_tobacco_v19 import numeric_details as details19
OUT=ROOT/'文献全量利用复核_20261027/批次20_橙汁稻壳咖啡污泥螺旋藻与辣木'
DB=OUT/'literature_material_pool_v20.sqlite'
PARENT=ROOT/'文献全量利用复核_20261027/批次19_木质素纳米纤维蛋米与烟草系列/literature_material_pool_v19.sqlite'
PSHA='2575e0462738b534de8931dd98a1ea471948741a976eba36235199235892392e'
OJ='10.3390/nano14010071';RH='10.1039/d5ra03028e';CO='10.1021/acsomega.3c09438';SP='10.3390/nano13172431';MO='10.1021/acsomega.2c04301'
KEYS={OJ:'OJ20',RH:'Rice20',CO:'Coffee20',SP:'Spirulina20',MO:'Moringa20'}
SI={OJ:'同体系文献补充_第二批_20261017/定向扩搜40至60篇_20261017/sources/OA006/nanomaterials-2759617-SI.pdf',RH:'循环稳定性文献补充_20261017/N001/RA-015-D5RA03028E-s001.pdf',CO:'循环稳定性数据库_v0.3_数据库优化_20261017/第三轮_逐条准入闭环_20261017/external_sources/R104_ao3c09438_si_001.pdf',SP:'同体系文献补充_第二批_20261017/定向扩搜40至60篇_20261017/sources/OA043/nanomaterials-2538993-supplementary.pdf'}
def numeric_details(raw):
    token=raw.strip().replace('−','-').replace('–','-')
    if token in ['---','——','–','-','—','']:return dict(raw_token=raw,value=None,kind='not_reported_or_not_resolved_dash_not_zero',uncertainty=None)
    token=re.sub(r'\s*at\s*%$','',token).strip();token=re.sub(r'(?<=\d),(?=\d{3}(?:\D|$))','',token)
    d=details19(token);d['raw_token']=raw;return d
def number(raw):return numeric_details(raw)['value']
def curate():
    assert sha(PARENT)==PSHA and not DB.exists()and not(OUT/'curation_spec.json').exists()and not(OUT/'merge_manifest.json').exists()
    notes=json.loads((OUT/'source_review_notes.json').read_text('utf8'))
    spec={k:[]for k in ['sources','documents','tables','units','materials','facts','caps','responses','synthesis','decisions','feature_decisions','figures','candidates','annotations','identity_links','raw_dispositions','lineage','protocol_reviews']}
    roots={};tabs={}
    def doc(key,doi,path,role):
        path=Path(path);assert path.is_file();spec['documents'].append(dict(key=key,doi=doi,path=path.relative_to(ROOT).as_posix()if path.is_absolute()else path.as_posix(),sha256=sha(path),role=role))
    with closing(ro(ROOT/'全库复检与特征补提取_20261021/full_corpus_search_native.sqlite'))as n:
        n.row_factory=sqlite3.Row
        for src in notes['sources']:
            doi=src['doi'];p=ROOT/src['path'];assert sha(p)==src['sha256'];r=E.parse(p).getroot();roots[doi]=r
            assert {x.text.lower()for x in r.findall('./front/article-meta/article-id')if x.get('pub-id-type')=='doi'}=={doi}
            identities=list(n.execute('select distinct identity_key from identity_sources where sha256=?',(src['sha256'],)));assert {x[0]for x in identities}=={'doi:'+doi}
            years={int(x.text)for x in r.findall('./front/article-meta/pub-date/year')};assert len(years)==1,years
            spec['sources'].append(dict(src,title=clean(r.find('.//article-title')),year=years.pop(),classification='original_biomass_research_with_explicit_method_scopes'));doc(KEYS[doi],doi,p,'primary_XML')
            raw={x['locator']:x['table_id']for x in n.execute('select table_id,locator from raw_tables_v11 where source_sha256=?',(src['sha256'],))}
            for t in r.findall('.//table-wrap'):
                loc='XML table-wrap '+t.get('id');g=xml_grid(t);tabs[doi,t.get('id')]=[[v['raw']for v in rr]for rr in g]
                spec['tables'].append(dict(doi=doi,id=t.get('id'),document=KEYS[doi],locator=loc,caption=clean(t.find('caption')),footnote=clean(t.find('table-wrap-foot')),grid=g,raw_table_id=raw[loc],kind='native_XML_table_own_cells_only_foreign_comparisons_retained'))
            bindings=json.loads((OUT/'evidence'/(src['key']+'_figure_bindings.json')).read_text('utf8'))
            for b in bindings:
                f=next(f for f in r.findall('.//fig')if f.get('id')==b['id']);assert clean(f.find('label'))==b['label']and f.find('.//graphic').get('{http://www.w3.org/1999/xlink}href')==b['href']
                assert all(sha(ROOT/q)==b['sha256']for q in b['equivalent_local_paths']);num=int(re.search(r'\d+',b['label'])[0]);key=KEYS[doi]+'_Fig'+str(num);doc(key,doi,ROOT/b['path'],'original_main_figure')
                spec['figures'].append(dict(doi=doi,figure_number=num,printed_label=b['label'],xml_id=b['id'],graphic_href=b['href'],document=key,caption=clean(f.find('caption')),equivalent_local_paths=b['equivalent_local_paths'],scope_visually_inspected=True,full_waveform_extracted=False,remaining='Continuous waveforms and untranscribed markers remain; scope inspection is not full numerical extraction'))
            if doi in SI:doc(KEYS[doi]+'_SI',doi,ROOT/SI[doi],'original_SI_PDF')
            for x in n.execute('select distinct t.*from raw_tables_v11 t join identity_sources i on t.source_sha256=i.sha256 where i.identity_key=?',('doi:'+doi,)):
                if x['locator'].startswith('XML'):continue
                spec['raw_dispositions'].append(dict(table_id=x['table_id'],doi=doi,source_sha256=x['source_sha256'],locator=x['locator'],caption=x['caption'],disposition='v20_same_article_HTML_duplicate_own_rows_and_foreign_context_reviewed'if x['locator'].startswith('HTML')else'v20_SI_physical_tables_transcribed_merged_parser_context_retained',not_new_independent_table=x['locator'].startswith('HTML')))
    def unit(doi,id,header,rows,locator,document=None,kind='own_bound_prose_or_printed_figure_transcription'):
        spec['units'].append(dict(doi=doi,id=id,header=header,rows=[[str(v)for v in rr]for rr in rows],locator=locator,document=document or KEYS[doi],kind=kind));return id
    def fact(doi,s,id,row,col,field,u,method,status='own_reported_method_and_stage_qualified'):
        spec['facts'].append(dict(doi=doi,sample=s,id=id,row=row,col=col,field=field,unit=u,method=method,status=status))
    def reg(doi,s,stage,feed):spec['materials'].append(dict(doi=doi,sample=s,stage=stage,feedstock=feed))
    def resp(doi,s,id,row,col,metric,u,**conditions):spec['responses'].append(dict(doi=doi,sample=s,id=id,row=row,col=col,metric=metric,unit=u,conditions=conditions))
    def cap(doi,s,id,row,col,j,purpose=None,method='GCD',scan=None,**conditions):spec['caps'].append(dict(doi=doi,sample=s,id=id,row=row,col=col,j=j,purpose=purpose,method=method,scan=scan,conditions=conditions))
    def issue(doi,id,evidence,decision):spec['decisions'].append(dict(id='V20_'+id,doi=doi,evidence=evidence,decision=decision,not_author_erratum=True))
    def choose(doi,s,f,v,reason):spec['feature_decisions'].append(dict(doi=doi,sample=s,field=f,selected_value=v,reason=reason,not_author_erratum=True))
    def synth(doi,s,loc,stages):spec['synthesis'].append(dict(doi=doi,sample=s,document=KEYS[doi],locator=loc,stages=stages))
    # Orange juice: nine actual final materials and two distinct precursors.
    oj=[];t1='nanomaterials-14-00071-t001';t2='nanomaterials-14-00071-t002';t3='nanomaterials-14-00071-t003'
    for row,ratio in enumerate([3,4,5],3):
        for col,minutes in enumerate([30,120,210],1):
            s=f'{ratio}:1@{minutes}';oj.append(s);reg(OJ,s,'final_biomass_carbon_before_test','orange_juice');fact(OJ,s,t1,row,col,'BET_surface_area_m2_g','m2/g','N2BET; authortriplicateexperiments, ±type unspecified for this material table')
            synth(OJ,s,'MainP9 andTable1 separatehydrothermal/pyrolysis/activation',[dict(stage='hydrothermal',temperature_C=180,duration_h=6,juice_volume_mL=225),dict(stage='precarbonization',temperature_C=800,duration_h=None,atmosphere='N2',flow_mL_min=800),dict(stage='chemical_activation',temperature_C=800,duration_h=minutes/60,raw_duration_min=minutes,atmosphere='N2',flow_mL_min=800,carbon_to_activator_mass_ratio=[1,ratio],activator='KOH'),dict(stage='acid_wash',reagent='HCl',concentration_M=1,neutral_water_pH=7)])
    reg(OJ,'hydrochar180','hydrothermal_biomass_intermediate','orange_juice');reg(OJ,'pyrochar800','precarbonized_biomass_before_activation','orange_juice')
    spec['lineage'].append(dict(doi=OJ,parent='hydrochar180',child='pyrochar800',kind='separate800Cpyrolysis'))
    spec['lineage'].extend(dict(doi=OJ,parent='pyrochar800',child=s,kind='KOH_activation_not_same_material_stage')for s in oj)
    selected=['4:1@120','5:1@120','5:1@210']
    for row,s in enumerate(selected,2):
        fact(OJ,s,t2,row,1,'Raman_ID_IG','ratio','OwnTable2 intensityratio, notarearatio');fact(OJ,s,t2,row,2,'Raman_I2D_IG','ratio','Dash means unresolved/notdiscerniblepeak; bodyzero kept as distinctclaim','conflict_ND_vs_zero_claim'if row==2 else'own_reported_method_and_stage_qualified')
    u=unit(OJ,'Raman_zero_claim',['sample','I2D_G'],[['4:1@120','0']],'MainP34 author interprets non-discernible2D as0; rawTabledash retained');fact(OJ,'4:1@120',u,1,1,'Raman_I2D_IG','ratio','Authorzerointerpretation, not instrument detectionlimit','conflict_ND_vs_zero_claim')
    for row,component in [(2,'CC_sp2'),(3,'C_OH'),(4,'CO'),(5,'OCO')]:
        fact(OJ,'5:1@120',t3,row,1,'XPS_C1s_'+component+'_binding_energy_eV','eV','OwnC1sGaussianfit');fact(OJ,'5:1@120',t3,row,2,'XPS_C1s_'+component+'_envelope_pct','%withinC1s','FractionwithinC1s, notwholematerialatomicpercent')
    for row,component in [(7,'OCO'),(8,'CO'),(9,'C_O')]:
        fact(OJ,'5:1@120',t3,row,1,'XPS_O1s_'+component+'_binding_energy_eV','eV','OwnO1sGaussianfit');fact(OJ,'5:1@120',t3,row,2,'XPS_O1s_'+component+'_envelope_pct','%withinO1s','FractionwithinO1s, notwholematerialatomicpercent')
    u=unit(OJ,'SI_S1',['sample','Dstar','D','Dstarstar','G','2D','R2'],[['4:1@120','1198.91','1333.47','1439.41','1579.53','---','.971'],['5:1@120','1221.78','1336.89','1431.97','1582.21','2678.37','.997'],['5:1@210','1227.72','1335.71','1418.60','1574.74','2674.45','.978']],'SIp6 actualTableS1; one malformed nativecandidate covers bothS1/S2',KEYS[OJ]+'_SI','own_SI_physical_table')
    for row,s in enumerate(selected,1):
        for col,f in enumerate(['Dstar','D','Dstarstar','G','2D'],1):fact(OJ,s,u,row,col,'Raman_'+f+'_position_cm_inv','cm-1','OwnSI Lorentzianpeakpositions; dashnot0')
        resp(OJ,s,u,row,6,'Raman_fit_R2','ratio',not_model_accuracy=True)
    u=unit(OJ,'SI_S2',['sample','RA','RB','RC','RBA','RCB','ESR'],[['4:1@120','3.33','4.96','6.85','1.63','1.89','7.83'],['51@120','2.36','3.38','3.83','1.02','.45','4.41'],['5:1@210','2.17','2.33','2.79','.16','.46','2.98']],'SIp6 TableS2; authorprinted51@120 alias matched main5:1@120 by device set/figurelegend; originalalias retained',KEYS[OJ]+'_SI','own_SI_physical_table')
    for row,s in enumerate(selected,1):
        for col,name in enumerate(['RA','RB','RC','RBA','RCB','ESR'],1):resp(OJ,s,u,row,col,'EIS_'+name,'ohm',system='2E',electrolyte='1MNa2SO4',not_intrinsic_conductivity=True)
    u=unit(OJ,'Pyrochar_mean_size',['sample','mean_SD_um'],[['pyrochar800','6.6 ± 1.5']],'MainP24/SIp2FigS3 SEM meanandSD beforeactivation');fact(OJ,'pyrochar800',u,1,1,'SEM_microsphere_diameter_um','um','AuthorSEMmean±SD, notfinalporediameter')
    u=unit(OJ,'Own_CV',['sample','C_F_g'],list(zip(selected,['22.26','56.05','26.95'])),'MainP55 actualFig6d CV10mVs, notGCD1Ag')
    for row,s in enumerate(selected,1):cap(OJ,s,u,row,1,None,'reported_orange_2e_CV_device_Cg',method='CV',scan=10,system='2E',electrolyte='Na2SO4',concentration_mol_L=1,voltage_lower_V=0,voltage_upper_V=1.4,capacitance_basis='CT_over_total_two_electrode_active_masses_2m',physical_test_group='doi:'+OJ+'#'+s+'_CV10',binder='PVDF',active_mass_per_electrode_approx_mg=2,AC_CB_binder_mass_ratio=[85,10,5])
    issue(OJ,'cv_gcd_and_peak_scope',dict(CV_window=[0,1.4],cycle_GCD_window=[0,1],current_A_g=1,cycles=5000,capvalues_method='CV10mVs',I2DG_dash_vs_claim0=True,Si='authorsubstrate'), 'CVvalues notrelabeledGCD; withinpeakXPSpercentnotatomic. UseactualFig7legend black4:1@120/red5:1@120/blue5:1@210; caption andP64color dissent retained. No inferredcycle retentionratio fromspecificCwithoutboundedreading.')
    # Rice husk: same fresh carbon, unequal electrode masses are test descriptors.
    reg(RH,'RHC','final_biomass_carbon_before_test','rice_husk')
    for s in ['RHC+ ratio2 after10000','RHC+ ratio1 after10000']:reg(RH,s,'after_cycling_positive_electrode','rice_husk');spec['lineage'].append(dict(doi=RH,parent='RHC',child=s,kind='postcycle_not_pretest_feature_inheritance'))
    synth(RH,'RHC','MainP4 stages; no unreportedacid',[dict(stage='precarbonization',temperature_C=500,duration_h=1,heating_rate_C_min=10,atmosphere='N2'),dict(stage='chemical_activation',temperature_C=700,duration_h=1,heating_rate_C_min=None,carbon_to_activator_mass_ratio=[1,4],activator='KOH'),dict(stage='wash',reagent='deionizedwater_to_neutral',acid_not_reported=True)])
    u=unit(RH,'SI_S1',['sample','BET','Vtotal','Vmeso','Vmicro','Dpore'],[['RHC','3185','1.766','.661','1.145','2.21']],'SIp2TableS1; fractionalvolumesnotforcedtosum',KEYS[RH]+'_SI','own_SI_physical_table')
    for col,f,un in [(1,'BET_surface_area_m2_g','m2/g'),(2,'total_pore_volume_cm3_g','cm3/g'),(3,'reported_mesopore_volume_method_unspecified_cm3_g','cm3/g'),(4,'reported_micropore_volume_method_unspecified_cm3_g','cm3/g'),(5,'average_pore_diameter_reported_nm','nm')]:fact(RH,'RHC',u,1,col,f,un,'N2BET77K; totalP/P0.97; subporemethodsnotstated')
    ofields=['adsorbedO','CO','C_O_OH','COOH_COO','totalO']
    u=unit(RH,'SI_S2',['sample',*ofields],[['RHC','1.22 at%','3.07 at%','2.17 at%','2.08 at%','8.54 at%']],'SIp3TableS2 wholematerialatompercentcomponents, sum8.54 not100',KEYS[RH]+'_SI','own_SI_physical_table')
    for col,f in enumerate(ofields,1):fact(RH,'RHC',u,1,col,'XPS_O_at_pct'if f=='totalO'else'XPS_'+f+'_whole_material_at_pct','at%','OwnfreshXPSatomiccomponents, notwithinOenvelopefraction')
    for row,s in [(2,'RHC+ ratio2 after10000'),(3,'RHC+ ratio1 after10000')]:
        for col,f in enumerate(ofields,1):fact(RH,s,'tab4',row,col,'XPS_O_at_pct'if f=='totalO'else'XPS_'+f+'_whole_material_at_pct','at%','After10000GCDpositiveelectrode; nofreshfeatureprojection')
    for tid,ratios,cycles in [('tab1',[1]*4,[1,2000,5000,10000]),('tab2',[1,1.25,1.5,2],[1]*4),('tab3',[2]*2,[1,10000])]:
        for row,(ratio,cyc)in enumerate(zip(ratios,cycles),2):
            for col,name in enumerate(['Ee','Emax_positive','Emin_negative','deltaE_positive','deltaE_negative'],1):resp(RH,'RHC',tid,row,col,'cycling_'+name,'V_vs_HgHgO',positive_negative_mass_ratio=ratio,cycle_count=cyc,system='2E',stage='operating_response_not_intrinsic_predictor')
    windows=[['1','-.560','.085','-.915','-.560'],['1.25','-.534','.066','-.934','-.534'],['1.5','-.500','.047','-.953','-.500'],['2','-.465','.012','-.988','-.465']]
    u=unit(RH,'SI_S3',['mass_ratio','positive_lower','positive_upper','negative_lower','negative_upper'],windows,'SIp6TableS3, actual3Ecomponentwindows fromfullcellinitialcycle, notwholecellwindows',KEYS[RH]+'_SI','own_SI_physical_table')
    for row,rr in enumerate(windows,1):
        for col,f in enumerate(['positive_lower','positive_upper','negative_lower','negative_upper'],1):resp(RH,'RHC',u,row,col,'component_3E_'+f,'V_vs_HgHgO',positive_negative_mass_ratio=float(rr[0]),system='3E',concentration_mol_L=6,electrolyte='KOH')
    u=unit(RH,'Main_P23_Ct',['ratio','Ct'],[['1','155'],['1.25','167'],['2','141']],'MainP23/Fig6b, exactreportedCt vsratio; CV/GCD andspecificcurrentnotexplicitforb, notguessedfromc')
    for row,ratio in enumerate([1,1.25,2],1):cap(RH,'RHC',u,row,1,None,None,method=None,system='2E',electrolyte='KOH',concentration_mol_L=6,voltage_lower_V=0,voltage_upper_V=1,positive_negative_mass_ratio=ratio,capacitance_basis='author_Ct_totalmass_formula; exactmethod_for_this_numeric_report_unselected',physical_test_group='doi:'+RH+'#ratio'+str(ratio),method_selection_issue='OwnFig6cGCDseries remainsforboundedpointmapping; notinferredj')
    u=unit(RH,'Main_cycle',['ratio','retention'],[['1','27.9'],['2','96.4']],'MainP12/16/31 actualFig2a/Fig3, 10k1Ag0..1V')
    for row,ratio in enumerate([1,2],1):
        resp(RH,'RHC',u,row,1,'capacitance_retention','%',cycle_count=10000,current_A_g=1,positive_negative_mass_ratio=ratio,system='2E')
        spec['candidates'].append(dict(candidate_id='LP20:RHC:ratio'+str(ratio),doi=RH,sample='RHC',record=dict(retention_pct=27.9 if ratio==1 else 96.4,cycle_count=10000,reported_current_A_g=1,method='GCD',system='2E_symmetric'if ratio==1 else'2E_homogeneous_mass_imbalanced',electrolyte='KOH',concentration_mol_L=6,cycle_voltage_lower_V=0,cycle_voltage_upper_V=1,positive_negative_mass_ratio=ratio,positive_mass_loading_mg_cm2=4,electrode_area_cm2=1,positive_electrode_mass_mg=4,negative_electrode_mass_mg_derived=4/ratio,derived_mass_basis='authorpositive_loading*area thenexplicitratio, notcurrentdenominator',source_locator='MainP6/P12/P16; actualFig2/3',baseline_reference='author_initial_normalized_reference')))
    issue(RH,'mass_ratio_and_postcycle',dict(mass_ratios=[1,1.25,1.5,2],retention_extremes=[27.9,96.4],pore_sum=1.806,total_pore=1.766,late_Emax_table=.361,late_Emax_conclusion=.354),'Samecarbon4protocols keptsameDOI; ratio isexplicitfeature, unknownotherpapersratio notfilled1. PostcycleXPS/potentials notfreshpredictors. NativeformulaCt totalmass retained; energyconsistency notusedtoinfernormalization/currentbasis. ExactFig6b method/currentpending, sourcepointsnotforcedintoGCD.')
    # Coffee/sludge: eight nominal carbons; binders describe tests, not new materials.
    co=[]
    fields=[('BET_surface_area_m2_g','m2/g'),('tplot_micropore_area_m2_g','m2/g'),('BET_minus_tplot_external_area_m2_g','m2/g'),('total_pore_volume_cm3_g','cm3/g'),('average_pore_diameter_reported_nm','nm')]
    for tid in ['tbl1','tbl2','tbl3']:
        for row,cells in enumerate(tabs[CO,tid][1:],2):
            s=cells[0]
            if s not in co:co.append(s);reg(CO,s,'final_mixed_coffee_sludge_carbon_before_test','spent_coffee_and_waste_activated_sludge_1to1')
            for col,(f,un)in enumerate(fields,1):fact(CO,s,tid,row,col,f,un,'N2BET/tplot; externalarea=BETminusmicro; totalP/P0.99; ±type unspecified for material table')
    assert len(co)==8
    reg(CO,'DS_SC_dried_blend','raw_biomass_mixture','spent_coffee_and_waste_activated_sludge_1to1')
    for s in co:
        wet='L-'in s;temp=int(s.rsplit('-',1)[1]);activator=next((a for a in ['Na2S2O3','K2CO3','Na3C6H5O7']if a in s),None);kcl=3.6 if wet and 'Na2'in s else 1.5 if wet else 3.3 if 'KCl'in s else None
        stages=[dict(stage='raw_drying',temperature_C=100,duration_h=24,sludge_to_coffee_mass_ratio=[1,1],author_typo='DS and SS, context definesSC')]
        if wet:stages.append(dict(stage='wet_mixing',temperature_C=25,duration_h_approx=18,water_volume_mL=20,drying_temperature_C=80,drying_duration_h=24))
        stages.extend([dict(stage='single_carbonization_activation',temperature_C=temp,duration_h=1,heating_rate_C_min=5,atmosphere='N2',activator=activator,carbon_to_activator_mass_ratio=[1,1.5]if activator else None,KCl_to_feedstock_mass_ratio=kcl,mixing='wet'if wet else'dry'),dict(stage='wash_dry',reagent='DIwater',acid_not_reported=True,drying_temperature_C=80,drying_duration_h=24)])
        synth(CO,s,'Methods actualparagraphs7/8, names tied toTables1/2/3',stages);spec['lineage'].append(dict(doi=CO,parent='DS_SC_dried_blend',child=s,kind='single_combined_activation_not_extra_prechar_stage'))
    # Preserve competing table properties with no performance-based selection.
    wet800='SSC-Na2S2O3-KCl-1.5-3.6L-800';wet850=wet800[:-3]+'850';wet900=wet800[:-3]+'900'
    for f,_ in fields[:4]:choose(CO,wet800,f,None,'Same nominal material differs betweenTable1 andTable2; no independent replicate binding, both raw reports retained')
    choose(CO,wet850,fields[4][0],None,'Table2 3.76±.04 versusTable3 3.89±.04, same nominal material; unresolved')
    u=unit(CO,'Printed_Raman',['sample','ID_IG'],[[co[0],'1.210'],[co[1],'1.050'],[co[2],'1.035'],[wet800,'1.036']],'ActualFig2d printedratios; notbodyroundedvalues',KEYS[CO]+'_Fig2')
    for row,rr in enumerate(spec['units'][-1]['rows'],1):fact(CO,rr[0],u,row,1,'Raman_ID_IG','ratio','ActualprintedFig2d intensityratio')
    u=unit(CO,'Printed_Raman_temperature',['sample','ID_IG'],[[wet800,'1.036'],[wet850,'1.031'],[wet900,'1.029']],'ActualFig4d printedtemperaturelabels',KEYS[CO]+'_Fig4')
    for row,rr in enumerate(spec['units'][-1]['rows'],1):fact(CO,rr[0],u,row,1,'Raman_ID_IG','ratio','ActualprintedFig4d intensityratio')
    kcarb='SSC-K2CO3-KCl-1.5-1.5L-850';citrate='SSC-Na3C6H5O7-KCl-1.5-1.5L-850'
    u=unit(CO,'Body_Raman',['sample','ID_IG'],[[wet900,'1.025'],[wet850,'1.036'],[kcarb,'.98'],[citrate,'1.05']],'OwnRamanresults prose900 andactivatorcomparison; competing exactreports retained')
    for row,rr in enumerate(spec['units'][-1]['rows'],1):fact(CO,rr[0],u,row,1,'Raman_ID_IG','ratio','Authorbodyintensityratio')
    for s in [wet850,wet900]:choose(CO,s,'Raman_ID_IG',None,'Actualprintedfigure and prose differ; no authorerratum, allvalues retained')
    for row,s,b in [(2,co[1],'PVDF'),(3,co[2],'PVDF'),(4,co[2],'PTFE')]:
        for col,f in enumerate(['RCT','ESR','Warburg_coefficient'],1):resp(CO,s,'tbl4',row,col,'EIS_'+f,'ohm'if col<3 else'ohm_s^-0.5',binder=b,system='2E',electrolyte='KOH',concentration_mol_L=6,uncertainty_kind='author_SD_electrochemical_pairs',not_intrinsic_material_conductivity=True)
    u=unit(CO,'Own_GCD',['sample','C_F_g'],[[co[1],'67.4 ± 0.4'],[co[2],'89 ± 14'],[co[2],'157 ± 24'],[citrate,'101.8 ± 10.2']],'OwnGCDresults andFig7d/Fig9c; pairedcoin-cellSD. ActualFig7dbluej1~157, earlier~97reading withdrawn')
    for row,(s,b,j,ele,conc,upper)in enumerate([(co[1],'PVDF',1,'KOH',6,1),(co[2],'PVDF',1,'KOH',6,1),(co[2],'PTFE',1,'KOH',6,1),(citrate,None,.2,'CH3COONa',1,1.5)],1):
        cap(CO,s,u,row,1,j,'reported_coffee_sludge_2e_GCD_author_'+ele,system='2E',electrolyte=ele,concentration_mol_L=conc,voltage_lower_V=0,voltage_upper_V=upper,binder=b,uncertainty_kind='author_SD_electrochemical_pairs',capacitance_basis='author_C_or_Cg_symbol_unselected_literal_Eq1_factor4_Eq2_factor2_m_each_electrode',cross_source_comparable=False,physical_test_group='doi:'+CO+'#'+s+'_'+str(b)+'_'+ele,AC_CB_binder_mass_ratio=[80,10,10],loading_basis='coating_mass_includes_CB_binder',native_ash_unquantified=True)
    u=unit(CO,'Own_cycle',['sample','retention'],[[citrate,'98.4 ± 0.3']],'Ownlongcycle20k10Ag/Fig10, sodiumacetate; pairedcellsSD')
    resp(CO,citrate,u,1,1,'capacitance_retention','%',cycle_count=20000,current_A_g=10,electrolyte='CH3COONa',concentration_mol_L=1,system='2E',uncertainty_kind='author_SD_electrochemical_pairs',binder=None)
    spec['candidates'].append(dict(candidate_id='LP20:Coffee:citrate_2E',doi=CO,sample=citrate,record=dict(retention_pct=98.4,retention_SD_pct=.3,cycle_count=20000,reported_current_A_g=10,method='GCD',system='2E',electrolyte='CH3COONa',concentration_mol_L=1,cycle_voltage_lower_V=0,cycle_voltage_upper_V=1.5,binder=None,binder_evidence='cyclebinderunreported, SI6PVDFnotinherited',source_locator='Ownlongcycleprose/Fig10 beforeafterCV0..1.5, Methods sameGCDwindow',native_ash_unquantified=True,baseline_reference='author_initial_normalized_reference')))
    issue(CO,'tables_formula_and_initial_graph_check',dict(wet800_BET=[878,820],wet850_pore=[3.76,3.89],Raman900=[1.029,1.025],equation_C='4I/((dV/dt)m)',equation_Cg='2I_dt/(mDV)',m_definition='each_electrode',earlier_graph_hypothesis_withdrawn='Fig7dPTFE~97 was misread; originalbluepoint~157 agreeswith157±24'), 'Conflictingmaterialfields frozen. Separate source-specific authorcapacitytargets retain unresolvedC/Cgidentity, neverunifiedCs/Cd. ElectrochemicalSDnotassignedtomaterial±. ActualFig7d supports157, nofalseconflict retained as scientificfact. Neitherenergy norformula usedtoguesscurrentdenominator; cyclebinderunknown.')
    # Spirulina: raw/prechar/final composition, actual reciprocal Raman direction.
    sp=['PSB','SNPB-700-4','SNPB-800-1','SNPB-800-2','SNPB-800-4','SNPB-900-4'];best=sp[4]
    reg(SP,'Spirulina','raw_biomass','Spirulina_platensis')
    for row,s in enumerate(sp,3):
        reg(SP,s,'precarbonized_biomass_before_activation'if s=='PSB'else'final_biomass_carbon_before_test','Spirulina_platensis')
        for col,(f,un)in enumerate([('BET_surface_area_m2_g','m2/g'),('reported_micropore_area_method_unspecified_m2_g','m2/g'),('reported_mesopore_area_method_unspecified_m2_g','m2/g'),('total_pore_volume_cm3_g','cm3/g'),('tplot_micropore_volume_cm3_g','cm3/g'),('BJH_mesopore_volume_cm3_g','cm3/g'),('reported_mesopore_fraction_pct','%'),('average_pore_diameter_reported_nm','nm')],1):fact(SP,s,'nanomaterials-13-02431-t001',row,col,f,un,'N2BET77K P/P0.02-.25; totalP/P0.99, tplotVmicro, BJHVmeso; dashednotzero')
        if s!='PSB':
            temp,ratio=map(int,s.rsplit('-',2)[1:]);synth(SP,s,'Methods400Cprechar then separateKOHactivation',[dict(stage='precarbonization',temperature_C=400,duration_h=2,heating_rate_C_min=5,atmosphere='N2'),dict(stage='chemical_activation',temperature_C=temp,duration_h=2,heating_rate_C_min=5,atmosphere='N2',activator='KOH',carbon_to_activator_mass_ratio=[1,ratio]),dict(stage='wash_dry',reagent='HCl',concentration_M=1,drying_temperature_C=105,drying_duration_h=12)]);spec['lineage'].append(dict(doi=SP,parent='PSB',child=s,kind='KOHactivation'))
    spec['lineage'].append(dict(doi=SP,parent='Spirulina',child='PSB',kind='400Cprechar'))
    ea=[['Spirulina','45.43','7.76','10.22','36.59','4.45','5.85','1.24','.97'],['PSB','59.28','3.84','10.35','26.53','5.73','15.44','2.23','1.61'],['SNPB-700-4','72.08','3.21','3.42','21.29','21.08','22.45','3.39','2.92'],['SNPB-800-1','68.73','1.09','1.27','28.91','54.12','63.06','2.38','2.28'],['SNPB-800-2','75.06','2.91','1.92','20.11','39.09','25.79','3.73','3.41'],[best,'80.58','3.09','2.55','13.78','31.6','26.08','5.85','4.93'],['SNPB-900-4','81.11','1.21','2.11','15.57','38.44','67.03','5.21','4.59']]
    u=unit(SP,'SI_S1',['sample','C','H','N','O','CN','CH','CO','C_NO'],ea,'SIp7TableS1 actualbulkEA wt%; VarioELIII andbodywt% explicit',KEYS[SP]+'_SI','own_SI_physical_table')
    for row,rr in enumerate(ea,1):
        for col,el in enumerate(['C','H','N','O'],1):fact(SP,rr[0],u,row,col,'bulk_EA_'+el+'_wt_pct','wt%','BulkEA VarioELIII, notXPSatomic')
        for col,f in enumerate(['CN','CH','CO','C_NO'],5):fact(SP,rr[0],u,row,col,'bulk_EA_author_'+f+'_mass_ratio','ratio','Printedbulkweightfractionsratio, notatomicratio')
    u=unit(SP,'Body_XPS',['sample','C','N','O'],[[best,'80.58','2.55','13.78']],'Ownsurfacecompositionprose andFig4survey; claimsAt.% exactlycoincideEAwt% but no proof authorfalse')
    for col,el in enumerate(['C','N','O'],1):fact(SP,best,u,1,col,'XPS_'+el+'_at_pct','at%','Author-claimedXPSatomicpercent; suspectedEAattributionrisk, separatebulkclaim','author_claimed_XPS_at_pct_with_method_attribution_risk')
    u=unit(SP,'Printed_Raman',['sample','IG_ID'],list(zip(sp,['1.0231','1.1409','1.0945','1.1238','1.1619','1.1348'])),'ActualFig3d printedIG/ID, fourdecimalvalues; bodyPSB1.023/best1.162rounded',KEYS[SP]+'_Fig3')
    for row,s in enumerate(sp,1):fact(SP,s,u,row,1,'Raman_IG_ID','ratio','ActualprintedIG/ID, notID/IG and no unmarkedinverse')
    u=unit(SP,'Own_3E',['sample','C_F_g'],[[best,'348.5']],'Own3EGCDresults 1Ag andTable2 ownrow; abstract348rounded claimseparate')
    cap(SP,best,u,1,1,1,'reported_aqueous_3e_GCD_capacitance',system='3E',electrolyte='KOH',concentration_mol_L=6,reference_electrode='Hg/HgO',voltage_lower_V=-1,voltage_upper_V=0,capacitance_basis='author_single_working_electrode',physical_test_group='doi:'+SP+'#'+best+'_3E',surface_XPS_method_attribution_risk=True)
    cap(SP,best,'nanomaterials-13-02431-t002',2,2,1,None,system='3E',electrolyte='KOH',concentration_mol_L=6,capacitance_basis='repeat_of_Own3E',repeat_of=u)
    u=unit(SP,'SI_S2_own',['sample','BET','C','j','retention','cycles'],[[best,'2923.7','348.5','1','94.14','10000']],'SIp8TableS2 ownrow only; commercial/otherpublicationrows notownfacts',KEYS[SP]+'_SI','own_SI_physical_table_with_foreign_comparison_context')
    cap(SP,best,u,1,2,1,None,system='3E',electrolyte='KOH',concentration_mol_L=6,capacitance_basis='repeat_of_Own3E');resp(SP,best,u,1,4,'capacitance_retention','%',cycle_count=10000,current_A_g=10,existing_endpoint_id='candidate:V05:018')
    spec['identity_links'].append(dict(doi=SP,existing_endpoint_id='candidate:V05:018',sample=best,not_new_cycling_endpoint=True,evidence='SIp8ownrow actualFig6printed94.14,3E10Ag10k; conclusiononly5%loss rounded/dissentkept',core_endpoint_unchanged=True,optional_XPS_risk='Bulkandclaimedatomicvaluescoincide; separatemethods retained, no provennumericcorrection'))
    u=unit(SP,'Own_2E_competing',['sample','C_F_g'],[[best,'307'],[best,'304'],[best,'307.6'],[best,'47']],'Body2E307/.5, conclusion304/.5, actualSIp6FigS5printed307.6/.5; body47/20 beyondSIaxis10')
    for row,j in [(1,.5),(2,.5),(3,.5),(4,20)]:cap(SP,best,u,row,1,j,None,system='2E',electrolyte='KOH',concentration_mol_L=6,voltage_lower_V=0,voltage_upper_V=1.3,capacitance_basis='author_m_both_electrodes_globalformula_vs_unselected2Efactor',target_issue='Competing.5Ag values; body20AgnotshownSIaxis10',physical_test_group='doi:'+SP+'#'+best+'_2E')
    issue(SP,'percent_direction_and_device_conflicts',dict(EAwt=[80.58,3.09,2.55,13.78],claimedXPSat=[80.58,2.55,13.78],XPS_survey='peakswithoutquantitativepercentlabels',IGID=1.1619,bodyrounded=1.162,device_C_at_point5=[307,304,307.6],fresh_CV_window_search_upper=1.8,chosen_device_window=1.3),'BulkEAwt andauthorXPSat retainedseparately. Exactcoincidence raisesmethod-attributionrisk, notproofXPSfalse; qualityfilteredmatrix excludesriskmarkedXPSoptionalfields withreason. ActualIG/IDdirection retained.2Ecompetinglabelsnotselected, noenergyinversion. Old94.14cyclelinked, notduplicated orsubtractedfromoriginal37.')
    # Moringa: residual inorganic phases and an unbound duplicated printed row.
    mol=['MOL600','MOL650','MOL750','MOL850'];unbound='Table1 row6 printed MOL750 unbound'
    reg(MO,'prechar250','precarbonized_biomass_before_activation','Moringa_oleifera_leaves');reg(MO,unbound,'unbound_printed_table_row_not_additional_material','Moringa_oleifera_leaves')
    for s in mol:
        reg(MO,s,'final_biomass_carbon_with_Zn_Ca_residue_before_test','Moringa_oleifera_leaves');reg(MO,s+' predisc','pressed_precursor_before_furnace','Moringa_oleifera_leaves');spec['lineage'].extend([dict(doi=MO,parent='prechar250',child=s+' predisc',kind='ZnCl2impregnation_and_pressing'),dict(doi=MO,parent=s+' predisc',child=s,kind='integratedN2carbonization_CO2activation')])
        temp=int(s[3:]);synth(MO,s,'Methods disc route; N2to600 thenCO2tofinal, holdsunreported',[dict(stage='precarbonization',temperature_C=250,duration_h=2.5),dict(stage='impregnation_pressing',activator='ZnCl2',concentration_M=.5,temperature_C=80,duration_h=2,stirring_rpm=300,press_load_ton=8,disc_diameter_mm=19,disc_precursor_mass_g_approx=.7),dict(stage='integrated_carbonization_physical_activation',carbonization_temperature_C=600,carbonization_atmosphere='N2',carbonization_heating_rate_C_min=3,activation_atmosphere='CO2'if temp>600 else None,activation_temperature_C=temp if temp>600 else None,activation_heating_rate_C_min=10 if temp>600 else None,duration_h=None),dict(stage='wash',reagent='HCl andneutralwater',acid_concentration_raw='1m/L',concentration_M=None)])
    for row,s in enumerate(mol[:3]+[unbound],3):
        for col,f in enumerate(['XRD_d002_A','XRD_d100_A','XRD_Lc_A','XRD_La_A'],1):fact(MO,s,'tbl1',row,col,f,'angstrom','OwnXRDmicrocrystallinesize; lastduplicateMOL750row unbound')
        for col,el in enumerate(['C','O','Ca','Cl','Zn'],5):fact(MO,s,'tbl1',row,col,'EDS_'+el+'_reported_pct','%basis_unknown','OwnEDS notXPS; atom/weightbasis unstated; finalZn/Caphases retained')
    for row,s in enumerate(mol,2):
        for col,(f,un)in enumerate([('BET_surface_area_m2_g','m2/g'),('reported_micropore_area_method_unspecified_m2_g','m2/g'),('reported_mesopore_area_method_unspecified_m2_g','m2/g'),('total_pore_volume_cm3_g','cm3/g'),('average_pore_diameter_reported_nm','nm')],1):fact(MO,s,'tbl2',row,col,f,un,'OwnN2BET finaldisc, notbeforepyrolysis')
    u=unit(MO,'Body_best_pore_and_C',['sample','BET','Vtotal','C_EDS'],[['MOL750','433','.244','88.54'],['MOL850','','','88.91']],'BodybestBET433/V.244 dissent vsTable2; explicitMOL850C88.91 doesnotbindallTable1lastrow')
    fact(MO,'MOL750',u,1,1,'BET_surface_area_m2_g','m2/g','Ownbodyreportcompeting');fact(MO,'MOL750',u,1,2,'total_pore_volume_cm3_g','cm3/g','Ownbodyreportcompeting');fact(MO,'MOL850',u,2,3,'EDS_C_reported_pct','%basis_unknown','ExplicitbodyMOL850Cclaim, noinheritancefromunboundrow')
    choose(MO,'MOL750','BET_surface_area_m2_g',412.196,'Table2 ownsample and conclusion independently agree412.196; body433 dissentretained, notchosenbyperformance')
    choose(MO,'MOL750','total_pore_volume_cm3_g',None,'Table2.2697 versusbody.244, no authorresolution')
    u=unit(MO,'Disc_density',['sample','before','after'],[[s,a,b]for s,a,b in zip(mol,['.999','.968','.973','.966'],['.828','.650','.560','.670'])],'OwnFig1/bodybeforevsafterpyrolysis density explicitlyseparatestages')
    for row,s in enumerate(mol,1):fact(MO,s+' predisc',u,row,1,'geometric_disc_density_g_cm3','g/cm3','Beforefurnace pressedprecursor');fact(MO,s,u,row,2,'geometric_disc_density_g_cm3','g/cm3','Aftercarbonization/activation finaldisc, notskeletaldensity')
    u=unit(MO,'Own_CV_series',['sample','C_F_g'],list(zip(mol,['101','196','283','211'])),'OwnCVresults at1mVs in1MH2SO4/Fig5; notGCD')
    for row,s in enumerate(mol,1):cap(MO,s,u,row,1,None,'reported_moringa_ZnCa_residue_2e_CV_author_Csp',method='CV',scan=1,system='2E',electrolyte='H2SO4',concentration_mol_L=1,voltage_lower_V=0,voltage_upper_V=1,capacitance_basis='author_Csp_CV_integration_formula_not_stated',cross_source_comparable=False,physical_test_group='doi:'+MO+'#'+s+'_H2SO4_CV1',binder='none',retained_Zn_Ca_phases=True)
    u=unit(MO,'Own_GCD_series',['sample','C_F_g'],[['MOL650','156'],['MOL750','307'],['MOL850','221']],'OwnGCDresults1Ag1MH2SO4/Fig6; mdefinedworkingoneelectrode')
    for row,s in enumerate(mol[1:],1):cap(MO,s,u,row,1,1,'reported_moringa_ZnCa_residue_2e_GCD_working_mass_Csp',system='2E',electrolyte='H2SO4',concentration_mol_L=1,voltage_lower_V=0,voltage_upper_V=1,capacitance_basis='I_dt_over_mworking_dV',physical_test_group='doi:'+MO+'#'+s+'_H2SO4_GCD1',binder='none',retained_Zn_Ca_phases=True)
    for row,ele,conc in [(3,'H2SO4',1),(4,'KOH',6),(5,'Na2SO4',1)]:
        for col,method in [(1,'CV'),(2,'GCD')]:
            # Acid repeats earlierseries, not another label. Role comesfromownprose+actualplot.
            purpose=None if ele=='H2SO4'else'reported_moringa_ZnCa_residue_2e_'+('CV_author_Csp'if method=='CV'else'GCD_working_mass_Csp')
            cap(MO,'MOL750','tbl3',row,col,1 if method=='GCD'else None,purpose,method=method,scan=1 if method=='CV'else None,system='2E',electrolyte=ele,concentration_mol_L=conc,voltage_lower_V=0,voltage_upper_V=1,capacitance_basis='I_dt_over_mworking_dV'if method=='GCD'else'author_Csp_CV_integration_formula_not_stated',physical_test_group='doi:'+MO+'#MOL750_'+ele+'_'+method+'1',binder='none',retained_Zn_Ca_phases=True,cross_source_comparable=method=='GCD',literal_XML_header='CV spansbothCcolumns; rolemappedfromownprose/graph')
        for col,f,un in [(3,'energy_density','Wh/kg'),(4,'power_density','W/kg'),(5,'resistance','ohm')]:resp(MO,'MOL750','tbl3',row,col,f,un,electrolyte=ele,concentration_mol_L=conc,system='2E')
    for row,ele,conc in [(12,'Na2SO4',1),(13,'KOH',6),(14,'H2SO4',1)]:cap(MO,'MOL750','tbl4',row,4,1,None,system='2E',electrolyte=ele,concentration_mol_L=conc,capacitance_basis='repeatofOwnGCD_notnewlabel')
    u=unit(MO,'Volume_reports',['electrolyte','Cvol','Evol'],[['H2SO4','101.61','12.07'],['KOH','684.07','10.99'],['Na2SO4','66.53','10.45']],'Ownvolumetricprose,684.07 literalnotguessed84.07; notconvertedusingassumeddensity')
    for row,ele in enumerate(['H2SO4','KOH','Na2SO4'],1):resp(MO,'MOL750',u,row,1,'volumetric_capacitance_author','F/cm3',electrolyte=ele,verification='unresolvedauthorreport');resp(MO,'MOL750',u,row,2,'volumetric_energy_density_author','Wh/L',electrolyte=ele)
    issue(MO,'duplicate_identity_and_residual_scope',dict(Table1_row6_label='MOL750',own850_C=88.91,residual_phases=['ZnO','CaCO3'],EDSbasis=None,BET_750=[412.196,433],pore_750=[.2697,.244]),'Lastrowremainsunbound, notassumed850orfifthcarbon. Bodyexplicit850Cseparate. Zn/Camaterialpurpose separateordinarycarbon, EDSnotXPSatomic; BETworkingtable+conclusionagree, poreunselected. No silentHCl1m/Lto1M.')
    issue(MO,'methods_and_rate_not_lifetime',dict(table3_CV_spans_two_C_columns=True,own_methods=dict(CV283=1,GCD307=1),claim78='Bodylongtermwording butFig7eaxis scanratemVs',volumeC_KOH=684.07),'CV/GCDrolesmappedbyownproseandgraphs withliteralheaderpreserved.78%scanrateretentionnotlifetime, no cyclecandidate. Volume684.07notcorrectedbyguess, noenergyinversevoltageorcapbasis.')
    spec['protocol_reviews'].extend([
        dict(doi=OJ,equations=['CT=whole_CV_loop_integral/(2*r*V0)','Cg=CT/(2*m_one_electrode)','GCDCs=i*dt/dV; i_mass_denominator_unknown'],CV_window=[0,1.4],cycle_GCD_window=[0,1],cycle_count=5000,cycle_current_A_g=1,unextracted_cycle_specific_C_curve=True),
        dict(doi=RH,equations=['CV_Ct=integral/(2*mt*v*dV)','GCD_Ct=I*dt/(mt*dV)'],mt='totalmass_positive_and_negative',current_mass_basis='unknown_not_inferred',mass_ratios=[1,1.25,1.5,2],fresh_BET=3185),
        dict(doi=CO,equations=['C=4*I/((dV/dt)*m)','Cg=2*I*dt/(m*dV)'],m='each_electrode_as_printed',selected_C_or_Cg_symbol=None,paired_SD=True,SI6_binder='PVDF_only_that_panel',cycle_binder=None),
        dict(doi=SP,Raman_direction='IG/ID',EA='bulk_wt_percent',XPS='separate_author_claim_at_percent_with_attribution_risk',cycle_existing_endpoint='candidate:V05:018',device_rate_conflicts=[307,304,307.6]),
        dict(doi=MO,equations=['Csp=I*dt/(m*dV)'],m='working_electrode',literal_table3_header_retained=True,residual_Zn_Ca=True,lifetime_endpoint_reported=False)
    ])
    # Formula image assets, obtained with existing public OA asset bundles, remain evidence.
    for key in ['CO','MO','RH']:
        for p in sorted((OUT/'evidence'/key).glob('*m*.jpg')):
            doi=next(d for d in KEYS if KEYS[d].lower().startswith({'CO':'coffee','MO':'moringa','RH':'rice'}[key]));doc(KEYS[doi]+'_formula_'+p.stem,doi,p,'original_formula_graphic')
    for doi in KEYS:spec['annotations'].append(dict(id='V20_'+KEYS[doi]+'_scope',doi=doi,document=KEYS[doi],scope='Ownmain/SItables, methods, selected exactlabels andactualmainfigurescope reviewed. Remainingcontinuouswaveforms andmarkers notfullnumericextraction.',full_source_review_complete=False))
    write(OUT/'curation_spec.json',spec);print({k:len(v)for k,v in spec.items()})


def build():
    assert sha(PARENT)==PSHA and not DB.exists()and not(OUT/'merge_manifest.json').exists()
    spec=json.loads((OUT/'curation_spec.json').read_text('utf8'));docs={d['key']:d for d in spec['documents']}
    with closing(ro(PARENT))as parent,closing(sqlite3.connect(DB))as c:
        parent.backup(c);c.row_factory=sqlite3.Row;c.execute('pragma foreign_keys=on')
        c.executescript('''create table source_reviews_v20(doi text primary key references reviewed_sources,record_json text);create table cell_extractions_v20(kind text,record_id text,table_key text references reviewed_tables,row_ordinal integer,column_ordinal integer,primary key(kind,record_id));create table decisions_v20(decision_id text primary key,doi text references reviewed_sources,record_json text);create table material_feature_decisions_v20(material_key text references materials,field_name text,record_json text,primary key(material_key,field_name));create table purpose_reviews_v20(observation_id text primary key references capacitance_observations,purpose text,eligible integer,record_json text);create table figure_scope_reviews_v20(doi text references reviewed_sources,figure_number integer,document_key text references source_documents,record_json text,primary key(doi,figure_number));create table annotations_v20(annotation_id text primary key,doi text references reviewed_sources,document_key text references source_documents,record_json text);create table cycle_identity_links_v20(link_id text primary key,record_json text);''')
        for s in spec['sources']:insert(c,'reviewed_sources',dict(doi=s['doi'],path=s['path'],sha256=s['sha256'],title=s['title'],stage='Five own sources; main/SItables, methods, literalformulas and selectedprintedlabels; untranscribed waveforms remain'))
        for d in docs.values():assert sha(ROOT/d['path'])==d['sha256'];insert(c,'source_documents',dict(document_key=d['key'],doi=d['doi'],path=d['path'],sha256=d['sha256'],role=d['role']))
        for t in spec['tables']+spec['units']:
            key=t['doi']+'#'+t['id'];rows=[[v['raw']for v in r]for r in t['grid']]if'grid'in t else t['rows'];insert(c,'reviewed_tables',dict(table_key=key,doi=t['doi'],xml_id=t['id'],caption=t.get('caption',t['id']),header_json=json.dumps(rows[0]if'grid'in t else t['header']),footnote=t.get('footnote','Own bounded transcription; stages/repeats/foreign comparisons kept distinct'),source_raw_table_id=t.get('raw_table_id')));insert(c,'table_source_links',dict(table_key=key,document_key=t['document'],locator=t['locator']));insert(c,'extraction_units_v3',dict(table_key=key,kind=t['kind'],scope='Own explicitly bound cells only; foreign rows retained as context, never admitted'))
            for i,row in enumerate(rows,1):insert(c,'transcribed_rows',dict(table_key=key,row_ordinal=i,cells_json=json.dumps(row,ensure_ascii=False)));insert(c,'transcription_origins_v7',dict(table_key=key,row_ordinal=i,origin_json=json.dumps(t['grid'][i-1]if'grid'in t else dict(document=t['document'],locator=t['locator'],row=i),ensure_ascii=False)))
            if t.get('raw_table_id'):
                assert c.execute('select review_state from raw_table_queue where table_id=?',(t['raw_table_id'],)).fetchone()[0]=='automatic_candidate_unreviewed'
                c.execute('update raw_table_queue set review_state=?where table_id=?',('v20_own_cells_methods_stage_and_conflicts_reviewed',t['raw_table_id']))
        for r in spec['materials']:
            insert(c,'materials',dict(material_key=mk(r['doi'],r['sample']),doi=r['doi'],sample_name=r['sample'],material_stage=r['stage']));insert(c,'material_scopes_v8',dict(material_key=mk(r['doi'],r['sample']),scope_json=json.dumps(dict(origin_class='PEO_assisted_biomass_carbon'if'PEO_assisted'in r['stage']else'biomass_carbon'if'carbon'in r['stage']else'raw_or_intermediate_biomass',feedstock=r['feedstock'],stage=r['stage'],not_assumed_pure_carbon=True,same_source_not_independent=True))))
        def cell(r):
            key=r['doi']+'#'+r['id'];raw=json.loads(c.execute('select cells_json from transcribed_rows where table_key=?and row_ordinal=?',(key,r['row'])).fetchone()[0])[r['col']];return key,raw,number(raw)
        def receipt(kind,rid,r,key):insert(c,'cell_extractions_v20',dict(kind=kind,record_id=str(rid),table_key=key,row_ordinal=r['row'],column_ordinal=r['col']))
        for r in spec['facts']:
            key,raw,value=cell(r);doc=c.execute('select document_key from table_source_links where table_key=?',(key,)).fetchone()[0];q=insert(c,'material_facts',dict(material_key=mk(r['doi'],r['sample']),field_name=r['field'],value=value,raw_value=raw,unit=r['unit'],method=r['method'],table_key=key,row_ordinal=r['row'],column_ordinal=r['col'],source_sha256=docs[doc]['sha256'],review_status=r['status'],training_eligible=0));receipt('fact',q.lastrowid,r,key)
        for r in spec['caps']:
            key,raw,value=cell(r);rid=key+'#'+str(r['row'])+'#'+str(r['col']);cond=dict(extraction_batch='v20',current_mass_basis='author_reported_unknown_not_inferred',repeat_reports_not_independent=True);cond.update(r['conditions'])
            insert(c,'capacitance_observations',dict(observation_id=rid,material_key=mk(r['doi'],r['sample']),table_key=key,row_ordinal=r['row'],column_ordinal=r['col'],value=value,raw_value=raw,unit='F/g',method=r['method'],system=cond['system'],electrolyte=cond['electrolyte'],concentration_mol_L=cond['concentration_mol_L'],current_A_g=r['j'],scan_rate_mV_s=r['scan'],conditions_json=json.dumps(cond,ensure_ascii=False),status='own_reported'if r['purpose']else'own_repeat_or_competing_report',source_group='doi:'+r['doi'],training_eligible=0));receipt('capacitance',rid,r,key)
            if r['purpose']:
                reason='Own bound fresh method-specific report; explicit target/normalization/material scope, optional missing fields masked; source-specific ambiguous C/Cg never mixed into unified targets'
                insert(c,'purpose_reviews_v20',dict(observation_id=rid,purpose=r['purpose'],eligible=1,record_json=json.dumps(dict(reason=reason,purpose_input_ready=True,cyclic_retention_training_admitted=False,training_authorized=False))))
                if r['purpose']=='reported_aqueous_3e_GCD_capacitance':insert(c,'auxiliary_gcd_reviews_v3',dict(observation_id=rid,purpose=r['purpose'],eligible=1,reason=reason,review_basis='Own specific results/actual printed plot and matched own protocol, variants retained; no performance-based selection'))
        for r in spec['responses']:
            key,raw,value=cell(r);rid=key+'#'+str(r['row'])+'#'+str(r['col']);insert(c,'outcome_observations_v3',dict(outcome_id=rid,material_key=mk(r['doi'],r['sample']),table_key=key,record_json=json.dumps(dict(source_group='doi:'+r['doi'],extraction_batch='v20',metric=r['metric'],value=value,raw_value=raw,unit=r['unit'],**(dict(feature_role='test_or_process_response_not_pretest_predictor')|r['conditions'])),ensure_ascii=False),training_eligible=0));receipt('response',rid,r,key)
        for r in spec['synthesis']:insert(c,'synthesis_stages_v3',dict(material_key=mk(r['doi'],r['sample']),document_key=r['document'],locator=r['locator'],stages_json=json.dumps(r['stages'],ensure_ascii=False)))
        for r in spec['feature_decisions']:insert(c,'material_feature_decisions_v20',dict(material_key=mk(r['doi'],r['sample']),field_name=r['field'],record_json=json.dumps(r,ensure_ascii=False)))
        for r in spec['decisions']:insert(c,'decisions_v20',dict(decision_id=r['id'],doi=r['doi'],record_json=json.dumps(r,ensure_ascii=False)));insert(c,'scientific_issues',dict(issue_id=r['id'],doi=r['doi'],sample_name=None,issue_json=json.dumps(dict(kind=r['id'],action=r['decision']),ensure_ascii=False)))
        for r in spec['figures']:insert(c,'figure_scope_reviews_v20',dict(doi=r['doi'],figure_number=r['figure_number'],document_key=r['document'],record_json=json.dumps(r,ensure_ascii=False)))
        for r in spec['annotations']:insert(c,'annotations_v20',dict(annotation_id=r['id'],doi=r['doi'],document_key=r['document'],record_json=json.dumps(r,ensure_ascii=False)))
        for r in spec['identity_links']:insert(c,'cycle_identity_links_v20',dict(link_id='LP19_'+r['existing_endpoint_id'],record_json=json.dumps(r,ensure_ascii=False)))
        sources={r['doi']:r for r in spec['sources']}
        for r in spec['candidates']:insert(c,'test_candidates',dict(candidate_id=r['candidate_id'],material_key=mk(r['doi'],r['sample']),record_json=json.dumps(dict(r['record'],source_group='doi:'+r['doi'],source_year=sources[r['doi']]['year'],evidence_source_path=sources[r['doi']]['path'],source_sha256=sources[r['doi']]['sha256'],current_mass_basis='author_reported_unknown_not_inferred',baseline_cycle=None,baseline_reference='author_reference_not_assumed_cycle1'),ensure_ascii=False),training_eligible=0))
        for s in spec['sources']:
            review=dict(source_year=s['year'],classification=s['classification'],scope='Ownmain/SItables, methods, actualprintedlabels and mainfigure scope',remaining='Continuous spectra/isotherms/CV/GCD/EIS, untranscribed rate markers, unresolved protocols/identities; not full-source extraction.',full_source_review_complete=False)
            insert(c,'source_scope_decisions',dict(doi=s['doi'],scope=review['scope'],reason=review['remaining'],evidence_json=json.dumps(review,ensure_ascii=False),full_source_review_complete=0));insert(c,'source_reviews_v20',dict(doi=s['doi'],record_json=json.dumps(review,ensure_ascii=False)))
        c.executescript('create table raw_candidate_dispositions_v20(table_id text primary key references raw_table_queue,record_json text);create table numeric_details_v20(fact_id integer primary key references material_facts,record_json text);create table material_lineage_v20(lineage_id integer primary key,parent_key text references materials,child_key text references materials,record_json text);')
        for r in spec['raw_dispositions']:
            c.execute('update raw_table_queue set review_state=?where table_id=?',(r['disposition'],r['table_id']));insert(c,'raw_candidate_dispositions_v20',dict(table_id=r['table_id'],record_json=json.dumps(r,ensure_ascii=False)))
        for r in c.execute('select f.fact_id,f.raw_value,f.method from material_facts f join cell_extractions_v20 x on x.record_id=cast(f.fact_id as text)and x.kind="fact"').fetchall():
            nd=numeric_details(r['raw_value'])
            if 'mean±SD'in r['method']:nd['uncertainty_kind']='author_mean_and_SD'
            insert(c,'numeric_details_v20',dict(fact_id=r['fact_id'],record_json=json.dumps(nd,ensure_ascii=False)))
        for r in spec['lineage']:insert(c,'material_lineage_v20',dict(parent_key=mk(r['doi'],r['parent']),child_key=mk(r['doi'],r['child']),record_json=json.dumps(r,ensure_ascii=False)))
        c.execute('create table protocol_reviews_v20(doi text primary key references reviewed_sources,record_json text)')
        for r in spec['protocol_reviews']:insert(c,'protocol_reviews_v20',dict(doi=r['doi'],record_json=json.dumps(r,ensure_ascii=False)))
        c.commit()
    protected={ROOT/d['path']for d in docs.values()}|{PARENT,ROOT/'循环稳定性数据库_v0.26_蛋米循环电流补正_20261027/cycling_v0_26.sqlite',ROOT/'全库复检与特征补提取_20261021/full_corpus_search_native.sqlite'}
    protected.update((OUT/'evidence'/k/'primary_assets.zip')for k in ['CO','MO'])
    write(OUT/'protected_inputs.json',dict(files=[dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p),bytes=p.stat().st_size)for p in sorted(protected)]));print('Built unsealed v20; no cycling admission or model fitting')


if __name__=='__main__':
    if len(sys.argv)!=2 or sys.argv[1]not in ['curate','build']:raise SystemExit('One-use curate/build only before sealing')
    globals()[sys.argv[1]]()
