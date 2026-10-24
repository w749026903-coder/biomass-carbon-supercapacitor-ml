"""Build a new small v0.15 delta. Never changes baseline, originals or membership."""
from pathlib import Path
from contextlib import closing
import collections,copy,hashlib,importlib.util,json,sqlite3,sys
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'tools')]
from inspect_existing_sources_v015 import BATCH,SNAPSHOT,read,sha
PARENT=ROOT/'循环稳定性数据库_v0.14_主集参数精提取_20261022'
OUT=ROOT/'循环稳定性数据库_v0.15_表图与待补证复核_20261024'
def dump(x):return json.dumps(x,ensure_ascii=False,sort_keys=True)
def write(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n','utf-8')
def module(p,n):
    s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);sys.modules[n]=m;s.loader.exec_module(m);return m
def main():
    path=OUT/'cycling_v0_15.sqlite'
    if path.exists():raise FileExistsError('Sealed output exists; do not rebuild in place.')
    snapshot=read(SNAPSHOT);curation=read(BATCH/'reviewed_curation.json')
    assert sha(PARENT/'cycling_v0_14.sqlite')==snapshot['parent_pointer']['sha256']
    old=module(PARENT/'ml_data.py','_v015_build_parent')
    with old.Database() as db:rows={r['endpoint_id']:r for r in db.fetch('all_review').rows};contract=copy.deepcopy(db.contract)
    protected={}
    for p in snapshot['papers']:
        for s in p['sources']:
            f=Path(s['path']);f=f if f.is_absolute() else ROOT/f
            assert sha(f)==s['sha256'];protected[s['path']]=s['sha256']
    changes={};materials={};fields=set();numeric=set()
    # Correction is explicitly limited to mistaken EDS-to-XPS mapping for ALPC-800.
    allowed_corrections={(k,f) for k,r in rows.items() if r['sample_name']=='ALPC-800' for f in ['XPS_N_reported_pct','XPS_O_reported_pct']}
    for c in curation['selections']:
        field=c['field_name'];value=c['after'];key=c['endpoint_id'];mkey=c['material_key']
        assert rows[key]['material_key_v11']==mkey
        fields.add(field)
        if isinstance(value,(int,float)) and not isinstance(value,bool):numeric.add(field)
        targets=[k for k,r in rows.items() if r['material_key_v11']==mkey] if c['scope']=='material' else [key]
        for target in targets:
            before=rows[target].get(field)
            if before==value:continue
            if before is not None:
                assert (target,field) in allowed_corrections and c['operation']=='correct_measurement_method'
                assert (field,before,value) in [('XPS_N_reported_pct',11.23,4.64),('XPS_O_reported_pct',8.54,7.44)]
            for e in c['evidence']:
                f=Path(e['path']);f=f if f.is_absolute() else ROOT/f
                assert field in e['fields'] and sha(f)==e['sha256']
            ck=(target,field);change={**c,'endpoint_id':target,'reviewed_endpoint':key,'before':before}
            if ck in changes:assert changes[ck]['after']==value
            changes[ck]=change
        if c['scope']=='material':
            mk=(mkey,field)
            if mk in materials:assert materials[mk]['after']==value
            materials[mk]=c
    additional_numeric=sorted(numeric-set(contract['extra_material_feature_whitelist']))
    contract.update(version='v0.15',database_file=path.name,parent_directory=PARENT.name,parent_database_sha256=snapshot['parent_pointer']['sha256'],
        storage_layout='Small table/figure evidence delta over immutable v0.14; no corpus copy.',
        field_names_v15=sorted(fields),new_numeric_candidates_v15=additional_numeric,
        extra_material_feature_whitelist=list(dict.fromkeys(contract['extra_material_feature_whitelist']+additional_numeric)),
        reviewed_pending_batch_size_v15=41,model_fits=0,preparation_only=True,all_records_admitted=False,
        field_semantics_v15={'XPS_percentage_basis':'atomic_explicit / weight_explicit / not_explicitly_reported; method and basis must not be pooled silently',
            'ALPC_800':'Explicit XPS N4.64/O7.44at%; historical N_at_pct/O_at_pct refer to EDS11.23/8.54 and carry method metadata.',
            'pore_conflict_candidates_v15':'raw conflicting ALPC micropore values, excluded from canonical numeric channels',
            'Raman_ID_IG':'RSM-0.33-550 derived reciprocal of author-labelled IG/ID1.292',
            'water_contact_angle_deg_v15':'candidate, measurement timing/protocol differs across sources; KAC58.25deg is at70ms, not equilibrium'} )
    write(OUT/'data_contract.json',contract)
    with closing(sqlite3.connect(path)) as c:
        c.execute('pragma foreign_keys=on')
        c.executescript('''
        create table record_keys_v15(endpoint_id text primary key);
        create table field_changes_v15(endpoint_id text references record_keys_v15,field_name text,before_json text,after_json text,operation text,scope text,material_key text,reviewed_endpoint text references record_keys_v15,evidence_json text,reason text,primary key(endpoint_id,field_name));
        create table material_fields_v15(material_key text,field_name text,value_json text,evidence_json text,primary key(material_key,field_name));
        create table pending_reviews_v15(endpoint_id text primary key references record_keys_v15,review_json text not null);
        ''')
        c.executemany('insert into record_keys_v15 values(?)',[(k,) for k in rows])
        c.executemany('insert into field_changes_v15 values(?,?,?,?,?,?,?,?,?,?)',[(x['endpoint_id'],x['field_name'],dump(x['before']),dump(x['after']),x['operation'],x['scope'],x['material_key'],x['reviewed_endpoint'],dump(x['evidence']),x['reason']) for x in changes.values()])
        c.executemany('insert into material_fields_v15 values(?,?,?,?)',[(k,f,dump(v['after']),dump(v['evidence'])) for (k,f),v in materials.items()])
        c.executemany('insert into pending_reviews_v15 values(?,?)',[(r['endpoint_id'],dump(r)) for r in curation['pending_reviews']])
        c.commit();assert c.execute('pragma integrity_check').fetchone()[0]=='ok';assert not c.execute('pragma foreign_key_check').fetchall()
    write(BATCH/'field_changes.json',list(changes.values()));write(BATCH/'protected_sources.json',protected)
    write(BATCH/'task_plan.json',dict(parent_version='v0.14',fixed_main_cohort={'tests':42,'source_groups':30},fixed_pending={'tests':41,'source_groups':27},
        scope='Existing local tables/figures/SI; evidence-reviewed descriptor fills, explicit method correction and disposition review.',
        raw_sources_immutable=True,targets_and_membership_immutable=True,model_fits=0,training_authorized_in_this_batch=False,
        validation=['source hashes','sealed parent payloads','SQLite/FK','all original fields/values','correction allowlist','holds history','source groups/weights','training-only preprocessing','fixed18-field coverage']))
    print(dump(dict(changes=len(changes),endpoints=len({k for k,f in changes}),material_fields=len(materials),corrections=sum(c['before'] is not None for c in changes.values()),sha256=sha(path))))
