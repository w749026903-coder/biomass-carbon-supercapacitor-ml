"""Own stage-qualified inputs and secondary retrieval rows, kept in separate APIs."""
import collections,json
from data.literature_v22 import LiteratureDatabaseV22,FIELDS22
NEW23={'10.3390/molecules30010026','10.1002/cplu.202500342','10.3390/molecules30153125','10.1002/tcr.202600007'}
TARGETS23=('reported_aqueous_3e_GCD_capacitance','feather_Cu_composite_3e_GCD','feather_Cu_composite_2e_author_single_electrode')
FIELDS23=list(dict.fromkeys(FIELDS22+['bulk_EA_C_reported_pct','bulk_EA_H_reported_pct','bulk_EA_N_reported_pct','author_O_by_100_minus_CHN_proxy_pct','author_atomic_O_C_ratio','author_atomic_H_C_ratio','HTC_temperature_C','HTC_duration_min','nominal_Cu_feed_mg_per_g_pine_sawdust']))
class LiteratureDatabaseV23(LiteratureDatabaseV22):
    def batch23_sources(self):return self._rows19('source_reviews_v23')
    def batch23_decisions(self):return self._rows19('decisions_v23')
    def batch23_figures(self):return self._rows19('figure_scope_reviews_v23')
    def batch23_protocols(self):return self._rows19('protocol_reviews_v23')
    def batch23_lineage(self):return self._rows19('material_lineage_v23')
    def batch23_cycle_identity_links(self):return self._rows19('cycle_identity_links_v23')
    def peer_metrics(self):return self._rows19('peer_model_metrics_v23')
    def peer_dataset_audit(self):return self._rows19('peer_dataset_audit_v23')
    def secondary_inspection_rows(self,curator_doi=None,heldout=()):
        """Retrieval/inspection only. A held-out cited source or curator quarantines the row."""
        result=[];held={self.isolation_group(g)for g in heldout}
        for r in self.connection.execute('select *from secondary_rows_v23 order by row_id'):
            if curator_doi and r['curator_doi']!=curator_doi:continue
            x=json.loads(r['record_json']);groups={self.isolation_group(d)for d in [r['curator_doi']]+x['cited_DOIs']}
            result.append(dict(r,record=x,evidence_source_families=sorted(groups),quarantined_for_heldout=bool(groups&held),training_input_ready=False,model_fits=0))
        return result
    def peer_compilation_matrix(self,*args,**kwargs):
        raise ValueError('Secondary compiled rows lack verified primary sample/protocol/normalization. No training matrix is admitted.')
    def facts(self,doi=None,sample=None,field=None):
        rows=super().facts(doi,sample,field);details={r['fact_id']:json.loads(r['record_json'])for r in self.connection.execute('select *from numeric_details_v23')}
        for r in rows:
            if r['fact_id']in details:r['numeric_details_v23']=details[r['fact_id']]
        return rows
    def canonical_material_features_v13(self,doi,sample):
        if doi not in NEW23:return super().canonical_material_features_v13(doi,sample)
        groups=collections.defaultdict(list)
        for r in self.facts(doi,sample):groups[r['field_name']].append(r)
        values={};provenance={};excluded={}
        for f,rs in groups.items():
            observed={r['value']for r in rs if r['value']is not None}
            if any('conflict'in r['review_status']or'ambiguous'in r['review_status']for r in rs)or len(observed)>1:excluded[f]='Unresolved own claim/direction/unit; all literal reports retained.'
            elif len(observed)==1:values[f]=next(iter(observed));provenance[f]=dict(decision='Own sample/stage/method only. Reported EA percentage and O-by-difference proxy retain their separate names; no XPS conversion.',all_reports=rs)
            else:excluded[f]='Unreported is not zero.'
        return dict(values=values,provenance=provenance,excluded=excluded)
    def _features23(self,r):
        v=self._features22(r);v.update(r['material_features'])
        a=next((s for q in self.synthesis(r['doi'],r['sample_name'])for s in q['stages']if s['stage']=='hydrothermal_carbonization'),{})
        v['HTC_temperature_C']=a.get('temperature_C');v['HTC_duration_min']=a.get('duration_min');v['nominal_Cu_feed_mg_per_g_pine_sawdust']=a.get('Cu_feed_mg_per_g_pine_sawdust')
        return v
    def batch23_inputs(self,target=TARGETS23[0]):
        if target not in TARGETS23:raise ValueError('Choose an explicit material and normalization purpose')
        ids={r[0]for r in self.connection.execute('select observation_id from purpose_reviews_v23 where eligible=1 and purpose=?',(target,))};rows=[]
        for r in self.capacitances():
            if r['observation_id']not in ids:continue
            f=self.canonical_material_features_v13(r['doi'],r['sample_name'])
            r.update(target_name=target,material_features=f['values'],feature_evidence=f['provenance'],excluded_feature_reasons=f['excluded'],source_family_group=self.isolation_group(r['source_group']),purpose_input_ready=True,cyclic_retention_training_admitted=False,training_authorized=False,model_fits=0)
            r['matrix_feature_values']=self._features23(r);rows.append(r)
        return sorted(rows,key=lambda r:(r['doi'],r['sample_name'],r['current_A_g']or 0))
    def batch23_matrix(self,target=TARGETS23[0]):
        rows=self.batch23_inputs(target);groups=[r['source_family_group']for r in rows];n=collections.Counter(groups);X=[[r['matrix_feature_values'].get(f)for f in FIELDS23]for r in rows]
        return dict(target=target,feature_names=FIELDS23,X=X,missing_mask=[[v is None for v in x]for x in X],y=[r['value']for r in rows],groups=groups,sample_weight=[1/n[g]for g in groups],observation_ids=[r['observation_id']for r in rows],physical_test_groups=[r['conditions']['physical_test_group']for r in rows],categorical_protocol=[dict(system=r['system'],method=r['method'],electrolyte=r['electrolyte'],capacitance_basis=r['conditions']['capacitance_basis'],cross_source_comparable=r['conditions']['cross_source_comparable'])for r in rows],source_families=len(n),imputed=False,estimators_fitted=0,training_authorized=False,scope='Own zero-Cu controls vs Cu composites separated; competing M3251Ag3E excluded; secondary reviews/peer166 and overlap-pending HDP never training inputs. No cycling admission.')
    def auxiliary_gcd(self,profile='3e'):
        rows=super().auxiliary_gcd(profile)
        for r in rows:
            if r['doi']in NEW23:
                f=self.canonical_material_features_v13(r['doi'],r['sample_name']);r.update(material_features=f['values'],feature_evidence=f['provenance'],excluded_feature_reasons=f['excluded'])
        return rows
    def auxiliary_feature_rows(self,profile='3e'):
        rows=super().auxiliary_feature_rows(profile);caps={r['observation_id']:r for r in self.capacitances()if r['doi']in NEW23}
        for r in rows:
            if r['doi']in NEW23:
                cap=caps[r['observation_id']];cap['material_features']=self.canonical_material_features_v13(r['doi'],r['sample_name'])['values'];r.update(self._features23(cap))
        return rows
def open_literature_database(database=None,expected_sha256=None):return LiteratureDatabaseV23(database,expected_sha256)
