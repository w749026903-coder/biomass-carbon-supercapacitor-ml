"""Primary-table/SI extraction with ready-input receipts over immutable v2."""
from pathlib import Path
import collections,csv,hashlib,io,json,sqlite3,sys
from xml.etree import ElementTree as E
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.improve_training_inputs_v2 import sha,read,write,dump,group
BASE=ROOT/'全量文献训练数据接入_v2_质量与覆盖_20261028'
OUT=ROOT/'全量文献训练数据接入_v3_玉米秸秆与烟炱_20261028'
DB=OUT/'training_data_v3.sqlite'
CORN='10.3390/ma19173741';SOOT='10.1021/acsomega.5c04992'
CP='同体系文献补充_第二批_20261017/sources/L14/fulltext.xml'
SP='数据补充_v07_20261018/sources/PMC12242611/main.xml'
SI='同体系文献补充_第二批_20261017/sources/L14/materials-4317154-supplementary.pdf'
FIG='文献全量利用复核_20261028/批次27_玉米秸秆全样品与烟炱用途辨析/evidence/materials-19-03741-g003.webp'

def native_table(path,tid):
    t=E.parse(ROOT/path).getroot().find('.//table-wrap[@id="'+tid+'"]');assert t is not None
    return [[' '.join(''.join(x.itertext()).split())for x in tr]for tr in t.findall('.//tbody/tr')]

