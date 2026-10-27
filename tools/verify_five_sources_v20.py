"""Read-only scientific/lineage/old-row checks; prepare/seal only before release."""
import collections,contextlib,csv,io,json,math,sqlite3,sys,xml.etree.ElementTree as E
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tools'))
from extract_five_sources_v20 import OUT,DB,PARENT,PSHA,KEYS,OJ,RH,CO,SP,MO,sha,write,ro,number,xml_grid,clean
from data.literature_v20 import open_literature_database,TARGETS20,FIELDS20
from data.literature_v19 import open_literature_database as old_open,TARGETS19

def verify(prepare=False):
    if prepare:assert not(OUT/'merge_manifest.json').exists()
    checks=[];digest=sha(DB);spec=json.loads((OUT/'curation_spec.json').read_text('utf8'));docs={d['key']:d for d in spec['documents']}
    def ck(name,ok):assert ok,name;checks.append(name)
    ck('parent_hash',sha(PARENT)==PSHA)
    for record in json.loads((OUT/'protected_inputs.json').read_text('utf8'))['files']:ck('original:'+record['path'],sha(ROOT/record['path'])==record['sha256'])
    for record in json.loads((PARENT.parent/'merge_manifest.json').read_text('utf8'))['outputs']:ck('old_release:'+record['path'],sha(ROOT/record['path'])==record['sha256'])
    for t in spec['tables']:
        root=E.parse(ROOT/docs[t['document']]['path']).getroot();tt=next(x for x in root.findall('.//table-wrap')if x.get('id')==t['id']);ck('native_grid:'+t['id']+t['doi'],xml_grid(tt)==t['grid'])
    for f in spec['figures']:
        root=E.parse(ROOT/docs[KEYS[f['doi']]]['path']).getroot();fig=next(x for x in root.findall('.//fig')if x.get('id')==f['xml_id'])
        ck('actual_figure_label_href:'+f['doi']+str(f['figure_number']),clean(fig.find('label'))==f['printed_label']and fig.find('.//graphic').get('{http://www.w3.org/1999/xlink}href')==f['graphic_href'])
        ck('all_equivalent_original_images:'+f['doi']+str(f['figure_number']),all(sha(ROOT/p)==docs[f['document']]['sha256']for p in f['equivalent_local_paths']))
    with contextlib.closing(ro(DB))as c,contextlib.closing(ro(PARENT))as p:
        c.row_factory=p.row_factory=sqlite3.Row;ck('SQLite_integrity',[r[0]for r in c.execute('pragma integrity_check')]==['ok']);ck('foreign_keys',not c.execute('pragma foreign_key_check').fetchall())
        changed=[]
        for name, in p.execute("select name from sqlite_master where type='table'and name not like'sqlite_%'"):
            if name=='raw_table_queue':
                before={r['table_id']:dict(r)for r in p.execute('select *from raw_table_queue')}
                for r in c.execute('select *from raw_table_queue'):
                    a=dict(r);b=before[r['table_id']]
                    if a!=b:changed.append(r['table_id']);ck('only_review_state_changed:'+r['table_id'],{k:v for k,v in a.items()if k!='review_state'}=={k:v for k,v in b.items()if k!='review_state'})
            else:ck('old_rows_preserved:'+name,{tuple(r)for r in p.execute('select *from "'+name+'"')}<={tuple(r)for r in c.execute('select *from "'+name+'"')})
        ck('28_raw_candidates_touched',len(changed)==28)
        for table,n in [('materials',40),('material_facts',307),('capacitance_observations',33),('outcome_observations_v3',115),('synthesis_stages_v3',27),('test_candidates',3),('reviewed_sources',5),('reviewed_tables',44),('scientific_issues',6)]:ck('delta:'+table,c.execute('select count(*)from '+table).fetchone()[0]-p.execute('select count(*)from '+table).fetchone()[0]==n)
        for r in c.execute('select *from cell_extractions_v20'):
            raw=json.loads(c.execute('select cells_json from transcribed_rows where table_key=?and row_ordinal=?',(r['table_key'],r['row_ordinal'])).fetchone()[0])[r['column_ordinal']]
            table,pk={'fact':('material_facts','fact_id'),'capacitance':('capacitance_observations','observation_id'),'response':('outcome_observations_v3','outcome_id')}[r['kind']];v=c.execute('select *from '+table+' where '+pk+'=?',(r['record_id'],)).fetchone();v=json.loads(v['record_json'])if r['kind']=='response'else dict(v)
            ck('raw_cell:'+r['kind']+r['record_id'],v['raw_value']==raw);ck('numeric_cell:'+r['kind']+r['record_id'],v['value']==number(raw))
            if r['kind']=='fact':
                doc=c.execute('select document_key from table_source_links where table_key=?',(r['table_key'],)).fetchone()[0];ck('fact_original_SHA:'+r['record_id'],v['source_sha256']==docs[doc]['sha256']);ck('fact_numeric_details:'+r['record_id'],json.loads(c.execute('select record_json from numeric_details_v20 where fact_id=?',(r['record_id'],)).fetchone()[0])['value']==v['value'])
        count=lambda t:c.execute('select count(*)from '+t).fetchone()[0]
        totals={k:count(t)for k,t in [('cumulative_reviewed_source_publications','source_scope_decisions'),('cumulative_materials','materials'),('cumulative_selected_material_cells','material_facts'),('actual_distinct_reviewed_table_keys','reviewed_tables'),('extraction_units_v3_count','extraction_units_v3'),('capacitance_records','capacitance_observations'),('cycling_candidates','test_candidates'),('scientific_issues','scientific_issues'),('synthesis_materials','synthesis_stages_v3'),('response_outcomes','outcome_observations_v3')]}
        totals['cumulative_numeric_material_facts']=c.execute('select count(*)from material_facts where value is not null').fetchone()[0];totals['unreported_material_cells']=count('material_facts')-totals['cumulative_numeric_material_facts'];totals['numeric_capacitance_values']=c.execute('select count(*)from capacitance_observations where value is not null').fetchone()[0]
        ck('959_queue_745_untouched',count('raw_table_queue')==959 and c.execute("select count(*)from raw_table_queue where review_state='automatic_candidate_unreviewed'").fetchone()[0]==745)
    preflight={};exports=[]
    with open_literature_database(DB,digest)as d,old_open(PARENT,PSHA)as old:
        oldfacts={r['fact_id']:r for r in old.facts()}
        for r in d.facts():
            if r['fact_id']in oldfacts:ck('old_fact_API_exact:'+str(r['fact_id']),r==oldfacts[r['fact_id']])
        for t in TARGETS19:ck('old_v19_matrix_exact:'+t,d.batch19_matrix(t)==old.batch19_matrix(t))
        for profile in ['3e','2e_device','native_mineral_3e','2e_author_factor2']:
            current={r['observation_id']:r for r in d.auxiliary_gcd(profile)}
            for r in old.auxiliary_gcd(profile):ck('old_aux_exact:'+r['observation_id'],r==current[r['observation_id']])
        for t,n in zip(TARGETS20,[1,3,3,1,5,6]):
            rows=d.batch20_inputs(t);m=d.batch20_matrix(t);ck('target_count:'+t,len(rows)==n==len(m['y']));ck('nullmask:'+t,m['missing_mask']==[[v is None for v in xx]for xx in m['X']]);ck('no_fitting_imputation:'+t,m['estimators_fitted']==0 and not m['imputed']and not m['training_authorized'])
            ck('no_duplicate_physical_test:'+t,len(set(m['physical_test_groups']))==n)
            for g in sorted(set(m['groups'])):ck('source_weight:'+t+g,math.isclose(sum(w for w,gg in zip(m['sample_weight'],m['groups'])if gg==g),1))
            for r in rows:ck('method_role:'+r['observation_id'],r['method']==('CV'if '_CV_'in t else'GCD')and not r['cyclic_retention_training_admitted']and d.isolation_group(r['source_group'])==r['source_family_group'])
            preflight[t]=dict(rows=n,features=len(FIELDS20),source_families=m['source_families'],missing_cells=sum(sum(x)for x in m['missing_mask']),model_fits=0,cross_source_comparable=all(x['cross_source_comparable']for x in m['categorical_protocol']));exports.append((t,rows,m))
        ck('ordinary189_25DOI',len(d.auxiliary_gcd())==189 and len({r['doi']for r in d.auxiliary_gcd()})==25);ck('expanded358_25DOI',len(d.expanded_graph_3e_matrix()['y'])==358 and d.expanded_graph_3e_matrix()['source_families']==25)
        f=d.canonical_material_features_v13(OJ,'4:1@120');ck('Orange_ND_vs_zero_not_selected','Raman_I2D_IG'not in f['values']);ck('Orange_CV_notGCD',all(r['current_A_g']is None and r['scan_rate_mV_s']==10 and r['conditions']['voltage_upper_V']==1.4 for r in d.batch20_inputs(TARGETS20[1])))
        f=d.canonical_material_features_v13(CO,'SSC-Na2S2O3-KCl-1.5-3.6L-800');ck('Coffee_wet800_BET_frozen','BET_surface_area_m2_g'not in f['values']);ck('Coffee_PTFEsupports157',any(r['value']==157 and r['conditions']['binder']=='PTFE'for r in d.batch20_inputs(TARGETS20[2])))
        f=d.canonical_material_features_v13(SP,'SNPB-800-4');ck('Spirulina_different_methods',f['values']['bulk_EA_N_wt_pct']==2.55 and 'XPS_N_at_pct'not in f['values']and len(d.facts(SP,'SNPB-800-4','XPS_N_at_pct'))==1);ck('Spirulina_IGID_notIDIG',f['values']['Raman_IG_ID']==1.1619 and 'Raman_ID_IG'not in f['values']);ck('Spirulina_dashes_not_zero','tplot_micropore_volume_cm3_g'not in f['values'])
        f=d.canonical_material_features_v13(MO,'MOL850');ck('Moringa_unbound_not_inherited','XRD_d002_A'not in f['values']and f['values']['EDS_C_reported_pct']==88.91);f=d.canonical_material_features_v13(MO,'MOL750');ck('Moringa_evidence_choice',f['values']['BET_surface_area_m2_g']==412.196 and 'total_pore_volume_cm3_g'not in f['values']);ck('Moringa_no_lifetime',not any(r['record']['source_group']=='doi:'+MO for r in d.tests()))
        f=d.canonical_material_features_v13(RH,'RHC');ck('Rice_fresh_not_postcycle',f['values']['XPS_O_at_pct']==8.54 and all(r['value']!=21.22 for r in d.facts(RH,'RHC','XPS_O_at_pct')));ck('Rice_Ct_method_unknown',all(r['method']is None and r['current_A_g']is None for r in d.capacitances(RH)))
        ck('52_not_full',len(d.batch20_sources())==5 and totals['cumulative_reviewed_source_publications']==52 and not d.connection.execute('select *from source_scope_decisions where full_source_review_complete=1').fetchall())
        oldsummary=json.loads((PARENT.parent/'summary.json').read_text('utf8'));summary=dict(oldsummary)
        for k in list(summary):
            if k.startswith('new_')and isinstance(summary[k],int):summary[k]=0
        allaux=[r for p in ['3e','2e_device','native_mineral_3e','2e_author_factor2']for r in d.auxiliary_gcd(p)]
        summary.update(totals);summary.update(new_materials=40,new_final_carbon_materials=27,new_other_stages=12,new_unbound_printed_rows=1,new_material_facts=307,new_numeric_material_facts=totals['cumulative_numeric_material_facts']-3555,new_null_material_facts=totals['unreported_material_cells']-173,new_capacitance_reports=33,new_response_records=115,new_source_response_records=115,new_cycle_candidates=3,new_source_scopes=5,new_own_main_tables=15,new_mixed_own_foreign_main_tables=3,new_own_SI_tables=7,new_raw_candidates_touched=28,raw_candidates_touched=214,raw_candidates_untouched=745,reviewed_table_units=245,reviewed_evidence_units=480,distinct_database_table_keys=totals['actual_distinct_reviewed_table_keys'],database_extraction_units_v3=totals['extraction_units_v3_count'],reviewed_evidence_units_definition='480declaredunits;466actualtablekeys/449extractionunits;245physicaltables. New18main+7ownSI+19boundedprose/figuretranscriptions. 40registrationsinclude27finalcarbons,12otherstages,1unboundprintedrow, not40independentmaterials.',auxiliary_aqueous_3e_GCD_rows=189,auxiliary_ordinary_3e_DOI_groups=25,auxiliary_purpose_reviewed_input_rows=len(allaux),auxiliary_independent_DOI_groups=len({r['doi']for r in allaux}),expanded_3e_with_graph_rows=358,expanded_3e_with_graph_DOI_groups=25,new_3e_purpose_inputs=1,new_separate_purpose_rows=[1,3,3,1,5,6],scope_note='Five existing sources ownmain/SI and methods. 19deduplicated method/material-specific purpose rows, including1ordinary3E; other purposes source-specific orCV orresidualZnCa. No poolingambiguousC/Cg, nofullsourcecompletion/newcyclingadmission/fit.')
    for i,(target,rows,m)in enumerate(exports,1):
        path=OUT/f'purpose_inputs_v20_{i}.csv';cols=['observation_id','doi','sample','target_name','target_F_g','raw_target','method','system','electrolyte','capacitance_basis','binder','uncertainty_kind','source_family','source_weight','source_path','source_sha256','locator']+FIELDS20
        if prepare:
            with path.open('w',encoding='utf-8-sig',newline='')as f:
                w=csv.DictWriter(f,fieldnames=cols);w.writeheader()
                for j,r in enumerate(rows):w.writerow(dict(observation_id=r['observation_id'],doi=r['doi'],sample=r['sample_name'],target_name=target,target_F_g=r['value'],raw_target=r['raw_value'],method=r['method'],system=r['system'],electrolyte=r['electrolyte'],capacitance_basis=r['conditions']['capacitance_basis'],binder=r['conditions'].get('binder'),uncertainty_kind=r['conditions'].get('uncertainty_kind'),source_family=m['groups'][j],source_weight=m['sample_weight'][j],source_path=r['source_path'],source_sha256=r['source_sha256'],locator=r['locator'],**dict(zip(FIELDS20,m['X'][j]))))
        with path.open(encoding='utf-8-sig',newline='')as f:rr=list(csv.DictReader(f))
        ck('CSV_exact_and_null:'+target,len(rr)==len(rows)and all(float(row['target_F_g'])==r['value']and all((row[k]=='')==(v is None)for k,v in zip(FIELDS20,m['X'][j]))for j,(row,r)in enumerate(zip(rr,rows))))
    ck('readonly_database_hash',sha(DB)==digest)
    report=dict(status='passed',database_sha256=digest,check_count=len(checks),checks=sorted(checks),formal_cycling_admissions=0,model_fits=0,scientific_goal_complete=False)
    for name,data in [('summary',summary),('verification',report),('model_inputs_preflight',preflight)]:
        if prepare:write(OUT/(name+'.json'),data)
        else:ck('saved_report:'+name,json.loads((OUT/(name+'.json')).read_text('utf8'))==data)
    if (OUT/'merge_manifest.json').exists():
        for r in json.loads((OUT/'merge_manifest.json').read_text('utf8'))['outputs']:assert sha(ROOT/r['path'])==r['sha256'],r['path']
    print(json.dumps({k:v for k,v in report.items()if k!='checks'},ensure_ascii=False))

