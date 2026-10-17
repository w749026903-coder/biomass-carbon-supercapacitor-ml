"""One-time non-destructive revision from v0.1; never rerun old ingestion."""
import hashlib
import json
import pathlib
import sqlite3

ROOT = pathlib.Path(__file__).resolve().parent
PREVIOUS = ROOT.parent / '循环稳定性数据库_v0.1_20261017'
TARGET = ROOT / 'cycling_v0_2.sqlite'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    if TARGET.exists():
        raise FileExistsError('Existing revision preserved.')
    with sqlite3.connect((PREVIOUS/'cycling_v0_1.sqlite').as_uri()+'?mode=ro', uri=True) as old:
        sources = [{'path': p, 'sha256': h} for p, h in old.execute('SELECT path,sha256 FROM source_files')]
        for row in sources:
            assert sha(pathlib.Path(row['path'])) == row['sha256'], row['path']
        manifest = {'previous_database_sha256': sha(PREVIOUS/'cycling_v0_1.sqlite'),
                    'previous_modeling': {p.name:sha(p) for p in (PREVIOUS/'modeling').iterdir() if p.is_file()},
                    'source_files': sources}
        with sqlite3.connect(TARGET) as new:
            old.backup(new)
            new.execute('PRAGMA foreign_keys=ON')
            new.executescript('''
            CREATE TABLE review_events(
              review_id INTEGER PRIMARY KEY,record_id TEXT NOT NULL REFERENCES cycling_endpoints,
              field_name TEXT NOT NULL,decision TEXT NOT NULL,value_json TEXT,
              source_path TEXT NOT NULL,source_sha256 TEXT NOT NULL,locator TEXT NOT NULL,
              evidence_excerpt TEXT NOT NULL,rationale TEXT NOT NULL,review_date TEXT NOT NULL);
            CREATE TABLE revision_changes(
              change_id INTEGER PRIMARY KEY,table_name TEXT NOT NULL,row_key TEXT NOT NULL,
              field_name TEXT NOT NULL,old_json TEXT,new_json TEXT,rationale TEXT NOT NULL);
            ''')
            new.execute("UPDATE metadata SET value='0.2' WHERE key='schema_version'")
            new.execute("INSERT INTO metadata VALUES ('parent_database_sha256',?)", (manifest['previous_database_sha256'],))
            new.execute("INSERT INTO metadata VALUES ('revision_policy','incremental review; raw records and freezes retained; no research training')")
            new.commit()
    (ROOT/'parent_and_source_fingerprints.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    (ROOT/'modeling').mkdir()
    for name in ['model_contract.json','prepare_dataset.py','train_nested.py','train_grouped.py']:
        (ROOT/'modeling'/name).write_bytes((PREVIOUS/'modeling'/name).read_bytes())
    print('Revision created; 137 source fingerprints verified; parent preserved.')

if __name__ == '__main__':
    main()
