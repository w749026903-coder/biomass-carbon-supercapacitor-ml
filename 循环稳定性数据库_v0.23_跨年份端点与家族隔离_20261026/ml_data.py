"""Read-only v0.23 admissions and source-family validation groups; no fitting."""
from pathlib import Path
import collections,hashlib,importlib.util,json,math,sqlite3,sys
ROOT=Path(__file__).resolve().parents[1];FOLDER=Path(__file__).resolve().parent;PARENT=ROOT/'循环稳定性数据库_v0.22_原图循环与新增来源_20261026';NAME='_cycling_v022_parent_for_v023'
if NAME not in sys.modules:
    spec=importlib.util.spec_from_file_location(NAME,PARENT/'ml_data.py');module=importlib.util.module_from_spec(spec);sys.modules[NAME]=module;spec.loader.exec_module(module)
base=sys.modules[NAME];DataNotReady=base.DataNotReady
SOURCE_FAMILY_RULES=json.loads((FOLDER/'data_contract.json').read_text('utf8'))['source_family_rules']
def family_key(group):
    raw=str(group).strip();doi=raw.lower().removeprefix('https://doi.org/').removeprefix('http://doi.org/').removeprefix('doi:')
    if not(doi.startswith('10.')and'/'in doi):return raw
    matches=[r['isolation_group']for r in SOURCE_FAMILY_RULES if doi in[r['doi'],r['related_doi']]]
    if len(set(matches))>1:raise DataNotReady('Source family conflict requires review')
    return matches[0]if matches else'doi:'+doi
class Dataset(base.Dataset):
    def feature_matrix(self):
        for row in self.rows:
            if self.profile in row.get('admission_profiles_v23',[])and not row.get('baseline_reference'):raise DataNotReady('Reviewed v0.23 author cycling reference required')
        if self.profile not in base.EXTENDED:
            counts=collections.Counter(family_key(r['source_group'])for r in self.rows)
            projected=[dict(r,source_weight=1/counts[family_key(r['source_group'])])for r in self.rows]
            matrix=base.Dataset(self.profile,projected,list(self.features)).feature_matrix()
        else:
            if not self.rows:raise DataNotReady('Empty reviewed cohort')
            for row in self.rows:
                if row.get('system')!=('3E'if self.profile=='reported_3e_all_years'else'2E_symmetric')or row.get('method')!='GCD':raise DataNotReady('Wrong test system/method')
                provenance=row.get('all_years_admission_basis_v23')or row.get('all_years_admission_basis_v22')
                if row.get('eligible')!=1 or row.get('admission_status')!='approved_for_reported_protocol'or provenance not in['validated_legacy_profile','explicit_v022_test_review','explicit_v023_test_review']:raise DataNotReady('Explicit review required')
                if provenance=='explicit_v023_test_review'and self.profile not in row.get('admission_profiles_v23',[]):raise DataNotReady('No v0.23 membership for this purpose')
                if row.get('metric_kind')!='capacitance_retention'or row.get('retention_relation')!='eq'or not row.get('baseline_reference'):raise DataNotReady('Exact own cycling target/reference required')
                year=row.get('source_year')
                if isinstance(year,bool)or not isinstance(year,int)or not 1<=year<=2026:raise DataNotReady('Verified publication year required')
                for f in self.features+['retention_pct']:
                    value=row.get(f)
                    if f in['electrolyte','reference_electrode']:
                        if not isinstance(value,str)or not value.strip():raise DataNotReady('Missing categorical input')
                    elif isinstance(value,bool)or not isinstance(value,(int,float))or not math.isfinite(value):raise DataNotReady('Missing or nonfinite numeric core')
                if any(row[f]<=0 for f in['cycle_count','reported_current_A_g','concentration_mol_L','BET_m2_g'])or row['cycle_count']<1000 or row['cycle_voltage_upper_V']<=row['cycle_voltage_lower_V']or row['retention_pct']<0:raise DataNotReady('Invalid core/target')
            matrix=dict(X=[[r[f]for f in self.features]for r in self.rows],y=[r['retention_pct']for r in self.rows],feature_names=list(self.features),training_authorized=False,current_semantics='author_reported_protocol_descriptor',all_years_scope=True,legacy_year_rule_not_changed=True)
        groups=[family_key(r['source_group'])for r in self.rows];counts=collections.Counter(groups)
        for row,g in zip(self.rows,groups):
            if row.get('source_family_group_v23')not in[None,g]:raise DataNotReady('Stale source-family projection')
        matrix.update(groups=groups,sample_weight=[1/counts[g]for g in groups],grouping_policy='v0.23 canonical DOI plus explicitly documented prior-work families',raw_source_groups=[r['source_group']for r in self.rows],training_authorized=False)
        return matrix
    def source_folds(self,folds=5):
        groups=[family_key(r['source_group'])for r in self.rows];unique=sorted(set(groups))
        if not isinstance(folds,int)or not 2<=folds<=len(unique):raise ValueError('Need 2..N source-family folds')
        buckets=[set(unique[i::folds])for i in range(folds)]
        return[dict(train=[i for i,g in enumerate(groups)if g not in bucket],test=[i for i,g in enumerate(groups)if g in bucket])for bucket in buckets]
