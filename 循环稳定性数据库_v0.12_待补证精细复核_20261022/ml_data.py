"""Read-only v0.12 reviewed evidence overlay; the immutable v0.11 stays in place."""
from pathlib import Path
import collections, hashlib, importlib.util, json, math, sqlite3, sys

ROOT=Path(__file__).resolve().parents[1]
PARENT=ROOT/'循环稳定性数据库_v0.11_全库复检与材料特征_20261021'
NAME='_cycling_v011_parent_for_v012'
if NAME not in sys.modules:
    spec=importlib.util.spec_from_file_location(NAME,PARENT/'ml_data.py')
    parent=importlib.util.module_from_spec(spec);sys.modules[NAME]=parent;spec.loader.exec_module(parent)
base=sys.modules[NAME]
DataNotReady=base.DataNotReady


class Dataset(base.Dataset):
    def feature_matrix(self):
        if self.profile=='reported_3e':
            for row in self.rows:
                if not row.get('baseline_reference'):raise DataNotReady('Reviewed cycling reference required.')
                if self.profile not in row.get('admission_profiles_v12',[]):raise DataNotReady('Current explicit main admission required.')
        if self.profile not in ['reported_3e_sensitivity','reported_3e_residue_sensitivity']:return super().feature_matrix()
        if not self.rows:raise DataNotReady('Empty sensitivity cohort.')
        numeric=set(self.features)-{'electrolyte','reference_electrode'}
        for row in self.rows:
            if row.get('system')!='3E' or row.get('method')!='GCD':raise DataNotReady('Wrong test system/method.')
            if row.get('eligible')!=1 or self.profile not in row.get('admission_profiles_v12',[]):raise DataNotReady('Explicit sensitivity admission required.')
            relations=['eq'] if self.profile=='reported_3e_residue_sensitivity' else ['eq','approx','derived_complement']
            if row.get('metric_kind')!='capacitance_retention' or row.get('retention_relation') not in relations:raise DataNotReady('Wrong target/relation.')
            if row.get('source_year') is None or not 2023<=row['source_year']<=2026 or row['cycle_count']<1000:raise DataNotReady('Unchanged 2023-2026 and >=1000 cycle cohort boundaries.')
            if not row.get('baseline_reference'):raise DataNotReady('Reference evidence required.')
            for field in numeric|{'retention_pct'}:
                v=row.get(field)
                if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v):raise DataNotReady('Missing/nonfinite numeric field: '+field)
            if any(not isinstance(row.get(f),str) or not row[f].strip() for f in ['electrolyte','reference_electrode']):raise DataNotReady('Missing categorical descriptor.')
            if any(row[k]<=0 for k in ['cycle_count','reported_current_A_g','BET_m2_g','concentration_mol_L']):raise DataNotReady('Nonpositive descriptor.')
            if row['cycle_voltage_upper_V']<=row['cycle_voltage_lower_V'] or row['retention_pct']<0:raise DataNotReady('Invalid potential/target.')
        return {'X':[[r[f] for f in self.features] for r in self.rows], 'y':[r['retention_pct'] for r in self.rows],
                'groups':[r['source_group'] for r in self.rows],'sample_weight':[r['source_weight'] for r in self.rows],
                'feature_names':self.features,'training_authorized':False,'current_semantics':'author_reported_protocol_descriptor',
                'label_relations':[r['retention_relation'] for r in self.rows],
                'label_evidence_kind':[r.get('retention_evidence_kind_v12','complement_of_author_reported_loss' if r['retention_relation']=='derived_complement' else 'author_reported') for r in self.rows],
                'label_reading_bound_pp':[r.get('retention_reading_bound_pp_v12') for r in self.rows],
                'note':'Nested, explicitly reviewed sensitivity cohort. Label or residue uncertainty stays separate from main admission.'}


