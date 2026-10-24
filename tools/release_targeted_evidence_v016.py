"""Explicit reviewed evidence choices and bounded v0.16 build/check/seal.

No automated scientific admission, source movement, fitting or old-script rerun.
Use build once, verify read-only, then seal once after reports are complete.
"""
from pathlib import Path
from contextlib import closing
import collections,copy,csv,hashlib,importlib.util,json,math,sqlite3,sys,xml.etree.ElementTree as E,zipfile
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'tools')]
BATCH=ROOT/'补证与测量口径复核_v016_20261024'
PARENT=ROOT/'循环稳定性数据库_v0.15_表图与待补证复核_20261024'
OUT=ROOT/'循环稳定性数据库_v0.16_补证与口径复核_20261024'
DB=OUT/'cycling_v0_16.sqlite'
def read(p):return json.loads(p.read_text('utf8'))
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n','utf8')
def dump(x):return json.dumps(x,ensure_ascii=False,sort_keys=True)
def module(path,name):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m
def evidence(path,locator,excerpt,version,kind='native_table_or_text'):
    p=ROOT/path
    return dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p),locator=locator,
        evidence_excerpt=excerpt,document_version=version,evidence_kind=kind)

def choices():
    """Values below were read from the actual main/SI/figures by the agent."""
    si=BATCH.relative_to(ROOT).as_posix()+'/retrieved/Fe_SN6C_SI.docx'
    fe='legacy:R081_CY01';k='incoming:ADD_016_T01';h='incoming:ADD_016_T02'
    fig5=BATCH.relative_to(ROOT).as_posix()+'/retrieved/LWCA_formal_Fig5.png'
    fig6=BATCH.relative_to(ROOT).as_posix()+'/retrieved/LWCA_formal_Fig6.png'
    pre='新增文献整理_20261020/originals/ADD_016.pdf'
    es1=evidence(si,'Table S1; Fe-SN6C@900 row','C 73.52, N 8.47, S 2.56, H 1.482; all wt%.','published_article_supplement')
    es2=evidence(si,'Table S2; Fe-SN6C@900 row','BET542 m2/g; Vtotal0.3315, Vmicro0.2055, Vmeso0.1027 cm3/g.','published_article_supplement')
    es3=evidence(si,'Table S3; Fe-SN6C@900 row','Pyridinic35.34, pyrrolic23.67, graphitic31.80, oxidized9.19%; within N1s species, not bulk atomic percent.','published_article_supplement')
    es7=evidence(si,'Fig S7(a), final Fe-SN6C@900; word/media/image7.tiff','EDS wt%/at%: C75.12/81.36; N5.24/4.87; O15.22/12.37; S2.15/0.87; Fe2.27/0.53. Panel b is Fe-SC@900, not this sample.','published_article_supplement','reviewed_image_numbers')
    sels=[]
    def add(key,field,value,ev,reason,scope='material',operation='fill_qualified_evidence'):
        sels.append(dict(endpoint_id=key,field_name=field,after=value,evidence=[dict(e,fields=[field]) for e in ev],reason=reason,scope=scope,operation=operation))
    for f,v in [('bulk_C_wt_pct_v16',73.52),('bulk_S_wt_pct_v16',2.56),('bulk_H_wt_pct_v16',1.482)]:
        add(fe,f,v,[es1],'Own final sample elemental analysis; not EDS or XPS. No oxygen-by-difference inference.')
    for f,v in [('total_pore_volume_cm3_g',.3315),('micropore_volume_cm3_g',.2055),('mesopore_volume_cm3_g',.1027)]:
        add(fe,f,v,[es2],'Own final sample SI row; source/main identity checked. BET542 and bulkN8.47 already present and retained.')
    add(fe,'N1s_relative_species_pct_v16',dict(pyridinic=35.34,pyrrolic=23.67,graphitic=31.80,oxidized=9.19),[es3],'Relative chemical species fractions only; excluded from whole-material XPS N and default predictors.')
    for el,wt,at in [('C',75.12,81.36),('N',5.24,4.87),('O',15.22,12.37),('S',2.15,.87),('Fe',2.27,.53)]:
        for basis,val in [('wt_pct',wt),('at_pct',at)]:
            add(fe,'EDS_'+el+'_'+basis+'_v16',val,[es7],'FigS7(a) final sample EDS; no conversion to bulk or XPS and no chemical-state claim.')
    add(fe,'Fe_state_review_v16',dict(final_Fe_detected=True,measurement='SEM-EDX',wt_pct=2.27,atomic_pct=.53,chemical_state=None,Fe_free_claim_supported=False),[es7],'Presence is resolved; EDS does not establish metallic Fe/oxide/single sites or final removal.')
    for key,pan,n,o,c,p in [(k,'a',1.07,7.53,91.04,.35),(h,'b',.66,4.97,94.19,.18)]:
        ef=evidence(fig5,'Formal Fig5('+pan+'), Element content(at.%) table',f'C{c}, O{o}, N{n}, P{p}; explicit at.%.','version_of_record','reviewed_image_numbers')
        for field,val in [('XPS_N_reported_pct',n),('XPS_O_reported_pct',o),('XPS_percentage_basis','atomic_explicit'),('XPS_C_at_pct_v16',c),('XPS_P_at_pct_v16',p)]:
            add(key,field,val,[ef],'Own initial sample formal publisher figure; explicit XPS atomic percent.')
        proto=evidence(pre,'PDF p5, section2.5; p10 and p20 Fig6(f)','3E:6M KOH, Hg/HgO reference; own cycling10A/g5000. Preprint only; formal method not accessed.','ResearchSquare_v1_preprint')
        for field,val in [('electrolyte','KOH'),('concentration_mol_L',6),('reference_electrode','Hg/HgO')]:
            add(key,field,val,[proto],'Qualified preprint protocol value; source-version flag and formal protocol hold prevent training use.',scope='test')
        add(key,'protocol_document_version_v16','ResearchSquare_rs2596680_v1_not_formal_verified',[proto],'Do not relabel the preprint method as verified formal method.',scope='test')
        pore=evidence(pre,'PDF p7 Table1; p8 own-sample discussion','Table1 surface areas headed cm2/g, while p8 calls BET1780/1996m2/g; pore volumes cm3/g.','ResearchSquare_v1_preprint')
        add(key,'BET_m2_g',1780 if key==k else 1996,[pore],
            'Select the author explicit body p8 rounded m2/g value, not a conversion of the conflicting cm2/g table or an inferred exact1780.145/1996.116. Formal table remains unverified.')
        vals=(.773,.598,.175,1.737) if key==k else (.98,.72,.27,2.33)
        for field,val in zip(['total_pore_volume_cm3_g','micropore_volume_cm3_g','mesopore_volume_cm3_g','average_pore_diameter_nm'],vals):
            add(key,field,val,[pore],'Unambiguous volume/diameter units; own preprint sample, formal table still unverified. Not approval.')
        cand=dict(table_surface_unit='cm2/g',body_BET_unit='m2/g',BET_table_raw=1780.145 if key==k else 1996.116,
            micropore_surface_raw=1488.46 if key==k else 1617.412,mesopore_surface_raw=291.685 if key==k else 378.704,
            body_BET_raw=1780 if key==k else 1996,canonical_surface_area_selected='explicit_body_rounded_m2_g_not_converted_table',table_exact_area_selected=False)
        add(key,'surface_area_unit_conflict_v16',cand,[pore],'Retain contradictory table units/raw exact values; selected BET is the explicit rounded body m2/g report, not a silent table conversion.')
    ef6=evidence(fig6,'Formal Fig6(f), K-LWCA3/H-LWCA labelled endpoints and inset','5000 cycles; K-LWCA3 94.11%; H-LWCA81.37%; inset Voltage -1.0..0.0V without reference identity.','version_of_record','reviewed_image_numbers')
    for key in [k,h]:
        window=evidence(pre,'PDF p5 section2.5 reference and p20 Fig6(f) own cycle inset','Own 3E method Hg/HgO; Fig6(f) cycle inset -1..0V, same two sample tests.','ResearchSquare_v1_preprint','reviewed_method_and_own_waveform')
        for field,val in [('cycle_voltage_lower_V',-1),('cycle_voltage_upper_V',0)]:
            add(key,field,val,[window,ef6],'Qualified preprint own cycle inset/method binding, corroborated by formal inset endpoints; formal reference protocol still not verified.',scope='test')
        add(key,'formal_cycle_window_unreferenced_v16',dict(lower_V=-1,upper_V=0,reference_electrode_on_axis=None),[ef6],'Formal inset endpoints observed; formal reference not stated on axis. Selected referenced window is explicitly qualified preprint binding, not formal method verification.',scope='test')
        add(key,'publication_version_evidence_v16',dict(doi='10.1007/s00226-023-01515-0',published_online='2023-12-02',issue_year=2024,formal_images=[3,5,6],formal_fulltext_available=False),[ef6],'Same study/group; formal figure and preprint are not independent sources.',scope='test')
    oldlabel=evidence(pre,'PDF p10 results paragraph and p20 Fig6','Text gives H-LWCA81.3%; own graphic labels81.37%; competing values preserved.','ResearchSquare_v1_preprint')
    add(h,'retention_candidates_v16',[dict(value_pct=81.3,relation='eq',origin='preprint_results_text',selected_canonical=True),dict(value_pct=81.37,relation='eq',origin='formal_Fig6f_label',selected_canonical=False)],
        [oldlabel,ef6],'No selection by recency, rounding, or favourable performance. Formal results text/author record required.',scope='test')
    return sels,dict(si=si,es7=es7,fig5=fig5,fig6=fig6,pre=pre,ef6=ef6)

