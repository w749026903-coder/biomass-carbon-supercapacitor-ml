"""Two individually reviewed test admissions; source-family grouped inputs, no fitting."""
from pathlib import Path
from contextlib import closing
import collections,json,sqlite3,sys,xml.etree.ElementTree as E,math
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tools'))
from extract_biomass_series_v11 import OUT as LIT,DB as LDB,TAC,BTC,PRIOR,sha,write,ro
from release_feature_freezes_v021 import load
from data.literature_v11 import open_literature_database
OUT=ROOT/'循环稳定性数据库_v0.23_跨年份端点与家族隔离_20261026';DB=OUT/'cycling_v0_23.sqlite';PARENT=ROOT/'循环稳定性数据库_v0.22_原图循环与新增来源_20261026';PSHA='11925373f0fc101bc0ccc81caa266e49fd1d0077aeffe69cbec479ac1ef07798'
P2=['reported_2e','reported_2e_residue','reported_2e_approx','reported_2e_all_years'];JOBS=[('LP11_Tondolo_2E_C10000','v23:NTAC_2E_C10000',P2),('LP11_Tea_3E_C2000','candidate:TE045',['reported_3e_all_years'])]
def build():
    assert not DB.exists()and not(OUT/'merge_manifest.json').exists();assert sha(PARENT/'cycling_v0_22.sqlite')==PSHA
    OUT.mkdir(parents=True,exist_ok=True);contract=json.loads((PARENT/'data_contract.json').read_text('utf8'));litsha=sha(LDB)
    with load(PARENT,'_cycling_v022_build_v23').Database()as old,open_literature_database(LDB,litsha)as lit,closing(sqlite3.connect(DB))as c:
        contract.update(schema='cycling_two_test_source_families_v23',database_file=DB.name,parent_database_sha256=PSHA,literature_input_path=LDB.relative_to(ROOT).as_posix(),literature_input_sha256=litsha,source_family_rules=[r['record']for r in lit.source_relations()],grouping_policy='Canonical DOI plus explicit prior-work families; raw source_group retained; source_folds and matrix groups both use same family key',new_endpoint_records=1,promoted_existing_endpoints=1,research_training_authorized=False,model_fits=0,scope='Two ownGCD tests: new2026Tondolo2E and existing2021Tea3E all_years-only promotion; sourcefamily reuse with JECEprior; no newfits',year_scope_policy_v23='Legacy2023..2026 unchanged;2021Tea only explicit all_years3E;2026Tondolo ordinary2E/residue/approx/all_years2E',stage_semantics_v23='Tondolo700C2h is one joint pyrolysis, no separate activation time filled; Tea200C12h HTC separate from600C1h airactivation')
        extras=['joint_carbonization_activation_temperature_C_v23','joint_carbonization_activation_duration_h_v23','hydrothermal_carbonization_temperature_C_v23','hydrothermal_carbonization_duration_h_v23']
        for k in['model_material_features','extra_material_feature_whitelist']:contract[k]=list(dict.fromkeys(contract[k]+extras))
        write(OUT/'data_contract.json',contract)
        c.executescript('''create table reviewed_endpoints_v23(endpoint_id text primary key,row_json text,review_json text,is_new integer check(is_new in(0,1)));create table profile_membership_v23(endpoint_id text references reviewed_endpoints_v23,profile text,primary key(endpoint_id,profile));create table evidence_v23(evidence_id text primary key,endpoint_id text references reviewed_endpoints_v23,field_name text,value_json text,path text,sha256 text,locator text,selected integer check(selected in(0,1)),note text);create table changes_v23(change_id integer primary key,endpoint_id text references reviewed_endpoints_v23,field_name text,operation text,before_json text,after_json text,evidence_json text);create table material_fields_v23(material_key text,field_name text,value_json text,unit text,evidence_json text,primary key(material_key,field_name));create table literature_links_v23(candidate_id text primary key,endpoint_id text references reviewed_endpoints_v23,literature_database_sha256 text,status text);''');c.execute('pragma foreign_keys=on')
        oldrows={r['endpoint_id']:r for r in old.fetch('all_review').rows};candidates={r['candidate_id']:r for r in lit.tests()};materials={r['material_key']:r for r in lit.materials()};protected={}
        for cid,key,profiles in JOBS:
            candidate=candidates[cid];raw=candidate['record'];mat=materials[candidate['material_key']];doi=mat['doi'];sample=mat['sample_name'];before=oldrows.get(key);isnew=before is None
            assert bool(raw['legacy_endpoint_id'])!=isnew;assert key not in{r['endpoint_id']for r in old.reviewed_pending_batch()}
            source=ROOT/raw['evidence_source_path'];years={int(y.text)for y in E.parse(source).findall('.//article-meta/pub-date/year')};assert len(years)==1;year=years.pop();assert year==(2026 if doi==TAC else 2021)
            row=json.loads(json.dumps(before))if before else{f:None for f in set(contract['model_material_features']+contract['extra_material_feature_whitelist'])}
            if before:
                for f in['retention_pct','cycle_count','reported_current_A_g','cycle_voltage_lower_V','cycle_voltage_upper_V','system','electrolyte']:assert row[f]==raw[f]
            else:row.update(endpoint_id=key,doi=doi,source_group='doi:'+doi,identity_key='doi:'+doi,sample_name=sample,source_year=year,material_id='v23_material:'+candidate['material_key'],material_key_v11='v23m:'+candidate['material_key'],test_id='v23_test:'+key,curve_group='doi:'+doi+'#Fig8d',baseline_cycle=None,current_mass_basis=None,canonical_current_A_g=None,scope_flags='[]')
            fields=['system','method','retention_pct','cycle_count','reported_current_A_g','cycle_voltage_lower_V','cycle_voltage_upper_V','electrolyte','concentration_mol_L','reference_electrode','baseline_reference']
            for f in fields:row[f]=raw[f]
            row.update(retention_relation='eq',metric_kind='capacitance_retention',eligible=1,admission_status='approved_for_reported_protocol',admission_profiles_v23=profiles,workflow_status='approved_v023_reported_protocol',promoted_existing_endpoint_v23=not isnew,literature_candidate_id_v23=cid,literature_material_key=candidate['material_key'],source_year=year)
            if doi==BTC:row['reference_electrode']=before['reference_electrode'] # Preserve established NaCl-saturated identity spelling.
            if doi==TAC:row.update(joint_carbonization_activation_temperature_C_v23=700,joint_carbonization_activation_duration_h_v23=2,carbonization_temperature_C=700,carbonization_duration_h=2,activation_temperature_C=None,activation_duration_h=None,joint_process_not_two_heating_operations_v23=True,XPS_percentage_basis='atomic_explicit')
            else:row.update(hydrothermal_carbonization_temperature_C_v23=200,hydrothermal_carbonization_duration_h_v23=12,activation_temperature_C=600,activation_duration_h=1,activation_atmosphere_v23='air')
            mapping={'BET_m2_g':('BET_surface_area_m2_g','m2/g'),'total_pore_volume_cm3_g':('total_pore_volume_cm3_g','cm3/g'),'micropore_volume_cm3_g':('micropore_volume_cm3_g','cm3/g')}
            if doi==TAC:mapping.update(Raman_ID_IG=('Raman_ID_IG','ratio'),XPS_N_reported_pct=('XPS_N_at_pct','at%'),N_at_pct=('XPS_N_at_pct','at%'))
            proof=[]
            def ev(f,value,path,locator,selected=1,note=''):
                path=Path(path);digest=sha(path);rel=path.relative_to(ROOT).as_posix();protected[rel]=digest;proof.append(dict(evidence_id=key+'#'+f+'#'+str(len(proof)),endpoint_id=key,field_name=f,value_json=json.dumps(value,ensure_ascii=False),path=rel,sha256=digest,locator=locator,selected=selected,note=note))
            for f in fields+['retention_relation','source_year','eligible']:ev(f,row.get(f),source,raw['locator'],note='Actual own test and matched common GCD protocol; unknown current mass/exact baseline index retained')
            graph=LIT/'evidence/d6ra02137a-f8.jpg'if doi==TAC else ROOT/'三电极端点扩充_20261018/new_sources/PMC8585355/assets/materials-14-06592-g009.jpg'
            ev('retention_pct',row['retention_pct'],graph,'OwnFig8d/body45 right-axis94%,5Ag10000'if doi==TAC else'ActualFig9c printed98.8%, ownbody21 5Ag2000')
            for f in['cycle_voltage_lower_V','cycle_voltage_upper_V']:ev(f,row[f],graph if doi==TAC else source,'OwnFig8b+same-devicebody44 GCD0..1.7'if doi==TAC else'Ownbody10/18 GCD-.2...8 + matchedcyclebody21')
            for field,(name,unit)in mapping.items():
                facts=[f for f in lit.facts(doi=doi,sample=sample,field=name)if f['value']is not None and'conflict'not in f['review_status']];values={f['value']for f in facts};assert len(values)==1,(field,values);value=values.pop();row[field]=value
                for f in facts:ev(field,value,ROOT/f['source_path'],f['locator'],note='Specific own final material; source-family reuse and reported BET interval remain qualified')
                if isnew or before.get(field)!=value:c.execute('insert into material_fields_v23 values(?,?,?,?,?)',(row['material_key_v11'],field,json.dumps(value),unit,json.dumps([p for p in proof if p['field_name']==field],ensure_ascii=False)))
            for field in extras+['carbonization_temperature_C','carbonization_duration_h','activation_temperature_C','activation_duration_h']:
                if row.get(field)is None or not isnew and before.get(field)==row[field]:continue
                ev(field,row[field],source,'Ownmethods5/6 single700C2hArgonpyrolysis'if doi==TAC else'Ownmethods5/7 HTC200C12h thenair600C1hKOHchar1:3')
                c.execute('insert into material_fields_v23 values(?,?,?,?,?)',(row['material_key_v11'],field,json.dumps(row[field]),'degC'if'temperature'in field else'h',json.dumps([p for p in proof if p['field_name']==field],ensure_ascii=False)))
            caveats=['Author-reported current; physical mass denominator unknown, no formula conversion. Exact initial cycle index not invented.','OwnBET/characterization explicitly reused from JECE prior work; both DOIs form one validation family; dye protocol/fit issues remain unrelated response holds.'if doi==TAC else'2021 outside legacy2023..2026; approval only all_years3E. Original outside_year history retained; nativeCaCO3trace not erased.']
            review=dict(endpoint_id=key,disposition='approved_reported_protocol',approved_profiles=profiles,open_issues=[],caveats=caveats,reason='Own material/source year/actual cycle target,current,electrolyte,voltage and BET matched under current reported-protocol purpose',previous_holds=old.holds(key)if before else None,literature_candidate_id=cid,review_version='v0.23',model_fits=0)
            c.execute('insert into reviewed_endpoints_v23 values(?,?,?,?)',(key,json.dumps(row,ensure_ascii=False),json.dumps(review,ensure_ascii=False),int(isnew)));c.executemany('insert into profile_membership_v23 values(?,?)',[(key,p)for p in profiles]);c.executemany('insert into evidence_v23 values(:evidence_id,:endpoint_id,:field_name,:value_json,:path,:sha256,:locator,:selected,:note)',proof)
            for f in sorted(row):
                if isnew or before.get(f)!=row[f]:c.execute('insert into changes_v23(endpoint_id,field_name,operation,before_json,after_json,evidence_json)values(?,?,?,?,?,?)',(key,f,'insert_new_reviewed_endpoint'if isnew else'promote_existing_endpoint_for_separate_purpose',json.dumps(None if isnew else before.get(f),ensure_ascii=False),json.dumps(row[f],ensure_ascii=False),json.dumps([p for p in proof if p['field_name']==f],ensure_ascii=False)))
            c.execute('insert into literature_links_v23 values(?,?,?,?)',(cid,key,litsha,'admitted_reported_protocol_v023'))
        c.commit()
    write(OUT/'protected_inputs.json',[dict(path=p,sha256=h)for p,h in sorted(protected.items())]+[dict(path=LDB.relative_to(ROOT).as_posix(),sha256=litsha),dict(path=(PARENT/'cycling_v0_22.sqlite').relative_to(ROOT).as_posix(),sha256=PSHA)])
    print('Built v0.23 draft: one new endpoint + one existing ID promoted; no fit')