class Database(base.Database):
    def __init__(self,path=None):
        contract=json.loads((FOLDER/'data_contract.json').read_text('utf8'))
        if contract['source_family_rules']!=SOURCE_FAMILY_RULES:raise RuntimeError('Reload module after source-family contract change')
        with(PARENT/'cycling_v0_22.sqlite').open('rb')as f:
            if hashlib.file_digest(f,'sha256').hexdigest()!=contract['parent_database_sha256']:raise RuntimeError('Immutable v0.22 differs')
        super().__init__(PARENT/'cycling_v0_22.sqlite');self.root,self.contract=FOLDER,contract;self.path=Path(path).resolve()if path else FOLDER/contract['database_file']
        self.delta_v23=sqlite3.connect(self.path.as_uri()+'?mode=ro',uri=True);self.delta_v23.row_factory=sqlite3.Row;self.delta_v23.execute('pragma query_only=on')
        self.rows_v23={r['endpoint_id']:json.loads(r['row_json'])for r in self.delta_v23.execute('select *from reviewed_endpoints_v23')};self.members_v23=collections.defaultdict(set)
        for r in self.delta_v23.execute('select *from profile_membership_v23'):self.members_v23[r['profile']].add(r['endpoint_id'])
    def close(self):
        if hasattr(self,'delta_v23'):self.delta_v23.close()
        super().close()
    def fetch(self,profile=None,year_min=None,year_max=None):
        old=super().fetch(profile,year_min,year_max)
        if not hasattr(self,'rows_v23'):return old
        rows={r['endpoint_id']:r for r in old.rows}
        for key,row in self.rows_v23.items():
            if old.profile!='all_review'and key not in self.members_v23.get(old.profile,set()):continue
            year=row['source_year']
            if year_min is not None and year<int(year_min)or year_max is not None and year>int(year_max):continue
            rows[key]=json.loads(json.dumps(row))
        counts=collections.Counter(family_key(r['source_group'])for r in rows.values())
        for row in rows.values():
            g=family_key(row['source_group']);row.update(source_family_group_v23=g,source_weight=1/counts[g])
            if old.profile in base.EXTENDED and row['endpoint_id']in self.rows_v23:row['all_years_admission_basis_v23']='explicit_v023_test_review'
        return Dataset(old.profile,sorted(rows.values(),key=lambda r:(r['source_family_group_v23'],r['endpoint_id'])),list(old.features))
    def by_endpoint(self,key):
        row=json.loads(json.dumps(self.rows_v23[key]))if key in getattr(self,'rows_v23',{})else super().by_endpoint(key)
        if row is not None:row['source_family_group_v23']=family_key(row['source_group'])
        return row
    def holds(self,key):
        if key not in getattr(self,'rows_v23',{}):return super().holds(key)
        return json.loads(self.delta_v23.execute('select review_json from reviewed_endpoints_v23 where endpoint_id=?',(key,)).fetchone()[0])
    def admission_checks(self,key,profile=None):
        if key not in getattr(self,'rows_v23',{}):return super().admission_checks(key,profile)
        return[dict(endpoint_id=key,profile=p,status='approved_for_reported_protocol'if key in self.members_v23.get(p,set())else'not_admitted_to_this_purpose',current_review=self.holds(key),review_version='v0.23')for p in([profile]if profile else self.contract['profiles'])]
    def evidence(self,key,field=None):
        if key not in getattr(self,'rows_v23',{}):return super().evidence(key,field)
        old=super().evidence(key,field)if self.rows_v23[key].get('promoted_existing_endpoint_v23')else[]
        changed={r[0]for r in self.delta_v23.execute('select field_name from changes_v23 where endpoint_id=?and before_json!=after_json',(key,))}
        for e in old:
            if e.get('field_name')in changed:e.update(currently_selected=0,selected=0,superseded_in_v23=True)
        return old+[dict(r,currently_selected=r['selected'],value=json.loads(r['value_json']),review_version='v0.23')for r in self.delta_v23.execute('select *from evidence_v23 where endpoint_id=?and(?is null or field_name=?)order by evidence_id',(key,field,field))]
    def field_changes(self,key=None,include_history=False):
        old=super().field_changes(key,True)if include_history else[]
        if not hasattr(self,'delta_v23'):return old
        return old+[dict(r,before=json.loads(r['before_json']),after=json.loads(r['after_json']),evidence=json.loads(r['evidence_json']),review_version='v0.23')for r in self.delta_v23.execute('select *from changes_v23 where(?is null or endpoint_id=?)order by change_id',(key,key))]
    def material_properties(self,material_key=None,selected_only=True):
        old=super().material_properties(material_key,selected_only)
        if not hasattr(self,'delta_v23'):return old
        added=[dict(r,value=json.loads(r['value_json']),evidence=json.loads(r['evidence_json']),selected=1,review_version='v0.23',stage='before_cycling',applies_to_systems_json='[]')for r in self.delta_v23.execute('select *from material_fields_v23 where(?is null or material_key=?)',(material_key,material_key))];replaced={(r['material_key'],r['field_name'])for r in added}
        if selected_only:old=[r for r in old if(r['material_key'],r['field_name'])not in replaced]
        else:
            for r in old:
                if(r['material_key'],r['field_name'])in replaced:r['selected']=0;r['superseded_in_v23']=True
        return old+added
    def literature_links(self):
        old=super().literature_links()
        if not hasattr(self,'delta_v23'):return old
        return old+[dict(r,review_version='v0.23')for r in self.delta_v23.execute('select *from literature_links_v23')]
    def source_family_rules(self):return self.contract['source_family_rules']
    def source_aliases(self):
        old=super().source_aliases()
        if not hasattr(self,'rows_v23'):return old
        return old+[dict(endpoint_id=k,doi=r['source_group'].removeprefix('doi:'),source_group=r['source_group'],source_family_group=family_key(r['source_group']),alias_kind='new_reviewed_endpoint_or_existing_purpose_promotion',review_version='v0.23')for k,r in self.rows_v23.items()]