def build():
    if DB.exists() or (OUT/'merge_manifest.json').exists():raise FileExistsError('Do not rebuild sealed or existing v0.16.')
    pointer=read(BATCH/'parent_pointer.json');assert pointer['version_directory']==PARENT.name and sha(PARENT/pointer['database_file'])==pointer['sha256']
    parent=module(PARENT/'ml_data.py','_v16_build_parent')
    with parent.Database() as db:
        rows={r['endpoint_id']:r for r in db.fetch('all_review').rows};contract=copy.deepcopy(db.contract)
        reviews={r['endpoint_id']:r for r in db.reviewed_pending_batch(True)}
    sels,ev=choices();changes=[]
    for s in sels:
        row=rows[s['endpoint_id']];s['material_key']=row['material_key_v11'];before=row.get(s['field_name'])
        assert before is None,(s['endpoint_id'],s['field_name'],before)
        changes.append(dict(s,before=before))
    latest=[]
    def review(key,disposition,issues,resolutions,reason,evidence_list):
        r=copy.deepcopy(reviews[key]);r.update(disposition=disposition,open_issues=issues,resolution=resolutions,reason=reason,
            evidence=[dict(e,fields=['review_disposition_v16']) for e in evidence_list],approved_profiles=[],review_version='v0.16')
        latest.append(r)
    review('legacy:R081_CY01','partly_resolved_final_Fe_present_phase_pending',['final_Fe_chemical_state_and_current_scope'],
        ['Official SI retrieved and identity matched.','Final Fe is detected by EDS2.27wt%/0.53at%; removal/absence uncertainty narrowed.','Own pore volumes, bulkC/S/H and EDS channels extracted.'],
        '附件已取得，最终样品Fe检出已确认；EDS不能判断独立金属/氧化物或配位位点，不能直接判纯碳或直接排除。保留材料相态范围冻结，原约102%标签仍为近似。',[ev['es7']])
    for key in ['incoming:ADD_016_T01','incoming:ADD_016_T02']:
        issues=['formal_protocol_vs_preprint_not_verified']
        if key.endswith('T02'):issues.append('retention_text81_3_vs_figure81_37')
        review(key,'partly_resolved_formal_figures_protocol_units_pending',issues,
            ['Formal publisher identity and own figures3/5/6 obtained.','XPS atomic percentage is explicit.','Preprint protocol and volumes extracted with version qualifier; formal numeric BET not assumed.'],
            '正式页与公开图核定同一研究和样品，K-LWCA3原名称已正确。预印本方法/自身循环图及孔容已限定版本补录；BET选正文明确的1780/1996m2/g，不把表头cm2/g精确值换算入库，矛盾留存。正式方法尚未核验；H-LWCA另有正文81.3与图81.37需核。原标签/年份/分组不改。',[ev['ef6'],evidence(ev['pre'],'PDF p5/7/8/10/20','Own preprint protocol, pore table and label discussion.','ResearchSquare_v1_preprint')])
    for key,why in [('legacy:R033_CY01','aGCL SI真实链接已核定，但本次403，未取得正文外新条件证据。'),('candidate:TE008','方法15的官方API本次仅返回题录XML，无originalText/body；不能据此补参比。')]:
        r=copy.deepcopy(reviews[key]);r.update(review_version='v0.16',resolution=r['resolution']+[why],reason=r['reason']+' 本轮：'+why)
        latest.append(r)
    OUT.mkdir(exist_ok=True)
    contract.update(version='v0.16',database_file=DB.name,parent_directory=PARENT.name,parent_database_sha256=pointer['sha256'],
        storage_layout='Small immutable-parent delta plus new SI text and explicit reviewed image readings.',model_fits=0,
        field_names_v16=sorted({s['field_name'] for s in changes}),preparation_only=True,all_records_admitted=False,
        field_semantics_v16={'Fe_EDS':'Final sample presence, not chemical state; never XPS/bulk replacement.',
            'LWCA_protocol':'Qualified ResearchSquare preprint values; not verified formal protocol, not admission.',
            'LWCA_BET':'Select explicit body rounded1780/1996m2/g; conflicting table exact numbers/units retained, not converted. Preprint version hold remains.',
            'LWCA_H_retention':'Preprint text81.3 vs formal figure81.37 stored as competing evidence; canonical81.3 remains frozen.',
            'N1s_species':'Percent within N1s chemical species, not total elemental percentage.',
            'new_custom_fields':'Audit/candidate only; no automatic addition to model predictor whitelist.'})
    write(OUT/'data_contract.json',contract)
    with closing(sqlite3.connect(DB)) as c:
        c.execute('pragma foreign_keys=on')
        c.executescript('''create table record_keys_v16(endpoint_id text primary key);
        create table field_changes_v16(endpoint_id text references record_keys_v16,field_name text,before_json text,after_json text,operation text,scope text,material_key text,evidence_json text,reason text,primary key(endpoint_id,field_name));
        create table material_fields_v16(material_key text,field_name text,value_json text,evidence_json text,primary key(material_key,field_name));
        create table reviews_v16(endpoint_id text primary key references record_keys_v16,review_json text not null);
        create table sources_v16(source_sha256 text primary key,path text not null,doi text not null,format text,component text);
        create table source_segments_v16(segment_id integer primary key,source_sha256 text references sources_v16,locator text,text text,content_sha256 text,reading_kind text);
        create virtual table segment_fts_v16 using fts5(text,content='source_segments_v16',content_rowid='segment_id');''')
        c.executemany('insert into record_keys_v16 values(?)',[(k,) for k in rows])
        c.executemany('insert into field_changes_v16 values(?,?,?,?,?,?,?,?,?)',[(s['endpoint_id'],s['field_name'],dump(s['before']),dump(s['after']),s['operation'],s['scope'],s['material_key'],dump(s['evidence']),s['reason']) for s in changes])
        c.executemany('insert into material_fields_v16 values(?,?,?,?)',[(s['material_key'],s['field_name'],dump(s['after']),dump(s['evidence'])) for s in changes if s['scope']=='material'])
        c.executemany('insert into reviews_v16 values(?,?)',[(r['endpoint_id'],dump(r)) for r in latest])
        # Index the new actual SI, not the metadata-only API response as full text.
        indexed=[]
        def segment(path,doi,fmt,component,loc,text,kind):
            h=sha(ROOT/path);c.execute('insert or ignore into sources_v16 values(?,?,?,?,?)',(h,path,doi,fmt,component))
            c.execute('insert into source_segments_v16(source_sha256,locator,text,content_sha256,reading_kind) values(?,?,?,?,?)',(h,loc,text,hashlib.sha256(text.encode()).hexdigest(),kind));indexed.append((path,loc))
        ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
        with zipfile.ZipFile(ROOT/ev['si']) as z:body=E.fromstring(z.read('word/document.xml')).find('w:body',ns)
        pi=ti=0
        for element in body:
            kind=element.tag.rsplit('}',1)[-1]
            if kind=='p':
                pi+=1;txt=''.join(n.text or '' for n in element.findall('.//w:t',ns));loc=f'DOCX body paragraph {pi}'
            elif kind=='tbl':
                ti+=1;txt='\n'.join(' | '.join(''.join(n.text or '' for n in cell.findall('.//w:t',ns)) for cell in row.findall('w:tc',ns)) for row in element.findall('w:tr',ns));loc=f'DOCX table {ti}'
            else:continue
            if txt.strip():segment(ev['si'],'10.1186/s42825-023-00122-w','docx','supplement',loc,txt,'native_text')
        unique={}
        for s in changes:
            for e in s['evidence']:
                if e['evidence_kind']=='reviewed_image_numbers':unique[(e['path'],e['locator'])]=e
        for e in unique.values():segment(e['path'],'10.1186/s42825-023-00122-w' if e['path'].endswith('.docx') else '10.1007/s00226-023-01515-0',Path(e['path']).suffix[1:],'supplement_image' if e['path'].endswith('.docx') else 'public_formal_figure',e['locator'],e['evidence_excerpt'],'agent_reviewed_image_transcription')
        c.execute("insert into segment_fts_v16(segment_fts_v16) values('rebuild')");c.commit()
    write(BATCH/'field_changes.json',changes);write(BATCH/'reviewed_cases.json',latest)
    write(BATCH/'task_plan.json',dict(parent='v0.15',fixed_pending=39,focused_reviews=5,source_groups_reviewed=4,model_fits=0,new_admissions=0,
        raw_sources_immutable=True,labels_membership_weights_immutable=True,network='Public publisher links only; no entitlement/access-control bypass.',
        indexing='New SI native text and explicitly typed image transcriptions; no large corpus copy.'))
    write(BATCH/'new_index_summary.json',dict(segments=len(indexed),readings=len(unique),native_document='Fe_SN6C_SI.docx',
        excluded_as_fulltext=['FWCA_cited_method15.xml'],reason='Metadata response lacks originalText/body.'))
    print(dump(dict(field_fills=len(changes),affected_records=len({s['endpoint_id'] for s in changes}),new_index_segments=len(indexed))))