def verify(prepare=False):
    checks=[]
    def ck(name,ok):
        if not ok:raise AssertionError(name)
        checks.append(name)
    for p in json.loads((OUT/'protected_inputs.json').read_text('utf8')):ck('protected_'+p['path'],sha(ROOT/p['path'])==p['sha256'])
    for p in json.loads((PARENT/'merge_manifest.json').read_text('utf8'))['outputs']:ck('parent_payload_'+p['path'],sha(ROOT/p['path'])==p['sha256'])
    for p in json.loads((LIT/'merge_manifest.json').read_text('utf8'))['outputs']:ck('literature_payload_'+p['path'],sha(ROOT/p['path'])==p['sha256'])
    digest=sha(DB)
    with closing(ro(DB))as c:
        ck('integrity',c.execute('pragma integrity_check').fetchone()[0]=='ok');ck('foreign_keys',not c.execute('pragma foreign_key_check').fetchall());ck('one_new_one_promotion',list(c.execute('select is_new,count(*)from reviewed_endpoints_v23 group by is_new'))==[(0,1),(1,1)])
    child=load(OUT,'_v023_verify');parent=load(PARENT,'_v022_pinned_v23')
    derived={'source_family_group_v23','source_weight','all_years_admission_basis_v23'};strip=lambda r:{k:v for k,v in r.items()if k not in derived}
    with parent.Database()as old,child.Database()as new,open_literature_database(LDB,sha(LDB))as lit:
        oldrows={r['endpoint_id']:r for r in old.fetch('all_review').rows};rows={r['endpoint_id']:r for r in new.fetch('all_review').rows}
        ck('282_observations',len(rows)==282);ck('182_original_source_groups',len({r['source_group']for r in rows.values()})==182);ck('exact_new_ID',set(rows)-set(oldrows)=={'v23:NTAC_2E_C10000'})
        for key,row in oldrows.items():
            if key=='candidate:TE045':
                for field in['source_group','sample_name','system','method','retention_pct','retention_relation','cycle_count','reported_current_A_g','cycle_voltage_lower_V','cycle_voltage_upper_V','electrolyte','reference_electrode','source_year','BET_m2_g','total_pore_volume_cm3_g']:ck('Tea_original_core_'+field,rows[key][field]==row[field])
            else:ck('old_row_'+key,strip(rows[key])==strip(row))
        expected={'reported_3e':(43,31),'reported_3e_residue_sensitivity':(44,32),'reported_3e_sensitivity':(52,38),'reported_2e':(30,24),'reported_2e_residue':(32,25),'reported_2e_approx':(34,27),'reported_3e_all_years':(45,33),'reported_2e_all_years':(32,26)};counts={};matrices={}
        for profile,want in expected.items():
            ds=new.fetch(profile);m=ds.feature_matrix();matrices[profile]=m;counts[profile]=dict(rows=len(ds.rows),source_families=len(set(m['groups'])))
            ck('count_'+profile,(counts[profile]['rows'],counts[profile]['source_families'])==want)
            before={r['endpoint_id']for r in old.fetch(profile).rows};added={key for cid,key,profiles in JOBS if profile in profiles};ck('exact_members_'+profile,{r['endpoint_id']for r in ds.rows}==before|added)
            for group in set(m['groups']):ck('family_weight_'+profile+group,abs(sum(w for g,w in zip(m['groups'],m['sample_weight'])if g==group)-1)<1e-12)
            for i,fold in enumerate(ds.source_folds(len(set(m['groups'])))):ck('fold_'+profile+str(i),not{m['groups'][j]for j in fold['train']}&{m['groups'][j]for j in fold['test']})
            mm=new.method_specific_material_matrix(profile);ck('no_fits_imputation_'+profile,mm['estimators_fitted']==0 and not mm['imputed']and all(mask==(v is None)for values,masks in zip(mm['X'],mm['missing_mask'])for v,mask in zip(values,masks)))
            ck('no_label_identity_as_feature_'+profile,not{'retention_pct','doi','source_group','source_family_group_v23','endpoint_id','CE','capacitance_F_g'}&set(mm['feature_names']))
        tea=new.by_endpoint('candidate:TE045');tac=new.by_endpoint('v23:NTAC_2E_C10000')
        ck('Tea_only_all_years',tea['admission_profiles_v23']==['reported_3e_all_years']and tea['source_year']==2021)
        ck('Tea_unchanged_old_outside_year_history',tea['review_disposition_v12']=='outside_year'and new.holds(tea['endpoint_id'])['previous_holds']==old.holds(tea['endpoint_id']))
        ck('unknown_current_mass_allowed',tac['canonical_current_A_g']is None and tac['current_mass_basis']is None and tac['baseline_cycle']is None)
        ck('TAC_exact_core',(tac['retention_pct'],tac['cycle_count'],tac['reported_current_A_g'],tac['cycle_voltage_lower_V'],tac['cycle_voltage_upper_V'],tac['BET_m2_g'])==(94,10000,5,0,1.7,3504.5))
        ck('TAC_no_separate_activation_imputed',tac['joint_carbonization_activation_temperature_C_v23']==700 and tac['activation_temperature_C']is None)
        ck('Tea_HTC_not_pyrolysis',tea.get('carbonization_temperature_C')is None and tea['hydrothermal_carbonization_temperature_C_v23']==200 and tea['activation_temperature_C']==600)
        ck('family_rule_matches_literature',new.source_family_rules()==[r['record']for r in lit.source_relations()]and child.family_key('doi:'+TAC)==child.family_key(PRIOR)==lit.isolation_group(TAC))
        # Counterexample is an in-memory structural check, not scientific data or a fit.
        first=dict(tac);second=dict(tac,endpoint_id='synthetic_prior_work_copy_not_scientific_record',source_group='doi:'+PRIOR);unrelated=next(dict(r)for r in new.fetch('reported_2e').rows if r['source_group']!='doi:'+TAC)
        for r in[first,second,unrelated]:r.pop('source_family_group_v23',None)
        counter=child.Dataset('reported_2e',[first,second,unrelated],list(new.fetch('reported_2e').features));cm=counter.feature_matrix()
        ck('prior_work_alias_weighted_once',cm['groups'][0]==cm['groups'][1]and cm['sample_weight'][:2]==[.5,.5]);ck('prior_work_no_fold_split',all((0 in f['test'])==(1 in f['test'])for f in counter.source_folds(2)))
        invalid_cases=[('reported_current_A_g',None),('BET_m2_g',0),('method','CV'),('retention_pct',float('nan')),('cycle_voltage_upper_V',-1),('baseline_reference',None),('source_family_group_v23','fake_family')]
        for field,value in invalid_cases:
            r=dict(tac);r[field]=value
            try:child.Dataset('reported_2e',[r],counter.features).feature_matrix()
            except child.DataNotReady:ck('reject_'+field,True)
            else:raise AssertionError('Invalid row admitted:'+field)
        try:child.Dataset('reported_3e',[tea],list(new.fetch('reported_3e').features)).feature_matrix()
        except child.DataNotReady:ck('legacy_year_gate_not_weakened',True)
        else:raise AssertionError('Old cohort date guard lost')
        ck('positive_growth_not_clipped',new.by_endpoint('v22:NFACc_2E_C10000')['retention_pct']==101.7)
        ck('fixed38_original_exact',new.reviewed_pending_batch()==old.reviewed_pending_batch()and len(new.reviewed_pending_batch())==38)
        ck('15_feature_freezes_preserved',sum(x.get('review_version')=='v0.21'for x in new.field_changes(include_history=True))==15)
        for r in new.fetch('reported_3e').rows:
            if r['source_group']=='doi:10.3390/molecules31132329':ck('freeze_mask_'+r['endpoint_id'],all(r.get(f)is None for f in['N_at_pct','XPS_N_reported_pct','Raman_ID_IG']))
        ck('two_new_links',len(new.literature_links())==len(old.literature_links())+2)
        for cid,key,profiles in JOBS:
            link=next(r for r in new.literature_links()if r['candidate_id']==cid);ck('link_'+cid,link['endpoint_id']==key and link['literature_database_sha256']==sha(LDB));ck('selected_own_target_proof_'+key,any(e.get('currently_selected')and e.get('value')==new.by_endpoint(key)['retention_pct']for e in new.evidence(key,'retention_pct')))
        mm=new.method_specific_material_matrix('reported_2e');i=mm['endpoint_ids'].index(tac['endpoint_id']);ck('TAC_explicit_atomic_only',mm['X'][i][mm['feature_names'].index('XPS_N_atomic_pct_v15')]==2.75 and mm['X'][i][mm['feature_names'].index('XPS_N_weight_pct_v15')]is None)
    ck('readonly_database_hash',sha(DB)==digest)
    report=dict(status='passed',database_sha256=digest,check_count=len(checks),checks=sorted(checks),observations=282,raw_source_groups=182,profiles=counts,new_endpoints=1,promoted_existing_endpoints=1,new_purpose_admissions=2,source_family_rules=1,original_fixed_resolved=1,original_fixed_pending=38,model_fits=0,full_goal_complete=False)
    if prepare:
        assert not(OUT/'merge_manifest.json').exists();write(OUT/'verification.json',report);write(OUT/'summary.json',{k:v for k,v in report.items()if k!='checks'});write(OUT/'model_inputs_preflight.json',matrices)
    else:
        assert json.loads((OUT/'verification.json').read_text('utf8'))==report;assert json.loads((OUT/'model_inputs_preflight.json').read_text('utf8'))==matrices
        if(OUT/'merge_manifest.json').exists():
            for p in json.loads((OUT/'merge_manifest.json').read_text('utf8'))['outputs']:assert sha(ROOT/p['path'])==p['sha256']
    print(json.dumps({k:v for k,v in report.items()if k!='checks'},ensure_ascii=False))

