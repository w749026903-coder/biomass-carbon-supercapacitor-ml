"""One-use source-metadata/measurement-QA release; no new admission or ML fit."""
from pathlib import Path
from contextlib import closing
import collections, copy, hashlib, importlib.util, json, math, sqlite3, sys
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'tools')]
PARENT=ROOT/'循环稳定性数据库_v0.17_原图标签补正_20261024'
OUT=ROOT/'循环稳定性数据库_v0.18_来源题录与质量核查_20261024'
B=ROOT/'持续补正_v017_20261024/post_v017_figure_review'
DB=OUT/'cycling_v0_18.sqlite'
AC='incoming:ADD_073_T01';DS='legacy:SRC121_CY01'

def read(p):return json.loads(Path(p).read_text('utf8'))
def write(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n','utf8')
def dump(v):return json.dumps(v,ensure_ascii=False,sort_keys=True)
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def module(path,name):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m
def ev(path,loc,text):return dict(path=path.relative_to(ROOT).as_posix(),sha256=sha(path),locator=loc,evidence_excerpt=text)

def build():
    if DB.exists() or (OUT/'merge_manifest.json').exists():raise FileExistsError('Existing v0.18 preserved.')
    pointer=read(ROOT/'data/current_database.json');assert pointer['version_directory']==PARENT.name
    assert sha(PARENT/pointer['database_file'])==pointer['sha256']
    api=module(PARENT/'ml_data.py','_v18_build_parent')
    with api.Database() as db:
        rows={r['endpoint_id']:r for r in db.fetch('all_review').rows};contract=copy.deepcopy(db.contract)
        reviews={r['endpoint_id']:r for r in db.reviewed_pending_batch(True)}
    changes=[]
    ssrn=read(B/'SSRN_bibliographic_review.json');unit=read(B/'DSAC_BET_unit_reproduction.json');authority=read(B/'IUPAC_primary_review.json')
    se=ev(B/'SSRN_bibliographic_review.json','Primary SSRN bibliographic facts read2026-10-24','SSRN6799753 posted20May2026,52pages; own preprint DOI10.2139/ssrn.6799753. Not formal numerical verification.')
    se['primary_url']=ssrn['primary_url'];se['reading_kind']='reviewed_primary_bibliographic_metadata'
    de=ev(B/'DSAC_BET_unit_reproduction.json','Raw7-point mass/volume ordinate transform and author report reproduction','Sample0.0232g,N2 MW28.013g/mol; conventional STP assumption22414cc/mol reproduces slope/intercept/area. No replacement selected.')
    ie=ev(B/'IUPAC_primary_review.json','IUPAC2015 section5.2.2, publisher search-rendered passage','IUPAC lists3 criteria; all78 supplied ranges fail the3-condition conjunction. RSC pressure20% condition is separate. Missing low-pressure data not reconstructed.')
    ie['primary_url']=authority['primary_url'];ie['reading_kind']='reviewed_primary_method_passage'
    def add(key,field,value,evidence,reason):
        before=rows[key].get(field);assert before is None,(key,field,before)
        changes.append(dict(endpoint_id=key,field_name=field,before=before,after=value,operation='fill_qualified_evidence',
                            evidence=[dict(e,fields=[field]) for e in evidence],reason=reason))
    add(AC,'source_year',2026,[se],'Own SSRN posting year explicitly verified; not file creation or formal numeric-data approval.')
    add(AC,'doi','10.2139/ssrn.6799753',[se],'Actual DOI displayed by the primary SSRN page; do not relabel preprint92.1% as formally checked data.')
    add(AC,'source_document_version_v18',dict(kind='SSRN_preprint',posted_date='2026-05-20',year_basis='preprint_posting',
        formal_candidate_doi='10.1016/j.ultsonch.2026.108104',formal_own_control_numbers_verified=False,
        source_group_migrated=False),[se],'Keep document source group and preprint/formal roles distinct; no additional independent source count.')
    add(DS,'BET_unit_reproduction_v18',{k:unit[k] for k in ['reported_sample_mass_g','reported_N2_molecular_mass_g_mol',
        'reported_cross_section_nm2','diagnostic_assumed_standard_molar_volume_cm3_mol','assumption_status',
        'recomputed_slope','recomputed_intercept','recomputed_C','recomputed_area_m2_g','replacement_BET_selected']},[de],
        'Measurement QA only. Reproducing the report does not validate its fit or replace reported BET1374.')
    add(DS,'BET_method_quality_v18',dict(author_reported_fit_positive_C_pass=False,IUPAC_2015_criteria=3,
        passing_supplied_ranges_IUPAC3=0,RSC_additional_pressure_criterion_separate=True,
        valid_reanalysis_obtained=False,measurement_quality_resolved=False,universal_C_reporting_gate=False),[de,ie],
        'Known negativeC is now method-source corroborated; no claim that all microporous BET is geometric area, and no blanket C-reporting requirement.')
    a=copy.deepcopy(reviews[AC]);a.update(review_version='v0.18',disposition='partly_resolved_preprint_bibliography_formal_control_pending',
        open_issues=['formal_version_own_AC700_numeric_comparison'],approved_profiles=[],
        reason='预印本发布年份2026和自身SSRN DOI已核实补录；正式DOI已知，但正式正文中无Au AC700数值/协议仍未对照，92.1%保持冻结。不得把OA或题录当全文。',
        resolution=a.get('resolution',[])+['SSRN6799753 posting date20May2026 and DOI directly verified.','Only bibliographic fields filled; existing study group, target and eligibility unchanged.'])
    d=copy.deepcopy(reviews[DS]);d.update(review_version='v0.18',disposition='pending_cycle_binding_and_known_BET_fit_quality',
        open_issues=['cycling_window_reference_scale_binding','known_negative_BET_C_requires_valid_reanalysis_or_additional_raw_data'],approved_profiles=[],
        reason='已从原始吸附点复现仪器面积/斜率/截距及负C；提供范围无通过IUPAC三项条件的区间。保留1374报告值和质量注记，仍需有效重分析/补充原始点及循环条件绑定，不另选拟合强行准入。',
        resolution=d.get('resolution',[])+['Raw sample-volume to adsorbate-mass BET ordinate reproduced with declared conventional STP assumption.','IUPAC3 vs RSC4 criteria separated; known failed fit is not just an unreported-C field.'])
    contract.update(version='v0.18',database_file=DB.name,parent_directory=PARENT.name,parent_database_sha256=pointer['sha256'],
        storage_layout='Small immutable-parent source-metadata and measurement-QA delta; current membership unchanged.',model_fits=0,
        field_semantics_v18={'source_year':'Source preprint posting year, not automatic journal approval.',
            'doi':'Own source document SSRN DOI; formal candidate retained separately.',
            'source_groups':'Document group and all preprint/formal same-study relationships unchanged; no split.',
            'BET_QA':'Recomputed measurement diagnostics only, never additional default predictors or replacement area.',
            'source_aliases':'Metadata lookup only; native full-corpus DOI index is not migrated in this release.'})
    write(OUT/'data_contract.json',contract);write(B/'release_parent_pointer.json',pointer)
    with closing(sqlite3.connect(DB)) as c:
        c.execute('pragma foreign_keys=on')
        c.executescript('''create table record_keys_v18(endpoint_id text primary key);
        create table field_changes_v18(endpoint_id text references record_keys_v18,field_name text,before_json text,after_json text,operation text,evidence_json text,reason text,primary key(endpoint_id,field_name));
        create table reviews_v18(endpoint_id text primary key references record_keys_v18,review_json text);
        create table source_aliases_v18(endpoint_id text references record_keys_v18,doi text,source_group text,relation text,document_version text,primary key(endpoint_id,doi));''')
        c.executemany('insert into record_keys_v18 values(?)',[(k,) for k in rows])
        c.executemany('insert into field_changes_v18 values(?,?,?,?,?,?,?)',[(x['endpoint_id'],x['field_name'],dump(x['before']),dump(x['after']),x['operation'],dump(x['evidence']),x['reason']) for x in changes])
        c.executemany('insert into reviews_v18 values(?,?)',[(r['endpoint_id'],dump(r)) for r in [a,d]])
        c.executemany('insert into source_aliases_v18 values(?,?,?,?,?)',[(AC,'10.2139/ssrn.6799753',rows[AC]['source_group'],'actual_source_document','SSRN_preprint'),
            (AC,'10.1016/j.ultsonch.2026.108104',rows[AC]['source_group'],'formal_version_candidate_numeric_unverified','formal_metadata_only')]);c.commit()
    write(B/'field_changes_v018.json',changes);write(B/'reviewed_cases_v018.json',[a,d])
    print(dump(dict(fills=len(changes),new_admissions=0,pending=38)))

def verify():
    from training_input_quality import assess
    checks=[];sealed=(OUT/'merge_manifest.json').exists()
    def check(name,value):
        if not value:raise AssertionError(name)
        checks.append(name)
    def emit(path,value):
        if sealed:
            if read(path)!=value:raise AssertionError('Sealed report differs: '+str(path))
        else:write(path,value)
    manifest=read(PARENT/'merge_manifest.json')
    for item in manifest['outputs']:check('parent_sealed_'+item['path'],sha(ROOT/item['path'])==item['sha256'])
    protected={}
    for mp in [ROOT/'模型v1.0_来源留出训练_20261022/run_manifest.json',ROOT/'模型逐项优化_v1.1_20261022/run_manifest.json']:
        for section in ['outputs','protected_files','protected_sources']:
            vals=read(mp).get(section,[])
            if isinstance(vals,dict):vals=[dict(path=p,sha256=h) for p,h in vals.items()]
            for item in vals:
                if isinstance(item,dict) and 'path' in item and 'sha256' in item:
                    path=Path(item['path']);path=path if path.is_absolute() else ROOT/path
                    check('old_model_or_source_'+str(path),sha(path)==item['sha256']);protected[str(path)]=item['sha256']
    for name in ['protected_sources.json','review_evidence_hashes.json']:
        for p,h in read(ROOT/'已有文献表图与41条复核_20261024'/name).items():
            path=Path(p);path=path if path.is_absolute() else ROOT/path
            check('old_review_original_'+p,sha(path)==h);protected[str(path)]=h
    with closing(sqlite3.connect(DB.as_uri()+'?mode=ro',uri=True)) as c:
        check('sqlite_integrity',c.execute('pragma integrity_check').fetchone()[0]=='ok')
        check('foreign_keys',not c.execute('pragma foreign_key_check').fetchall())
    oldapi=module(PARENT/'ml_data.py','_v18_verify_parent');api=module(OUT/'ml_data.py','_v18_verify_current')
    changes=read(B/'field_changes_v018.json');lookup={(r['endpoint_id'],r['field_name']):r for r in changes}
    readiness={};cohorts={}
    with oldapi.Database() as old,api.Database() as db:
        a={r['endpoint_id']:r for r in old.fetch('all_review').rows};b={r['endpoint_id']:r for r in db.fetch('all_review').rows}
        check('all277_retained',len(b)==277 and set(a)==set(b))
        for key in sorted(a):
            for field,value in sorted(a[key].items()):
                if (key,field) in lookup:check('before_'+key+field,lookup[key,field]['before']==value)
                else:check('old_value_'+key+field,b[key].get(field)==value)
            if key in db.reviews_v18:check('hold_chain_'+key,db.holds(key)['previous_holds']==old.holds(key))
            else:check('unchanged_hold_'+key,db.holds(key)==old.holds(key))
        for c in changes:
            key,field=c['endpoint_id'],c['field_name']
            check('fill_'+key+field,c['before'] is None and b[key][field]==c['after'])
            check('selected_evidence_'+key+field,any(e.get('review_version')=='v0.18' and e.get('currently_selected')==1 for e in db.evidence(key,field)))
            for e in c['evidence']:check('hash_'+key+field+e['locator'],field in e['fields'] and sha(ROOT/e['path'])==e['sha256'])
        for p in db.contract['profiles']:
            x,y=old.fetch(p),db.fetch(p)
            check('membership_core_label_groups_weights_'+p,x.feature_matrix()==y.feature_matrix())
            check('optional_materials_'+p,old.material_matrix(p)==db.material_matrix(p))
            check('method_materials_'+p,old.method_specific_material_matrix(p)==db.method_specific_material_matrix(p))
            readiness[p]=assess(y);cohorts[p]=dict(records=len(y.rows),source_groups=len({r['source_group'] for r in y.rows}))
        check('unchanged_whitelist_and_profiles',db.contract['extra_material_feature_whitelist']==old.contract['extra_material_feature_whitelist'] and db.contract['profiles']==old.contract['profiles'])
        check('AC_source_is_preprint',b[AC]['doi']=='10.2139/ssrn.6799753' and b[AC]['source_year']==2026 and b[AC]['source_document_version_v18']['kind']=='SSRN_preprint')
        check('AC_group_not_migrated',b[AC]['source_group']==a[AC]['source_group'] and b[AC]['source_group'].startswith('document:'))
        check('AC_not_auto_admitted',not b[AC]['admission_profiles_v17'] and b[AC]['eligible']==0 and db.admission_checks(AC,'reported_3e')[0]['status']=='not_approved')
        check('AC_target_BET_unchanged',b[AC]['retention_pct']==a[AC]['retention_pct']==92.1 and b[AC]['BET_m2_g']==2142)
        check('AC_year_filter_after_fill',AC in {r['endpoint_id'] for r in db.fetch('all_review',year_min=2026).rows} and AC not in {r['endpoint_id'] for r in db.fetch('all_review',year_max=2025).rows})
        check('old_review_year_members_added_only_AC',{r['endpoint_id'] for r in db.fetch('all_review',year_min=2026).rows}=={r['endpoint_id'] for r in old.fetch('all_review',year_min=2026).rows}|{AC})
        sums=collections.defaultdict(float)
        for r in db.fetch('all_review',year_min=2026).rows:sums[r['source_group']]+=r['source_weight']
        check('filtered_group_weights',all(abs(w-1)<1e-10 for w in sums.values()))
        aliases=db.source_aliases();check('two_aliases_one_study',len(aliases)==2 and {r['source_group'] for r in aliases}=={a[AC]['source_group']})
        check('DSAC_not_replaced',b[DS]['BET_m2_g']==a[DS]['BET_m2_g']==1374 and not b[DS]['BET_unit_reproduction_v18']['replacement_BET_selected'])
        check('no_universal_C_gate',b[DS]['BET_method_quality_v18']['universal_C_reporting_gate'] is False and len(db.fetch().rows)==43)
        check('DSAC_remains_pending',not b[DS]['admission_profiles_v17'] and len(db.holds(DS)['open_issues'])==2)
        pending=db.reviewed_pending_batch();check('38pending24groups',len(pending)==38 and len({r['source_group'] for r in pending})==24)
        check('41audit_cases_preserved',len(db.reviewed_pending_batch(True))==41)
        check('existing_native_search',bool(db.search_native('cycling',limit=2)))
        check('expanded_optional327of774',sum(r.get(f) is not None for r in db.fetch().rows for f in db.contract['model_material_features'])==327)
        for field,value in [('baseline_reference',None),('reported_current_A_g',None),('retention_relation','gt')]:
            ds=db.fetch();ds.rows=copy.deepcopy(ds.rows);ds.rows[0][field]=value
            try:ds.feature_matrix()
            except api.DataNotReady:check('reject_'+field,True)
            else:raise AssertionError('Accepted invalid input: '+field)
    for name in ['related_data_discovery.json','title_data_discovery.json']:
        d=read(B/name)
        for r in d['rows']:
            if r.get('path'):check('discovery_hash_'+name+r['identifier'],sha(ROOT/r['path'])==r['sha256'])
    d=read(B/'related_data_discovery.json')
    check('DOI_zero_hits_not_absence',sum(r.get('returned',0)>0 and r['kind']=='article_relation' for r in d['rows'])==0 and any(r.get('returned')==1 and r['kind']=='known_dataset_control' for r in d['rows']))
    title=read(B/'title_data_discovery.json');found={m['doi'] for r in title['rows'] for m in r.get('matches',[])}
    check('title_hits_only_known_dataset_versions',found=={'10.17632/f7m96z8dgm','10.17632/f7m96z8dgm.1'})
    unit=read(B/'DSAC_BET_unit_reproduction.json');check('BET_slope_intercept_C_area_reproduction',abs(unit['recomputed_slope']-2.57316)<.0001 and abs(unit['recomputed_intercept']+.0399293)<.00001 and abs(unit['recomputed_C']+63.443)<.01 and abs(unit['recomputed_area_m2_g']-1374.73)<.02)
    emit(B/'remaining_pending_records_v018.json',pending)
    emit(OUT/'training_readiness.json',readiness)
    emit(B/'release_statistics_v018.json',dict(field_fills=5,affected_records=2,new_admissions=0,current_pending=38,pending_source_groups=24,
        core_bibliographic_fills=['source_year','doi'],scientific_target_and_core_predictor_values_changed=0,cohorts=cohorts,model_fits=0,
        DOI_relation_queries=25,title_queries=26,new_datasets=0,all_scientific_questions_resolved=False))
    checks.sort()
    emit(OUT/'verification.json',dict(passed=True,check_count=len(checks),checks=checks,protected_old_payloads=len(protected),model_fits=0))
    if sealed:
        for x in read(OUT/'merge_manifest.json')['outputs']:assert sha(ROOT/x['path'])==x['sha256'],x['path']
    print(dump(dict(passed=True,checks=len(checks),new_admissions=0,pending=38,sealed_payloads_verified=sealed)))

def seal():
    if (OUT/'merge_manifest.json').exists():raise FileExistsError('Already sealed; verify instead.')
    assert read(OUT/'verification.json')['passed'] and read(ROOT/'data/current_database.json')==read(B/'release_parent_pointer.json')
    for p in [OUT/'README.md',B/'README.md',B/'review_log.json']:assert p.is_file(),p
    paths=[p for p in B.rglob('*') if p.is_file()]+[p for p in OUT.iterdir() if p.is_file()]
    paths += [Path(__file__),ROOT/'tools/discover_related_data_v018.py']
    outputs=[dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p),bytes=p.stat().st_size) for p in sorted(paths)]
    write(OUT/'merge_manifest.json',dict(schema='source_bibliography_measurement_QA_v1',version='v0.18',database_sha256=sha(DB),
        parent_database_sha256=read(B/'release_parent_pointer.json')['sha256'],ready_for_merge=True,ready_for_training_inputs=True,
        all_records_admitted=False,all_scientific_questions_resolved=False,new_admissions=0,current_pending=38,model_fits=0,
        cohorts=read(B/'release_statistics_v018.json')['cohorts'],outputs=outputs))
    write(ROOT/'data/current_database.json',dict(version_directory=OUT.name,database_file=DB.name,sha256=sha(DB),
        parent_database_file=(PARENT/'cycling_v0_17.sqlite').relative_to(ROOT).as_posix(),default_profile='reported_3e',
        stage='qualified_source_bibliography_and_measurement_QA',ready_for_training_inputs=True,research_training_authorized=False,all_records_admitted=False))
    print(dump(dict(sealed_outputs=len(outputs),database_sha256=sha(DB))))

if __name__=='__main__':{'build':build,'verify':verify,'seal':seal}[sys.argv[1]]()
