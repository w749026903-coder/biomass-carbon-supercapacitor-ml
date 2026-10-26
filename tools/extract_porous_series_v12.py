"""One-use additive curation of two source scopes; verify is read-only."""
from pathlib import Path
from contextlib import closing
import hashlib,json,re,sqlite3,sys,xml.etree.ElementTree as E,zipfile
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tools'))
from extract_onion_composite_v8 import sha,ro,write,insert,mk
from extract_palm_kernel_v7 import xml_grid
OUT=ROOT/'文献全量利用复核_20261026/批次12_椰壳苏铁绒芒果核与原料边界';EV=OUT/'evidence';DB=OUT/'literature_material_pool_v12.sqlite'
PARENT=ROOT/'文献全量利用复核_20261026/批次11_青豌豆皮水葫芦红茶与Tondolo/literature_material_pool_v11.sqlite';PSHA='f1aab46cbd15b4be6fbbbebe823f176efd5263953826ce42a991ee147312c70e'
CY='10.1039/d2ra02141b';CO='10.1039/d0ra09182k'
NAMES={CY:['CF-0','CF-HPC-1','CF-HPC-2','CF-HPC-3','CF_Table1_identity_unresolved'],CO:['AC1','AC2','AC3','AC4','AC5']}

def clean(e):return re.sub(r'\s+',' ',re.sub(r'<svg\b.*?</svg>','[vector-symbol]',''.join(e.itertext()),flags=re.S)).strip() if e is not None else ''
def number(raw,part=None):
    raw=raw.strip().replace('−','-')
    if raw in ['','—','–','-']:return None
    if part:
        a=raw.split('±');assert len(a)==2,raw;raw=a[part=='uncertainty'].strip()
    assert re.fullmatch(r'[+-]?(\d+(\.\d+)?|\.\d+)([eE][+-]?\d+)?',raw),raw
    return float(raw)

