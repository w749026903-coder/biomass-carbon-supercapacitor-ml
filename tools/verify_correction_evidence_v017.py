"""Verify the acquired-evidence checkpoint without granting data admission."""
from pathlib import Path
import hashlib,json,sqlite3,zipfile
ROOT=Path(__file__).resolve().parents[1];BATCH=ROOT/'持续补正_v017_20261024'
def read(p):return json.loads(p.read_text('utf8'))
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
    checks=[]
    def check(name,value):
        if not value:raise AssertionError(name)
        checks.append(name)
    pointer=read(ROOT/'data/current_database.json');parent=read(BATCH/'parent_pointer.json')
    check('formal_database_not_promoted_from_work_in_progress',pointer==parent)
    folder=ROOT/pointer['version_directory'];check('current_database_SHA',sha(folder/pointer['database_file'])==pointer['sha256'])
    for item in read(folder/'merge_manifest.json')['outputs']:check('sealed_v016_'+item['path'],sha(ROOT/item['path'])==item['sha256'])
    baseline=read(ROOT/'补证与测量口径复核_v016_20261024/remaining_pending_records.json');queue=read(BATCH/'work_queue.json')
    check('all39_original_endpoint_ids_tracked',len(queue)==39 and {r['endpoint_id'] for r in queue}=={r['endpoint_id'] for r in baseline})
    check('same25_source_groups',{r['source_group'] for r in baseline}=={r['source_group'] for r in queue} and len({r['source_group'] for r in queue})==25)
    check('no_claimed_scientific_closures',all(r['goal_status']=='pending_scientific_resolution' for r in queue))
    discovery=read(BATCH/'availability_discovery.json');check('32_actual_cue_scans',len(discovery['source_inventory'])==32)
    for source in discovery['source_inventory']:check('cue_scan_source_'+source['path'],sha(ROOT/source['path'])==source['sha256'])
    d=read(BATCH/'DSAC_download_receipt.json');zip_path=ROOT/d['path']
    check('author_zip_platform_and_local_SHA',sha(zip_path)==d['sha256']==d['publisher_declared_sha256']=='a3003f413d6103e658df9af9884e1d95a885730d06ffdab5440867f979d8c9d8')
    check('author_zip_declared_size',zip_path.stat().st_size==d['bytes']==41277608)
    summary=read(BATCH/'DSAC_raw_cycle_summary.json');phases=read(BATCH/'DSAC_raw_phase_summary.json')
    check('raw_720587_rows',summary['rows']==int(summary['member_header'][-1])==720587 and summary['bad_lines']==0)
    check('separate_cycle_and_phase_ordinals',summary['raw_column_ranges']['11']==[1,2256] and summary['raw_column_ranges']['13']==[1,2] and summary['phases']==len(phases)==4511)
    check('observed_potential_range',-.801<summary['raw_column_ranges']['1'][0]<-.799 and 0<summary['raw_column_ranges']['1'][1]<.01)
    check('cycle2000_not_last2256',len(summary['cycle2000_negative'])==1 and summary['cycle2000_negative'][0]['cycle_ordinal']==2000)
    check('no_claimed_author_retention_from_duration_diagnostic','not an author point label' in summary['semantics']['duration_ratio'])
    with zipfile.ZipFile(zip_path) as z:
        check('zip_inventory_complete',[r['name'] for r in read(BATCH/'DSAC_zip_inventory.json')]==z.namelist())
        for member,key in [(summary['flow_member'],'flow_sha256'),(summary['member'],'member_sha256')]:
            with z.open(member) as f:h=hashlib.file_digest(f,'sha256').hexdigest()
            check('parsed_member_'+member,h==summary[key])
        for r in read(BATCH/'render_provenance.json'):
            check('render_member_'+r['member'],hashlib.sha256(z.read(r['member'])).hexdigest()==r['member_sha256'])
            check('render_image_'+r['image'],sha(ROOT/r['image'])==r['image_sha256'])
    for receipt_name in ['DSAC_landing_receipt.json','DSAC_file_list_receipt.json']:
        r=read(BATCH/receipt_name);check('acquisition_'+receipt_name,sha(ROOT/r['path'])==r['sha256'])
    for r in read(BATCH/'AC700_formal_acquisition.json'):
        if r.get('path'):check('AC700_acquisition_'+r['name'],sha(ROOT/r['path'])==r['sha256'])
    for r in read(BATCH/'AC700_open_locations.json'):
        if r.get('path'):check('AC700_metadata_'+r['name'],sha(ROOT/r['path'])==r['sha256'])
    import xml.etree.ElementTree as E
    xml=E.fromstring((BATCH/'retrieved/AC700_formal_API.xml').read_bytes())
    check('metadata_response_not_misreported_fulltext',not any(e.tag.rsplit('}',1)[-1] in ['originalText','body'] for e in xml.iter()))
    core=read(BATCH/'retrieved/AC700_EuropePMC.json')['resultList']['result'][0]
    check('formal_AC700_DOI_year_identified',core['doi']=='10.1016/j.ultsonch.2026.108104' and core['pubYear']=='2026' and core['firstPublicationDate']=='2026-10-09')
    goal=read(ROOT/'docs/DATA_CORRECTION_GOAL.json');check('goal_still_active_in_record',goal['app_goal_status_last_confirmed']=='active' and goal['scientifically_resolved_in_goal']==0)
    storage=read(BATCH/'storage_review.json');check('only_verified_browser_cache_removed',storage['deleted_bytes']==5590 and not (BATCH/'retrieved/AC700_PubMed.html').exists())
    check('no_large_curve_copy',not any(p.suffix.lower()=='.crv' for p in BATCH.rglob('*')))
    result=dict(passed=True,checks=len(checks),check_names=checks,scope='Evidence-acquisition and derivation checkpoint, not scientific admission',current_database='v0.16',current_pending=39,new_admissions=0,model_fits=0,goal_completed=False)
    p=BATCH/'acquisition_verification.json'
    if (BATCH/'acquisition_manifest.json').exists():
        assert read(p)==result
        for r in read(BATCH/'acquisition_manifest.json')['outputs']:assert sha(ROOT/r['path'])==r['sha256'],r['path']
    else:p.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n','utf8')
    print(json.dumps({k:result[k] for k in ['passed','checks','current_pending','new_admissions','goal_completed']},ensure_ascii=False))
if __name__=='__main__':main()
