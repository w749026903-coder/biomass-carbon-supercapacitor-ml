"""Append bounded own-source reviews to a new v0.5 copy. Never changes v0.4 or fits."""
from pathlib import Path
import hashlib,json,re,sqlite3,xml.etree.ElementTree as ET
R=Path(__file__).resolve().parents[1]
O=R/'循环稳定性数据库_v0.5_逐条准入审查_20261018'
def enc(x):return json.dumps(x,ensure_ascii=False)
def key(*xs):return hashlib.sha256(enc(xs).encode()).hexdigest()[:24]

# Human adjudication of the 81-paper native-text queue. These are bounded
# dispositions, not claims that every figure/SI/protocol has final clearance.
NOTES={
0:('side_domain','Zn-ion hybrid capacity/CE, not target EDLC capacitance retention; 2% is CNT loading and 99.1% is CE.'),
1:('own_numeric_pending_protocol','Own C1000G0.2 electrode95%/10000; symmetric device98%/10000/2A/g. Native74% pair was rate retention. BET abstract cm2/g versus Table1 m2/g conflicts. SSP-900 is inherited precursor; do not assume independent prior work.'),
2:('qualitative_or_graph','86% is rate retention at10A/g, near100% is CE. Own cycling curve/absolute384→360F/g needs baseline binding; do not invent a reported93.75% label.'),
3:('side_domain','Zinc-ion hybrid. 98%/15000 in native pair is a cited Chen result, not own original experiment.'),
4:('own_numeric_pending_protocol','Own symmetric RPPAC-.25-850,6000GCD/10A/g/88%. Conclusion about88%; retain approximate relation.'),
5:('qualitative_or_graph','Native4000/20000+92.51% pairs are comparative table references. Own C:K:M5000 cycles described without apparent degradation; requires figure review.'),
6:('own_numeric_pending_protocol','Own AC symmetric device76.5%/10000; 3E characterization distinct. Current still needs cycle-specific binding.'),
7:('side_domain','Phenol/formaldehyde synthetic resin, own methods p2; not biomass-derived main scope. Own95.76%/10000 and105.75%/50000 remain side-domain evidence; do not clip >100.'),
8:('own_conflict','RH900 three-electrode98%/96% discrepancy retained; symmetric device95.23%/10000 is separate. Cited500cycles/63% not own.'),
9:('review_background','Front explicitly REVIEW; abstract says systematic review. Previous original-experiment classification corrected only in this new review layer; preserve original registry.'),
10:('own_numeric_pending_protocol','AC-N80.1%/10000 at1A/g belongs2E symmetric Fig5h, not3E Fig5a–d.'),
11:('side_domain','Methods p2 use commercial KurarayYP50F; biomass origin not established. Own electrolyte comparison80/77% at10000 and82/84% at20000 separate;17m is mol/kg, not mol/L. Native27.8% is energy improvement.'),
12:('own_conflict','Own5000/87.62% prose says capacitance but Fig9d caption says Coulombic efficiency; freeze metric until graph checked.10000/90% in introduction is secondary.'),
13:('side_domain','ME-rGO/TiO2 nanocomposite and sensor; no biomass precursor established. Own94.2%/5000 retained as side-domain, sensing50CV cycles separate.'),
14:('side_domain','Own resorcinol–hexamethylenetetramine synthetic resin, not biomass precursor. PC-Mn95.6%/10000 is side-domain candidate.'),
15:('own_numeric_pending_protocol','N3OPC-3:3E93.5%/10000 at200mV/s is CV, not GCD. Device89%/10000 at20A/g separate.63.7%/20000 is cited work.'),
16:('side_domain','MOF(Ni)@RGO//BC gel hybrid0–2.2V separated from biomass carbon EDLC main scope.85.2%/4000 own device;5% is RGO composition.83.97/45.81% material assignment/text explanation inconsistent; freeze.'),
17:('side_domain','Al-MOF carbon synthetic precursor; C/g capacity terminology mixed with capacitance, 3E positive/negative and3devices separate. No main-scope admission.'),
18:('own_numeric_pending_protocol','Marine glycogen carbon DES half-cell and SSE@DES symmetric prototype separated. Prototype75%/1000 at1A/g own. Native97%/2000 and100%/1000 passages contain comparisons; source Table3 multiple temperatures/times/uncertainties need full binding.'),
19:('own_numeric_pending_protocol','Own4QSC electrodes93.6/94.8/97.8/95.5% after10000 at5A/g. Device QSC3 two electrolytes97.55/96.2% separate; same paper source group.'),
20:('qualitative_or_graph','TAK5 close to100%/7000 is qualitative, not exact100. Preserve wording; figure needed.'),
21:('own_numeric_pending_protocol','LCNF82.8% Kraft pine/spruce and95.5% organosolv beech at10000; CE>98% distinct.12mol/kgNaNO3 device54% vs6MKOH89%; cited90%/9000 separate. Need sample/electrolyte/test bindings.'),
22:('own_numeric_pending_protocol','Own symmetric NSGP//NSGP99.46%/5000/5A/g in1MH2SO4, not three-electrode cycling.'),
23:('own_conflict','Honey abstract>96.7%/10000 versus introduction96.7%/15000; relation andhorizon not interchangeable. Rate78.2% distinct. Requires own results/graph adjudication.'),
24:('own_numeric_pending_protocol','Own PPC-500-1-1h symmetric99.3%/20000/10A/g,6MKOH.70.5% is rate retention.'),
25:('own_numeric_pending_protocol','Own HPC-P8 symmetric93.8%/5000/10A/g in1MNa2SO4; BET640m2/g abstract. Two-electrode identity explicit.'),
26:('qualitative_or_graph','BC800/900/1000 PVDF approximately93%; chitosan up to95%/10000. Do not assign a group maximum as exact per-sample label.'),
27:('own_conflict','ESC-G151→117F/g/5000 differs from stated89%; do not select by high/low performance. Both original values retained for graph/baseline review.'),
28:('own_numeric_pending_protocol','Own NSOC8003E90.1%/5000/1A/g,6MKOH; device lifecycle separate.'),
29:('own_conflict','PSAC10body90%/15000 versus conclusionaround93%; CE97% separate. Freeze label, not latest-write wins.'),
30:('own_conflict','WHAC100body99.45% then99.40%/7000; conclusionapprox99. WHAC50/15085.39/76.87; WHAC67.03% at3000. Baseline horizons and small discrepancy require graph review.'),
31:('own_numeric_pending_protocol','SNPB8004body94.14%/10000/10A/g in3E discussion, conclusion5%loss is rounded; preserve primary value and secondary rounded observation, device separate.'),
32:('own_numeric_pending_protocol','ACP800own conclusion100%/2000;1A/g and0–.9V cycle-specific. Cell configuration must be bound from own methods; native97%/1000 is cited,84.3/93.7% rate.'),
33:('own_conflict','ABPC4abstract andconclusion95.08%(loss4.92%) at10000/10A/g but bodyFigure8c3Eclaims100%. Scope3E/device inconsistent; freeze both, do not choose.'),
34:('own_numeric_pending_protocol','Own symmetric TFS-AC(KOH)approximately98.2% andTFS-ACaround95.4%/10000; approximate relations retained.'),
35:('own_numeric_pending_protocol','Own EC40091.4%/10000 exact stated conclusion; EC10%10.2%loss only derived complement89.8, keep separate.'),
36:('own_numeric_pending_protocol','Own LCF-AW symmetric about117%/10000/10A/g after activation; CE99.9% separate, do not clip above100.'),
37:('own_numeric_pending_protocol','Own bamboo94%/5000; not84.6/10000 or97.47/10000 cited comparisons. Actual cycle current needs binding.'),
38:('own_numeric_pending_protocol','AC8003E1.33%loss at1000/2A/g, derived98.67% only;2E3000/1A/g separate Fig7. Do not convert loss to reported exact retention.'),
39:('preprint_or_identity_pending','Birch BWC4materials60000cycles:loss.2/.66/2.75/1.25%, Kuraray.17%control. Source states preprint; identity/pubyear/baseline peaks vary5000–49000. No exact reported retention conversion.'),
40:('preprint_or_identity_pending','BLPC SCup to93%/8000 own abstract; sodium-ion battery310mAh/g separate. Bound qualifier, sample and bibliographic identity before records.'),
41:('preprint_or_identity_pending','Registry title is historical year-exclusion label, not actual paper title. CSCK8002symmetric99.7%/10000/5A/g own abstract, but publication/year identity must be resolved first.'),
42:('side_domain','T0.15PVA-NaOH/TiO2gel approximately100%/5000/10A/g;79.25%rate. Gel andpreprint not main ordinary-aqueous cohort.'),
43:('side_domain','MnO2/heating-element/tobacco asymmetric device81.8%/3000/1A/g; keep hybrid/metal composite separate from main carbon EDLC.'),
44:('side_domain','Biographite anode/NMC622 battery capacity after150cycles, not supercapacitor capacitance target.'),
45:('side_domain','Moisture-induced electricity generation review; not own supercapacitor retention experiment.'),
46:('own_numeric_pending_protocol','CEPAC1:1own3E3000:96.6%in3MKOH,97.8%in6M; lower activation sample93.2/96%must bind independently. Symmetricdevice98.4%/10000 separate, no inferred current.'),
47:('no_numeric_label_located','Native text cycle keyword read did not locate own long-cycle numerical retention. Does not establish no data in images/SI.'),
48:('no_numeric_label_located','CO2-activated nanofiber carbon native text no own numeric lifecycle label located. Need inspect graphical/SI stability rather than infer.'),
49:('no_numeric_label_located','Corn straw activation native text no own numerical cyclic retention located; life-cycle inventory is environmental LCA, not electrochemical cycles.'),
50:('side_domain','Injectable alginate hydrogel hemostasis; wet-surface retention not capacitance retention.'),
51:('qualitative_or_graph','Lignin composites cycling behavior mentioned but native exact retention/horizon unresolved; graph/first-cycle normalization required.'),
52:('no_numeric_label_located','Chemical surface modification carbon: own numeric long-cycle retention not located in native text. Image/SI review remains.'),
53:('qualitative_or_graph','Coconut hard-carbon rate retention mentioned; no own numerical long-cycle pair established from native text.'),
54:('side_domain','Coconut carbon OER/HER electrocatalyst, not target supercapacitor experiment.'),
55:('side_domain','Activated carbon hydrovoltaic evaporation generator; not target electrochemical retention.'),
56:('side_domain','PFAS adsorption efficiency31–98% not capacitance retention.'),
57:('side_domain','Coal-derived zinc-ion hybrid capacity~97.5%; coal andZn-hybrid both outside biomass EDLC main scope.'),
58:('side_domain','FeNS carbon zinc-air battery catalyst;3075cycles battery durability, not capacitance target.'),
59:('side_domain','Recovery of solid-state sodium battery cathode/electrolyte, not supercapacitor endpoint.'),
60:('own_numeric_pending_protocol','BarroSSC98.2%/10000/10A/g own symmetric cell; rate41.2% at50A/g distinct. Word wrapping prevented automatic pair.'),
61:('side_domain','CovalentBBD-MoS2 own76%/10000 non-biomass inorganic electrode; not main scope.'),
62:('own_conflict','F-ACNFdevicebody96.85% vsconclusion96.48%/10000, sample spellingF-ANFC also occurs. Preserve both; no current assignment from rate test.'),
63:('own_conflict','PurplecornAC10%50000:prose efficiency76% whereas figure captioncapacitance; curve/metric baseline binding required.2500cycles35%increase separate.'),
64:('qualitative_or_graph','AC-MNS3coin-cell10000cycles/3A/g minimal change only;77% at20A/g is rate. Need curve-derived estimate with uncertainty, not exactreported100.'),
65:('own_numeric_pending_protocol','APE2symmetric99.7%/20000 own conclusion/body.1A/g nearby is specific-capacitance test, not automatically cycle current; electrolyte M concentration missing in parsed text.'),
66:('side_domain','Pesticide adsorption/regeneration, not target capacitance retention.'),
67:('side_domain','MXene/polyaniline non-biomass composite; owncycledata separate side-domain.'),
68:('no_numeric_label_located','Slag-activated biomass main native text has generalcyclelife only; no own numerical lifecycle endpoint located. Image/SI review remains.'),
69:('qualitative_or_graph','Banana/silica stability assessed by CV; native exact retention+N not located, do not assign GCD.'),
70:('qualitative_or_graph','MK9device100000GCD at2A/g reported but retention curves without explicit exact terminal percentage in examined native text; CE100% not retention.'),
71:('qualitative_or_graph','HTWB.5.9003E10000/10A/g no discernible loss; qualitative wording, not exact100. Preprint remains separate.'),
72:('side_domain','Bamboo charcoal microbial fuel cell electrode optimization, not supercapacitor retention.'),
73:('qualitative_or_graph','Orangejuice prototypes5000cycles/1A/g/0–1V; decline/maintenance qualitative; curve normalization and sample color mismatch red/blue need review.'),
74:('own_conflict','PAC700symmetricapprox99.1%/10000/1A/g; SACbody600approx93.4%butFig9captionSAC700. Freeze SAC binding; do not merge samples.'),
75:('side_domain','Industrial dye adsorption retention, not capacitance target.'),
76:('short_test','CyperusPVA/Na2SO4gel lifecycle ends400cycles at50A/g;20cycleactivation154→168F/g; failsN>=1000 andordinaryaqueousmain scope.'),
77:('own_numeric_pending_protocol','BBC8000symmetric100%/7000/10A/g ownp10; preprint identity/year unresolved. Conclusion swapsenergy/powerunits, do not transfer those values.'),
78:('side_domain','Decoupled water electrolysis binder-free carbon60cycles, not target retention.'),
79:('no_numeric_label_located','Indonesian vegetable-waste electrode native text no numerical long-cycle label located. Language/image review remains.'),
80:('short_test','Date-palm-pollen CDI paper also electrochemical100GCDcycles3A/g,~96–98%range. Fails1000cycles. Desalting40/50cycles comparisons are different metrics.')}

