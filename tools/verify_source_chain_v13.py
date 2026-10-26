"""Pinned history and whole-source/family input checks, without any model fitting."""
from pathlib import Path
import collections,contextlib,io,json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tools'))
from verify_source_series_v13 import OUT,DB,PSHA,sha,write,verify


def run(prepare=False):
    with contextlib.redirect_stdout(io.StringIO()):
        verify(False)
        from verify_cycas_chain_v024 import run as history
        history(False)
    from data.literature_v13 import open_literature_database
    from data.literature_v12 import TARGETS12
    from release_cycas_cycles_v024 import OUT as COUT,DB as CDB,load
    with open_literature_database(DB,sha(DB))as lit,load(COUT,'_v024_pinned_v13').Database()as cycle:
        materials={r['material_key']:r for r in lit.materials()};payload=[]
        auxiliary=[r for p in ['3e','2e_device','native_mineral_3e','2e_author_factor2']for r in lit.auxiliary_feature_rows(p)]
        for kind,rows in [('capacitance',lit.capacitances()),('auxiliary_mass',auxiliary),('auxiliary_v12',[r for t in TARGETS12 for r in lit.batch12_inputs(t)]),('residue_v13',lit.template_residue_gcd_inputs())]:
            for r in rows:assert r['source_group']=='doi:'+r['doi'];payload.append(dict(kind=kind,group=r['source_group']))
        for r in lit.tests():
            assert r['record']['source_group']=='doi:'+materials[r['material_key']]['doi'];payload.append(dict(kind='candidate',group=r['record']['source_group']))
        payload += [dict(kind='bounded_curve',group='doi:'+r['doi'])for r in lit.sampled_curves()]
        payload += [dict(kind='material_fact',group='doi:'+r['doi'])for r in lit.facts()]
        payload += [dict(kind='material_registration',group='doi:'+r['doi'])for r in materials.values()]
        for r in lit.connection.execute('select material_key from synthesis_stages_v3'):payload.append(dict(kind='synthesis',group='doi:'+materials[r[0]]['doi']))
        for r in lit.connection.execute('select o.record_json,m.doi from outcome_observations_v3 o left join materials m using(material_key)'):
            raw=json.loads(r[0]);group='doi:'+r[1]if r[1]else raw.get('source_group');assert group;payload.append(dict(kind='response',group=group))
        payload += [dict(kind='wetting_view_v13',group=r['record']['source_group'])for r in lit.wettability_series_v13()]
        payload += [dict(kind='cycle_observation',group=r['source_group'])for r in cycle.fetch('all_review').rows]
        payload += [dict(kind='published_model_reference',group='doi:10.1039/c9ra01255a')for _ in lit.peer_model_cells()]
        payload.append(dict(kind='explicit_prior_work',group='doi:10.1016/j.jece.2025.120693'))
        for r in payload:r['family']=lit.isolation_group(r['group'])
        families=sorted({r['family']for r in payload});holds={}
        for family in families:
            held=[r for r in payload if r['family']==family];train=[r for r in payload if r['family']!=family]
            assert not{r['family']for r in held}&{r['family']for r in train}
            expanded=lit.quarantine_source_groups([family])
            assert all(lit.isolation_group(r['group'])in{lit.isolation_group(g)for g in expanded}for r in held)
            assert all(lit.is_quarantined_source(g,[family])for g in {r['group']for r in held})
            assert all(lit.isolation_group(group)==family for group in expanded)
            holds[family]=dict(collections.Counter(r['kind']for r in held))
        assert len(payload)==6999,len(payload)
        assert sha(CDB)=='08e9ff4f0781bb242e1b934aaed2240bafda02b5b913fe2f3e7706d869db1270'
        assert len(cycle.reviewed_pending_batch())==38 and len(cycle.feature_conflicts_v24())==4
        assert len(lit.legacy_feature_conflicts())==15
        assert holds['doi:10.3390/polym16233421']['residue_v13']==4
        assert holds['doi:10.1039/d6ra08120g']['wetting_view_v13']==9
        assert holds['doi:10.1039/d6ra08120g'].get('auxiliary_mass',0)==0
        profiles={p:dict(rows=len(cycle.fetch(p).rows),source_families=len(set(cycle.fetch(p).feature_matrix()['groups'])))for p in ['reported_3e','reported_2e','reported_3e_all_years','reported_2e_all_years']}
        preflight_profiles={}
        for p in ['3e','2e_device','native_mineral_3e','2e_author_factor2']:
            rows=lit.auxiliary_feature_rows(p);groups=collections.Counter(lit.isolation_group(r['source_group'])for r in rows)
            preflight_profiles[p]=dict(rows=len(rows),source_families=len(groups),source_contribution_rows=dict(groups),source_balanced_row_weights={g:1/n for g,n in groups.items()},missing_BET=sum(r['BET_surface_area_m2_g']is None for r in rows),model_fits=0)
        targets12={t:dict(rows=len(lit.batch12_inputs(t)),families=len(set(lit.batch12_matrix(t)['groups'])))for t in TARGETS12}
        residue=lit.template_residue_matrix()
        report=dict(status='passed',literature_sha256=sha(DB),parent_sha256=PSHA,cycling_sha256=sha(CDB),cycling_version='v0.24_pinned_unchanged',payloads=len(payload),raw_identifiers=len({r['group']for r in payload}),source_families=len(families),full_quarantine_counts=holds,payload_definition='Callable records/views including 9 wetting views already represented by material facts; inventory counts are not independent scientific measurements.',material_facts=2383,synthesis_records=176,original_fixed_pending=38,legacy_feature_freezes=15,cycle_v24_mask_aliases=4,cycling_profiles=profiles,formal_cycling_admissions=0,model_fits=0,full_goal_complete=False)
        preflight=dict(status='passed_input_checks_only',ordinary_mass_profiles=preflight_profiles,separate_v12_targets=targets12,residue_v13=dict(rows=len(residue['y']),families=len(set(residue['groups'])),feature_names=residue['feature_names'],missing_cells=sum(sum(r)for r in residue['missing_mask']),independent_source_validation_possible_alone=False),commercial_reference=dict(reports=24,nominal_conditions=21,independent_physical_experiments=None,biomass_training_eligible=False),report_groups=lit.report_groups_v13(),cycling_profiles=profiles,source_quarantine='All material, recipe, capacitance, curve, response, cycling and reference/prior-work family records held out together. Source weights do not create new independent papers.',model_route='Retain source-balanced tabular/auxiliary route after full literature review; no final route or performance claim before whole corpus coverage.',no_imputation=True,model_fits=0,scientific_goal_complete=False)
    for name,value in [('chain_verification',report),('model_inputs_preflight',preflight)]:
        if prepare:assert not(OUT/'merge_manifest.json').exists();write(OUT/(name+'.json'),value)
        else:assert json.loads((OUT/(name+'.json')).read_text('utf8'))==value
    print(json.dumps({k:v for k,v in report.items()if k!='full_quarantine_counts'},ensure_ascii=False))


if __name__=='__main__':
    if len(sys.argv)>2 or(len(sys.argv)==2 and sys.argv[1]!='--prepare'):raise SystemExit('Default read-only; --prepare only unsealed batch')
    run(len(sys.argv)==2)
