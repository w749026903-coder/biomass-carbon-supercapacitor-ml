"""Read-only v0.27: existing three forest endpoints, residue sensitivity only."""
from pathlib import Path
import collections,hashlib,importlib.util,json,math,sqlite3,sys
ROOT=Path(__file__).resolve().parents[1];FOLDER=Path(__file__).resolve().parent
PARENT=ROOT/'循环稳定性数据库_v0.26_蛋米循环电流补正_20261027';NAME='_cycling_v026_parent_for_v027'
if NAME not in sys.modules:
    spec=importlib.util.spec_from_file_location(NAME,PARENT/'ml_data.py');module=importlib.util.module_from_spec(spec);sys.modules[NAME]=module;spec.loader.exec_module(module)
base=sys.modules[NAME];DataNotReady=base.DataNotReady;family_key=base.family_key
PROFILES=['reported_2e_residue','reported_2e_approx']
class Dataset(base.Dataset):
    def feature_matrix(self):
        current=[r for r in self.rows if r.get('review_disposition_v27')]
        if not current:return super().feature_matrix()
        others=[r for r in self.rows if not r.get('review_disposition_v27')]
        historical=base.Dataset(self.profile,others,list(self.features)).feature_matrix()if others else{}
        for r in current:
            if self.profile not in PROFILES or self.profile not in r.get('admission_profiles_v27',[])or r.get('eligible')!=1:raise DataNotReady('Explicit v0.27 residue-purpose membership required')
            if r.get('admission_status')!='approved_for_reported_protocol'or r.get('system')!='2E_symmetric'or r.get('method')!='GCD'or r.get('metric_kind')!='capacitance_retention'or r.get('retention_relation')!='eq'or not r.get('baseline_reference'):raise DataNotReady('Reviewed own cycling target, system and author reference required')
            if r.get('material_scope_v27')!='biomass_carbon_with_author_reported_ash_AlOH3_impurity'or not r.get('ordinary_2e_excluded_v27'):raise DataNotReady('Keep actual inorganic residue scope separate')
            year=r.get('source_year')
            if isinstance(year,bool)or not isinstance(year,int)or not 2023<=year<=2026:raise DataNotReady('Current declared year scope required')
            for f in self.features+['retention_pct']:
                v=r.get(f)
                if f=='electrolyte':
                    if not isinstance(v,str)or not v.strip():raise DataNotReady('Missing electrolyte identity')
                elif isinstance(v,bool)or not isinstance(v,(int,float))or not math.isfinite(v):raise DataNotReady('Missing finite numeric core')
            if any(r[f]<=0 for f in ['cycle_count','reported_current_A_g','concentration_mol_L','BET_m2_g'])or r['cycle_count']<1000 or r['cycle_voltage_upper_V']<=r['cycle_voltage_lower_V']or r['retention_pct']<0:raise DataNotReady('Invalid condition or cycling label')
        groups=[family_key(r['source_group'])for r in self.rows];counts=collections.Counter(groups)
        result=dict(X=[[r[f]for f in self.features]for r in self.rows],y=[r['retention_pct']for r in self.rows],groups=groups,sample_weight=[1/counts[g]for g in groups],feature_names=list(self.features),training_authorized=False,current_semantics='author_reported_protocol_descriptor',raw_source_groups=[r['source_group']for r in self.rows],grouping_policy='SameDOI andexplicitpriorworkfamily, all materials/conditions/auxiliarylabels quarantined together',v27_validation='Three existing source-bound exact endpoints in alreadydeclared residueinclusive purpose; ordinaryprofiles unchanged')
        index={r['endpoint_id']:i for i,r in enumerate(others)}
        fields={'label_relations':'retention_relation','label_evidence_kind':'label_evidence_kind','label_reading_bound_pp':'label_reading_bound_pp','baseline_references':'baseline_reference'}
        for k,f in fields.items():
            if k in historical:result[k]=[historical[k][index[r['endpoint_id']]]if r['endpoint_id']in index else r.get(f)for r in self.rows]
        return result
