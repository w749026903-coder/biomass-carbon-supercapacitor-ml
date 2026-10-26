"""One-use v19 own-table curation. No old builders or sealed releases are rerun.

Numbers keep the printed token, method, stage, uncertainty and censoring.
Only explicit author fresh-GCD quantities receive separate purpose reviews.
"""
from pathlib import Path
from contextlib import closing
import json,re,sqlite3,sys,xml.etree.ElementTree as E
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tools'))
from extract_onion_composite_v8 import sha,write,ro,insert,mk
from extract_palm_kernel_v7 import xml_grid
from extract_source_series_v13 import clean
OUT=ROOT/'文献全量利用复核_20261027/批次19_木质素纳米纤维蛋米与烟草系列'
DB=OUT/'literature_material_pool_v19.sqlite'
PARENT=ROOT/'文献全量利用复核_20261027/批次18_淀粉稻壳混合碳倍率与循环再核/literature_material_pool_v18.sqlite'
PSHA='b1caff01d88b54b714360b6a7844b515ad4bd66e0f9cc1b21434206134ca643d'
L='10.1021/acssuschemeng.6c00388';EG='10.3390/molecules28186543';TO='10.3390/molecules28248136'
KEYS={L:'Lignin19',EG:'EggRice19',TO:'Tobacco19'}
NUM=r'[+-]?(?:\d+(?:\.\d+)?|\.\d+)'
def numeric_details(raw):
    r=raw.strip();d=dict(raw_token=raw,value=None,uncertainty=None,uncertainty_kind=None,relation=None,limit=None)
    if r in ['','-','—']:return dict(d,kind='not_reported_or_dash_not_zero')
    if re.fullmatch('[<>]'+NUM,r):return dict(d,kind='censored_author_limit',relation=r[0],limit=float(r[1:]))
    if r.startswith('0 085')or r.startswith('0 143'):return dict(d,kind='ambiguous_printed_decimal_spacing')
    if '±'in r:
        a,b=map(str.strip,r.split('±'));assert re.fullmatch(NUM,a),r
        return dict(d,value=float(a),uncertainty=float(b)if re.fullmatch(NUM,b)else None,uncertainty_raw=b,uncertainty_kind='author_uncertainty_unspecified_unless_method_states_SD',kind='author_mean_with_reported_uncertainty')
    r=r.rstrip('%');assert re.fullmatch(NUM,r),raw
    return dict(d,value=float(r),kind='author_printed_scalar')
def number(raw):return numeric_details(raw)['value']

