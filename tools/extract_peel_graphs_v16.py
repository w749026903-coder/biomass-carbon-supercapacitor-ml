"""Original-pixel bounded GCD rate transcriptions; explicit author-anchor links."""
from pathlib import Path
from contextlib import closing
import collections,json,sqlite3,sys
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tools'))
from extract_peel_date_v15 import PE,DA,PE_DIR,PATHS,sha,write,ro,insert,mk
OUT=ROOT/'文献全量利用复核_20261027/批次16_花椒全样倍率与椰枣叶工况';DB=OUT/'literature_material_pool_v16.sqlite'
PARENT=ROOT/'文献全量利用复核_20261026/批次15_花椒皮籽与椰枣叶/literature_material_pool_v15.sqlite';PSHA='c0e8fa48157a74b025e10ad06565db3499ffa7d08a42a917742d4b04f4560ba4'
IMAGES={'Peel16_Fig8':PE_DIR/'figures/nanomaterials-14-00836-g008.jpg','Peel16_Fig9':PE_DIR/'figures/nanomaterials-14-00836-g009.jpg','Date16_Fig5':PARENT.parent/'evidence/nanomaterials-12-00122-g005.jpg'}
AXES={'8c':dict(x0=0,xp0=74,x1=16,xp1=341,y0=100,yp0=522.5,y1=200,yp1=336.5),'9c':dict(x0=0,xp0=75,x1=16,xp1=340,y0=50,yp0=496.5,y1=200,yp1=339.5),'5e':dict(x0=0,xp0=56,x1=6,xp1=332,y0=0,yp0=866,y1=180,yp1=624),'5f':dict(x0=4,xp0=426,x1=20,xp1=708,y0=0,yp0=866,y1=100,yp1=624)}
CURRENTS=[1,3,5,7,9,11,13,15]
SERIES=[('8c','PAC-600','black',[187,170,162,154,147,141,142,137]),('8c','PAC-700','red',[211,201,188,182,177,173,169,165]),('8c','PAC-800','blue',[198,185,177,172,168,164,161,158]),('8c','PAC-900','pink',[189,180,174,170,166,164,162,160]),('8c','PAC-1000','green',[155,142,134,126,120,114,107,101]),('9c','SAC-600','black',[220,196,187,180,175,170,165,161]),('9c','SAC-700','red',[177,162,155,151,147,143,141,139]),('9c','SAC-800','blue',[130,122,118,116,113,110,108,105]),('9c','SAC-900','pink',[86,78,76,74,72,71,70,69]),('9c','SAC-1000','green',[28,23,22,21,20,19,18,18]),('5e','NaOH-activated','black',[156.8,142,133,126,108,92,83.5]),('5f','NaOH-activated','black',[83.5,77,72,68,64,61,58,55.9])]

def signal(color,rgb):
    r,g,b=rgb
    return {'black':max(rgb)<155 and max(rgb)-min(rgb)<30,'red':r-max(g,b)>50,'blue':b-max(r,g)>50,'pink':min(r,b)-g>40,'green':g-max(r,b)>35}[color]

def runs(values):
    result=[]
    for n in values:
        if result and n==result[-1][-1]+1:result[-1].append(n)
        else:result.append([n])
    return result

def at_y(a,y):return a['y0']+(y-a['yp0'])*(a['y1']-a['y0'])/(a['yp1']-a['yp0'])

