"""Admit five source-qualified cycling tests, with existing IDs promoted and original reports retained."""
from pathlib import Path
from contextlib import closing
import collections,hashlib,json,sqlite3,sys,xml.etree.ElementTree as E
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tools'))
from extract_four_sources_v10 import OUT as LIT,DB as LDB,COT,QSC,ANN,SOURCES,sha,ro,write
from release_feature_freezes_v021 import load
from data.literature_v10 import open_literature_database
OUT=ROOT/'循环稳定性数据库_v0.22_原图循环与新增来源_20261026';DB=OUT/'cycling_v0_22.sqlite';PARENT=ROOT/'循环稳定性数据库_v0.21_图表冲突特征冻结_20261026';PSHA='240547aea23959fc2d606593224b394a78404e697bf9e485b6c22a969e4f015a'
P3=['reported_3e','reported_3e_residue_sensitivity','reported_3e_sensitivity'];P2=['reported_2e','reported_2e_residue','reported_2e_approx']
JOBS=[('LP10_Cotton_3E_C5000','v22:COT_CDAP800350_3E_C5000',['reported_3e_all_years']),('LP10_Cotton_2E_C5000','v22:COT_CDAP800350_2E_C5000',['reported_2e_all_years']),('LP10_Quinoa_2E_KOH_C10000','candidate:V05:012',P2+['reported_2e_all_years']),('LP10_Quinoa_2E_Na2SO4_C10000','candidate:V05:013',P2+['reported_2e_all_years']),('LP10_NFAC_2E_C10000','v22:NFACc_2E_C10000',['reported_2e_all_years'])]

def extended_contract(contract):
    for profile,original in[('reported_3e_all_years','reported_3e'),('reported_2e_all_years','reported_2e')]:contract['profiles'][profile]=dict(contract['profiles'][original],year_scope='Allpublicationyearspositivelyverifiedinexplicitreview; noautomaticunreviewedoldrecordadmission',legacy_base=original)
    contract['year_scope_policy_v22']='Existing2023..2026profilesretainoriginalDatasetchecks. Twoexplicitall_yearsviewsincludevalidatedlegacycohortplusindividuallyreviewed2018Cotton/2019NFAC; differentcohorts, nofit.'
    return contract
