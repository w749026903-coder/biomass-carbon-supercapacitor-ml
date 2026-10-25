"""Read-only API for the reviewed full-literature evidence layer."""
from pathlib import Path
import hashlib,json,sqlite3

ROOT=Path(__file__).resolve().parents[1]


class LiteratureDatabase:
    def __init__(self):
        pointer=json.loads((ROOT/'data/current_literature.json').read_text('utf8'))
        self.path=(ROOT/pointer['directory']/pointer['database_file']).resolve()
        if ROOT not in self.path.parents:raise ValueError('Literature database must stay in project.')
        with self.path.open('rb') as stream:
            if hashlib.file_digest(stream,'sha256').hexdigest()!=pointer['sha256']:raise RuntimeError('Literature pool fingerprint differs.')
        self.connection=sqlite3.connect(self.path.as_uri()+'?mode=ro',uri=True)
        self.connection.row_factory=sqlite3.Row
        self.connection.execute('pragma query_only=on')

    def __enter__(self):return self
    def __exit__(self,*_):self.close()
    def close(self):self.connection.close()

    def materials(self,doi=None,sample=None):
        return [dict(r) for r in self.connection.execute('select * from materials where (? is null or doi=?) and (? is null or sample_name=?) order by doi,sample_name',(doi,doi,sample,sample))]

    def facts(self,doi=None,sample=None,field=None):
        return [dict(r) for r in self.connection.execute('''select f.*,m.doi,m.sample_name,m.material_stage,s.path as source_path,t.xml_id,t.caption
        from material_facts f join materials m using(material_key) join reviewed_sources s using(doi) join reviewed_tables t using(table_key)
        where (? is null or m.doi=?) and (? is null or m.sample_name=?) and (? is null or f.field_name=?)
        order by m.doi,m.sample_name,f.field_name''',(doi,doi,sample,sample,field,field))]

    def tests(self,method=None,system=None):
        rows=[]
        for item in self.connection.execute('select * from test_candidates order by candidate_id'):
            row=dict(item);row['record']=json.loads(row.pop('record_json'))
            if method is not None and row['record'].get('method')!=method:continue
            if system is not None and row['record'].get('system')!=system:continue
            rows.append(row)
        return rows

    def issues(self,doi=None):
        return [dict(r,issue=json.loads(r['issue_json'])) for r in self.connection.execute('select * from scientific_issues where (? is null or doi=?) order by issue_id',(doi,doi))]

    def queue(self,state='automatic_candidate_unreviewed',limit=20):
        return [dict(r) for r in self.connection.execute('select * from raw_table_queue where review_state=? order by previous_role,table_id limit ?',(state,max(0,int(limit))))]


def open_literature_database():return LiteratureDatabase()
