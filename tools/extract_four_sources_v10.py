"""One-use own-material extraction and peer-method audit; no estimators are fitted."""
from pathlib import Path
from contextlib import closing
import hashlib,json,re,sqlite3,sys,xml.etree.ElementTree as E,zipfile
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tools'))
from extract_onion_composite_v8 import sha,ro,write,insert,mk,text
from extract_palm_kernel_v7 import xml_grid
OUT=ROOT/'文献全量利用复核_20261026/批次10_棉花藜麦黄瓜与同行ANN';DB=OUT/'literature_material_pool_v10.sqlite';EV=OUT/'evidence'
PARENT=ROOT/'文献全量利用复核_20261026/批次09_藻类与杜仲木系统系列/literature_material_pool_v9.sqlite';PSHA='a6af4ea9be04f6aae1de53ec91150915331d1b2315e917d6030200edc90fe777'
COT='10.1039/c7ra11475c';QSC='10.1021/acsomega.3c04692';CUC='10.3390/nano14080686';ANN='10.1039/c9ra01255a'
BASE=ROOT/'同体系文献补充_第二批_20261017/定向扩搜40至60篇_20261017/sources'
SOURCES=[('Cotton10',COT,ROOT/'三电极端点扩充_20261018/new_sources/PMC9077822/main.xml','5296ec71b3f3532469f96e762617725fe74c3a0ff2c849b38ab220e17b061374'),('Quinoa10',QSC,BASE/'OA004/main.xml','ad46844bf81d199cb68ee02269524b65d4bac51304f66a45f947a88be8159a7e'),('Cucumber10',CUC,BASE/'OA048/main.xml','b47a2c273215a8ad814da6d6e0212fcc5576dc43f17bca66aa65940ff99e28af'),('NFAC10',ANN,ROOT/'三电极端点扩充_20261018/new_sources/PMC9064150/main.xml','7caff2646c65af0db52811020934a814b5de037bc7b148ce3d57cb31519a98e2')]
COTN=['C800','CDAP800','CDAP800-300','CDAP800-350','CDAP800-400'];QN=['QSC','QSC-2','QSC-3','QSC-4'];CN=['CCP','ACP-700','ACP-800'];NN=['NFAC','NFAC-a','NFAC-b','NFAC-c','NFAC-c-600','NFAC-c-800','NFAC-c-900','NFAC-c-2','NFAC-c-4']

def num(raw,mode='decimal'):
    if raw in ['-','–','—','']:return None
    if mode=='not_detected':
        assert raw=='not detected';return None
    if mode=='malformed_grouping':return None
    if mode=='pct':raw=raw.removesuffix('%')
    raw=raw.replace('−','-').replace('–','-')
    assert re.fullmatch(r'[+-]?(?:\d+(?:\.\d+)?|\.\d+)',raw),raw
    return float(raw)

def si_weight_rows():
    import pypdf
    txt=pypdf.PdfReader(EV/'RA-009-C9RA01255A-s001.pdf').pages[7].extract_text()
    portions=[txt.split('Table S1',1)[1].split('Table S2',1)[0],txt.split('Table S2',1)[1]];results=[]
    for part,n in zip(portions,[2,8]):
        rows=[]
        for line in part.splitlines():
            m=re.match(r'^\s*(I\s*\d+|O)\s+(.+)$',line)
            if not m:continue
            values=m[2].split()
            if len(values)==10 and all(re.fullmatch(r'-?\d+(?:\.\d+)?',x) for x in values):rows.append([m[1].replace(' ','')]+values)
        assert len(rows)==n+1,(n,rows);results.append(rows)
    return results

def units():
    def u(doc,doi,id,kind,locator,header,rows):return dict(document=doc,doi=doi,id=id,kind=kind,locator=locator,header=header,rows=rows)
    s1,s2=si_weight_rows()
    return [
      u('Cotton10',COT,'Raman_p25','own_numeric_prose','bodyp25; ownFig3b','sample ID_IG'.split(),[[n,v] for n,v in zip(COTN[1:],['1.01','1.02','1.05','1.03'])]),
      u('Cotton10',COT,'3E_p35','own_numeric_prose','bodyp35: .5Ag in3E','sample C_F_g'.split(),[['C800','160'],['CDAP800-300','240'],['CDAP800-350','292'],['CDAP800-400','267']]),
      u('Cotton10',COT,'3E_p37','own_numeric_prose','bodyp37 ownCDAP8003503E GCD','sample current_A_g C_F_g'.split(),[['CDAP800-350',str(j),str(v)] for j,v in [(.5,292),(1,284),(2,272),(5,250),(10,233)]]),
      u('Cotton10',COT,'2E_p41','own_numeric_prose','bodyp41 own2E.5Ag','sample C_F_g'.split(),[[n,str(v)] for n,v in zip(COTN,[116,192,203,270,250])]),
      u('Cotton10',COT,'2E_p43','own_numeric_prose','bodyp43 .5/10Ag; Fig10d usesAaxis label, proseAg preserved','sample current_A_g C_F_g'.split(),[['CDAP800-350','.5','270'],['CDAP800-350','10','212']]),
      u('Cotton10',COT,'N_O_wt_p45','own_numeric_prose','Conclusionbodyp45 explicitwt%, Table2 elsewhereonlypercent','sample XPS_N_wt_pct XPS_O_wt_pct'.split(),[['CDAP800-350','5.8','11.8']]),
      u('Cotton10',COT,'yield_reports','own_numeric_prose','abstract38%;bodyp4product34%;p22/23TGA13.0/38.2,distinctscope','sample metric value scope'.split(),[['C800','TGA_residue_pct','13.0','p22_untreatedrawcotton'],['DAP_impregnated_cotton','TGA_residue_pct','38.2','p23_TGAfeedincludesDAP'],['CDAP800','reported_product_yield_pct','34','p4_productyield'],['CDAP800','abstract_yield_pct','38','abstract_basisnotfullyspecified']]),
      u('Cotton10',COT,'cycle_reports','own_numeric_prose','abstract/bodyp39,p44,p45 plusactualownFig8c/Fig11a','system retention_pct cycles current_A_g scope'.split(),[['3E','92','5000','5','Fig8cprinted92_andp39about92'],['2E_symmetric','86','5000','5','Fig11aprinted86_andp44about86'],['2E_symmetric','87','5000','5','abstract_competing'],['2E_symmetric','89','5000','5','conclusion_competing']]),
      u('Quinoa10',QSC,'Raman_p17','own_numeric_prose','bodyp17 sampleorder+ownFig3b','sample ID_IG'.split(),[[n,v] for n,v in zip(QN,['.78','.83','.88','.82'])]),
      u('Quinoa10',QSC,'XPS_p24','own_numeric_prose','bodyp24 percentbasisunspecified; ownFig5nobasislabel','sample C_reported_pct N_reported_pct O_reported_pct'.split(),[['QSC-3','80.01','2.4','17.59']]),
      u('Quinoa10',QSC,'3E_p28','own_numeric_prose','bodyp28 .5Ag GCD all4samples','sample C_F_g'.split(),[[n,str(v)] for n,v in zip(QN,[55.9,232.1,469.5,222.9])]),
      u('Quinoa10',QSC,'3E_cycle_p30','own_numeric_prose','bodyp30/ownFig8a,10k5Ag','sample retention_pct'.split(),[[n,str(v)] for n,v in zip(QN,[93.6,94.8,97.8,95.5])]),
      u('Quinoa10',QSC,'2E_cycle_p37','own_numeric_prose','bodyp34,p37/actualFig11a,c insets; notcomparisonTable3signedrange','electrolyte concentration_M retention_pct cycles current_A_g lower_V upper_V'.split(),[['KOH','3','97.55','10000','5','0','1.5'],['Na2SO4','1','96.2','10000','5','0','2.0']]),
      u('Quinoa10',QSC,'device_energy_p39','own_numeric_prose','bodyp39; notderivedcapacitance orcyclecurrent','electrolyte reported_A_g E_Wh_kg P_W_kg'.split(),[['KOH','.5','15.0','689.7'],['Na2SO4','.5','39.68','999.0'],['Na2SO4','','13.66','19650']]),
      u('Cucumber10',CUC,'CCP_BET_p20','own_numeric_prose','bodyp20 owncarbonizedCCP','sample BET_m2_g'.split(),[['CCP','20.34']]),
      u('Cucumber10',CUC,'CV_p36','own_numeric_prose','bodyp36 CV5mVs; textTable1misreference notnewtable','sample C_F_g'.split(),[['ACP-700','252'],['ACP-800','300']]),
      u('Cucumber10',CUC,'GCD_p37_p38_p44','own_numeric_prose','bodyp37,p38,p44; actualownFig9','sample current_A_g C_F_g'.split(),[['ACP-700','.1','237'],['ACP-800','.1','331'],['ACP-800','1','286'],['ACP-800','2','279']]),
      u('Cucumber10',CUC,'response_p38_p41_p43','own_numeric_prose','bodyp38,p41,p43; originalunitsqualificationsnotrepaired','sample metric value qualifier'.split(),[['ACP-700','rate_retention_pct','93.7','from.1to2Ag'],['ACP-800','rate_retention_pct','84.3','from.1to2Ag'],['ACP-700','CE_mean_pct','83.9','across.1to2Ag'],['ACP-800','CE_mean_pct','89.5','across.1to2Ag'],['ACP-700','CE_max_pct','91.7','at1Ag'],['ACP-800','CE_max_rawvalue','94.8','authorprintsAgunit_at2Ag_notnewcapacitance'],['ACP-700','approx_Rct_ohm','.07','authorapprox'],['ACP-800','approx_Rct_ohm','.025','authorapprox'],['ACP-700','approx_Rs_ohm','.01','authorapprox'],['ACP-800','approx_Rs_ohm','.01','authorapprox']]),
      u('NFAC10',ANN,'Raman_p30','own_numeric_prose','bodyp30/ownFig7b','sample ID_IG'.split(),[[n,v] for n,v in zip(NN[:4],['.95','.81','.82','.78'])]),
      u('NFAC10',ANN,'GCD_p32','own_numeric_prose','bodyp32 ownsingleelectrodeequivalentC=4Idt/(m_bothdV)','sample current_A_g C_F_g'.split(),[[n,'.1',str(v)] for n,v in zip(NN[:4],[200,239,253,283])]+[['NFAC-c',str(j),str(v)] for j,v in [(.1,283),(.2,276),(.5,264),(1,255),(2,242),(5,225),(10,210),(20,190)]]),
      u('NFAC10',ANN,'neutral_GCD_p34','own_numeric_prose','bodyp34 own1MNa2SO40..1.6V','sample current_A_g C_F_g'.split(),[['NFAC-c','1','191'],['NFAC-c','10','143']]),
      u('NFAC10',ANN,'correct_volume_prose_p31','own_numeric_prose','bodyp31 explicitlycm3onlyNFACandNFACc; other/tablecm2preserved','sample Vtot_cm3_g'.split(),[['NFAC','2.26'],['NFAC-c','1.93']]),
      u('NFAC10',ANN,'EIS_time_p33','own_numeric_prose','bodyp33 numericalRs order proseinequalityinconsistent; numberspreserved','sample Rs_ohm relaxation_time_s'.split(),[[n,str(r),str(t)] for n,r,t in zip(NN[:4],[.85,.74,.91,.73],[1.47,1.78,1.47,1.21])]),
      u('NFAC10',ANN,'N_detection_p38','own_numeric_prose','bodyp38 authorEDSnotdetectedstatement; zeroonlywasamodelinitialization','sample N_reported_status'.split(),[['NFAC-c','not detected']]),
      u('NFAC_SI10',ANN,'SI_TableS1','peer_model_weights','PDFp8TableS1,2inputs; notnewphysicalmaterialtable',['row']+['H'+str(i) for i in range(1,11)],s1),
      u('NFAC_SI10',ANN,'SI_TableS2','peer_model_weights','PDFp8TableS2,8inputs; modelweightsnotnewphysicalmeasurements',['row']+['H'+str(i) for i in range(1,11)],s2)
    ]

