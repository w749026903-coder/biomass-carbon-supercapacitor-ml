"""One-use extraction of newly obtained official wheat-husk assets; original releases immutable."""
from pathlib import Path
from contextlib import closing
import json,math,sqlite3,sys,xml.etree.ElementTree as E
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tools'))
from extract_onion_composite_v8 import sha,write,ro,insert,mk
OUT=ROOT/'文献全量利用复核_20261028/批次25_麦壳原图与循环程序复核';DB=OUT/'literature_material_pool_v25.sqlite'
PARENT=ROOT/'文献全量利用复核_20261028/批次24_糠醛渣食物气凝胶柚皮与麦壳全样品/literature_material_pool_v24.sqlite';PSHA='d31e97b73cd52eac2cbbc26aae6f03ce6f46b4644c70234366df14c1904b6ea8'
SOURCE=ROOT/'三电极端点扩充_20261018/new_sources/PMC9655081/main.xml';SSHA='add2688eb017b236e0c7b46f6c04c3ac9a076483ad448c04f202037271059a25'
DOI='10.3390/nano12213804';CYCLE=ROOT/'循环稳定性数据库_v0.27_林业含灰双电极准入_20261028/cycling_v0_27.sqlite'
AXES={'Fig7d':dict(x0=0,xp0=172.5,x1=20,xp1=338.5,y0=0,yp0=386.5,y1=600,yp1=232.5), 'Fig8b':dict(x0=0,xp0=407.5,x1=20,xp1=668.5,y0=0,yp0=242.5,y1=350,yp1=42.5)}
SERIES=[('Fig7d','HPC-700','red',[402,385,376,369,346]),('Fig7d','HPC-800','green',[210,170,157,149,134]),('Fig7d','HPC-900','blue',[199,157,139,131,122]),('Fig8b','HPC-700','red',[346,329,309,293,262])]
J=[1,2,5,10,20]

def color_match(color,rgb):
    r,g,b=rgb
    return {'red':r-max(g,b)>65,'green':g-max(r,b)>55,'blue':b-max(r,g)>55}[color]
def y_at(a,p):return a['y0']+(p-a['yp0'])*(a['y1']-a['y0'])/(a['yp1']-a['yp0'])
def locate(im,a,j,guess,color):
    xp=a['xp0']+j*(a['xp1']-a['xp0'])/20;yc=round(a['yp0']+guess*(a['yp1']-a['yp0'])/(a['y1']-a['y0']));xc=round(xp);hits=[]
    for y in range(yc-5,yc+6):
        xs=[x for x in range(xc-2,xc+3)if color_match(color,im.getpixel((x,y)))]
        if xs:hits.append(dict(y=y,count=len(xs)))
    assert hits,('No actual matching colour',j,guess,color)
    best=max(h['count']for h in hits);rows=[h['y']for h in hits if h['count']==best];yp=sum(rows)/len(rows)
    return xp,yp,hits,[xc-2,yc-5,xc+2,yc+5]

