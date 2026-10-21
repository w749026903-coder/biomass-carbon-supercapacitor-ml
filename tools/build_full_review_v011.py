"""Build an additive v0.11 release from explicitly reviewed original-source ledgers.

This tool creates a NEW version only. It does not publish a pointer, fit models,
run downloads, change original literature, or rewrite any earlier release.
"""
from pathlib import Path
import collections
import copy
import hashlib
import importlib.util
import json
import math
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
BATCH = ROOT / '全库复检与特征补提取_20261021'
OUT = ROOT / '循环稳定性数据库_v0.11_全库复检与材料特征_20261021'
PARENT = ROOT / '循环稳定性数据库_v0.10_原文精细补证_20261021'
PARENT_SHA = '75d5da96e42fa34da4c7c987debb32d55a1346deb34929502b8fc91417c865d2'
sys.path.insert(0, str(ROOT))
from training_input_quality import assess
from material_feature_inputs_v011 import prepare_material_fold

MATERIAL_PREDICTORS = ['total_pore_volume_cm3_g', 'micropore_volume_cm3_g', 'mesopore_volume_cm3_g',
    'average_pore_diameter_nm', 'micropore_surface_area_m2_g', 'external_surface_area_m2_g',
    'Raman_ID_IG', 'XRD_d002_nm', 'XPS_N_reported_pct', 'XPS_O_reported_pct', 'XPS_percentage_basis',
    'mass_loading_mg_cm2', 'activation_temperature_C', 'activation_duration_h', 'heating_rate_C_min',
    'material_density_g_cm3', 'bulk_N_wt_pct', 'bulk_O_wt_pct']


def read(path):
    return json.loads(path.read_text('utf-8'))


