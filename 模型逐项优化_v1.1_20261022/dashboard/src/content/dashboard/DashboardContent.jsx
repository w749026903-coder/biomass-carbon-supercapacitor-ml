import React,{useState} from 'react';
import {DataComponent,EvidenceChart,Section,useDataApp} from '../../data-app-public.jsx';
import './optimization.css';

const names={v1_1_nested:'v1.1正值目标与内层选型',v1_recipe_same_cohort:'v1.0配方·同批来源重评',source_mean:'来源等权均值参照'};
const statusNames={complete:'已完成',implemented:'已实现',requires_further_source_review:'仍需逐来源处理'};
const number=(n,d=2)=>Number.isFinite(n)?n.toFixed(d):'—';
function Retention({pct}){return <span className="retention-unit"><b className="pct">{number(pct)}%</b><small className="ratio">比例{number(pct/100,4)}</small></span>;}

export function DashboardContent(){
 const {queries}=useDataApp();const [variant,setVariant]=useState('v1_1_nested');
 const state=queries.status?.rows?.[0]||{};const metrics=queries.metrics?.rows||[];
 const points=(queries.predictions?.rows||[]).filter(row=>row.variant===variant);
 const topErrors=[...points].sort((a,b)=>b.absolute_error_pp-a.absolute_error_pp).slice(0,10);
 const steps=queries.checklist?.rows||[];const examples=queries.units?.rows||[];
 return <article className="optimization-v11">
  <DataComponent id="unit-definition" queryId="units" title="保持率单位与超过100%的解释" variant="card" kind="custom" displayRows={examples} sourceRows={examples}>
   <p className="unit-formula">保持率比例 R = 给定循环点电容 / 作者初始参照电容；保持率百分数 = 100 × R。</p>
   <p className="unit-key">101.24% = 比例1.0124。保持率不是概率；高于初始参照时可以超过100%。</p>
   <p className="optimization-note">原文报告的增长与模型预测的增长分别处理。截图中稻草AC的旧预测101.24%，实际为83.54%，高估17.70个百分点；不能据此声称发生了活化。</p>
   <div className="table-scroll unit-examples" data-reviewed-rows><table><thead><tr><th>样品 / 类型</th><th>百分数与比例</th><th>证据解释</th></tr></thead><tbody>{examples.map(row=><tr key={row.sample_name}><td>{row.sample_name}<small>{row.type==='author_reported_3e'?'作者报告的3E观测':'旧模型留出预测'}</small></td><td><Retention pct={row.retention_pct}/></td><td>{row.meaning}</td></tr>)}</tbody></table></div>
  </DataComponent>
  <DataComponent id="optimization-checklist" queryId="checklist" title="逐项优化清单" variant="card" kind="table" displayRows={steps} sourceRows={steps}>
   <div className="table-scroll" data-reviewed-rows><table><thead><tr><th>顺序</th><th>改进项</th><th>当前状态</th></tr></thead><tbody>{steps.map(row=><tr key={row.id}><td>{row.id}</td><td>{row.task}</td><td>{statusNames[row.status]||row.status}</td></tr>)}</tbody></table></div>
   <p className="optimization-note">前5项属于已实施的本轮优化。独立困难来源仍不足；另定位到CA-TB、CA-W、CA-C三个同论文样品，仍须逐测试审查后入库，不能算3个新来源。</p>
  </DataComponent>
  <DataComponent id="experiment-status" queryId="status" title="v1.1实验与可靠性状态" variant="card" kind="custom" displayRows={[state]} sourceRows={[state]}>
   <div className="status-line" data-reviewed-rows><strong>本轮优化实验完成 · 精度尚未达标</strong><span>{state.completed} / {state.total}个任务</span></div>
   <progress value={state.completed||0} max={state.total||1332} aria-label="实际优化任务进度"/>
   <div className="summary-grid" data-reviewed-rows><div><span>同批评估数据</span><b>42条 / 30来源</b></div><div><span>实际拟合</span><b>{state.actual_estimator_fits}次</b></div><div><span>耗时</span><b>{number(state.elapsed_seconds,1)}秒</b></div><div><span>全量选定配方</span><b>{state.selected_id}</b></div></div>
   <p className="optimization-alert">正值输出、单位清楚和核验通过，都不表示预测准确。当前仅提供研究数值；没有独立验证的材料设计推荐值，也没有校准的单样品预测区间。</p>
   <p className="optimization-note">本轮对已经使用过的42条数据进行30折外层来源留一、每折5折内层选型。不是新的独立检验；不能把这里4.75与旧7来源检验的6.88直接比较。对数目标保证预测为正，保留超过100%的可能，不做上限截断。</p>
  </DataComponent>
  <Section id="same-cohort-comparison" title="同一批来源上的比较" columns={1}>
   <EvidenceChart id="v11-mae" queryId="metrics" title="来源等权平均绝对误差" variant="card" spec={{type:'horizontalBar',x:'label',y:'mae',yLabel:'MAE（百分点）',stackable:false,valueDecimals:3,colors:{mae:'var(--chart-1)'}}} rows={metrics} sourceRows={metrics} height={230}/>
   <DataComponent id="v11-metrics" queryId="metrics" title="误差、参照与描述性区间" variant="card" kind="table" displayRows={metrics} sourceRows={metrics}>
    <div className="table-scroll" data-reviewed-rows><table><thead><tr><th>方案</th><th>MAE（百分点）</th><th>RMSE</th><th>R²</th><th>相对旧配方 ΔMAE [95%区间]</th></tr></thead><tbody>{metrics.map(row=><tr key={row.variant}><td>{row.label}</td><td>{number(row.mae,3)}</td><td>{number(row.rmse,3)}</td><td>{number(row.r2,3)}</td><td>{number(row.vs_reference.delta_mae,3)} [{number(row.vs_reference.delta_low,3)}, {number(row.vs_reference.delta_high,3)}]</td></tr>)}</tbody></table></div>
    <p className="optimization-note">v1.1比旧配方平均少0.024个百分点误差，差异区间跨0；均值参照反而更低。未证明精度改进成立。区间是30来源5000次配对重采样的条件性描述结果。</p>
   </DataComponent>
  </Section>
  <Section id="predictions-section" title="带双单位与风险状态的逐条结果" columns={1}>
   <div className="prediction-filter"><label>方案 <select value={variant} onChange={e=>setVariant(e.target.value)}>{Object.entries(names).map(([key,value])=><option key={key} value={key}>{value}</option>)}</select></label><span>{points.length}条 / 30来源</span></div>
   <DataComponent id="v11-predictions" queryId="predictions" title="原文观测与来源留出预测" kind="table" variant="card" displayRows={points} sourceRows={points}>
    <div className="table-scroll prediction-records" data-reviewed-rows><table><thead><tr><th>样品 / DOI</th><th>报告保持率</th><th>预测保持率</th><th>误差（百分点）</th><th>可靠性与输入支持</th></tr></thead><tbody>{points.map(row=><tr key={row.endpoint_id}><td><b>{row.sample_name}</b><small>{row.source_group}</small></td><td><Retention pct={row.observed_pct}/>{row.observed_pct>100&&<small>原文报告高于初始参照</small>}</td><td><Retention pct={row.predicted_pct}/>{row.predicted_pct>100&&<small>预测高于初始值；非活化证据</small>}</td><td>{number(row.error_pp)}</td><td><b className="reliability">研究用 · 未独立验证</b><small>{row.input_warnings?.length?row.input_warnings.join('; '):'字段范围内仍可能严重失准'}</small></td></tr>)}</tbody></table></div>
   </DataComponent>
   <EvidenceChart id="v11-largest-errors" queryId="predictions" title="绝对误差最大的10条记录：带方向误差" variant="card" spec={{type:'horizontalBar',x:'sample_name',y:'error_pp',yLabel:'预测−报告值（百分点）',stackable:false,valueDecimals:2,colors:{error_pp:'var(--chart-1)'}}} rows={topErrors} sourceRows={topErrors} height={390}/>
  </Section>
  <Section id="feature-support-section" title="语义特征与来源支持" columns={1}>
   <DataComponent id="v11-semantic-support" queryId="semantic_support" title="已整理的三类语义参数" kind="table" variant="card" displayRows={queries.semantic_support?.rows||[]} sourceRows={queries.semantic_support?.rows||[]}>
    <p className="optimization-note">使用已有方法证据形成活化剂类别、工艺状态和原料来源类别。未知值与明确未活化分开；类别须有至少3个训练来源才单独编码，否则归入稀有/未知桶。数值材料字段仍要求至少5个训练来源。</p>
    <div className="table-scroll semantic-records" data-reviewed-rows><table><thead><tr><th>字段</th><th>类别</th><th>支持来源数</th></tr></thead><tbody>{(queries.semantic_support?.rows||[]).map(row=><tr key={row.field+row.category}><td>{row.field}</td><td>{row.category}</td><td>{row.sources}</td></tr>)}</tbody></table></div>
    <p className="optimization-note">材料及语义候选在17/30个外层训练选择中被采用；最终全量配方仍选核心参数。不能把参与训练等同于已证明有效，也没有隔离证明某个新语义字段的独立收益。</p>
   </DataComponent>
   <EvidenceChart id="v11-progress" queryId="progress" title="实际优化任务进度记录" variant="card" spec={{type:'line',x:'seconds',y:'completed',xLabel:'实际秒数',yLabel:'累计完成任务',stackable:false,valueDecimals:0,colors:{completed:'var(--chart-1)'}}} rows={queries.progress?.rows||[]} sourceRows={queries.progress?.rows||[]} height={240}/>
  </Section>
 </article>;
}
