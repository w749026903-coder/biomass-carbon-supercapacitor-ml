"""Read-only verification of the frozen experiment; performs no estimator fitting."""
from pathlib import Path
import collections,csv,io,json,math,sqlite3,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import joblib,numpy as np
from tools.train_model_v1 import read,write,sha
from tools.prepare_model_v12 import RUN,PROCESS
from models.v1_2.model import Encoder,weights,weighted_median
from models.v1_1.model import derive_semantics
from data.cycling_db import open_database

def verify(save=False):
    checks=[]
    def ck(name,ok):
        assert ok,name
        checks.append(name)
    snapshot=read(RUN/'input_snapshot.json');records=snapshot['records'];features=snapshot['features'];plan=read(RUN/'training_plan.json');result=read(RUN/'results.json');state=read(RUN/'progress.json')
    ck('plan_snapshot',sha(RUN/'input_snapshot.json')==plan['snapshot_sha256']);ck('frozen_plan',sha(RUN/'training_plan.json')==result['plan_sha256'])
    for name,h in read(RUN/'frozen_run_hashes.json').items():ck('frozen_code:'+name,sha((RUN if name.endswith('.json') else ROOT)/name)==h)
    for name,h in read(RUN/'protected_inputs.json').items():ck('protected:'+name,sha(ROOT/name)==h)
    ck('actual_progress560',state['status']=='completed' and state['completed']==state['actual_estimator_fits']==result['estimator_fits']==560)
    ck('planned_not_expanded',len(plan['candidates'])==5 and plan['planned_estimator_fits']==560)
    ck('47rows34families',len(records)==47 and len({r['source_group'] for r in records})==34)
    ck('50provenance_fields',len(features)==50 and not set(features)&{'retention_pct','endpoint_id','source_group','sample_name','N_at_pct','O_at_pct','capacitance_F_g'})
    c=sqlite3.connect((RUN/'evaluation.sqlite').as_uri()+'?mode=ro',uri=True)
    ck('SQL_integrity',c.execute('pragma integrity_check').fetchone()[0]=='ok')
    jobs={k:json.loads(v) for k,v in c.execute('select key,record_json from fits')};selections={k:json.loads(v) for k,v in c.execute('select key,record_json from selections')};c.close()
    counts=collections.Counter(j['stage'] for j in jobs.values());ck('560actual_fit_receipts',len(jobs)==560 and counts=={'inner':525,'outer':34,'refit':1})
    ck('35train_only_selections',len(selections)==35)
    specs={s['id']:s for s in plan['candidates']};expected=set()
    for k,split in enumerate(plan['outer_folds']):
        for spec in plan['candidates']:
            for n,s in enumerate(split['inner']):
                key=f'outer{k}/{spec["id"]}/{n}';expected.add(key);j=jobs[key]
                ck('inner_indices:'+key,j['train']==s['train'] and j['test']==s['test'] and set(j['train']+j['test'])==set(split['train']))
        expected.add(f'outer{k}/selected')
    for spec in plan['candidates']:
        for n,s in enumerate(plan['final_selection_folds']):
            key=f'final/{spec["id"]}/{n}';expected.add(key);ck('finalCV_indices:'+key,jobs[key]['train']==s['train'] and jobs[key]['test']==s['test'])
    expected.add('final/refit');ck('exact_expected_jobs',set(jobs)==expected)
    for key,j in jobs.items():
        train=[records[i] for i in j['train']];test=[records[i] for i in j['test']]
        ck('source_isolation:'+key,not {r['source_group'] for r in train}&{r['source_group'] for r in test})
        ck('train_sources_receipt:'+key,sorted({r['source_group'] for r in train})==j['train_sources'])
        e=Encoder(specs[j['candidate']],features).fit(train)
        ck('preprocessing_training_only:'+key,e.schema==j['schema'])
        z=np.log(np.array([r['retention_pct'] for r in train])/100);w=weights(train);center=float(np.average(z,weights=w));scale=math.sqrt(float(np.average((z-center)**2,weights=w))) or 1.
        ck('target_statistics_training_only:'+key,abs(center-j['target_center'])<1e-13 and abs(scale-j['target_scale'])<1e-13)
        for item in j['schema']:
            if item['kind']=='numeric' and item['field'] not in CORE:ck('optional_source_support:'+key+item['field'],not item['enabled'] or item['source_support']>=5)
            if item['kind']=='categorical':ck('categorical_source_support:'+key+item['field'],all(item['source_support'][v]>=3 for v in item['vocabulary']))
    def independent_metrics(rs,p):
        count=collections.Counter(r['source_group'] for r in rs);w=np.array([1/count[r['source_group']] for r in rs]);y=np.array([r['retention_pct'] for r in rs]);p=np.array(p)
        mse=np.average((y-p)**2,weights=w);var=np.average((y-np.average(y,weights=w))**2,weights=w)
        return dict(mae=float(np.average(abs(y-p),weights=w)),rmse=float(np.sqrt(mse)),r2=float(1-mse/var))
    prefixes={f'outer{k}':split['inner'] for k,split in enumerate(plan['outer_folds'])}|{'final':plan['final_selection_folds']}
    for prefix,splits in prefixes.items():
        scores=[]
        for spec in plan['candidates']:
            ids=[];p=[]
            for k,s in enumerate(splits):ids+=s['test'];p+=jobs[f'{prefix}/{spec["id"]}/{k}']['predictions']
            scores.append(dict(candidate=spec['id'],**independent_metrics([records[i] for i in ids],p)))
        selected=min(scores,key=lambda x:x['mae'])['candidate'];ck('inner_selection_recomputed:'+prefix,selected==selections[prefix]['selected'])
        for actual,recomputed in zip(selections[prefix]['scores'],scores):ck('inner_score_recomputed:'+prefix+actual['candidate'],all(abs(actual[k]-recomputed[k])<1e-11 for k in ['mae','rmse','r2']))
    predictions=read(RUN/'outer_predictions.json');by_id={r['endpoint_id']:r for r in predictions};ck('exact47heldout',set(by_id)=={r['endpoint_id'] for r in records})
    for k,split in enumerate(plan['outer_folds']):
        j=jobs[f'outer{k}/selected'];ck('outer_uses_own_inner_selection:'+str(k),j['candidate']==selections[f'outer{k}']['selected'])
        tr=[records[i] for i in split['train']];y=np.array([r['retention_pct'] for r in tr]);w=weights(tr)
        for i,p in zip(split['test'],j['predictions']):
            r=records[i];v=by_id[r['endpoint_id']]
            ck('outer_prediction:'+r['endpoint_id'],v['observed_pct']==r['retention_pct'] and v['predicted_pct']==p and p>0 and v['predicted_ratio']==p/100)
            ck('mean_median_training_only:'+r['endpoint_id'],v['source_mean_pct']==float(np.average(y,weights=w)) and v['source_median_pct']==weighted_median(y,w))
    for score,field in zip(result['metrics'],['predicted_pct','source_mean_pct','source_median_pct']):
        values=[by_id[r['endpoint_id']][field] for r in records];m=independent_metrics(records,values)
        ck('outer_metrics:'+score['variant'],all(abs(score[k]-m[k])<1e-12 for k in m))
        source_errors=[]
        for group in sorted({r['source_group'] for r in records}):
            rs=[by_id[r['endpoint_id']] for r in records if r['source_group']==group]
            ae=np.mean([abs(r[field]-r['observed_pct']) for r in rs]);base=np.mean([abs(r['source_mean_pct']-r['observed_pct']) for r in rs])
            source_errors.append([ae,ae-base])
        errors=np.array(source_errors);idx=np.random.default_rng(20261028).integers(0,34,size=(5000,34));bounds=np.quantile(errors[idx].mean(axis=1),[.025,.975],axis=0)
        ck('descriptive_bootstrap:'+score['variant'],abs(bounds[0,1]-score['vs_mean']['delta_low'])<1e-12 and abs(bounds[1,1]-score['vs_mean']['delta_high'])<1e-12)
    ck('final_selected_by_finalCV',result['final_candidate']==selections['final']['selected']==jobs['final/refit']['candidate'])
    model=joblib.load(RUN/'model_v1_2.joblib');ck('saved_model_hash',sha(RUN/'model_v1_2.joblib')==result['model_sha256'])
    ck('saved_model_training_rows',model.training_endpoint_ids==[r['endpoint_id'] for r in records]);ck('saved_model_training_sources',model.training_sources==sorted({r['source_group'] for r in records}))
    ck('inference_roundtrip',model.predict_with_context(read(RUN/'inference_example.json'))==read(RUN/'inference_example_output.json'))
    for wrong in [dict(read(RUN/'inference_example.json')[0],system='2E_symmetric'),dict(read(RUN/'inference_example.json')[0],method='CV')]:
        try:model.predict_with_context([wrong])
        except ValueError:checks.append('unsupported_protocol_rejected')
        else:raise AssertionError('Unsupported inference accepted')
    with open_database()as d:
        raw={r['endpoint_id']:r for r in d.fetch('reported_3e').rows};matrix=d.method_specific_material_matrix('reported_3e');xs={k:dict(zip(matrix['feature_names'],row)) for k,row in zip(matrix['endpoint_ids'],matrix['X'])}
        for r in records:
            original=raw[r['endpoint_id']];ck('original_target:'+r['endpoint_id'],r['retention_pct']==original['retention_pct'])
            for f,v in xs[r['endpoint_id']].items():ck('selected_matrix_projection:'+r['endpoint_id']+f,r[f]==v)
            for f in PROCESS:ck('own_selected_stage:'+r['endpoint_id']+f,r[f]==original.get(f))
            ck('unchanged_semantics:'+r['endpoint_id'],all(r[f]==v for f,v in derive_semantics(original).items()))
        ck('37pending_still_held',len(d.reviewed_pending_batch())==37);ck('all287unchanged',len(d.fetch('all_review').rows)==287)
    audit=read(RUN/'input_audit.json');ck('15oldfreezes',audit['old_feature_freeze_count']==15);ck('unsealed_and_aux_not_used',not audit['auxiliary_learning_used'] and not audit['unsealed_batch27_used'])
    if (RUN/'historical_overlap_audit.json').exists():
        correction=read(RUN/'historical_overlap_audit.json');ck('normalized_historical_overlap30',audit['historical_overlap']['current_groups_already_in_v11']==30 and audit['historical_overlap']['common_endpoint_ids']==42)
        ck('historical_correction_original_retained',correction['original_historical_overlap']['current_groups_already_in_v11']==0 and sha(RUN/'input_audit.json')==correction['corrected_input_audit_sha256'])
        for name,h in correction['unchanged'].items():ck('postrun_metadata_did_not_change_training:'+name,sha(RUN/name)==h)
    ck('not_claiming_independent_or_reliable',not result['independent_external_validation'] and not result['reliable_for_design'])
    if (RUN/'selected_source_file_verification.json').exists():
        sourcecheck=read(RUN/'selected_source_file_verification.json');ck('46source_file_pairs',sourcecheck['known_source_pairs']==sourcecheck['matched']==46)
        for item in sourcecheck['checks']:
            p=Path(item['path']);p=p if p.is_absolute() else ROOT/p
            ck('selected_original_source_SHA:'+item['path'],sha(p)==item['sha256_expected'])
    if (RUN/'report_visual_verification.json').exists():ck('browser_QA',read(RUN/'report_visual_verification.json')['passed'])
    report=dict(status='passed',checks=len(checks),protected_files=len(read(RUN/'protected_inputs.json')),actual_estimator_fits=560,verification_estimator_fits=0,
        rows=47,source_families=34,original_pending=37,model_sha256=sha(RUN/'model_v1_2.joblib'),plan_sha256=sha(RUN/'training_plan.json'),check_names=checks)
    if save:write(RUN/'verification.json',report)
    else:assert read(RUN/'verification.json')==report
    if (RUN/'merge_manifest.json').exists():
        for item in read(RUN/'merge_manifest.json')['outputs']:assert sha(ROOT/item['path'])==item['sha256'],item['path']
    print(json.dumps({k:v for k,v in report.items() if k!='check_names'}))

from models.v1_2.model import CORE
if __name__=='__main__':verify('--save' in sys.argv)