def capture():
    images={k:Image.open(p).convert('RGB')for k,p in IMAGES.items()};assert [im.size for im in images.values()]==[(741,1174),(738,1161),(741,911)]
    reads=[]
    for panel,sample,color,rough in SERIES:
        a=AXES[panel];doi=PE if panel[0]in '89'else DA;doc='Peel16_Fig'+panel[0]if doi==PE else'Date16_Fig5';image=images[doc]
        currents=CURRENTS if doi==PE else[.4,.6,.8,1,2,4,6]if panel=='5e'else[6,8,10,12,14,16,18,20]
        assert len(currents)==len(rough)
        for current,guess in zip(currents,rough):
            xp=a['xp0']+(current-a['x0'])*(a['xp1']-a['xp0'])/(a['x1']-a['x0']);xc=round(xp);yp=a['yp0']+(guess-a['y0'])*(a['yp1']-a['yp0'])/(a['y1']-a['y0']);yc=round(yp);candidates=[]
            for y in range(yc-7,yc+8):
                xs=[x for x in range(xc-4,xc+5)if signal(color,image.getpixel((x,y)))]
                if xs:candidates.append(dict(y=y,count=len(xs),left=min(xs),right=max(xs),span=max(xs)-min(xs)+1))
            assert candidates,(sample,current,'No colour evidence; inspect rather than infer from neighbouring points')
            width=max(r['span']for r in candidates);assert width>=3,(sample,current,width)
            best=runs([r['y']for r in candidates if r['span']==width]);selected=min(best,key=lambda rr:(abs(sum(rr)/len(rr)-yp),-len(rr),rr[0]));center=sum(selected)/len(selected);value=at_y(a,center);lower=at_y(a,center+4);upper=at_y(a,center-4)
            reads.append(dict(reading_id='LP16_Fig'+panel+'_'+sample+'_j'+format(current,'g'),doi=doi,sample=sample,document=doc,panel='Fig'+panel,curve_group='doi:'+doi+':Fig'+panel+':'+sample,x_name='reported_current_A_g',x_value=current,x_uncertainty=0,x_value_origin='Nominal author GCD legend labels and corresponding rate markers; zero denotes nominal-label coordinate, not measurement accuracy',y_name='capacitance_F_g',y_value=value,y_lower_bound=lower,y_upper_bound=upper,y_uncertainty=(upper-lower)/2,pixel_x=xp,pixel_y=center,selected_marker_column=xc,pixel_x_extent=[xc-4,xc+4],manual_roi_y=[yc-7,yc+7],manual_localization_guess=guess,color=color,color_candidates=candidates,selected_widest_span_rows=selected,all_widest_span_runs=best,axis=a,pixel_error_y=4,kind='bounded_original_marker',method='Widest horizontal own-colour span; if disconnected equal widths, nearest localized marker run. Original-pixel +/-4y reading envelope, not SD/SEM/CI or model error. No curve fitting/interpolation.',physical_test_group='doi:'+doi+':'+sample+':3E:GCD:j'+format(current,'g'),not_independent_from_same_material_current_reports=True,retention_point_admitted=False,extraction_batch='v16'))
    assert len(reads)==95
    return reads

