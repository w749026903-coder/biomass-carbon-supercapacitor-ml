"""Latest reviewed input release, selected by an unsealed routing pointer.

Older v1/v2 entrypoints remain pinned for reproducibility. Each release stores
its pointer snapshot; updating the latest route never rewrites an old manifest.
"""
import json
from data.training_current import CurrentTrainingDatasets,ROOT
from data.training_datasets import TrainingDatasets

class ReadyTrainingDatasets(CurrentTrainingDatasets):
    def __init__(self,database=None,expected_sha256=None):
        if database is None:
            p=json.loads((ROOT/'data/current_training_ready.json').read_text('utf8'))
            database=ROOT/p['directory']/p['database_file'];expected_sha256=p['sha256']
        TrainingDatasets.__init__(self,database,expected_sha256)

    def extraction_coverage(self):
        return [json.loads(r[0])for r in self.connection.execute('select record_json from extraction_coverage_v3 order by doi,unit_id')]

    def capacity_reports(self):
        return [json.loads(r[0])for r in self.connection.execute('select record_json from capacity_reports_v3 order by observation_id')]

def open_training_datasets(database=None,expected_sha256=None):return ReadyTrainingDatasets(database,expected_sha256)
