"""Rebuild only this revision's derived views/exports; never fit research data."""
from pathlib import Path
import sqlite3, json, csv, sys
from admission_policy import assess, clean_optional_pore, CORE, CHECKS, WATER_ELECTROLYTES

ROOT=Path(__file__).resolve().parent
sys.stdout.reconfigure(encoding='utf-8')
c=sqlite3.connect(ROOT/'cycling_v0_3r3.sqlite');c.row_factory=sqlite3.Row
c.execute('PRAGMA foreign_keys=ON')
rows=[dict(r) for r in c.execute('SELECT * FROM endpoint_effective_review')]
flags={r['record_id']:dict(r) for r in c.execute('SELECT * FROM admissions')}
blockers={r['record_id']:[dict(b) for b in c.execute('SELECT * FROM record_blockers WHERE record_id=?',(r['record_id'],))] for r in rows}
c.execute('DELETE FROM admission_decisions_r3')
for row in rows:
    rid=row['record_id']
    row['paper_year']=c.execute('SELECT year FROM papers WHERE paper_id=?',(row['paper_id'],)).fetchone()[0]
    row['group_review_status']=c.execute('SELECT review_status FROM validation_group_assignments WHERE record_id=?',(rid,)).fetchone()[0]
    fails=assess(row,flags[rid],blockers[rid])
    track=c.execute('SELECT track FROM utilization_routes WHERE record_id=?',(rid,)).fetchone()[0]
    extent='focused_main_record_review_complete_with_explicit_remaining_evidence_gap' if rid in {r[0] for r in c.execute('SELECT record_id FROM mass_definition_audits')} else 'scope_routing_and_completeness_preflight_only_not_a_full_field_audit'
    if track!='aqueous_symmetric_GCD_candidate': disp='outside_primary_track_retained_separately'
    elif not fails: disp='approved_core7'
    elif any(s.startswith('scope:') or s.startswith('label:') or s.startswith('record:') for s in fails): disp='excluded_or_held_by_scope_label_or_conflict'
    elif rid.startswith('SRC123_'): disp='blocked_current_definition_and_predecessor_overlap'
    elif rid=='R107_CY02': disp='blocked_current_definition_and_endpoint_window'
    elif extent.startswith('focused'): disp='blocked_current_definition_only'
    else: disp='blocked_incomplete_evidence'
    # A record is approved only after all scientific gates are met, never to meet a count target.
    if not fails:
        c.execute("UPDATE admissions SET status='approved',eligible=1 WHERE record_id=?",(rid,))
    elif flags[rid]['eligible']:
        raise RuntimeError('Previously eligible row fails current scientific checks: '+rid)
    c.execute('INSERT INTO admission_decisions_r3 VALUES(?,?,?,?,?,?)',
        (rid,disp,json.dumps(fails,ensure_ascii=False),sum(row[f] is not None for f in CORE),clean_optional_pore(row,blockers[rid]),extent))

old=c.execute("SELECT sql FROM sqlite_master WHERE name='training_ready'").fetchone()[0]
old_file=ROOT/'parent_training_ready_view.sql'
if not old_file.exists():old_file.write_text(old+';\n','utf-8')
c.execute('DROP VIEW training_ready')
# Scoped optional blockers remain open, but their values are masked before any use.
cols=[r[1] for r in c.execute('PRAGMA table_info(endpoint_effective_review)')]
projection=[]
for col in cols:
    if col=='total_pore_volume_cm3_g':
        projection.append("CASE WHEN e.pore_unit_review_required=1 OR EXISTS(SELECT 1 FROM record_blockers b JOIN blocker_scopes s USING(record_id,code) WHERE b.record_id=e.record_id AND b.status='open' AND s.scope_kind='field' AND s.field_name='total_pore_volume_cm3_g') THEN NULL ELSE e.total_pore_volume_cm3_g END AS total_pore_volume_cm3_g")
    else:projection.append('e.'+col)
