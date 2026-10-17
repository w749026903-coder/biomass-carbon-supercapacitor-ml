"""Read-only profile loading. Reported current is never silently harmonized."""
import importlib.util
import json
import math
import pathlib
import sqlite3

ROOT=pathlib.Path(__file__).resolve().parents[1]
CONTRACT=json.loads((ROOT/'modeling/model_contract.json').read_text('utf-8'))

def database_path(config=None):return ROOT/(config or CONTRACT)['database_file']

def connect():
    c=sqlite3.connect(database_path().as_uri()+'?mode=ro',uri=True)
    c.row_factory=sqlite3.Row
    return c

def canonicalize_concentration(row):
    unit=str(row.get('concentration_unit') or '').strip().replace(' ','')
    factors={'M':1.,'mol/L':1.,'mol/l':1.,'molL-1':1.,'mol·L−1':1.,'mM':.001,'mmol/L':.001,'mmol/l':.001}
    if unit not in factors:
        raise ValueError('Molar concentration required; m/mol/kg cannot be converted without evidence')
    value=row.get('concentration_value')
    if type(value) not in (int,float) or not math.isfinite(value) or value<=0:
        raise ValueError('Finite positive concentration required')
    row.setdefault('reported_concentration_value',value)
    row.setdefault('reported_concentration_unit',row.get('concentration_unit'))
    row['concentration_value']=value*factors[unit]
    row['concentration_unit']='mol/L'
    row['electrolyte']={'sodium_acetate':'CH3COONa','potassium_hydroxide':'KOH'}.get(row.get('electrolyte'),row.get('electrolyte'))
    return row

def validate_rows(rows,config=None,require_admission=True):
    cfg=config or CONTRACT
    seen=set(); profiles=set()
    maps={k:{} for k in ['paper_id','material_id','cycle_test_id']}
    for r in rows:
        canonicalize_concentration(r)
        if not r.get('record_id') or r['record_id'] in seen:raise ValueError('Missing/duplicate endpoint')
        seen.add(r['record_id'])
        profile=r.get('profile',cfg['default_profile']);profiles.add(profile)
        if profile not in cfg['label_relations_by_profile']:raise ValueError('Unknown admission profile')
        if require_admission:
            if r.get('eligible')!=1 or r.get('admission_status')!='approved_for_declared_profile':raise ValueError('Profile admission required')
            if r.get('current_input_semantics')!='author_reported_protocol_descriptor':raise ValueError('Reported-current meaning required')
            if r.get('reported_current_A_g')!=r.get('current_density_A_g'):raise ValueError('Reported current must remain unchanged')
            if r.get('validation_group_id')!=r.get('study_group'):raise ValueError('Source group mismatch')
            if r.get('current_denominator_status')!='not_uniquely_defined' or r.get('canonical_current_A_g') is not None:
                raise ValueError('This revision must preserve unresolved denominator and empty canonical current')
        if r.get('system')!=cfg['primary_system'] or r.get('method')!=cfg['method'] or r.get('conflict'):
            raise ValueError('Outside reviewed symmetric GCD protocol')
        if r.get('retention_relation') not in cfg['label_relations_by_profile'][profile]:raise ValueError('Label precision outside profile')
        for key in cfg['required_conditions']+cfg['primary_required_material_features']+['retention_pct']:
            v=r.get(key)
            if key in cfg['categorical_features']:
                if not isinstance(v,str) or not v.strip():raise ValueError('Missing category:'+key)
            elif type(v) not in (int,float) or not math.isfinite(v):raise ValueError('Missing/invalid numeric:'+key)
        if r['cycle_count']<cfg['screening_min_cycles'] or int(r['cycle_count'])!=r['cycle_count']:raise ValueError('Invalid cycle count')
        if r['retention_pct']<0 or r['reported_current_A_g']<=0 or r['BET_m2_g']<=0:raise ValueError('Invalid physical input/target')
        if r['voltage_upper_V']<=r['voltage_lower_V']:raise ValueError('Invalid device voltage interval')
        pore=r.get('total_pore_volume_cm3_g')
        if pore is not None and (type(pore) not in (int,float) or not math.isfinite(pore) or pore<=0):raise ValueError('Invalid optional total pore')
        if not r.get('study_group'):raise ValueError('Source group missing')
        for key,mapping in maps.items():
            identity=r.get(key)
            if not identity:raise ValueError('Identity required:'+key)
            if identity in mapping and mapping[identity]!=r['study_group']:raise ValueError('Shared identity split between groups')
            mapping[identity]=r['study_group']
        r['log10_cycle_count']=math.log10(r['cycle_count'])
    if len(profiles)>1:raise ValueError('Nested profiles must be evaluated separately; do not stack duplicate endpoints')
    return rows

