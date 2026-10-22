"""Build a new fill-only parameter delta; preserve targets, membership and holds."""
from pathlib import Path
from contextlib import closing
import collections,copy,hashlib,importlib.util,json,sqlite3,sys
import pypdfium2 as P
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'tools')]
PARENT=ROOT/'循环稳定性数据库_v0.13_冲突复核_20261022'
OUT=ROOT/'循环稳定性数据库_v0.14_主集参数精提取_20261022';BATCH=ROOT/'主集参数精提取_20261022'
PARENT_SHA='6e6d349df83bb53ac944546b8c42c73d7ab043e1cce40abac85cdaaf1fddf973'
from training_input_quality import assess
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(p.read_text('utf-8'))
def dump(v):return json.dumps(v,ensure_ascii=False,sort_keys=True)
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n','utf-8')
def module(path,name):
    sp=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(sp);sys.modules[name]=m;sp.loader.exec_module(m);return m

def main():
    path=OUT/'cycling_v0_14.sqlite'
    if path.exists():raise FileExistsError('No overwrite of a published or existing build.')
    assert sha(PARENT/'cycling_v0_13.sqlite')==PARENT_SHA
    reviews=read(BATCH/'reviewed_parameters.json');assert reviews['reviewed_sources']==30 and len(reviews['records'])==42
    parent=module(PARENT/'ml_data.py','_v014_build_parent')
    with parent.Database() as db:
        original={r['endpoint_id']:r for r in db.fetch('all_review').rows};contract=copy.deepcopy(db.contract)
        assert {r['endpoint_id'] for r in db.fetch().rows}=={r['endpoint_id'] for r in reviews['records']}
    rows=copy.deepcopy(original);changes={};materials={};fields=set();numeric=set();agreement=[]
    for review in reviews['records']:
        key=review['endpoint_id'];mkey=review['material_key']
        assert original[key]['material_key_v11']==mkey
        for scope,updates in [('material',review['material_updates']),('test',review['test_updates'])]:
            for field,value in updates.items():
                fields.add(field)
                if isinstance(value,(int,float)) and not isinstance(value,bool):numeric.add(field)
                evidence=[e for e in review['evidence'] if field in e['fields']]
                assert evidence,(key,field)
                for e in evidence:assert sha(ROOT/e['path'])==e['sha256']
                targets=[k for k,r in original.items() if r.get('material_key_v11')==mkey] if scope=='material' else [key]
                for target in targets:
                    before=original[target].get(field)
                    if before is not None:
                        if before!=value:raise ValueError('Existing nonempty field conflicts; review instead of overwrite: '+str((target,field,before,value)))
                        agreement.append(dict(endpoint_id=target,field=field,value=value));continue
                    change=dict(endpoint_id=target,field_name=field,before=None,after=value,scope=scope,material_key=mkey,
                        reviewed_endpoint=key,evidence=evidence,reason=' '.join(review['notes']))
                    ck=(target,field)
                    if ck in changes and changes[ck]['after']!=value:raise ValueError('Conflicting same-material fill.')
                    changes[ck]=change;rows[target][field]=value
                if scope=='material':
                    mk=(mkey,field)
                    if mk in materials and materials[mk]['value']!=value:raise ValueError('Material evidence conflict.')
                    materials[mk]=dict(material_key=mkey,field_name=field,value=value,evidence=evidence)
    # Material equality agreement is useful evidence even if a prior version already selected it.
    process_features=sorted(numeric-set(contract['core_features'])-set(contract['model_material_features']))
    contract.update(version='v0.14',database_file=path.name,parent_directory=PARENT.name,parent_database_sha256=PARENT_SHA,
        storage_layout='Small fill-only parameter delta over immutable v0.13; main corpus reused.',parameter_fields_v14=sorted(fields),
        process_feature_fields_v14=process_features,
        extra_material_feature_whitelist=list(dict.fromkeys(contract['extra_material_feature_whitelist']+process_features)),
        process_field_semantics_v14={'heating_rate_C_min':'activation-stage ramp only; other thermal ramps use qualified fields',
            'activation_duration_h':'reported activation exposure; microwave total time explicitly tagged, not silently called a furnace hold',
            'mass_loading_mg_cm2':'author point/nominal value or explicit active mass divided by stated coated area; no range midpoint/unknown delivery volume'},
        preparation_only=True,model_fits=0,all_records_admitted=False)
    write(OUT/'data_contract.json',contract)
    with closing(sqlite3.connect(path)) as db:
        db.execute('pragma foreign_keys=on')
        db.executescript('''
        create table record_keys_v14(endpoint_id text primary key);
        create table reviewed_parameters_v14(endpoint_id text primary key references record_keys_v14,review_json text not null);
        create table parameter_changes_v14(endpoint_id text references record_keys_v14,field_name text,before_json text,after_json text,scope text,material_key text,reviewed_endpoint text references record_keys_v14,evidence_json text,reason text,primary key(endpoint_id,field_name));
        create table material_parameters_v14(material_key text,field_name text,value_json text,evidence_json text,primary key(material_key,field_name));
        create table rebound_segments_v14(segment_id integer primary key,doi text,path text,sha256 text,locator text,text text);
        ''')
        db.executemany('insert into record_keys_v14 values(?)',[(k,) for k in original])
        db.executemany('insert into reviewed_parameters_v14 values(?,?)',[(r['endpoint_id'],dump(r)) for r in reviews['records']])
        db.executemany('insert into parameter_changes_v14 values(?,?,?,?,?,?,?,?,?)',[(c['endpoint_id'],c['field_name'],dump(c['before']),dump(c['after']),c['scope'],c['material_key'],c['reviewed_endpoint'],dump(c['evidence']),c['reason']) for c in changes.values()])
        db.executemany('insert into material_parameters_v14 values(?,?,?,?)',[(m['material_key'],m['field_name'],dump(m['value']),dump(m['evidence'])) for m in materials.values()])
        for entry in read(BATCH/'supplement_access.json'):
            if not entry['identity_verified']:continue
            for f in entry.get('files',[]):
                assert sha(ROOT/f['path'])==f['sha256'];doc=P.PdfDocument(ROOT/f['path'])
                for n in range(len(doc)):
                    pg=doc[n];tp=pg.get_textpage();t=tp.get_text_range();tp.close();pg.close()
                    db.execute('insert into rebound_segments_v14(doi,path,sha256,locator,text) values(?,?,?,?,?)',(entry['doi'],f['path'],f['sha256'],f'SI PDF p{n+1}',t))
                doc.close()
        db.commit();assert db.execute('pragma integrity_check').fetchone()[0]=='ok';assert not db.execute('pragma foreign_key_check').fetchall()
    write(BATCH/'field_changes.json',list(changes.values()));write(BATCH/'existing_value_agreements.json',agreement)
    api=module(OUT/'ml_data.py','_v014_build_api')
    with api.Database() as db:
        write(OUT/'training_readiness.json',{p:assess(db.fetch(p)) for p in contract['profiles']})
        write(OUT/'reported_3e_material_inputs.json',db.material_matrix())
        write(OUT/'reported_3e_process_inputs.json',db.material_matrix(extra_features=contract['model_material_features']+process_features))
        print(dump(dict(field_changes=len(changes),main_rows=len(db.fetch().rows),source_groups=len({r['source_group'] for r in db.fetch().rows}),
            enriched_endpoints=len({k for k,f in changes}),process_features=process_features,sha256=sha(path),model_fits=0)))
if __name__=='__main__':main()