c.execute('DROP VIEW IF EXISTS modeling_effective_inputs')
c.execute('CREATE VIEW modeling_effective_inputs AS SELECT '+','.join(projection)+' FROM endpoint_effective_review e')
water=','.join("'"+v+"'" for v in sorted(WATER_ELECTROLYTES))
sql=f'''CREATE VIEW training_ready AS SELECT e.*,g.group_id AS validation_group_id
 FROM modeling_effective_inputs e JOIN admissions a USING(record_id)
 JOIN validation_group_assignments g USING(record_id)
 JOIN papers p ON p.paper_id=e.paper_id
 WHERE e.system='2E_symmetric' AND e.method='GCD' AND e.metric_kind='capacitance_retention'
 AND e.material_scope IN ('carbon_candidate','carbon_control') AND e.category IN ('A','B')
 AND e.retention_relation='eq' AND e.retention_pct IS NOT NULL
 AND e.cycle_count>=1000 AND e.short_test=0 AND e.conflict=0 AND e.Si_residue_review_required=0
 AND e.current_density_A_g>0 AND e.mass_basis='two_electrode_total_active_mass'
 AND e.electrolyte IN ({water}) AND e.concentration_value>0 AND e.concentration_unit IN ('M','mol/L')
 AND e.voltage_lower_V IS NOT NULL AND e.voltage_upper_V>e.voltage_lower_V AND e.BET_m2_g>0
 AND p.year>=2023 AND p.year<=2026
 AND a.status='approved' AND a.eligible=1
 AND a.source_checked=1 AND a.material_checked=1 AND a.protocol_checked=1
 AND a.baseline_checked=1 AND a.mass_basis_checked=1 AND a.independence_checked=1 AND a.freeze_cleared=1
 AND g.review_status='reviewed_available_corpus'
 AND NOT EXISTS(SELECT 1 FROM record_blockers b LEFT JOIN blocker_scopes s USING(record_id,code)
 WHERE b.record_id=e.record_id AND b.status='open' AND COALESCE(s.affects_core7,1)=1)'''
c.execute(sql)
(ROOT/'training_ready_r3.sql').write_text(sql+';\n','utf-8')
c.execute('DROP VIEW IF EXISTS training_ready_pore')
c.execute('CREATE VIEW training_ready_pore AS SELECT * FROM training_ready')
# Optional pore missingness is permitted; this view is the same admitted cohort with masked optional fields.
c.commit()
out=ROOT/'exports';out.mkdir(exist_ok=True)
def export(name, query):
    cursor=c.execute(query);cols=list(dict.fromkeys(d[0] for d in cursor.description));v=[dict(r) for r in cursor]
    (out/(name+'.json')).write_text(json.dumps(v,ensure_ascii=False,indent=2),'utf-8')
    with (out/(name+'.csv')).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=cols);w.writeheader();w.writerows(v)
    return v
allrows=export('全部89条准入判定','SELECT e.record_id,e.paper_id,e.sample_name,e.system,e.method,e.retention_pct,e.retention_relation,u.track,d.* FROM admission_decisions_r3 d JOIN endpoint_effective_review e USING(record_id) JOIN utilization_routes u USING(record_id)')
primary=export('主候选10条逐项检查','SELECT e.record_id,e.paper_id,e.sample_name,e.cycle_count,e.retention_pct,e.current_density_A_g,e.mass_basis,e.voltage_lower_V,e.voltage_upper_V,e.BET_m2_g,e.total_pore_volume_cm3_g,a.*,d.primary_disposition,d.failures_json FROM endpoint_effective_review e JOIN admissions a USING(record_id) JOIN admission_decisions_r3 d USING(record_id) WHERE e.record_id IN (SELECT record_id FROM primary_screening_candidates)')
export('正式准入七输入','SELECT * FROM training_ready')
export('电流质量口径终审','SELECT * FROM mass_definition_audits')
export('来源分组终审','SELECT * FROM source_group_reviews')
export('验证分组89条','SELECT * FROM validation_group_assignments')
export('字段冻结与记录阻碍','SELECT b.*,s.scope_kind,s.field_name,s.affects_core7,s.policy FROM record_blockers b JOIN blocker_scopes s USING(record_id,code)')
summary={'baseline_primary_candidates':10,'current_primary_candidates':len(primary),
 'training_ready':c.execute('SELECT count(*) FROM training_ready').fetchone()[0],
 'primary_checks_passed':{k:sum(r[k] for r in primary) for k in CHECKS},
 'primary_dispositions':{k:c.execute('SELECT count(*) FROM admission_decisions_r3 WHERE primary_disposition=?',(k,)).fetchone()[0] for k in sorted({r['primary_disposition'] for r in allrows})},
 'primary_7_nonnull':c.execute('SELECT count(*) FROM admission_decisions_r3 WHERE core_fields_present=7 AND record_id IN (SELECT record_id FROM primary_screening_candidates)').fetchone()[0],
 'counts':{t:c.execute('SELECT count(*) FROM '+t).fetchone()[0] for t in ['papers','source_files','materials','cycling_tests','cycling_endpoints','review_events','revision_changes','material_observations']},
 'coverage':{f:dict(zip(('endpoints','materials','papers'),c.execute(f'SELECT count(*),count(DISTINCT material_id),count(DISTINCT paper_id) FROM endpoint_effective_review WHERE {f} IS NOT NULL').fetchone())) for f in ['BET_m2_g','total_pore_volume_cm3_g']},
 'no_research_training':True,'primary_target_unchanged':'cycling stability as capacitance retention at requested cycles and conditions'}
(ROOT/'准入闭环结果.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),'utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2));c.close()
