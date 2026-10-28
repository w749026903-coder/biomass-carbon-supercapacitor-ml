"""Read-only single 2022 wheat-husk test in the existing all-years 2E purpose."""
from pathlib import Path
import collections,hashlib,importlib.util,json,math,sqlite3,sys
ROOT=Path(__file__).resolve().parents[1];FOLDER=Path(__file__).resolve().parent
PARENT=ROOT/'循环稳定性数据库_v0.27_林业含灰双电极准入_20261028';NAME='_cycling_v027_parent_for_v028'
if NAME not in sys.modules:
    spec=importlib.util.spec_from_file_location(NAME,PARENT/'ml_data.py');module=importlib.util.module_from_spec(spec);sys.modules[NAME]=module;spec.loader.exec_module(module)
base=sys.modules[NAME];DataNotReady=base.DataNotReady;family_key=base.family_key
PROFILE='reported_2e_all_years';KEY='v28:HPC700_2E_C30000';DOI='10.3390/nano12213804'

class Dataset(base.Dataset):
    def feature_matrix(self):
        current=[r for r in self.rows if r.get('review_disposition_v28')]
        if not current:return super().feature_matrix()
        others=[r for r in self.rows if not r.get('review_disposition_v28')]
        historical=base.Dataset(self.profile,others,list(self.features)).feature_matrix()if others else{}
        for r in current:
            if self.profile!=PROFILE or r.get('admission_profiles_v28')!=[PROFILE]or r.get('endpoint_id')!=KEY or r.get('source_group')!='doi:'+DOI:raise DataNotReady('One explicitly reviewed all-years 2E test required')
            if r.get('source_year')!=2022 or isinstance(r['source_year'],bool)or r.get('all_years_admission_basis_v28')!='explicit_v028_test_review':raise DataNotReady('Positive 2022 source identity and current review required')
            if r.get('eligible')!=1 or r.get('admission_status')!='approved_for_reported_protocol'or r.get('system')!='2E_symmetric'or r.get('method')!='GCD'or r.get('metric_kind')!='capacitance_retention'or r.get('retention_relation')!='eq'or not r.get('baseline_reference'):raise DataNotReady('Reviewed own GCD retention, symmetric cell and initial reference required')
            if r.get('material_scope_v28')!='biomass_derived_porous_carbon':raise DataNotReady('Own carbon material scope required')
            for f in self.features+['retention_pct']:
                v=r.get(f)
                if f=='electrolyte':
                    if not isinstance(v,str)or not v.strip():raise DataNotReady('Missing electrolyte')
                elif isinstance(v,bool)or not isinstance(v,(int,float))or not math.isfinite(v):raise DataNotReady('Missing finite numeric core')
            if any(r[f]<=0 for f in ['cycle_count','reported_current_A_g','concentration_mol_L','BET_m2_g'])or r['cycle_count']<1000 or r['retention_pct']<0 or r['cycle_voltage_upper_V']<=r['cycle_voltage_lower_V']:raise DataNotReady('Invalid label or conditions')
        groups=[family_key(r['source_group'])for r in self.rows];counts=collections.Counter(groups)
        result=dict(historical,X=[[r[f]for f in self.features]for r in self.rows],y=[r['retention_pct']for r in self.rows],groups=groups,sample_weight=[1/counts[g]for g in groups],feature_names=list(self.features),training_authorized=False,current_semantics='author_reported_protocol_descriptor',all_years_scope=True,legacy_year_rule_not_changed=True,v28_validation='Single own2022 device test; author initialreference andapplicable samecellGCDwindow, no guessedcurrentmass')
        index={r['endpoint_id']:i for i,r in enumerate(others)}
        for k,f in {'label_relations':'retention_relation','label_evidence_kind':'label_evidence_kind','label_reading_bound_pp':'label_reading_bound_pp','baseline_references':'baseline_reference'}.items():
            if k in historical:result[k]=[historical[k][index[r['endpoint_id']]]if r['endpoint_id']in index else r.get(f)for r in self.rows]
        return result

