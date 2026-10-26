"""One-use release of two source-bound Cycas cycling purposes; verify is read-only."""
from pathlib import Path
from contextlib import closing
import collections,json,sqlite3,sys,xml.etree.ElementTree as E
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tools'))
from extract_porous_series_v12 import OUT as LIT,DB as LDB,CY,sha,write,ro,clean
from data.literature_v12 import open_literature_database
from release_feature_freezes_v021 import load
OUT=ROOT/'循环稳定性数据库_v0.24_苏铁绒跨年份循环准入_20261026';DB=OUT/'cycling_v0_24.sqlite'
PARENT=ROOT/'循环稳定性数据库_v0.23_跨年份端点与家族隔离_20261026';PSHA='ccebb63c33c87b3f726fa044cf83973ab7ec9fb613ea13bb725b6ae35445d9b5'
JOBS=[('LP12_Cycas_KOH_3E_C10000','v24:CFHPC2_KOH_3E_C10000'),('LP12_Cycas_Na2SO4_3E_C10000','v24:CFHPC2_Na2SO4_3E_C10000')]
PROFILE='reported_3e_all_years'

def build():
    assert not DB.exists()and not(OUT/'merge_manifest.json').exists();assert sha(PARENT/'cycling_v0_23.sqlite')==PSHA
    contract=json.loads((PARENT/'data_contract.json').read_text('utf8'));litsha=sha(LDB)
    contract.update(schema='cycling_Cycas_two_salts_all_years_v24',database_file=DB.name,parent_database_sha256=PSHA,literature_input_path=LDB.relative_to(ROOT).as_posix(),literature_input_sha256=litsha,new_endpoint_records=2,promoted_existing_endpoints=0,research_training_authorized=False,model_fits=0,scope='Two2022Cycas3E tests, same material/two salts/one source; all_years3E only; N/O conflict remains masked',year_scope_policy_v24='Legacy2023..2026 profiles unchanged; only two explicit2022 tests added to all_years3E',feature_conflict_policy_v24='HPC2 Table1/abstract XPS N/O competition retained; N/O and reportedpct aliases null in all new cycling inputs; no density/Cv or EIS outcome substituted')
    write(OUT/'data_contract.json',contract)
    with load(PARENT,'_v023_build_cycas').Database()as old,open_literature_database(LDB,litsha)as lit,closing(sqlite3.connect(DB))as c:
        assert contract['source_family_rules']==[r['record']for r in lit.source_relations()]
        oldrows=old.fetch('all_review').rows;matches=[r for r in oldrows if r['source_group']=='doi:'+CY or 'CF-HPC'in str(r.get('sample_name'))];assert not matches
        aliases=[r for r in old.source_aliases()if CY in str(r)];assert not aliases
        write(OUT/'identity_audit.json',dict(parent_database_sha256=PSHA,source_group='doi:'+CY,old_endpoint_matches=matches,old_alias_matches=aliases,new_materials=1,new_test_endpoints=2,independent_source_groups_added=1,same_literature_material_for_both=True))
        c.execute('pragma foreign_keys=on');c.executescript('''create table reviewed_endpoints_v24(endpoint_id text primary key,row_json text,review_json text);create table profile_membership_v24(endpoint_id text references reviewed_endpoints_v24,profile text,primary key(endpoint_id,profile));create table evidence_v24(evidence_id text primary key,endpoint_id text references reviewed_endpoints_v24,field_name text,value_json text,path text,sha256 text,locator text,selected integer check(selected in(0,1)),note text);create table changes_v24(change_id integer primary key,endpoint_id text references reviewed_endpoints_v24,field_name text,operation text,before_json text,after_json text,evidence_json text);create table material_fields_v24(material_key text,field_name text,value_json text,unit text,evidence_json text,primary key(material_key,field_name));create table literature_links_v24(candidate_id text primary key,endpoint_id text references reviewed_endpoints_v24,literature_database_sha256 text,status text);create table feature_conflicts_v24(material_key text,field_name text,record_json text,primary key(material_key,field_name));''')
        candidates={r['candidate_id']:r for r in lit.tests()};protected={};shared_material=None
        for cid,key in JOBS:
            candidate=candidates[cid];raw=candidate['record'];source=ROOT/raw['evidence_source_path'];root=E.parse(source).getroot();assert {int(y.text)for y in root.findall('.//article-meta/pub-date/year')}=={2022}
            caption=clean(next(x for x in root.findall('.//fig')if x.get('id')=='fig8').find('caption'));assert 'Capacitance retention of CF-HPC-2 at 1 A' in caption
            material='v24m:'+candidate['material_key'];assert shared_material in[None,material];shared_material=material
            row={f:None for f in set(contract['model_material_features']+contract['extra_material_feature_whitelist'])}
            row.update(endpoint_id=key,doi=CY,identity_key='doi:'+CY,source_group='doi:'+CY,sample_name='CF-HPC-2',material_id=material,material_key_v11=material,literature_material_key=candidate['material_key'],test_id='v24test:'+key,source_year=2022,year_basis='primary_XML_publication_date',scope_flags='[]',curve_group=raw['curve_group'],baseline_cycle=None,current_mass_basis=None,current_mass_basis_status='not_explicit; reported_A/g_preserved',canonical_current_A_g=None,canonical_current_A_g_status='not_physically_unified',temperature_C=None,temperature_C_status='room_temperature_not_numeric25',source_weight=.5)
            fields=['system','method','retention_pct','retention_relation','cycle_count','reported_current_A_g','cycle_voltage_lower_V','cycle_voltage_upper_V','electrolyte','concentration_mol_L','reference_electrode','baseline_reference']
            for f in fields:row[f]=raw[f]
            row.update(metric_kind='capacitance_retention',eligible=1,admission_status='approved_for_reported_protocol',admission_profiles_v24=[PROFILE],workflow_status='approved_v024_reported_protocol',literature_candidate_id_v24=cid,cycle_voltage_lower_V_status='own_salt_GCD_plus_matched_common_protocol',cycle_voltage_upper_V_status='own_salt_GCD_plus_matched_common_protocol',reference_electrode_status='explicit_common3E_HgHgO_method_p8_and_same_method_p20',retention_pct_status='own_reported_figure_printed_endpoint',reported_current_A_g_status='actual_cycle_Fig8f_caption',baseline_reference_status='author_initial_specific_capacitance_not_invented_cycle1',XPS_percentage_basis='atomic_explicit',joint_carbonization_activation_temperature_C_v23=700,joint_carbonization_activation_duration_h_v23=2,carbonization_temperature_C=700,carbonization_duration_h=2,heating_rate_C_min=5,activation_temperature_C=None,activation_duration_h=None,joint_process_not_two_heating_operations_v24=True,mass_loading_mg_cm2=2.5,mass_loading_mg_cm2_status='author_ca_approximate')
            proof=[]
            def ev(field,value,path,locator,selected=1,note=''):
                path=Path(path);digest=sha(path);rel=path.relative_to(ROOT).as_posix();protected[rel]=digest
                proof.append(dict(evidence_id=key+'#'+field+'#'+str(len(proof)),endpoint_id=key,field_name=field,value_json=json.dumps(value,ensure_ascii=False),path=rel,sha256=digest,locator=locator,selected=selected,note=note))
            for f in fields+['source_year','eligible']:ev(f,row[f],source,raw['evidence'],note='Owncycling endpoint plus matchedsame-material/saltGCD and commonprotocol; not a new continuous-cycle GCD trace')
            ev('XPS_percentage_basis','atomic_explicit',source,'OwnTable1 header explicitly XPS(at%); basis known while N/O labels compete')
            ev('retention_pct',row['retention_pct'],LIT/'evidence/d2ra02141b-f8.jpg','ActualFig8f '+raw['electrolyte']+' printed endpoint; 10000cycle axis')
            ev('reported_current_A_g',1,source,'Fig8f owncaption explicitly1A/g for bothsaltcurves')
            graph=LIT/'evidence'/('d2ra02141b-f7.jpg'if raw['electrolyte']=='KOH'else'd2ra02141b-f8.jpg')
            for f in['cycle_voltage_lower_V','cycle_voltage_upper_V']:ev(f,row[f],graph,'OwnmatchedsaltGCD Fig7b/e −1..0HgHgO'if raw['electrolyte']=='KOH'else'Own3E Fig8b/e 0..1; body20 same method; not device2MNa2SO4 Fig9')
            mapping={'BET_m2_g':('BET_surface_area_m2_g','m2/g'),'total_pore_volume_cm3_g':('total_pore_volume_cm3_g','cm3/g'),'micropore_volume_cm3_g':('micropore_volume_cm3_g','cm3/g'),'micropore_surface_area_m2_g':('micropore_surface_area_m2_g','m2/g'),'Raman_ID_IG':('Raman_ID_IG','ratio'),'C_at_pct':('XPS_C_at_pct','at%'),'S_at_pct':('XPS_S_at_pct','at%'),'XPS_S_reported_pct_v15':('XPS_S_at_pct','at%')}
            for field,(name,unit)in mapping.items():
                fs=lit.facts(doi=CY,sample='CF-HPC-2',field=name);assert not any('conflict'in f['review_status']for f in fs);values={f['value']for f in fs if f['value']is not None};assert len(values)==1
                row[field]=values.pop()
                for f in fs:ev(field,row[field],ROOT/f['source_path'],f['locator'],note=f['method'])
            for field in['N_at_pct','O_at_pct','XPS_N_reported_pct','XPS_O_reported_pct']:
                element='N'if 'N_'in field else'O';fs=lit.facts(doi=CY,sample='CF-HPC-2',field='XPS_'+element+'_at_pct');assert {f['value']for f in fs}=={3.54,4.09}
                row[field]=None
                for f in fs:ev(field,f['value'],ROOT/f['source_path'],f['locator'],selected=0,note='Unresolvedabstract/table elemental labelcompetition; preserveboth, not selected')
                ev(field,None,source,'Abstract vsTable1; actualFig4 has no resolvingatom% labels',note='Canonicalfeature frozen, unrelated validcyclingpurpose remains')
                conflict=dict(kind='XPS_N_O_label_competition',raw_reports=[dict(value=f['value'],field=f['field_name'],path=f['source_path'],locator=f['locator'])for f in fs],canonical_value=None,status='unresolved_feature_only',not_resolved_by_cycle_admission=True)
                previous=c.execute('select record_json from feature_conflicts_v24 where material_key=?and field_name=?',(material,field)).fetchone()
                if previous:assert json.loads(previous[0])==conflict
                else:c.execute('insert into feature_conflicts_v24 values(?,?,?)',(material,field,json.dumps(conflict,ensure_ascii=False)))
            processfields=['joint_carbonization_activation_temperature_C_v23','joint_carbonization_activation_duration_h_v23','carbonization_temperature_C','carbonization_duration_h','heating_rate_C_min','mass_loading_mg_cm2']
            for f in processfields:ev(f,row[f],source,'body6 single700C2hAr5C/min, rawNaHCO3:CF2:1; body8 ca2.5mg/cm2',note='Onejointprocess, no independentpostactivation; loadingauthorapproximate')
            for field in list(mapping)+['N_at_pct','O_at_pct','XPS_N_reported_pct','XPS_O_reported_pct']+processfields:
                value=row[field];unit=mapping[field][1]if field in mapping else'at%'if field in['N_at_pct','O_at_pct','XPS_N_reported_pct','XPS_O_reported_pct']else'degC'if'temperature'in field else'h'if'duration'in field else'degC/min'if'heating_rate'in field else'mg/cm2'
                previous=c.execute('select value_json from material_fields_v24 where material_key=?and field_name=?',(material,field)).fetchone()
                if previous:assert json.loads(previous[0])==value
                else:c.execute('insert into material_fields_v24 values(?,?,?,?,?)',(material,field,json.dumps(value),unit,json.dumps([e for e in proof if e['field_name']==field],ensure_ascii=False)))
            review=dict(endpoint_id=key,disposition='approved_reported_protocol',approved_profiles=[PROFILE],open_feature_issues=['HPC2_XPS_N_O_label_competition'],caveats=['2022onlyexplicitall_years3E, legacy2023..2026unchanged','OwnGCD matchedsame-material/salt commonprotocol; unknown currentmass denominator andexactinitialcycleindex retained','SameCF-HPC2/twosalts is one source family; no independentvalidation between these rows','Hypotheticalpurity/density not inferred; N/Oconflict remains, Cv/Ragoneissuesnotusedascyclinglevidence'],reason='Ownprintedcyclingendpoint/10000/current1Ag, per-salt3E electrolyte/window, commonHgHgO andBETbound',review_version='v0.24',literature_candidate_id=cid,model_fits=0)
            c.execute('insert into reviewed_endpoints_v24 values(?,?,?)',(key,json.dumps(row,ensure_ascii=False),json.dumps(review,ensure_ascii=False)));c.execute('insert into profile_membership_v24 values(?,?)',(key,PROFILE))
            c.executemany('insert into evidence_v24 values(:evidence_id,:endpoint_id,:field_name,:value_json,:path,:sha256,:locator,:selected,:note)',proof)
            for f in sorted(row):c.execute('insert into changes_v24(endpoint_id,field_name,operation,before_json,after_json,evidence_json)values(?,?,?,?,?,?)',(key,f,'insert_new_reviewed_endpoint',json.dumps(None),json.dumps(row[f],ensure_ascii=False),json.dumps([e for e in proof if e['field_name']==f],ensure_ascii=False)))
            c.execute('insert into literature_links_v24 values(?,?,?,?)',(cid,key,litsha,'admitted_reported_protocol_v024'))
        c.commit()
    write(OUT/'protected_inputs.json',[dict(path=p,sha256=h)for p,h in sorted(protected.items())]+[dict(path=LDB.relative_to(ROOT).as_posix(),sha256=litsha),dict(path=(PARENT/'cycling_v0_23.sqlite').relative_to(ROOT).as_posix(),sha256=PSHA)])
    print('Built draft v0.24: two tests/one new source; no fitting')

