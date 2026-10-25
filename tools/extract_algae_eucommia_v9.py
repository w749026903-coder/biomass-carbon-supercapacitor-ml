"""Append native, own multi-sample data; preserve contradictory reports and old releases."""
from pathlib import Path
from contextlib import closing
import hashlib,json,re,sqlite3,sys,xml.etree.ElementTree as E
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tools'))
from extract_palm_kernel_v7 import xml_grid
from extract_onion_composite_v8 import sha,ro,write,insert,mk,text
OUT=ROOT/'文献全量利用复核_20261026/批次09_藻类与杜仲木系统系列';DB=OUT/'literature_material_pool_v9.sqlite'
PARENT=ROOT/'文献全量利用复核_20261026/批次08_洋葱壳与生物炭复合/literature_material_pool_v8.sqlite'
PARENT_SHA='ab78ccc9b9ce1d802f44705a7240af590c2b9b95047f00f912c2c8d87082aa62'
A='10.3390/molecules31132329';W='10.3390/polym15030663';R='10.3390/nano16090524';C='10.3390/molecules31172997'
BASE=ROOT/'同体系文献补充_第二批_20261017/定向扩搜40至60篇_20261017/sources'
SOURCES=[('Algae',A,BASE/'OA001/main.xml','da88f13708ab3545567ea0db19692ce706ce27ef6bfe7a998e8b07ef77230a2e'),('Eucommia',W,BASE/'OA025/main.xml','f44d758d98305ed742e1d13c5bce1b9986a647b5a2d8a22185a3c0b2cbe15095'),('Review',R,ROOT/'三电极端点扩充_20261018/new_sources/PMC13165098/main.xml','6aa9d364f7ab204480182500199950864f6b4c960f78de8c321c9e13e596fd07'),('Coal',C,ROOT/'三电极端点扩充_20261018/new_sources/PMC13567573/main.xml','00f2cd954e202cb9142daefb6370bcd8ea8f0346f56eda1acdb71cab7d3acc64')]
SI=BASE/'OA025/polymers-2180113-supplementary.pdf'
FIVE=['AC-850','AHPC-700','AHPC-800','AHPC-850','AHPC-900']
OPT=['AHPC-700','AHPC-800','AHPC-850','AHPC-900','AHPC-850-R1','AHPC-850-R2','AHPC-850','AHPC-850-R4','AHPC-850-t0.5','AHPC-850','AHPC-850-t2.5']

def number(raw,mode='decimal'):
    if mode=='wt_suffix':raw=raw.removesuffix(' wt.%')
    if mode=='pct':raw=raw.removesuffix('%')
    if mode=='retained':raw=raw.removeprefix('retained ').removesuffix('%')
    if mode=='scientific':
        m=re.fullmatch(r'([\d.]+)\s*×\s*10([−+\-]?\d+)',raw);assert m,raw
        return float(m[1])*10**int(m[2].replace('−','-'))
    assert re.fullmatch(r'\d+(?:\.\d+)?',raw),raw
    return float(raw)

def curated_units():
    def unit(doc,doi,id,kind,locator,head,rows):return dict(document=doc,doi=doi,id=id,kind=kind,locator=locator,header=head,rows=rows)
    names=['EC-10%','EC-25%','EC-40%','EC-55%','EC-1:2','EC-1:3','EC-1:4','EC-1:5','EC-2h','EC-4h','EC-6h','EC-8h','EC-350','EC-400','EC-450','EC-500']
    values=['153.7 148.0 134.9 112.8 73.4%','194.6 181.1 166.4 148.5 76.3%','178.4 169.3 145.5 135.0 75.7%','171.1 157.9 144.6 134.1 78.4%','148.3 125.2 109.9 101.3 68.3%','177.5 167.0 150.1 135.4 76.2%','194.6 181.1 166.4 139.9 76.3%','171.4 160.6 140.0 126.0 73.5%','194.6 181.1 166.4 139.9 76.3%','226.7 211.4 185.3 177.3 78.2%','257.8 247.5 220.2 208.7 81.0%','171.7 161.3 155.4 141.3 82.3%','186.5 171.0 164.4 147.5 79.1%','257.8 247.5 220.2 208.7 81.0%','238.2 227.7 210.0 198.7 83.4%','210.0 194.3 185.5 171.6 81.7%']
    return [
      unit('Eucommia_SI',W,'SI_TableS1','own_SI_table','PDF p4 TableS1, visually verified header and all16rows',['sample','C_0.2Ag','C_0.5Ag','C_0.8Ag','C_1.2Ag','rate_retention_pct'],[[n]+v.split() for n,v in zip(names,values)]),
      unit('Eucommia_SI',W,'SI_TableS2','own_and_comparison_pdf_table','PDF p5 TableS2; foreign9rows separated, ownfinalrow method/current conflict retained',['precursor','activator','activation_C','BET','Vtotal','capacitance','characterization_A_g','cycling'],[['Soya Beans','KOH','700','1208','-','149','0.5','89.3% in5000'],['Binata','KOH','852','2273','1.19','373','0.5','94.6% in10000'],['Tree bark','KOH','800','1018','0.67','191','1','100% in5000'],['Brussel','KOH','900','2267','1.32','255','0.5','99.55% in5000'],['Rotten carrot','ZnCl2','700','1253','0.95','137','1','-'],['Cottonseed meal','K2CO3','800','2361','1.41','313.4','0.1','86.4% in20000'],['Tamarindus indica Fruit Shell','H3PO4','900','846','0.556','287','1','92.5% in5000'],['Baobab shell','H3PO4','800','911','0.47','355','1','99.7% in5000'],['Olive residue','H3PO4','840','1390','0.61','150','0.25','91% in12500'],['EUO (EC-400)','H3PO4','400','2033.87','1.11','252','0.2','91.4% in10000']]),
      unit('Algae_Fig3',A,'Fig3_Raman_XPS','own_figure_label','OriginalFig3d/e printed ratios and element bars, conflicts withTables3/4',['sample','ID_IG','XPS_C_at_pct','XPS_N_at_pct','XPS_O_at_pct','XPS_S_at_pct'],[[s]+r.split() for s,r in zip(FIVE,['1.22 87.1 6.3 6.2 0.4','1.15 85.3 7.6 6.5 0.6','1.06 86.4 7.8 5.4 0.4','1.01 87.6 8.3 4.0 0.1','1.09 86.8 7.2 5.7 0.3'])]),
      unit('Algae_Fig4',A,'Fig4C_labels','own_figure_label','OriginalFig4c printed redAHPC850 labels; othercoloredbarheights not exact labels',['sample','current_A_g','C_F_g'],[['AHPC-850',str(j),str(v)] for j,v in [(1,386),(2,349),(5,312),(10,273),(20,241)]]),
      unit('Eucommia_Fig3',W,'Fig3_Raman_labels','own_figure_label','OriginalFig3a-d labels; finalcurve saysEC550, not silently renamed500',['sample','ID_IG'],[[n,v] for n,v in zip(['EC-10%','EC-25%','EC-40%','EC-55%','EC-1:2','EC-1:3','EC-1:4','EC-1:5','EC-2h','EC-4h','EC-6h','EC-8h','EC-350','EC-400','EC-450','EC-550_graph_label_only'],['0.570','0.643','0.769','0.812','0.635','0.642','0.643','0.644','0.645','0.655','0.656','0.658','0.623','0.656','0.669','0.674'])]),
      unit('Eucommia',W,'prose_competing_values','own_numeric_prose','XML abstract; bodyp15,p17,p19,p33,p37; locatorperrow retained',['sample','metric','raw','locator'],[['EC-400','cycle_retention_pct','92.3','abstract'],['EC-400','cycle_retention_pct','91.4','bodyp33 loss8.6 complement +p37 exact'],['EC-10%','cycle_loss_pct','10.2','bodyp33'],['EC-6h','BET_surface_area_m2_g','2300.87','bodyp17 versusTable2033.87'],['EC-6h','author_mislabeled_yield_pct','93','bodyp17; Table2 yield43.88,mesofraction96.4'],['EC-55%','mesopore_volume_fraction_pct','71.7','bodyp15 versusTable71.1'],['EC-350','Raman_ID_IG','0.648','bodyp19 versusFigure0.623'],['EC-500','Raman_ID_IG','0.674','bodyp19 temperaturesequence; Figurefinalname550']])
    ]

