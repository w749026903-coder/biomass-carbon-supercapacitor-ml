"""Enumerate training-only supervision candidates from currently approved retention traces."""
import bisect
import collections
import hashlib
import json
import math
from pathlib import Path
import sqlite3

ROOT = Path(__file__).resolve().parents[1]
ROUND = ROOT/'保持率达标研究_v3_主线与近优组合_20261030/第十三轮_MK9纠错复验_20261104'
MK9 = 'v25:Mango_MK9_2E_C100000'


def read(path):
    return json.loads(path.read_text('utf8'))


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def pick_by_position(candidates, limit=16):
    if len(candidates) <= limit:
        return candidates
    x = [math.log(point['cycle_coordinate']) for point,_ in candidates]
    grid = [x[0]+i*(x[-1]-x[0])/(limit-1) for i in range(limit)]
    indexes = sorted({min(range(len(x)),key=lambda j:(abs(x[j]-v),j)) for v in grid})
    return [candidates[i] for i in indexes]


def build():
    pointer = read(ROOT/'data/current_retention_research.json')
    db_path = ROOT/pointer['database']
    assert pointer['version']=='retention_research_v3h_20261031' and sha(db_path)==pointer['sha256']
    windows = collections.defaultdict(list)
    excluded_boundary_markers = 0
    checked = 0
    with sqlite3.connect(db_path.as_uri()+'?mode=ro',uri=True) as db:
        assert db.execute('PRAGMA integrity_check').fetchone()==('ok',) and not db.execute('PRAGMA foreign_key_check').fetchall()
        query = 'SELECT curve_id,endpoint_id,source_family,system,target_cycle_count,target_retention_pct,raw_json FROM curves WHERE approved=1 ORDER BY source_family,curve_id'
        curves = db.execute(query).fetchall()
        assert len(curves)==len({r[1] for r in curves})==57
        assert [(r[0],r[5]) for r in curves if r[1]==MK9]==[('metric_v3h:'+MK9,65.)]
        for curve_id,endpoint,source,system,horizon,author_target,raw in curves:
            raw_points = [json.loads(r[0]) for r in db.execute('SELECT raw_json FROM curve_points WHERE curve_id=? ORDER BY marker_index',(curve_id,))]
            points = [p for p in raw_points if p['cycle_upper']<horizon]
            excluded_boundary_markers += len(raw_points)-len(points)
            upper = [p['cycle_upper'] for p in points]
            assert all(b>a for a,b in zip(upper,upper[1:]))
            assert len(points)==len({p['cycle_coordinate'] for p in points})
            reference = json.loads(raw).get('first_plotted_reference')
            for fraction in (.2,.1):
                candidates = []
                nominal_count = 0
                for p in points:
                    if p['cycle_coordinate']<=0:
                        continue
                    nominal_count += bisect.bisect_right(upper,fraction*p['cycle_coordinate'])>=3
                    available = bisect.bisect_right(upper,fraction*p['cycle_lower'])
                    if available>=3:
                        candidates.append((p,points[:available]))
                selected = []
                for p,early in pick_by_position(candidates):
                    assert early[-1]['cycle_upper']<=fraction*p['cycle_lower']<p['cycle_lower']
                    assert p['marker_index'] not in {q['marker_index'] for q in early}
                    assert 0<p['reading_interval_pp'][0]<=p['retention_pct']<=p['reading_interval_pp'][1]
                    selected.append(dict(marker_index=p['marker_index'],cycle_coordinate=p['cycle_coordinate'],
                                         cycle_interval=[p['cycle_lower'],p['cycle_upper']],retention_reading_pct=p['retention_pct'],
                                         reading_interval_pp=p['reading_interval_pp'],early_marker_indices=[q['marker_index'] for q in early]))
                    checked += 1
                if selected:
                    windows[(system,fraction)].append(dict(curve_id=curve_id,endpoint_id=endpoint,source_family=source,
                        author_endpoint_cycle=horizon,author_endpoint_retention_pct=author_target,shared_reference=reference,
                        strict_eligible_positions=len(candidates),nominal_eligible_positions=nominal_count,selected=selected))
    inventory = []
    for (system,fraction), rows in windows.items():
        inventory.append(dict(system=system,fraction=fraction,curves=len(rows),sources=len({r['source_family'] for r in rows}),
                              strict_eligible_positions=sum(r['strict_eligible_positions'] for r in rows),
                              capped_selected_positions=sum(len(r['selected']) for r in rows),detail=rows))
    return dict(status='inventory_only',database_sha256=pointer['sha256'],active_curves_checked=57,selected_positions_checked=checked,
                author_boundary_markers_excluded=excluded_boundary_markers,
                new_source_families=0,new_author_endpoints=0,new_model_fits=0,old_misclassified_CE_excluded=True,
                method='Current SQL approved curves. Actual digitized positions; early point upper bound at or before fraction times the target cycle lower bound. At most 16 positions per curve selected by log cycle position. Author endpoints are separate.',
                future_contract='Auxiliary training supervision only. Exclude the entire held source in every split. Inner selection and outer acceptance use author endpoints only. Keep each reading interval and shared reference uncertainty. Normalize weights within source and curve before trying any auxiliary loss.',
                inventory=sorted(inventory,key=lambda r:(r['system'],-r['fraction'])))


if __name__=='__main__':
    result = build()
    out = ROUND/'curve_supervision_inventory_v3h.json'
    with out.open('x',encoding='utf8') as stream:
        json.dump(result,stream,ensure_ascii=False,indent=2,allow_nan=False)
        stream.write('\n')
    print(json.dumps([{k:v for k,v in row.items() if k!='detail'} for row in result['inventory']],ensure_ascii=False))