def curate():
    assert sha(PARENT)==PSHA and not DB.exists()and not(OUT/'curation_spec.json').exists()and not(OUT/'merge_manifest.json').exists()
    notes=json.loads((OUT/'source_review_notes.json').read_text('utf8'))
    spec={k:[]for k in ['sources','documents','tables','units','materials','facts','caps','responses','synthesis','decisions','feature_decisions','figures','candidates','annotations','identity_links','raw_dispositions','lineage']}
    roots={};tabs={};paths={s['doi']:ROOT/s['path']for s in notes['sources']}
    def doc(key,doi,path,role):
        assert path.is_file(),path
        spec['documents'].append(dict(key=key,doi=doi,path=path.relative_to(ROOT).as_posix(),sha256=sha(path),role=role))
    with closing(ro(ROOT/'全库复检与特征补提取_20261021/full_corpus_search_native.sqlite'))as native:
        for src in notes['sources']:
            doi=src['doi'];path=paths[doi];assert sha(path)==src['sha256'];root=E.parse(path).getroot();roots[doi]=root
            assert {x.text.lower()for x in root.findall('./front/article-meta/article-id')if x.get('pub-id-type')=='doi'}=={doi}
            ids=list(native.execute('select identity_key,role,basis from identity_sources where sha256=?',(src['sha256'],)));assert {r[0]for r in ids}=={'doi:'+doi}
            year=max(int(x.text)for x in root.findall('./front/article-meta/pub-date/year'))
            spec['sources'].append(dict(src,title=clean(root.find('.//article-title')),year=year,identity_roles=ids,classification='original_biomass_research'))
            doc(KEYS[doi],doi,path,'primary_XML')
            raw={r[1]:r[0]for r in native.execute('select table_id,locator from raw_tables_v11 where source_sha256=?',(src['sha256'],))}
            for t in root.findall('.//table-wrap'):
                locator='XML table-wrap '+t.get('id');grid=xml_grid(t);tabs[doi,t.get('id')]=[[v['raw']for v in rr]for rr in grid]
                spec['tables'].append(dict(doi=doi,id=t.get('id'),document=KEYS[doi],locator=locator,caption=clean(t.find('caption')),footnote=clean(t.find('table-wrap-foot')),grid=grid,raw_table_id=raw[locator],kind='native_XML_own_rows_extracted_foreign_rows_context_only'))
            for f in root.findall('.//fig'):
                label=clean(f.find('label'));n=int(re.search(r'\d+',label)[0]);href=f.find('.//graphic').get('{http://www.w3.org/1999/xlink}href');matches=list(path.parent.rglob(href))or list((OUT/'evidence/Tobacco').glob(href));assert len(matches)==1,(doi,href)
                key=KEYS[doi]+'_Fig'+str(n);doc(key,doi,matches[0],'original_main_figure')
                spec['figures'].append(dict(doi=doi,figure_number=n,printed_label=label,xml_id=f.get('id'),graphic_href=href,document=key,caption=clean(f.find('caption')),scope_visually_inspected=True,full_waveform_extracted=False,remaining='Continuous spectra/isotherms/CV/GCD/EIS and untranscribed graphical markers remain'))
            si=list(path.parent.glob('sc6c00388_si_001.pdf'if doi==L else'*supplementary.pdf'));assert len(si)==1
            doc(KEYS[doi]+'_SI',doi,si[0],'original_SI_PDF')
            if doi==L:
                for r in native.execute('select table_id,locator from raw_tables_v11 where source_sha256=?',(sha(si[0]),)):
                    foreign=r[0]in ['a1399dbd24cf69017492feb9','94b5d4bbbea31ca04106f815']
                    spec['raw_dispositions'].append(dict(table_id=r[0],locator=r[1],disposition='v19_foreign_comparison_S1_two_page_fragments_not_own_samples'if foreign else'v19_own_SI_physical_table_cells_reviewed',physical_table='S1'if foreign else None))
    def unit(doi,id,header,rows,locator,document=None,kind='own_bound_prose_or_printed_figure_transcription',raw_id=None):
        item=dict(doi=doi,id=id,header=header,rows=[[re.sub(r'(?<![\d.])\.(\d+)',r'0.\1',str(v))for v in rr]for rr in rows],locator=locator,document=document or KEYS[doi],kind=kind)
        if raw_id:item['raw_table_id']=raw_id
        spec['units'].append(item);return id
    def fact(doi,s,id,row,col,field,un,method,status='own_reported_method_qualified'):
        spec['facts'].append(dict(doi=doi,sample=s,id=id,row=row,col=col,field=field,unit=un,method=method,status=status))
    def reg(doi,s,stage,feedstock):spec['materials'].append(dict(doi=doi,sample=s,stage=stage,feedstock=feedstock))
    def response(doi,s,id,row,col,metric,un,**cond):spec['responses'].append(dict(doi=doi,sample=s,id=id,row=row,col=col,metric=metric,unit=un,conditions=cond))
    def cap(doi,s,id,row,col,j,purpose,**cond):spec['caps'].append(dict(doi=doi,sample=s,id=id,row=row,col=col,j=j,purpose=purpose,conditions=cond))
    def issue(doi,id,evidence,decision):spec['decisions'].append(dict(doi=doi,id='V19_'+id,evidence=evidence,decision=decision,not_author_erratum=True))
    def synth(doi,s,locator,stages):spec['synthesis'].append(dict(doi=doi,sample=s,document=KEYS[doi],locator=locator,stages=stages))
    # Lignin: six technical lignins, seven actual dopes, nine final fibre materials.
    labels=['OS beech','Kraft eucalyptus','Kraft pine/spruce','IS eucalyptus','IS spruce','IS miscanthus']
    feed=['beech_organosolv_lignin','eucalyptus_Kraft_lignin','pine_spruce_Kraft_lignin','eucalyptus_ionosolv_lignin','spruce_ionosolv_lignin','miscanthus_ionosolv_lignin']
    finals=[x+' LCNF1000'for x in labels];raws=[x+' raw lignin'for x in labels];dopes=[x+' standard dope'for x in labels]
    extra=['OS beech LCNF700','OS beech LCNF1300','OS beech LCNF1000 12% solids'];dope12='OS beech 12% dope'
    for i in range(6):
        reg(L,raws[i],'technical_lignin_precursor',feed[i]);reg(L,dopes[i],'polymer_assisted_spinning_dope',feed[i]+'+PEO');reg(L,finals[i],'final_biomass_carbon_PEO_assisted_nanofiber',feed[i]+'+PEO_spinning_aid')
        spec['lineage'].extend([dict(doi=L,parent=raws[i],child=dopes[i],kind='precursor_not_final_feature_inheritance'),dict(doi=L,parent=dopes[i],child=finals[i],kind='stabilization_then_carbonization_activation')])
    reg(L,dope12,'polymer_assisted_spinning_dope',feed[0]+'+PEO')
    for s in extra:reg(L,s,'final_biomass_carbon_PEO_assisted_nanofiber',feed[0]+'+PEO_spinning_aid')
    spec['lineage'].extend([dict(doi=L,parent=raws[0],child=dope12,kind='lower_solid_loading_dope'),dict(doi=L,parent=dope12,child=extra[2],kind='stabilization_then_carbonization_activation'),*[dict(doi=L,parent=dopes[0],child=s,kind='temperature_variant_not_an_independent_source')for s in extra[:2]]])
    t='tbl1'
    for row,s in enumerate(dopes,2):
        for col,f,u in [(1,'dope_lignin_mass_g','g'),(2,'dope_PEO_mass_g','g'),(3,'dope_PEO_Mw_kDa','kDa'),(4,'dope_NaOH_solution_mass_g','g')]:fact(L,s,t,row,col,f,u,'OwnMainTable1 actual recipe; raw polymer fraction is not final carbon composition')
    porefields=[('total_pore_volume_cm3_g','cm3/g'),('BET_surface_area_m2_g','m2/g'),('micropore_volume_cm3_g','cm3/g'),('N2_2D_NLDFT_pore_volume_cm3_g','cm3/g'),('N2_2D_NLDFT_surface_area_m2_g','m2/g'),('CO2_2D_NLDFT_pore_volume_cm3_g','cm3/g'),('CO2_2D_NLDFT_surface_area_m2_g','m2/g')]
    for row,s in enumerate(finals,2):
        for col,(f,u)in enumerate(porefields,1):fact(L,s,'tbl2',row,col,f,u,'OwnMainTable2 N2 77K, CO2 273K; Rouquerol-selected BET; t-plot micropore, separate 2D-NLDFT adsorptives')
    def sitable(id,page,fields,rows,samples,rawid,method,field_status=None):
        uid=unit(L,'SI_'+id,['Sample']+[x[0]for x in fields],[[s,*r]for s,r in zip(samples,rows)],'SI physical PDF p'+str(page)+' Table'+id+'; printed original labels retained',KEYS[L]+'_SI','own_SI_physical_table',rawid)
        for row,s in enumerate(samples,1):
            for col,(f,u)in enumerate(fields,1):fact(L,s,uid,row,col,f,u,method,(field_status or{}).get(f,'own_reported_method_qualified'))
        return uid
    s2=unit(L,'SI_S2',['Sample','Ctemperature','electrolyte','electrode1_mg','electrode2_mg','loading_mg_cm2'],[[s,t,e,a,b,c]for s,t,e,a,b,c in [
        (extra[0],700,'6M KOH','1.41','1.40','1.2'),(finals[0],1000,'6M KOH','1.55','1.50','1.4'),(extra[2],1000,'6M KOH','1.17','1.13','1.0'),(extra[1],1300,'6M KOH','.74','.70','.6'),(finals[1],1000,'6M KOH','.63','.60','.5'),(finals[1],1000,'12mol/kg NaNO3','.51','.62','.7'),(finals[2],1000,'6M KOH','.79','.94','.8'),(finals[3],1000,'6M KOH','.93','1.03','.9'),(finals[4],1000,'6M KOH','.70','.74','.6'),(finals[5],1000,'6M KOH','.71','.76','.7')]],'SI PDF p3 TableS2; ten electrode pairs, same material in different electrolytes not new material',KEYS[L]+'_SI','own_SI_physical_table','b7b1a00a09214d2ab3ad5823')
    for row,rr in enumerate(spec['units'][-1]['rows'],1):
        for col,metric,u in [(3,'electrode1_active_mass_mg','mg'),(4,'electrode2_active_mass_mg','mg'),(5,'author_mass_loading_mg_cm2','mg/cm2')]:response(L,rr[0],s2,row,col,metric,u,electrolyte=rr[2],feature_role='test_geometry_not_intrinsic_material_property',printed_mass_loading_not_recomputed=True)
    sitable('S3',4,[('dope_viscosity_at_10_per_s_Pa_s','Pa.s')],[[v]for v in ['6.01','.27','1.09','2.51','.42','.49']],dopes,'0d9278d24bb3ac3043f1e0d3','Shear rate10/s; spinning dope, not final electrode conductivity')
    sitable('S4',4,[('SEM_fiber_diameter_mean_nm','nm')],[[v]for v in ['613 ± 56','251 ± 47','488 ± 57','352 ± 51','496 ± 78','686 ± 92']],finals,'b902512281c0932b1609ac6d','Author SEM ImageJ mean±SD, not independent materials')
    sitable('S5',5,[(f'XPS_{x}_wt_pct','wt%')for x in ['C','N','S','O']],list(zip(['93.28','93.47','95.13','94.60','89.47','93.92'],['1.01','1.42','.89','1.09','.57','.69'],['<0.01','.84','.91','.57','.89','1.04'],['5.71','4.26','3.07','3.74','9.06','4.35'])),finals,'31dc6407b53cd57d71f594e7','XPS; SI FigS3b explicitly y-axis Weight(%); <.01 censored, not zero; not atom%')
    s6rows=[['.389','1.77','1.21 ± .02','3.32 ± .12','1597 ± 1','65 ± 1','1345 ± 1','179 ± 3'],['.366','1.48','1.22 ± .06','3.47 ± .36','1595 ± 1','62 ± 2','1339 ± 1','174 ± 4'],['.400','2.23','1.25 ± .05','3.43 ± .33','1594 ± 1','62 ± 2','1339 ± 1','169 ± 5'],['.396','1.88','1.43 ± .06','4.58 ± .43','1599 ± 1','57 ± 3','1337 ± 1','185 ± 7'],['.408','3.17','1.46 ± .10','4.48 ± .65','1596 ± 2','62 ± 6','1339 ± 2','194 ± 7'],['.391','1.60','1.43 ± .07','4.64 ± .46','1594 ± 1','61 ± 2','1339 ± 1','197 ± 7']]
    sitable('S6',6,[('XRD_d002_nm','nm'),('XRD_Lc_nm','nm'),('Raman_ID_IG','ratio'),('Raman_AD_AG','ratio'),('Raman_G_position_cm_inv','cm-1'),('Raman_G_FWHM_cm_inv','cm-1'),('Raman_D_position_cm_inv','cm-1'),('Raman_D_FWHM_cm_inv','cm-1')],s6rows,finals,'d9d599a8c9da814ec08537eb','Mo XRD lambda.7093Angstrom; Raman532nm mapped>=25points, ID/IG distinct AD/AG; author uncertainty not assumed experimental CI')
    density=[['.135 ± .004','1.25 ± .07','.108 ± .009'],['.054 ± .002','.76 ± .02','.071 ± .004'],['.077 ± .003','.91 ± .03','0 085 ± .006'],['.087 ± .003','.61 ± .03','0 143 ± .012'],['.064 ± .002','1.06 ± .04','.061 ± .004'],['.065 ± .002','.98 ± .04','.066 ± .005']]
    df=[('packing_density_g_cm3','g/cm3'),('skeletal_density_He_g_cm3','g/cm3'),('volume_packing_fraction_author','ratio')]
    sitable('S7',7,df,density,finals,'b3677a9d511dda9b7893431d','Packing disk mass/volume vs helium skeletal; two decimal-spacing ambiguities retained without inferred decimal')
    sitable('S8',8,[('electrical_conductivity_4point_S_cm','S/cm'),('packing_normalized_conductivity_S_cm2_g','S.cm2/g')],[['15.98 ± .46','118.4 ± 6.9'],['18.57 ± 4.46','343.9 ± 95.3'],['10.27 ± 3.22','133.4 ± 47.0'],['18.02 ± 5.14','207.1 ± 66.2'],['8.49 ± 2.55','132.7 ± 44.0'],['7.62 ± 1.91','117.2 ± 33.0']],finals,'0145d872e81a0e716ea4db65','4point probe5locations, mean with author unspecified uncertainty; not five samples')
    sitable('S9',14,[('HSQC_S_to_G_ratio','ratio'),('HSQC_xylose_per_100_aromatic_units','per100aromatic')],[['1.65','.31'],['2.80','2.65'],['0','1.13'],['1.57','.24'],['0','.22'],['.15','.46']],raws,'93d669e4b99c4ae634190ea5','Raw technical lignin semiquantitative HSQC, not final carbon atomic composition')
    sitable('S10',14,[('HSQC_C_O_C_linkage_pct','%linkages'),('HSQC_C_C_linkage_pct','%linkages')],[['34.8','65.2'],['55.9','44.1'],['47.6','52.4'],['30.1','69.9'],['28.8','71.2'],['45.2','54.8']],raws,'4e8c7c5a54817d88b4e78a41','Raw technical lignin HSQC integration relative abundance')
    sitable('S11',19,[('NMR31P_total_OH_mmol_g','mmol/g'),('NMR31P_aliphatic_OH_mmol_g','mmol/g'),('NMR31P_phenolic_OH_mmol_g','mmol/g'),('NMR31P_aliphatic_phenolic_ratio','ratio')],[['4.16','1.03','3.08','.33'],['6.00','1.38','4.45','.31'],['4.29','1.30','2.88','.45'],['5.09','.82','4.00','.21'],['4.88','.35','3.77','.10'],['6.70','2.11','4.08','.52']],raws,'a8433a915d48346a85299e3e','Quantitative31P NMR rawlignin total includes carboxylic; not simply aliphatic+phenolic')
    sitable('S12',19,[(f'NMR31P_{x}_OH_mmol_g','mmol/g')for x in ['aliphatic','syringyl_condensed_phenolic','guaiacyl','p_hydroxyphenyl','carboxylic']],[['1.03','2.14','.85','.09','.06'],['1.38','3.35','1.10','.00','.17'],['1.30','.72','2.15','.01','.11'],['.82','2.52','1.20','.28','.27'],['.35','.86','2.32','.58','.77'],['2.11','1.58','1.56','.94','.51']],raws,'7280ae03664047efff4feaf7','Rawlignin31P NMR; explicit0.00 retained, not missing')
    sitable('S13',22,[('GPC_Mn_Da','Da'),('GPC_Mw_Da','Da'),('GPC_dispersity','ratio')],[['2023 ± 76','4275 ± 152','2.11 ± .01'],['1891 ± 36','5134 ± 19','2.72 ± .04'],['3263 ± 85','15717 ± 448','4.82 ± .02'],['2484 ± 34','7787 ± 89','3.14 ± .08'],['2513 ± 71','6375 ± 213','2.54 ± .02'],['2436 ± 69','5499 ± 226','2.26 ± .03']],raws,'79523538a6b9570fa17d8f02','RawligninGPC duplicate; author uncertainty, not electrode molecularweight')
    sitable('S14',22,[(f'CHNS_{x}_wt_pct','wt%')for x in ['C','H','N','S']]+[('raw_lignin_ash525C_wt_pct','wt%'),('raw_lignin_author_C_O_ratio','ratio')],[['63.23 ± .02','5.58 ± .02','.215 ± <0.01','<0.01','1.30 ± .20','2.04'],['59.59 ± .02','5.75 ± .02','.225 ± <0.01','2.815 ± .015','1.14 ± .10','1.88'],['63.66 ± .02','5.715 ± <0.01','.14 ± <0.01','1.83 ± .09','1.23 ± .12','2.22'],['61.195 ± .175','5.38 ± .15','.455 ± .055','1.105 ± .175','2.85 ± .02','1.92'],['60.5 ± .05','5.805 ± .205','1.51 ± .02','2.7 ± .11','2.87 ± .22','2.05'],['63.235 ± .115','7.205 ± .175','.78 ± .03','2.525 ± .175','1.59 ± .09','2.4']],raws,'e37bb14dba6ddefaedb81975','RawligninCHNS and air525C ash; not final carbon, Oxygen not supplied as separatevalue')
    sitable('S15',23,[('raw_lignin_TGA900C_char_yield_pct','%')],[[s]for s in ['38.8 ± .1','35.9 ± .7','37.6 ± 1.9','43.8 ± .6','39.6 ± .6','41.1 ± 1.5']],raws,'bd98a9a0747a8b34a22daf05','RawligninTGA900CN2; not1000C electrospun mat yield')
    sitable('S116',24,[('author_dope_solid_loading_pct','%'),('dope_lignin_mass_g','g'),('dope_PEO_mass_g','g'),('dope_PEO_Mw_kDa','kDa'),('dope_NaOH_solution_mass_g','g'),('dope_viscosity_at_10_per_s_Pa_s','Pa.s')],[['15','1.2','.15','400','7.8','6.01'],['12','1.2','.15','400','10','.16']],[dopes[0],dope12],'919a73e52ef00ef70ed38247','PrintedTableS116, referencedS16; authorroundedsolidloading not silently replaced by massrecalculation')
    sitable('S1127',25,porefields,[['.30','464','.11','.28','207','.21','605'],['.57','1212','.36','.53','638','.45','1424']],[finals[0],extra[2]],'2a56bc54170c815c76ce964a','PrintedTableS1127 referencedS17; DFT N2 header also t-plot, methodlabel dissent retained, not extra sample')
    sitable('S18',26,df,[density[0],['.102 ± .003','.71 ± .01','.144 ± .008']],[finals[0],extra[2]],'b475c042f4e622c9d3271d75','Own density repeat for15% not new sample; lower loading12% distinct')
    u=unit(L,'SI_FigS33_diameter',['sample','mean_SD_nm'],[[extra[2],'422 ± 74']],'SIp25actualFigS33b printedmeanSD',KEYS[L]+'_SI');fact(L,extra[2],u,1,1,'SEM_fiber_diameter_mean_nm','nm','SEM ImageJ author mean±SD')
    for i,s in enumerate(finals+extra):
        t=700 if s==extra[0]else 1300 if s==extra[1]else 1000;peo=.30 if s==finals[1]else .15;mw=400 if s.startswith('OS beech')else 200
        synth(L,s,'MainP16/33-35,Table1; SI S116 lowerload; all own conditions, no final PEO fraction inferred',[dict(stage='polymer_assisted_electrospinning',lignin_mass_g=1.2,PEO_mass_g=peo,PEO_Mw_kDa=mw,NaOH_concentration_M=.5,NaOH_solution_mass_g=10 if s==extra[2]else 7.8,voltage_kV=20,distance_cm=20,flow_mL_h=1,drum_rpm=500,relative_humidity_pct=25),dict(stage='stabilization',temperature_C=250,duration_h=2,heating_rate_C_min=1,atmosphere='air'),dict(stage='single_carbonization_activation',temperature_C=t,duration_h=2,heating_rate_C_min=1,atmosphere='N2',activator='NaOH from dope; dry NaOH mass ratio unreported'),dict(stage='acid_wash',reagent='HCl',concentration_M=.5,duration_min=30)])
    lcond=dict(system='2E',electrolyte='KOH',concentration_mol_L=6,voltage_lower_V=0,voltage_upper_V=1.2,capacitance_basis='pseudo_single_electrode_Cs_2Ctotal/mave_equals4Ctotal/mtotal',preconditioning_cycles=500,preconditioning_current_A_g=5,current_mass_basis='author_reported_unknown_not_inferred',physical_test_group='doi:'+L+'#KE6MKOH')
    u=unit(L,'Main_P52_P78_GCD',['sample','current','Cs'],[[finals[1],'.25','192'],[finals[1],'200','134'],[finals[1],'.25','174']],'MainP52/P78 ownpseudoSinglevalues Fig6a/Fig11c')
    for row,j,e,con,v in [(1,.25,'KOH',6,1.2),(2,200,'KOH',6,1.2),(3,.25,'NaNO3',None,1.8)]:
        cap(L,finals[1],u,row,2,j,'reported_lignin_PEO_2e_factor4_Cs_aqueous'if e=='KOH'else'reported_lignin_PEO_2e_factor4_Cs_WIS',**dict(lcond,electrolyte=e,concentration_mol_L=con,concentration_mol_kg=12 if e=='NaNO3'else None,voltage_upper_V=v,physical_test_group='doi:'+L+'#KE_'+e))
    u=unit(L,'Main_P54_volume_area',['sample','j','volume','area'],[[finals[0],'.25','19.9','.20']],'MainP54 Fig6c/d pseudoSingle electrode, separatevolume/area targets')
    response(L,finals[0],u,1,2,'pseudo_single_electrode_volumetric_capacitance','F/cm3',current_A_g=.25,system='2E',electrolyte='6M KOH');response(L,finals[0],u,1,3,'pseudo_single_electrode_areal_capacitance','F/cm2',current_A_g=.25,system='2E',electrolyte='6M KOH')
    u=unit(L,'Main_cycle_own_values',['sample','electrolyte','retention'],[[finals[0],'6M KOH','95.5'],[finals[2],'6M KOH','82.8'],[finals[1],'6M KOH','89'],[finals[1],'12mol/kg NaNO3','54']],'MainP50/78 Fig5f/SI FigS39; 10kcycles; WIScyclingcurrent not explicitlySIcaption')
    for row,rr in enumerate(spec['units'][-1]['rows'],1):
        j=10 if row<4 else None
        response(L,rr[0],u,row,2,'capacitance_retention','%',cycle_count=10000,current_A_g=j,system='2E',electrolyte=rr[1])
        spec['candidates'].append(dict(candidate_id='LP19:Lignin:'+str(row),doi=L,sample=rr[0],record=dict(retention_pct=float(rr[2]),cycle_count=10000,reported_current_A_g=j,system='2E',method='GCD',electrolyte=rr[1],cycle_voltage_lower_V=None,cycle_voltage_upper_V=None,scope_flags=['PEO_assisted_biomass_carbon_fiber','cycle_local_voltage_pending'],basis='OwnmainP50/78; SI39 WIS current not specified; do not borrow preconditioning5Ag')))
    issue(L,'precursor_stage_and_PEO',dict(default_lignin_PEO=[1.2,.15],Kraft_eucalyptus=[1.2,.30],XPS_SI_axis='Weight(%)',TGA_temperature_C=900),'Rawlignin NMR/GPC/CHNS/ash/yield and dopeviscosity separatelyregistered; no automatic inheritance. PEO dryfeedfraction is not finalcarboncomposition; explicitseparateCs use.')
    issue(L,'SI_printed_limits_and_labels',dict(S7_ambiguous=['0 085','0 143'],S5_Sulfur='<0.01',labels=['S116','S1127'],S17_N2DFT_header='also says t-plot',S6_ADAG_max=4.64,body_collective_range_max=4.68),'Preserveprintedambiguouscells asnull, censoredlimitnotzero; printedlabels andreferencednumbers retained; bodycollectiverange not assigned to anysample.')
    # Egg/rice: all six final materials and six actual prechars.
    eg_names=['WPAC-1','WPAC-2','WPAC-0','YPAC-1','YPAC-2','YPAC-0'];egt1='molecules-28-06543-t001';egt2='molecules-28-06543-t002'
    for i,s in enumerate(eg_names):
        pre=s.replace('PAC','PC');feedstock=('egg_white'if s.startswith('W')else'egg_yolk')+('_plus_waste_rice'if s[-1]!='0'else'_without_rice');reg(EG,s,'final_biomass_carbon_before_test',feedstock);reg(EG,pre,'precarbonized_biomass_before_activation',feedstock);spec['lineage'].append(dict(doi=EG,parent=pre,child=s,kind='separate600C_KOH_activation'))
        row=i+3
        for col,f,u in [(1,'BET_surface_area_m2_g','m2/g'),(2,'micropore_surface_area_m2_g','m2/g'),(3,'micropore_volume_cm3_g','cm3/g'),(4,'total_pore_volume_cm3_g','cm3/g'),(5,'author_micropore_volume_fraction_pct','%')]:fact(EG,s,egt1,row,col,f,u,'N2BET P/P0.005-.05; tplotVmicro; Vtotal at.99; ownTable1 dominates prosecm2/g unittypo')
        for col,f,u in [(1,'bulk_EA_C_wt_pct','wt%'),(2,'bulk_EA_H_wt_pct','wt%'),(3,'bulk_EA_N_wt_pct','wt%'),(4,'bulk_EA_O_wt_pct','wt%'),(5,'author_bulk_H_C_mass_ratio','ratio'),(6,'author_bulk_O_C_mass_ratio','ratio'),(7,'author_bulk_OplusN_C_mass_ratio','ratio'),(8,'author_product_yield_pct','%')]:fact(EG,s,egt2,i+2,col,f,u,'Vario bulk elemental analysis massratios numerically consistent; distinctfromXPS surfacepercent; yieldbasis not overdefined')
        mix={'1':1,'2':1.5,'0':0}[s[-1]];stages=[dict(stage='mixed_feed_preparation',egg_to_rice_mass_ratio=[1,mix],liquid_N2_freeze=True,freeze_dry_h=72),dict(stage='precarbonization',temperature_C=600,duration_h=2,heating_rate_C_min=2,atmosphere='N2')]
        synth(EG,pre,'MainP15 two actualstages, not a single4h hold',stages)
        synth(EG,s,'MainP15 KOHexplicit vs reagentparagraph dissent',stages+[dict(stage='activation',temperature_C=600,duration_h=2,heating_rate_C_min=2,atmosphere='N2',flow_mL_min=25,char_to_activator_mass_ratio=[1,4],activator='KOH'),dict(stage='acid_wash',reagent='HCl',concentration_wt_pct=10,wash_repeats=3)])
    for names,values,uid,document,locator in [(eg_names[:3],['.75','.89','.85'],'Raman_SI_W',KEYS[EG]+'_SI','SIp2actualFigS1b Wseries printedratios'),(eg_names[3:],['.80','.87','.80'],'Raman_main_Y',KEYS[EG]+'_Fig3','ActualMainFig3b Yseries printedratios')]:
        u=unit(EG,uid,['sample','ID_IG'],list(zip(names,values)),locator,document)
        for row,s in enumerate(names,1):fact(EG,s,u,row,1,'Raman_ID_IG','ratio','Own printed intensityratio notarea; samplelabels matched actualpanel')
    u=unit(EG,'Main_P8_XPS',['sample','C','N','O'],[['YPAC-1','87.76','2.81','10.14']],'MainP8 XPSpercent basis unspecified; sum100.71 not normalized')
    for col,e in enumerate(['C','N','O'],1):fact(EG,'YPAC-1',u,1,col,'XPS_'+e+'_reported_pct','%basis_unspecified','AuthorXPS surfacepercent; no atom/wt basis specified, no normalization','conflict_XPS_sum100point71_and_basis_unspecified')
    egcond=dict(system='3E',electrolyte='KOH',concentration_mol_L=6,voltage_lower_V=-1,voltage_upper_V=0,reference_electrode='HgO/Hg (reported order)',capacitance_basis='I_dt_over_m_dV_author_working_mass',physical_test_group='doi:'+EG+'#YPAC1_3E',active_mass_mg=None)
    u=unit(EG,'Main_P11_fresh_and_cycle',['sample','C1','C20','cyclej','retention','Rs_first','Rct','Rs_second'],[['YPAC-1','446.22','136.55','10','82.26','2.43','.73','.107']],'MainP11 completeparagraph; explicit10Agconstantcurrentcycles, conflictingtwoRs; SI S2 confirmsfreshlabels')
    cap(EG,'YPAC-1',u,1,1,1,'reported_aqueous_3e_GCD_capacitance',**egcond);cap(EG,'YPAC-1',u,1,2,20,'reported_aqueous_3e_GCD_capacitance',**egcond)
    for col,m,un in [(3,'cycling_reported_current_A_g','A/g'),(4,'capacitance_retention','%'),(5,'Rs_competing_report_1','ohm'),(6,'Rct','ohm'),(7,'Rs_competing_report_2','ohm')]:response(EG,'YPAC-1',u,1,col,m,un,cycle_count=10000 if col in [3,4]else None,system='3E',conflict=col in [5,7])
    spec['identity_links'].append(dict(doi=EG,sample='YPAC-1',existing_endpoint_id='candidate:TE009',new_reported_current_A_g=10,previous_reported_current_A_g=None,source_document=KEYS[EG],locator='bodyP11 exact sentence: YPAC-1 also underwent 10 A g−1 constant-current charge/discharge cycles.',correction='Previousreview saidcurrentnotlocated; originalXMLalreadycontains explicitcyclecurrent. Realmissedextraction, notnewexternaldata.',not_new_cycling_endpoint=True,formal_admission_pending_cycling_version=True))
    issue(EG,'old_missed_cycling_current',dict(existing_endpoint='candidate:TE009',old_claim='cyclingcurrentnotlocated',P11current_A_g=10),'Correctmissedextraction with exactoriginalparagraph; preserveoldreview androuteexistingendpoint tocyclingincrement, notduplicateendpoint.')
    issue(EG,'method_basis_and_Rs',dict(XPS_sum=100.71,EA='bulk mass%',XPS_basis='unspecified',Rs=[2.43,.107],reagent_paragraph='potassiumcarbonate(KOH85%)',preparation='explicitKOH'), 'No EA→XPSinheritance orpercentrenormalization; selectexplicitrecipeKOHretainreagentdissent; Rscompeting reports excludedfrompredictors. Fig4cO1s/Fig4dN1s peractualaxes, prosepaneltypo retained.')
    # Tobacco: four final materials, one combined activation/carbonization stage.
    tn=['YAC','N-YAC0.5','N-YAC1','N-YAC2'];tt1='molecules-28-08136-t001';tt2='molecules-28-08136-t002'
    for row,s in enumerate(tn,2):
        reg(TO,s,'final_biomass_carbon_before_test','tobacco_straw_with_melamine'if s!='YAC'else'tobacco_straw_no_melamine')
        for col,f,u in [(1,'BET_surface_area_m2_g','m2/g'),(2,'total_pore_volume_cm3_g','cm3/g'),(3,'author_BJH_mesopore_volume_cm3_g','cm3/g'),(4,'author_HK_micropore_volume_cm3_g','cm3/g'),(5,'author_mesopore_volume_fraction_pct','%'),(6,'average_pore_diameter_reported_nm','nm')]:fact(TO,s,tt1,row,col,f,u,'OwnTable1; Fig3b HK<2nm/BJH>2nm; differentmodelvolumesnotadditive; noforcedpartition')
        x=0 if s=='YAC'else float(s[5:]);synth(TO,s,'MainP28-31 actualserieslabels vs P29x=0.5,2,2typo',[dict(stage='raw_preparation',particle_size_mesh=100,drying_temperature_C=80,drying_h=12),dict(stage='single_carbonization_activation',temperature_C=800,duration_h=100/60,raw_hold_duration_min=100,heating_rate_C_min=10,atmosphere='Ar',activator='K2CO3',melamine_to_feedstock_mass_ratio=x,feedstock_melamine_K2CO3_mass_ratio=[1,x,2]),dict(stage='acid_wash',reagent='HCl',concentration_M=1,duration_min=30),dict(stage='drying',temperature_C=120,duration_h=12)])
    for row,s in [(3,'YAC'),(4,'N-YAC0.5')]:
        fact(TO,s,tt2,row,1,'XPS_N_at_pct','at%','OwnTable2 explicitat% totalN; components percentagewithinN')
        for col,f in enumerate(['N6','N5','NQ','NX'],2):fact(TO,s,tt2,row,col,'XPS_'+f+'_fraction_within_N_pct','%ofN','OwnTable2 relativepeakcomponents, notwholematerialNatom%; dashnotzero')
    u=unit(TO,'ActualFig4b_Raman',['sample','IDIG'],list(zip(tn,['1.13','1.10','1.05','1.17'])),'ActualprintedFig4b ratios, MainP12',KEYS[TO]+'_Fig4')
    for row,s in enumerate(tn,1):fact(TO,s,u,row,1,'Raman_ID_IG','ratio','ActualFig4b author intensityratio')
    u=unit(TO,'ActualFig5_atomic',['sample','C','O','N'],[['YAC','89.32','10.14','.54'],['N-YAC0.5','91.81','6.34','1.85']],'ActualFig5a/d explicitAtomic% (captionpanelorder wrong); sumcheck',KEYS[TO]+'_Fig5')
    for row,s in enumerate(['YAC','N-YAC0.5'],1):
        for col,e in enumerate(['C','O','N'],1):fact(TO,s,u,row,col,'XPS_'+e+'_at_pct','at%','ActualsurveyAtomic%labels, notEDSmapquantification')
    u=unit(TO,'Main_P22_fresh',['sample','C1'],[['N-YAC0.5','338'],['YAC','288']],'MainP22 own3E freshGCD1Ag, Table3ownrepeatnotanotherlabel')
    for row,s in enumerate(['N-YAC0.5','YAC'],1):cap(TO,s,u,row,1,1,'reported_aqueous_3e_GCD_capacitance',system='3E',electrolyte='KOH',concentration_mol_L=6,voltage_lower_V=-1,voltage_upper_V=0,reference_electrode='Hg/HgO',capacitance_basis='I_dt_over_m_dV_author_working_mass',active_mass_mg=4,active_mass_status='approximately',physical_test_group='doi:'+TO+'#'+s+'_3E',fresh_CV_GCD_graph_cycle=5)
    u=unit(TO,'Main_abstract_rate_dissent',['sample','C20','retention_abstract','retention_body'],[['N-YAC0.5','288','85.2','82']],'Abstract vsMainP22/conclusion40/actualFig6f separateclaims notsameascycle91.85')
    cap(TO,'N-YAC0.5',u,1,1,20,None,system='3E',electrolyte='KOH',concentration_mol_L=6,capacitance_basis='author_single_electrode',physical_test_group='doi:'+TO+'#NYAC05_3E',target_conflict='body82% vsabstract85.2% and288Fg; numeric20labelnotselected')
    response(TO,'N-YAC0.5',u,1,2,'rate_retention_competing_abstract','%',current_A_g=20,reference_current_A_g=1);response(TO,'N-YAC0.5',u,1,3,'rate_retention_competing_body','%',current_A_g=20,reference_current_A_g=1)
    u=unit(TO,'Main_P24_device',['sample','Cs','j','retention','cyclej','CE'],[['N-YAC0.5','166.25','.5','91.85','1','97.44']],'MainP24 Eq3/5 andactualFig7c/f caption; device1MNa2SO4, fifthfreshcycle not cyclingbaseline')
    cap(TO,'N-YAC0.5',u,1,1,.5,'reported_aqueous_2e_factor4_Cs',system='2E',electrolyte='Na2SO4',concentration_mol_L=1,voltage_lower_V=0,voltage_upper_V=1.6,capacitance_basis='single_electrode_Cs_4I_dt_over_total_two_active_masses_dV',physical_test_group='doi:'+TO+'#NYAC05_symmetric_Na2SO4',fresh_CV_GCD_graph_cycle=5)
    response(TO,'N-YAC0.5',u,1,3,'capacitance_retention','%',cycle_count=5000,current_A_g=1,system='2E');response(TO,'N-YAC0.5',u,1,5,'coulombic_efficiency','%',system='2E',author_approximate=True)
    spec['candidates'].append(dict(candidate_id='LP19:Tobacco:NYAC05_2E',doi=TO,sample='N-YAC0.5',record=dict(retention_pct=91.85,cycle_count=5000,reported_current_A_g=1,method='GCD',system='2E',electrolyte='Na2SO4',concentration_mol_L=1,cycle_voltage_lower_V=None,cycle_voltage_upper_V=None,characterization_voltage_lower_V=0,characterization_voltage_upper_V=1.6,basis='MainP24+Fig7fcaption; localcyclevoltagepending, freshFig7cnotautomaticallycyclingvoltage',fresh_graph_reference_cycle=5)))
    issue(TO,'rate_and_pore_models',dict(abstract_retention=85.2,abstract_C20=288,body_retention=82,own_1Ag=338,pore_models=['HK','BJH'],Vtotal_0point5=1.53,Vmeso_0point5=.71,Vmicro_0point5=.98),'C20abstractnotselecteduntilboundedactualpointreview; nochoosingbyperformance. HK/BJHvolumesseparatemethodsnotforcedsum; sourcefractionsretainednotrecomputed. No extra second thermalstage.')
    issue(TO,'aliases_and_fifth_measurement',dict(N_PAC='N-YAC authorinconsistentabbreviation',method_x='0.5,2,2',actual_x=[.5,1,2],graph_reference_cycle=5,cycling_endpoint=5000),'Actualtable/legendseriesused, authoraliasesretained; fifthCV/GCDcycleappliesfreshgraphs, notinitialretentionreference; 2E factor4Cs separatedfromfactor2 anddeviceCd.')
    for doi in KEYS:
        spec['annotations'].append(dict(id='V19_'+KEYS[doi]+'_scope',doi=doi,document=KEYS[doi],scope='Methods, ownmain/SItables, exactprintedlabels andmainfigure scope reviewed; untranscribed waveforms remain',full_source_review_complete=False))
    write(OUT/'curation_spec.json',spec);print({k:len(v)for k,v in spec.items()})

