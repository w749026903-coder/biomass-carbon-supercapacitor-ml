"""One-use additive extraction of three own sources; verify is read-only after sealing."""
from pathlib import Path
from contextlib import closing
from collections import Counter
import csv, hashlib, io, json, math, re, sqlite3, sys, xml.etree.ElementTree as E
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT/'文献全量利用复核_20261025/批次04_循环原图与新来源'
DB = OUT/'literature_material_pool_v4.sqlite'
PARENT = ROOT/'文献全量利用复核_20261025/批次03_多样品与工况/literature_material_pool_v3.sqlite'
CORPUS = ROOT/'全库复检与特征补提取_20261021/full_corpus_search_native.sqlite'
T='10.1021/acsomega.5c08826'; H='10.1002/cplu.202400408'; W='10.1002/smsc.202500174'
PARENT_SHA='465f0bb63dc07e5db722868d53c464f61d7a722ffc32b17cee8019da963ee7ce'
CORPUS_SHA='f2720c3e417904dad5857a6574cc72d5cf996f9b8716620d69594f11380c658c'
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def ro(p):return sqlite3.connect(Path(p).resolve().as_uri()+'?mode=ro',uri=True)
def txt(e):return ' '.join(''.join(e.itertext()).split()) if e is not None else ''
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def mk(d,s):return 'literature:'+hashlib.sha256((d+'\0'+s).encode()).hexdigest()[:24]
PDF_TABLES=[
 dict(doc='Hardwood_SI',id='SI_TableS1',raw='cd9dff32406cc3e8a5d8347f',header=['sample','BET_surface_area_m2_g','micropore_surface_area_m2_g','micropore_volume_cm3_g'],rows=[['WPC400-4','3257.09','2240.50','0.4024'],['WPC500-4','3366.26','1454.04','0.5911'],['WPC600-4','3377.94','1380.2','0.4797']]),
 dict(doc='Hardwood_SI',id='SI_TableS2',raw='49ebdbf5bb42c43fbf6211a6',header=['sample','EDX_C_wt_pct','EDX_C_at_pct','EDX_O_wt_pct','EDX_O_at_pct'],rows=[['WPC600-3','98.58','98.93','1.42','1.07'],['WPC600-4','99.06','99.29','0.94','0.71'],['WPC600-5','99.04','99.28','0.96','0.72'],['WPC600-6','98.71','99.03','1.29','0.97']])]