def curate():
    assert not DB.exists()and not(OUT/'curation_spec.json').exists()
    notes=json.loads((OUT/'source_review_notes.json').read_text('utf8'))
    spec=dict(sources=[],tables=[],units=[],facts=[],capacitances=[],responses=[],candidates=[],synthesis=[],decisions=[])
    docs={CY:'Cycas12',CO:'Coconut12'}
    with closing(ro(ROOT/'全库复检与特征补提取_20261021/full_corpus_search_native.sqlite'))as c:
        for item in notes['sources'][:2]:
            doi=item['doi'];path=ROOT/item['path'];assert sha(path)==item['sha256'];r=E.parse(path).getroot()
            spec['sources'].append(dict(item,key=docs[doi],title=clean(r.find('.//article-title'))))
            raw={x[1]:x[0]for x in c.execute('select table_id,locator from raw_tables_v11 where source_sha256=?',(item['sha256'],))}
            identities=c.execute('select identity_key,role,basis from identity_sources where sha256=?',(item['sha256'],)).fetchall();assert [x[0]for x in identities]==['doi:'+doi]
            spec['sources'][-1]['identity_evidence']=identities
            for t in r.findall('.//table-wrap'):
                id=t.get('id');loc='XML table-wrap '+id;spec['tables'].append(dict(doi=doi,document=docs[doi],id=id,locator=loc,caption=clean(t.find('caption')),footnote=clean(t.find('table-wrap-foot')),grid=xml_grid(t),raw_table_id=raw[loc],kind='foreign_comparison_only'if doi==CO and id=='tab1'else'mixed_comparison_own_last_row_only'if doi==CY and id=='tab3'else'own_xml_table'))
    def u(doi,id,header,rows,loc,document=None,kind='own_numeric_prose',**extra):
        spec['units'].append(dict(doi=doi,id=id,header=header,rows=rows,locator=loc,document=document or docs[doi],kind=kind,**extra));return id
    def f(doi,s,id,row,col,field,unit,method,status='own_reported_method_qualified',part=None):spec['facts'].append(dict(doi=doi,sample=s,id=id,row=row,col=col,field=field,unit=unit,method=method,status=status,part=part))
    def cap(doi,s,id,row,col,j=None,method='GCD',scan=None,unit='F/g',purpose=None,legacy=False,status='own_reported',**conditions):spec['capacitances'].append(dict(doi=doi,sample=s,id=id,row=row,col=col,current=j,method=method,scan=scan,unit=unit,purpose=purpose,legacy=legacy,status=status,conditions=conditions))
    def response(doi,s,id,row,col,metric,unit,**extra):spec['responses'].append(dict(doi=doi,sample=s,id=id,row=row,col=col,metric=metric,unit=unit,extra=extra))
    # CF in Table1 is not silently assigned to the raw feed or carbonized CF-0.
    for row,s in enumerate(['CF_Table1_identity_unresolved','CF-HPC-1','CF-HPC-2','CF-HPC-3'],3):
        for col,el in enumerate(['C','N','O','S'],1):f(CY,s,'tab1',row,col,'XPS_'+el+'_at_pct','at%','OwnTable1; CF row identity unresolved; HPC2 N/O competes with abstract',status='conflict_abstract_table_N_O'if s=='CF-HPC-2'and el in ['N','O']else'identity_unresolved'if row==3 else'own_reported_method_qualified')
    id=u(CY,'abstract_composition',['sample','C','O','N','S'],[['CF-HPC-2','91.77','4.09','3.54','.60']],'abstract atomiccomposition: C/O/N/S order competes with Table1 C/N/O/S')
    for col,el in enumerate(['C','O','N','S'],1):f(CY,'CF-HPC-2',id,1,col,'XPS_'+el+'_at_pct','at%','Ownabstract values/elementorder retained; Fig4 no numeric atomic labels',status='conflict_abstract_table_N_O'if el in['N','O']else'own_repeated_report')
    fields=[('BET_surface_area_m2_g','m2/g'),('micropore_surface_area_m2_g','m2/g'),('micropore_surface_fraction_pct','%'),('total_pore_volume_cm3_g','cm3/g'),('micropore_volume_cm3_g','cm3/g'),('micropore_volume_fraction_pct','%'),('author_assumed_density_g_cm3','g/cm3')]
    for row,s in enumerate(NAMES[CY][:4],2):
        for col,(field,unit)in enumerate(fields,1):f(CY,s,'tab2',row,col,field,unit,'OwnTable2; rho=1/(Vt+1/rho_t),rho_t=2g/cm3 assumed; density not measured packing density'if col==7 else'OwnTable2 BET/t-plot as described, author rounding retained')
    id=u(CY,'Raman_p16',['sample','ID_IG'],[[s,v]for s,v in zip(NAMES[CY][:4],['.82','.91','.91','.97'])],'body16 author D/G peakintensity ratios')
    for i,s in enumerate(NAMES[CY][:4],1):f(CY,s,id,i,1,'Raman_ID_IG','ratio','Ownpeakintensity ratio; not integrated-area method')
    id=u(CY,'XPS_p14',['sample','component','BE'],[['CF-HPC-2',label,v]for label,v in [('C_CdoubleC','284.7'),('C_CC','284.8'),('C_CO','286.3'),('O_CO','531.9'),('O_COH','532.8'),('O_COC','532.8'),('N_N5','397.5'),('N_NQ','400.3'),('N_NX','402.5'),('S_CSC','163.6'),('S_CS','164.7'),('S_CSOxC','168.5')]],'body14 own author XPS componentassignments; repeated532.8 retained')
    for i,(label,v)in enumerate([('C_CdoubleC','284.7'),('C_CC','284.8'),('C_CO','286.3'),('O_CO','531.9'),('O_COH','532.8'),('O_COC','532.8'),('N_N5','397.5'),('N_NQ','400.3'),('N_NX','402.5'),('S_CSC','163.6'),('S_CS','164.7'),('S_CSOxC','168.5')],1):f(CY,'CF-HPC-2',id,i,2,'XPS_'+label+'_binding_energy_eV','eV','Author assignment retained, no silent spectral reinterpretation')
    cycond=dict(system='3E',electrolyte='KOH',concentration_mol_L=6,voltage_lower_V=-1,voltage_upper_V=0,reference_electrode='Hg/HgO',physical_test_group='doi:'+CY+':HPC2:KOH:Fig7_GCD',mass_loading_mg_cm2=2.5,current_mass_basis='author_reported_unknown_not_inferred')
    cap(CY,'CF-HPC-2','tab3',13,2,1,legacy=True,capacitance_basis='single_working_carbon_electrode',**cycond)
    cap(CY,'CF-HPC-2','tab3',13,3,1,unit='F/cm3',status='own_comparison_rounded_same_test_not_new_measurement',capacitance_basis='author_Cg_times_assumed_density',**cycond)
    id=u(CY,'volume_prose',['sample','current','Cv'],[['CF-HPC-2','1','349.1'],['CF-HPC-2','10','289.1']],'abstract/body4/conclusion23 same reports; Fig7c highcurrent gravimetric curve requires further numeric comparison')
    for i,j in enumerate([1,10],1):cap(CY,'CF-HPC-2',id,i,2,j,unit='F/cm3',purpose='reported_3e_author_density_volume'if i==1 else None,status='own_reported'if i==1 else'author_highcurrent_report_figure_comparison_pending',capacitance_basis='author_Cg_times_assumed_density',target_derived_from_Cg_and_assumed_density=True,assumed_true_carbon_density_g_cm3=2,**cycond)
    id=u(CY,'cycles_Fig8f',['sample','electrolyte','retention','cycles','j'],[['CF-HPC-2','1M Na2SO4','96.36','10000','1'],['CF-HPC-2','6M KOH','96.71','10000','1']],'body20 + actualFig8f endpointlabels; caption8f explicit1Ag',document='CycasFig8_12',kind='own_printed_figure_annotations')
    for i,(salt,m,ret,lo,hi)in enumerate([('Na2SO4',1,96.36,0,1),('KOH',6,96.71,-1,0)],1):
        for col,metric,unit in[(2,'cycling_retention','%'),(3,'cycle_count','cycles'),(4,'cycle_current','A/g')]:response(CY,'CF-HPC-2',id,i,col,metric,unit,electrolyte=salt)
        spec['candidates'].append(dict(candidate_id='LP12_Cycas_'+salt+'_3E_C10000',doi=CY,sample='CF-HPC-2',record=dict(source_year=2022,system='3E',method='GCD',metric='capacitance_retention',metric_kind='cycling_retention',retention_pct=ret,retention_relation='eq',cycle_count=10000,reported_current_A_g=1,current_mass_basis='author_reported_unknown_not_inferred',electrolyte=salt,concentration_mol_L=m,cycle_voltage_lower_V=lo,cycle_voltage_upper_V=hi,reference_electrode='Hg/HgO',reference_basis='common3E method + same method for Na2SO4',BET_m2_g=516.7,baseline_reference='author_initial_specific_capacitance',baseline_cycle=None,purpose_reviewed_candidate_ready=True,admission_still_required=True,evidence='Fig8f printed endpoints/caption current/body20; actualFigs7b/e and8b/e own salt GCD windows',source_group='doi:'+CY,curve_group='doi:'+CY+':Fig8f:'+salt,composition_N_O_conflict_not_resolved=True)))
    id=u(CY,'device_energy',['sample','E','P'],[['CF-HPC-2','27.72','20000'],['CF-HPC-2','21.31','40000']],'body22/conclusion23 literalpower kW/kg vs actualFig9e scale unresolved')
    for i in [1,2]:
        response(CY,'CF-HPC-2',id,i,1,'device_energy_density','Wh/kg',system='2E_symmetric',electrolyte='Na2SO4',concentration_mol_L=2)
        response(CY,'CF-HPC-2',id,i,2,'device_power_density','W/kg',status='author_literal_power_vs_Ragone_figure_pending')
    # Coconut: all five final carbons, including microcrystalline and integrated Raman fields.
    for row,s in enumerate(NAMES[CO],2):
        for col,field,unit in [(1,'XRD_2theta002_deg','degree'),(2,'XRD_2theta100_deg','degree'),(3,'XRD_d002_nm','nm'),(4,'XRD_d100_nm','nm'),(5,'XRD_Scherrer_Lc002_nm','nm'),(6,'XRD_Scherrer_La100_nm','nm')]:f(CO,s,'tab2',row,col,field,unit,'OwnXRD/Scherrer, shape factors .9(Lc),1.84(La); no independent direct TEM measurement')
        for col,field,unit in [(1,'Raman_D_position_cm_inv','cm^-1'),(2,'Raman_D_integrated_area','author_integrated_area_unit_unspecified'),(3,'Raman_G_position_cm_inv','cm^-1'),(4,'Raman_G_integrated_area','author_integrated_area_unit_unspecified'),(5,'Raman_integrated_area_ID_IG','ratio')]:f(CO,s,'tab3',row,col,field,unit,'Integrated D/G areas, NOT peakheight ID/IG; 514.5nm/.7mW fit')
        for col,field,unit in[(6,'PVP_film_sheet_resistance_kohm_sq','kohm/sq'),(7,'PVP_film_conductivity_S_m','S/m')]:
            f(CO,s,'tab3',row,col,field,unit,'25um PVP-containing film/4probe; reportedmean, ± statistic not defined',part='mean')
            f(CO,s,'tab3',row,col,field+'_author_plusminus',unit,'Author±, not declared SD/SEM/CI',part='uncertainty')
        for col,field,unit in[(1,'BET_surface_area_m2_g','m2/g'),(2,'total_pore_volume_cm3_g','cm3/g'),(3,'DFT_area_in_pores_unspecified_class_m2_g','m2/g')]:
            part=None if s=='AC1'and col==3 else'mean';f(CO,s,'tab4',row,col,field,unit,'OwnN2 BET/DFT; porearea class unspecified; author± meaning not declared; AC1 zero not absence of all pores',part=part)
            if part:f(CO,s,'tab4',row,col,field+'_author_plusminus',unit,'Author± not assumed SD/SEM/CI',part='uncertainty')
    # SI exact printed pair cells expanded by representation, never by recalculating x4.
    u(CO,'SI_TableS1',['ACwt','PVPwt','PVDFwt','CBwt','collector','electrolyte','separator'],[['96','4','-','-','FTO','6M KOH','filterpaper'],['96','4','-','-','FTO','1.5M H2SO4','filterpaper'],['85','-','10','5','Ti','1.5M H2SO4','filterpaper'],['85','-','10','5','expanded_graphite','1.5M H2SO4','filterpaper'],['85','-','10','5','expanded_graphite','pure MPPyFSI','filterpaper or polyethylene']],'SIp2 TableS1 rawrecipe/collector rows; dashnotzero',document='CoconutSI12',kind='own_SI_table')
    s2=[['AC1','539±16','52.4','13.1','42.4','10.6','52.4 (13.1)','42.4 (10.6)'],['AC2','858±25','76.9','19.2','73.0','18.3','76.9 (19.2)','73.0 (18.3)'],['AC3','952±28','75.2','18.8','69.0','17.3','75.2 (18.8)','69.0 (17.3)'],['AC4','1054±31','75.6','18.9','71.2','17.8','75.6 (18.9)','71.2 (17.8)'],['AC5','1998±58','106','26.5','106.0','26.5','106 (26.5)','106.0 (26.5)']]
    u(CO,'SI_TableS2',['sample','BETraw','CV_Cs','CV_Cd','CD_Cs','CD_Cd','original_CVpair','original_CDpair'],s2,'SIp5 TableS2; split literal Cs(Cd) into pairedcolumns; same physical test, no new measurement',document='CoconutSI12',kind='own_SI_table',pair_columns={'2,3':6,'4,5':7})
    s3=[['2','109.5','27.4','.2','96.7','24.2','109.5 (27.4)','96.7 (24.2)'],['5','102.7','25.7','.5','89.9','22.5','102.7 (25.7)','89.9 (22.5)'],['10','97.7','24.4','1','82.7','20.7','97.7 (24.4)','82.7 (20.7)'],['20','91.4','22.8','2','72.2','18.0','91.4 (22.8)','72.2 (18.0)'],['50','79.1','19.8','','','','79.1 (19.8)',''],['100','66.1','16.5','','','','66.1 (16.5)','']]
    u(CO,'SI_TableS3',['scan','CV_Cs','CV_Cd','j','CD_Cs','CD_Cd','original_CVpair','original_CDpair'],s3,'SIp7 TableS3; .5Ag and5mVs compete with TableS2; not invented replicate identities',document='CoconutSI12',kind='own_SI_table',pair_columns={'1,2':6,'4,5':7})
    def coconut_conditions(id,row,salt,m,collector,separator='filterpaper',ionic=False,lo=0,hi=1):
        explicit_recipe=not ionic or collector=='expanded_graphite'
        return dict(system='2E_symmetric',electrolyte=salt,concentration_mol_L=m,electrolyte_class='neat_ionic_liquid'if ionic else'aqueous',voltage_lower_V=lo,voltage_upper_V=(.9 if salt=='H2SO4' else hi),reference_electrode=None,current_collector=collector,separator=separator,current_mass_basis='author_reported_unknown_not_inferred',capacitance_mass_scope='author_m_active_not_explicitly_total_both',carbon_wt_pct=(96 if collector=='FTO'else 85)if explicit_recipe else None,PVP_wt_pct=4 if collector=='FTO'and explicit_recipe else None,PVDF_wt_pct=10 if collector!='FTO'and explicit_recipe else None,carbon_black_wt_pct=5 if collector!='FTO'and explicit_recipe else None,recipe_basis='OwnSI_S1 exactconfiguration'if explicit_recipe else'SI_S1 does not explicitly list this IL/collector recipe',physical_test_group='doi:'+CO+':'+salt+':'+collector+':'+separator+':'+id+':row'+str(row))
    for i,s in enumerate(NAMES[CO],1):
        cond=coconut_conditions('S2',i,'KOH',6,'FTO')
        for col,method,basis in[(2,'CV','Cs'),(3,'CV','Cd'),(4,'GCD','Cs'),(5,'GCD','Cd')]:
            conflict=s=='AC5';cap(CO,s,'SI_TableS2',i,col,.5 if method=='GCD'else None,method,5 if method=='CV'else None,purpose=('reported_2e_aqueous_author_'+basis+('_factor4'if basis=='Cs'else''))if method=='GCD'and not conflict else None,status='conflict_S2_S3_same_nominal_protocol'if conflict else'own_reported',capacitance_basis='author_Cs_factor4'if basis=='Cs'else'author_reported_Cd',same_test_representations_not_independent=True,**cond)
    for i,row in enumerate(s3,1):
        for col,method,basis in[(1,'CV','Cs'),(2,'CV','Cd')]+([(4,'GCD','Cs'),(5,'GCD','Cd')]if i<=4 else[]):
            conflict=i==2;cond=coconut_conditions('S3',i,'KOH',6,'FTO');cond['physical_test_group']+=':method'+method
            cap(CO,'AC5','SI_TableS3',i,col,float(row[3])if method=='GCD'else None,method,float(row[0])if method=='CV'else None,purpose=('reported_2e_aqueous_author_'+basis+('_factor4'if basis=='Cs'else''))if method=='GCD'and not conflict else None,status='conflict_S2_S3_same_nominal_protocol'if conflict else'own_reported',capacitance_basis='author_Cs_factor4'if basis=='Cs'else'author_reported_Cd',same_test_representations_not_independent=True,**cond)
    s5=[['FTO','22.9','105.9','26.5','94.48','23.6','2.6','224.5','105.9 (26.5)','94.48 (23.6)'],['expanded_graphite','.7','132.3','33.1','118.0','29.5','3.3','225.1','132.3 (33.1)','118.0 (29.5)'],['Ti','7.0','144.9','36.2','123.0','30.8','3.4','225.4','144.9 (36.2)','123.0 (30.8)']]
    s6=[['FTO','filterpaper','58.3','153.8','38.5','153.7','38.4','65.4','2123.0','153.8 (38.5)','153.7 (38.4)'],['expanded_graphite','filterpaper','22.7','224.5','56.1','233.5','58.4','99.3','2267.6','224.5 (56.1)','233.5 (58.4)'],['Ti','filterpaper','32.7','161.0','40.3','170.9','42.7','72.7','2037.2','161.0 (40.3)','170.9 (42.7)'],['expanded_graphite','ozone_treated_polyethylene_7um','4.3','219.4','54.8','216.6','54.1','92.1','2046.9','219.4 (54.8)','216.6 (54.1)']]
    u(CO,'SI_TableS5',['collector','ESR','CV_Cs','CV_Cd','CD_Cs','CD_Cd','E','P','original_CVpair','original_CDpair'],s5,'SIp8 TableS5 1.5MH2SO4/filterpaper,5mVs/.5Ag; paired Cs/Cd author reports',document='CoconutSI12',kind='own_SI_table',pair_columns={'2,3':8,'4,5':9})
    u(CO,'SI_TableS6',['collector','separator','ESR','CV_Cs','CV_Cd','CD_Cs','CD_Cd','E','P','original_CVpair','original_CDpair'],s6,'SIp8 TableS6 pure MPPyFSI,5mVs/1Ag; final216.6GCD vs219.4CV',document='CoconutSI12',kind='own_SI_table',pair_columns={'3,4':9,'5,6':10})
    for id,rs,ionic in[('SI_TableS5',s5,False),('SI_TableS6',s6,True)]:
        offset=int(ionic)
        for i,row in enumerate(rs,1):
            cond=coconut_conditions(id,i,'MPPyFSI'if ionic else'H2SO4',None if ionic else 1.5,row[0],row[1]if ionic else'filterpaper',ionic,hi=3.5 if ionic else 1)
            for col,method,basis in[(2+offset,'CV','Cs'),(3+offset,'CV','Cd'),(4+offset,'GCD','Cs'),(5+offset,'GCD','Cd')]:cap(CO,'AC5',id,i,col,1 if ionic else.5,method,5 if method=='CV'else None,purpose=('reported_2e_'+('ionic'if ionic else'aqueous')+'_author_'+basis+('_factor4'if basis=='Cs'else''))if method=='GCD'else None,capacitance_basis='author_Cs_factor4'if basis=='Cs'else'author_reported_Cd',same_test_representations_not_independent=True,**cond)
            for col,metric,unit in[(1+offset,'EIS_ESR','ohm'),(6+offset,'device_energy_density','Wh/kg'),(7+offset,'device_power_density','W/kg')]:response(CO,'AC5',id,i,col,metric,unit,**cond)
    # CV has scan rate, not an assigned galvanostatic current.
    for r in spec['capacitances']:
        r['conditions']['physical_test_group']+=':sample'+r['sample']+':method'+r['method']
        if r['method']=='CV':r['current']=None
    s4=[['R1','23','22','ohm'],['W','16','7.9','ohm s^-1/2'],['Q1','1.2e-4','32e-6','F s^(n-1)'],['n','.79','.84','ratio'],['Ra','.5','9.7','ohm'],['C1','16.2e-4','46.0e-4','F/g'],['C3','10','22','F/g'],['R3','249','1668','ohm'],['C_at_.01Hz','44','82','F/g']]
    u(CO,'SI_TableS4',['parameter','AC1','AC5','unit'],s4,'SIp7 TableS4 fitted EIS parameters; BET repeated S2 not duplicated as new materialfacts',document='CoconutSI12',kind='own_SI_table')
    for i,row in enumerate(s4,1):
        for col,s in[(1,'AC1'),(2,'AC5')]:response(CO,s,'SI_TableS4',i,col,'EIS_'+row[0],row[3],not_pretest_predictor=True)
    id=u(CO,'EIS_prose',['sample','C','phase'],[['AC1','44','63'],['AC5','84','72']],'body46 .01Hz ownEIS; AC5 84 vsSI82 retained, not GCD')
    for i,s in enumerate(['AC1','AC5'],1):response(CO,s,id,i,1,'EIS_lowfrequency_C','F/g',status='conflict_AC5_prose84_SI82'if s=='AC5'else'own_reported');response(CO,s,id,i,2,'EIS_phase_angle','degree')
    id=u(CO,'prose_collector_GCD',['sample','collector','C'],[['AC5','FTO','94.5'],['AC5','expanded_graphite','118.0'],['AC5','Ti','123.0']],'body48 sameSI_S5; FTO94.48->94.5 matchingrounding')
    for i,row in enumerate(s5,1):cap(CO,'AC5',id,i,2,.5,status='own_repeat_report_not_new_test',capacitance_basis='author_Cs_factor4',**coconut_conditions('SI_TableS5',i,'H2SO4',1.5,row[0]))
    id=u(CO,'conclusion_C219',['sample','C'],[['AC5','219.4']],'conclusion55 wrongly associates CV219.4 with1Ag; SI_S6 explicitly CV219.4/GCD216.6')
    cap(CO,'AC5',id,1,1,1,method='method_ambiguous_conclusion',status='conflict_conclusion_method_assignment',capacitance_basis='author_Cs_factor4',**coconut_conditions('conclusion',1,'MPPyFSI',None,'expanded_graphite','ozone_treated_polyethylene_7um',True,hi=3.5))
    id=u(CO,'energy_high_current',['sample','separator','j','E','P'],[['AC5','filterpaper','10','28.4','18466'],['AC5','polyethylene','30','28.6','70259']],'body51 explicitseparator/j/E/P; energy retention is rate retention not cycling')
    for i in[1,2]:response(CO,'AC5',id,i,3,'device_energy_density','Wh/kg');response(CO,'AC5',id,i,4,'device_power_density','W/kg')
    id=u(CO,'cycle_prose49',['sample','retention','cycles','j','chargingV'],[['AC5','92.3','5000','1','1']],'body49 ownretention +SIp8 FigS5 explicitlyTi/AC5/MPPyFSI/filterpaper, not3.5V freshwindow')
    for col,metric,unit in[(1,'cycling_retention','%'),(2,'cycle_count','cycles'),(3,'cycle_current','A/g'),(4,'cycle_charging_voltage','V')]:response(CO,'AC5',id,1,col,metric,unit)
    spec['candidates'].append(dict(candidate_id='LP12_Coconut_AC5_IL_Ti_C5000',doi=CO,sample='AC5',record=dict(source_year=2021,system='2E_symmetric',method='GCD',metric_kind='cycling_retention',retention_pct=92.3,retention_relation='eq',cycle_count=5000,reported_current_A_g=1,electrolyte='MPPyFSI',electrolyte_class='neat_ionic_liquid',concentration_mol_L=None,current_collector='Ti',separator='filterpaper',cycle_voltage_lower_V=None,cycle_voltage_upper_V=1,baseline_reference='author_initial_capacitance',baseline_cycle=None,purpose_reviewed_candidate_ready=False,reason='Specificnon-aqueouspurposeandactualcycledischarge lowerboundnotyetreviewed; do notborrowfresh0..3.5V or othercollector',evidence='body49+SIp8FigS5; sourcePDF not SI alone for92.3',source_group='doi:'+CO,curve_group='doi:'+CO+':FigS5')))
    # Recipes stay at the actual material stage; no collapsing repeated quench/steam routes.
    for i,s in enumerate(NAMES[CY][:4]):spec['synthesis'].append(dict(doi=CY,sample=s,document=docs[CY],locator='body6/8',stages=[dict(stage='aqueous_raw_biomass_impregnation',duration_h=24,agent='NaHCO3',activator_to_raw_biomass_mass_ratio=i,pre_drying_C=100,pre_drying_h=24),dict(stage='single_pyrolysis_carbonization_and_activation',temperature_C=700,duration_h=2,atmosphere='Ar',heating_rate_C_min=5,post_wash_HCl_M=1,post_wash_pH=7,post_drying_C=100,post_drying_h=24),dict(stage='electrode_preparation',carbon_acetylene_PTFE_mass_parts=[48,9,3],collector='Ni_foam',area_cm2=1,mass_loading_mg_cm2=2.5,approximate_loading=True,drying_C=85,drying_h=24)]))
    for s in NAMES[CO]:
        stages=[dict(stage='closed_container_shell_burning_to_char',temperature_C=None,duration_h=None,post_wash=True,post_drying_C=100)]
        if s in['AC1','AC2']:stages.append(dict(stage='water_quench_activation_cycles',temperature_C=900,duration_min_per_cycle=20,cycles=1 if s=='AC1'else 10,atmosphere='closed_box_unspecified',particle_size_mm='powder'if s=='AC1'else[.5,1.5],disc_mill_min=10,disc_mill_order='before_activation'if s=='AC1'else'after_activation'))
        else:
            stages.append(dict(stage='steam_activation',temperature_C=900,duration_h=2 if s=='AC3'else 1,particle_size_mm=[.5,1.5],cooling='water_quench'if s=='AC3'else'to200C_under_steam',disc_mill_min=None if s=='AC3'else 3))
            if s=='AC5':stages.append(dict(stage='second_steam_activation_of_AC4_powder',temperature_C=900,duration_h=1,particle_size_upper_mm=.1,cooling='to200C_under_steam'))
        stages.append(dict(stage='electrode_preparation_recipe_by_configuration',aqueous_FTO=dict(carbon_wt_pct=96,PVP_wt_pct=4),metal_graphite_recipe=dict(carbon_wt_pct=85,PVDF_wt_pct=10,carbonblack_wt_pct=5),drying_C=100,drying_min=15,Ti_IL_cycle_recipe_not_explicit_in_TableS1=True))
        spec['synthesis'].append(dict(doi=CO,sample=s,document=docs[CO],locator='body7..14/21/39 +SIp2TableS1',stages=stages))
    decisions=[(CY,'N_O_swap','Freeze HPC2 N/O canonical features; Table1 N4.09/O3.54, abstract O4.09/N3.54. Fig4 has no resolving atomiclabels.'),(CY,'CF_identity','Table1 CF maps to its own unresolved registration, not raw CF or CF-0; do not propagate its XPS.'),(CY,'density_volume','rho=1/(Vt+1/2), author assumed truecarbon density, not measured packing density. Keep mass/volume tasks separate, same source/test quarantine.'),(CY,'highcurrent_volume','Keep289.1F/cm3@10Ag report; Fig7c mass endpoint comparison still requires bounded digitization. No select-by-highest.'),(CY,'Ragone_power','Literal20/40kWkg body22 vs Fig9e axispoints unresolved. Preserve reports, not silently convert to W/kg using guessed current.'),(CO,'S2_S3_competition','AC5 at.5Ag has Cs106.0/Cd26.5 vs89.9/22.5; CV5 has106/26.5 vs102.7/25.7. Freeze these nominal overlaps, do not invent replicate batches. Other noncompeting currents remain specific reported inputs.'),(CO,'method_conclusion','Select SI_S6 explicitGCD216.6@1Ag andCV219.4@5mVs; preserve conclusion219.4@1Ag as method-conflicting prose.'),(CO,'BET_minimum','Table4+SI_S2 AC1 BET539±16 vs conclusionlowerbound586. Keep specificAC1 own table539, preserve586 as unbound range dissent.'),(CO,'EIS_dissent','AC5 .01Hz body84 vsSI82 retained as EIS competition, not GCD label or pretest feature.'),(CO,'Raman_area_method','Integrated-area ID/IG is its own feature; not generic peak-intensity ID/IG. Rounded area ratios are not replaced by exact division.'),(CO,'device_normalization','All2E, Cs=4Cd representations of same device. Author m active not explicit totalboth; newreportedpurposes separate from physicallyunified device targets. Current denominator remains unknown.'),(CO,'uncertainty_and_DFTzero','± statistic unspecified; mean and author± separate. AC1 DFTarea_in_pores0 does not mean nonporous or microporearea0.'),(CO,'cycle_binding','92.3/5000/1Ag appliesTi+IL+filterpaper charged1V; no3.5V substitution. Non-aqueouscycle candidate remains pending, no ordinaryaqueousqualification.')]
    spec['decisions']=[dict(id='LP12_'+id,doi=doi,decision=text)for doi,id,text in decisions]
    write(OUT/'curation_spec.json',spec);print(json.dumps({k:len(v)for k,v in spec.items()}))

