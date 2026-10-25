"""One-use append of a source-qualified symmetric cycling endpoint; no model fitting."""
from pathlib import Path
from contextlib import closing
import collections,csv,hashlib,importlib.util,io,json,math,sqlite3,sys,xml.etree.ElementTree as E
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
OUT=ROOT/'循环稳定性数据库_v0.20_新增来源准入_20261025';DB=OUT/'cycling_v0_20.sqlite'
PARENT=ROOT/'循环稳定性数据库_v0.19_摘要与制备漏项补正_20261025'
LIT=ROOT/'文献全量利用复核_20261025/批次05_碳化系列与多电解液'
KEY='v20:WJ2026_NWJPC2_SSC_C10000';DOI='10.1016/j.isci.2026.117248';MKEY='v20m:WJ2026_NWJPC2'
APPROVED=['reported_2e','reported_2e_residue','reported_2e_approx']
PARENT_SHA='3c50428341089dd6f51dd540c7fa37c019b9ff7f28084babd61675809adbdf8c'
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def ro(p):return sqlite3.connect(Path(p).resolve().as_uri()+'?mode=ro',uri=True)
def txt(e):return ' '.join(''.join(e.itertext()).split()) if e is not None else ''
def load_api(folder,name):
 if name not in sys.modules:
  spec=importlib.util.spec_from_file_location(name,folder/'ml_data.py');m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m)
 return sys.modules[name]
def norm(s):return str(s).strip().lower().removeprefix('doi:').removeprefix('https://doi.org/')

