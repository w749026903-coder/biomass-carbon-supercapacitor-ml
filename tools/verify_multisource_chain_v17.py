"""Pinned historical verifications and current cross-task source quarantine."""
from pathlib import Path
import collections,contextlib,io,json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tools'))
from extract_multisource_tables_v17 import OUT,DB,PSHA,sha,write

def run(prepare=False):
    if prepare:assert not(OUT/'merge_manifest.json').exists()
    with contextlib.redirect_stdout(io.StringIO()):
        from verify_peel_graph_chain_v16 import run as old
        old(False)
    from data.literature_v17 import open_literature_database,TARGETS17
    from data.literature_v12 import TARGETS12
    from data.cycling_db import open_database
    CDB=ROOT/'循环稳定性数据库_v0.25_芒果核皮革循环准入_20261026/cycling_v0_25.sqlite'
    assert sha(CDB)=='8a8f311509df7d72738840aac31ced027849a538ee31ec785ede71aa4abcc5b2'
    with open_literature_database(DB,sha(DB))as d,open_database()as cycle:
        assert cycle.path==CDB or Path(cycle.path).resolve()==CDB.resolve()
        mats={r['material_key']:r for r in d.materials()};payload=[]
        def add(kind,rows):
            for r in rows:
                assert r['source_group']=='doi:'+r['doi'];payload.append(dict(kind=kind,group=r['source_group']))
        add('capacitance',d.capacitances())
        add('auxiliary_mass',[r for p in ['3e','2e_device','native_mineral_3e','2e_author_factor2']for r in d.auxiliary_gcd(p)])
        add('auxiliary_v12',[r for t in TARGETS12 for r in d.batch12_inputs(t)])
        add('residue_v13',d.template_residue_gcd_inputs());add('rate_v14',d.furfural_rate_inputs('interval_mixed'));add('rate_v16',d.batch16_rate_inputs('point_mixed'));add('expanded_graph3E',d.expanded_graph_3e_inputs())
        add('purpose_v17',[r for t in TARGETS17 for r in d.batch17_inputs(t)])
        for r in d.tests():
            assert r['record']['source_group']=='doi:'+mats[r['material_key']]['doi'];payload.append(dict(kind='cycle_candidate',group=r['record']['source_group']))
        for kind,rows in [('material_fact',d.facts()),('registration',d.materials()),('bounded_curve',d.sampled_curves())]:payload.extend(dict(kind=kind,group='doi:'+r['doi'])for r in rows)
        for r in d.connection.execute('select material_key from synthesis_stages_v3'):payload.append(dict(kind='synthesis',group='doi:'+mats[r[0]]['doi']))
        for r in d.connection.execute('select o.record_json,m.doi from outcome_observations_v3 o left join materials m using(material_key)'):
            rec=json.loads(r[0]);g='doi:'+r[1]if r[1]else rec.get('source_group');assert g;payload.append(dict(kind='response',group=g))
        payload.extend(dict(kind='cycle_observation',group=r['source_group'])for r in cycle.fetch('all_review').rows)
        payload.extend(dict(kind='model_reference',group='doi:10.1039/c9ra01255a')for _ in d.peer_model_cells());payload.append(dict(kind='explicit_priorwork',group='doi:10.1016/j.jece.2025.120693'))
        for kind,rows in [('annotation_v14',d.furfural_series_annotations()),('figure_v14',d.figure_scope_reviews_v14()),('annotation_v15',d.batch15_annotations()),('figure_v15',d.batch15_figures()),('annotation_v17',d.batch17_annotations()),('figure_v17',d.batch17_figures())]:payload.extend(dict(kind=kind,group='doi:'+r['doi'])for r in rows)
        payload.extend(dict(kind='XPS_component_v15',group=r['record']['source_group'])for r in d.batch15_components())
        payload.extend(dict(kind='wetting_v13',group=r['record']['source_group'])for r in d.wettability_series_v13())
        payload.extend(dict(kind='rate_audit_v14',group='doi:10.3390/polym16233421')for _ in d.furfural_rate_audits());payload.extend(dict(kind='contribution_v14',group='doi:10.3390/polym16233421')for _ in d.furfural_contributions())
        for r in payload:r['family']=d.isolation_group(r['group'])
        families=sorted({r['family']for r in payload});holds={}
        for family in families:
            test=[r for r in payload if r['family']==family];train=[r for r in payload if r['family']!=family]
            assert not{r['family']for r in test}&{r['family']for r in train}
            assert all(d.is_quarantined_source(g,[family])and d.is_quarantined_source(g.removeprefix('doi:'),[family])for g in {r['group']for r in test})
            holds[family]=dict(collections.Counter(r['kind']for r in test))
        assert len(cycle.reviewed_pending_batch())==38 and len(cycle.feature_conflicts_v24())==4
        rows3=d.auxiliary_gcd('3e');allaux=[r for p in ['3e','2e_device','native_mineral_3e','2e_author_factor2']for r in d.auxiliary_gcd(p)]
        report=dict(status='passed',literature_sha256=sha(DB),parent_sha256=PSHA,cycling_sha256=sha(CDB),payloads=len(payload),raw_identifiers=len({r['group']for r in payload}),source_families=len(families),full_quarantine_counts=holds,ordinary_3e_rows=len(rows3),ordinary_3e_DOI_groups=len({r['doi']for r in rows3}),all_four_auxiliary_rows=len(allaux),all_four_auxiliary_DOI_groups=len({r['doi']for r in allaux}),expanded_graph_3e_rows=259,separate_v17_purpose_rows=[8,6,1],original_fixed_pending=38,legacy_feature_freezes=15,Cycas_mask_aliases=4,formal_cycling_admissions=0,model_fits=0,scientific_goal_complete=False,payload_definition='Callable reports and views, not independent experiments. Same DOI/family quarantines every material/response/curve/auxiliary/cycling task together. Historical chain uses pinned immutable databases.')
    if prepare:write(OUT/'chain_verification.json',report)
    else:assert json.loads((OUT/'chain_verification.json').read_text('utf8'))==report
    print(json.dumps({k:v for k,v in report.items()if k!='full_quarantine_counts'},ensure_ascii=False))

if __name__=='__main__':
    if len(sys.argv)>2 or(len(sys.argv)==2 and sys.argv[1]!='--prepare'):raise SystemExit('Default readonly, --prepare before seal only')
    run(len(sys.argv)==2)