def finalize_draft_contract():
    assert not(OUT/'merge_manifest.json').exists();p=OUT/'data_contract.json';contract=json.loads(p.read_text('utf8'));contract.update(scope='Two ownGCD tests: new2026Tondolo2E and existing2021Tea3E all_years-only promotion; sourcefamily reuse with JECEprior; no newfits',year_scope_policy_v23='Legacy2023..2026 unchanged;2021Tea only explicit all_years3E;2026Tondolo ordinary2E/residue/approx/all_years2E',stage_semantics_v23='Tondolo700C2h is one joint pyrolysis, no separate activation time filled; Tea200C12h HTC separate from600C1h airactivation');write(p,contract)

def seal():
    assert not(OUT/'merge_manifest.json').exists()
    from verify_cycle_family_v023 import run
    run(False)
    paths=[p for p in OUT.rglob('*')if p.is_file()]+[ROOT/'tools/release_cycle_family_v023.py',ROOT/'tools/verify_cycle_family_v023.py']
    write(OUT/'merge_manifest.json',dict(version='cycling_v0.23',parent_sha256=PSHA,outputs=[dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p),bytes=p.stat().st_size)for p in sorted(paths)],model_fits=0,scientific_goal_complete=False))
    write(ROOT/'data/current_database.json',dict(version='cycling_v0.23',version_directory=OUT.relative_to(ROOT).as_posix(),database_file=DB.name,sha256=sha(DB),parent_database_file=(PARENT/'cycling_v0_22.sqlite').relative_to(ROOT).as_posix(),default_profile='reported_3e',stage='two_test_admissions_and_source_family_groups',ready_for_training_inputs=True,research_training_authorized=False,all_records_admitted=False))
if __name__=='__main__':
    if len(sys.argv)!=2 or sys.argv[1]not in['build','prepare','verify','finalize_draft_contract','seal']:raise SystemExit('One-use build/seal; prepare unsealed; verify read-only')
    if sys.argv[1]=='prepare':verify(True)
    else:globals()[sys.argv[1]]()
