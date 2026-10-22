"""Create a new small conflict-review overlay; no old rebuild, pointer update or fit."""
from pathlib import Path
from contextlib import closing
import copy,hashlib,importlib.util,json,sqlite3,sys,xml.etree.ElementTree as E,zipfile
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'tools')]
OUT=ROOT/'循环稳定性数据库_v0.13_冲突复核_20261022'
BATCH=ROOT/'冲突复核与来源充分性_20261022'
PARENT=ROOT/'循环稳定性数据库_v0.12_待补证精细复核_20261022'
PARENT_SHA='c5bb8878dd3dd117514b4caa601bfffd110534d61f56d828fd498a0e53075884'
from training_input_quality import assess
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def dump(v):return json.dumps(v,ensure_ascii=False,sort_keys=True)
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n','utf-8')
def module(path,name):
    sp=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(sp);sys.modules[name]=m;sp.loader.exec_module(m);return m

def main():
    target=OUT/'cycling_v0_13.sqlite'
    if target.exists():raise FileExistsError('Never overwrite a release.')
    assert sha(PARENT/'cycling_v0_12.sqlite')==PARENT_SHA
    parent=module(PARENT/'ml_data.py','_v013_build_parent')
    cases=json.loads((BATCH/'reviewed_cases.json').read_text('utf-8'))['cases']
    assert len({c['endpoint_id'] for c in cases})==len(cases)==16
    with parent.Database() as db:
        original={r['endpoint_id']:r for r in db.fetch('all_review').rows}
        memberships={p:{r['endpoint_id'] for r in db.fetch(p).rows} for p in db.contract['profiles']}
        contract=copy.deepcopy(db.contract)
        for c in cases:c['previous_holds']=db.holds(c['endpoint_id'])
    rows=copy.deepcopy(original);changes=[];material_changes=[]
    material_fields={'total_pore_volume_cm3_g','micropore_volume_cm3_g','mesopore_volume_cm3_g','micropore_surface_area_m2_g','average_pore_diameter_nm','Raman_ID_IG'}
    protected=json.loads((BATCH/'protected_sources.json').read_text('utf-8'))
    for path,h in protected.items():assert sha(ROOT/path)==h,path
    for c in cases:
        key=c['endpoint_id'];c['before']=copy.deepcopy(original[key]);row=rows[key]
        for f,v in c['changes'].items():
            ev=[e for e in c['evidence'] if f in e['fields']]
            assert ev,('Changed field without direct evidence',key,f)
            if row.get(f)!=v:
                changes.append(dict(endpoint_id=key,field_name=f,before=row.get(f),after=v,evidence=ev,reason=c['reason']))
                row[f]=copy.deepcopy(v);row[f+'_status']='v013_agent_original_source_adjudication'
                if f in material_fields:material_changes.append(dict(material_key=row['material_key_v11'],field_name=f,value=v,evidence=ev))
        for p,ids in memberships.items():
            ids.discard(key)
            if p in c['approved_profiles']:ids.add(key)
        row.update(review_disposition_v13=c['disposition'],review_reason_v13=c['reason'])
        if c['approved_profiles']:row.update(eligible=1,admission_status='approved_for_reported_protocol')
        c['after']=copy.deepcopy(row)
    contract.update(version='v0.13',database_file=target.name,parent_database_sha256=PARENT_SHA,parent_directory=PARENT.name,
        storage_layout='Immutable v0.12 plus 16 adjudicated row snapshots and small SI; large native index reused.',
        baseline_table_rule='Own cycling-retention column plus common own protocol accepted for reported-protocol purpose; exact baseline index/normalization stays unknown; no per-sample figure requirement.',
        all_records_admitted=False,preparation_only=True)
    write(OUT/'data_contract.json',contract)
    with closing(sqlite3.connect(target)) as db:
        db.execute('pragma foreign_keys=on')
        db.executescript('''
        create table reviewed_rows_v13(endpoint_id text primary key,row_json text not null);
        create table record_keys_v13(endpoint_id text primary key);
        create table profile_membership_v13(profile text,endpoint_id text references record_keys_v13,primary key(profile,endpoint_id));
        create table test_reviews_v13(endpoint_id text primary key references reviewed_rows_v13,review_json text not null);
        create table field_changes_v13(endpoint_id text references reviewed_rows_v13,field_name text,before_json text,after_json text,evidence_json text,reason text,primary key(endpoint_id,field_name));
        create table material_changes_v13(material_key text,field_name text,value_json text,evidence_json text,primary key(material_key,field_name));
        create table supplement_segments_v13(segment_id integer primary key,doi text,path text,sha256 text,locator text,text text);
        create table supplement_table_rows_v13(row_id integer primary key,doi text,path text,sha256 text,table_ordinal integer,row_ordinal integer,cells_json text,row_text text);
        ''')
        db.executemany('insert into record_keys_v13 values(?)',[(k,) for k in rows])
        db.executemany('insert into reviewed_rows_v13 values(?,?)',[(c['endpoint_id'],dump(c['after'])) for c in cases])
        db.executemany('insert into test_reviews_v13 values(?,?)',[(c['endpoint_id'],dump(c)) for c in cases])
        db.executemany('insert into profile_membership_v13 values(?,?)',[(p,k) for p,ids in memberships.items() for k in sorted(ids)])
        db.executemany('insert into field_changes_v13 values(?,?,?,?,?,?)',[(c['endpoint_id'],c['field_name'],dump(c['before']),dump(c['after']),dump(c['evidence']),c['reason']) for c in changes])
        db.executemany('insert into material_changes_v13 values(?,?,?,?)',[(c['material_key'],c['field_name'],dump(c['value']),dump(c['evidence'])) for c in material_changes])
        si=next(p for p in protected if p.endswith('LCC_LCNC_mmc1.docx'))
        ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
        with zipfile.ZipFile(ROOT/si) as z:root=E.fromstring(z.read('word/document.xml'))
        ordinal=0
        for i,block in enumerate(root.find('w:body',ns)):
            text=' '.join(t.text or '' for t in block.findall('.//w:t',ns))
            if text:db.execute('insert into supplement_segments_v13(doi,path,sha256,locator,text) values(?,?,?,?,?)',('10.1016/j.indcrop.2026.123626',si,protected[si],f'Word body block {i+1}',text))
            if block.tag.endswith('}tbl'):
                ordinal+=1
                for j,tr in enumerate(block.findall('w:tr',ns)):
                    cells=[' '.join(t.text or '' for t in tc.findall('.//w:t',ns)) for tc in tr.findall('w:tc',ns)]
                    db.execute('insert into supplement_table_rows_v13(doi,path,sha256,table_ordinal,row_ordinal,cells_json,row_text) values(?,?,?,?,?,?,?)',('10.1016/j.indcrop.2026.123626',si,protected[si],ordinal,j+1,dump(cells),' | '.join(cells)))
        db.commit()
        assert db.execute('pragma integrity_check').fetchone()[0]=='ok'
        assert not db.execute('pragma foreign_key_check').fetchall()
    write(BATCH/'effective_reviews.json',cases);write(BATCH/'field_changes.json',changes)
    api=module(OUT/'ml_data.py','_v013_build_api')
    with api.Database() as db:
        readiness={p:assess(db.fetch(p)) for p in contract['profiles']}
        write(OUT/'training_readiness.json',readiness)
        write(OUT/'reported_3e_material_inputs.json',db.material_matrix())
        write(OUT/'all_profile_inputs.json',{p:db.fetch(p).feature_matrix() for p in contract['profiles']})
        print(dump(dict(rows=len(db.fetch('all_review').rows),changes=len(changes),cohorts={p:[r['rows'],r['source_groups']] for p,r in readiness.items()},model_fits=0,sha256=sha(target))))
if __name__=='__main__':main()
