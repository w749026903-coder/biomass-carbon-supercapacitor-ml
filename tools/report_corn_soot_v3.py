"""Standalone progress/evidence report for the first active-goal milestone."""
from pathlib import Path
import collections,csv,html,io,json,sqlite3,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.extract_corn_soot_v3 import OUT,DB,read,write

def report():
    assert not(OUT/'merge_manifest.json').exists()
    s=read(OUT/'summary.json');c=sqlite3.connect(DB.as_uri()+'?mode=ro',uri=True);by=collections.defaultdict(lambda:collections.Counter())
    for rr,uu in c.execute('select f.record_json,u.record_json from facts f join usage_ledger u using(fact_id)'):
        f=json.loads(rr);u=json.loads(uu);a=by[f['doi']];a['facts']+=1;a['numeric']+=f['value']is not None;a['connected']+=bool(u['uses'])
    stream=io.StringIO(newline='');w=csv.DictWriter(stream,fieldnames=['doi','facts','numeric','connected','connection_rate','whole_paper_complete'],lineterminator='\n');w.writeheader()
    for doi,a in sorted(by.items()):w.writerow(dict(doi=doi,**a,connection_rate=a['connected']/a['numeric']if a['numeric']else None,whole_paper_complete=False))
    (OUT/'source_fact_utilization.csv').write_text(stream.getvalue(),encoding='utf-8-sig')
    summary=dict(numeric_unconnected=s['remaining_unconnected_numeric_facts'],nonpoint=s['nonpoint_facts'],measurement_metadata=s['measurement_metadata_facts'],
      remaining_work=['Continue local lignin/commercial-CF full body and SI; 99% unbending recovery is not cycle retention.',
       'Corn: remaining native rate bars, PSD/GCD/CV/charge-storage contributions and ambiguous device cycling traces; keep the CS1000 BET and device formula disputes.',
       'Soot: unresolved EDS-N/table discrepancies, incomplete mass sums and particle-size measurement basis; adsorption/sensor responses remain outside cycling targets.',
       'Continue existing unconnected contracts/units/stages and 37 fixed cycling pending records, then untouched original table/figure/SI units.'],
      all_literature_extracted=False,goal_status='active',new_model_fits=0,new_cycling_admissions=0)
    write(OUT/'next_actions.json',summary)
    caps=read(OUT/'new_capacity_reports.json');esc=html.escape
    rows=''.join('<tr><td>'+esc(r['sample_name'])+'</td><td>'+('含天然残留的三电极'if r['configuration']=='3e_native_corn'else'器件作者公式用途')+'</td><td>'+str(r['conditions']['reported_current_A_g'])+'</td><td>'+str(r['value'])+'</td></tr>'for r in caps)
    labels={
      'corn_residual_silica':'玉米酸洗后仍有石英残留，按天然残留材料分用途，不能假定已成为无灰纯碳。',
      'corn_BET_prose_precision':'CS-1000的BET：表格6.6534、正文6.70；两值保留，该字段冻结，不按数值高低选择。',
      'soot_EDS_sum_AP_PS':'AP+PS烟炱已列EDS元素合计91.74%，空白仍未知，不补零、不重新归一化。',
      'soot_EDS_N_table_figure':'AP/PS烟炱的N表项与谱图/正文不一致，该字段冻结；谱图未显峰不能直接视作0。',
      'corn_2e_basis_label_formula':'玉米器件“单电极”文字与总质量公式不一致，保留独立作者公式用途，不擅自乘2或4。',
      'corn_cycle_old_identity':'旧玉米器件候选已有自身材料证据，但循环图线/归一化仍有疑点；本批不新增循环标签或准入。'}
    issues=''.join('<li>'+esc(labels.get(r['issue_id'],r.get('reason','保留原值和具体出处，继续核查')) )+'</li>'for r in read(OUT/'scientific_issues.json'))
    page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>数据库质量目标 · 首批文献接续</title><style>body{font:16px/1.7 system-ui,"Microsoft YaHei",sans-serif;background:#f2f5f2;color:#203a32;margin:0}main{max-width:1080px;margin:auto;padding:24px}h1{line-height:1.3}.cards{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}.card,section{background:white;border:1px solid #dce6df;border-radius:12px;padding:20px;margin:18px 0}.card{margin:0}.card strong{display:block;font-size:28px;color:#20725b}a{color:#1c745a}code{overflow-wrap:anywhere}.table{overflow:auto}table{width:100%;border-collapse:collapse}th,td{padding:9px;text-align:left;border-bottom:1px solid #e0e8e3}td{white-space:nowrap}li{margin:10px 0;overflow-wrap:anywhere}.muted{color:#61756b}@media(max-width:650px){main{padding:14px}.cards{grid-template-columns:1fr 1fr}.card{padding:12px}h1{font-size:26px}}</style><main>
<p class="muted">2026-10-28 · 总体目标 active · 新增拟合 0</p><h1>继续提升质量与文献利用率：首批接续结果</h1><div class="cards"><div class="card"><strong>+160</strong>材料事实（145数值）</div><div class="card"><strong>+120</strong>数值接入实际输入</div><div class="card"><strong>+11</strong>有明确工况的比电容报告</div><div class="card"><strong>68.88%</strong>3,178 / 4,614数值接入</div></div>
<section><h2>从已读论文走到可调用输入</h2><p>本批结构化玉米秸秆与坚果壳烟炱两篇现有论文，登记8个最终样品和3个未酸洗阶段，补入主表、SI表、原图印字，以及15个带±0.25°读图容差的水接触角标记点。时间点分别保存，没有把水湿润性当实际电解液湿润性。</p><p>已提取材料事实目前覆盖63个有事实来源；复核登记67来源，均未声称整篇完成。68.88%只计唯一数值事实进入准备输入/辅助目标的回执，不能当全部文献利用率、独立实验数或实际拟合使用率。新增数值包括同一测量在主图与SI重复报告的独立证据记录，不增独立实验。</p></section>
<section><h2>循环保持率模型仍有哪些限制</h2><p>三电极主集仍为47条/34来源，双电极31条/25来源。本批没有新增循环准入，也没有新训练。玉米材料有明确残留SiO₂，烟炱含原生无机组分，按独立用途保存；没有混入普通生物质碳主集。旧玉米器件候选已关联自身材料，但图线/归一化疑点保留；不属于原固定37条审查，不能拿它抵扣37条待证。</p><p>新比电容用途各只有一个来源，不能独立验证跨来源预测能力。旧数据的来源分组、训练折内覆盖选列及辅助任务同源隔离继续适用。</p></section>
<section><h2>新增比电容报告</h2><div class="table"><table><thead><tr><th>样品</th><th>独立用途</th><th>电流 A/g</th><th>比电容 F/g</th></tr></thead><tbody>CAPS</tbody></table></div><p>器件作者称“单电极”，公式却使用两电极总质量；该表达冲突保留在独立作者公式用途，不擅自乘2或4。</p></section>
<section><h2>明确冻结与继续处理的内容</h2><ul>ISSUES</ul><p>累计未进入预测输入/目标的数值1,436项，其中326项在谱峰/误差元数据索引，另6项是原有EDX/DFT误差分类；其余也有重复报告、阶段或用途限制，不能一律强行准入。216项非点/空值保留。原37条循环待证与旧冻结不动。</p></section>
<section><h2>证据与调用</h2><p><a href="README.md">调用说明</a> · <a href="new_facts.json">新增事实与原值</a> · <a href="source_fact_utilization.csv">逐来源材料事实接入</a> · <a href="extraction_coverage.json">本批表图/SI覆盖</a> · <a href="unconnected_numeric_queue.csv">未接入数值队列</a> · <a href="verification.json">独立核验</a></p><p>当前入口：<code>data.training_ready.open_training_datasets()</code>；v1/v2入口保留历史。文献v26与循环v029仍为封存底座，本版是两篇论文的明确扩展，不代表原批次27（含木质素）整体封版。</p></section>
<section><h2>目标继续执行</h2><p>下一批优先核读尚未完成的木质素/商用碳布正文和SI，区分弯折电容恢复与循环保持率；再继续原表、曲线与现有未接入队列。工作总目标尚未完成。</p></section></main></html>'''
    (OUT/'目标执行与文献接入进度.html').write_text(page.replace('CAPS',rows).replace('ISSUES',issues),encoding='utf8');c.close()
    print('Report exported; active goal remains incomplete.')

if __name__=='__main__':report()
