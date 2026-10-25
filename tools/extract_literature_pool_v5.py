"""Versioned selected-cell extraction: carbonization series and multiple electrolytes."""
from pathlib import Path
from contextlib import closing
from collections import Counter
import hashlib,json,re,sqlite3,sys,xml.etree.ElementTree as E,csv,io,math
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
OUT=ROOT/'文献全量利用复核_20261025/批次05_碳化系列与多电解液';DB=OUT/'literature_material_pool_v5.sqlite'
PARENT=ROOT/'文献全量利用复核_20261025/批次04_循环原图与新来源/literature_material_pool_v4.sqlite'
PARENT_SHA='090bb5ef701c68521806eb2b9c7aeb2b00100020ce090a81156421a0d5d3a7de'
CORPUS=ROOT/'全库复检与特征补提取_20261021/full_corpus_search_native.sqlite'
J='10.1016/j.isci.2026.117248';G='10.1021/acsomega.3c00816';A='10.1021/acsomega.5c05285'
SOURCES=[('Weigela',J,'三电极端点扩充_20261018/new_sources/PMC13521071/main.xml','7f70c9528ccbd1609ef8ed183a1208f9b2ae5ee76a31a9a541ea721ac776e856'),('Glycogen',G,'同体系文献补充_第二批_20261017/定向扩搜40至60篇_20261017/sources/OA041/main.xml','0245ed4c6b2e3c58e11578910237d73abc72e4153d8627cf9ba5e01ce0c68d0b'),('WoodApple',A,'数据补充_v07_20261018/sources/PMC12444587/main.xml','b25ba18bb87c6dd4ee4e9b663953db87ad841c01309a3c19403a78fef9ae062a')]
SI_TABLES=[
 ('SI_TableS2',8,['sample','XPS_C_at_pct','XPS_O_at_pct','XPS_N_at_pct'],[['NWJPC-0','89.56','9.54','0.9'],['NWJPC-1','89.66','8.62','1.72'],['NWJPC-2','77.06','8.12','14.83'],['NWJPC-3','81.18','9.25','9.57'],['NWJPC-4','90.22','6.05','3.37']]),
 ('SI_TableS3',10,['sample','XPS_C1s_C_C_C_double_C_envelope_pct','XPS_C1s_C_O_C_N_envelope_pct','XPS_C1s_C_double_O_C_N_envelope_pct','XPS_C1s_O_double_C_OH_envelope_pct'],[['NWJPC-0','61.02','17.68','4.18','17.12'],['NWJPC-1','62.87','12.07','8.12','16.94'],['NWJPC-2','43.75','35.54','8.07','12.6.'],['NWJPC-3','54.43','23.40','9.60','12.57'],['NWJPC-4','56.19','17.22','9.60','16.99']]),
 ('SI_TableS4',10,['sample','XPS_O1s_O_N_envelope_pct','XPS_O1s_C_O_C_C_OH_envelope_pct','XPS_O1s_O_double_C_O_envelope_pct'],[['NWJPC-0','-','76.86','23.14'],['NWJPC-1','28.93','58.63','12.44'],['NWJPC-2','35.73','52.83','11.44'],['NWJPC-3','28.80','57.01','14.19'],['NWJPC-4','30.98','42.26','26.76']])]
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def ro(p):return sqlite3.connect(Path(p).resolve().as_uri()+'?mode=ro',uri=True)
def txt(e):return ' '.join(''.join(e.itertext()).split()) if e is not None else ''
def mk(d,s):return 'literature:'+hashlib.sha256((d+'\0'+s).encode()).hexdigest()[:24]
def number(raw,component='whole'):
 raw=raw.replace(',','')
 if component=='mean':raw=raw.split('±')[0].strip()
 elif component=='uncertainty':raw=raw.split('±')[1].strip()
 return float(raw) if re.fullmatch(r'\d+(?:\.\d+)?',raw) else None

