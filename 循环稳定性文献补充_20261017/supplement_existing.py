"""Apply reviewed evidence to a NEW 81-row candidate snapshot, preserving originals."""
import copy, hashlib, json, pathlib
ROOT=pathlib.Path(__file__).resolve().parent
BASE=ROOT.parent
src=BASE/'循环稳定性可行性_20261017/循环稳定性逐记录候选.json'
original=json.loads(src.read_text(encoding='utf-8-sig'));rows=copy.deepcopy(original);changes=[]
def add(r,field,value,source,note=''):
 old=copy.deepcopy(r.get(field))
 if old==value:return
 r[field]=value
 r.setdefault('input_provenance',{})[field]=source
 r.setdefault('field_status',{})[field]='recorded_in_followup_with_evidence'
 changes.append(dict(record_id=r['record_id'],paper_id=r['paper_id'],field=field,old=old,new=value,evidence=source,note=note))
for r in rows:
 ident=r['paper_id']
 if ident=='R012':
  for k,v in [('BET_m2_g',1840.51),('total_pore_volume_cm3_g',1.16)]:add(r,k,v,'main PDF p6 Table 1; visual review R012_p6.png')
  add(r,'mass_loading_mg_cm2',2,'main PDF p4 CR2016 assembly','Approximately 2 mg/cm2 on each electrode; keep approximate qualifier.')
  add(r,'mass_loading_relation','approx','main PDF p4 CR2016 assembly')
 if ident=='R093':
  for k,v in [('voltage_lower_V',0),('voltage_upper_V',1.2)]:add(r,k,v,'main PDF p10 Fig8 discussion; explicit chosen device window; visual R093_p10.png')
  add(r,'capacitance_mass_basis','single_electrode_active_mass_with_factor_2','main PDF p4 Eq2: two-electrode k=2 and m is active mass on each electrode','This verifies capacitance formula only; current-density denominator still separately unresolved.')
 if ident=='R091':
  for k,v in [('BET_m2_g',1098.07),('N_at_pct',0.84),('O_at_pct',6.72)]:add(r,k,v,'main PDF p5 Table I and XPS paragraph; visual R091_p5.png')
  add(r,'total_pore_volume_reported',{'value':0.68,'unit_as_printed':'m3/g','normalized_cm3_g':None},'main PDF p5 Table I Vt header','Printed unit is m3/g, visually checked; do not silently reinterpret as cm3/g.')
  add(r,'pore_unit_review_required',True,'main PDF p5 Table I')
  add(r,'working_electrode_mass_loading_mg_cm2',4,'main PDF p2 working electrode preparation','Device p3 uses same working electrodes; preserve protocol context rather than assuming a new device-specific measured loading.')
 if ident=='R103':
  for k,v in [('voltage_lower_V',0),('voltage_upper_V',1)]:add(r,k,v,'main PDF p8 Fig7b GCD axes 0-1 V; direct axis reading, no curve digitization')
  add(r,'capacitance_mass_basis','single_electrode_LAC_mass_with_factor_2','new SI PDF p1 EqS2 and p2 definition of m')
  add(r,'supplement_evidence_path',str(ROOT/'已有_R103/molecules-3368983-supplementary.pdf'),'Europe PMC PMC11722339 supplementary package; matched title and authors')
 if ident=='R106':
  add(r,'active_mass_range_mg',[1.3,2.8],'main PDF p5 electrochemical testing','Reported range covers three- and two-electrode testing; not a per-sample loading and not mg/cm2.')
  if r['sample']=='FMCA':
   add(r,'EDS_composition',{'C_at_pct':65.93,'O_at_pct':22.39,'Si_at_pct':11.68,'C_wt_pct':53.57,'O_wt_pct':24.24,'Si_wt_pct':22.20},'new SI p1 Table S1, as-prepared FMCA EDS','Keep EDS separate from XPS. Non-negligible silicon means residue/composition needs review before pure-carbon pooling.')
   add(r,'Si_residue_review_required',True,'new SI p1 Table S1')
  add(r,'supplement_evidence_path',str(ROOT/'已有_R106/nanomaterials-3569537-supplementary.pdf'),'Europe PMC PMC12029297 supplementary package; matched title and authors')
 if ident=='R111':
  add(r,'device_single_electrode_active_mass_mg',2,'main PDF p3 section2.4 symmetric electrode fabrication','Absolute mass is reported; electrode area and mg/cm2 remain unfilled.')
  add(r,'capacitance_mass_basis','porous_carbon_mass_with_factor_2_device_formula','main PDF p3 Eq6 and definition of m','No explicit cycle-current normalization mass or electrolyte concentration; neither is inferred from cited papers.')

tracked=['current_density_A_g','electrolyte','concentration_value','voltage_lower_V','voltage_upper_V','BET_m2_g','total_pore_volume_cm3_g']
for r in rows:
 r['voltage_complete']=r.get('voltage_lower_V') is not None and r.get('voltage_upper_V') is not None
 r['condition_basic_complete']=all(r.get(k) is not None for k in ['cycle_count','retention_pct','current_density_A_g','electrolyte','concentration_value'])
 r['provisional_core_conditions']=bool(r.get('candidate_clean') and r.get('method')=='GCD' and r.get('system') in ['3E','2E_symmetric'] and r['condition_basic_complete'])
 r['provisional_minimal_features']=bool(r['provisional_core_conditions'] and r['voltage_complete'] and r.get('BET_m2_g') is not None and r.get('total_pore_volume_cm3_g') is not None)
 if r['record_id'] in {c['record_id'] for c in changes}:
  r['followup_review_note']='Candidate only. Baseline, cycle-current mass normalization, source overlap and any freeze still require final audit.'
def profile(a):return {'endpoint_rows':len(a),'material_keys':len({x['material_id'] for x in a}),'source_papers':len({x['paper_id'] for x in a})}
basic=[x for x in rows if x['provisional_core_conditions']]
summary={'date':'2026-10-17','changed_fields_including_metadata':len(changes),'affected_records':len({c['record_id'] for c in changes}),'affected_materials':len({r['material_id'] for r in rows if r['record_id'] in {c['record_id'] for c in changes}}),'affected_sources':sorted({c['paper_id'] for c in changes}),'all_existing_candidates':profile(rows),'basic_conditions':profile(basic),'basic_BET_voltage':profile([x for x in basic if x.get('BET_m2_g') is not None and x['voltage_complete']]),'basic_BET_voltage_totalpore':profile([x for x in rows if x['provisional_minimal_features']]),'eligible_records':0,'comparison_note':'Same provisional completeness criteria as prior snapshot. These counts are not purity, independence, baseline or quality admission; R106 silicon and R091 printed pore-unit issues are separate review flags.'}
out=ROOT/'现有数据补齐';out.mkdir(exist_ok=True)
for name,obj in [('循环稳定性逐记录候选_v2.json',rows),('字段补录日志.json',changes),('补录统计.json',summary)]:
 p=out/name
 if p.exists():raise FileExistsError('Do not overwrite an existing reviewed version: '+str(p))
 p.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
assert len(rows)==81 and all(not r['eligible_for_database'] for r in rows)
assert [r['retention_pct'] for r in rows]==[r['retention_pct'] for r in original]
assert [r['cycle_count'] for r in rows]==[r['cycle_count'] for r in original]
assert src.read_bytes()==json.dumps(original,ensure_ascii=False,indent=2).encode('utf-8') or json.loads(src.read_text(encoding='utf-8-sig'))==original
print(json.dumps(summary,ensure_ascii=False,indent=2))
