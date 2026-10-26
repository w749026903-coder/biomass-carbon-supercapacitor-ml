"""One-use v17 curation/build. Additive own-source extraction; no fitting.

Do not rerun against a sealed batch. Native tables keep original grids, PDF
transcriptions retain page locators, and every extracted scalar has a cell.
"""
from pathlib import Path
from contextlib import closing
import json,re,sqlite3,sys,xml.etree.ElementTree as E
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tools'))
from extract_onion_composite_v8 import sha,write,ro,insert,mk
from extract_palm_kernel_v7 import xml_grid
from extract_source_series_v13 import clean
OUT=ROOT/'文献全量利用复核_20261027/批次17_多来源全样表格与方法审查'
DB=OUT/'literature_material_pool_v17.sqlite'
PARENT=ROOT/'文献全量利用复核_20261027/批次16_花椒全样倍率与椰枣叶工况/literature_material_pool_v16.sqlite'
PSHA='a82b0e4abfceca2fdfd9c096e0c724851b69d0110b7a22c351b823e2cbd46351'
EX='10.1002/cssc.202200651';NPC='10.3390/molecules29112532';HC='10.3390/polym15234478';RH='10.1021/acsomega.2c07932';MIX='10.3390/nano14161368'
KEYS={EX:'Extrusion17',NPC:'Starch17',HC:'Cellulose17',RH:'Rice17',MIX:'Mixed17'}
def norm(s):return re.sub(r'\[[a-z]\]$','',s.translate(str.maketrans({'‐':'-','–':'-','−':'-'})))
def number(raw):
    if raw in ['','-','—']:return None
    assert re.fullmatch(r'[+-]?(?:\d+(?:\.\d+)?|\.\d+)',raw),raw
    return float(raw)