def build():
 if DB.exists() or (OUT/'merge_manifest.json').exists():raise FileExistsError('Never overwrite a release or draft database.')
 assert sha(PARENT/'cycling_v0_19.sqlite')==PARENT_SHA
 parent_api=load_api(PARENT,'_v019_newsource_build_parent')
 with parent_api.Database() as old:
  previous=old.fetch('all_review').rows
  assert len(previous)==277
  assert not any(norm(r['source_group'])==DOI or 'NWJPC' in (r.get('sample_name') or '') for r in previous)
 candidate=json.loads((LIT/'ready_cycling_candidates_v5.json').read_text('utf8'))[0]
 assert candidate['candidate_id']=='LP5_SSC' and candidate['retention_pct']==99.8
 docs={d['document']:d for d in candidate['evidence']}
 for d in docs.values():assert sha(ROOT/d['path'])==d['sha256']
 root=E.parse(ROOT/docs['Weigela']['path']).getroot();paras=root.findall('.//body//p');title=txt(root.find('.//article-title'))
 assert DOI in [txt(a).lower() for a in root.findall('.//article-id') if a.get('pub-id-type')=='doi']
 assert {int(a.text) for a in root.findall('.//article-meta/pub-date/year')}=={2026}
 assert '99.8%' in txt(paras[51]) and '10,000' in txt(paras[51]) and '5 A' in txt(paras[51])
 import pypdfium2 as pdf
 with pdf.PdfDocument(str(ROOT/docs['Weigela_SI']['path'])) as d:
  p=d[2];tp=p.get_textpage();methods=tp.get_text_range();tp.close();p.close()
 assert '6 M KOH' in methods and 'Hg/HgO' in methods and '10,000' in methods
 # Scientific decision uses the actual first/last cycling insets in originalFig7G, not diagnosticCV.
 decision=dict(issue='SI signed window versus actual own cycling plot',selected_window_V=[0,1],preserved_SI_window_V=[-1,0],evidence=['Main body p51 explicitly0–1V and ownSSC sample.','Original Figure7G first/last actualcyclinginsets show0–1V, at5A/g per caption/body.','SIphysicalp3 writesSSC−1–0V; retained as dissent, not overwritten.'],basis='Specific actual cycling evidence corroborated by own main text; not latest-write selection, CV substitution or author erratum.',residual_caveats=['Author reporting quality includes a contradictorySI signedwindow.','Exact normalization cycle index and cycling-current mass denominator unspecified; retained under established reportpurpose.','SI material-characterization paragraph saysMorus alba; mainarticle/ownNWJPCsamplelabels and DOI retained, source text not repaired.'],resolved_for_reported_protocol=True,not_author_erratum=True)
 from data.literature_v4 import open_literature_database
 lp=json.loads((ROOT/'data/current_literature.json').read_text('utf8'));assert lp['version']=='literature_pool_v5'
 litpath=ROOT/lp['directory']/lp['database_file']
 with open_literature_database(litpath,lp['sha256']) as lit:
  facts=lit.facts(doi=DOI,sample='NWJPC-2');stages=lit.synthesis(doi=DOI,sample='NWJPC-2')[0]['stages']
 mapping={'BET_m2_g':'BET_surface_area_m2_g','total_pore_volume_cm3_g':'total_pore_volume_cm3_g','micropore_volume_cm3_g':'micropore_volume_cm3_g','micropore_surface_area_m2_g':'micropore_surface_area_m2_g','average_pore_diameter_nm':'BJH_average_pore_diameter_nm','Raman_ID_IG':'Raman_ID_IG','XPS_N_reported_pct':'XPS_N_at_pct','XPS_O_reported_pct':'XPS_O_at_pct','C_at_pct':'XPS_C_at_pct','meso_plus_macro_volume_cm3_g_v20':'meso_plus_macro_volume_cm3_g'}
 properties={};evidence=[]
 def ev(field,value,doc,locator,excerpt,selected=1,note=''):
  item=dict(evidence_id='v20ev:'+str(len(evidence)+1).zfill(3),endpoint_id=KEY,field_name=field,value_json=json.dumps(value,ensure_ascii=False),document_key=doc,locator=locator,excerpt=excerpt,selected=selected,decision_note=note)
  evidence.append(item);return item
 for field,original in mapping.items():
  selected=[f for f in facts if f['field_name']==original];assert len(selected)==1 and selected[0]['value'] is not None
  f=selected[0];doc='Weigela_SI' if f['document_role']=='SI' else 'Weigela'
  proof=ev(field,f['value'],doc,f['locator'],f['raw_value'],note=f['method'])
  properties[field]=dict(value=f['value'],unit=f['unit'],method=f['method'],evidence=[proof])
 assert properties['BET_m2_g']['value']==2916 and properties['total_pore_volume_cm3_g']['value']==2.06
 activation=next(s for s in stages if s['stage']=='chemical_activation')
 process={'activation_temperature_C':activation['temperature_C'],'activation_duration_h':activation['duration_h'],'heating_rate_C_min':activation['heating_rate_C_min'],'activation_KOH_to_hydrochar_mass_ratio_v20':activation['carbon_to_activator_mass_ratio'][1]/activation['carbon_to_activator_mass_ratio'][0],'activation_melamine_to_hydrochar_mass_ratio_v20':activation['melamine_to_hydrochar_mass_ratio'],'hydrothermal_duration_h':4}
 for field,value in dict(process,XPS_percentage_basis='atomic_explicit').items():
  doc='Weigela_SI' if field=='XPS_percentage_basis' else 'Weigela';loc='PDF physicalp8TableS2;mainp35' if field=='XPS_percentage_basis' else 'XML body//p89-90'
  proof=ev(field,value,doc,loc,txt(paras[35]) if field=='XPS_percentage_basis' else txt(paras[89])+' '+txt(paras[90]))
  properties[field]=dict(value=value,unit='categorical' if isinstance(value,str) else 'stage-qualified reported',method='XPS explicit at%' if field=='XPS_percentage_basis' else 'Synthesis stages; no hydrothermal temperature or active electrode mass inferred.',evidence=[proof])
 contract=json.loads((PARENT/'data_contract.json').read_text('utf8'));contract.update(schema='cycling_reported_source_append_v20',version='0.20',database_file=DB.name,parent_database_sha256=PARENT_SHA,parent_directory=PARENT.name,preparation_only=True,research_training_authorized=False,all_records_admitted=False,model_fits=0,storage_layout='Normalized new source/material/test/endpoint/evidence delta plus immutable v0.19 API; no parent rows cloned or overwritten.',expansion_rule='One newly reviewed symmetric source appended to all_review and explicit2E nested profiles only; source weights rebuilt per profile, all old scientific rows unchanged.')
 for f in ['meso_plus_macro_volume_cm3_g_v20','activation_KOH_to_hydrochar_mass_ratio_v20','activation_melamine_to_hydrochar_mass_ratio_v20']:
  if f not in contract['extra_material_feature_whitelist']:contract['extra_material_feature_whitelist'].append(f)
 contract['field_semantics_v20']=dict(meso_plus_macro_volume_cm3_g_v20='Author combined BJH meso+macro volume, not canonical mesopore volume.',hydrothermal_temperature_C='Unknown NWJPC series temperature remains null; optimization candidate180C not assigned.',active_mass_mg_v14='SI about2mg refers to prepared electrode sheet; active carbon mass not inferred.',current_mass_basis='AuthorA/g remains permitted under reportpurpose; no formula-based denominator inference.')
 row={f:None for f in contract['extra_material_feature_whitelist']}
 row.update({f:p['value'] for f,p in properties.items()})
 row.update(endpoint_id=KEY,identity_key='doi:'+DOI,source_group=DOI,source_year=2026,year_basis='Own XML front:epub2026-08-19;collection2026-09-18',doi=DOI,title=title,sample_name='NWJPC-2',material_id='v20_material:WJ2026_NWJPC2',material_key_v11=MKEY,material_key_v20=MKEY,literature_material_key='literature:'+hashlib.sha256((DOI+'\0NWJPC-2').encode()).hexdigest()[:24],test_id='v20_test:WJ2026_NWJPC2_SSC',curve_group='doi:'+DOI+'#Figure7G',system='2E_symmetric',method='GCD',metric_kind='capacitance_retention',cycle_count=10000,retention_pct=99.8,retention_relation='eq',reported_current_A_g=5,canonical_current_A_g=None,current_mass_basis=None,concentration_mol_L=6,electrolyte='KOH',cycle_voltage_lower_V=0,cycle_voltage_upper_V=1,reference_electrode=None,baseline_reference='author_initial_specific_capacitance',baseline_cycle=None,temperature_C=None,value_kind='reported',eligible=1,admission_status='approved_for_reported_protocol',workflow_status='approved_v20_reported_2e',source_weight=1,admission_profiles_v20=APPROVED,literature_candidate_id='LP5_SSC',scope_flags=json.dumps(dict(material_scope='biomass_derived_pororous_carbon',nitrogen_modifier='melamine',symmetric_carbon_electrodes=True,zinc_foil_only_in_separate_ZIHC_not_this_test=True,cycle_voltage_dissent_retained=True),ensure_ascii=False),preconditioning_protocol_v20=dict(cycles=5,current_A_g=.5,followed_by_cycles=10000,followed_by_current_A_g=5),baseline_reference_note_v20='Exact normalization index unknown; conditioning protocol does not establish the reference cycle.',material_key_compatibility_note_v20='material_key_v11 is the existing API field name; valuev20m is newly registered here, not a historicalv11 material.')
 for field in list(properties)+['cycle_count','retention_pct','retention_relation','reported_current_A_g','concentration_mol_L','electrolyte','cycle_voltage_lower_V','cycle_voltage_upper_V','baseline_reference','system','method','source_year']:
  row[field+'_status']='v020_selected_source_review'
 row['current_mass_basis_status']='unknown_not_required_for_reported_current_purpose';row['canonical_current_A_g_status']='not_admitted_to_unified_physical_current';row['baseline_cycle_status']='not_reported_not_assumed_cycle1'
 for field,value in [('cycle_count',10000),('retention_pct',99.8),('reported_current_A_g',5),('baseline_reference',row['baseline_reference']),('system','2E_symmetric')]:ev(field,value,'Weigela','XML body//p51',txt(paras[51]))
 for field,value in [('electrolyte','KOH'),('concentration_mol_L',6),('method','GCD')]:ev(field,value,'Weigela_SI','PDF physicalp3MethodsS2',methods)
 for field,value,dissent in [('cycle_voltage_lower_V',0,-1),('cycle_voltage_upper_V',1,0)]:
  ev(field,value,'Weigela_Fig7','OriginalFigure7G:first/lastactualcyclinginsets','Both actual cycling insetpotential axes0–1V; greenleftaxis isretention, orange rightaxisCE is separate.',note='Actual own cycle evidence corroborates mainp51; '+decision['basis'])
  ev(field,dissent,'Weigela_SI','PDF physicalp3MethodsS2',methods,0,'Preserved contradictorySI signed endpoint; not selected for this actual cycle decision.')
 review=dict(endpoint_id=KEY,disposition='approved_reported_2e_new_source',open_issues=[],approved_profiles=APPROVED,reason='Own symmetricGCD retention and required report-purpose inputs bound; actual cycle inset resolves sharedSI window dissent.',resolution=decision,caveats=decision['residual_caveats'],historical_candidate_path=(LIT/'ready_cycling_candidates_v5.json').relative_to(ROOT).as_posix(),no_human_review_claimed=True,model_fits=0)
 with closing(sqlite3.connect(DB)) as c:
  c.execute('pragma foreign_keys=on');c.executescript('''
  create table sources_v20(source_id text primary key,doi text unique not null,source_group text unique not null,year integer,title text);
  create table source_documents_v20(document_key text primary key,source_id text references sources_v20,path text,sha256 text,role text);
  create table materials_v20(material_key text primary key,source_id text references sources_v20,sample_name text,stage text,unique(source_id,sample_name));
  create table tests_v20(test_id text primary key,material_key text references materials_v20,system text,method text,curve_group text);
  create table endpoints_v20(endpoint_id text primary key,test_id text references tests_v20,cycle_count integer,retention_pct real,retention_relation text,row_json text);
  create table reviews_v20(endpoint_id text primary key references endpoints_v20,review_json text);
  create table profile_membership_v20(endpoint_id text references endpoints_v20,profile text,eligible integer check(eligible=1),primary key(endpoint_id,profile));
  create table evidence_v20(evidence_id text primary key,endpoint_id text references endpoints_v20,field_name text,value_json text,document_key text references source_documents_v20,locator text,excerpt text,selected integer check(selected in(0,1)),decision_note text);
  create table material_fields_v20(material_key text references materials_v20,field_name text,value_json text,status text,unit text,evidence_json text,metadata_json text,primary key(material_key,field_name));
  create table field_changes_v20(change_id integer primary key,endpoint_id text references endpoints_v20,field_name text,operation text,before_json text,after_json text,reason text,evidence_json text);
  create table literature_links_v20(candidate_id text primary key,endpoint_id text references endpoints_v20,literature_database_sha256 text,status text);
  create view training_rows_v20 as select e.endpoint_id,e.cycle_count,e.retention_pct,t.system,t.method,s.doi,s.source_group,m.sample_name from endpoints_v20 e join tests_v20 t using(test_id) join materials_v20 m using(material_key) join sources_v20 s using(source_id);
  ''')
  c.execute('insert into sources_v20 values(?,?,?,?,?)',('doi:'+DOI,DOI,DOI,2026,title))
  for key,d in docs.items():c.execute('insert into source_documents_v20 values(?,?,?,?,?)',(key,'doi:'+DOI,d['path'],d['sha256'],d['role']))
  c.execute('insert into materials_v20 values(?,?,?,?)',(MKEY,'doi:'+DOI,'NWJPC-2','before_cycling'))
  c.execute('insert into tests_v20 values(?,?,?,?,?)',(row['test_id'],MKEY,row['system'],row['method'],row['curve_group']))
  c.execute('insert into endpoints_v20 values(?,?,?,?,?,?)',(KEY,row['test_id'],10000,99.8,'eq',json.dumps(row,ensure_ascii=False)))
  c.execute('insert into reviews_v20 values(?,?)',(KEY,json.dumps(review,ensure_ascii=False)))
  c.executemany('insert into profile_membership_v20 values(?,?,1)',[(KEY,p) for p in APPROVED])
  c.executemany('insert into evidence_v20 values(:evidence_id,:endpoint_id,:field_name,:value_json,:document_key,:locator,:excerpt,:selected,:decision_note)',evidence)
  for field,p in properties.items():c.execute('insert into material_fields_v20 values(?,?,?,?,?,?,?)',(MKEY,field,json.dumps(p['value']), 'selected_agent_source_review',p['unit'],json.dumps(p['evidence'],ensure_ascii=False),json.dumps(dict(method=p['method'],stage='before_cycling'),ensure_ascii=False)))
  for field in ['cycle_count','retention_pct','reported_current_A_g','electrolyte','concentration_mol_L','cycle_voltage_lower_V','cycle_voltage_upper_V','baseline_reference','system','method']+list(properties):
   c.execute('insert into field_changes_v20(endpoint_id,field_name,operation,before_json,after_json,reason,evidence_json) values(?,?,?,?,?,?,?)',(KEY,field,'insert_new_endpoint_field','null',json.dumps(row[field]),'New record absent from immutable parent; no original value overwritten.',json.dumps([e for e in evidence if e['field_name']==field],ensure_ascii=False)))
  c.execute('insert into literature_links_v20 values(?,?,?,?)',('LP5_SSC',KEY,lp['sha256'],'admitted_reported_2e_v020'))
  c.commit()
 write(OUT/'data_contract.json',contract);write(OUT/'voltage_decision.json',decision);write(OUT/'admission_review.json',review)
 protected=[PARENT/'cycling_v0_19.sqlite',PARENT/'ml_data.py',PARENT/'data_contract.json',LIT/lp['database_file'],LIT/'merge_manifest.json',LIT/'ready_cycling_candidates_v5.json',ROOT/'全库复检与特征补提取_20261021/full_corpus_search_native.sqlite']+[ROOT/d['path'] for d in docs.values()]
 write(OUT/'protected_inputs.json',[dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p)) for p in protected])
 print('Built v0.20 new-source delta; not yet promoted.')

