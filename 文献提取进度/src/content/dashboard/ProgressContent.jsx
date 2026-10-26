import React from 'react';
import {useDataApp,useSectionFilters,Filters,MetricCard,EvidenceChart,DataComponent,DataTable,Section} from '../../data-app-public.jsx';
import './literature-progress.css';
const f=(field,label)=>({field,label});
const factCols=[f('sample_name','样品'),f('parameter','参数'),f('quantity_label','原报数值'),f('unit','单位'),f('status_label','状态'),f('evidence','原文位置')];
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
 const batch12Scope=useSectionFilters([{id:'batch12-target',field:'task',label:'新批次独立目标',defaultValue:'3E体积电容（作者假定密度）',queryIds:['batch12_inputs']}],{},{id:'batch12-target-scope'});
 const furfural14Scope=useSectionFilters([{id:'furfural14-mode',field:'mode_label',label:'糠醛渣标签模式',defaultValue:'点标签：4正文＋42读图',queryIds:['furfural14_inputs']}],{},{id:'furfural14-input-mode'});
 const batch15Scope=useSectionFilters([{id:'batch15-source',field:'doi',label:'批次15来源',defaultValue:'all',queryIds:['batch15_inputs','batch15_components','batch15_decisions']}],{},{id:'batch15-source-scope'});
 const rate18Scope=useSectionFilters([{id:'rate18-purpose',field:'purpose',label:'新倍率用途',defaultValue:'普通碳3E',queryIds:['rate18_inputs']},{id:'rate18-mode',field:'mode',label:'新倍率标签',defaultValue:'作者值＋可读图值',queryIds:['rate18_inputs']},{id:'rate18-scope',field:'plot_scope',label:'新倍率图范围',defaultValue:'淀粉（十材料）',queryIds:['rate18_plot']}],{},{id:'rate18-scope'});
 const batch17Scope=useSectionFilters([{id:'batch17-target',field:'task',label:'批次17目标',defaultValue:'三电极水系GCD',queryIds:['batch17_inputs']}],{},{id:'batch17-target-scope'});
 const rate16Scope=useSectionFilters([{id:'rate16-mode',field:'mode',label:'全样倍率标签模式',defaultValue:'报告值＋读图（95总工况）',queryIds:['rate16_inputs']},{id:'rate16-plot-range',field:'plot_scope',label:'倍率图范围',defaultValue:'花椒皮（5材料）',queryIds:['rate16_plot']}],{},{id:'rate16-mode-scope'});
 return <article className="literature-progress">
  <p className="progress-intro" data-editable-id="extraction-introduction" data-editable-narrative="true">全量目标尚未完成，按用户续行逐批推进：先充分提取已有文献，再确定模型路线。材料事实、测试报告、分用途输入与正式循环准入分别计数。</p>
  <div className="extraction-cards">
   <MetricCard id="material-numbers" title="材料数值单元" queryId="overview" value={h.cumulative_numeric_material_facts} displayRows={rows} sourceRows={rows} description={`累计${h.cumulative_materials}个材料登记，含前驱体、对照与待核名称`}/>
   <MetricCard id="cap-numbers" title="比电容数值单元" queryId="overview" value={h.numeric_capacitance_values} displayRows={rows} sourceRows={rows} description={`${h.capacitance_records}条报告；复述、竞争和换算不当独立样本`}/>
   <MetricCard id="pending-corrections" title="原固定队列仍待证" queryId="overview" value={h.fixed_pending} displayRows={rows} sourceRows={rows} description={`原39条中${h.fixed_resolved}条完成；新候选与特征冻结不抵扣`}/>
   <MetricCard id="graph-expanded-inputs" title="含读图的3E输入" queryId="overview" value={h.expanded_3e_with_graph_rows} displayRows={rows} sourceRows={rows} description={`普通${h.auxiliary_aqueous_3e_GCD_rows}＋显式有界图值169；${h.expanded_3e_with_graph_DOI_groups}DOI，显式用途`}/>
  </div>
  <Section id="corpus-overview-title" title="全库排查范围" columns={2}>
   <EvidenceChart id="identity-catalogue" queryId="identity_states" title="初始480条身份匹配盘点" rows={reviewedRows('identity_states')} sourceRows={reviewedRows('identity_states')} variant="card" spec={{type:'bar',x:'chart_label',y:'count',showXAxisLabel:false,showYAxisLabel:false,valueDecimals:0}} height={245}/>
   <EvidenceChart id="curated-growth" queryId="batch_progress" title="各批次的累计材料数值" rows={reviewedRows('batch_progress')} sourceRows={reviewedRows('batch_progress')} variant="card" spec={{type:'bar',x:'batch_short',y:'numeric_facts',showXAxisLabel:false,showYAxisLabel:false,valueDecimals:0}} height={245}/>
  </Section>
  <DataComponent id="scope-boundaries" kind="custom" title="当前范围与下一步" queryId="overview" displayRows={rows} sourceRows={rows} variant="plain">
   <div className="scope-note" data-reviewed-rows="true">
    <p><strong>{h.raw_table_candidates} 个原始表候选：</strong>本流程已处理指定范围 {h.raw_candidates_touched} 个，尚未进入处理 {h.raw_candidates_untouched} 个。已处理不代表整篇或全部参数完成。</p>
    <p>第十八批新增94普通碳有界倍率工况及11天然含硅碳独立工况，并更正上一批淀粉四单元的原图绑定。六个遮挡标称工况不代填，循环配置未决不强行准入。</p>
    <p>第十七批新增五来源全样品提取：631材料数值、23电容报告。v17封版时普通3E为184条/22DOI；当前计数见上方；新6条水系2E两倍系数和1条有机四倍系数在独立目标下调用。</p>
    <p>历史已有 <strong>{h.historical_selected_fact_references} 项材料属性</strong>另行对账，其中 {h.historical_fact_references_with_same_source_table_candidates} 项存在同源表线索；不能与本页新增层直接相加。目录、论文、材料、数值单元与训练样本分母不同。</p>
    <p>原2023—2026队列：三电极循环 <strong>{h.formal_main_rows} 条 / {h.formal_main_sources} 来源家族</strong>，双电极 <strong>{h.formal_2e_rows} 条 / {h.formal_2e_sources} 家族</strong>。当前循环v0.26补正既有YPAC-1循环电流，新增{h.new_formal_cycling_admissions}项准入、{h.new_endpoint_records}新端点；全部观察仍{h.cycling_observations}条。原固定队列现{h.fixed_pending}条待证，真实拟合 {h.model_fits} 次。</p>
    <p>跨年份视图已逐测试核定2018年棉花、2019年NFAC、2021年红茶及2022年苏铁绒：三电极 <strong>{h.all_years_3e_rows} 条 / {h.all_years_3e_sources} 家族</strong>，双电极 <strong>{h.all_years_2e_rows} 条 / {h.all_years_2e_sources} 家族</strong>。苏铁绒两盐一起留出；原日期规则保持，Tondolo与前作同家族隔离。</p>
    <p>已有 <strong>{h.auxiliary_purpose_reviewed_input_rows} 条辅助GCD输入</strong>按四个目标分别核定：普通三电极水系 {h.auxiliary_aqueous_3e_GCD_rows} 条、双电极器件总质量 {h.auxiliary_aqueous_2e_GCD_rows} 条、天然矿物残留碳三电极 {h.auxiliary_native_mineral_3e_GCD_rows} 条、双电极作者两倍系数 {h.auxiliary_author_factor2_2e_GCD_rows} 条。合计 {h.auxiliary_independent_DOI_groups} 个DOI组，输入预检通过不表示泛化精度已得到证明。</p>
    <p>另有 <strong>{h.DES_purpose_reviewed_rows_per_target} 组DES样品</strong>，分别通过保持率均值和首圈比电容均值用途审查，合计仅 {h.DES_independent_DOI_groups} 个DOI。两个目标各12行，不当24次独立实验，不混入普通水系循环集。</p>
    <p>历史棕榈壳SI的器件、工况、EIS及电学响应继续保留；汇总、单件、多指标与串并联分别保存，数量与原值差异见下方专表，同一来源不能拆作独立论文。</p>
    <p>第十六批已补入花椒全十样品倍率及椰枣叶工况，净新增75个有界近似条件。95次图捕获含一次6A/g双面板复述；94图示工况与19作者锚点去重，加原有CO2对照后，混合模式为95工况。本批历史范围是20作者值与75净新增近似工况；当前普通3E与扩展用途计数见上方，原固定队列现37条待证。</p>
    <p>第十五批新增核读花椒皮籽、椰枣叶两来源：154项材料数值、24条电容报告，20条自身普通3E输入。十样品的材料数据与倍率已对应，连续波形仍待；不把特征条数或多电流行当独立论文。</p>
    <p>第十四批深化糠醛渣 <strong>8材料／48标称倍率工况</strong>：46点标签含原有4正文值和42个新读图条件，另2个被覆盖的点只留区间。它们全部来自同一DOI；不同模式不能相加，不按电流拆成独立论文。2个遮挡空值与原有2个未报告空值分开。</p>
    <p>第十三批增加204项材料数值、55条电容报告：芒果核、废皮革、糠醛渣与商业参考四个指定范围。9条普通3E、4条残留用途分开，商业参考未取得生物质训练资格。5个循环候选中2个已在v0.25准入，其余3个商业参考仍待审。</p>
    <p>第十二批体积与Cs/Cd的29个表达行继续独立调用；Cs/Cd同测试、体积/质量共享来源隔离。有界图捕获现{h.cumulative_bounded_curve_samples}条，其中{h.cumulative_numeric_curve_samples}数值／2仅区间／{h.cumulative_occluded_curve_samples}遮挡；{h.peer_model_numeric_cells}个同行参数另计。12原图检查不代表整篇波形提取完成。</p>
   </div>
  </DataComponent>
  <Section id="sources-title" title="已提取来源与范围"><EvidenceTable id="reviewed-sources" title="来源清单 · 指定表格已核定" queryId="source_summary" columns={[f('doi','DOI'),f('title','论文'),f('batch','批次'),f('materials','材料数'),f('numeric_facts','数值单元'),f('scope','用途边界')]}/></Section>
  <Section id="evidence-title" title="材料与测试数据检索" filters={<Filters {...scope.filterProps}/>}>
   <EvidenceTable id="material-evidence" title="材料属性 · 按方法保留原值" queryId="material_facts" columns={factCols} scope={scope}/>
   <EvidenceTable id="capacitance-evidence" title="比电容 · 每种工况分别记录" queryId="capacitances" columns={capCols} scope={scope}/>
  </Section>
   <Section id="batch19-title" title="第十九批 · 三来源分阶段提取与旧记录补正">
    <p>新增38个分阶段登记、477材料数值及5项空值，来自木质素、蛋米废料、烟草三个来源。原料NMR/GPC与纺丝液黏度单列；PEO投料不作最终组成。4条普通三电极比电容与三个单独的双电极用途分别调用。</p>
    <EvidenceTable id="batch19-inputs-table" title="本批八条分用途输入" queryId="batch19_inputs" columns={[f('doi','DOI'),f('sample','材料'),f('task','目标用途'),f('current','A/g'),f('value','F/g'),f('weight_label','用途内来源权重'),f('missing_features','空特征数')]}/>
    <EvidenceTable id="batch19-decisions-table" title="方法、阶段与异文处置" queryId="batch19_decisions" columns={[f('doi','DOI'),f('action','当前处理')]}/>
    <EvidenceTable id="cycle26-correction-table" title="v0.26 · 既有YPAC-1循环电流补正" queryId="cycle26_correction" columns={[f('sample_name','材料'),f('old_current','旧状态'),f('reported_current_A_g','A/g'),f('retention_pct','保持率 %'),f('cycle_count','循环次数'),f('current_basis','原文依据'),f('status','当前状态')]}/>
    <p>原审查漏掉既有正文中明确的10A/g循环句，现按原端点补正，不新增实验。原39条已解决2条，剩37条/23来源；全量文献利用仍在继续，没有进行新模型拟合。</p>
   </Section>
   <Section id="rate18-title" title="第十八批 · 三来源倍率与证据更正" filters={<Filters {...rate18Scope.filterProps}/>}>
    <p>126捕获/114标称工况，8原始遮挡表达中2个可由自身重复图补回，6个工况仍空。普通点模式97含3旧作者值和94新图值；含天然硅稻壳碳另11条，不混入普通碳用途。连线仅辅助显示，不生成新数值。</p>
    <EvidenceChart id="rate18-chart" title="三来源原图倍率 · 遮挡保留断线" queryId="rate18_plot" rows={rate18Scope.componentProps('rate18_plot',[]).displayRows} sourceRows={rate18Scope.componentProps('rate18_plot',[]).sourceRows} variant="card" spec={{type:'line',x:'current',y:'value',series:'sample',xLabel:'标称电流（A/g）',yLabel:'原图电容（F/g）',colors:Object.fromEntries(['CS-700','NPC-700-3.5-1','NPC-700-3.5-2','NPC-700-3.5-3','NPC-700-1-2','NPC-700-2-2','NPC-700-4-2','NPC-600-2-2','NPC-800-2-2','NPC-900-2-2','RH-1000','RHPC-1000','ABC','ABPC-1','ABPC-2','ABPC-4'].map((s,i)=>[s,['#333333','#00a6ca','#ff7f00','#e7298a','#984ea3','#377eb8','#b15928','#66a61e','#a6761d','#666666','#8c510a','#01665e','#7570b3','#d95f02','#1b9e77','#e6ab02'][i]])),valueDecimals:2}} height={350}/>
    <EvidenceTable id="rate18-inputs-table" title="三模式与两用途 · 不相加" queryId="rate18_inputs" scope={rate18Scope} columns={[f('doi','DOI'),f('sample','样品'),f('current','A/g'),f('value','F/g'),f('lower','图下界'),f('upper','图上界'),f('kind','状态'),f('weight_label','本模式来源权重')]}/>
    <EvidenceTable id="bindings18-table" title="图像证据绑定更正 · 旧值保留" queryId="bindings18" columns={[f('table_key','转录单元'),f('old_image','原绑定图片'),f('new_image','更正后原图'),f('action','原因与处理')]}/>
    <EvidenceTable id="cycle-review18-table" title="ABPC4循环 · 角色与配置分开审查" queryId="cycle_review18" columns={[f('sample','样品'),f('retention','工作保持率'),f('CE','库仑效率'),f('configuration','配置'),f('window','窗口'),f('status','准入状态')]}/>
   </Section>
   <Section id="batch17-title" title="第十七批 · 五来源全样品与方法审查" filters={<Filters {...batch17Scope.filterProps}/>}>
    <p>新增64个分阶段登记、631材料数值，含10张主表与8张SI表。下表8条三电极、6条双电极两倍系数、1条有机四倍系数分别调用；8条三电极已包含在普通184条中。空值保留，没有插补或训练。</p>
    <EvidenceTable id="batch17-inputs-table" title="分用途输入 · 三个目标分别调用" queryId="batch17_inputs" scope={batch17Scope} columns={[f('doi','DOI'),f('sample','样品'),f('current','A/g'),f('capacitance','F/g'),f('BET','BET m²/g'),f('Raman_label','ID/IG'),f('bulk_N','体相N wt%'),f('XPS_N_at','XPS N at%'),f('XPS_N_wt','XPS N wt%'),f('window','电压与缺失状态'),f('weight_label','本用途来源权重')]}/>
    <EvidenceTable id="batch17-decisions-table" title="本批16项方法与争议处置" queryId="batch17_decisions" columns={[f('doi','DOI'),f('action','处理'),f('decision_id','证据记录')]}/>
   </Section>
   <Section id="rate16-title" title="第十六批 · 全样品倍率与显式读图用途" filters={<Filters {...rate16Scope.filterProps}/>}>
    <p>倍率图默认显示花椒皮五材料，可切换花椒籽或椰枣叶。图中均为原图主表达，完整上下界保存在数据中；作者报告值与读图混合表另列，三种模式不可相加。连线不生成新训练点，没有模型拟合。</p>
    <EvidenceChart id="rate16-chart" title="原图倍率 · 按面板切换" queryId="rate16_plot" rows={rate16Scope.componentProps('rate16_plot',[]).displayRows} sourceRows={rate16Scope.componentProps('rate16_plot',[]).sourceRows} variant="card" spec={{type:'line',x:'current',y:'value',series:'sample',stackable:false,xLabel:'作者报告电流（A/g）',yLabel:'原图电容（F/g）',colors:{'PAC-600':'#333333','PAC-700':'#d73027','PAC-800':'#377eb8','PAC-900':'#e7298a','PAC-1000':'#1b9e77','SAC-600':'#984ea3','SAC-700':'#ff7f00','SAC-800':'#00a6ca','SAC-900':'#b15928','SAC-1000':'#999999','NaOH-activated':'#f781bf'},valueDecimals:2}} height={330}/>
    <EvidenceTable id="rate16-inputs-table" title="作者值／混合／仅图 · 各模式分开调用" queryId="rate16_inputs" scope={rate16Scope} columns={[f('doi','DOI'),f('sample','样品'),f('current','A/g'),f('value','F/g'),f('lower','下界'),f('upper','上界'),f('kind','标签来源'),f('weight_label','本模式来源权重'),f('evidence','原文位置')]}/>
    <EvidenceTable id="expanded16-inputs-table" title={`显式含读图3E输入 · ${h.expanded_3e_with_graph_rows}行／${h.expanded_3e_with_graph_DOI_groups}DOI`} queryId="expanded16_inputs" columns={[f('doi','DOI'),f('sample','样品'),f('current','A/g'),f('value','F/g'),f('kind','用途类型'),f('lower','图下界'),f('upper','图上界'),f('weight_label','全用途来源权重')]}/>
    <EvidenceTable id="rate16-decisions-table" title="倍率标记的四项处理" queryId="rate16_decisions" columns={[f('decision_id','记录'),f('action','处理')]}/>
   </Section>
   <Section id="batch15-title" title="第十五批 · 花椒皮籽与椰枣叶" filters={<Filters {...batch15Scope.filterProps}/>}>
    <p>两来源新增20个自身三电极工况，SI复述和循环后电容另存。下面32行是XPS拟合分量表达，全表at%和C1s内%Area分别列示。两个器件循环缺物理电压，PAC700还与旧端点重复，不作新增准入。</p>
    <EvidenceTable id="batch15-inputs-table" title="两来源 · 20条自身GCD输入" queryId="batch15_inputs" scope={batch15Scope} columns={[f('doi','DOI'),f('sample','样品'),f('current','作者A/g'),f('capacitance','电容F/g'),f('BET','BET m²/g'),f('XPS_N','XPS N at%'),f('XPS_O','XPS O at%'),f('Raman','Raman积分比'),f('window','测试窗口'),f('reference','工作参比'),f('weight_label','本批来源权重'),f('evidence','原文位置')]}/>
    <EvidenceTable id="batch15-components-table" title="XPS组分 · 两种尺度分开" queryId="batch15_components" scope={batch15Scope} columns={[f('doi','DOI'),f('sample','样品'),f('component','组分'),f('energy','结合能eV'),f('absolute_at_pct','全表at%'),f('relative_area_pct','C1s内%Area'),f('basis','尺度'),f('status','核查状态')]}/>
    <EvidenceTable id="batch15-decisions-table" title="十二项方法与冲突处置" queryId="batch15_decisions" scope={batch15Scope} columns={[f('doi','DOI'),f('decision_id','记录'),f('action','处置')]}/>
    <EvidenceTable id="batch15-links-table" title="历史循环身份关联 · 避免重复端点" queryId="batch15_identity_links" columns={[f('candidate_id','本批候选'),f('existing_endpoint','旧端点'),f('relation','关系'),f('status','状态')]}/>
   </Section>
   <Section id="furfural14-title" title="第十四批 · 倍率曲线与点/区间标签" filters={<Filters {...furfural14Scope.filterProps}/>}>
   <EvidenceChart id="furfural14-rate-chart" title="糠醛渣8材料倍率图 · 遮挡点保留缺口" queryId="furfural14_curve" rows={reviewedRows('furfural14_curve')} sourceRows={reviewedRows('furfural14_curve')} variant="card" spec={{type:'line',x:'x_value',y:'graph_capacitance_F_g',series:'sample_name',stackable:false,colors:{'PC700-1':'#d73027','PC800-1':'#00a6ca','PC900-1':'#1b9e77','PC950-1':'#984ea3','FR900':'#f28e2b','PC900-0':'#333333','PC900-0.1':'#cc79a7','PC900-0.5':'#377eb8'},xLabel:'作者报告电流（A/g）',yLabel:'原图读数（F/g）',valueDecimals:2}} height={370}>
    <p className="scope-note">原图近似读数，常规标记4px读取界限；两个遮挡点不画中点、不跨空值连线。不是模型预测或实验误差条，完整上下界见下表与来源。</p>
   </EvidenceChart>
   <EvidenceTable id="furfural14-inputs-table" title="三个显式模式 · 同48工况不能相加" queryId="furfural14_inputs" scope={furfural14Scope} columns={[f('sample_name','样品'),f('mode_label','目标模式'),f('current_A_g','作者 A/g'),f('target_value','点目标 F/g'),f('lower','标签下界 F/g'),f('upper','标签上界 F/g'),f('quality','数值类型与界限'),f('physical_test_group','标称测试组')]}/>
   <EvidenceTable id="furfural14-ratio-table" title="倍率注记核查 · 原值与未决分别保留" queryId="furfural14_ratio_audits" columns={[f('sample_name','材料'),f('author_rate_retention_pct','作者倍率 %'),f('derived_from_figure_pct','图点比 %'),f('interval_lower','图比下界 %'),f('interval_upper','图比上界 %'),f('derived_from_reported_exact_capacitances_pct','正文点值算术 %'),f('canonical_display','标准倍率'),f('status_label','核查状态')]}/>
   <EvidenceTable id="furfural14-contribution-table" title="CV贡献率 · 印刷和101不归一化" queryId="furfural14_contributions" columns={[f('scan_rate_mV_s','扫描 mV/s'),f('capacitive_pct','电容贡献 %'),f('diffusion_pct','扩散贡献 %'),f('printed_sum_pct','印刷合计 %'),f('status','处置')]}/>
   <EvidenceTable id="furfural14-annotations-table" title="18个集体/阶段注记 · 非逐样重复测量" queryId="furfural14_annotations" columns={[f('category','类别'),f('annotation_id','注记'),f('value_display','作者数值/范围'),f('unit','单位'),f('assignment','作者归属'),f('scope_label','适用边界'),f('evidence','原文位置')]}/>
   <EvidenceTable id="furfural14-figures-table" title="12原图范围台账 · 剩余波形继续" queryId="furfural14_figures" columns={[f('figure','图'),f('review','已核/剩余范围'),f('completion','完成边界'),f('source_path','原图文件')]}/>
   <EvidenceTable id="furfural14-decisions-table" title="8项处置 · 提取、冻结和阶段分开" queryId="furfural14_decisions" columns={[f('decision_id','核验项'),f('action','依据与处理')]}/>
  </Section>
  <Section id="batch13-review-title" title="第十三批 · 多样品提取与图文冲突">
   <EvidenceTable id="cycle25-admissions-table" title="v0.25正式循环 · 芒果核2E与皮革3E" queryId="cycle25_admissions" columns={[f('sample_name','样品'),f('source_year_display','年份'),f('electrolyte_label','电解液'),f('retention_pct','保持率 %'),f('cycle_count','圈数'),f('reported_current_A_g','作者 A/g'),f('cycle_voltage_lower_V','下限 V'),f('cycle_voltage_upper_V','上限 V'),f('profile_label','用途'),f('review_note','原值与裁决'),f('feature_note','特征限定')]}/>
   <EvidenceTable id="batch13-sources-table" title="四个来源范围 · 商业参考另列" queryId="batch13_sources" columns={[f('doi','DOI'),f('classification','身份与用途'),f('scope','已核范围'),f('remaining','剩余工作')]}/>
   <EvidenceTable id="batch13-decisions-table" title="18项证据处置 · 工作值与未决冻结" queryId="batch13_decisions" columns={[f('doi','DOI'),f('decision_id','核验项'),f('decision','原值、依据与处理')]}/>
   <EvidenceTable id="residue13-inputs-table" title="糠醛渣GCD · ZnS残留独立用途" queryId="residue13_inputs" columns={[f('sample_name','样品'),f('value','F/g'),f('current_A_g','A/g'),f('electrolyte','电解液'),f('window','测试窗口'),f('BET','BET m²/g'),f('Zn','ICP-OES Zn wt%'),f('purpose','用途边界'),f('evidence','原文位置')]}/>
   <EvidenceTable id="interface13-reference-table" title="商业界面参考 · 24报告非训练输入" queryId="interface13_reference" columns={[f('sample_name','配方'),f('value','F/g'),f('current_A_g','A/g'),f('reported_plusminus','作者±量'),f('statistic','统计限定'),f('status','准入边界'),f('evidence','原文位置')]}/>
   <EvidenceTable id="wetting13-table" title="接触角随时间 · 0/3/6秒分别保存" queryId="wetting13" columns={[f('sample','配方'),f('time_s','时间 s'),f('contact_angle_deg','接触角 °'),f('status','限定'),f('table_key','原表')]}/>
  </Section>
  <Section id="batch12-review-title" title="第十二批 · 体积电容与椰壳补充表" filters={<Filters {...batch12Scope.filterProps}/>}>
   <EvidenceTable id="cycle24-admissions-table" title="v0.24苏铁绒循环 · 两盐同一来源" queryId="cycle24_admissions" columns={[f('sample_name','样品'),f('source_year_display','年份'),f('electrolyte_label','电解液'),f('retention_pct','保持率 %'),f('cycle_count','圈数'),f('reported_current_A_g','作者 A/g'),f('cycle_voltage_lower_V','下限 V'),f('cycle_voltage_upper_V','上限 V'),f('profile_label','准入范围'),f('source_weight_label','来源权重'),f('feature_note','材料特征')]}/>
   <EvidenceTable id="cycle24-feature-masks-table" title="同材料N/O竞争 · 原值保留与空值通道" queryId="cycle24_feature_masks" columns={[f('material','材料'),f('field_name','通道'),f('raw_values','竞争原值 at%'),f('canonical','当前输入'),f('status','处置')]}/>
   <EvidenceTable id="batch12-inputs-table" title="分目标输入 · 同测试表达不能重复计数" queryId="batch12_inputs" scope={batch12Scope} columns={[f('sample_name','样品'),f('task','目标'),f('quantity','作者数值'),f('unit','单位'),f('current_A_g','A/g'),f('electrolyte','电解液'),f('collector','集流体'),f('separator','隔膜'),f('voltage_lower_V','下限 V'),f('voltage_upper_V','上限 V'),f('evidence','原文位置')]}/>
   <EvidenceTable id="batch12-sources-table" title="两篇指定范围 · 剩余波形继续" queryId="batch12_sources" columns={[f('doi','DOI'),f('scope','已核范围'),f('remaining','剩余工作')]}/>
   <EvidenceTable id="batch12-decisions-table" title="13项处置 · 方法、身份与竞争原值" queryId="batch12_decisions" columns={[f('doi','DOI'),f('decision_id','核验项'),f('decision','证据与处理')]}/>
  </Section>
  <Section id="batch11-review-title" title="第十一批 · 多样品、原图裁决与前作复用">
   <EvidenceTable id="cycle23-admissions-table" title="v0.23新准入 · 两项用途与来源隔离" queryId="cycle23_admissions" columns={[f('sample_name','样品'),f('source_year_display','年份'),f('electrolyte_label','电解液'),f('retention_pct','保持率 %'),f('cycle_count','圈数'),f('reported_current_A_g','作者 A/g'),f('cycle_voltage_lower_V','下限 V'),f('cycle_voltage_upper_V','上限 V'),f('BET_m2_g','自身BET m²/g'),f('profile_label','准入视图'),f('family_label','隔离范围')]}/>
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
   <EvidenceTable id="bounded-curve-table" title="182条图捕获 · 180数值与2仅区间" queryId="bounded_curve_samples" scope={curveScope} columns={[f('sample_name','样品'),f('x_kind','横轴含义'),f('x_value','横轴值'),f('y_value','电容 F/g'),f('y_uncertainty','读图界限 ±F/g'),f('y_lower_bound','区间下界 F/g'),f('y_upper_bound','区间上界 F/g'),f('error_kind','界限定义'),f('curve_group','曲线组')]}/>
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
