"""Read-only v0.21 feature freezes over immutable v0.20; endpoints and membership unchanged."""
from pathlib import Path
import hashlib,importlib.util,json,sqlite3,sys
ROOT=Path(__file__).resolve().parents[1];PARENT=ROOT/'循环稳定性数据库_v0.20_新增来源准入_20261025'
NAME='_cycling_v020_parent_for_v021'
if NAME not in sys.modules:
    spec=importlib.util.spec_from_file_location(NAME,PARENT/'ml_data.py');module=importlib.util.module_from_spec(spec);sys.modules[NAME]=module;spec.loader.exec_module(module)
base=sys.modules[NAME];Dataset=base.Dataset;DataNotReady=base.DataNotReady

class Database(base.Database):
    def __init__(self,path=None):
        folder=Path(__file__).resolve().parent;contract=json.loads((folder/'data_contract.json').read_text('utf8'))
        with (PARENT/'cycling_v0_20.sqlite').open('rb') as f:
            if hashlib.file_digest(f,'sha256').hexdigest()!=contract['parent_database_sha256']:raise RuntimeError('Immutable v0.20 differs.')
        super().__init__(PARENT/'cycling_v0_20.sqlite');self.root,self.contract=folder,contract
        self.path=Path(path).resolve() if path else folder/contract['database_file']
        self.delta_v21=sqlite3.connect(self.path.as_uri()+'?mode=ro',uri=True);self.delta_v21.row_factory=sqlite3.Row;self.delta_v21.execute('pragma query_only=on')
        self.freezes_v21={}
        for r in self.delta_v21.execute('select * from feature_freezes_v21 order by endpoint_id,field_name'):
            self.freezes_v21.setdefault(r['endpoint_id'],{})[r['field_name']]=dict(r,record=json.loads(r['record_json']))

    def close(self):
        if hasattr(self,'delta_v21'):self.delta_v21.close()
        super().close()

    def _apply_v21(self,previous):
        if previous is None or previous['endpoint_id'] not in getattr(self,'freezes_v21',{}):return previous
        row=json.loads(json.dumps(previous));qualifications={}
        for field,r in self.freezes_v21[row['endpoint_id']].items():
            if row.get(field)!=json.loads(r['before_json']):raise RuntimeError('Parent value no longer matches feature freeze: '+field)
            row[field]=None;row[field+'_status']='v021_conflict_original_table_vs_figure_feature_frozen'
            qualifications[field]=dict(original_parent_value=json.loads(r['before_json']),current_value=None,record=r['record'],not_zero=True)
        row['feature_freezes_v21']=qualifications
        return row

    def fetch(self,profile=None,year_min=None,year_max=None):
        old=super().fetch(profile,year_min,year_max)
        if not hasattr(self,'freezes_v21'):return old
        return Dataset(old.profile,[self._apply_v21(r) for r in old.rows],list(old.features))

    def by_endpoint(self,key):return self._apply_v21(super().by_endpoint(key))

    def holds(self,key):
        old=super().holds(key)
        if key not in getattr(self,'freezes_v21',{}):return old
        return dict(old,feature_freezes_v21={f:r['record'] for f,r in self.freezes_v21[key].items()},feature_freeze_does_not_revoke_valid_cycle_label=True,review_version='v0.21')

    def evidence(self,key,field=None):
        old=super().evidence(key,field);fields=getattr(self,'freezes_v21',{}).get(key,{})
        result=[]
        for r in old:
            if r.get('field_name') in fields:r=dict(r,currently_selected=0,selection_superseded_by='v0.21 featurefreeze; original evidence preserved')
            result.append(r)
        for name,r in fields.items():
            if field is not None and name!=field:continue
            for proof in r['record']['evidence']:result.append(dict(proof,endpoint_id=key,field_name=name,currently_selected=0,review_version='v0.21',status='competing_report_not_selected',selected_value=None))
        return result

    def field_changes(self,key=None,include_history=False):
        old=super().field_changes(key,include_history) if include_history else []
        if not hasattr(self,'delta_v21'):return old
        return old+[dict(r,before=json.loads(r['before_json']),after=None,operation='freeze_competing_material_feature',reason='Own table and originalFig3 conflict; do not selectlatest/highest or fill0',evidence=json.loads(r['record_json'])['evidence'],review_version='v0.21') for r in self.delta_v21.execute('select * from feature_freezes_v21 where (? is null or endpoint_id=?) order by endpoint_id,field_name',(key,key))]

    def material_properties(self,material_key=None,selected_only=True):
        old=super().material_properties(material_key,False)
        if not hasattr(self,'freezes_v21'):return [r for r in old if not selected_only or r.get('selected')]
        result=[]
        for r in old:
            if any(r.get('material_key')==item['material_key'] and r.get('field_name')==field for fields in self.freezes_v21.values() for field,item in fields.items()):r=dict(r,selected=0,selection_status='v021_conflict_frozen_original_property_retained')
            if not selected_only or r.get('selected'):result.append(r)
        return result
