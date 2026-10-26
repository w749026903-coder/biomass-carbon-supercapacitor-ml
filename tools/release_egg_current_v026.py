"""One-use correction of an existing endpoint, using an overlooked original sentence."""
from pathlib import Path
import json,sqlite3,sys,xml.etree.ElementTree as E
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tools'))
from extract_onion_composite_v8 import sha,write
from extract_source_series_v13 import clean
OUT=ROOT/'循环稳定性数据库_v0.26_蛋米循环电流补正_20261027'
DB=OUT/'cycling_v0_26.sqlite';PARENT=ROOT/'循环稳定性数据库_v0.25_芒果核皮革循环准入_20261026'
PSHA='8a8f311509df7d72738840aac31ced027849a538ee31ec785ede71aa4abcc5b2'
KEY='candidate:TE009';DOI='10.3390/molecules28186543'
PROFILES=['reported_3e','reported_3e_residue_sensitivity','reported_3e_sensitivity','reported_3e_all_years']
SOURCE=ROOT/'同体系文献补充_第二批_20261017/定向扩搜40至60篇_20261017/sources/OA007/main.xml'
SSHA='40eb264737fcfd84211214ea784030f0808590d65ce27304ee46a77919fac391'
def build():
    assert sha(PARENT/'cycling_v0_25.sqlite')==PSHA and sha(SOURCE)==SSHA and not OUT.exists()
    from data.cycling_db import open_database
    from data.literature_current import open_literature_database
    with open_database()as old,open_literature_database()as lit:
        assert old.path==PARENT/'cycling_v0_25.sqlite'
        before=old.by_endpoint(KEY);assert before['reported_current_A_g']is None and before['eligible']==0 and before['retention_pct']==82.26 and before['BET_m2_g']==1572.1
        oldreview=next(r for r in old.reviewed_pending_batch()if r['endpoint_id']==KEY);assert oldreview['open_issues']==['cycling_current_A_g_not_located']
        paragraph=clean(E.parse(SOURCE).getroot().findall('.//body//p')[11]);assert 'YPAC-1 also underwent 10 A g−1 constant-current charge/discharge cycles.'in paragraph
        link=lit.batch19_cycle_identity_links()[0]['record'];assert link['existing_endpoint_id']==KEY and link['new_reported_current_A_g']==10
        facts=lit.canonical_material_features_v13(DOI,'YPAC-1');assert facts['values']['BET_surface_area_m2_g']==1572.1
        after=dict(before,reported_current_A_g=10,reported_current_A_g_status='v026_original_body_P11_explicit_cycling_sentence',current_mass_basis='author_reported_unknown_not_inferred',current_mass_basis_status='v026_reported_protocol_not_physical_calibration',eligible=1,workflow_status='reviewed_and_admitted_reported_protocol',admission_status='approved_for_reported_protocol',admission_profiles_v26=PROFILES,review_disposition_v26='approved_reported_protocol',label_evidence_kind='author_printed_numeric_label',label_reading_bound_pp=None,all_years_admission_basis_v26='explicit_v026_test_review')
        # All historical profile markers and the unknown physical current/index stay unchanged.
        after['review_disposition_v12']=before['review_disposition_v12'];after['review_disposition_v15']=before['review_disposition_v15']
        proof=[]
        def ev(field,value,locator,reason,selected=1):
            proof.append(dict(evidence_id='V26:'+str(len(proof)+1),endpoint_id=KEY,field_name=field,value_json=json.dumps(value,ensure_ascii=False),path=SOURCE.relative_to(ROOT).as_posix(),sha256=SSHA,locator=locator,selected=selected,note=reason))
        ev('reported_current_A_g',None,'Previousv0.12/v0.15review ofsameXML', 'Historicalnotlocatedclaim superseded by explicit sentence; oldreview preserved',0)
        ev('reported_current_A_g',10,'bodyP11 complete paragraph, sentence explicitly YPAC-1 also underwent10Agconstantcurrentcharge/dischargecycles','Cyclingcurrent explicitlyauthorreported; not inferredfromfreshGCD/CEformula')
        for f,loc in [('retention_pct','bodyP11/22 andactualFig6d numeric82.26'),('cycle_count','bodyP11/22 andactualFig6d 10000'),('system','actualFig6dcaptionthreeelectrode; bodyP18HgO/Hg-Pt configuration'),('electrolyte','bodyP18 6MKOH3E'),('concentration_mol_L','bodyP18 6MKOH3E'),('BET_m2_g','OwnTable1 YPAC-1row m2/g; bodyP11 cm2/g dissent retained byoldselectedTablevalue'),('cycle_voltage_lower_V','OwnFig6b/5d -1..0VsHg/HgO; existingv0.12 applicableGCDprogramme review retained'),('cycle_voltage_upper_V','OwnFig6b/5d -1..0VsHg/HgO; existingv0.12 applicableGCDprogramme review retained'),('reference_electrode','bodyP18 explicitHgO/Hg authororder'),('baseline_reference','OwnFig6d initialnormalized100%, do not invent exactcycleindex')]:ev(f,after[f],loc,'Ownsame-samplebinding retained; originalolddecisions not rewritten')
        review=dict(endpoint_id=KEY,sample_name='YPAC-1',source_group='doi:'+DOI,disposition='approved_reported_protocol',approved_profiles=PROFILES,open_issues=[],open_feature_issues=['XPSpercentbasisunreported_and_sum100point71','Rscompetingreports'],reason='Previouslymissedexplicit10Agcyclingcurrent nowbound tosameexisting82.26%/10000cycles3E endpoint; all current purpose core evidence verified',resolution=['cycling_current_A_g_not_located resolved by originalbodyP11sentence'],caveats=['Unknowncurrentmassdenominator is retained, canonicalphysicalcurrentnotadmitted','Authornormalizedinitialreference retained, exactcycleindexunknown','OptionalXPS/Rsdisputes not usedtopredictor orfalseatomicvalues','Oldfixed39scopeunchanged; one existingpendingendpointresolved, notnewendpoint'],previous_review=oldreview,review_version='v0.26',model_fits=0)
        contract=dict(old.contract,schema='cycling_existing_egg_endpoint_current_correction_v26',database_file=DB.name,parent_database_sha256=PSHA,parent_directory=PARENT.name,parent_api_directory=PARENT.name,research_training_authorized=False,correction_scope=dict(fixed_original_records=39,resolved_original=2,pending_original=37,endpoint=KEY,existing_endpoint_not_inserted=True),current_version='v0.26')
        litsha=sha(lit.database)if hasattr(lit,'database')else json.loads((ROOT/'data/current_literature.json').read_text('utf8'))['sha256']
        OUT.mkdir();write(OUT/'data_contract.json',contract);write(OUT/'source_review.json',dict(paragraph_P11_unabridged=paragraph,path=SOURCE.relative_to(ROOT).as_posix(),sha256=SSHA,before=before,after=after,current_review=review,previous_admission_checks=old.admission_checks(KEY),previous_pending_review=oldreview,literature_v19_sha256=litsha,full_source_review_complete=False))
    c=sqlite3.connect(DB)
    try:
        c.executescript('pragma foreign_keys=on;create table reviewed_endpoints_v26(endpoint_id text primary key,row_json text not null,review_json text not null);create table profile_membership_v26(endpoint_id text references reviewed_endpoints_v26,profile text,primary key(endpoint_id,profile));create table evidence_v26(evidence_id text primary key,endpoint_id text references reviewed_endpoints_v26,field_name text,value_json text,path text,sha256 text,locator text,selected integer,note text);create table changes_v26(change_id integer primary key,endpoint_id text references reviewed_endpoints_v26,field_name text,before_json text,after_json text,evidence_json text);create table literature_links_v26(candidate_id text primary key,endpoint_id text references reviewed_endpoints_v26,literature_sha256 text,status text);')
        c.execute('insert into reviewed_endpoints_v26 values(?,?,?)',(KEY,json.dumps(after,ensure_ascii=False),json.dumps(review,ensure_ascii=False)))
        c.executemany('insert into profile_membership_v26 values(?,?)',[(KEY,p)for p in PROFILES]);c.executemany('insert into evidence_v26 values(:evidence_id,:endpoint_id,:field_name,:value_json,:path,:sha256,:locator,:selected,:note)',proof)
        for f in sorted(after):
            if before.get(f)!=after[f]:c.execute('insert into changes_v26(endpoint_id,field_name,before_json,after_json,evidence_json)values(?,?,?,?,?)',(KEY,f,json.dumps(before.get(f),ensure_ascii=False),json.dumps(after[f],ensure_ascii=False),json.dumps([e for e in proof if e['field_name']==f],ensure_ascii=False)))
        c.execute('insert into literature_links_v26 values(?,?,?,?)',(KEY,KEY,litsha,'existing_endpoint_corrected_and_admitted_reported_protocol_v026'));c.commit()
    finally:c.close()
    protected=[PARENT/'cycling_v0_25.sqlite',SOURCE,ROOT/'同体系文献补充_第二批_20261017/定向扩搜40至60篇_20261017/sources/OA007/molecules-2594381-supplementary.pdf',ROOT/'同体系文献补充_第二批_20261017/定向扩搜40至60篇_20261017/sources/OA007/figures/molecules-28-06543-g006.jpg']
    write(OUT/'protected_inputs.json',[dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p))for p in protected]);print('Built unsealed v0.26: corrected existingTE009, no new endpoint or fit')
if __name__=='__main__':
    if sys.argv[1:]!=['build']:raise SystemExit('One-use build before release')
    build()
