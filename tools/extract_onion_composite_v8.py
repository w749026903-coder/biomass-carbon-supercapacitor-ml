"""Additive source-qualified Onion and PAN/biochar extraction. No model fitting."""
from pathlib import Path
from contextlib import closing
import csv,hashlib,io,json,math,re,sqlite3,sys,xml.etree.ElementTree as E,zipfile
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tools'))
from extract_palm_kernel_v7 import xml_grid
OUT=ROOT/'文献全量利用复核_20261026/批次08_洋葱壳与生物炭复合';DB=OUT/'literature_material_pool_v8.sqlite'
PARENT=ROOT/'文献全量利用复核_20261026/批次07_棕榈壳与串并联/literature_material_pool_v7.sqlite'
PARENT_SHA='357822c5d605897e540f5d2e7b01edd3e2224eeadf93aea706d5a9549152f9df'
ONION='10.1016/j.heliyon.2024.e32915';GELS='10.3390/gels10010082'
OB=ROOT/'文献扩充_大批补齐_20261018/sources/SUP_109';GB=ROOT/'文献扩充_大批补齐_20261018/sources/SUP_038'
def text(e):return ' '.join(''.join(e.itertext()).split()) if e is not None else ''
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf8')
def ro(p):return sqlite3.connect(Path(p).resolve().as_uri()+'?mode=ro',uri=True)
def mk(doi,sample):return 'literature:'+hashlib.sha256((doi+'\0'+sample).encode()).hexdigest()[:24]
def number(raw,mode='decimal'):
    if raw in ['–','—','',None]:return None
    raw=str(raw)
    if mode=='cap_prefix':raw=re.match(r'([\d.,]+)\s*F/g',raw)[1]
    if mode=='approx':raw=raw.removeprefix('~')
    if not re.fullmatch(r'\d+(?:[.,]\d+)?',raw):raise ValueError(raw)
    return float(raw.replace(',','.'))
def insert(c,table,v):
    keys=list(v);return c.execute('insert into '+table+' ('+','.join(keys)+') values ('+','.join('?' for _ in keys)+')',[v[k] for k in keys])

def curve_samples():
    """Deterministic image readings with calibrated axes and explicit error, never exact author labels."""
    from PIL import Image
    readings=[]
    p=OUT/'evidence/Onion_SI_image2.jpeg';im=Image.open(p).convert('RGB')
    bands={'GC_600C':(650,715,'blue'),'GC_850C':(155,215,'red'),'GC_950C':(825,875,'black'),'COH_550C':(940,1020,'green')}
    def color(rgb,name):
        r,g,b=rgb
        return (r>165 and g<135 and b<135) if name=='red' else (b>150 and r<135 and g<175) if name=='blue' else (g>130 and r<145 and b<145) if name=='green' else max(rgb)<95
    for sample,(ya,yb,hue) in bands.items():
        for n in [100,500,1000,2000,3000,4000,5000]:
            x=377+n*(1286-377)/5000;pixels=[(xx,yy) for xx in range(round(x)-3,round(x)+4) for yy in range(ya,yb+1) if color(im.getpixel((xx,yy)),hue)]
            assert pixels,(sample,n)
            best_x=min({xx for xx,_ in pixels},key=lambda xx:(-sum(px==xx for px,_ in pixels),abs(xx-x)))
            ys=[yy for xx,yy in pixels if xx==best_x];low,high=min(ys),max(ys);py=(low+high)/2
            readings.append(dict(doi=ONION,sample=sample,document='Onion_SI_cycle',curve_group=ONION+'#SI_S1b#'+sample,x_name='plotted_cycle_coordinate',x_value=n,y_name='cycle_specific_capacitance_F_g',y_value=(1021-py)*120/(1021-210),y_uncertainty=((high-low)/2+2)*120/(1021-210),pixel_y_extent=[low,high],selected_marker_column=best_x,x_uncertainty=3*5000/(1286-377),pixel_x=x,pixel_y=py,axis=dict(x0_px=377,x5000_px=1286,y0_px=1021,y120_px=210),pixel_error_y=2,pixel_error_x=3,method='sample axis coordinate; widest local colored marker column midpoint; bounds include its half-height +2px calibration; approximate, not raw instrument data',reported_current_A_g=2,baseline='No author retention normalization inferred; not first-cycle label',retention_point_admitted=False))
    p=GB/'assets/gels-10-00082-g007.jpg';im=Image.open(p).convert('RGB')
    for panel,xvalues,xzero,xhigh,xmax,yzero,yhigh,ymax in [('CV',[5,10,20,50,100],77,306,100,513,291,400),('GCD',[.5,1,2,5,10],473,703,10,512,302,400)]:
        for sample,hue,band in [('ENFAa','black',(430,508)),('ENFA-Ba','red',(330,440) if panel=='CV' else (320,435)),('ENFA-FBa','blue',(305,445) if panel=='CV' else (293,435))]:
            for value in xvalues:
                x=xzero+value*(xhigh-xzero)/xmax;pixels=[]
                for xx in range(round(x)-3,round(x)+4):
                    for yy in range(band[0],band[1]+1):
                        if (panel=='CV' and xx>250 and yy<340) or (panel=='GCD' and xx>610 and yy<350):continue # printed legend, not curve
                        if color(im.getpixel((xx,yy)),hue):pixels.append((xx,yy))
                assert pixels,(panel,sample,value)
                best_x=min({xx for xx,_ in pixels},key=lambda xx:(-sum(px==xx for px,_ in pixels),abs(xx-x)))
                ys=[yy for xx,yy in pixels if xx==best_x];low,high=min(ys),max(ys);py=(low+high)/2
                readings.append(dict(doi=GELS,sample=sample,document='Composite_Fig7',curve_group=GELS+'#Fig7'+panel+'#'+sample,x_name='scan_rate_mV_s' if panel=='CV' else 'reported_current_A_g',x_value=value,y_name='capacitance_F_g',y_value=(yzero-py)*ymax/(yzero-yhigh),y_uncertainty=((high-low)/2+2)*ymax/(yzero-yhigh),pixel_y_extent=[low,high],selected_marker_column=best_x,x_uncertainty=3*xmax/(xhigh-xzero),pixel_x=x,pixel_y=py,axis=dict(xzero_px=xzero,xhigh_px=xhigh,xmax=xmax,yzero_px=yzero,yhigh_px=yhigh,ymax=ymax),pixel_error_y=2,pixel_error_x=3,method='widest local marker column midpoint; half-height+2px bounds; legends masked by reviewed geometry',electrolyte='H2SO4',concentration_mol_L=1,system='3E',voltage_window_V=[0,1],retention_point_admitted=False))
    assert len(readings)==58
    return readings