def curate():
    assert sha(PARENT)==PSHA and sha(SOURCE)==SSHA and not DB.exists()and not(OUT/'curation_spec.json').exists()
    from data.literature_v24 import open_literature_database
    x=E.parse(SOURCE).getroot();figs={''.join(f.find('label').itertext()).strip():f for f in x.findall('.//fig')};assert len(figs)==9
    s=dict(parent_sha256=PSHA,doi=DOI,figures=[],readings=[],protocol_bindings=[],decisions=[],full_source_review_complete=False)
    notes={'Scheme 1':'Wheat husk -> molten-salt prechar -> KOH activated carbon; no numeric SEM/porosity inference.', 'Figure 1':'HPC-700/800/900 own sheet SEM and scale bars; no particle-size scalar guessed.', 'Figure 2':'Three final carbons TEM/HRTEM/SAED; no numeric spacing inferred from stripe image.', 'Figure 3':'MHPC-700/800/900 vs NHPC-700 control; final and prechar properties not inherited.', 'Figure 4':'XRD/C1s/O1s spectra; body peak/element claims already in v24. No fitted peak fractions invented.', 'Figure 5':'All7 final/prechar N2 and PSD series; raw axes and scales kept, continuous curves not yet extracted.', 'Figure 6':'3E own sample comparison and CV scan-rate series; not counted as new GCD rate conditions.', 'Figure 7':'3E GCD/actual rate markers and EIS; 15 markers transcribed, 6 previous author anchors.', 'Figure 8':'2E symmetric 0..1V GCD/current legend1/2/5/10/20, 5 capacity markers, Ragone and 30000-cycle retention;8d is retention not CE. No individually plotted cycle voltage inset.'}
    for label,f in figs.items():
        n=1 if label=='Scheme 1'else int(label.split()[-1]);name='nanomaterials-12-03804-'+('sch001'if label=='Scheme 1'else'g'+str(n).zfill(3))+'.jpg';p=OUT/'evidence'/name;assert p.is_file()
        s['figures'].append(dict(document_key='HP25_'+('Scheme1'if label=='Scheme 1'else'Fig'+str(n)),doi=DOI,path=p.relative_to(ROOT).as_posix(),sha256=sha(p),label=label,caption=' '.join(''.join(f.find('caption').itertext()).split()),scope_visually_inspected=True,full_waveform_extracted=False,note=notes[label]))
    with open_literature_database(PARENT,PSHA)as lit:
        caps=lit.capacitances(DOI)
        for r in caps:
            if r['system']=='2E_symmetric':
                assert r['conditions']['voltage_lower_V']is None and r['conditions']['voltage_upper_V']is None
                s['protocol_bindings'].append(dict(observation_id=r['observation_id'],previous_conditions=r['conditions'],selected_window_V=[0,1],document_key='HP25_Fig8',source_path=next(d['path']for d in s['figures']if d['label']=='Figure 8'),source_sha256=next(d['sha256']for d in s['figures']if d['label']=='Figure 8'),locator='ActualFigure8(a)2E Voltage(V)0..1; MainP7+P18 same symmetric cell GCD programme',not_3e_inheritance=True,not_individual_cycle_trace=True))
        for panel,sample,color,guesses in SERIES:
            doc='HP25_Fig7'if panel=='Fig7d'else'HP25_Fig8';d=next(d for d in s['figures']if d['document_key']==doc);im=Image.open(ROOT/d['path']).convert('RGB');a=AXES[panel];overlay=im.copy();draw=ImageDraw.Draw(overlay);sy='3E'if panel=='Fig7d'else'2E_symmetric'
            for j,guess in zip(J,guesses):
                xp,yp,hits,roi=locate(im,a,j,guess,color);v=y_at(a,yp);anchor=[c for c in caps if c['system']==sy and c['sample_name']==sample and c['current_A_g']==j and c['status']=='own_reported'];assert len(anchor)<=1
                rid='HP25_'+panel+'_'+sample+'_j'+str(j);nom='doi:'+DOI+'#'+sample+'#'+sy+'GCD'+str(j)
                r=dict(reading_id=rid,doi=DOI,sample=sample,document=doc,panel=panel,curve_group='doi:'+DOI+'#'+panel+'#'+sample,nominal_report_group=nom,extraction_batch='v25',x_name='reported_current_A_g',x_value=j,x_uncertainty=2*(a['x1']-a['x0'])/(a['xp1']-a['xp0']),x_value_kind='explicit1/2/5/10/20GCDlegends_and_actual_rate_markers',y_name='capacitance_F_g',y_value=v,y_lower_bound=y_at(a,yp+4),y_upper_bound=y_at(a,yp-4),pixel_x=xp,pixel_y=yp,pixel_error_y=4,pixel_error_x=2,localization_guess_not_measurement=guess,color=color,color_hits=hits,manual_roi=roi,axis=a,image_size=list(im.size),kind='bounded_original_marker',author_exact_observation_id=anchor[0]['observation_id']if anchor else None,system=sy,method='GCD',purpose='wheat_husk_3e_reported_capacity'if panel=='Fig7d'else'wheat_husk_2e_factor4_total_active_mass_Cs',reading_bounds_not_experimental_SD_or_CI=True,no_interpolation=True,physical_replicate_identity_not_proven=True,current_mass_basis='author_reported_unknown_not_inferred')
                if anchor:assert r['y_lower_bound']<=anchor[0]['value']<=r['y_upper_bound'],(rid,v,anchor[0]['value'])
                s['readings'].append(r);draw.rectangle(roi,outline='lime');draw.line((xp-4,yp,xp+4,yp),fill='orange')
            overlay.save(OUT/'review'/(panel+'_'+sample+'_marker_ROIs.png'))
    s['decisions']=[dict(decision_id='V25_wheat_original_window',doi=DOI,previous='v24: nine original figures unavailable,2Ewindow unknown',current='OfficialPMC9655081package obtains9originaljpg; actualFig8a binds0..1V to2EsymmetricGCD, not3Einheritance.',remaining='Actualcycle8dhas no GCDinset; bindingusesapplicablecommonGCDprogramme andMainP18. Specificcyclingadmissionseparatelyreviewed,year2022not2023main.'),dict(decision_id='V25_rate_bounds_and_identity',doi=DOI,current='20native markers,8alreadyreported anchors,12 additional nominal conditions; 3E andfactor4totalmass2ECs separated. ±4y/±2xpixelenvelopes notauthorSD; no waveforminterpolation or 20independent experiments.',remaining='Continuousspectra/sorption/CV/GCD/EIS andotherRagone/CE/retentionmarkersnotallnumericallyextracted; sourcepartial.')]
    write(OUT/'curation_spec.json',s);print(dict(figures=9,rate_captures=len(s['readings']),existing_anchors=sum(bool(r['author_exact_observation_id'])for r in s['readings']),protocol_bindings=len(s['protocol_bindings'])))

