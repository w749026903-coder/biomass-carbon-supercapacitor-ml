"""Execute exactly the frozen finite experiment, with durable actual-fit progress."""
from pathlib import Path
import collections,json,sqlite3,sys,time,warnings,traceback
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import numpy as np
import joblib
from threadpoolctl import threadpool_limits
from models.v1_2.model import RetentionModel,metrics,weights,weighted_median
from tools.train_model_v1 import read,write,sha,now
from tools.prepare_model_v12 import RUN

def bootstrap(pred,base,records):
    groups=sorted({r['source_group'] for r in records})
    errors=np.array([[np.mean([abs(pred[i]-records[i]['retention_pct']) for i,r in enumerate(records) if r['source_group']==g]),
                     np.mean([abs(pred[i]-records[i]['retention_pct'])-abs(base[i]-records[i]['retention_pct']) for i,r in enumerate(records) if r['source_group']==g])] for g in groups])
    idx=np.random.default_rng(20261028).integers(0,len(groups),size=(5000,len(groups)));lo,hi=np.quantile(errors[idx].mean(axis=1),[.025,.975],axis=0)
    return dict(mae_low=float(lo[0]),mae_high=float(hi[0]),delta_mae=float(errors[:,1].mean()),delta_low=float(lo[1]),delta_high=float(hi[1]),resamples=5000,independent_prediction_interval=False)

