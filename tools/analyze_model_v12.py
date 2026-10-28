"""Post-run summaries only; normalizes historical DOI spellings, with correction receipt."""
from pathlib import Path
import collections,json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import joblib,numpy as np
from tools.train_model_v1 import read,write,sha
from tools.prepare_model_v12 import RUN
from data.literature_current import open_literature_database
from models.v1_2.model import weights

def analyze():
    snapshot=read(RUN/'input_snapshot.json');rows=snapshot['records'];pred=read(RUN/'outer_predictions.json');result=read(RUN/'results.json')
    old=read(ROOT/'模型逐项优化_v1.1_20261022/input_snapshot.json')['records']
    with open_literature_database()as d:
        oldgroups={d.isolation_group(r['source_group']) for r in old};newgroups={r['source_group'] for r in rows}
    normalized=dict(prior_rows=len(old),prior_groups=len(oldgroups),current_groups_already_in_v11=len(newgroups&oldgroups),
        current_groups_not_in_v11=sorted(newgroups-oldgroups),common_endpoint_ids=len({r['endpoint_id'] for r in old}&{r['endpoint_id'] for r in rows}),
        interpretation='All this run is exploratory. Bare DOI and doi: spellings refer to the same source; no prospectively untouched external test was designated.')
    audit=read(RUN/'input_audit.json')
    if not (RUN/'historical_overlap_audit.json').exists():
        correction=dict(kind='postrun_descriptive_metadata_correction_not_training_change',original_input_audit_sha256=sha(RUN/'input_audit.json'),
            original_historical_overlap=audit['historical_overlap'],corrected_historical_overlap=normalized,
            cause='Initial descriptive overlap compared bare historical DOIs with new doi: family keys using lower() only. Actual training used normalized current family keys throughout.',
            unchanged={n:sha(RUN/n) for n in ['training_plan.json','input_snapshot.json','model_v1_2.joblib','evaluation.sqlite','outer_predictions.json','results.json']})
        audit['historical_overlap']=normalized;audit['historical_overlap_correction']='historical_overlap_audit.json';write(RUN/'input_audit.json',audit)
        correction['corrected_input_audit_sha256']=sha(RUN/'input_audit.json');write(RUN/'historical_overlap_audit.json',correction)
    else:assert audit['historical_overlap']==normalized
    assert normalized['current_groups_already_in_v11']==30 and normalized['common_endpoint_ids']==42
    w=weights(rows);squared=w*np.array([r['error_pct']**2 for r in pred]);shares=[]
    for group in sorted(newgroups):
        ids=[i for i,r in enumerate(pred) if r['source_group']==group]
        shares.append(dict(source=group,weighted_squared_error_share=float(squared[ids].sum()/squared.sum()),rows=len(ids)))
    shares.sort(key=lambda r:-r['weighted_squared_error_share'])
    schema=read(RUN/'model_schema.json');selection=collections.Counter(r['candidate'] for r in read(RUN/'outer_selections.json'))
    post=dict(outer_selection_counts=dict(selection),final_enabled_numeric=sum(s['kind']=='numeric' and s['enabled'] for s in schema),
        final_categorical_fields=sum(s['kind']=='categorical' for s in schema),
        final_disabled_numeric=[s['field'] for s in schema if s['kind']=='numeric' and not s['enabled']],
        worst_predictions=sorted(pred,key=lambda r:-abs(r['error_pct']))[:7],source_squared_error_shares=shares,
        legitimate_growth_records=[r for r in pred if r['observed_pct']>100],
        feature_use_qualification='Material candidates selected in all34 outer training folds, but this is not a controlled estimate of any single feature effect. No separate post-hoc ablation fitting.',
        improvement_qualification='RMSE below mean baseline; MAE essentially equal and paired delta interval spans zero. Predefined acceptance did not pass.',
        model_fits_in_analysis=0)
    write(RUN/'postrun_analysis.json',post)
    card=dict(model='v1.2',task='Reviewed biomass-derived porous-carbon3E GCD retention at specified cycles and reported protocol',
        rows=47,source_families=34,source_database='cycling_v0.29',literature_database='literature_pool_v26',
        authorization='User request2026-10-28: 接续到下一个对话并尝试训练一次',
        selected_candidate=result['final_candidate'],feature_catalogue=50,enabled_numeric=post['final_enabled_numeric'],categorical_fields=post['final_categorical_fields'],
        final_model_sha256=sha(RUN/'model_v1_2.joblib'),input_snapshot_sha256=sha(RUN/'input_snapshot.json'),
        metrics=result['metrics'],independent_external_validation=False,reliable_for_design=False,
        positive_prediction=True,upper_clipped=False,calibrated_prediction_interval=None,
        forbidden_uses=['2E or CV protocols','engineering design guarantees','unreviewed material/composite/gel extrapolation','treating all-library capacity reports as cycling labels'],
        metadata_correction='Historical DOI overlap count corrected with retained original count/receipt; no training input, split, weights or scores changed.')
    write(RUN/'model_card.json',card)
    print(json.dumps(dict(historical_overlap=normalized,selection_counts=dict(selection),top3_squared_error_share=sum(r['weighted_squared_error_share'] for r in shares[:3]),analysis_fits=0),ensure_ascii=False))
if __name__=='__main__':analyze()