# The new additive build is below; all v18 rows are preserved byte-for-byte.

def build():
    assert sha(PARENT)==PSHA and not DB.exists()and not(OUT/'merge_manifest.json').exists()
    spec=json.loads((OUT/'curation_spec.json').read_text('utf8'));docs={d['key']:d for d in spec['documents']}
    with closing(ro(PARENT))as parent,closing(sqlite3.connect(DB))as c:
        parent.backup(c);c.row_factory=sqlite3.Row;c.execute('pragma foreign_keys=on')
        c.executescript('''create table source_reviews_v19(doi text primary key references reviewed_sources,record_json text);create table cell_extractions_v19(kind text,record_id text,table_key text references reviewed_tables,row_ordinal integer,column_ordinal integer,primary key(kind,record_id));create table decisions_v19(decision_id text primary key,doi text references reviewed_sources,record_json text);create table material_feature_decisions_v19(material_key text references materials,field_name text,record_json text,primary key(material_key,field_name));create table purpose_reviews_v19(observation_id text primary key references capacitance_observations,purpose text,eligible integer,record_json text);create table figure_scope_reviews_v19(doi text references reviewed_sources,figure_number integer,document_key text references source_documents,record_json text,primary key(doi,figure_number));create table annotations_v19(annotation_id text primary key,doi text references reviewed_sources,document_key text references source_documents,record_json text);create table cycle_identity_links_v19(link_id text primary key,record_json text);''')
        for s in spec['sources']:insert(c,'reviewed_sources',dict(doi=s['doi'],path=s['path'],sha256=s['sha256'],title=s['title'],stage='Own main tables and17SI physical tables, stage/method/printed-label review; untranscribed waveforms remain'))
        for d in docs.values():assert sha(ROOT/d['path'])==d['sha256'];insert(c,'source_documents',dict(document_key=d['key'],doi=d['doi'],path=d['path'],sha256=d['sha256'],role=d['role']))
        for t in spec['tables']+spec['units']:
            key=t['doi']+'#'+t['id'];rows=[[v['raw']for v in r]for r in t['grid']]if'grid'in t else t['rows'];insert(c,'reviewed_tables',dict(table_key=key,doi=t['doi'],xml_id=t['id'],caption=t.get('caption',t['id']),header_json=json.dumps(rows[0]if'grid'in t else t['header']),footnote=t.get('footnote','Own bounded transcription; stages/repeats/foreign comparisons kept distinct'),source_raw_table_id=t.get('raw_table_id')));insert(c,'table_source_links',dict(table_key=key,document_key=t['document'],locator=t['locator']));insert(c,'extraction_units_v3',dict(table_key=key,kind=t['kind'],scope='Own explicitly bound cells only; foreign rows retained as context, never admitted'))
            for i,row in enumerate(rows,1):insert(c,'transcribed_rows',dict(table_key=key,row_ordinal=i,cells_json=json.dumps(row,ensure_ascii=False)));insert(c,'transcription_origins_v7',dict(table_key=key,row_ordinal=i,origin_json=json.dumps(t['grid'][i-1]if'grid'in t else dict(document=t['document'],locator=t['locator'],row=i),ensure_ascii=False)))
            if t.get('raw_table_id'):
                assert c.execute('select review_state from raw_table_queue where table_id=?',(t['raw_table_id'],)).fetchone()[0]=='automatic_candidate_unreviewed'
                c.execute('update raw_table_queue set review_state=?where table_id=?',('v19_own_cells_methods_stage_and_conflicts_reviewed',t['raw_table_id']))
        for r in spec['materials']:
            insert(c,'materials',dict(material_key=mk(r['doi'],r['sample']),doi=r['doi'],sample_name=r['sample'],material_stage=r['stage']));insert(c,'material_scopes_v8',dict(material_key=mk(r['doi'],r['sample']),scope_json=json.dumps(dict(origin_class='PEO_assisted_biomass_carbon'if'PEO_assisted'in r['stage']else'biomass_carbon'if'carbon'in r['stage']else'raw_or_intermediate_biomass',feedstock=r['feedstock'],stage=r['stage'],not_assumed_pure_carbon=True,same_source_not_independent=True))))
        def cell(r):
            key=r['doi']+'#'+r['id'];raw=json.loads(c.execute('select cells_json from transcribed_rows where table_key=?and row_ordinal=?',(key,r['row'])).fetchone()[0])[r['col']];return key,raw,number(raw)
        def receipt(kind,rid,r,key):insert(c,'cell_extractions_v19',dict(kind=kind,record_id=str(rid),table_key=key,row_ordinal=r['row'],column_ordinal=r['col']))
        for r in spec['facts']:
            key,raw,value=cell(r);doc=c.execute('select document_key from table_source_links where table_key=?',(key,)).fetchone()[0];q=insert(c,'material_facts',dict(material_key=mk(r['doi'],r['sample']),field_name=r['field'],value=value,raw_value=raw,unit=r['unit'],method=r['method'],table_key=key,row_ordinal=r['row'],column_ordinal=r['col'],source_sha256=docs[doc]['sha256'],review_status=r['status'],training_eligible=0));receipt('fact',q.lastrowid,r,key)
        for r in spec['caps']:
            key,raw,value=cell(r);rid=key+'#'+str(r['row'])+'#'+str(r['col']);cond=dict(extraction_batch='v19',current_mass_basis='author_reported_unknown_not_inferred',repeat_reports_not_independent=True);cond.update(r['conditions'])
            insert(c,'capacitance_observations',dict(observation_id=rid,material_key=mk(r['doi'],r['sample']),table_key=key,row_ordinal=r['row'],column_ordinal=r['col'],value=value,raw_value=raw,unit='F/g',method='GCD',system=cond['system'],electrolyte=cond['electrolyte'],concentration_mol_L=cond['concentration_mol_L'],current_A_g=r['j'],scan_rate_mV_s=None,conditions_json=json.dumps(cond,ensure_ascii=False),status='own_reported'if r['purpose']else'own_repeat_or_competing_report',source_group='doi:'+r['doi'],training_eligible=0));receipt('capacitance',rid,r,key)
            if r['purpose']:
                reason='Own bound fresh GCD with method-qualified configuration/electrolyte/formula; optional missing features remain masks; source/sample/current repeated reports deduplicated by purpose'
                insert(c,'purpose_reviews_v19',dict(observation_id=rid,purpose=r['purpose'],eligible=1,record_json=json.dumps(dict(reason=reason,purpose_input_ready=True,cyclic_retention_training_admitted=False,training_authorized=False))))
                if r['purpose']=='reported_aqueous_3e_GCD_capacitance':insert(c,'auxiliary_gcd_reviews_v3',dict(observation_id=rid,purpose=r['purpose'],eligible=1,reason=reason,review_basis='Own specific results/actual printed plot and matched own protocol, variants retained; no performance-based selection'))
        for r in spec['responses']:
            key,raw,value=cell(r);rid=key+'#'+str(r['row'])+'#'+str(r['col']);insert(c,'outcome_observations_v3',dict(outcome_id=rid,material_key=mk(r['doi'],r['sample']),table_key=key,record_json=json.dumps(dict(source_group='doi:'+r['doi'],extraction_batch='v19',metric=r['metric'],value=value,raw_value=raw,unit=r['unit'],**(dict(feature_role='test_or_process_response_not_pretest_predictor')|r['conditions'])),ensure_ascii=False),training_eligible=0));receipt('response',rid,r,key)
        for r in spec['synthesis']:insert(c,'synthesis_stages_v3',dict(material_key=mk(r['doi'],r['sample']),document_key=r['document'],locator=r['locator'],stages_json=json.dumps(r['stages'],ensure_ascii=False)))
        for r in spec['feature_decisions']:insert(c,'material_feature_decisions_v19',dict(material_key=mk(r['doi'],r['sample']),field_name=r['field'],record_json=json.dumps(r,ensure_ascii=False)))
        for r in spec['decisions']:insert(c,'decisions_v19',dict(decision_id=r['id'],doi=r['doi'],record_json=json.dumps(r,ensure_ascii=False)));insert(c,'scientific_issues',dict(issue_id=r['id'],doi=r['doi'],sample_name=None,issue_json=json.dumps(dict(kind=r['id'],action=r['decision']),ensure_ascii=False)))
        for r in spec['figures']:insert(c,'figure_scope_reviews_v19',dict(doi=r['doi'],figure_number=r['figure_number'],document_key=r['document'],record_json=json.dumps(r,ensure_ascii=False)))
        for r in spec['annotations']:insert(c,'annotations_v19',dict(annotation_id=r['id'],doi=r['doi'],document_key=r['document'],record_json=json.dumps(r,ensure_ascii=False)))
        for r in spec['identity_links']:insert(c,'cycle_identity_links_v19',dict(link_id='LP19_'+r['existing_endpoint_id'],record_json=json.dumps(r,ensure_ascii=False)))
        sources={r['doi']:r for r in spec['sources']}
        for r in spec['candidates']:insert(c,'test_candidates',dict(candidate_id=r['candidate_id'],material_key=mk(r['doi'],r['sample']),record_json=json.dumps(dict(r['record'],source_group='doi:'+r['doi'],source_year=sources[r['doi']]['year'],evidence_source_path=sources[r['doi']]['path'],source_sha256=sources[r['doi']]['sha256'],current_mass_basis='author_reported_unknown_not_inferred',baseline_cycle=None,baseline_reference='author_reference_not_assumed_cycle1'),ensure_ascii=False),training_eligible=0))
        for s in spec['sources']:
            review=dict(source_year=s['year'],classification=s['classification'],scope='Ownmain tables,17ligninSI physical tables,methods/exactlabels andmainfigure scope; Egg/TobaccoSIscope',remaining='Continuous spectra/isotherms/CV/GCD/EIS, remaining rate markers and quantitative SIfigures; lignin fullSI spectral pages not all visually reviewed. Conflicts and source-specific purposes remain.',full_source_review_complete=False)
            insert(c,'source_scope_decisions',dict(doi=s['doi'],scope=review['scope'],reason=review['remaining'],evidence_json=json.dumps(review,ensure_ascii=False),full_source_review_complete=0));insert(c,'source_reviews_v19',dict(doi=s['doi'],record_json=json.dumps(review,ensure_ascii=False)))
        c.executescript('create table raw_candidate_dispositions_v19(table_id text primary key references raw_table_queue,record_json text);create table numeric_details_v19(fact_id integer primary key references material_facts,record_json text);create table material_lineage_v19(lineage_id integer primary key,parent_key text references materials,child_key text references materials,record_json text);')
        for r in spec['raw_dispositions']:
            c.execute('update raw_table_queue set review_state=?where table_id=?',(r['disposition'],r['table_id']));insert(c,'raw_candidate_dispositions_v19',dict(table_id=r['table_id'],record_json=json.dumps(r,ensure_ascii=False)))
        for r in c.execute('select f.fact_id,f.raw_value,f.method from material_facts f join cell_extractions_v19 x on x.record_id=cast(f.fact_id as text)and x.kind="fact"').fetchall():
            nd=numeric_details(r['raw_value'])
            if 'mean±SD'in r['method']:nd['uncertainty_kind']='author_mean_and_SD'
            insert(c,'numeric_details_v19',dict(fact_id=r['fact_id'],record_json=json.dumps(nd,ensure_ascii=False)))
        for r in spec['lineage']:insert(c,'material_lineage_v19',dict(parent_key=mk(r['doi'],r['parent']),child_key=mk(r['doi'],r['child']),record_json=json.dumps(r,ensure_ascii=False)))
        c.commit()
    protected={ROOT/d['path']for d in docs.values()}|{PARENT,ROOT/'循环稳定性数据库_v0.25_芒果核皮革循环准入_20261026/cycling_v0_25.sqlite',ROOT/'全库复检与特征补提取_20261021/full_corpus_search_native.sqlite'}
    write(OUT/'protected_inputs.json',dict(files=[dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p),bytes=p.stat().st_size)for p in sorted(protected)]));print('Built unsealed v19; no cycling admission or model fitting')

if __name__=='__main__':
    if len(sys.argv)!=2 or sys.argv[1]not in ['curate','build']:raise SystemExit('One-use curate/build only before sealing')
    globals()[sys.argv[1]]()
