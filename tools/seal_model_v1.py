"""Seal verified task outputs and remove only this task's byte-identical extra export."""
from pathlib import Path
import hashlib
import json
import subprocess

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / '模型v1.0_来源留出训练_20261022'


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def seal():
    verification = json.loads((RUN/'verification.json').read_text('utf-8'))
    visual = json.loads((RUN/'dashboard_visual_verification.json').read_text('utf-8'))
    if not verification['passed'] or not visual['passed']:
        raise ValueError('Both scientific and rendered verification must pass.')
    duplicate = RUN/'dashboard/.data-app-offline/exports/模型v1.0训练结果.html'
    delivered = RUN/'模型v1.0训练结果.html'
    cleanup_path = RUN/'workspace_cleanup.json'
    if duplicate.exists():
        assert sha(duplicate)==sha(delivered)
        size=duplicate.stat().st_size
        duplicate.unlink()
        cleanup={'deleted_path':duplicate.relative_to(ROOT).as_posix(), 'bytes_released':size,
            'preserved_path':delivered.relative_to(ROOT).as_posix(),'sha256':sha(delivered),
            'basis':'Only this run-created byte-identical ignored export; delivered HTML and verified split bundle retained.',
            'raw_or_historical_files_deleted':0}
        cleanup_path.write_text(json.dumps(cleanup,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    paths=['models/v1_0/__init__.py','models/v1_0/model.py']
    paths += [str(p.relative_to(ROOT).as_posix()) for p in (ROOT/'tools').glob('*model_v1*') if p.is_file()]
    for file in RUN.rglob('*'):
        if not file.is_file() or file.name=='run_manifest.json':
            continue
        rel=file.relative_to(ROOT).as_posix()
        ignored=subprocess.run(['git','-c','safe.directory='+ROOT.as_posix(),'check-ignore','--quiet',rel],cwd=ROOT,capture_output=True)
        if ignored.returncode==1:
            paths.append(rel)
        elif ignored.returncode!=0:
            raise RuntimeError('Git ignore classification failed.')
    outputs=[{'path':p,'bytes':(ROOT/p).stat().st_size,'sha256':sha(ROOT/p)} for p in sorted(set(paths))]
    manifest={'run_id':'retention-v1.0-v014-20261022','model_version':'1.0','complete':True,'local_verified':True,
        'scientific_reliability_approved':False,'performance_gate_passed':False,'actual_estimator_fits':534,'evaluation_tasks':581,
        'development_rows':35,'development_sources':23,'reserved_rows':7,'reserved_sources':7,
        'final_research_fit_rows':42,'final_research_fit_sources':30,
        'verification_checks':verification['check_count'],'protected_old_payloads':verification['protected_sealed_payloads'],
        'protected_original_files':verification['original_source_files_verified'],
        'no_extra_fits_after_test':True,'calibrated_prediction_intervals':False,
        'model_weight_distribution':'Only the user-authorized project Git repository, after sync; no public service.',
        'outputs':outputs}
    (RUN/'run_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'sealed_files':len(outputs),'bytes':sum(x['bytes'] for x in outputs),
        'released_duplicate_bytes':json.loads(cleanup_path.read_text('utf-8'))['bytes_released']},ensure_ascii=False))


if __name__=='__main__':
    seal()
