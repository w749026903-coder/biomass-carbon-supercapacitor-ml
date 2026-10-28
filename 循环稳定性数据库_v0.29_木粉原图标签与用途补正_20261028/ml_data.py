"""Read-only actual-figure selection over three existing wood test IDs; old values retained."""
from pathlib import Path
import collections,hashlib,importlib.util,json,math,sqlite3,sys
ROOT=Path(__file__).resolve().parents[1];FOLDER=Path(__file__).resolve().parent
PARENT=ROOT/'循环稳定性数据库_v0.28_麦壳跨年份器件循环准入_20261028';NAME='_cycling_v028_parent_for_v029'
if NAME not in sys.modules:
    spec=importlib.util.spec_from_file_location(NAME,PARENT/'ml_data.py');module=importlib.util.module_from_spec(spec);sys.modules[NAME]=module;spec.loader.exec_module(module)
base=sys.modules[NAME];DataNotReady=base.DataNotReady;family_key=base.family_key
PROFILES=['reported_3e','reported_3e_residue_sensitivity','reported_3e_sensitivity','reported_3e_all_years']
APPROVED={'candidate:TE037','candidate:TE038'}
class Dataset(base.Dataset):
    def feature_matrix(self):
        current=[r for r in self.rows if r.get('review_disposition_v29')]
        if not current:return super().feature_matrix()
        others=[r for r in self.rows if not r.get('review_disposition_v29')];historical=base.Dataset(self.profile,others,list(self.features)).feature_matrix()if others else{}
        for r in current:
            if r.get('endpoint_id')not in APPROVED or self.profile not in PROFILES or self.profile not in r.get('admission_profiles_v29',[])or r.get('eligible')!=1 or r.get('admission_status')!='approved_for_reported_protocol':raise DataNotReady('Explicit source-specific current-purpose review required; AC500 remains unadmitted')
            if r.get('source_group')!='doi:10.1016/j.heliyon.2024.e25628'or r.get('source_year')!=2024 or isinstance(r['source_year'],bool)or r.get('system')!='3E'or r.get('method')!='GCD'or r.get('metric_kind')!='capacitance_retention'or r.get('retention_relation')!='eq'or not r.get('baseline_reference'):raise DataNotReady('Own verified 2024 three-electrode GCD endpoint and initial reference required')
            for f in self.features+['retention_pct']:
                v=r.get(f)
                if f in ['electrolyte','reference_electrode']:
                    if not isinstance(v,str)or not v.strip():raise DataNotReady('Missing category')
                elif isinstance(v,bool)or not isinstance(v,(int,float))or not math.isfinite(v):raise DataNotReady('Missing numeric core')
            if any(r[f]<=0 for f in ['cycle_count','reported_current_A_g','concentration_mol_L','BET_m2_g'])or r['cycle_count']<1000 or r['cycle_voltage_upper_V']<=r['cycle_voltage_lower_V']or r['retention_pct']<0:raise DataNotReady('Invalid core or target')
        groups=[family_key(r['source_group'])for r in self.rows];counts=collections.Counter(groups);result=dict(historical,X=[[r[f]for f in self.features]for r in self.rows],y=[r['retention_pct']for r in self.rows],groups=groups,sample_weight=[1/counts[g]for g in groups],feature_names=list(self.features),training_authorized=False,current_semantics='author_reported_protocol_descriptor',v29_validation='SpecificactualFig10printedendpoints; no loss-complement substitution, history preserved')
        if self.profile=='reported_3e_all_years':result.update(all_years_scope=True,legacy_year_rule_not_changed=True)
        index={r['endpoint_id']:i for i,r in enumerate(others)}
        for k,f in {'label_relations':'retention_relation','label_evidence_kind':'label_evidence_kind','label_reading_bound_pp':'label_reading_bound_pp','baseline_references':'baseline_reference'}.items():
            if k in historical:result[k]=[historical[k][index[r['endpoint_id']]]if r['endpoint_id']in index else r.get(f)for r in self.rows]
        return result
