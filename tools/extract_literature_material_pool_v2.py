"""One-use extension of sealed literature pool; verification is read-only after sealing."""
from pathlib import Path
from contextlib import closing
import hashlib, json, re, sqlite3, sys, xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT/'文献全量利用复核_20261025/批次02_紫玉米芯与对照'
PARENT = ROOT/'文献全量利用复核_20261025/literature_material_pool_v1.sqlite'
DB = OUT/'literature_material_pool_v2.sqlite'
CORPUS = ROOT/'全库复检与特征补提取_20261021/full_corpus_search_native.sqlite'
A = '10.1021/acsenvironau.3c00048'
B = '10.3390/molecules29225413'
DOCS = {
 'purple_main': (A,'三电极端点扩充_20261018/new_sources/PMC10958655/main.xml','615850ad32df82a442126cb54476f1740f2dc665567edf75b4056ef1e8b7ce93'),
 'purple_si': (A,'三电极端点扩充_20261018/new_sources/PMC10958655/assets/vg3c00048_si_001.pdf','b52839919bdc35e9eec83fa08f4a809b33202614e5bfbbe643a824d7986f0cbd'),
 'synthetic_main': (B,'同体系文献补充_第二批_20261017/定向扩搜40至60篇_20261017/sources/OA030/main.xml','e8173d892344e8b91b436a2a6b30c3ca80c9513bccd8d12cce961da38a30a8b5'),
 'synthetic_si': (B,'同体系文献补充_第二批_20261017/定向扩搜40至60篇_20261017/sources/OA030/molecules-3331745-supplementary.pdf','b56864847e966388570f41c3263e6382c7a235a9b60a60120314e6c539c4b2e1')
}

def sha(path):
    with Path(path).open('rb') as f: return hashlib.file_digest(f,'sha256').hexdigest()
def write(path,value): path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def txt(node): return ' '.join(''.join(node.itertext()).split()) if node is not None else ''
def normalize(s): return re.sub(r'\s+',' ',s).strip()
def ro(path): return sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro',uri=True)
def material_key(doi,sample): return 'literature:'+hashlib.sha256((doi+'\0'+sample).encode()).hexdigest()[:24]

