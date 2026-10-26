"""Read-only current v10/v0.22 audit; historical audits retain their pinned inputs."""
from pathlib import Path
import json,sys,collections
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tools'))
from extract_four_sources_v10 import OUT,DB,sha,write,verify as literature_verify,COT,QSC,CUC,ANN
from release_cycle_admissions_v022 import OUT as CYCLE,DB as CDB,JOBS,load,verify as cycling_verify

def run(prepare=False):
    literature_verify(False);cycling_verify(False)
    from verify_corpus_chain_v8 import verify as pinned_v8
    from extract_algae_eucommia_v9 import verify as pinned_v9
    from release_feature_freezes_v021 import verify as pinned_v21
    pinned_v8(False);pinned_v9(False);pinned_v21(False)
    from data.literature_v10 import open_literature_database
    with open_literature_database(DB,sha(DB))as lit,load(CYCLE,'_v22_current_chain').Database(CDB)as cycle:
        materials={r['material_key']:r for r in lit.materials()};tests=lit.tests();caps=lit.capacitances();curves=lit.sampled_curves();responses=lit.series_responses();aux=[r for p in['3e','2e_device','native_mineral_3e','2e_author_factor2']for r in lit.auxiliary_feature_rows(p)]
        assert len(tests)==54 and len(curves)==128 and len(aux)==149
        for r in tests:assert r['record']['source_group']=='doi:'+materials[r['material_key']]['doi']
        payload=[]
        for kind,rows in[('capacitance',caps),('auxiliary',aux)]:
            for r in rows:
                assert r['source_group']=='doi:'+r['doi'];payload.append(dict(kind=kind,source_group=r['source_group']))
        payload += [dict(kind='cycle_candidate',source_group=r['record']['source_group'])for r in tests]
        payload += [dict(kind='bounded_curve',source_group='doi:'+r['doi'])for r in curves]
        allresponses=[]
        for r in lit.connection.execute('select o.outcome_id,o.record_json,m.doi from outcome_observations_v3 o left join materials m using(material_key)'):
            raw=json.loads(r['record_json']);group='doi:'+r['doi']if r['doi']else raw.get('source_group')
            assert group and group.startswith('doi:')
            if raw.get('source_group'):assert raw['source_group']==group
            allresponses.append(dict(outcome_id=r['outcome_id'],source_group=group))
        assert len(allresponses)==2243
        payload += [dict(kind='response',source_group=r['source_group'])for r in allresponses]
        payload += [dict(kind='cycle_observation',source_group=r['source_group'])for r in cycle.fetch('all_review').rows]
        payload += [dict(kind='published_model_parameter_reference',source_group='doi:'+ANN)for r in lit.peer_model_cells()]
        groups=sorted({r['source_group']for r in payload});holds={}
        for group in groups:
            train=[r for r in payload if r['source_group']!=group];test=[r for r in payload if r['source_group']==group]
            assert not {r['source_group']for r in train}&{r['source_group']for r in test}
            assert len(train)+len(test)==len(payload)and all(r['source_group']==group for r in test)
            holds[group]=dict(collections.Counter(r['kind']for r in test))
        links={r['candidate_id']:r for r in cycle.literature_links()};candidate_map={r['candidate_id']:r for r in tests}
        for candidate,key,profiles in JOBS:
            link=links[candidate];raw=candidate_map[candidate]['record'];row=cycle.by_endpoint(key)
            assert link['endpoint_id']==key and link['literature_database_sha256']==sha(DB)
            for field in['retention_pct','cycle_count','reported_current_A_g','system','electrolyte','cycle_voltage_lower_V','cycle_voltage_upper_V']:assert row[field]==raw[field],(candidate,field)
            assert row['source_group']==raw['source_group']
        inputs={p:dict(core=cycle.fetch(p).feature_matrix(),material=cycle.method_specific_material_matrix(p))for p in['reported_3e','reported_2e','reported_3e_all_years','reported_2e_all_years']}
        for p,m in inputs.items():
            assert not m['core']['training_authorized']and m['material']['estimators_fitted']==0
            assert not m['material']['imputed']and len(m['core']['y'])==len(m['material']['X'])
        assert len(cycle.reviewed_pending_batch())==38 and lit.peer_model_review()['target']=='specific_capacitance_F_g_not_cycle_retention'
        report=dict(status='passed',literature_version='v10',literature_sha256=sha(DB),cycling_version='v0.22',cycling_sha256=sha(CDB),historical_audits='v8/v0.20 retain original v5/v7/v8 inputs; v9 and v0.21 explicit immutable inputs; historical counts not weakened',candidate_rows=54,auxiliary_rows=149,bounded_curve_samples=128,published_model_parameter_cells_separate=240,source_groups_audited=len(groups),payloads_audited=len(payload),cross_purpose_DOI_quarantine=holds,new_purpose_admissions=5,new_endpoint_records=3,existing_ID_promotions=2,legacy_year_scope='2023..2026 unchanged',new_year_scope='Two explicitly reviewed all-year views, not replacement cohorts',original_fixed_pending=38,model_fits=0,full_goal_complete=False)
    if prepare:
        assert not(OUT/'merge_manifest.json').exists();write(OUT/'chain_verification.json',report);write(OUT/'cycling_model_inputs_v022.json',inputs)
    else:
        assert json.loads((OUT/'chain_verification.json').read_text('utf8'))==report
        assert json.loads((OUT/'cycling_model_inputs_v022.json').read_text('utf8'))==inputs
    print(json.dumps({k:v for k,v in report.items()if k!='cross_purpose_DOI_quarantine'},ensure_ascii=False))
if __name__=='__main__':
    if len(sys.argv)>2 or(len(sys.argv)==2 and sys.argv[1]!='--prepare'):raise SystemExit('Default read-only; --prepare only unsealed reports')
    run(len(sys.argv)==2)
