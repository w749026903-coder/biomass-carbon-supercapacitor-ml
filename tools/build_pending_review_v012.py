"""Create a new, evidence-backed overlay after the fixed pending queue is reviewed.

No overwrite of sealed versions, no downloads, no model fitting or pointer promotion.
"""
from pathlib import Path
from contextlib import closing
import collections,copy,csv,hashlib,importlib.util,json,sqlite3,sys,xml.etree.ElementTree as ET,zipfile
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'循环稳定性数据库_v0.12_待补证精细复核_20261022'
BATCH=ROOT/'待补证原文复核_20261022'
PARENT=ROOT/'循环稳定性数据库_v0.11_全库复检与材料特征_20261021'
PARENT_SHA='5492ec9c8b321aa27af72273d60ffb32d4a26b986528cda27c28db2b3ad12322'
sys.path[:0]=[str(ROOT),str(ROOT/'tools')]
from training_input_quality import assess
from material_feature_inputs_v011 import prepare_material_fold

MATERIAL_FIELDS={'BET_m2_g','N_at_pct','O_at_pct','S_at_pct','P_at_pct','C_at_pct','XPS_N_reported_pct','XPS_O_reported_pct','XPS_percentage_basis',
 'total_pore_volume_cm3_g','micropore_volume_cm3_g','mesopore_volume_cm3_g','micropore_surface_area_m2_g','average_pore_diameter_nm',
 'Raman_ID_IG','XRD_d002_nm','activation_temperature_C','activation_duration_h','bulk_N_wt_pct','bulk_O_wt_pct','bulk_O_method'}

def read(p):return json.loads(p.read_text('utf-8'))
def dump(v):return json.dumps(v,ensure_ascii=False,sort_keys=True)
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n','utf-8')
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def module(path,name):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m

