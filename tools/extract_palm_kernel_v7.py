"""One-source additive extraction; raw replicas, aggregate statistics and stacks remain distinct."""
from pathlib import Path
from contextlib import closing
import csv,hashlib,io,json,math,re,sqlite3,statistics,sys,xml.etree.ElementTree as E
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
OUT=ROOT/'文献全量利用复核_20261026/批次07_棕榈壳与串并联';DB=OUT/'literature_material_pool_v7.sqlite'
PARENT=ROOT/'文献全量利用复核_20261026/批次06_剩余SI与DES协议/literature_material_pool_v6.sqlite'
PARENT_SHA='8d9cb4b62c4dd1b6f8cd31ea7b6459472d84ee03e4eb2852a07d3bd9af981723'
DOI='10.3390/nano16040260';BASE=ROOT/'文献扩充_大批补齐_20261018/sources/SUP_144'
MAIN=BASE/'main.xml';SI=OUT/'evidence/PalmKernel_SI.pdf'
NUM=r'[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][-+]?\d+)?'
def text(e):return ' '.join(''.join(e.itertext()).split()) if e is not None else ''
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf8')
def ro(p):return sqlite3.connect(Path(p).resolve().as_uri()+'?mode=ro',uri=True)
def mk(sample):return 'literature:'+hashlib.sha256((DOI+'\0'+sample).encode()).hexdigest()[:24]
def number(raw):
    if raw=='22,806':return 22806.0
    return float(raw) if re.fullmatch(NUM,raw) else None
def measurement(raw):
    parts=[p.strip() for p in raw.split('±')]
    assert len(parts) in (1,2) and all(number(p) is not None for p in parts),raw
    return number(parts[0]),number(parts[1]) if len(parts)==2 else None
def insert(c,t,v):
    keys=list(v);return c.execute('insert into '+t+' ('+','.join(keys)+') values ('+','.join('?' for _ in keys)+')',[v[k] for k in keys])
def xml_grid(table):
    occupied={};result=[]
    for ri,tr in enumerate(table.findall('.//tr')):
        col=0
        for td in tr:
            while (ri,col) in occupied:col+=1
            cell=dict(raw=text(td),origin_row=ri,origin_column=col,rowspan=int(td.get('rowspan','1')),colspan=int(td.get('colspan','1')))
            for rr in range(ri,ri+cell['rowspan']):
                for cc in range(col,col+cell['colspan']):assert (rr,cc) not in occupied;occupied[(rr,cc)]=cell
            col+=cell['colspan']
        width=max(cc for rr,cc in occupied if rr==ri)+1
        result.append([occupied.get((ri,cc),dict(raw='',origin_row=ri,origin_column=cc)) for cc in range(width)])
    return result

