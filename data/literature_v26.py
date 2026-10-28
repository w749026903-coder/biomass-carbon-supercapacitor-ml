"""All wood-temperature controls/composites with per-field disputes preserved."""
import collections,json
from data.literature_v25 import LiteratureDatabaseV25
from data.literature_v24 import FIELDS24
DOI26='10.1016/j.heliyon.2024.e25628'
TARGETS26=('reported_aqueous_3e_GCD_capacitance','wood_MnO2_3e_author_capacity')
FIELDS26=list(dict.fromkeys(FIELDS24+['H3PO4_stock_mass_percent','H3PO4_stock_molarity_M','wetting_temperature_C','wetting_duration_h','preheat_temperature_C','preheat_duration_h','N2_flow_mL_min','carbon_component_carbonization_temperature_C']))

class LiteratureDatabaseV26(LiteratureDatabaseV25):
    def batch26_decisions(self):return self._rows19('decisions_v26')
    def batch26_figures(self):return self._rows19('figure_reviews_v26')
    def batch26_protocol(self):return self._rows19('protocol_reviews_v26')
    def batch26_lineage(self):return self._rows19('material_lineage_v26')
    def batch26_cycle_claims(self):return self._rows19('cycle_claims_v26')
    def batch26_cycle_links(self):return self._rows19('cycle_links_v26')
    def batch26_annotations(self):return self._rows19('annotations_v26')
    def facts(self,doi=None,sample=None,field=None):
        rows=super().facts(doi,sample,field);details={r['fact_id']:json.loads(r['record_json'])for r in self.connection.execute('select *from numeric_details_v26')}
        for r in rows:
            if r['fact_id']in details:r['numeric_details_v26']=details[r['fact_id']]
        return rows
    def canonical_material_features_v13(self,doi,sample):
        if doi!=DOI26:return super().canonical_material_features_v13(doi,sample)
        rr=collections.defaultdict(list)
        for r in self.facts(doi,sample):rr[r['field_name']].append(r)
        values={};provenance={};excluded={}
        for f,rs in rr.items():
            nums={r['value']for r in rs if r['value']is not None}
            if any('conflict'in r['review_status']for r in rs)or len(nums)>1:excluded[f]='Own figure/body direction or numeric dispute; no inversion, performance selection or inheritance.'
            elif len(nums)==1:values[f]=next(iter(nums));provenance[f]=dict(decision='Own final sample and method only; no precursor/composite inheritance',all_reports=rs)
            else:excluded[f]='No own scalar reported/located; a bound is not an exact value and absence is not zero.'
        return dict(values=values,provenance=provenance,excluded=excluded)
    def _features26(self,r):
        v=self._features24(r);ss=[s for record in self.synthesis(r['doi'],r['sample_name'])for s in record['stages']]
        wet=next((s for s in ss if s['stage']=='phosphoric_wetting'),{});pre=next((s for s in ss if s['stage']=='preheat_before_carbonization'),{});carb=next((s for s in ss if s['stage']=='carbonization'),{});mix=next((s for s in ss if s['stage']=='composite_electrode_blending'),{})
        for field,key in [('H3PO4_stock_mass_percent','stock_mass_percent'),('H3PO4_stock_molarity_M','stock_molarity_M'),('wetting_temperature_C','temperature_C'),('wetting_duration_h','duration_h')]:v[field]=wet.get(key)
        v['preheat_temperature_C']=pre.get('temperature_C');v['preheat_duration_h']=pre.get('duration_h');v['N2_flow_mL_min']=carb.get('N2_flow_mL_min');v['carbon_component_carbonization_temperature_C']=mix.get('carbon_component_carbonization_temperature_C')
        return v
    def batch26_inputs(self,target=TARGETS26[0]):
        if target not in TARGETS26:raise ValueError('Explicit report-purpose target required; disputed400C reports are inspection only')
        ids={r[0]for r in self.connection.execute('select observation_id from purpose_reviews_v26 where purpose=?',(target,))};out=[]
        for r in self.capacitances(DOI26):
            if r['observation_id']not in ids:continue
            f=self.canonical_material_features_v13(r['doi'],r['sample_name']);r.update(target_name=target,material_features=f['values'],feature_evidence=f['provenance'],excluded_feature_reasons=f['excluded'],source_family_group=self.isolation_group(r['source_group']),purpose_input_ready=True,cyclic_retention_training_admitted=False,training_authorized=False,model_fits=0)
            r['matrix_feature_values']=self._features26(r);out.append(r)
        return sorted(out,key=lambda r:r['sample_name'])
    def batch26_matrix(self,target=TARGETS26[0]):
        rows=self.batch26_inputs(target);groups=[r['source_family_group']for r in rows];counts=collections.Counter(groups);X=[[r['matrix_feature_values'].get(f)for f in FIELDS26]for r in rows]
        return dict(target=target,feature_names=FIELDS26,X=X,y=[r['value']for r in rows],missing_mask=[[v is None for v in row]for row in X],groups=groups,sample_weight=[1/counts[g]for g in groups],source_families=len(counts),observation_ids=[r['observation_id']for r in rows],physical_test_groups=[r['conditions']['physical_test_group']for r in rows],categorical_protocol=[dict(system=r['system'],electrolyte=r['electrolyte'],capacitance_basis=r['conditions']['capacitance_basis'],reference_electrode=r['conditions']['reference_electrode'],material_scope=r['conditions']['material_scope'])for r in rows],imputed=False,estimators_fitted=0,training_authorized=False,scope='Three own carbon reports versus three MnO2 composite reports, sameDOI; 400Ctarget disputes held. AC500BETmissing is masked for this auxiliary purpose, not cleared for cycling. Author DT/capacity tension retained; no recalculation. No composite BET inherited from carbon.')
    def batch26_inspection_rows(self):
        ids={r[0]for r in self.connection.execute('select observation_id from inspection_rows_v26')}
        return[dict(r,purpose_input_ready=False,training_input_ready=False,reason='AC400183.4/184.4 orHC400491.0/491.3 remains disputed; all source statements preserved')for r in self.capacitances(DOI26)if r['observation_id']in ids]
    def auxiliary_gcd(self,profile='3e'):
        rows=super().auxiliary_gcd(profile)
        for r in rows:
            if r['doi']==DOI26:
                f=self.canonical_material_features_v13(r['doi'],r['sample_name']);r.update(material_features=f['values'],feature_evidence=f['provenance'],excluded_feature_reasons=f['excluded'])
        return rows
    def auxiliary_feature_rows(self,profile='3e'):
        rows=super().auxiliary_feature_rows(profile);caps={r['observation_id']:r for r in self.capacitances(DOI26)}
        for r in rows:
            if r['doi']==DOI26:
                cap=caps[r['observation_id']];cap['material_features']=self.canonical_material_features_v13(DOI26,r['sample_name'])['values'];r.update(self._features26(cap))
        return rows

def open_literature_database(database=None,expected_sha256=None):return LiteratureDatabaseV26(database,expected_sha256)
