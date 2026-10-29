"""Independent checks of sources, feature provenance, metrics and frozen artifacts. No estimator fit."""
from pathlib import Path
import collections,json,math,sqlite3,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import numpy as np,joblib
from tools.prepare_model_v13 import RUN,TASKS,read,write,sha
from data.training_latest import open_training_datasets

def verify(save=False):
    checks=collections.Counter()
    def ck(k,v):
        assert v,k
        checks[k]+=1
    plan=read(RUN/'training_plan.json');data=read(RUN/'input_snapshot.json');results=read(RUN/'results.json');state=read(RUN/'progress.json')
    ck('frozen_before_fitting',plan['frozen_at']<=state['started_at']and results['plan_sha256']==sha(RUN/'training_plan.json')and results['snapshot_sha256']==sha(RUN/'input_snapshot.json'))
    for k,h in read(RUN/'frozen_run_hashes.json').items():ck('frozen_plan_code_snapshot',sha((RUN if k.endswith('.json')else ROOT)/k)==h)
    for k,h in read(RUN/'protected_inputs.json').items():ck('unchanged_originals_history_inputs',sha(ROOT/k)==h)
    db=sqlite3.connect((RUN/'evaluation.sqlite').as_uri()+'?mode=ro',uri=True)
    ck('evaluation_integrity',db.execute('pragma integrity_check').fetchone()[0]=='ok')
    fits={k:json.loads(v)for k,v in db.execute('select *from fits')};stack={k:json.loads(v)for k,v in db.execute('select *from stacked_features')};db.close()
    ck('exact508fits',len(fits)==508==state['completed']==results['actual_estimator_fits']and state['status']=='completed')
    ck('stage_counts',collections.Counter(x['stage']for x in fits.values())=={'retention':140,'assisting_helper':280,'standalone_auxiliary':88})
    ck('preselected_primary_not_score_winner',plan['primary']==results['primary_preselected']=='latest_assisted_ridge')
    lookup={(r['task'],r['row_id']):r for rs in data.values()for r in rs};main={r['row_id']:r for r in data['retention']}
    g=sorted({r['source_family']for r in main.values()});expected=set()
    for fold in range(35):
        prefix='main/'+(str(fold)if fold<34 else 'refit')
        expected|={prefix+'/'+v for v in plan['retention_recipes']}
        expected|={prefix+'/cross'+str(j)+'/'+n for j in range(3)for n in ['capacity','BET']}
        expected|={prefix+'/helper/'+n for n in ['capacity','BET']}
        blocked={g[fold]}if fold<34 else set();train=[r for r in main.values()if r['source_family']not in blocked];test=[r for r in main.values()if r['source_family']in blocked]
        ck('stacked_rows_complete',len(stack[prefix])==2*(len(train)+len(test)))
        for assignment in stack[prefix]:
            helper=fits[assignment['helper_fit']];row=main[assignment['row_id']];i=helper['query_rows'].index(row['row_id'])
            ck('generated_auxiliary_value_receipt',assignment['value']==helper['predictions'][i])
            ck('query_source_never_in_helper_training',row['source_family']not in helper['train_sources']and not(blocked&set(helper['train_sources'])))
            ck('crossfit_or_outer_role',assignment['role']==('outer_test'if row['source_family']in blocked else'crossfit_training'))
    for name in ['capacity','BET']:
        expected|={name+'/'+str(i)for i in range(len({r['source_family']for r in data[name]}))}|{name+'/refit'}
    ck('exact_planned_jobs',expected==set(fits))
    candidates=collections.defaultdict(list)
    for row in read(RUN/'fact_use_candidates.json'):candidates[(row['task'],row['row_id'])].append(row)
    actual_used=set();facts_by_task=collections.defaultdict(set)
    p=plan['input_pointer']
    with open_training_datasets(ROOT/p['directory']/p['database_file'],p['sha256'])as d:
        c=d.connection;facts={r['fact_id']:json.loads(r['record_json'])for r in c.execute('select *from facts')}
        for name,task in TASKS.items():
            current={r['row_id']:r for r in d.rows(task)};ck('exact_api_task_membership',set(current)=={r['row_id']for r in data[name]})
            for r in data[name]:ck('targets_and_source_groups_unchanged',r['target']==current[r['row_id']]['target']and r['source_family']==current[r['row_id']]['source_family'])
    for key,job in fits.items():
        rows=[lookup[(job['train_task'],i)]for i in job['train_rows']]
        actual_groups={r['source_family']for r in rows}
        ck('train_source_receipts',actual_groups==set(job['train_sources']))
        ck('all_tasks_source_disjoint',not actual_groups&(set(job['query_sources'])|set(job['blocked_sources'])))
        if job['stage']!='retention':
            name='capacity'if job['train_task']==TASKS['capacity']else'BET'
            ck('all_eligible_aux_rows_used',set(job['train_rows'])=={r['row_id']for r in data[name]if r['source_family']not in job['blocked_sources']})
        if key.endswith('/latest_assisted_ridge'):
            additions=collections.defaultdict(dict)
            for x in stack[key.rsplit('/',1)[0]]:
                if x['role']=='crossfit_training':additions[x['row_id']][x['field']]=x['value']
            rows=[dict(r,features=dict(r['features'],**additions[r['row_id']]))for r in rows]
        enabled={x['field']for x in job['schema']if x['enabled']};fraction=.2 if job['stage']=='retention'else .1
        for item in job['schema']:
            field=item['field'];observed=[r for r in rows if r['features'].get(field)is not None];support=len({r['source_family']for r in observed})
            ck('training_only_support_selection',support==item['source_support']and len(observed)==item['observed_rows']and item['enabled']==(support>=3 and len(observed)/len(rows)>=fraction))
            if item['enabled']and item['kind']=='categorical':
                levels={r['features'][field]for r in observed};vocab=sorted(v for v in levels if len({r['source_family']for r in observed if r['features'][field]==v})>=3)
                ck('training_only_category_vocabulary',vocab==item['vocabulary'])
            if item['enabled']and item['kind']=='numeric':
                vals=np.array([r['features'][field]for r in observed],float);z=np.log1p(vals)if item['log1p']else vals
                count=collections.Counter()
                for r in observed:count[r['source_family']]+=r['quality_weight']
                w=np.array([r['quality_weight']/count[r['source_family']]for r in observed]);center=np.average(z,weights=w);sd=np.sqrt(np.average((z-center)**2,weights=w))or 1
                ix=np.argsort(z,kind='stable');med=z[ix][np.searchsorted(w[ix].cumsum(),w.sum()/2)]
                ck('training_only_imputation_and_scaling',abs(center-item['center'])<1e-11 and abs(sd-item['scale'])<1e-11 and abs(med-item['impute'])<1e-11)
        job_used=set()
        for r in rows:
            for use in candidates[(r['task'],r['row_id'])]:
                f=r['feature_mapping'].get(use['feature'],use['feature'])
                if use['role']=='target'or(f in enabled and r['features'].get(f)is not None):
                    fact=facts[use['fact_id']];v=r['target']if use['role']=='target'else r['features'][f]
                    ck('actual_numeric_fact_values',fact['value']==v and v is not None)
                    job_used.add(use['fact_id']);facts_by_task[r['task']].add(use['fact_id'])
        ck('actual_fit_fact_receipts',job_used==set(job['actual_fact_ids']));actual_used|=job_used
    utilization=read(RUN/'actual_fact_utilization.json');ck('actual_unique_facts_not_catalog_connections',actual_used==set(utilization['fact_ids'])and len(actual_used)==results['unique_numeric_material_facts_fitted'])
    masks=read(RUN/'training_projection_masks.json');ck('four_area_ratio_masks',len(masks)==4 and all(x['field']=='micro_to_meso_surface_area_ratio__v2'for x in masks))
    ck('BET_no_same_block_leak',all(not any(s in f for s in ['BET_','pore','surface_area'])for r in data['BET']for f in r['features']))
    out=read(RUN/'outer_predictions.json')
    baseline={r['row_id']:r for r in out['retention_baselines']}
    for recipe in plan['retention_recipes']:
        p={r['row_id']:r for r in out[recipe]};gs=sorted({r['source_family']for r in data['retention']});deltas=[]
        for group in gs:
            rows=[r for r in data['retention']if r['source_family']==group]
            deltas.append(np.mean([abs(p[r['row_id']]['predicted']-r['target'])-abs(baseline[r['row_id']]['mean']-r['target'])for r in rows]))
        deltas=np.array(deltas);idx=np.random.default_rng(20261029).integers(0,len(gs),(5000,len(gs)));lo,hi=np.quantile(deltas[idx].mean(1),[.025,.975]);receipt=results['metrics'][recipe]['vs_mean']
        ck('independent_paired_source_bootstrap',abs(lo-receipt['delta_low'])<1e-12 and abs(hi-receipt['delta_high'])<1e-12 and abs(deltas.mean()-receipt['delta_mae'])<1e-12)
    def metrics(rows,values):
        count=collections.Counter()
        for r in rows:count[r['source_family']]+=r['quality_weight']
        w=np.array([r['quality_weight']/count[r['source_family']]for r in rows]);y=np.array([r['target']for r in rows]);p=np.array(values);mse=np.average((p-y)**2,weights=w)
        return dict(mae=float(np.average(abs(p-y),weights=w)),rmse=float(np.sqrt(mse)),r2=float(1-mse/np.average((y-np.average(y,weights=w))**2,weights=w)))
    for variant in plan['retention_recipes']+['capacity','BET']:
        name=variant if variant in ['capacity','BET']else'retention';rows=data[name];pred={r['row_id']:r for r in out[variant]};ck('complete_outer_predictions',set(pred)=={r['row_id']for r in rows})
        calc=metrics(rows,[pred[r['row_id']]['predicted']for r in rows]);expected=results['metrics'][variant]['model']if name!='retention'else results['metrics'][variant]
        ck('independent_source_weighted_metrics',all(abs(calc[k]-expected[k])<1e-10 for k in calc))
        for row in rows:ck('observed_label_unchanged',pred[row['row_id']]['observed']==row['target'])
    for name,h in results['actual_model_files'].items():ck('saved_model_hash',sha(RUN/name)==h)
    saved_primary=joblib.load(RUN/'latest_assisted_ridge.joblib')
    held_out={r['row_id']for r in data['retention']}
    ck('full_final_research_refit',set(saved_primary.main.training_rows)==held_out)
    ck('all_final_auxiliary_task_rows_fitted',set(saved_primary.helpers['capacity'].training_rows)=={r['row_id']for r in data['capacity']}and set(saved_primary.helpers['BET'].training_rows)=={r['row_id']for r in data['BET']})
    saved=joblib.load(RUN/'latest_assisted_ridge.joblib');example=read(RUN/'inference_example.json')
    ck('saved_assisted_model_reloaded',np.allclose(saved.predict(example['inputs']),example['research_refit_predictions_pct'],rtol=0,atol=1e-12))
    primary=results['metrics']['latest_assisted_ridge'];base=results['metrics']['mean_baseline'];median=results['metrics']['median_baseline']
    ck('honest_acceptance_and_scope',results['acceptance_passed']==(primary['mae']<min(base['mae'],median['mae'])and primary['vs_mean']['delta_high']<0)and not results['reliable_for_design']and not results['independent_external_validation'])
    ck('original_pending_and_unsealed',read(RUN/'input_audit.json')['original_pending']==37 and not plan['unsealed_v8_used'])
    result=dict(status='passed',checks=sum(checks.values()),groups=dict(checks),actual_estimator_fits=508,verification_estimator_fits=0,all_tasks_source_isolation=True,actual_unique_facts=len(actual_used),primary=primary,plan_sha256=sha(RUN/'training_plan.json'))
    if save:write(RUN/'verification.json',result)
    print(json.dumps({k:v for k,v in result.items()if k!='groups'},ensure_ascii=False))
if __name__=='__main__':verify('--save'in sys.argv)
