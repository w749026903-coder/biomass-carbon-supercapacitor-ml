"""Export source/field coverage, evidence priorities and a standalone report."""
from pathlib import Path
import collections,csv,html,io,json,sqlite3,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.improve_training_inputs_v2 import OUT,DB,BASE,read,write,sha
from data.training_current import open_training_datasets

def csvout(name,rows):
    stream=io.StringIO(newline='');w=csv.DictWriter(stream,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
    (OUT/name).write_text(stream.getvalue(),encoding='utf-8-sig')

def report():
    assert not(OUT/'merge_manifest.json').exists()
    s=read(OUT/'summary.json');c=sqlite3.connect(DB.as_uri()+'?mode=ro',uri=True);facts={fid:json.loads(r)for fid,r in c.execute('select fact_id,record_json from facts')}
    used={fid for fid, in c.execute('select distinct fact_id from fact_uses')};new=set(read(OUT/'new_connected_fact_ids.json'));source={}
    for doi, in c.execute('select doi from sources'):
        source[doi]=dict(doi=doi,numeric_facts=0,connected_numeric_facts=0,added_connections=0,metadata_numeric_facts=0,remaining_numeric_facts=0,connection_rate=None,whole_paper_extraction_complete=False)
    for fid,f in facts.items():
        r=source.setdefault(f['doi'],dict(doi=f['doi'],numeric_facts=0,connected_numeric_facts=0,added_connections=0,metadata_numeric_facts=0,remaining_numeric_facts=0,connection_rate=0,whole_paper_extraction_complete=False))
        if f['value']is None:continue
        r['numeric_facts']+=1;r['connected_numeric_facts']+=fid in used;r['added_connections']+=fid in new
    for fid, in c.execute('select fact_id from measurement_metadata'):source[facts[fid]['doi']]['metadata_numeric_facts']+=1
    for r in source.values():
        r['remaining_numeric_facts']=r['numeric_facts']-r['connected_numeric_facts'];r['connection_rate']=r['connected_numeric_facts']/r['numeric_facts'] if r['numeric_facts']else None
    sources=sorted(source.values(),key=lambda r:(-r['added_connections'],-r['remaining_numeric_facts'],r['doi']));csvout('source_utilization.csv',sources)
    with open_training_datasets()as d:
        fields=d.feature_coverage('cycle:reported_3e');csvout('main3e_feature_coverage.csv',fields)
        coverage={task:d.feature_coverage(task)for task in ['cycle:reported_3e','cycle:reported_2e','capacity:3e_reported','material:ordinary_biomass_pretest:BET_surface_area_m2_g']}
        write(OUT/'feature_coverage.json',coverage)
        main=d.rows('cycle:reported_3e');families=collections.Counter(r['source_family']for r in main)
        write(OUT/'source_concentration.json',dict(main3e_rows=47,source_families=34,maximum_rows_one_family=max(families.values()),
            maximum_row_share=max(families.values())/47,source_equal_weight_required=True,field_level_coverage='main3e_feature_coverage.csv',
            task_numeric_receipts={task:c.execute('select count(distinct fact_id)from fact_uses where task=?',(task,)).fetchone()[0]for task in ['cycle:reported_3e','cycle:reported_2e','capacity:3e_reported','capacity:3e_with_graph']}))
    priority=[]
    for disp,n in c.execute("select disposition,count(*)from usage_ledger join facts using(fact_id)where numeric=1 and disposition!='connected_to_training_inputs'group by disposition order by count(*)desc"):
        actions={
          'specialized_target_or_feature_contract_pending':'Review source-specific XPS peak numbering/assignment, explicit synthesis masses and special endpoints; avoid assigning a target solely to raise counts.',
          'composition_or_measurement_basis_unresolved':'Read method, table footnotes or SI to establish mass/atomic/envelope basis; preserve unknowns.',
          'measurement_uncertainty_metadata_not_independent_predictor':'Other author errors / fit errors already retained as quality metadata, not forced predictor targets.',
          'measurement_metadata_not_independent_predictor':'Already indexed as measurement/assignment metadata. Not a backlog requiring forced predictor admission.',
          'competing_or_nonselected_report':'Review the original table/sample conditions and retain both values until resolved.',
          'method_or_unit_ambiguity_retained':'Compare table headers with methods; never repair by value magnitude alone.',
          'stage_specific_or_no_qualified_target':'Continue explicit precursor/final-stage linkage and independent characterization; no automatic inheritance.',
        }
        priority.append(dict(disposition=disp,numeric_facts=n,next_action=actions.get(disp,'Review the existing original evidence and task-specific identity or lineage contract.')))
    write(OUT/'remaining_work.json',dict(numeric_unconnected=1411,measurement_metadata_not_predictor=315,other_unconnected_numeric=1096,
         nonpoint_or_missing=201,previous_fixed_cycling_pending=37,all_papers_fully_extracted=False,actions=priority))
    small={k:s[k]for k in ['numeric_facts_connected_to_training_inputs','numeric_fact_connection_rate','additional_connected_numeric_facts','net_connection_change_from_v1','additional_main3e_nonmissing_cells','withdrawn_uncertainty_facts']}
    write(OUT/'report_metrics.json',small)
    esc=html.escape
    st=''.join('<tr><td>'+esc(r['doi'])+'</td><td>'+str(r['numeric_facts'])+'</td><td>'+str(r['connected_numeric_facts'])+'</td><td>+'+str(r['added_connections'])+'</td><td>'+(f"{100*r['connection_rate']:.1f}%"if r['connection_rate']is not None else '无材料数值分母')+'</td></tr>'for r in sources)
    ft=''.join('<tr data-supported="'+str(int(r['source_families']>=3 and r['nonmissing_fraction']>=.2))+'"><td>'+esc(r['field'])+'</td><td>'+str(r['nonmissing_rows'])+'/47</td><td>'+str(r['source_families'])+'</td><td>'+f"{100*r['maximum_source_row_share']:.0f}%"+'</td></tr>'for r in sorted(fields,key=lambda x:(-x['source_families'],-x['nonmissing_rows'],x['field'])))
    doc='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>文献利用与数据库质量 v2</title>
<style>body{font:16px/1.65 system-ui,"Microsoft YaHei",sans-serif;color:#20312f;background:#f2f5f1;margin:0}main{max-width:1160px;padding:28px;margin:auto}h1{font-size:30px;line-height:1.3}h2{font-size:22px}p{max-width:95ch}.cards{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}.card,section{background:white;border:1px solid #d9e4dd;border-radius:12px;padding:20px;margin:16px 0}.card strong{display:block;font-size:28px;color:#1b6651}.card{margin:0}.muted{color:#5e6a65}.bar{height:14px;background:#e5ebe8;border-radius:9px;overflow:hidden}.bar i{display:block;height:100%;background:#267c62}.table{overflow:auto;max-height:470px}table{border-collapse:collapse;width:100%;font-size:14px}th,td{text-align:left;padding:10px;border-bottom:1px solid #e1e8e2}thead{position:sticky;top:0;background:#eaf0ec}td:first-child{min-width:230px;overflow-wrap:anywhere}code{overflow-wrap:anywhere;word-break:break-word}button{padding:9px 15px;border-radius:7px;border:1px solid #9ab6a8;background:white;color:#235640;cursor:pointer}a{color:#236b54}.note{border-left:4px solid #ca8f3b;padding-left:14px}@media(max-width:700px){main{padding:16px}.cards{grid-template-columns:repeat(2,1fr)}h1{font-size:25px}.card{padding:12px}.card strong{font-size:24px}}</style>
<main><p class="muted">2026-10-28 · 准备输入与证据质量 · 本轮新增拟合 0 次</p><h1>让已有论文数据进入可追溯的训练输入</h1>
<div class="cards"><div class="card"><strong>68.43%</strong>唯一数值事实接入率</div><div class="card"><strong>+245</strong>新接入数值，覆盖21来源</div><div class="card"><strong>+23</strong>主集非空特征单元</div><div class="card"><strong>47 / 34</strong>三电极记录 / 来源</div></div>
<section><h2>这一批改变了什么</h2><p>新增导电率、密度、润湿性、XPS化学组分和明确阶段的前驱体任务；保留压片、薄膜、骨架与堆积等方法差别。移出旧层中10项误差数值及10条误差目标行，原值与撤回原因均可追溯。接入总数从2,823净增235至3,058。</p><div class="bar"><i style="width:68.43%"></i></div><p class="muted">分母4,469项已提取数值，覆盖65个已复核登记来源，其中61个有材料事实；不代表全部文献已提取完，也不代表3,058个独立循环样本或已经训练使用。</p></section>
<section><h2>仍然限制模型的因素</h2><p>当前循环标签没有增加。主集122个候选字段中，按“至少3来源、20%记录非空”的说明性条件，全数据覆盖仅30列；正式训练时必须在每个训练折重新检查，不能用留出来源选特征。大部分论文仍未完成整篇表格、曲线及SI提取。</p><p class="note">剩余1,411项数值中，315项已作为测量或谱峰元数据保留，不应强制当预测变量；其余1,096项继续核对具体用途、阶段、单位或争议。另201项非点或缺失信息保留，原37条循环待补证与既有冻结不变。</p></section>
<section><h2>三电极特征覆盖</h2><p>最后一列显示有该字段的记录中，最大单一来源占比。单来源字段不能据此获得跨来源预测能力。</p><button id="filter" type="button">只看覆盖示例条件通过字段</button><p id="field-status" class="muted">显示全部122个候选字段</p><div class="table"><table id="features"><thead><tr><th>字段</th><th>非空记录</th><th>独立来源</th><th>最大来源占比</th></tr></thead><tbody>FIELDROWS</tbody></table></div></section>
<section><h2>已提取来源的数值去向</h2><p>这是已提取事实的接入情况；没有把未读完的论文称为“利用完成”。多任务重叠只计一次。</p><div class="table"><table><thead><tr><th>DOI</th><th>数值</th><th>接入</th><th>本批新增</th><th>接入率</th></tr></thead><tbody>SOURCEROWS</tbody></table></div></section>
<section><h2>可调用文件与核验</h2><p><a href="README.md">调用说明</a> · <a href="source_utilization.csv">逐来源利用率</a> · <a href="main3e_feature_coverage.csv">逐字段覆盖</a> · <a href="unconnected_numeric_queue.csv">未接入逐项队列</a> · <a href="quality_corrections.json">质量修正原值与回执</a> · <a href="verification.json">独立核验</a></p><p>当前入口：<code>data.training_current.open_training_datasets()</code>。历史v1入口和数据库完整保留；原v26/v029及旧模型没有改写。</p></section></main>
<script>let filtered=false;document.getElementById('filter').addEventListener('click',()=>{filtered=!filtered;let n=0;document.querySelectorAll('#features tbody tr').forEach(r=>{r.hidden=filtered&&r.dataset.supported!=='1';if(!r.hidden)n++});document.getElementById('field-status').textContent=`显示 ${n} 个字段；仅为覆盖说明，正式选列在训练折内完成`;document.getElementById('filter').textContent=filtered?'显示全部字段':'只看覆盖示例条件通过字段';});</script></html>'''
    (OUT/'文献利用与质量结果.html').write_text(doc.replace('FIELDROWS',ft).replace('SOURCEROWS',st),encoding='utf8')
    print(json.dumps(dict(sources=len(sources),additional_connected_sources=sum(r['added_connections']>0 for r in sources),main3e_candidate_columns=len(fields),full_data_illustrative_supported_columns=sum(r['source_families']>=3 and r['nonmissing_fraction']>=.2 for r in fields)),ensure_ascii=False))
    c.close()

if __name__=='__main__':report()
