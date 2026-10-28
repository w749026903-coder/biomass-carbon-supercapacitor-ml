"""Read-only v25 scientific, native-image and immutable-parent verification; prepare/seal once."""
from contextlib import closing
import collections,csv,io,json,math,sqlite3,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tools'))
from extract_wheat_figures_v25 import OUT,DB,PARENT,PSHA,SOURCE,SSHA,CYCLE,DOI,sha,write,ro,locate,y_at
from release_feature_freezes_v021 import load
from data.literature_v25 import open_literature_database,PURPOSES25,MODES25
from data.literature_v24 import open_literature_database as old_open,TARGETS24
from PIL import Image

def verify(prepare=False):
    if prepare:assert not(OUT/'merge_manifest.json').exists()
    checks=[]
    def ck(name,ok):assert ok,name;checks.append(name)
    s=json.loads((OUT/'curation_spec.json').read_text('utf8'));ck('parent_SHA',sha(PARENT)==PSHA);ck('XML_SHA',sha(SOURCE)==SSHA)
    for r in json.loads((OUT/'protected_inputs.json').read_text('utf8')):ck('protected:'+r['path'],sha(ROOT/r['path'])==r['sha256'])
    for r in json.loads((PARENT.parent/'merge_manifest.json').read_text('utf8'))['outputs']:ck('parent_manifest:'+r['path'],sha(ROOT/r['path'])==r['sha256'])
    with closing(ro(DB))as c,closing(ro(PARENT))as p:
        ck('integrity',c.execute('pragma integrity_check').fetchall()==[('ok',)]);ck('foreign_keys',not c.execute('pragma foreign_key_check').fetchall())
        for name, in p.execute("select name from sqlite_master where type='table'and name not like'sqlite_%'"):
            ck('old_raw_rows_immutable:'+name,{tuple(r)for r in p.execute('select *from "'+name+'"')}<={tuple(r)for r in c.execute('select *from "'+name+'"')})
        ck('raw959queue_exact',c.execute('select *from raw_table_queue').fetchall()==p.execute('select *from raw_table_queue').fetchall())
        ck('20graphs_not_extra_materials',c.execute('select count(*)from materials').fetchone()[0]==447 and c.execute('select count(*)from material_facts').fetchone()[0]==4656 and c.execute('select count(*)from capacitance_observations').fetchone()[0]==1266)
        ck('9original_figures_and_2forward_bindings',c.execute('select count(*)from figure_reviews_v25').fetchone()[0]==9 and c.execute('select count(*)from protocol_bindings_v25').fetchone()[0]==2)
    documents={d['document_key']:d for d in s['figures']};images={k:Image.open(ROOT/d['path']).convert('RGB')for k,d in documents.items()}
    with open_literature_database(DB,sha(DB))as d,old_open(PARENT,PSHA)as old:
        oldfacts={r['fact_id']:r for r in old.facts()}
        for r in d.facts():ck('old_fact_API:'+str(r['fact_id']),r==oldfacts[r['fact_id']])
        oldcaps={r['observation_id']:r for r in old.capacitances()};now={r['observation_id']:r for r in d.capacitances()};fix={r['observation_id']for r in s['protocol_bindings']}
        for oid,r in oldcaps.items():
            a=dict(now[oid])
            if oid in fix:
                original=a.pop('original_conditions_v24');a['conditions']=original;ck('forward_window:'+oid,now[oid]['conditions']['voltage_lower_V']==0 and now[oid]['conditions']['voltage_upper_V']==1 and r['conditions']['voltage_upper_V']is None)
            ck('old_cap_API_except_forward_window:'+oid,a==r)
        for t in TARGETS24[:3]:ck('other_v24_matrix_exact:'+t,d.batch24_matrix(t)==old.batch24_matrix(t))
        a=d.batch24_matrix(TARGETS24[3]);b=old.batch24_matrix(TARGETS24[3]);ck('HPC_old_labels_unchanged',a['y']==b['y']==[346,262]);ck('source4furfural_still_frozen',d.batch24_inspection_rows()==old.batch24_inspection_rows())
        ck('secondary309_stillinspection',d.secondary_inspection_rows()==old.secondary_inspection_rows()and len(d.secondary_inspection_rows())==309)
        preflight=dict(status='passed',purposes={},model_fits=0,training_authorized=False,note='3E6/15/15 and2E2/5/5 are nested representations of oneDOI, not independent sources.')
        exports=[]
        for purpose,n in zip(PURPOSES25,[15,5]):
            preflight['purposes'][purpose]={}
            for mode in MODES25:
                rs=d.batch25_rate_inputs(mode,purpose);m=d.batch25_rate_matrix(mode,purpose);expected=(6 if n==15 else 2)if mode=='author_exact'else n
                ck('purpose_count:'+mode+purpose,len(rs)==len(m['y'])==expected);ck('one_DOI_holdout:'+mode+purpose,len(set(m['groups']))==1 and all(g=='doi:'+DOI for g in m['groups']));ck('weights:'+mode+purpose,math.isclose(sum(m['sample_weight']),1));ck('mask_no_imputation:'+mode+purpose,m['missing_mask']==[[v is None for v in x]for x in m['X']]and not m['imputed']and m['estimators_fitted']==0)
                ck('unique_nominal:'+mode+purpose,len(set(m['nominal_report_groups']))==len(rs));ck('own_stage_BET:'+mode+purpose,all(r['material_features']['BET_surface_area_m2_g']=={'HPC-700':2721,'HPC-800':2202,'HPC-900':1739}[r['sample_name']]for r in rs))
                ck('separate_normalization:'+mode+purpose,all(r['system']==('3E'if n==15 else'2E_symmetric')and r['conditions']['capacitance_basis']==('I_dt_over_working_active_m_dV'if n==15 else'4I_dt_over_total_two_electrode_active_m_dV')for r in rs))
                preflight['purposes'][purpose][mode]=dict(rows=len(rs),source_families=m['source_families'],feature_columns=len(m['feature_names']),masked_feature_cells=sum(sum(row)for row in m['missing_mask']),nominal_condition_groups=len(set(m['nominal_report_groups'])),model_fits=0)
                exports.append((purpose,mode,rs,m))
        for r in s['readings']:
            xp,yp,hits,roi=locate(images[r['document']],r['axis'],r['x_value'],r['localization_guess_not_measurement'],r['color']);ck('native_colour_receipt:'+r['reading_id'],xp==r['pixel_x']and yp==r['pixel_y']and hits==r['color_hits']);ck('axis_bounds:'+r['reading_id'],r['y_value']==y_at(r['axis'],yp)and r['y_lower_bound']==y_at(r['axis'],yp+4)and r['y_upper_bound']==y_at(r['axis'],yp-4))
            if r['author_exact_observation_id']:ck('known_anchor_in_reading_bound:'+r['reading_id'],r['y_lower_bound']<=oldcaps[r['author_exact_observation_id']]['value']<=r['y_upper_bound'])
        ck('12newconditions_8oldanchors',sum(not r['author_exact_observation_id']for r in s['readings'])==12 and sum(bool(r['author_exact_observation_id'])for r in s['readings'])==8)
        ck('ordinary_aux_not_inflated',len(d.auxiliary_gcd())==205);oldex={r['observation_id']:r for r in old.expanded_graph_3e_inputs()};expanded=d.expanded_graph_3e_inputs();m=d.expanded_graph_3e_matrix();ck('expanded383_30nested',len(expanded)==383 and m['source_families']==30)
        ex={r['observation_id']:r for r in expanded}
        for oid,r in oldex.items():ck('old_expanded_value:'+oid,ex[oid]['target_value']==r['target_value']and ex[oid]['matrix_feature_values']==r['matrix_feature_values'])
        for g in set(m['groups']):ck('expanded_source_weight:'+g,math.isclose(sum(w for gg,w in zip(m['groups'],m['sample_weight'])if gg==g),1))
        ck('9not15added_toexpanded',len(set(ex)-set(oldex))==9)
        try:d.batch25_rate_matrix('invented_mode')
        except ValueError:ck('reject_invalid_mode',True)
        else:raise AssertionError('Invalid mode accepted')
        cycle=load(CYCLE.parent,'_v027_v25verify')
        with cycle.Database()as cy:
            ck('pinned_cycle286_fixed37',len(cy.fetch('all_review').rows)==286 and len(cy.reviewed_pending_batch())==37)
            oldcycles=cy.fetch('all_review').rows
        mats={r['material_key']:r for r in d.materials()};payload=[dict(kind='material',group='doi:'+r['doi'])for r in mats.values()]+[dict(kind='fact',group='doi:'+r['doi'])for r in d.facts()]+[dict(kind='capacity',group=r['source_group'])for r in d.capacitances()]+[dict(kind='curve',group='doi:'+r['doi'])for r in d.sampled_curves()]+[dict(kind='cycle',group=r['source_group'])for r in oldcycles]
        for r in d.tests():payload.append(dict(kind='candidate',group='doi:'+mats[r['material_key']]['doi']))
        for r in d.connection.execute('select material_key from synthesis_stages_v3'):payload.append(dict(kind='synthesis',group='doi:'+mats[r[0]]['doi']))
        for r in d.connection.execute('select o.record_json,m.doi from outcome_observations_v3 o left join materials m using(material_key)'):
            q=json.loads(r[0]);payload.append(dict(kind='response',group='doi:'+r[1]if r[1]else q['source_group']))
        families=collections.defaultdict(collections.Counter)
        for r in payload:
            g=d.isolation_group(r['group']);families[g][r['kind']]+=1;ck('all_task_quarantine:'+str(len(checks)),d.is_quarantined_source(r['group'],[g]))
        counts={g:dict(sorted(v.items()))for g,v in sorted(families.items())}
        ck('same_HPC_family',counts['doi:'+DOI]['capacity']==29 and counts['doi:'+DOI]['curve']==20)
    summary=json.loads((PARENT.parent/'summary.json').read_text('utf8'))
    for k,v in list(summary.items()):
        if k.startswith('new_')and isinstance(v,int):summary[k]=0
        elif k.startswith('new_')and isinstance(v,list):summary[k]=[]
    summary.update(capacitance_records=1266,numeric_capacitance_values=1252,new_capacitance_reports=20,new_figure_scope_inspections=9,new_bounded_curve_samples=20,bounded_curve_samples=459,numeric_bounded_curve_samples=449,new_nominal_conditions=12,existing_author_anchors=8,new_protocol_bindings=2,reviewed_evidence_units=558,actual_distinct_reviewed_table_keys=544,distinct_database_table_keys=544,extraction_units_v3_count=527,database_extraction_units_v3=527,reviewed_table_units=284,expanded_3e_with_graph_rows=383,expanded_3e_with_graph_DOI_groups=30,new_separate_purpose_rows=[15,5],new_model_fits=0,scope_note='Nine wheat-husk originals obtained/read;20 bounded rate markers,8existing author anchors/12additional nominal conditions. Ordinaryaux205unchanged, expanded383nested. Two old2Ecapacityconditions forwardbound0..1V; nocyclingadmissioninthisliteraturelayer, no fullsourcecompletion;707rawcandidatesunchanged.')
    summary.update(cumulative_bounded_curve_samples=459,cumulative_numeric_curve_samples=449,cumulative_curve_groups=72,curve_sampling_panels=22,new_curve_groups=4,new_numeric_curve_samples=20,reviewed_evidence_units_definition='558declared;544actualtablekeys/527extractionunits;284physicaltables. v25adds2graphmarkerunits, no new physicaltable/automaticcandidate;9figureswereobtainedandreadofexistingHPsource.')
    report=dict(status='passed',database_sha256=sha(DB),parent_sha256=PSHA,check_count=len(checks),checks=sorted(checks),graph_captures=20,existing_author_anchors=8,additional_nominal_conditions=12,protocol_bindings=2,all_source_scopes_still_partial=True,model_fits=0,scientific_goal_complete=False)
    chain=dict(status='passed',representation_payloads=len(payload),source_families=len(counts),whole_family_counts=counts,cycle_snapshot='v0.27',pending_original=37,resolved_original=2,model_fits=0,representations_not_experiments=True)
    for name,value in [('summary',summary),('verification',report),('chain_verification',chain),('model_inputs_preflight',preflight)]:
        if prepare:write(OUT/(name+'.json'),value)
        else:assert json.loads((OUT/(name+'.json')).read_text('utf8'))==value,name
    for purpose,mode,rs,m in exports:
        buff=io.StringIO(newline='');w=csv.writer(buff,lineterminator='\n');w.writerow(['observation_id','sample','nominal_current_A_g','C_F_g','C_lower_F_g','C_upper_F_g','target_kind','source_family','source_weight','nominal_report_group']+m['feature_names'])
        for i,r in enumerate(rs):w.writerow([r['observation_id'],r['sample_name'],r['current_A_g'],r['target_value'],r['target_lower_bound'],r['target_upper_bound'],r['target_value_kind'],r['source_family_group'],m['sample_weight'][i],r['nominal_report_group']]+m['X'][i])
        path=OUT/(purpose+'_'+mode+'.csv')
        if prepare:path.write_text(buff.getvalue(),encoding='utf-8-sig',newline='')
        else:assert path.read_text('utf-8-sig')==buff.getvalue()
    if(OUT/'merge_manifest.json').exists():
        for r in json.loads((OUT/'merge_manifest.json').read_text('utf8'))['outputs']:assert sha(ROOT/r['path'])==r['sha256'],r['path']
    print(json.dumps({k:v for k,v in report.items()if k!='checks'}))

def seal():
    assert not(OUT/'merge_manifest.json').exists();verify(False)
    paths=[p for p in OUT.rglob('*')if p.is_file()]+[ROOT/'data/literature_v25.py',ROOT/'tools/extract_wheat_figures_v25.py',Path(__file__).resolve()]
    write(OUT/'merge_manifest.json',dict(version='literature_pool_v25',parent_sha256=PSHA,outputs=[dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p),bytes=p.stat().st_size)for p in sorted(paths)],model_fits=0,scientific_goal_complete=False))
    write(ROOT/'data/current_literature.json',dict(version='literature_pool_v25',directory=OUT.relative_to(ROOT).as_posix(),database_file=DB.name,sha256=sha(DB),api_module='data.literature_v25',scope='Nine wheat originals,20bounded rate captures/8oldanchors/12newconditions;3E15 and2E5nested modes, expanded383/30DOI. Two own2Eprotocolwindows resolvedbyactualFig8a. No fit/fullsourcecompletion.'))
if __name__=='__main__':
    action=sys.argv[1]if len(sys.argv)==2 else''
    if action=='prepare':verify(True)
    elif action=='verify':verify(False)
    elif action=='seal':seal()
    else:raise SystemExit('prepare/seal once before release; verify readonly')
