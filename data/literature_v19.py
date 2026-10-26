"""Own lignin, egg/rice and tobacco tables; explicit target and stage boundaries."""
import collections,json
from data.literature_v18 import LiteratureDatabaseV18,FIELDS17
NEW19={'10.1021/acssuschemeng.6c00388','10.3390/molecules28186543','10.3390/molecules28248136'}
TARGETS19=('reported_aqueous_3e_GCD_capacitance','reported_lignin_PEO_2e_factor4_Cs_aqueous','reported_lignin_PEO_2e_factor4_Cs_WIS','reported_aqueous_2e_factor4_Cs')
FIELDS19=FIELDS17+['XPS_C_wt_pct','XPS_N_at_pct','XPS_O_at_pct','SEM_fiber_diameter_mean_nm','packing_density_g_cm3','skeletal_density_He_g_cm3','electrical_conductivity_4point_S_cm','N2_2D_NLDFT_pore_volume_cm3_g','CO2_2D_NLDFT_pore_volume_cm3_g','concentration_mol_kg']
FIELDS19=list(dict.fromkeys(FIELDS19))
class LiteratureDatabaseV19(LiteratureDatabaseV18):
    def _rows19(self,t):return[dict(r,record=json.loads(r['record_json']))for r in self.connection.execute('select *from '+t)]
    def batch19_sources(self):return self._rows19('source_reviews_v19')
    def batch19_decisions(self):return self._rows19('decisions_v19')
    def batch19_figures(self):return self._rows19('figure_scope_reviews_v19')
    def batch19_annotations(self):return self._rows19('annotations_v19')
    def batch19_cycle_identity_links(self):return self._rows19('cycle_identity_links_v19')
    def batch19_raw_dispositions(self):return self._rows19('raw_candidate_dispositions_v19')
    def batch19_lineage(self):return self._rows19('material_lineage_v19')
    def facts(self,doi=None,sample=None,field=None):
        rows=super().facts(doi,sample,field);details={r['fact_id']:json.loads(r['record_json'])for r in self.connection.execute('select *from numeric_details_v19')}
        for r in rows:
            if r['fact_id']in details:r['numeric_details_v19']=details[r['fact_id']]
        return rows
    def canonical_material_features_v13(self,doi,sample):
        if doi not in NEW19:return super().canonical_material_features_v13(doi,sample)
        reports=collections.defaultdict(list)
        for r in self.facts(doi,sample):reports[r['field_name']].append(r)
        values={};provenance={};excluded={}
        for f,rs in reports.items():
            observed={r['value']for r in rs if r['value']is not None}
            if any('conflict'in r['review_status']for r in rs)or len(observed)>1:excluded[f]='Competing or disputed own reports; raw values and methods retained.'
            elif len(observed)==1:values[f]=next(iter(observed));provenance[f]=dict(decision='Same own material and stage; uncertainty/censoring metadata retained',all_reports=rs)
            else:excluded[f]='No selected numeric scalar: unreported/dash, censored or ambiguous printed value.'
        return dict(values=values,provenance=provenance,excluded=excluded)
    def auxiliary_gcd(self,profile='3e'):
        rows=super().auxiliary_gcd(profile)
        for r in rows:
            if r['doi']in NEW19:
                x=self.canonical_material_features_v13(r['doi'],r['sample_name']);r.update(material_features=x['values'],feature_evidence=x['provenance'],excluded_feature_reasons=x['excluded'])
        return rows
    def _features19(self,r):
        v=self._features17(r);stages=[s for rec in self.synthesis(doi=r['doi'],sample=r['sample_name'])for s in rec['stages']]
        a=next((s for s in stages if s['stage']=='activation'),{})
        if a:
            for f in ['temperature_C','duration_h','heating_rate_C_min']:v['activation_'+f]=a.get(f)
            ratio=a.get('char_to_activator_mass_ratio');v['activator_to_carbon_mass_ratio']=ratio[1]/ratio[0]if ratio else None
        a=next((s for s in stages if s['stage']=='single_carbonization_activation'),{})
        ratio=a.get('feedstock_melamine_K2CO3_mass_ratio');
        if ratio:v['single_stage_activator_to_feedstock_mass_ratio']=ratio[2]/ratio[0]
        v['concentration_mol_kg']=r['conditions'].get('concentration_mol_kg');return v
    def batch19_inputs(self,target=TARGETS19[0]):
        if target not in TARGETS19:raise ValueError('Choose one explicitly separate v19 target')
        ids={r[0]for r in self.connection.execute('select observation_id from purpose_reviews_v19 where eligible=1 and purpose=?',(target,))};rows=[]
        for r in self.capacitances():
            if r['observation_id']not in ids:continue
            x=self.canonical_material_features_v13(r['doi'],r['sample_name']);r.update(target_name=target,material_features=x['values'],feature_evidence=x['provenance'],excluded_feature_reasons=x['excluded'],source_family_group=self.isolation_group(r['source_group']),purpose_input_ready=True,cyclic_retention_training_admitted=False,training_authorized=False,model_fits=0)
            r['matrix_feature_values']=self._features19(r);rows.append(r)
        return sorted(rows,key=lambda r:(r['doi'],r['sample_name'],r['current_A_g']))
    def batch19_matrix(self,target=TARGETS19[0]):
        rows=self.batch19_inputs(target);groups=[r['source_family_group']for r in rows];counts=collections.Counter(groups);X=[[r['matrix_feature_values'].get(f)for f in FIELDS19]for r in rows]
        return dict(target=target,feature_names=FIELDS19,X=X,missing_mask=[[v is None for v in rr]for rr in X],y=[r['value']for r in rows],groups=groups,sample_weight=[1/counts[g]for g in groups],observation_ids=[r['observation_id']for r in rows],source_families=len(counts),imputed=False,estimators_fitted=0,training_authorized=False,excluded_from_X=['source/sample/curve IDs and all electrochemical outcomes','raw lignin NMR/GPC/CHNS or dope values inherited as final-carbon properties','unknown XPS atom/weight projections or normalized disputed percentages','unreported/ambiguous/censored point values','fresh fifth-cycle index used as cycling retention baseline'])
    def auxiliary_feature_rows(self,profile='3e'):
        rows=super().auxiliary_feature_rows(profile)
        caps={r['observation_id']:r for r in self.capacitances()if r['doi']in NEW19}
        for r in rows:
            if r['doi']in NEW19:
                cap=caps[r['observation_id']];cap['material_features']=self.canonical_material_features_v13(r['doi'],r['sample_name'])['values'];r.update(self._features19(cap))
        return rows
def open_literature_database(database=None,expected_sha256=None):return LiteratureDatabaseV19(database,expected_sha256)