def documents(spec):
    docs={s['key']:dict(doi=s['doi'],path=ROOT/s['path'])for s in spec['sources']}
    docs.update(CoconutSI12=dict(doi=CO,path=EV/'RA-011-D0RA09182K-s001.pdf'),CycasFig8_12=dict(doi=CY,path=EV/'d2ra02141b-f8.jpg'))
    return docs

def build():
    assert sha(PARENT)==PSHA and not DB.exists()and not(OUT/'merge_manifest.json').exists()
    spec=json.loads((OUT/'curation_spec.json').read_text('utf8'));docs=documents(spec)
    with closing(ro(PARENT))as parent,closing(sqlite3.connect(DB))as c:
        parent.backup(c);c.row_factory=sqlite3.Row;c.execute('pragma foreign_keys=on')
        c.executescript('''create table source_reviews_v12(doi text primary key references reviewed_sources,record_json text);create table cell_extractions_v12(kind text,record_id text,table_key text references reviewed_tables,row_ordinal integer,column_ordinal integer,parse_part text,primary key(kind,record_id));create table decisions_v12(decision_id text primary key,doi text references reviewed_sources,record_json text);create table purpose_reviews_v12(observation_id text references capacitance_observations,purpose text,eligible integer,reason text,primary key(observation_id,purpose));''')
        for s in spec['sources']:insert(c,'reviewed_sources',dict(doi=s['doi'],path=s['path'],sha256=s['sha256'],title=s['title'],stage='Allmainparagraphs read; allownmain/SItables in specifiedscope; waveformremaining'))
        for key,d in docs.items():insert(c,'source_documents',dict(document_key=key,doi=d['doi'],path=d['path'].relative_to(ROOT).as_posix(),sha256=sha(d['path']),role='primary_xml'if key in['Cycas12','Coconut12']else'own_SI_or_actual_figure'))
        for t in spec['tables']+spec['units']:
            key=t['doi']+'#'+t['id'];rows=[[v['raw']for v in r]for r in t['grid']]if'grid'in t else t['rows']
            insert(c,'reviewed_tables',dict(table_key=key,doi=t['doi'],xml_id=t['id'],caption=t.get('caption',t['id']),header_json=json.dumps(rows[0]if'grid'in t else t['header'],ensure_ascii=False),footnote=t.get('footnote','Ownspecifiedscope; pairedreports not independent experiments'),source_raw_table_id=t.get('raw_table_id')))
            insert(c,'table_source_links',dict(table_key=key,document_key=t['document'],locator=t['locator']));insert(c,'extraction_units_v3',dict(table_key=key,kind=t['kind'],scope='Specifiedowncells only; foreigntable/comparison rows not own labels'))
            for i,row in enumerate(rows,1):
                insert(c,'transcribed_rows',dict(table_key=key,row_ordinal=i,cells_json=json.dumps(row,ensure_ascii=False)))
                insert(c,'transcription_origins_v7',dict(table_key=key,row_ordinal=i,origin_json=json.dumps(t['grid'][i-1]if'grid'in t else dict(document=t['document'],locator=t['locator'],row=i,pair_columns=t.get('pair_columns')),ensure_ascii=False)))
            if t.get('raw_table_id'):c.execute('update raw_table_queue set review_state=?where table_id=?',('v12_declared_scope_own_cells_foreign_rows_separate',t['raw_table_id']))
        for doi,names in NAMES.items():
            for s in names:
                unresolved=s=='CF_Table1_identity_unresolved';insert(c,'materials',dict(material_key=mk(doi,s),doi=doi,sample_name=s,material_stage='Table1_CF_identity_stage_unresolved'if unresolved else'final_biomass_carbon_before_test'))
                insert(c,'material_scopes_v8',dict(material_key=mk(doi,s),scope_json=json.dumps(dict(origin_class='biomass_carbon',feedstock='Cycas_fluff'if doi==CY else'coconut_shell',identity_unresolved=unresolved,not_assumed_pure_carbon=True,same_source_not_independent=True),ensure_ascii=False)))
        def cell(r):
            key=r['doi']+'#'+r['id'];raw=json.loads(c.execute('select cells_json from transcribed_rows where table_key=?and row_ordinal=?',(key,r['row'])).fetchone()[0])[r['col']];return key,raw,number(raw,r.get('part'))
        def receipt(kind,rid,r,key):insert(c,'cell_extractions_v12',dict(kind=kind,record_id=str(rid),table_key=key,row_ordinal=r['row'],column_ordinal=r['col'],parse_part=r.get('part')))
        for r in spec['facts']:
            key,raw,val=cell(r);doc=c.execute('select document_key from table_source_links where table_key=?',(key,)).fetchone()[0]
            cur=insert(c,'material_facts',dict(material_key=mk(r['doi'],r['sample']),field_name=r['field'],value=val,raw_value=raw,unit=r['unit'],method=r['method'],table_key=key,row_ordinal=r['row'],column_ordinal=r['col'],source_sha256=sha(docs[doc]['path']),review_status='author_dash_not_quantified_not_zero'if val is None else r['status'],training_eligible=0));receipt('fact',cur.lastrowid,r,key)
        for r in spec['capacitances']:
            key,raw,val=cell(r);cond=dict(extraction_batch='v12',**r['conditions']);rid=key+'#'+str(r['row'])+'#'+str(r['col'])
            insert(c,'capacitance_observations',dict(observation_id=rid,material_key=mk(r['doi'],r['sample']),table_key=key,row_ordinal=r['row'],column_ordinal=r['col'],value=val,raw_value=raw,unit=r['unit'],method=r['method'],system=cond['system'],electrolyte=cond['electrolyte'],concentration_mol_L=cond['concentration_mol_L'],current_A_g=r['current'],scan_rate_mV_s=r['scan'],conditions_json=json.dumps(cond,ensure_ascii=False),status=r['status'],source_group='doi:'+r['doi'],training_eligible=0));receipt('capacitance',rid,r,key)
            if r['legacy']:insert(c,'auxiliary_gcd_reviews_v3',dict(observation_id=rid,purpose='reported_aqueous_3e_GCD_capacitance',eligible=1,reason='OwnTable3 HPC2 massCg291@1Ag, actualFig7−1..0HgHgO/6MKOH, BETbound; N/O conflicts excluded',review_basis='Specificowncomparisonrow + commonmethod + actualFig7GCD'))
            if r['purpose']:insert(c,'purpose_reviews_v12',dict(observation_id=rid,purpose=r['purpose'],eligible=1,reason='Specificauthorrepresentation, sample/configuration/current/unit bound; competing/repeated/foreign reports not pooled'))
        for r in spec['responses']:
            key,raw,val=cell(r);rid=key+'#'+str(r['row'])+'#'+str(r['col']);insert(c,'outcome_observations_v3',dict(outcome_id=rid,material_key=mk(r['doi'],r['sample']),table_key=key,record_json=json.dumps(dict(source_group='doi:'+r['doi'],extraction_batch='v12',metric=r['metric'],value=val,raw_value=raw,unit=r['unit'],feature_role='test_or_fitted_response_not_pretest_predictor',**r['extra']),ensure_ascii=False),training_eligible=0));receipt('response',rid,r,key)
        source={s['doi']:s for s in spec['sources']}
        for r in spec['candidates']:insert(c,'test_candidates',dict(candidate_id=r['candidate_id'],material_key=mk(r['doi'],r['sample']),record_json=json.dumps(dict(r['record'],evidence_source_path=source[r['doi']]['path'],source_sha256=source[r['doi']]['sha256']),ensure_ascii=False),training_eligible=0))
        for r in spec['synthesis']:insert(c,'synthesis_stages_v3',dict(material_key=mk(r['doi'],r['sample']),document_key=r['document'],locator=r['locator'],stages_json=json.dumps(r['stages'],ensure_ascii=False)))
        for r in spec['decisions']:insert(c,'decisions_v12',dict(decision_id=r['id'],doi=r['doi'],record_json=json.dumps(r,ensure_ascii=False)));insert(c,'scientific_issues',dict(issue_id=r['id'],doi=r['doi'],sample_name=None,issue_json=json.dumps(dict(kind=r['id'],action=r['decision']),ensure_ascii=False)))
        for s in spec['sources']:
            decision=dict(classification='original_biomass_research',scope='Allmainparagraphs read; ownmain/SItables, selectednumericprose andoriginalcyclefigurelabels; not completewaveforms',remaining='RemainingCV/GCD/Raman/adsorption/EIS/morphology curves andsomeprosequantities notfullydigitized; nextfourselectedpapers stillqueued',full_source_review_complete=False)
            insert(c,'source_scope_decisions',dict(doi=s['doi'],scope=decision['scope'],reason=decision['remaining'],evidence_json=json.dumps(decision,ensure_ascii=False),full_source_review_complete=0));insert(c,'source_reviews_v12',dict(doi=s['doi'],record_json=json.dumps(decision,ensure_ascii=False)))
        c.commit()
    protected=[dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p))for p in EV.iterdir()if p.is_file()]+[dict(path=s['path'],sha256=s['sha256'])for s in spec['sources']]+[dict(path=PARENT.relative_to(ROOT).as_posix(),sha256=PSHA),dict(path='全库复检与特征补提取_20261021/full_corpus_search_native.sqlite',sha256='f2720c3e417904dad5857a6574cc72d5cf996f9b8716620d69594f11380c658c')]
    write(OUT/'protected_inputs.json',dict(files=protected));print('Draft v12 built; no cycling admission or fitting')