def curate():
    if (OUT/'curation_spec.json').exists() or DB.exists():raise FileExistsError('Never overwrite curation.')
    sources=[dict(key='Onion',doi=ONION,path=(OB/'main.xml').relative_to(ROOT).as_posix(),sha256='b91e2287b5488a510324072fa05d337ec0d0619008409f2aba8f88e23156b9f9'),dict(key='Composite',doi=GELS,path=(GB/'main.xml').relative_to(ROOT).as_posix(),sha256='4fcc2bdcb87b58d240a09602332475c89d9dc8ef5768da4d8ed276821a1fcd52')];tables=[]
    with closing(ro(ROOT/'全库复检与特征补提取_20261021/full_corpus_search_native.sqlite')) as corpus:
        for source in sources:
            assert sha(ROOT/source['path'])==source['sha256'];root=E.parse(ROOT/source['path']).getroot();source['title']=text(root.find('.//article-title'))
            rawmap={r[1]:r[0] for r in corpus.execute('select table_id,locator from raw_tables_v11 where source_sha256=?',(source['sha256'],))}
            for t in root.findall('.//table-wrap'):
                loc='XML table-wrap '+t.get('id');tables.append(dict(doi=source['doi'],document=source['key'],id=t.get('id'),caption=text(t.find('caption')),locator=loc,grid=xml_grid(t),raw_table_id=rawmap[loc],kind='mixed_comparison_table' if source['key']=='Onion' and t.get('id')=='tbl3' else 'own_xml_table'))
    graph_units=[dict(doi=ONION,document='Onion',id='own_BET_p22',kind='own_numeric_prose',locator='XML body//p22',header=['sample','BET_m2_g'],rows=[['COH_550C','49'],['GC_600C','388'],['GC_850C','1924'],['GC_950C','919']]),dict(doi=ONION,document='Onion',id='own_GCD_p29',kind='own_numeric_prose',locator='XML body//p29 andFigure4/5',header=['sample','current_mA_g','capacitance_F_g'],rows=[[sample,str(j),v] for sample,values in [('GC_600C',['155.19','119','92.56','56.68']),('GC_850C',['137.6','140.1','130.9','116.4']),('GC_950C',['81.1','60.29','54.75','25.2'])] for j,v in zip([100,500,1000,2000],values)]),dict(doi=ONION,document='Onion_SI',id='own_EDAX_S4',kind='own_instrument_text_output',locator='Word document.xml paragraphs43-48 followingFigureS4; not the two layout tables',header=['element','reported_keV','mass_pct','Error_pct','at_pct','instrument_K_column'],rows=[['C','0.183','98.01','0.03','99.33','100.1747'],['Al','1.486','1.37','0.06','0.56','2.1181'],['Ca','3.690','0.35','0.07','0.10','0.7205'],['Lu','1.581','0.27','0.23','0.02','0.6398']]),dict(doi=ONION,document='Onion_SI_Dunn',id='own_Dunn_S2',kind='own_figure_label',locator='WordFigureS2 media/image7.emf; printedpercentage labels',header=['scan_mV_s','capacitive_pct','diffusion_pct'],rows=[['20','14','87'],['40','17','83'],['80','26','74'],['160','49','51']]),dict(doi=ONION,document='Onion',id='own_yield_p10',kind='own_numeric_prose',locator='XML body//p10',header=['scope','yield_wt_pct'],rows=[['COH_550C','27.5'],['activated_carbon_temperature_not_bound','8.4']]),dict(doi=ONION,document='Onion',id='own_CE_EIS_p29_p35_p36',kind='own_numeric_prose',locator='XML body//p29,p35-36',header=['sample','CE_pct_at1Ag','approx_Rct_ohm'],rows=[['GC_600C','94.7','5'],['GC_850C','98.08','1.4'],['GC_950C','95.3','4.3']]),dict(doi=GELS,document='Composite_Fig2',id='own_Raman_Fig2',kind='own_figure_label',locator='OriginalFigure2 printed IG/ID labels',header=['sample','IG_ID'],rows=[[s,v] for s,v in [('ECNF','0.975'),('ECNF-B','0.974'),('ECNF-FB','0.936'),('ENFA','0.969'),('B-ENFA','0.946'),('ENFA-B','0.914'),('FB-ENFA','0.928'),('ENFA-FB','0.907')]]),dict(doi=GELS,document='Composite',id='own_activated_Raman_XPS_p23',kind='own_numeric_prose',locator='XML body//p23',header=['sample','IG_ID','approx_XPS_F_at_pct'],rows=[['ENFA-FBa','0.898','~1.0']]),dict(doi=GELS,document='Composite_Fig4C',id='own_GCD_Fig4C',kind='own_figure_label',locator='OriginalFigure4C printedbar labels; current0.5A/g fromowncaption4 and0..0.8V programme',header=['sample','capacitance_F_g'],rows=[[s,v] for s,v in [('ECNF','29'),('ECNF-B','49'),('ECNF-FB','58'),('ENFA','65'),('B-ENFA','115'),('ENFA-B','159'),('FB-ENFA','147'),('ENFA-FB','187')]]),dict(doi=GELS,document='Composite',id='own_3E_extended_p19_p29',kind='own_numeric_prose',locator='XML body//p19,p29;0..1V programme',header=['sample','method','capacitance_F_g','current_A_g','scan_mV_s'],rows=[['ENFA-FB','GCD','215','0.5',''],['ENFA-FBa','GCD','407','0.5',''],['ENFA-FBa','CV','360','','5']]),dict(doi=GELS,document='Composite',id='own_2E_p35',kind='own_numeric_prose',locator='XML body//p35 andFigure8; Eq3/Eq4 singleelectrode mass conventions retained',header=['sample','method','capacitance_F_g','current_A_g','scan_mV_s'],rows=[['ENFA-FBa','GCD',str(v),str(j),''] for j,v in [(.5,323),(1,301),(2,284),(5,260),(10,236),(50,130)]]+[['ENFA-FBa','CV',str(v),'',str(j)] for j,v in [(5,312),(10,292),(20,277),(50,248),(100,220)]]),dict(doi=GELS,document='Composite',id='own_device_cycle_energy_p35',kind='own_numeric_prose',locator='XML body//p35 andFigure8B/F; same sample/commonprogramme, not CVwindow substitution',header=['sample','cycles','retention_pct','CE_pct','cycle_A_g','energy_Wh_kg','power_W_kg'],rows=[['ENFA-FBa','10000','91','53.5','10','11.2','125']])]
    write(OUT/'curation_spec.json',dict(sources=sources,xml_tables=tables,own_numeric_units=graph_units,scientific_scope='All declared own cells in5main tables, own EDAX and printedfigure/prose units; sampled curves approximate and source-grouped. Foreign comparison rows are not own experimental labels. Not whole-article completion.'))
    write(OUT/'curve_samples.json',curve_samples())
    print(json.dumps(dict(xml_tables=len(tables),own_numeric_units=len(graph_units),curve_readings=58),ensure_ascii=False))