# Manual transcription checked against the six saved rendered SI pages. All rows
# are retained, including ancillary columns not promoted to material features.
SI = [
 dict(doc='purple_si',id='Table1S',page=2,raw='4432d1827c42459ab08ea274',kind='material',
      header=['sample','element','reported_percentage'],footnote='SEM-EDS; atomic versus mass percentage not specified.',
      rows=[['AC-5%','C','84.6'],['AC-5%','O','13.6'],['AC-5%','K','0.9'],['AC-5%','Al','0.7'],
            ['AC-10%','C','89.9'],['AC-10%','O','9.9'],['AC-10%','K','0.2'],
            ['AC-20%','C','85.3'],['AC-20%','O','13.5'],['AC-20%','Si','0.5'],['AC-20%','Na','0.4'],
            ['AC-30%','C','72.3'],['AC-30%','O','20.4'],['AC-30%','Na','2.6'],['AC-30%','Si','2.6'],['AC-30%','Al','1.1']]),
 dict(doc='purple_si',id='Table2S',page=3,raw='98ea31e6b8e5ee9ace63ab1b',kind='material',
      header=['sample','ID','IG','reported_R_ID_IG','La','LD','nD'],footnote='R is reported intensity ratio; retain author precision. La/LD/nD formulas in source; ancillary columns staged, not canonical features.',
      rows=[['AC-0%','814','1051','0.77','24.9','13.7','1.7 x 1011'],['AC-5%','200','206','0.97','19.8','12.2','2.1 x 1011'],
            ['AC-10%','382','406','0.94','20.7','12.5','2.1 x 1011'],['AC-20%','225','224','1.004','18.6','11.8','2.3 x 1011'],
            ['AC-30%','851','901','0.94','20.2','12.3','2.1 x 1011']]),
 dict(doc='purple_si',id='Table3S',page=4,raw='de630e4a916526b60ced8bbf',kind='material',
      header=['sample','level','BE_eV','At_pct','FWHM','Area'],footnote='AC-30% C1s/O1s binding energies conflict with element labels; no silent swap. Ancillary fit columns retained as raw.',
      rows=[['AC-0%','C1s','284.0','80.60','2.11','2331.3'],['AC-0%','O1s','531.5','14.79','2.94','12530'],['AC-0%','Si2p','101.5','4.61','2.27','109.0'],
            ['AC-5%','C1s','283.5','86.70','2.30','2658.4'],['AC-5%','O1s','531.5','13.30','3.70','1195.3'],
            ['AC-10%','C1s','284.0','81.80','2.27','2656.4'],['AC-10%','O1s','531.5','18.20','3.88','1731.5'],
            ['AC-20%','C1s','284.0','83.94','2.55','2564.1'],['AC-20%','O1s','532.0','16.06','3.00','1437.6'],
            ['AC-30%','C1s','532.0','80.00','4.45','2678.1'],['AC-30%','O1s','284.5','17.59','2.89','1725.2'],['AC-30%','Si2p','102.0','2.41','2.14','65.9']]),
 dict(doc='purple_si',id='Table7S',page=8,raw='a45e939c04347f22197dec14',kind='capacitance',
      header=['sample','CV_mass_H2SO4','CV_mass_KOH','CV_volume_H2SO4','CV_volume_KOH','GCD_mass_H2SO4','GCD_mass_KOH','EIS_mass_H2SO4','EIS_mass_KOH'],
      footnote='Grouped headers visually reviewed. CV5mV/s and GCD0.5A/g from own Figure6 caption; EIS OCP, 0.005V amplitude,0.01-1000Hz method. AC-5% EIS conflicts with Tables8S/9S.',
      rows=[['AC-5%','105','75','144','103','120','73','70','25'],['AC-10%','179','111','208','129','195','116','128','90'],
            ['AC-20%','90','75','127','106','91','80','52','53'],['AC-30%','32','24','-','-','23','29','32','12']]),
 dict(doc='purple_si',id='Table8S',page=8,raw='a45e939c04347f22197dec14',kind='capacitance_with_raw_circuit',
      header=['quantity','unit','AC-5%','AC-10%','AC-20%','AC-30%'],footnote='1mol/L H2SO4. Circuit fitted parameters retained in transcribed rows, not material features. Competing AC-5% capacitance versusTable7S.',
      rows=[['Capacitance','F/g','25','128','52','32'],['Rs','ohm','22','17.5','23.4','134'],['Rs_error','%','0.3','0.45','0.1','4'],
            ['R2','ohm','-','-','-','88.8'],['R2_error','%','-','-','-','6.3'],['W','mMho*s^1/2','0.0023','0.02','0.02','0.007'],
            ['W_error','%','2.3','3.8','0.6','0.475'],['Q','microMho*s^N','0.0006','0.00084','0.0001','2.9E-05'],
            ['Q_error','%','1.7','11.9','1.2','2.3'],['N','dimensionless','0.7','0.8','0.2','0.27'],
            ['C','mF','0.00095','0.005','0.002','0.0012'],['C_error','%','1.56','2.3','0.2','0.154']]),
 dict(doc='purple_si',id='Table9S',page=9,raw='f968dc883c21891c548e9477',kind='capacitance_with_raw_circuit',
      header=['quantity','unit','AC-5%','AC-10%','AC-20%','AC-30%'],footnote='1mol/L KOH. Preserve raw; no acid/alkali column correction inferred.',
      rows=[['Capacitance','F/g','70','90','53','12'],['Rs','ohm','20.1','33','32','26'],['Rs_error','%','0.3','0.14','0.1','0.36'],
            ['W','mMho*s^1/2','0.0048','0.046','0.09','0.002'],['W_error','%','0.952','1.9','4.2','0.6'],
            ['Q','microMho*s^N','0.0004','3.4808E-05','0.0005','0.0002'],['Q_error','%','7.5','7.7','1.5','1.3'],
            ['N','dimensionless','0.45','0.09','0.6','0.4'],['C','mF','0.0026','0.0034','0.002','0.0004'],['C_error','%','2.33','0.27','0.48','0.91']]),
 dict(doc='synthetic_si',id='TableS1',page=3,raw='058964609032c68e7d852a0b',kind='material_reference_only',
      header=['entry','sample','ID','IG','ID_IG'],footnote='Syntheticresorcinol/formaldehyde precursor; no biomass origin reported.',
      rows=[['1','C0','196','194','1.01'],['2','C0.5','200','195','1.03'],['3','C1','206','194','1.06'],['4','C2','144','132','1.09']]),
 dict(doc='synthetic_si',id='TableS2',page=3,raw='058964609032c68e7d852a0b',kind='comparison_rows_separated',
      header=['sample','capacitance_F_g','current_A_g','electrolyte','reference'],footnote='Only final Thiswork row belongs to this source. Six foreign-paper rows are comparison references, never six new own samples.',
      rows=[['ACA60','89.1','1','1M H2SO4','[1]'],['CA-L87','122','1','6M KOH','[2]'],['CHPC-7','210','1','6M KOH','[3]'],
            ['NCA8','240','1','6M KOH','[4]'],['NGCA','244','1','6M KOH','[5]'],['HPCAs-0.4-800','260','1','6M KOH','[6]'],['C1','261.9','1','6M KOH','This work']])
]

