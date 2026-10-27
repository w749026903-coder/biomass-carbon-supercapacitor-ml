"""Four-source stage/method-qualified inputs. No estimators or imputation."""
import collections,json
from data.literature_v21 import LiteratureDatabaseV21
from data.literature_v20 import FIELDS20
NEW22={'10.1039/d3ra00820g','10.3390/mi14030572','10.1039/d5ra00450k','10.3390/molecules26237104'}
TARGETS22=('reported_aqueous_3e_GCD_capacitance','forest_aqueous_raw_whole_sample_author_capacity','forest_aqueous_ash_free_author_recalculation_author_capacity','forest_organic_raw_whole_sample_author_capacity','forest_organic_ash_free_author_recalculation_author_capacity','SAP_rich_reference_3e_GCD','SAP_rich_reference_2e_author_factor2','lignin_F127_author_CV_10mVs','lignin_Mn_author_CV_10mVs')
FIELDS22=list(dict.fromkeys(FIELDS20+['QSDFT_total_pore_volume_cm3_g','QSDFT_micropore_volume_cm3_g','author_micropore_volume_fraction_pct','author_overall_AC_mass_yield_pct','TGA_air_author_carbon_fraction_pct','single_stage_ZnCl2_to_feedstock_mass_ratio','template_F127_to_lignin_mass_pct','nominal_Mn_precursor_loading_wt_pct','pretest_H2O2_vol_pct']))
class LiteratureDatabaseV22(LiteratureDatabaseV21):
    def batch22_sources(self):return self._rows19('source_reviews_v22')
    def batch22_decisions(self):return self._rows19('decisions_v22')
    def batch22_figures(self):return self._rows19('figure_scope_reviews_v22')
    def batch22_protocols(self):return self._rows19('protocol_reviews_v22')
    def batch22_lineage(self):return self._rows19('material_lineage_v22')
    def batch22_cycle_identity_links(self):return self._rows19('cycle_identity_links_v22')
    def facts(self,doi=None,sample=None,field=None):
        rows=super().facts(doi,sample,field);details={r['fact_id']:json.loads(r['record_json'])for r in self.connection.execute('select *from numeric_details_v22')}
        for r in rows:
            if r['fact_id']in details:r['numeric_details_v22']=details[r['fact_id']]
        return rows
    def canonical_material_features_v13(self,doi,sample):
        if doi not in NEW22:return super().canonical_material_features_v13(doi,sample)
        reports=collections.defaultdict(list)
        for r in self.facts(doi,sample):reports[r['field_name']].append(r)
        decisions={r['field_name']:json.loads(r['record_json'])for r in self.connection.execute('select *from material_feature_decisions_v22 where material_key in(select material_key from materials where doi=?and sample_name=?)',(doi,sample))}
        values={};provenance={};excluded={}
        for f,rs in reports.items():
            observed={r['value']for r in rs if r['value']is not None};decision=decisions.get(f)
            if decision and decision['selected_value']is None:excluded[f]=decision['reason']
            elif any('conflict'in r['review_status']or'ambiguous'in r['review_status']for r in rs)or len(observed)>1:excluded[f]='Unresolved report/unit/method/percentage basis; all literal claims retained.'
            elif len(observed)==1:
                values[f]=next(iter(observed));provenance[f]=dict(decision='Own sample/stage and declared method only; no inferred precursor inheritance',all_reports=rs)
            else:excluded[f]='Dash or unresolved report is not zero.'
        return dict(values=values,provenance=provenance,excluded=excluded)
    def auxiliary_gcd(self,profile='3e'):
        rows=super().auxiliary_gcd(profile)
        for r in rows:
            if r['doi']in NEW22:
                f=self.canonical_material_features_v13(r['doi'],r['sample_name']);r.update(material_features=f['values'],feature_evidence=f['provenance'],excluded_feature_reasons=f['excluded'])
        return rows
    def _features22(self,r):
        v=self._features20(r)
        stages=[s for q in self.synthesis(r['doi'],r['sample_name'])for s in q['stages']]
        a=next((s for s in stages if s['stage']=='single_carbonization_activation'),{})
        if a:
            for f in ['temperature_C','duration_h','heating_rate_C_min']:v['single_stage_'+f]=a.get(f)
            ratio=a.get('feedstock_to_activator_mass_ratio');v['single_stage_ZnCl2_to_feedstock_mass_ratio']=ratio[1]/ratio[0]if ratio and a.get('activator')=='ZnCl2'else None
        a=next((s for s in stages if s['stage']=='template_crosslink'),{})
        v['template_F127_to_lignin_mass_pct']=a.get('F127_to_lignin_mass_pct');v['nominal_Mn_precursor_loading_wt_pct']=a.get('Mn_precursor_nominal_loading_wt_pct')
        a=next((s for s in stages if s['stage']=='pretest_oxidation'),{});v['pretest_H2O2_vol_pct']=a.get('H2O2_vol_pct')
        return v
    def batch22_inputs(self,target=TARGETS22[0]):
        if target not in TARGETS22:raise ValueError('Choose an explicit method, material and normalization purpose')
        ids={r[0]for r in self.connection.execute('select observation_id from purpose_reviews_v22 where eligible=1 and purpose=?',(target,))};rows=[]
        for r in self.capacitances():
            if r['observation_id']not in ids:continue
            f=self.canonical_material_features_v13(r['doi'],r['sample_name']);r.update(target_name=target,material_features=f['values'],feature_evidence=f['provenance'],excluded_feature_reasons=f['excluded'],source_family_group=self.isolation_group(r['source_group']),purpose_input_ready=True,cyclic_retention_training_admitted=False,training_authorized=False,model_fits=0)
            r['matrix_feature_values']=self._features22(r);rows.append(r)
        return sorted(rows,key=lambda r:(r['doi'],r['sample_name'],r['current_A_g']or r['scan_rate_mV_s']or 0))
    def batch22_matrix(self,target=TARGETS22[0]):
        rows=self.batch22_inputs(target);groups=[r['source_family_group']for r in rows];counts=collections.Counter(groups);X=[[r['matrix_feature_values'].get(f)for f in FIELDS22]for r in rows]
        return dict(target=target,feature_names=FIELDS22,X=X,missing_mask=[[v is None for v in xx]for xx in X],y=[r['value']for r in rows],groups=groups,sample_weight=[1/counts[g]for g in groups],observation_ids=[r['observation_id']for r in rows],physical_test_groups=[r['conditions']['physical_test_group']for r in rows],categorical_protocol=[dict(system=r['system'],electrolyte=r['electrolyte'],method=r['method'],binder=r['conditions'].get('binder'),capacitance_basis=r['conditions']['capacitance_basis'],cross_source_comparable=r['conditions'].get('cross_source_comparable',True))for r in rows],source_families=len(counts),imputed=False,estimators_fitted=0,training_authorized=False,scope='Source-specific purposes stay separate. Raw/ash-free expressions are the same experiment and may not be pooled as independent labels. SAP and Mn references do not enter ordinary biomass GCD or lifetime inputs.')
    def auxiliary_feature_rows(self,profile='3e'):
        rows=super().auxiliary_feature_rows(profile);caps={r['observation_id']:r for r in self.capacitances()if r['doi']in NEW22}
        for r in rows:
            if r['doi']in NEW22:
                cap=caps[r['observation_id']];cap['material_features']=self.canonical_material_features_v13(r['doi'],r['sample_name'])['values'];r.update(self._features22(cap))
        return rows
def open_literature_database(database=None,expected_sha256=None):return LiteratureDatabaseV22(database,expected_sha256)
