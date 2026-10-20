"""Read-only v0.9 evidence overlay. The immutable v0.8 SQLite remains the base."""
from pathlib import Path
import collections, hashlib, importlib.util, json, sqlite3, sys
ROOT=Path(__file__).resolve().parents[1]
PARENT=ROOT/'循环稳定性数据库_v0.8_新增文献整理_20261020'
NAME='_cycling_v08_parent_api'
if NAME not in sys.modules:
    spec=importlib.util.spec_from_file_location(NAME,PARENT/'ml_data.py')
    module=importlib.util.module_from_spec(spec);sys.modules[NAME]=module;spec.loader.exec_module(module)
base=sys.modules[NAME]
Dataset=base.Dataset
DataNotReady=base.DataNotReady

class Database(base.Database):
    def __init__(self,path=None):
        folder=Path(__file__).resolve().parent
        contract=json.loads((folder/'data_contract.json').read_text('utf-8'))
        parent=PARENT/'cycling_v0_8.sqlite'
        with parent.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
        if digest!=contract['parent_database_sha256']:raise RuntimeError('Immutable v0.8 base fingerprint changed.')
        super().__init__(parent)
        self.root=folder;self.contract=contract
        self.path=Path(path).resolve() if path else folder/'cycling_v0_9.sqlite'
        self.delta=sqlite3.connect(self.path.as_uri()+'?mode=ro',uri=True);self.delta.row_factory=sqlite3.Row
        self.delta.execute('PRAGMA query_only=ON')
        self.cases={r['endpoint_id']:json.loads(r['decision_json']) for r in self.delta.execute('select * from quality_decisions_v09')}
    def close(self):
        if hasattr(self,'delta'):self.delta.close()
        super().close()
    def incoming_tests(self,document_id=None):
        rows=super().incoming_tests(document_id)
        return [json.loads(json.dumps(self.cases[r['endpoint_id']]['after'])) if r['endpoint_id'] in self.cases else r for r in rows]
    def incoming_sources(self):
        rows=super().incoming_sources()
        for r in rows:
            if r['document_id']=='ADD_052':
                r['year']=2025;r['year_basis']='Own journal PDF footer; v0.9 reviewed correction'
        return rows
    def fetch(self,profile=None,year_min=None,year_max=None):
        profile=profile or self.contract['default_profile']
        result=super().fetch(profile,None,None)
        rows={r['endpoint_id']:r for r in result.rows}
        for key,case in self.cases.items():
            r=json.loads(json.dumps(case['after']))
            if profile in self.contract['profiles']:
                if key in rows:del rows[key]
                if profile not in case['profiles']:continue
            elif key not in rows:continue
            if year_min is not None and (r['source_year'] is None or r['source_year']<int(year_min)):continue
            if year_max is not None and (r['source_year'] is None or r['source_year']>int(year_max)):continue
            r['profile_review']={'reason':case['reason'],'evidence':case['evidence'],'review_version':'v0.9'}
            rows[key]=r
        result.rows=sorted(rows.values(),key=lambda r:(r['source_group'],r['endpoint_id']))
        result.rows=[r for r in result.rows if (year_min is None or r['source_year'] is not None and r['source_year']>=int(year_min)) and (year_max is None or r['source_year'] is not None and r['source_year']<=int(year_max))]
        counts=collections.Counter(r['source_group'] for r in result.rows)
        for r in result.rows:r['source_weight']=1/counts[r['source_group']]
        return result
    def evidence(self,endpoint_id,field=None):
        old=super().evidence(endpoint_id,field)
        case=self.cases.get(endpoint_id)
        if not case:return old
        changed={k for k,v in case['after'].items() if v!=case['before'].get(k)}
        changed|={k for k,v in case['after']['fields'].items() if v!=case['before']['fields'].get(k)}
        for r in old:
            if r['field_name'] in changed:r['selected']=0;r['status']='superseded_in_v09'
        for e in case['evidence']:
            for f in e.get('fields',[]):
                if field and field!=f:continue
                old.append({'field_name':f,'value_json':json.dumps(case['after'].get(f,case['after']['fields'].get(f)),ensure_ascii=False),'selected':1,'review_version':'v0.9',**e})
        return old
    def holds(self,endpoint_id):
        if endpoint_id not in self.cases:return super().holds(endpoint_id)
        c=self.cases[endpoint_id];r=c['after']
        return {'open_issues':r['open_issues'],'remaining_evidence_work':r['remaining_evidence_work'],
                'previous_holds':super().holds(endpoint_id),'v09_reason':c['reason'],'v09_profiles':c['profiles']}
    def admission_checks(self,endpoint_id,profile=None):
        if endpoint_id not in self.cases:return super().admission_checks(endpoint_id,profile)
        c=self.cases[endpoint_id]
        return [{'profile':p,'endpoint_id':endpoint_id,'status':'approved_for_reported_protocol' if p in c['profiles'] else 'pending_or_outside','reason':c['reason'],'evidence':c['evidence']} for p in ([profile] if profile else self.contract['profiles'])]
    def quality_readiness(self):return json.loads((self.root/'training_readiness.json').read_text('utf-8'))
