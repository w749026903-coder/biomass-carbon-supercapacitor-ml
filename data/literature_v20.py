"""Five-source method/stage-qualified literature API; no estimator fitting."""
import collections,json
from data.literature_v19 import LiteratureDatabaseV19,FIELDS19
NEW20={'10.3390/nano14010071','10.1039/d5ra03028e','10.1021/acsomega.3c09438','10.3390/nano13172431','10.1021/acsomega.2c04301'}
TARGETS20=('reported_aqueous_3e_GCD_capacitance','reported_orange_2e_CV_device_Cg','reported_coffee_sludge_2e_GCD_author_KOH','reported_coffee_sludge_2e_GCD_author_CH3COONa','reported_moringa_ZnCa_residue_2e_GCD_working_mass_Csp','reported_moringa_ZnCa_residue_2e_CV_author_Csp')
FIELDS20=list(dict.fromkeys(FIELDS19+['scan_rate_mV_s','Raman_IG_ID','bulk_EA_C_wt_pct','bulk_EA_H_wt_pct','geometric_disc_density_g_cm3','positive_negative_mass_ratio','KCl_to_feedstock_mass_ratio','physical_activation_temperature_C','physical_activation_heating_rate_C_min','carbonization_temperature_C','carbonization_heating_rate_C_min']))
class LiteratureDatabaseV20(LiteratureDatabaseV19):
    def batch20_sources(self):return self._rows19('source_reviews_v20')
    def batch20_decisions(self):return self._rows19('decisions_v20')
    def batch20_figures(self):return self._rows19('figure_scope_reviews_v20')
    def batch20_protocols(self):return self._rows19('protocol_reviews_v20')
    def batch20_lineage(self):return self._rows19('material_lineage_v20')
    def batch20_raw_dispositions(self):return self._rows19('raw_candidate_dispositions_v20')
    def batch20_cycle_identity_links(self):return self._rows19('cycle_identity_links_v20')
    def facts(self,doi=None,sample=None,field=None):
        rows=super().facts(doi,sample,field);details={r['fact_id']:json.loads(r['record_json'])for r in self.connection.execute('select *from numeric_details_v20')}
        for r in rows:
            if r['fact_id']in details:r['numeric_details_v20']=details[r['fact_id']]
        return rows
    def canonical_material_features_v13(self,doi,sample):
        if doi not in NEW20:return super().canonical_material_features_v13(doi,sample)
        reports=collections.defaultdict(list)
        for r in self.facts(doi,sample):reports[r['field_name']].append(r)
        decisions={r['field_name']:json.loads(r['record_json'])for r in self.connection.execute('select *from material_feature_decisions_v20 where material_key in(select material_key from materials where doi=?and sample_name=?)',(doi,sample))}
        values={};provenance={};excluded={}
        for f,rs in reports.items():
            observed={r['value']for r in rs if r['value']is not None};decision=decisions.get(f)
            if decision:
                if decision['selected_value']is None:excluded[f]=decision['reason'];continue
                assert decision['selected_value']in observed
                values[f]=decision['selected_value'];provenance[f]=dict(decision=decision,all_reports=rs)
            elif any('attribution_risk'in r['review_status']for r in rs):excluded[f]='Author-claimed surface atomic reports coincide with bulk mass fractions; attribution risk, not proven false. Raw method claims remain inspectable; quality-filtered optional feature masked.'
            elif any('conflict'in r['review_status']for r in rs)or len(observed)>1:excluded[f]='Competing own values or ND versus author zero interpretation; raw claims retained.'
            elif len(observed)==1:values[f]=next(iter(observed));provenance[f]=dict(decision='Same own sample, stage and declared measurement method',all_reports=rs)
            else:excluded[f]='No resolved numeric scalar; dash/unreported/ambiguous is not zero.'
        return dict(values=values,provenance=provenance,excluded=excluded)
    def auxiliary_gcd(self,profile='3e'):
        rows=super().auxiliary_gcd(profile)
        for r in rows:
            if r['doi']in NEW20:
                x=self.canonical_material_features_v13(r['doi'],r['sample_name']);r.update(material_features=x['values'],feature_evidence=x['provenance'],excluded_feature_reasons=x['excluded'])
        return rows
    def _features20(self,r):
        v=self._features19(r);v['scan_rate_mV_s']=r['scan_rate_mV_s'];v['positive_negative_mass_ratio']=r['conditions'].get('positive_negative_mass_ratio')
        stages=[s for rec in self.synthesis(doi=r['doi'],sample=r['sample_name'])for s in rec['stages']]
        a=next((s for s in stages if s['stage']=='chemical_activation'),{})
        if a:
            for f in ['temperature_C','duration_h','heating_rate_C_min']:v['activation_'+f]=a.get(f)
            ratio=a.get('carbon_to_activator_mass_ratio');v['activator_to_carbon_mass_ratio']=ratio[1]/ratio[0]if ratio else None
        a=next((s for s in stages if s['stage']=='single_carbonization_activation'),{});v['KCl_to_feedstock_mass_ratio']=a.get('KCl_to_feedstock_mass_ratio')
        a=next((s for s in stages if s['stage']=='integrated_carbonization_physical_activation'),{})
        for f in ['temperature_C','heating_rate_C_min']:v['physical_activation_'+f]=a.get('activation_'+f);v['carbonization_'+f]=a.get('carbonization_'+f)
        return v
    def batch20_inputs(self,target=TARGETS20[0]):
        if target not in TARGETS20:raise ValueError('Choose one explicit v20 method/material/normalization purpose')
        ids={r[0]for r in self.connection.execute('select observation_id from purpose_reviews_v20 where eligible=1 and purpose=?',(target,))};rows=[]
        for r in self.capacitances():
            if r['observation_id']not in ids:continue
            x=self.canonical_material_features_v13(r['doi'],r['sample_name']);r.update(target_name=target,material_features=x['values'],feature_evidence=x['provenance'],excluded_feature_reasons=x['excluded'],source_family_group=self.isolation_group(r['source_group']),purpose_input_ready=True,cyclic_retention_training_admitted=False,training_authorized=False,model_fits=0)
            r['matrix_feature_values']=self._features20(r);rows.append(r)
        return sorted(rows,key=lambda r:(r['doi'],r['sample_name'],r['electrolyte'],r['method'],r['current_A_g']or r['scan_rate_mV_s']or 0,r['conditions'].get('binder')or''))
    def batch20_matrix(self,target=TARGETS20[0]):
        rows=self.batch20_inputs(target);groups=[r['source_family_group']for r in rows];counts=collections.Counter(groups);X=[[r['matrix_feature_values'].get(f)for f in FIELDS20]for r in rows]
        return dict(target=target,feature_names=FIELDS20,X=X,missing_mask=[[v is None for v in row]for row in X],y=[r['value']for r in rows],groups=groups,sample_weight=[1/counts[g]for g in groups],observation_ids=[r['observation_id']for r in rows],physical_test_groups=[r['conditions']['physical_test_group']for r in rows],categorical_protocol=[dict(system=r['system'],electrolyte=r['electrolyte'],method=r['method'],binder=r['conditions'].get('binder'),capacitance_basis=r['conditions']['capacitance_basis'],cross_source_comparable=r['conditions'].get('cross_source_comparable',True))for r in rows],source_families=len(counts),imputed=False,estimators_fitted=0,training_authorized=False,excluded_from_X=['source/sample/curve identifiers and all electrochemical responses','postcycle positive-electrode XPS/potentials','raw/prechar/predisc properties inherited by finalcarbon','riskmarked author XPS claims conflated with bulkEAwt','unbound duplicated MOL750 row assigned to MOL850','unknown current denominators or mass ratios filled by formula or default'])
    def auxiliary_feature_rows(self,profile='3e'):
        rows=super().auxiliary_feature_rows(profile);caps={r['observation_id']:r for r in self.capacitances()if r['doi']in NEW20}
        for r in rows:
            if r['doi']in NEW20:
                cap=caps[r['observation_id']];cap['material_features']=self.canonical_material_features_v13(r['doi'],r['sample_name'])['values'];r.update(self._features20(cap))
        return rows
def open_literature_database(database=None,expected_sha256=None):return LiteratureDatabaseV20(database,expected_sha256)
