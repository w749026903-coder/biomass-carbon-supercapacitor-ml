"""Build once / verify read-only / seal a reviewed v0.17 evidence delta.

No ML fitting, downloads, author contact, scientific gate relaxation or old build rerun.
"""
from pathlib import Path
from contextlib import closing
import collections, copy, csv, hashlib, importlib.util, io, json, math, sqlite3, sys, zipfile
ROOT = Path(__file__).resolve().parents[1]; sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
BATCH = ROOT / '持续补正_v017_20261024'
PARENT = ROOT / '循环稳定性数据库_v0.16_补证与口径复核_20261024'
OUT = ROOT / '循环稳定性数据库_v0.17_原图标签补正_20261024'
DB = OUT / 'cycling_v0_17.sqlite'
CMC = 'incoming:ADD_035_T01'
PROFILES = ['reported_3e', 'reported_3e_residue_sensitivity', 'reported_3e_sensitivity']
MAIN = '三电极端点扩充_20261018/corpus/U017/main.pdf'

def read(p): return json.loads(Path(p).read_text('utf8'))
def write(p, v): Path(p).write_text(json.dumps(v, ensure_ascii=False, indent=2) + '\n', 'utf8')
def dump(v): return json.dumps(v, ensure_ascii=False, sort_keys=True)
def sha(p):
    with Path(p).open('rb') as f: return hashlib.file_digest(f, 'sha256').hexdigest()
def module(path, name):
    s = importlib.util.spec_from_file_location(name, path); m = importlib.util.module_from_spec(s)
    sys.modules[name] = m; s.loader.exec_module(m); return m
def evidence(path, locator, reading, kind='reviewed_native_text'):
    return dict(path=path, sha256=sha(ROOT / path), locator=locator, evidence_excerpt=reading,
                evidence_kind=kind, document_version='version_of_record' if path == MAIN else 'derived_review_or_public_metadata')