def build():
    if DB.exists()or(OUT/'merge_manifest.json').exists():raise FileExistsError('Do notoverwriteDB')
    OUT.mkdir(parents=True,exist_ok=True);assert sha(PARENT/'cycling_v0_21.sqlite')==PSHA;litsha=sha(LDB);contract=json.loads((PARENT/'data_contract.json').read_text('utf8'));contract.update(schema='cycling_five_test_admissions_v22',database_file=DB.name,parent_database_sha256=PSHA,literature_input_path=LDB.relative_to(ROOT).as_posix(),literature_input_sha256=litsha,research_training_authorized=False,model_fits=0,new_endpoint_records=3,promoted_existing_endpoints=2,scope='FiveGCDtests: Cotton3E/2E,Quinoa2salts,NFAC2E; old15featurefreezes preserved; unknowncurrentmassretained.')
    write(OUT/'data_contract.json',extended_contract(contract));parent=load(PARENT,'_v021_admission_build')
    with parent.Database()as old,open_literature_database(LDB,litsha)as lit,closing(sqlite3.connect(DB))as c:
        c.executescript('''create table reviewed_endpoints_v22(endpoint_id text primary key,row_json text,review_json text,is_new integer check(is_new in(0,1)));
        create table profile_membership_v22(endpoint_id text references reviewed_endpoints_v22,profile text,eligible integer check(eligible=1),primary key(endpoint_id,profile));
        create table evidence_v22(evidence_id text primary key,endpoint_id text references reviewed_endpoints_v22,field_name text,value_json text,path text,sha256 text,locator text,excerpt text,selected integer check(selected in(0,1)),decision_note text);
        create table changes_v22(change_id integer primary key,endpoint_id text references reviewed_endpoints_v22,field_name text,operation text,before_json text,after_json text,evidence_json text);
        create table material_fields_v22(material_key text,field_name text,value_json text,unit text,evidence_json text,primary key(material_key,field_name));
        create table literature_links_v22(candidate_id text primary key,endpoint_id text references reviewed_endpoints_v22,literature_database_sha256 text,status text);''');c.execute('pragma foreign_keys=on')
        previous={r['endpoint_id']:r for r in old.fetch('all_review').rows};candidates={r['candidate_id']:r for r in lit.tests()};materials={r['material_key']:r for r in lit.materials()};protected={};added_properties=set()
        for candidate_id,key,profiles in JOBS:
            candidate=candidates[candidate_id];r=candidate['record'];material=materials[candidate['material_key']];doi=material['doi'];sample=material['sample_name'];isnew=key not in previous
            assert isnew==(not r.get('legacy_endpoint_id'));assert key not in{r['endpoint_id']for r in old.reviewed_pending_batch()}
            before=previous.get(key);row=json.loads(json.dumps(before))if before else{f:None for f in set(contract['extra_material_feature_whitelist']+contract['model_material_features'])}
            if before:
                assert before['retention_pct']==r['retention_pct']and before['cycle_count']==r['cycle_count']and before['reported_current_A_g']==r['reported_current_A_g'];assert before['cycle_voltage_lower_V']is None and before['cycle_voltage_upper_V']is None
            else:
                year={int(x.text)for x in E.parse(ROOT/r['evidence_source_path']).findall('.//article-meta/pub-date/year')};assert len(year)==1
                row.update(endpoint_id=key,source_group='doi:'+doi,identity_key='doi:'+doi,doi=doi,sample_name=sample,source_year=year.pop(),material_id='v22_material:'+candidate['material_key'],material_key_v11='v22m:'+candidate['material_key'],material_key_v22='v22m:'+candidate['material_key'],test_id='v22_test:'+key,curve_group='doi:'+doi+'#'+('Fig8c'if r['system']=='3E'else'Fig11a'if doi==COT else'Fig8h'),source_weight=1,canonical_current_A_g=None,current_mass_basis=None,baseline_cycle=None,value_kind='reported_exact_own_figure_or_prose',scope_flags='[]',XPS_percentage_basis=None)
            fields=['system','method','cycle_count','retention_pct','reported_current_A_g','electrolyte','concentration_mol_L','reference_electrode','cycle_voltage_lower_V','cycle_voltage_upper_V','baseline_reference']
            row.update({f:r.get(f)for f in fields});row.update(retention_relation='eq',metric_kind='capacitance_retention',eligible=1,admission_status='approved_for_reported_protocol',admission_profiles_v22=profiles,workflow_status='approved_v022_reported_protocol',promoted_existing_endpoint_v22=not isnew,literature_candidate_id_v22=candidate_id,literature_material_key=candidate['material_key'])
            facts=lit.facts(doi=doi,sample=sample);props={}
            mapping={'BET_m2_g':'BET_surface_area_m2_g','total_pore_volume_cm3_g':'total_pore_volume_cm3_g','micropore_volume_cm3_g':'micropore_volume_cm3_g','mesopore_volume_cm3_g':'mesopore_volume_cm3_g','Raman_ID_IG':'Raman_ID_IG'}
            if doi==COT:mapping.update(XPS_N_reported_pct='XPS_N_wt_pct',XPS_O_reported_pct='XPS_O_wt_pct')
            if isnew or row.get('BET_m2_g') is None:
                for field,sourcefield in (mapping.items() if isnew else [('BET_m2_g','BET_surface_area_m2_g')]):
                    good=[f for f in facts if f['field_name']==sourcefield and f['value']is not None and'conflict'not in f['review_status']];values={f['value']for f in good}
                    if len(values)==1:row[field]=next(iter(values));props[field]=(row[field],good)
            if isnew:
                if doi==COT:row['XPS_percentage_basis']='weight_explicit';row['N_at_pct']=None;row['O_at_pct']=None
                if doi==ANN:row['N_at_pct']=None;row['XPS_N_reported_pct']=None;row['EDX_N_reported_pct']=None;row['N_detection_state_v22']='authorEDSnotdetected_limitunknown_notzero'
                stages=[s for rec in lit.synthesis(doi=doi,sample=sample)for s in rec['stages']];carbon=next((s for s in stages if s['stage']=='carbonization'),{});activation=next((s for s in stages if s['stage']=='chemical_activation'),{});oxid=next((s for s in stages if s['stage']=='air_oxidation_after_carbonization'),{})
                row.update(carbonization_temperature_C=carbon.get('temperature_C'),carbonization_duration_h=carbon.get('duration_h'),activation_temperature_C=activation.get('temperature_C'),activation_duration_h=activation.get('duration_h'),post_air_oxidation_temperature_C_v22=oxid.get('temperature_C'),post_air_oxidation_duration_h_v22=oxid.get('duration_h'))
            proof=[]
            def ev(field,value,path,locator,selected=1,note=''):
                path=Path(path);digest=sha(path);protected[path.relative_to(ROOT).as_posix()]=digest
                item=dict(evidence_id=key+'#'+field+'#'+str(len(proof)),endpoint_id=key,field_name=field,value_json=json.dumps(value,ensure_ascii=False),path=path.relative_to(ROOT).as_posix(),sha256=digest,locator=locator,excerpt=locator,selected=selected,decision_note=note);proof.append(item)
            sourcepath=ROOT/r['evidence_source_path']
            for f in fields+['retention_relation']:ev(f,row.get(f),sourcepath,r['locator'],note='Ownreportedprotocol; currentmassandexactbaselineindexunknownretained')
            if doi==COT:
                graph=LIT/'evidence'/('c7ra11475c-f8.jpg'if r['system']=='3E'else'c7ra11475c-f11.jpg');ev('retention_pct',row['retention_pct'],graph,'ActualownFig8cprinted92%'if r['system']=='3E'else'ActualownFig11aprinted86%',note='Specificactualcycleevidencewithcorroboratingownbody; noauthorerratum')
                voltage=LIT/'evidence'/('c7ra11475c-f8.jpg'if r['system']=='3E'else'c7ra11475c-f10.jpg')
                for f in['cycle_voltage_lower_V','cycle_voltage_upper_V']:ev(f,row[f],voltage,'OwnsameconfigurationGCDpanelb+samecellcycleprotocol; notCVsubstitution')
                if r['system']=='2E_symmetric':
                    for value,loc in[(87,'abstract'),(89,'conclusionp45')]:ev('retention_pct',value,sourcepath,loc,0,'Dissentpreserved; ownactualFig11a/body44select86')
            elif doi==QSC:
                for f in['cycle_voltage_lower_V','cycle_voltage_upper_V','retention_pct']:ev(f,row[f],BASE_FIG:=ROOT/'同体系文献补充_第二批_20261017/定向扩搜40至60篇_20261017/sources/OA004/figures/ao3c04692_0011.jpg','ActualownFig11aKOH/cNa2SO4cycleinsets0..1.5/0..2.0; body37andcaption5Ag')
                if r['electrolyte']=='Na2SO4':ev('cycle_voltage_lower_V',1,sourcepath,'ComparisonTable3ownrow1..2.0',0,'PreserveTable3dissent; specificactualcycleinsetandbody34show0..2.0')
            else:
                for f in['retention_pct','cycle_voltage_lower_V','cycle_voltage_upper_V']:ev(f,row[f],LIT/'evidence/c9ra01255a-f8.jpg','ActualFig8hbefore/afterGCDinsets0..0.8+body33retention101.7,1Ag',note='Roundedcycle280/285separatefromfreshrate255; >100notclipped')
            for field,(value,evidence)in props.items():
                for f in evidence:ev(field,value,ROOT/f['source_path'],f['locator'],note='Ownpretestmaterial; XPSwt/atandporeunitskeptseparate')
                propkey=(row['material_key_v11'],field)
                if propkey not in added_properties:
                    c.execute('insert into material_fields_v22 values(?,?,?,?,?)',(row['material_key_v11'],field,json.dumps(value),evidence[0]['unit'],json.dumps([{k:p[k]for k in['path','sha256','locator','value_json']}for p in proof if p['field_name']==field],ensure_ascii=False)));added_properties.add(propkey)
            review=dict(endpoint_id=key,disposition='approved_reported_protocol',approved_profiles=profiles,open_issues=[],reason='Ownmaterial/configuration/cyclelabel/current/electrolyte/actualcycleorcommonGCDwindowboundunderexistingreportedprotocolpolicy',caveats=['Currentmassbasisunknown,noformula-basedphysicalconversion; exactnormalizationcycleindexunknown.','Cotton2E86selectedspecificactualfigure+body,abstract87/conclusion89retained.'if doi==COT and r['system']!='3E'else'Nativecomparisons/format/unitscaveatsretaininliteraturev10,notnewscientificmeasurements.'],previous_holds=old.holds(key)if not isnew else None,literature_candidate_id=candidate_id,review_version='v0.22',model_fits=0)
            c.execute('insert into reviewed_endpoints_v22 values(?,?,?,?)',(key,json.dumps(row,ensure_ascii=False),json.dumps(review,ensure_ascii=False),int(isnew)));c.executemany('insert into profile_membership_v22 values(?,?,1)',[(key,p)for p in profiles])
            c.executemany('insert into evidence_v22 values(:evidence_id,:endpoint_id,:field_name,:value_json,:path,:sha256,:locator,:excerpt,:selected,:decision_note)',proof)
            changed={f for f in row if isnew or row[f]!=before.get(f)}
            for f in sorted(changed):c.execute('insert into changes_v22(endpoint_id,field_name,operation,before_json,after_json,evidence_json)values(?,?,?,?,?,?)',(key,f,'insert_new_endpoint_field'if isnew else'promote_existing_after_own_cycle_review',json.dumps(None if isnew else before.get(f),ensure_ascii=False),json.dumps(row[f],ensure_ascii=False),json.dumps([p for p in proof if p['field_name']==f],ensure_ascii=False)))
            c.execute('insert into literature_links_v22 values(?,?,?,?)',(candidate_id,key,litsha,'admitted_reported_protocol_v022'))
        c.commit();write(OUT/'protected_inputs.json',[dict(path=p,sha256=h)for p,h in sorted(protected.items())]+[dict(path=(PARENT/'cycling_v0_21.sqlite').relative_to(ROOT).as_posix(),sha256=PSHA),dict(path=LDB.relative_to(ROOT).as_posix(),sha256=litsha)])
    print('Builtfiveadmissions:3newrecords,2existingIDs promoted;nofit')

