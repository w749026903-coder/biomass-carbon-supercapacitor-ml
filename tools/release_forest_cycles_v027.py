"""One-use review of three existing forest endpoints in the declared residue sensitivity purpose."""
from pathlib import Path
import json,sqlite3,sys,xml.etree.ElementTree as E
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tools'))
from extract_onion_composite_v8 import sha,write
from extract_source_series_v13 import clean
from release_feature_freezes_v021 import load
OUT=ROOT/'循环稳定性数据库_v0.27_林业含灰双电极准入_20261028';DB=OUT/'cycling_v0_27.sqlite'
PARENT=ROOT/'循环稳定性数据库_v0.26_蛋米循环电流补正_20261027';PSHA='0db5456c736716b285a0223e2d63cc81e7c137c1fda00e9846f768b3870885cb'
LIT=ROOT/'文献全量利用复核_20261027/批次22_林业多前驱体松木配方与参考体系';LSHA='407161771aaefe2bd1539f545a36b1166d80ff145c569ceac3d3fa5ffff6a778'
SOURCE=ROOT/'同体系文献补充_第二批_20261017/sources/L04/fulltext.xml';SSHA='c8bbac8d77d2786022a4702629079b697a30b1c6e53d79ac68eb785c4024cea7'
FIG=SOURCE.parent/'d3ra00820g-f8.jpg';POLICY=ROOT/'循环稳定性数据库_v0.3_数据库优化_20261017/第四轮_专业复核与训练数据_20261017/prediction_input_contract.json'
DOI='10.1039/d3ra00820g';PROFILES=['reported_2e_residue','reported_2e_approx']
JOBS=[('candidate:B20:B2_004:1','PAC',88.31,2813,90.03),('candidate:B20:B2_004:2','SAC',93.10,3565,96.82),('candidate:B20:B2_004:3','LAC',93.53,2981,85.22)]
API=r'''"""Read-only v0.27: existing three forest endpoints, residue sensitivity only."""
from pathlib import Path
import collections,hashlib,importlib.util,json,math,sqlite3,sys
ROOT=Path(__file__).resolve().parents[1];FOLDER=Path(__file__).resolve().parent
PARENT=ROOT/'循环稳定性数据库_v0.26_蛋米循环电流补正_20261027';NAME='_cycling_v026_parent_for_v027'
if NAME not in sys.modules:
    spec=importlib.util.spec_from_file_location(NAME,PARENT/'ml_data.py');module=importlib.util.module_from_spec(spec);sys.modules[NAME]=module;spec.loader.exec_module(module)
base=sys.modules[NAME];DataNotReady=base.DataNotReady;family_key=base.family_key
PROFILES=['reported_2e_residue','reported_2e_approx']
class Dataset(base.Dataset):
    def feature_matrix(self):
        current=[r for r in self.rows if r.get('review_disposition_v27')]
        if not current:return super().feature_matrix()
        others=[r for r in self.rows if not r.get('review_disposition_v27')]
        historical=base.Dataset(self.profile,others,list(self.features)).feature_matrix()if others else{}
        for r in current:
            if self.profile not in PROFILES or self.profile not in r.get('admission_profiles_v27',[])or r.get('eligible')!=1:raise DataNotReady('Explicit v0.27 residue-purpose membership required')
            if r.get('admission_status')!='approved_for_reported_protocol'or r.get('system')!='2E_symmetric'or r.get('method')!='GCD'or r.get('metric_kind')!='capacitance_retention'or r.get('retention_relation')!='eq'or not r.get('baseline_reference'):raise DataNotReady('Reviewed own cycling target, system and author reference required')
            if r.get('material_scope_v27')!='biomass_carbon_with_author_reported_ash_AlOH3_impurity'or not r.get('ordinary_2e_excluded_v27'):raise DataNotReady('Keep actual inorganic residue scope separate')
            year=r.get('source_year')
            if isinstance(year,bool)or not isinstance(year,int)or not 2023<=year<=2026:raise DataNotReady('Current declared year scope required')
            for f in self.features+['retention_pct']:
                v=r.get(f)
                if f=='electrolyte':
                    if not isinstance(v,str)or not v.strip():raise DataNotReady('Missing electrolyte identity')
                elif isinstance(v,bool)or not isinstance(v,(int,float))or not math.isfinite(v):raise DataNotReady('Missing finite numeric core')
            if any(r[f]<=0 for f in ['cycle_count','reported_current_A_g','concentration_mol_L','BET_m2_g'])or r['cycle_count']<1000 or r['cycle_voltage_upper_V']<=r['cycle_voltage_lower_V']or r['retention_pct']<0:raise DataNotReady('Invalid condition or cycling label')
        groups=[family_key(r['source_group'])for r in self.rows];counts=collections.Counter(groups)
        result=dict(X=[[r[f]for f in self.features]for r in self.rows],y=[r['retention_pct']for r in self.rows],groups=groups,sample_weight=[1/counts[g]for g in groups],feature_names=list(self.features),training_authorized=False,current_semantics='author_reported_protocol_descriptor',raw_source_groups=[r['source_group']for r in self.rows],grouping_policy='SameDOI andexplicitpriorworkfamily, all materials/conditions/auxiliarylabels quarantined together',v27_validation='Three existing source-bound exact endpoints in alreadydeclared residueinclusive purpose; ordinaryprofiles unchanged')
        index={r['endpoint_id']:i for i,r in enumerate(others)}
        fields={'label_relations':'retention_relation','label_evidence_kind':'label_evidence_kind','label_reading_bound_pp':'label_reading_bound_pp','baseline_references':'baseline_reference'}
        for k,f in fields.items():
            if k in historical:result[k]=[historical[k][index[r['endpoint_id']]]if r['endpoint_id']in index else r.get(f)for r in self.rows]
        return result
class Database(base.Database):
    def __init__(self,path=None):
        contract=json.loads((FOLDER/'data_contract.json').read_text('utf8'))
        with(PARENT/'cycling_v0_26.sqlite').open('rb')as f:
            if hashlib.file_digest(f,'sha256').hexdigest()!=contract['parent_database_sha256']:raise RuntimeError('Immutablev026fingerprint differs')
        super().__init__(PARENT/'cycling_v0_26.sqlite');self.root,self.contract=FOLDER,contract;self.path=Path(path).resolve()if path else FOLDER/contract['database_file']
        self.delta_v27=sqlite3.connect(self.path.as_uri()+'?mode=ro',uri=True);self.delta_v27.row_factory=sqlite3.Row;self.delta_v27.execute('pragma query_only=on')
        self.rows_v27={r['endpoint_id']:json.loads(r['row_json'])for r in self.delta_v27.execute('select *from reviewed_endpoints_v27')};self.reviews_v27={r['endpoint_id']:json.loads(r['review_json'])for r in self.delta_v27.execute('select *from reviewed_endpoints_v27')};self.members_v27=collections.defaultdict(set)
        for r in self.delta_v27.execute('select *from profile_membership_v27'):self.members_v27[r['profile']].add(r['endpoint_id'])
    def close(self):
        if hasattr(self,'delta_v27'):self.delta_v27.close()
        super().close()
    def fetch(self,profile=None,year_min=None,year_max=None):
        old=super().fetch(profile,year_min,year_max)
        if not hasattr(self,'rows_v27'):return old
        rows={r['endpoint_id']:r for r in old.rows if r['endpoint_id']not in self.rows_v27}
        for key,r in self.rows_v27.items():
            if old.profile!='all_review'and key not in self.members_v27.get(old.profile,set()):continue
            if year_min is not None and r['source_year']<int(year_min)or year_max is not None and r['source_year']>int(year_max):continue
            rows[key]=json.loads(json.dumps(r))
        counts=collections.Counter(family_key(r['source_group'])for r in rows.values())
        for r in rows.values():r.update(source_family_group_v23=family_key(r['source_group']),source_weight=1/counts[family_key(r['source_group'])])
        return Dataset(old.profile,sorted(rows.values(),key=lambda r:(r['source_family_group_v23'],r['endpoint_id'])),list(old.features))
    def by_endpoint(self,key):return json.loads(json.dumps(self.rows_v27[key]))if key in getattr(self,'rows_v27',{})else super().by_endpoint(key)
    def holds(self,key):
        if key not in getattr(self,'reviews_v27',{}):return super().holds(key)
        return dict(self.reviews_v27[key],previous_holds=super().holds(key))
    def admission_checks(self,key,profile=None):
        if key not in getattr(self,'reviews_v27',{}):return super().admission_checks(key,profile)
        return[dict(endpoint_id=key,profile=p,status='approved_for_reported_protocol'if key in self.members_v27.get(p,set())else'not_admitted_to_this_purpose',current_review=self.reviews_v27[key],review_version='v0.27')for p in([profile]if profile else self.contract['profiles'])]
    def evidence(self,key,field=None):
        old=super().evidence(key,field)
        if key not in getattr(self,'rows_v27',{}):return old
        changed={'BET_m2_g','cycle_voltage_lower_V','cycle_voltage_upper_V','baseline_reference'}
        old=[dict(r,currently_selected=0,superseded_by_v27=True)if r.get('field_name')in changed else r for r in old]
        return old+[dict(r,value=json.loads(r['value_json']),currently_selected=r['selected'],review_version='v0.27')for r in self.delta_v27.execute('select *from evidence_v27 where endpoint_id=?and(?is null or field_name=?)',(key,field,field))]
    def field_changes(self,key=None,include_history=False):
        old=super().field_changes(key,True)if include_history else[]
        if not hasattr(self,'delta_v27'):return old
        return old+[dict(r,before=json.loads(r['before_json']),after=json.loads(r['after_json']),evidence=json.loads(r['evidence_json']),review_version='v0.27')for r in self.delta_v27.execute('select *from changes_v27 where(?is null or endpoint_id=?)',(key,key))]
    def literature_links(self):return super().literature_links()+([dict(r,review_version='v0.27')for r in self.delta_v27.execute('select *from literature_links_v27')]if hasattr(self,'delta_v27')else[])
'''
def build():
    assert not OUT.exists()and sha(PARENT/'cycling_v0_26.sqlite')==PSHA and sha(SOURCE)==SSHA and sha(LIT/'literature_material_pool_v22.sqlite')==LSHA
    from data.cycling_db import open_database
    from data.literature_v22 import open_literature_database
    rawpolicy=json.loads(POLICY.read_text('utf8'));assert rawpolicy['scope']['material']=='biomass carbon main; residue-inclusive sensitivity separately declared'
    root=E.parse(SOURCE).getroot();paragraphs={i:clean(p)for i,p in enumerate(root.findall('./body//p'),1)}
    assert 'two identical AC-based electrodes'in paragraphs[21]and'3 A g−1'in paragraphs[21]and'pellet electrodes with 6 M KOH'in paragraphs[43]and'Al (OH)3'in paragraphs[37]
    proof=[];records=[]
    with open_database()as old,open_literature_database(LIT/'literature_material_pool_v22.sqlite',LSHA)as lit:
        assert old.path==PARENT/'cycling_v0_26.sqlite';assert len(old.reviewed_pending_batch())==37
        for key,s,ret,bet,tga in JOBS:
            before=old.by_endpoint(key);assert before['sample_name']==s and before['retention_pct']==ret and before['cycle_count']==10000 and before['reported_current_A_g']==3 and before['source_year']==2023 and before['method']=='GCD'and before['system']=='2E_symmetric'and before['source_group']=='doi:'+DOI
            assert all(before[f]is None for f in ['BET_m2_g','cycle_voltage_lower_V','cycle_voltage_upper_V','baseline_reference','canonical_current_A_g','baseline_cycle'])
            f=lit.canonical_material_features_v13(DOI,s)['values'];assert f['BET_surface_area_m2_g']==bet and f['TGA_air_author_carbon_fraction_pct']==tga
            assert any(r['record']['existing_endpoint_id']==key for r in lit.batch22_cycle_identity_links())
            baseline=dict(reference='Authors own Table3retention andFig8e initial capacitance reference for same sample and water programme',exact_reference_cycle=None,not_fresh_rate_C_at_other_current=True)
            after=dict(before,BET_m2_g=bet,BET_m2_g_status='v027_own_Table1_uncorrected_whole_sample_BET',cycle_voltage_lower_V=0,cycle_voltage_upper_V=1,cycle_voltage_lower_V_status='v027_applicable_same_cell_GCD_programme_Fig8b_not_individual_cycle_trace',cycle_voltage_upper_V_status='v027_applicable_same_cell_GCD_programme_Fig8b_not_individual_cycle_trace',baseline_reference=json.dumps(baseline,ensure_ascii=False),baseline_reference_status='v027_author_retention_reference_exact_cycle_index_unknown',eligible=1,workflow_status='reviewed_and_admitted_residue_reported_protocol',admission_status='approved_for_reported_protocol',admission_profiles_v27=PROFILES,review_disposition_v27='approved_residue_reported_protocol',material_scope_v27='biomass_carbon_with_author_reported_ash_AlOH3_impurity',ordinary_2e_excluded_v27=True,label_evidence_kind='author_tabulated_numeric_retention',label_reading_bound_pp=None,current_mass_basis='author_reported_unknown_not_inferred',current_mass_basis_status='v027_empirical_descriptor_not_calibrated_physical_current',author_TGA_carbon_proxy_pct_v27=tga,scope_flags=json.dumps(dict(material_scope='biomass_carbon_with_inorganic_residue',AlOH3_impurity_author_reported=True,ash_quantification='TGAproxy_not_elementalcarbon',ordinary_main=False),ensure_ascii=False),scope_flags_status='v027_actual_author_ash_and_AlOH3_scope_separate_from_ordinary_carbon')
            review=dict(endpoint_id=key,sample_name=s,source_group='doi:'+DOI,disposition='approved_residue_reported_protocol',approved_profiles=PROFILES,open_issues=[],open_feature_issues=['Ramanintensity_vsareaambiguous','binderidentityunreported','AlOH3individualmassfractionunquantified'],outside_profiles=['reported_2e','reported_2e_all_years','reported_3e','canonical_2e'],reason='SameownTable1material/uncorrectedBET andTable3retention; pelletwaterprogramme0..1V actualGCD/3Ag10k; authorreportedashresiduepurpose only, notordinarycarbon',caveats=['Fig8b is applicableGCDprogramme at1Ag, not a claim thatFig8e draws individualcyclingvoltage','Exactbaselinecycle/temperature/currentmassdenominatorremainunknown','TGAauthorcarbonproxy notEA_C; ash-freeBET notselected','No known reuse claim found in reviewed own source; allsameDOI and other tasks heldouttogether','Outsideoriginalfixed39andhistorical41audit; no deductionfrom37'],previous_admission_checks=old.admission_checks(key),previous_holds=old.holds(key),review_version='v0.27',model_fits=0)
            def ev(field,value,loc,reason,path=SOURCE):
                proof.append(dict(evidence_id='V27:'+str(len(proof)+1),endpoint_id=key,field_name=field,value_json=json.dumps(value,ensure_ascii=False),path=path.relative_to(ROOT).as_posix(),sha256=sha(path),locator=loc,selected=1,note=reason))
            for field,loc in [('BET_m2_g','OwnTable1 row '+s+' rawSSA_AC_not_ashfree'),('retention_pct','OwnTable3 row '+s+' exactretention10k3Ag'),('cycle_count','MainP21 andOwnTable3'),('reported_current_A_g','MainP21 aqueous3Ag, actualFig8e3Ag'),('electrolyte','MainP21/P43 andOwnTable3 6MKOH'),('concentration_mol_L','MainP21 andOwnTable3'),('system','MainP21 twoidenticalACelectrodes symmetriccell'),('baseline_reference','OwnTable3retention andFig8e owninitial-to-finalcapacitance reference; exactindexunknown'),('material_scope_v27','MainP37AlOH3 andOwnTable1TGAproxy; notintentionalSiO2_GOdispersion'),('author_TGA_carbon_proxy_pct_v27','OwnTable1 finalAC row '+s)]:ev(field,after[field],loc,'Source/same sample and pellet programme bound; no mass-calibration inference')
            for field in ['cycle_voltage_lower_V','cycle_voltage_upper_V']:ev(field,after[field],'ActualFig8b0..1V applicableKOHpelletGCD programme; Fig8e/Table3samewatercyclingsection', 'Applicableprogramme inheritance explicit; no assertion of individuallyplottedcyclingvoltage',FIG)
            ev('electrode_form','pressed_pellet','MainP19/P43; AC/CB/binder8:1:1,~7mg1.2cm2,80MPa,200C1hair', 'SiO2/GOdispersiononlyESI, notusedforTable3')
            ev('mass_balance','two_identical_AC_based_electrodes','MainP21 explicittwoidenticalelectrodes; MainP19samepelletmethod','Symmetricmatchingjustifiedbyauthors, not guessed fromcapacitanceformula')
            ev('residue_purpose',PROFILES,'scope.material','Existingcontractresidue-inclusivesensitivity, not ordinaryapproval',POLICY)
            records.append(dict(before=before,after=after,current_review=review))
        contract=dict(old.contract,schema='cycling_existing_forest_residue_endpoints_v27',database_file=DB.name,parent_database_sha256=PSHA,parent_directory=PARENT.name,parent_api_directory=PARENT.name,current_version='v0.27',research_training_authorized=False,scope='Threeexistingforestwater2Eendpoints, alreadydeclaredresidueinclusive sensitivityonly',correction_scope=dict(fixed_original_records=39,resolved_original=2,pending_original=37,newly_reviewed_outside_original=3),material_scope_v27=dict(author_claim='ash_and_AlOH3impurity',TGA_proxy_not_elemental_C=True,ordinary_main=False,approved_profiles=PROFILES),new_endpoints=0,new_materials=0,promoted_existing_endpoints=3)
    OUT.mkdir();write(OUT/'data_contract.json',contract);(OUT/'ml_data.py').write_text(API,encoding='utf8')
    write(OUT/'source_review.json',dict(records=records,source_path=SOURCE.relative_to(ROOT).as_posix(),source_sha256=SSHA,literature_database_sha256=LSHA,policy_path=POLICY.relative_to(ROOT).as_posix(),policy_sha256=sha(POLICY),complete_evidence_paragraphs={str(k):paragraphs[k]for k in [16,18,19,20,21,37,42,43,44,45,47,49]},full_source_review_complete=False))
    c=sqlite3.connect(DB)
    try:
        c.executescript('pragma foreign_keys=on;create table reviewed_endpoints_v27(endpoint_id text primary key,row_json text,review_json text);create table profile_membership_v27(endpoint_id text references reviewed_endpoints_v27,profile text,primary key(endpoint_id,profile));create table evidence_v27(evidence_id text primary key,endpoint_id text references reviewed_endpoints_v27,field_name text,value_json text,path text,sha256 text,locator text,selected integer,note text);create table changes_v27(change_id integer primary key,endpoint_id text references reviewed_endpoints_v27,field_name text,before_json text,after_json text,evidence_json text);create table literature_links_v27(candidate_id text primary key,endpoint_id text references reviewed_endpoints_v27,literature_sha256 text,status text);')
        for rec in records:
            before,after=rec['before'],rec['after'];key=after['endpoint_id'];c.execute('insert into reviewed_endpoints_v27 values(?,?,?)',(key,json.dumps(after,ensure_ascii=False),json.dumps(rec['current_review'],ensure_ascii=False)));c.executemany('insert into profile_membership_v27 values(?,?)',[(key,p)for p in PROFILES])
            for f in sorted(after):
                if before.get(f)!=after[f]:c.execute('insert into changes_v27(endpoint_id,field_name,before_json,after_json,evidence_json)values(?,?,?,?,?)',(key,f,json.dumps(before.get(f),ensure_ascii=False),json.dumps(after[f],ensure_ascii=False),json.dumps([e for e in proof if e['endpoint_id']==key and e['field_name']==f],ensure_ascii=False)))
            c.execute('insert into literature_links_v27 values(?,?,?,?)',(key,key,LSHA,'existing_forest_endpoint_admitted_residue_only_v027'))
        c.executemany('insert into evidence_v27 values(:evidence_id,:endpoint_id,:field_name,:value_json,:path,:sha256,:locator,:selected,:note)',proof);c.commit()
    finally:c.close()
    paths=[PARENT/'cycling_v0_26.sqlite',PARENT/'ml_data.py',SOURCE,FIG,POLICY,LIT/'literature_material_pool_v22.sqlite',LIT/'merge_manifest.json']
    write(OUT/'protected_inputs.json',dict(files=[dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p),bytes=p.stat().st_size)for p in paths]));print('Unsealedv027 built; no newendpoints orfitting')
if __name__=='__main__':
    if sys.argv[1:]!=['build']:raise SystemExit('One-use build only before sealing')
    build()