def choices(rows, reviews):
    # Scientific choices explicitly reviewed against the source, not keyword inference.
    fig = evidence(MAIN, 'PDF p5 Fig4(i), own red CMC curve, author-printed annotation and inset',
                   'CMC: author label96.7%; terminal x15000; own waveform -0.3..0.9V. Caption cycle stability at10A/g.', 'reviewed_author_printed_figure_label')
    fig['derived_image'] = '持续补正_v017_20261024/evidence_images/CMC_Fig4i_author_label.png'
    fig['derived_image_sha256'] = sha(ROOT / fig['derived_image'])
    label = evidence(MAIN, 'PDF p2 introduction; p6 cycling/post-cycle paragraphs; p7 conclusion',
                     'p2 directly reports96.7% after15000 cycles; p6 says over96.7% of original after15000 and separately parenthetical96.7% capacitance retention; p7 over96% after15000 at10A/g.')
    protocol = evidence(MAIN, 'PDF p2 section2.3; p5 3E results and Fig4 caption/inset; p7 conclusion',
                        '3E working carbon, Pt counter, SCE reference,2M H2SO4. Fig4(i) CMC own10A/g cycling; inset -0.3..0.9V. p5 mass loading2mg/cm2. Distinct2E Fig5 not transferred.')
    scope = evidence(MAIN, 'PDF p2 synthesis; p3 removal paragraph; p4 XPS and ICP-MS paragraph',
                     'Expired-honey carbon; KOH and Co catalytic carbonization followed by0.1M HCl/water washing. Final XPS no Co observed; main text ICP-MS residualCo<0.05wt% referring TableS2. Intermediate Co/CoO is not the final tested composite. SI itself not obtained.')
    material = evidence(MAIN, 'PDF p4 Raman; p5 own CMC discussion; p6 initial vs cycled comparison',
                        'Initial CMC ID/IG1.175, total pore volume1.081cm3/g, BET1404.6m2/g. Cycled1296.3m2/g and O8.54at% excluded from predictors.')
    synth = evidence(MAIN, 'PDF p2 section2.1; p3 synthesis discussion',
                     'Microwave200W180C4h then KOH/Co(NO3)2 impregnation and activated carbonization700C underAr, ramp5C/min, acid wash. Hold duration at700C not reported here.')
    changes = []
    def add(key, field, value, ev, reason, scope_name='test'):
        before = rows[key].get(field)
        assert before != value, (key, field, 'no-op')
        changes.append(dict(endpoint_id=key, field_name=field, before=before, after=value,
                            evidence=[dict(e, fields=[field]) for e in ev], material_key=rows[key]['material_key_v11'],
                            scope=scope_name, operation='fill' if before is None else 'correct_with_history', reason=reason))
    why = 'Own author-printed point label and two independent locations within the same article support the rounded reported point; never convert a bound by assumption or count these as independent sources.'
    add(CMC, 'retention_relation', 'eq', [fig, label], why)
    add(CMC, 'baseline_reference', dict(reference='author_initial_or_own_normalized_reference', cycle_index=None,
                                      basis='Own Fig4(i) starts normalized100%; p6 states original value; author-printed96.7% at15000. Exact baseline cycle index remains unknown.'), [fig, label], why)
    add(CMC, 'baseline_evidence_kind_v13', 'author_printed_numeric_label', [fig, label], 'Compatibility evidence descriptor; rounded author label, not pixel-derived approximation.')
    for field, value in [('eligible', 1), ('admission_status', 'approved_for_reported_protocol'),
                         ('review_status', 'approved_for_reported_protocol'), ('scope_status', 'biomass_carbon_catalyst_removed_trace_bound_reported'),
                         ('core_missing_fields', []), ('issues', []), ('open_issues', []), ('remaining_evidence_work', [])]:
        add(CMC, field, value, [fig, label, protocol, scope], 'Current reviewed projection replaces stale working flags; all original values and old holds remain in the immutable parent and field-change chain.')
    add(CMC, 'cycle_count_source_caveat_v17', dict(selected_cycles=15000, selected_basis='own_Fig4i_terminal_plus_results_and_introduction',
        abstract_statement=dict(cycles=10000, relation='gt', retention_pct=96.7), author_correction_found=False,
        interpretation='Abstract lower-bound statement at10000 is retained, not asserted to be a typographical error or an alternate exact endpoint.'), [fig, label], 'Do not erase competing wording or pretend an author correction exists.')
    add(CMC, 'metal_removal_evidence_v17', dict(catalyst='Co/CoO during carbonization', acid_wash=True,
        final_ICP_MS_Co_wt_pct_bound=0.05, relation='lt', numeric_zero=False, SI_table_independently_read=False,
        source='Explicit formal main p4 report; no intentionally retained metal composite established.'), [scope], 'No invented universal residue threshold; own catalyst-removal and final-material evidence supports existing biomass-carbon scope.')
    add(CMC, 'total_pore_volume_cm3_g', 1.081, [material], 'Own initial sample, not post-cycle0.965.', 'material')
    add(CMC, 'Raman_ID_IG', 1.175, [material], 'Own initial CMC Raman ratio, not CHC/MC/HC.', 'material')
    add(CMC, 'mass_loading_mg_cm2', 2.0, [protocol], 'Baseline Fig4 three-electrode protocol;5mg/cm2 is a distinct supplementary high-loading test.')
    for field, value in [('activation_temperature_C', 700), ('heating_rate_C_min', 5), ('carbonization_temperature_C', 700),
                         ('carbonization_heating_rate_C_min', 5), ('microwave_power_W_v14', 200)]:
        add(CMC, field, value, [synth], 'Stage-qualified own material synthesis; KOH activated carbonization is one process, not two independent measurements.', 'material')
    # Audit metadata is separate from selected numeric predictors and admission.
    ds = evidence('持续补正_v017_20261024/DSAC_BET_consistency_audit.json', 'raw report reproduction and all contiguous adsorption intervals',
                  '13 supplied adsorption points;78 intervals including two-point diagnostics;0 pass all four checked criteria. Reported C-63.443 reproduced. No replacement area chosen.', 'raw_data_consistency_diagnostic')
    add('legacy:SRC121_CY01', 'BET_consistency_review_v17', dict(author_area_m2_g=1374.73, author_C=-63.443,
        database_reported_area_retained=1374, adsorption_points=13, contiguous_intervals_checked=78, all_criteria_pass=0,
        independent_remeasurement=False, replacement_area_selected=False, status='known_consistency_problem_not_resolved',
        minimum_supplied_relative_pressure=0.0450331), [ds], 'Author reported BET is retained with known quality problem; no alternative fit chosen to force admission.', 'audit')
    ac = evidence('持续补正_v017_20261024/retrieved/AC700_Crossref.json', 'formal article title/DOI/authors/published-online metadata',
                  'Formal DOI10.1016/j.ultsonch.2026.108104; same four authors and control-study identity; full text still not obtained.', 'bibliographic_identity_only')
    add('incoming:ADD_073_T01', 'formal_version_candidate_v17', dict(doi='10.1016/j.ultsonch.2026.108104',
        online_date='2026-10-09', fulltext_obtained=False, own_AC700_numbers_formally_verified=False,
        same_study_not_new_source=True, canonical_source_group_unchanged=True), [ac], 'Formal metadata association, not full-text substitution or new study/admission.', 'audit')
    review = copy.deepcopy(reviews[CMC])
    review.update(disposition='approved_for_reported_protocol', approved_profiles=PROFILES, open_issues=[], review_version='v0.17',
        reason='直接核到自身Fig4(i)印字96.7%、15000圈和p2/p6点值；协议、初始BET、参比和酸洗去催化剂证据完整。gt旧值与摘要10000圈下限原话均留在历史，不把作者圆整标签说成数学精确测量。',
        resolution=['Own printed label96.7% at15000 confirmed; prior text-only lower-bound gate corrected.',
                    'Own3E10A/g2M H2SO4/SCE and -0.3..0.9V confirmed.',
                    'Initial material and catalyst-removal evidence checked; residualCo reported<0.05wt%, not0.',
                    'Unknown current mass basis and exact baseline cycle index remain unknown under the existing reported-protocol purpose.'],
        caveats=['Same-source abstract over96.7% at10000 retained; no author corrigendum claimed.',
                 'Formal main refers to SI ICP-MS; actual SI not obtained. No claim of zero cobalt or measurement revalidation.',
                 'New inputs have not been trained or independently performance-tested.'],
        evidence=[fig, label, protocol, scope])
    return changes, [review]

