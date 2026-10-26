"""Original-pixel/label/interval checks and immutable parent/API verification."""
from pathlib import Path
from contextlib import closing
import csv,json,math,sqlite3,sys,xml.etree.ElementTree as E,zipfile
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tools'))
from extract_furfural_curves_v14 import OUT,DB,PARENT,PSHA,SOURCE,SOURCE_SHA,IMAGE,ASSETS,FU,CURRENTS,OCCLUDED,sha,write,ro,clean,color_signal


def verify(prepare=False):
    from data.literature_v14 import open_literature_database
    from data.literature_v13 import open_literature_database as parentapi
    from data.literature_v12 import TARGETS12
    checks=[]
    def ck(name,passed):
        if not passed:raise AssertionError(name)
        checks.append(name)
    digest=sha(DB);spec=json.loads((OUT/'curation_spec.json').read_text('utf8'))
    ck('source_XML_pin',sha(SOURCE)==SOURCE_SHA);ck('parent_pin',sha(PARENT)==PSHA)
    for p in json.loads((OUT/'protected_inputs.json').read_text('utf8')):ck('protected:'+p['path'],sha(ROOT/p['path'])==p['sha256'])
    for p in json.loads((PARENT.parent/'merge_manifest.json').read_text('utf8'))['outputs']:ck('parent_payload:'+p['path'],sha(ROOT/p['path'])==p['sha256'])
    archive=spec['original_figure_package'];ck('original_archive',sha(ROOT/archive['path'])==archive['sha256'])
    with zipfile.ZipFile(ROOT/archive['path'])as z:
        for f in spec['figures']:ck('exact_original_member:'+str(f['figure_number']),(ROOT/f['path']).read_bytes()==z.read(Path(f['path']).name))
    original=E.parse(SOURCE).getroot();body=original.findall('./body//p');ck('source_DOI',{a.text.lower()for a in original.findall('./front/article-meta/article-id')if a.get('pub-id-type')=='doi'}=={FU})
    ck('explicit_control_nothing_added','with nothing added'in clean(body[11]));ck('all_six_current_labels',set(CURRENTS)=={.5,1,2,5,10,20});ck('no_cyclelife_claim','rate performance'in clean(body[34]))
    im=Image.open(IMAGE).convert('RGB');ck('original_dimensions',im.size==(752,939))
    for panel,x0,x1 in [('c',53,350),('d',442,738)]:
        for y in [343,581]:ck('axis_original_pixels:'+panel+str(y),sum(max(im.getpixel((x,y)))<185 for x in range(x0,x1))>285)
    index={r['reading_id']:r for r in spec['readings']};ck('54_unique_capture_IDs',len(index)==54);ck('48_primary_nominal_conditions',len(spec['primary_reading_ids'])==48)
    for r in spec['readings']:
        name=r['reading_id'];ck('nominal_current:'+name,r['x_value']in CURRENTS and r['x_name']=='reported_current_A_g'and r['retention_point_admitted']is False)
        xp=r['axis']['x_pixel0']+(r['axis']['x_pixel1']-r['axis']['x_pixel0'])*r['x_value']/20;ck('x_mapping:'+name,r['pixel_x']==xp and r['selected_marker_column']==round(xp))
        candidates=[]
        for y in range(r['manual_roi_y'][0],r['manual_roi_y'][1]+1):
            xs=[x for x in range(r['pixel_x_extent'][0],r['pixel_x_extent'][1]+1)if color_signal(r['color'],im.getpixel((x,y)))]
            if xs:candidates.append(dict(y=y,matching_pixels=len(xs),x_min=min(xs),x_max=max(xs),horizontal_span=max(xs)-min(xs)+1))
        ck('original_colour_support:'+name,candidates==r['color_candidates'])
        if r['kind']=='bounded_marker_reading':
            ck('observed_marker:'+name,candidates and max(c['horizontal_span']for c in candidates)>=3)
            width=max(c['horizontal_span']for c in candidates);ys=[c['y']for c in candidates if c['horizontal_span']==width];yp=sum(ys)/len(ys);value=40+(581.5-yp)*120/239;bound=4*120/239
            ck('independent_pixel_recalculation:'+name,r['pixel_y']==yp and r['y_value']==value and r['y_uncertainty']==bound and math.isclose(r['y_lower_bound'],value-bound,abs_tol=1e-12)and math.isclose(r['y_upper_bound'],value+bound,abs_tol=1e-12))
        else:
            ck('only_declared_occlusions:'+name,(r['panel'][-1],r['sample'],r['x_value'])in OCCLUDED and not candidates and r['y_value']is None and r['pixel_y']is None and not r['point_loss_eligible'])
            front=index[r['occlusion_origin_reading_id']];ck('occlusion_no_point_or_midpoint:'+name,front['sample']==r['occluding_sample']and r['y_lower_bound']<r['y_upper_bound']and r['pixel_y_extent']==[front['pixel_y']-8,front['pixel_y']+8])
            ck('occlusion_pixel_bound_recalculation:'+name,r['y_lower_bound']==40+(581.5-r['pixel_y_extent'][1])*120/239 and r['y_upper_bound']==40+(581.5-r['pixel_y_extent'][0])*120/239)
        ck('positive_ordered_bounds:'+name,0<r['y_lower_bound']<r['y_upper_bound'])
    for current in CURRENTS:
        pair=[r for r in spec['readings']if r['sample']=='PC900-1'and r['x_value']==current];ck('duplicate_panels_overlap:'+str(current),len(pair)==2 and max(r['y_lower_bound']for r in pair)<=min(r['y_upper_bound']for r in pair))
    with closing(ro(DB))as c:
        c.row_factory=sqlite3.Row;ck('integrity',c.execute('pragma integrity_check').fetchone()[0]=='ok');ck('foreignkeys',not c.execute('pragma foreign_key_check').fetchall());c.execute('attach database ?as parent',(PARENT.as_uri()+'?mode=ro',))
        changed={'source_documents','reviewed_tables','table_source_links','extraction_units_v3','transcribed_rows','transcription_origins_v7','curve_samples_v8','capacitance_observations','outcome_observations_v3','scientific_issues'}
        for(t,)in c.execute("select name from parent.sqlite_master where type='table'and name not like 'sqlite_%'"):
            ck('parent_rows_exact_retained:'+t,not c.execute('select *from parent.'+t+' except select *from main.'+t).fetchall())
            if t not in changed:ck('no_extra_rows_in_unchanged_table:'+t,c.execute('select count(*)from parent.'+t).fetchone()[0]==c.execute('select count(*)from main.'+t).fetchone()[0])
        deltas={'source_documents':14,'reviewed_tables':6,'table_source_links':6,'extraction_units_v3':6,'transcribed_rows':86,'transcription_origins_v7':86,'curve_samples_v8':54,'capacitance_observations':48,'outcome_observations_v3':19,'scientific_issues':8}
        for t,n in deltas.items():ck('only_declared_delta:'+t,c.execute('select count(*)from main.'+t).fetchone()[0]-c.execute('select count(*)from parent.'+t).fetchone()[0]==n)
        for t in ['material_facts','capacitance_observations','outcome_observations_v3','test_candidates','raw_table_queue']:ck('raw_no_auto_qualification:'+t,c.execute('select count(*)from '+t+' where training_eligible!=0 or training_eligible is null').fetchone()[0]==0)
        ck('959_queue_exact',c.execute('select count(*)from raw_table_queue').fetchone()[0]==959 and not c.execute('select *from raw_table_queue except select *from parent.raw_table_queue').fetchall());ck('813_untouched',c.execute("select count(*)from raw_table_queue where review_state='automatic_candidate_unreviewed'").fetchone()[0]==813)
        ck('48_explicit_purpose_reviews',c.execute('select count(*)from purpose_reviews_v14').fetchone()[0]==48)
        for review in c.execute('select *from purpose_reviews_v14'):
            r=index[review['reading_id']];cap=dict(c.execute('select *from capacitance_observations where observation_id=?',(review['observation_id'],)).fetchone());cond=json.loads(cap['conditions_json']);record=json.loads(review['record_json'])
            ck('raw_point_value:'+r['reading_id'],cap['value']==r['y_value']and cap['current_A_g']==r['x_value']and cap['unit']=='F/g'and cap['method']=='GCD'and cap['system']=='3E'and cap['concentration_mol_L']==6)
            ck('test_bound_protocol:'+r['reading_id'],cond['voltage_lower_V']==-1 and cond['voltage_upper_V']==0 and cond['reference_electrode']=='Hg/HgO'and cond['current_mass_basis']=='author_reported_unknown_not_inferred')
            ck('interval_scope:'+r['reading_id'],record['lower_bound']==r['y_lower_bound']and record['upper_bound']==r['y_upper_bound']and bool(review['point_input_ready'])==(cap['value']is not None)and review['interval_input_ready']==1)
            ck('raw_transcription:'+r['reading_id'],cap['raw_value']==json.loads(c.execute('select cells_json from transcribed_rows where table_key=?and row_ordinal=?',(cap['table_key'],cap['row_ordinal'])).fetchone()[0])[cap['column_ordinal']])
        old=json.loads((PARENT.parent/'summary.json').read_text('utf8'));summary=dict(old);count=lambda t:c.execute('select count(*)from '+t).fetchone()[0]
        summary.update(cumulative_reviewed_source_publications=37,cumulative_materials=count('materials'),cumulative_selected_material_cells=count('material_facts'),cumulative_numeric_material_facts=c.execute('select count(*)from material_facts where value is not null').fetchone()[0],new_materials=0,new_numeric_material_facts=0,reviewed_evidence_units=old['reviewed_evidence_units']+6,distinct_database_table_keys=count('reviewed_tables'),database_extraction_units_v3=count('extraction_units_v3'),capacitance_records=count('capacitance_observations'),numeric_capacitance_values=c.execute('select count(*)from capacitance_observations where value is not null').fetchone()[0],unreported_capacitance_cells=2,interval_only_capacitance_cells=2,null_capacitance_cells=4,scientific_issues=count('scientific_issues'),response_outcomes=count('outcome_observations_v3'),new_source_response_records=19,new_capacitance_reports=48,new_response_records=19,new_own_main_tables=0,new_own_SI_tables=0,new_mixed_comparison_main_tables=0,new_foreign_comparison_main_tables=0,new_bounded_curve_samples=54,new_numeric_curve_samples=52,new_interval_only_curve_samples=2,new_curve_groups=9,curve_sampling_panels=old['curve_sampling_panels']+2,cumulative_bounded_curve_samples=count('curve_samples_v8'),cumulative_numeric_curve_samples=180,cumulative_interval_only_curve_samples=2,cumulative_curve_groups=32,batch14_series_annotations=18,batch14_figure_scope_reviews=12,batch14_author_exact_conditions=4,batch14_point_mixed_conditions=46,batch14_interval_mixed_conditions=48,batch14_net_new_point_conditions_beyond_existing4=42,scope_note='One existing Furfural source deepened:54 curve captures/48 nominal conditions,46 numeric+2 interval-only primary labels;18 collective/stage annotations; no new material/source/cycle and no full-source completion.')
        summary['reviewed_evidence_units_definition']='Cumulative declared units328, distinct table keys314/extraction_units_v3 297; physical table units172 unchanged because6 new units are derived review transcriptions.'
        ck('expected_inventory',all(summary[k]==v for k,v in dict(cumulative_materials=211,cumulative_selected_material_cells=2383,cumulative_numeric_material_facts=2293,capacitance_records=832,numeric_capacitance_values=828,response_outcomes=2528,scientific_issues=144,distinct_database_table_keys=314,database_extraction_units_v3=297,cumulative_bounded_curve_samples=182).items()))
    with open_literature_database(DB,digest)as d,parentapi(PARENT,PSHA)as old:
        for profile in ['3e','2e_device','native_mineral_3e','2e_author_factor2']:ck('old_aux_exact:'+profile,d.auxiliary_feature_rows(profile)==old.auxiliary_feature_rows(profile))
        for t in TARGETS12:ck('old_target12_exact:'+t,d.batch12_inputs(t)==old.batch12_inputs(t)and d.batch12_matrix(t)==old.batch12_matrix(t))
        ck('old_residue_exact4',d.template_residue_gcd_inputs()==old.template_residue_gcd_inputs()and d.template_residue_matrix()==old.template_residue_matrix())
        ck('old_ref24_exact',d.interface_reference_reports()==old.interface_reference_reports());ck('old_wetting_exact',d.wettability_series_v13()==old.wettability_series_v13());ck('old_report_identity_exact',d.report_groups_v13()==old.report_groups_v13())
        ids={r['reading_id']for r in old.sampled_curves()};ck('old128_curves_exact',[r for r in d.sampled_curves()if r['reading_id']in ids]==old.sampled_curves())
        ck('old15_freezes_exact',d.legacy_feature_conflicts()==old.legacy_feature_conflicts());ck('old_families_exact',d.source_relations()==old.source_relations());ck('old_DES_exact',all(d.des_reported_inputs(t)==old.des_reported_inputs(t)for t in ['retention','capacitance']))
        matrices={}
        for mode,n,missing in [('author_exact',4,0),('point_mixed',46,0),('interval_mixed',48,2),('figure_only',46,0)]:
            rows=d.furfural_rate_inputs(mode);m=d.furfural_rate_matrix(mode);matrices[mode]=m;ck('explicit_mode_counts:'+mode,len(rows)==n and len(m['y'])==n and sum(v is None for v in m['y'])==missing)
            ck('explicit_mode_masks:'+mode,all(mask==(v is None)for row,masks in zip(m['X'],m['missing_mask'])for v,mask in zip(row,masks)))
            ck('source_weight_one:'+mode,abs(sum(m['sample_weight'])-1)<1e-12 and m['source_families']==1 and not m['independent_source_validation_possible_alone'])
            ck('no_fit_or_impute:'+mode,m['estimators_fitted']==0 and not m['imputed']and m['point_estimator_ready']==(missing==0)and m['requires_interval_aware_loss']==(missing>0))
            ck('no_responses_or_unknown_basis_X:'+mode,not{'author_S_wt_pct_method_unspecified','water_contact_angle_time_unspecified_deg','rate_retention_pct','capacitance_F_g','EIS_Rs','source_group','doi'}&set(m['feature_names']))
            for r in rows:
                ck('whole_source_and_nominal_group:'+mode+r['observation_id'],d.is_quarantined_source(r['source_group'],[r['source_family_group']])and r['conditions']['physical_test_group']==r['physical_test_group'])
                ck('bounded_not_statistical:'+mode+r['observation_id'],r['target_lower_bound']<=r['target_upper_bound']and not r['ordinary_biomass_carbon_profile'])
                if r['sample_name']=='FR900':
                    j=m['observation_ids'].index(r['observation_id']);ck('control_zero_recipe_only:'+mode+str(r['current_A_g']),m['X'][j][-2:]==[0,0])
            if mode=='interval_mixed':ck('no_midpoint_fill',all(value is None for value,mask in zip(m['y'],m['point_loss_mask'])if not mask))
        exactids={r['observation_id']for r in old.template_residue_gcd_inputs()};ck('same_four_exact_observation_IDs',{r['observation_id']for r in d.furfural_rate_inputs('author_exact')}==exactids)
        for mode,name,n in [('point_mixed','point_inputs_v14.csv',46),('interval_mixed','interval_inputs_v14.csv',48)]:
            with(OUT/name).open(encoding='utf8',newline='')as f:export=list(csv.DictReader(f))
            api=d.furfural_rate_inputs(mode);ck('CSV_scoped_rows:'+mode,len(export)==n and{r['observation_id']for r in export}=={r['observation_id']for r in api})
            expected={r['observation_id']:r for r in api}
            for row in export:
                r=expected[row['observation_id']];value=None if row['target_F_g']==''else float(row['target_F_g'])
                ck('CSV_target_null_and_bounds:'+mode+row['observation_id'],value==r['target_value']and float(row['target_lower_F_g'])==r['target_lower_bound']and float(row['target_upper_F_g'])==r['target_upper_bound'])
            ck('CSV_source_weight:'+mode,abs(sum(float(r['source_balanced_weight'])for r in export)-1)<1e-12)
        ck('net42_new_point_conditions',len({r['observation_id']for r in d.furfural_rate_inputs('point_mixed')}-exactids)==42)
        ratios={r['record']['sample']:r['record']for r in d.furfural_rate_audits()};fr=ratios['FR900'];pc=ratios['PC900-0.1']
        ck('FR900_unresolved_annotation',fr['author_rate_retention_pct']==79.3 and fr['derived_figure_interval_pct'][1]<50 and fr['canonical_rate_retention_pct']is None)
        ck('point1_exact_arithmetic_dissent',pc['author_rate_retention_pct']==80.7 and math.isclose(pc['derived_from_reported_exact_capacitances_pct'],114.32/141.32*100)and pc['canonical_rate_retention_pct']is None)
        pairs=[r['record']for r in d.furfural_contributions()];ck('five_rate_contribution_pairs',[(r['scan_rate_mV_s'],r['capacitive_pct'],r['diffusion_pct'])for r in pairs]==[(5,72,29),(10,73,27),(20,76,24),(40,83,17),(60,90,10)])
        ck('printed101_not_renormalized',pairs[0]['printed_sum_pct']==101 and not pairs[0]['normalize_to100'])
        annotations=[r['record']for r in d.furfural_series_annotations()];ck('18_collective_annotations',len(annotations)==18 and all(r['not_independent_per_sample_measurements']and not r['predictor_ready']for r in annotations))
        precursor=next(r for r in annotations if r['id']=='ZnO_precursor_nominal_size');ck('precursor_not_pore_size',precursor['value']==30 and precursor['author_plusminus']==10 and'input_nanoZnO'in precursor['stage'])
        ck('12_figure_scope_not_full_source',len(d.figure_scope_reviews_v14())==12 and not d.batch14_sources()[0]['record']['full_source_review_complete'])
        ck('no_new_cycle_candidates',len(d.tests())==len(old.tests())==69)
        ck('contact_and_S_method_not_filled',all('water_contact_angle_time_unspecified_deg'not in d.canonical_material_features_v13(FU,s)['values']for s in ['PC900-0','PC900-1'])and d.canonical_material_features_v13(FU,'PC900-1')['values']['author_S_wt_pct_method_unspecified']==19.26)
    ck('read_only_DB_hash',sha(DB)==digest);report=dict(status='passed',database_sha256=digest,check_count=len(checks),checks=checks,raw_graph_reports=48,new_numeric_graph_reports=46,new_interval_graph_reports=2,point_mixed_conditions=46,net_new_point_conditions=42,interval_mixed_conditions=48,formal_cycling_admissions=0,model_fits=0,scientific_goal_complete=False)
    for name,value in [('summary',summary),('verification',report),('model_inputs_preflight',matrices)]:
        if prepare:assert not(OUT/'merge_manifest.json').exists();write(OUT/(name+'.json'),value)
        else:assert json.loads((OUT/(name+'.json')).read_text('utf8'))==value
    if not prepare and(OUT/'merge_manifest.json').exists():
        for p in json.loads((OUT/'merge_manifest.json').read_text('utf8'))['outputs']:assert sha(ROOT/p['path'])==p['sha256']
    print(json.dumps({k:v for k,v in report.items()if k!='checks'},ensure_ascii=False))