def build():
    if DB.exists() or (OUT/'merge_manifest.json').exists():raise FileExistsError('Never overwrite a batch.')
    assert sha(PARENT)==PARENT_SHA and sha(CORPUS)==CORPUS_SHA
    inventory=json.loads((PARENT.parent/'source_inventory.json').read_text('utf8'))
    selected=[s for s in inventory if s['key'] in ['Tucuma','HempHoneycomb','Hardwood']]
    docs={s['key']:dict(doi=s['doi'],path=s['path'],sha256=s['sha256'],role='main') for s in selected}
    extras=[
      ('Hardwood_SI',W,'文献扩充_大批补齐_20261018/sources/SUP_026/assets/SMSC-5-2500174-s001.pdf','SI','7c0214b230d9e370b099a7178d9b1e4c8575b64d8c616b04b53061ca9a2e60fa'),
      ('Hemp_SI',H,'文献扩充_大批补齐_20261018/sources/SUP_099/assets/CPLU-89-e202400408-s001.pdf','SI','ae44dd16135153c3d5bc85016ed1d5f561049360b67bde4d8039826382cdb228'),
      ('Tucuma_Fig6',T,'同体系文献补充_第二批_20261017/定向扩搜40至60篇_20261017/sources/OA047/figures/ao5c08826_0006.jpg','original_graphic',None),
      ('Hemp_Fig6',H,'文献扩充_大批补齐_20261018/sources/SUP_099/assets/CPLU-89-e202400408-g005.jpg','original_graphic',None),
      ('Hardwood_Fig7',W,'文献扩充_大批补齐_20261018/sources/SUP_026/assets/SMSC-5-2500174-g009.jpg','original_graphic',None)]
    for key,doi,p,role,expected in extras:
        digest=sha(ROOT/p)
        if expected:assert digest==expected
        docs[key]=dict(doi=doi,path=p,sha256=digest,role=role)
    for s in docs.values():assert sha(ROOT/s['path'])==s['sha256']
    roots={s['key']:E.parse(ROOT/s['path']).getroot() for s in selected}
    paragraphs={key:root.findall('.//body//p') for key,root in roots.items()}
    receipt=[];units={};evidence_spans=[]
    with closing(ro(PARENT)) as src,closing(sqlite3.connect(DB)) as c,closing(ro(CORPUS)) as corpus:
        src.backup(c);c.row_factory=sqlite3.Row;corpus.row_factory=sqlite3.Row;c.execute('pragma foreign_keys=on')
        c.execute('create table evidence_spans_v4(document_key text references source_documents,locator text,text text,primary key(document_key,locator))')
        c.execute('create table curve_readings_v4(reading_id text primary key,document_key text references source_documents,record_json text)')
        for s in selected:
            assert s['doi'] in [txt(i).lower() for i in roots[s['key']].findall('.//article-id') if i.get('pub-id-type')=='doi']
            c.execute('insert into reviewed_sources values(?,?,?,?,?)',(s['doi'],s['path'],s['sha256'],s['title'],'Selected own tables, numeric methods/results and specified SI/figures reviewed; not full-paper completion.'))
        for key,s in docs.items():c.execute('insert into source_documents values(?,?,?,?,?)',(key,s['doi'],s['path'],s['sha256'],s['role']))
        def span(doc,locator,text):
            c.execute('insert or ignore into evidence_spans_v4 values(?,?,?)',(doc,locator,text))
            evidence_spans.append(dict(document=doc,locator=locator,text=text))
        def material(doc,sample):
            doi=docs[doc]['doi'];canonical=sample.replace('‐','-')
            if sample!=canonical:c.execute('insert or ignore into material_aliases_v3 values(?,?,?,?)',(doi,sample,canonical,'Own series typography hyphen; no experimental sample merge.'))
            stage='final_biomass_carbon_before_cycling'
            if doi==H:stage='final_biomass_carbon_native_CaP_inclusions' if canonical.startswith('HAC') else 'biochar_intermediate'
            if canonical=='HAC||EMD':stage='asymmetric_biomass_carbon_MnO2_hybrid_device'
            if canonical=='EMD':stage='non_biomass_MnO2_counterpart_not_carbon_sample'
            c.execute('insert or ignore into materials values(?,?,?,?)',(mk(doi,canonical),doi,canonical,stage));return mk(doi,canonical)
        def unit(doc,ident,locator,header,rows,raw=None,kind='own_narrative_cells',caption=''):
            key=docs[doc]['doi']+'#'+ident
            c.execute('insert into reviewed_tables values(?,?,?,?,?,?,?)',(key,docs[doc]['doi'],ident,caption or ident,json.dumps(header,ensure_ascii=False),'Scope and method qualifications are in source review notes and issues.',raw))
            c.execute('insert into table_source_links values(?,?,?)',(key,doc,locator))
            for i,row in rows:c.execute('insert into transcribed_rows values(?,?,?)',(key,i,json.dumps(row,ensure_ascii=False)))
            c.execute('insert into extraction_units_v3 values(?,?,?)',(key,kind,'Selected own cells; comparison rows remain contextual, not own labels.'))
            if raw:
                assert c.execute('select count(*) from raw_table_queue where table_id=?',(raw,)).fetchone()[0]==1
                c.execute('update raw_table_queue set review_state=? where table_id=?',('specified_own_cells_reviewed_remaining_curves_context_pending',raw))
            receipt.append(dict(table_key=key,document=doc,locator=locator,kind=kind,raw_table_id=raw,rows=len(rows)))
            return key
        def prose(doc,index,header,rows,ident=None):
            locator='XML body//p zero-based index'+str(index);text=txt(paragraphs[doc][index]);span(doc,locator,text)
            return unit(doc,ident or 'own_body_p'+str(index),locator,header,list(enumerate(rows,1)))
        def fact(doc,sample,key,i,col,field,raw,un,method,component='whole',token=None,status='own_reported_value_method_qualified_not_model_admission'):
            if token is None:
                pattern={'whole':r'^\s*(\d+(?:\.\d+)?)\s*$','leading':r'^\s*(\d+(?:\.\d+)?)','parenthetical_percent':r'\((\d+(?:\.\d+)?)%\)'}[component]
                match=re.search(pattern,raw);assert match,(sample,field,raw);token=match[1]
            cur=c.execute('insert into material_facts(material_key,field_name,value,raw_value,unit,method,table_key,row_ordinal,column_ordinal,source_sha256,review_status,training_eligible) values(?,?,?,?,?,?,?,?,?,?,?,0)',(material(doc,sample),field,float(token),raw,un,method,key,i,col,docs[doc]['sha256'],status))
            c.execute('insert into value_components_v3 values(?,?,?,?)',(cur.lastrowid,component,token,'Author text/table cell retained; qualified component only.'))
        def cap(doc,sample,key,i,col,raw,system,ely,molar,current,basis,extra=None,status='own_reported_candidate_purpose_review_separate',eligible=False,profile='3e'):
            from data.literature_v4 import PROFILES
            ident=key+'#'+str(i)+'#'+str(col)
            cond=dict(capacitance_basis=basis,physical_test_group=docs[doc]['doi']+'#'+sample+'#'+system+'#reported_rate_series',mass_denominator='author_reported_unification_not_assumed')
            cond.update(extra or {})
            c.execute('insert into capacitance_observations values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,0)',(ident,material(doc,sample),key,i,col,float(raw),raw,'F/g','GCD',system,ely,molar,current,None,json.dumps(cond,ensure_ascii=False),status,'doi:'+docs[doc]['doi']))
            c.execute('insert into auxiliary_gcd_reviews_v3 values(?,?,?,?,?)',(ident,PROFILES[profile][0],int(eligible),'Own numeric report with bound configuration/protocol and explicit target convention.' if eligible else 'Competing, approximate, unbound current, repeated report or separate hybrid purpose; not a canonical input.','Source/agent scientific review; not human sign-off or formal cycling admission.'))
            return ident
        # Main table snapshots include headers and foreign comparisons; only explicit own cells are typed below.
        for doc,root in roots.items():
            for t in root.findall('.//table-wrap'):
                ident=t.get('id');rows=[(i,[txt(v) for v in r if v.tag in ['td','th']]) for i,r in enumerate(t.findall('.//tr'))]
                match=corpus.execute('select table_id from raw_tables_v11 where source_sha256=? and locator=?',(docs[doc]['sha256'],'XML table-wrap '+ident)).fetchone();assert match
                key=unit(doc,ident,'XML table-wrap '+ident,rows[0][1],rows,match[0],'own_xml_table' if not(doc=='Tucuma' and ident=='tbl2') else 'mixed_comparison_table',txt(t.find('caption')))
                units[(doc,ident)]=(key,dict(rows))
        for spec in PDF_TABLES:
            key=unit(spec['doc'],spec['id'],'PDF physical p1 '+spec['id'],spec['header'],list(enumerate(spec['rows'],1)),spec['raw'],'own_SI_table')
            for i,row in enumerate(spec['rows'],1):
                for col,field in enumerate(spec['header'][1:],1):
                    un='cm3/g' if 'volume' in field else ('m2/g' if 'area' in field else ('wt%' if '_wt_' in field else 'at%'))
                    fact(spec['doc'],row[0],key,i,col,field,row[col],un,'N2 BET / t-plot' if spec['id']=='SI_TableS1' else 'EDX; mass and atomic percentages distinct from XPS')
        key,rows=units[('Tucuma','tbl1')]
        for i in range(1,4):
            for col,(field,un,method) in enumerate([('BET_surface_area_m2_g','m2/g','BET explicit methods; table label S APOSTA retained'),('total_pore_volume_cm3_g','cm3/g','reported total nitrogen pore volume'),('micropore_volume_cm3_g','cm3/g','DFT cylindrical model, adsorption branch'),('mesopore_volume_cm3_g','cm3/g','DFT cylindrical model, adsorption branch')],1):fact('Tucuma',rows[i][0],key,i,col,field,rows[i][col],un,method)
        key=prose('Tucuma',43,['sample','Raman_ID_IG'],[['TAK1','0.98'],['TAK3','0.95'],['TAK5','0.92']])
        assert all(t in txt(paragraphs['Tucuma'][43]) for t in ['0.98','0.95','0.92'])
        for i,(sample,raw) in enumerate([('TAK1','0.98'),('TAK3','0.95'),('TAK5','0.92')],1):fact('Tucuma',sample,key,i,1,'Raman_ID_IG',raw,'ratio','Raman; author approximate values',status='own_reported_approximate_Raman_ratio')
        key,rows=units[('Hardwood','smsc70024-tbl-0001')]
        for i in range(1,5):
            sample=rows[i][0]
            for col,field,un,method in [(1,'BET_surface_area_m2_g','m2/g','BET'),(2,'micropore_surface_area_m2_g','m2/g','t-plot'),(3,'total_pore_volume_cm3_g','cm3/g','N2 single point p/p0=0.99'),(4,'micropore_volume_cm3_g','cm3/g','t-plot')]:fact('Hardwood',sample,key,i,col,field,rows[i][col],un,method,'leading')
            for col,field in [(2,'micropore_surface_fraction_pct'),(4,'micropore_volume_fraction_pct')]:fact('Hardwood',sample,key,i,col,field,rows[i][col],'%','reported relative contribution','parenthetical_percent')
            for j,token in enumerate(rows[i][5].split('/'),1):fact('Hardwood',sample,key,i,5,'NLDFT_pore_peak_'+str(j)+'_nm',rows[i][5],'nm','NLDFT multimodal peaks; slash values not averaged','slash_component_'+str(j),token)
        key,rows=units[('HempHoneycomb','cplu202400408-tbl-0001')]
        hemp_samples=['Biochar','HAC_450_1:1','HAC_450_1:2','HAC_800_1:2']
        for i,sample in enumerate(hemp_samples,1):
            for col,field,un,method in [(1,'BET_surface_area_m2_g','m2/g','N2 BET'),(2,'BET_fit_correlation_coefficient','ratio','BET fit; not predictive model R2'),(3,'author_t_pore_area_m2_g','m2/g','author t-pore area; not automatically total or mesopore area'),(4,'author_t_pore_volume_cm3_g','cm3/g','author t-pore volume; standard pore class not inferred')]:fact('HempHoneycomb',sample,key,i,col,field,rows[i][col],un,method)
        # Raw capacitance reports: repetitions, approximate readings and conflicting reports are not additional canonical labels.
        vals=[['TAK1','1','84'],['TAK3','1','146'],['TAK5','1','298']];key=prose('Tucuma',58,['sample','current_A_g','capacitance_F_g'],vals)
        for i,r in enumerate(vals,1):cap('Tucuma',r[0],key,i,2,r[2],'3E','KOH',1,1,'single_working_electrode',dict(voltage_lower_V=-1,voltage_upper_V=0,reference_electrode='saturated Ag/AgCl',protocol_locator='XML body//p15',reported_BET_fit_pressure_range=[.05,.8]),eligible=True)
        key=prose('Tucuma',67,['sample','current_A_g','capacitance_F_g'],[['TAK5','7','160']])
        cap('Tucuma','TAK5',key,1,2,'160','3E','KOH',1,7,'single_working_electrode',{'value_relation':'approx','competing_figure6A':True},status='approximate_prose_vs_figure_conflict')
        key,rows=units[('Tucuma','tbl2')]
        cap('Tucuma','TAK5',key,7,3,rows[7][3],'3E','KOH',1,1,'single_working_electrode',{'duplicate_of_body_p58':True},status='repeated_own_report_in_comparison_table')
        vals=[['HAC_450_1:2',str(a),str(v)] for a,v in [(1,360),(2,240),(5,180),(10,150),(15,135),(20,120)]]
        key=prose('HempHoneycomb',42,['sample','current_A_g','capacitance_F_g'],vals)
        for i,r in enumerate(vals,1):cap('HempHoneycomb',r[0],key,i,2,r[2],'3E','Na2SO4',2,float(r[1]),'single_working_electrode',dict(voltage_lower_V=-1,voltage_upper_V=0,reference_electrode='Hg/HgO',protocol_locator='XML body//p55',native_CaP_inclusions=True),status='own_reported_1A_g_conflict' if i==1 else 'native_mineral_separate_purpose',eligible=i!=1,profile='native_mineral_3e')
        abstract=txt(roots['HempHoneycomb'].find('.//abstract'));span('HempHoneycomb','XML abstract',abstract)
        key=unit('HempHoneycomb','own_abstract_caps','XML abstract',['sample','current_A_g','capacitance_F_g'],[(1,['HAC_450_1:2','1','240']),(2,['HAC||EMD','1','95'])])
        cap('HempHoneycomb','HAC_450_1:2',key,1,2,'240','3E','Na2SO4',2,1,'single_working_electrode',status='abstract_vs_body_1A_g_conflict',profile='native_mineral_3e')
        cap('HempHoneycomb','HAC||EMD',key,2,2,'95','2E_asymmetric_hybrid','Na2SO4',2,1,'author_hybrid_device',status='abstract_vs_body_hybrid_1A_g_conflict')
        key=prose('HempHoneycomb',57,['sample','current_A_g','capacitance_F_g'],[['HAC_450_1:2',None,'240'],['EMD',None,'95']])
        for i,sample,raw in [(1,'HAC_450_1:2','240'),(2,'EMD','95')]:cap('HempHoneycomb',sample,key,i,2,raw,'3E','Na2SO4',2,None,'single_working_electrode',{'current_binding':'not specified in charge-balance paragraph'},status='charge_balance_capacitance_current_unbound',profile='native_mineral_3e')
        vals=[['HAC||EMD',str(a),str(v)] for a,v in [(1,75),(2,50),(4,40),(8,30)]];key=prose('HempHoneycomb',48,['sample','current_A_g','capacitance_F_g'],vals)
        for i,r in enumerate(vals,1):cap('HempHoneycomb',r[0],key,i,2,r[2],'2E_asymmetric_hybrid','Na2SO4',2,float(r[1]),'author_hybrid_device',{'voltage_lower_V':0,'voltage_upper_V':2},status='hybrid_separate_purpose_conflict_at_1A_g' if i==1 else 'hybrid_separate_purpose')
        key,rows=units[('Hardwood','smsc70024-tbl-0003')]
        for i in range(2,6):
            for col,a in enumerate([.5,1,2,4,7,10],1):cap('Hardwood',rows[i][0],key,i,col,rows[i][col],'3E','KOH',3,a,'single_working_electrode',dict(reference_electrode='SCE',voltage_lower_V=None,voltage_upper_V=None,protocol_locator='XML body//p38; ownTable3',CV_window_not_assigned_to_GCD=[-.8,0]),eligible=True)
            for col,metric in [(7,'series_resistance_ohm'),(8,'charge_transfer_resistance_ohm')]:
                c.execute('insert into outcome_observations_v3 values(?,?,?,?,0)',(key+'#EIS'+str(i)+'_'+str(col),material('Hardwood',rows[i][0]),key,json.dumps(dict(metric=metric,value=float(rows[i][col]),raw_value=rows[i][col],unit='ohm',system='3E',electrolyte='KOH',concentration_mol_L=3,source_group='doi:'+W,row_ordinal=i,column_ordinal=col,feature_role='same_test_response_not_pretest_material_feature'),ensure_ascii=False)))
        key,rows=units[('Hardwood','smsc70024-tbl-0002')]
        for i in range(2,6):
            for col,(temp,bar) in enumerate([(0,1),(0,30),(10,1),(10,30),(25,1),(25,30)],1):
                c.execute('insert into outcome_observations_v3 values(?,?,?,?,0)',(key+'#CO2'+str(i)+'_'+str(col),material('Hardwood',rows[i][0]),key,json.dumps(dict(metric='CO2_adsorption_mmol_g',value=float(rows[i][col]),raw_value=rows[i][col],unit='mmol/g',temperature_C=temp,pressure_bar=bar,source_group='doi:'+W,row_ordinal=i,column_ordinal=col,feature_role='separate_adsorption_task_not_capacitance_or_pretest_electrochemical_feature'),ensure_ascii=False)))
        vals=[['WPC600-5',str(a),str(v)] for a,v in [(.5,91.67),(1,84.62),(2,77.54),(4,64.60),(7,59.23),(10,46.15)]];key=prose('Hardwood',31,['sample','current_A_g','capacitance_F_g'],vals)
        for i,r in enumerate(vals,1):cap('Hardwood',r[0],key,i,2,r[2],'2E_symmetric','KOH',3,float(r[1]),'author_factor2_Csp_mass_scope_not_unified',dict(author_equation='Csp=2*I*dt/(m*dV)',voltage_lower_V=None,voltage_upper_V=None,protocol_locator='XML body//p38',not_device_total_mass_target=True),eligible=True,profile='2e_author_factor2')
        # Process roles: activation, precursor treatment, measurement degassing and electrode drying stay separate.
        for sample in ['TAK1','TAK3','TAK5']:
            stages=[dict(stage='hydrothermal_carbonization',temperature_C=180,duration_h=24,medium='water',carbonization_heating_rate_not_assigned=True),dict(stage='chemical_activation',temperature_C=850,duration_h=1,heating_rate_C_min=10,atmosphere='N2',gas_flow_mL_min=100,agent='KOH',carbon_to_activator_mass_ratio=[1,int(sample[-1])],KOH_solution_wt_pct=50,pre_drying_temperature_C=130,pre_drying_duration_h=12,postwash='1MHCl thenwaterneutral',final_drying_temperature_C=100,final_drying_duration_h=12)]
            c.execute('insert into synthesis_stages_v3 values(?,?,?,?)',(material('Tucuma',sample),'Tucuma','XML body//p11-12',json.dumps(stages,ensure_ascii=False)))
        for sample in hemp_samples:
            stages=[dict(stage='carbonization',temperature_C=300,duration_h=2,atmosphere='ambient furnace; open versus covered lid alternatives not assigned',yield_pct=None)]
            if sample!='Biochar':
                temp=int(sample.split('_')[1]);ratio=int(sample[-1]);stages.append(dict(stage='chemical_activation',temperature_C=temp,duration_h=1,heating_rate_C_min=None,atmosphere=None,agent='KOH',carbon_to_activator_mass_ratio=[1,ratio],pre_drying_temperature_C=90,pre_drying_duration_h=24,postwash='author 1MHCl(32%) thenDI neutral~7; stock/working concentration wording ambiguous',final_drying_temperature_C=60,final_drying_duration_h=12))
            c.execute('insert into synthesis_stages_v3 values(?,?,?,?)',(material('HempHoneycomb',sample),'HempHoneycomb','XML body//p52-53; p37; SIphysicalp3FigureS2',json.dumps(stages,ensure_ascii=False)))
        for sample in ['WPC400-4','WPC500-4','WPC600-3','WPC600-4','WPC600-5','WPC600-6']:
            temp=int(sample[3:6]);ratio=int(sample[-1]);stages=[dict(stage='carbonization',temperature_C=temp,duration_h=2,heating_rate_C_min=5,atmosphere='inert gas identity unspecified'),dict(stage='chemical_activation',temperature_C=800,duration_h=2,heating_rate_C_min=5,atmosphere=None,agent='KOH',carbon_to_activator_mass_ratio=[1,ratio],postwash='2MHCl thenDIwater',final_drying_temperature_C=100,final_drying_duration_h=None,final_drying_duration_raw='overnight')]
            c.execute('insert into synthesis_stages_v3 values(?,?,?,?)',(material('Hardwood',sample),'Hardwood','XML body//p35;Table1;SIphysicalp1',json.dumps(stages,ensure_ascii=False)))
        # Original raster digitization: estimates plus reading resolution, never an exact author label.
        from PIL import Image
        with Image.open(ROOT/docs['Tucuma_Fig6']['path']) as im:assert im.size==(796,1231)
        reading=dict(source_sha256=docs['Tucuma_Fig6']['sha256'],image_size_px=[796,1231],coordinates='original image pixels; top-left origin',method='manually located printed axis anchors and marker centers; linear axes',panel_A=dict(x_anchors=[[154,1],[744,7]],y_anchors=[[492,0],[33,300]],marker_centers_px=[[154,31],[351,152],[547,218],[744,234]],center_uncertainty_px=3),panel_B=dict(x_anchors=[[99,0],[746,7000]],y_anchors=[[1144,0],[643,100]],first_shown_marker_center_px=[146,669],final_marker_center_px=[744,674],center_uncertainty_px=3,normalization='author plotted retention; first shown point is not asserted to be cycle1 or the normalization origin'))
        for name,panel in [('A',reading['panel_A']),('B',reading['panel_B'])]:
            ya=panel['y_anchors'];slope=(ya[1][1]-ya[0][1])/(ya[1][0]-ya[0][0]);panel['y_uncertainty_from_3px']=abs(3*slope)
            centers=panel['marker_centers_px'] if name=='A' else [panel['first_shown_marker_center_px'],panel['final_marker_center_px']]
            panel['y_readings']=[round(ya[0][1]+(y-ya[0][0])*slope,2) for x,y in centers]
        write(OUT/'evidence/Tucuma_Fig6_reading.json',reading)
        c.execute('insert into curve_readings_v4 values(?,?,?)',('TAK5_Fig6','Tucuma_Fig6',json.dumps(reading,ensure_ascii=False)))
        vals=[['TAK5',str(a),str(v)] for a,v in zip([1,3,5,7],reading['panel_A']['y_readings'])]
        key=unit('Tucuma_Fig6','Fig6A_readings','original Figure6A; evidence/Tucuma_Fig6_reading.json',['sample','current_A_g','capacitance_F_g'],list(enumerate(vals,1)),kind='original_figure_readings')
        for i,r in enumerate(vals,1):cap('Tucuma_Fig6',r[0],key,i,2,r[2],'3E','KOH',1,float(r[1]),'single_working_electrode',dict(value_relation='approx',reading_uncertainty_F_g=reading['panel_A']['y_uncertainty_from_3px'],duplicate_of_reported_rate_series=True),status='approximate_figure_reading_not_exact_auxiliary_label')
        # Source-specific cycling candidates: formal cycling library is intentionally unchanged.
        candidates=[('TAK5', 'Tucuma', 'TAK5',dict(system='3E',electrolyte='KOH',concentration_mol_L=1,reported_current_A_g=7,reference_electrode='saturated Ag/AgCl',cycle_voltage_lower_V=-1,cycle_voltage_upper_V=0,cycle_count=7000,retention_pct=98,retention_relation='eq',competing_figure_retention_pct=reading['panel_B']['y_readings'][-1],figure_reading_uncertainty_pp=reading['panel_B']['y_uncertainty_from_3px'],unresolved=['abstract98% versus ownFigure6B approximately94%; normalization explanation not supplied'],locator='XML abstract,p15,p71; originalFigure6B')),
          ('HAC','HempHoneycomb','HAC_450_1:2',dict(system='3E',electrolyte='Na2SO4',concentration_mol_L=2,reported_current_A_g=10,reference_electrode='Hg/HgO',cycle_voltage_lower_V=-1,cycle_voltage_upper_V=0,cycle_count=15000,retention_pct=98.3,retention_relation='eq',terminal_capacitance_F_g=144,native_CaP_inclusions=True,unresolved=['nativeCaP separate material purpose, not silently admitted into pure-carbon main'],locator='XML p37,p44,p55;originalFigure6d printed98.3%')),
          ('HAC_EMD','HempHoneycomb','HAC||EMD',dict(system='2E_asymmetric_hybrid',electrolyte='Na2SO4',concentration_mol_L=2,reported_current_A_g=.5,reference_electrode=None,cycle_voltage_lower_V=0,cycle_voltage_upper_V=2,cycle_count=1000,retention_pct=91,retention_relation='eq',initial_capacitance_F_g=105,terminal_capacitance_F_g=95,abstract_retention_pct=90,unresolved=['MnO2 hybrid separate purpose','body91% versus abstract90% retained; not pure-carbon cycle label'],locator='XML abstract,p48,p55')),
          ('WPC6005','Hardwood','WPC600-5',dict(system='2E_symmetric',electrolyte='KOH',concentration_mol_L=3,reported_current_A_g=5,reference_electrode=None,cycle_voltage_lower_V=None,cycle_voltage_upper_V=None,cycle_count=10000,retention_pct=87.5,retention_relation='eq',same_curve_plateau_report=dict(retention_pct=100,up_to_cycle=4000),unresolved=['cycling voltage endpoints not explicitly bound in reviewed methods; CV and diagnostic GCD not substituted'],locator='XML p31,p38;originalFigure7d'))]
        for ident,doc,sample,record in candidates:
            record.update(source_group='doi:'+docs[doc]['doi'],sample_name=sample,method='GCD',baseline_reference='author own initial normalization; exact cycle index unknown',source_sha256=docs[doc]['sha256'],evidence_source_path=docs[doc]['path'],scientific_gate_passed=False,current_cycle_database_membership=False)
            c.execute('insert into test_candidates values(?,?,?,0)',('LP4_cycle_'+ident,material(doc,sample),json.dumps(record,ensure_ascii=False)))
        issues=[('TAK_retention',T,'TAK5',dict(kind='abstract_original_figure_retention_conflict',abstract_pct=98,body_raw='close to100%',figure_pct=reading['panel_B']['y_readings'][-1],reading_uncertainty_pp=reading['panel_B']['y_uncertainty_from_3px'],action='Keep all three reports. No unsupported renormalization to first shown point; cycling admission frozen.')),
          ('TAK_rate',T,'TAK5',dict(kind='prose_figure_rate_capacitance_difference',body_7A_g_F_g=160,figure_7A_g_F_g=reading['panel_A']['y_readings'][-1],action='Both approximate reports retained; no exact7A/g auxiliary label selected.')),
          ('TAK_BET',T,'all',dict(kind='reported_BET_fit_range_quality_qualification',reported_relative_pressure_range=[.05,.8],action='Store reported BET with pressure-range quality annotation; no invented universal C-constant admission gate.')),
          ('TAK_mass',T,'all',dict(kind='electrode_mass_reports_different_scope',methods_raw='approximately1mg distributed across3electrodes',EIS_caption_raw='0.1mg',action='Keep scope/uncertainty; no per-electrode mass or unified current denominator inferred; author A/g remains allowed for report purpose.')),
          ('HAC_cap',H,'HAC_450_1:2',dict(kind='same_current_capacitance_conflict',body_F_g=360,abstract_F_g=240,current_A_g=1,charge_balance_F_g=240,charge_balance_current_A_g=None,action='Freeze canonical1A/g label; other explicitly bound currents remain available in native-mineral purpose.')),
          ('HAC_scope',H,'HAC_450_1:2',dict(kind='native_calcium_phosphate_material_purpose',evidence='Ownp37 STEM/EDS says CaP inclusions at450/800C; SIFigureS2 onlyCmap, not quantitative absence ofCa/P.',action='Separate native-mineral3E task; do not extend existing residualSi subset or call intentional MnO2 hybrid pure carbon.')),
          ('HAC_hybrid',H,'HAC||EMD',dict(kind='hybrid_capacitance_and_retention_competition',body_1A_g_F_g=75,abstract_1A_g_F_g=95,body_cycle_pct=91,abstract_cycle_pct=90,action='Keep separate hybrid candidate and conflicting author reports; no transfer to HAC single-electrode labels.')),
          ('WPC_precision',W,'WPC600-4',dict(kind='reported_precision_and_transcription_variants',body_BET=3377.4,table_BET=3377.94,SI_BET=3377.94,table_microvolume=.48,SI_microvolume=.4797,action='Select matching mainTable1+SI BET3377.94; microvolumeSI0.4797 is explicit additional precision consistent with main0.48 rounding. Preserve all reports, not independent measurements.')),
          ('WPC_voltage',W,'WPC600-5',dict(kind='cycling_voltage_binding_unresolved',CV_3E_window=[-.8,0],cycling_2E_window=None,action='Do not transplant CV or diagnostic GCD window to cycling, or backsolve cycling voltage from energy. Retention87.5% is supported but necessary cycle voltage still pending.')),
          ('WPC_basis',W,'WPC600-5',dict(kind='author_factor2_capacitance_separate_target',equation='Csp=2I*dt/(m*dV)',mass_scope=None,action='Keep authorfactor2 task. Do not concatenate with device-total-active-mass or3E capacitance, and do not infer current denominator from formula.')),
          ('WPC_outcomes',W,'all',dict(kind='adsorption_and_EIS_responses_not_pretest_features',action='24CO2 adsorption and8EIS outcomes separately typed, never cycling labels or pretest material descriptors. Table3Rct1.32 is tied for600-3/600-5 despite prose lowest claim.'))]
        for ident,doi,sample,issue in issues:c.execute('insert into scientific_issues values(?,?,?,?)',('LP4_'+ident,doi,sample,json.dumps(issue,ensure_ascii=False)))
        for doi,scope,reason in [(T,'biomass_own_carbon_cycle_conflict','Tucuma bark carbon; own material and3EGCD report purpose; cycling graph-text conflict frozen.'),(H,'native_mineral_carbon_and_separate_MnO2_hybrid','HAC finalcarbon retains naturalCaP; native-mineral target separated; EMD andhybrid notpurecarbon.'),(W,'biomass_own_carbon_two_capacitance_conventions','Wastehardwood owncarbon;3EGCD andfactor2symmetricCsp separately typed; cycling voltage binding pending.')]:c.execute('insert into source_scope_decisions values(?,?,?,?,0)',(doi,scope,reason,json.dumps({'full_paper_all_curves_complete':False},ensure_ascii=False)))
        for doc,inds in [('Tucuma',[11,12,13,14,15,43,58,67,71]),('HempHoneycomb',[37,42,44,48,52,53,54,55,57]),('Hardwood',[7,29,31,35,37,38])]:
            for i in inds:span(doc,'XML body//p zero-based index'+str(i),txt(paragraphs[doc][i]))
        span('Tucuma','XML abstract',txt(roots['Tucuma'].find('.//abstract')))
        c.commit()
    write(OUT/'source_inventory.json',selected)
    write(OUT/'source_protection.json',dict(documents=docs,parent=dict(path=PARENT.relative_to(ROOT).as_posix(),sha256=PARENT_SHA),corpus=dict(path=CORPUS.relative_to(ROOT).as_posix(),sha256=CORPUS_SHA),cycling_pointer=json.loads((ROOT/'data/current_database.json').read_text('utf8'))))
    write(OUT/'table_review_receipt.json',receipt)
    write(OUT/'source_review_notes.json',dict(scope='Selected tables and named paragraphs/figures/SI only; three papers not fully utilized.',sources=[dict(doi=T,done='OwnTable1; Table2ownrow+foreigncontext; synthesis; Raman; three1A/g GCD values; rate and retention figure6 readings with pixel uncertainty; graph-text conflicts preserved.',remaining=['fullGCDcurve digitization and protocol-specific uncertainty','remainingSEM/XRD/Raman/sorptionfigures','retention conflict requires source-supported clarification; first shown point not asserted baseline']),dict(doi=H,done='OwnBETtable; methods/process; SIphysicalp3Cmap; own3E/hybridcapacitance reports; Figure6d98.3%label; nativeCaPscope and conflicts.',remaining=['remainingSI/figure-specificquantitativeextraction','1A/g competing240/360 author evidence','native-mineral cycling purpose and purecarbon boundary not silentlymerged']),dict(doi=W,done='OwnTables1-3; SIphysicalp1TablesS1/S2; synthesis;3EGCD24and2Efactor2sixreports;Figure7cyclinglabel/protocolreview; CO2/EISseparateoutcomes.',remaining=['cycling voltage directbinding','full3EGCDandothercharacterizationcurve digitization','otherSIcomparisons remainreferences notownmeasurements'])],scientific_goal_complete=False))
    print('Built additive v4; unsealed until all checks and notes pass.')

