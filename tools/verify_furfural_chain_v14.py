"""Pinned history plus full-task source quarantine for bounded and interval views."""
from pathlib import Path
import collections,contextlib,io,json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tools'))
from verify_furfural_curves_v14 import OUT,DB,PARENT,PSHA,sha,write,verify


def run(prepare=False):
    with contextlib.redirect_stdout(io.StringIO()):
        verify(False)
        from verify_mango_leather_chain_v025 import run as history
        history(False)
    from data.literature_v14 import open_literature_database,FU
    from data.literature_v12 import TARGETS12
    from release_mango_leather_cycles_v025 import OUT as COUT,DB as CDB,load
    with open_literature_database(DB,sha(DB))as lit,load(COUT,'_v025_pinned_furfural14').Database()as cycle:
        materials={r['material_key']:r for r in lit.materials()};payload=[]
        for kind,rows in [('capacitance',lit.capacitances()),('auxiliary_mass',[r for p in ['3e','2e_device','native_mineral_3e','2e_author_factor2']for r in lit.auxiliary_feature_rows(p)]),('auxiliary_v12',[r for t in TARGETS12 for r in lit.batch12_inputs(t)]),('residue_v13',lit.template_residue_gcd_inputs()),('rate_v14',lit.furfural_rate_inputs('interval_mixed'))]:
            for r in rows:assert r['source_group']=='doi:'+r['doi'];payload.append(dict(kind=kind,group=r['source_group']))
        for r in lit.tests():assert r['record']['source_group']=='doi:'+materials[r['material_key']]['doi'];payload.append(dict(kind='candidate',group=r['record']['source_group']))
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
        payload += [dict(kind='series_annotation_v14',group='doi:'+r['doi'])for r in lit.furfural_series_annotations()]
        payload += [dict(kind='figure_scope_v14',group='doi:'+r['doi'])for r in lit.figure_scope_reviews_v14()]
        payload += [dict(kind='rate_audit_v14',group='doi:'+FU)for _ in lit.furfural_rate_audits()]
        payload += [dict(kind='contribution_pair_view_v14',group='doi:'+FU)for _ in lit.furfural_contributions()]
        for r in payload:r['family']=lit.isolation_group(r['group'])
        families=sorted({r['family']for r in payload});holds={}
        for family in families:
            held=[r for r in payload if r['family']==family];train=[r for r in payload if r['family']!=family];assert not{r['family']for r in held}&{r['family']for r in train}
            assert all(lit.is_quarantined_source(g,[family])for g in {r['group']for r in held});holds[family]=dict(collections.Counter(r['kind']for r in held))
        assert len(payload)==7213,len(payload)
        assert len(families)==207 and len({r['group']for r in payload})==209
        expected=dict(capacitance=53,auxiliary_mass=0,rate_v14=48,residue_v13=4,bounded_curve=54,material_fact=59,material_registration=9,synthesis=8,response=48,series_annotation_v14=18,figure_scope_v14=12,rate_audit_v14=8,contribution_pair_view_v14=5)
        for kind,n in expected.items():assert holds['doi:'+FU].get(kind,0)==n,(kind,holds['doi:'+FU])
        assert len(cycle.reviewed_pending_batch())==38 and len(cycle.feature_conflicts_v24())==4
        assert sha(CDB)=='8a8f311509df7d72738840aac31ced027849a538ee31ec785ede71aa4abcc5b2'
        profiles={p:dict(rows=len(cycle.fetch(p).rows),source_families=len(set(cycle.fetch(p).feature_matrix()['groups'])))for p in ['reported_3e','reported_2e','reported_3e_all_years','reported_2e_all_years']}
        modes={mode:dict(rows=len(lit.furfural_rate_inputs(mode)),point_labels=sum(v is not None for v in lit.furfural_rate_matrix(mode)['y']),interval_only_labels=sum(v is None for v in lit.furfural_rate_matrix(mode)['y']),source_families=1,model_fits=0)for mode in ['author_exact','point_mixed','interval_mixed','figure_only']}
        report=dict(status='passed',literature_sha256=sha(DB),parent_literature_sha256=PSHA,cycling_version='v0.25_pinned_unchanged',cycling_sha256=sha(CDB),payloads=len(payload),raw_identifiers=209,source_families=207,full_quarantine_counts=holds,payload_definition='Callable records and duplicate representations, including figure/series reviews and interval targets; inventory counts are not independent experiments.',new_source_families=0,new_materials=0,material_facts=2383,synthesis_records=176,rate_modes=modes,cycling_profiles=profiles,original_fixed_pending=38,legacy_feature_freezes=15,cycle_v24_mask_aliases=4,formal_cycling_admissions=0,model_fits=0,full_goal_complete=False)
    if prepare:assert not(OUT/'merge_manifest.json').exists();write(OUT/'chain_verification.json',report)
    else:assert json.loads((OUT/'chain_verification.json').read_text('utf8'))==report
    print(json.dumps({k:v for k,v in report.items()if k!='full_quarantine_counts'},ensure_ascii=False))


if __name__=='__main__':
    if len(sys.argv)>2 or(len(sys.argv)==2 and sys.argv[1]!='--prepare'):raise SystemExit('Defaultread-only; --prepare unsealedbatchonly')
    run(len(sys.argv)==2)
