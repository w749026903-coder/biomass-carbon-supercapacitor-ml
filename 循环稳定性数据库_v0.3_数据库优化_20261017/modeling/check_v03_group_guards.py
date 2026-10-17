"""Behavioral group-leakage checks; no estimators, no research records fitted."""
import sqlite3,json
from pathlib import Path
from prepare_dataset import validate_link_groups
def main():
 c=sqlite3.connect(':memory:');c.row_factory=sqlite3.Row
 c.executescript('CREATE TABLE papers(doi TEXT,study_group TEXT); CREATE TABLE validation_links(record_a TEXT,record_b TEXT,related_doi TEXT,status TEXT);')
 checks={}
 def rejects(name,rs):
  try:validate_link_groups(c,rs)
  except ValueError:checks[name]=True
  else:checks[name]=False
 c.execute("INSERT INTO validation_links VALUES ('A','B',NULL,'documented')")
 rejects('linked_curve_cross_group_rejected',[{'record_id':'A','study_group':'one'},{'record_id':'B','study_group':'two'}])
 validate_link_groups(c,[{'record_id':'A','study_group':'one'},{'record_id':'B','study_group':'one'}]);checks['linked_curve_same_group_allowed']=True
 c.execute('DELETE FROM validation_links')
 c.execute("INSERT INTO papers VALUES ('https://doi.org/10.example/PREV','prior_group')")
 c.execute("INSERT INTO validation_links VALUES ('A',NULL,' DOI:10.example/prev ','pending')")
 rejects('normalized_predecessor_doi_cross_group_rejected',[{'record_id':'A','study_group':'new_group'}])
 validate_link_groups(c,[{'record_id':'A','study_group':'prior_group'}]);checks['unresolved_predecessor_union_group_allowed']=True
 c.execute("UPDATE validation_links SET status='resolved_independent'")
 validate_link_groups(c,[{'record_id':'A','study_group':'new_group'}]);checks['explicitly_resolved_independence_allowed']=True
 out={'checks':checks,'all_passed':all(checks.values()),'fitting_performed':False,'fixture':'in-memory synthetic identity rows only'}
 (Path(__file__).parent/'v03_group_guard_checks.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
 print(json.dumps(out,indent=2));assert out['all_passed']
if __name__=='__main__':main()
