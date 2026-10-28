"""Mutable latest route; sealed release snapshots remain independently readable."""
import json
from data.training_datasets import ROOT
from data.training_store import TrainingStore


def open_training_datasets(database=None, expected_sha256=None):
    if database is None:
        p = json.loads((ROOT / 'data/current_training_latest.json').read_text('utf8'))
        database = ROOT / p['directory'] / p['database_file']
        expected_sha256 = p['sha256']
    return TrainingStore(database, expected_sha256)
