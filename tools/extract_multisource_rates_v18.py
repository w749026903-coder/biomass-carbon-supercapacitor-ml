"""One-use bounded native-pixel rate transcriptions; no waveform interpolation."""
from pathlib import Path
from contextlib import closing
import collections,json,sqlite3,sys
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tools'))
from extract_multisource_tables_v17 import NPC,RH,MIX,sha,write,ro,insert,mk
from extract_peel_graphs_v16 import runs
OUT=ROOT/'文献全量利用复核_20261027/批次18_淀粉稻壳混合碳倍率与循环再核';DB=OUT/'literature_material_pool_v18.sqlite'
PARENT=ROOT/'文献全量利用复核_20261027/批次17_多来源全样表格与方法审查/literature_material_pool_v17.sqlite';PSHA='247adec30392c77695b085a81223baa943c400eb5e7b7a8e3e22d679f135524a'
IMAGES={'Starch18_ActualFig5':ROOT/'文献扩充_大批补齐_20261018/sources/SUP_040/assets/molecules-29-02532-g005.jpg','Rice17_Fig10':ROOT/'文献扩充_大批补齐_20261018/sources/SUP_043/assets/ao2c07932_0011.jpg','Mixed17_Fig6':ROOT/'文献全量利用复核_20261027/批次17_多来源全样表格与方法审查/evidence/Mixed17/nanomaterials-14-01368-g006.jpg'}
AXES={'5g':dict(x0=0,xp0=551,x1=10,xp1=716,y0=50,yp0=175,y1=300,yp1=15),'5h':dict(x0=0,xp0=552,x1=10,xp1=717,y0=50,yp0=365,y1=300,yp1=215),'5i':dict(x0=0,xp0=552,x1=10,xp1=717,y0=50,yp0=571,y1=300,yp1=410),'10d':dict(x0=0,xp0=375.5,x1=30,xp1=600.5,y0=0,yp0=438,y1=80,yp1=264),'6c':dict(x0=0,xp0=90.5,x1=20,xp1=333.5,y0=150,yp0=509,y1=550,yp1=310.5)}
CURRENTS={'5g':[.5,1,1.5,3,5,10],'5h':[.5,1,1.5,3,5,10],'5i':[.5,1,1.5,3,5,10],'10d':[.5,1,2,3,4,5,7,10,15,20,30],'6c':[.5,1,2,4,6,8,10,20]}
ROI_OVERRIDES={('5h','NPC-700-2-2',1):[243,251]}
SERIES=[('5g','CS-700','black',[159,138,126,119,102,90]),('5g','NPC-700-3.5-1','cyan',[180,168,156,142,130,109]),('5g','NPC-700-3.5-2','orange',[255,235,230,215,205,190]),('5g','NPC-700-3.5-3','salmon',[245,220,220,197,185,173]),('5h','NPC-700-1-2','black',[237,224,215,205,197,189]),('5h','NPC-700-2-2','cyan',[262,250,234,222,216,205]),('5h','NPC-700-3.5-2','orange',[255,237,228,217,207,193]),('5h','NPC-700-4-2','salmon',[250,229,222,211,204,194]),('5i','NPC-600-2-2','black',[195,154,146,134,126,119]),('5i','NPC-700-2-2','cyan',[263,250,234,222,216,205]),('5i','NPC-800-2-2','orange',[260,227,213,148,147,144]),('5i','NPC-900-2-2','salmon',[198,156,146,134,128,119]),('10d','RH-1000','black',[41,38,34,31,29,27,24.5,19.5,16,13,7.5]),('10d','RHPC-1000','red',[78.7,74.5,71,69,67,66,64,61,56,53,46]),('6c','ABC','black',[370,347,310,277,255,239,225,165]),('6c','ABPC-1','red',[378,386,378,350,328,308,291,212]),('6c','ABPC-2','green',[426,423,388,353,333,296,283,210]),('6c','ABPC-4','blue',[529,473,434,382,344,313,283,180])]
def color_match(color,rgb):
    r,g,b=rgb
    return {'black':max(rgb)<155 and max(rgb)-min(rgb)<35,'cyan':min(g,b)-r>55 and b>g-30,'orange':r>160 and 65<g<200 and b<100 and r-g>50 and g-b>35,'salmon':r>160 and r-max(g,b)>55 and b-g>5,'red':r-max(g,b)>60,'green':g-max(r,b)>40,'blue':b-max(r,g)>55}[color]
