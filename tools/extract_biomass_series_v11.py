"""Versioned own-source curation; raw reports and purpose decisions remain separate."""
from pathlib import Path
from contextlib import closing
import hashlib,json,re,sqlite3,sys,xml.etree.ElementTree as E
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tools'))
from extract_onion_composite_v8 import sha,ro,write,insert,mk
from extract_palm_kernel_v7 import xml_grid
OUT=ROOT/'文献全量利用复核_20261026/批次11_青豌豆皮水葫芦红茶与Tondolo';DB=OUT/'literature_material_pool_v11.sqlite';EV=OUT/'evidence'
PARENT=ROOT/'文献全量利用复核_20261026/批次10_棉花藜麦黄瓜与同行ANN/literature_material_pool_v10.sqlite';PSHA='843f58a2c737bdb187cf800888732d20f5b3c13a6c94f14ab3cd04d500977b99'
TAC='10.1039/d6ra02137a';PEA='10.1039/d5ra01262g';WH='10.3390/ma17133233';BTC='10.3390/ma14216592';PRIOR='10.1016/j.jece.2025.120693'
BASE=ROOT/'同体系文献补充_第二批_20261017/定向扩搜40至60篇_20261017/sources'
SOURCES=[('Tondolo11',TAC,ROOT/'同体系文献补充_第二批_20261017/sources/L07/fulltext.xml','bc332e1c5775d261b0eb064abf99105d1d5cef6d454c32efc8162c365336f27d'),('Pea11',PEA,BASE/'OA011/main.xml','9800cda82ddea99d1c4d07a6ebd549497d6463c0f199dfcc81d60cacf640505c'),('Hyacinth11',WH,BASE/'OA050/main.xml','83ea243fc959d69b5f9f56a1464367b36e7e2f114ea4bbe39a5b6bf3112124fc'),('Tea11',BTC,ROOT/'三电极端点扩充_20261018/new_sources/PMC8585355/main.xml','fd7e50ea43731a897f819088317cacb144d35807388bd84f346ced8f70687afc')]
NAMES={TAC:['TAC','N-TAC'],PEA:['GP','NGP','NSGP'],WH:['WHAC','WHAC50','WHAC100','WHAC150'],BTC:['BTC-612','BTC-613','BTC-614','BTC-712','BTC-713','BTC-714']}
def text(e):return ''.join(e.itertext())if e is not None else''
def clean(e):return re.sub(r'\s+',' ',re.sub(r'<svg\b.*?</svg>','[vector-symbol]',text(e),flags=re.S)).strip()
def num(v):
    if v in['','-','–','—']:return None
    v=v.replace('\u2009','').replace('−','-').strip()
    if re.fullmatch(r'\d{1,3}(?: \d{3})+(?:\.\d+)?',v):v=v.replace(' ','')
    if '×'in v:
        m=re.fullmatch(r'([\d.]+)\s*×\s*10\s*([+-]?\d+)',v);assert m,v;return float(m[1])*10**int(m[2])
    assert re.fullmatch(r'[+-]?(?:\d+(?:\.\d+)?|\.\d+)',v),v
    return float(v)

