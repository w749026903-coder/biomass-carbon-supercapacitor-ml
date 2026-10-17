"""Human-reviewed extraction instructions. Counts are endpoints, never independent-paper counts."""
from pathlib import Path
import json
OUT=Path(__file__).resolve().parent
rows=[]
def add(tag,sample,n,ret,current,el,conc,loc,rel='eq',note='',kind='reported',loss=None):
 rows.append({'source_tag':tag,'sample':sample,'cycle_count':n,'retention_pct':ret,'retention_relation':rel,'reported_current_A_g':current,'electrolyte':el,'concentration_mol_L':conc,'locator':loc,'review_note':note,'value_kind':kind,'reported_loss_pct':loss,'system':'3E','cycle_method':'GCD','training_admitted':False,'material_identity_finalized':False,'current_mass_denominator_finalized':False})
# Existing database: six carbon records; all legacy holds remain unchanged.
add('B_R013','EUAC1-60',10000,89.9,1,'KOH',1,'PDF p7; Figure6i/Table comparison; three-electrode method','eq','Coulombic efficiency 117.21% is separately reported, never used as retention.')
add('B_R042','CGBC',1000,64.8,1,'KOH',1,'PDF p1,p8 and methods; pure coffee-carbon control','eq','Ni(OH)2 composite retained separately; not included in this carbon endpoint.')
add('B_R078','C/600C',8000,98.1,5,'KOH',6,'PDF p1 abstract and Fig6b; methods','eq','Body says >98%, compatible with the abstract point; keep original wording and unresolved protocol metadata.')
add('B_R087','OAC623',1000,85.5,0.1,'NaOH',2,'PDF p1,p9 and Fig12; methods')
add('B_SRC025','AC3',10000,91,20,'KOH',6,'PDF p9 Figure6d; three-electrode method','eq','93% is coulombic efficiency, not retention.')
add('B_SRC121','DSAC',2000,83.3,10,'KOH',1,'PDF p7 Figure6a and electrode methods','eq','3 M KOH test is a different experiment; physical-current normalization and voltage reference remain under review.')
# Previously obtained original XML, now extracted as actual three-electrode records.
add('EXT_001','AHPC-850',10000,96.3,10,'KOH',6,'P0055/three-electrode method/Fig4d')
add('EXT_002','FWCA-4',10000,94.1,None,'KOH',6,'P0019/Fig7c; methods','eq','Cycle current not borrowed from separate capacitance tests.')
add('EXT_003','YPAC-1',10000,82.26,None,'KOH',6,'P0011-P0012/Fig6d','eq','Paper calls the working electrode a device in prose; paired with explicit three-electrode methods; cycling current remains unlocated.')
add('EXT_005','FRPCK-Urea',5000,96.43,20,'KOH',6,'P0009,P0039/Fig4f')
add('EXT_008','AHC-CL-TU',20000,99.96,10,'KOH',6,'P0015,P0033/Fig7c')
add('EXT_011','FPC',1000,98.4,3,'KOH',6,'P0021,P0056/Fig6','approx','Author explicitly says approximately; preserve approximate relation.')
add('EXT_013','CMC-ZnK-800',5000,94.3,10,'KOH',6,'P0006,P0031/Fig8d')
for sample,ret in [('AF-MMTC0',98.8),('AF-MMTC1',97.0),('AF-MMTC3',96.9),('AF-MMTC5',98.5),('AF-MMTC7',98.0),('AF-MMTC9',97.9)]:
 add('EXT_014',sample,5000,ret,10,'KOH',6,'P0009,P0019/Fig4e','eq','Six distinct preparations in one paper; same study_group; the two-electrode Fig5e values are not used.')
