"""Bounded original-image rate readings and source-scoped spectroscopy annotations."""
from pathlib import Path
import collections,json,sqlite3,sys,xml.etree.ElementTree as E,zipfile
from contextlib import closing
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tools'))
from extract_source_series_v13 import sha,write,clean,FU,NAMES,ro,insert,mk
OUT=ROOT/'文献全量利用复核_20261026/批次14_糠醛渣倍率曲线与全图审查';EV=OUT/'evidence';DB=OUT/'literature_material_pool_v14.sqlite'
PARENT=ROOT/'文献全量利用复核_20261026/批次13_芒果核皮革糠醛渣与界面参考/literature_material_pool_v13.sqlite';PSHA='60f9245ad39234bea13a8b830ca41b328f36752cd27dcc4f2df1081ddb10167f'
SOURCE=ROOT/'文献扩充_大批补齐_20261018/sources/SUP_117/main.xml';SOURCE_SHA='e0e6206b6eb2304e729f5ac5adc61ebbc38e7b7c5fedf4865d075318cf520cc0'
ASSETS=SOURCE.parent/'assets';IMAGE=ASSETS/'polymers-16-03421-g010.jpg';CURRENTS=[.5,1,2,5,10,20]
CURVES=[('c','PC700-1','red',[510,520,531,551,556,568]),('c','PC800-1','cyan',[500,513,521,541,546,550]),('c','PC900-1','green',[357,399,414,435,446,458]),('c','PC950-1','purple',[486,490,493,498,502,502]),('d','FR900','orange',[464,488,505,528,547,571]),('d','PC900-0','black',[390,408,418,435,445,447]),('d','PC900-0.1','pink',[382,397,408,424,431,435]),('d','PC900-0.5','blue',[366,395,405,424,433,439]),('d','PC900-1','green',[357,399,414,435,446,458])]
OCCLUDED={('d','PC900-0',5):('PC900-1','black marker covered by green marker; individual center not separable'),('d','PC900-0.1',5):('PC900-0.5','pink marker covered by blue marker; individual center not separable')}


def color_signal(name,rgb):
    r,g,b=rgb
    return {'red':r-max(g,b)>25,'cyan':min(g,b)-r>25 and b-g>3,'green':g-r>18 and g-b>5,'purple':b-g>25 and r-g>15 and b-r>5,'orange':r-g>22 and g-b>12,'black':max(rgb)-min(rgb)<14 and max(rgb)<175,'pink':min(r,b)-g>12,'blue':b-r>18 and b-g>8 and g-r>5}[name]


def value_at(y):return 40+(581.5-y)*120/239


