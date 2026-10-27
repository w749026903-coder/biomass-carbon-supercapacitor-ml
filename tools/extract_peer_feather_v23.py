"""Source-bound append of own experiments and quarantined secondary compilations.

One-use preparation/build. Never fit a model or mutate a sealed release.
"""
from pathlib import Path
from contextlib import closing
import collections, json, re, sqlite3, sys, xml.etree.ElementTree as E
import pdfplumber
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tools'))
from extract_onion_composite_v8 import sha,write,ro,insert,mk
from extract_palm_kernel_v7 import xml_grid
from extract_source_series_v13 import clean
from extract_four_sources_v22 import numeric_details as previous_numeric_details
OUT=ROOT/'文献全量利用复核_20261028/批次23_同体系机器学习蜜瓜皮鹅羽与综述对账'
DB=OUT/'literature_material_pool_v23.sqlite'
PARENT=ROOT/'文献全量利用复核_20261027/批次22_林业多前驱体松木配方与参考体系/literature_material_pool_v22.sqlite'
PSHA='407161771aaefe2bd1539f545a36b1166d80ff145c569ceac3d3fa5ffff6a778'
FE='10.3390/molecules30010026';ML='10.1002/cplu.202500342'
ME='10.3390/molecules30153125';SA='10.1002/tcr.202600007'
KEYS={FE:'Feather23',ML:'ML23',ME:'Mech23',SA:'Satoyama23'}
CYCLE=ROOT/'循环稳定性数据库_v0.27_林业含灰双电极准入_20261028/cycling_v0_27.sqlite'
CSHA='9c5689c6b7806f64f3fbe51b469e23efff2fa508626e94287a792a9c7bdf555e'
NATIVE=ROOT/'全库复检与特征补提取_20261021/full_corpus_search_native.sqlite'

def numeric_details(raw):
    if str(raw).strip()=='--':return dict(raw_token=raw,value=None,value_kind='unreported_dash_not_zero')
    return previous_numeric_details(raw)

def number(raw):return numeric_details(raw)['value']

