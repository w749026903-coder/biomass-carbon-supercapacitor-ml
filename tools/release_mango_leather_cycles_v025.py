"""Two explicit own-source cycling admissions; no fitting or parent mutation."""
from pathlib import Path
from contextlib import closing
import collections,decimal,json,sqlite3,sys,xml.etree.ElementTree as E
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tools'))
from extract_source_series_v13 import OUT as LIT,DB as LDB,MA,LE,sha,write,ro,clean
from data.literature_v13 import open_literature_database
from release_feature_freezes_v021 import load
OUT=ROOT/'循环稳定性数据库_v0.25_芒果核皮革循环准入_20261026';DB=OUT/'cycling_v0_25.sqlite'
PARENT=ROOT/'循环稳定性数据库_v0.24_苏铁绒跨年份循环准入_20261026';PSHA='08e9ff4f0781bb242e1b934aaed2240bafda02b5b913fe2f3e7706d869db1270'
JOBS=[('LP13_Mango_MK9_2E_C100000','v25:Mango_MK9_2E_C100000',MA,'MK9'),('LP13_Leather_ANSC8_3E_C10000','v25:Leather_ANSC8_3E_C10000',LE,'A-NSC8')]
PROFILES={'3E':['reported_3e','reported_3e_residue_sensitivity','reported_3e_sensitivity','reported_3e_all_years'],'2E_symmetric':['reported_2e','reported_2e_residue','reported_2e_approx','reported_2e_all_years']}


def write_api():
    assert not(OUT/'merge_manifest.json').exists(),'Never rewrite a sealed API'
    source=(PARENT/'ml_data.py').read_text('utf8').split('    def feature_conflicts_v24(self):')[0]
    source=source.replace('Read-only v0.24: two 2022 Cycas tests, one source, explicit all-years review.','Read-only v0.25: own Mango2E and Leather3E tests, original report variants retained.')
    source=source.replace("PARENT=ROOT/'循环稳定性数据库_v0.23_跨年份端点与家族隔离_20261026';NAME='_cycling_v023_parent_for_v024'", "PARENT=ROOT/'循环稳定性数据库_v0.24_苏铁绒跨年份循环准入_20261026';NAME='_cycling_v024_parent_for_v025'")
    source=source.replace('cycling_v0_23.sqlite','cycling_v0_24.sqlite').replace('Immutable v0.23 differs','Immutable v0.24 differs')
    source=source.replace('_v24','_v25').replace('explicit_v024_test_review','explicit_v025_test_review').replace("review_version='v0.24'","review_version='v0.25'")
    source=source.replace("r.get('all_years_admission_basis_v25')or r.get('all_years_admission_basis_v23')", "r.get('all_years_admission_basis_v25')or r.get('all_years_admission_basis_v24')or r.get('all_years_admission_basis_v23')")
    source=source.replace("'explicit_v023_test_review','explicit_v025_test_review'", "'explicit_v023_test_review','explicit_v024_test_review','explicit_v025_test_review'")
    source=source.replace("for version in ['v23','v24']:","for version in ['v23','v24','v25']:")
    source=source.replace("    def feature_matrix(self):\n        if self.profile", "    def feature_matrix(self):\n        for row in self.rows:\n            if row.get('literature_candidate_id_v25') and (self.profile not in row.get('admission_profiles_v25',[])or not row.get('baseline_reference')):raise DataNotReady('Explicit v0.25 purpose membership and author reference required')\n        if self.profile")
    source=source.replace("        if self.profile not in EXTENDED:return super().feature_matrix()", "        if self.profile not in EXTENDED:\n            projected=[dict(r,admission_profiles_v13=list(r['admission_profiles_v25']))if r.get('literature_candidate_id_v25')else r for r in self.rows]\n            matrix=base.Dataset(self.profile,projected,list(self.features)).feature_matrix()\n            if any(r.get('literature_candidate_id_v25')for r in self.rows):matrix['legacy_validator_projection_v25']='v0.25 explicitmembership projected onlyinmemory to unchangedv0.13 3Evalidator; no historicalreview backdating'\n            return matrix")
    source=source.replace("return old+[dict(r,value=json.loads(r['value_json']),evidence=json.loads(r['evidence_json']),selected=1,review_version='v0.25',stage='before_cycling',applies_to_systems_json='[\"3E\"]')", "return old+[dict(r,value=json.loads(r['value_json']),evidence=json.loads(r['evidence_json']),selected=1,review_version='v0.25',stage='before_cycling',applies_to_systems_json=json.dumps(sorted({v['system']for v in self.rows_v25.values()if v['material_id']==r['material_key']})))")
    source=source.replace("alias_kind='new_reviewed_test_same_material_two_salts'","alias_kind='new_source_bound_own_cycling_test'")
    source=source.replace("grouping_policy='v0.23 canonical DOI and explicit prior-work families retained in v0.24'","grouping_policy='Canonical DOI and explicit prior-work families; source grouping retained in v0.25'")
    compile(source,str(OUT/'ml_data.py'),'exec')
    (OUT/'ml_data.py').write_text(source,encoding='utf8')


