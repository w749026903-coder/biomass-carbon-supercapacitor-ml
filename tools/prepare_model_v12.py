"""Prepare and freeze one new, finite experiment; never fits an estimator."""
from pathlib import Path
import collections, importlib.metadata, json, math, sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.train_model_v1 import read,write,sha,now
from data.cycling_db import open_database
from data.literature_current import open_literature_database
from models.v1_1.model import derive_semantics,SEMANTIC
from models.v1_2.model import Encoder,CORE
RUN=ROOT/'模型v1.2_来源隔离再训练_20261028'
PROCESS=['carbonization_temperature_C','carbonization_duration_h','carbonization_heating_rate_C_min',
 'precarbonization_temperature_C','precarbonization_duration_h','precarbonization_heating_rate_C_min',
 'hydrothermal_temperature_C','hydrothermal_duration_h','post_treatment_temperature_C','post_treatment_duration_h',
 'post_treatment_heating_rate_C_min','pretreatment_temperature_C','pretreatment_duration_h',
 'pretreatment_heating_rate_C_min','microwave_power_W_v14']

def prepare():
    assert not RUN.exists(),'Do not overwrite an experiment'
    cp=read(ROOT/'data/current_database.json');lp=read(ROOT/'data/current_literature.json')
    cpath=ROOT/cp['version_directory']/cp['database_file'];lpath=ROOT/lp['directory']/lp['database_file']
    assert cp['version']=='cycling_v0.29' and sha(cpath)==cp['sha256']=='092124bd9df25ae2d258cd46588ae27fde9371ace329cb3070ae3f48b4f7d279'
    assert lp['version']=='literature_pool_v26' and sha(lpath)==lp['sha256']=='c48964f31d2e7bcd9745785c1a21c51cb81000afd26d0e8ace73fd8de06ccef5'
    with open_database() as d,open_literature_database() as lit:
        raw=d.fetch('reported_3e').rows;matrix=d.method_specific_material_matrix('reported_3e')
        base={key:dict(zip(matrix['feature_names'],row)) for key,row in zip(matrix['endpoint_ids'],matrix['X'])}
        features=list(dict.fromkeys(matrix['feature_names']+PROCESS+SEMANTIC));records=[];evidence=[]
        properties=d.material_properties()
        for r in raw:
            vals=dict(base[r['endpoint_id']])
            # Historical parameters() assumes a v13 admission key absent in newer
            # already-admitted endpoints. Project its documented selected values
            # and actual change receipts without fabricating that old member key.
            params=dict(values={f:r.get(f) for f in d.contract['parameter_fields_v14']},
                changes=[{**c,'before':json.loads(c['before_json']),'after':json.loads(c['after_json']),
                          'evidence':json.loads(c['evidence_json'])}
                         for c in d.parameter_changes_v14.get(r['endpoint_id'],[])])
            for f in PROCESS:
                value=params['values'].get(f)
                assert value is None or (isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value))
                vals[f]=value
            vals.update(derive_semantics(r))
            group=lit.isolation_group(r.get('source_family_group_v23',r['source_group']))
            records.append(dict(vals,endpoint_id=r['endpoint_id'],source_group=group,raw_source_group=r['source_group'],
                sample_name=r['sample_name'],system=r['system'],method=r['method'],retention_pct=r['retention_pct']))
            evidence.append(dict(endpoint_id=r['endpoint_id'],material_key=r.get('material_key_v11'),
                selected_field_states={k:v for k,v in r.items() if k.endswith('_status') or k in ['field_evidence','field_states','v29_evidence','v26_evidence','source_pdf','source_sha256','XPS_percentage_basis']},
                v14_parameter_changes=params['changes'],material_properties=[p for p in properties if p['material_key']==r.get('material_key_v11')],
                semantic_inputs={f:r.get(f) for f in ['activation_agent_v14','activation_applicability_v14','precursor_v14']},
                projection='Existing method-specific matrix plus selected own stage-specific parameters and unchanged v1.1 taxonomy. No fuzzy DOI/sample join, no raw library response as predictor.'))
        groups=sorted({r['source_group'] for r in records});assert len(records)==47 and len(groups)==34
        assert len({r['endpoint_id'] for r in records})==47
        assert len(d.reviewed_pending_batch())==37
        assert all(r['system']=='3E' and r['method']=='GCD' and r['retention_pct']>0 for r in records)
        assert all(f not in features for f in ['N_at_pct','O_at_pct','retention_pct','sample_name','source_year','source_group','capacitance_F_g'])
        freezes={k:list(v) for k,v in d.freezes_v21.items()};conflicts=d.feature_conflicts_v24()
        # Preserve field-specific N/O ambiguity in the actual method-qualified channels.
        conflict_ids=[]
        for r in raw:
            if any(x['material_key']==r.get('material_key_v11') for x in conflicts):
                q=next(v for v in records if v['endpoint_id']==r['endpoint_id'])
                assert all(q[f] is None for f in ['XPS_N_atomic_pct_v15','XPS_O_atomic_pct_v15','XPS_N_weight_pct_v15','XPS_O_weight_pct_v15'])
                conflict_ids.append(r['endpoint_id'])
        docs=[dict(r) for r in lit.connection.execute('select path,sha256 from source_documents')]
        linkage=d.literature_links();preparation=d.reviewed_preparation_rows_v29()
        audit=dict(rows=47,source_families=34,review_observations=len(d.fetch('all_review').rows),pending_original=37,
            old_feature_freeze_count=sum(len(v) for v in freezes.values()),conflict_masked_endpoints=conflict_ids,
            freeze_index=freezes,raw_source_family_rules=d.source_family_rules(),literature_links=linkage,
            selected_preparation_v29=preparation,library_auxiliary_gcd=208,library_expanded_3e=386,
            auxiliary_learning_used=False,unsealed_batch27_used=False,raw_library_feature_join_performed=False,
            rationale='Use existing traceable cycling-material feature projections. v26 material library contains multiple samples/stages; publication-only or guessed alias joins are prohibited. Auxiliary data are not cycling labels.',
            leakage_prohibitions=['same-test capacitance/CE/retention/EIS/Ragone','DOI/sample IDs','unknown XPS basis substitution','precursor/composite inheritance','unsealed batch27'],
            preprocessing_compatibility='Legacy parameters() assumes admission_profiles_v13; newer admitted endpoints need no invented historical key. Read current selected values and original v14 changes directly. Corrected before plan freezing or any fit.')
    coverage={f:dict(rows=sum(r.get(f)is not None for r in records),families=len({r['source_group'] for r in records if r.get(f)is not None})) for f in features}
    old=read(ROOT/'模型逐项优化_v1.1_20261022/input_snapshot.json')['records'];old_groups={r['source_group'].lower() for r in old}
    audit['historical_overlap']=dict(prior_rows=len(old),prior_groups=len(old_groups),current_groups_already_in_v11=sum(g.lower() in old_groups for g in groups),
        current_groups_not_in_v11=[g for g in groups if g.lower() not in old_groups],interpretation='All this run is exploratory. No group is prospectively designated untouched external validation.')
    protected={}
    def protect(p,expected=None):
        p=Path(p);key=p.relative_to(ROOT).as_posix();h=sha(p)
        if expected:assert h==expected,key
        if key in protected:assert protected[key]==h
        protected[key]=h
    for p in [cpath,lpath,ROOT/'data/current_database.json',ROOT/'data/current_literature.json']:protect(p)
    for folder in [cpath.parent,lpath.parent]:
        protect(folder/'merge_manifest.json')
        for item in read(folder/'merge_manifest.json')['outputs']:protect(ROOT/item['path'],item['sha256'])
    for item in docs:protect(ROOT/item['path'],item['sha256'])
    for oldfolder in ['初步模型训练_20261021','模型诊断与改进_20261021','模型v1.0_来源留出训练_20261022','模型逐项优化_v1.1_20261022']:
        for p in (ROOT/oldfolder).iterdir():
            if p.is_file():protect(p)
    for p in (ROOT/'data').glob('*.py'):protect(p)
    protect(ROOT/'models/v1_1/model.py');protect(ROOT/'models/v1_0/model.py')
    RUN.mkdir()
    snapshot=dict(records=records,features=features,profile='reported_3e',source_scope='reported author current; unknown physical mass remains unknown')
    write(RUN/'input_snapshot.json',snapshot);write(RUN/'raw_selected_records.json',raw);write(RUN/'field_evidence.json',evidence)
    write(RUN/'feature_coverage.json',coverage);write(RUN/'input_audit.json',audit);write(RUN/'protected_inputs.json',protected)
    candidates=[dict(id='core_noI_ridge100',kind='ridge',block='core',current=False,alpha=100.),
                dict(id='material_noI_ridge100',kind='ridge',block='material',current=False,alpha=100.),
                dict(id='material_I_ridge100',kind='ridge',block='material',current=True,alpha=100.),
                dict(id='material_I_krr10',kind='krr',block='material',current=True,alpha=10.),
                dict(id='material_I_extra_trees',kind='extra_trees',block='material',current=True)]
    outer=[]
    def split3(indices):
        gg=sorted({records[i]['source_group'] for i in indices});bucket={g:k%3 for k,g in enumerate(gg)}
        return [dict(train=[i for i in indices if bucket[records[i]['source_group']]!=k],test=[i for i in indices if bucket[records[i]['source_group']]==k]) for k in range(3)]
    for g in groups:
        tr=[i for i,r in enumerate(records) if r['source_group']!=g];te=[i for i,r in enumerate(records) if r['source_group']==g]
        outer.append(dict(source=g,train=tr,test=te,inner=split3(tr)))
    plan=dict(run_id='retention-v1.2-source-isolated-20261028',created_at=now(),
        authorization=dict(authorized=True,user_request='接续到下一个对话并尝试训练一次',scope='One finite small-data exploratory experiment; no giant pretraining, service, data relabeling or iterative test-score search.'),
        database_pointer=cp,literature_pointer=lp,snapshot_sha256=sha(RUN/'input_snapshot.json'),rows=47,source_families=34,
        feature_names=features,candidates=candidates,outer_folds=outer,final_selection_folds=split3(list(range(47))),
        primary='Nested procedure: choose one of five fixed candidates by 3-fold source-equal inner MAE; evaluate once on each of 34 outer source families; final recipe selected separately by all-source 3-fold CV.',
        target='log(retention_pct/100); training-fold source-weighted centering and scaling; inverse100*exp, no upper cap',
        baselines=['training-fold source-weighted arithmetic mean','training-fold source-weighted median'],
        preprocessing=dict(optional_numeric_minimum_training_families=5,categorical_minimum_training_families=3,
            numeric_imputation='training observed-source-weighted median',scaling='training observed-source-weighted mean/SD',
            missing_indicator='optional numeric fields',kernel_gamma='inverse training cross-family weighted median squared distance'),
        planned_estimator_fits=560,random_seed=20261028,threads=1,hyperparameter_search='Only these five candidates; no post-outer-score additions.',
        performance_acceptance='Exploratory evidence only: nested source-equal MAE below both simple baselines AND upper95% descriptive paired source-bootstrap delta vsmean <0. Not a claim of external predictive validity.',
        uncertainty='5000 paired source-bootstrap resamples; no refits, descriptive cohort uncertainty only, not prediction intervals',
        stop='After 560 planned fits and verification. Do not remove difficult records or add candidates after scores.',
        independent_external_validation=False,auxiliary_learning_used=False,training_2e=False,
        excluded=['unsealed batch27','pending/frozen/non-main endpoints','direct mixing2E and3E','same-test response predictors'])
    # This is preprocessing-only validation, before any estimator fit.
    a=Encoder(candidates[2],features).fit(records[:-1]);before=json.dumps(a.schema,sort_keys=True)
    changed=dict(records[-1]);changed['BET_m2_g']=1e9;a.transform([changed]);assert json.dumps(a.schema,sort_keys=True)==before
    assert a.schema and all(f['field'] not in ['retention_pct','endpoint_id','source_group'] for f in a.schema)
    write(RUN/'training_plan.json',plan)
    code=['models/v1_2/model.py','tools/prepare_model_v12.py','tools/train_model_v12.py']
    write(RUN/'frozen_run_hashes.json',{p:sha(ROOT/p) for p in code}|{'training_plan.json':sha(RUN/'training_plan.json'),'input_snapshot.json':sha(RUN/'input_snapshot.json')})
    write(RUN/'progress.json',dict(status='planned',completed=0,total=560,actual_estimator_fits=0,percent=0,events=[],updated_at=now(),plan_sha256=sha(RUN/'training_plan.json')))
    write(RUN/'environment.json',dict(python=sys.version,executable=str(Path(sys.executable).relative_to(ROOT)),packages={n:importlib.metadata.version(n) for n in ['numpy','scipy','scikit-learn','joblib','threadpoolctl']},shared_runtime_modified=False))
    print(json.dumps(dict(prepared=True,rows=47,sources=34,features=len(features),protected_files=len(protected),planned_fits=560,model_fits=0,coverage=coverage),ensure_ascii=False))

if __name__=='__main__':prepare()
