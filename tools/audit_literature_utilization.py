"""Read-only corpus utilization and saved-OOF concentration audit. No fitting."""
from pathlib import Path
import collections
import hashlib
import json
import math
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from data.cycling_db import open_database

CORE = ('cycle_count', 'reported_current_A_g', 'concentration_mol_L',
        'cycle_voltage_lower_V', 'cycle_voltage_upper_V', 'BET_m2_g',
        'electrolyte', 'reference_electrode')
OPTIONAL = ('total_pore_volume_cm3_g', 'N_at_pct', 'O_at_pct',
            'mass_loading_mg_cm2', 'temperature_C')


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def profile(rows):
    return {'records': len(rows), 'source_groups': len({r['source_group'] for r in rows}),
            'configuration': dict(collections.Counter(r.get('system') for r in rows)),
            'nonnull_fields': {f: sum(r.get(f) is not None for r in rows) for f in CORE + OPTIONAL},
            'field_statuses': {f: dict(collections.Counter(str(r.get(f + '_status', 'status_not_in_flat_row'))
                                                         for r in rows if r.get(f) is not None)) for f in OPTIONAL},
            'all_eight_core_nonnull': sum(all(r.get(f) is not None for f in CORE) for r in rows)}


def summarize(predictions):
    by_source = collections.defaultdict(list)
    for r in predictions:
        by_source[r['source_group']].append(r)
    ymean = statistics.fmean(statistics.fmean(r['observed'] for r in g) for g in by_source.values())
    source_stats = []
    for source, group in by_source.items():
        source_stats.append({'source_group': source, 'records': len(group),
                             'source_mae': statistics.fmean(abs(r['predicted'] - r['observed']) for r in group),
                             'source_mse': statistics.fmean((r['predicted'] - r['observed']) ** 2 for r in group),
                             'source_target_ss': statistics.fmean((r['observed'] - ymean) ** 2 for r in group)})
    sse = sum(r['source_mse'] for r in source_stats)
    sst = sum(r['source_target_ss'] for r in source_stats)
    sae = sum(r['source_mae'] for r in source_stats)
    for r in source_stats:
        r.update(sse_share=r['source_mse'] / sse, sae_share=r['source_mae'] / sae,
                 target_ss_share=r['source_target_ss'] / sst)
    return {'mae': sae / len(source_stats), 'rmse': math.sqrt(sse / len(source_stats)),
            'r2': 1 - sse / sst, 'target_weighted_mean': ymean,
            'sources': sorted(source_stats, key=lambda r: -r['sse_share'])}


