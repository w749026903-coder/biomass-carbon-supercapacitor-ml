"""Read-only verification of the v0.10 chain, field lineage and grouped inputs."""
import collections
import copy
import csv
import json
import sqlite3

from build_evidence_v010 import ROOT, BATCH, OUT, PARENT, PARENT_SHA, api, read, sha, write
from training_input_quality import assess, prepare_source_fold


def verify():
    checks = []

    def check(name, ok):
        if not ok:
            raise AssertionError(name)
        checks.append(name)

    import verify_incoming_v08_20261020 as prior
    prior_report = prior.verify(write=False)
    check('v08_and_older_audit', prior_report['all_technical_checks_passed'])
    check('v09_parent_hash', sha(PARENT / 'cycling_v0_9.sqlite') == PARENT_SHA)
    for x in read(PARENT / 'merge_manifest.json')['outputs']:
        check('v09_payload:' + x['path'], sha(ROOT / x['path']) == x['sha256'])
    protected = read(BATCH / 'protected_inputs.json')['files']
    for x in protected:
        check('protected:' + x['path'], sha(ROOT / x['path']) == x['sha256'])
    cases = read(BATCH / 'curation_delta.json')
    changed = {c['endpoint_id'] for c in cases}
    expected = {'reported_3e': (31, 23), 'reported_2e': (26, 21),
                'reported_2e_residue': (28, 22), 'reported_2e_approx': (30, 24)}
    report = {}
    with api().Database() as db, api(PARENT).Database() as parent, sqlite3.connect(
            (OUT / 'cycling_v0_10.sqlite').as_uri() + '?mode=ro', uri=True) as c:
        check('integrity_check', c.execute('pragma integrity_check').fetchone()[0] == 'ok')
        check('foreign_key_check', not c.execute('pragma foreign_key_check').fetchall())
        old = {r['endpoint_id']: r for r in parent.incoming_tests()}
        current = {r['endpoint_id']: r for r in db.incoming_tests()}
        check('incoming_grain_preserved', set(current) == set(old) and len(current) == 82)
        for key in set(old) - changed:
            check('unchanged_record:' + key, current[key] == old[key])
        for case in cases:
            key = case['endpoint_id']
            check('before_values:' + key, case['before'] == old[key])
            check('after_values:' + key, case['after'] == current[key])
            sql_case = json.loads(c.execute('select decision_json from evidence_decisions_v10 where endpoint_id=?', (key,)).fetchone()[0])
            check('sqlite_delta:' + key, sql_case == case)
            check('original_holds:' + key, db.holds(key)['previous_holds'] == parent.holds(key))
            check('mass_unknown_kept:' + key, current[key]['canonical_current_A_g'] is None
                  and current[key]['current_mass_basis'] is None and not current[key]['physical_current_harmonized'])
            for e in case['evidence']:
                check('own_primary_evidence:' + key + ':' + e['locator'],
                      e['document_id'] == current[key]['document_id'] and sha(ROOT / e['path']) == e['sha256'])
            for f in ['cycle_count', 'retention_pct', 'retention_relation', 'source_group', 'reported_current_A_g']:
                check('label_group_current_preserved:' + key + ':' + f, current[key][f] == old[key][f])
        check('one_new_admission', sum(bool(x['profiles']) for x in cases) == 1)
        check('pending_56', len(db.review_queue()) == 56 and sum(bool(r['eligible']) for r in current.values()) == 26)
        check('queue_matches_api', db.review_queue() == read(BATCH / '当前待补证据队列.json'))
        check('no_BET_borrowing', current['incoming:ADD_007_T01']['BET_m2_g'] == 1260
              and current['incoming:ADD_007_T02'].get('BET_m2_g') is None)
        check('no_3E_mass_transfer', not current['incoming:ADD_027_T02']['pairing_review']['transferred_to_device']
              and not current['incoming:ADD_068_T01']['pairing_review']['transferred_to_cycling_device'])
        check('old_LYS_SI_preserved', any(e.get('kind') == 'publisher_SI_DOCX' and 'FigS7' in e.get('locator', '')
              for e in db.evidence('incoming:ADD_026_T02', 'cycle_voltage_upper_V') if e.get('selected')))
        check('old_year_correction_preserved', next(r for r in db.incoming_sources() if r['document_id'] == 'ADD_052')['year'] == 2025)
        sets = {}
        for profile, shape in expected.items():
            ds = db.fetch(profile)
            quality = assess(ds)
            report[profile] = {**quality, 'fingerprint': ds.fingerprint()}
            check('shape:' + profile, (len(ds.rows), len({r['source_group'] for r in ds.rows})) == shape)
            snapshot = read(OUT / (profile + '_inputs.json'))
            check('matrix_JSON:' + profile, snapshot['matrix'] == ds.feature_matrix() and snapshot['fingerprint'] == ds.fingerprint())
            cached = [json.loads(x[0]) for x in c.execute('select row_json from training_rows_v10 where profile=? order by source_group,endpoint_id', (profile,))]
            check('SQL_rows:' + profile, cached == ds.rows)
            fold_cache = [json.loads(x[0]) for x in c.execute('select split_json from training_folds_v10 where profile=? order by fold_index', (profile,))]
            check('SQL_folds:' + profile, fold_cache == snapshot['source_folds'])
            with (OUT / (profile + '_inputs.csv')).open(encoding='utf-8-sig', newline='') as f:
                csvrows = list(csv.DictReader(f))
            check('CSV_labels:' + profile, len(csvrows) == len(ds.rows) and all(a['endpoint_id'] == b['endpoint_id']
                  and float(a['retention_pct']) == b['retention_pct'] for a, b in zip(csvrows, ds.rows)))
            oldrows = {r['endpoint_id']: r for r in parent.fetch(profile).rows}
            nowrows = {r['endpoint_id']: r for r in ds.rows}
            check('inherited_training_rows:' + profile, all(nowrows[k] == v for k, v in oldrows.items()))
            sets[profile] = set(nowrows)
            check('only_expected_new_row:' + profile, set(nowrows) - set(oldrows) ==
                  (set() if profile == 'reported_3e' else {'incoming:ADD_007_T01'}))
            keys = [(r['source_group'], r['system'], str(r['sample_name']).lower(), r['cycle_count'],
                     r['reported_current_A_g'], r['electrolyte'], r['concentration_mol_L'],
                     r['cycle_voltage_lower_V'], r['cycle_voltage_upper_V'], r.get('reference_electrode')) for r in ds.rows]
            check('test_deduplication:' + profile, len(keys) == len(set(keys)))
            for n, outer in enumerate(read(OUT / (profile + '_nested_fold_plan.json'))):
                check('outer_plan:' + profile + ':' + str(n), {k: v for k, v in outer.items() if k != 'inner_folds'} == snapshot['source_folds'][n])
                for k, split in enumerate(outer['inner_folds']):
                    encoded = prepare_source_fold(ds, split)
                    check('nested_fold:' + profile + ':' + str(n) + ':' + str(k),
                          set(split['train']) | set(split['test']) == set(outer['train'])
                          and encoded['outer_holdout_indices'] == outer['test'] and encoded['estimators_fitted'] == 0)
            for field, value in [('metric_kind', 'coulombic_efficiency'), ('method', 'CV'), ('BET_m2_g', float('nan')), ('reported_current_A_g', None)]:
                bad = copy.deepcopy(ds)
                bad.rows[0][field] = value
                try:
                    bad.feature_matrix()
                except ValueError:
                    checks.append('invalid_input_rejected:' + profile + ':' + field)
                else:
                    raise AssertionError('Invalid input accepted')
        check('nested_sensitivity_sets', sets['reported_2e'] < sets['reported_2e_residue'] < sets['reported_2e_approx'])
        check('pending_not_admitted', all(r['endpoint_id'] not in set.union(*sets.values()) for r in db.review_queue()))
        check('strict_views_unchanged', not db.fetch('strict_3e').rows and not db.fetch('strict_2e').rows)
        check('3E_fingerprint_unchanged', db.fetch().fingerprint() == parent.fetch().fingerprint())
        check('current_fields_defensive_copy', db.incoming_tests('ADD_007')[0]['fields']['BET_m2_g'] == 1260)
        probe = db.incoming_tests('ADD_007'); probe[0]['fields']['BET_m2_g'] = -1
        check('mutation_does_not_persist', db.incoming_tests('ADD_007')[0]['fields']['BET_m2_g'] == 1260)
        check('no_research_fit_authorization', db.contract['research_training_authorized'] is False)
        try:
            db.delta_v10.execute("delete from evidence_decisions_v10")
        except sqlite3.OperationalError:
            checks.append('read_only_write_rejected')
        else:
            raise AssertionError('Overlay allowed writes')
    for img in read(BATCH / 'evidence_image_manifest.json'):
        check('render_lineage:' + img['path'], sha(ROOT / img['path']) == img['sha256']
              and sha(ROOT / img['source_path']) == img['source_sha256'])
    return {'all_technical_checks_passed': True, 'check_count': len(checks),
            'protected_files': len(protected), 'v09_payloads_verified': 40,
            'v08_checks': prior_report['check_count'], 'older_checks': prior_report['inherited_v07_check_counts'],
            'fold_quality_checks': sum(len(q['quality_checks']) for q in report.values()),
            'incoming_observations': 82, 'incoming_admitted_any_reported_purpose': 26, 'pending_or_outside': 56,
            'new_approved_records': 1, 'cohorts': report, 'research_model_fits': 0,
            'all_literature_admitted': False, 'formal_training_authorized': False, 'checks': checks}


if __name__ == '__main__':
    result = verify()
    if (OUT / 'merge_manifest.json').exists():
        print('Sealed release checked read-only; existing reports retained.')
    else:
        write(OUT / '最终核验.json', result)
    print(json.dumps({k: v for k, v in result.items() if k not in ['checks', 'cohorts']}, ensure_ascii=False, indent=2))