def build():
    if DB.exists() or (OUT/'merge_manifest.json').exists():raise FileExistsError('Do not overwrite draft or release.')
    assert sha(PARENT)==PARENT_SHA
    spec=json.loads((OUT/'curation_spec.json').read_text('utf8'));curves=json.loads((OUT/'curve_samples.json').read_text('utf8'))
    docs={s['key']:dict(doi=s['doi'],path=ROOT/s['path']) for s in spec['sources']}
    docs.update(Onion_SI=dict(doi=ONION,path=OB/'assets/mmc1.docx'),Onion_SI_cycle=dict(doi=ONION,path=OUT/'evidence/Onion_SI_image2.jpeg'),Onion_SI_Dunn=dict(doi=ONION,path=OUT/'evidence/Onion_SI_image7.emf'),Onion_GA=dict(doi=ONION,path=OB/'assets/ga1.jpg'),Onion_Fig4=dict(doi=ONION,path=OB/'assets/gr4.jpg'),Onion_Fig5=dict(doi=ONION,path=OB/'assets/gr5.jpg'),Composite_Fig2=dict(doi=GELS,path=GB/'assets/gels-10-00082-g002.jpg'),Composite_Fig4C=dict(doi=GELS,path=GB/'assets/gels-10-00082-g004b.jpg'),Composite_Fig4AB=dict(doi=GELS,path=GB/'assets/gels-10-00082-g004a.jpg'),Composite_Fig7=dict(doi=GELS,path=GB/'assets/gels-10-00082-g007.jpg'),Composite_Fig8=dict(doi=GELS,path=GB/'assets/gels-10-00082-g008.jpg'))
    receipt=[];units={}
    with closing(ro(PARENT)) as parent,closing(sqlite3.connect(DB)) as c:
        parent.backup(c);c.row_factory=sqlite3.Row;c.execute('pragma foreign_keys=on')
        c.executescript('''
          create table material_scopes_v8(material_key text primary key references materials,scope_json text);
          create table ratio_audits_v8(audit_id text primary key,material_key text references materials,audit_json text);
          create table curve_samples_v8(reading_id text primary key,material_key text references materials,document_key text references source_documents,reading_json text);
          create table purpose_reviews_v8(candidate_id text references test_candidates,purpose text,eligible integer check(eligible=1),review_json text,primary key(candidate_id,purpose));
          create table parse_rules_v8(record_id text primary key,kind text,parse_mode text);
          create index curve_material_v8 on curve_samples_v8(material_key);
        ''')
        for s in spec['sources']:insert(c,'reviewed_sources',dict(doi=s['doi'],path=s['path'],sha256=s['sha256'],title=s['title'],stage='Declared own tables/prose/figure labels and bounded samples; not whole-source completion'))
        for label,d in docs.items():insert(c,'source_documents',dict(document_key=label,doi=d['doi'],path=d['path'].relative_to(ROOT).as_posix(),sha256=sha(d['path']),role='primary_xml' if label in ['Onion','Composite'] else 'own_Word_SI' if label=='Onion_SI' else 'original_graphic'))
        def material(doi,sample,origin,stage,scope):
            key=mk(doi,sample);insert(c,'materials',dict(material_key=key,doi=doi,sample_name=sample,material_stage=stage));insert(c,'material_scopes_v8',dict(material_key=key,scope_json=json.dumps(dict(origin_class=origin,**scope),ensure_ascii=False)))
        for sample in ['COH_550C','GC_600C','GC_850C','GC_950C']:material(ONION,sample,'biomass_carbon','carbonized_biomass_control_before_activation' if sample=='COH_550C' else 'final_biomass_carbon_before_test',dict(feedstock='onion_husk',synthetic_carbon_component=False))
        gelnames=['ECNF','ECNF-B','ECNF-FB','ENFA','B-ENFA','ENFA-B','FB-ENFA','ENFA-FB','ENFAa','ENFA-Ba','ENFA-FBa']
        for sample in gelnames:
            control=sample in ['ECNF','ENFA','ENFAa'];ftreated='FB' in sample
            material(GELS,sample,'synthetic_PAN_carbon_control' if control else 'intentional_wood_biochar_PAN_composite','activated_aerogel_before_test' if sample.endswith('a') else 'nonactivated_carbon_before_test',dict(feedstock=None if control else 'oakwood_biochar',synthetic_carbon_component='PAN',F_treated_biomass=ftreated,aerogel_route='type_I_blended_PAN_fiber_with_biochar' if sample in ['B-ENFA','FB-ENFA'] else 'type_II_biochar_embedded_in_PAN' if sample in ['ENFA-B','ENFA-FB','ENFA-Ba','ENFA-FBa'] else 'PAN_control_or_no_aerogel',final_biochar_fraction=None))
        def unit(t):
            key=t['doi']+'#'+t['id'];rows=[[x['raw'] for x in r] for r in t['grid']] if 'grid' in t else t['rows'];header=rows[0] if 'grid' in t else t['header']
            insert(c,'reviewed_tables',dict(table_key=key,doi=t['doi'],xml_id=t['id'],caption=t.get('caption',t['id']),header_json=json.dumps(header,ensure_ascii=False),footnote='Declared scope; decimal commas explicit. XML origins or ownWord/graphic source binding retained; not automatic training membership.',source_raw_table_id=t.get('raw_table_id')))
            insert(c,'table_source_links',dict(table_key=key,document_key=t['document'],locator=t['locator']));insert(c,'extraction_units_v3',dict(table_key=key,kind=t['kind'],scope='Own declared cells only; comparison references excluded from own labels; point and approximate curves distinct.'))
            for i,row in enumerate(rows,1):
                insert(c,'transcribed_rows',dict(table_key=key,row_ordinal=i,cells_json=json.dumps(row,ensure_ascii=False)))
                insert(c,'transcription_origins_v7',dict(table_key=key,row_ordinal=i,origin_json=json.dumps(t['grid'][i-1] if 'grid' in t else dict(document=t['document'],locator=t['locator'],declared_row=i),ensure_ascii=False)))
            if t.get('raw_table_id'):c.execute('update raw_table_queue set review_state=? where table_id=?',('v8_own_declared_cells_reviewed_comparisons_and_controls_separate',t['raw_table_id']))
            units[(t['doi'],t['id'])]=(key,rows,t);receipt.append(dict(table_key=key,kind=t['kind'],document=t['document'],locator=t['locator'],rows=len(rows),raw_table_id=t.get('raw_table_id')))
            return key,rows,t
        for t in spec['xml_tables']+spec['own_numeric_units']:unit(t)
        def cell(key,row,col):return json.loads(c.execute('select cells_json from transcribed_rows where table_key=? and row_ordinal=?',(key,row)).fetchone()[0])[col]
        def fact(doi,sample,key,i,col,field,unit,method,mode='decimal',status='own_reported_method_qualified_not_automatic_admission'):
            raw=cell(key,i,col);value=number(raw,mode);doc=c.execute('select document_key from table_source_links where table_key=?',(key,)).fetchone()[0]
            cur=insert(c,'material_facts',dict(material_key=mk(doi,sample),field_name=field,value=value,raw_value=raw,unit=unit,method=method,table_key=key,row_ordinal=i,column_ordinal=col,source_sha256=sha(docs[doc]['path']),review_status='author_dash_not_reported_not_zero' if value is None else status,training_eligible=0));insert(c,'parse_rules_v8',dict(record_id='fact:'+str(cur.lastrowid),kind='fact',parse_mode=mode))
        key,rows,_=units[(ONION,'tbl1')]
        fields=[('Raman_D_position_cm_inv','cm^-1'),('Raman_G_position_cm_inv','cm^-1'),('Raman_I2D_reported_intensity','author_intensity_unit_unspecified'),('Raman_ID_reported_intensity','author_intensity_unit_unspecified'),('Raman_IG_reported_intensity','author_intensity_unit_unspecified'),('Raman_ID_IG','ratio'),('Raman_I2D_IG','ratio')]
        for i,(row,sample) in enumerate(zip(rows[1:],['GC_600C','GC_850C','GC_950C']),2):
            for col,(field,un) in enumerate(fields,1):fact(ONION,sample,key,i,col,field,un,'OwnRaman473nm; reportedratio and intensities kept separate',status='conflict_reported_ratio_vs_printed_intensities' if (sample=='GC_600C' and col==6) or (sample!='GC_600C' and col==7) else 'own_reported_method_qualified_not_automatic_admission')
            audit=dict(sample=sample,printed_ID=number(row[4]),printed_IG=number(row[5]),reported_ID_IG=number(row[6]),computed_ID_IG=number(row[4])/number(row[5]),reported_I2D_IG=number(row[7]),computed_I2D_IG=None if number(row[3]) is None else number(row[3])/number(row[5]),decision='Arithmetic audit only; do not silently invert a ratio or change author intensities. Competing reportedratios frozen in shared features.',not_new_measurement=True)
            insert(c,'ratio_audits_v8',dict(audit_id='Onion_Raman_'+sample,material_key=mk(ONION,sample),audit_json=json.dumps(audit,ensure_ascii=False)))
        key,rows,_=units[(ONION,'own_BET_p22')]
        for i,r in enumerate(rows,1):fact(ONION,r[0],key,i,1,'BET_surface_area_m2_g','m2/g','OwnBET nitrogen77K frombodyp11,p22')
        key,rows,_=units[(ONION,'tbl3')];fact(ONION,'GC_850C',key,9,2,'BET_surface_area_m2_g','m2/g','Own presentwork row; repeats body1924, not new experiment',status='repeat_own_source_report_not_independent_measurement')
        key,rows,_=units[(ONION,'own_EDAX_S4')]
        for i,r in enumerate(rows,1):
            for col,suffix,un in [(1,'reported_line_energy_keV','keV'),(2,'wt_pct','wt%'),(3,'author_Error_pct','author_Error%_definition_not_further_stated'),(4,'at_pct','at%')]:fact(ONION,'GC_850C',key,i,col,'EDX_'+r[0]+'_'+suffix,un,'OwnEDAX instrument output; author element assignment retained; not XPS; K correction column excluded from composition')
        key,rows,_=units[(ONION,'own_yield_p10')];fact(ONION,'COH_550C',key,1,1,'reported_product_yield_pct','wt%','Carbonized precursor productyield relativefeed; activation8.4 not bound to a temperature')
        for short in ['gels-10-00082-t001','gels-10-00082-t002']:
            key,rows,_=units[(GELS,short)]
            fs=[('BET_surface_area_m2_g','m2/g'),('average_pore_width_nm','nm'),('micropore_volume_cm3_g','cm3/g'),('mesopore_volume_cm3_g','cm3/g'),('macropore_volume_cm3_g','cm3/g'),('total_pore_volume_cm3_g','cm3/g'),('micropore_volume_fraction_pct','%'),('mesopore_volume_fraction_pct','%'),('macropore_volume_fraction_pct','%')]
            for i,row in enumerate(rows[2:],3):
                for col,(field,un) in enumerate(fs,1):fact(GELS,row[0],key,i,col,field,un,'OwnreportedN2/BET porosity table; pore-volume fit model not further specified; literal XML precision preserved')
        key,rows,_=units[(GELS,'own_Raman_Fig2')]
        for i,row in enumerate(rows,1):fact(GELS,row[0],key,i,1,'Raman_IG_ID','ratio','OwnFig2 printed IG/ID, not ID/IG;532nm')
        key,rows,_=units[(GELS,'own_activated_Raman_XPS_p23')];fact(GELS,'ENFA-FBa',key,1,1,'Raman_IG_ID','ratio','Ownbodyp23 activatedratio;532nm');fact(GELS,'ENFA-FBa',key,1,2,'XPS_F_at_pct','at%','Author approximate ownXPSFatomic%; not wt%',mode='approx',status='author_approximate_report_not_exact_label')
        def cap(doi,sample,key,i,col,method,system,current,scan,conditions,mode='decimal',duplicate=False):
            raw=cell(key,i,col);ident=key+'#'+str(i)+'#'+str(col)
            insert(c,'capacitance_observations',dict(observation_id=ident,material_key=mk(doi,sample),table_key=key,row_ordinal=i,column_ordinal=col,value=number(raw,mode),raw_value=raw,unit='F/g',method=method,system=system,electrolyte='KOH' if doi==ONION else 'H2SO4',concentration_mol_L=6 if doi==ONION else 1,current_A_g=current,scan_rate_mV_s=scan,conditions_json=json.dumps(dict(conditions,extraction_batch='v8',not_additional_physical_test=duplicate,physical_test_group=doi+'#'+sample+'#'+system+'#'+method+'#'+str(current or scan)),ensure_ascii=False),status='repeat_own_report_not_independent' if duplicate else 'own_reported_scope_qualified_not_automatic_shared_admission',source_group='doi:'+doi,training_eligible=0));insert(c,'parse_rules_v8',dict(record_id=ident,kind='capacitance',parse_mode=mode))
        key,rows,_=units[(ONION,'own_GCD_p29')]
        for i,r in enumerate(rows,1):cap(ONION,r[0],key,i,2,'GCD','2E_symmetric',float(r[1])*.001,None,dict(reported_current_mA_g=float(r[1]),current_conversion_factor=.001,current_mass_basis='author_reported_unknown_not_inferred',electrolyte_source_state='own_presentwork_table_for850; inherited_common_series_forother_temperatures_not_independently_stated',capacitance_basis='author_two_electrode_normalization_not_reported',voltage_lower_V=0,voltage_upper_V=1,electrolyte_binding='Own presentworkTable3 says6MKOH; same sample/common2E series, no unrelated reference electrolyte used'))
        key,rows,_=units[(ONION,'tbl3')];cap(ONION,'GC_850C',key,9,4,'GCD','2E_symmetric',.5,None,dict(capacitance_basis='author_two_electrode_normalization_not_reported',voltage_lower_V=0,voltage_upper_V=1,repeat_of=ONION+'#own_GCD_p29#6#2',table_printed_year='2023_not_publication_year_override'),mode='cap_prefix',duplicate=True)
        key,rows,_=units[(GELS,'own_GCD_Fig4C')]
        for i,r in enumerate(rows,1):cap(GELS,r[0],key,i,1,'GCD','3E',.5,None,dict(capacitance_basis='single_working_electrode',voltage_lower_V=0,voltage_upper_V=.8,current_mass_basis='author_reported_unknown_not_inferred',material_scope='PAN_control_or_biochar_PAN_composite_separate'))
        for short,system in [('own_3E_extended_p19_p29','3E'),('own_2E_p35','2E_symmetric')]:
            key,rows,_=units[(GELS,short)]
            for i,r in enumerate(rows,1):cap(GELS,r[0],key,i,2,r[1],system,number(r[3]),number(r[4]),dict(capacitance_basis='single_working_electrode' if system=='3E' else 'author_single_electrode_material_equivalent_two_electrode_cell',formula='I*dt/(m*dV)' if system=='3E' and r[1]=='GCD' else '2*I*dt/(m_single*dV)' if r[1]=='GCD' else 'OwnEq1' if system=='3E' else 'OwnEq3_integral/(m_single*v*dV)',mass_normalization='single electrode explicitly stated; current denominator kept unknown',current_mass_basis='author_reported_unknown_not_inferred',voltage_lower_V=0,voltage_upper_V=1))
        def response(doi,sample,key,i,col,metric,unit,context):
            raw=cell(key,i,col);ident=key+'#'+str(i)+'#'+str(col)
            insert(c,'outcome_observations_v3',dict(outcome_id=ident,material_key=mk(doi,sample) if sample else None,table_key=key,record_json=json.dumps(dict(context,metric=metric,value=number(raw),raw_value=raw,unit=unit,row_ordinal=i,column_ordinal=col,source_group='doi:'+doi,feature_role='test_response_not_pretest_material_predictor',extraction_batch='v8'),ensure_ascii=False),training_eligible=0));insert(c,'parse_rules_v8',dict(record_id=ident,kind='response',parse_mode='decimal'))
        key,rows,_=units[(ONION,'tbl2')]
        for i,r in enumerate(rows[2:],3):
            for k,sample in enumerate(['GC_600C','GC_850C','GC_950C']):
                ctx=dict(system='2E_symmetric',reported_current_mA_g=float(r[0]),current_A_g=float(r[0])*.001,author_calculated_from_GCD=True)
                response(ONION,sample,key,i,k+1,'specific_energy_Wh_kg','Wh/kg',ctx);response(ONION,sample,key,i,k+4,'specific_power_W_kg','W/kg',ctx)
        key,rows,_=units[(ONION,'own_EDAX_S4')]
        for i,r in enumerate(rows,1):response(ONION,'GC_850C',key,i,5,'EDAX_'+r[0]+'_instrument_K_column','instrument_unit_not_defined',dict(not_composition_fraction=True))
        key,rows,_=units[(ONION,'own_Dunn_S2')]
        for i,r in enumerate(rows,1):
            for col,metric in [(1,'CV_capacitive_contribution_pct'),(2,'CV_diffusion_contribution_pct')]:response(ONION,'GC_850C',key,i,col,metric,'%',dict(scan_rate_mV_s=float(r[0]),first_column_sum101_preserved=True,not_cycle_retention=True))
        key,rows,_=units[(ONION,'own_yield_p10')];response(ONION,None,key,2,1,'source_reported_activation_yield_pct','wt%',dict(sample_temperature_unbound=True))
        key,rows,_=units[(ONION,'own_CE_EIS_p29_p35_p36')]
        for i,r in enumerate(rows,1):response(ONION,r[0],key,i,1,'coulombic_efficiency_pct','%',dict(current_A_g=1,not_cycle_retention=True));response(ONION,r[0],key,i,2,'approx_Rct_ohm','ohm',dict(author_approximate=True,EIS_amplitude_mV=5,frequency_range_Hz=[.01,100000]))
        key,rows,_=units[(GELS,'own_device_cycle_energy_p35')]
        for col,metric,unitname in [(3,'coulombic_efficiency_pct','%'),(5,'specific_energy_Wh_kg','Wh/kg'),(6,'specific_power_W_kg','W/kg')]:response(GELS,'ENFA-FBa',key,1,col,metric,unitname,dict(system='2E_symmetric',cycle_count=10000 if col==3 else None,current_A_g=10 if col==3 else None,not_cycle_retention=True))
        for i,r in enumerate(curves,1):insert(c,'curve_samples_v8',dict(reading_id='v8_curve_'+str(i),material_key=mk(r['doi'],r['sample']),document_key=r['document'],reading_json=json.dumps(r,ensure_ascii=False)))
        for sample in ['COH_550C','GC_600C','GC_850C','GC_950C']:
            rec=dict(source_group='doi:'+ONION,system='2E_symmetric',method='GCD',electrolyte='KOH',concentration_mol_L=6,reported_current_A_g=2,current_mass_basis='author_reported_unknown',cycle_count=5000,cycle_voltage_lower_V=0,cycle_voltage_upper_V=1,baseline_index=None,baseline_reference='not specified by author; no fresh-rate value substituted',retention_pct=95 if sample=='GC_850C' else None,retention_relation='<' if sample=='GC_850C' else None,reported_retention_is_censored=sample=='GC_850C',point_label_admitted=False,electrolyte_source_state='own_presentwork850table; inherited_series_forother_samples_not_independently_stated',issue='AbsoluteC(N) sourcecurves and <95% prose do not define a reconciled exact retention target; preserve both',evidence_source_path=(OB/'main.xml').relative_to(ROOT).as_posix(),source_sha256=sha(OB/'main.xml'),locator='bodyp38/p42 + originalFigure5c + WordSI_S1b')
            insert(c,'test_candidates',dict(candidate_id='LP8_Onion_'+sample+'_C5000',material_key=mk(ONION,sample),record_json=json.dumps(rec,ensure_ascii=False),training_eligible=0))
        candidate='LP8_Gels_ENFAFBa_2E_C10000';rec=dict(source_group='doi:'+GELS,system='2E_symmetric',method='GCD',material_class='intentional_wood_biochar_PAN_composite',electrolyte='H2SO4',concentration_mol_L=1,reported_current_A_g=10,current_mass_basis='author_reported_unknown_not_inferred_from_capacitance_formula',cycle_count=10000,retention_pct=91,retention_relation='=',cycle_voltage_lower_V=0,cycle_voltage_upper_V=1,baseline_index=None,baseline_reference='author_initial_capacitance_exact_index_unspecified',evidence_source_path=(GB/'main.xml').relative_to(ROOT).as_posix(),source_sha256=sha(GB/'main.xml'),locator='ownbodyp35,p54-57 and originalFigure8B/F; composite purpose, not ordinary main',ordinary_biomass_cycling_admitted=False)
        insert(c,'test_candidates',dict(candidate_id=candidate,material_key=mk(GELS,'ENFA-FBa'),record_json=json.dumps(rec,ensure_ascii=False),training_eligible=0))
        review=dict(purpose='reported_PAN_biochar_composite_2e_cycle_retention',scope='Intentional PAN-derivedcarbon plus woodbiochar; finalcomponentfraction unknown, precursor stages known',window_evidence='OriginalFig8B ownGCD0..1V + sameFig8F/ownp35cycle10A/g protocol andmethods54-57; existingapplicableGCD/commonprotocol rule; not borrowedCVwindow',baseline_rule='Authorinitial normalization, exactcycleindex not invented',current_rule='Report10A/g plus unknownmassbasis; unknowndenominator not sole rejection',selected_target=dict(retention_pct=91,cycles=10000),excluded_response='CE53.5% separate, nottarget orX',source_group='doi:'+GELS,one_DOI_only=True,no_new_training_authorization=True)
        insert(c,'purpose_reviews_v8',dict(candidate_id=candidate,purpose=review['purpose'],eligible=1,review_json=json.dumps(review,ensure_ascii=False)))
        for s in ['COH_550C','GC_600C','GC_850C','GC_950C']:
            stages=[dict(stage='feedstock_drying',temperature_C=120,duration_h=8),dict(stage='carbonization',temperature_C=550,duration_min=100,duration_h=100/60,heating_rate_C_min=7,atmosphere='Ar',reported_product_yield_wt_pct=27.5,field_scope='carbonizedCOH common precursor')]
            if s!='COH_550C':stages+=[dict(stage='chemical_activation',temperature_C=int(s[3:6]),duration_min=None,duration_h=None,reported_duration_min_body=90,reported_duration_min_graphical_abstract=100,duration_state='conflict_methods90_vs_graphicalabstract100_not_resolved',atmosphere='Ar',gas_flow_cm3_min=450,agent='KOH',reported_CO_H_KOH_ratio='1:4',activator_to_carbon_mass_ratio=None,ratio_orientation='bodyp10 wording does not unambiguously specify numerator; do not guess4'),dict(stage='washing_and_drying',washing='hotDIwater untilneutralpH',temperature_C=100,duration_h=10)]
            stages.append(dict(stage='electrode_preparation',phase='electrode_not_bulk_material',carbon_wt_pct=70,conductive_carbon_wt_pct=20,PVDF_wt_pct=10,NMP_mL_per_g_mixture=4,current_collector='Ni_foil',coated_area_cm2=1,drying_temperature_C=130,drying_duration_h=10));insert(c,'synthesis_stages_v3',dict(material_key=mk(ONION,s),document_key='Onion',locator='ownbodyp10,p12; ratio orientation unresolved',stages_json=json.dumps(stages,ensure_ascii=False)))
        for sample in gelnames:
            control=sample in ['ECNF','ENFA','ENFAa'];ftreated='FB' in sample;typeI=sample in ['B-ENFA','FB-ENFA'];activated=sample.endswith('a');aerogel=not sample.startswith('ECNF');stages=[]
            if not control:
                if ftreated:stages.append(dict(stage='wood_feedstock_F_pretreatment',HF_wt_pct=20,phase='biochar_feedstock_not_final_electrode_F_fraction',temperature_C=None,duration_h=None,drying_temperature_C=120))
                stages += [dict(stage='biochar_ingredient_carbonization',temperature_C=500,duration_min=30,heating_rate_C_min=10,atmosphere='N2',flow_mL_min=400),dict(stage='biochar_ingredient_activation',temperature_C=800,duration_h=1,atmosphere='N2',agent='KOH',KOH_to_biochar_mass_ratio=1)]
            stages.append(dict(stage='PAN_electrospinning',PAN_solution_wt_pct=10,BO_wt_pct=1,biochar_solution_wt_pct=0 if control or typeI else 2,biochar_zero_is_recipe_absence_not_detection=True,voltage_kV=15,solution_rate_mL_h=1,tip_distance_cm=15,needle_gauge=18,solution='DMF',final_biochar_fraction=None))
            if aerogel:stages.append(dict(stage='aerogel_construction',route='typeI' if typeI else 'typeII' if not control else 'PAN_control',PAN_fiber_to_biochar_mass_ratio=[5,1] if typeI else None,freeze_drying_duration_h=48,starting_cut_fiber_cm=[1,1],phase='precursor_not_final_composition'))
            stages += [dict(stage='PAN_stabilization',temperature_C=250,duration_h=6,atmosphere='air'),dict(stage='PAN_carbonization',temperature_C=900,duration_h=1,atmosphere='N2')]
            if activated:stages.append(dict(stage='final_aerogel_activation',temperature_C=800,duration_h=1,agent='KOH',KOH_to_aerogel_mass_ratio=1,atmosphere='N2',washing_HCl_mol_L=3,drying_temperature_C=120))
            stages.append(dict(stage='electrode_preparation',phase='electrode_not_bulk_material',aerogel_slurry_carbon_wt_pct=80 if aerogel else None,acetylene_black_wt_pct=10 if aerogel else None,PVDF_wt_pct=10 if aerogel else None,reported_aerogel_active_mass_mg=.8 if aerogel else None,active_mass_scope='threeelectrode prep approximately; not transferred to each2E electrode',slurry_mesh='SS316' if aerogel else None,three_electrode_setup_working_collector='Au described separately',area_cm2=1,reference_electrode='Ag/AgCl',electrolyte='H2SO4',concentration_mol_L=1))
            insert(c,'synthesis_stages_v3',dict(material_key=mk(GELS,sample),document_key='Composite',locator='ownbodyp42-48,p50,p54-57; biocharingredient/PAN/finalactivation/electrode phases separate',stages_json=json.dumps(stages,ensure_ascii=False)))
        issues=[('Onion_activation_time',ONION,'all_activated','activation_duration_body_vs_graphical_abstract','正文90分钟与自身流程图100分钟并存，活化时长保持未知；碳化100分钟一致，不连带冻结。'),('Onion_Raman',ONION,'GC_600C/850C/950C','reported_Raman_ratio_arithmetic_conflict','自身强度与报告比值不一致，三项算术审计另存，不默改1.2为倒数或把0.07改成0.7。'),('Onion_retention',ONION,'GC_850C','censored_retention_vs_absolute_curve','正文<95%保留不当=95精确标签；自身C(N)近似采样另存，不借新鲜倍率电容或图首点强行归一化。'),('Onion_basis',ONION,'all','two_electrode_normalization_unreported','12点作者2E比电容和mA/g换算可用作报告事实，质量口径未报不混器件总质量目标；KOH1:4比例方向也不猜。'),('Onion_Dunn',ONION,'GC_850C','rounded_contribution_sum101','20mV/s的图中文字14%+87%=101%，照录，非循环保持率，不归一化成100。'),('Onion_EDAX',ONION,'GC_850C','method_qualified_EDAX_error_and_element_assignment','EDAX质量/原子/作者Error/K列分开；Lu保留作者赋值和误差，未报O不填0；不把EDAX当XPS。'),('Gels_scope',GELS,'all','intentional_PAN_composite_and_controls','PAN对照、typeI5:1纤维配比、typeII溶液2wt%生物炭及最终碳比例未知分开；不是同材料别名。'),('Gels_window',GELS,'ENFA-FB','different_GCD_voltage_programmes','0.5A/g的187 F/g对应初始0～0.8V，215 F/g对应扩展0～1V，不是竞争测量或重复择高。'),('Gels_basis',GELS,'ENFA-FBa','single_electrode_equivalent_vs_device_mass','2E的Eq4用2IΔt/(m_singleΔV)，原323等保留单电极等效口径，不拼器件总质量；电流分母仍未知。'),('Gels_CE',GELS,'ENFA-FBa','coulombic_efficiency_separate_from_retention','图8F左轴91%电容保持率、右轴53.5%库仑效率分开；后者不作预测特征或保持率。')]
        for name,doi,sample,kind,action in issues:insert(c,'scientific_issues',dict(issue_id='LP8_'+name,doi=doi,sample_name=sample,issue_json=json.dumps(dict(kind=kind,action=action),ensure_ascii=False)))
        for ident,doc,record in [('Onion_synthesis','Onion_GA',dict(carbonization_duration_min=100,activation_duration_body_min=90,activation_duration_graphical_abstract_min=100,activation_duration_selected_min=None)),('Onion_GCD','Onion_Fig4',dict(window_V=[0,1],scope='OwnGCDall3temperatures; SI_COHandbodyp42 separately bindcycleprogramme')),('Composite_cycle','Composite_Fig8',rec)]:insert(c,'figure_protocol_reviews_v6',dict(review_id=ident,document_key=doc,record_json=json.dumps(record,ensure_ascii=False)))
        # Reconcile scope-index coverage from already bound units; this is not a
        # new scientific eligibility or whole-paper completion decision.
        for source in c.execute('select doi from reviewed_sources where doi not in (select doi from source_scope_decisions)').fetchall():
            links=[dict(r) for r in c.execute('select t.table_key,t.caption,l.locator,d.path,d.sha256 from reviewed_tables t join table_source_links l using(table_key) join source_documents d using(document_key) where t.doi=? order by t.table_key',(source['doi'],))]
            insert(c,'source_scope_decisions',dict(doi=source['doi'],scope='partial_declared_own_evidence_units_not_whole_source',reason='Scope-index reconciliation from existing unit/source bindings only. No new material classification, admission or full-paper claim.',evidence_json=json.dumps(dict(derived_from='reviewed_tables + table_source_links + source_documents',units=links,whole_source_completion_proven=False),ensure_ascii=False),full_source_review_complete=0))
        c.commit()
    files=[PARENT,ROOT/'全库复检与特征补提取_20261021/full_corpus_search_native.sqlite']+[d['path'] for d in docs.values()]
    write(OUT/'protected_inputs.json',dict(files=[dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p)) for p in dict.fromkeys(files)],pinned_parent_sha256=PARENT_SHA,dependency_policy='Immutable files only; current pointers may advance.'))
    write(OUT/'table_review_receipt.json',receipt)
    print('Built unsealed v8; no fits, originalfixed38 unchanged.')

