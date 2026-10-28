"""Independent v2 provenance, leakage, grouping and immutable-parent checks."""
from pathlib import Path
import collections,csv,io,json,math,sqlite3,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.improve_training_inputs_v2 import OUT,DB,BASE,sha,read,write,group,PRECURSOR_STAGES
from data.training_current import open_training_datasets,CurrentTrainingDatasets

def verify(save=False):
    counts=collections.Counter()
    def ck(name,ok):
        assert ok,name
        counts[name]+=1
    c=sqlite3.connect(DB.as_uri()+'?mode=ro',uri=True);c.row_factory=sqlite3.Row
    p=sqlite3.connect((BASE/'training_data_v1.sqlite').as_uri()+'?mode=ro',uri=True);p.row_factory=sqlite3.Row
    ck('sqlite_integrity',c.execute('pragma integrity_check').fetchone()[0]=='ok')
    ck('foreign_keys',not c.execute('pragma foreign_key_check').fetchall())
    for path,h in read(OUT/'protected_inputs.json').items():ck('protected_original_SHA',sha(ROOT/path)==h)
    for table in ['sources','facts','cycle_records','cycle_material_links','candidates','held_features','held_inputs','lineage_pairs']:
        ck('parent_table_unchanged_'+table,[tuple(r)for r in c.execute('select *from '+table)]==[tuple(r)for r in p.execute('select *from '+table)])
    facts={r['fact_id']:json.loads(r['record_json'])for r in c.execute('select *from facts')}
    parent_inputs={(r['task'],r['row_id']):json.loads(r['record_json'])for r in p.execute('select *from inputs')}
    inputs={(r['task'],r['row_id']):json.loads(r['record_json'])for r in c.execute('select *from inputs')}
    corrections=read(OUT/'quality_corrections.json');withdrawn={(r['task'],r['row_id'])for r in corrections['withdrawn_rows']}
    removed={tuple(r[k]for k in ['fact_id','task','row_id','feature','role'])for r in corrections['removed_receipts']}
    for key,old in parent_inputs.items():
        if key in withdrawn:
            ck('uncertainty_target_withdrawn_with_original_retained',key not in inputs and 'plusminus'in old['target_name']);continue
        v=inputs[key];ck('parent_labels_and_conditions_unchanged',v['target']==old['target']and v['target_name']==old['target_name']and v['conditions']==old['conditions'])
        for f,x in old['features'].items():
            if 'plusminus'in f:ck('uncertainty_removed_from_predictors',f not in v['features'])
            else:ck('no_parent_feature_overwrite',v['features'][f]==x)
    ck('old_receipts_preserved_except_documented_quality_correction',(set(map(tuple,p.execute('select *from fact_uses')))-removed)<=set(map(tuple,c.execute('select *from fact_uses'))))
    ann=read(BASE/'typed_feature_contract.json');desc=read(OUT/'typed_feature_contract_v2.json')
    def orig(f):
        if f.startswith(('lib__','precursor__')):f=f.split('__',1)[1]
        return desc.get(f,ann.get(f,{})).get('original_field',f)
    usage=collections.defaultdict(list)
    for r in c.execute('select *from fact_uses'):
        v=inputs[r['task'],r['row_id']];f=facts[r['fact_id']];value=v['target']if r['role']=='target'else v['features'][r['feature']]
        ck('every_numeric_receipt_matches_original_value',f['value']==value and value is not None)
        ck('receipt_same_material_or_explicit_precursor',f['material_key']==v['material_key']or(r['task'].startswith('lineage:')and f['material_key']==v['lineage_path'][0]))
        usage[r['fact_id']].append(dict(task=r['task'],row_id=r['row_id'],feature=r['feature'],role=r['role']))
    for key,v in inputs.items():
        ck('finite_target',isinstance(v['target'],(float,int))and math.isfinite(v['target']))
        if key[0].startswith(('material:','precursor:')):
            # Historical tasks keep their established grouping. Every added field
            # and all new tasks must additionally pass the broader v2 grouping.
            for f in v.get('v2_additions',[]) if key in parent_inputs else v['features']:
                ck('no_target_measurement_block_leakage',group(orig(f))!=v['excluded_target_measurement_block'])
        if key[0].startswith('precursor:'):
            ck('explicit_precursor_stage_only',v['conditions']['material_stage']in PRECURSOR_STAGES)
            ck('no_later_product_recipe_in_precursor_task',not any(f.startswith('process__')for f in v['features']))
        if key[0].startswith('cycle:'):
            ck('no_cycling_row_admission',key in parent_inputs)
    frozen=read(BASE/'cross_task_freeze_review.json')['material_blocks']
    for (task,rid),v in inputs.items():
        mk=v['lineage_path'][0]if task.startswith('lineage:')else v['material_key'];bb=frozen.get(mk,[])
        for ff in v['features']:
            f=orig(ff)
            ck('frozen_values_not_revived',not('N'in bb and f.startswith(('XPS_N_at_pct','XPS_N_wt_pct','XPS_N_reported_pct','XPS_C_to_N')))and not('O'in bb and f.startswith(('XPS_O_at_pct','XPS_O_wt_pct','XPS_O_reported_pct')))and not('Raman_ratio'in bb and f.startswith(('Raman_ID_IG','Raman_IG_ID','Raman_derived_crystallite'))))
    s=read(OUT/'summary.json');numeric={fid for fid in usage if facts[fid]['value']is not None};oldids={r[0]for r in p.execute('select distinct fact_id from fact_uses')}
    ck('independent_unique_usage',len(numeric)==s['numeric_facts_connected_to_training_inputs'])
    ck('new_connected_exactly245',numeric-oldids==set(read(OUT/'new_connected_fact_ids.json'))and len(numeric-oldids)==245)
    ck('4469_numeric_denominator',sum(f['value']is not None for f in facts.values())==4469)
    ck('201_nonpoint_preserved',sum(f['value']is None for f in facts.values())==201)
    for r in c.execute('select *from usage_ledger'):
        u=json.loads(r['record_json']);ck('ledger_matches_actual_receipts',sorted(u['uses'],key=str)==sorted(usage.get(r['fact_id'],[]),key=str))
        ck('ledger_disposition',bool(u['uses'])==(r['disposition']=='connected_to_training_inputs'))
    for r in c.execute('select *from measurement_metadata'):
        v=json.loads(r['record_json']);ck('metadata_is_not_predictor_credit',r['fact_id']not in numeric)
        ck('metadata_exact_original_receipt',v['source_receipt']==facts[r['fact_id']]and v['not_predictor']and v['not_independent_target'])
    for task in s['task_counts']:
        rows=[v for (t,_),v in inputs.items()if t==task];ck('task_counts',len(rows)==s['task_counts'][task]['rows']and len({r['source_family']for r in rows})==s['task_counts'][task]['source_families'])
    fold_checks=[]
    with open_training_datasets()as d:
        ck('main3e47_34',len(d.rows('cycle:reported_3e'))==47 and d.tasks()['cycle:reported_3e']['source_families']==34)
        ck('main2e31_25',len(d.rows('cycle:reported_2e'))==31 and d.tasks()['cycle:reported_2e']['source_families']==25)
        for family in sorted({v['source_family']for v in d.rows('cycle:reported_3e')}):
            z=d.source_split('cycle:reported_3e',[family]);ck('whole_source_split',not set(z['train']['groups'])&set(z['test']['groups']))
            for f in z['feature_names']:
                cov=next(x for x in z['training_coverage']if x['field']==f)
                ck('training_only_feature_support',cov['source_families']>=3 and cov['nonmissing_fraction']>=.2)
            fold_checks.append(dict(heldout_family=family,train_rows=len(z['train']['row_ids']),test_rows=len(z['test']['row_ids']),supported_columns=len(z['feature_names'])))
        family='10.3390/molecules31132329';z=d.source_split_bundle('cycle:reported_3e',[family]);excluded=d.family(family)
        for matrix in z['auxiliary_training'].values():ck('heldout_all_auxiliary_tasks',excluded not in matrix['groups'])
        for task in ['cycle:reported_3e','capacity:3e_reported','material:ordinary_biomass_pretest:BET_surface_area_m2_g']:
            mm=d.matrix(task);ck('source_equal_weights',all(abs(sum(w for w,g in zip(mm['sample_weight'],mm['groups'])if g==family)-1)<1e-10 for family in set(mm['groups'])))
        # Perturb held-out feature presence and EVERY target. Selection must stay
        # fixed; a full-data selection implementation would fail this test.
        fake=CurrentTrainingDatasets.__new__(CurrentTrainingDatasets)
        fake.rows=lambda task,exclude_sources=():[r for r in fake_data if r['source_family']not in {fake.family(x)for x in exclude_sources}]
        fake.rules=[]
        fake_data=[dict(row_id=str(i),source_family='doi:'+g,features=ff,target=i) for i,(g,ff) in enumerate([('a',{'x':1}),('b',{'x':2}),('c',{'x':3}),('held',{'held_only':9})])]
        a=fake.source_split('synthetic',['held'])['feature_names']
        for row in fake_data:row['target']=123456
        fake_data[-1]['features']={'x':None,'changed_test_only':100}
        ck('no_test_or_target_driven_feature_selection',a==fake.source_split('synthetic',['held'])['feature_names']==['x'])
    ck('new_fits_zero',s['new_model_fits']==0 and s['new_cycling_admissions']==0)
    result=dict(status='passed',checks=sum(counts.values()),groups=dict(counts),source_holdout_support_checks=fold_checks,database_sha256=sha(DB),new_model_fits=0)
    if save:write(OUT/'verification.json',result)
    else:ck('saved_verification_matches',read(OUT/'verification.json')==result)
    print(json.dumps(dict(status='passed',checks=result['checks'],sha256=result['database_sha256']),ensure_ascii=False))
    c.close();p.close()

if __name__=='__main__':verify('--save'in sys.argv)
