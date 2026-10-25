"""Historical versions pinned to their inputs, current cross-purpose groups audited separately."""
from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tools'))
from extract_algae_eucommia_v9 import OUT,DB,sha,verify,write,A,W,R,C
from release_feature_freezes_v021 import verify as cycle_verify
def run(prepare=False):
    verify(False);cycle_verify(False)
    from verify_corpus_chain_v8 import verify as historical_verify
    historical_verify(False)
    from data.literature_v9 import open_literature_database
    from data.cycling_db import open_database
    with open_literature_database(DB,sha(DB)) as lit,open_database() as cycle:
        assert cycle.contract['schema']=='cycling_feature_conflict_freeze_v21'
        tests=lit.tests();caps=lit.capacitances();aux=lit.auxiliary_feature_rows('3e');material_matrix=lit.algae_GCD_matrix();responses=lit.series_responses();oldcycles=cycle.fetch('all_review').rows
        assert len(tests)==44 and len(aux)==121 and len(material_matrix['X'])==18
        assert all(r.get('source_group')=='doi:'+A for r in aux if r['doi']==A)
        assert len({tuple(row) for row in zip(material_matrix['sample_names'],[r[0] for r in material_matrix['X']])})==18
        assert not material_matrix['imputed'] and not material_matrix['estimators_fitted'] and not material_matrix['training_authorized']
        assert abs(sum(material_matrix['sample_weight'])-1)<1e-12
        assert not {'Rct','retention_pct','CE','capacitance_F_g','DOI','sample_name'} & set(material_matrix['feature_names'])
        holds={}
        for doi,expected in [(A,(35,6,18,5)),(W,(129,2,0,2)),(R,(0,0,0,0)),(C,(0,0,0,0))]:
            g='doi:'+doi;counts=(sum(r['doi']==doi for r in caps),sum(r['record']['source_group']==g for r in tests),sum(r['source_group']==g for r in aux),sum(r['source_group']==g for r in oldcycles))
            assert counts==expected,(doi,counts)
            retained=[r for r in aux if r['source_group']!=g];assert not any(r['source_group']==g for r in retained)
            holds[doi]=dict(capacitance_reports=counts[0],cycle_candidates=counts[1],auxiliary_GCD_rows=counts[2],existing_cycling_observations=counts[3],separate_response_records=sum(r['doi']==doi for r in responses),all_labels_curves_responses_sameDOI_quarantine_required=True)
        assert len(cycle.field_changes())==15
        assert len(cycle.reviewed_pending_batch())==38
    report=dict(status='passed',literature_version='v9',database_sha256=sha(DB),cycling_version='v0.21',historical_v8_v020_pinned_verification='passed with original v5/v7/v8 inputs; no cardinality weakening',current44_source_groups_verified=True,current_cross_purpose_holdouts=holds,cycle_feature_freezes=15,original_fixed_pending=38,new_formal_cycling_admissions=0,model_fits=0,full_goal_complete=False)
    if prepare:
        assert not (OUT/'merge_manifest.json').exists();write(OUT/'chain_verification.json',report);write(OUT/'Algae_GCD_model_inputs.json',material_matrix)
    else:
        assert json.loads((OUT/'chain_verification.json').read_text('utf8'))==report
        assert json.loads((OUT/'Algae_GCD_model_inputs.json').read_text('utf8'))==material_matrix
    print(json.dumps(report,ensure_ascii=False))
if __name__=='__main__':
    if len(sys.argv)>2 or (len(sys.argv)==2 and sys.argv[1]!='--prepare'):raise SystemExit('Defaultread-only; --prepareonlyunsealedreports')
    run(len(sys.argv)==2)