def curate():
    assert not DB.exists()and not(OUT/'curation_spec.json').exists()
    spec=dict(sources=[],tables=[],units=[],facts=[],capacitances=[],responses=[],candidates=[],synthesis=[],decisions=[],relations=[dict(doi=TAC,related_doi=PRIOR,kind='explicit_prior_work_material_characterization_reuse',basis='ownp5/6/36/39 andreference1; do not count reused XPS/three-electrode reports as independent',isolation_group='family:Tondolo_TAC_JECE_RSC')])
    source_bydoi={}
    with closing(ro(ROOT/'全库复检与特征补提取_20261021/full_corpus_search_native.sqlite'))as corpus:
        for key,doi,path,digest in SOURCES:
            assert sha(path)==digest;root=E.parse(path).getroot();s=dict(key=key,doi=doi,path=path.relative_to(ROOT).as_posix(),sha256=digest,title=clean(root.find('.//article-title')),article_type=root.get('article-type'));spec['sources'].append(s);source_bydoi[doi]=key
            raw={r[1]:r[0]for r in corpus.execute('select table_id,locator from raw_tables_v11 where source_sha256=?',(digest,))}
            for t in root.findall('.//table-wrap'):
                id=t.get('id');loc='XML table-wrap '+id;mixed=(doi==TAC and id in['tab2','tab4','tab7'])or(doi==PEA and id=='tab4')or(doi==WH and id.endswith('t004'))or(doi==BTC and id.endswith('t003'))
                spec['tables'].append(dict(doi=doi,document=key,id=id,kind='mixed_comparison_foreign_rows_not_own'if mixed else'own_xml_table',locator=loc,caption=clean(t.find('caption')),footnote=clean(t.find('table-wrap-foot')),grid=xml_grid(t),raw_table_id=raw[loc]))
    def u(doi,id,header,rows,locator,document=None,kind='own_numeric_prose'):
        spec['units'].append(dict(doi=doi,document=document or source_bydoi[doi],id=id,header=header,rows=rows,locator=locator,kind=kind));return id
    def f(doi,s,id,row,col,field,unit,method,status='own_reported_method_qualified'):
        spec['facts'].append(dict(doi=doi,sample=s,id=id,row=row,col=col,field=field,unit=unit,method=method,status=status))
    def cap(doi,s,id,row,col,j=None,method='GCD',scan=None,system='3E',select=False,qualifier='own_reported',**extra):
        spec['capacitances'].append(dict(doi=doi,sample=s,id=id,row=row,col=col,current=j,method=method,scan=scan,system=system,select=select,qualifier=qualifier,extra=extra))
    def response(doi,s,id,row,col,metric,unit,**extra):spec['responses'].append(dict(doi=doi,sample=s,id=id,row=row,col=col,metric=metric,unit=unit,extra=extra))
    # Tondolo: transposed pore table; five-component fit is not an intensity ratio.
    for col,s in enumerate(NAMES[TAC],1):
        for row,field,unit in[(2,'micropore_volume_cm3_g','cm3/g'),(3,'total_pore_volume_cm3_g','cm3/g'),(4,'average_pore_size_nm','nm')]:f(TAC,s,'tab1',row,col,field,unit,'OwnTable1; statedBET P/P0=.05..95 is a reported qualification, not an automatic rejection')
    for i,s in[(2,'TAC'),(8,'N-TAC')]:
        for offset,peak in enumerate(['D1','D2','D3','G','D4']):
            for col,measure,unit in[(2,'position','cm^-1'),(3,'reported_width','cm^-1'),(4,'reported_area','author_area_unit_unspecified'),(5,'area_fraction','%of_fitted_envelope')]:f(TAC,s,'tab3',i+offset,col,'Raman_'+peak+'_'+measure,unit,'OwnfivecomponentGaussianfit; area not peak intensity; width not silently redefined')
    id=u(TAC,'Gaussian_fit_quality',['sample','R2','chi2'],[['TAC','.958','446.6'],['N-TAC','.920','287.9']],'ownTable3 rows7/13 authorR2/chi2, not ML prediction accuracy')
    for i,s in enumerate(NAMES[TAC],1):f(TAC,s,id,i,1,'Raman_Gaussian_fit_R2','fit_R2','Spectralfitquality, not modeltestR2');f(TAC,s,id,i,2,'Raman_Gaussian_fit_chi2','author_chi2','Ownspectralfit')
    id=u(TAC,'selected_prose',['sample','BET','ID_IG','recovery'],[['TAC','2331.15','.986','16'],['N-TAC','3504.5','.984','22']],'body32/34/37, own material reports; prior-work reuse explicit')
    for i,s in enumerate(NAMES[TAC],1):
        for col,field,unit in[(1,'BET_surface_area_m2_g','m2/g'),(2,'Raman_ID_IG','ratio'),(3,'reported_carbon_recovery_pct','%basis_not_further_specified')]:f(TAC,s,id,i,col,field,unit,'Ownprose; characterization linked to named prior paper, not independent replication')
    f(TAC,'N-TAC','tab2',12,4,'BET_reported_rounded_m2_g','m2/g','Owncomparisonrounded3505, canonicalprose3504.5 separately retained')
    id=u(TAC,'N_envelope',['sample','N_at','species','share','BE'],[['N-TAC','2.75',sp,a,e]for sp,a,e in[('pyridinic','42.3','398.1'),('pyrrolic','31.5','400'),('graphitic','20.1','401.7'),('oxidized','6','404.5')]],'ownp36/Fig3; explicitly reproduced prior XPS, not new independent batch')
    f(TAC,'N-TAC',id,1,1,'XPS_N_at_pct','at%','Ownexplicitat% previousworkreproduction')
    for i,sp in enumerate(['pyridinic','pyrrolic','graphitic','oxidized'],1):
        f(TAC,'N-TAC',id,i,3,'XPS_N_'+sp+'_envelope_pct','%ofN1s_envelope','Ownrelativecomponent, not total N');f(TAC,'N-TAC',id,i,4,'XPS_N_'+sp+'_binding_energy_eV','eV','Authorreportedassignment')
    id=u(TAC,'device_Fig8c',['sample','j','C'],[['N-TAC',j,v]for j,v in[('.5','118.2'),('1','97.5'),('2','69.7'),('3','52.9'),('4','42.4'),('5','34.5')]],'ActualFig8c printedbarvalues andxcenters; lastbar5Ag, not10',document='Tondolo_Fig8_11',kind='own_printed_figure_annotations')
    for i,(j,v)in enumerate([(.5,118.2),(1,97.5),(2,69.7),(3,52.9),(4,42.4),(5,34.5)],1):cap(TAC,'N-TAC',id,i,2,j,system='2E_symmetric',capacitance_basis='author_factor4_single_equivalent_unequal_mass_device')
    id=u(TAC,'own_device_p45',['sample','C'],[['N-TAC','118.2']],'body45 .5Ag ownsingleelectrodeequivalent');cap(TAC,'N-TAC',id,1,1,.5,system='2E_symmetric',repeat_of='Fig8c .5Ag')
    cap(TAC,'N-TAC','tab4',12,2,.5,system='2E_symmetric',repeat_of='ownbody45/Fig8c')
    for row in range(3,9):
        for col,c0 in[(3,20),(4,40),(5,60)]:response(TAC,'N-TAC','tab5',row,col,'adsorption_model_parameter','as_printed_parameter_specific',initial_MB_ppm=c0,parameter_row=row,not_new_measurement=True)
    for row in range(2,11):response(TAC,'N-TAC','tab6',row,3,'adsorption_isotherm_parameter','as_printed_parameter_specific',parameter_row=row,not_new_measurement=True)
    # GP table/prose swap: select ownTable4 supported by actualFig6c/d + ownconclusion.
    for row,s in enumerate(NAMES[PEA],3):
        for col,e in enumerate(['C','O','N','S'],1):f(PEA,s,'tab1',row,col,'EDX_'+e+'_at_pct','at%','TEMEDXmapping, not XPS')
    for row,s in enumerate(NAMES[PEA],2):
        for col,field,unit in[(1,'BET_surface_area_m2_g','m2/g'),(2,'micropore_volume_cm3_g','cm3/g'),(3,'mesopore_volume_cm3_g','cm3/g'),(4,'macropore_volume_cm3_g','cm3/g'),(5,'total_pore_volume_cm3_g','cm3/g')]:f(PEA,s,'tab2',row,col,field,unit,'OwnTable2: Vmic=DFT-VmesBJH,Vmac=Vt-DFT,Vt atP/P0=.99; rounding qualified')
    for row,s in enumerate(NAMES[PEA],2):
        for col in range(1,5):response(PEA,s,'tab3',row,col,'EIS_fitted_'+['','R1','R2','Q2','Q3'][col],'ohm'if col<=2 else'F s^(a-1)',not_pretest_predictor=True)
    id=u(PEA,'SI_TableS1',['sample','C','O','N','S'],[['GP','82.76','15.75','1.49','-'],['NGP','82.90','14.30','2.80','-'],['NSGP','83.32','14.86','1.68','0.14']],'SI PDFp1 TableS1 EDXmass%',document='Pea_SI11',kind='own_SI_table')
    for row,s in enumerate(NAMES[PEA],1):
        for col,e in enumerate(['C','O','N','S'],1):f(PEA,s,id,row,col,'EDX_'+e+'_wt_pct','wt%','OwnSI EDXmass%; not XPS and not final atom%')
    id=u(PEA,'SI_FigS4',['sample','C','O','N','S'],[['GP','71.17','28.11','.72','0'],['NGP','73.96','23.32','2.72','0'],['NSGP','63.59','33.77','2.4','.24']],'SI PDFp4 FigS4 printedatomiclabels; zero is authorroundedreport, no detectionlimit',document='Pea_SI11',kind='own_printed_figure_annotations')
    for row,s in enumerate(NAMES[PEA],1):
        for col,e in enumerate(['C','O','N','S'],1):f(PEA,s,id,row,col,'XPS_'+e+('_author_rounded_zero_at_pct'if e=='S'and s!='NSGP'else'_at_pct'),'at%','OwnSI atomicbarlabels; printedzero not a proof of elementalabsence')
    id=u(PEA,'Raman_p15',['sample','ID_IG'],[[s,v]for s,v in zip(NAMES[PEA],['.88','.90','.91'])],'ownbody15/Fig4b')
    for i,s in enumerate(NAMES[PEA],1):f(PEA,s,id,i,1,'Raman_ID_IG','ratio','OwnD/G intensity')
    for row,s in enumerate(NAMES[PEA],9):cap(PEA,s,'tab4',row,3,1,select=True,qualifier='selected_own_table_conclusion_and_actual_GCD_figure',competing_p19_label_swap_preserved=True)
    for id,vals,method,scan in [('GCD_p19_swapped',['230.22','208.78','257.01'],'GCD',None),('GCD_p23',['208.78','230.22','257.01'],'GCD',None),('CV_p19',['206.47','229.87','260.86'],'CV',5)]:
        u(PEA,id,['sample','C'],[[s,v]for s,v in zip(NAMES[PEA],vals)],'body19 GP/NGP GCDswapped; body23+Table4+actualFig6 selectGP208.78/NGP230.22'if id.startswith('GCD')else'ownbody19 CV5mVs')
        for i,s in enumerate(NAMES[PEA],1):cap(PEA,s,id,i,1,1 if method=='GCD'else None,method=method,scan=scan,qualifier='conflict_GP_NGP_prose_swap'if id=='GCD_p19_swapped'and s!='NSGP'else'own_repeated_or_other_method')
    id=u(PEA,'device_p21',['sample','j','C'],[['NSGP','1','99.84'],['NSGP','10','60.74']],'ownbody21/actualFig8c; graphlegendNS-APSBcompetes with NSGPcaption/body')
    for i,j in enumerate([1,10],1):cap(PEA,'NSGP',id,i,2,j,system='2E_symmetric',capacitance_basis='author_device_normalization_formula_review_required')
    # WH primary three-electrode values and full own SI peak table.
    for row,s in enumerate(NAMES[WH],2):
        for col,field,unit in[(1,'BET_surface_area_m2_g','m2/g'),(2,'micropore_surface_area_m2_g','m2/g'),(3,'BJH_average_pore_diameter_nm','nm')]:f(WH,s,'materials-17-03233-t001',row,col,field,unit,'OwnfootnoteBET,tplot atP/P0=.95,BJHdesorption; no porevolume inferred')
    for row,s in enumerate(NAMES[WH],3):
        for col,e in enumerate(['C','O','Ca','Si','Al','Mg','N','Cl','P'],1):f(WH,s,'materials-17-03233-t002',row,col,'XPS_'+e+'_at_pct','at%','OwnXPSatomicconcentration; dashnotzero; mineralresidue preserved')
    for row,s in enumerate(NAMES[WH],2):response(WH,s,'materials-17-03233-t003',row,1,'EIS_Rs','ohm',not_pretest_predictor=True)
    id=u(WH,'Raman_p12',['sample','ID_IG','gamma_kGy'],[[s,v,g]for s,v,g in zip(NAMES[WH],['.99','1.03','1.10','1.10'],['0','50','100','150'])],'ownbody8/12 andFig3')
    for i,s in enumerate(NAMES[WH],1):f(WH,s,id,i,1,'Raman_ID_IG','ratio','OwnD/Gintensity');f(WH,s,id,i,2,'pretreatment_gamma_dose_kGy','kGy','Explicitprocessdose, authorzero meansunirradiated')
    id=u(WH,'GCD_p15',['sample','C'],[[s,v]for s,v in zip(NAMES[WH],['95','214','258','208'])],'ownbody15 current1Ag; originalrounding')
    for i,s in enumerate(NAMES[WH],1):cap(WH,s,id,i,1,1,select=s in['WHAC50','WHAC150'])
    id=u(WH,'GCD_p20_precision',['sample','C'],[['WHAC','95.35'],['WHAC100','257.82']],'ownconclusion20 sameGCD1Ag Fig7a/P15; round95/258 retained')
    for i,s in enumerate(['WHAC','WHAC100'],1):cap(WH,s,id,i,1,1,select=True,precision_decision='ownconclusionadditionalprecisionmatchesbodyintegerrounding')
    cap(WH,'WHAC100','materials-17-03233-t004',10,2,1,qualifier='own_comparison_257_rounding_dissent_not_new_test')
    peaks={
      'WHAC':{'C1s':[('Carbide','282.0','4.9'),('Carbide','282.8','6.2'),('C-Si','283.5','5.3'),('C=C_sp2','284.3','7.7'),('C-C_sp3','285.1','44.5'),('C-O','286.0','18.1'),('C=O','287.2','8.7'),('carbonates','288.5','4.6')],'O1s':[('C-O','529.8','9.3'),('C=O_COOH','531.3','21.3'),('C-OH_C-O-C','532.5','36.4'),('COOCO','533.7','26.3'),('Chemisorbed_water_O2','532.2','6.6')]},
      'WHAC50':{'C1s':[('C-Si','283.2','1.1'),('C=C_sp2','284.1','4.6'),('C-C_sp3','285.0','60.9'),('C-O','286.0','10.4'),('C-O','286.9','10.1'),('C=O','288.0','5.5'),('Carbonate','289.2','4.3'),('pi_pi_star','290.5','3.1')],'O1s':[('C=O_COOH','531.0','12.2'),('C-OH_C-O-C','532.5','37.2'),('COOCO','533.2','32.2'),('COOH','534.3','18.4')]},
      'WHAC100':{'C1s':[('Carbide','282.2','4.8'),('C-Si','282.9','7.1'),('C=C_sp2_g3','283.8','4.6'),('C-C_sp3','284.9','56.8'),('C-O','286.0','11.1'),('C=O','286.9','9.1'),('COOH_COOR','288.1','3.5'),('Carbonate','289.3','3.0')],'O1s':[('C-O','529.8','13.5'),('C=O_COOH','531.1','26.8'),('C-OH_C-O-C','532.4','38.9'),('COOCO','533.7','20.8')]},
      'WHAC150':{'C1s':[('Carbide','282.3','4.6'),('C-Si','283.1','3.3'),('C=C_sp2','284.2','5.5'),('C-C_sp3','285.0','60.6'),('C-O','286.1','10.9'),('C=O','287.1','8.0'),('COOH_COOR','288.2','3.4'),('Carbonate','289.3','3.8')],'O1s':[('C-O','529.7','6.2'),('C=O_COOH','531.1','19.7'),('C-OH_C-O-C_g3','532.3','51.1'),('COOCO','533.6','23.0')]}}
    rows=[]
    for s,spectra in peaks.items():
        for spectrum,entries in spectra.items():
            for k,(assignment,be,pct)in enumerate(entries,1):rows.append([s,spectrum,str(k),assignment,be,pct])
    id=u(WH,'SI_TableS1',['sample','spectrum','peak','assignment','BE','component_pct'],rows,'OwnSI TableS1 PDFp1-2; original two C-O components/chemwater529etc labels preserved',document='Hyacinth_SI11',kind='own_SI_table')
    for i,row in enumerate(rows,1):
        for col,suffix,unit in[(4,'binding_energy_eV','eV'),(5,'envelope_pct','%of_'+row[1]+'_envelope')]:f(WH,row[0],id,i,col,'XPS_'+row[1]+'_peak'+row[2]+'_'+suffix,unit,'OwnSI assignment='+row[3]+'; no relabelling/calibration inferred')
    # Tea has six real activation conditions; energy/power and impedance are responses.
    for row,s in enumerate(NAMES[BTC],2):
        for col,field,unit in[(1,'BET_surface_area_m2_g','m2/g'),(2,'total_pore_volume_cm3_g','cm3/g'),(3,'micropore_volume_cm3_g','cm3/g')]:f(BTC,s,'materials-14-06592-t001',row,col,field,unit,'OwnBET/BJH/tplot methods; nativeCaCO3trace not setzero')
        cap(BTC,s,'materials-14-06592-t002',row,2,.5,select=True)
        for col,metric,unit in[(1,'reported_GCD_ESR','ohm_as_printed'),(3,'reported_3E_energy_density','Wh/kg'),(4,'reported_3E_power_density','W/kg')]:response(BTC,s,'materials-14-06592-t002',row,col,metric,unit,device_performance_not_inferred=True)
    id=u(BTC,'CV_p17',['sample','C'],[[s,str(v)]for s,v in zip(NAMES[BTC],[148,200,159,53,110,97])],'ownbody17 CV1mVs, not.5AgGCD')
    for i,s in enumerate(NAMES[BTC],1):cap(BTC,s,id,i,1,method='CV',scan=1)
    cap(BTC,'BTC-613','materials-14-06592-t003',2,1,method='CV',scan=1,repeat_of='ownbody17')
    id=u(BTC,'EIS_p20',['sample','Rct','slope','Warburg'],[[s,str(a),str(b),str(c)]for s,a,b,c in zip(NAMES[BTC][:3],[257,138,133],[5.49,9.39,6.45],[83.5,41.9,51.6])],'ownbody20; authorfrequencyrange1to10MHz competeswithactualFig9.25Hz..100kHz')
    for i,s in enumerate(NAMES[BTC][:3],1):
        for col,metric,unit in[(1,'EIS_Rct','ohm'),(2,'Nyquist_low_frequency_slope','author_slope_unit_unspecified'),(3,'Warburg_impedance','ohm')]:response(BTC,s,id,i,col,metric,unit,not_pretest_predictor=True)
    # Candidate records preserve reused IDs and actual-cycle unknowns.
    for doi,s,id,system,ret,cycles,j,lo,hi,salt,M,legacy,relation in[(TAC,'N-TAC','LP11_Tondolo_2E_C10000','2E_symmetric',94,10000,5,0,1.7,'NaNO3',1,None,'eq'),(PEA,'NSGP','LP11_Pea_2E_C5000','2E_symmetric',99.46,5000,5,0,1,'H2SO4',1,'candidate:V05:014','eq'),(BTC,'BTC-613','LP11_Tea_3E_C2000','3E',98.8,2000,5,-.2,.8,'H2SO4',1,'candidate:TE045','eq')]+[(WH,s,'LP11_'+s+'_3E_C'+str(n),'3E',ret,n,None,-.3,.3,'H2SO4',2,None,'eq')for s,ret,n in[('WHAC',67.03,3000),('WHAC50',85.39,7000),('WHAC100',99.45,7000),('WHAC150',76.87,7000)]]:
        if doi==WH and s!='WHAC100':lo=hi=None
        spec['candidates'].append(dict(doi=doi,sample=s,candidate_id=id,record=dict(source_group='doi:'+doi,source_family_group='family:Tondolo_TAC_JECE_RSC'if doi==TAC else'doi:'+doi,system=system,method='GCD',retention_pct=ret,retention_relation=relation,cycle_count=cycles,reported_current_A_g=j,current_mass_basis=None,cycle_voltage_lower_V=lo,cycle_voltage_upper_V=hi,electrolyte=salt,concentration_mol_L=M,reference_electrode='Ag/AgCl_saturated_NaCl'if doi==BTC else'Ag/AgCl'if system=='3E'else None,baseline_reference='author_own_normalized_initial_reference_index_unspecified',legacy_endpoint_id=legacy,purpose_reviewed_candidate_ready=doi!=WH,locator='OwnFig8d/body45'if doi==TAC else'OwnFig8b/f/body22; alreadyformal'if doi==PEA else'OwnFig9c/body21/commonGCDprotocol'if doi==BTC else'OwnFig8a/b; actualcycleinset-.3..+.3 WHAC100only, currentnotreported',competing_retention_reports_pct=[99.4]if s=='WHAC100'else[],scientific_hold='Actualcyclecurrentnotreported; WHAC10099.45/99.40dissent remains'if doi==WH else None)))
    spec['decisions']=[dict(id='Pea_GCD_identity',doi=PEA,decision='SelectGP208.78/NGP230.22 fromownTable4+conclusion23+actualFig6c/d; p19swappedvalues retained',author_erratum_claimed=False),dict(id='Pea_EDX_XPS',doi=PEA,decision='EDXat/EDXwt/XPSat differentmeasurements; ownS4zeros roundedreports not absoluteabsence'),dict(id='Pea_device_graph_alias',doi=PEA,decision='Fig8c legendNS-APSB vs caption/bodyNSGP; retainlabeldissent, ownFig8a/b/f bindNSGP. Devicecapacitancebasis not silently unified'),dict(id='Tondolo_prior_reuse',doi=TAC,decision='Ownp5/6/36/39 explicitlyreuseJECE2025.120693 characterization; entire sourcefamilyheldout, notnewindependentreplicates'),dict(id='Tondolo_dopant',doi=TAC,decision='Ownmethods6+scheme4 selecturea; comparisonTable2ownrowthioureadissent retained. S notassumedzero'),dict(id='Tondolo_adsorption',doi=TAC,decision='Qe kineticfit rows exceed C0*50mL/10mg available dye; KF/n table257.5/.2047 vsbody273.1/.16 retained. Unresolved dyeprotocol notlabelretention'),dict(id='Hyacinth_cycle_current',doi=WH,decision='No numeric actualcyclecurrent inbody/caption/actualFig8; do not borrowfresh1Ag. Actualcyclewindow-.3..+.3 differsfresh;99.45/99.40 retained'),dict(id='Tea_year_native_mineral',doi=BTC,decision='2021oldendpoint outsidelegacydatecohort; potentialall_years3E only afterseparateadmission. NativeCaCO3trace.32%unboundbasis/sample notsetzero; nointentionalMn/CNTcomposite')]
    for doi,names in NAMES.items():
        for s in names:
            if doi==TAC:
                stages=[dict(stage='raw_feed_drying',temperature_C=60,duration_h=12),dict(stage='single_pyrolysis_carbonization_and_activation',temperature_C=700,duration_h=2,atmosphere='Ar',agent='K2CO3',raw_biomass_to_activator_mass_ratio=[1,1],urea_to_raw_biomass_mass_ratio=1 if s=='N-TAC'else None,particle_size_upper_um=5 if s=='N-TAC'else None,heating_rate_C_min=None,post_wash_HCl_M=3,post_wash_duration_h=5,post_wash_pH='neutral'),dict(stage='electrode_preparation',carbon_wt_pct=80,PVDF_wt_pct=10,acetylene_black_wt_pct=10,collector='Ni_foam',area_cm2=1,mass_loading_mg_cm2_range=[2.5,3],drying_C=60,drying_h=12)]
                if s=='N-TAC':stages.append(dict(stage='same_material_2e_device',negative_to_positive_electrode_mass_ratio=1.2,total_electrode_mass_loading_mg_cm2=5,author_calls_symmetric_but_mass_balanced_unequal=True))
            elif doi==PEA:
                stages=[dict(stage='raw_feed_drying',temperature_C=80,duration_h=12,sieve_um=106),dict(stage='carbonization',temperature_C=600,duration_h=2,heating_rate_C_min=10,cooling_rate_C_min=10,atmosphere='N2'),dict(stage='chemical_activation',temperature_C=900,duration_h=2,heating_rate_C_min=10,cooling_rate_C_min=10,atmosphere=None,agent='KOH',carbon_to_activator_mass_ratio=[1,3],post_wash_HCl_M=1,post_wash_pH=7,post_drying_C=80,post_drying_h=12)]
                if s!='GP':stages.append(dict(stage='post_activation_heteroatom_doping',temperature_C=400,duration_h=1,heating_rate_C_min=10,atmosphere=None,GP_g=1,melamine_mg=123,thiourea_mg=231 if s=='NSGP'else None,DIwater_mL=5,post_drying_C=80,post_drying_h=12,nominal_element_ratio_not_final_composition=True))
                stages.append(dict(stage='electrode_preparation',carbon_wt_pct=80,carbonblack_wt_pct=10,PVDF_wt_pct=10,collector='graphite_foil',area_cm2=1,mass_loading_mg_cm2=3,drying_C=120,drying_h=11,vacuum=True))
            elif doi==WH:
                dose={'WHAC':0,'WHAC50':50,'WHAC100':100,'WHAC150':150}[s];stages=[dict(stage='gamma_raw_biomass_pretreatment',sieve_mesh=200,raw_g=4,DIwater_mL=200,sonication_min=60,gamma_source='Co60',dose_kGy=dose,dose_rate_kGy_h=1.9),dict(stage='carbonization',temperature_C=800,duration_h=5,atmosphere='N2',heating_rate_C_min=None),dict(stage='chemical_activation',temperature_C=800,duration_h=5,atmosphere='N2',agent='KOH',carbon_to_activator_mass_ratio=[1,2],pre_drying_C=80,pre_drying_h=72,post_wash_H2SO4_M=.1,post_drying_C=60,post_drying_h=24),dict(stage='electrode_preparation',carbon_wt_pct=80,carbonblack_wt_pct=10,PVDF_wt_pct=10,reported_PVDF_stock_wt_pct=5,collector='graphite_foil',area_cm2=4,mass_mg_per_electrode_range=[3,5],drying_C=100,drying_h=None,sonication_min=30)]
            else:
                temp=600 if s[4]=='6'else 700;ratio=int(s[-1]);stages=[dict(stage='feedstock_brewing',temperature_C=92,duration_min=4,raw_water_content_pct=82.1,raw_water_content_author_plusminus=.6,no_pre_drying=True),dict(stage='hydrothermal_carbonization',temperature_C=200,duration_h=12,wet_feed_g=45,post_drying_C=105,post_drying_h=24),dict(stage='chemical_activation',temperature_C=temp,duration_h=1,atmosphere='air',agent='KOH',char_g=.8,carbon_to_activator_mass_ratio=[1,ratio],post_hot_water_wash_pH=7,post_drying_C=105,post_drying_h=24),dict(stage='electrode_preparation',carbon_wt_pct=80,SuperP_wt_pct=10,PTFE_wt_pct=10,collector='stainless_SUS_mesh',area_cm2=1,solvent='isopropanol',hydraulic_press_load=None)]
            spec['synthesis'].append(dict(doi=doi,sample=s,document=source_bydoi[doi],locator='Ownexperimentalparagraphs with sample-specific post-treatment; unknown atmospheres/durations remain null',stages=stages))
    write(OUT/'curation_spec.json',spec)
    print(json.dumps({k:len(v)for k,v in spec.items()},ensure_ascii=False))

