"""Forward identity/protocol correction and bounded rate markers; originals immutable."""
from pathlib import Path
from contextlib import closing
import collections,json,sqlite3,sys,xml.etree.ElementTree as E
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tools'))
from extract_onion_composite_v8 import sha,write,ro,insert,mk
from extract_source_series_v13 import clean
from extract_peel_graphs_v16 import runs
from data.cycling_identity import cycling_endpoints_by_doi
from data.literature_groups import normalize_doi
OUT=ROOT/'文献全量利用复核_20261027/批次21_候选身份对账与咖啡稻壳工况复核';DB=OUT/'literature_material_pool_v21.sqlite'
PARENT=ROOT/'文献全量利用复核_20261027/批次20_橙汁稻壳咖啡污泥螺旋藻与辣木/literature_material_pool_v20.sqlite';PSHA='440b94941ce154604ec6359e066305e5c67721990c56472e95a17377a56ff742'
RH='10.1039/d5ra03028e';CO='10.1021/acsomega.3c09438'
AXES={'CO7d':dict(x0=0,xp0=454,x1=20,xp1=728.5,y0=0,yp0=592,y1=200,yp1=343.5),'RH6c':dict(x0=0,xp0=55.5,x1=20,xp1=367.5,y0=0,yp0=591.5,y1=200,yp1=328.5)}
J={'CO7d':[1,5,10,20],'RH6c':[.5,1,2,5,10,20]}
co0='SSC-Na2S2O3-1.5-800';co1='SSC-Na2S2O3-KCl-1.5-3.3-800'
SERIES=[('CO7d',co0,'PVDF',None,'black',[67.4,50,45,40]),('CO7d',co1,'PVDF',None,'red',[89,78,73,65]),('CO7d',co1,'PTFE',None,'blue',[157,141,137,127]),('RH6c','RHC','PTFE',1,'black',[155,141,130,118,106,81]),('RH6c','RHC','PTFE',1.25,'red',[166,146,140,123,110,83]),('RH6c','RHC','PTFE',1.5,'blue',[160,145,128,116,103,78]),('RH6c','RHC','PTFE',2,'magenta',[142,129,117,103,89,69])]

def color_match(color,rgb):
    r,g,b=rgb
    return {'black':max(rgb)<145 and max(rgb)-min(rgb)<35,'red':r-max(g,b)>60,'blue':b-max(r,g)>55,'magenta':min(r,b)-g>65 and abs(r-b)<100}[color]
def y_at(axis,pixel):return axis['y0']+(pixel-axis['yp0'])*(axis['y1']-axis['y0'])/(axis['yp1']-axis['yp0'])