def capture():
    """Original coordinates only; declared ROIs/colour rules, no fitted/interpolated data."""
    im=Image.open(IMAGE).convert('RGB');assert im.size==(752,939)
    readings=[]
    for panel,sample,color,guesses in CURVES:
        axis=dict(x_value0=0,x_pixel0=82.5 if panel=='c'else 470.5,x_value1=20,x_pixel1=320 if panel=='c'else 708,y_value0=40,y_pixel0=581.5,y_value1=160,y_pixel1=342.5)
        for current,guess in zip(CURRENTS,guesses):
            xp=axis['x_pixel0']+(axis['x_pixel1']-axis['x_pixel0'])*current/20;xc=round(xp);candidates=[]
            for y in range(guess-7,guess+8):
                xs=[x for x in range(xc-4,xc+5)if color_signal(color,im.getpixel((x,y)))]
                if xs:candidates.append(dict(y=y,matching_pixels=len(xs),x_min=min(xs),x_max=max(xs),horizontal_span=max(xs)-min(xs)+1))
            key=(panel,sample,current);rid='v14_Furfural_Fig10'+panel+'_'+sample+'_'+format(current,'g')
            r=dict(reading_id=rid,doi=FU,sample=sample,document='Furfural14_Fig10',curve_group='doi:'+FU+':Fig10'+panel+':'+sample,x_name='reported_current_A_g',x_value=current,x_uncertainty=0,x_value_origin='Six author GCD current labels and corresponding plotted rate-marker positions; zero here denotes nominal label, not experimental accuracy',y_name='capacitance_F_g',pixel_x=xp,selected_marker_column=xc,pixel_x_extent=[xc-4,xc+4],manual_roi_y=[guess-7,guess+7],color=color,color_candidates=candidates,axis=axis,panel='Fig10'+panel,extraction_batch='v14',not_independent_from_same_material_current_reports=True,retention_point_admitted=False,physical_test_group='doi:'+FU+':'+sample+':GCD:6MKOH:HgHgO:-1..0:j'+format(current,'g'))
            if key in OCCLUDED:
                assert not candidates,(key,'Expected occlusion changed; inspect original before replacing interval')
                r.update(kind='occluded_interval_only',y_value=None,y_uncertainty=None,pixel_y=None,occluding_sample=OCCLUDED[key][0],occlusion_basis=OCCLUDED[key][1],point_loss_eligible=False)
            else:
                assert candidates,(key,'No colour evidence; never interpolate missing markers')
                width=max(c['horizontal_span']for c in candidates);assert width>=3,(key,'Insufficient marker evidence')
                rows=[c['y']for c in candidates if c['horizontal_span']==width];yp=sum(rows)/len(rows)
                r.update(kind='bounded_marker_reading',pixel_y=yp,pixel_y_extent=[yp-4,yp+4],y_value=value_at(yp),y_uncertainty=4*120/239,y_lower_bound=value_at(yp+4),y_upper_bound=value_at(yp-4),point_loss_eligible=True,method='Center of widest horizontal colour-marker span inside declared original-pixel ROI; four vertical pixels cover marker/line/calibration reading, not SD/CI')
            readings.append(r)
    index={(r['panel'][-1],r['sample'],r['x_value']):r for r in readings}
    for r in readings:
        if r['kind']!='occluded_interval_only':continue
        front=index[('d',r['occluding_sample'],r['x_value'])];center=front['pixel_y'];assert center is not None
        r.update(occlusion_origin_reading_id=front['reading_id'],pixel_y_extent=[center-8,center+8],y_lower_bound=value_at(center+8),y_upper_bound=value_at(center-8),method='Conservative envelope of occluding marker plus calibration/hidden-marker radius, 8 original y pixels; no point estimate or midpoint imputation')
    assert len(readings)==54 and sum(r['y_value']is None for r in readings)==2
    return readings


