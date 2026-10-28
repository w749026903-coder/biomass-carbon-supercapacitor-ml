"""Read-only training catalog with pinned, append-only SQLite extensions."""
from pathlib import Path
import hashlib,json,sqlite3
from data.training_ready import ReadyTrainingDatasets
from data.training_datasets import ROOT

class TrainingCatalog(ReadyTrainingDatasets):
    def __init__(self,database=None,expected_sha256=None):
        if database is None:
            p=json.loads((ROOT/'data/current_training_catalog.json').read_text('utf8'));database=ROOT/p['directory']/p['database_file'];expected_sha256=p['sha256']
        self.path=Path(database).resolve()
        def check(path,expected):
            if ROOT not in path.parents or not expected:raise ValueError('Pinned in-project catalog required')
            with path.open('rb')as f:
                if hashlib.file_digest(f,'sha256').hexdigest()!=expected:raise ValueError('Catalog fingerprint differs: '+str(path))
        check(self.path,expected_sha256)
        self.connection=sqlite3.connect(self.path.as_uri()+'?mode=ro',uri=True);self.connection.row_factory=sqlite3.Row
        meta={r['key']:json.loads(r['value_json'])for r in self.connection.execute('select *from metadata')}
        self.summary=meta['summary'];self.rules=json.loads((self.path.parent/'source_family_rules.json').read_text('utf8'))
        parents=meta.get('readonly_parent_chain',[])
        if len(parents)>self.connection.getlimit(sqlite3.SQLITE_LIMIT_ATTACHED):raise ValueError('Materialize a reviewed snapshot before exceeding the SQLite attachment limit')
        aliases=['main'];seen={self.path}
        for i,r in enumerate(parents):
            path=(ROOT/r['path']).resolve();check(path,r['sha256'])
            if path in seen:raise ValueError('Repeated/cyclic parent dependency')
            seen.add(path);alias='parent'+str(i);aliases.append(alias)
            self.connection.execute('attach database ? as '+alias,(path.as_uri()+'?mode=ro',))
        tables=meta.get('append_only_union_tables',[])
        for table in tables:
            if not table.replace('_','').isalnum():raise ValueError('Invalid table identifier')
            parts=[]
            for alias in aliases:
                if self.connection.execute('select 1 from '+alias+'.sqlite_master where type="table"and name=?',(table,)).fetchone():parts.append('select *from '+alias+'.'+table)
            self.connection.execute('create temp view '+table+' as '+' union all '.join(parts))
        self.connection.execute('pragma query_only=on')

    def rows(self,task,exclude_sources=()):
        if task not in self.tasks():raise ValueError('Unknown task; inspect tasks()')
        excluded={self.family(s)for s in exclude_sources};out=[]
        for rr, in self.connection.execute('select record_json from inputs where task=?order by row_id',(task,)):
            row=json.loads(rr);row['source_family']=self.family(row['source_family'])
            if row['source_family']not in excluded:out.append(row)
        return out

def open_training_datasets(database=None,expected_sha256=None):return TrainingCatalog(database,expected_sha256)
