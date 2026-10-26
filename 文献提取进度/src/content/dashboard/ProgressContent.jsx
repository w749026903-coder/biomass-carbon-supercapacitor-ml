import React from 'react';
import {useDataApp,useSectionFilters,Filters,MetricCard,EvidenceChart,DataComponent,DataTable,Section} from '../../data-app-public.jsx';
import './literature-progress.css';
const f=(field,label)=>({field,label});
const factCols=[f('sample_name','样品'),f('parameter','参数'),f('quantity','数值'),f('unit','单位'),f('status_label','状态'),f('evidence','原文位置')];
const capCols=[f('sample_name','样品'),f('method','方法'),f('system','配置'),f('electrolyte','电解液'),f('quantity','数值'),f('unit','单位'),f('basis_label','归一化口径'),f('current_label','报告电流'),f('scan_rate_mV_s','扫描 mV/s'),f('status_label','用途'),f('evidence','原文位置')];
function EvidenceTable({id,title,queryId,columns,scope}){
 const {reviewedRows}=useDataApp();
 const p=scope?scope.componentProps(queryId,[]):{displayRows:reviewedRows(queryId),sourceRows:reviewedRows(queryId)};
 return <DataComponent variant="card" id={id} title={title} kind="table" queryId={queryId} {...p}><DataTable label={title} rows={p.displayRows} columns={columns}/></DataComponent>;
}
export function DashboardContent(){
 const {reviewedRows}=useDataApp(),rows=reviewedRows('overview'),h=rows[0]??{};
 const scope=useSectionFilters([{id:'doi',field:'doi',label:'论文 DOI',defaultValue:'all',queryIds:['material_facts','capacitances']},{id:'method',field:'method',label:'比电容方法',defaultValue:'all',queryIds:['capacitances']}],{},{id:'literature-evidence'});
 const auxiliaryScope=useSectionFilters([{id:'task',field:'task',label:'辅助目标',defaultValue:'all',queryIds:['auxiliary_inputs']}],{},{id:'auxiliary-gcd-inputs'});
 const desScope=useSectionFilters([{id:'des-task',field:'task',label:'DES目标',defaultValue:'DES保持率均值',queryIds:['des_inputs']}],{},{id:'des-reported-inputs'});
 const palmScope=useSectionFilters([{id:'assembly',field:'assembly_label',label:'器件形式',defaultValue:'all',queryIds:['palm_electrical']},{id:'grain',field:'grain_label',label:'报告层级',defaultValue:'all',queryIds:['palm_electrical']}],{},{id:'palm-electrical-scope'});
 const curveScope=useSectionFilters([{id:'curve-x-kind',field:'x_kind',label:'采样横轴',defaultValue:'all',queryIds:['bounded_curve_samples']}],{},{id:'bounded-curve-scope'});
 return <article className="literature-progress">
  <p className="progress-intro" data-editable-id="extraction-introduction" data-editable-narrative="true">全量目标尚未完成，按用户续行逐批推进：先充分提取已有文献，再确定模型路线。材料事实、测试报告、分用途输入与正式循环准入分别计数。</p>
  <div className="extraction-cards">
   <MetricCard id="material-numbers" title="材料数值单元" queryId="overview" value={h.cumulative_numeric_material_facts} displayRows={rows} sourceRows={rows} description={`累计${h.cumulative_materials}个材料登记，含前驱体、对照与待核名称`}/>
   <MetricCard id="cap-numbers" title="比电容数值单元" queryId="overview" value={h.numeric_capacitance_values} displayRows={rows} sourceRows={rows} description={`${h.capacitance_records}条报告；复述、竞争和换算不当独立样本`}/>
   <MetricCard id="pending-corrections" title="原固定队列仍待证" queryId="overview" value={h.fixed_pending} displayRows={rows} sourceRows={rows} description="原39条中1条完成；新文献与特征冻结不抵扣"/>
  </div>
  <Section id="corpus-overview-title" title="全库排查范围" columns={2}>
   <EvidenceChart id="identity-catalogue" queryId="identity_states" title="初始480条身份匹配盘点" rows={reviewedRows('identity_states')} sourceRows={reviewedRows('identity_states')} variant="card" spec={{type:'bar',x:'category',y:'count',showXAxisLabel:false,showYAxisLabel:false,valueDecimals:0}} height={245}/>
   <EvidenceChart id="curated-growth" queryId="batch_progress" title="各批次的累计材料数值" rows={reviewedRows('batch_progress')} sourceRows={reviewedRows('batch_progress')} variant="card" spec={{type:'bar',x:'batch',y:'numeric_facts',showXAxisLabel:false,showYAxisLabel:false,valueDecimals:0}} height={245}/>
  </Section>
  <DataComponent id="scope-boundaries" kind="custom" title="当前范围与下一步" queryId="overview" displayRows={rows} sourceRows={rows} variant="plain">
   <div className="scope-note" data-reviewed-rows="true">
    <p><strong>{h.raw_table_candidates} 个原始表候选：</strong>本流程已处理指定范围 {h.raw_candidates_touched} 个，尚未进入处理 {h.raw_candidates_untouched} 个。已处理不代表整篇或全部参数完成。</p>
    <p>历史已有 <strong>{h.historical_selected_fact_references} 项材料属性</strong>另行对账，其中 {h.historical_fact_references_with_same_source_table_candidates} 项存在同源表线索；不能与本页新增层直接相加。目录、论文、材料、数值单元与训练样本分母不同。</p>
    <p>原2023—2026队列：三电极循环 <strong>{h.formal_main_rows} 条 / {h.formal_main_sources} 来源</strong>，双电极 <strong>{h.formal_2e_rows} 条 / {h.formal_2e_sources} 来源</strong>。循环v0.22上一批核定{h.last_cycling_release_purpose_admissions}项用途（{h.new_endpoint_records}新记录、{h.promoted_existing_endpoints}旧ID补证），全部观察{h.cycling_observations}条；本批文献新增正式循环准入{h.new_formal_cycling_admissions}项。原固定38待证保持，真实拟合 {h.model_fits} 次。</p>
    <p>跨年份视图纳入逐测试核定的2018年棉花及2019年NFAC：三电极 <strong>{h.all_years_3e_rows} 条 / {h.all_years_3e_sources} 来源</strong>，双电极 <strong>{h.all_years_2e_rows} 条 / {h.all_years_2e_sources} 来源</strong>。原日期规则保持，不同队列分别报告。</p>
    <p>已有 <strong>{h.auxiliary_purpose_reviewed_input_rows} 条辅助GCD输入</strong>按四个目标分别核定：普通三电极水系 {h.auxiliary_aqueous_3e_GCD_rows} 条、双电极器件总质量 {h.auxiliary_aqueous_2e_GCD_rows} 条、天然矿物残留碳三电极 {h.auxiliary_native_mineral_3e_GCD_rows} 条、双电极作者两倍系数 {h.auxiliary_author_factor2_2e_GCD_rows} 条。合计 {h.auxiliary_independent_DOI_groups} 个DOI组，输入预检通过不表示泛化精度已得到证明。</p>
    <p>另有 <strong>{h.DES_purpose_reviewed_rows_per_target} 组DES样品</strong>，分别通过保持率均值和首圈比电容均值用途审查，合计仅 {h.DES_independent_DOI_groups} 个DOI。两个目标各12行，不当24次独立实验，不混入普通水系循环集。</p>
    <p>棕榈壳SI新增 <strong>{h.new_Palm_individual_electrical_coins} 个器件 / {h.new_Palm_individual_electrical_conditions} 组工况</strong>，表格共提取{h.new_Palm_response_records}项EIS及电学响应；汇总、单件、多指标与串并联分别保存，同一来源不能拆作独立论文。作者汇总与SI明细的差异列在下方对账。</p>
    <p>第十一批增加 <strong>{h.new_numeric_material_facts} 项材料数值、{h.new_capacitance_reports} 条比电容报告</strong>，核定13条青豌豆皮/水葫芦/红茶辅助GCD输入。原{h.cumulative_bounded_curve_samples}有界图点、{h.peer_model_numeric_cells}个同行参数、15格争议特征冻结及1条复合循环用途保持。两个Tondolo工作有明确复用关系，验证时须归入同一家族。</p>
   </div>
  </DataComponent>
  <Section id="sources-title" title="已提取来源与范围"><EvidenceTable id="reviewed-sources" title="来源清单 · 指定表格已核定" queryId="source_summary" columns={[f('doi','DOI'),f('title','论文'),f('batch','批次'),f('materials','材料数'),f('numeric_facts','数值单元'),f('scope','用途边界')]}/></Section>
  <Section id="evidence-title" title="材料与测试数据检索" filters={<Filters {...scope.filterProps}/>}>
   <EvidenceTable id="material-evidence" title="材料属性 · 按方法保留原值" queryId="material_facts" columns={factCols} scope={scope}/>
   <EvidenceTable id="capacitance-evidence" title="比电容 · 每种工况分别记录" queryId="capacitances" columns={capCols} scope={scope}/>
  </Section>
  <Section id="batch11-review-title" title="第十一批 · 多样品、原图裁决与前作复用">
   <EvidenceTable id="batch11-sources-table" title="四篇原始研究 · 指定范围与剩余工作" queryId="batch11_sources" columns={[f('doi','DOI'),f('scope','已核范围'),f('remaining','仍待提取')]}/>
   <EvidenceTable id="batch11-decisions-table" title="8项证据处置 · 已解与未决分开" queryId="batch11_decisions" columns={[f('doi','DOI'),f('decision_id','核验项'),f('decision','依据与处理')]}/>
   <EvidenceTable id="source-families-table" title="前作复用 · 两DOI同一家族留出" queryId="source_families" columns={[f('doi','本论文'),f('related_doi','前作'),f('family','隔离家族'),f('basis','原文明确依据')]}/>
   <EvidenceTable id="batch11-quantity-audits-table" title="吸附物料衡算与Raman组分核查" queryId="batch11_quantity_audits" columns={[f('sample','材料'),f('kind_label','检查类型'),f('model_label','拟合模型'),f('initial_ppm','初始 mg/L'),f('reported_fitted_Qe_mg_g','作者拟合Qe mg/g'),f('maximum_from_stated_protocol_mg_g','给定投料上限 mg/g'),f('computed_sum','组分合计 %'),f('status_label','核查结论')]}/>
  </Section>
  <Section id="batch10-review-title" title="第十批 · 自身证据与同行方法">
   <EvidenceTable id="batch10-sources-table" title="四篇原始研究 · 完成范围与剩余任务" queryId="batch10_sources" columns={[f('doi','DOI'),f('classification','类别'),f('tables','主表候选'),f('scope','已核范围'),f('remaining','仍待提取')]}/>
   <EvidenceTable id="peer-model-review-table" title="同行ANN审查 · 预测目标与验证边界" queryId="peer_model_review" columns={[f('doi','DOI'),f('target','目标'),f('samples','样本口径'),f('split','拆分方式'),f('validation_R2','作者验证R²'),f('parameters','参数数值数'),f('data_status','原始数据取得情况'),f('limits','适用边界')]}/>
   <EvidenceTable id="batch10-audits-table" title="28项数值核验 · 原报告与派生检查分开" queryId="batch10_audits" columns={[f('doi','DOI'),f('audit_id','核验项'),f('kind','类型'),f('details','证据与处置')]}/>
   <EvidenceTable id="cycling-cohorts-table" title="循环队列 · 原年份与跨年份分别调用" queryId="cycling_cohorts" columns={[f('profile','调用视图'),f('year_scope','年份范围'),f('rows','端点数'),f('sources','来源数'),f('rule','比较边界')]}/>
   <EvidenceTable id="new-cycle-admissions-table" title="v0.22核定5用途 · 3新记录与2旧ID补证" queryId="new_cycle_admissions" columns={[f('sample_name','样品'),f('source_year_display','年份'),f('electrolyte_label','电解液'),f('retention_pct','保持率 %'),f('cycle_count','圈数'),f('reported_current_A_g','作者 A/g'),f('cycle_voltage_lower_V','下限 V'),f('cycle_voltage_upper_V','上限 V'),f('BET_m2_g','自身BET m²/g'),f('profile_label','准入视图'),f('review_note','选值依据')]}/>
  </Section>
  <Section id="systematic-series-title" title="第九批 · 多样品系列与原图复核">
   <EvidenceTable id="source-classification-table" title="四个来源的身份与用途" queryId="source_classifications" columns={[f('doi','DOI'),f('classification','范围'),f('basis','原文依据'),f('remaining','尚未完成的范围')]}/>
   <EvidenceTable id="systematic-scopes-table" title="32个材料登记 · 同配方名称与前驱体分开" queryId="systematic_material_scopes" columns={[f('doi','DOI'),f('sample_name','样品'),f('material_class','材料类别'),f('material_stage','阶段'),f('aliases','明确同条件别名'),f('independence','计数边界')]}/>
   <EvidenceTable id="current-feature-freezes-table" title="当前循环输入 · 15个特征冲突已冻结" queryId="current_feature_freezes" columns={[f('sample_name','样品'),f('parameter','特征'),f('field_name','兼容字段'),f('table_value','原表值'),f('figure_value','原图值'),f('unit','单位'),f('selected_display','当前选值')]}/>
   <EvidenceTable id="series-arithmetic-table" title="倍率与成本对账 · 不覆盖作者原值" queryId="series_arithmetic_audits" columns={[f('sample_name','样品'),f('kind','检查类型'),f('reported_rate_retention_pct','作者倍率保持率 %'),f('computed_from_printed_capacitances_pct','印刷电容算术比 %'),f('overlaps_reported_rounding','印刷精度区间相容'),f('reported_SUM_CNY','作者成本合计 CNY'),f('computed_printed_component_sum_CNY','分项算术合计 CNY')]}/>
  </Section>
  <Section id="auxiliary-title" title="已核定的辅助比电容输入" filters={<Filters {...auxiliaryScope.filterProps}/>}><EvidenceTable id="auxiliary-gcd-table" title="四个辅助目标分别调用 · 同DOI整组隔离" queryId="auxiliary_inputs" scope={auxiliaryScope} columns={[f('doi','DOI'),f('sample_name','样品'),f('task','任务'),f('capacitance_F_g','比电容 F/g'),f('current_A_g','电流 A/g'),f('electrolyte','电解液'),f('BET_surface_area_m2_g','BET m²/g'),f('EDX_C_at_pct','EDX C原子%'),f('mesopore_volume_cm3_g','介孔容 cm³/g')]}/>
  </Section>
  <Section id="des-input-title" title="DES的两个独立均值目标" filters={<Filters {...desScope.filterProps}/>}>
   <EvidenceTable id="des-input-table" title="同12样品 · 单一来源整体留出" queryId="des_inputs" scope={desScope} columns={[f('sample_name','样品'),f('task','目标'),f('target_value','作者均值'),f('target_unit','单位'),f('target_reported_uncertainty','作者±量'),f('cycle_count','圈数'),f('current_A_g','报告 A/g'),f('BET_surface_area_m2_g','BET m²/g'),f('XPS_N_at_pct','XPS N原子%'),f('carbonization_temperature_C','碳化 ℃'),f('carbonization_duration_h','碳化 h'),f('window_label','电压证据'),f('purpose_status','用途资格')]}/>
  </Section>
  <Section id="si-response-title" title="SI中的峰参数与测试响应">
   <EvidenceTable id="eis-response-table" title="糖原EIS拟合量 · 作为响应保存" queryId="eis_responses" columns={[f('sample_name','样品'),f('metric','参数'),f('value','均值'),f('reported_uncertainty','作者±量'),f('unit','单位'),f('uncertainty_description','作者不确定量定义'),f('locator','原文位置')]}/>
   <EvidenceTable id="xrd-peaks-table" title="糖原XRD原峰 · 仅(002)峰绑定层间距" queryId="xrd_peaks" columns={[f('sample_name','样品'),f('peak_number','峰序号'),f('two_theta_deg','2θ °'),f('d_A','间距 Å'),f('FWHM_deg','FWHM °'),f('integrated_intensity_counts_deg','积分强度 counts·°'),f('locator','原文位置')]}/>
  </Section>
  <Section id="palm-audit-title" title="棕榈壳 · 作者统计与SI明细对账">
   <EvidenceTable id="palm-statistics-table" title="8组统计对账 · 列表重算不覆盖原报告" queryId="palm_statistics" columns={[f('sample_name','样品'),f('system','配置'),f('reported_mean_F_g','作者均值 F/g'),f('arithmetic_mean_of_listed_reports','列表均值 F/g'),f('reported_SD_F_g','作者S F/g'),f('arithmetic_SD_of_listed_reports','列表S F/g'),f('listed_measurement_reports','列出报告数'),f('SI_footnote_n','脚注n'),f('explicit_repeat_reports','明示重复数')]}/>
  </Section>
  <Section id="palm-electrical-title" title="棕榈壳 · 单器件与串并联工况" filters={<Filters {...palmScope.filterProps}/>}>
   <EvidenceTable id="palm-electrical-table" title="电学响应 · 按器件和工况绑定" queryId="palm_electrical" scope={palmScope} columns={[f('sample_name','材料'),f('printed_coin_id','印刷器件号'),f('printed_coin_pair','串联器件对'),f('assembly_label','形式'),f('grain_label','层级'),f('voltage_limit_per_coin_V','单器件 V'),f('current_A','电流 A'),f('experimental_capacitance_F','实验电容 F'),f('energy_efficiency_pct','能量效率 %'),f('specific_energy_Wh_kg','能量 Wh/kg'),f('specific_power_W_kg','功率 W/kg'),f('locator','原文位置')]}/>
  </Section>
  <Section id="new-source-scope-title" title="洋葱壳与生物炭复合体系的类别和核查">
   <EvidenceTable id="new-material-scope-table" title="15种新登记 · 原料类别和前驱体阶段分开" queryId="new_material_scopes" columns={[f('doi','DOI'),f('sample_name','样品'),f('material_class','材料类别'),f('route','制备路线'),f('F_treatment','F处理'),f('final_fraction_status','最终组分状态')]}/>
   <EvidenceTable id="onion-raman-audit-table" title="洋葱壳Raman · 原报告与算术比值并存" queryId="onion_raman_audit" columns={[f('sample','样品'),f('printed_ID','原D强度'),f('printed_IG','原G强度'),f('reported_ID_IG','报告ID/IG'),f('computed_ID_IG','强度算术比'),f('reported_I2D_IG','报告2D/G'),f('computed_I2D_IG','2D/G算术比')]}/>
  </Section>
  <Section id="curve-evidence-title" title="原文曲线采样 · 近似界限单独保留" filters={<Filters {...curveScope.filterProps}/>}>
   <EvidenceChart id="onion-absolute-cycle-chart" title="洋葱壳绝对电容（F/g）· 2 A/g原图采样" queryId="onion_cycle_curves" rows={reviewedRows('onion_cycle_curves')} sourceRows={reviewedRows('onion_cycle_curves')} variant="card" spec={{type:'line',x:'cycle_coordinate',y:'specific_capacitance_F_g',series:'sample_label',stackable:false,showXAxisLabel:false,showYAxisLabel:false,valueDecimals:1}} height={330}/>
   <EvidenceTable id="bounded-curve-table" title="128个图点 · 原图/坐标/像素误差可查" queryId="bounded_curve_samples" scope={curveScope} columns={[f('sample_name','样品'),f('x_kind','横轴含义'),f('x_value','横轴值'),f('y_value','电容 F/g'),f('y_uncertainty','读图界限 ±F/g'),f('error_kind','界限定义'),f('curve_group','曲线组')]}/>
   <EvidenceTable id="composite-cycle-table" title="复合体系循环输入 · 1条/1来源，非普通主集" queryId="composite_cycle_inputs" columns={[f('sample_name','样品'),f('cycle_count','圈数'),f('reported_current_A_g','作者 A/g'),f('target_retention_pct','保持率 %'),f('BET_surface_area_m2_g','BET m²/g'),f('biochar_carbonization_temperature_C','生物炭 ℃'),f('PAN_carbonization_temperature_C','PAN ℃'),f('final_aerogel_activation_temperature_C','最终活化 ℃'),f('final_biochar_fraction','最终生物炭份额')]}/>
  </Section>
  <Section id="issues-title" title="争议与待办">
   <EvidenceTable id="formal-2e-table" title="正式双电极循环数据 · 分来源调用" queryId="formal_2e" columns={[f('sample_name','样品'),f('source_group','来源组'),f('cycle_count','圈数'),f('reported_current_A_g','作者 A/g'),f('electrolyte','电解液'),f('concentration_mol_L','浓度 M'),f('cycle_voltage_lower_V','下限 V'),f('cycle_voltage_upper_V','上限 V'),f('BET_m2_g','BET m²/g'),f('retention_pct','保持率 %')]}/>
   <EvidenceTable id="cycling-candidates-table" title="循环候选与当前准入链接" queryId="cycling_candidates" columns={[f('doi','DOI'),f('sample','样品'),f('system','配置'),f('metric','响应指标'),f('electrolyte','电解液'),f('current_A_g','循环 A/g'),f('cycle_count','圈数'),f('retention_display','保持率 % / 限值'),f('retention_uncertainty','作者±量'),f('status','准入阶段'),f('formal_endpoint_id','正式端点'),f('locator','证据位置')]}/>
   <EvidenceTable id="scientific-issues" title="科学争议原值与处理边界" queryId="issues" columns={[f('doi','DOI'),f('sample','样品'),f('issue','问题类型'),f('action','处置'),f('details','竞争证据')]}/>
   <EvidenceTable id="full-table-queue" title="959个表候选的处理队列" queryId="table_queue" columns={[f('table_id','候选ID'),f('caption','表题'),f('locator','原定位'),f('raw_rows','原始行数'),f('role','原始角色'),f('state','当前处理范围')]}/>
  </Section>
 </article>;
}
