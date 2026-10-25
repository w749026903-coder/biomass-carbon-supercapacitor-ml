"""Read-only literature evidence, with four explicitly separate capacitance tasks."""
import json
from data.literature_v3 import LiteratureDatabaseV3

PROFILES = {
    '3e': ('reported_aqueous_3e_GCD_capacitance', 'reported_3e_capacitance_F_g'),
    '2e_device': ('reported_aqueous_2e_GCD_device_capacitance', 'reported_2e_device_capacitance_F_g'),
    'native_mineral_3e': ('reported_native_mineral_3e_GCD_capacitance', 'reported_native_mineral_3e_capacitance_F_g'),
    '2e_author_factor2': ('reported_2e_author_factor2_GCD_capacitance', 'reported_2e_author_factor2_capacitance_F_g'),
}


class LiteratureDatabaseV4(LiteratureDatabaseV3):
    def curve_readings(self):
        return [dict(r,record=json.loads(r['record_json'])) for r in self.connection.execute('''
          select r.*,d.path as source_path,d.sha256 as source_sha256 from curve_readings_v4 r
          join source_documents d using(document_key) order by reading_id''')]

    def auxiliary_feature_rows(self, profile='3e'):
        rows = super().auxiliary_feature_rows(profile)
        evidence = {r['observation_id']:r for r in self.auxiliary_gcd(profile)}
        extras = ['EDX_C_wt_pct','EDX_C_at_pct','EDX_O_wt_pct','EDX_O_at_pct',
                  'author_t_pore_area_m2_g','author_t_pore_volume_cm3_g',
                  'NLDFT_pore_peak_1_nm','NLDFT_pore_peak_2_nm','NLDFT_pore_peak_3_nm']
        for row in rows:
            item = evidence[row['observation_id']]
            for field in extras:
                row[field] = item['material_features'].get(field)
                row[field+'_is_missing'] = row[field] is None
            row['native_CaP_reported_present'] = item['conditions'].get('native_CaP_inclusions')
            row['Raman_ID_IG_value_relation'] = 'approx' if any('approximate' in f['review_status'] for f in self.facts(doi=row['doi'],sample=row['sample_name'],field='Raman_ID_IG')) else ('reported' if row['Raman_ID_IG'] is not None else None)
            stages = [s for record in item['synthesis'] for s in record['stages']]
            hydro = next((s for s in stages if s['stage']=='hydrothermal_carbonization'),{})
            row['hydrothermal_carbonization_temperature_C'] = hydro.get('temperature_C')
            row['hydrothermal_carbonization_duration_h'] = hydro.get('duration_h')
            row['reported_BET_fit_pressure_range_json'] = json.dumps(item['conditions'].get('reported_BET_fit_pressure_range'))
        return rows

    def auxiliary_gcd(self, profile='3e'):
        if profile not in PROFILES:
            raise ValueError('Unknown separate target profile: ' + profile)
        purpose, target = PROFILES[profile]
        rows = self.connection.execute('''select x.*,d.path as source_path,d.sha256 as source_sha256,l.locator
          from auxiliary_reported_GCD_v3 x join table_source_links l using(table_key)
          join source_documents d using(document_key) where x.purpose=?
          order by x.source_group,x.sample_name,x.current_A_g''', (purpose,))
        result = []
        for r in rows:
            item = dict(r)
            item['conditions'] = json.loads(item['conditions_json'])
            item['raw_candidate_training_eligible'] = item.pop('training_eligible')
            item.update(auxiliary_input_ready=True, target_name=target, capacitance_F_g=item['value'], scientific_goal_complete=False)
            grouped = {}
            for f in self.facts(doi=item['doi'], sample=item['sample_name']):
                grouped.setdefault(f['field_name'], []).append(f)
            features, provenance, excluded = {}, {}, {}
            coupled = set()
            if item['doi'] == '10.1021/acsomega.5c06396' and item['sample_name'] == 'C-MNS':
                coupled = {'mesopore_volume_cm3_g', 'mesopore_volume_fraction_pct', 'micro_to_meso_pore_volume_ratio'}
            for field, evidence in grouped.items():
                usable = [f for f in evidence if f['value'] is not None and 'conflict' not in f['review_status']]
                values = {f['value'] for f in usable}
                if field in coupled:
                    excluded[field] = 'Coupled to unresolved C-MNS mesopore-volume conflict.'
                elif field == 'micropore_volume_cm3_g' and item['doi'] == '10.1002/smsc.202500174' and item['sample_name'] == 'WPC600-4':
                    # Table1 rounds 0.4797 to 0.48; SI supplies the additional precision.
                    exact = [f for f in usable if f['xml_id'] == 'SI_TableS1']
                    if not exact or values != {.48, .4797}:
                        raise RuntimeError('Hardwood precision decision no longer matches evidence.')
                    features[field] = .4797
                    provenance[field] = {'selected': exact, 'all_reports': evidence, 'decision': 'SI precision; main table0.48 is matching rounding, not a second experiment.'}
                elif len(values) == 1:
                    features[field] = next(iter(values))
                    provenance[field] = {'all_reports': evidence, 'decision': 'matching reported values'}
                elif len(values) > 1:
                    excluded[field] = 'Competing values require an explicit decision; no last-write selection.'
            item.update(material_features=features, feature_evidence=provenance, excluded_feature_reasons=excluded)
            item['derived_features'] = {'Raman_ID_IG_from_reported_IG_ID': 1/features['Raman_IG_ID']} if 'Raman_IG_ID' in features and 'Raman_ID_IG' not in features else {}
            item['synthesis'] = self.synthesis(doi=item['doi'], sample=item['sample_name'])
            item['feature_boundary'] = 'Pretest material/process and protocol only; same-test capacitance, CE, retention, energy, adsorption and EIS outcomes excluded. All labels from a DOI stay in one source group.'
            result.append(item)
        return result


def open_literature_database(database=None, expected_sha256=None):
    return LiteratureDatabaseV4(database, expected_sha256)