def verify():
    from training_input_quality import assess
    from material_feature_inputs_v011 import prepare_material_fold
    checks=[];sealed=(OUT/'merge_manifest.json').exists()
    def emit(path,value):
        if sealed:
            if read(path)!=value:raise AssertionError('Sealed report differs from recomputed result: '+str(path))
        else:write(path,value)
    def check(name,ok):
        if not ok:raise AssertionError(name)
        checks.append(name)
    protection={}
    for mpath in [PARENT/'merge_manifest.json',ROOT/'模型v1.0_来源留出训练_20261022/run_manifest.json',ROOT/'模型逐项优化_v1.1_20261022/run_manifest.json']:
        m=read(mpath)
        for section in ['outputs','protected_files','protected_sources']:
            vals=m.get(section,[])
            if isinstance(vals,dict):vals=[dict(path=p,sha256=h) for p,h in vals.items()]
            for x in vals:
                if isinstance(x,dict) and 'path' in x and 'sha256' in x:
                    p=Path(x['path']);p=p if p.is_absolute() else ROOT/p
                    check('sealed_'+str(p),p.is_file() and sha(p)==x['sha256']);protection[str(p)]=x['sha256']
    # Prior review sources include both in-project originals and external originals.
    source_protection={}
    for file in ['protected_sources.json','review_evidence_hashes.json']:
        for p,h in read(ROOT/'已有文献表图与41条复核_20261024'/file).items():
            f=Path(p);f=f if f.is_absolute() else ROOT/f;check('original_'+p,sha(f)==h);source_protection[p]=h
    check('unchanged_full_corpus',sha(ROOT/read(OUT/'data_contract.json')['corpus_search_database'])==read(OUT/'data_contract.json')['corpus_search_database_sha256'])
    with closing(sqlite3.connect(DB.as_uri()+'?mode=ro',uri=True)) as c:
        check('sqlite_integrity',c.execute('pragma integrity_check').fetchone()[0]=='ok')
        check('foreign_keys',not c.execute('pragma foreign_key_check').fetchall())
    oldapi=module(PARENT/'ml_data.py','_v16_verify_parent');api=module(OUT/'ml_data.py','_v16_verify_current')
    changes=read(BATCH/'field_changes.json');lookup={(s['endpoint_id'],s['field_name']):s for s in changes}
    check('unique_changes',len(lookup)==len(changes));cohorts={};readiness={}
    with oldapi.Database() as old,api.Database() as db:
        a={r['endpoint_id']:r for r in old.fetch('all_review').rows};b={r['endpoint_id']:r for r in db.fetch('all_review').rows}
        check('all_observations_retained',set(a)==set(b) and len(b)==277)
        for key,row in a.items():
            for field,val in row.items():
                if (key,field) in lookup:check('before_chain_'+key+'_'+field,lookup[(key,field)]['before']==val)
                elif field.endswith('_status') and (key,field.removesuffix('_status')) in lookup:continue
                else:check('old_value_'+key+'_'+field,b[key].get(field)==val)
            if key in db.reviews_v16:check('hold_chain_'+key,db.holds(key)['previous_holds']==old.holds(key))
            else:check('holds_unchanged_'+key,db.holds(key)==old.holds(key))
        for s in changes:
            key=s['endpoint_id'];field=s['field_name']
            check('fill_only_'+key+field,s['before'] is None and a[key].get(field) is None and b[key][field]==s['after'])
            check('selected_evidence_'+key+field,any(e.get('review_version')=='v0.16' and e.get('currently_selected')==1 for e in db.evidence(key,field)))
            check('material_key_'+key+field,s['material_key']==a[key]['material_key_v11'])
            for e in s['evidence']:check('evidence_hash_'+key+field+e['locator'],field in e['fields'] and sha(ROOT/e['path'])==e['sha256'])
        for profile in db.contract['profiles']:
            x=old.fetch(profile);y=db.fetch(profile)
            check('membership_'+profile,[r['endpoint_id'] for r in x.rows]==[r['endpoint_id'] for r in y.rows])
            check('core_groups_weights_'+profile,x.feature_matrix()==y.feature_matrix())
            check('material_inputs_'+profile,old.material_matrix(profile)==db.material_matrix(profile))
            check('method_inputs_'+profile,old.method_specific_material_matrix(profile)==db.method_specific_material_matrix(profile))
            readiness[profile]=assess(y);check('quality_'+profile,readiness[profile]['status']=='ready_for_exploratory_grouped_baseline_inputs')
            cohorts[profile]=dict(records=len(y.rows),source_groups=len({r['source_group'] for r in y.rows}))
        check('unchanged_predictor_whitelist',db.contract['extra_material_feature_whitelist']==old.contract['extra_material_feature_whitelist'])
        for i,matrix in enumerate([db.material_matrix(),db.method_specific_material_matrix()]):
            for j,fold in enumerate(matrix['source_folds']):
                x=prepare_material_fold(matrix,fold);check(f'finite_{i}_{j}',all(math.isfinite(v) for n in ['X_train','X_validation'] for r in x[n] for v in r))
                changed=copy.deepcopy(matrix)
                for z in fold['test']:
                    changed['y'][z]=-987654
                    for col,f in enumerate(matrix['feature_names']):changed['X'][z][col]='HELDOUT_ONLY' if f in matrix['categorical_features'] else 987654
                y=prepare_material_fold(changed,fold);check(f'no_leak_{i}_{j}',x['X_train']==y['X_train'] and x['training_only_schema']==y['training_only_schema'])
        fe=b['legacy:R081_CY01'];h=b['incoming:ADD_016_T02'];k=b['incoming:ADD_016_T01']
        check('Fe_presence_not_speciation',fe['EDS_Fe_wt_pct_v16']==2.27 and fe['Fe_state_review_v16']['chemical_state'] is None and fe.get('XPS_N_reported_pct') is None)
        check('Fe_approx_target_preserved',fe['retention_pct']==102 and fe['retention_relation']=='approx')
        check('EDS_bulk_separate',fe['EDS_N_wt_pct_v16']==5.24 and fe['bulk_N_wt_pct']==8.47 and 'N_at_pct' in fe and fe['N_at_pct'] is None)
        check('N1s_relative_sums100',abs(sum(fe['N1s_relative_species_pct_v16'].values())-100)<1e-8)
        check('BET_explicit_body_not_table_conversion',h['BET_m2_g']==1996 and k['BET_m2_g']==1780 and not h['surface_area_unit_conflict_v16']['table_exact_area_selected'])
        check('preprint_cycle_binding_qualified',h['cycle_voltage_lower_V']==-1 and k['cycle_voltage_upper_V']==0 and h['protocol_document_version_v16'].startswith('ResearchSquare'))
        check('LWCA_current_labels_names_unchanged',h['retention_pct']==81.3 and k['sample_name']=='K-LWCA3' and k['reported_current_A_g']==10)
        check('formal_label_competing',h['retention_candidates_v16'][1]['value_pct']==81.37 and not h['retention_candidates_v16'][1]['selected_canonical'])
        check('explicit_XPS_atomic',k['XPS_percentage_basis']=='atomic_explicit' and k['XPS_N_reported_pct']==1.07 and h['XPS_O_reported_pct']==4.97)
        check('native_new_SI_search',any(r.get('path','').endswith('Fe_SN6C_SI.docx') and '0.3315' in r['excerpt'] and r['reading_kind']=='native_text' for r in db.search_native('0.3315',doi='10.1186/s42825-023-00122-w')))
        check('typed_image_search',any(r.get('reading_kind')=='agent_reviewed_image_transcription' and 'Fe2.27' in r['excerpt'] for r in db.search_native('Fe2.27',doi='10.1186/s42825-023-00122-w')))
        check('metadata_not_fulltext',not db.delta_v16.execute("select 1 from sources_v16 where path like '%FWCA_cited_method15%'").fetchall())
        check('old_native_search_still_works',bool(db.search_native('cycling',limit=2)))
        check('empty_search',db.search_native('')==[] and db.search_native('Fe',limit=0)==[])
        check('39_pending_25_groups',len(db.reviewed_pending_batch())==39 and len({r['source_group'] for r in db.reviewed_pending_batch()})==25)
        check('fixed41_with_outside',len(db.reviewed_pending_batch(True))==41)
        check('no_new_approval',all(not r['approved_profiles'] for r in read(BATCH/'reviewed_cases.json')))
        check('main_coverage_320_of756',sum(r.get(f) is not None for r in db.fetch().rows for f in db.contract['model_material_features'])==320)
        for kind in ['missing_baseline','wrong_system','missing_current']:
            ds=db.fetch();ds.rows=copy.deepcopy(ds.rows)
            if kind=='missing_baseline':ds.rows[0]['baseline_reference']=None
            elif kind=='wrong_system':ds.rows[0]['system']='2E'
            else:ds.rows[0]['reported_current_A_g']=None
            try:ds.feature_matrix()
            except api.DataNotReady:check('reject_'+kind,True)
            else:raise AssertionError(kind)
        emit(BATCH/'remaining_pending_records.json',db.reviewed_pending_batch())
        pending=db.reviewed_pending_batch()
    # Every fetched original and derived figure is fingerprinted, including failed-access receipts.
    for receipt in ['publisher_acquisition.json','LWCA_additional_acquisition.json']:
        for r in read(BATCH/receipt):
            if r.get('path'):check('retrieved_'+r['path'],sha(ROOT/r['path'])==r['sha256'])
    r=read(BATCH/'public_figure_acquisition.json');check('public_cycle_figure_hash',sha(ROOT/r['path'])==r['sha256'])
    emit(OUT/'training_readiness.json',readiness)
    emit(BATCH/'coverage_and_dispositions.json',dict(field_fills=len(changes),field_corrections=0,affected_records=len({s['endpoint_id'] for s in changes}),focused_records=5,
        reviewed_source_groups=4,cohorts=cohorts,pending_records=39,pending_source_groups=25,new_admissions=0,model_fits=0,
        main_optional_nonmissing=320,main_optional_denominator=756,main_optional_coverage_pct=100*320/756,
        all_scientific_questions_resolved=False,limits=['No accuracy improvement tested.','Current training matrices unchanged.','Formal LWCA full text and Fe chemical state remain unresolved.']))
    import io
    f=io.StringIO(newline='');w=csv.DictWriter(f,fieldnames=['endpoint_id','sample_name','source_group','disposition','open_issues','reason']);w.writeheader()
    for r in pending:w.writerow({k:'; '.join(r[k]) if isinstance(r.get(k),list) else r.get(k,'') for k in w.fieldnames})
    csv_path=BATCH/'当前待补证据.csv';csv_bytes=f.getvalue().encode('utf-8-sig')
    if sealed:assert csv_path.read_bytes()==csv_bytes
    else:csv_path.write_bytes(csv_bytes)
    emit(OUT/'verification.json',dict(passed=True,check_count=len(checks),checks=checks,protected_payloads=len(protection),protected_original_paths=len(source_protection),model_fits=0))
    if sealed:
        for x in read(OUT/'merge_manifest.json')['outputs']:assert sha(ROOT/x['path'])==x['sha256'],x['path']
    print(dump(dict(passed=True,checks=len(checks),fills=len(changes),new_admissions=0,pending=39,sealed_payloads_verified=sealed)))