def documents(spec):
    docs={s['key']:dict(doi=s['doi'],path=ROOT/s['path'])for s in spec['sources']}
    docs.update(Pea_SI11=dict(doi=PEA,path=BASE/'OA011/RA-015-D5RA01262G-s001.pdf'),Hyacinth_SI11=dict(doi=WH,path=BASE/'OA050/materials-3005630-supplementary.pdf'),Tondolo_SI11=dict(doi=TAC,path=EV/'RA-016-D6RA02137A-s001.pdf'),Tondolo_Fig8_11=dict(doi=TAC,path=EV/'d6ra02137a-f8.jpg'),Pea_Fig6_11=dict(doi=PEA,path=BASE/'OA011/figures/d5ra01262g-f6.jpg'),Pea_Fig8_11=dict(doi=PEA,path=BASE/'OA011/figures/d5ra01262g-f8.jpg'),Hyacinth_Fig8_11=dict(doi=WH,path=BASE/'OA050/figures/materials-17-03233-g008.jpg'),Tea_Fig9_11=dict(doi=BTC,path=ROOT/'三电极端点扩充_20261018/new_sources/PMC8585355/assets/materials-14-06592-g009.jpg'))
    return docs

def build(resume=False):
    assert not(OUT/'merge_manifest.json').exists();assert sha(PARENT)==PSHA
    if resume:
        with closing(ro(DB))as check:
            check.execute('attach database ? as pinned',(PARENT.as_uri()+'?mode=ro',))
            for(t,)in check.execute("select name from pinned.sqlite_master where type='table'and name not like 'sqlite_%'"):
                assert check.execute('select count(*)from main.'+t).fetchone()==check.execute('select count(*)from pinned.'+t).fetchone()
                assert not check.execute('select *from main.'+t+' except select *from pinned.'+t).fetchall()
                assert not check.execute('select *from pinned.'+t+' except select *from main.'+t).fetchall()
            for t in['source_reviews_v11','source_relations_v11','cell_extractions_v11','decisions_v11']:assert check.execute('select count(*)from '+t).fetchone()[0]==0
        write(OUT/'draft_build_recovery.json',dict(repairs=['Explicit normalized thousands grouping 86 183.7 parser','Apply record-specific capacitance basis after default condition dictionary'],parent_sha256=PSHA,all_parent_rows_identical=True,new_tables_empty_before_resume=True,source_files_changed=False))
    else:assert not DB.exists()
    spec=json.loads((OUT/'curation_spec.json').read_text('utf8'));docs=documents(spec);sources={s['doi']:s for s in spec['sources']}
    with closing(ro(PARENT))as parent,closing(sqlite3.connect(DB))as c:
        if not resume:parent.backup(c)
        c.row_factory=sqlite3.Row;c.execute('pragma foreign_keys=on');c.executescript('''create table if not exists source_reviews_v11(doi text primary key references reviewed_sources,record_json text);create table if not exists source_relations_v11(doi text,related_doi text,record_json text,primary key(doi,related_doi));create table if not exists cell_extractions_v11(kind text,record_id text,table_key text references reviewed_tables,row_ordinal integer,column_ordinal integer,primary key(kind,record_id));create table if not exists decisions_v11(decision_id text primary key,doi text references reviewed_sources,record_json text);''')
        for s in spec['sources']:insert(c,'reviewed_sources',dict(doi=s['doi'],path=s['path'],sha256=s['sha256'],title=s['title'],stage='Ownspecifiedmain/SI/prose/printedfigurelabels; fullwaveformsnotcomplete'))
        for key,d in docs.items():insert(c,'source_documents',dict(document_key=key,doi=d['doi'],path=d['path'].relative_to(ROOT).as_posix(),sha256=sha(d['path']),role='primary_xml'if key in[s['key']for s in spec['sources']]else'own_SI_or_own_original_figure'))
        for t in spec['tables']+spec['units']:
            key=t['doi']+'#'+t['id'];rows=[[x['raw']for x in row]for row in t['grid']]if'grid'in t else t['rows']
            insert(c,'reviewed_tables',dict(table_key=key,doi=t['doi'],xml_id=t['id'],caption=t.get('caption',t['id']),header_json=json.dumps(rows[0]if'grid'in t else t['header'],ensure_ascii=False),footnote=t.get('footnote','Ownspecifiedscope, related reports not independent experiments'),source_raw_table_id=t.get('raw_table_id')));insert(c,'table_source_links',dict(table_key=key,document_key=t['document'],locator=t['locator']));insert(c,'extraction_units_v3',dict(table_key=key,kind=t['kind'],scope='Ownspecifiedcells; foreigncomparisons retainedtranscriptionnotownlabels'))
            for i,row in enumerate(rows,1):insert(c,'transcribed_rows',dict(table_key=key,row_ordinal=i,cells_json=json.dumps(row,ensure_ascii=False)));insert(c,'transcription_origins_v7',dict(table_key=key,row_ordinal=i,origin_json=json.dumps(t['grid'][i-1]if'grid'in t else dict(document=t['document'],locator=t['locator'],row=i),ensure_ascii=False)))
            if t.get('raw_table_id'):c.execute('update raw_table_queue set review_state=?where table_id=?',('v11_declared_own_scope_foreign_rows_separate',t['raw_table_id']))
        for doi,names in NAMES.items():
            for s in names:insert(c,'materials',dict(material_key=mk(doi,s),doi=doi,sample_name=s,material_stage='final_biomass_carbon_before_test'));insert(c,'material_scopes_v8',dict(material_key=mk(doi,s),scope_json=json.dumps(dict(origin_class='biomass_carbon',feedstock={TAC:'Tondolo_fruit_peels_author_taxonomic_wording_competing',PEA:'green_pea_peels',WH:'water_hyacinth_leaves',BTC:'brewed_black_tea_waste'}[doi],native_residue_reported=doi in[WH,BTC],not_assumed_pure_carbon=True,same_source_not_independent=True),ensure_ascii=False)))
        def cell(r):
            key=r['doi']+'#'+r['id'];raw=json.loads(c.execute('select cells_json from transcribed_rows where table_key=?and row_ordinal=?',(key,r['row'])).fetchone()[0])[r['col']];return key,raw,num(raw)
        def receipt(kind,rid,r,key):insert(c,'cell_extractions_v11',dict(kind=kind,record_id=str(rid),table_key=key,row_ordinal=r['row'],column_ordinal=r['col']))
        for r in spec['facts']:
            key,raw,val=cell(r);doc=c.execute('select document_key from table_source_links where table_key=?',(key,)).fetchone()[0];cur=insert(c,'material_facts',dict(material_key=mk(r['doi'],r['sample']),field_name=r['field'],value=val,raw_value=raw,unit=r['unit'],method=r['method'],table_key=key,row_ordinal=r['row'],column_ordinal=r['col'],source_sha256=sha(docs[doc]['path']),review_status='author_dash_not_quantified_not_zero'if val is None else r['status'],training_eligible=0));receipt('fact',cur.lastrowid,r,key)
        for r in spec['capacitances']:
            key,raw,val=cell(r);doi=r['doi'];lo,hi=(-.2,.8)if doi==BTC else(-.3,.7)if doi==WH else(0,1.7)if doi==TAC else(0,1)
            cond=dict(extraction_batch='v11',current_mass_basis='author_reported_unknown_not_inferred',voltage_lower_V=lo,voltage_upper_V=hi,reference_electrode='Ag/AgCl_saturated_NaCl'if doi==BTC else'Ag/AgCl_3M_KCl'if doi==PEA and r['system']=='3E'else'Ag/AgCl'if r['system']=='3E'else None,capacitance_basis='single_working_carbon_electrode'if r['system']=='3E'else'author_reported_device_not_physically_unified',repeat_reports_not_independent_tests=True);cond.update(r['extra']);rid=key+'#'+str(r['row'])+'#'+str(r['col'])
            insert(c,'capacitance_observations',dict(observation_id=rid,material_key=mk(doi,r['sample']),table_key=key,row_ordinal=r['row'],column_ordinal=r['col'],value=val,raw_value=raw,unit='F/g',method=r['method'],system=r['system'],electrolyte='NaNO3'if doi==TAC else'H2SO4',concentration_mol_L=2 if doi==WH else 1,current_A_g=r['current'],scan_rate_mV_s=r['scan'],conditions_json=json.dumps(cond,ensure_ascii=False),status=r['qualifier'],source_group='doi:'+doi,training_eligible=0));receipt('capacitance',rid,r,key)
            if r['select']:insert(c,'auxiliary_gcd_reviews_v3',dict(observation_id=rid,purpose='reported_aqueous_3e_GCD_capacitance',eligible=1,reason='Ownspecificmaterial/GCD/current/3Eelectrolyte/reference/voltage andpretestfeaturesbound; repeatsanddissentseparate',review_basis='Originalownprotocol/table/figurewithsample-specificdecision'))
        for r in spec['responses']:
            key,raw,val=cell(r);rid=key+'#'+str(r['row'])+'#'+str(r['col']);insert(c,'outcome_observations_v3',dict(outcome_id=rid,material_key=mk(r['doi'],r['sample']),table_key=key,record_json=json.dumps(dict(source_group='doi:'+r['doi'],extraction_batch='v11',metric=r['metric'],value=val,raw_value=raw,unit=r['unit'],feature_role='test_or_fitted_response_not_pretest_predictor',**r['extra']),ensure_ascii=False),training_eligible=0));receipt('response',rid,r,key)
        for r in spec['candidates']:
            s=sources[r['doi']];record=dict(r['record'],evidence_source_path=s['path'],source_sha256=s['sha256']);insert(c,'test_candidates',dict(candidate_id=r['candidate_id'],material_key=mk(r['doi'],r['sample']),record_json=json.dumps(record,ensure_ascii=False),training_eligible=0))
        for r in spec['synthesis']:insert(c,'synthesis_stages_v3',dict(material_key=mk(r['doi'],r['sample']),document_key=r['document'],locator=r['locator'],stages_json=json.dumps(r['stages'],ensure_ascii=False)))
        for r in spec['decisions']:insert(c,'decisions_v11',dict(decision_id=r['id'],doi=r['doi'],record_json=json.dumps(r,ensure_ascii=False)));insert(c,'scientific_issues',dict(issue_id='LP11_'+r['id'],doi=r['doi'],sample_name=None,issue_json=json.dumps(dict(kind=r['id'],action=r['decision']),ensure_ascii=False)))
        for r in spec['relations']:insert(c,'source_relations_v11',dict(doi=r['doi'],related_doi=r['related_doi'],record_json=json.dumps(r,ensure_ascii=False)))
        for s in spec['sources']:
            decision=dict(classification='original_biomass_research',scope='Ownspecifiedmain/SI/printedfigure/prosenumbers; foreigncomparisons not ownlabels',remaining='FullCV/GCD/adsorption/EISwaveforms andremainingmorphology/figurequantities notyetfullyextracted',full_source_review_complete=False)
            insert(c,'source_scope_decisions',dict(doi=s['doi'],scope=decision['scope'],reason=decision['remaining'],evidence_json=json.dumps(decision,ensure_ascii=False),full_source_review_complete=0));insert(c,'source_reviews_v11',dict(doi=s['doi'],record_json=json.dumps(decision,ensure_ascii=False)))
        c.commit()
    write(OUT/'protected_inputs.json',dict(files=[dict(path=d['path'].relative_to(ROOT).as_posix(),sha256=sha(d['path']))for d in docs.values()]+[dict(path=PARENT.relative_to(ROOT).as_posix(),sha256=PSHA),dict(path='全库复检与特征补提取_20261021/full_corpus_search_native.sqlite',sha256='f2720c3e417904dad5857a6574cc72d5cf996f9b8716620d69594f11380c658c')]))
    print('Built draft v11; not sealed/admitted/trained')