def finalize_evidence_locators():
    """Refine review locators in this unsealed draft; no scientific field mutation."""
    if (OUT/'merge_manifest.json').exists():raise RuntimeError('Release already sealed; no in-place editing.')
    history={}
    for p in [ROOT/'待补证原文复核_20261022/effective_reviews.json',ROOT/'冲突复核与来源充分性_20261022/effective_reviews.json']:
        history.update({c['endpoint_id']:c for c in read(p)})
    document=read(BATCH/'reviewed_curation.json');ledger=[]
    for c in document['pending_reviews']:
        key=c['endpoint_id']
        if c['disposition'].startswith('outside_'):continue
        if c['disposition'].startswith('partly_'):
            evs=[e for s in document['selections'] if s['endpoint_id']==key for e in s['evidence']]
        else:evs=history[key]['evidence']
        seen=set();precise=[]
        for e in evs:
            identity=(e['path'],e['locator'])
            if identity in seen:continue
            seen.add(identity);precise.append({**e,'fields':['review_disposition_v15']})
        assert precise,key
        ledger.append(dict(endpoint_id=key,previous_evidence=c['evidence'],refined_evidence=precise,
            operation='Precise locator reconciliation only; values, reason, issues and admission unchanged.'))
        c['evidence']=precise
    with closing(sqlite3.connect(OUT/'cycling_v0_15.sqlite')) as con:
        for c in document['pending_reviews']:con.execute('update pending_reviews_v15 set review_json=? where endpoint_id=?',(dump(c),c['endpoint_id']))
        con.commit()
    write(BATCH/'reviewed_curation.json',document);write(BATCH/'evidence_locator_refinement.json',ledger)
    print(dump(dict(refined_reviews=len(ledger),scientific_field_changes=0,draft_database_sha256=sha(OUT/'cycling_v0_15.sqlite'))))
if __name__=='__main__':
    if '--finalize-evidence-locators' in sys.argv:finalize_evidence_locators()
    else:main()
