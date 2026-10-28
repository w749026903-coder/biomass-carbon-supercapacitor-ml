"""Validate primary units/roles, read-only overlay, stage isolation and receipts."""
from pathlib import Path
import collections,json,math,sqlite3,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.extract_lignin_cf_v4 import BASE,OUT,DB,DOI,PRIOR,FAMILY,MAIN,SI,read,write,sha
from data.training_catalog import open_training_datasets

def verify(save=False):
    count=collections.Counter()
    def ck(k,v):assert v,k;count[k]+=1
    for path,h in read(OUT/'protected_inputs.json').items():ck('protected_SHA',sha(ROOT/path)==h)
    raw=sqlite3.connect(DB.as_uri()+'?mode=ro',uri=True);raw.row_factory=sqlite3.Row
    ck('extension_integrity',raw.execute('pragma integrity_check').fetchone()[0]=='ok');ck('extension_foreign_keys',not raw.execute('pragma foreign_key_check').fetchall())
    fs=read(OUT/'new_facts.json');reports=read(OUT/'capacity_reports.json');eis=read(OUT/'EIS_reports.json');s=read(OUT/'summary.json')
    ck('140facts113numeric27null',len(fs)==140 and sum(f['value']is not None for f in fs)==113)
    ck('39reports34ready9EIS',len(reports)==39 and sum(r['ready_for_training_inputs']for r in reports)==34 and sum(r['ready_for_training_inputs']for r in eis)==9)
    with open_training_datasets(DB,sha(DB))as d:
        c=d.connection;parent=sqlite3.connect((BASE/'training_data_v3.sqlite').as_uri()+'?mode=ro',uri=True);parent.row_factory=sqlite3.Row
        ck('parent_integrity',parent.execute('pragma integrity_check').fetchone()[0]=='ok')
        for table, in parent.execute("select name from sqlite_master where type='table'and name!='metadata'"):
            old=set(map(tuple,parent.execute('select *from '+table)));new=set(map(tuple,c.execute('select *from '+table)))
            for row in old:ck('inherited_row_unchanged:'+table,row in new)
        # The union must not silently duplicate any inherited primary key.
        for table, in raw.execute("select name from sqlite_master where type='table'and name!='metadata'"):
            keys=sorted([(r['pk'],r['name'])for r in raw.execute('pragma table_info('+table+')')if r['pk']])
            if not keys:continue
            values=[tuple(r)for r in c.execute('select '+','.join(k[1]for k in keys)+' from '+table)]
            ck('union_primary_keys_unique:'+table,len(values)==len(set(values)))
        ck('4970facts4727numeric3287used',c.execute('select count(*)from facts').fetchone()[0]==4970 and c.execute('select sum(numeric)from facts').fetchone()[0]==4727 and c.execute('select count(distinct fact_id)from fact_uses').fetchone()[0]==3287)
        oldmax=parent.execute('select max(fact_id)from facts').fetchone()[0];nf={f['fact_id']:f for f in fs};newuses=c.execute('select *from fact_uses where fact_id>?',(oldmax,)).fetchall();used={u['fact_id']for u in newuses}
        ck('109new_connected',len(used)==109 and used==set(s['new_connected_fact_ids']))
        newrows={(r['task'],r['row_id']):json.loads(r['record_json'])for r in raw.execute('select *from inputs')}
        bindings={r['device_material_key']:r['electrode_material_key']for r in read(OUT/'recipe_bindings.json')}
        for u in newuses:
            f=nf[u['fact_id']];row=newrows[u['task'],u['row_id']];value=row['target']if u['role']=='target'else row['features'][u['feature']]
            ck('actual_fact_use_original_value',value==f['value']and value is not None)
            ck('own_or_explicit_electrode_role',f['material_key']==row['material_key']or(row['material_key']in bindings and f['material_key']==bindings[row['material_key']]and u['feature'].startswith('electrode__')))
        for f in fs:
            actual=json.loads(raw.execute('select record_json from facts where fact_id=?',(f['fact_id'],)).fetchone()[0]);ck('source_fact_exact',actual==f)
            if f['field_name']=='BET_surface_area_m2_g'and'electrode'in f['material_stage']:ck('no_composite_BET_inherited',f['fact_id']not in used and(f['value']is None or f['sample_name']=='Plain CF'and f['value']==.2))
            if f['field_name']=='author_TGA_lignin_loading_wt_pct':ck('TGA_unbound_not_used',f['fact_id']not in used)
            if f['field_name']in ['calcination_temperature_C','calcination_duration_h','heating_rate_C_min']and f['value']is None:ck('not_applied_not_zero',f['fact_id']not in used)
        for key,row in newrows.items():
            ck('no_new_ordinary_or_retention_task',not key[0].startswith('cycle:')and not key[0].startswith('material:ordinary_biomass'))
            ck('same_source_family',row['source_family']==FAMILY)
            ck('no_discharge_time_target_formula_leak','discharge_time_s'not in row['features']and not any('Csp'in f or 'capacitance'in f.lower()for f in row['features']))
            if key[0].startswith('material:'):
                ck('lignin_same_adsorption_block_removed',all(f.startswith(('calcination_','heating_'))for f in row['features']))
            else:ck('no_constituent_BET_in_composite_input',not any('BET'in f for f in row['features']))
        for r in reports:
            if r['kind']=='gel_device_GCD_mF_g':
                q=r['conditions'];ck('mA_to_A_explicit',q['reported_current_A_g']==q['reported_current_mA_g']/1000 and q['current_conversion']['factor']==.001)
                ck('GCD_units_match_C_I_t_at1V',abs(r['value']-q['reported_current_mA_g']*q['discharge_time_s'])<=.051)
                ck('native_energy_unit_consistency',abs(r['energy_mWh_kg']-r['value']/7.2)<=.06)
            ck('all_cap_reports_not_retention',r['not_cycling_retention'])
            if r['kind']=='lignin_normalized_CV_author_F_g'or r['conditions'].get('after_bending'):ck('normalized_or_after_bending_inspection_only',not r['ready_for_training_inputs'])
        capture=read(OUT/'curve_captures.json');ck('10bounded_absolute_trace_reads',len(capture)==10)
        rr={r['report_id']:r for r in reports}
        for a in capture:
            r=rr[a['report_id']];x,y=a['marker_center_px'];ck('curve_calibration',r['value']==round((353.5-y)*200/130.75,1)and a['cycle_interval'][0]<=((x-57.5)*100/142.75)<=a['cycle_interval'][1])
            ck('curve_not_retention_or_SD',r['not_retention_ratio']and r['unit']=='mF/g'and a['not_author_SD']and a['readout_tolerance_mF_g']==4)
            ck('curve_reported_current',r['conditions']['reported_current_A_g']==.00005)
        ck('98plus_percent_unbending_not_cycle_target',all('retention'not in row['target_name'].lower()for row in newrows.values()))
        for task in d.tasks():
            if task not in read(BASE/'summary.json')['task_counts']:
                m=d.matrix(task);ck('new_tasks_one_family_not_independent_validation',m['source_families']==1 and not m['source_holdout_validation_possible']and math.isclose(sum(m['sample_weight']),1))
        for name in [DOI,PRIOR]:
            for task,m in d.training_bundle([name]).items():ck('current_and_prior_all_task_quarantine',FAMILY not in m['groups'])
        ck('main_counts_not_changed',d.tasks()['cycle:reported_3e']['rows']==47 and d.tasks()['cycle:reported_3e']['source_families']==34 and d.tasks()['cycle:reported_2e']['rows']==31)
        for statement in ['create table x_test(v)','update main.sources set record_json=record_json','update parent0.sources set record_json=record_json']:
            try:c.execute(statement)
            except sqlite3.OperationalError:ck('API_query_only_and_readonly_attachments',True)
            else:raise AssertionError('Read-only API accepted write')
        ck('increment_not_full_copy',DB.stat().st_size<(BASE/'training_data_v3.sqlite').stat().st_size/10 and raw.execute('select count(*)from facts').fetchone()[0]==140)
        parent.close()
    result=dict(status='passed',checks=sum(count.values()),groups=dict(count),database_sha256=sha(DB),storage='read_only_parent_union',new_numeric_facts=113,new_connected_facts=109,new_capacity_reports=39,new_ready_capacity_rows=34,new_EIS_training_rows=9,new_model_fits=0,new_cycling_admissions=0,goal_complete=False)
    if save:write(OUT/'verification.json',result)
    else:ck('saved_verification_matches',read(OUT/'verification.json')==result)
    raw.close();print(json.dumps(dict(status='passed',checks=result['checks'],sha256=result['database_sha256'])))

if __name__=='__main__':verify('--save'in sys.argv)