def curate():
    assert sha(PARENT)==PSHA and sha(CYCLE)==CSHA
    assert not DB.exists() and not (OUT/'curation_spec.json').exists() and not (OUT/'merge_manifest.json').exists()
    notes=json.loads((OUT/'source_review_notes.json').read_text('utf8'))
    spec={k:[] for k in ['sources','documents','tables','units','materials','facts','caps','responses','synthesis','decisions','feature_decisions','figures','candidates','annotations','identity_links','raw_dispositions','lineage','protocol_reviews','secondary_rows','peer_metrics','citation_links']}
    roots={};tables={};docs={}
    def doc(key,doi,path,role):
        p=ROOT/path;d=dict(key=key,doi=doi,path=path,sha256=sha(p),role=role)
        assert key not in docs;docs[key]=d;spec['documents'].append(d)
    with closing(ro(NATIVE)) as c:
        c.row_factory=sqlite3.Row
        for s in notes['sources']:
            doi=s['doi'];r=E.parse(ROOT/s['path']).getroot();roots[doi]=r
            assert sha(ROOT/s['path'])==s['sha256']
            assert {clean(x).lower() for x in r.findall('./front/article-meta/article-id') if x.get('pub-id-type')=='doi'}=={doi}
            years={int(x.text) for x in r.findall('./front/article-meta/pub-date/year')}
            y=max(years)
            typ={FE:'original_Cu_contaminated_and_zero_Cu_controls',ML:'peer_ML_secondary_compilation_with_own_overlap_pending_validation',ME:'review_secondary_only',SA:'PersonalAccount_secondary_and_prior_group_work'}[doi]
            spec['sources'].append(dict(s,year=y,classification=typ))
            doc(KEYS[doi],doi,s['path'],'primary_XML')
            raw={x['locator']:x['table_id'] for x in c.execute('select table_id,locator from raw_tables_v11 where source_sha256=?',(s['sha256'],))}
            for t in r.findall('.//table-wrap'):
                loc='XML table-wrap '+t.get('id')
                q=dict(doi=doi,id=t.get('id'),document=KEYS[doi],locator=loc,caption=clean(t.find('caption')),footnote=clean(t.find('table-wrap-foot')),grid=xml_grid(t),raw_table_id=raw[loc],kind='native_XML_own_or_secondary_roles_explicit')
                tables[(doi,q['id'])]=q;spec['tables'].append(q)
        inv=json.loads((OUT/'local_document_inventory.json').read_text('utf8'))
        for d in inv['documents']:doc(d['key'],ML if d['key'].startswith('ML') else FE,d['path'],'existing_own_main_PDF' if 'MainPDF' in d['key'] else 'existing_SI_PDF')
        for doi,pages in [(FE,{1:4,2:5,3:6,4:7,5:8,6:9,7:10,8:11}),(ML,{1:3,2:5,3:6,4:7,5:8,6:9,7:9,8:10,9:11})]:
            for f in roots[doi].findall('.//fig'):
                label=clean(f.find('label'));n=int(re.search(r'\d+',label)[0]);assert n in pages
                render=OUT/'evidence'/f'{KEYS[doi]}_MainPDF_p{pages[n]}.png';assert render.is_file()
                spec['figures'].append(dict(doi=doi,figure_number=n,printed_label=label,xml_id=f.get('id'),graphic_href=f.find('.//graphic').get('{http://www.w3.org/1999/xlink}href'),document=KEYS[doi]+'_MainPDF',PDF_page=pages[n],render_path=render.relative_to(ROOT).as_posix(),render_sha256=sha(render),caption=clean(f.find('caption')),scope_visually_inspected=True,full_waveform_extracted=False))
        # One physical Table S1 across seven pages, not seven independent tables.
        peer=json.loads((OUT/'peer_SI_S1_native_transcription.json').read_text('utf8'))
        for tid,page,rows in [('SI_TableS1',2,[peer['header']]+[x['cells']for x in peer['rows']]),('SI_TableS2',9,None)]:
            if rows is None:
                with pdfplumber.open(ROOT/docs['ML23_SI']['path']) as p:rows=p.pages[8].extract_tables()[0]
            rr=c.execute('select table_id,locator from raw_tables_v11 where source_sha256=? and locator like ?', (docs['ML23_SI']['sha256'],f'PDF p{page} %')).fetchall()
            assert len(rr)==1,(page,[dict(x)for x in rr])
            spec['tables'].append(dict(doi=ML,id=tid,document='ML23_SI',locator='PDF TableS1 pages2..8' if page==2 else 'PDF TableS2 page9',caption=tid,header=rows[0],rows=rows,raw_table_id=rr[0]['table_id'],kind='peer_secondary_compilation' if page==2 else 'peer_model_performance_not_experimental_materials'))
        # Review table rows are retrieval leads, never experiments attributed to the review DOI.
        for doi in [ME,SA]:
            refs={}
            for x in roots[doi].findall('.//ref'):
                label=clean(x.find('label')).strip('. ');links=[z.get('{http://www.w3.org/1999/xlink}href') for z in x.findall('.//ext-link') if z.get('ext-link-type')=='doi']
                links += [clean(z) for z in x.findall('.//pub-id') if z.get('pub-id-type')=='doi']
                refs[label]=dict(ref_id=x.get('id'),citation=clean(x),DOIs=sorted({v.lower().removeprefix('https://doi.org/').rstrip('.')for v in links if v}))
            for t in [x for x in spec['tables']if x['doi']==doi]:
                for i,row in enumerate(t['grid'][1:],2):
                    cells=[x['raw']for x in row];numbers=re.findall(r'\[(\d+(?:\s*,\s*\d+)*)\]', ' '.join(cells))
                    labels=[v.strip()for x in numbers for v in x.split(',')]
                    if doi==ME and t['id'].endswith('t001'):labels=['84']
                    links=[refs[x]for x in dict.fromkeys(labels)if x in refs]
                    rec=dict(row_id=KEYS[doi]+':'+t['id']+':'+str(i),curator_doi=doi,table_id=t['id'],row_ordinal=i,cells=cells,citations=links,cited_DOIs=sorted({d for q in links for d in q['DOIs']}),source_sha256=docs[KEYS[doi]]['sha256'],training_eligible=False,primary_protocol_verified=False,scope='secondary_retrieval_or_context_not_new_own_experiment')
                    spec['secondary_rows'].append(rec)
        for r in peer['rows']:spec['secondary_rows'].append(dict(r,row_id='ML23:S1:'+str(r['row_number']),table_id='SI_TableS1',row_ordinal=r['row_number']+1,cited_DOIs=[r['cited_doi']],scope='peer_secondary_compilation_not_qualified_primary_sample'))
        for i,row in enumerate(spec['tables'][-1]['rows'][1:],2):
            spec['peer_metrics'].append(dict(model=row[0].replace('\n',' '),RMSE=float(row[1]),MAE=float(row[2]),R2=float(row[3]),raw_cells=row,curator_doi=ML,table_id='SI_TableS2',row_ordinal=i,physical_unit_verified=False,target='specific_capacitance_scaled_not_retention',not_our_model_score=True))
    def unit(doi,id,header,rows,loc,document=None):
        spec['units'].append(dict(doi=doi,id=id,header=header,rows=[[str(v)for v in rr]for rr in rows],locator=loc,document=document or KEYS[doi],kind='own_bound_prose_or_printed_figure_values'));return id
    def reg(doi,s,stage,feed):spec['materials'].append(dict(doi=doi,sample=s,stage=stage,feedstock=feed))
    def fact(doi,s,id,row,col,f,un,met,status='own_stage_method_qualified'):
        spec['facts'].append(dict(doi=doi,sample=s,id=id,row=row,col=col,field=f,unit=un,method=met,status=status))
    def resp(doi,s,id,row,col,f,un,**conds):spec['responses'].append(dict(doi=doi,sample=s,id=id,row=row,col=col,metric=f,unit=un,conditions=conds))
    def cap(doi,s,id,row,col,j,purpose=None,**conds):spec['caps'].append(dict(doi=doi,sample=s,id=id,row=row,col=col,j=j,purpose=purpose,method='GCD',scan=None,conditions=conds))
    def issue(doi,id,evidence,decision):spec['decisions'].append(dict(id='V23_'+id,doi=doi,evidence=evidence,decision=decision,not_author_erratum=True))
    raw=['Pine Sawdust','Goose Feather'];hyd=['PS-0','PS-25','PS-50','M-0','M-25','M-50']
    final=['PS-3-0','PS-3-25','PS-3-50','M-3-0','M-2-25','M-3-25','M-4-25','M-3-50']
    for s in raw+hyd+final:
        stage='raw_biomass'if s in raw else 'hydrochar_before_KOH'if s in hyd else 'final_carbon_zero_Cu_control'if s in ['PS-3-0','M-3-0']else 'final_Cu_Cu2O_carbon_composite'
        feed='pine_sawdust'if s.startswith('PS')or s=='Pine Sawdust'else'goose_feather'if s=='Goose Feather'else'pine_sawdust_and_goose_feather'
        reg(FE,s,stage,feed)
    # Bulk CHN and author O-by-difference are not XPS atomic composition.
    names=raw+hyd+final
    for row,s in enumerate(names,2):
        tid='molecules-30-00026-t002'
        resp(FE,s,tid,row,1,'author_stage_mass_yield_pct','%',yield_denominator_unreported=True)
        for col,f in [(2,'bulk_EA_C_reported_pct'),(3,'bulk_EA_H_reported_pct'),(4,'bulk_EA_N_reported_pct'),(5,'author_O_by_100_minus_CHN_proxy_pct'),(6,'author_atomic_O_C_ratio'),(7,'author_atomic_H_C_ratio')]:
            fact(FE,s,tid,row,col,f,'ratio'if col>5 else'%_as_reported','ElementarVarioELcubeCHN; O=100-CHN includes unquantifiedCu/ash. Percentheaderdoesnotexplicitlystatewt; atomicratioscompatiblewithmassCHN, rawmethodkept; notXPS.')
        if s in final:
            z=int(s.split('-')[1]);cu=int(s.split('-')[2]);parent=('PS-'if s.startswith('PS')else'M-')+str(cu)
            spec['lineage'].append(dict(doi=FE,parent=parent,child=s,kind='own_P14_legal_factor_levels_and_raw_table_alias_kept'))
            stages=[dict(stage='hydrothermal_carbonization',temperature_C=240,duration_min=120,water_mL=150,reactor_mL=250,pine_sawdust_g=7.5 if s.startswith('M')else None,goose_feather_g=7.5 if s.startswith('M')else None,Cu_feed_mg_per_g_pine_sawdust=cu,Cu_feed_not_final_content=True),dict(stage='chemical_activation',temperature_C=700,duration_h=1,heating_rate_C_min=10,atmosphere='N2',flow_mL_min=25,activator='KOH',carbon_to_activator_mass_ratio=[1,z]),dict(stage='wash',HCl_M=.1,water_to_neutral=True)]
            spec['synthesis'].append(dict(doi=FE,sample=s,document=KEYS[FE],locator='MainP13..14; 500rpm6h Cuimpregnation,80C12h/80mesh preparation; finaldry80C,3statedrepeatsnot3reportedmeasurements',stages=stages))
    samples=['PS-25','M-25','PS-3-0','PS-3-25','M-3-0','M-2-25','M-3-25','M-4-25','M-3-50']
    for row,s in enumerate(samples,2):
        tid='molecules-30-00026-t001'
        for col,f,un,met in [(1,'BET_surface_area_m2_g','m2/g','N2multi-pointBET; sourceP5relativepressure.001-.05'),(2,'total_pore_volume_cm3_g','cm3/g','N2P/P0.99'),(3,'tplot_micropore_volume_cm3_g','cm3/g','Author t-plot micro'),(4,'author_micropore_volume_fraction_pct','%','AuthorVmicro/Vtotal percent'),(5,'BJH_mesopore_volume_cm3_g','cm3/g','AuthorBJHmesopore')]:fact(FE,s,tid,row,col,f,un,met)
        purpose='reported_aqueous_3e_GCD_capacitance'if s in ['PS-3-0','M-3-0']else'feather_Cu_composite_3e_GCD'if s in final and s!='M-3-25'else None
        cap(FE,s,tid,row,6,None if s in hyd else 1,purpose,system='3E',electrolyte='KOH',concentration_mol_L=6,voltage_lower_V=-1,voltage_upper_V=0,reference_electrode='HgO/Hg',counter_electrode='Pt',binder='PTFE',capacitance_basis='author_working_active_mass_I_dt_m_dV',physical_test_group='doi:'+FE+'#'+s+'#3EGCD1',material_scope='zero_Cu_control'if s in ['PS-3-0','M-3-0']else'Cu_Cu2O_composite_or_hydrochar',cross_source_comparable=purpose=='reported_aqueous_3e_GCD_capacitance',unsupported_hydrochar_current_binding=s in hyd)
    u=unit(FE,'Raman_printed',['sample','ID_IG'],[['PS-3-0',.87],['M-3-0',.95],['M-3-25',1.02]],'ActualFig3c printedratios/MainP8; intensitynotassumedarea', 'Feather23_MainPDF')
    for row,s in enumerate(['PS-3-0','M-3-0','M-3-25'],1):fact(FE,s,u,row,1,'Raman_ID_IG','ratio','OwnprintedFig3c intensityratio')
    u=unit(FE,'M325_competing_C_and_device',['sample','C','j','system'],[['M-3-25',581.74,1,'3E'],['M-3-25',630.6,1,'2E']],'MainP11variant581.74vsTable1/3 587.14; MainP12Fig7device630.6')
    for row,system in [(1,'3E'),(2,'2E')]:cap(FE,'M-3-25',u,row,1,1,'feather_Cu_composite_2e_author_single_electrode'if row==2 else None,system=system,electrolyte='KOH',concentration_mol_L=6,voltage_lower_V=0 if row==2 else-1,voltage_upper_V=1.3 if row==2 else 0,binder='PTFE',capacitance_basis='author_single_electrode_Eq2_I_dt_m_dV_mass_identity_unresolved'if row==2 else'author_working_active_mass_I_dt_m_dV',physical_test_group='doi:'+FE+'#M-3-25#'+system+'GCD1',cross_source_comparable=False)
    cap(FE,'M-3-25','molecules-30-00026-t003',2,2,1,None,system='3E',electrolyte='KOH',concentration_mol_L=6,capacitance_basis='author_working_active_mass_I_dt_m_dV',physical_test_group='doi:'+FE+'#M-3-25#3EGCD1',cross_source_comparable=False)
    u=unit(FE,'M325_device_energy_EIS',['sample','value','metric','unit'],[['M-3-25',42.16,'energy','Wh/kg'],['M-3-25',398.17,'power','W/kg'],['M-3-25',12.75,'energy','Wh/kg'],['M-3-25',6463.30,'power','W/kg'],['M-3-25',.805,'Rs','U_as_printed_ohm_axes'],['M-3-25',.077,'Rct','U_as_printed_ohm_axes']],'MainP11/12; EISnotintrinsicconductivity; deviceenergytwopairs')
    for i,(f,un)in enumerate([('device_energy','Wh/kg'),('device_power','W/kg'),('device_energy','Wh/kg'),('device_power','W/kg'),('EIS_Rs','U_as_printed_ohm_axes'),('EIS_Rct','U_as_printed_ohm_axes')],1):resp(FE,'M-3-25',u,i,1,f,un,not_pretest_predictor=True,pair_index=1 if i<3 else 2 if i<5 else None)
    reg(ML,'HDP-AC','final_H3PO4_biomass_carbon_prior_sample_overlap_pending','honeydew_melon_peel')
    u=unit(ML,'HDP_own_reports',['sample','BET','3E_C','2E_C','Raman_value'],[['HDP-AC',33,485,611,1.05]],'MainP43BET,MainP6/45ownC,MainP35RamanID/IG vsactualFig6bIG/ID')
    fact(ML,'HDP-AC',u,1,1,'BET_surface_area_m2_g','m2/g','OwnMainP43, notunnameddosagerange')
    fact(ML,'HDP-AC',u,1,4,'Raman_ID_IG','ratio','MainP35bodyID/IG',status='conflict_reciprocal_direction_with_printed_IG_ID')
    fact(ML,'HDP-AC',u,1,4,'Raman_IG_ID','ratio','ActualFig6bprintedIG/ID',status='conflict_reciprocal_direction_with_body_ID_IG')
    for col,system,j in [(2,'3E',None),(3,'2E',1.3)]:cap(ML,'HDP-AC',u,1,col,j,None,system=system,electrolyte='H2SO4',concentration_mol_L=1,voltage_lower_V=0 if system=='2E'else None,voltage_upper_V=1.1 if system=='2E'else None,binder='PVDF',capacitance_basis='author_I_dt_m_dV_mass_identity_unresolved',physical_test_group='doi:'+ML+'#HDP-AC#'+system,source_overlap_pending=True,cross_source_comparable=False,current_at_3e485_not_explicitly_bound=True)
    spec['synthesis'].append(dict(doi=ML,sample='HDP-AC',document=KEYS[ML],locator='OwnMainmethods; sample/prior overlap stillpending',stages=[dict(stage='precarbonization',temperature_C=300,duration_h=4,heating_rate_C_min=2.5,atmosphere=None),dict(stage='chemical_activation',temperature_C=500,duration_h=1,heating_rate_C_min=2.5,activator='H3PO4',carbon_to_activator_mass_ratio=[1,4],atmosphere=None)]))
    for doi,s,eid in [(FE,'M-3-25','legacy:SRC126_CY01'),(ML,'HDP-AC','legacy:R001_CY01')]:spec['identity_links'].append(dict(doi=doi,sample=s,existing_endpoint_id=eid,not_new_cycling_endpoint=True,core_endpoint_unchanged=True,evidence='Ownbodymatchesexistingendpoint; originalscope/overlapholdsretained, no cyclingadmission'))
    issue(FE,'Cu_controls_and_stage_aliases',dict(raw_PS_table2=['PS-0-3','PS-25-3','PS-50-3'],canonical=['PS-3-0','PS-3-25','PS-3-50'],basis='P14Z=2/3/4 Y=0/25/50 uniquelegalfactorlevels; literalrawtablecellsretained',Cu_free=['PS-3-0','M-3-0'],Cu_phases='XRD/Cu2p Cu/Cu2O and redox'),'OnlytwoCu-freecontrols ordinary3EGCD; Cucompositeseparate. No entire-paper exclusion; no old cyclingunfreeze.')
    issue(FE,'M325_capacity_competition_and_O_proxy',dict(capacitance_F_g=[581.74,587.14],BET_malformed_prose='25.1.08',BET_table=2501.08,O_method='100-CHN includesunquantifiedCu/ash',stock_8mg_not_measured_coating_mass=True),'FreezeM3253E1Ag target; no majority/performance choice. KeepEAseparatefromXPS, OproxyseparatefrommeasuredO, no mass_loading8 assumption.')
    issue(ML,'prior_overlap_and_protocol',dict(prior_DOI='10.1002/asia.202400622',existing_status='sample_overlap_pending',printed_2E_axis='V vs Hg/HgO',body_device_window=[0,1.1],rounding_body_V=1),'RetainexistingR001hold; BET33alonecannotunfreeze; massconventionnotinferredfromenergy; Raman directionsdisputed, current485unknown, EDSqualitativenotXPS.')
    issue(ML,'peer_ML_scaling_split_and_duplicates',dict(raw_rows=166,cited_DOI_strings=41,exact_duplicate_rows=[89,164],feature_collision_rows=[32,33],own_measured_C=611,predictions=[229,208],fitcsvm_documentation='https://www.mathworks.com/help/stats/fitcsvm.html',fitrsvm_documentation='https://www.mathworks.com/help/stats/fitrsvm.html'),'Noverifiedauthorcode; prosenamesclassifierforregressioninconsistencyonly. No explicitDOIheldoutproof, no actualleakageclaim. ScaledMAEnotF/gorretentionpp. All166secondaryrowshelduntilprimaryprotocolsverified; duplicatesretained.')
    issue(ME,'secondary_unit_typo',dict(Table3_header='Specific Surface Area (cm2 g−1)',Table2_header='SSA,m2 g−1'),'Keep review rawheader; do not quietlyconvert primarySSA or assignreviewtablesasnewownexperiments. Follow cited originalDOI.')
    for doi in KEYS:
        spec['protocol_reviews'].append(dict(doi=doi,scope=next(s['classification']for s in spec['sources']if s['doi']==doi),full_body_paragraphs_read=next(s['body_paragraphs']for s in spec['sources']if s['doi']==doi),native_main_tables_read=True,remaining='Residualwaveforms/plotmarkers and primarycitations; all sourceextraction remains partial.',no_model_fit=True))
    write(OUT/'curation_spec.json',spec)
    print(json.dumps({k:len(v)for k,v in spec.items()}))

