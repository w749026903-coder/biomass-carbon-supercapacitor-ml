"""One-use multi-sample extraction with source-qualified auxiliary GCD admission."""
from pathlib import Path
from contextlib import closing
import hashlib,json,re,sqlite3,sys,xml.etree.ElementTree as E
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
OUT=ROOT/'文献全量利用复核_20261025/批次03_多样品与工况';DB=OUT/'literature_material_pool_v3.sqlite'
PARENT=ROOT/'文献全量利用复核_20261025/批次02_紫玉米芯与对照/literature_material_pool_v2.sqlite'
CORPUS=ROOT/'全库复检与特征补提取_20261021/full_corpus_search_native.sqlite'
M='10.1021/acsomega.5c06396';H='10.1021/acsomega.5c10175';P='10.1021/acsomega.5c03461';C='10.1002/advs.202206320'
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def ro(p):return sqlite3.connect(Path(p).resolve().as_uri()+'?mode=ro',uri=True)
def txt(e):return ' '.join(''.join(e.itertext()).split()) if e is not None else ''
def mk(doi,s):return 'literature:'+hashlib.sha256((doi+'\0'+s).encode()).hexdigest()[:24]

MAIN_KEYS=['Macadamia','HempNaOH','Popcorn','CNF_MWCNT']
SI_DOCS=[
 ('Macadamia_SI',M,'同体系文献补充_第二批_20261017/定向扩搜40至60篇_20261017/sources/OA014/ao5c06396_si_001.pdf','f5779fad14ec0e47875621a13b82b4bd02bcb84d294a07d74ccf90a580d8aa5f'),
 ('HempNaOH_SI',H,'同体系文献补充_第二批_20261017/定向扩搜40至60篇_20261017/sources/OA010/ao5c10175_si_001.pdf','96dfa65d918a7015ba154029a814bc9b2dae932d7be7f486ca4b1ff7cc7a4745'),
 ('CNF_MWCNT_SI',C,'文献扩充_大批补齐_20261018/sources/SUP_119/assets/ADVS-10-2206320-s001.pdf','139ccdc2359c1cb42fcb83d204f2890fc42996c060175901cc4691882157a915')]
PDF_TABLES=[
 dict(doc='Macadamia_SI',id='SI_TableS1',page=3,raw='165bd6dce134dc709989dd01',header=['sample','EDS_C_at_pct','EDS_O_at_pct','EDS_K_at_pct'],rows=[['C-MNS','92.65','7.20','0.15'],['AC-MNS-1','90.05','9.95','-'],['AC-MNS-2','90.73','9.28','-'],['AC-MNS-3','90.27','9.73','-']]),
 dict(doc='HempNaOH_SI',id='SI_TableS1',page=5,raw='4135b5b47d04fd9d6312d470',header=['sample','SSA','Vtotal','Vmeso','Vmicro','Vmeso_Vmicro','capacitance_F_g'],rows=[['Hurd-4','3033','1.55','0.95','0.60','1.58','435'],['Coal tar pitch-based porous carbons','3305','1.66','0.78','0.88','0.89','308'],['Eucommia Ulmoides Wood-derived activated carbon','2912','1.48','1.35','0.12','11.25','510 @0.2 A/g']]),
 dict(doc='HempNaOH_SI',id='SI_TableS2',page=6,raw='a17fea03208b7a0c334425e5',header=['sample','current_A_g','electrolyte','coulombic_efficiency_pct'],rows=[['AB520Y','0.3','1 M H2SO4','66.4'],['Hurd-1','0.3','1 M H2SO4','64.1'],['Hurd-2','0.3','1 M H2SO4','70.7'],['Hurd-3','0.3','1 M H2SO4','62.4'],['Hurd-4','0.3','1 M H2SO4','61.1'],['Hurd-4','0.5','1 M H2SO4','82.0'],['Hurd-4','1.0','1 M H2SO4','93.1'],['Hurd-4','10.0','1 M H2SO4','94.9'],['Coconut husk [3]','1.0','1 M H2SO4','67.6'],['KOH activated carbon [4]','N/A','1 M Li2SO4','97.0']]),
 dict(doc='CNF_MWCNT_SI',id='SI_TableS4',page=24,raw='9b4153d45085bf0237ce70a9',header=['layer_number','height_mm','area_cm2','mass_loading_mg_cm2'],rows=[['3','1.22','1','15.2'],['4','1.61','1','20.4'],['5','2.03','1','25.1'],['6','2.43','1','30.2']])]

