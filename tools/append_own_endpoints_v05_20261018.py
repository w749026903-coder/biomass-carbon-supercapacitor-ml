"""Add manually bound own-paper endpoint candidates. No automatic-claim promotion."""
from pathlib import Path
import hashlib,json,re,sqlite3,xml.etree.ElementTree as ET
R=Path(__file__).resolve().parents[1];O=R/'循环稳定性数据库_v0.5_逐条准入审查_20261018'
def enc(x):return json.dumps(x,ensure_ascii=False)
def key(*xs):return hashlib.sha256(enc(xs).encode()).hexdigest()[:24]

def main():
 c=sqlite3.connect(O/'cycling_v0_5.sqlite');c.row_factory=sqlite3.Row;c.execute('pragma foreign_keys=ON')
 if c.execute("select count(*) from extraction_run where key='v05_own_endpoint_append'").fetchone()[0]:raise RuntimeError('Already applied')
 q=json.loads((O/'尚无结构记录_81篇审查队列.json').read_text(encoding='utf-8'));cases=[]
 def add(i,sample,system,N,ret,seg,current=None,relation='eq',method='GCD',extra=None,segments=None,note=''):
  vals={'cycle_count':N,'retention_pct':ret,'retention_relation':relation,'value_kind':'reported_exact' if relation=='eq' else 'reported_approximate' if relation=='approx' else 'derived_loss_complement' if relation=='derived_complement' else 'reported_censored','reported_current_A_g':current}
  vals.update(extra or {});cases.append({'i':i,'sample':sample,'system':system,'method':method,'segment':seg,'evidence_segments':segments or [seg],'values':vals,'note':note})
 add(1,'C1000G0.2','2E_symmetric',10000,98,1204,2,segments=[1204,1205],note='SSP900 precursor/previous-work relation unresolved. AbstractBETcm2/g vsTable1m2/g not harmonized.')
 add(4,'RPPAC-0.25-850','2E_symmetric',6000,88,6029,10,'approx',segments=[6017,6020,6029],extra={'BET_m2_g':553},note='Conclusion about88%; preserve approximation. BET553 only ownsamplep4; cycle window0–1V explicitly links GCD/cycling inmethods, not selected without separate protocol review.')
 add(6,'AC (Eucalyptus seeds)','2E_symmetric',10000,76.5,5851,.5,'approx',segments=[5842,5851],extra={'BET_m2_g':610.248},note='Ownbodyaround76.5%; BETfromownkinetic discussionp9 added separately below.')
 add(8,'RH-900','2E_symmetric',10000,95.23,5761,segments=[5746,5760,5761],extra={'electrolyte':'KOH','concentration_mol_L':6},note='Ownhighlights12A/g vsbody20A/g: reported current masked; do not choose20based on later text.')
 add(10,'AC-N','2E_symmetric',10000,80.1,5528,1,segments=[5526,5527,5528,5529])
 add(15,'N3OPC-3','3E',10000,93.5,5907,method='CV',note='Actualscanrate200mV/s; no invented GCDcurrent. Device is separate.')
 add(15,'N3OPC-3','2E_symmetric',10000,89,5909,20,segments=[5901,5909])
 for sample,ret in [('QSC',93.6),('QSC-2',94.8),('QSC-3',97.8),('QSC-4',95.5)]:
  add(19,sample,'3E',10000,ret,4731,5,segments=[4702,4724,4731],extra={'electrolyte':'KOH','concentration_mol_L':3,'reference_electrode':'Hg/HgO'})
 for electrolyte,molar,ret in [('KOH',3,97.55),('Na2SO4',1,96.2)]:
  add(19,'QSC-3','2E_symmetric',10000,ret,4741,5,segments=[4704,4741],extra={'electrolyte':electrolyte,'concentration_mol_L':molar})
 add(22,'NSGP','2E_symmetric',5000,99.46,5027,5,segments=[5025,5026,5027],extra={'electrolyte':'H2SO4','concentration_mol_L':1})
 add(24,'PPC-500-1-1h','2E_symmetric',20000,99.3,5989,10,segments=[5981,5988,5989],extra={'electrolyte':'KOH','concentration_mol_L':6})
 add(25,'HPC-P8','2E_symmetric',5000,93.8,5972,10,segments=[5960,5962,5972,5975],extra={'electrolyte':'Na2SO4','concentration_mol_L':1})
 add(28,'NSOC-800','3E',5000,90.1,3717,1,segments=[3712,3716,3717],extra={'electrolyte':'KOH','concentration_mol_L':6,'reference_electrode':'calomel'})
 add(31,'SNPB-800-4','3E',10000,94.14,4242,10,segments=[4216,4239,4242],extra={'electrolyte':'KOH','concentration_mol_L':6,'reference_electrode':'Hg/HgO','BET_m2_g':2923.7,'total_pore_volume_cm3_g':1.8448},note='Conclusionrounded5%loss retained inpaperreview, not a second independent endpoint.')
 add(32,'ACP-800','2E_symmetric',2000,100,5595,1,segments=[5566,5589,5595],extra={'electrolyte':'KOH','concentration_mol_L':6,'cycle_voltage_lower_V':0,'cycle_voltage_upper_V':.9,'BET_m2_g':2333},note='Cycle-specific0–.9V differs from generalGCDmethod0–1V; useexplicitcyclingparagraph, retainboth.')
 for sample,ret in [('TFS-AC (KOH)',98.2),('TFS-AC',95.4)]:add(34,sample,'2E_symmetric',10000,ret,4963,5,'approx',segments=[4963,6995])
 add(35,'EC-400','3E',10000,91.4,4015,segments=[3971,4010,4015],extra={'electrolyte':'H2SO4','concentration_mol_L':1},note='91.4explicitreported; matches8.6%loss. Cyclecurrentnotinferredfromrateprofiles.')
 add(35,'EC-10%','3E',10000,89.8,4010,relation='derived_complement',segments=[3971,4010],extra={'electrolyte':'H2SO4','concentration_mol_L':1},note='100−10.2%loss; derived relation, never exactreported.')
 add(36,'LCF-AW','2E_symmetric',10000,117,5727,10,'approx',note='About117afteractivation; above100retained. CE99.9%notlabel.')
 add(37,'NaOH-activated bamboo carbon','3E',5000,94,1448,segments=[1434,1435,1446,1448],extra={'electrolyte':'KOH','concentration_mol_L':6},note='Actualcyclecurrentunknown; standardGCDcurrentsnotinherited.')
 add(38,'AC800','3E',1000,98.67,4987,2,'derived_complement',segments=[4987,7088],extra={'electrolyte':'H2SO4','concentration_mol_L':1},note='100−1.33loss; initial89.93→88.73F/g ratio not silently substituted.')
 for sample,molar,ret,seg in [('CEPAC 1:1',3,96.6,5894),('CEPAC 1:1',6,97.8,5894),('CEPAC 1:0.5',3,93.2,5896),('CEPAC 1:0.5',6,96,5896)]:
  add(46,sample,'3E',3000,ret,seg,segments=[5892,5894,5895,5896],extra={'electrolyte':'KOH','concentration_mol_L':molar},note='Fig6c/f samplebindingverified.1A/gcapacitancetestnotautomaticallycyclingcurrent.')
 add(46,'CEPAC 1:1','2E_symmetric',10000,98.4,5898,segments=[5898],note='Ownassembleddevice; electrolyte/cyclecurrentstillneedmethod/figurebinding.')
 add(60,'Barro seed activated carbon','2E_symmetric',10000,98.2,5873,10,segments=[5857,5872,5873,5875],extra={'electrolyte':'H2SO4','concentration_mol_L':1},note='SamplelabelSSCdenotesdevice; exactcarbonprocessingaliasneedsreview.')
 add(65,'APE-2','2E_symmetric',20000,99.7,5503,segments=[5502,5503],note='1A/gisratecapacitancecontext; no cyclecurrentassignment. ParsedconcentrationMmissingnumber.')
 add(74,'PAC-700','2E_symmetric',10000,99.1,5462,1,'approx',segments=[5462,7121],extra={'electrolyte':'KOH','concentration_mol_L':6},note='SAC600/700conflictkeptseparate; PACmaterialbindingonly.')
 add(77,'BBC-800-0','2E_symmetric',7000,100,1460,10,segments=[1451,1454,1460,1461],extra={'electrolyte':'KOH','concentration_mol_L':6},note='Preprintpublicationidentity/yearunresolved. Energy/powerunitsnotimported.')
 fields={r['field_name']:r['unit'] for r in c.execute('select field_name,unit from field_observations group by field_name')}
 def select(ep,field,val,segids,status='own_primary_bound_candidate',reason='New own-paper candidate, not scientific admission.'):
  ss=[c.execute('select * from source_segments where segment_id=?',(s,)).fetchone() for s in segids];s=ss[0]
  old=c.execute('select observation_id from field_selection where endpoint_id=? and field_name=?',(ep,field)).fetchone()
  z=c.execute('insert into field_observations(endpoint_id,field_name,value_json,unit,status,source_id,segment_id,locator,evidence_excerpt,provenance_json) values (?,?,?,?,?,?,?,?,?,?)',(ep,field,enc(val),fields.get(field),status,s['source_id'],s['segment_id'],s['locator'],s['text'] if val is not None else '',enc({'reviewed_evidence_segments':segids,'note':reason})))
  oid=z.lastrowid;c.execute('insert or replace into field_selection values (?,?,?)',(ep,field,oid));c.execute('insert into field_selection_history(endpoint_id,field_name,old_observation_id,new_observation_id,reason) values (?,?,?,?,?)',(ep,field,old[0] if old else None,oid,reason))
 def year(ident):
  for x in c.execute('select source_json from literature_observations where identity_key=?',(ident,)):
   d=json.loads(x[0]);y=d.get('year')
   if isinstance(y,int):return y,'inherited_bibliography_not_new_publication_review'
  for s in c.execute("select source_id from paper_documents where identity_key=? and role='main'",(ident,)):
   for p, in c.execute("select path from document_locations where source_id=? and path like '%.xml'",(s[0],)):
    p=Path(p);p=p if p.is_absolute() else R/p
    root=ET.parse(p).getroot();ys=[int(e.text) for e in root.findall('.//article-meta/pub-date/year') if e.text and e.text.isdigit()]
    if ys:return min(ys),'own_XML_article_meta_pub_date'
  return None,'publication_year_unlocated'
 log=[]
 for n,x in enumerate(cases,1):
  identity=q[x['i']]['identity_key'];ep='candidate:V05:'+f'{n:03}';mid='material:'+key(identity,re.sub(r'\W+','',x['sample'].casefold()))
  tid='test:'+key(mid,x['system'],x['method'],x['values'].get('reported_current_A_g'),x['values'].get('electrolyte'),x['values'].get('concentration_mol_L'))
  c.execute('insert or ignore into model_materials values (?,?,?,?,NULL)',(mid,identity,x['sample'],'own_sample_candidate_identity_not_independence_clearance'))
  c.execute('insert or ignore into model_tests values (?,?,?,?,?,?,NULL)',(tid,mid,x['system'],x['method'],tid,'own_label_bound_protocol_pending'))
  gid=c.execute('select group_id from unified_source_groups where identity_key=?',(identity,)).fetchone()[0];y,yb=year(identity)
  c.execute('insert into model_endpoints values (?,?,?,?,?,?,?,?,?,NULL)',(ep,identity,mid,tid,'capacitance_retention',gid,y,yb,'own_label_candidate_not_admitted'))
  c.execute('insert into endpoint_aliases values (?,?,?)',('V05',f'V05_{n:03}',ep))
  for s in x['evidence_segments']:
   assert c.execute('select 1 from source_segments s join paper_documents p using(source_id) where s.segment_id=? and p.identity_key=?',(s,identity)).fetchone(),(n,s)
  for field in fields:
   v=x['values'].get(field)
   select(ep,field,v,[x['segment']]+[s for s in x['evidence_segments'] if s!=x['segment']],status='own_primary_bound_candidate' if v is not None else 'not_located_by_bounded_review',reason=x['note'] or 'Own-label extraction only; conditions and admission remain pending.')
  # Field-specific evidence avoids attaching a BET number to a cycling-only passage.
  if x['i']==4:select(ep,'BET_m2_g',553,[6020])
  if x['i']==6:select(ep,'BET_m2_g',610.248,[5850])
  for profile in ['canonical_2e','canonical_3e']:c.execute('insert into admission_reviews values (?,?,?,?)',(ep,profile,'pending','Own numeric label bound; current mass basis, cycle baseline, applicability, grouping and full field audit not cleared.'))
  if x['i']==8:
   for value,seg in [(12,5746),(20,5761)]:
    ss=c.execute('select * from source_segments where segment_id=?',(seg,)).fetchone();c.execute('insert into field_observations(endpoint_id,field_name,value_json,unit,status,source_id,segment_id,locator,evidence_excerpt,provenance_json) values (?,?,?,?,?,?,?,?,?,?)',(ep,'reported_current_A_g',enc(value),'A/g','conflicting_primary_report_not_selected',ss['source_id'],seg,ss['locator'],ss['text'],enc({'conflict':'highlights12vsbody20'})))
   c.execute('insert into extraction_issues(endpoint_id,identity_key,field_name,code,status,evidence_json,reason) values (?,?,?,?,?,?,?)',(ep,identity,'reported_current_A_g','primary_cycle_current_12_vs_20','open',enc({'segments':[5746,5761],'values_A_g':[12,20]}),'Keep both primary values; canonical reported currentNULL until resolved.'))
  log.append({'alias':f'V05_{n:03}','endpoint_id':ep,'identity_key':identity,**x})
 c.execute('insert into extraction_run values (?,?)',('v05_own_endpoint_append',enc({'count':len(cases),'admitted':0})));c.commit();c.close()
 (O/'逐篇新增端点与字段证据.json').write_text(json.dumps(log,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(enc({'new_own_endpoints':len(cases),'new_approvals':0}))
if __name__=='__main__':main()
