"""Read-only v0.13 delta; sealed v0.12 and its evidence remain unchanged."""
from pathlib import Path
import collections,hashlib,importlib.util,json,math,sqlite3,sys
ROOT=Path(__file__).resolve().parents[1]
PARENT=ROOT/'循环稳定性数据库_v0.12_待补证精细复核_20261022'
NAME='_cycling_v012_parent_for_v013'
if NAME not in sys.modules:
    spec=importlib.util.spec_from_file_location(NAME,PARENT/'ml_data.py')
    m=importlib.util.module_from_spec(spec);sys.modules[NAME]=m;spec.loader.exec_module(m)
base=sys.modules[NAME]
DataNotReady=base.DataNotReady

class Dataset(base.Dataset):
    def feature_matrix(self):
        if self.profile not in ['reported_3e','reported_3e_residue_sensitivity','reported_3e_sensitivity']:
            return super().feature_matrix()
        if not self.rows:raise DataNotReady('Empty reviewed cohort.')
        relations=['eq','approx','derived_complement'] if self.profile=='reported_3e_sensitivity' else ['eq']
        for row in self.rows:
            if row.get('system')!='3E' or row.get('method')!='GCD':raise DataNotReady('Wrong test system/method.')
            if row.get('eligible')!=1 or row.get('admission_status')!='approved_for_reported_protocol' or self.profile not in row.get('admission_profiles_v13',[]):raise DataNotReady('Current explicit admission required.')
            if row.get('metric_kind')!='capacitance_retention' or row.get('retention_relation') not in relations:raise DataNotReady('Wrong target or relation.')
            year=row.get('source_year')
            if year is None or not 2023<=year<=2026 or not isinstance(row.get('cycle_count'),(int,float)) or row['cycle_count']<1000:raise DataNotReady('Unchanged year/cycle cohort required.')
            if not row.get('baseline_reference'):raise DataNotReady('Reviewed author cycling reference required.')
            for f in self.features+['retention_pct']:
                v=row.get(f)
                if f in ['electrolyte','reference_electrode']:
                    if not isinstance(v,str) or not v.strip():raise DataNotReady('Missing categorical field: '+f)
                elif isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v):raise DataNotReady('Missing/invalid numeric field: '+f)
            if any(row[f]<=0 for f in ['cycle_count','reported_current_A_g','concentration_mol_L','BET_m2_g']):raise DataNotReady('Nonpositive core descriptor.')
            if row['cycle_voltage_upper_V']<=row['cycle_voltage_lower_V'] or row['retention_pct']<0:raise DataNotReady('Invalid voltage or target.')
        return dict(X=[[r[f] for f in self.features] for r in self.rows],y=[r['retention_pct'] for r in self.rows],
            groups=[r['source_group'] for r in self.rows],sample_weight=[r['source_weight'] for r in self.rows],
            feature_names=self.features,training_authorized=False,current_semantics='author_reported_protocol_descriptor',
            label_relations=[r['retention_relation'] for r in self.rows],
            label_evidence_kind=[r.get('baseline_evidence_kind_v13',r.get('retention_evidence_kind_v12','complement_of_author_reported_loss' if r['retention_relation']=='derived_complement' else 'author_reported')) for r in self.rows],
            label_reading_bound_pp=[r.get('retention_reading_bound_pp_v12') for r in self.rows],
            baseline_references=[r['baseline_reference'] for r in self.rows])