def add_secondary(c,spec):
    c.executescript('create table secondary_rows_v23(row_id text primary key,curator_doi text references reviewed_sources,table_key text references reviewed_tables,row_ordinal integer,record_json text,training_eligible integer check(training_eligible=0));create table peer_model_metrics_v23(model text primary key,record_json text);create table peer_dataset_audit_v23(curator_doi text primary key references reviewed_sources,record_json text);')
    for r in spec['secondary_rows']:
        insert(c,'secondary_rows_v23',dict(row_id=r['row_id'],curator_doi=r['curator_doi'],table_key=r['curator_doi']+'#'+r['table_id'],row_ordinal=r['row_ordinal'],record_json=json.dumps(r,ensure_ascii=False),training_eligible=0))
    for r in spec['peer_metrics']:insert(c,'peer_model_metrics_v23',dict(model=r['model'],record_json=json.dumps(r,ensure_ascii=False)))
    audit=json.loads((OUT/'peer_dataset_quality_audit.json').read_text('utf8'))
    insert(c,'peer_dataset_audit_v23',dict(curator_doi=ML,record_json=json.dumps(audit,ensure_ascii=False)))
    relation=dict(isolation_group='priorwork:10.1002/asia.202400622|10.1002/cplu.202500342',status='sample_overlap_pending',basis='ML main P6 and reference17 cite prior own honeydew validation; old cycling relationship retained. Same-family quarantine is precaution, not proof of duplicate experiments.',not_new_cycling_decision=True)
    insert(c,'source_relations_v11',dict(doi=ML,related_doi='10.1002/asia.202400622',record_json=json.dumps(relation)))
    c.commit()

