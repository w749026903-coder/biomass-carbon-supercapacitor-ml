"""Versioned reported-protocol cohorts with own-source review; never fits a model."""
from pathlib import Path
import collections,hashlib,json,sqlite3
R=Path(__file__).resolve().parents[1];O=R/'循环稳定性数据库_v0.6_报告工况训练就绪_20261018';P=R/'循环稳定性数据库_v0.5_逐条准入审查_20261018'
def enc(x):return json.dumps(x,ensure_ascii=False)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
 c=sqlite3.connect(O/'cycling_v0_6.sqlite');c.row_factory=sqlite3.Row;c.execute('pragma foreign_keys=ON')
 if c.execute("select count(*) from extraction_run where key='v06_reported_profiles_built'").fetchone()[0]:raise RuntimeError('Already built; sealed versions are immutable')
 c.executescript('''
 CREATE TABLE reported_record_reviews_v06(endpoint_id TEXT PRIMARY KEY REFERENCES model_endpoints,decision TEXT NOT NULL,system TEXT,reason TEXT NOT NULL,review_json TEXT NOT NULL);
 CREATE TABLE reported_profile_admissions_v06(profile TEXT,endpoint_id TEXT REFERENCES model_endpoints,status TEXT NOT NULL,reason TEXT NOT NULL,evidence_json TEXT NOT NULL,PRIMARY KEY(profile,endpoint_id));
 CREATE TABLE reported_training_rows_v06(profile TEXT,endpoint_id TEXT REFERENCES model_endpoints,identity_key TEXT REFERENCES literature_registry,source_group TEXT,row_json TEXT NOT NULL,PRIMARY KEY(profile,endpoint_id));
 CREATE INDEX idx_reported_rows_profile_group ON reported_training_rows_v06(profile,source_group);
 CREATE TABLE reported_route_policy_v06(key TEXT PRIMARY KEY,value_json TEXT NOT NULL);
 CREATE TABLE reported_issue_dispositions_v06(endpoint_id TEXT REFERENCES model_endpoints,issue_id INTEGER,profile TEXT,disposition TEXT,reason TEXT,PRIMARY KEY(endpoint_id,issue_id,profile));
 CREATE TABLE source_visual_reviews_v06(path TEXT PRIMARY KEY,sha256 TEXT NOT NULL,scope TEXT NOT NULL,judgment TEXT NOT NULL);
 ''')
 core=['cycle_count','reported_current_A_g','electrolyte','concentration_mol_L','cycle_voltage_lower_V','cycle_voltage_upper_V','BET_m2_g'];core3=core+['reference_electrode']
 def ep(alias,namespace='TE'):return c.execute('select endpoint_id from endpoint_aliases where namespace=? and alias=?',(namespace,alias)).fetchone()[0]
 def select(e,field,val,sids,reason,unit=None):
  ss=[c.execute('select * from source_segments where segment_id=?',(sid,)).fetchone() for sid in sids];s=ss[0];identity=c.execute('select identity_key from model_endpoints where endpoint_id=?',(e,)).fetchone()[0]
  assert all(c.execute('select 1 from paper_documents where identity_key=? and source_id=?',(identity,t['source_id'])).fetchone() for t in ss)
  old=c.execute('select observation_id from field_selection where endpoint_id=? and field_name=?',(e,field)).fetchone()
  oid=c.execute('insert into field_observations(endpoint_id,field_name,value_json,unit,status,source_id,segment_id,locator,evidence_excerpt,provenance_json) values (?,?,?,?,?,?,?,?,?,?)',(e,field,enc(val),unit,'v06_own_source_reported_protocol_review',s['source_id'],s['segment_id'],s['locator'],s['text'],enc({'reason':reason,'supporting_segments':sids}))).lastrowid
  c.execute('insert or replace into field_selection values (?,?,?)',(e,field,oid));c.execute('insert into field_selection_history(endpoint_id,field_name,old_observation_id,new_observation_id,reason) values (?,?,?,?,?)',(e,field,old[0] if old else None,oid,reason))
 reviews=[]
 def review(alias,window,sids,basis,scope,fig=None,namespace='TE',extra=None,cycle=None,caveats=None):
  e=ep(alias,namespace);x=dict(c.execute('select * from model_feature_rows where endpoint_id=?',(e,)).fetchone());data={'alias':alias,'namespace':namespace,'endpoint_id':e,'identity_key':x['identity_key'],'system':x['system'],'window':window,'segments':sids,'window_evidence_kind':basis,'scope_review':scope,'source_group_review':'Own paper and sample/protocol evidence checked; no additional reuse link identified in this bounded review. Existing unified_source_groups and known historical reuse relationships retained. This is not proof of statistical independence.','figure':fig,'caveats':caveats or []}
  for f,v in [('cycle_voltage_lower_V',window[0]),('cycle_voltage_upper_V',window[1])]:select(e,f,v,sids,'Own cycling waveform or same explicitly defined GCD programme within this sample/configuration; no transfer from another device.', 'V')
  baseline={'reference':'author_initial_or_plotted_start_normalized_to_100pct','cycle_index':cycle,'basis':'Actual cycling graph/prose and original retention label; no invented conditioning/first-cycle number.','source_segments':sids,'figure':fig}
  select(e,'baseline_reference',baseline,sids,'Reported-protocol baseline: author initial/plotted reference is valid metadata; exact conditioning index stays unknown unless explicitly shown.')
  if cycle is not None:select(e,'baseline_cycle',cycle,sids,'Actual cycle labels in first/last GCD inset explicitly identify Cycle1.')
  for f,v,unit,fsids in extra or []:select(e,f,v,fsids,'Own sample-specific table/passage; value not borrowed from another material or configuration.',unit)
  c.execute('insert into reported_record_reviews_v06 values (?,?,?,?,?)',(e,'approved_for_reported_protocol',x['system'],'Own target, sample, reported current, electrolyte, BET, cycle protocol and baseline reviewed for the declared empirical use; physical mass basis remains metadata.',enc(data)));reviews.append(data)
 # Actual 3E cycling tests. Windows are sourced and their applicability is explicit.
 review('TE007',[-1,0],[3868,3896,3847],'all_three_electrode_tests_unless_otherwise_stated','Green algae carbon; self-N/KOH activation, no designed redox composite.','同体系文献补充_第二批_20261017/定向扩搜40至60篇_20261017/sources/OA001/figures/molecules-31-02329-g004.jpg')
 review('TE020',[-.1,.6],[4669,4688,4647],'explicit_long_cycle_paragraph','Anacardium nut-skin directly pyrolyzed carbon; own3E not HER identity.','同体系文献补充_第二批_20261017/定向扩搜40至60篇_20261017/sources/OA059/figures/nanomaterials-13-01654-g007.jpg',caveats=['SIcontainsHERwording; complete electrochemical methods and own cycling paragraph explicitly establish3Ecapacitor test. Fig7bduplicatesbeforelegend; no before/after inference made from that legend.'])
 for a in ['TE021','TE022','TE023','TE024']:
  review(a,[-1,0],[5801,5810,5811,5797],'same_reported_three_electrode_GCD_programme','Orange peel B/N/P doped carbon/control;3Ecapacitor is distinct from symmetric device and sodium battery.','循环稳定性数据库_v0.6_报告工况训练就绪_20261018/evidence_images/U002_p16.png',cycle=1 if a=='TE021' else None,caveats=['Cycle1/lastGCDinsetdirectlyshownforOPBNP; other3samples use own shared3EGCDmethod and named cycle comparison, not device window.'] if a!='TE021' else [])
 review('TE025',[-1,0],[5955,5950],'actual_first_and_2000th_cycle_GCD_inset','Soybean-straw activated carbon, no designed oxide/polymer electrode.','循环稳定性数据库_v0.6_报告工况训练就绪_20261018/evidence_images/U013_p8.png',cycle=1)
 for a,w in [('TE029',[-.2,1]),('TE030',[-.9,.9])]:
  review(a,w,[6143,6136,6134],'same_sample_electrolyte_and_three_electrode_GCD_programme','Agarwood-leaf carbon, ORR uses a differentreference; SCusesAg/AgCl. Separate acid andneutral3Econditions, same sourcegroup.','循环稳定性数据库_v0.6_报告工况训练就绪_20261018/evidence_images/U024_p9.png',caveats=['Own3EGCDbounds are stated per electrolyte; the long cycle panel does not restate the voltage. Stored as same-protocol evidence, not an independently labelled cycle waveform.'])
 review('TE031',[-1,0],[2567,2576,2553,2554],'actual_after_20000_cycle_GCD_inset','Cotton-pulp board carbon with inherent processing-derived heteroatoms; no intentional metal oxide or conductive polymer phase.','三电极端点扩充_20261018/new_sources/PMC12794195/assets/d5ra08165c-f4.jpg',caveats=['Cottonpulpindustrialprocessingcontainsheteroatomreagents; retain provenance, not claim untreated natural cotton.'])
 for a in ['TE033','TE034']:
  review(a,[-1,0],[6197,6161],'actual_cycle1_and_cycle5000_GCD_inset','Pine-wood carbon withZnCl2activation andacidwashing; optional printed pore unit remains masked.','三电极端点扩充_20261018/new_sources/PMC10056672/assets/micromachines-14-00572-g008.jpg',cycle=1,caveats=['Printedtotalporevolumem3/gisnotcorrectedto cm3/g; excluded from optionalpore input, doesnot invalidate independently supportedBET/core.'])
 # Configuration-specific disambiguation:3E101.35;2E102. Preserveold102observation.
 select(ep('TE035'),'retention_pct',101.35,[6241,6242],'Correct prior configuration mismatch: Fig7a and its explicit3Eparagraph giveCA-AA101.35%;102%isFig7b2E. Do not choose by performance.', '%')
 review('TE035',[0,.8],[6219,6241,6242],'explicit_three_electrode_GCD_method_and_configured_cycle_panel','Cellulose carbon aerogel withaceticacidantisolvent;3Elabel101.35identifiedseparatelyfrom2E102.','三电极端点扩充_20261018/new_sources/PMC10759806/assets/d3ra07014j-f7.jpg',caveats=['Genericconclusion/table102%belongsdevicecontext; original102keptinfield_observations.3Ecyclehasown1A/g despite routineGCDmethods5–10A/g.'])
 review('TE003',[-1,0],[176,180,175],'sole_three_electrode_GCD_programme_stated_in_methods','Reed-extraction-residue KOH activated carbon C/600C. Own98.1abstract/figure and >98body are compatible.','循环稳定性数据库_v0.6_报告工况训练就绪_20261018/evidence_images/B_R078_p6.png')
 # Extra2Ecohorts: retain the parent8 and add only separately reviewed records.
 review('V05_019',[0,.9],[5589,5566,5595],'explicit_cycling_paragraph','Cucumber-peel carbon ACP800; two identical electrodes explicitly stated; commonmethod0–1Vnot substituted for explicit0–.9cycling.',namespace='V05',caveats=['CapacitanceformulaIunitinconsistency retainedasphysicalnormalizationcaveat; authorreported1A/gand100%are not recalculated.'])
 review('V05_015',[0,1],[5981,5988,5989],'own_device_GCD_programme_and_cycle_figure','Peanut-shellPPC-500-1-1h; matched electrodes less0.1mgdifference,6MKOH. Own BET1184.88.','循环稳定性数据库_v0.6_报告工况训练就绪_20261018/evidence_images/PPC_p12.png',namespace='V05',extra=[('BET_m2_g',1184.88,'m2/g',[5984,5989]),('total_pore_volume_cm3_g',.67,'cm3/g',[5984])])
 review('V05_014',[0,1],[5007,5025,5027],'same_reported_symmetric_device_GCD_programme','Green-pea-peel NSGP co-doped carbon; samegraphite-disc area andreported1mg/cm2commoncoating give nominal matched symmetricpair. Measuredpairmassdifference not reported.','同体系文献补充_第二批_20261017/定向扩搜40至60篇_20261017/sources/OA011/figures/d5ra01262g-f8.jpg',namespace='V05',extra=[('BET_m2_g',1691,'m2/g',[5016])],caveats=['Massbalanceisnominalsamegeometry/loadingjustification, not measuredperfectequality. Fig8cratelegendNS-APSBcopyerrornotused; owncyclingpanel8fisNSGP.'])
 # Make a well-identified record more complete without granting admission.
 e=ep('V05_016','V05');select(e,'BET_m2_g',640,[5964,5965],'Own HPC-P8 table; not the precursor or another pyrolysis temperature.','m2/g')
 for f,v in [('cycle_voltage_lower_V',0),('cycle_voltage_upper_V',2)]:select(e,f,v,[5974,5975],'Own first/last5000cycleGCDinset explicitly0–2V.','V')
 c.execute('insert into reported_record_reviews_v06 values (?,?,?,?,?)',(e,'pending','2E_symmetric','HPC-P8label,640BETandcyclewindowlocated; matched/justifiedequalactivepairmassesnotexplicitlycleared.',enc({'segments':[5962,5964,5974],'remaining':['electrode_pair_active_mass_balance']})))
 # Separate true window inconsistency from the resolved mass-policy question.
 e=ep('TE011');c.execute('insert into reported_record_reviews_v06 values (?,?,?,?,?)',(e,'pending','3E','Own99.96labelverified,butactualGCDinsetvoltageaxisappearsdifferentfromCV-1to0V; donotfillfromCV.',enc({'segments':[4284,4302],'figure':'同体系文献补充_第二批_20261017/定向扩搜40至60篇_20261017/sources/OA044/figures/polymers-15-04478-g007.jpg','remaining':['cycling_window_inset_vs_characterization_check']})))
 # Newcache, sameimmutablehistory. Canonicalv05gates are retained as historical
 # snapshots and are not silently reinterpreted as reported-protocol admissions.
 c.execute('delete from model_feature_cache');c.execute('insert into model_feature_cache select * from model_feature_rows')
 for k,v in [('selection_history_max_id',c.execute('select max(selection_id) from field_selection_history').fetchone()[0]),('selected_fields',c.execute('select count(*) from field_selection').fetchone()[0])]:c.execute('update feature_cache_meta set value=? where key=?',(str(v),k))
 def identity_for_paper(pid):return c.execute("select identity_key from literature_aliases where batch='archived_126' and local_id=?",(pid,)).fetchone()[0]
 def store(profile,row,evidence,reason):
  eid=row['endpoint_id'];identity=row['identity_key'];gid=c.execute('select group_id from unified_source_groups where identity_key=?',(identity,)).fetchone()[0];row['source_group']=gid;row['profile']=profile;row['admission_status']='approved_for_reported_protocol';row['eligible']=1;row['current_input_semantics']='author_reported_protocol_descriptor';row['training_authorized']=False
  row['current_denominator_status']=row.get('current_denominator_status') or 'not_uniquely_defined';row['physical_current_harmonized']=False
  c.execute('insert into reported_profile_admissions_v06 values (?,?,?,?,?)',(profile,eid,'approved_for_reported_protocol',reason,enc(evidence)))
  c.execute('insert into reported_training_rows_v06 values (?,?,?,?,?)',(profile,eid,identity,gid,enc(row)))
 inherited={'literature_core7_exact':'reported_2e','literature_residue_sensitivity':'reported_2e_residue','literature_approx_sensitivity':'reported_2e_approx'}
 for old,new in inherited.items():
  for r in c.execute('select r.*,p.year as source_year from training_rows_r4 r join papers p using(paper_id) where r.profile=?',(old,)).fetchall():
   row=dict(r);identity=identity_for_paper(row['paper_id']);row.update({'endpoint_id':'legacy:'+row['record_id'],'identity_key':identity,'concentration_mol_L':row['concentration_value'],'cycle_voltage_lower_V':row['voltage_lower_V'],'cycle_voltage_upper_V':row['voltage_upper_V'],'reference_electrode':None,'upstream_profile':old,'data_origin':'r4_effective_reported_protocol_rows'})
   assert row['concentration_unit'] in ('M','mol/L'),row['concentration_unit']
   store(new,row,{'table':'training_rows_r4','profile':old,'record_id':row['record_id'],'source':'Fourthround scientific reviews retained unchanged.'},'Restore the previously approved empirical use; do not reinterpret unknown current mass as a new failure.')
 for d in reviews:
  row=dict(c.execute('select * from model_feature_cache where endpoint_id=?',(d['endpoint_id'],)).fetchone());assert row['retention_relation']=='eq' and row['retention_pct'] is not None
  required=core3 if row['system']=='3E' else core
  assert all(row[f] is not None for f in required),(d['alias'],[(f,row[f]) for f in required])
  profiles=['reported_3e'] if row['system']=='3E' else ['reported_2e','reported_2e_residue','reported_2e_approx']
  for profile in profiles:
   store(profile,dict(row),d,'Primary sample/protocol/label and bounded source-group review completed for the reported-current empirical use. Currentmassunknownretained; no physical conversion.')
   # Optionalfield issues stay recorded with scope; do not blanket-clear oldfreezes.
   for issue in c.execute('select i.* from extraction_issues i left join extraction_issue_resolutions z using(issue_id) where i.endpoint_id=? and z.issue_id is null',(row['endpoint_id'],)).fetchall():
    optional=issue['field_name'] in ('total_pore_volume_cm3_g','raw_total_pore_volume_m3_g')
    c.execute('insert into reported_issue_dispositions_v06 values (?,?,?,?,?)',(row['endpoint_id'],issue['issue_id'],profile,'optional_field_masked_not_core_blocker' if optional else 'addressed_by_current_record_review','Originalissuepreserved; currentreportuseevidenceinreported_record_reviews_v06. Optionalporesremainmasked.' if optional else 'Current source review provides the actual protocol and baseline, without clearing unknown physical mass basis.'))
 # Everyrowreceivesan explicit reported-use disposition; no mass-only blanketfailure.
 approved={r[0] for r in c.execute('select distinct endpoint_id from reported_training_rows_v06')}
 for row in c.execute('select * from model_feature_cache').fetchall():
  profile='reported_3e' if row['system']=='3E' else 'reported_2e' if row['system']=='2E_symmetric' else 'reported_outside_main'
  if c.execute('select 1 from reported_profile_admissions_v06 where profile=? and endpoint_id=?',(profile,row['endpoint_id'])).fetchone():continue
  hard=[];missing=[]
  if row['system'] not in ('3E','2E_symmetric'):hard.append('system_outside_separate_main_profiles')
  if row['method']!='GCD':hard.append('GCD_method_not_confirmed_or_different')
  if row['source_year'] is not None and not 2023<=row['source_year']<=2026:hard.append('outside_declared_publication_years')
  if row['cycle_count'] is not None and row['cycle_count']<1000:hard.append('fewer_than1000cycles')
  if row['retention_relation']!='eq' or any(v in str(row['value_kind']).lower() for v in ['loss','derived','approx','qualitative']):hard.append('not_exact_reported_main_label')
  fields=core3 if row['system']=='3E' else core
  missing=[f for f in fields+['retention_pct','source_year'] if row[f] is None]
  state='excluded_from_main' if hard else 'pending_primary_review'
  if row['endpoint_id'] in approved:reason='Profile-specific effective review differs from the legacy broad projection; use approved row snapshot, not the stale legacy values.'
  else:reason='Record has actual non-mass scope/label/missingness or unresolved source-review work.'
  c.execute('insert into reported_profile_admissions_v06 values (?,?,?,?,?)',(profile,row['endpoint_id'],state,reason,enc({'failed_conditions':hard,'missing_fields':missing,'mass_denominator_unknown_alone_is_not_failure':True,'baseline_cycle_index_unknown_alone_is_not_failure':True})))
 for d in reviews:
  if d['figure']:
   p=R/d['figure'];c.execute('insert or ignore into source_visual_reviews_v06 values (?,?,?,?)',(p.relative_to(R).as_posix(),sha(p),'Own cycling/configuration/baseline visual review',d['window_evidence_kind']))
 for path in ['同体系文献补充_第二批_20261017/定向扩搜40至60篇_20261017/sources/OA044/figures/polymers-15-04478-g007.jpg']:
  c.execute('insert or ignore into source_visual_reviews_v06 values (?,?,?,?)',(path,sha(R/path),'Unresolved cycling inset axis','Do not fill cyclewindow from CV.'))
 policies={'default_profile':'reported_3e','current_semantics':'author_reported_protocol_descriptor','current_mass_unknown_policy':'metadata_only_for_reported_use; not a standalone exclusion','baseline_policy':'author initial/plotted reference allowed; exact cycle index remains unknown when unreported','strict_current_views':'unchanged separate canonical use; not the reported-use count','training_authorized':False,'core_features_2e':core,'core_features_3e':core3,'historical_admission_checks':'v05canonical snapshot retained verbatim; not current reported-profile gates'}
 for k,v in policies.items():c.execute('insert into reported_route_policy_v06 values (?,?)',(k,enc(v)))
 c.execute('insert into extraction_run values (?,?)',('v06_reported_profiles_built',enc({'parent_sha256':sha(P/'cycling_v0_5.sqlite'),'new_record_reviews':len(reviews),'research_training_performed':False})));c.commit()
 contract={'schema':'reported-retention-training-input-v1','database_file':'cycling_v0_6.sqlite','parent_database_sha256':sha(P/'cycling_v0_5.sqlite'),'target':'capacitance_retention_pct_at_requested_cycle_count_and_reported_protocol','default_profile':'reported_3e','research_training_authorized':False,'current_semantics':'author_reported_protocol_descriptor','core_features':core3,'canonical_core_features':['cycle_count','canonical_current_A_g','electrolyte','concentration_mol_L','cycle_voltage_lower_V','cycle_voltage_upper_V','BET_m2_g'],'profiles':{'reported_3e':{'features':core3,'system':'3E','relations':['eq']},'reported_2e':{'features':core,'system':'2E_symmetric','relations':['eq']},'reported_2e_residue':{'features':core,'system':'2E_symmetric','relations':['eq']},'reported_2e_approx':{'features':core,'system':'2E_symmetric','relations':['eq','approx']}},'optional_features':['total_pore_volume_cm3_g'],'forbidden_predictors':['endpoint_id','identity_key','source_group','material_id','test_id','sample_name','retention_pct','post_cycle_EIS','post_cycle_XPS','final_capacitance'],'review_only_profiles':['review_3e','review_3e_all','all_review','proposal_2e'],'physical_current_warning':'No unknown denominator was imputed/converted. Main features are literature descriptors; do not claim calibrated equal physical stress.','3E_reference_policy':'Reference identity is a required categorical descriptor; raw reported potentials are not silently converted.','window_evidence_policy':'Own actual waveforms or an explicitly reviewed applicable GCD programme in same sample/configuration/electrolyte; evidence kind and caveats saved per record.','baseline_policy':policies['baseline_policy'],'split_policy':'Unified paper/reuse groups stay together; leave-one-source-out; equal total source weight; no preprocessing before group split.'}
 (O/'data_contract.json').write_text(json.dumps(contract,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');(O/'逐记录报告工况复核.json').write_text(json.dumps(reviews,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(enc({'profiles':list(map(tuple,c.execute('select profile,count(*) from reported_training_rows_v06 group by profile'))),'new_primary_reviews':len(reviews),'unharmonized_currents_retained':True}));c.close()
if __name__=='__main__':main()
