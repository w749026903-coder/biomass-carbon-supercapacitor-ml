"""Readonly checks; preparation and sealing are one-use before release."""
import collections,contextlib,csv,io,json,math,sqlite3,sys,xml.etree.ElementTree as E
from pathlib import Path
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tools'))
from extract_identity_rates_v21 import OUT,DB,PARENT,PSHA,RH,CO,sha,write,ro,y_at,color_match,clean
from data.literature_v21 import open_literature_database,MODES21,FIELDS20
from data.literature_v20 import open_literature_database as old_open,TARGETS20
from data.cycling_identity import cycling_endpoints_by_doi

def verify(prepare=False):
    if prepare:assert not(OUT/'merge_manifest.json').exists()
    spec=json.loads((OUT/'curation_spec.json').read_text('utf8'));digest=sha(DB);checks=[]
    def ck(n,b):assert b,n;checks.append(n)
    ck('parent_hash',sha(PARENT)==PSHA)
    for r in json.loads((OUT/'protected_inputs.json').read_text('utf8')):ck('protected:'+r['path'],sha(ROOT/r['path'])==r['sha256'])
    for r in json.loads((PARENT.parent/'merge_manifest.json').read_text('utf8'))['outputs']:ck('old_manifest:'+r['path'],sha(ROOT/r['path'])==r['sha256'])
    with contextlib.closing(ro(DB))as c,contextlib.closing(ro(PARENT))as p:
        ck('integrity',[r[0]for r in c.execute('pragma integrity_check')]==['ok']);ck('foreign_keys',not c.execute('pragma foreign_key_check').fetchall())
        for name, in p.execute("select name from sqlite_master where type='table'and name not like'sqlite_%'"):ck('all_parent_rows_unchanged:'+name,{tuple(r)for r in p.execute('select *from "'+name+'"')}<={tuple(r)for r in c.execute('select *from "'+name+'"')})
        for t,delta in [('capacitance_observations',36),('curve_samples_v8',36),('reviewed_tables',2),('extraction_units_v3',2),('materials',0),('material_facts',0),('outcome_observations_v3',0),('test_candidates',0),('reviewed_sources',0)]:ck('delta:'+t,c.execute('select count(*)from '+t).fetchone()[0]-p.execute('select count(*)from '+t).fetchone()[0]==delta)
        ck('raw_queue_unchanged',list(c.execute('select *from raw_table_queue order by table_id'))==list(p.execute('select *from raw_table_queue order by table_id')))
    for r in spec['readings']:
        doc=spec['documents'][r['document']];im=Image.open(ROOT/doc['path']).convert('RGB');key=r['reading_id'];a=r['axis'];xc=round(r['pixel_x']);expected=[]
        for y in range(r['manual_roi_y'][0],r['manual_roi_y'][1]+1):
            xs=[x for x in range(xc-3,xc+4)if color_match(r['color'],im.getpixel((x,y)))]
            if xs:expected.append(dict(y=y,left=min(xs),right=max(xs),span=max(xs)-min(xs)+1,count=len(xs)))
        ck('native_color_pixels:'+key,expected==r['color_candidates']);ck('native_scalar:'+key,math.isclose(r['y_value'],y_at(a,r['pixel_y'])));ck('native_bounds:'+key,r['y_lower_bound']<r['y_value']<r['y_upper_bound']and math.isclose(r['y_upper_bound']-r['y_lower_bound'],8*abs((a['y1']-a['y0'])/(a['yp1']-a['yp0']))));ck('bounds_not_SD:'+key,r['reading_bounds_not_experimental_SD_or_CI']and not r['errorbar_whiskers_quantified']);ck('not_reusing_CV_for_GCD:'+key,r['panel']!='RH6c'or r['author_exact_observation_id']is None)
    with open_literature_database(DB,digest)as d,old_open(PARENT,PSHA)as old:
        ck('all_old_fact_API_exact',d.facts()==old.facts());oldcaps={r['observation_id']:r for r in old.capacitances()};curcaps={r['observation_id']:r for r in d.capacitances()};fix={r['observation_id']:r for r in spec['protocol_corrections']}
        for oid,r in oldcaps.items():
            cur=curcaps[oid]
            if oid in fix:
                ck('original_protocol_preserved:'+oid,cur['original_protocol_v20']==dict(method=r['method'],scan_rate_mV_s=r['scan_rate_mV_s'],current_A_g=r['current_A_g'],conditions=r['conditions']));ck('selected_CV5:'+oid,cur['method']=='CV'and cur['scan_rate_mV_s']==5 and cur['current_A_g']is None and cur['value']==r['value']);ck('other_old_fields_exact:'+oid,{k:v for k,v in cur.items()if k not in ['method','scan_rate_mV_s','conditions','original_protocol_v20','protocol_binding_decision_v21']}=={k:v for k,v in r.items()if k not in ['method','scan_rate_mV_s','conditions']})
            else:ck('old_cap_API_exact:'+oid,cur==r)
        ck('CV_filter_after_binding',len(d.capacitances(RH,method='CV'))==3 and len(d.capacitances(RH,method='GCD'))==24)
        xml=E.parse(ROOT/spec['documents']['Rice20']['path']).getroot();cap=clean(next(f for f in xml.findall('.//fig')if clean(f.find('label'))=='Fig. 6').find('caption'));ck('source_explicit_Fig6b5mVs','(b) specific capacitance of SCs with varying'in cap and 'at a scan rate of 5 mV s−1'in cap)
        for t in TARGETS20:ck('v20_matrix_exact:'+t,d.batch20_matrix(t)==old.batch20_matrix(t))
        for profile in ['3e','2e_device','native_mineral_3e','2e_author_factor2']:ck('old_auxiliary_exact:'+profile,d.auxiliary_gcd(profile)==old.auxiliary_gcd(profile))
        ck('ordinary189_expanded358',len(d.auxiliary_gcd())==189 and len(d.expanded_graph_3e_matrix()['y'])==358)
        preflight={};exports=[]
        for mode,n in zip(MODES21,[3,12,12]):
            rows=d.batch21_rate_rows(mode);matrix=d.batch21_rate_matrix(mode);ck('mode_count:'+mode,len(rows)==n==len(matrix['y']));ck('nominal_unique:'+mode,len(set(matrix['nominal_report_groups']))==n);ck('source_one:'+mode,matrix['source_families']==1 and all(g=='doi:'+CO for g in matrix['groups']));ck('weight:'+mode,math.isclose(sum(matrix['sample_weight']),1));ck('masks:'+mode,matrix['missing_mask']==[[v is None for v in rr]for rr in matrix['X']]);ck('not_fit:'+mode,not matrix['imputed']and matrix['estimators_fitted']==0 and not matrix['training_authorized']and not matrix['cross_source_comparable'])
            if mode=='point_mixed':ck('3_old9_new',sum(r['target_lower_bound']is None for r in rows)==3 and sum(r['target_lower_bound']is not None for r in rows)==9)
            preflight[mode]=dict(rows=n,source_families=1,features=len(FIELDS20),reading_bounds_not_SD=True,model_fits=0);exports.append((mode,rows,matrix))
        rh=d.batch21_rate_rows('point_mixed','rice_mass_ratio_inspection');ck('RHC24_inspection_only',len(rh)==24 and all(r['source_overlap_pending']and not r['purpose_input_ready']for r in rh))
        try:d.batch21_rate_matrix('point_mixed','rice_mass_ratio_inspection')
        except ValueError as e:ck('RHC_matrix_refused_real_hold','sample_overlap_pending'in str(e))
        else:ck('RHC_matrix_refused_real_hold',False)
        ck('83_candidate_audits_3_manual_links',len(d.batch21_candidate_audits())==83 and len(d.batch21_identity_links())==3)
        oldsummary=json.loads((PARENT.parent/'summary.json').read_text('utf8'));summary=dict(oldsummary)
        for k in list(summary):
            if k.startswith('new_')and isinstance(summary[k],int):summary[k]=0
        summary.update(capacitance_records=1178,numeric_capacitance_values=1166,new_capacitance_reports=36,new_bounded_curve_samples=36,new_numeric_curve_samples=36,new_curve_groups=7,cumulative_bounded_curve_samples=439,cumulative_numeric_curve_samples=429,cumulative_curve_groups=68,curve_sampling_panels=20,reviewed_evidence_units=482,actual_distinct_reviewed_table_keys=468,distinct_database_table_keys=468,extraction_units_v3_count=451,database_extraction_units_v3=451,reviewed_evidence_units_definition='482declaredunits;468actualkeys/451extractionunits;245physicaltablesunchanged. Newtwofiguretranscriptions, notnewphysicaltables.',new_protocol_corrections=3,new_identity_links=3,candidate_identity_audits=83,new_source_scopes=0,new_materials=0,new_material_facts=0,new_numeric_material_facts=0,new_separate_purpose_rows=[3,12,12],new_approximate_conditions_beyond_author_points=9,new_inspection_only_RHC_GCD_points=24,new_formal_cycling_admissions=0,scope_note='83candidate canonicalDOIaudit; threeLP20candidates reconcileexistingcycles, Coffeealreadyapproved/RHCprioroverlapfreeze retained. ThreeRH155/167/141 resolvedasCV5mVs viaactualcaption. 36boundedGCDcaptures; COpointmixed3old+9new, RH24inspectiononly. No new source, cycling endpoint, admission, physicaltable, fit orfullsourcecompletion.')
        for r in spec['manual_links']:ck('linked_candidate_raw_unchanged:'+r['candidate_id'],next(x for x in d.tests()if x['candidate_id']==r['candidate_id'])==next(x for x in old.tests()if x['candidate_id']==r['candidate_id']))
    for mode,rows,m in exports:
        path=OUT/('coffee_KOH_'+mode+'.csv');columns=['observation_id','sample','binder','current_A_g','target_F_g','raw_report','lower_graphical','upper_graphical','source_weight','source_family','source_path','source_sha256','locator']+FIELDS20
        # current_A_g is a matrix field already; keep each CSV column unique.
        columns=list(dict.fromkeys(columns))
        if prepare:
            with path.open('w',encoding='utf-8-sig',newline='')as f:
                w=csv.DictWriter(f,fieldnames=columns);w.writeheader()
                for i,r in enumerate(rows):w.writerow(dict(observation_id=r['observation_id'],sample=r['sample_name'],binder=r['binder'],target_F_g=r['target_value'],raw_report=r['raw_value'],lower_graphical=r['target_lower_bound'],upper_graphical=r['target_upper_bound'],source_weight=m['sample_weight'][i],source_family=m['groups'][i],source_path=r['source_path'],source_sha256=r['source_sha256'],locator=r['locator'],**dict(zip(FIELDS20,m['X'][i]))))
        with path.open(encoding='utf-8-sig',newline='')as f:stored=list(csv.DictReader(f))
        ck('CSV_exact:'+mode,len(stored)==len(rows)and all(float(rr['target_F_g'])==r['target_value']and(rr['lower_graphical']=='')==(r['target_lower_bound']is None)for rr,r in zip(stored,rows)))
    if prepare:
        with(OUT/'RHC_inspection_only.csv').open('w',encoding='utf-8-sig',newline='')as f:
            w=csv.DictWriter(f,fieldnames=['sample','positive_negative_mass_ratio','current_A_g','value_F_g','lower','upper','status']);w.writeheader()
            for r in rh:w.writerow(dict(sample=r['sample_name'],positive_negative_mass_ratio=r['positive_negative_mass_ratio'],current_A_g=r['current_A_g'],value_F_g=r['target_value'],lower=r['target_lower_bound'],upper=r['target_upper_bound'],status='sample_overlap_pending_not_training_ready'))
    # Prefix-equivalence counterfactual catches the actual historical missed-link cause.
    rows=[dict(endpoint_id='plain',doi=None,source_group='10.1021/acsomega.3c09438'),dict(endpoint_id='prefixed',source_group='doi:10.1021/acsomega.3c09438'),dict(endpoint_id='URL',source_group='https://doi.org/10.1021/acsomega.3c09438')];before=json.dumps(rows,sort_keys=True);look=cycling_endpoints_by_doi(rows);ck('prefix_equivalence_and_raw_preservation',len(look['by_doi'][CO])==3 and json.dumps(rows,sort_keys=True)==before)
    try:cycling_endpoints_by_doi([dict(endpoint_id='bad',doi=RH,source_group=CO)])
    except ValueError:ck('conflicting_identity_rejected',True)
    else:ck('conflicting_identity_rejected',False)
    ck('readonly_DB_hash',sha(DB)==digest);report=dict(status='passed',database_sha256=digest,checks=sorted(checks),check_count=len(checks),model_fits=0,new_endpoints=0,new_admissions=0,scientific_goal_complete=False)
    for name,value in [('summary',summary),('verification',report),('model_inputs_preflight',preflight)]:
        if prepare:write(OUT/(name+'.json'),value)
        else:assert json.loads((OUT/(name+'.json')).read_text('utf8'))==value,name
    if(OUT/'merge_manifest.json').exists():
        for r in json.loads((OUT/'merge_manifest.json').read_text('utf8'))['outputs']:assert sha(ROOT/r['path'])==r['sha256'],r['path']
    print(json.dumps({k:v for k,v in report.items()if k!='checks'}))

