"""Research entry: only admitted records, explicit invocation required."""
import hashlib
import json
from prepare_dataset import ROOT, CONTRACT, database_path, load_ready
from benchmark_engine import run_benchmark, source_disjoint

def train(feature_set='plus_BET', run_name=None):
    rows = load_ready()
    if not rows:
        raise ValueError('No admitted records. Candidate exports cannot bypass admission.')
    if not run_name or '/' in run_name or chr(92) in run_name or run_name in ['.', '..']:
        raise ValueError('Supply a new simple --run-name to preserve prior runs')
    output = ROOT/'modeling/research_runs'/run_name
    results = run_benchmark(rows, output, feature_set)
    (output/'database_fingerprint.json').write_text(json.dumps({'database_sha256':hashlib.sha256(database_path().read_bytes()).hexdigest()},indent=2),encoding='utf-8')
    return results
