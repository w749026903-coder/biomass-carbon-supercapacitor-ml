"""No model training: demonstrate source-backed data loading."""
from pathlib import Path
import json,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from data.cycling_db import open_database
with open_database() as db:
    review=db.fetch('review_3e')
    strict=db.fetch('strict_3e')
    print(json.dumps({'review_rows':len(review.rows),'strict_ready_rows':len(strict.rows),'training_authorized':False},ensure_ascii=False,indent=2))
    row=db.by_alias('TE','TE005')
    print(json.dumps({'TE005_concentration_mol_L':row['concentration_mol_L'],'evidence':[(v['locator'],v['status']) for v in db.evidence(row['endpoint_id'],'concentration_mol_L')]},ensure_ascii=False,indent=2))