def curate():
    if (OUT/'curation_spec.json').exists() or DB.exists():raise FileExistsError('Never overwrite existing curation.')
    assert sha(MAIN)=='5c66e914bdbf0c7c06f54a595f6df446e2152df96668986575d61a77221762ef'
    assert sha(SI)=='f899868a448bf62b1dd8bd0703e71c71addec37cbcb745ccd6ff1eb3e728fb5d'
    root=E.parse(MAIN).getroot();tables=[]
    with closing(ro(ROOT/'全库复检与特征补提取_20261021/full_corpus_search_native.sqlite')) as corpus:
        rawmap={r[1]:r[0] for r in corpus.execute('select table_id,locator from raw_tables_v11 where source_sha256=?',(sha(MAIN),))}
    for t in root.findall('.//table-wrap'):
        ident=t.get('id');tables.append(dict(id=ident,document='PalmKernel',kind='own_xml_table',caption=text(t.find('caption')),locator='XML table-wrap '+ident,raw_table_id=rawmap['XML table-wrap '+ident],grid=xml_grid(t)))
    import pypdfium2 as pdf
    d=pdf.PdfDocument(SI);pages=[p.get_textpage().get_text_range() for p in d]
    lines=lambda s:[' '.join(x.split()) for x in s.splitlines() if x.strip()]
    s1=[];sample=None;ordinal=0
    for line in lines(pages[2]):
        m=re.match(r'^(PK700N?|PZ700N?)(?:\s+(.*))?$',line)
        if m:sample=m[1];ordinal=0;line=m[2] or ''
        vals=line.split()
        if vals and all(re.fullmatch(NUM,x) for x in vals) and len(vals) in [3,5,7]:
            assert sample is not None;ordinal+=1;s1.append(dict(cells=[sample]+vals+['']*(7-len(vals)),sample=sample,source_row=f'PDFp3 {sample} peakrow{ordinal}',page=3))
    assert len(s1)==24 and sum(len([v for v in r['cells'][1:] if v]) for r in s1)==150
    tables.append(dict(id='SI_S1',document='PalmKernel_SI',kind='own_SI_table',caption='Own XPS binding energies, envelope percentages and printed C1s FWHM',locator='PDF physicalp3 TableS1',raw_table_id=None,header=['sample','C1s_eV','C1s_envelope_pct','C1s_FWHM_unit_not_printed','O1s_eV','O1s_envelope_pct','N1s_eV','N1s_envelope_pct'],rows=s1))
    s2=[]
    part=pages[3].split('Table S2.')[1].split('Table S3.')[0]
    pattern=re.compile(r'^(.*?)\s+('+NUM+r')\s+('+NUM+r')(?:\s+(.*?)\s+('+NUM+r')\s+('+NUM+r'))?$')
    for i,line in enumerate(lines(part)):
        if not line.startswith(('P7-','P8-')):continue
        m=pattern.fullmatch(line);assert m,line
        for side,fields in [('left',m.groups()[:3]),('right',m.groups()[3:])]:
            if fields[0] is not None:s2.append(dict(cells=list(fields),sample='PK700N' if 'N' in fields[0] else 'PK700',system='2E_symmetric_Swagelok',source_row=f'PDFp4 line{i} {side}',page=4))
    assert len(s2)==17
    tables.append(dict(id='SI_S2',document='PalmKernel_SI',kind='own_SI_table',caption='Own individual PK700/PK700N Swagelok EIS',locator='PDF physicalp4 TableS2',raw_table_id=None,header=['printed_electrode_id','Cmax_F_g','ESR_ohm'],rows=s2))
    s3=[]
    for line in lines(pages[3].split('Table S3.')[1].split('Table S4.')[0]):
        vals=line.split()
        if not vals or not (vals[0]=='RC' or vals[0].startswith('PK700')):continue
        assert len(vals)==5 and all(re.fullmatch(NUM,x) for x in vals[1:]),line
        s3.append(dict(cells=vals,sample='reference_commercial_RC' if vals[0]=='RC' else ('PK700N' if vals[0].startswith('PK700N') else 'PK700'),system='2E_symmetric_coin' if vals[0]!='RC' else 'commercial_reference_unknown_composition',source_row='PDFp4 TableS3 '+vals[0],page=4))
    assert len(s3)==27
    tables.append(dict(id='SI_S3',document='PalmKernel_SI',kind='own_SI_table',caption='Individual coin EIS including separately labelled commercial reference',locator='PDF physicalp4 TableS3',raw_table_id=None,header=['printed_coin_id','CEIS_F_g','ESR_ohm','Cprime_F','Cdoubleprime_F'],rows=s3))
    s4=[]
    for page,part in [(4,pages[3].split('Table S4.')[1]),(5,pages[4].split('Figure S5.')[0])]:
        for line in lines(part):
            if not line.startswith(('P1 ','PZ700 ','Pcoin')):continue
            vals=line.rsplit(' ',2);assert len(vals)==3 and all(re.fullmatch(NUM,x) for x in vals[1:]),line
            s4.append(dict(cells=vals,sample='PZ700N' if 'mod' in vals[0] else 'PZ700',system='2E_symmetric_coin' if vals[0].startswith('Pcoin') else '2E_symmetric_Swagelok',source_row=f'PDFp{page} TableS4 '+vals[0],page=page,repeat_measurement='e1 rep' in vals[0]))
    assert len(s4)==19
    tables.append(dict(id='SI_S4',document='PalmKernel_SI',kind='own_SI_table',caption='Own ZnCl2-derived electrode and coin EIS; e1 rep explicitly repeated',locator='PDF physicalp4-5 TableS4',raw_table_id=None,header=['printed_device_id','Cmax_F_g','ESR_ohm'],rows=s4))
    s5=[];coin=None
    for page in range(6,9):
        for line in lines(pages[page-1]):
            vals=line.split()
            if len(vals) not in [10,11] or not all(re.fullmatch(NUM,x) for x in vals[-10:]):continue
            printed_coin=len(vals)==11
            if printed_coin:assert re.fullmatch(r'\d+N?',vals[0]);coin=vals.pop(0)
            assert coin is not None
            s5.append(dict(cells=[coin]+vals,sample='PK700N' if coin.endswith('N') else 'PK700',system='2E_symmetric_coin',source_row=f'PDFp{page} TableS5 coin{coin} row{len(s5)+1}',page=page,coin_id_inherited_from_merged_or_continued_group=not printed_coin))
    groups={r['cells'][0] for r in s5}
    assert len(s5)==132 and len(groups)==22 and all(sum(r['cells'][0]==g for r in s5)==6 for g in groups)
    tables.append(dict(id='SI_S5',document='PalmKernel_SI',kind='own_SI_table',caption='Own individual coin electrical results at20s; cross-page group labels explicitly carried',locator='PDF physicalp6-8 TableS5',raw_table_id=None,header=['printed_coin_id','EV_V','I_A','Rint_ohm','Echarge_Ws','Edischarge_Ws','energy_efficiency_pct','Cu_F','Ci_F','specific_energy_Wh_kg','specific_power_W_kg'],rows=s5))
    write(OUT/'curation_spec.json',dict(source_main_sha256=sha(MAIN),source_SI_sha256=sha(SI),header_policy='XML span expansion retains original origin cell. SI normalized from visually checked physicalp3-8; two-side and multi-page tables keep printed IDs and explicit inherited group metadata. SI Eexp/Pexp units bound by ownmainTable5 andp35, not printed inSIheader.',tables=tables))
    print(json.dumps(dict(main_tables=7,SI_tables=5,XPS_peak_numbers=150,EIS_individual_reports=len(s2)+len(s3)+len(s4),electrical_rows=len(s5),physical_coins=len(groups)),ensure_ascii=False))

