"""Build once, verify read-only, seal a source-qualified v0.19 evidence delta.

Correct an omitted own SSA report without silently calling it BET.
Keep all admission decisions and prior scientific payloads intact. No ML fits.
"""
from pathlib import Path
from contextlib import closing
import collections, copy, hashlib, importlib.util, json, sqlite3, sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
PARENT = ROOT / '循环稳定性数据库_v0.18_来源题录与质量核查_20261024'
OUT = ROOT / '循环稳定性数据库_v0.19_摘要与制备漏项补正_20261025'
BATCH = ROOT / '持续补正_v017_20261024/resumed_20261025'
DB = OUT / 'cycling_v0_19.sqlite'
SOURCE = ROOT / '同体系文献补充_第二批_20261017/定向扩搜40至60篇_20261017/sources/OA058/main.xml'
DOI = '10.1039/d4ra08818b'
KEYS = [f'candidate:TE{i:03d}' for i in range(14, 20)]
OWN = 'candidate:TE017'


def read(path):
    return json.loads(Path(path).read_text('utf8'))


def write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', 'utf8')


def dump(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    sys.modules[name] = result
    spec.loader.exec_module(result)
    return result


def source_segments():
    root = ET.parse(SOURCE).getroot()
    paragraphs = root.findall('.//p')
    abstract = ' '.join(''.join(root.find('.//abstract').itertext()).split())
    segments = [dict(locator='XML abstract id=abstract1', text=abstract)]
    for index in [9, 10, 11, 18, 19]:
        text = ' '.join(''.join(paragraphs[index].itertext()).split())
        segments.append(dict(locator=f'XML .//p zero-based index {index}', text=text))
    assert 'AF-MMTC5 has a high specific surface area of 1772' in abstract
    assert '41% microporous content' in abstract
    assert 'ASAP2020' in segments[2]['text']
    assert 'Hg/HgO' in segments[3]['text'] and '6 M KOH' in segments[3]['text']
    all_text = ' '.join(''.join(root.itertext()).split())
    import re
    assert not re.search(r'\bBET\b|Brunauer', all_text, re.I), 'Re-review explicit area method if found.'
    return segments


def build():
    if DB.exists() or (OUT / 'merge_manifest.json').exists():
        raise FileExistsError('Existing v0.19 must not be rebuilt.')
    pointer = read(ROOT / 'data/current_database.json')
    assert pointer['version_directory'] == PARENT.name
    assert sha(PARENT / pointer['database_file']) == pointer['sha256']
    parent_api = module(PARENT / 'ml_data.py', '_v19_build_parent')
    with parent_api.Database() as db:
        rows = {r['endpoint_id']: r for r in db.fetch('all_review').rows}
        reviews = {r['endpoint_id']: r for r in db.reviewed_pending_batch(True)}
        contract = copy.deepcopy(db.contract)
    segments = source_segments()
    source_hash = sha(SOURCE)
    changes, decisions = [], []

    def add(key, field, value, loc, reason):
        before = rows[key].get(field)
        assert before is None, (key, field, before)
        evidence = [dict(path=SOURCE.relative_to(ROOT).as_posix(), sha256=source_hash,
                         locator=loc, fields=[field], document_version='formal_published_XML',
                         evidence_kind='reviewed_own_native_text', evidence_excerpt=reason)]
        changes.append(dict(endpoint_id=key, material_key=rows[key]['material_key_v11'],
                            field_name=field, before=before, after=value,
                            operation='fill_qualified_source', evidence=evidence, reason=reason))

    for key, kcl in zip(KEYS, [0, .5, 1.5, 2.5, 3.5, 4.5]):
        assert rows[key]['source_group'] == 'doi:' + DOI
        assert reviews[key]['approved_profiles'] == []
        stage_reason = ('Own common synthesis section2.2.2: initial N2 carbonization800C2h ramp5C/min, '
                        'then HCl/HF template washing, then C:KOH1:4 activation under N2 at800C2h ramp5C/min. '
                        'Two distinct thermal stages, not electrode drying or BET degassing; all six named samples covered.')
        for field, value in [('carbonization_temperature_C', 800), ('carbonization_duration_h', 2),
                             ('carbonization_heating_rate_C_min', 5), ('activation_temperature_C', 800),
                             ('activation_duration_h', 2), ('heating_rate_C_min', 5)]:
            add(key, field, value, 'section2.2.2; XML .//p zero-based index9', stage_reason)
        add(key, 'synthesis_stages_v19', dict(biomass_carbon_source='chitosan',
            KCl_template_added_g=kcl, initial_thermal_stage='carbonization',
            intermediate_wash=['1M HCl12h', '1M HF12h'], second_thermal_stage='KOH_activation',
            carbon_to_KOH_mass_ratio=[1, 4], final_wash='1M HCl12h then water',
            furnace_atmosphere='N2', drying_temperature_C=110,
            two_distinct_stages=True, proof_of_zero_residual_inorganic=False),
            'section2.2.2; XML .//p zero-based index9',
            'Explicit sample-dose mapping and synthesis provenance; drying110C is not a thermal activation feature. '
            'Acid wash/XRD statements are not proof of chemically zero impurities.')
        review = copy.deepcopy(reviews[key])
        review.update(review_version='v0.19')
        review['resolution'] = review.get('resolution', []) + [
            'Filled6 own common stage-qualified numerical synthesis parameters; all six remain one paper group.']
        if key == OWN:
            review.update(disposition='pending_specific_surface_area_method_binding',
                open_issues=['own_SSA_1772_report_found_BET_analysis_method_not_explicit'],
                reason='摘要已明确AF-MMTC5自身SSA1772m2/g及microporous content41%；此前同组六样品一律称无数值有误。'
                       '全文提供ASAP2020孔结构仪器、氮吸附图，但未明确1772属于BET还是其它面积口径。'
                       '保存原始SSA和方法未知，BET标准字段仍空，未给训练资格。',
                resolution=review['resolution'] + ['Corrected prior claim of no own numeric area:1772 is explicitly reported in the abstract.',
                    'No area-method inference from instrument name, same-scale isotherm or agreement with a fitted number.'])
        else:
            review['reason'] += ' 本轮逐样品更正：AF-MMTC5摘要有自身SSA1772；该数值不属于本样品。本样品自身BET仍待证。'
        decisions.append(review)
    add(OWN, 'reported_specific_surface_area_m2_g_v19', 1772,
        'article abstract; XML abstract id=abstract1',
        'Explicit own AF-MMTC5 SSA1772m2/g. Author-reported number, not curve digitization; area analysis method unspecified.')
    add(OWN, 'surface_area_analysis_method_v19', 'not_explicit_in_reviewed_formal_main_or_SI',
        'abstract; section2.3 and3.2; own Fig3e; supplied3-page SI',
        'ASAP2020 instrument/N2 isotherm do not uniquely name BET; no Brunauer/BET method statement found. '
        'Keep generic SSA outside the canonical BET feature, without borrowing other samples.')
    add(OWN, 'microporous_content_reported_pct_v19', 41,
        'article abstract; XML abstract id=abstract1',
        'Author reports41% microporous content for AF-MMTC5, but area-vs-volume denominator is not explicit.')
    add(OWN, 'microporous_content_percentage_basis_v19', 'area_vs_volume_not_explicit',
        'article abstract and section3.2',
        'No multiplication by1772 or total pore volume; do not manufacture canonical micropore area/volume.')
    assert len(changes) == 46
    contract.update(version='v0.19', database_file=DB.name, parent_directory=PARENT.name,
        parent_database_sha256=pointer['sha256'], model_fits=0,
        storage_layout='Immutable v0.18 plus qualified abstract and synthesis corrections; memberships unchanged.',
        field_semantics_v19=dict(generic_SSA='1772 author report for AF-MMTC5 only; method unknown, never silently BET.',
            microporous_content='41percent reported; area/volume basis unknown; no derived micropore number.',
            synthesis='Two distinct800C2h5C/min stages: carbonization, washed template, then KOH activation.',
            admission='All prior training memberships/target values unchanged; no automatic new scientific approval.'))
    write(OUT / 'data_contract.json', contract)
    write(BATCH / 'release_parent_pointer.json', pointer)
    write(BATCH / 'field_changes_v019.json', changes)
    write(BATCH / 'reviewed_cases_v019.json', decisions)
    with closing(sqlite3.connect(DB)) as connection:
        connection.execute('pragma foreign_keys=on')
        connection.executescript('''
        create table record_keys_v19(endpoint_id text primary key);
        create table field_changes_v19(endpoint_id text references record_keys_v19,field_name text,before_json text,after_json text,operation text,evidence_json text,reason text,primary key(endpoint_id,field_name));
        create table reviews_v19(endpoint_id text primary key references record_keys_v19,review_json text);
        create table material_fields_v19(material_key text,field_name text,value_json text,evidence_json text,primary key(material_key,field_name));
        create table source_segments_v19(segment_id integer primary key,path text,sha256 text,doi text,locator text,text text,content_sha256 text,reading_kind text);''')
        connection.executemany('insert into record_keys_v19 values(?)', [(key,) for key in sorted(rows)])
        connection.executemany('insert into field_changes_v19 values(?,?,?,?,?,?,?)', [
            (c['endpoint_id'], c['field_name'], dump(c['before']), dump(c['after']), c['operation'], dump(c['evidence']), c['reason']) for c in changes])
        connection.executemany('insert into material_fields_v19 values(?,?,?,?)', [
            (c['material_key'], c['field_name'], dump(c['after']), dump(c['evidence'])) for c in changes])
        connection.executemany('insert into reviews_v19 values(?,?)', [(r['endpoint_id'], dump(r)) for r in decisions])
        for s in segments:
            connection.execute('insert into source_segments_v19(path,sha256,doi,locator,text,content_sha256,reading_kind) values(?,?,?,?,?,?,?)',
                (SOURCE.relative_to(ROOT).as_posix(), source_hash, DOI, s['locator'], s['text'],
                 hashlib.sha256(s['text'].encode()).hexdigest(), 'reviewed_native_text'))
        connection.commit()
    print(dump(dict(changes=len(changes), records=6, new_admissions=0)))


def verify():
    from training_input_quality import assess
    checks = []
    sealed = (OUT / 'merge_manifest.json').exists()

    def check(name, value):
        if not value:
            raise AssertionError(name)
        checks.append(name)

    def emit(path, value):
        if sealed:
            if read(path) != value:
                raise AssertionError('Sealed report differs: ' + str(path))
        else:
            write(path, value)

    for item in read(PARENT / 'merge_manifest.json')['outputs']:
        check('sealed_parent_' + item['path'], sha(ROOT / item['path']) == item['sha256'])
    contract = read(OUT / 'data_contract.json')
    check('parent_database', sha(PARENT / 'cycling_v0_18.sqlite') == contract['parent_database_sha256'])
    original_hashes = {}
    for name in ['protected_sources.json', 'review_evidence_hashes.json']:
        for path, digest in read(ROOT / '已有文献表图与41条复核_20261024' / name).items():
            absolute = Path(path) if Path(path).is_absolute() else ROOT / path
            check('original_' + path, sha(absolute) == digest)
            original_hashes[path] = digest
    protected_models = {}
    for name in ['模型v1.0_来源留出训练_20261022', '模型逐项优化_v1.1_20261022']:
        manifest = read(ROOT / name / 'run_manifest.json')
        for section in ['outputs', 'protected_files', 'protected_sources']:
            values = manifest.get(section, [])
            if isinstance(values, dict):
                values = [dict(path=p, sha256=h) for p, h in values.items()]
            for item in values:
                if isinstance(item, dict) and 'path' in item and 'sha256' in item:
                    path = Path(item['path']); path = path if path.is_absolute() else ROOT / path
                    check('model_' + str(path), sha(path) == item['sha256'])
                    protected_models[str(path)] = item['sha256']
    with closing(sqlite3.connect(DB.as_uri() + '?mode=ro', uri=True)) as connection:
        check('sqlite_integrity', connection.execute('pragma integrity_check').fetchone()[0] == 'ok')
        check('foreign_keys', not connection.execute('pragma foreign_key_check').fetchall())
    previous_api = module(PARENT / 'ml_data.py', '_v19_verify_previous')
    current_api = module(OUT / 'ml_data.py', '_v19_verify_current')
    changes = read(BATCH / 'field_changes_v019.json')
    lookup = {(c['endpoint_id'], c['field_name']): c for c in changes}
    check('46_unique_changes', len(changes) == len(lookup) == 46)
    cohorts, readiness = {}, {}
    with previous_api.Database() as old, current_api.Database() as db:
        before = {r['endpoint_id']: r for r in old.fetch('all_review').rows}
        after = {r['endpoint_id']: r for r in db.fetch('all_review').rows}
        check('all277_preserved', set(before) == set(after) and len(after) == 277)
        for key in sorted(before):
            for field, value in sorted(before[key].items()):
                if (key, field) in lookup:
                    check('before_' + key + field, lookup[key, field]['before'] == value)
                elif field.endswith('_status') and (key, field.removesuffix('_status')) in lookup:
                    continue
                else:
                    check('unchanged_' + key + field, after[key].get(field) == value)
            for field in ['retention_pct', 'retention_relation', 'cycle_count', 'source_group', 'source_weight',
                          'material_key_v11', 'BET_m2_g', 'canonical_current_A_g', 'current_mass_basis']:
                check('protected_' + key + field, before[key].get(field) == after[key].get(field))
            if key in KEYS:
                check('previous_hold_' + key, db.holds(key)['previous_holds'] == old.holds(key))
            else:
                check('same_hold_' + key, db.holds(key) == old.holds(key))
        for change in changes:
            key, field = change['endpoint_id'], change['field_name']
            check('fill_' + key + field, change['before'] is None and after[key][field] == change['after'])
            check('selected_evidence_' + key + field, any(e.get('review_version') == 'v0.19' and e.get('currently_selected') == 1 for e in db.evidence(key, field)))
            check('history_' + key + field, any(e['field_name'] == field and e['before'] is None and e['after'] == change['after'] for e in db.field_changes(key, True)))
            check('material_' + key + field, any(e['field_name'] == field and e['value'] == change['after'] for e in db.material_properties(after[key]['material_key_v11'])))
            for evidence in change['evidence']:
                check('source_' + key + field, sha(ROOT / evidence['path']) == evidence['sha256'])
        check('same_profiles_whitelist', contract['profiles'] == old.contract['profiles'] and contract['extra_material_feature_whitelist'] == old.contract['extra_material_feature_whitelist'])
        for profile in sorted(contract['profiles']):
            left, right = old.fetch(profile), db.fetch(profile)
            check('identical_training_inputs_' + profile, left.feature_matrix() == right.feature_matrix())
            check('identical_optional_inputs_' + profile, old.material_matrix(profile) == db.material_matrix(profile))
            check('identical_method_inputs_' + profile, old.method_specific_material_matrix(profile) == db.method_specific_material_matrix(profile))
            sums = collections.defaultdict(float)
            for row in right.rows:
                sums[row['source_group']] += row['source_weight']
            check('source_weights_' + profile, all(abs(value - 1) < 1e-10 for value in sums.values()))
            readiness[profile] = assess(right)
            cohorts[profile] = dict(records=len(right.rows), source_groups=len(sums))
        pending = db.reviewed_pending_batch()
        check('same38_pending', {r['endpoint_id'] for r in pending} == {r['endpoint_id'] for r in old.reviewed_pending_batch()})
        check('38pending24sources', len(pending) == 38 and len({r['source_group'] for r in pending}) == 24)
        check('fixed41_review_history', len(db.reviewed_pending_batch(True)) == 41)
        queue = read(ROOT / '持续补正_v017_20261024/work_queue.json')
        check('fixed39_scope', {r['endpoint_id'] for r in queue} == {r['endpoint_id'] for r in pending} | {'incoming:ADD_035_T01'})
        check('SSA_only_own_sample', after[OWN]['reported_specific_surface_area_m2_g_v19'] == 1772 and all(after[k].get('reported_specific_surface_area_m2_g_v19') is None for k in KEYS if k != OWN))
        check('SSA_not_silently_BET', all(after[k]['BET_m2_g'] is None for k in KEYS) and not after[OWN]['admission_profiles_v17'])
        check('no_pore_basis_invention', after[OWN]['microporous_content_reported_pct_v19'] == 41 and after[OWN].get('micropore_volume_cm3_g') is None and after[OWN].get('micropore_surface_area_m2_g') is None)
        check('current_reason_corrected', db.holds(OWN)['open_issues'] == ['own_SSA_1772_report_found_BET_analysis_method_not_explicit'])
        check('no_false_scientific_completion', not read(ROOT / 'docs/DATA_CORRECTION_GOAL.json').get('full_goal_completed', False))
        check('new_native_search', any(r.get('provider') == 'v19_reviewed_native_source' for r in db.search_native('1772', doi=DOI)))
        check('old_native_search', bool(db.search_native('cycling', limit=2)))
        check('empty_native_search', db.search_native('') == [] and db.search_native('1772', limit=0) == [])
        check('unknown_endpoint', db.by_endpoint('does-not-exist') is None)
        check('filtered_year', len(db.fetch('reported_3e', year_min=2026).rows) == len(old.fetch('reported_3e', year_min=2026).rows))
    for segment in source_segments():
        check('reviewed_segment_' + segment['locator'], bool(segment['text']))
    emit(BATCH / 'remaining_pending_records_v019.json', pending)
    emit(OUT / 'training_readiness.json', readiness)
    emit(OUT / 'release_statistics.json', dict(field_fills=46, affected_records=6, own_reported_SSA_records=1,
        standard_stage_numeric_fills=36, new_admissions=0, current_pending=38, pending_source_groups=24,
        fixed_goal_completed=1, fixed_goal_total=39, cohorts=cohorts, model_fits=0,
        precise_scope='AF-MMTC6 samples; targeted first-page/abstract checks of14 protocol source groups included cover-only or absent-main-text cases; not14 complete abstract/full-text rereads.'))
    report = dict(status='passed', checks=len(checks), check_names=checks,
                  original_files_verified=len(original_hashes), model_files_verified=len(protected_models), model_fits=0)
    emit(OUT / 'verification_report.json', report)
    if sealed:
        for item in read(OUT / 'merge_manifest.json')['outputs']:
            if sha(ROOT / item['path']) != item['sha256']:
                raise AssertionError('Sealed payload changed: ' + item['path'])
    print(dump(dict(status='passed', checks=len(checks), pending=38, new_admissions=0, model_fits=0)))


def seal():
    if (OUT / 'merge_manifest.json').exists():
        raise FileExistsError('Do not reseal existing v0.19.')
    verify()
    paths = [p for directory in [OUT, BATCH] for p in directory.rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    paths += [Path(__file__).resolve()]
    paths = sorted(set(paths))
    manifest = dict(version='v0.19', parent_database_sha256=read(OUT / 'data_contract.json')['parent_database_sha256'],
                    ready_for_training_inputs=True, all_records_admitted=False, fixed_goal_complete=False,
                    new_admissions=0, model_fits=0,
                    outputs=[dict(path=p.relative_to(ROOT).as_posix(), sha256=sha(p), bytes=p.stat().st_size) for p in paths])
    write(OUT / 'merge_manifest.json', manifest)
    write(ROOT / 'data/current_database.json', dict(version_directory=OUT.name, database_file=DB.name, sha256=sha(DB),
        parent_database_file=(PARENT / 'cycling_v0_18.sqlite').relative_to(ROOT).as_posix(), default_profile='reported_3e',
        stage='qualified_abstract_and_stage_corrections', ready_for_training_inputs=True,
        research_training_authorized=False, all_records_admitted=False))
    print(dump(dict(sealed_files=len(paths), database_sha256=sha(DB))))


if __name__ == '__main__':
    if len(sys.argv) != 2 or sys.argv[1] not in ['build', 'verify', 'seal']:
        raise SystemExit('Usage: build (one-use), verify (read-only), seal (one-use).')
    globals()[sys.argv[1]]()