def seal():
    manifest=OUT/'merge_manifest.json'
    if manifest.exists():raise FileExistsError('Already sealed; verify instead.')
    v=read(OUT/'verification.json');stats=read(BATCH/'coverage_and_dispositions.json');assert v['passed']
    assert read(ROOT/'data/current_database.json')==read(BATCH/'parent_pointer.json'),'Current pointer moved; preserve the other task and do not promote a stale parent.'
    for p in [BATCH/'README.md',OUT/'README.md',BATCH/'source_review.json']:assert p.is_file(),p
    receipt=dict(schemaVersion=1,items=[dict(id='evidence-correction',title='本轮补证结果',queries=[dict(id='verified-batch',source=dict(label='v0.16核验与补证台账',files=[dict(label='coverage_and_dispositions.json'),dict(label='field_changes.json'),dict(label='reviewed_cases.json')],filters=['固定39条待证中的5条重点复核'],caveats=['补录均在冻结候选中，训练主集仍42条/30来源。','新增准入0；不将Fe检出当作化学态或将图文冲突猜为通过。']),columns=[dict(field='item',label='核验项'),dict(field='value',label='数量')],rows=[dict(item='补录字段',value=stats['field_fills']),dict(item='仍待证记录',value=39),dict(item='新增准入',value=0),dict(item='新增模型拟合',value=0)])])])
    write(BATCH/'sources_receipt.json',receipt)
    write(BATCH/'storage_review.json',dict(new_SI_documents=1,new_formal_fulltexts=0,public_formal_figures=3,publisher_HTML_snapshots=2,metadata_only_XML=1,
        large_corpus_copies=0,failed_HTML_PDFs_saved=0,deleted_bytes=0,derived_images_retained=['Fe_SN6C_FigS7_final_sample_EDX.png','LWCA_preprint_p20_cycle_figure.png'],
        reason='All saved artifacts have evidence/identity/access-audit purpose; no disposable failed-download cache retained.'))
    outputs=[]
    for folder in [BATCH,OUT]:
        for p in sorted(folder.rglob('*')):
            if p.is_file() and '__pycache__' not in p.parts:outputs.append(dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p),bytes=p.stat().st_size))
    for name in ['retrieve_targeted_evidence_v016.py','release_targeted_evidence_v016.py']:
        p=ROOT/'tools'/name;outputs.append(dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p),bytes=p.stat().st_size))
    write(manifest,dict(schema='targeted_evidence_delivery_v1',version='v0.16',database_sha256=sha(DB),parent_database_sha256=read(BATCH/'parent_pointer.json')['sha256'],
        ready_for_merge=True,ready_for_training_inputs=True,all_records_admitted=False,all_scientific_questions_resolved=False,
        new_admissions=0,model_fits=0,current_pending=39,verification_checks=v['check_count'],cohorts=stats['cohorts'],outputs=outputs))
    pointer=dict(version_directory=OUT.name,database_file=DB.name,sha256=sha(DB),parent_database_file=(PARENT/'cycling_v0_15.sqlite').relative_to(ROOT).as_posix(),
        default_profile='reported_3e',stage='targeted_publisher_SI_and_formal_image_evidence_qualified_delta',ready_for_training_inputs=True,
        research_training_authorized=False,all_records_admitted=False)
    write(ROOT/'data/current_database.json',pointer);print(dump(dict(sealed_outputs=len(outputs),database_sha256=pointer['sha256'])))
if __name__=='__main__':
    {'build':build,'verify':verify,'seal':seal}[sys.argv[1]]()
