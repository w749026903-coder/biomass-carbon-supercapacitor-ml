"""Read-only four-source extraction with published-model artifacts separate from physical evidence."""
import json
from data.literature_v9 import LiteratureDatabaseV9
class LiteratureDatabaseV10(LiteratureDatabaseV9):
    def peer_model_review(self):return json.loads(self.connection.execute('select record_json from peer_model_reviews_v10').fetchone()[0])
    def peer_model_cells(self):return[dict(r,record=json.loads(r['record_json']))for r in self.connection.execute('select * from peer_model_cells_v10 order by record_id')]
    def batch10_sources(self):return[dict(r,record=json.loads(r['record_json']))for r in self.connection.execute('select * from source_reviews_v10 order by doi')]
    def batch10_audits(self):return[dict(r,record=json.loads(r['record_json']))for r in self.connection.execute('select * from numerical_audits_v10 order by audit_id')]
    def auxiliary_feature_rows(self,profile='3e'):
        rows=super().auxiliary_feature_rows(profile)
        for r in rows:
            if r['doi']!='10.1039/c7ra11475c':continue
            facts={f['field_name']:f['value']for f in self.facts(doi=r['doi'],sample=r['sample_name'])if f['value']is not None and 'conflict'not in f['review_status']}
            for field in['XPS_N_wt_pct','XPS_O_wt_pct']:r[field]=facts.get(field);r[field+'_is_missing']=r[field]is None
            stages=[s for x in self.synthesis(doi=r['doi'],sample=r['sample_name'])for s in x['stages']];oxid=next((s for s in stages if s['stage']=='air_oxidation_after_carbonization'),{})
            r['post_air_oxidation_temperature_C']=oxid.get('temperature_C');r['post_air_oxidation_duration_h']=oxid.get('duration_h');r['DAP_to_raw_cotton_mass_ratio']=None if r['sample_name']=='C800'else 1
        return rows
    def auxiliary_gcd(self,profile='3e'):
        rows=super().auxiliary_gcd(profile)
        for r in rows:
            if r['doi']=='10.1039/c7ra11475c':
                # Only350 is admitted here; its explicitconclusion statesN/Owt%, notatomic%.
                for e in ['N','O']:
                    r['material_features'].pop('XPS_'+e+'_at_pct',None)
        return rows
def open_literature_database(database=None,expected_sha256=None):return LiteratureDatabaseV10(database,expected_sha256)