def build(preflight=False):
    if (OUT/'cycling_v0_12.sqlite').exists():raise FileExistsError('Existing v0.12 is immutable; never rebuild in place.')
    assert sha(PARENT/'cycling_v0_11.sqlite')==PARENT_SHA
    packet=read(BATCH/'original_review_packets.json');cases=read(BATCH/'reviewed_cases.json')['cases']
    fixed={r['endpoint_id'] for p in packet for r in p['rows']}
    assert len(fixed)==87 and len({c['endpoint_id'] for c in cases})==len(cases)
    coverage=fixed&{c['endpoint_id'] for c in cases}
    if not preflight and coverage!=fixed:raise ValueError('Review every fixed queue item before publication; still untouched: '+','.join(sorted(fixed-coverage)))
    parent=module(PARENT/'ml_data.py','_v012_build_parent')
    with parent.Database() as db:
        original={r['endpoint_id']:r for r in db.fetch('all_review').rows}
        memberships={p:{r['endpoint_id'] for r in db.fetch(p).rows} for p in db.contract['profiles']}
        contract=copy.deepcopy(db.contract)
        previous_holds={c['endpoint_id']:db.holds(c['endpoint_id']) for c in cases}
    rows=copy.deepcopy(original);changes=[];materials={};protected={}
    sensitivity=any('reported_3e_sensitivity' in c['approved_profiles'] for c in cases)
    if sensitivity:
        contract['profiles']['reported_3e_sensitivity']={'features':contract['core_features'],'system':'3E','relations':['eq','approx','derived_complement'],'nested_main':'reported_3e','nested_residue':'reported_3e_residue_sensitivity','year_min':2023,'year_max':2026,'use':'Explicit label/figure-reading sensitivity including the separately declared native-residue scope; neither author-exact labels nor main approval are inferred. No training run authorized.'}
        memberships['reported_3e_sensitivity']=set(memberships['reported_3e'])
    residue=any('reported_3e_residue_sensitivity' in c['approved_profiles'] for c in cases)
    if residue:
        contract['profiles']['reported_3e_residue_sensitivity']={'features':contract['core_features'],'system':'3E','relations':['eq'],'nested_main':'reported_3e','year_min':2023,'year_max':2026,'use':'Explicit native/residual Si scope sensitivity, following the existing separate 2E residue purpose; not main approval.'}
        memberships['reported_3e_residue_sensitivity']=set(memberships['reported_3e'])
    for case in cases:
        key=case['endpoint_id'];before=original[key];row=rows[key]
        case['before']=copy.deepcopy(before);case['previous_holds']=previous_holds[key]
        assert case['reason'] and case['evidence']
        for e in case['evidence']:
            p=ROOT/e['path'];assert sha(p)==e['sha256'],e['path'];protected[e['path']]=e['sha256']
        for field,value in case['changes'].items():
            targets=[key]
            if case.get('propagate_material_fields') and field in MATERIAL_FIELDS:
                targets=[k for k,r in rows.items() if r.get('material_key_v11')==before.get('material_key_v11')]
            for target in targets:
                old=rows[target].get(field)
                if old!=value:
                    changes.append({'endpoint_id':target,'field_name':field,'before':old,'after':value,'reason':case['reason'],'evidence':case['evidence'],'origin_review_endpoint':key})
                rows[target][field]=copy.deepcopy(value);rows[target][field+'_status']='v012_agent_original_source_review'
                if field in MATERIAL_FIELDS:
                    mkey=rows[target]['material_key_v11'];m=(mkey,field)
                    if m in materials and materials[m]['value']!=value:raise ValueError('Conflicting current material observations require explicit resolution: '+str(m))
                    materials[m]={'value':value,'evidence':case['evidence']}
        for p in memberships:
            if key in fixed:memberships[p].discard(key)
            if p in case['approved_profiles']:memberships[p].add(key)
        row['review_disposition_v12']=case['disposition'];row['review_reason_v12']=case['reason']
    if sensitivity:memberships['reported_3e_sensitivity']|=memberships['reported_3e']
    if residue:memberships['reported_3e_residue_sensitivity']|=memberships['reported_3e']
    if sensitivity and residue:memberships['reported_3e_sensitivity']|=memberships['reported_3e_residue_sensitivity']
    for key,row in rows.items():
        row.pop('source_weight',None)
        row['admission_profiles_v12']=[p for p,keys in memberships.items() if key in keys]
        if row['admission_profiles_v12']:
            row['eligible']=1;row['admission_status']='approved_for_reported_protocol'
        if key in fixed and not row['admission_profiles_v12']:row['eligible']=0
    for case in cases:
        case['approved_profiles']=rows[case['endpoint_id']]['admission_profiles_v12']
        case['after']=copy.deepcopy(rows[case['endpoint_id']])
    # Validate every proposed cohort before creating any new scientific payload.
    api_preview=module(OUT/'ml_data.py','_v012_preview_api')
    for profile,keys in memberships.items():
        selected=[copy.deepcopy(rows[k]) for k in sorted(keys)]
        counts=collections.Counter(r['source_group'] for r in selected)
        for row in selected:row['source_weight']=1/counts[row['source_group']]
        assess(api_preview.Dataset(profile,selected,list(contract['profiles'][profile]['features'])))
    if preflight:
        print(dump({'reviewed_queue_items':len(coverage),'untouched':sorted(fixed-coverage),'changes':len(changes),'cohorts':{p:len(k) for p,k in memberships.items()}}));return
    contract.update(version='v0.12',database_file='cycling_v0_12.sqlite',parent_database_sha256=PARENT_SHA,
        parent_directory=PARENT.name,storage_layout='Immutable v0.11 parent plus reviewed current snapshots and small evidence delta; original SI retained.',
        preparation_only=True,all_records_admitted=False,year_cohort_policy='Existing 2023-2026 main cohort is unchanged; older literature remains separately reviewed, not automatically trained.')
    write(OUT/'data_contract.json',contract)
    with closing(sqlite3.connect(OUT/'cycling_v0_12.sqlite')) as c:
        c.execute('pragma foreign_keys=on')
        c.executescript('''
        create table review_rows_v12(endpoint_id text primary key,row_json text not null);
        create table profile_membership_v12(profile text,endpoint_id text references review_rows_v12,primary key(profile,endpoint_id));
        create table test_reviews_v12(endpoint_id text primary key references review_rows_v12,review_json text not null);
        create table field_changes_v12(endpoint_id text references review_rows_v12,field_name text,before_json text,after_json text,evidence_json text,reason text,primary key(endpoint_id,field_name));
        create table material_changes_v12(material_key text,field_name text,value_json text,evidence_json text,primary key(material_key,field_name));
        create table native_supplement_segments_v12(segment_id integer primary key,doi text,path text,sha256 text,locator text,text text,unique(sha256,locator));
        create virtual table native_supplement_fts_v12 using fts5(text,content='native_supplement_segments_v12',content_rowid='segment_id');
        create table native_tables_v12(table_id integer primary key,doi text,path text,sha256 text,table_ordinal integer,caption text,status text);
        create table native_table_rows_v12(row_id integer primary key,table_id integer references native_tables_v12,row_ordinal integer,cells_json text,row_text text);
        create virtual table native_table_fts_v12 using fts5(row_text,content='native_table_rows_v12',content_rowid='row_id');
        ''')
        c.executemany('insert into review_rows_v12 values(?,?)',[(k,dump(v)) for k,v in rows.items()])
        c.executemany('insert into profile_membership_v12 values(?,?)',[(p,k) for p,keys in memberships.items() for k in sorted(keys)])
        c.executemany('insert into test_reviews_v12 values(?,?)',[(c['endpoint_id'],dump(c)) for c in cases])
        c.executemany('insert into field_changes_v12 values(?,?,?,?,?,?)',[(r['endpoint_id'],r['field_name'],dump(r['before']),dump(r['after']),dump(r['evidence']),r['reason']) for r in changes])
        c.executemany('insert into material_changes_v12 values(?,?,?,?)',[(key,field,dump(o['value']),dump(o['evidence'])) for (key,field),o in materials.items()])
        for receipt in read(BATCH/'SI_identity_reviews.json'):
            assert receipt['identity_verified'] and sha(ROOT/receipt['si_path'])==receipt['si_sha256']
            protected[receipt['si_path']]=receipt['si_sha256']
            with zipfile.ZipFile(ROOT/receipt['si_path']) as z:doc=ET.fromstring(z.read('word/document.xml'))
            body=doc.find('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}body')
            table_ordinal=0;caption='';ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
            for i,block in enumerate(body):
                text=' '.join(e.text or '' for e in block.iter() if e.tag.endswith('}t'))
                if text.strip():c.execute('insert into native_supplement_segments_v12(doi,path,sha256,locator,text) values(?,?,?,?,?)',(receipt['doi'],receipt['si_path'],receipt['si_sha256'],'OOXML body block'+str(i),text))
                if block.tag.endswith('}p') and text.strip():caption=text
                if block.tag.endswith('}tbl'):
                    table_ordinal+=1
                    tid=c.execute('insert into native_tables_v12(doi,path,sha256,table_ordinal,caption,status) values(?,?,?,?,?,?)',(receipt['doi'],receipt['si_path'],receipt['si_sha256'],table_ordinal,caption,'raw_table_not_test_admission')).lastrowid
                    for ordinal,tr in enumerate(block.findall('w:tr',ns),1):
                        cells=[' '.join(t.text or '' for t in cell.findall('.//w:t',ns)) for cell in tr.findall('w:tc',ns)]
                        c.execute('insert into native_table_rows_v12(table_id,row_ordinal,cells_json,row_text) values(?,?,?,?)',(tid,ordinal,dump(cells),' | '.join(cells)))
        c.execute("insert into native_supplement_fts_v12(native_supplement_fts_v12) values('rebuild')");c.commit()
        c.execute("insert into native_table_fts_v12(native_table_fts_v12) values('rebuild')");c.commit()
        assert c.execute('pragma integrity_check').fetchone()[0]=='ok' and not c.execute('pragma foreign_key_check').fetchall()
    write(BATCH/'field_changes.json',changes);write(BATCH/'protected_sources.json',protected)
    write(BATCH/'effective_reviews.json',cases)
    api=module(OUT/'ml_data.py','_v012_built_api');summary={'version':'v0.12','model_fits':0,'reviewed_fixed_queue_items':87,'cohorts':{}}
    with api.Database() as db:
        for profile in contract['profiles']:
            ds=db.fetch(profile);matrix=ds.feature_matrix();report=assess(ds)
            summary['cohorts'][profile]=report
            write(OUT/(profile+'_inputs.json'),{'rows':ds.rows,'matrix':matrix,'fingerprint':ds.fingerprint(),'source_folds':ds.source_folds(len(set(matrix['groups'])))})
        mat=db.material_matrix();write(OUT/'reported_3e_material_inputs.json',mat)
        for fold in mat['source_folds']:
            prepared=prepare_material_fold(mat,fold);mut=copy.deepcopy(mat)
            for i in fold['test']:mut['y'][i]=99999;mut['X'][i]=['UNSEEN' if f in mat['categorical_features'] else 999999 for f in mat['feature_names']]
            other=prepare_material_fold(mut,fold)
            assert prepared['training_only_schema']==other['training_only_schema'] and prepared['X_train']==other['X_train']
        summary.update(field_changes=len(changes),material_observations=len(materials),pending_evidence=len(db.pending_evidence()),unadmitted_all_review=len(db.full_review_queue()))
    write(OUT/'training_readiness.json',summary)
    print(dump({'cohorts':{p:{'rows':v['rows'],'source_groups':v['source_groups']} for p,v in summary['cohorts'].items()},'model_fits':0}))

if __name__=='__main__':build('--preflight' in sys.argv)