def normalized_doi(value):
    value=(value or '').strip().lower()
    for prefix in ['https://doi.org/','http://doi.org/','https://dx.doi.org/','http://dx.doi.org/','doi:']:
        if value.startswith(prefix):return value[len(prefix):].strip()
    return value

def validate_link_groups(c,rows):
    byid={r['record_id']:r for r in rows}
    bydoi={normalized_doi(r['doi']):r['study_group'] for r in c.execute('SELECT doi,study_group FROM papers') if r['doi']}
    for link in c.execute('SELECT * FROM validation_links'):
        if link['status']=='resolved_independent':continue
        a,b=byid.get(link['record_a']),byid.get(link['record_b'])
        if a and b and a['study_group']!=b['study_group']:raise ValueError('Linked endpoints split between groups')
        related=bydoi.get(normalized_doi(link['related_doi']))
        if a and related and related!=a['study_group']:raise ValueError('Predecessor relationship unresolved')

def load_ready(profile=None):
    profile=profile or CONTRACT['default_profile']
    if profile not in CONTRACT['label_relations_by_profile']:raise ValueError('Unknown admission profile')
    with connect() as c:
        rows=[dict(r) for r in c.execute('SELECT * FROM training_rows_r4 WHERE profile=? ORDER BY study_group,material_id,cycle_count,record_id',(profile,))]
        validate_link_groups(c,rows)
        for rel in c.execute("SELECT p.study_group AS a,q.study_group AS b FROM source_relationships r JOIN papers p ON p.paper_id=r.paper_id JOIN papers q ON q.paper_id=r.related_paper_id WHERE r.relationship='reuses_underlying_secondary_dataset'"):
            if rel['a']!=rel['b']:raise ValueError('Known reused-source groups must be united')
    return validate_rows(rows)

def preflight():
    profiles={}
    for profile in CONTRACT['label_relations_by_profile']:
        rows=load_ready(profile)
        profiles[profile]={'endpoints':len(rows),'papers':len({r['paper_id'] for r in rows}),
                           'materials':len({r['material_id'] for r in rows}),
                           'tests':len({r['cycle_test_id'] for r in rows}),
                           'source_groups':len({r['study_group'] for r in rows}),
                           'unknown_current_denominator':sum(r['current_denominator_status']=='not_uniquely_defined' for r in rows),
                           'approximate_labels':sum(r['retention_relation']=='approx' for r in rows),
                           'missing_optional_pore':sum(r['total_pore_volume_cm3_g'] is None for r in rows)}
    with connect() as c:
        canonical=c.execute('SELECT COUNT(*) FROM training_ready_canonical_current').fetchone()[0]
    return {'status':'data_ready_for_exploratory_reported_protocol_regression',
            'default_profile':CONTRACT['default_profile'],'profiles_nested_not_additive':profiles,
            'canonical_current_ready':canonical,'dependencies':{n:importlib.util.find_spec(n) is not None for n in ['numpy','sklearn','xgboost']},
            'research_training_performed':False,'small_sample_accuracy_claim_supported':False,
            'limitation':'Current is an uncalibrated literature descriptor; source grouping cannot remove physical denominator uncertainty.'}

if __name__=='__main__':print(json.dumps(preflight(),ensure_ascii=False,indent=2))
