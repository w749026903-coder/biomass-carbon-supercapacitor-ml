"""Selected remaining-SI extraction; deterministic sealed reports and pinned dependencies."""
from pathlib import Path
from contextlib import closing
import csv,hashlib,importlib.util,io,json,math,re,sqlite3,sys,xml.etree.ElementTree as E
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
OUT=ROOT/'文献全量利用复核_20261026/批次06_剩余SI与DES协议';DB=OUT/'literature_material_pool_v6.sqlite'
PARENT=ROOT/'文献全量利用复核_20261025/批次05_碳化系列与多电解液/literature_material_pool_v5.sqlite'
PARENT_SHA='b632d3b74123a644dc7cd72a139640a14355bb5c4420d5b34ebc7300620ea578'
G='10.1021/acsomega.3c00816';W='10.1016/j.isci.2026.117248'
CORPUS=ROOT/'全库复检与特征补提取_20261021/full_corpus_search_native.sqlite'
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf8')
def ro(p):return sqlite3.connect(Path(p).resolve().as_uri()+'?mode=ro',uri=True)
def txt(e):return ' '.join(''.join(e.itertext()).split()) if e is not None else ''
def mk(d,s):return 'literature:'+hashlib.sha256((d+'\0'+s).encode()).hexdigest()[:24]
def numeric(raw,component='whole'):
    if component=='mean':raw=raw.split('±')[0].strip()
    if component=='uncertainty':raw=raw.split('±')[1].strip()
    if not re.fullmatch(r'\d+(?:\.\d+)?',raw):return None
    return float(raw)*(.1 if component=='angstrom_to_nm' else 1)
def insert(c,table,values):
    # Identifiers are internal code constants, not literature text.
    fields=list(values)
    c.execute('insert into '+table+' ('+','.join(fields)+') values ('+','.join('?' for _ in fields)+')',[values[k] for k in fields])

