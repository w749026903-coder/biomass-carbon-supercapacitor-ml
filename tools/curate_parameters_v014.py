"""Explicit agent-reviewed recipes for all 30 main-cohort sources, not NLP guesses."""
from pathlib import Path
import copy,hashlib,json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from data.cycling_db import open_database
BATCH=ROOT/'主集参数精提取_20261022'

# Every numeric declaration below was read in the own-source methods during this batch.
# Control samples are deliberately handled separately from activated materials.
RECIPES={
'10.1007/s00339-023-07141-8':dict(locator='PDF p3 sections2.2-2.3',anchors=['673 K','623 K','24.8'],
 common=dict(activation_temperature_C=399.85,post_treatment_temperature_C=349.85,post_treatment_duration_h=4,post_treatment_heating_rate_C_min=10,activation_agent_v14='H3PO4',precursor_v14='apricot stones'),
 notes=['673 K converted to399.85 C;623 K oxidation converted to349.85 C. Oxidation ramp10 C/min is NOT activation ramp.','24.8±3 mg in Teflon tip is electrode mass; area not established, no mg/cm2.'],
 electrode=dict(active_mass_mg_v14=24.8,active_mass_uncertainty_mg_v14=3)),
'10.1016/j.jpcs.2023.111318':dict(locator='PDF p2 sections2.2/2.4',anchors=['800','2.4'],
 common=dict(precarbonization_temperature_C=600,precarbonization_duration_h=2,precarbonization_heating_rate_C_min=10,activation_temperature_C=800,activation_duration_h=2,heating_rate_C_min=10,activation_agent_v14='KOH',precursor_v14='reed residue waste'),
 electrode=dict(mass_loading_mg_cm2=2.4,loading_evidence_kind_v14='nominal active mass2.4mg divided by explicitly coated1x1cm2'),
 notes=['600 C is the first carbonization; all carbonized samples subsequently activated at800 C.']),
'10.1021/acs.energyfuels.4c01398':dict(locator='PDF p2-3 own synthesis and electrochemical measurements',anchors=['800','0.8','AC3'],
 common=dict(precarbonization_temperature_C=350,precarbonization_duration_h=1,activation_temperature_C=800,activation_duration_h=2,heating_rate_C_min=5,activation_agent_v14='KMnO4',precursor_v14='coconut tree husk'),
 electrode=dict(mass_loading_mg_cm2=0.8),notes=['AC3 specifically uses KMnO4; common800 C/2h/5 Cmin programme applies. No KOH identity borrowed from AC2.']),
'10.1021/acsomega.4c11529':dict(locator='PDF p2-3 section2.2 and electrochemistry',anchors=['900 W','60','8.0'],
 common=dict(activation_duration_h=1,activation_time_kind_v14='total microwave exposure; not an isothermal furnace hold',microwave_power_W_v14=900,activation_agent_v14='H3PO4',precursor_v14='Eucommia ulmoides wood'),
 notes=['Own60min microwave treatment; no actual thermal temperature or conventional ramp established.900W is power, not temperature.']),
'10.1039/d5ra08165c':dict(locator='XML experimental own MHDHPC-600 preparation',anchors=['600','5'],
 common=dict(activation_temperature_C=600,activation_duration_h=2,heating_rate_C_min=5,activation_agent_v14='KOH',precursor_v14='cotton pulp board'),
 electrode=dict(mass_loading_mg_cm2=1.5),electrode_si='循环稳定性文献补充_20261017/N002/RA-016-D5RA08165C-s001.pdf',
 notes=['Loading1.5mg/cm2 from SI p2 working-electrode procedure; not TGA10 Cmin ramp.']),
'10.3390/molecules28124633':dict(locator='PDF p9 section3.2 own RSM-y-550',anchors=['550','2 h','5'],
 common=dict(hydrothermal_temperature_C=120,hydrothermal_duration_h=2,activation_temperature_C=550,activation_duration_h=2,heating_rate_C_min=5,activation_agent_v14='KOH',precursor_v14='reed straw with melamine'),
 notes=['120 C partial hydrothermal carbonization is separate from550 C activation. No precise mass loading located in own methods.']),
'10.1002/asia.70648':dict(locator='PDF p2 synthesis and p3 working electrodes',anchors=['700','0.5 h','2–3'],
 common=dict(precarbonization_temperature_C=400,precarbonization_duration_h=2,precarbonization_heating_rate_C_min=10,activation_temperature_C=700,activation_duration_h=0.5,heating_rate_C_min=10,activation_agent_v14='KOH',precursor_v14='mixed Chinese herbal medicine residues'),
 electrode=dict(mass_loading_range_mg_cm2_v14={'lower':2,'upper':3,'kind':'author_reported_range'}),notes=['2–3 mg/cm2 kept as a range; no midpoint used.']),
'10.1002/ente.202201281':dict(locator='PDF p8 Experimental Section',anchors=['600','800','3 mg'],
 common=dict(precarbonization_temperature_C=800,precarbonization_duration_h=2,precarbonization_heating_rate_C_min=5,activation_temperature_C=600,activation_duration_h=2,heating_rate_C_min=5,activation_agent_v14='KOH',precursor_v14='Kochia'),
 notes=['Own methods explicitly carbonize800 C then activate600 C. Existing3mg/cm2 unchanged.']),
'10.1007/s10854-026-18573-2':dict(locator='PDF p3 section2.2; p4 electrode fabrication',anchors=['500','700','5'],
 common=dict(precarbonization_temperature_C=500,precarbonization_duration_h=1,precarbonization_heating_rate_C_min=5,activation_temperature_C=700,activation_duration_h=1,heating_rate_C_min=5,activation_agent_v14='KOH',precursor_v14='AMFS biomass as named by authors'),
 notes=['Characterization TGA ramp10 Cmin and1000 C are not synthesis. No loading inferred from2x1cm collector.']),
'10.1016/j.biombioe.2026.109160':dict(locator='PDF p2 section2.2',anchors=['200','700','90 min'],
 common=dict(pretreatment_temperature_C=200,pretreatment_duration_h=1/3,pretreatment_heating_rate_C_min=10,activation_temperature_C=700,activation_duration_h=1.5,activation_agent_v14='KOH',precursor_v14='walnut shell and urea'),
 notes=['NCHU20 own20min precursor treatment defined by t.10 Cmin applies to200 C treatment, not700 C activation.']),
'10.1016/j.biombioe.2026.109168':dict(locator='PDF p2 synthesis and electrode procedure',anchors=['400','700','2.5'],
 common=dict(precarbonization_temperature_C=400,precarbonization_duration_h=1,precarbonization_heating_rate_C_min=10,activation_temperature_C=700,activation_duration_h=2,heating_rate_C_min=10,activation_agent_v14='K2CO3',precursor_v14='CCL biomass as defined in main'),
 electrode=dict(active_mass_range_mg_v14={'lower':2.5,'upper':3,'kind':'author_reported_range'}),
 notes=['No electrode area assumed;2.5–3mg is mass, not areal loading.']),
'10.1016/j.ijbiomac.2023.128794':dict(locator='PDF p5-6 sections2.2/2.4',anchors=['140','800','2 - 3'],
 common=dict(hydrothermal_temperature_C=140,hydrothermal_duration_h=8,activation_temperature_C=800,activation_duration_h=2,activation_agent_v14='KOH',precursor_v14='rapeseed meal'),
 electrode=dict(active_mass_range_mg_v14={'lower':2,'upper':3,'kind':'author_reported_range'}),notes=['Own text gives Ni foam(1.0 cm), insufficient to establish coated area.']),
'10.1016/j.jaap.2026.107754':dict(locator='PDF p3 section2.2',anchors=['700','100','2 h'],
 common=dict(activation_temperature_C=700,activation_duration_h=2,post_treatment_temperature_C=100,post_treatment_duration_h=2,activation_agent_v14='KOH',precursor_v14='chestnut shells'),
 electrode=dict(ink_recipe_v14={'active_powder_mg':18,'binder_PVDF_mg':2,'solvent_mL':2,'delivered_mass_unknown':True}),notes=['H3PO4 postfunctionalization100 C/2h is not700 C activation. Ink stock mass18mg is not deposited electrode mass.']),
'10.1016/j.jenvman.2025.125582':dict(locator='PDF p2 synthesis section',anchors=['700','1-h','NPC-T'],
 common=dict(activation_temperature_C=700,activation_duration_h=1,activation_agent_v14='NaOH/urea solvent during one-step carbonization/activation',precursor_v14='cellulose and extracted sludge organic matter'),
 notes=['T in NPC-T-w explicitly defined as annealing temperature; own NPC7006 mapped with text and sample definition. No heating ramp inferred.']),
'10.1016/j.jenvman.2026.129124':dict(locator='PDF p2 sections2.3 and p3 section2.5',anchors=['240','800','2.5'],
 common=dict(hydrothermal_temperature_C=240,hydrothermal_duration_h=1,activation_temperature_C=800,heating_rate_C_min=10,activation_agent_v14='KOH',precursor_v14='cellulose with sludge aqueous phase'),
 electrode=dict(active_mass_mg_v14=2.5),notes=['Activation hold duration not found. Circular-sheet area unreported;2.5mg is not mg/cm2.']),
'10.1021/acsomega.3c04692':dict(locator='XML own QSC/QSC-x preparation and electrode procedure',anchors=['600','800','2–3.0'],
 common=dict(precarbonization_temperature_C=600,precarbonization_duration_h=2,precursor_v14='quinoa straw'),
 sample_overrides={'QSC':dict(carbonization_temperature_C=600,carbonization_duration_h=2,activation_applicability_v14='nonactivated carbonization control'),
 'QSC-2':dict(activation_temperature_C=800,activation_duration_h=2,heating_rate_C_min=5,activation_agent_v14='K2CO3'),
 'QSC-3':dict(activation_temperature_C=800,activation_duration_h=2,heating_rate_C_min=5,activation_agent_v14='K2CO3'),
 'QSC-4':dict(activation_temperature_C=800,activation_duration_h=2,heating_rate_C_min=5,activation_agent_v14='K2CO3')},
 electrode=dict(active_mass_range_mg_v14={'lower':2,'upper':3,'kind':'author_reported_range','collector_cm2':2}),notes=['QSC control not assigned800 C activation. Range2–3mg not replaced by midpoint.']),
'10.1021/acssusresmgt.3c00028':dict(locator='PDF p3 own synthesis and Supercapacitor subsection',anchors=['800','1.2 mg'],
 common=dict(activation_temperature_C=800,activation_duration_h=2,heating_rate_C_min=5,activation_agent_v14='KOH with NH4Cl',precursor_v14='agarwood leaves'),
 electrode=dict(mass_loading_mg_cm2=1.2,loading_evidence_kind_v14='nominal1.2mg active material divided by coated1x1cm2 graphite'),
 notes=['ORR ink5mg and symmetric total2mg not transferred to the3E cycling tests. Both own acid/neutral3E endpoints share recipe.']),
'10.1039/d3ra07014j':dict(locator='XML own two-step carbonization and electrode preparation',anchors=['800','7–9'],
 common=dict(pretreatment_temperature_C=200,pretreatment_duration_h=2,pretreatment_heating_rate_C_min=5,carbonization_temperature_C=800,carbonization_duration_h=2,carbonization_heating_rate_C_min=5,activation_applicability_v14='no separate activation step declared',precursor_v14='regenerated cellulose aerogel; acetic-acid antisolvent'),
 electrode=dict(mass_loading_range_mg_cm2_v14={'lower':7,'upper':9,'kind':'author_reported_range'}),notes=['Solvent/antisolvent processing not relabeled as thermal activation.']),
'10.1039/d4cp01914h':dict(locator='PDF p2 own CW/UACW/AUACW preparation',anchors=['700','2 h'],
 common=dict(activation_temperature_C=700,activation_duration_h=2,activation_agent_v14='KOH/urea',precursor_v14='sawdust; acid-modified UACW'),
 notes=['AUACW inherits the explicitly described UACW700 C/2h preparation followed by acid modification. Ramp/loading not located; official SI attempt404, main HTML403.']),
'10.1039/d4ta02115k':dict(locator='PDF p5-7 sections2.2-2.4',anchors=['600','3 h','1-2 mg'],
 common=dict(hydrothermal_temperature_C=180,hydrothermal_duration_h=12,activation_temperature_C=600,activation_duration_h=3,heating_rate_C_min=3,activation_agent_v14='KOH',precursor_v14='onion peel; separately specified B/N/P addition'),
 electrode=dict(mass_loading_range_mg_cm2_v14={'lower':1,'upper':2,'kind':'author_reported_range'}),notes=['Controls explicitly use similar method with only dopants omitted. Device about2mg/cm2 is not the3E range midpoint.']),
'10.1039/d4ya00076e':dict(locator='PDF p3 preparation and distinct3E/2E measurement sections',anchors=['600','800','703.5'],
 common=dict(precarbonization_temperature_C=600,precarbonization_duration_h=3,activation_temperature_C=800,activation_duration_h=3,activation_agent_v14='KOH/KNO3',precursor_v14='soybean straw'),
 notes=['3E ink delivered volume unreported; device volumetric density703.5mg/cm3 not a3E areal loading.']),
'10.1039/d6na00276e':dict(locator='XML bare rice-straw carbon synthesis and electrode method',anchors=['600','6 h','2.2'],
 common=dict(carbonization_temperature_C=600,carbonization_duration_h=6,activation_applicability_v14='no separate activation stated for bare carbon control',precursor_v14='rice straw'),
 notes=['ZnO composite hydrothermal180 C/24h does not apply to bare AC control. Existing2.2mg/cm2 unchanged.']),
'10.1088/1361-6528/ace97a':dict(locator='PDF p3 synthesis, p4 electrode methods',anchors=['300','600','5'],
 common=dict(precarbonization_temperature_C=300,precarbonization_duration_h=2,precarbonization_heating_rate_C_min=5,activation_temperature_C=600,activation_duration_h=2,heating_rate_C_min=5,activation_agent_v14='KNO3',precursor_v14='sesame residue'),
 notes=['SS300 name refers to first-stage300 C; final activation600 C. Device2–3mg not transferred to3E.']),
'10.3390/mi14030572':dict(locator='XML own sample preparation and electrochemistry',anchors=['600','10 mg'],
 common=dict(activation_temperature_C=600,activation_duration_h=2,heating_rate_C_min=5,activation_agent_v14='ZnCl2',precursor_v14='pine wood'),
 sample_overrides={'WET-1':dict(impregnation_method_v14='aqueous impregnation'),'DRY-1':dict(impregnation_method_v14='physical dry mixing')},
 electrode=dict(mass_loading_mg_cm2=10),notes=['10mg/cm2 is explicit high nominal loading, not a typo to be clipped. TGA10 Cmin excluded.']),
'10.3390/molecules31132329':dict(locator='XML own preparation paragraphs and Table1 sample definitions',anchors=['500','1.5 h','AC-850'],
 common=dict(precarbonization_temperature_C=500,precarbonization_duration_h=2,precarbonization_heating_rate_C_min=5,precursor_v14='algae biomass'),
 sample_overrides={'AHPC-700':dict(activation_temperature_C=700,activation_duration_h=1.5,activation_agent_v14='KOH'),
 'AHPC-800':dict(activation_temperature_C=800,activation_duration_h=1.5,activation_agent_v14='KOH'),
 'AHPC-850':dict(activation_temperature_C=850,activation_duration_h=1.5,activation_agent_v14='KOH'),
 'AHPC-900':dict(activation_temperature_C=900,activation_duration_h=1.5,activation_agent_v14='KOH'),
 'AC-850':dict(carbonization_temperature_C=850,activation_applicability_v14='explicit nonactivated reheated-char control')},
 notes=['Activation ramp not stated; do not borrow first-stage5 Cmin. AC850 final hold duration not assigned1.5h without explicit statement.']),
'10.3390/nano13101654':dict(locator='XML own direct pyrolysis; existing SI p1-2',anchors=['800','3 h'],
 common=dict(carbonization_temperature_C=800,carbonization_duration_h=3,activation_applicability_v14='explicit direct pyrolysis without chemicals or template',precursor_v14='Anacardium occidentale nut skin'),
 notes=['SI exists locally but source-to-DOI association was missing. SI gives1cm2 carbon cloth and95:5 powder/binder, but no deposited mass; loading remains unknown.']),
'10.3390/nano13172431':dict(locator='XML own SNPB-X-Y synthesis',anchors=['400','800','5'],
 common=dict(precarbonization_temperature_C=400,precarbonization_duration_h=2,precarbonization_heating_rate_C_min=5,activation_temperature_C=800,activation_duration_h=2,heating_rate_C_min=5,activation_agent_v14='KOH',precursor_v14='Spirulina'),
 notes=['800 and ratio4 bound by explicit SNPB-X-Y definition and own preparation.']),
'10.3390/polym15234478':dict(locator='XML own hydrothermal/activation and electrode procedure',anchors=['240','800','1 h'],
 common=dict(hydrothermal_temperature_C=240,hydrothermal_duration_h=1,activation_temperature_C=800,activation_duration_h=1,heating_rate_C_min=10,activation_agent_v14='KOH',precursor_v14='cellulose and thiourea'),
 notes=['No mass loading inferred from10mm disk diameter; precursor temperature240 C not activation800 C.']),
'10.3390/polym17091198':dict(locator='XML own hydrogel/aerogel thermal treatment and sample naming',anchors=['800','CMC-ZnK'],
 common=dict(activation_temperature_C=800,activation_agent_v14='potassium citrate/zinc acetate template-assisted pyrolysis',precursor_v14='chitosan/melamine aerogel'),
 notes=['Own dual activating/template agents pyrolysis800 C. No hold duration, ramp or loading point located; drying100 C/10h is not carbonization.']),
'10.3390/polym17111544':dict(locator='XML own synthesis and working-electrode preparation',anchors=['800','8 mg'],
 common=dict(carbonization_temperature_C=800,carbonization_duration_h=2,carbonization_heating_rate_C_min=5,activation_applicability_v14='no separate activation step declared',precursor_v14='sodium alginate/nanocellulose aerogel'),
 electrode=dict(mass_loading_mg_cm2=8,loading_evidence_kind_v14='author8mg active mass on explicitly coated1cm2 nickel foam'),
 notes=['No independent chemical-activation stage invented. Binder/carbon black mass excluded by author active-substance8mg statement.'])}

