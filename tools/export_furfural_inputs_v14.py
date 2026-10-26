"""One-use typed point/interval exports; blank targets stay blank."""
import csv,io,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tools'))
from extract_furfural_curves_v14 import OUT,DB,sha
from data.literature_v14 import open_literature_database


def run():
    assert not(OUT/'merge_manifest.json').exists()
    jobs=[('point_mixed','point_inputs_v14.csv'),('interval_mixed','interval_inputs_v14.csv')]
    assert all(not(OUT/name).exists()for mode,name in jobs)
    fields=['sample_name','reported_current_A_g','target_F_g','target_lower_F_g','target_upper_F_g','target_kind','bounds_kind','point_loss_eligible','source_family_group','source_balanced_weight','observation_id','graph_observation_id','physical_test_group','DOI','system','electrolyte','concentration_mol_L','reference_electrode','voltage_lower_V','voltage_upper_V','current_mass_basis']
    outputs=[]
    with open_literature_database(DB,sha(DB))as d:
        for mode,name in jobs:
            rows=d.furfural_rate_inputs(mode);stream=io.StringIO(newline='');writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
            for r in rows:
                c=r['conditions'];writer.writerow(dict(sample_name=r['sample_name'],reported_current_A_g=r['current_A_g'],target_F_g=r['target_value'],target_lower_F_g=r['target_lower_bound'],target_upper_F_g=r['target_upper_bound'],target_kind=r['target_value_kind'],bounds_kind=r['target_bound_semantics'],point_loss_eligible=r['point_loss_eligible'],source_family_group=r['source_family_group'],source_balanced_weight=1/len(rows),observation_id=r['observation_id'],graph_observation_id=r['graph_observation_id'],physical_test_group=r['physical_test_group'],DOI=r['doi'],system=r['system'],electrolyte=r['electrolyte'],concentration_mol_L=r['concentration_mol_L'],reference_electrode=c['reference_electrode'],voltage_lower_V=c['voltage_lower_V'],voltage_upper_V=c['voltage_upper_V'],current_mass_basis=c['current_mass_basis']))
            outputs.append((OUT/name,stream.getvalue()))
    for path,content in outputs:
        with path.open('x',encoding='utf8',newline='')as f:f.write(content)
    print(json.dumps(dict(point_rows=46,interval_rows=48,blank_interval_point_targets=2,model_fits=0)))


if __name__=='__main__':run()
