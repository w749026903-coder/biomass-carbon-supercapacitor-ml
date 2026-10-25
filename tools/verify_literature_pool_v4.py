"""Read-only v4 postseal verifier: four CSV checks do not change the sealed preflight summary.
The original sealed extractor is preserved. All its science checks, plus CSV and manifest
hash checks, still run. This file cannot build, reseal, or modify the evidence database.
"""
from extract_literature_pool_v4 import *
def verify():
    if not (OUT/'merge_manifest.json').exists():raise FileNotFoundError('Sealed batch required; this verifier never builds or seals.')
    checks=[]
    def check(name,ok):
        if not ok:raise AssertionError(name)
        checks.append(name)
    proof=json.loads((OUT/'source_protection.json').read_text('utf8'))
    for key,d in proof['documents'].items():check('original_'+key,sha(ROOT/d['path'])==d['sha256'])
    for key in ['parent','corpus']:check('unchanged_'+key,sha(ROOT/proof[key]['path'])==proof[key]['sha256'])
    check('cycling_pointer',json.loads((ROOT/'data/current_database.json').read_text('utf8'))==proof['cycling_pointer'])
    with closing(ro(DB)) as c,closing(ro(PARENT)) as old:
        c.row_factory=sqlite3.Row
        check('integrity',c.execute('pragma integrity_check').fetchone()[0]=='ok');check('foreign_keys',not c.execute('pragma foreign_key_check').fetchall())
        for (name,) in old.execute("select name from sqlite_master where type='table' and name not like 'sqlite_%'"):
            if name=='raw_table_queue':continue
            current={tuple(r) for r in c.execute('select * from '+name)}
            check('parent_rows_'+name,all(tuple(r) in current for r in old.execute('select * from '+name)))
        oldq={r[0]:tuple(r) for r in old.execute('select * from raw_table_queue')};q=[tuple(r) for r in c.execute('select * from raw_table_queue')]
        check('queue_identity',set(oldq)=={r[0] for r in q})
        check('queue_raw_fields',all(r[:6]==oldq[r[0]][:6] and r[7:]==oldq[r[0]][7:] for r in q))
        for rec in json.loads((OUT/'table_review_receipt.json').read_text('utf8')):
            doc=proof['documents'][rec['document']]
            if rec['kind'] in ['own_xml_table','mixed_comparison_table']:
                root=E.parse(ROOT/doc['path']).getroot();ident=rec['locator'].removeprefix('XML table-wrap ');t=root.find(".//table-wrap[@id='"+ident+"']")
                for i,r in enumerate(t.findall('.//tr')):check('xml_'+rec['table_key']+'_'+str(i),[txt(v) for v in r if v.tag in ['td','th']]==json.loads(c.execute('select cells_json from transcribed_rows where table_key=? and row_ordinal=?',(rec['table_key'],i)).fetchone()[0]))
        for r in c.execute('select * from evidence_spans_v4'):
            root=E.parse(ROOT/proof['documents'][r['document_key']]['path']).getroot();loc=r['locator']
            actual=txt(root.find('.//abstract')) if loc=='XML abstract' else txt(root.findall('.//body//p')[int(loc.split('index')[-1])])
            check('span_'+r['document_key']+'_'+loc,actual==r['text'])
        for r in c.execute('select f.*,v.component,v.numeric_token from material_facts f join value_components_v3 v using(fact_id) where fact_id>519'):
            cells=json.loads(c.execute('select cells_json from transcribed_rows where table_key=? and row_ordinal=?',(r['table_key'],r['row_ordinal'])).fetchone()[0]);check('rawcell_'+str(r['fact_id']),cells[r['column_ordinal']]==r['raw_value'])
            check('number_'+str(r['fact_id']),r['value']==float(r['numeric_token']))
            if r['component'].startswith('slash_component_'):token=r['raw_value'].split('/')[int(r['component'][-1])-1]
            else:
                p={'whole':r'^\s*(\d+(?:\.\d+)?)\s*$','leading':r'^\s*(\d+(?:\.\d+)?)','parenthetical_percent':r'\((\d+(?:\.\d+)?)%\)'}[r['component']];token=re.search(p,r['raw_value'])[1]
            check('component_'+str(r['fact_id']),token==r['numeric_token'])
        for table in ['raw_table_queue','material_facts','capacitance_observations','test_candidates','outcome_observations_v3']:check('no_automatic_admission_'+table,c.execute('select count(*) from '+table+' where training_eligible!=0 or training_eligible is null').fetchone()[0]==0)
        new_dois={T,H,W}
        for r in c.execute('select x.*,m.doi from capacitance_observations x join materials m using(material_key)'):
            if r['doi'] not in new_dois:continue
            cells=json.loads(c.execute('select cells_json from transcribed_rows where table_key=? and row_ordinal=?',(r['table_key'],r['row_ordinal'])).fetchone()[0])
            check('cap_source_cell_'+r['observation_id'],r['raw_value']==cells[r['column_ordinal']] and float(r['raw_value'])==r['value'])
        import pypdfium2 as pdf
        with pdf.PdfDocument(str(ROOT/proof['documents']['Hardwood_SI']['path'])) as d:
            page=d[0];tp=page.get_textpage();text=tp.get_text_range();tp.close();page.close()
        for spec in PDF_TABLES:
            for row in spec['rows']:
                for token in row[1:]:check('SI_native_token_'+spec['id']+'_'+row[0]+'_'+token,token in text)
        check('cycling_candidates_still_pending',all(not json.loads(r[0])['current_cycle_database_membership'] for r in c.execute("select record_json from test_candidates where candidate_id like 'LP4_%'")))
        count=lambda t:c.execute('select count(*) from '+t).fetchone()[0]
        untouched=c.execute("select count(*) from raw_table_queue where review_state='automatic_candidate_unreviewed'").fetchone()[0]
        aux=c.execute('select * from auxiliary_reported_GCD_v3').fetchall();parts=Counter(r['purpose'] for r in aux)
        summary=dict(identity_catalogue_entries=480,raw_table_candidates=959,raw_table_rows=6121,cumulative_reviewed_source_publications=count('reviewed_sources'),cumulative_materials=count('materials'),cumulative_selected_material_cells=count('material_facts'),cumulative_numeric_material_facts=c.execute('select count(*) from material_facts where value is not null').fetchone()[0],new_materials=count('materials')-46,new_numeric_material_facts=c.execute('select count(*) from material_facts where value is not null').fetchone()[0]-511,reviewed_table_units=c.execute("select count(*) from reviewed_tables where table_key not in (select table_key from extraction_units_v3) or table_key in (select table_key from extraction_units_v3 where kind in ('own_xml_table','own_SI_table','own_and_comparison_pdf_table','mixed_comparison_table'))").fetchone()[0],reviewed_evidence_units=count('reviewed_tables'),raw_candidates_touched=959-untouched,raw_candidates_untouched=untouched,capacitance_records=count('capacitance_observations'),numeric_capacitance_values=c.execute('select count(*) from capacitance_observations where value is not null').fetchone()[0],unreported_capacitance_cells=2,cycling_candidates=count('test_candidates'),scientific_issues=count('scientific_issues'),historical_selected_fact_references=725,historical_fact_references_with_same_source_table_candidates=171,synthesis_materials=count('synthesis_stages_v3'),coulombic_efficiency_outcomes=8,CO2_adsorption_outcomes=24,EIS_outcomes=8,auxiliary_aqueous_3e_GCD_rows=parts['reported_aqueous_3e_GCD_capacitance'],auxiliary_aqueous_2e_GCD_rows=parts['reported_aqueous_2e_GCD_device_capacitance'],auxiliary_native_mineral_3e_GCD_rows=parts['reported_native_mineral_3e_GCD_capacitance'],auxiliary_author_factor2_2e_GCD_rows=parts['reported_2e_author_factor2_GCD_capacitance'],auxiliary_independent_DOI_groups=len({r['source_group'] for r in aux}),auxiliary_purpose_reviewed_input_rows=len(aux),new_training_admissions=0,formal_cycling_admissions=0,model_fits=0,all_literature_fully_utilized=False,scope_note='Four distinct capacitance tasks are never concatenated. Numeric cells/repeated reports are not independent papers or new cycling admissions. Source-group counts describe documented provenance, not proof of statistical independence.')
    from data.literature_v4 import open_literature_database,PROFILES
    from data.cycling_db import open_database
    digest=sha(DB)
    with open_literature_database(DB,digest) as db,open_database() as cy:
        profiles={p:db.auxiliary_feature_rows(p) for p in PROFILES}
        main=cy.fetch('reported_3e').rows
        check('cycling_main_43_31',len(main)==43 and len({r['source_group'] for r in main})==31)
        expected={'3e':47,'2e_device':5,'native_mineral_3e':5,'2e_author_factor2':6}
        for p,rows in profiles.items():
            check('purpose_count_'+p,len(rows)==expected[p])
            weights=Counter(r['source_group'] for r in rows)
            for r in rows:
                r['source_balanced_weight']=1/weights[r['source_group']]
                check('positive_target_'+r['observation_id'],math.isfinite(r['capacitance_F_g']) and r['capacitance_F_g']>0)
                check('protocol_bound_'+r['observation_id'],r['current_A_g'] is not None and r['concentration_mol_L'] is not None)
                check('no_outcome_features_'+r['observation_id'],not any('retention' in k or 'coulombic' in k or 'resistance' in k or 'adsorption' in k for k in r))
                for k,v in r.items():
                    if k.endswith('_is_missing'):check('mask_'+r['observation_id']+'_'+k,v==(r[k.removesuffix('_is_missing')] is None))
            for source in weights:check('source_weight_'+p+source,abs(sum(r['source_balanced_weight'] for r in rows if r['source_group']==source)-1)<1e-12)
            buf=io.StringIO(newline='');writer=csv.DictWriter(buf,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows);text=buf.getvalue();path=OUT/('auxiliary_'+p+'.csv')
            if (OUT/'merge_manifest.json').exists():
                with path.open('r',encoding='utf8',newline='') as f:
                    if f.read()!=text:raise AssertionError('sealed_csv_'+p)
            else:
                with path.open('w',encoding='utf8',newline='') as f:f.write(text)
        check('four_targets',len({r['target_name'] for rows in profiles.values() for r in rows})==4)
        check('HAC1Ag_not_selected',all(r['current_A_g']!=1 for r in profiles['native_mineral_3e']))
        check('WPC_correct_stage',all(r['activation_temperature_C']==800 and r['carbonization_temperature_C']==600 for r in profiles['3e'] if r['doi']==W))
        wpc=next(r for r in profiles['3e'] if r['doi']==W and r['sample_name']=='WPC600-4');check('SI_precision_explicit',wpc['micropore_volume_cm3_g']==.4797)
        check('EDX_not_XPS',all(r['XPS_C_at_pct'] is None for r in profiles['3e'] if r['doi']==W))
        check('native_mineral_not_purecarbon',not any(r['doi']==H for r in profiles['3e']))
        all_aux=[r for rows in profiles.values() for r in rows];sources=sorted({r['source_group'] for r in all_aux});folds=[]
        for source in sources:
            hold=[r for r in all_aux if r['source_group']==source];train=[r for r in all_aux if r['source_group']!=source]
            check('whole_source_'+source,not {r['source_group'] for r in hold}&{r['source_group'] for r in train})
            folds.append(dict(heldout_source=source,auxiliary_train_rows=len(train),auxiliary_validation_rows=len(hold),all_capacitance_reports_quarantined=sum(r['source_group']==source for r in db.capacitances()),cycling_candidates_quarantined=sum(r['record']['source_group']==source for r in db.tests()),other_outcomes_quarantined=sum(db.connection.execute('select doi from materials where material_key=?',(r['material_key'],)).fetchone()[0]==source.removeprefix('doi:') for r in db.outcomes()),all_same_source_labels_must_be_excluded_from_pretraining=True,actual_model_fit=False))
        input_report=dict(status='passed',profile_rows={p:len(r) for p,r in profiles.items()},profile_sources={p:len({x['source_group'] for x in r}) for p,r in profiles.items()},source_folds=folds,missingness_by_profile={p:{k:sum(r[k] is None for r in rows) for k in rows[0] if any(r[k] is None for r in rows)} for p,rows in profiles.items()},purpose_sufficiency='Matrix reading/masks/group isolation verified; no independent model validation or claimed error reduction.',scientific_goal_complete=False,model_fits=0)
    check('read_only_preflight',sha(DB)==digest)
    report=dict(status='passed',checks=len(checks),check_names=checks,model_fits=0,scientific_goal_complete=False)
    sealed=(OUT/'merge_manifest.json').exists()
    for name,value in [('summary.json',summary),('verification.json',report),('auxiliary_input_preflight.json',input_report)]:
        if sealed:
            if json.loads((OUT/name).read_text('utf8'))!=value:raise AssertionError('sealed_report_'+name)
        else:write(OUT/name,value)
    if sealed:
        for item in json.loads((OUT/'merge_manifest.json').read_text('utf8'))['outputs']:
            if sha(ROOT/item['path'])!=item['sha256']:raise AssertionError('sealed_hash_'+item['path'])
    print(json.dumps(dict(status='passed',checks=report['checks'],summary=summary),ensure_ascii=False))

if __name__=='__main__':
    verify()
    addendum=json.loads((OUT/'addendum_manifest.json').read_text('utf8'))
    assert sha(OUT/'merge_manifest.json')==addendum['primary_manifest_sha256']
    for item in addendum['outputs']:
        assert sha(ROOT/item['path'])==item['sha256'],item['path']
    print(json.dumps(dict(postseal_csv_checks=4,addendum_payload_hashes=len(addendum['outputs']),primary_payload_hashes=len(json.loads((OUT/'merge_manifest.json').read_text('utf8'))['outputs']),status='passed')))
