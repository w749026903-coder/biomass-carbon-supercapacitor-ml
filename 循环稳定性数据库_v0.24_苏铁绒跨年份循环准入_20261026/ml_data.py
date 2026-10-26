"""Read-only v0.24: two 2022 Cycas tests, one source, explicit all-years review."""
from pathlib import Path
import collections,hashlib,importlib.util,json,math,sqlite3,sys
ROOT=Path(__file__).resolve().parents[1];FOLDER=Path(__file__).resolve().parent
PARENT=ROOT/'循环稳定性数据库_v0.23_跨年份端点与家族隔离_20261026';NAME='_cycling_v023_parent_for_v024'
if NAME not in sys.modules:
    spec=importlib.util.spec_from_file_location(NAME,PARENT/'ml_data.py');module=importlib.util.module_from_spec(spec);sys.modules[NAME]=module;spec.loader.exec_module(module)
base=sys.modules[NAME];DataNotReady=base.DataNotReady;family_key=base.family_key
EXTENDED={'reported_3e_all_years','reported_2e_all_years'}

class Dataset(base.Dataset):
    def feature_matrix(self):
        if self.profile not in EXTENDED:return super().feature_matrix()
        if not self.rows:raise DataNotReady('Empty reviewed cohort')
        for r in self.rows:
            if r.get('system')!=('3E'if self.profile=='reported_3e_all_years'else'2E_symmetric')or r.get('method')!='GCD':raise DataNotReady('Wrong configuration or method')
            provenance=r.get('all_years_admission_basis_v24')or r.get('all_years_admission_basis_v23')or r.get('all_years_admission_basis_v22')
            if r.get('eligible')!=1 or r.get('admission_status')!='approved_for_reported_protocol'or provenance not in['validated_legacy_profile','explicit_v022_test_review','explicit_v023_test_review','explicit_v024_test_review']:raise DataNotReady('Explicit purpose review required')
            for version in ['v23','v24']:
                if provenance=='explicit_v0'+version[1:]+'_test_review'and self.profile not in r.get('admission_profiles_'+version,[]):raise DataNotReady('No membership for this purpose')
            if r.get('metric_kind')!='capacitance_retention'or r.get('retention_relation')!='eq'or not r.get('baseline_reference'):raise DataNotReady('Own cycling target and author reference required')
            year=r.get('source_year')
            if isinstance(year,bool)or not isinstance(year,int)or not 1<=year<=2026:raise DataNotReady('Verified year required')
            for f in self.features+['retention_pct']:
                v=r.get(f)
                if f in['electrolyte','reference_electrode']:
                    if not isinstance(v,str)or not v.strip():raise DataNotReady('Missing categorical core')
                elif isinstance(v,bool)or not isinstance(v,(int,float))or not math.isfinite(v):raise DataNotReady('Missing or nonfinite numeric core')
            if any(r[f]<=0 for f in['cycle_count','reported_current_A_g','concentration_mol_L','BET_m2_g'])or r['cycle_count']<1000 or r['cycle_voltage_upper_V']<=r['cycle_voltage_lower_V']or r['retention_pct']<0:raise DataNotReady('Invalid core or target')
            if r.get('source_family_group_v23')not in[None,family_key(r['source_group'])]:raise DataNotReady('Stale source family')
        groups=[family_key(r['source_group'])for r in self.rows];counts=collections.Counter(groups)
        return dict(X=[[r[f]for f in self.features]for r in self.rows],y=[r['retention_pct']for r in self.rows],feature_names=list(self.features),groups=groups,sample_weight=[1/counts[g]for g in groups],raw_source_groups=[r['source_group']for r in self.rows],grouping_policy='v0.23 canonical DOI and explicit prior-work families retained in v0.24',current_semantics='author_reported_protocol_descriptor',all_years_scope=True,legacy_year_rule_not_changed=True,training_authorized=False)