def curate():
    if (OUT/'curation_spec.json').exists() or DB.exists():raise FileExistsError('Do not overwrite curation.')
    source_specs=[];tables=[]
    with closing(ro(ROOT/'全库复检与特征补提取_20261021/full_corpus_search_native.sqlite')) as n:
        for label,doi,path,digest in SOURCES:
            assert sha(path)==digest;root=E.parse(path).getroot()
            source_specs.append(dict(key=label,doi=doi,path=path.relative_to(ROOT).as_posix(),sha256=digest,title=text(root.find('.//article-title')),article_type=root.get('article-type'),abstract=text(root.find('.//abstract'))))
            rawmap={r[1]:r[0] for r in n.execute('select table_id,locator from raw_tables_v11 where source_sha256=?',(digest,))}
            for t in root.findall('.//table-wrap'):
                loc='XML table-wrap '+t.get('id');kind='secondary_review_context' if doi==R else 'non_biomass_coal_reference' if doi==C else 'mixed_comparison_table' if doi==A and t.get('id').endswith('t009') else 'own_xml_table'
                tables.append(dict(doi=doi,document=label,id=t.get('id'),caption=text(t.find('caption')),locator=loc,kind=kind,grid=xml_grid(t),raw_table_id=rawmap[loc],footnote=text(t.find('table-wrap-foot')),bibr_refs=[text(x) for x in t.findall('.//xref') if x.get('ref-type')=='bibr']))
    write(OUT/'curation_spec.json',dict(sources=source_specs,xml_tables=tables,units=curated_units(),scope='Declared own14main tables/2SI tables/figure labels; all7reviewtables are secondary context and3coal tables nonbiomass reference. No wholepaper completion claim.'))
    print('Curated',len(tables),'main tables and',len(curated_units()),'additional units')

