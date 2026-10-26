"""Furfural rate inputs with explicit point/interval modes; no hidden imputation."""
import collections,json
from data.literature_v13 import LiteratureDatabaseV13
FU='10.3390/polym16233421'


class LiteratureDatabaseV14(LiteratureDatabaseV13):
    def report_groups_v13(self):
        """Keep the named v13 report scope; v14 targets have their own nominal groups."""
        ids={r[0]for r in self.connection.execute("select observation_id from capacitance_observations where json_extract(conditions_json,'$.extraction_batch')='v13'")}
        return[r for r in super().report_groups_v13()if r['observation_id']in ids]

    def batch14_sources(self):return[dict(r,record=json.loads(r['record_json']))for r in self.connection.execute('select *from source_reviews_v14 order by doi')]
    def batch14_decisions(self):return[dict(r,record=json.loads(r['record_json']))for r in self.connection.execute('select *from decisions_v14 order by decision_id')]
    def figure_scope_reviews_v14(self):return[dict(r,record=json.loads(r['record_json']))for r in self.connection.execute('select *from figure_scope_reviews_v14 order by figure_number')]
    def furfural_series_annotations(self):
        return[dict(r,record=json.loads(r['record_json']))for r in self.connection.execute('select a.*,d.path as source_path,d.sha256 as source_sha256 from series_annotations_v14 a join source_documents d using(document_key) order by annotation_id')]
    def furfural_rate_audits(self):return[dict(r,record=json.loads(r['record_json']))for r in self.connection.execute('select *from rate_ratio_reviews_v14 order by material_key')]
    def furfural_contributions(self):return[dict(r,record=json.loads(r['record_json']))for r in self.connection.execute('select *from contribution_pairs_v14 order by scan_rate_mV_s')]

    def furfural_rate_inputs(self,mode='author_exact'):
        if mode not in ['author_exact','point_mixed','interval_mixed','figure_only']:raise ValueError('Choose an explicit exact, point, interval, or figure-only target mode')
        caps={r['observation_id']:r for r in self.capacitances(doi=FU)};graphs=self.sampled_curves(doi=FU);result=[]
        for review in self.connection.execute('select *from purpose_reviews_v14 order by observation_id'):
            link=json.loads(review['record_json']);graph=caps[review['observation_id']];exact=link.get('author_exact_observation_id')
            use_exact=exact is not None and mode!='figure_only'
            if mode=='author_exact'and not use_exact:continue
            row=dict(caps[exact]if use_exact else graph);row['conditions']=dict(row['conditions'])
            row['conditions']['original_report_group_before_v14']=row['conditions'].get('physical_test_group')
            row['conditions']['physical_test_group']=link['physical_test_group']
            kind='author_reported_exact'if use_exact else'bounded_figure'if graph['value']is not None else'occluded_interval_only'
            if mode in ['point_mixed','figure_only']and row['value']is None:continue
            lower=row['value']if use_exact else link['lower_bound'];upper=row['value']if use_exact else link['upper_bound']
            features=self.canonical_material_features_v13(FU,row['sample_name'])
            support=[r['reading_id']for r in graphs if r['sample_name']==row['sample_name']and r['reading']['x_value']==row['current_A_g']]
            result.append(dict(row,graph_observation_id=graph['observation_id'],target_mode=mode,target_name='reported_furfural_residual_3e_GCD_F_g',target_value=row['value'],target_lower_bound=lower,target_upper_bound=upper,target_value_kind=kind,target_bound_semantics='reported label value, experimental uncertainty unreported'if use_exact else'graphical reading/occlusion envelope, not an experimental confidence interval',point_loss_eligible=row['value']is not None,requires_interval_aware_loss=row['value']is None,physical_test_group=link['physical_test_group'],source_family_group=self.isolation_group(row['source_group']),material_features=features['values'],feature_evidence=features['provenance'],excluded_feature_reasons=features['excluded'],synthesis=self.synthesis(doi=FU,sample=row['sample_name']),supporting_curve_reading_ids=support,ordinary_biomass_carbon_profile=False,scientific_goal_complete=False,model_fits=0))
        return sorted(result,key=lambda r:(r['sample_name'],r['current_A_g']))

    def furfural_rate_matrix(self,mode='author_exact'):
        rows=self.furfural_rate_inputs(mode);fields=['BET_surface_area_m2_g','total_pore_volume_cm3_g','micropore_volume_cm3_g','Raman_ID_IG','average_pore_diameter_reported_nm','ICP_OES_Zn_wt_pct']
        X=[]
        for r in rows:
            process=next(s for record in r['synthesis']for s in record['stages']if s['stage']=='single_carbonization_template_activation')
            parts=process['raw_FR_ZnO_APS_mass_parts']
            if parts is None:
                if r['sample_name']!='FR900':raise RuntimeError('Unknown recipe cannot be filled with zero')
                # Own body11 explicitly says FR900 was carbonized with nothing added.
                parts=[1,0,0]
            X.append([r['material_features'].get(f)for f in fields]+[r['current_A_g'],r['concentration_mol_L'],r['conditions']['voltage_lower_V'],r['conditions']['voltage_upper_V'],process['temperature_C'],process['duration_h'],process['heating_rate_C_min'],parts[1]/parts[0],parts[2]/parts[0]])
        groups=[r['source_family_group']for r in rows];counts=collections.Counter(groups)
        return dict(purpose='reported_furfural_residual_3e_GCD_F_g',target_mode=mode,feature_names=fields+['reported_current_A_g','concentration_mol_L','voltage_lower_V','voltage_upper_V','carbonization_temperature_C','carbonization_duration_h','carbonization_heating_rate_C_min','recipe_ZnO_to_FR_mass_ratio','recipe_APS_to_FR_mass_ratio'],X=X,missing_mask=[[v is None for v in row]for row in X],y=[r['target_value']for r in rows],y_lower=[r['target_lower_bound']for r in rows],y_upper=[r['target_upper_bound']for r in rows],target_value_kinds=[r['target_value_kind']for r in rows],point_loss_mask=[r['point_loss_eligible']for r in rows],requires_interval_aware_loss=any(r['requires_interval_aware_loss']for r in rows),point_estimator_ready=all(r['point_loss_eligible']for r in rows),groups=groups,sample_weight=[1/counts[g]for g in groups],observation_ids=[r['observation_id']for r in rows],graph_observation_ids=[r['graph_observation_id']for r in rows],physical_test_groups=[r['physical_test_group']for r in rows],sample_names=[r['sample_name']for r in rows],source_families=len(set(groups)),independent_source_validation_possible_alone=len(set(groups))>=2,imputed=False,estimators_fitted=0,training_authorized=False,excluded_from_X=['rate_retention_annotations','all_CV/GCD/EIS_response_targets','contact_angle_conflicts','S_pct_method_unspecified','identities','unquantified_composition'],stage_policy='FR900 recipezero derives only from explicit no-addition control; ZnO precursor size is not final carbon pore size')


def open_literature_database(database=None,expected_sha256=None):return LiteratureDatabaseV14(database,expected_sha256)
