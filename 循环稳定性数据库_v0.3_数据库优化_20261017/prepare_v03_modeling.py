"""Copy only reusable model source/config, never fit or clone environments."""
from pathlib import Path
import shutil,json
ROOT=Path(__file__).resolve().parent
BASE=ROOT.parent/'循环稳定性数据库_v0.2_20261017/modeling'
for p in BASE.iterdir():
 if p.is_file() and p.suffix in ['.py','.json','.txt'] and p.name not in ['preflight_result.json']:
  out=ROOT/'modeling'/p.name
  if out.exists():raise RuntimeError('Do not overwrite prepared sources.')
  shutil.copyfile(p,out)
p=ROOT/'modeling/model_contract.json'
c=json.loads(p.read_text(encoding='utf-8'));c['database_file']='cycling_v0_3.sqlite'
p.write_text(json.dumps(c,ensure_ascii=False,indent=2),encoding='utf-8')
p=ROOT/'modeling/prepare_dataset.py';text=p.read_text(encoding='utf-8')
old='    return validate_rows(rows)\n'
assert text.count(old)==1
new='''        # v0.3 endpoint links complement paper/material/test grouping checks.
        by_id = {r['record_id']:r for r in rows}
        for link in c.execute('SELECT * FROM validation_links'):
            a, b = by_id.get(link['record_a']), by_id.get(link['record_b'])
            if a and b and a['study_group'] != b['study_group']:
                raise ValueError('Linked endpoints must share a source validation group')
            if a and link['related_doi']:
                related = c.execute('SELECT study_group FROM papers WHERE lower(trim(doi))=lower(trim(?))',(link['related_doi'],)).fetchone()
                if related and related[0] != a['study_group']:
                    raise ValueError('Predecessor overlap must be resolved or grouped before fitting')
    return validate_rows(rows)
'''
p.write_text(text.replace(old,new),encoding='utf-8')
print('Prepared model sources; config changed only for database filename. No training.')
