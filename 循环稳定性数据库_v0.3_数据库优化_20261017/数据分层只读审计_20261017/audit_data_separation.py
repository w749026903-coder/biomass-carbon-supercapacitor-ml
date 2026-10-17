"""Independent read-only audit; never run migrations, fits, or database writes.

Run with python -B audit_data_separation.py; JSON is printed to stdout.
"""
from pathlib import Path
import collections, copy, csv, datetime, hashlib, json, sqlite3, sys

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'循环稳定性数据库_v0.3_数据库优化_20261017'
R3=BASE/'第三轮_逐条准入闭环_20261017'
R4=BASE/'第四轮_专业复核与训练数据_20261017'

def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def connect(path):
    c=sqlite3.connect(path.as_uri()+'?mode=ro',uri=True);c.row_factory=sqlite3.Row
    c.execute('PRAGMA query_only=ON')
    return c

def audit():
    checks=[];queries={}
    def query(c,name,sql,params=()):
        rows=[dict(r) for r in c.execute(sql,params)]
        queries[name]={'sql':sql,'parameters':list(params),'rows':rows}
        return rows
    def check(name,passed,detail=None):checks.append({'name':name,'passed':bool(passed),'detail':detail})
    protected_databases={str(p.relative_to(ROOT)):sha(p) for p in [R3/'cycling_v0_3r3.sqlite',R4/'cycling_v0_3r4.sqlite']}
    c=connect(R4/'cycling_v0_3r4.sqlite');old=connect(R3/'cycling_v0_3r3.sqlite')
    check('sqlite_integrity',query(c,'integrity','PRAGMA integrity_check')==[{'integrity_check':'ok'}])
    check('foreign_key_integrity',not query(c,'foreign_keys','PRAGMA foreign_key_check'))
    counts={t:c.execute('SELECT COUNT(*) FROM '+t).fetchone()[0] for t in ['papers','source_files','materials','cycling_tests','cycling_endpoints','raw_records','field_evidence','material_observations']}
    check('endpoint_join_no_loss_or_expansion',c.execute('SELECT COUNT(*) FROM endpoint_review').fetchone()[0]==counts['cycling_endpoints'])
    check('material_test_paper_identity_consistent',not query(c,'cross_paper_material',
        'SELECT t.cycle_test_id,t.paper_id,m.paper_id AS material_paper FROM cycling_tests t JOIN materials m USING(material_id) WHERE t.paper_id!=m.paper_id'))
    check('same_material_characterization_not_cross_paired',not query(c,'material_feature_variation',
        'SELECT material_id,COUNT(DISTINCT BET_m2_g) AS nbet,COUNT(DISTINCT total_pore_volume_cm3_g) AS npore FROM endpoint_review GROUP BY material_id HAVING nbet>1 OR npore>1'))
    unchanged=[]
    for t in ['raw_records','papers','materials','cycling_tests','cycling_endpoints','endpoint_features','admissions','review_events','field_evidence','validation_group_assignments','source_files']:
        eq=[tuple(r) for r in old.execute('SELECT * FROM '+t+' ORDER BY rowid')]==[tuple(r) for r in c.execute('SELECT * FROM '+t+' ORDER BY rowid')]
        check('r3_to_r4_unchanged:'+t,eq);unchanged.append(t) if eq else None
    systems=query(c,'systems','SELECT system,method,COUNT(*) AS endpoints FROM endpoint_review GROUP BY system,method')
    metrics=query(c,'metrics','SELECT metric_kind,retention_relation,COUNT(*) AS endpoints FROM endpoint_review GROUP BY metric_kind,retention_relation')
    concentrations=query(c,'concentrations','SELECT concentration_unit,COUNT(*) AS tests FROM cycling_tests GROUP BY concentration_unit')
    source_units=query(c,'current_units','SELECT COUNT(current_density_A_g) AS mass_specific_tests,COUNT(current_density_mA_cm2) AS area_specific_tests,COUNT(scan_rate_mV_s) AS scan_rate_tests FROM cycling_tests')
    profiles=query(c,'profiles','SELECT profile,COUNT(*) AS rows,COUNT(DISTINCT record_id) AS endpoints,COUNT(DISTINCT paper_id) AS papers,COUNT(DISTINCT material_id) AS materials FROM training_rows_r4 GROUP BY profile')
    check('profile_grain_unique',all(r['rows']==r['endpoints'] for r in profiles))
    union=query(c,'union_grain','SELECT COUNT(*) AS rows,COUNT(DISTINCT record_id) AS distinct_endpoints FROM training_rows_r4')[0]
    check('combined_view_is_profile_memberships_not_endpoint_grain',union=={'rows':29,'distinct_endpoints':11},'Intentional nested memberships; never stack as independent rows.')
    admitted=[dict(r) for r in c.execute('SELECT * FROM training_rows_r4')]
    check('no_3E_CV_capacity_or_hybrid_in_any_profile',all(r['system']=='2E_symmetric' and r['method']=='GCD' and r['metric_kind']=='capacitance_retention' for r in admitted))
    check('all_profiles_molar_concentration_only',all(r['concentration_unit'] in ('M','mol/L') for r in admitted))
    check('area_current_not_treated_as_mass_current',all(r['current_density_A_g'] is not None and r['current_density_mA_cm2'] is None for r in admitted))
    check('no_censored_or_missing_target_admitted',all(r['retention_relation'] in ('eq','approx') and r['retention_pct'] is not None for r in admitted))
    check('approximate_only_in_declared_extension',all(r['retention_relation']=='eq' or (r['record_id']=='R020_CY01' and r['profile']=='literature_approx_sensitivity') for r in admitted))
    check('residue_only_in_declared_extensions',all(not r['Si_residue_review_required'] or (r['paper_id']=='R112' and r['profile']!='literature_core7_exact') for r in admitted))
    check('canonical_current_not_fabricated',all(r['canonical_current_A_g'] is None and r['reported_current_A_g']==r['current_density_A_g'] for r in admitted))
    check('strict_current_subset_still_zero',c.execute('SELECT COUNT(*) FROM training_ready_canonical_current').fetchone()[0]==0)
    check('primary_view_fixed_profile',c.execute('SELECT COUNT(*) FROM training_ready').fetchone()[0]==8)
    check('same_paper_not_split_between_groups',not query(c,'group_identity',
        'SELECT paper_id,COUNT(DISTINCT group_id) AS n FROM endpoint_review JOIN validation_group_assignments USING(record_id) GROUP BY paper_id HAVING n>1'))
    plans=json.loads((R4/'modeling/分组验证计划_未拟合.json').read_text('utf-8'))
    bad_splits=[]
    for profile,folds in plans.items():
        mapping={r['record_id']:r for r in admitted if r['profile']==profile}
        for fold in folds:
            for key in ['paper_id','material_id','cycle_test_id','study_group']:
                a={mapping[r][key] for r in fold['train_ids']};b={mapping[r][key] for r in fold['test_ids']}
                if a&b:bad_splits.append([profile,fold['fold'],key])
        check('folds_cover_each_endpoint_once:'+profile,collections.Counter(r for f in folds for r in f['test_ids'])==collections.Counter(mapping.keys()))
    check('no_source_material_test_cross_fold_leakage',not bad_splits,bad_splits)
    effective={r['record_id']:dict(r) for r in c.execute('SELECT * FROM modeling_effective_inputs')}
    ledger_mismatches=[]
    for e in c.execute('SELECT * FROM field_evidence'):
        if e['field_name'] in effective[e['record_id']]:
            actual=effective[e['record_id']][e['field_name']];ledger=json.loads(e['value_json'])
            if ledger!=actual:
                ledger_mismatches.append({'record_id':e['record_id'],'field':e['field_name'],'ledger_value':ledger,'effective_value':actual,'ledger_status':e['status']})
    check('field_ledger_matches_effective_values',not ledger_mismatches,{'fields':len(ledger_mismatches),'endpoints':len({r['record_id'] for r in ledger_mismatches})})
    primary={r['record_id'] for r in admitted if r['profile']=='literature_core7_exact'}
    primary_fields={'cycle_count','current_density_A_g','electrolyte','concentration_value','voltage_lower_V','voltage_upper_V','BET_m2_g'}
    primary_mismatches=[r for r in ledger_mismatches if r['record_id'] in primary and r['field'] in primary_fields]
    legacy_open=query(c,'profile_legacy_open','''SELECT DISTINCT p.record_id,b.code,s.affects_core7 FROM profile_admissions_r4 p
      JOIN record_blockers b USING(record_id) LEFT JOIN blocker_scopes s USING(record_id,code)
      WHERE p.eligible=1 AND b.status='open' AND b.code!='mass_basis_checked' AND COALESCE(s.affects_core7,1)=1''')
    check('new_profile_legacy_blockers_have_structured_per_blocker_dispositions',not legacy_open,
          'Legacy blockers retained; r4 narrative reviews exist but no per-profile per-blocker mapping is implemented.')
    baseline_missing=[r['record_id'] for r in {r['record_id']:r for r in admitted}.values() if r['baseline_json'] is None]
    check('baseline_visible_in_single_training_view',not baseline_missing,baseline_missing)
    sys.path.insert(0,str(R4/'modeling'))
    import prepare_dataset as prep
    csv_disagreements=[]
    for row in profiles:
        profile=row['profile'];dbrows={r['record_id']:r for r in admitted if r['profile']==profile}
        disk={r['record_id']:r for r in json.loads((R4/'exports'/f'{profile}.json').read_text('utf-8'))}
        check('full_json_matches_database:'+profile,dbrows==disk)
        prepared={r['record_id']:r for r in prep.load_ready(profile)}
        with (R4/'exports'/f'{profile}_训练矩阵.csv').open(encoding='utf-8-sig',newline='') as f:matrix=list(csv.DictReader(f))
        for r in matrix:
            for k,v in r.items():
                expected=prepared[r['record_id']][k]
                if v!=('' if expected is None else str(expected)):csv_disagreements.append([profile,r['record_id'],k])
        check('matrix_grain_and_values:'+profile,len(matrix)==len(prepared) and len({r['record_id'] for r in matrix})==len(matrix) and not [d for d in csv_disagreements if d[0]==profile])
    guards={}
    for key,value in [('metric_kind','capacity_retention'),('system','3E'),('method','CV'),('retention_relation','gt'),('concentration_unit','mol/kg'),('retention_pct',None)]:
        test=copy.deepcopy(prep.load_ready()[:1]);test[0][key]=value
        try:prep.validate_rows(test);guards[key]={'rejected':False}
        except ValueError as e:guards[key]={'rejected':True,'message':str(e)}
    check('validator_explicitly_rejects_capacity_target',guards['metric_kind']['rejected'],guards['metric_kind'])
    check('validator_rejects_incompatible_system_method_units_label',all(v['rejected'] for k,v in guards.items() if k!='metric_kind'))
    manifest=json.loads((R4/'merge_manifest.json').read_text('utf-8'))
    artifact_bad=[a['path'] for a in manifest['artifacts'] if not (R4/a['path']).is_file() or sha(R4/a['path'])!=a['sha256']]
    check('r4_manifest_hashes',not artifact_bad,{'verified':len(manifest['artifacts']),'mismatches':artifact_bad})
    parent=json.loads((R4/'protected_parent_fingerprints.json').read_text('utf-8'))
    bad_parent=[p['path'] for p in parent if not Path(p['path']).is_file() or sha(p['path'])!=p['sha256']]
    check('older_deliverables_hashes',not bad_parent,{'checked':len(parent),'mismatches':bad_parent})
    source_files=[dict(r) for r in c.execute('SELECT path,sha256 FROM source_files')]
    bad_sources=[r['path'] for r in source_files if not Path(r['path']).is_file() or sha(r['path'])!=r['sha256']]
    check('original_source_hashes',not bad_sources,{'checked':len(source_files),'mismatches':bad_sources})
    state=(ROOT/'docs/CURRENT_STATE.md').read_text('utf-8')
    readme=(ROOT/'README.md').read_text('utf-8')
    check('root_entry_discloses_r4_separate_profile_revision','第四轮' in state and '第四轮' in readme,
          'Both root entries still say latest independent database is r3. r4 manifest declares proposed contract changes and no scientific merge.')
    candidate=json.loads((ROOT/'同体系文献补充_第二批_20261017/merge_manifest.json').read_text('utf-8'))
    check('candidate_literature_not_marked_admitted',candidate.get('training_admitted')==0 and candidate.get('no_database_writes') is True)
    db_after={str(p.relative_to(ROOT)):sha(p) for p in [R3/'cycling_v0_3r3.sqlite',R4/'cycling_v0_3r4.sqlite']}
    check('audit_database_bytes_unchanged',db_after==protected_databases)
    c.close();old.close()
    return {'executed_at':datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(timespec='seconds'),
            'scope':'126 archived papers/89 endpoint database; r3/r4 comparison; staged literature admission boundary. Not a full new extraction of all papers.',
            'data_modified':False,'research_fit_calls':0,'synthetic_fit_calls':0,'counts':counts,
            'checks':checks,'passed':sum(x['passed'] for x in checks),'failed':sum(not x['passed'] for x in checks),
            'systems':systems,'metrics':metrics,'concentrations':concentrations,'current_units':source_units,
            'profiles':profiles,'combined_profile_view':union,'ledger_mismatches':ledger_mismatches,
            'primary_core_value_ledger_mismatches':primary_mismatches,'legacy_open_with_profile_eligibility':legacy_open,
            'baseline_missing_from_training_view':baseline_missing,'in_memory_guard_checks':guards,
            'database_sha256_before':protected_databases,'database_sha256_after':db_after,
            'queries':queries,'csv_disagreements':csv_disagreements,
            'limitations':['System labels are checked structurally and against selected original source passages; this is not a fresh full-text adjudication of every endpoint.',
                           'A stale null ledger does not prove the effective value is wrong; relevant review events must be consulted.',
                           'Legacy scope blockers can legitimately remain open for stricter models; profile-specific exceptions must not be called universal clearance.']}

if __name__=='__main__':print(json.dumps(audit(),ensure_ascii=False,indent=2,allow_nan=False))