def curate():
    assert not DB.exists()and not(OUT/'curation_spec.json').exists()and not(OUT/'merge_manifest.json').exists()and sha(PARENT)==PSHA
    from data.literature_v15 import open_literature_database
    with open_literature_database(PARENT,PSHA)as old:
        exact=[r for r in old.auxiliary_gcd('3e')if r['doi']in [PE,DA]];assert len(exact)==20
        anchors={(r['doi'],r['sample_name'],r['current_A_g']):r for r in exact};reads=capture()
        for r in reads:
            key=(r['doi'],r['sample'],r['x_value']);r['author_exact_observation_id']=anchors.get(key,{}).get('observation_id');r['is_primary_for_nominal_condition']=not(r['panel']=='Fig5e'and r['x_value']==6)
            if key in anchors:
                r['author_reported_value']=anchors[key]['value'];r['author_anchor_within_graph_envelope']=r['y_lower_bound']<=r['author_reported_value']<=r['y_upper_bound'];assert r['author_anchor_within_graph_envelope'],(key,r['y_value'],r['author_reported_value'],r['y_lower_bound'],r['y_upper_bound'])
        six=[r for r in reads if r['doi']==DA and r['x_value']==6];assert len(six)==2 and max(r['y_lower_bound']for r in six)<=min(r['y_upper_bound']for r in six)
        extra=[r['observation_id']for r in exact if r['sample_name']=='CO2-activated'];assert len(extra)==1
    spec=dict(readings=reads,extra_exact_control_observation_ids=extra,documents=[dict(key=k,path=p.relative_to(ROOT).as_posix(),sha256=sha(p),doi=DA if k.startswith('Date')else PE)for k,p in IMAGES.items()],decisions=[dict(id='LP16_axes',decision='Four panels independently calibrated from original tick centres; no scale transfer between peel/seed or low/high current panels.'),dict(id='LP16_bounds',decision='Original-pixel +/-4y envelopes are graphical reading limits, not experimental uncertainty. Approximate values explicitly separated from author-reported points; unknown denominator remains author A/g.'),dict(id='LP16_repeats',decision='SixA/g appears inDateFig5e/f; keep both raw captures but primary f chosen by higher vertical pixels perF/g, not capacitance or model performance. Nineteen exact anchor conditions retain old IDs; CO2 j1 control retained.'),dict(id='LP16_scope',decision='These are3E fresh GCD-rate conditions, not2E cycling endpoints. Same source/material/current copies not independent; allauxiliary/material/response/curve payloads held out as whole DOI family. No new source, material or cycle admission.')],remaining='Continuous CV/GCD/N2/EIS/spectral waveforms and other document evidence remain; extraction of these rate-marker panels is not full-source completion',model_fits=0)
    write(OUT/'curation_spec.json',spec);print(json.dumps(dict(captures=len(reads),nominal_graph_conditions=sum(r['is_primary_for_nominal_condition']for r in reads),author_anchor_reports=sum(bool(r['author_exact_observation_id'])for r in reads),extra_exact_controls=len(extra),same_condition_duplicate=1),ensure_ascii=False))

