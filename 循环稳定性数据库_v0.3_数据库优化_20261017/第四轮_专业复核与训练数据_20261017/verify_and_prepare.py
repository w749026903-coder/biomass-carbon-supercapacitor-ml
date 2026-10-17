"""Validate evidence preservation, ready data, source splits and synthetic interfaces."""
from pathlib import Path
import collections, contextlib, copy, csv, hashlib, io, json, sqlite3, sys

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'modeling'))
from prepare_dataset import CONTRACT, connect, load_ready, preflight, validate_rows
from benchmark_engine import candidates_for, load_spaces, run_benchmark, source_disjoint, splitter, weights_for

checks=[]
def check(name,value):
    checks.append({'check':name,'passed':bool(value)})
    if not value:raise AssertionError(name)

def dump(path,obj):path.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def table_rows(c,name):return [tuple(r) for r in c.execute('SELECT * FROM "'+name+'" ORDER BY rowid')]

def reject(name,fn):
    try:fn()
    except (ValueError,RuntimeError):check(name,True)
    else:check(name,False)

def main():
    import numpy as np
    old=sqlite3.connect((ROOT.parent/'第三轮_逐条准入闭环_20261017/cycling_v0_3r3.sqlite').as_uri()+'?mode=ro',uri=True)
    with connect() as c:
        check('sqlite_integrity',c.execute('PRAGMA integrity_check').fetchone()[0]=='ok')
        check('foreign_keys',not list(c.execute('PRAGMA foreign_key_check')))
        for table in ['raw_records','cycling_endpoints','cycling_tests','papers','materials','endpoint_features','admissions',
                      'source_files','review_events','field_evidence','record_blockers','blocker_scopes',
                      'validation_group_assignments','validation_links','mass_definition_audits','material_observations']:
            check('unchanged_parent_table:'+table,table_rows(old,table)==table_rows(c,table))
        check('all89_endpoints_profile_reviewed',c.execute('SELECT COUNT(DISTINCT record_id) FROM profile_admissions_r4').fetchone()[0]==89)
        check('all267_profile_assessments',c.execute('SELECT COUNT(*) FROM profile_admissions_r4').fetchone()[0]==267)
        check('strict_canonical_still_zero',c.execute('SELECT COUNT(*) FROM training_ready_canonical_current').fetchone()[0]==0)
        check('legacy_denominator_gate_not_falsified',c.execute('SELECT COUNT(*) FROM admissions WHERE eligible=1').fetchone()[0]==0)
        check('three_new_records_have_source_group_receipts',c.execute("SELECT COUNT(*) FROM domain_reviews_r4 WHERE topic='source_group'").fetchone()[0]==3)
        check('six_SRC028_protocol_holds',c.execute("SELECT COUNT(*) FROM domain_reviews_r4 WHERE topic='device_protocol' AND decision='held_internal_voltage_and_electrolyte_scope'").fetchone()[0]==6)
        for rid in ['R107_CY02','SRC123_CY02','SRC112_CY01','R105_CY01','R017_CY01','R017_CY02']:
            check('not_promoted:'+rid,c.execute('SELECT SUM(eligible) FROM profile_admissions_r4 WHERE record_id=?',(rid,)).fetchone()[0]==0)
        # Complete source lineage for training rows, not only the final numeric matrix.
        keys=['cycle_count','current_density_A_g','electrolyte','concentration_value','voltage_lower_V','voltage_upper_V','BET_m2_g']
        ledger=[dict(r) for r in c.execute('SELECT * FROM field_evidence')]
        for profile in CONTRACT['label_relations_by_profile']:
            byid={r['record_id']:r for r in load_ready(profile)}
            for rid,row in byid.items():
                check('source_file_exists:'+profile+':'+rid,Path(row['evidence_path']).is_file())
        allrows=[dict(r) for r in c.execute('SELECT * FROM modeling_effective_inputs ORDER BY record_id')]
        routes={r['record_id']:dict(r) for r in c.execute('SELECT * FROM utilization_routes')}
        assessments={(r['record_id'],r['profile']):dict(r) for r in c.execute('SELECT * FROM profile_admissions_r4')}
        flat=[]
        for r in allrows:
            rec={k:r[k] for k in ['record_id','paper_id','material_id','sample_name','system','method','cycle_count','retention_pct','retention_relation']}
            rec.update(existing_track=routes[r['record_id']]['track'],review_extent=assessments[(r['record_id'],CONTRACT['default_profile'])]['review_extent'])
            for profile in CONTRACT['label_relations_by_profile']:
                a=assessments[(r['record_id'],profile)]
                rec[profile+'_eligible']=a['eligible'];rec[profile+'_reasons']=a['failures_json']
            flat.append(rec)
        with (ROOT/'exports/全部89端点_单行用途总表.csv').open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(flat[0]));w.writeheader();w.writerows(flat)
        dump(ROOT/'exports/全部89端点_单行用途总表.json',flat)
        for name in ['material_observations','field_evidence']:
            dump(ROOT/'exports'/f'{name}_全部保留.json',[dict(r) for r in c.execute('SELECT * FROM '+name)])
    old.close()
    plans={};profile_counts={}
    for profile,count in [('literature_core7_exact',8),('literature_residue_sensitivity',10),('literature_approx_sensitivity',11)]:
        rows=load_ready(profile);check('expected_count:'+profile,len(rows)==count)
        check('unique_endpoints:'+profile,len({r['record_id'] for r in rows})==count)
        check('unknown_denominator_preserved:'+profile,all(r['canonical_current_A_g'] is None and r['current_denominator_status']=='not_uniquely_defined' for r in rows))
        check('no_missing_core:'+profile,all(r[k] is not None for r in rows for k in CONTRACT['required_conditions']+['BET_m2_g']))
        check('author_current_unchanged:'+profile,all(r['reported_current_A_g']==r['current_density_A_g'] for r in rows))
        n_groups=len({r['study_group'] for r in rows});g=np.array([r['study_group'] for r in rows]);X=np.zeros((len(rows),1))
        plan=[]
        for fold,(tr,te) in enumerate(splitter(n_groups,CONTRACT['split']['folds_up_to'],CONTRACT).split(X,groups=g)):
            source_disjoint([rows[i] for i in tr],[rows[i] for i in te])
            check('source_split_disjoint:'+profile+':'+str(fold),not set(g[tr])&set(g[te]))
            w=weights_for(g[tr]);sums=[sum(w[j] for j,i in enumerate(tr) if g[i]==s) for s in sorted(set(g[tr]))]
            check('source_weights_equal:'+profile+':'+str(fold),np.allclose(sums,sums[0]))
            plan.append({'fold':fold,'train_ids':[rows[i]['record_id'] for i in tr],'test_ids':[rows[i]['record_id'] for i in te],
                         'train_groups':sorted(set(g[tr])),'test_groups':sorted(set(g[te]))})
        check('LOPO_one_test_source:'+profile,all(len(p['test_groups'])==1 for p in plan))
        check('each_endpoint_tested_once:'+profile,collections.Counter(x for p in plan for x in p['test_ids'])==collections.Counter(r['record_id'] for r in rows))
        plans[profile]=plan
        profile_counts[profile]={'rows':count,'sources':n_groups,'outer_folds':len(plan),'fits_performed':0}
    core=load_ready();extended=load_ready('literature_approx_sensitivity')
    check('activation_over100_retained',next(r for r in core if r['record_id']=='R093_CY01')['retention_pct']==108.8)
    check('questionable_pore_stays_masked',next(r for r in core if r['record_id']=='R091_CY01')['total_pore_volume_cm3_g'] is None)
    check('approx89_not_exact',next(r for r in extended if r['record_id']=='R020_CY01')['retention_relation']=='approx')
    rr=[r for r in extended if r['paper_id']=='R112']
    check('same_curve_two_nodes_one_source',len(rr)==2 and len({r['study_group'] for r in rr})==1 and sum(r['source_weight'] for r in rr)==1)
    check('same_curve_not_split',all(not ({r['record_id'] for r in rr}&set(p['train_ids']) and {r['record_id'] for r in rr}&set(p['test_ids'])) for p in plans['literature_approx_sensitivity']))
    def mutate(key,value):
        row=copy.deepcopy(core[0]);row[key]=value;return validate_rows([row])
    reject('reject_unapproved',lambda:mutate('eligible',0))
    reject('reject_invented_current',lambda:mutate('reported_current_A_g',1.234))
    reject('reject_fake_canonical_current',lambda:mutate('canonical_current_A_g',1.0))
    reject('reject_molality_as_molarity',lambda:mutate('concentration_unit','mol/kg'))
    reject('reject_lowercase_m_as_M',lambda:mutate('concentration_unit','m'))
    reject('reject_target_missing',lambda:mutate('retention_pct',None))
    reject('reject_lower_bound_as_exact',lambda:mutate('retention_relation','gt'))
    reject('reject_duplicate_endpoint',lambda:validate_rows(copy.deepcopy(core[:1]+core[:1])))
    reject('reject_stacking_profiles',lambda:validate_rows(copy.deepcopy(core[:1]+[r for r in extended if r['record_id']=='R020_CY01'])))
    reject('research_engine_guard',lambda:run_benchmark(core,ROOT/'modeling/SHOULD_NOT_EXIST','plus_BET'))
    check('blocked_research_wrote_nothing',not (ROOT/'modeling/SHOULD_NOT_EXIST').exists())
    specs=load_spaces(CONTRACT)
    check('single_candidate_means_declared_default',all(candidates_for(n,CONTRACT,specs)==[specs[n]['default']] for n in CONTRACT['models']))
    dump(ROOT/'modeling/分组验证计划_未拟合.json',plans)
    dump(ROOT/'训练数据预检.json',preflight())
    # Completely artificial rows: no research endpoints or labels are copied.
    synthetic=[]
    for group in range(6):
        for j in range(3):
            synthetic.append({'_synthetic':True,'record_id':f'SYNTH_{group}_{j}','paper_id':f'SYNTH_P{group}',
                              'material_id':f'SYNTH_M{group}','cycle_test_id':f'SYNTH_T{group}','study_group':f'SYNTH_G{group}',
                              'system':'2E_symmetric','method':'GCD','conflict':0,'retention_relation':'eq',
                              'cycle_count':2000*(j+1),'reported_current_A_g':float(group+1),
                              'electrolyte':'SYNTH_E'+str(group%3),'concentration_value':1.0,'concentration_unit':'M',
                              'voltage_lower_V':0.,'voltage_upper_V':1.+.1*(group%2),'BET_m2_g':500.+100*group,
                              'total_pore_volume_cm3_g':None if (j+group)%2 else .2+.1*group,
                              'retention_pct':90.-2*j+group})
    cfg=copy.deepcopy(CONTRACT);cfg['split']['folds_up_to']=3
    # Fixed defaults exercise all five pipelines once per held-out synthetic source fold.
    run_benchmark(synthetic,ROOT/'modeling/SYNTHETIC_INTERFACE_CHECK_NOT_RESEARCH','plus_BET_pore',config=cfg,synthetic=True)
    completion=json.loads((ROOT/'modeling/SYNTHETIC_INTERFACE_CHECK_NOT_RESEARCH/completion.json').read_text('utf-8'))
    check('synthetic_all_models_complete',completion['status']=='completed' and completion['synthetic'] and not completion['research_training_performed'])
    with connect() as c:
        inv=[dict(r) for r in c.execute('SELECT path,sha256 FROM source_files')]
    for entry in inv:check('unchanged_original_source:'+entry['path'],digest(entry['path'])==entry['sha256'])
    protected=json.loads((ROOT/'protected_parent_fingerprints.json').read_text('utf-8'))
    for entry in protected:check('unchanged_parent_artifact:'+entry['path'],digest(entry['path'])==entry['sha256'])
    result={'passed':all(x['passed'] for x in checks),'checks_count':len(checks),'checks':checks,
            'original_source_files_unchanged':len(inv),'parent_artifacts_unchanged':len(protected),
            'profile_summary':profile_counts,'research_fit_calls':0,'synthetic_fit_calls':completion['fit_calls'],
            'synthetic_warning_count':len(json.loads((ROOT/'modeling/SYNTHETIC_INTERFACE_CHECK_NOT_RESEARCH/warnings.json').read_text('utf-8'))),
            'scope':'Evidence-preserving preparation only. No research accuracy reported.'}
    dump(ROOT/'核验结果_r4.json',result)
    print(json.dumps({k:v for k,v in result.items() if k!='checks'},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
