"""Locate numeric cycling claims in all indexed original-experiment papers.
These are unreviewed extraction leads, never model rows or scientific admissions.
"""
from pathlib import Path
import json,re,sqlite3
R=Path(__file__).resolve().parents[1];O=R/'循环稳定性数据库_v0.4_提取与调用_20261018'
def main():
 c=sqlite3.connect(O/'cycling_v0_4.sqlite');c.row_factory=sqlite3.Row;c.execute('pragma foreign_keys=ON')
 c.executescript('''CREATE TABLE native_measurement_claims(claim_id INTEGER PRIMARY KEY,identity_key TEXT REFERENCES literature_registry,source_id TEXT REFERENCES document_sources,segment_id INTEGER REFERENCES source_segments,start_offset INTEGER,end_offset INTEGER,cycle_count_candidate INTEGER,retention_pct_candidate REAL,metric_wording TEXT,qualifier TEXT,source_context TEXT,evidence_span TEXT,review_status TEXT NOT NULL CHECK(review_status='machine_pair_candidate_unreviewed'),eligible INTEGER NOT NULL CHECK(eligible=0),UNIQUE(identity_key,segment_id,start_offset,end_offset));CREATE INDEX idx_native_claim_identity ON native_measurement_claims(identity_key);CREATE INDEX idx_native_claim_cycle ON native_measurement_claims(cycle_count_candidate);''')
 scopes={r['identity_key']:r['status'] for r in c.execute('select * from extraction_queue')};scanned=0;found=0;stats=[]
 percentage=re.compile(r'(?<![\d.])(\d{1,3}(?:\.\d+)?)\s*(?:%|percent\b)',re.I)
 cycles=re.compile(r'(?<![\d.])(\d{1,3}(?:[,\s]\d{3})+|\d{3,7})\s*(?:charge[–-]discharge\s*)?cycles?\b',re.I)
 metrics=re.compile(r'capacitance\s+retention|capacitance\s+(?:retained|remaining)|retained\s+capacitance|capacity\s+retention|cycling\s+stability|capacitance\s+loss',re.I)
 for q in c.execute("select * from extraction_queue where main_source_id is not null and priority<3").fetchall():
  scanned+=1;paper_count=0
  for segment in c.execute('select * from source_segments where source_id=?',(q['main_source_id'],)).fetchall():
   t=segment['text'];seen=set()
   for metric in metrics.finditer(t):
    a=max(0,metric.start()-180);b=min(len(t),metric.end()+380);fragment=t[a:b];ns=list(cycles.finditer(fragment));ps=list(percentage.finditer(fragment))
    if not ns or not ps:continue
    for n in ns:
     # Pair only the nearest numeric percentage as a review lead. System/sample/current are not inferred.
     pct=min(ps,key=lambda p:abs((p.start()+p.end())/2-(metric.start()-a)))
     nval=int(re.sub(r'\s|,','',n[1]));pval=float(pct[1]);start=a+min(metric.start()-a,n.start(),pct.start());end=a+max(metric.end()-a,n.end(),pct.end());signature=(start,end)
     if signature in seen:continue
     seen.add(signature);span=t[max(0,start-100):min(len(t),end+120)]
     context='comparison_table_or_mixed_sources_needs_original_trace' if segment['section_kind']=='table-wrap' and re.search(r'\bRef\b|comparison|reported (?:studies|papers)',t,re.I) else 'own_article_passage_context_not_yet_bound'
     qualifier='approximate_or_bound_wording_present' if re.search(r'about|approx|over|above|more than|nearly|almost|∼|~|>|<',span,re.I) else 'not_classified'
     c.execute('insert or ignore into native_measurement_claims(identity_key,source_id,segment_id,start_offset,end_offset,cycle_count_candidate,retention_pct_candidate,metric_wording,qualifier,source_context,evidence_span,review_status,eligible) values (?,?,?,?,?,?,?,?,?,?,?,?,0)',(q['identity_key'],segment['source_id'],segment['segment_id'],start,end,nval,pval,metric[0],qualifier,context,span,'machine_pair_candidate_unreviewed'));paper_count+=1
  if q['status']=='indexed_target_review_pending':c.execute("update extraction_queue set status='native_text_scanned_awaiting_record_review',reason=? where identity_key=?",(f'Numeric phrase scan located{paper_count}unreviewed candidate pairs; sample/configuration/CE-vs-retention/secondary-source binding still required. Zero pairs does not prove no endpoint exists in figures.',q['identity_key']))
  stats.append({'identity_key':q['identity_key'],'claim_candidates':paper_count,'human_review_status':q['status']})
 c.commit();summary={'indexed_original_experiment_papers_scanned':scanned,'papers_with_numeric_claim_leads':c.execute('select count(distinct identity_key) from native_measurement_claims').fetchone()[0],'unreviewed_claim_leads':c.execute('select count(*) from native_measurement_claims').fetchone()[0],'new_training_admissions':0,'note':'Phrase pairs may still include different samples, qualitative/bound/capacity metrics or comparison data. They are isolated from model_feature_cache and all dataset exports.'};(O/'全文预提取覆盖.json').write_text(json.dumps({'summary':summary,'papers':stats},ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(summary,ensure_ascii=False));c.close()
if __name__=='__main__':main()
