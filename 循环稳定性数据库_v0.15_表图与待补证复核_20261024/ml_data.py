"""Read-only v0.15 evidence delta over immutable v0.14; no model fitting."""
from pathlib import Path
import collections,hashlib,importlib.util,json,sqlite3,sys
ROOT=Path(__file__).resolve().parents[1]
PARENT=ROOT/'循环稳定性数据库_v0.14_主集参数精提取_20261022'
NAME='_cycling_v014_parent_for_v015'
if NAME not in sys.modules:
    spec=importlib.util.spec_from_file_location(NAME,PARENT/'ml_data.py')
    m=importlib.util.module_from_spec(spec);sys.modules[NAME]=m;spec.loader.exec_module(m)
base=sys.modules[NAME];Dataset=base.Dataset;DataNotReady=base.DataNotReady

class Database(base.Database):
    def __init__(self,path=None):
        folder=Path(__file__).resolve().parent;contract=json.loads((folder/'data_contract.json').read_text('utf-8'))
        with (PARENT/'cycling_v0_14.sqlite').open('rb') as f:
            if hashlib.file_digest(f,'sha256').hexdigest()!=contract['parent_database_sha256']:raise RuntimeError('Immutable v0.14 changed.')
        super().__init__(PARENT/'cycling_v0_14.sqlite')
        self.root=folder;self.contract=contract;self.path=Path(path).resolve() if path else folder/contract['database_file']
        self.delta_v15=sqlite3.connect(self.path.as_uri()+'?mode=ro',uri=True);self.delta_v15.row_factory=sqlite3.Row
        self.delta_v15.execute('pragma query_only=on')
        self.changes_v15=collections.defaultdict(list)
        for r in self.delta_v15.execute('select * from field_changes_v15 order by endpoint_id,field_name'):
            self.changes_v15[r['endpoint_id']].append(dict(r))
        self.reviews_v15={r['endpoint_id']:json.loads(r['review_json']) for r in self.delta_v15.execute('select * from pending_reviews_v15')}

    def close(self):
        if hasattr(self,'delta_v15'):self.delta_v15.close()
        super().close()

    def _apply_v15(self,row):
        if row is not None and hasattr(self,'changes_v15'):
            for c in self.changes_v15.get(row['endpoint_id'],[]):
                row[c['field_name']]=json.loads(c['after_json'])
                row[c['field_name']+'_status']='v015_original_source_'+c['operation']
            if row['endpoint_id'] in self.reviews_v15:
                row['review_disposition_v15']=self.reviews_v15[row['endpoint_id']]['disposition']
        return row

    def fetch(self,profile=None,year_min=None,year_max=None):
        ds=super().fetch(profile,year_min,year_max)
        for r in ds.rows:self._apply_v15(r)
        return ds

    def by_endpoint(self,key):return self._apply_v15(super().by_endpoint(key))

    def holds(self,key):
        old=super().holds(key)
        if not hasattr(self,'reviews_v15') or key not in self.reviews_v15:return old
        c=self.reviews_v15[key]
        return dict(open_issues=c['open_issues'],approved_profiles=c['approved_profiles'],disposition=c['disposition'],
            reason=c['reason'],resolution=c['resolution'],previous_holds=old,review_version='v0.15')

    def pending_evidence(self):
        return [r for r in self.full_review_queue() if not str(r.get('review_disposition_v15',r.get('review_disposition_v13',r.get('review_disposition_v12','')))).startswith('outside_')]

    def reviewed_pending_batch(self,include_outside=False):
        """Fixed 41-record batch; 39 remain pending after two scope decisions."""
        return [dict(c) for c in self.reviews_v15.values() if include_outside or not c['disposition'].startswith('outside_')]

    def admission_checks(self,key,profile=None):
        checks=super().admission_checks(key,profile)
        if hasattr(self,'reviews_v15') and key in self.reviews_v15:
            for c in checks:
                c['historical_v13_review']=c.get('current_review')
                c['current_review']=self.reviews_v15[key]
                c['review_version']='v0.15'
        return checks

    def field_changes(self,key=None):
        raw=[c for k,cs in self.changes_v15.items() for c in cs if key is None or k==key]
        return [{**c,'before':json.loads(c['before_json']),'after':json.loads(c['after_json']),'evidence':json.loads(c['evidence_json'])} for c in raw]

    def method_specific_material_matrix(self,profile=None):
        """Separate explicit XPS atomic and weight percentages without conversion.

        Unspecified-basis values remain in raw evidence but do not populate either
        numeric channel. EDS and legacy generic atomic fields are never substituted.
        """
        extras=[f for f in self.contract['model_material_features'] if f not in ['XPS_N_reported_pct','XPS_O_reported_pct']]
        matrix=self.material_matrix(profile,extra_features=extras)
        rows={r['endpoint_id']:r for r in self.fetch(profile).rows}
        fields=[('XPS_N_atomic_pct_v15','XPS_N_reported_pct','atomic_explicit'),
                ('XPS_O_atomic_pct_v15','XPS_O_reported_pct','atomic_explicit'),
                ('XPS_N_weight_pct_v15','XPS_N_reported_pct','weight_explicit'),
                ('XPS_O_weight_pct_v15','XPS_O_reported_pct','weight_explicit')]
        for i,key in enumerate(matrix['endpoint_ids']):
            row=rows[key]
            matrix['X'][i].extend(row.get(raw) if row.get('XPS_percentage_basis')==basis else None for _,raw,basis in fields)
        matrix['feature_names'].extend(name for name,_,_ in fields)
        matrix['missing_mask']=[[x is None for x in row] for row in matrix['X']]
        matrix['xps_basis_projection']='Explicit atomic / weight channels; unspecified basis withheld; no conversion or EDS substitution.'
        return matrix

    def material_properties(self,material_key=None,selected_only=True):
        old=super().material_properties(material_key,selected_only)
        if not hasattr(self,'delta_v15') or getattr(self,'_reading_historical_evidence',False):return old
        current=[dict(r) for r in self.delta_v15.execute('select * from material_fields_v15') if material_key is None or r['material_key']==material_key]
        keys={(r['material_key'],r['field_name']) for r in current}
        if selected_only:old=[r for r in old if (r['material_key'],r['field_name']) not in keys]
        else:
            for r in old:
                if (r['material_key'],r['field_name']) in keys:r['selected']=0;r['superseded_in_v15']=True
        for r in current:r.update(value=json.loads(r['value_json']),evidence=json.loads(r['evidence_json']),selected=1,
            review_version='v0.15',stage='before_cycling',applies_to_systems_json='[]')
        return old+current

    def evidence(self,key,field=None):
        flag=getattr(self,'_reading_historical_evidence',False);self._reading_historical_evidence=True
        try:old=super().evidence(key,field)
        finally:self._reading_historical_evidence=flag
        if not hasattr(self,'changes_v15'):return old
        changes=self.changes_v15.get(key,[]);changed_fields={c['field_name'] for c in changes}
        for e in old:
            if e.get('field_name') in changed_fields:
                e['selected']=0;e['currently_selected']=0;e['superseded_by_v15']=True
        for c in changes:
            if field is not None and c['field_name']!=field:continue
            for e in json.loads(c['evidence_json']):
                if c['field_name'] in e['fields']:
                    old.append(dict(endpoint_id=key,field_name=c['field_name'],value_json=c['after_json'],
                        selected=1,currently_selected=1,review_version='v0.15',excerpt_kind='reviewed_own_source_field',**e))
        return old
