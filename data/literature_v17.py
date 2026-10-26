"""Five method-qualified source series; explicit 2E formula/electrolyte targets.

Current-source facts override only via evidence decisions. All historical rows
and APIs remain available. Purpose input readiness does not authorize fitting.
"""
import collections,json
from data.literature_v16 import LiteratureDatabaseV16,FIELDS16
NEW17={'10.1002/cssc.202200651','10.3390/molecules29112532','10.3390/polym15234478','10.1021/acsomega.2c07932','10.3390/nano14161368'}
TARGETS17=('reported_aqueous_3e_GCD_capacitance','reported_aqueous_2e_factor2_Cs','reported_organic_2e_factor4_Cs')
FIELDS17=FIELDS16+['bulk_EA_C_wt_pct','bulk_EA_N_wt_pct','bulk_EA_O_wt_pct','bulk_EA_S_wt_pct','XPS_N_wt_pct','XPS_O_wt_pct','XPS_S_wt_pct','hydrothermal_temperature_C','hydrothermal_duration_h','precarbonization_temperature_C','precarbonization_duration_h','single_carbonization_activation_temperature_C','single_carbonization_activation_duration_h','single_carbonization_activation_heating_rate_C_min','single_stage_activator_to_feedstock_mass_ratio','extrusion_screw_speed_rpm','extrusion_barrel_temperature_C','extrusion_feed_rate_g_min']

class LiteratureDatabaseV17(LiteratureDatabaseV16):
    def _rows17(self,table):return[dict(r,record=json.loads(r['record_json']))for r in self.connection.execute('select *from '+table)]
    def batch17_sources(self):return self._rows17('source_reviews_v17')
    def batch17_decisions(self):return self._rows17('decisions_v17')
    def batch17_figures(self):return self._rows17('figure_scope_reviews_v17')
    def batch17_annotations(self):return self._rows17('annotations_v17')
    def batch17_cycle_identity_links(self):return self._rows17('cycle_identity_links_v17')
    def canonical_material_features_v13(self,doi,sample):
        if doi not in NEW17:return super().canonical_material_features_v13(doi,sample)
        reports=collections.defaultdict(list)
        for r in self.facts(doi=doi,sample=sample):reports[r['field_name']].append(r)
        decisions={r['field_name']:json.loads(r['record_json'])for r in self.connection.execute('select x.*from material_feature_decisions_v17 x join materials m using(material_key)where m.doi=?and m.sample_name=?',(doi,sample))}
        values={};provenance={};excluded={}
        for f,rs in reports.items():
            observed={r['value']for r in rs if r['value']is not None}
            if f in decisions:
                d=decisions[f];assert d['selected_value']in observed;values[f]=d['selected_value'];provenance[f]=dict(decision=d,all_reports=rs)
            elif any('conflict'in r['review_status']or'not_applicable'in r['review_status']for r in rs)or len(observed)>1:excluded[f]='Competing values, dimensional dispute, or table defaults not applicable to actual process; raw reports retained.'
            elif len(observed)==1:values[f]=next(iter(observed));provenance[f]=dict(decision='Matching own reports, stage/method/basis retained',all_reports=rs)
            else:excluded[f]='No numeric author value; blank/dash/ND does not mean zero.'
        return dict(values=values,provenance=provenance,excluded=excluded)

    def auxiliary_gcd(self,profile='3e'):
        rows=super().auxiliary_gcd(profile)
        for r in rows:
            if r['doi']not in NEW17:continue
            x=self.canonical_material_features_v13(r['doi'],r['sample_name']);r.update(material_features=x['values'],feature_evidence=x['provenance'],excluded_feature_reasons=x['excluded'])
        return rows

    def batch17_inputs(self,target='reported_aqueous_3e_GCD_capacitance'):
        if target not in TARGETS17:raise ValueError('Choose one explicitly separate v17 target: '+', '.join(TARGETS17))
        ids={r['observation_id']:r for r in self.connection.execute('select *from purpose_reviews_v17 where eligible=1 and purpose=?',(target,))}
        result=[]
        for r in self.capacitances():
            if r['observation_id']not in ids:continue
            x=self.canonical_material_features_v13(r['doi'],r['sample_name']);row=dict(r,target_name=target,material_features=x['values'],feature_evidence=x['provenance'],excluded_feature_reasons=x['excluded'],source_family_group=self.isolation_group(r['source_group']),purpose_input_ready=True,cyclic_retention_training_admitted=False,model_fits=0)
            row['matrix_feature_values']=self._features17(row);result.append(row)
        return sorted(result,key=lambda r:(r['doi'],r['sample_name'],r['current_A_g']))

    def _features17(self,row):
        values=self._rate_feature_values16(row)
        stages=[s for rec in self.synthesis(doi=row['doi'],sample=row['sample_name'])for s in rec['stages']]
        for kind in ['hydrothermal','precarbonization','single_carbonization_activation']:
            stage=next((s for s in stages if s['stage']==kind),{})
            for f in ['temperature_C','duration_h','heating_rate_C_min']:values[kind+'_'+f]=stage.get(f)
        stage=next((s for s in stages if s['stage']=='single_carbonization_activation'),{})
        ratio=stage.get('carbon_to_activator_mass_ratio')or stage.get('starch_to_activator_mass_ratio')
        values['single_stage_activator_to_feedstock_mass_ratio']=ratio[1]/ratio[0]if ratio else None
        for rec in stages:
            if rec['stage']=='mechanochemical_precursor':
                for field in ['screw_speed_rpm','barrel_temperature_C','feed_rate_g_min']:values['extrusion_'+field]=rec.get(field)
        return values

    def batch17_matrix(self,target='reported_aqueous_3e_GCD_capacitance'):
        rows=self.batch17_inputs(target);groups=[r['source_family_group']for r in rows];counts=collections.Counter(groups);X=[[r['matrix_feature_values'].get(f)for f in FIELDS17]for r in rows]
        return dict(target=target,feature_names=FIELDS17,X=X,missing_mask=[[v is None for v in rr]for rr in X],y=[r['value']for r in rows],groups=groups,sample_weight=[1/counts[g]for g in groups],observation_ids=[r['observation_id']for r in rows],physical_test_groups=[r['conditions']['physical_test_group']for r in rows],categorical_protocol=[dict(system=r['system'],electrolyte=r['electrolyte'],capacitance_basis=r['conditions']['capacitance_basis'],reference_electrode=r['conditions'].get('reference_electrode'))for r in rows],imputed=False,estimators_fitted=0,training_authorized=False,source_families=len(set(groups)),excluded_from_X=['all capacitance/cycling/CE/rate/EIS/Ragone/STY responses','source/sample/curve identifiers','raw/other-stage composition','XPS wt percent interpreted as at percent','rice printed m3/g as standard BET','ballmill table defaults','inferred voltage from energy formula'])

    def auxiliary_feature_rows(self,profile='3e'):
        rows=super().auxiliary_feature_rows(profile)
        for r in rows:
            if r['doi']not in NEW17:continue
            cap=next(v for v in self.capacitances(doi=r['doi'],sample=r['sample_name'])if v['observation_id']==r['observation_id']);cap['material_features']=self.canonical_material_features_v13(r['doi'],r['sample_name'])['values'];r.update(self._features17(cap))
        return rows

    def expanded_graph_3e_matrix(self):
        result=super().expanded_graph_3e_matrix();result['cohort']='current_ordinary3E_plus75_v16_bounded_graph_conditions';return result

def open_literature_database(database=None,expected_sha256=None):return LiteratureDatabaseV17(database,expected_sha256)