def build():
    if DB.exists() or (OUT/'merge_manifest.json').exists():raise FileExistsError('Do not overwrite a draft or release.')
    assert sha(PARENT)==PARENT_SHA
    assert sha(CORPUS)=='f2720c3e417904dad5857a6574cc72d5cf996f9b8716620d69594f11380c658c'
    spec=json.loads((OUT/'curation_spec.json').read_text('utf8'));receipt=[]
    assert all(len(row)==len(t['header']) for t in spec['tables'] for row in t['rows'])
    with closing(ro(PARENT)) as old:
        old.row_factory=sqlite3.Row
        docs={r['document_key']:dict(r) for r in old.execute("select * from source_documents where document_key in ('Weigela_SI','Weigela','Glycogen_SI','Glycogen')")}
    for d in docs.values():assert sha(ROOT/d['path'])==d['sha256']
    assert docs['Glycogen_SI']['sha256']=='4924bb0d36b244c7967bb526ae55ed7ffb0eb514b252bcfdf71b82fc6b3017a9'
    for label,filename in [('Glycogen_Fig10','ao3c00816_0011.jpg'),('Glycogen_Fig11','ao3c00816_0012.jpg')]:
        path='同体系文献补充_第二批_20261017/定向扩搜40至60篇_20261017/sources/OA041/figures/'+filename
        docs[label]=dict(document_key=label,doi=G,path=path,sha256=sha(ROOT/path),role='original_graphic')
    root=E.parse(ROOT/docs['Glycogen']['path']).getroot();paragraphs=root.findall('.//body//p')
    with closing(ro(PARENT)) as old,closing(sqlite3.connect(DB)) as c:
        old.backup(c);c.row_factory=sqlite3.Row;c.execute('pragma foreign_keys=on')
        c.executescript('''
          create table diffraction_peaks_v6(peak_id text primary key,material_key text references materials,table_key text references reviewed_tables,row_ordinal integer,record_json text);
          create table report_variants_v6(variant_id text primary key,material_key text references materials,document_key text references source_documents,locator text,metric text,value real,raw_value text,unit text,conditions_json text,training_eligible integer check(training_eligible=0));
          create table capacitance_current_decisions_v6(observation_id text primary key references capacitance_observations,selected_current_A_g real,decision_json text);
          create table figure_protocol_reviews_v6(review_id text primary key,document_key text references source_documents,record_json text);
          create table fact_components_v6(fact_id integer primary key references material_facts,component text,conversion_factor real,qualification text);
          create table purpose_reviews_v6(observation_id text references capacitance_observations,purpose text,eligible integer check(eligible=1),review_json text,primary key(observation_id,purpose));
        ''')
        for key in ['Glycogen_Fig10','Glycogen_Fig11']:
            insert(c,'source_documents',docs[key])
        def material(doc,sample,stage='final_biomass_carbon_before_test'):
            key=mk(docs[doc]['doi'],sample)
            if not c.execute('select 1 from materials where material_key=?',(key,)).fetchone():
                insert(c,'materials',dict(material_key=key,doi=docs[doc]['doi'],sample_name=sample,material_stage=stage))
            return key
        units={}
        for t in spec['tables']:
            key=docs[t['doc']]['doi']+'#'+t['id'];loc='PDF physical p'+str(t['page'])+' '+t['id'].removesuffix('_v6')
            insert(c,'reviewed_tables',dict(table_key=key,doi=docs[t['doc']]['doi'],xml_id=t['id'],caption=t['id']+'; selected own rows as specified',header_json=json.dumps(t['header'],ensure_ascii=False),footnote='Canonical sample bindings and header spelling normalized for structured transcription; original PDF layout retained. All numeric/ND/dash tokens preserved.',source_raw_table_id=t['raw_table_id']))
            insert(c,'table_source_links',dict(table_key=key,document_key=t['doc'],locator=loc))
            for i,row in enumerate(t['rows'],1):insert(c,'transcribed_rows',dict(table_key=key,row_ordinal=i,cells_json=json.dumps(row,ensure_ascii=False)))
            insert(c,'extraction_units_v3',dict(table_key=key,kind=t['kind'],scope='Declared own rows and numeric fields only; no foreign comparison as own measurement.'))
            if t['raw_table_id']:
                assert c.execute('select count(*) from raw_table_queue where table_id=?',(t['raw_table_id'],)).fetchone()[0]==1
                c.execute('update raw_table_queue set review_state=? where table_id=?',('v6_selected_SI_own_cells_reviewed_foreign_rows_not_own_labels',t['raw_table_id']))
            units[(t['doc'],t['id'])]=(key,t);receipt.append(dict(table_key=key,document=t['doc'],locator=loc,raw_table_id=t['raw_table_id'],kind=t['kind'],structured_rows=len(t['rows'])))
        def fact(doc,sample,key,i,col,field,raw,unit,method,component='whole',stage='final_biomass_carbon_before_test'):
            value=numeric(raw,component)
            status='own_reported_value_method_qualified_not_model_admission'
            if raw=='ND':status='author_not_detected_detection_limit_unreported_not_zero'
            elif raw=='---':status='author_dash_not_quantified_not_zero'
            elif value is None:raise ValueError('Unexpected numeric token '+raw)
            if component=='angstrom_to_nm':status='selected_002_peak_with_explicit_A_to_nm_conversion'
            cur=c.execute('insert into material_facts(material_key,field_name,value,raw_value,unit,method,table_key,row_ordinal,column_ordinal,source_sha256,review_status,training_eligible) values(?,?,?,?,?,?,?,?,?,?,?,0)',(material(doc,sample,stage),field,value,raw,unit,method,key,i,col,docs[doc]['sha256'],status))
            insert(c,'fact_components_v6',dict(fact_id=cur.lastrowid,component=component,conversion_factor=.1 if component=='angstrom_to_nm' else 1,qualification=method))
        key,t=units[('Weigela_SI','SI_TableS1_v6')]
        for col,field,unit,method in [(1,'BET_surface_area_m2_g','m2/g','BET'),(2,'micropore_surface_area_m2_g','m2/g','author Smic; exact fit model not further inferred'),(3,'micropore_volume_cm3_g','cm3/g','t-plot; mainTable1footnote b'),(4,'meso_plus_macro_volume_cm3_g','cm3/g','BJH combined meso+macro, not mesopore alone'),(5,'total_pore_volume_cm3_g','cm3/g','BJH author total'),(6,'BJH_average_pore_diameter_nm','nm','BJH author average')]:
            fact('Weigela_SI','NWJPC-2.5',key,1,col,field,t['rows'][0][col],unit,method)
        inherited=[dict(stage='hydrothermal_carbonization',temperature_C=None,duration_h=4,field_state='inherited_same_source_common_method_not_independently_stated_for2.5'),dict(stage='chemical_activation',temperature_C=800,duration_h=2,heating_rate_C_min=5,atmosphere='N2',agent='KOH',carbon_to_activator_mass_ratio=[1,1],melamine_to_hydrochar_mass_ratio=2.5,ratio_basis='AuthorXseriesdefinition in mainp90 plus ownSI sampleNWJPC2.5 andp24',field_state='inherited_author_series_protocol_not_independent_sample_measurement')]
        insert(c,'synthesis_stages_v3',dict(material_key=mk(W,'NWJPC-2.5'),document_key='Weigela',locator='XML body//p24,p89-90 andSIphysicalp6TableS1; inheritance explicitly marked',stages_json=json.dumps(inherited,ensure_ascii=False)))
        for ident,samples in [('SI_TableS1',['raw_glycogen','GC_1000C_0.5h','GC_1000C_1h','GC_1000C_3h','GC_1000C_4h','GC_1000C_5h','GC_1000C_7h']),('SI_TableS2',['GC_500C_1h','GC_750C_1h','GC_1200C_1h'])]:
            key,t=units[('Glycogen_SI',ident)]
            for i,row in enumerate(t['rows'],1):
                field='XPS_'+row[0].split()[0]+'_at_pct'
                for col,sample in enumerate(samples,1):fact('Glycogen_SI',sample,key,i,col,field,row[col],'at%','XPS explicit elemental atomic%; ND and dash remain separate states',stage='raw_glycogen_before_carbonization' if sample=='raw_glycogen' else 'final_biomass_carbon_before_test')
        key,t=units[('Glycogen_SI','SI_TableS3')]
        for i,row in enumerate(t['rows'],1):
            sample='GC_'+row[0]+'C_1h'
            fact('Glycogen_SI',sample,key,i,1,'Raman_ID_IG',row[1],'ratio','Raman reported mean±; uncertainty type not stated','mean')
            fact('Glycogen_SI',sample,key,i,1,'Raman_ID_IG_reported_uncertainty',row[1],'ratio','Author ± value, no SD/SEM interpretation','uncertainty')
            fact('Glycogen_SI',sample,key,i,2,'Raman_derived_crystallite_La_nm',row[2],'nm','Author La derived from RamanID/IG and532nm, not independent observation')
        key,t=units[('Glycogen_SI','SI_TableS4')]
        for i,row in enumerate(t['rows'],1):
            record=dict(peak_number=int(row[1]),two_theta_deg=float(row[2]),d_A=float(row[3]),FWHM_deg=float(row[4]),integrated_intensity_counts_deg=float(row[5]),integrated_width_deg=float(row[6]),row_ordinal=i,stage='before_cycling',original_sample_group='Glycogen-based carbon at1000C '+('1h' if '1h' in row[0] else '5h'),not_all_peaks_are_d002=True)
            insert(c,'diffraction_peaks_v6',dict(peak_id=key+'#'+str(i),material_key=material('Glycogen_SI',row[0]),table_key=key,row_ordinal=i,record_json=json.dumps(record,ensure_ascii=False)))
            if row[1]=='2':fact('Glycogen_SI',row[0],key,i,3,'XRD_d002_nm',row[3],'nm','OwnTableS4(002) peak; explicit0.1nm/angstrom conversion; sample-specific table selected, competing body3.8A retained as variant','angstrom_to_nm')
        key,t=units[('Glycogen_SI','SI_TableS5')]
        metrics=[('EIS_Re_ohm','ohm'),('EIS_Rt_ohm','ohm'),('EIS_CPE_alpha','dimensionless'),('EIS_CPE_Q','microF s^(alpha-1)'),('EIS_Wd','ohm^-1 s^0.5')]
        for i,row in enumerate(t['rows'],1):
            hours=row[1].removesuffix('.0');sample='GC_'+row[0]+'C_'+hours+'h'
            for col,(metric,unit) in enumerate(metrics,2):
                raw=row[col];rec=dict(metric=metric,fit_parameter=True,value=numeric(raw,'mean'),reported_uncertainty=numeric(raw,'uncertainty'),uncertainty_description='Author ±s confidence intervals of fit; numerical confidence level not stated',raw_value=raw,unit=unit,electrolyte='ethaline_ChCl_EG_1to2',temperature_C=30,source_group='doi:'+G,row_ordinal=i,column_ordinal=col,feature_role='same_test_EIS_response_not_pretest_material_predictor',extraction_batch='v6')
                insert(c,'outcome_observations_v3',dict(outcome_id=key+'#'+str(i)+'#'+str(col),material_key=material('Glycogen_SI',sample),table_key=key,record_json=json.dumps(rec,ensure_ascii=False),training_eligible=0))
        key,t=units[('Glycogen_SI','SI_TableS6_selected_own')]
        for i,row in enumerate(t['rows'],1):
            cond=dict(duplicate_of_main_table3_or_body_p80=True,physical_test_group=G+'#GC_1000C_5h#'+('3E_liquid_DES' if i==1 else '2E_SSE_DES'),capacitance_basis='single_working_electrode' if i==1 else 'device_total_two_electrode_active_mass',current_binding='Printed1A/g multirow header applies to both own rows; corroborated by own main Table3 andp80')
            insert(c,'capacitance_observations',dict(observation_id=key+'#'+str(i)+'#6',material_key=material('Glycogen_SI','GC_1000C_5h'),table_key=key,row_ordinal=i,column_ordinal=6,value=float(row[6]),raw_value=row[6],unit='F/g',method='GCD',system='3E' if i==1 else '2E_symmetric_solid_DES',electrolyte='ethaline_ChCl_EG_1to2' if i==1 else 'SSE_ethaline',concentration_mol_L=None,current_A_g=1,scan_rate_mV_s=None,conditions_json=json.dumps(cond,ensure_ascii=False),status='repeat_own_report_not_additional_training_example',source_group='doi:'+G,training_eligible=0))
            insert(c,'report_variants_v6',dict(variant_id='Glycogen_SI_retention_'+str(i),material_key=material('Glycogen_SI','GC_1000C_5h'),document_key='Glycogen_SI',locator='PDF physicalp11TableS6ownrow'+str(i),metric='cycling_retention_pct',value=99 if i==1 else 75,raw_value=row[7],unit='%',conditions_json=json.dumps(dict(system='3E' if i==1 else '2E_symmetric_solid_DES',cycle_count=1000,current_A_g=1,not_independent_new_test=True,main_report_pct=100 if i==1 else 75,main_reported_uncertainty=2 if i==1 else None,interpretation='99 lies within main reported100±2; source-specific presentations preserved, no averaging or author-erratum claim'),ensure_ascii=False),training_eligible=0))
        insert(c,'report_variants_v6',dict(variant_id='Glycogen_body_d002_5h',material_key=material('Glycogen','GC_1000C_5h'),document_key='Glycogen',locator='XML body//p53',metric='XRD_d002_A',value=3.8,raw_value='3.8 A',unit='angstrom',conditions_json=json.dumps(dict(selected=False,selected_own_table_A=3.7,own_two_theta_deg=23.9,Bragg_crosscheck_A=round(1.54060/(2*math.sin(math.radians(23.9/2))),4),decision='Sample-specific TableS4 plus reported peak angle supports3.7A; body3.8A retained, no silent rewrite or author erratum.'),ensure_ascii=False),training_eligible=0))
        obs=G+'#own_body_p80#1#2'
        assert c.execute('select current_A_g from capacitance_observations where observation_id=?',(obs,)).fetchone()[0]==.01
        decision=dict(original_prose_current_A_g=.01,selected_current_A_g=.1,value_F_g=802,basis='OriginalFigure11e printed0.1A/g→10A/g annotation; owncaption andp79say0.1–10A/g. p80says0.01, retained as dissent.',source_paths=[docs['Glycogen_Fig11']['path'],docs['Glycogen']['path']],source_sha256s=[docs['Glycogen_Fig11']['sha256'],docs['Glycogen']['sha256']],not_author_erratum=True,not_new_experiment=True)
        insert(c,'capacitance_current_decisions_v6',dict(observation_id=obs,selected_current_A_g=.1,decision_json=json.dumps(decision,ensure_ascii=False)))
        for name,doc,record in [('Glycogen_first_cycle','Glycogen_Fig10',dict(initial_cycle_GCD_window_V=[0,1],current_A_g=1,temperature_C=30,sample_scope='all twelve own carbonization rows',cycle_number=1,later_1000cycle_window_independently_plotted=False,scope='Actual first-cycleGCD is shown; do not infer every later cycle potential without explicitbinding.')),('Glycogen_SSE','Glycogen_Fig11',dict(first_eight_cycles_GCD_window_V=[0,1],plotted_current_A_g=10,reported_retention_current_A_g=1,retention_cycle_count=1000,scope='Figure11d10A/gfirst8cycles is not the1A/g1000cycle experiment; cannot transfer its exact cyclewindow automatically.'))]:
            insert(c,'figure_protocol_reviews_v6',dict(review_id=name,document_key=doc,record_json=json.dumps(record,ensure_ascii=False)))
        issues=[('LP6_ND_dash',G,'all',dict(kind='XPS_not_detected_and_unreported_distinct',action='KeepND and---separate,null not0; rawglycogen is separateprecursor, no transfer to carbonizedsamples.')),
          ('LP6_Raman_uncertainty',G,'GC_1000C_1h',dict(kind='reported_uncertainty_competing',main_ID_IG='1.563±0.004',SI_ID_IG='1.563±0.007',action='Mean agrees; both author±values retained, no unstatedSD/SEM interpretation or silent uncertaintyselection.')),
          ('LP6_XRD_spacing',G,'GC_1000C_5h',dict(kind='sample_specific_XRD_table_and_body_difference',table_d_A=3.7,body_d_A=3.8,table_two_theta_deg=23.9,action='Use own sample-specific(002)TableS4 spacing, geometricBraggcrosscheck consistent; retainbody3.8A asvariant. Otherpeaks not d002; A to nm explicit.')),
          ('LP6_DES_retention',G,'GC_1000C_5h',dict(kind='same_source_summary_within_reported_uncertainty',main_pct=100,main_plus_minus=2,SI_summary_pct=99,action='Keep100±2 and99 ownreports; not additionalexperiments, no averaging, no authorerratum invented.')),
          ('LP6_SSE_current',G,'GC_1000C_5h',dict(kind='current_prose_decimal_vs_own_axis',main_prose_A_g=.01,figure_annotation_and_caption_A_g=.1,action='Select0.1fromactualcurrentaxis+caption+p79; preserve0.01asrawv5sourcevalue in current API.')),
          ('LP6_protocol_scope',G,'all',dict(kind='initial_curve_vs_full_retention_protocol_scope',action='For liquid3E, ownTable3 binds firstcycleC/1000cycleretention for eachsample undercommon1A/g/30C protocol andownFig10 shows eachsample0..1V; accepted separateDESreportedmean purpose underexistingtable/commonprotocolrule. SSEFig11d is10A/g8cycles, not1A/g1000; do not transfer thatwindow. Neither is ordinaryaqueousmembership.'))]
        for ident,doi,sample,issue in issues:insert(c,'scientific_issues',dict(issue_id=ident,doi=doi,sample_name=sample,issue_json=json.dumps(issue,ensure_ascii=False)))
        for row in c.execute('select observation_id,material_key from capacitance_observations where table_key=?',(G+'#tbl3',)).fetchall():
            for target in ['capacitance','retention']:
                review=dict(purpose='reported_DES_3e_'+target+'_mean',scope='3E neatethaline,ChCl:EG1:2,30C,reported1A/g; author mean±targets',window_V=[0,1],window_evidence='OwnFig10eachsampleactualfirst-cycleGCD + ownTable3firstcycleC and1000cycleretention in same row/commonprotocol +SIp3-4. Existingtable/commonprotocoldecision applies; not CV-window substitution or demandforeverycycleplot.',source_group='doi:'+G,independent_source_groups=1,later_cycles_independently_plotted=False,main_table_preferred_over_summary='OwnTable3includesreporteduncertainty; SI99%variant retained within100±2%, not averaged.',not_ordinary_aqueous=True,no_new_training_authorization=True)
                insert(c,'purpose_reviews_v6',dict(observation_id=row['observation_id'],purpose=review['purpose'],eligible=1,review_json=json.dumps(review,ensure_ascii=False)))
        c.commit()
    pinned=json.loads((ROOT/'data/current_database.json').read_text('utf8'))
    protected=[PARENT,CORPUS]+[ROOT/d['path'] for d in docs.values()]+[ROOT/pinned['version_directory']/pinned['database_file']]
    write(OUT/'protected_inputs.json',dict(files=[dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p)) for p in protected],pinned_cycling_pointer=pinned,dependency_policy='Verify immutable files by these hashes; do not require global pointers to stay frozen forever.'))
    write(OUT/'table_review_receipt.json',receipt)
    write(OUT/'source_review_notes.json',dict(Weigela='Own SI TableS1 NWJPC2.5 sixproperties extracted; no electrochemical numbers reported for this sample in selectedSI. Othergraphs remain to digitize.',Glycogen='All sixSI tables reviewed for declaredownrows; XPS/Raman/XRD/EIS typed, references excluded. Liquid3E ownTable3 andeachsampleFig10 share1A/g/30C protocol:0..1V accepted for separateDESreportedmean purpose; no extra everycycleplot gate. SSE10A/g8cyclefigure cannot supply1A/g1000cyclewindow. Maintext remainingCV/othercurves and method-specific quality remain incomplete.',all_literature_goal_complete=False))
    print('Built v6; unsealed pending independent-process verification.')

