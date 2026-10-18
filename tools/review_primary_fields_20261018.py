"""Apply bounded source reviews to this task's v0.4 only; append every selection change."""
from pathlib import Path
import collections,hashlib,json,re,sqlite3,unicodedata,xml.etree.ElementTree as ET
R=Path(__file__).resolve().parents[1];O=R/'循环稳定性数据库_v0.4_提取与调用_20261018'
def enc(x):return json.dumps(x,ensure_ascii=False)
def norm(x):return ''.join(v for v in unicodedata.normalize('NFKC',str(x)).casefold() if v.isalnum())
def number(x):
 try:return float(re.sub(r'\s+','',x).replace(',',''))
 except (ValueError,TypeError):return None

def main():
 c=sqlite3.connect(O/'cycling_v0_4.sqlite');c.row_factory=sqlite3.Row;c.execute('pragma foreign_keys=ON')
 if c.execute("select count(*) from extraction_run where key='bounded_source_review_complete'").fetchone()[0]:raise RuntimeError('Source reviews already applied')
 te=json.loads((R/'三电极端点扩充_20261018/三电极端点_53条.json').read_text(encoding='utf-8'))['rows'];bytag={x['source_tag']:x for x in te};log=[]
 before=dict(c.execute('select sum(BET_m2_g is not null),sum(total_pore_volume_cm3_g is not null) from review_3e_rows').fetchone()) if False else list(c.execute('select sum(BET_m2_g is not null),sum(total_pore_volume_cm3_g is not null) from review_3e_rows').fetchone())
 units={'BET_m2_g':'m2/g','total_pore_volume_cm3_g':'cm3/g','micropore_volume_cm3_g':'cm3/g','BJH_ads_pore_volume_cm3_g':'cm3/g','raw_total_pore_volume_m3_g':'m3/g','reported_pore_volume_Vp_cm3_g':'cm3/g','reported_current_A_g':'A/g','concentration_mol_L':'mol/L','cycle_voltage_lower_V':'V','cycle_voltage_upper_V':'V','characterization_voltage_lower_V':'V','characterization_voltage_upper_V':'V'}
 def source(tag):return bytag[tag]['source_sha256']
 def locate(tag,needle=None,locator=None):
  sid=source(tag);rs=c.execute('select * from source_segments where source_id=? order by segment_id',(sid,)).fetchall()
  canonical=lambda v:''.join(v.split()).casefold().replace('−','-').replace('–','-')
  found=[x for x in rs if (locator is None or x['locator']==locator) and (needle is None or canonical(needle) in canonical(x['text']))]
  if not found:raise RuntimeError('Evidence not found: '+tag+' '+str(needle)+' '+str(locator))
  return dict(found[0])
 def endpoints_for(tag,sample=None):
  aliases=[x['endpoint_id'] for x in te if x['source_tag']==tag and (sample is None or norm(x['sample'])==norm(sample))]
  return [c.execute("select endpoint_id from endpoint_aliases where namespace='TE' and alias=?",(a,)).fetchone()[0] for a in aliases]
 def put(ep,f,v,status,segment,reason,unit=None):
  old=c.execute('select observation_id from field_selection where endpoint_id=? and field_name=?',(ep,f)).fetchone();unit=unit or units.get(f)
  q=c.execute('insert into field_observations(endpoint_id,field_name,value_json,unit,status,source_id,segment_id,locator,evidence_excerpt,provenance_json) values (?,?,?,?,?,?,?,?,?,?)',(ep,f,enc(v),unit,status,segment['source_id'],segment['segment_id'],segment['locator'],segment['text'][:3500],enc({'review':'20261018_bounded_primary_source_review','scope':reason})))
  c.execute('insert or replace into field_selection values (?,?,?)',(ep,f,q.lastrowid));c.execute('insert into field_selection_history(endpoint_id,field_name,old_observation_id,new_observation_id,reason) values (?,?,?,?,?)',(ep,f,old[0] if old else None,q.lastrowid,reason));log.append({'endpoint_id':ep,'field':f,'value':v,'status':status,'source_id':segment['source_id'],'locator':segment['locator'],'reason':reason})
 def issue(tag,field,code,segments,reason,sample=None):
  for ep in endpoints_for(tag,sample):c.execute('insert into extraction_issues(endpoint_id,identity_key,field_name,code,status,evidence_json,reason) values (?,?,?,?,?,?,?)',(ep,c.execute('select identity_key from model_endpoints where endpoint_id=?',(ep,)).fetchone()[0],field,code,'open',enc(segments),reason))
 # Column mappings below were inspected against the actual headers/units, not inferred from the numbers.
 configs=[('EXT_001','molecules-31-02329-t004',{1:'BET_m2_g',2:'total_pore_volume_cm3_g'}),('EXT_002','nanomaterials-15-00387-t002',{1:'BET_m2_g',2:'total_pore_volume_cm3_g'}),('EXT_003','molecules-28-06543-t001',{1:'BET_m2_g',4:'total_pore_volume_cm3_g'}),('EXT_005','polymers-15-03976-t001',{1:'BET_m2_g',4:'total_pore_volume_cm3_g'}),('EXT_011','tbl2',{1:'BET_m2_g',3:'BJH_ads_pore_volume_cm3_g'}),('PMC12794195','tab1',{1:'BET_m2_g',3:'total_pore_volume_cm3_g'}),('PMC12175059','tab1',{1:'BET_m2_g'}),('PMC10759806','tab1',{1:'BET_m2_g',3:'total_pore_volume_cm3_g'}),('PMC9738515','nanomaterials-12-04204-t001',{1:'BET_m2_g',5:'micropore_volume_cm3_g'}),('PMC6843703','tbl1',{1:'BET_m2_g',3:'total_pore_volume_cm3_g'}),('PMC8912637','nanomaterials-12-00810-t002',{1:'BET_m2_g',2:'total_pore_volume_cm3_g'}),('PMC8585355','materials-14-06592-t001',{1:'BET_m2_g',2:'total_pore_volume_cm3_g'}),('PMC8707477','nanomaterials-11-03175-t001',{1:'BET_m2_g',4:'reported_pore_volume_Vp_cm3_g'}),('PMC9038012','tab1',{1:'BET_m2_g',3:'total_pore_volume_cm3_g'}),('PMC12158216','polymers-17-01544-t001',{1:'BET_m2_g',4:'total_pore_volume_cm3_g'}),('PMC7770663','Tab1',{1:'BET_m2_g',4:'total_pore_volume_cm3_g'})]
 for tag,table_id,mapping in configs:
  root=ET.parse(R/bytag[tag]['source_file']).getroot();table=next(t for t in root.findall('.//table-wrap') if t.get('id')==table_id);seg=locate(tag,locator='XML table-wrap '+table_id)
  identity=c.execute("select identity_key from literature_aliases where batch='three_electrode_53' and local_id=?",(bytag[tag]['endpoint_id'],)).fetchone()[0]
  for row in table.findall('.//tr'):
   cells=[re.sub(r'\s+',' ',' '.join(v.itertext())).strip() for v in row]
   if not cells or not any(k<len(cells) and number(cells[k]) is not None for k in mapping):continue
   sample=cells[0];materials=c.execute('select material_id from model_materials where identity_key=?',(identity,)).fetchall();materials=[v[0] for v in materials if norm(c.execute('select sample_name from model_materials where material_id=?',(v[0],)).fetchone()[0])==norm(sample)]
   mid=materials[0] if materials else 'material:'+hashlib.sha256(enc((identity,norm(sample))).encode()).hexdigest()[:24]
   if not materials:c.execute('insert or ignore into model_materials values (?,?,?,?,NULL)',(mid,identity,sample,'characterized_sample_without_assumed_cycle_label'))
   for col,f in mapping.items():
    value=number(cells[col]) if col<len(cells) else None
    if value is None:continue
    c.execute('insert into material_properties(material_id,property_name,reported_value,numeric_value,unit,stage,method,status,source_id,segment_id,locator,raw_row_json) values (?,?,?,?,?,?,?,?,?,?,?,?)',(mid,f,cells[col],value,units.get(f),'as_prepared_before_electrochemical_cycling','N2_sorption_table','direct_table_cell',seg['source_id'],seg['segment_id'],seg['locator']+' row '+sample,enc(cells)))
    for ep in endpoints_for(tag,sample):
     if f in ('BET_m2_g','total_pore_volume_cm3_g'):put(ep,f,value,'reported_direct_table',seg,'Exact sample row and inspected column header; precycling material characterization, not postcycle.')
 # Transposed table: printed total/micropore unit is m3/g. Keep it unconverted and out of total-pore model input.
 tag='PMC10056672';root=ET.parse(R/bytag[tag]['source_file']).getroot();table=next(t for t in root.findall('.//table-wrap') if t.get('id')=='micromachines-14-00572-t002');seg=locate(tag,locator='XML table-wrap micromachines-14-00572-t002');trs=[[' '.join(v.itertext()) for v in row] for row in table.findall('.//tr')]
 for col,sample in enumerate(trs[0][1:],1):
  for ep in endpoints_for(tag,sample):
   put(ep,'BET_m2_g',number(trs[1][col]),'reported_direct_table',seg,'Transposed table: exact DRY/WET sample column.');put(ep,'raw_total_pore_volume_m3_g',number(trs[5][col]),'printed_unit_pending',seg,'Table explicitly prints m3/g; no silent conversion to cm3/g.')
   issue(tag,'total_pore_volume_cm3_g','printed_pore_volume_unit_requires_review',[dict(seg)],'Total pore volume printed as m3/g; preserve original and withhold canonical cm3/g.',sample)
 # PDF table values were visually reviewed in evidence_images; each value is checked in its original page text.
 pdf_tables=[('U002','PDF p12',{'OPC':(10.9,0.053),'OPB':(871.9,0.36),'OPNP':(1894.9,0.83),'OPBNP':(1774.8,0.81)}),('U013','PDF p5',{'SSC2-0.6':(1658.8,0.84)}),('U016','PDF p4',{'KAC-5':(1441.3,0.5992)})]
 for tag,loc,data in pdf_tables:
  seg=locate(tag,locator=loc)
  for sample,(bet,pore) in data.items():
   for ep in endpoints_for(tag,sample):
    put(ep,'BET_m2_g',bet,'reported_direct_visual_table',seg,'Visual row/column review; exact sample BET, not neighboring sample.');put(ep,'total_pore_volume_cm3_g',pore,'reported_direct_visual_table',seg,'Visual row/column review; total pore column distinct from micropore column.')
 # Direct statements with explicit target-sample binding.
 statements=[('B_R013','1589.0',{'BET_m2_g':1589.0,'total_pore_volume_cm3_g':0.82}),('B_R087','1382 1344 1184 959 715',{'BET_m2_g':715.0,'total_pore_volume_cm3_g':0.3503}),('B_SRC025','2333.4',{'BET_m2_g':2333.4}),('B_SRC121','1374',{'BET_m2_g':1374.0}),('EXT_015','615',{'BET_m2_g':615.0}),('U018','2011',{'BET_m2_g':2011.0}),('U024','375, 718',{'BET_m2_g':718.0}),('PMC8838214','1293.2',{'BET_m2_g':1293.2}),('B_R085','582.9',{'BET_m2_g':582.9})]
 for tag,needle,data in statements:
  try:seg=locate(tag,needle)
  except RuntimeError:
   if tag=='B_R087':seg=locate(tag,locator='PDF p6')
   else:raise
  for ep in endpoints_for(tag):
   for f,value in data.items():put(ep,f,value,'reported_direct_primary_passage',seg,'Read exact target sample in its own article; value is precycling characterization. No source-admission clearance implied.')
 # Verify corrections and contradictions from original methods/results. Old observations remain in selection history.
 seg=locate('B_SRC025','2 M KOH was used')
 for ep in endpoints_for('B_SRC025'):put(ep,'concentration_mol_L',2.0,'corrected_with_primary_evidence',seg,'Prior TE005 says6 M; own methods and3E results consistently say2 M. Preserve6 in prior observation; corrected reported condition only.')
 seg=locate('PMC8912637','electrolyte was 3 M KOH')
 for ep in endpoints_for('PMC8912637'):put(ep,'concentration_mol_L',3.0,'corrected_with_primary_evidence',seg,'Prior TE044 says6 M; own methods and3E results explicitly say3 M. Preserve prior6 M and source versions.')
 seg=locate('PMC8838214','94.83')
 # Select the body paragraph that explicitly includes both5 A/g and3000cycles rather than a comparison citation.
 candidates=c.execute('select * from source_segments where source_id=? and text like ?',(source('PMC8838214'),'%94.83%')).fetchall();seg=dict(next(x for x in candidates if '5 A' in x['text'] and ('3000' in x['text'] or '3,000' in x['text'])))
 for ep in endpoints_for('PMC8838214'):
  put(ep,'reported_current_A_g',5.0,'reported_direct_cycle_current',seg,'Cycle-life paragraph explicitly binds5 A/g toTCZn-800 at3000cycles; current denominator remains unfinalized.');put(ep,'retention_relation','approx','verified_existing_approximate_qualifier',seg,'Original TE043 already marks approx; own primary wording confirms about94.83%; retain its approximate relation.');put(ep,'value_kind','reported_approximate','verified_existing_approximate_qualifier',seg,'Same primary wording about94.83%.')
 # Methods6 mol/L and result/figure caption1 M conflict; no latest-write choice.
 method=locate('EXT_005','6 mol');result=locate('EXT_005','1 M KOH')
 for ep in endpoints_for('EXT_005'):put(ep,'concentration_mol_L',None,'conflict_unresolved',result,'Methods state6 mol/L KOH but3E results/caption state1 M; keep both, canonical input withheld.')
 issue('EXT_005','concentration_mol_L','methods_vs_results_concentration',[method,result],'6 mol/L in methods versus1 M in3E results/caption; unresolved scientific contradiction.')
 # Table/header versus prose unit conflicts are not silently repaired.
 seg=locate('EXT_003','1572.1 cm')
 for ep in endpoints_for('EXT_003'):put(ep,'BET_m2_g',None,'unit_conflict_table_vs_prose',seg,'Table1 reports1572.1 m2/g but result prose prints1572.1 cm2/g. Table observation retained; canonical BET withheld pending unit review.')
 issue('EXT_003','BET_m2_g','table_vs_prose_area_unit',[seg],'Tablem2/g versus bodycm2/g forYPAC-1; no implicit correction.')
 seg=locate('EXT_002','0.634 m')
 for ep in endpoints_for('EXT_002'):put(ep,'total_pore_volume_cm3_g',None,'unit_conflict_table_vs_prose',seg,'Table2 usescm3/g; conclusion prints0.634m3/g. Preserve both and withhold optional canonical pore value.')
 issue('EXT_002','total_pore_volume_cm3_g','table_vs_conclusion_pore_unit',[seg],'Tablecm3/g versus conclusionm3/g; optional feature held.')
 # Method/characterization windows remain separate from the actual long-cycle window.
 for tag,needle,low,high in [('B_R013','potential window spanning',-1.0,0.2),('EXT_001','potential window was set',-1.0,0.0),('EXT_011','same potential window',-1.0,-0.2),('U021','−1.2 to −0.2',-1.2,-0.2),('PMC9038012','potential range of',-1.0,0.0),('PMC7770663','potential window in acidic',-0.1,0.9),('PMC12158216','−1.0 to 0 V voltage window',-1.0,0.0)]:
  seg=locate(tag,needle)
  for ep in endpoints_for(tag):
   put(ep,'characterization_voltage_lower_V',low,'reported_method_window_only',seg,'Method/CV/GCD characterization window; not automatically bound to the long-cycle test.');put(ep,'characterization_voltage_upper_V',high,'reported_method_window_only',seg,'Same method-scope limitation.')
 seg=locate('EXT_013','Long-term cyclic stability')
 for ep in endpoints_for('EXT_013'):
  put(ep,'cycle_voltage_lower_V',-1.0,'reported_direct_cycle_window',seg,'Own long-term5000GCDcycles at10 A/g explicitly state−1 to0 V.');put(ep,'cycle_voltage_upper_V',0.0,'reported_direct_cycle_window',seg,'Same cycle-specific primary statement.');put(ep,'baseline_reference','author_initial_capacitance_unspecified_cycle','reported_direct_reference',seg,'Author explicitly says94.3% of initial capacitance; no exact baseline circle index invented.')
 # Prior B20 claim is qualitative, even though its historical numeric field used100.
 for row in c.execute("select a.endpoint_id,o.source_json from endpoint_aliases a join literature_observations o on o.batch='B20' and a.alias like o.local_id||':%' where a.namespace='B20'").fetchall():
  x=json.loads(row['source_json'])
  if x.get('candidate_id')=='B2_018':
   ep=row['endpoint_id'];obs=c.execute('select d.* from paper_documents p join source_segments d using(source_id) where p.identity_key=? limit1'.replace('limit1','limit 1'),(c.execute('select identity_key from model_endpoints where endpoint_id=?',(ep,)).fetchone()[0],)).fetchone()
   if obs:
    seg=dict(obs);put(ep,'retention_pct',None,'qualitative_near100_no_exact_numeric_label',seg,'B2_018 historical value100 is explicitly near_100_qualitative; raw claim retained, numeric modeling label withheld.');put(ep,'retention_relation','qualitative','qualified_prior_claim',seg,'Unresolved2E/3E and qualitative near100 never become an exact point.')
 # All53 priority observations have explicit completion/hold states; the rest remain in the ordered queue.
 for x in te:
  ep=endpoints_for(x['source_tag'],x['sample'])
  for e in ep:
   if c.execute('select count(*) from field_selection s join field_observations o using(observation_id) where s.endpoint_id=? and s.field_name="BET_m2_g" and json_extract(o.value_json,"$") is null',(e,)).fetchone()[0]:issue(x['source_tag'],'BET_m2_g','BET_unlocated_or_binding_unresolved',[], 'No safe exact-sample BET selected from reviewed main/SI; no paper optimum or related material substituted.',x['sample'])
 c.execute("update extraction_queue set status='priority_fields_reviewed_with_open_scientific_holds',reason='Own main/SI indexed; bounded field review applied. Denominator, exact cycle protocol, material independence and missing evidence remain explicit.' where identity_key in(select distinct identity_key from staged_cycling_evidence)")
 c.execute('insert into extraction_run values (?,?)',('bounded_source_review_complete',enc(True)));c.commit();after=list(c.execute('select sum(BET_m2_g is not null),sum(total_pore_volume_cm3_g is not null) from review_3e_rows').fetchone());summary={'3E_BET_and_total_pore_before':before,'3E_BET_and_total_pore_after':after,'new_primary_field_selections':len(log),'material_property_cells':c.execute('select count(*) from material_properties').fetchone()[0],'open_review_issues':c.execute('select count(*) from extraction_issues').fetchone()[0]};(O/'本轮直接提取与更正.json').write_text(json.dumps({'summary':summary,'selections':log},ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(enc(summary));c.close()
if __name__=='__main__':main()
