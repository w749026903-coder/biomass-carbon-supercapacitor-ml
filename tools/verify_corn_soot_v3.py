"""Read-only independent validation of the new source extension and input use."""
from pathlib import Path
import collections,csv,json,math,sqlite3,sys
from xml.etree import ElementTree as E
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.extract_corn_soot_v3 import BASE,OUT,DB,CP,SP,SI,CORN,SOOT,read,write,sha,group
from data.training_ready import open_training_datasets

def verify(save=False):
    n=collections.Counter()
    def ck(label,value):assert value,label;n[label]+=1
    c=sqlite3.connect(DB.as_uri()+'?mode=ro',uri=True);c.row_factory=sqlite3.Row
    p=sqlite3.connect((BASE/'training_data_v2.sqlite').as_uri()+'?mode=ro',uri=True);p.row_factory=sqlite3.Row
    ck('SQLite_integrity',c.execute('pragma integrity_check').fetchone()[0]=='ok');ck('foreign_keys',not c.execute('pragma foreign_key_check').fetchall())
    for path,h in read(OUT/'protected_inputs.json').items():ck('protected_SHA',sha(ROOT/path)==h)
    # Compare old content, not only row totals, across EVERY inherited table.
    for table, in p.execute("select name from sqlite_master where type='table'"):
        old=list(map(tuple,p.execute('select *from '+table)));new=set(map(tuple,c.execute('select *from '+table)))
        if table=='metadata':continue
        for r in old:ck('inherited_row_unchanged:'+table,r in new)
    s=read(OUT/'summary.json');fs={r['fact_id']:json.loads(r['record_json'])for r in c.execute('select *from facts')};newfs=read(OUT/'new_facts.json');mats={r['material_key']:json.loads(r['record_json'])for r in c.execute('select *from materials')}
    ck('160new145numeric15null',len(newfs)==160 and sum(f['value']is not None for f in newfs)==145)
    ck('new_materials_8final_3crude',len(read(OUT/'new_materials.json'))==11 and sum(m['material_stage']=='unwashed_corn_char_intermediate'for m in read(OUT/'new_materials.json'))==3)
    for f in newfs:ck('fact_record_exact',fs[f['fact_id']]==f)
    inp={(r['task'],r['row_id']):json.loads(r['record_json'])for r in c.execute('select *from inputs')};used=set()
    for r in c.execute('select *from fact_uses'):
        f=fs[r['fact_id']];v=inp[r['task'],r['row_id']];x=v['target']if r['role']=='target'else v['features'][r['feature']]
        ck('actual_numeric_value_receipt',x==f['value']and x is not None);used.add(f['fact_id'])
        if f['fact_id']>4670:ck('new_fact_same_material_and_family',f['material_key']==v['material_key']and v['source_family']=='doi:'+f['doi'])
    newused=used&{f['fact_id']for f in newfs};ck('120new_actual_connections',len(newused)==120 and newused==set(s['new_connected_fact_ids']))
    ck('3178of4614',len(used)==3178 and sum(f['value']is not None for f in fs.values())==4614 and s['numeric_fact_connection_rate']==3178/4614)
    for r in c.execute('select *from usage_ledger'):
        u=json.loads(r['record_json']);ck('ledger_matches_actual_use',bool(u['uses'])==(r['fact_id']in used))
    # Independent XML coordinate check of each porosity and EDS table cell.
    xml=E.parse(ROOT/CP).getroot();tab=xml.find('.//table-wrap[@id="materials-19-03741-t001"]')
    for tr in tab.findall('.//tbody/tr'):
        cells=[' '.join(''.join(x.itertext()).split())for x in tr];name=cells[0]
        for field,raw in zip(['BET_surface_area_m2_g','tplot_micropore_area_m2_g','total_pore_volume_cm3_g','micropore_volume_cm3_g'],cells[1:]):ck('corn_table_cell_exact',any(f['sample_name']==name and f['field_name']==field and f['raw_value']==raw and f['value']==float(raw)for f in newfs))
    sootxml=E.parse(ROOT/SP).getroot();tab=sootxml.find('.//table-wrap[@id="tbl1"]')
    for tr in tab.findall('.//tbody/tr'):
        cells=[' '.join(''.join(x.itertext()).split())for x in tr];sample=cells[0]
        for el,raw in zip(['C','O','N','S','K','Na','P','Cl','Ca'],cells[1:]):
            f=next(f for f in newfs if f['doi']==SOOT and f['sample_name']==sample and f['field_name']=='EDS_'+el+'_wt_pct')
            ck('soot_EDS_literal_basis_and_nulls',f['value']==(float(raw)if raw else None)and f['unit']=='wt%')
    for sample in ['CS-600','CS-800','CS-1000']:
        x=[f for f in newfs if f['doi']==CORN and f['sample_name']==sample]
        ck('XPS_atomic_sum_not_envelope',abs(sum(f['value']for f in x if f['field_name']in ['XPS_C_at_pct','XPS_N_at_pct','XPS_O_at_pct','XPS_P_at_pct','XPS_S_at_pct']and f['source_path']!=SI)-100)<1e-9)
        ck('C1s_envelope_sum100',abs(sum(f['value']for f in x if f['unit']=='%ofC1s_envelope')-100)<1e-9)
    forbidden={f['fact_id']for f in newfs if (f['sample_name']=='CS-1000'and f['field_name']in ['BET_surface_area_m2_g','BET_prose_report_m2_g'])or(f['doi']==SOOT and f['sample_name']in ['AP','PS']and f['field_name']=='EDS_N_wt_pct')or'plusminus'in f['field_name']or'Uncert'in f['field_name']or'particle_size'in f['field_name']}
    ck('disputes_uncertainties_not_used',not forbidden&used)
    caps=[json.loads(r[0])for r in c.execute('select record_json from capacity_reports_v3')]
    ck('6three_electrode5device',len(caps)==11 and sum(r['configuration']=='3e_native_corn'for r in caps)==6)
    for cap in caps:
        ck('capacities_not_cycle_labels',cap['not_cycling_label']and cap['doi']==CORN)
        task='capacity:'+cap['configuration'];v=inp[task,cap['observation_id']]
        ck('reported_current_feature_matches_condition',v['features']['reported_current_A_g']==cap['conditions']['reported_current_A_g'])
        if cap['configuration'].startswith('2e'):ck('formula_dispute_scope_separate','single-electrode'in v['capacitance_basis']and v['conditions']['reference_electrode']is None)
    for (task,rid),v in inp.items():
        if v.get('provenance_release')!='v27A':continue
        def g(f):return 'EDS'if f.startswith('EDS_')else'reported_yield'if'yield'in f else group(f)
        for f in v['features']:ck('new_tasks_no_measurement_block_leakage',g(f)!=v['excluded_target_measurement_block'])
        ck('native_materials_not_ordinary_biomass',not task.startswith('material:ordinary_biomass_pretest'))
        if v['conditions']['material_stage']=='unwashed_corn_char_intermediate':ck('no_final_wash_in_crude_precursor','process__acid_wash__temperature_C'not in v['features']and'process__postwash_drying__temperature_C'not in v['features'])
    captures=read(OUT/'curve_marker_captures.json');ck('15marked_points_no_interpolation',len(captures)==15 and{a['time_min']for a in captures}=={0,3,5,8,10})
    for a in captures:
        f=fs[a['fact_id']];x,y=a['marker_center_px']
        ck('calibrated_pixel_readout',f['value']==round(56-(y-225)*16/292,1)and abs((x-583)*10/341-a['time_min'])<.1 and a['readout_tolerance_degree']==.25 and a['not_author_SD'])
    for row in c.execute('select record_json from response_reports_v3'):
        r=json.loads(row[0]);ck('adsorption_CE_not_cycle_retention',r['ready_for_cycling']is False)
    with open_training_datasets(DB,sha(DB))as d:
        ck('main3e47_34_2e31_25',d.tasks()['cycle:reported_3e']['rows']==47 and d.tasks()['cycle:reported_3e']['source_families']==34 and d.tasks()['cycle:reported_2e']['rows']==31 and d.tasks()['cycle:reported_2e']['source_families']==25)
        for doi in [CORN,SOOT]:
            z=d.training_bundle([doi]);
            for task,m in z.items():ck('whole_source_all_tasks_quarantine','doi:'+doi not in m['groups'])
        for task in ['capacity:3e_native_corn','capacity:2e_corn_author_formula']:
            m=d.matrix(task);ck('one_source_not_independent_validation',not m['source_holdout_validation_possible']and math.isclose(sum(m['sample_weight']),1))
        # v2 stable entrypoint must still be intact and report its own version.
        from data.training_current import open_training_datasets as v2open
        with v2open()as old:ck('v2_entry_preserved',old.summary['numeric_facts_connected_to_training_inputs']==3058)
    ck('all_sources_partial',all(not r['full_paper_complete']for r in read(OUT/'extraction_coverage.json')))
    ck('no_new_training_or_cycle_admission',s['new_model_fits']==0 and s['new_cycling_admissions']==0)
    result=dict(status='passed',checks=sum(n.values()),groups=dict(n),database_sha256=sha(DB),new_material_facts=160,new_numeric_facts=145,new_connected_facts=120,new_capacity_reports=11,new_model_fits=0,new_cycling_admissions=0,all_sources_fully_extracted=False)
    if save:write(OUT/'verification.json',result)
    else:ck('saved_verification_matches',read(OUT/'verification.json')==result)
    print(json.dumps(dict(status='passed',checks=result['checks'],sha256=result['database_sha256'])))
    c.close();p.close()

if __name__=='__main__':verify('--save'in sys.argv)
