"""Read-only early-cycling research input, separate from the legacy training API."""
from pathlib import Path
import hashlib,json,sqlite3
ROOT=Path(__file__).resolve().parents[1]
def load_windows(system='3E',fraction=.2,include_shape=False):
 """One endpoint per row; group source_family together in every split."""
 if system not in('2E','3E')or fraction not in(.1,.2):raise ValueError('Approved systems2E/3E and windows10%/20% only')
 config=json.loads((ROOT/'data/current_retention_research.json').read_text('utf8'));p=ROOT/config['database']
 if hashlib.sha256(p.read_bytes()).hexdigest()!=config['sha256']:raise ValueError('Research database SHA256 mismatch')
 view=f'training_B_{system}_early{int(100*fraction)}'
 with sqlite3.connect(p.as_uri()+'?mode=ro',uri=True)as connection:
  connection.row_factory=sqlite3.Row
  rows=[dict(r)for r in connection.execute(f'SELECT * FROM {view} ORDER BY source_family,curve_id')]
  if include_shape:
   from data.retention_shape import shape_summaries
   for r in rows:
    points=[json.loads(p[0])for p in connection.execute('SELECT raw_json FROM curve_points WHERE curve_id=? AND cycle_upper<=? ORDER BY marker_index',(r['curve_id'],fraction*r['target_cycle_count']))]
    r['early_points']=points;r['shape_features']=shape_summaries(points)
 for r in rows:
  r['point_indices']=json.loads(r.pop('point_indices_json'));r['static_features']=json.loads(r.pop('static_features_json'))
 return rows