def build():
    if DB.exists() or (OUT/'merge_manifest.json').exists():raise FileExistsError('Do not overwrite database/release.')
    assert sha(PARENT)==PARENT_SHA
    spec=json.loads((OUT/'curation_spec.json').read_text('utf8'));docs={s['key']:dict(doi=s['doi'],path=ROOT/s['path']) for s in spec['sources']}
    docs.update(Eucommia_SI=dict(doi=W,path=SI),Algae_Fig3=dict(doi=A,path=BASE/'OA001/figures/molecules-31-02329-g003.jpg'),Algae_Fig4=dict(doi=A,path=BASE/'OA001/figures/molecules-31-02329-g004.jpg'),Eucommia_Fig3=dict(doi=W,path=BASE/'OA025/figures/polymers-15-00663-g003.jpg'),Eucommia_Fig7=dict(doi=W,path=BASE/'OA025/figures/polymers-15-00663-g007.jpg'))
    a3='molecules-31-02329-t003';a4='molecules-31-02329-t004';a7='molecules-31-02329-t007';w2='polymers-15-00663-t002'
    with closing(ro(PARENT)) as old,closing(sqlite3.connect(DB)) as c:
        old.backup(c);c.row_factory=sqlite3.Row;c.execute('pragma foreign_keys=on')
        c.executescript('''create table cell_extractions_v9(kind text,record_id text,table_key text references reviewed_tables,row_ordinal integer,column_ordinal integer,parse_mode text,primary key(kind,record_id));
        create table source_classifications_v9(doi text primary key references reviewed_sources,decision_json text);
        create table qualification_audits_v9(audit_id text primary key,doi text,record_json text);
        create table purpose_reviews_v9(observation_id text primary key references capacitance_observations,purpose text,review_json text);
        create table legacy_feature_conflicts_v9(endpoint_id text,field_name text,record_json text,primary key(endpoint_id,field_name));''')
        for s in spec['sources']:
            insert(c,'reviewed_sources',dict(doi=s['doi'],path=s['path'],sha256=s['sha256'],title=s['title'],stage='Declared source/table scope; not entire source extraction'))
        for label,d in docs.items():insert(c,'source_documents',dict(document_key=label,doi=d['doi'],path=d['path'].relative_to(ROOT).as_posix(),sha256=sha(d['path']),role='primary_xml' if label in ['Algae','Eucommia','Review','Coal'] else 'own_SI' if label=='Eucommia_SI' else 'original_graphic'))
        units={}
        for t in spec['xml_tables']+spec['units']:
            key=t['doi']+'#'+t['id'];rows=[[x['raw'] for x in r] for r in t['grid']] if 'grid' in t else t['rows'];units[(t['doi'],t['id'])]=(key,rows)
            insert(c,'reviewed_tables',dict(table_key=key,doi=t['doi'],xml_id=t['id'],caption=t.get('caption',t['id']),header_json=json.dumps(rows[0] if 'grid' in t else t['header'],ensure_ascii=False),footnote=t.get('footnote','Declared own source scope; not independent samples or automatic admission.'),source_raw_table_id=t.get('raw_table_id')))
            insert(c,'table_source_links',dict(table_key=key,document_key=t['document'],locator=t['locator']));insert(c,'extraction_units_v3',dict(table_key=key,kind=t['kind'],scope='Secondary comparison and nonbiomass reference excluded from own ordinary labels.' if t['doi'] in [R,C] else 'Own declared cells only; duplicates/competing reports retained.'))
            for i,row in enumerate(rows,1):
                insert(c,'transcribed_rows',dict(table_key=key,row_ordinal=i,cells_json=json.dumps(row,ensure_ascii=False)));insert(c,'transcription_origins_v7',dict(table_key=key,row_ordinal=i,origin_json=json.dumps(t['grid'][i-1] if 'grid' in t else dict(document=t['document'],locator=t['locator'],row=i),ensure_ascii=False)))
            if t.get('raw_table_id'):c.execute('update raw_table_queue set review_state=? where table_id=?',('v9_secondary_review_context_not_own_experiments' if t['doi']==R else 'v9_nonbiomass_coal_reference_not_ordinary_biomass' if t['doi']==C else 'v9_declared_own_series_cells_reviewed_conflicts_separate',t['raw_table_id']))
        def material(doi,sample,stage,scope):
            insert(c,'materials',dict(material_key=mk(doi,sample),doi=doi,sample_name=sample,material_stage=stage));insert(c,'material_scopes_v8',dict(material_key=mk(doi,sample),scope_json=json.dumps(scope,ensure_ascii=False)))
        anames=FIVE+['AHPC-850-R1','AHPC-850-R2','AHPC-850-R4','AHPC-850-t0.5','AHPC-850-t2.5']
        material(A,'raw_algae_precursor','raw_biomass_before_carbonization',dict(origin_class='biomass_precursor',feedstock='washed_green_algae',do_not_copy_CHNS_to_final_XPS=True))
        for s in anames:material(A,s,'reheated_nonactivated_control' if s=='AC-850' else 'final_biomass_carbon_before_test',dict(origin_class='biomass_carbon',feedstock='green_algae',source_equivalent_aliases=['AHPC-850-R3','AHPC-850-t1.5'] if s=='AHPC-850' else [],not_independent_source=True))
        wn=[r[0] for r in units[(W,w2)][1][1:]]
        for s in wn+['EC-550_graph_label_only']:material(W,s,'figure_label_identity_unresolved' if s.endswith('only') else 'final_biomass_carbon_before_test',dict(origin_class='unresolved_graph_sample_identity' if s.endswith('only') else 'biomass_carbon',feedstock='Eucommia_wood',sample_registration_not_unique_independent_recipe=True))
        for alias in ['AHPC-850-R3','AHPC-850-t1.5']:insert(c,'material_aliases_v3',dict(doi=A,raw_name=alias,canonical_name='AHPC-850',basis='OwnTable2/3 explicitly same850C1:3,1.5h optimum; repeated condition reports not independent preparations.'))
        def cell(key,i,col):return json.loads(c.execute('select cells_json from transcribed_rows where table_key=? and row_ordinal=?',(key,i)).fetchone()[0])[col]
        def receipt(kind,id,key,i,col,mode):insert(c,'cell_extractions_v9',dict(kind=kind,record_id=str(id),table_key=key,row_ordinal=i,column_ordinal=col,parse_mode=mode))
        def fact(doi,sample,id,i,col,field,un,method,mode='decimal',conflict=False):
            key=units[(doi,id)][0];raw=cell(key,i,col);doc=c.execute('select document_key from table_source_links where table_key=?',(key,)).fetchone()[0]
            status='conflict_competing_reports_freeze_shared_feature' if conflict else 'own_reported_method_qualified_no_automatic_admission'
            previous=c.execute('select fact_id,value from material_facts where material_key=? and field_name=? and table_key=?',(mk(doi,sample),field,key)).fetchone()
            if previous is not None:
                assert previous['value']==number(raw,mode)
                insert(c,'qualification_audits_v9',dict(audit_id='repeat_fact_'+key+'_'+str(i)+'_'+str(col),doi=doi,record_json=json.dumps(dict(kind='repeated_equivalent_condition_report',selected_fact_id=previous['fact_id'],same_value=previous['value'],row_ordinal=i,column_ordinal=col,table_key=key,not_additional_measurement=True),ensure_ascii=False)))
                return
            row=insert(c,'material_facts',dict(material_key=mk(doi,sample),field_name=field,value=number(raw,mode),raw_value=raw,unit=un,method=method,table_key=key,row_ordinal=i,column_ordinal=col,source_sha256=sha(docs[doc]['path']),review_status=status,training_eligible=0));receipt('fact',row.lastrowid,key,i,col,mode)
        def cap(doi,sample,id,i,col,method,current=None,scan=None,system='3E',extra=None,conflict=False):
            key=units[(doi,id)][0];raw=cell(key,i,col);ident=key+'#'+str(i)+'#'+str(col)
            conditions=dict(extraction_batch='v9',voltage_lower_V=-1 if doi==A and system=='3E' else -.8 if doi==W else 0,voltage_upper_V=0 if doi==A and system=='3E' else .4 if doi==W else 1.6,reference_electrode='Ag/AgCl' if doi==A and system=='3E' else 'Hg/Hg2SO4' if doi==W else None,capacitance_basis='author_whole_electrode_mass' if doi==W else 'single_working_carbon_electrode' if system=='3E' else 'device_total_two_electrode_active_mass',current_mass_basis='author_reported_unknown_not_inferred_from_C_formula',repeat_reports_not_independent_tests=True)
            conditions.update(extra or {})
            insert(c,'capacitance_observations',dict(observation_id=ident,material_key=mk(doi,sample),table_key=key,row_ordinal=i,column_ordinal=col,value=number(raw),raw_value=raw,unit='F/g',method=method,system=system,electrolyte='H2SO4' if doi==W else 'KOH' if system=='3E' else 'Na2SO4',concentration_mol_L=1 if doi==W or system!='3E' else 6,current_A_g=current,scan_rate_mV_s=scan,conditions_json=json.dumps(conditions,ensure_ascii=False),status='conflict_comparison_method_or_value_not_shared_label' if conflict else 'own_reported_scope_qualified_not_automatic_shared_admission',source_group='doi:'+doi,training_eligible=0));receipt('capacitance',ident,key,i,col,'decimal');return ident
        def response(doi,sample,id,i,col,metric,un,mode='decimal',extra=None):
            key=units[(doi,id)][0];raw=cell(key,i,col);ident=key+'#'+str(i)+'#'+str(col)
            insert(c,'outcome_observations_v3',dict(outcome_id=ident,material_key=mk(doi,sample) if sample else None,table_key=key,record_json=json.dumps(dict(metric=metric,value=number(raw,mode),raw_value=raw,unit=un,row_ordinal=i,column_ordinal=col,extraction_batch='v9',source_group='doi:'+doi,feature_role='response_not_pretest_predictor',**(extra or {})),ensure_ascii=False),training_eligible=0));receipt('response',ident,key,i,col,mode)
        # Precursor CHNS/proximate measurements never substitute for final-carbon XPS.
        for i,row in enumerate(units[(A,'molecules-31-02329-t001')][1][1:],2):fact(A,'raw_algae_precursor','molecules-31-02329-t001',i,2,'precursor_'+row[1].replace(' ','_')+'_wt_pct','wt%','Ownproximate/CHNS-O; tabledeclaresdrybasis includingmoisture, no silent renormalization','wt_suffix')
        preferred=[]
        for i,(row,s) in enumerate(zip(units[(A,a3)][1][2:],OPT),3):
            for col,field,un in [(2,'reported_product_yield_pct','wt%'),(3,'BET_surface_area_m2_g','m2/g'),(4,'XPS_N_at_pct','at%')]:fact(A,s,a3,i,col,field,un,'OwnoptimizationTable3; yieldrelativeprecarbonizedchar; NsurfaceXPS notbulk',conflict=col==4 and s in FIVE)
            response(A,s,a3,i,5,'charge_transfer_resistance_ohm','ohm',extra=dict(system='3E',electrolyte='6M_KOH'))
            ident=cap(A,s,a3,i,6,'GCD',current=1)
            if s not in FIVE:preferred.append(ident)
        for i,row in enumerate(units[(A,a4)][1][2:],3):
            s=row[0]
            for col,field,un in [(1,'BET_surface_area_m2_g','m2/g'),(2,'total_pore_volume_cm3_g','cm3/g'),(3,'XPS_N_at_pct','at%'),(4,'Raman_ID_IG','ratio')]:fact(A,s,a4,i,col,field,un,'OwnTable4 NsurfaceXPS;Raman532nm; N2BET77K,degassing200C10h',conflict=col in [3,4])
            response(A,s,a4,i,5,'charge_transfer_resistance_ohm','ohm');preferred.append(cap(A,s,a4,i,6,'GCD',current=1))
        for i,row in enumerate(units[(A,'molecules-31-02329-t005')][1][2:],3):
            component=row[0].lower().replace(' ','_')
            for col,field,un in [(1,'binding_energy_eV','eV'),(2,'FWHM_eV','eV'),(3,'N1s_envelope_pct','%ofN1s_envelope')]:fact(A,'AHPC-850','molecules-31-02329-t005',i,col,'XPS_'+component+'_'+field,un,'OwnN1s fit; fractions withinN1s, nottotalatomic%; no multiplication through conflictingtotalN')
        for i,row in enumerate(units[(A,'molecules-31-02329-t006')][1][2:],3):
            for col,field,un in [(1,'water_contact_angle_deg','degree'),(2,'electrolyte_uptake_g_g','g/g'),(3,'pellet_conductivity_S_m','S/m')]:fact(A,row[0],'molecules-31-02329-t006',i,col,field,un,'Owncontactwater/electrolyteuptake/fourpointcompressedpellet; uptakeelectrolyteidentity/duration notspecifiedperrow')
        for i,row in enumerate(units[(A,'Fig3_Raman_XPS')][1],1):
            for col,field,un in [(1,'Raman_ID_IG','ratio'),(2,'XPS_C_at_pct','at%'),(3,'XPS_N_at_pct','at%'),(4,'XPS_O_at_pct','at%'),(5,'XPS_S_at_pct','at%')]:fact(A,row[0],'Fig3_Raman_XPS',i,col,field,un,'OwnFig3 printedlabels; C/N/O/S atomic% separately; notderivedfromcomplement',conflict=col in [1,3])
        for i,row in enumerate(units[(A,a7)][1][2:],3):
            cap(A,row[0],a7,i,1,'GCD',current=1);preferred.append(cap(A,row[0],a7,i,2,'GCD',current=20))
            response(A,row[0],a7,i,3,'GCD_rate_retention_pct','%','decimal',dict(from_current_A_g=1,to_current_A_g=20,not_cycle_retention=True));response(A,row[0],a7,i,4,'charge_transfer_resistance_ohm','ohm');response(A,row[0],a7,i,6,'cycle_10000_coulombic_efficiency_pct','%',extra=dict(cycle_count=10000,not_retention_target=True))
            rec=dict(source_group='doi:'+A,system='3E',method='GCD',electrolyte='KOH',concentration_mol_L=6,reference_electrode='Ag/AgCl',reported_current_A_g=10,current_mass_basis='author_reported_unknown',cycle_count=10000,retention_pct=float(row[5]),retention_relation='=',cycle_voltage_lower_V=-1,cycle_voltage_upper_V=0,baseline_index=None,baseline_reference='ownTable7 cyclingcolumn,common10Agmethod; exactinitialindexunknown; not ratecolumn',source_sha256=docs['Algae'].get('sha256',sha(docs['Algae']['path'])),evidence_source_path=docs['Algae']['path'].relative_to(ROOT).as_posix(),locator='Table7 ownrow;bodyp26commoncycling,Fig4only850',already_present_cycling_source=True,legacy_endpoint_id='candidate:TE007' if row[0]=='AHPC-850' else 'candidate:v11:AHPC2026:'+row[0]+':3E:10000')
            insert(c,'test_candidates',dict(candidate_id='LP9_Algae_'+row[0]+'_C10000',material_key=mk(A,row[0]),record_json=json.dumps(rec,ensure_ascii=False),training_eligible=0))
        for i,row in enumerate(units[(A,'Fig4C_labels')][1],1):
            ident=cap(A,row[0],'Fig4C_labels',i,2,'GCD',current=float(row[1]))
            if float(row[1]) in [2,5,10]:preferred.append(ident)
        for i,row in enumerate(units[(A,'molecules-31-02329-t008')][1][2:6],3):
            cap(A,'AHPC-850','molecules-31-02329-t008',i,2,'GCD',system='2E_symmetric',extra=dict(operation_name=row[0],reported_power_W_kg=float(row[4]),reported_current_A_g=None,current_not_derived_from_energy_power=True))
            for col,metric,un in [(3,'device_energy_Wh_kg','Wh/kg'),(4,'device_power_W_kg','W/kg'),(5,'device_coulombic_efficiency_pct','%')]:response(A,'AHPC-850','molecules-31-02329-t008',i,col,metric,un,extra=dict(system='2E_symmetric',voltage_window_V=[0,1.6],normalization='total_active_mass_both_electrodes'))
        response(A,'AHPC-850','molecules-31-02329-t008',7,5,'device_cycle10000_CE_pct','%',extra=dict(not_retention_target=True))
        rec=dict(source_group='doi:'+A,system='2E_symmetric',method='GCD',electrolyte='Na2SO4',concentration_mol_L=1,cycle_count=10000,retention_pct=95.2,retention_relation='=',reported_current_A_g=None,cycle_voltage_lower_V=0,cycle_voltage_upper_V=1.6,baseline_index=None,baseline_reference='authorreportedretainedpercentage; no exactindex',issue='Cyclecurrent notspecified inTable8; do notborrow3E10Ag orderivefrom250Wkg',locator='ownTable8 finalrow retained95.2%; notcapacitanceF/g',evidence_source_path=docs['Algae']['path'].relative_to(ROOT).as_posix(),source_sha256=sha(docs['Algae']['path']))
        insert(c,'test_candidates',dict(candidate_id='LP9_Algae_AHPC850_2E_C10000',material_key=mk(A,'AHPC-850'),record_json=json.dumps(rec,ensure_ascii=False),training_eligible=0))
        # Eucommia: all20 porosity registrations; ratios, angstroms and yield units stay explicit.
        for i,row in enumerate(units[(W,w2)][1][1:],2):
            for col,field,un in [(1,'BET_surface_area_m2_g','m2/g'),(2,'BJH_average_pore_diameter_A','angstrom'),(3,'total_pore_volume_cm3_g','cm3/g'),(4,'mesopore_volume_cm3_g','cm3/g'),(5,'reported_product_yield_pct','wt%'),(6,'mesopore_volume_fraction_pct','%')]:fact(W,row[0],w2,i,col,field,un,'OwnN2BET; tablefootnotes VtotalP/P0~.95,BJH4V/A,meso=total-micro;yielddryrawwood',mode='pct' if col==6 else 'decimal',conflict=(row[0]=='EC-6h' and col==1) or (row[0]=='EC-55%' and col==6))
        for i,row in enumerate(units[(W,'Fig3_Raman_labels')][1],1):fact(W,row[0],'Fig3_Raman_labels',i,1,'Raman_ID_IG','ratio','OwnFig3 intensityratio; lastlabelEC550notrenamed500',conflict=row[0] in ['EC-350','EC-550_graph_label_only'])
        for i,row in enumerate(units[(W,'prose_competing_values')][1],1):
            if row[1] in ['BET_surface_area_m2_g','mesopore_volume_fraction_pct','Raman_ID_IG']:fact(W,row[0],'prose_competing_values',i,2,row[1],'m2/g' if row[1].startswith('BET') else 'ratio' if row[1].startswith('Raman') else '%','Ownprose '+row[3]+';competingoriginalvalue',conflict=True)
            else:response(W,row[0],'prose_competing_values',i,2,row[1],'%',extra=dict(status='competing_or_qualified_report',locator=row[3]))
        for i,row in enumerate(units[(W,'polymers-15-00663-t003')][1][2:],3):
            for col,v in enumerate([5,10,20,50],1):cap(W,row[0],'polymers-15-00663-t003',i,col,'CV',scan=v)
            response(W,row[0],'polymers-15-00663-t003',i,5,'CV_rate_retention_pct','%','pct',dict(from_scan_mV_s=5,to_scan_mV_s=50,not_cycle_retention=True))
        for i,row in enumerate(units[(W,'SI_TableS1')][1],1):
            for col,j in enumerate([.2,.5,.8,1.2],1):cap(W,row[0],'SI_TableS1',i,col,'GCD',current=j)
            response(W,row[0],'SI_TableS1',i,5,'GCD_rate_retention_pct','%','pct',dict(from_current_A_g=.2,to_current_A_g=1.2,not_cycle_retention=True))
        # SI comparison's own252@.2 conflicts with directGCD257.8 andmatchesCV252: keep isolated.
        cap(W,'EC-400','SI_TableS2',10,5,'unspecified_comparison',current=.2,conflict=True,extra=dict(competing_direct_GCD_F_g=257.8,matching_CV5mVs_F_g=252,not_cycle_current=True))
        for i,row in enumerate(units[(W,'polymers-15-00663-t004')][1][1:],2):
            for col,metric in [(1,'Rs_ohm'),(2,'Rct_ohm'),(3,'author_ESR_ohm')]:response(W,row[0],'polymers-15-00663-t004',i,col,metric,'ohm',extra=dict(author_ESR_formula_not_assumed=True))
        for tid,kind in [('polymers-15-00663-t001','author_resource_inventory'),('polymers-15-00663-t005','author_cost_assessment')]:
            key,rows=units[(W,tid)]
            for i,row in enumerate(rows[1:],2):
                for col,s in enumerate(rows[0][1:],1):response(W,s,tid,i,col,row[0],row[0].split('/')[-1] if kind.endswith('assessment') else row[0],mode='scientific' if '×' in row[col] else 'decimal',extra=dict(response_family=kind,not_electrochemical_target=True,costSUM_not_recomputed_or_replaced=True,unit_definition_uncertainties_preserved=True))
        for s,ret,kind in [('EC-10%',89.8,'derived_complement_of_reported_loss10.2'),('EC-400',91.4,'body_and_SI_report_abs92.3_competing')]:
            rec=dict(source_group='doi:'+W,system='3E',method='GCD',electrolyte='H2SO4',concentration_mol_L=1,reference_electrode='Hg/Hg2SO4',cycle_count=10000,retention_pct=ret,retention_relation='derived_complement' if s=='EC-10%' else '=',value_kind=kind,reported_current_A_g=None,current_mass_basis='unknown',cycle_voltage_lower_V=-.8,cycle_voltage_upper_V=.4,baseline_index=None,baseline_reference='ownSI_FigS5normalizedstart;exactindexunknown',issue='Actualcyclecurrent missing; SIcomparison .2Ag ischaracterization,notcyclecurrent',already_present_cycling_source=True,legacy_endpoint_id='candidate:V05:023' if s=='EC-10%' else 'candidate:V05:022',evidence_source_path=SI.relative_to(ROOT).as_posix(),source_sha256=sha(SI),locator='SIp3FigS5,p5ownrow +bodyp33,p37; originalabstract92.3kept')
            insert(c,'test_candidates',dict(candidate_id='LP9_Eucommia_'+s+'_C10000',material_key=mk(W,s),record_json=json.dumps(rec,ensure_ascii=False),training_eligible=0))
        # Bind synthesis per variable; preserve temp-series duration ambiguity, no tuning by outputs.
        for s in anames:
            temp=850 if s=='AC-850' or '-850' in s else int(s.split('-')[-1]);ratio=int(s[-1]) if '-R' in s else 3;duration=float(s.split('-t')[1]) if '-t' in s else 1.5
            stages=[dict(stage='feedstock_pretreatment',drying_temperature_C=80,drying_duration_h=12,sieve_mesh=100,washing='DIwater'),dict(stage='carbonization',temperature_C=500,duration_h=2,heating_rate_C_min=5,atmosphere='N2')]
            stages.append(dict(stage='reheating_without_activator' if s=='AC-850' else 'chemical_activation',temperature_C=temp,duration_h=None if s=='AC-850' else duration,agent=None if s=='AC-850' else 'KOH',carbon_to_activator_mass_ratio=None if s=='AC-850' else [1,ratio],atmosphere='N2',impregnation_stir_h=4,impregnation_drying_C=100,activation_heating_rate_C_min=None,post_wash_HCl_mol_L=1,post_wash_pH='nearneutral',post_drying_C=80,post_drying_duration='overnight_unquantified'))
            stages.append(dict(stage='electrode_preparation',carbon_wt_pct=80,acetylene_black_wt_pct=10,PVDF_wt_pct=10,slurry_stir_h=6,drying_temperature_C=80,collector='Ni_foam',mass_loading_mg_cm2=2.4,mass_loading_uncertainty=.2,active_mass_excludes_binder_additive_collector=True,replicate_statement='atleast3independent electrodes,reportedaverages; no separate measuredreplicatesprovided'))
            insert(c,'synthesis_stages_v3',dict(material_key=mk(A,s),document_key='Algae',locator='bodyp5-27;Table2/3series;ACreheatingdurationnotexplicit',stages_json=json.dumps(stages,ensure_ascii=False)))
        for s in wn:
            conc=float(s[3:-1]) if s.endswith('%') else 25;ratio=int(s.split(':')[1]) if s.startswith('EC-1:') else 4;duration=float(s[3:-1]) if s.endswith('h') else 2 if not re.fullmatch(r'EC-\d{3}',s) else None;temp=int(s[3:]) if re.fullmatch(r'EC-\d{3}',s) else 400
            stages=[dict(stage='hydrothermal_carbonization',temperature_C=170,duration_h=1,feedstock_g=10,DIwater_mL=80,prior_sieve_mesh=[40,60],bark_and_leaves_removed=True),dict(stage='chemical_activation',temperature_C=temp,duration_h=duration,duration_state='temperature_series_methodcontrol2h_vsoptimized6h_tablepattern_unresolved' if duration is None else 'ownsinglefactorcondition',agent='H3PO4',reported_H3PO4_solution_mass_pct=conc,reported_feedstock_to_activator_ratio=[1,ratio],ratio_caveat='bodycallswood:H3PO4massratio andsolid-liquidratio; do notinferpureacidmassfromsolution',carbon_to_activator_mass_ratio=None,heating_rate_C_min=5,atmosphere='N2',drying_before_activation_C=105),dict(stage='washing',HCl_pct=1,temperature_C=105,duration_min=50,post_water_wash='neutralfiltrate'),dict(stage='electrode_preparation',carbon_wt_pct=85,carbonblack_wt_pct=10,PTFE_wt_pct=5,reported_total_mixture_mg=9.5,press_pressure_MPa=1,collector='stainless_steel_mesh',capacitance_mass_basis='authorwholeelectrodemass; no silentactivecarbonconversion')]
            insert(c,'synthesis_stages_v3',dict(material_key=mk(W,s),document_key='Eucommia',locator='ownbodyp4,p5,p8; contradictorytemperature/timeparentheticals retained inXML',stages_json=json.dumps(stages,ensure_ascii=False)))
        # Review per chosen exact report; duplicate aliases/summary cells stay outside view.
        assert len(preferred)==18 and len(set(preferred))==18
        for ident in preferred:
            review=dict(purpose='reported_aqueous_3e_GCD_capacitance',decision='OwnGCD/singleactivecarbonmass/6MKOH/AgAgCl/-1..0V andmaterialrecipebound; selectoneexactreportpercanonicalmaterial/current; N/Ramanconflictsmasked',new_source_group='doi:'+A,not_new_independent_cycling_source=True,same_DOI_alltests_and_auxiliary_quarantined=True,new_training_authorization=False)
            insert(c,'auxiliary_gcd_reviews_v3',dict(observation_id=ident,purpose=review['purpose'],eligible=1,reason=review['decision'],review_basis='Ownmethods26/27+Fig4+Tables3/4/7; material facts qualified separately'))
            insert(c,'purpose_reviews_v9',dict(observation_id=ident,purpose=review['purpose'],review_json=json.dumps(review,ensure_ascii=False)))
        decisions={A:dict(classification='original_biomass_research',basis='Nativearticlemeta+ownmethods5-34+ownvariablematrixTables1-8; Fig3/tableNandRamanconflictsretained',remaining='FullCV/GCD/adsorption/EISwaveforms,morphologyquantification,figure5panelmismatch,originalinstrumentfilesnotprovided'),W:dict(classification='original_biomass_research',basis='Nativearticlemeta+ownEUOwoodmethod+20sampleporosity,16sampleCV/GCD/EIS+matched6pSI',remaining='Fullwaveforms;actualcyclingcurrentunreported;recipealiases/temperatureduration,abstract/bodyretention/Raman/porosityandcostconflicts'),R:dict(classification='secondary_review_context',basis='Nativearticletypereview +abstractexplicitreview+all7tableheaders/rowswithbibrreferences; noownexperimentalmeasurements',remaining='Reference-levelprimarysourcecrosswalk notdone; tablecontextonly, notownmeasurements'),C:dict(classification='non_biomass_coal_reference',basis='Ownabstract/bodyp4-8 andexperimentalfeedstocksBaishihu/Yicheng fossilcoals; all3tablesowncoalreference',remaining='Noordinarybiomassadmission; keepnativecoalreference,notfullextraction')}
        for s in spec['sources']:
            d=decisions[s['doi']];evidence=[dict(table_key=t['doi']+'#'+t['id'],locator=t['locator'],path=s['path'],sha256=s['sha256']) for t in spec['xml_tables'] if t['doi']==s['doi']]
            insert(c,'source_classifications_v9',dict(doi=s['doi'],decision_json=json.dumps(dict(d,native_article_type=s['article_type'],source_sha256=s['sha256'],whole_source_review_complete=False),ensure_ascii=False)))
            insert(c,'source_scope_decisions',dict(doi=s['doi'],scope=d['classification'],reason=d['basis'],evidence_json=json.dumps(dict(units=evidence,whole_source_completion_proven=False,remaining=d['remaining']),ensure_ascii=False),full_source_review_complete=0))
        issues=[('Algae_XPS_N',A,None,'Tables3/4surfaceN differsFig3e forfive samples; freeze bothreportsets,notlatest/highest'),('Algae_Raman',A,None,'Table4ratios differFig3d; freezeallfive sharedratios'),('Algae_N_envelope',A,'AHPC-850','N1sspeciesareenvelopefractions; no multiplythroughconflictingtotalN'),('Algae_device_cycle',A,'AHPC-850','Table8retained95.2ispercentnotF/g; cyclecurrentmissing'),('Algae_Fig5_panels',A,'AHPC-850','bodydescribessixpanels,butcaption/availableimage4; retainprose/figureidentitylimits'),('Wood_BET',W,'EC-6h','Table2033.87 vsbody2300.87; nooverwrite'),('Wood_Raman350',W,'EC-350','Figure.623 vsbody.648'),('Wood_Raman550',W,'EC-500','FigureEC550 vsbody/tableEC500; noaliasguess'),('Wood_cycle',W,'EC-400','abstract92.3,body/SI91.4; currentmissing; oldfixedpendingnotcleared'),('Wood_alias',W,None,'EC25/1:4/2hcommonrecipe butownrows differ yield,porevolume,GCD1.2; registrationsnotindependentrecipes'),('Wood_rate',W,None,'ReportedCV/GCDretentionratios include arithmeticalmismatch; keepraw,notcyclingtarget'),('Wood_protocol',W,None,'EISmethods100kHz..10MHz vsresult.01..100000Hz; rawrangesretained,notnormalized'),('Wood_cost',W,None,'Table5SUM1.54 differscomponentcosts~15.4+; no overwrite oruseasmaterialfeature'),('Secondary_review',R,None,'7tablesarecitedcontext,notnewmeasurements'),('Coal_scope',C,None,'Fossilcoalreferenceoutsidebiomassmain,retainoriginal')]
        for name,doi,s,reason in issues:insert(c,'scientific_issues',dict(issue_id='LP9_'+name,doi=doi,sample_name=s,issue_json=json.dumps(dict(kind=name,action=reason),ensure_ascii=False)))
        c.commit()
    # Freeze old selected fields via a forward overlay later; scientific source records stay raw.
    from data.cycling_db import open_database
    conflicts=[]
    with open_database() as old:
        for row in old.fetch('all_review').rows:
            if row['source_group']!='doi:'+A:continue
            for f in ['N_at_pct','XPS_N_reported_pct','Raman_ID_IG']:
                if row.get(f) is not None:conflicts.append(dict(endpoint_id=row['endpoint_id'],sample_name=row['sample_name'],field_name=f,previous_value=row[f],selected_value=None,reason='NeworiginalFig3/tableconflict; rawbothvaluesretainedinliteraturev9',source_sha256=SOURCES[0][3],figure_sha256=sha(docs['Algae_Fig3']['path']),table='molecules-31-02329-t004',figure='Fig3d/e',status='conflict_frozen_not_zero'))
    with closing(sqlite3.connect(DB)) as c:
        for item in conflicts:insert(c,'legacy_feature_conflicts_v9',dict(endpoint_id=item['endpoint_id'],field_name=item['field_name'],record_json=json.dumps(item,ensure_ascii=False)))
        c.commit()
    protected=[dict(path=d['path'].relative_to(ROOT).as_posix(),sha256=sha(d['path'])) for d in docs.values()]
    protected.extend([dict(path=PARENT.relative_to(ROOT).as_posix(),sha256=PARENT_SHA),dict(path='全库复检与特征补提取_20261021/full_corpus_search_native.sqlite',sha256='f2720c3e417904dad5857a6574cc72d5cf996f9b8716620d69594f11380c658c')])
    cp=json.loads((ROOT/'data/current_database.json').read_text('utf8'));q=ROOT/cp['version_directory']/cp['database_file'];protected.append(dict(path=q.relative_to(ROOT).as_posix(),sha256=cp['sha256']))
    write(OUT/'protected_inputs.json',dict(files=protected));write(OUT/'legacy_feature_conflicts.json',conflicts)
    audit()
    print('Built v9; legacy feature conflicts:',len(conflicts))