def main():
 c=sqlite3.connect(O/'cycling_v0_5.sqlite');c.row_factory=sqlite3.Row;c.execute('pragma foreign_keys=ON')
 if c.execute("select count(*) from extraction_run where key='v05_bounded_review_complete'").fetchone()[0]:raise RuntimeError('Already applied')
 c.executescript('''
 CREATE TABLE paper_source_reviews(identity_key TEXT PRIMARY KEY REFERENCES literature_registry,review_scope TEXT NOT NULL,disposition TEXT NOT NULL,reason TEXT NOT NULL,source_id TEXT REFERENCES document_sources,evidence_segment_ids_json TEXT NOT NULL,remaining_work TEXT NOT NULL);
 CREATE TABLE native_claim_adjudications(claim_id INTEGER PRIMARY KEY REFERENCES native_measurement_claims,decision TEXT NOT NULL,reason TEXT NOT NULL,evidence_segment_id INTEGER REFERENCES source_segments,eligible INTEGER NOT NULL CHECK(eligible=0));
 CREATE TABLE bibliography_reviews(review_id INTEGER PRIMARY KEY,identity_key TEXT REFERENCES literature_registry,publication_year INTEGER,date_type TEXT,source_id TEXT REFERENCES document_sources,segment_id INTEGER REFERENCES source_segments,locator TEXT,excerpt TEXT,decision TEXT);
 CREATE TABLE endpoint_metadata_changes(change_id INTEGER PRIMARY KEY,endpoint_id TEXT REFERENCES model_endpoints,field_name TEXT,old_value_json TEXT,new_value_json TEXT,reason TEXT,evidence_json TEXT);
 CREATE TABLE review_search_audit(search_id INTEGER PRIMARY KEY,scope TEXT,expression TEXT,result_count INTEGER,interpretation TEXT);
 '''.replace('CREATE TABLE ','CREATE TABLE IF NOT EXISTS '))
 queue=json.loads((O/'尚无结构记录_81篇审查队列.json').read_text(encoding='utf-8'))
 assert len(queue)==len(NOTES)==81
 for i,x in enumerate(queue):
  disposition,reason=NOTES[i];segs=c.execute('select * from source_segments where source_id=?',(x['main_source_id'],)).fetchall()
  ev=[s['segment_id'] for s in segs if re.search(r'cycl|retention|durab|stabil|\bREVIEW\b|ABSTRACT',s['text'],re.I)]
  if not ev:ev=[s['segment_id'] for s in segs[:1]]
  remaining='Primary-source field/figure/SI and record-level admission review remains; this disposition never grants training eligibility.'
  if disposition in ('side_domain','review_background','short_test'):remaining='Retain for side/background uses; cannot pass the current main-cohort scope/horizon by filling unknown fields.'
  c.execute('insert into paper_source_reviews values (?,?,?,?,?,?,?)',(x['identity_key'],'bounded_native_text_own_vs_secondary_and_metric_review',disposition,reason,x['main_source_id'],enc(ev),remaining))
  for n in c.execute('select * from native_measurement_claims where identity_key=?',(x['identity_key'],)).fetchall():
   decision={'side_domain':'out_of_main_scope','review_background':'secondary_review_not_own_experiment','own_conflict':'conflict_or_metric_binding_requires_review','own_numeric_pending_protocol':'own_passage_reviewed_pair_not_automatically_valid','qualitative_or_graph':'pair_not_exact_original_cycle_label','preprint_or_identity_pending':'identity_or_relation_pending'}.get(disposition,'not_admitted')
   c.execute('insert into native_claim_adjudications values (?,?,?,?,0)',(n['claim_id'],decision,reason,n['segment_id']))
 # Specific false pair decisions supersede only this new adjudication table,
 # never delete or rewrite the original isolated automatic candidate.
 overrides={314:'rejected_composition_percent',315:'rejected_coulombic_efficiency',291:'rejected_rate_retention_pair',440:'rejected_rate_retention_pair',491:'rejected_secondary_citation',448:'rejected_comparative_table',449:'rejected_comparative_table',465:'rejected_secondary_citation',321:'rejected_review_comparison',322:'rejected_review_comparison',316:'rejected_energy_improvement_percent',301:'rejected_secondary_citation',474:'rejected_secondary_citation',340:'conflicting_sample_assignment',341:'conflicting_sample_assignment',343:'rejected_composition_percent',411:'rejected_secondary_citation',413:'loss_complement_not_reported_retention',439:'own_numeric_label_candidate_not_admitted',486:'horizon_and_inequality_conflict',487:'horizon_and_inequality_conflict',488:'rejected_rate_retention_pair',489:'horizon_and_inequality_conflict',490:'horizon_and_inequality_conflict'}
 for cid,decision in overrides.items():
  assert c.execute('select 1 from native_claim_adjudications where claim_id=?',(cid,)).fetchone(),cid
  c.execute('update native_claim_adjudications set decision=? where claim_id=?',(decision,cid))
 # Own-publication metadata, not DOI substrings or receipt dates.
 for aliases,year,needle,date_type in [(['TE026'],2023,'Energy Technol.','issue_year'),(['TE028'],2026,'ChemistrySelect','issue_year'),(['TE029','TE030'],2023,'December','first_online_year')]:
  ep=c.execute("select endpoint_id from endpoint_aliases where namespace='TE' and alias=?",(aliases[0],)).fetchone()[0]
  identity=c.execute('select identity_key from model_endpoints where endpoint_id=?',(ep,)).fetchone()[0]
  segs=c.execute("select s.* from source_segments s join paper_documents d using(source_id) where d.identity_key=? and d.role='main' and s.locator='PDF p1'",(identity,)).fetchall()
  s=next(s for s in segs if needle.lower() in s['text'].lower() and str(year) in s['text'])
  c.execute('insert into bibliography_reviews(identity_key,publication_year,date_type,source_id,segment_id,locator,excerpt,decision) values (?,?,?,?,?,?,?,?)',(identity,year,date_type,s['source_id'],s['segment_id'],s['locator'],s['text'],'Publication line verified; received/accepted andDOIyears are not substituted.'))
  for alias in aliases:
   ep=c.execute("select endpoint_id from endpoint_aliases where namespace='TE' and alias=?",(alias,)).fetchone()[0];old=c.execute('select source_year,year_basis from model_endpoints where endpoint_id=?',(ep,)).fetchone()
   c.execute('insert into endpoint_metadata_changes(endpoint_id,field_name,old_value_json,new_value_json,reason,evidence_json) values (?,?,?,?,?,?)',(ep,'publication_metadata',enc(dict(old)),enc({'source_year':year,'year_basis':date_type}),'Own publication line; no guessed year',enc({'source_id':s['source_id'],'segment_id':s['segment_id']})))
   c.execute('update model_endpoints set source_year=?,year_basis=? where endpoint_id=?',(year,'own_primary_publication_line:'+date_type,ep))
 # AF-MMTC SI only containsS1–S6 spectra/CV/GCD/Ragone figures: no SSA table.
 afsid=c.execute("select source_id from document_locations where path like '%RA-015-D4RA08818B-s001.pdf'").fetchone()[0]
 c.execute('insert into review_search_audit(scope,expression,result_count,interpretation) values (?,?,?,?)',(afsid,'Entire3-page own SI reviewed for sample-specific BET/table',0,'No BET table located in this SI; do not assign AF-MMTC5 property to six samples. Main fulltext/figures remain a separate source.'))
 c.execute('insert into extraction_run values (?,?)',('v05_bounded_review_complete','true'));c.commit();c.close()
 print('81paper dispositions, isolated claim adjudications,4publication-year metadata changes appended.')
if __name__=='__main__':main()
