"""Read-only additive v0.8 API. Loading/prechecking never authorizes fitting."""
from pathlib import Path
import collections, importlib.util, json, sys

ROOT=Path(__file__).resolve().parents[1]
PARENT=ROOT/'循环稳定性数据库_v0.7_数据补充_20261018/ml_data.py'
NAME='_cycling_v07_parent_api'
if NAME not in sys.modules:
    spec=importlib.util.spec_from_file_location(NAME,PARENT)
    module=importlib.util.module_from_spec(spec);sys.modules[NAME]=module;spec.loader.exec_module(module)
base=sys.modules[NAME]
Dataset=base.Dataset
DataNotReady=base.DataNotReady
StaleCacheError=base.StaleCacheError

class Database(base.Database):
    def __init__(self,path=None):
        folder=Path(__file__).resolve().parent
        super().__init__(path or folder/'cycling_v0_8.sqlite')
        self.root=folder
        self.contract=json.loads((folder/'data_contract.json').read_text('utf-8'))

    def incoming_sources(self):
        return [json.loads(r[0]) for r in self.conn.execute('select review_json from incoming_sources_v08 order by document_id')]

    def incoming_tests(self,document_id=None):
        sql='select row_json from incoming_tests_v08';args=[]
        if document_id:sql+=' where document_id=?';args.append(document_id)
        return [json.loads(r[0]) for r in self.conn.execute(sql+' order by record_id',args)]

    def fetch(self,profile=None,year_min=None,year_max=None):
        profile=profile or self.contract['default_profile']
        if profile=='incoming_review':
            rows=self.incoming_tests()
            rows=[r for r in rows if (year_min is None or r['source_year'] is not None and r['source_year']>=year_min) and (year_max is None or r['source_year'] is not None and r['source_year']<=year_max)]
            counts=collections.Counter(r['source_group'] for r in rows)
            for r in rows:r['source_weight']=1/counts[r['source_group']]
            return Dataset(profile,rows,list(self.contract['core_features']))
        result=super().fetch(profile,year_min,year_max)
        if profile in self.contract['profiles']:
            extra=[json.loads(r[0]) for r in self.conn.execute('select t.row_json from incoming_tests_v08 t join incoming_admissions_v08 a using(record_id) where a.profile=? and a.status=? order by t.source_group,t.record_id',(profile,'approved_for_reported_protocol'))]
        elif profile=='all_review':extra=self.incoming_tests()
        elif profile=='review_3e_all':extra=[r for r in self.incoming_tests() if r['system']=='3E']
        else:extra=[]
        for r in extra:
            if year_min is not None and (r['source_year'] is None or r['source_year']<int(year_min)):continue
            if year_max is not None and (r['source_year'] is None or r['source_year']>int(year_max)):continue
            r['profile_review']={'reason':'Explicit per-test own-source review in incoming batch.','evidence':{'label_pages':r['evidence_pages'],'fields':r.get('field_evidence',{}),'source_sha256':r['source_sha256'],'notes':r.get('review_notes',[])}}
            result.rows.append(r)
        result.rows.sort(key=lambda r:(r['source_group'],r['endpoint_id']))
        counts=collections.Counter(r['source_group'] for r in result.rows)
        for r in result.rows:r['source_weight']=1/counts[r['source_group']]
        return result

    def evidence(self,endpoint_id,field=None):
        if not endpoint_id.startswith('incoming:'):return super().evidence(endpoint_id,field)
        record_id=endpoint_id.removeprefix('incoming:')
        sql='''select o.*,p.document_id,p.page_number,s.repository_path,s.sha256
               from incoming_observations_v08 o
               left join incoming_observation_pages_v08 p using(observation_id)
               left join incoming_sources_v08 s using(document_id)
               where o.record_id=?'''
        args=[record_id]
        if field:sql+=' and o.field_name=?';args.append(field)
        return [dict(r) for r in self.conn.execute(sql+' order by o.observation_id,p.page_number',args)]

    def admission_checks(self,endpoint_id,profile=None):
        if not endpoint_id.startswith('incoming:'):return super().admission_checks(endpoint_id,profile)
        sql='select * from incoming_admissions_v08 where record_id=?';args=[endpoint_id.removeprefix('incoming:')]
        if profile:sql+=' and profile=?';args.append(profile)
        return [dict(r) for r in self.conn.execute(sql+' order by profile',args)]

    def holds(self,endpoint_id):
        if not endpoint_id.startswith('incoming:'):return super().holds(endpoint_id)
        row=self.conn.execute('select row_json from incoming_tests_v08 where record_id=?',(endpoint_id.removeprefix('incoming:'),)).fetchone()
        if not row:return {}
        r=json.loads(row[0])
        return {'open_issues':r['open_issues'],'remaining_evidence_work':r['remaining_evidence_work'],'historical_issues':r['issues'],'issue_dispositions':r.get('issue_dispositions',[]),'alternatives':r.get('extra_observations',[])}

    def search_incoming(self,query,doi=None,limit=10):
        words=str(query).split()
        if not words:return []
        expr=' AND '.join('"'+w.replace('"','""')+'"' for w in words)
        sql='''select p.document_id,p.page_number,p.text,s.doi,s.source_group,s.repository_path,s.sha256
               from incoming_search_v08 f join incoming_pages_v08 p
               on p.document_id=f.document_id and p.page_number=f.page_number
               join incoming_sources_v08 s on s.document_id=p.document_id
               where incoming_search_v08 match ?''';args=[expr]
        if doi:sql+=' and s.doi=?';args.append(str(doi).lower().removeprefix('https://doi.org/'))
        sql+=' order by p.document_id,p.page_number limit ?';args.append(max(1,min(int(limit),100)))
        return [dict(r) for r in self.conn.execute(sql,args)]

    def search(self,query,doi=None,limit=10):
        # Incoming evidence first, then inherited sources, bounded by the requested limit.
        limit=max(1,min(int(limit),100));new=self.search_incoming(query,doi,limit)
        return (new+super().search(query,doi,limit))[:limit]

    def review_summary(self):
        result=super().review_summary()
        result['reported_profiles']=[{'profile':p,'records':len((d:=self.fetch(p)).rows),'source_groups':len({r['source_group'] for r in d.rows})} for p in self.contract['profiles']]
        result['incoming_documents']=len(self.incoming_sources())
        result['incoming_test_observations']=len(self.incoming_tests())
        result['incoming_explicit_approvals']=sum(r['eligible'] for r in self.incoming_tests())
        result['historical_records']=result.pop('records')
        result['all_records_admitted']=False
        return result
