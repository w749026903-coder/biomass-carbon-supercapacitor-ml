"""Pinned history plus full-family quarantine for the v12 evidence layer; no fitting."""
from pathlib import Path
import collections,contextlib,io,json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tools'))
from extract_porous_series_v12 import OUT,DB,PSHA,sha,write,verify

def run(prepare=False):
    with contextlib.redirect_stdout(io.StringIO()):
        verify(False)
        from verify_cycle_family_v023 import run as history
        history(False)
    from data.literature_v12 import open_literature_database,TARGETS12
    from release_cycle_family_v023 import OUT as COUT,DB as CDB,load,PRIOR
    with open_literature_database(DB,sha(DB))as lit,load(COUT,'_v023_pinned_v12').Database()as cycle:
        materials={r['material_key']:r for r in lit.materials()};payload=[]
        for kind,rs in [('capacitance',lit.capacitances()),('auxiliary_mass',[r for p in['3e','2e_device','native_mineral_3e','2e_author_factor2']for r in lit.auxiliary_feature_rows(p)]),('auxiliary_v12',[r for target in TARGETS12 for r in lit.batch12_inputs(target)])]:
            for r in rs:assert r['source_group']=='doi:'+r['doi'];payload.append(dict(kind=kind,group=r['source_group']))
        for r in lit.tests():
            assert r['record']['source_group']=='doi:'+materials[r['material_key']]['doi'];payload.append(dict(kind='candidate',group=r['record']['source_group']))
        payload += [dict(kind='bounded_curve',group='doi:'+r['doi'])for r in lit.sampled_curves()]
        payload += [dict(kind='material_fact',group='doi:'+r['doi'])for r in lit.facts()]
        payload += [dict(kind='material_registration',group='doi:'+r['doi'])for r in materials.values()]
        for r in lit.connection.execute('select material_key from synthesis_stages_v3'):payload.append(dict(kind='synthesis',group='doi:'+materials[r[0]]['doi']))
        for r in lit.connection.execute('select o.record_json,m.doi from outcome_observations_v3 o left join materials m using(material_key)'):
            raw=json.loads(r[0]);g='doi:'+r[1]if r[1]else raw.get('source_group');assert g;payload.append(dict(kind='response',group=g))
        payload += [dict(kind='cycle_observation',group=r['source_group'])for r in cycle.fetch('all_review').rows]
        payload += [dict(kind='published_model_reference',group='doi:10.1039/c9ra01255a')for _ in lit.peer_model_cells()]
        payload.append(dict(kind='explicit_prior_work',group='doi:'+PRIOR))
        for r in payload:r['family']=lit.isolation_group(r['group'])
        families=sorted({r['family']for r in payload});holds={}
        for f in families:
            held=[r for r in payload if r['family']==f];train=[r for r in payload if r['family']!=f];assert not{r['family']for r in held}&{r['family']for r in train};holds[f]=dict(collections.Counter(r['kind']for r in held))
        assert len(cycle.reviewed_pending_batch())==38
        assert sha(CDB)=='ccebb63c33c87b3f726fa044cf83973ab7ec9fb613ea13bb725b6ae35445d9b5'
        assert len(payload)==6518,len(payload)
        profiles={p:dict(rows=len(cycle.fetch(p).rows),source_families=len(set(cycle.fetch(p).feature_matrix()['groups'])))for p in['reported_3e','reported_2e','reported_3e_all_years','reported_2e_all_years']}
        targets={}
        for t in TARGETS12:
            m=lit.batch12_matrix(t);targets[t]=dict(rows=len(m['y']),unit=m['unit'],families=len(set(m['groups'])),physical_test_groups=len(set(m['physical_test_groups'])),missing_cells=sum(sum(r)for r in m['missing_mask']),feature_names=m['feature_names'],independent_source_validation_possible_alone=len(set(m['groups']))>=2,model_fits=0)
        report=dict(status='passed',database_sha256=sha(DB),parent_literature_sha256=PSHA,cycling_version='v0.23_pinned_unchanged',cycling_sha256=sha(CDB),payloads=len(payload),raw_identifiers=len({r['group']for r in payload}),source_families=len(families),family_quarantine_counts=holds,cycling_profiles=profiles,original_fixed_pending=38,legacy_cycle_feature_cells_frozen=15,material_facts=2172,synthesis_records=151,model_fits=0,full_goal_complete=False)
        preflight=dict(status='passed_input_checks_only',targets=targets,ordinary_mass_auxiliary_rows=163,ordinary_mass_auxiliary_DOI_groups=15,cycling_profiles=profiles,cross_task_quarantine='All labels, material facts, synthesis, response, curves and explicit prior-work families held out together; do not pool Cs/Cd or mass/volume as independent observations.',no_model_performance_claim=True,model_fits=0)
    for name,value in [('chain_verification',report),('model_inputs_preflight',preflight)]:
        if prepare:assert not(OUT/'merge_manifest.json').exists();write(OUT/(name+'.json'),value)
        else:assert json.loads((OUT/(name+'.json')).read_text('utf8'))==value
    print(json.dumps({k:v for k,v in report.items()if k!='family_quarantine_counts'},ensure_ascii=False))

if __name__=='__main__':
    if len(sys.argv)>2 or(len(sys.argv)==2 and sys.argv[1]!='--prepare'):raise SystemExit('Default read-only; --prepare unsealed batch only')
    run(len(sys.argv)==2)
