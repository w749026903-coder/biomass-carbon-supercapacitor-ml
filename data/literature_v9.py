"""Read-only systematic-series evidence; original table/figure disagreements remain visible."""
import json
from data.literature_v8 import LiteratureDatabaseV8

class LiteratureDatabaseV9(LiteratureDatabaseV8):
    def source_classifications(self):
        return [dict(r,decision=json.loads(r['decision_json'])) for r in self.connection.execute('select * from source_classifications_v9 order by doi')]

    def qualification_audits(self):
        return [dict(r,record=json.loads(r['record_json'])) for r in self.connection.execute('select * from qualification_audits_v9 order by audit_id')]

    def legacy_feature_conflicts(self):
        return [dict(r,record=json.loads(r['record_json'])) for r in self.connection.execute('select * from legacy_feature_conflicts_v9 order by endpoint_id,field_name')]

    def algae_GCD_matrix(self):
        rows=[r for r in self.auxiliary_feature_rows('3e') if r['doi']=='10.3390/molecules31132329']
        names=['current_A_g','concentration_mol_L','voltage_lower_V','voltage_upper_V','BET_surface_area_m2_g','total_pore_volume_cm3_g','XPS_N_at_pct','XPS_C_at_pct','XPS_O_at_pct','Raman_ID_IG','carbonization_temperature_C','carbonization_duration_h','activation_temperature_C','activation_duration_h','activator_to_carbon_mass_ratio']
        X=[[r.get(f) for f in names] for r in rows]
        return dict(purpose='reported_aqueous_3e_GCD_capacitance',feature_names=names,X=X,missing_mask=[[v is None for v in row] for row in X],y=[r['capacitance_F_g'] for r in rows],groups=[r['source_group'] for r in rows],sample_weight=[1/len(rows)]*len(rows),observation_ids=[r['observation_id'] for r in rows],sample_names=[r['sample_name'] for r in rows],independent_DOI_groups=len({r['source_group'] for r in rows}),training_authorized=False,estimators_fitted=0,imputed=False,limitations='18distinctcanonicalmaterial/currentreportsfromoneDOI; sameDOI5existingcyclelabelsandallotherresponsesmustbequarantined; conflictingN/Ramanmasked, no replicateindependenceorperformanceclaim.')

    def series_responses(self,doi=None):
        return [dict(r,record=json.loads(r['record_json'])) for r in self.connection.execute('''select o.*,m.doi,m.sample_name,d.path as source_path,d.sha256 as source_sha256,l.locator
        from outcome_observations_v3 o join materials m using(material_key) join table_source_links l using(table_key) join source_documents d using(document_key)
        where json_extract(o.record_json,'$.extraction_batch')='v9' and (? is null or m.doi=?) order by outcome_id''',(doi,doi))]

def open_literature_database(database=None,expected_sha256=None):return LiteratureDatabaseV9(database,expected_sha256)
