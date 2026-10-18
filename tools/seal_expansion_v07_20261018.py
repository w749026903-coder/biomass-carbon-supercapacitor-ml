"""Seal reviewed v0.7 outputs and switch the stable pointer; no model fit."""
from pathlib import Path
import json
from build_expansion_v07_20261018 import ROOT,PARENT,OUT,BATCH,dump,sha
from verify_expansion_v07_20261018 import verify

def main():
    manifest=OUT/'merge_manifest.json';pointer=ROOT/'data/current_database.json';backup=ROOT/'data/pointer_history/current_database_v06_20261018.json'
    if manifest.exists() or backup.exists():raise RuntimeError('Version sealed or pointer backup exists; inspect rather than overwrite.')
    old=json.loads(pointer.read_text(encoding='utf-8'))
    if old['version_directory']!=PARENT.name or old['sha256']!=sha(PARENT/'cycling_v0_6.sqlite'):raise RuntimeError('Current parent pointer differs.')
    results=verify();dump(OUT/'最终核验.json',results)
    dump(OUT/'变更日志.json',{'parent_version':'v0.6','version':'v0.7','new_training_3e_records':7,'new_training_source_groups':4,'all_existing_training_snapshots_preserved':True,'new_candidate_identities':13,'new_candidates_automatically_admitted':False,'paper_archive_unchanged':True,'research_training_performed':False,'knowledge':'docs/knowledge/补数据审查经验_20261018.md'})
    outputs=[]
    for folder in [OUT,BATCH]:
        for path in sorted(folder.rglob('*')):
            if path.is_file() and '__pycache__' not in path.parts:outputs.append({'path':path.relative_to(ROOT).as_posix(),'sha256':sha(path),'bytes':path.stat().st_size})
    dump(manifest,{'schema':'reported-protocol-expansion-release-v1','created_date':'2026-10-18','parent_database_sha256':sha(PARENT/'cycling_v0_6.sqlite'),'database_sha256':sha(OUT/'cycling_v0_7.sqlite'),'ready_for_training_inputs':True,'research_training_authorized':False,'research_training_performed':False,'all_candidates_admitted':False,'cohorts':results['cohorts'],'new_candidate_identities':13,'parent_checks':results['parent_check_count'],'new_checks':results['new_check_count'],'outputs':outputs})
    backup.write_bytes(pointer.read_bytes());dump(pointer,{'version_directory':OUT.name,'database_file':'cycling_v0_7.sqlite','sha256':sha(OUT/'cycling_v0_7.sqlite'),'default_profile':'reported_3e','stage':'reviewed_reported_protocol_expansion','ready_for_training_inputs':True,'research_training_authorized':False,'all_records_admitted':False})
    print(json.dumps({'sealed':True,'version':OUT.name,'sha256':sha(OUT/'cycling_v0_7.sqlite'),'output_files':len(outputs)},ensure_ascii=False))

if __name__=='__main__':main()