def build():
    if DB.exists() or (OUT / 'merge_manifest.json').exists(): raise FileExistsError('Do not rebuild existing v0.17.')
    pointer = read(BATCH / 'parent_pointer.json')
    assert pointer['version_directory'] == PARENT.name and sha(PARENT / pointer['database_file']) == pointer['sha256']
    api = module(PARENT / 'ml_data.py', '_v17_build_parent')
    with api.Database() as db:
        rows = {r['endpoint_id']: r for r in db.fetch('all_review').rows}
        reviews = {r['endpoint_id']: r for r in db.reviewed_pending_batch(True)}
        contract = copy.deepcopy(db.contract)
        members = {p: {r['endpoint_id'] for r in db.fetch(p).rows} for p in contract['profiles']}
    changes, decisions = choices(rows, reviews)
    for p in PROFILES:
        assert CMC not in members[p]; members[p].add(CMC)
    contract.update(version='v0.17', database_file=DB.name, parent_directory=PARENT.name, parent_database_sha256=pointer['sha256'],
                    storage_layout='Immutable v0.16 parent plus explicit current membership and evidence changes.',
                    preparation_only=True, all_records_admitted=False, model_fits=0,
                    field_semantics_v17={'eq': 'Rounded author-printed point value; not infinite measurement precision.',
                       'historical_flags': 'v11/v12 admission fields and review_disposition_v12/v15 remain historical; v17 membership/current holds control.',
                       'current_membership': 'admission_profiles_v17 and compatibility admission_profiles_v13 carry v17 membership.',
                       'Co': 'Own formal main ICP-MS<0.05wt% preserved as bound, never zero; SI itself unavailable.',
                       'DSAC': 'Negative BET C/interval diagnostic metadata only, no chosen substitute or new admission.',
                       'AC700': 'Formal candidate metadata only; no canonical source-group change or new admission.'})
    write(OUT / 'data_contract.json', contract)
    with closing(sqlite3.connect(DB)) as c:
        c.execute('pragma foreign_keys=on')
        c.executescript('''create table record_keys_v17(endpoint_id text primary key);
        create table field_changes_v17(endpoint_id text references record_keys_v17,field_name text,before_json text,after_json text,operation text,scope text,material_key text,evidence_json text,reason text,primary key(endpoint_id,field_name));
        create table material_fields_v17(material_key text,field_name text,value_json text,evidence_json text,primary key(material_key,field_name));
        create table reviews_v17(endpoint_id text primary key references record_keys_v17,review_json text not null);
        create table profile_membership_v17(profile text,endpoint_id text references record_keys_v17,primary key(profile,endpoint_id));
        create table source_segments_v17(segment_id integer primary key,path text,sha256 text,doi text,locator text,text text,content_sha256 text,reading_kind text);''')
        c.executemany('insert into record_keys_v17 values(?)', [(k,) for k in rows])
        c.executemany('insert into field_changes_v17 values(?,?,?,?,?,?,?,?,?)', [(s['endpoint_id'], s['field_name'], dump(s['before']), dump(s['after']), s['operation'], s['scope'], s['material_key'], dump(s['evidence']), s['reason']) for s in changes])
        c.executemany('insert into material_fields_v17 values(?,?,?,?)', [(s['material_key'], s['field_name'], dump(s['after']), dump(s['evidence'])) for s in changes if s['scope'] == 'material'])
        c.executemany('insert into reviews_v17 values(?,?)', [(r['endpoint_id'], dump(r)) for r in decisions])
        c.executemany('insert into profile_membership_v17 values(?,?)', [(p, k) for p, keys in members.items() for k in sorted(keys)])
        import pypdfium2 as pdf
        with pdf.PdfDocument(ROOT / MAIN) as document:
            for page_number in [2, 3, 4, 5, 6, 7]:
                page = document[page_number - 1]; tp = page.get_textpage(); txt = tp.get_text_range(); tp.close(); page.close()
                c.execute('insert into source_segments_v17(path,sha256,doi,locator,text,content_sha256,reading_kind) values(?,?,?,?,?,?,?)',
                          (MAIN, sha(ROOT / MAIN), '10.1039/d6nj00244g', f'PDF p{page_number}', txt, hashlib.sha256(txt.encode()).hexdigest(), 'native_text'))
        txt = 'Fig4(i) CMC red capacitance retention curve; author-printed96.7%; terminal15000 cycles; inset -0.3..0.9V; caption10A/g. This is a printed label, not a digitized value.'
        c.execute('insert into source_segments_v17(path,sha256,doi,locator,text,content_sha256,reading_kind) values(?,?,?,?,?,?,?)',
                  (MAIN, sha(ROOT / MAIN), '10.1039/d6nj00244g', 'Fig4(i) PDF p5', txt, hashlib.sha256(txt.encode()).hexdigest(), 'agent_reviewed_author_printed_image_label'))
        c.commit()
    write(BATCH / 'field_changes.json', changes); write(BATCH / 'reviewed_cases.json', decisions)
    write(BATCH / 'release_plan.json', dict(fixed_goal_records=39, fixed_source_groups=25, scientifically_resolved=1,
        new_admissions=[CMC], model_fits=0, BET_diagnostic_regressions=78, no_new_gate=True,
        protected='Originals, immutable prior database/model versions, unchanged source groups and all old holds remain.'))
    print(dump(dict(changes=len(changes), new_admissions=1)))

