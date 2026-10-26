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
    raman={'Raman_D_position_cm_inv':'Raman D峰位','Raman_G_position_cm_inv':'Raman G峰位','Raman_I2D_reported_intensity':'Raman 2D报告强度','Raman_ID_reported_intensity':'Raman D报告强度','Raman_IG_reported_intensity':'Raman G报告强度','Raman_I2D_IG':'Raman 2D/G报告比'}
    if f in raman:return raman[f]
    if f=='XPS_C_O_reported_ratio':return 'XPS C/O报告比值'
    if f=='XPS_O_C_reported_ratio':return 'XPS O/C报告比值'
    if f.startswith('XPS_'):
        body=f[4:].replace('_at_pct',' 原子百分比').replace('_wt_pct',' 质量百分比').replace('_reported_ratio',' 报告比值').replace('_envelope_pct',' 包络内比例').replace('_binding_energy_eV',' 峰位 eV').replace('_reported_FWHM',' FWHM（表未印单位）').replace('_peak',' 峰')
        return 'XPS '+body.replace('_double_','=').replace('_','–')
    if f.startswith('EDS_'):return 'EDS '+f[4:].replace('_reported_pct',' 百分比（口径未知）').replace('_at_pct',' 原子百分比')
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
    ap=argparse.ArgumentParser();ap.add_argument('--build-status',choices=['creating','updating','complete'],default='updating');args=ap.parse_args()
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
        for r in facts:r.update(parameter=label(r['field_name']),quantity=r['value'],evidence=r['locator'],status_label=('未检出（ND），限值未知，不填0' if 'not_detected' in r['review_status'] else ('原印数字格式异常，待核' if 'malformed' in r['review_status'] else ('低于误差，空值' if 'censored' in r['review_status'] else '原文横杠/未报告，不填0'))) if r['value'] is None else ('冲突冻结' if 'conflict' in r['review_status'] else '作者近似报告，非精确值' if 'approximate' in r['review_status'] else '已提取，按用途调用'))
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
        query('material_facts',facts,['material_facts','materials','table_source_links','source_documents'],
          'SELECT f.*,m.doi,m.sample_name,d.path,d.sha256,l.locator FROM material_facts f JOIN materials m USING(material_key) JOIN table_source_links l USING(table_key) JOIN source_documents d USING(document_key);',
          '材料×参数×自身表单元；受限值为null，不同测法不拼成一个参数。',['原始层不自动取得训练资格；独立辅助用途视图另行审查。source_path返回实际正文或SI。'])
        query('capacitances',caps,['capacitance_observations','materials','table_source_links'],
          'SELECT x.*,m.doi,m.sample_name,l.locator FROM capacitance_observations x JOIN materials m USING(material_key) JOIN table_source_links l USING(table_key);',
          '材料×方法×电解液×工况×自身报告表单元，不同配置、归一化和单位分开。',[f"{summary['capacitance_records']}报告含{summary['numeric_capacitance_values']}数值、2未报告；复述、竞争、换算、参考和复合体系不能当独立样本相加。",'CV速率不当电流；面积电流不猜算A/g。辅助资格不等于循环保持率准入。'])
        query('auxiliary_inputs',auxiliary,['auxiliary_reported_GCD_v3','auxiliary_gcd_reviews_v3','material_facts','synthesis_stages_v3'],
          'SELECT * FROM auxiliary_reported_GCD_v3 ORDER BY purpose,source_group,sample_name,current_A_g;',
          '146条普通三电极、5条器件总质量、5条天然矿物残留碳三电极、6条作者两倍系数双电极，四目标分开。EDX与XPS、原方向Raman和缺失掩码分别保留。',['合计14个DOI组；普通三电极13组，其余每任务各1组；不是独立性或泛化性能证明。','新青豌豆3、水葫芦4、红茶6行与各自循环/曲线/其它响应同组；Tondolo与前作另有显式家族隔离。','输入预检通过不表示循环准入或精度改善；原年份三电极主集仍43/31，无新拟合。'])
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
            r=item['reading'];curve_rows.append(dict(r,reading_id=item['reading_id'],doi=item['doi'],sample_name=item['sample_name'],source_path=item['source_path'],source_sha256=item['source_sha256'],x_kind={'plotted_cycle_coordinate':'循环图坐标 N','scan_rate_mV_s':'扫描速率 mV/s','reported_current_A_g':'报告电流 A/g'}[r['x_name']],error_kind='标记像素范围＋2px校准界限；非统计置信区间'))
        query('bounded_curve_samples',curve_rows,['curve_samples_v8','source_documents','curve_samples.json'],
          'db.sampled_curves() -- source images, axes, pixel extents and uncertainty preserved',
          '7原图面板/23曲线组的128个有界采样，非128个独立训练样本。',
          ['近似图像读取与作者精确报告分开；横轴分别是圈坐标、电流或扫描速率，不拼为一个工况。','原图误差由局部标记高度和校准像素给出，不假称SD、SEM或95%CI；同DOI所有曲线/标签整组隔离。'])
        cycle_rows=[dict(r,cycle_coordinate=r['x_value'],specific_capacitance_F_g=r['y_value'],sample_label='COH（550℃未活化）' if r['sample_name']=='COH_550C' else 'GLC-OH '+r['sample_name'][3:6]+'℃') for r in curve_rows if r['x_name']=='plotted_cycle_coordinate']
        query('onion_cycle_curves',cycle_rows,['curve_samples_v8','Onion_SI_image2.jpeg'],
          'SELECT reading_json FROM curve_samples_v8 WHERE document_key="Onion_SI_cycle"; -- 4curves sampled at7plotted coordinates',
          '2 A/g下绝对电容C(F/g)随图中循环坐标变化，不是已经归一化的保持率。',
          ['图点近似，误差可在128点采样表/来源预览中查；所选坐标不是作者已确认的第1圈参照。','正文<95%与绝对C(N)仍未协调；未把图中电容或任意起点转换成精确保持率。'])
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
        query('source_families',relations11,['source_relations_v11'],'db.source_relations(); db.isolation_group(doi)','原文明确复用的两篇工作归入同一验证家族；不将复用表征当独立样本。')
        audits11=json.loads((folder/'quantity_audits.json').read_text('utf8'))
        for r in audits11:
            r['status_label']='协议或拟合不一致，仍未解决'if r['status'].startswith('unresolved')else'原印精度保留，不归一化'
            r['kind_label']='拟合容量与可用染料量核对'if r['kind']=='fitted_Qe_vs_stated_available_dye'else'Raman分峰百分比合计'
            r['model_label']={'pseudo_first_order':'准一级动力学','pseudo_second_order':'准二级动力学'}.get(r.get('model'),'—')
        query('batch11_quantity_audits',audits11,['quantity_audits.json','transcribed_rows'],'C0_mg_L * volume_L / adsorbent_g; compare to author fitted Qe, not new measurement','6项吸附拟合与给定物料衡算矛盾，另2项Raman百分比合计；算术核验不改原报告。')
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
    overview=[dict(summary,goal_status=active['app_goal_status_last_confirmed'],formal_main_rows=len(main_rows),formal_main_sources=len({group(r)for r in main_rows}),formal_2e_rows=len(two_rows),formal_2e_sources=len({group(r)for r in two_rows}),all_years_3e_rows=len(all_years_3e),all_years_3e_sources=len({group(r)for r in all_years_3e}),all_years_2e_rows=len(all_years_2e),all_years_2e_sources=len({group(r)for r in all_years_2e}),new_formal_cycling_admissions=cycle_summary.get('new_purpose_admissions',0),last_cycling_release_purpose_admissions=cycle_summary.get('new_purpose_admissions',0),new_endpoint_records=cycle_summary.get('new_endpoints',0),promoted_existing_endpoints=cycle_summary.get('promoted_existing_endpoints',0),linked_candidates=len(links),cycling_observations=observation_count,fixed_goal_records=fixed['fixed_record_count'],fixed_resolved=fixed['scientifically_resolved_in_goal'],fixed_pending=fixed['current_pending'])]
    query('overview',overview,['summary.json','docs/LITERATURE_EXTRACTION_GOAL.json',cycle_pointer['database_file']],
      'SELECT COUNT(*) FROM materials; SELECT COUNT(*) FROM material_facts WHERE value IS NOT NULL; SELECT COUNT(*) FROM capacitance_observations WHERE value IS NOT NULL;',
      '材料数值与比电容报告按当前证据层汇总；循环主集和固定待证另计。',['历史725项与本页新增层重叠未完全对账，不能直接相加。'])
    query('formal_2e',two_rows,['cycling_API.fetch(reported_2e)','profile_membership_v20','immutable_parent_chain'],
      "db.fetch('reported_2e').rows -- versioned read-only API across the immutable parent chain",
      '正式双电极普通水系循环端点；与三电极主集分开，同来源全部标签整体留出。',
      ['原2023—2026年份规则保持；新增Tondolo后30行/24家族。2018/2019早期来源在跨年份视图。','来源家族用于权重和来源折，不作为X预测特征；未执行新拟合。'])
    cohorts=[dict(profile=p,year_scope=year,rows=len(rs),sources=len({group(r)for r in rs}),rule='来源家族用于矩阵/权重/折分；不同队列分别报告')for p,year,rs in [('reported_3e','2023—2026',main_rows),('reported_2e','2023—2026',two_rows),('reported_3e_all_years','已逐测试核定的跨年份',all_years_3e),('reported_2e_all_years','已逐测试核定的跨年份',all_years_2e)]]
    query('cycling_cohorts',cohorts,['cycling_API.fetch','profile_membership_v22'],'db.fetch(profile).feature_matrix() -- no fitting','四个队列分开；跨年份是显式旧主集加早期核定测试，不能与旧模型直接比误差。')
    query('new_cycle_admissions',new_admissions,['reviewed_endpoints_v22','evidence_v22','changes_v22'],'db.fetch(profile); unique endpoint_id with literature_candidate_id_v22','五项用途准入=3新记录+2既有ID补证；不减少原38待证。',['棉花86%争议原值保留；NFAC真实101.7%不裁100；未知质量分母不猜算。'])
    query('cycle23_admissions',cycle23,['reviewed_endpoints_v23','evidence_v23','changes_v23','source_family_rules'],'db.fetch(profile); current rows with literature_candidate_id_v23','2项用途=1新端点+1旧ID晋升；282观察不全是训练数据。',['Tondolo94%/10000/5A/g及红茶98.8%/2000/5A/g逐测试核定；前作同家族全部任务隔离。','红茶2021仅跨年份3E；15格冻结/原38待证保持，无新拟合。'])
    for key in ['overview','formal_2e','cycling_candidates','cycling_cohorts','new_cycle_admissions','cycle23_admissions']:
        source=queries[key]['source'];source['label']='文献v11与当前循环v0.23只读接口'
        source['files'].extend([{'name':cycle_pointer['database_file']},{'name':'data/current_database.json'}])
        source['evidenceFlow'].append('候选当前状态通过不可变父链及literature_links_v22/v23查询；家族规则同时作用于矩阵权重和来源折，既有ID晋升不重复计实验。')
    progress=[dict(batch='批次01',numeric_facts=88,materials=15),dict(batch='批次02',numeric_facts=157,materials=24),dict(batch='批次03',numeric_facts=511,materials=46),dict(batch='批次04',numeric_facts=603,materials=61),dict(batch='批次05',numeric_facts=791,materials=84),dict(batch='批次06',numeric_facts=862,materials=86),dict(batch='批次07',numeric_facts=1055,materials=92),dict(batch='批次08',numeric_facts=1205,materials=107),dict(batch='批次09',numeric_facts=1453,materials=139),dict(batch='批次10',numeric_facts=1645,materials=160),dict(batch='批次11',numeric_facts=summary['cumulative_numeric_material_facts'],materials=summary['cumulative_materials'])]
    query('batch_progress',progress,['literature_pool_v1.summary.json','literature_pool_v2.summary.json','literature_pool_v3.summary.json','literature_pool_v4.summary.json','literature_pool_v5.summary.json','literature_pool_v6.summary.json','literature_pool_v7.summary.json','literature_pool_v8.summary.json'],
      'SELECT COUNT(*) FROM material_facts WHERE value IS NOT NULL; -- 十一个封版版本的独立累计快照',
      '同一证据层十一个批次累计快照，不内插每日进度，不当独立实验数。')
    result=dict(id=existing['id'],surface='dashboard',title='文献提取与补正进度',generatedAt=now,status='reviewed_local_snapshot',buildStatus=args.build_status,filters=[],queries=queries)
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(dict(snapshot=str(target.relative_to(ROOT)),queries={k:len(v['rows']) for k,v in queries.items()},buildStatus=args.build_status),ensure_ascii=False))
if __name__=='__main__':main()