def curate():
    assert sha(PARENT)==PSHA and not DB.exists()and not(OUT/'curation_spec.json').exists()and not(OUT/'merge_manifest.json').exists()
    from data.literature_v20 import open_literature_database
    from data.cycling_db import open_database
    s=dict(parent_sha256=PSHA,documents={},panels=[],readings=[],protocol_corrections=[],candidate_audits=[],manual_links=[],source_review_notes=[])
    with open_literature_database(PARENT,PSHA)as lit,open_database()as cycle:
        allcycle=cycle.fetch('all_review').rows;lookup=cycling_endpoints_by_doi(allcycle);mats={r['material_key']:r for r in lit.materials()};links={r['candidate_id']:r for r in cycle.literature_links()}
        for candidate in sorted(lit.tests(),key=lambda r:r['candidate_id']):
            doi=normalize_doi(mats[candidate['material_key']]['doi']);matches=lookup['by_doi'].get(doi,[])
            s['candidate_audits'].append(dict(candidate_id=candidate['candidate_id'],doi=doi,existing_same_DOI_endpoint_ids=sorted(r['endpoint_id']for r in matches),established_link=links.get(candidate['candidate_id']),decision='Existingauthoritativecandidate_link_retained'if candidate['candidate_id']in links else'SameDOIonly_requires_sample_protocol_endpoint_review'if matches else'No_directcanonical_DOI_match_in_current_rows_not_proof_of_new_experiment',automatic_admission=False,raw_source_strings_preserved=True))
        s['identity_audit_summary']=dict(candidates=len(s['candidate_audits']),cycling_rows=len(allcycle),unresolved_cycling_DOI_endpoint_ids=lookup['unresolved_endpoint_ids'],same_DOI_candidates=sum(bool(r['existing_same_DOI_endpoint_ids'])for r in s['candidate_audits']),not_new_experiment_count=True)
        cases=[('LP20:Coffee:citrate_2E','legacy:R104_CY01',98.4,20000,10,None),('LP20:RHC:ratio1','legacy:SRC123_CY02',27.9,10000,1,1),('LP20:RHC:ratio2','legacy:SRC123_CY03',96.4,10000,1,2)]
        candidates={r['candidate_id']:r for r in lit.tests()}
        for cid,key,ret,n,j,ratio in cases:
            old=cycle.by_endpoint(key);raw=candidates[cid]['record'];doi=normalize_doi(old['source_group']);assert doi==normalize_doi(mats[candidates[cid]['material_key']]['doi']);assert old['retention_pct']==raw['retention_pct']==ret and old['cycle_count']==raw['cycle_count']==n and old['reported_current_A_g']==raw['reported_current_A_g']==j
            approved=old.get('eligible')==1;relationship=[dict(r)for r in cycle.conn.execute('select *from source_relationships where paper_id=?',('SRC123',))]if doi==RH else[]
            if doi==RH:assert relationship[0]['status']=='sample_overlap_pending'
            s['manual_links'].append(dict(candidate_id=cid,endpoint_id=key,doi=doi,raw_source_group=old['source_group'],canonical_source_group='doi:'+doi,sample_name=old['sample_name'],retention_pct=ret,cycle_count=n,reported_current_A_g=j,positive_negative_mass_ratio=ratio,matching_basis='Exactownsample+retention+cyclecount+current; RHCmassratio explicitprimaryFig2/3 andsamelegacycurvegroup',current_formal_status='already_admitted_reported_protocol'if approved else'not_admitted_sample_overlap_pending'+('_and_mass_unbalanced_outside_main'if ratio==2 else''),not_new_endpoint=True,new_admissions=0,previous_holds=cycle.holds(key),prior_source_relationships=relationship,legacy_row=old))
        for doc in ['Coffee20_Fig7','Rice20_Fig6','Coffee20','Rice20']:
            r=dict(lit.connection.execute('select *from source_documents where document_key=?',(doc,)).fetchone());assert sha(ROOT/r['path'])==r['sha256'];s['documents'][doc]=r
        root=E.parse(ROOT/s['documents']['Rice20']['path']).getroot();fig=next(f for f in root.findall('.//fig')if clean(f.find('label'))=='Fig. 6');caption=clean(fig.find('caption'));assert '(b)'in caption and 'at a scan rate of 5 mV s−1'in caption
        rhcaps=lit.capacitances(RH);assert sorted(r['value']for r in rhcaps)==[141,155,167]
        for r in rhcaps:
            assert r['method']is None and r['current_A_g']is None and r['scan_rate_mV_s']is None
            s['protocol_corrections'].append(dict(observation_id=r['observation_id'],doi=RH,previous_method=r['method'],previous_scan_rate_mV_s=r['scan_rate_mV_s'],selected_method='CV',selected_scan_rate_mV_s=5,current_A_g=None,source_path=s['documents']['Rice20']['path'],source_sha256=s['documents']['Rice20']['sha256'],locator='ActualFig6caption panelb explicitlyscanrate5mVs; bodyP23CV +P24numbers',caption=caption,raw_capacitance_value=r['value'],author_formula='Ct=wholeloopintegral/(2*mt*v*dV), mt=positive+negative_totalactive_mass',not_GCD_0point5=True,formal_training_ready=False,source_overlap_pending=True,original_row_preserved=True))
        s['source_review_notes'].append(dict(doi=RH,legacy_relationship='references_authors_2016_RHC_study/sample_overlap_pending',prior_doi='10.1016/j.colsurfa.2016.10.009',primary_preview_url='https://www.sciencedirect.com/science/article/abs/pii/S0927775716308627',bounded_prior_findings=dict(precarbonization_C_h=[500,1],activation_C_h=[700,1],KOH_carbon_ratio=4,BET_m2_g=3263,pore_cm3_g=1.772),current_findings=dict(BET_m2_g=3185,pore_cm3_g=1.766),decision='Publicpreviewreconfirmsoldreview, neitherestablishesnorrulesoutbatch/curveresue. Keep existing sampleoverlapfreeze; no newformal RHC inputs, citationnotdeclaredprovenreuse.',current_model_fits=0,full_source_review_complete=False))
        for panel in ['CO7d','RH6c']:
            doc='Coffee20_Fig7'if panel=='CO7d'else'Rice20_Fig6';a=AXES[panel];im=Image.open(ROOT/s['documents'][doc]['path']).convert('RGB');s['panels'].append(dict(panel=panel,document_key=doc,axis=a,image_size=list(im.size),x_values=J[panel],pixel_error_y=4,pixel_error_x=2,kind='own_GCD_rate_markers',full_waveform_extracted=False))
            overlay=im.copy();draw=ImageDraw.Draw(overlay)
            for _,sample,binder,ratio,color,guesses in [r for r in SERIES if r[0]==panel]:
                assert len(guesses)==len(J[panel])
                for current,guess in zip(J[panel],guesses):
                    xp=a['xp0']+(current-a['x0'])*(a['xp1']-a['xp0'])/(a['x1']-a['x0']);xc=round(xp);yp=a['yp0']+(guess-a['y0'])*(a['yp1']-a['yp0'])/(a['y1']-a['y0']);yc=round(yp);hits=[]
                    for y in range(yc-8,yc+9):
                        xs=[x for x in range(xc-3,xc+4)if color_match(color,im.getpixel((x,y)))]
                        if xs:hits.append(dict(y=y,left=min(xs),right=max(xs),span=max(xs)-min(xs)+1,count=len(xs)))
                    width=max((x['span']for x in hits),default=0);rr=runs([x['y']for x in hits if x['span']==width]);selected=min(rr,key=lambda r:(abs(sum(r)/len(r)-yp),-len(r),r[0]))if rr else[];readable=width>=3;py=sum(selected)/len(selected)if readable else None;doi=CO if panel=='CO7d'else RH
                    aid=None
                    if panel=='CO7d'and current==1:
                        anchors=[r for r in lit.batch20_inputs('reported_coffee_sludge_2e_GCD_author_KOH')if r['sample_name']==sample and r['conditions']['binder']==binder];assert len(anchors)==1;aid=anchors[0]['observation_id']
                    name=sample+'_'+binder if ratio is None else'RHC_ratio'+str(ratio);rid='LP21_'+panel+'_'+name+'_j'+str(current)
                    r=dict(reading_id=rid,doi=doi,sample=sample,binder=binder,positive_negative_mass_ratio=ratio,document=doc,panel=panel,curve_group='doi:'+doi+'#'+panel+'#'+name,nominal_report_group='doi:'+doi+'#'+name+'#GCD_j'+str(current),x_name='reported_current_A_g',x_value=current,x_value_kind='nominal_protocol_grid_and_actual_tick_positions',x_uncertainty=2*(a['x1']-a['x0'])/(a['xp1']-a['xp0']),y_name='capacitance_F_g',y_value=y_at(a,py)if readable else None,y_lower_bound=y_at(a,py+4)if readable else None,y_upper_bound=y_at(a,py-4)if readable else None,pixel_x=xp,pixel_y=py,pixel_error_y=4,pixel_error_x=2,pixel_x_extent=[xc-3,xc+3],manual_roi_y=[yc-8,yc+8],manual_localization_guess=guess,color=color,color_candidates=hits,selected_widest_span_rows=selected,all_widest_span_runs=rr,axis=a,kind='bounded_original_marker'if readable else'occluded_marker_without_numeric_bound',author_exact_observation_id=aid,primary_for_nominal_condition=aid is None,source_overlap_pending=doi==RH,purpose_input_ready=doi==CO and readable,author_errorbars_visible=doi==CO,author_errorbars_kind='author_SD_electrochemical_pairs'if doi==CO else None,errorbar_whiskers_quantified=False,reading_bounds_not_experimental_SD_or_CI=True,current_mass_basis='author_reported_unknown_not_inferred',extraction_batch='v21',method='Actualnativecolour widestmarkerROI, ±4ypixel/±2xreading envelope. No interpolatedpoints; ROIguessesnotmeasurements; insufficient owncolour remainsnull. Printed SDseparatefromreadingbounds.')
                    s['readings'].append(r);draw.rectangle((xc-3,yc-8,xc+3,yc+8),outline='lime',width=1)
                    if py is not None:draw.line((xc-5,py,xc+5,py),fill='orange',width=1)
            overlay.save(OUT/'evidence'/(panel+'_marker_ROIs.png'))
        assert len(s['readings'])==36
        for r in s['readings']:
            if r['author_exact_observation_id']:
                anchor=next(c for c in lit.capacitances(CO)if c['observation_id']==r['author_exact_observation_id']);assert r['y_lower_bound']<=anchor['value']<=r['y_upper_bound'],(r,anchor['value'])
        s['decisions']=[dict(id='V21_canonical_DOI_and_existing_candidates',action='CanonicalDOI matching atlookup; originalsource_group andallparentrows preserved. ThreeLP20candidates areexistingendpoints; Coffee alreadyapproved, RHCremainprioroverlapfrozen. No newendpoints/admissions.'),dict(id='V21_RHC_CV5_not_GCD',action='ActualFig6b captionresolves155/167/141 asCV5mVs; noGCDcurrentguessed, originalv20methodnull preserved.'),dict(id='V21_marker_bounds_and_priorfreeze',action='36nativeGCDcaptures, CO3oldanchorsnotnewconditions; errorbarSDandpixelreadingbounds separate. RH24graphreportsinspectiononly underexisting sampleoverlapfreeze; no fabricated independent source or admission.')]
        s['cycling_snapshot']=dict(path=str(cycle.path.relative_to(ROOT)),sha256=sha(cycle.path),observations=len(allcycle),fixed_pending=len(cycle.reviewed_pending_batch()),new_endpoints=0,new_admissions=0)
    write(OUT/'curation_spec.json',s);print(dict(readings=len(s['readings']),numeric=sum(r['y_value']is not None for r in s['readings']),protocol_corrections=3,manual_links=3,candidate_audits=len(s['candidate_audits'])))

