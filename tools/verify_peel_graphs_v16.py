"""Verify graph coordinates, author anchors, deduplication and explicit input modes."""
from pathlib import Path
from contextlib import closing
import collections,csv,json,math,sqlite3,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tools'))
from extract_peel_graphs_v16 import OUT,DB,PARENT,PSHA,PE,DA,AXES,IMAGES,sha,write,ro,capture,at_y
from data.literature_v16 import open_literature_database,FIELDS16

def verify(prepare=False):
    digest=sha(DB);checks=[]
    def ck(name,value):assert value,name;checks.append(name)
    spec=json.loads((OUT/'curation_spec.json').read_text('utf8'));ck('parentSHA',sha(PARENT)==PSHA)
    for entry in json.loads((OUT/'protected_inputs.json').read_text('utf8'))['files']:ck('protected:'+entry['path'],sha(ROOT/entry['path'])==entry['sha256']and(ROOT/entry['path']).stat().st_size==entry['bytes'])
    for entry in json.loads((PARENT.parent/'merge_manifest.json').read_text('utf8'))['outputs']:ck('parent_manifest:'+entry['path'],sha(ROOT/entry['path'])==entry['sha256'])
    recomputed={r['reading_id']:r for r in capture()};ck('95_original_pixel_captures',len(recomputed)==95 and len(spec['readings'])==95)
    for r in spec['readings']:
        for k,v in recomputed[r['reading_id']].items():ck('pixel_reading:'+r['reading_id']+':'+k,r[k]==v)
        ck('y_and_bounds:'+r['reading_id'],math.isclose(r['y_value'],at_y(r['axis'],r['pixel_y']))and math.isclose(r['y_lower_bound'],at_y(r['axis'],r['pixel_y']+4))and math.isclose(r['y_upper_bound'],at_y(r['axis'],r['pixel_y']-4)))
        ck('no_interpolation_or_retention:'+r['reading_id'],r['kind']=='bounded_original_marker'and not r['retention_point_admitted']and r['y_lower_bound']<=r['y_value']<=r['y_upper_bound'])
    with closing(ro(PARENT))as old,closing(ro(DB))as c:
        old.row_factory=c.row_factory=sqlite3.Row;ck('integrity',[r[0]for r in c.execute('pragma integrity_check')]==['ok']);ck('foreign_keys',not c.execute('pragma foreign_key_check').fetchall())
        changed={'source_documents','reviewed_tables','table_source_links','transcribed_rows','transcription_origins_v7','extraction_units_v3','curve_samples_v8','capacitance_observations'}
        for t in [r[0]for r in old.execute("select name from sqlite_master where type='table'and name not like'sqlite_%'")]:
            before={tuple(r)for r in old.execute('select *from "'+t+'"')};after={tuple(r)for r in c.execute('select *from "'+t+'"')};ck('parent_rows_exact:'+t,before<=after if t in changed else before==after)
        for t,n in [('source_documents',3),('reviewed_tables',4),('extraction_units_v3',4),('curve_samples_v8',95),('capacitance_observations',95)]:ck('exact_delta:'+t,c.execute('select count(*)from '+t).fetchone()[0]-old.execute('select count(*)from '+t).fetchone()[0]==n)
        ck('raw_queue959_810_untouched',c.execute('select count(*)from raw_table_queue').fetchone()[0]==959 and c.execute("select count(*)from raw_table_queue where review_state='automatic_candidate_unreviewed'").fetchone()[0]==810)
        for r in c.execute('select x.*,p.reading_id,p.record_json from capacitance_observations x join purpose_reviews_v16 p using(observation_id)'):
            reading=next(q for q in spec['readings']if q['reading_id']==r['reading_id']);cond=json.loads(r['conditions_json']);link=json.loads(r['record_json']);ck('DB_graph_binding:'+r['observation_id'],r['value']==reading['y_value']and math.isclose(float(r['raw_value']),r['value'],abs_tol=1e-9)and r['current_A_g']==reading['x_value']and r['system']=='3E'and r['method']=='GCD'and r['unit']=='F/g'and r['training_eligible']==0)
            ck('DB_conditions:'+r['observation_id'],cond['current_mass_basis']=='author_reported_unknown_not_inferred'and cond['target_stage']=='fresh_reported_GCD_rate_test'and cond['physical_test_group']==reading['physical_test_group']and link['lower_bound']==reading['y_lower_bound']and link['upper_bound']==reading['y_upper_bound'])
    from data.literature_v15 import open_literature_database as open_old
    with open_literature_database(DB,digest)as d,open_old(PARENT,PSHA)as old:
        for p,n in [('3e',176),('2e_device',5),('native_mineral_3e',5),('2e_author_factor2',6)]:ck('ordinary_API_unchanged:'+p,d.auxiliary_gcd(p)==old.auxiliary_gcd(p)and d.auxiliary_feature_rows(p)==old.auxiliary_feature_rows(p)and len(d.auxiliary_gcd(p))==n)
        ck('batch15matrix_unchanged',d.batch15_matrix()==old.batch15_matrix())
        for mode in ['author_exact','point_mixed','interval_mixed','figure_only']:ck('v14_mode_exact:'+mode,d.furfural_rate_matrix(mode)==old.furfural_rate_matrix(mode))
        from data.literature_v12 import TARGETS12
        for t in TARGETS12:ck('v12_targets:'+t,d.batch12_inputs(t)==old.batch12_inputs(t))
        ck('residue_and_reference_exact',d.template_residue_matrix()==old.template_residue_matrix()and d.interface_reference_reports()==old.interface_reference_reports()and d.wettability_series_v13()==old.wettability_series_v13())
        modes={};old20={r['observation_id']:r for r in old.auxiliary_gcd('3e')if r['doi']in [PE,DA]}
        for mode,counts in [('author_exact',[20,16,4]),('point_mixed',[95,80,15]),('figure_only',[94,80,14])]:
            for scope,n in zip(['all','peel','date'],counts):
                m=d.batch16_rate_matrix(mode,scope);rows=d.batch16_rate_inputs(mode,scope);ck('mode_count:'+mode+scope,len(m['y'])==len(rows)==n and len(m['observation_ids'])==len(set(m['observation_ids']))and len(m['physical_test_groups'])==len(set(m['physical_test_groups'])))
                ck('balance_and_masks:'+mode+scope,all(math.isclose(sum(w for g,w in zip(m['groups'],m['sample_weight'])if g==f),1)for f in set(m['groups']))and all(flag==(v is None)for xx,mask in zip(m['X'],m['missing_mask'])for v,flag in zip(xx,mask)))
                ck('no_fit_no_impute:'+mode+scope,not m['imputed']and not m['training_authorized']and m['estimators_fitted']==0)
                for r in rows:
                    if r['target_value_kind'].startswith('author_reported'):
                        ck('author_anchor_original_ID_value:'+mode+scope+r['observation_id'],r['observation_id']in old20 and r['target_value']==old20[r['observation_id']]['value'])
                    else:ck('approximate_bound_semantics:'+mode+scope+r['observation_id'],r['target_lower_bound']<=r['target_value']<=r['target_upper_bound']and 'not experimental'in r['target_bounds_kind'])
                modes[mode+'_'+scope]=dict(rows=n,source_families=m['source_families'],approximate=sum(r['target_value_kind']=='bounded_original_figure'for r in rows),model_fits=0)
        exact=d.batch16_rate_inputs();mixed=d.batch16_rate_inputs('point_mixed');ck('20_oldIDs75_newconditions',set(r['observation_id']for r in exact)==set(old20)and len({r['observation_id']for r in mixed}-set(old20))==75)
        anchors=[r for r in spec['readings']if r['author_exact_observation_id']];ck('19_author_graph_anchors_in_bounds',len(anchors)==19 and all(r['author_anchor_within_graph_envelope']for r in anchors))
        six=[r for r in spec['readings']if r['doi']==DA and r['x_value']==6];ck('6Ag_duplicate_not_two_conditions',len(six)==2 and max(r['y_lower_bound']for r in six)<=min(r['y_upper_bound']for r in six)and next(r for r in mixed if r['doi']==DA and r['current_A_g']==6)['graph_reading_id'].startswith('LP16_Fig5f'))
        ck('f_selected_by_resolution',abs((AXES['5f']['yp1']-AXES['5f']['yp0'])/(AXES['5f']['y1']-AXES['5f']['y0']))>abs((AXES['5e']['yp1']-AXES['5e']['yp0'])/(AXES['5e']['y1']-AXES['5e']['y0'])))
        ck('ten_peel_samples_have8conditions',collections.Counter(r['sample_name']for r in d.batch16_rate_inputs('point_mixed','peel'))==dict.fromkeys([a+'-'+str(t)for a in ['PAC','SAC']for t in [600,700,800,900,1000]],8))
        expanded=d.expanded_graph_3e_inputs();matrix=d.expanded_graph_3e_matrix();ck('expanded251_18_DOI',len(expanded)==len(matrix['y'])==251 and matrix['source_families']==18 and len(set(matrix['observation_ids']))==251)
        base=d.auxiliary_gcd('3e');ck('expanded_old176targets_preserved',[(r['observation_id'],r['target_value'])for r in expanded[:176]]==[(r['observation_id'],r['value'])for r in base])
        ck('75new_approx_rows_only',all(r['target_value_kind']=='bounded_original_figure'for r in expanded[176:])and{r['source_group']for r in expanded[176:]}=={'doi:'+PE,'doi:'+DA})
        ck('expanded_source_weights',all(math.isclose(sum(w for g,w in zip(matrix['groups'],matrix['sample_weight'])if g==f),1)for f in set(matrix['groups'])))
        for i,r in enumerate(expanded):
            if r['doi']!=DA:continue
            vals=dict(zip(matrix['feature_names'],matrix['X'][i]));ck('Date_unknowns_and_models:'+r['observation_id'],vals['Raman_ID_IG']is None and vals['carbonization_temperature_C']is None and vals['total_pore_volume_cm3_g']is None and vals['DFT_pore_volume_cm3_g']in [.401,.452]and vals['DA_micropore_volume_cm3_g']in [.416,.486])
        ck('no_new_cycle_or_full_source',len(d.tests())==len(old.tests())==71 and all(not r['record']['full_source_review_complete']for r in d.batch16_sources()))
        for export_name,rows,mat in [('rate_inputs_v16',mixed,d.batch16_rate_matrix('point_mixed')),('expanded_3e_inputs_v16',expanded,matrix)]:
            if prepare:
                assert not(OUT/'merge_manifest.json').exists()
                fields=['observation_id','doi','sample','target_F_g','target_lower_F_g','target_upper_F_g','target_kind','source_family','physical_test_group','source_weight','source_path','source_sha256']+FIELDS16
                with(OUT/(export_name+'.csv')).open('w',encoding='utf-8-sig',newline='')as f:
                    writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
                    for i,r in enumerate(rows):writer.writerow(dict(observation_id=r['observation_id'],doi=r['doi'],sample=r['sample_name'],target_F_g=r['target_value'],target_lower_F_g=r.get('target_lower_bound'),target_upper_F_g=r.get('target_upper_bound'),target_kind=r['target_value_kind'],source_family=mat['groups'][i],physical_test_group=mat['physical_test_groups'][i],source_weight=mat['sample_weight'][i],source_path=r['source_path'],source_sha256=r['source_sha256'],**dict(zip(FIELDS16,mat['X'][i]))))
            with(OUT/(export_name+'.csv')).open(encoding='utf-8-sig',newline='')as f:export=list(csv.DictReader(f))
            ck('CSV_labels_and_missing:'+export_name,len(export)==len(rows)and all(e['observation_id']==r['observation_id']and float(e['target_F_g'])==r['target_value']and all((e[field]=='')==(value is None)for field,value in zip(FIELDS16,mat['X'][i]))for i,(e,r)in enumerate(zip(export,rows))))
        ck('bounds_at_four_different_scales',len({round(r['y_uncertainty'],6)for r in spec['readings']})==4)
    ck('read_only_DB_hash',sha(DB)==digest)
    summary=json.loads((PARENT.parent/'summary.json').read_text('utf8'))
    for k in list(summary):
        if k.startswith('new_')and isinstance(summary[k],int):summary[k]=0
    summary.update(capacitance_records=951,numeric_capacitance_values=947,reviewed_evidence_units=353,actual_distinct_reviewed_table_keys=339,extraction_units_v3_count=322,cumulative_bounded_curve_samples=277,cumulative_curve_groups=43,curve_sampling_panels=13,new_bounded_curve_samples=95,new_curve_groups=11,new_capacitance_reports=95,new_nominal_graph_conditions=94,new_approximate_conditions_beyond_author_points=75,expanded_3e_with_graph_rows=251,expanded_3e_with_graph_DOI_groups=18,scope_note='Two existing sources deepened:95rawcapturereports/94nominalgraphconditions;19authoranchors plusoneCO2control yield20exact or95mixedconditions.75netnewapproximateconditions,ordinary176unchanged; no full-source completion or fit')
    report=dict(status='passed',database_sha256=digest,check_count=len(checks),checks=checks,raw_graph_captures=95,nominal_graph_conditions=94,author_anchor_conditions=19,existing_exact_inputs=20,mixed_inputs=95,new_approximate_conditions=75,expanded_graph_3e_rows=251,expanded_graph_3e_sources=18,ordinary_3e_rows=176,formal_cycling_admissions=0,model_fits=0,scientific_goal_complete=False)
    preflight=dict(modes=modes,expanded={k:v for k,v in matrix.items()if k not in ['X','missing_mask','y','y_lower','y_upper','groups','sample_weight','observation_ids','physical_test_groups','categorical_protocol','target_value_kinds']},expanded_rows=len(matrix['y']),old176unchanged=True,source_folds_eligible_for_simulation_only=True)
    for name,val in [('verification',report),('summary',summary),('model_inputs_preflight',preflight)]:
        if prepare:write(OUT/(name+'.json'),val)
        else:assert json.loads((OUT/(name+'.json')).read_text('utf8'))==val,name
    if not prepare and(OUT/'merge_manifest.json').exists():
        for p in json.loads((OUT/'merge_manifest.json').read_text('utf8'))['outputs']:assert sha(ROOT/p['path'])==p['sha256']
    print(json.dumps({k:v for k,v in report.items()if k!='checks'},ensure_ascii=False))

