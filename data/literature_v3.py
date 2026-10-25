"""Read-only reviewed literature, synthesis stages and purpose-specific GCD inputs."""
import json,hashlib,sqlite3
from pathlib import Path
from data.literature_v2 import LiteratureDatabaseV2
ROOT=Path(__file__).resolve().parents[1]

class LiteratureDatabaseV3(LiteratureDatabaseV2):
    def __init__(self,database=None,expected_sha256=None):
        if database is None:
            super().__init__();return
        path=Path(database).resolve()
        if ROOT not in path.parents or expected_sha256 is None:raise ValueError('Explicit version must stay in project and provide its expected SHA256.')
        with path.open('rb') as stream:
            if hashlib.file_digest(stream,'sha256').hexdigest()!=expected_sha256:raise RuntimeError('Explicit literature version fingerprint differs.')
        self.path=path;self.connection=sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)
        self.connection.row_factory=sqlite3.Row;self.connection.execute('pragma query_only=on')
    def synthesis(self,doi=None,sample=None):
        rows=self.connection.execute('''select s.*,m.doi,m.sample_name,d.path as source_path,d.sha256
          from synthesis_stages_v3 s join materials m using(material_key)
          join source_documents d using(document_key)
          where (? is null or m.doi=?) and (? is null or m.sample_name=?) order by m.doi,m.sample_name''',(doi,doi,sample,sample))
        return [dict(r,stages=json.loads(r['stages_json'])) for r in rows]

    def outcomes(self,metric=None):
        rows=[]
        for r in self.connection.execute('select * from outcome_observations_v3 order by outcome_id'):
            record=json.loads(r['record_json'])
            if metric is None or record['metric']==metric:rows.append(dict(r,record=record))
        return rows

    def auxiliary_gcd(self,profile='3e'):
        purposes={'3e':'reported_aqueous_3e_GCD_capacitance','2e_device':'reported_aqueous_2e_GCD_device_capacitance'}
        if profile not in purposes:raise ValueError('Use3e or2e_device;the two targets must remain separate.')
        rows=self.connection.execute('''select x.*,d.path as source_path,d.sha256 as source_sha256,l.locator
           from auxiliary_reported_GCD_v3 x join table_source_links l using(table_key)
           join source_documents d using(document_key) where x.purpose=? order by x.source_group,x.sample_name,x.current_A_g''',(purposes[profile],))
        result=[]
        for r in rows:
            item=dict(r);item['conditions']=json.loads(item['conditions_json']);item['auxiliary_input_ready']=True
            item['raw_candidate_training_eligible']=item.pop('training_eligible')
            item['target_name']='reported_3e_capacitance_F_g' if profile=='3e' else 'reported_2e_device_capacitance_F_g'
            item['capacitance_F_g']=item['value']
            evidence=self.facts(doi=item['doi'],sample=item['sample_name'])
            good=[f for f in evidence if f['value'] is not None and 'conflict' not in f['review_status']]
            coupled=set()
            if item['doi']=='10.1021/acsomega.5c06396' and item['sample_name']=='C-MNS':
                coupled={'mesopore_volume_cm3_g','mesopore_volume_fraction_pct','micro_to_meso_pore_volume_ratio'}
            features={f['field_name']:f['value'] for f in good if f['field_name'] not in coupled}
            item['excluded_feature_reasons']={f:'Coupled to unresolved own Table1 mesopore-volume conflict.' for f in sorted(coupled)}
            item['material_features']=features
            if 'Raman_IG_ID' in features and 'Raman_ID_IG' not in features:
                item['derived_features']={'Raman_ID_IG_from_reported_IG_ID':1/features['Raman_IG_ID']}
            else:item['derived_features']={}
            item['synthesis']=self.synthesis(doi=item['doi'],sample=item['sample_name'])
            item['feature_boundary']='Pretest material/process and bound protocol only. Same-test CE,cycling retention,energy/power,or other capacitance labels are not material features.'
            item['scientific_goal_complete']=False
            result.append(item)
        return result

    def auxiliary_feature_rows(self,profile='3e'):
        fields=['BET_surface_area_m2_g','total_pore_volume_cm3_g','micropore_volume_cm3_g','mesopore_volume_cm3_g','XPS_C_at_pct','XPS_N_at_pct','XPS_O_at_pct','Raman_ID_IG','Raman_IG_ID']
        result=[]
        for item in self.auxiliary_gcd(profile):
            row={key:item[key] for key in ['observation_id','source_group','doi','sample_name','target_name','capacitance_F_g','current_A_g','electrolyte','concentration_mol_L','source_path','source_sha256','locator']}
            row['purpose']=item['purpose'];row['capacitance_basis']=item['conditions'].get('capacitance_basis','author_reported');row['current_mass_basis']='author_reported_not_further_unified'
            for field in fields:row[field]=item['material_features'].get(field)
            stages=[stage for record in item['synthesis'] for stage in record['stages']]
            carbon=next((s for s in stages if s['stage']=='carbonization'),{})
            activation=next((s for s in stages if s['stage'] in ['chemical_activation','direct_KOH_activation']),{})
            for field in ['temperature_C','duration_h','heating_rate_C_min','atmosphere']:row['carbonization_'+field]=carbon.get(field);row['activation_'+field]=activation.get(field)
            row['activation_agent']=activation.get('agent');ratio=activation.get('carbon_to_activator_mass_ratio')
            row['activator_to_carbon_mass_ratio']=ratio[1]/ratio[0] if ratio else None
            row['Raman_ID_IG_derived_from_IG_ID']=item['derived_features'].get('Raman_ID_IG_from_reported_IG_ID')
            row['voltage_lower_V']=item['conditions'].get('voltage_lower_V');row['voltage_upper_V']=item['conditions'].get('voltage_upper_V')
            for field in fields:row[field+'_is_missing']=row[field] is None
            result.append(row)
        return result

def open_literature_database(database=None,expected_sha256=None):return LiteratureDatabaseV3(database,expected_sha256)