def main():
    target=BATCH/'reviewed_parameters.json'
    if target.exists():raise FileExistsError('Do not overwrite completed review.')
    packets=json.loads((BATCH/'method_packets.json').read_text('utf-8'))
    with open_database() as db:rows=db.fetch().rows;assert db.contract['version']=='v0.13'
    assert set(RECIPES)=={r['source_group'].removeprefix('doi:') for r in rows}
    records=[];protected={}
    for p in packets:
        doi=p['doi'];recipe=RECIPES[doi];source=p['source'];path=Path(source['path'])
        rel=path.relative_to(ROOT).as_posix();protected[rel]=source['sha256']
        for r in [r for r in rows if r['source_group'].removeprefix('doi:')==doi]:
            material=copy.deepcopy(recipe['common']);material.update(recipe.get('sample_overrides',{}).get(r['sample_name'],{}))
            test=copy.deepcopy(recipe.get('electrode',{}))
            evidence=[dict(path=rel,sha256=source['sha256'],locator=recipe['locator'],fields=list(material)+([] if recipe.get('electrode_si') else list(test)),
                basis='Own-sample/common-protocol manual review; ordered thermal roles and controls checked. '+' '.join(recipe['notes']))]
            if recipe.get('electrode_si'):
                si=ROOT/recipe['electrode_si'];h=hashlib.sha256(si.read_bytes()).hexdigest();protected[recipe['electrode_si']]=h
                evidence.append(dict(path=recipe['electrode_si'],sha256=h,locator='SI p2 working electrode fabrication',fields=list(test),basis=recipe['notes'][0]))
            records.append(dict(endpoint_id=r['endpoint_id'],doi=doi,sample_name=r['sample_name'],material_key=r['material_key_v11'],
                material_updates=material,test_updates=test,evidence=evidence,notes=recipe['notes'],
                review_status='agent_reviewed_own_methods',reviewer='Codex agent; not independent expert sign-off'))
    ao='同体系文献补充_第二批_20261017/定向扩搜40至60篇_20261017/sources/OA059/nanomaterials-2373998-supplementary.pdf'
    protected[ao]=hashlib.sha256((ROOT/ao).read_bytes()).hexdigest()
    target.write_text(json.dumps(dict(parent_version='v0.13',reviewed_sources=30,reviewed_main_tests=42,
        qualification='Primary methods and identified SI; numeric choices are explicit agent review, not regex output.',records=records),ensure_ascii=False,indent=2)+'\n','utf-8')
    (BATCH/'protected_sources.json').write_text(json.dumps(protected,ensure_ascii=False,indent=2)+'\n','utf-8')
    print(json.dumps(dict(reviewed_sources=len(packets),records=len(records),protected_sources=len(protected)),ensure_ascii=False))
if __name__=='__main__':main()