def y_at(a,p):return a['y0']+(p-a['yp0'])*(a['y1']-a['y0'])/(a['yp1']-a['yp0'])
def capture():
    images={k:Image.open(p).convert('RGB')for k,p in IMAGES.items()};reads=[]
    assert [im.size for im in images.values()]==[(740,608),(627,473),(754,575)]
    for panel,sample,color,guesses in SERIES:
        a=AXES[panel];doi=NPC if panel.startswith('5')else RH if panel.startswith('10')else MIX;doc='Starch18_ActualFig5'if doi==NPC else'Rice17_Fig10'if doi==RH else'Mixed17_Fig6'
        assert len(guesses)==len(CURRENTS[panel])
        for j,guess in zip(CURRENTS[panel],guesses):
            xp=a['xp0']+(j-a['x0'])*(a['xp1']-a['xp0'])/(a['x1']-a['x0']);xc=round(xp);yp=a['yp0']+(guess-a['y0'])*(a['yp1']-a['yp0'])/(a['y1']-a['y0']);yc=round(yp);candidates=[]
            ylo,yhi=ROI_OVERRIDES.get((panel,sample,j),[yc-8,yc+8])
            for y in range(ylo,yhi+1):
                xs=[x for x in range(xc-3,xc+4)if color_match(color,images[doc].getpixel((x,y)))]
                if xs:candidates.append(dict(y=y,left=min(xs),right=max(xs),span=max(xs)-min(xs)+1,count=len(xs)))
            width=max((r['span']for r in candidates),default=0)
            rr=runs([r['y']for r in candidates if r['span']==width]);selected=min(rr,key=lambda r:(abs(sum(r)/len(r)-yp),-len(r),r[0]))if rr else[];py=sum(selected)/len(selected)if selected else None
            readable=width>=3;value=y_at(a,py)if readable else None;lower=y_at(a,py+4)if readable else None;upper=y_at(a,py-4)if readable else None
            reads.append(dict(reading_id='LP18_Fig'+panel+'_'+sample+'_j'+format(j,'g'),doi=doi,sample=sample,document=doc,panel='Fig'+panel,curve_group='doi:'+doi+':Fig'+panel+':'+sample,nominal_report_group='doi:'+doi+':'+sample+':3E:GCD:j'+format(j,'g'),x_name='reported_current_A_g',x_value=j,x_value_kind='nominal_tick_grid_position_crosschecked_with_own_GCD_or_rate_protocol_not_individually_printed_marker_label',x_uncertainty=2*abs((a['x1']-a['x0'])/(a['xp1']-a['xp0'])),x_lower_bound=j-2*abs((a['x1']-a['x0'])/(a['xp1']-a['xp0'])),x_upper_bound=j+2*abs((a['x1']-a['x0'])/(a['xp1']-a['xp0'])),y_name='capacitance_F_g',y_value=value,y_lower_bound=lower,y_upper_bound=upper,y_uncertainty=(upper-lower)/2 if readable else None,pixel_x=xp,pixel_y=py,pixel_error_y=4,pixel_error_x=2,pixel_x_extent=[xc-3,xc+3],manual_roi_y=[ylo,yhi],manual_roi_reason='Exclude legend cyan line y239; actual j1 marker y245..249 visually resolved in native grid'if(panel,sample,j)in ROI_OVERRIDES else'localized original marker, not y-value inference',manual_localization_guess=guess,color=color,color_candidates=candidates,selected_widest_span_rows=selected,all_widest_span_runs=rr,axis=a,kind='bounded_original_marker'if readable else'occluded_marker_without_numeric_bound',visible_fragment_only=not readable,method='Original-colour widest span inside manually localized native-pixel marker ROI; +/-4y and nominal +/-2x reading envelopes. If width<3 or no identifiable own-colour marker, target and bounds remain null, not an interval based on a localization guess. Not experimental SD/CI. No interpolation or fitting. Nominal report grouping is not proof of identical physical replicate.',extraction_batch='v18',retention_point_admitted=False))
    assert len(reads)==126
    return reads