class Database(base.Database):
    def __init__(self,path=None):
        folder=Path(__file__).resolve().parent
        contract=json.loads((folder/'data_contract.json').read_text('utf-8'))
        with (PARENT/'cycling_v0_11.sqlite').open('rb') as f:
            if hashlib.file_digest(f,'sha256').hexdigest()!=contract['parent_database_sha256']:raise RuntimeError('Immutable v0.11 fingerprint changed.')
        super().__init__(PARENT/'cycling_v0_11.sqlite')
        self.root=folder;self.contract=contract;self.path=Path(path).resolve() if path else folder/contract['database_file']
        self.delta_v12=sqlite3.connect(self.path.as_uri()+'?mode=ro',uri=True);self.delta_v12.row_factory=sqlite3.Row
        self.delta_v12.execute('pragma query_only=on')
        self.decisions_v12={r['endpoint_id']:json.loads(r['review_json']) for r in self.delta_v12.execute('select * from test_reviews_v12')}

    def close(self):
        if hasattr(self,'delta_v12'):self.delta_v12.close()
        super().close()

    def fetch(self,profile=None,year_min=None,year_max=None):
        if not hasattr(self,'delta_v12'):return super().fetch(profile,year_min,year_max)
        profile=profile or self.contract['default_profile']
        if profile in self.contract['profiles']:
            rows=[json.loads(r[0]) for r in self.delta_v12.execute('select row_json from review_rows_v12 join profile_membership_v12 using(endpoint_id) where profile=?',(profile,))]
            features=self.contract['profiles'][profile]['features']
        elif profile in ['all_review','review_3e_all','incoming_review']:
            rows=[json.loads(r[0]) for r in self.delta_v12.execute('select row_json from review_rows_v12')];features=self.contract['core_features']
            if profile=='review_3e_all':rows=[r for r in rows if r['system']=='3E']
            if profile=='incoming_review':rows=[r for r in rows if r['endpoint_id'].startswith('incoming:')]
        else:return super().fetch(profile,year_min,year_max)
        rows=[r for r in rows if (year_min is None or r.get('source_year') is not None and r['source_year']>=int(year_min)) and (year_max is None or r.get('source_year') is not None and r['source_year']<=int(year_max))]
        counts=collections.Counter(r['source_group'] for r in rows)
        for r in rows:r['source_weight']=1/counts[r['source_group']]
        return Dataset(profile,sorted(rows,key=lambda r:(r['source_group'],r['endpoint_id'])),list(features))

    def by_endpoint(self,endpoint_id):
        row=self.delta_v12.execute('select row_json from review_rows_v12 where endpoint_id=?',(endpoint_id,)).fetchone()
        if not row:return None
        result=json.loads(row[0]);result.pop('source_weight',None);return result

    def incoming_tests(self,document_id=None):
        if not hasattr(self,'delta_v12'):return super().incoming_tests(document_id)
        return [self.by_endpoint(r['endpoint_id']) for r in self.fetch('incoming_review').rows if not document_id or r['document_id']==document_id]

    def full_review_queue(self):
        return [r for r in self.fetch('all_review').rows if not r.get('admission_profiles_v12')]

    def pending_evidence(self):
        """Actionable/uncertain records, excluding explicit scope and method exclusions."""
        return [r for r in self.full_review_queue() if not str(r.get('review_disposition_v12','')).startswith('outside_')]

    def evidence(self,endpoint_id,field=None):
        previous=super().evidence(endpoint_id,field)
        for r in self.delta_v12.execute('select * from field_changes_v12 where endpoint_id=?',(endpoint_id,)):
            if field and r['field_name']!=field:continue
            for e in json.loads(r['evidence_json']):
                previous.append({'endpoint_id':endpoint_id,'field_name':r['field_name'],'value_json':r['after_json'],'selected':1,
                    'review_version':'v0.12','excerpt_kind':'agent_source_evidence_summary',**e})
        return previous

    def material_properties(self,material_key=None,selected_only=True):
        values=super().material_properties(material_key,selected_only)
        sql='select * from material_changes_v12';args=[]
        if material_key:sql+=' where material_key=?';args=[material_key]
        current=[dict(r) for r in self.delta_v12.execute(sql,args)]
        replaced={(r['material_key'],r['field_name']) for r in current}
        if selected_only:values=[r for r in values if (r['material_key'],r['field_name']) not in replaced]
        for r in current:
            r['value']=json.loads(r['value_json']);r['evidence']=json.loads(r.pop('evidence_json'));r['review_version']='v0.12'
            r['selected']=1;r['stage']='before_cycling';r['applies_to_systems_json']='[]';r['reviewer']='Codex agent original-source review; no human review claimed'
        return values+current

    def holds(self,endpoint_id):
        case=self.decisions_v12.get(endpoint_id)
        if not case:
            historical=super().holds(endpoint_id);row=self.by_endpoint(endpoint_id)
            return {**historical,'approved_profiles_v12':row.get('admission_profiles_v12',[]) if row else []}
        return {'open_issues':case.get('open_issues',[]),'approved_profiles':case['approved_profiles'],'disposition':case['disposition'],
                'gate_dispositions':case.get('gate_dispositions',{}),'caveats':case.get('caveats',[]),'reason':case['reason'],
                'previous_holds':super().holds(endpoint_id),'review_version':'v0.12'}

    def admission_checks(self,endpoint_id,profile=None):
        case=self.decisions_v12.get(endpoint_id)
        if not case:
            row=self.by_endpoint(endpoint_id)
            return [{'endpoint_id':endpoint_id,'profile':p,'status':'approved_for_reported_protocol' if row and p in row.get('admission_profiles_v12',[]) else 'not_approved',
                     'historical_checks':super(Database,self).admission_checks(endpoint_id,p),'review_version':'v0.12'}
                    for p in ([profile] if profile else self.contract['profiles'])]
        return [{'endpoint_id':endpoint_id,'profile':p,'status':'approved_for_reported_protocol' if p in case['approved_profiles'] else case['disposition'],
                 'evidence':case['evidence'],'review_version':'v0.12'} for p in ([profile] if profile else self.contract['profiles'])]

    def search_native(self,query,doi=None,limit=10):
        parent_result=super().search_native(query,doi,limit);result=[]
        expression=' AND '.join('"'+w.replace('"','""')+'"' for w in str(query).split())
        if not expression:return parent_result
        sql='select n.* from native_supplement_fts_v12 f join native_supplement_segments_v12 n on n.segment_id=f.rowid where native_supplement_fts_v12 match ?';args=[expression]
        if doi:sql+=' and n.doi=?';args.append(str(doi).lower().removeprefix('doi:'))
        sql+=' limit ?';args.append(int(limit))
        verified=set()
        for row in self.delta_v12.execute(sql,args):
            r=dict(row)
            if r['sha256'] not in verified:
                with (ROOT/r['path']).open('rb') as f:
                    if hashlib.file_digest(f,'sha256').hexdigest()!=r['sha256']:raise RuntimeError('Supplement fingerprint changed.')
                verified.add(r['sha256'])
            r['excerpt']=r.pop('text')[:3500];r['training_eligible']=0;r['status']='native_search_match_not_test_admission';result.append(r)
        return (result+parent_result)[:int(limit)]

    def search_tables(self,query,doi=None,limit=20):
        expression=' AND '.join('"'+w.replace('"','""')+'"' for w in str(query).split())
        if not expression:return []
        sql='''select t.*,r.row_ordinal,r.cells_json,r.row_text from native_table_fts_v12 f
               join native_table_rows_v12 r on r.row_id=f.rowid join native_tables_v12 t using(table_id)
               where native_table_fts_v12 match ?''';args=[expression]
        if doi:sql+=' and t.doi=?';args.append(str(doi).lower().removeprefix('doi:').removeprefix('https://doi.org/'))
        sql+=' order by t.table_id,r.row_ordinal limit ?';args.append(int(limit))
        current=[dict(r) for r in self.delta_v12.execute(sql,args)]
        for r in current:
            with (ROOT/r['path']).open('rb') as f:
                if hashlib.file_digest(f,'sha256').hexdigest()!=r['sha256']:raise RuntimeError('Supplement fingerprint changed.')
        return (current+super().search_tables(query,doi,limit))[:int(limit)]
