"""Latest read-only inputs with explicit, auditable derived-row replacements.

Original facts are append-only. Updated input/catalog rows require recorded
before/after hashes; parent versions remain unchanged and independently usable.
"""
from pathlib import Path
import hashlib,json,sqlite3
from data.training_catalog import TrainingCatalog
from data.training_datasets import ROOT

class TrainingStore(TrainingCatalog):
    def __init__(self,database=None,expected_sha256=None):
        if database is None:
            p=json.loads((ROOT/'data/current_training_store.json').read_text('utf8'));database=ROOT/p['directory']/p['database_file'];expected_sha256=p['sha256']
        self.path=Path(database).resolve()
        def check(path,h):
            if ROOT not in path.parents or not h:raise ValueError('Pinned in-project release required')
            with path.open('rb')as f:
                if hashlib.file_digest(f,'sha256').hexdigest()!=h:raise ValueError('Release fingerprint differs')
        check(self.path,expected_sha256)
        c=sqlite3.connect(self.path.as_uri()+'?mode=ro',uri=True);c.row_factory=sqlite3.Row;self.connection=c
        meta={r['key']:json.loads(r['value_json'])for r in c.execute('select *from metadata')};self.summary=meta['summary'];self.rules=json.loads((self.path.parent/'source_family_rules.json').read_text('utf8'))
        aliases=['main'];seen={self.path};parents=meta['readonly_parent_chain']
        if len(parents)>c.getlimit(sqlite3.SQLITE_LIMIT_ATTACHED):raise ValueError('Reviewed materialization needed before SQLite attachment limit')
        for i,r in enumerate(parents):
            path=(ROOT/r['path']).resolve();check(path,r['sha256'])
            if path in seen:raise ValueError('Repeated parent dependency')
            seen.add(path);alias='parent'+str(i);aliases.append(alias);c.execute('attach database ? as '+alias,(path.as_uri()+'?mode=ro',))
        overrides=meta.get('override_primary_keys',{})
        allowed={'inputs','usage_ledger','materials','cycle_records','cycle_material_links','selected_features'}
        if not set(overrides)<=allowed:raise ValueError('Original facts/targets cannot be silently replaced')
        receipts=[]
        for alias in aliases:
            if c.execute('select 1 from '+alias+'.sqlite_master where name="overlay_changes"').fetchone():
                receipts.extend(json.loads(r[0])for r in c.execute('select record_json from '+alias+'.overlay_changes'))
        for table in meta['append_only_union_tables']:
            if not table.replace('_','').isalnum():raise ValueError('Invalid table identifier')
            present=[a for a in aliases if c.execute('select 1 from '+a+'.sqlite_master where type="table"and name=?',(table,)).fetchone()]
            if table not in overrides:
                sql=' union all '.join('select *from '+a+'.'+table for a in present)
            else:
                keys=overrides[table]
                if any(not k.replace('_','').isalnum()for k in keys):raise ValueError('Invalid override key')
                columns=[r['name']for r in c.execute('pragma main.table_info('+table+')')];keysql=','.join(keys)
                union=' union all '.join('select *,'+str(i)+' as __layer from '+a+'.'+table for i,a in enumerate(present))
                for row in c.execute('select '+keysql+',count(*)as n from ('+union+')group by '+keysql+' having n>1'):
                    key=[row[k]for k in keys];versions=[]
                    for alias in present:
                        r=c.execute('select record_json from '+alias+'.'+table+' where '+' and '.join(k+'=?'for k in keys),key).fetchone()
                        if r:versions.append(hashlib.sha256(r[0].encode()).hexdigest())
                    edges={(r['after_sha256'],r['before_sha256'])for r in receipts if r['table']==table and r['key']==key}
                    if any((a,b)not in edges for a,b in zip(versions,versions[1:])):raise ValueError('Unreceipted duplicate or replacement: '+table+str(key))
                sql='select '+','.join(columns)+' from(select *,row_number()over(partition by '+keysql+' order by __layer)as __rank from('+union+'))where __rank=1'
            c.execute('create temp view '+table+' as '+sql)
        c.execute('pragma query_only=on')

def open_training_datasets(database=None,expected_sha256=None):return TrainingStore(database,expected_sha256)
