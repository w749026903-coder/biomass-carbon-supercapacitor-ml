import React, {useEffect, useState} from 'react';
import {DataComponent, EvidenceChart, Section, useDataApp} from '../../data-app-public.jsx';
import './model-v1.css';

const labels={selected:'v1.0选定模型',source_mean:'来源等权均值',legacy_mlp_noI:'原去电流MLP',
  ridge_core_noI_100:'Ridge100·核心参数',ridge_material_noI_100:'Ridge100·加入材料制备'};
const f=(value, digits=2)=>Number.isFinite(value)?value.toFixed(digits):'—';

export function DashboardContent(){
 const {queries}=useDataApp();
 const [run,setRun]=useState({...queries.status?.rows?.[0],events:queries.progress?.rows||[],
   metrics:queries.metrics?.rows||[],predictions:queries.predictions?.rows||[],candidates:queries.candidates?.rows||[]});
 const [variant,setVariant]=useState('selected');
 const [connection,setConnection]=useState(location.protocol==='file:'?'离线结果快照':'连接本机实际日志');
 useEffect(()=>{
  if(location.protocol==='file:')return;
  let active=true;
  const load=async()=>{try{const response=await fetch('/progress.json',{cache:'no-store'});if(!response.ok)throw Error('unavailable');
    const value=await response.json();if(active){setRun(value);setConnection(value.status==='complete'?'实际执行日志 · 已完成':'实际执行日志 · 每秒刷新');}}
    catch(e){if(active)setConnection('本机日志不可达，显示保存快照');}};
  load();const timer=setInterval(load,1000);return()=>{active=false;clearInterval(timer);};
 },[]);
 const scores=(run.metrics||[]).map(row=>({...row,label:labels[row.variant]}));
 const points=(run.predictions||[]).filter(row=>row.variant===variant).map(row=>({...row,absolute_error:Math.abs(row.predicted-row.observed)}));
 const status=[{status:run.status,completed:run.completed,total:run.total,actual_estimator_fits:run.actual_estimator_fits,
    elapsed_seconds:run.elapsed_seconds,selected_id:run.selected_id}];
 const candidates=[...(run.candidates||[])].sort((a,b)=>a.mae-b.mae);
 const diagnose=queries.diagnosis?.rows?.[0];
 return <article className="model-v1">
  <DataComponent id="v1-status" queryId="status" title="训练与模型文件" kind="custom" variant="card" displayRows={status} sourceRows={status}>
   <div data-reviewed-rows className="v1-status-line"><strong>{run.status==='complete'?'v1.0训练完成 · 性能验收未通过':run.status==='failed'?'执行失败 · 已保留断点':'v1.0训练执行中'}</strong><span>{connection}</span></div>
   <div className="v1-progress-title" data-reviewed-rows><b>{f(run.percent||0,1)}%</b><span>{run.completed||0} / {run.total||581} 个已完成任务</span></div>
   <progress aria-label="实际任务进度" value={run.completed||0} max={run.total||581}/>
   <div className="v1-stats" data-reviewed-rows><div><span>主集规模</span><b>42条 / 30来源</b></div><div><span>开发 / 留出来源</span><b>23 / 7</b></div><div><span>实际模型拟合</span><b>{run.actual_estimator_fits||0}次</b></div><div><span>拟合与评分用时</span><b>{f(run.elapsed_seconds||0,1)}秒</b></div></div>
   <p className="v1-note">开发集35条，用整来源留一法比较25个候选与参照。新增7来源在选型之后检验；原文审查已接触其标签，并非前瞻盲测。全42条重训模型另存，以下留出分数属于35条训练模型。</p>
   <p className="v1-alert">选定模型留出MAE 6.88个百分点，高于均值参照5.93；相对原MLP的差异区间跨0。研究模型已经保存，尚不支持可靠的新材料性能承诺。</p>
  </DataComponent>
  <Section id="v1-reserved-section" title="7个新增来源的固定检验" columns={1}>
   <EvidenceChart id="v1-reserved-mae" queryId="metrics" title="来源等权平均绝对误差" variant="card"
    spec={{type:'horizontalBar',x:'label',y:'mae',yLabel:'MAE（百分点，越低越好）',valueDecimals:2,stackable:false,colors:{mae:'var(--chart-1)'}}}
    rows={scores} sourceRows={scores} height={300}/>
   <DataComponent id="v1-reserved-table" queryId="metrics" title="检验指标与不确定性" kind="table" variant="card" displayRows={scores} sourceRows={scores}>
    <div className="v1-table" data-reviewed-rows><table><thead><tr><th>方案</th><th>MAE [95%描述区间]</th><th>RMSE</th><th>R²</th><th>相对均值 ΔMAE [95%区间]</th></tr></thead>
     <tbody>{scores.map(row=><tr key={row.variant}><td>{row.label}</td><td>{f(row.mae)} [{f(row.vs_mean?.mae_ci_low)}, {f(row.vs_mean?.mae_ci_high)}]</td><td>{f(row.rmse)}</td><td>{f(row.r2,3)}</td><td>{f(row.vs_mean?.delta_mae)} [{f(row.vs_mean?.delta_ci_low)}, {f(row.vs_mean?.delta_ci_high)}]</td></tr>)}</tbody></table></div>
    <p className="v1-note">来源5000次重采样的条件性描述区间，仅7篇，未计重新拟合不确定性。负Δ表示误差更低。这些区间不是单样品预测区间；没有依据留出成绩重新选择模型。</p>
   </DataComponent>
  </Section>
  <Section id="v1-predictions-section" title="逐材料检验记录" columns={1}>
   <div className="v1-filter"><label>查看方案 <select value={variant} onChange={event=>setVariant(event.target.value)}>{Object.entries(labels).map(([id,label])=><option value={id} key={id}>{label}</option>)}</select></label><span>{points.length}条 / 7来源</span></div>
   <EvidenceChart id="v1-parity" queryId="predictions" title="报告值与留出预测值" variant="card"
     spec={{type:'scatter',x:'observed',y:'predicted',xLabel:'作者报告保持率（%）',yLabel:'模型预测保持率（%）',valueDecimals:2,stackable:false,colors:{predicted:'var(--chart-1)'}}}
     rows={points} sourceRows={points} height={320}/>
   <DataComponent id="v1-records" queryId="predictions" title="来源、误差与适用范围提示" kind="table" variant="card" displayRows={points} sourceRows={points}>
    <div className="v1-table v1-records" data-reviewed-rows><table><thead><tr><th>材料 / DOI</th><th>报告保持率（%）</th><th>预测（%）</th><th>绝对误差（百分点）</th><th>训练支持提示</th></tr></thead><tbody>{points.map(row=><tr key={row.endpoint_id}><td><b>{row.sample_name}</b><small>{row.source_group}</small></td><td>{f(row.observed)}</td><td>{f(row.predicted)}</td><td>{f(row.absolute_error)}</td><td>{(row.warnings||[]).join('; ')||'核心字段未超出训练范围；不代表预测可靠'}</td></tr>)}</tbody></table></div>
   </DataComponent>
  </Section>
  {diagnose&&<DataComponent id="v1-distribution" queryId="diagnosis" title="来源分布与误差集中" kind="custom" variant="card" displayRows={[diagnose]} sourceRows={[diagnose]}>
   <div data-reviewed-rows className="v1-stats"><div><span>开发来源平均保持率</span><b>{f(diagnose.development.source_equal_target_mean)}%</b></div><div><span>留出来源平均保持率</span><b>{f(diagnose.reserved.source_equal_target_mean)}%</b></div><div><span>低于91%的来源</span><b>开发2/23 · 留出4/7</b></div><div><span>最大2项平方误差占比</span><b>{f(100*diagnose.top2_squared_error_share,1)}%</b></div></div>
   <p className="v1-note">OAC623与稻草AC是最大误差来源；NaOH在开发集中没有出现。材料制备参数已进入候选比较，但不足以稳定区分这些新来源。上述分布差异是观察结果，尚不能证明唯一的因果机制。</p>
  </DataComponent>}
  <Section id="v1-development-section" title="开发集选型与真实运行记录" columns={1}>
   <EvidenceChart id="v1-progress-history" queryId="progress" title="累计完成任务随实际耗时变化" variant="card"
    spec={{type:'line',x:'seconds',y:'completed',xLabel:'实际运行秒数',yLabel:'累计任务数',valueDecimals:0,stackable:false,colors:{completed:'var(--chart-1)'}}}
    rows={run.events||[]} sourceRows={run.events||[]} height={240}/>
   <DataComponent id="v1-development-table" queryId="candidates" title="25个候选与参照的开发集结果" kind="table" variant="card" displayRows={candidates} sourceRows={candidates}>
    <p className="v1-note">这些分数用于选型，不能作为独立检验精度。新材料与制备参数每个字段至少获5个训练来源支持才启用。选定：{run.selected_id||'尚未完成'}。</p>
    <div className="v1-table v1-candidates" data-reviewed-rows><table><thead><tr><th>候选</th><th>特征范围</th><th>报告电流</th><th>MAE（百分点）</th><th>R²</th></tr></thead><tbody>{candidates.map(row=><tr key={row.candidate}><td>{row.candidate}</td><td>{row.block==='material'?'核心 + 材料制备':'核心'}</td><td>{row.current?'使用':'去电流'}</td><td>{f(row.mae)}</td><td>{f(row.r2,3)}</td></tr>)}</tbody></table></div>
   </DataComponent>
  </Section>
 </article>;
}