def build():
    if DB.exists() or (OUT/'merge_manifest.json').exists():raise FileExistsError('Do not overwrite a draft/release.')
    assert sha(PARENT)==PARENT_SHA
    spec=json.loads((OUT/'curation_spec.json').read_text('utf8'));root=E.parse(MAIN).getroot();ps=root.findall('.//body//p')
    assert sha(MAIN)==spec['source_main_sha256'] and sha(SI)==spec['source_SI_sha256']
    docs={'PalmKernel':MAIN,'PalmKernel_SI':SI,'PalmKernel_Fig1':BASE/'assets/nanomaterials-16-00260-g001.jpg','PalmKernel_Fig11':BASE/'assets/nanomaterials-16-00260-g011.jpg'}
    receipt=[]
    with closing(ro(PARENT)) as parent,closing(sqlite3.connect(DB)) as c:
        parent.backup(c);c.row_factory=sqlite3.Row;c.execute('pragma foreign_keys=on')
        c.executescript('''
          create table transcription_origins_v7(table_key text references reviewed_tables,row_ordinal integer,origin_json text,primary key(table_key,row_ordinal));
          create table device_bindings_v7(printed_id text,table_key text references reviewed_tables,material_key text references materials,device_json text,primary key(printed_id,table_key));
          create table extraction_metrics_v7(record_id text primary key,table_key text,metric text,record_kind text,material_key text);
          create index response_lookup_v7 on extraction_metrics_v7(record_kind,metric,material_key);
        ''')
        assert not c.execute('select 1 from reviewed_sources where doi=?',(DOI,)).fetchone()
        insert(c,'reviewed_sources',dict(doi=DOI,path=MAIN.relative_to(ROOT).as_posix(),sha256=sha(MAIN),title=text(root.find('.//article-title')),stage='Own main7tables andSI5tables; remaining curves not fully digitized'))
        for label,p in docs.items():insert(c,'source_documents',dict(document_key=label,doi=DOI,path=p.relative_to(ROOT).as_posix(),sha256=sha(p),role='own_SI' if label.endswith('_SI') else 'primary_xml' if label=='PalmKernel' else 'original_graphic'))
        for sample,stage in [('raw_PKS','raw_palm_kernel_shell_before_activation'),('PK700','final_biomass_carbon_before_test'),('PK700N','final_biomass_carbon_before_test'),('PZ700','final_biomass_carbon_before_test'),('PZ700N','final_biomass_carbon_before_test'),('reference_commercial_RC','commercial_control_unknown_composition_not_biomass')]:insert(c,'materials',dict(material_key=mk(sample),doi=DOI,sample_name=sample,material_stage=stage))
        units={}
        def table(ident,caption,header,rows,doc,loc,kind,raw_id=None,origins=None):
            key=DOI+'#'+ident
            insert(c,'reviewed_tables',dict(table_key=key,doi=DOI,xml_id=ident,caption=caption,header_json=json.dumps(header,ensure_ascii=False),footnote='Source-qualified rows; original XML span origins/SI printed group IDs retained. Aggregates, replicas, configurations and units are separate.',source_raw_table_id=raw_id))
            insert(c,'table_source_links',dict(table_key=key,document_key=doc,locator=loc))
            insert(c,'extraction_units_v3',dict(table_key=key,kind=kind,scope='Declared own numerical cells; controls labelled separately; not whole-article completion.'))
            for i,row in enumerate(rows,1):
                insert(c,'transcribed_rows',dict(table_key=key,row_ordinal=i,cells_json=json.dumps(row,ensure_ascii=False)))
                if origins:insert(c,'transcription_origins_v7',dict(table_key=key,row_ordinal=i,origin_json=json.dumps(origins[i-1],ensure_ascii=False)))
            if raw_id:c.execute('update raw_table_queue set review_state=? where table_id=?',('v7_own_main_table_cells_reviewed_configurations_and_statistical_grains_separate',raw_id))
            receipt.append(dict(table_key=key,kind=kind,source_document=doc,locator=loc,rows=len(rows),raw_table_id=raw_id));return key
        for t in spec['tables']:
            rows=[[cell['raw'] for cell in r] for r in t['grid']] if 'grid' in t else [r['cells'] for r in t['rows']]
            origins=t.get('grid',t.get('rows'));header=rows[0] if 'grid' in t else t['header']
            key=table(t['id'],t['caption'],header,rows,t['document'],t['locator'],t['kind'],t['raw_table_id'],origins)
            units[t['id'].split('-')[-1]]=(key,rows,t)
        def fact(sample,key,i,col,field,unit,method):
            row=json.loads(c.execute('select cells_json from transcribed_rows where table_key=? and row_ordinal=?',(key,i)).fetchone()[0]);raw=row[col];value=number(raw);assert value is not None
            doc=c.execute('select document_key from table_source_links where table_key=?',(key,)).fetchone()[0]
            cur=insert(c,'material_facts',dict(material_key=mk(sample),field_name=field,value=value,raw_value=raw,unit=unit,method=method,table_key=key,row_ordinal=i,column_ordinal=col,source_sha256=sha(docs[doc]),review_status='own_reported_method_and_stage_qualified_not_automatic_training_admission',training_eligible=0))
            insert(c,'extraction_metrics_v7',dict(record_id='fact:'+str(cur.lastrowid),table_key=key,metric=field,record_kind='material_fact',material_key=mk(sample)))
        key,rows,_=units['t001']
        rawfields=[('precursor_fixed_carbon_wt_pct','wt%'),('precursor_volatile_matter_wt_pct','wt%'),('precursor_ash_wt_pct','wt%'),('precursor_moisture_wt_pct','wt%'),('precursor_sulfur_wt_pct','wt%'),('precursor_HHV_kJ_kg','kJ/kg'),('precursor_Klason_lignin_pct','%')]
        for i,(field,unit) in enumerate(rawfields,2):fact('raw_PKS',key,i,1,field,unit,'Own precursor Table1; '+rows[i-1][2]+'; HHV comma explicitly thousands, not decimal')
        key,rows,_=units['t002']
        fields=[('BET_surface_area_m2_g','m2/g','BET'),('micropore_volume_cm3_g','cm3/g','Dubinin-Radushkevich'),('DR_micropore_size_nm','nm','Dubinin-Radushkevich mean, not PSDpeak'),('total_pore_volume_cm3_g','cm3/g','adsorbed volume at relative pressure0.98'),('mesopore_volume_cm3_g','cm3/g','Gurvich difference V0.98−DR micropore volume'),('XPS_C_wt_pct','wt%','XPS author explicitly weight%, not atomic%'),('XPS_O_wt_pct','wt%','XPS author explicitly weight%, not atomic%'),('XPS_N_wt_pct','wt%','XPS author explicitly weight%, not atomic%')]
        for i,row in enumerate(rows[2:],3):
            for col,(field,unit,method) in enumerate(fields,1):fact(row[0],key,i,col,field,unit,method)
        key,rows,t=units['SI_S1'];ordinals={}
        for i,row in enumerate(rows,1):
            sample=row[0];ordinals[sample]=ordinals.get(sample,0)+1;n=ordinals[sample]
            for col in range(1,8):
                if not row[col]:continue
                axis='C1s' if col<=3 else 'O1s' if col<=5 else 'N1s'
                metric='binding_energy_eV' if col in [1,4,6] else 'envelope_pct' if col in [2,5,7] else 'reported_FWHM'
                unit='eV' if 'energy' in metric else 'envelope%' if 'pct' in metric else 'unit_not_printed_in_table'
                fact(sample,key,i,col,f'XPS_{axis}_peak{n}_{metric}',unit,'Own SI peak row; envelope proportions not total atomic/weight%; no chemical-species assignment from position alone')
        peakrows=[['PK700','0.59'],['PZ700','0.5'],['PK700N','1.0'],['PZ700N','1.2']]
        key=table('own_PSD_p41','Own reported primary PSD peaks',['sample','peak_nm'],peakrows,'PalmKernel','XML body//p41','own_numeric_prose')
        for i,r in enumerate(peakrows,1):fact(r[0],key,i,1,'reported_primary_PSD_peak_nm','nm','Author PSD primary peak; not DR mean and not universal average pore size')
        for sample in ['PK700','PK700N','PZ700','PZ700N']:
            stages=[dict(stage='biomass_milling',particle_size_range_mm=[1,2],phase='bulk_material_preparation'),dict(stage='impregnation',agent='KOH' if sample.startswith('PK') else 'ZnCl2',agent_solution_mol_L=6 if sample.startswith('PK') else 1,agent_to_biomass_mass_ratio=2 if sample.startswith('PK') else 1,ratio_basis='OwnFig1wt:wt feed mixture; precursor biomass, not resulting carbon',temperature_C=25,duration_h=4,stirring_rpm=400),dict(stage='drying',temperature_C=105,duration_h=12),dict(stage='chemical_activation',temperature_C=700,duration_h=1,heating_rate_C_min=5,atmosphere='N2',flow_mL_min=100,duration_evidence='OwnFig1 explicitly1h; bodyp10 does not give hold duration'),dict(stage='washing',reagent='HCl',concentration_mol_L=.1,duration_h=1,final_pH='neutral'),dict(stage='post_activation_drying',temperature_C=105,duration_h=12)]
            if sample.endswith('N'):stages+=[dict(stage='nitric_acid_surface_modification',reagent='HNO3',reported_solution_pct=None,competing_solution_pct=[30,65],conflict='bodyp10 says30%; ownFig1 says65%; unresolved, not chosen by performance',reported_impregnation_ratio='1:1',ratio_basis='author unspecified',duration_h=4,temperature_C=25,stirring_rpm=400),dict(stage='drying',temperature_C=105,duration_h=12)]
            stages.append(dict(stage='electrode_preparation',phase='electrode_preparation_not_bulk_carbon_synthesis',carbon_wt_pct=80,acetylene_black_wt_pct=10,PTFE_wt_pct=10,paste_portion_mg_reported=7,paste_portion_scope='author portion; do not infer current-mass denominator',disk_diameter_mm=12,soak_electrolyte='H2SO4',soak_concentration_mol_L=1,soak_duration_days=5,press_force_raw='2 USTonb',source='ownbodyp14'))
            insert(c,'synthesis_stages_v3',dict(material_key=mk(sample),document_key='PalmKernel',locator='XML body//p10 and originalFigure1; HNO3 concentration conflict explicitly retained',stages_json=json.dumps(stages,ensure_ascii=False)))
        def index(ident,key,metric,kind,material=None):insert(c,'extraction_metrics_v7',dict(record_id=ident,table_key=key,metric=metric,record_kind=kind,material_key=material))
        def cap(key,i,col,sample,method,system,context):
            raw=json.loads(c.execute('select cells_json from transcribed_rows where table_key=? and row_ordinal=?',(key,i)).fetchone()[0])[col];value,unc=measurement(raw);ident=key+'#'+str(i)+'#'+str(col)
            conditions=dict(context,reported_uncertainty=unc,extraction_batch='v7',aggregate_and_individual_same_source_not_independent=True)
            insert(c,'capacitance_observations',dict(observation_id=ident,material_key=mk(sample),table_key=key,row_ordinal=i,column_ordinal=col,value=value,raw_value=raw,unit='F/g',method=method,system=system,electrolyte='H2SO4' if sample!='reference_commercial_RC' else 'reference_not_bound',concentration_mol_L=1 if sample!='reference_commercial_RC' else None,current_A_g=context.get('reported_current_A_g'),scan_rate_mV_s=None,conditions_json=json.dumps(conditions,ensure_ascii=False),status='own_'+context['statistical_grain']+'_typed_not_shared_training_admission',source_group='doi:'+DOI,training_eligible=0));index(ident,key,'capacitance_F_g','capacitance',mk(sample))
        def response(key,i,col,metric,unit,context,sample=None):
            raw=json.loads(c.execute('select cells_json from transcribed_rows where table_key=? and row_ordinal=?',(key,i)).fetchone()[0])[col];value,unc=measurement(raw);ident=key+'#'+str(i)+'#'+str(col)
            record=dict(context,metric=metric,value=value,reported_uncertainty=unc,raw_value=raw,unit=unit,row_ordinal=i,column_ordinal=col,source_group='doi:'+DOI,feature_role='test_response_not_pretest_material_predictor',extraction_batch='v7')
            insert(c,'outcome_observations_v3',dict(outcome_id=ident,material_key=mk(sample) if sample else None,table_key=key,record_json=json.dumps(record,ensure_ascii=False),training_eligible=0));index(ident,key,metric,context['response_family'],mk(sample) if sample else None)
        commonEIS=dict(frequency_Hz=.001,sinusoidal_reported_amplitude='±10mV',DC_bias_V=None,capacitance_basis='authorEIS totalactive mass; ownEq3/p19states5.6mg both electrodes; not GCD2m formula',reported_active_mass_mg=5.6,uncertainty_type='95% confidence interval from mainp28-29 and tablecaption; separate S is sample standard deviation')
        for short,system in [('t003','2E_symmetric_Swagelok'),('t004','2E_symmetric_coin')]:
            key,rows,_=units[short]
            for i,row in enumerate(rows[1:],2):
                sample=row[0].removesuffix('coin');ctx=dict(commonEIS,statistical_grain='aggregate_mean',reported_sample_SD_F_g=float(row[2]),physical_test_group=DOI+'#'+sample+'#'+system,response_family='EIS')
                cap(key,i,1,sample,'EIS',system,ctx)
                response(key,i,3,'EIS_ESR_ohm','ohm',dict(ctx,reported_sample_SD_ohm=float(row[4])),sample)
                if short=='t003':response(key,i,5,'EIS_interfacial_capacitance_microF_cm2','microF/cm2',dict(ctx,derived_from='Cmax/BET; not independent material measurement'),sample)
        for short in ['SI_S2','SI_S3','SI_S4']:
            key,rows,t=units[short]
            for i,(row,binding) in enumerate(zip(rows,t['rows']),1):
                sample=binding['sample'];ctx=dict(commonEIS,statistical_grain='individual_device' if sample!='reference_commercial_RC' else 'commercial_reference',printed_device_id=row[0],physical_test_group=DOI+'#'+row[0],repeat_measurement=binding.get('repeat_measurement',False),response_family='EIS')
                if sample=='reference_commercial_RC':ctx.update(reported_active_mass_mg=None,capacitance_basis='commercial_control_author_report_not_bound_to_biomass_mass')
                insert(c,'device_bindings_v7',dict(printed_id=row[0],table_key=key,material_key=mk(sample),device_json=json.dumps(binding,ensure_ascii=False)))
                cap(key,i,1,sample,'EIS',binding['system'],ctx);response(key,i,2,'EIS_ESR_ohm','ohm',ctx,sample)
                if short=='SI_S3':
                    response(key,i,3,'EIS_Cprime_F','F',ctx,sample);response(key,i,4,'EIS_Cdoubleprime_F','F',ctx,sample)
        key=table('own_GCD_p72','Own prose GCD endpoint values, with explicit author2m normalization',['sample','capacitance_F_g'],[['PK700','40'],['PK700N','34']],'PalmKernel','XML body//p72 and Eq1/bodyp16-17','own_numeric_prose')
        for i,sample in enumerate(['PK700','PK700N'],1):cap(key,i,1,sample,'GCD','2E_symmetric_Swagelok',dict(statistical_grain='prose_point',reported_current_A_g=.125,voltage_lower_V=0,voltage_upper_V=.75,current_mass_basis='author_reported_unknown_not_inferred_from_capacitance_formula',capacitance_basis='author_I_dt_over_2m_dV; m wording not physically unified with other studies',formula='Ccp=I*dt/(2*m*dV)',source_purpose='separate_author2m_report; not ordinary device-total-mass or authornumeratorfactor2 target'))
        key,rows,_=units['t005'];metrics=[('internal_resistance_ohm','ohm'),('energy_efficiency_pct','%'),('experimental_capacitance_F','F'),('ideal_capacitance_F','F'),('specific_energy_Wh_kg','Wh/kg'),('specific_power_W_kg','W/kg')]
        for i,row in enumerate(rows[1:],2):
            ctx=dict(response_family='electrical',assembly='individual_coin',voltage_limit_per_coin_V=float(row[1]),current_A=float(row[2]),duration_s=20,statistical_grain='aggregate_mean',uncertainty_type='95% confidence interval; ownmainp28-29')
            for col,(metric,unit) in enumerate(metrics,3):response(key,i,col,metric,unit,ctx,row[0])
        key,rows,_=units['t006'];pair=None
        metrics=[('first_coin_capacitance_F','F'),('first_coin_energy_efficiency_pct','%'),('second_coin_capacitance_F','F'),('second_coin_energy_efficiency_pct','%'),('theoretical_capacitance_F','F'),('internal_resistance_ohm','ohm'),('energy_efficiency_pct','%'),('experimental_capacitance_F','F'),('ideal_capacitance_F','F'),('stack_voltage_V','V'),('capacitance_error_pct','%'),('specific_energy_Wh_kg','Wh/kg'),('specific_power_W_kg','W/kg')]
        for i,row in enumerate(rows,1):
            if len(set(row))==1 and row[0] in ['27–28','29–30']:pair=row[0];continue
            if number(row[0]) is None:continue
            assert pair
            ctx=dict(response_family='electrical',assembly='2S',printed_coin_pair=pair,voltage_limit_per_coin_V=float(row[0]),current_A=float(row[1]),duration_s=20,statistical_grain='single_stack_report',component_coins=[int(x) for x in pair.split('–')],not_replicates_of_material_electrochemistry=True)
            for col,(metric,unit) in enumerate(metrics,2):response(key,i,col,metric,unit,ctx)
        key,rows,_=units['t007'];metrics=[('internal_resistance_ohm','ohm'),('energy_efficiency_pct','%'),('theoretical_capacitance_F','F'),('experimental_capacitance_F','F'),('ideal_capacitance_F','F'),('capacitance_error_pct','%'),('stack_voltage_V','V'),('specific_energy_Wh_kg','Wh/kg'),('specific_power_W_kg','W/kg')]
        for i,row in enumerate(rows[2:],3):
            ctx=dict(response_family='electrical',assembly=row[0],voltage_limit_per_coin_V=float(row[1]),current_A=float(row[2]),duration_s=20,statistical_grain='single_stack_report',component_coins=[17,21,23,24,25,26,29,30] if row[0]=='8S' else [40,41,43,44,46,47,48,49],material_composition='Do not infer all-stack composition from nearby best sample; each coin identity retained')
            for col,(metric,unit) in enumerate(metrics,3):response(key,i,col,metric,unit,ctx)
        key,rows,t=units['SI_S5'];metrics=[('internal_resistance_ohm','ohm'),('charge_energy_Ws','W*s'),('discharge_energy_Ws','W*s'),('energy_efficiency_pct','%'),('experimental_capacitance_F','F'),('ideal_capacitance_F','F'),('specific_energy_Wh_kg','Wh/kg'),('specific_power_W_kg','W/kg')]
        for i,(row,binding) in enumerate(zip(rows,t['rows']),1):
            ctx=dict(response_family='electrical',assembly='individual_coin',printed_coin_id=row[0],voltage_limit_per_coin_V=float(row[1]),current_A=float(row[2]),duration_s=20,statistical_grain='individual_device_condition',physical_test_group=DOI+'#coin'+row[0],unit_binding='SIheader Ws/F; Eexp/Pexpunits from ownmainTable5/bodyp35; not estimated from performance',coin_id_inherited=binding['coin_id_inherited_from_merged_or_continued_group'])
            for col,(metric,unit) in enumerate(metrics,3):response(key,i,col,metric,unit,ctx,binding['sample'])
        key=table('own_stack_cycling_p36_p63','Own 2S stack cycling report; planned and reported cycles distinct',['sample','retention_pct','reported_endpoint_cycles','method_cycles'],[['PK700_stack25_26','57','2100','10000']],'PalmKernel','XML body//p36,p63 + actualFigure11','own_numeric_prose')
        candidate=dict(system='two_coin_cells_in_series_stack_not_single_EDLC',method='GCD',electrolyte='H2SO4',concentration_mol_L=1,reported_current_A_g=.125,current_mass_basis='author_reported_unknown',cycle_count=2100,retention_pct=57,reported_method_cycle_count=10000,figure_a_last_cycle_label=2400,curve_voltage_lower_V=-1,curve_voltage_upper_V=1,baseline_index=None,initial_reference='author retention reference, exact normalization not specified',material='PK700 via ownSIcoin25/26 labels',training_admission=False,reason='Stack topology distinct from ordinary single-cell2E purpose; method/report/figure cycle roles preserved',evidence_source_path=MAIN.relative_to(ROOT).as_posix(),source_sha256=sha(MAIN),locator='bodyp36/p63; Figure11a-c; SI TableS3 coins25/26')
        insert(c,'test_candidates',dict(candidate_id='LP7_PK_stack25_26_C2100',material_key=mk('PK700'),record_json=json.dumps(candidate,ensure_ascii=False),training_eligible=0))
        for label,doc,record in [('PalmKernel_synthesis','PalmKernel_Fig1',dict(temperature_C=700,duration_h=1,source_only_duration=True,HNO3_figure_pct=65,HNO3_body_pct=30,HNO3_selected_pct=None)),('PalmKernel_stack_cycling','PalmKernel_Fig11',candidate)]:insert(c,'figure_protocol_reviews_v6',dict(review_id=label,document_key=doc,record_json=json.dumps(record,ensure_ascii=False)))
        issues=[('HNO3','nitric_acid_concentration_conflict','PK700N/PZ700N','正文30%与实际制备图65%并存；浓度不择值，温度/时间/700℃1h有自身证据可分别提取。'),('GCDbasis','author_2m_capacitance_normalization','PK700/PK700N','原Eq1为IΔt/(2mΔV)，m文字与其它文献不能直接统一；不按EIS的质量或电容公式推断电流分母。两自身GCD点按独立作者2m口径保存。'),('SIcount','aggregate_vs_listed_replica_count','PK700/PK700N','S3实际19个PK700、7个PK700N，脚注却18和8；主表均值/SD与列出个体逐项对账，保留原报告，不默认为独立重复或改写均值。'),('coin44','EIS_capacitance_vs_Cprime_mass_relation','PK700coin44','S3的CEIS57 F/g、C′0.096 F并存，按其它行常用5.6mg不能重现；不替换原值或猜漏位数。'),('PZrep','repeat_measurement_not_new_electrode','PZ700N','S4的e1和e1 rep是两个测量报告、同一标识的重复；保留两值与关系，不当两个独立电极。'),('stackcycles','stack_topology_and_cycle_roles','PK700','方法计划10000圈、57%结果2100圈、Figure11a还标C2400；原图电位为−1～1V。按各自角色保留，不改成普通单器件0～1V10000圈。'),('power','stack_power_prose_units_and_values','8P','自身Table7在0.001A/0.75V为2.6Wh/kg、475W/kg；后文有521Wh/kg等竞争表述，不把它改写成新增高性能点。'),('rate','rate_retention_not_lifetime','all','Figure6与Eq2比较不同电流相对0.125A/g的倍率保持率，不能当作10000圈的循环标签；方法1A/g上限与结果2A/g范围分别保存。')]
        for name,kind,sample,action in issues:insert(c,'scientific_issues',dict(issue_id='LP7_PK_'+name,doi=DOI,sample_name=sample,issue_json=json.dumps(dict(kind=kind,action=action),ensure_ascii=False)))
        wood=ROOT/'数据补充_v07_20261018/sources/PMC12444587/assets/ao5c05285_0006.jpg'
        insert(c,'scientific_issues',dict(issue_id='LP7_WoodApple_cycle_figure_checked',doi='10.1021/acsomega.5c05285',sample_name='WAS',issue_json=json.dumps(dict(kind='cycle_current_figure_searched_no_numeric_label',action='已读实际Figure6f原图：只有2/4/6M、10000圈及96.07/96.8/95.16%，未印数值电流；仍不借倍率2A/g补填。',path=wood.relative_to(ROOT).as_posix(),sha256=sha(wood)),ensure_ascii=False)))
        c.commit()
    protected=[PARENT,MAIN,SI,BASE/'assets/nanomaterials-16-00260-s001.zip',BASE/'primary_assets.zip',wood]+list(docs.values())
    write(OUT/'protected_inputs.json',dict(files=[dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p)) for p in dict.fromkeys(protected)],parent_pointer=json.loads((ROOT/'data/current_literature.json').read_text('utf8')),dependency_policy='Pin immutable artifacts; future global pointers may advance.'))
    write(OUT/'table_review_receipt.json',receipt)
    print('Built unsealed v7; all7main/5SI tables with separate grain; no fit.')

