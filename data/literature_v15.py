"""Primary peel/seed and date-frond series with method-qualified composition."""
import collections,json
from data.literature_v14 import LiteratureDatabaseV14
NEW15={'10.3390/nano14100836','10.3390/nano12010122'}

class LiteratureDatabaseV15(LiteratureDatabaseV14):
    def batch15_sources(self):return[dict(r,record=json.loads(r['record_json']))for r in self.connection.execute('select *from source_reviews_v15 order by doi')]
    def batch15_decisions(self):return[dict(r,record=json.loads(r['record_json']))for r in self.connection.execute('select *from decisions_v15 order by decision_id')]
    def batch15_components(self):
        return[dict(r,record=json.loads(r['record_json']))for r in self.connection.execute('select *from xps_components_v15 order by component_id')]
    def batch15_annotations(self):return[dict(r,record=json.loads(r['record_json']))for r in self.connection.execute('select *from series_annotations_v15 order by annotation_id')]
    def batch15_figures(self):return[dict(r,record=json.loads(r['record_json']))for r in self.connection.execute('select *from figure_scope_reviews_v15 order by doi,figure_number')]
    def batch15_cycle_identity_links(self):return[dict(r,record=json.loads(r['record_json']))for r in self.connection.execute('select *from cycle_identity_links_v15 order by candidate_id')]
    def auxiliary_gcd(self,profile='3e'):
        rows=super().auxiliary_gcd(profile)
        for r in rows:
            if r['doi']not in NEW15:continue
            x=self.canonical_material_features_v13(r['doi'],r['sample_name'])
            r.update(material_features=x['values'],feature_evidence=x['provenance'],excluded_feature_reasons=x['excluded'])
        return rows
    def auxiliary_feature_rows(self,profile='3e'):
        rows=super().auxiliary_feature_rows(profile)
        for r in rows:
            if r['doi']not in NEW15:continue
            stages=[s for record in self.synthesis(doi=r['doi'],sample=r['sample_name'])for s in record['stages']]
            physical=next((s for s in stages if s['stage']=='physical_activation'),{})
            if physical:
                for k in ['temperature_C','duration_h','heating_rate_C_min','atmosphere']:r['activation_'+k]=physical.get(k)
                r['activation_agent']=physical['agent']
            r['activation_method']='physical_CO2'if physical else'chemical'
        return rows
    def batch15_matrix(self):
        rows=[r for r in self.auxiliary_feature_rows('3e')if r['doi']in NEW15]
        fields=['BET_surface_area_m2_g','total_pore_volume_cm3_g','micropore_volume_cm3_g','mesopore_volume_cm3_g','XPS_C_at_pct','XPS_N_at_pct','XPS_O_at_pct','Raman_ID_IG','current_A_g','concentration_mol_L','voltage_lower_V','voltage_upper_V','carbonization_temperature_C','carbonization_duration_h','activation_temperature_C','activation_duration_h','activation_heating_rate_C_min','activator_to_carbon_mass_ratio']
        groups=[self.isolation_group(r['source_group'])for r in rows];counts=collections.Counter(groups);X=[[r.get(f)for f in fields]for r in rows]
        return dict(target='reported_aqueous_3e_GCD_capacitance_F_g',feature_names=fields,X=X,missing_mask=[[v is None for v in rr]for rr in X],y=[r['capacitance_F_g']for r in rows],groups=groups,sample_weight=[1/counts[g]for g in groups],physical_test_groups=[next(x for x in self.capacitances()if x['observation_id']==r['observation_id'])['conditions']['physical_test_group']for r in rows],observation_ids=[r['observation_id']for r in rows],imputed=False,estimators_fitted=0,training_authorized=False,source_families=len(set(groups)),excluded_from_X=['postcycle_capacitance','cycling_retention','rate_retention','Dunn/Bode/EIS/Ragone_responses','raw_feedstock_composition','component_percentages_not_whole_surface_totals','DFT_DA_volumes_not_unified','coating_not_active_mass','unknown_carbonization_conditions'])

def open_literature_database(database=None,expected_sha256=None):return LiteratureDatabaseV15(database,expected_sha256)
