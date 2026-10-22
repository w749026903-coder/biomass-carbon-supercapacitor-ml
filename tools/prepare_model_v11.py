"""Audit units and own-source labels; freeze the next experimental improvement plan."""
from pathlib import Path
from collections import Counter
import datetime
import hashlib
import json
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from data.cycling_db import open_database
from models.v1_1.model import SEMANTIC, derive_semantics, assess_prediction

RUN=ROOT/'模型逐项优化_v1.1_20261022'
PARENT=ROOT/'模型v1.0_来源留出训练_20261022'


def read(p): return json.loads(p.read_text('utf-8'))
def sha(p):
    with p.open('rb') as f: return hashlib.file_digest(f,'sha256').hexdigest()
def write(p,v): p.write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')


def prepare():
    if RUN.exists(): raise ValueError('New run directory required.')
    RUN.mkdir()
    previous=read(PARENT/'data_snapshot.json')
    recipes={r['endpoint_id']:r for r in read(ROOT/'主集参数精提取_20261022/reviewed_parameters.json')['records']}
    primary_requests=[('CCL-K2CO3-1-700','10.1016/j.biombioe.2026.109168','109.2'),
        ('NPC-700-6','10.1016/j.jenvman.2025.125582','106.3'),('CA-AA','10.1039/d3ra07014j','101.35'),
        ('AC_rice_straw','10.1039/d6na00276e','83.54'),('OAC623','10.1007/s00339-023-07141-8','85.5')]
    with open_database() as db:
        current=db.fetch('reported_3e')
        assert current.fingerprint()==previous['dataset_fingerprint']
        allrows=db.fetch('all_review').rows
        raw={r['endpoint_id']:r for r in current.rows}
        records=[]; semantics_evidence=[]
        for old in previous['records']:
            source=raw[old['endpoint_id']]
            semantic=derive_semantics(source)
            records.append(old|semantic)
            recipe=recipes[old['endpoint_id']]
            semantics_evidence.append({'endpoint_id':old['endpoint_id'],'source_group':old['source_group'],
                'raw_methods':{k:source.get(k) for k in ['activation_agent_v14','activation_applicability_v14','precursor_v14']},
                'derived_features':semantic,'evidence':recipe['evidence'],
                'qualification':'Derived taxonomy from v0.14 agent-reviewed own methods, not new expert sign-off; unknown remains missing.'})
        reviews=[]
        for name,doi,token in primary_requests:
            row=next(r for r in current.rows if r['sample_name']==name)
            matches=db.search_native(token,doi=doi,limit=10)
            if name=='NPC-700-6': matches=[m for m in matches if m.get('format')=='pdf']
            if not matches: raise ValueError('Own-source label passage missing: '+name)
            match=matches[0]
            source_path=Path(match['path']);source_path=source_path if source_path.is_absolute() else ROOT/source_path
            reviews.append({'endpoint_id':row['endpoint_id'],'sample_name':name,'doi':doi,
                'retention_pct':row['retention_pct'],'retention_ratio':row['retention_pct']/100.,
                'locator':match['locator'],'path':source_path.relative_to(ROOT).as_posix(),'sha256':sha(source_path),
                'native_segment':match.get('map_id',match.get('segment_id')),
                'decision':'Retain the own3E original percentage; do not upper-clip or substitute device/Coulombic-efficiency values.',
                'review_summary':{'CCL-K2CO3-1-700':'50000cycles; own main text explicitly increases to109.2percent of initial; wetting/activation is an author hypothesis.',
                    'NPC-700-6':'50000cycles; initial decline followed by recovery and106.3percent; preserve nonmonotonic behavior.',
                    'CA-AA':'Own3E101.35percent is distinct from its2E102percent; do not substitute abstract device value.',
                    'AC_rice_straw':'Own bareAC83.54percent is distinct from AC-ZnO89.98percent and Coulombic efficiency75percent.',
                    'OAC623':'Own original capacitance85.5percent at1000cycles; same as14.5percent loss, not 0.855percent.'}[name]})
    values=[r for r in allrows if isinstance(r.get('retention_pct'),(int,float))]
    audit={'review_observations':len(allrows),'numeric_retention_values':len(values),'missing_retention_values':len(allrows)-len(values),
        'stored_unit':'percent_0_to100_scale_not_bounded_above100',
        'conversion':'retention_ratio=retention_pct/100; inverse pct=100*ratio',
        'negative_values':[r['endpoint_id'] for r in values if r['retention_pct']<0],
        'possible_fraction_in_pct_field':[r['endpoint_id'] for r in values if 0<r['retention_pct']<=1],
        'above100_review_rows':sum(r['retention_pct']>100 for r in values),
        'above100_main_rows':[{'endpoint_id':r['endpoint_id'],'sample_name':r['sample_name'],'retention_pct':r['retention_pct']} for r in records if r['retention_pct']>100],
        'all_review_warning':'Review observations include excluded/held records; unit scan does not grant admission or validate all20 above100 labels.',
        'screenshot_value_review':assess_prediction(101.23917325206921),
        'data_changed':False,'target_values_clipped':False}
    write(RUN/'unit_audit.json',audit);write(RUN/'critical_source_review.json',reviews)
    write(RUN/'semantic_feature_evidence.json',semantics_evidence)
    write(RUN/'input_snapshot.json',{'records':records,'dataset_fingerprint':current.fingerprint(),
        'parent_snapshot_sha256':sha(PARENT/'data_snapshot.json'),'new_semantic_fields':SEMANTIC})
    support={f:{v:len({r['source_group'] for r in records if r[f]==v}) for v in sorted({r[f] for r in records if r[f] is not None})} for f in SEMANTIC}
    write(RUN/'semantic_coverage.json',{'rows':42,'sources':30,'field_source_support':support,
        'raw_precursor_names_not_predictors':True,'semantic_categorical_minimum_training_sources':3,
        'numeric_optional_minimum_training_sources':5,'labels_or_sample_ids_used_for_taxonomy':False})
    # Real source-table opportunities remain candidates until their own complete review.
    write(RUN/'additional_sample_candidates.json',{'source_doi':'10.1039/d3ra07014j','same_existing_source':True,
        'training_eligible':False,'source_url':'https://pubs.rsc.org/en/content/articlehtml/2024/ra/d3ra07014j',
        'locator':'OwnTable1 and Fig7a prose, distinct from2E Fig7b',
        'samples':[{'sample':'CA-TB','BET_m2_g':455.83,'retention_pct':114.36},
                   {'sample':'CA-W','BET_m2_g':571.82,'retention_pct':106.99},
                   {'sample':'CA-C','BET_m2_g':210.49,'retention_pct':99.07}],
        'remaining':'Per-test full protocol/window/reference/material-residue and duplicate review before database promotion; no new independent source count.'})
    candidates=[{'id':f'positive_{block}_{"I" if current else "noI"}_{alpha}',
        'block':block,'current':current,'alpha':float(alpha)} for block in ['core','material'] for current in [False,True] for alpha in [10,100]]
    groups=sorted({r['source_group'] for r in records})
    outer=[]
    for k,g in enumerate(groups):
        train=[i for i,r in enumerate(records) if r['source_group']!=g]
        inner_groups=[x for x in groups if x!=g]
        buckets={x:n%5 for n,x in enumerate(inner_groups)}
        inner=[{'train':[i for i in train if buckets[records[i]['source_group']]!=f],
                'test':[i for i in train if buckets[records[i]['source_group']]==f]} for f in range(5)]
        outer.append({'fold':k+1,'source':g,'train':train,'test':[i for i,r in enumerate(records) if r['source_group']==g],'inner':inner})
    final_buckets={g:n%5 for n,g in enumerate(groups)}
    final_folds=[{'train':[i for i,r in enumerate(records) if final_buckets[r['source_group']]!=f],
                 'test':[i for i,r in enumerate(records) if final_buckets[r['source_group']]==f]} for f in range(5)]
    stamp=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()
    plan={'run_id':'retention-v1.1-sequential-20261022','authorization':{'authorized':True,
        'user_request':'这保持率都出现超过1的了。列出我们要改进的地方，一个一个优化',
        'scope':'Unit and source audit, semantic feature projection, one bounded positive-target experiment and risk-aware research inference; no data relabeling, services or giant pretraining.'},
        'created_at':stamp,'database_pointer':read(ROOT/'data/current_database.json'),'dataset_fingerprint':current.fingerprint(),
        'snapshot_sha256':sha(RUN/'input_snapshot.json'),'rows':42,'sources':30,
        'target':'log(retention_pct/100), transformed only with training-fold weighted statistics; inverse100*exp; positive predictions, no upper cap or clipping.',
        'candidates':candidates,'outer_folds':outer,'final_selection_folds':final_folds,
        'selection':'Minimum inner pooled source-equal MAE, tie by candidate order. One frozen nested selection rule; no selection based on outer results.',
        'reference':'The frozen v1.0 direct-target core no-current Ridge alpha10 refitted on each identical outer training set.',
        'validation_limits':'All42rows/30sources are already reviewed and evaluated development data, including the previously used7; this is exploratory nested source CV, not a new independent test.',
        'categorical_source_threshold':3,'numeric_optional_source_threshold':5,'seed':42,'threads':1,
        'bootstrap':'5000 paired source resamples of outer errors, seed20261023; descriptive conditional intervals, no calibrated sample interval.',
        'total_fits':1301,'total_tasks':1332,'final_full_data_refit':True,
        'deployment_gate':'Always exploratory until fresh independent sources validate it; engineering checks or positive outputs do not confer scientific reliability.',
        'stop_rule':'Run only these8 candidates and this selection rule. Report all results, no further tuning based on outer scores.',
        'documentation':['https://pubs.rsc.org/en/content/articlehtml/2024/ra/d3ra07014j',
            'https://scikit-learn.org/1.7/modules/cross_validation.html#cross-validation-iterators-for-grouped-data']}
    # 30*(8*5 + selected_outer + reference)=1260; final40+refit1=1301 fits.
    write(RUN/'training_plan.json',plan)
    protected={str(p.relative_to(ROOT).as_posix()):sha(p) for p in [PARENT/'run_manifest.json',PARENT/'data_snapshot.json',ROOT/'data/current_database.json',
        ROOT/plan['database_pointer']['version_directory']/plan['database_pointer']['database_file'],
        ROOT/'主集参数精提取_20261022/reviewed_parameters.json']}
    write(RUN/'protected_inputs.json',protected)
    write(RUN/'progress.json',{'status':'planned','completed':0,'total':1332,'percent':0,'actual_estimator_fits':0,'elapsed_seconds':0,'events':[],'metrics':[],'predictions':[]})
    write(RUN/'optimization_checklist.json',{'steps':[
        {'id':1,'task':'单位与超过100%的科学解释','status':'complete','evidence':'unit_audit.json'},
        {'id':2,'task':'五个重点样品原文复核','status':'complete','evidence':'critical_source_review.json'},
        {'id':3,'task':'三类工艺与原料语义特征标准化','status':'complete','evidence':'semantic_feature_evidence.json'},
        {'id':4,'task':'固定正值目标与相同来源的嵌套对照','status':'planned','evidence':'training_plan.json'},
        {'id':5,'task':'双单位显示、可靠性提示与交互核验','status':'in_progress'},
        {'id':6,'task':'独立困难来源与进一步样品准入','status':'requires_further_source_review','evidence':'additional_sample_candidates.json'}],
        'no_claim_all_scientific_gaps_resolved':True})
    print(json.dumps({'prepared':True,'rows':42,'sources':30,'candidates':8,'fits_planned':1301,'semantic_source_support':support},ensure_ascii=False))


if __name__=='__main__': prepare()