def verify(write_reports=False):
    checks=[]
    def check(name,ok):
        if not ok:raise AssertionError(name)
        checks.append(name)
    protection=json.loads((OUT/'protected_inputs.json').read_text('utf8'))
    for p in protection['files']:check('protected_'+p['path'],sha(ROOT/p['path'])==p['sha256'])
    # Historical releases remain immutable, while current pointers may legitimately advance.
    parent_manifest=PARENT.parent/'merge_manifest.json'
    for p in json.loads(parent_manifest.read_text('utf8'))['outputs']:check('parent_payload_'+p['path'],sha(ROOT/p['path'])==p['sha256'])
    digest=sha(DB);spec=json.loads((OUT/'curation_spec.json').read_text('utf8'));original=E.parse(MAIN).getroot()
    with closing(ro(DB)) as c,closing(ro(PARENT)) as old:
        c.row_factory=sqlite3.Row
        check('sqlite_integrity',c.execute('pragma integrity_check').fetchone()[0]=='ok');check('foreign_keys',not c.execute('pragma foreign_key_check').fetchall())
        for (name,) in old.execute("select name from sqlite_master where type='table' and name not like 'sqlite_%'"):
            if name=='raw_table_queue':continue
            current={tuple(r) for r in c.execute('select * from '+name)};check('parent_'+name,all(tuple(r) in current for r in old.execute('select * from '+name)))
        oldq={r[0]:tuple(r) for r in old.execute('select * from raw_table_queue')};now=[tuple(r) for r in c.execute('select * from raw_table_queue')]
        expected_ids={t['raw_table_id'] for t in spec['tables'] if t['raw_table_id']}
        check('queue_only7_declared_status_changes',{r[0] for r in now if r!=oldq[r[0]]}==expected_ids and len(expected_ids)==7 and all(r[:6]==oldq[r[0]][:6] and r[7:]==oldq[r[0]][7:] for r in now))
        for t in spec['tables']:
            key=DOI+'#'+t['id'];stored=[json.loads(r[0]) for r in c.execute('select cells_json from transcribed_rows where table_key=? order by row_ordinal',(key,))]
            if 'grid' in t:
                native=xml_grid(original.find(".//table-wrap[@id='"+t['id']+"']"));check('XML_original_spans_'+t['id'],native==t['grid']);expected=[[v['raw'] for v in row] for row in native]
            else:expected=[r['cells'] for r in t['rows']]
            check('transcription_'+t['id'],stored==expected)
        for f in c.execute("select f.* from material_facts f join extraction_metrics_v7 x on x.record_id='fact:'||f.fact_id"):
            cells=json.loads(c.execute('select cells_json from transcribed_rows where table_key=? and row_ordinal=?',(f['table_key'],f['row_ordinal'])).fetchone()[0]);check('raw_fact_'+str(f['fact_id']),cells[f['column_ordinal']]==f['raw_value']);check('value_fact_'+str(f['fact_id']),number(f['raw_value'])==f['value'])
        for t in ['material_facts','capacitance_observations','outcome_observations_v3','test_candidates','raw_table_queue']:check('raw_training_flag0_'+t,c.execute('select count(*) from '+t+' where training_eligible!=0 or training_eligible is null').fetchone()[0]==0)
        count=lambda name:c.execute('select count(*) from '+name).fetchone()[0]
        actual=c.execute("select count(*) from reviewed_tables t left join extraction_units_v3 u using(table_key) where u.kind is null or u.kind in ('own_xml_table','own_SI_table','own_and_comparison_pdf_table','mixed_comparison_table')").fetchone()[0]
        check('75_actual_tables',actual==75)
        summary=dict(identity_catalogue_entries=480,raw_table_candidates=959,raw_table_rows=6121,cumulative_reviewed_source_publications=count('reviewed_sources'),cumulative_materials=count('materials'),cumulative_selected_material_cells=count('material_facts'),cumulative_numeric_material_facts=c.execute('select count(*) from material_facts where value is not null').fetchone()[0],new_materials=count('materials')-86,new_numeric_material_facts=c.execute('select count(*) from material_facts where value is not null').fetchone()[0]-862,reviewed_table_units=actual,reviewed_evidence_units=count('reviewed_tables')+count('figure_protocol_reviews_v6'),raw_candidates_touched=959-c.execute("select count(*) from raw_table_queue where review_state='automatic_candidate_unreviewed'").fetchone()[0],raw_candidates_untouched=c.execute("select count(*) from raw_table_queue where review_state='automatic_candidate_unreviewed'").fetchone()[0],capacitance_records=count('capacitance_observations'),numeric_capacitance_values=c.execute('select count(*) from capacitance_observations where value is not null').fetchone()[0],unreported_capacitance_cells=2,cycling_candidates=count('test_candidates'),scientific_issues=count('scientific_issues'),historical_selected_fact_references=725,historical_fact_references_with_same_source_table_candidates=171,synthesis_materials=count('synthesis_stages_v3'),response_outcomes=count('outcome_observations_v3'),new_Palm_response_records=c.execute("select count(*) from extraction_metrics_v7 where record_kind in ('EIS','electrical')").fetchone()[0],new_Palm_EIS_individual_capacitance_reports=63,new_Palm_mean_EIS_reports=8,new_Palm_GCD_author2m_reports=2,new_Palm_individual_electrical_conditions=132,new_Palm_individual_electrical_coins=22,auxiliary_aqueous_3e_GCD_rows=103,auxiliary_aqueous_2e_GCD_rows=5,auxiliary_native_mineral_3e_GCD_rows=5,auxiliary_author_factor2_2e_GCD_rows=6,auxiliary_independent_DOI_groups=8,auxiliary_purpose_reviewed_input_rows=119,DES_purpose_reviewed_rows_per_target=12,DES_purpose_reviews=24,DES_independent_DOI_groups=1,new_training_admissions=0,formal_cycling_admissions=0,model_fits=0,all_literature_fully_utilized=False,scope_note='7main+5SI own tables; material peak descriptors, aggregate/individual EIS, 20s electrical outcomes and 2S cycle candidate are separate. Curves not fully digitized. New193cells are not193independent samples; originalfixed38 remain.')
        check('193_new_material_values',summary['new_numeric_material_facts']==193);check('73_new_capacitance_reports',summary['capacitance_records']-295==73);check('1485_new_response_reports',summary['new_Palm_response_records']==1485)
    from data.literature_v7 import open_literature_database as new_api
    from data.literature_v6 import open_literature_database as old_api
    from data.literature_v4 import PROFILES
    with new_api(DB,digest) as new,old_api(PARENT,PARENT_SHA) as old:
        for profile in PROFILES:check('aux_unchanged_'+profile,new.auxiliary_feature_rows(profile)==old.auxiliary_feature_rows(profile))
        for target in ['capacitance','retention']:check('DES_unchanged_'+target,new.des_reported_inputs(target)==old.des_reported_inputs(target))
        caps=new.palm_capacitances();check('cap_count73',len(caps)==73);check('EIS_not_GCD',len(new.palm_capacitances('EIS'))==71 and len(new.palm_capacitances('GCD'))==2)
        for r in caps:
            mean,unc=measurement(r['raw_value']);check('cap_raw_'+r['observation_id'],r['value']==mean and r['conditions']['reported_uncertainty']==unc)
            check('one_DOI_'+r['observation_id'],r['source_group']=='doi:'+DOI and r['training_eligible']==0)
            if r['method']=='GCD':check('GCD2m_not_unified_'+r['observation_id'],'2m' in r['conditions']['capacitance_basis'] and r['current_A_g']==.125 and 'unknown' in r['conditions']['current_mass_basis'])
        for r in new.palm_responses():
            record=r['record'];key=r['outcome_id'];mean,unc=measurement(record['raw_value']);check('response_numeric_'+key,record['value']==mean and record['reported_uncertainty']==unc)
            cells=json.loads(new.connection.execute('select cells_json from transcribed_rows where table_key=? and row_ordinal=?',(r['table_key'],record['row_ordinal'])).fetchone()[0]);check('response_origin_'+key,cells[record['column_ordinal']]==record['raw_value'] and bool(r['source_sha256']) and bool(r['locator']))
            check('response_role_'+key,record['feature_role']=='test_response_not_pretest_material_predictor' and math.isfinite(record['value']))
            if record['response_family']=='electrical':check('current_A_not_A_g_'+key,'current_A' in record and 'current_A_g' not in record)
        s5=[r['record'] for r in new.palm_responses('electrical',metric='experimental_capacitance_F') if '#SI_S5' in r['table_key']]
        groups={r['printed_coin_id'] for r in s5};check('SI5_22coins_132conditions',len(s5)==132 and len(groups)==22)
        expected={(v,i) for v in [.5,.75] for i in [.0001,.001,.01]}
        for g in groups:check('six_conditions_'+g,{(r['voltage_limit_per_coin_V'],r['current_A']) for r in s5 if r['printed_coin_id']==g}==expected)
        check('source_printed_zero_preserved',any(r['printed_coin_id']=='52N' and r['value']==0 and r['current_A']==.01 and r['voltage_limit_per_coin_V']==.5 for r in s5))
        audit=new.palm_statistics_audit();check('8_aggregate_audits',len(audit)==8)
        for sample,n,printed in [('PK700',19,18),('PK700N',7,8)]:check('SI3_count_conflict_'+sample,any(r['sample_name']==sample and r['system']=='2E_symmetric_coin' and r['listed_measurement_reports']==n and r['SI_footnote_n']==printed for r in audit))
        check('e1rep_preserved',any(r['sample_name']=='PZ700N' and r['system']=='2E_symmetric_Swagelok' and r['explicit_repeat_reports']==1 for r in audit))
        check('wt_not_atpct',len(new.facts(doi=DOI,field='XPS_C_wt_pct'))==4 and not new.facts(doi=DOI,field='XPS_C_at_pct'))
        check('precursor_separate',new.materials(doi=DOI,sample='raw_PKS')[0]['material_stage'].startswith('raw_'))
        check('RC_separate',new.materials(doi=DOI,sample='reference_commercial_RC')[0]['material_stage'].startswith('commercial_'))
        for sample in ['PK700N','PZ700N']:
            stage=next(s for s in new.synthesis(doi=DOI,sample=sample)[0]['stages'] if s['stage']=='nitric_acid_surface_modification');check('HNO3_frozen_'+sample,stage['reported_solution_pct'] is None and stage['competing_solution_pct']==[30,65])
        matrix=new.palm_material_matrix();check('material_matrix4_no_response',len(matrix['X'])==4 and not matrix['has_response_labels'] and not matrix['training_authorized'] and len(set(matrix['groups']))==1)
        check('matrix_HNO3_not_guessed',all(row[-1] is None for row in matrix['X']));check('matrix_missing_exact',all(m==(v is None) for row,mask in zip(matrix['X'],matrix['missing_mask']) for v,m in zip(row,mask)))
        candidate=next(r['record'] for r in new.tests() if r['candidate_id']=='LP7_PK_stack25_26_C2100');check('stack_cycles_voltage_roles',candidate['cycle_count']==2100 and candidate['reported_method_cycle_count']==10000 and candidate['curve_voltage_lower_V']==-1 and candidate['curve_voltage_upper_V']==1 and candidate['baseline_index'] is None)
        fields=['observation_id','sample_name','method','system','value','unit','current_A_g','raw_value','source_group','source_path','source_sha256','locator']
        buf=io.StringIO(newline='');w=csv.DictWriter(buf,fieldnames=fields);w.writeheader();w.writerows([{k:r[k] for k in fields} for r in caps]);export=buf.getvalue()
    check('API_readonly',sha(DB)==digest)
    report=dict(status='passed',checks=len(checks),check_names=sorted(checks),model_fits=0,scientific_goal_complete=False)
    preflight=dict(status='source_typed_and_grain_checked_not_new_shared_training_admission',material_matrix=matrix,aggregate_audit_rows=8,existing_auxiliary_rows_unchanged=119,existing_DES_rows_per_target=12,one_Palm_DOI_only=True,EIS_GCD_and_stack_targets_separate=True,ordinary_cycle_membership_unchanged=True,model_fits=0)
    for name,value in {'summary.json':summary,'verification.json':report,'palm_statistics_audit.json':audit,'palm_input_preflight.json':preflight}.items():
        if write_reports:write(OUT/name,value)
        else:assert json.loads((OUT/name).read_text('utf8'))==value,'report_'+name
    file=OUT/'palm_capacitance_reports.csv'
    if write_reports:
        with file.open('w',encoding='utf8',newline='') as f:f.write(export)
    else:
        with file.open('r',encoding='utf8',newline='') as f:assert f.read()==export
    if (OUT/'merge_manifest.json').exists():
        for p in json.loads((OUT/'merge_manifest.json').read_text('utf8'))['outputs']:assert sha(ROOT/p['path'])==p['sha256'],p['path']
    print(json.dumps(dict(status='passed',checks=report['checks'],summary=summary),ensure_ascii=False))

