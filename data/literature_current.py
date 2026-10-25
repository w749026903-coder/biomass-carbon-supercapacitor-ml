"""Stable read-only entry; dispatch to the API explicitly named by the current pointer."""
from pathlib import Path
import importlib,json,re
ROOT=Path(__file__).resolve().parents[1]
def open_literature_database():
    pointer=json.loads((ROOT/'data/current_literature.json').read_text('utf8'))
    name=pointer['api_module']
    if not re.fullmatch(r'data\.literature_v\d+',name):raise ValueError('Unsupported versioned literature API.')
    return importlib.import_module(name).open_literature_database()
