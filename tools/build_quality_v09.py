"""Build the small v0.9 SQLite overlay from reviewed deltas, never change v0.8.

--materialize-unsealed completes an existing unsealed overlay. A sealed release
always refuses writes. No estimator, downloader or source-library mover is run.
"""
from pathlib import Path
import csv, hashlib, importlib.util, json, sqlite3, sys
from training_input_quality import assess,prepare_source_fold
ROOT=Path(__file__).resolve().parents[1]
BATCH=ROOT/'数据质量优化_20261021'
OUT=ROOT/'循环稳定性数据库_v0.9_训练质量准备_20261021'
PARENT=ROOT/'循环稳定性数据库_v0.8_新增文献整理_20261020'
PARENT_SHA='7b0be21a669b7922a3c06671ddc5f14b285f19c8778dde2a14a8733ee89e964f'
def sha(path):
    with open(path,'rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(path):return json.loads(path.read_text('utf-8'))
def write(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n','utf-8')
def api():
    spec=importlib.util.spec_from_file_location('_quality_v09_api',OUT/'ml_data.py');m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m);return m
def build(materialize=False):
    if (OUT/'merge_manifest.json').exists():raise FileExistsError('Sealed v0.9 is immutable.')
    path=OUT/'cycling_v0_9.sqlite'
    if path.exists() and not materialize:raise FileExistsError('Use a new release or explicitly complete an unsealed overlay.')
    if sha(PARENT/'cycling_v0_8.sqlite')!=PARENT_SHA:raise ValueError('Parent changed')
    cases=read(BATCH/'curation_delta.json');identity=read(BATCH/'SI_identity_reviews.json')
    c=sqlite3.connect(path)
    if not materialize:
        c.executescript('CREATE TABLE quality_decisions_v09(endpoint_id TEXT PRIMARY KEY,record_id TEXT UNIQUE,decision_json TEXT NOT NULL); CREATE TABLE supplemental_sources_v09(document_id TEXT PRIMARY KEY,path TEXT NOT NULL,sha256 TEXT NOT NULL,identity_json TEXT NOT NULL); CREATE TABLE meta_v09(key TEXT PRIMARY KEY,value_json TEXT NOT NULL);')
        for r in cases:c.execute('insert into quality_decisions_v09 values(?,?,?)',(r['endpoint_id'],r['record_id'],json.dumps(r,ensure_ascii=False)))
        for r in identity:c.execute('insert into supplemental_sources_v09 values(?,?,?,?)',(r['document_id'],r['path'],r['sha256'],json.dumps(r,ensure_ascii=False)))
        c.execute('insert into meta_v09 values(?,?)',('parent_database_sha256',json.dumps(PARENT_SHA)))
    else:
        saved={r[0]:json.loads(r[1]) for r in c.execute('select endpoint_id,decision_json from quality_decisions_v09')}
        if saved!={r['endpoint_id']:r for r in cases}:raise ValueError('Unsealed SQLite differs from reviewed input; inspect before updating.')
    c.execute('CREATE TABLE IF NOT EXISTS training_rows_v09(profile TEXT NOT NULL,endpoint_id TEXT NOT NULL,source_group TEXT NOT NULL,row_json TEXT NOT NULL,PRIMARY KEY(profile,endpoint_id))')
    c.execute('CREATE TABLE IF NOT EXISTS training_folds_v09(profile TEXT NOT NULL,fold_index INTEGER NOT NULL,split_json TEXT NOT NULL,PRIMARY KEY(profile,fold_index))')
    c.execute('DELETE FROM training_rows_v09');c.execute('DELETE FROM training_folds_v09');c.commit()
    contract=read(PARENT/'data_contract.json');contract.update(version='v0.9',database_file=path.name,parent_database_sha256=PARENT_SHA,storage_layout='Verified read-only v0.8 base plus v0.9 evidence overlay and materialized training snapshots. Whole repository required for historical evidence.',research_training_authorized=False)
    write(OUT/'data_contract.json',contract)
    readiness={'purpose':'reported_protocol_retention','data_preparation_ready':True,'formal_model_fit_authorized':False,'all_literature_admitted':False,'cohorts':{}}
    with api().Database() as db:
        for prof in contract['profiles']:
            ds=db.fetch(prof);q=assess(ds);readiness['cohorts'][prof]=q
            folds=ds.source_folds(len({r['source_group'] for r in ds.rows}))
            write(OUT/(prof+'_inputs.json'),{'rows':ds.rows,'matrix':ds.feature_matrix(),'source_folds':folds,'fingerprint':ds.fingerprint()})
            for r in ds.rows:c.execute('insert into training_rows_v09 values(?,?,?,?)',(prof,r['endpoint_id'],r['source_group'],json.dumps(r,ensure_ascii=False)))
            for n,fold in enumerate(folds):c.execute('insert into training_folds_v09 values(?,?,?)',(prof,n,json.dumps(fold)))
            with (OUT/(prof+'_inputs.csv')).open('w',encoding='utf-8-sig',newline='') as f:
                fields=['endpoint_id','source_group','source_year','sample_name',*ds.features,'retention_pct','retention_relation','source_weight'];w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(ds.rows)
            write(OUT/(prof+'_fold_example.json'),prepare_source_fold(ds,folds[0]))
        write(BATCH/'current_review_rows.json',db.incoming_tests());write(BATCH/'current_source_reviews.json',db.incoming_sources())
    c.commit();assert c.execute('pragma integrity_check').fetchone()[0]=='ok';c.close();write(OUT/'training_readiness.json',readiness)
    return readiness
if __name__=='__main__':
    result=build('--materialize-unsealed' in sys.argv)
    print(json.dumps({p:{k:q[k] for k in ['rows','source_groups','status','model_fits']} for p,q in result['cohorts'].items()},ensure_ascii=False))
