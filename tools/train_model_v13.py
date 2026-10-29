"""Run exactly the frozen 508 fits, preserving per-fit data and source receipts."""
from pathlib import Path
import collections, json, sqlite3, sys, time, traceback, warnings
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import joblib,numpy as np
from threadpoolctl import threadpool_limits
from models.v1_3.model import Regressor,AssistedModel,weights,scores
from tools.prepare_model_v13 import RUN,TASKS,read,write,sha,now,split3

def bootstrap(rows,p,reference):
    gs=sorted({r['source_family']for r in rows});errors=[]
    for g in gs:
        ids=[i for i,r in enumerate(rows)if r['source_family']==g]
        errors.append(np.mean([abs(p[i]-rows[i]['target'])-abs(reference[i]-rows[i]['target'])for i in ids]))
    errors=np.array(errors);idx=np.random.default_rng(20261029).integers(0,len(gs),(5000,len(gs)));lo,hi=np.quantile(errors[idx].mean(1),[.025,.975])
    return dict(delta_mae=float(errors.mean()),delta_low=float(lo),delta_high=float(hi),resamples=5000,descriptive_not_prediction_interval=True)

def run():
    assert not (RUN/'evaluation.sqlite').exists()and not(RUN/'results.json').exists(), 'Do not restart or overwrite fits'
    plan=read(RUN/'training_plan.json');data=read(RUN/'input_snapshot.json')
    for k,h in read(RUN/'frozen_run_hashes.json').items():assert sha((RUN if k.endswith('.json')else ROOT)/k)==h,k
    for k,h in read(RUN/'protected_inputs.json').items():assert sha(ROOT/k)==h,k
    assert plan['authorization']['authorized']and plan['primary']=='latest_assisted_ridge'
    db=sqlite3.connect(RUN/'evaluation.sqlite');db.execute('create table fits(key text primary key,record_json text not null)');db.execute('create table stacked_features(key text primary key,record_json text not null)');db.commit()
    start=time.monotonic();state=read(RUN/'progress.json');state.update(status='running',started_at=now());fits=0
    candidates=collections.defaultdict(list)
    for r in read(RUN/'fact_use_candidates.json'):candidates[(r['task'],r['row_id'])].append(r)
    used=collections.defaultdict(set);used_by_role=collections.defaultdict(set);allmodels={};outpred=collections.defaultdict(list)
    def update():
        state.update(completed=fits,percent=100*fits/508,updated_at=now(),elapsed_seconds=round(time.monotonic()-start,3));write(RUN/'progress.json',state)
    def fit(key,rows,query,kind,stage,blocked=(),fraction=.2):
        nonlocal fits
        tr_groups={r['source_family']for r in rows};te_groups={r['source_family']for r in query}
        assert not tr_groups & (te_groups|set(blocked)), key
        assert len(tr_groups)>=3
        with warnings.catch_warnings(record=True)as caught,threadpool_limits(limits=1):
            m=Regressor(kind,fraction).fit(rows);p=m.predict(query).tolist()if query else []
        enabled={s['field']for s in m.encoder.schema if s['enabled']};jobfacts=set()
        for r in rows:
            for use in candidates.get((r['task'],r['row_id']),[]):
                field=r['feature_mapping'].get(use['feature'],use['feature'])
                if use['role']=='target'or(field in enabled and r['features'].get(field)is not None):
                    used[r['task']].add(use['fact_id']);used_by_role[use['role']].add(use['fact_id']);jobfacts.add(use['fact_id'])
        record=dict(key=key,stage=stage,kind=kind,train_task=rows[0]['task'],train_rows=m.training_rows,train_sources=m.training_sources,
                    query_rows=[r['row_id']for r in query],query_sources=sorted(te_groups),blocked_sources=sorted(blocked),schema=m.encoder.schema,
                    predictions=p,actual_fact_ids=sorted(jobfacts),warnings=[str(x.message)for x in caught],actual_estimator_fits=1,
                    target_center=m.center,target_scale=m.scale)
        db.execute('insert into fits values(?,?)',(key,json.dumps(record,ensure_ascii=False,allow_nan=False)));db.commit();fits+=1
        state['events'].append(dict(completed=fits,elapsed_seconds=round(time.monotonic()-start,3)));state['active']=key;update()
        return m,p
    def means(rows,query):
        y=np.array([r['target']for r in rows]);w=weights(rows);idx=np.argsort(y,kind='stable');median=y[idx][np.searchsorted(np.cumsum(w[idx]),w.sum()/2)]
        return [float(np.average(y,weights=w))]*len(query),[float(median)]*len(query)
    def helper_query(rs):
        # This is an inference query, not copying fresh GCD measurements into cycle evidence.
        return [dict(r,features=dict(r['features'],voltage_lower_V=r['features'].get('cycle_voltage_lower_V'),voltage_upper_V=r['features'].get('cycle_voltage_upper_V')))for r in rs]
    try:
        update();legacy={r['row_id']:r for r in data['legacy']};groups=sorted({r['source_family']for r in data['retention']})
        for fold,g in enumerate(groups+[None]):
            prefix='main/'+(str(fold)if g is not None else 'refit');blocked={g}if g else set()
            tr=[r for r in data['retention']if r['source_family']not in blocked];te=[r for r in data['retention']if r['source_family']in blocked]
            mu,md=means(tr,te)
            for r,a,b in zip(te,mu,md):outpred['retention_baselines'].append(dict(row_id=r['row_id'],source_family=r['source_family'],observed=r['target'],mean=a,median=b))
            for recipe,kind,rs in [('legacy_input_ridge','ridge',[legacy[r['row_id']]for r in tr]),('latest_ridge','ridge',tr),('latest_trees','trees',tr)]:
                qs=[legacy[r['row_id']]for r in te]if recipe=='legacy_input_ridge'else te
                m,p=fit(prefix+'/'+recipe,rs,qs,kind,'retention',blocked)
                if g is None:allmodels[recipe]=m
                else:
                    for r,v in zip(te,p):outpred[recipe].append(dict(row_id=r['row_id'],source_family=r['source_family'],observed=r['target'],predicted=v))
            enriched={r['row_id']:dict(r,features=dict(r['features']))for r in tr};assignments=[];helpers={}
            for j,(_,crossquery)in enumerate(split3(tr)):
                excluded=blocked|{r['source_family']for r in crossquery}
                for name in ['capacity','BET']:
                    aux=[r for r in data[name]if r['source_family']not in excluded]
                    key=prefix+'/cross'+str(j)+'/'+name;m,p=fit(key,aux,helper_query(crossquery),'trees','assisting_helper',excluded,.1)
                    for r,v in zip(crossquery,p):
                        field='aux_predicted_'+name;enriched[r['row_id']]['features'][field]=v
                        assignments.append(dict(row_id=r['row_id'],field=field,value=v,helper_fit=key,role='crossfit_training'))
            enriched_test=[dict(r,features=dict(r['features']))for r in te]
            for name in ['capacity','BET']:
                aux=[r for r in data[name]if r['source_family']not in blocked];key=prefix+'/helper/'+name
                helpers[name],p=fit(key,aux,helper_query(te),'trees','assisting_helper',blocked,.1)
                for r,v in zip(enriched_test,p):
                    field='aux_predicted_'+name;r['features'][field]=v
                    assignments.append(dict(row_id=r['row_id'],field=field,value=v,helper_fit=key,role='outer_test'))
            db.execute('insert into stacked_features values(?,?)',(prefix,json.dumps(assignments)));db.commit()
            m,p=fit(prefix+'/latest_assisted_ridge',[enriched[r['row_id']]for r in tr],enriched_test,'ridge','retention',blocked)
            if g is None:allmodels['latest_assisted_ridge']=AssistedModel(m,helpers)
            else:
                for r,v in zip(te,p):outpred['latest_assisted_ridge'].append(dict(row_id=r['row_id'],source_family=r['source_family'],observed=r['target'],predicted=v))
            state['completed_retention_sources']=fold+1 if g else len(groups);update()
        for name in ['capacity','BET']:
            groups=sorted({r['source_family']for r in data[name]})
            for i,g in enumerate(groups+[None]):
                excluded={g}if g else set();tr=[r for r in data[name]if r['source_family']not in excluded];te=[r for r in data[name]if r['source_family']in excluded]
                m,p=fit(name+'/'+('refit'if g is None else str(i)),tr,te,'trees','standalone_auxiliary',excluded,.1)
                if g is None:allmodels[name]=m
                mu,md=means(tr,te)
                for r,v,a,b in zip(te,p,mu,md):outpred[name].append(dict(row_id=r['row_id'],source_family=r['source_family'],observed=r['target'],predicted=v,mean=a,median=b,quality_weight=r['quality_weight']))
        assert fits==508
        results={};base={r['row_id']:r for r in outpred['retention_baselines']}
        for recipe in plan['retention_recipes']:
            pred={r['row_id']:r['predicted']for r in outpred[recipe]};rs=data['retention'];p=[pred[r['row_id']]for r in rs];mu=[base[r['row_id']]['mean']for r in rs]
            results[recipe]=dict(**scores(rs,p),vs_mean=bootstrap(rs,p,mu))
        rs=data['retention'];mu=[base[r['row_id']]['mean']for r in rs];md=[base[r['row_id']]['median']for r in rs]
        results['mean_baseline']=scores(rs,mu);results['median_baseline']=scores(rs,md)
        for name in ['capacity','BET']:
            pp={r['row_id']:r for r in outpred[name]};rs=data[name]
            results[name]=dict(model=scores(rs,[pp[r['row_id']]['predicted']for r in rs]),mean_baseline=scores(rs,[pp[r['row_id']]['mean']for r in rs]),rows=len(rs),sources=len({r['source_family']for r in rs}))
        for name,m in allmodels.items():joblib.dump(m,RUN/(name+'.joblib'),compress=3)
        write(RUN/'outer_predictions.json',dict(outpred));all_used=set().union(*used.values())
        write(RUN/'actual_fact_utilization.json',dict(unique_material_numeric_fact_ids_used=len(all_used),fact_ids=sorted(all_used),by_task={k:sorted(v)for k,v in used.items()},
            by_role={k:sorted(v)for k,v in used_by_role.items()},denominator_connected_inputs=3727,not_all_connected_inputs_claimed_fitted=True,
            counts_are_union_across_this_finite_experiment_not_independent_samples=True,all_747_task_rows_used_in_final_research_refits=True))
        primary=results[plan['primary']];passed=primary['mae']<min(results[k]['mae']for k in ['mean_baseline','median_baseline'])and primary['vs_mean']['delta_high']<0
        result=dict(run_id=plan['run_id'],primary_preselected=plan['primary'],metrics=results,acceptance_passed=bool(passed),reliable_for_design=False,
            independent_external_validation=False,actual_estimator_fits=fits,unique_numeric_material_facts_fitted=len(all_used),actual_model_files={n+'.joblib':sha(RUN/(n+'.joblib'))for n in allmodels},
            plan_sha256=sha(RUN/'training_plan.json'),snapshot_sha256=sha(RUN/'input_snapshot.json'),elapsed_seconds=round(time.monotonic()-start,3),
            stop_completed_no_post_score_candidates=True,notes='All fixed recipes reported. Best outer score is not a separately validated model-selection procedure. No new cycling admissions or clipping.')
        write(RUN/'results.json',result)
        # Check the final assisted artifact uses the same helper predictions as its receipt.
        refit=allmodels['latest_assisted_ridge'];p=refit.predict(data['retention'][:2]);loaded=joblib.load(RUN/'latest_assisted_ridge.joblib');assert np.allclose(p,loaded.predict(data['retention'][:2]),rtol=0,atol=1e-12)
        write(RUN/'inference_example.json',dict(inputs=data['retention'][:2],research_refit_predictions_pct=p.tolist(),not_held_out_validation=True,reliable_for_design=False))
        for k,h in read(RUN/'protected_inputs.json').items():assert sha(ROOT/k)==h,k
        state.update(status='completed',finished_at=now(),active=None,acceptance_passed=bool(passed));update()
        print(json.dumps(result,ensure_ascii=False))
    except BaseException:
        state.update(status='failed',error=traceback.format_exc());update();raise
    finally:db.close()
if __name__=='__main__':run()