def run():
    assert not (RUN/'results.json').exists() and not (RUN/'evaluation.sqlite').exists(),'Completed/partial runs need explicit diagnosis, never silently overwrite.'
    plan=read(RUN/'training_plan.json');snapshot=read(RUN/'input_snapshot.json');records=snapshot['records'];features=snapshot['features']
    assert plan['authorization']['authorized'] and sha(RUN/'input_snapshot.json')==plan['snapshot_sha256']
    frozen=read(RUN/'frozen_run_hashes.json')
    for name,h in frozen.items():assert sha((RUN if name.endswith('.json') else ROOT)/name)==h,name
    for name,h in read(RUN/'protected_inputs.json').items():assert sha(ROOT/name)==h,name
    db=sqlite3.connect(RUN/'evaluation.sqlite');db.execute('create table fits(key text primary key,record_json text not null)');db.execute('create table selections(key text primary key,record_json text not null)');db.commit()
    state=read(RUN/'progress.json');state.update(status='running',started_at=now(),metrics=[]);start=time.monotonic();fits=0
    allpred={name:{} for name in ['nested','source_mean','source_median']};specs={s['id']:s for s in plan['candidates']}
    def update():
        state.update(completed=fits,actual_estimator_fits=fits,percent=100*fits/560,elapsed_seconds=round(time.monotonic()-start,3),updated_at=now())
        write(RUN/'progress.json',state)
    def fit(key,spec,train,test,stage):
        nonlocal fits
        tr=[records[i] for i in train];te=[records[i] for i in test]
        assert not {r['source_group'] for r in tr}&{r['source_group'] for r in te}
        with warnings.catch_warnings(record=True) as caught,threadpool_limits(limits=1):
            m=RetentionModel(spec,features).fit(tr);p=m.predict(te) if te else []
        job=dict(key=key,stage=stage,candidate=spec['id'],train=train,test=test,train_sources=m.training_sources,
            test_sources=sorted({r['source_group'] for r in te}),schema=m.encoder.schema,target_center=m.center,target_scale=m.scale,
            kernel_gamma=getattr(m,'kernel_gamma',None),warnings=[str(w.message) for w in caught],predictions=[float(x) for x in p],
            input_warnings=[m.encoder.warnings(r) for r in te],actual_estimator_fits=1)
        db.execute('insert into fits values(?,?)',(key,json.dumps(job,ensure_ascii=False,allow_nan=False)));db.commit();fits+=1
        state['events'].append(dict(fits=fits,seconds=round(time.monotonic()-start,3)));state['active']=dict(stage=stage,key=key,candidate=spec['id']);update()
        return p,m
    def select(prefix,splits):
        scores=[]
        for spec in plan['candidates']:
            ids=[];pred=[]
            for k,split in enumerate(splits):
                p,_=fit(prefix+'/'+spec['id']+'/'+str(k),spec,split['train'],split['test'],'inner');ids+=split['test'];pred+=list(p)
            score=metrics([records[i] for i in ids],pred);scores.append(dict(candidate=spec['id'],**score))
        selected=min(scores,key=lambda s:s['mae'])['candidate']
        db.execute('insert into selections values(?,?)',(prefix,json.dumps(dict(selected=selected,scores=scores))));db.commit()
        return selected
    try:
        update()
        selections=[]
        for k,split in enumerate(plan['outer_folds']):
            selected=select('outer'+str(k),split['inner']);selections.append(dict(source=split['source'],candidate=selected))
            p,m=fit('outer'+str(k)+'/selected',specs[selected],split['train'],split['test'],'outer')
            tr=[records[i] for i in split['train']];y=np.array([r['retention_pct'] for r in tr]);w=weights(tr)
            mean=float(np.average(y,weights=w));median=weighted_median(y,w)
            for i,value in zip(split['test'],p):
                allpred['nested'][i]=float(value);allpred['source_mean'][i]=mean;allpred['source_median'][i]=median
            state['completed_outer_sources']=k+1
        assert all(set(v)==set(range(47)) for v in allpred.values())
        arrays={name:[p[i] for i in range(47)] for name,p in allpred.items()}
        scores=[dict(variant=name,**metrics(records,p),vs_mean=bootstrap(p,arrays['source_mean'],records)) for name,p in arrays.items()]
        state['metrics']=scores;update()
        selected=select('final',plan['final_selection_folds']);_,final=fit('final/refit',specs[selected],list(range(47)),[],'refit')
        assert fits==plan['planned_estimator_fits']==560
        joblib.dump(final,RUN/'model_v1_2.joblib',compress=3);write(RUN/'model_schema.json',final.encoder.schema)
        predictions=[dict(endpoint_id=r['endpoint_id'],sample_name=r['sample_name'],source_group=r['source_group'],observed_pct=r['retention_pct'],
            predicted_pct=arrays['nested'][i],predicted_ratio=arrays['nested'][i]/100,source_mean_pct=arrays['source_mean'][i],source_median_pct=arrays['source_median'][i],
            error_pct=arrays['nested'][i]-r['retention_pct'],above_initial_reference=bool(arrays['nested'][i]>100)) for i,r in enumerate(records)]
        write(RUN/'outer_predictions.json',predictions);write(RUN/'outer_selections.json',selections)
        main=scores[0];accepted=main['mae']<min(s['mae'] for s in scores[1:]) and main['vs_mean']['delta_high']<0
        result=dict(run_id=plan['run_id'],rows=47,source_families=34,estimator_fits=fits,final_candidate=selected,final_spec=specs[selected],
            metrics=scores,descriptive_acceptance_passed=bool(accepted),independent_external_validation=False,reliable_for_design=False,
            evaluation='Exploratory nested leave-one-source-family-out validation; all47 source-held-out predictions. Not new external validation; not directly comparable to old42/30 scores.',
            final_model='Refit on all47 reviewed rows; these training rows do not independently validate the saved weight.',
            positive_target_no_upper_clip=True,source_weighting='Each source family totals one; means/medians fit only on training sources',
            warnings_count=db.execute("select count(*)from fits where json_array_length(json_extract(record_json,'$.warnings'))>0").fetchone()[0],
            elapsed_seconds=round(time.monotonic()-start,3),model_sha256=sha(RUN/'model_v1_2.joblib'),plan_sha256=sha(RUN/'training_plan.json'))
        write(RUN/'results.json',result)
        example={k:v for k,v in records[0].items() if k not in ['retention_pct','source_group','raw_source_group','endpoint_id','sample_name']}
        write(RUN/'inference_example.json',[example]);write(RUN/'inference_example_output.json',final.predict_with_context([example]))
        for name,h in read(RUN/'protected_inputs.json').items():assert sha(ROOT/name)==h,name
        state.update(status='completed',finished_at=now(),active=None,final_candidate=selected,descriptive_acceptance_passed=bool(accepted));update()
        print(json.dumps(result,ensure_ascii=False))
    except BaseException:
        state.update(status='failed',error=traceback.format_exc());update();raise
    finally:db.close()

if __name__=='__main__':run()