def verify(prepare=False):
    checks=[]
    def ck(n,ok):
        if not ok:raise AssertionError(n)
        checks.append(n)
    for p in json.loads((OUT/'protected_inputs.json').read_text('utf8')):ck('protected:'+p['path'],sha(ROOT/p['path'])==p['sha256'])
    for folder in[PARENT,LIT]:
        for p in json.loads((folder/'merge_manifest.json').read_text('utf8'))['outputs']:ck('payload:'+p['path'],sha(ROOT/p['path'])==p['sha256'])
    digest=sha(DB)
    with closing(ro(DB))as c:ck('integrity',c.execute('pragma integrity_check').fetchone()[0]=='ok');ck('foreignkeys',not c.execute('pragma foreign_key_check').fetchall());ck('2new_tests',c.execute('select count(*)from reviewed_endpoints_v24').fetchone()[0]==2)
    child=load(OUT,'_v024_verify');parent=load(PARENT,'_v023_pinned_cycas');matrices={};counts={}
    with child.Database()as new,parent.Database()as old,open_literature_database(LDB,sha(LDB))as lit:
        before={r['endpoint_id']:r for r in old.fetch('all_review').rows};after={r['endpoint_id']:r for r in new.fetch('all_review').rows};ck('284observations',len(after)==284);ck('183raw_source_groups',len({r['source_group']for r in after.values()})==183);ck('two_exact_IDs',set(after)-set(before)=={k for cid,k in JOBS})
        for key,r in before.items():ck('original_row:'+key,after[key]==r)
        expected={'reported_3e':(43,31),'reported_3e_residue_sensitivity':(44,32),'reported_3e_sensitivity':(52,38),'reported_2e':(30,24),'reported_2e_residue':(32,25),'reported_2e_approx':(34,27),'reported_3e_all_years':(47,34),'reported_2e_all_years':(32,26)}
        for p,want in expected.items():
            ds=new.fetch(p);m=ds.feature_matrix();matrices[p]=m;counts[p]=dict(rows=len(ds.rows),source_families=len(set(m['groups'])));ck('count:'+p,(counts[p]['rows'],counts[p]['source_families'])==want)
            oldds=old.fetch(p);oldids={r['endpoint_id']for r in oldds.rows};newids={k for cid,k in JOBS}if p==PROFILE else set();ck('exact_members:'+p,{r['endpoint_id']for r in ds.rows}==oldids|newids)
            oldmatrix=oldds.feature_matrix();position={r['endpoint_id']:i for i,r in enumerate(ds.rows)}
            for i,r in enumerate(oldds.rows):
                j=position[r['endpoint_id']];ck('old_X_y_group_weight:'+p+':'+r['endpoint_id'],all(m[f][j]==oldmatrix[f][i]for f in['X','y','groups','sample_weight']))
            for g in set(m['groups']):ck('family_weight:'+p+g,abs(sum(w for group,w in zip(m['groups'],m['sample_weight'])if group==g)-1)<1e-12)
            for i,fold in enumerate(ds.source_folds(len(set(m['groups'])))):ck('fold:'+p+str(i),not{m['groups'][j]for j in fold['train']}&{m['groups'][j]for j in fold['test']})
            mm=new.method_specific_material_matrix(p);ck('no_fit_or_impute:'+p,mm['estimators_fitted']==0 and not mm['imputed']and all(mask==(v is None)for xs,ms in zip(mm['X'],mm['missing_mask'])for v,mask in zip(xs,ms)))
            ck('no_label_identity_X:'+p,not{'retention_pct','doi','source_group','source_family_group_v23','endpoint_id','capacitance_F_g','CE'}&set(mm['feature_names']))
        ds=new.fetch(PROFILE);m=ds.feature_matrix();indices=[i for i,r in enumerate(ds.rows)if r['source_group']=='doi:'+CY];ck('twosalts_one_weighted_source',len(indices)==2 and[m['sample_weight'][i]for i in indices]==[.5,.5]);ck('no_salt_split',all((indices[0]in f['test'])==(indices[1]in f['test'])for f in ds.source_folds(5)))
        mm=new.method_specific_material_matrix(PROFILE)
        for cid,key in JOBS:
            r=new.by_endpoint(key);ck('only_2022_all_years:'+key,r['source_year']==2022 and r['admission_profiles_v24']==[PROFILE]);ck('mass_unknown_allowed:'+key,r['current_mass_basis']is None and r['canonical_current_A_g']is None and r['baseline_cycle']is None);ck('one_joint_process:'+key,r['joint_carbonization_activation_temperature_C_v23']==700 and r['activation_temperature_C']is None and r['material_density_g_cm3']is None)
            ck('own_feature_values:'+key,(r['BET_m2_g'],r['Raman_ID_IG'],r['total_pore_volume_cm3_g'],r['micropore_volume_cm3_g'])==(516.7,.91,.33,.14))
            for f in['N_at_pct','O_at_pct','XPS_N_reported_pct','XPS_O_reported_pct']:
                proof=new.evidence(key,f);ck('conflict_raw_and_null:'+key+f,r[f]is None and{e['value']for e in proof if not e['selected']}=={3.54,4.09}and any(e['selected']and e['value']is None for e in proof))
            i=mm['endpoint_ids'].index(key)
            for f in['XPS_N_atomic_pct_v15','XPS_N_weight_pct_v15','XPS_O_atomic_pct_v15','XPS_O_weight_pct_v15']:ck('method_mask:'+key+f,mm['X'][i][mm['feature_names'].index(f)]is None)
            ck('selected_own_endpoint:'+key,any(e['selected']and e['value']==r['retention_pct']and e['path'].endswith('d2ra02141b-f8.jpg')for e in new.evidence(key,'retention_pct')))
            ck('open_feature_issue_not_cleared:'+key,new.holds(key)['open_feature_issues']==['HPC2_XPS_N_O_label_competition'])
            ck('explicit_XPS_basis_proof:'+key,any(e['selected']and e['value']=='atomic_explicit'and'Table1'in e['locator']for e in new.evidence(key,'XPS_percentage_basis')))
        r=new.by_endpoint(JOBS[0][1])
        for field,value in[('reported_current_A_g',None),('BET_m2_g',0),('method','CV'),('retention_pct',float('nan')),('cycle_voltage_upper_V',-1),('baseline_reference',None),('all_years_admission_basis_v24','unreviewed'),('admission_profiles_v24',[])]:
            item=dict(r,all_years_admission_basis_v24='explicit_v024_test_review');item[field]=value
            try:child.Dataset(PROFILE,[item],list(ds.features)).feature_matrix()
            except child.DataNotReady:ck('reject:'+field,True)
            else:raise AssertionError('Invalidpurposeaccepted:'+field)
        try:child.Dataset('reported_3e',[r],list(new.fetch('reported_3e').features)).feature_matrix()
        except child.DataNotReady:ck('old_year_gate_preserved',True)
        else:raise AssertionError('2022 wrongly enters legacy profile')
        ck('fixed38_exact',new.reviewed_pending_batch()==old.reviewed_pending_batch()and len(new.reviewed_pending_batch())==38)
        ck('old15freezes',sum(r.get('review_version')=='v0.21'for r in new.field_changes(include_history=True))==15)
        ck('101point7_not_clipped',new.by_endpoint('v22:NFACc_2E_C10000')['retention_pct']==101.7)
        ck('4material_alias_conflict_masks',len(new.feature_conflicts_v24())==4)
        ck('parent_source_families',new.source_family_rules()==old.source_family_rules());ck('two_links',len(new.literature_links())==len(old.literature_links())+2)
        candidates={r['candidate_id']:r for r in lit.tests()};links={r['candidate_id']:r for r in new.literature_links()}
        for cid,key in JOBS:
            row=new.by_endpoint(key);raw=candidates[cid]['record'];ck('label_protocol_crosslink:'+key,links[cid]['endpoint_id']==key and all(row[f]==raw[f]for f in['retention_pct','cycle_count','reported_current_A_g','electrolyte','concentration_mol_L','cycle_voltage_lower_V','cycle_voltage_upper_V','reference_electrode']))
    ck('readonly_hash',sha(DB)==digest)
    report=dict(status='passed',database_sha256=digest,check_count=len(checks),checks=sorted(checks),observations=284,raw_source_groups=183,profiles=counts,new_endpoints=2,new_materials=1,promoted_existing_endpoints=0,new_purpose_admissions=2,new_source_families=1,original_fixed_resolved=1,original_fixed_pending=38,legacy_feature_cells_frozen=15,new_material_feature_conflict_aliases=4,model_fits=0,full_goal_complete=False)
    if prepare:
        assert not(OUT/'merge_manifest.json').exists();write(OUT/'verification.json',report);write(OUT/'summary.json',{k:v for k,v in report.items()if k!='checks'});write(OUT/'model_inputs_preflight.json',matrices)
    else:
        assert json.loads((OUT/'verification.json').read_text('utf8'))==report;assert json.loads((OUT/'model_inputs_preflight.json').read_text('utf8'))==matrices
        if(OUT/'merge_manifest.json').exists():
            for p in json.loads((OUT/'merge_manifest.json').read_text('utf8'))['outputs']:assert sha(ROOT/p['path'])==p['sha256']
    print(json.dumps({k:v for k,v in report.items()if k!='checks'},ensure_ascii=False))

