"""Explicit graph-expanded GCD cohorts; ordinary profiles remain unchanged.

author_exact selects author-reported numeric labels, retaining author approximate
qualifiers in each original status. It never claims exact physical measurements.
"""
import collections,json
from data.literature_v15 import LiteratureDatabaseV15
PE='10.3390/nano14100836';DA='10.3390/nano12010122'
FIELDS16=['BET_surface_area_m2_g','total_pore_volume_cm3_g','micropore_volume_cm3_g','mesopore_volume_cm3_g','XPS_C_at_pct','XPS_N_at_pct','XPS_O_at_pct','Raman_ID_IG','current_A_g','concentration_mol_L','voltage_lower_V','voltage_upper_V','carbonization_temperature_C','carbonization_duration_h','activation_temperature_C','activation_duration_h','activation_heating_rate_C_min','activator_to_carbon_mass_ratio','DFT_pore_volume_cm3_g','DA_micropore_volume_cm3_g']

class LiteratureDatabaseV16(LiteratureDatabaseV15):
    def batch16_decisions(self):return[dict(r,record=json.loads(r['record_json']))for r in self.connection.execute('select *from decisions_v16 order by decision_id')]
    def batch16_sources(self):return[dict(r,record=json.loads(r['record_json']))for r in self.connection.execute('select *from source_reviews_v16 order by doi')]
    def _rate_feature_values16(self,r):
        values=dict(r['material_features']);values.update(current_A_g=r['current_A_g'],concentration_mol_L=r['concentration_mol_L'],voltage_lower_V=r['conditions'].get('voltage_lower_V'),voltage_upper_V=r['conditions'].get('voltage_upper_V'))
        stages=[s for record in self.synthesis(doi=r['doi'],sample=r['sample_name'])for s in record['stages']];carbon=next((s for s in stages if s['stage']=='carbonization'),{});activation=next((s for s in stages if s['stage']in ['chemical_activation','physical_activation']),{})
        for p,stage in [('carbonization',carbon),('activation',activation)]:
            for f in ['temperature_C','duration_h','heating_rate_C_min']:values[p+'_'+f]=stage.get(f)
        ratio=activation.get('carbon_to_activator_mass_ratio');values['activator_to_carbon_mass_ratio']=ratio[1]/ratio[0]if ratio else None
        return values
    def batch16_rate_inputs(self,mode='author_exact',scope='all'):
        if mode not in ['author_exact','point_mixed','figure_only']or scope not in ['all','peel','date']:raise ValueError('Choose explicit mode author_exact/point_mixed/figure_only and scope all/peel/date')
        caps={r['observation_id']:r for r in self.capacitances()};selected=[]
        for review in self.connection.execute('select *from purpose_reviews_v16 where is_primary=1 order by observation_id'):
            graph=caps[review['observation_id']];link=json.loads(review['record_json']);exact=link['author_exact_observation_id'];use_exact=exact is not None and mode!='figure_only'
            if mode=='author_exact'and not use_exact:continue
            row=dict(caps[exact]if use_exact else graph);row['conditions']=dict(row['conditions']);row['conditions']['original_report_group_before_v16']=row['conditions'].get('physical_test_group');row['conditions']['physical_test_group']=link['physical_test_group']
            row.update(graph_observation_id=graph['observation_id'],graph_reading_id=review['reading_id'],target_value=row['value'],target_lower_bound=row['value']if use_exact else link['lower_bound'],target_upper_bound=row['value']if use_exact else link['upper_bound'],target_value_kind='author_reported_anchor'if use_exact else'bounded_original_figure',target_bounds_kind='reported label value; experimental uncertainty unreported'if use_exact else'graphical4pixel reading envelope, not experimental CI',author_exact_observation_id=exact,physical_test_group=link['physical_test_group'])
            selected.append(row)
        if mode!='figure_only':
            controls=[r for r in caps.values()if r['doi']==DA and r['sample_name']=='CO2-activated'and r['conditions'].get('extraction_batch')=='v15'];assert len(controls)==1
            row=dict(controls[0]);row['conditions']=dict(row['conditions']);group='doi:'+DA+':CO2-activated:3E:GCD:j1';row['conditions']['original_report_group_before_v16']=row['conditions'].get('physical_test_group');row['conditions']['physical_test_group']=group
            row.update(graph_observation_id=None,graph_reading_id=None,target_value=row['value'],target_lower_bound=row['value'],target_upper_bound=row['value'],target_value_kind='author_reported_control_without_new_graph_capture',target_bounds_kind='reported label value; experimental uncertainty unreported',author_exact_observation_id=row['observation_id'],physical_test_group=group);selected.append(row)
        result=[]
        for r in selected:
            if scope=='peel'and r['doi']!=PE or scope=='date'and r['doi']!=DA:continue
            features=self.canonical_material_features_v13(r['doi'],r['sample_name']);r.update(material_features=features['values'],feature_evidence=features['provenance'],excluded_feature_reasons=features['excluded'],source_family_group=self.isolation_group(r['source_group']),target_mode=mode,purpose='explicit_reported_3e_GCD_with_graphical_values',scientific_goal_complete=False,model_fits=0);r['matrix_feature_values']=self._rate_feature_values16(r);result.append(r)
        return sorted(result,key=lambda r:(r['doi'],r['sample_name'],r['current_A_g']))
    def _matrix16(self,rows,cohort):
        X=[[r['matrix_feature_values'].get(f)for f in FIELDS16]for r in rows];groups=[self.isolation_group(r['source_group'])for r in rows];counts=collections.Counter(groups)
        return dict(cohort=cohort,target='reported_3e_GCD_capacitance_F_g',feature_names=FIELDS16,X=X,missing_mask=[[v is None for v in rr]for rr in X],y=[r['target_value']for r in rows],y_lower=[r.get('target_lower_bound')for r in rows],y_upper=[r.get('target_upper_bound')for r in rows],target_value_kinds=[r['target_value_kind']for r in rows],groups=groups,sample_weight=[1/counts[g]for g in groups],observation_ids=[r['observation_id']for r in rows],physical_test_groups=[r.get('physical_test_group',r['conditions'].get('physical_test_group'))for r in rows],categorical_protocol=[dict(electrolyte=r['electrolyte'],system=r['system'])for r in rows],source_families=len(set(groups)),imputed=False,estimators_fitted=0,training_authorized=False,experimental_uncertainties_not_inferred=True,excluded_from_X=['all capacitance/rate/cycle/Bode/EIS/Ragone responses','source/material/curve identifiers','raw precursor composition','conflicting XPS components','coating mass as active mass','unreported initial carbonization and Ramannear1 as exact scalar'])
    def batch16_rate_matrix(self,mode='author_exact',scope='all'):return self._matrix16(self.batch16_rate_inputs(mode,scope),'two_existing_source_series_'+mode+'_'+scope)
    def expanded_graph_3e_inputs(self):
        rows=[];flats={r['observation_id']:r for r in self.auxiliary_feature_rows('3e')}
        for r in self.auxiliary_gcd('3e'):
            row=dict(r);row.update(matrix_feature_values=dict(flats[r['observation_id']]),target_value=r['value'],target_value_kind='legacy_existing_purpose_input:'+r['status'],target_lower_bound=None,target_upper_bound=None,physical_test_group=r['conditions'].get('physical_test_group'),source_family_group=self.isolation_group(r['source_group']))
            for f in ['DFT_pore_volume_cm3_g','DA_micropore_volume_cm3_g']:row['matrix_feature_values'][f]=r['material_features'].get(f)
            rows.append(row)
        oldids={r['observation_id']for r in rows}
        for r in self.batch16_rate_inputs('point_mixed'):
            if r['observation_id']not in oldids:assert r['target_value_kind']=='bounded_original_figure';rows.append(r)
        return rows
    def expanded_graph_3e_matrix(self):return self._matrix16(self.expanded_graph_3e_inputs(),'explicit_existing_ordinary3E_plus75_bounded_graph_conditions')

def open_literature_database(database=None,expected_sha256=None):return LiteratureDatabaseV16(database,expected_sha256)
