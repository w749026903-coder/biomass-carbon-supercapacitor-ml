"""Read-only current protocol bindings, identity reviews and source-specific rates."""
import collections,json
from data.literature_v20 import LiteratureDatabaseV20,FIELDS20
MODES21=('author_exact','point_mixed','figure_only')
class LiteratureDatabaseV21(LiteratureDatabaseV20):
    def batch21_protocol_corrections(self):return[dict(r,doi=r['record']['doi'])for r in self._rows19('protocol_corrections_v21')]
    def batch21_candidate_audits(self):return[dict(r,doi=r['record']['doi'])for r in self._rows19('candidate_identity_audits_v21')]
    def batch21_identity_links(self):return[dict(r,doi=r['record']['doi'])for r in self._rows19('candidate_identity_links_v21')]
    def batch21_source_notes(self):return self._rows19('source_review_notes_v21')
    def batch21_decisions(self):return self._rows19('decisions_v21')
    def sampled_curves(self,doi=None,sample=None):
        rows=super().sampled_curves(doi,sample)
        for row in rows:
            r=row['reading']
            if r.get('extraction_batch')!='v21':continue
            r.update(x_lower_bound=r['x_value']-r['x_uncertainty'],x_upper_bound=r['x_value']+r['x_uncertainty'],y_uncertainty=(r['y_upper_bound']-r['y_lower_bound'])/2 if r['y_value']is not None else None,uncertainty_metadata_derived_from_stored_bounds=True)
        return rows
    def capacitances(self,doi=None,sample=None,method=None,electrolyte=None):
        # Apply selected protocol before method filtering; raw SQL rows remain immutable.
        rows=super().capacitances(doi,sample,None,electrolyte);fix={r['observation_id']:r['record']for r in self.batch21_protocol_corrections()}
        for r in rows:
            if r['observation_id']not in fix:continue
            decision=fix[r['observation_id']];r['original_protocol_v20']=dict(method=r['method'],scan_rate_mV_s=r['scan_rate_mV_s'],current_A_g=r['current_A_g'],conditions=dict(r['conditions']));r.update(method=decision['selected_method'],scan_rate_mV_s=decision['selected_scan_rate_mV_s'],protocol_binding_decision_v21=decision)
            r['conditions']=dict(r['conditions'],source_overlap_pending=True,capacitance_basis='author_Ct_CV_total_positive_negative_active_masses',physical_test_group=r['conditions']['physical_test_group']+'_CV5mVs',protocol_binding_v21='ActualFig6bcaption explicitlyCV5mVs')
        return[r for r in rows if method is None or r['method']==method]
    def batch21_rate_rows(self,mode='point_mixed',purpose='coffee_KOH_author_capacity'):
        if mode not in MODES21 or purpose not in ['coffee_KOH_author_capacity','rice_mass_ratio_inspection']:raise ValueError('Explicit mode and purpose required')
        caps={r['observation_id']:r for r in self.capacitances()};rows=[]
        for record in self.connection.execute('select *from rate_reviews_v21 where purpose=?order by observation_id',(purpose,)):
            proof=json.loads(record['record_json']);anchor=caps.get(proof['author_exact_observation_id'])
            if mode=='author_exact'and anchor is None:continue
            if mode!='figure_only'and anchor is not None:item=dict(anchor,target_value=anchor['value'],target_lower_bound=None,target_upper_bound=None,target_value_kind='author_exact_mean_SD_kept_in_raw_and_conditions',graph_reading_id=proof['reading_id'])
            else:item=dict(caps[record['observation_id']],target_value=caps[record['observation_id']]['value'],target_lower_bound=proof['y_lower_bound'],target_upper_bound=proof['y_upper_bound'],target_value_kind='bounded_original_marker'if proof['y_value']is not None else'occluded_marker_without_numeric_bound',graph_reading_id=proof['reading_id'])
            f=self.canonical_material_features_v13(item['doi'],item['sample_name']);item.update(target_mode=mode,target_purpose=purpose,source_family_group=self.isolation_group(item['source_group']),material_features=f['values'],feature_evidence=f['provenance'],excluded_feature_reasons=f['excluded'],nominal_report_group=proof['nominal_report_group'],binder=proof['binder'],positive_negative_mass_ratio=proof['positive_negative_mass_ratio'],current_graphical_uncertainty=proof['x_uncertainty'],bounds_not_experimental_SD_or_CI=True,source_overlap_pending=proof['source_overlap_pending'],purpose_input_ready=bool(record['eligible'])and item['target_value']is not None,formal_cycling_admission=False,model_fits=0,training_authorized=False)
            item['matrix_feature_values']=self._features20(item);rows.append(item)
        return sorted(rows,key=lambda r:(r['sample_name'],r['binder'],r['positive_negative_mass_ratio']or 0,r['current_A_g']))
    def batch21_rate_matrix(self,mode='point_mixed',purpose='coffee_KOH_author_capacity'):
        if purpose!='coffee_KOH_author_capacity':raise ValueError('RHC remains sample_overlap_pending; inspection rows are not a training matrix')
        rows=self.batch21_rate_rows(mode,purpose)
        if any(not r['purpose_input_ready']for r in rows):raise ValueError('Unresolved/occluded point is not eligible for this point matrix')
        groups=[r['source_family_group']for r in rows];counts=collections.Counter(groups);X=[[r['matrix_feature_values'].get(f)for f in FIELDS20]for r in rows]
        return dict(target=purpose,mode=mode,feature_names=FIELDS20,X=X,y=[r['target_value']for r in rows],missing_mask=[[v is None for v in rr]for rr in X],groups=groups,sample_weight=[1/counts[g]for g in groups],observation_ids=[r['observation_id']for r in rows],nominal_report_groups=[r['nominal_report_group']for r in rows],categorical_protocol=[dict(binder=r['binder'],method=r['method'],system=r['system'],capacitance_basis=r['conditions']['capacitance_basis'])for r in rows],source_families=len(counts),cross_source_comparable=False,imputed=False,estimators_fitted=0,training_authorized=False,scope='Source-specific author C/Cg expression, sameDOI across3binder/materialseries. 3oldanchors+9newapproximateconditions inpoint_mixed; no claimed newindependentsources or cyclingadmission.')
def open_literature_database(database=None,expected_sha256=None):return LiteratureDatabaseV21(database,expected_sha256)
