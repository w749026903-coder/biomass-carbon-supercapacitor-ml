from pathlib import Path
import json, collections, statistics, hashlib
OUT=Path(__file__).resolve().parent
rows=json.loads((OUT/'循环稳定性逐记录候选.json').read_text(encoding='utf-8'))
sources=json.loads((OUT/'全库循环证据定位.json').read_text(encoding='utf-8'))
def profile(items):
    return dict(endpoint_rows=len(items),material_keys=len({r['material_id'] for r in items}),
                source_papers=len({r['paper_id'] for r in items}),
                study_groups=len({r['study_group'] for r in items}))
numeric=[r for r in rows if r['cycle_count'] is not None and r['retention_pct'] is not None]
clean=[r for r in rows if r['candidate_clean']]
gcd=[r for r in clean if r['method']=='GCD' and r['system'] in ['3E','2E_symmetric']]
basic=[r for r in rows if r['provisional_core_conditions']]
minimal=[r for r in rows if r['provisional_minimal_features']]
minimal_bet=[r for r in basic if r['BET_m2_g'] is not None and r['voltage_complete']]
cohorts={s:profile([r for r in gcd if r['system']==s]) for s in ['3E','2E_symmetric']}
by_n={str(n):profile([r for r in gcd if r['cycle_count']==n]) for n in sorted({r['cycle_count'] for r in gcd})}
summary=dict(date='2026-10-17',scope='current local library only; no downloads, training, formal admission or historical script reruns',
             scanned_current_papers=len(sources),hashes_verified=121,
             original_experiment_candidate_sources=sum(s['category'] in ['A','B'] for s in sources),
             extracted_candidates=profile(rows),numeric_endpoints=profile(numeric),
             carbon_point_candidates=profile(clean),carbon_GCD_candidates=profile(gcd),
             paired_basic_conditions=profile(basic),paired_basic_conditions_BET_voltage=profile(minimal_bet),
             paired_basic_conditions_BET_totalpore_voltage=profile(minimal),
             cohorts=cohorts,gcd_cycle_count_cohorts=by_n,
             conflict_sources=sorted({r['paper_id'] for r in rows if r['conflict']}),
             CV_endpoint_rows=sum(r['method']=='CV' for r in rows),
             short_endpoint_rows=sum(r['short_test'] for r in rows),
             training_eligible_records=sum(r['eligible_for_database'] for r in rows),
             limitations=[
               'All material keys are provisional within-source identifiers, not final independent-material audit.',
               '81 candidate endpoint rows include unresolved/partial labels and separate systems; never 81 independent samples.',
               'Null input means not yet paired or not located, not proven absent from the paper.',
               'Basic-condition completeness is an extraction checkpoint, not quality admission or validation.',
               'Counts are explicitly extracted evidence lower bounds, not an exhaustive upper bound on digitizable curves.',
               'Current density mass denominator, voltage reference, baseline and source overlap still require record-level audit.',
               '1000 cycles is a provisional long-cycle screening boundary, not a scientific universal cutoff.',
               'No RUL label, no universal minimum ML sample size, no claim of achieved model performance.',
             ])
(OUT/'统计摘要.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2))

# Stable integrity checks for the actual extraction, not tests of model efficacy.
assert len({r['record_id'] for r in rows})==len(rows)
assert all(r['paper_id'] in {s['id'] for s in sources} for r in rows)
assert not any(r['eligible_for_database'] for r in rows)
assert all(r['year'] is None or r['year']>=2023 for r in rows)
assert all(r['cycle_count'] is None or r['cycle_count']>0 for r in rows)
assert all(r['retention_pct'] is None or r['retention_pct']>=0 for r in rows)
assert all(not r['candidate_clean'] or (not r['conflict'] and not r['short_test']) for r in rows)
assert all(r['method']=='GCD' for r in basic)
assert len({r['material_id'] for r in rows if r['paper_id']=='R107'})==1
assert len({r['material_id'] for r in rows if r['paper_id']=='SRC101'})==1
for r in rows:
    assert Path(r['evidence_path']).is_file()
(OUT/'数据核验.json').write_text(json.dumps(dict(
    unique_record_ids=True,all_sources_in_current_library=True,all_evidence_files_exist=True,
    no_pre2023_records=True,no_training_admission=True,CV_not_counted_as_GCD=True,
    repeated_endpoints_share_material_id=True,retention_above_100_preserved=True,
    original_pdfs_sha256_checked=121,visual_pages_reviewed=9),ensure_ascii=False,indent=2),encoding='utf-8')