def chain(prepare=False):
    if prepare:assert not(OUT/'merge_manifest.json').exists()
    from verify_egg_current_v026 import verify as old_check
    with contextlib.redirect_stdout(io.StringIO()):old_check(False)
    from data.cycling_db import open_database
    payload=[]
    with open_literature_database(DB,sha(DB))as d,open_database()as cycle:
        mats={r['material_key']:r for r in d.materials()}
        def add(kind,rows):
            for r in rows:
                g=r.get('source_group')or'doi:'+r['doi'];payload.append(dict(kind=kind,group=g))
        add('capacitance',d.capacitances());add('material_fact',d.facts());add('registration',d.materials());add('curve',d.sampled_curves())
        for r in d.tests():payload.append(dict(kind='cycle_candidate',group=r['record']['source_group']))
        for r in d.connection.execute('select material_key from synthesis_stages_v3'):payload.append(dict(kind='synthesis',group='doi:'+mats[r[0]]['doi']))
        for r in d.connection.execute('select o.record_json,m.doi from outcome_observations_v3 o left join materials m using(material_key)'):
            rec=json.loads(r[0]);g='doi:'+r[1]if r[1]else rec.get('source_group');assert g;payload.append(dict(kind='response',group=g))
        for t in TARGETS20:add('v20_purpose',d.batch20_inputs(t))
        for t in TARGETS19:add('v19_purpose',d.batch19_inputs(t))
        for profile in ['3e','2e_device','native_mineral_3e','2e_author_factor2']:add('auxiliary',d.auxiliary_gcd(profile))
        add('expanded3E',d.expanded_graph_3e_inputs());add('cycling',cycle.fetch('all_review').rows)
        for r in d.batch20_figures()+d.batch20_protocols()+d.batch20_decisions():payload.append(dict(kind='v20_scope_evidence',group='doi:'+r['doi']))
        payload.extend(dict(kind='lineage',group='doi:'+r['record']['doi'])for r in d.batch20_lineage())
        for r in payload:r['family']=d.isolation_group(r['group'])
        families=sorted({r['family']for r in payload});holds={}
        for family in families:
            test=[r for r in payload if r['family']==family];train=[r for r in payload if r['family']!=family]
            assert not{r['family']for r in test}&{r['family']for r in train}
            assert all(d.is_quarantined_source(g,[family])and d.is_quarantined_source(g.removeprefix('doi:'),[family])for g in {r['group']for r in test});holds[family]=dict(sorted(collections.Counter(r['kind']for r in test).items()))
        assert len(cycle.reviewed_pending_batch())==37
        report=dict(status='passed',literature_sha256=sha(DB),cycling_sha256=sha(cycle.path),payloads=len(payload),raw_identifiers=len({r['group']for r in payload}),source_families=len(families),full_quarantine_counts=holds,separate_purpose_counts=[len(d.batch20_inputs(t))for t in TARGETS20],historical_v026_and_v19_chain='passed_immutable_inputs',current_original_pending=37,formal_cycling_admissions=0,model_fits=0,scientific_goal_complete=False,payload_definition='Callable records/views, including repeated representations, not independent experimental samples; historical narrower views covered by unchanged pinned v19 chain.')
    if prepare:write(OUT/'chain_verification.json',report)
    else:assert json.loads((OUT/'chain_verification.json').read_text('utf8'))==report
    print(json.dumps({k:v for k,v in report.items()if k!='full_quarantine_counts'},ensure_ascii=False))

def seal():
    assert not(OUT/'merge_manifest.json').exists();verify(False);chain(False)
    paths=[p for p in OUT.rglob('*')if p.is_file()]+[ROOT/'data/literature_v20.py',ROOT/'tools/extract_five_sources_v20.py',Path(__file__).resolve()]
    write(OUT/'merge_manifest.json',dict(version='literature_pool_v20',parent_sha256=PSHA,outputs=[dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p),bytes=p.stat().st_size)for p in sorted(paths)],formal_cycling_admissions=0,model_fits=0,scientific_goal_complete=False))
    write(ROOT/'data/current_literature.json',dict(version='literature_pool_v20',directory=OUT.relative_to(ROOT).as_posix(),database_file=DB.name,sha256=sha(DB),api_module='data.literature_v20',scope='Five existing source scopes;307facts,33capacityreports,19separate method/material purposes. No fullsource completion, formalcyclingadmission or newfit.'))
if __name__=='__main__':
    action=sys.argv[1]if len(sys.argv)==2 else''
    if action=='prepare':verify(True);chain(True)
    elif action=='verify':verify(False);chain(False)
    elif action=='seal':seal()
    else:raise SystemExit('prepare/seal once before release; verify readonly')