class Database(base.Database):
    def __init__(self,path=None):
        contract=json.loads((FOLDER/'data_contract.json').read_text('utf8'))
        with(PARENT/'cycling_v0_27.sqlite').open('rb')as f:
            if hashlib.file_digest(f,'sha256').hexdigest()!=contract['parent_database_sha256']:raise RuntimeError('Immutablev027 fingerprint differs')
        super().__init__(PARENT/'cycling_v0_27.sqlite');self.root,self.contract=FOLDER,contract;self.path=Path(path).resolve()if path else FOLDER/contract['database_file']
        self.delta_v28=sqlite3.connect(self.path.as_uri()+'?mode=ro',uri=True);self.delta_v28.row_factory=sqlite3.Row;self.delta_v28.execute('pragma query_only=on')
        self.rows_v28={r['endpoint_id']:json.loads(r['row_json'])for r in self.delta_v28.execute('select *from reviewed_endpoints_v28')};self.reviews_v28={r['endpoint_id']:json.loads(r['review_json'])for r in self.delta_v28.execute('select *from reviewed_endpoints_v28')}
    def close(self):
        if hasattr(self,'delta_v28'):self.delta_v28.close()
        super().close()
    def fetch(self,profile=None,year_min=None,year_max=None):
        old=super().fetch(profile,year_min,year_max)
        if not hasattr(self,'rows_v28'):return old
        rows={r['endpoint_id']:r for r in old.rows}
        if old.profile in [PROFILE,'all_review']:
            for key,r in self.rows_v28.items():
                if year_min is not None and r['source_year']<int(year_min)or year_max is not None and r['source_year']>int(year_max):continue
                rows[key]=json.loads(json.dumps(r))
        counts=collections.Counter(family_key(r['source_group'])for r in rows.values())
        for r in rows.values():r.update(source_family_group_v23=family_key(r['source_group']),source_weight=1/counts[family_key(r['source_group'])])
        return Dataset(old.profile,sorted(rows.values(),key=lambda r:(r['source_family_group_v23'],r['endpoint_id'])),list(old.features))
    def by_endpoint(self,key):return json.loads(json.dumps(self.rows_v28[key]))if key in getattr(self,'rows_v28',{})else super().by_endpoint(key)
    def holds(self,key):return json.loads(json.dumps(self.reviews_v28[key]))if key in getattr(self,'reviews_v28',{})else super().holds(key)
    def admission_checks(self,key,profile=None):
        if key not in getattr(self,'rows_v28',{}):return super().admission_checks(key,profile)
        return[dict(endpoint_id=key,profile=p,status='approved_for_reported_protocol'if p==PROFILE else'not_admitted_to_this_purpose',current_review=self.reviews_v28[key],review_version='v0.28')for p in([profile]if profile else self.contract['profiles'])]
    def evidence(self,key,field=None):
        if key not in getattr(self,'rows_v28',{}):return super().evidence(key,field)
        return[dict(r,value=json.loads(r['value_json']),currently_selected=r['selected'],review_version='v0.28')for r in self.delta_v28.execute('select *from evidence_v28 where endpoint_id=?and(?is null or field_name=?)',(key,field,field))]
    def field_changes(self,key=None,include_history=False):
        old=super().field_changes(key,True)if include_history else[]
        if not hasattr(self,'delta_v28'):return old
        return old+[dict(r,before=json.loads(r['before_json']),after=json.loads(r['after_json']),evidence=json.loads(r['evidence_json']),review_version='v0.28')for r in self.delta_v28.execute('select *from changes_v28 where(?is null or endpoint_id=?)',(key,key))]
    def literature_links(self):return super().literature_links()+([dict(r,review_version='v0.28')for r in self.delta_v28.execute('select *from literature_links_v28')]if hasattr(self,'delta_v28')else[])