def verify(prepare=False):
    from data.literature_v12 import open_literature_database,TARGETS12
    from data.literature_v11 import open_literature_database as oldapi
    checks=[]
    def ck(n,ok):
        if not ok:raise AssertionError(n)
        checks.append(n)
    digest=sha(DB);spec=json.loads((OUT/'curation_spec.json').read_text('utf8'))
    for p in json.loads((OUT/'protected_inputs.json').read_text('utf8'))['files']:ck('protected:'+p['path'],sha(ROOT/p['path'])==p['sha256'])
    for p in json.loads((PARENT.parent/'merge_manifest.json').read_text('utf8'))['outputs']:ck('parent_payload:'+p['path'],sha(ROOT/p['path'])==p['sha256'])
    for label in['Cycas','Coconut']:
        receipt=json.loads((EV/(label+'_acquisition.json')).read_text('utf8'));ck('OApackage_'+label,sha(ROOT/receipt['path'])==receipt['sha256'])
        with zipfile.ZipFile(ROOT/receipt['path'])as z:
            for n in receipt['selected_members']:ck('exact_original_member:'+n,(EV/n).read_bytes()==z.read(n))
    with closing(ro(DB))as c:
        c.row_factory=sqlite3.Row;ck('integrity',c.execute('pragma integrity_check').fetchone()[0]=='ok');ck('foreignkeys',not c.execute('pragma foreign_key_check').fetchall());c.execute('attach database ?as parent',(PARENT.as_uri()+'?mode=ro',))
        for (t,)in c.execute("select name from parent.sqlite_master where type='table'and name not like 'sqlite_%'"):
            if t=='raw_table_queue':continue
            ck('all_parent_rows_retained:'+t,not c.execute('select *from parent.'+t+' except select *from main.'+t).fetchall())
        changed=c.execute('select table_id from raw_table_queue where review_state like\'v12_%\'').fetchall();ck('seven_raw_tables_only',len(changed)==7)
        touched={t['raw_table_id']for t in spec['tables']}
        for oldrow in c.execute('select *from parent.raw_table_queue'):
            now=dict(c.execute('select *from raw_table_queue where table_id=?',(oldrow['table_id'],)).fetchone());before=dict(oldrow)
            if oldrow['table_id']in touched:
                ck('previously_untouched:'+oldrow['table_id'],before['review_state']=='automatic_candidate_unreviewed');now['review_state']=before['review_state']
            ck('raw_queue_original_fields:'+oldrow['table_id'],now==before)
        ck('959_raw_candidates_preserved',c.execute('select count(*)from raw_table_queue').fetchone()[0]==959)
        ck('828_actual_untouched',c.execute("select count(*)from raw_table_queue where review_state='automatic_candidate_unreviewed'").fetchone()[0]==828)
        for table in['material_facts','capacitance_observations','outcome_observations_v3','test_candidates','raw_table_queue']:ck('no_raw_auto_qualification:'+table,c.execute('select count(*)from '+table+' where training_eligible!=0 or training_eligible is null').fetchone()[0]==0)
        for t in spec['tables']:
            root=E.parse(ROOT/next(s['path']for s in spec['sources']if s['doi']==t['doi'])).getroot();ck('original_XML_grid:'+t['doi']+t['id'],xml_grid(next(x for x in root.findall('.//table-wrap')if x.get('id')==t['id']))==t['grid'])
        for r in c.execute('select *from cell_extractions_v12'):
            raw=json.loads(c.execute('select cells_json from transcribed_rows where table_key=?and row_ordinal=?',(r['table_key'],r['row_ordinal'])).fetchone()[0])[r['column_ordinal']];val=number(raw,r['parse_part']);table={'fact':'material_facts','capacitance':'capacitance_observations','response':'outcome_observations_v3'}[r['kind']];idfield={'fact':'fact_id','capacitance':'observation_id','response':'outcome_id'}[r['kind']];stored=dict(c.execute('select *from '+table+' where '+idfield+'=?',(r['record_id'],)).fetchone());stored=json.loads(stored['record_json'])if r['kind']=='response'else stored;ck('cell:'+r['kind']+':'+r['record_id'],stored['raw_value']==raw and stored['value']==val)
        old=json.loads((PARENT.parent/'summary.json').read_text('utf8'));summary=dict(old)
        count=lambda t:c.execute('select count(*)from '+t).fetchone()[0]
        numeric=c.execute('select count(*)from material_facts where value is not null').fetchone()[0];caps=count('capacitance_observations');unreported=c.execute('select count(*)from material_facts where value is null').fetchone()[0]
        summary.update(cumulative_reviewed_source_publications=count('reviewed_sources'),cumulative_materials=count('materials'),cumulative_selected_material_cells=count('material_facts'),cumulative_numeric_material_facts=numeric,new_materials=len(sum(NAMES.values(),[])),new_numeric_material_facts=numeric-old['cumulative_numeric_material_facts'],reviewed_table_units=old['reviewed_table_units']+13,reviewed_evidence_units=count('reviewed_tables'),raw_candidates_touched=old['raw_candidates_touched']+7,raw_candidates_untouched=old['raw_candidates_untouched']-7,capacitance_records=caps,numeric_capacitance_values=c.execute('select count(*)from capacitance_observations where value is not null').fetchone()[0],cycling_candidates=count('test_candidates'),scientific_issues=count('scientific_issues'),synthesis_materials=count('synthesis_stages_v3'),response_outcomes=count('outcome_observations_v3'),new_source_response_records=len(spec['responses']),auxiliary_aqueous_3e_GCD_rows=old['auxiliary_aqueous_3e_GCD_rows']+1,auxiliary_independent_DOI_groups=old['auxiliary_independent_DOI_groups']+1,auxiliary_purpose_reviewed_input_rows=old['auxiliary_purpose_reviewed_input_rows']+1,scope_note='Two ownsource scopes/10registrations including1unresolvedidentity, sevenmaintables(2comparison) and6SI tables; nextfourpapers remainqueued. SeparateauthorCs/Cd/volume purposes, nofit.',new_capacitance_reports=len(spec['capacitances']),new_response_records=len(spec['responses']),new_own_main_tables=5,new_own_SI_tables=6,new_mixed_comparison_main_tables=1,new_foreign_comparison_main_tables=1,unreported_material_cells=unreported,new_batch12_purpose_rows=count('purpose_reviews_v12'),full_source_review_complete=0)
        audits=[]
        # Historical summaries count declared scopes cumulatively; distinct table keys are a different inventory metric.
        summary['reviewed_evidence_units']=old['reviewed_evidence_units']+len(spec['tables'])+len(spec['units'])
        summary['distinct_database_table_keys']=count('reviewed_tables')
        summary['database_extraction_units_v3']=count('extraction_units_v3')
        summary['reviewed_evidence_units_definition']='Historical cumulative declared scope units (268); distinct DB table keys254 and extraction_units_v3 237 are separate inventories, not experiments.'
        for sample,v,rho in[('CF-HPC-1',.21,1.41),('CF-HPC-2',.33,1.20),('CF-HPC-3',.23,1.37)]:ck('density_formula_rounding_'+sample,round(1/(v+.5),2)==rho);audits.append(dict(sample=sample,kind='author_density_formula',porevolume=v,assumed_true_density=2,computed_density=1/(v+.5),reported_density=rho,status='rounded_formula_not_measured_packing_density'))
        for sample,a,b,ratio in[('AC1',147,86,1.7),('AC2',88,56,1.6),('AC3',92,47,1.9),('AC4',114,31,3.6),('AC5',120,31,3.8)]:
            derived_lo=(a-.5)/(b+.5);derived_hi=(a+.5)/(b-.5);overlap=max(derived_lo,ratio-.05)<=min(derived_hi,ratio+.05);ck('Raman_printed_rounding_overlap_'+sample,overlap);audits.append(dict(sample=sample,kind='printed_area_and_ratio_rounding_envelopes',printed_D_area=a,printed_G_area=b,reported_ratio=ratio,exact_division=a/b,derived_rounding_interval=[derived_lo,derived_hi],reported_rounding_interval=[ratio-.05,ratio+.05],status='rounding_envelopes_overlap_not_a_new_measurement_or_errorbar'))
    with open_literature_database(DB,digest)as d,oldapi(PARENT,PSHA)as old:
        for p in['3e','2e_device','native_mineral_3e','2e_author_factor2']:
            before=old.auxiliary_feature_rows(p);after=d.auxiliary_feature_rows(p);ids={x['observation_id']for x in before};ck('old_aux_exact_'+p,[r for r in after if r['observation_id']in ids]==before)
        cy=[r for r in d.auxiliary_feature_rows('3e')if r['doi']==CY];ck('one_mass_Cg291',len(cy)==1 and cy[0]['capacitance_F_g']==291 and cy[0]['XPS_N_at_pct']is None and cy[0]['XPS_O_at_pct']is None)
        expected=dict(zip(TARGETS12,[1,10,10,4,4]))
        for target in TARGETS12:
            rows=d.batch12_inputs(target);ck('separate_target_count_'+target,len(rows)==expected[target]);matrix=d.batch12_matrix(target);ck('separate_target_masks_'+target,all(mask==(value is None)for row,masks in zip(matrix['X'],matrix['missing_mask'])for value,mask in zip(row,masks)));ck('family_weight_'+target,abs(sum(matrix['sample_weight'])-1)<1e-12)
            ck('no_outcomes_as_features_'+target,all(not any(z in f.lower()for z in['retention','energy_density','EIS_'.lower()])for r in rows for f in r['material_features']))
            ck('no_conflicted_AC5_overlap_'+target,all(not(r['sample_name']=='AC5'and r['electrolyte']=='KOH'and r['current_A_g']==.5)for r in rows))
            ck('whole_source_quarantine_'+target,all('doi:'+r['doi']in d.quarantine_source_groups([r['source_family_group']])for r in rows))
        rows=d.batch12_inputs('3e_volume');ck('volume_not_mass_or_measured_density',rows[0]['target_value']==349.1 and rows[0]['target_unit']=='F/cm3'and not any('density'in f for f in rows[0]['material_features']))
        co=d.batch12_inputs('2e_aqueous_Cs');a=next(r for r in co if r['sample_name']=='AC1');ck('integrated_not_peak_ratio',a['material_features']['Raman_integrated_area_ID_IG']==1.7 and 'Raman_ID_IG'not in a['material_features']);ck('DFT_zero_only_own_field',a['material_features']['DFT_area_in_pores_unspecified_class_m2_g']==0 and 'micropore_surface_area_m2_g'not in a['material_features'])
        ck('plusminus_channels_not_SDs',a['material_features']['BET_surface_area_m2_g']==539 and a['material_features']['BET_surface_area_m2_g_author_plusminus']==16)
        ionic=d.batch12_inputs('2e_ionic_Cs');ck('ionic_not_assumed_molarity',all(r['concentration_mol_L']is None for r in ionic));ck('GCD216_not_CV219',next(r for r in ionic if r['conditions']['separator'].startswith('ozone'))['value']==216.6)
        ck('acid_actual0_to_point9',all(r['conditions']['voltage_upper_V']==.9 for r in co if r['electrolyte']=='H2SO4'))
        ck('IL_unlisted_recipe_not_guessed',all(r['conditions']['carbon_wt_pct']is None for r in ionic if r['conditions']['current_collector']in['FTO','Ti']))
        ck('current_in_matrix_not_discarded',d.batch12_matrix('2e_aqueous_Cs')['feature_names'][-4]=='reported_current_A_g')
        ck('parent128curves',d.sampled_curves()==old.sampled_curves());ck('parent15freezes',d.legacy_feature_conflicts()==old.legacy_feature_conflicts());ck('parentfamilyrelation',d.source_relations()==old.source_relations());ck('old_composite',d.composite_cycle_inputs()==old.composite_cycle_inputs());ck('old_DES',all(d.des_reported_inputs(t)==old.des_reported_inputs(t)for t in['retention','capacitance']))
        ck('no_CF_identity_propagation',not d.facts(doi=CY,sample='CF-0',field='XPS_N_at_pct'))
        ck('specific_cycles_3_not_admissions',len([r for r in d.tests()if r['candidate_id'].startswith('LP12_')])==3)
    ck('read_only_hash',sha(DB)==digest);report=dict(status='passed',database_sha256=digest,check_count=len(checks),checks=checks,model_fits=0,formal_cycling_admissions=0,scientific_goal_complete=False)
    if prepare:
        assert not(OUT/'merge_manifest.json').exists();write(OUT/'summary.json',summary);write(OUT/'verification.json',report);write(OUT/'quantity_audits.json',audits)
    else:
        for name,value in [('summary',summary),('verification',report),('quantity_audits',audits)]:assert json.loads((OUT/(name+'.json')).read_text('utf8'))==value
        if(OUT/'merge_manifest.json').exists():
            for p in json.loads((OUT/'merge_manifest.json').read_text('utf8'))['outputs']:assert sha(ROOT/p['path'])==p['sha256']
    print(json.dumps(dict(checks=len(checks),summary=summary),ensure_ascii=False))