def verify(write_reports=False):
    checks=[]
    def check(name,ok):
        if not ok:raise AssertionError(name)
        checks.append(name)
    protection=json.loads((OUT/'protected_inputs.json').read_text('utf8'))
    for p in protection['files']:check('protected_'+p['path'],sha(ROOT/p['path'])==p['sha256'])
    for manifest in [PARENT.parent/'merge_manifest.json',PARENT.parent/'grouping_addendum_manifest.json']:
        for p in json.loads(manifest.read_text('utf8'))['outputs']:check('parent_payload_'+p['path'],sha(ROOT/p['path'])==p['sha256'])
    spec=json.loads((OUT/'curation_spec.json').read_text('utf8'));readings=json.loads((OUT/'curve_samples.json').read_text('utf8'));digest=sha(DB)
    check('58_curves_recomputed_same_algorithm',readings==curve_samples() and len(readings)==58)
    # Verify the extracted Word graphics and native EDAX tokens against the ZIP,
    # independently of the structured transcription and GDI viewing surrogates.
    ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    with zipfile.ZipFile(OB/'assets/mmc1.docx') as z:
        for p in (OUT/'evidence').glob('Onion_SI_image*'):
            native='word/media/'+p.name.removeprefix('Onion_SI_')
            if native in z.namelist():check('Word_embedded_'+p.name,p.read_bytes()==z.read(native))
        root=E.fromstring(z.read('word/document.xml'));paras=root.findall('.//w:p',ns)
        edax=next(t for t in spec['own_numeric_units'] if t['id']=='own_EDAX_S4')
        for i,row in enumerate(edax['rows']):
            para=''.join(t.text or '' for t in paras[44+i].findall('.//w:t',ns));check('Word_EDAX_raw_'+row[0],re.findall(r'\d+\.\d+',para)==row[1:])
    with closing(ro(DB)) as c,closing(ro(PARENT)) as old:
        c.row_factory=sqlite3.Row
        check('integrity',c.execute('pragma integrity_check').fetchone()[0]=='ok');check('foreign_keys',not c.execute('pragma foreign_key_check').fetchall())
        for (name,) in old.execute("select name from sqlite_master where type='table' and name not like 'sqlite_%'"):
            if name=='raw_table_queue':continue
            rows={tuple(r) for r in c.execute('select * from '+name)};check('parent_'+name,all(tuple(r) in rows for r in old.execute('select * from '+name)))
        oldq={r[0]:tuple(r) for r in old.execute('select * from raw_table_queue')};now=[tuple(r) for r in c.execute('select * from raw_table_queue')]
        ids={t['raw_table_id'] for t in spec['xml_tables']};check('only5_declared_queue_updates',{r[0] for r in now if r!=oldq[r[0]]}==ids and len(ids)==5 and all(r[:6]==oldq[r[0]][:6] and r[7:]==oldq[r[0]][7:] for r in now))
        for t in spec['xml_tables']+spec['own_numeric_units']:
            key=t['doi']+'#'+t['id'];actual=[json.loads(r[0]) for r in c.execute('select cells_json from transcribed_rows where table_key=? order by row_ordinal',(key,))]
            if 'grid' in t:
                source=next(s for s in spec['sources'] if s['key']==t['document']);root=E.parse(ROOT/source['path']).getroot();grid=xml_grid(root.find(".//table-wrap[@id='"+t['id']+"']"));check('original_XML_spans_'+key,grid==t['grid']);expected=[[x['raw'] for x in row] for row in grid]
            else:expected=t['rows']
            check('transcription_'+key,actual==expected)
        def cells(key,i):return json.loads(c.execute('select cells_json from transcribed_rows where table_key=? and row_ordinal=?',(key,i)).fetchone()[0])
        for f in c.execute("select f.*,p.parse_mode from material_facts f join parse_rules_v8 p on p.record_id='fact:'||f.fact_id"):
            check('fact_raw_'+str(f['fact_id']),f['raw_value']==cells(f['table_key'],f['row_ordinal'])[f['column_ordinal']]);check('fact_value_'+str(f['fact_id']),number(f['raw_value'],f['parse_mode'])==f['value'])
        for t in ['material_facts','capacitance_observations','outcome_observations_v3','test_candidates','raw_table_queue']:check('raw_eligible0_'+t,c.execute('select count(*) from '+t+' where training_eligible!=0 or training_eligible is null').fetchone()[0]==0)
        check('scope_index_covers19_sources',c.execute('select count(*) from reviewed_sources where doi not in(select doi from source_scope_decisions)').fetchone()[0]==0)
        old_scope_ids={r[0] for r in old.execute('select doi from source_scope_decisions')}
        new_scopes=[dict(r) for r in c.execute('select * from source_scope_decisions') if r['doi'] not in old_scope_ids]
        check('7_missing_scope_entries_added_without_completion',len(new_scopes)==7 and all(r['full_source_review_complete']==0 and json.loads(r['evidence_json'])['whole_source_completion_proven']==False for r in new_scopes))
        for row in new_scopes:
            for evidence in json.loads(row['evidence_json'])['units']:check('scope_source_hash_'+row['doi']+evidence['table_key'],sha(ROOT/evidence['path'])==evidence['sha256'])
        count=lambda name:c.execute('select count(*) from '+name).fetchone()[0]
        actual_tables=c.execute("select count(*) from reviewed_tables t left join extraction_units_v3 u using(table_key) where u.kind is null or u.kind in ('own_xml_table','own_SI_table','own_and_comparison_pdf_table','mixed_comparison_table')").fetchone()[0]
        panels=len({(r['document'],r['x_name']) for r in readings})
        summary=dict(identity_catalogue_entries=480,raw_table_candidates=959,raw_table_rows=6121,cumulative_reviewed_source_publications=count('reviewed_sources'),cumulative_materials=count('materials'),cumulative_selected_material_cells=count('material_facts'),cumulative_numeric_material_facts=c.execute('select count(*) from material_facts where value is not null').fetchone()[0],new_materials=count('materials')-92,new_numeric_material_facts=c.execute('select count(*) from material_facts where value is not null').fetchone()[0]-1055,reviewed_table_units=actual_tables,reviewed_evidence_units=count('reviewed_tables')+count('figure_protocol_reviews_v6')+panels,curve_sampling_panels=panels,new_bounded_curve_samples=58,new_curve_groups=len({r['curve_group'] for r in readings}),raw_candidates_touched=959-c.execute("select count(*) from raw_table_queue where review_state='automatic_candidate_unreviewed'").fetchone()[0],raw_candidates_untouched=c.execute("select count(*) from raw_table_queue where review_state='automatic_candidate_unreviewed'").fetchone()[0],capacitance_records=count('capacitance_observations'),numeric_capacitance_values=c.execute('select count(*) from capacitance_observations where value is not null').fetchone()[0],unreported_capacitance_cells=2,cycling_candidates=count('test_candidates'),scientific_issues=count('scientific_issues'),historical_selected_fact_references=725,historical_fact_references_with_same_source_table_candidates=171,synthesis_materials=count('synthesis_stages_v3'),response_outcomes=count('outcome_observations_v3'),new_source_response_records=46,new_Palm_response_records=1485,new_Palm_individual_electrical_conditions=132,new_Palm_individual_electrical_coins=22,auxiliary_aqueous_3e_GCD_rows=103,auxiliary_aqueous_2e_GCD_rows=5,auxiliary_native_mineral_3e_GCD_rows=5,auxiliary_author_factor2_2e_GCD_rows=6,auxiliary_independent_DOI_groups=8,auxiliary_purpose_reviewed_input_rows=119,DES_purpose_reviewed_rows_per_target=12,DES_purpose_reviews=24,DES_independent_DOI_groups=1,new_composite_cycle_purpose_rows=1,new_composite_cycle_DOI_groups=1,new_training_admissions=0,formal_cycling_admissions=0,model_fits=0,all_literature_fully_utilized=False,scope_note='Selected5main tables, ownSIEDAX/labels/prose and58bounded curve samples; controls/composite and differentcapacitance conventions separate. New custom composite-purpose input1 is not ordinarycycling membership. CensoredOnion retention remainsunresolved; originalfixed38 unchanged.')
        check('expected_evidence_grains',actual_tables==80 and panels==3 and summary['new_numeric_material_facts']==150 and summary['new_materials']==15 and summary['capacitance_records']==403)
    from data.literature_v8 import open_literature_database as new_api
    from data.literature_v7 import open_literature_database as old_api
    from data.literature_v4 import PROFILES
    exports={}
    with new_api(DB,digest) as new,old_api(PARENT,PARENT_SHA) as old:
        for p in PROFILES:check('aux_unchanged_'+p,new.auxiliary_feature_rows(p)==old.auxiliary_feature_rows(p))
        for target in ['capacitance','retention']:check('DES_unchanged_'+target,new.des_reported_inputs(target)==old.des_reported_inputs(target))
        check('Palm_audit_unchanged',new.palm_statistics_audit()==old.palm_statistics_audit());check('Palm_responses_unchanged',new.palm_responses()==old.palm_responses())
        for doi,ncap,nfact in [(ONION,13,43),(GELS,22,109)]:check('new_source_counts_'+doi,len(new.capacitances(doi=doi))==ncap and len(new.facts(doi=doi))==nfact)
        for p in new.connection.execute("select * from parse_rules_v8 where kind='capacitance'"):
            r=next(r for r in new.capacitances() if r['observation_id']==p['record_id']);check('cap_value_'+r['observation_id'],r['value']==number(r['raw_value'],p['parse_mode']))
            source=new.connection.execute('select cells_json from transcribed_rows where table_key=? and row_ordinal=?',(r['table_key'],r['row_ordinal'])).fetchone()[0];check('cap_source_'+r['observation_id'],json.loads(source)[r['column_ordinal']]==r['raw_value'])
            if '#own_GCD_p29#' in r['table_key']+'#':check('mA_to_A_'+r['observation_id'],r['current_A_g']==r['conditions']['reported_current_mA_g']*.001)
        for r in new.new_source_responses():
            record=r['record'];source=json.loads(new.connection.execute('select cells_json from transcribed_rows where table_key=? and row_ordinal=?',(r['table_key'],record['row_ordinal'])).fetchone()[0]);check('response_source_'+r['outcome_id'],record['raw_value']==source[record['column_ordinal']] and number(record['raw_value'])==record['value'] and bool(r['source_sha256']))
        scopes=new.material_scopes();check('classes_not_all_biomass',len(scopes)==15 and sum(r['scope']['origin_class']=='synthetic_PAN_carbon_control' for r in scopes)==3 and sum(r['scope']['origin_class']=='intentional_wood_biochar_PAN_composite' for r in scopes)==8)
        check('Raman_conflicts_not_silently_fixed',new.facts(doi=ONION,sample='GC_600C',field='Raman_ID_IG')[0]['value']==1.2 and 'conflict' in new.facts(doi=ONION,sample='GC_600C',field='Raman_ID_IG')[0]['review_status'])
        check('missing_Raman_intensity_not_zero',new.facts(doi=ONION,sample='GC_600C',field='Raman_I2D_reported_intensity')[0]['value'] is None)
        check('EDAX_not_XPS',new.facts(doi=ONION,field='EDX_C_wt_pct')[0]['value']==98.01 and new.facts(doi=ONION,field='EDX_C_at_pct')[0]['value']==99.33 and not new.facts(doi=ONION,field='XPS_C_at_pct'))
        check('unreported_O_not0',not new.facts(doi=ONION,field='EDX_O_wt_pct'))
        ratios=new.ratio_audits();check('ratio_audit3',len(ratios)==3 and all(r['audit']['not_new_measurement'] for r in ratios))
        for r in new.tests():
            material=next(m for m in new.materials() if m['material_key']==r['material_key']);check('all_candidate_groups_'+r['candidate_id'],r['record']['source_group']=='doi:'+material['doi'])
        onion=[r['record'] for r in new.tests() if r['candidate_id'].startswith('LP8_Onion')]
        check('Onion_censored_not_exact95',len(onion)==4 and sum(r['retention_pct']==95 for r in onion)==1 and all(not r['point_label_admitted'] for r in onion) and next(r for r in onion if r['retention_pct']==95)['retention_relation']=='<')
        matrix=new.composite_cycle_matrix();rows=new.composite_cycle_inputs();check('one_composite_input_not_ordinary',len(rows)==1 and rows[0]['target_retention_pct']==91 and rows[0]['reported_current_A_g']==10 and rows[0]['cycle_count']==10000 and not rows[0]['ordinary_biomass_cycling_admitted'])
        check('matrix_no_response_leak',matrix['y']==[91] and all(k not in matrix['feature_names'] for k in ['CE_pct','coulombic_efficiency_pct','capacitance_F_g','DOI','target_retention_pct']))
        check('matrix_unknown_fraction_not_zero',matrix['X'][0][-1] is None and matrix['missing_mask'][0][-1] and not matrix['imputed'] and matrix['estimators_fitted']==0)
        check('matrix_one_source_no_validation_claim',matrix['independent_source_groups']==1 and not matrix['external_source_fold_possible'] and not matrix['training_authorized'])
        for sample in ['GC_600C','GC_850C','GC_950C']:
            stage=next(s for s in new.synthesis(doi=ONION,sample=sample)[0]['stages'] if s['stage']=='chemical_activation')
            check('activation_time_conflict_'+sample,stage['duration_min'] is None and stage['reported_duration_min_body']==90 and stage['reported_duration_min_graphical_abstract']==100)
        check('stage_roles_preserved',[rows[0][k] for k in ['biochar_carbonization_temperature_C','PAN_carbonization_temperature_C','final_aerogel_activation_temperature_C']]==[500,900,800])
        for r in new.sampled_curves():
            p=r['reading'];check('curve_uncertainty_'+r['reading_id'],p['y_uncertainty']>0 and p['pixel_error_y']==2 and p['pixel_y_extent'][0]<=p['pixel_y']<=p['pixel_y_extent'][1] and not p['retention_point_admitted'])
        for method,label in [('scan_rate_mV_s',360),('reported_current_A_g',407)]:
            r=next(r['reading'] for r in new.sampled_curves(doi=GELS,sample='ENFA-FBa') if r['reading']['x_name']==method and r['reading']['x_value']==(5 if label==360 else .5));check('bounded_plot_vs_own_exact_'+method,abs(r['y_value']-label)<=r['y_uncertainty'])
        for doi,capn,curven,candidaten in [(ONION,13,28,4),(GELS,22,30,1)]:
            check('holdout_counts_'+doi,len(new.capacitances(doi=doi))==capn and len(new.sampled_curves(doi=doi))==curven and sum(r['record']['source_group']=='doi:'+doi for r in new.tests())==candidaten)
        check('API_RO',new.connection.execute('pragma query_only').fetchone()[0]==1)
        exports['composite_cycle_model_inputs.json']=json.dumps(matrix,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
        exports['composite_cycle_reported_input.json']=json.dumps(rows,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
    check('SQLite_unchanged_by_API',sha(DB)==digest)
    fixed=json.loads((ROOT/'docs/DATA_CORRECTION_GOAL.json').read_text('utf8'));check('fixed39_still38',fixed['fixed_record_count']==39 and fixed['current_pending']==38)
    report=dict(status='passed',checks=len(checks),check_names=sorted(checks),model_fits=0,scientific_goal_complete=False)
    preflight=dict(status='source_typed_and_one_separate_composite_purpose_reviewed',new_composite_cycle_rows=1,ordinary_cycling_new_members=0,independent_composite_DOI_groups=1,external_source_fold_possible=False,old_auxiliary_rows_preserved=119,old_DES_rows_per_target_preserved=12,curve_samples=58,curve_samples_are_not_independent_training_examples=True,Onion_censored_retention_unresolved=True,model_fits=0)
    for name,value in {'summary.json':summary,'verification.json':report,'input_preflight.json':preflight}.items():
        if write_reports:write(OUT/name,value)
        else:assert json.loads((OUT/name).read_text('utf8'))==value,'report_'+name
    for name,value in exports.items():
        if write_reports:(OUT/name).write_text(value,encoding='utf8')
        else:assert (OUT/name).read_text('utf8')==value,'export_'+name
    if (OUT/'merge_manifest.json').exists():
        for p in json.loads((OUT/'merge_manifest.json').read_text('utf8'))['outputs']:assert sha(ROOT/p['path'])==p['sha256'],p['path']
    print(json.dumps(dict(status='passed',checks=report['checks'],summary=summary),ensure_ascii=False))

def seal():
    if (OUT/'merge_manifest.json').exists():raise FileExistsError('Never reseal.')
    assert (OUT/'README.md').exists();verify(False)
    assert (OUT/'chain_verification.json').exists()
    files=sorted([p for p in OUT.rglob('*') if p.is_file()]+[Path(__file__).resolve(),ROOT/'data/literature_v8.py',ROOT/'tools/verify_corpus_chain_v8.py'])
    write(OUT/'merge_manifest.json',dict(version='literature_pool_v8',parent_sha256=PARENT_SHA,scientific_goal_complete=False,model_fits=0,outputs=[dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p),bytes=p.stat().st_size) for p in files]))
    write(ROOT/'data/current_literature.json',dict(version='literature_pool_v8',directory=OUT.relative_to(ROOT).as_posix(),database_file=DB.name,sha256=sha(DB),api_module='data.literature_v8',scope='Onion/PAN-biochar classes, own5tables andEDAX/labels/prose;58bounded curve samples; separatecomposite-cycle purpose1; old119aux/DES/currentcycling unchanged.'))

if __name__=='__main__':
    if len(sys.argv)!=2 or sys.argv[1] not in ['curate','build','prepare_reports','verify','seal']:raise SystemExit('curate/build/prepare_reports(unsealed), verify(readonly), seal(one-use)')
    command=sys.argv[1]
    if command=='prepare_reports':
        if (OUT/'merge_manifest.json').exists():raise RuntimeError('Cannot regenerate sealed reports.')
        verify(True)
    elif command=='verify':verify(False)
    else:globals()[command]()