def chain(prepare=False):
    from verify_five_sources_v20 import chain as historical
    with contextlib.redirect_stdout(io.StringIO()):historical(False)
    from data.cycling_db import open_database
    payload=[]
    with open_literature_database(DB,sha(DB))as d,open_database()as cycle:
        materials={r['material_key']:r for r in d.materials()}
        def add(kind,rows):
            for r in rows:payload.append(dict(kind=kind,group=r.get('source_group')or'doi:'+r['doi']))
        add('capacitance',d.capacitances());add('fact',d.facts());add('registration',d.materials());add('curve',d.sampled_curves());add('cycling',cycle.fetch('all_review').rows)
        for r in d.tests():payload.append(dict(kind='candidate',group=r['record']['source_group']))
        for r in d.connection.execute('select material_key from synthesis_stages_v3'):payload.append(dict(kind='synthesis',group='doi:'+materials[r[0]]['doi']))
        for r in d.connection.execute('select record_json,m.doi from outcome_observations_v3 o left join materials m using(material_key)'):
            rec=json.loads(r[0]);g='doi:'+r[1]if r[1]else rec.get('source_group');assert g;payload.append(dict(kind='response',group=g))
        for t in TARGETS20:add('v20_inputs',d.batch20_inputs(t))
        for purpose in ['coffee_KOH_author_capacity','rice_mass_ratio_inspection']:add('v21_rates',d.batch21_rate_rows('point_mixed',purpose))
        add('v21_protocol',d.batch21_protocol_corrections());add('identity_audit',d.batch21_candidate_audits());add('identity_link',d.batch21_identity_links())
        for r in payload:r['family']=d.isolation_group(r['group'])
        holds={}
        for g in sorted({r['family']for r in payload}):
            test=[r for r in payload if r['family']==g];train=[r for r in payload if r['family']!=g];assert not{r['family']for r in test}&{r['family']for r in train};assert all(d.is_quarantined_source(x,[g])and d.is_quarantined_source(x.removeprefix('doi:'),[g])for x in {r['group']for r in test});holds[g]=dict(sorted(collections.Counter(r['kind']for r in test).items()))
        ck=cycle.by_endpoint('legacy:R104_CY01');rh=cycle.by_endpoint('legacy:SRC123_CY02');rel=[dict(r)for r in cycle.conn.execute('select *from source_relationships where paper_id="SRC123"')];assert ck['eligible']==1 and rh.get('eligible')is None and rel[0]['status']=='sample_overlap_pending';assert len(cycle.fetch('all_review').rows)==286 and len(cycle.reviewed_pending_batch())==37
        report=dict(status='passed',database_sha256=sha(DB),payloads=len(payload),raw_identifiers=len({r['group']for r in payload}),source_families=len(holds),full_quarantine_counts=holds,historical_pinned_v20_chain='passed',current_fixed_pending=37,existing_Coffee_already_admitted=True,RHC_prior_overlap_still_pending=True,new_endpoints=0,new_admissions=0,model_fits=0,scientific_goal_complete=False,payload_definition='Representations andviews, not independent samples; historical additional oldpurposeviews covered by immutablev20chain')
    if prepare:write(OUT/'chain_verification.json',report)
    else:assert json.loads((OUT/'chain_verification.json').read_text('utf8'))==report
    print(json.dumps({k:v for k,v in report.items()if k!='full_quarantine_counts'}))

