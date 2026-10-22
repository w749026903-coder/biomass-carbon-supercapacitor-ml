"""Prepare a small, append-only adjudication batch; never rebuild a prior release."""
from pathlib import Path
import copy, hashlib, json, sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from data.cycling_db import open_database
BATCH=ROOT/'冲突复核与来源充分性_20261022'
OLD=ROOT/'待补证原文复核_20261022'

def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(p,v):
    if p.exists():raise FileExistsError(p)
    p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n','utf-8')
def evidence(path,locator,fields,basis):
    return dict(path=path,sha256=sha(ROOT/path),locator=locator,fields=fields,basis=basis)

def main():
    target=BATCH/'reviewed_cases.json'
    if target.exists():raise FileExistsError(target)
    old={c['endpoint_id']:c for c in json.loads((OLD/'reviewed_cases.json').read_text('utf-8'))['cases']}
    with open_database() as db:
        assert db.contract['version']=='v0.12'
        rows={r['endpoint_id']:r for r in db.fetch('all_review').rows}
    cases=[]
    def case(key,changes,reason,issues=None,profiles=None,resolution=None,ev=None):
        previous=old[key]
        c=dict(endpoint_id=key,changes=changes,reason=reason,
               approved_profiles=profiles if profiles is not None else rows[key]['admission_profiles_v12'],
               open_issues=issues if issues is not None else previous.get('open_issues',[]),
               disposition='reviewed_conflict_remains',resolution=resolution or [],
               evidence=ev or copy.deepcopy(previous['evidence']),
               reviewer='Codex agent original-source review; not independent expert sign-off')
        for e in c['evidence']:assert sha(ROOT/e['path'])==e['sha256']
        cases.append(c);return c
    p='同体系文献补充_第二批_20261017/定向扩搜40至60篇_20261017/sources/OA001/main.xml'
    rule=('Table7分别列明各自身样品10000圈循环保持率、倍率保持率和CE；共同方法明确6 M KOH、Ag/AgCl、−1至0 V、GCD循环10 A/g。'
          '未提出另一种循环保持率分母。报告工况用途接受作者表格自身的循环保持率语义，参照精确循环下标/归一化原值保持未知，'
          '不借优化样品Fig4d曲线，也不增加每个样品必须单独曲线的门槛。纠正此前过严的审查；并不证明作者原始仪器记录。')
    for key in rows:
        if 'candidate:v11:AHPC2026:' not in key:continue
        changes={'baseline_reference':{'reference':'author_table_reported_cycling_retention',
                 'cycle_index':None,'normalization_capacitance_F_g':None,
                 'basis':'Own Table7 Cycling Retention (10000 Cycles, %) under the common cycling protocol; exact normalization/index unspecified.'},
                 'baseline_evidence_kind_v13':'own_table_metric_and_common_protocol',
                 'baseline_reference_caveat_v13':'No own normalized trace or exact baseline cycle supplied; no AHPC-850 curve borrowed.'}
        c=case(key,changes,rule,[],['reported_3e','reported_3e_residue_sensitivity','reported_3e_sensitivity'],
               ['unnecessary_individual_curve_requirement_removed'],
               [evidence(p,'XML electrochemical methods; Table7 own sample row; Fig4 caption',list(changes),rule)])
        c['disposition']='approved_reported_protocol_table_metric'
    key='legacy:R018_CY01';p='三电极端点扩充_20261018/corpus/B_R018/main.pdf'
    changes={'preferred_retention_derivation_v13':{'value_pct':round(36.45/138.5*100,2),
             'relation':'derived_ratio','formula':'100 * 36.45 / 138.5',
             'initial_capacitance_F_g':138.5,'final_capacitance_F_g':36.45,
             'endpoint_cycles':5000,'current_A_g':2.5,
             'status':'detailed_values_and_own_plot_corrobated_not_author_correction',
             'competing_conclusion_pct':40,'training_admitted':False}}
    reason=('原Fig8b左轴为比电容、右轴红线为CE。蓝线初末约138.5/36.45 F/g，与正文详细端点相符，'
            '据此保存26.32%的可复算派生候选，不能用约100% CE作保持率。结论40%仍保留，原文还把约1000圈87.5写成100圈。'
            '这是图文详细端点优先的用途判读，不冒称作者勘误；自身BET仍缺，未获训练准入。')
    case(key,changes,reason,['own_BET_not_located','conclusion_40pct_not_author_corrected'],resolution=['CE_vs_retention_separated','preferred_ratio_derivation_recorded'],
         ev=[evidence(p,'PDF p11 Fig8b and detailed endpoints; p13 conclusion',list(changes),reason)])
    main='新增文献整理_20261020/originals/ADD_059.pdf'
    si='冲突复核与来源充分性_20261022/new_supplements/LCC_LCNC_mmc1.docx'
    for key in ['incoming:ADD_059_T01','incoming:ADD_059_T02']:
        changes={'electrolyte':'KOH','concentration_mol_L':6,'reference_electrode':'Hg/HgO',
                 'cycle_voltage_lower_V':-1,'cycle_voltage_upper_V':0,
                 'mass_loading_mg_cm2':None,
                 'loading_range_mg_cm2_v13':{'lower':1,'upper':2,'area_cm2_approx':1,
                     'basis':'approximately 1x1 cm carbon cloth; active mass 1-2 mg, not a single measured loading'}}
        if key.endswith('T01'):
            changes.update(total_pore_volume_cm3_g=2.6842,micropore_volume_cm3_g=2.4235,
                mesopore_volume_cm3_g=0.2607,micropore_surface_area_m2_g=3175.91,
                external_surface_area_m2_g=247.24,average_pore_diameter_nm=3.13,Raman_ID_IG=5.44,
                pore_surface_definition_v13='SI Table S1 Smeso retained as reported mesopore area; NOT equated with t-plot external area')
            # Smeso is not the same definition as t-plot external surface area.
            changes.pop('external_surface_area_m2_g')
            changes['reported_mesopore_surface_area_m2_g_v13']=247.24
            changes['label_claims_v13']={'body_and_Table8_pct':89,'conclusion_and_publisher_highlight_pct':88,
               'figure8d_endpoint_visual_pct_approx':88,'exact_choice_made':False}
            reason=('补回原文p5明示的共同3E协议；新出版社SI TableS1补LCC-3自身孔结构。Fig8d末端约88%，'
                    '结论/出版社亮点88%，正文/Table8为89%。保留差异，不用较高值覆盖；原图没有精确数值标签，未给精确训练标签。')
            issues=['88_vs89pct_label_not_author_corrected']
            resolution=['missing_protocol_extraction_corrected','own_SI_pore_structure_recovered']
        else:
            changes['sample_identity_assessment_v13']={'preferred_figure_sample':'LCNC-1',
                'support':['Fig10d caption','same cycling discussion opening','SI FigS6 LCNC-1 and Table7 electrochemical ranking'],
                'contradictory_sentence':'LCNC-3 at the end of cycling discussion',
                'canonical_sample_renamed':False,'unambiguous_author_correction':False}
            changes['label_claims_v13']={'body_pct':78.1,'figure10d_endpoint_visual_pct_approx':80,
                'figure_caption_sample':'LCNC-1','body_last_sentence_sample':'LCNC-3',
                'exact_choice_made':False}
            reason=('共同3E协议已补回；Fig10d图注和同段开头均指LCNC-1，末句却写LCNC-3。SI FigS6也明确研究LCNC-1。'
                    '优先样品归属记录为LCNC-1，但不静默改材料键或把LCNC-1 BET借给旧LCNC3记录。'
                    '循环图最后一个点约80%，正文78.1%，不能把近末稳定段冒充最终5000圈。维持冻结。')
            issues=['sample_identity_conflicting_sentence','78_1pct_vs_final_point_approx80pct']
            resolution=['missing_protocol_extraction_corrected','preferred_sample_identity_with_competing_claim_preserved']
        # Test-specific loading is not inferred from the 1-2 mg range.
        assert rows[key].get('mass_loading_mg_cm2') is None
        fields=list(changes)
        case(key,changes,reason,issues,resolution=resolution,ev=[
            evidence(main,'PDF p5 methods/Table4; p7 Raman; p9 Fig8d; p11 Fig10d; p12-13 endpoints/conclusion',
                     [f for f in fields if f not in ['micropore_volume_cm3_g','mesopore_volume_cm3_g','micropore_surface_area_m2_g','reported_mesopore_surface_area_m2_g_v13']],reason),
            evidence(si,'Publisher PII S0926669026010137; SI FigS6 and TableS1',
                     [f for f in fields if f in ['micropore_volume_cm3_g','mesopore_volume_cm3_g','micropore_surface_area_m2_g','reported_mesopore_surface_area_m2_g_v13','sample_identity_assessment_v13']],
                     'Official publisher PII attachment; sample/figure series and LCC3 TableS1 match main. No title/author front page in SI; identity established by publisher PII and content matching.')])
    # Actual conflicts cannot be decided by common practice, majority vote or a better score.
    remaining={
      'candidate:TE010':('方法6 M与自身Fig4/结果1 M冲突，原文/PMC未消除。出版社版本说明本次403；不是不存在勘误的证明。','concentration'),
      'candidate:V05:017':('方法甘汞与原Fig3 Hg/HgO冲突。常见使用Hg/HgO不能证明本试验如此；版本说明403，未取得作者更正。','reference'),
      'legacy:SRC121_CY01':('已明确硬件Hg/HgO与作者换算RHE可同时记录；1 M转换+0.924 V。CV程序−0.8至0 V明确，GCD图轴mV却数值约0.1至0.9，循环插图也为RHE。无法凭CV程序强定GCD上下限，继续保留窗口待证。','scale'),
      'candidate:TE028':('原Fig7d 2000圈最后点约82%，文字约85%。两者均非精确仪器记录，当前不能用任意读图误差包住差异；保留双方，不选较高数。','label'),
      'legacy:R069_CY01':('原Fig6a黑线KOH起末约137/129，正文/Table2均97.2%，与曲线比例不符；未报告循环A/g，不能借Fig5的1 A/g。酸/中性映射也冲突。','label'),
      'legacy:R069_CY02':('正文与Table2对Na2SO4/H2SO4保持率互换；Fig6a自身曲线比例也不支持两种报告值。循环A/g缺失，保留冻结。','label'),
      'legacy:R069_CY03':('正文与Table2对Na2SO4/H2SO4保持率互换；Fig6a自身曲线比例也不支持两种报告值。循环A/g缺失，保留冻结。','label'),
      'incoming:ADD_002_T01':('AGC原循环图caption10 A/g与inset20 A/g冲突；没有更正或原始程序，不能把表征窗口/电流当循环工况。','current'),
      'incoming:ADD_002_T02':('AGC-K同一循环caption10 A/g与inset20 A/g冲突，继续保持原始候选值及出处。','current')}
    for key,(reason,kind) in remaining.items():
        changes={}
        if kind=='scale':changes['potential_scale_metadata_v13']={'hardware_reference':'Hg/HgO','plotted_reference':'RHE',
            'author_offset_V':0.924,'electrolyte_concentration_mol_L':1,
            'author_CV_program_V_vs_HgHgO':[-0.8,0],
            'GCD_window_selected':False,'caveat':'Fig4b mV/RHE unit mismatch; CV range is not copied to cycling.'}
        ev=None
        if kind=='scale':
            ev=[evidence('三电极端点扩充_20261018/corpus/B_SRC121/main.pdf',
                'PDF p3 explicit conversion and CV programme; p6 Fig4b; p9 Fig6a cycling inset',list(changes),reason)]
        case(key,changes,reason,resolution=['hardware_and_reported_scale_separated'] if kind=='scale' else [],ev=ev)
    protected={e['path']:e['sha256'] for c in cases for e in c['evidence']}
    renders=[]
    # Current and existing figure renders are evidence views; originals remain authoritative.
    images=[('三电极端点扩充_20261018/corpus/B_R018/main.pdf',11,BATCH/'evidence_images/R018_p11.png',1.6)]
    images += [(main,n,BATCH/f'evidence_images/ADD059_p{n}.png',2) for n in [9,10,11,12]]
    for source,n,image,scale in images:
        protected[source]=sha(ROOT/source)
        renders.append(dict(source_path=source,source_sha256=protected[source],page_1based=n,scale=scale,
                            render_path=image.relative_to(ROOT).as_posix(),render_sha256=sha(image),
                            purpose='Visual conflict review; approximate visual estimates are not exact labels.'))
    write(BATCH/'render_provenance.json',renders)
    write(BATCH/'protected_sources.json',protected)
    write(target,dict(version='v0.13',purpose='Original-source adjudication; no model fits',
        baseline_rule_correction=rule,cases=cases))
    print(json.dumps(dict(reviewed=len(cases),new_main=4,protected_sources=len(protected)),ensure_ascii=False))
if __name__=='__main__':main()