def audit():
    """Complete own draft arithmetic receipts, without changing an author cell."""
    assert not (OUT/'merge_manifest.json').exists()
    with closing(sqlite3.connect(DB)) as c:
        c.row_factory=sqlite3.Row
        assert not c.execute("select 1 from qualification_audits_v9 where audit_id like 'v9rate_%'").fetchone()
        def interval(raw):
            raw=raw.removesuffix('%');places=len(raw.split('.')[1]) if '.' in raw else 0;half=.5*10**(-places);v=float(raw);return v-half,v+half
        for doi,tid,start,first,last,rate,kind in [(A,'molecules-31-02329-t007',3,1,2,3,'GCD_20Ag_over1Ag'),(W,'polymers-15-00663-t003',3,1,4,5,'CV50mVs_over5mVs'),(W,'SI_TableS1',1,1,4,5,'GCD1.2Ag_over0.2Ag')]:
            key=doi+'#'+tid
            for r in c.execute('select * from transcribed_rows where table_key=? and row_ordinal>=? order by row_ordinal',(key,start)).fetchall():
                row=json.loads(r['cells_json']);a,b=interval(row[first]),interval(row[last]);reported=interval(row[rate]);bounds=[100*b[0]/a[1],100*b[1]/a[0]]
                record=dict(kind='rate_ratio_arithmetic_not_new_measurement',sample_name=row[0],table_key=key,row_ordinal=r['row_ordinal'],ratio_kind=kind,reported_rate_retention_pct=number(row[rate],'pct'),computed_from_printed_capacitances_pct=100*float(row[last])/float(row[first]),printed_rounding_ratio_bounds_pct=bounds,overlaps_reported_rounding=not(bounds[1]<reported[0] or reported[1]<bounds[0]),decision='Preserveauthorrateandowncapacitances; no correction orconversiontocyclingtarget')
                insert(c,'qualification_audits_v9',dict(audit_id='v9rate_'+key+'_'+str(r['row_ordinal']),doi=doi,record_json=json.dumps(record,ensure_ascii=False)))
        key=W+'#polymers-15-00663-t005';rows=[json.loads(r[0]) for r in c.execute('select cells_json from transcribed_rows where table_key=? order by row_ordinal',(key,))]
        for col,sample in enumerate(rows[0][1:],1):
            total=sum(number(row[col],'scientific' if '×' in row[col] else 'decimal') for row in rows[1:12]);reported=float(rows[12][col]);record=dict(kind='cost_component_sum_not_new_measurement',sample_name=sample,table_key=key,reported_SUM_CNY=reported,computed_printed_component_sum_CNY=total,decision='SUM1.54differscomponents; rawcostsnotmaterialfeatures, noauthorcorrectionclaimed')
            insert(c,'qualification_audits_v9',dict(audit_id='v9cost_'+sample,doi=W,record_json=json.dumps(record,ensure_ascii=False)))
        c.commit()

