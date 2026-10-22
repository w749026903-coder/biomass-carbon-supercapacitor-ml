"""Add saved-fold support warnings; preserve all raw predictions and metrics."""
from pathlib import Path
from collections import Counter
import json,sqlite3,sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from models.v1_1.model import assess_prediction
from tools.train_model_v1 import read,write,sha
RUN=ROOT/'模型逐项优化_v1.1_20261022'


def review():
    records={r['endpoint_id']:r for r in read(RUN/'input_snapshot.json')['records']}
    conn=sqlite3.connect('file:'+(RUN/'evaluation.sqlite').as_posix()+'?mode=ro',uri=True)
    jobs=[json.loads(v) for v, in conn.execute('SELECT payload FROM jobs ORDER BY rowid')];conn.close()
    schemas={p['endpoint_id']:j['semantic_schema'] for j in jobs if j['stage']=='outer_selected' for p in j['predictions']}
    reviewed=[]
    for raw in read(RUN/'outer_predictions.json'):
        item=dict(raw);alerts=list(raw['input_warnings'])
        if raw['variant']=='v1_1_nested':
            record=records[raw['endpoint_id']]
            for schema in schemas[raw['endpoint_id']]:
                value=record.get(schema['field'])
                if value is None:alerts.append('semantic_missing:'+schema['field'])
                elif value not in schema['vocabulary']:alerts.append('semantic_rare_or_unseen:'+schema['field'])
        item.update(input_warnings=alerts,assessment=assess_prediction(item['predicted_pct'],alerts))
        reviewed.append(item)
    write(RUN/'reviewed_predictions.json',reviewed)
    counts=Counter(j['candidate'] for j in jobs if j['stage']=='outer_selected')
    summary={'raw_predictions_sha256':sha(RUN/'outer_predictions.json'),
        'reviewed_predictions_sha256':sha(RUN/'reviewed_predictions.json'),
        'prediction_values_changed':0,'metrics_changed':False,'estimator_fits_added':0,
        'outer_selected_configurations':dict(counts),
        'v1_1_predicted_above100':sum(p['predicted_pct']>100 for p in reviewed if p['variant']=='v1_1_nested'),
        'v1_1_negative_predictions':sum(p['predicted_pct']<0 for p in reviewed if p['variant']=='v1_1_nested'),
        'qualification':'Support alerts derived only from each saved outer training schema; no new fitting or score changes.'}
    write(RUN/'output_review.json',summary)
    print(json.dumps(summary,ensure_ascii=False))


if __name__=='__main__':review()