def verify():
    checks=[]
    def check(name,ok):
        if not ok:raise AssertionError(name)
        checks.append(name)
    proof=json.loads((OUT/'source_protection.json').read_text('utf8'))
    for key,d in proof['documents'].items():check('original_'+key,sha(ROOT/d['path'])==d['sha256'])
    for key in ['parent','corpus']:check('unchanged_'+key,sha(ROOT/proof[key]['path'])==proof[key]['sha256'])
    check('cycling_pointer',json.loads((ROOT/'data/current_database.json').read_text('utf8'))==proof['cycling_pointer'])
    with closing(ro(DB)) as c,closing(ro(PARENT)) as old:
        c.row_factory=sqlite3.Row
        check('integrity',c.execute('pragma integrity_check').fetchone()[0]=='ok');check('foreign_keys',not c.execute('pragma foreign_key_check').fetchall())
        for (name,) in old.execute("select name from sqlite_master where type='table' and name not like 'sqlite_%'"):
            if name=='raw_table_queue':continue
            current={tuple(r) for r in c.execute('select * from '+name)}
            check('parent_rows_'+name,all(tuple(r) in current for r in old.execute('select * from '+name)))
        oldq={r[0]:tuple(r) for r in old.execute('select * from raw_table_queue')};q=[tuple(r) for r in c.execute('select * from raw_table_queue')]
        check('queue_identity',set(oldq)=={r[0] for r in q})
        check('queue_raw_fields',all(r[:6]==oldq[r[0]][:6] and r[7:]==oldq[r[0]][7:] for r in q))
        for rec in json.loads((OUT/'table_review_receipt.json').read_text('utf8')):
            doc=proof['documents'][rec['document']]
            if rec['kind'] in ['own_xml_table','mixed_comparison_table']:
                root=E.parse(ROOT/doc['path']).getroot();ident=rec['locator'].removeprefix('XML table-wrap ');t=root.find(".//table-wrap[@id='"+ident+"']")
                for i,r in enumerate(t.findall('.//tr')):check('xml_'+rec['table_key']+'_'+str(i),[txt(v) for v in r if v.tag in ['td','th']]==json.loads(c.execute('select cells_json from transcribed_rows where table_key=? and row_ordinal=?',(rec['table_key'],i)).fetchone()[0]))
        for r in c.execute('select * from evidence_spans_v4'):
            root=E.parse(ROOT/proof['documents'][r['document_key']]['path']).getroot();loc=r['locator']
            actual=txt(root.find('.//abstract')) if loc=='XML abstract' else txt(root.findall('.//body//p')[int(loc.split('index')[-1])])
            check('span_'+r['document_key']+'_'+loc,actual==r['text'])
        for r in c.execute('select f.*,v.component,v.numeric_token from material_facts f join value_components_v3 v using(fact_id) where fact_id>519'):
            cells=json.loads(c.execute('select cells_json from transcribed_rows where table_key=? and row_ordinal=?',(r['table_key'],r['row_ordinal'])).fetchone()[0]);check('rawcell_'+str(r['fact_id']),cells[r['column_ordinal']]==r['raw_value'])
            check('number_'+str(r['fact_id']),r['value']==float(r['numeric_token']))
            if r['component'].startswith('slash_component_'):token=r['raw_value'].split('/')[int(r['component'][-1])-1]
            else:
                p={'whole':r'^\s*(\d+(?:\.\d+)?)\s*$','leading':r'^\s*(\d+(?:\.\d+)?)','parenthetical_percent':r'\((\d+(?:\.\d+)?)%\)'}[r['component']];token=re.search(p,r['raw_value'])[1]
            check('component_'+str(r['fact_id']),token==r['numeric_token'])
        for table in ['raw_table_queue','material_facts','capacitance_observations','test_candidates','outcome_observations_v3']:check('no_automatic_admission_'+table,c.execute('select count(*) from '+table+' where training_eligible!=0 or training_eligible is null').fetchone()[0]==0)
        new_dois={T,H,W}
        for r in c.execute('select x.*,m.doi from capacitance_observations x join materials m using(material_key)'):
            if r['doi'] not in new_dois:continue
            cells=json.loads(c.execute('select cells_json from transcribed_rows where table_key=? and row_ordinal=?',(r['table_key'],r['row_ordinal'])).fetchone()[0])
            check('cap_source_cell_'+r['observation_id'],r['raw_value']==cells[r['column_ordinal']] and float(r['raw_value'])==r['value'])
        import pypdfium2 as pdf
        with pdf.PdfDocument(str(ROOT/proof['documents']['Hardwood_SI']['path'])) as d:
            page=d[0];tp=page.get_textpage();text=tp.get_text_range();tp.close();page.close()
        for spec in PDF_TABLES:
            for row in spec['rows']:
                for token in row[1:]:check('SI_native_token_'+spec['id']+'_'+row[0]+'_'+token,token in text)
        check('cycling_candidates_still_pending',all(not json.loads(r[0])['current_cycle_database_membership'] for r in c.execute("select record_json from test_candidates where candidate_id like 'LP4_%'")))
        count=lambda t:c.execute('select count(*) from '+t).fetchone()[0]
        untouched=c.execute("select count(*) from raw_table_queue where review_state='automatic_candidate_unreviewed'").fetchone()[0]
        aux=c.execute('select * from auxiliary_reported_GCD_v3').fetchall();parts=Counter(r['purpose'] for r in aux)
        summary=dict(identity_catalogue_entries=480,raw_table_candidates=959,raw_table_rows=6121,cumulative_reviewed_source_publications=count('reviewed_sources'),cumulative_materials=count('materials'),cumulative_selected_material_cells=count('material_facts'),cumulative_numeric_material_facts=c.execute('select count(*) from material_facts where value is not null').fetchone()[0],new_materials=count('materials')-46,new_numeric_material_facts=c.execute('select count(*) from material_facts where value is not null').fetchone()[0]-511,reviewed_table_units=c.execute("select count(*) from reviewed_tables where table_key not in (select table_key from extraction_units_v3) or table_key in (select table_key from extraction_units_v3 where kind in ('own_xml_table','own_SI_table','own_and_comparison_pdf_table','mixed_comparison_table'))").fetchone()[0],reviewed_evidence_units=count('reviewed_tables'),raw_candidates_touched=959-untouched,raw_candidates_untouched=untouched,capacitance_records=count('capacitance_observations'),numeric_capacitance_values=c.execute('select count(*) from capacitance_observations where value is not null').fetchone()[0],unreported_capacitance_cells=2,cycling_candidates=count('test_candidates'),scientific_issues=count('scientific_issues'),historical_selected_fact_references=725,historical_fact_references_with_same_source_table_candidates=171,synthesis_materials=count('synthesis_stages_v3'),coulombic_efficiency_outcomes=8,CO2_adsorption_outcomes=24,EIS_outcomes=8,auxiliary_aqueous_3e_GCD_rows=parts['reported_aqueous_3e_GCD_capacitance'],auxiliary_aqueous_2e_GCD_rows=parts['reported_aqueous_2e_GCD_device_capacitance'],auxiliary_native_mineral_3e_GCD_rows=parts['reported_native_mineral_3e_GCD_capacitance'],auxiliary_author_factor2_2e_GCD_rows=parts['reported_2e_author_factor2_GCD_capacitance'],auxiliary_independent_DOI_groups=len({r['source_group'] for r in aux}),auxiliary_purpose_reviewed_input_rows=len(aux),new_training_admissions=0,formal_cycling_admissions=0,model_fits=0,all_literature_fully_utilized=False,scope_note='Four distinct capacitance tasks are never concatenated. Numeric cells/repeated reports are not independent papers or new cycling admissions. Source-group counts describe documented provenance, not proof of statistical independence.')
    from data.literature_v4 import open_literature_database,PROFILES
    from data.cycling_db import open_database
    digest=sha(DB)
    with open_literature_database(DB,digest) as db,open_database() as cy:
        profiles={p:db.auxiliary_feature_rows(p) for p in PROFILES}
        main=cy.fetch('reported_3e').rows
        check('cycling_main_43_31',len(main)==43 and len({r['source_group'] for r in main})==31)
        expected={'3e':47,'2e_device':5,'native_mineral_3e':5,'2e_author_factor2':6}
        for p,rows in profiles.items():
            check('purpose_count_'+p,len(rows)==expected[p])
            weights=Counter(r['source_group'] for r in rows)
            for r in rows:
                r['source_balanced_weight']=1/weights[r['source_group']]
                check('positive_target_'+r['observation_id'],math.isfinite(r['capacitance_F_g']) and r['capacitance_F_g']>0)
                check('protocol_bound_'+r['observation_id'],r['current_A_g'] is not None and r['concentration_mol_L'] is not None)
                check('no_outcome_features_'+r['observation_id'],not any('retention' in k or 'coulombic' in k or 'resistance' in k or 'adsorption' in k for k in r))
                for k,v in r.items():
                    if k.endswith('_is_missing'):check('mask_'+r['observation_id']+'_'+k,v==(r[k.removesuffix('_is_missing')] is None))
            for source in weights:check('source_weight_'+p+source,abs(sum(r['source_balanced_weight'] for r in rows if r['source_group']==source)-1)<1e-12)
            buf=io.StringIO(newline='');writer=csv.DictWriter(buf,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows);text=buf.getvalue();path=OUT/('auxiliary_'+p+'.csv')
            if (OUT/'merge_manifest.json').exists():
                with path.open('r',encoding='utf8',newline='') as f:check('sealed_csv_'+p,f.read()==text)
            else:
                with path.open('w',encoding='utf8',newline='') as f:f.write(text)
        check('four_targets',len({r['target_name'] for rows in profiles.values() for r in rows})==4)
        check('HAC1Ag_not_selected',all(r['current_A_g']!=1 for r in profiles['native_mineral_3e']))
        check('WPC_correct_stage',all(r['activation_temperature_C']==800 and r['carbonization_temperature_C']==600 for r in profiles['3e'] if r['doi']==W))
        wpc=next(r for r in profiles['3e'] if r['doi']==W and r['sample_name']=='WPC600-4');check('SI_precision_explicit',wpc['micropore_volume_cm3_g']==.4797)
        check('EDX_not_XPS',all(r['XPS_C_at_pct'] is None for r in profiles['3e'] if r['doi']==W))
        check('native_mineral_not_purecarbon',not any(r['doi']==H for r in profiles['3e']))
        all_aux=[r for rows in profiles.values() for r in rows];sources=sorted({r['source_group'] for r in all_aux});folds=[]
        for source in sources:
            hold=[r for r in all_aux if r['source_group']==source];train=[r for r in all_aux if r['source_group']!=source]
            check('whole_source_'+source,not {r['source_group'] for r in hold}&{r['source_group'] for r in train})
            folds.append(dict(heldout_source=source,auxiliary_train_rows=len(train),auxiliary_validation_rows=len(hold),all_capacitance_reports_quarantined=sum(r['source_group']==source for r in db.capacitances()),cycling_candidates_quarantined=sum(r['record']['source_group']==source for r in db.tests()),other_outcomes_quarantined=sum(db.connection.execute('select doi from materials where material_key=?',(r['material_key'],)).fetchone()[0]==source.removeprefix('doi:') for r in db.outcomes()),all_same_source_labels_must_be_excluded_from_pretraining=True,actual_model_fit=False))
        input_report=dict(status='passed',profile_rows={p:len(r) for p,r in profiles.items()},profile_sources={p:len({x['source_group'] for x in r}) for p,r in profiles.items()},source_folds=folds,missingness_by_profile={p:{k:sum(r[k] is None for r in rows) for k in rows[0] if any(r[k] is None for r in rows)} for p,rows in profiles.items()},purpose_sufficiency='Matrix reading/masks/group isolation verified; no independent model validation or claimed error reduction.',scientific_goal_complete=False,model_fits=0)
    check('read_only_preflight',sha(DB)==digest)
    report=dict(status='passed',checks=len(checks),check_names=checks,model_fits=0,scientific_goal_complete=False)
    sealed=(OUT/'merge_manifest.json').exists()
    for name,value in [('summary.json',summary),('verification.json',report),('auxiliary_input_preflight.json',input_report)]:
        if sealed:
            if json.loads((OUT/name).read_text('utf8'))!=value:raise AssertionError('sealed_report_'+name)
        else:write(OUT/name,value)
    if sealed:
        for item in json.loads((OUT/'merge_manifest.json').read_text('utf8'))['outputs']:
            if sha(ROOT/item['path'])!=item['sha256']:raise AssertionError('sealed_hash_'+item['path'])
    print(json.dumps(dict(status='passed',checks=report['checks'],summary=summary),ensure_ascii=False))

def seal():
    if (OUT/'merge_manifest.json').exists():raise FileExistsError('Do not reseal.')
    for name in ['README.md','source_review_notes.json']:assert (OUT/name).exists()
    verify()
    files=sorted([p for p in OUT.rglob('*') if p.is_file()]+[Path(__file__).resolve(),ROOT/'data/literature_v4.py'])
    write(OUT/'merge_manifest.json',dict(kind='literature_evidence_pool_v4',parent_sha256=PARENT_SHA,new_formal_cycling_admissions=0,model_fits=0,outputs=[dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p),bytes=p.stat().st_size) for p in files]))
    write(ROOT/'data/current_literature.json',dict(version='literature_pool_v4',directory=OUT.relative_to(ROOT).as_posix(),database_file=DB.name,sha256=sha(DB),api_module='data.literature_v4',scope='Selected source-qualified material/process/capacitance evidence; four separate auxiliary tasks, not cycling main membership.'))
if __name__=='__main__':
    if len(sys.argv)!=2 or sys.argv[1] not in ['build','verify','seal']:raise SystemExit('build(one-use), verify(read-only), seal(one-use)')
    globals()[sys.argv[1]]()