def build():
 if DB.exists() or (OUT/'merge_manifest.json').exists():raise FileExistsError('Never overwrite.')
 assert sha(PARENT)==PARENT_SHA
 assert sha(CORPUS)=='f2720c3e417904dad5857a6574cc72d5cf996f9b8716620d69594f11380c658c'
 docs={k:dict(doi=d,path=p,sha256=s,role='main') for k,d,p,s in SOURCES}
 for k,d,p in [('Weigela_SI',J,(OUT/'evidence/Weigela_mmc1.pdf').relative_to(ROOT).as_posix()),('Glycogen_SI',G,'同体系文献补充_第二批_20261017/定向扩搜40至60篇_20261017/sources/OA041/ao3c00816_si_001.pdf'),('WoodApple_SI',A,(OUT/'evidence/WoodApple_SI.pdf').relative_to(ROOT).as_posix()),('Weigela_Fig7',J,(OUT/'evidence/Weigela_gr7.webp').relative_to(ROOT).as_posix())]:docs[k]=dict(doi=d,path=p,sha256=sha(ROOT/p),role='SI' if k.endswith('_SI') else 'original_graphic')
 for d in docs.values():assert sha(ROOT/d['path'])==d['sha256']
 acquisition=json.loads((OUT/'attachment_acquisition.json').read_text('utf8'));was_receipt=json.loads((OUT/'WoodApple_attachment_receipt.json').read_text('utf8'))
 assert sha(ROOT/acquisition['selected_pdf']['path'])==acquisition['selected_pdf']['sha256']
 assert sha(ROOT/was_receipt['extracted_path'])==was_receipt['sha256']
 roots={k:E.parse(ROOT/p).getroot() for k,d,p,s in SOURCES};pp={k:r.findall('.//body//p') for k,r in roots.items()};receipt=[];units={}
 with closing(ro(PARENT)) as old,closing(sqlite3.connect(DB)) as c,closing(ro(CORPUS)) as corpus:
  old.backup(c);c.row_factory=sqlite3.Row;c.execute('pragma foreign_keys=on')
  c.execute('create table row_bindings_v5(table_key text references reviewed_tables,row_ordinal integer,record_json text,primary key(table_key,row_ordinal))')
  for k,d,p,s in SOURCES:
   assert d in [txt(x).lower() for x in roots[k].findall('.//article-id') if x.get('pub-id-type')=='doi']
   c.execute('insert into reviewed_sources values(?,?,?,?,?)',(d,p,s,txt(roots[k].find('.//article-title')),'Selected own tables,protocols andSI; not full-paper completion.'))
  for k,d in docs.items():c.execute('insert into source_documents values(?,?,?,?,?)',(k,d['doi'],d['path'],d['sha256'],d['role']))
  def material(doc,sample):
   canonical=sample.replace('NWJPC -','NWJPC-');d=docs[doc]['doi']
   if canonical!=sample:c.execute('insert or ignore into material_aliases_v3 values(?,?,?,?)',(d,sample,canonical,'Own table spacing only; same named series, not experimental merge.'))
   c.execute('insert or ignore into materials values(?,?,?,?)',(mk(d,canonical),d,canonical,'final_biomass_carbon_before_test'))
   return mk(d,canonical)
  def unit(doc,ident,locator,header,rows,kind='own_narrative_cells',raw=None,caption=''):
   key=docs[doc]['doi']+'#'+ident
   c.execute('insert into reviewed_tables values(?,?,?,?,?,?,?)',(key,docs[doc]['doi'],ident,caption or ident,json.dumps(header,ensure_ascii=False),'See source review and issues; blank cells and header hierarchy retained.',raw));c.execute('insert into table_source_links values(?,?,?)',(key,doc,locator))
   for i,row in rows:c.execute('insert into transcribed_rows values(?,?,?)',(key,i,json.dumps(row,ensure_ascii=False)))
   c.execute('insert into extraction_units_v3 values(?,?,?)',(key,kind,'Explicitly selected own cells only; not full source completion.'))
   if raw:c.execute('update raw_table_queue set review_state=? where table_id=?',('specified_own_rows_and_protocols_reviewed_remaining_figures_pending',raw))
   receipt.append(dict(table_key=key,document=doc,locator=locator,kind=kind,raw_table_id=raw,rows=len(rows)));return key
  def prose(doc,index,header,rows):return unit(doc,'own_body_p'+str(index),'XML body//p zero-based index'+str(index),header,list(enumerate(rows,1)))
  def fact(doc,sample,key,i,col,field,raw,un,method,component='whole'):
   value=number(raw,component);status='own_reported_value_method_qualified_not_model_admission'
   if value is None:status='author_dash_not_zero' if raw in ['-','–'] else 'malformed_author_numeric_string_not_silently_repaired'
   cur=c.execute('insert into material_facts(material_key,field_name,value,raw_value,unit,method,table_key,row_ordinal,column_ordinal,source_sha256,review_status,training_eligible) values(?,?,?,?,?,?,?,?,?,?,?,0)',(material(doc,sample),field,value,raw,un,method,key,i,col,docs[doc]['sha256'],status))
   c.execute('insert into value_components_v3 values(?,?,?,?)',(cur.lastrowid,'v5_'+component,str(value) if value is not None else None,method))
  def cap(doc,sample,key,i,col,raw,system,ely,molar,current,method='GCD',un='F/g',scan=None,eligible=False,status='own_reported_candidate_purpose_review_separate',extra=None):
   conditions=dict(capacitance_basis='single_working_electrode' if system=='3E' else 'author_reported',physical_test_group=docs[doc]['doi']+'#'+sample+'#'+system+'#'+method+'#'+str(molar),mass_denominator='author_reported_not_further_unified')
   conditions.update(extra or {});ident=key+'#'+str(i)+'#'+str(col);value=number(raw,'mean' if '±' in raw else 'whole');assert value is not None
   if '±' in raw:conditions.update(reported_uncertainty=number(raw,'uncertainty'),uncertainty_kind='author±type_not_assumed',value_relation='reported_mean')
   c.execute('insert into capacitance_observations values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,0)',(ident,material(doc,sample),key,i,col,value,raw,un,method,system,ely,molar,current,scan,json.dumps(conditions,ensure_ascii=False),status,'doi:'+docs[doc]['doi']))
   if eligible:c.execute('insert into auxiliary_gcd_reviews_v3 values(?,?,?,?,?)',(ident,'reported_aqueous_3e_GCD_capacitance',1,'Own exactGCD,aqueous3E; protocol andmethod independently bound.','Scientific source review only; not new cycling membership or real fit.'))
  def outcome(doc,sample,key,i,col,metric,raw,un,extra=None):
   record=dict(metric=metric,value=number(raw),raw_value=raw,unit=un,source_group='doi:'+docs[doc]['doi'],row_ordinal=i,column_ordinal=col,feature_role='response_not_pretest_material_feature');record.update(extra or {})
   c.execute('insert into outcome_observations_v3 values(?,?,?,?,0)',(key+'#outcome'+str(i)+'_'+str(col),material(doc,sample),key,json.dumps(record,ensure_ascii=False)))
  def cycle(doc,sample,ident,record):
   record.update(source_group='doi:'+docs[doc]['doi'],sample_name=sample,method='GCD',source_sha256=docs[doc]['sha256'],evidence_source_path=docs[doc]['path'],current_cycle_database_membership=False,scientific_gate_passed=False)
   c.execute('insert into test_candidates values(?,?,?,0)',('LP5_'+ident,material(doc,sample),json.dumps(record,ensure_ascii=False)))
  for doc,root in roots.items():
   for t in root.findall('.//table-wrap'):
    if t.get('id')=='undtbl1':continue
    rows=[(i,[txt(x) for x in row if x.tag in ['td','th']]) for i,row in enumerate(t.findall('.//tr'))];ident=t.get('id');raw=corpus.execute('select table_id from raw_tables_v11 where source_sha256=? and locator=?',(docs[doc]['sha256'],'XML table-wrap '+ident)).fetchone();assert raw
    key=unit(doc,ident,'XML table-wrap '+ident,rows[0][1],rows,'mixed_comparison_table' if doc=='WoodApple' and ident=='tbl3' else 'own_xml_table',raw[0],txt(t.find('caption')));units[(doc,ident)]=(key,dict(rows))
  # Five Weigela pore rows: comma thousands; combined meso+macro is not mesopore volume.
  key,rows=units[('Weigela','tbl1')]
  fields=[('BET_surface_area_m2_g','m2/g','BET'),('micropore_surface_area_m2_g','m2/g','author Smic; footer shareda onlystatesBETsurface method'),('micropore_volume_cm3_g','cm3/g','t-plot'),('meso_plus_macro_volume_cm3_g','cm3/g','BJH combined meso+macro,not canonical mesopore'),('total_pore_volume_cm3_g','cm3/g','BJH author total'),('BJH_average_pore_diameter_nm','nm','BJH')]
  for i in range(1,6):
   for col,(field,un,method) in enumerate(fields,1):fact('Weigela',rows[i][0],key,i,col,field,rows[i][col],un,method)
  key,rows=units[('Weigela','tbl2')]
  for i in range(1,6):
   for col,name in enumerate(['pyridinic','pyrrolic','graphitic','oxide'],1):fact('Weigela',rows[i][0],key,i,col,'XPS_N1s_'+name+'_envelope_pct',rows[i][col],'% of N1s envelope','Relative nitrogen-species distribution; captionat% not global nitrogen atomic fraction')
  for ident,page,header,rows in SI_TABLES:
   key=unit('Weigela_SI',ident,'PDF physical p'+str(page)+' '+ident,header,list(enumerate(rows,1)),'own_SI_table')
   for i,row in enumerate(rows,1):
    for col,field in enumerate(header[1:],1):fact('Weigela_SI',row[0],key,i,col,field,row[col],'at%' if ident=='SI_TableS2' else '% of corresponding element envelope','XPS element atomic%' if ident=='SI_TableS2' else 'XPS relative fitted element envelope; not global atomic%')
  vals=[[f'NWJPC-{i}',v] for i,v in enumerate(['1.01','1.10','1.15','1.26','1.32'])];key=prose('Weigela',34,['sample','Raman_ID_IG'],vals)
  for i,row in enumerate(vals,1):fact('Weigela',row[0],key,i,1,'Raman_ID_IG',row[1],'ratio','Raman; baseline-corrected and peak-deconvoluted')
  key,rows=units[('Weigela','tbl3')]
  for i in range(2,7):
   for col,current in enumerate([1,2,5,10,20],1):cap('Weigela',rows[i][0],key,i,col,rows[i][col],'3E','KOH',6,current,eligible=not(i==3 and col==1),status='body_table_133_vs_133_7_conflict' if i==3 and col==1 else 'own_exact_GCD_auxiliary',extra=dict(voltage_lower_V=-1,voltage_upper_V=0,reference_electrode='Hg/HgO',protocol_locator='WeigelaSIphysicalp3MethodsS2'))
  key=prose('Weigela',42,['sample','current_A_g','capacitance_F_g'],[['NWJPC-1','1','133']]);cap('Weigela','NWJPC-1',key,1,2,'133','3E','KOH',6,1,status='body_table_133_vs_133_7_conflict')
  vals=[[f'WJHC-{t}','1',v] for t,v in zip([140,160,180,200,220],['120.0','129.0','146.0','134.1','80.6'])];key=prose('Weigela',5,['sample','current_A_g','capacitance_F_g'],vals)
  for i,row in enumerate(vals,1):cap('Weigela',row[0],key,i,2,row[2],'3E','KOH',6,1,eligible=True,extra=dict(voltage_lower_V=-1,voltage_upper_V=0,reference_electrode='Hg/HgO',protocol_locator='WeigelaSIphysicalp3MethodsS2'))
  vals=[['NWJPC-2','0.5','178.3'],['NWJPC-2','20','147.4']];key=prose('Weigela',51,['sample','current_A_g','capacitance_F_g'],vals)
  for i,row in enumerate(vals,1):cap('Weigela',row[0],key,i,2,row[2],'2E_symmetric','KOH',6,float(row[1]),extra=dict(capacitance_basis='author2I_dt_over_single_electrode_m_dV',voltage_main_and_own_cycling_inset=[0,1],voltage_SI=[-1,0],protocol_locator='SIphysicalp3-4;Figure7',not_device_total_mass_target=True))
  cycle('Weigela','NWJPC-2','SSC',dict(system='2E_symmetric',electrolyte='KOH',concentration_mol_L=6,reported_current_A_g=5,cycle_voltage_lower_V=0,cycle_voltage_upper_V=1,competing_SI_voltage=[-1,0],cycle_count=10000,retention_pct=99.8,retention_relation='eq',baseline_reference='author initial; exactindexunknown; SIpreconditions5cycles0.5A/g then10000at5A/g',locator='ownFigure7Gfirst/lastcyclinginsets0..1V,p51;SIp3MethodsS2',unresolved=['Formal append tocycling library and final admissibility review pending'],voltage_decision='actual own cycling first/lastinsets and mainp51both0..1; retain SI-1..0 contradiction,do not treatdiagnosticCVascycleevidence'))
  cycle('Weigela','NWJPC-2','ZIHC',dict(system='2E_zinc_ion_hybrid',electrolyte='ZnSO4',concentration_mol_L=2,reported_current_A_g=5,cycle_voltage_lower_V=0,cycle_voltage_upper_V=1.8,cycle_count=10000,retention_pct=99.9,retention_metric='specific_capacity_mAh_g_not_capacitance',retention_relation='eq',locator='p74;SIphysicalp3-4',unresolved=['Zinc hybrid is separate response task,not purecarbon symmetric retention']))
  # Glycogen blank grouping is manually bound from the two independent table headers.
  gbind={i:(1000,h) for i,h in enumerate([.5,1,2,3,4,5,6,7],2)};gbind.update({10:(500,1),11:(750,1),12:(900,1),13:(1200,1)})
  gname=lambda i:'GC_'+str(gbind[i][0])+'C_'+str(gbind[i][1])+'h'
  key,rows=units[('Glycogen','tbl1')]
  for i,(temp,hours) in gbind.items():
   c.execute('insert into row_bindings_v5 values(?,?,?)',(key,i,json.dumps(dict(temperature_C=temp,duration_h=hours,basis='OwnTable1grouping;confirmedTable3sameT/timeseries;blankcellsretained'))))
   for col,field,un in [(3,'BET_surface_area_m2_g','m2/g'),(4,'micropore_volume_cm3_g','cm3/g'),(5,'mesopore_volume_cm3_g','cm3/g'),(6,'total_pore_volume_cm3_g','cm3/g'),(7,'reported_pore_diameter_A','angstrom')]:fact('Glycogen',gname(i),key,i,col,field,rows[i][col],un,'Reported BET/porosity table; diameter originalangstrom,not silently nm')
  key,rows=units[('Glycogen','tbl2')]
  for i in range(1,9):
   sample=gname(i+1)
   for field,component,un in [('Raman_ID_IG','mean','ratio'),('Raman_ID_IG_reported_uncertainty','uncertainty','ratio')]:fact('Glycogen',sample,key,i,2,field,rows[i][2],un,'Raman reported mean±uncertainty; uncertaintytype not guessed',component)
   fact('Glycogen',sample,key,i,3,'Raman_derived_crystallite_La_nm',rows[i][3],'nm','Author derived from sameID/IG and532nm; not independent measurement')
  key,rows=units[('Glycogen','tbl3')]
  for i,(temp,hours) in gbind.items():
   cap('Glycogen',gname(i),key,i,3,rows[i][3],'3E','ethaline_ChCl_EG_1to2',None,1,extra=dict(temperature_C=30,reference_electrode='silver_wire_pseudoreference',initial_capacitance_cycle_index=1,protocol_locator='SIphysicalp3-4',not_ordinary_aqueous=True))
   cycle('Glycogen',gname(i),'GC'+str(i),dict(system='3E',electrolyte='ethaline_ChCl_EG_1to2',concentration_mol_L=None,temperature_C=30,reported_current_A_g=1,reference_electrode='silver_wire_pseudoreference',cycle_count=1000,retention_pct=number(rows[i][4],'mean'),reported_retention_uncertainty=number(rows[i][4],'uncertainty'),retention_raw=rows[i][4],retention_relation='reported_mean',baseline_reference='OwnTable3firstcyclecapacitance',initial_capacitance_F_g=number(rows[i][3],'mean'),initial_capacitance_reported_uncertainty=number(rows[i][3],'uncertainty'),locator='ownTable3,p70;SIphysicalp3-4',unresolved=['DES separate purpose; ordinaryaqueousmembershipnotapplicable','GCDcycling voltage directbinding stillneedsowncurve; CVwindowalone notassigned']))
  vals=[['GC_1000C_5h','0.01','802'],['GC_1000C_5h','1','703'],['GC_1000C_5h','10','468']];key=prose('Glycogen',80,['sample','current_A_g','capacitance_F_g'],vals)
  for i,row in enumerate(vals,1):cap('Glycogen',row[0],key,i,2,row[2],'2E_symmetric_solid_DES','SSE_ethaline',None,float(row[1]),extra=dict(capacitance_basis='device_total_two_electrode_active_mass',electrolyte_state='cellulose_acrylamide_SSE_DES',protocol_locator='SIphysicalp5-6EqS6'))
  cycle('Glycogen','GC_1000C_5h','GCprototype',dict(system='2E_symmetric_solid_DES',electrolyte='SSE_ethaline',concentration_mol_L=None,reported_current_A_g=1,cycle_count=1000,retention_pct=75,retention_relation='eq',locator='p80,p82;SIphysicalp5-6',unresolved=['SolidDES separatepurpose; cyclevoltage directbinding notcompleted']))
  # Wood apple: separate CVgravimetric/volumetric, GCD, energy/power and EIS response columns.
  key,rows=units[('WoodApple','tbl1')]
  for i in range(3,14):
   for col in range(1,7):cap('WoodApple','WAS',key,i,col,rows[i][col],'3E','KOH',[2,4,6][(col-1)%3],None,'CV','F/g' if col<=3 else 'F/cm3',float(rows[i][0]),extra=dict(capacitance_basis='single_working_electrode_mass' if col<=3 else 'author_electrode_volume',voltage_lower_V=-1,voltage_upper_V=.1,reference_electrode='Ag/AgCl',protocol_locator='WoodAppleSIphysicalp3-4'))
  key,rows=units[('WoodApple','tbl2')]
  for i in range(3,12):
   for col in range(1,4):cap('WoodApple','WAS',key,i,col,rows[i][col],'3E','KOH',[2,4,6][col-1],float(rows[i][0]),eligible=True,extra=dict(voltage_lower_V=-1,voltage_upper_V=.1,reference_electrode='Ag/AgCl',protocol_locator='SIphysicalp3;bodyp33',EDX_trace_Ca_phase_unknown=True))
   for col in range(4,10):outcome('WoodApple','WAS',key,i,col,'energy_density_Wh_kg' if col<=6 else 'power_density_W_kg',rows[i][col],'Wh/kg' if col<=6 else 'W/kg',dict(system='3E',concentration_mol_L=[2,4,6][(col-1)%3],current_A_g=float(rows[i][0])))
  key,rows=units[('WoodApple','tbl3')]
  for i,col,molar,method,current,scan in [(11,3,2,'CV',None,5),(12,2,4,'CV',None,5),(13,2,6,'CV',None,5),(14,2,2,'GCD',2,None),(15,2,4,'GCD',2,None)]:cap('WoodApple','WAS',key,i,col,rows[i][col],'3E','KOH',molar,current,method,scan=scan,status='repeat_own_report_comparison_not_additional_label',extra={'duplicate_of_ownTables1or2':True})
  key,rows=units[('WoodApple','tbl4')]
  metrics=[('series_resistance_ohm','ohm'),('charge_transfer_resistance_ohm','ohm'),('Warburg_impedance_reported_ohm','ohm'),('time_constant_reported_ms','ms'),('double_layer_capacitance_microF','microF'),('relaxation_time_s','s')]
  for i in range(1,4):
   for col,(metric,un) in enumerate(metrics,1):outcome('WoodApple','WAS',key,i,col,metric,rows[i][col],un,dict(system='3E',electrolyte='KOH',concentration_mol_L=[2,4,6][i-1]))
  for index,rowspec in [(24,[['WAS','BET_surface_area_m2_g','590','m2/g'],['WAS','total_pore_volume_cm3_g','0.623','cm3/g']]),(8,[['WAS','reported_product_yield_pct','58.33','% of dryrawprecursor']]),(11,[['WAS','XRD_d002_A','3.498','angstrom']]),(19,[['WAS','TEM_interlayer_spacing_nm','0.3512','nm']])]:
   key=prose('WoodApple',index,['sample','field','value','unit'],rowspec)
   for i,row in enumerate(rowspec,1):assert row[2] in txt(pp['WoodApple'][index]);fact('WoodApple',row[0],key,i,2,row[1],row[2],row[3],'Own BET/pore/yield/XRD/TEM methods remain distinct')
  for molar,ret in [(2,96.07),(4,96.8),(6,95.16)]:cycle('WoodApple','WAS','WAS'+str(molar),dict(system='3E',electrolyte='KOH',concentration_mol_L=molar,reference_electrode='Ag/AgCl',reported_current_A_g=None,cycle_count=10000,retention_pct=ret,retention_relation='eq',baseline_reference='authorinitial;exactindexunknown',locator='p48;SIphysicalp3-4',unresolved=['Cyclingcurrentnotreported;rate-testcurrentnottransferred','Cyclingvoltagebindingneedsowncycleevidence']))
  # Stage extraction never swaps KOH dose, carbonization, hydrothermal treatment or electrode drying.
  for sample in ['NWJPC-'+str(i) for i in range(5)]+['WJHC-'+str(t) for t in [140,160,180,200,220]]:
   control=sample=='NWJPC-0' or sample.startswith('WJHC');temp=int(sample.split('-')[1]) if sample.startswith('WJHC') else None
   stages=[dict(stage='hydrothermal_carbonization',temperature_C=temp,duration_h=4,selected180C_candidate_not_directly_bound_to_NWJPC=not sample.startswith('WJHC')),dict(stage='chemical_activation',temperature_C=800,duration_h=2,heating_rate_C_min=5,atmosphere='N2',agent='KOH',carbon_to_activator_mass_ratio=[1,3 if control else 1],melamine_to_hydrochar_mass_ratio=0 if control else int(sample[-1]),postwash='1MHClthenDIwaterneutral',final_drying_temperature_C=80,final_drying_duration_h=24)]
   c.execute('insert into synthesis_stages_v3 values(?,?,?,?)',(material('Weigela',sample),'Weigela','XML body//p89-90',json.dumps(stages,ensure_ascii=False)))
  for i,(temp,hours) in gbind.items():
   stages=[dict(stage='carbonization',temperature_C=temp,duration_h=hours,heating_rate_C_min=None,atmosphere='N2',gas_flow_L_h=.3,activating_agent=None)]
   c.execute('insert into synthesis_stages_v3 values(?,?,?,?)',(material('Glycogen',gname(i)),'Glycogen','OwnTable1/3conditions;bodyp11N2flow',json.dumps(stages,ensure_ascii=False)))
  stages=[dict(stage='chemical_activation',temperature_C=None,duration_h=48,temperature_raw='roomtemperature',agent='concentratedH2SO4',precursor_mass_g=48,agent_mass_g=46,postwash='notreported;notinvented'),dict(stage='carbonization',temperature_C=400,duration_h=2,heating_rate_C_min=None,atmosphere=None)]
  c.execute('insert into synthesis_stages_v3 values(?,?,?,?)',(material('WoodApple','WAS'),'WoodApple','XML body//p7-8',json.dumps(stages,ensure_ascii=False)))
  issues=[('WJ_voltage',J,'NWJPC-2',dict(kind='cycling_SI_signed_voltage_vs_actual_own_cycle_insets',main_window=[0,1],SI_window=[-1,0],actual_first_last_cycle_insets=[0,1],action='OwnFigure7G actually showsfirst/lastcycling0..1V, corroboratingp51. Selectthatactualcyclewindow withexplicitdecision; retain SI-1..0. Formalappendstillpending.')),
   ('WJ_cap',J,'NWJPC-1',dict(kind='own_body_table_capacitance_competition',body=133,table=133.7,current_A_g=1,action='Do not silentlyround133.7to133; onlythiscurrent frozen; other fourboundtablecurrents retained.')),
   ('WJ_scope',J,'all',dict(kind='synthesis_control_and_alias_not_assumed',control_KOH_to_hydrochar=3,doped_KOH_to_hydrochar=1,action='KOHdosecontrol3,doped1 preserved. NWJPC0notmergedwithWJHC180;146vs129capacitanceandsamplebindingretained. NWJPChydrothermalTnotexplicitlybound,180Cnotfilled. SImethodsmentionsMorus alba despiteWeigela main;rawtextretained.')),
   ('WJ_XPS',J,'NWJPC-0 / NWJPC-2 / NWJPC-4',dict(kind='XPS_envelope_dash_malformed_and_sum',NWJPC0_total_N_at_pct=.9,NWJPC0_N_species_raw='dash',NWJPC2_C1s_last_raw='12.6.',NWJPC4_element_sum=99.64,action='N1s/C1s/O1senvelopepercent notglobalatomic%;dashandmalformed12.6.keptnull,nosilentrepairorrenormalization. N0.9doesnotmakedash0.')),
   ('G_pore',G,'GC_1000C_5h',dict(kind='abstract_pore_volume_scope_not_assumed_total',abstract_volume_cm3_g=.38,table_microvolume=.377,table_totalvolume=.897,action='UseexplicitTable1micro/meso/totalchannels,retainabstractunspecifiedvolume,notreplaceTabletotalwith.38. Angstromdiameterretained,notnm.')),
   ('G_targets',G,'all',dict(kind='DES_and_mean_uncertainty_separate_purpose',action='12Table3ownretentionsandfirstcyclecapskeptwithauthor±values;DES30C/silverpseudo-reference separatefromordinaryaqueous;prototypeSSEseparatefromliquidDES. RamanLaderivedfromID/IGnotindependentmeasurement.')),
   ('A_cycle',A,'WAS',dict(kind='cycling_current_not_bound_from_rate_test',retentions_pct=[96.07,96.8,95.16],concentrations_M=[2,4,6],cycling_current_A_g=None,action='Threeowncyclinglabelsretained;constcurrentwithoutnumberstillnull,not2A/gfromGCDtable. Conclusionover96.8acrossallconflictswithown95.16/96.07,donotreplacethem.')),
   ('A_EIS',A,'WAS',dict(kind='EIS_report_and_summary_competition',table_2M_Rct=42.96,body_2M_Rct=42,table_4M_Rct=58.06,action='KeepTableandbodyvalues;proseclaims4MlowresistancedespitehighestTableRct,nottrainingfeature. TraceCaEDSdoesnotidentifymineralphaseorzero;noinventedphase.'))]
  for ident,d,s,issue in issues:c.execute('insert into scientific_issues values(?,?,?,?)',('LP5_'+ident,d,s,json.dumps(issue,ensure_ascii=False)))
  for d,scope,reason in [(J,'biomass_carbon_3e_with_separate_symmetric_and_Zn_hybrid','WJHCandNWJPCcarbon;Znfoilonlyhybriddevice,notin3Ecarbon. SSCactualcycleinsetsresolvesignedwindowwithSIretained.'),(G,'biomass_glycogen_DES_and_SSE_separate_purposes','Musselwastewaterglycogencarbon;ethaline30Candsolidprototype,notsameordinaryaqueouspurpose;2023cohortretained.'),(A,'biomass_carbon_multi_concentration_3e','WASacidcarbon,AgAgCl3E;traceCaEDSpreservedwithoutphaseguess;cyclingcurrentunknown.')]:c.execute('insert into source_scope_decisions values(?,?,?,?,0)',(d,scope,reason,json.dumps({'full_paper_all_curves_complete':False},ensure_ascii=False)))
  for doc,inds in [('Weigela',[5,24,34,35,42,51,74,89,90]),('Glycogen',[8,10,11,13,55,68,70,80,82]),('WoodApple',[7,8,11,19,24,26,33,35,48,52])]:
   for i in inds:c.execute('insert into evidence_spans_v4 values(?,?,?)',(doc,'XML body//p zero-based index'+str(i),txt(pp[doc][i])))
  c.commit()
 write(OUT/'source_protection.json',dict(documents=docs,parent=dict(path=PARENT.relative_to(ROOT).as_posix(),sha256=PARENT_SHA),corpus=dict(path=CORPUS.relative_to(ROOT).as_posix(),sha256=sha(CORPUS)),cycling_pointer=json.loads((ROOT/'data/current_database.json').read_text('utf8')),evidence_archives=[dict(path=(OUT/'evidence/Weigela_supplementary_package.zip').relative_to(ROOT).as_posix(),sha256=acquisition['sha256']),dict(path=was_receipt['source_zip'],sha256=was_receipt['source_zip_sha256'])]))
 write(OUT/'table_review_receipt.json',receipt)
 write(OUT/'source_review_notes.json',dict(scope='Selected own numeric tables/prose, namedSIpagesandWeigelaFigure7;notfullpapercompletion',remaining={J:['SI ownTableS1NWJPC2.5andothercurves','formalcyclingappendandindependentpurposeadmission','othercharacterizationandZncapacityratecurve'],G:['SIremainingXPS/XRDandmethod-qualifiedfittingtables','actualGCDcyclewindow','DESpurposematrixandcyclingadmissionnotordinaryaqueous'],A:['RemainingFTIR/XPSandowncyclefigure','cyclenumericcurrentnotfoundinmainorSI','otherenergyresponseformulaqualityandcurvedigitization']},scientific_goal_complete=False))
 print('Built v5, not sealed.')

