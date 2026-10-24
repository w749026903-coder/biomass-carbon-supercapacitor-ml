"""Read-only v0.18: source bibliography and explicit known-measurement QA.

No new training admission; parent labels, source groups and holds preserved.
"""
from pathlib import Path
import collections, hashlib, importlib.util, json, sqlite3, sys
ROOT=Path(__file__).resolve().parents[1]
PARENT=ROOT/'循环稳定性数据库_v0.17_原图标签补正_20261024'
NAME='_cycling_v017_parent_for_v018'
if NAME not in sys.modules:
    s=importlib.util.spec_from_file_location(NAME,PARENT/'ml_data.py')
    m=importlib.util.module_from_spec(s);sys.modules[NAME]=m;s.loader.exec_module(m)
base=sys.modules[NAME];Dataset=base.Dataset;DataNotReady=base.DataNotReady

class Database(base.Database):
    def __init__(self,path=None):
        folder=Path(__file__).resolve().parent;contract=json.loads((folder/'data_contract.json').read_text('utf8'))
        with (PARENT/'cycling_v0_17.sqlite').open('rb') as f:
            if hashlib.file_digest(f,'sha256').hexdigest()!=contract['parent_database_sha256']:raise RuntimeError('Immutable v0.17 changed.')
        super().__init__(PARENT/'cycling_v0_17.sqlite')
        self.root=folder;self.contract=contract;self.path=Path(path).resolve() if path else folder/contract['database_file']
        self.delta_v18=sqlite3.connect(self.path.as_uri()+'?mode=ro',uri=True);self.delta_v18.row_factory=sqlite3.Row
        self.delta_v18.execute('pragma query_only=on')
        self.changes_v18=collections.defaultdict(list)
        for r in self.delta_v18.execute('select * from field_changes_v18 order by endpoint_id,field_name'):
            self.changes_v18[r['endpoint_id']].append(dict(r))
        self.reviews_v18={r['endpoint_id']:json.loads(r['review_json']) for r in self.delta_v18.execute('select * from reviews_v18')}

    def close(self):
        if hasattr(self,'delta_v18'):self.delta_v18.close()
        super().close()

    def _apply_v18(self,row):
        if row is not None and hasattr(self,'changes_v18') and not getattr(self,'_reading_parent_v17',False):
            for c in self.changes_v18.get(row['endpoint_id'],[]):
                row[c['field_name']]=json.loads(c['after_json']);row[c['field_name']+'_status']='v018_'+c['operation']
            if row['endpoint_id'] in self.reviews_v18:
                review=self.reviews_v18[row['endpoint_id']]
                row['review_disposition_v18']=review['disposition']
                row['current_open_issues_v18']=list(review['open_issues'])
        return row

    def fetch(self,profile=None,year_min=None,year_max=None):
        if not hasattr(self,'delta_v18'):return super().fetch(profile,year_min,year_max)
        ds=super().fetch(profile)
        rows=[self._apply_v18(r) for r in ds.rows]
        rows=[r for r in rows if (year_min is None or r.get('source_year') is not None and r['source_year']>=int(year_min))
              and (year_max is None or r.get('source_year') is not None and r['source_year']<=int(year_max))]
        counts=collections.Counter(r['source_group'] for r in rows)
        for r in rows:r['source_weight']=1/counts[r['source_group']]
        return Dataset(ds.profile,rows,list(ds.features))

    def by_endpoint(self,key):return self._apply_v18(super().by_endpoint(key))

    def holds(self,key):
        flag=getattr(self,'_reading_parent_v17',False);self._reading_parent_v17=True
        try:old=super().holds(key)
        finally:self._reading_parent_v17=flag
        if not hasattr(self,'reviews_v18') or key not in self.reviews_v18:return old
        r=self.reviews_v18[key]
        return dict(open_issues=r['open_issues'],approved_profiles=r['approved_profiles'],disposition=r['disposition'],reason=r['reason'],
                    resolution=r['resolution'],previous_holds=old,review_version='v0.18')

    def reviewed_pending_batch(self,include_outside=False):
        rows=[dict(self.reviews_v18.get(r['endpoint_id'],r)) for r in super().reviewed_pending_batch(True)]
        return rows if include_outside else [r for r in rows if not r['disposition'].startswith(('outside_','approved_'))]

    def admission_checks(self,key,profile=None):
        checks=super().admission_checks(key,profile)
        if hasattr(self,'reviews_v18') and key in self.reviews_v18:
            for c in checks:
                c['historical_v17_review']=c.get('current_review');c['current_review']=self.reviews_v18[key];c['review_version']='v0.18'
        return checks

    def field_changes(self,key=None,include_history=False):
        rows=[dict(c,before=json.loads(c['before_json']),after=json.loads(c['after_json']),evidence=json.loads(c['evidence_json']),review_version='v0.18')
              for k,cs in self.changes_v18.items() for c in cs if key is None or k==key]
        return (super().field_changes(key,include_history=True) if include_history else [])+rows

    def evidence(self,key,field=None):
        flag=getattr(self,'_reading_historical_evidence',False);self._reading_historical_evidence=True
        try:old=super().evidence(key,field)
        finally:self._reading_historical_evidence=flag
        if not hasattr(self,'changes_v18'):return old
        names={c['field_name'] for c in self.changes_v18.get(key,[])}
        for e in old:
            if e.get('field_name') in names:e.update(selected=0,currently_selected=0,superseded_by_v18=True)
        for c in self.changes_v18.get(key,[]):
            if field is not None and field!=c['field_name']:continue
            for e in json.loads(c['evidence_json']):old.append(dict(e,endpoint_id=key,field_name=c['field_name'],value_json=c['after_json'],selected=1,currently_selected=1,review_version='v0.18',excerpt_kind='reviewed_bibliography_or_measurement_QA'))
        return old

    def source_aliases(self):
        """Source-document identifiers only, without source-group migration or approval."""
        return [dict(r) for r in self.delta_v18.execute('select * from source_aliases_v18 order by endpoint_id,doi')]