def sample_curves():
    from PIL import Image
    rows=[]
    def read(doi,sample,doc,path,xs,xt0,xp0,xt1,xp1,yv0,yp0,yv1,yp1,hue,band,panel):
        im=Image.open(path).convert('RGB')
        def matches(rgb):
            r,g,b=rgb
            return r>170 and g<130 and b<150 if hue=='red' else b>170 and r<70 and g<150 if hue=='blue' else g>160 and r<150 and b<160 if hue=='green' else b>180 and r>165 and g<110 if hue=='magenta' else b>180 and 95<r<180 and g<100 if hue=='violet' else max(rgb)<150 and max(rgb)-min(rgb)<85
        for j in xs:
            x=xp0+(j-xt0)*(xp1-xp0)/(xt1-xt0);pixels=[(xx,y) for xx in range(round(x)-3,round(x)+4) for y in range(*band) if matches(im.getpixel((xx,y)))]
            assert pixels,(sample,j,panel);col=min({p[0] for p in pixels},key=lambda xx:(-sum(a==xx for a,b in pixels),abs(xx-x)));ys=[yy for xx,yy in pixels if xx==col];low,high=min(ys),max(ys);py=(low+high)/2;v=yv0+(py-yp0)*(yv1-yv0)/(yp1-yp0);scale=abs((yv1-yv0)/(yp1-yp0))
            rows.append(dict(doi=doi,sample=sample,document=doc,curve_group=doi+'#'+sample+'#GCD#'+('H2SO4' if doi==ANN else 'KOH'),x_name='reported_current_A_g',x_value=j,y_name='capacitance_F_g',y_value=v,y_uncertainty=((high-low)/2+2)*scale,x_uncertainty=3*abs((xt1-xt0)/(xp1-xp0)),pixel_x=x,pixel_y=py,pixel_y_extent=[low,high],selected_marker_column=col,axis=dict(x_value0=xt0,x_pixel0=xp0,x_value1=xt1,x_pixel1=xp1,y_value0=yv0,y_pixel0=yp0,y_value1=yv1,y_pixel1=yp1),method='Originalimagewidestlocalmarkercolumnmidpoint; localhalfheight+2pxcalibration,notstatisticalCI',panel=panel,not_independent_from_same_material_current_reports=True,retention_point_admitted=False))
    for s,hue,band in zip(COTN,['gray','red','green','blue','violet'],[(500,557),(435,486),(425,479),(360,432),(383,466)]):read(COT,s,'Cotton_Fig9_10',EV/'c7ra11475c-f9.jpg',[.5,1,2,5,10],0,300.5,10,571.5,100,527.5,300,343.5,hue,band,'Fig9c')
    for s,hue,band in [('ACP-700','gray',(320,353)),('ACP-800','red',(230,310))]:read(CUC,s,'Cucumber_Fig9_10',BASE/'OA048/figures/nanomaterials-14-00686-g009.jpg',[.1,.25,.5,1,2],.5,119,2,341,100,461.5,300,267.5,hue,band,'Fig9c')
    for s,hue in [('NFAC-c-600','green'),('NFAC-c','red'),('NFAC-c-800','blue'),('NFAC-c-900','magenta')]:read(ANN,s,'NFAC_SI_p4_10',EV/'AlgaeANN_SI_p4.png',[1,2,5,10,20],0,286,20,519,0,696,300,482,hue,(495,610),'SI_FigS3c')
    for s,hue in [('NFAC-c-2','green'),('NFAC-c','red'),('NFAC-c-4','blue')]:read(ANN,s,'NFAC_SI_p6_10',EV/'AlgaeANN_SI_p6.png',[1,2,5,10,20],0,714,20,947,0,756,300,542,hue,(551,683),'SI_FigS5d')
    assert len(rows)==70
    return rows

def curate():
    if (OUT/'curation_spec.json').exists() or DB.exists():raise FileExistsError('Do notoverwritecuration')
    sources=[];tables=[]
    with closing(ro(ROOT/'全库复检与特征补提取_20261021/full_corpus_search_native.sqlite')) as corpus:
        for key,doi,path,digest in SOURCES:
            assert sha(path)==digest;root=E.parse(path).getroot();sources.append(dict(key=key,doi=doi,path=path.relative_to(ROOT).as_posix(),sha256=digest,title=text(root.find('.//article-title')),article_type=root.get('article-type')))
            raw={r[1]:r[0] for r in corpus.execute('select table_id,locator from raw_tables_v11 where source_sha256=?',(digest,))}
            for tb in root.findall('.//table-wrap'):
                id=tb.get('id');loc='XML table-wrap '+id;kind='peer_model_weights' if doi==ANN and id=='tab3' else 'peer_model_importance' if doi==ANN and id=='tab4' else 'mixed_comparison_table' if (doi==COT and id=='tab4') or(doi==QSC and id in ['tbl2','tbl3'])or(doi==CUC and id.endswith('t004'))or(doi==ANN and id=='tab2') else 'own_xml_table'
                tables.append(dict(doi=doi,document=key,id=id,kind=kind,locator=loc,caption=text(tb.find('caption')),footnote=text(tb.find('table-wrap-foot')),grid=xml_grid(tb),raw_table_id=raw[loc]))
    write(OUT/'curation_spec.json',dict(sources=sources,tables=tables,units=units(),scope='Allspecifiedownmaincells,ownprosenumbers,70boundedcurvepoints,2SImodelweighttables; comparativeforeignrowsnotownlabels; notfullwaveformcompletion.'))
    write(OUT/'curve_samples.json',sample_curves())