def repair_draft_scope():
    assert not(OUT/'merge_manifest.json').exists()
    p=OUT/'data_contract.json';write(p,extended_contract(json.loads(p.read_text('utf8'))))
    with closing(sqlite3.connect(DB))as c:
        for candidate,key,profiles in JOBS:
            stored,review=c.execute('select row_json,review_json from reviewed_endpoints_v22 where endpoint_id=?',(key,)).fetchone();row=json.loads(stored);r=json.loads(review);row['admission_profiles_v22']=profiles;r['approved_profiles']=profiles
            c.execute('update reviewed_endpoints_v22 set row_json=?,review_json=?where endpoint_id=?',(json.dumps(row,ensure_ascii=False),json.dumps(r,ensure_ascii=False),key));c.execute('delete from profile_membership_v22 where endpoint_id=?',(key,));c.executemany('insert into profile_membership_v22 values(?,?,1)',[(key,p)for p in profiles]);c.execute("update changes_v22 set after_json=?where endpoint_id=?and field_name='admission_profiles_v22'",(json.dumps(profiles),key))
        c.commit()

def repair_own_bet():
    """One-time draft repair: bind the already transcribed own QSC-3 BET cell."""
    assert not(OUT/'merge_manifest.json').exists()
    with closing(sqlite3.connect(DB))as c,open_literature_database(LDB,sha(LDB))as lit:
        for candidate,key,profiles in JOBS:
            if not candidate.startswith('LP10_Quinoa'):continue
            row=json.loads(c.execute('select row_json from reviewed_endpoints_v22 where endpoint_id=?',(key,)).fetchone()[0]);assert row['BET_m2_g'] is None
            facts=[f for f in lit.facts(doi=QSC,sample=row['sample_name'])if f['field_name']=='BET_surface_area_m2_g'and f['value']is not None and'conflict'not in f['review_status']]
            assert len(facts)==1 and facts[0]['value']==1802;f=facts[0];row['BET_m2_g']=f['value']
            proof=dict(evidence_id=key+'#own_BET_v22',endpoint_id=key,field_name='BET_m2_g',value_json=json.dumps(f['value']),path=f['source_path'],sha256=f['source_sha256'],locator=f['locator']+'; own QSC-3 row BET column',excerpt=f['raw_value'],selected=1,decision_note='Missing old cache cell filled from own matching final QSC-3 Table1; old null preserved in change history')
            c.execute('insert into evidence_v22 values(:evidence_id,:endpoint_id,:field_name,:value_json,:path,:sha256,:locator,:excerpt,:selected,:decision_note)',proof)
            c.execute('insert into changes_v22(endpoint_id,field_name,operation,before_json,after_json,evidence_json)values(?,?,?,?,?,?)',(key,'BET_m2_g','bind_own_matching_material_cell','null',json.dumps(f['value']),json.dumps([proof],ensure_ascii=False)))
            c.execute('insert or ignore into material_fields_v22 values(?,?,?,?,?)',(row['material_key_v11'],'BET_m2_g',json.dumps(f['value']),f['unit'],json.dumps([proof],ensure_ascii=False)))
            c.execute('update reviewed_endpoints_v22 set row_json=?where endpoint_id=?',(json.dumps(row,ensure_ascii=False),key))
        c.commit()

