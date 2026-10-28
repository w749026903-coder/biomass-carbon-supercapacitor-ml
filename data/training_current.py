"""Current reviewed training inputs; v1 remains independently reproducible."""
from pathlib import Path
import collections,json
from data.training_datasets import TrainingDatasets
ROOT=Path(__file__).resolve().parents[1]

class CurrentTrainingDatasets(TrainingDatasets):
    def __init__(self):
        p=json.loads((ROOT/'data/current_training_inputs.json').read_text('utf8'))
        super().__init__(ROOT/p['directory']/p['database_file'],p['sha256'])

    def feature_coverage(self,task,exclude_sources=()):
        rows=self.rows(task,exclude_sources);out=[]
        for field in sorted({f for r in rows for f in r['features']}):
            available=[r for r in rows if r['features'].get(field) is not None]
            counts=collections.Counter(r['source_family'] for r in available)
            out.append(dict(field=field,nonmissing_rows=len(available),total_rows=len(rows),
                            nonmissing_fraction=len(available)/len(rows) if rows else 0,
                            source_families=len(counts),maximum_source_row_share=max(counts.values(),default=0)/len(available) if available else 0))
        return out

    def source_split(self,task,heldout_sources,minimum_sources=3,minimum_fraction=0.2):
        """Feature support is determined on training sources ONLY, without y."""
        excluded={self.family(s) for s in heldout_sources}
        if not excluded:raise ValueError('Explicit held-out source families required')
        if minimum_sources<1 or not 0<=minimum_fraction<=1:raise ValueError('Invalid support thresholds')
        allrows=self.rows(task);train=[r for r in allrows if r['source_family'] not in excluded]
        test=[r for r in allrows if r['source_family'] in excluded]
        if not train or not test:raise ValueError('Both source partitions must contain rows')
        coverage=self.feature_coverage(task,excluded)
        fields=[r['field'] for r in coverage if r['source_families']>=minimum_sources and r['nonmissing_fraction']>=minimum_fraction]
        def pack(rows):
            groups=[r['source_family'] for r in rows];count=collections.Counter(groups)
            return dict(row_ids=[r['row_id'] for r in rows],X=[[r['features'].get(f) for f in fields] for r in rows],
                        y=[r['target'] for r in rows],groups=groups,sample_weight=[1/count[g] for g in groups])
        return dict(task=task,feature_names=fields,training_coverage=coverage,train=pack(train),test=pack(test),
                    selection_basis='training_sources_only_no_outcomes',minimum_sources=minimum_sources,
                    minimum_fraction=minimum_fraction,imputed=False,model_fits=0,
                    warning='Exploratory support filter; thresholds are not an established performance guarantee.')

    def measurement_metadata(self,material_key=None):
        sql='select record_json from measurement_metadata';args=()
        if material_key is not None:sql+=' where material_key=?';args=(material_key,)
        return [json.loads(r[0]) for r in self.connection.execute(sql,args)]

    def source_split_bundle(self,primary_task,heldout_sources,minimum_sources=3,minimum_fraction=0.2):
        """Quarantine the primary held-out families from every auxiliary task."""
        heldout_sources=tuple(heldout_sources)
        primary=self.source_split(primary_task,heldout_sources,minimum_sources,minimum_fraction)
        auxiliary={task:self.matrix(task,heldout_sources) for task in self.tasks() if task!=primary_task}
        return dict(primary=primary,auxiliary_training=auxiliary,model_fits=0)

def open_training_datasets():return CurrentTrainingDatasets()
