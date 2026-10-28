"""Read-only ready-to-call datasets with fact receipts and whole-family isolation."""
from pathlib import Path
import collections,hashlib,json,sqlite3
ROOT=Path(__file__).resolve().parents[1]

class TrainingDatasets:
    def __init__(self,database=None,expected_sha256=None):
        if database is None:
            p=json.loads((ROOT/'data/current_training_datasets.json').read_text('utf8'))
            database=ROOT/p['directory']/p['database_file'];expected_sha256=p['sha256']
        self.path=Path(database).resolve()
        if ROOT not in self.path.parents or expected_sha256 is None:raise ValueError('A pinned project dataset is required')
        with self.path.open('rb')as f:
            if hashlib.file_digest(f,'sha256').hexdigest()!=expected_sha256:raise ValueError('Dataset fingerprint differs')
        self.connection=sqlite3.connect(self.path.as_uri()+'?mode=ro',uri=True);self.connection.row_factory=sqlite3.Row
        self.connection.execute('pragma query_only=on')
        self.summary=json.loads(self.connection.execute("select value_json from metadata where key='summary'").fetchone()[0])
        self.rules=json.loads((self.path.parent/'source_family_rules.json').read_text('utf8'))

    def close(self):self.connection.close()
    def __enter__(self):return self
    def __exit__(self,*args):self.close()
    def family(self,value):
        if value.startswith('family:'):return value
        doi=value.removeprefix('doi:').lower()
        for r in self.rules:
            if doi in [r['doi'].lower(),r['related_doi'].lower()]:return r['isolation_group']
        return 'doi:'+doi
    def tasks(self):return self.summary['task_counts']
    def rows(self,task,exclude_sources=()):
        if task not in self.tasks():raise ValueError('Unknown task; inspect tasks()')
        excluded={self.family(x) for x in exclude_sources}
        rows=[json.loads(r[0])for r in self.connection.execute('select record_json from inputs where task=?order by row_id',(task,))]
        return [r for r in rows if r['source_family']not in excluded]
    def matrix(self,task,exclude_sources=()):
        rows=self.rows(task,exclude_sources);fields=sorted({f for r in rows for f in r['features']});X=[[r['features'].get(f)for f in fields]for r in rows]
        groups=[r['source_family']for r in rows];counts=collections.Counter(groups)
        return dict(task=task,row_ids=[r['row_id']for r in rows],feature_names=fields,X=X,y=[r['target']for r in rows],
                    missing_mask=[[x is None for x in row]for row in X],groups=groups,sample_weight=[1/counts[g]for g in groups],
                    source_families=len(counts),source_holdout_validation_possible=len(counts)>=2,imputed=False,model_fits=0,
                    conditions=[r['conditions']for r in rows],target_names=sorted({r['target_name']for r in rows}))
    def training_bundle(self,exclude_sources):
        """Call once per held-out family to quarantine ALL supervised tasks."""
        return {task:self.matrix(task,exclude_sources)for task in self.tasks()}
    def fact_usage(self,fact_id=None):
        rs=self.connection.execute('select record_json from usage_ledger'+(' where fact_id=?'if fact_id is not None else' order by fact_id'),(fact_id,)if fact_id is not None else())
        return [json.loads(r[0])for r in rs]
    def material_catalog(self):return [json.loads(r[0])for r in self.connection.execute('select record_json from materials order by material_key')]
    def canonical_cycles(self):return [json.loads(r[0])for r in self.connection.execute('select record_json from cycle_records order by endpoint_id')]
    def review_queue(self):return [json.loads(r[0])for r in self.connection.execute('select record_json from review_queue order by queue_id')]

def open_training_datasets(database=None,expected_sha256=None):return TrainingDatasets(database,expected_sha256)
