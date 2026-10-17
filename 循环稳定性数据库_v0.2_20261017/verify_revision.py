"""Reproducible read-only checks and local evidence exports for this revision."""
import ast
import collections
import hashlib
import importlib.util
import json
import pathlib
import sqlite3
import sys

ROOT=pathlib.Path(__file__).resolve().parent
OLD=ROOT.parent/'循环稳定性数据库_v0.1_20261017'
def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def dump(p,value):p.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
def connect(p):
    c=sqlite3.connect(p.as_uri()+'?mode=ro',uri=True);c.row_factory=sqlite3.Row;return c
def records(c,table):return [dict(x) for x in c.execute('SELECT * FROM '+table)]

def main():
    old=connect(OLD/'cycling_v0_1.sqlite');new=connect(ROOT/'cycling_v0_2.sqlite')
    manifest=read(ROOT/'parent_and_source_fingerprints.json')
    checks={
      'parent_database_unchanged':sha(OLD/'cycling_v0_1.sqlite')==manifest['previous_database_sha256'],
      'parent_modeling_files_unchanged':all(sha(OLD/'modeling'/n)==h for n,h in manifest['previous_modeling'].items()),
      '137_original_source_files_unchanged':len(manifest['source_files'])==137 and all(sha(r['path'])==r['sha256'] for r in manifest['source_files']),
      'candidate_input_snapshots_unchanged':all(sha(r['path'])==r['sha256'] for r in records(old,'ingestion_sources')),
      'integrity':new.execute('PRAGMA integrity_check').fetchone()[0]=='ok',
      'foreign_keys':not new.execute('PRAGMA foreign_key_check').fetchall(),
      'ready_view_still_empty':new.execute('SELECT count(*) FROM training_ready').fetchone()[0]==0,
      'no_research_run_directory':not (ROOT/'modeling/research_runs').exists(),
    }
    for table in ['raw_records','papers','source_files','ingestion_sources','materials','cycling_endpoints','field_evidence']:
        checks[table+'_unchanged']=records(old,table)==records(new,table)
    for table in ['issues','material_observations']:
        before=records(old,table);after=records(new,table)
        checks[table+'_old_rows_preserved']=after[:len(before)]==before
    keys={'admissions':'record_id','cycling_tests':'cycle_test_id','endpoint_features':'record_id','source_relationships':'relationship_id'}
    changes=records(new,'revision_changes')
    tracked=collections.defaultdict(list)
    for r in changes:tracked[(r['table_name'],r['row_key'],r['field_name'])].append(r)
    accounted=True
    for table,key in keys.items():
        before={str(r[key]):r for r in records(old,table)}
        for after in records(new,table):
            prior=before[str(after[key])]
            for field,value in after.items():
                if prior[field]!=value:
                    deltas=tracked.get((table,str(after[key]),field),[])
                    state=prior[field]
                    for delta in deltas:
                        accounted &= json.loads(delta['old_json'])==state
                        state=json.loads(delta['new_json'])
                    accounted &= bool(deltas) and state==value
    checks['all_curated_changes_have_old_new_and_reason']=bool(accounted)
    events=records(new,'review_events')
    checks['review_evidence_hashes_match']=all(sha(r['source_path'])==r['source_sha256'] for r in events)
    for p in (ROOT/'modeling').glob('*.py'):ast.parse(p.read_text(encoding='utf-8'))
    checks['python_syntax']=True
    # Verify runtime separation without importing the model libraries into the shared runtime.
    checks['shared_runtime_still_has_no_sklearn_or_xgboost']=all(importlib.util.find_spec(k) is None for k in ['sklearn','xgboost'])
    checks['final_synthetic_interface_suite_passed']=read(ROOT/'modeling/synthetic_interface_checks_v2/summary.json')['passed']
    checks['known_secondary_reuse_group_unchanged']=new.execute("SELECT count(distinct study_group) FROM papers WHERE paper_id IN ('SRC087','R002')").fetchone()[0]==1
    all_rows=records(new,'endpoint_review');main_rows=records(new,'primary_screening_candidates')
    def profile(rows):
        return {'endpoints':len(rows),'provisional_materials':len({r['material_id'] for r in rows}),
                'papers':len({r['paper_id'] for r in rows}),'study_groups':len({r['study_group'] for r in rows})}
    required=['cycle_count','current_density_A_g','electrolyte','concentration_value','concentration_unit','voltage_lower_V','voltage_upper_V']
    full=[r for r in main_rows if all(r[k] is not None for k in required)]
    tiers={'screening_queue_not_admission':profile(main_rows),'all_required_conditions_paired':profile(full),
           'plus_BET_paired':profile([r for r in full if r['BET_m2_g'] is not None]),
           'plus_BET_and_pore_paired':profile([r for r in full if r['BET_m2_g'] is not None and r['total_pore_volume_cm3_g'] is not None])}
    latest={(r['record_id'],r['field_name']):r for r in records(new,'field_review_latest')}
    old_evidence={(r['record_id'],r['field_name']):r for r in records(new,'field_evidence')}
    field_rows=[]
    fields=required+['BET_m2_g','total_pore_volume_cm3_g','N_at_pct','O_at_pct']
    for r in main_rows:
        for field in fields:
            event=latest.get((r['record_id'],field));previous=old_evidence.get((r['record_id'],field))
            evidence=event or previous
            field_rows.append({'record_id':r['record_id'],'paper_id':r['paper_id'],'material_id':r['material_id'],
                'field':field,'current_value':r[field],
                'audit_status':event['decision'] if event else 'inherited_pairing_pending_field_audit',
                'source_path':evidence['source_path'] if evidence else None,'locator':evidence['locator'] if evidence else None,
                'rationale':event['rationale'] if event else 'v0.1 extraction retained; not newly certified by this review'})
    coverage={k:{'paired_endpoints':sum(r[k] is not None for r in main_rows),'queue_endpoints':len(main_rows),
                  'paired_materials':len({r['material_id'] for r in main_rows if r[k] is not None}),
                  'paired_papers':len({r['paper_id'] for r in main_rows if r[k] is not None}),
                  'explicit_batch1_verified_endpoints':sum(x['field']==k and x['audit_status'].startswith('verified') for x in field_rows)} for k in fields}
    counts={t:new.execute('SELECT count(*) FROM '+t).fetchone()[0] for t in ['papers','source_files','materials','cycling_tests','cycling_endpoints','material_observations','field_evidence','issues','admissions','review_events','revision_changes','training_ready']}
    outcomes=dict(new.execute("SELECT status,count(*) FROM admissions WHERE source_checked=1 GROUP BY status").fetchall())
    synthetic={}
    for p in (ROOT/'modeling/synthetic_interface_checks_v2').glob('*/completion.json'):
        synthetic[p.parent.name]=read(p)
    report={'date':'2026-10-17','checks':checks,'all_passed':all(checks.values()),'counts':counts,'all_candidates':profile(all_rows),
            'tiers':tiers,'review_outcomes':outcomes,'feature_coverage_pairing_not_final_admission':coverage,
            'synthetic_checks':synthetic,'database_sha256':sha(ROOT/'cycling_v0_2.sqlite'),
            'research_training_performed':False,
            'limitations':['Paired coverage is not final verified training coverage.','Twelve endpoints are ten provisional materials and ten papers.',
                'No cross-paper independence clearance; no universal silicon threshold or sample adequacy threshold.',
                'No longitudinal experiment history is available for a temporal drift assessment.','No research model comparison or winner is available.']}
    dump(ROOT/'核验与覆盖_v02.json',report)
    dump(ROOT/'字段覆盖与出处.json',field_rows)
    exports=ROOT/'exports';exports.mkdir(exist_ok=True)
    for table in ['endpoint_review','primary_screening_candidates','training_ready','admissions','source_relationships','review_events','field_review_latest','revision_changes']:
        dump(exports/(table+'.json'),records(new,table))
    (ROOT/'schema_v02.sql').write_text('\n'.join(r[0]+';' for r in new.execute("SELECT sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY type,name")),encoding='utf-8')
    # These SQL outputs were actually executed above the notebook serialization.
    queries=[
        "SELECT 'candidate_endpoints' AS kind,count(*) AS n FROM endpoint_review UNION ALL SELECT 'training_ready',count(*) FROM training_ready",
        "SELECT status,count(*) AS endpoints FROM admissions WHERE source_checked=1 GROUP BY status",
        "SELECT p.paper_id,r.record_id,r.field_name,r.decision,r.locator FROM field_review_latest r JOIN raw_records p ON p.record_id=r.record_id WHERE r.decision IN ('conflict_text_vs_cycle_inset','requires_missing_SI','material_scope_review') ORDER BY r.record_id,r.field_name",
        "SELECT relationship_id,paper_id,related_doi,relationship,status,note FROM source_relationships ORDER BY relationship_id"]
    cells=[{'cell_type':'markdown','metadata':{},'source':['# v0.2 首批核查\n只读SQL；当前0条正式训练记录。配对覆盖不等于准入。执行日期2026-10-17。']}]
    setup="import pathlib, sqlite3\n# Open the notebook from its containing v0.2 directory.\ndb = pathlib.Path('cycling_v0_2.sqlite').resolve()\nconn = sqlite3.connect(db.as_uri()+'?mode=ro', uri=True)\nconn.row_factory = sqlite3.Row\n"
    cells.append({'cell_type':'code','metadata':{},'source':setup.splitlines(keepends=True),'execution_count':1,'outputs':[]})
    for i,sql in enumerate(queries,2):
        result=[dict(x) for x in new.execute(sql)]
        source='sql = '+repr(sql)+'\nrows = [dict(x) for x in conn.execute(sql)]\nprint(rows)'
        cells.append({'cell_type':'code','metadata':{},'source':source.splitlines(keepends=True),'execution_count':i,
                      'outputs':[{'output_type':'stream','name':'stdout','text':[repr(result)+'\n']}]})
    dump(ROOT/'首批核查复核.ipynb',{'nbformat':4,'nbformat_minor':5,'metadata':{'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'}},'cells':cells})
    print(json.dumps({'all_passed':report['all_passed'],'checks':len(checks),'counts':counts,'tiers':tiers,'review_outcomes':outcomes},ensure_ascii=False,indent=2))
    if not report['all_passed']:raise AssertionError('Review checks failed')

if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