def build():
    assert sha(PARENT)==PSHA and not DB.exists()and not(OUT/'merge_manifest.json').exists()
    spec=json.loads((OUT/'curation_spec.json').read_text('utf8'));docs={d['key']:d for d in spec['documents']}
    with closing(ro(PARENT))as parent,closing(sqlite3.connect(DB))as c:
        parent.backup(c);c.row_factory=sqlite3.Row;c.execute('pragma foreign_keys=on')
        c.executescript('''create table source_reviews_v23(doi text primary key references reviewed_sources,record_json text);create table cell_extractions_v23(kind text,record_id text,table_key text references reviewed_tables,row_ordinal integer,column_ordinal integer,primary key(kind,record_id));create table decisions_v23(decision_id text primary key,doi text references reviewed_sources,record_json text);create table material_feature_decisions_v23(material_key text references materials,field_name text,record_json text,primary key(material_key,field_name));create table purpose_reviews_v23(observation_id text primary key references capacitance_observations,purpose text,eligible integer,record_json text);create table figure_scope_reviews_v23(doi text references reviewed_sources,figure_number integer,document_key text references source_documents,record_json text,primary key(doi,figure_number));create table annotations_v23(annotation_id text primary key,doi text references reviewed_sources,document_key text references source_documents,record_json text);create table cycle_identity_links_v23(link_id text primary key,record_json text);''')
        for s in spec['sources']:insert(c,'reviewed_sources',dict(doi=s['doi'],path=s['path'],sha256=s['sha256'],title=s['title'],stage='Four source roles: own controls/composites, overlap-pending honeydew, secondary reviews and peer compilation; partial extraction'))
        for d in docs.values():assert sha(ROOT/d['path'])==d['sha256'];insert(c,'source_documents',dict(document_key=d['key'],doi=d['doi'],path=d['path'],sha256=d['sha256'],role=d['role']))
        for t in spec['tables']+spec['units']:
            key=t['doi']+'#'+t['id'];rows=[[v['raw']for v in r]for r in t['grid']]if'grid'in t else t['rows'];insert(c,'reviewed_tables',dict(table_key=key,doi=t['doi'],xml_id=t['id'],caption=t.get('caption',t['id']),header_json=json.dumps(rows[0]if'grid'in t else t['header']),footnote=t.get('footnote','Own bounded transcription; stages/repeats/foreign comparisons kept distinct'),source_raw_table_id=t.get('raw_table_id')));insert(c,'table_source_links',dict(table_key=key,document_key=t['document'],locator=t['locator']));insert(c,'extraction_units_v3',dict(table_key=key,kind=t['kind'],scope='Own explicitly bound cells only; foreign rows retained as context, never admitted'))
            for i,row in enumerate(rows,1):insert(c,'transcribed_rows',dict(table_key=key,row_ordinal=i,cells_json=json.dumps(row,ensure_ascii=False)));insert(c,'transcription_origins_v7',dict(table_key=key,row_ordinal=i,origin_json=json.dumps(t['grid'][i-1]if'grid'in t else dict(document=t['document'],locator=t['locator'],row=i),ensure_ascii=False)))
            if t.get('raw_table_id'):
                assert c.execute('select review_state from raw_table_queue where table_id=?',(t['raw_table_id'],)).fetchone()[0]=='automatic_candidate_unreviewed'
                c.execute('update raw_table_queue set review_state=?where table_id=?',('v23_own_cells_methods_stage_and_conflicts_reviewed',t['raw_table_id']))
        for r in spec['materials']:
            insert(c,'materials',dict(material_key=mk(r['doi'],r['sample']),doi=r['doi'],sample_name=r['sample'],material_stage=r['stage']))
            insert(c,'material_scopes_v8',dict(material_key=mk(r['doi'],r['sample']),scope_json=json.dumps(dict(origin_class=r['stage'],feedstock=r['feedstock'],stage=r['stage'],not_assumed_pure_carbon=True,same_source_not_independent=True))))
        def cell(r):
            key=r['doi']+'#'+r['id'];raw=json.loads(c.execute('select cells_json from transcribed_rows where table_key=?and row_ordinal=?',(key,r['row'])).fetchone()[0])[r['col']];return key,raw,number(raw)
        def receipt(kind,rid,r,key):insert(c,'cell_extractions_v23',dict(kind=kind,record_id=str(rid),table_key=key,row_ordinal=r['row'],column_ordinal=r['col']))
        for r in spec['facts']:
            key,raw,value=cell(r);doc=c.execute('select document_key from table_source_links where table_key=?',(key,)).fetchone()[0];q=insert(c,'material_facts',dict(material_key=mk(r['doi'],r['sample']),field_name=r['field'],value=value,raw_value=raw,unit=r['unit'],method=r['method'],table_key=key,row_ordinal=r['row'],column_ordinal=r['col'],source_sha256=docs[doc]['sha256'],review_status=r['status'],training_eligible=0));receipt('fact',q.lastrowid,r,key)
        for r in spec['caps']:
            key,raw,value=cell(r);rid=key+'#'+str(r['row'])+'#'+str(r['col']);cond=dict(extraction_batch='v23',current_mass_basis='author_reported_unknown_not_inferred',repeat_reports_not_independent=True);cond.update(r['conditions'])
            insert(c,'capacitance_observations',dict(observation_id=rid,material_key=mk(r['doi'],r['sample']),table_key=key,row_ordinal=r['row'],column_ordinal=r['col'],value=value,raw_value=raw,unit='F/g',method=r['method'],system=cond['system'],electrolyte=cond['electrolyte'],concentration_mol_L=cond['concentration_mol_L'],current_A_g=r['j'],scan_rate_mV_s=r['scan'],conditions_json=json.dumps(cond,ensure_ascii=False),status='own_reported'if r['purpose']else'own_repeat_or_competing_report',source_group='doi:'+r['doi'],training_eligible=0));receipt('capacitance',rid,r,key)
            if r['purpose']:
                reason='Own bound fresh method-specific report; explicit target/normalization/material scope, optional missing fields masked; source-specific ambiguous C/Cg never mixed into unified targets'
                insert(c,'purpose_reviews_v23',dict(observation_id=rid,purpose=r['purpose'],eligible=1,record_json=json.dumps(dict(reason=reason,purpose_input_ready=True,cyclic_retention_training_admitted=False,training_authorized=False))))
                if r['purpose']=='reported_aqueous_3e_GCD_capacitance':insert(c,'auxiliary_gcd_reviews_v3',dict(observation_id=rid,purpose=r['purpose'],eligible=1,reason=reason,review_basis='Own specific results/actual printed plot and matched own protocol, variants retained; no performance-based selection'))
        for r in spec['responses']:
            key,raw,value=cell(r);rid=key+'#'+str(r['row'])+'#'+str(r['col']);insert(c,'outcome_observations_v3',dict(outcome_id=rid,material_key=mk(r['doi'],r['sample']),table_key=key,record_json=json.dumps(dict(source_group='doi:'+r['doi'],extraction_batch='v23',metric=r['metric'],value=value,raw_value=raw,unit=r['unit'],**(dict(feature_role='test_or_process_response_not_pretest_predictor')|r['conditions'])),ensure_ascii=False),training_eligible=0));receipt('response',rid,r,key)
        for r in spec['synthesis']:insert(c,'synthesis_stages_v3',dict(material_key=mk(r['doi'],r['sample']),document_key=r['document'],locator=r['locator'],stages_json=json.dumps(r['stages'],ensure_ascii=False)))
        for r in spec['feature_decisions']:insert(c,'material_feature_decisions_v23',dict(material_key=mk(r['doi'],r['sample']),field_name=r['field'],record_json=json.dumps(r,ensure_ascii=False)))
        for r in spec['decisions']:insert(c,'decisions_v23',dict(decision_id=r['id'],doi=r['doi'],record_json=json.dumps(r,ensure_ascii=False)));insert(c,'scientific_issues',dict(issue_id=r['id'],doi=r['doi'],sample_name=None,issue_json=json.dumps(dict(kind=r['id'],action=r['decision']),ensure_ascii=False)))
        for r in spec['figures']:insert(c,'figure_scope_reviews_v23',dict(doi=r['doi'],figure_number=r['figure_number'],document_key=r['document'],record_json=json.dumps(r,ensure_ascii=False)))
        for r in spec['annotations']:insert(c,'annotations_v23',dict(annotation_id=r['id'],doi=r['doi'],document_key=r['document'],record_json=json.dumps(r,ensure_ascii=False)))
        for r in spec['identity_links']:insert(c,'cycle_identity_links_v23',dict(link_id='LP22_'+r['existing_endpoint_id'],record_json=json.dumps(r,ensure_ascii=False)))
        sources={r['doi']:r for r in spec['sources']}
        for r in spec['candidates']:insert(c,'test_candidates',dict(candidate_id=r['candidate_id'],material_key=mk(r['doi'],r['sample']),record_json=json.dumps(dict(r['record'],source_group='doi:'+r['doi'],source_year=sources[r['doi']]['year'],evidence_source_path=sources[r['doi']]['path'],source_sha256=sources[r['doi']]['sha256'],current_mass_basis='author_reported_unknown_not_inferred',baseline_cycle=None,baseline_reference='author_reference_not_assumed_cycle1'),ensure_ascii=False),training_eligible=0))
        for s in spec['sources']:
            review=dict(source_year=s['year'],classification=s['classification'],scope='All native main tables and body; own/secondary roles, 17 main figure scopes and two local SI reviewed',remaining='Continuous spectra/isotherms/CV/GCD/EIS, untranscribed rate markers, unresolved protocols/identities; not full-source extraction.',full_source_review_complete=False)
            insert(c,'source_scope_decisions',dict(doi=s['doi'],scope=review['scope'],reason=review['remaining'],evidence_json=json.dumps(review,ensure_ascii=False),full_source_review_complete=0));insert(c,'source_reviews_v23',dict(doi=s['doi'],record_json=json.dumps(review,ensure_ascii=False)))
        c.executescript('create table raw_candidate_dispositions_v23(table_id text primary key references raw_table_queue,record_json text);create table numeric_details_v23(fact_id integer primary key references material_facts,record_json text);create table material_lineage_v23(lineage_id integer primary key,parent_key text references materials,child_key text references materials,record_json text);')
        for r in spec['raw_dispositions']:
            c.execute('update raw_table_queue set review_state=?where table_id=?',(r['disposition'],r['table_id']));insert(c,'raw_candidate_dispositions_v23',dict(table_id=r['table_id'],record_json=json.dumps(r,ensure_ascii=False)))
        for r in c.execute('select f.fact_id,f.raw_value,f.method from material_facts f join cell_extractions_v23 x on x.record_id=cast(f.fact_id as text)and x.kind="fact"').fetchall():
            nd=numeric_details(r['raw_value'])
            if 'mean±SD'in r['method']:nd['uncertainty_kind']='author_mean_and_SD'
            insert(c,'numeric_details_v23',dict(fact_id=r['fact_id'],record_json=json.dumps(nd,ensure_ascii=False)))
        for r in spec['lineage']:insert(c,'material_lineage_v23',dict(parent_key=mk(r['doi'],r['parent']),child_key=mk(r['doi'],r['child']),record_json=json.dumps(r,ensure_ascii=False)))
        c.execute('create table protocol_reviews_v23(doi text primary key references reviewed_sources,record_json text)')
        for r in spec['protocol_reviews']:insert(c,'protocol_reviews_v23',dict(doi=r['doi'],record_json=json.dumps(r,ensure_ascii=False)))
        c.commit()
        add_secondary(c,spec)
    protected={ROOT/d['path']for d in docs.values()}|{PARENT,CYCLE,NATIVE}
    write(OUT/'protected_inputs.json',dict(files=[dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p),bytes=p.stat().st_size)for p in sorted(protected)]))
    print('Built unsealed v23; no original cycling modification or model fitting')

if __name__=='__main__':
    if len(sys.argv)!=2 or sys.argv[1]not in ['curate','build']:raise SystemExit('One-use curate/build, only before sealing')
    globals()[sys.argv[1]]()