def verify(prepare=False):
    checks=[]
    def ck(name,condition):
        if not condition:raise AssertionError(name)
        checks.append(name)
    for p in json.loads((OUT/'protected_inputs.json').read_text('utf8'))['files']:ck('protected_'+p['path'],sha(ROOT/p['path'])==p['sha256'])
    for p in json.loads((PARENT.parent/'merge_manifest.json').read_text('utf8'))['outputs']:ck('v8payload_'+p['path'],sha(ROOT/p['path'])==p['sha256'])
    spec=json.loads((OUT/'curation_spec.json').read_text('utf8'));digest=sha(DB)
    with closing(ro(DB)) as c,closing(ro(PARENT)) as old:
        c.row_factory=sqlite3.Row
        ck('integrity',c.execute('pragma integrity_check').fetchone()[0]=='ok');ck('foreign_keys',not c.execute('pragma foreign_key_check').fetchall())
        for (t,) in old.execute("select name from sqlite_master where type='table' and name not like 'sqlite_%'"):
            if t=='raw_table_queue':continue
            now={tuple(x) for x in c.execute('select * from '+t)};ck('parent_rows_'+t,all(tuple(x) in now for x in old.execute('select * from '+t)))
        oldq={r[0]:tuple(r) for r in old.execute('select * from raw_table_queue')};now=list(c.execute('select * from raw_table_queue'));changed={r[0] for r in now if tuple(r)!=oldq[r[0]]};ids={t['raw_table_id'] for t in spec['xml_tables']};ck('only24rawqueuechanges',changed==ids and len(ids)==24)
        for r in now:ck('raw_queue_identity_'+r[0],tuple(r)[:6]==oldq[r[0]][:6] and tuple(r)[7:]==oldq[r[0]][7:])
        for t in spec['xml_tables']+spec['units']:
            key=t['doi']+'#'+t['id'];rows=[json.loads(r[0]) for r in c.execute('select cells_json from transcribed_rows where table_key=? order by row_ordinal',(key,))]
            if 'grid' in t:
                src=next(s for s in spec['sources'] if s['key']==t['document']);root=E.parse(ROOT/src['path']).getroot();grid=xml_grid(root.find(".//table-wrap[@id='"+t['id']+"']"));ck('native_spans_'+key,grid==t['grid']);expect=[[x['raw'] for x in r] for r in grid]
            else:expect=t['rows']
            ck('transcription_'+key,rows==expect)
        for r in c.execute('select * from cell_extractions_v9'):
            cell=json.loads(c.execute('select cells_json from transcribed_rows where table_key=? and row_ordinal=?',(r['table_key'],r['row_ordinal'])).fetchone()[0])[r['column_ordinal']]
            table,key=('material_facts','fact_id') if r['kind']=='fact' else ('capacitance_observations','observation_id') if r['kind']=='capacitance' else ('outcome_observations_v3','outcome_id')
            out=c.execute('select * from '+table+' where '+key+'=?',(r['record_id'],)).fetchone();v=json.loads(out['record_json']) if r['kind']=='response' else out
            ck('raw_'+r['kind']+r['record_id'],v['raw_value']==cell);ck('value_'+r['kind']+r['record_id'],v['value']==number(cell,r['parse_mode']))
            if r['parse_mode']=='scientific':
                tid=r['table_key'].split('#')[-1];root=E.parse(BASE/'OA025/main.xml').getroot();td=root.find(".//table-wrap[@id='"+tid+"']").findall('.//tr')[r['row_ordinal']-1][r['column_ordinal']]
                ck('native_superscript_'+r['record_id'],td.find('sup') is not None and '10'+text(td.find('sup'))==re.sub(r'\s+','',cell).split('×')[1])
        # Independently compare the complete SI numeric rows with native PDF text tokens.
        import pypdf
        native=pypdf.PdfReader(SI).pages[3].extract_text();sirows=next(t['rows'] for t in spec['units'] if t['id']=='SI_TableS1')
        for row in sirows:
            line=next(x for x in native.splitlines() if x.strip().startswith(row[0]+' '));tokens=line.split();ck('SI_all_cells_'+row[0],tokens==row)
        for t in ['material_facts','capacitance_observations','outcome_observations_v3','test_candidates','raw_table_queue']:ck('raw_no_auto_admit_'+t,c.execute('select count(*) from '+t+' where training_eligible!=0 or training_eligible is null').fetchone()[0]==0)
        ck('all23_scopes_partial',c.execute('select count(*) from source_scope_decisions').fetchone()[0]==23 and c.execute('select sum(full_source_review_complete) from source_scope_decisions').fetchone()[0]==0)
        count=lambda t:c.execute('select count(*) from '+t).fetchone()[0]
        previous=json.loads((PARENT.parent/'summary.json').read_text('utf8'));summary=dict(previous)
        updates=dict(cumulative_reviewed_source_publications=count('reviewed_sources'),cumulative_materials=count('materials'),cumulative_selected_material_cells=count('material_facts'),cumulative_numeric_material_facts=c.execute('select count(*) from material_facts where value is not null').fetchone()[0],capacitance_records=count('capacitance_observations'),numeric_capacitance_values=c.execute('select count(*) from capacitance_observations where value is not null').fetchone()[0],cycling_candidates=count('test_candidates'),response_outcomes=count('outcome_observations_v3'),scientific_issues=count('scientific_issues'),synthesis_materials=count('synthesis_stages_v3'),raw_candidates_touched=91,raw_candidates_untouched=868,reviewed_table_units=106,reviewed_evidence_units=163,new_materials=count('materials')-previous['cumulative_materials'],new_numeric_material_facts=c.execute('select count(*) from material_facts where value is not null').fetchone()[0]-previous['cumulative_numeric_material_facts'],new_capacitance_reports=count('capacitance_observations')-previous['capacitance_records'],new_response_records=count('outcome_observations_v3')-previous['response_outcomes'],new_own_main_tables=14,new_own_SI_tables=2,new_secondary_review_tables=7,new_non_biomass_coal_reference_tables=3,new_bounded_curve_samples=0,auxiliary_aqueous_3e_GCD_rows=121,auxiliary_purpose_reviewed_input_rows=137,auxiliary_independent_DOI_groups=9,legacy_cycle_feature_cells_frozen=count('legacy_feature_conflicts_v9'),formal_cycling_admissions=0,model_fits=0,all_literature_fully_utilized=False,scope_note='OwnAlgae/Eucommiaseries,explicitduplicate/conflict/methodboundaries;7reviewtablessecondary,3coaltablesnonbiomass. New18auxinputssameDOIas5existingcyclerecords,notnewindependentsources; nofit. Fixed38pendingnotcleared.')
        updates.update(new_source_response_records=updates['new_response_records'],new_curve_groups=0,cumulative_bounded_curve_samples=58,cumulative_curve_groups=10,arithmetic_qualification_audits=count('qualification_audits_v9'))
        summary.update(updates);ck('untouched_count',c.execute("select count(*) from raw_table_queue where review_state='automatic_candidate_unreviewed'").fetchone()[0]==868)
        ck('37_rate_audits',c.execute("select count(*) from qualification_audits_v9 where audit_id like 'v9rate_%'").fetchone()[0]==37)
    from data.literature_v9 import open_literature_database as api9
    from data.literature_v8 import open_literature_database as api8
    with api9(DB,digest) as new,api8(PARENT,PARENT_SHA) as old:
        for profile in ['3e','2e_device','native_mineral_3e','2e_author_factor2']:
            oldrows=old.auxiliary_feature_rows(profile);newrows=new.auxiliary_feature_rows(profile);oldids={r['observation_id'] for r in oldrows};ck('old_aux_values_'+profile,[r for r in newrows if r['observation_id'] in oldids]==oldrows)
        arows=[r for r in new.auxiliary_feature_rows('3e') if r['doi']==A];ck('18_exact_own_GCD_inputs',len(arows)==18 and len({(r['sample_name'],r['current_A_g']) for r in arows})==18)
        ck('five_main_N_Raman_masked',all(r['XPS_N_at_pct'] is None and r['Raman_ID_IG'] is None for r in arows if r['sample_name'] in FIVE));ck('uncontested_subset_BET',all(r['BET_surface_area_m2_g'] is not None for r in arows))
        for target in ['retention','capacitance']:ck('DES_preserved_'+target,new.des_reported_inputs(target)==old.des_reported_inputs(target))
        ck('composite_preserved',new.composite_cycle_inputs()==old.composite_cycle_inputs());ck('oldcurves58',new.sampled_curves()==old.sampled_curves())
        ck('44candidate_groups',len(new.tests())==44 and all(x['record']['source_group'].startswith('doi:') for x in new.tests()))
        for doi in [R,C]:ck('not_own_labels_'+doi,not new.facts(doi=doi) and not new.capacitances(doi=doi))
    ck('readonly_DB',sha(DB)==digest)
    report=dict(status='passed',database_sha256=digest,check_count=len(checks),checks=checks,model_fits=0,full_goal_complete=False)
    if prepare:
        assert not (OUT/'merge_manifest.json').exists();write(OUT/'summary.json',summary);write(OUT/'verification.json',report)
    else:
        assert json.loads((OUT/'summary.json').read_text('utf8'))==summary,'summary_recomputed'
        saved=json.loads((OUT/'verification.json').read_text('utf8'));assert saved==report
        if (OUT/'merge_manifest.json').exists():
            for p in json.loads((OUT/'merge_manifest.json').read_text('utf8'))['outputs']:assert sha(ROOT/p['path'])==p['sha256'],p['path']
    print(json.dumps(dict(summary=summary,checks=len(checks)),ensure_ascii=False))