class Database(base.Database):
    def __init__(self,path=None):
        contract=json.loads((FOLDER/'data_contract.json').read_text('utf8'))
        with(PARENT/'cycling_v0_26.sqlite').open('rb')as f:
            if hashlib.file_digest(f,'sha256').hexdigest()!=contract['parent_database_sha256']:raise RuntimeError('Immutablev026fingerprint differs')
        super().__init__(PARENT/'cycling_v0_26.sqlite');self.root,self.contract=FOLDER,contract;self.path=Path(path).resolve()if path else FOLDER/contract['database_file']
        self.delta_v27=sqlite3.connect(self.path.as_uri()+'?mode=ro',uri=True);self.delta_v27.row_factory=sqlite3.Row;self.delta_v27.execute('pragma query_only=on')
        self.rows_v27={r['endpoint_id']:json.loads(r['row_json'])for r in self.delta_v27.execute('select *from reviewed_endpoints_v27')};self.reviews_v27={r['endpoint_id']:json.loads(r['review_json'])for r in self.delta_v27.execute('select *from reviewed_endpoints_v27')};self.members_v27=collections.defaultdict(set)
        for r in self.delta_v27.execute('select *from profile_membership_v27'):self.members_v27[r['profile']].add(r['endpoint_id'])
    def close(self):
        if hasattr(self,'delta_v27'):self.delta_v27.close()
        super().close()
    def fetch(self,profile=None,year_min=None,year_max=None):
        old=super().fetch(profile,year_min,year_max)
        if not hasattr(self,'rows_v27'):return old
        rows={r['endpoint_id']:r for r in old.rows if r['endpoint_id']not in self.rows_v27}
        for key,r in self.rows_v27.items():
            if old.profile!='all_review'and key not in self.members_v27.get(old.profile,set()):continue
            if year_min is not None and r['source_year']<int(year_min)or year_max is not None and r['source_year']>int(year_max):continue
            rows[key]=json.loads(json.dumps(r))
        counts=collections.Counter(family_key(r['source_group'])for r in rows.values())
        for r in rows.values():r.update(source_family_group_v23=family_key(r['source_group']),source_weight=1/counts[family_key(r['source_group'])])
        return Dataset(old.profile,sorted(rows.values(),key=lambda r:(r['source_family_group_v23'],r['endpoint_id'])),list(old.features))
    def by_endpoint(self,key):return json.loads(json.dumps(self.rows_v27[key]))if key in getattr(self,'rows_v27',{})else super().by_endpoint(key)
    def holds(self,key):
        if key not in getattr(self,'reviews_v27',{}):return super().holds(key)
        return dict(self.reviews_v27[key],previous_holds=super().holds(key))
    def admission_checks(self,key,profile=None):
        if key not in getattr(self,'reviews_v27',{}):return super().admission_checks(key,profile)
        return[dict(endpoint_id=key,profile=p,status='approved_for_reported_protocol'if key in self.members_v27.get(p,set())else'not_admitted_to_this_purpose',current_review=self.reviews_v27[key],review_version='v0.27')for p in([profile]if profile else self.contract['profiles'])]
    def evidence(self,key,field=None):
        old=super().evidence(key,field)
        if key not in getattr(self,'rows_v27',{}):return old
        changed={'BET_m2_g','cycle_voltage_lower_V','cycle_voltage_upper_V','baseline_reference'}
        old=[dict(r,currently_selected=0,superseded_by_v27=True)if r.get('field_name')in changed else r for r in old]
        return old+[dict(r,value=json.loads(r['value_json']),currently_selected=r['selected'],review_version='v0.27')for r in self.delta_v27.execute('select *from evidence_v27 where endpoint_id=?and(?is null or field_name=?)',(key,field,field))]
    def field_changes(self,key=None,include_history=False):
        old=super().field_changes(key,True)if include_history else[]
        if not hasattr(self,'delta_v27'):return old
        return old+[dict(r,before=json.loads(r['before_json']),after=json.loads(r['after_json']),evidence=json.loads(r['evidence_json']),review_version='v0.27')for r in self.delta_v27.execute('select *from changes_v27 where(?is null or endpoint_id=?)',(key,key))]
    def literature_links(self):return super().literature_links()+([dict(r,review_version='v0.27')for r in self.delta_v27.execute('select *from literature_links_v27')]if hasattr(self,'delta_v27')else[])
