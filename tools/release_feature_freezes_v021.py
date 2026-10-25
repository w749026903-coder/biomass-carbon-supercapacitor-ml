"""Forward-only null selection for newly verified table/figure conflicts. No model fits."""
from pathlib import Path
from contextlib import closing
import hashlib,importlib.util,json,sqlite3,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tools'))
from extract_onion_composite_v8 import sha,write,ro
OUT=ROOT/'循环稳定性数据库_v0.21_图表冲突特征冻结_20261026';DB=OUT/'cycling_v0_21.sqlite'
PARENT=ROOT/'循环稳定性数据库_v0.20_新增来源准入_20261025';PARENT_SHA='09160929dbe487adc989edc92b0abb2ca4871d48b6b20aea0c688582c190694e'
LIT=ROOT/'文献全量利用复核_20261026/批次09_藻类与杜仲木系统系列';DOI='10.3390/molecules31132329'
def load(folder,name):
    if name not in sys.modules:
        spec=importlib.util.spec_from_file_location(name,folder/'ml_data.py');m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m)
    return sys.modules[name]

def build():
    if DB.exists() or (OUT/'merge_manifest.json').exists():raise FileExistsError('Do not overwrite old draft/release.')
    assert sha(PARENT/'cycling_v0_20.sqlite')==PARENT_SHA
    conflicts=json.loads((LIT/'legacy_feature_conflicts.json').read_text('utf8'));assert len(conflicts)==15 and len({r['endpoint_id'] for r in conflicts})==5
    from data.literature_v9 import open_literature_database
    with open_literature_database(LIT/'literature_material_pool_v9.sqlite',sha(LIT/'literature_material_pool_v9.sqlite')) as lit:
        with load(PARENT,'_v020_freeze_build').Database() as parent:
            old={r['endpoint_id']:r for r in parent.fetch('all_review').rows}
            for r in conflicts:
                previous=old[r['endpoint_id']];assert previous[r['field_name']]==r['previous_value'] and previous['source_group']=='doi:'+DOI
                r['material_key']=previous.get('material_key_v11');r['before_status']=previous.get(r['field_name']+'_status')
                mapped='Raman_ID_IG' if r['field_name']=='Raman_ID_IG' else 'XPS_N_at_pct'
                facts=lit.facts(doi=DOI,sample=r['sample_name'],field=mapped)
                assert len({f['value'] for f in facts})==2 and all('conflict' in f['review_status'] for f in facts)
                r['evidence']=[{k:f[k] for k in ['fact_id','value','raw_value','unit','method','source_path','source_sha256','locator','table_key','row_ordinal','column_ordinal']} for f in facts]
    contract=json.loads((PARENT/'data_contract.json').read_text('utf8'));contract.update(schema='cycling_feature_conflict_freeze_v21',database_file=DB.name,parent_database_sha256=PARENT_SHA,parent_api_directory=PARENT.relative_to(ROOT).as_posix(),field_freeze_policy='Original table/graphic values and previous selection preserved; conflictingN/Raman features selectednull, valid cyclelabels/membership/weightsunchanged. No imputation ornewfit.',storage_layout='15fieldselectiondeltaoverimmutablev0.20,notclone.',model_fits=0,feature_freezes=15,research_training_authorized=False)
    write(OUT/'data_contract.json',contract)
    with closing(sqlite3.connect(DB)) as c:
        c.execute('create table feature_freezes_v21(endpoint_id text,field_name text,material_key text,before_json text,after_json text check(after_json=\'null\'),record_json text,primary key(endpoint_id,field_name))')
        for r in conflicts:c.execute('insert into feature_freezes_v21 values(?,?,?,?,?,?)',(r['endpoint_id'],r['field_name'],r['material_key'],json.dumps(r['previous_value']),'null',json.dumps(r,ensure_ascii=False)))
        c.commit()
    write(OUT/'feature_freezes.json',conflicts)
    print('Built15 forward feature freezes; zero label/member edits')