def curate():
    assert sha(PARENT)==PSHA and not DB.exists()and not(OUT/'curation_spec.json').exists()and not(OUT/'merge_manifest.json').exists()
    notes=json.loads((OUT/'source_review_notes.json').read_text('utf8'))
    spec={k:[]for k in ['sources','documents','tables','units','materials','facts','caps','responses','synthesis','decisions','feature_decisions','figures','candidates','annotations','identity_links']}
    roots={};tabs={};names={};paths={s['doi']:ROOT/s['path']for s in notes['sources']}
    def doc(key,doi,path,role):
        assert path.is_file(),path
        spec['documents'].append(dict(key=key,doi=doi,path=path.relative_to(ROOT).as_posix(),sha256=sha(path),role=role))
    with closing(ro(ROOT/'全库复检与特征补提取_20261021/full_corpus_search_native.sqlite'))as native:
        for src in notes['sources']:
            doi=src['doi'];path=paths[doi];assert sha(path)==src['sha256'];root=E.parse(path).getroot();roots[doi]=root
            assert {x.text.lower()for x in root.findall('./front/article-meta/article-id')if x.get('pub-id-type')=='doi'}=={doi}
            ids=list(native.execute('select identity_key,role,basis from identity_sources where sha256=?',(src['sha256'],)))
            assert {r[0]for r in ids}=={'doi:'+doi}
            years={int(x.text)for x in root.findall('./front/article-meta/pub-date/year')};assert len(years)==1,years
            spec['sources'].append(dict(src,title=clean(root.find('.//article-title')),year=years.pop(),identity_roles=ids,classification='original_biomass_research'))
            doc(KEYS[doi],doi,path,'primary_XML')
            raw={r[1]:r[0]for r in native.execute('select table_id,locator from raw_tables_v11 where source_sha256=?',(src['sha256'],))}
            for t in root.findall('.//table-wrap'):
                locator='XML table-wrap '+t.get('id');grid=xml_grid(t)
                item=dict(doi=doi,id=t.get('id'),document=KEYS[doi],locator=locator,caption=clean(t.find('caption')),footnote=clean(t.find('table-wrap-foot')),grid=grid,raw_table_id=raw[locator],kind='own_original_XML_table_with_foreign_rows_retained_but_not_admitted')
                spec['tables'].append(item);tabs[(doi,t.get('id'))]=[[v['raw']for v in rr]for rr in grid]
            for i,f in enumerate(root.findall('.//fig'),1):
                href=f.find('.//graphic').get('{http://www.w3.org/1999/xlink}href')
                folder=OUT/'evidence'/KEYS[doi]if doi in [EX,MIX]else path.parent/('figures'if doi==HC else'assets')
                candidate=list(folder.glob(href.split('/')[-1]+'.*'))
                if not candidate:candidate=list(folder.glob(href.split('/')[-1]))
                assert len(candidate)==1,(doi,href,candidate)
                key=KEYS[doi]+'_Fig'+str(i);doc(key,doi,candidate[0],'original_main_figure')
                spec['figures'].append(dict(doi=doi,figure_number=i,document=key,caption=clean(f.find('caption')),scope_visually_inspected=True,full_waveform_extracted=False,remaining='Continuous waveforms, morphology distributions and untranscribed rate markers remain; scope inspection is not full quantitative extraction'))
    def unit(doi,id,header,rows,locator,document=None,kind='own_bound_prose_transcription'):
        spec['units'].append(dict(doi=doi,id=id,header=header,rows=[[str(v)for v in row]for row in rows],locator=locator,document=document or KEYS[doi],kind=kind));return id
    def fact(doi,s,id,row,col,field,un,method,status='own_reported_method_qualified'):
        spec['facts'].append(dict(doi=doi,sample=s,id=id,row=row,col=col,field=field,unit=un,method=method,status=status))
    def cap(doi,s,id,row,col,j,purpose=None,**cond):spec['caps'].append(dict(doi=doi,sample=s,id=id,row=row,col=col,j=j,purpose=purpose,conditions=cond))
    def response(doi,s,id,row,col,metric,un,**cond):spec['responses'].append(dict(doi=doi,sample=s,id=id,row=row,col=col,metric=metric,unit=un,conditions=cond))
    def feature_choice(doi,s,field,value,reason):spec['feature_decisions'].append(dict(doi=doi,sample=s,field=field,selected_value=value,reason=reason,not_author_erratum=True))
    def register(doi,s,stage,feedstock):
        spec['materials'].append(dict(doi=doi,sample=s,stage=stage,feedstock=feedstock));names.setdefault(doi,[]).append(s)
    # Extruded lignin/wood: full 21 final sample table plus two pre-wash stages.
    xt='cssc202200651-tbl-0001';exrows=tabs[(EX,xt)][1:]
    for row,rr in enumerate(exrows,2):
        s=norm(rr[1]);register(EX,s,'final_biomass_carbon_before_test','wood_waste'if s=='WUK'else'lignin')
        for col,field,un in [(2,'extrusion_screw_speed_rpm','rpm'),(3,'extrusion_barrel_temperature_C','degC'),(4,'extrusion_feed_rate_g_min','g/min'),(5,'author_carbon_efficiency_pct','%carbon_to_lignin_plus_Nsource_mass'),(6,'XPS_C_to_N_atomic_ratio','ratio'),(7,'BET_surface_area_m2_g','m2/g')]:
            status='table_default_not_applicable_to_ball_mill'if s=='LUK-BM'and col in [2,3,4]else'conflict_main_vs_SI_N2BET'if s=='LMK-1'and col==7 else'own_reported_method_qualified'
            fact(EX,s,xt,row,col,field,un,'Own mainTable1; Ceff excludes carbonate; C/N from XPS; N2 BET; BM defaults not actual processing conditions',status)
    final_ex=list(names[EX]);register(EX,'LUK-4 polymer','polymer_precursor','lignin');register(EX,'LUK-4 crude','unwashed_carbon_composite','lignin')
    si=OUT/'evidence/Extrusion17/CSSC-15-0-s001.pdf';doc('Extrusion17_SI',EX,si,'original_SI_PDF')
    # PDF rows transcribed against original rendered pages; SI typography retained.
    s1=unit(EX,'SI_S1',['Entry','Sample','rpm','barrel_C','feed_g_min','Ceff','CN','BET'],[[i,norm(r[1]),*r[2:]]for i,r in enumerate(exrows[:12],1)],'SI PDF p3 TableS1; same 12 final samples as main, not independent','Extrusion17_SI','own_SI_table')
    s2=unit(EX,'SI_S2',['Entry','Sample','barrel_C','Ceff','CN','BET'],[[i,norm(r[1]),r[3],*r[5:]]for i,r in enumerate(exrows[12:17],1)],'SI PDF p3 TableS2; LBK explicitly biuret','Extrusion17_SI','own_SI_table')
    s3rows=[[i,s,feature,*r[5:]]for i,(s,feature,r)in enumerate(zip(['LUK-4','LUK-BM','LUK-CS','LK','WUK'],['-','Ball mill','Conveying screws','Without Urea','Alternative feedstock'],[exrows[k]for k in [3,17,18,19,20]]),1)]
    s3=unit(EX,'SI_S3',['Entry','Sample','Unique feature','Ceff','CN','BET'],s3rows,'SI PDF p3 TableS3; BM and conveying/withouturea/wood controls','Extrusion17_SI','own_SI_table')
    for uid,rows,cols in [(s1,spec['units'][-3]['rows'],[(5,'author_carbon_efficiency_pct','%'),(6,'XPS_C_to_N_atomic_ratio','ratio'),(7,'BET_surface_area_m2_g','m2/g')]),(s2,spec['units'][-2]['rows'],[(3,'author_carbon_efficiency_pct','%'),(4,'XPS_C_to_N_atomic_ratio','ratio'),(5,'BET_surface_area_m2_g','m2/g')]),(s3,s3rows,[(3,'author_carbon_efficiency_pct','%'),(4,'XPS_C_to_N_atomic_ratio','ratio'),(5,'BET_surface_area_m2_g','m2/g')])]:
        for row,rr in enumerate(rows,1):
            for col,field,un in cols:fact(EX,rr[1],uid,row,col,field,un,'Own SI repeat, not another material/test','conflict_main_vs_SI_N2BET'if rr[1]=='LMK-1'and field=='BET_surface_area_m2_g'else'own_repeat_report')
    xtext='''LUK-1 93.86 2.29 3.85 - - -
LUK-2 95.29 1.04 3.67 - - -
LUK-3 84.59 5.64 9.77 - - -
LUK-4 89.72 2.76 7.52 - - -
LUK-5 91.12 1.26 7.62 - - -
LUK-6 88.17 1.64 10.19 - - -
LUK-7 88.26 2.34 9.4 - - -
LUK-8 89.36 2.52 8.12 - - -
LUK-9 87.79 1.15 11.05 - - -
LUK-10 86.48 1.22 12.3 - - -
LUK-11 88.51 2.34 9.15 - - -
LUK-12 88.24 5.11 6.65 - - -
LUK-4_polymer 51.08 13.76 26.01 7.63 0.75 0.76
LUK-4_crude 23.97 0.99 46.91 20.92 5.80 1.41
LMK-1 88.87 5.23 5.9 - - -
LMK-2 89.84 4.52 5.64 - - -
LMK-3 90.81 5.25 3.95 - - -
LBK-1 93.77 1.66 4.56 - - -
LBK-2 93.89 0.66 5.45 - - -
LUK-BM 87.51 5.78 6.71 - - -
LUK-CS 89.53 1.29 9.19 - - -
LK 92.98 0.66 6.36 - - -
WUK 88.93 3.07 7.98 - - -'''
    xr=[line.split()for line in xtext.splitlines()];xr=[[r[0].replace('_',' '),*r[1:]]for r in xr]
    u=unit(EX,'SI_S4',['Sample','C','N','O','K','Na','S'],xr,'SI PDF p11 TableS4 XPS at%; K/Na/S dash=not detected, limit unknown; etch state not row-bound','Extrusion17_SI','own_SI_table')
    for row,rr in enumerate(xr,1):
        for col,e in enumerate(['C','N','O','K','Na','S'],1):fact(EX,rr[0],u,row,col,'XPS_'+e+'_at_pct','at%','SI S4; surface not bulk; polymer/crude separate; method includes before/after etch but table etch state unspecified','not_detected_limit_unreported'if rr[col]=='-'else'own_reported_method_qualified')
    u=unit(EX,'SI_S5',['Sample','BET_Ar','V_Ar'],[['LUK-4','1955','1.121']],'SI PDF p23 TableS5, Ar86.7K, distinct from N2','Extrusion17_SI','own_SI_table')
    fact(EX,'LUK-4',u,1,1,'Ar_BET_surface_area_m2_g','m2/g','Ar86.7K');fact(EX,'LUK-4',u,1,2,'Ar_total_pore_volume_cm3_g','cm3/g','Ar86.7K')
    vols='2.598 1.956 1.258 1.783 1.389 1.427 1.564 1.389 1.607 1.459 1.954 2.122 2.005 2.201 2.298 2.468 1.33 1.861 1.189 0.2602 1.295'.split()
    rows=[[s,'3037'if s=='LMK-1'else exrows[i][7],v]for i,(s,v)in enumerate(zip(final_ex,vols))]
    u=unit(EX,'SI_S6',['Sample','BET_N2','V_N2'],rows,'SI PDF p28 TableS6; caption PAA/PI erroneous but all actual row IDs LUK/LMK/LBK; LMK1 conflicts with main/S2','Extrusion17_SI','own_SI_table')
    for row,rr in enumerate(rows,1):
        fact(EX,rr[0],u,row,1,'BET_surface_area_m2_g','m2/g','N2 BET','conflict_main_vs_SI_N2BET'if rr[0]=='LMK-1'else'own_reported_method_qualified');fact(EX,rr[0],u,row,2,'total_pore_volume_cm3_g','cm3/g','N2 own total pore volume')
    sty='''42905 16203 1657
44569 14455 3070
33824 9269 3517
30029 10353 3941
40510 11869 6277
34300 12289 3767
38281 12176 4404
42427 18917 6270
45272 14619 4737
50105 19710 8614
60506 18811 7554
145977 42496 2965
31397 12429 1156
29871 11715 1245
30519 12954 1943
24271 9385 1507
17061 8265 2411
10746 3968 556
66810 22103 8184
42317 23027 8971
41567 9225 3551'''
    rows=[[s,*line.split()]for s,line in zip(final_ex,sty.splitlines())];u=unit(EX,'SI_S7',['Sample','STY_polymer','STY_composite','STY_carbon'],rows,'SI PDF p35 TableS7 calculated STY; extrusion as limiting step','Extrusion17_SI','own_SI_table')
    for row,rr in enumerate(rows,1):
        for col,stage in enumerate(['polymer','composite','carbon'],1):response(EX,rr[0],u,row,col,'author_space_time_yield_'+stage,'kg/m3/day',derived_by_author=True,not_capacitance_predictor=True)
    u=unit(EX,'SI_S8',['Entry','Source','Carbon','Electrolyte','Cs'],[[1,'Our work','NC from lignin','1M TEABF4/AcN','101'],[2,'[1]','NC from lignin','1M TEABF4/AcN','147'],[3,'[1]','YP-80F','1M TEABF4/AcN','112'],[4,'[2]','AC-W800','1M TEABF4/AcN','236'],[5,'[3]','Mesoporous-CDC','1M TEABF4/AcN','170'],[6,'[4]','MCNAs','1M TEABF4/AcN','152'],[7,'[5]','1700-VAC','1M TEABF4/AcN','20'],[8,'[6]','MWCNT','1.5M TEABF4/AcN','18']],'SI PDF p36 TableS8 own first row only, sample linked by own mainP190; not SI S54 BM','Extrusion17_SI','SI_comparison_own_first_row_only')
    excond=dict(system='2E_symmetric',electrolyte='TEABF4/AcN',concentration_mol_L=1,voltage_lower_V=0,voltage_upper_V=2.5,reference_electrode=None,capacitance_basis='author_symmetric_factor4_total_active_carbon_equivalent',target_stage='fresh_reported_GCD_rate_test')
    cap(EX,'LUK-4',u,1,4,1,**excond,report_kind='SI_same_report_repeat')
    u=unit(EX,'body_own_cap',['sample','Cs','j'],[['LUK-4','101','1'],['LUK-4','76','']],'bodyP190 specific101@1 and conclusionP19476 at unbound current; retain both')
    cap(EX,'LUK-4',u,1,1,1,purpose='reported_organic_2e_factor4_Cs',**excond,physical_test_group='doi:'+EX+':LUK-4:2E:GCD:j1')
    cap(EX,'LUK-4',u,2,1,None,**excond,report_kind='conclusion_unbound_current_dissent')
    for rr,s in zip(exrows,final_ex):
        nitrogen='melamine'if s.startswith('LMK')else'biuret'if s.startswith('LBK')else None if s=='LK'else'urea'
        spec['synthesis'].append(dict(doi=EX,sample=s,document=KEYS[EX],locator='bodyP189/P195-P201, ownTable1/SI S3; extrusion and pyrolysis separate',stages=[dict(stage='mechanochemical_precursor',method='ball_milling'if s=='LUK-BM'else'extrusion_conveying_only'if s=='LUK-CS'else'extrusion',screw_speed_rpm=None if s=='LUK-BM'else float(rr[2]),barrel_temperature_C=None if s=='LUK-BM'else float(rr[3]),feed_rate_g_min=None if s=='LUK-BM'else float(rr[4]),nitrogen_source=nitrogen,carbon_Nsource_K2CO3_mass_parts=[1,0 if s=='LK'else 1,1],LBK_biotin_wording_dissent=s.startswith('LBK')),dict(stage='thermal_prehold',temperature_C=60,duration_h=1,heating_rate_C_min=2.5,rate_converted_from_C_per_h=150),dict(stage='single_carbonization_activation',temperature_C=800,duration_h=2,atmosphere='N2',heating_rate_C_min=2.5,agent='K2CO3',carbon_to_activator_mass_ratio=[1,1],rate_converted_from_C_per_h=150),dict(stage='postwash',sample_g=.5,half_concentrated_HCl_mL=400,water_wash_to_neutral=True,drying_C=80,drying_h=None),dict(stage='electrode_preparation',PTFE_wt_pct=5,active_carbon_mass_mg=None,film_thickness_um_range=[150,200],disc_diameter_mm=10,drying_C=80,drying_h=24,vacuum=True,collector='TiO2_with_carbon_coating',separator='Whatman_GF/D',separator_diameter_mm=12)]))
    # Starch: all ten own final samples, no foreign comparison labels.
    nt='molecules-29-02532-t001';nrows=tabs[(NPC,nt)][2:]
    for row,rr in enumerate(nrows,3):
        s=rr[0];register(NPC,s,'final_biomass_carbon_before_test','starch')
        for col,f,un in [(1,'BET_surface_area_m2_g','m2/g'),(2,'micropore_surface_area_m2_g','m2/g'),(3,'total_pore_volume_cm3_g','cm3/g'),(4,'micropore_volume_cm3_g','cm3/g'),(5,'mean_pore_diameter_reported_nm','nm')]:fact(NPC,s,nt,row,col,f,un,'OwnTable1; N277K/BET, VtotalP.99, DFT slit PSD; Daver printed nm under nested volume header')
        parts=s.split('-');t=700 if s=='CS-700'else int(parts[1]);ur=0 if s=='CS-700'else float(parts[2]);zn=0 if s=='CS-700'else float(parts[3])
        spec['synthesis'].append(dict(doi=NPC,sample=s,document=KEYS[NPC],locator='bodyP15-P17 and sample definitions, CS700 explicit starch-alone control',stages=[dict(stage='hydrothermal',temperature_C=150,duration_h=12,starch_g=2,urea_g=ur,ZnCl2_g=zn,water_mL=50,reactor_mL=100,stirring_h=1),dict(stage='single_carbonization_activation',temperature_C=t,duration_h=1,heating_rate_C_min=5,atmosphere='N2',agent=None if s=='CS-700'else'ZnCl2',starch_to_activator_mass_ratio=[2,zn],washing_acid_ultrasound=True,water_wash_to_neutral_and_no_chloride=True),dict(stage='electrode_preparation',carbon_acetylene_PTFE_mass_parts=[8,1,1],working_mass_mg_range=[2.5,4],working_mass_mg=None,collector='Ni_foam',press_MPa=10,press_min=1,NMP=True)]))
    best='NPC-700-2-2';u=unit(NPC,'own_prose_BET',['sample','BET'],[[best,'1498.4']],'abstract/bodyP3 extra precision vsTable1 integer1498')
    fact(NPC,best,u,1,1,'BET_surface_area_m2_g','m2/g','Author extra precision, not a new measurement');feature_choice(NPC,best,'BET_surface_area_m2_g',1498.4,'1498 integer Table1 and1498.4 abstract compatible at integer precision; explicit higher author precision retained')
    u=unit(NPC,'Fig3_Raman',['sample','IDIG'],[[r[0],v]for r,v in zip(nrows,['1.140','1.091','1.039','1.044','1.067','1.028','1.048','1.134','1.070','1.127'])],'ActualFig3a-i printed Raman ratios, repeated panels not new values','Starch17_Fig3','own_printed_figure_annotations')
    for row,r in enumerate(nrows,1):fact(NPC,r[0],u,row,1,'Raman_ID_IG','ratio','Own printed ratios; peak fit definition retained, no conversion from IG/ID')
    u=unit(NPC,'Fig3_XPS',['sample','C','N','O'],[[best,'87.7','7.37','4.93']],'ActualFig3k printed survey pie at%, only best sample','Starch17_Fig3','own_printed_figure_annotations')
    for col,e in enumerate(['C','N','O'],1):fact(NPC,best,u,1,col,'XPS_'+e+'_at_pct','at%','Printed XPS survey, not inferred C complement')
    ncond=dict(system='3E',electrolyte='KOH',concentration_mol_L=6,voltage_lower_V=-1,voltage_upper_V=0,reference_electrode='Hg/HgO',capacitance_basis='author_reported_3E',target_stage='fresh_reported_GCD_rate_test')
    u=unit(NPC,'own_cap',['sample','C','j'],[[best,'249.7','1']],'Ownbody/Table2 lastrow own best; actualFig5 3E GCD andP17 protocol')
    cap(NPC,best,u,1,1,1,purpose='reported_aqueous_3e_GCD_capacitance',**ncond,physical_test_group='doi:'+NPC+':'+best+':3E:GCD:j1')
    u=unit(NPC,'Fig7_EDLC',['sample','scan','EDLC','pseudo'],[[best,j,e,p]for j,e,p in zip([5,10,20,50,100,200],['48.4','56.8','65.1','78.2','94.3','100'],['51.6','43.2','34.9','21.8','5.7','0'])],'ActualFig7e printed contributions, not new material predictors','Starch17_Fig7','own_printed_figure_annotations')
    for row,j in enumerate([5,10,20,50,100,200],1):
        response(NPC,best,u,row,2,'author_EDLC_contribution','%',scan_rate_mV_s=j);response(NPC,best,u,row,3,'author_pseudocapacitance_contribution','%',scan_rate_mV_s=j)
    u=unit(NPC,'body_EDLC_dissent',['sample','EDLC'],[[best,'58.6']],'bodyP13 EDLC at10mVs differs from actualFig7e56.8; original preserved');response(NPC,best,u,1,1,'author_EDLC_contribution_dissent','%',scan_rate_mV_s=10)
    u=unit(NPC,'own_EIS',['sample','Rs','tau'],[[best,'.63','.56']],'bodyP12 best Rs and characteristic relaxation time, response not pretest predictor')
    response(NPC,best,u,1,1,'EIS_Rs','ohm');response(NPC,best,u,1,2,'Bode_relaxation_time','s')
    u=unit(NPC,'Fig7_cycle',['sample','electrolyte','retention','CE'],[[best,'1M_TEABF4_AN','83.3','83.3'],[best,'6M_KOH','90.3','99.3']],'ActualFig7g/h own labels; stated2E but SCE/signedKOHwindow inconsistent; candidate only','Starch17_Fig7','own_printed_figure_annotations')
    for row,e in enumerate(['TEABF4/AN','KOH'],1):
        for col,metric in [(2,'cycling_retention'),(3,'coulombic_efficiency')]:response(NPC,best,u,row,col,metric,'%',cycle_count=10000,reported_current_A_g=2,system='author_2E_with_configuration_window_dispute',electrolyte=e)
        spec['candidates'].append(dict(candidate_id='LP17_NPC_'+str(row),doi=NPC,sample=best,record=dict(system='author_2E_disputed',method='GCD',cycle_count=10000,retention_pct=[83.3,90.3][row-1],reported_current_A_g=2,electrolyte=e,concentration_mol_L=[1,6][row-1],cycle_voltage_lower_V=None,cycle_voltage_upper_V=None,reason='Fig7g/h axes/insets say vsSCE; KOH signed-1..0 despite2E claim; physical configuration/window unresolved',purpose_reviewed_candidate_ready=False)))
    # Cellulose stages; EA wt% distinct from XPS explicitly wt%.
    ht='polymers-15-04478-t001'
    for row,rr in enumerate(tabs[(HC,ht)][1:],2):
        s=rr[0];stage='raw_feedstock'if s=='CL'else'hydrochar_intermediate'if s.startswith('HC-')else'final_biomass_carbon_before_test';register(HC,s,stage,'cellulose')
        for col,e in enumerate(['C','H','N','S','O'],1):fact(HC,s,ht,row,col,'bulk_EA_'+e+'_wt_pct','wt%','OwnTable1 EA, stage-specific, no sum-to100 correction')
        for col,e in [(6,'H_C'),(7,'O_C')]:fact(HC,s,ht,row,col,'bulk_EA_'+e+'_mass_ratio','mass_ratio','Numerically mass percentages ratio; not atomic ratio')
    ht2='polymers-15-04478-t002'
    for row,rr in enumerate(tabs[(HC,ht2)][1:],2):
        for col,e in enumerate(['C','N','S','O','B'],1):fact(HC,rr[0],ht2,row,col,'XPS_'+e+'_wt_pct','wt%','Own Table2 explicitly wt%; not atomic percent','unreported_blank'if not rr[col]else'own_reported_method_qualified')
    u=unit(HC,'body_EA_dissent',['sample','C','S'],[['HC-CL','71.14',''],['HC-CL-TU','','4.54']],'bodyP17 C71.14 vsTable70.14; S4.54 assignedTU inprose vsTableTU2.92, not silently reassigned')
    fact(HC,'HC-CL',u,1,1,'bulk_EA_C_wt_pct','wt%','OwnbodyP17 competing claim','conflict_body_vs_table');fact(HC,'HC-CL-TU',u,2,2,'bulk_EA_S_wt_pct','wt%','OwnbodyP17 competing assignment','conflict_body_vs_table')
    feature_choice(HC,'HC-CL','bulk_EA_C_wt_pct',70.14,'Specific own stage-labelled Table1 vs prose incompatible claim; working table value, dissent retained')
    feature_choice(HC,'HC-CL-TU','bulk_EA_S_wt_pct',2.92,'Specific stage/sample-labelled Table1;4.54 is another row but prose kept as written, no fabricated erratum')
    hfinal=['AHC-CL','AHC-CL-AS','AHC-CL-TU','AHC-CL-AS-BA','AHC-CL-TU-BA']
    hvals=[['369.75','207.87'],['829.59','712.66'],['952.27','694.69'],['484.75','418.98'],['397.59','304.81']]
    u=unit(HC,'Fig3_textures',['sample','BET','Smicro'],[[s,*v]for s,v in zip(hfinal,hvals)],'ActualFig3c printed allfive BET/micropore areas, includingcontrolAHC_CL','Cellulose17_Fig3','own_printed_figure_annotations')
    for row,s in enumerate(hfinal,1):
        fact(HC,s,u,row,1,'BET_surface_area_m2_g','m2/g','ActualFig3c printed ownsample label');fact(HC,s,u,row,2,'micropore_surface_area_m2_g','m2/g','ActualFig3c own printedmicropore area')
    u=unit(HC,'body_ASBA_texture',['sample','BET','Smicro'],[['AHC-CL-AS-BA','484.76','418.99']],'bodyP23 lastdigit alternatives to Fig3c484.75/418.98')
    for col,f,value in [(1,'BET_surface_area_m2_g',484.75),(2,'micropore_surface_area_m2_g',418.98)]:fact(HC,'AHC-CL-AS-BA',u,1,col,f,'m2/g','OwnbodyP23 alternative lastdigit');feature_choice(HC,'AHC-CL-AS-BA',f,value,'Working specific printed Fig3c; body last-digit difference retained; not an additional material or inferred precision')
    hcond=dict(system='3E',electrolyte='KOH',concentration_mol_L=6,voltage_lower_V=-1,voltage_upper_V=0,reference_electrode='Hg/HgO',capacitance_basis='author_reported_3E',target_stage='fresh_reported_GCD_rate_test')
    four=hfinal[1:];u=unit(HC,'Fig7_cap',['sample','C','j'],[[s,c,'1']for s,c in zip(four,['215.9','235.8','218.8','204.3'])]+[['AHC-CL-TU','172.0','20']],'ActualFig7b labels and bodyP32 specific GCD enumeration; TU20AgP32','Cellulose17_Fig7','own_figure_bound_prose')
    for row,rr in enumerate(spec['units'][-1]['rows'],1):cap(HC,rr[0],u,row,1,float(rr[2]),purpose='reported_aqueous_3e_GCD_capacitance',**hcond,physical_test_group='doi:'+HC+':'+rr[0]+':3E:GCD:j'+rr[2])
    u=unit(HC,'body_cap_dissent',['sample','C','j'],[[s,c,'1']for s,c in zip(four,['216.4','236.25','219.3','205.8'])]+[['AHC-CL-TU','236.25','1']],'ConclusionP36 andbodyP29 alternatives, not new independent GCD conditions')
    for row,rr in enumerate(spec['units'][-1]['rows'],1):cap(HC,rr[0],u,row,1,1,**hcond,report_kind='competing_body_or_conclusion',physical_test_group='doi:'+HC+':'+rr[0]+':3E:GCD:j1')
    h2=dict(system='2E_symmetric',electrolyte='KOH',concentration_mol_L=6,voltage_lower_V=None,voltage_upper_V=None,reference_electrode=None,capacitance_basis='author_symmetric_factor2_with_m_as_written',target_stage='fresh_reported_GCD_rate_test',voltage_status='not_explicitly_bound_no_reverse_calculation_from_Ragone',reference_wording_dissent='Formula definition says vsHgHgO despite2Econfiguration')
    u=unit(HC,'own_2E_cap',['sample','C','j'],[[s,c,'1']for s,c in zip(four,['208.8','224.0','210.6','193.2'])],'bodyP33 Fig8a authorCs=2I dt/(m dV), separated from deviceCd')
    for row,s in enumerate(four,1):cap(HC,s,u,row,1,1,purpose='reported_aqueous_2e_factor2_Cs',**h2,physical_test_group='doi:'+HC+':'+s+':2E:GCD:j1')
    u=unit(HC,'own_cycle',['sample','retention'],[['AHC-CL-TU','99.96']],'OwnFig7c/P32/Table3 consistent3E20000@10Ag; already candidateTE011, not a new endpoint')
    response(HC,'AHC-CL-TU',u,1,1,'cycling_retention','%',system='3E',cycle_count=20000,reported_current_A_g=10,existing_endpoint_id='candidate:TE011')
    spec['identity_links'].append(dict(doi=HC,sample='AHC-CL-TU',existing_endpoint_id='candidate:TE011',relationship='same_paper_sample_3E20000_10Ag99.96',formal_admission_changed=False))
    for s in names[HC]:
        if s=='CL':continue
        add='thiourea'if'-TU'in s else'ammonium_sulfate'if'-AS'in s else None
        stages=[dict(stage='hydrothermal',temperature_C=240,duration_h=1,cellulose_g=5,Nsource=add,Nsource_g=.5 if add else 0,boric_acid_g=.5 if s.endswith('-BA')else 0,water_mL=40,reactor_mL=100,heating_time_approx_min=30,heating_rate_C_min=None,drying_C=105,drying_h=12)]
        if s.startswith('AHC-'):stages.extend([dict(stage='KOH_impregnation',carbon_g=.5,KOH_g=1.5,water_mL=200,ultrasound_min=20,soak_h=24,drying_C=105,drying_h=12),dict(stage='chemical_activation',temperature_C=800,duration_h=1,heating_rate_C_min=10,atmosphere='Ar',gas_flow_mL_min=20,agent='KOH',carbon_to_activator_mass_ratio=[1,3],water_wash_to_neutral=True,drying_C=105,drying_h=12),dict(stage='electrode_preparation',carbon_acetylene_PTFE_mass_parts=[16,3,1],working_active_mass_mg=None,carbon_flake_diameter_mm=10,Ni_foam_diameter_mm=15,ultrasound_W=120,ultrasound_min=20,drying_C=105,drying_h=5,press_sequence_MPa=[2,4])])
        spec['synthesis'].append(dict(doi=HC,sample=s,document=KEYS[HC],locator='bodyP10/P11/P14; stage-specific actual naming fromTables/Figures',stages=stages))
    # Rice: standard BET remains missing; printed surface-area dimensions retained.
    rt='tbl1'
    for row,rr in enumerate(tabs[(RH,rt)][1:],2):
        s=rr[0];register(RH,s,'final_washed_biomass_carbon_before_test'if s.startswith('RHPC')else'carbon_silica_intermediate','rice_husk')
        fact(RH,s,rt,row,1,'surface_area_as_printed_m3_g','m3/g_as_printed','OwnTable1/body repeatedlym3/g; dimensional conflict unresolved, not standardBET','conflict_surface_area_dimension')
        fact(RH,s,rt,row,2,'total_pore_volume_cm3_g','cm3/g','OwnTable1 N2');fact(RH,s,rt,row,3,'mean_pore_diameter_reported_nm','nm','OwnTable1 reported average adsorption diameter')
        t=int(s.split('-')[1]);stages=[dict(stage='feedstock_wash_dry',drying_C=100,drying_h=10),dict(stage='carbonization',temperature_C=t,duration_h=2,heating_rate_C_min=4,atmosphere='N2')]
        if s.startswith('RHPC'):stages.append(dict(stage='post_carbonization_deashing',HCl_wt_pct=10,HCl_duration_h=3,NaOH_M=2,NaOH_reflux_C=80,NaOH_duration_h=2,high_temperature_activation=False,water_wash_to_neutral=True))
        stages.append(dict(stage='electrode_preparation',carbon_g=.08,carbon_black_g=.015,PVDF_g=.005,NMP=True,collector='Ni_foam',collector_dimensions_cm=[1,2],drying_C=80,drying_h=None,working_active_mass_mg=None,slurry_mass_not_final_loading=True))
        spec['synthesis'].append(dict(doi=RH,sample=s,document=KEYS[RH],locator='bodyP4-P9 own thermal/removal/electrode methods',stages=stages))
    rcond=dict(system='3E',electrolyte='KOH',concentration_mol_L=6,voltage_lower_V=-.9,voltage_upper_V=.1,reference_electrode='Hg/HgO',capacitance_basis='author_reported_3E',target_stage='fresh_reported_GCD_rate_test',BET_dimension_disputed_optional_feature_missing=True,replicate_count_author_claim=3,statistic='mean',numeric_SD=None)
    u=unit(RH,'own_cap',['sample','C','j'],[['RHPC-1000','78.70','.5']],'bodyP26 own GCD under.5Ag; actualFig9b -.9..+.1 Hg; CVcycling separate')
    cap(RH,'RHPC-1000',u,1,1,.5,purpose='reported_aqueous_3e_GCD_capacitance',**rcond,physical_test_group='doi:'+RH+':RHPC-1000:3E:GCD:j.5')
    u=unit(RH,'CV_cycle',['sample','retention','scan'],[['RHPC-1000','97.2','200']],'bodyP26 explicit200mV/s CV/10000 and actualFig9d CVinset, not GCD')
    response(RH,'RHPC-1000',u,1,1,'CV_cycling_retention','%',cycle_count=10000,scan_rate_mV_s=200,method='CV',system='3E')
    spec['candidates'].append(dict(candidate_id='LP17_Rice_CV',doi=RH,sample='RHPC-1000',record=dict(system='3E',method='CV',cycle_count=10000,retention_pct=97.2,scan_rate_mV_s=200,reported_current_A_g=None,cycle_voltage_lower_V=-.9,cycle_voltage_upper_V=.1,purpose_reviewed_candidate_ready=False,reason='CV cycling cannot become current-controlled GCD cycle target; separate method purpose')))
    # Mixed biomass: preserve raw/prechar/final EA and pore nulls.
    mt='nanomaterials-14-01368-t001'
    for row,rr in enumerate(tabs[(MIX,mt)][1:],2):
        s=rr[0];stage='raw_feedstock'if s in ['Broccoli','Pigskin']else'final_biomass_carbon_before_test'if s.startswith('A')else'precarbonization_intermediate';register(MIX,s,stage,'broccoli'if s in ['Broccoli','BC','ABC']else'pigskin'if s=='Pigskin'else'broccoli_and_pigskin')
        for col,e in enumerate(['C','H','N','O','S'],1):fact(MIX,s,mt,row,col,'bulk_EA_'+e+'_wt_pct','wt%','Vario EA own stage/sample; not XPSat%; reportedzero retained not ND assumption')
        for col,e in [(6,'H_C'),(7,'O_C'),(8,'ON_C')]:fact(MIX,s,mt,row,col,'bulk_EA_'+e+'_mass_ratio','mass_ratio','Numerical elemental mass-fraction ratios, not atomic ratios')
    mt2='nanomaterials-14-01368-t002'
    for row,rr in enumerate(tabs[(MIX,mt2)][1:],2):
        for col,f,un in [(1,'BET_surface_area_m2_g','m2/g'),(2,'micropore_surface_area_m2_g','m2/g'),(3,'total_pore_volume_cm3_g','cm3/g'),(4,'micropore_volume_cm3_g','cm3/g'),(5,'pore_size_as_printed_nm_footnote_disputed','nm_as_header')]:fact(MIX,rr[0],mt2,row,col,f,un,'OwnTable2, BJH/Tplot qualifiers; size nm header vs mesoporevolume footnote inconsistent','unreported_dash'if rr[col]=='—'else'conflict_pore_size_footnote_dimension'if col==5 else'own_reported_method_qualified')
    u=unit(MIX,'Fig2_Raman',['sample','area_ID_IG'],[[s,v]for s,v in zip(['BC','BPC-1','BPC-2','BPC-4','ABC','ABPC-1','ABPC-2','ABPC-4'],['.82','.83','.85','.88','.89','.95','.88','.87'])],'ActualFig2c/d printed integrated area D/G ratios, stages distinct','Mixed17_Fig2','own_printed_figure_annotations')
    for row,rr in enumerate(spec['units'][-1]['rows'],1):fact(MIX,rr[0],u,row,1,'Raman_ID_IG','ratio','OwnFig2 integrated area D/G')
    mcond=dict(system='3E',electrolyte='KOH',concentration_mol_L=6,voltage_lower_V=-1,voltage_upper_V=0,reference_electrode='Hg/HgO',capacitance_basis='author_reported_3E',target_stage='fresh_reported_GCD_rate_test')
    u=unit(MIX,'own_3E_cap',['sample','C','j'],[['ABPC-4','473.03','1']],'bodyP20/21 andTable3 ownrow, actualFig6c bluej1; 3E ownFig6b protocol')
    cap(MIX,'ABPC-4',u,1,1,1,purpose='reported_aqueous_3e_GCD_capacitance',**mcond,physical_test_group='doi:'+MIX+':ABPC-4:3E:GCD:j1')
    m2=dict(system='2E_symmetric',electrolyte='KOH',concentration_mol_L=6,voltage_lower_V=0,voltage_upper_V=1.3,reference_electrode=None,capacitance_basis='author_symmetric_factor2_with_m_as_written',target_stage='fresh_reported_GCD_rate_test')
    u=unit(MIX,'own_2E_cap',['sample','C','j'],[['ABPC-4','273.41','1'],['ABPC-4','300.74','.5'],['ABPC-4','273.41','30']],'bodyP23/Table3 at1, P25 at.5, conclusionP26 wronglyat30; Fig8a israte despite swappedcaption')
    for row,j in [(1,1),(2,.5),(3,30)]:cap(MIX,'ABPC-4',u,row,1,j,purpose='reported_aqueous_2e_factor2_Cs'if row<3 else None,**m2,report_kind='conclusion_current_dissent'if row==3 else'own_bound_GCD',physical_test_group='doi:'+MIX+':ABPC-4:2E:GCD:j'+str(j))
    u=unit(MIX,'cycle_role_claims',['sample','retention_as_claimed','CE'],[['ABPC-4','100','95.08'],['ABPC-4','95.08','']],'ActualFig8c blackleftretention~100 redrightCE95.08/bodyP25 versusabstract/P4/P26 ret95.08; both retained','Mixed17_Fig8','own_figure_bound_prose_with_role_dissent')
    response(MIX,'ABPC-4',u,1,1,'cycling_retention_author_rounded','%',system='3E',cycle_count=10000,reported_current_A_g=10,relation='approx',role_selection_basis='actualFig8c axes+bodyP25, no author erratum')
    response(MIX,'ABPC-4',u,1,2,'coulombic_efficiency','%',system='3E',cycle_count=10000,reported_current_A_g=10)
    response(MIX,'ABPC-4',u,2,1,'cycling_retention_role_disputed_claim','%',system='3E',cycle_count=10000,reported_current_A_g=10,ordinary_training_input=False)
    spec['candidates'].append(dict(candidate_id='LP17_ABPC4',doi=MIX,sample='ABPC-4',record=dict(system='3E',method='GCD',cycle_count=10000,retention_pct=100,retention_relation='approx',coulombic_efficiency_pct=95.08,reported_current_A_g=10,cycle_voltage_lower_V=-1,cycle_voltage_upper_V=0,voltage_binding='matched_own_3E_GCD_Fig6b_common_method_not_local_cycle_inset',purpose_reviewed_candidate_ready=False,reason='Role resolved for working report from actual axes+P25; common-protocol cycling admission and full record still require explicit cycling release, not automatic literature-layer admission',conflicting_original_retention_claim=95.08)))
    for s in names[MIX]:
        if s in ['Broccoli','Pigskin']:continue
        pig=0 if s in ['BC','ABC']else{1:6,2:3,4:1.5}[int(s.split('-')[1])]
        stages=[dict(stage='feedstock_preparation',broccoli_drying_C=60,broccoli_drying_h=12,pigskin_NaHCO3_M=1,pigskin_degreasing_h=12,pigskin_drying_C=80,pigskin_drying_h=24,grinding_min=3,broccoli_sieve_mm=.25),dict(stage='precarbonization',temperature_C=500,duration_h=1,heating_rate_C_min=3,atmosphere='N2',broccoli_g=6,pigskin_g=pig,EtOH_water_wash_repeats=3,drying_C=80,drying_duration='overnight_not_numeric')]
        if s.startswith('A'):stages.extend([dict(stage='chemical_activation',temperature_C=700,duration_h=1,heating_rate_C_min=3,atmosphere='N2',gas_flow_mL_min=25,pressure_bar=1,agent='KOH',carbon_to_activator_mass_ratio=[1,4],HCl_wt_pct=10,wash_repeats=3,water_wash_to_neutral=True,drying_C=80,drying_duration='overnight_not_numeric',duplicate_700C1h_method_wording_not_summed=True),dict(stage='electrode_preparation',carbon_mg=8,carbon_black_mg=1,PTFE_mg=1,collector='Ni_foam',collector_dimensions_cm=[1,2],press_MPa=15,press_min=2,working_loading_approx_mg_cm2=5,slurry_input_not_final_electrode_mass=True)])
        spec['synthesis'].append(dict(doi=MIX,sample=s,document=KEYS[MIX],locator='bodyP6-P10; explicit finalratio definitions precede early naming-list dissent',stages=stages))
    doc('Mixed17_SI',MIX,OUT/'evidence/Mixed17/nanomaterials-3151670-supplementary.pdf','original_SI_PDF')
    for i in range(1,5):spec['figures'].append(dict(doi=MIX,figure_number=100+i,document='Mixed17_SI',scope_visually_inspected=True,caption='SI FigureS'+str(i)+' p'+str(i+1),full_waveform_extracted=False,remaining='TGA/DTG not digitized; circuit/preparation/LED figures have no extra composition or cycle endpoint values'))
    # Record conflicts/limits as row-level scientific issues, never technical passes.
    findings=json.loads((OUT/'primary_review_findings.json').read_text('utf8'))['findings']
    for r in findings:spec['decisions'].append(dict(doi=r['doi'],id='LP17_'+r['id'],decision=r['finding']))
    for doi in [NPC,MIX]:
        spec['annotations'].append(dict(doi=doi,id=KEYS[doi]+'_XPS_binding_energies',document=KEYS[doi]+'_Fig'+('3'if doi==NPC else'4'),kind='fitted_component_assignments_not_elemental_fractions',energies_eV=([284.7,285.59,287.97,398.2,400.11,404.65,530.92,532.68]if doi==NPC else[284.8,286.55,288.87,398.68,400.10,401.87,531.56,533.03,535.16]),not_predictor_scalar=True))
    assert len(spec['materials'])==64 and len(spec['tables'])==10
    assert len({(r['doi'],r['sample'])for r in spec['materials']})==64
    # Every declared fact/cap/response binds an existing exact source cell.
    allrows={(r['doi'],r['id']):([[v['raw']for v in row]for row in r['grid']]if'grid'in r else r['rows'])for r in spec['tables']+spec['units']}
    for kind in ['facts','caps','responses']:
        for r in spec[kind]:number(allrows[(r['doi'],r['id'])][r['row']-1][r['col']])
    write(OUT/'curation_spec.json',spec);print(json.dumps({k:len(v)for k,v in spec.items()},ensure_ascii=False))

