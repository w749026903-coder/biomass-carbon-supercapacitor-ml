"""Three-source rate series with occlusion masks and explicit native-silica use."""
import collections,json
from data.literature_v17 import LiteratureDatabaseV17,FIELDS17
PURPOSE18={'ordinary_3e':'explicit_ordinary_3e_GCD_with_graphical_values','native_silica_3e':'reported_native_silica_rice_3e_GCD'}
DOI18={'10.3390/molecules29112532','10.1021/acsomega.2c07932','10.3390/nano14161368'}

class LiteratureDatabaseV18(LiteratureDatabaseV17):
    def _rows18(self,t):return[dict(r,record=json.loads(r['record_json']))for r in self.connection.execute('select *from '+t)]
    def batch18_decisions(self):return self._rows18('decisions_v18')
    def batch18_sources(self):return self._rows18('source_reviews_v18')
    def batch18_cycle_reviews(self):return self._rows18('cycle_reviews_v18')
    def batch18_figure_identities(self):return[dict(r,record=json.loads(r['record_json']))for r in self.connection.execute('select *from figure_identity_resolution_v18 order by document_key')]
    def batch18_binding_corrections(self):return self._rows18('source_binding_corrections_v18')
    def _resolved18(self):return{r['table_key']:dict(r)for r in self.connection.execute('select *from resolved_table_sources_v18 where binding_corrected=1')}
    def facts(self,doi=None,sample=None,field=None):
        rows=super().facts(doi,sample,field);resolved=self._resolved18()
        for r in rows:
            if r['table_key']not in resolved:continue
            d=resolved[r['table_key']];r['original_provenance_v17']={k:r[k]for k in ['source_path','source_sha256','locator']};r.update(source_path=d['path'],source_sha256=d['sha256'],current_source_binding_correction_v18=True,current_document_key=d['document_key'],source_binding_basis='Printed figure label and original graphic href; v17 ordinal offset retained as original_provenance_v17')
        return rows
    def outcomes(self,metric=None):
        rows=super().outcomes(metric);resolved=self._resolved18()
        for r in rows:
            if r['table_key']in resolved:r['current_provenance_v18']=resolved[r['table_key']]
        return rows
    def batch17_annotations(self):
        rows=super().batch17_annotations()
        for r in rows:
            if r['doi']=='10.3390/molecules29112532':r.update(original_document_key_v17=r['document_key'],document_key='Starch18_ActualFig3',source_binding_correction_v18=True)
        return rows
    def batch17_figures(self):
        rows=super().batch17_figures();mapping={r['document_key']:r for r in self.batch18_figure_identities()}
        for r in rows:
            if r['document_key']in mapping:
                label=mapping[r['document_key']]['printed_label'];r.update(original_ordinal_v17=r['figure_number'],printed_label=label,figure_number=int(label.split()[-1])if label.startswith('Figure ')else None)
        return rows
    def tests(self):
        rows=super().tests();reviews={r['candidate_id']:r['record']for r in self.batch18_cycle_reviews()}
        for r in rows:
            if r['candidate_id']in reviews:r['current_review_v18']=reviews[r['candidate_id']]
        return rows
    def batch18_rate_inputs(self,mode='author_exact',purpose='ordinary_3e'):
        if mode not in ['author_exact','point_mixed','figure_only']or purpose not in PURPOSE18:raise ValueError('Choose author_exact/point_mixed/figure_only and ordinary_3e/native_silica_3e explicitly')
        review={r['observation_id']:dict(r,reading=json.loads(r['record_json']))for r in self.connection.execute('select *from purpose_reviews_v18 where is_primary=1 and purpose=?',(PURPOSE18[purpose],))}
        anchors={r['observation_id']:r for r in self.auxiliary_gcd('3e')if r['doi']in DOI18};rows=[]
        for r in self.capacitances():
            if r['observation_id']not in review:continue
            proof=review[r['observation_id']];rr=proof['reading'];anchor=anchors.get(rr['author_exact_observation_id'])
            if mode=='author_exact'and not anchor:continue
            if mode=='point_mixed'and not(anchor or proof['eligible']):continue
            if mode!='figure_only'and anchor:
                item=dict(anchor,target_value=anchor['value'],target_lower_bound=None,target_upper_bound=None,target_value_kind='author_reported_preserved:'+anchor['status'],graph_reading_id=rr['reading_id'],nominal_report_group=rr['nominal_report_group'])
            else:
                item=dict(r,target_value=r['value'],target_lower_bound=rr['y_lower_bound'],target_upper_bound=rr['y_upper_bound'],target_value_kind='bounded_original_figure'if r['value']is not None else'occluded_original_marker_no_numeric_bound',graph_reading_id=rr['reading_id'],nominal_report_group=rr['nominal_report_group'])
            features=self.canonical_material_features_v13(item['doi'],item['sample_name']);item.update(material_features=features['values'],feature_evidence=features['provenance'],excluded_feature_reasons=features['excluded'],source_family_group=self.isolation_group(item['source_group']),target_mode=mode,target_purpose=purpose,current_graphical_bounds=[rr['x_lower_bound'],rr['x_upper_bound']],graphical_bounds_not_experimental_CI=True,physical_replicate_identity_not_proven=True,point_target_ready=item['target_value']is not None,training_authorized=False,model_fits=0)
            item['matrix_feature_values']=self._features17(item);rows.append(item)
        return sorted(rows,key=lambda r:(r['doi'],r['sample_name'],r['current_A_g']))
    def batch18_rate_matrix(self,mode='author_exact',purpose='ordinary_3e'):
        rows=self.batch18_rate_inputs(mode,purpose)
        if any(r['target_value']is None for r in rows):raise ValueError('Occluded marker rows are inspection-only; choose point_mixed. No midpoint, interpolation, or unbounded target may enter a point matrix.')
        groups=[r['source_family_group']for r in rows];counts=collections.Counter(groups);X=[[r['matrix_feature_values'].get(f)for f in FIELDS17]for r in rows]
        return dict(target='reported_3e_GCD_capacitance_F_g',purpose=purpose,target_mode=mode,feature_names=FIELDS17,X=X,missing_mask=[[v is None for v in xx]for xx in X],y=[r['target_value']for r in rows],y_lower=[r['target_lower_bound']for r in rows],y_upper=[r['target_upper_bound']for r in rows],current_reading_bounds=[r['current_graphical_bounds']for r in rows],groups=groups,sample_weight=[1/counts[g]for g in groups],observation_ids=[r['observation_id']for r in rows],nominal_report_groups=[r['nominal_report_group']for r in rows],source_families=len(set(groups)),imputed=False,estimators_fitted=0,training_authorized=False,physical_replicate_identity_not_proven=True,excluded_from_X=['all electrochemical responses and target values','source/sample/curve identifiers','disputed Rice standardBET','inherited raw or intermediate composition','unreported SD and occluded targets'])
    def expanded_graph_3e_inputs(self):
        rows=super().expanded_graph_3e_inputs();ids={r['observation_id']for r in rows}
        for r in self.batch18_rate_inputs('point_mixed','ordinary_3e'):
            if r['observation_id']in ids:continue
            assert r['target_value_kind']=='bounded_original_figure';r['physical_test_group']=None;rows.append(r)
        return rows
    def expanded_graph_3e_matrix(self):
        result=super().expanded_graph_3e_matrix();result['cohort']='current_ordinary3E_plus_explicit_v16_v18_bounded_graph_conditions';result['nominal_report_groups']=[r.get('nominal_report_group',r.get('physical_test_group'))for r in self.expanded_graph_3e_inputs()];result['physical_replicate_identity_not_proven_for_v18']=True;return result

def open_literature_database(database=None,expected_sha256=None):return LiteratureDatabaseV18(database,expected_sha256)