def refresh_curves():
    assert not(OUT/'merge_manifest.json').exists()
    values=sample_curves();write(OUT/'curve_samples.json',values)
    with closing(sqlite3.connect(DB))as c:
        for r in values:
            rid='v10_'+r['document']+'_'+r['sample']+'_'+str(r['x_value']);cur=c.execute('update curve_samples_v8 set reading_json=? where reading_id=?',(json.dumps(r,ensure_ascii=False),rid));assert cur.rowcount==1
        c.commit()

def build():
    if DB.exists() or (OUT/'merge_manifest.json').exists():raise FileExistsError('Do notoverwriteDB')
    assert sha(PARENT)==PSHA;spec=json.loads((OUT/'curation_spec.json').read_text('utf8'));docs={s['key']:dict(doi=s['doi'],path=ROOT/s['path']) for s in spec['sources']}
    docs.update(NFAC_SI10=dict(doi=ANN,path=EV/'RA-009-C9RA01255A-s001.pdf'),Cotton_Fig8_10=dict(doi=COT,path=EV/'c7ra11475c-f8.jpg'),Cotton_Fig9_10=dict(doi=COT,path=EV/'c7ra11475c-f9.jpg'),Cotton_Fig10_10=dict(doi=COT,path=EV/'c7ra11475c-f10.jpg'),Cotton_Fig11_10=dict(doi=COT,path=EV/'c7ra11475c-f11.jpg'),NFAC_Fig8_10=dict(doi=ANN,path=EV/'c9ra01255a-f8.jpg'),NFAC_SI_p4_10=dict(doi=ANN,path=EV/'AlgaeANN_SI_p4.png'),NFAC_SI_p6_10=dict(doi=ANN,path=EV/'AlgaeANN_SI_p6.png'),Quinoa_Fig11_10=dict(doi=QSC,path=BASE/'OA004/figures/ao3c04692_0011.jpg'),Cucumber_Fig9_10=dict(doi=CUC,path=BASE/'OA048/figures/nanomaterials-14-00686-g009.jpg'))
    with closing(ro(PARENT)) as old,closing(sqlite3.connect(DB)) as c:
        old.backup(c);c.row_factory=sqlite3.Row;c.execute('pragma foreign_keys=on');c.executescript('''create table cell_extractions_v10(kind text,record_id text,table_key text references reviewed_tables,row_ordinal integer,column_ordinal integer,parse_mode text,primary key(kind,record_id));
        create table peer_model_cells_v10(record_id text primary key,table_key text references reviewed_tables,record_json text);
        create table peer_model_reviews_v10(doi text primary key references reviewed_sources,record_json text);
        create table source_reviews_v10(doi text primary key references reviewed_sources,record_json text);
        create table purpose_reviews_v10(observation_id text primary key references capacitance_observations,record_json text);
        create table numerical_audits_v10(audit_id text primary key,doi text,record_json text);''')
        for s in spec['sources']:insert(c,'reviewed_sources',dict(doi=s['doi'],path=s['path'],sha256=s['sha256'],title=s['title'],stage='Ownspecifiedmaincells/prose/70curves andpeermethod; notwholepapercompletion'))
        for key,d in docs.items():insert(c,'source_documents',dict(document_key=key,doi=d['doi'],path=d['path'].relative_to(ROOT).as_posix(),sha256=sha(d['path']),role='primary_xml' if key in [s['key'] for s in spec['sources']] else 'own_SI' if key=='NFAC_SI10' else 'original_figure_or_source_bound_PDF_render'))
        tables={}
        for t in spec['tables']+spec['units']:
            key=t['doi']+'#'+t['id'];rows=[[x['raw'] for x in r] for r in t['grid']] if 'grid' in t else t['rows'];tables[(t['doi'],t['id'])]=(key,rows)
            insert(c,'reviewed_tables',dict(table_key=key,doi=t['doi'],xml_id=t['id'],caption=t.get('caption',t['id']),header_json=json.dumps(rows[0] if 'grid' in t else t['header'],ensure_ascii=False),footnote=t.get('footnote','Ownscope; rawclaims/units/conflictsqualified, noautomaticadmission.'),source_raw_table_id=t.get('raw_table_id')));insert(c,'table_source_links',dict(table_key=key,document_key=t['document'],locator=t['locator']));insert(c,'extraction_units_v3',dict(table_key=key,kind=t['kind'],scope='Ownspecifiedcells; modelweights/importancearemethodartifacts, notphysicalmaterialsamples.'))
            for i,row in enumerate(rows,1):insert(c,'transcribed_rows',dict(table_key=key,row_ordinal=i,cells_json=json.dumps(row,ensure_ascii=False)));insert(c,'transcription_origins_v7',dict(table_key=key,row_ordinal=i,origin_json=json.dumps(t['grid'][i-1] if 'grid' in t else dict(document=t['document'],locator=t['locator'],row=i),ensure_ascii=False)))
            if t.get('raw_table_id'):c.execute('update raw_table_queue set review_state=? where table_id=?',('v10_peer_model_artifact_not_physical_measurement' if t['kind'].startswith('peer') else 'v10_declared_own_cells_reviewed_foreign_comparisons_separate',t['raw_table_id']))
        for doi,names,feed in [(COT,COTN,'absorbent_cotton'),(QSC,QN,'quinoa_straw'),(CUC,CN,'cucumber_peel'),(ANN,NN,'Nostoc_flagelliforme')]:
            for s in names:insert(c,'materials',dict(material_key=mk(doi,s),doi=doi,sample_name=s,material_stage='carbonized_control' if s in ['C800','QSC','CCP'] else 'final_biomass_carbon_before_test'));insert(c,'material_scopes_v8',dict(material_key=mk(doi,s),scope_json=json.dumps(dict(origin_class='biomass_carbon',feedstock=feed,sample_registration_not_independent_source=True),ensure_ascii=False)))
        def raw(key,i,col):return json.loads(c.execute('select cells_json from transcribed_rows where table_key=? and row_ordinal=?',(key,i)).fetchone()[0])[col]
        def receipt(kind,rid,key,i,col,mode):insert(c,'cell_extractions_v10',dict(kind=kind,record_id=str(rid),table_key=key,row_ordinal=i,column_ordinal=col,parse_mode=mode))
        def fact(doi,s,id,i,col,field,unit,method,mode='decimal',status='own_reported_method_qualified'):
            key=tables[(doi,id)][0];v=raw(key,i,col);doc=c.execute('select document_key from table_source_links where table_key=?',(key,)).fetchone()[0];value=num(v,mode);status='not_detected_limit_unknown_not_zero' if mode=='not_detected' else 'malformed_grouping_no_numeric_interpretation' if mode=='malformed_grouping' else 'author_dash_not_quantified_not_zero' if value is None else status
            cur=insert(c,'material_facts',dict(material_key=mk(doi,s),field_name=field,value=value,raw_value=v,unit=unit,method=method,table_key=key,row_ordinal=i,column_ordinal=col,source_sha256=sha(docs[doc]['path']),review_status=status,training_eligible=0));receipt('fact',cur.lastrowid,key,i,col,mode)
        preferred=[]
        def cap(doi,s,id,i,col,method,current=None,scan=None,system='2E_symmetric',electrolyte='KOH',M=6,extra=None,select=False):
            key=tables[(doi,id)][0];v=raw(key,i,col);rid=key+'#'+str(i)+'#'+str(col)
            cond=dict(extraction_batch='v10',repeat_reports_not_independent_tests=True,current_mass_basis='author_reported_unknown_not_inferred_from_capacitance_formula',voltage_lower_V=-1 if system=='3E' else 0,voltage_upper_V=0 if system=='3E' else .8 if doi==ANN and electrolyte=='H2SO4' else 1.6 if doi==ANN else 1,reference_electrode='Hg/HgO' if system=='3E' else None,capacitance_basis='single_working_carbon_electrode' if system=='3E' else 'author_factor4_single_electrode_C_mass_both' if doi==ANN else 'author_factor2_single_electrode_mass_explicit' if doi==CUC else 'author_factor2_material_mass_not_further_unified',mass_normalization_caveat='Cotton3Emethodactive5mgperworking,p14coinwordingretained' if doi==COT else None)
            cond.update(extra or {});insert(c,'capacitance_observations',dict(observation_id=rid,material_key=mk(doi,s),table_key=key,row_ordinal=i,column_ordinal=col,value=num(v),raw_value=v,unit='F/g',method=method,system=system,electrolyte=electrolyte,concentration_mol_L=M,current_A_g=current,scan_rate_mV_s=scan,conditions_json=json.dumps(cond,ensure_ascii=False),status='own_reported_scope_qualified_not_automatic_shared_admission',source_group='doi:'+doi,training_eligible=0));receipt('capacitance',rid,key,i,col,'decimal')
            if select:preferred.append(rid)
        def response(doi,s,id,i,col,metric,unit,mode='decimal',extra=None):
            key=tables[(doi,id)][0];v=raw(key,i,col);rid=key+'#'+str(i)+'#'+str(col);insert(c,'outcome_observations_v3',dict(outcome_id=rid,material_key=mk(doi,s) if s in COTN+QN+CN+NN else None,table_key=key,record_json=json.dumps(dict(extraction_batch='v10',source_group='doi:'+doi,metric=metric,value=num(v,mode),raw_value=v,unit=unit,row_ordinal=i,column_ordinal=col,feature_role='response_not_pretest_predictor',**(extra or {})),ensure_ascii=False),training_eligible=0));receipt('response',rid,key,i,col,mode)
        for i,row in enumerate(tables[(COT,'tab1')][1][1:],2):
            for col,f,un in [(1,'BET_surface_area_m2_g','m2/g'),(2,'micropore_surface_area_m2_g','m2/g'),(3,'mesopore_surface_area_m2_g','m2/g'),(4,'total_pore_volume_cm3_g','cm3/g'),(5,'micropore_volume_cm3_g','cm3/g'),(6,'mesopore_volume_cm3_g','cm3/g'),(7,'average_pore_diameter_nm','nm')]:fact(COT,row[0],'tab1',i,col,f,un,'OwnBET/N2degassing200C3h; PSDmethodsBJH,figureDFT/bodytplotwordingretained',status='conflict_micropore_plus_mesopore_area_exceeds_total' if row[0]=='CDAP800-400' and col in [2,3] else 'own_reported_method_qualified')
        for i,row in enumerate(tables[(COT,'tab2')][1][1:],2):
            for col,e in enumerate(['C','N','O','P'],1):fact(COT,row[0],'tab2',i,col,'XPS_'+e+'_reported_pct','%basis_unspecified','OwnTable2relativeXPS; notassumedatomic/weightfromtechnique')
        for i,row in enumerate(tables[(COT,'tab3')][1][1:],2):
            for col,component in enumerate(['N6','N5','NQ','NX','OI','OII','OIII'],1):fact(COT,row[0],'tab3',i,col,'XPS_'+component+'_envelope_pct','%ofN1s_envelope' if col<=4 else '%ofO1s_envelope','OwnrelativeN/Oenvelope; notsampletotal%',status='conflict_N_envelope_sum107.5_not_renormalized' if row[0]=='CDAP800-350' and col<=4 else 'own_reported_envelope_qualified')
        for doi,id in [(COT,'Raman_p25'),(QSC,'Raman_p17'),(ANN,'Raman_p30')]:
            for i,row in enumerate(tables[(doi,id)][1],1):fact(doi,row[0],id,i,1,'Raman_ID_IG','ratio','OwnreportedRamanratio,notinverse')
        for col,e in [(1,'N'),(2,'O')]:fact(COT,'CDAP800-350','N_O_wt_p45',1,col,'XPS_'+e+'_wt_pct','wt%','Ownconclusionexplicitwt%; notatomic; Table2rawunspecifiedpreserved')
        for i,row in enumerate(tables[(QSC,'tbl1')][1][1:],2):
            for col,f,un in [(1,'BET_surface_area_m2_g','m2/g'),(2,'micropore_surface_area_m2_g','m2/g'),(3,'total_pore_volume_cm3_g','cm3/g'),(4,'micropore_volume_cm3_g','cm3/g'),(5,'mesopore_volume_cm3_g','cm3/g')]:fact(QSC,row[0],'tbl1',i,col,f,un,'OwnN2at77.3K; porepartitionmethodsnotfurtherexplicit; noforcedclosure')
        for col,e in enumerate(['C','N','O'],1):fact(QSC,'QSC-3','XPS_p24',1,col,'XPS_'+e+'_reported_pct','%basis_unspecified','Ownprose/figuredoesnotexplicitlyspecifyat/vswt; keepgeneric')
        for i,row in enumerate(tables[(CUC,'nanomaterials-14-00686-t001')][1][1:],2):
            for col,f,un in [(1,'BET_surface_area_m2_g','m2/g'),(2,'total_pore_volume_cm3_g','cm3/g'),(3,'mesopore_volume_cm3_g','cm3/g'),(4,'pore_volume_below0p7nm_cm3_g','cm3/g'),(5,'pore_volume_below1nm_cm3_g','cm3/g'),(6,'micropore_volume_cm3_g','cm3/g'),(7,'mesopore_to_total_volume_reported_ratio','ratio')]:fact(CUC,row[0],'nanomaterials-14-00686-t001',i,col,f,un,'OwnNLDFT; below0.7andbelow1nm are nestedsubsets, notadditivecomponents')
        for i,row in enumerate(tables[(CUC,'nanomaterials-14-00686-t002')][1][1:],2):
            fact(CUC,row[0],'nanomaterials-14-00686-t002',i,1,'reported_product_yield_pct','wt%','YieldrelativedriedrawcucumbernotEDSatomiccomposition')
            for col,e in enumerate(['C','O','Na','Mg','Al','Si','K','Ca','Cl','P','S'],2):fact(CUC,row[0],'nanomaterials-14-00686-t002',i,col,'EDX_'+e+'_at_pct','at%','OwnEDAXTableatomicexplicit; dashesnotzero; bodyapproxC88/92sampleordercompeting',status='own_specific_EDAX_table_C_selected_body_rounded_order_dissent_retained' if e=='C' and row[0]!='CCP' else 'own_reported_method_qualified')
        for i,(row,s) in enumerate(zip(tables[(CUC,'nanomaterials-14-00686-t003')][1][1:],CN),2):
            for col,f in [(1,'Raman_G_reported_width'),(2,'Raman_D_reported_width')]:fact(CUC,s,'nanomaterials-14-00686-t003',i,col,f,'author_width_unit_unspecified','Multiplecommagroupingunresolved,noforceintegerordecimal',mode='malformed_grouping')
            fact(CUC,s,'nanomaterials-14-00686-t003',i,3,'Raman_G_area_fraction_pct','%','AuthorGarea/totalRamanarea700..2000cm-1,notID/IG','pct')
        fact(CUC,'CCP','CCP_BET_p20',1,1,'BET_surface_area_m2_g','m2/g','OwnCCPproseBET')
        for i,row in enumerate(tables[(ANN,'tab1')][1][1:],2):
            for col,f,un in [(1,'BET_surface_area_m2_g','m2/g'),(2,'micropore_surface_area_m2_g','m2/g'),(3,'mesopore_surface_area_m2_g','m2/g'),(4,'reported_pore_volume_cm2_g','as_printed_cm2/g'),(5,'reported_micropore_volume_cm2_g','as_printed_cm2/g'),(6,'reported_mesopore_volume_cm2_g','as_printed_cm2/g'),(7,'average_pore_diameter_nm','nm')]:fact(ANN,row[0],'tab1',i,col,f,un,'OwnTableliteralcm2header; do notsilentlyconvertto cm3')
        for i,row in enumerate(tables[(ANN,'correct_volume_prose_p31')][1],1):fact(ANN,row[0],'correct_volume_prose_p31',i,1,'total_pore_volume_cm3_g','cm3/g','Ownproseexplicitcm3forspecificNFACandNFACc; samevalue/tablecm2headerdissentretained')
        fact(ANN,'NFAC-c','N_detection_p38',1,1,'EDX_N_reported_pct','%basis_unspecified','OwnauthorEDSnotdetected, limitunknown; modelzeroassumptionnotmeasurement','not_detected')
        for i,row in enumerate(tables[(COT,'3E_p35')][1],1):cap(COT,row[0],'3E_p35',i,1,'GCD',.5,system='3E',select=row[0]!='CDAP800-350')
        for i,row in enumerate(tables[(COT,'3E_p37')][1],1):cap(COT,row[0],'3E_p37',i,2,'GCD',float(row[1]),system='3E',select=True)
        for i,row in enumerate(tables[(COT,'2E_p41')][1],1):cap(COT,row[0],'2E_p41',i,1,'GCD',.5)
        for i,row in enumerate(tables[(COT,'2E_p43')][1],1):cap(COT,row[0],'2E_p43',i,2,'GCD',float(row[1]))
        cap(COT,'CDAP800-350','tab4',9,3,'GCD',.5,extra=dict(repeats_own_p41=True,not_additional_physical_test=True))
        for i,row in enumerate(tables[(QSC,'3E_p28')][1],1):cap(QSC,row[0],'3E_p28',i,1,'GCD',.5,system='3E',M=3,select=True)
        cap(QSC,'QSC-3','tbl2',9,3,'GCD',.5,system='3E',M=3,extra=dict(repeated_own_comparison=True))
        for i,row in enumerate(tables[(CUC,'CV_p36')][1],1):cap(CUC,row[0],'CV_p36',i,1,'CV',scan=5)
        for i,row in enumerate(tables[(CUC,'GCD_p37_p38_p44')][1],1):cap(CUC,row[0],'GCD_p37_p38_p44',i,2,'GCD',float(row[1]))
        cap(CUC,'ACP-800','nanomaterials-14-00686-t004',14,3,'GCD',1,extra=dict(repeated_own_comparison=True))
        for i,row in enumerate(tables[(ANN,'GCD_p32')][1],1):cap(ANN,row[0],'GCD_p32',i,2,'GCD',float(row[1]),electrolyte='H2SO4',M=1)
        for i,row in enumerate(tables[(ANN,'neutral_GCD_p34')][1],1):cap(ANN,row[0],'neutral_GCD_p34',i,2,'GCD',float(row[1]),electrolyte='Na2SO4',M=1)
        cap(ANN,'NFAC-c','tab2',10,3,'GCD',.1,electrolyte='H2SO4',M=1,extra=dict(repeated_own_comparison=True))
        for i,row in enumerate(tables[(COT,'yield_reports')][1],1):response(COT,row[0],'yield_reports',i,2,row[1],'%',extra=dict(scope=row[3],TGA_not_assumed_product_yield=True))
        for i,row in enumerate(tables[(CUC,'response_p38_p41_p43')][1],1):response(CUC,row[0],'response_p38_p41_p43',i,2,row[1],'author_A/g_malformed' if row[1]=='CE_max_rawvalue' else 'ohm' if 'ohm' in row[1] else '%',extra=dict(qualification=row[3]))
        for i,row in enumerate(tables[(ANN,'EIS_time_p33')][1],1):response(ANN,row[0],'EIS_time_p33',i,1,'Rs_ohm','ohm');response(ANN,row[0],'EIS_time_p33',i,2,'relaxation_time_s','s')
        for i,row in enumerate(tables[(QSC,'device_energy_p39')][1],1):
            for col,metric,un in [(2,'reported_energy_Wh_kg','Wh/kg'),(3,'reported_power_W_kg','W/kg')]:response(QSC,'QSC-3','device_energy_p39',i,col,metric,un,extra=dict(electrolyte=row[0],reported_current_A_g=num(row[1]),author_energy_formula_not_validated=True))
        def candidate(doi,s,id,system,ret,n,j,lo,hi,electrolyte,M,locator,legacy=None,selected=True,extra=None):
            r=dict(source_group='doi:'+doi,system=system,method='GCD',cycle_count=n,retention_pct=ret,retention_relation='=',reported_current_A_g=j,current_mass_basis='author_reported_unknown_not_inferred',cycle_voltage_lower_V=lo,cycle_voltage_upper_V=hi,electrolyte=electrolyte,concentration_mol_L=M,reference_electrode='Hg/HgO' if system=='3E' else None,baseline_index=None,baseline_reference='author_initial_or_ownnormalized_reference_exactindexunspecified',locator=locator,evidence_source_path=next(s['path'] for s in spec['sources'] if s['doi']==doi),source_sha256=next(s['sha256'] for s in spec['sources'] if s['doi']==doi),legacy_endpoint_id=legacy,purpose_reviewed_candidate_ready=selected,**(extra or {}));insert(c,'test_candidates',dict(candidate_id=id,material_key=mk(doi,s),record_json=json.dumps(r,ensure_ascii=False),training_eligible=0))
        candidate(COT,'CDAP800-350','LP10_Cotton_3E_C5000','3E',92,5000,5,-1,0,'KOH',6,'ActualFig8cprinted92%;Fig8bGCD-1..0,methods12-14/body39')
        candidate(COT,'CDAP800-350','LP10_Cotton_2E_C5000','2E_symmetric',86,5000,5,0,1,'KOH',6,'ActualFig11aprinted86andbody44; ownFig10bGCD0..1+samecellcycle5Ag',extra=dict(competing_retention_reports_pct=[87,89],decision='Specificactualcyclefigure86corroboratedbybody44, versusabstract87andconclusion89; noauthorerratumclaimed'))
        for i,row in enumerate(tables[(QSC,'3E_cycle_p30')][1],1):candidate(QSC,row[0],'LP10_Quinoa_'+row[0]+'_3E_C10000','3E',float(row[1]),10000,5,-1,0,'KOH',3,'Ownbody30/Fig8a/commonmethod9GCD',legacy='candidate:V05:'+str(7+i).zfill(3))
        for salt,M,ret,upper,legacy in [('KOH',3,97.55,1.5,'candidate:V05:012'),('Na2SO4',1,96.2,2,'candidate:V05:013')]:candidate(QSC,'QSC-3','LP10_Quinoa_2E_'+salt+'_C10000','2E_symmetric',ret,10000,5,0,upper,salt,M,'ActualownFig11a/c8cycledinsets+body34/37; ownGCDvoltage,notCVwindoworTable3misprint',legacy=legacy)
        candidate(CUC,'ACP-800','LP10_Cucumber_2E_C2000','2E_symmetric',100,2000,1,0,.9,'KOH',6,'Ownbody38/44+Fig9d actualcycling; freshGCD0..1 remainsseparate',legacy='candidate:V05:019')
        candidate(ANN,'NFAC-c','LP10_NFAC_2E_C10000','2E_symmetric',101.7,10000,1,0,.8,'H2SO4',1,'Ownbody33+Fig8hactualbefore/afterGCDinsets0..0.8; actualCE92..95 notretention',extra=dict(real_growth_not_clipped=True,cycle_initial_capacitance_F_g_rounded=280,cycle_final_capacitance_F_g_rounded=285,fresh_rate_capacitance_at1Ag_F_g=255,fresh_rate_value_not_substituted_for_cycle_baseline=True))
        for r in json.loads((OUT/'curve_samples.json').read_text('utf8')):insert(c,'curve_samples_v8',dict(reading_id='v10_'+r['document']+'_'+r['sample']+'_'+str(r['x_value']),material_key=mk(r['doi'],r['sample']),document_key=r['document'],reading_json=json.dumps(r,ensure_ascii=False)))
        # Published model parameters/importance are not experimental material observations.
        for id in ['tab3','tab4','SI_TableS1','SI_TableS2']:
            key,rows=tables[(ANN,id)];start=1 if id.startswith('SI') else 2
            for i,row in enumerate(rows[start-1:],start):
                for col,v in enumerate(row[1:],1):
                    rid=key+'#'+str(i)+'#'+str(col);record=dict(kind='published_RF_importance_pct' if id=='tab4' else 'published_ANN_weight',value=num(v),raw_value=v,row_label=row[0],column_ordinal=col,row_ordinal=i,unit='%' if id=='tab4' else 'dimensionless_model_weight',not_experimental_sample=True)
                    insert(c,'peer_model_cells_v10',dict(record_id=rid,table_key=key,record_json=json.dumps(record,ensure_ascii=False)));receipt('peer_model',rid,key,i,col,'decimal')
        review=dict(doi=ANN,target='specific_capacitance_F_g_not_cycle_retention',claimed_literature_samples='morethan200',not_claimed_independent_papers=200,inputs=['aspect_ratio','cellulose_pct','BET','average_pore_size','total_pore_volume','micropore_volume','mesopore_volume','Raman_ID_IG','Rs','N_pct'],split='random90percenttrain/10percentvalidation',normalization='minmax0..1; train-onlyfitnotexplicitlydocumented',source_grouped_validation_reported=False,reported_training_r2=.896,reported_validation_r2=.864,reported_MSE_2_8_10_inputs=[6.38,5.50,4.39],reported_epochs=1000,training_algorithm='authorLevenberg-Marquartbackprop',reported_architecture='bodytwohiddenlayers20neurons,weighttabletenhiddenlabels; fullreproducibilitynotestablished',own_prediction_runs_F_g=[313,319,274,281,258,287,255,315],author_reported_prediction_average_F_g=289,computed_list_mean_F_g=287.75,reported_NFAC_N_zero_policy='authorinitializedN=0fromEDSnotdetected; NOTcopiedastruezero_materialfeature',data_access=dict(XLSX_claim_in_body=True,public_package_in_hand_contains_PDF9pages_and_figures=True,XLSX_present_in_package=False,PDF_embedded_files=False,available_PDF_has_only_model_weights_not_200rowdataset=True,no_proof_dataset_does_not_exist=True),applicability='Usefulfeatureandmultisamplestudy; target/unitandrandomsplitdifferentfromourretention/sourceholdout; cannotpromisesameR2/MSE. Rsrequiresmeasurementavailabilityatspecifiedpredictiontime.',new_model_fits=0)
        insert(c,'peer_model_reviews_v10',dict(doi=ANN,record_json=json.dumps(review,ensure_ascii=False)))
        for rid in preferred:
            record=dict(purpose='reported_aqueous_3e_GCD_capacitance',decision='OwnGCDvalue/current,workingactivecarbonandpreparation,3Eelectrolyte/reference/voltagebound; selectedonepermaterial/current. Cottonp14coinwordingretained; currentmassnotphysicallynormalized.',source_isolation='AllsameDOIcycles,materials,curvesandauxoutcomesheldouttogether',new_fit=False)
            insert(c,'auxiliary_gcd_reviews_v3',dict(observation_id=rid,purpose=record['purpose'],eligible=1,reason=record['decision'],review_basis='Ownbody/protocol/GCD andmaterialbindings, notsecondaryrows'));insert(c,'purpose_reviews_v10',dict(observation_id=rid,record_json=json.dumps(record,ensure_ascii=False)))
        assert len(preferred)==12
        # Synthesis stage records: preserve pre-treatment, control, and final activation separately.
        for doi,names in [(COT,COTN),(QSC,QN),(CUC,CN),(ANN,NN)]:
            for s in names:
                if doi==COT:
                    stages=[] if s=='C800' else [dict(stage='DAP_impregnation',cotton_g=10,DAP_g=10,DIwater_mL=250,duration_h=2,drying_temperature_C=100,drying_duration_h=12)]
                    stages+=[dict(stage='carbonization' if s=='C800' else 'chemical_activation',temperature_C=800,duration_h=2,heating_rate_C_min=5,atmosphere='N2',agent=None if s=='C800' else 'diammonium_hydrogen_phosphate',carbon_to_activator_mass_ratio=None,raw_biomass_to_DAP_mass_ratio=None if s=='C800' else [1,1],post_DIwater_wash=True,post_drying_C=100,post_drying_h=5)]
                    if '-' in s:stages.append(dict(stage='air_oxidation_after_carbonization',temperature_C=int(s.split('-')[-1]),duration_h=5,atmosphere='air'))
                    stages.append(dict(stage='electrode_preparation',carbon_wt_pct=80,carbonblack_wt_pct=10,PTFE_wt_pct=10,active_material_mg_per_electrode=5,area_cm2=1,press_MPa=15,drying_C=60,drying_min=30,collector='titanium_mesh'))
                elif doi==QSC:
                    stages=[dict(stage='feedstock_drying',temperature_C=60,duration_h=48,sieve_mesh=40),dict(stage='carbonization',temperature_C=600,duration_h=2,atmosphere=None,heating_rate_C_min=None)]
                    if s!='QSC':stages.append(dict(stage='chemical_activation',temperature_C=800,duration_h=2,heating_rate_C_min=5,atmosphere='N2',agent='K2CO3',carbon_to_activator_mass_ratio=[1,int(s[-1])],ratio_qualification='ownbody3char/activator; body5QSwordingretained',post_wash_HCl_M=1,post_wash_pH='neutral',post_drying_C=80,post_drying_h=8))
                    stages.append(dict(stage='electrode_preparation',carbon_wt_pct=80,acetylene_black_wt_pct=10,PTFE_wt_pct=10,active_material_mg_range=[2,3],collector='Ni_foam',area_cm2=2,drying_C=70,drying_h=12,press_MPa=10))
                elif doi==CUC:
                    stages=[dict(stage='carbonization',temperature_C=600,duration_h=2,atmosphere='Ar',Ar_flow_cm3_min=100,Ar_purity_pct=99.993)]
                    if s!='CCP':stages.append(dict(stage='chemical_activation',temperature_C=int(s[-3:]),duration_h=2,atmosphere='Ar',agent='KOH',carbon_to_activator_mass_ratio=[1,2],post_wash_HCl_M=1,post_DIwater_to_stable_pH=True,post_drying_duration='overnight_notnumber',heating_rate_C_min=None))
                    stages.append(dict(stage='electrode_preparation',carbon_wt_pct=75,carbonblack_wt_pct=10,PVDF_wt_pct=15,NMP_mL_range=[1,2],slurry_stir_min=20,collector='titanium_foil',area_cm2=2,drying_C=130,drying_h=12))
                else:
                    pretreat='Ac_H2O2_5wtpct' if s=='NFAC-a' else 'Ac_NaClO2_5wtpct' if s=='NFAC-b' else 'HF_2M' if s.startswith('NFAC-c') else None
                    stages=[] if pretreat is None else [dict(stage='raw_algae_pretreatment',agent=pretreat,temperature_C=20,duration_h=4,DIwater_wash_times=5,freeze_drying_h=24)]
                    ratio=2 if s=='NFAC-c-2' else 4 if s=='NFAC-c-4' else 3 if s.startswith('NFAC-c') else None;temp=int(s[-3:]) if s.endswith(('600','800','900')) else 700
                    stages+=[dict(stage='carbonization',temperature_C=400,duration_h=1,atmosphere='Ar'),dict(stage='chemical_activation',temperature_C=temp,duration_h=2,agent='KOH',carbon_to_activator_mass_ratio=[1,ratio] if ratio else None,ratio_basis='SI_S2/S3/S5bindNFACcdefault3; otherpretreatmentseriesnotindependentlyspecified',post_wash_HCl_M=1,post_wash_pH='neutral',post_drying_C=50,post_drying_h=24),dict(stage='electrode_preparation',carbon_wt_pct=80,PTFE_wt_pct=10,conductivecarbon_wt_pct=10,electrode_diameter_mm=8,collector='carbon_paper',collector_diameter_mm=12,drying_C=150,drying_h=5)]
                insert(c,'synthesis_stages_v3',dict(material_key=mk(doi,s),document_key=next(x['key'] for x in spec['sources'] if x['doi']==doi),locator='Ownexperimentalparagraphs + matchedSIparameterlabels, unknownsremainnull',stages_json=json.dumps(stages,ensure_ascii=False)))
        remaining='FullCV/GCD/adsorption/EISwaveforms,morphologyquantification,andunextractedfigure-specificvaluesremain; notwholepapercomplete.'
        for s in spec['sources']:
            rows=[t for t in spec['tables'] if t['doi']==s['doi']];proof=[dict(table_key=t['doi']+'#'+t['id'],locator=t['locator'],path=s['path'],sha256=s['sha256']) for t in rows];decision=dict(classification='original_biomass_research',article_type=s['article_type'],scope='Ownspecifiedcells/prose/boundedcurves; ANNweightsnotphysicaldata' if s['doi']==ANN else 'Ownspecifiedtables/prose/boundedcurves; foreigncomparisonsseparate',remaining=remaining,whole_source_completion_proven=False,units=proof)
            insert(c,'source_scope_decisions',dict(doi=s['doi'],scope='original_biomass_research',reason=decision['scope'],evidence_json=json.dumps(decision,ensure_ascii=False),full_source_review_complete=0));insert(c,'source_reviews_v10',dict(doi=s['doi'],record_json=json.dumps(decision,ensure_ascii=False)))
        issues=[('Cotton_N_envelope',COT,'CDAP800-350','Nrelativefractions107.5%,keepallfourfrozen; no100renormalization'),('Cotton_XPS_basis',COT,None,'Table2%unspecified; conclusiononlyN/Owt%explicit; noatomicinference'),('Cotton_area_partition',COT,'CDAP800-400','Smicro710+Smeso71>SBET772; keepareas, sharedcoupledfeatureswithheld'),('Cotton_yield',COT,None,'Product34vsabstract38 andTGA38.2differentfeedmass; do notbindall38.2asfinalyield'),('Cotton_2E_retention',COT,'CDAP800-350','Select86actualFig11a+ownbody44, preserveabstract87/conclusion89; authorerratumnotclaimed'),('Cotton_3E_formula_wording',COT,None,'p14coinmasswordingretained; actual3E5mgactiveworkingcontext, nofactorcurrentinference'),('Quinoa_partition',QSC,None,'Micro+mesovolumesdifferfromtotal; methodsnotexplicit,noexhaustivepartitionassumed'),('Quinoa_XPS_basis',QSC,'QSC-3','2.4/17.59%basisunspecified,notatomic'),('Quinoa_voltage',QSC,'QSC-3','Table3own1..2.0versusactualcycleinset0..2.0; actualowncycle/ownbodyselected'),('Cucumber_FWHM',CUC,None,'Multiplecommagroupedwidthraw; numericnull,nointeger/decimalguess'),('Cucumber_Corder',CUC,None,'SpecificEDAXTable91.69/88.21selected; proseapprox88/92orderdissentretained'),('Cucumber_cycle_window',CUC,'ACP-800','Actualcycle.9VnotfreshGCD1V; do notoverwritevalidoldendpoint'),('Cucumber_CE_units',CUC,'ACP-800','Authorprints94.8AgforCE; rawvalue/unitsretained,notlabelcapacitance'),('NFAC_volume_units',ANN,None,'TableVcm2/g; ownbodyonlyNFAC/NFACcVtotalexplicitcm3; noautomaticcm2tocm3'),('NFAC_N_zero',ANN,'NFAC-c','AuthorANNsetsEDSundetectedNto0; noactualzeroNfactcopied'),('NFAC_rate_retention',ANN,'NFAC-c','bodyp29rate74vsownp32190/283and67; keepreportedclaims,notcyclelabel'),('NFAC_model_scope',ANN,None,'200+sampleXLSXclaimed,notinavailablepublicpackage/PDF; random90/10specificcapnotourretention/sourceholdout'),('NFAC_power_formula',ANN,None,'PrintedpowerformulaP=E/(3600dt)unitdissentretained; energy/powernotrecomputed'),('NFAC_EIS_order',ANN,None,'Proseinequality .85>.91 invalid; retainnumericalRs'),('NFAC_target_growth',ANN,'NFAC-c','101.7%realreportedretention notclipped; initial280vsfresh255keptdistinct')]
        for name,doi,s,action in issues:insert(c,'scientific_issues',dict(issue_id='LP10_'+name,doi=doi,sample_name=s,issue_json=json.dumps(dict(kind=name,action=action),ensure_ascii=False)))
        c.commit()
    protected=[dict(path=d['path'].relative_to(ROOT).as_posix(),sha256=sha(d['path'])) for d in docs.values()]
    protected.extend([dict(path=PARENT.relative_to(ROOT).as_posix(),sha256=PSHA),dict(path='全库复检与特征补提取_20261021/full_corpus_search_native.sqlite',sha256='f2720c3e417904dad5857a6574cc72d5cf996f9b8716620d69594f11380c658c')]);write(OUT/'protected_inputs.json',dict(files=protected));audit();print('Builtv10withoutmodeltraining')

