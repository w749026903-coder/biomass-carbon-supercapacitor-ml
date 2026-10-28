"""Read-only full own-table coverage, figure-label disputes and model-input checks."""
from pathlib import Path
from contextlib import closing
import collections,csv,io,json,math,sqlite3,sys,xml.etree.ElementTree as E,zipfile
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tools'))
from extract_wood_temperatures_v26 import OUT,DB,PARENT,PSHA,CYCLE,CSHA,SOURCE,SSHA,DOI,NATIVE,TEMPS,numeric,sha,write,ro,xml_grid,clean
from release_feature_freezes_v021 import load
from data.literature_v26 import open_literature_database,TARGETS26,FIELDS26
from data.literature_v25 import open_literature_database as old_open,PURPOSES25,MODES25
from data.literature_v24 import TARGETS24

def verify(prepare=False):
    if prepare:assert not(OUT/'merge_manifest.json').exists()
    checks=[]
    def ck(name,ok):assert ok,name;checks.append(name)
    s=json.loads((OUT/'curation_spec.json').read_text('utf8'));ck('parent_SHA',sha(PARENT)==PSHA);ck('source_SHA',sha(SOURCE)==SSHA);ck('cycle_SHA',sha(CYCLE)==CSHA)
    for r in json.loads((OUT/'protected_inputs.json').read_text('utf8')):ck('protected:'+r['path'],sha(ROOT/r['path'])==r['sha256'])
    for r in json.loads((PARENT.parent/'merge_manifest.json').read_text('utf8'))['outputs']:ck('parent_manifest:'+r['path'],sha(ROOT/r['path'])==r['sha256'])
    x=E.parse(SOURCE).getroot();paras={str(i):clean(p)for i,p in enumerate(x.findall('./body//p'),1)};ck('144fullbodyparagraphs',len(paras)==144 and paras==s['body_paragraphs']);ck('primary_research_and_12figs',x.get('article-type')=='research-article'and len(x.findall('.//fig'))==12)
    asset=json.loads((OUT/'asset_inventory.json').read_text('utf8'));z=zipfile.ZipFile(ROOT/asset['archive_path']);ck('archive_SHA',sha(ROOT/asset['archive_path'])==asset['archive_sha256']);ck('no_declaredSI_or_SI_inpackage',not x.findall('.//supplementary-material')and set(Path(m.filename).suffix for m in z.infolist())=={'.jpg','.gif'})
    for r in asset['files']:ck('12archive_members:'+r['archive_member'],z.read(r['archive_member'])==(ROOT/r['path']).read_bytes())
    with closing(ro(DB))as c,closing(ro(PARENT))as p:
        c.row_factory=p.row_factory=sqlite3.Row;ck('integrity',[r[0]for r in c.execute('pragma integrity_check')]==['ok']);ck('foreign_keys',not c.execute('pragma foreign_key_check').fetchall())
        for name, in p.execute("select name from sqlite_master where type='table'and name not like'sqlite_%'"):
            if name=='raw_table_queue':continue
            ck('old_raw_rows:'+name,{tuple(r)for r in p.execute('select *from "'+name+'"')}<={tuple(r)for r in c.execute('select *from "'+name+'"')})
        before={r['table_id']:dict(r)for r in p.execute('select *from raw_table_queue')};changed=[]
        for r in c.execute('select *from raw_table_queue'):
            a=dict(r);b=before[r['table_id']]
            if a!=b:changed.append(r['table_id']);ck('queue_only_status:'+r['table_id'],{k:v for k,v in a.items()if k!='review_state'}=={k:v for k,v in b.items()if k!='review_state'})
        ck('only_two_native_candidates',set(changed)=={t['raw_table_id']for t in s['tables']});ck('959queue_705untouched',len(before)==959 and c.execute("select count(*)from raw_table_queue where review_state='automatic_candidate_unreviewed'").fetchone()[0]==705)
        for t in x.findall('.//table-wrap'):
            grid=xml_grid(t);key=DOI+'#v26_'+t.get('id');ck('own_table_header:'+key,len(grid)==5 and len(grid[0])==6)
            for row in range(1,5):
                cells=json.loads(c.execute('select cells_json from transcribed_rows where table_key=?and row_ordinal=?',(key,row)).fetchone()[0]);ck('all_native_cells:'+key+str(row),cells==[r['raw']for r in grid[row]])
                for col in [1,2,4,5]:ck('all32ownnumericcells_accounted:'+key+str(row)+str(col),len(c.execute('select *from cell_extractions_v26 where table_key=?and row_ordinal=?and column_ordinal=?',(key,row,col)).fetchall())==1)
        docs={r['document_key']:r for r in c.execute('select *from source_documents')}
        for r in c.execute('select *from cell_extractions_v26'):
            a=json.loads(r['record_json']);raw=json.loads(c.execute('select cells_json from transcribed_rows where table_key=?and row_ordinal=?',(r['table_key'],r['row_ordinal'])).fetchone()[0])[r['column_ordinal']];ck('raw_cell:'+r['kind']+r['record_id'],raw==a['raw']and numeric(raw)['value']==a['value'])
            table,pk={'fact':('material_facts','fact_id'),'capacitance':('capacitance_observations','observation_id'),'response':('outcome_observations_v3','outcome_id')}[r['kind']];actual=c.execute('select *from '+table+' where '+pk+'=?',(r['record_id'],)).fetchone();actual=json.loads(actual['record_json'])if r['kind']=='response'else dict(actual);ck('selected_raw_value:'+r['kind']+r['record_id'],actual['raw_value']==raw and actual['value']==a['value'])
            if r['kind']=='fact':doc=c.execute('select document_key from table_source_links where table_key=?',(r['table_key'],)).fetchone()[0];ck('fact_SHA:'+r['record_id'],actual['source_sha256']==docs[doc]['sha256'])
        counts={t:c.execute('select count(*)from '+t).fetchone()[0]for t in ['materials','material_facts','capacitance_observations','outcome_observations_v3','synthesis_stages_v3','test_candidates','source_scope_decisions','scientific_issues','reviewed_tables','extraction_units_v3','curve_samples_v8']}
        ck('literal_counts',counts['materials']==458 and counts['material_facts']==4670 and counts['capacitance_observations']==1282 and counts['outcome_observations_v3']==3003 and counts['synthesis_stages_v3']==353 and counts['test_candidates']==96 and counts['source_scope_decisions']==65 and counts['scientific_issues']==207);ck('material10numeric4null',c.execute('select count(*)from material_facts where value is not null').fetchone()[0]==4469);ck('no_source_falsely_complete',not c.execute('select *from source_scope_decisions where full_source_review_complete=1').fetchall());ck('unit_counts_not_physicaltables',counts['reviewed_tables']==558 and counts['extraction_units_v3']==541 and counts['curve_samples_v8']==459)
    exports=[];preflight={}
    with open_literature_database(DB,sha(DB))as d,old_open(PARENT,PSHA)as old:
        oldfacts={r['fact_id']:r for r in old.facts()}
        for r in d.facts():
            if r['fact_id']in oldfacts:ck('old_fact_API:'+str(r['fact_id']),r==oldfacts[r['fact_id']])
        newcaps={r['observation_id']:r for r in d.capacitances()}
        for r in old.capacitances():ck('old_cap_API:'+r['observation_id'],newcaps[r['observation_id']]==r)
        for p in PURPOSES25:
            for mode in MODES25:ck('v25matrix:'+p+mode,d.batch25_rate_matrix(mode,p)==old.batch25_rate_matrix(mode,p))
        for p in TARGETS24:ck('v24matrix:'+p,d.batch24_matrix(p)==old.batch24_matrix(p))
        for p in ['3e','2e_device','native_mineral_3e','2e_author_factor2']:
            current={r['observation_id']:r for r in d.auxiliary_gcd(p)}
            for r in old.auxiliary_gcd(p):ck('old_aux:'+p+r['observation_id'],current[r['observation_id']]==r)
        for target in TARGETS26:
            rows=d.batch26_inputs(target);m=d.batch26_matrix(target);ck('three_purpose_rows:'+target,len(rows)==len(m['y'])==3 and len(set(m['physical_test_groups']))==3);ck('one_DOI_per_purpose:'+target,m['source_families']==1 and all(g=='doi:'+DOI for g in m['groups'])and math.isclose(sum(m['sample_weight']),1));ck('no_imputation_orfit:'+target,not m['imputed']and m['estimators_fitted']==0 and m['missing_mask']==[[v is None for v in row]for row in m['X']]);ck('no400target_or_wrong_current:'+target,all(not r['sample_name'].endswith('400')and r['current_A_g']==1 for r in rows));ck('no_fake_mass_loading:'+target,all(r['conditions']['mass_loading_mg_cm2']is None and r['conditions']['current_mass_basis']=='author_reported_unknown_not_inferred'for r in rows));preflight[target]=dict(rows=3,source_families=1,masked_cells=sum(sum(row)for row in m['missing_mask']),model_fits=0);exports.append((target,rows,m))
        a=d.batch26_inputs();ck('AC500BETstillnull',next(r for r in a if r['sample_name']=='AC-500')['material_features'].get('BET_surface_area_m2_g')is None);ck('own600700BET',dict((r['sample_name'],r['material_features'].get('BET_surface_area_m2_g'))for r in a)=={'AC-500':None,'AC-600':280,'AC-700':67})
        comp=d.batch26_inputs(TARGETS26[1]);ck('no_parent_BET_or_heat_inheritance',all(not r['material_features']and r['matrix_feature_values'].get('carbonization_temperature_C')is None and r['matrix_feature_values']['carbon_component_carbonization_temperature_C']==int(r['sample_name'][-3:])for r in comp))
        for t in TEMPS:
            f=d.canonical_material_features_v13(DOI,'AC-'+str(t));ck('Ramanbothdirectionsmasked:'+str(t),'Raman_ID_IG'not in f['values']and'Raman_IG_ID'not in f['values']);ck('no_XPS_from_FTIR:'+str(t),not any(k.startswith('XPS')for k in f['values']))
        ck('AC400BETdispute_masked','BET_surface_area_m2_g'not in d.canonical_material_features_v13(DOI,'AC-400')['values']);inspect=d.batch26_inspection_rows();ck('eight400inspectionreports',len(inspect)==8 and{r['value']for r in inspect if r['sample_name']=='AC-400'}=={183.4,184.4}and{r['value']for r in inspect if r['sample_name']=='AC:MnO2-400'}=={491,491.3})
        try:d.batch26_matrix('inspection')
        except ValueError:ck('reject_disputed_matrix',True)
        else:raise AssertionError('Disputed inspection became matrix')
        ck('CV100mV_not100V',d.batch26_protocol()[0]['record']['CV_actual_scan_mV_s']==100 and d.batch26_protocol()[0]['record']['CV_body_caption_raw']=='100V/s');ck('8ownexactprintedcyclelabels',[r['record']['selected_retention_pct']for r in d.batch26_cycle_claims()]==[96,91.4,78.4,62.2,99.4,97.3,82.3,70.2]);ck('3oldlinks',[r['record']['endpoint_id']for r in d.batch26_cycle_links()]==['candidate:TE036','candidate:TE037','candidate:TE038'])
        ck('ordinary208_31',len(d.auxiliary_gcd())==208 and len({r['doi']for r in d.auxiliary_gcd()})==31);expanded=d.expanded_graph_3e_matrix();ck('expanded386_31',len(expanded['y'])==386 and expanded['source_families']==31)
        new_expanded_by_id={r['observation_id']:r for r in d.expanded_graph_3e_inputs()}
        for oldr in old.expanded_graph_3e_inputs():ck('old_expanded_label:'+oldr['observation_id'],new_expanded_by_id[oldr['observation_id']]['target_value']==oldr['target_value'])
        cy=load(CYCLE.parent,'_v028_v26_verify')
        with cy.Database()as cycling:
            cycles=cycling.fetch('all_review').rows;ck('pinned287_original37',len(cycles)==287 and len(cycling.reviewed_pending_batch())==37);ck('no_retroactive_cycle_update',[cycling.by_endpoint('candidate:TE0'+str(n))['retention_pct']for n in [36,37,38]]==[90.3,76.4,59.2])
        mats={r['material_key']:r for r in d.materials()};payload=[dict(kind='material',group='doi:'+r['doi'])for r in mats.values()]+[dict(kind='fact',group='doi:'+r['doi'])for r in d.facts()]+[dict(kind='capacitance',group=r['source_group'])for r in d.capacitances()]+[dict(kind='curve',group='doi:'+r['doi'])for r in d.sampled_curves()]+[dict(kind='cycle',group=r['source_group'])for r in cycles]
        for r in d.tests():payload.append(dict(kind='candidate',group='doi:'+mats[r['material_key']]['doi']))
        for r in d.connection.execute('select material_key from synthesis_stages_v3'):payload.append(dict(kind='synthesis',group='doi:'+mats[r[0]]['doi']))
        for r in d.connection.execute('select o.record_json,m.doi from outcome_observations_v3 o left join materials m using(material_key)'):
            v=json.loads(r[0]);payload.append(dict(kind='response',group='doi:'+r[1]if r[1]else v['source_group']))
        families=collections.defaultdict(collections.Counter)
        for i,r in enumerate(payload):
            g=d.isolation_group(r['group']);families[g][r['kind']]+=1;ck('all_task_quarantine:'+str(i),d.is_quarantined_source(r['group'],[g]))
        family_counts={g:dict(sorted(v.items()))for g,v in sorted(families.items())}
    summary=json.loads((PARENT.parent/'summary.json').read_text('utf8'))
    for k,v in list(summary.items()):
        if k.startswith('new_')and isinstance(v,int):summary[k]=0
        elif k.startswith('new_')and isinstance(v,list):summary[k]=[]
    summary.update(cumulative_reviewed_source_publications=65,cumulative_materials=458,cumulative_selected_material_cells=4670,cumulative_numeric_material_facts=4469,unreported_material_cells=201,capacitance_records=1282,numeric_capacitance_values=1268,response_outcomes=3003,response_records=3003,synthesis_materials=353,cycling_candidates=96,scientific_issues=207,reviewed_evidence_units=572,actual_distinct_reviewed_table_keys=558,distinct_database_table_keys=558,database_extraction_units_v3=541,extraction_units_v3_count=541,reviewed_table_units=286,raw_candidates_touched=254,raw_candidates_untouched=705,auxiliary_aqueous_3e_GCD_rows=208,auxiliary_ordinary_3e_DOI_groups=31,auxiliary_purpose_reviewed_input_rows=224,auxiliary_independent_DOI_groups=32,expanded_3e_with_graph_rows=386,expanded_3e_with_graph_DOI_groups=31,new_materials=11,new_material_facts=14,new_numeric_material_facts=10,new_null_material_facts=4,new_capacitance_reports=16,new_response_records=59,new_source_response_records=59,new_synthesis_materials=8,new_cycle_candidates=8,new_existing_cycle_identity_links=3,new_nominal_cycle_candidates=5,new_source_scopes=1,new_own_main_tables=2,new_raw_candidates_touched=2,new_figure_scope_inspections=12,new_separate_purpose_rows=[3,3],new_scientific_decisions=7,new_model_fits=0,reviewed_evidence_units_definition='572declared;558actualtablekeys/541extractionunits;286physicaltables. v26twoownnativetables and12ownprose/printedlabelunits; 3AC400BETclaims splitbyactualAbstract/P75/P138evidence.',scope_note='Woodall4carbonizationand4MnO2composites;14facts10numeric/4null,16capacityreports,59responses. Sixpurposeinputs,8disputed400Cinspectionreports. Eightcyclecandidates3oldlinks/5notyetcanonical, exactFig10versusbodydissentpreserved; cyclingupdatesrequireseparatereview, nofit/fullcompletion.')
    report=dict(status='passed',database_sha256=sha(DB),parent_sha256=PSHA,check_count=len(checks),checks=sorted(checks),new_material_facts=14,new_numeric_material_facts=10,new_capacitance_reports=16,separate_purpose_rows=[3,3],inspection_rows=8,cycle_candidates=8,existing_cycle_links=3,model_fits=0,scientific_goal_complete=False)
    chain=dict(status='passed',representation_payloads=len(payload),source_families=len(family_counts),whole_family_counts=family_counts,cycles_snapshot='v0.28',original_resolved=2,original_pending=37,all_tasks_quarantined=True,representations_not_experiments=True,model_fits=0)
    for name,value in [('summary',summary),('verification',report),('model_inputs_preflight',preflight),('chain_verification',chain)]:
        if prepare:write(OUT/(name+'.json'),value)
        else:assert json.loads((OUT/(name+'.json')).read_text('utf8'))==value,name
    for target,rows,m in exports:
        b=io.StringIO(newline='');w=csv.writer(b,lineterminator='\n');w.writerow(['observation_id','sample','C_F_g','current_A_g','source_family','source_weight']+FIELDS26)
        for i,r in enumerate(rows):w.writerow([r['observation_id'],r['sample_name'],r['value'],r['current_A_g'],r['source_family_group'],m['sample_weight'][i]]+m['X'][i])
        p=OUT/(target+'.csv')
        if prepare:p.write_text(b.getvalue(),encoding='utf-8-sig',newline='')
        else:assert p.read_text('utf-8-sig')==b.getvalue()
    if(OUT/'merge_manifest.json').exists():
        for r in json.loads((OUT/'merge_manifest.json').read_text('utf8'))['outputs']:assert sha(ROOT/r['path'])==r['sha256'],r['path']
    print(json.dumps({k:v for k,v in report.items()if k!='checks'}))

def seal():
    assert not(OUT/'merge_manifest.json').exists();verify(False);paths=[p for p in OUT.rglob('*')if p.is_file()]+[ROOT/'data/literature_v26.py',ROOT/'tools/extract_wood_temperatures_v26.py',Path(__file__).resolve()]
    write(OUT/'merge_manifest.json',dict(version='literature_pool_v26',parent_sha256=PSHA,outputs=[dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p),bytes=p.stat().st_size)for p in sorted(paths)],model_fits=0,scientific_goal_complete=False))
    write(ROOT/'data/current_literature.json',dict(version='literature_pool_v26',directory=OUT.relative_to(ROOT).as_posix(),database_file=DB.name,sha256=sha(DB),api_module='data.literature_v26',scope='Allwood4temperatureand4MnO2series;14facts/10numeric,16capacities,59responses;3ordinary+3compositeinputs,8disputed400Cinspection. Eightcycleclaims and3oldlinks separatelyreviewed; 65sourcespartial, nofit.'))
if __name__=='__main__':
    action=sys.argv[1]if len(sys.argv)==2 else''
    if action=='prepare':verify(True)
    elif action=='verify':verify(False)
    elif action=='seal':seal()
    else:raise SystemExit('prepare/seal once before release; verify readonly')
