"""Read-only parameter enrichment. Memberships, targets and holds remain in v0.13."""
from pathlib import Path
import collections,hashlib,importlib.util,json,sqlite3,sys
ROOT=Path(__file__).resolve().parents[1]
PARENT=ROOT/'循环稳定性数据库_v0.13_冲突复核_20261022'
NAME='_cycling_v013_parent_for_v014'
if NAME not in sys.modules:
    sp=importlib.util.spec_from_file_location(NAME,PARENT/'ml_data.py');m=importlib.util.module_from_spec(sp);sys.modules[NAME]=m;sp.loader.exec_module(m)
base=sys.modules[NAME];Dataset=base.Dataset;DataNotReady=base.DataNotReady

class Database(base.Database):
    def __init__(self,path=None):
        folder=Path(__file__).resolve().parent;contract=json.loads((folder/'data_contract.json').read_text('utf-8'))
        with (PARENT/'cycling_v0_13.sqlite').open('rb') as f:
            if hashlib.file_digest(f,'sha256').hexdigest()!=contract['parent_database_sha256']:raise RuntimeError('Immutable v0.13 changed.')
        super().__init__(PARENT/'cycling_v0_13.sqlite')
        self.root=folder;self.contract=contract;self.path=Path(path).resolve() if path else folder/contract['database_file']
        self.delta_v14=sqlite3.connect(self.path.as_uri()+'?mode=ro',uri=True);self.delta_v14.row_factory=sqlite3.Row;self.delta_v14.execute('pragma query_only=on')
        self.parameter_changes_v14=collections.defaultdict(list)
        for r in self.delta_v14.execute('select * from parameter_changes_v14 order by endpoint_id,field_name'):self.parameter_changes_v14[r['endpoint_id']].append(dict(r))

    def close(self):
        if hasattr(self,'delta_v14'):self.delta_v14.close()
        super().close()

    def _apply_parameters(self,row):
        if row is not None and hasattr(self,'parameter_changes_v14'):
            for c in self.parameter_changes_v14.get(row['endpoint_id'],[]):
                row[c['field_name']]=json.loads(c['after_json']);row[c['field_name']+'_status']='v014_agent_reviewed_precycling_source'
        return row

    def fetch(self,profile=None,year_min=None,year_max=None):
        ds=super().fetch(profile,year_min,year_max)
        for r in ds.rows:self._apply_parameters(r)
        return ds

    def by_endpoint(self,key):return self._apply_parameters(super().by_endpoint(key))

    def parameters(self,key):
        """Selected own-material/process and test-only parameters with direct evidence."""
        row=self.by_endpoint(key)
        if row is None:return None
        fields=self.contract['parameter_fields_v14']
        return dict(endpoint_id=key,values={f:row.get(f) for f in fields},
            changes=[{**c,'before':json.loads(c['before_json']),'after':json.loads(c['after_json']),'evidence':json.loads(c['evidence_json'])} for c in self.parameter_changes_v14.get(key,[])],
            admission_profiles=row['admission_profiles_v13'],model_fits=0)

    def material_properties(self,material_key=None,selected_only=True):
        previous=super().material_properties(material_key,selected_only)
        if not hasattr(self,'delta_v14') or getattr(self,'_reading_historical_evidence',False):return previous
        current=[dict(r) for r in self.delta_v14.execute('select * from material_parameters_v14') if not material_key or r['material_key']==material_key]
        keys={(r['material_key'],r['field_name']) for r in current}
        if selected_only:previous=[r for r in previous if (r['material_key'],r['field_name']) not in keys]
        else:
            for r in previous:
                if (r['material_key'],r['field_name']) in keys:r['selected']=0;r['superseded_in_v14']=True
        for r in current:r.update(value=json.loads(r['value_json']),evidence=json.loads(r['evidence_json']),selected=1,
            review_version='v0.14',stage='before_cycling',applies_to_systems_json='[]')
        return previous+current

    def evidence(self,key,field=None):
        # Parent evidence must see its own historical material selections.
        previous_flag=getattr(self,'_reading_historical_evidence',False)
        self._reading_historical_evidence=True
        try:old=super().evidence(key,field)
        finally:self._reading_historical_evidence=previous_flag
        if not hasattr(self,'parameter_changes_v14'):return old
        row=self.by_endpoint(key);selected=[]
        if row:
            for r in self.delta_v14.execute('select * from material_parameters_v14 where material_key=?',(row['material_key_v11'],)):
                if field and r['field_name']!=field:continue
                selected.append(dict(field_name=r['field_name'],after_json=r['value_json'],evidence_json=r['evidence_json']))
        selected+=self.parameter_changes_v14.get(key,[])
        seen=set()
        for c in selected:
            if field and c['field_name']!=field:continue
            for e in json.loads(c['evidence_json']):
                if c['field_name'] not in e['fields']:continue
                identity=(c['field_name'],e['path'],e['locator'],c['after_json'])
                if identity in seen:continue
                seen.add(identity)
                old.append(dict(endpoint_id=key,field_name=c['field_name'],value_json=c['after_json'],selected=1,
                    review_version='v0.14',excerpt_kind='agent_reviewed_own_parameter',**e))
        return old

    def search_native(self,query,doi=None,limit=10):
        previous=super().search_native(query,doi,limit)
        if not hasattr(self,'delta_v14') or not str(query).split():return previous
        out=[];words=str(query).lower().split()
        for raw in self.delta_v14.execute('select * from rebound_segments_v14'):
            r=dict(raw)
            if doi and r['doi']!=str(doi).lower().removeprefix('doi:').removeprefix('https://doi.org/'):continue
            if not all(w in r['text'].lower() for w in words):continue
            with (ROOT/r['path']).open('rb') as f:
                if hashlib.file_digest(f,'sha256').hexdigest()!=r['sha256']:raise RuntimeError('Rebound SI fingerprint changed.')
            r.update(excerpt=r.pop('text')[:3500],training_eligible=0,status='native_source_rebound_not_test_admission');out.append(r)
        return (out+previous)[:int(limit)]