def verify():
 checks=[]
 def check(name,ok):
  if not ok:raise AssertionError(name)
  checks.append(name)
 proof=json.loads((OUT/'source_protection.json').read_text('utf8'))
 for key,d in proof['documents'].items():check('original_'+key,sha(ROOT/d['path'])==d['sha256'])
 for key in ['parent','corpus']:check('protected_'+key,sha(ROOT/proof[key]['path'])==proof[key]['sha256'])
 for archive in proof.get('evidence_archives',[]):check('archive_'+archive['path'],sha(ROOT/archive['path'])==archive['sha256'])
 check('cycling_pointer',json.loads((ROOT/'data/current_database.json').read_text('utf8'))==proof['cycling_pointer'])
 with closing(ro(DB)) as c,closing(ro(PARENT)) as old:
  c.row_factory=sqlite3.Row;check('integrity',c.execute('pragma integrity_check').fetchone()[0]=='ok');check('foreign_keys',not c.execute('pragma foreign_key_check').fetchall())
  for (name,) in old.execute("select name from sqlite_master where type='table' and name not like 'sqlite_%'"):
   if name=='raw_table_queue':continue
   current={tuple(r) for r in c.execute('select * from '+name)};check('all_parent_rows_'+name,all(tuple(r) in current for r in old.execute('select * from '+name)))
  oldq={r[0]:tuple(r) for r in old.execute('select * from raw_table_queue')};now=[tuple(r) for r in c.execute('select * from raw_table_queue')];check('queue_rawfields',set(oldq)=={r[0] for r in now} and all(r[:6]==oldq[r[0]][:6] and r[7:]==oldq[r[0]][7:] for r in now))
  for rec in json.loads((OUT/'table_review_receipt.json').read_text('utf8')):
   if not rec['locator'].startswith('XML table-wrap '):continue
   t=E.parse(ROOT/proof['documents'][rec['document']]['path']).getroot().find(".//table-wrap[@id='"+rec['locator'].split()[-1]+"']")
   for i,row in enumerate(t.findall('.//tr')):check('xml_'+rec['table_key']+str(i),[txt(x) for x in row if x.tag in ['td','th']]==json.loads(c.execute('select cells_json from transcribed_rows where table_key=? and row_ordinal=?',(rec['table_key'],i)).fetchone()[0]))
  for r in c.execute("select f.*,v.component from material_facts f join value_components_v3 v using(fact_id) where v.component like 'v5_%'"):
   cells=json.loads(c.execute('select cells_json from transcribed_rows where table_key=? and row_ordinal=?',(r['table_key'],r['row_ordinal'])).fetchone()[0]);check('fact_raw_'+str(r['fact_id']),cells[r['column_ordinal']]==r['raw_value']);check('fact_value_'+str(r['fact_id']),number(r['raw_value'],r['component'][3:])==r['value'])
  for r in c.execute('select x.*,m.doi from capacitance_observations x join materials m using(material_key)'):
   if r['doi'] not in [J,G,A]:continue
   cells=json.loads(c.execute('select cells_json from transcribed_rows where table_key=? and row_ordinal=?',(r['table_key'],r['row_ordinal'])).fetchone()[0]);check('cap_raw_'+r['observation_id'],cells[r['column_ordinal']]==r['raw_value']);check('cap_value_'+r['observation_id'],number(r['raw_value'],'mean' if '±' in r['raw_value'] else 'whole')==r['value'])
  for table in ['raw_table_queue','material_facts','capacitance_observations','test_candidates','outcome_observations_v3']:check('raw_qualification_'+table,c.execute('select count(*) from '+table+' where training_eligible!=0 or training_eligible is null').fetchone()[0]==0)
  import pypdfium2 as pdf
  with pdf.PdfDocument(str(ROOT/proof['documents']['Weigela_SI']['path'])) as d:
   for ident,page,header,rows in SI_TABLES:
    p=d[page-1];tp=p.get_textpage();text=tp.get_text_range();tp.close();p.close()
    for row in rows:
     for token in row[1:]:
      if token!='-':check('SI_token_'+ident+row[0]+token,token in text)
  count=lambda t:c.execute('select count(*) from '+t).fetchone()[0]
  untouched=c.execute("select count(*) from raw_table_queue where review_state='automatic_candidate_unreviewed'").fetchone()[0]
  parts=dict(c.execute('select purpose,count(*) from auxiliary_reported_GCD_v3 group by purpose'));summary=dict(identity_catalogue_entries=480,raw_table_candidates=959,raw_table_rows=6121,cumulative_reviewed_source_publications=count('reviewed_sources'),cumulative_materials=count('materials'),cumulative_selected_material_cells=count('material_facts'),cumulative_numeric_material_facts=c.execute('select count(*) from material_facts where value is not null').fetchone()[0],new_materials=count('materials')-61,new_numeric_material_facts=c.execute('select count(*) from material_facts where value is not null').fetchone()[0]-603,reviewed_table_units=c.execute("select count(*) from reviewed_tables t left join extraction_units_v3 u using(table_key) where u.kind is null or u.kind in ('own_xml_table','own_SI_table','own_and_comparison_pdf_table','mixed_comparison_table')").fetchone()[0],reviewed_evidence_units=count('reviewed_tables'),raw_candidates_touched=959-untouched,raw_candidates_untouched=untouched,capacitance_records=count('capacitance_observations'),numeric_capacitance_values=c.execute('select count(*) from capacitance_observations where value is not null').fetchone()[0],unreported_capacitance_cells=2,cycling_candidates=count('test_candidates'),scientific_issues=count('scientific_issues'),historical_selected_fact_references=725,historical_fact_references_with_same_source_table_candidates=171,synthesis_materials=count('synthesis_stages_v3'),coulombic_efficiency_outcomes=8,CO2_adsorption_outcomes=24,response_outcomes=count('outcome_observations_v3'),auxiliary_aqueous_3e_GCD_rows=parts['reported_aqueous_3e_GCD_capacitance'],auxiliary_aqueous_2e_GCD_rows=parts['reported_aqueous_2e_GCD_device_capacitance'],auxiliary_native_mineral_3e_GCD_rows=parts['reported_native_mineral_3e_GCD_capacitance'],auxiliary_author_factor2_2e_GCD_rows=parts['reported_2e_author_factor2_GCD_capacitance'],auxiliary_independent_DOI_groups=c.execute('select count(distinct source_group) from auxiliary_reported_GCD_v3').fetchone()[0],auxiliary_purpose_reviewed_input_rows=sum(parts.values()),new_training_admissions=0,formal_cycling_admissions=0,model_fits=0,all_literature_fully_utilized=False,scope_note='Material registrations and numeric reports are not independent experiments. Four auxiliary targets separate; DES andCVlabels remain otherpurpose. All sameDOIlabels heldtogether; no fit or performance claim.')
 from data.literature_v4 import open_literature_database,PROFILES
 from data.cycling_db import open_database
 digest=sha(DB);exports={};profiles={}
 with open_literature_database(DB,digest) as db,open_database() as cy:
  main=cy.fetch('reported_3e').rows;check('formal_cycling_unchanged',len(main)==43 and len({r['source_group'] for r in main})==31)
  for profile in PROFILES:
   rows=db.auxiliary_feature_rows(profile);profiles[profile]=rows;weights=Counter(r['source_group'] for r in rows)
   for r in rows:
    r['source_balanced_weight']=1/weights[r['source_group']]
    check('target_'+r['observation_id'],math.isfinite(r['capacitance_F_g']) and r['capacitance_F_g']>0 and r['current_A_g'] is not None and r['concentration_mol_L'] is not None)
    for k,v in r.items():
     if k.endswith('_is_missing'):check('mask_'+r['observation_id']+k,v==(r[k.removesuffix('_is_missing')] is None))
   for source in weights:check('sourceweight_'+profile+source,abs(sum(r['source_balanced_weight'] for r in rows if r['source_group']==source)-1)<1e-12)
   buf=io.StringIO(newline='');w=csv.DictWriter(buf,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows);exports['auxiliary_'+profile+'.csv']=buf.getvalue()
  check('profile_counts',{k:len(v) for k,v in profiles.items()}==dict(zip(PROFILES,[103,5,5,6])))
  check('WJ1_conflict_not_chosen',not any(r['sample_name']=='NWJPC-1' and r['current_A_g']==1 for r in profiles['3e']))
  check('WAS27_not_CV66',sum(r['doi']==A for r in profiles['3e'])==27 and sum(r['method']=='CV' for r in db.capacitances(doi=A))==69)
  check('DES_not_aqueous',not any(r['doi']==G for r in profiles['3e']))
  wj0=next(r for r in profiles['3e'] if r['sample_name']=='NWJPC-0');check('N_species_dash_not_Nzero',wj0['XPS_N_at_pct']==.9 and db.facts(doi=J,sample='NWJPC-0',field='XPS_N1s_pyridinic_envelope_pct')[0]['value'] is None)
  controls=next(r for r in profiles['3e'] if r['sample_name']=='NWJPC-2');check('control_dopant_KOH_doses',wj0['activator_to_carbon_mass_ratio']==3 and controls['activator_to_carbon_mass_ratio']==1)
  check('combined_not_meso',all(r['mesopore_volume_cm3_g'] is None for r in profiles['3e'] if r['doi']==J))
  sources=sorted({r['source_group'] for rows in profiles.values() for r in rows});folds=[]
  for source in sources:
   hold=[r for rows in profiles.values() for r in rows if r['source_group']==source];train=[r for rows in profiles.values() for r in rows if r['source_group']!=source]
   check('group_isolation_'+source,not {r['source_group'] for r in train}&{r['source_group'] for r in hold})
   folds.append(dict(heldout_source=source,validation_rows=len(hold),all_same_source_capacitance_labels_quarantined=sum(r['source_group']==source for r in db.capacitances()),cycling_candidates_quarantined=sum(r['record']['source_group']==source for r in db.tests()),other_same_source_response_labels_must_also_be_quarantined=True,actual_model_fit=False))
  input_report=dict(status='passed',rows={k:len(v) for k,v in profiles.items()},DOI_groups={k:len({r['source_group'] for r in v}) for k,v in profiles.items()},folds=folds,missingness={k:{f:sum(r[f] is None for r in v) for f in v[0] if any(r[f] is None for r in v)} for k,v in profiles.items()},model_fits=0,scientific_goal_complete=False)
 check('readonly_api',sha(DB)==digest);report=dict(status='passed',checks=len(checks),check_names=checks,model_fits=0,scientific_goal_complete=False)
 sealed=(OUT/'merge_manifest.json').exists()
 for name,value in [('summary.json',summary),('verification.json',report),('auxiliary_input_preflight.json',input_report)]:
  if sealed:assert json.loads((OUT/name).read_text('utf8'))==value,'sealedreport_'+name
  else:write(OUT/name,value)
 # These conditional file checks deliberately do not mutate the fixed science-check report.
 for name,value in exports.items():
  if sealed:
   with (OUT/name).open('r',encoding='utf8',newline='') as f:assert f.read()==value,'sealedCSV_'+name
  else:
   with (OUT/name).open('w',encoding='utf8',newline='') as f:f.write(value)
 if sealed:
  for item in json.loads((OUT/'merge_manifest.json').read_text('utf8'))['outputs']:assert sha(ROOT/item['path'])==item['sha256'],item['path']
 print(json.dumps(dict(status='passed',checks=report['checks'],summary=summary),ensure_ascii=False))

def seal():
 if (OUT/'merge_manifest.json').exists():raise FileExistsError('Never reseal.')
 assert (OUT/'README.md').exists();verify()
 files=sorted([p for p in OUT.rglob('*') if p.is_file()]+[Path(__file__).resolve()])
 write(OUT/'merge_manifest.json',dict(kind='literature_evidence_pool_v5',parent_sha256=PARENT_SHA,api_module='data.literature_v4',formal_cycling_admissions=0,model_fits=0,outputs=[dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p),bytes=p.stat().st_size) for p in files]))
 write(ROOT/'data/current_literature.json',dict(version='literature_pool_v5',directory=OUT.relative_to(ROOT).as_posix(),database_file=DB.name,sha256=sha(DB),api_module='data.literature_v4',scope='Selected carbonization series, multi-electrolyte and method-qualified evidence; four auxiliary tasks separate; not newcyclingmembership.'))
if __name__=='__main__':
 if len(sys.argv)!=2 or sys.argv[1] not in ['build','verify','seal']:raise SystemExit('build(oneuse),verify(readonlyafterseal),seal(oneuse)')
 globals()[sys.argv[1]]()
