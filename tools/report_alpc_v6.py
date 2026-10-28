"""Export full fact dispositions and readable ALPC progress without fitting."""
from pathlib import Path
import collections,csv,html,io,json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.extract_alpc_v6 import OUT,DB,BASE,DOI,EIDS,read,write,sha
from data.training_latest import open_training_datasets

def report():
    assert not(OUT/'merge_manifest.json').exists()
    s=read(OUT/'summary.json')
    with open_training_datasets()as d:
        for name,only in [('all_fact_usage.csv',False),('unconnected_numeric_queue.csv',True)]:
            stream=io.StringIO(newline='');fields=['fact_id','doi','sample_name','material_stage','field_name','value','unit','source_path','source_sha256','locator','disposition','task_receipts'];w=csv.DictWriter(stream,fieldnames=fields,lineterminator='\n');w.writeheader()
            for rr,uu,disp in d.connection.execute('select f.record_json,u.record_json,u.disposition from facts f join usage_ledger u using(fact_id)order by f.fact_id'):
                f=json.loads(rr);u=json.loads(uu)
                if only and(f['value']is None or u['uses']):continue
                row={k:f.get(k)for k in fields};row.update(disposition=disp,task_receipts=len(u['uses']));w.writerow(row)
            (OUT/name).write_text(stream.getvalue(),encoding='utf-8-sig')
        q=read(BASE/'main3e_unlinked_priorities.json');pending=[r for r in q['next_review_records']if r['endpoint_id']not in EIDS];groups=collections.defaultdict(list)
        for r in pending:groups[r['doi']].append(r)
        write(OUT/'main3e_unlinked_priorities.json',dict(main3e_rows=47,linked_rows=23,unlinked_rows=len(pending),unlinked_main_source_families=len(groups),next_review_records=pending,priority_sources=[dict(doi=doi,main_rows=len(rows),samples=sorted({r['sample_name']for r in rows}),local_sources=rows[0]['local_sources'])for doi,rows in sorted(groups.items())]))
        rows={r['row_id']:r for r in d.rows('cycle:reported_3e')};details=[]
        for eid in EIDS:
            r=rows[eid];e=r['v6_material_evidence'];details.append(dict(endpoint_id=eid,sample=r['sample_name'],electrolyte=r['features']['electrolyte'],retention_pct=r['target'],cycle_count=r['features']['cycle_count'],new_nonmissing_cells=len(e['added_nonmissing_fields']),existing_attested_cells=len(e['existing_values_attested']),new_fields=e['added_nonmissing_fields'],material_key=r['material_key']))
        write(OUT/'main_feature_changes.json',details);write(OUT/'main_feature_coverage.json',d.feature_coverage('cycle:reported_3e'))
        sources=len({json.loads(r[0])['doi']for r in d.connection.execute('select record_json from facts')})
        write(OUT/'coverage_counts.json',dict(registered_sources=s['reviewed_sources'],material_fact_sources=sources,main_joined_rows=23,main_total_rows=47,unlinked_main_rows=24,whole_paper_completion_claimed=False))
    rr=''.join('<tr><td>'+html.escape(r['electrolyte'])+'</td><td>'+str(r['retention_pct'])+'</td><td>'+str(r['cycle_count'])+'</td><td>+'+str(r['new_nonmissing_cells'])+'</td><td>'+str(r['existing_attested_cells'])+'</td></tr>'for r in details)
    graph=read(OUT/'graph_rate_captures.json');gr=''.join('<tr><td>'+x['sample_name']+'</td><td>'+str(x['current_A_g'])+'</td><td>'+str(x['readout_F_g'])+'</td><td>±8 F/g</td><td>'+('正文锚点确认'if x['current_A_g']==1 else'新增读图条件')+'</td></tr>'for x in graph['captures'])
    page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ALPC正文与补充材料接入进度</title><style>body{font:16px/1.75 system-ui,"Microsoft YaHei",sans-serif;background:#f1f5f2;color:#233b31;margin:0}main{max-width:1100px;padding:24px;margin:auto}h1{line-height:1.35}.cards{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}.card,section{padding:20px;background:#fff;border:1px solid #dce5df;border-radius:12px;margin:18px 0}.card{margin:0}.card strong{display:block;font-size:28px;color:#207354}table{width:100%;border-collapse:collapse}td,th{text-align:left;padding:10px;border-bottom:1px solid #dfe7e2;white-space:nowrap}.table{overflow:auto}.warning{border-left:5px solid #b87922}a{color:#246e53}li{margin:8px 0}.muted{color:#667b70}summary{cursor:pointer;font-weight:600}code{overflow-wrap:anywhere}@media(max-width:650px){main{padding:14px}h1{font-size:26px}.cards{grid-template-columns:repeat(2,1fr)}.card{padding:12px}}</style><main><p class="muted">2026-10-29 · 持续目标active · 本轮拟合0</p><h1>ALPC正文与补充材料：补齐两条主记录</h1><div class="cards"><div class="card"><strong>23 / 47</strong>主集规范材料关联，原21条</div><div class="card"><strong>+38</strong>主集非空特征单元</div><div class="card"><strong>16</strong>已有单元补证，原值未改</div><div class="card"><strong>RATE%</strong>3,467 / 4,922数值接入</div></div>
<section><h2>直接补齐现有训练输入</h2><p>核读本地U024正文和SUP_139补充材料，关联同一ALPC-800材料在两种电解液下的既有循环记录。新增EDX原子组成、前驱体干燥、NH₄Cl处理、酸洗、最终干燥、电极制备及XRD峰位等字段。38是两条记录的非空单元数，包含共同条件，不能当38个独立材料参数。</p><div class="table"><table><thead><tr><th>电解液，均0.5M</th><th>保持率%，未改</th><th>循环次数，未改</th><th>新增单元</th><th>已有单元补证</th></tr></thead><tbody>ROWS</tbody></table></div><p>三电极主集仍47条/34家族，双电极主集仍31条/25家族。ALPC-700、800、900全部同源留出；本批无新循环准入。</p></section>
<section class="warning"><h2>找到数值，也要核对它代表什么</h2><ul><li>表S1的ALPC-800微孔面积757大于BET718，微孔体积0.382大于总孔体积0.35；ALPC-700微孔面积37大于BET25。三项原值保存，计量/方法一致性待核查，未填入训练字段，也未擅自交换表列。</li><li>EDX氮11.23%、氧8.54%与XPS氮4.64%、氧7.44%属于不同测量通道，分别保留。ORR催化剂负载约0.35mg/cm²不替换超级电容器已有1.2mg/cm²。</li><li>酸性GCD正文421F/g与SI比较表409F/g并存。沿用正文421，原图锚点包络支持该值；409保留为异文，未称作者已更正。</li><li>七个酸性CV电容与正文反序扫描速率暂不配对；器件摘要1A/g与图文10A/g保留差异。ORR的70%电流耐久性、模拟石墨烯数据都不变成电容保持率。</li></ul></section>
<section><h2>表格、倍率图和辅助任务已接入</h2><p>新增91项材料/制备事实，85项为数值，76项有实际训练输入或辅助目标回执。表S1共21个自身数值格，18个按方法选择、3个保留待核查。原文三个温度样品分别登记；6个共同近似Raman峰位仅保留为元数据。</p><p>新增34条独特电容报告：31个三电极GCD条件、2个中性CV条件、1个器件作者公式用途。另有3个EIS电荷转移电阻辅助目标。普通GCD视图220行/33家族包含于含图视图425行/33家族，两视图不相加。</p><p>图7(e)捕获30个倍率标记，其中3个是正文已有锚点确认，净27个新增条件。读图包络±8F/g、横轴容差±0.1A/g是图像读取界限，不能当作者标准差或置信区间；不平滑、不强制单调。</p><details id="rates"><summary>展开30个倍率标记及去重角色</summary><div class="table"><table><thead><tr><th>样品</th><th>A/g</th><th>读图F/g</th><th>读取包络</th><th>角色</th></tr></thead><tbody>GRAPHROWS</tbody></table></div></details><p>SI的28条二手比较行、10个DFT数值格单独索引，未伪装为新原始实验。表S1～S6均已有去向；其余连续曲线、图像与争议方法尚未完成全量提取。</p></section>
<section><h2>进度口径与接续</h2><p>累计3,467/4,922数值事实接入，RATE%；这不是全部论文利用率、独立实验数，也不是已拟合使用率。70个来源登记、66个有材料事实，均未声明整篇完成；另253项非标量/空值与1,455项未接入数值仍有明确去向。</p><p>当前统一入口：<code>data.training_latest.open_training_datasets()</code>。只读连接受SHA保护的历史库；有前后哈希回执的派生行补齐，不覆盖原始事实。旧v1～v5调用方式保持。</p><p>下一步继续剩余24条/24来源主集本地原文、固定37条待补证和已读来源剩余表图/SI。保留全部原标签、冻结、未知与旧模型；总体目标仍active。</p></section>
<section><h2>原文证据与核验</h2><p><a href="README.md">调用说明</a> · <a href="evidence/SI_p6.png">表S1原图</a> · <a href="evidence/Figure7e_rate_review.png">倍率图证据</a> · <a href="main_feature_changes.json">逐行特征变化</a> · <a href="overlay_changes.json">前后值与出处</a> · <a href="extraction_coverage.json">表图覆盖去向</a> · <a href="verification.json">数据核验</a> · <a href="unconnected_numeric_queue.csv">未接入队列</a></p><p>表S1为图像表格，本批逐格视觉转录并保存图像SHA；没有声称独立OCR核验。正文与SI文本数值另经新鲜PDF解析核对。</p></section></main></html>'''
    (OUT/'ALPC文献与主集质量进度.html').write_text(page.replace('RATE',f"{100*s['numeric_fact_connection_rate']:.2f}").replace('GRAPHROWS',gr).replace('ROWS',rr),encoding='utf-8')
    print('ALPC report, complete fact dispositions and24-source next queue saved')

if __name__=='__main__':report()
