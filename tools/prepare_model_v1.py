"""Freeze the new, explicitly authorized v1.0 run; never fit or rewrite a database."""
from pathlib import Path
import datetime
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from data.cycling_db import open_database
from models.v1_0.model import CORE, MATERIAL

RUN = ROOT / '模型v1.0_来源留出训练_20261022'


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def canonical(group):
    return group.lower().removeprefix('doi:')


def prepare():
    if RUN.exists() and any(RUN.iterdir()):
        raise ValueError('Do not overwrite a planned or completed run.')
    RUN.mkdir(exist_ok=True)
    old = json.loads((ROOT / '初步模型训练_20261021/data_snapshot.json').read_text('utf-8'))
    old_sources = {canonical(g) for g in old['matrix']['groups']}
    with open_database() as db:
        ds = db.fetch('reported_3e')
        records = []
        for original in ds.rows:
            row = {f: original.get(f) for f in CORE + MATERIAL}
            # Atomic percentages are distinct from wt%; unspecified percentages stay unused.
            if original.get('XPS_percentage_basis') == 'atomic_explicit':
                for element in ('N', 'O'):
                    value = original.get('XPS_' + element + '_reported_pct')
                    if value is not None:
                        row[element + '_at_pct'] = value
            row.update(endpoint_id=original['endpoint_id'], source_group=canonical(original['source_group']),
                       material_key=original['material_key_v11'], curve_group=original.get('curve_group'),
                       sample_name=original.get('sample_name'), retention_pct=original['retention_pct'],
                       system=original['system'], method=original['method'],
                       current_mass_basis=original.get('current_mass_basis'),
                       XPS_percentage_basis=original.get('XPS_percentage_basis'))
            records.append(row)
        fingerprint = ds.fingerprint()
    dev = [i for i, r in enumerate(records) if r['source_group'] in old_sources]
    held = [i for i, r in enumerate(records) if r['source_group'] not in old_sources]
    assert len(dev) == 35 and len(held) == 7 and len(old_sources) == 23
    assert len({records[i]['source_group'] for i in held}) == 7
    for field in ('source_group', 'material_key', 'curve_group'):
        assert not {records[i][field] for i in dev if records[i][field] is not None} & {records[i][field] for i in held if records[i][field] is not None}
    candidates = []
    for block in ('core', 'material'):
        for current in (False, True):
            for family, alphas in [('ridge', [10., 100.]), ('krr', [1., 10.])]:
                for alpha in alphas:
                    candidates.append({'id': f'{family}_{block}_{"I" if current else "noI"}_{alpha:g}',
                        'kind': family, 'block': block, 'current': current, 'alpha': alpha,
                        'eligible_for_selection': True})
        for leaf in (2, 4):
            candidates.append({'id': f'extra_trees_{block}_noI_leaf{leaf}', 'kind': 'extra_trees',
                'block': block, 'current': False, 'leaf': leaf, 'eligible_for_selection': True})
        candidates.append({'id': f'mlp_{block}_noI_4_alpha10', 'kind': 'mlp', 'block': block,
            'current': False, 'hidden': 4, 'alpha': 10., 'eligible_for_selection': True})
    candidates += [{'id': 'legacy_mlp_noI', 'kind': 'mlp', 'block': 'core', 'current': False,
                    'hidden': 8, 'alpha': 1., 'legacy': True, 'eligible_for_selection': True},
                   {'id': 'source_mean', 'kind': 'mean', 'block': 'core', 'current': False,
                    'eligible_for_selection': False},
                   {'id': 'source_median', 'kind': 'median', 'block': 'core', 'current': False,
                    'eligible_for_selection': False}]
    assert len(candidates) == 25
    sources = sorted(old_sources)
    folds = [{'fold': n + 1, 'train': [i for i in dev if records[i]['source_group'] != group],
              'test': [i for i in dev if records[i]['source_group'] == group], 'held_source': group}
             for n, group in enumerate(sources)]
    stamp = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()
    plan = {'run_id': 'retention-v1.0-v014-20261022', 'model_version': '1.0', 'created_at': stamp,
        'authorization': {'authorized': True, 'user_request': '再尝试进行一次模型训练，不一定要严格遵守上一次的模型排布。可以创建一个新的适合本项目数据与目标的v1.0新模型',
                          'scope': 'Bounded local training, source holdout evaluation, final all-main-data research artifact and project Git sync; no service or giant-model pretraining.'},
        'profile': 'reported_3e', 'database_pointer': json.loads((ROOT / 'data/current_database.json').read_text('utf-8')),
        'dataset_fingerprint': fingerprint, 'rows': 42, 'sources': 30,
        'development_indices': dev, 'reserved_source_test_indices': held,
        'development_rows': 35, 'development_sources': 23, 'reserved_rows': 7, 'reserved_sources': 7,
        'holdout_rule': 'Canonical DOI not present in the original v0.10 23-source model snapshot; determined before any new fit.',
        'holdout_limits': 'Source-disjoint and unused in previous model fits/scores; literature review has seen these labels. Not prospective blinded or fully untouched external validation.',
        'development_folds': folds, 'candidates': candidates,
        'selection': 'Minimum pooled source-equal development LOSO MAE among23 learned candidates; ties within1e-10 resolved by listed order. Selection CV score is optimistic, not a nested test estimate.',
        'reserved_evaluation_slots': ['selected', 'source_mean', 'legacy_mlp_noI', 'ridge_core_noI_100', 'ridge_material_noI_100'],
        'reserved_evaluation_rule': 'Freeze selected.json before accessing held-out y in evaluation. Report all five fixed slots once; do not reselect, add candidates, change labels, or retune after test results.',
        'final_refit': 'Refit the already selected specification on all42 admitted rows/30sources. Save separately from the35-row evaluated artifact. Its training rows are not test rows; no training-score generalization claim.',
        'feature_encoding': {'numeric': 'log1p on named nonnegative core/pore/loading fields; source-equal training-only mean/scale; training-mean fill and explicit optional missing indicators',
            'optional_source_threshold': 5, 'categories': 'training vocabulary plus unknown bucket',
            'atomic_composition': 'N/O_at_pct or explicitly atomic XPS only; bulk wt% remains separate',
            'stage_separation': 'precarbonization/carbonization/activation/hydrothermal/post/pretreatment never conflated',
            'core': CORE, 'material': MATERIAL, 'legacy': 'Original raw7 inputs, row-weighted X scaling, source-weighted target scaling and mean-one fit weights retained exactly.'},
        'weights': 'Every source contributes total1 within each split, including observed-feature scaling. Legacy fit normalizes weights to mean1 to retain its original recipe.',
        'labels_clipped': False, 'seed': 42, 'threads': 1,
        'uncertainty': '5000 paired source-group bootstrap resamples of reserved errors, seed20261022; descriptive conditional intervals only,7sources, not calibrated prediction intervals.',
        'planned_jobs': 581, 'maximum_estimator_fits': 534,
        'quality_gate': 'Exploratory model only; report failure to beat mean/legacy and any delta interval crossing0. No service publication.',
        'method_sources': ['https://scikit-learn.org/1.7/modules/cross_validation.html#cross-validation-iterators-for-grouped-data',
                           'https://scikit-learn.org/1.7/modules/generated/sklearn.kernel_ridge.KernelRidge.html',
                           'https://scikit-learn.org/1.7/modules/generated/sklearn.neural_network.MLPRegressor.html']}
    write(RUN / 'data_snapshot.json', {'records': records, 'dataset_fingerprint': fingerprint})
    plan['snapshot_sha256'] = sha(RUN / 'data_snapshot.json')
    write(RUN / 'training_plan.json', plan)
    protected = {}
    # Protect the current database batch, parent manifests, and prior model outputs without copying them.
    directories = [plan['database_pointer']['version_directory'], '循环稳定性数据库_v0.13_冲突复核_20261022',
                   '初步模型训练_20261021', '模型诊断与改进_20261021']
    for directory in directories:
        for filename in ['merge_manifest.json', 'run_manifest.json']:
            path = ROOT / directory / filename
            if path.exists():
                protected[path.relative_to(ROOT).as_posix()] = sha(path)
    for path in [ROOT / plan['database_pointer']['version_directory'] / plan['database_pointer']['database_file'],
                 ROOT / 'data/current_database.json', ROOT / '全库复检与特征补提取_20261021/full_corpus_search_native.sqlite']:
        protected[path.relative_to(ROOT).as_posix()] = sha(path)
    write(RUN / 'protected_inputs.json', protected)
    write(RUN / 'progress.json', {'status': 'planned', 'completed': 0, 'total': 581, 'percent': 0,
          'actual_estimator_fits': 0, 'events': [], 'metrics': [], 'predictions': [], 'candidates': [],
          'elapsed_seconds': 0, 'active': None, 'updated_at': stamp})
    print(json.dumps({'run': str(RUN), 'development': [35, 23], 'reserved': [7, 7],
                      'candidates': 25, 'planned_jobs': 581, 'plan_sha256': sha(RUN / 'training_plan.json')}))


if __name__ == '__main__':
    prepare()
