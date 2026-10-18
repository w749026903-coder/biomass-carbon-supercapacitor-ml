"""Seal the new version, preserve the old pointer and switch the local entry."""
from pathlib import Path
import hashlib,json
from prepare_training_inputs_v06 import ROOT,VERSION,module,dump
from verify_training_ready_v06_20261018 import verify,sha

def main():
    manifest=VERSION/'merge_manifest.json'
    if manifest.exists():raise RuntimeError('Version already sealed; do not overwrite.')
    results=verify();dump(VERSION/'最终核验.json',results)
    with module().Database() as db:
        admissions=[dict(r) for r in db.conn.execute('select * from reported_profile_admissions_v06 order by endpoint_id,profile')]
        for row in admissions:row['evidence']=json.loads(row.pop('evidence_json'))
        dump(VERSION/'逐记录用途状态.json',admissions)
        reviews=[dict(r) for r in db.conn.execute('select * from reported_record_reviews_v06 order by endpoint_id')]
        for row in reviews:row['review']=json.loads(row.pop('review_json'))
        dump(VERSION/'本轮主证据与未决.json',reviews)
    dump(VERSION/'变更日志.json',{
        'parent_version':'v0.5','new_version':'v0.6','parent_sha256':sha(ROOT/'循环稳定性数据库_v0.5_逐条准入审查_20261018/cycling_v0_5.sqlite'),
        'decisions':['Restore reported-current empirical use; preserve canonical-current use separately.','Retain fourth-round effective 8/10/11 rows and add own-source reviewed endpoints.','Separate 3E with reference identity and 2E without reference feature.','Correct CA-AA 3E102 to101.35 using configuration-specific prose and Fig7a; keep original102 observation.','Keep true protocol/matching gaps pending and ambiguous optional pore values masked.'],
        'source_protection':'No original paper/SI or sealed database overwritten. Observation/selection histories append-only.',
        'training_performed':False})
    outputs=[]
    for path in sorted(VERSION.rglob('*')):
        if not path.is_file() or '__pycache__' in path.parts:continue
        outputs.append({'path':path.relative_to(ROOT).as_posix(),'sha256':sha(path),'bytes':path.stat().st_size})
    dump(manifest,{'schema':'reported-protocol-training-input-release-v1','database_sha256':sha(VERSION/'cycling_v0_6.sqlite'),'parent_database_sha256':results['checks'][0]['passed'] and json.loads((VERSION/'data_contract.json').read_text(encoding='utf-8'))['parent_database_sha256'],'ready_for_training_inputs':True,'research_training_authorized':False,'research_training_performed':False,'all_records_admitted':False,'cohorts':results['cohorts'],'verification_count':results['check_count'],'protected_files':results['protected_file_count'],'outputs':outputs})
    pointer=ROOT/'data/current_database.json';previous=ROOT/'data/pointer_history/current_database_v05_20261018.json'
    if previous.exists():raise RuntimeError('Previous pointer backup already exists; inspect before switching.')
    old=json.loads(pointer.read_text(encoding='utf-8'))
    if old['version_directory']!='循环稳定性数据库_v0.5_逐条准入审查_20261018':raise RuntimeError('Unexpected current pointer; do not replace it.')
    previous.write_bytes(pointer.read_bytes())
    dump(pointer,{'version_directory':VERSION.name,'database_file':'cycling_v0_6.sqlite','sha256':sha(VERSION/'cycling_v0_6.sqlite'),'default_profile':'reported_3e','stage':'reviewed_reported_protocol_training_inputs','ready_for_training_inputs':True,'research_training_authorized':False,'all_records_admitted':False})
    print(json.dumps({'sealed':True,'database_sha256':sha(VERSION/'cycling_v0_6.sqlite'),'version':VERSION.name},ensure_ascii=False))

if __name__=='__main__':main()
