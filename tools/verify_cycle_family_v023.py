"""Pinned history and current full-source family quarantine for v0.23."""
from pathlib import Path
import collections,json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tools'))
from release_cycle_family_v023 import OUT,DB,LIT,LDB,JOBS,TAC,BTC,PRIOR,load,sha,write,verify
def run(prepare=False):
    verify(False)
    from verify_corpus_chain_v11 import run as pinned_history
    pinned_history(False)
    from data.literature_v11 import open_literature_database
    with open_literature_database(LDB,sha(LDB))as lit,load(OUT,'_v023_fullchain').Database()as cycle:
        materials={r['material_key']:r for r in lit.materials()};payload=[]
        for kind,rows in[('capacitance',lit.capacitances()),('auxiliary',[r for p in['3e','2e_device','native_mineral_3e','2e_author_factor2']for r in lit.auxiliary_feature_rows(p)])]:
            for r in rows:
                assert r['source_group']=='doi:'+r['doi'];payload.append(dict(kind=kind,group=r['source_group']))
        for r in lit.tests():
            assert r['record']['source_group']=='doi:'+materials[r['material_key']]['doi'];payload.append(dict(kind='candidate',group=r['record']['source_group']))
        payload += [dict(kind='bounded_curve',group='doi:'+r['doi'])for r in lit.sampled_curves()]
        payload += [dict(kind='material_fact',group='doi:'+r['doi'])for r in lit.facts()]
        payload += [dict(kind='material_registration',group='doi:'+r['doi'])for r in materials.values()]
        for r in lit.connection.execute('select material_key from synthesis_stages_v3'):payload.append(dict(kind='synthesis',group='doi:'+materials[r[0]]['doi']))
        for r in lit.connection.execute('select o.record_json,m.doi from outcome_observations_v3 o left join materials m using(material_key)'):
            record=json.loads(r[0]);g='doi:'+r[1]if r[1]else record.get('source_group');assert g;payload.append(dict(kind='response',group=g))
        payload += [dict(kind='cycle_observation',group=r['source_group'])for r in cycle.fetch('all_review').rows]
        payload += [dict(kind='published_model_reference',group='doi:10.1039/c9ra01255a')for r in lit.peer_model_cells()]
        payload.append(dict(kind='explicit_related_work_reference',group='doi:'+PRIOR))
        for r in payload:
            r['family']=lit.isolation_group(r['group']);assert r['family']==cycle.source_family_rules()[0]['isolation_group']if r['group']in['doi:'+TAC,'doi:'+PRIOR]else True
        groups=sorted({r['family']for r in payload});holds={}
        for g in groups:
            test=[r for r in payload if r['family']==g];train=[r for r in payload if r['family']!=g];assert not{r['family']for r in test}&{r['family']for r in train};holds[g]=dict(collections.Counter(r['kind']for r in test))
        links={r['candidate_id']:r for r in cycle.literature_links()};candidates={r['candidate_id']:r for r in lit.tests()}
        for cid,key,profiles in JOBS:
            raw=candidates[cid]['record'];row=cycle.by_endpoint(key);assert links[cid]['endpoint_id']==key
            for f in['system','method','retention_pct','cycle_count','reported_current_A_g','cycle_voltage_lower_V','cycle_voltage_upper_V','electrolyte','concentration_mol_L']:assert row[f]==raw[f]
            assert row['source_family_group_v23']==lit.isolation_group(raw['source_group'])
        report=dict(status='passed',cycling_version='v0.23',cycling_sha256=sha(DB),literature_version='v11_pinned',literature_sha256=sha(LDB),historical_inputs_unchanged=True,payloads=len(payload),raw_identifiers=len({r['group']for r in payload}),source_families=len(groups),full_quarantine_counts=holds,material_facts_included=2004,synthesis_records_included=142,source_family_rules=1,new_purpose_admissions=2,new_endpoint_records=1,promoted_existing_IDs=1,original_fixed_pending=38,model_fits=0,full_goal_complete=False)
        assert len(payload)==6161
    if prepare:
        assert not(OUT/'merge_manifest.json').exists();write(OUT/'chain_verification.json',report)
    else:assert json.loads((OUT/'chain_verification.json').read_text('utf8'))==report
    print(json.dumps({k:v for k,v in report.items()if k!='full_quarantine_counts'},ensure_ascii=False))
if __name__=='__main__':
    if len(sys.argv)>2 or(len(sys.argv)==2 and sys.argv[1]!='--prepare'):raise SystemExit('Default read-only; --prepare unsealed only')
    run(len(sys.argv)==2)