add('EXT_015','AO-PC',10000,97,5,'H2SO4',1,'P0026-P0028/Fig7a; repeated GCD caption')
# User-provided papers; same-paper tests remain grouped.
for sample,ret in [('OPBNP',93.6),('OPB',88.8),('OPNP',83.5),('OPC',76.7)]:add('U002',sample,10000,ret,5,'KOH',6,'PDF p7,p16-p17/Fig3f','eq','Accepted Manuscript; sodium-ion battery cycles and Fig4 device cycles are excluded.')
add('U013','SSC2-0.6',2000,93.18,5,'KOH',6,'PDF p8/Fig5f; three-electrode methods')
add('U016','KAC-5',10000,90.31,None,'KOH',6,'PDF p7 Fig4f/p8 methods','eq','88.83% belongs to two-electrode device; cycle current remains unlocated.')
add('U018','LC/rGO',10000,97,5,'KOH',6,'PDF p1-p3 and Fig3/three-electrode section','eq','Lignosulfonate/rGO carbon-carbon composite; exact recipe and independence not yet finalized.')
add('U021','ACA-US',2000,85,10,'KOH',3,'PDF p1,p10 Fig10d; three-electrode methods','approx','Author approximately 85%; not a precise 85.000% label.')
add('U024','ALPC-800',2000,100,10,'H2SO4',0.5,'PDF p10/Fig8c,three-electrode acid paragraph','eq','Neutral-electrolyte test below is separate; device91%/6000 cycles not included.')
add('U024','ALPC-800',2000,100,10,'Na2SO4',0.5,'PDF p10/Fig8c,three-electrode neutral paragraph')
# Newly retrieved public research.
add('PMC12794195','MHDHPC-600',20000,100,20,'KOH',6,'P0017,P0019/Fig4f','eq','Device performance is in a later Fig5 section.')
add('PMC12175059','NAPC-650-4',10000,87.65,10,'KOH',6,'Three-electrode section and cycling figure; conclusion P0040','eq','Mixed diaper-derived precursor; preserve mixed-feedstock flag; not finalized for a pure-biomass training scope.')
add('PMC10056672','WET-1',5000,94.4,5,'KOH',6,'P0014,P0053/Fig8')
add('PMC10056672','DRY-1',5000,97.8,5,'KOH',6,'P0014,P0053/Fig8')
add('PMC10759806','CA-AA',5000,102,1,'H2SO4',1,'P0012,P0037-P0040/Fig7a','eq','Only explicitly reported CA-AA endpoint is counted; other curves are not assigned invented numeric values.')
for sample,loss in [('AC-500C',9.7),('AC-600C',23.6),('AC-700C',40.8)]:
 add('PMC10869866',sample,1000,round(100-loss,1),3,'KOH',6,'P0035,P0118-P0121/Fig10a','eq','Author reports percentage loss, retention calculated transparently as 100-loss. Conflicting AC-400C values are excluded.','loss_complement',loss)
add('PMC13400085','AC_rice_straw',10000,83.54,5,'H2SO4',1,'P0029,P0041/Fig7C-E','eq','Pure rice-straw carbon control only; ZnO and AC-ZnO composite not counted; cycle current 5 A/g explicitly in Fig7 caption.')
add('PMC9738515','MGCs-2',10000,96,5,'KOH',6,'P0007,P0029-P0034/three-electrode cycling','eq','Symmetric device section follows the three-electrode comparison; Cycling current 5 A/g explicitly in Fig5f and P0029.')
add('PMC9033565','LLC',5000,96.5,None,'KOH',6,'P0008,P0020-P0021/Fig5f','eq','Cycling current is 1 mA/cm2; preserve areal unit; do not convert to A/g.')
add('PMC6843703','WW-KOH9',5000,94,5,'KOH',6,'P0029/Fig7d; methods P0039','approx')
add('PMC8838214','TCZn-800',3000,94.83,None,'KOH',6,'P0017,P0020/Fig7','approx','Author says about; unknown cycling current is kept null.')
add('PMC8912637','SD-AC',10000,87.03,10,'KOH',6,'P0030-P0031/Fig6e; three-electrode caption','eq','Two-electrode Fig7e about80% is separate.')
add('PMC8585355','BTC-613',2000,98.8,5,'H2SO4',1,'Abstract/P0003,P0017,P0022/Fig9c','eq','Use abstract explicitly stating capacitance; body calls loss energy loss, kept in note.')
add('PMC8707477','LTSC_K900',10000,99.7,50,'H2SO4',1,'P0033-P0040; three-electrode GCD stability figure','eq','Derived only as 100 minus reported0.3% loss; cycling current 50 A/g explicitly in Fig8a caption.','loss_complement',0.3)
add('PMC6401840','ECNFs-6',2000,88.8,1,'KOH',6,'P0010,Fig7c (1 A/g),conclusion P0022','eq','Lignin/PAN mixed-feedstock carbon fiber; binder-free; electrospinning composition preserved for later scope audit.')
add('PMC8705087','BSPC',5000,94,5,'KOH',1,'P0006,P0011-P0012/Fig4e','eq','Fig4e explicitly states 5000 GCD cycles, resolving body minimum5000 wording.')
add('PMC6648613','NSHPC2',10000,85.8,10,'KOH',6,'P0021-P0023/Fig6f','eq','Symmetric device is a separate later section.')
add('PMC9038012','ACST-2',5000,89.6,3,'KOH',6,'Three-electrode cycling section; conclusion P0036','eq','Two-electrode ACST-2//ACST-2 is a separate experiment.')
add('B_R085','NPCA-600-0.5',5000,80,10,'KOH',6,'Methods2.4 and Fig7i, before separate two-electrode Fig8 section','approx','Approximately80% in cycling paragraph;91%/10cycles belongs to CO2 adsorption and is not used.')
add('PMC12158216','SC-0.03',5000,93.7,10,'KOH',2,'P0004-P0007,P0018-P0019/Fig7','eq','Sodium alginate and nanocellulose carbon aerogel; phenol-formaldehyde is discussed only as prior art, not the synthesis here.')
add('PMC7770663','u-MPC',10000,100,10,'H2SO4',None,'P0009,P0011,P0039/Fig5e','approx','Author almost100%; acid concentration not borrowed from later1M device assembly. MPC-800 morethan100% is retained as bounded supplemental evidence, not another point endpoint.')
(OUT/'manual_endpoint_reviews.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8',newline='\n')
print('Human extracted candidate endpoints:',len(rows),'unique study tags:',len({x['source_tag'] for x in rows}))
