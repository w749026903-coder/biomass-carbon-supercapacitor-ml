"""Read-only, source-qualified access to literature pool v2, including SI tables."""
import json
from data.literature_db import LiteratureDatabase

class LiteratureDatabaseV2(LiteratureDatabase):
    def facts(self,doi=None,sample=None,field=None):
        return [dict(row) for row in self.connection.execute('''
        select f.*,m.doi,m.sample_name,m.material_stage,d.path as source_path,
               s.path as publication_source_path,t.xml_id,t.caption,l.locator,
               d.role as document_role
        from material_facts f join materials m using(material_key)
        join reviewed_sources s using(doi) join reviewed_tables t using(table_key)
        join table_source_links l using(table_key) join source_documents d using(document_key)
        where (? is null or m.doi=?) and (? is null or m.sample_name=?) and (? is null or f.field_name=?)
        order by m.doi,m.sample_name,f.field_name,t.table_key
        ''',(doi,doi,sample,sample,field,field))]

    def capacitances(self,doi=None,sample=None,method=None,electrolyte=None):
        rows=self.connection.execute('''select x.*,m.doi,m.sample_name,d.path as source_path,
        d.sha256 as source_sha256,l.locator from capacitance_observations x
        join materials m using(material_key) join table_source_links l using(table_key)
        join source_documents d using(document_key)
        where (? is null or m.doi=?) and (? is null or m.sample_name=?)
          and (? is null or x.method=?) and (? is null or x.electrolyte=?)
        order by m.doi,m.sample_name,x.method,x.electrolyte,x.table_key,x.row_ordinal,x.column_ordinal
        ''',(doi,doi,sample,sample,method,method,electrolyte,electrolyte))
        return [dict(row,conditions=json.loads(row['conditions_json'])) for row in rows]

    def scopes(self):
        return [dict(row) for row in self.connection.execute('select * from source_scope_decisions order by doi')]

    def staged_rows(self,table_key):
        return [dict(row,cells=json.loads(row['cells_json'])) for row in self.connection.execute('select * from transcribed_rows where table_key=? order by row_ordinal',(table_key,))]

def open_literature_database():return LiteratureDatabaseV2()