class Database(base.Database):
    def __init__(self,path=None):
        contract=json.loads((FOLDER/'data_contract.json').read_text('utf8'))
        with(PARENT/'cycling_v0_28.sqlite').open('rb')as f:
            if hashlib.file_digest(f,'sha256').hexdigest()!=contract['parent_database_sha256']:raise RuntimeError('Immutablev028 fingerprint differs')
        super().__init__(PARENT/'cycling_v0_28.sqlite');self.root,self.contract=FOLDER,contract;self.path=Path(path).resolve()if path else FOLDER/contract['database_file']
        self.delta_v29=sqlite3.connect(self.path.as_uri()+'?mode=ro',uri=True);self.delta_v29.row_factory=sqlite3.Row;self.delta_v29.execute('pragma query_only=on')
        self.rows_v29={r['endpoint_id']:json.loads(r['row_json'])for r in self.delta_v29.execute('select *from reviewed_endpoints_v29')};self.reviews_v29={r['endpoint_id']:json.loads(r['review_json'])for r in self.delta_v29.execute('select *from reviewed_endpoints_v29')};self.members_v29=collections.defaultdict(set)
        for r in self.delta_v29.execute('select *from profile_membership_v29'):self.members_v29[r['profile']].add(r['endpoint_id'])
    def close(self):
        if hasattr(self,'delta_v29'):self.delta_v29.close()
        super().close()
    def fetch(self,profile=None,year_min=None,year_max=None):
        old=super().fetch(profile,year_min,year_max)
        if not hasattr(self,'rows_v29'):return old
        rows={r['endpoint_id']:r for r in old.rows if r['endpoint_id']not in self.rows_v29}
        for key,r in self.rows_v29.items():
            if old.profile!='all_review'and key not in self.members_v29.get(old.profile,set()):continue
            if year_min is not None and r['source_year']<int(year_min)or year_max is not None and r['source_year']>int(year_max):continue
            rows[key]=json.loads(json.dumps(r))
        counts=collections.Counter(family_key(r['source_group'])for r in rows.values())
        for r in rows.values():r.update(source_family_group_v23=family_key(r['source_group']),source_weight=1/counts[family_key(r['source_group'])])
        return Dataset(old.profile,sorted(rows.values(),key=lambda r:(r['source_family_group_v23'],r['endpoint_id'])),list(old.features))
    def by_endpoint(self,key):return json.loads(json.dumps(self.rows_v29[key]))if key in getattr(self,'rows_v29',{})else super().by_endpoint(key)
    def holds(self,key):
        if key not in getattr(self,'reviews_v29',{}):return super().holds(key)
        return dict(self.reviews_v29[key],previous_holds=super().holds(key))
    def reviewed_pending_batch(self,include_outside=False):
        rows=[dict(getattr(self,'reviews_v29',{}).get(r['endpoint_id'],r))for r in super().reviewed_pending_batch(True)]
        return rows if include_outside else[r for r in rows if not r['disposition'].startswith(('approved_','outside_'))]
    def admission_checks(self,key,profile=None):
        if key not in getattr(self,'rows_v29',{}):return super().admission_checks(key,profile)
        return[dict(endpoint_id=key,profile=p,status='approved_for_reported_protocol'if key in self.members_v29.get(p,set())else'pending_own_numeric_BET'if key=='candidate:TE036'and p in PROFILES else'not_admitted_to_this_purpose',current_review=self.reviews_v29[key],review_version='v0.29')for p in([profile]if profile else self.contract['profiles'])]
    def evidence(self,key,field=None):
        old=super().evidence(key,field)
        if key not in getattr(self,'rows_v29',{}):return old
        selected={r[0]for r in self.delta_v29.execute('select field_name from evidence_v29 where endpoint_id=?and selected=1',(key,))};old=[dict(r,currently_selected=0,superseded_by_v29=True)if r.get('field_name')in selected else r for r in old]
        return old+[dict(r,value=json.loads(r['value_json']),currently_selected=r['selected'],review_version='v0.29')for r in self.delta_v29.execute('select *from evidence_v29 where endpoint_id=?and(?is null or field_name=?)',(key,field,field))]
    def field_changes(self,key=None,include_history=False):
        old=super().field_changes(key,True)if include_history else[]
        if not hasattr(self,'delta_v29'):return old
        return old+[dict(r,before=json.loads(r['before_json']),after=json.loads(r['after_json']),evidence=json.loads(r['evidence_json']),review_version='v0.29')for r in self.delta_v29.execute('select *from changes_v29 where(?is null or endpoint_id=?)',(key,key))]
    def literature_links(self):return super().literature_links()+([dict(r,review_version='v0.29')for r in self.delta_v29.execute('select *from literature_links_v29')]if hasattr(self,'delta_v29')else[])
    def reviewed_preparation_rows_v29(self,include_pending=False):
        mapping={'carbonization_temperature_C':'carbonization_temperature_C','carbonization_duration_h':'carbonization_duration_h','carbonization_N2_flow_mL_min':'carbonization_N2_flow_mL_min_v29','wetting_temperature_C':'wetting_temperature_C_v29','wetting_duration_h':'wetting_duration_h_v29','preheat_temperature_C':'preheat_temperature_C_v29','preheat_duration_h':'preheat_duration_h_v29'}
        rows=[]
        for key,r in sorted(self.rows_v29.items()):
            if not include_pending and r['eligible']!=1:continue
            rows.append(dict(endpoint_id=key,sample_name=r['sample_name'],source_group=r['source_group'],source_family_group=family_key(r['source_group']),preparation_values={f:r.get(raw)for f,raw in mapping.items()},source_field_map=dict(mapping),carbonization_atmosphere='N2',phase='joint_phosphoric_activation_carbonization',cycling_purpose_eligible=bool(r['eligible']),literature_material_key=r['literature_material_key_v29'],evidence=[e for e in self.evidence(key)if e.get('review_version')=='v0.29'and e['field_name']in list(mapping.values())+['carbonization_atmosphere_v29']],coverage_note='This incremental preparation export covers oneDOI only; no automatic append/imputation to legacy material matrix or inference of loading/massratio.',model_fits=0))
        return rows
