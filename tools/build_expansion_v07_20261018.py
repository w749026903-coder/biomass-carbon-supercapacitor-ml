"""Versioned evidence-led additions to the v0.6 reported-protocol cohorts."""
from pathlib import Path
import collections,csv,hashlib,importlib.util,json,shutil,sqlite3,sys,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
PARENT=ROOT/'循环稳定性数据库_v0.6_报告工况训练就绪_20261018'
OUT=ROOT/'循环稳定性数据库_v0.7_数据补充_20261018'
BATCH=ROOT/'数据补充_v07_20261018'

def enc(x):return json.dumps(x,ensure_ascii=False)
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def api():
    spec=importlib.util.spec_from_file_location('_v07_api',OUT/'ml_data.py');m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m);return m

def build():
    if OUT.exists():raise RuntimeError('New version exists; do not rerun a one-time builder.')
    assert sha(PARENT/'cycling_v0_6.sqlite')=='4bb330ba8225578069f18b92823f2ae5bedff2cdcba70c0ade4cadf69ba0182a'
    OUT.mkdir();p=sqlite3.connect((PARENT/'cycling_v0_6.sqlite').as_uri()+'?mode=ro',uri=True);c=sqlite3.connect(OUT/'cycling_v0_7.sqlite');p.backup(c);p.close();c.row_factory=sqlite3.Row;c.execute('pragma foreign_keys=ON')
    c.executescript('''
    CREATE TABLE record_expansion_reviews_v07(endpoint_id TEXT PRIMARY KEY REFERENCES model_endpoints,status TEXT NOT NULL,reason TEXT NOT NULL,evidence_json TEXT NOT NULL);
    CREATE TABLE reported_admission_history_v07(change_id INTEGER PRIMARY KEY,profile TEXT,endpoint_id TEXT REFERENCES model_endpoints,old_json TEXT,new_json TEXT,reason TEXT);
    CREATE TABLE candidate_sources_v07(pmcid TEXT PRIMARY KEY,doi TEXT,title TEXT,publication_year INTEGER,article_type TEXT,existing_identity TEXT,new_to_registry INTEGER,review_status TEXT,reason TEXT,metadata_json TEXT);
    CREATE TABLE candidate_source_segments_v07(segment_id INTEGER PRIMARY KEY,pmcid TEXT REFERENCES candidate_sources_v07,ordinal INTEGER,locator TEXT,text TEXT,UNIQUE(pmcid,ordinal));
    CREATE VIRTUAL TABLE candidate_search_v07 USING fts5(text,content='candidate_source_segments_v07',content_rowid='segment_id');
    ''')
    reviews=[]
    def endpoint(namespace,alias):return c.execute('select endpoint_id from endpoint_aliases where namespace=? and alias=?',(namespace,alias)).fetchone()[0]
    def observation(e,field,value,sids,reason,selected=True,unit=None):
        sources=[c.execute('select * from source_segments where segment_id=?',(sid,)).fetchone() for sid in sids]
        identity=c.execute('select identity_key from model_endpoints where endpoint_id=?',(e,)).fetchone()[0]
        assert all(s and c.execute('select 1 from paper_documents where identity_key=? and source_id=?',(identity,s['source_id'])).fetchone() for s in sources)
        s=sources[0];oid=c.execute('insert into field_observations(endpoint_id,field_name,value_json,unit,status,source_id,segment_id,locator,evidence_excerpt,provenance_json) values (?,?,?,?,?,?,?,?,?,?)',(e,field,enc(value),unit,'v07_primary_review_selected' if selected else 'v07_conflicting_primary_value_retained',s['source_id'],s['segment_id'],s['locator'],s['text'],enc({'reason':reason,'supporting_segments':sids}))).lastrowid
        if selected:
            old=c.execute('select observation_id from field_selection where endpoint_id=? and field_name=?',(e,field)).fetchone()
            c.execute('insert or replace into field_selection values (?,?,?)',(e,field,oid));c.execute('insert into field_selection_history(endpoint_id,field_name,old_observation_id,new_observation_id,reason) values (?,?,?,?,?)',(e,field,old[0] if old else None,oid,reason))
    def review(namespace,alias,window,sids,figure,kind,scope,extra=None,caveats=None):
        e=endpoint(namespace,alias)
        for field,val in [('cycle_voltage_lower_V',window[0]),('cycle_voltage_upper_V',window[1])]:observation(e,field,val,sids,'Own sample/configuration GCD programme reviewed; '+kind,unit='V')
        observation(e,'baseline_reference',{'reference':'author_initial_or_plotted_start','cycle_index':None,'basis':'Own reported retention label/graph; no fabricated conditioning cycle.','segments':sids},sids,'Reported-protocol author reference; unknown exact cycle index is preserved.')
        for field,value,fsids,unit in extra or []:observation(e,field,value,fsids,'Own sample-specific measurement, not a literature comparison row.',unit=unit)
        info={'namespace':namespace,'alias':alias,'endpoint_id':e,'segments':sids,'figure':figure,'window_evidence_kind':kind,'scope_review':scope,'caveats':caveats or [],'source_group_review':'Existing unified groups and known reuse relationships retained. Own sample, named cycling trace and source checked; no new cross-source reuse identified in this bounded review. This is not proof of statistical independence.'}
        c.execute('insert into record_expansion_reviews_v07 values (?,?,?,?)',(e,'approved_for_reported_protocol','Own label, protocol, core inputs and declared material scope checked for reported-current empirical use.',enc(info)));reviews.append(info)
    review('V05','V05_018',[-1,0],[4216,4242,4226],'同体系文献补充_第二批_20261017/定向扩搜40至60篇_20261017/sources/OA043/figures/nanomaterials-13-02431-g006.jpg','actual_first_and_last_cycle_waveforms','Spirulina self N/O-doped KOH activated carbon; no designed oxide/polymer phase.')
    review('TE','TE052',[-1,0],[6415,6416,6426,6427,6984],'三电极端点扩充_20261018/new_sources/PMC12158216/assets/polymers-17-01544-g006.jpg','same_sample_aqueous_three_electrode_GCD_programme','Sodium alginate/nanocellulose carbon aerogel SC-0.03; own aqueous3E test, not a gel-device endpoint.',caveats=['Fig6d/e explicitly shows own GCD-1to0V including10A/g; Fig7 cycle panel does not repeat voltage. This is programme binding, not a separately labelled cycle inset.'])
    for alias,bet in [('V05_008',365),('V05_009',708),('V05_010',1802),('V05_011',886)]:
        review('V05',alias,[-1,0],[4702,4724,4727,4731,4714],'同体系文献补充_第二批_20261017/定向扩搜40至60篇_20261017/sources/OA004/figures/ao3c04692_0008.jpg','explicit_same_three_electrode_GCD_window_all_named_samples','Quinoa straw K2CO3 activated carbon/control; all four samples remain in one paper source group.',extra=[('BET_m2_g',bet,[4714],'m2/g')],caveats=['Methods/result both say3M KOH; parent values already3M and remain unchanged. Fig8 reports absolute F/g; use explicit author retention percentages from main text, without pixel-derived new ratios.'])
    # Actual own GCD axes and result prose consistently negative; retain the
    # contrary positive generic method range, with an explicit adjudication.
    e=endpoint('TE','TE005')
    observation(e,'cycle_voltage_lower_V',0,[696],'Generic methods report0–0.5V, conflicting with own negative-potential result figures.',selected=False,unit='V')
    observation(e,'cycle_voltage_upper_V',.5,[696],'Generic methods report0–0.5V; retained as an unselected contradictory primary statement.',selected=False,unit='V')
    review('TE','TE005',[-.5,0],[700,702,699,696],'数据补充_v07_20261018/evidence_images/AC3_p7.png','own_GCD_axes_and_negative_range_result_prose_adjudicate_method_sign','Coconut-husk carbon AC3 fromKMnO4activation; own XPS survey reportsC/O, no intentional retainedMnO2composite.',caveats=['Generic methods0to+.5V conflicts with own Fig6a/b negative GCD axes and negative-range result text/Fig5. Selected actual GCD interval-.5to0V; both primary statements retained.','Own reported91%at10000/20A/g and author initial reference are used. Early F/g transient is not re-normalized; exact conditioning cycle and initial capacitance are unknown.','Cycle window bound to same own GCD programme, not an independently labelled long-cycle waveform.'])
    # Complete fields without giving a conflicting reference or missing current
    # an invented value. These records remain outside the exported cohorts.
    pending=[]
    def hold(namespace,alias,reason,sids,extras=None):
        e=endpoint(namespace,alias)
        for field,value,fsids,unit in extras or []:observation(e,field,value,fsids,reason,unit=unit)
        x={'namespace':namespace,'alias':alias,'endpoint_id':e,'segments':sids,'reason':reason};pending.append(x)
        c.execute('insert into record_expansion_reviews_v07 values (?,?,?,?)',(e,'pending_or_outside_main',reason,enc(x)))
    hold('V05','V05_017','Methods specify calomel but own Fig3 axes sayHg/HgO. Reference unresolved; do not silently choose one.',[3712,3714,3716,3717],extras=[('BET_m2_g',1267.913,[3714],'m2/g')])
    e=endpoint('V05','V05_017');observation(e,'reference_electrode','Hg/HgO',[3716],'Own Fig3axesexplicitHg/HgO; contradicts methodscalomel, so retained unselected.',selected=False)
    hold('TE','TE009','OwnBETandGCDwindowlocated; cycling current not located in this bounded text/SI/figure review. Do not borrow rate-test20A/g.',[3950,3957,7020,7023],extras=[('BET_m2_g',1572.1,[7023],'m2/g')])
    hold('V05','V05_022','EUO SI FigS5 has retention but no cycling-current annotation; SI rate-capacitance0.2A/g is not proof of endurance current.',[3971,4010,4015,4030,4032],extras=[('BET_m2_g',2033.87,[4015,4032],'m2/g')])
    hold('TE','TE032','Selected raw feedstock is recovered superabsorbent polymer from diapers, explicitly containing synthetic sodium polyacrylate. Not admitted as ordinary biomass-only carbon.',[6438,6439])
    hold('legacy','SRC126_CY01','Own M-3-25 explicitly contains electroactiveCu/CuO/Cu2O; not silently pooled with ordinary carbon main set.',[2615,2617,2618],extras=[('BET_m2_g',2501.08,[2615],'m2/g')])
    hold('legacy','R045_CY01','Reed/melamine material has explicitly detectedg-C3N4phase; material-scope review remains before main admission.',[1061,1066])
    hold('TE','TE010','Method electrolyte6M conflicts with own Fig4caption1M. Concentration remains unresolved.',[4042,4064,4065])
    for alias in ['TE036','TE037','TE038']:
        e=endpoint('TE',alias);observation(e,'retention_relation','derived_complement',[6370],'Values90.3/76.4/59.2 are100minus reported loss9.7/23.6/40.8; not exact directly reported retention labels.')
        observation(e,'value_kind','derived_100_minus_reported_loss_percent',[6370],'Preserve arithmetic provenance; no change to original numeric value.')
        hold('TE',alias,'Retention is a calculated complement of reported loss; keep outside exact-label main profile.',[6370])
    # Keep each original admission row in an explicit change chain before update.
    c.execute('delete from model_feature_cache');c.execute('insert into model_feature_cache select * from model_feature_rows')
    for k,val in [('selection_history_max_id',c.execute('select max(selection_id) from field_selection_history').fetchone()[0]),('selected_fields',c.execute('select count(*) from field_selection').fetchone()[0])]:c.execute('update feature_cache_meta set value=? where key=?',(str(val),k))
    for info in reviews:
        row=dict(c.execute('select * from model_feature_cache where endpoint_id=?',(info['endpoint_id'],)).fetchone());row.update({'profile':'reported_3e','eligible':1,'admission_status':'approved_for_reported_protocol','current_denominator_status':'not_uniquely_defined','current_input_semantics':'author_reported_protocol_descriptor','physical_current_harmonized':False,'training_authorized':False})
        spec=json.loads((PARENT/'data_contract.json').read_text(encoding='utf-8'))['profiles']['reported_3e'];assert row['system']=='3E' and row['method']=='GCD' and row['retention_relation']=='eq';assert all(row[f] is not None for f in spec['features'])
        old=dict(c.execute('select * from reported_profile_admissions_v06 where profile="reported_3e" and endpoint_id=?',(row['endpoint_id'],)).fetchone())
        new={'profile':'reported_3e','endpoint_id':row['endpoint_id'],'status':'approved_for_reported_protocol','reason':'v0.7 own-source core fields, scope and protocol reviewed; unknown mass denominator remains metadata.','evidence_json':enc(info)}
        c.execute('insert into reported_admission_history_v07(profile,endpoint_id,old_json,new_json,reason) values (?,?,?,?,?)',('reported_3e',row['endpoint_id'],enc(old),enc(new),'Evidence-led admission in new version; no global policy relaxation.'))
        c.execute('update reported_profile_admissions_v06 set status=?,reason=?,evidence_json=? where profile=? and endpoint_id=?',(new['status'],new['reason'],new['evidence_json'],new['profile'],new['endpoint_id']))
        c.execute('insert into reported_training_rows_v06 values (?,?,?,?,?)',('reported_3e',row['endpoint_id'],row['identity_key'],row['source_group'],enc(row)))
        path=ROOT/info['figure'];assert path.exists();c.execute('insert or ignore into source_visual_reviews_v06 values (?,?,?,?)',(path.relative_to(ROOT).as_posix(),sha(path),'v07 own source visual review',info['window_evidence_kind']))
    # Fresh sources are searchable, but have NO automatic archive/admission path.
    reasons={
    'PMC12232101':'Existing source, symmetric device gives384to360F/g; derived retention ratio is not promoted as an exact reported label.',
    'PMC12128159':'CV-based capacitance study; own endurance GCD endpoint not located in bounded body review.',
    'PMC12750383':'Existing source; own retention described as close to100%, not an exact point for the main profile.',
    'PMC13182528':'Same-material2Edevice has explicitly unequal mass ratio1.2; not the current equal-active-mass symmetric main use.',
    'PMC13527080':'PVdF-HFP gel device, areal cycling current and6wt%Fe; separate from ordinary aqueous carbon main use.',
    'PMC13227491':'Review article; quoted endpoints are other studies, not new independent experiments.',
    'PMC12444587':'Own3Econfirmed by SI, three retention values located; cycling current not located in the bounded main/SI/figure review. BET590.65abstract vs590body retained for review.',
    'PMC12251755':'Own aqueous3EGCDcharacterization located; no endurance endpoint located in bounded body review.',
    'PMC13516699':'Own endurance test explicitly200mV/s CV, despite abstract cyclic-retention wording; do not mark GCD.',
    'PMC13363457':'Own3000cycle95.2%retention measured by continuousCV20mV/s, not GCD.',
    'PMC12348096':'Review article; use references for discovery, not as experimental training rows.',
    'PMC12388389':'Endurance label belongsMnO2/hyphae/bamboo composite; not the carbon-only control.',
    'PMC12242611':'CV/EIS and adsorption/sensor study; cycle values in introduction refer to other papers.',
    'PMC13339986':'OwnGCD10000cycles/10A/g located, retention described qualitatively as negligible decay; exact point not located in bounded review.',
    'PMC12942665':'Own2E2100cycles57%located; absolute/areal current, mass pairing and train-input binding need record-level review.'}
    sources=json.loads((BATCH/'source_collection.json').read_text(encoding='utf-8'))
    for src in sources:
        pmc=src['pmcid'];folder=BATCH/'sources'/pmc;article=ET.parse(folder/'main.xml').getroot();atype=article.get('article-type');dates=article.findall('.//article-meta/pub-date/year');years=[int(x.text) for x in dates if x.text and x.text.isdigit()];year=min(years) if years else None
        reason=reasons[pmc];state='background_review' if atype=='review-article' else 'candidate_not_admitted'
        c.execute('insert into candidate_sources_v07 values (?,?,?,?,?,?,?,?,?,?)',(pmc,src['doi'],src['title'],year,atype,src['existing_identity'],int(src['new_to_registry']),state,reason,enc(src)))
        for i,seg in enumerate(json.loads((folder/'segments.json').read_text(encoding='utf-8'))):
            sid=c.execute('insert into candidate_source_segments_v07(pmcid,ordinal,locator,text) values (?,?,?,?)',(pmc,i,seg['locator'],seg['text'])).lastrowid
            c.execute('insert into candidate_search_v07(rowid,text) values (?,?)',(sid,seg['text']))
    c.execute('insert into extraction_run values (?,?)',('v07_evidence_expansion',enc({'parent_sha256':sha(PARENT/'cycling_v0_6.sqlite'),'added_main_records':len(reviews),'research_fits':0})));c.commit();c.close()
    contract=json.loads((PARENT/'data_contract.json').read_text(encoding='utf-8'));contract.update({'database_file':'cycling_v0_7.sqlite','parent_database_sha256':sha(PARENT/'cycling_v0_6.sqlite'),'version':'v0.7','expansion_rule':'Same v0.6 scientific contract; own-source additions only; candidates stay separate.'});dump(OUT/'data_contract.json',contract)
    code=(PARENT/'ml_data.py').read_text(encoding='utf-8').replace("self.root/'cycling_v0_6.sqlite'","self.root/'cycling_v0_7.sqlite'")
    code+='''\n    def candidate_sources(self):
        return [dict(r) for r in self.conn.execute('select pmcid,doi,title,publication_year,article_type,new_to_registry,review_status,reason from candidate_sources_v07 order by pmcid')]
    def search_candidates(self,query,limit=10):
        words=str(query).split()
        if not words:return []
        expression=' AND '.join('"'+w.replace('"','""')+'"' for w in words)
        return [dict(r) for r in self.conn.execute('select s.*,c.doi,c.review_status from candidate_search_v07 f join candidate_source_segments_v07 s on s.segment_id=f.rowid join candidate_sources_v07 c using(pmcid) where candidate_search_v07 match ? limit ?',(expression,max(1,min(int(limit),100))))]
    def expansion_reviews(self):
        return [dict(r) for r in self.conn.execute('select * from record_expansion_reviews_v07 order by endpoint_id')]
'''
    (OUT/'ml_data.py').write_text(code,encoding='utf-8')
    for name in ['preprocessing.py','requirements-model-lock.txt']:shutil.copyfile(PARENT/name,OUT/name)
    dump(OUT/'本轮准入复核.json',reviews);dump(OUT/'本轮未决与范围处置.json',pending)
    with api().Database() as db:
        summary={};out=OUT/'training_inputs';out.mkdir()
        for profile in contract['profiles']:
            ds=db.fetch(profile);matrix=ds.feature_matrix();g=len(set(matrix['groups']));folds=ds.source_folds(g)
            dump(out/(profile+'.json'),{'profile':profile,'dataset_fingerprint':ds.fingerprint(),'matrix':matrix,'rows':ds.rows,'leave_one_source_out':folds,'research_training_performed':False})
            with (out/(profile+'.csv')).open('w',encoding='utf-8-sig',newline='') as f:
                columns=['endpoint_id','source_group']+ds.features+['retention_pct','retention_relation','source_weight'];w=csv.DictWriter(f,columns,extrasaction='ignore');w.writeheader();w.writerows(ds.rows)
            summary[profile]={'records':len(ds.rows),'source_groups':g,'features':len(ds.features),'fingerprint':ds.fingerprint()}
        dump(out/'cohort_summary.json',summary);dump(OUT/'新增来源候选索引.json',db.candidate_sources())
    print(enc(summary))

if __name__=='__main__':build()