def seal():
    assert not(OUT/'merge_manifest.json').exists()
    from verify_furfural_chain_v14 import run
    run(False)
    paths=[p for p in OUT.rglob('*')if p.is_file()]+[ROOT/'data/literature_v14.py',ROOT/'tools/extract_furfural_curves_v14.py',ROOT/'tools/export_furfural_inputs_v14.py',ROOT/'tools/verify_furfural_curves_v14.py',ROOT/'tools/verify_furfural_chain_v14.py']
    write(OUT/'merge_manifest.json',dict(version='literature_pool_v14',parent_sha256=PSHA,outputs=[dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p),bytes=p.stat().st_size)for p in sorted(paths)],model_fits=0,formal_cycling_admissions=0,scientific_goal_complete=False))
    write(ROOT/'data/current_literature.json',dict(version='literature_pool_v14',directory=OUT.relative_to(ROOT).as_posix(),database_file=DB.name,sha256=sha(DB),api_module='data.literature_v14',scope='Furfural bounded rate data, explicit point/interval modes, collective spectral annotations and all12figure ledger; no full-source completion or fit'))


if __name__=='__main__':
    if len(sys.argv)!=2 or sys.argv[1]not in ['prepare','verify','seal']:raise SystemExit('prepare/seal once on unsealed release; verify read-only')
    if sys.argv[1]=='seal':seal()
    else:verify(sys.argv[1]=='prepare')
