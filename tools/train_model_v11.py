"""One frozen positive-target / semantic-feature experiment on already-used sources."""
from pathlib import Path
from collections import defaultdict
import argparse
import importlib.metadata
import json
import math
import sqlite3
import sys
import time
import traceback
import warnings

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from models.v1_0.model import RetentionModel, metrics
from models.v1_1.model import PositiveRetentionModel, assess_prediction
from tools.train_model_v1 import read,write,sha,now


def evaluate(key,stage,spec,records,train,test,reference=False):
    from threadpoolctl import threadpool_limits
    tr,te=[records[i] for i in train],[records[i] for i in test]
    assert not {r['source_group'] for r in tr}&{r['source_group'] for r in te}
    tick=time.monotonic()
    with warnings.catch_warnings(record=True) as caught, threadpool_limits(limits=1):
        model=RetentionModel(spec) if reference else PositiveRetentionModel(spec)
        model.fit(tr);pred=model.predict(te)
    job={'key':key,'stage':stage,'candidate':spec['id'],'train':train,'test':test,
        'training_sources':model.training_sources,'schema':model.encoder.schema,
        'semantic_schema':getattr(model,'semantic_schema',[]),'target_center':model.center,
        'target_scale':model.scale,'reference':reference,'estimator_fits':1,
        'warnings':[str(w.message) for w in caught],'seconds':time.monotonic()-tick,
        'predictions':[{'index':i,'endpoint_id':r['endpoint_id'],'source_group':r['source_group'],
            'sample_name':r['sample_name'],'observed_pct':r['retention_pct'],'predicted_pct':float(p),
            'input_warnings':model.encoder.warnings(r)} for i,r,p in zip(test,te,pred)]}
    return job,model


def score(predictions,records):
    return metrics([records[r['index']] for r in predictions],[r['predicted_pct'] for r in predictions])


def paired_bootstrap(rows,reference):
    import numpy as np
    baseline={r['endpoint_id']:r for r in reference};grouped=defaultdict(list)
    for r in rows:
        base=baseline[r['endpoint_id']]
        e=abs(r['predicted_pct']-r['observed_pct'])
        grouped[r['source_group']].append((e,e-abs(base['predicted_pct']-base['observed_pct'])))
    group_errors=np.array([np.mean(v,axis=0) for _,v in sorted(grouped.items())])
    ids=np.random.default_rng(20261023).integers(0,len(group_errors),(5000,len(group_errors)))
    bounds=np.quantile(group_errors[ids].mean(axis=1),[.025,.975],axis=0)
    return {'mae_low':float(bounds[0,0]),'mae_high':float(bounds[1,0]),
            'delta_mae':float(group_errors[:,1].mean()),'delta_low':float(bounds[0,1]),'delta_high':float(bounds[1,1]),
            'method':'5000 paired source-bootstrap resamples, descriptive95%; reused development cohort, no independent prediction interval.'}