def build():
 if DB.exists():raise FileExistsError('Never overwrite a release or unreviewed existing batch.')
 assert sha(PARENT)=='23257647f168cf18c4435622ef9a0dc9cede70af71b8ce4b3402294810b5a7cf'
 inventory=json.loads((OUT/'source_inventory.json').read_text('utf8'));specs=[x for x in inventory if x['key'] in MAIN_KEYS]
 docs={x['key']:dict(doi=x['doi'],path=x['path'],sha256=x['sha256'],role='main') for x in specs}
 docs.update({k:dict(doi=d,path=p,sha256=s,role='SI') for k,d,p,s in SI_DOCS})
 for v in docs.values():assert sha(ROOT/v['path'])==v['sha256']
 roots={x['key']:E.parse(ROOT/x['path']).getroot() for x in specs}
 paragraphs={key:root.findall('.//body//p') for key,root in roots.items()};receipts=[]
 with closing(ro(PARENT)) as src,closing(sqlite3.connect(DB)) as c,closing(ro(CORPUS)) as corpus:
  src.backup(c);c.row_factory=sqlite3.Row;corpus.row_factory=sqlite3.Row;c.execute('pragma foreign_keys=on')
  c.executescript('''
  create table extraction_units_v3(table_key text primary key references reviewed_tables,kind text,scope text);
  create table value_components_v3(fact_id integer primary key references material_facts,component text,numeric_token text,qualification text);
  create table material_aliases_v3(doi text,raw_name text,canonical_name text,basis text,primary key(doi,raw_name));
  create table synthesis_stages_v3(material_key text primary key references materials,document_key text references source_documents,locator text,stages_json text);
  create table outcome_observations_v3(outcome_id text primary key,material_key text references materials,table_key text references reviewed_tables,record_json text,training_eligible integer check(training_eligible=0));
  create table auxiliary_gcd_reviews_v3(observation_id text primary key references capacitance_observations,purpose text,eligible integer check(eligible in(0,1)),reason text,review_basis text);
  create index auxiliary_eligibility_by_purpose on auxiliary_gcd_reviews_v3(purpose,eligible);
  ''')
  for x in specs:
   root=roots[x['key']];actual=[txt(i).lower() for i in root.findall('.//article-id') if i.get('pub-id-type')=='doi'];assert x['doi'] in actual
   c.execute('insert into reviewed_sources values(?,?,?,?,?)',(x['doi'],x['path'],x['sha256'],x['title'],'Selected own tables,methods,and numeric prose reviewed; remaining curve digitization/SI not full completion.'))
  for key,v in docs.items():c.execute('insert into source_documents values(?,?,?,?,?)',(key,v['doi'],v['path'],v['sha256'],v['role']))
  for doi,scope,reason in [(M,'biomass_own_carbon','Macadamia nutshell;own carbonization+KOH activation,aqueous3E/2E bound.'),(H,'biomass_plus_separate_commercial_control','Hemp hurd,NaOH activation;AB520Y commercial comparator separately retained.'),(P,'biomass_own_carbon_organic_device','Popcorn+KNO3;air versusN2 distinct;device and single-electrode convention separated.'),(C,'biomass_CNT_composite_separate_purpose','CNF and intentionally retained MWCNT;precursorCNF:MWCNT3:7 andMWCNT:urea1:5;final carbon fractions not inferred. Not pure biomass-carbon auxiliary mass target.')]:
   c.execute('insert into source_scope_decisions values(?,?,?,?,0)',(doi,scope,reason,json.dumps({'methods_reviewed':True,'full_paper_all_curves_complete':False},ensure_ascii=False)))
  def material(doi,sample):
   if doi==M and sample=='C–MNS':
    c.execute('insert or ignore into material_aliases_v3 values(?,?,?,?)',(doi,sample,'C-MNS','Own Table2 typesetting en-dash; methods and own sample series explicitly identify same unactivated carbon.'));sample='C-MNS'
   stage='final_sample_before_cycling'
   if sample=='AB520Y':stage='commercial_reference_origin_not_reported'
   elif sample=='Hurd-BC':stage='intermediate_biochar_not_activated'
   elif sample in ['C-MNS','POP']:stage='unactivated_carbon_control'
   elif doi==C:stage='final_biomass_CNT_composite_separate_purpose'
   key=mk(doi,sample);c.execute('insert or ignore into materials values(?,?,?,?)',(key,doi,sample,stage));return key
  def unit(doc,identifier,locator,header,rows,raw=None,kind='own_narrative_cells',caption='',footnote=''):
   doi=docs[doc]['doi'];key=doi+'#'+identifier
   c.execute('insert into reviewed_tables values(?,?,?,?,?,?,?)',(key,doi,identifier,caption or identifier,json.dumps(header,ensure_ascii=False),footnote,raw))
   c.execute('insert into table_source_links values(?,?,?)',(key,doc,locator))
   for ordinal,row in rows:c.execute('insert into transcribed_rows values(?,?,?)',(key,ordinal,json.dumps(row,ensure_ascii=False)))
   c.execute('insert into extraction_units_v3 values(?,?,?)',(key,kind,'Only explicitly selected fields and own rows; source-stage notes retain remaining work.'))
   if raw:c.execute('update raw_table_queue set review_state=? where table_id=?',('own_rows_methods_reviewed_comparisons_separated_remaining_curves_pending',raw))
   receipts.append(dict(table_key=key,document=doc,locator=locator,raw_table_id=raw,kind=kind,rows=len(rows)));return key
  xmlunits={}
  for doc in ['Macadamia','HempNaOH','Popcorn']:
   root=roots[doc]
   for t in root.findall('.//table-wrap'):
    identifier=t.get('id');rows=[(i,[txt(v) for v in r if v.tag in ['td','th']]) for i,r in enumerate(t.findall('.//tr'))]
    raw=corpus.execute('select table_id from raw_tables_v11 where source_sha256=? and locator=?',(docs[doc]['sha256'],'XML table-wrap '+identifier)).fetchone();assert raw
    key=unit(doc,identifier,'XML table-wrap '+identifier,rows[0][1],rows,raw[0],'own_xml_table',txt(t.find('caption')),txt(t.find('table-wrap-foot')))
    xmlunits[(doc,identifier)]=(key,dict(rows))
  def fact(doc,sample,key,row,col,field,value_raw,unit_name,method,component='whole',status='own_reported_value_method_qualified_not_model_admission',qualification=''):
   parts={'whole':r'^\s*(\d+(?:\.\d+)?)\s*$','leading':r'^\s*(\d+(?:\.\d+)?)','parenthetical_percent':r'\((\d+(?:\.\d+)?)%\)'}
   match=re.search(parts[component],value_raw);token=match[1] if match else None;value=float(token) if token is not None else None
   if value is None:status='author_dash_or_NA_not_zero_detection_status_not_inferred'
   cur=c.execute('insert into material_facts(material_key,field_name,value,raw_value,unit,method,table_key,row_ordinal,column_ordinal,source_sha256,review_status,training_eligible) values(?,?,?,?,?,?,?,?,?,?,?,0)',(material(docs[doc]['doi'],sample),field,value,value_raw,unit_name,method,key,row,col,docs[doc]['sha256'],status))
   c.execute('insert into value_components_v3 values(?,?,?,?)',(cur.lastrowid,component,token,qualification))
  # MNS pore main values plus author-reported parenthetical contributions.
  key,rows=xmlunits[('Macadamia','tbl1')]
  mf=[('BET_surface_area_m2_g','m2/g','BET'),('micropore_surface_area_m2_g','m2/g','t-plot'),('mesopore_surface_area_m2_g','m2/g','author SBET-Smicro'),('total_pore_volume_cm3_g','cm3/g','N2 P/P0=0.998'),('micropore_volume_cm3_g','cm3/g','t-plot'),('mesopore_volume_cm3_g','cm3/g','author Vtotal-Vmicro'),('micro_to_meso_surface_area_ratio','ratio','author reported'),('micro_to_meso_pore_volume_ratio','ratio','author reported')]
  for i in range(1,5):
   r=rows[i]
   for col,(field,un,method) in enumerate(mf,1):fact('Macadamia',r[0],key,i,col,field,r[col],un,method,'leading',status='own_reported_partition_conflict_frozen' if i==1 and col==6 else 'own_reported_value_method_qualified_not_model_admission')
   for col,field in [(2,'micropore_surface_fraction_pct'),(3,'mesopore_surface_fraction_pct'),(5,'micropore_volume_fraction_pct'),(6,'mesopore_volume_fraction_pct')]:fact('Macadamia',r[0],key,i,col,field,r[col],'%','reported contribution to matching total','parenthetical_percent')
  key,rows=xmlunits[('Macadamia','tbl2')]
  fields=['XPS_C_at_pct','XPS_O_at_pct','XPS_O_C_reported_ratio','XPS_C1s_C_C_envelope_pct','XPS_C1s_C_O_envelope_pct','XPS_C1s_C_double_O_envelope_pct','XPS_O1s_C_double_O_envelope_pct','XPS_O1s_C_O_envelope_pct','XPS_O1s_O_C_double_O_envelope_pct']
  for i in range(2,6):
   r=rows[i]
   for col,field in enumerate(fields,1):fact('Macadamia',r[0],key,i,col,field,r[col],'at%' if col<3 else ('ratio' if col==3 else '% of corresponding element envelope'),'XPS; envelope fractions not global elemental fraction')
  # Hurd own XPS, yields, envelope-specific fractions and method-qualified pore data.
  for table,start,mappings in [('tbl1',2,[(1,'XPS_C_at_pct','at%'),(2,'XPS_O_at_pct','at%'),(3,'XPS_C_O_reported_ratio','ratio'),(4,'reported_product_yield_pct','% of raw dry hemp mass')]),('tbl2',2,[(i+1,'XPS_C1s_'+s+'_envelope_pct','% of C1s envelope') for i,s in enumerate(['C_C','C_OH','C_double_O','O_C_double_O'])]),('tbl3',2,[(i+1,'XPS_O1s_'+s+'_envelope_pct','% of O1s envelope') for i,s in enumerate(['O_double_C_OH','C_double_O','C_OH'])]),('tbl4',2,[(1,'BET_surface_area_m2_g','m2/g'),(2,'mesopore_to_BET_surface_area_ratio','ratio'),(3,'total_pore_volume_cm3_g','cm3/g'),(4,'micropore_volume_cm3_g','cm3/g'),(5,'mesopore_volume_cm3_g','cm3/g'),(6,'meso_to_micro_pore_volume_ratio','ratio'),(7,'DFT_pore_diameter_nm','nm')])]:
   key,rows=xmlunits[('HempNaOH',table)]
   for i in range(start,max(rows)+1):
    r=rows[i]
    for col,field,un in mappings:fact('HempNaOH',r[0],key,i,col,field,r[col],un,'XPS envelope-qualified or raw-mass yield' if table!='tbl4' else ('BET' if col==1 else 'author reported; micro/meso volume and diameter DFT per footnote'))
  # Popcorn pore properties. Rowspan grouping is checked before carrying sample names.
  key,rows=xmlunits[('Popcorn','tbl3')]
  fields=[('BET_surface_area_m2_g','m2/g'),('total_pore_volume_cm3_g','cm3/g'),('average_pore_width_nm','nm'),('reported_mesopore_volume_fraction_pct','% reported'),('micropore_surface_area_m2_g','m2/g'),('micropore_to_BET_surface_area_ratio','ratio'),('micropore_volume_cm3_g','cm3/g'),('micropore_volume_fraction_pct','% reported')]
  for i in range(1,8):
   for col,(field,un) in enumerate(fields,1):fact('Popcorn',rows[i][0],key,i,col,field,rows[i][col],un,'BET; micropore t-plot; other reported pore metric retains author basis')
  key,rows=xmlunits[('Popcorn','tbl5')];sample=None
  peaknames=['C_double_C','C_C','C_O_C_OH','C_double_O','COOH_COOR']
  table=roots['Popcorn'].find(".//table-wrap[@id='tbl5']")
  for i in range(1,36):
   r=rows[i]
   if len(r)==4:
    sample=r[0];assert table.findall('.//tr')[i][0].get('rowspan')=='5';offset=1
   else:assert len(r)==3;offset=0
   peak=peaknames[(i-1)%5]
   for col,field,un in [(offset+1,'XPS_C1s_'+peak+'_binding_energy_eV','eV'),(offset+2,'XPS_C1s_'+peak+'_envelope_pct','% of C1s envelope')]:fact('Popcorn',sample,key,i,col,field,r[col],un,'XPS C1s fitted component; not global elemental abundance')
  def prose_unit(doc,index,header,rows):
   value=txt(paragraphs[doc][index]);key=unit(doc,'own_body_p'+str(index),'XML body//p zero-based index'+str(index),header,list(enumerate(rows,1)),kind='own_narrative_cells',caption='Reviewed own paragraph '+str(index),footnote='Numeric rows manually bound to this paragraph; not an original table.')
   return key,value
  for doc,index,field,unit_name,method,values in [
    ('Macadamia',19,'Raman_ID_IG','ratio','reported D/G intensity ratio',[('C-MNS','0.85'),('AC-MNS-1','0.92'),('AC-MNS-2','0.98'),('AC-MNS-3','1.02')]),
    ('Macadamia',38,'water_contact_angle_deg','degree','5uLwater;5min;5positions mean',[('AC-MNS-1','83.9'),('AC-MNS-2','58.6'),('AC-MNS-3','51.0')]),
    ('HempNaOH',26,'Raman_IG_ID','ratio','reported G/D intensity ratio,not ID/IG',[('Hurd-BC','1.47'),('Hurd-1','1.03'),('Hurd-2','1.05'),('Hurd-3','1.06'),('Hurd-4','1.09'),('AB520Y','0.88')]),
    ('HempNaOH',25,'Boehm_total_acidic_groups_mmol_g','mmol/g','Boehm titration;approximately',[('Hurd-1','1.42'),('Hurd-2','1.24'),('Hurd-3','1.12'),('Hurd-4','0.93'),('AB520Y','0.22')]),
    ('Popcorn',41,'Raman_ID1_IG','ratio','reported fitted D1/G,not generic unqualified D/G',[('POP','1.32'),('KPOP-12','1.61')])]:
   rows=[list(v) for v in values];key,paragraph=prose_unit(doc,index,['sample',field],rows)
   for i,r in enumerate(rows,1):assert r[1] in paragraph;fact(doc,r[0],key,i,1,field,r[1],unit_name,method)
  # Named SI tables; rows with merged cells expanded only as visually reviewed.
  for spec in PDF_TABLES:
   key=unit(spec['doc'],spec['id'],f"PDF p{spec['page']} {spec['id']}",spec['header'],list(enumerate(spec['rows'],1)),spec['raw'],'own_and_comparison_pdf_table',caption=spec['id'])
   if spec['doc']=='Macadamia_SI':
    for i,r in enumerate(spec['rows'],1):
     for col,element in enumerate(['C','O','K'],1):fact(spec['doc'],r[0],key,i,col,'EDS_'+element+'_at_pct',r[col],'at%','SEM-EDS atom% explicitly in source;notXPS')
   if spec['doc']=='CNF_MWCNT_SI':
    for i,r in enumerate(spec['rows'],1):
     sample='CMU_block_'+r[0]+'_layers'
     for col,field,un in [(0,'printed_layer_count','layers'),(1,'electrode_height_mm','mm'),(2,'electrode_area_cm2','cm2'),(3,'mass_loading_mg_cm2','mg/cm2')]:fact(spec['doc'],sample,key,i,col,field,r[col],un,'own SI TableS4;geometry of each final printed composite')
   if spec['id']=='SI_TableS2':
    for i,r in enumerate(spec['rows'][:8],1):c.execute('insert into outcome_observations_v3 values(?,?,?,?,0)',('CE_Hurd_'+str(i),material(H,r[0]),key,json.dumps(dict(metric='coulombic_efficiency_pct',value=float(r[3]),reported_current_A_g=float(r[1]),electrolyte='H2SO4',concentration_mol_L=1,system='3E',locator='SI p6 TableS2;merged current/electrolyte cells visually reviewed',not_cycle_retention=True),ensure_ascii=False)))
  # Composite characterization is generic; do not transplant its BET into all layers.
  vals=[['CMU_characterized_block_layer_unspecified','BET_surface_area_m2_g','171.76','m2/g'],['CMU_characterized_block_layer_unspecified','XPS_C_at_pct','87.86','at%'],['CMU_characterized_block_layer_unspecified','XPS_O_at_pct','7.63','at%'],['CMU_characterized_block_layer_unspecified','XPS_N_at_pct','4.51','at%'],['CMU_characterized_block_layer_unspecified','Raman_ID_IG','0.79','ratio'],['CMU_characterized_block_layer_unspecified','DFT_micropore_peak_nm','1.17','nm']]
  key,paragraph=prose_unit('CNF_MWCNT',14,['sample','field','value','unit'],vals)
  for i,r in enumerate(vals,1):assert r[2] in paragraph;fact('CNF_MWCNT',r[0],key,i,2,r[1],r[2],r[3],'BET/XPS/Raman/DFT reported own generic block;layer binding not explicit')
  # All test rows retain one DOI source group; repeated forms share physical_test_group.
  def cap(doc,sample,key,row,col,raw,system,electrolyte,molar,current,un='F/g',basis='author_reported',extra=None):
   conditions=dict(capacitance_basis=basis,physical_test_group=docs[doc]['doi']+'#'+key.split('#')[-1]+'#'+str(row),mass_denominator='author_reported_unification_not_assumed',reference_electrode='Ag/AgCl' if doc=='HempNaOH' and system=='3E' else ('Hg/HgO in1MNaOH' if doc=='Macadamia' and system=='3E' else None))
   conditions.update(extra or {})
   ident=docs[doc]['doi']+'#'+key.split('#')[-1]+'#'+str(row)+'#'+str(col)
   c.execute('insert into capacitance_observations values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,0)',(ident,material(docs[doc]['doi'],sample),key,row,col,float(raw),raw,un,'GCD',system,electrolyte,molar,current,None,json.dumps(conditions,ensure_ascii=False),'own_reported_candidate_purpose_review_separate','doi:'+docs[doc]['doi']));return ident
  vals=[['C-MNS','1','6'],['AC-MNS-1','1','153'],['AC-MNS-2','1','158'],['AC-MNS-3','1','170']];key,_=prose_unit('Macadamia',39,['sample','current_A_g','capacitance_F_g'],vals)
  for i,r in enumerate(vals,1):cap('Macadamia',r[0],key,i,2,r[2],'3E','KOH',6,1,basis='single_working_carbon_electrode',extra={'voltage_lower_V':-1,'voltage_upper_V':0,'estimated_measurement_error_pct':[3,5],'active_mass_mg':.015,'current_binding':'ownFigure6c;paragraph39'})
  key,rows=xmlunits[('Macadamia','tbl4')]
  for i in range(1,6):
   r=rows[i]
   for col,un,basis in [(1,'F/g','device_total_two_electrode_active_mass'),(2,'mF/cm2','device_author_reported_areal'),(3,'F/cm3','device_author_reported_volumetric')]:cap('Macadamia','AC-MNS-3',key,i,col,r[col],'2E_symmetric','KOH',6,float(r[0]),un,basis,{'voltage_lower_V':0,'voltage_upper_V':1,'method_binding':'section2;Figure8;Table4','electrode_mass_per_side_mg':3.4,'electrode_mass_sd_mg':.12})
  for index,system,values,molar,electrolyte in [(39,'3E',[['Hurd-1','0.3','518'],['Hurd-2','0.3','576'],['Hurd-3','0.3','603'],['Hurd-4','0.3','725'],['AB520Y','0.3','295'],['Hurd-4','0.5','538'],['Hurd-4','1.0','435'],['Hurd-4','5.0','268'],['Hurd-4','10.0','151']],1,'H2SO4'),(44,'2E_symmetric',[['Hurd-1','0.3','29'],['Hurd-2','0.3','19'],['Hurd-3','0.3','38'],['Hurd-4','0.3','39'],['AB520Y','0.3','18'],['Hurd-4','0.5','38'],['Hurd-4','1.0','36'],['Hurd-4','3.0','31'],['Hurd-4','5.0','30']],None,'TEABF4_organic_solvent_not_explicit_in_reviewed_methods')]:
   key,paragraph=prose_unit('HempNaOH',index,['sample','current_A_g','capacitance_F_g'],values)
   for i,r in enumerate(values,1):assert r[2] in paragraph;cap('HempNaOH',r[0],key,i,2,r[2],system,electrolyte,molar,float(r[1]),basis='single_working_electrode' if system=='3E' else 'device_total_two_electrode_mass',extra={'voltage_lower_V':0,'voltage_upper_V':1 if system=='3E' else 2.5,'current_binding':'methods and own results paragraph'+str(index)})
  key,rows=xmlunits[('Popcorn','tbl6')]
  for i in range(1,5):
   r=rows[i]
   cap('Popcorn',r[0],key,i,1,r[1],'2E_symmetric','TEABF4_in_propylene_carbonate',1,1,basis='device_reported_Ccp',extra={'voltage_lower_V':0,'voltage_upper_V':2.7,'current_binding':'Table6 caption andFigure18a'})
   cap('Popcorn',r[0],key,i,2,r[2],'2E_symmetric','TEABF4_in_propylene_carbonate',1,1,basis='author_single_electrode_Cs_factor4_of_same_device_Ccp',extra={'voltage_lower_V':0,'voltage_upper_V':2.7,'duplicate_target_convention_of_column1':True,'author_equation':'ownEq8 Cs=4Ccp;rounded table values preserved'})
  values=[[f'CMU_block_{n}_layers',str(current),str(value)] for n,low,high in [(3,2.61,1.97),(4,3.31,2.39),(5,3.82,2.65),(6,4.2,2.81)] for current,value in [(2,low),(30,high)]]
  key,_=prose_unit('CNF_MWCNT',17,['sample','reported_current_mA_cm2','capacitance_F_cm2'],values)
  for i,r in enumerate(values,1):cap('CNF_MWCNT',r[0],key,i,2,r[2],'3E','H2SO4',1,None,'F/cm2','printed_working_electrode_area',{'reported_current_mA_cm2':float(r[1]),'reference_electrode':'mercury/mercurous_sulfate','protocol_locator':'SIp6','intentional_MWCNT_composite':True})
  # Process stages are not confused with electrode drying or sorption degassing.
  for doi,doc,index,samples in [(M,'Macadamia',6,['C-MNS','AC-MNS-1','AC-MNS-2','AC-MNS-3']),(H,'HempNaOH',8,['Hurd-BC','Hurd-1','Hurd-2','Hurd-3','Hurd-4']),(P,'Popcorn',8,['POP','KPOP-4','KPOP-6','KPOP-8','KPOP-10','KPOP-10n','KPOP-12'])]:
   for sample in samples:
    if doi==M:
     stages=[dict(stage='carbonization',temperature_C=600,duration_h=18,atmosphere='oxygen_limited',heating_rate_C_min=None)]
     if sample!='C-MNS':stages.append(dict(stage='chemical_activation',temperature_C=800,duration_h=1,heating_rate_C_min=5,atmosphere='Ar',gas_flow_L_min=.2,agent='KOH',carbon_to_activator_mass_ratio=[1,int(sample[-1])],postwash='1MHCl thenDIwaterneutral',yield_pct_relative_to_char={'AC-MNS-1':74,'AC-MNS-2':66,'AC-MNS-3':52}[sample]))
    elif doi==H:
     stages=[dict(stage='carbonization',temperature_C=500,duration_h=2,heating_rate_C_min=5,atmosphere='N2',gas_flow_sccm=500)]
     if sample!='Hurd-BC':stages.append(dict(stage='chemical_activation',temperature_C=720,duration_h=1,heating_rate_C_min=5,atmosphere='Ar',gas_flow_sccm=500,agent='NaOH',carbon_to_activator_mass_ratio=[1,int(sample[-1])],postwash='1MHCl100C4h thenDIwaterneutral',yield_basis='dry raw hemp mass,not char mass'))
    else:stages=[dict(stage='calcination_after_torch_precarbonization',temperature_C=800,duration_h=2,heating_rate_C_min=10,atmosphere='N2' if sample.endswith('n') else 'air',air_flow_L_min=None if sample.endswith('n') else 7.5,agent=None if sample=='POP' else 'KNO3',popcorn_mass_g=10,activator_mass_g=0 if sample=='POP' else int(re.search(r'KPOP-(\d+)',sample)[1]),postwash='35%HCl30min thenDIwaterneutral',precarbonization_temperature_C=None)]
    c.execute('insert into synthesis_stages_v3 values(?,?,?,?)',(material(doi,sample),doc,'XML body//p zero-based index'+str(index),json.dumps(stages,ensure_ascii=False)))
  # Earlier purple-corncob source: bind its already available synthesis to four own samples.
  purple=dict(c.execute("select * from source_documents where document_key='purple_main'").fetchone());docs['purple_main']=dict(doi=purple['doi'],path=purple['path'],sha256=purple['sha256'],role='main')
  for dose in [5,10,20,30]:
   sample=f'AC-{dose}%';stages=[dict(stage='direct_KOH_activation',temperature_C=700,duration_h=1,heating_rate_C_min=5,atmosphere='N2',agent='KOH',reported_KOH_concentration_pct=dose,percentage_basis='not_explicit;not a carbon:KOH mass ratio',carbon_to_activator_mass_ratio=None,precursor='purple corncob',postwash='ultrapure water pH6.5-7')]
   c.execute('insert into synthesis_stages_v3 values(?,?,?,?)',(mk(purple['doi'],sample),'purple_main','XML body//p zero-based index11',json.dumps(stages,ensure_ascii=False)))
  issues=[('MNS_char_Vmeso',M,'C-MNS',dict(kind='explicit_partition_conflict',total=.176,micro=.140,reported_meso=.36,reported_meso_fraction_pct=20.5,reported_micro_meso_ratio=3.89,action='Own footnote saysVmeso=Vtotal-Vmicro;keep0.36 and all author numbers,do not silently repair to0.036;canonical meso value frozen.')),
   ('Hurd2_partition',H,'Hurd-2',dict(kind='method_qualified_partition_not_assumed_exhaustive',total=1.08,DFT_micro=.65,DFT_meso=.18,action='Keep distinct methods and raw reported volumes;do not replace total or fill a missing volume from subtraction.')),
   ('Hurd_Raman_direction',H,'all',dict(kind='Raman_IG_ID_not_ID_IG',action='Store original IG/ID;any inverse appears explicitly derived in auxiliary features,not a measured ID/IG field.')),
   ('Hurd_CE_not_retention',H,'Hurd-4',dict(kind='coulombic_efficiency_not_cycle_retention',coulombic_efficiency_pct=61.1,current_A_g=.3,cycle_retention_pct=78,cycle_count=10000,action='Separate outcome task and cycling label;no use of same-test CE as pretest input feature.')),
   ('Hurd_cycle_baseline',H,'Hurd-4',dict(kind='separate_test_baselines',rate_test_cap_at_05A_g=38,cycling_initial_F_g=28,cycling_terminal_F_g=22,reported_cycle_retention_pct=78,action='Retain within-cycle baseline28,not substitute fresh rate-test38 or recalculate authors rounded78.')),
   ('Popcorn_capacitance_basis',P,'all',dict(kind='device_vs_factor4_single_electrode_convention',device_Ccp=23.30,author_single_electrode_Cs=93.20,action='Same physical test,two conventions;do not count as independent experiments or mix with measured3E capacitance.')),
   ('Popcorn_current_range',P,'all',dict(kind='method_results_current_range_difference',method_A_g=[.5,5],results_A_g=[.5,1,2,5,10],action='Keep both scopes;Table6 at1A/g independently bound,do not infer unavailable10A/g numerical capacitance.')),
   ('CNF_precursor_final_basis',C,'all',dict(kind='intentional_CNT_and_precursor_mass_basis',MWCNT_to_CNF=[7,3],MWCNT_to_urea=[1,5],final_MWCNT_fraction=None,action='Retain composite view;70percent refers to carbon building blocks,not final char fraction or all CMU dry solids.'))]
  c.executemany('insert into scientific_issues values(?,?,?,?)',[(i,d,s,json.dumps(v,ensure_ascii=False)) for i,d,s,v in issues])
  # New source-specific cycling reports remain candidates, not main cycling membership.
  cycle=dict(source_group='doi:'+H,sample_name='Hurd-4',system='2E_symmetric',method='GCD',electrolyte='TEABF4_organic_solvent_not_explicit_in_reviewed_methods',concentration_mol_L=None,reported_current_A_g=.5,cycle_voltage_lower_V=0,cycle_voltage_upper_V=2.5,cycle_count=10000,retention_pct=78,retention_relation='eq',initial_capacitance_F_g=28,terminal_capacitance_F_g=22,baseline_reference='author own cycling initial;exact cycle index unknown',locator='ownFigure9f,bodyparagraph44,methodsparagraph11',scientific_gate_passed=False,current_cycle_database_membership=False,source_sha256=docs['HempNaOH']['sha256'],evidence_source_path=docs['HempNaOH']['path'],unresolved=['organic separate purpose;not aqueous3E main','solvent/concentration not explicit in reviewed methods','exact plotted baseline crosscheck pending'])
  c.execute('insert into test_candidates values(?,?,?,0)',('LP3_Hurd4_organic_cycle',material(H,'Hurd-4'),json.dumps(cycle,ensure_ascii=False)))
  # Purpose-specific human-visible review. This does not flip immutable raw training flags.
  for row in c.execute('select x.*,m.doi,m.sample_name,m.material_stage from capacitance_observations x join materials m using(material_key)').fetchall():
   cond=json.loads(row['conditions_json']);pure=row['doi'] in ['10.1021/acsenvironau.3c00048',M,H]
   measured=row['method']=='GCD' and row['value'] is not None and row['current_A_g'] is not None
   eligible=pure and measured and row['unit']=='F/g' and row['system'] in ['3E','2E_symmetric'] and row['electrolyte'] in ['H2SO4','KOH'] and row['concentration_mol_L'] is not None and row['material_stage'] not in ['commercial_reference_origin_not_reported','intermediate_biochar_not_activated']
   purpose='reported_aqueous_3e_GCD_capacitance' if row['system']=='3E' else 'reported_aqueous_2e_GCD_device_capacitance'
   reason='Explicit own GCD value/current/configuration/electrolyte binding;pretest features separately masked;DOI grouped.' if eligible else 'Outside this auxiliary purpose or missing its evidence;raw candidate retained,not rejected for all purposes.'
   c.execute('insert into auxiliary_gcd_reviews_v3 values(?,?,?,?,?)',(row['observation_id'],purpose,int(eligible),reason,'Agent scientific source review,not human confirmation;no real model fit or formal cycling admission.'))
  c.execute('''create view auxiliary_reported_GCD_v3 as select x.*,m.doi,m.sample_name,m.material_stage,r.purpose,r.reason as admission_reason
      from capacitance_observations x join materials m using(material_key) join auxiliary_gcd_reviews_v3 r using(observation_id) where r.eligible=1''')
  c.commit()
 write(OUT/'table_review_receipt.json',receipts);write(OUT/'PDF_transcriptions.json',PDF_TABLES)
 write(OUT/'source_protection.json',dict(documents=docs,parent=dict(path=PARENT.relative_to(ROOT).as_posix(),sha256=sha(PARENT)),corpus=dict(path=CORPUS.relative_to(ROOT).as_posix(),sha256=sha(CORPUS)),cycling_pointer=json.loads((ROOT/'data/current_database.json').read_text('utf8'))))
 verify()