def audit():
    assert not(OUT/'merge_manifest.json').exists()
    with closing(sqlite3.connect(DB))as c:
        assert c.execute('select count(*)from numerical_audits_v10').fetchone()[0]==0
        def add(id,doi,r):insert(c,'numerical_audits_v10',dict(audit_id=id,doi=doi,record_json=json.dumps(r,ensure_ascii=False)))
        for tid,cols,total,kind in [('tab1',[2,3],1,'pore_surface_partition'),('tab1',[5,6],4,'pore_volume_partition'),('tab2',[1,2,3,4],None,'XPS_unspecified_percent_sum'),('tab3',[1,2,3,4],None,'N1s_envelope_sum'),('tab3',[5,6,7],None,'O1s_envelope_sum')]:
            rows=[json.loads(r[0])for r in c.execute('select cells_json from transcribed_rows where table_key=? and row_ordinal>1 order by row_ordinal',(COT+'#'+tid,))]
            for row in rows:
                component=sum(num(row[k])for k in cols);target=num(row[total])if total else 100
                add(kind+'_'+row[0],COT,dict(kind=kind,sample_name=row[0],reported_total=target,computed_component_sum=component,difference=component-target,decision='Arithmeticdiagnosticnotmeasurement; originalallcellsretained, noforcedclosure'))
        rows=[json.loads(r[0])for r in c.execute('select cells_json from transcribed_rows where table_key=? and row_ordinal>1',(QSC+'#tbl1',))]
        for row in rows:add('Quinoa_volume_'+row[0],QSC,dict(kind='pore_partition_methods_not_assumed_exhaustive',sample_name=row[0],total_volume_cm3_g=num(row[3]),sum_micro_meso=num(row[4])+num(row[5]),decision='Methodsnotfullyspecified; keepgap, noautomaticcorrectionorfraction'))
        r=json.loads(c.execute('select record_json from peer_model_reviews_v10').fetchone()[0]);add('ANN_mean',ANN,dict(kind='published_model_prediction_list_mean',reported_mean=r['author_reported_prediction_average_F_g'],computed_mean=sum(r['own_prediction_runs_F_g'])/8,not_new_experimental_data=True))
        c.commit()

