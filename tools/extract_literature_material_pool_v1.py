"""One-use reviewed own-table extraction plus full-library work queue.

Creates a separate literature evidence layer, not automatic training admission.
Reads original XML and the sealed corpus index; never executes source files.
"""
from pathlib import Path
from contextlib import closing
import collections, hashlib, json, re, sqlite3, sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / '文献全量利用复核_20261025'
DB = OUT / 'literature_material_pool_v1.sqlite'
CORPUS = ROOT / '全库复检与特征补提取_20261021/full_corpus_search_native.sqlite'
SPECS = [
    dict(doi='10.3390/nano16161035', path='数据补充_v07_20261018/sources/PMC13516699/main.xml', tables=[
        ('nanomaterials-16-01035-t001', [(1,'BET_m2_g','m2/g','modified_BET'),(2,'micropore_surface_area_m2_g','m2/g','t_plot'),
          (3,'mesopore_surface_area_m2_g','m2/g','t_plot_author_label'),(4,'total_pore_volume_cm3_g','cm3/g','adsorption_at_p_p0_0.99'),
          (5,'average_pore_diameter_nm','nm','author_4V_over_SBET')]),
        ('nanomaterials-16-01035-t002', [(1,'XPS_C_at_pct','at.%','XPS'),(2,'XPS_N_at_pct','at.%','XPS'),
          (3,'XPS_O_at_pct','at.%','XPS'),(4,'XPS_B_at_pct','at.%','XPS')])]),
    dict(doi='10.3390/ma19132797', path='数据补充_v07_20261018/sources/PMC13363457/main.xml', tables=[
        ('materials-19-02797-t001', [(3,'XRD_d002_nm','nm','XRD')]),
        ('materials-19-02797-t002', [(4,'Raman_ID_IG','ratio','peak_intensity_ratio_not_peak_area')]),
        ('materials-19-02797-t003', [(1,'BET_m2_g','m2/g','BET'),(2,'reported_N2_pore_volume_cm3_g','cm3/g','author_N2_pore_volume_kind_not_explicit'),
          (3,'reported_pore_width_nm','nm','author_width_not_silently_diameter')])]),
    dict(doi='10.3390/molecules29215029', path='文献扩充_大批补齐_20261018/sources/SUP_111/main.xml', tables=[
        ('molecules-29-05029-t001',[(1,'BET_m2_g','m2/g','BET'),(2,'total_pore_volume_cm3_g','cm3/g','author_total_pore_volume')])]),
    dict(doi='10.1021/acs.energyfuels.3c01925', path='文献扩充_大批补齐_20261018/sources/SUP_009/main.xml', tables=[
        ('tbl3',[(1,'reported_total_surface_area_m2_g','m2/g','author_SSA_T'),(2,'reported_micropore_surface_area_m2_g','m2/g','author_SSA_mic'),
          (3,'reported_mesopore_surface_area_m2_g','m2/g','author_SSA_meso'),(4,'reported_mesopore_surface_fraction_pct','%','author_SSA_meso_over_SSA_T'),
          (5,'total_pore_volume_cm3_g','cm3/g','author_V_T'),(6,'micropore_volume_cm3_g','cm3/g','author_V_mic'),
          (7,'mesopore_volume_cm3_g','cm3/g','author_V_meso'),(8,'reported_mesopore_volume_fraction_pct','%','author_V_meso_over_V_T'),
          (9,'reported_pore_size_nm','nm','author_pore_size_definition_not_explicit')])])]


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def write(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', 'utf8')


def text(node):
    return ' '.join(''.join(node.itertext()).split()) if node is not None else ''


def normalized(value):
    return str(value or '').lower().removeprefix('doi:').removeprefix('https://doi.org/').strip()


def build():
    if DB.exists() or (OUT / 'merge_manifest.json').exists():
        raise FileExistsError('Preserve existing pool; review a new version instead.')
    OUT.mkdir(exist_ok=True)
    from data.cycling_db import open_database
    with open_database() as database:
        observations = database.fetch('all_review').rows
    pointer = json.loads((ROOT / 'data/current_database.json').read_text('utf8'))
    observation_map = collections.defaultdict(set)
    for row in observations:
        for value in [row.get('source_group'),row.get('identity_key'),row.get('doi')]:
            if value:
                observation_map[normalized(value)].add(row['endpoint_id'])
    reviews, source_hashes = [], {}
    with closing(sqlite3.connect(DB)) as current, closing(sqlite3.connect(CORPUS.as_uri()+'?mode=ro',uri=True)) as corpus:
        corpus.row_factory = sqlite3.Row
        current.execute('pragma foreign_keys=on')
        current.executescript('''
        create table identity_inventory(identity_key text primary key,doi text,title text,source_files integer,native_contents integer,current_observations integer,work_state text,association_basis text);
        create table raw_table_queue(table_id text primary key,source_sha256 text,locator text,caption text,previous_role text,raw_rows integer,review_state text,training_eligible integer check(training_eligible=0));
        create table reviewed_sources(doi text primary key,path text,sha256 text,title text,stage text);
        create table materials(material_key text primary key,doi text references reviewed_sources,sample_name text,material_stage text,unique(doi,sample_name));
        create table reviewed_tables(table_key text primary key,doi text references reviewed_sources,xml_id text,caption text,header_json text,footnote text,source_raw_table_id text);
        create table material_facts(fact_id integer primary key,material_key text references materials,field_name text,value real,raw_value text,unit text,method text,table_key text references reviewed_tables,row_ordinal integer,column_ordinal integer,source_sha256 text,review_status text,training_eligible integer check(training_eligible=0),unique(material_key,field_name,table_key));
        create table test_candidates(candidate_id text primary key,material_key text references materials,record_json text,training_eligible integer check(training_eligible=0));
        create table scientific_issues(issue_id text primary key,doi text references reviewed_sources,sample_name text,issue_json text);
        create index facts_by_material on material_facts(material_key,field_name);
        create index materials_by_source on materials(doi,sample_name);
        create index queue_by_state on raw_table_queue(review_state,previous_role);
        ''')
        for identity in corpus.execute('select * from identities order by identity_key'):
            key = identity['identity_key']
            shas = {r[0] for r in corpus.execute('select distinct sha256 from identity_sources where identity_key=?',(key,))}
            native = sum(bool(corpus.execute('select 1 from full_native_map_v11 where source_sha256=? limit 1',(s,)).fetchone()) for s in shas)
            matched = observation_map.get(normalized(identity['doi']),set()) | observation_map.get(normalized(key),set())
            state = 'has_current_observation_not_full_utilization_proof' if matched else ('native_content_without_normalized_DOI_observation_match' if native else 'metadata_or_non_native_content_needs_identity_review')
            current.execute('insert into identity_inventory values(?,?,?,?,?,?,?,?)',
                (key,identity['doi'],identity['title'],len(shas),native,len(matched),state,'Exact normalized DOI/identity match; not fuzzy entity resolution or scientific admission.'))
        for table in corpus.execute('select * from raw_tables_v11 order by table_id'):
            count = corpus.execute('select count(*) from raw_table_rows_v11 where table_id=?',(table['table_id'],)).fetchone()[0]
            current.execute('insert into raw_table_queue values(?,?,?,?,?,?,?,0)',
                (table['table_id'],table['source_sha256'],table['locator'],table['caption'],table['table_role'],count,'automatic_candidate_unreviewed'))
        for spec in SPECS:
            path = ROOT / spec['path']; root = ET.parse(path).getroot(); digest = sha(path)
            actual = [text(e).lower() for e in root.findall('.//article-id') if e.attrib.get('pub-id-type')=='doi']
            assert spec['doi'] in actual, (spec['doi'],actual)
            title = text(root.find('.//article-title')); source_hashes[spec['path']] = digest
            current.execute('insert into reviewed_sources values(?,?,?,?,?)',(spec['doi'],spec['path'],digest,title,'Own tables reviewed; main cycling training admission not inferred.'))
            for table_id, fields in spec['tables']:
                table = root.find(f".//table-wrap[@id='{table_id}']"); assert table is not None
                rows = table.findall('.//tr')
                header = [text(cell) for cell in rows[0] if cell.tag in ['th','td']]
                raw = corpus.execute('select table_id from raw_tables_v11 where source_sha256=? and locator=?',(digest,'XML table-wrap '+table_id)).fetchone()
                assert raw is not None
                table_key = spec['doi']+'#'+table_id
                current.execute('insert into reviewed_tables values(?,?,?,?,?,?,?)',
                    (table_key,spec['doi'],table_id,text(table.find('caption')),json.dumps(header,ensure_ascii=False),text(table.find('table-wrap-foot')),raw[0]))
                current.execute('update raw_table_queue set review_state=? where table_id=?',('own_material_values_reviewed_training_not_admitted',raw[0]))
                for ordinal, row in enumerate(rows[1:],1):
                    cells = [text(cell) for cell in row if cell.tag in ['th','td']]
                    if not cells:continue
                    sample = cells[0]
                    material_key = 'literature:'+hashlib.sha256((spec['doi']+'\0'+sample).encode()).hexdigest()[:24]
                    stage = 'intermediate_not_final_activated_carbon' if sample in ['CF-OC','CF-HTC'] else 'final_sample_before_cycling'
                    current.execute('insert or ignore into materials values(?,?,?,?)',(material_key,spec['doi'],sample,stage))
                    for column,field,unit,method in fields:
                        raw_value = cells[column]
                        assert re.fullmatch(r'\d+(?:\.\d+)?',raw_value), (sample,field,raw_value)
                        value = float(raw_value)
                        current.execute('insert into material_facts(material_key,field_name,value,raw_value,unit,method,table_key,row_ordinal,column_ordinal,source_sha256,review_status,training_eligible) values(?,?,?,?,?,?,?,?,?,?,?,0)',
                            (material_key,field,value,raw_value,unit,method,table_key,ordinal,column,digest,'own_reported_value_method_qualified_not_model_admission'))
                reviews.append(dict(doi=spec['doi'],path=spec['path'],sha256=digest,table_id=table_id,header=header,
                                    raw_table_id=raw[0],own_table_reviewed=True,training_eligible=False))
        def candidate(identifier,doi,sample,record):
            key = current.execute('select material_key from materials where doi=? and sample_name=?',(doi,sample)).fetchone()[0]
            record.update(source_group='doi:'+doi,sample_name=sample,scientific_gate_passed=False,
                          evidence_source_path=next(s['path'] for s in SPECS if s['doi']==doi),source_sha256=source_hashes[next(s['path'] for s in SPECS if s['doi']==doi)],
                          current_cycle_database_membership=False)
            current.execute('insert into test_candidates values(?,?,?,0)',(identifier,key,json.dumps(record,ensure_ascii=False)))
        candidate('LP1_PC700_CV',SPECS[0]['doi'],'PC-700',dict(system='2E_symmetric',method='CV',scan_rate_mV_s=200,
            reported_current_A_g=None,cycle_count=10000,retention_pct=98.60,retention_relation='eq',
            locator='own Figure7c and electrochemical-results paragraph;200mV/s explicitly CV',
            purpose='separate_CV_endpoint_not_GCD_target',unresolved=['complete_device_protocol_and_version_review']))
        candidate('LP1_CFHTCAC_CV',SPECS[1]['doi'],'CF-HTC-AC',dict(system='3E',method='CV',scan_rate_mV_s=20,
            reported_current_A_g=None,cycle_count=3000,retention_pct=95.2,retention_relation='eq',
            electrolyte='H2SO4',concentration_mol_L=1,reference_electrode='Ag/AgCl',
            initial_capacitance_F_g=201.1,terminal_capacitance_F_g=191.5,
            locator='own Figure11; paragraphs67-68; section2.3',purpose='separate_CV_endpoint_not_GCD_target',
            unresolved=['complete_waveform_binding_and_version_review']))
        for sample in ['WhB','BS','WhS']:
            candidate('LP1_'+sample+'_organic_GCD',SPECS[2]['doi'],sample,dict(system='2E_symmetric',method='GCD',
                reported_current_A_g=1,cycle_count=6000,retention_pct=94,retention_relation='approx',
                electrolyte='1M TEATFB in acetonitrile (author abbreviation)',concentration_mol_L=1,
                cycle_voltage_lower_V=.4,cycle_voltage_upper_V=1.5,
                locator='Figure5c; results2.2; cell fabrication3.3',purpose='separate_organic_2E_endpoint_not_aqueous_3E',
                unresolved=['approximate_each_sample_label','normalization_role_of_initial0.1A/g_vs_cycling1A/g','full_source_review']))
        candidate('LP1_ACgrain_gel_GCD',SPECS[3]['doi'],'AC grain',dict(system='2E_symmetric',method='GCD',
            reported_current_A_g=5,cycle_count=10000,retention_pct=91.3,retention_relation='derived_complement',
            reported_loss_pct=8.7,derivation='100-8.7',electrolyte='HEC/KOH gel',
            locator='Figure7b and own cycling paragraph36/conclusion39',purpose='separate_gel_2E_endpoint_not_aqueous_3E',
            unresolved=['cycle_waveform_window','full_surface_area_conflict_review','full_source_review']))
        issues = [
            ('PC800_XPS',SPECS[0]['doi'],'PC-800',dict(kind='reported_XPS_sum',values=[85,2.27,8.64,3.79],sum=99.7,action='Keep all raw values; do not normalize to100 or invent another element.')),
            ('corn_husk_surface',SPECS[3]['doi'],'AC husk',dict(kind='surface_partition_inconsistent',total=1508,micro=643,meso=1067,action='Raw own table preserved; components exceed total. No silent swapping or selected canonical partition.')),
            ('corn_cob_BET',SPECS[3]['doi'],'AC cob',dict(kind='body_table_disagreement',table_total_area=1770,body_total_area=1705,action='Preserve both sources; canonical area choice deferred.')),
            ('corn_cob_volume_ratio',SPECS[3]['doi'],'AC cob',dict(kind='author_ratio_vs_volumes',reported_ratio_pct=61.8,total=.97,meso=.61,action='Keep reported ratio and volume values; no replacement derived ratio.')),
            ('corn_grain_precision',SPECS[3]['doi'],'AC grain',dict(kind='reported_precision_variants',table=1804,body=1805,other_body=1804.90,action='Keep table and body locators; not three measurements or a claim of independently resolved precision.'))]
        current.executemany('insert into scientific_issues values(?,?,?,?)',[(i,d,s,json.dumps(v,ensure_ascii=False)) for i,d,s,v in issues])
        current.commit()
    write(OUT / 'reviewed_table_receipt.json', reviews)
    write(OUT / 'protected_sources.json', source_hashes)
    write(OUT / 'input_pointer.json',pointer)
    write(OUT / 'corpus_pointer.json',dict(path=CORPUS.relative_to(ROOT).as_posix(),sha256=sha(CORPUS)))
    verify()


def verify():
    checks=[]
    def check(name,ok):
        if not ok:raise AssertionError(name)
        checks.append(name)
    with closing(sqlite3.connect(DB.as_uri()+'?mode=ro',uri=True)) as c:
        c.row_factory=sqlite3.Row
        check('integrity',c.execute('pragma integrity_check').fetchone()[0]=='ok')
        check('foreign_keys',not c.execute('pragma foreign_key_check').fetchall())
        expected={'identity_inventory':480,'raw_table_queue':959,'reviewed_sources':4,'reviewed_tables':7,'materials':15,'material_facts':88,'test_candidates':6,'scientific_issues':5}
        for table,count in expected.items():check('count_'+table,c.execute('select count(*) from '+table).fetchone()[0]==count)
        for table in ['raw_table_queue','material_facts','test_candidates']:
            check('not_auto_training_'+table,c.execute('select count(*) from '+table+' where training_eligible!=0').fetchone()[0]==0)
        check('two_intermediates_separate',c.execute("select count(*) from materials where material_stage='intermediate_not_final_activated_carbon'").fetchone()[0]==2)
        check('no_amalgamated_material_rows',c.execute('select count(*) from (select doi,sample_name,count(*) n from materials group by doi,sample_name having n>1)').fetchone()[0]==0)
        for fact in c.execute('select f.*,m.sample_name,s.path,t.xml_id from material_facts f join materials m using(material_key) join reviewed_sources s using(doi) join reviewed_tables t using(table_key) order by fact_id'):
            root=ET.parse(ROOT/fact['path']).getroot()
            table=root.find(f".//table-wrap[@id='{fact['xml_id']}']")
            row=table.findall('.//tr')[fact['row_ordinal']]
            cells=[text(cell) for cell in row if cell.tag in ['th','td']]
            check('cell_'+str(fact['fact_id']),cells[0]==fact['sample_name'] and cells[fact['column_ordinal']]==fact['raw_value'] and float(fact['raw_value'])==fact['value'])
        check('CF_width_not_diameter',c.execute("select count(*) from material_facts f join materials m using(material_key) where m.doi='10.3390/ma19132797' and f.field_name='average_pore_diameter_nm'").fetchone()[0]==0)
        check('all6_test_candidates_explicitly_nontraining',all(not json.loads(r[0])['scientific_gate_passed'] for r in c.execute('select record_json from test_candidates')))
        summary=dict(identity_catalogue_entries=480,distinct_metadata_DOI_values=c.execute('select count(distinct doi) from identity_inventory').fetchone()[0],
            identity_work_states={r[0]:r[1] for r in c.execute('select work_state,count(*) from identity_inventory group by work_state')},
            raw_tables=959,raw_table_rows=6121,own_or_context_tables=780,comparison_or_summary_tables=179,
            own_tables_reviewed_this_batch=7,material_rows=15,final_material_rows=13,intermediate_rows=2,
            reviewed_numeric_material_facts=88,new_candidate_cycling_endpoints=6,new_training_admissions=0,model_fits=0,
            remaining_table_candidates=952,all_literature_fully_utilized=False,
            counting_caveat='480identities/464DOI values are catalogue clues, not480 downloaded or scientifically admitted independent papers. Raw table headers, duplicates and comparisons are not samples.')
    for path,digest in json.loads((OUT/'protected_sources.json').read_text('utf8')).items():check('source_'+path,sha(ROOT/path)==digest)
    pointer=json.loads((OUT/'corpus_pointer.json').read_text('utf8'))
    check('sealed_corpus_unchanged',sha(ROOT/pointer['path'])==pointer['sha256'])
    sealed=(OUT/'merge_manifest.json').exists()
    report=dict(status='passed',checks=len(checks),check_names=list(checks),model_fits=0)
    for name,value in [('summary.json',summary),('verification.json',report)]:
        if sealed:
            if json.loads((OUT/name).read_text('utf8'))!=value:raise AssertionError('Sealed report differs:'+name)
        else:write(OUT/name,value)
    if sealed:
        for item in json.loads((OUT/'merge_manifest.json').read_text('utf8'))['outputs']:
            if sha(ROOT/item['path'])!=item['sha256']:raise AssertionError('Sealed pool changed:'+item['path'])
    print(json.dumps(dict(status='passed',checks=report['checks'],material_facts=88,cycling_candidates=6,new_training_admissions=0),ensure_ascii=False))


def seal():
    if (OUT/'merge_manifest.json').exists():raise FileExistsError('Do not reseal existing pool.')
    verify()
    files=sorted([p for p in OUT.rglob('*') if p.is_file()]+[Path(__file__).resolve(),ROOT/'data/literature_db.py'])
    write(OUT/'merge_manifest.json',dict(kind='reviewed_literature_evidence_pool_v1',training_admission=False,model_fits=0,
        outputs=[dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p),bytes=p.stat().st_size) for p in files]))
    write(ROOT/'data/current_literature.json',dict(version='literature_pool_v1',directory=OUT.name,database_file=DB.name,sha256=sha(DB),
        scope='Existing literature material facts, separate test candidates and full corpus queue; not cycling training membership.'))


if __name__=='__main__':
    if len(sys.argv)!=2 or sys.argv[1] not in ['build','verify','seal']:raise SystemExit('Use build(one-use),verify(read-only),seal(one-use).')
    globals()[sys.argv[1]]()
