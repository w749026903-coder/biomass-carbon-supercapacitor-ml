"""Read-only five-test admission delta; v0.21 feature freezes and history preserved."""
from pathlib import Path
import hashlib,importlib.util,json,sqlite3,sys,collections,math
ROOT=Path(__file__).resolve().parents[1];PARENT=ROOT/'循环稳定性数据库_v0.21_图表冲突特征冻结_20261026';NAME='_cycling_v021_parent_for_v022'
if NAME not in sys.modules:
    spec=importlib.util.spec_from_file_location(NAME,PARENT/'ml_data.py');module=importlib.util.module_from_spec(spec);sys.modules[NAME]=module;spec.loader.exec_module(module)
base=sys.modules[NAME];DataNotReady=base.DataNotReady
EXTENDED={'reported_3e_all_years':'reported_3e','reported_2e_all_years':'reported_2e'}
class Dataset(base.Dataset):
    def feature_matrix(self):
        if self.profile not in EXTENDED:return super().feature_matrix()
        if not self.rows:raise DataNotReady('Emptyreviewedall-yearcohort')
        for row in self.rows:
            if row.get('system')!=('3E'if self.profile=='reported_3e_all_years'else'2E_symmetric')or row.get('method')!='GCD':raise DataNotReady('Wrongtestsystem/method')
            if row.get('eligible')!=1 or row.get('admission_status')!='approved_for_reported_protocol' or row.get('all_years_admission_basis_v22')not in['validated_legacy_profile','explicit_v022_test_review']:raise DataNotReady('Explicitreviewrequired')
            if row.get('metric_kind')!='capacitance_retention'or row.get('retention_relation')!='eq'or not row.get('baseline_reference'):raise DataNotReady('Exactowncyclingtarget/reference required')
            year=row.get('source_year')
            if isinstance(year,bool)or not isinstance(year,int)or not 1<=year<=2026:raise DataNotReady('Verifiedpublicationyearrequired')
            for f in self.features+['retention_pct']:
                v=row.get(f)
                if f in['electrolyte','reference_electrode']:
                    if not isinstance(v,str)or not v.strip():raise DataNotReady('Missingcategory')
                elif isinstance(v,bool)or not isinstance(v,(int,float))or not math.isfinite(v):raise DataNotReady('Missingnumericcore')
            if any(row[f]<=0 for f in['cycle_count','reported_current_A_g','concentration_mol_L','BET_m2_g'])or row['cycle_count']<1000 or row['cycle_voltage_upper_V']<=row['cycle_voltage_lower_V']or row['retention_pct']<0:raise DataNotReady('Invalidcore/target')
        return dict(X=[[r[f]for f in self.features]for r in self.rows],y=[r['retention_pct']for r in self.rows],groups=[r['source_group']for r in self.rows],sample_weight=[r['source_weight']for r in self.rows],feature_names=self.features,training_authorized=False,current_semantics='author_reported_protocol_descriptor',all_years_scope=True,legacy_year_rule_not_changed=True)
