"""Freeze the newly authorized v7 experiment before any estimator is fitted."""
from pathlib import Path
import collections, datetime, hashlib, importlib.metadata, json, sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from data.training_latest import open_training_datasets
from models.v1_3.model import canonical,Encoder
RUN=ROOT/'模型v1.3_新数据与辅助学习_20261029'
TASKS={'retention':'cycle:reported_3e','capacity':'capacity:3e_with_graph','BET':'material:ordinary_biomass_pretest:BET_surface_area_m2_g'}
def read(p):return json.loads(Path(p).read_text('utf-8-sig'))
def write(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n','utf8')
def sha(p):
    with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def now():return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(timespec='seconds')
def split3(rows):
    gs=sorted({r['source_family']for r in rows});b={g:i%3 for i,g in enumerate(gs)}
    return [( [r for r in rows if b[r['source_family']]!=i], [r for r in rows if b[r['source_family']]==i])for i in range(3)]

def prepare():
    assert not RUN.exists(), 'Never replace an existing experiment'
    pointer=read(ROOT/'data/current_training_latest.json');release=ROOT/pointer['directory']
    assert pointer['version']=='training_latest_v7_YZPC_Kochia'
    data={};raw={};uses=[];projection_masks=[];protected=read(release/'protected_inputs.json')
    with open_training_datasets(release/pointer['database_file'],pointer['sha256'])as d:
        reported={r['row_id']for r in d.rows('capacity:3e_reported')}
        for name,task in TASKS.items():
            raw[name]=d.rows(task);data[name]=[]
            for r in raw[name]:
                features,mapping=canonical(r['features'])
                if name=='BET':
                    for field in list(features):
                        if any(s in field for s in ['BET_', 'pore', 'surface_area']):
                            projection_masks.append(dict(task=task,row_id=r['row_id'],field=field,value=features.pop(field),reason='Adsorption-derived area ratio belongs to the same measurement block as BET; excluded in this frozen training projection, original v7 unchanged'))
                    assert all(not any(s in k for s in ['BET_', 'pore', 'surface_area'])for k in features)
                data[name].append(dict(row_id=r['row_id'],source_family=r['source_family'],material_key=r.get('material_key'),sample_name=r['sample_name'],features=features,
                    target=r['target'],feature_mapping=mapping,quality_weight=.5 if name=='capacity'and r['row_id']not in reported else 1.,
                    task=task,conditions=r['conditions']))
        q=d.connection
        for r in q.execute('select *from fact_uses where task in (?,?,?)',tuple(TASKS.values())):uses.append(dict(r))
        ledger=[dict(r)for r in q.execute('select fact_id,disposition from usage_ledger')]
        dataset_scope=[dict(task=t,**v,included=t in TASKS.values(),reason='Selected cycling, ordinary 3E capacitance, or ordinary pretest BET task'if t in TASKS.values()else'Other target/stage/system or overlapping sensitivity/method view; not pooled as retention labels')for t,v in d.summary['task_counts'].items()]
        parentmeta={r['key']:json.loads(r['value_json'])for r in q.execute('select *from main.metadata')}
    old=read(ROOT/'模型v1.2_来源隔离再训练_20261028/input_snapshot.json')
    data['legacy']=[]
    for r in old['records']:
        features,mapping=canonical({f:r.get(f)for f in old['features']})
        data['legacy'].append(dict(row_id=r['endpoint_id'],source_family=r['source_group'],sample_name=r['sample_name'],features=features,target=r['retention_pct'],quality_weight=1.,feature_mapping=mapping,task='legacy_reference'))
    a={r['row_id']:r for r in data['legacy']};b={r['row_id']:r for r in data['retention']}
    assert set(a)==set(b) and len(b)==47 and len({r['source_family']for r in b.values()})==34
    for k in a:assert a[k]['target']==b[k]['target']and a[k]['source_family']==b[k]['source_family']
    assert len(data['capacity'])==434 and len(data['BET'])==266
    added=sum(v is not None and a[k]['features'].get(f)is None for k,r in b.items()for f,v in r['features'].items())
    assert all(r['target']>0 for rs in data.values()for r in rs)
    for name,rs in data.items():
        for tr,te in split3(rs):
            enc=Encoder(.1 if name in ['capacity','BET']else .2).fit(tr);before=json.dumps(enc.schema,sort_keys=True)
            enc.transform(te);assert before==json.dumps(enc.schema,sort_keys=True)
    def protect(p,expected=None):
        p=Path(p);h=sha(p)
        if expected:assert h==expected,str(p)
        protected[p.relative_to(ROOT).as_posix()]=h
    protect(release/pointer['database_file'],pointer['sha256'])
    for p in parentmeta['readonly_parent_chain']:protect(ROOT/p['path'],p['sha256'])
    for item in read(release/'merge_manifest.json')['outputs']:protect(ROOT/item['path'],item['sha256'])
    for p in (ROOT/'模型v1.2_来源隔离再训练_20261028').iterdir():
        if p.is_file():protect(p)
    protect(ROOT/'data/current_training_latest.json')
    for name in ['retention','capacity','BET']:
        for r in raw[name]:
            record=r.get('original_report',{})
            if record.get('path')and record.get('sha256'):protect(ROOT/record['path'],record['sha256'])
            for ev in r.get('process_evidence',[]):
                if ev.get('path')and ev.get('sha256'):protect(ROOT/ev['path'],ev['sha256'])
    RUN.mkdir()
    write(RUN/'input_snapshot.json',data);write(RUN/'raw_api_rows.json',raw)
    write(RUN/'fact_use_candidates.json',uses);write(RUN/'dataset_scope.json',dataset_scope);write(RUN/'protected_inputs.json',protected);write(RUN/'training_projection_masks.json',projection_masks)
    write(RUN/'input_audit.json',dict(counts={k:dict(rows=len(v),sources=len({r['source_family']for r in v}))for k,v in data.items()},
        additional_nonempty_canonical_main_cells=added,material_connections=25,original_pending=37,original_freezes=15,unsealed_v8_used=False,
        graph_rows=205,graph_quality_weight=.5,graph_weight_is_heuristic_not_measurement_variance=True,raw_values_and_original_conditions_not_changed=True,
        fact_ledger_count=len(ledger),source_grouping='Existing API source families, all tasks cross-excluded',new_cycling_admissions=0))
    plan=dict(run_id='v1.3-v7-assisted-20261029',frozen_at=now(),authorization=dict(authorized=True,user_request='先充分利用新获取到的数据尝试进行一次模型训练，再重新生成进展报告，页数要少一点，但又要用大白话讲清楚'),
        input_pointer=pointer,snapshot_sha256=sha(RUN/'input_snapshot.json'),primary='latest_assisted_ridge',
        retention_recipes=['legacy_input_ridge','latest_ridge','latest_trees','latest_assisted_ridge'],
        primary_preselected_not_outer_score_winner=True,hyperparameters=dict(ridge_alpha=100.,tree_estimators=160,tree_depth=4,tree_leaf=3,tree_max_features=.8),
        transforms='Train-fold-only source-weighted scaling/imputation, positive log target, no upper clipping',
        feature_guard=dict(minimum_sources=3,minimum_row_fraction_main=.2,minimum_row_fraction_aux=.1,categorical_vocabulary_minimum_sources=3),
        source_weighting='Each source totals one; graph-only rows receive0.5 relative weight within their own source',
        validation='One entire source family held out in each task. All related auxiliary rows from a main held-out family excluded. No prospective untouched external test.',
        auxiliary_stack='For each retention training split, create 3-fold source-cross-fitted capacity and BET predictions. Each helper excludes outer test family and its query families. Fit final helpers excluding outer family to predict main test. Never use observed auxiliary responses as retention predictors.',
        capacity_query='Predicted auxiliary 3E response at supplied cycling current/electrolyte/window; hypothetical model query, not experimentally measured initial capacitance or copied fresh-GCD protocol.',
        plan_fit_counts=dict(retention=140,assisting_helpers=280,standalone_auxiliary=88,total=508),
        diagnostic_baselines=['Training-only source-weighted arithmetic mean','Training-only source-weighted median'],
        acceptance='Preselected primary retention recipe must beat both baselines in source-equal MAE and paired5000 source-bootstrap delta vsmean upper95%<0. Descriptive only, no calibrated prediction intervals.',
        stop='Exactly508 estimator fits; do not add recipes or refit after held-out scores. Preserve failures and difficult samples.',
        new_external_validation=False,training_2e=False,unsealed_v8_used=False,new_data_admission=False,
        methods_source='https://scikit-learn.org/stable/modules/cross_validation.html#cross-validation-iterators-for-grouped-data')
    write(RUN/'training_plan.json',plan)
    code=['models/v1_3/model.py','tools/prepare_model_v13.py','tools/train_model_v13.py']
    write(RUN/'frozen_run_hashes.json',{p:sha(ROOT/p)for p in code}|{'training_plan.json':sha(RUN/'training_plan.json'),'input_snapshot.json':sha(RUN/'input_snapshot.json')})
    write(RUN/'progress.json',dict(status='planned',completed=0,total=508,events=[],updated_at=now()))
    write(RUN/'environment.json',dict(python=sys.version,packages={k:importlib.metadata.version(k)for k in ['numpy','scipy','scikit-learn','joblib']},global_runtime_changed=False))
    print(json.dumps(dict(prepared=True,planned_fits=508,additional_cells=added,protected_files=len(protected),counts=read(RUN/'input_audit.json')['counts']),ensure_ascii=False))
if __name__=='__main__':prepare()
