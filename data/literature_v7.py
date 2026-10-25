"""Read-only Palm Kernel bulk materials, per-device reports and source-statistic audits."""
import json,statistics
from data.literature_v6 import LiteratureDatabaseV6
PALM='10.3390/nano16040260'

class LiteratureDatabaseV7(LiteratureDatabaseV6):
    def palm_capacitances(self,method=None,statistical_grain=None):
        rows=self.capacitances(doi=PALM,method=method)
        return [r for r in rows if statistical_grain is None or r['conditions']['statistical_grain']==statistical_grain]

    def palm_responses(self,family=None,metric=None,assembly=None):
        rows=self.connection.execute('''
          select o.*,x.record_kind,d.path as source_path,d.sha256 as source_sha256,l.locator,m.sample_name
          from extraction_metrics_v7 x join outcome_observations_v3 o on x.record_id=o.outcome_id
          join table_source_links l on l.table_key=o.table_key join source_documents d using(document_key)
          left join materials m on m.material_key=o.material_key
          where (? is null or x.record_kind=?) and (? is null or x.metric=?)
          order by o.table_key,o.outcome_id''',(family,family,metric,metric))
        result=[]
        for r in rows:
            value=dict(r);value['record']=json.loads(r['record_json'])
            if assembly is None or value['record'].get('assembly')==assembly:result.append(value)
        return result

    def palm_statistics_audit(self):
        """Arithmetic of listed reports; never substitutes a new aggregate or asserts independence."""
        caps=self.palm_capacitances('EIS');result=[]
        for agg in [r for r in caps if r['conditions']['statistical_grain']=='aggregate_mean']:
            listed=[r for r in caps if r['sample_name']==agg['sample_name'] and r['system']==agg['system'] and r['conditions']['statistical_grain']=='individual_device']
            values=[r['value'] for r in listed];assert values
            n=len(values);printed_n=9 if agg['sample_name']=='PK700' and 'Swagelok' in agg['system'] else 8 if agg['sample_name']=='PK700N' else 18 if agg['sample_name']=='PK700' else None
            result.append(dict(doi=PALM,sample_name=agg['sample_name'],system=agg['system'],aggregate_observation_id=agg['observation_id'],reported_mean_F_g=agg['value'],reported_SD_F_g=agg['conditions']['reported_sample_SD_F_g'],reported_95CI_half_width_F_g=agg['conditions']['reported_uncertainty'],SI_footnote_n=printed_n,listed_measurement_reports=n,explicit_repeat_reports=sum(r['conditions']['repeat_measurement'] for r in listed),arithmetic_mean_of_listed_reports=statistics.mean(values),arithmetic_SD_of_listed_reports=statistics.stdev(values),mean_difference_reported_minus_listed=agg['value']-statistics.mean(values),listed_observation_ids=[r['observation_id'] for r in listed],source_group='doi:'+PALM,decision='Preserve author aggregate and individual reports separately; no automatic mean replacement, silent exclusion, new independent samples or training admission.',derived_audit_not_new_author_measurement=True))
        return result

    def palm_material_matrix(self):
        names=['BET_surface_area_m2_g','micropore_volume_cm3_g','mesopore_volume_cm3_g','total_pore_volume_cm3_g','DR_micropore_size_nm','reported_primary_PSD_peak_nm','XPS_C_wt_pct','XPS_O_wt_pct','XPS_N_wt_pct','activation_temperature_C','activation_duration_h','HNO3_solution_pct']
        data=[];metadata=[]
        for sample in ['PK700','PK700N','PZ700','PZ700N']:
            facts=self.facts(doi=PALM,sample=sample);values={f['field_name']:f['value'] for f in facts}
            stages=self.synthesis(doi=PALM,sample=sample)[0]['stages'];activation=next(s for s in stages if s['stage']=='chemical_activation')
            values.update(activation_temperature_C=activation['temperature_C'],activation_duration_h=activation['duration_h'],HNO3_solution_pct=None)
            data.append([values[k] for k in names]);metadata.append(dict(sample_name=sample,HNO3_state='competing30vs65pct' if sample.endswith('N') else 'not_applicable_no_HNO3_treatment',source_group='doi:'+PALM,source_qualified_facts=[f['fact_id'] for f in facts]))
        return dict(feature_names=names,X=data,missing_mask=[[v is None for v in row] for row in data],metadata=metadata,groups=['doi:'+PALM]*4,independent_source_groups=1,imputed=False,has_response_labels=False,training_authorized=False,ordinary_cycling_admissions=0,limitations='Bulk material view only; per-device EIS, aggregates, GCD author2m points and stack responses are separate. One DOI, no external-source validation fold.')

def open_literature_database(database=None,expected_sha256=None):
    return LiteratureDatabaseV7(database,expected_sha256)