def verify(prepare=False):
    checks=[]
    def ck(name,ok):
        if not ok:raise AssertionError(name)
        checks.append(name)
    ck('parent_hash',sha(PARENT/'cycling_v0_20.sqlite')==PARENT_SHA)
    changes=json.loads((OUT/'feature_freezes.json').read_text('utf8'));fields={}
    for r in changes:
        fields.setdefault(r['endpoint_id'],set()).add(r['field_name'])
        for e in r['evidence']:ck('raw_source_'+str(e['fact_id']),sha(ROOT/e['source_path'])==e['source_sha256'])
    with closing(ro(DB)) as c:
        ck('integrity',c.execute('pragma integrity_check').fetchone()[0]=='ok');ck('15changes',c.execute('select count(*) from feature_freezes_v21').fetchone()[0]==15);ck('all_null_not_zero',all(json.loads(r[0]) is None for r in c.execute('select after_json from feature_freezes_v21')))
    parent=load(PARENT,'_v020_freeze_verify');child=load(OUT,'_v021_verify');summary={}
    with parent.Database() as old,child.Database() as new:
        for profile in ['all_review']+list(json.loads((OUT/'data_contract.json').read_text('utf8'))['profiles']):
            before=old.fetch(profile);after=new.fetch(profile);a={r['endpoint_id']:r for r in before.rows};b={r['endpoint_id']:r for r in after.rows};ck('membership_'+profile,set(a)==set(b));ck('features_whitelist_'+profile,before.features==after.features)
            for key,row in a.items():
                if key not in fields:ck('unchanged_'+profile+key,b[key]==row);continue
                restored=dict(b[key]);audit=restored.pop('feature_freezes_v21');ck('full_audit_'+profile+key,set(audit)==fields[key])
                for f in fields[key]:
                    ck('null_'+profile+key+f,restored[f] is None and new.by_endpoint(key)[f] is None)
                    ck('original_'+profile+key+f,audit[f]['original_parent_value']==row[f]);restored[f]=row[f]
                    if f+'_status' in row:restored[f+'_status']=row[f+'_status']
                    else:restored.pop(f+'_status',None)
                ck('only15feature_changes_'+profile+key,restored==row)
            summary[profile]=dict(rows=len(after.rows),sources=len({r['source_group'] for r in after.rows}),frozen_features=sum(len(fields.get(r['endpoint_id'],[])) for r in after.rows))
        ck('all278_retained',len(new.fetch('all_review').rows)==278)
        ck('changes15',len(new.field_changes())==15)
        ck('literature_links_preserved',new.literature_links()==old.literature_links())
        # Dataset access must not repopulate missing values by silently selecting a competing source.
        ds=new.fetch('reported_3e')
        for r in ds.rows:
            if r['endpoint_id'] in fields:ck('main_no_conflict_fallback_'+r['endpoint_id'],r['N_at_pct'] is None and r['Raman_ID_IG'] is None and r['XPS_N_reported_pct'] is None)
        for name,matrix in [('material',new.material_matrix('reported_3e')),('method_specific',new.method_specific_material_matrix('reported_3e'))]:
            for i,key in enumerate(matrix['endpoint_ids']):
                if key not in fields:continue
                for f in ['N_at_pct','Raman_ID_IG','XPS_N_reported_pct','XPS_N_atomic_pct_v15']:
                    if f in matrix['feature_names']:ck('matrix_mask_'+name+key+f,matrix['X'][i][matrix['feature_names'].index(f)] is None)
        ck('3e43_31',summary['reported_3e']['rows']==43 and summary['reported_3e']['sources']==31)
        ck('2e27_22',summary['reported_2e']['rows']==27 and summary['reported_2e']['sources']==22)
    report=dict(status='passed',database_sha256=sha(DB),check_count=len(checks),checks=sorted(checks),profile_counts=summary,original_fixed_resolved=1,original_fixed_pending=38,changes=15,affected_endpoints=5,label_changes=0,membership_changes=0,model_fits=0,old_model_claim='Priorperformancebelongsoldinputs; newfreezeversionhasnofitandnoaccuracyclaim')
    if prepare:
        assert not (OUT/'merge_manifest.json').exists();write(OUT/'verification.json',report);write(OUT/'summary.json',dict(profile_counts=summary,changes=15,affected_endpoints=5,original_fixed_resolved=1,original_fixed_pending=38,model_fits=0))
    else:
        assert json.loads((OUT/'verification.json').read_text('utf8'))==report
        if (OUT/'merge_manifest.json').exists():
            for r in json.loads((OUT/'merge_manifest.json').read_text('utf8'))['outputs']:assert sha(ROOT/r['path'])==r['sha256']
    print(json.dumps({k:v for k,v in report.items() if k!='checks'},ensure_ascii=False))

def seal():
    if (OUT/'merge_manifest.json').exists():raise FileExistsError('Alreadysealed')
    verify(False)
    paths=[p for p in OUT.rglob('*') if p.is_file()]+[ROOT/'tools/release_feature_freezes_v021.py']
    write(OUT/'merge_manifest.json',dict(version='cycling_v0.21',parent_sha256=PARENT_SHA,outputs=[dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p),bytes=p.stat().st_size) for p in sorted(paths)],scientific_goal_complete=False,model_fits=0))
    write(ROOT/'data/current_database.json',dict(version_directory=OUT.relative_to(ROOT).as_posix(),database_file=DB.name,sha256=sha(DB),parent_database_file=(PARENT/'cycling_v0_20.sqlite').relative_to(ROOT).as_posix(),default_profile='reported_3e',stage='feature_conflict_freeze_over_immutable_v020',ready_for_training_inputs=True,research_training_authorized=False,all_records_admitted=False))

if __name__=='__main__':
    if len(sys.argv)!=2 or sys.argv[1] not in ['build','prepare','verify','seal']:raise SystemExit('build/prepare/seal once; verify read-only')
    if sys.argv[1]=='prepare':verify(True)
    else:globals()[sys.argv[1]]()