def seal():
    assert not(OUT/'merge_manifest.json').exists()
    from verify_cycas_chain_v024 import run
    run(False)
    paths=[p for p in OUT.rglob('*')if p.is_file()]+[ROOT/'tools/release_cycas_cycles_v024.py',ROOT/'tools/verify_cycas_chain_v024.py']
    write(OUT/'merge_manifest.json',dict(version='cycling_v0.24',parent_sha256=PSHA,outputs=[dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p),bytes=p.stat().st_size)for p in sorted(paths)],model_fits=0,scientific_goal_complete=False))
    write(ROOT/'data/current_database.json',dict(version='cycling_v0.24',version_directory=OUT.relative_to(ROOT).as_posix(),database_file=DB.name,sha256=sha(DB),parent_database_file=(PARENT/'cycling_v0_23.sqlite').relative_to(ROOT).as_posix(),default_profile='reported_3e',stage='two_Cycas2022_all_years3E_tests_feature_conflicts_retained',ready_for_training_inputs=True,research_training_authorized=False,all_records_admitted=False))

if __name__=='__main__':
    if len(sys.argv)!=2 or sys.argv[1]not in['build','prepare','verify','seal']:raise SystemExit('One-usebuild/prepare/seal; verifyread-only')
    if sys.argv[1]=='prepare':verify(True)
    else:globals()[sys.argv[1]]()