def curate():
    assert not DB.exists()and not(OUT/'curation_spec.json').exists()and not(OUT/'merge_manifest.json').exists()and sha(PARENT)==PSHA
    from data.literature_v17 import open_literature_database
    with open_literature_database(PARENT,PSHA)as p:
        anchors={(r['doi'],r['sample_name'],r['current_A_g']):r for r in p.auxiliary_gcd('3e')if r['doi']in [NPC,RH,MIX]};assert len(anchors)==3
        reads=capture();groups=collections.defaultdict(list)
        for r in reads:
            k=(r['doi'],r['sample'],r['x_value']);groups[k].append(r)
            r['author_exact_observation_id']=anchors.get(k,{}).get('observation_id');r['target_purpose']='reported_native_silica_rice_3e_GCD'if r['sample']=='RH-1000'else'explicit_ordinary_3e_GCD_with_graphical_values'
            if k in anchors:r['author_reported_value']=anchors[k]['value'];r['author_anchor_within_graph_envelope']=r['y_lower_bound']<=anchors[k]['value']<=r['y_upper_bound'];assert r['author_anchor_within_graph_envelope'],(k,r['y_value'],anchors[k]['value'],r['y_lower_bound'],r['y_upper_bound'])
        for k,rows in groups.items():
            good=[r for r in rows if r['y_value']is not None];intersect_low=max((r['y_lower_bound']for r in good),default=None);intersect_high=min((r['y_upper_bound']for r in good),default=None);overlap=bool(good)and intersect_low<=intersect_high
            primary=max(good or rows,key=lambda r:abs((r['axis']['yp1']-r['axis']['yp0'])/(r['axis']['y1']-r['axis']['y0'])))
            for r in rows:r.update(primary_for_nominal_condition=r is primary,duplicate_report_count=len(rows),numeric_duplicate_reports=len(good),duplicate_envelopes_overlap=overlap,duplicate_intersection=[intersect_low,intersect_high],ready_for_point_purpose=overlap and r['y_value']is not None)
        write(OUT/'curation_spec.json',dict(readings=reads,documents=[dict(key=k,path=p.relative_to(ROOT).as_posix(),sha256=sha(p))for k,p in IMAGES.items()],cycle_review=json.loads((OUT/'ABPC4_cycle_configuration_review.json').read_text('utf8')),decisions=[dict(id='LP18_axis_and_precision',decision='Five native panels calibrated separately. Starch points are0.5/1/1.5/3/5/10, Rice0.5/1/2/3/4/5/7/10/15/20/30, Mixed0.5/1/2/4/6/8/10/20; do not assume evenly spaced or round1.5 to2. Original pixel bounds, nominalx uncertainty retained.'),dict(id='LP18_repeats',decision='Two starch series repeated across panels; all raw captures retained. Choose higher native vertical resolution only if envelopes overlap; otherwise freeze affected graph condition. Author anchors retain original IDs and qualifiers, never overwrite with graph values.'),dict(id='LP18_scope',decision='RH1000 before silica removal is a separately declared native-silica material purpose; RHPC1000 washed material separate. StandardBET remains missing due printedm3/g; optional missingBET does not invalidate GCD report. No CVcycling label/current transfer.'),dict(id='LP18_cycle_configuration',decision='ABPC4role95.08CE/~100ret supported but cyclingconfiguration unresolved:caption3E vs2Econtext/conclusion. Selectedcycleconfiguration/window unknown; no automatic cyclingadmission. Keep old candidate originalrecord and add currentreview.'),dict(id='LP18_isolation',decision='All source/material/curve/response/auxiliary/cycling payloads held out by wholeDOI/prior-workfamily; numerical markers are not independent papers or replicates. No fit.')],model_fits=0,full_source_review_complete=False))
    for key,p in IMAGES.items():
        im=Image.open(p).convert('RGB');draw=ImageDraw.Draw(im)
        for r in reads:
            if r['document']!=key:continue
            x,y=r['pixel_x'],r['pixel_y']
            if r['y_value']is not None:draw.rectangle((x-3,y-4,x+3,y+4),outline='purple',width=1)
            else:draw.rectangle((x-3,r['manual_roi_y'][0],x+3,r['manual_roi_y'][1]),outline='orange',width=1)
        im.resize((im.width*2,im.height*2)).save(OUT/'evidence'/(key+'_marker_bounds.png'))
    print(json.dumps(dict(captures=len(reads),nominal_conditions=len(groups),duplicate_captures=len(reads)-len(groups),unresolved_overlap=[list(k)for k,v in groups.items()if not v[0]['duplicate_envelopes_overlap']]),ensure_ascii=False))