def seal():
    assert not(OUT/'merge_manifest.json').exists();verify(False);chain(False)
    paths=[p for p in OUT.rglob('*')if p.is_file()]+[ROOT/'data/literature_v21.py',ROOT/'data/cycling_identity.py',ROOT/'tools/extract_identity_rates_v21.py',Path(__file__).resolve()]
    write(OUT/'merge_manifest.json',dict(version='literature_pool_v21',parent_sha256=PSHA,outputs=[dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p),bytes=p.stat().st_size)for p in sorted(paths)],model_fits=0,new_endpoints=0,new_admissions=0,scientific_goal_complete=False))
    write(ROOT/'data/current_literature.json',dict(version='literature_pool_v21',directory=OUT.relative_to(ROOT).as_posix(),database_file=DB.name,sha256=sha(DB),api_module='data.literature_v21',scope='83candidateidentityaudit/3existingcyclelinks; 3CV5mVsprotocolcorrections;36GCDcaptures CO3old+9new andRH24inspectiononly; legacyfreeze retained, no newadmission/fit/fullsourcecompletion.'))
if __name__=='__main__':
    action=sys.argv[1]if len(sys.argv)==2 else''
    if action=='prepare':verify(True);chain(True)
    elif action=='verify':verify(False);chain(False)
    elif action=='seal':seal()
    else:raise SystemExit('prepare/seal once before release; verify readonly')
