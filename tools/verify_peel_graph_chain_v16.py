"""Pinned historical chain plus cross-task quarantine, without any estimator fit."""
from pathlib import Path
import collections,contextlib,io,json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tools'))
from extract_peel_graphs_v16 import OUT,DB,PARENT,PSHA,PE,DA,sha,write

def run(prepare=False):
    with contextlib.redirect_stdout(io.StringIO()):
        from verify_peel_graphs_v16 import verify
        verify(False)
        from verify_peel_date_chain_v15 import run as history
        history(False)
    from data.literature_v16 import open_literature_database
    from data.literature_v12 import TARGETS12
    from release_mango_leather_cycles_v025 import OUT as COUT,DB as CDB,load
    with open_literature_database(DB,sha(DB))as lit,load(COUT,'_v025_pinned_graph16').Database()as cycle:
        mats={r['material_key']:r for r in lit.materials()};payload=[]
        for kind,rows in [('capacitance',lit.capacitances()),('auxiliary_mass',[r for p in ['3e','2e_device','native_mineral_3e','2e_author_factor2']for r in lit.auxiliary_feature_rows(p)]),('auxiliary_v12',[r for t in TARGETS12 for r in lit.batch12_inputs(t)]),('residue_v13',lit.template_residue_gcd_inputs()),('rate_v14',lit.furfural_rate_inputs('interval_mixed')),('rate_v16',lit.batch16_rate_inputs('point_mixed')),('expanded_graph_3e',lit.expanded_graph_3e_inputs())]:
            for r in rows:assert r['source_group']=='doi:'+r['doi'];payload.append(dict(kind=kind,group=r['source_group']))
        for r in lit.tests():assert r['record']['source_group']=='doi:'+mats[r['material_key']]['doi'];payload.append(dict(kind='candidate',group=r['record']['source_group']))
        payload += [dict(kind='bounded_curve',group='doi:'+r['doi'])for r in lit.sampled_curves()]
        payload += [dict(kind='material_fact',group='doi:'+r['doi'])for r in lit.facts()]
        payload += [dict(kind='material_registration',group='doi:'+r['doi'])for r in mats.values()]
        for r in lit.connection.execute('select material_key from synthesis_stages_v3'):payload.append(dict(kind='synthesis',group='doi:'+mats[r[0]]['doi']))
        for r in lit.connection.execute('select o.record_json,m.doi from outcome_observations_v3 o left join materials m using(material_key)'):
            rec=json.loads(r[0]);g='doi:'+r[1]if r[1]else rec.get('source_group');assert g;payload.append(dict(kind='response',group=g))
        payload += [dict(kind='wetting_view_v13',group=r['record']['source_group'])for r in lit.wettability_series_v13()]
        payload += [dict(kind='cycle_observation',group=r['source_group'])for r in cycle.fetch('all_review').rows]
        payload += [dict(kind='published_model_reference',group='doi:10.1039/c9ra01255a')for _ in lit.peer_model_cells()]
        payload.append(dict(kind='explicit_prior_work',group='doi:10.1016/j.jece.2025.120693'))
        for kind,rows in [('series_annotation_v14',lit.furfural_series_annotations()),('figure_scope_v14',lit.figure_scope_reviews_v14()),('series_annotation_v15',lit.batch15_annotations()),('figure_scope_v15',lit.batch15_figures())]:
            payload += [dict(kind=kind,group='doi:'+r['doi'])for r in rows]
        payload += [dict(kind='rate_audit_v14',group='doi:10.3390/polym16233421')for _ in lit.furfural_rate_audits()]
        payload += [dict(kind='contribution_pair_view_v14',group='doi:10.3390/polym16233421')for _ in lit.furfural_contributions()]
        payload += [dict(kind='XPS_component_view_v15',group=r['record']['source_group'])for r in lit.batch15_components()]
        for r in payload:r['family']=lit.isolation_group(r['group'])
        families=sorted({r['family']for r in payload});holds={}
        for f in families:
            held=[r for r in payload if r['family']==f];train=[r for r in payload if r['family']!=f];assert not{r['family']for r in held}&{r['family']for r in train};assert all(lit.is_quarantined_source(g,[f])for g in{r['group']for r in held});holds[f]=dict(collections.Counter(r['kind']for r in held))
        assert len(payload)==8071,len(payload)
        for doi,expected in [(PE,dict(material_registration=12,material_fact=118,capacitance=100,bounded_curve=80,rate_v16=80,expanded_graph_3e=80,auxiliary_mass=16,synthesis=10,response=36,candidate=2,XPS_component_view_v15=26,series_annotation_v15=8,figure_scope_v15=10)),(DA,dict(material_registration=2,material_fact=38,capacitance=19,bounded_curve=15,rate_v16=15,expanded_graph_3e=15,auxiliary_mass=4,synthesis=2,response=2,XPS_component_view_v15=6,figure_scope_v15=6))]:
            # This cohort may also have existing cycling endpoints; compare new literature payload kinds only.
            for k,n in expected.items():assert holds['doi:'+doi].get(k,0)==n,(doi,k,holds['doi:'+doi])
        assert sha(CDB)=='8a8f311509df7d72738840aac31ced027849a538ee31ec785ede71aa4abcc5b2'
        assert len(cycle.reviewed_pending_batch())==38 and len(cycle.feature_conflicts_v24())==4
        report=dict(status='passed',literature_sha256=sha(DB),parent_sha256=PSHA,cycling_sha256=sha(CDB),payloads=len(payload),raw_identifiers=len({r['group']for r in payload}),source_families=len(families),full_quarantine_counts=holds,new_literature_sources=0,new_approximate_GCD_inputs=75,explicit_expanded_graph_3e_rows=251,explicit_expanded_graph_3e_DOI_groups=18,ordinary_3e_rows=176,ordinary_3e_DOI_groups=18,all_four_auxiliary_rows=192,all_four_auxiliary_DOI_groups=19,original_fixed_pending=38,legacy_feature_freezes=15,Cycas_mask_aliases=4,formal_cycling_admissions=0,model_fits=0,scientific_goal_complete=False,payload_definition='Callable payloads and duplicate views, not independent experiments; same DOI family quarantines all tasks together')
    if prepare:assert not(OUT/'merge_manifest.json').exists();write(OUT/'chain_verification.json',report)
    else:assert json.loads((OUT/'chain_verification.json').read_text('utf8'))==report
    print(json.dumps({k:v for k,v in report.items()if k!='full_quarantine_counts'},ensure_ascii=False))

if __name__=='__main__':
    if len(sys.argv)>2 or(len(sys.argv)==2 and sys.argv[1]!='--prepare'):raise SystemExit('Default read-only; --prepare once on unsealed release')
    run(len(sys.argv)==2)