def build():
    assert not DB.exists()and not(OUT/'merge_manifest.json').exists()and sha(PARENT)==PSHA
    spec=json.loads((OUT/'curation_spec.json').read_text('utf8'))
    with closing(ro(PARENT))as parent,closing(sqlite3.connect(DB))as c:
        parent.backup(c);c.row_factory=sqlite3.Row;c.execute('pragma foreign_keys=on');c.executescript('''create table purpose_reviews_v18(observation_id text primary key references capacitance_observations,reading_id text references curve_samples_v8,purpose text,is_primary integer,eligible integer,record_json text);create table decisions_v18(decision_id text primary key,record_json text);create table source_reviews_v18(doi text primary key references reviewed_sources,record_json text);create table cycle_reviews_v18(candidate_id text primary key references test_candidates,record_json text);create table source_binding_corrections_v18(table_key text primary key references reviewed_tables,old_document_key text references source_documents,new_document_key text references source_documents,record_json text);create table figure_identity_resolution_v18(document_key text primary key references source_documents,printed_label text,record_json text);''')
        for d in spec['documents']:
            old=c.execute('select path,sha256 from source_documents where document_key=?',(d['key'],)).fetchone();assert sha(ROOT/d['path'])==d['sha256']
            if old:assert tuple(old)==(d['path'],d['sha256'])
            else:assert d['key']=='Starch18_ActualFig5';insert(c,'source_documents',dict(document_key=d['key'],doi=NPC,path=d['path'],sha256=d['sha256'],role='original_figure_printed_Figure5'))
        # Versioned correction: native printed labels, never XML ordinal as figure ID.
        import xml.etree.ElementTree as E
        from extract_source_series_v13 import clean
        main=ROOT/'文献扩充_大批补齐_20261018/sources/SUP_040/main.xml';root=E.parse(main).getroot();figs=root.findall('.//fig')
        for ordinal,f in enumerate(figs,1):
            label=clean(f.find('label'));href=f.find('.//graphic').get('{http://www.w3.org/1999/xlink}href');oldkey='Starch17_Fig'+str(ordinal);path=main.parent/'assets'/href
            assert c.execute('select path from source_documents where document_key=?',(oldkey,)).fetchone()[0]==path.relative_to(ROOT).as_posix()
            insert(c,'figure_identity_resolution_v18',dict(document_key=oldkey,printed_label=label,record_json=json.dumps(dict(xml_id=f.get('id'),XML_ordinal=ordinal,printed_label=label,href=href,path=path.relative_to(ROOT).as_posix(),sha256=sha(path),basis='Native label and graphic href, not ordinal; Scheme1 precedes Figure1',source_XML=main.relative_to(ROOT).as_posix(),source_XML_sha256=sha(main)),ensure_ascii=False)))
        for n in [3,7]:
            f=next(f for f in figs if clean(f.find('label'))=='Figure '+str(n));p=main.parent/'assets'/f.find('.//graphic').get('{http://www.w3.org/1999/xlink}href');insert(c,'source_documents',dict(document_key='Starch18_ActualFig'+str(n),doi=NPC,path=p.relative_to(ROOT).as_posix(),sha256=sha(p),role='original_figure_printed_Figure'+str(n)))
        for unit,n in [('Fig3_Raman',3),('Fig3_XPS',3),('Fig7_EDLC',7),('Fig7_cycle',7)]:
            key=NPC+'#'+unit;old=c.execute('select document_key from table_source_links where table_key=?',(key,)).fetchone()[0];insert(c,'source_binding_corrections_v18',dict(table_key=key,old_document_key=old,new_document_key='Starch18_ActualFig'+str(n),record_json=json.dumps(dict(reason='v17 XML ordinal was mistaken for printed figure number because Scheme1 precedes Figure1; numerical values unchanged',old_document_key=old,new_document_key='Starch18_ActualFig'+str(n),printed_label='Figure '+str(n),original_table_and_fact_rows_preserved=True),ensure_ascii=False)))
        c.execute('''create view resolved_table_sources_v18 as select l.table_key,coalesce(x.new_document_key,l.document_key) as document_key,d.path,d.sha256,l.locator,l.document_key as original_document_key,case when x.table_key is null then 0 else 1 end as binding_corrected from table_source_links l left join source_binding_corrections_v18 x using(table_key)join source_documents d on d.document_key=coalesce(x.new_document_key,l.document_key)''')
        for panel in ['Fig5g','Fig5h','Fig5i','Fig10d','Fig6c']:
            reads=[r for r in spec['readings']if r['panel']==panel];doi=reads[0]['doi'];key=doi+'#v18_'+panel
            insert(c,'reviewed_tables',dict(table_key=key,doi=doi,xml_id='v18_'+panel,caption='Bounded original GCD rate-marker '+panel,header_json=json.dumps(['sample','nominal_current_A_g','bounded_capacitance_F_g']),footnote='Figure transcription with native pixel bounds; not a new physical experimental table',source_raw_table_id=None));insert(c,'table_source_links',dict(table_key=key,document_key=reads[0]['document'],locator='Original'+panel+' rate-markers; original±4y/nominal±2x pixel envelopes and report duplicates retained'));insert(c,'extraction_units_v3',dict(table_key=key,kind='bounded_original_rate_figure_transcription',scope='All visible own markers, not continuous waveform interpolation; nominalreportgroup not provenphysicalreplicate'))
            for i,r in enumerate(reads,1):
                obs=key+'#'+str(i)+'#2';raw=format(r['y_value'],'.12g')if r['y_value']is not None else'occluded_marker_no_numeric_bound';insert(c,'transcribed_rows',dict(table_key=key,row_ordinal=i,cells_json=json.dumps([r['sample'],str(r['x_value']),raw])));insert(c,'transcription_origins_v7',dict(table_key=key,row_ordinal=i,origin_json=json.dumps(dict(document=r['document'],panel=panel,reading_id=r['reading_id'],original_pixel=[r['pixel_x'],r['pixel_y']]))));insert(c,'curve_samples_v8',dict(reading_id=r['reading_id'],material_key=mk(doi,r['sample']),document_key=r['document'],reading_json=json.dumps(r,ensure_ascii=False)))
                cond=dict(extraction_batch='v18',current_mass_basis='author_reported_unknown_not_inferred',nominal_current_coordinate_origin=r['x_value_kind'],current_graphical_bounds=[r['x_lower_bound'],r['x_upper_bound']],capacitance_basis='author_reported_3E_no_further_mass_unification',voltage_lower_V=-.9 if doi==RH else-1,voltage_upper_V=.1 if doi==RH else 0,reference_electrode='Hg/HgO',target_stage='fresh_reported_GCD_rate_test',nominal_report_group=r['nominal_report_group'],physical_replicate_identity_not_proven=True,graphical_reading_bounds=[r['y_lower_bound'],r['y_upper_bound']],bounds_not_experimental_CI=True,author_exact_observation_id=r['author_exact_observation_id'],primary_for_nominal_condition=r['primary_for_nominal_condition'])
                insert(c,'capacitance_observations',dict(observation_id=obs,material_key=mk(doi,r['sample']),table_key=key,row_ordinal=i,column_ordinal=2,value=r['y_value'],raw_value=raw,unit='F/g',method='GCD',system='3E',electrolyte='KOH',concentration_mol_L=6,current_A_g=r['x_value'],scan_rate_mV_s=None,conditions_json=json.dumps(cond,ensure_ascii=False),status='bounded_original_figure_not_exact_author_number'if r['y_value']is not None else'occluded_marker_without_numeric_bound',source_group='doi:'+doi,training_eligible=0));insert(c,'purpose_reviews_v18',dict(observation_id=obs,reading_id=r['reading_id'],purpose=r['target_purpose'],is_primary=int(r['primary_for_nominal_condition']),eligible=int(r['ready_for_point_purpose']),record_json=json.dumps(r,ensure_ascii=False)))
        for d in spec['decisions']:insert(c,'decisions_v18',dict(decision_id=d['id'],record_json=json.dumps(d,ensure_ascii=False)))
        insert(c,'cycle_reviews_v18',dict(candidate_id='LP17_ABPC4',record_json=json.dumps(spec['cycle_review'],ensure_ascii=False)))
        insert(c,'scientific_issues',dict(issue_id='LP18_ABPC4_cycle_configuration',doi=MIX,sample_name='ABPC-4',issue_json=json.dumps(dict(kind='cycling_configuration_conflict',action=spec['cycle_review']),ensure_ascii=False)))
        for doi in [NPC,RH,MIX]:insert(c,'source_reviews_v18',dict(doi=doi,record_json=json.dumps(dict(scope='All selected five own rate-marker panels; rawduplicate and authoranchor links',full_source_review_complete=False,remaining='Other adsorption/CV/GCD/EIS/spectra and source evidence remain; cycling disputes not removed'),ensure_ascii=False)))
        c.commit()
    protected={PARENT,*IMAGES.values(),ROOT/'循环稳定性数据库_v0.25_芒果核皮革循环准入_20261026/cycling_v0_25.sqlite'};write(OUT/'protected_inputs.json',dict(files=[dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p),bytes=p.stat().st_size)for p in sorted(protected)]));print('Built unsealedv18; no formal cycling admission or fit')

if __name__=='__main__':
    if len(sys.argv)!=2 or sys.argv[1]not in ['curate','build']:raise SystemExit('One-use on new unsealed release only')
    globals()[sys.argv[1]]()
