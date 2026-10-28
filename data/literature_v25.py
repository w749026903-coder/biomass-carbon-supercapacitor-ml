"""Forward-only wheat-husk figure evidence and two separately normalized rate series."""
import collections,json
from data.literature_v24 import LiteratureDatabaseV24,FIELDS24
DOI25='10.3390/nano12213804'
PURPOSES25=('wheat_husk_3e_reported_capacity','wheat_husk_2e_factor4_total_active_mass_Cs')
MODES25=('author_exact','point_mixed','figure_only')

class LiteratureDatabaseV25(LiteratureDatabaseV24):
    def batch25_figures(self):return self._rows19('figure_reviews_v25')
    def batch25_decisions(self):return self._rows19('decisions_v25')
    def batch25_protocol_bindings(self):return self._rows19('protocol_bindings_v25')
    def capacitances(self,doi=None,sample=None,method=None,electrolyte=None):
        rows=super().capacitances(doi,sample,method,electrolyte)
        fixes={r['observation_id']:r['record']for r in self.batch25_protocol_bindings()}
        for r in rows:
            if r['observation_id']in fixes:
                r['original_conditions_v24']=dict(r['conditions'])
                r['conditions']=dict(r['conditions'],voltage_lower_V=0,voltage_upper_V=1,voltage_evidence_v25=fixes[r['observation_id']],device_window_not_inherited_from_3E=True)
        return rows

    def batch25_rate_inputs(self,mode='point_mixed',purpose=PURPOSES25[0]):
        if mode not in MODES25 or purpose not in PURPOSES25:raise ValueError('Choose explicit wheat-husk system/normalization and rate mode')
        caps={r['observation_id']:r for r in self.capacitances(DOI25)};out=[]
        for rr in self.connection.execute('select *from rate_reviews_v25 where purpose=?order by reading_id',(purpose,)):
            proof=json.loads(rr['record_json']);anchor=caps.get(proof['author_exact_observation_id'])
            if mode=='author_exact'and anchor is None:continue
            if anchor is not None and mode!='figure_only':
                item=dict(anchor,target_value=anchor['value'],target_value_kind='author_reported_exact',target_lower_bound=None,target_upper_bound=None)
            else:
                item=dict(caps[rr['observation_id']],target_value=proof['y_value'],target_value_kind='bounded_original_figure',target_lower_bound=proof['y_lower_bound'],target_upper_bound=proof['y_upper_bound'])
            features=self.canonical_material_features_v13(DOI25,item['sample_name'])
            item.update(target_mode=mode,target_purpose=purpose,graph_reading_id=proof['reading_id'],graph_observation_id=rr['observation_id'],material_features=features['values'],feature_evidence=features['provenance'],excluded_feature_reasons=features['excluded'],source_family_group=self.isolation_group(item['source_group']),nominal_report_group=proof['nominal_report_group'],physical_test_group=proof['nominal_report_group'],current_graphical_bounds=[proof['x_value']-proof['x_uncertainty'],proof['x_value']+proof['x_uncertainty']],pixel_reading_bounds_not_SD_or_CI=True,purpose_input_ready=True,cyclic_retention_training_admitted=False,model_fits=0,training_authorized=False)
            item['matrix_feature_values']=self._features24(item);out.append(item)
        return sorted(out,key=lambda r:(r['sample_name'],r['current_A_g']))

    def batch25_rate_matrix(self,mode='point_mixed',purpose=PURPOSES25[0]):
        rows=self.batch25_rate_inputs(mode,purpose);X=[[r['matrix_feature_values'].get(f)for f in FIELDS24]for r in rows];groups=[r['source_family_group']for r in rows];counts=collections.Counter(groups)
        return dict(target=purpose,mode=mode,feature_names=FIELDS24,X=X,y=[r['target_value']for r in rows],missing_mask=[[v is None for v in x]for x in X],y_lower=[r['target_lower_bound']for r in rows],y_upper=[r['target_upper_bound']for r in rows],observation_ids=[r['observation_id']for r in rows],nominal_report_groups=[r['nominal_report_group']for r in rows],groups=groups,sample_weight=[1/counts[g]for g in groups],source_families=len(counts),categorical_protocol=[dict(system=r['system'],electrolyte=r['electrolyte'],capacitance_basis=r['conditions']['capacitance_basis'])for r in rows],imputed=False,estimators_fitted=0,training_authorized=False,scope='Eight author anchors already existed; 20 graph captures represent 20 nominal conditions, only12 additional conditions. Modes are nested alternatives. Two electrode Cs=4I*dt/(total active mass*dV) stays separate from working-electrode capacity; all targets/cycles/stages share one DOI holdout.')

    def expanded_graph_3e_inputs(self):
        rows=super().expanded_graph_3e_inputs();ids={r['observation_id']for r in rows}
        for r in self.batch25_rate_inputs('point_mixed',PURPOSES25[0]):
            if r['observation_id']not in ids:
                assert r['target_value_kind']=='bounded_original_figure';rows.append(r)
        return rows
    def expanded_graph_3e_matrix(self):
        result=super().expanded_graph_3e_matrix();result['cohort']='current_ordinary3E_plus_explicit_v16_v18_v25_bounded_graph_conditions';result['nominal_report_groups']=[r.get('nominal_report_group',r.get('physical_test_group'))for r in self.expanded_graph_3e_inputs()];return result

def open_literature_database(database=None,expected_sha256=None):return LiteratureDatabaseV25(database,expected_sha256)