def build():
    assert sha(PARENT)==PSHA and not DB.exists()and not(OUT/'merge_manifest.json').exists();s=json.loads((OUT/'curation_spec.json').read_text('utf8'))
    with closing(ro(PARENT))as p,closing(sqlite3.connect(DB))as c:
        p.backup(c);c.row_factory=sqlite3.Row;c.execute('pragma foreign_keys=on')
        c.executescript('''create table protocol_corrections_v21(observation_id text primary key references capacitance_observations,record_json text);create table candidate_identity_audits_v21(candidate_id text primary key references test_candidates,record_json text);create table candidate_identity_links_v21(candidate_id text primary key references test_candidates,endpoint_id text,record_json text);create table rate_reviews_v21(observation_id text primary key references capacitance_observations,reading_id text references curve_samples_v8,purpose text,eligible integer,is_primary integer,record_json text);create table source_review_notes_v21(doi text primary key references reviewed_sources,record_json text);create table decisions_v21(decision_id text primary key,record_json text);''')
        for r in s['protocol_corrections']:insert(c,'protocol_corrections_v21',dict(observation_id=r['observation_id'],record_json=json.dumps(r,ensure_ascii=False)))
        for r in s['candidate_audits']:insert(c,'candidate_identity_audits_v21',dict(candidate_id=r['candidate_id'],record_json=json.dumps(r,ensure_ascii=False)))
        for r in s['manual_links']:insert(c,'candidate_identity_links_v21',dict(candidate_id=r['candidate_id'],endpoint_id=r['endpoint_id'],record_json=json.dumps(r,ensure_ascii=False)))
        for r in s['source_review_notes']:insert(c,'source_review_notes_v21',dict(doi=r['doi'],record_json=json.dumps(r,ensure_ascii=False)))
        for panel in s['panels']:
            rows=[r for r in s['readings']if r['panel']==panel['panel']];key=rows[0]['doi']+'#v21_'+panel['panel'];doc=panel['document_key']
            insert(c,'reviewed_tables',dict(table_key=key,doi=rows[0]['doi'],xml_id='v21_'+panel['panel'],caption='OwnboundGCD rate-marker '+panel['panel'],header_json=json.dumps(['sample','nominal_current_A_g','bounded_capacitance_F_g']),footnote='Nativepixelreadingbounds notauthorSD; protocol/scope andsourcepending retained',source_raw_table_id=None));insert(c,'table_source_links',dict(table_key=key,document_key=doc,locator='Original'+panel['panel']+' actualratepanel, native±4y/±2xpixelbounds'));insert(c,'extraction_units_v3',dict(table_key=key,kind='bounded_original_GCD_rate_figure',scope='Ownmarkers, notcontinuouswaveform; no newphysicaltable'))
            for i,r in enumerate(rows,1):
                oid=key+'#'+str(i)+'#2';raw=format(r['y_value'],'.12g')if r['y_value']is not None else'occluded_marker_no_numeric_bound';insert(c,'transcribed_rows',dict(table_key=key,row_ordinal=i,cells_json=json.dumps([r['sample'],str(r['x_value']),raw])));insert(c,'transcription_origins_v7',dict(table_key=key,row_ordinal=i,origin_json=json.dumps(dict(document=doc,reading_id=r['reading_id'],original_pixel=[r['pixel_x'],r['pixel_y']]))));insert(c,'curve_samples_v8',dict(reading_id=r['reading_id'],material_key=mk(r['doi'],r['sample']),document_key=doc,reading_json=json.dumps(r,ensure_ascii=False)))
                cond=dict(extraction_batch='v21',current_mass_basis=r['current_mass_basis'],graphical_reading_bounds=[r['y_lower_bound'],r['y_upper_bound']],bounds_not_experimental_CI=True,nominal_report_group=r['nominal_report_group'],physical_replicate_identity_not_proven=True,author_exact_observation_id=r['author_exact_observation_id'],primary_for_nominal_condition=r['primary_for_nominal_condition'],source_overlap_pending=r['source_overlap_pending'],binder=r['binder'],positive_negative_mass_ratio=r['positive_negative_mass_ratio'],voltage_lower_V=0,voltage_upper_V=1,capacitance_basis='author_C_or_Cg_symbol_unselected_literal_Eq1_factor4_Eq2_factor2_m_each_electrode'if r['doi']==CO else'author_Ct_GCD_total_positive_negative_active_masses',cross_source_comparable=False,physical_test_group=r['curve_group'],author_SD_errorbars_quantified=False)
                insert(c,'capacitance_observations',dict(observation_id=oid,material_key=mk(r['doi'],r['sample']),table_key=key,row_ordinal=i,column_ordinal=2,value=r['y_value'],raw_value=raw,unit='F/g',method='GCD',system='2E',electrolyte='KOH',concentration_mol_L=6,current_A_g=r['x_value'],scan_rate_mV_s=None,conditions_json=json.dumps(cond,ensure_ascii=False),status='bounded_original_figure_not_exact_author_number'if r['y_value']is not None else'occluded_marker_without_numeric_bound',source_group='doi:'+r['doi'],training_eligible=0));insert(c,'rate_reviews_v21',dict(observation_id=oid,reading_id=r['reading_id'],purpose='coffee_KOH_author_capacity'if r['doi']==CO else'rice_mass_ratio_inspection',eligible=int(r['purpose_input_ready']),is_primary=int(r['primary_for_nominal_condition']),record_json=json.dumps(r,ensure_ascii=False)))
        for r in s['decisions']:insert(c,'decisions_v21',dict(decision_id=r['id'],record_json=json.dumps(r,ensure_ascii=False)))
        c.commit()
    protected={PARENT,ROOT/s['cycling_snapshot']['path'],ROOT/'全库复检与特征补提取_20261021/full_corpus_search_native.sqlite'}|{ROOT/r['path']for r in s['documents'].values()}
    write(OUT/'protected_inputs.json',[dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p))for p in sorted(protected)]);print('Builtunsealedv21: originalrowsimmutable, no cyclingadmission or fitting')
if __name__=='__main__':
    if len(sys.argv)!=2 or sys.argv[1]not in ['curate','build']:raise SystemExit('One-use curate/build before seal only')
    globals()[sys.argv[1]]()
