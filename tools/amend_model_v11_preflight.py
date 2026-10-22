"""Preserve and amend an untrained plan after finding two taxonomy omissions."""
from pathlib import Path
import json
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from models.v1_1.model import derive_semantics, SEMANTIC
from tools.prepare_model_v11 import RUN,read,write,sha


if __name__=='__main__':
    if (RUN/'evaluation.sqlite').exists() or (RUN/'frozen_run_hashes.json').exists():
        raise ValueError('Cannot amend after fitting starts.')
    history=RUN/'planning_history'
    if history.exists():raise ValueError('Preflight amendment already recorded.')
    history.mkdir()
    names=['training_plan.json','input_snapshot.json','semantic_feature_evidence.json','semantic_coverage.json']
    originals={}
    for name in names:
        shutil.copy2(RUN/name,history/name);originals[name]=sha(history/name)
    evidence=read(RUN/'semantic_feature_evidence.json');by_id={r['endpoint_id']:r for r in evidence}
    snapshot=read(RUN/'input_snapshot.json');changes=[]
    for row in snapshot['records']:
        item=by_id[row['endpoint_id']];new=derive_semantics(item['raw_methods'])
        for field in SEMANTIC:
            if row[field]!=new[field]:changes.append({'endpoint_id':row['endpoint_id'],'field':field,'before':row[field],'after':new[field]})
        row.update(new);item['derived_features']=new
    assert len(changes)==2 and all(c['field']=='precursor_origin_class' and c['before'] is None and c['after']=='plant_residue' for c in changes)
    write(RUN/'input_snapshot.json',snapshot);write(RUN/'semantic_feature_evidence.json',evidence)
    coverage=read(RUN/'semantic_coverage.json')
    coverage['field_source_support']={f:{v:len({r['source_group'] for r in snapshot['records'] if r[f]==v})
        for v in sorted({r[f] for r in snapshot['records'] if r[f] is not None})} for f in SEMANTIC}
    write(RUN/'semantic_coverage.json',coverage)
    plan=read(RUN/'training_plan.json');plan.update(planning_revision=2,snapshot_sha256=sha(RUN/'input_snapshot.json'),
        prefit_amendment='Two existing explicit precursor terms, sesame residue and sawdust, were omitted from the plant taxonomy. Corrected before any estimator fit; all original files retained in planning_history.')
    plan['reference']+=' Source-equal training-target mean is also derived for each outer test, without an extra estimator fit.'
    write(RUN/'training_plan.json',plan)
    write(history/'amendment_record.json',{'reason':plan['prefit_amendment'],'original_sha256':originals,
        'changes':changes,'estimator_fits_before_amendment':0,'target_or_protocol_changes':0,'selection_results_seen':False})
    print(json.dumps({'prefit_amendment':True,'corrected_terms':2,'fits':0},ensure_ascii=False))