def build():
    assert not OUT.exists()and sha(PARENT/'cycling_v0_24.sqlite')==PSHA
    assert sha(LDB)=='60f9245ad39234bea13a8b830ca41b328f36752cd27dcc4f2df1081ddb10167f'
    OUT.mkdir();contract=json.loads((PARENT/'data_contract.json').read_text('utf8'));litsha=sha(LDB)
    contract.update(schema='cycling_Mango_Leather_own_source_v25',version='0.25',database_file=DB.name,parent_database_sha256=PSHA,parent_api_directory=PARENT.relative_to(ROOT).as_posix(),literature_input_path=LDB.relative_to(ROOT).as_posix(),literature_input_sha256=litsha,new_endpoint_records=2,promoted_existing_endpoints=0,new_source_families=2,new_materials=2,research_training_authorized=False,model_fits=0,scope='Mango2025 symmetric2E andLeather2026 three-electrode own cycling; explicitworkingBET/current/role decisions retainallvariants',year_scope_policy_v25='Existing2023..2026 and explicitall-year purposes retained, newtests qualifyboththeirlegacyandall-yearprofiles',feature_semantics_v25='LeatherEDS/XPS percentbasis unreported; canonicalatom/wt channels null. MangoMK10EDS notinheritedbyMK9. Three-electrodemass2.61mg notusedfor5mgdevice. No guessedcurrentdenominator orbaselineindex.')
    write(OUT/'data_contract.json',contract);write_api()
    with load(PARENT,'_v024_build_mango_leather').Database()as old,open_literature_database(LDB,litsha)as lit,closing(sqlite3.connect(DB))as c:
        assert contract['source_family_rules']==[r['record']for r in lit.source_relations()]
        oldrows=old.fetch('all_review').rows;aliases=old.source_aliases();audit=[]
        for cid,key,doi,sample in JOBS:
            matches=[r for r in oldrows if lit.isolation_group(r['source_group'])=='doi:'+doi or any(t in json.dumps(r,ensure_ascii=False).lower()for t in (['mango','mangifera']if doi==MA else['leather','pickle pelt','a-nsc8']))]
            aliasmatches=[r for r in aliases if doi in json.dumps(r,ensure_ascii=False).lower()];assert not matches and not aliasmatches
            audit.append(dict(doi=doi,sample=sample,old_endpoint_matches=matches,old_alias_matches=aliasmatches,source_group_comparison='canonical DOI/prefix/family plus feedstock/sample keywords; no match, evidence is not a proof of unknown external reuse'))
        write(OUT/'identity_audit.json',dict(parent_database_sha256=PSHA,entries=audit,new_test_endpoints=2,new_materials=2,new_source_families=2))
        c.execute('pragma foreign_keys=on');c.executescript('''create table reviewed_endpoints_v25(endpoint_id text primary key,row_json text,review_json text);create table profile_membership_v25(endpoint_id text references reviewed_endpoints_v25,profile text,primary key(endpoint_id,profile));create table evidence_v25(evidence_id text primary key,endpoint_id text references reviewed_endpoints_v25,field_name text,value_json text,path text,sha256 text,locator text,selected integer check(selected in(0,1)),note text);create table changes_v25(change_id integer primary key,endpoint_id text references reviewed_endpoints_v25,field_name text,operation text,before_json text,after_json text,evidence_json text);create table material_fields_v25(material_key text,field_name text,value_json text,unit text,evidence_json text,primary key(material_key,field_name));create table literature_links_v25(candidate_id text primary key,endpoint_id text references reviewed_endpoints_v25,literature_database_sha256 text,status text);create table report_decisions_v25(endpoint_id text references reviewed_endpoints_v25,decision_id text,record_json text,primary key(endpoint_id,decision_id));''')
        candidates={r['candidate_id']:r for r in lit.tests()};protected={}
        for cid,key,doi,sample in JOBS:
            candidate=candidates[cid];raw=candidate['record'];source=ROOT/raw['evidence_source_path'];root=E.parse(source).getroot();year=2025 if doi==MA else 2026
            assert {int(y.text)for y in root.findall('.//article-meta/pub-date/year')}=={year}
            row={f:None for f in set(contract['model_material_features']+contract['extra_material_feature_whitelist'])}
            row.update(endpoint_id=key,doi=doi,identity_key='doi:'+doi,source_group='doi:'+doi,sample_name=sample,material_id='v25m:'+candidate['material_key'],material_key_v11='v25m:'+candidate['material_key'],literature_material_key=candidate['material_key'],test_id='v25test:'+key,source_year=year,year_basis='primary_XML_publication_date',scope_flags='[]',curve_group=raw['curve_group'],baseline_cycle=None,current_mass_basis=None,current_mass_basis_status='not_explicit; authorreported_A/g_preserved',canonical_current_A_g=None,canonical_current_A_g_status='not_physically_unified',temperature_C=None,temperature_C_status='not_numerically_reported_for_this_test',source_weight=1)
            fields=['system','method','retention_pct','retention_relation','cycle_count','reported_current_A_g','cycle_voltage_lower_V','cycle_voltage_upper_V','electrolyte','concentration_mol_L','reference_electrode','baseline_reference']
            for f in fields:row[f]=raw[f]
            profiles=PROFILES[row['system']]
            row.update(metric_kind='capacitance_retention',eligible=1,admission_status='approved_for_reported_protocol',admission_profiles_v25=profiles,workflow_status='approved_v025_reported_protocol',literature_candidate_id_v25=cid,retention_pct_status='own_original_figure_printed_label',reported_current_A_g_status='own_cycle_methods_and_results'if doi==LE else'own100k_GCD_cycle_results',cycle_voltage_lower_V_status='own_cycle_explicit_protocol'if doi==LE else'actual_first_and_last_cycle_GCD',cycle_voltage_upper_V_status='own_cycle_explicit_protocol'if doi==LE else'actual_first_and_last_cycle_GCD',baseline_reference_status='author_normalized_initial_capacitance_no_exact_index_inferred',XPS_percentage_basis='unreported'if doi==LE else'not_quantified_for_MK9',XPS_N_reported_pct=None,XPS_O_reported_pct=None)
            proof=[]
            def ev(field,value,path,locator,selected=1,note=''):
                path=Path(path);rel=path.relative_to(ROOT).as_posix();digest=sha(path);protected[rel]=digest
                proof.append(dict(evidence_id=key+'#'+field+'#'+str(len(proof)),endpoint_id=key,field_name=field,value_json=json.dumps(value,ensure_ascii=False),path=rel,sha256=digest,locator=locator,selected=selected,note=note))
            for f in fields+['source_year','eligible']:ev(f,row[f],source,raw['locator'],note='Own test-bound report; optional unknown mass denominator/baseline index do not invalidate established empirical purpose')
            graph=LIT/'evidence'/('d5ra02129d-f10.jpg'if doi==MA else'd6ra04144b-f5.jpg')
            ev('retention_pct',row['retention_pct'],graph,'ActualFig10a rightaxisgreen79.3%,leftaxisblueCE65%'if doi==MA else'ActualFig5F printed99.2%,10000cycleaxis')
            for f in ['cycle_voltage_lower_V','cycle_voltage_upper_V']:ev(f,row[f],graph,'ActualFig10b/c/d first/last cycling0..1.2V'if doi==MA else'OwnFig5A/B0..0.5AgAgCl; body13samewindow andbody28explicitcycle0..0.5V')
            def feature(field,name,unit):
                fs=lit.facts(doi=doi,sample=sample,field=name);selected=lit.canonical_material_features_v13(doi,sample)['values'][name];row[field]=selected
                for f in fs:ev(field,f['value'],ROOT/f['source_path'],f['locator'],int(f['value']==selected),f['method']+'; original report retained, explicitv13working/precision decision ifmultiple')
                return fs
            mapping={'BET_m2_g':('BET_surface_area_m2_g','m2/g'),'total_pore_volume_cm3_g':('total_pore_volume_cm3_g','cm3/g')}
            if doi==MA:
                mapping['average_pore_diameter_nm']=('mean_pore_diameter_reported_nm','nm')
            else:
                mapping.update(average_pore_diameter_nm=('average_pore_diameter_reported_nm','nm'),water_contact_angle_deg_v15=('water_contact_angle_time_unspecified_deg','degree'),XPS_N_reported_pct=('XPS_N_reported_pct','%basis_unspecified'),XPS_O_reported_pct=('XPS_O_reported_pct','%basis_unspecified'),XPS_S_reported_pct_v15=('XPS_S_reported_pct','%basis_unspecified'))
            for field,(name,unit)in mapping.items():feature(field,name,unit)
            ev('XPS_percentage_basis',row['XPS_percentage_basis'],source,'LeatherTable2 footnoteoutsideEDS/insideXPS; no atom/wt header'if doi==LE else'OwnMK9 XPS survey energies, no elemental percent quantification; Fig4hEDS belongsMK10')
            if doi==MA:
                row.update(carbonization_temperature_C=900,carbonization_duration_h=None,carbonization_heating_rate_C_min=10,activation_temperature_C=None,activation_duration_h=None,active_mass_mg_v14=5,active_mass_mg_v14_status='author_approximately_total_device_active_mass_not3E2point61mg',XRD_d002_nm=.35,XRD_d002_nm_status='author_approximate3point5A_converted_to_nm')
                processfields=['carbonization_temperature_C','carbonization_duration_h','carbonization_heating_rate_C_min','activation_temperature_C','activation_duration_h','active_mass_mg_v14','XRD_d002_nm']
                for f in processfields:ev(f,row[f],source,'body5single900CN2/10Cmin/noactivator/noholdtime; body8own2x2.5mg~5mgdevice; body13d002~3.5A',note='No3Eworkingmass2.61mg transfer; authorapproximation andunitconversion retained')
                decisions=[dict(id='axis_roles',reported_prose_CE_pct=79.3,actual_figure_CE_pct=65,actual_figure_retention_pct=79.3,action='Selectrightaxis retentionlabel; retainbody32wrongrole, do not useCEaslabel/predictor'),dict(id='BET_working',detailed_table_body_conclusion=1348.5,abstract_dissent=1348.9,action='OwnTable1workingvalue supportedbybody11/conclusion34; noerratum orrawrecalculation claim'),dict(id='scope_mass',MK10_EDS_not_assigned_to_MK9=True,three_electrode_MK9_active_mass_mg=2.61,device_total_active_mass_approx_mg=5,action='Deviceonlymass bound; unknowncurrentmassdenominator not inferredfromcapacitanceformula')]
                ev('coulombic_efficiency_pct',79.3,source,'body32 labels79.3 asCE (axisrole dissent)',selected=0);ev('coulombic_efficiency_pct',65,graph,'Fig10a leftaxisblue65%',note='Response only, not modelpredictor or cyclingretention')
            else:
                row.update(precarbonization_temperature_C=400,precarbonization_duration_h=1,activation_temperature_C=800,activation_duration_h=1,heating_rate_C_min=None,active_mass_mg_v14=None,contact_angle_time_ms_v15=None)
                processfields=['precarbonization_temperature_C','precarbonization_duration_h','activation_temperature_C','activation_duration_h','heating_rate_C_min','active_mass_mg_v14','contact_angle_time_ms_v15']
                for f in processfields:ev(f,row[f],source,'body8precarbon400C1hN2 +final800C1hN2,KOHchar1:3; extra400Cactivationwording ambiguous; body10castingnotmass; Table2contact28timeunreported',note='No additionalhold summed, no heatingrateoractive mass guessed')
                ev('reported_current_A_g',1,source,'OwncomparisonTable1 row18 cyclingcolumn1A/g',selected=0,note='Competes withactualcaption/methods/results10; retainoriginal')
                ev('retention_pct',99,source,'OwncomparisonTable1 row18 retention99%',selected=0,note='Matchingintegerrounding of99.2, not authorerratum')
                ev('reported_current_A_g',10,source,'OwnFig5Fcaption andbody13/28 explicitcycling10A/g')
                decisions=[dict(id='cycle_current_and_rounding',own_cycle_methods_caption_results_current_A_g=10,comparison_current_A_g=1,original_figure_retention_pct=99.2,comparison_retention_pct=99,action='Owncycleprotocol selected, currentdissent retained; retentionintegerrounding agrees'),dict(id='BET_precision',body=2214.5,table=2215,half_up_rounded=str(decimal.Decimal('2214.50').quantize(decimal.Decimal('1'),rounding=decimal.ROUND_HALF_UP)),action='Additionalownprecision selected, not higherperformancesample selection'),dict(id='composition_basis',EDS_N=28.59,XPS_N=31.12,XPS_O=8.91,basis='unreported',action='Method-specific percentchannels preserved; N/O atomic andweight projections remainnull; no Crzero fromresidueclaim'),dict(id='thermal_stage',precarbonization=[400,1],final_activation=[800,1],extra400Cactivation_sentence='ambiguous_not_summed',action='Separatestages, unknownratesandcastingmass remainunknown')]
            materialfields=list(mapping)+processfields+['XPS_percentage_basis']
            for f in materialfields:
                unit=mapping[f][1]if f in mapping else'basis'if f=='XPS_percentage_basis'else'mg'if f=='active_mass_mg_v14'else'nm'if f=='XRD_d002_nm'else'degreeC'if'temperature'in f else'degreeC/min'if'heating_rate'in f else'ms'if'time_ms'in f else'h'
                c.execute('insert into material_fields_v25 values(?,?,?,?,?)',(row['material_id'],f,json.dumps(row[f]),unit,json.dumps([p for p in proof if p['field_name']==f],ensure_ascii=False)))
            review=dict(endpoint_id=key,disposition='approved_reported_protocol',approved_profiles=profiles,open_feature_issues=['MK9_abstract_BET_dissent_retained']if doi==MA else['EDS_XPS_percent_basis_unreported','extra400Cactivation_sentence_ambiguous'],reason='Ownoriginalcyclingendpoint andactualGCD configuration/electrolyte/current/window plus same-materialBET bound',caveats=['No guessedcurrentmassdenominator or exactinitialcycleindex','Allmaterial/process/curve/auxiliary/cycling labels fromsource heldouttogether','Workingandprecisiondecisions preserveoriginalreports; noerratum claim','No newfit or performanceimprovement claim'],review_version='v0.25',literature_candidate_id=cid,model_fits=0)
            c.execute('insert into reviewed_endpoints_v25 values(?,?,?)',(key,json.dumps(row,ensure_ascii=False),json.dumps(review,ensure_ascii=False)))
            c.executemany('insert into profile_membership_v25 values(?,?)',[(key,p)for p in profiles]);c.executemany('insert into evidence_v25 values(:evidence_id,:endpoint_id,:field_name,:value_json,:path,:sha256,:locator,:selected,:note)',proof)
            for f in sorted(row):c.execute('insert into changes_v25(endpoint_id,field_name,operation,before_json,after_json,evidence_json)values(?,?,?,?,?,?)',(key,f,'insert_new_reviewed_endpoint','null',json.dumps(row[f],ensure_ascii=False),json.dumps([e for e in proof if e['field_name']==f],ensure_ascii=False)))
            c.execute('insert into literature_links_v25 values(?,?,?,?)',(cid,key,litsha,'admitted_reported_protocol_v025'))
            c.executemany('insert into report_decisions_v25 values(?,?,?)',[(key,d['id'],json.dumps(d,ensure_ascii=False))for d in decisions])
        c.commit()
    write(OUT/'protected_inputs.json',[dict(path=p,sha256=h)for p,h in sorted(protected.items())]+[dict(path=LDB.relative_to(ROOT).as_posix(),sha256=litsha),dict(path=(PARENT/'cycling_v0_24.sqlite').relative_to(ROOT).as_posix(),sha256=PSHA)])
    print('Built unsealed v0.25: two sources/two tests, no fit')


if __name__=='__main__':
    if len(sys.argv)!=2 or sys.argv[1]!='build':raise SystemExit('One-use build only; verification/seal separate')
    build()
