"""Read-only append layer over v0.19; original records and reviews remain immutable."""
from pathlib import Path
import collections,hashlib,importlib.util,json,sqlite3,sys
ROOT=Path(__file__).resolve().parents[1]
PARENT=ROOT/'循环稳定性数据库_v0.19_摘要与制备漏项补正_20261025'
NAME='_cycling_v019_parent_for_v020'
if NAME not in sys.modules:
    spec=importlib.util.spec_from_file_location(NAME,PARENT/'ml_data.py')
    module=importlib.util.module_from_spec(spec);sys.modules[NAME]=module;spec.loader.exec_module(module)
base=sys.modules[NAME];Dataset=base.Dataset;DataNotReady=base.DataNotReady

class Database(base.Database):
    def __init__(self,path=None):
        folder=Path(__file__).resolve().parent
        contract=json.loads((folder/'data_contract.json').read_text('utf8'))
        with (PARENT/'cycling_v0_19.sqlite').open('rb') as f:
            if hashlib.file_digest(f,'sha256').hexdigest()!=contract['parent_database_sha256']:
                raise RuntimeError('Immutable v0.19 differs.')
        super().__init__(PARENT/'cycling_v0_19.sqlite')
        self.root,self.contract=folder,contract
        self.path=Path(path).resolve() if path else folder/contract['database_file']
        self.delta_v20=sqlite3.connect(self.path.as_uri()+'?mode=ro',uri=True)
        self.delta_v20.row_factory=sqlite3.Row;self.delta_v20.execute('pragma query_only=on')
        self.new_rows_v20={r['endpoint_id']:json.loads(r['row_json']) for r in self.delta_v20.execute('select * from endpoints_v20')}
        self.members_v20=collections.defaultdict(set)
        for r in self.delta_v20.execute('select * from profile_membership_v20 where eligible=1'):
            self.members_v20[r['profile']].add(r['endpoint_id'])

    def close(self):
        if hasattr(self,'delta_v20'):self.delta_v20.close()
        super().close()

    def fetch(self,profile=None,year_min=None,year_max=None):
        previous=super().fetch(profile,year_min,year_max)
        if not hasattr(self,'new_rows_v20'):return previous
        profile=previous.profile;rows=list(previous.rows)
        for key,stored in self.new_rows_v20.items():
            if profile!='all_review' and key not in self.members_v20.get(profile,set()):continue
            year=stored.get('source_year')
            if year_min is not None and (year is None or year<int(year_min)):continue
            if year_max is not None and (year is None or year>int(year_max)):continue
            if any(r['endpoint_id']==key for r in rows):raise RuntimeError('Append collides with parent endpoint.')
            rows.append(json.loads(json.dumps(stored)))
        counts=collections.Counter(r['source_group'] for r in rows)
        for r in rows:r['source_weight']=1/counts[r['source_group']]
        return Dataset(profile,sorted(rows,key=lambda r:(r['source_group'],r['endpoint_id'])),list(previous.features))

    def by_endpoint(self,key):
        if key in getattr(self,'new_rows_v20',{}):return json.loads(json.dumps(self.new_rows_v20[key]))
        return super().by_endpoint(key)

    def holds(self,key):
        if key not in getattr(self,'new_rows_v20',{}):return super().holds(key)
        r=self.delta_v20.execute('select review_json from reviews_v20 where endpoint_id=?',(key,)).fetchone()
        return dict(json.loads(r[0]),review_version='v0.20')

    def admission_checks(self,key,profile=None):
        if key not in getattr(self,'new_rows_v20',{}):return super().admission_checks(key,profile)
        review=self.holds(key);result=[]
        for p in ([profile] if profile else self.contract['profiles']):
            approved=key in self.members_v20.get(p,set())
            result.append(dict(endpoint_id=key,profile=p,status='approved_for_reported_protocol' if approved else 'not_admitted_to_this_purpose',current_review=review,review_version='v0.20',historical_checks=[],reason='Current documented 2E symmetric report-purpose decision; strict unified current and all3E purposes not inferred.'))
        return result

    def evidence(self,key,field=None):
        if key not in getattr(self,'new_rows_v20',{}):return super().evidence(key,field)
        return [dict(r,currently_selected=r['selected'],review_version='v0.20') for r in self.delta_v20.execute('''
          select e.*,d.path,d.sha256,d.role as document_role from evidence_v20 e
          join source_documents_v20 d using(document_key)
          where endpoint_id=? and (? is null or field_name=?) order by evidence_id''',(key,field,field))]

    def field_changes(self,key=None,include_history=False):
        previous=super().field_changes(key,include_history) if include_history else []
        if not hasattr(self,'delta_v20'):return previous
        rows=[dict(r,before=json.loads(r['before_json']),after=json.loads(r['after_json']),evidence=json.loads(r['evidence_json']),review_version='v0.20') for r in self.delta_v20.execute('select * from field_changes_v20 where (? is null or endpoint_id=?) order by change_id',(key,key))]
        return previous+rows

    def material_properties(self,material_key=None,selected_only=True):
        previous=super().material_properties(material_key,selected_only)
        if not hasattr(self,'delta_v20'):return previous
        rows=[];docs={r['document_key']:dict(r) for r in self.delta_v20.execute('select * from source_documents_v20')}
        for r in self.delta_v20.execute('select * from material_fields_v20 where (? is null or material_key=?)',(material_key,material_key)):
            proof=[dict(e,path=docs[e['document_key']]['path'],sha256=docs[e['document_key']]['sha256']) for e in json.loads(r['evidence_json'])]
            rows.append(dict(r,value=json.loads(r['value_json']),evidence=proof,path=proof[0]['path'],sha256=proof[0]['sha256'],locator=proof[0]['locator'],excerpt=proof[0]['excerpt'],selected=1,review_version='v0.20',stage='before_cycling',training_admission_inferred=False,applies_to_systems_json='[]'))
        return previous+rows

    def source_aliases(self):
        previous=super().source_aliases()
        if not hasattr(self,'delta_v20'):return previous
        for r in self.delta_v20.execute('''select e.endpoint_id,s.doi,s.source_group from endpoints_v20 e
          join tests_v20 t using(test_id) join materials_v20 m using(material_key) join sources_v20 s using(source_id)'''):
            previous.append(dict(r,alias_kind='new_source_document_identity_no_parent_migration',review_version='v0.20'))
        return previous

    def literature_links(self):
        return [dict(r,review_version='v0.20') for r in self.delta_v20.execute('select * from literature_links_v20')]

    def search_native(self,query,doi=None,limit=10):
        if not hasattr(self,'delta_v20'):return super().search_native(query,doi,limit)
        if not str(query).strip() or int(limit)<=0:return []
        rows=[];term=str(query).lower()
        for r in self.delta_v20.execute('''select e.*,d.path,d.sha256,s.doi from evidence_v20 e
          join source_documents_v20 d using(document_key) join sources_v20 s using(source_id)'''):
            if doi is not None and doi.lower().removeprefix('doi:')!=r['doi']:continue
            if term in (r['excerpt']+' '+r['locator']).lower():rows.append(dict(r,training_eligible=0,status='reviewed_excerpt_search_not_automatic_admission'))
        return (rows+super().search_native(query,doi,limit))[:int(limit)]
