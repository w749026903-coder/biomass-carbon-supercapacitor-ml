"""Save explicit evidence dispositions and reproducible bounded plot captures."""
from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.extract_alpc_v6 import OUT,DOI,MAIN,SI,TABLE,FIELDS,HELD,write,sha

def prepare():
    assert not(OUT/'merge_manifest.json').exists()
    # Bounded marker readout from the rendered own Fig7e; no smoothing or
    # forced monotonicity (the black 7->8A/g rise is retained).
    import numpy as np
    from PIL import Image
    import pypdfium2 as pdf
    evidence=OUT/'evidence';evidence.mkdir(exist_ok=True)
    for source,nums,prefix in [(SI,[6],'SI'),(MAIN,[3,5,9],'main')]:
        doc=pdf.PdfDocument(ROOT/source)
        for n in nums:
            dest=evidence/(prefix+'_p'+str(n)+'.png')
            if not dest.exists():
                page=doc[n-1];page.render(scale=2).to_pil().save(dest);page.close()
        doc.close()
    crop=evidence/'Figure7e_rate_review.png'
    if not crop.exists():
        Image.open(evidence/'main_p9.png').crop((460,345,755,550)).resize((1180,820)).save(crop)
    im=np.array(Image.open(OUT/'evidence/Figure7e_rate_review.png').convert('RGB'))
    x0,x10,y0,y400=272,1018,655,60
    rough={'ALPC-700':[170,132,110,94,82,73,60,63,58,37],'ALPC-800':[421,364,331,307,283,271,256,246,238,229],'ALPC-900':[264,211,185,172,158,151,141,137,130,128]};captures=[]
    for sample,values in rough.items():
        for j,v in enumerate(values,1):
            xc=x0+(x10-x0)*j/10;yc=y0-v*(y0-y400)/400
            xa,xb=int(xc-9),int(xc+10);ya,yb=max(0,int(yc-12)),int(yc+13);a=im[ya:yb,xa:xb].astype(int)
            mask=(a[:,:,0]>170)&(a[:,:,1]<145)&(a[:,:,2]<145)if sample.endswith('800')else(a[:,:,2]>150)&(a[:,:,0]<145)&(a[:,:,1]<170)if sample.endswith('900')else(a.max(2)<115)
            ys,xs=np.where(mask);assert len(ys)>6
            px=xa+float(np.median(xs));py=ya+float(np.median(ys));v=round((y0-py)*400/(y0-y400),1)
            captures.append(dict(sample_name=sample,current_A_g=j,readout_F_g=v,readout_interval_F_g=[round(v-8,1),round(v+8,1)],pixel_center=[px,py],color_pixels=int(len(ys)),capture_role='author_anchor_confirmation_not_extra_experiment'if j==1 else'new_graph_condition',current_axis_tolerance_A_g=.1,uncertainty_kind='conservative_pixel_readout_envelope_not_SD_or_CI'))
    write(OUT/'graph_rate_captures.json',dict(figure='main physicalp9 Fig7e',image='evidence/Figure7e_rate_review.png',image_sha256=sha(OUT/'evidence/Figure7e_rate_review.png'),axis_calibration=dict(x0=x0,x10=x10,y0=y0,y400=y400),captures=captures,unique_conditions=30,author_anchors=3,net_new_conditions=27,full_continuous_curves_complete=False))
    table=dict(source_path=SI,source_sha256=sha(ROOT/SI),page=6,table='S1',evidence_image='evidence/SI_p6.png',image_sha256=sha(OUT/'evidence/SI_p6.png'),transcription_method='Visual reading of raster table; pypdf text contains only caption. Not claimed independent OCR.',fields=FIELDS,rows=TABLE,own_numeric_cells=21,held_cells=[dict(sample=n,field=f,value=TABLE[n][FIELDS.index(f)])for n,f in sorted(HELD)],header_basis='FESEM-EDX atomic percent; cc/g explicitly converted to cm3/g with factor1')
    write(OUT/'TableS1_visual_transcription.json',table)
    sec=[]
    def row(table,name,ref,**values):sec.append(dict(comparison_id=table+':'+str(ref),table=table,precursor=name,cited_reference_number=ref,values=values,source_path=SI,source_sha256=sha(ROOT/SI),role='secondary_comparison_not_new_primary_experiment',ready_for_training_inputs=False,original_primary_protocol_not_reviewed=True))
    for name,onset,current,ref in [('Dandelion seed',.83,4.98,1),('Lotus root',.84,4.4,2),('Cattail fibres',.92,4.8,3),('Mulberry leaves',.86,3.2,4),('Enoki mushroom',.94,4.9,5),('Water hyacinth',.98,4.15,6),('Plum blossoms',.95,5.96,7)]:row('S2',name,ref,onset_V_RHE=onset,limiting_current_mA_cm2=current,rpm=1600,system='ORR')
    for name,j,cap,ref in [('Bamboo fiber',1,328,8),('Crop waste',1,317,9),('European deciduous trees',.25,74,10),('Lemon peel',1,121,11),('Pinecone',.5,185,12),('Moringa oleifera leaves',1,201,13),('Aesculus turbinata seeds',.5,142,14),('Prosopis juliflora stems',.5,307.14,15),('Watermelon peels',.5,278,16),('Jackfruit seeds',1,261.3,17)]:row('S5',name,ref,current_A_g=j,specific_capacitance_F_g=cap,electrolyte='1M H2SO4',configuration='3e')
    for name,window,e,p,ref in [('Onion skin',1.4,17,150.6,18),('Ant powder',1.6,24.20,400,19),('Bamboo fiber',1.8,21.2,454,8),('Perilla frutescens',1.8,14.8,490,20),('Bacterial cellulose',1.8,20.4,81.8,21),('Corn husk',1.8,21,875,22),('Willow catkin',1.8,21,180,23),('Auricularia fungus',1.8,22,100,24),('Cotton stalk',1.8,18.14,450,25),('Rice wine lees',1.8,17.8,450,26),('Pomelo',1.8,14.70,450,27)]:row('S6',name,ref,window_V=window,energy_Wh_kg=e,power_W_kg=p,electrolyte='1M Na2SO4'if ref!=27 else'0.5M Na2SO4',configuration='2e')
    dft=[]
    for intermediate,dist,energy in [('O2',2.97,3.1575),('OOH',1.61,1.1320),('O',1.41,.3537),('OH',1.48,-3.6699),('H2O',3.25,-7.9249)]:dft.append(dict(report_id='ALPC_DFT:'+intermediate,adsorbate=intermediate,host='epoxide_functionalized_N_doped_graphene_model_not_experimental_ALPC_material',bond_distance_A=dist,adsorption_free_energy_eV=energy,source_path=SI,source_sha256=sha(ROOT/SI),tables=['S3','S4'],role='computed_ORR_separate_not_supercapacitor_label_or_measured_feature',ready_for_training_inputs=False))
    write(OUT/'secondary_and_DFT_tables.json',dict(secondary_rows=sec,secondary_count=len(sec),DFT_rows=dft,DFT_cells=10,own_comparison_rows=[dict(table='S2',system='ORR',not_cycle=True),dict(table='S5',value=409,unit='F/g',alternate_to_own_body421=True),dict(table='S6',energy_Wh_kg=21.15,power_W_kg=450,duplicate_of_body_not_extra_experiment=True)],all_tables_S1_to_S6_accounted_for=True))
    coverage=[]
    def cv(unit,status,source=MAIN,**extra):coverage.append(dict(doi=DOI,unit_id=unit,status=status,source_path=source,source_sha256=sha(ROOT/source),full_paper_complete=False,**extra))
    cv('Main_methods','sample shared synthesis and supercapacitor electrode protocol structured; ORR separated')
    cv('Main_Fig1','Raman ratios structured; shared approximate peak positions metadata; continuous spectra pending')
    cv('Main_Fig2','morphology scope located; TableS1 EDX structured; pixel morphology descriptors not invented')
    cv('Main_Fig3','XPS N/O atomic structured; component fits/continuous spectra pending')
    for n in [4,5,6]:cv('Main_Fig'+str(n),'ORR/computational scope indexed, not capacitance retention; full numerical traces pending')
    cv('Main_Fig7','30 bounded rate markers captured,3 anchor duplicates; acid CV seven-value rate order unresolved; continuous CV/GCD/EIS pending')
    cv('Main_Fig8','two existing 3e cycles linked; neutral GCD/CV anchors and device report structured; continuous traces pending')
    cv('SI_instrumentation','source and measurement methods read; apparatus settings not independent material samples',SI)
    cv('SI_TableS1','21 own numeric cells transcribed,3 micropore/total consistency questions held,18 selected',SI,own_numeric_cells=21,held_cells=3)
    cv('SI_TableS2','7 secondary ORR comparisons indexed; own ORR not capacitance',SI)
    for n in [3,4]:cv('SI_TableS'+str(n),'5 own computational cells indexed separately, not experimental material labels',SI)
    cv('SI_TableS5','10 secondary comparisons indexed, own409 vs main421 alternate retained',SI)
    cv('SI_TableS6','11 secondary comparisons indexed, own Ragone pair duplicate retained',SI)
    for n in range(1,18):
        status='caption and scope indexed; full curve/image numerical extraction pending'
        if n in [5,6,7,8,9,10]:status='ORR curve/post-ORR state; not supercapacitor feature or retention; numerical traces pending'
        if n in [11,12,13]:status='computed graphene geometry/AIMD scope; not measured final carbon features'
        if n in [14,15,16,17]:status='supercapacitor additional curve scope located; full numerical extraction pending'
        cv('SI_FigS'+str(n),status,SI)
    write(OUT/'extraction_coverage.json',coverage)
    write(OUT/'remaining_source_actions.json',dict(full_source_complete=False,actions=['Resolve original micropore table anomalies through an author correction or defensible raw analysis; never swap/renormalize numbers to force validity.','Continue acidic CV rate mapping, SI S14/S16 neutral/acid CV/GCD waveforms and main/SI remaining continuous curves.','Keep 421/409 and device1/10A/g alternates visible; no new cycling admission in this batch.','Continue remaining local main3e source queue and fixed37 evidence review.'],model_fits=0))
    print('21 TableS1 cells,28 secondary rows,10 DFT cells and33 coverage units saved')

if __name__=='__main__':prepare()