def verify():
 checks=[]
 def check(name,condition):
  if not condition:raise AssertionError(name)
  checks.append(name)
 for p in json.loads((OUT/'protected_inputs.json').read_text('utf8')):check('protected_'+p['path'],sha(ROOT/p['path'])==p['sha256'])
 # The literature release is immutable; its old verifier assumes the old global cycling pointer.
 # Verify its sealed payloads directly rather than changing that historical verifier/report.
 for p in json.loads((LIT/'merge_manifest.json').read_text('utf8'))['outputs']:check('literature_sealed_'+p['path'],sha(ROOT/p['path'])==p['sha256'])
 with closing(ro(DB)) as c:
  check('sqlite_integrity',c.execute('pragma integrity_check').fetchone()[0]=='ok');check('foreign_keys',not c.execute('pragma foreign_key_check').fetchall())
  check('one_new_endpoint',c.execute('select count(*) from endpoints_v20').fetchone()[0]==1)
  check('three_2e_memberships',c.execute('select count(*) from profile_membership_v20').fetchone()[0]==3)
  check('raw_SI_dissent_retained',c.execute('select count(*) from evidence_v20 where selected=0').fetchone()[0]==2)
  check('no_overwrite_history',c.execute("select count(*) from field_changes_v20 where before_json!='null' or operation!='insert_new_endpoint_field'").fetchone()[0]==0)
 api=load_api(OUT,'_v020_release_verify');parent_api=load_api(PARENT,'_v019_release_verify_parent')
 lp=json.loads((ROOT/'data/current_literature.json').read_text('utf8'));from data.literature_v4 import open_literature_database,PROFILES
 exports={}
 with api.Database(DB) as new,parent_api.Database() as old,open_literature_database() as lit:
  oldall={r['endpoint_id']:r for r in old.fetch('all_review').rows};newall={r['endpoint_id']:r for r in new.fetch('all_review').rows}
  check('append_exactly_one',set(newall)-set(oldall)=={KEY} and len(newall)==278)
  for key,row in oldall.items():
   check('old_row_'+key,newall[key]==row)
   check('old_holds_'+key,new.holds(key)==old.holds(key))
  check('old_change_chain',new.field_changes(include_history=True)[:len(old.field_changes(include_history=True))]==old.field_changes(include_history=True))
  check('old_material_fields',new.material_properties()[:len(old.material_properties())]==old.material_properties())
  check('fixed38_unmodified',new.reviewed_pending_batch()==old.reviewed_pending_batch() and len(new.reviewed_pending_batch())==38)
  cohort_counts={};coverage={}
  for profile in new.contract['profiles']:
   before=old.fetch(profile);after=new.fetch(profile);ids={r['endpoint_id'] for r in after.rows}
   expected={r['endpoint_id'] for r in before.rows}|({KEY} if profile in APPROVED else set())
   check('membership_'+profile,ids==expected)
   matrix=after.feature_matrix();cohort_counts[profile]=dict(rows=len(after.rows),sources=len(set(matrix['groups'])))
   check('matrix_rows_'+profile,len(matrix['X'])==len(matrix['y'])==len(after.rows) and not matrix['training_authorized'])
   for source in set(matrix['groups']):check('weights_'+profile+source,abs(sum(w for g,w in zip(matrix['groups'],matrix['sample_weight']) if g==source)-1)<1e-12)
   for fold in after.source_folds(len(set(matrix['groups']))):check('fold_'+profile+str(fold['test'][0]),not {matrix['groups'][i] for i in fold['train']}&{matrix['groups'][i] for i in fold['test']})
   material=new.method_specific_material_matrix(profile)
   check('no_imputation_'+profile,not material['imputed'] and material['estimators_fitted']==0 and all(mask==(value is None) for row,flags in zip(material['X'],material['missing_mask']) for value,mask in zip(row,flags)))
   coverage[profile]=dict(non_null=sum(v is not None for r in material['X'] for v in r),cells=sum(len(r) for r in material['X']),feature_names=material['feature_names'])
   if profile in APPROVED:
    fields=list(dict.fromkeys(['endpoint_id','source_group','sample_name','source_year']+after.features+['retention_pct','retention_relation','baseline_reference','current_mass_basis','canonical_current_A_g','source_weight']))
    buf=io.StringIO(newline='');writer=csv.DictWriter(buf,fieldnames=fields);writer.writeheader()
    # Audit identifiers are columns for provenance, never implicit model predictors.
    writer.writerows([{k:r.get(k) for k in fields} for r in after.rows])
    exports[profile+'.csv']=buf.getvalue()
  row=new.by_endpoint(KEY);check('same_by_endpoint',row==newall[KEY])
  check('source_identity_new_to_parent',DOI not in {norm(r['source_group']) for r in oldall.values()})
  check('core_values',[(row[k]) for k in ['cycle_count','reported_current_A_g','electrolyte','concentration_mol_L','cycle_voltage_lower_V','cycle_voltage_upper_V','BET_m2_g','retention_pct']]==[10000,5,'KOH',6,0,1,2916,99.8])
  check('unknowns_remain_null',all(row.get(k) is None for k in ['canonical_current_A_g','current_mass_basis','baseline_cycle','hydrothermal_temperature_C','active_mass_mg_v14','mass_loading_mg_cm2','mesopore_volume_cm3_g']))
  check('no_3e_or_strict_approval',not any(c['status']=='approved_for_reported_protocol' for p in ['reported_3e','strict_2e'] for c in new.admission_checks(KEY,p)))
  check('2e_approval',all(c['status']=='approved_for_reported_protocol' for p in APPROVED for c in new.admission_checks(KEY,p)))
  check('resolved_caveat_not_suppressed',not new.holds(KEY)['open_issues'] and bool(new.holds(KEY)['caveats']) and new.holds(KEY)['resolution']['preserved_SI_window_V']==[-1,0])
  check('all_core_evidence',all(new.evidence(KEY,f) for f in new.contract['profiles']['reported_2e']['features']+['retention_pct','system','method']))
  check('XPS_method_projection',row['XPS_N_reported_pct']==14.83 and row['XPS_O_reported_pct']==8.12 and row['XPS_percentage_basis']=='atomic_explicit')
  check('combined_volume_not_meso',row['meso_plus_macro_volume_cm3_g_v20']==1.48 and row['mesopore_volume_cm3_g'] is None)
  check('own_process_doses',row['activation_temperature_C']==800 and row['activation_duration_h']==2 and row['activation_KOH_to_hydrochar_mass_ratio_v20']==1 and row['activation_melamine_to_hydrochar_mass_ratio_v20']==2)
  check('new_alias',any(a['endpoint_id']==KEY and a['doi']==DOI for a in new.source_aliases()))
  check('linked_candidate',new.literature_links()[0]['candidate_id']=='LP5_SSC')
  check('source_search',any(r.get('endpoint_id')==KEY for r in new.search_native('99.8',doi=DOI)))
  check('year_exclusion',KEY not in {r['endpoint_id'] for r in new.fetch('reported_2e',year_max=2025).rows})
  check('year_inclusion',KEY in {r['endpoint_id'] for r in new.fetch('reported_2e',year_min=2026).rows})
  # A cycling holdout quarantines that DOI across every other task, even previously prepared auxiliary data.
  auxiliary=[r for p in PROFILES for r in lit.auxiliary_feature_rows(p)];allcaps=lit.capacitances();cycles=lit.tests()
  excluded_aux=[r for r in auxiliary if norm(r['source_group'])==DOI];train_aux=[r for r in auxiliary if norm(r['source_group'])!=DOI]
  check('29_same_source_aux_quarantined',len(excluded_aux)==29 and len(train_aux)==90 and not {norm(r['source_group']) for r in train_aux}&{DOI})
  check('119_aux_original_rows_retained',len(auxiliary)==119)
  check('33_raw_cap_reports_quarantined',sum(norm(r['source_group'])==DOI for r in allcaps)==33)
  check('2_cycle_candidates_quarantined',sum(norm(r['record']['source_group'])==DOI for r in cycles)==2)
  check('new_only_group_weight',row['source_weight']==1)
  check('parent3E_material_matrix_unchanged',new.method_specific_material_matrix('reported_3e')==old.method_specific_material_matrix('reported_3e'))
  projected=new.method_specific_material_matrix('reported_2e');idx=projected['endpoint_ids'].index(KEY)
  for field,value in [('XPS_N_atomic_pct_v15',14.83),('XPS_O_atomic_pct_v15',8.12),('XPS_N_weight_pct_v15',None),('XPS_O_weight_pct_v15',None)]:check('explicit_XPS_channel_'+field,projected['X'][idx][projected['feature_names'].index(field)]==value)
  check('connections_readonly',new.delta_v20.execute('pragma query_only').fetchone()[0]==1)
  for field,bad in [('reported_current_A_g',None),('retention_pct',float('nan')),('system','3E')]:
   sample=dict(row);sample[field]=bad
   try:api.Dataset('reported_2e',[sample],new.contract['profiles']['reported_2e']['features']).feature_matrix()
   except api.DataNotReady:rejected=True
   else:rejected=False
   check('invalid_row_rejected_'+field,rejected)
  hypothetical=dict(row,retention_pct=105)
  check('retention_is_not_probability_no_upper_clip',api.Dataset('reported_2e',[hypothetical],new.contract['profiles']['reported_2e']['features']).feature_matrix()['y']==[105])
  preflight=dict(model_fits=0,new_endpoint_id=KEY,holdout_source=DOI,auxiliary_all_rows=len(auxiliary),quarantined_auxiliary_rows=len(excluded_aux),remaining_auxiliary_training_rows=len(train_aux),quarantined_raw_capacitance_reports=33,quarantined_cycle_candidates=2,rule='Exclude every label and learned preprocessing contribution from this DOI across auxiliary andcycling tasks. Raw facts and historical candidates are preserved; candidate-to-formal link is not a second experiment.',profiles=cohort_counts,material_matrix_coverage=coverage,performance_improvement_proven=False)
  summary=dict(version='0.20',observations=278,source_groups=len({r['source_group'] for r in newall.values()}),material_keys=len({r['material_key_v11'] for r in newall.values()}),new_endpoints=1,new_source_groups=1,new_admission_purpose='reported aqueous2E symmetricGCD only',profiles=cohort_counts,original_fixed_records=39,original_resolved=1,original_pending=38,newly_linked_literature_candidate='LP5_SSC',material_fields_added=len(new.material_properties())-len(old.material_properties()),formal_main_3e_rows=43,formal_main_3e_sources=31,model_fits=0,full_literature_goal_complete=False)
 sealed=(OUT/'merge_manifest.json').exists();report=dict(status='passed',checks=len(checks),check_names=checks,model_fits=0,scientific_goal_complete=False)
 for name,value in [('summary.json',summary),('verification.json',report),('model_input_preflight.json',preflight)]:
  if sealed:assert json.loads((OUT/name).read_text('utf8'))==value,'sealed_report_'+name
  else:write(OUT/name,value)
 for name,value in exports.items():
  if sealed:
   with (OUT/name).open('r',encoding='utf8',newline='') as f:assert f.read()==value,'sealedCSV_'+name
  else:
   with (OUT/name).open('w',encoding='utf8',newline='') as f:f.write(value)
 if sealed:
  for p in json.loads((OUT/'merge_manifest.json').read_text('utf8'))['outputs']:assert sha(ROOT/p['path'])==p['sha256'],p['path']
 print(json.dumps(dict(status='passed',checks=report['checks'],summary=summary),ensure_ascii=False))

def seal():
 if (OUT/'merge_manifest.json').exists():raise FileExistsError('Do not reseal.')
 assert (OUT/'README.md').exists();verify()
 files=sorted([p for p in OUT.rglob('*') if p.is_file()]+[Path(__file__).resolve()])
 write(OUT/'merge_manifest.json',dict(version='v0.20',parent_database_sha256=PARENT_SHA,new_endpoints=1,model_fits=0,outputs=[dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p),bytes=p.stat().st_size) for p in files]))
 write(ROOT/'data/current_database.json',dict(version_directory=OUT.name,database_file=DB.name,sha256=sha(DB),parent_database_file=(PARENT/'cycling_v0_19.sqlite').relative_to(ROOT).as_posix(),default_profile='reported_3e',stage='source_qualified_new_2e_endpoint',ready_for_training_inputs=True,research_training_authorized=False,all_records_admitted=False))
if __name__=='__main__':
 if len(sys.argv)!=2 or sys.argv[1] not in ['build','verify','seal']:raise SystemExit('build(one-use),verify(read-only afterseal),seal(one-use)')
 globals()[sys.argv[1]]()
