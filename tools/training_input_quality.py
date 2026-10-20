"""Model-free checks and training-fold-only numeric encoding. No estimator is run."""
from __future__ import annotations
import collections, copy, math, statistics

CATEGORICAL={'electrolyte','reference_electrode'}
FORBIDDEN={'endpoint_id','identity_key','source_group','sample_name','retention_pct','post_cycle_EIS','post_cycle_XPS','final_capacitance'}

def prepare_source_fold(dataset,split,drop_reported_current=False):
    """Prepare one grouped fold. Vocabulary and scale statistics use training rows only.

    Unknown held-out categories get a separate declared unknown bucket. Labels never
    contribute to encoding. This function does not train an ML estimator.
    """
    dataset.feature_matrix()  # Reject non-admitted/missing/wrong-target inputs.
    train=list(split['train']);test=list(split['test']);excluded=list(split.get('outer_holdout',[]));n=len(dataset.rows)
    if not train or not test or set(train)&set(test) or (set(train)|set(test))&set(excluded) or set(train)|set(test)|set(excluded)!=set(range(n)):
        raise ValueError('Nonempty disjoint train/test partition required.')
    tg={dataset.rows[i]['source_group'] for i in train};vg={dataset.rows[i]['source_group'] for i in test}
    if tg&vg:raise ValueError('Study group leakage.')
    excluded_groups={dataset.rows[i]['source_group'] for i in excluded}
    if excluded_groups&(tg|vg):raise ValueError('Outer study group leakage.')
    features=[f for f in dataset.features if not(drop_reported_current and f=='reported_current_A_g')]
    if set(features)&FORBIDDEN:raise ValueError('Forbidden predictor.')
    schema=[];columns=[]
    for f in features:
        values=[dataset.rows[i][f] for i in train]
        if f in CATEGORICAL:
            categories=sorted(set(values));schema.append({'field':f,'kind':'categorical','vocabulary':categories})
            columns += [f+'='+x for x in categories]+[f+'=<UNKNOWN>']
        else:
            mean=statistics.fmean(values);scale=statistics.pstdev(values) or 1.0
            schema.append({'field':f,'kind':'numeric','mean':mean,'scale':scale});columns.append(f)
    def encode(ids):
        matrix=[]
        for i in ids:
            row=dataset.rows[i];out=[]
            for s in schema:
                value=row[s['field']]
                if s['kind']=='numeric':out.append((value-s['mean'])/s['scale'])
                else:out += [float(value==c) for c in s['vocabulary']]+[float(value not in s['vocabulary'])]
            if any(not math.isfinite(v) for v in out):raise ValueError('Nonfinite encoded feature.')
            matrix.append(out)
        return matrix
    def weights(ids):
        counts=collections.Counter(dataset.rows[i]['source_group'] for i in ids)
        return [1/counts[dataset.rows[i]['source_group']] for i in ids]
    return {'X_train':encode(train),'X_validation':encode(test),
            'y_train':[dataset.rows[i]['retention_pct'] for i in train],
            'y_validation':[dataset.rows[i]['retention_pct'] for i in test],
            'train_indices':train,'validation_indices':test,'outer_holdout_indices':excluded,'feature_names':columns,'training_only_schema':schema,
            'train_source_weights':weights(train),'validation_source_weights':weights(test),
            'training_source_groups':sorted(tg),'validation_source_groups':sorted(vg),
            'research_training_authorized':False,'estimators_fitted':0}

def assess(dataset):
    matrix=dataset.feature_matrix();rows=dataset.rows;groups=sorted(set(matrix['groups']))
    folds=dataset.source_folds(len(groups));checks=[]
    def check(name,ok):
        if not ok:raise AssertionError(name)
        checks.append(name)
    check('approved_core_matrix',len(matrix['X'])==len(rows))
    check('no_forbidden_predictors',not(set(dataset.features)&FORBIDDEN))
    check('multiple_groups_for_validation',len(groups)>=3)
    seen=[]
    for k,fold in enumerate(folds):
        out=prepare_source_fold(dataset,fold);seen+=fold['test']
        check('finite_fold_'+str(k),all(math.isfinite(v) for row in out['X_train']+out['X_validation'] for v in row))
        check('equal_source_weight_'+str(k),all(abs(sum(w for i,w in zip(out['train_indices'],out['train_source_weights']) if rows[i]['source_group']==g)-1)<1e-10 for g in out['training_source_groups']))
        # A held-out extreme/categorical/label mutation must never alter training statistics.
        perturbed=copy.deepcopy(dataset)
        for i in fold['test']:
            for f in dataset.features:
                perturbed.rows[i][f]='HELDOUT_CATEGORY_SENTINEL' if f in CATEGORICAL else (999999999 if f!='cycle_voltage_lower_V' else -999999999)
            # Keep a valid voltage interval while changing every held-out numeric field.
            perturbed.rows[i]['cycle_voltage_upper_V']=1000000000
            perturbed.rows[i]['retention_pct']=99999
        second=prepare_source_fold(perturbed,fold)
        check('heldout_does_not_change_training_'+str(k),out['training_only_schema']==second['training_only_schema'] and out['X_train']==second['X_train'])
        control=prepare_source_fold(dataset,fold,drop_reported_current=True)
        check('no_current_control_'+str(k),'reported_current_A_g' not in control['feature_names'])
    check('each_record_held_once',sorted(seen)==list(range(len(rows))))
    # Guard the real public preparation API against accidental row-based splitting.
    leaking=None
    for g in groups:
        ids=[i for i,r in enumerate(rows) if r['source_group']==g]
        if len(ids)>1:leaking={'test':[ids[0]],'train':[i for i in range(len(rows)) if i!=ids[0]]};break
    if leaking:
        try:prepare_source_fold(dataset,leaking)
        except ValueError:checks.append('within_study_split_rejected')
        else:raise AssertionError('Leakage split accepted')
    values=[r['retention_pct'] for r in rows]
    categories={f:{v:len({r['source_group'] for r in rows if r[f]==v}) for v in sorted({r[f] for r in rows})} for f in dataset.features if f in CATEGORICAL}
    return {'status':'ready_for_exploratory_grouped_baseline_inputs','rows':len(rows),'source_groups':len(groups),
            'core_missing_cells':0,'target_min':min(values),'target_max':max(values),'target_mean':statistics.fmean(values),
            'retention_above_100_records':[r['endpoint_id'] for r in rows if r['retention_pct']>100],
            'category_source_group_counts':categories,'singleton_categories':{f:[v for v,n in d.items() if n==1] for f,d in categories.items()},
            'model_fits':0,'research_training_authorized':False,'quality_checks':checks,
            'scientific_limits':['Small study count; no reliable generalization or large-model sufficiency claim.',
                'Reported A/g denominators may differ; no canonical current inferred.',
                'Sparse electrolyte/reference categories cannot support broad categorical effect claims.',
                'Shared publication/reuse groups must remain together in outer and inner validation.']}