def build():
    assert not DB.exists()and not(OUT/'merge_manifest.json').exists()and sha(PARENT)==PSHA;s=json.loads((OUT/'curation_spec.json').read_text('utf8'))
    with closing(ro(PARENT))as p,closing(sqlite3.connect(DB))as c:
        p.backup(c);c.row_factory=sqlite3.Row;c.executescript('pragma foreign_keys=on;create table figure_reviews_v25(document_key text primary key references source_documents,record_json text);create table rate_reviews_v25(observation_id text primary key references capacitance_observations,reading_id text unique references curve_samples_v8,purpose text,record_json text);create table protocol_bindings_v25(observation_id text primary key references capacitance_observations,record_json text);create table decisions_v25(decision_id text primary key,record_json text);')
        for d in s['figures']:
            insert(c,'source_documents',dict(document_key=d['document_key'],doi=DOI,path=d['path'],sha256=d['sha256'],role='official_primary_article_figure'));insert(c,'figure_reviews_v25',dict(document_key=d['document_key'],record_json=json.dumps(d,ensure_ascii=False)))
        for r in s['protocol_bindings']:insert(c,'protocol_bindings_v25',dict(observation_id=r['observation_id'],record_json=json.dumps(r,ensure_ascii=False)))
        for r in s['decisions']:insert(c,'decisions_v25',dict(decision_id=r['decision_id'],record_json=json.dumps(r,ensure_ascii=False)))
        for panel in ['Fig7d','Fig8b']:
            rs=[r for r in s['readings']if r['panel']==panel];doc=rs[0]['document'];key=DOI+'#v25_'+panel
            insert(c,'reviewed_tables',dict(table_key=key,doi=DOI,xml_id='v25_'+panel,caption='Own wheat-husk rate-marker panel '+panel,header_json=json.dumps(['sample','nominal_current_A_g','bounded_capacitance_F_g']),footnote='Graphical reading envelope notSD/CI. Eight author anchors not new conditions.',source_raw_table_id=None));insert(c,'table_source_links',dict(table_key=key,document_key=doc,locator='Actual'+panel+'; ±4y/±2x nativepixelbound'));insert(c,'extraction_units_v3',dict(table_key=key,kind='bounded_original_GCD_rate_figure',scope='Own discrete rate markers, not full waveform or physical table'))
            for i,r in enumerate(rs,1):
                oid=key+'#'+str(i)+'#2';raw=format(r['y_value'],'.12g');insert(c,'transcribed_rows',dict(table_key=key,row_ordinal=i,cells_json=json.dumps([r['sample'],str(r['x_value']),raw])));insert(c,'transcription_origins_v7',dict(table_key=key,row_ordinal=i,origin_json=json.dumps(dict(document=doc,reading_id=r['reading_id'],original_pixel=[r['pixel_x'],r['pixel_y']]))));insert(c,'curve_samples_v8',dict(reading_id=r['reading_id'],material_key=mk(DOI,r['sample']),document_key=doc,reading_json=json.dumps(r,ensure_ascii=False)))
                cond=dict(extraction_batch='v25',current_mass_basis=r['current_mass_basis'],graphical_reading_bounds=[r['y_lower_bound'],r['y_upper_bound']],bounds_not_experimental_CI=True,nominal_report_group=r['nominal_report_group'],physical_test_group=r['nominal_report_group'],author_exact_observation_id=r['author_exact_observation_id'],primary_for_nominal_condition=r['author_exact_observation_id']is None,binder='PTFE',mass_loading_mg_cm2=3,voltage_lower_V=0,voltage_upper_V=1,reference_electrode='Ag/AgCl'if r['system']=='3E'else None,capacitance_basis='I_dt_over_working_active_m_dV'if r['system']=='3E'else'4I_dt_over_total_two_electrode_active_m_dV',cross_source_comparable=r['system']=='3E',physical_replicate_identity_not_proven=True,voltage_source='OwnactualFig7abc'if r['system']=='3E'else'OwnactualFig8a')
                insert(c,'capacitance_observations',dict(observation_id=oid,material_key=mk(DOI,r['sample']),table_key=key,row_ordinal=i,column_ordinal=2,value=r['y_value'],raw_value=raw,unit='F/g',method='GCD',system=r['system'],electrolyte='H2SO4',concentration_mol_L=1,current_A_g=r['x_value'],scan_rate_mV_s=None,conditions_json=json.dumps(cond,ensure_ascii=False),status='bounded_original_figure_not_exact_author_number',source_group='doi:'+DOI,training_eligible=0));insert(c,'rate_reviews_v25',dict(observation_id=oid,reading_id=r['reading_id'],purpose=r['purpose'],record_json=json.dumps(r,ensure_ascii=False)))
        c.commit()
    protected={PARENT,SOURCE,CYCLE,ROOT/'全库复检与特征补提取_20261021/full_corpus_search_native.sqlite'}|{ROOT/d['path']for d in s['figures']}|{OUT/'evidence/PMC9655081_primary_assets.zip'}
    write(OUT/'protected_inputs.json',[dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p),bytes=p.stat().st_size)for p in sorted(protected)]);print('Unsealedv25, no old rows edited or model fitting')
if __name__=='__main__':
    action=sys.argv[1]if len(sys.argv)==2 else''
    if action not in ['curate','build']:raise SystemExit('One-use curate/build only before sealing')
    globals()[action]()