def seal():
    if (OUT/'merge_manifest.json').exists():raise FileExistsError('Already sealed.')
    verify(False)
    paths=[p for p in OUT.rglob('*') if p.is_file()]+[ROOT/'tools/extract_algae_eucommia_v9.py',ROOT/'tools/verify_corpus_chain_v9.py',ROOT/'data/literature_v9.py']
    write(OUT/'merge_manifest.json',dict(version='literature_pool_v9',database_sha256=sha(DB),parent_sha256=PARENT_SHA,outputs=[dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p),bytes=p.stat().st_size) for p in sorted(paths)],model_fits=0,scientific_goal_complete=False))
    write(ROOT/'data/current_literature.json',dict(version='literature_pool_v9',directory=OUT.relative_to(ROOT).as_posix(),database_file=DB.name,sha256=sha(DB),api_module='data.literature_v9',scope='Algae/Eucommiaownseries; reviewandcoalcontextseparate;fig/tableconflicts;18newauxiliaryGCDinputs, no newformalcyclingadmission.'))

if __name__=='__main__':
    if len(sys.argv)!=2 or sys.argv[1] not in ['curate','build','audit','prepare','verify','seal']:raise SystemExit('curate/build/audit/prepare/seal are one-use; verify is read-only')
    if sys.argv[1]=='prepare':verify(True)
    else:globals()[sys.argv[1]]()
