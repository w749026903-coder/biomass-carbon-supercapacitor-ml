"""Read-only v0.8 audit; --write-report saves only this release's report/exports."""
from __future__ import annotations
import collections, csv, hashlib, importlib.util, json, pathlib, re, sqlite3, sys, zipfile
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import build_incoming_release_20261020 as build
BATCH=build.BATCH;OUT=build.RELEASE;PARENT=build.PARENT

def load_module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m

def table_digest(c,name):
    # Canonical row multiset, including duplicates, independent of physical SQLite layout.
    quoted='"'+name.replace('"','""')+'"'
    def encode(row):return json.dumps([{'blob_hex':v.hex()} if isinstance(v,bytes) else v for v in row],ensure_ascii=False,separators=(',',':')).encode()
    h=hashlib.sha256()
    rows=sorted(encode(r) for r in c.execute('select * from '+quoted))
    for x in rows:h.update(len(x).to_bytes(8,'big'));h.update(x)
    return {'rows':len(rows),'sha256':h.hexdigest()}

def verify(write=False):
    checks=[]
    def check(name,ok):
        if not ok:raise AssertionError(name)
        checks.append(name)
    check('parent_database_hash',build.sha(PARENT/'cycling_v0_7.sqlite')==build.PARENT_SHA)
    # This inherited verifier checks sealed historical outputs and source protection hashes.
    old=load_module('inherited_v07_verifier',ROOT/'tools/verify_expansion_v07_20261018.py').verify()
    check('inherited_v07_verification',old['all_checks_passed'])
    p=sqlite3.connect((PARENT/'cycling_v0_7.sqlite').as_uri()+'?mode=ro',uri=True)
    c=sqlite3.connect((OUT/'cycling_v0_8.sqlite').as_uri()+'?mode=ro',uri=True)
    check('integrity',c.execute('PRAGMA integrity_check').fetchone()[0]=='ok')
    check('foreign_keys',not c.execute('PRAGMA foreign_key_check').fetchall())
    historical={}
    tables=[r[0] for r in p.execute("select name from sqlite_master where type='table' order by name")]
    for name in tables:
        a=table_digest(p,name);b=table_digest(c,name)
        check('inherited_table:'+name,a==b);historical[name]=a
    inputs=build.read('input_manifest.json')
    for row in inputs['input_files']:check('external_original:'+row['path'],build.sha(row['path'])==row['sha256'] and pathlib.Path(row['path']).stat().st_size==row['bytes'])
    idx=build.read('intake_index.json');sources=build.read('source_reviews.json');tests=build.read('normalized_tests.json')
    for r in idx:
        file=ROOT/r['repository_path'];check('canonical_pdf:'+r['document_id'],build.sha(file)==r['sha256'] and file.stat().st_size==r['bytes'])
    for r in build.read('evidence_image_manifest.json'):
        check('retained_original_render:'+r['path'],build.sha(ROOT/r['path'])==r['sha256'] and r['source_sha256']==next(d['sha256'] for d in idx if d['document_id']==r['document_id']))
    # ZIP bytes and all canonical member contents are covered by the original+PDF fingerprints.
    # Re-read members too, so path/member mistakes in intake cannot silently pass.
    manifest_occ=inputs.get('PDF_occurrences',inputs.get('pdf_occurrences',[]))
    for inp in inputs['input_files']:
        if not inp['path'].lower().endswith('.zip'):continue
        with zipfile.ZipFile(inp['path']) as z:
            members=[i for i in z.infolist() if not i.is_dir() and i.filename.lower().endswith('.pdf')]
            check('zip_member_count',len(members)==48)
            hashes={hashlib.sha256(z.read(i)).hexdigest() for i in members}
            check('zip_member_contents',hashes<={r['sha256'] for r in idx})
    check('scope_classified_all',len(idx)==len(sources)==80 and len({r['document_id'] for r in sources})==80)
    check('own_test_count',len(tests)==82 and len({r['record_id'] for r in tests})==82)
    check('candidate_archive_unchanged',all(not r['archived'] and not r['training_eligible'] for r in sources))
    check('source_group_integrity',all(r['source_group']==next(s['source_group'] for s in sources if s['document_id']==r['document_id']) for r in tests))
    check('pending_not_admitted',all(r['review_status']=='approved_for_reported_protocol' for r in tests if r['eligible']))
    check('null_current_not_zero',next(r for r in tests if r['record_id']=='ADD_080_T01')['reported_current_A_g'] is None)
    check('configuration_conflict_frozen',next(r for r in tests if r['record_id']=='ADD_052_T01')['system']=='configuration_unresolved')
    check('ASC_current_conflict_frozen',all(r['reported_current_A_g'] is None and {x['value'] for x in r['extra_observations'] if x['field']=='reported_current_A_g'}>={2,10} for r in tests if r['record_id'] in ['ADD_025_T02','ADD_025_T03']))
    check('nonexact_3E_not_main',not next(r for r in tests if r['record_id']=='ADD_034_T01')['eligible'])
    check('003_3E_device_separated',next(r for r in tests if r['record_id']=='ADD_003_T01')['retention_pct']==93.6 and next(r for r in tests if r['record_id']=='ADD_003_T02')['retention_pct']==80.9)
    check('027_positive_window',next(r for r in tests if r['record_id']=='ADD_027_T01')['cycle_voltage_lower_V']==-0.2)
    check('activated_retention_preserved',next(r for r in tests if r['record_id']=='ADD_027_T01')['retention_pct']==109.2)
    check('no_SSRN_invented_DOI',all(s['doi'] is None for s in sources if s['document_id'] in ['ADD_029','ADD_050','ADD_073','ADD_075']))
    check('070_review_not_experiment',next(s for s in sources if s['document_id']=='ADD_070')['publication_type']!='original_experiment')
    check('no_duplicate_old_3E_reintake',not any(r['document_id'] in ['ADD_006','ADD_033'] and r['system']=='3E' for r in tests))
    # All mapped evidence points at this document's actual page range.
    check('observation_document_binding',not c.execute('select 1 from incoming_observation_pages_v08 p join incoming_observations_v08 o using(observation_id) join incoming_tests_v08 t using(record_id) where p.document_id!=t.document_id').fetchone())
    cohort={};m=load_module('v08_verification_api',OUT/'ml_data.py');parentm=load_module('v07_verification_api',PARENT/'ml_data.py')
    with m.Database() as db,parentm.Database() as parent:
        for profile,expected in [('reported_3e',(30,22)),('reported_2e',(20,17)),('reported_2e_residue',(22,18)),('reported_2e_approx',(23,19))]:
            ds=db.fetch(profile);matrix=ds.feature_matrix();oldrows=parent.fetch(profile).rows
            check(profile+':counts',(len(ds.rows),len(set(matrix['groups'])))==expected)
            current={r['endpoint_id']:r for r in ds.rows}
            for r in oldrows:check(profile+':inherited_row:'+r['endpoint_id'],all(current[r['endpoint_id']][k]==v for k,v in r.items() if k!='source_weight'))
            weights=collections.defaultdict(float)
            for r in ds.rows:weights[r['source_group']]+=r['source_weight']
            check(profile+':source_weights',all(abs(v-1)<1e-12 for v in weights.values()))
            keys=[(r['source_group'],r['system'],re.sub(r'[^a-z0-9]','',str(r['sample_name']).lower()),r['cycle_count'],r['reported_current_A_g'],r['retention_pct'],r['electrolyte'],r['concentration_mol_L'],r['cycle_voltage_lower_V'],r['cycle_voltage_upper_V'],r.get('reference_electrode')) for r in ds.rows]
            check(profile+':no_duplicate_tests',len(keys)==len(set(keys)))
            seen=[]
            for fold in ds.source_folds(len(weights)):
                a,b=fold['train'],fold['test'];seen+=b
                check(profile+':source_fold:'+str(len(seen)),{ds.rows[i]['source_group'] for i in a}.isdisjoint(ds.rows[i]['source_group'] for i in b))
            check(profile+':each_held_once',sorted(seen)==list(range(len(ds.rows))))
            check(profile+':no_fit',matrix['training_authorized'] is False)
            if write:
                build.write(OUT/(profile+'_inputs.json'),{'rows':ds.rows,'matrix':matrix,'fingerprint':ds.fingerprint(),'source_folds':ds.source_folds(len(weights))})
                build.dump_csv(OUT/(profile+'_inputs.csv'),ds.rows,['endpoint_id','source_group','source_year','sample_name',*ds.features,'retention_pct','retention_relation','source_weight'])
            else:
                export=json.loads((OUT/(profile+'_inputs.json')).read_text('utf-8'));check(profile+':export_matches',export['matrix']==matrix and export['fingerprint']==ds.fingerprint())
            with (OUT/(profile+'_inputs.csv')).open(encoding='utf-8-sig',newline='') as f:csvrows=list(csv.DictReader(f))
            check(profile+':CSV_matches',len(csvrows)==len(ds.rows) and all(a['endpoint_id']==b['endpoint_id'] and float(a['retention_pct'])==b['retention_pct'] for a,b in zip(csvrows,ds.rows)))
            cohort[profile]={'records':len(ds.rows),'source_groups':len(weights),'features':len(ds.features),'fingerprint':ds.fingerprint()}
        check('incoming_review_excludes_training_matrix',len(db.fetch('incoming_review').rows)==82)
        try:db.fetch('incoming_review').feature_matrix()
        except m.DataNotReady:checks.append('review_matrix_rejected')
        else:raise AssertionError('Review matrix unexpectedly allowed')
        for field,value in [('metric_kind','coulombic_efficiency'),('system','2E_symmetric'),('BET_m2_g',None),('reported_current_A_g',0)]:
            ds=db.fetch();ds.rows[0][field]=value
            try:ds.feature_matrix()
            except m.DataNotReady:checks.append('invalid_matrix_rejected:'+field)
            else:raise AssertionError('Bad matrix was accepted: '+field)
        check('incoming_search',bool(db.search_incoming('cycling')))
        check('source_protection_3214_or_more',old['parent_protected_file_count']>=3214)
        check('old_freezes_unchanged',db.conn.execute('select count(*) from field_selection_history').fetchone()[0]==p.execute('select count(*) from field_selection_history').fetchone()[0])
    # Browser catalog hrefs must point at real directly readable PDFs, including all reused paths.
    text=(BATCH/'文献分类入口.html').read_text('utf-8')
    check('catalog_all_direct_originals',text.count('打开原文PDF')==80 and all((ROOT/s['storage_path']).is_file() for s in sources))
    result={'all_technical_checks_passed':True,'check_count':len(checks),'inherited_v07_check_counts':{k:v for k,v in old.items() if k in ['parent_check_count','new_check_count','parent_protected_file_count']},
            'external_input_files_unchanged':33,'original_PDF_contents_verified':80,'inherited_table_count':len(historical),'historical_tables':historical,
            'cohorts':cohort,'new_explicit_approvals':18,'pending_or_outside_observations':64,'all_records_scientifically_admitted':False,
            'research_training_runs':0,'scientific_limits':'Technical integrity does not resolve pending SI, scope, preprint or conflicting scientific claims. Provided-main bounded review only.','checks':checks}
    p.close();c.close()
    if write:build.write(OUT/'最终核验.json',result)
    return result

if __name__=='__main__':
    result=verify('--write-report' in sys.argv)
    print(json.dumps({k:v for k,v in result.items() if k not in ['checks','historical_tables']},ensure_ascii=False,indent=2))
