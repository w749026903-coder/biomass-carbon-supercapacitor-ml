"""Own-source series and explicit prior-work families; no fitted models."""
import json
from data.literature_v10 import LiteratureDatabaseV10
class LiteratureDatabaseV11(LiteratureDatabaseV10):
    def batch11_sources(self):return[dict(r,record=json.loads(r['record_json']))for r in self.connection.execute('select *from source_reviews_v11 order by doi')]
    def batch11_decisions(self):return[dict(r,record=json.loads(r['record_json']))for r in self.connection.execute('select *from decisions_v11 order by decision_id')]
    def source_relations(self):return[dict(r,record=json.loads(r['record_json']))for r in self.connection.execute('select *from source_relations_v11 order by doi,related_doi')]
    def isolation_group(self,doi_or_group):
        raw=str(doi_or_group).strip();doi=raw.lower().removeprefix('https://doi.org/').removeprefix('http://doi.org/').removeprefix('doi:')
        if not(doi.startswith('10.')and'/'in doi):return raw
        matches=[r['record']['isolation_group']for r in self.source_relations()if doi in[r['doi'],r['related_doi']]]
        if len(set(matches))>1:raise RuntimeError('Conflicting source families require review')
        return matches[0]if matches else'doi:'+doi
    def quarantine_source_groups(self,heldout):
        keys={self.isolation_group(x)for x in heldout};out=set(heldout)
        for r in self.source_relations():
            if r['record']['isolation_group']in keys:out.update(['doi:'+r['doi'],'doi:'+r['related_doi']])
        return sorted(out)
def open_literature_database(database=None,expected_sha256=None):return LiteratureDatabaseV11(database,expected_sha256)
