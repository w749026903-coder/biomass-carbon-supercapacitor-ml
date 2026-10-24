"""Explicit, source-reviewed v0.15 field selections and 41-record dispositions.

This is a single-use curation batch, not an automatic extractor or training run.
Originals, parent databases, targets, and profile memberships are immutable.
"""
from pathlib import Path
import collections, copy, json, sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from inspect_existing_sources_v015 import ROOT,BATCH,SNAPSHOT,read,sha,segments

def main():
    target=BATCH/'reviewed_curation.json'
    if target.exists():raise FileExistsError(target)
    baseline=read(SNAPSHOT); rows=baseline['all_rows'];papers={p['doi']:p for p in baseline['papers']}
    selections=[];agreements=[];alternatives=[]
    def source(doi,part='main'):
        fs=papers[doi]['sources']
        if part=='main':
            candidates=[f for f in fs if Path(f['path']).name in ('main.xml','main.pdf','公开全文.xml','fulltext.xml') or Path(f['path']).name.startswith('ADD_')]
            candidates.sort(key=lambda f:(f['format']!='xml',len(f['path'])))
        else:candidates=[f for f in fs if part.lower() in f['path'].lower()]
        assert candidates,(doi,part)
        return candidates[0]
    def ev(doi,part,locator,basis):
        s=source(doi,part);return dict(path=s['path'],sha256=s['sha256'],locator=locator,basis=basis)
    def add(key,values,evidence,reason,scope='material',allow_corrections=()):
        for field,value in values.items():
            before=rows[key].get(field)
            if before==value:
                agreements.append(dict(endpoint_id=key,field=field,value=value,evidence=evidence));continue
            if before is not None and field not in allow_corrections:
                alternatives.append(dict(endpoint_id=key,field=field,current=before,candidate=value,evidence=evidence,reason=reason));continue
            selections.append(dict(endpoint_id=key,material_key=rows[key]['material_key_v11'],field_name=field,before=before,after=value,
                operation='correct_measurement_method' if before is not None else 'fill_missing',scope=scope,evidence=[{**e,'fields':[field]} for e in evidence],reason=reason))
    def first(doi,sample=None):
        keys=papers[doi]['endpoint_ids']
        return next(k for k in keys if sample is None or rows[k]['sample_name']==sample)

    doi='10.1021/acsomega.3c04692'
    e=ev(doi,'main','XML Table1 / tbl1 own rows','Vtotal is explicitly cm3/g; use the reported column, not Vmicro+Vmeso. Some rounded pore partitions are not additive.')
    for name,v in [('QSC',.189),('QSC-2',.342),('QSC-3',.756),('QSC-4',.433)]:
        add(first(doi,name),{'total_pore_volume_cm3_g':v},[e],'补回自身Table1总孔容；不以分项加和覆盖作者报告列。')
    doi='10.1016/j.biombioe.2026.109160';key=first(doi)
    add(key,{'mesopore_volume_cm3_g':.994,'average_pore_diameter_nm':2.337,'reported_mesopore_diameter_nm_v15':3.387},
        [ev(doi,'main','PDF p3 Table1 NCHU20 row','Own Table1: Vtotal2.211, Vmeso0.994, Daver2.337, Dmeso3.387; no micropore subtraction assumed.')],
        '原文自身Table1补提介孔容与总孔/介孔平均孔径；不拿NCHU40最小值或TEPA负载后样品作特征。')
    for field,val in [('bulk_N_wt_pct',5.69),('bulk_O_wt_pct',20.94)]:
        add(key,{field:val},[ev(doi,'NCHU20_mmc1.docx','SI TableS3; DOCX table8 NCHU20','EA wt%, O* calculated by difference; these fields already existed in v0.14.')],'复核已有本体元素，不重复计作新增。')
    doi='10.3390/polym15234478';key=first(doi)
    add(key,{'XPS_N_reported_pct':3.2,'XPS_O_reported_pct':24.16,'XPS_percentage_basis':'weight_explicit',
             'XPS_S_reported_pct_v15':3.73},
        [ev(doi,'main','XML Table2 / polymers-15-04478-t002 AHC-CL-TU','Table explicitly says XPS-derived elemental contents (wt%); separate from EA Table1.')],
        'XPS质量百分数按作者原口径保存，不改成原子百分数或本体EA。')
    add(key,{'bulk_N_wt_pct':3.25,'bulk_O_wt_pct':12.46},[ev(doi,'main','XML Table1 AHC-CL-TU','EA wt% of activated AHC, not hydrochar HC.')],'本体元素已有值复核。')
    doi='10.1016/j.biombioe.2026.109168';key=first(doi)
    add(key,{'bulk_N_wt_pct':1.39,'bulk_O_wt_pct':19.23,'water_contact_angle_deg_v15':17.6},
        [ev(doi,'CCL_mmc1.docx','SI TableS3 own row / TableS5 EA wt%','Own CCL-K2CO3-1-700; contact angle17.6deg; EA N1.39/O19.23 already in v0.14.')],'区分前驱体CCL、本体EA与XPS，补自身接触角。')
    doi='10.1016/j.jaap.2026.107754'
    add(first(doi),{'total_pore_volume_cm3_g':.26},[ev(doi,'main','PDF p6 pore characterization','CSKOH0.37 and P-doped CSKOH0.26 cm3/g, respectively.')],'补回P掺杂样品自身孔容，不借未掺杂0.37。')
    doi='10.1002/ente.202201281'
    add(first(doi),{'Raman_ID_IG':.99,'XPS_O_reported_pct':8.25,'XPS_percentage_basis':'atomic_explicit',
                    'water_contact_angle_deg_v15':58.25},
        [ev(doi,'main','PDF p4 text and p5 Fig3b,c,f','Fig3b KAC-5 ID/IG0.99; Fig3c inset At% C91.75/O8.25; Fig3f contact angle58.25deg at70ms.')],
        '自身图中明确数字，与正文吻合；接触角时点70ms另记，不作为平衡接触角。')
    add(first(doi),{'contact_angle_time_ms_v15':70},[ev(doi,'main','PDF p5 Fig3f','58.25deg marked at70ms; full absorption within1s.')],'补测量时点。')
    doi='10.3390/molecules28124633';key=first(doi)
    add(key,{'Raman_ID_IG':round(1/1.292,6),'Raman_IG_ID_reported_v15':1.292,
             'Raman_conversion_v15':{'formula':'1 / 1.292','relation':'derived_reciprocal','rounded_decimals':6},
             'XPS_N_reported_pct':6.1,'XPS_O_reported_pct':13.0,'XPS_percentage_basis':'atomic_explicit',
             'N_at_pct':6.1,'O_at_pct':13.0,
             'nitrogen_claims_v15':{'abstract_pct':6.02,'body_and_own_Fig4d_XPS_at_pct':6.1,'abstract_basis_unspecified':True}},
        [ev(doi,'main','PDF p4 Raman discussion; p5 Fig3b; p6 Fig4d atomic% inset; p1 abstract','Own RSM-0.33-550 IG/ID1.292, not RSM-1-5501.232. Fig4d XPS N6.1/O13.0 atomic%. Abstract6.02 retained separately.')],
        '从自身图数字补提，原IG/ID和倒数公式同时保存；XPS图标明atomic%，摘要不同口径主张保留。')
    doi='10.1039/d4ya00076e'
    add(first(doi),{'XRD_d002_nm':.37},[ev(doi,'main','PDF p6 Fig3b adjacent text','Explicit d002 for SSC2-0/.5/.6/.7 = .34/.36/.37/.39nm, respectively.')],'作者明确给出SSC2-0.6晶面间距，不从峰位重新猜算。')
    doi='10.1039/d6na00276e'
    add(first(doi),{'XRD_d002_nm':.310,'XRD_d002_definition_v15':'author Table1 AC (002) d-spacing3.10 Angstrom; converted to nm; no ZnO/composite row used'},
        [ev(doi,'main','XML Table1 / tab1 AC (002) row','Own AC d-spacing3.10 Angstrom, conversion0.310nm; other rows belong to ZnO/composite.')],'按作者自身AC表格换算Å至nm，保留报告性质，不借复合物行。')
    doi='10.1021/acssusresmgt.3c00028';key=first(doi)
    add(key,{'XPS_N_reported_pct':4.64,'XPS_O_reported_pct':7.44},
        [ev(doi,'main','PDF p6 XPS section before ORR tests; SI FigS4','Initial ALPC-800 XPS explicitly N4.64atom%/O7.44atom%. SI TableS1 is FESEM-EDX, not XPS.')],
        '纠正把EDS原子组成填入XPS的提取方法错误；旧11.23/8.54及出处保留，未更改原论文本身。',allow_corrections=('XPS_N_reported_pct','XPS_O_reported_pct'))
    add(key,{'total_pore_volume_cm3_g':.35,'EDS_N_at_pct_v15':11.23,'EDS_O_at_pct_v15':8.54,
             'legacy_atomic_percentage_method_v15':'N_at_pct/O_at_pct retain initial FESEM-EDX atomic percentages; use explicit XPS fields for XPS-only modeling',
             'pore_conflict_candidates_v15':{'SI_micropore_area_m2_g':757,'SI_BET_m2_g':718,
               'SI_micropore_volume_cm3_g':.382,'SI_total_pore_volume_cm3_g':.35,
               'canonical_micropore_fields_withheld':True,'reason':'micropore exceeds corresponding total; no silent swap or correction'}},
        [ev(doi,'rm3c00028_si_001.pdf','SI PDF p6 TableS1 visually inspected','FESEM-EDX N11.23/O8.54atomic%; Vtotal.35cc/g supported by main p6. Smicro757>BET718 and Vmicro.382>Vtotal.35 withheld.')],
        '总孔容由正文与SI双重支持；图像表内微孔数值冲突隔离；保留EDS原子组成及历史原子字段测量来源。')
    doi='10.3390/molecules31132329'
    for name,angle,uptake,conduct in [('AC-850',91,1.4,38),('AHPC-700',63,2.2,54),('AHPC-800',38,3.6,71),('AHPC-850',24,4.5,86),('AHPC-900',31,4.2,73)]:
        add(first(doi,name),{'water_contact_angle_deg_v15':angle,'electrolyte_uptake_g_g_v15':uptake,'pellet_conductivity_S_m_v15':conduct},
            [ev(doi,'main','XML Table6 / molecules-31-02329-t006 own sample row','Before cycling interfacial/transport properties; conductivity belongs to pellets, not electrochemical impedance.')],
            '保存循环前直接材料性质候选；不自动扩大原18字段或声称可独立提高预测。')
    # Pending records can gain descriptors without gaining training membership.
    doi='10.21203/rs.3.rs-11058750/v1';key=first(doi)
    add(key,{'BET_m2_g':1018.74,'average_pore_diameter_nm':3.25,
             'reported_maximum_pore_volume_cm3_g_v15':.5238,
             'retention_verbal_claim_v15':'maintaining initial capacitance / no discernible loss after10000 cycles at10A/g; no exact numeric endpoint selected'},
        [ev(doi,'main','Preprint PDF p3 abstract; p9 Table1; p17 cycling paragraph','Own HTWB-0.5-900 SBET1018.74, maximum pore volume.5238, average diameter3.25. Verbal no-loss statement is not exact100%.')],
        '补预印本自身BET与描述符，不把无明显损失伪造成100%精确标签，也不视作期刊发表。')
    doi='document:b1fe8f461ebdeaba2d59dfdd49820c802b113fc6035ff52e2d6147eca5db23f2';key=first(doi)
    add(key,{'BET_m2_g':2142,'Raman_ID_IG':.83,'bulk_N_wt_pct':.7,'bulk_O_wt_pct':7.1,
             'bulk_element_basis_v15':'dry ash-free (d.a.f.) as reported; not automatically interchangeable with other bulk bases'},
        [ev(doi,'main','SSRN PDF p11 text/Table1 citation; p18 EA paragraph','Own Au-free AC700 BET2142, ID/IG.83; ultimate analysis N.7/O7.1wt% d.a.f.; Au-decorated2180 not borrowed.')],
        '补无Au自身对照，不从复合样品移借；期刊版本及年份身份仍未核实。')

    pending=[]
    for old in baseline['pending']:
        key=old['endpoint_id'];doi=old['source_group'].removeprefix('doi:');r=rows[key]
        evidence=[]
        # Existing primary/SI files are inspected in-place, not re-downloaded.
        for s in papers[doi]['sources']:
            evidence.append(dict(path=s['path'],sha256=s['sha256'],locator='Targeted original table/figure/method review; previous precise locators retained in inherited evidence() and batch review files',fields=['review_disposition_v15'],basis=old['reason']))
        c=dict(endpoint_id=key,sample_name=r['sample_name'],source_group=r['source_group'],
            previous_reason=old['reason'],previous_open_issues=old['open_issues'],open_issues=copy.deepcopy(old['open_issues']),
            approved_profiles=copy.deepcopy(r['admission_profiles_v13']),disposition='pending_original_evidence',
            reason=old['reason'],resolution=[],evidence=evidence,access_scope='existing local main/SI only; no new publisher or author contact',
            reviewer='Codex agent targeted original-source review; not independent expert sign-off')
        if key=='legacy:SRC126_CY01':
            c.update(disposition='outside_material_scope',open_issues=[],resolution=['Cu_and_Cu2O_phases_explicitly_identified'],
                reason='主文XRD明确识别Cu与Cu2O晶相，XPS Cu2p及作者讨论确认含铜活性体系；依既有普通多孔碳用途边界排除，保存其它研究用途。不是因为保持率高低排除。',
                evidence=[{**ev(doi,'main','XML p11 XRD; p12 XPS; p13 electrochemical discussion','Cu and Cu2O phases explicitly assigned, not inferred from sample name.'),'fields':['review_disposition_v15']}])
        elif key=='candidate:TE032':
            c.update(disposition='outside_material_scope',open_issues=[],resolution=['isolated_synthetic_SAP_precursor_identified'],
                reason='原文明确分离尿布吸水聚合物颗粒并碳化，主体SAP为聚丙烯酸钠；不是把整片含纤维素尿布直接作为前驱体。依既有生物质来源范围排除，保留原值及其它用途。',
                evidence=[{**ev(doi,'main','XML p6 SAP identity; p9 isolation; p10 pyrolysis','Isolated sodium-polyacrylate-rich SAP particles are pyrolyzed; cellulose elsewhere in diaper does not establish biomass-derived carbon skeleton.'),'fields':['review_disposition_v15']}])
        elif key=='incoming:ADD_073_T01':
            c.update(disposition='partly_completed_identity_pending',open_issues=['peer_reviewed_version_and_year'],resolution=['own_BET_and_Raman_and_bulk_composition_recovered'],
                reason='自身无Au AC700的BET2142、ID/IG0.83及EA质量组成已从原文补齐；仍为未同行评审SSRN文件，年份和对应正式版本未核实，不准入。')
        elif key=='incoming:ADD_058_T01':
            c.update(disposition='partly_completed_version_and_target_pending',open_issues=['peer_reviewed_version','own_numeric_retention_point_label'],resolution=['own_BET_recovered'],
                reason='HTWB-0.5-900自身BET1018.74及孔径已补齐；正文仅称无明显损失，未选精确100%点标签；本地仍为ResearchSquare v1预印本，期刊身份未核实。')
        pending.append(c)
    assert len(pending)==len({c['endpoint_id'] for c in pending})==41
    document=dict(parent_version='v0.14',main_tests=42,main_sources=30,fixed_pending_tests=41,fixed_pending_sources=27,
        scientific_values_are_agent_reviewed=True,model_fits=0,selection_count=len(selections),selections=selections,
        agreements=agreements,unselected_alternatives=alternatives,pending_reviews=pending,
        limits=['No new literature download or publisher-version check in this local batch.','No author correction or raw measurement files acquired.','No retraining; past v1.0/v1.1 metrics remain historical.'])
    target.write_text(json.dumps(document,ensure_ascii=False,indent=2)+'\n','utf-8')
    print(json.dumps(dict(selections=len(selections),agreements=len(agreements),alternatives=len(alternatives),pending_dispositions=dict(collections.Counter(c['disposition'] for c in pending))),ensure_ascii=False))
if __name__=='__main__':main()