def seal():
    assert not(OUT/'merge_manifest.json').exists();verify(False)
    from verify_peel_graph_chain_v16 import run
    run(False)
    paths=[p for p in OUT.rglob('*')if p.is_file()]+[ROOT/'data/literature_v16.py',ROOT/'tools/extract_peel_graphs_v16.py',ROOT/'tools/verify_peel_graphs_v16.py',ROOT/'tools/verify_peel_graph_chain_v16.py'];write(OUT/'merge_manifest.json',dict(version='literature_pool_v16',parent_sha256=PSHA,outputs=[dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p),bytes=p.stat().st_size)for p in sorted(paths)],model_fits=0,formal_cycling_admissions=0,scientific_goal_complete=False));write(ROOT/'data/current_literature.json',dict(version='literature_pool_v16',directory=OUT.relative_to(ROOT).as_posix(),database_file=DB.name,sha256=sha(DB),api_module='data.literature_v16',scope='Full rate-marker panels for tenpeel/seed carbons and datefrond;75netnewboundedconditions,explicit251graph-expanded3E cohort;ordinaryprofilesunchanged,no full-source completion or fit'))

if __name__=='__main__':
    if len(sys.argv)!=2 or sys.argv[1]not in ['prepare','verify','seal']:raise SystemExit('prepare/seal on new unsealed release; default verify read-only')
    if sys.argv[1]=='seal':seal()
    else:verify(sys.argv[1]=='prepare')