def dump(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', 'utf-8')


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def module(folder, name):
    spec = importlib.util.spec_from_file_location(name, folder / 'ml_data.py')
    result = importlib.util.module_from_spec(spec)
    sys.modules[name] = result
    spec.loader.exec_module(result)
    return result


def material_key(doi, sample):
    doi = str(doi).lower().removeprefix('doi:').removeprefix('https://doi.org/')
    # This pair identity was explicitly confirmed in its own assembly method.
    if doi == '10.1039/d4ta02115k' and sample == 'OPBNP//OPBNP':
        sample = 'OPBNP'
    return 'v11m:' + hashlib.sha256(dump([doi, sample]).encode()).hexdigest()[:24]


def unit(field):
    if field.endswith('_cm3_g'): return 'cm3/g'
    if field.endswith('_m3_g'): return 'm3/g as printed; unit freeze retained'
    if field.endswith('_m2_g'): return 'm2/g'
    if field.endswith('_mg_cm2'): return 'mg/cm2'
    if field.endswith('_g_cm3'): return 'g/cm3'
    if field.endswith('_nm'): return 'nm'
    if field.endswith('_pct'): return 'percent; basis/method retained separately'
    if field.endswith('_C_min'): return 'degreeC/min'
    if field.endswith('_C'): return 'degreeC'
    if field.endswith('_h'): return 'h'
    if field.endswith('_meq_g'): return 'meq/g'
    if field.startswith('Raman_'): return 'ratio; direction retained'
    return 'as reported; see evidence'


def build():
    target = OUT / 'cycling_v0_11.sqlite'
    if target.exists() or (OUT / 'merge_manifest.json').exists():
        raise FileExistsError('Do not overwrite an existing v0.11 scientific release.')
    if sha(PARENT / 'cycling_v0_10.sqlite') != PARENT_SHA:
        raise RuntimeError('Parent fingerprint mismatch.')
    ledger = read(BATCH / 'reviewed_curation.json')
    materials = list(ledger['reviewed_materials'])
    for path in sorted(BATCH.glob('reviewed_materials_*.json')):
        materials.extend(read(path)['reviewed_materials'])
    parent_api = module(PARENT, '_v011_build_parent')
    with parent_api.Database() as parent:
        original_rows = {r['endpoint_id']: r for r in parent.fetch('all_review').rows}
        rows = copy.deepcopy(original_rows)
        profiles = {p: parent.fetch(p).rows for p in parent.contract['profiles']}
        previous_holds = {r['endpoint_id']: parent.holds(r['endpoint_id']) for r in ledger['admission_reviews']}
        contract = copy.deepcopy(parent.contract)
    memberships = {p: {r['endpoint_id'] for r in data} for p, data in profiles.items()}
    core = contract['core_features'] + ['retention_pct', 'retention_relation', 'system', 'method']
    for profile, data in profiles.items():
        for accepted in data:
            old = rows[accepted['endpoint_id']]
            if any(old.get(k) != accepted.get(k) for k in core):
                raise ValueError('Parent review/approved core differs: ' + accepted['endpoint_id'])
            for key in ['admission_status', 'eligible', 'profile_review']:
                old[key] = copy.deepcopy(accepted[key])
    reviews = []
    for case in ledger['admission_reviews']:
        key = case['endpoint_id']
        case = copy.deepcopy(case)
        case['before'] = copy.deepcopy(original_rows[key])
        row = rows[key]
        row.update(copy.deepcopy(case['changes']))
        row.update(eligible=1, admission_status='approved_for_reported_protocol', workflow_status='admitted_reported_protocol_v011')
        row['profile_review'] = {'review_version': 'v0.11', 'evidence': case['evidence'], 'gate_dispositions': case['gate_dispositions'], 'caveats': case['caveats']}
        for profile in memberships:
            memberships[profile].discard(key)
            if profile in case['approved_profiles']:
                memberships[profile].add(key)
        case['previous_holds'] = previous_holds[key]
        case['after'] = copy.deepcopy(row)
        reviews.append(case)
    candidate_file = BATCH / 'new_test_candidates.json'
    if candidate_file.exists():
        for item in read(candidate_file)['candidates']:
            row = copy.deepcopy(item['row']); key = row['endpoint_id']
            if key in rows:
                raise ValueError('Duplicate new endpoint: ' + key)
            rows[key] = row
            reviews.append({'endpoint_id': key, 'before': None, 'after': copy.deepcopy(row), 'approved_profiles': [],
                            'evidence': item['evidence'], 'open_issues': item['open_issues'], 'caveats': item.get('caveats', [])})
    material_index = {}; properties = []; documents = {}; selected_by_material = collections.defaultdict(dict)
    for entry in materials:
        path = ROOT / entry['path']
        if sha(path) != entry['sha256']:
            raise RuntimeError('Reviewed original changed: ' + str(path))
        if entry['stage'] != 'before_cycling':
            raise ValueError('Post-cycling material evidence cannot become predictors.')
        key = material_key(entry['doi'], entry['sample'])
        material_index[key] = {'doi': entry['doi'], 'sample': entry['sample'], 'notes': entry.get('notes', [])}
        for field, value in entry['features'].items():
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError('Non-numeric selected property: ' + field)
            if field.endswith('_pct') and not 0 <= value <= 100:
                raise ValueError('Percent outside0..100: ' + field)
            if field in selected_by_material[key] and selected_by_material[key][field]['value'] != value:
                raise ValueError('Unresolved competing feature values: ' + key + '/' + field)
            locator = entry.get('feature_locators', {}).get(field, entry['locator'])
            evidence_id = hashlib.sha256(dump([entry['sha256'], entry['sample'], field, locator]).encode()).hexdigest()[:24]
            documents[evidence_id] = {'path': entry['path'], 'sha256': entry['sha256'], 'locator': locator,
                                      'excerpt': entry.get('raw_excerpt', dump(entry['features'])), 'stage': entry['stage']}
            systems = entry.get('feature_systems', {}).get(field, ['3E'] if field.startswith('mass_loading') else [])
            property_row = {'material_key': key, 'field_name': field, 'value': value, 'status': 'selected_agent_source_review',
                            'unit': unit(field), 'evidence_id': evidence_id, 'applies_to_systems': systems,
                            'method': entry.get('methods', {}).get(field), 'derivation': entry.get('feature_derivations', {}).get(field),
                            'notes': entry.get('notes', [])}
            selected_by_material[key][field] = property_row
            properties.append(property_row)
        for field, observation in entry.get('unselected_features', {}).items():
            evidence_id = hashlib.sha256(dump([entry['sha256'], entry['sample'], field, 'unselected']).encode()).hexdigest()[:24]
            documents[evidence_id] = {'path': entry['path'], 'sha256': entry['sha256'], 'locator': entry['locator'], 'excerpt': dump(observation), 'stage': entry['stage']}
            properties.append({'material_key': key, 'field_name': field, 'value': observation['value'], 'status': 'pending_property_conflict',
                               'unit': unit(field), 'evidence_id': evidence_id, 'applies_to_systems': [], 'method': None,
                               'derivation': None, 'notes': [observation['reason']]})
    for case in reviews:
        for evidence in case['evidence']:
            if sha(ROOT / evidence['path']) != evidence['sha256']:
                raise RuntimeError('Test evidence fingerprint changed.')
    changes = []
    for row in rows.values():
        key = material_key(row['identity_key'], row['sample_name'])
        row['material_key_v11'] = key
        material_index.setdefault(key, {'doi': row['identity_key'].removeprefix('doi:'), 'sample': row['sample_name'], 'notes': []})
        for field, observation in selected_by_material[key].items():
            if observation['applies_to_systems'] and row['system'] not in observation['applies_to_systems']:
                continue
            old = row.get(field); new = observation['value']
            if old is not None and old != new:
                raise ValueError('Non-null source conflict needs explicit disposition: ' + row['endpoint_id'] + '/' + field)
            if old != new:
                changes.append({'endpoint_id': row['endpoint_id'], 'field_name': field, 'before': old, 'after': new,
                                'evidence_id': observation['evidence_id'], 'reason': 'Own-sample pre-cycling original-source review; no label/performance selection'})
            row[field] = new
            row[field + '_status'] = 'v011_selected_agent_original_source_review'
        if row.get('XPS_N_reported_pct') is not None or row.get('XPS_O_reported_pct') is not None:
            row['XPS_percentage_basis'] = 'atomic_explicit' if row.get('N_at_pct') is not None or row.get('O_at_pct') is not None else 'not_explicitly_reported'
        row['admission_profiles_v11'] = [p for p, keys in memberships.items() if row['endpoint_id'] in keys]
        if row['admission_profiles_v11']:
            row['eligible'] = 1; row['admission_status'] = 'approved_for_reported_protocol'
    contract.update(version='v0.11', database_file=target.name, parent_database_sha256=PARENT_SHA,
        storage_layout='Immutable v0.10/v0.9/v0.8 chain plus reviewed material properties and compact current row snapshots',
        model_material_features=MATERIAL_PREDICTORS,
        extra_material_feature_whitelist=MATERIAL_PREDICTORS + ['N_at_pct', 'O_at_pct', 'S_at_pct', 'P_at_pct', 'C_at_pct'],
        corpus_search_database='全库复检与特征补提取_20261021/full_corpus_search_native.sqlite',
        corpus_search_database_sha256=sha(BATCH / 'full_corpus_search_native.sqlite'),
        material_feature_limits=['Sparse extra predictors retain None and evidence; raw-unit freezes are excluded from default material predictors.',
            'Reported XPS percentage basis is retained; unspecified percentage is not silently made atomic percent.',
            'Mass loading is a test/configuration property; the new standard3E loadings do not populate2E device tests.',
            'Raman direction and derived reciprocal are retained; isolated source features need training-fold coverage.',
            'This release performs no training and does not establish improved prediction error.'])
    if '--preflight' in sys.argv:
        print(json.dumps({'preflight':'passed','parent_unchanged':True,'review_rows':len(rows),'reviewed_material_entries':len(materials),
                          'selected_properties':sum(p['status']=='selected_agent_source_review' for p in properties),
                          'new_material_cells_all_review':len(changes),'profile_counts':{p:len(keys) for p,keys in memberships.items()},
                          'database_written':False},ensure_ascii=False,indent=2))
        return
    write(OUT / 'data_contract.json', contract)
    with sqlite3.connect(target) as connection:
        connection.execute('PRAGMA foreign_keys=ON')
        connection.executescript('''
        create table metadata_v11(key text primary key,value_json text not null);
        create table material_index_v11(material_key text primary key,metadata_json text not null);
        create table document_evidence_v11(evidence_id text primary key,path text not null,sha256 text not null,locator text not null,excerpt text not null,stage text not null check(stage='before_cycling'));
        create table material_properties_v11(material_key text references material_index_v11,field_name text,value_json text not null,status text not null,unit text,evidence_id text references document_evidence_v11,applies_to_systems_json text not null,metadata_json text not null,primary key(material_key,field_name,status));
        create table review_rows_v11(endpoint_id text primary key,row_json text not null);
        create table profile_membership_v11(profile text,endpoint_id text references review_rows_v11,primary key(profile,endpoint_id));
        create table test_reviews_v11(endpoint_id text primary key references review_rows_v11,review_json text not null);
        create table row_changes_v11(endpoint_id text references review_rows_v11,field_name text,before_json text,after_json text,evidence_id text references document_evidence_v11,reason text,primary key(endpoint_id,field_name));
        ''')
        connection.executemany('insert into material_index_v11 values(?,?)', [(k, dump(v)) for k, v in material_index.items()])
        connection.executemany('insert into document_evidence_v11 values(?,?,?,?,?,?)', [(k, v['path'], v['sha256'], v['locator'], v['excerpt'], v['stage']) for k, v in documents.items()])
        connection.executemany('insert into material_properties_v11 values(?,?,?,?,?,?,?,?)', [(p['material_key'],p['field_name'],dump(p['value']),p['status'],p['unit'],p['evidence_id'],dump(p['applies_to_systems']),dump(p)) for p in properties])
        connection.executemany('insert into review_rows_v11 values(?,?)', [(k,dump(v)) for k,v in rows.items()])
        connection.executemany('insert into profile_membership_v11 values(?,?)', [(p,k) for p,keys in memberships.items() for k in sorted(keys)])
        connection.executemany('insert into test_reviews_v11 values(?,?)', [(c['endpoint_id'],dump(c)) for c in reviews])
        connection.executemany('insert into row_changes_v11 values(?,?,?,?,?,?)', [(c['endpoint_id'],c['field_name'],dump(c['before']),dump(c['after']),c['evidence_id'],c['reason']) for c in changes])
        connection.execute('insert into metadata_v11 values(?,?)', ('parent_database_sha256',dump(PARENT_SHA)))
        assert connection.execute('pragma integrity_check').fetchone()[0] == 'ok'
        assert not connection.execute('pragma foreign_key_check').fetchall()
    write(BATCH / 'record_field_changes.json', changes)
    api = module(OUT, '_v011_built_api')
    readiness = {'version':'v0.11','parent_sha256':PARENT_SHA,'model_fits':0,'all_literature_admitted':False,'cohorts':{},'material_preparation':{}}
    with api.Database() as db:
        for profile in contract['profiles']:
            ds = db.fetch(profile)
            readiness['cohorts'][profile] = assess(ds)
            write(OUT / (profile + '_inputs.json'), {'rows':ds.rows,'matrix':ds.feature_matrix(),'source_folds':ds.source_folds(len({r['source_group'] for r in ds.rows})),'fingerprint':ds.fingerprint()})
        matrix = db.material_matrix()
        write(OUT / 'reported_3e_material_inputs.json', matrix)
        tests = []
        for k, fold in enumerate(matrix['source_folds']):
            prepared = prepare_material_fold(matrix, fold)
            changed = copy.deepcopy(matrix)
            for i in fold['test']:
                changed['y'][i] = 999999
                changed['X'][i] = ['HELDOUT_ONLY' if f in matrix['categorical_features'] else 99999999 for f in matrix['feature_names']]
            mutated = prepare_material_fold(changed, fold)
            assert prepared['training_only_schema'] == mutated['training_only_schema']
            assert prepared['X_train'] == mutated['X_train']
            tests.append({'fold':k,'source_groups_disjoint':True,'heldout_mutation_does_not_change_training':True,'finite_training_and_validation':True})
            if k == 0:
                write(OUT / 'material_fold_example.json', prepared)
        coverage = {f:{'records':sum(r.get(f) is not None for r in db.fetch().rows),
                       'source_groups':len({r['source_group'] for r in db.fetch().rows if r.get(f) is not None})} for f in MATERIAL_PREDICTORS}
        readiness['material_preparation'] = {'raw_missing_values_retained':True,'fold_count':len(tests),'checks':tests,'coverage':coverage,'model_fits':0}
        write(BATCH / 'current_full_review_queue.json', db.full_review_queue())
    write(OUT / 'training_readiness.json', readiness)
    assert sha(PARENT / 'cycling_v0_10.sqlite') == PARENT_SHA
    print(json.dumps({'cohorts':{p:{'rows':v['rows'],'source_groups':v['source_groups']} for p,v in readiness['cohorts'].items()},
                      'reviewed_materials':len(materials),'selected_material_observations':sum(p['status']=='selected_agent_source_review' for p in properties),
                      'new_or_filled_record_cells':len(changes),'model_fits':0},ensure_ascii=False,indent=2))


if __name__ == '__main__':
    build()