class Database(base.Database):
    def __init__(self,path=None):
        contract=json.loads((FOLDER/'data_contract.json').read_text('utf8'))
        with(PARENT/'cycling_v0_23.sqlite').open('rb')as f:
            if hashlib.file_digest(f,'sha256').hexdigest()!=contract['parent_database_sha256']:raise RuntimeError('Immutable v0.23 differs')
        super().__init__(PARENT/'cycling_v0_23.sqlite')
        if contract['source_family_rules']!=super().source_family_rules():raise RuntimeError('Source families require an explicit new reconciliation')
        self.root,self.contract=FOLDER,contract;self.path=Path(path).resolve()if path else FOLDER/contract['database_file']
        self.delta_v24=sqlite3.connect(self.path.as_uri()+'?mode=ro',uri=True);self.delta_v24.row_factory=sqlite3.Row;self.delta_v24.execute('pragma query_only=on')
        self.rows_v24={r['endpoint_id']:json.loads(r['row_json'])for r in self.delta_v24.execute('select *from reviewed_endpoints_v24')};self.members_v24=collections.defaultdict(set)
        for r in self.delta_v24.execute('select *from profile_membership_v24'):self.members_v24[r['profile']].add(r['endpoint_id'])
    def close(self):
        if hasattr(self,'delta_v24'):self.delta_v24.close()
        super().close()
    def fetch(self,profile=None,year_min=None,year_max=None):
        old=super().fetch(profile,year_min,year_max)
        if not hasattr(self,'rows_v24'):return old
        rows={r['endpoint_id']:r for r in old.rows}
        for key,r in self.rows_v24.items():
            if old.profile!='all_review'and key not in self.members_v24.get(old.profile,set()):continue
            if year_min is not None and r['source_year']<int(year_min)or year_max is not None and r['source_year']>int(year_max):continue
            rows[key]=json.loads(json.dumps(r))
        counts=collections.Counter(family_key(r['source_group'])for r in rows.values())
        for r in rows.values():
            g=family_key(r['source_group']);r.update(source_family_group_v23=g,source_weight=1/counts[g])
            if old.profile in EXTENDED and r['endpoint_id']in self.rows_v24:r['all_years_admission_basis_v24']='explicit_v024_test_review'
        return Dataset(old.profile,sorted(rows.values(),key=lambda r:(r['source_family_group_v23'],r['endpoint_id'])),list(old.features))
    def by_endpoint(self,key):
        r=json.loads(json.dumps(self.rows_v24[key]))if key in getattr(self,'rows_v24',{})else super().by_endpoint(key)
        if r is not None:r['source_family_group_v23']=family_key(r['source_group'])
        return r
    def holds(self,key):
        if key not in getattr(self,'rows_v24',{}):return super().holds(key)
        return json.loads(self.delta_v24.execute('select review_json from reviewed_endpoints_v24 where endpoint_id=?',(key,)).fetchone()[0])
    def admission_checks(self,key,profile=None):
        if key not in getattr(self,'rows_v24',{}):return super().admission_checks(key,profile)
        return[dict(endpoint_id=key,profile=p,status='approved_for_reported_protocol'if key in self.members_v24.get(p,set())else'not_admitted_to_this_purpose',current_review=self.holds(key),review_version='v0.24')for p in([profile]if profile else self.contract['profiles'])]
    def evidence(self,key,field=None):
        if key not in getattr(self,'rows_v24',{}):return super().evidence(key,field)
        return[dict(r,currently_selected=r['selected'],value=json.loads(r['value_json']),review_version='v0.24')for r in self.delta_v24.execute('select *from evidence_v24 where endpoint_id=?and(?is null or field_name=?)order by evidence_id',(key,field,field))]
    def field_changes(self,key=None,include_history=False):
        old=super().field_changes(key,True)if include_history else[]
        if not hasattr(self,'delta_v24'):return old
        return old+[dict(r,before=json.loads(r['before_json']),after=json.loads(r['after_json']),evidence=json.loads(r['evidence_json']),review_version='v0.24')for r in self.delta_v24.execute('select *from changes_v24 where(?is null or endpoint_id=?)order by change_id',(key,key))]
    def material_properties(self,material_key=None,selected_only=True):
        old=super().material_properties(material_key,selected_only)
        if not hasattr(self,'delta_v24'):return old
        return old+[dict(r,value=json.loads(r['value_json']),evidence=json.loads(r['evidence_json']),selected=1,review_version='v0.24',stage='before_cycling',applies_to_systems_json='["3E"]')for r in self.delta_v24.execute('select *from material_fields_v24 where(?is null or material_key=?)',(material_key,material_key))]
    def literature_links(self):
        old=super().literature_links()
        if not hasattr(self,'delta_v24'):return old
        return old+[dict(r,review_version='v0.24')for r in self.delta_v24.execute('select *from literature_links_v24')]
    def source_aliases(self):
        old=super().source_aliases()
        if not hasattr(self,'rows_v24'):return old
        return old+[dict(endpoint_id=k,doi=r['source_group'][4:],source_group=r['source_group'],source_family_group=family_key(r['source_group']),alias_kind='new_reviewed_test_same_material_two_salts',review_version='v0.24')for k,r in self.rows_v24.items()]
    def feature_conflicts_v24(self):
        return[dict(r,record=json.loads(r['record_json']))for r in self.delta_v24.execute('select *from feature_conflicts_v24 order by material_key,field_name')]
