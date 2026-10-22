"""Independent checks for unit interpretation, source-safe fitting, and preserved history."""
from pathlib import Path
from collections import Counter,defaultdict
import io
import json
import math
import sqlite3
import statistics
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from models.v1_0.model import CORE,MATERIAL
from models.v1_1.model import SEMANTIC,derive_semantics,assess_prediction
from tools.train_model_v1 import sha,read,write


def independent_metric(rows):
    counts=Counter(r['source_group'] for r in rows);w=[1/counts[r['source_group']] for r in rows];n=len(counts)
    center=sum(r['observed_pct']*v for r,v in zip(rows,w))/n
    mae=sum(abs(r['predicted_pct']-r['observed_pct'])*v for r,v in zip(rows,w))/n
    mse=sum((r['predicted_pct']-r['observed_pct'])**2*v for r,v in zip(rows,w))/n
    var=sum((r['observed_pct']-center)**2*v for r,v in zip(rows,w))/n
    return dict(mae=mae,rmse=math.sqrt(mse),r2=1-mse/var)


def verify(folder):
    import joblib
    import numpy as np
    folder=folder.resolve();plan=read(folder/'training_plan.json');rows=read(folder/'input_snapshot.json')['records']
    checks=0
    def check(condition,message):
        nonlocal checks
        checks+=1
        if not condition:raise AssertionError(message)
    def near(x,y,message):check(abs(x-y)<1e-8,message)
    for path,digest in read(folder/'protected_inputs.json').items():check(sha(ROOT/path)==digest,'Protected input: '+path)
    old=read(ROOT/'模型v1.0_来源留出训练_20261022/run_manifest.json')['outputs']
    for payload in old:check(sha(ROOT/payload['path'])==payload['sha256'],'Oldv1.0 payload: '+payload['path'])
    originals=read(ROOT/'主集参数精提取_20261022/protected_sources.json')
    for path,digest in originals.items():check(sha(ROOT/path)==digest,'Original source: '+path)
    frozen=read(folder/'frozen_run_hashes.json')
    for path,digest in frozen.items():
        file=folder/('training_plan.json' if path=='plan' else 'input_snapshot.json') if path in ['plan','snapshot'] else ROOT/path
        check(sha(file)==digest,'Frozen file changed: '+path)
    evidence={r['endpoint_id']:r for r in read(folder/'semantic_feature_evidence.json')}
    previous=read(ROOT/'模型v1.0_来源留出训练_20261022/data_snapshot.json')['records']
    for r,oldrow in zip(rows,previous):
        for key,value in oldrow.items():check(r[key]==value,'Old target/core/parameter changed: '+key)
        item=evidence[r['endpoint_id']]
        check({f:r[f] for f in SEMANTIC}==derive_semantics(item['raw_methods']),'Semantic projection differs from reviewed raw values')
    audit=read(folder/'unit_audit.json')
    check(audit['review_observations']==277 and audit['numeric_retention_values']==273,'Review count')
    check(not audit['negative_values'] and not audit['possible_fraction_in_pct_field'],'Units need review')
    check(sorted(r['retention_pct'] for r in audit['above100_main_rows'])==[101.35,106.3,109.2],'Legitimate high values lost')
    source_reviews=read(folder/'critical_source_review.json')
    check(len(source_reviews)==5,'Critical source review count')
    for item in source_reviews:
        check(sha(ROOT/item['path'])==item['sha256'],'Critical source hash')
        near(item['retention_ratio']*100,item['retention_pct'],'Critical source ratio')
    for value in [0.,83.54,100.,101.24,109.2,114.36]:
        result=assess_prediction(value)
        near(result['predicted_retention_ratio']*100,value,'Percentage ratio conversion')
        check(result['above_initial_reference']==(value>100),'Above reference interpretation')
        check(not result['reliable_for_design'] and result['calibrated_prediction_interval'] is None,'Unjustified confidence')
    for value in [-.1,float('nan'),float('inf')]:
        try:assess_prediction(value)
        except ValueError:check(True,'Invalid output rejected')
        else:check(False,'Invalid output accepted')
    conn=sqlite3.connect('file:'+(folder/'evaluation.sqlite').as_posix()+'?mode=ro',uri=True)
    check(conn.execute('PRAGMA integrity_check').fetchone()[0]=='ok','SQLite integrity')
    jobs=[json.loads(v) for v, in conn.execute('SELECT payload FROM jobs ORDER BY rowid')];conn.close()
    by_key={j['key']:j for j in jobs}
    check(len(jobs)==1332 and sum(j['estimator_fits'] for j in jobs)==1301,'Real job/fit count')
    main_predictions=read(folder/'outer_predictions.json')
    for job in jobs:
        if job['stage']=='selection':
            check(job['selected_id']==min(job['scores'],key=lambda r:r['mae'])['candidate'],'Selection not from inner scores')
            prefix=job['key'].removesuffix('/selection')
            for candidate in job['scores']:
                predictions=[p for key,j in by_key.items() if key.startswith(prefix+'/inner/'+candidate['candidate']+'/') for p in j['predictions']]
                for metric,value in independent_metric(predictions).items():near(value,candidate[metric],'Inner selection metric')
            continue
        train,test=job['train'],job['test'];tr=[rows[i] for i in train]
        check(not {r['source_group'] for r in tr}&{rows[i]['source_group'] for i in test},'Source leakage')
        if job['stage']=='inner' and job['key'].startswith('outer/'):
            outer_number=int(job['key'].split('/')[1])-1
            check(not set(train+test)&set(plan['outer_folds'][outer_number]['test']),'Outer source in inner selection')
        for item in job['schema']:
            f=item['field'];check(f in CORE+MATERIAL,'Identifier or outcome used as numeric predictor')
            if item['kind']=='categorical':
                check(item['vocabulary']==sorted({r[f] for r in tr if r[f] is not None}),'Vocabulary leakage');continue
            observed=[r for r in tr if r[f] is not None]
            support=len({r['source_group'] for r in observed})
            check(item['source_support']==support,'Numeric support inflated by repeated rows')
            if f in MATERIAL:check(item['enabled']==(support>=5),'Wrong numeric support threshold')
            if item['enabled']:
                grouped=defaultdict(list)
                for r in observed:grouped[r['source_group']].append(math.log1p(r[f]) if item['transform']=='log1p' else r[f])
                mean=statistics.fmean(statistics.fmean(v) for v in grouped.values())
                var=statistics.fmean(statistics.fmean((v-mean)**2 for v in vs) for vs in grouped.values())
                near(mean,item['mean'],'Numeric center');near(math.sqrt(var) or 1.,item['scale'],'Numeric scale')
        for item in job['semantic_schema']:
            check(item['field'] in SEMANTIC,'Unexpected semantic field')
            support=defaultdict(set)
            for r in tr:
                if r[item['field']] is not None:support[r[item['field']]].add(r['source_group'])
            check(item['source_support']=={k:len(v) for k,v in sorted(support.items())},'Semantic source support')
            check(item['vocabulary']==sorted(k for k,v in support.items() if len(v)>=3),'Semantic vocabulary leakage or rare-class inflation')
        z_groups=defaultdict(list)
        for r in tr:z_groups[r['source_group']].append(r['retention_pct'] if job['reference'] else math.log(r['retention_pct']/100))
        center=statistics.fmean(statistics.fmean(v) for v in z_groups.values())
        variance=statistics.fmean(statistics.fmean((z-center)**2 for z in values) for values in z_groups.values())
        near(center,job['target_center'],'Training-only target center');near(math.sqrt(variance) or 1.,job['target_scale'],'Training-only target scale')
        for p in job['predictions']:
            check(rows[p['index']]['retention_pct']==p['observed_pct'],'Outcome changed')
            check(math.isfinite(p['predicted_pct']) and (job['reference'] or p['predicted_pct']>0),'Output domain')
    result=read(folder/'results.json')
    for s in result['metrics']:
        predictions=[r for r in main_predictions if r['variant']==s['variant']]
        check(len(predictions)==42 and len({r['endpoint_id'] for r in predictions})==42,'OOF duplicate/omission')
        for metric,value in independent_metric(predictions).items():near(value,s[metric],'Independent OOF metric')
        for base_key,variant in [('vs_reference','v1_recipe_same_cohort'),('vs_mean','source_mean')]:
            reference={r['endpoint_id']:r for r in main_predictions if r['variant']==variant}
            by_group=defaultdict(list)
            for r in predictions:
                base=reference[r['endpoint_id']];by_group[r['source_group']].append(abs(r['predicted_pct']-r['observed_pct'])-abs(base['predicted_pct']-base['observed_pct']))
            group_errors=np.array([statistics.fmean(v) for _,v in sorted(by_group.items())])
            sampled=np.random.default_rng(20261023).integers(0,30,(5000,30))
            lo,hi=np.quantile(group_errors[sampled].mean(axis=1),[.025,.975])
            near(float(group_errors.mean()),s[base_key]['delta_mae'],'Paired delta')
            near(float(lo),s[base_key]['delta_low'],'Delta lower');near(float(hi),s[base_key]['delta_high'],'Delta upper')
    model=joblib.load(folder/'model_v1_1.joblib')
    check(len(model.training_sources)==30 and len(model.training_endpoint_ids)==42,'Final fit scope')
    check(model.spec['id']==result['selected_id']==by_key['final/selection']['selected_id'],'Final selected model changed')
    check(sha(folder/'model_v1_1.joblib')==result['model_sha256'],'Model hash')
    check(read(folder/'model_schema.json')=={'numeric':model.encoder.schema,'semantic':model.semantic_schema},'Schema differs from saved model')
    buffer=io.BytesIO();joblib.dump(model,buffer);buffer.seek(0)
    check(np.array_equal(model.predict(rows),joblib.load(buffer).predict(rows)),'Serialization roundtrip')
    probe=read(folder/'inference_example.json')
    check(model.predict_with_context(probe)==read(folder/'inference_example_output.json'),'Actual inference example')
    modified=[dict(probe[0],system='2E')]
    try:model.predict_with_context(modified)
    except ValueError:check(True,'Wrong system rejected')
    else:check(False,'Wrong system accepted')
    progress=read(folder/'progress.json')
    check(progress['status']=='complete' and progress['completed']==1332,'Progress completion')
    check([r['completed'] for r in progress['events']]==list(range(1,1333)),'Progress not actual unique jobs')
    # Counterfactual held-out values must not affect any training schema or its encoded X.
    from models.v1_0.model import Encoder
    split=plan['outer_folds'][0]['inner'][0];train=[rows[i] for i in split['train']]
    e=Encoder({'block':'material','current':True}).fit(train);before=e.transform(train)
    changed=[dict(r) for r in rows]
    for i in set(range(42))-set(split['train']):changed[i].update(retention_pct=-999, BET_m2_g=1e12,electrolyte='NEW_UNKNOWN')
    f=Encoder({'block':'material','current':True}).fit([changed[i] for i in split['train']])
    check(e.schema==f.schema and np.array_equal(before,f.transform(train)),'Held-out mutation changes training transformation')
    report={'passed':True,'check_count':checks,'new_estimator_fits':0,'old_v1_payloads_verified':len(old),
        'original_source_files_verified':len(originals),'actual_estimator_fits':1301,'tasks':1332,
        'scientific_reliability_approved':False,'independent_validation_available':False,
        'positive_output_and_explicit_units_verified':True,'above100_originals_preserved':3,
        'cohort_comparison':'Both methods evaluated on identical42rows/30sources. New workflow uses nested selection; all sources were previously seen.',
        'model_sha256':result['model_sha256']}
    write(folder/'verification.json',report);print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':verify(ROOT/'模型逐项优化_v1.1_20261022')
