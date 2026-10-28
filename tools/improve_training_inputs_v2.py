"""Versioned quality/coverage improvement over sealed v1. No fitting/admission."""
from pathlib import Path
import collections,csv,hashlib,io,json,math,re,sqlite3,sys
from xml.etree import ElementTree as ET
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from data.literature_current import open_literature_database
from tools.build_training_associations_v1 import scope,measurement_group
from tools.extend_training_associations_v1 import block

BASE=ROOT/'全量文献训练数据接入_v1_20261028'
OUT=ROOT/'全量文献训练数据接入_v2_质量与覆盖_20261028'
DB=OUT/'training_data_v2.sqlite'
def read(p):return json.loads(p.read_text('utf8'))
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def dump(v):return json.dumps(v,ensure_ascii=False,allow_nan=False)
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf8')

PRECURSOR_STAGES={'precarbonization_intermediate','hydrochar_intermediate','raw_feedstock',
 'intermediate_biochar_not_activated','precarbonized_before_KOH','intermediate_not_final_activated_carbon',
 'biochar_intermediate','raw_glycogen_before_carbonization','carbonized_biomass_control_before_activation','raw_biomass'}

def group(field):
    if any(x in field for x in ['conductivity','density','volume_packing_fraction']):return 'density_transport'
    if 'contact_angle'in field or 'uptake_g_g'in field:return 'wetting'
    if field.startswith(('SEM_','TEM_')):return 'morphology'
    if field.startswith(('HSQC_','NMR31P_')):return 'lignin_NMR'
    if field.startswith('author_atomic_') or field.startswith('author_bulk_'):return 'bulk_EA'
    return block(field)

def contract(f):
    name,u=f['field_name'],f['unit'];notes=[];method_scope=None
    if any(t in name.lower() for t in ['uncertainty','plusminus','error','binding_energy','fwhm','reported_energy']):return None
    if name=='BET_m2_g' and u=='m2/g':
        method_scope='modified_BET' if f['method']=='modified_BET' else 'source_reported_BET'
        notes=['Preserve reported BET method; no replacement of canonical BET or cycling admission.']
    elif name.startswith('XPS_') and ('envelope_pct'in name or 'fraction_within_N_pct'in name):
        if re.search(r'peak\d|component_\d',name):return None
        if u not in ['%','%C1s_envelope','%ofN1s_envelope','%ofO1s_envelope','%withinO1s','%ofN']:return None
        notes=['Within corresponding XPS envelope, never whole-material elemental fraction.',
               'Keep source-native chemical assignment; no automatic equivalence of N5/N6 and other naming.']
    elif name in ['XPS_COOH_COO_whole_material_at_pct','XPS_CO_whole_material_at_pct',
                  'XPS_C_O_OH_whole_material_at_pct','XPS_adsorbedO_whole_material_at_pct'] and u=='at%':
        notes=['Author whole-material component atoms; not within-envelope fractions or new total element measurements.']
    elif name in ['pellet_conductivity_S_m','PVP_film_conductivity_S_m','electrical_conductivity_4point_S_cm',
                  'packing_density_g_cm3','skeletal_density_He_g_cm3','geometric_disc_density_g_cm3',
                  'SEM_fiber_diameter_mean_nm','SEM_microsphere_diameter_um']:
        expected={'pellet_conductivity_S_m':'S/m','PVP_film_conductivity_S_m':'S/m','electrical_conductivity_4point_S_cm':'S/cm',
                  'packing_density_g_cm3':'g/cm3','skeletal_density_He_g_cm3':'g/cm3','geometric_disc_density_g_cm3':'g/cm3',
                  'SEM_fiber_diameter_mean_nm':'nm','SEM_microsphere_diameter_um':'um'}
        if u!=expected[name]:return None
        notes=['Measurement geometry and sample stage stay in feature name/receipt; no cross-method conversion.']
    elif name in ['water_contact_angle_deg','water_contact_angle_time_unspecified_deg'] and u=='degree':
        method_scope='water_5uL_5min_5positions' if f['doi']=='10.1021/acsomega.5c06396' else 'water_time_unspecified'
        notes=['Water wetting, not operating-electrolyte wetting; timing known only where explicitly reported.']
    elif name=='electrolyte_uptake_g_g' and u=='g/g':
        method_scope='author_electrolyte_identity_and_duration_unresolved'
        notes=['Reported empirical uptake; do not infer electrolyte identity or immersion duration.']
    elif name in ['HSQC_S_to_G_ratio','NMR31P_aliphatic_phenolic_ratio','author_atomic_H_C_ratio',
                  'author_atomic_O_C_ratio','author_bulk_H_C_mass_ratio','author_bulk_O_C_mass_ratio',
                  'author_bulk_OplusN_C_mass_ratio'] and u=='ratio':
        notes=['Reported ratio retained with method/stage; no elemental basis inferred or precursor inheritance.']
    elif name=='micro_to_meso_surface_area_ratio' and u=='ratio':
        notes=['Reported surface-area ratio, not pore-volume fraction.']
    else:return None
    field=name+'__v2'+('__'+method_scope if method_scope else '')
    return dict(field=field,original_field=name,unit=u,measurement_group=group(name),method_scope=method_scope,
                notes=notes,measurement_receipts_required=True)