def verify():
    from training_input_quality import assess
    from material_feature_inputs_v011 import prepare_material_fold
    checks = []; sealed = (OUT / 'merge_manifest.json').exists()
    def check(name, ok):
        if not ok: raise AssertionError(name)
        checks.append(name)
    def emit(path, value):
        if sealed:
            if read(path) != value: raise AssertionError('Sealed report changed: ' + path.name)
        else: write(path, value)
    protected = {}
    for mp in [PARENT / 'merge_manifest.json', ROOT / '模型v1.0_来源留出训练_20261022/run_manifest.json', ROOT / '模型逐项优化_v1.1_20261022/run_manifest.json']:
        for section in ['outputs', 'protected_files', 'protected_sources']:
            vals = read(mp).get(section, [])
            if isinstance(vals, dict): vals = [dict(path=p, sha256=h) for p, h in vals.items()]
            for item in vals:
                if isinstance(item, dict) and 'path' in item and 'sha256' in item:
                    path = Path(item['path']); path = path if path.is_absolute() else ROOT / path
                    check('protected_' + str(path), sha(path) == item['sha256']); protected[str(path)] = item['sha256']
    originals = {}
    for name in ['protected_sources.json', 'review_evidence_hashes.json']:
        for p, h in read(ROOT / '已有文献表图与41条复核_20261024' / name).items():
            path = Path(p); path = path if path.is_absolute() else ROOT / path
            check('original_' + p, sha(path) == h); originals[p] = h
    contract = read(OUT / 'data_contract.json')
    check('unchanged_search_corpus', sha(ROOT / contract['corpus_search_database']) == contract['corpus_search_database_sha256'])
    check('parent_hash', sha(PARENT / 'cycling_v0_16.sqlite') == contract['parent_database_sha256'])
    with closing(sqlite3.connect(DB.as_uri() + '?mode=ro', uri=True)) as c:
        check('sqlite_integrity', c.execute('pragma integrity_check').fetchone()[0] == 'ok')
        check('foreign_keys', not c.execute('pragma foreign_key_check').fetchall())
    oldapi = module(PARENT / 'ml_data.py', '_v17_check_parent'); api = module(OUT / 'ml_data.py', '_v17_check_current')
    changes = read(BATCH / 'field_changes.json'); lookup = {(s['endpoint_id'], s['field_name']): s for s in changes}
    check('unique_changes', len(lookup) == len(changes))
    readiness = {}; cohorts = {}
    with oldapi.Database() as old, api.Database() as db:
        a = {r['endpoint_id']: r for r in old.fetch('all_review').rows}; b = {r['endpoint_id']: r for r in db.fetch('all_review').rows}
        check('all277_retained', set(a) == set(b) and len(b) == 277)
        for key, row in a.items():
            for field, value in row.items():
                if (key, field) in lookup: check('before_chain_' + key + field, lookup[key, field]['before'] == value)
                elif field == 'admission_profiles_v13':
                    check('explicit_membership_change_' + key, key == CMC or b[key][field] == value)
                elif field.endswith('_status') and (key, field.removesuffix('_status')) in lookup: continue
                else: check('old_value_' + key + field, b[key].get(field) == value)
            for f in ['retention_pct', 'cycle_count', 'source_group', 'material_key_v11', 'current_mass_basis', 'canonical_current_A_g']:
                check('protected_core_' + key + f, b[key].get(f) == row.get(f))
            if key == CMC: check('CMC_old_hold_chain', db.holds(key)['previous_holds'] == old.holds(key))
            else: check('hold_unchanged_' + key, db.holds(key) == old.holds(key))
            check('endpoint_projection_' + key, all(db.by_endpoint(key).get(f) == b[key].get(f) for f in ['retention_relation', 'eligible', 'admission_status', 'admission_profiles_v17']))
        for s in changes:
            key, f = s['endpoint_id'], s['field_name']
            check('after_' + key + f, b[key][f] == s['after'])
            check('selected_evidence_' + key + f, any(e.get('review_version') == 'v0.17' and e.get('currently_selected') == 1 for e in db.evidence(key, f)))
            for e in s['evidence']:
                check('source_hash_' + key + f + e['locator'], f in e['fields'] and sha(ROOT / e['path']) == e['sha256'])
                if e.get('derived_image'): check('derived_' + f, sha(ROOT / e['derived_image']) == e['derived_image_sha256'])
        for p in db.contract['profiles']:
            x, y = old.fetch(p), db.fetch(p)
            oldkeys, newkeys = {r['endpoint_id'] for r in x.rows}, {r['endpoint_id'] for r in y.rows}
            check('members_' + p, newkeys == oldkeys | ({CMC} if p in PROFILES else set()))
            check('no_duplicates_' + p, len(newkeys) == len(y.rows))
            if p not in PROFILES: check('2E_matrix_unchanged_' + p, x.feature_matrix() == y.feature_matrix())
            else:
                for key in oldkeys:
                    u, v = next(r for r in x.rows if r['endpoint_id'] == key), next(r for r in y.rows if r['endpoint_id'] == key)
                    check('old_main_core_' + p + key, all(u[f] == v[f] for f in x.features + ['retention_pct', 'source_weight', 'source_group']))
            sums = collections.defaultdict(float)
            for r in y.rows: sums[r['source_group']] += r['source_weight']
            check('equal_source_weight_' + p, all(abs(v - 1) < 1e-10 for v in sums.values()))
            readiness[p] = assess(y)
            cohorts[p] = dict(records=len(y.rows), source_groups=len(sums))
        check('main43_31', cohorts['reported_3e'] == dict(records=43, source_groups=31))
        for p in PROFILES:
            check('CMC_profile_approval_' + p, db.admission_checks(CMC, p)[0]['status'] == 'approved_for_reported_protocol')
        check('no_CMC_2E_approval', db.admission_checks(CMC, 'reported_2e')[0]['status'] == 'not_approved')
        check('whitelist_unchanged', db.contract['extra_material_feature_whitelist'] == old.contract['extra_material_feature_whitelist'])
        for i, matrix in enumerate([db.material_matrix(), db.method_specific_material_matrix()]):
            for j, fold in enumerate(matrix['source_folds']):
                out = prepare_material_fold(matrix, fold)
                check(f'finite_material_{i}_{j}', all(math.isfinite(v) for n in ['X_train', 'X_validation'] for row in out[n] for v in row))
                changed = copy.deepcopy(matrix)
                for z in fold['test']:
                    changed['y'][z] = -987654
                    for col, f in enumerate(matrix['feature_names']): changed['X'][z][col] = 'HELDOUT_ONLY' if f in matrix['categorical_features'] else 987654
                control = prepare_material_fold(changed, fold)
                check(f'no_material_leak_{i}_{j}', out['X_train'] == control['X_train'] and out['training_only_schema'] == control['training_only_schema'])
        r = b[CMC]
        check('author_point_not_guessed_bound', r['retention_pct'] == 96.7 and r['retention_relation'] == 'eq' and r['cycle_count'] == 15000)
        check('unknown_baseline_index_preserved', r['baseline_reference']['cycle_index'] is None)
        check('trace_bound_not_zero', r['metal_removal_evidence_v17']['relation'] == 'lt' and r['metal_removal_evidence_v17']['final_ICP_MS_Co_wt_pct_bound'] == .05 and not r['metal_removal_evidence_v17']['numeric_zero'])
        check('before_after_not_confused', r['BET_m2_g'] == 1404.6 and r['total_pore_volume_cm3_g'] == 1.081 and r['XPS_O_reported_pct'] == 9.71)
        check('old_gt_in_history', next(s for s in db.field_changes(CMC) if s['field_name'] == 'retention_relation')['before'] == 'gt')
        check('printed_label_search', any(x['reading_kind'] == 'agent_reviewed_author_printed_image_label' for x in db.search_native('printed96.7%', doi='10.1039/d6nj00244g')))
        check('old_search', bool(db.search_native('cycling', limit=2)))
        check('empty_search', db.search_native('') == [] and db.search_native('a', limit=0) == [])
        check('year_filter_excludes2025', CMC not in {r['endpoint_id'] for r in db.fetch(year_max=2025).rows})
        check('year_filter_includes2026', CMC in {r['endpoint_id'] for r in db.fetch(year_min=2026).rows})
        check('CMC_stale_flags_resolved', r['core_missing_fields'] == [] and r['issues'] == [] and r['remaining_evidence_work'] == [])
        for field, value in [('baseline_reference', None), ('retention_relation', 'gt'), ('system', '2E'), ('reported_current_A_g', None)]:
            ds = db.fetch(); ds.rows = copy.deepcopy(ds.rows); target = next(x for x in ds.rows if x['endpoint_id'] == CMC); target[field] = value
            try: ds.feature_matrix()
            except api.DataNotReady: check('reject_' + field, True)
            else: raise AssertionError('Invalid input accepted: ' + field)
        pending = db.reviewed_pending_batch()
        check('38pending24groups', len(pending) == 38 and len({r['source_group'] for r in pending}) == 24)
        check('fixed41_audit_retained', len(db.reviewed_pending_batch(True)) == 41)
        check('CMC_not_in_current_pending', CMC not in {r['endpoint_id'] for r in pending})
        features = db.contract['model_material_features']; oldkeys = {r['endpoint_id'] for r in old.fetch().rows}
        fixed = sum(r.get(f) is not None for r in db.fetch().rows if r['endpoint_id'] in oldkeys for f in features)
        expanded = sum(r.get(f) is not None for r in db.fetch().rows for f in features)
        check('old42_coverage_still320', fixed == 320)
        check('DSAC_area_unchanged', b['legacy:SRC121_CY01']['BET_m2_g'] == 1374)
        check('AC700_not_admitted_from_metadata', not b['incoming:ADD_073_T01']['admission_profiles_v17'])
    for name in ['CMC_Fig4i_provenance.json', 'render_provenance.json']:
        data = read(BATCH / name); entries = data if isinstance(data, list) else [data]
        for e in entries:
            image = e.get('image_path', e.get('image'))
            if image: check('rendered_' + image, sha(ROOT / image) == e['image_sha256'])
    metadata = read(BATCH / 'publisher_metadata_pass.json')
    check('25_source_metadata_pass', len(metadata) == 25)
    for item in metadata:
        if item.get('path'): check('metadata_' + item['path'], sha(ROOT / item['path']) == item['sha256'])
    audit = read(BATCH / 'DSAC_BET_consistency_audit.json')
    check('raw_archive_unchanged', sha(ROOT / audit['archive_path']) == audit['archive_sha256'])
    with zipfile.ZipFile(ROOT / audit['archive_path']) as z:
        check('raw_BET_member_unchanged', hashlib.sha256(z.read(audit['member'])).hexdigest() == audit['member_sha256'])
    bet = module(ROOT / 'tools/review_DSAC_BET_v017.py', '_v17_BET_arithmetic')
    windows = []
    for i in range(len(audit['adsorption_points']) - 1):
        for j in range(i + 2, len(audit['adsorption_points']) + 1):
            windows.append(dict(start_point=i + 1, end_point=j, **bet.fit(audit['adsorption_points'][i:j])))
    check('BET_recomputed78_diagnostics', windows == audit['windows'] and len(windows) == 78)
    check('BET_no_selected_replacement', audit['passing_ranges'] == [] and audit['ML_model_fits'] == 0)
    emit(BATCH / 'remaining_pending_records.json', pending)
    emit(OUT / 'training_readiness.json', readiness)
    emit(BATCH / 'coverage_and_dispositions.json', dict(changes=len(changes), field_fills=sum(s['before'] is None for s in changes),
         field_corrections=sum(s['before'] is not None for s in changes), new_admissions=1, resolved_in_fixed_goal=1,
         pending_records=38, pending_source_groups=24, original_goal_records=39, cohorts=cohorts,
         fixed_old42_optional_nonmissing=fixed, fixed_old42_optional_denominator=756,
         expanded_main_optional_nonmissing=expanded, expanded_main_optional_denominator=43 * len(features),
         model_fits=0, BET_diagnostic_regressions=78, all_scientific_questions_resolved=False))
    emit(OUT / 'verification.json', dict(passed=True, check_count=len(checks), checks=checks,
         protected_payloads=len(protected), protected_original_paths=len(originals), model_fits=0))
    if sealed:
        for item in read(OUT / 'merge_manifest.json')['outputs']:
            assert sha(ROOT / item['path']) == item['sha256'], item['path']
    print(dump(dict(passed=True, checks=len(checks), new_admissions=1, pending=38, sealed_payloads_verified=sealed)))