def seal():
    if (OUT/'merge_manifest.json').exists():raise FileExistsError('Never reseal.')
    assert (OUT/'README.md').exists();verify(False)
    files=sorted([p for p in OUT.rglob('*') if p.is_file()]+[Path(__file__).resolve(),ROOT/'data/literature_v7.py'])
    write(OUT/'merge_manifest.json',dict(version='literature_pool_v7',parent_sha256=PARENT_SHA,scientific_goal_complete=False,model_fits=0,outputs=[dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p),bytes=p.stat().st_size) for p in files]))
    write(ROOT/'data/current_literature.json',dict(version='literature_pool_v7',directory=OUT.relative_to(ROOT).as_posix(),database_file=DB.name,sha256=sha(DB),api_module='data.literature_v7',scope='PalmKernel7main+5SI tables: raw/aggregate EIS, typed electrical stack responses, stage/normalization/statistical conflicts. Existing119aux and DES purposes unchanged; no fit.'))

if __name__=='__main__':
    if len(sys.argv)!=2 or sys.argv[1] not in ['curate','build','prepare_reports','verify','seal']:raise SystemExit('curate/build/prepare_reports(unsealed), verify(readonly), seal(one-use)')
    command=sys.argv[1]
    if command=='prepare_reports':
        if (OUT/'merge_manifest.json').exists():raise RuntimeError('Cannot regenerate sealed reports.')
        verify(True)
    elif command=='verify':verify(False)
    else:globals()[command]()
