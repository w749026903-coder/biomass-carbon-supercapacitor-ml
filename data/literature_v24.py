"""Four-study own-sample inputs with explicit purpose-specific protocol boundaries."""
import collections,json
from data.literature_v23 import LiteratureDatabaseV23,FIELDS23
NEW24={'10.3390/polym15193976','10.3390/nano15050387','10.3390/ma16134577','10.3390/nano12213804'}
TARGETS24=('reported_aqueous_3e_GCD_capacitance','food_waste_2e_author_capacity','grapefruit_2e_author_capacity','wheat_husk_2e_factor4_total_active_mass_Cs')
FIELDS24=list(dict.fromkeys(FIELDS23+['HK_micropore_volume_cm3_g','author_micropore_volume_fraction','activation_stage_yield_pct','EDS_C_wt_pct','EDS_N_wt_pct','EDS_O_wt_pct','EDS_S_wt_pct','mass_loading_mg_cm2','salt_sealed_precarbonization_temperature_C','microwave_carbonization_temperature_C','microwave_carbonization_duration_min','microwave_carbonization_heating_rate_C_min','microwave_activation_duration_min','single_stage_temperature_K_as_reported','single_stage_temperature_C_from_K','initial_KOH_to_raw_feedstock_mass_ratio']))
class LiteratureDatabaseV24(LiteratureDatabaseV23):
    def batch24_sources(self):return self._rows19('source_reviews_v24')
    def batch24_decisions(self):return self._rows19('decisions_v24')
    def batch24_figures(self):return self._rows19('figure_scope_reviews_v24')
    def batch24_protocols(self):return self._rows19('protocol_reviews_v24')
    def batch24_lineage(self):return self._rows19('material_lineage_v24')
    def batch24_cycle_identity_links(self):return self._rows19('cycle_identity_links_v24')
    def facts(self,doi=None,sample=None,field=None):
        rows=super().facts(doi,sample,field);details={r['fact_id']:json.loads(r['record_json'])for r in self.connection.execute('select *from numeric_details_v24')}
        for r in rows:
            if r['fact_id']in details:r['numeric_details_v24']=details[r['fact_id']]
        return rows
    def canonical_material_features_v13(self,doi,sample):
        if doi not in NEW24:return super().canonical_material_features_v13(doi,sample)
        rr=collections.defaultdict(list)
        for r in self.facts(doi,sample):rr[r['field_name']].append(r)
        values={};provenance={};excluded={}
        for f,rs in rr.items():
            nums={r['value']for r in rs if r['value']is not None}
            if any('conflict'in r['review_status']or'ambiguous'in r['review_status']for r in rs)or len(nums)>1:excluded[f]='Conflicting own unit/value/assignment or unspecified percentage basis; all reports retained, no majority/performance choice.'
            elif len(nums)==1:values[f]=next(iter(nums));provenance[f]=dict(decision='Own sample/stage/method only. Raw chemistry, precursor yield, envelope fractions, EDS weight and XPS atoms kept separate.',all_reports=rs)
            else:excluded[f]='Unreported dash is not zero.'
        return dict(values=values,provenance=provenance,excluded=excluded)
    def _features24(self,r):
        v=self._features23(r);v.update(r['material_features']);v['mass_loading_mg_cm2']=r['conditions'].get('mass_loading_mg_cm2');stages=[s for x in self.synthesis(r['doi'],r['sample_name'])for s in x['stages']]
        a=next((s for s in stages if s['stage']=='salt_sealed_precarbonization'),{});v['salt_sealed_precarbonization_temperature_C']=a.get('temperature_C')
        a=next((s for s in stages if s['stage']=='microwave_carbonization'),{})
        for f in ['temperature_C','duration_min','heating_rate_C_min']:v['microwave_carbonization_'+f]=a.get(f)
        a=next((s for s in stages if s['stage']=='chemical_activation'and s.get('heating_mode')=='microwave'),{});v['microwave_activation_duration_min']=a.get('duration_min')
        a=next((s for s in stages if s['stage']=='single_carbonization_activation'),{});k=a.get('temperature_K');v['single_stage_temperature_K_as_reported']=k;v['single_stage_temperature_C_from_K']=k-273.15 if k is not None else None
        ratio=a.get('raw_feedstock_to_KOH_mass_ratio');v['initial_KOH_to_raw_feedstock_mass_ratio']=ratio[1]/ratio[0]if ratio else None
        return v
    def batch24_inputs(self,target=TARGETS24[0]):
        if target not in TARGETS24:raise ValueError('Choose an admitted per-purpose representation; disputed furfural conditions are inspection only')
        ids={r[0]for r in self.connection.execute('select observation_id from purpose_reviews_v24 where eligible=1 and purpose=?',(target,))};out=[]
        for r in self.capacitances():
            if r['observation_id']not in ids:continue
            f=self.canonical_material_features_v13(r['doi'],r['sample_name']);r.update(target_name=target,material_features=f['values'],feature_evidence=f['provenance'],excluded_feature_reasons=f['excluded'],source_family_group=self.isolation_group(r['source_group']),purpose_input_ready=True,cyclic_retention_training_admitted=False,training_authorized=False,model_fits=0)
            r['matrix_feature_values']=self._features24(r);out.append(r)
        return sorted(out,key=lambda r:(r['doi'],r['sample_name'],r['current_A_g']or 0))
    def batch24_matrix(self,target=TARGETS24[0]):
        rows=self.batch24_inputs(target);groups=[r['source_family_group']for r in rows];counts=collections.Counter(groups);X=[[r['matrix_feature_values'].get(f)for f in FIELDS24]for r in rows]
        return dict(target=target,feature_names=FIELDS24,X=X,missing_mask=[[v is None for v in xx]for xx in X],y=[r['value']for r in rows],groups=groups,sample_weight=[1/counts[g]for g in groups],observation_ids=[r['observation_id']for r in rows],physical_test_groups=[r['conditions']['physical_test_group']for r in rows],categorical_protocol=[dict(system=r['system'],method=r['method'],electrolyte=r['electrolyte'],reference_electrode=r['conditions'].get('reference_electrode'),reference_status=r['conditions'].get('reference_status'),capacitance_basis=r['conditions']['capacitance_basis'],cross_source_comparable=r['conditions']['cross_source_comparable'])for r in rows],source_families=len(counts),imputed=False,estimators_fitted=0,training_authorized=False,derived_features={'single_stage_temperature_C_from_K':'Exact K−273.15 conversion; source sample name is not an annealing temperature.'},scope='Reported working-mass 3E capacity can retain an unknown/conflicting optional reference; this does not resolve the stricter cycling admission. 2E author normalizations stay separate, furfural concentration conflict is inspection only; no fitting.')
    def batch24_inspection_rows(self):
        ids={r[0]for r in self.connection.execute('select observation_id from inspection_rows_v24')}
        return[dict(r,training_input_ready=False,purpose_input_ready=False,reason='1M versus6M contradiction remains frozen; own features and literal capacity still inspectable',source_family_group=self.isolation_group(r['source_group']))for r in self.capacitances()if r['observation_id']in ids]
    def auxiliary_gcd(self,profile='3e'):
        out=super().auxiliary_gcd(profile)
        for r in out:
            if r['doi']in NEW24:
                f=self.canonical_material_features_v13(r['doi'],r['sample_name']);r.update(material_features=f['values'],feature_evidence=f['provenance'],excluded_feature_reasons=f['excluded'])
        return out
    def auxiliary_feature_rows(self,profile='3e'):
        rows=super().auxiliary_feature_rows(profile);caps={r['observation_id']:r for r in self.capacitances()if r['doi']in NEW24}
        for r in rows:
            if r['doi']in NEW24:
                cap=caps[r['observation_id']];cap['material_features']=self.canonical_material_features_v13(r['doi'],r['sample_name'])['values'];r.update(self._features24(cap))
        return rows
def open_literature_database(database=None,expected_sha256=None):return LiteratureDatabaseV24(database,expected_sha256)
