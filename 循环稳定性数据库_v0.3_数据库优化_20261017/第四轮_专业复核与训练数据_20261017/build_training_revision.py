"""One-time r4 profile-specific admission; no target/current edits or research fits."""
from pathlib import Path
import collections, csv, hashlib, json, re, shutil, sqlite3

ROOT = Path(__file__).resolve().parent
PARENT = ROOT.parent
R2 = PARENT/'第二轮_全量利用与输入定稿_20261017'
R3 = PARENT/'第三轮_逐条准入闭环_20261017'
DB = ROOT/'cycling_v0_3r4.sqlite'
BASE = {'R091_CY01','R093_CY01','R103_CY01','R104_CY01','R107_CY01','R111_CY01','SRC035_CY01','SRC124_CY01'}
RESIDUE = {'R112_CY02','R112_CY03'}
APPROX = {'R020_CY01'}
PROFILES = {'literature_core7_exact': BASE, 'literature_residue_sensitivity': BASE|RESIDUE,
            'literature_approx_sensitivity': BASE|RESIDUE|APPROX}

def dump(path, value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')

def export(name, rows):
    dump(ROOT/'exports'/f'{name}.json',rows)
    if rows:
        with (ROOT/'exports'/f'{name}.csv').open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main():
    c=sqlite3.connect(DB);c.row_factory=sqlite3.Row;c.execute('PRAGMA foreign_keys=ON')
    assert not c.execute("SELECT 1 FROM metadata WHERE key='r4_profile_revision_applied'").fetchone(),'Already applied'
    inventory=json.loads((R2/'source_inventory_all137.json').read_text('utf-8'))
    allrows={r['record_id']:dict(r) for r in c.execute('SELECT * FROM modeling_effective_inputs')}
    mains={f['paper_id']:f for f in inventory if f['role']=='main'}
    texts={pid:'\n'.join(p['text'] for p in json.loads(Path(f['extraction_path']).read_text('utf-8')))
           for pid,f in mains.items()}
    # Bounded corpus audit plus manual reading of original preparation and cycle sections.
    # An absence of a string match is a diagnostic, not proof of global independence.
    audit={}
    for pid,anchor in [('R112','Act_OFSCBC'),('R020','NdFeB')]:
        paper=dict(c.execute('SELECT * FROM papers WHERE paper_id=?',(pid,)).fetchone())
        hits=[]
        for other,text in texts.items():
            if other!=pid and anchor.casefold() in text.casefold():
                pos=text.casefold().find(anchor.casefold())
                hits.append({'paper_id':other,'context':text[max(0,pos-150):pos+240]})
        audit[pid]={'paper_doi':paper['doi'],'sample_anchor':anchor,'cross_paper_anchor_hits':hits,
                    'same_file_hash_papers':[q for q,f in mains.items() if q!=pid and f['sha256']==mains[pid]['sha256']],
                    'existing_source_relationships':[dict(r) for r in c.execute('SELECT * FROM source_relationships WHERE paper_id=? OR related_paper_id=?',(pid,pid))],
                    'existing_endpoint_links':[dict(r) for r in c.execute('SELECT * FROM validation_links WHERE record_a LIKE ? OR record_b LIKE ?',(pid+'%',pid+'%'))],
                    'manual_review':'Read own preparation, characterization and symmetric device cycling sections. R112 two nodes same Fig11c; R020 AC control separate from its NdFeB/PANI composites. No documented cross-source cycle-data reuse located in this available corpus; not a global independence proof.',
                    'source_path':mains[pid]['path'],'source_sha256':sha(mains[pid]['path'])}
    dump(ROOT/'来源分组复核_r4.json',audit)
    c.executescript('''
    CREATE TABLE profile_admissions_r4(
      profile TEXT NOT NULL,record_id TEXT NOT NULL REFERENCES cycling_endpoints,
      eligible INTEGER NOT NULL CHECK(eligible IN(0,1)),status TEXT NOT NULL,
      failures_json TEXT NOT NULL,qualified_use TEXT NOT NULL,caveats_json TEXT NOT NULL,
      evidence_json TEXT NOT NULL,review_extent TEXT NOT NULL,
      PRIMARY KEY(profile,record_id),CHECK(eligible=0 OR status='approved_for_declared_profile'));
    CREATE TABLE domain_reviews_r4(
      record_id TEXT NOT NULL REFERENCES cycling_endpoints,topic TEXT NOT NULL,
      decision TEXT NOT NULL,value_json TEXT,source_path TEXT NOT NULL,source_sha256 TEXT NOT NULL,
      locator TEXT NOT NULL,rationale TEXT NOT NULL,PRIMARY KEY(record_id,topic));
    CREATE TABLE profile_definitions_r4(profile TEXT PRIMARY KEY,definition_json TEXT NOT NULL);
    ''')
    def review(rid,topic,decision,value,locator,rationale):
        row=allrows[rid]; path=mains[row['paper_id']]['path']
        c.execute('INSERT INTO domain_reviews_r4 VALUES(?,?,?,?,?,?,?,?)',
                  (rid,topic,decision,json.dumps(value,ensure_ascii=False),path,sha(path),locator,rationale))
    for rid in sorted(RESIDUE):
        review(rid,'material_scope','qualified_for_residue_sensitivity',{'reported_Si_percent':1.7,'percent_basis':'unspecified','purity_proven':False},
               'PDF p2 preparation, p6 XPS, p10 cycling, p13 Fig11c',
               'Biomass activated carbon without intentionally added oxide/polymer; retain Si flag and limit to declared residue-inclusive sensitivity. Not cleared as pure carbon.')
        review(rid,'normalization_reference','author_curve_initial_reference',{'reference':'Fig11c plotted start approximately100%','exact_reference_cycle':None},
               'PDF p10 and p13 Fig11c; evidence_images/R112_p13.png',
               '5000/10000 nodes belong to the same retention curve. Baseline accepted as author plotted reference, not guessed to be cycle1.')
        review(rid,'source_group','reviewed_available_corpus',{'group_id':allrows[rid]['study_group']},
               'Own preparation/results and 来源分组复核_r4.json',audit['R112']['manual_review'])
    review('R020_CY01','numeric_label','approximate_point_only',{'retention_pct':89.0,'relation':'approx','reference':'author initial capacitance'},
           'PDF p11-13 sec3.5 Fig7; evidence_images/R020_p13.png',
           'AC control under symmetric1M KNO3,0–1V,3A/g,5000cycles. Preserve approximately89%; no transference of asymmetric-section current normalization.')
    review('R020_CY01','source_group','reviewed_available_corpus',{'group_id':allrows['R020_CY01']['study_group']},
           'Own AC preparation/symmetric results and 来源分组复核_r4.json',audit['R020']['manual_review'])
    for rid in sorted(RESIDUE|APPROX):
        review(rid,'current_input','as_reported_uncalibrated',{'reported_current_A_g':allrows[rid]['current_density_A_g'],'canonical_current_A_g':None,'denominator_status':'not_uniquely_defined'},
               'Own device methods and cycle paragraph',
               'Literal author cycling current accepted only as an empirical literature descriptor; physical denominator remains unresolved.')
    for rid in sorted(x for x in allrows if x.startswith('SRC028_')):
        review(rid,'device_protocol','held_internal_voltage_and_electrolyte_scope',{'reported_window':[0,1],'Fig6c_GCD_axis_approx':[-0.8,0],'device_electrolyte_confirmation':None},
               'PDF p3 methods,p8 sec3.2,p9 Fig6c; evidence_images/SRC028_p9.png',
               '6M KOH is expressly in the3E sentence; Fig6c device caption conflicts with its negative GCD axis. Preserve raw report, do not assign a corrected cycling window or verified2E electrolyte.')

    core=['cycle_count','current_density_A_g','electrolyte','concentration_value','voltage_lower_V','voltage_upper_V','BET_m2_g']
    previous={r['record_id']:dict(r) for r in c.execute('SELECT * FROM utilization_routes')}
    flags=['source_checked','material_checked','protocol_checked','baseline_checked','independence_checked','freeze_cleared']
    for profile,selected in PROFILES.items():
        definition={'scope':'2E_symmetric aqueous liquid GCD biomass carbon; literature-reported current descriptor',
                    'target':'capacitance_retention_pct_at_requested_cycles_and_protocol',
                    'physical_current_harmonized':False,'mass_denominator_unknown_allowed_only_for_reported_descriptor':True,
                    'residue_extension':profile!='literature_core7_exact',
                    'numeric_approx_extension':profile=='literature_approx_sensitivity',
                    'primary':profile=='literature_core7_exact','training_authorized':False}
        c.execute('INSERT INTO profile_definitions_r4 VALUES(?,?)',(profile,json.dumps(definition)))
        for rid,row in sorted(allrows.items()):
            a=dict(c.execute('SELECT * FROM admissions WHERE record_id=?',(rid,)).fetchone())
            failures=[]; evidence=[]
            if row['system']!='2E_symmetric':failures.append('outside_2E_symmetric')
            if row['method']!='GCD':failures.append('outside_GCD')
            if row['conflict']:failures.append('unresolved_label_or_pairing_conflict')
            if row['retention_pct'] is None:failures.append('target_missing_no_imputation')
            if row['retention_relation']!='eq' and not (rid in APPROX and definition['numeric_approx_extension']):
                failures.append('not_exact_reported_point')
            missing=[k for k in core if row[k] is None]
            if missing:failures.append('missing_core:'+','.join(missing))
            if row['concentration_unit'] not in ('M','mol/L'):failures.append('non_molar_or_unknown_concentration_no_conversion')
            if row['short_test'] or (row['cycle_count'] or 0)<1000:failures.append('outside_project_cycle_horizon')
            if rid.startswith('SRC028_'):failures.append('device_protocol_internal_conflict_and_electrolyte_scope')
            if rid=='SRC123_CY02' or rid=='SRC123_CY01':failures.append('predecessor_data_relationship_unresolved')
            if rid in RESIDUE and not definition['residue_extension']:failures.append('residue_inclusive_scope_extension_only')
            if row['material_scope'] not in ('carbon_candidate','carbon_control'):
                failures.append('material_scope_not_qualified_for_profile')
            if rid in BASE:
                assert all(a[k]==1 for k in flags),(rid,a)
                pending=[b['code'] for b in c.execute('''SELECT b.code FROM record_blockers b LEFT JOIN blocker_scopes s USING(record_id,code)
                    WHERE b.record_id=? AND b.status='open' AND COALESCE(s.affects_core7,1)=1 AND b.code!='mass_basis_checked' ''',(rid,))]
                assert not pending,(rid,pending)
                evidence.append('r3 source/material/protocol/baseline/source-group/freeze evidence reused; only denominator gate re-scoped')
            elif rid in (RESIDUE|APPROX):
                evidence.append('r4 own-paper methods/label/figure review; bounded source-group audit; use qualified only in specified sensitivity profile')
            else:
                incomplete=[k for k in flags if a[k]!=1]
                if incomplete:failures.append('not_closed_by_review:'+','.join(incomplete))
            if rid not in selected and not failures:failures.append('not_released_after_evidence_review')
            assert (not failures)==(rid in selected),(profile,rid,failures)
            caveats=['author_reported_current_denominator_unresolved','unmodeled_temperature_and_loading','small_source_count']
            if rid in RESIDUE:caveats+=['reported_Si1.7_percent_basis_unspecified','shared_curve_two_endpoints']
            if rid in APPROX:caveats+=['approximate89_percent_no_error_bound_given']
            if row['total_pore_volume_cm3_g'] is None:caveats+=['optional_total_pore_missing_or_masked']
            evidence+=['existing route:'+previous[rid]['track']+' / '+previous[rid]['label_tier']]
            c.execute('INSERT INTO profile_admissions_r4 VALUES(?,?,?,?,?,?,?,?,?)',
                      (profile,rid,int(rid in selected),'approved_for_declared_profile' if rid in selected else 'held_or_separate_use',
                       json.dumps(failures), 'exploratory_literature_retention_regression' if rid in selected else previous[rid]['usable_role'],
                       json.dumps(caveats),json.dumps(evidence),
                       'r3 bounded evidence plus r4 estimand review' if rid in BASE else 'r4 own-paper focused review' if rid in (RESIDUE|APPROX) or rid.startswith('SRC028_') else 'inherited review; current profile routing only'))

    old=c.execute("SELECT sql FROM sqlite_master WHERE name='training_ready'").fetchone()[0]
    dump(ROOT/'legacy_training_ready_definition.json',{'r3_training_ready_sql':old})
    c.execute(old.replace('CREATE VIEW training_ready AS','CREATE VIEW training_ready_canonical_current AS',1))
    c.execute('DROP VIEW training_ready_pore');c.execute('DROP VIEW training_ready')
    cols=[x[1] for x in c.execute('PRAGMA table_info(modeling_effective_inputs)')]
    selected_cols=','.join('e.'+k for k in cols if k not in ('admission_status','eligible'))
    c.execute(f'''CREATE VIEW training_rows_r4 AS SELECT {selected_cols},
      e.admission_status AS legacy_admission_status,e.eligible AS legacy_eligible,
      a.profile,a.status AS admission_status,a.eligible,a.caveats_json,
      e.current_density_A_g AS reported_current_A_g,
      CAST(NULL AS REAL) AS canonical_current_A_g,
      'not_uniquely_defined' AS current_denominator_status,
      'author_reported_protocol_descriptor' AS current_input_semantics,
      g.group_id AS validation_group_id,
      1.0 / COUNT(*) OVER(PARTITION BY a.profile,g.group_id) AS source_weight
      FROM modeling_effective_inputs e JOIN profile_admissions_r4 a USING(record_id)
      JOIN validation_group_assignments g USING(record_id) WHERE a.eligible=1''')
    c.execute("CREATE VIEW training_ready AS SELECT * FROM training_rows_r4 WHERE profile='literature_core7_exact'")
    c.execute('CREATE VIEW training_ready_pore AS SELECT * FROM training_ready')
    c.execute("INSERT INTO metadata VALUES('r4_profile_revision_applied','true')")
    c.commit()
    for profile in PROFILES:
        rows=[dict(r) for r in c.execute('SELECT * FROM training_rows_r4 WHERE profile=? ORDER BY validation_group_id,material_id,cycle_count',(profile,))]
        export(profile,rows)
    export('全部89端点_逐用途准入与待补项',[dict(r) for r in c.execute('SELECT * FROM profile_admissions_r4 ORDER BY record_id,profile')])
    export('专业复核证据_r4',[dict(r) for r in c.execute('SELECT * FROM domain_reviews_r4 ORDER BY record_id,topic')])
    for name in ['benchmark_engine.py','model_spaces.json','train_nested.py']:
        shutil.copy2(R2/'modeling'/name,ROOT/'modeling'/name)
    cfg=json.loads((R2/'modeling/model_contract.json').read_text('utf-8'))
    cfg.update(database_file=DB.name,database_view='training_ready',default_profile='literature_core7_exact',
               current_input='reported_current_A_g',canonical_current_mass_basis=None,
               readiness='profile-specific evidence closure for exploratory reported-protocol model; not calibrated-current admission',
               label_relations_by_profile={p:['eq','approx'] if p=='literature_approx_sensitivity' else ['eq'] for p in PROFILES},
               current_denominator_policy='Unknown is retained. Never infer, convert or impute the current denominator. Canonical-current view is separate.',
               research_training_authorized=False)
    cfg['required_conditions']=[x.replace('current_density_A_g','reported_current_A_g') for x in cfg['required_conditions']]
    cfg['split'].update(folds_up_to=126,shuffle=False,tuning='Leave one available source out; fixed defaults initially. Any expanded tuning must use inner source-group folds.')
    cfg['tuning'].update(candidate_budget_per_model=1,budget_by_model={})
    cfg['feature_sets']={name:[x.replace('current_density_A_g','reported_current_A_g') for x in features] for name,features in cfg['feature_sets'].items()}
    cfg['feature_sets']['without_current']=[x for x in cfg['feature_sets']['plus_BET'] if x!='reported_current_A_g']
    cfg['forbidden_features']+=['current_density_A_g','canonical_current_A_g','current_denominator_status','source_weight','profile']
    cfg['evaluation']+=['same_cohort_without_current_sensitivity','nested_profile_sensitivity_not_posthoc_selection']
    cfg['comparison_policy']='Fixed core7 main; same-cohort no-current, no-BET and optional-pore sensitivities. Profile expansions reported separately. No accuracy claim before grouped validation.'
    dump(ROOT/'modeling/model_contract.json',cfg)
    # With candidate budget1, actual candidate is the explicitly declared default, not a random draw.
    engine=(ROOT/'modeling/benchmark_engine.py').read_text('utf-8')
    needle="    return list(ParameterSampler(grid,n_iter=min(budget,math.prod(len(v) for v in grid.values())),random_state=cfg['split']['random_state']))"
    assert needle in engine
    engine=engine.replace(needle,"    if budget == 1:\n        return [copy.deepcopy(specs[name]['default'])]\n"+needle)
    # Keep the authorization boundary at the shared engine, not only its CLI wrapper.
    needle='    specs = validate_config(cfg)\n    rows = validate_rows'
    assert needle in engine
    engine=engine.replace(needle,"    if not synthetic and cfg.get('research_training_authorized') is not True:\n        raise RuntimeError('Research fitting is disabled in this data-preparation revision')\n    specs = validate_config(cfg)\n    rows = validate_rows")
    (ROOT/'modeling/benchmark_engine.py').write_text(engine,encoding='utf-8')
    inp=json.loads((R3/'prediction_input_contract.json').read_text('utf-8'))
    inp.update(schema_version='retention-input-contract-r4-reported-current',decision_status='explicit_literature_reported_protocol_estimand',
               default_profile=cfg['default_profile'],training_authorized=False,current_unit_policy=cfg['current_denominator_policy'])
    for item in inp['required_physical_inputs']:
        if item['name']=='current_density_A_g':
            item.update(name='reported_current_A_g',label='作者报告的循环电流（质量口径不齐）',canonical_mass_basis=None,
                        normalization_metadata_required='Keep unknown denominator explicit; literal reported descriptor, not calibrated physical stress.')
    inp['scope']['material']='biomass carbon main; residue-inclusive sensitivity separately declared'
    inp['definition_change_from_v03']+=['r4 distinguishes reported-current empirical model from calibrated-current model; old canonical admission not overwritten.']
    dump(ROOT/'prediction_input_contract.json',inp)
    c.close()
    print('r4 profiles built:8 core;10 residue sensitivity;11 approximate sensitivity;0 canonical-current. No research fitting.')

if __name__=='__main__':main()
