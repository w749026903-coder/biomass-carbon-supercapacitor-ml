"""Pinned full history and joint literature/cycling family quarantine; no fits."""
from pathlib import Path
import collections,contextlib,io,json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tools'))
from verify_mango_leather_cycles_v025 import OUT,DB,PARENT,PSHA,LIT,LDB,JOBS,sha,write,load,verify


def run(prepare=False):
    with contextlib.redirect_stdout(io.StringIO()):
        verify(False)
        from verify_source_chain_v13 import run as history
        history(False)
    from data.literature_v13 import open_literature_database
    from data.literature_v12 import TARGETS12
    with open_literature_database(LDB,sha(LDB))as lit,load(OUT,'_v025_fullchain').Database()as cycle:
        materials={r['material_key']:r for r in lit.materials()};payload=[]
        for kind,rows in [('capacitance',lit.capacitances()),('auxiliary_mass',[r for p in ['3e','2e_device','native_mineral_3e','2e_author_factor2']for r in lit.auxiliary_feature_rows(p)]),('auxiliary_v12',[r for t in TARGETS12 for r in lit.batch12_inputs(t)]),('residue_v13',lit.template_residue_gcd_inputs())]:
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
            assert all(lit.is_quarantined_source(g,[family])for g in {r['group']for r in held})
            holds[family]=dict(collections.Counter(r['kind']for r in held))
        assert len(payload)==7001 and len(families)==207
        candidates={r['candidate_id']:r for r in lit.tests()};links={r['candidate_id']:r for r in cycle.literature_links()}
        for cid,key,doi,sample in JOBS:
            row=cycle.by_endpoint(key);raw=candidates[cid]['record'];held=holds['doi:'+doi]
            assert held['cycle_observation']==1 and held['candidate']==1 and held['auxiliary_mass']==(4 if 'Mango'in cid else 5)
            assert links[cid]['endpoint_id']==key and links[cid]['literature_database_sha256']==sha(LDB)
            for f in ['retention_pct','cycle_count','reported_current_A_g','cycle_voltage_lower_V','cycle_voltage_upper_V','reference_electrode','system','method','electrolyte','concentration_mol_L']:assert raw[f]==row[f]
            assert row['source_family_group_v23']==lit.isolation_group(raw['source_group'])
        assert len(cycle.reviewed_pending_batch())==38 and len(cycle.feature_conflicts_v24())==4
        profiles={p:dict(rows=len(cycle.fetch(p).rows),source_families=len(set(cycle.fetch(p).feature_matrix()['groups'])))for p in ['reported_3e','reported_2e','reported_3e_all_years','reported_2e_all_years']}
        report=dict(status='passed',cycling_version='v0.25',cycling_sha256=sha(DB),parent_sha256=PSHA,literature_version='v13_pinned_unchanged',literature_sha256=sha(LDB),payloads=len(payload),raw_identifiers=len({r['group']for r in payload}),source_families=len(families),full_quarantine_counts=holds,payload_definition='Callable records/views; 9wettingviews duplicatefactrepresentation, not independentexperiments.',material_facts=2383,synthesis_records=176,profiles=profiles,original_fixed_pending=38,legacy_feature_freezes=15,cycle_v24_mask_aliases=4,new_endpoints=2,new_source_families=2,new_purpose_admissions=2,model_fits=0,full_goal_complete=False)
    if prepare:assert not(OUT/'merge_manifest.json').exists();write(OUT/'chain_verification.json',report)
    else:assert json.loads((OUT/'chain_verification.json').read_text('utf8'))==report
    print(json.dumps({k:v for k,v in report.items()if k!='full_quarantine_counts'},ensure_ascii=False))


if __name__=='__main__':
    if len(sys.argv)>2 or(len(sys.argv)==2 and sys.argv[1]!='--prepare'):raise SystemExit('Defaultread-only; --prepare unsealedbatchonly')
    run(len(sys.argv)==2)
