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
 return <article className="literature-progress">
  <p className="progress-intro" data-editable-id="extraction-introduction" data-editable-narrative="true">全量目标尚未完成，按用户续行逐批推进：先充分提取已有文献，再确定模型路线。材料事实、测试报告、分用途输入与正式循环准入分别计数。</p>
  <div className="extraction-cards">
   <MetricCard id="material-numbers" title="材料数值单元" queryId="overview" value={h.cumulative_numeric_material_facts} displayRows={rows} sourceRows={rows} description={`证据层累计${h.cumulative_materials}种材料，含对照与参考体系`}/>
   <MetricCard id="cap-numbers" title="比电容数值单元" queryId="overview" value={h.numeric_capacitance_values} displayRows={rows} sourceRows={rows} description={`${h.capacitance_records}条报告；复述、竞争和换算不当独立样本`}/>
   <MetricCard id="pending-corrections" title="原固定队列仍待证" queryId="overview" value={h.fixed_pending} displayRows={rows} sourceRows={rows} description="原39条中1条完成；本批新增正式准入0"/>
  </div>
  <Section id="corpus-overview-title" title="全库排查范围" columns={2}>
   <EvidenceChart id="identity-catalogue" queryId="identity_states" title="480个身份条目的匹配状态" rows={reviewedRows('identity_states')} sourceRows={reviewedRows('identity_states')} variant="card" spec={{type:'bar',x:'category',y:'count',showXAxisLabel:false,showYAxisLabel:false,valueDecimals:0}} height={245}/>
   <EvidenceChart id="curated-growth" queryId="batch_progress" title="各批次的累计材料数值" rows={reviewedRows('batch_progress')} sourceRows={reviewedRows('batch_progress')} variant="card" spec={{type:'bar',x:'batch',y:'numeric_facts',showXAxisLabel:false,showYAxisLabel:false,valueDecimals:0}} height={245}/>
  </Section>
  <DataComponent id="scope-boundaries" kind="custom" title="当前范围与下一步" queryId="overview" displayRows={rows} sourceRows={rows} variant="plain">
   <div className="scope-note" data-reviewed-rows="true">
    <p><strong>{h.raw_table_candidates} 个原始表候选：</strong>本流程已处理指定范围 {h.raw_candidates_touched} 个，尚未进入处理 {h.raw_candidates_untouched} 个。已处理不代表整篇或全部参数完成。</p>
    <p>历史已有 <strong>{h.historical_selected_fact_references} 项材料属性</strong>另行对账，其中 {h.historical_fact_references_with_same_source_table_candidates} 项存在同源表线索；不能与本页新增层直接相加。目录、论文、材料、数值单元与训练样本分母不同。</p>
    <p>正式循环主集仍 <strong>{h.formal_main_rows} 条 / {h.formal_main_sources} 来源</strong>。下一步优先生物质自身多样品表、制备阶段和多工况曲线；协议冲突保留竞争证据。本轮真实拟合 {h.model_fits} 次。</p>
    <p>已有 <strong>{h.auxiliary_purpose_reviewed_input_rows} 条辅助GCD输入</strong>按四个目标分别核定：普通三电极水系 {h.auxiliary_aqueous_3e_GCD_rows} 条、双电极器件总质量 {h.auxiliary_aqueous_2e_GCD_rows} 条、天然矿物残留碳三电极 {h.auxiliary_native_mineral_3e_GCD_rows} 条、双电极作者两倍系数 {h.auxiliary_author_factor2_2e_GCD_rows} 条。合计 {h.auxiliary_independent_DOI_groups} 个DOI组，输入预检通过不表示泛化精度已得到证明。</p>
   </div>
  </DataComponent>
  <Section id="sources-title" title="已提取来源与范围"><EvidenceTable id="reviewed-sources" title="来源清单 · 指定表格已核定" queryId="source_summary" columns={[f('doi','DOI'),f('title','论文'),f('batch','批次'),f('materials','材料数'),f('numeric_facts','数值单元'),f('scope','用途边界')]}/></Section>
  <Section id="evidence-title" title="材料与测试数据检索" filters={<Filters {...scope.filterProps}/>}>
   <EvidenceTable id="material-evidence" title="材料属性 · 按方法保留原值" queryId="material_facts" columns={factCols} scope={scope}/>
   <EvidenceTable id="capacitance-evidence" title="比电容 · 每种工况分别记录" queryId="capacitances" columns={capCols} scope={scope}/>
  </Section>
  <Section id="auxiliary-title" title="已核定的辅助比电容输入" filters={<Filters {...auxiliaryScope.filterProps}/>}><EvidenceTable id="auxiliary-gcd-table" title="四个辅助目标分别调用 · 同DOI整组隔离" queryId="auxiliary_inputs" scope={auxiliaryScope} columns={[f('doi','DOI'),f('sample_name','样品'),f('task','任务'),f('capacitance_F_g','比电容 F/g'),f('current_A_g','电流 A/g'),f('electrolyte','电解液'),f('BET_surface_area_m2_g','BET m²/g'),f('EDX_C_at_pct','EDX C原子%'),f('mesopore_volume_cm3_g','介孔容 cm³/g')]}/>
  </Section>
  <Section id="issues-title" title="争议与待办">
   <EvidenceTable id="scientific-issues" title="科学争议原值与处理边界" queryId="issues" columns={[f('doi','DOI'),f('sample','样品'),f('issue','问题类型'),f('action','处置'),f('details','竞争证据')]}/>
   <EvidenceTable id="full-table-queue" title="959个表候选的处理队列" queryId="table_queue" columns={[f('table_id','候选ID'),f('caption','表题'),f('locator','原定位'),f('raw_rows','原始行数'),f('role','原始角色'),f('state','当前处理范围')]}/>
  </Section>
 </article>;
}
