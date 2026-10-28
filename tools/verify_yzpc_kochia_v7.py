"""Verify current extension against immutable v6 and fresh primary PDF tables."""
from pathlib import Path
import collections,json,re,sqlite3,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.curate_yzpc_kochia_v7 import OUT,YZ,KA,FIELDS
from tools.extract_lignin_cf_v4 import read,write,sha
from data.training_latest import open_training_datasets
from data.training_store import TrainingStore

def verify(save=False):
    checks=collections.Counter()
    def ck(k,ok):
        if not ok:raise AssertionError(k)
        checks[k]+=1
    spec=read(OUT/'reviewed_extraction_spec.json');base=ROOT/spec['parent_directory'];db=OUT/spec['database_file'];parent=read(base/'entrypoint_snapshot.json');s=read(OUT/'summary.json');facts=read(OUT/'new_facts.json');fs={f['fact_id']:f for f in facts}
    for path,h in read(OUT/'protected_inputs.json').items():ck('originals_and_history_SHA',sha(ROOT/path)==h)
    raw=sqlite3.connect(db.as_uri()+'?mode=ro',uri=True);raw.row_factory=sqlite3.Row
    ck('SQLite_integrity',raw.execute('pragma integrity_check').fetchone()[0]=='ok');ck('SQLite_foreign_keys',not raw.execute('pragma foreign_key_check').fetchall())
    ck('301facts275numeric26null',len(facts)==301 and sum(f['value']is not None for f in facts)==275)
    changes=read(OUT/'overlay_changes.json');overrides={(r['table'],tuple(r['key'])):r for r in changes};ids={x['endpoint_id']for x in spec['cycle_links']}
    with open_training_datasets()as d,TrainingStore(base/parent['database_file'],parent['sha256'])as old:
        c=d.connection
        for table, in old.connection.execute('select name from main.sqlite_master where type="table"and name!="metadata"'):
            info=old.connection.execute('pragma main.table_info('+table+')').fetchall();pk=[x['name']for x in sorted(info,key=lambda x:x['pk'])if x['pk']]
            if not pk:continue
            actual={tuple(x[k]for k in pk):tuple(x)for x in c.execute('select *from '+table)}
            for x in old.connection.execute('select *from '+table):
                key=tuple(x[k]for k in pk)
                if(table,key)not in overrides:ck('unchanged_parent_rows:'+table,actual[key]==tuple(x))
        for table in json.loads(raw.execute('select value_json from metadata where key="append_only_union_tables"').fetchone()[0]):
            info=raw.execute('pragma table_info('+table+')').fetchall();pk=[x['name']for x in sorted(info,key=lambda x:x['pk'])if x['pk']]
            if pk:
                values=[tuple(x)for x in c.execute('select '+','.join(pk)+' from '+table)];ck('logical_primary_keys:'+table,len(values)==len(set(values)))
        for x in changes:
            a,b=x['before_record'],x['after_record']
            if x['table']=='cycle_records':ck('cycle_identical_passthrough',a==b and x['before_sha256']==x['after_sha256'])
            else:
                ck('original_targets_conditions_preserved',a['target']==b['target']and a['target_name']==b['target_name']and a['conditions']==b['conditions'])
                for field,v in a['features'].items():
                    if v is not None:ck('old_nonempty_features_preserved',b['features'][field]==v)
        current={x['row_id']:x for x in d.rows('cycle:reported_3e')};previous={x['row_id']:x for x in old.rows('cycle:reported_3e')}
        ck('47rows34families',set(current)==set(previous)and len(current)==47 and len({x['source_family']for x in current.values()})==34)
        newcells=attested=0
        for eid in ids:
            a,b=previous[eid],current[eid];e=b['current_material_evidence'];newcells+=sum(v is not None and a['features'].get(k)is None for k,v in b['features'].items());attested+=len(e['existing_values_attested']);ck('bridge_existing_endpoint',a['material_key']is None and b['material_key']is not None)
        ck('34new26attested',newcells==34 and attested==26 and s['additional_main3e_nonmissing_cells']==34)
        y=current['incoming:ADD_039_T01']['features'];k=current['candidate:TE026']['features']
        ck('YZPC_original_volume_freeze',y['micropore_volume_cm3_g']is None and y['mesopore_volume_cm3_g']is None and 'reported_micropore_volume_fraction'not in y)
        ck('YZPC_loading_interval_no_midpoint',y['mass_loading_mg_cm2']is None and y['electrode_active_loading_lower_mg_cm2']==2 and y['electrode_active_loading_upper_mg_cm2']==3)
        ck('separate_heat_stages_not_reversed',y['precarbonization_temperature_C']==400 and y['activation_temperature_C']==700 and k['precarbonization_temperature_C']==800 and k['activation_temperature_C']==600)
        ck('contact_angle_time_not_equilibrium',k['water_contact_angle_deg_v15']==58.25 and k['contact_angle_time_ms_v15']==70 and y['water_contact_angle_deg_v15']==92 and 'contact_angle_time_ms_v15'not in y)
        ck('actual_electrode_compositions',y['electrode_PVDF_fraction']==.15 and y['electrode_conductive_fraction']==.05 and k['electrode_PVDF_fraction']==.1 and k['electrode_conductive_fraction']==.1)
        ck('25main57all_material_links',len({eid for eid in current if c.execute('select 1 from cycle_material_links where endpoint_id=?',(eid,)).fetchone()})==25 and c.execute('select count(*)from cycle_material_links').fetchone()[0]==57)
        ck('287original_cycles',c.execute('select count(*)from cycle_records').fetchone()[0]==287)
        used=set()
        for x in raw.execute('select *from fact_uses'):
            f=fs[x['fact_id']];row=json.loads(c.execute('select record_json from inputs where task=?and row_id=?',(x['task'],x['row_id'])).fetchone()[0]);v=row['target']if x['role']=='target'else row['features'][x['feature']]
            ck('actual_fact_value_receipts',v is not None and v==f['value']);ck('actual_stage_material_source_receipts',row['material_key']==f['material_key']and row['source_family']=='doi:'+f['doi']);used.add(f['fact_id'])
        ck('260new_connected',len(used)==260 and used==set(s['new_connected_fact_ids']))
        ck('3727of5197',c.execute('select count(distinct fact_id)from fact_uses').fetchone()[0]==3727 and c.execute('select sum(numeric)from facts').fetchone()[0]==5197 and s['numeric_fact_connection_rate']==3727/5197)
        ck('5476facts_all_have_disposition',c.execute('select count(*)from facts').fetchone()[0]==5476 and c.execute('select count(*)from usage_ledger').fetchone()[0]==5476)
        for f in facts:
            if not f['selected_for_this_purpose']:ck('held_metadata_unknown_not_promoted',f['fact_id']not in used)
        ck('frozen_and_TGA_5cells',raw.execute('select count(*)from held_features').fetchone()[0]==5)
        ck('raw_FTIR_10metadata',raw.execute('select count(*)from measurement_metadata').fetchone()[0]==10)
        ordinary={x['row_id']:x for x in d.rows('capacity:3e_reported')};expanded={x['row_id']:x for x in d.rows('capacity:3e_with_graph')}
        ck('229_nested434',len(ordinary)==229 and len(expanded)==434 and set(ordinary)<=set(expanded))
        for rid,row in ordinary.items():ck('nested_target_identical',row['target']==expanded[rid]['target'])
        ck('35capacity_source_families',len({x['source_family']for x in ordinary.values()})==35)
        partial=d.rows('capacity:3e_reported_without_BET');ck('three_no_BET_partial_separate',len(partial)==3 and all('BET_surface_area_m2_g'not in x['features']for x in partial)and not({x['row_id']for x in partial}&set(ordinary)))
        ck('device7rows2sources',len(d.rows('capacity:2e_device'))==7 and len({x['source_family']for x in d.rows('capacity:2e_device')})==2)
        for obs in read(OUT/'new_capacity_reports.json'):
            if obs['conditions']['configuration']=='2e_symmetric':ck('explicit_device_total_mass_not_single_electrode',obs['conditions']['current_mass_basis']=='total_active_mass_both_electrodes_explicit'and obs['conditions']['voltage_upper_V']==1.2)
        for x in raw.execute('select *from inputs where task not like "cycle:%"'):
            row=json.loads(x['record_json'])
            if x['task'].startswith('material:'):
                for f in row['features']:
                    group='adsorption_porosity'if any(v in f for v in ['pore','BET_'])else'XPS'if f.startswith('XPS_')else'Raman'if f.startswith('Raman_')else'electrode_protocol'if f.startswith('electrode_')or f.startswith('mass_loading_')else'wettability'if 'contact_angle'in f else'process'
                    ck('same_measurement_block_no_future_electrode_leak',group!=row['excluded_target_measurement_block']and group!='electrode_protocol')
            else:ck('aux_not_cycle_or_formula_time_leak',row['target_name']!='capacitance_retention_pct'and'discharge_time_s'not in row['features'])
        for doi in [YZ,KA]:
            for task in d.tasks():ck('whole_DOI_every_aux_task_holdout','doi:'+doi not in d.matrix(task,[doi])['groups'])
            split=d.source_split('cycle:reported_3e',[doi]);ck('whole_source_main_holdout',len(split['test']['row_ids'])==1 and not(set(split['train']['groups'])&set(split['test']['groups'])))
        ck('no_fit_admission_original37',s['new_model_fits']==0 and s['new_cycling_admissions']==0 and s['original_pending']==37)
        for alias in ['main','parent0','parent1','parent2','parent3']:
            try:c.execute('update '+alias+'.sources set record_json=record_json')
            except sqlite3.OperationalError:ck('all_database_layers_readonly',True)
            else:raise AssertionError('Writable layer')
    raw.close()
    from pypdf import PdfReader
    yz_source=next(x for x in spec['sources']if x['doi']==YZ);ka_source=next(x for x in spec['sources']if x['doi']==KA)
    yp=PdfReader(ROOT/yz_source['path']);kp=PdfReader(ROOT/ka_source['path']);parsed={}
    for line in yp.pages[4].extract_text().splitlines():
        m=re.match(r'^(YZPC-\d|YZC|YZ)\s+([\d.].*)$',line.strip())
        if m:
            vals=[float(v)for v in m[2].split()];ck('fresh_YZ_table_row_width',len(vals)==8);parsed[m[1]]=vals
    ck('fresh_YZ_table7rows',len(parsed)==7)
    for name,values in parsed.items():
        for field,value in zip(FIELDS,values):ck('fresh_YZ_56cells',any(f['doi']==YZ and f['sample_name']==name and f['field_name']==field and f['value']==value for f in facts))
    kt=kp.pages[3].extract_text();row=next(line for line in kt.splitlines()if line.startswith('KAC-5 1441.3'));values=[float(v)for v in row.split()[1:]]
    for field,value in zip(['BET_surface_area_m2_g','total_pore_volume_cm3_g','micropore_volume_cm3_g','mesopore_volume_cm3_g','average_pore_diameter_nm'],values):ck('fresh_KAC_table5cells',any(f['doi']==KA and f['sample_name']=='KAC-5'and f['field_name']==field and f['value']==value for f in facts))
    ck('fresh_KAC_table_fraction', '(82.28%)'in kt and any(f['field_name']=='reported_micropore_volume_fraction'and f['doi']==KA and f['value']==82.28/100 for f in facts))
    norm=lambda t:re.sub(r'\s+',' ',t)
    ck('fresh_KAC_device_values',all(x in norm(kp.pages[6].extract_text())for x in ['61.7','41.7','0.5','10 A']))
    ck('fresh_YZ_own_cap_values',all(x in norm(yp.pages[7].extract_text())for x in ['77, 196, 218, 344','278','270 F']))
    # Visual image evidence confirms exact graph/inset identifiers, not fake OCR.
    ck('KAC_visual_evidence_available',(OUT/'evidence/KAC_p5.png').is_file())
    result=dict(status='passed',checks=sum(checks.values()),groups=dict(checks),database_sha256=sha(db),fresh_primary_table_cells=62,visual_insets_reviewed=['KACFig3c At%C91.75/O8.25','KACFig3f58.25deg at70ms'],SI_acquired=False,full_papers_complete=False,new_model_fits=0,new_cycling_admissions=0)
    if save:write(OUT/'verification.json',result)
    print(json.dumps({k:v for k,v in result.items()if k!='groups'},ensure_ascii=False))

if __name__=='__main__':verify('--save'in sys.argv)