def verify(prepare=False):
    checks=[]
    def ck(name,ok):
        if not ok:raise AssertionError(name)
        checks.append(name)
    for p in json.loads((OUT/'protected_inputs.json').read_text('utf8')):ck('protected_'+p['path'],sha(ROOT/p['path'])==p['sha256'])
    for p in json.loads((PARENT/'merge_manifest.json').read_text('utf8'))['outputs']:ck('parent_payload_'+p['path'],sha(ROOT/p['path'])==p['sha256'])
    with closing(ro(DB))as c:ck('integrity',c.execute('pragma integrity_check').fetchone()[0]=='ok');ck('FK',not c.execute('pragma foreign_key_check').fetchall());ck('new3_promoted2',list(c.execute('select is_new,count(*)from reviewed_endpoints_v22 group by is_new'))==[(0,2),(1,3)])
    child=load(OUT,'_v022_verify');parent=load(PARENT,'_v021_verify_parent_v22');counts={}
    with parent.Database()as old,child.Database()as new,open_literature_database(LDB,sha(LDB))as lit:
        oldall={r['endpoint_id']:r for r in old.fetch('all_review').rows};newall={r['endpoint_id']:r for r in new.fetch('all_review').rows};jobkeys={k for a,k,p in JOBS}
        ck('281observations',len(newall)==281);ck('181sourcegroups',len({r['source_group']for r in newall.values()})==181);ck('exact3newIDs',set(newall)-set(oldall)=={k for a,k,p in JOBS if k not in oldall})
        for k,row in oldall.items():
            if k not in jobkeys:ck('oldrow_preserved_'+k,newall[k]==row)
            else:
                for f in['retention_pct','retention_relation','cycle_count','reported_current_A_g','electrolyte','concentration_mol_L','system','method','source_group','sample_name']:ck('promoted_core_preserved_'+k+f,newall[k][f]==row[f])
                ck('promoted_BET_bound_'+k,row['BET_m2_g']is None and newall[k]['BET_m2_g']==1802 and any(e.get('value')==1802 and e.get('currently_selected') for e in new.evidence(k,'BET_m2_g')))
        expected={'reported_3e':(43,31),'reported_3e_residue_sensitivity':(44,32),'reported_3e_sensitivity':(52,38),'reported_2e':(29,23),'reported_2e_residue':(31,24),'reported_2e_approx':(33,26),'reported_3e_all_years':(44,32),'reported_2e_all_years':(31,25)}
        for profile,want in expected.items():
            ds=new.fetch(profile);m=ds.feature_matrix();counts[profile]=dict(rows=len(ds.rows),sources=len(set(m['groups'])));ck('counts_'+profile,(counts[profile]['rows'],counts[profile]['sources'])==want)
            base_profile={'reported_3e_all_years':'reported_3e','reported_2e_all_years':'reported_2e'}.get(profile,profile);before={r['endpoint_id']for r in old.fetch(base_profile).rows};added={k for a,k,ps in JOBS if profile in ps};ck('exact_membership_'+profile,{r['endpoint_id']for r in ds.rows}==before|added)
            for g in set(m['groups']):ck('weight_'+profile+g,abs(sum(w for group,w in zip(m['groups'],m['sample_weight'])if group==g)-1)<1e-12)
            for fold in ds.source_folds(len(set(m['groups']))):ck('isolation_'+profile+str(fold['test'][0]),not{m['groups'][i]for i in fold['train']}&{m['groups'][i]for i in fold['test']})
            mat=new.method_specific_material_matrix(profile);ck('no_imputation_'+profile,not mat['imputed']and mat['estimators_fitted']==0 and all(mask==(value is None)for row,flags in zip(mat['X'],mat['missing_mask'])for value,mask in zip(row,flags)))
        ck('oldfixed38_unchanged',new.reviewed_pending_batch()==old.reviewed_pending_batch()and len(new.reviewed_pending_batch())==38)
        ck('15freeze_chain_preserved',sum(r.get('review_version')=='v0.21'for r in new.field_changes(include_history=True))==15)
        for row in new.fetch('reported_3e').rows:
            if row['source_group']=='doi:10.3390/molecules31132329':ck('oldN_Raman_stillnull_'+row['endpoint_id'],row['N_at_pct']is None and row['XPS_N_reported_pct']is None and row['Raman_ID_IG']is None)
        nf=new.by_endpoint('v22:NFACc_2E_C10000');ck('real101p7_preserved',nf['retention_pct']==101.7);ck('noNzero',nf['N_at_pct']is None and nf['EDX_N_reported_pct']is None)
        cot=new.by_endpoint('v22:COT_CDAP800350_2E_C5000');ck('86owncycle_selected',cot['retention_pct']==86 and{e['value']for e in new.evidence(cot['endpoint_id'],'retention_pct')if not e['currently_selected']}=={87,89})
        projected=new.method_specific_material_matrix('reported_2e_all_years');i=projected['endpoint_ids'].index(cot['endpoint_id']);ck('Cotton_weight_channel',projected['X'][i][projected['feature_names'].index('XPS_N_weight_pct_v15')]==5.8 and projected['X'][i][projected['feature_names'].index('XPS_N_atomic_pct_v15')]is None)
        ck('legacy_year_rule_preserved',all(2023<=r['source_year']<=2026 for p in['reported_3e','reported_2e']for r in new.fetch(p).rows))
        for p,year,n in [('reported_3e_all_years',2018,1),('reported_2e_all_years',2018,1),('reported_2e_all_years',2019,1)]:
            filtered=new.fetch(p,year_min=year,year_max=year);ck('filter_'+p+str(year),len(filtered.feature_matrix()['y'])==n)
        valid=new.fetch('reported_2e_all_years');original=valid.rows[-1]
        for field,value in [('reported_current_A_g',None),('BET_m2_g',0),('method','CV'),('system','3E'),('retention_pct',float('nan')),('retention_pct',-1),('source_year',None),('all_years_admission_basis_v22',None),('cycle_voltage_upper_V',-10)]:
            changed=json.loads(json.dumps(original));changed[field]=value
            try:child.Dataset(valid.profile,[changed],valid.features).feature_matrix()
            except child.DataNotReady:ck('reject_invalid_'+field+str(value),True)
            else:raise AssertionError('Invalid test admitted:'+field)
        for key in['v22:COT_CDAP800350_2E_C5000','v22:NFACc_2E_C10000']:
            row=new.by_endpoint(key)
            try:child.Dataset('reported_2e',[row],valid.features).feature_matrix()
            except child.DataNotReady:ck('legacy_rejects_early_year_'+key,True)
            else:raise AssertionError('Legacy year restriction lost')
        ck('five_links',len(new.literature_links())==len(old.literature_links())+5)
        aux=[r for p in['3e','2e_device','native_mineral_3e','2e_author_factor2']for r in lit.auxiliary_feature_rows(p)]
        holds={};candidate_dois={r['material_key']:r['doi']for r in lit.materials()}
        for doi in[COT,QSC,ANN]:
            g='doi:'+doi;holds[doi]=dict(all_cycle_observations=sum(r['source_group']==g for r in newall.values()),capacitance_reports=len(lit.capacitances(doi=doi)),bounded_curve_samples=sum(r['doi']==doi for r in lit.sampled_curves()),auxiliary_rows=sum(r['source_group']==g for r in aux),all_labels_same_source_quarantined=True);ck('quarantine_'+doi,all(r['source_group']==g for r in aux if r['doi']==doi)and all(r['source_group']==g for r in lit.capacitances(doi=doi))and all(r['record']['source_group']==g for r in lit.tests()if candidate_dois[r['material_key']]==doi))
    report=dict(status='passed',database_sha256=sha(DB),check_count=len(checks),checks=sorted(checks),profiles=counts,observations=281,source_groups=181,new_endpoints=3,promoted_existing_endpoints=2,new_purpose_admissions=5,cross_task_holdouts=holds,original_fixed_resolved=1,original_fixed_pending=38,model_fits=0,full_goal_complete=False)
    if prepare:
        assert not(OUT/'merge_manifest.json').exists();write(OUT/'verification.json',report);write(OUT/'summary.json',{k:v for k,v in report.items()if k!='checks'})
    else:
        assert json.loads((OUT/'verification.json').read_text('utf8'))==report
        if(OUT/'merge_manifest.json').exists():
            for p in json.loads((OUT/'merge_manifest.json').read_text('utf8'))['outputs']:assert sha(ROOT/p['path'])==p['sha256']
    print(json.dumps({k:v for k,v in report.items()if k!='checks'},ensure_ascii=False))
def seal():
    if(OUT/'merge_manifest.json').exists():raise FileExistsError('Alreadysealed')
    verify(False);paths=[p for p in OUT.rglob('*')if p.is_file()]+[ROOT/'tools/release_cycle_admissions_v022.py']
    write(OUT/'merge_manifest.json',dict(version='cycling_v0.22',parent_sha256=PSHA,outputs=[dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p),bytes=p.stat().st_size)for p in sorted(paths)],model_fits=0,scientific_goal_complete=False))
    write(ROOT/'data/current_database.json',dict(version_directory=OUT.relative_to(ROOT).as_posix(),database_file=DB.name,sha256=sha(DB),parent_database_file=(PARENT/'cycling_v0_21.sqlite').relative_to(ROOT).as_posix(),default_profile='reported_3e',stage='own_cycle_five_test_admissions',ready_for_training_inputs=True,research_training_authorized=False,all_records_admitted=False))
if __name__=='__main__':
    if len(sys.argv)!=2 or sys.argv[1]not in['build','repair_draft_scope','repair_own_bet','prepare','verify','seal']:raise SystemExit('build/prepare/sealonce; verifyreadonly')
    if sys.argv[1]=='prepare':verify(True)
    else:globals()[sys.argv[1]]()