def curate():
    assert sha(SOURCE)==SOURCE_SHA and sha(PARENT)==PSHA and not DB.exists()and not(OUT/'curation_spec.json').exists()and not(OUT/'merge_manifest.json').exists()
    archive=SOURCE.parent/'primary_assets.zip'
    with zipfile.ZipFile(archive)as z:
        for number in range(1,13):
            name='polymers-16-03421-g'+str(number).zfill(3)+'.jpg';assert(ASSETS/name).read_bytes()==z.read(name)
    root=E.parse(SOURCE).getroot();readings=capture();primary=[r for r in readings if not(r['panel']=='Fig10d'and r['sample']=='PC900-1')]
    assert len(primary)==48 and len({(r['sample'],r['x_value'])for r in primary})==48
    exact={('PC900-1',.5):153.03,('PC900-1',20):102,('PC900-0.1',.5):141.32,('PC900-0.1',20):114.32}
    for key,value in exact.items():
        r=next(r for r in primary if(r['sample'],r['x_value'])==key);assert r['y_lower_bound']<=value<=r['y_upper_bound']
    printed=[('c','PC700-1',63.1),('c','PC800-1',71.4),('c','PC900-1',66.7),('c','PC950-1',90.8),('d','FR900',79.3),('d','PC900-0',79.4),('d','PC900-0.1',80.7),('d','PC900-0.5',75.0),('d','PC900-1',66.7)]
    audits=[]
    for sample in NAMES[FU][1:]:
        first=next(r for r in primary if r['sample']==sample and r['x_value']==.5);last=next(r for r in primary if r['sample']==sample and r['x_value']==20)
        author={v for panel,s,v in printed if s==sample};assert len(author)==1;reported=author.pop();lo=100*last['y_lower_bound']/first['y_upper_bound'];hi=100*last['y_upper_bound']/first['y_lower_bound'];computed=100*last['y_value']/first['y_value'];exactratio=100*exact[(sample,20)]/exact[(sample,.5)]if(sample,.5)in exact else None
        graph_ok=lo<=reported<=hi;rounding_ok=exactratio is None or abs(exactratio-reported)<=.05
        status='printed_rate_vs_own_curve_unresolved'if not graph_ok else'printed_rate_vs_exact_reported_capacitances_unresolved'if not rounding_ok else'compatible_at_reported_or_figure_precision'
        audits.append(dict(sample=sample,author_rate_retention_pct=reported,derived_from_figure_pct=computed,derived_figure_interval_pct=[lo,hi],derived_from_reported_exact_capacitances_pct=exactratio,figure_interval_contains_author=graph_ok,reported_decimal_rounding_compatible=rounding_ok,canonical_rate_retention_pct=reported if graph_ok and rounding_ok else None,status=status,not_cycling_retention=True,action='Preserve all reports; unresolved rate annotation does not overwrite separately bound GCD point targets'))
    assert next(r for r in audits if r['sample']=='FR900')['status']=='printed_rate_vs_own_curve_unresolved'
    assert next(r for r in audits if r['sample']=='PC900-0.1')['canonical_rate_retention_pct']is None
    contributions=[dict(sample='PC900-1',scan_rate_mV_s=rate,capacitive_pct=c,diffusion_pct=d,printed_sum_pct=c+d,statistic='Author printed integer contributions, not retention or experimental replicate statistics',normalize_to100=False)for rate,c,d in [(5,72,29),(10,73,27),(20,76,24),(40,83,17),(60,90,10)]]
    aps=[s for s in NAMES[FU][1:]if s not in ['FR900','PC900-0']];annotations=[]
    for position,phase,plane,scope in [(26.5,'carbon','002',NAMES[FU][1:]),(42.6,'carbon','101',NAMES[FU][1:]),(20.9,'SiO2','100',NAMES[FU][1:])]+[(v,'ZnS',p,aps)for v,p in [(27.0,'100'),(28.6,'002'),(30.5,'101'),(39.7,'102'),(47.5,'110'),(51.7,'103'),(56.4,'112')]]:
        annotations.append(dict(id='XRD_'+phase+'_'+plane,kind='author_series_XRD_peak_assignment',value=position,unit='degree_2theta',phase=phase,plane=plane,scope_samples=scope,binding='Author body28 explicitly all samples or APS-added samples; one collective annotation, not one independent peak measurement per sample',source_document='Furfural14_Fig7',locator='body28 and actualFig7 labels; vertically offset arbitrary intensities not phase fractions',predictor_ready=False))
    for ident,lo,hi,assignment in [('OH',3560,3830,'O-H stretching'),('OH_NH',3439,3439,'combined O-H/N-H stretching'),('CH2',2920,2920,'CH2 stretching'),('CdoubleO',1430,1430,'author C=O assignment, not independently chemically reassigned'),('CN_CC',1520,1690,'author C-N/aromatic C=C and COO- discussion'),('CO_CN_SO',1105,1105,'author mixed C-O/C-N/S=O assignment'),('CH',450,825,'author C-H assignment')]:
        annotations.append(dict(id='FTIR_'+ident,kind='author_series_FTIR_band_assignment',lower=lo,upper=hi,unit='cm^-1',assignment=assignment,scope='Series-level comparison; not automatically a quantitative amount or an individually measured peak for every sample',source_document='Furfural14_Fig6',locator='body26 / actualFig6; source assignments retained without chemical certainty claim',predictor_ready=False))
    annotations.append(dict(id='ZnO_precursor_nominal_size',kind='precursor_recipe_property',value=30,author_plusminus=10,plusminus_statistic='unreported_not_assumed_SD',unit='nm',scope_samples=[s for s in NAMES[FU][1:]if s!='FR900'],stage='input_nanoZnO_before_carbonization_not_final_carbon_pore_size',source_document='Furfural14_main',locator='body9 nanoZnO diameter30±10nm; body11 FR900 nothing added',predictor_ready=False))
    remaining={1:'N2 adsorption/desorption branches remain to digitize; no new BET/STP recomputation',2:'Qualitative SEM/sample/scale review; no particle or pore population mean inferred',3:'Qualitative TEM,100/50nm scales; no population pore mean inferred',4:'EDS maps C/O/N/S,25um scales only; no quantitative table, S19.26wt% method still unbound',5:'Own angles34.2/8.7 and caption oppose body23; prior canonical freeze retained',6:'Seven source-level band assignments transcribed; raw arbitrary spectra remain',7:'Ten collective peak assignments transcribed; no phase mass fractions or normalized intensities',8:'Eight printed D/G and four fitted centers already v13; raw spectra/fitted components remain',9:'3E6MKOH/HgHgO -1..0; 20mVs sample comparisons and5/10/20/40/60/80/100/200mVs waveforms remain',10:'54 rate captures/48 nominal conditions,2 interval-only overlapped markers; a/b/e/f continuous GCD waveforms remain',11:'All curves inspected; raw Nyquist points remain, fitted Wd disagreement disclosed by authors, no curve-to-Rs guessing',12:'All five printed paired contributions read;5mVs72+29=101 retained, no renormalization'}
    figures=[]
    for number in range(1,13):
        figure=next(f for f in root.findall('.//fig')if f.get('id')=='polymers-16-03421-f'+str(number).zfill(3));path=ASSETS/('polymers-16-03421-g'+str(number).zfill(3)+'.jpg')
        figures.append(dict(figure_number=number,figure_id=figure.get('id'),path=path.relative_to(ROOT).as_posix(),sha256=sha(path),dimensions=list(Image.open(path).size),caption=clean(figure.find('caption')),review=remaining[number],full_quantitative_extraction_complete=None if number==4 else number in [5,12],quantitative_disposition='No numeric elemental quantification printed in EDS maps'if number==4 else'read scope and remaining work as stated',scientific_conflict_resolved=False if number==5 else None,full_source_review_complete=False))
    decisions=[dict(id='FR900_rate_annotation',status='unresolved',action='Printed79.3% conflicts with same-curve endpoint ratio approximately46.2%, even within declared pixel bounds; raw annotation and curve values retained, canonical rate ratio null; no cycle label created'),dict(id='PC900point1_rate_arithmetic',status='unresolved_existing_v13_dissent',action='Author80.7 vs114.32/141.32*100; do not hide exact-report discrepancy inside wider graph bounds'),dict(id='two_occluded_markers',status='interval_only_not_point',action='PC900-0 andPC900-0.1 at5Ag retain conservative graphical envelopes; no point or midpoint imputation, no invented exact labels'),dict(id='contribution101',status='printed_values_retained',action='5mVs72+29=101, integer rounding intervals can touch100 at a boundary; no forced normalization or author erratum claim'),dict(id='S_method',status='unresolved_method',action='ActualFig4 only EDS maps; conclusion19.26wt% has no quantitative measurement binding, keep method-unspecified field distinct fromICPZn1.19wt% and atomic channels'),dict(id='stage_and_control',status='explicit_recipe_only',action='FR900 body11 nothing added gives ZnO/APS recipe0; nanoZnO30±10nm is precursor, not final pore mean or final Zn fraction'),dict(id='series_annotations',status='method_qualified',action='10XRD+7FTIR+1precursor annotations are collective/stage-limited facts; no duplicated independent per-sample measurements or inferred composition'),dict(id='remaining_scope',status='partial_source',action='All12 original figures inspected; N2/CV/EIS and continuousGCD/raw spectra still unextracted, fullsource flagfalse; originalfixed38 and allcycling unchanged')]
    spec=dict(source=dict(doi=FU,path=SOURCE.relative_to(ROOT).as_posix(),sha256=SOURCE_SHA),original_figure_package=dict(path=archive.relative_to(ROOT).as_posix(),sha256=sha(archive),all12originalmembers_equal=True),parent_sha256=PSHA,readings=readings,primary_reading_ids=[r['reading_id']for r in primary],reported_exact_anchors=[dict(sample=s,current_A_g=j,value=v,locator='body34, existingv13 GCD_prose')for(s,j),v in exact.items()],printed_rate_annotations=[dict(panel='Fig10'+p,sample=s,rate_retention_pct=v)for p,s,v in printed],rate_ratio_audits=audits,contributions=contributions,series_annotations=annotations,figures=figures,decisions=decisions,formal_cycling_admissions=0,model_fits=0,full_source_review_complete=False)
    write(OUT/'curation_spec.json',spec)
    print(json.dumps(dict(readings=len(readings),numeric_readings=sum(r['y_value']is not None for r in readings),nominal_conditions=len(primary),numeric_nominal_conditions=sum(r['y_value']is not None for r in primary),interval_only=2,series_annotations=len(annotations),figure_reviews=len(figures),model_fits=0)))