def build():
    if DB.exists(): raise FileExistsError('Existing batch must not be overwritten.')
    assert sha(PARENT)=='72982e906e44bfd2428a25f5fe27f2ca25ee07974f97200da9ba3e9ddb16570b'
    for _,path,digest in DOCS.values(): assert sha(ROOT/path)==digest,path
    with closing(ro(PARENT)) as src,closing(sqlite3.connect(DB)) as c,closing(ro(CORPUS)) as corpus:
        src.backup(c);c.row_factory=sqlite3.Row;corpus.row_factory=sqlite3.Row
        c.execute('pragma foreign_keys=on')
        c.executescript('''
        create table source_documents(document_key text primary key,doi text references reviewed_sources,path text,sha256 text,role text);
        create table table_source_links(table_key text primary key references reviewed_tables,document_key text references source_documents,locator text);
        create table transcribed_rows(table_key text references reviewed_tables,row_ordinal integer,cells_json text,primary key(table_key,row_ordinal));
        create table source_scope_decisions(doi text primary key references reviewed_sources,scope text,reason text,evidence_json text,full_source_review_complete integer check(full_source_review_complete=0));
        create table capacitance_observations(observation_id text primary key,material_key text references materials,table_key text references reviewed_tables,row_ordinal integer,column_ordinal integer,value real,raw_value text,unit text,method text,system text,electrolyte text,concentration_mol_L real,current_A_g real,scan_rate_mV_s real,conditions_json text,status text,source_group text,training_eligible integer check(training_eligible=0));
        create table historical_fact_references(reference_id integer primary key,material_key text,field_name text,value_json text,source_sha256 text,locator text,source_level_candidate_table_ids_json text,association_basis text);
        create index cap_by_source_method on capacitance_observations(source_group,method,electrolyte);
        ''')
        # Bring v1 table provenance into the same schema without altering old rows.
        for row in c.execute('select * from reviewed_sources').fetchall():
            key='legacy:'+row['doi'];c.execute('insert into source_documents values(?,?,?,?,?)',(key,row['doi'],row['path'],row['sha256'],'main'))
            for t in c.execute('select * from reviewed_tables where doi=?',(row['doi'],)).fetchall():
                c.execute('insert into table_source_links values(?,?,?)',(t['table_key'],key,'XML table-wrap '+t['xml_id']))
        for doc,(doi,path,digest) in DOCS.items():
            if doc.endswith('main'):
                root=ET.parse(ROOT/path).getroot();actual=[txt(x).lower() for x in root.findall('.//article-id') if x.get('pub-id-type')=='doi']
                assert doi in actual
                c.execute('insert into reviewed_sources values(?,?,?,?,?)',(doi,path,digest,txt(root.find('.//article-title')),'Selected own tables/SI reviewed; not complete publication or training admission.'))
        for doc,(doi,path,digest) in DOCS.items(): c.execute('insert into source_documents values(?,?,?,?,?)',(doc,doi,path,digest,'SI' if doc.endswith('si') else 'main'))
        c.execute('insert into source_scope_decisions values(?,?,?,?,0)',(A,'biomass_candidate_protocol_conflict','Purple corncob own materials; cycling conflicts retained.',json.dumps({'main':'sections2.2-2.4,Figure7,abstract','SI':'Tables1S-3S,7S-9S'},ensure_ascii=False)))
        c.execute('insert into source_scope_decisions values(?,?,?,?,0)',(B,'reference_only_no_biomass_origin_reported','Own resorcinol/formaldehyde synthetic precursor; retained for method reference, excluded from biomass training.',json.dumps({'main':'abstract,section3.2','precursors':['resorcinol','formaldehyde']},ensure_ascii=False)))
        receipts=[]
        def mat(doi,sample):
            key=material_key(doi,sample)
            stage='unactivated_control' if doi==A and sample=='AC-0%' else 'final_sample_before_cycling'
            c.execute('insert or ignore into materials values(?,?,?,?)',(key,doi,sample,stage));return key
        def table(doc,identifier,caption,header,footnote,raw,locator,rows):
            doi,_,digest=DOCS[doc];key=doi+'#'+identifier
            c.execute('insert into reviewed_tables values(?,?,?,?,?,?,?)',(key,doi,identifier,caption,json.dumps(header,ensure_ascii=False),footnote,raw))
            c.execute('insert into table_source_links values(?,?,?)',(key,doc,locator))
            for i,row in enumerate(rows,1): c.execute('insert into transcribed_rows values(?,?,?)',(key,i,json.dumps(row,ensure_ascii=False)))
            c.execute('update raw_table_queue set review_state=? where table_id=?',('selected_own_values_reviewed_ancillary_rows_staged_not_full_paper',raw))
            receipts.append(dict(table_key=key,document_key=doc,source_sha256=digest,locator=locator,raw_table_id=raw,rows=len(rows)))
            return key
        def fact(doi,sample,key,row,col,field,raw,unit,method,status='own_reported_value_method_qualified_not_model_admission'):
            digest=c.execute('select d.sha256 from table_source_links l join source_documents d using(document_key) where table_key=?',(key,)).fetchone()[0]
            val=None if not re.fullmatch(r'\d+(?:\.\d+)?',raw) else float(raw)
            c.execute('insert into material_facts(material_key,field_name,value,raw_value,unit,method,table_key,row_ordinal,column_ordinal,source_sha256,review_status,training_eligible) values(?,?,?,?,?,?,?,?,?,?,?,0)',(mat(doi,sample),field,val,raw,unit,method,key,row,col,digest,status))
        def cap(doi,sample,key,row,col,raw,method,unit,electrolyte,current=None,scan=None,conflict=False):
            v=None if raw=='-' else float(raw)
            status='not_reported_dash' if v is None else ('conflicting_own_tables_canonical_value_frozen' if conflict else 'own_reported_candidate_not_training')
            system='3E' if doi==A else 'not_bound_in_this_reference_table'
            cond=dict(reference='Ag/AgCl(3M KCl)' if doi==A else None,conditions_locator='main section2.3,ownFigure6 caption' if doi==A else 'SI TableS2 own Thiswork row only',mass_denominator='author_reported_not_further_unified',grouping='All material/capacitance/cycling auxiliary rows from DOI stay in one split group.')
            if method=='EIS':cond.update(measured_at='OCP',amplitude_V=.005,frequency_min_Hz=.01,frequency_max_Hz=1000)
            identifier=doi+'#'+key.split('#')[-1]+'#'+str(row)+'#'+str(col)
            c.execute('insert into capacitance_observations values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,0)',(identifier,mat(doi,sample),key,row,col,v,raw,unit,method,system,electrolyte,1 if doi==A else 6,current,scan,json.dumps(cond,ensure_ascii=False),status,'doi:'+doi))
        for doc,identifier,fields in [
            ('purple_main','tbl1',[(1,'BET_surface_area_m2_g','m2/g','BET'),(2,'micropore_area_reported_m2_g','m2/g','micropore analysis method not specified'),(3,'microporosity_reported_pct','% basis unknown','reported percentage; area/volume basis not explicit'),(4,'micropore_volume_cm3_g','cm3/g','reported micropore volume'),(5,'pore_width_nm','nm','reported width, not silently diameter')]),
            ('synthetic_main','molecules-29-05413-t001',[(1,'BET_surface_area_m2_g','m2/g','BET'),(2,'mesopore_volume_cm3_g','cm3/g','reported mesopore volume'),(3,'total_pore_volume_cm3_g','cm3/g','reported total volume'),(4,'BJH_pore_diameter_nm','nm','BJH')])]:
            doi,path,digest=DOCS[doc];root=ET.parse(ROOT/path).getroot();t=root.find(f".//table-wrap[@id='{identifier}']")
            allrows=[[txt(cell) for cell in r if cell.tag in ['th','td']] for r in t.findall('.//tr')]
            header,rows=allrows[0],allrows[1:];raw=corpus.execute('select table_id from raw_tables_v11 where source_sha256=? and locator=?',(digest,'XML table-wrap '+identifier)).fetchone()[0]
            key=table(doc,identifier,txt(t.find('caption')),header,txt(t.find('table-wrap-foot')),raw,'XML table-wrap '+identifier,rows)
            for i,row in enumerate(rows,1):
                for col,field,unit,method in fields:
                    value=row[col];status='censored_below_error_not_zero' if value.startswith(('-', '−', '–')) else 'own_reported_value_method_qualified_not_model_admission'
                    fact(doi,row[0],key,i,col,field,value,unit,method,status)
        for spec in SI:
            doi=DOCS[spec['doc']][0];key=table(spec['doc'],spec['id'],spec['id']+'; '+spec['kind'],spec['header'],spec['footnote'],spec['raw'],f"PDF p{spec['page']} {spec['id']}",spec['rows'])
            for i,row in enumerate(spec['rows'],1):
                if spec['id']=='Table1S':fact(doi,row[0],key,i,2,'EDS_'+row[1]+'_reported_pct',row[2],'% basis unknown','SEM-EDS; mass/atomic basis unknown')
                elif spec['id']=='Table2S':fact(doi,row[0],key,i,3,'Raman_ID_IG',row[3],'ratio','Raman reported peak intensity ID/IG')
                elif spec['id']=='Table3S':
                    element=re.sub(r'\d.*','',row[1]);status='own_reported_assignment_conflict_frozen' if row[0]=='AC-30%' and element in ['C','O'] else 'own_reported_value_method_qualified_not_model_admission'
                    fact(doi,row[0],key,i,3,'XPS_'+element+'_at_pct',row[3],'at%','XPS survey; author element assignment retained',status)
                elif spec['id']=='TableS1':fact(doi,row[1],key,i,4,'Raman_ID_IG',row[4],'ratio','Raman reported peak intensity ID/IG')
                elif spec['id']=='Table7S':
                    for col in range(1,9):
                        method='CV' if col<=4 else ('GCD' if col<=6 else 'EIS')
                        cap(doi,row[0],key,i,col,row[col],method,'F/cm3' if col in [3,4] else 'F/g','H2SO4' if col%2 else 'KOH',.5 if method=='GCD' else None,5 if method=='CV' else None,method=='EIS' and row[0]=='AC-5%')
                elif spec['id'] in ['Table8S','Table9S'] and i==1:
                    for col,sample in enumerate(['AC-5%','AC-10%','AC-20%','AC-30%'],2):cap(doi,sample,key,i,col,row[col],'EIS','F/g','H2SO4' if spec['id']=='Table8S' else 'KOH',conflict=sample=='AC-5%')
                elif spec['id']=='TableS2' and row[-1]=='This work':cap(doi,row[0],key,i,1,row[1],'GCD','F/g','KOH',1)
        issue_records=[
            ('purple_cycle_protocol',A,'AC-10%',dict(kind='cycling_configuration_electrolyte_and_current_roles',competing=[{'locator':'mainsection2.3','claim':'3E lifecycle,acid/alkali;Ag/AgCl reference'},{'locator':'section2.4','claim':'2E symmetric,1MH2SO4'},{'locator':'Figure7a/caption','claim':'2E diagram,KOH1M;GCD1A/g'},{'locator':'own cycling paragraph','claim':'cycles6A/g,readings1A/g'},{'locator':'Figure7b','claim':'waveform axisVvsAg/AgCl'}],action='Preserve alternatives; canonical cycle configuration/electrolyte/current remain null. Abstract76% is retention, not coulombic efficiency.')),
            ('purple_EIS_AC5',A,'AC-5%',dict(kind='own_table_conflict',Table7S={'H2SO4':70,'KOH':25},Table8S={'H2SO4':25},Table9S={'KOH':70},action='No automatic swap; all four competing values and locators retained; canonical frozen.')),
            ('purple_XPS_AC30',A,'AC-30%',dict(kind='element_label_binding_energy_conflict',C1s={'BE_eV':532.0,'At_pct':80},O1s={'BE_eV':284.5,'At_pct':17.59},action='No silent chemical reassignment. C/O values qualified and frozen for canonical use.')),
            ('purple_microporosity',A,'all',dict(kind='percentage_basis_not_explicit',example={'sample':'AC-5%','area_micro':415.5,'area_total':499.5,'reported_microporosity_pct':88},action='Retain generic reported percent, not assume micro area/total or micro volume/total.')),
            ('purple_control_alias',A,'AC-0%',dict(kind='control_alias_not_merged',main='AC; no activated KOH',SI='AC-0%',action='SI control stored separately; no experimental-test admission or automatic alias to activated samples.'))
        ]
        for issue,doi,sample,record in issue_records:c.execute('insert into scientific_issues values(?,?,?,?)',(issue,doi,sample,json.dumps(record,ensure_ascii=False)))
        c.execute('insert into test_candidates values(?,?,?,0)',('LP2_purple_AC10_cycling',material_key(A,'AC-10%'),json.dumps(dict(source_group='doi:'+A,sample_name='AC-10%',system=None,method='GCD',electrolyte=None,reported_current_A_g=None,cycle_count=50000,retention_pct=76,retention_relation='eq',target_evidence='main abstract; Figure7c plots absolute capacitance not coulombic efficiency',protocol_conflict_issue='purple_cycle_protocol',scientific_gate_passed=False,current_cycle_database_membership=False,source_sha256=DOCS['purple_main'][2],evidence_source_path=DOCS['purple_main'][1],unresolved=['cycle configuration','electrolyte binding','6A/gcycling versus1A/greadout']),ensure_ascii=False)))
        from data.cycling_db import open_database
        with open_database() as previous: historical=previous.material_properties()
        for i,row in enumerate(historical,1):
            candidates=[r[0] for r in corpus.execute('select table_id from raw_tables_v11 where source_sha256=?',(row.get('sha256'),))]
            c.execute('insert into historical_fact_references values(?,?,?,?,?,?,?,?)',(i,row['material_key'],row['field_name'],json.dumps(row['value'],ensure_ascii=False),row.get('sha256'),row.get('locator'),json.dumps(candidates),'Same source SHA candidates only; NOT a table/cell match or full-table completion. Counts cannot be added as disjoint facts.'))
        c.commit()
    write(OUT/'table_review_receipt.json',receipts)
    write(OUT/'source_protection.json',dict(documents={k:dict(doi=d,path=p,sha256=s) for k,(d,p,s) in DOCS.items()},parent=dict(path=PARENT.relative_to(ROOT).as_posix(),sha256=sha(PARENT)),corpus=dict(path=CORPUS.relative_to(ROOT).as_posix(),sha256=sha(CORPUS)),cycling_pointer=json.loads((ROOT/'data/current_database.json').read_text('utf8'))))
    write(OUT/'SI_transcriptions.json',SI)
    verify()