def verify():
 checks=[]
 def check(name,ok):
  if not ok:raise AssertionError(name)
  checks.append(name)
 proof=json.loads((OUT/'source_protection.json').read_text('utf8'))
 for key,row in proof['documents'].items():check('original_'+key,sha(ROOT/row['path'])==row['sha256'])
 for key in ['parent','corpus']:check('unchanged_'+key,sha(ROOT/proof[key]['path'])==proof[key]['sha256'])
 check('cycling_pointer_unchanged',json.loads((ROOT/'data/current_database.json').read_text('utf8'))==proof['cycling_pointer'])
 with closing(ro(DB)) as c,closing(ro(PARENT)) as old:
  c.row_factory=sqlite3.Row
  check('integrity',c.execute('pragma integrity_check').fetchone()[0]=='ok');check('foreign_keys',not c.execute('pragma foreign_key_check').fetchall())
  for table in ['identity_inventory','materials','material_facts','capacitance_observations','test_candidates','scientific_issues']:
   current={tuple(r) for r in c.execute('select * from '+table)};check('parent_preserved_'+table,all(tuple(r) in current for r in old.execute('select * from '+table)))
  for rec in json.loads((OUT/'table_review_receipt.json').read_text('utf8')):
   if rec['kind']!='own_xml_table':continue
   doc=proof['documents'][rec['document']];r=E.parse(ROOT/doc['path']).getroot();ident=rec['locator'].removeprefix('XML table-wrap ');table=r.find(f".//table-wrap[@id='{ident}']")
   for i,row in enumerate(table.findall('.//tr')):check('XML_row_'+rec['table_key']+'_'+str(i),[txt(v) for v in row if v.tag in ['td','th']]==json.loads(c.execute('select cells_json from transcribed_rows where table_key=? and row_ordinal=?',(rec['table_key'],i)).fetchone()[0]))
  for row in c.execute('select f.*,v.component,v.numeric_token from material_facts f join value_components_v3 v using(fact_id)'):
   cells=json.loads(c.execute('select cells_json from transcribed_rows where table_key=? and row_ordinal=?',(row['table_key'],row['row_ordinal'])).fetchone()[0]);check('source_cell_'+str(row['fact_id']),cells[row['column_ordinal']]==row['raw_value']);check('number_'+str(row['fact_id']),row['value'] is None if row['numeric_token'] is None else row['value']==float(row['numeric_token']))
   pattern={'whole':r'^\s*(\d+(?:\.\d+)?)\s*$','leading':r'^\s*(\d+(?:\.\d+)?)','parenthetical_percent':r'\((\d+(?:\.\d+)?)%\)'}[row['component']]
   match=re.search(pattern,row['raw_value']);check('component_'+str(row['fact_id']),row['numeric_token']==(match[1] if match else None))
  import pypdfium2 as pdf
  for spec in PDF_TABLES:
   doc=proof['documents'][spec['doc']];document=pdf.PdfDocument(str(ROOT/doc['path']));native=re.sub(r'\s+','',document[spec['page']-1].get_textpage().get_text_range())
   for i,row in enumerate(spec['rows'],1):
    # Merged SI cells are expanded by the documented visual check; validate numeric tails independently.
    numeric=[v for v in row if re.fullmatch(r'\d+(?:\.\d+)?',v)]
    check('PDF_numeric_row_'+spec['doc']+'_'+spec['id']+'_'+str(i),all(v in native for v in numeric))
   if spec['page'] in [3,6,24]:check('SI_visual_evidence_'+spec['doc'],(OUT/'evidence'/f"{spec['doc']}_p{spec['page']}.png").is_file())
  parent_ids={r[0] for r in old.execute('select observation_id from capacitance_observations')}
  for row in c.execute('select * from capacitance_observations'):
   if row['observation_id'] in parent_ids:continue
   cells=json.loads(c.execute('select cells_json from transcribed_rows where table_key=? and row_ordinal=?',(row['table_key'],row['row_ordinal'])).fetchone()[0]);check('cap_original_cell_'+row['observation_id'],cells[row['column_ordinal']]==row['raw_value'] and float(row['raw_value'])==row['value'])
   check('cap_group_'+row['observation_id'],row['source_group'].startswith('doi:') and row['method']=='GCD' and row['scan_rate_mV_s'] is None)
  for row in c.execute('select s.*,m.doi,m.sample_name from synthesis_stages_v3 s join materials m using(material_key)'):
   stages=json.loads(row['stages_json']);check('stage_order_'+row['doi']+'_'+row['sample_name'],stages[0]['stage'] in ['carbonization','calcination_after_torch_precarbonization','direct_KOH_activation'])
   if row['doi']=='10.1021/acsenvironau.3c00048':check('purple_percent_not_massratio_'+row['sample_name'],stages[0]['carbon_to_activator_mass_ratio'] is None and stages[0]['temperature_C']==700 and stages[0]['duration_h']==1)
   if row['sample_name'].startswith('AC-MNS'):check('MNS_two_distinct_stages_'+row['sample_name'],[s['temperature_C'] for s in stages]==[600,800] and [s['duration_h'] for s in stages]==[18,1])
   if row['sample_name'] in ['Hurd-1','Hurd-2','Hurd-3','Hurd-4']:check('Hurd_two_distinct_stages_'+row['sample_name'],[s['temperature_C'] for s in stages]==[500,720] and [s['duration_h'] for s in stages]==[2,1])
  for sample in ['KPOP-8','KPOP-10','KPOP-10n','KPOP-12']:
   records=c.execute('select x.* from capacitance_observations x join materials m using(material_key) where m.doi=? and m.sample_name=?',(P,sample)).fetchall();check('Pop_same_test_conventions_'+sample,len(records)==2 and len({json.loads(r['conditions_json'])['physical_test_group'] for r in records})==1 and len({r['column_ordinal'] for r in records})==2)
  for doc,index,terms in [('Macadamia',10,['three-electrode','6 M KOH','Hg/HgO']),('Macadamia',39,['GCD','1 A','6, 153, 158, and 170']),('HempNaOH',10,['three-electrode','Ag/AgCl','1 M H2SO4']),('HempNaOH',11,['GCD','0.0 and 1.0 V']),('HempNaOH',39,['518','576','603','725','538','435','268','151'])]:
   root=E.parse(ROOT/proof['documents'][doc]['path']).getroot();paragraph=txt(root.findall('.//body//p')[index]);check('protocol_'+doc+'_'+str(index),all(t in paragraph for t in terms))
  for table in ['raw_table_queue','material_facts','capacitance_observations','test_candidates','outcome_observations_v3']:check('no_automatic_training_'+table,c.execute('select count(*) from '+table+' where training_eligible!=0 or training_eligible is null').fetchone()[0]==0)
  check('new_XPS_envelopes_qualified',c.execute("select count(*) from material_facts where fact_id>161 and field_name like '%envelope_pct' and unit not like '%envelope%'").fetchone()[0]==0)
  check('MNS_mesovol_original_frozen',tuple(c.execute("select value,review_status from material_facts f join materials m using(material_key) where m.doi=? and sample_name='C-MNS' and field_name='mesopore_volume_cm3_g'",(M,)).fetchone())==(.36,'own_reported_partition_conflict_frozen'))
  check('no_Hurd_BC_area_invented',c.execute("select count(*) from material_facts f join materials m using(material_key) where m.doi=? and sample_name='Hurd-BC' and field_name like 'BET%'",(H,)).fetchone()[0]==0)
  check('Hurd_IG_ID_separate',c.execute("select count(*) from material_facts f join materials m using(material_key) where m.doi=? and field_name='Raman_IG_ID'",(H,)).fetchone()[0]==6)
  aux=c.execute('select * from auxiliary_reported_GCD_v3').fetchall()
  check('auxiliary_expected_rows',len(aux)==25)
  check('auxiliary_unique_reports',len({r['observation_id'] for r in aux})==25)
  check('auxiliary_three_sources',len({r['source_group'] for r in aux})==3)
  check('auxiliary_3E_and_device_not_mixed',sum(r['system']=='3E' for r in aux)==20 and sum(r['system']=='2E_symmetric' for r in aux)==5)
  check('commercial_composite_not_in_pure_aux',all(r['sample_name']!='AB520Y' and r['doi']!=C for r in aux))
  check('no_CE_as_retention',c.execute('select count(*) from outcome_observations_v3').fetchone()[0]==8)
  count=lambda t:c.execute('select count(*) from '+t).fetchone()[0]
  numeric=c.execute('select count(*) from material_facts where value is not null').fetchone()[0]
  untouched=c.execute("select count(*) from raw_table_queue where review_state='automatic_candidate_unreviewed'").fetchone()[0]
  actual=count('reviewed_tables')-c.execute("select count(*) from extraction_units_v3 where kind='own_narrative_cells'").fetchone()[0]
  summary=dict(identity_catalogue_entries=480,raw_table_candidates=959,raw_table_rows=6121,cumulative_reviewed_source_publications=count('reviewed_sources'),cumulative_materials=count('materials'),cumulative_selected_material_cells=count('material_facts'),cumulative_numeric_material_facts=numeric,new_materials=count('materials')-24,new_numeric_material_facts=numeric-157,new_non_numeric_material_cells=count('material_facts')-161-(numeric-157),reviewed_table_units=actual,reviewed_evidence_units=count('reviewed_tables'),raw_candidates_touched=959-untouched,raw_candidates_untouched=untouched,capacitance_records=count('capacitance_observations'),numeric_capacitance_values=c.execute('select count(*) from capacitance_observations where value is not null').fetchone()[0],unreported_capacitance_cells=2,cycling_candidates=count('test_candidates'),scientific_issues=count('scientific_issues'),historical_selected_fact_references=725,historical_fact_references_with_same_source_table_candidates=171,synthesis_materials=count('synthesis_stages_v3'),coulombic_efficiency_outcomes=8,auxiliary_aqueous_3e_GCD_rows=20,auxiliary_aqueous_2e_GCD_rows=5,auxiliary_independent_DOI_groups=3,new_training_admissions=0,formal_cycling_admissions=0,auxiliary_purpose_reviewed_input_rows=25,model_fits=0,all_literature_fully_utilized=False,scope_note='Material cells and tests are not independent papers;whole table snapshots contain comparisons. Auxiliary25rows are reviewed for two separate capacitance purposes,not25new cycling endpoints or25sources. No fitted model or performance claim.')
 report=dict(status='passed',checks=len(checks),check_names=list(checks),model_fits=0,scientific_goal_complete=False)
 sealed=(OUT/'merge_manifest.json').exists()
 for filename,value in [('summary.json',summary),('verification.json',report)]:
  if sealed:check('sealed_report_'+filename,json.loads((OUT/filename).read_text('utf8'))==value)
  else:write(OUT/filename,value)
 if sealed:
  for item in json.loads((OUT/'merge_manifest.json').read_text('utf8'))['outputs']:check('hash_'+item['path'],sha(ROOT/item['path'])==item['sha256'])
 print(json.dumps(dict(status='passed',checks=report['checks'],summary=summary),ensure_ascii=False))

def seal():
 if (OUT/'merge_manifest.json').exists():raise FileExistsError('Do not reseal.')
 verify();files=sorted([p for p in OUT.rglob('*') if p.is_file()]+[Path(__file__).resolve(),ROOT/'data/literature_v3.py',ROOT/'tools/check_literature_auxiliary_inputs_v3.py'])
 write(OUT/'merge_manifest.json',dict(kind='literature_evidence_pool_v3',parent_sha256=sha(PARENT),new_formal_cycling_admissions=0,model_fits=0,outputs=[dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p),bytes=p.stat().st_size) for p in files]))
 write(ROOT/'data/current_literature.json',dict(version='literature_pool_v3',directory=OUT.relative_to(ROOT).as_posix(),database_file=DB.name,sha256=sha(DB),api_module='data.literature_v3',scope='Material/process/test evidence with25purpose-reviewed aqueous auxiliary GCD inputs;not cycling main membership.'))
if __name__=='__main__':
 if len(sys.argv)!=2 or sys.argv[1] not in ['build','verify','seal']:raise SystemExit('build(one-use),verify(read-only),seal(one-use)')
 globals()[sys.argv[1]]()
