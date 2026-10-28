"""Refresh the same local dashboard from verified SQLite; never changes science data."""
from pathlib import Path
import argparse,datetime,json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from data.literature_current import open_literature_database
from data.literature_groups import source_grouped_candidates
from data.literature_v4 import PROFILES
from data.cycling_db import open_database

LABELS={'BET_surface_area_m2_g':'BET比表面积','micropore_area_reported_m2_g':'报告微孔面积','microporosity_reported_pct':'报告微孔率（基准未知）','micropore_volume_cm3_g':'微孔容','pore_width_nm':'孔宽','mesopore_volume_cm3_g':'介孔容','total_pore_volume_cm3_g':'总孔容','BJH_pore_diameter_nm':'BJH孔径','Raman_ID_IG':'Raman强度比ID/IG','BET_m2_g':'BET比表面积','XRD_d002_nm':'XRD层间距d002','average_pore_width_nm':'平均孔宽','average_pore_diameter_nm':'平均孔径','mesopore_surface_area_m2_g':'介孔面积','micropore_surface_area_m2_g':'微孔面积','reported_N2_pore_volume_cm3_g':'报告氮吸附孔容','reported_mesopore_surface_area_m2_g':'报告介孔面积','reported_mesopore_surface_fraction_pct':'报告介孔面积占比','reported_mesopore_volume_fraction_pct':'报告介孔孔容占比','reported_micropore_surface_area_m2_g':'报告微孔面积','reported_pore_size_nm':'报告孔尺寸','reported_pore_width_nm':'报告孔宽','reported_total_surface_area_m2_g':'报告总比表面积'}
def label(f):
    labels22={'QSDFT_total_pore_volume_cm3_g':'QSDFT总孔容','QSDFT_micropore_volume_cm3_g':'QSDFT微孔容','author_ash_free_recalculated_BET_m2_g':'作者去灰折算BET（非新测量）','TGA_air_author_carbon_fraction_pct':'TGA空气燃尽代理碳分数','author_overall_AC_mass_yield_pct':'原料至活性炭总收率','tplot_micropore_volume_raw_m3_g':'t-plot微孔容（原印m³/g，单位未解）','total_pore_volume_raw_m3_g':'总孔容（原印m³/g）','BJH_ads_pore_width_reported_nm':'BJH表头孔宽（脚注方法争议）','author_micropore_volume_fraction_pct':'作者微孔孔容占比'}
    if f in labels22:return labels22[f]
    if f.startswith('elemental_analysis_'):return '元素分析 '+f[18:].replace('_pct_basis_unspecified',' 百分比基准未知').replace('_',' ')
    if f.startswith('SEM_EDX_'):return 'SEM-EDX '+f[8:].replace('_reported_pct_basis_unspecified',' 百分比基准未知')
    if f.startswith('bulk_EA_'):return '体相元素分析 '+f[8:].replace('_wt_pct',' 质量百分比').replace('_mass_ratio',' 质量比').replace('_','/')
    labels17={'surface_area_as_printed_m3_g':'原印比表面积（m³/g量纲争议）','pore_size_as_printed_nm_footnote_disputed':'原印孔尺寸（nm，脚注争议）','Ar_BET_surface_area_m2_g':'Ar吸附BET面积','Ar_total_pore_volume_cm3_g':'Ar吸附总孔容','extrusion_screw_speed_rpm':'挤出螺杆转速','extrusion_barrel_temperature_C':'挤出筒温度','extrusion_feed_rate_g_min':'挤出进料速率','author_carbon_efficiency_pct':'作者碳效率（分母不含碳酸盐）','XPS_C_to_N_atomic_ratio':'XPS C/N原子比'}
    if f in labels17:return labels17[f]
    raman={'Raman_D_position_cm_inv':'Raman D峰位','Raman_G_position_cm_inv':'Raman G峰位','Raman_I2D_reported_intensity':'Raman 2D报告强度','Raman_ID_reported_intensity':'Raman D报告强度','Raman_IG_reported_intensity':'Raman G报告强度','Raman_I2D_IG':'Raman 2D/G报告比'}
    if f in raman:return raman[f]
    if f=='water_contact_angle_time_unspecified_deg':return '水接触角（时间未报）'
    if f=='XPS_C_O_reported_ratio':return 'XPS C/O报告比值'
    if f=='XPS_O_C_reported_ratio':return 'XPS O/C报告比值'
    if f in {'bulk_EA_C_reported_pct','bulk_EA_H_reported_pct','bulk_EA_N_reported_pct'}:return '体相元素分析 '+f.split('_')[2]+'（原报%）'
    if f=='author_O_by_100_minus_CHN_proxy_pct':return '作者O差值代理（100−CHN，含无机风险）'
    if f in {'author_atomic_O_C_ratio','author_atomic_H_C_ratio'}:return '作者原子比 '+('O/C'if 'O_C'in f else'H/C')
    if f=='HK_micropore_volume_cm3_g':return 'HK法微孔容'
    if f=='author_micropore_volume_fraction':return '作者微孔容/总孔容（比值）'
    if f=='author_mesopore_volume_fraction_pct':return '作者介孔体积分数（%）'
    if f=='activation_stage_yield_pct':return '活化阶段收率（以预炭化物为分母）'
    if f=='precarbonization_stage_yield_pct':return '预炭化阶段收率（以原料为分母）'
    if f=='raw_moisture_wt_pct':return '原料水分（质量%）'
    if f=='raw_dry_ash_wt_pct':return '原料灰分（干基质量%）'
    if f=='raw_dry_volatiles_wt_pct':return '原料挥发分（干基质量%）'
    if f=='raw_O_by_difference_dry_wt_pct':return '原料差减氧（干基质量%）'
    if f=='raw_prose_pore_volume_m3_g':return '正文孔容原印m³/g（单位争议）'
    if f=='raw_prose_misattributed_Vmeso_cm3_g':return '正文介孔容（样品归属异文）'
    if f=='tplot_micropore_volume_cm3_g':return 't-plot微孔容'
    if f=='BJH_mesopore_volume_cm3_g':return 'BJH介孔容'
    if f.startswith('XPS_'):
        body=f[4:].replace('_at_pct',' 原子百分比').replace('_wt_pct',' 质量百分比').replace('_reported_ratio',' 报告比值').replace('_reported_pct_basis_unspecified',' 原报百分比（原子/质量基准未标明）').replace('_envelope_pct',' 包络内比例').replace('_binding_energy_eV',' 峰位 eV').replace('_reported_FWHM',' FWHM（表未印单位）').replace('_peak',' 峰')
        return 'XPS '+body.replace('_double_','=').replace('_','–')
    if f.startswith('raw_bulk_EA_'):return '原料体相 '+f.split('_')[3]+'（干基质量%）'
    if f.startswith('EDS_'):return 'EDS '+f[4:].replace('_reported_pct',' 百分比（口径未知）').replace('_at_pct',' 原子百分比').replace('_wt_pct',' 质量百分比')
    if f.startswith('EDX_'):return 'EDX '+f[4:].replace('_wt_pct',' 质量百分比').replace('_at_pct',' 原子百分比').replace('_reported_line_energy_keV',' 作者线能量 keV').replace('_author_Error_pct',' 作者Error%（定义见原文）')
    if f.startswith('NLDFT_pore_peak_'):return 'NLDFT孔峰 '+f.split('_')[-2]+'（非均值）'
    if f=='author_t_pore_area_m2_g':return '作者t-pore面积（未统一孔类）'
    if f=='author_t_pore_volume_cm3_g':return '作者t-pore孔容（未统一孔类）'
    if f=='BET_fit_correlation_coefficient':return 'BET拟合相关系数（非模型R²）'
    more={'meso_plus_macro_volume_cm3_g':'介孔+大孔孔容（非介孔单量）','BJH_average_pore_diameter_nm':'BJH平均孔径','reported_pore_diameter_A':'报告孔径（Å）','Raman_ID_IG_reported_uncertainty':'Raman ID/IG作者±量','Raman_derived_crystallite_La_nm':'Raman派生晶粒尺寸（非独立测量）','XRD_d002_A':'XRD层间距（Å）','TEM_interlayer_spacing_nm':'TEM层间距'}
    if f in more:return more[f]
    extras={'Raman_IG_ID':'Raman强度比IG/ID','Raman_ID1_IG':'Raman强度比ID1/IG','water_contact_angle_deg':'水接触角','Boehm_total_acidic_groups_mmol_g':'Boehm总酸性基团','reported_product_yield_pct':'报告收率（基准另列）','electrode_height_mm':'电极高度','electrode_area_cm2':'电极面积','mass_loading_mg_cm2':'质量负载','printed_layer_count':'打印层数','DFT_micropore_peak_nm':'DFT微孔峰位','DFT_pore_diameter_nm':'DFT孔径','micro_to_meso_surface_area_ratio':'微孔/介孔面积比','micro_to_meso_pore_volume_ratio':'微孔/介孔孔容比','micropore_surface_fraction_pct':'微孔面积贡献','mesopore_surface_fraction_pct':'介孔面积贡献','micropore_volume_fraction_pct':'微孔孔容贡献','mesopore_volume_fraction_pct':'介孔孔容贡献','mesopore_to_BET_surface_area_ratio':'介孔/BET面积比','meso_to_micro_pore_volume_ratio':'介孔/微孔孔容比','micropore_to_BET_surface_area_ratio':'微孔/BET面积比'}
    if f in extras:return extras[f]
    return LABELS.get(f,f)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--build-status',choices=['creating','updating','complete','paused'],default='updating');args=ap.parse_args()
    target=ROOT/'文献提取进度/src/data.json';existing=json.loads(target.read_text('utf8'))
    pointer=json.loads((ROOT/'data/current_literature.json').read_text('utf8'));folder=ROOT/pointer['directory'];summary=json.loads((folder/'summary.json').read_text('utf8'))
    now=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(timespec='seconds');queries={}
    def group(r):return r.get('source_family_group_v23',r['source_group'])
    def query(key,rows,tables,sql,definition,caveats=()):
        queries[key]=dict(rows=rows,source=dict(label='本地已核验文献证据层 '+pointer['version'],executedAt=now,tables=tables,sql=sql,
          files=[{'name':pointer['database_file']},{'name':'summary.json'},{'name':'verification.json'}],
          metricDefinitions=[dict(field='count',label='计数口径',definition=definition)],caveats=list(caveats),
          evidenceFlow=['读取当前文献层指针并核验SQLite SHA256。','只读API/SQL生成所列完整快照行；不联网刷新原文，不写回数据库。','筛选与导出保留相同记录、单位和限定；工程核验不解除科学冻结。']))
    cycle_pointer=json.loads((ROOT/'data/current_database.json').read_text('utf8'))
    cycle_folder=ROOT/cycle_pointer['version_directory']
    with open_database() as cycling:
        main_rows=cycling.fetch('reported_3e').rows
        two_rows=cycling.fetch('reported_2e').rows
        all_years_3e=cycling.fetch('reported_3e_all_years').rows;all_years_2e=cycling.fetch('reported_2e_all_years').rows
        current_byid={r['endpoint_id']:r for r in main_rows+two_rows+all_years_3e+all_years_2e}
        new_admissions=[dict(r,source_year_display=str(r['source_year']),electrolyte_label=f"{r['concentration_mol_L']:g}M {r['electrolyte']}",profiles=', '.join(r['admission_profiles_v22']),profile_label=('跨年份3E'if r['system']=='3E'else'跨年份2E')if r['source_year']<2023 else'原队列及跨年份2E',review_note='原图86；摘要87/结论89保留' if r['endpoint_id']=='v22:COT_CDAP800350_2E_C5000' else '自身循环与匹配条件逐测试核定') for r in current_byid.values()if r.get('literature_candidate_id_v22')]
        cycle23=[dict(r,source_year_display=str(r['source_year']),electrolyte_label=f"{r['concentration_mol_L']:g}M {r['electrolyte']}",profile_label='仅跨年份3E'if r['source_year']<2023 else'原年份及跨年份2E',family_label='Tondolo原文及明确复用前作'if group(r).startswith('family:')else'本论文DOI组',review_note='原ID晋升用途；保留2021年限历史'if r.get('promoted_existing_endpoint_v23')else'新端点；同家族全部任务一起留出')for r in current_byid.values()if r.get('literature_candidate_id_v23')]
        cycle24=[dict(r,source_year_display=str(r['source_year']),electrolyte_label=f"{r['concentration_mol_L']:g}M {r['electrolyte']}",profile_label='仅跨年份3E',feature_note='N/O竞争冻结；Raman0.91及BET/孔容可用',window_basis='同盐自身GCD＋共同协议',source_weight_label='同来源两行各0.5')for r in current_byid.values()if r.get('literature_candidate_id_v24')]
        masks24=[dict(field_name=r['field_name'],raw_values=' / '.join(f'{v:g}'for v in sorted({x['value']for x in r['record']['raw_reports']})),canonical='空值'if r['record']['canonical_value']is None else str(r['record']['canonical_value']),status='标签竞争未解决；循环用途不解除特征冻结',material='CF-HPC-2')for r in cycling.feature_conflicts_v24()]if hasattr(cycling,'feature_conflicts_v24')else[]
        cycle25=[dict(r,source_year_display=str(r['source_year']),electrolyte_label=f"{r['concentration_mol_L']:g}M {r['electrolyte']}",profile_label='普通2E及跨年份2E'if r['system']=='2E_symmetric'else'普通3E及跨年份3E',review_note='原图保持率79.3/CE65；正文角色异文保留'if r['system']=='2E_symmetric'else'原图99.2与方法10A/g；比较表99@1A/g保留',feature_note='BET1348.5工作值；摘要1348.9留证，器件约5mg'if r['system']=='2E_symmetric'else'BET2214.5精度值；XPS百分比基准未知，标准通道空')for r in current_byid.values()if r.get('literature_candidate_id_v25')]
        cycle26=[dict(r,old_current='未定位（旧审查漏读）',current_basis='正文P11明确恒流循环10A/g',status='现有端点补正准入；非新实验')for r in current_byid.values()if r.get('review_disposition_v26')]
        residue27=cycling.fetch('reported_2e_residue').rows;approx27=cycling.fetch('reported_2e_approx').rows
        cycle27=[dict(r,scope='含灰/Al(OH)₃残留用途，普通主集不纳入',baseline='作者保持率初始参照；精确圈号未报',window_basis='同电池压片GCD适用0～1V程序',current_basis='原文水系循环3A/g；物理质量分母未知',original=cycling.holds(r['endpoint_id']))for r in residue27 if r.get('review_disposition_v27')]
        residue27_cohorts=[dict(profile=p,rows=len(rr),sources=len({group(r)for r in rr}),scope='含报告无机组分，普通主集之外'if p=='reported_2e_residue'else'含上述残留集及既有近似标签；两视图嵌套')for p,rr in [('reported_2e_residue',residue27),('reported_2e_approx',approx27)]]
        cycle28=[dict(r,scope='仅跨年份2E；2023—2026主集不增加',window_basis='实际图8(a)同器件GCD程序0～1V',baseline='作者初始电容；精确参照圈号未报',mass_basis='作者报告5A/g；物理分母未知')for r in all_years_2e if r.get('review_disposition_v28')]
        links={r['candidate_id']:r for r in cycling.literature_links()} if hasattr(cycling,'literature_links') else {}
        observation_count=len(cycling.fetch('all_review').rows)
    cycle_summary=json.loads((cycle_folder/'summary.json').read_text('utf8')) if (cycle_folder/'summary.json').exists() else {}
    with open_literature_database() as db:
        facts=db.facts();caps=db.capacitances()
        auxiliary=[]
        task_names={'3e':'三电极水系比电容','2e_device':'双电极水系器件比电容','native_mineral_3e':'天然矿物残留碳三电极','2e_author_factor2':'双电极作者两倍系数'}
        for profile in PROFILES:
            subset=db.auxiliary_feature_rows(profile)
            for r in subset:r['task']=task_names[profile]
            auxiliary.extend(subset)
        eligible={r['observation_id'] for r in auxiliary}
        eligible12={r[0]for r in db.connection.execute('select observation_id from purpose_reviews_v12 where eligible=1')}
        eligible13={r['observation_id']for r in db.template_residue_gcd_inputs()}
        eligible19={r[0]for r in db.connection.execute('select observation_id from purpose_reviews_v19 where eligible=1')}
        eligible20={r[0]for r in db.connection.execute('select observation_id from purpose_reviews_v20 where eligible=1')}
        eligible24={r[0]for r in db.connection.execute('select observation_id from purpose_reviews_v24 where eligible=1')}
        eligible23={r[0]for r in db.connection.execute('select observation_id from purpose_reviews_v23 where eligible=1')}
        eligible22={r[0]for r in db.connection.execute('select observation_id from purpose_reviews_v22 where eligible=1')}
        decisions20={(r['material_key'],r['field_name']):json.loads(r['record_json'])for r in db.connection.execute('select *from material_feature_decisions_v20')}
        eligible17={r['observation_id']for target in ['reported_aqueous_3e_GCD_capacitance','reported_aqueous_2e_factor2_Cs','reported_organic_2e_factor4_Cs']for r in db.batch17_inputs(target)}
        for r in facts:r.update(parameter=label(r['field_name']),quantity=r['value'],evidence=r['locator'],status_label=('未检出（ND），限值未知，不填0' if 'not_detected' in r['review_status'] else ('原印数字格式异常，待核' if 'malformed' in r['review_status'] else ('低于误差，空值' if 'censored' in r['review_status'] else '原文横杠/未报告，不填0'))) if r['value'] is None else ('冲突冻结' if 'conflict' in r['review_status'] else '作者近似报告，非精确值' if 'approximate' in r['review_status'] else '已提取，按用途调用'))
        for r in facts:
            if r.get('numeric_details_v22'):
                r['quantity_label']=r['raw_value']
                if 'ambiguous'in r['review_status']:r['status_label']='原值保留；单位/基准/方法未定，矩阵掩码'
            r['quantity_label']=r['raw_value']if r.get('numeric_details_v19')else('—'if r['value']is None else r['raw_value'])
            if r.get('numeric_details_v19'):
                kind=r['numeric_details_v19']['kind']
                if kind=='censored_author_limit':r['status_label']='作者检出上限，点值为空，不填0'
                elif kind=='ambiguous_printed_decimal_spacing':r['status_label']='原印小数点空格歧义，点值为空'
                elif kind=='author_mean_with_reported_uncertainty':r['status_label']='作者均值及±量，类型见方法与证据'
            if r.get('numeric_details_v20'):
                r['quantity_label']=r['raw_value']
                if r['numeric_details_v20']['kind']=='author_mean_with_reported_uncertainty':r['status_label']='作者均值及±量，类型见测法'
                decision20=decisions20.get((r['material_key'],r['field_name']))
                if decision20:r['status_label']='原值保留；标准字段冻结'if decision20['selected_value']is None else'原值保留；工作值依证据选定'+str(decision20['selected_value'])
                if 'attribution_risk'in r['review_status']:r['status_label']='作者XPS原子值；测法归属风险，可选特征掩码'
        des_rows=[]
        for des_target,task in [('retention','DES保持率均值'),('capacitance','DES首圈比电容均值')]:
            for row in db.des_reported_inputs(des_target):
                row.update(task=task,target_unit='%' if des_target=='retention' else 'F/g',window_label='0～1 V（自身GCD＋共同协议）',purpose_status='已审独立DES用途；非普通水系循环成员')
                des_rows.append(row)
        des_ids={r['observation_id'] for r in des_rows}
        for r in caps:
            cond=r['conditions'];area_current=cond.get('reported_current_mA_cm2')
            current_label=f'{area_current:g} mA/cm²' if area_current is not None else (f"{r['current_A_g']:g} A/g" if r['current_A_g'] is not None else '—')
            basis=cond.get('capacitance_basis','author_reported')
            r.update(quantity=r['value'],evidence=r['locator'],current_label=current_label,basis_label={'author_single_electrode_Cs_factor4_of_same_device_Ccp':'同器件单电极换算','device_reported_Ccp':'器件','device_total_two_electrode_active_mass':'器件总活性质量','device_total_two_electrode_mass':'器件总质量','single_working_electrode':'单工作电极','single_working_carbon_electrode':'单工作碳电极','printed_working_electrode_area':'打印电极面积','author_factor2_Csp_mass_scope_not_unified':'作者两倍系数（单独目标）','author_hybrid_device':'混合器件作者口径'}.get(basis,'作者报告'),status_label='辅助比电容用途已核定' if r['observation_id'] in eligible else ('未报告' if r['value'] is None else ('竞争证据冻结' if 'conflict' in r['status'] else ('原图近似读数，非精确标签' if 'approximate_figure' in r['status'] else '已提取，其他用途待核'))))
            if r['observation_id'] in des_ids:r['status_label']='已审：独立DES首圈均值用途'
            if 'current_binding_decision' in r:r['status_label']='电流依原图/图注选0.1；正文原0.01保留'
            if r['doi']=='10.3390/nano16040260':r['status_label']='商业参考，非生物质样品' if r['sample_name']=='reference_commercial_RC' else '作者2m口径，未拼共享目标' if r['method']=='GCD' else 'EIS汇总/单件分存，统计见对账'
            if r['doi']=='10.1016/j.heliyon.2024.e32915':r.update(status_label='自身复述，不增加物理实验' if 'repeat' in r['status'] else '作者2E归一化未报告，分口径保存',basis_label='作者2E归一化未报告')
            if r['doi']=='10.3390/gels10010082' and r['system']=='2E_symmetric':r['basis_label']='作者单电极材料等效口径'
            if r['doi']=='10.1039/d2ra02141b' and r['unit']=='F/cm3':r['basis_label']='Cg×假定密度的体积口径'
            if r['doi']=='10.1039/d0ra09182k':r['basis_label']={'author_Cs_factor4':'作者Cs=4Cd','author_reported_Cd':'作者器件Cd，质量范围另记'}.get(basis,'作者报告，方法竞争保留')
            if r['observation_id']in eligible12:r['status_label']='已核定：独立体积/Cs/Cd报告用途'
            if r['observation_id']in eligible13:r['status_label']='已核定：ZnS/SiO₂残留独立用途'
            if r['doi']=='10.1039/d6ra08120g':r['status_label']='商业原料来源未核实，仅方法参考；±统计定义未知'
            if r['doi']=='10.1039/d5ra02129d'and 'repeat'in r['status']:r['status_label']='同文复述，不增加独立测试'
            if r['doi']=='10.1039/d6ra04144b'and 'repeat'in r['status']:r['status_label']='同文复述，不增加独立测试'
            if cond.get('extraction_batch')=='v14':r['status_label']='标记遮挡：仅区间，点标签空'if r['value']is None else'糠醛渣有界用途：原图近似值，非作者精确点'
            if cond.get('extraction_batch')=='v15':r['status_label']='循环10000圈后电容，非新鲜标签'if cond.get('target_stage')=='post_10000_cycles'else'SI复述，关联同一标称工况'if cond.get('report_kind')=='repeat_SI_same_test'else'自身3E GCD报告工况用途已核定'
            if cond.get('extraction_batch')=='v16':r['status_label']='原图有界近似：显式读图用途，旧普通队列不变'
            if cond.get('extraction_batch')in ['v17','v19']:r['status_label']='本批分用途工况已核定'if r['observation_id']in eligible17|eligible19 else'自身复述或竞争报告；不重复/直接准入'
            if cond.get('extraction_batch')=='v20':
                r['status_label']='已核定：分方法/材料/作者口径用途'if r['observation_id']in eligible20 else'自身复述、竞争或方法未选；不计用途输入'
                r['basis_label']={'CT_over_total_two_electrode_active_masses_2m':'CV器件总活性质量2m','I_dt_over_mworking_dV':'GCD作者工作电极质量','author_C_or_Cg_symbol_unselected_literal_Eq1_factor4_Eq2_factor2_m_each_electrode':'作者C/Cg符号未选，仅本来源表达','author_Csp_CV_integration_formula_not_stated':'CV作者Csp，积分式未明'}.get(basis,'作者报告口径，见证据')
            if cond.get('extraction_batch')=='v18':r['status_label']='遮挡：数值和数值界限均空，不代填'if r['value']is None else'有界近似报告：复述与作者锚点按用途去重'
            if cond.get('extraction_batch')=='v21':r['status_label']='稻壳前作样品重叠待核；图点仅供检查'if cond.get('source_overlap_pending')else'来源内作者容量近似；旧锚点按用途去重'
            if r.get('protocol_binding_decision_v21'):r.update(status_label='图注补正CV5mV/s；前作样品重叠待核',basis_label='CV Ct按正负极总活性质量')
            if cond.get('extraction_batch')=='v22':
                r['status_label']='已核定：分方法/材料/作者口径用途'if r['observation_id']in eligible22 else'图文竞争：保留作者247，当前工况冻结'
                if cond.get('material_scope')=='SAP_rich_mixed_waste_reference_not_ordinary_biomass':r['status_label']='SAP混合废物参考；独立用途，不进普通生物质'
                if r['doi']=='10.3390/molecules26237104':r['status_label']='CV10mV/s：含锰复合与无锰模板碳分目标'
                r['basis_label']={'raw_whole_sample':'作者原样品表达','ash_free_author_recalculation':'作者去灰折算，同一实验'}.get('ash_free_author_recalculation'if cond.get('same_experiment_recalculation')else'raw_whole_sample','作者原报')if r['doi']=='10.1039/d3ra00820g'else('作者2IΔt/(mΔV)，m的2E范围未定义'if r['doi']=='10.1039/d5ra00450k'and r['system']=='2E_symmetric'else'作者CV计算式未报告'if r['method']=='CV'else'作者单工作电极活性质量')
        for r in caps:
            if r['conditions'].get('extraction_batch')=='v23':
                r['status_label']='已核定：零Cu对照普通3E或含Cu独立用途'if r['observation_id']in eligible23 else'未报告，非零'if r['value']is None else'蜜瓜皮前作重叠待核'if r['doi']=='10.1002/cplu.202500342'else'M325同工况581.74/587.14竞争冻结'
                r['basis_label']='作者工作活性质量'if r['system']=='3E'else'作者单电极表达；器件质量范围未统一'
        for r in caps:
            if r['conditions'].get('extraction_batch')=='v24':
                r['status_label']='已核定：相应报告电容用途；非循环准入'if r['observation_id']in eligible24 else'1M/6M浓度争议：仅检查，不入矩阵'if r['doi']=='10.3390/polym15193976'else'介绍75未绑定电流，不补猜'if r['conditions'].get('intro75_unbound_context')else'自身复述或整数舍入表达，不重复扩样'
                r['basis_label']='工作电极作者质量口径；参比未知/争议保留'if r['system']=='3E'else'4IΔt/(正负极总活性质量×ΔV)'if r['doi']=='10.3390/nano12213804'else'作者2E电容，质量范围未统一'
        for r in facts:
            if r['review_status']=='qualitative_not_exact_numeric':r['status_label']='定性近1，精确值未给，不填1'
        query('material_facts',facts,['material_facts','materials','resolved_table_sources_v18','source_binding_corrections_v18','source_documents'],
          'SELECT f.*,m.doi,m.sample_name,r.path AS current_source_path,r.sha256 AS current_source_sha256,r.locator FROM material_facts f JOIN materials m USING(material_key) JOIN resolved_table_sources_v18 r USING(table_key); -- current API retains original_provenance_v17 when corrected',
          '材料×参数×自身表单元；受限值为null，不同测法不拼成一个参数。',['原始层不自动取得训练资格；独立辅助用途视图另行审查。source_path返回实际正文或SI。'])
        query('capacitances',caps,['capacitance_observations','materials','table_source_links'],
          'SELECT x.*,m.doi,m.sample_name,l.locator FROM capacitance_observations x JOIN materials m USING(material_key) JOIN table_source_links l USING(table_key);',
          '材料×方法×电解液×工况×自身报告表单元，不同配置、归一化和单位分开。',[f"{summary['capacitance_records']}报告含{summary['numeric_capacitance_values']}数值、4未报告（另有区间/遮挡）；复述、竞争、换算、参考和复合体系不能当独立样本相加。",'CV速率不当电流；面积电流不猜算A/g。辅助资格不等于循环保持率准入。'])
        query('auxiliary_inputs',auxiliary,['auxiliary_reported_GCD_v3','auxiliary_gcd_reviews_v3','material_facts','synthesis_stages_v3'],
          'SELECT * FROM auxiliary_reported_GCD_v3 ORDER BY purpose,source_group,sample_name,current_A_g;',
          '当前205条普通三电极、5条器件总质量、5条天然矿物残留碳三电极、6条旧作者两倍系数双电极，四目标分开。本批其它用途另列。',['四目标合计31个DOI组，普通3E30个；同论文各任务必须一起留出，不是泛化性能证明。','松木3行与既有循环及全样品特征同组，WET-1的0.1A/g争议247未进输入；Tondolo与前作另有显式家族隔离。','输入预检通过不表示循环准入或精度改善；当前原年份三电极循环主集45/33，无新拟合。'])
        query('des_inputs',des_rows,['purpose_reviews_v6','capacitance_observations','test_candidates','material_facts','figure_protocol_reviews_v6'],
          'db.des_reported_inputs("retention"); db.des_reported_inputs("capacitance") -- read-only API with explicit per-purpose review, selected facts and common own protocol',
          '同12个液态DES样品的两个独立均值目标，各12行；共1个DOI组，不是24次独立实验。',
          ['自身Table3＋各样品Figure10初圈0～1V GCD＋SI共同1A/g/30℃协议；不要求每圈均绘图。','作者±不是自动可解释的SD/SEM；ChCl:EG=1:2是组成，不是2M。','只通过单独DES报告均值用途，不加入普通水系循环集，只有一个来源无法构成跨来源验证；本批拟合0。'])
        table_sources={r['table_key']:dict(r) for r in db.connection.execute('select l.table_key,l.locator,d.path as source_path,d.sha256 as source_sha256 from table_source_links l join source_documents d using(document_key)')}
        eis=[dict(item['record'],doi=item['doi'],sample_name=item['sample_name'],**table_sources[item['table_key']]) for item in db.eis_fits()]
        query('eis_responses',eis,['outcome_observations_v3','table_source_links','source_documents'],
          'db.eis_fits() -- typed own SI TableS5 response records',
          '12样品×5个拟合参数=60响应；均值和作者±分开，不当预实验材料预测特征。',['SI称±s为拟合置信区间，未给置信水平，不猜95%或SD/SEM；Q和Wd保留作者量纲。'])
        peaks=[dict(item['record'],doi=item['doi'],sample_name=item['sample_name'],locator=item['locator'],source_path=item['source_path'],source_sha256=item['source_sha256']) for item in db.diffraction_peaks()]
        query('xrd_peaks',peaks,['diffraction_peaks_v6','table_source_links','source_documents'],
          'db.diffraction_peaks() -- own SI TableS4 peaks, original angstrom units',
          '两个自身样品各3峰，只有(002)峰绑定d002；全部6峰描述保存。',['5h的表3.7Å选作0.37nm，正文3.8Å异文保留；未将所有峰都当d002。'])
        query('palm_statistics',db.palm_statistics_audit(),['capacitance_observations','transcribed_rows','source_documents'],
          'db.palm_statistics_audit() -- compare author aggregate with arithmetic of listed same-source same-configuration reports',
          '4种碳×2种配置的8组统计对账；列表重算是派生核查，不覆盖作者均值/标准差，也不假定报告之间独立。',
          ['SI硬币列表19个PK700、7个PK700N，脚注18/8，均值也存在不符；原报告和明细并存，未假造解释。','e1 rep为重复测量；均值、单件和商业RC不拼成独立样本。'])
        condition_rows={}
        for item in db.palm_responses('electrical'):
            record=item['record'];key=(item['table_key'],record['row_ordinal'])
            if key not in condition_rows:
                context={k:v for k,v in record.items() if k not in ['metric','value','unit','reported_uncertainty','raw_value','column_ordinal']}
                condition_rows[key]=dict(context,table_key=item['table_key'],sample_name=item['sample_name'],source_path=item['source_path'],source_sha256=item['source_sha256'],locator=item['locator'],doi='10.3390/nano16040260',response_evidence={})
                condition_rows[key].update(assembly_label={'individual_coin':'单硬币器件','2S':'两器件串联','8S':'八器件串联','8P':'八器件并联'}[record['assembly']],grain_label={'aggregate_mean':'作者汇总均值','single_stack_report':'堆栈工况报告','individual_device_condition':'逐器件工况'}[record['statistical_grain']])
            condition_rows[key][record['metric']]=record['value']
            condition_rows[key][record['metric']+'_author_plus_minus']=record['reported_uncertainty']
            condition_rows[key]['response_evidence'][record['metric']]=dict(outcome_id=item['outcome_id'],raw_value=record['raw_value'],unit=record['unit'],column_ordinal=record['column_ordinal'])
        query('palm_electrical',list(condition_rows.values()),['outcome_observations_v3','extraction_metrics_v7','table_source_links','source_documents'],
          'db.palm_responses("electrical") -- pivot by(table_key,row_ordinal), keeping assembly, units, author uncertainty and printed IDs',
          '164个表格工况行：132单件工况+12汇总+12双串联+8八器件串并联；不是164个独立样品或循环标签。',
          ['安培A、法拉F与A/g、F/g分开，能量效率不是循环保持率；同工况多指标不计多个实验。','TableS5的22个器件都来自同一DOI，0.00F原印值保留；空值不填0，跨页样品号明确继承。','物理器件、作者均值及重复测量均整来源隔离。HNO3图文浓度、统计不符和串联循环角色仍冻结，无新拟合。'])
        scopes=[]
        class_labels={'biomass_carbon':'生物质碳','synthetic_PAN_carbon_control':'合成PAN碳对照','intentional_wood_biochar_PAN_composite':'有意木生物炭/PAN复合'}
        for item in db.material_scopes():
            if item['doi'] not in ['10.1016/j.heliyon.2024.e32915','10.3390/gels10010082']:continue
            r=item['scope'];scopes.append(dict(item,material_class=class_labels[r['origin_class']],route=r.get('aerogel_route','碳化/活化温度系列'),F_treatment=r.get('F_treated_biomass'),final_fraction_status='不适用：合成PAN对照' if r['origin_class']=='synthetic_PAN_carbon_control' else '未报告，不由前驱体配比反推' if 'composite' in r['origin_class'] else '单一生物质来源，未使用PAN'))
        query('new_material_scopes',scopes,['material_scopes_v8','materials','synthesis_stages_v3'],
          'db.material_scopes() -- 15new material registrations, classification/stage and precursor-vs-final composition kept separate',
          '4种洋葱壳碳、8种有意PAN/生物炭复合、3种合成PAN对照；不是15个主集准入样品。',
          ['type-I纤维/生物炭5:1与type-II溶液生物炭2wt%属于不同前驱体阶段，不推算最终碳比例。'])
        ratios=[dict(r['audit'],doi='10.1016/j.heliyon.2024.e32915') for r in db.ratio_audits()]
        query('onion_raman_audit',ratios,['ratio_audits_v8','material_facts','transcribed_rows'],
          'db.ratio_audits() -- printed ratios and direct arithmetic of reported intensities, no silent replacement',
          '3样品的原强度与报告比值对账；派生算术不当新测量。',['600℃ID/IG的1.2与0.831、850/950℃2D/G的0.07与0.711/0.681均保留，竞争比值冻结。'])
        classes={'original_biomass_research':'生物质原始研究','secondary_review_context':'综述二手背景','non_biomass_coal_reference':'非生物质煤基参考'}
        classifications=[]
        for item in db.source_classifications():
            r=item['decision']
            classifications.append(dict(doi=item['doi'],classification=classes[r['classification']],basis=r['basis'],remaining=r['remaining'],full_source_review_complete=False,source_sha256=r['source_sha256']))
        query('source_classifications',classifications,['source_classifications_v9','source_scope_decisions'],
          'db.source_classifications() -- own primary text, native article type and table citation scope, not title keywords',
          '本批四个来源的范围决定；两篇自身原始研究、一个综述和一个煤基参考，不等于四个新独立训练来源。',['24张原候选中14张自身主表、7张综述背景、3张煤基参考；另提取2张SI表。所有全文完成标记仍为0。'])
        series_scopes=[];material_stages={r['material_key']:r['material_stage'] for r in db.materials()}
        for item in db.material_scopes():
            if item['doi'] not in ['10.3390/molecules31132329','10.3390/polym15030663']:continue
            r=item['scope'];series_scopes.append(dict(doi=item['doi'],sample_name=item['sample_name'],material_stage=material_stages[item['material_key']],material_class={'biomass_carbon':'生物质碳','biomass_precursor':'生物质前驱体','unresolved_graph_sample_identity':'图中样品身份待核'}[r['origin_class']],aliases=', '.join(r.get('source_equivalent_aliases',[])),independence='登记名称不等于独立配方/来源'))
        query('systematic_material_scopes',series_scopes,['materials','material_scopes_v8','synthesis_stages_v3'],
          'db.material_scopes() filtered to Algae/Eucommia -- recipe stages and unresolved graph label preserved',
          '32个登记：11个藻类前驱体/碳登记、21个杜仲表/图名称；含一个EC550图名待核，不能当32个独立材料。')
        frozen=[];main_byid={r['endpoint_id']:r for r in main_rows}
        for item in db.legacy_feature_conflicts():
            r=item['record'];field='Raman_ID_IG' if r['field_name']=='Raman_ID_IG' else 'XPS_N_at_pct';facts=db.facts(doi='10.3390/molecules31132329',sample=r['sample_name'],field=field)
            table=next(f for f in facts if f['xml_id']=='molecules-31-02329-t004');graphic=next(f for f in facts if f['xml_id']=='Fig3_Raman_XPS')
            selected=main_byid[r['endpoint_id']][r['field_name']];assert selected is None
            frozen.append(dict(r,doi='10.3390/molecules31132329',parameter=label(field),table_value=table['value'],figure_value=graphic['value'],selected_value=selected,selected_display='空值（冲突冻结）',unit=table['unit'],source_path=table['source_path'],figure_path=graphic['source_path'],table_locator=table['locator'],figure_locator=graphic['locator']))
        query('current_feature_freezes',frozen,['legacy_feature_conflicts_v9','feature_freezes_v21','cycling_API.fetch(reported_3e)'],
          'db.legacy_feature_conflicts(); current cycling v0.23 fetch -- v0.21 null freezes preserved in current row and material matrices',
          '5条既有循环记录的15个特征选值冻结；两个氮字段是兼容表示，不是两个独立实验；标签、成员、来源权重保持。',['图表双方原值和旧选值保留，不填0、不择高值或覆盖旧模型。缺失变化不等于精度改善。'])
        arithmetic=[dict(r['record'],doi=r['doi'],audit_id=r['audit_id']) for r in db.qualification_audits()]
        query('series_arithmetic_audits',arithmetic,['qualification_audits_v9','transcribed_rows'],
          'db.qualification_audits() -- 37 rate ratios,16 cost sums,6 repeated-condition receipts',
          '倍率比值/成本合计是印刷数值算术检查，不能代替新测量或作者勘误；6条同配方材料复述不重复增加事实。',['比值按印刷精度区间判断，原表保持率仍原样保存；CV倍率、GCD倍率和循环保持率分开。'])
        curve_rows=[]
        for item in db.sampled_curves():
            r=item['reading'];curve_rows.append(dict(r,reading_id=item['reading_id'],doi=item['doi'],sample_name=item['sample_name'],source_path=item['source_path'],source_sha256=item['source_sha256'],x_kind={'plotted_cycle_coordinate':'循环图坐标 N','scan_rate_mV_s':'扫描速率 mV/s','reported_current_A_g':'报告电流 A/g'}[r['x_name']],error_kind=('遮挡标记8px范围：仅区间，不填中点'if r['y_value']is None else'原图4px读数界限：非实验误差')if r.get('extraction_batch')=='v14'else'标记像素范围＋2px校准界限；非统计置信区间'))
        query('bounded_curve_samples',curve_rows,['curve_samples_v8','source_documents','curve_samples.json'],
          'db.sampled_curves() -- source images, axes, pixel extents and uncertainty preserved',
          '当前20面板/68曲线组共439捕获：429数值、2仅区间、8遮挡；重复图与作者锚点另行去重，不能当独立实验。',
          ['近似图像读取与作者精确报告分开；横轴分别是圈坐标、电流或扫描速率，不拼为一个工况。','原图误差由局部标记高度和校准像素给出，不假称SD、SEM或95%CI；同DOI所有曲线/标签整组隔离。'])
        cycle_rows=[dict(r,cycle_coordinate=r['x_value'],specific_capacitance_F_g=r['y_value'],sample_label='COH（550℃未活化）' if r['sample_name']=='COH_550C' else 'GLC-OH '+r['sample_name'][3:6]+'℃') for r in curve_rows if r['x_name']=='plotted_cycle_coordinate']
        query('onion_cycle_curves',cycle_rows,['curve_samples_v8','Onion_SI_image2.jpeg'],
          'SELECT reading_json FROM curve_samples_v8 WHERE document_key="Onion_SI_cycle"; -- 4curves sampled at7plotted coordinates',
          '2 A/g下绝对电容C(F/g)随图中循环坐标变化，不是已经归一化的保持率。',
          ['图点近似，误差可在有界图采样表/来源预览中查；所选坐标不是作者已确认的第1圈参照。','正文<95%与绝对C(N)仍未协调；未把图中电容或任意起点转换成精确保持率。'])
        custom=db.composite_cycle_inputs()
        query('composite_cycle_inputs',custom,['purpose_reviews_v8','test_candidates','material_facts','synthesis_stages_v3'],
          'db.composite_cycle_inputs(); db.composite_cycle_matrix() -- explicit separate PAN/biochar 2E reported-purpose contract',
          '复合体系循环用途1条/1DOI；不加入普通生物质循环主集，不构成跨来源检验。',
          ['91%保持率与53.5%CE分开；X不含CE或其它同测试响应。','自身GCD＋同样品共同协议0～1V/10A/g/10000圈；未知质量分母和精确初始下标按既有报告用途规则保留。','500℃生物炭/900℃PAN/800℃最终活化是不同阶段；最终组分未知不填0。未执行新拟合。'])
        queue=[dict(r) for r in db.connection.execute('select * from raw_table_queue order by review_state,previous_role,table_id')]
        for r in queue:r.update(state='未进入本流程处理' if r['review_state']=='automatic_candidate_unreviewed' else '已处理指定范围',role='比较/汇总候选' if 'comparison' in r['previous_role'] else '自身/上下文待核')
        query('table_queue',queue,['raw_table_queue'],'SELECT * FROM raw_table_queue ORDER BY review_state,previous_role,table_id;',
          '一个自动候选可能合并两张真实表，不能等同样本。',['已处理只指声明范围，不代表整篇或全部参数完成。','历史725项材料属性另存，其中171项同源线索尚不等于表单元匹配。'])
        state_names={'has_current_observation_not_full_utilization_proof':'匹配现有观察','native_content_without_normalized_DOI_observation_match':'原生内容未匹配观察','metadata_or_non_native_content_needs_identity_review':'身份/内容待核'}
        states=[dict(category=state_names[r[0]],count=r[1]) for r in db.connection.execute('select work_state,count(*) from identity_inventory group by work_state')]
        for r in states:r['chart_label']={'匹配现有观察':'已匹配','原生内容未匹配观察':'有原生未匹配','身份/内容待核':'身份待核'}[r['category']]
        query('identity_states',states,['identity_inventory'],'SELECT work_state,COUNT(*) AS count FROM identity_inventory GROUP BY work_state;',
          '初始目录身份匹配盘点，包括版本/SI/综述/参考体系；不是当前全部提取完成度或独立合格论文数。',['该图保留初始基线，当前逐来源/单元审查进度另计；不以DOI匹配推断全文已利用。'])
        sql='SELECT s.doi,s.title,COUNT(DISTINCT m.material_key) AS materials,COUNT(DISTINCT f.fact_id) AS cells,COUNT(DISTINCT CASE WHEN f.value IS NOT NULL THEN f.fact_id END) AS numeric_facts FROM reviewed_sources s LEFT JOIN materials m USING(doi) LEFT JOIN material_facts f USING(material_key) GROUP BY s.doi;'
        sources=[dict(r) for r in db.connection.execute(sql)]
        new_dois={'10.1021/acsomega.5c06396','10.1021/acsomega.5c10175','10.1021/acsomega.5c03461','10.1002/advs.202206320'}
        for r in sources:r.update(batch='批次08' if r['doi'] in ['10.1016/j.heliyon.2024.e32915','10.3390/gels10010082'] else '批次07' if r['doi']=='10.3390/nano16040260' else '批次05＋06 SI' if r['doi'] in ['10.1016/j.isci.2026.117248','10.1021/acsomega.3c00816'] else '批次05' if r['doi']=='10.1021/acsomega.5c05285' else '批次04' if r['doi'] in ['10.1021/acsomega.5c08826','10.1002/cplu.202400408','10.1002/smsc.202500174'] else ('批次03' if r['doi'] in new_dois else ('批次02' if r['doi'] in ['10.1021/acsenvironau.3c00048','10.3390/molecules29225413'] else '批次01')),scope='温度系列/EDAX/有界曲线；<95%和90/100min冲突保留' if r['doi']=='10.1016/j.heliyon.2024.e32915' else 'PAN对照/8复合体系分开；独立循环用途1条，非普通主集' if r['doi']=='10.3390/gels10010082' else '原料/4种碳/商业参考分开；EIS与串并联另计，曲线未全提取' if r['doi']=='10.3390/nano16040260' else '合成碳方法参考' if r['doi']=='10.3390/molecules29225413' else ('复合碳独立用途' if r['doi']=='10.1002/advs.202206320' else ('天然CaP与MnO2混合器件分用途' if r['doi']=='10.1002/cplu.202400408' else '部分材料/测试已核定，整篇未完成')))
        classification_bydoi={r['doi']:r for r in classifications}
        for r in sources:
            if r['doi'] in classification_bydoi:r.update(batch='批次09',scope=classification_bydoi[r['doi']]['classification']+'；'+classification_bydoi[r['doi']]['remaining'])
            if r['doi'] in ['10.1039/c7ra11475c','10.1021/acsomega.3c04692','10.3390/nano14080686','10.1039/c9ra01255a']:r.update(batch='批次10',scope='自身材料/多工况与指定曲线核读；全波形/形貌及其它图值尚未全提取')
            if r['doi'] in ['10.1039/d6ra02137a','10.1039/d5ra01262g','10.3390/ma17133233','10.3390/ma14216592']:r.update(batch='批次11',scope='自身表/SI/印字与协议；Tondolo前作复用、GP标签竞争与WH未知循环电流分别处置，未全文完成')
            if r['doi'] in ['10.1039/d2ra02141b','10.1039/d0ra09182k']:r.update(batch='批次12',scope='自身主表及椰壳SI六表；体积/质量与Cs/Cd分开，N/O和同工况竞争冻结；剩余波形待提取')
            if r['doi']in ['10.1039/d5ra02129d','10.1039/d6ra04144b','10.3390/polym16233421','10.1039/d6ra08120g']:r.update(batch='批次13',scope='商业原料来源未核实，仅方法参考；9配方分开，不进入生物质训练'if r['doi']=='10.1039/d6ra08120g'else'全正文/自身表及可得SI、指定印字核读；普通3E/残留组分分用途，剩余波形继续')
            if r['doi']=='10.3390/polym16233421':r.update(batch='批次13＋14',scope='48标称倍率工况，46点标签/2仅区间；原图注记争议保留；12图审查但其余波形仍待提取')
        batch10=[dict(doi=r['doi'],classification='生物质原始研究',tables=len(r['record']['units']),scope='自身指定表/正文数值；他引比较分开',remaining='完整CV/GCD/吸附/EIS波形、形貌量化及剩余图值待提取')for r in db.batch10_sources()]
        query('batch10_sources',batch10,['source_reviews_v10','table_source_links'],'db.batch10_sources()','四个自身原始研究范围审查；15主表候选含2模型参数表，另2张SI参数表，不当实验表相加。',['四来源均未声称全文完成；同行模型数值与材料事实分库存放。'])
        peer=db.peer_model_review()
        peerrows=[dict(doi=peer['doi'],target='比电容 F/g',samples='200余样本；不是200篇论文',split='90/10随机；未报告按来源拆分',validation_R2=peer['reported_validation_r2'],data_status='公开包有9页PDF及原图；未取得所称XLSX',parameters=len(db.peer_model_cells()),limits='与保持率来源留出误差不可比；Rs需预测时可得；未检出N不填0')]
        query('peer_model_review',peerrows,['peer_model_reviews_v10','peer_model_cells_v10'],'db.peer_model_review(); db.peer_model_cells()','原论文方法审查与240参数数值；不计本项目实验样本或真实拟合。',['架构表述不一致、归一化是否仅拟合训练集未明；8预测均值287.75与作者289保留；不承诺复现同分数。'])
        audits10=[dict(doi=r['doi'],audit_id=r['audit_id'],kind=r['record']['kind'],details=json.dumps(r['record'],ensure_ascii=False))for r in db.batch10_audits()]
        query('batch10_audits',audits10,['numerical_audits_v10'],'db.batch10_audits()','28项孔分量/百分比/文献模型算术核验；不是28次独立实验。')
        sources11=[dict(doi=r['doi'],scope='自身指定表/SI/原图印字与正文',remaining='剩余波形、形貌与正文图值未全部完成')for r in db.batch11_sources()]
        query('batch11_sources',sources11,['source_reviews_v11'],'db.batch11_sources()','四篇原始研究/15材料；18主表候选含6混合比较表，另2自身SI表；不能当18个新实验。')
        decisions11=[dict(doi=r['doi'],decision_id=r['decision_id'],decision=r['record']['decision'])for r in db.batch11_decisions()]
        query('batch11_decisions',decisions11,['decisions_v11'],'db.batch11_decisions()','8项逐来源处置，区分已解标签竞争、方法限定、仍缺循环电流及前作复用。')
        relations11=[dict(doi=r['doi'],related_doi=r['related_doi'],family=r['record']['isolation_group'],basis=r['record']['basis'])for r in db.source_relations()]
        query('source_families',relations11,['source_relations_v11'],'db.source_relations(); db.isolation_group(doi)','既有明确复用与样品重叠待核关系分别保留状态，并在验证中共同留出；同家族不是确认全部实验重复。')
        audits11=json.loads((ROOT/'文献全量利用复核_20261026/批次11_青豌豆皮水葫芦红茶与Tondolo/quantity_audits.json').read_text('utf8'))
        for r in audits11:
            r['status_label']='协议或拟合不一致，仍未解决'if r['status'].startswith('unresolved')else'原印精度保留，不归一化'
            r['kind_label']='拟合容量与可用染料量核对'if r['kind']=='fitted_Qe_vs_stated_available_dye'else'Raman分峰百分比合计'
            r['model_label']={'pseudo_first_order':'准一级动力学','pseudo_second_order':'准二级动力学'}.get(r.get('model'),'—')
        query('batch11_quantity_audits',audits11,['quantity_audits.json','transcribed_rows'],'C0_mg_L * volume_L / adsorbent_g; compare to author fitted Qe, not new measurement','6项吸附拟合与给定物料衡算矛盾，另2项Raman百分比合计；算术核验不改原报告。')
        query('batch12_sources',[dict(doi=r['doi'],scope='自身主表/正文、椰壳SI全部表及指定原图',remaining='剩余波形未全提取；原选四篇已在第十三批提取指定范围')for r in db.batch12_sources()],['source_reviews_v12'],'db.batch12_sources()','两篇指定范围；10登记含1身份未决，不是10个确定样品。')
        query('batch12_decisions',[dict(doi=r['doi'],decision_id=r['decision_id'],decision=r['record']['decision'])for r in db.batch12_decisions()],['decisions_v12'],'db.batch12_decisions()','13项方法/身份/竞争及用途处置；冻结与已裁决分开。')
        targets12={'3e_volume':'3E体积电容（作者假定密度）','2e_aqueous_Cs':'水系2E作者Cs','2e_aqueous_Cd':'水系2E作者Cd','2e_ionic_Cs':'纯离子液体2E作者Cs','2e_ionic_Cd':'纯离子液体2E作者Cd'}
        inputs12=[]
        for key,title in targets12.items():
            for r in db.batch12_inputs(key):
                cond=r['conditions'];inputs12.append(dict(doi=r['doi'],sample_name=r['sample_name'],task=title,quantity=r['target_value'],unit=r['target_unit'],current_A_g=r['current_A_g'],electrolyte=r['electrolyte'],collector=cond.get('current_collector','Ni_foam'),separator=cond.get('separator','—'),voltage_lower_V=cond.get('voltage_lower_V'),voltage_upper_V=cond.get('voltage_upper_V'),source_group=r['source_family_group'],physical_test_group=cond['physical_test_group'],evidence=r['locator']))
        query('batch12_inputs',inputs12,['purpose_reviews_v12','capacitance_observations','material_facts'],'db.batch12_inputs(target); each target separately','29个表达行对应15个物理测试组；Cs/Cd是同一测试两种表示，体积与质量共享来源及测试隔离。',['5目标每项都仅1 DOI，单独不能验证跨论文泛化；当前未拟合。','同标称工况AC5竞争不选；离子液体浓度不填1M；电流分母未知保留。'])
        query('batch13_sources',[dict(doi=r['doi'],classification='商业原料未核实，方法参考'if r['doi']=='10.1039/d6ra08120g'else'生物质原始研究，按实际残留分用途',scope='全部正文/主表、可得SI全部页及指定原图印字',remaining='剩余曲线、形貌及其它数值未全部提取；没有整篇完成标记')for r in db.batch13_sources()],['source_reviews_v13'],'db.batch13_sources()','四个声明范围，含一个商业参考；不称四篇均取得生物质训练资格。')
        decisions13={'BET_working_value':'MK9详细自身表/正文1348.5作工作值，摘要1348.9留证；不声称勘误。','cycle_roles':'Fig10a右轴保持率79.3%、左轴CE65%；正文错称79.3CE保留。循环2A/g、100000圈、0～1.2V。','device_identity':'MK9同碳双电极装配明确；模板残留asymmetric/ZS_GP不另造样品。','seven_electrolytes':'实际7电解液柱全部保留；未报电流不猜；EMIM-BTI图44.7/正文46竞争冻结。','EDS_identity':'Fig4h的EDS属于MK10；百分比基准未知，50.15nm为单图颗粒尺寸。','cycle_actual_figure':'皮革原图99.2%、图注与方法10A/g；比较表99%@1A/g异文保留，正式准入待做。','EDS_XPS_basis':'表中括号外EDS/内XPS；未标at/wt，不填标准原子%。','activation_stage':'400℃1h预碳化与600/700/800℃1h活化分阶段；额外400℃措辞不自动累加。','SI_scaled_EIS':'SI缩放列按原头保存；A8的1.o是异常印字，保持空，不填1.0。','final_ZnS':'APS最终样品ZnS仍在；Zn1.19wt%为ICP-OES、S19.26wt%方法未定；残留用途另列。','rate_not_cycle':'66.7/80.7为倍率保持率，非循环寿命；80.7与点值算术80.894%并存。','contact_direction':'糠醛渣正文8.7/34.2与Fig5标签相反；两套值保留，两材料标准接触角冻结。','raw_and_caption':'原料ad/daf不传给最终碳；表3虽误题原料分析，实际Rs/Rct/Wd按EIS响应存。','origin_reference':'商业XFP01来源未报，仅方法参考；只测三配方BET，另六个不继承。','surface_IL_binder':'表面IL与实际1M KOH分开；PVDF溶液配比不填干粉80/10/10。','cycle_system_conflict':'作者声称2E但图用Hg/HgO带符号电位轴；实际器件窗口未知，3循环候选不准入。','dynamic_contact_ND':'接触角按0/3/6s分存；未检出B/F且限值未知不填0。','repeat_statistics':'均值±统计定义/n未报；同1A/g复述不当新测试，24报告仅21标称条件。'}
        query('batch13_decisions',[dict(doi=r['doi'],decision_id=r['decision_id'],decision=decisions13[r['decision_id'].removeprefix('LP13_')])for r in db.batch13_decisions()],['decisions_v13'],'db.batch13_decisions()','18项逐证据处置；有工作值选择，也有未决冻结，不全称解决。')
        residue13=[dict(doi=r['doi'],sample_name=r['sample_name'],value=r['value'],current_A_g=r['current_A_g'],electrolyte='6M KOH',window='−1～0 V，Hg/HgO',BET=r['material_features']['BET_surface_area_m2_g'],Zn=r['material_features'].get('ICP_OES_Zn_wt_pct'),purpose='ZnS/SiO₂残留独立用途；1DOI不可单独验证泛化',evidence=r['locator'])for r in db.template_residue_gcd_inputs()]
        query('residue13_inputs',residue13,['purpose_reviews_v13','material_facts','synthesis_stages_v3'],'db.template_residue_gcd_inputs(); db.template_residue_matrix()','4条自身GCD/2材料/1DOI；最终残留组分明确，不混普通3E。',['接触角冲突留空，未测Zn不填0；倍率保持率不当循环标签，无拟合。'])
        reference13=[dict(doi=r['doi'],sample_name=r['sample_name'],value=r['value'],current_A_g=r['current_A_g'],reported_plusminus=r['conditions'].get('reported_plusminus'),statistic='±定义与n未报'if r['conditions'].get('reported_plusminus')is not None else'表2重复/工况值',status='商业来源未知，仅方法参考；训练资格为否',evidence=r['locator'])for r in db.interface_reference_reports()]
        query('interface13_reference',reference13,['capacitance_observations','materials'],'db.interface_reference_reports()','24报告/21标称条件，独立物理重复数未知；不是新增生物质训练输入。')
        query('wetting13', [dict(r['record'],status='按时间保存；商业参考，不推未报基准')for r in db.wettability_series_v13()],['wettability_series_v13','material_facts'],'db.wettability_series_v13()','三参考配方各0/3/6s，共9个时间限定读数；与材料原始事实同源，不能重复计实验。')
        labels14={'author_exact':'作者正文精确值（4）','point_mixed':'点标签：4正文＋42读图','interval_mixed':'区间标签：48工况含2空点'}
        inputs14=[]
        for mode,title in labels14.items():
            for r in db.furfural_rate_inputs(mode):inputs14.append(dict(doi=r['doi'],sample_name=r['sample_name'],mode_label=title,current_A_g=r['current_A_g'],target_value=r['target_value'],lower=r['target_lower_bound'],upper=r['target_upper_bound'],quality={'author_reported_exact':'作者报告值；实验误差未报','bounded_figure':'原图近似点；4px读取界限','occluded_interval_only':'仅区间，点标签为空；不取中点'}[r['target_value_kind']],source_group=r['source_family_group'],observation_id=r['observation_id'],graph_observation_id=r['graph_observation_id'],physical_test_group=r['physical_test_group']))
        query('furfural14_inputs',inputs14,['purpose_reviews_v14','capacitance_observations','curve_samples_v8'],'db.furfural_rate_inputs(mode) for explicit author_exact/point_mixed/interval_mixed modes','98表达行对应同一48标称工况：46点模式含已存在4正文值，净新增42点条件；各模式不可相加。',['1DOI全部材料/工况整体留出；含ZnS/SiO₂残留用途，与普通碳用途分开。','2遮挡点只供区间损失；CSV空目标不填0或中点，界限不是SD/CI。'])
        current_query=queries['furfural14_inputs']['source'];current_query['files'].extend([{'name':'point_inputs_v14.csv'},{'name':'interval_inputs_v14.csv'}])
        primary14={r[0]for r in db.connection.execute('select reading_id from purpose_reviews_v14')}
        rate_plot14=[dict(r,graph_capacitance_F_g=r['y_value'])for r in curve_rows if r['reading_id']in primary14]
        query('furfural14_curve',rate_plot14,['curve_samples_v8','purpose_reviews_v14','Furfural14_Fig10'],'primary Fig10c/d readings with nullable y; retain gaps','8材料48标称工况，46原图数值/2区间；断线表示遮挡，不是模型预测或实验重复。',['原图4px界限与遮挡8px范围见源数据；图中不画区间中点，不跨空值连线。'])
        ratio14=[]
        for item in db.furfural_rate_audits():
            r=item['record'];ratio14.append(dict(r,sample_name=r['sample'],canonical_display='空（争议未解）'if r['canonical_rate_retention_pct']is None else f"{r['canonical_rate_retention_pct']:g}%",interval_lower=r['derived_figure_interval_pct'][0],interval_upper=r['derived_figure_interval_pct'][1],status_label='倍率注记与自身曲线不符'if r['sample']=='FR900'else'倍率注记与正文精细点值算术不同'if r['sample']=='PC900-0.1'else'在报告/图像精度范围相容'))
        query('furfural14_ratio_audits',ratio14,['rate_ratio_reviews_v14','curve_samples_v8'],'db.furfural_rate_audits()','8材料的倍率注记核查；FR900约46.2与79.3竞争，PC900-0.1精确报告算术异文保留，均非循环寿命。')
        query('furfural14_contributions',[dict(r['record'],status='印刷和101；不归一化'if r['record']['printed_sum_pct']==101 else'原印成对值保留')for r in db.furfural_contributions()],['contribution_pairs_v14','outcome_observations_v3'],'db.furfural_contributions()','5组CV贡献率；10原印响应不是保持率或材料预实验特征。')
        annotation14=[]
        for item in db.furfural_series_annotations():
            r=item['record'];v=(str(r['value'])+(' ± '+str(r['author_plusminus'])if 'author_plusminus'in r else''))if'value'in r else str(r['lower'])if r['lower']==r['upper']else f"{r['lower']}～{r['upper']}"
            annotation14.append(dict(annotation_id=r['id'],category='前驱体投料描述'if r['kind']=='precursor_recipe_property'else'XRD集体峰位'if r['kind']=='author_series_XRD_peak_assignment'else'FTIR作者归属',value_display=v,unit=r['unit'],scope_label='投料前ZnO，非最终碳孔径'if r['kind']=='precursor_recipe_property'else'作者集体样品范围；非独立逐样测量'if r['kind']=='author_series_XRD_peak_assignment'else'系列级作者归属；不推官能团含量',assignment=r.get('assignment',r.get('phase','')+' '+r.get('plane','')),evidence=r['locator'],source_path=item['source_path'],source_sha256=item['source_sha256']))
        query('furfural14_annotations',annotation14,['series_annotations_v14','source_documents'],'db.furfural_series_annotations()','18个集体/阶段限定注记；不复制为66个独立材料峰测量，不虚增材料数值。')
        figure_status14={1:'N₂吸附/脱附支线尚待提取',2:'SEM样品/尺度已核；不推粒径均值',3:'TEM 100/50nm尺度已核；不推孔径均值',4:'EDS仅分布图，无定量表；S测法仍未知',5:'图文角度对调；原值与冻结保持',6:'7个FTIR集体归属已存；谱线未全提取',7:'10个XRD集体峰位已存；不推相含量',8:'8个D/G与4中心原有值保留；谱线仍待提取',9:'20mV/s及8扫描速率CV波形仍待提取',10:'54倍率捕获已存，2仅区间；连续GCD仍待提取',11:'Nyquist波形仍待提取；作者拟合Wd差异保留',12:'5组成对贡献率已读，101不归一化'}
        query('furfural14_figures',[dict(figure='Fig'+str(r['figure_number']),review=figure_status14[r['figure_number']],source_path=r['record']['path'],source_sha256=r['record']['sha256'],completion='指定内容已核；整篇定量提取未完成')for r in db.figure_scope_reviews_v14()],['figure_scope_reviews_v14','source_documents'],'db.figure_scope_reviews_v14()','12图均已逐项审查；各图剩余波形单列，不能把全图检查说成全文提取完成。')
        decisions14={'FR900_rate_annotation':'FR900注记79.3与自身端点比约46.2%不符；标准倍率留空，保留双方。','PC900point1_rate_arithmetic':'80.7与正文114.32/141.32算术约80.894%竞争，宽图界不掩盖精细报告异文。','two_occluded_markers':'两个5A/g点被覆盖，只保留区间，不填中点、不进点回归。','contribution101':'5mV/s的72+29印刷和101，取整边界可相容；不归一化。','S_method':'EDS仅元素图；S19.26wt%方法未知，不能借ICPZn1.19wt%填补。','stage_and_control':'FR900明确未添加，配方比0有依据；ZnO30±10nm是前驱体，非最终孔径。','series_annotations':'10XRD+7FTIR+1前驱体为集体/阶段限定注记，不伪增独立样品。','remaining_scope':'全12图已审，N₂/CV/EIS/连续GCD及谱线仍待提取，原38待证保持。'}
        query('furfural14_decisions',[dict(decision_id=r['decision_id'],action=decisions14[r['record']['id']])for r in db.batch14_decisions()],['decisions_v14'],'db.batch14_decisions()','8项边界与争议处置，冻结与提取状态分开，未拟合。')
        input15=[];weights15=dict(zip(db.batch15_matrix()['observation_ids'],db.batch15_matrix()['sample_weight']))
        for r in db.auxiliary_gcd('3e'):
            if r['doi']not in ['10.3390/nano14100836','10.3390/nano12010122']:continue
            x=r['material_features'];input15.append(dict(doi=r['doi'],sample=r['sample_name'],current=r['current_A_g'],capacitance=r['value'],BET=x.get('BET_surface_area_m2_g'),XPS_N=x.get('XPS_N_at_pct'),XPS_O=x.get('XPS_O_at_pct'),Raman=x.get('Raman_ID_IG'),window=f"{r['conditions']['voltage_lower_V']:g}～{r['conditions']['voltage_upper_V']:g} V",reference=r['conditions']['reference_electrode'],weight=weights15[r['observation_id']],observation_id=r['observation_id'],source_group=db.isolation_group(r['source_group']),source_path=r['source_path'],source_sha256=r['source_sha256'],physical_test_group=r['conditions']['physical_test_group'],evidence=r['locator']))
        for r in input15:r['weight_label']=format(r['weight'],'.8g')
        query('batch15_inputs',input15,['capacitance_observations','auxiliary_gcd_reviews_v3','material_facts'],'db.auxiliary_gcd(3e) restricted to two v15 DOI;20 explicitly purpose-reviewed rows','20自身普通3E工况，花椒16/椰枣4；两论文整组留出，每来源在本批权重和1。',['SI复述及循环后电容不进入此表；其它8个花椒样品的曲线仍待提取。','椰枣参比工作值Ag/AgCl有正文SCE异文；未知质量分母保留作者A/g，不推算。'])
        components15=[]
        for item in db.batch15_components():
            r=item['record'];components15.append(dict(doi=r['doi'],sample=r['sample'],component=r['name'],energy=r['energy_eV'],absolute_at_pct=r['absolute_at_pct'],relative_area_pct=r['relative_envelope_pct'],basis='全表原子百分比'if r['absolute_at_pct']is not None else'C1s包络内面积百分比',status='表中0与拟合曲线争议'if'table_zero'in r['status']else'C组分和80.93/总C80.84争议'if'sum_C'in r['status']else'按原尺度保留',table_key=r['table_key'],source_group=r['source_group']))
        query('batch15_components',components15,['xps_components_v15','material_facts'],'db.batch15_components() with original absolute versus relative percentage fields','32个拟合分量表达：26全表at%、6C1s内%Area，不是32个独立样品。',['争议组分保留原0及原值，未归一化；元素总C/N/S/O独立保留。'])
        texts15=['XPS全表at%与包络比例分开；PAC碳组分和不强制归一化','表中零组分与原图拟合分量竞争，冻结组分而不抹去总S','原料成分限定原料阶段，不复制给最终碳','浆料4mg/实际约2mg；KOH1:1标为配方算术','表中孔值与原图Raman保留，XRD文字异文单列','作者Dunn解释及两段贡献报告分开，不修成更优值','真实2E循环不套3E窗口；SAC600图注异文保留','SI两自身复述去重、六他引行不作自身标签','方法和实图支持Ag/AgCl，正文SCE异文保留','DFT/DA体积与mode分开，不强行跨模型闭合','原子百分比与C1s面积分开；Raman近1不填精确1','初始碳化未知、球磨保留范围，涂层不当纯炭负载']
        spec15=json.loads((ROOT/'文献全量利用复核_20261026/批次15_花椒皮籽与椰枣叶/curation_spec.json').read_text('utf8'));labels15={r['id']:text for r,text in zip(spec15['decisions'],texts15)}
        decisions15=[dict(doi=r['doi'],decision_id=r['decision_id'],action=labels15[r['decision_id']],raw_action=r['record']['decision'])for r in db.batch15_decisions()]
        query('batch15_decisions',decisions15,['decisions_v15'],'db.batch15_decisions()','12项方法、阶段、重复及冲突处置；原38条待证未抵扣。')
        links15=[dict(candidate_id=r['candidate_id'],existing_endpoint=r['record']['existing_endpoint_id'],relation='同源PAC700循环已登记；本次转录不再计新端点',status='仅身份关联；未改变准入')for r in db.batch15_cycle_identity_links()]
        query('batch15_identity_links',links15,['cycle_identity_links_v15','test_candidates','cycling_v0_25'],'db.batch15_cycle_identity_links()','PAC700与旧端点同一循环报告；SAC600候选仍需自身器件电压，不拆成新论文。')
        rate16=[]
        for mode,label16 in [('author_exact','作者报告值（20总工况）'),('point_mixed','报告值＋读图（95总工况）'),('figure_only','仅图主表达（94总工况）')]:
            matrix16=db.batch16_rate_matrix(mode);weights16=dict(zip(matrix16['observation_ids'],matrix16['sample_weight']))
            for r in db.batch16_rate_inputs(mode):rate16.append(dict(mode=label16,doi=r['doi'],sample=r['sample_name'],current=r['current_A_g'],value=r['target_value'],lower=r['target_lower_bound'],upper=r['target_upper_bound'],kind='原图近似，±4像素界限'if r['target_value_kind']=='bounded_original_figure'else'作者原报值，约数限定仍保留',weight=weights16[r['observation_id']],observation_id=r['observation_id'],physical_test_group=r['physical_test_group'],source_path=r['source_path'],source_sha256=r['source_sha256'],evidence=r['locator']))
        for r in rate16:r['weight_label']=format(r['weight'],'.8g')
        query('rate16_inputs',rate16,['purpose_reviews_v16','capacitance_observations','material_facts'],'db.batch16_rate_inputs(mode) for author/pointmixed/figure-only modes','三个模式共209表达行，20/95/94分别调用不可相加；混合95含20旧作者工况＋75净新增近似工况。',['原作者约数和原状态保留；图界限不是实验CI。两个DOI整组留出。'])
        plot16=[]
        for r in db.batch16_rate_inputs('figure_only'):
            group16='花椒皮（5材料）'if r['sample_name'].startswith('PAC')else'花椒籽（5材料）'if r['sample_name'].startswith('SAC')else'椰枣叶NaOH'
            plot16.append(dict(plot_scope=group16,sample=r['sample_name'],current=r['current_A_g'],value=r['target_value'],lower=r['target_lower_bound'],upper=r['target_upper_bound'],doi=r['doi'],observation_id=r['observation_id'],source_path=r['source_path'],source_sha256=r['source_sha256']))
        query('rate16_plot',plot16,['curve_samples_v8','purpose_reviews_v16'],'primary bounded rate readings only; Date6Ag uses higher vertical resolution panel','图示主表达94工况；按皮/籽/椰枣切换，原始数值坐标，无模型预测；连线不新增训练点。',['纵向4像素界限约2.15/3.82/2.98/1.65F/g，完整上下界见数据与CSV。'])
        expanded16=db.expanded_graph_3e_inputs();em16=db.expanded_graph_3e_matrix();ew16=dict(zip(em16['observation_ids'],em16['sample_weight']))
        expanded_rows16=[dict(doi=r['doi'],sample=r['sample_name'],current=r['current_A_g'],value=r['target_value'],kind=('第十八批新增读图条件'if r['conditions'].get('extraction_batch')=='v18'else'第十六批新增读图条件')if r['target_value_kind']=='bounded_original_figure'else'既有普通用途输入',weight=ew16[r['observation_id']],lower=r.get('target_lower_bound'),upper=r.get('target_upper_bound'),observation_id=r['observation_id'],source_group=db.isolation_group(r['source_group']))for r in expanded16]
        for r in expanded_rows16:r['weight_label']=format(r['weight'],'.8g')
        query('expanded16_inputs',expanded_rows16,['auxiliary_gcd_reviews_v3','purpose_reviews_v16'],'db.expanded_graph_3e_inputs()','当前显式353输入/22DOI＝普通184＋75旧图值＋94新图值；不自动替换普通184，每来源权重和1。',['353行不是353篇论文；同材料多电流、其它辅助任务和所有证据一起按来源家族隔离。未拟合。'])
        decision_labels16={'LP16_axes':'四面板独立标定，不跨面板借用量程','LP16_bounds':'4像素读图界限与作者原报值分开，不当实验CI','LP16_repeats':'6A/g保留双捕获、按分辨率选主表达；旧作者ID不扩样','LP16_scope':'三电极倍率不当器件循环；整来源跨任务隔离'}
        query('rate16_decisions',[dict(decision_id=r['decision_id'],action=decision_labels16[r['decision_id']],original_action=r['record']['decision'])for r in db.batch16_decisions()],['decisions_v16'],'db.batch16_decisions()','四项量程、读图界限、复述和用途处理；工程通过不代表全量完成。')
        for r in sources:
            if r['doi']in ['10.3390/nano14100836','10.3390/nano12010122']:r.update(batch='批次15＋16',scope='自身表/印字/阶段与本批倍率标记已审；连续波形及循环缺证仍在队列')
        labels17={'reported_aqueous_3e_GCD_capacitance':'三电极水系GCD','reported_aqueous_2e_factor2_Cs':'双电极水系：作者两倍系数','reported_organic_2e_factor4_Cs':'双电极有机：作者四倍系数'}
        inputs17=[]
        for purpose17,label17 in labels17.items():
            matrix17=db.batch17_matrix(purpose17)
            for i,r in enumerate(db.batch17_inputs(purpose17)):
                values=r['matrix_feature_values'];inputs17.append(dict(task=label17,doi=r['doi'],sample=r['sample_name'],current=r['current_A_g'],capacitance=r['value'],BET=values.get('BET_surface_area_m2_g'),Raman=values.get('Raman_ID_IG'),bulk_N=values.get('bulk_EA_N_wt_pct'),XPS_N_at=values.get('XPS_N_at_pct'),XPS_N_wt=values.get('XPS_N_wt_pct'),window='未明确绑定；不从能量倒算'if r['conditions'].get('voltage_lower_V')is None else str(r['conditions']['voltage_lower_V'])+'～'+str(r['conditions']['voltage_upper_V'])+' V',weight_label=format(matrix17['sample_weight'][i],'.8g'),source_family=matrix17['groups'][i],observation_id=r['observation_id'],source_path=r['source_path'],source_sha256=r['source_sha256'],evidence=r['locator']))
        for r in inputs17:r['Raman_label']='—'if r['Raman']is None else format(r['Raman'],'.8g')
        query('batch17_inputs',inputs17,['purpose_reviews_v17','material_facts','synthesis_stages_v3'],'db.batch17_inputs(target); db.batch17_matrix(target)','8条3E、6条2E两倍系数、1条有机2E四倍系数，三个目标分别调用。',['v17的8条3E已包含于当前普通188；此表不是额外8条。体相wt%、XPSwt%和XPSat%分列。','稻壳BET量纲未解决，标准BET保持空；纤维素2E电压未知不倒算。权重在各目标内按来源和1，无插补拟合。'])
        decision17_labels={'adsorbate_qualified':'Ar与N₂物性分开，保留同一材料身份','LMK1_SSA_conflict':'LMK1 BET2934/3037继续冻结该字段','protocol_and_basis':'有机2E四倍系数；101@1与未绑定电流76分存','stages_and_names':'挤出和800℃碳化分阶段；球磨不套螺杆默认值','bulk_surface_and_stage':'体相EA与表面XPS的质量百分比分开','cap_report_variants':'具体结果图/正文选值，保留结论竞争数值','existing_endpoint':'AHC-CL-TU已在旧库准入，关联TE011不重计','cycle_roles':'ABPC4约100为保持率，95.08为CE；摘要异文保留','device_and_panel_variants':'273.41绑定1A/g；结论30A/g及图注错位留存','precursor_and_pore_footnotes':'原料配比、重复方法句与孔径脚注争议分别保留','electrolyte_and_config':'TEABF₄/AN为有机溶液；循环SCE/2E窗口矛盾待核','printed_contribution':'图示EDLC56.8与正文58.6分别保留','series_protocol':'全十样品；范围负载不填中点；XPS仅绑定最佳样','SSA_dimension':'稻壳面积原印m³/g；标准BET不擅改单位','CV_cycling':'稻壳97.2/10000属于CV，不混入GCD循环','replicates':'三次实验与缺SD分开，不展开为三独立训练样本'}
        query('batch17_decisions',[dict(doi=r['doi'],decision_id=r['decision_id'],action=decision17_labels[r['decision_id'].removeprefix('LP17_')],original_action=r['record']['decision'])for r in db.batch17_decisions()],['decisions_v17'],'db.batch17_decisions()','16项方法、阶段与图文争议处置。保留双方原值，未解决的科学问题继续冻结。')
        new17={r['doi']for r in db.batch17_sources()}
        for r in sources:
            if r['doi']in new17:r.update(batch='批次17',scope='全样品自身主表/方法；8张木质素SI表；指定图值。连续波形未提取完')
        rate18=[];plots18=[]
        for purpose,label18 in [('ordinary_3e','普通碳3E'),('native_silica_3e','含天然硅碳3E（独立用途）')]:
            for mode,mode_label in [('author_exact','作者原报值'),('point_mixed','作者值＋可读图值'),('figure_only','原图主表达（含遮挡空值）')]:
                rr=db.batch18_rate_inputs(mode,purpose);counter18={}
                for r in rr:counter18[r['source_family_group']]=counter18.get(r['source_family_group'],0)+1
                for r in rr:rate18.append(dict(purpose=label18,mode=mode_label,doi=r['doi'],sample=r['sample_name'],current=r['current_A_g'],value=r['target_value'],lower=r['target_lower_bound'],upper=r['target_upper_bound'],kind='遮挡，无数值或数值界限'if r['target_value']is None else'作者原值'if r['target_value_kind'].startswith('author_reported')else'原图有界近似',weight_label=format(1/counter18[r['source_family_group']],'.8g'),observation_id=r['observation_id'],source_path=r['source_path'],source_sha256=r['source_sha256'],evidence=r['locator']))
            for r in db.batch18_rate_inputs('figure_only',purpose):plots18.append(dict(plot_scope='淀粉（十材料）'if r['doi']=='10.3390/molecules29112532'else'稻壳（两阶段）'if r['doi']=='10.1021/acsomega.2c07932'else'混合碳（四材料）',sample=r['sample_name'],current=r['current_A_g'],value=r['target_value'],lower=r['target_lower_bound'],upper=r['target_upper_bound'],kind='遮挡空值'if r['target_value']is None else'原图近似',purpose=label18,doi=r['doi'],observation_id=r['observation_id'],source_path=r['source_path'],source_sha256=r['source_sha256']))
        query('rate18_inputs',rate18,['purpose_reviews_v18','capacitance_observations','resolved_table_sources_v18'],'db.batch18_rate_inputs(mode,purpose)','普通碳3/97/103与天然含硅碳0/11/11分别调用，全部225表达行不可相加。',['8原始遮挡表达中2个可从自身重复图补回，6标称工况仍空。点矩阵接口拒绝空目标。','97普通点工况含3旧作者锚点＋94新图值；11天然含硅碳另列。不是新论文或独立实验。'])
        query('rate18_plot',plots18,['curve_samples_v8','purpose_reviews_v18'],'db.batch18_rate_inputs(figure_only,purpose); primary nominal report expression','114原图主表达/16材料曲线，6遮挡空点断线；未插值、未拟合。',['电流含1.5与7A/g，保持不等距坐标；±4纵向像素不是实验CI。'])
        corrections18=[]
        for r in db.batch18_binding_corrections():
            docs18={v['document_key']:dict(v)for v in db.connection.execute('select *from source_documents')};a=docs18[r['old_document_key']];b=docs18[r['new_document_key']];corrections18.append(dict(table_key=r['table_key'],old_path=a['path'],old_image=Path(a['path']).name,old_sha=a['sha256'],new_path=b['path'],new_image=Path(b['path']).name,new_sha=b['sha256'],action='XML先列Scheme1；按原文Figure标签与href更正，数值不变，旧绑定保留'))
        query('bindings18',corrections18,['source_binding_corrections_v18','figure_identity_resolution_v18','resolved_table_sources_v18'],'db.batch18_binding_corrections(); resolved_table_sources_v18','4份转录单元的来源更正，涉及13事实/16响应及1条XPS注记。',['v17原库/原SHA保留；当前facts API返回更正后路径，并附original_provenance_v17。','旧技术核验缺少图号/图像语义检查，本批新增原文label/href交叉检查，不能用排列序号代替图号。'])
        query('cycle_review18',[dict(candidate_id=r['candidate_id'],sample='ABPC-4',retention='约100%',CE='95.08%',configuration='当前未选：图注3E，正文/结论2E语境',window='未知，不借用3E倍率窗口',status='继续冻结循环准入；原值/原候选保留')for r in db.batch18_cycle_reviews()],['cycle_reviews_v18','test_candidates'],'db.batch18_cycle_reviews()','角色问题与配置问题分别审；没有取得能解决配置冲突的原始证据，不准入。')
        from data.literature_v19 import TARGETS19
        names19=dict(zip(TARGETS19,['普通三电极GCD','木质素PEO辅助水系2E Cs','木质素PEO辅助WIS2E Cs','普通水系2E四倍Cs']))
        inputs19=[]
        for target19 in TARGETS19:
            matrix19=db.batch19_matrix(target19)
            for i,r in enumerate(db.batch19_inputs(target19)):
                inputs19.append(dict(doi=r['doi'],sample=r['sample_name'],task=names19[target19],current=r['current_A_g'],value=r['value'],basis=r['conditions']['capacitance_basis'],weight=matrix19['sample_weight'][i],weight_label=f"{matrix19['sample_weight'][i]:.4g}",missing_features=sum(matrix19['missing_mask'][i]),source_path=r['source_path'],source_sha256=r['source_sha256'],locator=r['locator']))
        query('batch19_inputs',inputs19,['purpose_reviews_v19','numeric_details_v19','material_lineage_v19'],'db.batch19_inputs(target); db.batch19_matrix(target)','四目标4/2/1/1分别调用，原料/纺丝液与最终碳不自动继承；4条普通3E已包含于188总数。',['木质素PEO投料比例不等于最终碳比例；WIS12mol/kg不换mol/L。','未知和检出上限不补0，原印±量保留类型。来源权重在每个目标内合计1，不拟合。'])
        labels19={'V19_precursor_stage_and_PEO':'前驱体/纺丝液/最终碳分层；PEO投料不作最终组成；木质素XPS质量百分比','V19_SI_printed_limits_and_labels':'硫<0.01保留检出限；小数点空格歧义不猜数；S116/S1127原印标签保留','V19_old_missed_cycling_current':'旧TE009漏读循环电流10A/g；v0.26按原端点补正准入','V19_method_basis_and_Rs':'蛋米体相EA与表面XPS分开；XPS合计100.71不归一化；Rs异文保留','V19_rate_and_pore_models':'烟草82%/85.2%倍率异文冻结；HK/BJH孔容分别保存，不强制加和','V19_aliases_and_fifth_measurement':'样品别名逐图绑定；第5次新鲜表征不是长循环分母；2E系数分用途'}
        query('batch19_decisions',[dict(doi=r['doi'],decision_id=r['decision_id'],action=labels19[r['decision_id']],original=r['record'])for r in db.batch19_decisions()],['decisions_v19'],'db.batch19_decisions()','保留原值与证据；已解决的旧漏提和未解决的科学异文分别处理。')
        from data.literature_v20 import TARGETS20
        names20=dict(zip(TARGETS20,['普通三电极GCD','橙汁双电极CV器件Cg','咖啡/污泥KOH作者容量','咖啡/污泥醋酸钠作者容量','辣木Zn/Ca残留碳GCD工作质量','辣木Zn/Ca残留碳CV作者Csp']))
        inputs20=[]
        for target20 in TARGETS20:
            matrix20=db.batch20_matrix(target20)
            for i,r in enumerate(db.batch20_inputs(target20)):
                inputs20.append(dict(doi=r['doi'],sample=r['sample_name'],task=names20[target20],method=r['method'],current=r['current_A_g'],scan=r['scan_rate_mV_s'],value=r['value'],raw_value=r['raw_value'],basis=r['conditions']['capacitance_basis'],binder=r['conditions'].get('binder'),weight_label=f"{matrix20['sample_weight'][i]:.4g}",missing_features=sum(matrix20['missing_mask'][i]),source_path=r['source_path'],source_sha256=r['source_sha256'],locator=r['locator']))
        query('batch20_inputs',inputs20,['purpose_reviews_v20','numeric_details_v20','material_feature_decisions_v20'],'db.batch20_inputs(target); db.batch20_matrix(target)','六目标1/3/3/1/5/6分别调用，共19行；普通3E一行已包含于189。',['CV不作GCD；咖啡/污泥C/Cg未选只用本来源表达，辣木Zn/Ca残留另列。','原报±、方法、binder与未知均保留；同DOI/复用家族的全部任务一起留出，无拟合。'])
        labels20={'V20_cv_gcd_and_peak_scope':'橙汁CV10mV/s与GCD1A/g分开；包络比例不作原子百分比，ND/0竞争留空','V20_mass_ratio_and_postcycle':'稻壳质量比是测试配置；循环后XPS不作新鲜碳特征；v20未选方法已由v21图注补正CV5mV/s','V20_tables_formula_and_initial_graph_check':'咖啡/污泥表间BET/孔径及Raman竞争冻结；原图PTFE约157与正文一致，撤回约97误读','V20_percent_direction_and_device_conflicts':'螺旋藻实际IG/ID；EA质量与作者XPS原子声称分存，测法归属风险掩码；2E竞争值未选','V20_duplicate_identity_and_residual_scope':'辣木表1末行重印750，身份未定；Zn/Ca残留另列，BET取表与结论一致值','V20_methods_and_rate_not_lifetime':'辣木原表CV跨列字样保留，方法依正文/实际曲线；78%扫描速率保持率不作循环寿命'}
        query('batch20_decisions',[dict(doi=r['doi'],action=labels20[r['decision_id']],original=r['record'])for r in db.batch20_decisions()],['decisions_v20'],'db.batch20_decisions()','逐项保留原值和证据；风险标记不是已证明作者错误。')
        protocol_labels20={'10.3390/nano14010071':'CV器件Cg=CT/(2m)，m为单电极质量；CV 0—1.4V，GCD循环0—1V，循环1A/g/5000圈。','10.1039/d5ra03028e':'Ct公式用正负极总质量；质量比1/1.25/1.5/2是测试配置，电流分母未知。循环后XPS不继承为新鲜特征。','10.1021/acsomega.3c09438':'原式C含系数4、Cg含系数2，正文m为每个电极；当前容量符号未选，不拼统一Cs/Cd。电化学±为SD，循环binder未知。','10.3390/nano13172431':'实际Raman为IG/ID；体相EA wt%与作者XPS at%分存并标归属风险。2E的307/304/307.6竞争，旧循环94.14%只关联。','10.1021/acsomega.2c04301':'GCD Csp=IΔt/(mΔV)，m为工作电极；CV另列。残留ZnO/CaCO3保留；扫描速率保持率不是循环寿命。'}
        query('batch20_protocols',[dict(doi=r['doi'],protocol=protocol_labels20[r['doi']],original=r['record'])for r in db.batch20_protocols()],['protocol_reviews_v20'],'db.batch20_protocols()','五来源公式、方法、电流与材料范围原报；未知分母不由公式反推。')
        points21=[]
        for purpose21,task21 in [('coffee_KOH_author_capacity','咖啡/污泥：作者容量用途'),('rice_mass_ratio_inspection','稻壳：待核检查用途')]:
            for r in db.batch21_rate_rows('point_mixed',purpose21):
                ratio=r['positive_negative_mass_ratio'];series=('无KCl / PVDF'if r['sample_name']=='SSC-Na2S2O3-1.5-800'else'KCl / '+r['binder'])if ratio is None else'm+/m−='+str(ratio)
                points21.append(dict(doi=r['doi'],sample=r['sample_name'],task=task21,series=series,current=r['current_A_g'],value=r['target_value'],lower=r['target_lower_bound'],upper=r['target_upper_bound'],kind='作者原报均值，SD见原报'if r['target_lower_bound']is None else'原图±4px读取界限，非SD',raw_value=r['raw_value'],status='前作样品重叠待核，非训练输入'if r['source_overlap_pending']else'来源内用途；同论文全部一起留出',source_path=r['source_path'],source_sha256=r['source_sha256'],locator=r['locator'],original=r))
        query('rate21_points',points21,['rate_reviews_v21','curve_samples_v8','capacitance_observations'],'db.batch21_rate_rows(point_mixed,purpose)','咖啡12=3旧作者锚点+9新近似；稻壳24仅检查，两个来源用途分开。',['像素读取界限非作者SD；CV155/167/141不作GCD锚点。','同一材料/粘结剂/质量配置多工况不当独立来源。稻壳前作重叠冻结保持，无新准入或拟合。'])
        for key21,doi21 in [('coffee21_plot','10.1021/acsomega.3c09438'),('rice21_plot','10.1039/d5ra03028e')]:query(key21,[r for r in points21 if r['doi']==doi21],['rate_reviews_v21','curve_samples_v8'],'db.batch21_rate_rows(point_mixed,purpose)','均值或原图标记读取；连线仅辅助显示，不插值新数据。',['作者均值/近似及读取上下界在同节明细表逐项给出，不把读取误差当实验统计误差。'])
        cvs21=[]
        for r in db.batch21_protocol_corrections():
            cap21=next(x for x in caps if x['observation_id']==r['observation_id']);cvs21.append(dict(doi=r['doi'],ratio=cap21['conditions']['positive_negative_mass_ratio'],value=cap21['value'],old_method='v20未选定',method='CV',scan=5,current='未知，不填A/g',basis='实际Fig6(b)明确5mV/s；原空方法保留',original=r['record']))
        query('protocol21_corrections',cvs21,['protocol_corrections_v21'],'db.batch21_protocol_corrections(); currentcapacitances(method=CV)','三旧报告的当前方法绑定，非三个新电容标签。')
        identity21={r['candidate_id']:r['record']for r in db.batch21_identity_links()}
        query('identity21_links',[dict(candidate_id=r['candidate_id'],endpoint_id=r['endpoint_id'],doi=r['doi'],sample=r['record']['sample_name'],retention=r['record']['retention_pct'],cycles=r['record']['cycle_count'],status='既有已准入端点关联，不重复计实验'if r['record']['current_formal_status'].startswith('already_')else'既有待证端点，前作重叠冻结保留'+('；质量不平衡在普通主集外'if r['record']['positive_negative_mass_ratio']==2 else''),original=r['record'])for r in db.batch21_identity_links()],['candidate_identity_links_v21'],'db.batch21_identity_links()','三文献候选关联既有端点，新增端点0/准入0。')
        query('identity21_audits',[dict(candidate_id=r['candidate_id'],doi=r['doi'],existing=', '.join(r['record']['existing_same_DOI_endpoint_ids'])or'直接DOI字段无匹配，不能据此认定新实验',status='已有权威候选链接'if r['record']['established_link']else'同DOI待逐测试审查'if r['record']['existing_same_DOI_endpoint_ids']else'待进一步身份核对',original=r['record'])for r in db.batch21_candidate_audits()],['candidate_identity_audits_v21'],'db.batch21_candidate_audits()','83个文献层循环候选的DOI检索对账，32同DOI命中，非83项准入。',['6个旧观察直接字段无可规范化DOI，详见本批curation_spec.identity_audit_summary，不能自动称新来源。'])
        from data.literature_v22 import TARGETS22
        names22=['松木：普通3E GCD','林业：水系原样品表达','林业：水系去灰折算','林业：有机原样品表达','林业：有机去灰折算','SAP参考：3E GCD','SAP参考：2E作者两倍式','木质素模板碳：CV10mV/s','含锰复合：CV10mV/s']
        inputs22=[]
        for t,name in zip(TARGETS22,names22):
            matrix=db.batch22_matrix(t)
            for i,r in enumerate(db.batch22_inputs(t)):inputs22.append(dict(doi=r['doi'],sample=r['sample_name'],task=name,method=r['method'],system=r['system'],value=r['value'],current=r['current_A_g'],scan=r['scan_rate_mV_s'],basis=r['conditions']['capacitance_basis'],physical_test=r['conditions']['physical_test_group'],source_group=r['source_family_group'],source_weight=matrix['sample_weight'][i],ready='当前独立用途输入通过；未拟合',original=r))
        query('batch22_inputs',inputs22,['purpose_reviews_v22','material_facts','synthesis_stages_v3'],'db.batch22_inputs(target); db.batch22_matrix(target)','九用途3/3/3/3/3/3/1/5/3，共27表达；松木3已在v22封版时嵌套于普通192，当前见总览。',['原样品/去灰折算共享实验；CV不作GCD，SAP和Mn用途不进普通生物质循环。','同DOI全任务留出；本批0拟合、0循环准入。'])
        labels22={'V22_forest_residue_normalization_and_missing_SI':'压片与SI分散配方分开；原/去灰表达同实验，有机窗口仍空','V22_pine_Raman_XPS_and_units':'实际ID/IG与DRY-2图例补正；孔容量纲和C1s内比例按证据保存','V22_pine_WET1_point1_capacitance_conflict':'WET-1的247@0.1A/g与图首点低于220冲突，该工况未进输入','V22_SAP_scope_methods_BET_and_formula':'SAP混合参考；BET竞争、成分基准、XPS图文峰位和缺C公式保留','V22_lignin_CV_composite_and_process_roles':'八条CV10mV/s分普通模板碳/含锰用途；无循环测试，动力学响应另计'}
        query('batch22_decisions',[dict(doi=r['doi'],action=labels22[r['decision_id']],original=r['record'])for r in db.batch22_decisions()],['decisions_v22'],'db.batch22_decisions()','五项逐问题决定，保存图文异文与用途掩码，不假称已有勘误。')
        query('batch22_links',[dict(doi=r['record']['doi'],sample=r['record']['sample'],endpoint=r['record']['existing_endpoint_id'],status='既有端点关联；本批不新增循环准入',evidence=r['record']['evidence'])for r in db.batch22_cycle_identity_links()],['cycle_identity_links_v22'],'db.batch22_cycle_identity_links()','六个既有端点链接，不是六个新循环实验；原固定37待证不抵扣。')
        new22={r['doi']for r in db.batch22_sources()}
        for r in sources:
            if r['doi']in new22:r.update(batch='批次22',scope='全正文/主表及可得原图范围；SAP/含锰参考分用途，未取得SI/原图与未转录波形继续')
        from data.literature_v23 import TARGETS23
        names23=['零Cu对照普通三电极','含Cu复合三电极','含Cu双电极作者单电极表达'];rows23=[]
        for t,name in zip(TARGETS23,names23):
            m=db.batch23_matrix(t)
            for i,r in enumerate(db.batch23_inputs(t)):rows23.append(dict(doi=r['doi'],sample=r['sample_name'],task=name,system=r['system'],value=r['value'],current=r['current_A_g'],source_weight=m['sample_weight'][i],status='仅相应用途输入，未拟合',original=r))
        query('batch23_inputs',rows23,['purpose_reviews_v23','material_facts','synthesis_stages_v3'],'db.batch23_inputs(target); db.batch23_matrix(target)','2零Cu普通3E、4含Cu3E、1含Cu2E，均同一DOI。',['同源权重归一；M325争议3E工况、蜜瓜皮旧冻结和309二手行未进输入。'])
        secondary=[]
        for r in db.secondary_inspection_rows():
            v=r['record'];secondary.append(dict(curator=v['curator_doi'],row_id=v['row_id'],cited=', '.join(v['cited_DOIs'])or'上下文/未列DOI',description=' | '.join(v['cells'][2:5])if v['curator_doi']=='10.1002/cplu.202500342'else' | '.join(v['cells'][:3]),location=v.get('locator')or v['table_id']+' row '+str(v['row_ordinal']),status='二手检索/核验；无训练资格',source_sha256=v['source_sha256']))
        query('secondary23_rows',secondary,['secondary_rows_v23','source_documents'],'db.secondary_inspection_rows()','309二手表行：166同行汇编＋143综述/上下文，不计自身样品。',['S1七页是一张表；续页漏首6行已按原PDF坐标补回。89/164重复、32/33同特征异目标，全部原行保留。','核验队列DOI不能自动代表新增或缺失全文；正文/SI引用关系仍需原论文核证。'])
        query('peer23_metrics',[dict(model=r['record']['model'],RMSE=r['record']['RMSE'],MAE=r['record']['MAE'],R2=r['record']['R2'],scope='同行特定缩放，不是保持率百分点或已核实原始F/g')for r in db.peer_metrics()],['peer_model_metrics_v23'],'db.peer_metrics()','同行四模型原报；真实量纲及拆分未复现，不作为本项目性能。')
        query('batch23_decisions',[dict(doi=r['doi'],decision=r['record']['decision'],evidence=r['record']['evidence'])for r in db.batch23_decisions()],['decisions_v23'],'db.batch23_decisions()','五项逐问题处置；原值/旧冻结/原端点保持。')
        new23={r['doi']for r in db.batch23_sources()}
        for r in sources:
            if r['doi']in new23:r.update(batch='批次23',scope='自身对照/含铜/蜜瓜皮与二手汇编/综述分层；全部来源仍部分提取')
        from data.literature_v24 import TARGETS24
        labels24=['普通三电极报告电容','食物气凝胶双电极作者口径','柚皮双电极作者口径','麦壳双电极四倍Cs'];inputs24=[]
        for t,name in zip(TARGETS24,labels24):
            m=db.batch24_matrix(t)
            for i,r in enumerate(db.batch24_inputs(t)):inputs24.append(dict(doi=r['doi'],sample=r['sample_name'],task=name,system=r['system'],value=r['value'],current=r['current_A_g'],source_weight=m['sample_weight'][i],basis='工作活性质量'if r['system']=='3E'else'正负极总质量四倍Cs'if r['doi']=='10.3390/nano12213804'else'作者口径，质量范围未统一',reference='未知/争议，未解冻循环'if r['doi']in ['10.3390/nano15050387','10.3390/ma16134577']else'Ag/AgCl（3E）；2E窗口未继承',original=r))
        query('batch24_inputs',inputs24,['purpose_reviews_v24','material_facts','synthesis_stages_v3'],'db.batch24_inputs(target); db.batch24_matrix(target)','四用途11/1/4/2，共18表达；不是18个循环样本。',['11条普通3E已计入205/30 DOI；其它2E作者口径分开，不与普通器件容量混称。','未知/争议参比保留，不清除循环保持率准入冻结；同文所有阶段、曲线和辅助任务一起留出。'])
        query('inspection24_rows',[dict(doi=r['doi'],sample=r['sample_name'],value=r['value'],current=r['current_A_g'],scope='1M与6M KOH矛盾；仅核查，不入矩阵',original=r)for r in db.batch24_inspection_rows()],['inspection_rows_v24','capacitance_observations'],'db.batch24_inspection_rows()','四种糠醛渣碳的报告电容保留；浓度争议尚未解决。')
        descriptions24={'V24_concentration_and_ratio_conflicts':'糠醛渣1M/6M、介孔比例异文保持；四电容仅核查，未知XPS基准不猜at%。','V24_unit_roles_and_cited_protocol_scope':'食物气凝胶HK孔容、原料干基与最终XPS分开；单位和能量/功率误写保留，详细314.4与舍入314对应；参比未补到。','V24_reference_temperature_and_peak_assignment':'柚皮873K不从名称猜800°C；calomel/HgHgO、Raman峰位与402.6eV归属异文保留，未给循环解冻。','V24_three_two_electrode_and_unbound_claims':'柚皮3E90.1与2E约81是不同测试；75F/g未绑定电流，CE和平均每圈损失不当保持率。','V24_prechar_alias_mass_and_unobtained_figures':'麦壳阶段/收率分母分开；2E四倍Cs不当器件C，未知窗口不抄3E；另一篇HPC截图不能借用。'}
        query('batch24_decisions',[dict(doi=r['doi'],action=descriptions24[r['decision_id']],original=r['record'])for r in db.batch24_decisions()],['decisions_v24'],'db.batch24_decisions()','五项按字段与用途处置，保留原值、出处与未决问题。')
        new24=[]
        for r in db.tests():
            if r['candidate_id'].startswith('LP24:'):
                q=r['record'];new24.append(dict(candidate=r['candidate_id'],sample='NSOC-800'if 'NSOC'in r['candidate_id']else'HPC-700',retention=('约'if q.get('retention_relation')=='approximately'else'')+str(q['retention_pct'])+'%',cycles=q['cycle_count'],current=q['current_A_g'],status='新增文献候选；未加入循环库',evidence='XML正文第18段：98.59%/30000圈；器件原图未取得，电压窗口待核'if 'HPC700'in r['candidate_id']else'自身表1约81%及图4(d)；与三电极90.1%分开',original=q))
        for r in new24:
            if r['candidate']=='LP24:HPC700:2E:C30000'and r['candidate']in links:r.update(status='v0.28已准入跨年份2E',evidence='正文第18段与实际图8(a)：98.59%/30000圈、同器件0～1V；2022年分用途')
        query('batch24_candidates',new24,['test_candidates','candidate_identity_audit.json','literature_links_v28'],'db.tests() LP24; current versioned cycling links','v24两个器件候选的当前状态；麦壳在v0.28跨年份用途准入，柚皮保持候选，不抵扣原37。',['柚皮约81不是精确81；麦壳原图现已取得，保留v24原始未知窗口。'])
        query('batch24_links',[dict(doi=r['record']['doi'],sample=r['record']['sample'],endpoint=r['record']['existing_endpoint_id'],scope='既有循环关联；原冻结保留')for r in db.batch24_cycle_identity_links()],['cycle_identity_links_v24'],'db.batch24_cycle_identity_links()','三个已有端点仅关联补提取材料特征，不是新循环准入。')
        for r in sources:
            if r['doi']in {x['doi']for x in db.batch24_sources()}:r.update(batch='批次24',scope='全样品/阶段原表及正文；17可得原图，麦壳9图未取得；协议争议和剩余波形保持')
            if r['doi']=='10.3390/nano12213804':r.update(batch='批次24/25',scope='9原图已取得并核读；20倍率捕获含8旧锚点/12新工况；实际器件0～1V，剩余波形仍待')
        from data.literature_v25 import PURPOSES25,MODES25
        rates25=[]
        for p,name in zip(PURPOSES25,['三电极工作质量比电容','双电极总质量四倍Cs']):
            for mode,label25 in zip(MODES25,['仅作者原值','报告值＋读图','仅原图读数']):
                matrix=db.batch25_rate_matrix(mode,p)
                for i,r in enumerate(db.batch25_rate_inputs(mode,p)):rates25.append(dict(sample=r['sample_name'],task=name,mode=label25,current=r['current_A_g'],value=r['target_value'],lower=r['target_lower_bound'],upper=r['target_upper_bound'],kind='作者报告值'if r['target_value_kind']=='author_reported_exact'else'有界读图，非作者精确值',weight=matrix['sample_weight'][i],source_family=r['source_family_group'],observation_id=r['observation_id'],original={k:r[k]for k in ['doi','sample_name','system','method','conditions','graph_reading_id','graph_observation_id','nominal_report_group','source_family_group','target_value_kind','target_lower_bound','target_upper_bound']}))
        query('batch25_rates',rates25,['rate_reviews_v25','curve_samples_v8','capacitance_observations'],'db.batch25_rate_inputs(mode,purpose); modes nested','3E为6/15/15、2E为2/5/5，都是同一DOI；20工况仅净新增12。',['±4y/±2x像素是读取包络，不是作者SD/置信区间；不插值或填补遮挡点。','双电极四倍Cs采用两电极活性物总质量，不能与器件比电容或三电极合并。'])
        query('batch25_figures',[dict(label=r['record']['label'],path=r['record']['path'],sha256=r['record']['sha256'],status='已取得并核读；连续波形未全部提取',original=r['record'])for r in db.batch25_figures()],['figure_reviews_v25','source_documents','acquisition.json'],'db.batch25_figures(); article PMC9655081 bound originals','9张原始JPG；包内无另行SI，不把GIF预览重复计图。')
        query('source_summary',sources,['reviewed_sources','materials','material_facts'],sql,'按DOI汇总数值单元，不是训练样本。',['只完成记录声明范围，尚未称全文全部利用。'])
        issue_labels={'reported_XPS_sum':'XPS合计限定','surface_partition_inconsistent':'孔面积分项不符','body_table_disagreement':'正文与表数值竞争','author_ratio_vs_volumes':'报告比例与孔容不符','reported_precision_variants':'数值精度表述不同','cycling_configuration_electrolyte_and_current_roles':'循环协议绑定冲突','own_table_conflict':'酸碱EIS表值冲突','element_label_binding_energy_conflict':'XPS元素标签与能量冲突','percentage_basis_not_explicit':'百分比基准未知','control_alias_not_merged':'无活化对照别名未合并'}
        actions={'PC800_XPS':'原值合计99.7%，不补元素、不归一化。','corn_cob_BET':'表1770与正文1705并存，标准面积待定。','corn_cob_volume_ratio':'孔容和报告比例并存，不用计算值覆盖。','corn_grain_precision':'保留各处精度，不能算作三次测量。','corn_husk_surface':'分项面积超过总量，隔离且不换列。','purple_EIS_AC5':'保留酸/碱四个竞争值，不自动交换列。','purple_XPS_AC30':'保留元素标签与能量冲突，C/O标准值冻结。','purple_control_alias':'SI无活化对照单独保存，别名不自动合并。','purple_microporosity':'微孔率基准未知，不猜面积比或体积比。','purple_cycle_protocol':'保留配置、电解液及电流角色竞争，循环标准条件留空。'}
        issue_labels.update(explicit_partition_conflict='明示孔容分项冲突',method_qualified_partition_not_assumed_exhaustive='不同方法孔容不假定穷尽',Raman_IG_ID_not_ID_IG='Raman比值方向',coulombic_efficiency_not_cycle_retention='库仑效率与循环保持率分开',separate_test_baselines='不同测试初始参照',device_vs_factor4_single_electrode_convention='器件与四倍单电极表达',method_results_current_range_difference='方法与结果电流范围差异',intentional_CNT_and_precursor_mass_basis='复合碳与前驱体质量口径')
        actions.update(MNS_char_Vmeso='原0.36及比例均保留，冲突孔容和耦合比值在辅助特征中屏蔽。',Hurd2_partition='保留各测法原值，不用差值补孔容。',Hurd_Raman_direction='保留IG/ID；倒数单列为派生量。',Hurd_CE_not_retention='库仑效率单独存响应任务，不作保持率或预实验特征。',Hurd_cycle_baseline='循环初始28与新鲜速率测试38分开，不改作者取整78%。',Popcorn_capacitance_basis='同一测试两种表达共享组，不当两次独立实验。',Popcorn_current_range='两处范围保留，Table6的1A/g另有明确绑定。',CNF_precursor_final_basis='前驱体两组质量比分别保存，不推断最终CNT质量分数。')
        issue_labels.update(abstract_original_figure_retention_conflict='摘要与循环原图冲突',prose_figure_rate_capacitance_difference='正文与倍率原图差别',reported_BET_fit_range_quality_qualification='BET拟合范围质量限定',electrode_mass_reports_different_scope='电极质量表述范围不同',same_current_capacitance_conflict='同电流比电容冲突',native_calcium_phosphate_material_purpose='天然钙磷残留材料用途',hybrid_capacitance_and_retention_competition='混合器件摘要正文竞争',reported_precision_and_transcription_variants='表图精度与转录差异',cycling_voltage_binding_unresolved='循环电压绑定待证',author_factor2_capacitance_separate_target='作者两倍系数独立目标',adsorption_and_EIS_responses_not_pretest_features='吸附及EIS响应分开')
        actions.update(LP4_TAK_retention='摘要98%与原图约93.81%（3像素约±0.60百分点）并存；不猜归一化，循环冻结。',LP4_TAK_rate='7A/g正文约160与读图约168.63并存；不选作精确标签。',LP4_TAK_BET='保留BET及作者0.05～0.8拟合区间注记，不新设一律要求C常数的门槛。',LP4_TAK_mass='质量范围分别保留，不推断每电极质量，不因此否定作者报告A/g用途。',LP4_HAC_cap='1A/g的360/240冻结；其余五种电流按天然矿物残留用途调用。',LP4_HAC_scope='天然CaP另列；SI碳元素图不能量化Ca/P或证明为零。',LP4_HAC_hybrid='HAC、EMD和HAC||EMD各自绑定，不转移混合器件冲突到碳单电极。',LP4_WPC_precision='BET用主表/SI共同3377.94；微孔容明确选SI0.4797，保留主表0.48取整值。',LP4_WPC_voltage='87.5%有原图支持；循环电压仍未知，不用CV或能量反算填补。',LP4_WPC_basis='六条作者两倍系数Csp独立目标，不混入器件总质量比电容。',LP4_WPC_outcomes='24条CO₂吸附和8条EIS独立响应，不作保持率或预实验材料特征。')
        issue_labels.update(XPS_not_detected_and_unreported_distinct='XPS未检出与未量化分开',reported_uncertainty_competing='作者不确定量异文',sample_specific_XRD_table_and_body_difference='XRD自身表与正文差异',same_source_summary_within_reported_uncertainty='自身摘要值在作者±范围内',current_prose_decimal_vs_own_axis='电流小数点与原图冲突',initial_curve_vs_full_retention_protocol_scope='共同GCD协议的用途范围')
        issue_labels.update(cycling_SI_signed_voltage_vs_actual_own_cycle_insets='实际循环图与SI电压异文',own_body_table_capacitance_competition='正文与自身表倍率值竞争',synthesis_control_and_alias_not_assumed='活化剂用量与对照别名',XPS_envelope_dash_malformed_and_sum='XPS包络、横杠及原印数字',abstract_pore_volume_scope_not_assumed_total='摘要孔容范围不明',DES_and_mean_uncertainty_separate_purpose='DES与均值±量单独保存',cycling_current_not_bound_from_rate_test='循环电流仍缺数值',EIS_report_and_summary_competition='EIS表与总结竞争')
        actions.update(LP5_WJ_voltage='实际首次/末次循环图与正文均0～1V，据此选择；保留SI−1～0V异文，已在v0.20准入双电极报告用途。',LP5_WJ_cap='NWJPC-1在1A/g的133/133.7冻结，其余四电流保留。',LP5_WJ_scope='对照KOH:前驱体3:1，掺杂组1:1；NWJPC组水热温度未明确绑定，未猜填180℃。',LP5_WJ_XPS='N1s横杠非0；总N0.9at%另存。原12.6.格式异常留空；99.64不归一化。',LP5_G_pore='明确微孔0.377、介孔0.520、总0.897；摘要0.38不当总孔容。',LP5_G_targets='12组DES保持率与作者±数保留；银丝伪参比、30℃及固态原型另列。',LP5_A_cycle='三浓度循环标签保留，电流未报数值；不借2A/g倍率工况补填。',LP5_A_EIS='保留42.96/42异文和4M最大Rct；EIS响应不作预实验材料特征。')
        issue_labels.update(activation_duration_body_vs_graphical_abstract='活化时长图文冲突',reported_Raman_ratio_arithmetic_conflict='Raman比值与强度不符',censored_retention_vs_absolute_curve='保持率限值与绝对C曲线',two_electrode_normalization_unreported='双电极归一化未报告',rounded_contribution_sum101='图中贡献比例合计101%',method_qualified_EDAX_error_and_element_assignment='EDAX测法/误差/元素赋值',intentional_PAN_composite_and_controls='PAN对照与复合体系',different_GCD_voltage_programmes='GCD电压程序不同',single_electrode_equivalent_vs_device_mass='单电极等效与器件质量分开',coulombic_efficiency_separate_from_retention='库仑效率与保持率分开')
        actions['V24_prechar_alias_mass_and_unobtained_figures']='v24原审查留存：v25现已取得9张原图，器件0～1V已补证；v0.28仅跨年份循环准入。前炭化物/别名与其它口径边界继续保持。'
        issues=[dict(doi=r['doi'],sample=r['sample_name'],issue=issue_labels.get(r['issue'].get('kind'),r['issue'].get('kind')),action=actions.get(r['issue_id'],r['issue'].get('action')),details=json.dumps(r['issue'],ensure_ascii=False)) for r in db.issues()]
        query('issues',issues,['scientific_issues'],'SELECT * FROM scientific_issues;','每个争议/限定项，不是独立样本。',['保留双方原值与出处，不以性能或新版本择值。'])
        material_map={m['material_key']:m for m in db.materials()};candidates=[]
        for item in source_grouped_candidates(db):
            record=item['record'];m=material_map[item['material_key']]
            kind='容量保持率（锌离子，独立任务）' if record.get('retention_metric')=='specific_capacity_mAh_g_not_capacitance' else '电容保持率候选'
            candidates.append(dict(candidate_id=item['candidate_id'],doi=m['doi'],sample=m['sample_name'],system=record.get('system'),electrolyte=record.get('electrolyte'),concentration_mol_L=record.get('concentration_mol_L'),current_A_g=record.get('reported_current_A_g'),cycle_count=record.get('cycle_count'),retention_pct=record.get('retention_pct'),retention_uncertainty=record.get('reported_retention_uncertainty'),metric=kind,status='已备主要证据，正式增量准入待做' if item['candidate_id']=='LP5_SSC' else '候选，尚非正式成员',source_path=record.get('evidence_source_path'),source_sha256=record.get('source_sha256'),locator=record.get('locator'),details=json.dumps(record,ensure_ascii=False)))
        for candidate in candidates:
            link=links.get(candidate['candidate_id'])
            candidate['formal_endpoint_id']=link['endpoint_id'] if link else None
            admitted=current_byid.get(link['endpoint_id'])if link else None
            candidate['status']=('已准入：'+('三电极'if admitted['system']=='3E'else'双电极')+'报告工况'+('（跨年份独立视图）'if admitted.get('source_year',2026)<2023 else'')) if admitted else ('已审：独立DES均值用途（非普通水系）' if candidate['candidate_id'].startswith('LP5_GC') and candidate['candidate_id']!='LP5_GCprototype' else '候选，当前未建立准入链接')
            if candidate['candidate_id']=='LP8_Gels_ENFAFBa_2E_C10000':candidate['status']='已审：PAN/生物炭复合循环用途（非普通主集）'
            if candidate['candidate_id'].startswith('LP8_Onion'):candidate['status']='限值/参照待协调，未审为精确保持率输入'
            rawrecord=json.loads(candidate['details']);rel=rawrecord.get('retention_relation') or ''
            if rawrecord.get('legacy_endpoint_id')and not link:
                candidate['formal_endpoint_id']=rawrecord['legacy_endpoint_id'];prior=current_byid.get(candidate['formal_endpoint_id']);candidate['status']=('既有正式'+('3E'if prior['system']=='3E'else'2E')+'端点的文献关联；不重复计数') if prior else '既有待证端点关联；所缺条件见原记录'
            if candidate['candidate_id']=='LP11_Tea_3E_C2000'and not link:candidate['status']='原ID/2021年；跨年份用途增量审查待做'
            if candidate['candidate_id']=='LP11_Tondolo_2E_C10000'and not link:candidate['status']='证据已整理；逐测试准入待做，须与前作隔离'
            if candidate['candidate_id'].startswith('LP11_WHAC'):candidate['status']='实际循环电流未报告；保持候选，不借倍率工况'
            if candidate['candidate_id'].startswith(('LP13_Mango','LP13_Leather'))and not link:candidate['status']='主要证据已核；正式逐测试增量准入待做'
            if candidate['candidate_id']=='LP17_Rice_CV':candidate['metric']='CV循环保持率（独立方法）';candidate['status']='200mV/s CV；不作GCD循环准入'
            if candidate['candidate_id'].startswith('LP17_NPC'):candidate['status']='配置/SCE轴与器件窗口争议待核；未准入'
            if candidate['candidate_id']=='LP17_ABPC4':candidate['status']='约100保持率/CE95.08角色已核；图注3E与2E语境冲突冻结';candidate['system']='当前未选（原候选曾记3E）'
            if candidate['candidate_id'].startswith('LP13_Interface'):candidate['status']='商业原料未知且器件窗口有争议；参考候选不准入'
            if candidate['candidate_id']in identity21:
                review21=identity21[candidate['candidate_id']];candidate['formal_endpoint_id']=review21['endpoint_id'];candidate['status']='既有正式2E端点关联，不重复计实验'if review21['current_formal_status'].startswith('already_')else'既有待证端点：前作样品重叠未核'+('；质量不平衡在普通主集外'if review21['positive_negative_mass_ratio']==2 else'')
            candidate['retention_relation']=rawrecord.get('retention_relation')
            candidate['retention_is_censored']=rawrecord.get('reported_retention_is_censored',False)
            candidate['retention_value_kind']='censored_limit_not_exact_target' if candidate['retention_is_censored'] else 'see_original_record_and_purpose_review'
            prefix=rel if rel in ['<','>','<=','>=','≤','≥','~'] else '≈' if rel=='approx' else ''
            suffix='（由损失率换算）' if rel=='derived_complement' else ''
            candidate['retention_display']='未给精确值' if candidate['retention_pct'] is None else prefix+f"{candidate['retention_pct']:g}"+suffix
            candidate['metric']=candidate['metric'].replace('电容保持率候选','电容保持率（作者报告）')
        query('cycling_candidates',candidates,['test_candidates','materials','literature_links_v20'],
          'SELECT t.*,m.doi,m.sample_name FROM test_candidates t JOIN materials m USING(material_key);',
          '文献层逐体系候选与当前循环库准入链接；不包含当前循环库全部观察，不把候选和正式端点算两次实验。',
          ['锌离子容量、普通电容保持率和DES用途明确分开；作者±量不猜SD或SEM。','早期候选中未结构化到相同字段的值保持空，原record_json和定位完整可查。'])
    fixed=json.loads((ROOT/'docs/DATA_CORRECTION_GOAL.json').read_text('utf8'))
    active=json.loads((ROOT/'docs/LITERATURE_EXTRACTION_GOAL.json').read_text('utf8'))
    overview=[dict(summary,goal_status=active['app_goal_status_last_confirmed'],cycling_version=cycle_pointer['version'],formal_main_rows=len(main_rows),formal_main_sources=len({group(r)for r in main_rows}),formal_2e_rows=len(two_rows),formal_2e_sources=len({group(r)for r in two_rows}),all_years_3e_rows=len(all_years_3e),all_years_3e_sources=len({group(r)for r in all_years_3e}),all_years_2e_rows=len(all_years_2e),all_years_2e_sources=len({group(r)for r in all_years_2e}),formal_2e_residue_rows=len(residue27),formal_2e_residue_sources=len({group(r)for r in residue27}),formal_2e_approx_rows=len(approx27),formal_2e_approx_sources=len({group(r)for r in approx27}),new_ordinary_main_admissions=cycle_summary.get('ordinary_main_new_admissions',0),new_residue_only_admissions=cycle_summary.get('residue_only_new_admissions',0),new_cross_year_only_admissions=cycle_summary.get('cross_year_only_new_admissions',0),new_formal_cycling_admissions=cycle_summary.get('new_purpose_admissions',0),last_cycling_release_purpose_admissions=cycle_summary.get('new_purpose_admissions',0),new_endpoint_records=cycle_summary.get('new_endpoints',0),promoted_existing_endpoints=cycle_summary.get('promoted_existing_endpoints',0),linked_candidates=len(links),cycling_observations=observation_count,fixed_goal_records=fixed['fixed_record_count'],fixed_resolved=fixed['scientifically_resolved_in_goal'],fixed_pending=fixed['current_pending'])]
    query('cycle28_reviews',cycle28,['reviewed_endpoints_v28','evidence_v28','literature_links_v28'],'db.fetch(reported_2e_all_years); onlyreview_disposition_v28','新增麦壳1条2022年对称器件循环；跨年份2E34/28家族，原普通2E31/25保持。',['作者初始参照，精确圈号未知；适用同电池GCD程序，不冒称实际循环电压插图。','同DOI全部材料/倍率/循环一起隔离；原39中2解决37待证不抵扣，无拟合。'])
    query('cycle27_reviews',cycle27,['cycling_API.reviewed_endpoints_v27','evidence_v27','profile_membership_v27'],'db.fetch(reported_2e_residue); onlyreview_disposition_v27','三条既有林业水系循环按已有残留敏感性用途准入；保留原值与身份，不增加观察行。',['自身原样品BET，不用去灰值；同论文三材料及所有辅助任务一起隔离。','0～1V依据适用同电池GCD程序，非声称Fig8e单独画循环电压；基线圈号及物理质量分母仍未知。','普通主集不增加；原固定39与历史41范围中均不含此三条，不抵扣37。'])
    query('cycle27_cohorts',residue27_cohorts,['profile_membership_v27','cycling_API.fetch'],'db.fetch(reported_2e_residue); db.fetch(reported_2e_approx)','残留36/27、含近似38/29为嵌套视图，不能相加；普通2E仍31/25。')
    query('overview',overview,['summary.json','docs/LITERATURE_EXTRACTION_GOAL.json',cycle_pointer['database_file']],
      'SELECT COUNT(*) FROM materials; SELECT COUNT(*) FROM material_facts WHERE value IS NOT NULL; SELECT COUNT(*) FROM capacitance_observations WHERE value IS NOT NULL;',
      '材料数值与比电容报告按当前证据层汇总；循环主集和固定待证另计。',['历史725项与本页新增层重叠未完全对账，不能直接相加。'])
    query('formal_2e',two_rows,['cycling_API.fetch(reported_2e)','profile_membership_v20','immutable_parent_chain'],
      "db.fetch('reported_2e').rows -- versioned read-only API across the immutable parent chain",
      '正式双电极普通水系循环端点；与三电极主集分开，同来源全部标签整体留出。',
      ['原2023—2026年份规则保持；新增芒果核后31行/25家族，Tondolo与前作仍整组隔离。2018/2019早期来源在跨年份视图。','来源家族用于权重和来源折，不作为X预测特征；未执行新拟合。'])
    cohorts=[dict(profile=p,year_scope=year,rows=len(rs),sources=len({group(r)for r in rs}),rule='来源家族用于矩阵/权重/折分；不同队列分别报告')for p,year,rs in [('reported_3e','2023—2026',main_rows),('reported_2e','2023—2026',two_rows),('reported_3e_all_years','已逐测试核定的跨年份',all_years_3e),('reported_2e_all_years','已逐测试核定的跨年份',all_years_2e)]]
    query('cycling_cohorts',cohorts,['cycling_API.fetch','profile_membership_v22'],'db.fetch(profile).feature_matrix() -- no fitting','四个队列分开；跨年份是显式旧主集加早期核定测试，不能与旧模型直接比误差。')
    query('new_cycle_admissions',new_admissions,['reviewed_endpoints_v22','evidence_v22','changes_v22'],'db.fetch(profile); unique endpoint_id with literature_candidate_id_v22','五项用途准入=3新记录+2既有ID补证；不减少原38待证。',['棉花86%争议原值保留；NFAC真实101.7%不裁100；未知质量分母不猜算。'])
    query('cycle23_admissions',cycle23,['reviewed_endpoints_v23','evidence_v23','changes_v23','source_family_rules'],'db.fetch(profile); current rows with literature_candidate_id_v23','2项用途=1新端点+1旧ID晋升；282观察不全是训练数据。',['Tondolo94%/10000/5A/g及红茶98.8%/2000/5A/g逐测试核定；前作同家族全部任务隔离。','红茶2021仅跨年份3E；15格冻结/原38待证保持，无新拟合。'])
    query('cycle24_admissions',cycle24,['reviewed_endpoints_v24','evidence_v24','changes_v24'],'db.fetch(reported_3e_all_years); rows with literature_candidate_id_v24','同一2022论文/一种材料/两盐的2项用途；新增1来源，不能当两篇独立论文。',['96.71/96.36来自Fig8f印字，10000圈/1A/g；窗口按同盐自身GCD和共同协议，不冒称取得逐圈原始GCD。','未知质量分母和精确基线下标保留；N/O继续冻结，无新拟合。'])
    query('cycle24_feature_masks',masks24,['feature_conflicts_v24','evidence_v24'],'db.feature_conflicts_v24(); selected null and unselected original N/O values','1个材料的N/O及报告百分比别名共4通道屏蔽；不是4个独立争议或新实验。')
    query('cycle25_admissions',cycle25,['reviewed_endpoints_v25','evidence_v25','report_decisions_v25','literature_links_v25'],'db.fetch(profile); current rows with literature_candidate_id_v25','2来源/2材料/2端点，Mango2E与Leather3E分用途；文献候选链接同一次测试，不重复计数。',['BET工作值/取整及循环电流/角色异文保留，未知电流分母和精确基线下标不猜填。','v0.25时原38待证；当前固定队列为37，15历史冻结和苏铁绒N/O屏蔽保持，没有新拟合。'])
    query('cycle26_correction',cycle26,['changes_v26','evidence_v26','reviewed_endpoints_v26'],'db.by_endpoint(candidate:TE009); explicit v26 membership','原39固定范围中的旧端点补正；新增准入1，观察数与端点数不增。',['旧审查漏读同一XML完整段落的10A/g循环句，保留旧空值和旧理由。','精确初始圈号、物理质量分母及N/O原子百分比仍空。'])
    for key in ['cycle28_reviews','cycle27_reviews','cycle27_cohorts','cycle26_correction','overview','formal_2e','cycling_candidates','cycling_cohorts','new_cycle_admissions','cycle23_admissions','cycle24_admissions','cycle24_feature_masks','cycle25_admissions']:
        source=queries[key]['source'];source['label']=pointer['version']+'与当前'+cycle_pointer['version']+'只读接口'
        source['files'].extend([{'name':cycle_pointer['database_file']},{'name':'data/current_database.json'}])
        source['evidenceFlow'].append('候选当前状态通过不可变父链及literature_links_v22/v23/v24/v25/v26/v27/v28查询；家族规则同时作用于矩阵权重和来源折，既有ID晋升不重复计实验。')
    progress=[dict(batch='批次01',numeric_facts=88,materials=15),dict(batch='批次02',numeric_facts=157,materials=24),dict(batch='批次03',numeric_facts=511,materials=46),dict(batch='批次04',numeric_facts=603,materials=61),dict(batch='批次05',numeric_facts=791,materials=84),dict(batch='批次06',numeric_facts=862,materials=86),dict(batch='批次07',numeric_facts=1055,materials=92),dict(batch='批次08',numeric_facts=1205,materials=107),dict(batch='批次09',numeric_facts=1453,materials=139),dict(batch='批次10',numeric_facts=1645,materials=160),dict(batch='批次11',numeric_facts=1926,materials=175),dict(batch='批次12',numeric_facts=2089,materials=185),dict(batch='批次13',numeric_facts=2293,materials=211),dict(batch='批次14',numeric_facts=2293,materials=211),dict(batch='批次15',numeric_facts=2447,materials=225),dict(batch='批次16',numeric_facts=2447,materials=225),dict(batch='批次17',numeric_facts=3078,materials=289),dict(batch='批次18',numeric_facts=3078,materials=289),dict(batch='批次19',numeric_facts=3555,materials=327),dict(batch='批次20',numeric_facts=3854,materials=367),dict(batch='批次21',numeric_facts=3854,materials=367),dict(batch='批次22',numeric_facts=4089,materials=405),dict(batch='批次23',numeric_facts=4236,materials=422),dict(batch='批次24',numeric_facts=4459,materials=447),dict(batch='批次25',numeric_facts=summary['cumulative_numeric_material_facts'],materials=summary['cumulative_materials'])]
    for r in progress:r['batch_short']=r['batch'].removeprefix('批次')
    query('batch_progress',progress,['literature_pool_v1.summary.json','literature_pool_v2.summary.json','literature_pool_v3.summary.json','literature_pool_v4.summary.json','literature_pool_v5.summary.json','literature_pool_v6.summary.json','literature_pool_v7.summary.json','literature_pool_v8.summary.json'],
      'SELECT COUNT(*) FROM material_facts WHERE value IS NOT NULL; -- 二十五个封版版本的累计快照',
      '同一证据层二十五个批次累计快照；材料事实与测试行分计，不内插每日进度。')
    historical_summaries=[]
    for review_root in sorted(ROOT.glob('文献全量利用复核_*')):
        historical_summaries.extend(sorted(review_root.glob('*/summary.json')))
        if (review_root/'summary.json').is_file():historical_summaries.append(review_root/'summary.json')
    queries['batch_progress']['source']['files']=[dict(name=p.relative_to(ROOT).as_posix())for p in historical_summaries]
    result=dict(id=existing['id'],surface='dashboard',title='文献提取与补正进度',generatedAt=now,status='reviewed_local_snapshot',buildStatus=args.build_status,filters=[],queries=queries)
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(dict(snapshot=str(target.relative_to(ROOT)),queries={k:len(v['rows']) for k,v in queries.items()},buildStatus=args.build_status),ensure_ascii=False))
if __name__=='__main__':main()