def seal():
    assert not(OUT/'merge_manifest.json').exists();verify(False)
    from verify_corpus_chain_v12 import run
    run(False)
    paths=[p for p in OUT.rglob('*')if p.is_file()]+[ROOT/'tools/extract_porous_series_v12.py',ROOT/'tools/verify_corpus_chain_v12.py',ROOT/'data/literature_v12.py']
    write(OUT/'merge_manifest.json',dict(version='literature_pool_v12',parent_sha256=PSHA,outputs=[dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p),bytes=p.stat().st_size)for p in sorted(paths)],model_fits=0,scientific_goal_complete=False))
    write(ROOT/'data/current_literature.json',dict(version='literature_pool_v12',directory=OUT.relative_to(ROOT).as_posix(),database_file=DB.name,sha256=sha(DB),api_module='data.literature_v12',scope='Cycas/coconut specificown tables/SI, separatevolume/Cs/Cd tasks; fourfurtherselectedpapers stillqueued; nofit'))

if __name__=='__main__':
    if len(sys.argv)!=2 or sys.argv[1]not in['curate','build','prepare','verify','seal']:raise SystemExit('curate/build/prepare/seal once; verify read-only')
    if sys.argv[1]=='prepare':verify(True)
    else:globals()[sys.argv[1]]()
