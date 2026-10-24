"""Read-only, evidence-qualified v0.16 delta; no admission or model fitting."""
from pathlib import Path
import collections,hashlib,importlib.util,json,re,sqlite3,sys
ROOT=Path(__file__).resolve().parents[1]
PARENT=ROOT/'循环稳定性数据库_v0.15_表图与待补证复核_20261024'
NAME='_cycling_v015_parent_for_v016'
if NAME not in sys.modules:
    spec=importlib.util.spec_from_file_location(NAME,PARENT/'ml_data.py')
    mod=importlib.util.module_from_spec(spec);sys.modules[NAME]=mod;spec.loader.exec_module(mod)
base=sys.modules[NAME];Dataset=base.Dataset;DataNotReady=base.DataNotReady

class Database(base.Database):
    def __init__(self,path=None):
        folder=Path(__file__).resolve().parent
        contract=json.loads((folder/'data_contract.json').read_text('utf8'))
        with (PARENT/'cycling_v0_15.sqlite').open('rb') as f:
            if hashlib.file_digest(f,'sha256').hexdigest()!=contract['parent_database_sha256']:
                raise RuntimeError('Immutable v0.15 changed.')
        super().__init__(PARENT/'cycling_v0_15.sqlite')
        self.root=folder;self.contract=contract
        self.path=Path(path).resolve() if path else folder/contract['database_file']
        self.delta_v16=sqlite3.connect(self.path.as_uri()+'?mode=ro',uri=True)
        self.delta_v16.row_factory=sqlite3.Row;self.delta_v16.execute('pragma query_only=on')
        self.changes_v16=collections.defaultdict(list)
        for r in self.delta_v16.execute('select * from field_changes_v16 order by endpoint_id,field_name'):
            self.changes_v16[r['endpoint_id']].append(dict(r))
        self.reviews_v16={r['endpoint_id']:json.loads(r['review_json']) for r in self.delta_v16.execute('select * from reviews_v16')}

    def close(self):
        if hasattr(self,'delta_v16'):self.delta_v16.close()
        super().close()

    def _apply_v16(self,row):
        if row is not None and hasattr(self,'changes_v16'):
            for c in self.changes_v16.get(row['endpoint_id'],[]):
                row[c['field_name']]=json.loads(c['after_json'])
                row[c['field_name']+'_status']='v016_'+c['operation']
            if row['endpoint_id'] in self.reviews_v16:
                row['review_disposition_v16']=self.reviews_v16[row['endpoint_id']]['disposition']
        return row

    def fetch(self,profile=None,year_min=None,year_max=None):
        ds=super().fetch(profile,year_min,year_max)
        for row in ds.rows:self._apply_v16(row)
        return ds

    def by_endpoint(self,key):return self._apply_v16(super().by_endpoint(key))

    def holds(self,key):
        old=super().holds(key)
        if not hasattr(self,'reviews_v16') or key not in self.reviews_v16:return old
        r=self.reviews_v16[key]
        return dict(open_issues=r['open_issues'],approved_profiles=r['approved_profiles'],
            disposition=r['disposition'],reason=r['reason'],resolution=r['resolution'],
            previous_holds=old,review_version='v0.16')

    def reviewed_pending_batch(self,include_outside=False):
        old=super().reviewed_pending_batch(True)
        rows=[dict(self.reviews_v16.get(r['endpoint_id'],r)) for r in old]
        return [r for r in rows if include_outside or not r['disposition'].startswith('outside_')]

    def admission_checks(self,key,profile=None):
        checks=super().admission_checks(key,profile)
        if hasattr(self,'reviews_v16') and key in self.reviews_v16:
            for c in checks:
                c['historical_v15_review']=c.get('current_review')
                c['current_review']=self.reviews_v16[key];c['review_version']='v0.16'
        return checks

    def field_changes(self,key=None,include_history=False):
        rows=[c for k,cs in self.changes_v16.items() for c in cs if key is None or k==key]
        current=[dict(c,before=json.loads(c['before_json']),after=json.loads(c['after_json']),
            evidence=json.loads(c['evidence_json']),review_version='v0.16') for c in rows]
        return (super().field_changes(key) if include_history else [])+current

    def material_properties(self,material_key=None,selected_only=True):
        old=super().material_properties(material_key,selected_only)
        if not hasattr(self,'delta_v16') or getattr(self,'_reading_historical_evidence',False):return old
        rows=[dict(r) for r in self.delta_v16.execute('select * from material_fields_v16') if material_key is None or r['material_key']==material_key]
        keys={(r['material_key'],r['field_name']) for r in rows}
        if selected_only:old=[r for r in old if (r['material_key'],r['field_name']) not in keys]
        else:
            for r in old:
                if (r['material_key'],r['field_name']) in keys:r['selected']=0;r['superseded_in_v16']=True
        for r in rows:r.update(value=json.loads(r['value_json']),evidence=json.loads(r['evidence_json']),
            selected=1,review_version='v0.16',stage='before_cycling',training_admission_inferred=False,
            applies_to_systems_json='[]')
        return old+rows

    def evidence(self,key,field=None):
        flag=getattr(self,'_reading_historical_evidence',False);self._reading_historical_evidence=True
        try:old=super().evidence(key,field)
        finally:self._reading_historical_evidence=flag
        if not hasattr(self,'changes_v16'):return old
        changes=self.changes_v16.get(key,[]);names={r['field_name'] for r in changes}
        for e in old:
            if e.get('field_name') in names:e.update(selected=0,currently_selected=0,superseded_by_v16=True)
        for c in changes:
            if field is not None and field!=c['field_name']:continue
            for e in json.loads(c['evidence_json']):
                old.append(dict(e,endpoint_id=key,field_name=c['field_name'],value_json=c['after_json'],
                    selected=1,currently_selected=1,review_version='v0.16',excerpt_kind='reviewed_own_source_field'))
        return old

    def search_native(self,query,doi=None,limit=10):
        """Search the new native SI text and reviewed image readings, then old corpus.

        Reviewed image transcriptions are explicitly different from native text.
        Neither a text hit nor an image reading grants training admission.
        """
        words=str(query).split();limit=max(0,int(limit))
        if not words or not limit:return []
        expression=' AND '.join('"'+w.replace('"','""')+'"' for w in words)
        sql='''select s.*,p.path,p.format,p.component from source_segments_v16 s
          join segment_fts_v16 f on f.rowid=s.segment_id join sources_v16 p using(source_sha256)
          where segment_fts_v16 match ?''';args=[expression]
        if doi:
            sql+=' and p.doi=?';args.append(str(doi).lower().removeprefix('https://doi.org/').removeprefix('doi:'))
        sql+=' order by s.segment_id limit ?';args.append(limit)
        result=[]
        for row in self.delta_v16.execute(sql,args):
            r=dict(row);text=r.pop('text')
            if hashlib.sha256(text.encode('utf8')).hexdigest()!=r['content_sha256']:raise RuntimeError('Evidence text changed.')
            match=re.search('|'.join(re.escape(w) for w in words),text,re.I)
            start=max(0,match.start()-180) if match else 0
            r.update(excerpt=text[start:start+1400],training_eligible=0,status='evidence_search_match_not_test_admission',provider='v16_new_evidence')
            result.append(r)
        if len(result)<limit:result.extend(super().search_native(query,doi,limit-len(result)))
        return result