def audit():
    pointer = read(ROOT / 'data/current_database.json')
    with open_database() as db:
        pool = db.fetch('all_review').rows
        three_review = db.fetch('review_3e_all').rows
        train = db.fetch().rows
        incoming = db.incoming_tests()
        incoming_sources = db.incoming_sources()
        profiles = {p: profile(db.fetch(p).rows) for p in
                    ['reported_3e', 'reported_2e', 'reported_2e_residue', 'reported_2e_approx']}
        counts = {t: db.conn.execute('select count(*) from ' + t).fetchone()[0] for t in
                  ['papers', 'literature_registry', 'document_sources', 'model_endpoints',
                   'native_measurement_claims', 'paper_source_reviews', 'candidate_sources_v07']}
        training_ids = {r['endpoint_id'] for r in train}
        eligible_union = {r['endpoint_id'] for p in profiles for r in db.fetch(p).rows}
        all_core_unadmitted = []
        missing = collections.Counter()
        for r in three_review:
            if r['endpoint_id'] in training_ids:
                continue
            absent = [f for f in CORE if r.get(f) is None]
            missing.update(absent)
            if not absent:
                all_core_unadmitted.append({'endpoint_id': r['endpoint_id'], 'sample_name': r['sample_name'],
                                           'source_group': r['source_group'], 'holds': db.holds(r['endpoint_id']),
                                           'admission_checks': db.admission_checks(r['endpoint_id'], 'reported_3e')})
        inventory = {'unit_warning': 'Catalog identities, archived papers, source files and test endpoints are different units; do not sum overlapping catalog counts.',
                     'tables': counts, 'all_structured_tests': profile(pool),
                     'all_3e_review_tests': profile(three_review), 'training_profiles': profiles,
                     'unique_admitted_endpoint_union_including_nested_sensitivity': len(eligible_union),
                     'incoming': {'documents': len(incoming_sources), 'test_records': len(incoming),
                                  'test_sources': len({r['source_group'] for r in incoming}),
                                  'admitted_to_at_least_one_use': sum(bool(r['eligible']) for r in incoming),
                                  'pending_or_outside': len(db.review_queue()),
                                  'document_categories': dict(collections.Counter(r['category'] for r in incoming_sources))},
                     'three_e_review_not_in_model': len(three_review) - len(train),
                     'unadmitted_3e_missing_counts_overlapping': dict(missing),
                     'unadmitted_3e_with_all_eight_fields_nonnull': all_core_unadmitted,
                     'nonnull_not_scientific_admission': True,
                     'fiber_morphology_not_a_required_or_validated_core_field': True}
        groups = collections.Counter(r['source_group'] for r in train)
        concentration = {'record_group_counts': dict(groups), 'largest_row_share': max(groups.values()) / len(train),
                         'each_source_total_dataset_weight': {g: sum(r['source_weight'] for r in train if r['source_group'] == g) for g in groups},
                         'source_equal_weight_share': 1 / len(groups),
                         'independent_source_count': len(groups),
                         'distinct_source_sample_pairs': len({(r['source_group'], r['sample_name']) for r in train}),
                         'records_missing_canonical_material_id': sum(r.get('material_id') is None for r in train),
                         'label_quantiles': {str(q): float(__import__('numpy').quantile([r['retention_pct'] for r in train], q))
                                             for q in [0, .25, .5, .75, 1]},
                         'below91_sources': sorted({r['source_group'] for r in train if r['retention_pct'] < 91}),
                         'core_material_descriptor_used': ['BET_m2_g'],
                         'unused_optional_numeric_counts': {f: sum(isinstance(r.get(f), (int, float)) for r in train) for f in OPTIONAL}}
        fingerprint = db.fetch().fingerprint()
    predictions = read(ROOT / '初步模型训练_20261021/predictions.json')
    new = read(ROOT / '模型诊断与改进_20261021/predictions.json')
    variants = {v: summarize([r for r in predictions if r['variant'] == v])
                for v in ['mean/full', 'RF/full', 'MLP/full', 'MLP/no_current']}
    variants.update({v: summarize([r for r in new if r['variant'] == v])
                     for v in ['nested_min', 'nested_1se', 'nested_linear']})
    sensitive = 'doi:10.1039/d4ta02115k'
    diagnostics = {}
    for variant in ['mean/full', 'MLP/no_current', 'MLP/full']:
        fixed = [r for r in predictions if r['variant'] == variant]
        diagnostics[variant] = {'all': {k: v for k, v in variants[variant].items() if k != 'sources'},
                                'without_OPB_study_saved_predictions_only': summarize([r for r in fixed if r['source_group'] != sensitive])}
    protected = []
    for run in ['初步模型训练_20261021', '模型诊断与改进_20261021']:
        manifest = ROOT / run / 'run_manifest.json'
        payloads = read(manifest)['outputs']
        assert all(sha(ROOT / r['path']) == r['sha256'] for r in payloads)
        protected.append({'manifest': manifest.relative_to(ROOT).as_posix(), 'sha256': sha(manifest), 'payloads_unchanged': len(payloads)})
    assert len(train) == 31 and len(groups) == 23
    assert all(abs(w - 1) < 1e-10 for w in concentration['each_source_total_dataset_weight'].values())
    return {'as_of': '2026-10-21', 'read_only': True, 'new_estimator_fits': 0,
            'dataset_fingerprint': fingerprint, 'pointer': pointer, 'inventory': inventory,
            'concentration': concentration, 'saved_prediction_error_concentration': variants,
            'diagnostic_subset_only_no_refitting_no_removal_recommendation': diagnostics,
            'protected_previous_runs': protected,
            'caveats': ['Non-null optional fields need individual definition, method and source review before use.',
                        'The audit does not estimate causal feature importance or improvement from new features.',
                        'Recomputed subset metrics diagnose sensitivity only; they are not model scores after deleting a paper.',
                        'An unvalidated fiber keyword is not a morphology classification.']}


if __name__ == '__main__':
    result = audit()
    target = ROOT / '文献利用与外部方法审查_20261021'
    target.mkdir(exist_ok=True)
    path = target / 'local_audit.json'
    if path.exists():
        raise FileExistsError('Preserve completed audit; use a reviewed new output if needed.')
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'dataset_fingerprint': result['dataset_fingerprint'],
                      'pool_records': result['inventory']['all_structured_tests']['records'],
                      'review_3e_records': result['inventory']['all_3e_review_tests']['records'],
                      'with_all_core_but_not_admitted': len(result['inventory']['unadmitted_3e_with_all_eight_fields_nonnull']),
                      'unused_optional_numeric_counts': result['concentration']['unused_optional_numeric_counts'],
                      'old_payloads_unchanged': result['protected_previous_runs']}, ensure_ascii=False))