def verify(write_reports=False):
    checks=[]
    def check(name,ok):
        if not ok:raise AssertionError(name)
        checks.append(name)
    protection=json.loads((OUT/'protected_inputs.json').read_text('utf8'))
    for p in protection['files']:check('input_'+p['path'],sha(ROOT/p['path'])==p['sha256'])
    from data.literature_v4 import open_literature_database as old_api,PROFILES
    from data.literature_v6 import open_literature_database as new_api,DES_PREDICTORS
    digest=sha(DB)
    with closing(ro(DB)) as c,closing(ro(PARENT)) as old:
        c.row_factory=sqlite3.Row
        check('integrity',c.execute('pragma integrity_check').fetchone()[0]=='ok');check('foreignkeys',not c.execute('pragma foreign_key_check').fetchall())
        for (table,) in old.execute("select name from sqlite_master where type='table' and name not like 'sqlite_%'"):
            if table=='raw_table_queue':continue
            current={tuple(r) for r in c.execute('select * from '+table)};check('parent_'+table,all(tuple(r) in current for r in old.execute('select * from '+table)))
        oldq={r[0]:tuple(r) for r in old.execute('select * from raw_table_queue')};now=[tuple(r) for r in c.execute('select * from raw_table_queue')]
        check('raw_queue_identity_and_fields',set(oldq)=={r[0] for r in now} and all(r[:6]==oldq[r[0]][:6] and r[7:]==oldq[r[0]][7:] for r in now))
        for r in c.execute('select f.*,v.component,v.conversion_factor from material_facts f join fact_components_v6 v using(fact_id)'):
            cells=json.loads(c.execute('select cells_json from transcribed_rows where table_key=? and row_ordinal=?',(r['table_key'],r['row_ordinal'])).fetchone()[0]);check('raw_'+str(r['fact_id']),cells[r['column_ordinal']]==r['raw_value']);check('number_'+str(r['fact_id']),numeric(r['raw_value'],r['component'])==r['value'])
        for t in ['material_facts','capacitance_observations','test_candidates','outcome_observations_v3','report_variants_v6','raw_table_queue']:check('no_auto_training_'+t,c.execute('select count(*) from '+t+' where training_eligible!=0 or training_eligible is null').fetchone()[0]==0)
        actual_tables=c.execute("select count(*) from reviewed_tables t left join extraction_units_v3 u using(table_key) where u.kind is null or u.kind in ('own_xml_table','own_SI_table','own_and_comparison_pdf_table','mixed_comparison_table')").fetchone()[0]
        check('24_explicit_reviews_for12samples_two_purposes',c.execute('select count(*) from purpose_reviews_v6 where eligible=1').fetchone()[0]==24)
        check('63_actual_tables_distinct_from55_raw_candidates',actual_tables==63)
        count=lambda t:c.execute('select count(*) from '+t).fetchone()[0]
        summary=dict(identity_catalogue_entries=480,raw_table_candidates=959,raw_table_rows=6121,cumulative_reviewed_source_publications=count('reviewed_sources'),cumulative_materials=count('materials'),cumulative_selected_material_cells=count('material_facts'),cumulative_numeric_material_facts=c.execute('select count(*) from material_facts where value is not null').fetchone()[0],new_materials=count('materials')-84,new_numeric_material_facts=c.execute('select count(*) from material_facts where value is not null').fetchone()[0]-791,reviewed_table_units=63,reviewed_evidence_units=count('reviewed_tables')+count('figure_protocol_reviews_v6'),raw_candidates_touched=959-c.execute("select count(*) from raw_table_queue where review_state='automatic_candidate_unreviewed'").fetchone()[0],raw_candidates_untouched=c.execute("select count(*) from raw_table_queue where review_state='automatic_candidate_unreviewed'").fetchone()[0],capacitance_records=count('capacitance_observations'),numeric_capacitance_values=c.execute('select count(*) from capacitance_observations where value is not null').fetchone()[0],unreported_capacitance_cells=2,cycling_candidates=count('test_candidates'),scientific_issues=count('scientific_issues'),historical_selected_fact_references=725,historical_fact_references_with_same_source_table_candidates=171,synthesis_materials=count('synthesis_stages_v3'),response_outcomes=count('outcome_observations_v3'),new_EIS_fitted_parameter_records=60,new_diffraction_peaks=count('diffraction_peaks_v6'),report_variants=count('report_variants_v6'),auxiliary_aqueous_3e_GCD_rows=103,auxiliary_aqueous_2e_GCD_rows=5,auxiliary_native_mineral_3e_GCD_rows=5,auxiliary_author_factor2_2e_GCD_rows=6,auxiliary_independent_DOI_groups=8,auxiliary_purpose_reviewed_input_rows=119,DES_purpose_reviewed_rows_per_target=12,DES_purpose_reviews=24,DES_independent_DOI_groups=1,new_training_admissions=0,formal_cycling_admissions=0,model_fits=0,all_literature_fully_utilized=False,scope_note='Own numeric cells include repeatedreports; EISresponses/peakdescriptors not counted as materialpredictors. DESreportedmean inputs have separatepurpose admission; no ordinaryaqueouscycling membership, no fit or externalvalidation. Originalfixed38 remain unresolved; currentcyclingv0.20 maintained.')
    exports={}
    with new_api(DB,digest) as new,old_api(PARENT,PARENT_SHA) as old:
        for profile in PROFILES:check('unchanged_aux_'+profile,new.auxiliary_feature_rows(profile)==old.auxiliary_feature_rows(profile))
        check('NWJPC25_sixvalues',[r['value'] for r in new.facts(doi=W,sample='NWJPC-2.5') if r['field_name']=='BET_surface_area_m2_g']==[2308])
        stage=new.synthesis(doi=W,sample='NWJPC-2.5')[0]['stages']
        check('sample25_inheritance_not_claimed_measured',all('inherited' in s['field_state'] for s in stage) and stage[0]['temperature_C'] is None and stage[1]['melamine_to_hydrochar_mass_ratio']==2.5)
        check('raw_precursor_not_carbonized',new.materials(doi=G,sample='raw_glycogen')[0]['material_stage']=='raw_glycogen_before_carbonization')
        nd=new.facts(doi=G,sample='GC_1000C_0.5h',field='XPS_N_at_pct')[0]
        check('ND_not_zero',nd['value'] is None and nd['raw_value']=='ND' and 'not_detected' in nd['review_status'])
        dash=new.facts(doi=G,sample='GC_750C_1h',field='XPS_P_at_pct')[0];check('dash_not_ND',dash['value'] is None and dash['raw_value']=='---' and 'dash' in dash['review_status'])
        check('Raman_competing_error_preserved',{r['value'] for r in new.facts(doi=G,sample='GC_1000C_1h',field='Raman_ID_IG_reported_uncertainty')}=={.004,.007})
        check('six_peaks_not_six_d002',len(new.diffraction_peaks())==6 and len(new.facts(doi=G,field='XRD_d002_nm'))==2)
        check('A_to_nm_explicit',math.isclose(new.facts(doi=G,sample='GC_1000C_5h',field='XRD_d002_nm')[0]['value'],.37,rel_tol=0,abs_tol=1e-12))
        check('si_body_variants_kept',any(r['value']==3.8 for r in new.report_variants('XRD_d002_A')))
        fixed=next(r for r in new.capacitances(doi=G) if r['observation_id']==G+'#own_body_p80#1#2')
        check('SSEcurrent_corrected_with_raw',fixed['current_A_g']==.1 and fixed['reported_current_raw_A_g']==.01 and fixed['value']==802)
        check('EIS60typed',len(new.eis_fits())==60)
        for item in new.eis_fits():
            r=item['record'];check('EIS_uncertainty_'+item['outcome_id'],numeric(r['raw_value'],'mean')==r['value'] and numeric(r['raw_value'],'uncertainty')==r['reported_uncertainty'])
        views={}
        for target in ['capacitance','retention']:
            rows=new.des_candidate_inputs(target);views[target]=dict(rows=len(rows),DOI_groups=len({r['source_group'] for r in rows}))
            check('DES12_'+target,len(rows)==12)
            check('one_DOI_no_independence_'+target,len({r['source_group'] for r in rows})==1 and all(r['purpose_reviewed_input_ready'] and not r['ordinary_aqueous_cycling_admitted'] and not r['training_authorized'] for r in rows))
            check('unit_source_weight_'+target,abs(sum(r['source_balanced_weight'] for r in rows)-1)<1e-12)
            check('molar_ratio_not_molarity_'+target,all(r['DES_ChCl_to_EG_molar_ratio']=='1:2' and r['electrolyte_concentration_mol_L'] is None for r in rows))
            check('no_fit_response_as_predictor_'+target,all(not any(k.startswith('EIS_') for k in r) for r in rows))
            for r in rows:
                check('finite_target_'+target+r['sample_name'],math.isfinite(r['target_value']))
                for k,v in r.items():
                    if k.endswith('_is_missing'):check('mask_'+target+r['sample_name']+k,v==(r[k.removesuffix('_is_missing')] is None))
            if target=='retention':check('common_protocol_binding_explicit_not_percycle_claim',all(r['cycle_voltage_lower_V']==0 and r['cycle_voltage_upper_V']==1 and not r['later_cycle_window_directly_shown'] and 'Table3' in r['cycle_window_review'] for r in rows))
            fields=[k for k in rows[0] if k not in ['material_evidence_states','material_evidence']];buf=io.StringIO(newline='');w=csv.DictWriter(buf,fieldnames=fields);w.writeheader();w.writerows([{k:r[k] for k in fields} for r in rows]);exports['DES_'+target+'_preparation.csv']=buf.getvalue()
        for target in ['capacitance','retention']:
            matrix=new.des_model_inputs(target);exports['DES_'+target+'_model_inputs.json']=json.dumps(matrix,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
            names=matrix['feature_names'];allrows=new.des_reported_inputs(target)
            check('matrix_shape_'+target,len(matrix['X'])==12 and all(len(x)==len(names) for x in matrix['X']))
            check('no_response_ID_or_uncertainty_in_X_'+target,set(names)==set(DES_PREDICTORS)|({'cycle_count','cycle_voltage_lower_V','cycle_voltage_upper_V'} if target=='retention' else set()) and not any('target' in k or 'uncertainty' in k or 'EIS' in k for k in names))
            check('source_isolation_across_targets_'+target,len(set(matrix['groups']))==1 and not matrix['external_source_fold_possible'] and not matrix['training_authorized'])
            check('matrix_missing_not_zero_'+target,all((v is None)==miss for x,masks in zip(matrix['X'],matrix['missing_mask']) for v,miss in zip(x,masks)))
            check('matrix_finite_when_reported_'+target,all(v is None or (isinstance(v,(int,float)) and math.isfinite(v)) for x in matrix['X'] for v in x))
            check('three_protocol_documents_with_hashes_'+target,all(len(r['protocol_evidence'])==3 and all(len(d['sha256'])==64 for d in r['protocol_evidence']) for r in allrows))
            check('source_qualified_facts_in_every_row_'+target,all(all(all(len(f['source_sha256'])==64 and f['locator'] for f in fs) for fs in r['material_evidence'].values()) for r in allrows))
        check('reported_mean100_plus_minus2_preserved',max(r['target_value'] for r in new.des_candidate_inputs('retention'))==100 and any(r['target_value']==100 and r['target_reported_uncertainty']==2 for r in new.des_candidate_inputs('retention')))
    check('API_readonly',sha(DB)==digest)
    report=dict(status='passed',checks=len(checks),check_names=sorted(checks),model_fits=0,scientific_goal_complete=False)
    preflight=dict(status='DES_report_purpose_inputs_reviewed_no_fit',views=views,aquatic_auxiliary_inputs_unchanged=119,formal_cycling_database_unchanged=protection['pinned_cycling_pointer'],limitations=['OnlyoneDESsource; no external-source validation fold.','0..1V window bound by owninitialGCD+sameTable3commonprotocol, not independentlyplotted everycycle.','EISresponses excluded frompretestpredictors; ±type retained asreported.'],model_fits=0)
    outputs={'summary.json':summary,'verification.json':report,'DES_input_preflight.json':preflight}
    for name,value in outputs.items():
        if write_reports:write(OUT/name,value)
        else:assert json.loads((OUT/name).read_text('utf8'))==value,'report_'+name
    for name,value in exports.items():
        if write_reports:
            with (OUT/name).open('w',encoding='utf8',newline='') as f:f.write(value)
        else:
            with (OUT/name).open('r',encoding='utf8',newline='') as f:assert f.read()==value,'csv_'+name
    if (OUT/'merge_manifest.json').exists():
        for p in json.loads((OUT/'merge_manifest.json').read_text('utf8'))['outputs']:assert sha(ROOT/p['path'])==p['sha256'],p['path']
    print(json.dumps(dict(status='passed',checks=report['checks'],summary=summary),ensure_ascii=False))

def seal():
    if (OUT/'merge_manifest.json').exists():raise FileExistsError('Never reseal.')
    assert (OUT/'README.md').exists();verify(False)
    files=sorted([p for p in OUT.rglob('*') if p.is_file()]+[Path(__file__).resolve(),ROOT/'data/literature_v6.py',ROOT/'data/literature_current.py'])
    write(OUT/'merge_manifest.json',dict(version='literature_pool_v6',parent_sha256=PARENT_SHA,scientific_goal_complete=False,model_fits=0,outputs=[dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p),bytes=p.stat().st_size) for p in files]))
    write(ROOT/'data/current_literature.json',dict(version='literature_pool_v6',directory=OUT.relative_to(ROOT).as_posix(),database_file=DB.name,sha256=sha(DB),api_module='data.literature_v6',scope='Remaining own SI, typed facts/uncertainty/variants and separately reviewed DES mean-target inputs; currentcyclingv0.20 unchanged.'))
if __name__=='__main__':
    if len(sys.argv)!=2 or sys.argv[1] not in ['build','prepare_reports','verify','seal']:raise SystemExit('build(oneuse),prepare_reports(unsealed),verify(readonly),seal(oneuse)')
    command=sys.argv[1]
    if command=='prepare_reports':
        if (OUT/'merge_manifest.json').exists():raise RuntimeError('Cannot regenerate sealed reports.')
        verify(True)
    elif command=='verify':verify(False)
    else:globals()[command]()
