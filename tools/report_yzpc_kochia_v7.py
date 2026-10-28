"""Full disposition exports and main-task coverage progress for reviewed v7."""
from pathlib import Path
import collections,csv,html,io,json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.curate_yzpc_kochia_v7 import OUT,YZ,KA
from tools.extract_lignin_cf_v4 import read,write
from data.training_latest import open_training_datasets

def report():
    assert not(OUT/'merge_manifest.json').exists()
    s=read(OUT/'summary.json');spec=read(OUT/'reviewed_extraction_spec.json');base=ROOT/spec['parent_directory'];details=read(OUT/'main_feature_changes.json');ids={x['endpoint_id']for x in details}
    with open_training_datasets()as d:
        for name,only in [('all_fact_usage.csv',False),('unconnected_numeric_queue.csv',True)]:
            st=io.StringIO(newline='');fields=['fact_id','doi','sample_name','material_stage','field_name','value','unit','source_path','source_sha256','locator','disposition','task_receipts'];w=csv.DictWriter(st,fieldnames=fields,lineterminator='\n');w.writeheader()
            for rr,uu,disp in d.connection.execute('select f.record_json,u.record_json,u.disposition from facts f join usage_ledger u using(fact_id)order by f.fact_id'):
                f=json.loads(rr);u=json.loads(uu)
                if only and(f['value']is None or u['uses']):continue
                w.writerow({k:f.get(k)for k in fields}|dict(disposition=disp,task_receipts=len(u['uses'])))
            (OUT/name).write_text(st.getvalue(),encoding='utf-8-sig')
        q=read(base/'main3e_unlinked_priorities.json');pending=[x for x in q['next_review_records']if x['endpoint_id']not in ids];groups=collections.defaultdict(list)
        for x in pending:groups[x['doi']].append(x)
        write(OUT/'main3e_unlinked_priorities.json',dict(main3e_rows=47,linked_rows=25,unlinked_rows=len(pending),unlinked_main_source_families=len(groups),next_review_records=pending,priority_sources=[dict(doi=doi,main_rows=len(rows),samples=sorted({x['sample_name']for x in rows}),local_sources=rows[0]['local_sources'])for doi,rows in sorted(groups.items())]))
        write(OUT/'main_feature_coverage.json',d.feature_coverage('cycle:reported_3e'))
        write(OUT/'coverage_counts.json',dict(registered_sources=s['reviewed_sources'],material_fact_sources=len({json.loads(x[0])['doi']for x in d.connection.execute('select record_json from facts')}),main_joined_rows=25,main_total_rows=47,unlinked_main_rows=22,whole_paper_completion_claimed=False))
    mainrows=''.join('<tr><td>'+html.escape(x['sample_name'])+'</td><td>'+str(x['target'])+'</td><td>+'+str(len(x['added_nonmissing_fields']))+'</td><td>'+str(len(x['existing_values_attested']))+'</td></tr>'for x in details)
    fields=''.join('<h3>'+html.escape(x['sample_name'])+'</h3><p>'+html.escape('、'.join(x['added_nonmissing_fields']))+'</p>'for x in details)
    page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>药渣与地肤文献接入进度</title><style>body{font:16px/1.75 system-ui,"Microsoft YaHei",sans-serif;background:#f2f5f1;color:#263c32;margin:0}main{max-width:1100px;margin:auto;padding:24px}h1{line-height:1.35}.cards{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}.card,section{background:#fff;border:1px solid #dce5dd;border-radius:12px;padding:20px;margin:18px 0}.card{margin:0}.card strong{display:block;color:#237453;font-size:28px}table{border-collapse:collapse;width:100%}th,td{text-align:left;padding:10px;border-bottom:1px solid #e0e7e1;white-space:nowrap}.table{overflow:auto}.warn{border-left:5px solid #b67c24}a{color:#237453}li{margin:8px 0}summary{cursor:pointer;font-weight:600}details p,code{overflow-wrap:anywhere}.muted{color:#65786c}@media(max-width:650px){main{padding:14px}.cards{grid-template-columns:repeat(2,1fr)}.card{padding:12px}h1{font-size:26px}}</style><main><p class="muted">2026-10-29 · 全量质量目标active · 本轮拟合0</p><h1>药渣与地肤：补齐两条主训练记录</h1><div class="cards"><div class="card"><strong>25 / 47</strong>主集规范材料关联，原23条</div><div class="card"><strong>+34</strong>新增非空主集特征单元</div><div class="card"><strong>260</strong>新增唯一数值输入回执</div><div class="card"><strong>RATE%</strong>3,727 / 5,197数值接入</div></div>
<section><h2>已有论文继续进入实际输入</h2><p>核读药渣YZPC正文、地肤KAC正文的自有表格、制备方法及电化学结果。两条既有主记录完成材料桥接；26个已有非空单元只补证，旧标签、工况及非空值全部保持。主3E仍47条/34家族、2E仍31条/25家族。</p><div class="table"><table><thead><tr><th>样品</th><th>保持率%，未改</th><th>新增单元</th><th>已有值补证</th></tr></thead><tbody>MAINROWS</tbody></table></div><p>新增电极配方、压片、干燥、接触角及制备参数等。配方16:3:1与8:1:1按原比例明确换算；这些共同或受约束字段不等于34个独立物理参数。</p><details id="fields"><summary>展开本批新增字段</summary>FIELDS</details></section>
<section><h2>阶段、表格与辅助目标</h2><p>12项材料/阶段登记含原始药渣、预碳化YZC、5个最终药渣碳，以及原始地肤、KC与3个活化KAC。它们只有两个来源家族，不能当12篇独立论文。301项事实中275为数值，260已连接，26项未报告保留为空。</p><p>两张自有表共62个数值格均有回执；73个材料属性目标按阶段分开，排除同一测量块。14个电容报告包含9个材料信息较完整的3E条件、3个缺自身BET的对照条件、2个明确双电极总活性质量的器件条件；另有23个EIS响应目标。</p><p>普通3E GCD共229行/35家族，包含于含图434行/35家族；三个缺BET对照在单独用途读取，未借用KAC-5的BET，也未混入完整材料视图。器件用途共7行/2来源；同DOI所有阶段、材料、倍率与辅助任务一起留出。</p></section>
<section class="warn"><h2>按证据补齐，同时保留已知问题</h2><ul><li>YZPC-3的微孔体积0.63、总孔体积1.223与报告比例0.37不相容，沿用已有冻结；未填入微孔/介孔字段，不再把旧问题当新发现。</li><li>药渣负载2–3mg/cm²以两个边界保存，精确点值保持未知；不填2.5。地肤58.25°是70ms接触角，药渣92°的测量时点未知，均不冒称平衡角。</li><li>地肤KC是优化后的800°C碳前驱体，KC-800的184F/g同一结果只用一次。800°C预碳化和600°C活化分阶段，不能调换。</li><li>药渣器件印刷功率公式以电压作分母，原式单独保留；不据此计算新功率标签。地肤原料TGA三段语义待核，不当成最终碳收率；原料FTIR仅作为测量元数据。</li><li>药渣详细方法称混合药渣、结论出现大黄根措辞，差异保留，不猜原料比例。两篇SI本次均403未取得，不造其表格、组分和曲线。</li></ul></section>
<section><h2>累计进度与剩余工作</h2><p>累计3,727/5,197数值事实接入，RATE%；不是整篇论文利用率、独立实验数或模型拟合使用率。72个来源登记、68个有材料事实，均未声称整篇完成。279项非标量/空值、1,470项未接入数值仍有逐项去向。</p><p>剩22条/22来源主集待与新版材料库规范桥接，均有本地原文；它们已有的历史BET和工况仍在使用，不能说这些论文完全未用。后续继续本地待处理来源、固定37待证及已读来源的其余曲线/SI。</p><p>调用入口仍为<code>data.training_latest.open_training_datasets()</code>；本批只增加受SHA保护的版本化数据与有前后值回执的派生输入，不改历史库、原文或旧模型。</p></section>
<section><h2>证据与核验</h2><p><a href="README.md">调用说明</a> · <a href="evidence/YZPC_p5.png">药渣原始表1</a> · <a href="evidence/KAC_p5.png">地肤XPS与接触角原图</a> · <a href="main_feature_changes.json">逐记录变化</a> · <a href="overlay_changes.json">更新前后与出处</a> · <a href="extraction_coverage.json">表图覆盖</a> · <a href="unconnected_numeric_queue.csv">未接入队列</a> · <a href="verification.json">数据核验</a> · <a href="SI_access_attempts.json">SI获取回执</a></p><p>62个自有表数值格由新鲜PDF解析另行核对，图中原子基准和70ms标记经视觉检查。SQLite、原件SHA、父版原值、实际输入回执、来源隔离与目标泄漏核验通过。未完成连续曲线与SI的范围继续列队；本批不进行训练或新增循环准入。</p></section></main></html>'''
    page=page.replace('MAINROWS',mainrows).replace('FIELDS',fields).replace('RATE',f"{100*s['numeric_fact_connection_rate']:.2f}")
    (OUT/'药渣地肤文献与数据库进度.html').write_text(page,encoding='utf-8');print('v7 report,full disposition exports and22-source queue saved')

if __name__=='__main__':report()
