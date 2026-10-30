"""Read-only-callable research curve increment; preserve frozen and final labels."""
from pathlib import Path
import collections,hashlib,json,math,sqlite3
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'保持率达标研究_v3_主线与近优组合_20261030/第十一轮_双电极原文曲线补充'
def read(p):return json.loads(Path(p).read_text('utf8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 dest=OUT/'cycling_research_v3d.sqlite';assert not dest.exists(),'Never overwrite a research store'
 curves=read(OUT/'curve_dataset_v3d.json');source_input_sha=sha(OUT/'curve_dataset_v3d.json');db=sqlite3.connect(dest);db.execute('PRAGMA foreign_keys=ON')
 db.executescript('''CREATE TABLE sources(source_family TEXT PRIMARY KEY);
 CREATE TABLE curves(curve_id TEXT PRIMARY KEY,source_family TEXT NOT NULL REFERENCES sources,endpoint_id TEXT NOT NULL,system TEXT CHECK(system IN ('2E','3E')),sample_name TEXT,target_cycle_count REAL NOT NULL,target_retention_pct REAL NOT NULL,approved INTEGER CHECK(approved IN (0,1)),figure_path TEXT NOT NULL,figure_sha256 TEXT NOT NULL,raw_json TEXT NOT NULL);
 CREATE TABLE curve_points(curve_id TEXT REFERENCES curves,marker_index INTEGER,cycle_coordinate REAL,cycle_upper REAL,retention_pct REAL,reading_bound_pp REAL,raw_json TEXT,PRIMARY KEY(curve_id,marker_index));
 CREATE TABLE early_windows(curve_id TEXT REFERENCES curves,fraction REAL CHECK(fraction IN (0.1,0.2)),point_count INTEGER,last_early_retention_pct REAL,early_mean_retention_pct REAL,early_retention_slope_per_1000_cycles REAL,early_retention_range_pp REAL,early_observed_cycle_count REAL,maximum_reading_bound_pp REAL,point_indices_json TEXT,static_features_json TEXT,PRIMARY KEY(curve_id,fraction));
 CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
 CREATE VIEW training_windows AS SELECT c.curve_id,c.endpoint_id,c.source_family,c.system,c.sample_name,c.target_cycle_count,c.target_retention_pct,w.fraction,w.point_count,w.last_early_retention_pct,w.early_mean_retention_pct,w.early_retention_slope_per_1000_cycles,w.early_retention_range_pp,w.early_observed_cycle_count,w.maximum_reading_bound_pp,w.point_indices_json,w.static_features_json FROM curves c JOIN early_windows w USING(curve_id) WHERE c.approved=1 AND w.point_count>=3;
 CREATE VIEW training_B_3E_early20 AS SELECT * FROM training_windows WHERE system='3E'AND fraction=0.2;
 CREATE VIEW training_B_3E_early10 AS SELECT * FROM training_windows WHERE system='3E'AND fraction=0.1;
 CREATE VIEW training_B_2E_early20 AS SELECT * FROM training_windows WHERE system='2E'AND fraction=0.2;
 CREATE VIEW training_B_2E_early10 AS SELECT * FROM training_windows WHERE system='2E'AND fraction=0.1;
 ''')
 checks=0
 for q in curves:
  assert sha(ROOT/q['figure_path'])==q['figure_sha256'];checks+=1;cid=q['curve_id'];db.execute('INSERT OR IGNORE INTO sources VALUES(?)',(q['source_family'],));db.execute('INSERT INTO curves VALUES(?,?,?,?,?,?,?,?,?,?,?)',(cid,q['source_family'],q['endpoint_id'],q['system'],q['sample_name'],q['target_cycle_count'],q['author_retention_pct'],int(q['training_eligible_pending_visual_review']),q['figure_path'],q['figure_sha256'],json.dumps(q,ensure_ascii=False)))
  for pt in q['points']:db.execute('INSERT INTO curve_points VALUES(?,?,?,?,?,?,?)',(cid,pt['marker_index'],pt['cycle_coordinate'],pt['cycle_upper'],pt['retention_pct'],pt['reading_bound_pp'],json.dumps(pt,ensure_ascii=False)))
  static={k:q['features'].get(k)for k in['reported_current_A_g','electrolyte','concentration_mol_L','cycle_voltage_lower_V','cycle_voltage_upper_V','BET_m2_g']+(['reference_electrode']if q['system']=='3E'else[])}
  for f in[.1,.2]:
   ps=[p for p in q['points']if p['cycle_upper']<=f*q['target_cycle_count']];n=len(ps)
   if n:
    x=[p['cycle_coordinate']for p in ps];y=[p['retention_pct']for p in ps];xm=sum(x)/n;ym=sum(y)/n;den=sum((v-xm)**2 for v in x);slope=sum((xx-xm)*(yy-ym)for xx,yy in zip(x,y))/den*1000 if den else None;values=[y[-1],ym,slope,max(y)-min(y),x[-1],max(p['reading_bound_pp']for p in ps)]
   else:values=[None]*6
   db.execute('INSERT INTO early_windows VALUES(?,?,?,?,?,?,?,?,?,?,?)',(cid,f,n,*values,json.dumps([p['marker_index']for p in ps]),json.dumps(static,ensure_ascii=False)))
 db.executemany('INSERT INTO metadata VALUES(?,?)',[('input_sha256',source_input_sha),('purpose','exploratory_early_window_retention_only_not_formal_new_endpoint_admission'),('research_goal','active'),('fitted_phase2_models','0')]);db.commit()
 assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'and not db.execute('PRAGMA foreign_key_check').fetchall();checks+=2
 counts={}
 for system in['2E','3E']:
  for f in[.1,.2]:
   view=f'training_B_{system}_early{int(f*100)}';counts[view]=db.execute(f'SELECT count(*),count(DISTINCT source_family) FROM {view}').fetchone()
   expected=[q for q in curves if q['system']==system and q['training_eligible_pending_visual_review']and len([p for p in q['points']if p['cycle_upper']<=f*q['target_cycle_count']])>=3];assert counts[view]==(len(expected),len({q['source_family']for q in expected}));checks+=1
 assert counts['training_B_3E_early20']==(30,24)and counts['training_B_3E_early10']==(20,19)and counts['training_B_2E_early20']==(8,8)and counts['training_B_2E_early10']==(5,5)
 db.row_factory=sqlite3.Row;export=[dict(r)for r in db.execute('SELECT * FROM training_windows ORDER BY system,fraction,curve_id')];db.close();assert sha(OUT/'curve_dataset_v3d.json')==source_input_sha;checks+=1
 (OUT/'training_windows_v3d.json').write_bytes((json.dumps(export,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode('utf8'))
 result=dict(status='research_store_verified',checks=checks,input_sha256=source_input_sha,sqlite_sha256=sha(dest),views=counts,new_early_curves=19,old_endpoint_labels_changed=0,new_formal_cycle_admissions=0,new_independent_external_sources=0,phase2_model_fits=0,research_goal_status='active',api='sqlite3.connect("file:/absolute/path/cycling_research_v3d.sqlite?mode=ro",uri=True); SELECT * FROM training_B_3E_early20; do not treat all curve_points as independent samples.')
 (OUT/'store_verification_v3d.json').write_bytes((json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode('utf8'));print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
