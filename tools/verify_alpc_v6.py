"""Read-only ALPC evidence, invariants and callable-input verification."""
from pathlib import Path
import collections,copy,hashlib,json,sqlite3,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.extract_alpc_v6 import BASE,OUT,DB,DOI,MAIN,SI,EIDS,TABLE,FIELDS,HELD,block,read,write,sha
from data.training_latest import open_training_datasets
from data.training_store import open_training_datasets as open_parent

def verify(save=False):
    checks=collections.Counter()
    def ck(group,condition):
        if not condition:raise AssertionError(group)
        checks[group]+=1
    for p,h in read(OUT/'protected_inputs.json').items():ck('protected_originals_and_parent_outputs',sha(ROOT/p)==h)
    raw=sqlite3.connect(DB.as_uri()+'?mode=ro',uri=True);raw.row_factory=sqlite3.Row
    ck('SQLite_integrity',raw.execute('pragma integrity_check').fetchone()[0]=='ok');ck('physical_foreign_keys',not raw.execute('pragma foreign_key_check').fetchall())
    facts=read(OUT/'new_facts.json');s=read(OUT/'summary.json');fs={f['fact_id']:f for f in facts};changes=read(OUT/'overlay_changes.json');parent=read(BASE/'entrypoint_snapshot.json')
    ck('91facts85numeric6unknown',len(facts)==91 and sum(f['value']is not None for f in facts)==85)
    with open_training_datasets()as d,open_parent(BASE/parent['database_file'],parent['sha256'])as old:
        c=d.connection
        overrides={(r['table'],tuple(r['key'])):r for r in changes}
        for table, in old.connection.execute('select name from main.sqlite_master where type="table" and name!="metadata"'):
            info=old.connection.execute('pragma main.table_info('+table+')').fetchall();pk=[r['name']for r in sorted(info,key=lambda x:x['pk'])if r['pk']]
            if not pk:continue
            actual={tuple(r[k]for k in pk):tuple(r)for r in c.execute('select *from '+table)}
            for r in old.connection.execute('select *from '+table):
                key=tuple(r[k]for k in pk)
                if(table,key)in overrides:continue
                ck('parent_rows_unchanged:'+table,actual[key]==tuple(r))
        for table in json.loads(raw.execute('select value_json from metadata where key="append_only_union_tables"').fetchone()[0]):
            info=raw.execute('pragma table_info('+table+')').fetchall();pk=[r['name']for r in sorted(info,key=lambda x:x['pk'])if r['pk']]
            if pk:
                vals=[tuple(x)for x in c.execute('select '+','.join(pk)+' from '+table)];ck('logical_PK_unique:'+table,len(vals)==len(set(vals)))
        for x in changes:
            a,b=x['before_record'],x['after_record']
            if x['table']=='cycle_records':ck('original_cycle_physical_passthrough',a==b and x['before_sha256']==x['after_sha256'])
            else:
                ck('target_conditions_unchanged',a['target']==b['target']and a['target_name']==b['target_name']and a['conditions']==b['conditions'])
                for k,v in a['features'].items():
                    if v is not None:ck('old_nonmissing_feature_unchanged',b['features'][k]==v)
        main={r['row_id']:r for r in d.rows('cycle:reported_3e')};prior={r['row_id']:r for r in old.rows('cycle:reported_3e')}
        ck('47rows34families',set(main)==set(prior)and len(main)==47 and len({r['source_family']for r in main.values()})==34)
        added=attested=0
        for eid in EIDS:
            a,b=prior[eid],main[eid];e=b['v6_material_evidence'];added+=sum(v is not None and a['features'].get(k)is None for k,v in b['features'].items());attested+=len(e['existing_values_attested'])
            ck('same_material_two_conditions',b['sample_name']=='ALPC-800'and b['material_key']=='literature:v29_ALPC:ALPC-800'and a['material_key']is None)
            ck('own_total_BET_not_overwritten',b['features']['BET_m2_g']==718 and b['features']['total_pore_volume_cm3_g']==.35)
            ck('three_controversial_micropore_cells_not_forced',b['features']['micropore_volume_cm3_g']is None and b['features']['micropore_surface_area_m2_g']is None)
            ck('EDX_XPS_distinct',b['features']['EDX_N_atomic_pct']==11.23 and b['features']['EDX_O_atomic_pct']==8.54 and b['features']['XPS_N_atomic_pct_v15']==4.64 and b['features']['XPS_O_atomic_pct_v15']==7.44)
            ck('ORR_loading_not_supercapacitor_loading',b['features']['mass_loading_mg_cm2']==1.2 and b['features']['mass_loading_mg_cm2']!=.35)
            ck('no_second_carbonization_invented',b['features']['carbonization_temperature_C']is None and b['features']['activation_temperature_C']==800)
            ck('no_overnight_or_KOH_ratio_guess','process__final_dry_duration_h'not in b['features']and'process__KOH_to_raw_leaf_mass_ratio'not in b['features'])
        ck('38new16attested',added==38 and attested==16 and s['additional_main3e_nonmissing_cells']==38)
        ck('main_links23_all55',len({eid for eid in main if c.execute('select 1 from cycle_material_links where endpoint_id=?',(eid,)).fetchone()})==23 and c.execute('select count(*)from cycle_material_links').fetchone()[0]==55)
        ck('original287cycles',c.execute('select count(*)from cycle_records').fetchone()[0]==287)
        used=set()
        for r in raw.execute('select *from fact_uses'):
            f=fs[r['fact_id']];row=json.loads(c.execute('select record_json from inputs where task=?and row_id=?',(r['task'],r['row_id'])).fetchone()[0]);value=row['target']if r['role']=='target'else row['features'][r['feature']]
            ck('fact_receipt_actual_value',value==f['value']and value is not None);ck('fact_receipt_material_source',row['material_key']==f['material_key']and row['source_family']=='doi:'+DOI);used.add(r['fact_id'])
        ck('76connected_unique_new',len(used)==76 and used==set(s['new_connected_fact_ids']))
        ck('3467of4922',c.execute('select count(distinct fact_id)from fact_uses').fetchone()[0]==3467 and c.execute('select sum(numeric)from facts').fetchone()[0]==4922 and s['numeric_fact_connection_rate']==3467/4922)
        ck('ledger_all5175',c.execute('select count(*)from facts').fetchone()[0]==5175 and c.execute('select count(*)from usage_ledger').fetchone()[0]==5175)
        for f in facts:
            if (f['sample_name'],f['field_name'])in HELD or f.get('value_kind')=='coarse_series_approximate_metadata':ck('held_or_coarse_not_connected',f['fact_id']not in used)
        ck('three_new_held_values_retained',raw.execute('select count(*)from held_features').fetchone()[0]==3)
        for r in raw.execute('select *from inputs where task not like "cycle:%"'):
            row=json.loads(r['record_json'])
            if r['task'].startswith('material:'):
                for field in row['features']:ck('same_measurement_block_and_future_protocol_excluded',block(field)!=row['excluded_target_measurement_block']and block(field)!='electrode_protocol')
            else:ck('cap_or_EIS_not_cycling_target',row['target_name']!='capacitance_retention_pct'and'discharge_time_s'not in row['features'])
        ordinary={r['row_id']:r for r in d.rows('capacity:3e_reported')};expanded={r['row_id']:r for r in d.rows('capacity:3e_with_graph')}
        ck('220_nested425',len(ordinary)==220 and len(expanded)==425 and set(ordinary)<=set(expanded))
        for rid,r in ordinary.items():ck('nested_values_same',r['target']==expanded[rid]['target'])
        ck('ordinary33families',len({r['source_family']for r in ordinary.values()})==33)
        newcaps=read(OUT/'new_capacity_reports.json');ck('34unique_cap_reports',len(newcaps)==34 and len({r['observation_id']for r in newcaps})==34)
        for r in newcaps:
            if r['role']=='bounded_graph_readout':
                ck('graph_only_not_ordinary',r['observation_id']in expanded and r['observation_id']not in ordinary)
                x=r['readout'];ck('graph_readout_not_SD',x['readout_interval_F_g'][0]<r['value']<x['readout_interval_F_g'][1]and x['current_axis_tolerance_A_g']==.1 and 'not_SD'in x['uncertainty_kind'])
        ck('27_new_graph_conditions',sum(r['role']=='bounded_graph_readout'for r in newcaps)==27)
        ck('ambiguous_acid_CV_not_mapped',not any(r['conditions']['method']=='CV'and r['conditions']['electrolyte']=='H2SO4'for r in newcaps))
        ck('no_409_silent_target',not any(r['value']==409 for r in newcaps))
        ck('28secondary10DFTcells_separate',c.execute('select count(*)from secondary_comparisons_v6').fetchone()[0]==28 and c.execute('select count(*)from DFT_reports_v6').fetchone()[0]==5)
        for task in d.tasks():
            mm=d.matrix(task,[DOI]);ck('whole_DOI_all_aux_tasks_holdout','doi:'+DOI not in mm['groups'])
        split=d.source_split('cycle:reported_3e',[DOI]);ck('two_same_source_holdout_together',set(split['test']['row_ids'])==set(EIDS)and not(set(split['train']['groups'])&set(split['test']['groups'])))
        ck('no_fits_admissions_fixed37',s['new_model_fits']==0 and s['new_cycling_admissions']==0 and s['original_pending']==37)
        ck('cumulative_cells203',s['cumulative_main3e_material_cells_added_since_v12']==203)
        for db in ['main','parent0','parent1','parent2']:
            try:c.execute('update '+db+'.sources set record_json=record_json')
            except sqlite3.OperationalError:ck('all_layers_readonly',True)
            else:raise AssertionError('Writable '+db)
    raw.close()
    # Fresh parsing uses no curator constants for secondary rows/DFT values.
    from pypdf import PdfReader
    import re
    mainreader=PdfReader(ROOT/MAIN);sireader=PdfReader(ROOT/SI)
    normalized=lambda t:re.sub(r'\s+',' ',t)
    t=normalized(mainreader.pages[5].extract_text());ck('primary_XPS_atomic_text','7.44 atom %'in t and '4.64 atom %'in t)
    t=normalized(mainreader.pages[9].extract_text());ck('primary_GCD_anchors','421 F g'in t and '264 F g'in t and '170 F g'in t and '255 F g'in t)
    ck('primary_EIS_own_anchors',all(str(x)in t for x in ['15.06','12.50','25.25']))
    comp=read(OUT/'secondary_and_DFT_tables.json')
    for row in comp['secondary_rows']:
        p=12 if row['table']=='S2' else 24;txt=normalized(sireader.pages[p].extract_text())
        # Each value is checked in its table body; row identity/cell direction is
        # retained in the structured review and visual S1 image separately.
        for key,v in row['values'].items():
            if isinstance(v,(int,float))and key not in ['rpm']:
                literal=re.escape(str(v))+(r'0*'if '.'in str(v)else'')
                ck('secondary_PDF_values_reparsed',re.search(r'(?<![\d.])'+literal+r'(?![\d.])',txt)is not None)
    for row in comp['DFT_rows']:
        for p,k in [(18,'bond_distance_A'),(19,'adsorption_free_energy_eV')]:ck('DFT_PDF_values_reparsed',str(row[k])in normalized(sireader.pages[p].extract_text()))
    trans=read(OUT/'TableS1_visual_transcription.json');ck('S1_image_not_fake_text_OCR',sha(OUT/trans['evidence_image'])==trans['image_sha256']and 'Not claimed independent OCR'in trans['transcription_method'])
    for name,values in trans['rows'].items():
        for field,v in zip(trans['fields'],values):ck('21_S1_transcribed_cells_receipted',any(f['sample_name']==name and f['field_name']==field and f['value']==v and f['source_path']==SI for f in facts))
    result=dict(status='passed',checks=sum(checks.values()),groups=dict(checks),database_sha256=sha(DB),new_model_fits=0,new_cycling_admissions=0,scope_limitations=['S1 image cells visually transcribed, not independently OCRed.','Full continuous curves and disputed table method remain incomplete.'])
    if save:write(OUT/'verification.json',result)
    print(json.dumps({k:v for k,v in result.items()if k!='groups'},ensure_ascii=False))

if __name__=='__main__':verify('--save'in sys.argv)