def resume_empty_build():build(True)

def verify(prepare=False):
    from data.literature_v11 import open_literature_database
    from data.literature_v10 import open_literature_database as old_api
    checks=[]
    def ck(name,ok):
        if not ok:raise AssertionError(name)
        checks.append(name)
    spec=json.loads((OUT/'curation_spec.json').read_text('utf8'));before_sha=sha(DB)
    for p in json.loads((OUT/'protected_inputs.json').read_text('utf8'))['files']:ck('protected_'+p['path'],sha(ROOT/p['path'])==p['sha256'])
    for p in json.loads((PARENT.parent/'merge_manifest.json').read_text('utf8'))['outputs']:ck('parent_payload_'+p['path'],sha(ROOT/p['path'])==p['sha256'])
    import zipfile,io
    from pypdf import PdfReader
    receipt=json.loads((EV/'Tondolo_acquisition.json').read_text('utf8'));ck('public_OA_package_hash',sha(ROOT/receipt['path'])==receipt['sha256'])
    with zipfile.ZipFile(ROOT/receipt['path'])as z:
        for name in receipt['selected_members']:ck('original_public_member_'+name,(EV/name).read_bytes()==z.read(name))
    with zipfile.ZipFile(BASE/'OA050/supplementary_package.zip')as z,zipfile.ZipFile(io.BytesIO(z.read('materials-17-03233-s001.zip')))as nested:
        name=next(n for n in nested.namelist()if n.endswith('materials-3005630-supplementary.pdf'));ck('WH_existing_SI_exact_public_member',(BASE/'OA050/materials-3005630-supplementary.pdf').read_bytes()==nested.read(name))
    ck('three_SIs_page_identity',[len(PdfReader(p).pages)for p in[BASE/'OA011/RA-015-D5RA01262G-s001.pdf',BASE/'OA050/materials-3005630-supplementary.pdf',EV/'RA-016-D6RA02137A-s001.pdf']]==[5,3,7])
    si_text=' '.join(PdfReader(BASE/'OA011/RA-015-D5RA01262G-s001.pdf').pages[0].extract_text().split())
    for line in['GP 82.76 15.75 1.49 -','NGP 82.90 14.30 2.80 -','NSGP 83.32 14.86 1.68 0.14']:ck('GP_SI_original_row_'+line.split()[0],line in si_text)
    audits=[]
    with closing(ro(DB))as c,closing(ro(PARENT))as old:
        c.row_factory=sqlite3.Row
        ck('SQLite_integrity',c.execute('pragma integrity_check').fetchone()[0]=='ok');ck('foreign_keys',not c.execute('pragma foreign_key_check').fetchall())
        for(t,)in old.execute("select name from sqlite_master where type='table'and name not like 'sqlite_%'"):
            if t=='raw_table_queue':continue
            now={tuple(r)for r in c.execute('select *from '+t)};ck('parent_rows_'+t,all(tuple(r)in now for r in old.execute('select *from '+t)))
        oq={r[0]:tuple(r)for r in old.execute('select *from raw_table_queue')};nq=[tuple(r)for r in c.execute('select *from raw_table_queue')];ids={r['raw_table_id']for r in spec['tables']}
        ck('exact18queuechanges',len(ids)==18 and{r[0]for r in nq if r!=oq[r[0]]}==ids)
        for r in nq:ck('queue_original_'+r[0],r[:6]==oq[r[0]][:6]and r[7:]==oq[r[0]][7:])
        for t in spec['tables']+spec['units']:
            key=t['doi']+'#'+t['id'];rows=[json.loads(r[0])for r in c.execute('select cells_json from transcribed_rows where table_key=?order by row_ordinal',(key,))]
            if'grid'in t:
                source=next(s for s in spec['sources']if s['key']==t['document']);original=xml_grid(E.parse(ROOT/source['path']).find(".//table-wrap[@id='"+t['id']+"']"));ck('native_grid_'+key,original==t['grid']);wanted=[[x['raw']for x in row]for row in original]
            else:wanted=t['rows']
            ck('transcribed_'+key,rows==wanted)
        for r in c.execute('select *from cell_extractions_v11'):
            raw=json.loads(c.execute('select cells_json from transcribed_rows where table_key=?and row_ordinal=?',(r['table_key'],r['row_ordinal'])).fetchone()[0])[r['column_ordinal']]
            table,key={'fact':('material_facts','fact_id'),'capacitance':('capacitance_observations','observation_id'),'response':('outcome_observations_v3','outcome_id')}[r['kind']];row=c.execute('select *from '+table+' where '+key+'=?',(r['record_id'],)).fetchone();value=json.loads(row['record_json'])if r['kind']=='response'else row
            ck('raw_'+r['kind']+r['record_id'],value['raw_value']==raw);ck('numeric_'+r['kind']+r['record_id'],value['value']==num(raw))
        for t in['material_facts','capacitance_observations','outcome_observations_v3','test_candidates','raw_table_queue']:ck('no_raw_auto_admission_'+t,c.execute('select count(*)from '+t+' where training_eligible!=0 or training_eligible is null').fetchone()[0]==0)
        count=lambda t:c.execute('select count(*)from '+t).fetchone()[0];prior=json.loads((PARENT.parent/'summary.json').read_text('utf8'));summary=dict(prior)
        summary.update(cumulative_reviewed_source_publications=count('reviewed_sources'),cumulative_materials=count('materials'),cumulative_selected_material_cells=count('material_facts'),cumulative_numeric_material_facts=c.execute('select count(*)from material_facts where value is not null').fetchone()[0],unreported_material_cells=c.execute('select count(*)from material_facts where value is null').fetchone()[0],capacitance_records=count('capacitance_observations'),numeric_capacitance_values=c.execute('select count(*)from capacitance_observations where value is not null').fetchone()[0],response_outcomes=count('outcome_observations_v3'),cycling_candidates=count('test_candidates'),synthesis_materials=count('synthesis_stages_v3'),scientific_issues=count('scientific_issues'),raw_candidates_touched=124,raw_candidates_untouched=835,reviewed_table_units=prior['reviewed_table_units']+20,reviewed_evidence_units=prior['reviewed_evidence_units']+36,new_materials=15,new_numeric_material_facts=281,new_capacitance_reports=42,new_response_records=70,new_source_response_records=70,new_own_main_tables=12,new_mixed_comparison_main_tables=6,new_own_SI_tables=2,new_peer_model_main_tables=0,new_peer_model_SI_tables=0,new_bounded_curve_samples=0,new_curve_groups=0,auxiliary_aqueous_3e_GCD_rows=146,auxiliary_purpose_reviewed_input_rows=162,auxiliary_independent_DOI_groups=14,formal_cycling_admissions=0,model_fits=0,all_literature_fully_utilized=False,scope_note='Fourownsource scopes and15materials,specifiedownmain/SI cells/printedlabels; priorworkTondolo sourcefamilyexplicit. Remainingprose/curvewaveforms/morphology are notcomplete, nofit. Separate cycling admission review still required.')
        ck('four_sources_partial',count('reviewed_sources')==31 and c.execute('select sum(full_source_review_complete)from source_scope_decisions').fetchone()[0]==0)
        ck('counts_materials_facts_reports_responses',(summary['cumulative_materials'],summary['cumulative_selected_material_cells'],summary['cumulative_numeric_material_facts'],summary['capacitance_records'],summary['response_outcomes'])==(175,2004,1926,653,2313))
        ck('835untouched',c.execute("select count(*)from raw_table_queue where review_state='automatic_candidate_unreviewed'").fetchone()[0]==835)
        ck('zero_model_cells_added',count('peer_model_cells_v10')==240)
        for model,row in[('pseudo_first_order',3),('pseudo_second_order',6)]:
            values=json.loads(c.execute('select cells_json from transcribed_rows where table_key=?and row_ordinal=?',(TAC+'#tab5',row)).fetchone()[0])
            for col,c0 in[(3,20),(4,40),(5,60)]:
                maximum=c0*.05/.01;reported=num(values[col]);ck('stated_adsorption_mass_balance_'+model+str(c0),reported>maximum)
                audits.append(dict(doi=TAC,sample='N-TAC',kind='fitted_Qe_vs_stated_available_dye',model=model,initial_ppm=c0,volume_L=.05,adsorbent_g=.01,reported_fitted_Qe_mg_g=reported,maximum_from_stated_protocol_mg_g=maximum,status='unresolved_protocol_or_fit_inconsistency',not_new_measurement=True))
        for s,start in[('TAC',2),('N-TAC',8)]:
            rows=[json.loads(c.execute('select cells_json from transcribed_rows where table_key=?and row_ordinal=?',(TAC+'#tab3',i)).fetchone()[0])for i in range(start,start+5)];total=sum(num(r[5])for r in rows);audits.append(dict(doi=TAC,sample=s,kind='Raman_component_percentage_sum',computed_sum=total,status='reported_rounding_preserved',not_new_measurement=True))
    with open_literature_database(DB,before_sha)as new,old_api(PARENT,PSHA)as old:
        for p in['3e','2e_device','native_mineral_3e','2e_author_factor2']:
            before=old.auxiliary_feature_rows(p);after=new.auxiliary_feature_rows(p);ids={r['observation_id']for r in before};ck('old_auxiliary_exact_'+p,[r for r in after if r['observation_id']in ids]==before)
        aux=new.auxiliary_feature_rows('3e');ck('146_ordinary3E',len(aux)==146)
        pea={r['sample_name']:r['capacitance_F_g']for r in aux if r['doi']==PEA};ck('Pea_specific_source_resolution',pea==dict(GP=208.78,NGP=230.22,NSGP=257.01))
        ck('WH_Raman_SI_methodseparate',len(new.facts(doi=WH,sample='WHAC100',field='XPS_C1s_peak1_binding_energy_eV'))==1)
        ck('Tondolo_source_family',new.isolation_group(TAC)==new.isolation_group(PRIOR)=='family:Tondolo_TAC_JECE_RSC'and set(new.quarantine_source_groups(['doi:'+TAC]))=={'doi:'+TAC,'doi:'+PRIOR})
        wh=[r['record']for r in new.tests()if r['candidate_id'].startswith('LP11_WHAC')];ck('WH_actual_current_not_borrowed',len(wh)==4 and all(r['reported_current_A_g']is None and not r['purpose_reviewed_candidate_ready']for r in wh))
        ck('WH_actual_window_only_own_sample',all(r['cycle_voltage_lower_V']is None for r in wh if r['cycle_count']==3000)and len([r for r in wh if r['cycle_voltage_lower_V']==-.3])==1)
        for target in['retention','capacitance']:ck('DES_preserved_'+target,new.des_reported_inputs(target)==old.des_reported_inputs(target))
        ck('old128bounded_points',new.sampled_curves()==old.sampled_curves());ck('old15freezes',new.legacy_feature_conflicts()==old.legacy_feature_conflicts());ck('composite_preserved',new.composite_cycle_inputs()==old.composite_cycle_inputs())
    ck('readonly_hash',sha(DB)==before_sha);report=dict(status='passed',database_sha256=before_sha,check_count=len(checks),checks=sorted(checks),model_fits=0,full_goal_complete=False)
    if prepare:
        assert not(OUT/'merge_manifest.json').exists();write(OUT/'summary.json',summary);write(OUT/'verification.json',report);write(OUT/'quantity_audits.json',audits)
    else:
        assert json.loads((OUT/'summary.json').read_text('utf8'))==summary;assert json.loads((OUT/'verification.json').read_text('utf8'))==report;assert json.loads((OUT/'quantity_audits.json').read_text('utf8'))==audits
        if(OUT/'merge_manifest.json').exists():
            for p in json.loads((OUT/'merge_manifest.json').read_text('utf8'))['outputs']:assert sha(ROOT/p['path'])==p['sha256']
    print(json.dumps(dict(checks=len(checks),summary=summary),ensure_ascii=False))

def seal():
    assert not(OUT/'merge_manifest.json').exists()
    from verify_corpus_chain_v11 import run
    run(False)
    paths=[p for p in OUT.rglob('*')if p.is_file()]+[ROOT/'tools/extract_biomass_series_v11.py',ROOT/'tools/verify_corpus_chain_v11.py',ROOT/'data/literature_v11.py']
    write(OUT/'merge_manifest.json',dict(version='literature_pool_v11',parent_sha256=PSHA,outputs=[dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p),bytes=p.stat().st_size)for p in sorted(paths)],model_fits=0,scientific_goal_complete=False))
    write(ROOT/'data/current_literature.json',dict(version='literature_pool_v11',directory=OUT.relative_to(ROOT).as_posix(),database_file=DB.name,sha256=sha(DB),api_module='data.literature_v11',scope='Fourprimarysource scopes/15materials; priorworkfamily/quarantine; cycles remain separate review, nofit'))

if __name__=='__main__':
    if len(sys.argv)!=2 or sys.argv[1]not in['curate','build','resume_empty_build','prepare','verify','seal']:raise SystemExit('curate/build/seal once; verify read-only')
    if sys.argv[1]=='prepare':verify(True)
    else:globals()[sys.argv[1]]()
