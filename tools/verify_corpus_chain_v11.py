"""Pinned history plus current-source/family quarantine; no fitting."""
from pathlib import Path
import collections,json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tools'))
from extract_biomass_series_v11 import OUT,DB,PSHA,sha,write,verify,TAC,PRIOR,PEA,WH,BTC
def run(prepare=False):
    verify(False)
    from verify_corpus_chain_v10 import run as pinned_history
    pinned_history(False)
    from data.literature_v11 import open_literature_database
    from release_cycle_admissions_v022 import load,OUT as PINNED_CYCLE
    with open_literature_database(DB,sha(DB))as lit,load(PINNED_CYCLE,'_cycling_v022_pinned_v11').Database()as cycle:
        tests=lit.tests();mats={r['material_key']:r for r in lit.materials()};caps=lit.capacitances();curves=lit.sampled_curves();aux=[r for p in['3e','2e_device','native_mineral_3e','2e_author_factor2']for r in lit.auxiliary_feature_rows(p)]
        assert len(tests)==61 and len(aux)==162 and len(curves)==128
        payload=[]
        for kind,rs in[('capacitance',caps),('auxiliary',aux)]:
            for r in rs:
                assert r['source_group']=='doi:'+r['doi'];payload.append(dict(kind=kind,group=r['source_group']))
        for r in tests:
            assert r['record']['source_group']=='doi:'+mats[r['material_key']]['doi'];payload.append(dict(kind='candidate',group=r['record']['source_group']))
        payload += [dict(kind='bounded_curve',group='doi:'+r['doi'])for r in curves]
        for r in lit.connection.execute('select o.record_json,m.doi from outcome_observations_v3 o left join materials m using(material_key)'):
            raw=json.loads(r[0]);g='doi:'+r[1]if r[1]else raw.get('source_group');assert g;payload.append(dict(kind='response',group=g))
        payload += [dict(kind='cycle_observation',group=r['source_group'])for r in cycle.fetch('all_review').rows]
        payload += [dict(kind='published_model_reference',group='doi:10.1039/c9ra01255a')for r in lit.peer_model_cells()]
        payload += [dict(kind='related_prior_work_reference',group='doi:'+PRIOR)]
        for r in payload:r['family']=lit.isolation_group(r['group'])
        families=sorted({r['family']for r in payload});holds={}
        for f in families:
            train=[r for r in payload if r['family']!=f];test=[r for r in payload if r['family']==f]
            assert not {r['family']for r in train}&{r['family']for r in test}
            holds[f]=dict(collections.Counter(r['kind']for r in test))
        assert lit.isolation_group(TAC)==lit.isolation_group(PRIOR)
        f=lit.isolation_group(TAC);held=[r for r in payload if r['family']==f]
        assert {'doi:'+TAC,'doi:'+PRIOR}<={r['group']for r in held}
        inputs={}
        for profile in['reported_3e','reported_2e','reported_3e_all_years','reported_2e_all_years']:
            ds=cycle.fetch(profile);matrix=ds.feature_matrix();groups=[lit.isolation_group(g)for g in matrix['groups']]
            assert len(set(groups))==len(set(matrix['groups'])) # No new family collision in current frozen cohort.
            inputs[profile]=dict(rows=len(ds.rows),original_groups=len(set(matrix['groups'])),family_groups=len(set(groups)),new_fits=0)
        assert len(cycle.reviewed_pending_batch())==38
        report=dict(status='passed',literature_version='v11',database_sha256=sha(DB),parent_literature_sha256=PSHA,current_cycling_version='v0.22_unchanged',candidate_rows=61,auxiliary_rows=162,bounded_curve_samples=128,source_family_rules=1,raw_identifier_groups=len({r['group']for r in payload}),normalized_families=len(families),audited_payloads=len(payload),holdout_counts=holds,cycling_preflight=inputs,original_fixed_pending=38,new_formal_cycle_admissions=0,pending_next_cycle_reviews=['Tondolo_new2E','Tea_existing2021_endpoint_all_years3E_only'],model_fits=0,full_goal_complete=False)
    if prepare:
        assert not(OUT/'merge_manifest.json').exists();write(OUT/'chain_verification.json',report)
    else:assert json.loads((OUT/'chain_verification.json').read_text('utf8'))==report
    print(json.dumps({k:v for k,v in report.items()if k!='holdout_counts'},ensure_ascii=False))
if __name__=='__main__':
    if len(sys.argv)>2 or(len(sys.argv)==2 and sys.argv[1]!='--prepare'):raise SystemExit('Default read-only; --prepare unsealed only')
    run(len(sys.argv)==2)