def build():
    assert not OUT.exists(),'Version exists; inspect/verify without rebuilding'
    manifest=read(BASE/'merge_manifest.json')
    assert sha(BASE/'training_data_v1.sqlite')==manifest['database_sha256']
    for f in manifest['outputs']:assert sha(ROOT/f['path'])==f['sha256'],f['path']
    OUT.mkdir();src=sqlite3.connect((BASE/'training_data_v1.sqlite').as_uri()+'?mode=ro',uri=True)
    c=sqlite3.connect(DB);src.backup(c);src.close();c.row_factory=sqlite3.Row;c.execute('pragma foreign_keys=on')
    c.execute('create table feature_contract_v2(field text primary key,record_json text not null)')
    c.execute('create table measurement_metadata(fact_id integer primary key references facts,material_key text references materials,record_json text not null)')
    facts={r['fact_id']:json.loads(r['record_json']) for r in c.execute('select * from facts')}
    mats={r['material_key']:json.loads(r['record_json']) for r in c.execute('select * from materials')}
    old_used={r[0] for r in c.execute('select distinct fact_id from fact_uses')}
    freeze=read(BASE/'cross_task_freeze_review.json')['material_blocks'];ann=read(BASE/'typed_feature_contract.json')
    def blocked(mk,original):
        b=freeze.get(mk,[])
        return ('N'in b and original.startswith(('XPS_N_at_pct','XPS_N_wt_pct','XPS_N_reported_pct','XPS_C_to_N'))) or ('O'in b and original.startswith(('XPS_O_at_pct','XPS_O_wt_pct','XPS_O_reported_pct'))) or ('Raman_ratio'in b and original.startswith(('Raman_ID_IG','Raman_IG_ID','Raman_derived_crystallite')))
    decisions=[];added=collections.defaultdict(dict);idmap=collections.defaultdict(dict);descriptors={};metadata=[]
    with open_literature_database() as l:
        canon={mk:l.canonical_material_features_v13(m['doi'],m['sample_name']) for mk,m in mats.items()}
        for fid,f in facts.items():
            name=f['field_name'];mk=f['material_key'];v=f['value']
            # Spectral assignment constants and reported +/- values remain useful
            # provenance, never independent samples, inputs, or utilization credit.
            if v is not None and (('XPS_'in name and f['unit']=='eV') or any(s in name.lower() for s in ['plusminus','uncertainty'])):
                targets=[a['fact_id'] for a in facts.values() if a['material_key']==mk and a['field_name']==name.replace('_author_plusminus','').replace('_reported_uncertainty','') and a['fact_id']!=fid]
                value=dict(fact_id=fid,material_key=mk,field=name,value=v,unit=f['unit'],
                           kind='author_uncertainty_unspecified_statistic' if 'XPS_'not in name else 'spectral_assignment_metadata',
                           measured_fact_ids=targets,source_receipt=f,not_predictor=True,not_independent_target=True)
                c.execute('insert into measurement_metadata values(?,?,?)',(fid,mk,dump(value)));metadata.append(value)
            desc=contract(f)
            if not desc or v is None:continue
            selected=canon[mk]['values'].get(name);p=canon[mk]['provenance'].get(name,{})
            explicit=isinstance(p.get('decision'),dict) and 'selected_value'in p['decision']
            reason=None
            if blocked(mk,name):reason='historical_field_freeze'
            elif selected is None or selected!=v:reason='canonical_competing_report_not_selected'
            elif any(s in f['review_status'] for s in ['ambiguous','conflict']) and not explicit:reason='method_conflict'
            elif not math.isfinite(v) or v<0:reason='numeric_domain'
            elif ('contact_angle'in name and v>180) or ('XPS_'in name and 'pct'in name and v>100):reason='numeric_domain'
            if reason:decisions.append(dict(fact_id=fid,decision='held',reason=reason));continue
            field=desc['field'];descriptors[field]=desc;added[mk][field]=v;idmap[mk].setdefault(field,[]).append(fid)
            decisions.append(dict(fact_id=fid,field=field,decision='selected_same_material_method_stage'))
    for field,a in descriptors.items():c.execute('insert into feature_contract_v2 values(?,?)',(field,dump(a)))
    for mk,ff in added.items():
        for field,value in ff.items():c.execute('insert into selected_features values(?,?,?,?)',(mk,field,value,dump(sorted(idmap[mk][field]))))
    def add_use(fid,task,rid,field,role):c.execute('insert or ignore into fact_uses values(?,?,?,?,?)',(fid,task,rid,field,role))
    def original(field):return descriptors.get(field,ann.get(field,{})).get('original_field',field)
    changes=[]
    for r in c.execute('select *from inputs').fetchall():
        row=json.loads(r['record_json']);task=r['task'];mk=r['material_key'];new=[]
        # Lineage inputs only describe the explicit precursor, never the child.
        owner=row['lineage_path'][0] if task.startswith('lineage:') else mk
        for field,value in added.get(owner,{}).items():
            if task.startswith('material:') and group(original(field))==row['excluded_target_measurement_block']:continue
            prefix='lib__' if task.startswith('cycle:') else 'precursor__' if task.startswith('lineage:') else ''
            target=prefix+field
            if target in row['features']:continue
            row['features'][target]=value;new.append(target)
            for fid in idmap[owner][field]:add_use(fid,task,r['row_id'],target,'input')
        if new:
            row['v2_additions']=new;c.execute('update inputs set record_json=?where task=?and row_id=?',(dump(row),task,r['row_id']))
            changes.append(dict(task=task,row_id=r['row_id'],fields=new))
    # Only already-defined material scopes or explicitly listed biomass stages
    # receive new reconstruction tasks. These never become cycling endpoints.
    created=[]
    for mk,m in mats.items():
        task_scope=m['task_scope'];stage=m['material_stage'];precursor=stage in PRECURSOR_STAGES
        if task_scope=='reference_or_unresolved' or (task_scope=='stage_specific_material_only' and not precursor):continue
        allf={r['field']:r['value'] for r in c.execute('select *from selected_features where material_key=?',(mk,))}
        allids={r['field']:json.loads(r['fact_ids_json']) for r in c.execute('select *from selected_features where material_key=?',(mk,))}
        targets=allf if precursor and task_scope=='stage_specific_material_only' else added.get(mk,{})
        for target,y in targets.items():
            g=group(original(target));xx={f:v for f,v in allf.items() if group(original(f))!=g}
            prep={};ev=[];conflicts=set()
            for item in m['synthesis']:
                for st in item['stages']:
                    if st.get('stage')=='electrode_preparation':continue
                    for key in ['temperature_C','duration_h','heating_rate_C_min']:
                        value=st.get(key)
                        if not isinstance(value,(int,float)) or isinstance(value,bool):continue
                        field='process__'+st['stage']+'__'+key
                        if field in conflicts:continue
                        if field in prep and prep[field]!=value:prep.pop(field);conflicts.add(field);continue
                        prep[field]=value;ev.append(dict(field=field,value=value,path=item['source_path'],sha256=item['sha256'],locator=item['locator']))
            # A raw/precursor characterization cannot receive later final-product
            # recipes. Only its own already-bound characterization values are used.
            if not precursor:xx.update(prep)
            if not xx:continue
            task=('precursor:'+stage if task_scope=='stage_specific_material_only' else 'material:'+task_scope)+':'+target
            row=dict(row_id=mk,material_key=mk,sample_name=m['sample_name'],source_family=m['source_family'],features=xx,target=y,target_name=target,
                     excluded_target_measurement_block=g,process_evidence=[] if precursor else ev,
                     conditions=dict(material_stage=stage,material_task_scope=task_scope,target_unit=descriptors.get(target,ann.get(target,{})).get('unit')),
                     ready_for_training_inputs=True,ordinary_cycle_admission=False,method_stage_contract_version='v2',
                     independent_validation_required=True)
            c.execute('insert into inputs values(?,?,?,?)',(task,mk,mk,dump(row)));created.append(dict(task=task,row_id=mk))
            for field in xx:
                for fid in allids.get(field,[]):add_use(fid,task,mk,field,'input')
            for fid in allids[target]:add_use(fid,task,mk,target,'target')
        m['features']=allf;c.execute('update materials set record_json=?where material_key=?',(dump(m),mk))
    uses=collections.defaultdict(list)
    for r in c.execute('select *from fact_uses'):uses[r['fact_id']].append(dict(task=r['task'],row_id=r['row_id'],feature=r['feature'],role=r['role']))
    for fid,f in facts.items():
        u=json.loads(c.execute('select record_json from usage_ledger where fact_id=?',(fid,)).fetchone()[0]);connected=bool(uses.get(fid))
        if connected:u['disposition']='connected_to_training_inputs'
        u.update(uses=uses.get(fid,[]),training_connected=connected)
        c.execute('update usage_ledger set disposition=?,record_json=?where fact_id=?',(u['disposition'],dump(u),fid))
    counts={}
    for task, in c.execute('select distinct task from inputs'):
        rr=[json.loads(r[0]) for r in c.execute('select record_json from inputs where task=?',(task,))];families={r['source_family'] for r in rr}
        counts[task]=dict(rows=len(rr),source_families=len(families),source_holdout_validation_possible=len(families)>=2)
    numeric_used={fid for fid in uses if facts[fid]['value'] is not None};new_used=sorted(numeric_used-old_used)
    summary=read(BASE/'summary.json');summary.update(version='training_inputs_v2',parent_database_sha256=sha(BASE/'training_data_v1.sqlite'),
        numeric_facts_connected_to_training_inputs=len(numeric_used),numeric_fact_connection_rate=len(numeric_used)/4469,
        additional_connected_numeric_facts=len(new_used),remaining_unconnected_numeric_facts=4469-len(numeric_used),
        additional_main3e_nonmissing_cells=sum(len(r['fields']) for r in changes if r['task']=='cycle:reported_3e'),
        additional_typed_fields=len(descriptors),new_material_or_precursor_task_rows=len(created),task_counts=counts,
        measurement_metadata_facts=len(metadata),metadata_excluded_from_training_connection_count=True,new_model_fits=0,new_cycling_admissions=0)
    summary['usage_counts']=dict(collections.Counter(r[0] for r in c.execute('select disposition from usage_ledger')))
    c.execute("update metadata set value_json=?where key='summary'",(dump(summary),));c.commit();c.close()
    write(OUT/'summary.json',summary);write(OUT/'typed_feature_contract_v2.json',descriptors)
    write(OUT/'field_decisions.json',decisions);write(OUT/'input_changes.json',changes)
    write(OUT/'new_task_rows.json',created);write(OUT/'new_connected_fact_ids.json',new_used)
    write(OUT/'measurement_metadata.json',metadata);write(OUT/'source_family_rules.json',read(BASE/'source_family_rules.json'))
    protected={str((BASE/'merge_manifest.json').relative_to(ROOT)):sha(BASE/'merge_manifest.json')}
    protected.update({f['path']:f['sha256'] for f in manifest['outputs']});protected.update(read(BASE/'protected_inputs.json'))
    evidence={};relevant={facts[r['fact_id']]['source_path'] for r in decisions if r['decision'].startswith('selected')}
    for path in sorted(relevant):
        p=ROOT/path;expected={f['source_sha256'] for f in facts.values() if f['source_path']==path}
        assert sha(p) in expected,path;protected[path]=sha(p)
        if p.suffix.lower()=='.xml':
            e=ET.parse(p).getroot();tables=[]
            wanted={f.get('xml_id') for f in facts.values() if f['source_path']==path and contract(f)}
            for t in e.iter('table-wrap'):
                if t.get('id') in wanted:tables.append(dict(locator='XML table-wrap '+str(t.get('id')),text=' '.join(''.join(t.itertext()).split())))
            evidence[path]=dict(sha256=sha(p),tables=tables)
        else:evidence[path]=dict(sha256=sha(p),receipts='Original qualified SI/figure locator in each source fact; reviewed SI density and conductivity pages S7/S8/S26.')
    write(OUT/'source_evidence_review.json',evidence);write(OUT/'protected_inputs.json',protected)
    write(ROOT/'data/current_training_inputs.json',dict(version='training_inputs_v2',directory=str(OUT.relative_to(ROOT)).replace('\\','/'),database_file=DB.name,sha256=sha(DB),
        previous_entry='data.training_datasets (immutable v1)',entry='data.training_current',new_model_fits=0))
    print(dump({k:summary[k] for k in ['additional_connected_numeric_facts','numeric_facts_connected_to_training_inputs','remaining_unconnected_numeric_facts','additional_main3e_nonmissing_cells','additional_typed_fields','new_material_or_precursor_task_rows']}))

if __name__=='__main__':build()