def verify():
    checks=[]
    def check(label,passed):
        if not passed:raise AssertionError(label)
        checks.append(label)
    protection=json.loads((OUT/'source_protection.json').read_text('utf8'))
    for key,row in protection['documents'].items():check('source_'+key,sha(ROOT/row['path'])==row['sha256'])
    for key in ['parent','corpus']:check(key+'_unchanged',sha(ROOT/protection[key]['path'])==protection[key]['sha256'])
    check('cycling_pointer_unchanged',json.loads((ROOT/'data/current_database.json').read_text('utf8'))==protection['cycling_pointer'])
    with closing(ro(DB)) as c,closing(ro(PARENT)) as parent:
        c.row_factory=sqlite3.Row;parent.row_factory=sqlite3.Row
        check('integrity',c.execute('pragma integrity_check').fetchone()[0]=='ok')
        check('foreign_keys',not c.execute('pragma foreign_key_check').fetchall())
        for table in ['identity_inventory','material_facts','materials','test_candidates','scientific_issues']:
            columns=[r[1] for r in parent.execute('pragma table_info('+table+')')]
            old=[tuple(r) for r in parent.execute('select * from '+table)]
            new={tuple(r) for r in c.execute('select '+','.join(columns)+' from '+table)}
            check('all_parent_rows_retained_'+table,all(r in new for r in old))
        for t in ['raw_table_queue','material_facts','test_candidates','capacitance_observations']:
            check('zero_auto_admission_'+t,c.execute('select count(*) from '+t+' where training_eligible!=0 or training_eligible is null').fetchone()[0]==0)
        newfacts=c.execute('select f.*,t.xml_id,l.locator,d.path,d.sha256,m.sample_name from material_facts f join materials m using(material_key) join reviewed_tables t using(table_key) join table_source_links l using(table_key) join source_documents d using(document_key) where f.fact_id>88').fetchall()
        for f in newfacts:
            cells=json.loads(c.execute('select cells_json from transcribed_rows where table_key=? and row_ordinal=?',(f['table_key'],f['row_ordinal'])).fetchone()[0])
            check('fact_source_cell_'+str(f['fact_id']),cells[f['column_ordinal']]==f['raw_value'] and f['source_sha256']==f['sha256'])
            check('fact_number_or_null_'+str(f['fact_id']),f['value'] is None if not re.fullmatch(r'\d+(?:\.\d+)?',f['raw_value']) else float(f['raw_value'])==f['value'])
        # Reparse XML independently; copied rows are not the sole validation source.
        for receipt in json.loads((OUT/'table_review_receipt.json').read_text('utf8')):
            if not receipt['locator'].startswith('XML'):continue
            root=ET.parse(ROOT/DOCS[receipt['document_key']][1]).getroot();identifier=receipt['locator'].removeprefix('XML table-wrap ')
            original=root.find(f".//table-wrap[@id='{identifier}']").findall('.//tr')[1:]
            for i,row in enumerate(original,1):
                raw=[txt(x) for x in row if x.tag in ['th','td']]
                staged=json.loads(c.execute('select cells_json from transcribed_rows where table_key=? and row_ordinal=?',(receipt['table_key'],i)).fetchone()[0])
                check('XML_row_'+identifier+'_'+str(i),raw==staged)
        import pypdfium2 as pdf
        for spec in SI:
            d=pdf.PdfDocument(str(ROOT/DOCS[spec['doc']][1]));source=normalize(d[spec['page']-1].get_textpage().get_text_range())
            evidence=OUT/'evidence'/f"{'purple' if spec['doc']=='purple_si' else 'synthetic'}_p{spec['page']}"
            check('render_exists_'+spec['id'],evidence.with_suffix('.png').is_file())
            check('PDF_text_snapshot_'+spec['id'],normalize(evidence.with_suffix('.txt').read_text('utf8'))==source)
            for i,row in enumerate(spec['rows'],1):
                # Rows with scientific symbol units use the visually reviewed numeric tail.
                tokens=row[2:] if spec['id'] in ['Table8S','Table9S'] else (row[1:] if spec['id'] in ['Table1S','Table3S'] else row)
                check('PDF_row_'+spec['id']+'_'+str(i),normalize(' '.join(tokens)) in source)
        caps=c.execute('select * from capacitance_observations').fetchall()
        for row in caps:
            cells=json.loads(c.execute('select cells_json from transcribed_rows where table_key=? and row_ordinal=?',(row['table_key'],row['row_ordinal'])).fetchone()[0])
            check('cap_cell_'+row['observation_id'],cells[row['column_ordinal']]==row['raw_value'])
            check('cap_null_'+row['observation_id'],row['value'] is None if row['raw_value']=='-' else row['value']==float(row['raw_value']))
            check('cap_group_'+row['observation_id'],row['source_group'].startswith('doi:') and row['training_eligible']==0)
            if row['method']=='CV':check('CV_scan_not_current_'+row['observation_id'],row['current_A_g'] is None and row['scan_rate_mV_s']==5)
        check('censored_not_zero',c.execute("select count(*) from material_facts where review_status='censored_below_error_not_zero' and value is null").fetchone()[0]==4)
        check('EDS_unknown_basis_not_XPS',c.execute("select count(*) from material_facts where field_name like 'EDS_%' and unit='% basis unknown'").fetchone()[0]==16)
        check('XPS_conflicting_assignments_frozen',c.execute("select count(*) from material_facts where review_status='own_reported_assignment_conflict_frozen'").fetchone()[0]==2)
        check('reference_scope_no_biomass_admission',c.execute('select scope from source_scope_decisions where doi=?',(B,)).fetchone()[0]=='reference_only_no_biomass_origin_reported')
        cyc=json.loads(c.execute("select record_json from test_candidates where candidate_id='LP2_purple_AC10_cycling'").fetchone()[0])
        check('cycle_protocol_not_invented',all(cyc[k] is None for k in ['system','electrolyte','reported_current_A_g']) and cyc['retention_pct']==76 and not cyc['scientific_gate_passed'])
        count=lambda t:c.execute('select count(*) from '+t).fetchone()[0]
        summary=dict(identity_catalogue_entries=count('identity_inventory'),raw_table_candidates=count('raw_table_queue'),raw_table_rows=6121,
            cumulative_reviewed_source_publications=count('reviewed_sources'),cumulative_materials=count('materials'),
            cumulative_selected_material_cells=count('material_facts'),cumulative_numeric_material_facts=c.execute('select count(*) from material_facts where value is not null').fetchone()[0],
            new_materials=count('materials')-15,new_numeric_material_facts=sum(r['value'] is not None for r in newfacts),new_censored_material_cells=sum(r['value'] is None for r in newfacts),
            reviewed_table_units=count('reviewed_tables'),raw_candidates_touched=c.execute("select count(*) from raw_table_queue where review_state!='automatic_candidate_unreviewed'").fetchone()[0],
            raw_candidates_untouched=c.execute("select count(*) from raw_table_queue where review_state='automatic_candidate_unreviewed'").fetchone()[0],
            capacitance_records=len(caps),numeric_capacitance_values=sum(r['value'] is not None for r in caps),unreported_capacitance_cells=sum(r['value'] is None for r in caps),
            own_conflicting_capacitance_records=sum(r['status']=='conflicting_own_tables_canonical_value_frozen' for r in caps),
            cycling_candidates=count('test_candidates'),new_cycling_candidates=1,scientific_issues=count('scientific_issues'),historical_selected_fact_references=count('historical_fact_references'),
            historical_fact_references_with_same_source_table_candidates=c.execute("select count(*) from historical_fact_references where source_level_candidate_table_ids_json!='[]'").fetchone()[0],
            all_literature_fully_utilized=False,new_training_admissions=0,model_fits=0,
            scope_note='Materialpool cumulative cells are not independent samples;39/41 capacitance numeric values include repeated/competing EIS reports and1synthetic reference. Historical725facts overlap unknown; do not add as disjoint. Table statuses record selected extraction scope, not full-paper completion.')
        check('counts_reconcile',summary['raw_candidates_touched']+summary['raw_candidates_untouched']==959)
        check('fixed_expected_counts',summary['new_numeric_material_facts']==69 and summary['new_materials']==9 and summary['capacitance_records']==41 and summary['numeric_capacitance_values']==39)
    report=dict(status='passed',checks=len(checks),check_names=list(checks),visual_review='Six SI page renders and own Figure7 inspected by agent; not human review.',new_real_model_fits=0)
    sealed=(OUT/'merge_manifest.json').exists()
    for name,value in [('summary.json',summary),('verification.json',report)]:
        if sealed:check('sealed_report_'+name,json.loads((OUT/name).read_text('utf8'))==value)
        else:write(OUT/name,value)
    if sealed:
        for item in json.loads((OUT/'merge_manifest.json').read_text('utf8'))['outputs']:check('sealed_'+item['path'],sha(ROOT/item['path'])==item['sha256'])
    print(json.dumps(dict(status='passed',checks=report['checks'],summary=summary),ensure_ascii=False))

def seal():
    if (OUT/'merge_manifest.json').exists():raise FileExistsError('Do not reseal a release.')
    verify()
    files=sorted([p for p in OUT.rglob('*') if p.is_file()]+[Path(__file__).resolve(),ROOT/'data/literature_v2.py'])
    write(OUT/'merge_manifest.json',dict(kind='literature_evidence_pool_v2',training_admission=False,new_model_fits=0,parent_sha256=sha(PARENT),outputs=[dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p),bytes=p.stat().st_size) for p in files]))
    write(ROOT/'data/current_literature.json',dict(version='literature_pool_v2',directory=OUT.relative_to(ROOT).as_posix(),database_file=DB.name,sha256=sha(DB),api_module='data.literature_v2',scope='Own material facts, source-qualified SI, separate capacitance/cycling candidates and corpus queue; all new rows nontraining.'))

if __name__=='__main__':
    if len(sys.argv)!=2 or sys.argv[1] not in ['build','verify','seal']:raise SystemExit('build(one-use),verify(read-only),seal(one-use)')
    globals()[sys.argv[1]]()