def verify(prepare=False):
    checks=[]
    def ck(name,ok):
        if not ok:raise AssertionError(name)
        checks.append(name)
    spec=json.loads((OUT/'curation_spec.json').read_text('utf8'));digest=sha(DB)
    for p in json.loads((OUT/'protected_inputs.json').read_text('utf8'))['files']:ck('protected_'+p['path'],sha(ROOT/p['path'])==p['sha256'])
    for p in json.loads((PARENT.parent/'merge_manifest.json').read_text('utf8'))['outputs']:ck('v9payload_'+p['path'],sha(ROOT/p['path'])==p['sha256'])
    for label in ['Cotton','AlgaeANN']:
        receipt=json.loads((EV/(label+'_acquisition.json')).read_text('utf8'));package=ROOT/receipt['path'];ck('packageSHA_'+label,sha(package)==receipt['sha256'])
        with zipfile.ZipFile(package) as z:
            for p in EV.iterdir():
                if p.name in z.namelist():ck('original_package_member_'+p.name,p.read_bytes()==z.read(p.name))
    ck('70image_readings_reproducible',json.loads((OUT/'curve_samples.json').read_text('utf8'))==sample_curves())
    with closing(ro(DB)) as c,closing(ro(PARENT)) as old:
        c.row_factory=sqlite3.Row;ck('integrity',c.execute('pragma integrity_check').fetchone()[0]=='ok');ck('FK',not c.execute('pragma foreign_key_check').fetchall())
        for(t,)in old.execute("select name from sqlite_master where type='table' and name not like 'sqlite_%'"):
            if t=='raw_table_queue':continue
            now={tuple(r) for r in c.execute('select * from '+t)};ck('parent_'+t,all(tuple(r)in now for r in old.execute('select * from '+t)))
        oldq={r[0]:tuple(r) for r in old.execute('select * from raw_table_queue')};newq=[tuple(r)for r in c.execute('select * from raw_table_queue')];ids={t['raw_table_id']for t in spec['tables']};ck('only15queueupdates',{r[0]for r in newq if r!=oldq[r[0]]}==ids and len(ids)==15)
        for r in newq:ck('queue_protection_'+r[0],r[:6]==oldq[r[0]][:6] and r[7:]==oldq[r[0]][7:])
        for t in spec['tables']+spec['units']:
            key=t['doi']+'#'+t['id'];rows=[json.loads(r[0])for r in c.execute('select cells_json from transcribed_rows where table_key=? order by row_ordinal',(key,))]
            if 'grid'in t:
                s=next(s for s in spec['sources']if s['key']==t['document']);grid=xml_grid(E.parse(ROOT/s['path']).find(".//table-wrap[@id='"+t['id']+"']"));ck('original_XML_spans_'+key,grid==t['grid']);expected=[[x['raw']for x in row]for row in grid]
            else:expected=t['rows']
            ck('transcription_'+key,rows==expected)
        ck('SIweights_exact_PDF_tokens',[t['rows']for t in spec['units']if t['id']in['SI_TableS1','SI_TableS2']]==si_weight_rows())
        for r in c.execute('select * from cell_extractions_v10'):
            value=json.loads(c.execute('select cells_json from transcribed_rows where table_key=? and row_ordinal=?',(r['table_key'],r['row_ordinal'])).fetchone()[0])[r['column_ordinal']]
            tab,k=('material_facts','fact_id')if r['kind']=='fact'else('capacitance_observations','observation_id')if r['kind']=='capacitance'else('peer_model_cells_v10','record_id')if r['kind']=='peer_model'else('outcome_observations_v3','outcome_id');out=c.execute('select * from '+tab+' where '+k+'=?',(r['record_id'],)).fetchone();v=json.loads(out['record_json'])if r['kind']in['response','peer_model']else out
            ck('raw_'+r['kind']+r['record_id'],v['raw_value']==value);ck('value_'+r['kind']+r['record_id'],v['value']==num(value,r['parse_mode']))
        for t in ['material_facts','capacitance_observations','outcome_observations_v3','test_candidates','raw_table_queue']:ck('no_auto_raw_admission_'+t,c.execute('select count(*)from '+t+' where training_eligible!=0 or training_eligible is null').fetchone()[0]==0)
        count=lambda t:c.execute('select count(*)from '+t).fetchone()[0];prior=json.loads((PARENT.parent/'summary.json').read_text('utf8'));summary=dict(prior)
        summary.update(cumulative_reviewed_source_publications=count('reviewed_sources'),cumulative_materials=count('materials'),cumulative_selected_material_cells=count('material_facts'),cumulative_numeric_material_facts=c.execute('select count(*)from material_facts where value is not null').fetchone()[0],capacitance_records=count('capacitance_observations'),numeric_capacitance_values=c.execute('select count(*)from capacitance_observations where value is not null').fetchone()[0],unreported_material_cells=c.execute('select count(*)from material_facts where value is null').fetchone()[0],cycling_candidates=count('test_candidates'),scientific_issues=count('scientific_issues'),synthesis_materials=count('synthesis_stages_v3'),response_outcomes=count('outcome_observations_v3'),reviewed_table_units=123,reviewed_evidence_units=204,raw_candidates_touched=106,raw_candidates_untouched=853,new_materials=21,new_bounded_curve_samples=70,cumulative_bounded_curve_samples=count('curve_samples_v8'),peer_model_numeric_cells=count('peer_model_cells_v10'),auxiliary_aqueous_3e_GCD_rows=133,auxiliary_purpose_reviewed_input_rows=149,auxiliary_independent_DOI_groups=11,formal_cycling_admissions=0,model_fits=0,all_literature_fully_utilized=False)
        newpanels=len({(r['document'],r['panel'])for r in json.loads((OUT/'curve_samples.json').read_text('utf8'))});newunits=count('reviewed_tables')-old.execute('select count(*)from reviewed_tables').fetchone()[0]
        readings=json.loads((OUT/'curve_samples.json').read_text('utf8'));oldgroups={json.loads(r[0])['curve_group']for r in old.execute('select reading_json from curve_samples_v8')};newgroups={r['curve_group']for r in readings}
        summary.update(reviewed_evidence_units=prior['reviewed_evidence_units']+newunits+newpanels,curve_sampling_panels=prior['curve_sampling_panels']+newpanels,new_numeric_material_facts=summary['cumulative_numeric_material_facts']-prior['cumulative_numeric_material_facts'],new_capacitance_reports=summary['capacitance_records']-prior['capacitance_records'],new_response_records=summary['response_outcomes']-prior['response_outcomes'],new_source_response_records=summary['response_outcomes']-prior['response_outcomes'],new_own_main_tables=13,new_own_SI_tables=0,new_peer_model_main_tables=2,new_peer_model_SI_tables=2,new_secondary_review_tables=0,new_non_biomass_coal_reference_tables=0,new_curve_groups=len(newgroups),cumulative_curve_groups=len(oldgroups|newgroups),scope_note='Fourprimarysources,ownspecifiedfacts/reports/70boundedcurves andpeerANNreference separated.15rawcandidatesreviewed,853untouched; all27sourcespartial. No newfits. Cycleadmissionsinindependentv0.22review.')
        ck('27sources_partial',count('reviewed_sources')==27 and c.execute('select sum(full_source_review_complete)from source_scope_decisions').fetchone()[0]==0)
        ck('853untouched',c.execute("select count(*)from raw_table_queue where review_state='automatic_candidate_unreviewed'").fetchone()[0]==853)
        ck('240modelcells_notphysical',count('peer_model_cells_v10')==240);ck('54candidates',count('test_candidates')==54);ck('28new_arithmetic_audits',count('numerical_audits_v10')==28)
    from data.literature_v10 import open_literature_database as api10
    from data.literature_v9 import open_literature_database as api9
    with api10(DB,digest) as new,api9(PARENT,PSHA) as old:
        for profile in ['3e','2e_device','native_mineral_3e','2e_author_factor2']:
            before=old.auxiliary_feature_rows(profile);after=new.auxiliary_feature_rows(profile);ids={r['observation_id']for r in before};ck('oldaux_preserved_'+profile,[r for r in after if r['observation_id']in ids]==before)
        ck('new12ordinary3E',[sum(r['doi']==doi for r in new.auxiliary_feature_rows('3e'))for doi in[COT,QSC]]==[8,4]);ck('all3E133',len(new.auxiliary_feature_rows('3e'))==133)
        for target in ['retention','capacitance']:ck('DES_unchanged_'+target,new.des_reported_inputs(target)==old.des_reported_inputs(target))
        ck('15feature_freeze_records_preserved',new.legacy_feature_conflicts()==old.legacy_feature_conflicts());ck('one_composite_unchanged',new.composite_cycle_inputs()==old.composite_cycle_inputs());ck('128curve_samples',len(new.sampled_curves())==128)
        ck('all_candidate_groups',all(r['record'].get('source_group') for r in new.tests()));ck('peer_target_not_retention',new.peer_model_review()['target']=='specific_capacitance_F_g_not_cycle_retention')
    ck('readonlyhash',sha(DB)==digest);report=dict(status='passed',database_sha256=digest,check_count=len(checks),checks=checks,model_fits=0,full_goal_complete=False)
    if prepare:
        assert not(OUT/'merge_manifest.json').exists();write(OUT/'summary.json',summary);write(OUT/'verification.json',report)
    else:
        assert json.loads((OUT/'summary.json').read_text('utf8'))==summary;assert json.loads((OUT/'verification.json').read_text('utf8'))==report
        if(OUT/'merge_manifest.json').exists():
            for p in json.loads((OUT/'merge_manifest.json').read_text('utf8'))['outputs']:assert sha(ROOT/p['path'])==p['sha256'],p['path']
    print(json.dumps(dict(summary=summary,checks=len(checks)),ensure_ascii=False))

def seal():
    if(OUT/'merge_manifest.json').exists():raise FileExistsError('Alreadysealed')
    verify(False);paths=[p for p in OUT.rglob('*')if p.is_file()]+[ROOT/'tools/extract_four_sources_v10.py',ROOT/'data/literature_v10.py',ROOT/'tools/verify_corpus_chain_v10.py']
    write(OUT/'merge_manifest.json',dict(version='literature_pool_v10',parent_sha256=PSHA,outputs=[dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p),bytes=p.stat().st_size)for p in sorted(paths)],model_fits=0,scientific_goal_complete=False))
    write(ROOT/'data/current_literature.json',dict(version='literature_pool_v10',directory=OUT.relative_to(ROOT).as_posix(),database_file=DB.name,sha256=sha(DB),api_module='data.literature_v10',scope='Fourprimarysources,ownfacts/reports/70boundedcurves; peerANN240parametercellsseparate, nofit.'))
if __name__=='__main__':
    if len(sys.argv)!=2 or sys.argv[1]not in['curate','build','refresh_curves','audit','prepare','verify','seal']:raise SystemExit('One-usecurate/build/prepare/seal; verifyreadonly')
    if sys.argv[1]=='prepare':verify(True)
    else:globals()[sys.argv[1]]()
