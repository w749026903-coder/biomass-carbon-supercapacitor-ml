"""Read-only, method-specific targets from Cycas and coconut; no model fitting."""
import collections,json
from data.literature_v11 import LiteratureDatabaseV11

TARGETS12 = {
    '3e_volume': ('reported_3e_author_density_volume', 'F/cm3'),
    '2e_aqueous_Cs': ('reported_2e_aqueous_author_Cs_factor4', 'F/g'),
    '2e_aqueous_Cd': ('reported_2e_aqueous_author_Cd', 'F/g'),
    '2e_ionic_Cs': ('reported_2e_ionic_author_Cs_factor4', 'F/g'),
    '2e_ionic_Cd': ('reported_2e_ionic_author_Cd', 'F/g'),
}

class LiteratureDatabaseV12(LiteratureDatabaseV11):
    def batch12_sources(self):
        return [dict(r,record=json.loads(r['record_json'])) for r in self.connection.execute('select *from source_reviews_v12 order by doi')]

    def batch12_decisions(self):
        return [dict(r,record=json.loads(r['record_json'])) for r in self.connection.execute('select *from decisions_v12 order by decision_id')]

    def batch12_inputs(self, target):
        if target not in TARGETS12:raise ValueError('Choose one separate v12 target: '+', '.join(TARGETS12))
        purpose,unit=TARGETS12[target]
        admitted={r['observation_id'] for r in self.connection.execute('select observation_id from purpose_reviews_v12 where eligible=1 and purpose=?',(purpose,))}
        result=[]
        for x in self.capacitances():
            if x['observation_id'] not in admitted:continue
            assert x['unit']==unit and x['method']=='GCD'
            features={};excluded={};provenance={}
            grouped=collections.defaultdict(list)
            for f in self.facts(doi=x['doi'],sample=x['sample_name']):grouped[f['field_name']].append(f)
            for field,evidence in grouped.items():
                # Freeze the entire competing field; do not take the only unflagged report.
                if any('conflict' in f['review_status'] for f in evidence):
                    excluded[field]='Competing own reports preserved; canonical feature frozen.';continue
                values={f['value'] for f in evidence if f['value'] is not None}
                if len(values)==1:features[field]=next(iter(values));provenance[field]=evidence
                elif len(values)>1:excluded[field]='Competing values need an explicit decision.'
            if target=='3e_volume':
                for field in list(features):
                    if 'density' in field:excluded[field]='Author density is part of target derivation, not an independent measured predictor.';del features[field]
            item=dict(x,purpose=purpose,target_name=purpose,target_unit=unit,target_value=x['value'],source_family_group=self.isolation_group(x['source_group']),material_features=features,feature_evidence=provenance,excluded_feature_reasons=excluded,synthesis=self.synthesis(doi=x['doi'],sample=x['sample_name']),auxiliary_input_ready=True)
            item['feature_boundary']='Pretest properties and explicit protocol only; Cs/Cd/volume, same-test EIS, retention, energy and power are responses. All tasks from one source family are quarantined together.'
            result.append(item)
        return result

    def batch12_matrix(self,target):
        """One explicit target only. Missing numeric inputs stay null; nothing is fitted."""
        rows=self.batch12_inputs(target)
        fields=['BET_surface_area_m2_g','total_pore_volume_cm3_g','micropore_volume_cm3_g','XPS_C_at_pct','XPS_N_at_pct','XPS_O_at_pct','Raman_ID_IG','Raman_integrated_area_ID_IG','XRD_d002_nm']
        protocol_fields=['reported_current_A_g','concentration_mol_L','voltage_lower_V','voltage_upper_V']
        X=[[r['material_features'].get(f)for f in fields]+[r['current_A_g'],r['concentration_mol_L'],r['conditions'].get('voltage_lower_V'),r['conditions'].get('voltage_upper_V')]for r in rows]
        groups=[r['source_family_group']for r in rows];counts=collections.Counter(groups)
        return dict(target=target,unit=TARGETS12[target][1],feature_names=fields+protocol_fields,X=X,missing_mask=[[v is None for v in row]for row in X],y=[r['target_value']for r in rows],groups=groups,sample_weight=[1/counts[g]for g in groups],observation_ids=[r['observation_id']for r in rows],physical_test_groups=[r['conditions']['physical_test_group']for r in rows],protocols=[r['conditions']for r in rows],model_fits=0)

def open_literature_database(database=None,expected_sha256=None):return LiteratureDatabaseV12(database,expected_sha256)
