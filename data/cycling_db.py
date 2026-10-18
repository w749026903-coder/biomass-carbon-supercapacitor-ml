"""Stable project entry for the versioned read-only literature database."""
from pathlib import Path
import hashlib,importlib.util,json,sys
ROOT=Path(__file__).resolve().parents[1]
def open_database(verify_hash=True):
    pointer=json.loads((ROOT/'data/current_database.json').read_text(encoding='utf-8'))
    folder=(ROOT/pointer['version_directory']).resolve()
    if ROOT not in folder.parents:raise ValueError('Database must stay inside this project.')
    path=folder/pointer['database_file']
    if verify_hash:
        h=hashlib.sha256()
        with path.open('rb') as f:
            for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
        if h.hexdigest()!=pointer['sha256']:raise RuntimeError('Database fingerprint differs from the current release pointer.')
    name='_supercapacitor_local_data_'+hashlib.sha256(str(folder).encode()).hexdigest()[:12]
    if name not in sys.modules:
        spec=importlib.util.spec_from_file_location(name,folder/'ml_data.py');module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    return sys.modules[name].Database(path)