def build():
    assert sha(PARENT)==PSHA and not DB.exists()and not(OUT/'merge_manifest.json').exists()
    spec=json.loads((OUT/'curation_spec.json').read_text('utf8'));docs={d['key']:d for d in spec['documents']}
    with closing(ro(PARENT))as parent,closing(sqlite3.connect(DB))as c:
        parent.backup(c);c.row_factory=sqlite3.Row;c.execute('pragma foreign_keys=on')
        c.executescript('''create table source_reviews_v17(doi text primary key references reviewed_sources,record_json text);create table cell_extractions_v17(kind text,record_id text,table_key text references reviewed_tables,row_ordinal integer,column_ordinal integer,primary key(kind,record_id));create table decisions_v17(decision_id text primary key,doi text references reviewed_sources,record_json text);create table material_feature_decisions_v17(material_key text references materials,field_name text,record_json text,primary key(material_key,field_name));create table purpose_reviews_v17(observation_id text primary key references capacitance_observations,purpose text,eligible integer,record_json text);create table figure_scope_reviews_v17(doi text references reviewed_sources,figure_number integer,document_key text references source_documents,record_json text,primary key(doi,figure_number));create table annotations_v17(annotation_id text primary key,doi text references reviewed_sources,document_key text references source_documents,record_json text);create table cycle_identity_links_v17(link_id text primary key,record_json text);''')
        for s in spec['sources']:insert(c,'reviewed_sources',dict(doi=s['doi'],path=s['path'],sha256=s['sha256'],title=s['title'],stage='All own main tables/methods and main figure scopes; selected SI tables/figures; continuous waveform extraction incomplete'))
        for d in docs.values():assert sha(ROOT/d['path'])==d['sha256'];insert(c,'source_documents',dict(document_key=d['key'],doi=d['doi'],path=d['path'],sha256=d['sha256'],role=d['role']))
        for t in spec['tables']+spec['units']:
            key=t['doi']+'#'+t['id'];rows=[[v['raw']for v in r]for r in t['grid']]if'grid'in t else t['rows'];insert(c,'reviewed_tables',dict(table_key=key,doi=t['doi'],xml_id=t['id'],caption=t.get('caption',t['id']),header_json=json.dumps(rows[0]if'grid'in t else t['header']),footnote=t.get('footnote','Own bounded transcription; stages/repeats/foreign comparisons kept distinct'),source_raw_table_id=t.get('raw_table_id')));insert(c,'table_source_links',dict(table_key=key,document_key=t['document'],locator=t['locator']));insert(c,'extraction_units_v3',dict(table_key=key,kind=t['kind'],scope='Own explicitly bound cells only; foreign rows retained as context, never admitted'))
            for i,row in enumerate(rows,1):insert(c,'transcribed_rows',dict(table_key=key,row_ordinal=i,cells_json=json.dumps(row,ensure_ascii=False)));insert(c,'transcription_origins_v7',dict(table_key=key,row_ordinal=i,origin_json=json.dumps(t['grid'][i-1]if'grid'in t else dict(document=t['document'],locator=t['locator'],row=i),ensure_ascii=False)))
            if t.get('raw_table_id'):
                assert c.execute('select review_state from raw_table_queue where table_id=?',(t['raw_table_id'],)).fetchone()[0]=='automatic_candidate_unreviewed'
                c.execute('update raw_table_queue set review_state=?where table_id=?',('v17_own_cells_methods_stage_and_conflicts_reviewed',t['raw_table_id']))
        for r in spec['materials']:
            insert(c,'materials',dict(material_key=mk(r['doi'],r['sample']),doi=r['doi'],sample_name=r['sample'],material_stage=r['stage']));insert(c,'material_scopes_v8',dict(material_key=mk(r['doi'],r['sample']),scope_json=json.dumps(dict(origin_class='biomass_carbon'if'carbon'in r['stage']else'raw_or_intermediate_biomass',feedstock=r['feedstock'],stage=r['stage'],not_assumed_pure_carbon=True,same_source_not_independent=True))))
        def cell(r):
            key=r['doi']+'#'+r['id'];raw=json.loads(c.execute('select cells_json from transcribed_rows where table_key=?and row_ordinal=?',(key,r['row'])).fetchone()[0])[r['col']];return key,raw,number(raw)
        def receipt(kind,rid,r,key):insert(c,'cell_extractions_v17',dict(kind=kind,record_id=str(rid),table_key=key,row_ordinal=r['row'],column_ordinal=r['col']))
        for r in spec['facts']:
            key,raw,value=cell(r);doc=c.execute('select document_key from table_source_links where table_key=?',(key,)).fetchone()[0];q=insert(c,'material_facts',dict(material_key=mk(r['doi'],r['sample']),field_name=r['field'],value=value,raw_value=raw,unit=r['unit'],method=r['method'],table_key=key,row_ordinal=r['row'],column_ordinal=r['col'],source_sha256=docs[doc]['sha256'],review_status=r['status'],training_eligible=0));receipt('fact',q.lastrowid,r,key)
        for r in spec['caps']:
            key,raw,value=cell(r);rid=key+'#'+str(r['row'])+'#'+str(r['col']);cond=dict(extraction_batch='v17',current_mass_basis='author_reported_unknown_not_inferred',repeat_reports_not_independent=True,**r['conditions'])
            insert(c,'capacitance_observations',dict(observation_id=rid,material_key=mk(r['doi'],r['sample']),table_key=key,row_ordinal=r['row'],column_ordinal=r['col'],value=value,raw_value=raw,unit='F/g',method='GCD',system=cond['system'],electrolyte=cond['electrolyte'],concentration_mol_L=cond['concentration_mol_L'],current_A_g=r['j'],scan_rate_mV_s=None,conditions_json=json.dumps(cond,ensure_ascii=False),status='own_reported'if r['purpose']else'own_repeat_or_competing_report',source_group='doi:'+r['doi'],training_eligible=0));receipt('capacitance',rid,r,key)
            if r['purpose']:
                reason='Own bound fresh GCD with method-qualified configuration/electrolyte/formula; optional missing features remain masks; source/sample/current repeated reports deduplicated by purpose'
                insert(c,'purpose_reviews_v17',dict(observation_id=rid,purpose=r['purpose'],eligible=1,record_json=json.dumps(dict(reason=reason,purpose_input_ready=True,cyclic_retention_training_admitted=False,training_authorized=False))))
                if r['purpose']=='reported_aqueous_3e_GCD_capacitance':insert(c,'auxiliary_gcd_reviews_v3',dict(observation_id=rid,purpose=r['purpose'],eligible=1,reason=reason,review_basis='Own specific results/actual printed plot and matched own protocol, variants retained; no performance-based selection'))
        for r in spec['responses']:
            key,raw,value=cell(r);rid=key+'#'+str(r['row'])+'#'+str(r['col']);insert(c,'outcome_observations_v3',dict(outcome_id=rid,material_key=mk(r['doi'],r['sample']),table_key=key,record_json=json.dumps(dict(source_group='doi:'+r['doi'],extraction_batch='v17',metric=r['metric'],value=value,raw_value=raw,unit=r['unit'],feature_role='test_or_process_response_not_pretest_predictor',**r['conditions']),ensure_ascii=False),training_eligible=0));receipt('response',rid,r,key)
        for r in spec['synthesis']:insert(c,'synthesis_stages_v3',dict(material_key=mk(r['doi'],r['sample']),document_key=r['document'],locator=r['locator'],stages_json=json.dumps(r['stages'],ensure_ascii=False)))
        for r in spec['feature_decisions']:insert(c,'material_feature_decisions_v17',dict(material_key=mk(r['doi'],r['sample']),field_name=r['field'],record_json=json.dumps(r,ensure_ascii=False)))
        for r in spec['decisions']:insert(c,'decisions_v17',dict(decision_id=r['id'],doi=r['doi'],record_json=json.dumps(r,ensure_ascii=False)));insert(c,'scientific_issues',dict(issue_id=r['id'],doi=r['doi'],sample_name=None,issue_json=json.dumps(dict(kind=r['id'],action=r['decision']),ensure_ascii=False)))
        for r in spec['figures']:insert(c,'figure_scope_reviews_v17',dict(doi=r['doi'],figure_number=r['figure_number'],document_key=r['document'],record_json=json.dumps(r,ensure_ascii=False)))
        for r in spec['annotations']:insert(c,'annotations_v17',dict(annotation_id=r['id'],doi=r['doi'],document_key=r['document'],record_json=json.dumps(r,ensure_ascii=False)))
        for r in spec['identity_links']:insert(c,'cycle_identity_links_v17',dict(link_id='LP17_'+r['existing_endpoint_id'],record_json=json.dumps(r,ensure_ascii=False)))
        sources={r['doi']:r for r in spec['sources']}
        for r in spec['candidates']:insert(c,'test_candidates',dict(candidate_id=r['candidate_id'],material_key=mk(r['doi'],r['sample']),record_json=json.dumps(dict(r['record'],source_group='doi:'+r['doi'],source_year=sources[r['doi']]['year'],evidence_source_path=sources[r['doi']]['path'],source_sha256=sources[r['doi']]['sha256'],current_mass_basis='author_reported_unknown_not_inferred',baseline_cycle=None,baseline_reference='author_reference_not_assumed_cycle1'),ensure_ascii=False),training_eligible=0))
        for s in spec['sources']:
            review=dict(source_year=s['year'],classification=s['classification'],scope='All ownmain tables and relevant methods/results, allmainfigure scope; ExtrusionSI8tables and MixedSI4figure scopes',remaining='Continuous spectra/isotherms/CV/GCD/EIS and remaining graphical rate quantities; ExtrusionSI spectral pages not fully visually reviewed. Conflicts and separate method/configuration purposes remain.',full_source_review_complete=False)
            insert(c,'source_scope_decisions',dict(doi=s['doi'],scope=review['scope'],reason=review['remaining'],evidence_json=json.dumps(review,ensure_ascii=False),full_source_review_complete=0));insert(c,'source_reviews_v17',dict(doi=s['doi'],record_json=json.dumps(review,ensure_ascii=False)))
        c.commit()
    protected={ROOT/d['path']for d in docs.values()}|{PARENT,ROOT/'循环稳定性数据库_v0.25_芒果核皮革循环准入_20261026/cycling_v0_25.sqlite',ROOT/'全库复检与特征补提取_20261021/full_corpus_search_native.sqlite',OUT/'evidence/Extrusion17/primary_assets.zip',OUT/'evidence/Mixed17/primary_assets.zip'}
    write(OUT/'protected_inputs.json',dict(files=[dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p),bytes=p.stat().st_size)for p in sorted(protected)]));print('Built unsealed v17; no cycling admission or model fitting')

if __name__=='__main__':
    if len(sys.argv)!=2 or sys.argv[1]not in ['curate','build']:raise SystemExit('One-use curate/build only on an unsealed new batch')
    globals()[sys.argv[1]]()