def run(folder,resume=False):
    import joblib
    from threadpoolctl import threadpool_limits
    folder=folder.resolve()
    if ROOT not in folder.parents or (folder/'results.json').exists():raise ValueError('Do not overwrite a completed run.')
    plan=read(folder/'training_plan.json')
    if not plan['authorization']['authorized']:raise ValueError('Explicit scoped authorization required.')
    if read(ROOT/'data/current_database.json')!=plan['database_pointer']:raise ValueError('Data pointer changed.')
    if sha(folder/'input_snapshot.json')!=plan['snapshot_sha256']:raise ValueError('Snapshot changed.')
    for path,h in read(folder/'protected_inputs.json').items():
        if sha(ROOT/path)!=h:raise ValueError('Protected input changed: '+path)
    code=['models/v1_1/model.py','tools/train_model_v11.py','tools/prepare_model_v11.py']
    seal={path:sha(ROOT/path) for path in code}
    seal.update(plan=sha(folder/'training_plan.json'),snapshot=sha(folder/'input_snapshot.json'))
    if (folder/'frozen_run_hashes.json').exists():
        if not resume or read(folder/'frozen_run_hashes.json')!=seal:raise ValueError('Only exact frozen runs can resume.')
    else:write(folder/'frozen_run_hashes.json',seal)
    records=read(folder/'input_snapshot.json')['records']
    connection=sqlite3.connect(folder/'evaluation.sqlite')
    connection.execute('CREATE TABLE IF NOT EXISTS jobs(key TEXT PRIMARY KEY,payload TEXT NOT NULL)');connection.commit()
    done={key:json.loads(value) for key,value in connection.execute('SELECT key,payload FROM jobs ORDER BY rowid')}
    previous=read(folder/'progress.json');elapsed=previous.get('elapsed_seconds',0) if resume else 0
    start=time.monotonic();state=dict(previous,status='running',started_at=previous.get('started_at',now()),plan_sha256=seal['plan'])
    specs={s['id']:s for s in plan['candidates']}
    reference={'id':'frozen_v1_recipe','kind':'ridge','block':'core','current':False,'alpha':10.}
    write(folder/'environment.json',{'python':sys.version,'runtime':str(Path(sys.executable).relative_to(ROOT)),
        'versions':{n:importlib.metadata.version(n) for n in ['numpy','scipy','scikit-learn','joblib','threadpoolctl']},
        'threads':1,'shared_dependencies_modified':False})

    def update():
        state.update(completed=len(done),actual_estimator_fits=sum(j['estimator_fits'] for j in done.values()),
            elapsed_seconds=round(elapsed+time.monotonic()-start,4),updated_at=now())
        state['percent']=100*state['completed']/state['total'];write(folder/'progress.json',state)

    def commit(job):
        connection.execute('INSERT INTO jobs VALUES(?,?)',(job['key'],json.dumps(job,ensure_ascii=False,allow_nan=False)))
        connection.commit();done[job['key']]=job
        state['events'].append({'seconds':round(elapsed+time.monotonic()-start,4),'completed':len(done),
            'fits':sum(j['estimator_fits'] for j in done.values())});update()

    def selection(prefix,splits):
        scores=[]
        for spec in plan['candidates']:
            predictions=[]
            for f,split in enumerate(splits):
                key=prefix+'/inner/'+spec['id']+'/'+str(f)
                if key not in done:
                    state['active']={'phase':prefix,'candidate':spec['id'],'inner_fold':f+1}
                    job,_=evaluate(key,'inner',spec,records,split['train'],split['test']);commit(job)
                predictions+=done[key]['predictions']
            scores.append({'candidate':spec['id'],**score(predictions,records)})
        selected=min(scores,key=lambda s:s['mae'])['candidate']
        key=prefix+'/selection'
        if key not in done:
            commit({'key':key,'stage':'selection','selected_id':selected,'scores':scores,'estimator_fits':0,'warnings':[]})
        else:assert done[key]['selected_id']==selected
        return selected

    def outer_predictions():
        rows=[]
        for job in done.values():
            if job['stage'] in ['outer_selected','outer_reference']:
                variant='v1_1_nested' if job['stage']=='outer_selected' else 'v1_recipe_same_cohort'
                rows.extend(p|{'variant':variant,'selected_candidate':job['candidate'],
                    'assessment':assess_prediction(p['predicted_pct'],p['input_warnings'])} for p in job['predictions'])
                if job['stage']=='outer_reference':
                    rows.extend(p|{'variant':'source_mean','selected_candidate':'source_mean',
                        'predicted_pct':job['target_center'],
                        'assessment':assess_prediction(job['target_center'])} for p in job['predictions'])
        return rows

    try:
        update()
        for split in plan['outer_folds']:
            prefix='outer/'+str(split['fold']);selected=selection(prefix,split['inner'])
            for stage,spec,is_reference in [('outer_selected',specs[selected],False),('outer_reference',reference,True)]:
                key=prefix+'/'+stage
                if key not in done:
                    job,_=evaluate(key,stage,spec,records,split['train'],split['test'],is_reference);commit(job)
            state['predictions']=outer_predictions();update()
        all_predictions=outer_predictions()
        base=[p for p in all_predictions if p['variant']=='v1_recipe_same_cohort']
        mean=[p for p in all_predictions if p['variant']=='source_mean']
        scores=[]
        for variant in ['v1_1_nested','v1_recipe_same_cohort','source_mean']:
            rows=[r for r in all_predictions if r['variant']==variant]
            scores.append({'variant':variant,'rows':42,'sources':30,**score(rows,records),
                'vs_reference':paired_bootstrap(rows,base),'vs_mean':paired_bootstrap(rows,mean)})
        state['metrics']=scores;update()
        selected=selection('final',plan['final_selection_folds']);state['selected_id']=selected
        # A final model is a research refit; its own training rows are never scored as external tests.
        if 'final/refit' not in done:
            tick=time.monotonic()
            with warnings.catch_warnings(record=True) as caught,threadpool_limits(limits=1):
                final=PositiveRetentionModel(specs[selected]).fit(records)
            joblib.dump(final,folder/'model_v1_1.joblib',compress=3)
            write(folder/'model_schema.json',{'numeric':final.encoder.schema,'semantic':final.semantic_schema})
            example={k:v for k,v in records[0].items() if k not in ['retention_pct','endpoint_id','source_group','sample_name','material_key','curve_group']}
            write(folder/'inference_example.json',[example]);write(folder/'inference_example_output.json',final.predict_with_context([example]))
            commit({'key':'final/refit','stage':'final_refit','candidate':selected,'train':list(range(42)),'test':[],
                'training_sources':final.training_sources,'schema':final.encoder.schema,'semantic_schema':final.semantic_schema,
                'target_center':final.center,'target_scale':final.scale,'reference':False,'predictions':[],
                'estimator_fits':1,'warnings':[str(w.message) for w in caught],'seconds':time.monotonic()-tick})
        results={'run_id':plan['run_id'],'selected_id':selected,'selected_specification':specs[selected],
            'evaluation':'Exploratory nested source CV on already-used42rows/30sources; not independent external validation.',
            'metrics':scores,'actual_estimator_fits':sum(j['estimator_fits'] for j in done.values()),'tasks':len(done),
            'warnings':[{'job':j['key'],'messages':j['warnings']} for j in done.values() if j['warnings']],
            'new_semantic_features_used_in_selected_model':specs[selected]['block']=='material',
            'positive_output_parameterization':True,'upper_clipping':False,
            'scientific_reliability_approved':False,'fresh_independent_validation_available':False,
            'no_model_reselection_from_outer_scores':True,'model_sha256':sha(folder/'model_v1_1.joblib')}
        assert results['tasks']==plan['total_tasks'] and results['actual_estimator_fits']==plan['total_fits']
        write(folder/'outer_predictions.json',all_predictions)
        write(folder/'selected.json',{'selected_id':selected,'specification':specs[selected],
            'rule':plan['selection'],'selection_scores':done['final/selection']['scores']})
        state.update(status='complete',active=None);update();results['elapsed_seconds']=state['elapsed_seconds']
        write(folder/'results.json',results)
        print(json.dumps({'selected':selected,'metrics':scores,'fits':results['actual_estimator_fits'],
            'warnings':len(results['warnings']),'seconds':results['elapsed_seconds']},ensure_ascii=False))
    except Exception:
        state.update(status='failed',error=traceback.format_exc());update();raise
    finally:connection.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--run-dir',type=Path,required=True);parser.add_argument('--resume',action='store_true')
    args=parser.parse_args();run(args.run_dir,args.resume)