class Database(base.Database):
    def __init__(self,path=None):
        folder=Path(__file__).resolve().parent;contract=json.loads((folder/'data_contract.json').read_text('utf8'))
        with(PARENT/'cycling_v0_21.sqlite').open('rb')as f:
            if hashlib.file_digest(f,'sha256').hexdigest()!=contract['parent_database_sha256']:raise RuntimeError('Immutablev0.21differs')
        super().__init__(PARENT/'cycling_v0_21.sqlite');self.root,self.contract=folder,contract;self.path=Path(path).resolve()if path else folder/contract['database_file']
        self.delta_v22=sqlite3.connect(self.path.as_uri()+'?mode=ro',uri=True);self.delta_v22.row_factory=sqlite3.Row;self.delta_v22.execute('pragma query_only=on')
        self.rows_v22={r['endpoint_id']:json.loads(r['row_json'])for r in self.delta_v22.execute('select *from reviewed_endpoints_v22')};self.members_v22=collections.defaultdict(set)
        for r in self.delta_v22.execute('select *from profile_membership_v22'):self.members_v22[r['profile']].add(r['endpoint_id'])
    def close(self):
        if hasattr(self,'delta_v22'):self.delta_v22.close()
        super().close()
    def fetch(self,profile=None,year_min=None,year_max=None):
        requested=profile;old=super().fetch(EXTENDED.get(profile,profile),year_min,year_max)
        if not hasattr(self,'rows_v22'):return old
        if requested in EXTENDED and old.rows:old.feature_matrix()
        selected=requested if requested in EXTENDED else old.profile
        rows={r['endpoint_id']:r for r in old.rows}
        for key,stored in self.rows_v22.items():
            if selected!='all_review'and key not in self.members_v22.get(selected,set()):continue
            year=stored.get('source_year')
            if year_min is not None and(year is None or year<int(year_min)):continue
            if year_max is not None and(year is None or year>int(year_max)):continue
            rows[key]=json.loads(json.dumps(stored))
        counts=collections.Counter(r['source_group']for r in rows.values())
        for r in rows.values():
            r['source_weight']=1/counts[r['source_group']]
            if selected in EXTENDED:r['all_years_admission_basis_v22']='explicit_v022_test_review'if r['endpoint_id']in self.rows_v22 else'validated_legacy_profile'
        return Dataset(selected,sorted(rows.values(),key=lambda r:(r['source_group'],r['endpoint_id'])),list(old.features))
    def by_endpoint(self,key):
        if key in getattr(self,'rows_v22',{}):return json.loads(json.dumps(self.rows_v22[key]))
        return super().by_endpoint(key)
    def holds(self,key):
        if key not in getattr(self,'rows_v22',{}):return super().holds(key)
        return json.loads(self.delta_v22.execute('select review_json from reviewed_endpoints_v22 where endpoint_id=?',(key,)).fetchone()[0])
    def admission_checks(self,key,profile=None):
        if key not in getattr(self,'rows_v22',{}):return super().admission_checks(key,profile)
        return[dict(endpoint_id=key,profile=p,status='approved_for_reported_protocol'if key in self.members_v22.get(p,set())else'not_admitted_to_this_purpose',current_review=self.holds(key),review_version='v0.22',historical_checks=[])for p in([profile]if profile else self.contract['profiles'])]
    def evidence(self,key,field=None):
        if key not in getattr(self,'rows_v22',{}):return super().evidence(key,field)
        old=super().evidence(key,field)if self.rows_v22[key].get('promoted_existing_endpoint_v22')else[]
        return old+[dict(r,currently_selected=r['selected'],value=json.loads(r['value_json']),review_version='v0.22')for r in self.delta_v22.execute('select *from evidence_v22 where endpoint_id=?and(?is null or field_name=?)order by evidence_id',(key,field,field))]
    def field_changes(self,key=None,include_history=False):
        old=super().field_changes(key,True)if include_history else[]
        if not hasattr(self,'delta_v22'):return old
        return old+[dict(r,before=json.loads(r['before_json']),after=json.loads(r['after_json']),evidence=json.loads(r['evidence_json']),review_version='v0.22')for r in self.delta_v22.execute('select *from changes_v22 where(?is null or endpoint_id=?)order by change_id',(key,key))]
    def material_properties(self,material_key=None,selected_only=True):
        old=super().material_properties(material_key,selected_only)
        if not hasattr(self,'delta_v22'):return old
        added=[dict(r,value=json.loads(r['value_json']),evidence=json.loads(r['evidence_json']),selected=1,review_version='v0.22',stage='before_cycling',applies_to_systems_json='[]')for r in self.delta_v22.execute('select *from material_fields_v22 where(?is null or material_key=?)',(material_key,material_key))]
        replaced={(r['material_key'],r['field_name'])for r in added}
        if selected_only:old=[r for r in old if(r['material_key'],r['field_name'])not in replaced]
        else:
            for r in old:
                if(r['material_key'],r['field_name'])in replaced:r['selected']=0;r['superseded_in_v22']=True
        return old+added
    def literature_links(self):
        old=super().literature_links()
        if not hasattr(self,'delta_v22'):return old
        return old+[dict(r,review_version='v0.22')for r in self.delta_v22.execute('select *from literature_links_v22')]
    def source_aliases(self):
        old=super().source_aliases()
        if not hasattr(self,'rows_v22'):return old
        return old+[dict(endpoint_id=k,doi=r['source_group'].removeprefix('doi:'),source_group=r['source_group'],alias_kind='new_reviewed_endpoint_or_existing_promotion',review_version='v0.22')for k,r in self.rows_v22.items()]