def build():
    assert not DB.exists()and not(OUT/'merge_manifest.json').exists()and sha(PARENT)==PSHA
    from data.literature_v13 import open_literature_database
    spec=json.loads((OUT/'curation_spec.json').read_text('utf8'));assert spec['readings']==capture()
    with open_literature_database(PARENT,PSHA)as old:exact={(r['sample_name'],r['current_A_g']):r for r in old.template_residue_gcd_inputs()}
    main='Furfural14_main';si='Furfural14_SI';docs={main:SOURCE,si:ROOT/'文献全量利用复核_20261026/批次13_芒果核皮革糠醛渣与界面参考/evidence/polymers-3313966-supplementary.pdf'}
    for f in spec['figures']:docs['Furfural14_Fig'+str(f['figure_number'])]=ROOT/f['path']
    units=[]
    for panel in ['c','d']:
        rows=[r for r in spec['readings']if r['panel']=='Fig10'+panel]
        cells=[[r['sample'],format(r['x_value'],'g'),('bounded %.10g F/g; originalpixel(%.4g,%.4g),4pxbound'%(r['y_value'],r['pixel_x'],r['pixel_y']))if r['y_value']is not None else'pointunresolved; graphicalinterval[%.10g,%.10g]F/g'%(r['y_lower_bound'],r['y_upper_bound']),r['kind']]for r in rows]
        units.append(dict(id='FU14_Fig10'+panel+'_rate',document='Furfural14_Fig10',rows=cells,header=['sample','current_A_g','derived_graph_reading_not_author_table_number','quality'],kind='bounded_original_figure_point_transcription',locator='ActualFig10'+panel+' rate markers, original752x939pixels; 4px readingbounds, 8px occlusion envelopes'))
    units.append(dict(id='FU14_Fig12_contribution',document='Furfural14_Fig12',rows=[[r['sample'],str(r['scan_rate_mV_s']),str(r['capacitive_pct']),str(r['diffusion_pct'])]for r in spec['contributions']],header=['sample','scan_mV_s','capacitive_pct','diffusion_pct'],kind='own_printed_figure_annotations',locator='ActualFig12 five pairs;72+29 retained101, not renormalized'))
    units.append(dict(id='FU14_rate_annotations',document='Furfural14_Fig10',rows=[[r['sample'],r['panel'],str(r['rate_retention_pct'])]for r in spec['printed_rate_annotations']],header=['sample','panel','author_rate_pct'],kind='own_printed_rate_annotation_not_cycling',locator='ActualFig10c/d printed rate percentages; FR90079.3 preserved as disputed annotation'))
    units.append(dict(id='FU14_FTIR_annotations',document=main,rows=[[r['id'],str(r['lower']),str(r['upper']),r['unit'],r['assignment']]for r in spec['series_annotations']if r['kind']=='author_series_FTIR_band_assignment'],header=['id','lower','upper','unit','author_assignment'],kind='own_series_body_figure_annotation',locator='body26 andactualFig6; series-level assignments, no per-sample quantitative inheritance'))
    units.append(dict(id='FU14_XRD_precursor_annotations',document=main,rows=[[r['id'],str(r['value']),str(r.get('author_plusminus','')),r['unit'],r['kind']]for r in spec['series_annotations']if r['kind']!='author_series_FTIR_band_assignment'],header=['id','value','author_plusminus','unit','stage_kind'],kind='own_series_stage_limited_annotation',locator='body28/actualFig7 XRD collective positions; body9 nanoZnO30±10nm precursor, not final pores'))
    with closing(ro(PARENT))as parent,closing(sqlite3.connect(DB))as c:
        parent.backup(c);c.row_factory=sqlite3.Row;c.execute('pragma foreign_keys=on');c.executescript('''create table source_reviews_v14(doi text primary key references reviewed_sources,record_json text);create table figure_scope_reviews_v14(doi text references reviewed_sources,figure_number integer,document_key text references source_documents,record_json text,primary key(doi,figure_number));create table series_annotations_v14(annotation_id text primary key,doi text references reviewed_sources,document_key text references source_documents,record_json text);create table purpose_reviews_v14(observation_id text primary key references capacitance_observations,reading_id text references curve_samples_v8,purpose text,point_input_ready integer,interval_input_ready integer,record_json text);create table rate_ratio_reviews_v14(material_key text primary key references materials,record_json text);create table contribution_pairs_v14(material_key text references materials,scan_rate_mV_s real,record_json text,primary key(material_key,scan_rate_mV_s));create table decisions_v14(decision_id text primary key,doi text references reviewed_sources,record_json text);''')
        for key,path in docs.items():insert(c,'source_documents',dict(document_key=key,doi=FU,path=path.relative_to(ROOT).as_posix(),sha256=sha(path),role='original_own_figure'if 'Fig'in key else'primary_XML'if key==main else'own_original_SI_exact_archive_member'))
        for unit in units:
            key=FU+'#'+unit['id'];insert(c,'reviewed_tables',dict(table_key=key,doi=FU,xml_id=unit['id'],caption=unit['locator'],header_json=json.dumps(unit['header']),footnote='Derived review transcription/authorseriesannotation, not a newly discovered native experimental table',source_raw_table_id=None));insert(c,'table_source_links',dict(table_key=key,document_key=unit['document'],locator=unit['locator']));insert(c,'extraction_units_v3',dict(table_key=key,kind=unit['kind'],scope='Own explicitly stated scope; plot copies and exact text anchors remain same nominal source/test'))
            for rownum,row in enumerate(unit['rows'],1):insert(c,'transcribed_rows',dict(table_key=key,row_ordinal=rownum,cells_json=json.dumps(row,ensure_ascii=False)));insert(c,'transcription_origins_v7',dict(table_key=key,row_ordinal=rownum,origin_json=json.dumps(dict(document=unit['document'],locator=unit['locator'],row=rownum,not_original_native_table=True),ensure_ascii=False)))
        panel_rows=collections.Counter();primary=set(spec['primary_reading_ids'])
        for r in spec['readings']:
            insert(c,'curve_samples_v8',dict(reading_id=r['reading_id'],material_key=mk(FU,r['sample']),document_key='Furfural14_Fig10',reading_json=json.dumps(r,ensure_ascii=False)))
            panel_rows[r['panel']]+=1;rownum=panel_rows[r['panel']]
            if r['reading_id']not in primary:continue
            key=FU+'#FU14_'+r['panel']+'_rate';obs=key+'#'+str(rownum)+'#2';raw=json.loads(c.execute('select cells_json from transcribed_rows where table_key=?and row_ordinal=?',(key,rownum)).fetchone()[0])[2]
            cond=dict(extraction_batch='v14',physical_test_group=r['physical_test_group'],current_mass_basis='author_reported_unknown_not_inferred',voltage_lower_V=-1,voltage_upper_V=0,reference_electrode='Hg/HgO',capacitance_basis='single_working_carbon_electrode',final_native_SiO2_XRD_present=True,final_ZnS_XRD_reported=r['sample']not in ['FR900','PC900-0'],protocol_document_key=si,protocol_locator='SIp2/3, mainbody32/34, actualFig10GCD',point_kind=r['kind'],graphical_lower_bound=r['y_lower_bound'],graphical_upper_bound=r['y_upper_bound'],bound_semantics='graphical reading/occlusion range, not an experimental confidence interval',not_independent_of_own_text_or_second_plot_copy=True)
            insert(c,'capacitance_observations',dict(observation_id=obs,material_key=mk(FU,r['sample']),table_key=key,row_ordinal=rownum,column_ordinal=2,value=r['y_value'],raw_value=raw,unit='F/g',method='GCD',system='3E',electrolyte='KOH',concentration_mol_L=6,current_A_g=r['x_value'],scan_rate_mV_s=None,conditions_json=json.dumps(cond,ensure_ascii=False),status='bounded_original_figure_not_exact_author_number'if r['y_value']is not None else'occluded_marker_interval_only_no_point',source_group='doi:'+FU,training_eligible=0))
            anchor=exact.get((r['sample'],r['x_value']));review=dict(author_exact_observation_id=anchor['observation_id']if anchor else None,lower_bound=r['y_lower_bound'],upper_bound=r['y_upper_bound'],physical_test_group=r['physical_test_group'],point_kind=r['kind'],primary_panel_policy='Fig10c forPC900-1, Fig10d forAPS/controlothers; chosen as sourcepanel roles, not to select higher/lower performance',current_A_g=r['x_value'],ordinary_profile=False,exact_text_and_graph_not_independent=True)
            if anchor:assert r['y_lower_bound']<=anchor['value']<=r['y_upper_bound']
            insert(c,'purpose_reviews_v14',dict(observation_id=obs,reading_id=r['reading_id'],purpose='reported_furfural_residue_3e_GCD_with_graphical_bounds',point_input_ready=int(r['y_value']is not None),interval_input_ready=1,record_json=json.dumps(review,ensure_ascii=False)))
        def response(sample,unit,rownum,col,metric,value,extra):
            key=FU+'#'+unit;obs=key+'#'+str(rownum)+'#'+str(col);raw=json.loads(c.execute('select cells_json from transcribed_rows where table_key=?and row_ordinal=?',(key,rownum)).fetchone()[0])[col]
            insert(c,'outcome_observations_v3',dict(outcome_id=obs,material_key=mk(FU,sample),table_key=key,record_json=json.dumps(dict(source_group='doi:'+FU,extraction_batch='v14',metric=metric,value=value,raw_value=raw,unit='%',feature_role='test_response_not_pretest_material_predictor',**extra),ensure_ascii=False),training_eligible=0))
        for i,r in enumerate(spec['contributions'],1):
            for col,metric in [(2,'capacitive_contribution'),(3,'diffusion_contribution')]:response(r['sample'],'FU14_Fig12_contribution',i,col,metric,r['capacitive_pct'if col==2 else'diffusion_pct'],dict(scan_rate_mV_s=r['scan_rate_mV_s'],printed_sum_pct=r['printed_sum_pct'],not_cycling_retention=True))
            insert(c,'contribution_pairs_v14',dict(material_key=mk(FU,r['sample']),scan_rate_mV_s=r['scan_rate_mV_s'],record_json=json.dumps(r,ensure_ascii=False)))
        for i,r in enumerate(spec['printed_rate_annotations'],1):response(r['sample'],'FU14_rate_annotations',i,2,'rate_capacitance_retention',r['rate_retention_pct'],dict(current_from_A_g=.5,current_to_A_g=20,panel=r['panel'],not_cycling_retention=True,original_annotation_not_canonical_ratio=True))
        for r in spec['rate_ratio_audits']:insert(c,'rate_ratio_reviews_v14',dict(material_key=mk(FU,r['sample']),record_json=json.dumps(r,ensure_ascii=False)))
        for r in spec['series_annotations']:insert(c,'series_annotations_v14',dict(annotation_id='LP14_'+r['id'],doi=FU,document_key=r['source_document'],record_json=json.dumps(dict(r,supporting_main_document=main,not_independent_per_sample_measurements=True),ensure_ascii=False)))
        for r in spec['figures']:insert(c,'figure_scope_reviews_v14',dict(doi=FU,figure_number=r['figure_number'],document_key='Furfural14_Fig'+str(r['figure_number']),record_json=json.dumps(r,ensure_ascii=False)))
        for r in spec['decisions']:
            did='LP14_'+r['id'];insert(c,'decisions_v14',dict(decision_id=did,doi=FU,record_json=json.dumps(r,ensure_ascii=False)));insert(c,'scientific_issues',dict(issue_id=did,doi=FU,sample_name=None,issue_json=json.dumps(dict(kind=did,action=r['action'],status=r['status']),ensure_ascii=False)))
        insert(c,'source_reviews_v14',dict(doi=FU,record_json=json.dumps(dict(scope='All12originalfigures inspected; twoGCD-ratepanels captured, contributionpairs and collective spectral/precursor annotations; inherited own tables/SI kept',remaining='N2/CV/EIS/continuousGCD/raw spectral waveforms remain; S method and contact/rate disputes remain',full_source_review_complete=False,point_target_conditions=46,interval_target_conditions=48,not_new_source=True),ensure_ascii=False)));c.commit()
    protected={p for p in docs.values()}|{SOURCE.parent/'primary_assets.zip',ASSETS/'polymers-16-03421-s001.zip',PARENT,ROOT/'循环稳定性数据库_v0.25_芒果核皮革循环准入_20261026/cycling_v0_25.sqlite'}
    write(OUT/'protected_inputs.json',[dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p))for p in sorted(protected)])
    print('Built unsealed v14:48 graph reports/46 numeric/2 interval-only, no cycle admission or fit')


if __name__=='__main__':
    if len(sys.argv)!=2 or sys.argv[1]not in ['curate','build']:raise SystemExit('One-use curate/build; verify/seal separate')
    globals()[sys.argv[1]]()
