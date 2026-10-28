"""Attach new own-material evidence to the existing pending device identity."""
from pathlib import Path
import json,sqlite3,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.extract_corn_soot_v3 import OUT,DB,CORN,read,write,sha,dump

def link():
    assert not(OUT/'merge_manifest.json').exists()and not(OUT/'cycle_candidate_evidence.json').exists()
    c=sqlite3.connect(DB);c.row_factory=sqlite3.Row;c.execute('pragma foreign_keys=on')
    eid='candidate:B20:B2_012:1';old=json.loads(c.execute('select record_json from cycle_records where endpoint_id=?',(eid,)).fetchone()[0])
    assert old['sample_name']=='CS-800//CS-800'and old['source_group']=='doi:'+CORN
    m=next(m for m in read(OUT/'new_materials.json')if m['doi']==CORN and m['sample_name']=='CS-800');mk=m['material_key']
    ff=[f for f in read(OUT/'new_facts.json')if f['material_key']==mk and f['selected_for_this_purpose']]
    evidence=dict(endpoint_id=eid,material_key=mk,status='confirmed_symmetric_device_material_identity_not_admission',
      basis='Own main methods p11 and device result p29-p30 explicitly CS-800//CS-800, identical CS-800 electrodes.',
      selected_material_values=m['features'],source_receipts=ff,original_cycle_record=old,
      retention_reports=[dict(value=93.75,locator='XML body p30 zero based'),dict(value=93.7,locator='Own Table3 row')],
      scope='native_residual_silica_2e_separate_review',current_mass_basis='author_reported_unknown_not_inferred',
      remaining=['Figure5e has ambiguous apparent trace levels without a clear series legend; no guessed normalization baseline.',
                 'Author device formula and single-electrode label differ; report-purpose kept separate.'],
      new_cycling_admission=False,new_cycle_record=False,new_model_fits=0,part_of_fixed_pending37=False)
    c.execute('insert into cycle_material_links values(?,?,?)',(eid,mk,dump(evidence)))
    c.execute('create table cycle_candidate_evidence_v3(endpoint_id text primary key references cycle_records,record_json text)')
    c.execute('insert into cycle_candidate_evidence_v3 values(?,?)',(eid,dump(evidence)))
    s=read(OUT/'summary.json');s.update(confirmed_cycle_material_links=c.execute('select count(*)from cycle_material_links').fetchone()[0],new_existing_cycle_material_links=1,main3e_material_links=17)
    c.execute("update metadata set value_json=?where key='summary'",(dump(s),));c.commit();c.close();write(OUT/'summary.json',s);write(OUT/'cycle_candidate_evidence.json',evidence)
    p=read(OUT/'entrypoint_snapshot.json');p['sha256']=sha(DB);write(OUT/'entrypoint_snapshot.json',p);write(ROOT/'data/current_training_ready.json',p)
    print('Existing candidate identity linked; cycling labels/admissions unchanged.')

if __name__=='__main__':link()