def seal():
    if (OUT / 'merge_manifest.json').exists(): raise FileExistsError('Already sealed; verify instead.')
    assert read(OUT / 'verification.json')['passed']
    assert read(ROOT / 'data/current_database.json') == read(BATCH / 'parent_pointer.json'), 'Current pointer moved; preserve other work.'
    for p in [BATCH / 'release_report.md', OUT / 'README.md', BATCH / 'source_review.json']: assert p.is_file(), p
    outputs = []
    # The live work queue/README remain mutable for the persistent goal; seal release evidence explicitly.
    names = ['field_changes.json', 'reviewed_cases.json', 'release_plan.json', 'remaining_pending_records.json',
             'coverage_and_dispositions.json', 'source_review.json', 'release_report.md', 'DSAC_BET_consistency_audit.json',
             'publisher_metadata_pass.json', 'CMC_Fig4i_provenance.json', 'sources_receipt.json']
    paths = [BATCH / n for n in names] + list((BATCH / 'evidence_images').glob('CMC*.png'))
    paths += [ROOT / item['path'] for item in read(BATCH / 'publisher_metadata_pass.json') if item.get('path')]
    paths += [ROOT / MAIN, BATCH / 'retrieved/DSAC_author_data.zip', BATCH / 'retrieved/AC700_Crossref.json']
    paths += [p for p in OUT.iterdir() if p.is_file()]
    paths += [Path(__file__), ROOT / 'tools/review_DSAC_BET_v017.py', ROOT / 'tools/collect_correction_metadata_v017.py']
    for p in sorted(set(paths)):
        outputs.append(dict(path=p.relative_to(ROOT).as_posix(), sha256=sha(p), bytes=p.stat().st_size))
    stats = read(BATCH / 'coverage_and_dispositions.json')
    write(OUT / 'merge_manifest.json', dict(schema='original_label_correction_v1', version='v0.17', database_sha256=sha(DB),
          parent_database_sha256=read(BATCH / 'parent_pointer.json')['sha256'], ready_for_merge=True, ready_for_training_inputs=True,
          all_records_admitted=False, all_scientific_questions_resolved=False, new_admissions=1, current_pending=38, model_fits=0,
          cohorts=stats['cohorts'], outputs=outputs))
    write(ROOT / 'data/current_database.json', dict(version_directory=OUT.name, database_file=DB.name, sha256=sha(DB),
          parent_database_file=(PARENT / 'cycling_v0_16.sqlite').relative_to(ROOT).as_posix(), default_profile='reported_3e',
          stage='own_author_printed_label_and_current_membership_review', ready_for_training_inputs=True,
          research_training_authorized=False, all_records_admitted=False))
    print(dump(dict(sealed_outputs=len(outputs), database_sha256=sha(DB))))

if __name__ == '__main__': {'build': build, 'verify': verify, 'seal': seal}[sys.argv[1]]()
