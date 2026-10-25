"""Read-only Onion and biochar/PAN evidence with explicit material classes and curve uncertainty."""
import json,types
from data.literature_v7 import LiteratureDatabaseV7
from data.literature_groups import source_grouped_candidates
ONION='10.1016/j.heliyon.2024.e32915';GELS='10.3390/gels10010082'

class LiteratureDatabaseV8(LiteratureDatabaseV7):
    def tests(self):
        raw=super().tests()
        return source_grouped_candidates(types.SimpleNamespace(tests=lambda:raw,materials=self.materials))

    def material_scopes(self,doi=None):
        return [dict(r,scope=json.loads(r['scope_json'])) for r in self.connection.execute('''
          select s.*,m.doi,m.sample_name from material_scopes_v8 s join materials m using(material_key)
          where (? is null or m.doi=?) order by m.doi,m.sample_name''',(doi,doi))]

    def sampled_curves(self,doi=None,sample=None):
        return [dict(r,reading=json.loads(r['reading_json'])) for r in self.connection.execute('''
          select s.*,m.doi,m.sample_name,d.path as source_path,d.sha256 as source_sha256
          from curve_samples_v8 s join materials m using(material_key) join source_documents d using(document_key)
          where (? is null or m.doi=?) and (? is null or m.sample_name=?) order by s.reading_id''',(doi,doi,sample,sample))]

    def ratio_audits(self):
        return [dict(r,audit=json.loads(r['audit_json'])) for r in self.connection.execute('select * from ratio_audits_v8 order by audit_id')]

    def new_source_responses(self,doi=None):
        return [dict(r,record=json.loads(r['record_json'])) for r in self.connection.execute('''
          select o.*,s.doi,d.path as source_path,d.sha256 as source_sha256,l.locator
          from outcome_observations_v3 o join table_source_links l using(table_key)
          join reviewed_tables s using(table_key) join source_documents d using(document_key)
          where json_extract(o.record_json,'$.extraction_batch')='v8' and (? is null or s.doi=?) order by outcome_id''',(doi,doi))]

    def composite_cycle_inputs(self):
        rows=[]
        for review in self.connection.execute('select * from purpose_reviews_v8 where eligible=1'):
            candidate=next(r for r in self.tests() if r['candidate_id']==review['candidate_id']);r=candidate['record'];sample=self.connection.execute('select sample_name from materials where material_key=?',(candidate['material_key'],)).fetchone()[0]
            facts=self.facts(doi=GELS,sample=sample);grouped={}
            for f in facts:grouped.setdefault(f['field_name'],[]).append(f)
            row=dict(candidate_id=candidate['candidate_id'],doi=GELS,sample_name=sample,source_group=r['source_group'],purpose=review['purpose'],purpose_reviewed_input_ready=True,ordinary_biomass_cycling_admitted=False,training_authorized=False,target_retention_pct=r['retention_pct'],cycle_count=r['cycle_count'],reported_current_A_g=r['reported_current_A_g'],current_mass_basis=r['current_mass_basis'],cycle_voltage_lower_V=0,cycle_voltage_upper_V=1,electrolyte='H2SO4',concentration_mol_L=1,system='2E_symmetric',baseline_index=None,baseline_reference=r['baseline_reference'],intentional_PAN_biochar_composite=True,final_biochar_fraction=None,biochar_fraction_status='precursor recipes explicit; final carbon fractions not reported',source_balanced_weight=1,review=json.loads(review['review_json']))
            for field in ['BET_surface_area_m2_g','micropore_volume_cm3_g','mesopore_volume_cm3_g','macropore_volume_cm3_g','total_pore_volume_cm3_g','Raman_IG_ID','XPS_F_at_pct']:
                values={f['value'] for f in grouped.get(field,[]) if f['value'] is not None and 'conflict' not in f['review_status']};row[field]=next(iter(values)) if len(values)==1 else None;row[field+'_is_missing']=row[field] is None
            preparation=self.synthesis(doi=GELS,sample=sample)[0];stages={s['stage']:s for s in preparation['stages']}
            row.update(biochar_carbonization_temperature_C=stages['biochar_ingredient_carbonization']['temperature_C'],PAN_carbonization_temperature_C=stages['PAN_carbonization']['temperature_C'],final_aerogel_activation_temperature_C=stages['final_aerogel_activation']['temperature_C'],final_aerogel_activation_duration_h=stages['final_aerogel_activation']['duration_h'])
            row['preparation_evidence']=preparation
            row['material_evidence']=[{k:f[k] for k in ['fact_id','field_name','value','raw_value','review_status','unit','method','source_path','source_sha256','locator']} for f in facts]
            row['limitations']='One source/one cycle endpoint in this purpose. No external-source fold or performance claim; CE53.5 is a separate response, not a predictor. Source-equivalent GCD/common programme accepted; no invented exact baseline cycle.'
            rows.append(row)
        return rows

    def composite_cycle_matrix(self):
        rows=self.composite_cycle_inputs()
        fields=['cycle_count','reported_current_A_g','concentration_mol_L','cycle_voltage_lower_V','cycle_voltage_upper_V','BET_surface_area_m2_g','micropore_volume_cm3_g','mesopore_volume_cm3_g','macropore_volume_cm3_g','total_pore_volume_cm3_g','Raman_IG_ID','XPS_F_at_pct','biochar_carbonization_temperature_C','PAN_carbonization_temperature_C','final_aerogel_activation_temperature_C','final_aerogel_activation_duration_h','final_biochar_fraction']
        return dict(purpose='reported_PAN_biochar_composite_2e_cycle_retention',feature_names=fields,X=[[r[k] for k in fields] for r in rows],missing_mask=[[r[k] is None for k in fields] for r in rows],y=[r['target_retention_pct'] for r in rows],groups=[r['source_group'] for r in rows],sample_weight=[r['source_balanced_weight'] for r in rows],candidate_ids=[r['candidate_id'] for r in rows],independent_source_groups=len({r['source_group'] for r in rows}),external_source_fold_possible=False,training_authorized=False,ordinary_biomass_cycling_admitted=False,imputed=False,estimators_fitted=0,excluded_from_X=['target','coulombic_efficiency','other_test_responses','DOI','sample_identifiers','unresolved_final_component_fraction_values'])

def open_literature_database(database=None,expected_sha256=None):return LiteratureDatabaseV8(database,expected_sha256)
