"""Read-only v19 companion: compare identical check inventories independent of set order.
The sealed verifier/report/data/manifest are not modified. No scientific gate is changed.
"""
from pathlib import Path
from contextlib import closing
import collections,csv,json,math,sqlite3,sys,xml.etree.ElementTree as E
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tools'))
from extract_lignin_egg_tobacco_v19 import OUT,DB,PARENT,PSHA,KEYS,L,EG,TO,sha,write,ro,number,numeric_details
from data.literature_v19 import open_literature_database,TARGETS19,FIELDS19
from data.literature_v18 import open_literature_database as parent_open

def verify(prepare=False):
    if prepare:assert not(OUT/'merge_manifest.json').exists()
    digest=sha(DB);checks=[]
    def ck(n,b):assert b,n;checks.append(n)
    s=json.loads((OUT/'curation_spec.json').read_text('utf8'));docs={r['key']:r for r in s['documents']}
    ck('parent_SHA',sha(PARENT)==PSHA)
    for r in json.loads((OUT/'protected_inputs.json').read_text('utf8'))['files']:ck('protected:'+r['path'],sha(ROOT/r['path'])==r['sha256'])
    for r in json.loads((PARENT.parent/'merge_manifest.json').read_text('utf8'))['outputs']:ck('parent_release:'+r['path'],sha(ROOT/r['path'])==r['sha256'])
    with closing(ro(DB))as c,closing(ro(PARENT))as p:
        c.row_factory=p.row_factory=sqlite3.Row;ck('integrity',[r[0]for r in c.execute('pragma integrity_check')]==['ok']);ck('foreign_keys',not c.execute('pragma foreign_key_check').fetchall())
        for name, in p.execute("select name from sqlite_master where type='table'and name not like'sqlite_%'"):
            if name=='raw_table_queue':
                before={r['table_id']:dict(r)for r in p.execute('select *from raw_table_queue')}
                changed=[]
                for r in c.execute('select *from raw_table_queue'):
                    b=before[r['table_id']];a=dict(r)
                    if b!=a:
                        ck('queue_only_review_state:'+r['table_id'],{k:v for k,v in a.items()if k!='review_state'}=={k:v for k,v in b.items()if k!='review_state'});changed.append(r['table_id'])
                ck('27_raw_candidates_reviewed',len(changed)==27)
            else:ck('all_parent_rows_preserved:'+name,{tuple(r)for r in p.execute('select *from "'+name+'"')}<={tuple(r)for r in c.execute('select *from "'+name+'"')})
        for name,n in [('material_facts',482),('materials',38),('capacitance_observations',9),('outcome_observations_v3',45),('synthesis_stages_v3',25),('test_candidates',5),('reviewed_sources',3),('reviewed_tables',38),('scientific_issues',6)]:ck('delta:'+name,c.execute('select count(*)from '+name).fetchone()[0]-p.execute('select count(*)from '+name).fetchone()[0]==n)
        for r in c.execute('select *from cell_extractions_v19'):
            raw=json.loads(c.execute('select cells_json from transcribed_rows where table_key=?and row_ordinal=?',(r['table_key'],r['row_ordinal'])).fetchone()[0])[r['column_ordinal']]
            table,pk={'fact':('material_facts','fact_id'),'capacitance':('capacitance_observations','observation_id'),'response':('outcome_observations_v3','outcome_id')}[r['kind']]
            v=c.execute('select *from '+table+' where '+pk+'=?',(r['record_id'],)).fetchone();v=json.loads(v['record_json'])if r['kind']=='response'else dict(v)
            ck('cell_raw:'+r['kind']+r['record_id'],v['raw_value']==raw);ck('cell_numeric:'+r['kind']+r['record_id'],v['value']==number(raw))
            if r['kind']=='fact':ck('fact_details:'+r['record_id'],json.loads(c.execute('select record_json from numeric_details_v19 where fact_id=?',(r['record_id'],)).fetchone()[0])['value']==v['value'])
        ck('raw_959_773_remaining',c.execute('select count(*)from raw_table_queue').fetchone()[0]==959 and c.execute("select count(*)from raw_table_queue where review_state='automatic_candidate_unreviewed'").fetchone()[0]==773)
        for r in c.execute('select *from figure_scope_reviews_v19'):
            rr=json.loads(r['record_json']);root=E.parse(ROOT/docs[KEYS[r['doi']]]['path']).getroot();f=next(f for f in root.findall('.//fig')if f.get('id')==rr['xml_id'])
            ck('actual_label_href:'+r['document_key'],''.join(f.find('label').itertext())==rr['printed_label']and f.find('.//graphic').get('{http://www.w3.org/1999/xlink}href')==rr['graphic_href'])
        count=lambda t:c.execute('select count(*)from '+t).fetchone()[0]
        totals={k:count(t)for k,t in [('cumulative_reviewed_source_publications','source_scope_decisions'),('cumulative_materials','materials'),('cumulative_selected_material_cells','material_facts'),('actual_distinct_reviewed_table_keys','reviewed_tables'),('extraction_units_v3_count','extraction_units_v3'),('capacitance_records','capacitance_observations'),('cycling_candidates','test_candidates'),('scientific_issues','scientific_issues'),('synthesis_materials','synthesis_stages_v3'),('response_outcomes','outcome_observations_v3')]}
        totals['cumulative_numeric_material_facts']=c.execute('select count(*)from material_facts where value is not null').fetchone()[0];totals['unreported_material_cells']=count('material_facts')-totals['cumulative_numeric_material_facts'];totals['numeric_capacitance_values']=c.execute('select count(*)from capacitance_observations where value is not null').fetchone()[0]
    preflight={};exports=[]
    with open_literature_database(DB,digest)as d,parent_open(PARENT,PSHA)as old:
        oldfacts={r['fact_id']:r for r in old.facts()}
        for r in d.facts():
            if r['fact_id']in oldfacts:ck('old_fact_API_exact:'+str(r['fact_id']),r==oldfacts[r['fact_id']])
        for t,n in zip(TARGETS19,[4,2,1,1]):
            rows=d.batch19_inputs(t);m=d.batch19_matrix(t);ck('purpose_count:'+t,len(rows)==n==len(m['y']));ck('purpose_not_fitted:'+t,m['estimators_fitted']==0 and not m['training_authorized']and not m['imputed']);ck('purpose_mask:'+t,m['missing_mask']==[[v is None for v in xx]for xx in m['X']])
            for g in set(m['groups']):ck('source_weight:'+t+g,math.isclose(sum(w for w,gg in zip(m['sample_weight'],m['groups'])if gg==g),1))
            for r in rows:ck('fresh_only:'+r['observation_id'],r['method']=='GCD'and 'retention'not in r['target_name']and r['source_family_group']==d.isolation_group('doi:'+r['doi']))
            preflight[t]=dict(rows=n,features=len(FIELDS19),source_families=m['source_families'],missing_cells=sum(sum(z)for z in m['missing_mask']),model_fits=0);exports.append((rows,m,t))
        for profile in ['3e','2e_device','native_mineral_3e','2e_author_factor2']:
            current={r['observation_id']:r for r in d.auxiliary_gcd(profile)}
            for r in old.auxiliary_gcd(profile):ck('old_aux_API_exact:'+r['observation_id'],r==current[r['observation_id']])
        ck('ordinary188_24DOI',len(d.auxiliary_gcd('3e'))==188 and len({r['doi']for r in d.auxiliary_gcd('3e')})==24)
        ck('expanded357_24DOI',len(d.expanded_graph_3e_matrix()['y'])==357 and d.expanded_graph_3e_matrix()['source_families']==24)
        for mode in ['author_exact','point_mixed','figure_only']:
            ck('v16_preserved:'+mode,d.batch16_rate_matrix(mode)==old.batch16_rate_matrix(mode))
            for purpose in ['ordinary_3e','native_silica_3e']:ck('v18_inspection_exact:'+mode+purpose,d.batch18_rate_inputs(mode,purpose)==old.batch18_rate_inputs(mode,purpose))
        from data.literature_v17 import TARGETS17
        for t in TARGETS17:ck('v17_exact:'+t,d.batch17_matrix(t)==old.batch17_matrix(t))
        # Scientific traps: retain limits, stages, percentage basis and conflicting rate.
        fs=d.facts(L,'OS beech LCNF1000','XPS_S_wt_pct');ck('censored_sulfur_not_zero',len(fs)==1 and fs[0]['value']is None and fs[0]['numeric_details_v19']['limit']==.01)
        f=d.canonical_material_features_v13(L,'Kraft pine/spruce LCNF1000');ck('ambiguous_decimal_not_guessed','volume_packing_fraction_author'not in f['values'])
        for s1 in ['OS beech LCNF1000','Kraft eucalyptus LCNF1000']:
            v=d.canonical_material_features_v13(L,s1)['values'];ck('no_raw_inheritance:'+s1,not any(k.startswith(('NMR31P','GPC','CHNS','dope_','raw_lignin_'))for k in v)and 'XPS_N_at_pct'not in v)
        f=d.canonical_material_features_v13(EG,'YPAC-1');ck('EA_not_XPS_atomic',f['values']['bulk_EA_N_wt_pct']==3.54 and 'XPS_N_at_pct'not in f['values']and 'XPS_N_reported_pct'not in f['values'])
        f=d.canonical_material_features_v13(TO,'N-YAC0.5')['values'];ck('Tobacco_atomic_basis',f['XPS_C_at_pct']==91.81 and f['XPS_N_at_pct']==1.85)
        ck('Tobacco_dissent_excluded',all(not(r['doi']==TO and r['current_A_g']==20)for r in d.batch19_inputs()))
        link=d.batch19_cycle_identity_links()[0]['record'];ck('missed_current_real_oldendpoint',link['existing_endpoint_id']=='candidate:TE009'and link['new_reported_current_A_g']==10 and link['not_new_cycling_endpoint'])
        text=(ROOT/docs[KEYS[EG]]['path']).read_text('utf8');ck('explicit_cycle_sentence_present','also underwent 10 A' in text and 'constant-current charge/discharge cycles' in text)
        ck('47not_full',len(d.connection.execute('select doi from source_scope_decisions').fetchall())==47 and not d.connection.execute('select doi from source_scope_decisions where full_source_review_complete=1').fetchall())
        allaux=[r for p in ['3e','2e_device','native_mineral_3e','2e_author_factor2']for r in d.auxiliary_gcd(p)]
        summary=json.loads((PARENT.parent/'summary.json').read_text('utf8'))
        for k in list(summary):
            if k.startswith('new_')and isinstance(summary[k],int):summary[k]=0
        summary.update(totals);summary.update(new_materials=38,new_material_facts=482,new_numeric_material_facts=totals['cumulative_numeric_material_facts']-3078,new_null_material_facts=totals['unreported_material_cells']-168,new_response_records=45,new_source_response_records=45,new_capacitance_reports=9,new_cycle_candidates=5,new_source_scopes=3,new_own_main_tables=6,new_own_SI_tables=17,new_mixed_own_foreign_main_tables=2,new_SI_foreign_comparison_physical_tables=1,new_raw_candidates_touched=27,raw_candidates_touched=186,raw_candidates_untouched=773,reviewed_table_units=220,reviewed_evidence_units=436,distinct_database_table_keys=totals['actual_distinct_reviewed_table_keys'],database_extraction_units_v3=totals['extraction_units_v3_count'],reviewed_evidence_units_definition='436 declared units;422 actual reviewed table keys/405 extraction_units;220 physicaltables includes foreigncomparisonS1 mapped to two PDF fragments. New8main+17ownSI+13boundprose/figure units; foreign S1 disposition not new ownfacttable.',auxiliary_aqueous_3e_GCD_rows=188,auxiliary_ordinary_3e_DOI_groups=24,auxiliary_purpose_reviewed_input_rows=len(allaux),auxiliary_independent_DOI_groups=len({r['doi']for r in allaux}),expanded_3e_with_graph_rows=357,expanded_3e_with_graph_DOI_groups=24,new_3e_purpose_inputs=4,new_separate_purpose_rows=[4,2,1,1],source_scope_complete=0,scope_note='Three new ownsource scopes,38staged materials,482facts; four3E authorlabels plus separatePEO2Eaqueous2/WIS1 andordinary2Efactor4one. OriginalTE009 missedcyclecurrent located; linked for cycling version, not admitted here. No fullsource completion or fit.')
    for i,(rows,m,t)in enumerate(exports,1):
        path=OUT/('purpose_inputs_v19_'+str(i)+'.csv');cols=['observation_id','doi','sample','target_name','target_F_g','source_family','source_weight','source_path','source_sha256','locator']+FIELDS19
        if prepare:
            with path.open('w',encoding='utf-8-sig',newline='')as f:
                w=csv.DictWriter(f,fieldnames=cols);w.writeheader()
                for k,r in enumerate(rows):w.writerow(dict(observation_id=r['observation_id'],doi=r['doi'],sample=r['sample_name'],target_name=t,target_F_g=r['value'],source_family=m['groups'][k],source_weight=m['sample_weight'][k],source_path=r['source_path'],source_sha256=r['source_sha256'],locator=r['locator'],**dict(zip(FIELDS19,m['X'][k]))))
        with path.open(encoding='utf-8-sig',newline='')as f:csvrows=list(csv.DictReader(f))
        ck('CSV:'+t,len(csvrows)==len(rows)and all(float(rr['target_F_g'])==r['value']and all((rr[name]=='')==(v is None)for name,v in zip(FIELDS19,m['X'][j]))for j,(rr,r)in enumerate(zip(csvrows,rows))))
    ck('readonly_DB_hash',sha(DB)==digest)
    report=dict(status='passed',database_sha256=digest,check_count=len(checks),checks=sorted(checks),formal_cycling_admissions=0,model_fits=0,scientific_goal_complete=False)
    for name,value in [('summary',summary),('verification',report),('model_inputs_preflight',preflight)]:
        if prepare:write(OUT/(name+'.json'),value)
        else:
            stored=json.loads((OUT/(name+'.json')).read_text('utf8'))
            if name=='verification':stored['checks']=sorted(stored['checks'])
            assert stored==value,name
    if not prepare and(OUT/'merge_manifest.json').exists():
        for r in json.loads((OUT/'merge_manifest.json').read_text('utf8'))['outputs']:assert sha(ROOT/r['path'])==r['sha256'],r['path']
    print(json.dumps({k:v for k,v in report.items()if k!='checks'},ensure_ascii=False))
if __name__=='__main__':
    if sys.argv[1:]!=['verify']:raise SystemExit('prepare/seal once before release; verify readonly')
    verify(False)
