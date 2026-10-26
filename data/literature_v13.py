"""Method-qualified source series and explicitly separate residue/reference uses."""
import collections,json
from data.literature_v12 import LiteratureDatabaseV12

NEW_DOIS={'10.1039/d5ra02129d','10.1039/d6ra04144b','10.3390/polym16233421','10.1039/d6ra08120g'}

class LiteratureDatabaseV13(LiteratureDatabaseV12):
    def is_quarantined_source(self,raw_group,heldout):
        """Compare canonical families, including bare DOI and doi: spellings."""
        return self.isolation_group(raw_group)in{self.isolation_group(g)for g in heldout}

    def batch13_sources(self):
        return [dict(r,record=json.loads(r['record_json']))for r in self.connection.execute('select *from source_reviews_v13 order by doi')]

    def batch13_decisions(self):
        return [dict(r,record=json.loads(r['record_json']))for r in self.connection.execute('select *from decisions_v13 order by decision_id')]

    def canonical_material_features_v13(self,doi,sample):
        """Explicit decisions precede consensus. Unresolved fields stay absent."""
        reports=collections.defaultdict(list)
        for f in self.facts(doi=doi,sample=sample):reports[f['field_name']].append(f)
        decisions={r['field_name']:json.loads(r['record_json'])for r in self.connection.execute('select x.*from material_feature_decisions_v13 x join materials m using(material_key)where m.doi=?and m.sample_name=?',(doi,sample))}
        values={};provenance={};excluded={}
        for field,rs in reports.items():
            observed={r['value']for r in rs if r['value']is not None}
            if field in decisions:
                d=decisions[field];selected=d['selected_value']
                if selected not in observed:raise RuntimeError('Selected field no longer matches original reports')
                values[field]=selected;provenance[field]=dict(decision=d,all_reports=rs)
            elif any('conflict'in r['review_status']for r in rs)or len(observed)>1:excluded[field]='Competing source reports require an explicit decision.'
            elif len(observed)==1:values[field]=next(iter(observed));provenance[field]=dict(decision='matching own reports; method and basis retained',all_reports=rs)
        return dict(values=values,provenance=provenance,excluded=excluded)

    def auxiliary_gcd(self,profile='3e'):
        rows=super().auxiliary_gcd(profile)
        for r in rows:
            if r['doi']not in NEW_DOIS:continue
            x=self.canonical_material_features_v13(r['doi'],r['sample_name'])
            r.update(material_features=x['values'],feature_evidence=x['provenance'],excluded_feature_reasons=x['excluded'])
            r['working_value_caveats']=[v['decision']['reason']for v in x['provenance'].values()if isinstance(v['decision'],dict)]
        return rows

    def auxiliary_feature_rows(self,profile='3e'):
        rows=super().auxiliary_feature_rows(profile)
        for r in rows:
            if r['doi']!='10.1039/d6ra04144b':continue
            stages=[s for record in self.synthesis(doi=r['doi'],sample=r['sample_name'])for s in record['stages']]
            pre=next((s for s in stages if s['stage']=='precarbonization'),{})
            r['precarbonization_temperature_C']=pre.get('temperature_C');r['precarbonization_duration_h']=pre.get('duration_h')
        return rows

    def template_residue_gcd_inputs(self):
        ids={r[0]for r in self.connection.execute("select observation_id from purpose_reviews_v13 where eligible=1 and purpose='reported_template_ZnS_residue_3e_GCD'")}
        result=[]
        for r in self.capacitances():
            if r['observation_id']not in ids:continue
            assert r['method']=='GCD'and r['unit']=='F/g'and r['system']=='3E'
            features=self.canonical_material_features_v13(r['doi'],r['sample_name'])
            result.append(dict(r,target_name='reported_template_ZnS_residue_3e_capacitance_F_g',material_features=features['values'],feature_evidence=features['provenance'],excluded_feature_reasons=features['excluded'],source_family_group=self.isolation_group(r['source_group']),synthesis=self.synthesis(doi=r['doi'],sample=r['sample_name']),purpose_input_ready=True,ordinary_biomass_carbon_profile=False,scientific_goal_complete=False))
        return result

    def template_residue_matrix(self):
        rows=self.template_residue_gcd_inputs();fields=['BET_surface_area_m2_g','total_pore_volume_cm3_g','micropore_volume_cm3_g','Raman_ID_IG','ICP_OES_Zn_wt_pct','author_S_wt_pct_method_unspecified']
        groups=[r['source_family_group']for r in rows];counts=collections.Counter(groups)
        X=[]
        for r in rows:
            process=next(s for item in r['synthesis']for s in item['stages']if s['stage']=='single_carbonization_template_activation');parts=process['raw_FR_ZnO_APS_mass_parts']
            X.append([r['material_features'].get(f)for f in fields]+[r['current_A_g'],r['concentration_mol_L'],r['conditions']['voltage_lower_V'],r['conditions']['voltage_upper_V'],process['temperature_C'],parts[2]/parts[0],parts[1]/parts[0]])
        return dict(target='reported_template_ZnS_residue_3e_capacitance_F_g',feature_names=fields+['reported_current_A_g','concentration_mol_L','voltage_lower_V','voltage_upper_V','carbonization_temperature_C','recipe_APS_to_FR_mass_ratio','recipe_ZnO_to_FR_mass_ratio'],X=X,missing_mask=[[v is None for v in r]for r in X],y=[r['value']for r in rows],groups=groups,sample_weight=[1/counts[g]for g in groups],observation_ids=[r['observation_id']for r in rows],model_fits=0,imputed=False,independent_source_validation_possible_alone=len(set(groups))>=2)

    def interface_reference_reports(self):
        """Reference reports remain ineligible for biomass training; origin unverified."""
        return [dict(r,reference_only=True,biomass_origin_confirmed=False,training_input_ready=False)for r in self.capacitances(doi='10.1039/d6ra08120g')]

    def wettability_series_v13(self):
        return [dict(r,record=json.loads(r['record_json']))for r in self.connection.execute('select *from wettability_series_v13 order by material_key,time_s')]

    def report_groups_v13(self):
        """Nominal report relationships, not counts of independent experiments."""
        result=[]
        eligible={v['observation_id']for v in self.auxiliary_gcd('3e')}
        for r in self.capacitances():
            if r['doi']not in NEW_DOIS:continue
            unit=r['table_key'].split('#',1)[1]
            if r['doi']=='10.1039/d5ra02129d':
                family='3E_Fig7'if unit in ['Fig7c_cap','body22_cap']else '2E_electrolyte_comparison'
            elif r['doi']=='10.1039/d6ra04144b':family='3E_GCD'
            elif r['doi']=='10.3390/polym16233421':family='3E_GCD_residue'
            else:family='3E_reference_GCD'
            # Unknown j is a report-comparison bucket, never proof of one physical run.
            group=':'.join(map(str,[r['source_group'],r['sample_name'],family,r['electrolyte'],r['current_A_g']]))
            result.append(dict(observation_id=r['observation_id'],doi=r['doi'],sample_name=r['sample_name'],value=r['value'],reported_current_A_g=r['current_A_g'],nominal_report_group=group,source_family_group=self.isolation_group(r['source_group']),basis='Same sample/method/source and nominal condition; repeated and competing reports retained separately. Unknown current does not prove physical identity.',independent_experiment_count=None,training_input_ready=r['observation_id']in eligible,reference_only=r['doi']=='10.1039/d6ra08120g'))
        return result

def open_literature_database(database=None,expected_sha256=None):return LiteratureDatabaseV13(database,expected_sha256)
