"""Verify four real main-task joins, immutable parents and receipted overlays."""
from pathlib import Path
import collections,gc,hashlib,json,math,shutil,sqlite3,sys,tempfile
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.extract_opb_main_v5 import OUT,DB,BASE,DOI,SOURCE,SOURCE_SHA,EIDS,TABLE,read,write,sha
from data.training_store import open_training_datasets
from data.training_catalog import open_training_datasets as v4open

def verify(save=False):
    checks=collections.Counter()
    def ck(k,v):assert v,k;checks[k]+=1
    for path,h in read(OUT/'protected_inputs.json').items():ck('protected_parent_original_SHA',sha(ROOT/path)==h)
    raw=sqlite3.connect(DB.as_uri()+'?mode=ro',uri=True);raw.row_factory=sqlite3.Row
    ck('new_extension_integrity',raw.execute('pragma integrity_check').fetchone()[0]=='ok');ck('new_extension_foreign_keys',not raw.execute('pragma foreign_key_check').fetchall())
    facts=read(OUT/'new_facts.json');fs={f['fact_id']:f for f in facts};s=read(OUT/'summary.json');changes=read(OUT/'overlay_changes.json')
    ck('114facts110numeric4unknown',len(facts)==114 and sum(f['value']is not None for f in facts)==110)
    parsed=read(OUT/'pdf_primary_verification.json');ck('independent_fresh_PDF_cells',parsed['status']=='passed'and parsed['source_sha256']==SOURCE_SHA and len(parsed['checked_fact_ids'])==45)
    with open_training_datasets(DB,sha(DB))as d,v4open()as old:
        c=d.connection;overrides={(r['table'],tuple(r['key'])):r for r in changes}
        for r in changes:
            before=json.dumps(r['before_record'],ensure_ascii=False,allow_nan=False)
            # Original strings are hashed in the API. Object equality below
            # independently checks semantics and guards every original feature.
            if r['table']=='cycle_records':
                ck('cycle_passthrough_identical',r['before_record']==r['after_record']and r['before_sha256']==r['after_sha256'])
            else:
                a,b=r['before_record'],r['after_record'];ck('target_and_protocol_preserved',a['target']==b['target']and a['target_name']==b['target_name']and a['conditions']==b['conditions'])
                for key,value in a['features'].items():
                    if value is not None:ck('no_nonempty_feature_overwrite',b['features'][key]==value)
                ck('explicit_material_identity',b['material_key']is not None and b['sample_name']in EIDS)
        for table, in old.connection.execute('select name from main.sqlite_master where type="table"and name!="metadata"'):
            info=old.connection.execute('pragma main.table_info('+table+')').fetchall();pk=[r['name']for r in sorted(info,key=lambda x:x['pk'])if r['pk']]
            if not pk:continue
            actual={tuple(r[k]for k in pk):tuple(r)for r in c.execute('select *from '+table)}
            for row in old.connection.execute('select *from '+table):
                key=tuple(row[k]for k in pk)
                if(table,key)in overrides:continue
                ck('all_unaffected_inherited_rows_unchanged:'+table,actual[key]==tuple(row))
        for table in json.loads(raw.execute('select value_json from metadata where key="append_only_union_tables"').fetchone()[0]):
            info=raw.execute('pragma table_info('+table+')').fetchall();pk=[r['name']for r in sorted(info,key=lambda x:x['pk'])if r['pk']]
            if not pk:continue
            vals=[tuple(r)for r in c.execute('select '+','.join(pk)+' from '+table)];ck('logical_primary_keys_unique:'+table,len(vals)==len(set(vals)))
        current={r['row_id']:r for r in d.rows('cycle:reported_3e')};previous={r['row_id']:r for r in old.rows('cycle:reported_3e')}
        ck('same47rows34groups',set(current)==set(previous)and len(current)==47 and len({r['source_family']for r in current.values()})==34)
        added=0;attested=0
        for name,eid in EIDS.items():
            a,b=previous[eid],current[eid];ck('four_main_identical_targets',a['target']==b['target']);ck('own_BET_Raman_match',b['features']['BET_m2_g']==TABLE[name][2]and b['features']['Raman_ID_IG']==TABLE[name][1])
            ck('material_join_not_new_admission',a['material_key']is None and b['material_key']is not None)
            actual=sum(v is not None and a['features'].get(k)is None for k,v in b['features'].items());added+=actual;attested+=len(b['v5_material_evidence']['existing_values_attested'])
            ck('explicit_HK_volume_method',b['v5_material_evidence']['micropore_method']=='HK')
            ck('no_XPS_atomic_basis_guess',b['features']['XPS_N_atomic_pct_v15']is None and b['features']['XPS_O_atomic_pct_v15']is None)
            ck('no_independent_carbonization_step_invented',b['features']['carbonization_temperature_C']is None)
            ck('loading_bounds_not_midpoint',b['features']['mass_loading_mg_cm2']is None and b['features']['electrode_active_loading_lower_mg_cm2']==1 and b['features']['electrode_active_loading_upper_mg_cm2']==2)
            for k in b['v5_material_evidence']['added_nonmissing_fields']:ck('new_cells_not_duplicate_alias',a['features'].get(k)is None)
        ck('60new44attested_cells',added==60 and attested==44 and s['additional_main3e_nonmissing_cells']==60)
        ck('main_links21_total53',len({eid for eid in current if c.execute('select 1 from cycle_material_links where endpoint_id=?',(eid,)).fetchone()})==21 and c.execute('select count(*)from cycle_material_links').fetchone()[0]==53)
        ck('original287cycle_records',c.execute('select count(*)from cycle_records').fetchone()[0]==287)
        used=set()
        for u in raw.execute('select *from fact_uses'):
            f=fs[u['fact_id']];row=json.loads(c.execute('select record_json from inputs where task=?and row_id=?',(u['task'],u['row_id'])).fetchone()[0]);v=row['target']if u['role']=='target'else row['features'][u['feature']]
            ck('actual_fact_receipt',v==f['value']and v is not None);ck('source_and_material_match',f['material_key']==row['material_key']and row['source_family']=='doi:'+DOI);used.add(f['fact_id'])
        ck('104new_unique_used',len(used)==104 and used==set(s['new_connected_fact_ids']))
        ck('3391of4837',c.execute('select count(distinct fact_id)from fact_uses').fetchone()[0]==3391 and c.execute('select sum(numeric)from facts').fetchone()[0]==4837 and s['numeric_fact_connection_rate']==3391/4837)
        ck('no_XPS_or_intro_promoted',not any(f['fact_id']in used for f in facts if f['field_name'].startswith('XPS_')or f['field_name']=='BET_intro_alternate_report_m2_g'))
        for row in raw.execute('select *from inputs where task not like "cycle:%"'):
            v=json.loads(row['record_json']);target=v['target_name']
            if row['task'].startswith('material:'):
                blocked=v['excluded_target_measurement_block']
                ck('electrode_loading_not_intrinsic_property_predictor',not any(f.startswith('electrode_active_loading_')for f in v['features']))
                for f in v['features']:
                    g='adsorption_porosity'if any(z in f for z in ['pore','BET_'])else'Raman'if f.startswith('Raman_')else'XRD'if f.startswith('XRD_')else'process'
                    ck('same_measurement_block_not_target_leak',g!=blocked)
            else:ck('capacity_not_retention',v['not_cycling_label']and'discharge_time_s'not in v['features'])
        ck('216ordinary3e32sources',d.tasks()['capacity:3e_reported']['rows']==216 and d.tasks()['capacity:3e_reported']['source_families']==32)
        ordinary={r['row_id']:r for r in d.rows('capacity:3e_reported')};expanded={r['row_id']:r for r in d.rows('capacity:3e_with_graph')}
        ck('216_nested_in394_not610',len(ordinary)==216 and len(expanded)==394 and set(ordinary)<=set(expanded))
        for key,r in ordinary.items():ck('nested_target_same',r['target']==expanded[key]['target'])
        ck('no_stale_parent_release_counters',s['new_response_training_rows']==0 and s['new_existing_cycle_material_links']==4 and s['new_material_or_precursor_task_rows']==32 and s['cumulative_main3e_material_cells_added_since_v12']==165)
        for task in d.tasks():
            mm=d.matrix(task,[DOI]);ck('whole_DOI_all_task_holdout','doi:'+DOI not in mm['groups'])
        for family in sorted({r['source_family']for r in current.values()}):
            split=d.source_split('cycle:reported_3e',[family]);ck('fold_support_train_only',not(set(split['train']['groups'])&set(split['test']['groups'])))
        split=d.source_split('cycle:reported_3e',[DOI]);ck('all_four_heldout_together',len(split['test']['row_ids'])==4 and not(set(EIDS.values())&set(split['train']['row_ids'])))
        for r in raw.execute('select record_json from response_reports_v3'):
            v=json.loads(r[0]);ck('SIB_and_device_not_admitted',v['ready_for_cycling']is False)
        for sql in ['update main.sources set record_json=record_json','update parent1.sources set record_json=record_json']:
            try:c.execute(sql)
            except sqlite3.OperationalError:ck('all_layers_readonly',True)
            else:raise AssertionError('Writable layer')
        ck('v4_entry_still_pinned',old.summary['numeric_facts_connected_to_training_inputs']==3287)
        ck('no_fits_or_admissions',s['new_model_fits']==0 and s['new_cycling_admissions']==0)
        # A changed target in an isolated copy must NOT win over a parent merely
        # because its file is newer. Pass the actual copy SHA to exercise the
        # replacement-receipt guard rather than the outer fingerprint check.
        (ROOT/'tmp').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='v5_overlay_guard_',dir=ROOT/'tmp')as tmp:
            fixture=Path(tmp).resolve();assert fixture.is_relative_to((ROOT/'tmp').resolve())
            copy=fixture/'fixture.sqlite';shutil.copyfile(DB,copy);shutil.copyfile(OUT/'source_family_rules.json',fixture/'source_family_rules.json')
            cc=sqlite3.connect(copy);v=json.loads(cc.execute('select record_json from inputs where task="cycle:reported_3e"and row_id="candidate:TE021"').fetchone()[0]);v['target']=999
            cc.execute('update inputs set record_json=?where task="cycle:reported_3e"and row_id="candidate:TE021"',(json.dumps(v,ensure_ascii=False),));cc.commit();cc.close()
            try:
                with open_training_datasets(copy,sha(copy)):pass
            except ValueError as error:ck('unreceipted_newer_target_rejected','Unreceipted'in str(error))
            else:raise AssertionError('Unreceipted target replacement was accepted')
            gc.collect()
    result=dict(status='passed',checks=sum(checks.values()),groups=dict(checks),database_sha256=sha(DB),new_numeric_facts=110,new_connected_facts=104,main3e_new_nonmissing_cells=60,main3e_existing_cells_attested=44,main3e_material_links=21,new_capacity_reports=8,new_model_fits=0,new_cycling_admissions=0,goal_complete=False)
    if save:write(OUT/'verification.json',result)
    else:ck('saved_verification_matches',read(OUT/'verification.json')==result)
    raw.close();print(json.dumps(dict(status='passed',checks=result['checks'],sha256=result['database_sha256'])))

if __name__=='__main__':verify('--save'in sys.argv)