class Database(base.Database):
    def __init__(self,path=None):
        folder=Path(__file__).resolve().parent
        contract=json.loads((folder/'data_contract.json').read_text('utf-8'))
        with (PARENT/'cycling_v0_12.sqlite').open('rb') as f:
            if hashlib.file_digest(f,'sha256').hexdigest()!=contract['parent_database_sha256']:raise RuntimeError('Immutable v0.12 changed.')
        super().__init__(PARENT/'cycling_v0_12.sqlite')
        self.root=folder;self.contract=contract;self.path=Path(path).resolve() if path else folder/contract['database_file']
        self.delta_v13=sqlite3.connect(self.path.as_uri()+'?mode=ro',uri=True);self.delta_v13.row_factory=sqlite3.Row
        self.delta_v13.execute('pragma query_only=on')
        self.decisions_v13={r['endpoint_id']:json.loads(r['review_json']) for r in self.delta_v13.execute('select * from test_reviews_v13')}
        self.members_v13=collections.defaultdict(set)
        for r in self.delta_v13.execute('select * from profile_membership_v13'):self.members_v13[r['profile']].add(r['endpoint_id'])

    def close(self):
        if hasattr(self,'delta_v13'):self.delta_v13.close()
        super().close()

    def fetch(self,profile=None,year_min=None,year_max=None):
        if not hasattr(self,'delta_v13'):return super().fetch(profile,year_min,year_max)
        profile=profile or self.contract['default_profile']
        if profile not in self.contract['profiles'] and profile not in ['all_review','review_3e_all','incoming_review']:return super().fetch(profile,year_min,year_max)
        rows={r['endpoint_id']:r for r in super().fetch('all_review').rows}
        for r in self.delta_v13.execute('select * from reviewed_rows_v13'):rows[r['endpoint_id']]=json.loads(r['row_json'])
        result=[]
        for key,row in rows.items():
            row['admission_profiles_v13']=[p for p,ids in self.members_v13.items() if key in ids]
            if profile in self.contract['profiles'] and key not in self.members_v13[profile]:continue
            if profile=='review_3e_all' and row['system']!='3E':continue
            if profile=='incoming_review' and not key.startswith('incoming:'):continue
            if year_min is not None and (row.get('source_year') is None or row['source_year']<int(year_min)):continue
            if year_max is not None and (row.get('source_year') is None or row['source_year']>int(year_max)):continue
            result.append(row)
        counts=collections.Counter(r['source_group'] for r in result)
        for r in result:r['source_weight']=1/counts[r['source_group']]
        features=self.contract['profiles'][profile]['features'] if profile in self.contract['profiles'] else self.contract['core_features']
        return Dataset(profile,sorted(result,key=lambda r:(r['source_group'],r['endpoint_id'])),list(features))

    def by_endpoint(self,key):
        if not hasattr(self,'delta_v13'):return super().by_endpoint(key)
        r=self.delta_v13.execute('select row_json from reviewed_rows_v13 where endpoint_id=?',(key,)).fetchone()
        row=json.loads(r[0]) if r else super().by_endpoint(key)
        if row:
            row.pop('source_weight',None)
            row['admission_profiles_v13']=[p for p,ids in self.members_v13.items() if key in ids]
        return row

    def full_review_queue(self):return [r for r in self.fetch('all_review').rows if not r['admission_profiles_v13']]
    def pending_evidence(self):return [r for r in self.full_review_queue() if not str(r.get('review_disposition_v13',r.get('review_disposition_v12',''))).startswith('outside_')]

    def holds(self,key):
        old=super().holds(key)
        if not hasattr(self,'decisions_v13'):return old
        c=self.decisions_v13.get(key)
        if c:return dict(open_issues=c['open_issues'],approved_profiles=c['approved_profiles'],disposition=c['disposition'],
            reason=c['reason'],resolution=c['resolution'],previous_holds=old,review_version='v0.13')
        row=self.by_endpoint(key)
        return {**old,'approved_profiles_v13':row['admission_profiles_v13'] if row else []}

    def admission_checks(self,key,profile=None):
        if not hasattr(self,'delta_v13'):return super().admission_checks(key,profile)
        row=self.by_endpoint(key)
        return [dict(endpoint_id=key,profile=p,status='approved_for_reported_protocol' if row and p in row['admission_profiles_v13'] else 'not_approved',
            current_review=self.decisions_v13.get(key),historical_checks=super(Database,self).admission_checks(key,p),review_version='v0.13')
            for p in ([profile] if profile else self.contract['profiles'])]

    def evidence(self,key,field=None):
        old=super().evidence(key,field)
        if not hasattr(self,'delta_v13'):return old
        # Respect the original per-evidence fields list; summaries for another field are not direct support.
        if field:old=[e for e in old if not e.get('fields') or field in e['fields']]
        for r in self.delta_v13.execute('select * from field_changes_v13 where endpoint_id=?',(key,)):
            if field and field!=r['field_name']:continue
            for e in json.loads(r['evidence_json']):
                if r['field_name'] not in e['fields']:continue
                old.append(dict(endpoint_id=key,field_name=r['field_name'],value_json=r['after_json'],selected=1,
                    review_version='v0.13',excerpt_kind='agent_original_source_adjudication',**e))
        return old

    def material_properties(self,material_key=None,selected_only=True):
        old=super().material_properties(material_key,selected_only)
        if not hasattr(self,'delta_v13'):return old
        values=[dict(r) for r in self.delta_v13.execute('select * from material_changes_v13') if not material_key or r['material_key']==material_key]
        replaced={(r['material_key'],r['field_name']) for r in values}
        if selected_only:old=[r for r in old if (r['material_key'],r['field_name']) not in replaced]
        else:
            for r in old:
                if (r['material_key'],r['field_name']) in replaced:r['selected']=0;r['superseded_in_v13']=True
        for r in values:r.update(value=json.loads(r['value_json']),evidence=json.loads(r['evidence_json']),selected=1,
            review_version='v0.13',stage='before_cycling',applies_to_systems_json='[]')
        return old+values

    def search_native(self,query,doi=None,limit=10):
        previous=super().search_native(query,doi,limit)
        if not hasattr(self,'delta_v13') or not str(query).split():return previous
        words=str(query).lower().split();out=[]
        for raw in self.delta_v13.execute('select * from supplement_segments_v13'):
            r=dict(raw)
            if doi and r['doi']!=str(doi).lower().removeprefix('doi:').removeprefix('https://doi.org/'):continue
            if not all(w in r['text'].lower() for w in words):continue
            with (ROOT/r['path']).open('rb') as f:
                if hashlib.file_digest(f,'sha256').hexdigest()!=r['sha256']:raise RuntimeError('Supplement changed.')
            r.update(excerpt=r.pop('text')[:3500],training_eligible=0,status='native_search_match_not_test_admission');out.append(r)
        return (out+previous)[:int(limit)]

    def search_tables(self,query,doi=None,limit=20):
        previous=super().search_tables(query,doi,limit)
        if not hasattr(self,'delta_v13') or not str(query).split():return previous
        out=[];words=str(query).lower().split()
        for raw in self.delta_v13.execute('select * from supplement_table_rows_v13'):
            r=dict(raw)
            if doi and r['doi']!=str(doi).lower().removeprefix('doi:').removeprefix('https://doi.org/'):continue
            if all(w in r['row_text'].lower() for w in words):
                with (ROOT/r['path']).open('rb') as f:
                    if hashlib.file_digest(f,'sha256').hexdigest()!=r['sha256']:raise RuntimeError('Supplement changed.')
                r.update(training_eligible=0,status='raw_SI_table_not_automatic_admission');out.append(r)
        return (out+previous)[:int(limit)]