def build():
    assert not OUT.exists(),'New release only; never rerun on an existing output'
    parent=read(BASE/'merge_manifest.json')
    for r in parent['outputs']:assert sha(ROOT/r['path'])==r['sha256'],r['path']
    expected={CP:'5d6152b62ffc7a60c5e91bfff0dee27ff5ed8bea4f27a6f333def55f11ab3955',SP:'d568254bb8792149e6025983c3583ff8baf73e4c190e2a4addba46b0534d952e',SI:'48731d223b99e543a75bc984f0f3724915fd755387ae760598b0d9c5034f9193',FIG:'a71c1c159b1cbe407d21a013271c5abe14c094ccd505a9fddb7e4c67e629c9b9'}
    for p,h in expected.items():assert sha(ROOT/p)==h,p
    OUT.mkdir();old=sqlite3.connect((BASE/'training_data_v2.sqlite').as_uri()+'?mode=ro',uri=True);c=sqlite3.connect(DB);old.backup(c);old.close();c.row_factory=sqlite3.Row;c.execute('pragma foreign_keys=on')
    c.executescript('''create table extraction_coverage_v3(doi text,unit_id text,record_json text,primary key(doi,unit_id));
    create table capacity_reports_v3(observation_id text primary key,material_key text references materials,record_json text);
    create table response_reports_v3(observation_id text primary key,record_json text);
    create table evidence_issues_v3(issue_id text primary key,record_json text);
    create table source_receipts_v3(path text primary key,sha256 text);''')
    for p,h in expected.items():c.execute('insert into source_receipts_v3 values(?,?)',(p,h))
    sources={CORN:CP,SOOT:SP};catalog={};facts=[];selected=collections.defaultdict(dict);ids=collections.defaultdict(lambda:collections.defaultdict(list));issues=[];caps=[];responses=[]
    nextid=c.execute('select max(fact_id)from facts').fetchone()[0]+1
    def material(doi,sample,stage,task_scope,synthesis):
        key='literature:v27A:'+hashlib.sha256((doi+'|'+sample+'|'+stage).encode()).hexdigest()[:24]
        m=dict(material_key=key,doi=doi,sample_name=sample,material_stage=stage,task_scope=task_scope,source_family='doi:'+doi,synthesis=synthesis,features={},source_provenance='v27A_primary_review',full_source_review_complete=False)
        catalog[doi,sample]=m;c.execute('insert into materials values(?,?,?)',(key,doi,dump(m)));return m
    def issue(code,**value):issues.append(dict(issue_id=code,**value));c.execute('insert into evidence_issues_v3 values(?,?)',(code,dump(issues[-1])))
    def fact(m,field,value,unit,locator,path=None,method=None,select=True,raw=None,**extra):
        nonlocal nextid
        path=path or sources[m['doi']]
        f=dict(fact_id=nextid,material_key=m['material_key'],field_name=field,value=value,raw_value=str(value)if raw is None else raw,
          unit=unit,method=method or field,source_path=path,source_sha256=expected[path],locator=locator,
          doi=m['doi'],sample_name=m['sample_name'],material_stage=m['material_stage'],review_status='own_primary_v27A_method_stage_qualified',
          training_eligible=0,selected_for_this_purpose=select and value is not None,**extra)
        c.execute('insert into facts values(?,?,?,?)',(nextid,m['material_key'],int(value is not None),dump(f)));facts.append(f)
        if select and value is not None:selected[m['material_key']][field]=value;ids[m['material_key']][field].append(nextid)
        nextid+=1;return f
    for doi,path in sources.items():
        assert not c.execute('select 1 from sources where doi=?',(doi,)).fetchone()
        c.execute('insert into sources values(?,?)',(doi,dump(dict(doi=doi,source_path=path,source_sha256=expected[path],review_version='v27A',full_source_review_complete=False))))
    # Source-native stage chain. Residual quartz is explicitly reported AFTER
    # acid washing, so the final material cannot enter the ordinary-carbon pool.
    corn=[]
    for temp in [600,800,1000]:
        st=[dict(stage='raw_biomass_drying',temperature_C=100,duration_h=12),dict(stage='carbonization',temperature_C=temp,duration_h=2,heating_rate_C_min=5,atmosphere='Ar'),dict(stage='acid_wash',acid='HCl',acid_wt_pct=10,temperature_C=None,duration_h=None),dict(stage='postwash_drying',temperature_C=80,duration_h=None)]
        synth=[dict(source_path=CP,sha256=expected[CP],locator='XML body p5-p7 zero based',stages=st)]
        m=material(CORN,'CS-'+str(temp),'final_biomass_carbon_with_residual_silica_before_test','native_residue_separate',synth);corn.append(m)
        material(CORN,'CS-'+str(temp)+' unwashed','unwashed_corn_char_intermediate','corn_unwashed_stage_separate',[dict(source_path=CP,sha256=expected[CP],locator='XML body p5/p7 zero based',stages=st[:2])])
    issue('corn_residual_silica',doi=CORN,locator='XML body p12 zero based',disposition='separate_native_residue_scope',reason='Acid washed material retains quartz; not inferred ash free.')
    for row in native_table(CP,'materials-19-03741-t001'):
        m=catalog[CORN,row[0]]
        for j,(field,u)in enumerate([('BET_surface_area_m2_g','m2/g'),('tplot_micropore_area_m2_g','m2/g'),('total_pore_volume_cm3_g','cm3/g'),('micropore_volume_cm3_g','cm3/g')],1):fact(m,field,float(row[j]),u,'XML table materials-19-03741-t001 row '+row[0]+' column '+str(j+1),method='N2 BET'if j==1 else 'tplot'if j in [2,4]else 'N2 total pore volume',raw=row[j],select=not(row[0]=='CS-1000'and j==1))
    # Preserve prose versus exact-table reports. The 6.70 prose statement is NOT
    # a rounding of 6.6534 at two decimals; no claim of a resolved conflict.
    for m,v in zip(corn,[8.09,7.85,6.70]):fact(m,'BET_prose_report_m2_g',v,'m2/g','XML body p15 zero based',select=False,decision='CS600/800 table precision retained; CS1000 both reports inspection-only pending original discrepancy resolution.')
    issue('corn_BET_prose_precision',doi=CORN,sample='CS-1000',table_value=6.6534,prose_value=6.70,blocked_fields=['BET_surface_area_m2_g','BET_prose_report_m2_g'],scientific_resolution=False)
    xps=[[64.43,4.16,30.51,.35,.55],[66.11,4.13,28.58,.49,.69],[61.95,5.77,31.08,.57,.63]]
    for m,rr,ram,env in zip(corn,xps,[1.004,1.006,1.011],[[77.9,17,5.1],[78.7,16.8,4.5],[74,21.4,4.6]]):
        for el,v in zip(['C','N','O','P','S'],rr):fact(m,'XPS_'+el+'_at_pct',v,'at%','Main Figure3c exact printed label '+m['sample_name'],FIG,'XPS survey atomic percent')
        fact(m,'Raman_ID_IG',ram,'ratio','SI physicalp5 TableS1 '+m['sample_name'],SI,'532nm Raman ID/IG')
        for f,v in zip(['XPS_C1s_CC_CdoubleC_envelope_pct','XPS_C1s_CN_CO_envelope_pct','XPS_C1s_OCdoubleO_envelope_pct'],env):fact(m,f,v,'%ofC1s_envelope','SI physicalp5 TableS1 '+m['sample_name'],SI,'C1s envelope fit fraction, not total carbon atomic percent')
        fact(m,'XPS_O_at_pct',rr[2],'at%','SI physicalp5 TableS1 '+m['sample_name'],SI,'XPS survey atomic percent')
    for i,m in enumerate(corn):
        rawmat=catalog[CORN,m['sample_name']+' unwashed']
        for owner,v,err in [(rawmat,[29.2,28.5,27.5][i],[.8,.6,.4][i]),(m,[22.1,21.4,19.4][i],[.7,.5,.3][i])]:
            fact(owner,'reported_gravimetric_yield_pct_of_dry_precursor',v,'%dry_precursor','XML body p14 zero based',method='Crude or postwash mass/dry precursor; five batches, ± statistic not defined')
            fact(owner,'reported_gravimetric_yield_author_plusminus',err,'percentage_point','XML body p14 zero based',select=False,method='Author ±, not declared SD/SEM')
        fact(m,'TGA_air_mass_loss_approx_pct',[55,54,45][i],'%precarbonized_sample','XML body p14 zero based',select=False,method='Approximate air TGA100-750C; different denominator from precursor yield')
    # Soot includes native inorganic constituents. All blanks are explicit null.
    soot=[]
    for sample in ['AP','PS','HZ','AP + PS','HZ + AP + PS']:soot.append(material(SOOT,sample,'native_inorganic_biomass_heater_soot_before_test','native_soot_separate',[]))
    for row in native_table(SP,'tbl1'):
        m=catalog[SOOT,row[0]]
        for el,raw in zip(['C','O','N','S','K','Na','P','Cl','Ca'],row[1:]):
            conflict=el=='N'and row[0]in ['AP','PS']
            fact(m,'EDS_'+el+'_wt_pct',float(raw)if raw else None,'wt%','XML table tbl1 literal mass% column '+el,method='EDS author mass percent; blanks are not zeros',select=not conflict,raw=raw if raw else 'blank_not_reported',table_vs_spectrum_dispute=conflict)
        total=sum(float(x)for x in row[1:]if x)
        if abs(total-100)>.15:issue('soot_EDS_sum_'+row[0].replace(' ','').replace('+','_'),doi=SOOT,sample=row[0],reported_sum=total,disposition='do_not_renormalize_or_fill_blank',scientific_resolution=False)
    issue('soot_EDS_N_table_figure',doi=SOOT,samples=['AP','PS'],reason='Table1 reports N while Figure2/prose do not identify corresponding N. N kept inspection-only; lack of visible peak is not proof of zero.',scientific_resolution=False)
    for row in native_table(SP,'tbl2'):
        m=catalog[SOOT,row[0]]
        for field,u,raw in zip(['BET_surface_area_m2_g','BJH_mean_pore_diameter_nm','total_pore_volume_cm3_g','author_average_particle_size_nm'],['m2/g','nm','cm3/g','nm'],row[1:]):
            # Particle size not presented as an independent SEM measurement;
            # avoid algebraic reuse of a likely area-derived size.
            fact(m,field,float(raw),u,'XML table tbl2 '+row[0],method='Author table SBET/BHJ spelling retained; particle-size method unspecified',select='particle'not in field,raw=raw)
    for m,ratio in zip(soot,[.91,.88,.98,.98,.99]):fact(m,'Raman_ID_IG',ratio,'ratio','XML body p24 zero based',method='Own reported Raman ID/IG by sample order')
    # Store the entire own-response context without promoting pollutant removal
    # or sensor CV metrics into a supercapacitor cycling target.
    for tid in ['tbl3','tbl4']:
        for n,row in enumerate(native_table(SP,tid)):
            rid='v27A:soot:'+tid+':'+str(n);v=dict(observation_id=rid,doi=SOOT,raw_cells=row,source_path=SP,source_sha256=expected[SP],locator='XML table '+tid+' row '+str(n),role='adsorption_context_or_own_response_not_cycling',ready_for_cycling=False)
            responses.append(v);c.execute('insert into response_reports_v3 values(?,?)',(rid,dump(v)))
    for n,row in enumerate(native_table(CP,'materials-19-03741-t002')):
        rid='v27A:corn:device_response:'+str(n);fields=['current_A_g','charge_time_s','discharge_time_s','coulombic_efficiency_pct','IR_drop_V','applied_current_A','ESR_author_ohm']
        v=dict(observation_id=rid,doi=CORN,raw_cells=row,values=dict(zip(fields,map(float,row))),source_path=CP,source_sha256=expected[CP],locator='XML Table2 row '+str(n),role='own_device_response_not_cycling_retention',ready_for_cycling=False)
        responses.append(v);c.execute('insert into response_reports_v3 values(?,?)',(rid,dump(v)))
    for n,row in enumerate(native_table(CP,'materials-19-03741-t003')):
        rid='v27A:corn:comparison_context:'+str(n);v=dict(observation_id=rid,doi=CORN,raw_cells=row,source_path=CP,source_sha256=expected[CP],locator='XML Table3 row '+str(n),role='comparison_context_not_independent_own_measurement',ready_for_cycling=False)
        responses.append(v);c.execute('insert into response_reports_v3 values(?,?)',(rid,dump(v)))
    # Dynamic-water-angle capture: exact marked time points only, no interpolation.
    from PIL import Image
    import numpy as np
    im=Image.open(ROOT/'tmp/pdfs/corn_goal/page2.png').convert('RGB');arr=np.asarray(im)
    (OUT/'evidence').mkdir();im.crop((480,190,990,615)).save(OUT/'evidence/SI_S3_review.png')
    im.crop((660,795,885,891)).resize((900,384)).save(OUT/'evidence/SI_S4_EDS_review.png')
    captures=[]
    for m,color,ys in zip(corn,['green','magenta','blue'],[[277,313,344,388,417],[332,380,418,478,507],[295,347,380,426,462]]):
        for t,x,y in zip([0,3,5,8,10],[583,686,754,855,924],ys):
            z=arr[y-5:y+6,x-5:x+6].astype(int);r,g,b=z[:,:,0],z[:,:,1],z[:,:,2]
            mask=(g>80)&(g>r*1.3)&(g>b*1.3)if color=='green'else(r>90)&(r>g*1.5)&(b>g*1.3)if color=='magenta'else(b>90)&(b>r*1.5)&(g>r*1.3)
            yy,xx=np.where(mask);assert len(yy)>12
            cy=float(yy.mean()+y-5);cx=float(xx.mean()+x-5);value=round(56-(cy-225)*16/292,1)
            detail=dict(render_scale=2,y56_px=225,y40_px=517,x0_px=583,x10_px=924,marker_center_px=[cx,cy],readout_tolerance_degree=.25,pixel_tolerance_px=3,time_min=t,not_author_SD=True)
            f=fact(m,'water_contact_angle_t'+str(t)+'min_digitized_deg',value,'degree','SI physicalp2 FigureS3 marked point '+str(t)+'min',SI,'Bounded deionized-water marker digitization; not electrolyte wetting',readout=detail)
            captures.append(dict(fact_id=f['fact_id'],**detail))
    # SI S4 printed columns: weight/atomic/Uncert are separate.
    m=catalog[CORN,'CS-800']
    for el,wt,at,err in [('C',94.21,95.63,1),('N',1.48,1.29,.6),('O',3.78,2.88,.44),('P',.29,.11,.3),('S',.24,.09,.31)]:
        fact(m,'EDS_'+el+'_wt_pct',wt,'wt%','SI physicalp2 FigureS4 printed Weight% column '+el,SI,'EDS mass percent')
        fact(m,'EDS_'+el+'_at_pct',at,'at%','SI physicalp2 FigureS4 printed Atomic% column '+el,SI,'EDS atomic percent')
        fact(m,'EDS_'+el+'_author_Uncert_pct',err,'author_Uncert%_unspecified','SI physicalp2 FigureS4 printed Uncert% column '+el,SI,'Author Uncert%, statistic and basis not inferred',select=False)
    # Capacity observations remain distinct by configuration and formula scope.
    def capacity(m,j,value,config,locator,basis,window):
        oid='v27A:'+config+':'+m['sample_name']+':'+str(j)
        cond=dict(reported_current_A_g=j,electrolyte='KOH',concentration_mol_L=1,voltage_lower_V=window[0],voltage_upper_V=window[1],reference_electrode='Ag/AgCl'if config=='3e_native_corn'else None,current_mass_basis='author_reported_unknown_not_inferred')
        v=dict(observation_id=oid,material_key=m['material_key'],doi=CORN,sample_name=m['sample_name'],source_family='doi:'+CORN,value=value,unit='F/g',conditions=cond,configuration=config,capacitance_basis=basis,source_path=CP,source_sha256=expected[CP],locator=locator,not_cycling_label=True)
        caps.append(v);c.execute('insert into capacity_reports_v3 values(?,?,?)',(oid,m['material_key'],dump(v)))
    for m,a,b in zip(corn,[21.2,53.8,36.7],[7.7,31.5,18.9]):capacity(m,1,a,'3e_native_corn','XML body p24 zero based','working_electrode_active_mass',[-1,0]);capacity(m,7,b,'3e_native_corn','XML body p25 zero based','working_electrode_active_mass',[-1,0])
    for j,v in zip([1,2,3,5,7],[18.6,16.3,14.8,13,11.7]):capacity(corn[1],j,v,'2e_corn_author_formula','XML body p29; Eq5/p11 zero based','Author calls single-electrode; Eq5 uses both-electrode total mass; retained in separate empirical formula purpose',[0,1.5])
    issue('corn_2e_basis_label_formula',doi=CORN,reason='Single-electrode text versus total-mass Eq5; own formula scope separate, no factor2/4 inference.',scientific_resolution=False)
    issue('corn_cycle_old_identity',doi=CORN,endpoint_id='candidate:B20:B2_012:1',retention_reports=[93.75,93.7],cycle_count=30000,current_A_g=2,reason='Existing device identity; Figure5e trace/baseline ambiguity and residual-silica review retained. No new cycling row/admission.',scientific_resolution=False)
    for mk,ff in selected.items():
        for f,v in ff.items():c.execute('insert into selected_features values(?,?,?,?)',(mk,f,v,dump(ids[mk][f])))
    def g(field):
        if field.startswith('EDS_'):return 'EDS'
        if 'yield'in field:return 'reported_yield'
        return group(field)
    def add_input(task,row):
        c.execute('insert into inputs values(?,?,?,?)',(task,row['row_id'],row['material_key'],dump(row)))
        for field in row['features']:
            for fid in ids[row['material_key']].get(field,[]):c.execute('insert into fact_uses values(?,?,?,?,?)',(fid,task,row['row_id'],field,'input'))
        for fid in ids[row['material_key']].get(row['target_name'],[]):c.execute('insert into fact_uses values(?,?,?,?,?)',(fid,task,row['row_id'],row['target_name'],'target'))
    for m in catalog.values():
        mk=m['material_key'];ff=selected[mk];m['features']=ff;c.execute('update materials set record_json=?where material_key=?',(dump(m),mk))
        prep={}
        for receipt in m['synthesis']:
            for st in receipt['stages']:
                for key in ['temperature_C','duration_h','heating_rate_C_min']:
                    if isinstance(st.get(key),(int,float)):prep['process__'+st['stage']+'__'+key]=st[key]
        for target,y in ff.items():
            # Crude stage targets can use their own processing only, not final wash.
            xx={f:v for f,v in ff.items()if g(f)!=g(target)};xx.update(prep)
            if not xx:continue
            task='material:'+m['task_scope']+':'+target
            row=dict(row_id=mk,material_key=mk,sample_name=m['sample_name'],source_family=m['source_family'],features=xx,target=y,target_name=target,
              excluded_target_measurement_block=g(target),conditions=dict(material_stage=m['material_stage'],material_task_scope=m['task_scope']),ready_for_training_inputs=True,ordinary_cycle_admission=False,provenance_release='v27A',independent_validation_required=True)
            add_input(task,row)
    for cap in caps:
        m=next(x for x in catalog.values()if x['material_key']==cap['material_key']);xx=dict(selected[m['material_key']]);xx.update(cap['conditions'])
        task='capacity:'+cap['configuration'];row=dict(row_id=cap['observation_id'],material_key=m['material_key'],sample_name=m['sample_name'],source_family=m['source_family'],features=xx,target=cap['value'],target_name='specific_capacitance_F_g',conditions=cap['conditions'],not_cycling_label=True,capacitance_basis=cap['capacitance_basis'],original_report=cap,ready_for_training_inputs=True)
        add_input(task,row)
    # Coverage ledger explicitly separates exhaustive numeric units from partial
    # figures and every unresolved source. It is not a whole-paper completion flag.
    coverage=[]
    for doi,path in sources.items():
        root=E.parse(ROOT/path).getroot()
        for t in root.iter('table-wrap'):
            tid=t.get('id');status='fully_structured_own_numeric'if tid in ['materials-19-03741-t001','tbl1','tbl2']else 'context_or_response_index_retained'
            v=dict(doi=doi,unit_id=tid,status=status,source_path=path,source_sha256=expected[path],full_paper_complete=False)
            coverage.append(v)
        for f in root.iter('fig'):
            v=dict(doi=doi,unit_id=f.get('id'),status='partial_printed_labels_only'if doi==CORN and f.get('id','').endswith('f003')else 'scope_reviewed_continuous_curves_pending',source_path=path,source_sha256=expected[path],full_paper_complete=False);coverage.append(v)
    for unit,status in [('SI_TableS1','fully_structured_own_numeric'),('SI_FigureS3','15_marked_points_bounded_digitization'),('SI_FigureS4','printed_EDS_columns_structured'),('SI_FiguresS1_S2_S5_S9','continuous_curves_pending')]:coverage.append(dict(doi=CORN,unit_id=unit,status=status,source_path=SI,source_sha256=expected[SI],full_paper_complete=False))
    for v in coverage:c.execute('insert into extraction_coverage_v3 values(?,?,?)',(v['doi'],v['unit_id'],dump(v)))
    uses=collections.defaultdict(list)
    for u in c.execute('select *from fact_uses'):uses[u['fact_id']].append(dict(task=u['task'],row_id=u['row_id'],feature=u['feature'],role=u['role']))
    for f in facts:
        fid=f['fact_id'];uu=uses.get(fid,[])
        disposition='connected_to_training_inputs'if uu else 'nonpoint_or_missing_retained'if f['value']is None else 'primary_evidence_conflict_or_metadata_not_predictor'
        u=dict(fact_id=fid,disposition=disposition,uses=uu,training_connected=bool(uu),fact=f)
        c.execute('insert into usage_ledger values(?,?,?)',(fid,disposition,dump(u)))
    s=read(BASE/'summary.json');total=c.execute('select count(*)from facts').fetchone()[0];numeric=c.execute('select sum(numeric)from facts').fetchone()[0]
    used=c.execute('select count(distinct fact_id)from fact_uses join facts using(fact_id)where numeric=1').fetchone()[0]
    counts={}
    for task, in c.execute('select distinct task from inputs'):
        rows=[json.loads(r[0])for r in c.execute('select record_json from inputs where task=?',(task,))];n=len({r['source_family']for r in rows});counts[task]=dict(rows=len(rows),source_families=n,source_holdout_validation_possible=n>=2)
    s.update(version='training_inputs_v3_v27A',parent_database_sha256=sha(BASE/'training_data_v2.sqlite'),total_facts=total,numeric_facts=numeric,nonpoint_facts=total-numeric,
      numeric_facts_connected_to_training_inputs=used,numeric_fact_connection_rate=used/numeric,remaining_unconnected_numeric_facts=numeric-used,material_registrations=c.execute('select count(*)from materials').fetchone()[0],reviewed_sources=c.execute('select count(*)from sources').fetchone()[0],
      new_material_registrations=len(catalog),new_material_facts=len(facts),new_numeric_material_facts=sum(f['value']is not None for f in facts),new_connected_fact_ids=[f['fact_id']for f in facts if uses.get(f['fact_id'])],new_capacity_reports=len(caps),new_sources=2,
      new_model_fits=0,new_cycling_admissions=0,task_counts=counts,usage_counts=dict(collections.Counter(r[0]for r in c.execute('select disposition from usage_ledger'))))
    c.execute("update metadata set value_json=?where key='summary'",(dump(s),));c.commit();c.close()
    for name,value in [('summary',s),('new_facts',facts),('new_materials',list(catalog.values())),('new_capacity_reports',caps),('response_context',responses),('scientific_issues',issues),('extraction_coverage',coverage),('curve_marker_captures',captures)]:write(OUT/(name+'.json'),value)
    write(OUT/'source_family_rules.json',read(BASE/'source_family_rules.json'))
    protected={r['path']:r['sha256']for r in parent['outputs']};protected[BASE.relative_to(ROOT).as_posix()+'/merge_manifest.json']=sha(BASE/'merge_manifest.json');protected.update(read(BASE/'protected_inputs.json'));protected.update(expected);write(OUT/'protected_inputs.json',protected)
    pointer=dict(version='training_inputs_v3_v27A',directory=OUT.relative_to(ROOT).as_posix(),database_file=DB.name,sha256=sha(DB),entry='data.training_ready',old_v2_entry_retained='data.training_current',new_model_fits=0)
    write(OUT/'entrypoint_snapshot.json',pointer);write(ROOT/'data/current_training_ready.json',pointer)
    print(dump({k:s[k]for k in ['new_material_registrations','new_material_facts','new_numeric_material_facts','numeric_facts','numeric_facts_connected_to_training_inputs','new_capacity_reports']}))

if __name__=='__main__':build()