def build():
    assert not DB.exists()and not(OUT/'merge_manifest.json').exists()and sha(PARENT)==PSHA
    spec=json.loads((OUT/'curation_spec.json').read_text('utf8'))
    with closing(ro(PARENT))as parent,closing(sqlite3.connect(DB))as c:
        parent.backup(c);c.row_factory=sqlite3.Row;c.execute('pragma foreign_keys=on');c.executescript('''create table purpose_reviews_v16(observation_id text primary key references capacitance_observations,reading_id text references curve_samples_v8,is_primary integer,record_json text);create table decisions_v16(decision_id text primary key,record_json text);create table source_reviews_v16(doi text primary key references reviewed_sources,record_json text);''')
        for d in spec['documents']:assert sha(ROOT/d['path'])==d['sha256'];insert(c,'source_documents',dict(document_key=d['key'],doi=d['doi'],path=d['path'],sha256=d['sha256'],role='original_own_GCD_rate_figure'))
        for panel in ['Fig8c','Fig9c','Fig5e','Fig5f']:
            reads=[r for r in spec['readings']if r['panel']==panel];r0=reads[0];key=r0['doi']+'#v16_'+panel
            insert(c,'reviewed_tables',dict(table_key=key,doi=r0['doi'],xml_id='v16_'+panel,caption='Bounded original GCD rate-marker transcription '+panel,header_json=json.dumps(['sample','nominal_current_A_g','bounded_capacitance_F_g']),footnote='Derived figure transcription, not a new native experimental table; original four-pixel reading envelope retained',source_raw_table_id=None));insert(c,'table_source_links',dict(table_key=key,document_key=r0['document'],locator='Original '+panel+' rate-marker panel; calibrated native pixels, bounds and repeat links in curve_samples_v8'));insert(c,'extraction_units_v3',dict(table_key=key,kind='bounded_original_rate_figure_transcription',scope='All own visible nominal rate markers; author anchors and duplicate6A/g kept as linked reports'))
            for rownum,r in enumerate(reads,1):
                obs=key+'#'+str(rownum)+'#2';raw=format(r['y_value'],'.12g');insert(c,'transcribed_rows',dict(table_key=key,row_ordinal=rownum,cells_json=json.dumps([r['sample'],str(r['x_value']),raw])));insert(c,'transcription_origins_v7',dict(table_key=key,row_ordinal=rownum,origin_json=json.dumps(dict(document=r['document'],panel=panel,original_pixel=[r['pixel_x'],r['pixel_y']],reading_id=r['reading_id']),ensure_ascii=False)));insert(c,'curve_samples_v8',dict(reading_id=r['reading_id'],material_key=mk(r['doi'],r['sample']),document_key=r['document'],reading_json=json.dumps(r,ensure_ascii=False)))
                cond=dict(extraction_batch='v16',current_mass_basis='author_reported_unknown_not_inferred',capacitance_basis='author_reported_single_working_electrode_not_further_mass_unified',voltage_lower_V=-1 if r['doi']==PE else 0,voltage_upper_V=0 if r['doi']==PE else 1,reference_electrode='Hg/HgO'if r['doi']==PE else'Ag/AgCl',reference_electrode_dissent=None if r['doi']==PE else'SCE bodyP19 dissent; methodP8/actualFig5/6 supportAgAgCl',target_stage='fresh_reported_GCD_rate_test',physical_test_group=r['physical_test_group'],graphical_reading_bounds=[r['y_lower_bound'],r['y_upper_bound']],graphical_bounds_not_experimental_CI=True,author_exact_observation_id=r['author_exact_observation_id'],primary_for_nominal_condition=r['is_primary_for_nominal_condition'])
                insert(c,'capacitance_observations',dict(observation_id=obs,material_key=mk(r['doi'],r['sample']),table_key=key,row_ordinal=rownum,column_ordinal=2,value=r['y_value'],raw_value=raw,unit='F/g',method='GCD',system='3E',electrolyte='KOH'if r['doi']==PE else'H2SO4',concentration_mol_L=6 if r['doi']==PE else 1,current_A_g=r['x_value'],scan_rate_mV_s=None,conditions_json=json.dumps(cond,ensure_ascii=False),status='bounded_original_figure_not_exact_author_number',source_group='doi:'+r['doi'],training_eligible=0));insert(c,'purpose_reviews_v16',dict(observation_id=obs,reading_id=r['reading_id'],is_primary=int(r['is_primary_for_nominal_condition']),record_json=json.dumps(dict(eligible_for_explicit_graphical_3e_purpose=True,ordinary_exact_profile_unchanged=True,source_group='doi:'+r['doi'],physical_test_group=r['physical_test_group'],author_exact_observation_id=r['author_exact_observation_id'],lower_bound=r['y_lower_bound'],upper_bound=r['y_upper_bound']),ensure_ascii=False)))
        for r in spec['decisions']:insert(c,'decisions_v16',dict(decision_id=r['id'],record_json=json.dumps(r,ensure_ascii=False)))
        for doi in [PE,DA]:insert(c,'source_reviews_v16',dict(doi=doi,record_json=json.dumps(dict(scope='Allrate markers inFig8c/9c orFig5e/f; repeatedviews andauthoranchors linked',remaining=spec['remaining'],full_source_review_complete=False,new_source=False),ensure_ascii=False)))
        c.commit()
    protected={PARENT,*PATHS.values(),*IMAGES.values(),PARENT.parent/'evidence/DatePalm_original_assets.zip',PE_DIR/'supplementary_package.zip',ROOT/'循环稳定性数据库_v0.25_芒果核皮革循环准入_20261026/cycling_v0_25.sqlite'};write(OUT/'protected_inputs.json',dict(files=[dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p),bytes=p.stat().st_size)for p in sorted(protected)]));print('Built unsealed v16; exact ordinary profiles and original sources unchanged')

if __name__=='__main__':
    if len(sys.argv)!=2 or sys.argv[1]not in ['curate','build']:raise SystemExit('One-use curate/build on a new unsealed release')
    globals()[sys.argv[1]]()
