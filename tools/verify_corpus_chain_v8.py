"""Pinned v8/current-view audit plus historical v0.20 verification against its original v5 input."""
from pathlib import Path
import hashlib,json,sys,types
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tools'))
from extract_onion_composite_v8 import OUT,DB,PARENT,PARENT_SHA,verify as core_verify
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def verify(write_report=False):
    core_verify(False)
    from data.literature_v8 import open_literature_database as api8
    from data.literature_v7 import open_literature_database as api7
    from data.literature_groups import source_grouped_candidates
    from data.literature_v4 import PROFILES
    digest=sha(DB)
    # Prior payloads are checked by immutable manifests, not a mutable global pointer.
    for folder in [ROOT/'文献全量利用复核_20261026/批次06_剩余SI与DES协议',ROOT/'文献全量利用复核_20261025/批次05_碳化系列与多电解液']:
        for item in json.loads((folder/'merge_manifest.json').read_text('utf8'))['outputs']:assert sha(ROOT/item['path'])==item['sha256'],item['path']
    with api7(PARENT,PARENT_SHA) as old:
        raw=old.tests();grouped=source_grouped_candidates(old);saved=json.loads((PARENT.parent/'verification_grouping_addendum.json').read_text('utf8'))
        assert len(raw)==len(grouped)==saved['candidate_rows']==31
        missing=[r['candidate_id'] for r in raw if not r['record'].get('source_group')]
        assert missing==saved['groups_derived_from_canonical_material_FK']==['LP7_PK_stack25_26_C2100']
        assert all(r['record']['source_group'] for r in grouped)
    # This validator's historical 988 checks describe the v0.20 release and v5
    # auxiliary inputs. Pin precisely those inputs; newer source counts are
    # audited separately below, rather than weakening old assertions.
    import data.literature_v4 as old_module
    import verify_new_source_v020 as cycling_verify
    baseline=ROOT/'文献全量利用复核_20261025/批次05_碳化系列与多电解液/literature_material_pool_v5.sqlite'
    baseline_sha='b632d3b74123a644dc7cd72a139640a14355bb5c4420d5b34ebc7300620ea578'
    original_open=old_module.open_literature_database
    try:
        old_module.open_literature_database=lambda:original_open(baseline,baseline_sha)
        cycling_verify.verify()
    finally:old_module.open_literature_database=original_open
    addendum=json.loads((cycling_verify.OUT/'verification_addendum.json').read_text('utf8'))
    assert sha(cycling_verify.OUT/'merge_manifest.json')==addendum['primary_manifest_sha256']
    for item in addendum['outputs']:assert sha(ROOT/item['path'])==item['sha256']
    with api8(DB,digest) as new:
        candidates=new.tests();mats={r['material_key']:r for r in new.materials()};allcaps=new.capacitances();curves=new.sampled_curves();aux=[r for p in PROFILES for r in new.auxiliary_feature_rows(p)];purpose=new.composite_cycle_inputs()
        assert len(candidates)==36 and all(r['record']['source_group']=='doi:'+mats[r['material_key']]['doi'] for r in candidates)
        holds={}
        for doi,expected in [('10.1016/j.heliyon.2024.e32915',(13,28,4,0)),('10.3390/gels10010082',(22,30,1,1)),('10.1016/j.isci.2026.117248',(33,0,2,0))]:
            group='doi:'+doi;caps=[r for r in allcaps if r['source_group']==group];sampled=[r for r in curves if r['doi']==doi];tests=[r for r in candidates if r['record']['source_group']==group];custom=[r for r in purpose if r['source_group']==group]
            assert (len(caps),len(sampled),len(tests),len(custom))==expected
            retained_aux=[r for r in aux if r['source_group']!=group];excluded_aux=[r for r in aux if r['source_group']==group]
            assert not {r['source_group'] for r in retained_aux}&{group}
            holds[doi]=dict(capacitance_reports=len(caps),bounded_curve_samples=len(sampled),cycle_candidates=len(tests),composite_cycle_purpose_inputs=len(custom),auxiliary_inputs=len(excluded_aux),all_same_DOI_must_be_quarantined_together=True)
        assert holds['10.1016/j.isci.2026.117248']['auxiliary_inputs']==29 and len(aux)==119
    assert sha(DB)==digest
    report=dict(status='passed',verified_literature_version='v8_pinned',database_sha256=digest,parent_v7_sha256=PARENT_SHA,prior_v7_31_source_groups_reconciled=True,prior_payloads_preserved=True,historical_v020_988_checks='passed with its original immutable v5 literature inputs',current_v8_36_candidate_groups_reconciled=True,current_holdout_evidence_counts=holds,new_composite_cycle_purpose_rows=1,ordinary_cycling_new_members=0,original_fixed_pending=38,model_fits=0,full_literature_goal_complete=False,dependency_policy='Historical audits pin historical datasets. The current pointer may advance; cardinality alone is not a permanent contract.')
    path=OUT/'chain_verification.json'
    if write_report:
        assert not (OUT/'merge_manifest.json').exists();path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    else:assert json.loads(path.read_text('utf8'))==report
    if (OUT/'merge_manifest.json').exists():
        for item in json.loads((OUT/'merge_manifest.json').read_text('utf8'))['outputs']:assert sha(ROOT/item['path'])==item['sha256']
    print(json.dumps(report,ensure_ascii=False))
if __name__=='__main__':
    if len(sys.argv)>2 or (len(sys.argv)==2 and sys.argv[1]!='--prepare'):raise SystemExit('No args:readonly verification; --prepare:unsealed report generation')
    verify(len(sys.argv)==2)
